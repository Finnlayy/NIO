"""Rücksynchronisation eines Sandbox-Ergebnisses in Store und Vault.

Liest die Resultate aus dem `out/` Verzeichnis, aktualisiert die Worker-Seele,
schreibt die Erfahrung in den Kanban-Store und spiegelt alles in den Obsidian Vault.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.protocol import utc_now_iso

from .audit import AuditDraft
from .models import Experience, KanbanTask, Worker
from .sandbox import SandboxResult
from .store import KanbanStore
from .vault import ObsidianVault, WorkerHome

__all__ = ["RunOutcome", "sync_back"]


@dataclass(frozen=True)
class RunOutcome:
    status: str
    reason: str
    result_payload: dict[str, Any] | None
    experience: Experience | None
    soul_md: str | None


async def sync_back(
    *,
    store: KanbanStore,
    vault: ObsidianVault,
    workspace_dir: Path,
    task: KanbanTask,
    worker: Worker,
    result: SandboxResult,
) -> RunOutcome:
    """Wertet Sandbox-Resultat aus und synchronisiert es zurück."""
    status = "failed"
    reason = "no result (exit None)" if result.exit_code is None else f"no result (exit {result.exit_code})"
    result_payload = None

    result_file = result.out_dir / "result.json"
    if result_file.is_file():
        try:
            data = json.loads(result_file.read_text("utf-8"))
            if isinstance(data, dict):
                st = data.get("status", "failed")
                if result.exit_code != 0:
                    status = "failed"
                    reason = data.get("reason", f"exit code {result.exit_code}")
                elif result.timed_out:
                    status = "failed"
                    reason = "deadline exceeded"
                elif st in {"completed", "blocked", "failed"}:
                    status = st
                    reason = data.get("reason", "")

                result_payload = data.get("result_payload")
        except (OSError, json.JSONDecodeError):
            pass

    if result.timed_out:
        status = "failed"
        reason = "deadline exceeded"

    if result.exit_code != 0 and status != "failed":
        status = "failed"
        if reason.startswith("no result"):
            reason = f"exit code {result.exit_code}"

    exp_file = result.out_dir / "experience.json"
    exp = None
    if exp_file.is_file():
        try:
            exp_data = json.loads(exp_file.read_text("utf-8"))
            if isinstance(exp_data, dict):
                exp = Experience(
                    id=f"e-{task.id[-12:]}",  # Fallback for mock/test if needed, actually core models define how to gen id but we can just make it unique or rely on store
                    worker_uid=worker.uid,
                    task_id=task.id,
                    summary=exp_data.get("summary", f"{task.title}: {status}"),
                    outcome=exp_data.get("outcome", status),
                    lessons=exp_data.get("lessons", []),
                    skills_delta=exp_data.get("skills_delta", []),
                    created_at=utc_now_iso()
                )
        except (OSError, json.JSONDecodeError):
            pass

    if not exp:
        exp = Experience(
            id=f"e-{task.id[-12:]}",
            worker_uid=worker.uid,
            task_id=task.id,
            summary=f"{task.title}: {status}",
            outcome=status,
            lessons=[],
            skills_delta=[],
            created_at=utc_now_iso()
        )

    # Let store handle the actual ID creation by not setting it, or generating a standard length ID. Let's look at `new_id`
    from .models import new_id
    exp = Experience(
        id=new_id("exp"),
        worker_uid=worker.uid,
        task_id=task.id,
        summary=exp.summary,
        outcome=exp.outcome,
        lessons=exp.lessons,
        skills_delta=exp.skills_delta,
        created_at=exp.created_at
    )

    soul_md = None
    soul_file = result.out_dir / "SOUL.md"
    if soul_file.is_file():
        try:
            if soul_file.stat().st_size <= 256 * 1024:
                soul_md = soul_file.read_text("utf-8")
        except OSError:
            import logging
            logging.getLogger(__name__).warning("Vault sync failed due to OSError")

    worker_changes: dict[str, Any] = {}
    if soul_md is not None:
        worker_changes["soul_md"] = soul_md

    audit = AuditDraft(
        actor=f"worker:{worker.uid}",
        action="worker.experience",
        category="worker",
        subject=task.id,
        payload={"outcome": exp.outcome}
    )

    await store.finish_run(
        task_id=task.id,
        expected=None,
        task_changes={},
        worker_uid=worker.uid,
        worker_changes=worker_changes,
        experience=exp,
        audit=audit
    )

    home = WorkerHome(workspace_dir)
    try:
        if soul_md is not None:
            vault.mirror_soul(worker.uid, soul_md)
            home.write_soul(worker.uid, soul_md)

        history_line = f"- {exp.created_at} [[task-{task.id}]] {exp.outcome}: {exp.summary}"
        vault.append_history(worker.uid, history_line)
        home.append_history(worker.uid, history_line)

        vault.write_experience(exp, task)
        vault.write_task(task)

        await store.mark_vault_synced(exp.id)
    except OSError:
        import logging
        logging.getLogger(__name__).warning("Vault sync failed due to OSError")

    return RunOutcome(
        status=status,
        reason=reason,
        result_payload=result_payload,
        experience=exp,
        soul_md=soul_md
    )
