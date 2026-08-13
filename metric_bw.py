import time
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER

from metric_base import BaseMetric

class BandwidthMetric(BaseMetric):

    def __init__(self, app, graph, capacity_config):
        super().__init__(app, graph)
        self.capacity_config = capacity_config  # Dict với default_capacity_mbps và links
        self.default_capacity = capacity_config.get("default_capacity_mbps", 10)
        self.links_capacity = capacity_config.get("links", {})
        self.port_stats = {}
        self.datapaths = {}

    def register_datapath(self, dp):
        self.datapaths[dp.id] = dp

    def start(self):
        self.app.logger.info("BandwidthMetric started")
    
    def get_link_capacity(self, src_dpid, dst_dpid):
        """Get capacity for a specific link from config, return default if not found"""
        src_key = str(src_dpid)
        dst_key = str(dst_dpid)
        
        if src_key in self.links_capacity:
            if dst_key in self.links_capacity[src_key]:
                return self.links_capacity[src_key][dst_key]
        
        return self.default_capacity

    def handle_event(self, ev):
  
        if not isinstance(ev, ofp_event.EventOFPPortStatsReply):
            return
        dpid = ev.msg.datapath.id
        now = time.time()
    
        for stat in ev.msg.body:
            key = (dpid, stat.port_no)

            if key in self.port_stats:
               
                prev = self.port_stats[key]
                delta_bytes = stat.tx_bytes - prev['tx']
                delta_time = now - prev['time']

                if delta_time > 0.1: # Minimal delta time to avoid noise with 0.3s monitor interval
                    bw = (delta_bytes * 8) / delta_time
                    dst_dpid = None
                    capacity = self.default_capacity
                    try:
                        for neigh, attr in self.graph[dpid].items():
                                if attr.get('port') == stat.port_no:
                                    dst_dpid = neigh
                                    # Lấy capacity từ config dựa trên link cụ thể
                                    capacity = self.get_link_capacity(dpid, dst_dpid)
                                    break
                    except Exception as e:
                        self.app.logger.error("Error occurred while updating graph: %s", e)
                        return
                 
                    capacity = capacity * 1_000_000  # Convert to bps
                    avail_bw = max(capacity - bw, 0)
                    avail_bw = avail_bw / 1_000_000  # Convert to Mbps
                    self._update_graph(dpid, stat.port_no, avail_bw)

            self.port_stats[key] = {
                'tx': stat.tx_bytes,
                'time': now
            }

    def _update_graph(self, dpid, port_no, avail_bw):
        if dpid not in self.graph:
            return
        for neigh, attr in self.graph[dpid].items():
            if attr.get('port') == port_no:
                attr['avail_bw'] = avail_bw