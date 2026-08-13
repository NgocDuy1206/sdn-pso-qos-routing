from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from functools import partial
from mininet.cli import CLI

class LeafSpineTopo(Topo):
    def build(self):
        # ===== Spine switches =====
        s1 = self.addSwitch('s1', dpid='1')
        s2 = self.addSwitch('s2', dpid='2')

        # ===== Leaf switches =====
        l1 = self.addSwitch('s3', dpid='3')
        l2 = self.addSwitch('s4', dpid='4')

        # ===== Hosts =====
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')

        # ===== Host to Leaf =====
        self.addLink(h1, l1)
        self.addLink(h2, l2)

        # ===== Leaf to Spine (full-mesh) =====
        self.addLink(l1, s1)
        self.addLink(l1, s2)

        self.addLink(l2, s1)
        self.addLink(l2, s2)


def run_network():
    topo = LeafSpineTopo()

    # OpenFlow 1.3
    switch = partial(OVSSwitch, protocols='OpenFlow13')

    net = Mininet(
        topo=topo,
        controller=lambda name: RemoteController(name, ip='127.0.0.1'),
        switch=switch
    )

    net.start()
    CLI(net)
    net.stop()


if __name__ == '__main__':
    run_network()
