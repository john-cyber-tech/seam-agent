# Java Monolith Knowledge Graph Agent

## What this project does

This is a local static analysis tool that parses a Java codebase, builds a knowledge graph of its dependencies, detects natural service boundaries using community detection, and outputs an interactive visualisation plus a structured report. A Claude-powered agent then reads the report and streams a full migration plan. The goal is to support monolith-to-microservices migration planning without any cloud infrastructure.

## Directory layout

The analyser and the monolith can live anywhere on your machine. The expected structure is:

```
<wherever you put it>/
├── CLAUDE.md                  ← you are here
├── analyser/
│   ├── main.py                ← entry point, orchestrates the full pipeline (batch + live)
│   ├── parse_java.py          ← static analysis: extracts imports, instantiations, SQL table access
│   ├── build_graph.py         ← NetworkX graph construction, Louvain clustering, coupling metrics
│   ├── visualise.py           ← PyVis interactive HTML graph renderer (static output)
│   ├── agent.py               ← Claude reasoning layer: reads report.json, streams migration plan
│   └── live_server.py         ← Flask + SSE server: real-time browser graph visualisation
└── java-monolith/             ← synthetic Java monolith used as test dataset
    └── src/main/java/com/ecommerce/
        ├── Application.java
        ├── user/              ← UserService, UserRepository, AuthService
        ├── order/             ← OrderService, OrderRepository, Order, OrderItem
        ├── payment/           ← PaymentService, PaymentRecord
        ├── inventory/         ← InventoryService, Product
        ├── notification/      ← NotificationService, NotificationRepository, Notification
        ├── reporting/         ← ReportingService, SalesReport
        └── shared/            ← DatabaseConnection, Logger, DateUtils, EmailSender, User (model)
```

## How to run

### Batch mode (original behaviour)

Navigate to the `analyser/` folder and pass the path to any Java repo:

```bash
cd analyser
python main.py ../java-monolith
```

Outputs are written alongside the repo being analysed:
- `<repo>/graph.html` — interactive dependency graph, open in any browser
- `<repo>/report.json` — structured JSON with communities, metrics, cross-cluster edges, and migration order

### Live mode (real-time browser visualisation + agent)

```bash
cd analyser
python main.py --live                    # no path — enter it in the browser
python main.py ../java-monolith --live   # pre-fills the folder field
```

Opens a browser at `http://localhost:5050` showing a **setup page** with two fields:

- **Monolith source folder** — path to any Java repo; pre-filled from the CLI arg if one was given. Validated server-side (must exist and contain `.java` files) before analysis begins.
- **Anthropic API key** — optional password field. Held in memory for the duration of the run only; never written to disk, logs, or any HTTP response body. If left blank the agent falls back to the `ANTHROPIC_API_KEY` environment variable.

Clicking **Start Analysis** (or pressing Enter) validates the inputs, then redirects to `/graph` where the live visualisation begins: the graph builds file-by-file, communities are coloured one-by-one, node sizes update with coupling weight, cross-cluster edges are highlighted in red, and the Claude agent streams its migration plan into the right-hand panel. The same output files are written at the end.

### Agent only (run against an existing report)

```bash
cd analyser
python agent.py ../java-monolith/report.json
```

Streams the migration plan to stdout. Useful for re-running the agent after tweaking the prompt without re-parsing the codebase.

## Dependencies

Install once before first run:

```bash
pip install javalang networkx python-louvain pyvis flask anthropic
```

If you're on a system-managed Python (e.g. Linux/Mac with Homebrew), add `--break-system-packages`:

```bash
pip install javalang networkx python-louvain pyvis flask anthropic --break-system-packages
```

`flask` and `anthropic` are only required for live mode and the agent respectively. Batch mode works without them.

The Anthropic API key can be supplied in two ways (in order of precedence):
1. Entered into the API key field on the setup page (ephemeral, in-memory only)
2. Set as the `ANTHROPIC_API_KEY` environment variable

## Pipeline stages

### Batch mode

1. **Parse** (`parse_java.py`) — walks all `.java` files, extracts:
   - `import` statements that reference project packages
   - `new Foo()` instantiation calls
   - SQL table references via regex on string literals (`FROM`, `INTO`, `UPDATE`, `JOIN`)

2. **Build graph** (`build_graph.py`) — constructs a `networkx.DiGraph` where:
   - Nodes = Java classes + DB tables
   - Edges = `imports`, `instantiates`, `accesses_table` relationships
   - Filters out stdlib noise (only nodes with a known project domain are clustered)

3. **Cluster** (`build_graph.py → run_clustering`) — runs Louvain community detection on the undirected projection of the graph. Each community is a candidate microservice boundary.

4. **Metrics** (`build_graph.py → compute_metrics`) — computes per-node:
   - Betweenness centrality (bridge risk — high = dangerous to extract early)
   - In-degree (how many classes depend on this one)
   - Out-degree (how many classes this one depends on)

5. **Cross-cluster edges** — edges that cross community boundaries; these are the coupling points that need to become API calls or events in a microservices world.

6. **Migration ranking** (`main.py → rank_extraction_order`) — ranks communities by `external_edges` ascending. Fewer external edges = safer to extract first.

7. **Visualise** (`visualise.py`) — renders a PyVis force-directed graph:
   - Node colour = community (cluster)
   - Node size = total degree (bigger = more connected)
   - Diamond shape = DB table node
   - Red edges = table access; grey = class dependency

8. **Agent** (`agent.py`) — calls `claude-opus-4-7` with streaming. Prompt caching is applied to the system prompt and static context block. Produces four sections:
   - Named microservices (one per community) with extraction difficulty rating
   - Strangler-fig migration plan (ordered steps with rationale)
   - Cross-cluster edge classification: REST API / async event / shared library
   - Top 3 architectural risks with mitigations

### Live mode additions

Live mode runs the same logical stages but processes **one file at a time**, emitting SSE events to the browser after each step:

- Files parse sequentially (150 ms delay each) — nodes and edges appear as they are discovered
- After all files: Louvain clustering runs, then each node is recoloured by community (60 ms each)
- Metrics update node sizes (30 ms each)
- Cross-cluster edges are highlighted red/dashed (30 ms each)
- Agent streams its plan word-by-word into the right-hand panel via marked.js (renders markdown)

The live server (`live_server.py`) is a Flask app on port 5050 with three routes:
- `GET /` — setup page (folder picker + API key field)
- `GET /graph` — live visualisation page (redirects to `/` if setup not completed)
- `POST /start` — receives and validates the folder path and API key, signals the analysis thread to begin
- `GET /events` — SSE stream

All HTML is embedded in the Python file — no separate static assets needed.

## Last analysis results (on the synthetic monolith)

- **22 classes**, **70 graph edges**, **4 communities** detected
- Communities found:
  - Community 0: `DatabaseConnection`, `PaymentService`, `InventoryService`, `ReportingService` — infrastructure + data-heavy
  - Community 1: `AuthService`, `UserService`, `UserRepository`, `Logger`, `User` — user/auth domain
  - Community 2: `NotificationService`, `NotificationRepository`, `EmailSender`, `Notification` — notification domain
  - Community 3: `OrderService`, `OrderRepository`, `Order`, `OrderItem` — order domain
- **20 cross-cluster edges** identified as coupling risk
- Highest betweenness: `NotificationService` (0.0272) — bridges user, order, and notification
- Highest in-degree: `Logger` (11) — legitimate shared utility, not a coupling problem
- Most coupled class: `OrderService` (out-degree 8) — hardest to extract

## Design decisions

- **No database required** — the graph lives in memory as a NetworkX object. Neptune or Neo4j can be added later if the codebase grows large.
- **Regex over full AST** for SQL extraction — javalang does not parse string contents, so SQL table names are found via regex on raw source. Good enough for a research prototype.
- **Louvain over other algorithms** — fast, parameter-free, and produces stable results on graphs of this size. Girvan-Newman would be more principled but is too slow for interactive use.
- **Filtering stdlib nodes** — `RuntimeException`, `InternetAddress`, etc. are excluded from clustering since they don't represent architectural boundaries.
- **SSE over WebSockets** for live mode — one-directional server-to-client streaming is all that's needed; SSE works over plain HTTP with no extra library beyond Flask.
- **Embedded HTML** in `live_server.py` — keeps the tool self-contained with no static file path concerns.
- **Prompt caching** in `agent.py` — the system prompt and static context are marked `cache_control: ephemeral` so repeated runs against the same report only pay for the dynamic report tokens.
- **Streaming agent output** — `claude-opus-4-7` streams tokens as they are generated; the frontend renders them incrementally via marked.js so the user sees the plan build in real time.
- **Ephemeral API key** — the key entered on the setup page is stored in a single module-level variable (`_pending_api_key`), cleared to `None` immediately after it is passed to the agent, and never serialised anywhere. If the field is left blank the SDK falls back to the environment variable.
