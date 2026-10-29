# WP-06: `KanbanService`, `kanban_*`-Agent-Tools, MCP-Shim, Ciel-Registrierung

Lies zuerst `00-README.md`. Du lieferst `KanbanService` exakt nach Signatur und nutzt
die WP-02-Protocols (für Tests die In-Memory-Varianten oder eigene Fakes).

## `orchestrator/kanban/service.py`
Die einzige Stelle, die Statusänderungen und Audit verbindet. Jede Methode schreibt ein
Audit-Ereignis (`category="task"` bzw. `"worker"`, `actor` wie übergeben) und publiziert
ein `KanbanEvent` (`kind` z. B. `task.created`, `task.transition`, `task.completed`,
`task.blocked`, `worker.created`).
- `create_task` prüft:
  - Das Board existiert.
  - `parent_id` existiert, falls gesetzt.
  - Jede ID in `dependencies` existiert und es entsteht **kein Zyklus**. DFS über die
    Abhängigkeiten; im Fehlerfall `ValueError`.
  - Der Titel ist 1..200 Zeichen lang.
- `transition`:
  - `models.check_transition(current, target)`, dann `store.cas_task(id, expected or current, {status: target, **changes})`.
  - Scheitert das CAS, `ConflictError` (eigene Exception, `__all__`).
- `complete`: `in_progress → completed` mit `result_payload`, `assigned_worker_uid` bleibt.
- `block`: aus jedem nicht-terminalen Status nach `blocked` mit `block_reason`.
- `heartbeat` delegiert an `HeartbeatStore.beat(task_id, config.heartbeat_ttl_s, worker_uid=…)`.
- `create_worker`:
  - UID prüfen.
  - Ist `soul_md` leer, `soul.default_soul(...)` aus WP-05 nehmen. Fehlt WP-05 noch,
    vorübergehend eine minimale Seele mit Frontmatter.
  - `store.upsert_worker`.

## `orchestrator/kanban/tools.py`
- `TOOL_DEFINITIONS: list[dict]` im MCP-Format `{"name","description","inputSchema"}` für:
  - `kanban_show {task_id?}`: Default ist der eigene Task.
  - `kanban_create {title, description?, required_skills?, dependencies?}`: legt immer
    ein **Kind des eigenen Tasks** an, mit `status="backlog"`.
  - `kanban_block {reason}`.
  - `kanban_complete {result_payload: object}`.
  - `kanban_heartbeat {note?}`.
- `class KanbanToolbox(service, tokens)` mit `async call(name, arguments, token) -> dict`:
  - `claims = await tokens.get(token)`. Fehlen sie, `PermissionError("invalid or expired task token")`.
  - **Scope**: Ein Worker darf nur `claims["task_id"]` und dessen direkte Kinder lesen,
    und nur den eigenen Task blockieren oder abschließen.
  - `actor = f"worker:{claims['worker_uid']}"`.
  - Unbekanntes Tool ergibt `KeyError`. Argumente gegen `inputSchema` mit
    `core.schemacheck.validate` prüfen, Fehler ergeben `ValueError`.
  - Rückgabe ist immer JSON-serialisierbar.
- `register_kanban_tools(registry, toolbox, token_provider: Callable[[], str])`:
  registriert die fünf Tools in einer Ciel-`ColdStorageRegistry`
  (`apollo/ciel/registry.py::register(tool, handler=…, origin="kanban", persist=False)`).
  Der Handler nimmt das `arguments`-Dict entgegen. Der Import von `apollo` erfolgt **lazy**
  in der Funktion (`orchestrator` darf nicht hart von `apollo` abhängen).

## `orchestrator/kanban/mcp_shim.py` (läuft IN der Sandbox, keine NIO-Imports!)
Ein Stdio-MCP-Server nach Spec `2024-11-05` mit newline-delimited JSON-RPC 2.0 auf
stdin/stdout.
- `initialize` antwortet mit `{protocolVersion, capabilities:{tools:{}}, serverInfo:{name:"nio-kanban", version:"1"}}`.
- `notifications/initialized` wird ignoriert.
- `tools/list` ruft `GET {NIO_KANBAN_API_URL}/api/v1/kanban/tools` ab.
- `tools/call` sendet `POST {API}/api/v1/kanban/tools/{name}` mit Body
  `{"tool": name, "arguments": {...}}` und Header
  `Authorization: Bearer {NIO_KANBAN_TASK_TOKEN}`.
  - Die Antwort geht als `{"content":[{"type":"text","text": json}], "isError": false}`
    zurück, bei HTTP-Fehler mit `isError: true`.
- `urllib.request` mit 30 s Timeout. Der Token erscheint nie in stderr.

## Tests: `tests/test_kanban_service_tools.py`
- `create_task` lehnt einen Zyklus (A→B→A) und eine fehlende Abhängigkeit ab.
- `transition` lehnt einen unerlaubten Übergang ab; bei einem CAS-Konflikt kommt `ConflictError`.
- Toolbox:
  - Ungültiger Token ergibt `PermissionError`.
  - Worker A kann den Task von Worker B weder lesen noch abschließen.
  - `kanban_create` legt ein Kind mit `parent_id` = eigener Task an.
  - `kanban_complete` setzt `completed` und erzeugt einen Audit-Eintrag mit `actor` `worker:…`.
- MCP-Shim: als Subprozess starten, mit einem lokalen `http.server` als Fake-API.
  `initialize`, `tools/list` und `tools/call` über stdin senden und die Antworten prüfen.
  Den Bearer-Header serverseitig prüfen.
- Ciel: `register_kanban_tools` mit einer echten `ColdStorageRegistry`. Mit
  `registry.get("kanban_show")` (oder dem Äquivalent der Registry-API) prüfen, dass
  das Tool existiert. Der Test wird geskippt, wenn der `apollo`-Import scheitert.

## Fertig, wenn
Die Abnahme ist grün.
