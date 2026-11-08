# Audit: Self-Modification Readiness (NEU / „Neo“)

- **Datum:** 2026-11-08
- **Branch:** `arena/20a81b7a-nio` (Basis: `2d18eeb`)
- **Art:** Read-only-Audit. Am Quellcode wurde nichts geändert. Die Experimente liefen in Kopien unter `/tmp`, die danach gelöscht wurden.
- **Maschinenlesbare Befundliste:** `findings.json` (gleiche IDs wie hier)
- **Belege:** `evidence/` (Rohausgaben von Befehlen und Testläufen)

---

## 1. Zusammenfassung

Neo kann Dateien im eigenen Repo lesen und schreiben. Die Policy schützt den Orchestrator-Kern sauber durch einen menschlichen Freigabeprozess. Eine geschlossene Selbstmodifikationsschleife gibt es aber nicht. Sie bricht an vier Stellen:

1. **Keine Verifikation.** Geänderter Code wird nie ausgeführt, bevor er wirksam wird (SC-05).
2. **Kein Rollback.** Es gibt keinen Git-Revert und keinen Known-Good-Stand (HR-07).
3. **Keine Übernahme.** Kanban-Ergebnisse landen auf einem Branch und werden nirgends gemerged (HR-10, SC-08).
4. **Keine Sprachbrücke zum Kern.** Voice erreicht nur den Vault (Inbox), nicht den Orchestrator (NO-01, NO-02).

Zusätzlich gilt: Ein Syntaxfehler im Orchestrator-Kern macht den nächsten Start unbrauchbar (HR-03). Die Diagnose verweist dabei auf eine falsche Maßnahme (HR-04).

### Befundübersicht

| Schwere | Anzahl | IDs |
|---|---|---|
| critical | 3 | SC-05, HR-03, HR-07 |
| high | 7 | SC-03, SC-08, HR-01, HR-08, HR-10, NO-01, NO-03, NO-07 |
| medium | 9 | SC-06, SC-09, HR-04, HR-05, HR-09, NO-04, NO-05, BL-01, BL-02 |
| low | 3 | SC-04, HR-06, NO-06 |
| info | 7 | SC-01, SC-02, SC-07, HR-02, NO-02, BL-03, BL-04 |

*(Summe: 30 Befunde, identisch mit den Einträgen in `findings.json`.)*

---

## 2. Methodik

1. **Konfiguration und Policy lesen:** `neu.config.json`, `core/policy.py`, `protocol/operations.json`, `limbs/registry.json`.
2. **Schreib-, Lese- und Git-Pfade verfolgen:** Bootstrap-Limb, Kanban-Dispatcher und Worker, Architect-Sicherheitsklasse.
3. **Voice-Kette verfolgen:** Frontend (`commands.ts`, `store.ts`, `client.ts`, API-Routen) bis zum Orchestrator.
4. **Tests ausführen:** `make test-core`, Unittest-Lauf für Core und Architect, `py_compile` für alle Kernmodule.
5. **Experimente:** Syntaxfehler in Kopien einbauen und das Verhalten beobachten (HR-02, HR-03, HR-04).
6. **Behauptungen gegenprüfen:** Jede Aussage aus der Erstanalyse wurde mit einem Befehl nachgeprüft (`evidence/18_claim_checks.txt`). Dabei wurden zwei Korrekturen fällig (Abschnitt 6).

---

## 3. Befunde nach Bereich

### 3.1 Self-Coding Readiness (Git / Dateisystem)

#### SC-01 · info · verifiziert · Repo-Schreibzugriff vorhanden
`core/policy.py` erlaubt `sandbox_root "."` und `elevation.level = "repo_write"`. Jeder Schreibpfad wird gegen vier Regeln geprüft: `allowed_repo_globs`, `denied_globs`, `human_only_globs` und `requested_paths`.
*Beleg:* `evidence/01_config_policy.txt`, `evidence/02_policy_code.txt`

#### SC-02 · info · verifiziert · Constitution Guard schützt den Kern
Human-only sind: `core/policy.py`, `core/config.py`, `core/kernel.py`, `orchestrator/runner.py`, `orchestrator/planner.py`, `limbs/registry.json`, `protocol/operations.json`, `neu.config.json`, `.git/*`, `.github/*`. Freigabe nur mit `approved_by=human` und Ticket.
*Beleg:* `evidence/01_config_policy.txt`

#### SC-03 · high · verifiziert · Tests, Prompts und Workspace sind selbst schreibbar
`tests/*`, `prompts/*` (außer `prompts/core/kernel_system.md`) und `workspace/*` sind freigegeben. Ein Agent könnte Tests so anpassen, dass sie grün werden (Goodhart / Reward Hacking). Er könnte auch Rollen-Prompts umschreiben.
**Empfehlung:** Kern-Tests und Rollen-Prompts in `human_only_globs` aufnehmen oder per Hash sperren.
*Beleg:* `evidence/01_config_policy.txt`, `evidence/13_selfmod_vectors.txt`

#### SC-04 · low · verifiziert · Frontend, Architect, rust, scripts liegen außerhalb
Neo kann das Voice-Frontend und das Architect-Teilprojekt nicht ändern. Ob das gewollt ist, ist nicht dokumentiert.
**Offen:** Soll Neo das Frontend langfristig ändern dürfen?

#### SC-05 · **critical** · verifiziert · Kein Verifikationsschritt
- `allow_test_ops: false`, `allow_shell_ops: false`.
- `test.run` und `shell.exec` haben Policy-Gates (`core/policy.py` Zeilen 335, 341, 440, 446), aber **keinen Handler**. Die Suche nach Handlern in `limbs/` ist negativ.

Konsequenz: Geänderter Code wird nie geprüft, bevor er wirksam wird.
**Empfehlung:** Isoliertes `sandbox_gate`-Skript (Compile, Unittest, Smoke-Test) als Pflicht-Gate.
*Beleg:* `evidence/01`, `evidence/02`, `evidence/04`, `evidence/18`

#### SC-06 · medium · verifiziert · Architektur-Lesen nur auf Datei-Ebene
Verfügbar: `fs.read_file` (max. 1 MB) und `fs.list` (max. 500 Einträge). Fehlend: Repo-Index, Import-/Symbolgraph, Werkzeug für `git log` und `git diff`. Der Zugriff läuft nur über handgeschriebene Intent-JSONs.
*Beleg:* `evidence/03_bootstrap_limb.txt`, `evidence/04_registry_operations.txt`

#### SC-07 · info · verifiziert · Schreibpfad des Bootstrap-Limbs ist solide
Atomares Schreiben, `expect_sha256` als Optimistic-Lock, Backup bei `constraints.backup`, Hash-Nachweis je Artefakt, `dry_run`-Modus.
*Beleg:* `evidence/03_bootstrap_limb.txt`

#### SC-08 · high · verifiziert · Git ist im Kern nicht angebunden
Kein Commit-, Revert-, Tag- oder Branch-Mechanismus im Kern. Git taucht nur an drei Stellen auf:
- `orchestrator/kanban/dispatcher.py`: Worktrees
- `limbs/rea_limb.py`: Clone
- `limbs/vault_limb.py`: eigenes Vault-Git

*Beleg:* `evidence/05_kanban_worktree.txt`, `evidence/18_claim_checks.txt`

#### SC-09 · medium · offen · Kanban-Runtime `opencode` ohne Verifikation
`worker_entry.py` fordert „committe sie“ und führt `opencode run` im Worktree aus. Im Repo gibt es keine `user.name` / `user.email`-Konfiguration für Worker. Ob das Sandbox-Image `opencode` enthält, ist nicht belegt (kein Treffer in `docker/` oder `kanban/config.py`).
*Beleg:* `evidence/06_kanban_opencode_runtime.txt`, `evidence/18_claim_checks.txt`

---

### 3.2 Hot-Reloading und Absturz-Risiko

#### HR-01 · high · verifiziert · Kein Watchdog, kein Hot-Reload, kein Restart-Supervisor
Die Suche nach `importlib.reload`, `watchdog`, `inotify`, `watchfiles`, `os.execv` und `sys.modules` ergab im Kern keinen Selbst-Neustart. Der Kern läuft als CLI-Prozess pro Auftrag oder als Kanban-Dienst ohne Überwachung.
*Beleg:* `evidence/08_limb_spawn.txt`, `evidence/09_limb_ffi_usage.txt`

#### HR-02 · info · verifiziert · Limbs sind isolierte Subprozesse
**Experiment 19b:** Syntaxfehler in `limbs/echo_limb.py`. Der Orchestrator bleibt lauffähig (`orchestrator status` → Exit 0). Der Auftrag endet mit `E_LIMB_CRASH`.
*Beleg:* `evidence/19b_limb_experiment.txt`, `evidence/08_limb_spawn.txt`

#### HR-03 · **critical** · verifiziert · Kaputter Kern-Code macht den nächsten Start unbrauchbar
**Experiment 19, Abschnitte A und C:**
- Syntaxfehler in `orchestrator/cli.py` → `python3 -m orchestrator status` endet mit Exit 1.
- Syntaxfehler in `core/config.py` → dasselbe.

Da der Kern beim Start geladen wird, gibt es keinen Fallback. Die Reparatur ist nur durch einen Menschen möglich, weil die Kern-Dateien `human_only` sind.
*Beleg:* `evidence/19_hot_reload_experiment.txt`
*Hinweis:* Abschnitt B derselben Datei ist ungültig (Setup-Artefakt, ein aktiver Job aus dem kopierten `runtime/` blockierte den Lauf). Gültig sind 19b und 19c.

#### HR-04 · medium · verifiziert · Fehlerdiagnose nennt die falsche Maßnahme
**Experiment 19c:** Die Konsole zeigt nur `E_LIMB_CRASH` und „Massnahme: Umfang halbieren“. Der eigentliche `SyntaxError` steht nur im Archiv unter `runtime/archive/.../result.json` (stderr). Die vorgeschlagene Maßnahme hilft bei einem Code-Fehler nicht. Der Diagnosepfad (`param_patch`, `timer_patch`) wiederholt zudem den kaputten Code.
**Empfehlung:** Letzte Zeilen von stderr in die Konsolendiagnose aufnehmen. Bei `SyntaxError` oder `ImportError` eine Code-Reparatur vorschlagen.
*Beleg:* `evidence/19c_limb_error_visibility.txt`

#### HR-05 · medium · verifiziert · Kanban-Dienst hat keine Reload-Logik
`orchestrator/kanban/cli.py` startet `asyncio.run(_main)`. Codeänderungen wirken erst nach manuellem Neustart.
*Beleg:* `evidence/09_limb_ffi_usage.txt`

#### HR-06 · low · verifiziert · Rust-.so-Hot-Reload ist nicht verdrahtet
`orchestrator/kanban/limb_ffi.py` implementiert atomaren Tausch mit `dlclose` und Schreibsperre. Nur `tests/test_limb_ffi.py` importiert es.
*Beleg:* `evidence/09_limb_ffi_usage.txt`

---

### 3.3 Rollback

#### HR-07 · **critical** · verifiziert · Kein Git-Revert, kein Known-Good-Stand
Es gibt keine Tags, kein Revert und kein Reset für Code-Änderungen. Das einzige Rollback ist das Bootstrap-Backup. Es betrifft eine einzelne Datei, wird nur bei `constraints.backup` angelegt und nie automatisch ausgelöst.
*Beleg:* `evidence/03_bootstrap_limb.txt`, `evidence/05_kanban_worktree.txt`, `evidence/18_claim_checks.txt`

#### HR-08 · high · verifiziert · Architect-Sicherheitsklasse schreibt keinen Inhalt
`Architect/core/self_modification_safety.py:apply_modification` schreibt nur Backups und prüft Hashes. Der Code selbst markiert die Lücke: „In a full implementation, the actual content patch would be applied here.“ Die Klasse gehört zum Architect-Teilprojekt und ist nicht mit dem Kern verdrahtet.
*Beleg:* `evidence/07_architect_safety.txt`

#### HR-09 · medium · verifiziert · Backup-Zuordnung nur über den Dateinamen
`rollback` sucht Backups per `glob(f"{file_path.name}_*.bak")` und nimmt den sortiert letzten. Gleichnamige Dateien aus verschiedenen Verzeichnissen teilen sich denselben Namensraum. Der Zeitstempel hat Sekundenauflösung.
*Beleg:* `evidence/07_architect_safety.txt`

#### HR-10 · high · verifiziert · Kanban-Worktree wird ohne Merge oder Test entfernt
`dispatcher.py` entfernt den Worktree mit `git worktree remove --force`. Der Commit bleibt nur als Branch `kanban/<run_id>` erhalten. Kein Schritt prüft, testet oder übernimmt diesen Branch.
*Beleg:* `evidence/05_kanban_worktree.txt`

---

### 3.4 Die Kette: Voice → Agent → Code → Memory → Anwenden

| Glied | Status | Befund | Befund-ID |
|---|---|---|---|
| Voice → Intent | ❌ | `/spawn`, `/dispatch` wirken auf den UI-Graphen, nicht auf NEU | NO-01 |
| Voice → Memory | ✅ | `/note` → Vault-Inbox | NO-02 |
| Dauerbetrieb | ❌ | `loop --watch` nicht implementiert | NO-03 |
| Agent schreibt Code | ⚠️ | Bootstrap (handgeschrieben) und Kanban `opencode` (ungeprüft) | SC-09 |
| Verifikation | ❌ | Kein Test-Gate | SC-05 |
| Merge / Anwenden | ❌ | Kanban-Branch wird nicht übernommen | HR-10 |
| Rollback | ❌ | Kein Git-Revert | HR-07 |
| Neustart | ❌ | Kein Supervisor | HR-01 |
| Memory automatisch | ❌ | `vault.capture` nur manuell aufgerufen | NO-05 |
| `core.memory_write` | ❌ | definiert, ohne Implementierung | NO-04 |
| Code-Gen-Limb | ❌ | `openmanus` nur geplant | NO-06 |

#### NO-01 · high · Voice erreicht den Orchestrator nicht
`frontend/src/apollo/commands.ts`: `/spawn` und `/dispatch` arbeiten am Node-Graphen der Apollo-UI. Es gibt keine Abbildung Sprache → Intent-JSON.
*Beleg:* `evidence/11_voice_frontend.txt`

#### NO-02 · info · verifiziert · Voice-Notiz → Vault ist verdrahtet
Kette: `commands.ts` (`/note`) → `store.ts:720` (`callVault`, capture) → `/api/apollo/vault` → `route.ts:71-74` (`vault.capture`) → Orchestrator. Schreibt nur nach `Inbox/`, `workers/`, `tasks/`. Kein Schreibzugriff auf Code.
*Beleg:* `evidence/11_voice_frontend.txt`, `evidence/18_claim_checks.txt`

#### NO-03 · high · Dauerbetrieb fehlt
`orchestrator/cli.py:cmd_loop` gibt bei `--watch` aus: „Dauerbetrieb folgt in Phase 4“. Nur `loop --once` existiert.
*Beleg:* `evidence/10_loop_watch.txt`

#### NO-04 · medium · `core.memory_write` ohne Implementierung
In `protocol/operations.json` definiert (Phase 4, risk=write). Kein Limb in `registry.json` bietet es an, kein Handler existiert.
*Beleg:* `evidence/04`, `evidence/12`, `evidence/18`

#### NO-05 · medium · Kein automatischer Memory-Schreibvorgang
`vault.capture` wird nur von der Voice-Notiz und `scripts/vault_mcp.py` aufgerufen. Der Orchestrator schreibt Ergebnisse, Diffs oder Fehler nicht selbst in den Vault.
*Beleg:* `evidence/12_memory.txt`, `evidence/18_claim_checks.txt`

#### NO-06 · low · `openmanus` nur geplant
`registry.json`: `status=planned`, Phase 6.
*Beleg:* `evidence/04_registry_operations.txt`

#### NO-07 · high · Freigabe-Route aus dem Frontend erreichbar
`frontend/src/apollo/proxy.ts:115-117`: `POST /api/v1/approvals/issue` ist in der Secure-Allowlist. Nicht geprüft wurde, ob diese Route durch Sprache auslösbar ist. Eine Sprachfreigabe für `human_only`-Pfade muss ausgeschlossen werden.
**Offen:** Ist die Route an eine bewusste menschliche Bestätigung gebunden (z. B. Tippen statt Sprache)?

---

### 3.5 Testbasis

#### BL-01 · medium · verifiziert · `make test-core`: 662 Tests, 1 Importfehler, 20 Skips
Der Importfehler `tests.test_ciel_mcp_nodes` kommt vom fehlenden Paket `mcp`. Das ist ein Umgebungsproblem, kein Codefehler. In dieser Sandbox ist das Gate trotzdem nicht reproduzierbar grün.
*Beleg:* `evidence/14_make_test_core.log`, `evidence/15_core_unittest_full.log`

#### BL-02 · medium · verifiziert · Architect-Suite: 218 Tests, 2 Fehler
`test_genai_client`: fehlendes Paket `google`. `test_telemetry_feed`: fehlendes Paket `numpy`. Umgebungsproblem.
*Beleg:* `evidence/16_architect_unittest.log`

#### BL-03 · info · verifiziert · Alle Kernmodule kompilieren
`py_compile` für `orchestrator/`, `core/`, `limbs/` ohne Fehler.
*Beleg:* `evidence/17_py_compile.txt`

#### BL-04 · info · Korrektur zur Erstanalyse
Die Erstanalyse nannte die Testbasis „rot“. Belegt ist: Die Fehler stammen aus fehlenden Paketen in der Sandbox. Die Aussage „Gate nicht grün“ gilt nur für diese Umgebung. Die Pakete müssen installiert werden, bevor der Code bewertet werden kann.

---

## 4. Experimente

| ID | Eingriff | Ergebnis | Beleg |
|---|---|---|---|
| A | Syntaxfehler in `orchestrator/cli.py` | `status` → Exit 1, Traceback | 19 |
| B | Syntaxfehler in `limbs/echo_limb.py` (erster Versuch) | ungültig: aktiver Job aus kopiertem `runtime/` | 19 |
| B' | Syntaxfehler in `limbs/echo_limb.py` (frische Laufzeit) | Job `failed`, Exit 2, `E_LIMB_CRASH`; Orchestrator danach Exit 0 | 19b |
| C | Syntaxfehler in `core/config.py` | `status` → Exit 1 | 19 |
| D | Konsolendiagnose bei B' | `SyntaxError` nicht sichtbar, Maßnahme „Umfang halbieren“ | 19c |

Alle Experimente liefen in Kopien ohne `.git`, `node_modules`, `frontend` und `runtime`. Die Kopien wurden danach gelöscht.

---

## 5. Empfohlene Reihenfolge

1. **Basis herstellen:** fehlende Pakete installieren (`mcp`, `pytest`, `google-genai`, `numpy`) und die Testbasis neu messen (BL-01, BL-02).
2. **Verifikation:** `sandbox_gate` als eigenes Skript außerhalb des Schreibbereichs (SC-05). Ohne dieses Gate ist keine weitere Automatisierung sinnvoll.
3. **Rollback:** Known-Good-Tag und Revert-Pfad (HR-07, SC-08), vor jeder Übernahme.
4. **Übernahme:** Kanban-Branch prüfen, testen und nur per `--ff-only` mergen (HR-10).
5. **Schutzlücken schließen:** `tests/*` und Rollen-Prompts sperren (SC-03). Freigabe-Route gegen Sprache absichern (NO-07).
6. **Diagnose:** stderr-Auszug in die Konsole, Code-Fehler nicht als „Umfang halbieren“ melden (HR-04).
7. **Schleife schließen:** Voice → Intent (NO-01), Dauerbetrieb (NO-03), automatischer Vault-Eintrag nach jedem Zyklus (NO-05).

---

## 6. Korrekturen zur Erstanalyse

1. **Testbasis:** Die Erstanalyse nannte sie „rot“. Richtig ist: Die Fehler stammen aus fehlenden Paketen (BL-04).
2. **Voice-Kette:** Die Erstanalyse sagte, es gebe keine Brücke von Voice zum System. Richtig ist: Voice → Vault (`/note`) ist verdrahtet. Nur die Brücke zu NEU-Intents fehlt (NO-02).
3. **Ausführung:** Die Erstanalyse nannte Testausführung „fehlend“. Richtig ist: Die Policy-Gates existieren, aber die Handler fehlen (SC-05).

---

## 7. Offene Fragen

- SC-04: Soll Neo das Frontend/Voice-Interface selbst ändern dürfen?
- SC-09: Existiert das Sandbox-Image mit `opencode`, und welche Git-Identität landet im Commit?
- NO-07: Ist `approvals/issue` gegen Sprachauslösung abgesichert?
- Wie gelangen Ergebnisse von Kanban-Tasks in den NEU-Kern oder in den Vault?

---

## 8. Belegverzeichnis

| Datei | Inhalt |
|---|---|
| `evidence/01_config_policy.txt` | Policy-Globs aus `neu.config.json` |
| `evidence/02_policy_code.txt` | Relevante Stellen in `core/policy.py` |
| `evidence/03_bootstrap_limb.txt` | Operationen und Schreibpfad des Bootstrap-Limbs |
| `evidence/04_registry_operations.txt` | Limb-Status und Operationsregister |
| `evidence/05_kanban_worktree.txt` | Worktree-Lebenszyklus im Dispatcher |
| `evidence/06_kanban_opencode_runtime.txt` | `opencode`-Runtime im Worker |
| `evidence/07_architect_safety.txt` | Architect-Sicherheitsklasse |
| `evidence/08_limb_spawn.txt` | Subprozess-Start der Limbs |
| `evidence/09_limb_ffi_usage.txt` | FFI-Hot-Reload und Kanban-Dienst |
| `evidence/10_loop_watch.txt` | `loop --watch` Status |
| `evidence/11_voice_frontend.txt` | Voice-Befehle und Vault-Route |
| `evidence/12_memory.txt` | Vault-Limb und Memory-Stellen |
| `evidence/13_selfmod_vectors.txt` | Schreibbare Vektoren (tests, prompts, workspace) |
| `evidence/14_make_test_core.log` | Testlauf `make test-core` |
| `evidence/15_core_unittest_full.log` | Vollständiger Core-Unittest-Lauf |
| `evidence/16_architect_unittest.log` | Architect-Unittest-Lauf |
| `evidence/17_py_compile.txt` | Kompilierprüfung |
| `evidence/18_claim_checks.txt` | Gegenprüfung der Behauptungen |
| `evidence/19_hot_reload_experiment.txt` | Experimente A und C (B ungültig) |
| `evidence/19b_limb_experiment.txt` | Experiment B' (gültig) |
| `evidence/19c_limb_error_visibility.txt` | Experiment D: Diagnose-Sichtbarkeit |

---

## 9. Grenzen dieses Audits

- Die Testläufe zeigen den Zustand dieser Sandbox. Mit vollständigen Paketen können Ergebnisse abweichen.
- Das Verhalten des Sandbox-Images für Kanban-Worker habe ich nicht ausgeführt.
- Der Architect-Teil wurde nur auf Code-Ebene geprüft, nicht im Betrieb.
- Die Experimente testen Syntaxfehler. Logik- und Laufzeitfehler (z. B. falsche Ergebnisse bei gültiger Syntax) habe ich nicht geprüft.
