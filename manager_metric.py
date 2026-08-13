from ryu.lib import hub

class MetricManager:


    def __init__(self, app, graph):
        self.app = app
        self.graph = graph
        self.metrics = []

    def add_metric(self, metric):
        self.metrics.append(metric)
        metric.start()

    def register_datapath(self, dp):
        for m in self.metrics:
            m.register_datapath(dp)

    def handle_event(self, ev):
        for m in self.metrics:
            m.handle_event(ev)
    def log_graph(self):
        for u, v, attr in self.graph.edges(data=True):
            self.app.logger.info(
                "EDGE %s -> %s | attr=%s",
                u, v, attr
            )