import heapq
import random
import sys
from collections import deque, namedtuple


Edge = namedtuple('Edge', ['frm', 'to', 'w1', 'w2', 'w3'])

class PSOAlgorithm:
    
    NUM_PARTICLES = 10
    MAX_ITERATIONS = 20
    W = 0.7
    C1 = 2.0
    C2 = 2.0

    def __init__(self, graph, source, target, logger, fitness_func, particles):
        self.graph = graph
        self.fitness_func = fitness_func
        self.source = source
        self.target = target
        self.logger = logger
        self.particles = particles

        self.population_size = self.NUM_PARTICLES
        self.iterations = self.MAX_ITERATIONS

    def get_neighbors(self, vertex):
        # return list of neighbour indices
        return [v for u, v in self.graph.edges() if u == vertex]

    def has_edge(self, frm, to):
        return self.graph.has_edge(frm, to)

    def find_edge(self, frm, to):
        if self.graph.has_edge(frm, to):
            attr = self.graph[frm][to]
            # Convert networkx edge attributes to Edge namedtuple
            # Using delay as w1, packet_loss as w2, and avail_bw as w3 for QoS metrics
            w1 = attr.get('delay', 0.0)
            w2 = attr.get('packet_loss', 0.0)
            w3 = attr.get('avail_bw', 0.0)
            return Edge(frm, to, w1, w2, w3)
        return None

    # repair a potentially invalid path by walking edges and avoiding loops
    def repair_path(self, path):
        max_len = max(2, len(self.graph.nodes()) * 3)
        repaired = []
        visited = set()
        current = self.source
        repaired.append(current)
        visited.add(current)
        for candidate in path[1:]:
            if len(repaired) >= max_len:
                break
            if not self.has_edge(current, candidate) or candidate in visited:
                candidate = self.pick_next_neighbor(current, visited)
                if candidate == -1:
                    break
            repaired.append(candidate)
            current = candidate
            visited.add(current)
            if current == self.target:
                break
        if current != self.target:
            tail = self.shortest_path_bfs(current, self.target)
            if tail and len(tail) >= 2:
                for node in tail[1:]:
                    if len(repaired) >= max_len:
                        break
                    repaired.append(node)
                current = repaired[-1]
        if repaired[-1] != self.target:
            repaired.append(self.target)
        return repaired

    def pick_next_neighbor(self, current, visited):
        neighbors = self.get_neighbors(current)
        if not neighbors:
            return -1
        unvisited = [nb for nb in neighbors if nb not in visited]
        pool = unvisited if unvisited else neighbors
        return random.choice(pool) if pool else -1

    def shortest_path_bfs(self, start, goal):
        if start == goal:
            return [start]
        prev = {}
        visited = set()
        q = deque([start])
        visited.add(start)
        while q:
            u = q.popleft()
            for v in self.graph.neighbors(u):
                if v in visited:
                    continue
                visited.add(v)
                prev[v] = u
                if v == goal:
                    q.clear()
                    break
                q.append(v)
        if goal not in visited:
            return None
        path = []
        at = goal
        while at != start:
            path.append(at)
            at = prev[at]
        path.append(start)
        return path[::-1]

    def run(self):

        
        if self.shortest_path_bfs(self.source, self.target) is None:
            self.logger.info(f"No path exists between {self.source} and {self.target} in this graph.")
            return None
        if self.particles is None:
                # Nếu KHÔNG CÓ (Lần đầu ping), tạo mới hoàn toàn
                self.particles = [self.Particle(self) for _ in range(self.NUM_PARTICLES)]
                for p in self.particles:
                    p.initialize()
                max_iters = self.MAX_ITERATIONS # Chạy nhiều vòng để hội tụ
        else:
         
            # CẬP NHẬT LẠI PARENT: Vì Object PSOAlgorithm vừa được khởi tạo mới 
            # nên các hạt cũ cần trỏ 'parent' về Object mới này để lấy graph/fitness_func mới.
            for p in self.particles:
                p.parent = self
            max_iters = 10
        
        global_best = []
        global_best_fitness = float('inf')
        for p in self.particles:
            p.reCalculate_fitness()
            if p.personal_best_fitness < global_best_fitness:
                global_best_fitness = p.personal_best_fitness
                global_best = list(p.personal_best)
        
        for iter in range(max_iters):
            
            for p in self.particles:
                p.update_velocity(global_best)
                p.update_position(global_best)
                if p.personal_best_fitness < global_best_fitness:
                    global_best_fitness = p.personal_best_fitness
                    global_best = list(p.personal_best)
        if (len(global_best) > 1):
            self.logger.info(f"FINAL RESULT: Best path = {global_best}")
            self.logger.info(f"Total fitness: {global_best_fitness}\n")
        
        return global_best, self.particles

    class Particle:
        def __init__(self, parent):
            self.parent = parent
            self.position = []
            self.velocity = []
            self.personal_best = []
            self.personal_best_fitness = float('inf')

        def reCalculate_fitness(self):
            self.personal_best_fitness = self.calculate_fitness(self.personal_best)

        def initialize(self):
            self.position.clear()
            self.velocity.clear()
            path = self.build_random_simple_path(self.parent.source, self.parent.target)
            if path is None:
                self.position = [self.parent.source, self.parent.target]
            else:
                self.position.extend(path)
            for _ in range(len(self.position)):
                self.velocity.append(random.randint(-1, 1))
            if self.velocity:
                self.velocity[0] = 0
                self.velocity[-1] = 0
            self.personal_best = list(self.position)
            self.personal_best_fitness = self.calculate_fitness(self.position)

        def build_random_simple_path(self, start, goal):
            max_retries = 50
            max_depth = max(2, len(self.parent.graph.nodes()) * 2)
            for _ in range(max_retries):
                visited = set()
                path = []
                if self.dfs_random(start, goal, visited, path, max_depth):
                    return path
            return None

        def dfs_random(self, u, goal, visited, path, remaining_depth):
            visited.add(u)
            path.append(u)
            if u == goal:
                return True
            if remaining_depth <= 0:
                path.pop()
                visited.remove(u)
                return False
            neighbors = list(self.parent.get_neighbors(u))
            random.shuffle(neighbors)
            for v in neighbors:
                if v in visited:
                    continue
                if self.dfs_random(v, goal, visited, path, remaining_depth - 1):
                    return True
            path.pop()
            visited.remove(u)
            return False
        def calculate_fitness(self, path):
            return self.parent.fitness_func(path)
        def get_clamped(self, lst, index, default):
            return default if not lst else lst[min(index, len(lst) - 1)]

        def update_velocity(self, global_best):
            size = len(self.position)
            # resize velocity vector efficiently
            if len(self.velocity) < size:
                self.velocity.extend([0] * (size - len(self.velocity)))
            elif len(self.velocity) > size:
                self.velocity[:] = self.velocity[:size]
            for i in range(size):
                r1, r2 = random.random(), random.random()
                pos_i = self.position[i]
                pb_i = self.get_clamped(self.personal_best, i, pos_i)
                gb_i = self.get_clamped(global_best, i, pos_i)
                new_v = (PSOAlgorithm.W * self.velocity[i]
                         + PSOAlgorithm.C1 * r1 * (pb_i - pos_i)
                         + PSOAlgorithm.C2 * r2 * (gb_i - pos_i))
                self.velocity[i] = round(new_v)
            if self.velocity:
                self.velocity[0] = 0
                self.velocity[-1] = 0

        def update_position(self, global_best):
            size = len(self.position)
            # ensure velocity length matches
            if len(self.velocity) < size:
                self.velocity.extend([0] * (size - len(self.velocity)))
            elif len(self.velocity) > size:
                self.velocity[:] = self.velocity[:size]
            new_pos = list(self.position)
            for i, v in enumerate(self.velocity):
                cand = self.position[i] + v
                # clamp to valid vertex indices
                cand = max(0, min(cand, len(self.parent.graph.nodes()) - 1))
                # Only fix source and target if they're at the correct positions
                if i == 0 and cand != self.parent.source:
                    cand = self.parent.source
                elif i == size - 1 and cand != self.parent.target:
                    cand = self.parent.target
                new_pos[i] = cand
                
            self.position = self.parent.repair_path(new_pos)
            current_fitness = self.calculate_fitness(self.position)
            if current_fitness < self.personal_best_fitness:
                self.personal_best = list(self.position)
                self.personal_best_fitness = current_fitness
