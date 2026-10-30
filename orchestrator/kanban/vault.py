"""Obsidian-Vault-Spiegel für Worker, Aufgaben und Erfahrungen.

Der Vault bietet eine Graphensicht (Markdown-Notizen mit Links) auf
alles, was im System passiert. Jeder Worker hat eine Notiz, in der
seine Historie, seine Seele und seine Erfahrungen abgelegt sind.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from core.atomic import atomic_write_bytes

from .models import UID_PATTERN

if TYPE_CHECKING:
    from .models import Experience, KanbanTask

__all__ = ["ObsidianVault", "WorkerHome"]

_TASK_PATTERN = re.compile(r"^t-[0-9a-f]{12}$")

def check_uid(uid: str) -> None:
    if not UID_PATTERN.match(uid):
        raise ValueError(f"Ungültige UID: {uid}")

def check_task_id(task_id: str) -> None:
    if not _TASK_PATTERN.match(task_id):
        raise ValueError(f"Ungültige Task-ID: {task_id}")


class ObsidianVault:
    def __init__(self, root: Path) -> None:
        self.root = root

    def mirror_soul(self, uid: str, soul_md: str) -> None:
        check_uid(uid)
        path = self.root / "workers" / uid / "SOUL.md"
        atomic_write_bytes(path, soul_md.encode("utf-8"), fsync=True)
        self._ensure_worker_index(uid)

    def append_history(self, uid: str, line: str) -> None:
        check_uid(uid)
        path = self.root / "workers" / uid / "history.md"

        content = ""
        if path.exists():
            content = path.read_text("utf-8")

        if not content.endswith("\n") and content:
            content += "\n"
        content += line.strip() + "\n"

        atomic_write_bytes(path, content.encode("utf-8"), fsync=True)
        self._ensure_worker_index(uid)

    def write_experience(self, exp: Experience, task: KanbanTask) -> None:
        check_uid(exp.worker_uid)
        check_task_id(task.id)

        date = exp.created_at[:10]  # YYYY-MM-DD
        path = self.root / "workers" / exp.worker_uid / "experiences" / f"{date}-{task.id}.md"

        lines = [
            "---",
            f"uid: {exp.worker_uid}",
            f"task: {task.id}",
            f"outcome: {exp.outcome}",
            f"created: {exp.created_at}",
            "tags: [experience, academy]",
            "---",
            "",
            "## Summary",
            exp.summary,
            "",
            "## Lessons",
        ]

        for lesson in exp.lessons:
            lines.append(f"- {lesson}")

        lines.append("")
        lines.append("## Skills gained")
        for skill in exp.skills_delta:
            lines.append(f"- {skill}")

        lines.append("")
        lines.append("## Links")
        lines.append(f"- Worker: [[{exp.worker_uid}]]")
        lines.append(f"- Task: [[task-{task.id}]]")
        lines.append("")

        atomic_write_bytes(path, "\n".join(lines).encode("utf-8"), fsync=True)
        self._ensure_worker_index(exp.worker_uid)

    def write_task(self, task: KanbanTask) -> None:
        check_task_id(task.id)
        path = self.root / "tasks" / f"task-{task.id}.md"

        lines = [
            "---",
            f"status: {task.status}",
            "---",
            f"# {task.title}",
            "",
            f"{task.description}",
            "",
            "## Links",
        ]

        if task.parent_id:
            lines.append(f"- Parent: [[task-{task.parent_id}]]")

        for dep in task.dependencies:
            lines.append(f"- Dependency: [[task-{dep}]]")

        if task.assigned_worker_uid:
            lines.append(f"- Worker: [[{task.assigned_worker_uid}]]")

        lines.append("")

        atomic_write_bytes(path, "\n".join(lines).encode("utf-8"), fsync=True)

    def _ensure_worker_index(self, uid: str) -> None:
        path = self.root / "workers" / uid / f"{uid}.md"
        if not path.exists():
            lines = [
                f"# {uid}",
                "",
                "- [[SOUL]]",
                "- [[history]]",
                "- [[experiences]]",
                ""
            ]
            atomic_write_bytes(path, "\n".join(lines).encode("utf-8"), fsync=True)


class WorkerHome:
    def __init__(self, workspace_dir: Path) -> None:
        self.workspace_dir = workspace_dir

    def write_soul(self, uid: str, soul_md: str) -> None:
        check_uid(uid)
        path = self.workspace_dir / "workers" / uid / "SOUL.md"
        atomic_write_bytes(path, soul_md.encode("utf-8"), fsync=True)

    def append_history(self, uid: str, line: str) -> None:
        check_uid(uid)
        path = self.workspace_dir / "workers" / uid / "history.md"

        content = ""
        if path.exists():
            content = path.read_text("utf-8")

        if not content.endswith("\n") and content:
            content += "\n"
        content += line.strip() + "\n"

        atomic_write_bytes(path, content.encode("utf-8"), fsync=True)

