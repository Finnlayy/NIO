"""Hermes-Kanban: dauerhafte Aufgaben-Queue, Dispatcher und JIT-Worker-Sandboxes.

Rein additives Paket im NEU-Orchestrator. Der Kern ist **Stdlib-only** (SQLite,
In-Process-Bus, Subprozess-Sandbox); Postgres (``store_pg``), Redis
(``redis_resp``, ebenfalls Stdlib) und die FastAPI-Schicht (``api``) sind Adapter,
die erst beim Gebrauch importiert werden (Extra ``kanban``). Siehe ``docs/KANBAN.md``.
"""

from __future__ import annotations

from .config import KanbanConfig
from .models import (
    ALLOWED_TRANSITIONS,
    AuditEntry,
    Experience,
    KanbanBoard,
    KanbanEvent,
    KanbanTask,
    TaskStatus,
    TransitionError,
    Worker,
    WorkerStatus,
)

__all__ = [
    "ALLOWED_TRANSITIONS",
    "AuditEntry",
    "Experience",
    "KanbanBoard",
    "KanbanConfig",
    "KanbanEvent",
    "KanbanTask",
    "TaskStatus",
    "TransitionError",
    "Worker",
    "WorkerStatus",
]
