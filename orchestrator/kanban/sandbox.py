"""Sandbox-Verträge (Dummy für WP-05, da WP-04 dies liefert)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = ["SandboxResult"]

@dataclass(frozen=True)
class SandboxResult:
    exit_code: int | None
    timed_out: bool
    cancelled: bool
    out_dir: Path
    stderr_tail: str
