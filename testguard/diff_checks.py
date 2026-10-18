"""Checks for ``git diff`` output.

The most common way an agent (or a rushed human) fakes a green suite is
not in the test file itself — it is in the *change*: delete the failing
test, remove the assertion, add a skip, add a sleep. Scanning the diff
catches the weakening at review time, before it merges.
"""

from __future__ import annotations

import re

from .findings import Finding

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
_TEST_DEF_RE = re.compile(r"^\s*def\s+(test\w*)\s*\(|^\s*(test|it)\s*\(")
_ASSERT_RE = re.compile(r"\bassert\b|\bexpect\s*\(")
_SKIP_RE = re.compile(r"@pytest\.mark\.skip|pytest\.skip|unittest\.skip"
                      r"|\.skip\s*\(|\bxit\s*\(|\bxdescribe\s*\(")
_SLEEP_RE = re.compile(r"\b(time\.sleep|asyncio\.sleep|setTimeout|sleep)\s*\(")
_FAKE_PASS_RE = re.compile(r"assert\s+True\b|expect\s*\(\s*true\s*\)\s*\.\s*toBe\s*\(\s*true\s*\)")


def analyze_diff(diff_text: str, label: str = "<diff>") -> list[Finding]:
    findings: list[Finding] = []
    current_file = label
    new_lineno = 0
    hunk_removed_asserts: list[tuple[int, str]] = []
    hunk_has_added_assert = False

    def flush_hunk() -> None:
        if hunk_removed_asserts and not hunk_has_added_assert:
            for line_no, content in hunk_removed_asserts:
                findings.append(Finding(
                    current_file, line_no, "removed-assert", "high",
                    "Assertion removed from a test with no replacement "
                    "assertion in the same change.", content[:120]))

    for raw in diff_text.splitlines():
        line = raw.rstrip("\n")
        if line.startswith("+++ "):
            flush_hunk()
            hunk_removed_asserts, hunk_has_added_assert = [], False
            name = line[4:].strip()
            if name.startswith("b/"):
                name = name[2:]
            current_file = name if name != "/dev/null" else current_file
            continue
        if line.startswith("diff --git"):
            flush_hunk()
            hunk_removed_asserts, hunk_has_added_assert = [], False
            continue
        match = _HUNK_RE.match(line)
        if match:
            flush_hunk()
            hunk_removed_asserts, hunk_has_added_assert = [], False
            new_lineno = int(match.group(1))
            continue
        if line.startswith("--- ") or line.startswith("index ") \
                or line.startswith("new file") or line.startswith("deleted file"):
            continue
        if line.startswith("+") and not line.startswith("+++"):
            content = line[1:]
            if _ASSERT_RE.search(content):
                hunk_has_added_assert = True
            if _SKIP_RE.search(content):
                findings.append(Finding(current_file, new_lineno, "added-skip",
                                        "medium", "Change adds a skip to a test.",
                                        content.strip()[:120]))
            if _SLEEP_RE.search(content):
                findings.append(Finding(current_file, new_lineno, "added-sleep",
                                        "medium", "Change adds a hardcoded sleep to a test.",
                                        content.strip()[:120]))
            if _FAKE_PASS_RE.search(content):
                findings.append(Finding(current_file, new_lineno, "added-fake-pass",
                                        "high",
                                        "Change adds an assertion that can never fail.",
                                        content.strip()[:120]))
            new_lineno += 1
        elif line.startswith("-") and not line.startswith("---"):
            content = line[1:]
            test_match = _TEST_DEF_RE.search(content)
            if test_match:
                findings.append(Finding(current_file, new_lineno, "deleted-test",
                                        "high",
                                        "Change deletes (or renames) a test — "
                                        "check that the coverage is replaced, "
                                        "not just dropped.",
                                        content.strip()[:120]))
            elif _ASSERT_RE.search(content):
                hunk_removed_asserts.append((new_lineno, content.strip()))
        else:
            # Context line: advances the new-file line number.
            if line.startswith(" ") or line == "":
                new_lineno += 1

    flush_hunk()
    return findings
