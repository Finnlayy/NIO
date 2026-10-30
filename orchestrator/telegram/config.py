"""Konfiguration für das Telegram-Modul.

Aus NIO_TELEGRAM_* Umgebungsvariablen.
Secrets (api_hash) werden in Logs/repr() geschuetzt.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from .models import normalize_peer

__all__ = ["TelegramConfig"]

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _float(env: Mapping[str, str], key: str, default: float) -> float:
    raw = env.get(key, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"Ungueltiger numerischer Wert fuer {key}") from None


def _int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"Ungueltiger numerischer Wert fuer {key}") from None


def _int_or_none(env: Mapping[str, str], key: str) -> int | None:
    raw = env.get(key, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"Ungueltiger numerischer Wert fuer {key}") from None


def _parse_allowlist(raw: str) -> tuple[int | str, ...]:
    return tuple(normalize_peer(item) for item in raw.split(",") if item.strip())


@dataclass(frozen=True)
class TelegramConfig:
    api_id: int | None
    api_hash: str = field(repr=False)
    data_dir: Path
    send_allowlist: tuple[int | str, ...]
    send_rate_per_hour: int
    gather_interval_s: float
    callback_allowlist: tuple[str, ...]
    kanban_board: str
    kanban_min_strength: int
    kanban_cooldown_s: float

    @property
    def configured(self) -> bool:
        return self.api_id is not None and bool(self.api_hash)

    @property
    def session_path(self) -> Path:
        return self.data_dir / "nio.session"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "telegram.db"

    @property
    def symbols_cache(self) -> Path:
        return self.data_dir / "kraken_symbols.json"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, *, repo_root: Path | None = None) -> TelegramConfig:
        if env is None:
            env = os.environ

        if repo_root is not None:
            root = repo_root
        elif env.get("NEU_ROOT"):
            root = Path(env["NEU_ROOT"]).resolve()
        else:
            root = _REPO_ROOT

        api_id = _int_or_none(env, "NIO_TELEGRAM_API_ID")
        api_hash = env.get("NIO_TELEGRAM_API_HASH", "").strip()

        raw_data_dir = env.get("NIO_TELEGRAM_DATA_DIR", "runtime/telegram").strip()
        data_dir = Path(raw_data_dir)
        if not data_dir.is_absolute():
            data_dir = (root / data_dir).resolve()

        raw_send_allowlist = env.get("NIO_TELEGRAM_SEND_ALLOWLIST", "").strip()
        send_allowlist = _parse_allowlist(raw_send_allowlist)

        send_rate_per_hour = _int(env, "NIO_TELEGRAM_SEND_RATE", 6)
        if send_rate_per_hour < 1:
            send_rate_per_hour = 1

        gather_interval_s = _float(env, "NIO_TELEGRAM_GATHER_S", 300.0)
        if gather_interval_s < 60.0:
            gather_interval_s = 60.0

        raw_callback = env.get("NIO_TELEGRAM_CALLBACK_ALLOWLIST", "").strip()
        callback_allowlist = tuple(item.strip() for item in raw_callback.split(",") if item.strip())

        kanban_board = env.get("NIO_TELEGRAM_KANBAN_BOARD", "").strip()
        kanban_min_strength = _int(env, "NIO_TELEGRAM_KANBAN_MIN_STRENGTH", 7)
        kanban_cooldown_s = _float(env, "NIO_TELEGRAM_KANBAN_COOLDOWN_S", 3600.0)

        return cls(
            api_id=api_id,
            api_hash=api_hash,
            data_dir=data_dir,
            send_allowlist=send_allowlist,
            send_rate_per_hour=send_rate_per_hour,
            gather_interval_s=gather_interval_s,
            callback_allowlist=callback_allowlist,
            kanban_board=kanban_board,
            kanban_min_strength=kanban_min_strength,
            kanban_cooldown_s=kanban_cooldown_s,
        )
