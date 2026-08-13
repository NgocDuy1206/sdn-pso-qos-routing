import time
import struct
from ryu.lib.packet import packet, lldp
from ryu.controller import ofp_event
from metric_base import BaseMetric

MAGIC = b'PSO1'

class DelayMetric(BaseMetric):

    def handle_event(self, ev):

        if not isinstance(ev, ofp_event.EventOFPPacketIn):
            return

        msg = ev.msg
        pkt = packet.Packet(msg.data)
        lldp_pkt = pkt.get_protocol(lldp.lldp)

        if not lldp_pkt:
            return

        try:
            src_dpid = int(lldp_pkt.tlvs[0].chassis_id)
        except Exception:
            return
        raw = msg.data

        idx = raw.rfind(MAGIC)
        if idx == -1:
            return

        send_time = struct.unpack('!d', raw[idx+4:idx+12])[0]

        recv_time = time.monotonic()
        delay = (recv_time - send_time) * 1000  # ms


        dst_dpid = msg.datapath.id
        src_port = int(lldp_pkt.tlvs[1].port_id)

        if self.graph.has_edge(src_dpid, dst_dpid):
            self.graph[src_dpid][dst_dpid]['delay'] = delay
        else:
            self.graph.add_edge(
                src_dpid,
                dst_dpid,
                port=src_port,
                delay=delay
            )
