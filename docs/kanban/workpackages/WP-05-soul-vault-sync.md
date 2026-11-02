# WP-05: `SOUL.md`, Obsidian-Vault-Spiegel, Host-seitiger `sync_back`

Lies zuerst `00-README.md`. Du lieferst `sync_back` und `RunOutcome` exakt nach Signatur
und liest den Dateivertrag `out/` (siehe dort).

## `orchestrator/kanban/soul.py`
- `@dataclass Soul`: `frontmatter: dict[str, str]`, `identity`, `mission`,
  `core_skills: list[str]`, `rules: list[str]`, `heartbeat`, `extra: str` (unbekannte
  Abschnitte bleiben wörtlich erhalten).
- `parse_soul(text) -> Soul` und `render_soul(soul) -> str`.
  - Frontmatter zwischen `---`-Zeilen mit `key: value`.
  - Abschnitte `## Identity`, `## Mission`, `## Core Skills` (Bullets), `## Rules / Constraints` (Bullets), `## Heartbeat`.
  - OpenClaw-Konvention, siehe `manduks/openclaw-soul-md-best-practices`.
  - Roundtrip: `render_soul(parse_soul(x)) == x` für alles, was `render_soul` erzeugt hat.
- `default_soul(uid, name, skills, mission="") -> str`: Frontmatter `uid`, `name`,
  `skills` (CSV), `runtime: noop`, dazu sinnvolle Default-Regeln, unter anderem
  "never push", "never print secrets" und "report heartbeat".
- `merge_skills(soul_text, skills_delta) -> str`: neue Skills ohne Duplikate an
  `Core Skills` und an das Frontmatter `skills` anhängen.

## `orchestrator/kanban/vault.py`
`ObsidianVault(root: Path)` (Default `config.vault_dir` = `workspace/obsidian`). Alle
Schreibzugriffe laufen über `core.atomic.atomic_write_bytes(..., fsync=True)`.

| Notiz | Inhalt |
|---|---|
| `workers/{uid}/SOUL.md` | Spiegel der Seele (`mirror_soul(uid, soul_md)`) |
| `workers/{uid}/history.md` | Lebensprotokoll, `append_history(uid, line)`: lesen, Zeile anhängen, atomar zurückschreiben. Zeilenformat `- {ts} [[task-{id}]] {outcome}: {summary}` |
| `workers/{uid}/experiences/{YYYY-MM-DD}-{task_id}.md` | `write_experience(exp, task)`: YAML-Frontmatter (`uid`, `task`, `outcome`, `created`, `tags: [experience, academy]`), Abschnitte Summary, Lessons, Skills gained, Links `[[{uid}]]` und `[[task-{task_id}]]` |
| `workers/{uid}/{uid}.md` | Worker-Index-Notiz, die auf SOUL, history und experiences verlinkt (Graph-Knoten) |
| `tasks/task-{id}.md` | `write_task(task)`: Status, Eltern-Link `[[task-{parent}]]`, Abhängigkeits-Links, Worker-Link |

- UIDs und Task-IDs vor der Pfadbildung gegen `UID_PATTERN` bzw. `^t-[0-9a-f]{12}$|^[a-z0-9-]{3,64}$`
  prüfen. Keine Pfad-Traversal-Möglichkeit.
- Der Arbeitsbereich `config.workspace_dir/workers/{uid}/` (`SOUL.md`, `history.md`)
  bekommt dieselben atomaren Schreibvorgänge: `WorkerHome(workspace_dir)` mit
  `write_soul` und `append_history`.

## `orchestrator/kanban/sync.py`
`async sync_back(*, store, vault, workspace_dir, task, worker, result: SandboxResult) -> RunOutcome`:
1. `out/result.json` lesen. Fehlt die Datei oder ist sie ungültig, gilt
   `status="failed"`, `reason="no result (exit {code})"`.
   Bei `result.timed_out` gilt `failed`/`"deadline exceeded"`. Ein Exit ≠ 0 ist immer
   `failed`, auch wenn `result.json` etwas anderes sagt.
2. `out/experience.json` lesen. Fehlt sie, eine minimale Experience bauen
   (`summary=f"{task.title}: {status}"`, `outcome=status`).
3. `out/SOUL.md` lesen, falls vorhanden; Größenlimit 256 KiB, sonst ignorieren.
4. **Eine DB-Transaktion**: `store.finish_run(task_id=…, expected=None, task_changes={}, worker_uid=uid, worker_changes={"soul_md": neu} if neu else {}, experience=exp, audit=AuditDraft(actor=f"worker:{uid}", action="worker.experience", category="worker", subject=task.id, payload={"outcome": …}))`.
   Den Task-Status setzt **nicht** `sync_back`, sondern der Dispatcher (WP-03).
5. Danach den Vault spiegeln: `mirror_soul`, `append_history`, `write_experience` und
   `write_task`, plus `WorkerHome`. Bei Erfolg `store.mark_vault_synced(exp.id)`.
   Bei `OSError` nur loggen; der Reaper versucht es später erneut, weil
   `vault_synced=0` bleibt.
6. `RunOutcome` zurückgeben.

## Tests: `tests/test_kanban_soul_vault.py`
- Parse/Render-Roundtrip. `merge_skills` erzeugt keine Duplikate. Unbekannte Abschnitte
  bleiben erhalten.
- Vault: Notizen werden erzeugt, Links stehen drin, `history.md` wächst mit zwei Aufrufen
  um zwei Zeilen, kein `.tmp` bleibt übrig. Eine UID `../x` wird abgelehnt.
- `sync_back` mit einem handgebauten `out/` in einem Temp-Verzeichnis und
  `SqliteKanbanStore(":memory:")`:
  - Experience in der DB, `soul_md` aktualisiert, Audit-Eintrag vorhanden, Vault-Dateien da.
  - Ohne `result.json` ergibt sich `failed`.
  - Ein schreibgeschütztes Vault-Verzeichnis ergibt eine Experience mit `vault_synced == False`.

## Fertig, wenn
Die Abnahme ist grün.
