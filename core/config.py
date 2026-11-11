"""NEU-Konfiguration (Protokoll 1.2).

Ein einziger, deterministischer Ort fuer Pfade, Sicherheits-Policy, Timer und
Skalierungsgrenzen. Core, Orchestrator und Limbs lesen alle dieselbe
Konfiguration, damit es keine divergierenden Annahmen gibt.

Ladereihenfolge (spaeter gewinnt):
    1. eingebaute Defaults
    2. ``neu.config.json`` im Repo-Root
    3. dokumentierte ``NEU_*``-Umgebungsvariablen
    4. explizite Parameter ``NeuConfig.load(repo_root=..., **overrides)``

**Dev-Modus** (``mode="dev"``) deckelt alles auf 1 Iteration / 1 Agent /
1 Limb / 1 parallelen Job. Hoeher skaliert wird erst, wenn das System sich im
Dev-Modus bewaehrt hat -- und nur mit menschlicher Freigabe, weil
``neu.config.json`` unter dem Constitution Guard steht.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

CONFIG_FILENAME = "neu.config.json"

#: Pfade, die ein Limb mit ``elevation.level == "repo_write"`` veraendern darf.
#: fnmatch-Semantik: ``*`` matcht auch Pfadtrenner.
DEFAULT_ALLOWED_REPO_GLOBS: tuple[str, ...] = (
    "core/*",
    "orchestrator/*",
    "limbs/*",
    "prompts/*",
    "protocol/*",
    "tests/*",
    "docs/*",
    "workspace/*",
    "README.md",
    "neu.config.json",  # schreibbar, aber human_only -> Constitution Guard
)

#: Harte Verbote. Diese Liste gewinnt immer gegen ``allowed_repo_globs``.
DEFAULT_DENIED_GLOBS: tuple[str, ...] = (
    ".git/*",
    ".github/*",
    "runtime/*",
    "node_modules/*",
    "dist/*",
    "frontend/.next/*",
    "*.bak",
    "*.log",
)

#: "Constitution Guard": Diese Dateien duerfen nur mit menschlicher Freigabe
#: (``elevation.approved_by == "human"``) veraendert werden. Ein Limb darf sich
#: seine eigenen Rechte niemals selbst erweitern koennen.
DEFAULT_HUMAN_ONLY_GLOBS: tuple[str, ...] = (
    "neu.config.json",
    "core/policy.py",
    "core/config.py",
    ".git/*",
    ".github/*",
)

DEFAULT_MAX_OUTPUT_BYTES = 1_048_576
HARD_MAX_OUTPUT_BYTES = 67_108_864

#: Mindest-Schwellenwert für die strukturierte `defineEval`-Pipeline (ersetzt starre 85er-Schwelle durch konfigurierbare Pipeline-Parameter).
EVAL_MIN_THRESHOLD = 85.0
EVAL_DEFAULT_SAFETY_TOLERANCE = 0.1

#: Timer-Defaults (Protokoll 1.2)
DEFAULT_RUNTIME_DIR = "runtime"
DEFAULT_WORKSPACE_DIR = "workspace"
DEFAULT_PROTOCOL_DIR = "protocol"

DEFAULT_DEADLINE_S = 60.0
DEFAULT_SOFT_DEADLINE_S = 45.0
DEFAULT_GRACE_S = 5.0
HARD_DEADLINE_S = 900.0

#: Reine Prozess-Hygiene fuer den Unlimited-Modus: kein Aufgabenlimit, sondern
#: Zombie-Schutz. 0 = wirklich unbegrenzt. Eingriffe melden E_SAFETY_NET.
DEFAULT_SAFETY_NET_S = 3600.0

#: Tick-Intervall des Schedulers (Auswertung der zeitgesteuerten Trigger)
DEFAULT_TICK_S = 0.5

#: Iterations-Budget: hartes Maximum ueber alle Profile (vom User festgelegt: 2).
ABSOLUTE_MAX_ITERATIONS = 2

#: Skalierungsprofile. Dev = 1/1/1/1, scale = das erlaubte Maximum.
SCALE_PROFILES: dict[str, dict[str, Any]] = {
    "dev": {
        "max_iterations": 1,
        "max_agents": 1,
        "max_limbs": 1,
        "max_concurrent_jobs": 1,
        "max_scheduled_jobs": 1,
    },
    "scale": {
        "max_iterations": ABSOLUTE_MAX_ITERATIONS,
        "max_agents": 4,
        "max_limbs": 4,
        "max_concurrent_jobs": 2,
        "max_scheduled_jobs": 4,
    },
}

VALID_MODES = ("dev", "scale")


@dataclass(frozen=True)
class Limits:
    """Ressourcen-Deckel. Iterationen zaehlen pro **Job**, nicht pro Agentenaufruf."""

    max_iterations: int = 1
    max_agents: int = 1
    max_limbs: int = 1
    max_concurrent_jobs: int = 1
    max_scheduled_jobs: int = 1

    def to_dict(self) -> dict[str, int]:
        return {
            "max_iterations": self.max_iterations,
            "max_agents": self.max_agents,
            "max_limbs": self.max_limbs,
            "max_concurrent_jobs": self.max_concurrent_jobs,
            "max_scheduled_jobs": self.max_scheduled_jobs,
        }

    @classmethod
    def from_dict(cls, data: Any, mode: str = "dev") -> Limits:
        profile = dict(SCALE_PROFILES.get(mode, SCALE_PROFILES["dev"]))
        if isinstance(data, dict):
            profile.update({k: v for k, v in data.items() if k in profile and v is not None})
        return cls(
            max_iterations=max(1, min(int(profile["max_iterations"]), ABSOLUTE_MAX_ITERATIONS)),
            max_agents=max(1, int(profile["max_agents"])),
            max_limbs=max(1, int(profile["max_limbs"])),
            max_concurrent_jobs=max(1, int(profile["max_concurrent_jobs"])),
            max_scheduled_jobs=max(1, int(profile.get("max_scheduled_jobs", 1))),
        )


@dataclass(frozen=True)
class TimerDefaults:
    """Vorgaben fuer den Timer, der vor jedem Auftrag scharf geschaltet wird.

    ``deadline_s = None`` bedeutet: Es wird **kein** Limit vorgegeben, die Zeit
    wird getrackt (``mode="unlimited"``, Protokoll 1.2).
    """

    deadline_s: float | None = DEFAULT_DEADLINE_S
    soft_deadline_s: float | None = DEFAULT_SOFT_DEADLINE_S
    grace_s: float = DEFAULT_GRACE_S
    safety_net_s: float | None = DEFAULT_SAFETY_NET_S
    tick_s: float = DEFAULT_TICK_S

    @property
    def unlimited(self) -> bool:
        return self.deadline_s is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "deadline_s": self.deadline_s,
            "soft_deadline_s": self.soft_deadline_s,
            "grace_s": self.grace_s,
            "safety_net_s": self.safety_net_s,
            "tick_s": self.tick_s,
        }

    @classmethod
    def from_dict(cls, data: Any) -> TimerDefaults:
        body = dict(data) if isinstance(data, dict) else {}
        raw_deadline = body.get("deadline_s", DEFAULT_DEADLINE_S)
        raw_soft = body.get("soft_deadline_s", DEFAULT_SOFT_DEADLINE_S)
        grace = float(body.get("grace_s", DEFAULT_GRACE_S))
        raw_net = body.get("safety_net_s", DEFAULT_SAFETY_NET_S)
        tick = float(body.get("tick_s", DEFAULT_TICK_S))

        if raw_deadline is None:
            # Unlimited: keine Fristen, nur Tracking + optionales Safety-Net
            net = None if raw_net is None else float(raw_net)
            if net is not None and net < 1.0:
                raise ValueError("timer.safety_net_s muss >= 1.0 sein (0/null = wirklich unbegrenzt)")
            return cls(deadline_s=None, soft_deadline_s=None, grace_s=max(0.0, grace), safety_net_s=net, tick_s=max(0.05, tick))

        deadline = float(raw_deadline)
        if not 0.1 <= deadline <= HARD_DEADLINE_S:
            raise ValueError(f"timer.deadline_s muss in [0.1, {HARD_DEADLINE_S}] liegen (gefunden: {deadline})")
        soft = None if raw_soft is None else min(max(0.1, float(raw_soft)), deadline)
        net = None if raw_net is None else float(raw_net)
        return cls(deadline_s=deadline, soft_deadline_s=soft, grace_s=max(0.0, grace), safety_net_s=net, tick_s=max(0.05, tick))


@dataclass(frozen=True)
class NeuConfig:
    """Unveraenderliche Laufzeitkonfiguration des NEU-Stacks."""

    repo_root: Path
    mode: str = "dev"
    # Invariante: Nach ``__post_init__`` sind das immer echte ``Path``-Objekte
    # (relativ = unterhalb repo_root, absolut = unveraendert). Eingaben duerfen
    # trotzdem Strings oder None sein -- ``load()`` und ``__post_init__``
    # normalisieren, damit kein Aufrufer ``Path | None`` weiterschleppen muss.
    runtime_dir: Path = field(default_factory=lambda: Path(DEFAULT_RUNTIME_DIR))
    workspace_dir: Path = field(default_factory=lambda: Path(DEFAULT_WORKSPACE_DIR))
    protocol_dir: Path = field(default_factory=lambda: Path(DEFAULT_PROTOCOL_DIR))
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES
    allow_shell_ops: bool = False
    allow_test_ops: bool = False
    allow_repo_write: bool = True
    allowed_repo_globs: tuple[str, ...] = DEFAULT_ALLOWED_REPO_GLOBS
    denied_globs: tuple[str, ...] = DEFAULT_DENIED_GLOBS
    human_only_globs: tuple[str, ...] = DEFAULT_HUMAN_ONLY_GLOBS
    limits: Limits = field(default_factory=lambda: Limits.from_dict(None, "dev"))
    timer: TimerDefaults = field(default_factory=TimerDefaults)
    eval_min_threshold: float = EVAL_MIN_THRESHOLD
    eval_safety_tolerance: float = EVAL_DEFAULT_SAFETY_TOLERANCE
    source_file: Path | None = field(default=None, repr=False)
    apollo_host: str = "127.0.0.1"
    apollo_port: int = 4001
    kanban_host: str = "127.0.0.1"
    kanban_port: int = 8740
    speech_url: str = "http://127.0.0.1:8011/v1/audio/transcriptions"
    speech_required: bool = False
    kanban_enabled: bool = False
    speech_timeout_s: float = 30.0
    speech_max_bytes: int = 20_000_000
    registry_file: Path = field(default_factory=lambda: Path("limbs/registry.json"))
    provenance: dict[str, str] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        root = Path(self.repo_root).resolve()
        object.__setattr__(self, "repo_root", root)
        for key, default in (
            ("runtime_dir", DEFAULT_RUNTIME_DIR),
            ("workspace_dir", DEFAULT_WORKSPACE_DIR),
            ("protocol_dir", DEFAULT_PROTOCOL_DIR),
        ):
            raw = getattr(self, key)
            if raw is not None and not isinstance(raw, (str, Path)):
                raise ValueError(f"{key} must be a path")
            text = str(raw).strip() if raw is not None else ""
            if ".." in Path(text).parts:
                raise ValueError(f"{key} must not contain '..'")
            # ``root / "/abs"`` ergibt "/abs": Ein isoliertes runtime/ ausserhalb
            # des Repos (CLI ``--runtime-dir``) bleibt damit moeglich.
            object.__setattr__(self, key, root / Path(text or default))
        for key in ("runtime_dir", "workspace_dir"):
            path = Path(getattr(self, key)).resolve()
            if (path == root and (root / ".git").exists()) or path == Path(path.anchor) or path == root / ".git" or root / ".git" in path.parents:
                raise ValueError(f"{key} must not be a checkout root, filesystem root, or .git")
        for key in ("apollo_host", "kanban_host"):
            if getattr(self, key) != "127.0.0.1":
                raise ValueError(f"{key} must be 127.0.0.1 for local-only operation")
        for key in ("apollo_port", "kanban_port"):
            value = getattr(self, key)
            if type(value) is not int or not 1 <= value <= 65535:
                raise ValueError(f"{key} must be an integer between 1 and 65535")
        if self.apollo_port == self.kanban_port:
            raise ValueError("apollo_port and kanban_port must differ")
        for key in ("speech_required", "kanban_enabled", "allow_shell_ops", "allow_test_ops", "allow_repo_write"):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f"{key} must be a boolean")
        if not isinstance(self.speech_url, str):
            raise ValueError("speech_url must be a local HTTP URL")
        try:
            url = urlsplit(self.speech_url)
            valid_url = (url.scheme == "http" and url.hostname == "127.0.0.1" and
                         url.port is not None and 1 <= url.port <= 65535 and url.username is None and url.password is None and
                         not url.query and not url.fragment)
        except ValueError:
            valid_url = False
        if not valid_url:
            raise ValueError("speech_url must be an HTTP URL on 127.0.0.1 with an explicit port and no credentials or query")
        if type(self.speech_timeout_s) not in (int, float) or not 0 < self.speech_timeout_s <= 300:
            raise ValueError("speech_timeout_s must be in (0, 300]")
        if type(self.speech_max_bytes) is not int or not 1 <= self.speech_max_bytes <= HARD_MAX_OUTPUT_BYTES:
            raise ValueError(f"speech_max_bytes must be in [1, {HARD_MAX_OUTPUT_BYTES}]")
        if type(self.max_output_bytes) is not int or not 1 <= self.max_output_bytes <= HARD_MAX_OUTPUT_BYTES:
            raise ValueError(f"max_output_bytes must be in [1, {HARD_MAX_OUTPUT_BYTES}]")
        if not isinstance(self.registry_file, (str, Path)) or '..' in Path(self.registry_file).parts:
            raise ValueError("registry_file must be a safe repository-relative path")
        registry = (root / self.registry_file).resolve()
        if not registry.is_relative_to(root) or registry.is_relative_to(root / '.git'):
            raise ValueError("registry_file must be inside the repository and outside .git")
        object.__setattr__(self, 'registry_file', registry)
        if self.mode not in VALID_MODES:
            raise ValueError("mode must be dev or scale")
        object.__setattr__(self, "limits", Limits.from_dict(self.limits.to_dict() if isinstance(self.limits, Limits) else self.limits, self.mode))

    # ---------------------------------------------------------------- Pfade
    @property
    def inbox_dir(self) -> Path:
        return Path(self.runtime_dir) / "inbox"

    @property
    def outbox_dir(self) -> Path:
        return Path(self.runtime_dir) / "outbox"

    @property
    def archive_dir(self) -> Path:
        return Path(self.runtime_dir) / "archive"

    @property
    def backup_dir(self) -> Path:
        return Path(self.runtime_dir) / "backups"

    @property
    def jobs_dir(self) -> Path:
        return Path(self.runtime_dir) / "jobs"

    @property
    def locks_dir(self) -> Path:
        return Path(self.runtime_dir) / "locks"

    @property
    def refinement_vault_dir(self) -> Path:
        """Refinement-Vault: geparkte Limbs mit FSM (``orchestrator/refinement.py``).

        Eigenes Verzeichnis unter ``runtime/``, damit geparkte Artefakte nie mit
        Job-/Schedule-Zustand verwechselt werden und der Vault per
        ``--runtime-dir`` vollstaendig isoliert (Tests, CI) betrieben werden kann.
        """
        return Path(self.runtime_dir) / "refinement-vault"

    @property
    def schedules_dir(self) -> Path:
        """Zustand der zeitgesteuerten Ausloeser (Protokoll 1.2).

        Eigenes Verzeichnis, damit ``runtime/jobs/job_*.json`` eindeutig Jobs
        bleiben und Trigger-Zustaende die Job-Liste nicht verwirren.
        """
        return Path(self.runtime_dir) / "schedules"

    @property
    def system_log_path(self) -> Path:
        """Ziel der Phase-3-Logging-Erweiterung (in Phase 1 noch unbeschrieben)."""
        return Path(self.runtime_dir) / "system.log"

    @property
    def registry_path(self) -> Path:
        return self.registry_file

    @property
    def is_dev(self) -> bool:
        return self.mode == "dev"

    def ensure_dirs(self) -> tuple[Path, ...]:
        """Legt alle Laufzeitverzeichnisse an (idempotent)."""
        created: list[Path] = []
        for directory in (
            Path(self.runtime_dir),
            self.inbox_dir,
            self.outbox_dir,
            self.archive_dir,
            self.backup_dir,
            self.jobs_dir,
            self.locks_dir,
            self.schedules_dir,
            Path(self.workspace_dir),
        ):
            directory.mkdir(parents=True, exist_ok=True)
            created.append(directory)
        return tuple(created)

    def relative(self, path: Path | str) -> str:
        """Pfad relativ zum Repo-Root (lesbar in Logs/Archiv)."""
        try:
            return str(Path(path).resolve().relative_to(self.repo_root)).replace(os.sep, "/")
        except ValueError:
            return str(path)

    def relative_resolved(self, absolute: Path | str) -> str:
        """Wie ``relative``, aber fuer Pfade, die das ``resolve()`` schon hinter sich haben.

        Der doppelte Realpath-Durchlauf ist der Grund: ``relative(sandbox_root(intent))``
        lief die Kette zwei Mal -- pro Pruefung, und die Sandbox-Wurzel steht in
        jeder Policy-Antwort. Wer einen Aufloesungs-Pfad in der Hand haelt (Policy,
        Transport), geht hier lang. Ausserhalb des Repos gilt derselbe Ruckfall wie
        bei ``relative``: die Stringform des Ubergebenen, kein Raise.
        """
        try:
            return str(Path(absolute).relative_to(self.repo_root)).replace(os.sep, "/")
        except ValueError:
            return str(absolute)

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_root": str(self.repo_root),
            "mode": self.mode,
            "limits": self.limits.to_dict(),
            "timer": self.timer.to_dict(),
            "allow_shell_ops": self.allow_shell_ops,
            "allow_test_ops": self.allow_test_ops,
            "allow_repo_write": self.allow_repo_write,
            "allowed_repo_globs": list(self.allowed_repo_globs),
            "denied_globs": list(self.denied_globs),
            "human_only_globs": list(self.human_only_globs),
            "max_output_bytes": self.max_output_bytes,
            "eval_min_threshold": self.eval_min_threshold,
            "eval_safety_tolerance": self.eval_safety_tolerance,
            "source_file": str(self.source_file) if self.source_file else None,
        }

    def diagnostics(self) -> dict[str, Any]:
        # Deliberate allowlist: no arbitrary environment or credential values.
        keys = ("mode", "apollo_host", "apollo_port", "kanban_host", "kanban_port",
                "speech_required", "kanban_enabled", "speech_timeout_s", "speech_max_bytes",
                "max_output_bytes")
        return {key: {"value": getattr(self, key), "source": self.provenance.get(key, "default")} for key in keys}

    # --------------------------------------------------------------- Laden
    @classmethod
    def load(cls, repo_root: Path | str | None = None, **overrides: Any) -> NeuConfig:
        root = Path(
            repo_root
            or os.environ.get("NEU_ROOT")
            or Path(__file__).resolve().parent.parent
        ).resolve()

        values: dict[str, Any] = {}
        provenance: dict[str, str] = {}
        config_file = root / CONFIG_FILENAME
        if config_file.is_file():
            try:
                raw = json.loads(config_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:  # Konfigurationsfehler darf nie still scheitern
                raise ValueError(f"{CONFIG_FILENAME} ist kein gueltiges JSON: {exc}") from exc
            if not isinstance(raw, dict):
                raise ValueError(f"{CONFIG_FILENAME} muss ein JSON-Objekt sein.")
            for key, value in raw.items():
                if key in {"repo_root", "$comment"}:
                    continue
                values[key] = value
                provenance[key] = "file"
            values["source_file"] = config_file

        from collections.abc import Callable
        env_fields: dict[str, tuple[str, Callable[[str], Any]]] = {
            "NEU_RUNTIME_DIR": ("runtime_dir", str), "NEU_WORKSPACE_DIR": ("workspace_dir", str),
            "NEU_PROTOCOL_DIR": ("protocol_dir", str), "NEU_REGISTRY_FILE": ("registry_file", str),
            "NEU_MODE": ("mode", str), "NEU_APOLLO_HOST": ("apollo_host", str),
            "NEU_APOLLO_PORT": ("apollo_port", int), "NEU_KANBAN_HOST": ("kanban_host", str),
            "NEU_KANBAN_PORT": ("kanban_port", int), "NEU_SPEECH_URL": ("speech_url", str),
            "NEU_SPEECH_REQUIRED": ("speech_required", _env_bool),
            "NEU_KANBAN_ENABLED": ("kanban_enabled", _env_bool),
            "NEU_SPEECH_TIMEOUT_S": ("speech_timeout_s", float),
            "NEU_SPEECH_MAX_BYTES": ("speech_max_bytes", int),
            "NEU_MAX_OUTPUT_BYTES": ("max_output_bytes", int),
        }
        for env_name, (key, convert) in env_fields.items():
            if env_name in os.environ:
                try:
                    values[key] = convert(os.environ[env_name])
                except ValueError as exc:
                    raise ValueError(f"{env_name} has an invalid value") from exc
                provenance[key] = "environment"
        values.update({k: v for k, v in overrides.items() if v is not None})
        provenance.update({k: "cli" for k, v in overrides.items() if v is not None})
        provenance["repo_root"] = "cli" if repo_root is not None else ("environment" if "NEU_ROOT" in os.environ else "default")
        values["provenance"] = provenance

        # Wird das Profil explizit gewaehlt (CLI/Env/Test), ziehen dessen Limits
        # mit -- sonst wuerde die Konfigurationsdatei das Profil still aushebeln.
        if ("mode" in overrides or "NEU_MODE" in os.environ) and values.get("mode") and "limits" not in overrides:
            if values["mode"] not in SCALE_PROFILES:
                raise ValueError("mode must be dev or scale")
            values["limits"] = dict(SCALE_PROFILES[values["mode"]])
            provenance["limits"] = provenance["mode"]

        for key in ("allowed_repo_globs", "denied_globs", "human_only_globs"):
            if key in values:
                values[key] = _as_str_tuple(values[key], key)

        # Pfadfelder: String -> Path, leer/null -> Default der Datenklasse.
        for key in ("runtime_dir", "workspace_dir", "protocol_dir", "source_file"):
            if key not in values:
                continue
            value = values[key]
            if value is None or (isinstance(value, str) and not value.strip()):
                values.pop(key)
            elif not isinstance(value, (str, Path)):
                raise ValueError(f"{key} must be a path")
            elif not isinstance(value, Path):
                values[key] = Path(value)

        mode = str(values.get("mode", "dev"))
        if "limits" in values and not isinstance(values["limits"], Limits):
            values["limits"] = Limits.from_dict(values["limits"], mode)
        elif "limits" not in values:
            values["limits"] = Limits.from_dict(None, mode)
        if "timer" in values and not isinstance(values["timer"], TimerDefaults):
            values["timer"] = TimerDefaults.from_dict(values["timer"])

        for key in cls.__dataclass_fields__:
            if key not in ("provenance", "source_file"):
                provenance.setdefault(key, "default")
        return cls(repo_root=root, **values)


def _env_bool(value: str) -> bool:
    if value.lower() not in ("true", "false"):
        raise ValueError("expected true or false")
    return value.lower() == "true"


def _as_str_tuple(value: Iterable[Any], key: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Iterable):
        raise ValueError(f"Konfigurationsschluessel '{key}' muss eine Liste von Strings sein.")
    items = tuple(str(v) for v in value)
    if any(not i for i in items):
        raise ValueError(f"Konfigurationsschluessel '{key}' enthaelt leere Eintraege.")
    return items
