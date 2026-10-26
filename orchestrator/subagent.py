"""Subagent-Knoten: eigener Sandbox-Rahmen um einen Limb (Phase 3).

Ein **Subagent** ist in NEU kein zweiter Orchestrator, sondern ein Aktor mit
einem eigenen, abgeschlossenen Wirkungsraum:

* **eigene Sandbox** -- ``workspace/subagents/<agent_id>/``. Die Policy erzwingt
  sie zweifach (Pre-Flight im Orchestrator, Laufzeit im Limb). Zwei Subagenten
  koennen sich gegenseitig nicht lesen.
* **eigenes Werkzeug** -- die Installation liegt *in* der Sandbox (``rea/``),
  nicht global. Ein Subagent kann eine andere Version fahren als der naechste.
* **eigenes Gedaechtnis** -- ``.subagent/state.json``: Identitaet, Installation,
  importierte Ziele, Lauf-Historie.
* **eigene Uhr** -- jeder Lauf ist ein normaler Job und erbt Timer, Agent-Slot,
  Policy, Archiv und Event-Bus des Orchestrators. Nichts wird umgangen.

Damit ist der Subagent die kleinste Einheit, die man gefahrlos wegwerfen kann:
Verzeichnis loeschen, ``create`` erneut -- fertig.

Der erste Nutzer dieses Rahmens ist REA (``limbs/rea_limb.py``); der Rahmen selbst
ist werkzeugagnostisch (``limb`` ist ein Feld, kein Sonderfall).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.config import NeuConfig
from core.protocol import ErrorCode, ProtocolError, utc_now_iso

from .runner import JobOutcome, Orchestrator

#: Unter diesem Verzeichnis liegt jeder Subagent. ``workspace/`` ist git-ignoriert.
SUBAGENT_DIRNAME = "subagents"
#: Bewusst streng: keine Pfadtrenner, kein ``..``, kein Grossbuchstaben-Chaos.
AGENT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{1,47}$")
NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
STATE_DIR = ".subagent"
STATE_FILE = "state.json"
STATE_SCHEMA = "neu.subagent/1"
#: Verzeichnisvertrag -- dieselbe Liste, die der REA-Limb anlegt.
LAYOUT_DIRS = ("rea", "targets", "out", "logs", "tmp", "home", "cache", STATE_DIR)
#: Import-Manifest je Ziel; bleibt neben dem Zielbaum liegen.
TARGET_MANIFEST = ".target.json"
#: Name der Installationsmarker-Datei des REA-Limbs. Als String gehalten, damit
#: dieses Modul nicht vom Limb abhaengt (Importrichtung: orchestrator -> core).
INSTALL_MARKER_NAME = ".rea-install.json"
#: Deckel fuer Manifest-Eintraege und Verzeichnis-Inventar (Sandboxen koennen
#: node_modules enthalten -- ein ``status`` darf daran nicht sterben).
MAX_MANIFEST_ENTRIES = 500
MAX_INVENTORY_ENTRIES = 20_000
MAX_RUN_HISTORY = 50


@dataclass
class SubagentRecord:
    """Persistenter Zustand eines Subagenten (``.subagent/state.json``)."""

    agent_id: str
    limb: str = "rea"
    sandbox: str = ""
    created_at: str = ""
    updated_at: str = ""
    install: dict[str, Any] | None = None
    targets: list[dict[str, Any]] = field(default_factory=list)
    runs: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    schema: str = STATE_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "agent_id": self.agent_id,
            "limb": self.limb,
            "sandbox": self.sandbox,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "install": self.install,
            "targets": list(self.targets),
            "runs": list(self.runs),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SubagentRecord:
        return cls(
            agent_id=str(data.get("agent_id") or ""),
            limb=str(data.get("limb") or "rea"),
            sandbox=str(data.get("sandbox") or ""),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
            install=dict(data["install"]) if isinstance(data.get("install"), Mapping) else None,
            targets=[dict(item) for item in data.get("targets") or [] if isinstance(item, Mapping)],
            runs=[dict(item) for item in data.get("runs") or [] if isinstance(item, Mapping)],
            notes=[str(item) for item in data.get("notes") or []],
            schema=str(data.get("schema") or STATE_SCHEMA),
        )

    def touch(self, note: str = "") -> None:
        self.updated_at = utc_now_iso()
        if note:
            self.notes.append(f"{self.updated_at} {note}")
            del self.notes[:-20]

    def add_run(self, entry: Mapping[str, Any]) -> None:
        self.runs.append(dict(entry))
        del self.runs[:-MAX_RUN_HISTORY]

    def set_target(self, manifest: Mapping[str, Any]) -> None:
        name = str(manifest.get("name") or "")
        self.targets = [item for item in self.targets if str(item.get("name") or "") != name]
        self.targets.append(dict(manifest))


class SubagentStore:
    """Dateisystem-Zugriff auf ``workspace/subagents/``."""

    def __init__(self, config: NeuConfig | None = None) -> None:
        self.config = config or NeuConfig.load()

    @property
    def root(self) -> Path:
        return Path(self.config.workspace_dir) / SUBAGENT_DIRNAME

    def sandbox(self, agent_id: str) -> Path:
        if not AGENT_ID_PATTERN.match(agent_id):
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID,
                f"Subagent-ID {agent_id!r} ist ungueltig (erlaubt: a-z, 0-9, '.', '_', '-', 2..48 Zeichen, "
                "Beginn mit Buchstabe/Ziffer).",
                "$.agent_id",
            )
        path = (self.root / agent_id).resolve()
        if not self._inside(path, self.root.resolve()):
            raise ProtocolError(ErrorCode.SANDBOX_ESCAPE, f"Subagent-Pfad verlaesst die Wurzel: {agent_id!r}", "$.agent_id")
        return path

    def state_path(self, agent_id: str) -> Path:
        return self.sandbox(agent_id) / STATE_DIR / STATE_FILE

    def load(self, agent_id: str) -> SubagentRecord | None:
        path = self.state_path(agent_id)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProtocolError(ErrorCode.IO, f"Zustand von '{agent_id}' ist unlesbar: {exc}", str(path)) from exc
        if not isinstance(data, Mapping):
            raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"Zustand von '{agent_id}' ist kein Objekt", str(path))
        record = SubagentRecord.from_dict(data)
        record.agent_id = agent_id
        return record

    def save(self, record: SubagentRecord) -> SubagentRecord:
        record.updated_at = utc_now_iso()
        path = self.state_path(record.agent_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return record

    def list(self) -> list[SubagentRecord]:
        if not self.root.is_dir():
            return []
        records: list[SubagentRecord] = []
        for child in sorted(self.root.iterdir()):
            if not child.is_dir() or not AGENT_ID_PATTERN.match(child.name):
                continue
            try:
                record = self.load(child.name)
            except ProtocolError:
                continue
            if record is not None:
                records.append(record)
        return records

    @staticmethod
    def _inside(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
        except ValueError:
            return False
        return True


class SubagentManager:
    """Lebenszyklus eines Subagenten: anlegen, Ziel importieren, Lauf starten."""

    def __init__(
        self,
        config: NeuConfig | None = None,
        *,
        orchestrator: Orchestrator | None = None,
        store: SubagentStore | None = None,
    ) -> None:
        self.config = config or NeuConfig.load()
        self.store = store or SubagentStore(self.config)
        self._orchestrator = orchestrator

    # ------------------------------------------------------------------ intern
    @property
    def orchestrator(self) -> Orchestrator:
        if self._orchestrator is None:
            self._orchestrator = Orchestrator(self.config, quiet=True)
        return self._orchestrator

    @property
    def root(self) -> Path:
        return self.store.root

    def sandbox(self, agent_id: str) -> Path:
        return self.store.sandbox(agent_id)

    def rel(self, path: Path) -> str:
        return self.config.relative(path)

    def _require(self, agent_id: str) -> SubagentRecord:
        record = self.store.load(agent_id)
        if record is None:
            raise ProtocolError(
                ErrorCode.PATH_NOT_FOUND,
                f"Subagent '{agent_id}' existiert nicht unter {self.rel(self.root)}.",
                "$.agent_id",
            )
        return record

    # ------------------------------------------------------------------ anlegen
    def ensure(self, agent_id: str, limb: str = "rea", *, create: bool = True) -> SubagentRecord:
        """Idempotent: legt Sandbox + Zustand an, wenn sie fehlen."""
        sandbox = self.store.sandbox(agent_id)
        record = self.store.load(agent_id)
        if record is not None:
            if sandbox.is_dir():
                return record
            raise ProtocolError(
                ErrorCode.PATH_NOT_FOUND,
                f"Zustand von '{agent_id}' existiert, Sandbox fehlt: {self.rel(sandbox)}",
                "$.agent_id",
            )
        if not create:
            raise ProtocolError(ErrorCode.PATH_NOT_FOUND, f"Subagent '{agent_id}' existiert nicht.", "$.agent_id")
        sandbox.mkdir(parents=True, exist_ok=True)
        for name in LAYOUT_DIRS:
            (sandbox / name).mkdir(parents=True, exist_ok=True)
        now = utc_now_iso()
        record = SubagentRecord(
            agent_id=agent_id,
            limb=limb,
            sandbox=self.rel(sandbox),
            created_at=now,
            updated_at=now,
            notes=[f"{now} created limb={limb}"],
        )
        return self.store.save(record)

    def list(self) -> list[SubagentRecord]:
        return self.store.list()

    # ------------------------------------------------------------------ Status
    def status(self, agent_id: str) -> dict[str, Any]:
        record = self._require(agent_id)
        sandbox = self.sandbox(agent_id)
        inventory = {
            name: _inventory(sandbox / name, self.config) for name in LAYOUT_DIRS if (sandbox / name).is_dir()
        }
        marker = _read_json(sandbox / "rea" / INSTALL_MARKER_NAME)
        return {
            "agent_id": record.agent_id,
            "limb": record.limb,
            "sandbox": record.sandbox,
            "exists": sandbox.is_dir(),
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "install": marker or record.install,
            "rea": {
                "installed": bool(marker),
                "version": (marker or {}).get("version"),
                "source": (marker or {}).get("source"),
                "pwntools": bool((marker or {}).get("pwntools", {}).get("ok")) if isinstance(marker, Mapping) else False,
            },
            "targets": record.targets,
            "dirs": inventory,
            "runs": record.runs[-5:],
            "runs_total": len(record.runs),
            "notes": record.notes[-5:],
        }

    # ------------------------------------------------------------------ Import
    def import_target(
        self,
        agent_id: str,
        source: Path | str,
        *,
        name: str = "",
        replace: bool = False,
    ) -> dict[str, Any]:
        """Kopiert ein Ziel (Datei oder Baum) in die Sandbox und hashed es.

        Der Import ist die einzige Stelle, an der Daten *in* den Subagenten
        hineingehen. Deshalb: Zielname streng pruefen, nichts ueberschreiben ohne
        ``replace``, und ein Manifest mit per-Datei-Hash daneben legen.
        """
        record = self.ensure(agent_id)
        src = Path(source).expanduser()
        if not src.is_absolute():
            src = (self.config.repo_root / src).resolve()
        if not src.exists():
            raise ProtocolError(ErrorCode.PATH_NOT_FOUND, f"Quelle existiert nicht: {src}", "$.source")

        target_name = name.strip() or src.name
        if not NAME_PATTERN.match(target_name):
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID,
                f"Zielname {target_name!r} ist ungueltig (a-z/A-Z/0-9/'.'/'_'/'-', max 64).",
                "$.name",
            )
        dest_root = (self.sandbox(agent_id) / "targets").resolve()
        dest = (dest_root / target_name).resolve()
        if not SubagentStore._inside(dest, dest_root):
            raise ProtocolError(ErrorCode.SANDBOX_ESCAPE, f"Ziel {target_name!r} verlaesst die Sandbox", "$.name")
        if dest.exists():
            if not replace:
                raise ProtocolError(
                    ErrorCode.ALREADY_EXISTS,
                    f"Ziel '{target_name}' liegt bereits in {self.rel(dest)}.",
                    "$.name",
                )
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()

        # Immer ein Verzeichnis als Zielcontainer: darin liegt entweder der
        # kopierte Baum oder genau eine Datei -- plus das Manifest. Damit ist
        # ``targets/<name>`` stabil, egal was importiert wurde.
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.mkdir(parents=True, exist_ok=False)
        if src.is_dir():
            shutil.copytree(src, dest, symlinks=False, dirs_exist_ok=True)
            entry = dest
        else:
            shutil.copy2(src, dest / src.name)
            entry = dest / src.name

        entries, total_bytes, truncated = _hash_tree(dest)
        # Das Manifest liegt *neben* dem Ziel, nicht darin: der Baum unter
        # targets/<name> muss byte-identisch mit der Quelle bleiben, sonst
        # analysiert REA ein Artefakt, das es so nie gab (Digest-Drift).
        manifest_dir = dest_root / ".manifests"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = manifest_dir / f"{target_name}.json"
        manifest = {
            "name": target_name,
            "kind": "directory" if src.is_dir() else "file",
            "source": str(src),
            "imported_at": utc_now_iso(),
            "path": self.rel(dest),
            "entry": self.rel(entry),
            "manifest": self.rel(manifest_path),
            "files": len(entries),
            "bytes": total_bytes,
            "sha256_root": _root_digest(entries),
            "entries": entries[:MAX_MANIFEST_ENTRIES],
            "entries_truncated": truncated,
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        record.set_target(manifest)
        record.touch(f"imported target={target_name} files={manifest['files']}")
        self.store.save(record)
        return manifest

    # ------------------------------------------------------------------ Laufen
    def run(
        self,
        agent_id: str,
        *,
        goal: str,
        operation: str,
        params: Mapping[str, Any] | None = None,
        limb: str = "",
        max_iterations: int | None = None,
        deadline_s: float | None = None,
        soft_deadline_s: float | None = None,
        grace_s: float | None = None,
        safety_net_s: float | None = None,
        unlimited: bool = False,
        allow_network: bool = False,
        allow_shell: bool = False,
        dry_run: bool = False,
        parent_job_id: str = "",
        auto_iterate: bool = True,
        on_failure: str = "autodidactic",
        title: str = "",
        objective: str = "",
        acceptance: Sequence[str] = (),
    ) -> JobOutcome:
        """Startet einen Lauf als normalen NEU-Job -- innerhalb der Subagent-Sandbox."""
        record = self.ensure(agent_id)
        sandbox = self.sandbox(agent_id)
        target_limb = limb or record.limb
        constraints = {
            "sandbox_root": self.rel(sandbox),
            "allow_network": bool(allow_network),
            "allow_shell": bool(allow_shell),
            "dry_run": bool(dry_run),
        }
        outcome = self.orchestrator.run_job(
            goal=goal,
            operation=operation,
            params=dict(params or {}),
            limb=target_limb,
            max_iterations=max_iterations,
            deadline_s=deadline_s,
            soft_deadline_s=soft_deadline_s,
            grace_s=grace_s,
            safety_net_s=safety_net_s,
            unlimited=unlimited,
            on_failure=on_failure,
            constraints=constraints,
            parent_job_id=parent_job_id,
            auto_iterate=auto_iterate,
            title=title,
            objective=objective,
            acceptance=tuple(acceptance),
        )
        self._record_run(record, outcome, operation=operation, limb=target_limb, goal=goal)
        return outcome

    def install(self, agent_id: str, *, source: str = "git", ref: str = "", with_pwntools: bool = False,
                force: bool = False, build: bool = True, repository: str = "", package_version: str = "",
                deadline_s: float | None = None, soft_deadline_s: float | None = None,
                unlimited: bool = True) -> JobOutcome:
        """Bequemer Weg zu ``rea.install``: Netz erlaubt, standardmaessig ohne Zeitlimit.

        Mit ``deadline_s`` wird die weiche Marke mitgesetzt -- sonst begrenzt der
        Profil-Default (dev: 45 s) den Kindprozess, obwohl der Auftrag 900 s haette.
        """
        params: dict[str, Any] = {
            "source": source,
            "build": bool(build),
            "with_pwntools": bool(with_pwntools),
            "force": bool(force),
        }
        if ref:
            params["ref"] = ref
        if repository:
            params["repository"] = repository
        if package_version:
            params["package_version"] = package_version
        return self.run(
            agent_id,
            goal=f"REA in Subagent '{agent_id}' installieren ({source})",
            operation="rea.install",
            params=params,
            allow_network=True,
            deadline_s=deadline_s,
            soft_deadline_s=soft_deadline_s if soft_deadline_s is not None else (
                max(1.0, deadline_s - 5.0) if deadline_s else None
            ),
            unlimited=unlimited and deadline_s is None,
            title="REA-Installation",
            objective="REA innerhalb der Subagent-Sandbox installieren und die Version verifizieren.",
            acceptance=("rea.ping meldet installed=true", "versionsgleicher Einstiegspunkt existiert"),
        )

    def _record_run(self, record: SubagentRecord, outcome: JobOutcome, *, operation: str, limb: str, goal: str) -> None:
        last = outcome.attempts[-1].summary() if outcome.attempts else {}
        output = outcome.attempts[-1].result.output if outcome.attempts else {}
        entry = {
            "job_id": outcome.job.job_id,
            "operation": operation,
            "limb": limb,
            "goal": goal,
            "status": outcome.status,
            "failure_kind": outcome.failure_kind,
            "result_status": last.get("status"),
            "verdict": last.get("verdict"),
            "duration_ms": last.get("duration_ms"),
            "timer_mode": outcome.job.timer_mode,
            "at": utc_now_iso(),
            "evidence_id": output.get("evidence_id") if isinstance(output, Mapping) else None,
            "raw": (output.get("raw") or {}).get("path") if isinstance(output, Mapping) else None,
        }
        record.add_run(entry)
        if operation == "rea.install" and isinstance(output, Mapping) and output.get("installed"):
            record.install = {
                "source": output.get("source"),
                "version": output.get("version"),
                "entrypoint": output.get("entrypoint"),
                "pwntools": output.get("pwntools"),
                "installed_at": entry["at"],
                "job_id": outcome.job.job_id,
            }
        record.touch(f"run {operation} -> {outcome.status} ({outcome.job.job_id})")
        self.store.save(record)


# ---------------------------------------------------------------------- #
# Inventar-Helfer
# ---------------------------------------------------------------------- #
def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return dict(data) if isinstance(data, Mapping) else None


def _inventory(directory: Path, config: NeuConfig) -> dict[str, Any]:
    """Grobes Inventar (Dateien, Bytes) -- gedeckelt, damit node_modules nicht blockiert."""
    files = 0
    total = 0
    truncated = False
    if directory.is_dir():
        for path in directory.rglob("*"):
            if not path.is_file():
                continue
            try:
                total += path.stat().st_size
            except OSError:
                continue
            files += 1
            if files >= MAX_INVENTORY_ENTRIES:
                truncated = True
                break
    return {"path": config.relative(directory), "files": files, "bytes": total, "truncated": truncated}


def _hash_tree(root: Path) -> tuple[list[dict[str, Any]], int, bool]:
    """Per-Datei-Hash des importierten Ziels (deterministisch sortiert)."""
    if root.is_file():
        data = root.read_bytes()
        return (
            [{"path": root.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}],
            len(data),
            False,
        )
    entries: list[dict[str, Any]] = []
    total = 0
    truncated = False
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == TARGET_MANIFEST:
            continue
        try:
            digest = hashlib.sha256()
            size = 0
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1 << 20), b""):
                    digest.update(chunk)
                    size += len(chunk)
        except OSError:
            continue
        total += size
        if len(entries) < MAX_MANIFEST_ENTRIES:
            entries.append({"path": str(path.relative_to(root)).replace("\\", "/"), "bytes": size, "sha256": digest.hexdigest()})
        else:
            truncated = True
    return entries, total, truncated


def _root_digest(entries: Sequence[Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for entry in entries:
        digest.update(f"{entry.get('path')}:{entry.get('sha256')}\n".encode())
    return digest.hexdigest()
