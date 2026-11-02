# WP-08: JSON-Schemas, Golden-Fixtures, Rust-Crate `nio-contracts`, Paritätstests

Lies zuerst `00-README.md`. Die Quelle der Wahrheit sind die Dataclasses in
`orchestrator/kanban/models.py` (fertig).

## `protocol/kanban/*.schema.json` (Draft 2020-12)
Ein Schema pro Typ: `task`, `worker`, `experience`, `audit_entry`, `event`, `tool_call`,
`rust_limb`, `rust_limb_request` und `rust_limb_response`.
- `additionalProperties: false`, alle Felder aus `to_dict()` als `required`.
- Nullable-Felder als `"type": ["string","null"]`, Enums für `status`.
- Nur Schlüsselwörter, die `core/schemacheck.py` versteht (siehe dessen Docstring).
  **Kein** `$ref`, also inline definieren.

## `tests/fixtures/kanban/*.json`
- Pro Typ mindestens zwei Fixtures: `task_minimal.json`, `task_full.json` (alle optionalen
  Felder gesetzt, verschachtelter `result_payload`), `worker.json`, `experience.json`,
  `audit_entry.json` usw.
- Erzeugen über `X.from_dict(...).to_dict()`, damit sie exakt der Python-Serialisierung
  entsprechen. Gespeichert mit `json.dumps(obj, indent=2, ensure_ascii=False) + "\n"`.

## `rust/nio-contracts/` (eigenständig, nicht in einem Workspace)
- `Cargo.toml`: `edition = "2021"`, deps `serde = { version = "1", features = ["derive"] }`, `serde_json = "1"`.
- `src/lib.rs`: Structs mit `#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]`
  und `#[serde(deny_unknown_fields)]`.
  - Feldnamen identisch zu Python (snake_case), `Option<T>` für nullable Felder.
  - `serde_json::Value` bzw. `serde_json::Map<String, Value>` für `result_payload`,
    `payload`, `params`, `arguments` und `result`.
  - Enums `TaskStatus` und `WorkerStatus` mit `#[serde(rename_all = "snake_case")]`.
  - `pub const CONTRACT_VERSION: &str = "1.0";`
- `tests/fixtures.rs`: Für jede Datei in `../../tests/fixtures/kanban/` den Typ nach
  Präfix wählen, deserialisieren, wieder serialisieren und als `serde_json::Value` mit
  dem Original vergleichen (Gleichheit).
- Ein Negativtest: Eine Fixture mit einem Zusatzfeld muss beim Deserialisieren scheitern.
- `.gitignore` im Crate: `target/`.

## Python-Seite: `tests/test_kanban_contracts.py`
- Jede Fixture validiert gegen ihr Schema (`core.schemacheck.validate(data, schema) == []`).
- Es gilt `X.from_dict(fixture).to_dict() == fixture`.
- `set(schema["properties"]) == set(X(...).to_dict())` für jeden Typ: Drift zwischen
  Dataclass und Schema wird rot.
- Ein Fixture-Satz mit einem Zusatzfeld wird vom Schema abgelehnt.

## Makefile
Ziel `rust-test` ergänzen und in `.PHONY` aufnehmen:
```make
rust-test:  ## Rust-Vertraege (Serde) gegen dieselben Fixtures wie Python
	@if command -v cargo >/dev/null 2>&1; then cargo test --manifest-path rust/nio-contracts/Cargo.toml; \
	else echo "rust-test: cargo fehlt -- uebersprungen"; fi
```
`rust-test` **nicht** in `check` aufnehmen; das entscheidet der Mensch.

## Fertig, wenn
Die Abnahme ist grün und `make rust-test` ist grün.
