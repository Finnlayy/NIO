"""CLI-Subkommandos ``neu kanban ...`` fuer das Hermes-Kanban.

Jedes Kommando baut die Runtime aus ``KanbanConfig.from_env()``, fuehrt genau
eine Operation aus und schliesst sie wieder -- der Zustand lebt im Store, nicht
im Prozess. Nur ``serve`` laeuft dauerhaft (Dispatcher + Reaper + optional API).
Mit dem globalen ``--json`` gibt jedes Kommando genau ein JSON-Dokument aus.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import signal
import sys
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from orchestrator.kanban.config import KanbanConfig
from orchestrator.kanban.models import TaskStatus, TransitionError
from orchestrator.kanban.runtime import KanbanRuntime, build_runtime
from orchestrator.kanban.service import ConflictError

__all__ = ["add_kanban_parser"]

_Handler = Callable[[argparse.Namespace, KanbanRuntime], Awaitable[int]]


def _plain(data: Any) -> Any:
    if hasattr(data, "to_dict"):
        return data.to_dict()
    if isinstance(data, list):
        return [_plain(d) for d in data]
    return data


def _say(args: argparse.Namespace, data: Any, text: str | None = None) -> None:
    if getattr(args, "json", False) or text is None:
        print(json.dumps(_plain(data), ensure_ascii=False, indent=None if getattr(args, "json", False) else 2))
    else:
        print(text)


def _run(handler: _Handler) -> Callable[[argparse.Namespace], int]:
    async def _main(args: argparse.Namespace) -> int:
        runtime = await build_runtime(KanbanConfig.from_env())
        try:
            return await handler(args, runtime)
        except (ValueError, TransitionError, ConflictError) as e:
            print(f"kanban: {e}", file=sys.stderr)
            return 1
        finally:
            await runtime.close()

    return lambda args: asyncio.run(_main(args))


async def _init(args: argparse.Namespace, rt: KanbanRuntime) -> int:
    where = (rt.config.pg_dsn and "postgres") or str(rt.config.sqlite_path)
    _say(args, {"ok": True, "store": rt.config.store, "location": where}, f"Kanban-Store bereit: {where}")
    return 0


async def _board_create(args: argparse.Namespace, rt: KanbanRuntime) -> int:
    board = await rt.service.create_board(args.name, actor="cli")
    _say(args, board, f"{board.id}  {board.name}")
    return 0


async def _board_list(args: argparse.Namespace, rt: KanbanRuntime) -> int:
    boards = await rt.store.list_boards()
    _say(args, boards, "\n".join(f"{b.id}  {b.name}" for b in boards))
    return 0


async def _task_create(args: argparse.Namespace, rt: KanbanRuntime) -> int:
    desc = Path(args.description_file).read_text(encoding="utf-8") if args.description_file else args.description
    task = await rt.service.create_task(
        board_id=args.board,
        title=args.title,
        description=desc,
        parent_id=args.parent,
        dependencies=tuple(args.dep),
        required_skills=tuple(args.skill),
        priority=args.priority,
        status=TaskStatus(args.status),
        workspace_repo=args.repo,
        actor="cli",
    )
    _say(args, task, f"{task.id}  [{task.status.value}]  {task.title}")
    return 0


async def _task_list(args: argparse.Namespace, rt: KanbanRuntime) -> int:
    status = TaskStatus(args.status) if args.status else None
    tasks = await rt.store.list_tasks(board_id=args.board, status=status)
    _say(args, tasks, "\n".join(f"{t.id}  [{t.status.value}]  {t.title}" for t in tasks))
    return 0


async def _task_show(args: argparse.Namespace, rt: KanbanRuntime) -> int:
    _say(args, await rt.service.show(args.id))
    return 0


async def _task_transition(args: argparse.Namespace, rt: KanbanRuntime) -> int:
    task = await rt.service.transition(args.id, TaskStatus(args.status), actor="cli", reason=args.reason)
    _say(args, task, f"{task.id}  [{task.status.value}]  {task.title}")
    return 0


async def _worker_create(args: argparse.Namespace, rt: KanbanRuntime) -> int:
    soul = Path(args.soul_file).read_text(encoding="utf-8") if args.soul_file else ""
    worker = await rt.service.create_worker(
        uid=args.uid, name=args.name or args.uid, skills=list(args.skill), soul_md=soul, actor="cli"
    )
    _say(args, worker, f"{worker.uid}  {worker.name}  skills={','.join(worker.skills)}")
    return 0


async def _worker_list(args: argparse.Namespace, rt: KanbanRuntime) -> int:
    workers = await rt.store.list_workers()
    _say(args, workers, "\n".join(f"{w.uid}  [{w.status.value}]  skills={','.join(w.skills)}" for w in workers))
    return 0


async def _tick(args: argparse.Namespace, rt: KanbanRuntime) -> int:
    report = await rt.dispatcher.tick(wait=args.wait)
    reaped = await rt.reaper.tick()
    data = {"dispatcher": asdict(report), "reaped": reaped}
    _say(args, data, f"tick: {data['dispatcher']}  reaped={len(reaped)}")
    return 0


async def _audit_verify(args: argparse.Namespace, rt: KanbanRuntime) -> int:
    errors = await rt.ledger.verify()
    _say(args, {"ok": not errors, "errors": errors}, "audit: OK" if not errors else "audit: FEHLER\n" + "\n".join(errors))
    return 0 if not errors else 1


async def _audit_tail(args: argparse.Namespace, rt: KanbanRuntime) -> int:
    entries = (await rt.ledger.entries(limit=10**9))[-args.n :]
    _say(args, entries, "\n".join(f"{e.seq:>6}  {e.ts}  {e.actor:<20} {e.action:<24} {e.subject}" for e in entries))
    return 0


async def _serve(args: argparse.Namespace, rt: KanbanRuntime) -> int:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)

    jobs = [asyncio.create_task(rt.serve(stop))]
    if not args.no_api:
        try:
            import uvicorn

            from orchestrator.kanban.api import build_app
        except ImportError:
            print("kanban: API nicht gestartet -- Extra 'kanban' (fastapi, uvicorn) fehlt", file=sys.stderr)
        else:
            if not rt.config.api_token:
                print("kanban: NIO_KANBAN_API_TOKEN fehlt -- Operator-Routen antworten 503", file=sys.stderr)
            server = uvicorn.Server(uvicorn.Config(build_app(rt), host=args.host or rt.config.api_host,
                                                   port=args.port or rt.config.api_port, log_level="info"))
            # uvicorn faengt SIGINT/SIGTERM waehrend ``serve()`` selbst ab: wer zuerst
            # endet (API oder ``stop``), beendet den jeweils anderen.
            async def _api() -> None:
                watch = asyncio.create_task(stop.wait())
                api = asyncio.create_task(server.serve())
                await asyncio.wait({watch, api}, return_when=asyncio.FIRST_COMPLETED)
                server.should_exit = True
                stop.set()
                await api
                watch.cancel()

            jobs.append(asyncio.create_task(_api()))
    await asyncio.gather(*jobs)
    return 0


def add_kanban_parser(sub: Any, parser_class: type[argparse.ArgumentParser]) -> None:
    p_kanban = sub.add_parser("kanban", help="Hermes-Kanban: Boards, Tasks, Worker, Audit")
    ksub = p_kanban.add_subparsers(dest="kanban_cmd", required=True, parser_class=parser_class)

    ksub.add_parser("init", help="Store anlegen/migrieren").set_defaults(func=_run(_init))

    board = ksub.add_parser("board", help="Boards").add_subparsers(dest="board_cmd", required=True, parser_class=parser_class)
    p = board.add_parser("create")
    p.add_argument("name")
    p.set_defaults(func=_run(_board_create))
    board.add_parser("list").set_defaults(func=_run(_board_list))

    task = ksub.add_parser("task", help="Tasks").add_subparsers(dest="task_cmd", required=True, parser_class=parser_class)
    p = task.add_parser("create")
    p.add_argument("--board", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--description", default="")
    p.add_argument("--description-file", default=None)
    p.add_argument("--parent", default=None)
    p.add_argument("--dep", action="append", default=[])
    p.add_argument("--skill", action="append", default=[])
    p.add_argument("--priority", type=int, default=0)
    p.add_argument("--status", default=TaskStatus.TRIAGE.value, choices=[s.value for s in TaskStatus])
    p.add_argument("--repo", default=None)
    p.set_defaults(func=_run(_task_create))
    p = task.add_parser("list")
    p.add_argument("--board", default=None)
    p.add_argument("--status", default=None, choices=[s.value for s in TaskStatus])
    p.set_defaults(func=_run(_task_list))
    p = task.add_parser("show")
    p.add_argument("id")
    p.set_defaults(func=_run(_task_show))
    p = task.add_parser("transition")
    p.add_argument("id")
    p.add_argument("status", choices=[s.value for s in TaskStatus])
    p.add_argument("--reason", default="")
    p.set_defaults(func=_run(_task_transition))

    worker = ksub.add_parser("worker", help="Worker").add_subparsers(dest="worker_cmd", required=True, parser_class=parser_class)
    p = worker.add_parser("create")
    p.add_argument("uid")
    p.add_argument("--name", default="")
    p.add_argument("--skill", action="append", default=[])
    p.add_argument("--soul-file", default=None)
    p.set_defaults(func=_run(_worker_create))
    worker.add_parser("list").set_defaults(func=_run(_worker_list))

    p = ksub.add_parser("tick", help="Ein Dispatcher- und Reaper-Durchlauf")
    p.add_argument("--wait", action="store_true", help="auf gestartete Worker warten")
    p.set_defaults(func=_run(_tick))

    p = ksub.add_parser("serve", help="Dispatcher + Reaper dauerhaft, optional mit API")
    p.add_argument("--host", default=None)
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--no-api", action="store_true")
    p.set_defaults(func=_run(_serve))

    audit = ksub.add_parser("audit", help="Audit-Ledger").add_subparsers(dest="audit_cmd", required=True, parser_class=parser_class)
    audit.add_parser("verify").set_defaults(func=_run(_audit_verify))
    p = audit.add_parser("tail")
    p.add_argument("-n", type=int, default=20)
    p.set_defaults(func=_run(_audit_tail))
