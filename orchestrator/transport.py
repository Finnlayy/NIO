"""Datei-Transport des Orchestrators (Phase 1).

Der Orchestrator spricht mit Limbs ueber das Dateisystem, nicht ueber Sockets.
Das hat drei Gruende:

1. **Nachvollziehbarkeit** -- jeder Auftrag und jedes Ergebnis bleibt als JSON
   liegen (``runtime/inbox``, ``runtime/outbox``, ``runtime/archive``).
2. **Sprachneutralitaet** -- ein Limb in Node, Rust oder Bash liest dieselbe
   Datei. Kein RPC-Framework noetig.
3. **Absturzsicherheit** -- liegt ein Intent in der Inbox, kann er nach einem
   Crash erneut zugestellt werden.

Alle Schreibvorgaenge sind atomar (Temp-Datei + ``os.replace``).
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.config import NeuConfig
from core.protocol import Intent, Result, sha256_file, utc_now_iso


@dataclass(frozen=True)
class QueueState:
    inbox: dict[str, int]
    outbox: int
    archived: int
    backups: int

    def to_dict(self) -> dict[str, Any]:
        return {"inbox": dict(self.inbox), "outbox": self.outbox, "archived": self.archived, "backups": self.backups}


def write_json_atomic(path: Path | str, data: Mapping[str, Any] | Iterable[Any], *, indent: int | None = 2) -> Path:
    """Schreibt JSON crash-sicher: erst Temp-Datei, dann atomares Umbenennen."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(  # noqa: SIM115 - delete=False ist Absicht: os.replace braucht die Datei
        "w",
        encoding="utf-8",
        delete=False,
        dir=str(target.parent),
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    try:
        with handle:
            json.dump(data, handle, ensure_ascii=False, indent=indent)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(handle.name, target)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise
    return target


def read_json(path: Path | str) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


class FileTransport:
    """Inbox/Outbox/Archiv/Backups -- das Gedächtnis der Pipeline."""

    def __init__(self, config: NeuConfig | None = None) -> None:
        self.config = config or NeuConfig.load()
        self.config.ensure_dirs()

    # ---------------------------------------------------------------- Inbox
    def inbox_dir(self, limb: str) -> Path:
        return self.config.inbox_dir / limb

    def submit(self, intent: Intent, *, iteration: int = 1) -> Path:
        """Legt einen Intent in der Inbox des Ziellimbs ab."""
        directory = self.inbox_dir(intent.target_limb)
        directory.mkdir(parents=True, exist_ok=True)
        suffix = "" if iteration <= 1 else f".d{iteration}"
        return write_json_atomic(directory / f"{intent.intent_id}{suffix}.json", intent.to_dict())

    def drain_inbox(self, limb: str | None = None) -> list[Path]:
        """Liefert alle offenen Intent-Dateien (aelteste zuerst)."""
        roots = [self.inbox_dir(limb)] if limb else [p for p in self.config.inbox_dir.iterdir() if p.is_dir()]
        pending: list[Path] = []
        for root in roots:
            if not root.is_dir():
                continue
            pending.extend(sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime))
        return pending

    def consume(self, path: Path | str) -> None:
        """Entfernt eine verarbeitete Intent-Datei aus der Inbox."""
        Path(path).unlink(missing_ok=True)

    # --------------------------------------------------------------- Outbox
    def deliver_result(self, result: Result) -> Path:
        write_json_atomic(self.config.outbox_dir / f"{result.result_id}.json", result.to_dict())
        return self.config.outbox_dir / f"{result.result_id}.json"

    def drain_outbox(self) -> list[Path]:
        return sorted(self.config.outbox_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)

    # -------------------------------------------------------------- Archiv
    def archive(self, intent: Intent, result: Result, extra: Mapping[str, Any] | None = None) -> Path:
        """Legt Intent + Result (+ Verdict) dauerhaft zusammen ab."""
        day = time.strftime("%Y-%m-%d", time.gmtime())
        target = self.config.archive_dir / day / intent.intent_id
        target.mkdir(parents=True, exist_ok=True)
        write_json_atomic(target / "intent.json", intent.to_dict())
        write_json_atomic(target / f"result.iteration{result.iteration}.json", result.to_dict())
        write_json_atomic(target / "result.json", result.to_dict())
        if extra:
            write_json_atomic(target / "verdict.json", dict(extra))
        return target

    # ------------------------------------------------------------- Backups
    def backup_file(self, path: Path | str, *, reason: str = "") -> Path | None:
        """Sichert eine Datei vor der Veraenderung (fuer den Ouroboros-Fall)."""
        source = Path(path)
        if not source.is_file():
            return None
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        safe_name = self.config.relative(source).replace("/", ">").replace(os.sep, ">")
        target = self.config.backup_dir / f"{stamp}__{safe_name}"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if reason:
            write_json_atomic(target.with_suffix(target.suffix + ".meta.json"), {"reason": reason, "source": self.config.relative(source), "sha256": sha256_file(source), "at": utc_now_iso()})
        return target

    # ---------------------------------------------------------------- Stand
    def state(self) -> QueueState:
        inbox: dict[str, int] = {}
        if self.config.inbox_dir.is_dir():
            for limb_dir in sorted(p for p in self.config.inbox_dir.iterdir() if p.is_dir()):
                inbox[limb_dir.name] = len(list(limb_dir.glob("*.json")))
        outbox = len(list(self.config.outbox_dir.glob("*.json"))) if self.config.outbox_dir.is_dir() else 0
        archived = len(list(self.config.archive_dir.glob("*/*"))) if self.config.archive_dir.is_dir() else 0
        backups = len(list(self.config.backup_dir.glob("*"))) if self.config.backup_dir.is_dir() else 0
        return QueueState(inbox=inbox, outbox=outbox, archived=archived, backups=backups)
