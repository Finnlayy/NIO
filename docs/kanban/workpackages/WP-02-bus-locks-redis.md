# WP-02: Event-Bus, Locks, Heartbeats, Tokens + Redis-RESP-Client

Lies zuerst `00-README.md`. Du lieferst `KanbanBus`, `LockManager`, `HeartbeatStore`
und `TokenStore` **exakt** wie dort spezifiziert.

## Dateien
### `orchestrator/kanban/bus.py` (Stdlib, In-Process)
- `InProcessBus`
  - Jeder `subscribe()`-Aufruf bekommt eine eigene `asyncio.Queue(maxsize=1000)`.
  - `publish` verteilt mit `put_nowait`. Ist eine Queue voll, wird das Event für diesen
    Abonnenten verworfen und `self.dropped` gezählt; der Publisher blockiert nie.
    Muster: `apollo/ciel/telemetry.py`.
  - `close()` beendet alle Iteratoren mit einem Sentinel.
- `NeuEventBridge(bus: orchestrator.events.EventBus)` ist ein zusätzlicher Abonnent.
  Er leitet jedes `KanbanEvent` als `bus.emit(f"kanban.{event.kind}", event.to_dict())`
  weiter, damit Events über die vorhandene UDS-Telemetrie in die UI kommen.
- `InMemoryLockManager`, `InMemoryHeartbeatStore`, `InMemoryTokenStore`:
  - Dicts mit Ablaufzeit über `time.monotonic()`, geschützt durch `asyncio.Lock`.
  - Abgelaufene Einträge zählen als nicht vorhanden.
  - `TokenStore` speichert unter `sha256(token)`, nie den Klartext als Schlüssel.

### `orchestrator/kanban/redis_resp.py` (Stdlib, asyncio)
- `RedisClient.from_url("redis://[:pw@]host:port/db")` nutzt `asyncio.open_connection`.
  - Nach dem Verbinden `AUTH` (falls Passwort) und `SELECT db`.
  - Ein `asyncio.Lock` serialisiert Request und Response pro Verbindung.
- RESP2-Encoder: Arrays von Bulk-Strings.
- Parser für `+ - : $ *`. Eine `-`-Antwort wirft `RedisError(msg)`; `$-1`/`*-1` ergibt `None`.
- Befehle: `set(key, val, nx=False, px=None)`, `get`, `delete`, `exists`, `pexpire`,
  `publish`, `eval(script, keys, args)`, `ping`, `close`.
- `subscribe(channel)` öffnet eine **eigene** Verbindung und liefert ein
  `AsyncIterator[bytes]`, das nur die Payloads der `message`-Frames ausgibt.
- Adapter auf die Protocols:
  - `RedisBus`: Kanal `kanban:events`, JSON von `KanbanEvent.to_dict()`.
  - `RedisLockManager`: `SET kanban:lock:{key} owner NX PX`.
    - Release per Lua: `if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end`.
    - Refresh analog mit `pexpire`.
  - `RedisHeartbeatStore`: `SET kanban:hb:{task_id} <json {ts, worker_uid}> PX ttl`; `alive` = `EXISTS`.
  - `RedisTokenStore`: `SET kanban:token:{sha256} <json claims> PX ttl`.
- Timeouts: Jeder Befehl läuft in `asyncio.wait_for(..., timeout)` (Default 5 s,
  Konstruktor-Parameter). Bei Verbindungsabbruch einmal neu verbinden und den Befehl
  einmal wiederholen, außer bei `eval`/`publish`.

## Tests
- `tests/test_kanban_bus.py`:
  - Fan-out an zwei Abonnenten.
  - Volle Queue verwirft das Event und erhöht `dropped`; der Publisher blockiert nicht.
  - Lock: zweiter `acquire` scheitert, fremder `release` scheitert, nach TTL ist der Lock frei.
  - Heartbeat läuft ab.
  - Token: `get` nach `revoke` ergibt `None`.
- `tests/test_kanban_redis_resp.py`:
  - Schreib einen **Fake-RESP-Server** im Test mit `asyncio.start_server`, der
    SET (NX/PX), GET, DEL, EXISTS, PEXPIRE, PUBLISH/SUBSCRIBE, PING, AUTH, SELECT und das
    eine Release-Lua-Skript (per Skript-Text erkannt) in einem Dict nachbildet.
  - Teste damit dieselben Fälle wie bei den In-Memory-Varianten.
  - Teste außerdem das Parsen aller fünf Antworttypen, inklusive Fehlerantwort und Null-Bulk.
- Keine echten Redis-Server, keine Fremdpakete.

## Fertig, wenn
Die Abnahme ist grün und `ruff`/`mypy` sind sauber.
