#!/usr/bin/env python3
"""
Read-only documentation consistency checks for KPulla6.

Usage (from repo root):
  python scripts/check_docs_consistency.py
  python scripts/check_docs_consistency.py --strict   # exit 1 on warnings

Checks:
  - mkdocs.yml nav entries point to existing files under docs/
  - Local Markdown links between docs resolve
  - Key API paths in docs/api-design.md appear in Django URL configs
  - Stale wording in current docs (conservative heuristics)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
MKDOCS_YML = REPO_ROOT / "mkdocs.yml"
API_DESIGN = DOCS_DIR / "api-design.md"

# Files where historical wording is expected.
HISTORICAL_DOC_GLOBS = {
    "changelog.md",
    "frontend-redesign-references.md",
    "dashboard-redesign-directions.md",
    "project-summary.md",
}

STALE_CHECKS = [
    (
        "mf_not_wired",
        re.compile(r"\*\*Not wired:\*\*.*\b(MF|mutual fund|CSV import|frontend MF)\b", re.I),
        "MF phases MF-1..MF-11b are implemented; remove stale 'Not wired' notes.",
    ),
    (
        "planned_cash_unify",
        re.compile(r"###\s+Planned\s+—\s+Cash unification", re.I),
        "Cash unification (CASH-UNIFY) is implemented; use 'Implemented' heading.",
    ),
    (
        "tear_sheet",
        re.compile(r"\btear[- ]sheet\b", re.I),
        "Prefer 'Metric Sheet' terminology in current docs.",
    ),
    (
        "sidebar_shell",
        re.compile(
            r"\b(sidebar selector|sidebar nav|scrolling the sidebar|from the sidebar)\b",
            re.I,
        ),
        "App shell uses sticky top header (Executive Portfolio OS); prefer header/top-nav.",
    ),
]

# Diátaxis pages that must exist (paths relative to docs/).
REQUIRED_PAGES = [
    "index.md",
    "getting-started/overview.md",
    "getting-started/quickstart.md",
    "getting-started/login-and-first-use.md",
    "getting-started/common-commands.md",
    "tutorials/add-first-portfolio.md",
    "tutorials/import-stock-transactions.md",
    "tutorials/add-mutual-fund-transactions.md",
    "tutorials/refresh-market-data.md",
    "tutorials/read-the-dashboard.md",
    "how-to/run-on-ipad-lan.md",
    "how-to/configure-google-oauth.md",
    "how-to/refresh-market-cache.md",
    "how-to/backup-restore-database.md",
    "how-to/add-backend-api-endpoint.md",
    "how-to/add-frontend-page.md",
    "how-to/investigate-dashboard-performance.md",
    "how-to/audit-docs-vs-code.md",
    "how-to/local-docs-domain.md",
    "concepts/architecture-overview.md",
    "concepts/transactions-source-of-truth.md",
    "concepts/cached-market-data.md",
    "concepts/portfolio-performance.md",
    "concepts/metric-sheet.md",
    "concepts/mutual-funds.md",
    "concepts/cash-ledger.md",
    "concepts/fixed-deposits-debt.md",
    "concepts/data-safety.md",
    "reference/api-reference.md",
    "reference/database-schema.md",
    "reference/make-commands.md",
    "reference/environment-variables.md",
    "reference/csv-formats.md",
    "reference/frontend-routes.md",
    "reference/backend-module-map.md",
    "reference/test-commands.md",
    "maintenance/agent-rules.md",
    "maintenance/cursor-maintenance-workflow.md",
    "maintenance/docs-consistency-checks.md",
    "maintenance/obsolete-code-audit.md",
    "maintenance/release-checklist.md",
    "troubleshooting/login-issues.md",
    "troubleshooting/google-oauth-errors.md",
    "troubleshooting/missing-prices-navs.md",
    "troubleshooting/dashboard-slow.md",
    "troubleshooting/database-safety.md",
    "troubleshooting/dev-server-ports.md",
    "decisions/architecture-decisions.md",
    "changelog/index.md",
]

# Docs that intentionally mention legacy terminology.
STALE_PHRASE_EXEMPT = {
    "concepts/metric-sheet.md",
    "maintenance/docs-consistency-checks.md",
}


def _collect_nav_paths(yaml_text: str) -> list[Path]:
    """Extract Markdown paths from mkdocs nav (indented 'key: file.md' lines)."""
    paths: list[Path] = []
    nav_entry = re.compile(r":\s+['\"]?([\w./-]+\.md)['\"]?\s*$")
    for line in yaml_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = nav_entry.search(stripped)
        if match:
            paths.append(DOCS_DIR / match.group(1))
    return paths


def _collect_markdown_files() -> list[Path]:
    return sorted(DOCS_DIR.rglob("*.md"))


def _resolve_link(source: Path, target: str) -> Path | None:
    target = target.split("#", 1)[0].strip()
    if not target or target.startswith(("http://", "https://", "mailto:")):
        return None
    if target.startswith("/"):
        resolved = DOCS_DIR / target.lstrip("/")
    else:
        resolved = (source.parent / target).resolve()
    return resolved


def check_required_pages(warnings: list[str]) -> None:
    for rel in REQUIRED_PAGES:
        path = DOCS_DIR / rel
        if not path.is_file():
            warnings.append(f"Required Diátaxis page missing: docs/{rel}")


def check_mkdocs_nav(warnings: list[str]) -> None:
    if not MKDOCS_YML.is_file():
        warnings.append(f"Missing {MKDOCS_YML.relative_to(REPO_ROOT)}")
        return
    yaml_text = MKDOCS_YML.read_text(encoding="utf-8")
    for path in _collect_nav_paths(yaml_text):
        if not path.is_file():
            warnings.append(f"mkdocs nav missing file: {path.relative_to(REPO_ROOT)}")


def check_markdown_links(warnings: list[str]) -> None:
    link_re = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    for md_file in _collect_markdown_files():
        text = md_file.read_text(encoding="utf-8", errors="replace")
        for match in link_re.finditer(text):
            raw = match.group(1).strip()
            if raw.startswith("<") and raw.endswith(">"):
                raw = raw[1:-1]
            resolved = _resolve_link(md_file, raw)
            if resolved is None:
                continue
            # Only validate links that stay inside docs/ or are explicit .md siblings.
            try:
                resolved.relative_to(DOCS_DIR)
            except ValueError:
                continue
            if not resolved.is_file():
                warnings.append(
                    f"Broken link in {md_file.relative_to(REPO_ROOT)}: "
                    f"({raw}) -> missing {resolved.relative_to(REPO_ROOT)}"
                )


def _collect_django_routes() -> set[str]:
    """Build normalized route paths under api/v1/ from Django url modules."""
    backend = REPO_ROOT / "backend"
    module_map = {
        "api.urls": backend / "api" / "urls.py",
        "cash.urls": backend / "cash" / "urls.py",
        "debt.urls": backend / "debt" / "urls.py",
        "analytics.urls": backend / "analytics" / "urls.py",
        "accounts.urls": backend / "accounts" / "urls.py",
    }
    include_re = re.compile(r'include\(\s*["\']([^"\']+)["\']')

    def walk(module: str, prefix: str) -> set[str]:
        url_file = module_map.get(module)
        if not url_file or not url_file.is_file():
            return set()
        routes: set[str] = set()
        collapsed = re.sub(r"\s+", " ", url_file.read_text(encoding="utf-8"))
        for m in re.finditer(r'path\(\s*["\']([^"\']*)["\']', collapsed):
            segment = m.group(1).strip("/")
            tail = collapsed[m.end() : m.end() + 120]
            include_m = include_re.search(tail)
            if include_m:
                child_module = include_m.group(1)
                child_prefix = "/".join(p for p in (prefix, segment) if p)
                routes |= walk(child_module, child_prefix)
            else:
                full = "/".join(p for p in (prefix, segment) if p)
                routes.add(_normalize_api_path(full))
        return routes

    return walk("api.urls", "")


def _load_url_patterns() -> set[str]:
    return _collect_django_routes()


def _normalize_api_path(path: str) -> str:
    path = path.strip().rstrip("/")
    if path.startswith("/api/v1/"):
        path = path[len("/api/v1/") :]
    elif path.startswith("api/v1/"):
        path = path[len("api/v1/") :]
    path = re.sub(r"\{[^}]+\}", "<id>", path)
    path = re.sub(r"<int:[^>]+>", "<id>", path)
    path = re.sub(r"<str:[^>]+>", "<id>", path)
    path = re.sub(r"<[^>]+>", "<id>", path)
    return path.rstrip("/")


def _path_matches_documented(doc_path: str, patterns: set[str]) -> bool:
    doc_norm = _normalize_api_path(doc_path)
    if doc_norm in patterns:
        return True
    doc_generic = re.sub(r"\{[^}]+\}", "<id>", doc_norm)
    doc_generic = re.sub(r"<int:[^>]+>", "<id>", doc_generic)
    doc_generic = re.sub(r"<str:[^>]+>", "<id>", doc_generic)
    doc_generic = re.sub(r"<[^>]+>", "<id>", doc_generic)
    for pat in patterns:
        if doc_generic == pat:
            return True
    return False


def check_api_paths(warnings: list[str]) -> None:
    if not API_DESIGN.is_file():
        warnings.append("Missing docs/api-design.md for API path check")
        return
    patterns = _load_url_patterns()
    text = API_DESIGN.read_text(encoding="utf-8")
    # Limit to the implemented endpoint index table (avoids prose mentions).
    index_start = text.find("## Implemented Endpoint Index")
    index_end = text.find("\n## ", index_start + 1) if index_start != -1 else -1
    index_text = text[index_start:index_end] if index_start != -1 else text[:8000]
    api_re = re.compile(r"`(/api/v1/[^`?*]+)`")
    seen: set[str] = set()
    for match in api_re.finditer(index_text):
        api_path = match.group(1).split("?")[0].rstrip("/")
        if api_path in seen or api_path.endswith("/*"):
            continue
        seen.add(api_path)
        if not _path_matches_documented(api_path, patterns):
            warnings.append(
                f"API path in api-design.md endpoint index not found in Django urls: {api_path}"
            )


def _is_historical(path: Path) -> bool:
    name = path.name
    if name in HISTORICAL_DOC_GLOBS:
        return True
    if path.parts and path.parts[0] == "backlog":
        return True
    if name == "changelog.md":
        return True
    return False


def check_stale_phrases(warnings: list[str]) -> None:
    for md_file in _collect_markdown_files():
        if _is_historical(md_file):
            continue
        rel = md_file.relative_to(DOCS_DIR).as_posix()
        if rel in STALE_PHRASE_EXEMPT:
            continue
        if md_file.name == "obsolete-code-audit.md":
            continue
        text = md_file.read_text(encoding="utf-8", errors="replace")
        for check_id, pattern, message in STALE_CHECKS:
            if pattern.search(text):
                warnings.append(
                    f"Stale phrase [{check_id}] in {md_file.relative_to(REPO_ROOT)}: {message}"
                )


def main() -> int:
    parser = argparse.ArgumentParser(description="KPulla6 docs consistency checks")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 when warnings are found",
    )
    args = parser.parse_args()

    warnings: list[str] = []
    check_required_pages(warnings)
    check_mkdocs_nav(warnings)
    check_markdown_links(warnings)
    check_api_paths(warnings)
    check_stale_phrases(warnings)

    if warnings:
        print(f"docs-check: {len(warnings)} warning(s)\n")
        for w in warnings:
            print(f"  - {w}")
        return 1 if args.strict else 0

    print("docs-check: OK (required pages, nav, links, API paths, stale phrases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
