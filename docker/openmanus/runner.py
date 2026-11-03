"""Fuehrt genau einen OpenManus-Auftrag aus und schreibt ``workspace/out/result.json``.

Der Upstream-Code bleibt unveraendert. Dieser Runner umgeht seine Bruchstellen:

- ``app.tool`` importiert die Websuche beim Laden. Ohne Internet ist sie wertlos,
  ihre Pakete fehlen im Image und werden hier durch leere Module ersetzt.
- Rueckfragen haben keinen Empfaenger, ``ask_human`` wird entfernt.
- Der Agent setzt seinen Zustand nach dem Lauf zurueck. Das Ende wird deshalb aus der
  ``terminate``-Nachricht gelesen. Fehlt sie, gilt der Lauf als fehlgeschlagen.

Die Laufzeitgrenze sitzt hier im Container. Sie greift auch dann, wenn niemand
``openmanus.status`` abfragt.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import signal
import sys
import types
from pathlib import Path
from typing import Any

ROOT = Path("/app/OpenManus")
OUT = ROOT / "workspace" / "out"
TASK = ROOT / "config" / "task.txt"
TIMEOUT_EXIT = 124
MAX_SUMMARY_CHARS = 8000


def write_result(state: str, **fields: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "result.json").write_text(json.dumps({"state": state, **fields}, ensure_ascii=False, indent=2), encoding="utf-8")


def on_alarm(_signum: int, _frame: Any) -> None:
    write_result("timeout", error="Laufzeit im Container ueberschritten.")
    os._exit(TIMEOUT_EXIT)


def stub_search_packages() -> None:
    for name, attributes in (
        ("duckduckgo_search", {"DDGS": object}),
        ("baidusearch", {}),
        ("baidusearch.baidusearch", {"search": None}),
        ("googlesearch", {"search": None}),
    ):
        module = types.ModuleType(name)
        module.__dict__.update(attributes)
        sys.modules[name] = module


def terminate_status(messages: list[Any]) -> str:
    """Status aus der letzten ``terminate``-Nachricht, sonst leer."""
    for message in reversed(messages):
        if getattr(message, "name", None) == "terminate":
            found = re.search(r"completed with status: (success|failure)", message.content or "")
            return found.group(1) if found else ""
    return ""


def last_answer(messages: list[Any]) -> str:
    for message in reversed(messages):
        if message.role == "assistant" and message.content:
            return str(message.content)[:MAX_SUMMARY_CHARS]
    return ""


async def run(prompt: str, max_steps: int) -> None:
    stub_search_packages()
    sys.path.insert(0, str(ROOT))
    from app.agent.manus import Manus

    agent = await Manus.create(max_steps=max_steps)
    tools = agent.available_tools
    tools.tools = tuple(tool for tool in tools.tools if tool.name != "ask_human")
    tools.tool_map.pop("ask_human", None)
    try:
        await agent.run(prompt)
    finally:
        await agent.cleanup()

    messages = agent.memory.messages
    status = terminate_status(messages)
    fields = {"steps": agent.current_step, "summary": last_answer(messages)}
    if status == "success":
        write_result("succeeded", **fields)
    else:
        write_result("failed", error=f"Kein erfolgreiches terminate (Status: {status or 'fehlt'}).", **fields)


def main() -> int:
    signal.signal(signal.SIGALRM, on_alarm)
    signal.alarm(int(os.environ["NIO_MAX_RUNTIME_S"]))
    try:
        asyncio.run(run(TASK.read_text(encoding="utf-8"), int(os.environ.get("NIO_MAX_STEPS", "20"))))
    except Exception as exc:
        write_result("failed", error=f"{type(exc).__name__}: {exc}"[:1000])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
