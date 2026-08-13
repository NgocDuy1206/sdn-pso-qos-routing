import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.link import TCLink
import os
import time

from udp_tools.scenario_runner import run_all_scenarios

class FatTree(Topo):
    def build(self):
        # Thay đổi k ở đây để điều chỉnh kích thước topology
        # k = 4: 16 hosts, k = 6: 54 hosts, k = 8: 128 hosts, k = 16: 1024 hosts
        k = 4
        half_k = k // 2
        
        # 1. Core Layer
        # Total core switches: (k/2)²
        core_switches = []
        for i in range(half_k**2):
            sw_name = f's{i+1}'
            sw = self.addSwitch(sw_name, dpid=f'{i+1:016x}')
            core_switches.append(sw)
            
        # 2. Pods
        # Aggregation and Edge switches offsets
        agg_offset = (half_k ** 2) + 1  # Start after core switches
        edge_offset = agg_offset + (k * half_k)  # Start after all aggregation switches
        host_idx = 1
        port_map = {} 
        for sw in core_switches:
            port_map[sw] = 1
        for p in range(k):
            aggr_switches = []
            edge_switches = []
            
            # Tạo Aggregation Switches cho mỗi Pod
            for i in range(half_k):
                name = f's{agg_offset}'
                sw = self.addSwitch(name, dpid=f'{agg_offset:016x}')
                aggr_switches.append(sw)
                agg_offset += 1
                
            # Tạo Edge Switches cho mỗi Pod
            for i in range(half_k):
                name = f's{edge_offset}'
                sw = self.addSwitch(name, dpid=f'{edge_offset:016x}')
                edge_switches.append(sw)
                edge_offset += 1
            
            # Kết nối Aggr <-> Core

            for i, aggr in enumerate(aggr_switches):
                if aggr not in port_map:
                    port_map[aggr] = 1
                for j in range(half_k):
                    core = core_switches[j * half_k + i]
                    if core not in port_map:
                        port_map[core] = 1
                    # Explicitly specify ports
                    self.addLink(aggr, core, 
                                port1=port_map[aggr], port2=port_map[core],
                                bw=10, delay="10ms", loss=5)
                    port_map[aggr] += 1
                    port_map[core] += 1
            
            # Kết nối Aggr <-> Edge     
            for aggr in aggr_switches:
                if aggr not in port_map:
                    port_map[aggr] = 1  
                for edge in edge_switches:
                    if edge not in port_map:
                        port_map[edge] = 1
                    self.addLink(aggr, edge, 
                                port1=port_map[aggr], port2=port_map[edge],
                                bw=10, delay="10ms", loss=5)
                    port_map[aggr] += 1
                    port_map[edge] += 1
            
            # Kết nối Edge <-> Host
            for edge in edge_switches:
                for j in range(half_k):
                    host = self.addHost(f'h{host_idx}')
                    self.addLink(edge, host, bw=10)
                    host_idx += 1

def run(algorithm_name="dijkstra"): 
    topo = FatTree()
    net = Mininet(
        topo=topo,
        controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6633),
        switch=OVSSwitch,
        link=TCLink
    )
    net.start()
    # Run scenarios with metric_manager
    # _apply_weak_links(net)
    run_all_scenarios(net, algorithm_name=algorithm_name)
    # CLI(net)    
    net.stop()  
def _apply_weak_links(net):
    """Áp dụng thông số yếu cho các link cụ thể ngay khi khởi tạo"""
    weak_links = [
        ("s1",  "s9",  dict(bw=5, delay="300ms", loss=10)),
        ("s5",  "s3",  dict(bw=5, delay="300ms", loss=10)),
        ("s10", "s17", dict(bw=5, delay="300ms", loss=10)),
    ]   

    for s1_name, s2_name, params in weak_links:
        s1 = net.get(s1_name)
        s2 = net.get(s2_name)

        # Tìm link giữa 2 switch
        intf1, intf2 = None, None
        for link in net.links:
            if link.intf1.node == s1 and link.intf2.node == s2:
                intf1, intf2 = link.intf1, link.intf2
                break
            elif link.intf1.node == s2 and link.intf2.node == s1:
                intf1, intf2 = link.intf2, link.intf1
                break

        if not intf1:
            print(f"❌ Link {s1_name}-{s2_name} not found")
            continue

        for intf in [intf1, intf2]:
            node = intf.node
            dev = intf.name

            node.cmd(f'tc qdisc del dev {dev} root 2>/dev/null')

            netem = ""
            if params.get("delay"):
                netem += f" delay {params['delay']}"
            if params.get("loss") is not None:
                netem += f" loss {params['loss']}%"

            if params.get("bw"):
                node.cmd(f'tc qdisc add dev {dev} root handle 1: tbf '
                         f'rate {params["bw"]}mbit burst 15k latency 50ms')
                if netem:
                    node.cmd(f'tc qdisc add dev {dev} parent 1:1 '
                             f'handle 10: netem{netem}')
            elif netem:
                node.cmd(f'tc qdisc add dev {dev} root netem{netem}')

        print(f"✅ Weak link applied: {s1_name}-{s2_name} | {params}")

if __name__ == '__main__':

    algorithm_name = sys.argv[1] if len(sys.argv) > 1 else "dijkstra"
    run(algorithm_name=algorithm_name)