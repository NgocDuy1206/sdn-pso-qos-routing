"""
Network Graph Visualization Module

This module provides functionality to visualize NetworkX graphs representing
the SDN network topology, and to draw specific paths on the graph with animation.
"""

import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import FancyArrowPatch
import networkx as nx
from typing import List, Tuple, Optional, Dict, Any, Callable
import numpy as np


class NetworkGraphVisualizer:
    """Visualizer for SDN network topology graphs with animation support."""
    
    def __init__(self, figsize: Tuple[int, int] = (16, 10)):
        """
        Initialize the visualizer.
        
        Args:
            figsize: Figure size as (width, height) in inches
        """
        self.figsize = figsize
        self.fig = None
        self.ax = None
        self.pos = None
        self.graph = None
        self.hosts = {}  # host_mac -> node_id mapping
        self.host_positions = {}  # host_mac -> (x, y) position
        self.animation_obj = None
        
    def add_hosts_to_graph(
        self,
        network_graph: nx.DiGraph,
        hosts_loc: Dict[str, Tuple[int, int]]
    ) -> nx.DiGraph:
        """
        Add host nodes to the graph for visualization.
        
        Args:
            network_graph: Original NetworkX DiGraph
            hosts_loc: Mapping from host MAC to (dpid, port)
            
        Returns:
            Extended graph with host nodes
        """
        G = network_graph.copy()
        
        # Add host nodes
        self.hosts = {}
        for mac, (dpid, port) in hosts_loc.items():
            host_node = f"host_{mac}"
            G.add_node(host_node, node_type='host', mac=mac)
            # Add edge from host to its connected switch
            G.add_edge(host_node, dpid, port=port, is_host_link=True)
            self.hosts[mac] = host_node
        
        return G
    
    def _hierarchical_layout(
        self,
        network_graph: nx.DiGraph,
        layers: Optional[Dict[int, List[int]]] = None
    ) -> Dict[int, Tuple[float, float]]:
        """
        Create a hierarchical/layered layout for the graph.
        
        Args:
            network_graph: NetworkX graph
            layers: Dict mapping layer number to list of node IDs.
                   If None, attempts to auto-detect layers.
        
        Returns:
            Position dictionary {node: (x, y)}
        """
        pos = {}
        
        # Get all switch nodes (exclude hosts)
        all_nodes = [n for n in network_graph.nodes() 
                    if not str(n).startswith('host_')]
        
        if layers is None:
            # Auto-detect layers based on topological sort and connectivity
            layers = {}
            
            if not all_nodes:
                layers[0] = list(network_graph.nodes())
            else:
                try:
                    # Simple heuristic: group by in-degree
                    in_degrees = {n: network_graph.in_degree(n) for n in all_nodes}
                    
                    # Group nodes by in-degree
                    degree_groups = {}
                    for node, deg in in_degrees.items():
                        if deg not in degree_groups:
                            degree_groups[deg] = []
                        degree_groups[deg].append(node)
                    
                    layer_idx = 0
                    for degree in sorted(degree_groups.keys()):
                        layers[layer_idx] = sorted(degree_groups[degree])
                        layer_idx += 1
                except:
                    # Fallback: just use one layer
                    layers[0] = all_nodes
        else:
            # Ensure all switch nodes are in layers
            positioned_nodes = set()
            for layer_nodes in layers.values():
                positioned_nodes.update(layer_nodes)
            
            unpositioned = [n for n in all_nodes if n not in positioned_nodes]
            if unpositioned:
                # Add unpositioned nodes to the last layer
                if layers:
                    max_layer = max(layers.keys())
                    layers[max_layer + 1] = unpositioned
                else:
                    layers[0] = unpositioned
        
        # Position nodes in layers
        num_layers = len(layers)
        max_nodes_in_layer = max(len(nodes) for nodes in layers.values()) if layers else 1
        
        for layer_idx, (layer_num, nodes) in enumerate(sorted(layers.items())):
            num_nodes = len(nodes)
            y = 1.0 - (layer_idx / (num_layers - 1)) if num_layers > 1 else 0.5
            
            for node_idx, node in enumerate(sorted(nodes)):
                x = (node_idx + 1) / (num_nodes + 1) if num_nodes > 0 else 0.5
                pos[node] = (x, y)
        
        # Position hosts at the bottom
        num_hosts = len(self.hosts)
        for host_idx, (mac, host_node) in enumerate(sorted(self.hosts.items())):
            if host_node in network_graph.nodes():
                x = (host_idx + 1) / (num_hosts + 1) if num_hosts > 0 else 0.5
                y = -0.15  # Below the switch layers
                pos[host_node] = (x, y)
                self.host_positions[mac] = (x, y)
        
        return pos
    
    def draw_graph(
        self, 
        network_graph: nx.DiGraph,
        hosts_loc: Optional[Dict[str, Tuple[int, int]]] = None,
        layout: str = 'hierarchical',
        layers: Optional[Dict[int, List[int]]] = None,
        node_size: int = 1500,
        host_node_size: int = 800,
        node_color: str = 'lightblue',
        host_color: str = 'lightgreen',
        edge_color: str = 'gray',
        with_labels: bool = True,
        arrows: bool = True,
        title: str = "Network Topology",
        show_edge_labels: bool = False
    ) -> Tuple[plt.Figure, plt.Axes]:
        """
        Draw the network graph with optional hosts.
        
        Args:
            network_graph: NetworkX DiGraph representing the network
            hosts_loc: Optional dict mapping host MAC to (dpid, port)
            layout: Layout algorithm ('hierarchical', 'spring', 'circular', 'kamada_kawai')
            layers: For hierarchical layout, dict mapping layer number to node lists
            node_size: Size of switch nodes
            host_node_size: Size of host nodes
            node_color: Color of switch nodes
            host_color: Color of host nodes
            edge_color: Color of edges
            with_labels: Whether to show node labels
            arrows: Whether to draw arrows
            title: Plot title
            show_edge_labels: Whether to display edge attributes
            
        Returns:
            Tuple of (figure, axes)
        """
        # Add hosts if provided
        if hosts_loc:
            network_graph = self.add_hosts_to_graph(network_graph, hosts_loc)
        
        self.graph = network_graph
        self.fig, self.ax = plt.subplots(figsize=self.figsize)
        
        # Compute layout
        if layout == 'hierarchical':
            self.pos = self._hierarchical_layout(network_graph, layers=layers)
        elif layout == 'spring':
            self.pos = nx.spring_layout(network_graph, k=2, iterations=50)
        elif layout == 'circular':
            self.pos = nx.circular_layout(network_graph)
        elif layout == 'kamada_kawai':
            self.pos = nx.kamada_kawai_layout(network_graph)
        else:
            self.pos = nx.spring_layout(network_graph, k=2, iterations=50)
        
        # Separate switches and hosts
        switch_nodes = [n for n in network_graph.nodes() 
                       if not str(n).startswith('host_')]
        host_nodes = [n for n in network_graph.nodes() 
                     if str(n).startswith('host_')]
        
        # Draw switch nodes
        nx.draw_networkx_nodes(
            network_graph,
            self.pos,
            nodelist=switch_nodes,
            node_size=node_size,
            node_color=node_color,
            ax=self.ax,
            label='Switches'
        )
        
        # Draw host nodes
        if host_nodes:
            nx.draw_networkx_nodes(
                network_graph,
                self.pos,
                nodelist=host_nodes,
                node_size=host_node_size,
                node_color=host_color,
                ax=self.ax,
                label='Hosts'
            )
        
        # Separate host and switch edges
        host_edges = [(u, v) for u, v in network_graph.edges() 
                      if str(u).startswith('host_') or str(v).startswith('host_')]
        switch_edges = [(u, v) for u, v in network_graph.edges() 
                       if u not in host_nodes and v not in host_nodes]
        
        # Draw switch edges
        nx.draw_networkx_edges(
            network_graph,
            self.pos,
            edgelist=switch_edges,
            edge_color=edge_color,
            arrows=arrows,
            arrowsize=20,
            arrowstyle='->',
            width=2,
            ax=self.ax,
            connectionstyle="arc3,rad=0.1",
            alpha=0.7
        )
        
        # Draw host edges (lighter)
        nx.draw_networkx_edges(
            network_graph,
            self.pos,
            edgelist=host_edges,
            edge_color='gray',
            arrows=arrows,
            arrowsize=15,
            arrowstyle='->',
            width=1.5,
            ax=self.ax,
            connectionstyle="arc3,rad=0.1",
            alpha=0.4,
            style='dashed'
        )
        
        # Draw labels
        if with_labels:
            labels = {}
            for node in network_graph.nodes():
                if str(node).startswith('host_'):
                    mac = network_graph.nodes[node].get('mac', node)
                    labels[node] = mac.replace(':', '')[-6:]  # Last 6 chars of MAC
                else:
                    labels[node] = f"S{node}"
            
            nx.draw_networkx_labels(
                network_graph,
                self.pos,
                labels=labels,
                font_size=9,
                font_weight='bold',
                ax=self.ax
            )
        
        # Draw edge labels if requested
        if show_edge_labels:
            edge_labels = {}
            for u, v, data in network_graph.edges(data=True):
                if data.get('is_host_link'):
                    continue  # Skip host links
                label_parts = []
                if 'port' in data:
                    label_parts.append(f"p:{data['port']}")
                if 'delay' in data:
                    label_parts.append(f"d:{data['delay']:.3f}s")
                if 'avail_bw' in data:
                    label_parts.append(f"bw:{data['avail_bw']:.1f}Mbps")
                if label_parts:
                    edge_labels[(u, v)] = '\n'.join(label_parts)
            
            if edge_labels:
                nx.draw_networkx_edge_labels(
                    network_graph,
                    self.pos,
                    edge_labels=edge_labels,
                    font_size=7,
                    ax=self.ax
                )
        
        self.ax.set_title(title, fontsize=16, fontweight='bold')
        self.ax.axis('off')
        if host_nodes:
            self.ax.legend(scatterpoints=1, loc='upper left')
        plt.tight_layout()
        
        return self.fig, self.ax
    
    def animate_path(
        self,
        path: List[int],
        color: str = 'red',
        width: float = 3.0,
        alpha: float = 0.8,
        interval: int = 500,
        highlight_nodes: bool = True,
        node_color_path: str = 'orange',
        repeat: bool = True
    ) -> animation.FuncAnimation:
        """
        Animate drawing a path on the graph.
        
        Args:
            path: List of node IDs representing the path
            color: Color for the path edges
            width: Width of path edges
            alpha: Transparency of path
            interval: Delay between animation frames in milliseconds
            highlight_nodes: Whether to highlight nodes
            node_color_path: Color for highlighted nodes
            repeat: Whether to repeat animation
            
        Returns:
            FuncAnimation object
            
        Raises:
            ValueError: If graph hasn't been drawn or path is invalid
        """
        if self.graph is None or self.pos is None:
            raise ValueError("Graph must be drawn first using draw_graph()")
        
        if len(path) < 2:
            raise ValueError("Path must contain at least 2 nodes")
        
        # Verify nodes exist and edges are valid
        for node in path:
            if node not in self.graph:
                raise ValueError(f"Node {node} not found in graph")
        
        # Verify all edges in path exist in graph
        path_edges = [(path[i], path[i+1]) for i in range(len(path)-1)]
        for u, v in path_edges:
            if not self.graph.has_edge(u, v):
                raise ValueError(f"Edge {u} -> {v} not found in graph. Path doesn't follow valid connections.")
        
        # Store initial figure and axes for animation
        fig = self.fig
        ax = self.ax
        
        def animate_frame(frame_num):
            # Calculate how many edges to draw (1 edge per frame)
            edges_to_draw = min(frame_num, len(path_edges))
            
            artists = []
            
            # Draw path edges using NetworkX for consistency
            edges_list = path_edges[:edges_to_draw]
            if edges_list:
                # Use NetworkX to draw edges (matches the original graph style)
                edge_collection = nx.draw_networkx_edges(
                    self.graph,
                    self.pos,
                    edgelist=edges_list,
                    edge_color=color,
                    width=width,
                    alpha=alpha,
                    arrows=True,
                    arrowsize=25,
                    arrowstyle='->',
                    ax=ax,
                    connectionstyle="arc3,rad=0.1"
                )
                # NetworkX drawing functions return collections that can be added to artists
                if edge_collection is not None:
                    artists.append(edge_collection)
            
            # Highlight nodes on the path drawn so far
            if highlight_nodes and edges_to_draw > 0:
                nodes_to_highlight = path[:edges_to_draw + 1]
                scatter = nx.draw_networkx_nodes(
                    self.graph,
                    self.pos,
                    nodelist=nodes_to_highlight,
                    node_size=1800,
                    node_color=node_color_path,
                    alpha=0.9,
                    ax=ax,
                    edgecolors=color,
                    linewidths=3
                )
                if scatter is not None:
                    artists.append(scatter)
            
            # Return artists or dummy if empty (required by FuncAnimation)
            return artists if artists else [ax.plot([], [])[0]]
        
        # Total frames: 1 per edge + a few extra for pause
        total_frames = len(path_edges) + 3
        
        self.animation_obj = animation.FuncAnimation(
            fig, animate_frame,
            frames=total_frames, interval=interval,
            blit=True, repeat=repeat
        )
        
        return self.animation_obj
    
    def draw_path(
        self,
        path: List[int],
        color: str = 'red',
        width: float = 3.0,
        alpha: float = 0.7,
        highlight_nodes: bool = True,
        node_color_path: str = 'orange'
    ) -> None:
        """
        Draw a static path on the graph (non-animated).
        
        Args:
            path: List of node IDs
            color: Path color
            width: Path width
            alpha: Transparency
            highlight_nodes: Whether to highlight nodes
            node_color_path: Color for highlighted nodes
        """
        if self.graph is None or self.pos is None:
            raise ValueError("Graph must be drawn first using draw_graph()")
        
        if len(path) < 2:
            raise ValueError("Path must contain at least 2 nodes")
        
        for node in path:
            if node not in self.graph:
                raise ValueError(f"Node {node} not found in graph")
        
        # Draw path edges
        path_edges = [(path[i], path[i+1]) for i in range(len(path)-1)]
        
        nx.draw_networkx_edges(
            self.graph,
            self.pos,
            edgelist=path_edges,
            edge_color=color,
            width=width,
            alpha=alpha,
            arrows=True,
            arrowsize=25,
            arrowstyle='->',
            ax=self.ax,
            connectionstyle="arc3,rad=0.1"
        )
        
        # Highlight nodes
        if highlight_nodes:
            path_nodes = path
            nx.draw_networkx_nodes(
                self.graph,
                self.pos,
                nodelist=path_nodes,
                node_size=1800,
                node_color=node_color_path,
                alpha=0.9,
                ax=self.ax,
                edgecolors=color,
                linewidths=3
            )
            
            # Re-draw labels
            nx.draw_networkx_labels(
                self.graph,
                self.pos,
                labels={node: f"S{node}" for node in path_nodes},
                font_size=10,
                font_weight='bold',
                ax=self.ax
            )
    
    def save_figure(self, filename: str, dpi: int = 300) -> None:
        """Save the current figure to a file."""
        if self.fig is None:
            raise ValueError("No figure to save. Call draw_graph() first.")
        
        self.fig.savefig(filename, dpi=dpi, bbox_inches='tight')
        print(f"Figure saved to {filename}")
    
    def save_animation(self, filename: str, fps: int = 2) -> None:
        """
        Save animation to file.
        
        Args:
            filename: Output filename (supports .mp4, .gif, etc.)
            fps: Frames per second
        """
        if self.animation_obj is None:
            raise ValueError("No animation to save. Call animate_path() first.")
        
        try:
            self.animation_obj.save(filename, fps=fps)
            print(f"Animation saved to {filename}")
        except Exception as e:
            print(f"Failed to save animation: {e}")
            print("Make sure you have ffmpeg installed: sudo apt-get install ffmpeg")
    
    def show(self) -> None:
        """Display the figure and animation."""
        if self.fig is None:
            raise ValueError("No figure to show. Call draw_graph() first.")
        plt.show()
    
    def show_animated_path(
        self,
        network_graph: nx.DiGraph,
        path: List[int],
        hosts_loc: Optional[Dict[str, Tuple[int, int]]] = None,
        layout: str = 'hierarchical',
        layers: Optional[Dict[int, List[int]]] = None,
        path_color: str = 'red',
        delay_before_animation: int = 2,
        animation_interval: int = 400,
        figsize: Tuple[int, int] = (16, 10),
        title: str = "Network Topology with Path"
    ) -> None:
        """
        Show an interactive window with graph and animated path.
        
        This is the easiest way to visualize: opens a window, shows the graph
        for a few seconds, then animates the path.
        
        Args:
            network_graph: NetworkX DiGraph
            path: List of node IDs for the path
            hosts_loc: Optional host locations
            layout: Layout algorithm
            layers: Layer definitions for hierarchical layout
            path_color: Color for path animation
            delay_before_animation: Seconds to wait before starting animation
            animation_interval: Milliseconds between animation frames
            figsize: Figure size
            title: Window title
            
        Example:
            from draw.network_graph_visualizer import NetworkGraphVisualizer
            import networkx as nx
            
            G = nx.DiGraph()
            G.add_edges_from([(1, 2), (2, 3)])
            
            viz = NetworkGraphVisualizer()
            viz.show_animated_path(
                G, 
                path=[1, 2, 3],
                path_color='red',
                delay_before_animation=2
            )
        """
        self.clear()  # Clear any previous figure
        self.__init__(figsize=figsize)  # Reinitialize
        
        # Draw the network graph
        self.draw_graph(
            network_graph,
            hosts_loc=hosts_loc,
            layout=layout,
            layers=layers,
            title=title
        )
        
        # Validate path before creating animation
        if len(path) < 2:
            raise ValueError("Path must have at least 2 nodes")
        
        for node in path:
            if node not in network_graph:
                raise ValueError(f"Node {node} not found in graph")
        
        # Verify edges
        for i in range(len(path) - 1):
            if not network_graph.has_edge(path[i], path[i+1]):
                raise ValueError(f"Edge {path[i]} → {path[i+1]} not found in graph")
        
        # Calculate delay in animation frames (each frame is animation_interval ms)
        delay_frames = int((delay_before_animation * 1000) / animation_interval)
        path_edges = [(path[i], path[i+1]) for i in range(len(path)-1)]
        
        # Create animation with delay
        fig = self.fig
        ax = self.ax
        pos = self.pos
        graph = self.graph
        
        def animate_with_delay(frame_num):
            # Skip frames during delay
            if frame_num < delay_frames:
                return [ax.plot([], [])[0]]  # Return dummy artist
            
            # Calculate path progress
            path_progress = frame_num - delay_frames
            edges_to_draw = min(path_progress, len(path_edges))
            
            artists = []
            
            # Draw edges
            edges_list = path_edges[:edges_to_draw]
            if edges_list:
                edge_collection = nx.draw_networkx_edges(
                    graph, pos,
                    edgelist=edges_list,
                    edge_color=path_color,
                    width=4.0,
                    alpha=0.8,
                    arrows=True,
                    arrowsize=25,
                    arrowstyle='->',
                    ax=ax,
                    connectionstyle="arc3,rad=0.1"
                )
                if edge_collection is not None:
                    artists.append(edge_collection)
            
            # Highlight nodes
            if edges_to_draw > 0:
                nodes_to_draw = path[:edges_to_draw + 1]
                scatter = nx.draw_networkx_nodes(
                    graph, pos,
                    nodelist=nodes_to_draw,
                    node_size=1800,
                    node_color='orange',
                    alpha=0.9,
                    ax=ax,
                    edgecolors=path_color,
                    linewidths=3
                )
                if scatter is not None:
                    artists.append(scatter)
            
            return artists if artists else [ax.plot([], [])[0]]
        
        # Total frames: delay + 1 frame per edge + pause at end
        total_frames = delay_frames + len(path_edges) + 5
        
        self.animation_obj = animation.FuncAnimation(
            fig, animate_with_delay,
            frames=total_frames,
            interval=animation_interval,
            blit=True,
            repeat=True
        )
        
        # Show the interactive window
        plt.show()
    
    def clear(self) -> None:
        """Clear the current figure."""
        if self.fig is not None:
            plt.close(self.fig)
        self.fig = None
        self.ax = None
        self.pos = None
        self.graph = None
        self.animation_obj = None


# Convenience functions for quick visualization
def show_network_animation(
    network_graph: nx.DiGraph,
    path: List[int],
    hosts_loc: Optional[Dict[str, Tuple[int, int]]] = None,
    layout: str = 'hierarchical',
    layers: Optional[Dict[int, List[int]]] = None,
    path_color: str = 'red',
    delay: int = 2,
    title: str = "Network Topology"
) -> None:
    """
    Quick way to show animated path in an interactive window.
    
    Opens a window, displays the graph, waits a few seconds, then animates the path.
    
    Args:
        network_graph: NetworkX DiGraph
        path: List of node IDs for the path
        hosts_loc: Optional host locations
        layout: Layout algorithm
        layers: For hierarchical layout
        path_color: Color for the path
        delay: Seconds before animation starts
        title: Window title
        
    Example:
        from draw.network_graph_visualizer import show_network_animation
        import networkx as nx
        
        G = nx.DiGraph()
        G.add_edges_from([(1, 2), (2, 3)])
        
        show_network_animation(G, [1, 2, 3], path_color='red', delay=2)
    """
    visualizer = NetworkGraphVisualizer()
    visualizer.show_animated_path(
        network_graph,
        path,
        hosts_loc=hosts_loc,
        layout=layout,
        layers=layers,
        path_color=path_color,
        delay_before_animation=delay,
        title=title
    )


def visualize_network(
    network_graph: nx.DiGraph,
    hosts_loc: Optional[Dict[str, Tuple[int, int]]] = None,
    layout: str = 'hierarchical',
    layers: Optional[Dict[int, List[int]]] = None,
    title: str = "Network Topology",
    figsize: Tuple[int, int] = (16, 10)
) -> NetworkGraphVisualizer:
    """
    Quickly visualize a network graph.
    
    Args:
        network_graph: NetworkX DiGraph
        hosts_loc: Optional host locations mapping
        layout: Layout algorithm ('hierarchical', 'spring', etc.)
        layers: For hierarchical layout
        title: Plot title
        figsize: Figure size
        
    Returns:
        NetworkGraphVisualizer instance
    """
    visualizer = NetworkGraphVisualizer(figsize=figsize)
    visualizer.draw_graph(network_graph, hosts_loc=hosts_loc, layout=layout,
                         layers=layers, title=title)
    return visualizer


def visualize_network_with_path(
    network_graph: nx.DiGraph,
    path: List[int],
    hosts_loc: Optional[Dict[str, Tuple[int, int]]] = None,
    path_color: str = 'red',
    layout: str = 'hierarchical',
    layers: Optional[Dict[int, List[int]]] = None,
    title: str = "Network Topology",
    figsize: Tuple[int, int] = (16, 10),
    animate: bool = False
) -> NetworkGraphVisualizer:
    """
    Quickly visualize a network graph with a highlighted path.
    
    Args:
        network_graph: NetworkX DiGraph
        path: List of node IDs representing the path
        hosts_loc: Optional host locations mapping
        path_color: Color for the path
        layout: Layout algorithm
        layers: For hierarchical layout
        title: Plot title
        figsize: Figure size
        animate: Whether to animate the path
        
    Returns:
        NetworkGraphVisualizer instance
    """
    visualizer = NetworkGraphVisualizer(figsize=figsize)
    visualizer.draw_graph(network_graph, hosts_loc=hosts_loc, layout=layout,
                         layers=layers, title=title)
    
    if animate:
        visualizer.animate_path(path, color=path_color)
    else:
        visualizer.draw_path(path, color=path_color)
    
    return visualizer


# Example usage
if __name__ == "__main__":
    # Create a sample fat-tree network
    G = nx.DiGraph()
    
    # Core layer (layer 0)
    core_switches = [1, 2]
    
    # Aggregation layer (layer 1)
    agg_switches = [5, 6, 7, 8, 9, 10, 11, 12]
    
    # Access layer (layer 2)
    access_switches = [13, 14, 15, 16, 17, 18, 19, 20]
    
    # Add all switches
    for s in core_switches + agg_switches + access_switches:
        G.add_node(s)
    
    # Add edges
    edges = [
        # Core to aggregation
        (1, 5), (1, 6), (1, 7), (1, 8),
        (2, 9), (2, 10), (2, 11), (2, 12),
        # Aggregation to access
        (5, 13), (5, 14), (6, 15), (6, 16),
        (7, 17), (7, 18), (8, 19), (8, 20),
        (9, 13), (9, 14), (10, 15), (10, 16),
        (11, 17), (11, 18), (12, 19), (12, 20),
    ]
    
    for u, v in edges:
        G.add_edge(u, v, port=1, delay=0.01, avail_bw=10.0)
    
    # Define hierarchical layers
    layers = {
        0: core_switches,
        1: agg_switches,
        2: access_switches
    }
    
    # Create sample host locations
    hosts_loc = {
        '00:00:00:00:00:01': (13, 1),
        '00:00:00:00:00:02': (14, 1),
        '00:00:00:00:00:03': (15, 1),
        '00:00:00:00:00:04': (16, 1),
        '00:00:00:00:00:05': (17, 1),
        '00:00:00:00:00:06': (18, 1),
        '00:00:00:00:00:07': (19, 1),
        '00:00:00:00:00:08': (20, 1),
    }
    
    # ====================
    # EXAMPLE 1: Interactive Animation (EASIEST!)
    # ====================
    # Opens a window, shows the network for 2 seconds, then animates the path
    print("=" * 60)
    print("EXAMPLE 1: Interactive Animation (Open Window Mode)")
    print("=" * 60)
    print("Opening window... Graph displays for 2 seconds, then path animates!")
    print()
    
    show_network_animation(
        G,
        path=[1, 5, 13],
        hosts_loc=hosts_loc,
        layout='hierarchical',
        layers=layers,
        path_color='red',
        delay=2,
        title="Path Animation: Core 1 → Agg 5 → Access 13"
    )
    
    # This will show an interactive window where you can:
    # - Zoom in/out with mouse wheel
    # - Pan by dragging
    # - See the animation loop continuously
    
    print("\nWindow closed! Moving to example 2...")
    
    # ====================
    # EXAMPLE 2: Save to PNG (Static Images)
    # ====================
    print("=" * 60)
    print("EXAMPLE 2: Save Static Images")
    print("=" * 60)
    
    viz2 = NetworkGraphVisualizer(figsize=(16, 10))
    viz2.draw_graph(G, hosts_loc=hosts_loc, layout='hierarchical',
                   layers=layers, title="Static Network with Path")
    viz2.draw_path([2, 9, 14], color='blue', width=3.0)
    viz2.save_figure('draw/network_static_path.png')
    print("Saved: draw/network_static_path.png")
    
    # ====================
    # EXAMPLE 3: Interactive then Save
    # ====================
    print()
    print("=" * 60)
    print("EXAMPLE 3: Manual Control (Draw → Animate → Show)")
    print("=" * 60)
    
    viz3 = NetworkGraphVisualizer(figsize=(16, 10))
    viz3.draw_graph(G, hosts_loc=hosts_loc, layout='hierarchical',
                   layers=layers, title="Another Path")
    viz3.animate_path([1, 6, 14], color='green', interval=400)
    viz3.save_figure('draw/network_manual_control.png')
    print("Saved: draw/network_manual_control.png")
    
    print("\nAll examples completed!")
