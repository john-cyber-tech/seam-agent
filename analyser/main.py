"""
main.py — Seam pipeline orchestrator.

Two entry points:

  Batch mode  (default)
    Runs the full analysis pipeline sequentially, writes graph.html and
    report.json next to the target repo, then exits.

  Live mode   (--live flag)
    Starts a Flask server on port 5050, opens a browser setup page, then
    runs the same pipeline one file at a time while streaming graph updates
    to the browser via Server-Sent Events.  The Claude agent streams its
    migration plan token-by-token into the right-hand panel.

Usage:
    python main.py <path-to-java-repo>
    python main.py <path-to-java-repo> --live
    python main.py --live                       # enter path in the browser
"""

import json
import sys
import time
from pathlib import Path

from parse_java import get_all_classes, parse_file, parse_repo
from build_graph import (
    build_graph,
    compute_metrics,
    cross_cluster_edges,
    get_domain_coupling,
    run_clustering,
)
from visualise import render_graph


# ── Batch mode ────────────────────────────────────────────────────────────────

def main(repo_path: str):
    repo = Path(repo_path).resolve()

    if not repo.exists():
        print(f"Error: path does not exist: {repo}"); sys.exit(1)
    if not repo.is_dir():
        print(f"Error: path is not a directory: {repo}"); sys.exit(1)
    if not list(repo.rglob("*.java")):
        print(f"Error: no .java files found under {repo}"); sys.exit(1)

    print(f"\n{'='*60}\n  Seam\n{'='*60}")
    print(f"  Repo: {repo}\n")

    # ── 1. Parse ───────────────────────────────────────────────────────────────
    print("► Parsing Java files...")
    classes = get_all_classes(str(repo))
    edges   = parse_repo(str(repo))
    print(f"  Found {len(classes)} classes, {len(edges)} raw edges")

    # ── 2. Build graph ─────────────────────────────────────────────────────────
    print("\n► Building knowledge graph...")
    G = build_graph(edges, classes)
    print(f"  Nodes: {G.number_of_nodes()}  Edges: {G.number_of_edges()}")

    # ── 3. Cluster ─────────────────────────────────────────────────────────────
    print("\n► Running Louvain community detection...")
    partition   = run_clustering(G)
    communities = {}
    for node, comm in partition.items():
        communities.setdefault(comm, []).append(node)
    print(f"  Detected {len(communities)} communities")
    for cid, members in sorted(communities.items()):
        print(f"    Community {cid}: {', '.join(sorted(members))}")

    # ── 4. Metrics ─────────────────────────────────────────────────────────────
    print("\n► Computing coupling metrics...")
    metrics = compute_metrics(G)

    print("\n  Top nodes by betweenness centrality (bridges / extraction risk):")
    for name, m in sorted(metrics.items(), key=lambda x: -x[1]["betweenness"])[:8]:
        print(f"    {name:<30} betweenness={m['betweenness']:.4f}  "
              f"in={m['in_degree']}  out={m['out_degree']}")

    print("\n  Most depended-upon classes (high in-degree):")
    for name, m in sorted(metrics.items(), key=lambda x: -x[1]["in_degree"])[:6]:
        print(f"    {name:<30} in-degree={m['in_degree']}")

    # ── 5. Cross-cluster edges ─────────────────────────────────────────────────
    risky = cross_cluster_edges(G, partition)
    print(f"\n► Cross-cluster edges (coupling risk): {len(risky)}")
    for e in risky[:10]:
        print(f"    {e['from']:<22} --{e['relationship']}--> {e['to']}")

    # ── 6. Domain coupling matrix ──────────────────────────────────────────────
    print("\n► Domain-level coupling:")
    coupling = get_domain_coupling(G, classes)
    for pair, count in list(coupling.items())[:10]:
        print(f"    {pair:<35} {count} edges")

    # ── 7. Migration extraction order ─────────────────────────────────────────
    print("\n► Migration extraction order (safest first):")
    recommendations = rank_extraction_order(communities, metrics, G, classes)
    for i, rec in enumerate(recommendations, 1):
        print(f"  {i}. {rec['community_label']:<25} "
              f"internal={rec['internal_edges']}  "
              f"external={rec['external_edges']}  "
              f"risk={rec['risk']}")

    # ── 8. Visualise ───────────────────────────────────────────────────────────
    output_html = str(repo / "graph.html")
    print(f"\n► Rendering interactive graph → {output_html}")
    render_graph(G, partition, metrics, output_html)

    # ── 9. Save JSON report ────────────────────────────────────────────────────
    report = {
        "summary": {
            "classes": len(classes),
            "edges": len(edges),
            "communities": len(communities),
            "cross_cluster_edges": len(risky),
        },
        "communities":         {str(k): v for k, v in communities.items()},
        "metrics":             metrics,
        "cross_cluster_edges": risky[:20],
        "domain_coupling":     coupling,
        "extraction_order":    recommendations,
    }
    report_path = str(repo / "report.json")
    Path(report_path).write_text(json.dumps(report, indent=2))
    print(f"► Report saved → {report_path}")
    print(f"\n{'='*60}\n")


# ── Live mode ─────────────────────────────────────────────────────────────────

def main_live(repo_path: str = None):
    """
    Live-streaming pipeline.

    Runs the same stages as batch mode but processes one file at a time,
    emitting SSE events to the browser after each step so the graph builds
    visually in real time.  The Claude agent streams its plan word-by-word
    into the right-hand panel; when it finishes, a save-plan modal appears
    in the browser.
    """
    from live_server import emit, start_server, wait_for_config

    print(f"\n{'='*60}\n  Seam  [live mode]\n{'='*60}")
    start_server(prefill=repo_path or "")

    folder, api_key = wait_for_config()
    repo       = Path(folder).resolve()
    java_files = list(repo.rglob("*.java"))

    print(f"  Repo : {repo}\n")

    classes    = get_all_classes(str(repo))
    class_meta = {c["name"]: c for c in classes}

    # ── 1. Parse ───────────────────────────────────────────────────────────────
    emit({"type": "stage",  "stage": "parsing"})
    emit({"type": "log",    "message": f"Found {len(java_files)} Java files", "highlight": True})
    emit({"type": "status", "message": f"Parsing {len(java_files)} Java files…"})

    seen_nodes:     set  = set()
    seen_edge_keys: set  = set()
    all_edges:      list = []

    for i, jf in enumerate(sorted(java_files)):
        name = jf.stem
        meta = class_meta.get(name, {"domain": "unknown"})

        emit({"type": "status",   "message": f"Parsing {jf.name}…"})
        emit({"type": "progress", "current": i + 1, "total": len(java_files)})

        if name not in seen_nodes:
            seen_nodes.add(name)
            emit({"type": "add_node", "id": name, "label": name,
                  "domain": meta.get("domain", "unknown"), "node_type": "class"})

        file_edges = parse_file(str(jf), str(repo))

        for edge in file_edges:
            all_edges.append(edge)
            target = edge["target"]

            if target not in seen_nodes:
                seen_nodes.add(target)
                if target.startswith("table:"):
                    emit({"type": "add_node", "id": target,
                          "label": target.replace("table:", "DB:"),
                          "domain": "database", "node_type": "table"})
                else:
                    tmeta = class_meta.get(target, {"domain": "unknown"})
                    emit({"type": "add_node", "id": target, "label": target,
                          "domain": tmeta.get("domain", "unknown"), "node_type": "class"})

            ekey = (edge["source"], target)
            if ekey not in seen_edge_keys:
                seen_edge_keys.add(ekey)
                emit({"type": "add_edge", "from": edge["source"], "to": target,
                      "relationship": edge["relationship"]})

        emit({"type": "file_parsed", "file": jf.name})
        emit({"type": "log", "message": f"Parsed {jf.name} ({len(file_edges)} edges)"})
        time.sleep(4)

    emit({"type": "log", "message": f"Parse complete — {len(all_edges)} raw edges",
          "highlight": True})

    # ── 2. Build graph + cluster ───────────────────────────────────────────────
    emit({"type": "stage",  "stage": "clustering"})
    emit({"type": "status", "message": "Running Louvain community detection…"})

    G         = build_graph(all_edges, classes)
    partition = run_clustering(G)
    communities: dict = {}
    for node, comm in partition.items():
        communities.setdefault(comm, []).append(node)

    emit({"type": "log", "message": f"Detected {len(communities)} communities",
          "highlight": True})

    for node, community in sorted(partition.items(), key=lambda x: x[1]):
        emit({"type": "cluster", "node": node, "community": community})
        time.sleep(0.06)

    # ── 3. Metrics ─────────────────────────────────────────────────────────────
    emit({"type": "stage",  "stage": "metrics"})
    emit({"type": "status", "message": "Computing coupling metrics…"})

    metrics = compute_metrics(G)
    for node, m in metrics.items():
        emit({"type": "metrics", "node": node, **m})
        time.sleep(0.03)

    # ── 4. Cross-cluster edges ─────────────────────────────────────────────────
    risky = cross_cluster_edges(G, partition)
    emit({"type": "log", "message": f"{len(risky)} cross-cluster edges (coupling risk)",
          "highlight": True})
    for e in risky:
        emit({"type": "highlight_cross_edge", "from": e["from"], "to": e["to"]})
        time.sleep(0.03)

    # ── 5. Save outputs ────────────────────────────────────────────────────────
    coupling        = get_domain_coupling(G, classes)
    recommendations = rank_extraction_order(communities, metrics, G, classes)

    output_html = str(repo / "graph.html")
    render_graph(G, partition, metrics, output_html)

    report = {
        "summary": {
            "classes": len(classes), "edges": len(all_edges),
            "communities": len(communities), "cross_cluster_edges": len(risky),
        },
        "communities":         {str(k): v for k, v in communities.items()},
        "metrics":             metrics,
        "cross_cluster_edges": risky[:20],
        "domain_coupling":     coupling,
        "extraction_order":    recommendations,
    }
    report_path = str(repo / "report.json")
    Path(report_path).write_text(json.dumps(report, indent=2))
    emit({"type": "log", "message": f"Report saved → {report_path}"})
    emit({"type": "log", "message": f"Graph  saved → {output_html}"})

    # ── 6. Agent ───────────────────────────────────────────────────────────────
    emit({"type": "stage",  "stage": "agent"})
    emit({"type": "status", "message": "Running Claude agent analysis…"})
    emit({"type": "log",    "message": "Starting AI migration analysis…", "highlight": True})

    try:
        from agent import run_agent
        from live_server import set_pending_plan
        plan = run_agent(
            report_path,
            lambda chunk: emit({"type": "agent_chunk", "text": chunk}),
            api_key=api_key,
        )
        emit({"type": "log", "message": "Agent analysis complete", "highlight": True})
        set_pending_plan(plan)
        emit({"type": "plan_ready", "default_dir": str(repo)})
    except ImportError:
        emit({"type": "agent_chunk", "text": (
            "**anthropic package not installed.**\n\n"
            "Install it with:\n\n```\npip install anthropic\n```"
        )})
    except Exception as ex:
        emit({"type": "agent_chunk", "text": f"**Agent error:** {ex}"})

    emit({"type": "stage",   "stage": "complete"})
    emit({"type": "complete", "message": f"Done — graph at {output_html}"})

    print("\n  Analysis complete. Press Ctrl+C to exit.\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


# ── Shared helpers ────────────────────────────────────────────────────────────

def rank_extraction_order(communities: dict, metrics: dict, G, classes: list) -> list:
    """
    Rank communities from safest to riskiest to extract.

    Scoring heuristic (ascending = safer first):
      primary   — external_edges: fewer cross-boundary edges means fewer contracts
                  to define before the service can stand alone.
      secondary — avg_betweenness: communities whose members are architectural
                  bridges carry higher co-change risk even at equal edge counts.

    Risk bands: LOW ≤ 2 external edges, MEDIUM ≤ 5, HIGH > 5.
    """
    class_to_domain = {c["name"]: c["domain"] for c in classes}
    results = []

    for cid, members in communities.items():
        member_set = set(members)
        internal = sum(1 for u, v in G.edges() if u in member_set and v in member_set)
        external = sum(1 for u, v in G.edges() if (u in member_set) != (v in member_set))
        avg_bc   = (sum(metrics.get(m, {}).get("betweenness", 0) for m in members)
                    / len(members)) if members else 0

        domain_counts: dict = {}
        for m in members:
            d = class_to_domain.get(m, "unknown")
            domain_counts[d] = domain_counts.get(d, 0) + 1
        dominant = max(domain_counts, key=domain_counts.get)

        results.append({
            "community_id":    cid,
            "community_label": dominant,
            "members":         members,
            "internal_edges":  internal,
            "external_edges":  external,
            "avg_betweenness": round(avg_bc, 4),
            "risk":            "LOW" if external <= 2 else ("MEDIUM" if external <= 5 else "HIGH"),
        })

    return sorted(results, key=lambda x: (x["external_edges"], x["avg_betweenness"]))


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    positional = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags      = {a for a in sys.argv[1:] if a.startswith("--")}

    if "--live" in flags:
        main_live(positional[0] if positional else None)
    elif not positional:
        print("Usage: python main.py <path-to-java-repo> [--live]")
        print("  --live    stream live graph visualisation in browser")
        sys.exit(1)
    else:
        main(positional[0])
