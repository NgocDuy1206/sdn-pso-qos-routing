import random
import logging
import networkx as nx


class HybridKSP_PSO:

    NUM_PARTICLES = 10
    MAX_ITERATIONS = 20

    MUTATION_RATE = 0.10
    K_SHORT = 6

    def __init__(self,
                 graph,
                 source,
                 target,
                 logger=None,
                 fitness_func=None,
                 particles=None):

        self.graph = graph
        self.source = source
        self.target = target
        self.logger = logger or logging.getLogger(__name__)
        self.fitness_func = fitness_func
        self.particles = particles

        if fitness_func is None:
            raise ValueError("fitness_func required")

        if not nx.has_path(graph, source, target):
            raise ValueError(f"No path {source}->{target}")


        self._fitness_cache = {}

        self._adj = {
            n: tuple(graph.neighbors(n))
            for n in graph.nodes()
        }

        self._adj_set = {
            n: set(self._adj[n])
            for n in graph.nodes()
        }

        # shortest path fallback
        try:
            self._shortest_path = nx.shortest_path(
                graph,
                source,
                target,
                weight='weight'
            )
        except:
            self._shortest_path = [source, target]

        # hybrid seeds
        self.k_paths = self.build_fast_k_paths()


    def calculate_fitness(self, path):

        key = tuple(path)

        if key not in self._fitness_cache:
            self._fitness_cache[key] = self.fitness_func(path)

        return self._fitness_cache[key]


    def build_fast_k_paths(self):

        paths = []
        seen = set()

        metrics = [
            'delay',
            'packet_loss',
            'aval_bw',
        ]

        for metric in metrics:

            try:
                p = nx.shortest_path(
                    self.graph,
                    self.source,
                    self.target,
                    weight=metric
                )

                tp = tuple(p)

                if tp not in seen:
                    paths.append(p)
                    seen.add(tp)

            except:
                pass

        return paths



    def build_random_simple_path(self):

        limit = len(self.graph) * 2

        for _ in range(10):

            current = self.source

            path = [current]
            visited = {current}

            while current != self.target and len(path) < limit:

                neighs = self._adj[current]

                found = False

                for _ in range(len(neighs)):

                    nxt = neighs[random.randint(0, len(neighs)-1)]

                    if nxt not in visited:

                        visited.add(nxt)
                        path.append(nxt)

                        current = nxt
                        found = True
                        break

                if not found:
                    break

            if path[-1] == self.target:
                return path

        return self._shortest_path[:]



    def repair_path(self, path):

        if not path:
            return self._shortest_path[:]

        repaired = [self.source]

        current = self.source
        visited = {self.source}

        for node in path[1:]:

            if node in visited:
                continue

            if node in self._adj_set[current]:

                repaired.append(node)

                current = node
                visited.add(node)

                if current == self.target:
                    return repaired

        # nối bằng shortest tail hợp lệ
        try:
            tail = nx.shortest_path(
                self.graph,
                current,
                self.target,
                weight='weight'
            )

            for node in tail[1:]:

                if node not in visited:
                    repaired.append(node)
                    visited.add(node)

            return repaired

        except:
            return self._shortest_path[:]



    def crossover(self, path_a, path_b):

        if len(path_a) < 3 or len(path_b) < 3:
            return path_a

        commons = set(path_a[1:-1]) & set(path_b[1:-1])

        if not commons:
            return path_a

        pivot = random.choice(tuple(commons))

        ia = path_a.index(pivot)
        ib = path_b.index(pivot)

        child = path_a[:ia] + path_b[ib:]

        return self.repair_path(child)


    def mutate(self, path):

        if len(path) <= 3:
            return path

        if random.random() > self.MUTATION_RATE:
            return path

        idx = random.randint(1, len(path)-2)

        prev = path[idx-1]

        path_set = set(path)

        neighs = self._adj[prev]

        for _ in range(len(neighs)):

            nxt = neighs[random.randint(0, len(neighs)-1)]

            if nxt not in path_set:

                new_path = path[:]
                new_path[idx] = nxt

                return new_path

        return path


    class Particle:

        def __init__(self, parent):

            self.parent = parent

            self.position = []
            self.personal_best = []

            self.personal_best_fitness = float('inf')

        def initialize_from_path(self, path):

            self.position = self.parent.repair_path(path)

            self.personal_best = self.position[:]

            self.personal_best_fitness = \
                self.parent.calculate_fitness(self.position)

        def update(self, global_best):

            pos = self.position

            if random.random() < 0.55:
                pos = self.parent.crossover(
                    pos,
                    self.personal_best
                )

            if random.random() < 0.55:
                pos = self.parent.crossover(
                    pos,
                    global_best
                )

            pos = self.parent.mutate(pos)

            pos = self.parent.repair_path(pos)

            self.position = pos

            fit = self.parent.calculate_fitness(pos)

            if fit < self.personal_best_fitness:

                self.personal_best = pos[:]
                self.personal_best_fitness = fit



    def run(self):

        self.logger.info(
            f"FAST HYBRID PSO {self.source}->{self.target}"
        )


        if self.particles is None:

            particles = []

            for pth in self.k_paths:

                p = self.Particle(self)

                p.initialize_from_path(pth)

                particles.append(p)

            while len(particles) < self.NUM_PARTICLES:

                p = self.Particle(self)

                p.initialize_from_path(
                    self.build_random_simple_path()
                )

                particles.append(p)

        else:

            particles = self.particles

            for p in particles:
                p.parent = self


        gbest_particle = min(
            particles,
            key=lambda p: p.personal_best_fitness
        )

        global_best = gbest_particle.personal_best[:]

        global_best_fitness = \
            gbest_particle.personal_best_fitness

 

        for _ in range(self.MAX_ITERATIONS):

            for p in particles:

                p.update(global_best)

                if p.personal_best_fitness < global_best_fitness:

                    global_best = p.personal_best[:]

                    global_best_fitness = \
                        p.personal_best_fitness

        self.particles = particles

        return global_best, particles
