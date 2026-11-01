# NIO: Harness-Lücken und Integrationsplan

Stand 2026-11-01, abgeglichen mit `main` (`ad1fc8a`, nach PR 278, 279, 286). Die Analyse lief ohne Testsuite.
Dieser Plan ergänzt `docs/helpers/INTEGRATION_PLAN.md` (ADR-001) und korrigiert ihn dort, wo er nicht mehr stimmt.

**Annahmen**
- „Apollo“ meint NIOs Oberfläche in `frontend/src/apollo/` plus `apollo/ciel`, nicht den Dienst Apollo.io.
- „Manus“ meint den gehosteten Dienst mit API, „OpenManus“ das lokale Projekt. Es sind zwei getrennte Limbs.
- Sprache bleibt kostenlos. Für Manus fallen Kosten an, das braucht deine Entscheidung (Abschnitt 7).

## 1. Ergebnis

Die Helfer sind nicht das größte Problem. **Der Harness ist noch nicht sicher genug für Agenten, die Code ausführen.**
ADR-001 startet direkt mit den Helfern, dieser Plan zieht deshalb zwei Stufen davor:

1. Harness absichern (Phasen 0 und 1).
2. Ein gemeinsames Gateway für alle externen Agenten bauen (Phase 2).
3. Apollo an das echte Backend anschließen (Phase 3). Vorher lässt sich nichts bedienen oder freigeben.
4. Erst dann die Helfer anschließen, einen nach dem anderen (Phasen 4 bis 10).

## 2. Lücken im Harness

Mit „✓“ markierte Befunde habe ich direkt im Code gegengeprüft, der Rest stammt aus der Code-Sichtung. Laufzeit-Exploits wurden nicht ausprobiert.

### Kritisch: vor jedem Agenten schließen

| # | Lücke | Beleg | Folge |
|---|---|---|---|
| K1 ✓ | Apollo-Proxy nimmt jede Ziel-URL an und hängt `FREELLMAPI_KEY` an jeden fremden Host | `frontend/src/app/api/apollo/route.ts:78-95`, `next dev -p 4001` ohne `-H` | Ein erreichbarer Dev-Server kann den Key abfließen lassen. Next bindet ohne `-H` standardmäßig alle Schnittstellen |
| K2 ✓ | Worker kann seine eigene `SOUL.md` zurückschreiben, darin `runtime: command` mit beliebigem argv | `orchestrator/kanban/sync.py:122-133`, `store.py:60`, `worker_entry.py:150-172` | Ein Agent verschafft sich beim nächsten Lauf eine freie Shell |
| K3 ✓ | Worker-Sandbox ist standardmäßig `subprocess`, also ohne Isolation | `orchestrator/kanban/config.py:50` | Agentencode läuft direkt auf dem Host |
| K4 ✓ | Sigma-Kill-Switch lässt sich ohne Auth lösen | `workspace/sigma/app/server/routes_sigma.py:513` | Berührt den Kapitalschutz. Der Fix liegt als `patches/sigma-runtime.patch` vor (PR 279, Trockenlauf fehlerfrei), ist aber nicht eingespielt und braucht `SIGMA_OPERATOR_TOKEN`. Laut Sichtung kommen `CORS *` und Risiko-Tools ohne Gate hinzu. Port 8731 ist nur lokal gebunden ✓, ein Agent auf dem Host erreicht ihn aber |
| K5 | Freigabe ist nur ein Textfeld: `approved_by: human` lässt sich ohne Signatur setzen | `core/protocol.py:528`, `core/policy.py:156` | Kein Mensch steht wirklich hinter einer Freigabe |
| K6 ✓ | Geschützt sind nur fünf Pfade, `orchestrator/runner.py`, `core/kernel.py`, `protocol/operations.json` und `limbs/registry.json` fehlen | `neu.config.json:46-52` | Ein Agent mit `repo_write` kann die eigenen Regeln ändern. Der Planner eskaliert laut Sichtung zudem selbst (`planner.py:186-199`) |
| K7 | Limbs erben die vollständige Host-Umgebung | `orchestrator/runner.py:1026`, `:1315` | Secrets landen in jedem Limb |
| K8 ✓ | Der harte Abbruch trifft nur den Hauptprozess | `orchestrator/runner.py:1432`, keine Prozessgruppe | Kindprozesse und Container können weiterlaufen. PR 279 löst das nur für den MCP-Client in `apollo/ciel/mcp_nodes.py` |

### Fehlende Bausteine

| # | Lücke | Beleg |
|---|---|---|
| F1 | `risk` wird nicht erzwungen, nur `requires_elevation` | `core/policy.py:301`, `:409` |
| F2 | Kein Freigabe-Ablauf: Telegram sendet nur, Apollo fragt nichts ab | `orchestrator/kanban/notify.py:28` |
| F3 | Kein Kill-Switch im NIO-Kern | nur in Sigma |
| F4 | Kein Budget für Token oder Credits | nur Zeit, Iterationen, Slots |
| F5 | Netz kennt nur `none` oder voll, OpenCode und OpenManus brauchen aber ein Modell | `orchestrator/kanban/config.py:56` |
| F6 | Der Limb-Vertrag ist für kurze Läufe gebaut: ein Prozess je Intent, im Dev-Profil ein Slot | `limbs/base.py`, `orchestrator/locks.py` |
| F7 | Kein Modellzugang im NIO-Kern, `LLMClient` ist nur ein Protokoll | `orchestrator/kanban/decomposer.py:71` |
| F8 | Apollo spricht nicht mit Kanban oder Orchestrator, `/spawn` und `/dispatch` wirken nur lokal | `frontend/src/apollo/store.ts:750-756` |
| F9 | Marktdaten hängen an tvremix, das abgeschaltet wird (50 Aufrufe pro Tag, Ersatz ist der offizielle TradingView-MCP) | `frontend/src/app/api/market/[tool]/route.ts` |
| F10 | `/ops` zeigt simulierte Daten, `runtime/system.log` ist nur ein Anker, es gibt keine Metriken | `frontend/src/app/ops/page.tsx:93`, `orchestrator/events.py:384` |
| F11 | CI für NIO ist nicht aktiv, Docker- und Postgres-Tests werden übersprungen | `ci/neu.yml`, `tests/test_kanban_sandbox.py:174` |
| F12 | Vier Operationen ohne Handler: `fs.delete`, `shell.exec`, `test.run`, `core.memory_write` | `protocol/operations.json` |
| F13 | Hermes-Phasen 0 bis 3 und 5 fehlen, Phase 4 ist teilweise da | `docs/hermes/RUNTIME_PLAN.md` |

### Akutes Verlustrisiko

Behoben am 2026-11-01: Der Sprachcode ist auf `fix/ui-testlauf-batch` gepusht (`7931c0a` Sprache, `8c0c941` UI). Die Trennung in `feat/speech-input` steht noch aus. Toolbox-Limb und `docs/helpers/` liegen auf eigenen Branches.

### Korrekturen an ADR-001

| ADR-001 sagt | Tatsächlich |
|---|---|
| Alle Helfer liegen in `Nio Helpers` | OpenManus und Cua liegen eigenständig in `Downloads`, dafür fehlen betterccxt und betterfinbert im Plan |
| `ffmpeg` fehlt | `/usr/bin/ffmpeg` ist vorhanden |
| `workspace/obsidian` ist leer | Der Ordner existiert nicht |
| VoiceStudio auf Port 8013 | Standard ist `127.0.0.1:3900` |
| Immich als feste Version | Das Archiv ist `3.4.0-rc.0`, also kein stabiles Release, und bindet Port 2283 auf alle Schnittstellen |
| OpenManus-Limb heißt `manus` | Name wird für den gehosteten Dienst gebraucht, lokal heißt er `openmanus` |
| Cua über `cua-sandbox` | `cua-sandbox` verlangt Python unter 3.14, der Host hat 3.14.4, und das Lizenzbild des `cua`-Wheels ist ungeklärt |
| Modelllizenz von VoiceStudio prüfen | Alle 77 Einträge stehen auf `commercial_use: false` |

Ressourcen heute: 17 GB Platte frei (Ziel 25 GB), 10 GB RAM verfügbar, Swap laut Sichtung voll. `/dev/kvm` ist da, gVisor (`runsc`) nicht.

## 3. Zielbild

```
Apollo (Web, Sprache)   Telegram
        │                  │
        ▼                  ▼
   Kanban-API (Operator-Auth, Freigaben, Kill-Switch)
        │
        ▼
   Dispatcher ──▶ Worker-Runtime `limb` (feste Operationen, kein argv)
                      │
                      ▼
   Agent-Gateway: Policy · Budget · Umgebung · Prozessgruppe · Protokoll
        │              │               │              │
     manus          openmanus       desktop        opencode
    (HTTPS)        (Container)     (Container)    (Container)
                       │
                       ▼
        internes Docker-Netz nio-agents ──▶ freellmapi
        Webzugriff nur je Lauf über Egress-Proxy mit Allowlist
```

**Grundsätze**
- Fremdcode bleibt außerhalb des Repos und läuft als Dienst oder Container hinter einem Limb (ADR-001, Option B).
- Der Kern bleibt Standardbibliothek.
- Agenten erhalten nie Kraken-Tools, Sigma-Zugriff, Keys, `$HOME` oder `docker.sock`.
- Ergebnisse externer Agenten sind Daten. Sie werden nie zu Prompts, SOUL-Dateien oder Freigaben.
- Immer nur ein schwerer Agent gleichzeitig, solange der RAM so knapp ist.

## 4. Phasen

Aufwand: S unter einem Tag, M einige Tage, C eine Woche oder mehr. Jede Phase bekommt einen eigenen Branch und PR.
⚠ heißt: Die Phase ändert `human_only_globs`-Dateien und braucht deine Freigabe.

### Phase 0: Bestand sichern (S)

1. Sprachcode aus `fix/ui-testlauf-batch` nach `feat/speech-input` übernehmen, UI-Änderungen getrennt.
2. Erledigt: Toolbox-Limb und Leafs auf `feat/toolbox-limb`, Pläne auf `docs/integrationsplan`.
3. Grundlinie messen: `make check`, Ergebnis in `docs/TESTING.md` festhalten.
4. Build-Cache leeren, nach Freigabe (Ertrag ungewiss, siehe Abschnitt 7). speaches auf eine feste Version stellen.

**Abnahme:** Sprachtest läuft aus frischem Checkout, mindestens 25 GB frei, Grundlinie dokumentiert.

### Phase 1: Sicherheits-Hotfixes (M) ⚠

| Paket | Inhalt | Dateien |
|---|---|---|
| 1.1 | Proxy mit Allowlist: Key nur an seinen Host, sonst Abweisung; Dev-Server auf `127.0.0.1`; Middleware für `/api/*` | `frontend/src/app/api/apollo/route.ts`, `frontend/src/middleware.ts`, `frontend/package.json` |
| 1.2 | Worker-Änderungen an `SOUL.md` nur noch als Vorschlag mit Freigabe; `runtime` und `command` sind für Worker nicht änderbar | `orchestrator/kanban/sync.py`, `worker_entry.py` |
| 1.3 | Runtime `command` nur mit Docker-Sandbox; Docker wird Standard, `subprocess` nur für `noop` | `orchestrator/kanban/config.py`, `sandbox.py` |
| 1.4 | Sigma: `patches/sigma-runtime.patch` einspielen, Token setzen, offene Punkte aus `patches/README.md` schließen (täglicher PnL über Redis, sichere Oberfläche zum Lösen). Sigma liegt ungetrackt in `workspace/`, deshalb zuerst den Sigma-Stand sichern | `workspace/sigma/` |
| 1.5 | Sandbox-Jail: alle Pfade prüfen, Route nur mit Auth | `frontend/src/app/api/sandbox/route.ts` |
| 1.6 | `human_only_globs` erweitern um Runner, Kernel, Planner, Sandbox, Operationen, Registry | `neu.config.json` ⚠ |
| 1.7 | Planner darf `repo_write` nicht selbst vergeben | `orchestrator/planner.py` |
| 1.8 | Marktdaten auf den offiziellen TradingView-MCP umstellen (baut auf PR 262 auf) | `frontend/src/app/api/market/[tool]/route.ts` |

**Abnahme:** Für jede Lücke K1 bis K4 und K6 gibt es einen Test, der vor dem Fix fehlschlägt und danach besteht.

### Phase 2: Agent-Gateway (C) ⚠

Gemeinsamer Unterbau, den alle Agenten nutzen. Hier entscheidet sich, ob spätere Helfer klein bleiben.

| Paket | Inhalt | Dateien |
|---|---|---|
| 2.1 | **Lauf-Modell:** kurze Operationen `<limb>.start/status/stop/collect`, Zustand unter `runtime/agents/<run_id>/`. So blockiert ein stundenlanger Lauf keinen Slot | `limbs/agent_base.py`, Tests |
| 2.2 | **Freigabe-Ticket:** HMAC über Intent-Hash, Ablauf und Operation; der Schlüssel liegt außerhalb der Reichweite von Limbs und Workern | `core/policy.py` ⚠, `core/protocol.py`, `orchestrator/kanban/api.py` |
| 2.3 | **`risk` erzwingen:** `high` und `external` nur mit gültigem Ticket | `core/policy.py` ⚠, `protocol/operations.json` |
| 2.4 | **Umgebung:** nur Variablen aus `env_allow` des Limbs | `orchestrator/runner.py`, `limbs/registry.json`, `limbs/rea_limb.py` |
| 2.5 | **Abbruch:** eigene Prozessgruppe, `killpg`, Container per `docker kill` | `orchestrator/runner.py` |
| 2.6 | **Kill-Switch:** `runtime/STOP` stoppt alle Läufe und blockiert neue | `orchestrator/runner.py`, `orchestrator/kanban/dispatcher.py`, `orchestrator/cli.py` |
| 2.7 | **Budget:** Grenzen für Laufzeit, Token und Credits je Lauf und Tag; Überschreitung beendet den Lauf | `orchestrator/budget.py`, `neu.config.json` ⚠ |
| 2.8 | **Container-Start:** ein gemeinsamer Helfer für `--read-only`, `--cap-drop ALL`, Nicht-Root, Limits, Mounts je Lauf | `limbs/agent_base.py`, `orchestrator/kanban/sandbox.py` |
| 2.9 | **Netz:** internes Docker-Netz `nio-agents` mit freellmapi; Webzugriff nur über Proxy-Container mit Allowlist je Lauf | `docker/egress-proxy/`, `docs/OPERATIONS.md` |
| 2.10 | **Worker-Runtime `limb`:** führt eine feste Operation aus, kein argv. Das verbindet Kanban mit Limbs | `orchestrator/kanban/worker_entry.py` |
| 2.11 | **Protokoll:** jeder Lauf schreibt Ereignisse, Kosten und Artefakte; `runtime/system.log` wird real | `orchestrator/events.py` |
| 2.12 | CI aktivieren (Mensch verschiebt `ci/neu.yml`), Docker-Tests dort einschalten | `.github/workflows/` ⚠ |

**Abnahme:** Mit `echo` als Testagent: Ohne Ticket abgewiesen, mit gefälschtem Ticket abgewiesen, Budget beendet den Lauf, `runtime/STOP` stoppt ihn in unter 5 Sekunden, nach dem Abbruch bleibt kein Prozess und kein Container übrig. Ein Testcontainer erreicht freellmapi, aber nicht das Internet, Sigma oder den Host.

**Abgrenzung zu Hermes:** Die Ciel-Policy mit Lua aus Phase 1 des Hermes-Plans wird hier nicht gebaut. Die Tickets decken den Bedarf ab und bleiben Grundlage für Hermes. `RUNTIME_PLAN.md` wird angepasst, damit nichts doppelt entsteht.

### Phase 3: Apollo als Leitstand (C)

| Paket | Inhalt | Dateien |
|---|---|---|
| 3.1 | Server-Proxy zur Kanban-API, Operator-Token nur serverseitig | `frontend/src/app/api/apollo/kanban/` |
| 3.2 | `/spawn` und `/dispatch` erzeugen echte Aufgaben, Knoten zeigen echte Worker | `frontend/src/apollo/store.ts`, `commands.ts` |
| 3.3 | Neue Befehle `/agent`, `/runs`, `/approve`, `/deny`, `/stop`, `/stopall` | `frontend/src/apollo/commands.ts` |
| 3.4 | Freigabekarte: Aktion, Ziel, Kosten, Datenabfluss, Ablauf; kein automatisches Freigeben | `frontend/src/apollo/` |
| 3.5 | Sichtbarer Not-Aus, Lauf-Ansicht mit Kosten und Artefakten | `frontend/src/apollo/` |
| 3.6 | Sprach-Diktat übernehmen; Text landet im Feld, wird nie automatisch gesendet, Freigaben gehen nicht per Sprache | aus Phase 0 |
| 3.7 | `/ops` von Simulation auf echte Daten umstellen oder Mock klar kennzeichnen; Ciel-Tools verdrahten, soweit Apollo sie braucht | `frontend/src/app/ops/page.tsx`, `apollo/ciel/` |
| 3.8 | `speech`-Limb, Sprachstatus im Orb (ADR-001, Phase 1) | `limbs/speech_limb.py`, `frontend/src/apollo/` |

**Abnahme:** Im Browser: `/agent echo …` erzeugt eine Aufgabe, zeigt die Freigabekarte, läuft nach `/approve` durch und liefert ein Ergebnis. Der Not-Aus beendet einen laufenden Testlauf. Diktat funktioniert, und ein Ausfall von speaches ergibt 503 statt erfundenem Text.

### Phase 4: Obsidian (M)

Der Vault ist ein Ordner mit Markdown. Der Zugriff läuft direkt über Dateien, die App ist nur zum Lesen da. Die offizielle CLI braucht eine laufende App, das Headless-Paket synchronisiert nur, und REST-Plugins hätten eine zusätzliche Angriffsfläche.

1. `workspace/obsidian` anlegen, Struktur laut ADR-001, eigenes lokales Git als Sicherung.
2. `vault`-Limb: `ping`, `search`, `read`, `capture`. Suche mit SQLite FTS5 (auf dem Host geprüft, läuft).
3. Agenten schreiben nur nach `Inbox/`, `workers/`, `tasks/`, nie nach `Knowledge/`.
4. Apollo: `/note`, `/vault <suche>`, Diktat als Notiz.
5. Lesender MCP-Server `scripts/vault_mcp.py` für OpenCode.
6. Notizen gelten als Fremdinhalt und werden beim Weitergeben entsprechend markiert. An Manus gehen sie nur auf ausdrückliche Auswahl im Auftrag.

**Abnahme:** Diktat steht mit Frontmatter in `Inbox/`, Suche findet es in unter einer Sekunde, `../` und Symlinks nach außen werden abgewiesen.

### Phase 5: OpenCode (M)

ADR-001, Phase 3 gilt, mit drei Änderungen: Container, Netz und Abbruch kommen aus dem Gateway, der Aufruf läuft über Runtime `limb`, und `/code` nutzt die Freigabekarte.

**Abnahme:** Aufgabe ändert eine Datei und committet lokal auf dem Worker-Branch, ein Push scheitert, der Timeout beendet einen hängenden Lauf.

### Phase 6: OpenManus (C)

Der Code wird nicht verändert. Ein eigener Runner im Image umgeht die bekannten Bruchstellen.

| Paket | Inhalt |
|---|---|
| 6.1 | Quelle festlegen: Upstream-Commit des Downloads ermitteln und pinnen, Image aus `docker/openmanus/` mit `.dockerignore`, Nicht-Root, Python 3.12 |
| 6.2 | `config.toml` wird je Lauf erzeugt, mit Platzhalter-Abschnitt `[daytona]` (sonst bricht laut Code `app/config.py:297` den Start ab) und ohne Provider-Keys |
| 6.3 | `OPENMANUS_DISABLE_BROWSER_USE=1`, damit kein ungepinntes `uvx browser-use` startet. Browser folgt erst nach einem eigenen Test |
| 6.4 | `use_sandbox` bleibt aus: **Der Container selbst ist die Sandbox**, verschachteltes Docker hieße `docker.sock` mounten |
| 6.5 | `docker/openmanus/runner.py` ruft Manus auf und schreibt `out/result.json`. Der Abschluss wird aus dem `terminate`-Zustand gelesen, Text-Parsing ist fragil. Unklare Ergebnisse gelten als `failed` |
| 6.6 | `openmanus`-Limb auf Basis des Gateways, `risk: high`. A2A und `run_mcp_server.py` werden nicht verwendet, beide wären ein offener Weg zur Codeausführung |

**Abnahme:** Testauftrag erzeugt ein Artefakt. Negativtests im Container: Host-Dateien, `docker.sock`, Sigma-Port, Kraken-Keys, fremde Hosts sind nicht erreichbar. Stop und Timeout entfernen den Container. Plattenbedarf ist gemessen.

### Phase 7: Manus, gehostet (M)

Offizielle API v2 (`https://api.manus.ai/v2/`, Header `x-manus-api-key`). Das ist der einzige Agent, bei dem Daten den Rechner verlassen.

| Paket | Inhalt |
|---|---|
| 7.1 | Zuerst Doku zu Task-Lebenszyklus, Status und Credit-Feldern lesen. Das ist bisher nicht geprüft |
| 7.2 | `manus`-Limb: `ping` (`user.me`), `start` (`task.create`), `status` (`task.detail`, `task.listMessages`), `stop` (`task.stop`), `collect` (`artifact.list`), `usage` (`usage.list`). Nur `urllib` |
| 7.3 | Feste Vorgaben: `clear_connectors: true`, `share_visibility: private`, `agent_profile: lite`, `interactive_mode: false` |
| 7.4 | **Polling statt Webhooks:** Webhooks verlangen einen öffentlichen HTTPS-Endpunkt, und NIO soll keinen Port öffnen. Abstand mindestens 10 Sekunden, Backoff mit Jitter bei `429` (Limit 100 pro Minute für Lesezugriffe, 10 für `task.create`) |
| 7.5 | Rückfragen von Manus (`task.confirmAction`) gehen als Karte an Apollo, nie automatisch bestätigen |
| 7.6 | Filter vor dem Senden: Secrets und Pfade aus `runtime/`, `workspace/sigma`, `.env` werden abgewiesen. `risk: external`, jede Sendung braucht ein Ticket |
| 7.7 | Budget über `usage.list`; bei Überschreitung `task.stop` |

**Abnahme:** Mit gefälschtem Dienst: Erfolg, 429, Ausfall, Timeout, Budgetstopp. Danach ein echter `lite`-Testlauf mit deiner Freigabe. Der Key erscheint in keinem Log und keinem Artefakt.

### Phase 8: Cua (C)

**Entscheidung:** Das Image `libs/xfce-cua` wird aus festem Stand selbst gebaut und über den enthaltenen `cua-driver` (MIT) gesteuert. `cua-sandbox`, das `cua`-Wheel, `cua-agent` (deprecated), Lume und Cua Spaces (FSL) entfallen. `cua-driver` auf dem Host bleibt verboten, dort sind Browser-Logins und Trading-Oberflächen offen.

1. Spike: Image bauen, Größe messen, Start im Docker-Netz prüfen. Die Annahme, dass der Treiber im Image per MCP erreichbar ist, wird dabei bestätigt oder der Plan angepasst.
2. Härtung: zufälliges `VNC_PW` je Lauf (ohne Passwort läuft VNC offen), noVNC nur auf `127.0.0.1`, `DO_NOT_TRACK=1`, `CUA_TELEMETRY=0`.
3. `desktop`-Limb: `start`, `status`, `screenshot`, `stop`, `collect`.
4. Eigene kleine Schleife aus Screenshot, Modell und Aktion, mit Schrittgrenze und Budget.
5. Live-Ansicht in Apollo.

**Abnahme:** Agent öffnet in der Sandbox eine App und liefert einen Screenshot. Nach dem Lauf ist kein Container mehr da, der Host-Desktop wurde nie angesprochen.

**Risiko:** Die Schleife braucht ein Modell mit Bildverständnis. `qwen2.5-coder` und `llama3.1:8b` kommen dafür kaum infrage, ob `freellmapi` eines liefert, ist ungeprüft. Fehlt es, bleibt Phase 8 beim Spike stehen.

### Phase 9: python-genai und awesome-opencode (S)

- `google-genai` in `Architect/requirements.txt` pinnen, Function Calling ausdrücklich steuern. Der in ADR-001 genannte LM-Studio-Fallback ließ sich in `genai_client.py` nicht finden, das zuerst klären.
- `awesome-opencode` bleibt Katalog. Plugins kommen nur nach Durchsicht und mit fester Version dazu.

### Phase 10: Schwere Helfer (C, nur bei freien Ressourcen)

- **VoiceStudio:** auf Abruf, Port 3900, `voice`-Limb. Nur privat nutzen, alle Modelle sind als nicht kommerziell eingetragen.
- **Immich:** nur mit eigenem Datenträger, stabilem Release, Bindung an `127.0.0.1:2283`, Lese-Key, `photos`-Limb ohne Löschen.

### Nicht eingebaut

| Helfer | Grund |
|---|---|
| openclaw-zero-token | Nutzt Web-Logins für kostenlose API-Aufrufe, das Projekt nennt selbst das Sperrrisiko. Bleibt bei ADR-001 |
| betterccxt | Enthält einen Live-Order-Pfad und eine Agenten-Schnittstelle für Orders, das widerspricht dem Kapitalschutz. Keine Lizenzdatei, also auch keine Code-Übernahme |
| betterfinbert | Ist trotz Namen nur ein Schlagwort-Lexikon, keine Lizenz |

Wird echtes FinBERT für Sentiment gebraucht, kommt es als eigener kleiner Limb mit dem offenen Modell, das ist ein separater Plan.

## 5. Reihenfolge

Entscheidung vom 2026-11-01: Sprache, Obsidian und Manus werden vorgezogen und parallel zur Absicherung gebaut. Das ändert die Kette aus Abschnitt 1 so:

| Spur | Inhalt | Wer |
|---|---|---|
| A | Sprache (0.1, 3.6, 3.8), dann Obsidian (4), dann Manus (2.1 und 7) | Claude |
| B | Absicherung, Welle 1 und 2 aus Abschnitt 9 | Jules |
| C | Entscheidungen, Freigaben, 1.6, 2.12 | Mensch |

**Sperre für Manus:** Der Limb wird gegen einen gefälschten Dienst gebaut und getestet. Ein echter Lauf findet erst statt, wenn die Tickets aus J4 gemergt sind und du Key und Budget gegeben hast.

Sprache und Obsidian bleiben lokal und schicken nichts nach außen, deshalb dürfen sie vor dem Gateway laufen. Ihre Routen fallen unter den Schutz aus J1, sobald er gemergt ist.

OpenCode, OpenManus und Cua führen Code aus und warten weiter auf Phase 2.

## 6. Gesamtprüfung

- Jede Phase: `make check` und die neuen Tests grün, Vergleich mit der Grundlinie aus Phase 0.
- Jeder Limb erfüllt die Abnahmeliste aus ADR-001, Abschnitt 4, und ist über die Toolbox auffindbar.
- Oberfläche wird im Browser geprüft: Konsole, Netzwerk, Screenshot.
- **Roter Testlauf nach Phase 8:** Ein Auftrag aus Apollo per Sprache läuft bis zum Artefakt im Vault, inklusive Freigabe. Danach versucht ein Testagent bewusst, an Keys, Sigma, Kraken, den Host und das offene Netz zu kommen. Alles muss scheitern und im Protokoll stehen.
- Nach jedem Lauf: `docker ps` zeigt keine Reste.

## 7. Entscheidungen von dir

| # | Frage | Empfehlung |
|---|---|---|
| 1 | Freigabe für Änderungen an `human_only_globs`-Dateien in Phasen 1 und 2 | Ja, je PR einzeln prüfen |
| 2 | Build-Cache leeren | Ja, aber Ertrag vorher mit `docker buildx du` prüfen: `docker system df` zeigt 11,16 GB bei 0 aktiven Einträgen, nennt aber 0 B als freigebbar. Reicht es nicht, muss anderer Platz frei werden |
| 3 | Manus: API-Key und Tagesbudget | Erst in Phase 7 nötig. Bezahlter Dienst, Preise habe ich nicht gefunden |
| 4 | Obsidian-App | Optional, NIO läuft ohne sie |
| 5 | VoiceStudio nur privat? | Bitte bestätigen, sonst entfällt es |

## 8. Offene Punkte

- Keine Testsuite wurde ausgeführt, Testzahlen sind statisch gezählt.
- Die Startfehler von OpenManus sind aus dem Code gelesen, nicht ausgeführt.
- Herkunft der laufenden Container `fable5-paper` und `neo-fabel-postgres` ist unklar. Sie bleiben unberührt.
- Plattenbedarf von OpenManus- und Cua-Images ist ungemessen.
- Status- und Credit-Felder der Manus-API sind nicht belegt, Preise ebenso.
- Zur Obsidian-CLI und zum Headless-Paket lagen nur Sekundärquellen vor. Für die Entscheidung genügt das, weil beides nicht verwendet wird.

## 9. Arbeitsaufteilung Jules

Die Aufträge liegen in `docs/helpers/jules/`. Sie sind in sich vollständig, weil Jules von `main` startet und dieser Plan dort erst nach dem Merge liegt.

**Welle 1 (dispatcht am 2026-11-01, Dateien überschneiden sich kaum):**

| Auftrag | Pakete | Lücken | Branch |
|---|---|---|---|
| `J1-frontend-haertung.md` | 1.1, 1.5 | K1 | `jules/j1-frontend-haertung` |
| `J2-kanban-worker.md` | 1.2, 1.3 | K2, K3 | `jules/j2-kanban-worker` |
| `J3-runner-haertung.md` | 2.4, 2.5, 2.6 | K7, K8, F3 | `jules/j3-runner-haertung` |
| `J4-freigabe-tickets.md` | 1.7, 2.2, 2.3 ⚠ | K5, F1 | `jules/j4-freigabe-tickets` |

**Welle 2 (erst nach dem Merge von Welle 1):** 2.7 Budget, 2.8 und 2.9 Container und Netz, 2.10 Runtime `limb`, 2.11 Protokoll, Phase 3 ohne 3.6 und 3.8, danach OpenCode, OpenManus, der Cua-Spike und Phase 9.

**Nicht für Jules:**

| Paket | Grund |
|---|---|
| 1.4 Sigma | Liegt ungetrackt auf dem Host und berührt den Kapitalschutz |
| 1.6, 2.12 | Änderungen, die ein Mensch vornimmt |
| 1.8 Marktdaten | PR 262 ist offen und mergebar, hier fehlt nur die Prüfung |
| 2.1 und Phase 7 | Baut Claude zusammen mit Manus, Jules hat keinen Zugang zu Manus |
| Phase 10, Phase 0 Schritt 3 und 4 | Brauchen den Host |

Jules-Ergebnisse gelten erst als fertig, wenn der PR geprüft ist. Docker-Tests laufen dort vermutlich nicht, das steht dann im PR.
