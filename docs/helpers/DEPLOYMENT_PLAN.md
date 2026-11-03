# NIO: Plan für das Deployment

Stand 2026-11-01. Nur Plan, nichts davon ist ausgeführt. Grundlage sind `main` (`284b2e1`) und der laufende Host.

**Annahmen**
- Deployment heißt: NIO läuft dauerhaft auf diesem Linux-Rechner und ist nur lokal erreichbar. Ein öffentlicher Zugang ist nicht geplant.
- Trading bleibt im Paper-Modus. Live-Orders sind nicht Teil dieses Plans.
- Sprache und Modellzugang bleiben kostenlos.

## 1. Ausgangslage

| Punkt | Befund |
|---|---|
| Start | Es gibt nur Handstart. Im Repo fehlen Compose-Datei und systemd-Units, nur `docker/openmanus/Dockerfile` existiert |
| CI | Aktiv ist nur `ci-evals.yml`. `ci/neu.yml` für Kern, Limbs und E2E ist nicht aktiviert (Paket 2.12) |
| Apollo | Port 4001 lauscht auf allen Schnittstellen. J1 behebt das, ist aber noch nicht gemergt |
| TradingView-MCP | Am 2026-11-02 auf `127.0.0.1:8080` gebunden, Änderung in `~/Desktop/fable5-tradingview-kraken-paper/docker-compose.yml` |
| Alter Orchestrator | `node dist/server.js` aus `~/Desktop/Architect/NIO` (Stand PR 250, tmux-Sitzung `nio-api`) lief offen auf `0.0.0.0:4000`. Am 2026-11-02 gestoppt, ohne Autostart |
| Platte | 18 GB frei, 92 % belegt. Das Ziel aus dem Harness-Plan sind 25 GB |
| Speicher | 9,5 GB verfügbar, 2,8 GB Swap belegt |
| Sigma | Der Kill-Switch-Patch ist am 2026-11-02 in `workspace/sigma` eingespielt, Sicherung in `~/nio-sicherung/`, Token in `~/.config/nio/sigma.env`. Offen aus 1.4: täglicher PnL über Redis und sichere Oberfläche zum Entsperren. 68 Sigma-Tests schlagen wie vor dem Patch fehl, dazu 13 Fehler in `test_blueprint_spec.py` |
| Kanban-Docker-Sandbox | Läuft auf diesem Rechner nicht: Snap-Docker bricht mit `no-new-privileges` ab. Vor Stufe 1 entscheiden, ob Docker aus apt kommt oder die Option abschaltbar wird |
| freellmapi | Hängt noch nicht im Netz `nio-agents`, `scripts/agents_network.sh` fehlt noch (Stufe 1) |
| Laufend | speaches, freellmapi, sigma-redis, tradingview-mcp. `fable5-paper` und `neo-fabel-postgres` gehören zu einem unklaren Stand und bleiben unberührt |

## 2. Reihenfolge

Eine Stufe beginnt erst, wenn die Abnahme der vorherigen erfüllt ist.

### Stufe 0: Blocker schließen

1. PRs von J1 bis J4 prüfen und mergen, J4 mit Handprüfung wegen `core/policy.py`.
2. Danach J5 bis J10 auf den neuen `main` bringen, prüfen, mergen. Reihenfolge siehe Abschnitt 4.
3. Du erweiterst `human_only_globs` in `neu.config.json` (1.6) und verschiebst `ci/neu.yml` nach `.github/workflows/` (2.12).
4. Sigma: Stand sichern, Patch einspielen, `SIGMA_OPERATOR_TOKEN` setzen, Tests laufen lassen (1.4). Das läuft auf dem Host, nicht über Jules.
5. Port 8080 auf `127.0.0.1` binden und alten Dienst auf Port 4000 stoppen (beides erledigt am 2026-11-02).

**Abnahme:** `make check` ist auf `main` grün, instabile Tests sind benannt. CI läuft auf PRs. `ss -ltn` zeigt keinen NIO-Dienst außerhalb von Loopback.

### Stufe 1: Reproduzierbarer Start

1. `deploy/compose.yaml` für die zustandsbehafteten Dienste (speaches, freellmapi, Redis, optional Qdrant), alle mit festen Image-Versionen und Bindung an `127.0.0.1`. Bestehende Container werden nicht ersetzt, bevor die Daten gesichert sind.
2. systemd-User-Units für Kanban-API, Dispatcher, Orchestrator und Apollo, jeweils mit `Restart=on-failure`, Limits und Start nach Docker.
3. Apollo läuft als Produktions-Build (`next build`, `next start -H 127.0.0.1`) statt als Dev-Server.
4. `deploy/env.example` listet alle Variablen ohne Werte. Die echte Datei liegt außerhalb des Repos mit Rechten `600`.
5. `scripts/agents_network.sh` richtet `nio-agents` ein (kommt aus J6).

**Abnahme:** Nach einem Neustart des Rechners läuft alles ohne Handarbeit, und `make health` meldet jeden Dienst. Dieses Ziel gibt es noch nicht, es wird in dieser Stufe gebaut und nutzt die Health-Checks aus `docs/OPERATIONS.md`.

### Stufe 2: Geheimnisse und Betrieb

1. Neu erzeugen: `NIO_APPROVAL_KEY`, `NIO_KANBAN_API_TOKEN`, `NIO_APOLLO_APPROVAL_PIN`, `SIGMA_OPERATOR_TOKEN`. Limbs und Worker bekommen keinen davon. Der PIN steht nur serverseitig und wird bei jeder Freigabe von Hand eingegeben.
2. Sicherung für SQLite-Store, `runtime/`, Vault-Git und Sigma-Daten. Eine Rücksicherung wird einmal real geübt.
3. Logrotation prüfen (aus J8). Plattenwarnung ab 90 %.
4. Telegram-Meldung bei Dienstausfall, ausgelöstem Budget und `runtime/STOP`.
5. Build-Cache erst nach Prüfung mit `docker buildx du` leeren, damit die 25 GB erreicht werden.

**Abnahme:** Rücksicherung auf leerem Pfad klappt. Der Prüflauf findet in Logs und Repo keine Geheimnisse.

### Stufe 3: Roter Testlauf

Aus Abschnitt 6 des Harness-Plans, auf dem deployten Stand:

- Auftrag aus Apollo per Sprache bis zum Artefakt im Vault, inklusive Freigabe.
- Testagent versucht, an Keys, Sigma, Kraken, Host und offenes Netz zu kommen. Alles muss scheitern und im Protokoll stehen.
- `runtime/STOP` beendet Läufe in unter 5 Sekunden, `docker ps` zeigt danach keine Reste.
- Ausfalltests: freellmapi, speaches und Kanban-API einzeln stoppen. Apollo zeigt Fehler statt erfundener Daten.

### Stufe 4: Freischalten

Jeweils einzeln, mit eigener Abnahme und nur auf deine Freigabe:

1. OpenManus von `planned` auf aktiv (Bedingung aus dem Harness-Plan: 2.8, 2.9 und J4 sind gemergt und der Limb nutzt sie).
2. OpenCode (Phase 5), danach Cua. J11 ([PR 298](https://github.com/Finnlayy/NIO/pull/298)) kommt zu „No-go“, weil das Image groß ist (geschätzt, der Bau schlug fehl) und `cua-driver` nur über einen Unix-Socket erreichbar ist. Das ist noch keine belastbare Absage: Die Größe ist nicht gemessen und der Socket ließe sich weiterleiten. Vor Phase 8 entscheidest du, ob auf dem Host ein echter Build gemessen wird.
3. `mode` in `neu.config.json` erst dann über `dev` hinaus. Die Datei steht unter dem Constitution Guard.

Live-Trading bleibt außerhalb. Es bräuchte eine eigene Entscheidung, harte Limits und einen Not-Aus außerhalb der KI-Logik.

## 3. Rücknahme

- Jede Stufe bekommt ein Git-Tag `deploy-sN`. Zurück geht es über das Tag und `systemctl --user restart`.
- Vor Stufe 1 und vor jeder Datenänderung läuft die Sicherung aus Stufe 2 von Hand.
- Bei Vorfällen zuerst `runtime/STOP`, dann Analyse.

## 4. Merge-Reihenfolge für die Jules-PRs

1. J2 ([PR 295](https://github.com/Finnlayy/NIO/pull/295)) und J1 ([PR 306](https://github.com/Finnlayy/NIO/pull/306)), sie sind am wenigsten verzahnt.
2. J3 ([PR 308](https://github.com/Finnlayy/NIO/pull/308)), danach J4 ([PR 307](https://github.com/Finnlayy/NIO/pull/307)). Beide ändern `orchestrator/runner.py`, `orchestrator/cli.py` und `core/protocol.py`, einer muss also auf den anderen aufsetzen. `NIO_APPROVAL_KEY` erst nach J3 setzen, sonst sehen Limbs ihn.
3. J5 und J8. Beide ändern `limbs/agent_base.py` nur wenig.
4. J6, danach die Umstellung von `limbs/openmanus_limb.py` auf `limbs/container.py` durch Claude.
5. J7. Sein Hook in `orchestrator/kanban/sync.py` muss nach J2 neu eingepasst werden.
6. J9 und J10. J9 braucht die Ticket-Route aus J4 und den Stop-Pfad aus J3.
7. J11 und J12 sind jederzeit möglich.

Jules wird am 11. November nur noch lesbar. Was bis dahin offen ist, übernimmt Claude.

**Stand 2026-11-02 abends:** Alle zwölf PRs und die Korrekturen aus der Tabelle unten ([PR 311](https://github.com/Finnlayy/NIO/pull/311)) sind auf `main` (`0279b99`). PR 311 hat zusätzlich behoben: `/dispatch` nutzte ein nie angelegtes Board `apollo`, und `limbs/container.py` lehnte auf diesem Rechner jeden Mount ab, weil das Repo unter `$HOME` liegt. Offen bleibt: Apollo kennt keine Warteschlange offener Freigaben, `/approve` verweist deshalb auf `neu approve`, und die Freigabekarte ist nicht eingebunden.

**Stand 2026-11-02, später:** [PR 312](https://github.com/Finnlayy/NIO/pull/312) enthält den OpenManus-Umbau, 1.6, 2.12 und `make lint`. Er wartet auf deinen Merge.

**Stufe 1, Stand 2026-11-02 nachts:** [PR 313](https://github.com/Finnlayy/NIO/pull/313) enthält `deploy/` und `make health`. Der Live-Stand liegt im Worktree `.claude/worktrees/live`, Geheimnisse in `~/.config/nio/nio.env`. Dauerhafte Dienste richtest du selbst mit `bash deploy/install.sh` ein. Compose entfällt, weil die Dienste schon mit `unless-stopped` laufen. Der erste echte Lauf ging von Apollo bis in den Vault, aber ohne Modell. Dafür fehlt `FREELLMAPI_KEY`. Die Anzeige in Apollo ist teils Attrappe: Modellname und Provider-Zahlen sind fest im Code, Latenz und Last der Knoten sind erzeugt.

**Prüfung vom 2026-11-02:** Testmerge aller zwölf PRs auf `284b2e1` in dieser Reihenfolge, ohne Push. Zehn PRs ließen sich konfliktfrei mergen. Auf diesem Stand ohne PR 301 und 305: 584 Python-Tests bestanden, 10 übersprungen, 145 UI-Tests bestanden, `tests/test_ciel_mcp_nodes.py` ausgenommen.

| PR | Befund | Folge |
|---|---|---|
| 295 (J2) | Der Fix gegen gefälschte Vorschläge ist drin | Mergen. Wie ein Vorschlag angenommen wird, ist noch offen |
| 300 (J6) | Secrets gehen nicht mehr über argv. `user="root:root"` umgeht die Root-Sperre | Vor dem Merge korrigieren |
| 301 (J5) | Konflikt in `limbs/agent_base.py` nach PR 308: Not-Aus- und Budget-Prüfung gehören beide in `_start`. Die Datei liegt in `core/budget.py`, der Auftrag nannte `orchestrator/budget.py` | Konflikt lösen, beide Prüfungen behalten |
| 302 (J8) | Die Zusammenfassung entsteht nur in `_collect`. Läufe ohne `collect` fehlen im Log, ein eigener Start-Eintrag fehlt auch | Vor dem Merge korrigieren |
| 303 (J7) | `limb_request.json` wird ohne Symlink-Prüfung auf dem Host gelesen | Vor dem Merge korrigieren |
| 304 (J9) | `/approve` schickt `intent: {}` und kann nie gelingen. `/spawn` schickt einen leeren PIN, scheitert immer und zählt zur Sperre mit. Freigabekarte, Stop-Knopf und Lauf-Ansicht sind nirgends eingebunden, die Lauf-Ansicht meldet fest „keine Läufe“ | Nicht mergen, nacharbeiten |
| 305 (J10) | Einzeiliger Konflikt in `frontend/scripts/ui-test.mjs` nach PR 306 | Beim Merge beide Einträge behalten |

## 5. Noch nicht an Jules

OpenCode (Phase 5) wartet, weil es J6 und J7 braucht. Der Auftrag lässt sich erst sinnvoll schreiben, wenn beide gemergt sind.

## 6. Entscheidungen von dir

| # | Frage | Empfehlung |
|---|---|---|
| 1 | Bleibt NIO nur lokal, oder soll es von außen erreichbar sein? | Lokal. Fernzugriff höchstens über Tailscale oder WireGuard, nie per offener Portfreigabe |
| 2 | Muss `tradingview-mcp` aus dem Netz erreichbar sein? | Nein, auf `127.0.0.1` binden |
| 3 | systemd-User-Units oder alles in Compose? | systemd für NIO, Compose für die Dienste. Limbs brauchen den Host |
| 4 | Wohin gehen die Sicherungen? | Externer Datenträger oder verschlüsseltes Ziel. Auf derselben Platte schützen sie nicht |
