"""Shared types and orchestration for testguard."""

from __future__ import annotations

import os

from . import js_checks, python_checks
from .diff_checks import analyze_diff  # noqa: F401  (re-exported)
from .findings import Finding  # noqa: F401  (re-exported)

SEVERITIES = ("low", "medium", "high")
_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2}

TEST_NAME_MARKERS = ("test", "spec")
PY_EXTS = {".py"}
JS_EXTS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".tox", ".mypy_cache", "dist", "build", ".next",
}


def _looks_like_test(path: str, text: str) -> bool:
    """Heuristic: is this file a test file?"""
    base = os.path.basename(path).lower()
    if any(m in base for m in ("test_", "_test.", ".test.", ".spec.")):
        return True
    if base.startswith("test") or base.startswith("spec"):
        return True
    if "/tests/" in path.replace(os.sep, "/") or "/__tests__/" in path.replace(os.sep, "/"):
        return True
    # Fallback: content smells like tests.
    markers = ("def test_", "def test", "test(", "it(", "describe(",
               "assert ", "expect(", "pytest", "unittest")
    return any(m in text for m in markers)


def scan_text(path: str, text: str) -> list[Finding]:
    """Scan one file's content, dispatching on extension."""
    ext = os.path.splitext(path)[1].lower()
    if ext in PY_EXTS:
        return python_checks.check_python(path, text)
    if ext in JS_EXTS:
        return js_checks.check_js(path, text)
    return []


def scan_path(path: str) -> list[Finding]:
    """Scan a file or directory tree, skipping vendored/ignored dirs."""
    findings: list[Finding] = []
    targets: list[str] = []
    if os.path.isfile(path):
        targets = [path]
    elif os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            for name in sorted(files):
                targets.append(os.path.join(root, name))
    else:
        raise FileNotFoundError(f"no such file or directory: {path}")

    for target in targets:
        ext = os.path.splitext(target)[1].lower()
        if ext not in PY_EXTS | JS_EXTS:
            continue
        try:
            with open(target, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        if not _looks_like_test(target, text):
            continue
        findings.extend(scan_text(target, text))
    return findings


def worst_severity(findings: list[Finding]) -> str | None:
    """Return the highest severity present, or None when clean."""
    if not findings:
        return None
    return max((f.severity for f in findings), key=lambda s: _SEVERITY_RANK[s])


def meets_threshold(finding: Finding, threshold: str) -> bool:
    return _SEVERITY_RANK[finding.severity] >= _SEVERITY_RANK[threshold]
