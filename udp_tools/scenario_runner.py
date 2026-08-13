# scenario_runner.py
import time
from unittest import runner
from mininet.net import Mininet
from pathlib import Path

class ScenarioRunner:
    def __init__(self, net: Mininet, results_dir="/home/duy/sdn_qos_project/results", algorithm_name="dijkstra", metric_manager=None):
        self.net = net
        self.algorithm_name = algorithm_name
        self.metric_manager = metric_manager  # Reference to controller's MetricManager for updating link params
        self.network_graph = metric_manager.graph if metric_manager else None # For backward compatibility if needed
        
        # Tạo folder con cho từng thuật toán: results/dijkstra, results/pso, etc.
        base_results_dir = Path(results_dir)
        self.results_dir = base_results_dir / algorithm_name
        
        # Ensure absolute path and clean old results
        if self.results_dir.exists():
            import shutil
            for f in self.results_dir.glob("*.csv"):
                f.unlink()
        self.results_dir.mkdir(exist_ok=True, parents=True)
        
        # ================== ĐƯỜNG DẪN LƯU RESULTS==================
        self.udp_path = "/home/duy/sdn_qos_project/udp_tools"  

    def start_receiver(self, host_name, port=5001, output_csv=None):
        if output_csv is None:
            output_csv = self.results_dir / f"sc_{host_name}_p{port}.csv"
        
        host = self.net.get(host_name)
        cmd = f"cd {self.udp_path} && python3 udp_receiver_full.py {port} {output_csv}"
        
        host.cmd(f"{cmd} > /tmp/receiver_{host_name}.log 2>&1 &")
        print(f"✅ Receiver started on {host_name} (port {port}) → {output_csv}")
        time.sleep(1.5) # Minimum time for controller discovery

    def start_sender(self, src_host, dst_ip, port=5001, duration=30, target_bps=10_000_000):
        host = self.net.get(src_host)
        cmd = f"cd {self.udp_path} && python3 udp_sender.py {dst_ip} {port} {duration} {target_bps}"
        cmd += " > /tmp/sender.log 2>&1 &"   # chạy background
        
        host.cmd(cmd)
        print(f"🚀 Sender {src_host} → {dst_ip}:{port} ({duration}s @ ~{target_bps/1e6:.1f} Mbps)")

    def modify_link(self, s1, s2, bw=None, delay=None, loss=None):
        try:
            switch1 = self.net.get(s1)
            switch2 = self.net.get(s2)

            if not switch1 or not switch2:
                print(f"❌ Switch {s1} or {s2} not found")
                return False

            # Tìm interface kết nối giữa 2 switch
            intf1, intf2 = None, None
            for link in self.net.links:
                if link.intf1.node == switch1 and link.intf2.node == switch2:
                    intf1, intf2 = link.intf1, link.intf2
                    break
                elif link.intf1.node == switch2 and link.intf2.node == switch1:
                    intf1, intf2 = link.intf2, link.intf1
                    break

            if not intf1:
                print(f"❌ Link {s1}-{s2} not found")
                return False

            # Áp dụng thông số lên cả 2 chiều
            for intf in [intf1, intf2]:
                node = intf.node
                dev = intf.name

                # Xóa qdisc cũ
                node.cmd(f'tc qdisc del dev {dev} root 2>/dev/null')

                # Build netem command (delay, loss)
                netem_params = ""
                if delay:
                    netem_params += f" delay {delay}"
                if loss is not None:
                    netem_params += f" loss {loss}%"

                if bw is not None:
                    # Dùng tbf để giới hạn bandwidth, netem để delay/loss
                    node.cmd(f'tc qdisc add dev {dev} root handle 1: tbf '
                            f'rate {bw}mbit burst 15k latency 50ms')
                    if netem_params:
                        node.cmd(f'tc qdisc add dev {dev} parent 1:1 '
                                f'handle 10: netem{netem_params}')
                elif netem_params:
                    node.cmd(f'tc qdisc add dev {dev} root netem{netem_params}')

            print(f"✅ Link {s1}-{s2} modified: bw={bw}, delay={delay}, loss={loss}")
            return True

        except Exception as e:
            print(f"❌ Error: {e}")
            return False

    def create_bottleneck(self, background_pairs, duration=60):
        print("🔥 Creating bottleneck background traffic...")
        for src, dst_ip, bps in background_pairs:
            self.start_sender(src, dst_ip, port=5002, duration=duration, target_bps=bps)
        time.sleep(1) # Added sleep to ensure background traffic starts

    def down_links(self, links):
        print("⚠️ Bringing links DOWN...")
        for s1, s2 in links:
            try:
                switch1 = self.net.get(s1)
                switch2 = self.net.get(s2)
                if not switch1 or not switch2:
                    continue

                link_obj = None
                for link in self.net.links:
                    if (link.intf1.node == switch1 and link.intf2.node == switch2) or \
                    (link.intf1.node == switch2 and link.intf2.node == switch1):
                        link_obj = link
                        break

                if link_obj:
                    intf1 = link_obj.intf1
                    intf2 = link_obj.intf2

                    # ✅ CHỈ dùng ip link set - không gây cascade
                    switch1.cmd(f"ip link set {intf1.name} down")
                    switch2.cmd(f"ip link set {intf2.name} down")

                    print(f"   ❌ Brought down: {intf1} and {intf2}")
                else:
                    self.net.configLinkStatus(s1, s2, 'down')

            except Exception as e:
                print(f"   ❌ Error downing link {s1}-{s2}: {e}")

        time.sleep(2)

    def restore_links(self, links):
        print("🔄 Restoring links...")
        for s1, s2 in links:
            try:
                switch1 = self.net.get(s1)
                switch2 = self.net.get(s2)
                if not switch1 or not switch2:
                    continue

                link_obj = None
                for link in self.net.links:
                    if (link.intf1.node == switch1 and link.intf2.node == switch2) or \
                    (link.intf1.node == switch2 and link.intf2.node == switch1):
                        link_obj = link
                        break

                if link_obj:
                    intf1 = link_obj.intf1
                    intf2 = link_obj.intf2

                    # ✅ Dùng ovs-vsctl thay vì ip link set
                    # ovs-vsctl chỉ thay đổi state port trong OVS
                    # không trigger re-negotiate toàn bộ switch
                    switch1.cmd(f"ovs-ofctl mod-port {s1} {intf1.name} up")
                    switch2.cmd(f"ovs-ofctl mod-port {s2} {intf2.name} up")
                    switch1.cmd(f"ip link set {intf1.name} up")
                    switch2.cmd(f"ip link set {intf2.name} up")

                    print(f"   ✅ Brought up: {intf1} and {intf2}")
                else:
                    self.net.configLinkStatus(s1, s2, 'up')

            except Exception as e:
                print(f"   ⚠️  Error restoring link {s1}-{s2}: {e}")

        time.sleep(1.5)

    def stop_all(self):
        print("🛑 Stopping all UDP processes...")
        # First stop senders to allow receivers to finish writing
        for h in self.net.hosts:
            h.cmd("pkill -SIGINT -f udp_sender.py 2>/dev/null || true")
        time.sleep(0.5)
        # Then stop receivers
        for h in self.net.hosts:
            h.cmd("pkill -SIGINT -f udp_receiver_full.py 2>/dev/null || true")
        time.sleep(1)

    def wait_for_stable(self, seconds=1):
        print(f"⏳ Waiting {seconds}s...")
        time.sleep(seconds)


def run_all_scenarios(net, algorithm_name="dijkstra"):
    runner = ScenarioRunner(net, algorithm_name=algorithm_name)
    
    print("\n" + "="*95)
    print(f"🚀 SDN QoS EXPERIMENT - FAT TREE k=4 [ALGORITHM: {algorithm_name.upper()}]")
    print("="*95)

    # # =========================================================
    # # SCENARIO 1: BASELINE PATH QUALITY (STATIC)
    # # =========================================================
    # print("\n===== [SCENARIO 1] BASELINE PATH QUALITY (h1 -> h9) =====")
    # runner.modify_link("s1", "s5", bw=5, delay = "10ms", loss=10)  # Tạo link yếu nhất trong topology để dễ thấy sự khác biệt giữa thuật toán
    # runner.modify_link("s9", "s3", bw=5, delay = "10ms", loss=10)  # Tạo
    # runner.modify_link("s10", "s17", bw=5, delay = "10ms", loss=10)  # Tạo
    
    # time.sleep(2)  # Increased wait for link parameter updates to propagate
    # runner.start_receiver("h10", port=5001, 
    #                       output_csv=runner.results_dir / "sc1_baseline.csv")
    # runner.wait_for_stable(2)  # Increased wait for topology/LLDP to be fully ready
    
    # runner.start_sender("h1", "10.0.0.10", port=5001,
    #                     duration=10, target_bps=8_000_000)

    # time.sleep(11) 
    # runner.stop_all()


    # # =========================================================
    # # SCENARIO 2: HEAVY CONGESTION (MULTI-FLOW COMPETITION)
    # # =========================================================
    # print("\n===== [SCENARIO 2] HEAVY CONGESTION (h1 -> h9) =====")
    
    # runner.start_receiver("h9", port=5001, 
    #                       output_csv=runner.results_dir / "sc2_congestion.csv")
    # runner.wait_for_stable(1.5)

    # # Main flow
    # runner.start_sender("h1", "10.0.0.9", port=5001,
    #                     duration=15, target_bps=7_000_000)

    # time.sleep(2) # Initial clean data

    # # 🔥 Create heavy congestion
    # runner.create_bottleneck([
    #     ("h2", "10.0.0.10", 8_000_000),
    #     ("h3", "10.0.0.11", 8_000_000),
    #     ("h4", "10.0.0.12", 8_000_000),
    # ], duration=10) 

    # time.sleep(11) 
    # runner.stop_all()


    # =========================================================
    # SCENARIO 3: FAILURE + CONGESTION + RECOVERY (HARD MODE)
    # =========================================================
    print("\n===== [SCENARIO 3] FAILURE + CONGESTION + RECOVERY (h2 -> h12) =====")

    runner.start_receiver("h9", port=5001, 
                          output_csv=runner.results_dir / "sc3_failure_phase2_failure_h9.csv")
    runner.start_receiver("h10", port=5001, 
                          output_csv=runner.results_dir / "sc3_failure_phase2_failure_h10.csv")
    runner.start_receiver("h11", port=5001, 
                          output_csv=runner.results_dir / "sc3_failure_phase2_failure_h11.csv")

    runner.wait_for_stable(2)

    # Main flow
    runner.start_sender("h1", "10.0.0.9", port=5001,
                        duration=30, target_bps=8_000_000)
    time.sleep(1) 
    runner.start_sender("h2", "10.0.0.10", port=5001,
                        duration=30, target_bps=8_000_000)
    time.sleep(1)
    runner.start_sender("h3", "10.0.0.11", port=5001,
                        duration=30, target_bps=8_000_000)
    time.sleep(1) 

    # Inject congestion



    # Break core links
    runner.down_links([
        ("s1", "s5"),
        ("s10", "s2"),
    ])

    time.sleep(4) 

    # Restore network
    # runner.restore_links([
    #     ("s1", "s5"),
    #     ("s10", "s2"),
    # ])

    time.sleep(10) 
    # runner.stop_all()

    print("\n🎉 ALL SCENARIOS COMPLETED")
