# Rollen-Spezifikation: Bootstrap-Limb (Phase 2)

Version 1.1 · Ziel-Datei `limbs/bootstrap_limb.py` · Register-Name `bootstrap`

Der Bootstrap-Limb ist der **erste echte Arm**: Er manipuliert Dateien und
liefert Nachweise. Er ist zugleich das Werkzeug, mit dem das System sich ab
Phase 3 selbst weiterentwickelt (Ouroboros).

---

## 1. Auftragsumfang

Zu implementieren (aus `protocol/operations.json`, Phase 2):

| Operation | Parameter | Verhalten |
|---|---|---|
| `fs.read_file` | `path`, `max_bytes?` | Inhalt, `sha256`, `bytes`; Artefakt `action="read"` |
| `fs.write_file` | `path`, `content`, `mode?` (`create`\|`overwrite`\|`append`), `expect_sha256?` | atomar schreiben; Backup bei vorhandener Datei; Artefakt `created`/`modified` |
| `fs.patch` | `path`, `patches[]` (`find`, `replace`, `count?`), `expect_sha256?` | alle Patches müssen treffen (all-or-nothing), sonst `E_PATCH_NO_MATCH` ohne Schreibaktion |
| `fs.list` | `path?`, `recursive?`, `max_entries?` | Einträge mit Typ und Größe |
| `fs.mkdir` | `path` | idempotent Verzeichnis anlegen |

**Nicht** in Phase 2: `fs.delete`, `shell.exec`, `test.run`, `core.memory_write`.
Sie bleiben im Register auf `phase: 4` und werden von der Policy blockiert.

---

## 2. Harte Regeln für den Limb

1. **Isolation.** Der Limb kennt nur den Intent. Keine Chat-Historie, keine
   anderen Aufträge, kein Raten über Absichten.
2. **Pfadprüfung ausschließlich über `ctx.resolve()`** (→
   `core/policy.py::Policy.resolve_path`). Niemals eigene Pfadlogik, niemals
   `open()` mit rohen Intent-Pfaden.
3. **Timer einhalten.** Der Handler setzt Checkpoints (`ctx.plan(...)`,
   `ctx.checkpoint(...)`, `ctx.finish_step(...)`), damit ein Statusbericht bei
   Ablauf substanziell ist. Die Basis-Laufzeit bricht bei der Soft-Deadline ab
   und meldet `status="timeout"`.
4. **Backup vor Überschreiben** (`ctx.backup(path)`), Pfad im Result als
   `artifacts[].backup_path` nachweisen.
5. **Atomar schreiben** (`ctx.write_atomic`) — keine halben Dateien.
6. **Hash-Nachweis** für jedes Artefakt (`ctx.record(path, action)`).
7. **stdout = genau ein JSON-Objekt.** Alles andere nach stderr.
8. **`dry_run`** respektieren: geplante Änderung berichten, nicht schreiben
   (`status="partial"` oder `success` mit `artifacts[].action="unchanged"`).
9. **Fehler fachlich melden** (`LimbError(code, message, hint)`) statt
   Ausnahmen durchzureichen — der Kern braucht Codes, keine Stacktraces.

---

## 3. Reihenfolge der Implementierung (Mikro-Schritte)

Jeder Schritt ist ein eigener Job mit Acceptance-Kriterien:

1. `fs.read_file` + `fs.list` (nur lesend, kein Rechtebedarf) → Register bleibt
   `planned`, Tests laufen gegen den Limb direkt.
2. `fs.mkdir` + `fs.write_file` **in die Sandbox** (`workspace/`) → Meilenstein
   Phase 2: „Der Kern lässt eine Datei anlegen."
3. `fs.write_file` mit `mode=overwrite/append`, Backup und `expect_sha256`.
4. `fs.patch` (all-or-nothing) — die Grundlage für Phase 3.
5. Register-Eintrag `bootstrap` auf `status="active"`, `version="1.0.0"`,
   `phase=2`; Operationen im Register als `implemented_by: ["bootstrap"]`
   bestätigen (stehen bereits so dort).
6. Testsuite erweitern: Sandbox-Grenze, Backup-Nachweis, Patch-No-Match,
   Hash-Drift, Timer-Ablauf bei großem Inhalt.

---

## 4. Abgrenzung zu Phase 3

Erst wenn Phase 2 grün ist, darf derselbe Limb mit
`elevation.level="repo_write"` am System selbst arbeiten. Der erste
Ouroboros-Auftrag ist in `docs/NEU.md` festgelegt: ein File-Sink für
`runtime/system.log`, angedockt an `NEU-PHASE-3-ANCHOR` in
`orchestrator/events.py::build_event_bus()`.
