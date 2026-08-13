from abc import ABC, abstractmethod

class BaseMetric(ABC):


    def __init__(self, app, graph):
        self.app = app          # RyuApp
        self.graph = graph     # networkx graph

    def register_datapath(self, dp):
        pass

    def start(self):
        pass

    def handle_event(self, ev):
        pass