from pyvis.network import Network
import json


class FatTreeVisualizerRT:
    def __init__(self, k=4):
        self.k = k
        self.net = Network(
            height="800px",
            width="100%",
            bgcolor="#1a1a1a",
            font_color="white",
            directed=False
        )

    @staticmethod
    def make_edge_id(u, v):
        """Canonical edge ID (giống JS)"""
        a, b = sorted([str(u), str(v)])
        return f"{a}__{b}"

    # ================= BUILD FAT-TREE =================
    def build_fattree(self):
        k = self.k
        num_pods = k
        num_core = (k // 2) ** 2
        num_agg = k // 2
        num_edge = k // 2
        num_host = k // 2

        # Layout config
        X_GAP, Y_GAP = 120, 180
        POD_WIDTH = (num_agg * X_GAP) + 50
        TOTAL_WIDTH = num_pods * POD_WIDTH
        START_X = -TOTAL_WIDTH // 2

        # ===== CORE =====
        core_ids = []
        span = TOTAL_WIDTH / (num_core - 1 if num_core > 1 else 1)

        for i in range(num_core):
            cid = f"S_core_{i+1}"
            core_ids.append(cid)

            x = START_X + i * span

            self.net.add_node(
                cid,
                label=f"Core {i+1}",
                color="#FFD700",
                shape="diamond",
                size=25,
                x=x,
                y=0,
                fixed=True
            )

        # ===== PODS =====
        for p in range(num_pods):
            pod_center = START_X + p * POD_WIDTH + POD_WIDTH // 2
            agg_nodes = []

            # ---- AGG ----
            for i in range(num_agg):
                aid = f"S_agg_{p}_{i}"
                agg_nodes.append(aid)

                x = pod_center + (i - (num_agg - 1) / 2) * X_GAP

                self.net.add_node(
                    aid,
                    label=f"Agg {p}.{i}",
                    color="#FF8C00",
                    size=20,
                    x=x,
                    y=Y_GAP,
                    fixed=True
                )

                # Agg -> Core
                offset = i * (k // 2)
                for j in range(k // 2):
                    self._add_edge(aid, core_ids[offset + j])

            # ---- EDGE ----
            for i in range(num_edge):
                eid = f"S_edge_{p}_{i}"
                x = pod_center + (i - (num_edge - 1) / 2) * X_GAP

                self.net.add_node(
                    eid,
                    label=f"Edge {p}.{i}",
                    color="#1E90FF",
                    size=20,
                    x=x,
                    y=Y_GAP * 2,
                    fixed=True
                )

                # Edge -> Agg
                for aid in agg_nodes:
                    self._add_edge(eid, aid)

                # ---- HOST ----
                for h in range(num_host):
                    hid = f"H_{p}_{i}_{h}"
                    hx = x + (h - (num_host - 1) / 2) * 40

                    self.net.add_node(
                        hid,
                        label=f"H_{h}",
                        color="#32CD32",
                        shape="square",
                        size=12,
                        x=hx,
                        y=Y_GAP * 3,
                        fixed=True
                    )

                    self._add_edge(hid, eid)

    def _add_edge(self, u, v):
        eid = self.make_edge_id(u, v)
        self.net.add_edge(u, v, id=eid, color="#444444", width=1)

    # ================= ANIMATION =================
    def animate_paths(self, paths, delay=500):
        js = """
        var edges = network.body.data.edges;
        var nodes = network.body.data.nodes;

        function makeEdgeId(u, v){
            return [u, v].sort().join("__");
        }

        function baseSize(id){
            if(id.startsWith("H_")) return 12;
            if(id.startsWith("S_core_")) return 25;
            return 20;
        }

        function setStatus(u, v, active){
            var id = makeEdgeId(u, v);
            var e = edges.get(id);

            if(e){
                edges.update({
                    id: id,
                    color: active ? "#00FFFF" : "#444444",
                    width: active ? 6 : 1,
                    shadow: active
                });
            }

            [u, v].forEach(n=>{
                nodes.update({
                    id: n,
                    size: active ? baseSize(n)+8 : baseSize(n)
                });
            });
        }
        """

        t = 0

        for path in paths:
            # highlight
            for i in range(len(path)-1):
                js += f'setTimeout(()=>setStatus("{path[i]}","{path[i+1]}",true),{t});\n'
                t += delay

            t += delay

            # reset
            for i in range(len(path)-1):
                js += f'setTimeout(()=>setStatus("{path[i]}","{path[i+1]}",false),{t});\n'
                t += delay//2

            t += delay

        self.net.set_options(json.dumps({
            "physics": {"enabled": False},
            "interaction": {
                "hover": True,
                "navigationButtons": True
            }
        }))

        html = self.net.generate_html()
        self.net.html = html.replace("</body>", f"<script>{js}</script></body>")

    # ================= SAVE =================
    def save(self, filename="fattree.html"):
        with open(filename, "w", encoding="utf-8") as f:
            f.write(self.net.html)
        print("Saved:", filename)


# ================= TEST =================
if __name__ == "__main__":
    vis = FatTreeVisualizerRT(k=4)
    vis.build_fattree()

    path1 = ["H_0_0_0","S_edge_0_0","S_agg_0_0","S_core_1","S_agg_1_0","S_edge_1_0","H_1_0_1"]
    path2 = ["H_2_1_1","S_edge_2_1","S_agg_2_1","S_core_4","S_agg_3_1","S_edge_3_1","H_3_1_0"]

    vis.animate_paths([path1, path2], delay=500)
    vis.save("demo_fattree.html")