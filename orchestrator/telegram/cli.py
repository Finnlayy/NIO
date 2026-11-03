"""CLI-Subkommandos ``neu telegram ...``.

Wie ``neu kanban``: jedes Kommando baut die Runtime, fuehrt eine Operation aus und
schliesst sie. Telegram wird nur verbunden, wenn das Kommando es braucht. Die
Telethon-Session gehoert einem Prozess: laeuft ``neu kanban serve``, gehen
verbindende Kommandos ueber API oder UI.

Login nur hier: Telefon und Code per Prompt, das 2FA-Passwort per ``getpass``. Nichts
davon landet in argv oder wird gespeichert.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import sys
from collections.abc import Awaitable, Callable
from typing import Any

from orchestrator.kanban.config import KanbanConfig
from orchestrator.kanban.runtime import build_runtime

from .approvals import Conflict, NotAllowed, RateLimited, SuggestionNotFound
from .client import TelegramError, TelegramFloodWait, TelethonClient
from .config import TelegramConfig
from .intel import ask
from .models import LoginState, SuggestionStatus
from .runtime import TelegramRuntime, build_telegram_runtime

__all__ = ["add_telegram_parser"]

_Handler = Callable[[argparse.Namespace, TelegramRuntime], Awaitable[int]]


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
        kanban = await build_runtime(KanbanConfig.from_env())
        tg = await build_telegram_runtime(TelegramConfig.from_env(), kanban=kanban)
        try:
            return await handler(args, tg)
        except (ValueError, LookupError, TelegramError, NotAllowed, Conflict, RateLimited) as e:
            label = "Vorschlag nicht gefunden" if isinstance(e, SuggestionNotFound) else e
            print(f"telegram: {label}", file=sys.stderr)
            return 1
        finally:
            await tg.close()
            await kanban.close()

    return lambda args: asyncio.run(_main(args))


def _online(handler: _Handler) -> _Handler:
    """Fuer Kommandos, die wirklich mit Telegram sprechen."""

    async def wrapped(args: argparse.Namespace, tg: TelegramRuntime) -> int:
        state = await tg.connect()
        if state is not LoginState.AUTHORIZED:
            print(f"telegram: Status {state.value}, erst neu telegram login", file=sys.stderr)
            return 1
        return await handler(args, tg)

    return wrapped


async def _login(args: argparse.Namespace, tg: TelegramRuntime) -> int:
    client = tg.client
    if not isinstance(client, TelethonClient):
        raise ValueError("Login braucht den Telethon-Client")
    state = await tg.connect()
    if state is LoginState.UNCONFIGURED:
        raise ValueError("NIO_TELEGRAM_API_ID und NIO_TELEGRAM_API_HASH fehlen")
    if state is not LoginState.AUTHORIZED:
        await client.send_code(input("Telefonnummer: ").strip())
        await client.sign_in_code(input("Code aus Telegram: ").strip())
        if await client.status() is LoginState.NEEDS_PASSWORD:
            await client.sign_in_password(getpass.getpass("2FA-Passwort: "))
    me = await client.me()
    _say(args, {"state": "authorized", "me": me}, f"eingeloggt als {(me or {}).get('username') or (me or {}).get('name')}")
    return 0


async def _status(args: argparse.Namespace, tg: TelegramRuntime) -> int:
    _say(args, await tg.status())
    return 0


async def _dialogs(args: argparse.Namespace, tg: TelegramRuntime) -> int:
    dialogs = await tg.client.dialogs()
    _say(args, dialogs, "\n".join(f"{d.id}  [{d.kind}{' bot' if d.is_bot else ''}]  {d.name}" for d in dialogs))
    return 0


async def _monitor_add(args: argparse.Namespace, tg: TelegramRuntime) -> int:
    peer = await tg.monitor(args.peer, actor="cli")
    _say(args, {"peer": peer}, f"ueberwacht ab jetzt: {peer}")
    return 0


async def _monitor_rm(args: argparse.Namespace, tg: TelegramRuntime) -> int:
    await tg.unmonitor(args.peer, actor="cli")
    _say(args, {"ok": True}, "entfernt")
    return 0


async def _monitor_ls(args: argparse.Namespace, tg: TelegramRuntime) -> int:
    peers = await tg.store.list_monitored()
    _say(args, peers, "\n".join(str(p) for p in peers))
    return 0


async def _pair(args: argparse.Namespace, tg: TelegramRuntime) -> int:
    source, target = await tg.pair(args.feed, args.bot, actor="cli")
    _say(args, {"source": source, "target": target}, f"{source} -> {target}")
    return 0


async def _unpair(args: argparse.Namespace, tg: TelegramRuntime) -> int:
    await tg.unpair(args.feed, actor="cli")
    _say(args, {"ok": True}, "entfernt")
    return 0


async def _pairings(args: argparse.Namespace, tg: TelegramRuntime) -> int:
    pairs = await tg.store.list_pairings()
    _say(args, [{"source": s, "target": t} for s, t in pairs.items()], "\n".join(f"{s} -> {t}" for s, t in pairs.items()))
    return 0


async def _allow_add(args: argparse.Namespace, tg: TelegramRuntime) -> int:
    peer = await tg.allow(args.peer, actor="cli")
    _say(args, {"peer": peer}, f"erlaubt: {peer}")
    return 0


async def _allow_rm(args: argparse.Namespace, tg: TelegramRuntime) -> int:
    await tg.disallow(args.peer, actor="cli")
    _say(args, {"ok": True}, "entfernt")
    return 0


async def _allow_ls(args: argparse.Namespace, tg: TelegramRuntime) -> int:
    peers = await tg.store.list_allowed()
    _say(args, peers, "\n".join(str(p) for p in peers))
    return 0


async def _gather(args: argparse.Namespace, tg: TelegramRuntime) -> int:
    await tg.symbols.ensure()
    report = await tg.gather.tick()
    _say(args, report.to_dict(), f"Chats {report.peers}, geholt {report.fetched}, geroutet {report.routed}, Fehler {len(report.errors)}")
    return 1 if report.errors else 0


async def _ask(args: argparse.Namespace, tg: TelegramRuntime) -> int:
    await tg.symbols.ensure()
    result = await ask(args.question, store=tg.store, symbols=tg.symbols, llm=tg.llm)
    _say(args, result, result["answer"])
    return 0


async def _suggestions_ls(args: argparse.Namespace, tg: TelegramRuntime) -> int:
    status = SuggestionStatus(args.status) if args.status else None
    rows = await tg.store.list_suggestions(status)
    _say(args, rows, "\n".join(f"{s.id}  [{s.status.value}/{s.origin}]  -> {s.target_peer}  {s.text}" for s in rows))
    return 0


async def _suggestions_approve(args: argparse.Namespace, tg: TelegramRuntime) -> int:
    try:
        result = await tg.approvals.approve(args.id, actor="cli")
    except TelegramFloodWait as e:
        print(f"telegram: {e}", file=sys.stderr)
        return 1
    _say(args, result, f"{result.id}  [{result.status.value}]  {result.error or ''}".rstrip())
    return 0 if result.status is SuggestionStatus.SENT else 1


async def _suggestions_dismiss(args: argparse.Namespace, tg: TelegramRuntime) -> int:
    result = await tg.approvals.dismiss(args.id)
    _say(args, result, f"{result.id}  [{result.status.value}]")
    return 0


async def _suggestions_retry(args: argparse.Namespace, tg: TelegramRuntime) -> int:
    result = await tg.approvals.retry(args.id)
    _say(args, result, f"{result.id}  [{result.status.value}]")
    return 0


async def _approvals_ls(args: argparse.Namespace, tg: TelegramRuntime) -> int:
    rows = await tg.approvals.pending()
    _say(args, rows, "\n".join(f"{a.id}  {a.title}" for a in rows))
    return 0


async def _approvals_decide(args: argparse.Namespace, tg: TelegramRuntime) -> int:
    result = await tg.approvals.decide(args.id, args.decision == "approve", actor="cli")
    _say(args, result, f"{result.id}  [{result.status.value}]")
    return 0


async def _signals_ls(args: argparse.Namespace, tg: TelegramRuntime) -> int:
    rows = await tg.store.list_signals(limit=args.limit, symbol=args.symbol)
    _say(
        args,
        rows,
        "\n".join(f"{s.created_at}  {s.symbol} {s.direction.value} {s.strength}/10  {s.kanban_task_id or ''}".rstrip() for s in rows),
    )
    return 0


def add_telegram_parser(sub: Any, parser_class: type[argparse.ArgumentParser]) -> None:
    p_tg = sub.add_parser("telegram", help="Telegram: Feeds lesen, Signale, Vorschlaege freigeben")
    tsub = p_tg.add_subparsers(dest="telegram_cmd", required=True, parser_class=parser_class)

    tsub.add_parser("login", help="Interaktiver Login (Telefon, Code, 2FA)").set_defaults(func=_run(_login))
    tsub.add_parser("status", help="Verbindung, Gather, Symbole").set_defaults(func=_run(_status))
    tsub.add_parser("dialogs", help="Chats des Kontos").set_defaults(func=_run(_online(_dialogs)))

    monitor = tsub.add_parser("monitor", help="Ueberwachte Chats").add_subparsers(
        dest="monitor_cmd", required=True, parser_class=parser_class
    )
    p = monitor.add_parser("add")
    p.add_argument("peer")
    p.set_defaults(func=_run(_online(_monitor_add)))
    p = monitor.add_parser("rm")
    p.add_argument("peer")
    p.set_defaults(func=_run(_monitor_rm))
    monitor.add_parser("ls").set_defaults(func=_run(_monitor_ls))

    p = tsub.add_parser("pair", help="Feed mit Bot verbinden: Ziel der Vorschlaege")
    p.add_argument("feed")
    p.add_argument("bot")
    p.set_defaults(func=_run(_online(_pair)))
    p = tsub.add_parser("unpair")
    p.add_argument("feed")
    p.set_defaults(func=_run(_unpair))
    tsub.add_parser("pairings").set_defaults(func=_run(_pairings))

    allow = tsub.add_parser("allow", help="Erlaubte Sendeziele").add_subparsers(dest="allow_cmd", required=True, parser_class=parser_class)
    p = allow.add_parser("add")
    p.add_argument("peer")
    p.set_defaults(func=_run(_online(_allow_add)))
    p = allow.add_parser("rm")
    p.add_argument("peer")
    p.set_defaults(func=_run(_allow_rm))
    allow.add_parser("ls").set_defaults(func=_run(_allow_ls))

    tsub.add_parser("gather", help="Ein Gather-Durchlauf").set_defaults(func=_run(_online(_gather)))

    p = tsub.add_parser("ask", help="Frage an den lokalen Feed-Cache")
    p.add_argument("question")
    p.set_defaults(func=_run(_ask))

    suggestions = tsub.add_parser("suggestions", help="Vorschlaege").add_subparsers(
        dest="suggestions_cmd", required=True, parser_class=parser_class
    )
    p = suggestions.add_parser("ls")
    p.add_argument("--status", default=None, choices=[s.value for s in SuggestionStatus])
    p.set_defaults(func=_run(_suggestions_ls))
    p = suggestions.add_parser("approve", help="Sendet den Vorschlag")
    p.add_argument("id")
    p.set_defaults(func=_run(_online(_suggestions_approve)))
    p = suggestions.add_parser("dismiss")
    p.add_argument("id")
    p.set_defaults(func=_run(_suggestions_dismiss))
    p = suggestions.add_parser("retry", help="Fehlgeschlagenen Vorschlag wieder oeffnen")
    p.add_argument("id")
    p.set_defaults(func=_run(_suggestions_retry))

    approvals = tsub.add_parser("approvals", help="Orchestrator-Freigaben").add_subparsers(
        dest="approvals_cmd", required=True, parser_class=parser_class
    )
    approvals.add_parser("ls").set_defaults(func=_run(_approvals_ls))
    p = approvals.add_parser("decide")
    p.add_argument("id")
    p.add_argument("decision", choices=("approve", "reject"))
    p.set_defaults(func=_run(_approvals_decide))

    signals = tsub.add_parser("signals", help="Signale").add_subparsers(dest="signals_cmd", required=True, parser_class=parser_class)
    p = signals.add_parser("ls")
    p.add_argument("--symbol", default=None)
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=_run(_signals_ls))
