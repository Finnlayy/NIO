# NIO als Agent-OS — Roadmap

Stand: `5e28298` (2026-11-12) · Referenz: Kortix CompanyOS `c910bb12` (v0.15.10)

NIO ist als vollständiger Harness gedacht, also als Betriebssystem für Agenten.
Diese Roadmap legt NIO neben eine produktive Referenz desselben Anspruchs
(Kortix CompanyOS, Open Source) und leitet daraus ab, was fehlt. Jede Ist-Aussage
trägt einen Beleg `datei:zeile`; die Aussagen über CompanyOS stammen aus dessen
README und Code-Stichproben, nicht aus einem Testlauf.

Nicht-Ziel: CompanyOS nachbauen. NIO bleibt lokal-first, ein Operator, Fail-Closed.
Übernommen werden Muster, nicht Infrastruktur (kein Platinum, kein Cloud-Zwang).

---

## 1. Das Leitbild: NIO als OS

| OS-Baustein | CompanyOS | NIO (belegt) | Stand |
|---|---|---|---|
| Shell | My Kortix: ein Ansprechpartner, routet Arbeit | Apollo-UI + Orchestrator (`orchestrator/runner.py:858` `dispatch`) | ✅ |
| Programme | pi-Agenten mit Prompt, Modell, Rechten | Limbs in `limbs/registry.json`, Basis `limbs/base.py:202` | ✅ |
| **Rechner** | eigener Cloud-Rechner pro Sitzung, schläft und wacht mit Verlauf | **Subagent-Rahmen**: eigene Sandbox `workspace/subagents/<id>/`, eigenes Werkzeug, Gedächtnis `.subagent/state.json`, eigene Uhr (`orchestrator/subagent.py:1-17`) | 🟡 nur für REA genutzt |
| Prozesse | Sitzungen | Jobs, Limb als Subprozess in eigener Gruppe (`orchestrator/runner.py:1118` `_spawn`) | ✅ |
| Scheduler & Interrupts | Zeitpläne, signierte Webhooks, App-Events, Filter im Code vor dem Modell | Job-relative Auslöser (`orchestrator/scheduler.py`), Telegram, Kanban-Dispatcher (`orchestrator/kanban/dispatcher.py:70` `tick`) | 🟡 kein Webhook-Eingang, keine Kalender-Zeitpläne |
| Rechte | Agent darf nicht mergen ohne Grant (CompanyOS `apps/api/src/projects/routes/change-request-actions.ts:80-87`) | Erhöhung nur mit `approved_by == "human"` + Ticket (`core/policy.py:138-176`), `env_allow` pro Limb | ✅ |
| Budget | LLM-Gateway mit Budgets | `core/budget.py` (Laufzeit, Token, Credits pro Lauf und Tag), genutzt nur in `limbs/agent_base.py:40` | 🟡 nicht zentral |
| Dateisystem / Gedächtnis | Drive, Markdown-Memory, Volltextsuche im Sitzungsprotokoll | Vault mit FTS5 (`limbs/vault_limb.py`), 40 Infografik-Notizen | 🟡 kein durchsuchbares Sitzungsprotokoll |
| Treiber | 3.000+ Apps, MCP, OpenAPI; Allow/Ask/Block pro Tool | Toolbox-Katalog, MCP in Kanban (`orchestrator/kanban/mcp_shim.py`) und Ciel (`apollo/ciel/mcp_nodes.py`), `orchestrator/secret_manager.py` | 🟡 wenige Anbindungen |
| Ziele | Outcome + getrennte Prüfer-Sitzung | Acceptance-Kriterien im Kern (`core/kernel.py:383`), aber nur lexikalische Abdeckung als Warnung | 🟡 kein unabhängiger Prüfer |
| Apps | Agenten hosten Apps unter fester URL | — | ❌ |
| Mehrbenutzer | SSO, Rollen, Audit | Audit-Ledger in Kanban (`orchestrator/kanban/audit.py`), sonst ein Operator | ⚪ bewusst später |

### Limbs als „Rechner“

Bei CompanyOS ist die Ausführungseinheit ein Rechner pro Sitzung. Die Entsprechung
in NIO ist **Limb + Subagent-Rahmen**:

- Ein **Limb** allein ist ein kurzlebiger Prozess: starten, Intent abarbeiten, beenden.
- Der **Subagent-Rahmen** macht daraus einen Rechner: eigener Wirkungsraum, eigene
  Installation, eigenes Gedächtnis, Lauf-Historie, wegwerfbar (`orchestrator/subagent.py:16-17`).
- Was zum CompanyOS-Rechner fehlt: der Rahmen gilt nur für REA, es gibt kein
  „Aufwachen mit Kontext“ für beliebige Limbs, und Isolation per Container ist in
  Kanban vorhanden (`orchestrator/kanban/sandbox.py`, `DockerSandbox`), aber nicht im
  Subagent-Rahmen.

---

## 2. Verhältnis zum Hermes-Plan

[`hermes/RUNTIME_PLAN.md`](hermes/RUNTIME_PLAN.md) (Phasen 0–5) bleibt gültig. Diese
Roadmap ordnet ihn ein und ergänzt, was er nicht abdeckt:

| Hermes-Phase | Hier |
|---|---|
| 0 Sicherheits-Hotfixes (Sigma-Approval-Gate, MCP-Prozessgruppen) | Voraussetzung **M0** |
| 1 Pre-Execution Policy Engine | Grundlage für Treiber-Rechte in **M6** |
| 2 DAG-Checkpointing + episodisches Gedächtnis | Kern von **M4** |
| 3 Cancellation, ExecutionEnv, Sub-Agenten | Kern von **M2** |
| 4 Control Plane | Eingang für **M3** |
| 5 Compaction, prozedurale Skills | Gegenstück zu **M4** (Suche statt Zusammenfassung) |

Hinweis: Der Hermes-Plan nennt „kein FTS5 im Repo“. Das ist überholt, der Vault-Limb
nutzt SQLite FTS5.

---

## 3. Meilensteine

Jeder Meilenstein hat ein prüfbares Abnahmekriterium. Er gilt erst als fertig, wenn
dieses Kriterium in einem Test oder einem dokumentierten Lauf belegt ist.

### M0 — Sicherheitsboden (Voraussetzung)

- **Ziel:** Kein Ausbau, solange kapitalrelevante Pfade offen sind.
- **Inhalt:** Hermes-Phase 0 abschließen; Status der Lücken aus `RUNTIME_PLAN.md`
  §1 „Bestätigte Lücken“ neu prüfen und hier eintragen.
- **Abnahme:** Jede dort genannte Lücke ist geschlossen oder ausdrücklich akzeptiert.
- **Blast-Radius:** 🔴 Trading. Live-Orders nur mit harten Limits und Not-Aus außerhalb der KI-Logik.

### M1 — Outcomes mit unabhängigem Prüfer

- **Ziel:** Ein Agent meldet „fertig“ nicht selbst. Eine getrennte Instanz prüft gegen die Definition of Done.
- **Ist:** `intent.task.acceptance` und `task.verification` existieren; fehlende Abdeckung
  erzeugt nur eine Warnung (`core/kernel.py:383-395`).
- **Bau:**
  1. Outcome als Kanban-Aufgabe mit Definition of Done (Liste prüfbarer Kriterien).
  2. Nach jedem Arbeitslauf startet ein Prüf-Job in einem eigenen, schreibgeschützten Subagenten.
  3. Status `done` nur, wenn der Prüfer jedes Kriterium mit Beleg bestätigt; sonst neuer Arbeitslauf.
  4. Prüfer und Arbeiter dürfen nicht derselbe Lauf sein.
- **Abnahme:** Test, in dem ein Arbeiter „fertig“ meldet, ein Kriterium aber nicht erfüllt ist, und die Aufgabe offen bleibt.
- **Abhängig von:** M0.

### M2 — Jeder Limb ein Rechner

- **Ziel:** Der Subagent-Rahmen gilt für alle Limbs, nicht nur für REA.
- **Ist:** `SubagentManager.ensure(agent_id, limb="rea")` (`orchestrator/subagent.py:234`); `limb` ist schon ein Feld.
- **Bau:**
  1. Rahmen für alle aktiven Limbs freischalten (Register-Feld, z. B. `stateful: true`).
  2. Schlafen = kein Prozess; Aufwachen = neuer Job mit `state.json` und Lauf-Historie als Kontext.
  3. Optional Container-Isolation über die vorhandene `DockerSandbox`.
- **Abnahme:** Zwei Läufe desselben Subagenten mit einem anderen Limb als REA; der zweite Lauf sieht Historie und Dateien des ersten, ein fremder Subagent sieht sie nicht.
- **Abhängig von:** Hermes-Phase 3.

### M3 — Ereignis-Eingang

- **Ziel:** Agenten starten ohne Operator an der Tastatur.
- **Ist:** Auslöser nur relativ zur Job-Uhr (`orchestrator/scheduler.py`); ein asyncio-Scheduler im Refinement-Daemon (`orchestrator/refinement_daemon.py:464`); Kanban-API mit Operator-Auth (`orchestrator/kanban/api.py`).
- **Bau:**
  1. Signierte Webhooks (HMAC) als Route in der Kanban-API.
  2. Kalender-Zeitpläne (Cron-Ausdruck) als Kanban-Aufgaben-Quelle.
  3. Filter im Code vor jedem Modellaufruf: Regel verwirft das Ereignis oder erzeugt eine Aufgabe.
- **Abnahme:** Unsignierter Webhook wird abgelehnt; signierter, aber vom Filter verworfener Webhook erzeugt keinen Modellaufruf (Budget-Zähler unverändert).
- **Abhängig von:** Hermes-Phase 4.

### M4 — Langer Horizont

- **Ziel:** Wird der Kontext voll, arbeitet der Agent in einem frischen weiter und sucht im vollständigen Protokoll, statt zusammenzufassen.
- **Bau:** Jede Sitzung schreibt ein Protokoll; FTS5-Index wie im Vault; Werkzeug „im eigenen Protokoll suchen“.
- **Abnahme:** Ein Detail aus dem ersten Kontext wird im dritten Kontext wörtlich gefunden.
- **Abhängig von:** Hermes-Phase 2, M2.

### M5 — Ein Budget für alle Modellaufrufe

- **Ziel:** Kein Modellaufruf am Budget vorbei.
- **Ist:** `BudgetTracker` nur in `limbs/agent_base.py:40`; weitere Aufrufer z. B. `frontend/src/server/providers.ts`, `orchestrator/kanban/worker_entry.py`.
- **Bau:** Ein lokales Gateway (oder eine Pflicht-Bibliothek), über das jeder Aufruf läuft; Tages- und Laufgrenzen aus `core/budget.py`.
- **Abnahme:** Test, der jeden bekannten Aufrufer gegen das Gateway prüft; Überschreitung bricht fail-closed ab.

### M6 — Treiber mit Rechten pro Werkzeug

- **Ziel:** Neue Anbindungen ohne neue Sicherheitslücken.
- **Bau:** Allow / Ask / Block pro Werkzeug im Toolbox-Katalog; Zugangsdaten nur serverseitig über `orchestrator/secret_manager.py`, nie im Limb-Prozess.
- **Abnahme:** Werkzeug auf „Ask“ erzeugt ein Freigabe-Ticket statt eines Aufrufs.
- **Abhängig von:** Hermes-Phase 1.

### Später

- **M7 Apps bauen und hosten:** lokal unter fester Adresse, mit Snapshot und Rollback.
- **M8 Mehrbenutzer:** Rollen und Rechte pro Ressource; nur falls NIO mehr als einen Operator bekommt.

---

## 4. Reihenfolge

```
M0 ──► M1 ──────────────┐
 │                      ▼
 ├──► (Hermes 3) ─► M2 ─► M4
 ├──► (Hermes 4) ─► M3
 ├──► M5               (unabhängig, früh sinnvoll)
 └──► (Hermes 1) ─► M6
```

M1 und M5 hängen von keinem anderen Meilenstein außer M0 ab und können parallel laufen.

## 5. Unverrückbar

- Fail-Closed vor Feature-Vollständigkeit.
- Neue Trading-Strategien zuerst im Paper-Modus; Live-Orders mit harten Limits und Not-Aus außerhalb der KI-Logik.
- Kein Meilenstein gilt als fertig ohne belegtes Abnahmekriterium.

## 6. Offene Entscheidungen

1. Prüfer in M1: eigener Limb oder Rolle eines bestehenden Limbs?
2. M2: Container-Isolation Pflicht oder optional pro Limb?
3. M5: echtes Gateway (eigener Prozess) oder Pflicht-Bibliothek?
