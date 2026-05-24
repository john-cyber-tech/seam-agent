"""System prompt and static context are ephemeral-cached; only the dynamic report JSON is billed on repeat runs (~85% cost reduction)."""

import os
import sys
from pathlib import Path

import anthropic


def _load_env_file():
    env_path = Path(__file__).resolve().parent.parent / '.env'
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, val = line.partition('=')
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

_load_env_file()

# ── System prompt ─────────────────────────────────────────────────────────────
_SYSTEM = """\
You are an expert software architect specialising in monolith-to-microservices \
migration using the strangler-fig pattern.

You will receive a knowledge-graph analysis report produced by a static-analysis \
tool that parsed a Java codebase, built a dependency graph, and ran Louvain \
community detection. Each community is a candidate microservice boundary.

Produce a structured migration plan with exactly these five sections:

## 0. Codebase Overview
A single paragraph (4–6 sentences) written for a reader who has never seen this \
codebase. Describe what the application does as a product, then explain how it is \
architected at a high level: the main functional domains, how they relate to each \
other, and what data the system manages. Do not mention communities, clusters, or \
graph metrics — write this as a plain architectural summary derived from the class \
names and dependencies in the report.

## 1. Proposed Microservices
For each detected community list:
- A meaningful service name (not "Community 0")
- One-sentence purpose
- Key classes
- Extraction difficulty: LOW / MEDIUM / HIGH with a one-line reason

## 2. Strangler Fig Migration Plan
A numbered, ordered step-by-step plan. Each step must state:
- Which service to extract
- What must be done (deploy alongside monolith, add anti-corruption layer, \
route traffic, cut over, retire monolith code)
- Why this step comes at this position in the sequence

## 3. Cross-Cluster Edge Classification
For every cross-cluster edge in the report decide:
- **REST API** — synchronous, caller needs an immediate response
- **Async event / message queue** — fire-and-forget or eventual consistency is fine
- **Shared library** — utility with no business logic, safe to keep shared

Give one-line rationale per decision. Present as a markdown table with columns: \
From | To | Type | Rationale

## 4. Risk Summary
Top 3 architectural risks with one concrete mitigation each.

Be concise and precise. Use markdown formatting throughout.\
"""

# ── Static context block ──────────────────────────────────────────────────────
_STATIC_CONTEXT = """\
The report below was produced by static analysis of a Java monolith. \
The tool extracted import statements, instantiation calls (new Foo()), and \
SQL table references, then built a directed dependency graph and ran Louvain \
community detection on its undirected projection. Communities represent \
cohesive groups of classes with dense internal dependencies and sparse \
external ones — natural microservice boundaries.\
"""


def save_plan_interactive(plan_text: str, default_dir: str = ".") -> Path:
    """Falls back to defaults silently when stdin is not a TTY."""
    print("\n► Migration plan ready. Where would you like to save it?")

    try:
        raw_name = input("  Filename [migration_plan.md]: ").strip()
        filename = raw_name or "migration_plan.md"
        if not filename.endswith(".md"):
            filename += ".md"

        raw_dir = input(f"  Directory [{default_dir}]: ").strip()
        directory = raw_dir or default_dir
    except EOFError:
        filename = "migration_plan.md"
        directory = default_dir
        print("  (no terminal input available — using defaults)")

    out_path = Path(directory).expanduser().resolve() / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(plan_text)
    print(f"  Saved → {out_path}")
    return out_path


def run_agent(report_path: str, chunk_callback=None, api_key: str = None) -> str:
    """Stream a migration plan from Claude; chunk_callback receives each token as it arrives."""
    report_text = Path(report_path).read_text()
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    full_text = ""
    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=8192,
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": _STATIC_CONTEXT,
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": (
                            f"Here is the full analysis report:\n\n"
                            f"```json\n{report_text}\n```\n\n"
                            f"Please produce the migration plan."
                        ),
                    },
                ],
            }
        ],
    ) as stream:
        for chunk in stream.text_stream:
            full_text += chunk
            if chunk_callback:
                chunk_callback(chunk)

    return full_text


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python agent.py <path-to-report.json>")
        sys.exit(1)

    def _print_chunk(text: str):
        print(text, end="", flush=True)

    report_dir = str(Path(sys.argv[1]).parent)
    result = run_agent(sys.argv[1], _print_chunk)
    print()
    save_plan_interactive(result, default_dir=report_dir)
