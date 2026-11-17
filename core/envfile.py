"""Laedt die lokale Betreiber-Datei ``~/.config/nio/nio.env`` beim Start.

Die Datei liegt nie im Repo. Sie enthaelt Geheimnisse wie
``NIO_KANBAN_API_TOKEN`` und wird sonst nur von den systemd-Units gelesen.
Damit ``neu`` aus jedem Terminal dieselben Werte sieht, uebernimmt dieser
Lader sie in ``os.environ``:

- Bereits gesetzte Variablen gewinnen; die Datei fuellt nur Luecken.
- ``NEU_ROOT``, ``NIO_REPO_ROOT`` und ``NIO_PYTHON`` werden uebersprungen,
  weil sie an einen bestimmten Checkout gebunden sind. Der laufende Checkout
  bestimmt seine Wurzel selbst.
- Die Datei muss dem Nutzer gehoeren und darf fuer niemanden sonst lesbar
  sein (Fail-Closed); sonst wird nichts geladen.
- ``NIO_ENV_FILE`` setzt einen anderen Pfad, ``NIO_ENV_FILE=off`` schaltet
  das Laden ab. Limbs bekommen von alldem nichts, weil ``_limb_env`` nur eine
  Allowlist weiterreicht.
"""

from __future__ import annotations

import os
import re
import stat
import sys
from collections.abc import MutableMapping
from pathlib import Path

DEFAULT_ENV_FILE = Path("~/.config/nio/nio.env")
CHECKOUT_KEYS = frozenset({"NEU_ROOT", "NIO_REPO_ROOT", "NIO_PYTHON"})
_LINE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def parse_env_text(text: str) -> dict[str, str]:
    """``KEY=VALUE`` je Zeile; Kommentare, Leerzeilen und Muell werden ignoriert."""
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _LINE.match(line)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def env_file_path(environ: MutableMapping[str, str]) -> Path | None:
    configured = environ.get("NIO_ENV_FILE", "").strip()
    if configured.lower() in {"off", "0", "false", "none"}:
        return None
    return Path(configured or DEFAULT_ENV_FILE).expanduser()


def load_env_file(environ: MutableMapping[str, str] | None = None) -> list[str]:
    """Uebernimmt fehlende Werte aus der Betreiber-Datei; liefert die Schluessel."""
    target = os.environ if environ is None else environ
    path = env_file_path(target)
    if path is None:
        return []
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return []
    except OSError:
        print(f"[nio-env] {path} nicht lesbar, nichts geladen.", file=sys.stderr)
        return []
    with os.fdopen(fd, "r", encoding="utf-8") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            print(f"[nio-env] {path} muss dir gehoeren und Rechte 600 haben, nichts geladen.", file=sys.stderr)
            return []
        values = parse_env_text(handle.read())
    loaded = []
    for key, value in values.items():
        if key in CHECKOUT_KEYS or key in target:
            continue
        target[key] = value
        loaded.append(key)
    return loaded
