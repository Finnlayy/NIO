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
from core.protocol import Intent, Result, sha256_bytes, sha256_file, utc_now_iso


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


def write_jsonl_atomic(path: Path | str, records: Iterable[Mapping[str, Any]]) -> Path:
    """Schreibt JSON-Lines (``compacted``-Snapshots) crash-sicher und kompakt."""
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
            for record in records:
                handle.write(json.dumps(dict(record), ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(handle.name, target)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise
    return target


def read_jsonl(path: Path | str) -> list[dict[str, Any]]:
    """Liest eine JSONL-Datei; leere/fehlende Datei ergibt eine leere Liste."""
    source = Path(path)
    if not source.is_file():
        return []
    records: list[dict[str, Any]] = []
    with open(source, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            parsed = json.loads(line)
            if isinstance(parsed, Mapping):
                records.append(dict(parsed))
    return records


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

    # ----------------------------------------------------- Kompaktierung
    def archive_stats(self) -> dict[str, Any]:
        """Zaehlt Archiv-Eintraege und Bytes pro Tag (inkl. ``compacted/``)."""
        archive = self.config.archive_dir
        stats: dict[str, Any] = {"days": {}, "total_entries": 0, "total_bytes": 0, "compacted": {}}
        if not archive.is_dir():
            return stats
        compact_dir = archive / "compacted"
        for day_dir in sorted(p for p in archive.iterdir() if p.is_dir() and p.name != "compacted"):
            entries = [p for p in day_dir.iterdir() if p.is_dir()]
            bytes_day = sum(f.stat().st_size for e in entries for f in e.iterdir() if f.is_file())
            stats["days"][day_dir.name] = {"entries": len(entries), "bytes": bytes_day}
            stats["total_entries"] += len(entries)
            stats["total_bytes"] += bytes_day
        if compact_dir.is_dir():
            for snappy in sorted(compact_dir.glob("*.jsonl")):
                stats["compacted"][snappy.stem] = {"records": len(read_jsonl(snappy)), "bytes": snappy.stat().st_size}
        return stats

    def _read_archive_entry(self, entry: Path, day: str) -> dict[str, Any] | None:
        """Liest einen Einzeleintrag ``<day>/<intent_id>`` in ein Snapshot-Record."""
        intent_p = entry / "intent.json"
        result_p = entry / "result.json"
        if not intent_p.is_file() or not result_p.is_file():
            return None
        record: dict[str, Any] = {"day": day, "intent_id": entry.name, "files": {}, "sha256": {}}
        for name in ("intent.json", "result.json", "verdict.json"):
            candidate = entry / name
            if candidate.is_file():
                content = read_json(candidate)
                record["files"][name] = content
                # Kanonische Form (kompaktes JSON) hashen, damit der Snapshot
                # unabhaengig von der Datei-Formatierung (indent/Zeilenende)
                # verifizierbar ist.
                record["sha256"][name] = sha256_bytes(
                    json.dumps(content, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                )
        record["archived_at"] = utc_now_iso()
        return record

    def compact_archive(self, *, older_than_days: int | None = None, keep_recent: int = 0) -> dict[str, Any]:
        """Schnappschusst + pruent veraltete Archiv-Eintraege (bounded ledger).

        Pro Tag werden alte ``<intent_id>``-Verzeichnisse in eine einzelne
        ``compacted/<day>.jsonl``-Datei zusammengefuehrt (inkl. SHA-256-Manifest),
        danach werden die Einzelverzeichnisse entfernt. Die *juengsten*
        ``keep_recent`` Eintraege bleiben als Verzeichnisse bestehen, damit
        ``attempt.archive_dir`` (frisch archivierte Durchgaenge) weiterhin lesbar
        ist. Kein Eintrag geht verloren -- jeder wird zuerst vollstaendig und
        checksummiert in das Snapshot geschrieben, *bevor* geloescht wird.
        """
        archive = self.config.archive_dir
        summary: dict[str, Any] = {"compacted_entries": [], "pruned_dirs": 0, "bytes_freed": 0, "snapshot_bytes": 0, "days": {}}
        if not archive.is_dir():
            return summary
        compact_dir = archive / "compacted"
        now = time.time()
        day_dirs = sorted(p for p in archive.iterdir() if p.is_dir() and p.name != "compacted")
        for day_dir in day_dirs:
            day = day_dir.name
            entries = sorted([p for p in day_dir.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime)
            if not entries:
                continue
            keep_set = set(entries[-keep_recent:]) if keep_recent > 0 else set()
            to_compact: list[tuple[Path, dict[str, Any]]] = []
            freed = 0
            for entry in entries:
                if entry in keep_set:
                    continue
                if older_than_days is not None:
                    try:
                        age_days = (now - entry.stat().st_mtime) / 86400.0
                    except OSError:
                        continue
                    if age_days < older_than_days:
                        continue
                record = self._read_archive_entry(entry, day)
                if record is None:
                    continue
                to_compact.append((entry, record))
                freed += sum(f.stat().st_size for f in entry.iterdir() if f.is_file())
                summary["compacted_entries"].append(entry.name)
            if not to_compact:
                continue
            compact_dir.mkdir(parents=True, exist_ok=True)
            snappy = compact_dir / f"{day}.jsonl"
            merged: dict[str, dict[str, Any]] = {
                str(r.get("intent_id")): r for r in read_jsonl(snappy) if r.get("intent_id")
            }
            for _entry, record in to_compact:
                merged[record["intent_id"]] = record
            new_lines = [merged[key] for key in sorted(merged)]
            write_jsonl_atomic(snappy, new_lines)
            write_json_atomic(
                compact_dir / f"{day}.manifest.json",
                {
                    "day": day,
                    "count": len(new_lines),
                    "entries": {intent_id: {"sha256": rec.get("sha256", {}), "files": sorted(rec.get("files", {}))} for intent_id, rec in merged.items()},
                },
            )
            for entry, _record in to_compact:
                shutil.rmtree(entry, ignore_errors=True)
                summary["pruned_dirs"] += 1
            summary["days"][day] = {"compacted": len(to_compact), "snapshot_records": len(new_lines)}
            summary["snapshot_bytes"] += snappy.stat().st_size
            summary["bytes_freed"] += freed
        return summary

    def verify_archive(self) -> list[str]:
        """Prueft die ``compacted``-Snapshots gegen ihre SHA-256-Manifeste."""
        archive = self.config.archive_dir
        compact_dir = archive / "compacted"
        violations: list[str] = []
        if not compact_dir.is_dir():
            return violations
        for manifest_path in sorted(compact_dir.glob("*.manifest.json")):
            day = manifest_path.stem.replace(".manifest", "")
            manifest = read_json(manifest_path)
            # Fuer jeden Intent die Dateien im Snapshot re-hashen und vergleichen.
            for record in read_jsonl(compact_dir / f"{day}.jsonl"):
                intent_id = str(record.get("intent_id", ""))
                expected = manifest.get("entries", {}).get(intent_id, {}).get("sha256", {})
                for filename, expected_hex in expected.items():
                    content = record.get("files", {}).get(filename)
                    if content is None:
                        violations.append(f"{day}/{intent_id}/{filename}: fehlt im Snapshot")
                        continue
                    actual = sha256_bytes(json.dumps(content, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
                    if actual != expected_hex:
                        violations.append(f"{day}/{intent_id}/{filename}: SHA-256 verletzt")
        return violations
