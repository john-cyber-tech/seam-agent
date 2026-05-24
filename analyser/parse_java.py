"""Import filter is hardcoded to com.ecommerce; update _parse_file for other codebases."""

import re
from pathlib import Path


def parse_repo(root: str) -> list[dict]:
    edges = []
    for f in Path(root).rglob("*.java"):
        edges.extend(_parse_file(f, root))
    return edges


def parse_file(path: str, root: str) -> list[dict]:
    return _parse_file(Path(path), root)


def _parse_file(path: Path, root: str) -> list[dict]:
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    source_class = path.stem
    edges = []

    # ── 1. Import edges ───────────────────────────────────────────────────────
    # only project imports; stdlib adds noise nodes with no architectural signal
    for imp in re.findall(r"^\s*import\s+([\w.]+)\s*;", src, re.MULTILINE):
        if imp.startswith("com.ecommerce"):
            edges.append({
                "source": source_class,
                "target": imp.split(".")[-1],
                "relationship": "imports",
                "source_file": str(path.relative_to(root)),
            })

    # ── 2. Instantiation edges ────────────────────────────────────────────────
    # PascalCase guard prevents false positives on primitive allocations like new int[
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
