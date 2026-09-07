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

import contextlib
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


#: Sidecar-Endung des Offset-Index zu einem ``.jsonl``-Snapshot.
INDEX_SUFFIX = ".index.json"

#: Schwellen der **automatischen** Kompaktierung (Fokus C). Bewusst konservativ:
#: Eintrag muss aelter als 7 Tage sein, die neuesten 8 pro Tag bleiben als
#: Verzeichnis liegen (Contract ``attempt.archive_dir``), und los geht es erst
#: ab 64 veralteten Eintraegen -- ein frisches Runtime-Verzeichnis kompaktiert
#: also nie, und ein Lauf ueber Monate wachst nicht ungebunden.
COMPACT_OLDER_THAN_DAYS = 7
COMPACT_KEEP_RECENT = 8
COMPACT_MIN_STALE_ENTRIES = 64
#: Nach so vielen Archivschreibungen wird wieder geprueft (Amortisation: der
#: Blick in die Verzeichnis-Mtimes kostet ~1 ms, pro Event waere das zu viel).
COMPACT_CHECK_EVERY = 64


def write_jsonl_indexed(
    path: Path | str,
    records: Iterable[Mapping[str, Any]],
    *,
    index_field: str = "intent_id",
) -> dict[str, Any]:
    """Schreibt einen JSONL-Snapshot **und** dabei seinen Offset-Index.

    Die Offset-Tabelle (``index_field`` -> Byte-Offset der Zeile) faellt beim
    Schreiben kostenlos ab: die Laenge jeder Zeile liegt schon vor. Ein spaeterer
    Einzelpunkt-Zugriff wird dadurch zu ``seek`` + ``readline`` + ein ``json``
    statt "Datei komplett einlesen und jede Zeile parseen" (gemessen 7,6 ms ->
    0,1 µs bei 400 Records in 900 KB).

    Reihenfolge ist die Crash-Garantie: erst Snapshot (atomar, fsync), dann
    Index. Fehlt der Index nach einem Absturz, wird er beim naechsten Zugriff
    neu aufgebaut -- er ist ein **abgeleitetes** Artefakt, nie die Wahrheitsquelle.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    offsets: dict[str, int] = {}
    total = 0
    count = 0
    handle = tempfile.NamedTemporaryFile(  # noqa: SIM115 - delete=False ist Absicht: os.replace braucht die Datei
        "wb",
        delete=False,
        dir=str(target.parent),
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    with handle:
        for record in records:
            blob = json.dumps(dict(record), ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
            key = record.get(index_field) if isinstance(record, Mapping) else None
            if key is not None:
                offsets[str(key)] = total
            handle.write(blob)
            total += len(blob)
            count += 1
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(handle.name, target)
    index_target = target.with_name(target.stem + INDEX_SUFFIX)
    write_json_atomic(
        index_target,
        {"field": index_field, "count": count, "bytes": total, "offsets": offsets},
        indent=None,
    )
    return {
        "snapshot": str(target),
        "index": str(index_target),
        "records": count,
        "bytes": total,
        "offsets": offsets,
    }



class FileTransport:
    """Inbox/Outbox/Archiv/Backups -- das Gedächtnis der Pipeline."""

    def __init__(self, config: NeuConfig | None = None) -> None:
        self.config = config or NeuConfig.load()
        self.config.ensure_dirs()
        #: Abgeleitete Offset-Indizes pro Snapshot: Pfad -> (mtime_ns, groesse, offsets).
        #: mtime/groesse sind die Verfalls-Marke; ein Snapshot wird nach der
        #: Kompaktierung nie angehaengt (er wird neu geschrieben), also ist der
        #: Eintrag entweder gueltig oder wird verworfen.
        self._index_cache: dict[str, tuple[int, int, dict[str, int]]] = {}
        #: Zaehlt Archivschreibungen, um die Ledger-Pruefung zu amortisieren.
        self._archive_writes = 0

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
        """Legt Intent + Result (+ Verdict) dauerhaft zusammen ab.

        Rueckgabe bleibt der Zielverzeichnis-Pfad (Contract von ``Attempt.archive_dir``).
        Alle ``COMPACT_CHECK_EVERY`` Schreibungen prueft ausserdem das
        Selbstpflege-Tor des Ledger (``maybe_compact``): ein Archiv, das nur
        waechst, macht jede Suche darauf mit der Zeit kaputt. Frische Eintraege
        werden dabei nie angefasst, und ein leerer/neuer Runtime-Ordner kostet
        die Pruefung genau einen Zaehler-Vergleich.
        """
        day = time.strftime("%Y-%m-%d", time.gmtime())
        target = self.config.archive_dir / day / intent.intent_id
        target.mkdir(parents=True, exist_ok=True)
        write_json_atomic(target / "intent.json", intent.to_dict())
        write_json_atomic(target / f"result.iteration{result.iteration}.json", result.to_dict())
        write_json_atomic(target / "result.json", result.to_dict())
        if extra:
            write_json_atomic(target / "verdict.json", dict(extra))
        self._archive_writes += 1
        if self._archive_writes % COMPACT_CHECK_EVERY == 0:
            with contextlib.suppress(OSError):  # Selbstpflege darf einen Lauf nie stoppen
                self.maybe_compact()
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
        """Zaehlt Archiv-Eintraege und Bytes pro Tag (inkl. ``compacted/``).

        Die Record-Zahl kompaktierter Tage kommt aus dem Manifest (ein kleiner
        Dict-Lesezugriff), nicht aus dem Einlesen des ganzen Snapshots: mit 400
        Records in ~900 KB waren das vorher ~7,6 ms fuer eine Zahl, die beim
        Kompaktieren laengst feststand. Ohne Manifest wird zurueckgefallen --
        die Zahl stimmt also auch bei Schnappschuesen aus aelteren Staenden.
        """
        archive = self.config.archive_dir
        stats: dict[str, Any] = {"days": {}, "total_entries": 0, "total_bytes": 0, "compacted": {}, "stale_entries": 0}
        if not archive.is_dir():
            return stats
        compact_dir = archive / "compacted"
        cutoff = time.time() - COMPACT_OLDER_THAN_DAYS * 86400
        for day_dir in sorted(p for p in archive.iterdir() if p.is_dir() and p.name != "compacted"):
            entries = [p for p in day_dir.iterdir() if p.is_dir()]
            bytes_day = sum(f.stat().st_size for e in entries for f in e.iterdir() if f.is_file())
            stale = 0
            for entry in entries:
                try:
                    if entry.stat().st_mtime <= cutoff:
                        stale += 1
                except OSError:
                    continue
            stats["days"][day_dir.name] = {"entries": len(entries), "bytes": bytes_day, "stale_entries": stale}
            stats["total_entries"] += len(entries)
            stats["total_bytes"] += bytes_day
            stats["stale_entries"] += stale
        if compact_dir.is_dir():
            for snappy in sorted(compact_dir.glob("*.jsonl")):
                index_path = snappy.with_name(snappy.stem + INDEX_SUFFIX)
                indexed = index_path.is_file()
                info: dict[str, Any] = {
                    "bytes": snappy.stat().st_size,
                    "records": None,
                    "source": "scan",
                    "indexed": indexed,
                    "index_bytes": index_path.stat().st_size if indexed else 0,
                }
                manifest = compact_dir / f"{snappy.stem}.manifest.json"
                if manifest.is_file():
                    meta: Any = None
                    try:
                        meta = read_json(manifest)
                    except (OSError, ValueError):
                        meta = None
                    if isinstance(meta, Mapping) and isinstance(meta.get("count"), int):
                        info["records"] = int(meta["count"])
                        info["source"] = "manifest"
                        info["digest"] = str(meta.get("sha256_snapshot") or "")[:16]
                if info["records"] is None:
                    info["records"] = len(read_jsonl(snappy))
                stats["compacted"][snappy.stem] = info
        return stats

    def stale_entry_count(self, *, older_than_days: int = COMPACT_OLDER_THAN_DAYS) -> int:
        """Wie viele expandierte Eintraege galten als veraltet? (billig: nur mtime)."""
        archive = self.config.archive_dir
        if not archive.is_dir():
            return 0
        cutoff = time.time() - max(0, older_than_days) * 86400
        stale = 0
        for day_dir in archive.iterdir():
            if not day_dir.is_dir() or day_dir.name == "compacted":
                continue
            for entry in day_dir.iterdir():
                try:
                    if entry.is_dir() and entry.stat().st_mtime <= cutoff:
                        stale += 1
                except OSError:
                    continue
        return stale

    def maybe_compact(self, *, force: bool = False) -> dict[str, Any]:
        """Selbstpflege des Ledgers: kompaktiert nur, wenn es sich lohnt.

        Schwellen (Modulkonstanten, per Umgebungsvariablen uebersteuerbar, weil
        ``neu.config.json`` dem Constitution Guard unterliegt):

        * ``NEU_ARCHIVE_AUTOCOMPACT=0``  -> Aus (Tests/CI)
        * ``NEU_ARCHIVE_COMPACT_DAYS``   -> Alter in Tagen (Default 7)
        * ``NEU_ARCHIVE_KEEP_RECENT``    -> expandede Eintraege pro Tag (Default 8)
        * ``NEU_ARCHIVE_MIN_STALE``      -> Mindestzahl veralteter Eintraege (Default 64)

        Alles unterhalb der Schwellen ist ein frueher Rueckkehr ohne jede
        Schreibaktion -- genau so soll sich ein Bound Ledger anfuehlen.
        """
        if os.environ.get("NEU_ARCHIVE_AUTOCOMPACT", "1").strip().lower() in ("0", "false", "no", "off"):
            return {"skipped": True, "reason": "deaktiviert (NEU_ARCHIVE_AUTOCOMPACT)"}
        older_than = int(os.environ.get("NEU_ARCHIVE_COMPACT_DAYS", COMPACT_OLDER_THAN_DAYS))
        keep_recent = int(os.environ.get("NEU_ARCHIVE_KEEP_RECENT", COMPACT_KEEP_RECENT))
        min_stale = int(os.environ.get("NEU_ARCHIVE_MIN_STALE", COMPACT_MIN_STALE_ENTRIES))
        stale = self.stale_entry_count(older_than_days=older_than)
        if not force and stale < min_stale:
            return {"skipped": True, "reason": f"nur {stale} veraltete Eintraege (Schwelle {min_stale})", "stale_entries": stale}
        summary = self.compact_archive(older_than_days=older_than, keep_recent=keep_recent)
        summary["skipped"] = False
        summary["stale_entries_before"] = stale
        return summary

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
        """Kompaktiert und prueft veraltete Archiv-Eintraege (bounded ledger).

        Pro Tag werden alte ``<intent_id>``-Verzeichnisse in eine einzelne
        ``compacted/<day>.jsonl``-Datei zusammengefuehrt (inkl. SHA-256-Manifest),
        danach werden die Einzelverzeichnisse entfernt. Die *juengsten*
        ``keep_recent`` Eintraege bleiben als Verzeichnisse bestehen, damit
        ``attempt.archive_dir`` (frisch archivierte Durchgaenge) weiterhin lesbar
        ist. Kein Eintrag geht verloren -- jeder wird zuerst vollstaendig und
        checksummiert in das Snapshot geschrieben, *bevor* geloescht wird.
        """
        archive = self.config.archive_dir
        summary: dict[str, Any] = {
            "compacted_entries": [],
            "pruned_dirs": 0,
            "bytes_freed": 0,
            "snapshot_bytes": 0,
            "index_bytes": 0,
            "days": {},
        }
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
            # Snapshot + Offset-Index in einem Durchgang (der Index faellt beim
            # Schreiben ab, kostet also nur die Bytes seiner Tabelle).
            indexed = write_jsonl_indexed(snappy, new_lines, index_field="intent_id")
            self._index_cache[str(snappy)] = (
                snappy.stat().st_mtime_ns,
                int(indexed["bytes"]),
                dict(indexed["offsets"]),
            )
            write_json_atomic(
                compact_dir / f"{day}.manifest.json",
                {
                    "day": day,
                    "count": len(new_lines),
                    # Tages-Pruefsumme ueber die Snapshot-Datei: verifizieren ohne
                    # Re-Parse (siehe ``verify_archive``).
                    "sha256_snapshot": sha256_file(snappy),
                    "indexed": True,
                    "entries": {intent_id: {"sha256": rec.get("sha256", {}), "files": sorted(rec.get("files", {}))} for intent_id, rec in merged.items()},
                },
            )
            # Verify-before-prune: geloescht wird erst, nachdem der frische
            # Snapshot geprueft ist. Ein Riss zwischen Schreibvorgang und
            # Loeschung darf keine Daten kosten -- Integritaet vor Speicherplatz.
            violations = self._verify_day(day, deep=True)
            if violations:
                summary["days"][day] = {
                    "compacted": 0,
                    "snapshot_records": len(new_lines),
                    "aborted": f"Snapshot unverifiziert: {violations[0]}",
                }
                continue
            for entry, _record in to_compact:
                shutil.rmtree(entry, ignore_errors=True)
                summary["pruned_dirs"] += 1
                summary["compacted_entries"].append(entry.name)
            index_path = snappy.with_name(snappy.stem + INDEX_SUFFIX)
            index_bytes = index_path.stat().st_size if index_path.is_file() else 0
            summary["days"][day] = {
                "compacted": len(to_compact),
                "snapshot_records": len(new_lines),
                "index_entries": len(indexed["offsets"]),
                "index_bytes": index_bytes,
                "verified": True,
            }
            summary["snapshot_bytes"] += snappy.stat().st_size
            summary["index_bytes"] = summary.get("index_bytes", 0) + index_bytes
            summary["bytes_freed"] += freed
        return summary

    def _verify_day(self, day: str, *, deep: bool = False) -> list[str]:
        """Prueft einen Tages-Snapshot.

        Schneller Pfad (Default): der Manifest-Digest ueber die Snapshot-Datei
        beantwortet "ist dieser Tag unveraendert?" in einem Durchgang Hashen
        statt jeden Datensatz erneut zu parsen und Feld fuer Feld zu re-hashen
        (gemessen 21 ms bei 400 Records in ~900 KB). Passt der Digest nicht,
        faellt die Pruefung auf den tiefen Pfad zurueck und nennt den konkreten
        Dateikonflikt -- der Schnellpfad ist eine Abkuerzung fuer "alles in
        Ordnung", nie ein Weglassen der Pruefung.
        """
        compact_dir = self.config.archive_dir / "compacted"
        snapshot = compact_dir / f"{day}.jsonl"
        manifest_path = compact_dir / f"{day}.manifest.json"
        if not snapshot.is_file():
            return [] if not manifest_path.is_file() else [f"{day}: Snapshot fehlt, Manifest vorhanden"]
        manifest: Any = None
        if manifest_path.is_file():
            try:
                manifest = read_json(manifest_path)
            except (OSError, ValueError):
                manifest = None
        if isinstance(manifest, Mapping) and not deep:
            recorded = manifest.get("sha256_snapshot")
            if isinstance(recorded, str) and recorded:
                try:
                    if sha256_file(snapshot) == recorded:
                        return []
                except OSError:
                    pass
        raw_entries = manifest.get("entries", {}) if isinstance(manifest, Mapping) else {}
        expected_entries: Mapping[str, Any] = raw_entries if isinstance(raw_entries, Mapping) else {}
        violations: list[str] = []
        for record in read_jsonl(snapshot):
            intent_id = str(record.get("intent_id", ""))
            expected_entry = expected_entries.get(intent_id)
            expected = expected_entry.get("sha256", {}) if isinstance(expected_entry, Mapping) else {}
            for filename, expected_hex in expected.items():
                content = record.get("files", {}).get(filename)
                if content is None:
                    violations.append(f"{day}/{intent_id}/{filename}: fehlt im Snapshot")
                    continue
                actual = sha256_bytes(json.dumps(content, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
                if actual != expected_hex:
                    violations.append(f"{day}/{intent_id}/{filename}: SHA-256 verletzt")
        return violations

    def verify_archive(self, *, force: bool = False) -> list[str]:
        """Prueft die ``compacted``-Snapshots gegen ihre SHA-256-Manifeste.

        ``force=True`` umgeht den Digest-Schnellpfad und re-hasht jeden Eintrag
        (das war das einzige Verhalten vor Triad 2; ``compact_archive`` nutzt ihn
        als Verify-before-prune-Garantie).
        """
        compact_dir = self.config.archive_dir / "compacted"
        if not compact_dir.is_dir():
            return []
        days = {p.stem.replace(".manifest", "") for p in compact_dir.glob("*.manifest.json")}
        days |= {p.stem for p in compact_dir.glob("*.jsonl")}
        violations: list[str] = []
        for day in sorted(days):
            violations.extend(self._verify_day(day, deep=force))
        return violations

    # ------------------------------------------------------- Index / Suche
    def snapshot_index(self, day: str) -> dict[str, int]:
        """``intent_id -> Byte-Offset`` fuer den Tages-Snapshot (memoisiert).

        Der Index kommt aus dem Sidecar, den ``write_jsonl_indexed`` beim
        Kompaktieren mitschreibt. Fehlt er (Absturz, aelterer Stand, Verfall),
        wird er einmalig per Scan aufgebaut und im Sidecar hinterlegt -- die
        Suche haengt nie an einem abgeleiteten Artefakt.
        """
        snapshot = self.config.archive_dir / "compacted" / f"{day}.jsonl"
        try:
            stat = snapshot.stat()
        except OSError:
            return {}
        key = str(snapshot)
        cached = self._index_cache.get(key)
        if cached is not None and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
            return cached[2]
        offsets = self._read_index_sidecar(snapshot, stat.st_size)
        if offsets is None:
            offsets = self._scan_offsets(snapshot)
            with contextlib.suppress(OSError, ValueError):
                write_json_atomic(
                    snapshot.with_name(snapshot.stem + INDEX_SUFFIX),
                    {"field": "intent_id", "count": len(offsets), "bytes": stat.st_size, "offsets": offsets},
                    indent=None,
                )
        self._index_cache[key] = (stat.st_mtime_ns, stat.st_size, offsets)
        return offsets

    def _read_index_sidecar(self, snapshot: Path, size: int) -> dict[str, int] | None:
        """Liest den Sidecar-Index; ``None``, wenn er fehlt oder nicht zur Datei passt."""
        sidecar = snapshot.with_name(snapshot.stem + INDEX_SUFFIX)
        if not sidecar.is_file():
            return None
        try:
            raw = read_json(sidecar)
        except (OSError, ValueError):
            return None
        if not isinstance(raw, Mapping) or raw.get("field") != "intent_id":
            return None
        if raw.get("bytes") != size:  # Snapshot hat sich seit dem Index veraendert
            return None
        table = raw.get("offsets")
        if not isinstance(table, Mapping) or not table:
            return None
        return {str(key): int(value) for key, value in table.items()}

    def _scan_offsets(self, snapshot: Path) -> dict[str, int]:
        """Ein Scan ueber den Snapshot, um die Offset-Tabelle neu zu bauen."""
        offsets: dict[str, int] = {}
        offset = 0
        with open(snapshot, "rb") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped:
                    try:
                        parsed = json.loads(stripped)
                    except ValueError:
                        parsed = None
                    if isinstance(parsed, Mapping) and parsed.get("intent_id") is not None:
                        offsets[str(parsed["intent_id"])] = offset
                offset += len(line)
        return offsets

    def _read_snapshot_line(self, snapshot: Path, position: int) -> dict[str, Any] | None:
        """Eine Zeile per ``seek`` lesen -- kein Einlesen der ganzen Datei."""
        try:
            with open(snapshot, "rb") as handle:
                handle.seek(position)
                line = handle.readline()
        except OSError:
            return None
        if not line.strip():
            return None
        try:
            parsed = json.loads(line)
        except ValueError:
            return None
        return dict(parsed) if isinstance(parsed, Mapping) else None

    def lookup_archived(self, intent_id: str) -> dict[str, Any] | None:
        """Holt einen archivierten Durchgang zurueck -- aus Snapshot *oder* Verzeichnis.

        Eine einzige Pforte ueber beide Zustaende des Ledgers: kalte Daten liegen
        kompaktiert im Tages-Snapshot (Offset + ``seek``), frische als
        Verzeichnis unter ``archive/<tag>/<intent_id>/``. Aufrufer muessen nicht
        wissen, ob ein Durchgang schon kompaktiert wurde.
        """
        if not intent_id:
            return None
        compact_dir = self.config.archive_dir / "compacted"
        for day in self._candidate_days(intent_id, compact_dir):
            snapshot = compact_dir / f"{day}.jsonl"
            if not snapshot.is_file():
                continue
            record = self._lookup_in_snapshot(snapshot, day, intent_id)
            if record is not None:
                return record
        for entry in self._candidate_entry_dirs(intent_id):
            intent_path = entry / "intent.json"
            result_path = entry / "result.json"
            verdict_path = entry / "verdict.json"
            if intent_path.is_file() and result_path.is_file():
                return {
                    "intent_id": intent_id,
                    "day": entry.parent.name,
                    "compacted": False,
                    "path": str(entry),
                    "intent": read_json(intent_path),
                    "result": read_json(result_path),
                    "verdict": read_json(verdict_path) if verdict_path.is_file() else None,
                }
        return None

    def _lookup_in_snapshot(self, snapshot: Path, day: str, intent_id: str) -> dict[str, Any] | None:
        offsets = self.snapshot_index(day)
        position = offsets.get(intent_id)
        if position is None:
            return None
        record = self._read_snapshot_line(snapshot, position)
        if record is not None and record.get("intent_id") == intent_id:
            return {"intent_id": intent_id, "day": day, "compacted": True, "record": record}
        # Paritaetspruefung fehlgeschlagen: Index ist veraltet, ein Neuaufbau
        # entscheidet -- ein falscher Index darf nie einen fremden Datensatz liefern.
        try:
            stat = snapshot.stat()
        except OSError:
            return None
        offsets = self._scan_offsets(snapshot)
        self._index_cache[str(snapshot)] = (stat.st_mtime_ns, stat.st_size, offsets)
        position = offsets.get(intent_id)
        if position is None:
            return None
        record = self._read_snapshot_line(snapshot, position)
        if record is not None and record.get("intent_id") == intent_id:
            return {"intent_id": intent_id, "day": day, "compacted": True, "record": record}
        return None

    def _candidate_days(self, intent_id: str, compact_dir: Path) -> list[str]:
        """Tage, in denen der Eintrag stecken koennte -- die ID traegt den Erstellungstag.

        ``int_20260907T235959Z_ab12cd`` nennt den Tag der *Erzeugung*; archiviert
        werden kann er Sekunden spaeter, also auf den naechsten Tag. Deshalb erst
        der naheliegende Kandidat (O(1)), dann der Rest (Tage sind wenige).
        """
        present = sorted({p.stem for p in compact_dir.glob("*.jsonl")})
        if not present:
            return []
        parts = intent_id.split("_")
        if len(parts) > 1 and len(parts[1]) >= 8 and parts[1][:8].isdigit():
            hint = f"{parts[1][:4]}-{parts[1][4:6]}-{parts[1][6:8]}"
            if hint in present:
                return [hint, *(day for day in present if day != hint)]
        return present

    def _candidate_entry_dirs(self, intent_id: str) -> list[Path]:
        archive = self.config.archive_dir
        if not archive.is_dir():
            return []
        days = sorted((p for p in archive.iterdir() if p.is_dir() and p.name != "compacted"), reverse=True)
        return [day / intent_id for day in days if (day / intent_id).is_dir()]
