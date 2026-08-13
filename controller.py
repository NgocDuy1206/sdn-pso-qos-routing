import eventlet
eventlet.monkey_patch()


from PSO_advance import HybridKSP_PSO
from ryu import cfg

CONF = cfg.CONF

MAGIC = b'PSO1'



from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, arp, ether_types, lldp, ipv4, udp, tcp
from ryu.topology import event
from ryu.topology.api import get_link
from ryu.lib import hub
import networkx as nx
import struct
import time
import csv
import os
import json

from manager_metric import MetricManager
from metric_bw import BandwidthMetric
from metric_delay import DelayMetric
from metric_packet_loss import PacketLossMetric
from PSO_algorithm import PSOAlgorithm


class MyController(app_manager.RyuApp):
    

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(MyController, self).__init__(*args, **kwargs)

        self.algo = CONF.user_flags if CONF.user_flags else "dijkstra"
        # ===== NETWORK STATE =====
        self.network_graph = nx.DiGraph()
        self.datapaths = {}
        self.hosts_loc = {}       # mac -> (dpid, port)
        self.arp_table = {}       # ip -> mac

        self.swarms_cache = {}  # Cache kết quả PSO cho các cặp host để tái sử dụng
        self.flows = {}
        self.computing_locks = {}  # Track locks for flows being computed
        # self.visualizer = GraphVisualizer(self)
        
        # ===== LOAD LINK CAPACITY CONFIG =====
        self.capacity = self._load_link_capacity_config()
        

        # ===== CSV LOGGING =====
        self.log_csv_file = "controller_log.csv"
        self._init_csv_log()
        self._port_down_set = set()
        
        # ===== CSV LOGGING FOR COMPUTATION TIME =====
        self.computation_time_csv_files = {
            "dijkstra": "dijkstra_computation_time.csv",
            "pso": "pso_computation_time.csv",
            "hybrid": "hybrid_computation_time.csv"
        }
        self._init_computation_time_csvs()
        
        # ===== METRIC MANAGER =====
        self.metric_manager = MetricManager(self, self.network_graph)
        self.metric_manager.add_metric(
            BandwidthMetric(self, self.network_graph, self.capacity)
        )
        self.metric_manager.add_metric(
            DelayMetric(self, self.network_graph)
        )
        self.metric_manager.add_metric(
            PacketLossMetric(self, self.network_graph)
        )
        
       # Để theo dõi các đường đi đang được tính toán
        self.lldp_thread = hub.spawn(self._lldp_loop)
        self.monitor_thread = hub.spawn(self._monitor)
      
        
        # self.pso_thread = hub.spawn(self._pso_monitoring_loop)
        self.logger.info("Controller initialized with Metric Framework")
        self.logger.info("PSO auto-monitoring loop ENABLED")

    def _init_csv_log(self):
       
        with open(self.log_csv_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "src_mac", "dst_mac", "src_ip", "dst_ip", "path"])
        self.logger.info("Created new CSV log file: %s", self.log_csv_file)
    
    def _init_computation_time_csvs(self):
        
        for algo, filename in self.computation_time_csv_files.items():
            # Chỉ tạo file và header nếu file chưa tồn tại
            if not os.path.exists(filename):
                with open(filename, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["timestamp", "src_dpid", "dst_dpid", "computation_time_ms"])
                self.logger.info("Created new computation time CSV log file for %s: %s", algo, filename)
            else:
                self.logger.info("Appending to existing computation time CSV log file for %s: %s", algo, filename)

    def _load_link_capacity_config(self):
        
        config_file = "link_capacity_config.json"
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
            self.logger.info("Loaded link capacity config from %s", config_file)
            self.logger.info("Default capacity: %s Mbps", config.get("default_capacity_mbps", 10))
            return config
        except FileNotFoundError:
            self.logger.warning("link_capacity_config.json not found, using default capacity 10 Mbps")
            return {
                "default_capacity_mbps": 10,
                "links": {}
            }
        except json.JSONDecodeError as e:
            self.logger.error("Failed to parse link_capacity_config.json: %s", e)
            return {
                "default_capacity_mbps": 10,
                "links": {}
            }

    def _update_link_capacity(self, node1, node2, capacity_mbps):
        
        if "links" not in self.capacity:
            self.capacity["links"] = {}
        
        link_key_1 = f"{node1}-{node2}"
        link_key_2 = f"{node2}-{node1}"
        
        self.capacity["links"][link_key_1] = {"capacity_mbps": capacity_mbps}
        self.capacity["links"][link_key_2] = {"capacity_mbps": capacity_mbps}
        
        self.logger.info("Updated capacity: %s <-> %s = %s Mbps", node1, node2, capacity_mbps)

    def _log_flow_to_csv(self, timestamp, src_mac, dst_mac, src_ip, dst_ip, path):
        
        try:
            path_str = "->".join(str(s) for s in path)
            with open(self.log_csv_file, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, src_mac, dst_mac, src_ip, dst_ip, path_str])
        except Exception as e:
            self.logger.error("Failed to write to CSV log: %s", e)    

    def _log_computation_time_to_csv(self, timestamp, algorithm, src_dpid, dst_dpid, computation_time_ms):
        
        try:
            filename = self.computation_time_csv_files.get(algorithm)
            if filename:
                with open(filename, "a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([timestamp, src_dpid, dst_dpid, computation_time_ms])
            else:
                self.logger.warning("Unknown algorithm: %s", algorithm)
        except Exception as e:
            self.logger.error("Failed to write computation time to CSV log: %s", e)
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        self.datapaths[datapath.id] = datapath

        # register datapath cho metric
        self.metric_manager.register_datapath(datapath)

        parser = datapath.ofproto_parser

        # table-miss
        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(
                datapath.ofproto.OFPP_CONTROLLER,
                datapath.ofproto.OFPCML_NO_BUFFER
            )
        ]
        self.add_flow(datapath, 0, match, actions)

        self.logger.info(
            "Switch S%s connected",
            datapath.id
        )


    def add_flow(self, datapath, priority, match, actions, idle=0, hard=0):
        """Optimized flow installation with better error handling"""
        try:
            inst = [
                datapath.ofproto_parser.OFPInstructionActions(
                    datapath.ofproto.OFPIT_APPLY_ACTIONS,
                    actions
                )
            ]
            mod = datapath.ofproto_parser.OFPFlowMod(
                datapath=datapath,
                priority=priority,
                idle_timeout=idle,
                hard_timeout=hard,
                match=match,
                instructions=inst,
                flags=datapath.ofproto.OFPFF_SEND_FLOW_REM
            )
            datapath.send_msg(mod)
        except Exception as e:
            self.logger.error("Failed to install flow on S%s: %s", datapath.id, e)

    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def port_status_handler(self, ev):
        msg = ev.msg
        reason = msg.reason
        port = msg.desc
        dpid = msg.datapath.id
        ofproto = msg.datapath.ofproto

        is_port_down = (port.config & ofproto.OFPPC_PORT_DOWN) or \
                    (port.state & ofproto.OFPPS_LINK_DOWN)

        reason_str = 'ADD' if reason == ofproto.OFPPR_ADD \
                else 'DELETE' if reason == ofproto.OFPPR_DELETE \
                else 'MODIFY'
        state_str = 'DOWN' if is_port_down else 'UP'

        self.logger.info("PORT_STATUS: Switch S%s, Port %s, Reason: %s, State: %s",
                        dpid, port.port_no, reason_str, state_str)

        key = (dpid, port.port_no)

        # ✅ Ignore spurious DELETE + UP
        if reason == ofproto.OFPPR_DELETE and not is_port_down:
            self.logger.info("⏭️  Ignoring spurious DELETE (port UP): S%s port %s",
                            dpid, port.port_no)
            return

        # ✅ PORT DOWN: chỉ xử lý 1 lần dù nhận nhiều event
        if is_port_down:
            if key in self._port_down_set:
                self.logger.info("⏭️  Already handled failure for S%s port %s, skipping",
                                dpid, port.port_no)
                return
            self._port_down_set.add(key)
            self.logger.warning("⚠️  PORT FAILED: Switch S%s, Port %s is DOWN",
                                dpid, port.port_no)
            self._handle_port_failure(dpid, port.port_no)

        # ✅ PORT UP: chỉ xử lý nếu trước đó đã DOWN
        elif reason == ofproto.OFPPR_MODIFY and not is_port_down:
            if key not in self._port_down_set:
                self.logger.info("⏭️  Ignoring MODIFY UP (port was not down): S%s port %s",
                                dpid, port.port_no)
                return
            self._port_down_set.discard(key)
            self.logger.info("❇️  PORT RECOVERED: Switch S%s, Port %s is UP",
                            dpid, port.port_no)
            self._handle_port_recovery(dpid, port.port_no)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats_reply_handler(self, ev):
        self.metric_manager.handle_event(ev)

    def _monitor(self):
        """Monitor port statistics from all connected switches (High-resolution: 0.3s)"""
        while True:
            if not self.datapaths:
                hub.sleep(0.3) # Adjusted for stability and less noise
                continue
                
            for dp in list(self.datapaths.values()):
                try:
                    parser = dp.ofproto_parser
                    req = parser.OFPPortStatsRequest(dp, 0, dp.ofproto.OFPP_ANY)
                    dp.send_msg(req)
                except Exception as e:
                    self.logger.error("Failed to request port stats from S%s: %s", dp.id, e)
            
            hub.sleep(0.3) # Adjusted for stability and less noise
    def print_arp_table(self):
        self.logger.info("===== ARP TABLE =====")
        if not self.arp_table:
            self.logger.info("ARP table is empty")
            return

        for ip, mac in self.arp_table.items():
            self.logger.info("IP: %s  ->  MAC: %s", ip, mac)

        self.logger.info("=====================")

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        dpid = datapath.id
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        
        if not eth:
            return

        # LLDP
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            self.metric_manager.handle_event(ev)
            return

        # Skip IPv6 multicast and other non-IPv4 traffic
        if eth.ethertype == ether_types.ETH_TYPE_IPV6:
            return
        if eth.dst[:5] == '33:33':  # IPv6 multicast
            return
        if eth.dst == 'ff:ff:ff:ff:ff:ff' and eth.ethertype == 0x86dd:  # IPv6 broadcast
            return

        src = eth.src
        dst = eth.dst
        

        # hoc hosting
        if dpid not in self.network_graph:
            self.network_graph.add_node(dpid)

        is_switch_link = any(
            attr.get('port') == in_port
            for _, attr in self.network_graph[dpid].items()
        )

        if not is_switch_link:
            if src not in self.hosts_loc:
                self.hosts_loc[src] = (dpid, in_port)
                self.logger.info(
                    "Learn host %s at S%s port %s",
                    src, dpid, in_port
                )
        
        # Handle ARP
        arp_pkt = pkt.get_protocol(arp.arp)
        if arp_pkt:
            self.arp_table[arp_pkt.src_ip] = src
            if arp_pkt.opcode == arp.ARP_REQUEST:
                if arp_pkt.dst_ip in self.arp_table:
                    # Send ARP reply if we know the destination MAC
                    self._send_arp_reply(
                        datapath,
                        self.arp_table[arp_pkt.dst_ip],
                        src,
                        arp_pkt.dst_ip,
                        arp_pkt.src_ip,
                        datapath.ofproto.OFPP_CONTROLLER,  # nhận ARP request từ controller
                        in_port
                    )
                    # self.logger.info("reply arp request for %s at S%s with known MAC %s", arp_pkt.dst_ip, dpid, self.arp_table[arp_pkt.dst_ip])
                else:
                    # Flood ARP request to find destination
                    # self.logger.info("ARP request for unknown IP %s, flooding", arp_pkt.dst_ip)
                    self._execute_flood(msg)
                return
            elif arp_pkt.opcode == arp.ARP_REPLY:
                # Flood ARP replies
                # self._execute_flood(msg)
                if dst in self.hosts_loc:
                    self._send_arp_reply(
                        self.datapaths[self.hosts_loc[dst][0]],  # datapath của switch nơi host đích đang ở
                        src,  # MAC nguồn là MAC của host gửi ARP reply
                        dst,  # MAC đích là MAC của host nhận ARP reply
                        arp_pkt.src_ip,  # IP nguồn là IP của host gửi ARP reply
                        arp_pkt.dst_ip,  # IP đích là IP của host nhận ARP reply
                        datapath.ofproto.OFPP_CONTROLLER,  # Port nhận ARP reply
                        self.hosts_loc[dst][1]  # Port gửi ARP reply (port
                    )
                else:
                    self.logger.info("eos hieu sao ko co luon")
            return
                            
        
        # ROUTING (PSO)

        target_dpid, final_port = self.hosts_loc[dst]
        pk = pkt.get_protocol(ipv4.ipv4)

        if not pk:
            self.logger.info("Non-IPv4 packet from %s to %s, flooding", src, dst)
            self._execute_flood(msg)
            return  
        # self._log_nav_graph()  # Log graph before path computation
        flow_key = (src, dst)
        if flow_key in self.flows:
            # self.logger.info("Flow %s -> %s already has a path, skipping PSO", src, dst)
            return
        
        # ===== LOCK-BASED SYNCHRONIZATION =====
        # If another packet is already computing path for this flow, wait for it
        if flow_key not in self.computing_locks:
            self.computing_locks[flow_key] = hub.Event()
        
        lock = self.computing_locks[flow_key]
        if lock.is_set():
           
            return
        
        # Mark this flow as being computed
        lock.clear()
        try:
            # Tìm đường ban đầu bằng BFS trước (dự phòng)
            
            # Nếu BFS không tìm được đường, thử PSO
            self.logger.info("Computing path from S%s to S%s", dpid, target_dpid)
            self._log_nav_graph()  # Log graph state before path computation
            start_time = time.perf_counter()
            if (self.algo == 'dijkstra'):
                path = nx.shortest_path(
                    self.network_graph, source=dpid, target=target_dpid, weight=None
                )
            else:
                if (self.algo == 'pso'):
                    pso = PSOAlgorithm(
                        self.network_graph,
                        dpid,
                        target_dpid,
                        self.logger,
                        fitness_func=self.calculate_fitness,
                        particles=None
                    )
                else:
                    pso = HybridKSP_PSO(
                        self.network_graph,
                        dpid,
                        target_dpid,
                        self.logger,
                        fitness_func=self.calculate_fitness,
                        particles=None
                    )
                path, swarm = pso.run()
                self.swarms_cache[(src, dst)] = {
                    'particles': swarm,
                    'gbest_path': path,
                    'last_fitness': self.calculate_fitness(path)
                }
            computed_time = (time.perf_counter() - start_time) * 1000
            self.logger.info("Path computed in %.3f ms: %s", computed_time, path)
            # Log computation time to CSV
            self._log_computation_time_to_csv(time.time(), self.algo, dpid, target_dpid, computed_time)
            if not path or len(path) < 1:
                self.logger.error("No path found from S%s to S%s", dpid, target_dpid)
                self._execute_flood(msg)
                return
            
            if (src, dst) in self.flows and self.flows[(src, dst)] == path:
                self.logger.info("Path for %s -> %s unchanged, no need to reinstall flows", src, dst)
                return  
            else:
                self.flows[(src, dst)] = path  # Cập nhật cache đường đi
                path_str = "->".join(str(s) for s in path)
                timestamp = time.time()
                self.logger.info("FLOW_COMPUTED: MAC_SRC=%s MAC_DST=%s IP_SRC=%s IP_DST=%s PATH=%s", 
                                src, dst, pk.src, pk.dst, path_str)
                self._log_flow_to_csv(timestamp, src, dst, pk.src, pk.dst, path)
                # self._log_nav_graph()
            # Cài đặt flow rule cho toàn bộ đường đi
            self.install_path_flows(src, dst, path)
           

            if dpid == target_dpid:
                out_port = final_port
            else:
                next_hop = path[path.index(dpid) + 1]
                out_port = self.network_graph[dpid][next_hop]['port']

            self._send_packet_out(datapath, in_port, out_port, msg.data, msg.buffer_id)
         


        except Exception as e:
            self.logger.error("Routing error: %s", e)
            # Khi có lỗi, flood packet để đảm bảo connectivity
            self._execute_flood(msg)
        
        finally:
            # Mark path computation as complete so waiting packets can proceed
            if flow_key in self.computing_locks:
                self.computing_locks[flow_key].set()

    

    def _handle_port_failure(self, dpid, port_no):
        self.logger.warning("🔥 PORT FAILURE: S%s port %s", dpid, port_no)
        edges_to_remove = []

        for src, dst, attr in list(self.network_graph.edges(data=True)):
            # ✅ Xóa edge khi dpid là source và dùng port_no
            if src == dpid and attr.get("port") == port_no:
                edges_to_remove.append((src, dst))
            # ✅ Xóa edge khi dpid là destination và dùng port_no  
            elif dst == dpid and attr.get("dst_port") == port_no:
                edges_to_remove.append((src, dst))

        for src, dst in set(edges_to_remove):
            if self.network_graph.has_edge(src, dst):
                self.network_graph.remove_edge(src, dst)
                self.logger.info("❌ Link removed: S%s <-> S%s", src, dst)

        self.logger.info("✅ Topology updated correctly")
        
        # ✅ Clear flows và cache nhưng cẩn thận với computing_locks
        self.flows.clear()
        self.swarms_cache.clear()
        # Bỏ clear computing_locks - để cho in-progress packets hoàn thành gracefully
        
        dp = self.datapaths.get(dpid)
        if dp:
            self.clear_flows(dp, port_no)
            
    def _handle_port_recovery(self, dpid, port_no):
        self.logger.info("🔄 Triggering topology rediscovery for S%s port %s...", dpid, port_no)
        # ✅ Chỉ clear flows/cache, để LLDP rediscover topology tự động
        # Không clear computing_locks để tránh race condition
        self.flows.clear()
        self.swarms_cache.clear()
            
    def clear_flows(self, datapath, port_no):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        mod = parser.OFPFlowMod(
            datapath=datapath,
            command=ofproto.OFPFC_DELETE,
            out_port=port_no,   
            out_group=ofproto.OFPG_ANY,
            match=parser.OFPMatch(),  # match all
        )
        datapath.send_msg(mod)
    def _execute_flood(self, msg):
        parser = msg.datapath.ofproto_parser
        actions = [
            parser.OFPActionOutput(
                msg.datapath.ofproto.OFPP_FLOOD
            )
        ]
        
        out = parser.OFPPacketOut(
            datapath=msg.datapath,
            buffer_id=msg.datapath.ofproto.OFP_NO_BUFFER,
            in_port=msg.match['in_port'],
            actions=actions,
            data=msg.data
        )
        msg.datapath.send_msg(out)

    def _send_arp_reply(self, datapath, 
                        target_mac,      # MAC của IP đích (người được proxy)
                        requester_mac,   # MAC của người gửi ARP request
                        target_ip,       # IP đích
                        requester_ip,    # IP của người hỏi
                        in_port,         # Port nhận ARP request
                        out_port):       # Port gửi ra (thường là in_port của request)
        
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Tạo Ethernet header
        eth = ethernet.ethernet(
            dst=requester_mac,          # gửi về người hỏi
            src=target_mac,             # nguồn là MAC của target (hoặc MAC của switch nếu muốn)
            ethertype=ether_types.ETH_TYPE_ARP
        )

        # Tạo ARP Reply packet
        arp_reply = arp.arp(
            hwtype=1,                   # Ethernet
            proto=ether_types.ETH_TYPE_IP,    # IPv4
            hlen=6,                     # MAC length
            plen=4,                     # IP length
            opcode=arp.ARP_REPLY,
            src_mac=target_mac,         # Sender MAC = target MAC
            src_ip=target_ip,           # Sender IP  = target IP
            dst_mac=requester_mac,      # Target MAC  = requester MAC
            dst_ip=requester_ip         # Target IP   = requester IP
        )

        # Đóng gói packet
        pkt = packet.Packet()
        pkt.add_protocol(eth)
        pkt.add_protocol(arp_reply)
        pkt.serialize()

        # Gửi Packet-Out
        self._send_packet_out(datapath,in_port, out_port, pkt.data, datapath.ofproto.OFP_NO_BUFFER)

    def send_lldp_probe(self, datapath, out_port):
        dpid = datapath.id
        send_time = time.monotonic()

        chassis = lldp.ChassisID(
            subtype=lldp.ChassisID.SUB_LOCALLY_ASSIGNED,
            chassis_id=str(dpid).encode()
        )

        port = lldp.PortID(
            subtype=lldp.PortID.SUB_PORT_COMPONENT,
            port_id=str(out_port).encode()
        )

        ttl = lldp.TTL(ttl=10)
        end = lldp.End()

        lldp_pkt = lldp.lldp([chassis, port, ttl, end])

        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(
            ethertype=ether_types.ETH_TYPE_LLDP,
            src='00:00:00:00:00:01',
            dst=lldp.LLDP_MAC_NEAREST_BRIDGE
        ))
        pkt.add_protocol(lldp_pkt)

        # MAGIC + timestamp
        pkt.add_protocol(MAGIC + struct.pack('!d', send_time))

        pkt.serialize()

        actions = [
            datapath.ofproto_parser.OFPActionOutput(out_port)
        ]

        out = datapath.ofproto_parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=datapath.ofproto.OFP_NO_BUFFER,
            in_port=datapath.ofproto.OFPP_CONTROLLER,
            actions=actions,
            data=pkt.data
        )

        datapath.send_msg(out)

    def _send_packet_out(self, datapath, in_port, out_port, data, buffer_id):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        actions = [parser.OFPActionOutput(out_port)]

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=buffer_id,
            in_port=in_port,
            actions=actions,
            data=data if buffer_id == ofproto.OFP_NO_BUFFER else None
        )

        datapath.send_msg(out)

    def _lldp_loop(self):
        
        while True:
            for dp in self.datapaths.values():
                for port_no in dp.ports:
                    if port_no > 0:  # bỏ OFPP_LOCAL
                        self.send_lldp_probe(dp, port_no)
            hub.sleep(0.5)

    def _log_nav_graph(self):
        
        for u, v, attr in self.network_graph.edges(data=True):
            self.logger.info("EDGE %s -> %s | attr=%s", u, v, attr)


    def install_path_flows(self, src_mac, dst_mac, path):
        
        if len(path) < 1:
            self.logger.info("Path too short to install flows: %s\n", path)
            return
        for i in range(len(path)):
            curr_dpid = path[i]
            if (i < len(path) - 1):
                next_dpid = path[i + 1]
            else:
                next_dpid = curr_dpid
            
            if curr_dpid not in self.datapaths:
                self.logger.info("[BFS] Switch %s not connected", curr_dpid)
                continue

            datapath = self.datapaths[curr_dpid]
            try:
                if (i == len(path) - 1 and curr_dpid == self.hosts_loc[dst_mac][0]):
                    # Last switch → output to host
                    out_port = self.hosts_loc[dst_mac][1]
                else:
                    out_port = self.network_graph[curr_dpid][next_dpid]['port']
            except KeyError:
                self.logger.error("[BFS] No link %s -> %s in graph", curr_dpid, next_dpid)
                continue

            # Install MAC-based flow rule with medium priority
            match = datapath.ofproto_parser.OFPMatch(eth_src=src_mac, eth_dst=dst_mac)
            actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
            inst = [datapath.ofproto_parser.OFPInstructionActions(
                datapath.ofproto.OFPIT_APPLY_ACTIONS, actions
            )]
            
            mod = datapath.ofproto_parser.OFPFlowMod(
                datapath=datapath, priority=10, match=match, instructions=inst,
                idle_timeout=0, hard_timeout=0
            )
            datapath.send_msg(mod)
            # self.logger.info("[BFS] S%s: Install flow rule for %s -> %s, output -> port %s (next S%s)",
            #                curr_dpid, src_mac, dst_mac, out_port, next_dpid)
        self.logger.info("=== done install path ===")

    def _pso_monitoring_loop(self):
        count = 0
        while True:
            hub.sleep(1) # Increased frequency for high-res scenarios
            self.logger.info("--- Kiểm tra sức khỏe toàn mạng (1s/lần) ---")
            # self._log_nav_graph()  # Log graph để debug
            for (mac_src, mac_dst), swarm_data in self.swarms_cache.items():
                # 1. Lấy đường đi tốt nhất hiện tại (gBest)
                current_gbest_path = swarm_data['gbest_path']
                
                # 2. Tính lại fitness thực tế dựa trên thông số mạng mới nhất
                # (Giả sử bạn đã cập nhật NetworkX trước đó)
                actual_fitness = self.calculate_fitness(current_gbest_path)
                
                # 3. So sánh với fitness cũ đã lưu trong cache
                old_fitness = swarm_data['last_fitness']
                
                # Ngưỡng: Nếu tệ hơn 10% hoặc bị đứt (inf)
                if actual_fitness > old_fitness * 1.1 or count >= 10 or actual_fitness == float('inf'):
                    if (actual_fitness > old_fitness * 1.1):
                        self.logger.warning(
                            "Đường đi %s có fitness tệ hơn 10%% (%.2f > %.2f), chạy lại PSO",
                            current_gbest_path, actual_fitness, old_fitness
                        )
                    elif actual_fitness == float('inf'):
                        self.logger.warning(
                            "Đường đi %s -> %s bị đứt (fitness=inf), chạy lại PSO",
                            mac_src, mac_dst
                        )
                    else:
                        self.logger.info(
                            "Đã 50s, kiểm tra lại đường đi %s -> %s dù fitness chưa tệ hơn 10%%",
                            mac_src, mac_dst
                        )
                    
                    # Gọi PSO tinh chỉnh với các hạt cũ
                    if (self.algo == 'pso'):
                        pso = PSOAlgorithm(
                            self.network_graph,
                            self.hosts_loc[mac_src][0],
                            self.hosts_loc[mac_dst][0],
                            self.logger,
                            fitness_func=self.calculate_fitness,
                            particles=None
                        )
                    else:
                        pso = HybridKSP_PSO(
                            self.network_graph,
                            self.hosts_loc[mac_src][0],
                            self.hosts_loc[mac_dst][0],
                            self.logger,
                            fitness_func=self.calculate_fitness,
                            particles=None
                        )
                    path, swarm = pso.run()
                    self.swarms_cache[(mac_src, mac_dst)] = {
                        'particles': swarm,
                        'gbest_path': path,
                        'last_fitness': self.calculate_fitness(path)
                    }
                  

                    # Cập nhật cache
              
                    self.logger.info("new path : %s, fitness: %.2f", path, self.swarms_cache[(mac_src, mac_dst)]['last_fitness'])
                    if path != current_gbest_path:
                        # Cài đặt lại Flow Table nếu đường đi thay đổi
                        self._log_flow_to_csv(time.time(), mac_src, mac_dst, self.hosts_loc[mac_src][0], self.hosts_loc[mac_dst][0], path)
                        self.install_path_flows(src_mac=mac_src, dst_mac=mac_dst, path=path)
                else:
                    # Nếu vẫn ổn, chỉ cập nhật lại giá trị fitness hiện tại vào cache
                    swarm_data['last_fitness'] = actual_fitness
            count += 1
            if count > 10:
                count = 0
                

    def calculate_fitness(self, path):
        if not path or len(path) < 2:
            return float('inf')

        # --- ĐỊNH NGHĨA GIỚI HẠN  ---
        MAX_DELAY = 200       # Giây
        MAX_LOSS = 100.0       # %
        MAX_BW_INV = 10.0      # 1/1Mbps
        MAX_HOPS = 20         # 


        ALPHA = 0.4 # Delay
        BETA  = 0.15  # Loss
        GAMMA = 0.4  # Bandwidth
        DELTA = 0.05  # Hop Count (Ưu tiên đường ngắn về mặt vật lý)

        total_delay = 0
        total_loss = 0
        min_bw = float('inf')
        hop_count = len(path) - 1 # Số cạnh nối giữa các Switch

        try:
            for i in range(len(path) - 1):
                u, v = path[i], path[i+1]
                edge_data = self.network_graph[u][v]
                total_delay += edge_data.get('delay', 1.0)
                total_loss += edge_data.get('packet_loss', 1.0)
                min_bw = min(min_bw, edge_data.get('avail_bw', 1.0))
        except KeyError:
            return float('inf')

        # --- TÍNH ĐIỂM PHẠT (SCORE 0-100) ---
        # Càng cao càng tệ
        
        s_delay = min((total_delay / MAX_DELAY) * 100, 100)
        s_loss  = min((total_loss / MAX_LOSS) * 100, 100)
        
     
        s_bw    = min((1 - (min_bw / MAX_BW_INV)) * 100, 100)
        
        # Điểm phạt cho số lượng Hop
        s_hop   = min((hop_count / MAX_HOPS) * 100, 100)

        # --- TỔNG HỢP FITNESS ---
        fitness = (ALPHA * s_delay) + (BETA * s_loss) + (GAMMA * s_bw) + (DELTA * s_hop)
        # self.logger.info(
        #     "Fitness for path %s: Delay=%.2fs (%.1f), Loss=%.2f%% (%.1f), 1/BW=%.2f (%.1f), Hops=%d (%.1f) => Fitness=%.2f",
        #     path, total_delay, s_delay, total_loss, s_loss, inv_bw, s_bw, hop_count, s_hop, fitness
        # )
        # self.logger.info("delay: %s, loss: %s, min_bw: %s, hops: %s, fitness: %s", s_delay, s_loss, s_bw, s_hop, fitness)
        return fitness