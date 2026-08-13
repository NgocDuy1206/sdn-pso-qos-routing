
import time
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from functools import partial
from mininet.cli import CLI
from mininet.link import TCLink
from udp_tools.scenario_runner import run_all_scenarios  # BẮT BUỘC có thư viện này để giả lập thông số

class FatTreeTopo(Topo):
    def build(self):
        # ===== Core switches =====
        c1 = self.addSwitch('s1', dpid='1') # Core 1 - Đường tệ
        c2 = self.addSwitch('s2', dpid='2') # Core 2 - Đường tốt

        # ===== Aggregation switches =====
        a1 = self.addSwitch('s3', dpid='3')
        a2 = self.addSwitch('s4', dpid='4')

        # ===== Edge (Leaf) switches =====
        e1 = self.addSwitch('s5', dpid='5')
        e2 = self.addSwitch('s6', dpid='6')
        e3 = self.addSwitch('s7', dpid='7')
        e4 = self.addSwitch('s8', dpid='8')

        # ===== Hosts =====
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        h3 = self.addHost('h3')
        h4 = self.addHost('h4')

        # ===== Host to Edge (Cấu hình mặc định tốt) =====
        self.addLink(h1, e1, cls=TCLink, bw=10)
        self.addLink(h2, e2, cls=TCLink, bw=10)
        self.addLink(h3, e3, cls=TCLink, bw=10)
        self.addLink(h4, e4, cls=TCLink, bw=10)

        # ===== Edge to Aggregation =====
        self.addLink(e1, a1, cls=TCLink, bw=10)
        self.addLink(e2, a1, cls=TCLink, bw=10)
        self.addLink(e3, a2, cls=TCLink, bw=10)
        self.addLink(e4, a2, cls=TCLink, bw=10)

        # ===== Aggregation to Core (ĐÂY LÀ NƠI TẠO SỰ KHÁC BIỆT) =====
        
        # Nhánh qua Core 1 (s1): Giả lập nghẽn, trễ cao, mất gói
        # Dijkstra rất dễ chọn đường này vì số hop bằng với Core 2
        self.addLink(a1, c1, cls=TCLink, bw=10, delay='0ms', loss=0) 
        self.addLink(a2, c1, cls=TCLink, bw=10, delay='0ms', loss=0)

        # Nhánh qua Core 2 (s2): Giả lập đường truyền lý tưởng
        # PSO phải tìm ra đường này để đạt Fitness cao nhất
        self.addLink(a1, c2, cls=TCLink, bw=10, delay='0ms', loss=0)
        self.addLink(a2, c2, cls=TCLink , bw=10, delay='0ms', loss=0)

        self.addLink(c1, c2, cls=TCLink, bw=10, delay= '0ms', loss=0)  # Liên kết giữa 2 core switch
def run_udp_test(net):
    
    time.sleep(1)
    h1, h2 = net.get('h1', 'h2')
    h3, h4 = net.get('h3', 'h4')

    # start receivers
    print("Starting UDP receivers...")
    r1 = h3.popen("python3 udp_receiver_full.py 5001 data/pso_f1.csv")
    r2 = h4.popen("python3 udp_receiver_full.py 5002 data/pso_f2.csv")

    time.sleep(2)

    # start flow 1
    p1 = h1.popen("python3 udp_sender.py 10.0.0.3 5001")

    time.sleep(1)  # overlap thật

    # start flow 2
    p2 = h2.popen("python3 udp_sender.py 10.0.0.4 5002")

    # đợi sender xong
    p1.wait()
    p2.wait()

    time.sleep(3)  # cho receiver flush dữ liệu

    # 🔥 kill receiver (QUAN TRỌNG)
    
    # h3.cmd("pkill -f udp_receiver_full.py")
    # h4.cmd("pkill -f udp_receiver_full.py")

    print("=== Done & Cleaned ===")
def run_congestion_test(net):

    # net.pingAll()
    time.sleep(2)
    h1, h2 = net.get('h1', 'h2')
    h3, h4 = net.get('h3', 'h4')

    # start server
    h3.cmd("iperf3 -s -p 5001 -J > f1.json 2>&1 &")
    h4.cmd("iperf3 -s -p 5002 -J > f2.json 2>&1 &")

    time.sleep(2)

    # start flows
    p1 = h1.popen("iperf3 -c 10.0.0.3 -p 5001 -u -b 10M -t 10 -i 1 -J")
    time.sleep(1)
    p2 = h2.popen("iperf3 -c 10.0.0.4 -p 5002 -u -b 10M -t 10 -i 1 -J")

    p1.wait()
    p2.wait()

    print("=== Done ===")
def run_network():
    topo = FatTreeTopo()
    switch = partial(OVSSwitch, protocols='OpenFlow13')

    # Lưu ý: Thêm link=TCLink vào khởi tạo Mininet
    net = Mininet(
        topo=topo,
        controller=lambda name: RemoteController(name, ip='127.0.0.1'),
        switch=switch,
        link=TCLink
    )

    net.start()
    # run_all_scenarios(net)
    CLI(net)
    net.stop()

if __name__ == '__main__':
    run_network()

