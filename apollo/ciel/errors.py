"""Fehlertypen der Ciel-Schicht."""

from __future__ import annotations


class CielError(Exception):
    """Basisklasse aller Ciel-Fehler."""


class CielConfigError(CielError):
    """Fehlkonfiguration (Modellpfad, Tokenizer, Dimension, ...)."""


class ToolNotFound(CielError):
    """Tool-Name ist nicht in der Cold-Storage-Registry."""

    def __init__(self, name: str) -> None:
        self.tool_name = name
        super().__init__(f"Tool nicht in Cold-Storage-Registry: {name!r}")


class ToolNotExecutable(CielError):
    """Tool hat keinen ausführbaren Handler (Schema-only, z. B. nach Cache-Reload)."""

    def __init__(self, name: str) -> None:
        self.tool_name = name
        super().__init__(
            f"Tool {name!r} ist schema-only (kein Handler). "
            "Handler via registry.register_handler(...) nach dem Cache-Reload erneut anhängen."
        )


class ToolTimeout(CielError):
    """Ein Tool-Aufruf hat sein Zeitbudget überschritten."""

    def __init__(self, name: str, timeout_sec: float) -> None:
        self.tool_name = name
        self.timeout_sec = timeout_sec
        super().__init__(f"Tool {name!r} überschritt das Timeout von {timeout_sec:g}s")


__all__ = ["CielConfigError", "CielError", "ToolNotExecutable", "ToolNotFound", "ToolTimeout"]
