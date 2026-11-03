# WP-09: Doku, Packaging, CHANGELOG, Ende-zu-Ende-Abnahme

Lies zuerst `00-README.md`. Voraussetzung: WP-01 bis WP-08 sind gemergt.

## Packaging (`pyproject.toml`)
- `[tool.setuptools] packages`: `"orchestrator.kanban"` ergänzen.
- `[tool.setuptools.package-data]`: `"orchestrator.kanban" = ["sql/*.sql"]`.
- `[project.optional-dependencies]`: `kanban = ["asyncpg>=0.29", "fastapi>=0.110", "uvicorn>=0.29", "pydantic>=2"]`
  mit einem deutschen Kommentar im Stil des `ciel`-Extras.
- `[[tool.mypy.overrides]]`: `module = ["asyncpg", "asyncpg.*", "uvicorn"]` mit
  `ignore_missing_imports = true`.
- `dependencies = []` bleibt unverändert.

## Doku
- `docs/KANBAN.md` (Deutsch):
  - Überblick und Architekturbild (ASCII): Layer 1 Apollo/Telegram/Obsidian, Layer 2
    Dispatcher/Reaper/Bus/Store, Layer 3 Docker-Sandbox/Rust-Limbs.
  - Zustandsmaschine und Übergangstabelle.
  - Alle `NIO_KANBAN_*`-Variablen aus `config.py` als Tabelle mit Defaults.
  - Backends wählen (SQLite/Postgres, Memory/Redis, Subprozess/Docker).
  - Sicherheitsmodell: Task-Token-Scopes, Secret-Injektion ohne argv, Container-Härtung,
    append-only Ledger plus Hash-Kette, "kein Push/PR durch Worker".
  - SOUL.md-Format, Vault-Struktur, API-Routen, CLI-Befehle.
  - Betriebsrezepte: Crash-Recovery, Breaker zurücksetzen per
    `task transition ID ready`, `audit verify`.
- `docs/INDEX.md`: Eintrag auf `KANBAN.md`.
- `CHANGELOG.md` unter `[Unreleased]` → `### Hinzugefügt`: ein Eintrag im Stil der
  vorhandenen Einträge (Module, Tests, Anzahl neuer Tests).

## Ende-zu-Ende-Abnahme (Stdlib-Default)
In einem Temp-Verzeichnis `NEU_ROOT=$tmp NIO_KANBAN_WORKSPACE=$tmp/ws NIO_OBSIDIAN_VAULT=$tmp/vault`:
```bash
python3 -m orchestrator kanban init
python3 -m orchestrator kanban worker create alpha --skill code
python3 -m orchestrator --json kanban board create demo
python3 -m orchestrator kanban task create --board <id> --title "Demo" --description $'- [ ] eins #code\n- [ ] zwei #code'
for i in 1 2 3 4; do python3 -m orchestrator kanban tick --wait; done
python3 -m orchestrator kanban audit verify
```
Erwartet:
- Der Eltern-Task und zwei Kinder sind `completed`.
- `$tmp/vault/workers/alpha/experiences/` enthält zwei Notizen.
- `audit verify` meldet ok.

Als Skript `scripts/ci_e2e_kanban.py` ablegen (Muster: `scripts/ci_e2e_unlimited.py`)
und als Makefile-Ziel `e2e-kanban`. Nicht in `check` aufnehmen.

## Volles Tor
`make check` muss grün sein, bis auf den bekannten, vorbestehenden mypy-Fehler in
`orchestrator/runner.py:2011`, falls er noch existiert. Den nicht fixen, nur melden.
