"""Konfiguration des Hermes-Kanban -- ausschliesslich aus ``NIO_KANBAN_*``-Variablen.

Bewusst **nicht** in ``neu.config.json``/``core/config.py``: beide stehen unter
``human_only_globs`` (Constitution Guard). Das Kanban ist additiv und bringt seine
Stellschrauben selbst mit; jede hat einen Default, der ohne Docker, Redis und
Postgres lauffaehig ist.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["KanbanConfig"]

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _float(env: Mapping[str, str], key: str, default: float) -> float:
    raw = env.get(key, "").strip()
    return float(raw) if raw else default


def _int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key, "").strip()
    return int(raw) if raw else default


def _path(env: Mapping[str, str], key: str, root: Path, default: str) -> Path:
    raw = env.get(key, "").strip()
    path = Path(raw) if raw else Path(default)
    return path if path.is_absolute() else root / path


def _csv(env: Mapping[str, str], key: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in env.get(key, "").split(",") if part.strip())


@dataclass(frozen=True)
class KanbanConfig:
    repo_root: Path = _REPO_ROOT
    # Backends
    store: str = "sqlite"  # sqlite | postgres
    sqlite_path: Path = _REPO_ROOT / "runtime" / "kanban" / "kanban.db"
    pg_dsn: str = ""
    bus: str = "memory"  # memory | redis
    redis_url: str = "redis://127.0.0.1:6379/0"
    sandbox: str = "subprocess"  # subprocess | docker
    # Docker-JIT-Sandbox
    image: str = "python:3.12-slim"
    cpus: str = "1.0"
    memory: str = "512m"
    pids_limit: int = 256
    network: str = "none"
    docker_bin: str = "docker"
    # Takt und Fristen
    tick_s: float = 2.0
    heartbeat_s: float = 5.0
    heartbeat_ttl_s: float = 20.0
    reaper_grace_s: float = 30.0
    task_deadline_s: float = 900.0
    stop_grace_s: float = 10.0
    max_concurrent: int = 1
    # Circuit-Breaker
    breaker_threshold: int = 3
    breaker_cooldown_s: float = 600.0
    # Dateisystem
    workspace_dir: Path = _REPO_ROOT / "workspace" / "kanban"
    vault_dir: Path = _REPO_ROOT / "workspace" / "obsidian"
    # Geheimnisse / API
    secret_allowlist: tuple[str, ...] = field(default_factory=tuple)
    api_token: str = ""
    api_host: str = "127.0.0.1"
    api_port: int = 8740
    sandbox_api_url: str = "http://host.docker.internal:8740"
    # Telegram
    telegram_token: str = ""
    telegram_chat_id: str = ""

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, *, repo_root: Path | None = None) -> KanbanConfig:
        e = os.environ if env is None else env
        root = Path(e.get("NEU_ROOT") or repo_root or _REPO_ROOT).resolve()
        return cls(
            repo_root=root,
            store=e.get("NIO_KANBAN_STORE", "sqlite").strip() or "sqlite",
            sqlite_path=_path(e, "NIO_KANBAN_SQLITE_PATH", root, "runtime/kanban/kanban.db"),
            pg_dsn=e.get("NIO_KANBAN_PG_DSN", ""),
            bus=e.get("NIO_KANBAN_BUS", "memory").strip() or "memory",
            redis_url=e.get("NIO_KANBAN_REDIS_URL", "redis://127.0.0.1:6379/0"),
            sandbox=e.get("NIO_KANBAN_SANDBOX", "subprocess").strip() or "subprocess",
            image=e.get("NIO_KANBAN_IMAGE", "python:3.12-slim"),
            cpus=e.get("NIO_KANBAN_CPUS", "1.0"),
            memory=e.get("NIO_KANBAN_MEMORY", "512m"),
            pids_limit=_int(e, "NIO_KANBAN_PIDS", 256),
            network=e.get("NIO_KANBAN_NETWORK", "none"),
            docker_bin=e.get("NIO_KANBAN_DOCKER_BIN", "docker"),
            tick_s=_float(e, "NIO_KANBAN_TICK_S", 2.0),
            heartbeat_s=_float(e, "NIO_KANBAN_HEARTBEAT_S", 5.0),
            heartbeat_ttl_s=_float(e, "NIO_KANBAN_HEARTBEAT_TTL_S", 20.0),
            reaper_grace_s=_float(e, "NIO_KANBAN_REAPER_GRACE_S", 30.0),
            task_deadline_s=_float(e, "NIO_KANBAN_TASK_DEADLINE_S", 900.0),
            stop_grace_s=_float(e, "NIO_KANBAN_STOP_GRACE_S", 10.0),
            max_concurrent=max(1, _int(e, "NIO_KANBAN_MAX_CONCURRENT", 1)),
            breaker_threshold=max(1, _int(e, "NIO_KANBAN_BREAKER_THRESHOLD", 3)),
            breaker_cooldown_s=_float(e, "NIO_KANBAN_BREAKER_COOLDOWN_S", 600.0),
            workspace_dir=_path(e, "NIO_KANBAN_WORKSPACE", root, "workspace/kanban"),
            vault_dir=_path(e, "NIO_OBSIDIAN_VAULT", root, "workspace/obsidian"),
            secret_allowlist=_csv(e, "NIO_KANBAN_SECRET_ALLOWLIST"),
            api_token=e.get("NIO_KANBAN_API_TOKEN", ""),
            api_host=e.get("NIO_KANBAN_API_HOST", "127.0.0.1"),
            api_port=_int(e, "NIO_KANBAN_API_PORT", 8740),
            sandbox_api_url=e.get("NIO_KANBAN_SANDBOX_API_URL", "http://host.docker.internal:8740"),
            telegram_token=e.get("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=e.get("TELEGRAM_CHAT_ID", ""),
        )
