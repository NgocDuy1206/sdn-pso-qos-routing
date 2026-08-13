import time
import subprocess
import re
from ryu.controller import ofp_event
from metric_base import BaseMetric


class PacketLossMetric(BaseMetric):

    def __init__(self, app, graph):
        super().__init__(app, graph)
        self._last_poll = 0
        self._poll_interval = 1.0  # giây

    def register_datapath(self, dp):
        pass

    def start(self):
        pass

    def handle_event(self, ev):
        # Dùng PortStatsReply làm trigger để poll định kỳ
        if not isinstance(ev, ofp_event.EventOFPPortStatsReply):
            return

        now = time.time()
        if now - self._last_poll < self._poll_interval:
            return
        self._last_poll = now

        self._poll_netem_loss()

    def _poll_netem_loss(self):
        """Đọc loss từ tc netem trực tiếp trên từng interface"""
        for src, dst, attr in self.graph.edges(data=True):
            port = attr.get('port')
            if port is None:
                continue

            # Tìm interface name: s{dpid}-eth{port}
            dev = f's{src}-eth{port}'

            try:
                result = subprocess.run(
                    ['tc', 'qdisc', 'show', 'dev', dev],
                    capture_output=True, text=True, timeout=1
                )
                output = result.stdout

                # Parse loss từ netem output
                # Ví dụ: "qdisc netem 10: parent 1:1 limit 1000 delay 100ms loss 10%"
                match = re.search(r'loss\s+([\d.]+)%', output)
                if match:
                    loss_percent = float(match.group(1))
                else:
                    loss_percent = 0.0

                attr['packet_loss'] = loss_percent

            except Exception as e:
                # Interface không tồn tại hoặc lỗi khác
                attr['packet_loss'] = 0.0