"""Modul A: Cold-Storage Skill Registry.

Fängt alle FastMCP-Tools beim Server-Start ab und speichert deren
vollständige JSON-Schemas lokal (In-Memory + SQLite/JSON-Cache), **anstatt**
sie in den System-Prompt des LLMs zu injizieren. Der LLM-Kontext sieht später
nur die JIT-Teilmenge aus :mod:`apollo.ciel.ncm_gate` (Top-3 + Meta-Tool).

Abwärtskompatibilität (Pflichtregel 1): Dieses Modul *liest* fremde
Tool-Objekte duck-typed und verändert sie nicht. :class:`CielFastMCPWrapper`
delegiert jede nicht abgefangene Operation an die gewrappte FastMCP-Instanz —
bestehende Routen und Interfaces bleiben unangetastet.
"""

from __future__ import annotations

import inspect
import json
import re
import sqlite3
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .bus import emit
from .embeddings import EmbeddingProvider, HashEmbeddingProvider, cosine_similarity
from .errors import CielConfigError, ToolNotFound
from .models import ScoredTool, ToolSchema
from .telemetry import NODE_COLD, CielTelemetryPublisher, cold_state_sync_event, estimate_tokens

#: Ein Handler bekommt die Tool-Argumente und liefert ein JSON-fähiges Ergebnis.
ToolHandler = Callable[..., Any]

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS ciel_tools (
  name TEXT PRIMARY KEY,
  description TEXT NOT NULL,
  parameters_json TEXT NOT NULL,
  required_state_keys_json TEXT NOT NULL DEFAULT '[]',
  is_deterministic INTEGER NOT NULL DEFAULT 0,
  timeout_sec REAL NOT NULL DEFAULT 30.0,
  anchor_json TEXT NOT NULL DEFAULT '[]',
  origin TEXT NOT NULL DEFAULT 'fastmcp',
  meta_json TEXT NOT NULL DEFAULT '{}',
  updated_at TEXT NOT NULL
);
"""


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


_NODE_SANITIZE_RE = re.compile(r"[^a-zA-Z0-9_.-]+")


def node_id_for(tool_name: str) -> str:
    """Deterministische Graph-Node-ID eines Tools (UI-Graph, Modul E)."""
    safe = _NODE_SANITIZE_RE.sub("-", tool_name.strip()).strip("-") or "unnamed"
    return f"ciel-node-{safe}"[:120]


def cluster_for(origin: str, meta: Mapping[str, Any] | None = None) -> str:
    """Cluster-Zugehoerigkeit eines Tools (UI-Graph; Default: Herkunft)."""
    if meta:
        cluster = meta.get("cluster")
        if isinstance(cluster, str) and cluster.strip():
            return cluster.strip()[:60]
    return (origin or "fastmcp").strip()[:60] or "fastmcp"


def _meta_tokens(meta: Mapping[str, Any] | None) -> int:
    if not meta:
        return 0
    tokens = meta.get("tokens_estimate", 0)
    return int(tokens) if isinstance(tokens, (int, float)) and tokens > 0 else 0


def normalize_tool_candidate(candidate: Any) -> dict[str, Any]:
    """Normalisiert ein duck-typed Tool (FastMCP-Tool, Dict, Limb-Eintrag, ...).

    Versteht u. a. die FastMCP-Formen (``name``/``description``/``parameters``,
    ``inputSchema``/``input_schema``, Handler unter ``fn``/``func``/``handler``/
    ``call``/``execute``/``run``) sowie plain Dicts. Wirft
    :class:`CielConfigError`, wenn kein Name ermittelbar ist.
    """
    if isinstance(candidate, ToolSchema):
        data = candidate.model_dump()
        data["handler"] = getattr(candidate, "__ciel_handler__", None)
        return data
    if isinstance(candidate, Mapping):
        data = dict(candidate)
    else:
        data = {}
        for attr in ("name", "tool_name", "title"):
            value = getattr(candidate, attr, None)
            if isinstance(value, str) and value:
                data["name"] = value
                break
        for attr in ("description", "doc", "__doc__"):
            value = getattr(candidate, attr, None)
            if isinstance(value, str) and value.strip() and attr != "__doc__":
                data["description"] = value.strip()
                break
            if attr == "__doc__" and isinstance(value, str) and value.strip() and "description" not in data:
                data["description"] = value.strip().splitlines()[0][:500]
        for attr in ("parameters", "inputSchema", "input_schema", "args_schema", "schema"):
            value = getattr(candidate, attr, None)
            if isinstance(value, Mapping):
                data["parameters"] = dict(value)
                break
            if attr == "args_schema" and inspect.isclass(value):
                model_dump = getattr(value, "model_json_schema", None)
                if callable(model_dump):
                    with suppress(Exception):
                        data["parameters"] = dict(model_dump())
                break
        for attr in ("required_state_keys", "required_keys", "state_keys"):
            value = getattr(candidate, attr, None)
            if isinstance(value, (list, tuple)):
                data["required_state_keys"] = [str(v) for v in value]
                break
        for attr in ("is_deterministic", "deterministic"):
            if getattr(candidate, attr, None) is not None:
                data["is_deterministic"] = bool(getattr(candidate, attr))
                break
        for attr in ("timeout_sec", "timeout", "timeout_s"):
            value = getattr(candidate, attr, None)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                data["timeout_sec"] = float(value)
                break
        for attr in ("fn", "func", "handler", "call", "execute", "run", "callback", "coro"):
            value = getattr(candidate, attr, None)
            if callable(value):
                data["handler"] = value
                break
        meta = getattr(candidate, "meta", None) or getattr(candidate, "metadata", None)
        if isinstance(meta, Mapping):
            data["meta"] = dict(meta)
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise CielConfigError(f"Tool ohne Namen kann nicht registriert werden: {type(candidate).__name__}")
    data["name"] = name.strip()
    return data


class ColdStorageRegistry:
    """Cold-Storage für Tool-Schemas (In-Memory primär, SQLite/JSON als Cache).

    * ``register*`` nimmt FastMCP-Tools (oder Dicts/ToolSchema) entgegen und
      berechnet je Tool einen Concept-Anchor-Vektor für das NCM-Matching.
    * Handler (Callables) sind prozesslokal und werden **nicht** persistiert;
      nach einem Cache-Reload sind Einträge schema-only, bis
      :meth:`register_handler` sie wieder ausführbar macht.
    """

    def __init__(
        self,
        *,
        embedder: EmbeddingProvider | None = None,
        cache_path: str | Path | None = None,
        event_bus: Any | None = None,
        telemetry: CielTelemetryPublisher | None = None,
    ) -> None:
        self._embedder: EmbeddingProvider = embedder or HashEmbeddingProvider()
        self._records: dict[str, ToolSchema] = {}
        self._handlers: dict[str, ToolHandler] = {}
        self._bus = event_bus
        self._telemetry = telemetry
        self._cold_tokens_total = 0
        self._cache_path = Path(cache_path) if cache_path is not None else None
        if self._cache_path is not None and self._cache_path.is_file():
            self.load_cache(self._cache_path)

    # -- Introspektion ----------------------------------------------------

    def __len__(self) -> int:
        return len(self._records)

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._records

    @property
    def embedder(self) -> EmbeddingProvider:
        return self._embedder

    @property
    def cache_path(self) -> Path | None:
        return self._cache_path

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._records))

    def get(self, name: str) -> ToolSchema | None:
        return self._records.get(name)

    def require(self, name: str) -> ToolSchema:
        record = self._records.get(name)
        if record is None:
            raise ToolNotFound(name)
        return record

    def get_handler(self, name: str) -> ToolHandler | None:
        return self._handlers.get(name)

    def anchor_text(self, name: str) -> str:
        """Exakt der Text, aus dem der Concept-Anchor eines Tools berechnet wurde."""
        record = self.require(name)
        return f"{record.name} {record.description}".strip()

    @property
    def telemetry(self) -> CielTelemetryPublisher | None:
        return self._telemetry

    @property
    def cold_tokens_total(self) -> int:
        """Geschaetzte Tokens aller Cold-Storage-Schemas (laufend mitgezaehlt)."""
        return self._cold_tokens_total

    def saved_tokens_estimate(self, injected: Iterable[str]) -> int:
        """Differenz Cold-Schemas vs. injizierte Schemas (Live-Token-Saver-Counter)."""
        injected_tokens = 0
        for name in injected:
            record = self._records.get(name)
            if record is not None:
                injected_tokens += _meta_tokens(record.meta)
        return max(0, self._cold_tokens_total - injected_tokens)

    def to_graph_nodes(self, names: Iterable[str] | None = None, *, status: str = NODE_COLD) -> list[dict[str, Any]]:
        """Projiziert Tools auf UI-Graph-Nodes (node_id, tool, status, cluster)."""
        selected = list(names) if names is not None else list(self._records)
        nodes: list[dict[str, Any]] = []
        for name in selected:
            record = self._records.get(name)
            if record is None:
                continue
            nodes.append(
                {
                    "node_id": record.node_id or node_id_for(record.name),
                    "tool": record.name,
                    "confidence_score": 0.0,
                    "status": status,
                    "cluster": cluster_for(record.origin, record.meta),
                }
            )
        return nodes

    def publish_cold_state_sync(self, *, intent: str = "", trace_id: str = "") -> bool:
        """Publiziert ``CIEL_COLD_STATE_SYNC`` (alle Nodes als COLD, non-blocking).

        Gibt ``False`` zurueck, wenn kein Telemetry-Publisher verdrahtet ist
        oder die Queue voll war — die Pipeline laeuft unbeeinflusst weiter.
        """
        if self._telemetry is None:
            return False
        return self._telemetry.publish(
            cold_state_sync_event(
                self.to_graph_nodes(status=NODE_COLD),
                intent=intent,
                trace_id=trace_id,
                detail={"tools": len(self._records), "cold_tokens_total": self._cold_tokens_total},
            )
        )

    # -- Registrierung ----------------------------------------------------

    def register(
        self,
        tool: Any,
        *,
        handler: ToolHandler | None = None,
        origin: str = "fastmcp",
        required_state_keys: Sequence[str] | None = None,
        is_deterministic: bool | None = None,
        timeout_sec: float | None = None,
        persist: bool = True,
    ) -> ToolSchema:
        """Registriert ein einzelnes Tool und berechnet seinen Concept-Anchor."""
        data = normalize_tool_candidate(tool)
        name: str = data["name"]
        parameters = dict(data.get("parameters") or {})
        if not isinstance(parameters, dict):
            parameters = {"type": "object", "properties": {}}
        parameters.setdefault("type", "object")
        if required_state_keys is not None:
            keys = [str(k) for k in required_state_keys]
        elif data.get("required_state_keys"):
            keys = [str(k) for k in data["required_state_keys"]]
        else:
            required = parameters.get("required")
            keys = [str(k) for k in required] if isinstance(required, (list, tuple)) else []
        deterministic = data.get("is_deterministic", False) if is_deterministic is None else is_deterministic
        timeout = data.get("timeout_sec", 30.0) if timeout_sec is None else timeout_sec
        description = str(data.get("description") or "")
        anchor = self._embedder.embed(f"{name} {description}".strip())
        meta = dict(data.get("meta") or {})
        node_id = str(data.get("node_id") or meta.get("node_id") or node_id_for(name))
        meta["node_id"] = node_id  # persistiert node_id im bestehenden meta_json (kein Schema-Bruch)
        tokens = estimate_tokens({"name": name, "description": description, "parameters": parameters})
        meta["tokens_estimate"] = tokens
        record = ToolSchema(
            name=name,
            description=description,
            parameters=parameters,
            required_state_keys=keys,
            is_deterministic=bool(deterministic),
            timeout_sec=float(timeout),
            concept_anchor=list(anchor),
            origin=str(data.get("origin") or origin),
            node_id=node_id,
            meta=meta,
        )
        resolved_handler = handler if handler is not None else data.get("handler")
        previous = self._records.get(name)
        if previous is not None:
            self._cold_tokens_total -= _meta_tokens(previous.meta)
        self._records[name] = record
        self._cold_tokens_total += tokens
        if callable(resolved_handler):
            self._handlers[name] = resolved_handler
        else:
            self._handlers.pop(name, None)
        if persist:
            self._write_through(name)
        return record

    def register_many(self, tools: Iterable[Any], *, origin: str = "fastmcp") -> list[ToolSchema]:
        """Registriert viele Tools (ein Event, ein Cache-Write pro Tool)."""
        records = [self.register(tool, origin=origin, persist=False) for tool in tools]
        if self._cache_path is not None:
            self.save_cache(self._cache_path)
        return records

    def register_handler(self, name: str, handler: ToolHandler) -> ToolSchema:
        """Hängt (erneut) einen ausführbaren Handler an ein registriertes Tool."""
        record = self.require(name)
        if not callable(handler):
            raise CielConfigError(f"Handler für {name!r} ist nicht aufrufbar.")
        self._handlers[name] = handler
        return record

    def unregister(self, name: str) -> bool:
        """Entfernt ein Tool (bei Bedarf inkl. Cache-Zeile)."""
        removed = self._records.pop(name, None)
        existed = removed is not None
        if removed is not None:
            self._cold_tokens_total = max(0, self._cold_tokens_total - _meta_tokens(removed.meta))
        self._handlers.pop(name, None)
        if existed and self._cache_path is not None:
            try:
                with sqlite3.connect(str(self._cache_path)) as conn:
                    conn.execute("DELETE FROM ciel_tools WHERE name = ?", (name,))
            except sqlite3.Error:
                pass
        return existed

    # -- Matching ---------------------------------------------------------

    def search_by_vector(self, vector: Sequence[float], *, top_k: int = 3) -> list[ScoredTool]:
        """Top-k Tools nach Cosine-Similarity gegen die Concept-Anchors."""
        vec = list(vector)
        scored = [
            ScoredTool(name=name, score=cosine_similarity(vec, record.concept_anchor), record=record)
            for name, record in self._records.items()
            if record.concept_anchor
        ]
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[: max(0, top_k)]

    def search(self, query: str, *, top_k: int = 3, exclude: Iterable[str] = ()) -> list[ScoredTool]:
        """Betten + Top-k-Suche in einem Schritt (mit Ausschlussliste)."""
        excluded = set(exclude)
        return [hit for hit in self.search_by_vector(self._embedder.embed(query), top_k=top_k + len(excluded)) if hit.name not in excluded][
            : max(0, top_k)
        ]

    # -- Prompt-Projektion --------------------------------------------------

    def to_prompt_schemas(self, names: Iterable[str]) -> list[dict[str, Any]]:
        """Projiziert benannte Tools auf LLM-Prompt-Schemas (OpenAI-Shape).

        Enthält bewusst nur Name/Beschreibung/Parameter — niemals Registry-
        Interna (Anchors, Handler, Herkunft).
        """
        schemas: list[dict[str, Any]] = []
        for name in names:
            record = self._records.get(name)
            if record is None:
                continue
            schemas.append({"name": record.name, "description": record.description, "parameters": dict(record.parameters)})
        return schemas

    # -- Persistenz (SQLite-Cache + JSON) ------------------------------------

    def save_cache(self, path: str | Path | None = None) -> Path | None:
        """Schreibt alle Schemas (ohne Handler/Callables) in den SQLite-Cache."""
        target = Path(path) if path is not None else self._cache_path
        if target is None:
            return None
        target.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(target)) as conn:
            conn.executescript(_SCHEMA_SQL)
            conn.executemany(
                "INSERT OR REPLACE INTO ciel_tools "
                "(name, description, parameters_json, required_state_keys_json, is_deterministic,"
                " timeout_sec, anchor_json, origin, meta_json, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        record.name,
                        record.description,
                        json.dumps(record.parameters, ensure_ascii=False, sort_keys=True),
                        json.dumps(record.required_state_keys, ensure_ascii=False),
                        1 if record.is_deterministic else 0,
                        float(record.timeout_sec),
                        json.dumps([float(v) for v in record.concept_anchor]),
                        record.origin,
                        json.dumps(record.meta, ensure_ascii=False, sort_keys=True),
                        utc_now_iso(),
                    )
                    for record in self._records.values()
                ],
            )
        return target

    def load_cache(self, path: str | Path | None = None) -> int:
        """Lädt Schemas aus dem SQLite-Cache (schema-only, ohne Handler)."""
        target = Path(path) if path is not None else self._cache_path
        if target is None or not target.is_file():
            return 0
        with sqlite3.connect(str(target)) as conn:
            conn.executescript(_SCHEMA_SQL)
            rows = conn.execute(
                "SELECT name, description, parameters_json, required_state_keys_json,"
                " is_deterministic, timeout_sec, anchor_json, origin, meta_json FROM ciel_tools"
            ).fetchall()
        loaded = 0
        for row in rows:
            name = str(row[0])
            try:
                record = ToolSchema(
                    name=name,
                    description=str(row[1] or ""),
                    parameters=dict(json.loads(row[2] or "{}")),
                    required_state_keys=[str(k) for k in json.loads(row[3] or "[]")],
                    is_deterministic=bool(row[4]),
                    timeout_sec=float(row[5] or 30.0),
                    concept_anchor=[float(v) for v in json.loads(row[6] or "[]")],
                    origin=str(row[7] or "fastmcp"),
                    meta=dict(json.loads(row[8] or "{}")),
                )
            except (ValueError, TypeError):
                continue
            if not record.concept_anchor:
                record = record.model_copy(update={"concept_anchor": self._embedder.embed(f"{record.name} {record.description}".strip())})
            record = self._adopt_cached_record(record)
            self._records[name] = record
            loaded += 1
        if loaded:
            emit(self._bus, "ciel.registry.cache_loaded", {"tools": loaded, "cache": str(target)})
        return loaded

    def export_json(self, path: str | Path) -> Path:
        """Exportiert alle Schemas (ohne Handler) als JSON-Datei."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": "ciel.registry/1",
            "exported_at": utc_now_iso(),
            "tools": [record.model_dump() for record in self._records.values()],
        }
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return target

    def import_json(self, path: str | Path) -> int:
        """Importiert Schemas aus :meth:`export_json` (schema-only, ohne Handler)."""
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        tools = payload.get("tools", []) if isinstance(payload, dict) else []
        count = 0
        for entry in tools:
            if not isinstance(entry, dict) or "name" not in entry:
                continue
            record = ToolSchema.model_validate(entry)
            if not record.concept_anchor:
                record = record.model_copy(update={"concept_anchor": self._embedder.embed(f"{record.name} {record.description}".strip())})
            record = self._adopt_cached_record(record)
            self._records[record.name] = record
            count += 1
        if count:
            emit(self._bus, "ciel.registry.cache_loaded", {"tools": count, "cache": str(path)})
        return count

    def _adopt_cached_record(self, record: ToolSchema) -> ToolSchema:
        """Normalisiert einen Cache-/JSON-Record (node_id + Token-Buchhaltung)."""
        node_id = record.node_id or str((record.meta or {}).get("node_id") or node_id_for(record.name))
        tokens = _meta_tokens(record.meta)
        meta = dict(record.meta or {})
        meta["node_id"] = node_id
        if tokens <= 0:
            tokens = estimate_tokens({"name": record.name, "description": record.description, "parameters": record.parameters})
            meta["tokens_estimate"] = tokens
        previous = self._records.get(record.name)
        if previous is not None:
            self._cold_tokens_total -= _meta_tokens(previous.meta)
        self._cold_tokens_total += tokens
        if record.node_id == node_id and _meta_tokens(record.meta) == tokens:
            return record
        return record.model_copy(update={"node_id": node_id, "meta": meta})

    def _write_through(self, name: str) -> None:
        if self._cache_path is None:
            return
        with suppress(sqlite3.Error, OSError):
            self.save_cache(self._cache_path)

    # -- Konstruktoren ------------------------------------------------------

    @classmethod
    def from_fastmcp(
        cls,
        server: Any,
        *,
        embedder: EmbeddingProvider | None = None,
        cache_path: str | Path | None = None,
        event_bus: Any | None = None,
        telemetry: CielTelemetryPublisher | None = None,
    ) -> ColdStorageRegistry:
        """Fängt alle Tools einer FastMCP(-ähnlichen) Server-Instanz beim Start ab.

        Duck-typed: versteht ``await server.get_tools()`` / ``get_tools()``,
        ``server._tool_manager._tools`` (FastMCP), ``server._tools`` und
        ``server.tools`` — als Dict oder Iterable. Das Server-Objekt selbst
        wird nicht verändert.
        """
        registry = cls(embedder=embedder, cache_path=cache_path, event_bus=event_bus, telemetry=telemetry)
        tools = _extract_fastmcp_tools(server)
        registry.register_many(tools, origin="fastmcp")
        emit(event_bus, "ciel.registry.snapshot", {"tools": len(registry), "origin": "fastmcp"})
        registry.publish_cold_state_sync()
        return registry

    @classmethod
    def from_limb_registry(
        cls,
        limb_registry: Any,
        *,
        embedder: EmbeddingProvider | None = None,
        cache_path: str | Path | None = None,
        event_bus: Any | None = None,
        telemetry: CielTelemetryPublisher | None = None,
    ) -> ColdStorageRegistry:
        """Spiegelt NEU-Limb-Operations als Cold-Storage-Tools (Brücke, lesend).

        Nutzt nur öffentliche Accessoren (``active()``/``names()``/``get()``);
        das übergebene ``LimbRegistry`` wird nicht verändert.
        """
        registry = cls(embedder=embedder, cache_path=cache_path, event_bus=event_bus, telemetry=telemetry)
        specs: list[Any] = []
        try:
            active = limb_registry.active() if callable(getattr(limb_registry, "active", None)) else ()
            specs = list(active or ())
        except Exception:
            specs = []
        if not specs and callable(getattr(limb_registry, "names", None)) and callable(getattr(limb_registry, "get", None)):
            try:
                specs = [spec for name in limb_registry.names() if (spec := limb_registry.get(name)) is not None]
            except Exception:
                specs = []
        mirrored = 0
        for spec in specs:
            limb_name = getattr(spec, "name", "?")
            operations = getattr(spec, "operations", ()) or ()
            description = getattr(spec, "description", "") or ""
            for operation in operations:
                registry.register(
                    {
                        "name": f"{limb_name}.{operation}",
                        "description": f"[{limb_name}] {operation} — {description}".strip(),
                        "parameters": {"type": "object", "properties": {}},
                        "meta": {"limb": limb_name, "operation": str(operation)},
                    },
                    origin="limb",
                    persist=False,
                )
                mirrored += 1
        if registry.cache_path is not None:
            registry.save_cache(registry.cache_path)
        emit(event_bus, "ciel.registry.snapshot", {"tools": mirrored, "origin": "limb"})
        registry.publish_cold_state_sync()
        return registry


def _extract_fastmcp_tools(server: Any) -> list[Any]:
    """Sammelt Tool-Objekte aus einer FastMCP(-ähnlichen) Server-Instanz (lesend)."""
    candidates: list[Any] = []
    get_tools = getattr(server, "get_tools", None)
    if callable(get_tools):
        try:
            result = get_tools()
            if inspect.isawaitable(result):
                # from_fastmcp ist synchron (Startpfad); ein awaitable get_tools()
                # wird hier nicht erzwungen — siehe CielFastMCPWrapper.ainit().
                pass
            else:
                candidates.append(result)
        except Exception:
            pass
    manager = getattr(server, "_tool_manager", None)
    if manager is not None:
        candidates.append(getattr(manager, "_tools", None))
        candidates.append(getattr(manager, "tools", None))
    candidates.append(getattr(server, "_tools", None))
    candidates.append(getattr(server, "tools", None))
    for candidate in candidates:
        tools = _as_tool_list(candidate)
        if tools:
            return tools
    return []


def _as_tool_list(candidate: Any) -> list[Any]:
    if candidate is None or isinstance(candidate, (str, bytes)):
        return []
    if isinstance(candidate, Mapping):
        return [v for v in candidate.values() if v is not None]
    if isinstance(candidate, (list, tuple, set, frozenset)):
        return [v for v in candidate if v is not None]
    if inspect.isawaitable(candidate):
        return []
    return []


async def extract_fastmcp_tools_async(server: Any) -> list[Any]:
    """Async-Variante: löst auch ``await server.get_tools()`` auf (FastMCP)."""
    get_tools = getattr(server, "get_tools", None)
    if callable(get_tools):
        try:
            result = get_tools()
            if inspect.isawaitable(result):
                result = await result
            tools = _as_tool_list(result)
            if tools:
                return tools
        except Exception:
            pass
    loop_tools = _extract_fastmcp_tools(server)
    if loop_tools:
        return loop_tools
    list_tools = getattr(server, "list_tools", None)
    if callable(list_tools):
        try:
            result = list_tools()
            if inspect.isawaitable(result):
                result = await result
            return _as_tool_list(result)
        except Exception:
            return []
    return []


class CielFastMCPWrapper:
    """Interceptor um eine bestehende FastMCP-Instanz (Pflichtregel 1).

    * Jede nicht abgefangene Attribut-/Methoden-Operation wird an die
      gewrappte Instanz delegiert (``__getattr__``) — Bestandsrouten laufen
      unverändert weiter.
    * Der ``@server.tool``-Decorator wird abgefangen: Die Registrierung läuft
      normal auf dem gewrappten Server weiter (kein Bruch), **zusätzlich**
      wird das Schema ins Cold-Storage gespiegelt.
    * :meth:`tools_for_prompt` liefert bewusst ``[]``: Schemas kommen zur
      Laufzeit ausschließlich per JIT-Injection in den Prompt (Modul B/C).

    Typischer Start::

        mcp = FastMCP("nio")
        ciel = CielFastMCPWrapper(mcp, registry=registry)
        await ciel.ainit()   # fängt alle bereits registrierten Tools ab
    """

    def __init__(self, server: Any, *, registry: ColdStorageRegistry | None = None) -> None:
        self._server = server
        # Achtung: kein `registry or ...` — eine (noch) leere Registry ist
        # via __len__ falsy und würde fälschlich verworfen.
        self._registry = registry if registry is not None else ColdStorageRegistry(event_bus=None)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._server, name)

    @property
    def wrapped(self) -> Any:
        """Die gewrappte Original-Instanz (unverändert)."""
        return self._server

    @property
    def registry(self) -> ColdStorageRegistry:
        return self._registry

    async def ainit(self) -> int:
        """Fängt alle bereits registrierten Tools ins Cold-Storage ab (Startpfad)."""
        tools = await extract_fastmcp_tools_async(self._server)
        self._registry.register_many(tools, origin="fastmcp")
        emit(self._registry._bus, "ciel.registry.snapshot", {"tools": len(tools), "origin": "fastmcp"})
        self._registry.publish_cold_state_sync()
        return len(tools)

    def tool(self, *dargs: Any, **dkwargs: Any) -> Any:
        """Abgefangener ``@server.tool``-Decorator: delegiert + spiegelt ins Cold-Storage."""
        original = getattr(self._server, "tool", None)
        if not callable(original):
            raise CielConfigError("Gewrappter Server hat keinen 'tool'-Decorator.")

        def _mirror(func_or_result: Any) -> Any:
            try:
                candidate: Any = func_or_result
                for attr in ("tool", "_tool", "__ciel_tool__"):
                    nested = getattr(func_or_result, attr, None)
                    if nested is not None and not callable(nested):
                        candidate = nested
                        break
                name = dkwargs.get("name") or getattr(candidate, "name", None) or getattr(func_or_result, "__name__", None)
                description = dkwargs.get("description") or getattr(candidate, "description", None) or ""
                parameters = getattr(candidate, "parameters", None) or getattr(candidate, "inputSchema", None) or {}
                handler = candidate if callable(candidate) else (func_or_result if callable(func_or_result) else None)
                if isinstance(name, str) and name:
                    self._registry.register(
                        {"name": name, "description": str(description or ""), "parameters": dict(parameters or {})},
                        handler=handler,
                        origin="fastmcp",
                    )
            except CielConfigError:
                pass
            return func_or_result

        decorator = original(*dargs, **dkwargs)
        if callable(decorator) and not dargs:

            def _wrapping_decorator(func: ToolHandler) -> Any:
                return _mirror(decorator(func))

            return _wrapping_decorator
        if dargs and callable(dargs[0]) and len(dargs) == 1 and not dkwargs:
            return _mirror(decorator)
        if callable(decorator):

            def _wrapping_decorator_kw(func: ToolHandler) -> Any:
                return _mirror(decorator(func))

            return _wrapping_decorator_kw
        return _mirror(decorator)

    def tools_for_prompt(self) -> list[dict[str, Any]]:
        """Bewusst leer: Prompt-Schemas kommen nur per JIT-Injection (Modul B/C)."""
        return []

    async def call_tool(self, name: str, arguments: Mapping[str, Any] | None = None) -> Any:
        """Führt ein Tool über die gewrappte Instanz aus (Fallback: Registry-Handler)."""
        args = dict(arguments or {})
        for attr in ("call_tool", "execute_tool", "_call_tool"):
            candidate = getattr(self._server, attr, None)
            if callable(candidate):
                try:
                    result = candidate(name, args)
                    if inspect.isawaitable(result):
                        return await result
                    return result
                except TypeError:
                    try:
                        result = candidate(name=name, arguments=args)
                        if inspect.isawaitable(result):
                            return await result
                        return result
                    except Exception:
                        break
                except Exception:
                    break
        handler = self._registry.get_handler(name)
        if handler is None:
            raise ToolNotFound(name)
        result = handler(args) if _takes_single_arg(handler) else handler(**args)
        if inspect.isawaitable(result):
            return await result
        return result


def _takes_single_arg(func: ToolHandler) -> bool:
    try:
        params = list(inspect.signature(func).parameters.values())
    except (TypeError, ValueError):
        return False
    positional = [p for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    return len(positional) == 1 and not any(p.kind is p.VAR_KEYWORD for p in params)


__all__ = [
    "CielFastMCPWrapper",
    "ColdStorageRegistry",
    "ToolHandler",
    "cluster_for",
    "extract_fastmcp_tools_async",
    "node_id_for",
    "normalize_tool_candidate",
    "utc_now_iso",
]
