# Seam

**Seam** is a local static analysis tool that maps the dependency structure of a Java monolith, detects natural service boundaries using community detection, and streams a full strangler-fig migration plan powered by Claude.

No cloud infrastructure required. Everything runs on your machine.

---

## What it does

1. **Parses** your Java source — imports, instantiations, and SQL table references.
2. **Builds a knowledge graph** — classes and DB tables as nodes, dependencies as directed edges.
3. **Detects communities** — runs the Louvain algorithm on the graph to surface cohesive groups of classes that are natural microservice boundaries.
4. **Scores extraction risk** — betweenness centrality, in/out degree, and cross-cluster edge count for every class.
5. **Visualises** — produces an interactive force-directed HTML graph you can open in any browser.
6. **Plans the migration** — a Claude agent reads the analysis report and streams a structured four-section plan: named microservices, strangler-fig steps, edge-by-edge API classification, and architectural risks.

---

## Modes

### Batch mode

Runs the full pipeline end-to-end and exits.

```bash
cd analyser
python main.py ../path/to/your/java-repo
```

Outputs written alongside the repo:
- `graph.html` — interactive dependency graph
- `report.json` — structured analysis: communities, metrics, cross-cluster edges, extraction order

### Live mode

Streams the analysis in real time to a browser UI.

```bash
cd analyser
python main.py --live                        # enter the repo path in the browser
python main.py ../path/to/your/java-repo --live   # pre-fills the path field
```

Opens `http://localhost:5050` with a setup page. Enter the repo path and your Anthropic API key, then click **Start Analysis**. The graph builds file-by-file; communities are coloured as they are detected; the Claude agent streams its plan into the right-hand panel. When the agent finishes, a **Save Migration Plan** modal appears in the browser.

### Agent-only mode

Re-run the agent against an existing report without re-parsing the codebase — useful when iterating on the prompt.

```bash
cd analyser
python agent.py ../path/to/your/java-repo/report.json
```

Streams the migration plan to stdout, then prompts for a filename and directory to save it as a markdown file.

---

## Installation

```bash
pip install javalang networkx python-louvain pyvis flask anthropic
```

On a system-managed Python (Homebrew / Linux):

```bash
pip install javalang networkx python-louvain pyvis flask anthropic --break-system-packages
```

`flask` is only required for live mode. `anthropic` is only required for the agent.

### Anthropic API key

The agent needs access to Claude. Supply the key in one of two ways:

1. Enter it in the **API key** field on the live-mode setup page (held in memory only, never written to disk).
2. Set the `ANTHROPIC_API_KEY` environment variable.

---

## Architecture

```
analyser/
├── main.py          Orchestrator — batch and live pipeline entry point
├── parse_java.py    Static analyser — imports, instantiations, SQL table refs
├── build_graph.py   Graph construction, Louvain clustering, coupling metrics
├── visualise.py     PyVis renderer — static graph.html output
├── agent.py         Claude integration — streaming migration plan
└── live_server.py   Flask + SSE server — real-time browser visualisation
```

### Pipeline stages

| Stage | Module | Description |
|---|---|---|
| Parse | `parse_java.py` | Regex extraction of three dependency types per file |
| Build graph | `build_graph.py` | NetworkX `DiGraph`; nodes = classes + DB tables |
| Cluster | `build_graph.py` | Louvain on undirected projection → community IDs |
| Metrics | `build_graph.py` | Betweenness centrality, in/out degree per class |
| Cross-cluster edges | `build_graph.py` | Edges that cross community boundaries = future API surface |
| Rank | `main.py` | Order communities by external edges + avg betweenness |
| Visualise | `visualise.py` | PyVis force-directed graph → self-contained HTML |
| Agent | `agent.py` | Claude streams four-section migration plan |

### Live mode architecture

```
Browser (vis.js + marked.js)
        ↑  SSE  /events
Flask (live_server.py, port 5050)
        ↑  emit()
Analysis thread (main.py → main_live())
```

The Flask server runs in a background daemon thread. The analysis runs on the main thread and pushes JSON events into a per-subscriber `queue.Queue`. The browser connects to `/events` and receives a stream of `text/event-stream` messages — one per graph update, cluster assignment, metric update, or agent token.

SSE was chosen over WebSockets because the communication is strictly one-directional (server → browser) and SSE works over plain HTTP with no extra library beyond Flask.

---

## Output files

### `graph.html`

A self-contained interactive graph rendered by PyVis (vis.js under the hood). Open in any browser — no server needed.

Visual encoding:
- **Node colour** → Louvain community (one colour per candidate microservice)
- **Node size** → total degree; larger = more coupled = higher extraction risk
- **Diamond shape** → DB table node
- **Red edges** → `accesses_table` (shared data = tight coupling)
- **Grey edges** → `imports` / `instantiates` relationships

### `report.json`

Structured JSON with five top-level keys:

```json
{
  "summary":             { "classes", "edges", "communities", "cross_cluster_edges" },
  "communities":         { "0": ["ClassName", ...], ... },
  "metrics":             { "ClassName": { "betweenness", "in_degree", "out_degree", "total_degree" } },
  "cross_cluster_edges": [ { "from", "to", "from_community", "to_community", "relationship" } ],
  "domain_coupling":     { "order → payment": 3, ... },
  "extraction_order":    [ { "community_label", "members", "internal_edges", "external_edges", "risk" } ]
}
```

### `migration_plan.md`

The Claude agent's output saved as markdown. Contains:
1. **Proposed Microservices** — named service per community, purpose, key classes, extraction difficulty (LOW / MEDIUM / HIGH)
2. **Strangler Fig Migration Plan** — ordered numbered steps with rationale
3. **Cross-Cluster Edge Classification** — table mapping each coupling point to REST API / async event / shared library
4. **Risk Summary** — top 3 architectural risks with concrete mitigations

---

## The AI agent

The agent is a single streaming call to `claude-opus-4-7` — it does not use tool use or multi-turn agentic loops. The system prompt and a static context block describing the analysis methodology are both marked `cache_control: ephemeral`, so repeated runs against the same report only bill for the dynamic report JSON (~85% token cost reduction on repeat runs).

---

## Design decisions

**No database required.** The graph lives in memory as a NetworkX object. Neptune or Neo4j can be added later if the codebase grows large enough to need persistence.

**Regex over full AST for SQL.** `javalang` does not parse string contents, so SQL table names are found via regex on raw source. Sufficient for boundary detection.

**Louvain over Girvan-Newman.** Fast and parameter-free; produces stable results on graphs of this size. Girvan-Newman is more theoretically principled but is too slow for interactive use.

**Filtering stdlib nodes.** `RuntimeException`, `List`, `InternetAddress`, etc. are excluded from clustering because they do not represent architectural boundaries.

**Import filter is hardcoded to `com.ecommerce`.** To analyse a different codebase, update the prefix check in `parse_java.py → _parse_file` to match your root package.

---

## Limitations

- Import filtering requires a manual update to match your package prefix (see above).
- SQL extraction is regex-based and will miss dynamically constructed queries.
- Louvain results are non-deterministic; re-running on the same codebase may produce slightly different community assignments. Run a few times and take the most stable grouping.
- The agent plan is only as good as the static analysis — dynamic dispatch, reflection, and runtime dependency injection are invisible to the parser.

---

## License

MIT
