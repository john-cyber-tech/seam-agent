
import networkx as nx
import community as community_louvain
from collections import defaultdict


def build_graph(edges: list[dict], classes: list[dict]) -> nx.DiGraph:
    """Edge key includes relationship — a class can both import and instantiate the same target."""
    G = nx.DiGraph()
    class_meta = {c["name"]: c for c in classes}

    for cls in classes:
        G.add_node(cls["name"], domain=cls["domain"], package=cls["package"],
                   file=cls["file"], node_type="class")

    table_nodes: set = set()
    for edge in edges:
        if edge["target"].startswith("table:") and edge["target"] not in table_nodes:
            G.add_node(edge["target"], domain="database", node_type="table")
            table_nodes.add(edge["target"])

    seen: set = set()
    for edge in edges:
        key = (edge["source"], edge["target"], edge["relationship"])
        if key not in seen:
            seen.add(key)
            if G.has_node(edge["source"]) or edge["source"] in class_meta:
                if not G.has_node(edge["source"]):
                    G.add_node(edge["source"], domain="unknown", node_type="class")
                G.add_edge(edge["source"], edge["target"],
                           relationship=edge["relationship"])

    return G


def run_clustering(G: nx.DiGraph) -> dict[str, int]:
    U = G.to_undirected()
    # exclude DB tables and stdlib nodes; they'd blur service boundaries
    project_nodes = [
        n for n in U.nodes()
        if G.nodes[n].get("node_type") == "class"
        and G.nodes[n].get("domain") not in ("unknown", "")
    ]
    U_filtered = U.subgraph(project_nodes).copy()
    U_filtered.remove_nodes_from(list(nx.isolates(U_filtered)))  # python-louvain errors on isolates
    return community_louvain.best_partition(U_filtered)


def compute_metrics(G: nx.DiGraph) -> dict:
    try:
        betweenness = nx.betweenness_centrality(G, normalized=True)
    except Exception:
        betweenness = {}

    in_degree  = dict(G.in_degree())
    out_degree = dict(G.out_degree())

    return {
        node: {
            "betweenness":  round(betweenness.get(node, 0), 4),
            "in_degree":    in_degree.get(node, 0),
            "out_degree":   out_degree.get(node, 0),
            "total_degree": in_degree.get(node, 0) + out_degree.get(node, 0),
        }
        for node in G.nodes()
        if G.nodes[node].get("node_type") == "class"
    }


def cross_cluster_edges(G: nx.DiGraph, partition: dict[str, int]) -> list[dict]:
    return [
        {
            "from": src, "to": dst,
            "from_community": partition[src],
            "to_community":   partition[dst],
            "relationship":   G[src][dst].get("relationship", ""),
        }
        for src, dst in G.edges()
        if partition.get(src) is not None
        and partition.get(dst) is not None
        and partition[src] != partition[dst]
    ]


def get_domain_coupling(G: nx.DiGraph, classes: list[dict]) -> dict:
    """Aggregate cross-domain edge counts for the domain-level coupling matrix."""
    class_to_domain = {c["name"]: c["domain"] for c in classes}
    coupling: dict = defaultdict(int)

    for src, dst in G.edges():
        src_d = class_to_domain.get(src, "unknown")
        dst_d = class_to_domain.get(dst, "unknown")
        if src_d != dst_d and not dst.startswith("table:"):
            coupling[f"{src_d} → {dst_d}"] += 1

    return dict(sorted(coupling.items(), key=lambda x: -x[1]))
