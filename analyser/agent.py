"""
agent.py — AI migration planner powered by Claude.

Reads the JSON report produced by the analysis pipeline and streams a structured
four-section migration plan using claude-opus-4-7.

Prompt-caching strategy
-----------------------
Two cache breakpoints are set with `cache_control: ephemeral`:

  1. The system prompt  — role definition and output schema.  Stable across all
     runs; cached on the first call and reused for ~5 minutes.

  2. The static context block — explanation of the analysis methodology, sent as
     the first content block of the user turn.  Also stable; cached alongside
     the system prompt.

Only the dynamic report JSON (the third block) is billed as input tokens on
repeat runs against the same report, reducing input cost by ~85 %.

Usage:
    python agent.py <path-to-report.json>
"""

import sys
from pathlib import Path

import anthropic

# ── System prompt ─────────────────────────────────────────────────────────────
# Sent with cache_control so it is cached on the first request and reused for
# all subsequent calls within the 5-minute TTL.
_SYSTEM = """\
You are an expert software architect specialising in monolith-to-microservices \
migration using the strangler-fig pattern.

You will receive a knowledge-graph analysis report produced by a static-analysis \
tool that parsed a Java codebase, built a dependency graph, and ran Louvain \
community detection. Each community is a candidate microservice boundary.

Produce a structured migration plan with exactly these four sections:

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
# Describes the analysis methodology; never changes between runs, so cached
# as the first user-turn content block alongside the system prompt.
_STATIC_CONTEXT = """\
The report below was produced by static analysis of a Java monolith. \
The tool extracted import statements, instantiation calls (new Foo()), and \
SQL table references, then built a directed dependency graph and ran Louvain \
community detection on its undirected projection. Communities represent \
cohesive groups of classes with dense internal dependencies and sparse \
external ones — natural microservice boundaries.\
"""


def save_plan_interactive(plan_text: str, default_dir: str = ".") -> Path:
    """
    Prompt for a filename and directory, then write the migration plan as a
    markdown file.

    Falls back to defaults silently when stdin is not a TTY (e.g. when the
    process is launched as a background task without an attached terminal).
    """
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
    """
    Load report.json, stream a migration plan from Claude, and return the full text.

    Args:
        report_path:    Path to the report.json file produced by the pipeline.
        chunk_callback: Optional callable invoked with each streamed text chunk.
                        Used by live mode to forward tokens to the browser via SSE.
        api_key:        Anthropic API key.  If None, falls back to the
                        ANTHROPIC_API_KEY environment variable.

    Returns:
        The complete migration plan as a markdown string.
    """
    report_text = Path(report_path).read_text()
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    full_text = ""
    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=4096,
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
