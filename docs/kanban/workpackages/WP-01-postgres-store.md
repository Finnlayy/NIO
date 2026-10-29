# WP-01: Postgres-Store (`orchestrator/kanban/store_pg.py`)

Lies zuerst `00-README.md` (Konventionen und Schnittstellen).

## Ziel
`PostgresKanbanStore` ist dasselbe `KanbanStore`-Protocol wie `SqliteKanbanStore`
(`orchestrator/kanban/store.py`), nur auf PostgreSQL mit `asyncpg`.

## Umsetzen
- `asyncpg` wird **lazy** in `init()` importiert. Fehlt das Paket, kommt ein
  `RuntimeError("PostgresKanbanStore braucht asyncpg: pip install -e '.[kanban]'")`.
- `asyncpg.create_pool(dsn, min_size=1, max_size=10, init=_init_conn)`. In `_init_conn`
  JSON-Codecs setzen: `conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")`
  und dasselbe für `json`.
- Migrationen: `schema_version(version INT PRIMARY KEY, applied_at TIMESTAMPTZ)`.
  - Anwenden mit `migration_scripts("postgres")` aus `store.py`, jede Version in einer
    eigenen Transaktion.
  - Davor `pg_advisory_xact_lock(hashtext('nio_kanban_migrate'))`, damit zwei Prozesse
    nicht gleichzeitig migrieren.
- Zeitstempel: Die Spalten sind `TIMESTAMPTZ`, die Modelle nutzen ISO-Strings.
  - Schreiben: String mit `core.protocol.parse_timestamp(value, "field")` in ein
    `datetime` wandeln.
  - Lesen: `core.protocol.format_timestamp(dt)`.
  - Kapsel das in `_to_db(changes)` und `_from_row(record)`.
- Die Whitelist `TASK_MUTABLE`/`WORKER_MUTABLE` aus `store.py` wiederverwenden (importieren,
  nicht kopieren). Platzhalter `$1, $2, …` dynamisch bauen.
- CAS wie in SQLite: `UPDATE … WHERE id=$n AND status=$m RETURNING *`.
- `promotable_tasks`: dieselbe Logik wie SQLite, mit
  `jsonb_array_elements_text(t.dependencies) AS d(dep_id)`.
- `apply_decomposition` und `finish_run` laufen in `async with conn.transaction():`.
  Scheitert das CAS in `finish_run`, Exception auslösen und abfangen, damit die
  Transaktion zurückrollt und `None` zurückkommt.
- `append_audit`:
  - In der Transaktion zuerst `SELECT pg_advisory_xact_lock(hashtext('nio_audit_ledger'))`,
    dann den letzten `entry_hash` lesen, `audit.seal(prev, draft)` aufrufen und einfügen.
    Das serialisiert die Kette.
  - `prev_hash`/`entry_hash` sind `CHAR(64)`, also beim Lesen `.strip()` anwenden.
- `close()` schließt den Pool.

## Tests: `tests/test_kanban_store_pg.py`
- `@unittest.skipUnless(os.environ.get("NIO_KANBAN_TEST_PG_DSN"), …)` und zusätzlich
  skippen, wenn `asyncpg` nicht importierbar ist.
- Pro Test ein eigenes Schema: `CREATE SCHEMA t_<uuid>` plus `SET search_path` über
  `server_settings` beim Pool, und am Ende `DROP SCHEMA … CASCADE`.
- Prüfe dieselben Fälle wie SQLite:
  - Migration ist idempotent (zweimal `init()`).
  - Zwei parallele `cas_task(..., READY → IN_PROGRESS)` per `asyncio.gather` ergeben genau
    einen Erfolg.
  - Dekomposition, Promotion und Roll-up.
  - `UPDATE audit_ledger` wirft eine Exception.
  - `AuditLedger(store).verify() == []` nach zehn parallelen `append`s.
- Lokal testen, wenn du willst:
  ```bash
  docker run --rm -d -p 5433:5432 -e POSTGRES_PASSWORD=pw postgres:16
  NIO_KANBAN_TEST_PG_DSN=postgresql://postgres:pw@127.0.0.1:5433/postgres
  ```

## Fertig, wenn
Die Abnahme aus `00-README.md` ist grün: ohne DSN wird der PG-Test geskippt, mit DSN
und `asyncpg` installiert ist er grün.
