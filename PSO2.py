import heapq
import random
import sys
from collections import deque, namedtuple
import networkx as nx
import logging

Edge = namedtuple('Edge', ['frm', 'to', 'w1', 'w2', 'w3'])  # delay, packet_loss, avail_bw

class HybridKSP_PSO:
    NUM_PARTICLES = 20
    MAX_ITERATIONS = 30
    K_SHORT = 8                    # Số đường ngắn nhất từ KSP
    W = 0.7
    C1 = 1.8
    C2 = 1.8

    def __init__(self, graph: nx.Graph, source, target, logger=None, fitness_func=None):
        self.graph = graph
        self.source = source
        self.target = target
        self.fitness_func = fitness_func or self.default_fitness
        self.logger = logger or logging.getLogger(__name__)
        
        if not nx.has_path(graph, source, target):
            raise ValueError(f"No path from {source} to {target}")

    def default_fitness(self, path):
        """Fitness mặc định cho QoS: minimize delay + loss, maximize bandwidth"""
        if not path or path[0] != self.source or path[-1] != self.target:
            return float('inf')
        total_delay = 0.0
        total_loss = 0.0
        min_bw = float('inf')
        for i in range(len(path)-1):
            u, v = path[i], path[i+1]
            if not self.graph.has_edge(u, v):
                return float('inf')
            attr = self.graph[u][v]
            total_delay += attr.get('delay', 0.0)
            total_loss += attr.get('packet_loss', 0.0)
            min_bw = min(min_bw, attr.get('avail_bw', 0.0))
        
        # Penalize long path + cycle
        penalty = len(path) * 0.1
        return total_delay + total_loss * 100 - min_bw * 0.01 + penalty

    def get_k_shortest_paths(self, k=10):
        """Sử dụng nx.shortest_simple_paths (approximate Yen's) hoặc implement Yen's đầy đủ"""
        try:
            paths = list(nx.shortest_simple_paths(self.graph, self.source, self.target, weight='weight'))[:k]
            return paths
        except nx.NetworkXNoPath:
            return []

    def repair_path(self, path):
        """Repair path: loại bỏ cycle, nối lại nếu cần"""
        if not path:
            return [self.source, self.target]
        
        repaired = []
        visited = set()
        current = self.source
        repaired.append(current)
        visited.add(current)

        for node in path[1:]:
            if node in visited or not self.graph.has_edge(current, node):
                continue
            repaired.append(node)
            visited.add(node)
            current = node
            if current == self.target:
                break

        if repaired[-1] != self.target:
            # Thử nối bằng BFS ngắn nhất
            tail = self.shortest_path_bfs(current, self.target)
            if tail and len(tail) > 1:
                repaired.extend(tail[1:])

        return repaired if repaired[-1] == self.target else [self.source, self.target]

    def shortest_path_bfs(self, start, goal):
        if start == goal:
            return [start]
        prev = {}
        q = deque([start])
        visited = {start}
        while q:
            u = q.popleft()
            for v in self.graph.neighbors(u):
                if v not in visited:
                    visited.add(v)
                    prev[v] = u
                    q.append(v)
                    if v == goal:
                        # Reconstruct
                        path = []
                        at = goal
                        while at != start:
                            path.append(at)
                            at = prev[at]
                        path.append(start)
                        return path[::-1]
        return None

    class Particle:
        def __init__(self, parent):
            self.parent = parent
            self.position = []          # list of nodes
            self.velocity = []          # list of integers (delta node index)
            self.personal_best = []
            self.personal_best_fitness = float('inf')

        def initialize_from_path(self, path):
            self.position = self.parent.repair_path(path)
            self.personal_best = list(self.position)
            self.personal_best_fitness = self.parent.fitness_func(self.position)
            self.velocity = [random.randint(-2, 2) for _ in self.position]
            if self.velocity:
                self.velocity[0] = 0
                self.velocity[-1] = 0

        def update_velocity(self, global_best):
            size = len(self.position)
            if len(self.velocity) != size:
                self.velocity = [0] * size

            for i in range(size):
                r1 = random.random()
                r2 = random.random()
                pb = self.personal_best[i] if i < len(self.personal_best) else self.position[i]
                gb = global_best[i] if i < len(global_best) else self.position[i]
                
                new_v = (HybridKSP_PSO.W * self.velocity[i] +
                         HybridKSP_PSO.C1 * r1 * (pb - self.position[i]) +
                         HybridKSP_PSO.C2 * r2 * (gb - self.position[i]))
                self.velocity[i] = round(new_v)
            if self.velocity:
                self.velocity[0] = 0
                self.velocity[-1] = 0

        def update_position(self):
            new_pos = list(self.position)
            for i, v in enumerate(self.velocity):
                if i == 0 or i == len(new_pos)-1:
                    continue
                cand = self.position[i] + v
                # Clamp node id (giả sử node là integer 0..N-1)
                cand = max(min(cand, max(self.parent.graph.nodes())), min(self.parent.graph.nodes()))
                new_pos[i] = cand

            self.position = self.parent.repair_path(new_pos)
            fitness = self.parent.fitness_func(self.position)

            if fitness < self.personal_best_fitness:
                self.personal_best = list(self.position)
                self.personal_best_fitness = fitness

    def run(self):
        self.logger.info(f"Hybrid K-Shortest Paths + PSO from {self.source} -> {self.target}")

        # Giai đoạn 1: Khởi tạo bằng K-Shortest Paths + random
        k_paths = self.get_k_shortest_paths(k=self.K_SHORT)
        
        particles = []
        # Thêm particles từ KSP
        for pth in k_paths:
            if len(particles) >= self.NUM_PARTICLES:
                break
            particle = self.Particle(self)
            particle.initialize_from_path(pth)
            particles.append(particle)

        # Bổ sung particles random nếu chưa đủ
        while len(particles) < self.NUM_PARTICLES:
            particle = self.Particle(self)
            random_path = self._build_random_simple_path()
            particle.initialize_from_path(random_path)
            particles.append(particle)

        # Tìm global best ban đầu
        global_best = min(particles, key=lambda p: p.personal_best_fitness).personal_best[:]
        global_best_fitness = self.fitness_func(global_best)

        # Giai đoạn 2: PSO iterations
        for it in range(self.MAX_ITERATIONS):
            for p in particles:
                p.update_velocity(global_best)
                p.update_position()

                if p.personal_best_fitness < global_best_fitness:
                    global_best = list(p.personal_best)
                    global_best_fitness = p.personal_best_fitness

            if it % 5 == 0:
                self.logger.info(f"Iter {it:2d} | Best fitness: {global_best_fitness:.4f} | Path len: {len(global_best)-1}")

        self.logger.info("=== HYBRID PSO RESULT ===")
        self.logger.info(f"Best path: {global_best}")
        self.logger.info(f"Fitness: {global_best_fitness:.4f}")
        return global_best, global_best_fitness, particles

    def _build_random_simple_path(self):
        """Tương tự build_random_simple_path của bạn"""
        max_retries = 30
        for _ in range(max_retries):
            path = []
            visited = set()
            if self._dfs_random(self.source, self.target, visited, path, max_depth= len(self.graph)*2):
                return path
        return [self.source, self.target]

    def _dfs_random(self, u, goal, visited, path, remaining_depth):
        visited.add(u)
        path.append(u)
        if u == goal:
            return True
        if remaining_depth <= 0:
            path.pop()
            visited.remove(u)
            return False

        neighbors = list(self.graph.neighbors(u))
        random.shuffle(neighbors)
        for v in neighbors:
            if v not in visited:
                if self._dfs_random(v, goal, visited, path, remaining_depth-1):
                    return True
        path.pop()
        visited.remove(u)
        return False