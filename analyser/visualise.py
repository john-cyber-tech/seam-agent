"""
visualise.py — Interactive graph renderer using PyVis.

Produces a self-contained HTML file with a vis.js force-directed graph.
Visual encoding:
  - Node colour   → Louvain community (candidate microservice boundary)
  - Node size     → total degree × 3 + 14 baseline; highly-connected classes
                    appear larger and are immediately visible as coupling hotspots
  - Diamond shape → DB table nodes (distinct from class nodes)
  - Red edges     → accesses_table relationships (shared data = tight coupling)
  - Grey edges    → imports / instantiates relationships
"""

import json
from pyvis.network import Network


# Community palette — up to 8 distinct clusters before cycling
COMMUNITY_PALETTE = [
    "#534AB7", "#D85A30", "#0F6E56", "#BA7517",
    "#993556", "#185FA5", "#639922", "#A32D2D",
]


def render_graph(G, partition: dict, metrics: dict, output_path: str):
    """
    Render *G* to an interactive HTML file at *output_path*.

    Args:
        G:           NetworkX DiGraph produced by build_graph.
        partition:   Node → community-id mapping from run_clustering.
        metrics:     Node → {betweenness, in_degree, out_degree, total_degree}.
        output_path: Destination path for the .html file.
    """
    net = Network(height="700px", width="100%", bgcolor="#1a1a1a",
                  font_color="white", directed=True)
    net.barnes_hut(gravity=-8000, central_gravity=0.3, spring_length=120)

    for node in G.nodes():
        node_data  = G.nodes[node]
        node_type  = node_data.get("node_type", "class")
        community  = partition.get(node, -1)
        m          = metrics.get(node, {})

        if node_type == "table":
            color = "#3d3d3a"
            size  = 10
            shape = "diamond"
            label = node.replace("table:", "DB: ")
        else:
            color = COMMUNITY_PALETTE[community % len(COMMUNITY_PALETTE)] if community >= 0 else "#555"
            size  = 14 + m.get("total_degree", 0) * 3
            shape = "dot"
            label = node

        net.add_node(
            node, label=label, color=color, size=size, shape=shape,
            font={"size": 12, "color": "white"},
            title=(
                f"<b>{node}</b><br>"
                f"Domain: {node_data.get('domain', 'unknown')}<br>"
                f"Community: {community}<br>"
                f"In-degree: {m.get('in_degree', 0)}<br>"
                f"Out-degree: {m.get('out_degree', 0)}<br>"
                f"Betweenness: {m.get('betweenness', 0)}"
            ),
        )

    for src, dst, data in G.edges(data=True):
        rel = data.get("relationship", "")
        net.add_edge(src, dst, title=rel, arrows="to",
                     color="#ff6b6b" if rel == "accesses_table" else "#666",
                     width=2 if rel == "instantiates" else 1)

    net.set_options(json.dumps({
        "physics": {
            "enabled": True,
            "barnesHut": {"gravitationalConstant": -8000,
                          "centralGravity": 0.3, "springLength": 120},
        },
        "interaction": {"hover": True, "tooltipDelay": 100},
        "edges":       {"smooth": {"type": "dynamic"}},
    }))

    net.save_graph(output_path)
    print(f"Graph saved to: {output_path}")
