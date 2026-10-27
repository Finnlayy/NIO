"""Geteilte Datenmodelle der Ciel-Schicht (pydantic v2, mit Stdlib-Fallback).

NEU ist laufzeitseitig bewusst Stdlib-only (siehe ``pyproject.toml``).
Ciel nutzt pydantic v2, wenn es installiert ist (``pip install -e '.[ciel]'``),
und fällt sonst auf einen minimalen, API-kompatiblen ``BaseModel``-Shim
zurück, damit der Orchestrator niemals an einer fehlenden Dependency stirbt.

Der Shim unterstützt absichtlich nur die hier verwendete Teilmenge:
 Feld-Defaults, ``Field(default_factory=...)``, ``model_dump()``,
 ``model_dump_json()``, ``model_validate()``, ``model_copy(update=...)``
 sowie verschachtelte Modelle in ``dict``/``list``-Feldern. Keine Validatoren.
"""

from __future__ import annotations

import json
import typing
from typing import Any, get_args, get_origin

try:  # pragma: no cover - je nach Umgebung einer der beiden Zweige
    from pydantic import BaseModel as _PydanticBaseModel
    from pydantic import ConfigDict as _PydanticConfigDict
    from pydantic import Field as _PydanticField

    BaseModel = _PydanticBaseModel
    ConfigDict = _PydanticConfigDict
    Field = _PydanticField
    HAVE_PYDANTIC = True
except ImportError:  # pragma: no cover - Stdlib-Fallback
    HAVE_PYDANTIC = False

    class _FieldInfo:
        __slots__ = ("default", "default_factory", "description")

        def __init__(self, default: Any = ..., default_factory: Any = None, description: str = "") -> None:
            self.default = default
            self.default_factory = default_factory
            self.description = description

    def Field(  # type: ignore[misc]
        default: Any = ...,
        *,
        default_factory: Any = None,
        description: str = "",
        **_ignored: Any,
    ) -> Any:
        return _FieldInfo(default=default, default_factory=default_factory, description=description)

    def ConfigDict(**kwargs: Any) -> dict[str, Any]:  # type: ignore[misc]
        return dict(kwargs)

    _MISSING = object()
    _HINTS_CACHE: dict[type, dict[str, Any]] = {}

    class BaseModel:  # type: ignore[no-redef]
        """Minimaler BaseModel-Shim (nur aktiv ohne pydantic)."""

        model_config: typing.ClassVar[dict[str, Any]] = {}

        def __init__(self, **data: Any) -> None:
            annotations = self._iter_annotations()
            for name, (has_default, default) in annotations.items():
                if name in data:
                    value = data[name]
                elif has_default:
                    if isinstance(default, _FieldInfo):
                        value = default.default_factory() if default.default_factory is not None else default.default
                    else:
                        value = default
                    if value is Ellipsis:
                        raise TypeError(f"Feld '{name}' ist erforderlich")
                else:
                    raise TypeError(f"Feld '{name}' ist erforderlich")
                object.__setattr__(self, name, self._coerce(name, value))

        @classmethod
        def _iter_annotations(cls) -> dict[str, tuple[bool, Any]]:
            fields: dict[str, tuple[bool, Any]] = {}
            for klass in reversed(cls.__mro__):
                for name, _tp in getattr(klass, "__annotations__", {}).items():
                    if name.startswith("_") or name == "model_config":
                        continue
                    default = klass.__dict__.get(name, _MISSING)
                    fields[name] = (default is not _MISSING, default)
            return fields

        @classmethod
        def _field_type(cls, name: str) -> Any:
            # get_type_hints() löst String-Annotationen (from __future__ import
            # annotations) zu echten Typen auf — nötig für verschachtelte Modelle.
            hints = _HINTS_CACHE.get(cls)
            if hints is None:
                try:
                    hints = dict(typing.get_type_hints(cls))
                except Exception:
                    hints = {}
                _HINTS_CACHE[cls] = hints
            if name in hints:
                return hints[name]
            for klass in cls.__mro__:
                if name in getattr(klass, "__annotations__", {}):
                    return klass.__annotations__[name]
            return Any

        @classmethod
        def _coerce(cls, name: str, value: Any) -> Any:
            if value is None:
                return None
            tp = cls._field_type(name)
            origin = get_origin(tp)
            args = [a for a in get_args(tp) if a is not type(None)]
            target = args[0] if origin is not None and len(args) == 1 else (tp if origin is None else None)
            if isinstance(target, type) and issubclass(target, BaseModel) and isinstance(value, dict):
                return target(**value)
            if origin in (list, tuple) and args and isinstance(value, (list, tuple)):
                item = args[0]
                if isinstance(item, type) and issubclass(item, BaseModel):
                    return [v if isinstance(v, item) else item(**v) for v in value]
            return value

        def model_dump(self, *, mode: str = "python") -> dict[str, Any]:
            _ = mode
            return {name: _dump_value(object.__getattribute__(self, name)) for name in self._iter_annotations()}

        def model_dump_json(self) -> str:
            return json.dumps(self.model_dump(), ensure_ascii=False, sort_keys=True)

        @classmethod
        def model_validate(cls, obj: Any) -> BaseModel:
            if isinstance(obj, cls):
                return obj
            if isinstance(obj, dict):
                return cls(**obj)
            raise TypeError(f"model_validate erwartet dict oder {cls.__name__}, bekam {type(obj).__name__}")

        def model_copy(self, *, update: dict[str, Any] | None = None) -> BaseModel:
            data = self.model_dump()
            if update:
                data.update(update)
            return type(self)(**data)

        def __eq__(self, other: Any) -> bool:
            return isinstance(other, BaseModel) and type(self) is type(other) and self.model_dump() == other.model_dump()

        def __repr__(self) -> str:
            inner = ", ".join(f"{k}={v!r}" for k, v in self.model_dump().items())
            return f"{type(self).__name__}({inner})"


def _dump_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, dict):
        return {k: _dump_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_dump_value(v) for v in value]
    return value


# ---------------------------------------------------------------------------
# Ciel-Modelle
# ---------------------------------------------------------------------------


class ToolSchema(BaseModel):
    """Vollständiges JSON-Schema eines einzelnen (FastMCP-)Tools.

    Das ist die Einheit, die in der Cold-Storage-Registry liegt — *nicht* im
    LLM-Kontext. ``handler`` ist prozesslokal (nicht persistierbar) und zeigt
    auf die ausführbare Funktion (async oder sync).
    """

    model_config = ConfigDict(extra="ignore")

    name: str
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    required_state_keys: list[str] = Field(default_factory=list)
    is_deterministic: bool = False
    timeout_sec: float = 30.0
    concept_anchor: list[float] = Field(default_factory=list)
    origin: str = "fastmcp"
    meta: dict[str, Any] = Field(default_factory=dict)


class ScoredTool(BaseModel):
    """Ein Registry-Treffer mit NCM-Confidence."""

    model_config = ConfigDict(extra="ignore")

    name: str
    score: float
    record: ToolSchema


class GateDecision(BaseModel):
    """Routing-Entscheidung des NCM-Gatekeepers (Pfad 1 oder Pfad 2)."""

    model_config = ConfigDict(extra="ignore")

    path: str  # "system1_bypass" | "system2_jit"
    confidence: float = 0.0
    tool: str | None = None
    top_tools: list[str] = Field(default_factory=list)
    required_state_keys: list[str] = Field(default_factory=list)
    missing_state_keys: list[str] = Field(default_factory=list)
    result: Any = None
    error: str = ""
    llm_calls: int = 0
    reason: str = ""


class ToolCall(BaseModel):
    """Ein vom LLM angeforderter Tool-Aufruf (OpenAI-Shape)."""

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class AssistantMessage(BaseModel):
    """Antwort eines LLM-Clients: Text und/oder Tool-Calls."""

    model_config = ConfigDict(extra="ignore")

    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)


class ToolResult(BaseModel):
    """Ergebnis eines einzelnen (Sandbox-)Tool-Aufrufs."""

    model_config = ConfigDict(extra="ignore")

    call_id: str
    name: str
    ok: bool = True
    result: Any = None
    error: str = ""
    timed_out: bool = False
    elapsed_s: float = 0.0


class AgentResult(BaseModel):
    """Gesamtergebnis eines Sandbox-Agenten-Laufs."""

    model_config = ConfigDict(extra="ignore")

    path: str  # initialer Gate-Pfad
    final_answer: str = ""
    tool_calls: list[str] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    llm_calls: int = 0
    turns: int = 0


class MacroSynthesis(BaseModel):
    """Protokoll einer Makro-Synthese (Modul D)."""

    model_config = ConfigDict(extra="ignore")

    macro_name: str
    chain: list[str] = Field(default_factory=list)
    runs_observed: int = 0
    created: bool = False


__all__ = [
    "HAVE_PYDANTIC",
    "AgentResult",
    "AssistantMessage",
    "BaseModel",
    "ConfigDict",
    "Field",
    "GateDecision",
    "MacroSynthesis",
    "ScoredTool",
    "ToolCall",
    "ToolResult",
    "ToolSchema",
]
