# Refinement-Vault — asynchrone Heilung geparkter Rust-Limbs

Modifizierte Limbs landen **nicht** direkt in der produktiven Baseline. Sie werden im
Refinement-Vault geparkt, dem Menschen über Apollo zur Freigabe gezeigt — oder zur
Heilung abgelehnt — und dann von einem Hintergrund-Daemon Schritt für Schritt
repariert, bis sie sauber erneut zur Freigabe vorliegen. Der Mensch behält die
letzte Entscheidung (Human-in-the-Loop), das System arbeitet den Vault im
Hintergrund eigenständig leer.

> Abgrenzung: Das ist **nicht** der Obsidian-Vault (`docs/VAULT.md`, Notizen).
> Der Refinement-Vault hält ausführbare Limb-Artefakte (`.so`, `.rs`, …) samt
> FSM-Metadaten unter `runtime/refinement-vault/`.

## Zustands-FSM

Jeder Eintrag ist ein Verzeichnis mit Artefakt und `meta.json` daneben
(Schema: `schemas/refinement-vault.schema.json`, `schema_version: 1`):

```
runtime/refinement-vault/<limb_id>/
├── meta.json                  # FSM-Zustand, Historie (≤200), Lease, letzter Fehler
├── artifact/<dateiname>       # aktueller Patch-Candidate
└── versions/v0001/<dateiname> # unveränderliche Schnappschüsse je Version
```

| Zustand | Bedeutung | Erlaubte Folgezustände |
|---|---|---|
| `parked_pending_user` | Im Staging geparkt, wartet auf die initiale Entscheidung (Apollo) | `refinement_queued`, `promoted`, `quarantined` |
| `refinement_queued` | Abgelehnt / fehlerhaft, wartet auf den nächsten Heilungslauf (Backoff beachten) | `healing_in_progress`, `quarantined` |
| `healing_in_progress` | Ein Daemon testet/heilt in einer isolierten Sandbox (Lease läuft) | `ready_for_review`, `refinement_queued`, `quarantined` |
| `ready_for_review` | Alle Tests grün — wird dem Menschen erneut vorgestellt | `promoted`, `refinement_queued`, `quarantined` |
| `promoted` | Menschlich freigegeben (optional in die Baseline kopiert) — terminal | — |
| `quarantined` | `max_attempts` erschöpft oder final abgelehnt — terminal, nur Mensch holt zurück (`requeue`) | `refinement_queued` |

Illegale Übergänge wirft die FSM laut (`InvalidTransition`) statt sie zu raten,
z. B. `promoted → refinement_queued`. Nur `approved_by="human"` kann freigeben.

## Hintergrund-Heilung (Daemon)

`orchestrator/refinement_daemon.py`, ein Lauf bearbeitet den **ältesten**
fälligen Eintrag (FIFO):

1. **Claim** unter Lease (`.claim.lock` schützt nur den Metadaten-Übergang).
   Abgelaufene Leases abgestürzter Worker werden aufgeräumt und zählen als Versuch.
2. **Isolierte Test-Ausführung:** Candidate in ein frisches Temp-Verzeichnis,
   Subprozess mit geleertem Environment (keine Secrets), eigenem `HOME`/`TMPDIR`,
   hartem Timeout. Läufer: `CommandSandbox` (pro Eintrag hinterlegtes
   `test_command`, `{artifact}`-Platzhalter), `CargoTestSandbox` (`cargo test`),
   `FfiSmokeSandbox` (lädt eine `.so` in einem **Kindprozess** und prüft den
   FFI-Vertrag aus `orchestrator/kanban/limb_ffi.py` — nie im Daemon-Prozess).
3. **Ciel-Fehleranalyse:** Bei Rot bekommt der Healer-Hook
   `heal(entry, workdir, failure)` den Compiler-/Panic-Tail und darf **einen**
   kleinen Patch liefern (`CommandHealer`: externer Prozess, Patch unter
   `patched/<dateiname>`; Ciel/LLM wird hier verdrahtet). Der Patch wird als neue
   Version (`v0002`, …) übernommen und erneut getestet — höchstens
   `max_heal_steps_per_run` (Default 3) Schritte pro Lauf.
4. **Abschluss:** Grün → `ready_for_review` + Benachrichtigung. Rot →
   `refinement_queued` mit exponentiellem Backoff (`60s · 2^attempts`, ≤ 1 h)
   oder nach `max_attempts` Läufen (Default 5) → `quarantined`.

**Fehlerisolation:** Jeder Schritt fängt seine Ausnahmen selbst ab; ein kaputter
Limb, eine explodierende Sandbox oder ein abstürzendes Ciel blockiert weder den
Daemon noch andere Einträge. Ohne verdrahteten Healer läuft `NullHealer`:
Er erfindet keine Patches, Fehler wandern sichtbar Richtung Quarantäne.

**Benachrichtigung (Apollo):** FSM-Übergänge gehen als `refinement.*`-Events auf
den Event-Bus; die CLI-Daemon-Läufe schreiben zusätzlich
`runtime/refinement-vault/notifications.jsonl` (eine Zeile je
`ready_for_review`/`quarantined`), die Apollo pollen kann.

## Scheduler-Anbindung

Bewusst **kein `apscheduler`**: Der NEU-Stack ist Stdlib-only
(`pyproject.toml`, `dependencies = []`). Zwei gleichwertige Wege:

```bash
# A) asyncio-Loop im Daemon, nur nachts 02:00–05:00, alle 5 Minuten ein Eintrag
python3 -m orchestrator refinement daemon --interval 300 --active-start 02:00 --active-end 05:00

# B) Cron / systemd-Timer: ein Zyklus pro Aufruf, kein Dauerprozess
python3 -m orchestrator refinement run-once --max-items 1
# crontab:  */15 2-4 * * *  cd /pfad/zu/NIO && python3 -m orchestrator refinement run-once
```

`run_forever` führt die eigentliche Arbeit per `asyncio.to_thread` aus — ein
langer `cargo test` blockiert den Event-Loop nicht. Ein Instanz-Lock
(`.daemon.lock`, PID) verhindert zwei Daemons auf demselben Vault.

## Bedienung (Mensch / Apollo)

```bash
python3 -m orchestrator refinement park rust/nio-limb/target/release/libnio_limb.so \
    --limb-id nio-limb --test-command "cargo test --manifest-path rust/nio-limb/Cargo.toml"
python3 -m orchestrator refinement list [--state ready_for_review]
python3 -m orchestrator refinement show nio-limb          # inkl. letztem Fehler + Feedback
python3 -m orchestrator refinement reject nio-limb --feedback "Lifetime-Fehler im FFI-Block"
python3 -m orchestrator refinement approve nio-limb --promote-to rust/nio-limb/target/release/libnio_limb.so
python3 -m orchestrator refinement reject nio-limb --final   # Quarantäne
python3 -m orchestrator refinement requeue nio-limb          # aus Quarantäne zurück (Mensch)
```

`--json` liefert überall das `meta.json`-Dokument bzw. die Daemon-Reports.

## Ciel verdrahten

```python
from orchestrator.refinement import RefinementVault
from orchestrator.refinement_daemon import CommandSandbox, RefinementDaemon

vault = RefinementVault("runtime/refinement-vault", bus=apollo_event_bus)
daemon = RefinementDaemon(vault, sandbox=CommandSandbox(), healer=my_ciel_healer,
                          notify=apollo_notify)
daemon.run_cycle(max_items=1)          # ein Hintergrund-Zyklus
```

Ein Healer muss nur `heal(entry, workdir, failure) -> Path | None` erfüllen:
Fehler-Tail lesen, kleinen Patch als Datei zurückgeben (oder `None`).
