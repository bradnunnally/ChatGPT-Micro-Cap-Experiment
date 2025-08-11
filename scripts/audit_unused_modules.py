from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple

from infra.logging import get_logger, new_correlation_id

IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".vscode",
    "build",
    "dist",
}

DEFAULT_APP_ENTRY_FILES = ["app.py", "main.py", "streamlit_app.py", "run.py", "cli/main.py"]


@dataclass(frozen=True)
class ModuleInfo:
    name: str
    path: Path
    imports: Set[str]
    has_main_guard: bool
    is_test: bool
    is_script: bool
    is_package_init: bool
    is_page: bool


def rel_module_name(root: Path, file: Path) -> str:
    rel = file.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def parse_py_file(py_file: Path) -> Tuple[Set[str], bool]:
    imports: Set[str] = set()
    has_main_guard = False
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    except Exception:
        return imports, has_main_guard
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
        elif isinstance(node, ast.If):
            try:
                test = node.test
                if isinstance(test, ast.Compare):
                    left = getattr(test, "left", None)
                    comps = getattr(test, "comparators", [])
                    if (
                        isinstance(left, ast.Name)
                        and left.id == "__name__"
                        and comps
                        and isinstance(comps[0], (ast.Str, ast.Constant))
                        and (
                            getattr(comps[0], "s", None) == "__main__"
                            or getattr(comps[0], "value", None) == "__main__"
                        )
                    ):
                        has_main_guard = True
            except Exception:
                pass
    return imports, has_main_guard


def collect_modules(root: Path) -> Dict[str, ModuleInfo]:
    modules: Dict[str, ModuleInfo] = {}
    for path in root.rglob("*.py"):
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        name = rel_module_name(root, path)
        if not name:
            continue
        imports, has_main = parse_py_file(path)
        is_test = (
            "tests" in path.parts or path.name.startswith("test_") or path.name.endswith("_test.py")
        )
        is_script = "scripts" in path.parts
        is_page = "pages" in path.parts
        modules[name] = ModuleInfo(
            name=name,
            path=path,
            imports=imports,
            has_main_guard=has_main,
            is_test=is_test,
            is_script=is_script,
            is_package_init=(path.name == "__init__.py"),
            is_page=is_page,
        )
    return modules


def build_graph(mods: Dict[str, ModuleInfo]) -> Dict[str, Set[str]]:
    names = set(mods.keys())
    graph: Dict[str, Set[str]] = {m: set() for m in names}
    for mod, info in mods.items():
        refs: Set[str] = set()
        for imp in info.imports:
            parts = imp.split(".")
            for i in range(len(parts), 0, -1):
                candidate = ".".join(parts[:i])
                if candidate in names:
                    refs.add(candidate)
                    break
        graph[mod] = refs
    return graph


def discover_entries(
    root: Path, mods: Dict[str, ModuleInfo], provided: List[str]
) -> tuple[set[str], set[str], set[str], set[str]]:
    names = set(mods.keys())

    # App entries
    app_entries: Set[str] = set()
    if provided:
        for p in provided:
            pth = (root / p).resolve()
            if pth.exists():
                try:
                    name = rel_module_name(root, pth)
                    if name in names:
                        app_entries.add(name)
                except Exception:
                    pass
    for fname in DEFAULT_APP_ENTRY_FILES:
        p = root / fname
        if p.exists():
            name = rel_module_name(root, p)
            if name in names:
                app_entries.add(name)
    for m, info in mods.items():
        if info.has_main_guard and not info.is_test and not info.is_script:
            app_entries.add(m)
    if not app_entries:
        app_entries.update({m for m in names if "." not in m and not mods[m].is_test})

    # Streamlit page entries (treated as app roots too)
    page_entries: Set[str] = {m for m, info in mods.items() if info.is_page}

    # Test and script entries
    test_entries: Set[str] = {m for m, info in mods.items() if info.is_test}
    script_entries: Set[str] = {
        m for m, info in mods.items() if info.is_script and info.has_main_guard
    }
    return app_entries & names, page_entries & names, test_entries & names, script_entries & names


def reachable(graph: Dict[str, Set[str]], roots: Set[str]) -> Set[str]:
    seen: set[str] = set()
    stack = list(roots)
    while stack:
        m = stack.pop()
        if m in seen:
            continue
        seen.add(m)
        stack.extend(graph.get(m, []))
    return seen


def main() -> None:
    logger = get_logger(__name__)
    ap = argparse.ArgumentParser(
        description="Classify Python modules by reachability (app/pages/tests/scripts)."
    )
    ap.add_argument("--root", default=".", help="Project root")
    ap.add_argument(
        "--entry", action="append", help="App entry file(s), relative to root (repeatable)"
    )
    args = ap.parse_args()

    root = Path(args.root).resolve()
    mods = collect_modules(root)
    graph = build_graph(mods)
    app_entries, page_entries, test_entries, script_entries = discover_entries(
        root, mods, args.entry or []
    )

    app_seen = reachable(graph, app_entries)
    page_seen = reachable(graph, page_entries)
    test_seen = reachable(graph, test_entries)
    script_seen = reachable(graph, script_entries)

    all_names = set(mods.keys())
    reachable_any = app_seen | page_seen | test_seen | script_seen
    unreachable = sorted(all_names - reachable_any)
    only_tests = sorted((test_seen - app_seen - page_seen) - script_seen)
    only_scripts = sorted((script_seen - app_seen - page_seen) - test_seen)
    reachable_app_pages = sorted(app_seen | page_seen)

    def pp(title: str, items: List[str]) -> None:
        # JSON-only: emit results as a single structured record
        logger.info(
            title,
            extra={
                "event": "audit_unused_modules",
                "title": title,
                "items": [{"module": m, "path": str(mods[m].path)} for m in items],
            },
        )

    logger.info(
        "Entry modules",
        extra={"event": "audit_unused_modules", "section": "entry_modules"},
    )
    pp("App entries", sorted(app_entries))
    pp("Page entries (Streamlit)", sorted(page_entries))
    pp("Test entries", sorted(test_entries))
    pp("Script entries", sorted(script_entries))

    pp("Reachable from app/pages (in use)", reachable_app_pages)
    pp("Only used by tests (not in production)", only_tests)
    pp("Only used by scripts (CLI-only)", only_scripts)
    pp("Unreachable (candidates for legacy removal)", unreachable)


if __name__ == "__main__":
    with new_correlation_id():
        main()
