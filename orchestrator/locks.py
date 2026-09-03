"""Agent-Slots (Phase 1, Protokoll 1.1).

Das Skalierungsprofil begrenzt, wie viele Agenten (Limb-Prozesse) gleichzeitig
laufen duerfen. Im Dev-Modus ist das exakt **einer**: ``max_agents=1``.

Implementiert als Datei-Locks unter ``runtime/locks/`` -- dadurch sichtbar,
nachvollziehbar und crash-tolerant (verwaiste Locks werden anhand von PID und
Ablaufzeit zurueckgeholt).
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Iterator

from core.config import NeuConfig
from core.protocol import format_timestamp, parse_timestamp, utc_now


@dataclass(frozen=True)
class AgentSlot:
    index: int
    path: Path
    job_id: str
    pid: int
    acquired_at: str
    expires_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "path": str(self.path),
            "job_id": self.job_id,
            "pid": self.pid,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
        }


class NoSlotAvailable(RuntimeError):
    """Alle Agent-Slots sind belegt (Dev-Modus: genau einer)."""

    def __init__(self, message: str, busy: tuple[dict[str, object], ...] = ()) -> None:
        self.busy = busy
        super().__init__(message)


class AgentPool:
    def __init__(self, config: NeuConfig | None = None) -> None:
        self.config = config or NeuConfig.load()
        self.config.ensure_dirs()

    @property
    def capacity(self) -> int:
        return max(1, self.config.limits.max_agents)

    def lock_path(self, index: int) -> Path:
        return self.config.locks_dir / f"agent-{index}.lock"

    def busy(self) -> list[AgentSlot]:
        slots: list[AgentSlot] = []
        for index in range(self.capacity):
            path = self.lock_path(index)
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            slots.append(
                AgentSlot(
                    index=index,
                    path=path,
                    job_id=str(data.get("job_id", "")),
                    pid=int(data.get("pid", 0)),
                    acquired_at=str(data.get("acquired_at", "")),
                    expires_at=str(data.get("expires_at", "")),
                )
            )
        return slots

    def is_stale(self, slot: AgentSlot) -> bool:
        """Verwaist, wenn die Frist abgelaufen ist oder die PID nicht mehr lebt."""
        try:
            expires = parse_timestamp(slot.expires_at, "$.expires_at")
        except Exception:  # noqa: BLE001 - defekte Lock-Datei gilt als verwaist
            return True
        if utc_now() > expires:
            return True
        if slot.pid <= 0:
            return True
        try:
            os.kill(slot.pid, 0)
        except (OSError, ProcessLookupError):
            return True
        return False

    def reclaim_stale(self) -> int:
        removed = 0
        for slot in self.busy():
            if self.is_stale(slot):
                slot.path.unlink(missing_ok=True)
                removed += 1
        return removed

    def acquire(self, *, job_id: str, ttl_s: float) -> AgentSlot:
        """Belegt einen Slot oder wirft ``NoSlotAvailable``."""
        self.config.locks_dir.mkdir(parents=True, exist_ok=True)
        self.reclaim_stale()
        now = utc_now()
        for index in range(self.capacity):
            path = self.lock_path(index)
            if path.exists():
                continue
            slot = AgentSlot(
                index=index,
                path=path,
                job_id=job_id,
                pid=os.getpid(),
                acquired_at=format_timestamp(now),
                expires_at=format_timestamp(now + _ttl(ttl_s)),
            )
            try:
                # O_CREAT|O_EXCL = atomar, auch gegen parallele Orchestratoren
                handle = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            except FileExistsError:
                continue
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(slot.to_dict(), stream, ensure_ascii=False, indent=2)
            return slot
        raise NoSlotAvailable(
            f"Kein Agent-Slot frei (mode={self.config.mode}, max_agents={self.capacity}).",
            busy=tuple(s.to_dict() for s in self.busy()),
        )

    def release(self, slot: AgentSlot) -> None:
        try:
            data = json.loads(slot.path.read_text(encoding="utf-8")) if slot.path.is_file() else {}
        except (json.JSONDecodeError, OSError):
            data = {}
        # Nur eigene Locks loesen (PID-Schutz gegen fremde Orchestratoren)
        if data.get("pid") in (os.getpid(), None):
            slot.path.unlink(missing_ok=True)

    @contextmanager
    def slot(self, *, job_id: str, ttl_s: float) -> Iterator[AgentSlot]:
        acquired = self.acquire(job_id=job_id, ttl_s=ttl_s)
        try:
            yield acquired
        finally:
            self.release(acquired)


def _ttl(value: float) -> timedelta:
    """Mindestens eine Sekunde, damit ein Lock nicht sofort als verwaist gilt."""
    return timedelta(seconds=max(1.0, float(value)))
