"""Shared finding type (kept separate to avoid a circular import)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Finding:
    """One suspicious pattern in a test file."""

    file: str
    line: int
    check_id: str
    severity: str  # low | medium | high
    message: str
    evidence: str = ""

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "line": self.line,
            "check": self.check_id,
            "severity": self.severity,
            "message": self.message,
            "evidence": self.evidence,
        }
