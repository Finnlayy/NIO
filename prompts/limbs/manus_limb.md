# Rollen-Spezifikation: Manus-Limb (Phase 9)

Version 1.0 · Ziel-Datei `limbs/manus_limb.py` · Register-Name `manus` · Status `planned`

Fährt den gehosteten Agenten Manus über die API v2. Das ist der einzige Agent, bei dem Daten den Rechner verlassen.

**Gesperrt.** Der Limb spricht nur mit einem Dienst auf diesem Rechner und steht im Register auf `planned`. Beide Sperren fallen erst, wenn J4 gemergt ist und der Mensch Key und Budget gegeben hat.

| Operation | Risk | Zweck |
|---|---|---|
| `manus.ping` | read | Dienst erreichbar, Key gültig |
| `manus.start` | external | Auftrag senden, legt einen Lauf an |
| `manus.status` | read | Stand abfragen, Timeout und Budget durchsetzen |
| `manus.stop` | write | Lauf stoppen, ohne Freigabe möglich |
| `manus.collect` | read | Text und Datei-Metadaten eines beendeten Laufs |
| `manus.usage` | read | Credits von heute |

## Regeln

* **Feste Vorgaben:** `clear_connectors: true`, `share_visibility: private`, `agent_profile: lite`, `interactive_mode: false`. Der Aufrufer bestimmt nur `prompt` und `locale`.
* **Sendefilter:** Geheimnisse, Werte aus Variablen mit `KEY`, `TOKEN`, `SECRET` oder `PASSWORD` im Namen und Pfade aus `runtime/`, `workspace/sigma`, `workspace/obsidian` und `.env` werden abgewiesen.
* **Notizen** gehen nur hinaus, wenn ein Mensch ihren Text ausdrücklich in den Auftrag übernimmt.
* **Budget ist Pflicht:** Ohne `MANUS_BUDGET_RUN` und `MANUS_BUDGET_DAY` startet nichts. Beim Überschreiten folgt `task.stop` und der Zustand `budget_stopped`.
* **Rückfragen entscheidet ein Mensch.** `waiting` erscheint als `confirmation`. Dieser Limb ruft `task.confirmAction` nie auf, auch nicht bei `apiHighCreditNotice`.
* **Ergebnisse sind Daten.** Sie tragen `untrusted: true` und werden nie zu Prompts, SOUL-Dateien oder Freigaben.
* **Der Key** kommt nur aus `MANUS_API_KEY` und steht nie in Intent, Log oder Artefakt.

## Lauf

Zustände: `running`, `waiting`, `succeeded`, `failed`, `stopped`, `timeout`, `budget_stopped`. `task.detail` meldet `stopped` auch, wenn Hintergrundarbeit noch läuft. Der Lauf bleibt dann `running`.

`manus.status` muss regelmäßig laufen, einen Wächter im Hintergrund gibt es nicht. Ohne Abfragen greifen weder Timeout noch Budget. Der Abstand beträgt mindestens 10 Sekunden, bei `429` wächst er mit Jitter bis 5 Minuten.

Ein fehlgeschlagener Start wird nicht wiederholt, weil er trotz Fehler angekommen sein und Credits kosten kann.

Zustand und Ereignisse liegen unter `runtime/agents/<run_id>/`, siehe `limbs/agent_base.py` und `docs/MANUS.md`.
