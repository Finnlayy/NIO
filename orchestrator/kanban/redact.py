"""Schwaerzt injizierte Geheimnisse aus Worker-Ausgaben.

Geschwaerzt wird nach den tatsaechlich injizierten Werten, nicht nach Mustern:
was der Dispatcher einem Worker mitgibt, darf weder im Store noch in der API,
im Vault oder im Log wieder auftauchen.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

__all__ = ["REDACTED", "redact", "redact_text"]

REDACTED = "[REDACTED]"


def _values(secrets: Iterable[str]) -> list[str]:
    # Laengste zuerst, damit ein Teilwert keinen laengeren Wert halb stehen laesst.
    return sorted({s for s in secrets if s}, key=len, reverse=True)


def redact_text(text: str, secrets: Iterable[str]) -> str:
    for value in _values(secrets):
        text = text.replace(value, REDACTED)
    return text


def redact(obj: Any, secrets: Iterable[str]) -> Any:
    """Gibt eine geschwaerzte Kopie von ``obj`` zurueck (Strings, Listen, Dicts)."""
    values = _values(secrets)
    if not values:
        return obj

    def walk(o: Any) -> Any:
        if isinstance(o, str):
            return redact_text(o, values)
        if isinstance(o, dict):
            return {walk(k) if isinstance(k, str) else k: walk(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return type(o)(walk(v) for v in o)
        return o

    return walk(obj)
