from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from functools import partial
from mininet.cli import CLI

class MyLinearTopo(Topo):
    def build(self):
        # Tạo 3 Switches
        s1 = self.addSwitch('s1', dpid='1')
        s2 = self.addSwitch('s2', dpid='2')
        s3 = self.addSwitch('s3', dpid='3')
        s4 = self.addSwitch('s4', dpid='4')

        # Tạo 3 Hosts
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')

        # Kết nối Host vào Switch
        self.addLink(h1, s1)
        self.addLink(h2, s4)

        # Kết nối các Switch với nhau
        self.addLink(s1, s2)
        self.addLink(s2, s4)
        self.addLink(s1, s3)
        self.addLink(s3, s4)
def run_network():
    topo = MyLinearTopo()
    
    # Cấu hình Switch để sử dụng OpenFlow 1.3
    switch = partial(OVSSwitch, protocols='OpenFlow13')
    
    # Khởi tạo mạng
    net = Mininet(topo=topo, 
                  controller=lambda name: RemoteController(name, ip='127.0.0.1'),
                  switch=switch) # Truyền biến switch đã cấu hình ở trên vào
    
    net.start()
    CLI(net)
    net.stop()
if __name__ == '__main__':
    run_network()