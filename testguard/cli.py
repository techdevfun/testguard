"""Command-line interface for testguard."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from .core import Finding, analyze_diff, meets_threshold, scan_path, worst_severity

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2


def format_text(findings: list[Finding]) -> str:
    if not findings:
        return "testguard: clean — no suspicious test patterns found.\n"
    lines = [f"testguard: {len(findings)} suspicious pattern(s) found:"]
    by_file: dict[str, list[Finding]] = {}
    for finding in findings:
        by_file.setdefault(finding.file, []).append(finding)
    for path in sorted(by_file):
        lines.append(f"\n{path}")
        for finding in sorted(by_file[path], key=lambda f: f.line):
            lines.append(
                f"  {finding.line:>4}  [{finding.severity:6}] "
                f"{finding.check_id}: {finding.message}"
            )
            if finding.evidence:
                lines.append(f"         evidence: {finding.evidence}")
    lines.append("")
    return "\n".join(lines)


def _run_git_diff(ref: str) -> str:
    proc = subprocess.run(
        ["git", "diff", ref, "--"],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git diff failed: {proc.stderr.strip()}")
    return proc.stdout


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="testguard",
        description="Scan test files for cheating/manipulation patterns "
                    "(fake passes, retry loops, swallowed assertions, "
                    "deleted tests) — the ways a green suite can lie.",
    )
    parser.add_argument("paths", nargs="*", default=["."],
                        help="Files or directories to scan (default: .)")
    parser.add_argument("--diff", nargs="?", const="HEAD", default=None,
                        metavar="REF",
                        help="Scan 'git diff REF' instead of files "
                             "(default REF: HEAD)")
    parser.add_argument("--format", choices=["text", "json"], default="text",
                        help="Output format (default: text)")
    parser.add_argument("--fail-on", choices=["low", "medium", "high", "none"],
                        default="low",
                        help="Fail when a finding at/above this severity "
                             "exists (default: low). 'none' never fails.")
    parser.add_argument("--version", action="version",
                        version="testguard 0.1.0")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    findings: list[Finding] = []
    try:
        if args.diff is not None:
            findings = analyze_diff(_run_git_diff(args.diff))
        else:
            for path in args.paths:
                findings.extend(scan_path(path))
    except FileNotFoundError as exc:
        print(f"testguard: error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except RuntimeError as exc:
        print(f"testguard: error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    findings.sort(key=lambda f: (f.file, f.line, f.check_id))
    if args.format == "json":
        print(json.dumps([f.to_dict() for f in findings], indent=2))
    else:
        print(format_text(findings), end="")

    if args.fail_on == "none":
        return EXIT_CLEAN
    worst = worst_severity(findings)
    if worst is None:
        return EXIT_CLEAN
    return EXIT_CLEAN if not any(
        meets_threshold(f, args.fail_on) for f in findings
    ) else EXIT_FINDINGS


if __name__ == "__main__":
    raise SystemExit(main())
