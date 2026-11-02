"""Budget-Verwaltung für den Orchestrator.

Beschränkt die Ressourcennutzung pro Lauf und pro Tag.
Gesteuert über Umgebungsvariablen:
- NIO_BUDGET_DAILY_SECONDS: Maximale Laufzeit (Sekunden) pro Tag (Default: 14400).
- NIO_BUDGET_DAILY_TOKENS: Maximale Token pro Tag (Default: 500000).
- NIO_BUDGET_DAILY_CREDITS: Maximale Credits pro Tag (Default: 1.0).
- NIO_BUDGET_RUN_SECONDS: Maximale Laufzeit (Sekunden) pro Lauf (Default: 1800).
- NIO_BUDGET_RUN_TOKENS: Maximale Token pro Lauf (Default: 50000).
- NIO_BUDGET_RUN_CREDITS: Maximale Credits pro Lauf (Default: 0.25).

Die tägliche Nutzungsbilanz wird in runtime/budget/<YYYY-MM-DD>.json abgelegt.
"""

from __future__ import annotations

import fcntl
import json

import math
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from core.atomic import atomic_write_bytes


class BudgetError(Exception):
    pass


DEFAULT_DAILY_SECONDS = 14400.0
DEFAULT_DAILY_TOKENS = 500000
DEFAULT_DAILY_CREDITS = 1.0
DEFAULT_RUN_SECONDS = 1800.0
DEFAULT_RUN_TOKENS = 50000
DEFAULT_RUN_CREDITS = 0.25


@dataclass
class Usage:
    seconds: float = 0.0
    tokens: int | None = None
    credits: float = 0.0


def _parse_env_float(name: str, default: float) -> float:
    val = os.environ.get(name)
    if val is None:
        return default
    try:
        f = float(val)
        if not math.isfinite(f) or f < 0:
            raise ValueError
        return f
    except (ValueError, TypeError):
        raise BudgetError(f"Ungueltiger Wert fuer {name}")


def _parse_env_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    if val is None:
        return default
    try:
        i = int(val)
        if i < 0:
            raise ValueError
        return i
    except (ValueError, TypeError):
        raise BudgetError(f"Ungueltiger Wert fuer {name}")


class BudgetTracker:
    def __init__(self, root: Path):
        self.root = root
        self._init_error: BudgetError | None = None
        try:
            self.daily_seconds = _parse_env_float("NIO_BUDGET_DAILY_SECONDS", DEFAULT_DAILY_SECONDS)
            self.daily_tokens = _parse_env_int("NIO_BUDGET_DAILY_TOKENS", DEFAULT_DAILY_TOKENS)
            self.daily_credits = _parse_env_float("NIO_BUDGET_DAILY_CREDITS", DEFAULT_DAILY_CREDITS)
            self.run_seconds = _parse_env_float("NIO_BUDGET_RUN_SECONDS", DEFAULT_RUN_SECONDS)
            self.run_tokens = _parse_env_int("NIO_BUDGET_RUN_TOKENS", DEFAULT_RUN_TOKENS)
            self.run_credits = _parse_env_float("NIO_BUDGET_RUN_CREDITS", DEFAULT_RUN_CREDITS)
        except BudgetError as e:
            self._init_error = e

        self.root.mkdir(parents=True, exist_ok=True)

    def _ledger_path(self, dt: datetime | None = None) -> Path:
        dt = dt or datetime.now(timezone.utc)
        return self.root / f"{dt.strftime('%Y-%m-%d')}.json"

    def _read_ledger(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"seconds": 0.0, "tokens": 0, "credits": 0.0, "unknown_tokens": 0}
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "seconds": float(data.get("seconds", 0.0)),
                    "tokens": int(data.get("tokens", 0)),
                    "credits": float(data.get("credits", 0.0)),
                    "unknown_tokens": int(data.get("unknown_tokens", 0))
                }
        except Exception as e:
            raise BudgetError(f"Budget ledger corrupt or unreadable: {e}")

    def _write_ledger(self, path: Path, data: dict[str, Any]) -> None:
        try:
            content = json.dumps(data, separators=(",", ":")).encode("utf-8")
            atomic_write_bytes(path, content)
        except Exception as e:
            raise BudgetError(f"Cannot write budget ledger: {e}")

    @contextmanager
    def _lock_ledger(self, path: Path) -> Generator[None, None, None]:
        lock_path = path.with_suffix(".lock")
        fd = -1
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
            start_time = time.monotonic()
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except (IOError, OSError):
                    if time.monotonic() - start_time > 5.0:
                        raise BudgetError("Konkurrierender Zugriff auf Budget Ledger (Lock Timeout).")
                    time.sleep(0.01)
            yield
        finally:
            if fd != -1:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                    os.close(fd)
                except OSError:
                    pass

    def check_start(self, dt: datetime | None = None) -> None:
        if self._init_error:
            raise self._init_error

        path = self._ledger_path(dt)
        with self._lock_ledger(path):
            ledger = self._read_ledger(path)

            if ledger["seconds"] >= self.daily_seconds:
                raise BudgetError("Tägliches Laufzeit-Budget überschritten.")
            if ledger["tokens"] >= self.daily_tokens:
                raise BudgetError("Tägliches Token-Budget überschritten.")
            if ledger["credits"] >= self.daily_credits:
                raise BudgetError("Tägliches Credit-Budget überschritten.")

    def record_and_check(self, run_id: str, delta: Usage, total_run: Usage, dt: datetime | None = None) -> str:
        if self._init_error:
            raise self._init_error

        path = self._ledger_path(dt)

        limit_reason = ""
        if total_run.seconds > self.run_seconds:
            limit_reason = "Laufzeit-Budget für diesen Lauf überschritten."
        if total_run.tokens is not None and total_run.tokens > self.run_tokens:
            limit_reason = "Token-Budget für diesen Lauf überschritten."
        if total_run.credits > self.run_credits:
            limit_reason = "Credit-Budget für diesen Lauf überschritten."

        with self._lock_ledger(path):
            ledger = self._read_ledger(path)
            ledger["seconds"] += delta.seconds
            if delta.tokens is not None:
                ledger["tokens"] += delta.tokens
            elif delta.tokens is None:
                 ledger["unknown_tokens"] += 1
            ledger["credits"] += delta.credits

            self._write_ledger(path, ledger)

            if ledger["seconds"] > self.daily_seconds:
                limit_reason = "Tägliches Laufzeit-Budget überschritten."
            if ledger["tokens"] > self.daily_tokens:
                limit_reason = "Tägliches Token-Budget überschritten."
            if ledger["credits"] > self.daily_credits:
                limit_reason = "Tägliches Credit-Budget überschritten."

            return limit_reason
