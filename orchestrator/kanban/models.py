"""Datenmodelle des Hermes-Kanban (Stdlib-Dataclasses, Vertrag fuer Python und Rust).

Jede Klasse hat ``to_dict``/``from_dict`` mit exakt den Feldern, die
``protocol/kanban/*.schema.json`` und die Serde-Structs in ``rust/nio-contracts``
beschreiben. ``tests/test_kanban_contracts.py`` haelt die drei Seiten gegen
dieselben Golden-Fixtures zusammen -- ein neues Feld muss an allen drei Stellen
landen, sonst wird der Test rot.

Zustandsmaschine (Hermes-Konvention)::

    triage -> backlog -> ready -> in_progress -> completed
                 ^         |          |
                 |         v          v
                 +------ blocked <----+        (in_progress -> ready = Reaper-Reset)
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from core.protocol import utc_now_iso

__all__ = [
    "ALLOWED_TRANSITIONS",
    "AUDIT_CATEGORIES",
    "UID_PATTERN",
    "AuditEntry",
    "Experience",
    "KanbanBoard",
    "KanbanEvent",
    "KanbanTask",
    "RustLimb",
    "RustLimbRequest",
    "RustLimbResponse",
    "TaskStatus",
    "ToolCall",
    "TransitionError",
    "Worker",
    "WorkerStatus",
    "check_transition",
    "new_id",
]

#: Gleiches Muster wie die Subagent-IDs (``orchestrator/subagent.py``): taugt als
#: Verzeichnisname, Container-Name und Obsidian-Notizname.
UID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{1,47}$")

AUDIT_CATEGORIES = ("system", "code", "trading", "task", "worker")


class TaskStatus(StrEnum):
    TRIAGE = "triage"
    BACKLOG = "backlog"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"


class WorkerStatus(StrEnum):
    IDLE = "idle"
    BUSY = "busy"
    DISABLED = "disabled"


#: Erlaubte Uebergaenge. ``backlog -> completed`` ist dem Roll-up eines Eltern-
#: Tasks vorbehalten (alle Kinder fertig), ``in_progress -> ready`` dem Reaper.
ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.TRIAGE: frozenset({TaskStatus.BACKLOG, TaskStatus.BLOCKED}),
    TaskStatus.BACKLOG: frozenset({TaskStatus.READY, TaskStatus.BLOCKED, TaskStatus.COMPLETED}),
    TaskStatus.READY: frozenset({TaskStatus.IN_PROGRESS, TaskStatus.BACKLOG, TaskStatus.BLOCKED}),
    TaskStatus.IN_PROGRESS: frozenset({TaskStatus.COMPLETED, TaskStatus.BLOCKED, TaskStatus.READY}),
    TaskStatus.BLOCKED: frozenset({TaskStatus.TRIAGE, TaskStatus.BACKLOG, TaskStatus.READY}),
    TaskStatus.COMPLETED: frozenset(),
}


class TransitionError(ValueError):
    """Ein Statuswechsel ist laut ``ALLOWED_TRANSITIONS`` nicht zulaessig."""


def check_transition(current: TaskStatus | str, target: TaskStatus | str) -> TaskStatus:
    """Prueft ``current -> target`` und gibt ``target`` als ``TaskStatus`` zurueck."""
    src, dst = TaskStatus(current), TaskStatus(target)
    if dst not in ALLOWED_TRANSITIONS[src]:
        raise TransitionError(f"Uebergang {src.value} -> {dst.value} ist nicht erlaubt")
    return dst


def new_id(prefix: str) -> str:
    """Kurze, kollisionsarme IDs wie ``t-3f9a0c1d2e4b`` (Task) oder ``b-…`` (Board)."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _str_list(value: Any) -> list[str]:
    return [str(v) for v in value] if isinstance(value, (list, tuple)) else []


def _opt_str(value: Any) -> str | None:
    return None if value is None else str(value)


@dataclass
class KanbanBoard:
    id: str
    name: str
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "created_at": self.created_at}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> KanbanBoard:
        return cls(id=str(data["id"]), name=str(data["name"]), created_at=str(data.get("created_at") or utc_now_iso()))


@dataclass
class KanbanTask:
    id: str
    board_id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.TRIAGE
    priority: int = 0
    assigned_worker_uid: str | None = None
    parent_id: str | None = None
    dependencies: list[str] = field(default_factory=list)
    required_skills: list[str] = field(default_factory=list)
    is_rollup: bool = False
    attempts: int = 0
    result_payload: dict[str, Any] | None = None
    block_reason: str = ""
    workspace_repo: str | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    started_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "board_id": self.board_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority,
            "assigned_worker_uid": self.assigned_worker_uid,
            "parent_id": self.parent_id,
            "dependencies": list(self.dependencies),
            "required_skills": list(self.required_skills),
            "is_rollup": self.is_rollup,
            "attempts": self.attempts,
            "result_payload": None if self.result_payload is None else dict(self.result_payload),
            "block_reason": self.block_reason,
            "workspace_repo": self.workspace_repo,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> KanbanTask:
        payload = data.get("result_payload")
        now = utc_now_iso()
        return cls(
            id=str(data["id"]),
            board_id=str(data["board_id"]),
            title=str(data["title"]),
            description=str(data.get("description") or ""),
            status=TaskStatus(data.get("status") or TaskStatus.TRIAGE),
            priority=int(data.get("priority") or 0),
            assigned_worker_uid=_opt_str(data.get("assigned_worker_uid")),
            parent_id=_opt_str(data.get("parent_id")),
            dependencies=_str_list(data.get("dependencies")),
            required_skills=_str_list(data.get("required_skills")),
            is_rollup=bool(data.get("is_rollup")),
            attempts=int(data.get("attempts") or 0),
            result_payload=dict(payload) if isinstance(payload, Mapping) else None,
            block_reason=str(data.get("block_reason") or ""),
            workspace_repo=_opt_str(data.get("workspace_repo")),
            created_at=str(data.get("created_at") or now),
            updated_at=str(data.get("updated_at") or now),
            started_at=_opt_str(data.get("started_at")),
        )


@dataclass
class Worker:
    uid: str
    name: str
    skills: list[str] = field(default_factory=list)
    soul_md: str = ""
    status: WorkerStatus = WorkerStatus.IDLE
    fail_count: int = 0
    breaker_open_until: str | None = None
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        if not UID_PATTERN.match(self.uid):
            raise ValueError(f"ungueltige Worker-UID {self.uid!r} (a-z, 0-9, '.', '_', '-'; 2..48 Zeichen)")

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "name": self.name,
            "skills": list(self.skills),
            "soul_md": self.soul_md,
            "status": self.status.value,
            "fail_count": self.fail_count,
            "breaker_open_until": self.breaker_open_until,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Worker:
        return cls(
            uid=str(data["uid"]),
            name=str(data.get("name") or data["uid"]),
            skills=_str_list(data.get("skills")),
            soul_md=str(data.get("soul_md") or ""),
            status=WorkerStatus(data.get("status") or WorkerStatus.IDLE),
            fail_count=int(data.get("fail_count") or 0),
            breaker_open_until=_opt_str(data.get("breaker_open_until")),
            updated_at=str(data.get("updated_at") or utc_now_iso()),
        )


@dataclass
class Experience:
    """Academy-*Experience*: die verdichtete Lehre eines Worker-Laufs."""

    id: str
    worker_uid: str
    task_id: str
    summary: str
    lessons: list[str] = field(default_factory=list)
    skills_delta: list[str] = field(default_factory=list)
    outcome: str = "success"
    vault_synced: bool = False
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "worker_uid": self.worker_uid,
            "task_id": self.task_id,
            "summary": self.summary,
            "lessons": list(self.lessons),
            "skills_delta": list(self.skills_delta),
            "outcome": self.outcome,
            "vault_synced": self.vault_synced,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Experience:
        return cls(
            id=str(data.get("id") or new_id("x")),
            worker_uid=str(data["worker_uid"]),
            task_id=str(data["task_id"]),
            summary=str(data.get("summary") or ""),
            lessons=_str_list(data.get("lessons")),
            skills_delta=_str_list(data.get("skills_delta")),
            outcome=str(data.get("outcome") or "success"),
            vault_synced=bool(data.get("vault_synced")),
            created_at=str(data.get("created_at") or utc_now_iso()),
        )


@dataclass(frozen=True)
class AuditEntry:
    """Eine Zeile des unveraenderlichen Audit-Ledgers (Hash-Kette, siehe ``audit.py``)."""

    seq: int
    ts: str
    actor: str
    action: str
    category: str
    subject: str
    payload: dict[str, Any]
    prev_hash: str
    entry_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "ts": self.ts,
            "actor": self.actor,
            "action": self.action,
            "category": self.category,
            "subject": self.subject,
            "payload": dict(self.payload),
            "prev_hash": self.prev_hash,
            "entry_hash": self.entry_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AuditEntry:
        payload = data.get("payload")
        return cls(
            seq=int(data["seq"]),
            ts=str(data["ts"]),
            actor=str(data["actor"]),
            action=str(data["action"]),
            category=str(data["category"]),
            subject=str(data.get("subject") or ""),
            payload=dict(payload) if isinstance(payload, Mapping) else {},
            prev_hash=str(data["prev_hash"]),
            entry_hash=str(data["entry_hash"]),
        )


@dataclass(frozen=True)
class KanbanEvent:
    """Echtzeit-Ereignis auf dem Bus (``kanban:events``)."""

    kind: str
    task_id: str | None = None
    board_id: str | None = None
    status: str | None = None
    worker_uid: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "task_id": self.task_id,
            "board_id": self.board_id,
            "status": self.status,
            "worker_uid": self.worker_uid,
            "payload": dict(self.payload),
            "ts": self.ts,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> KanbanEvent:
        payload = data.get("payload")
        return cls(
            kind=str(data["kind"]),
            task_id=_opt_str(data.get("task_id")),
            board_id=_opt_str(data.get("board_id")),
            status=_opt_str(data.get("status")),
            worker_uid=_opt_str(data.get("worker_uid")),
            payload=dict(payload) if isinstance(payload, Mapping) else {},
            ts=str(data.get("ts") or utc_now_iso()),
        )


@dataclass(frozen=True)
class ToolCall:
    """Aufruf eines ``kanban_*``-Tools aus der Sandbox (Shim -> API)."""

    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"tool": self.tool, "arguments": dict(self.arguments)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ToolCall:
        args = data.get("arguments")
        return cls(tool=str(data["tool"]), arguments=dict(args) if isinstance(args, Mapping) else {})


@dataclass(frozen=True)
class RustLimb:
    """Registrierung eines Rust-Limbs (HTTP-Endpunkt mit Serde-Vertrag)."""

    name: str
    version: str
    contract_version: str
    endpoint: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "version": self.version, "contract_version": self.contract_version, "endpoint": self.endpoint}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RustLimb:
        return cls(
            name=str(data["name"]),
            version=str(data["version"]),
            contract_version=str(data["contract_version"]),
            endpoint=str(data["endpoint"]),
        )


@dataclass(frozen=True)
class RustLimbRequest:
    request_id: str
    operation: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"request_id": self.request_id, "operation": self.operation, "params": dict(self.params)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RustLimbRequest:
        params = data.get("params")
        return cls(
            request_id=str(data["request_id"]),
            operation=str(data["operation"]),
            params=dict(params) if isinstance(params, Mapping) else {},
        )


@dataclass(frozen=True)
class RustLimbResponse:
    request_id: str
    ok: bool
    result: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "ok": self.ok,
            "result": None if self.result is None else dict(self.result),
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RustLimbResponse:
        result = data.get("result")
        return cls(
            request_id=str(data["request_id"]),
            ok=bool(data["ok"]),
            result=dict(result) if isinstance(result, Mapping) else None,
            error=_opt_str(data.get("error")),
        )
