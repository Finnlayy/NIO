#!/usr/bin/env python3
"""End-to-End-Abnahme fuer die Telegram-Integration (offline).

Echte Kanban-Runtime, echter SQLite-Store und echte Verdrahtung, nur Telegram ist der
``FakeTelegramClient``. Geprueft wird:
- Bestehende Historie eines neuen Chats erzeugt nichts.
- Feed-Nachricht -> Signal -> Vorschlag an den gepaarten Bot + Kanban-Task.
- Ohne Klick geht nichts raus; ein Approve sendet genau einmal.
- Ein Ziel ausserhalb der Allowlist wird abgelehnt.
- Das Audit-Ledger bleibt intakt und enthaelt den Versand.

Nur Standardbibliothek. Fehler -> Exit 1 mit deutschem Befund.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from orchestrator.kanban.config import KanbanConfig  # noqa: E402
from orchestrator.kanban.runtime import build_runtime  # noqa: E402
from orchestrator.telegram.approvals import NotAllowed  # noqa: E402
from orchestrator.telegram.client import FakeTelegramClient  # noqa: E402
from orchestrator.telegram.config import TelegramConfig  # noqa: E402
from orchestrator.telegram.models import Suggestion, SuggestionStatus, TgMessage  # noqa: E402
from orchestrator.telegram.runtime import build_telegram_runtime  # noqa: E402
from orchestrator.telegram.symbols import SymbolIndex  # noqa: E402

FEED, BOT, STRANGER = -100, 200, 300
T0 = "2026-01-01T12:00:00.000Z"


def _pairs(_url: str) -> dict[str, object]:
    return {"error": [], "result": {"XBTUSD": {"wsname": "XBT/USD", "status": "online"}}}


def _msg(msg_id: int, text: str) -> TgMessage:
    return TgMessage(FEED, msg_id, "glint", text, T0, False, True)


def check(ok: object, message: str) -> None:
    if not ok:
        raise AssertionError(message)


async def run(root: Path) -> None:
    kanban = await build_runtime(
        KanbanConfig(
            repo_root=root,
            store="sqlite",
            sqlite_path=root / "kanban.db",
            bus="memory",
            sandbox="subprocess",
            workspace_dir=root / "ws",
            vault_dir=root / "vault",
        )
    )
    board = await kanban.service.create_board("telegram", actor="e2e")
    config = TelegramConfig.from_env(
        {"NIO_TELEGRAM_KANBAN_BOARD": board.id, "NIO_TELEGRAM_KANBAN_MIN_STRENGTH": "4"},
        repo_root=root,
    )
    client = FakeTelegramClient()
    client.fake_names["@glint_bot"] = BOT
    client.fake_messages.append(_msg(1, "BTC bullish breakout from last year"))
    tg = await build_telegram_runtime(config, kanban=kanban, client=client, symbols=SymbolIndex(root / "s.json", _pairs))
    try:
        await tg.symbols.ensure()
        await tg.monitor(FEED, actor="e2e")
        await tg.allow("@glint_bot", actor="e2e")
        await tg.pair(FEED, "@glint_bot", actor="e2e")

        await tg.gather.tick()
        check(not await tg.store.list_signals(), "Historie erzeugte Signale")

        await client.push(_msg(2, "BTC bullish breakout"))
        report = await tg.gather.tick()
        check(report.routed == 1 and not report.errors, f"Gather-Bericht unerwartet: {report}")

        signals = await tg.store.list_signals()
        check(len(signals) == 1 and signals[0].symbol == "BTC", "Signal fehlt")
        suggestions = await tg.store.list_suggestions(SuggestionStatus.PENDING)
        check(len(suggestions) == 1 and suggestions[0].target_peer == BOT, "Vorschlag fehlt")
        check(not client.sent, "Ohne Klick wurde gesendet")
        tasks = await kanban.store.list_tasks(board_id=board.id)
        check(len(tasks) == 1 and tasks[0].status.value == "triage", "Kanban-Task fehlt")

        sent = await tg.approvals.approve(suggestions[0].id, actor="e2e")
        check(sent.status is SuggestionStatus.SENT, f"Status {sent.status}")
        check(client.sent == [(BOT, sent.text)], f"Versand unerwartet: {client.sent}")

        await tg.store.add_suggestion(Suggestion("fremd", FEED, STRANGER, "x", 2, "llm", SuggestionStatus.PENDING, T0, None, None))
        try:
            await tg.approvals.approve("fremd", actor="e2e")
        except NotAllowed:
            pass
        else:
            raise AssertionError("Ziel ausserhalb der Allowlist wurde gesendet")
        check(len(client.sent) == 1, "Fremdes Ziel erreichte den Client")

        check(not await kanban.ledger.verify(), "Audit-Ledger ist beschaedigt")
        actions = {e.action for e in await kanban.ledger.entries(limit=1000)}
        check({"telegram.sent", "telegram.send_refused"} <= actions, f"Audit unvollstaendig: {sorted(actions)}")
    finally:
        await tg.close()
        await kanban.close()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="neu-telegram-e2e-") as tmp:
        try:
            asyncio.run(run(Path(tmp)))
        except AssertionError as exc:
            print(f"[e2e-telegram] FEHLGESCHLAGEN: {exc}", file=sys.stderr)
            return 1
    print("[e2e-telegram] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
