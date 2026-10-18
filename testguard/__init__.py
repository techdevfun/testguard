"""testguard — catch tests that lie.

An AI coding agent (or a tired human) can make a test suite green without
fixing anything: delete the failing test, wrap the assertion in a retry
loop, swallow the AssertionError, skip the test, or assert ``True``.
CI stays green. The bug stays shipped.

testguard scans test files (Python + JavaScript/TypeScript) for those
manipulation patterns and reports each one with file, line and evidence.
It can also scan a ``git diff`` so a PR that weakens tests gets flagged
before it merges.
"""

from .core import Finding, scan_path, analyze_diff, scan_text

__all__ = ["Finding", "scan_path", "analyze_diff", "scan_text"]
__version__ = "0.1.0"
