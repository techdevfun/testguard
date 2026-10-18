"""Line-based checks for JavaScript / TypeScript test files.

Vitest, Jest, Mocha, Bun and Node's built-in runner share the same
vocabulary (``test`` / ``it`` / ``describe`` / ``expect``), so one
line-oriented scanner covers all of them without a JS parser.
"""

from __future__ import annotations

import re

from .findings import Finding

_SKIP_RE = re.compile(r"\b(test|it|describe|xdescribe|xit)\s*\.\s*skip\s*\(")
_FOCUS_RE = re.compile(r"\b(test|it|describe|fdescribe|fit)\s*\.\s*only\s*\(|\bfdescribe\s*\(|\bfit\s*\(")
_TODO_RE = re.compile(r"\b(test|it)\s*\.\s*todo\s*\(")
_SLEEP_RE = re.compile(r"\b(setTimeout|setInterval|sleep)\s*\(")
_FAKE_PASS_RE = re.compile(
    r"expect\s*\(\s*(true|1|'[^']*'|\"[^\"]*\")\s*\)\s*\.\s*toBe\s*\(\s*\1\s*\)"
    r"|assert\s*\(\s*(true|1)\s*\)"
)
_EMPTY_TEST_RE = re.compile(
    r"^\s*(test|it)\s*\(.*,\s*(async\s*)?\(\s*\)\s*=>\s*\{\s*\}\s*\)"
)
_LOOP_RE = re.compile(r"^\s*(for|while)\s*\(")


def check_js(path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines()

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if _SKIP_RE.search(line):
            findings.append(Finding(path, i, "skipped-test", "low",
                                    "Test is skipped and never runs.", stripped[:120]))
        if _FOCUS_RE.search(line):
            findings.append(Finding(path, i, "focused-test", "high",
                                    ".only() runs one test and silently skips "
                                    "the rest of the suite.", stripped[:120]))
        if _TODO_RE.search(line):
            findings.append(Finding(path, i, "skipped-test", "low",
                                    "Test is a .todo() placeholder and never runs.",
                                    stripped[:120]))
        if _SLEEP_RE.search(line):
            findings.append(Finding(path, i, "hardcoded-sleep", "medium",
                                    "Hardcoded timer in a test hides timing "
                                    "flakiness and slows the suite.",
                                    stripped[:120]))
        if _FAKE_PASS_RE.search(line):
            findings.append(Finding(path, i, "fake-pass", "high",
                                    "Assertion compares a constant to itself "
                                    "and can never fail.", stripped[:120]))
        if _EMPTY_TEST_RE.match(line):
            findings.append(Finding(path, i, "empty-test", "high",
                                    "Test body is empty — it can never fail.",
                                    stripped[:120]))

    # Retry loop: a for/while loop whose body contains expect() + try/catch.
    for i, line in enumerate(lines, start=1):
        if _LOOP_RE.match(line):
            window = "\n".join(lines[i:i + 20])
            if "expect(" in window and ("try" in window or "catch" in window):
                findings.append(Finding(path, i, "retry-loop", "high",
                                        "Assertion inside a retry loop: the "
                                        "test passes if it succeeds once.",
                                        line.strip()[:120]))
                break

    # Swallowed assertion: try { ... expect ... } catch (e) {} with an
    # empty catch. Only the FIRST catch after the try counts, so a retry
    # loop's non-empty catch does not trigger a false positive.
    for i, line in enumerate(lines, start=1):
        if re.search(r"\btry\s*\{", line):
            window = "\n".join(lines[i - 1:i + 8])
            first_catch = window.find("catch")
            if first_catch == -1:
                continue
            after_catch = window[first_catch:]
            empty_catch = re.match(r"catch\s*\([^)]*\)\s*\{\s*\}", after_catch)
            if empty_catch and "expect(" in window[:first_catch]:
                findings.append(Finding(path, i, "swallowed-assert", "high",
                                        "Assertion inside try/catch with an "
                                        "empty catch swallows the failure.",
                                        line.strip()[:120]))
                break

    return findings
