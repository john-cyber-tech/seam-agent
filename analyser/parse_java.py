"""
parse_java.py — Static dependency extractor for Java codebases.

Produces a flat list of directed edges  { source, target, relationship, source_file }
by applying three extraction strategies to each .java file:

  1. Import edges      — project-internal `import` statements only; stdlib imports
                         are filtered out to avoid polluting the graph with noise nodes
                         like RuntimeException or List that carry no architectural signal.

  2. Instantiation edges — `new Foo(...)` call-sites; catches runtime dependencies that
                           imports alone miss (e.g. when a class is only referenced via
                           a factory and never imported directly).

  3. Table access edges  — SQL keyword regex on string literals (FROM / INTO / UPDATE /
                           JOIN).  javalang does not parse string contents, so a full AST
                           approach cannot find table names.  Regex is good enough here
                           because the goal is boundary detection, not query validation.

NOTE: Import filtering currently matches the `com.ecommerce` prefix.  To analyse a
different codebase, update the prefix check in `_parse_file` to match your root package.
"""

import re
from pathlib import Path


def parse_repo(root: str) -> list[dict]:
    """Walk every .java file under *root* and return all dependency edges."""
    edges = []
    for f in Path(root).rglob("*.java"):
        edges.extend(_parse_file(f, root))
    return edges


def parse_file(path: str, root: str) -> list[dict]:
    """Parse a single .java file; public wrapper used by live mode."""
    return _parse_file(Path(path), root)


def _parse_file(path: Path, root: str) -> list[dict]:
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    source_class = path.stem
    edges = []

    # ── 1. Import edges ───────────────────────────────────────────────────────
    # Only follow imports that belong to the project's own package tree so that
    # JDK / third-party classes do not appear as graph nodes.
    for imp in re.findall(r"^\s*import\s+([\w.]+)\s*;", src, re.MULTILINE):
        if imp.startswith("com.ecommerce"):
            edges.append({
                "source": source_class,
                "target": imp.split(".")[-1],
                "relationship": "imports",
                "source_file": str(path.relative_to(root)),
            })

    # ── 2. Instantiation edges ────────────────────────────────────────────────
    # Regex matches `new ClassName(` — PascalCase guard avoids false positives
    # on primitive array allocations like `new int[`.
    for inst in re.findall(r"\bnew\s+([A-Z][A-Za-z0-9_]+)\s*\(", src):
        if inst != source_class:
            edges.append({
                "source": source_class,
                "target": inst,
                "relationship": "instantiates",
                "source_file": str(path.relative_to(root)),
            })

    # ── 3. Table access edges ─────────────────────────────────────────────────
    for table in re.findall(r"(?:FROM|INTO|UPDATE|JOIN)\s+([a-z_]+)", src, re.IGNORECASE):
        edges.append({
            "source": source_class,
            "target": f"table:{table.lower()}",
            "relationship": "accesses_table",
            "source_file": str(path.relative_to(root)),
        })

    return edges


def get_all_classes(root: str) -> list[dict]:
    """
    Return a metadata record for every Java class in the repo.

    Domain is inferred from the third package segment (e.g. `com.ecommerce.order`
    → `order`).  Classes whose package has fewer than three segments are tagged
    `unknown` and excluded from Louvain clustering.
    """
    classes = []
    for f in Path(root).rglob("*.java"):
        src = f.read_text(encoding="utf-8", errors="ignore")
        pkg_match = re.search(r"^\s*package\s+([\w.]+)\s*;", src, re.MULTILINE)
        package = pkg_match.group(1) if pkg_match else ""
        parts = package.split(".")
        domain = parts[2] if len(parts) >= 3 else "unknown"
        classes.append({
            "name": f.stem,
            "package": package,
            "domain": domain,
            "file": str(f.relative_to(root)),
        })
    return classes
