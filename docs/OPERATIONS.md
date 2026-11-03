# Betrieb

Ports, Prozesse, Umgebungsvariablen und was zu tun ist, wenn etwas nicht
antwortet.

---

## 1. Dienste und Ports

| Dienst | Port | Bindung | Start |
|---|---:|---|---|
| Next-UI (Apollo-Bühne, `/ops`) | **4001** | `0.0.0.0` | `npm run ui:dev` |
| Orchestrator-API | 4000 | `127.0.0.1` | `HOST=127.0.0.1 npm run start` (Default-Host im Code: `0.0.0.0`, ohne Auth) |
| Sigma-Worker (Trading-Limb) | **8731** | `127.0.0.1` | `trading.start` |
| Sigma-Scraper (Sidecar) | 8001 | `127.0.0.1` | im Worker erwartet, nicht gestartet |
| speaches (Spracherkennung) | 8011 | `127.0.0.1` | Docker, siehe [`SPEECH.md`](SPEECH.md) |

**Warum `0.0.0.0` für die UI:** In einer Sandbox wird die Vorschau über einen
Proxy-Host (`*.e2b.app`) ausgeliefert. Bindet der Dev-Server nur an
`127.0.0.1`, ist er von außen nicht erreichbar.

**Warum 8731 und nicht 8000:** 8000 ist der FastAPI-Default, 8001 erwartet
Sigma für den Contagion-Endpunkt. Ein eigener Port vermeidet die Kollision.

---

## 2. Schnellstart

```bash
# Abhängigkeiten (einmalig, ~12 s)
cd frontend && npm ci

# UI
cd frontend && npx next dev -H 0.0.0.0 -p 4001

# Prüfen
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:4001/
```

Für den Handelsteil zusätzlich:

```bash
python3 limbs/trading_limb.py --intent <intent-install.json>   # 32 s, 2,2 MB
python3 limbs/trading_limb.py --intent <intent-start.json>     # 2 s
```

---

## 3. Umgebungsvariablen

Es gibt **kein** `.env`-Template im Repo — Variablen werden aus der Umgebung
gelesen. Alle Secrets bleiben serverseitig.

### Marktdaten

| Variable | Wirkung ohne sie |
|---|---|
| `TVREMIX_API_KEY` | `/api/market/*` → 503, Widgets zeigen `SIM` |
| `TVREMIX_MCP_URL` | Default `https://tvremix.xyz/api/mcp/v1` |

### Sprache

| Variable | Wirkung ohne sie |
|---|---|
| `STT_ENDPOINT_URL` | Default `http://127.0.0.1:8011/v1/audio/transcriptions`, der Limb lehnt fremde Hosts ab |
| `STT_MODEL` | Default `Systran/faster-whisper-small` |
| `STT_LANGUAGE` | Default `de` |

### Freigabe-Tickets

| Variable | Wirkung |
|---|---|
| `NIO_APPROVAL_KEY` | Schlüssel für Tickets. Fehlt er, werden Operationen mit `risk` `high`, `destructive` oder `external` und jede Rechteanhebung abgelehnt |

Ein Ticket stellt der Mensch aus: `neu approve <intent.json> [--ttl-seconds N]` oder `POST /api/v1/approvals/issue` mit Operator-Token. Es gilt für genau einen Auftrag, läuft ab und wirkt nur einmal. `ticket`, `expires_at` und `approved_by: human` kommen danach in `elevation`.

Der Schlüssel darf nie in `env_allow` stehen. Setze ihn erst, wenn der Runner die Umgebung der Limbs filtert.

### Apollo-Proxy

Der Key wird über die Endpoint-URL gewählt (siehe [`API.md`](API.md)):

`OPENROUTER_API_KEY` · `GROQ_API_KEY` · `GOOGLE_API_KEY` ·
`MISTRAL_API_KEY` · `CEREBRAS_API_KEY`

### OpenManus (gesperrt)

Einrichtung und Variablen stehen in [`OPENMANUS.md`](OPENMANUS.md). `FREELLMAPI_KEY` bleibt serverseitig und erscheint in keinem Log.

### Trading-Limb (setzt der Limb selbst)

| Variable | Wert | Grund |
|---|---|---|
| `HOME`, `TMPDIR`, `XDG_CACHE_HOME` | Sandbox | sonst schreibt Sigma ins Host-Home |
| `SIGMA_DATA_DIR` | `<sandbox>/data` | DuckDB + Parquet bleiben lokal |
| `SIGMA_ALLOW_FAKE_REDIS` | `1` | kein Redis-Container nötig |
| `PYTHONUNBUFFERED` | `1` | Logs sofort sichtbar |
| `PYTHONDONTWRITEBYTECODE` | `1` | keine `__pycache__` im Clone |

### Obsidian-Vault

| Variable | Wirkung ohne sie |
|---|---|
| `NIO_OBSIDIAN_VAULT` | Default `workspace/obsidian`, siehe [`VAULT.md`](VAULT.md) |

### Qdrant (Architect-Stapel, optional)

`QDRANT_URL` · `QDRANT_API_KEY` · `QDRANT_CLUSTER_ID` ·
`QDRANT_USE_LOCAL_FALLBACK` — ohne Cloud-Zugang fällt der Client auf
`data/qdrant_db` zurück.

---

## 4. Logs und Systemereignisse

Der Orchestrator schreibt alle zentralen Ereignisse (inklusive Agenten-Starts und -Ergebnisse) in die Datei `runtime/system.log`.
- **Format:** JSON-Lines, wobei jede Zeile ein kompaktes Event ist.
- **Rotation:** Das Log rotiert automatisch nach Größe (Standard: 10 MB pro Datei). Es werden maximal 3 alte Versionen behalten (`system.log.1`, `system.log.2`, etc.). Die Rotation erfordert keine externen Abhängigkeiten oder Logrotate-Daemon.
- **Fehlertoleranz:** Schreibfehler in das Log (z. B. fehlende Rechte) brechen den Prozess nicht ab, sondern werden nur einmalig auf der Standardfehlerausgabe (`stderr`) vermerkt.
- **Sicherheit:** In Agenten-Rückgaben werden Newlines/Steuerzeichen entfernt, und konfigurierte Secrets vor dem Schreiben ins Log redigiert (`[REDACTED]`).

---

## 5. Prozessverwaltung

### Vordergrund vs. Hintergrund

Langlaufende Dienste gehören **nicht** in einen Bash-Aufruf mit Timeout,
sondern in einen eigenen Prozess. Ein Dev-Server, den man mit `ctrl-c` beendet,
hinterlässt keine Zustandsdatei — der Trading-Worker dagegen schon
(`logs/worker.pid`).

### Worker-Lebenszyklus

```
install → start → (status) → stop
```

| Operation | Dauer | Wirkung |
|---|---:|---|
| `install` | ~32 s | Clone auf Pin, venv, pip, Marker |
| `start` | ~2 s | uvicorn als Prozessgruppe, wartet auf `/api/v1/health` |
| `status` | <1 s | Health + Lake-Inventar |
| `stop` | <1 s | SIGTERM an die Gruppe, dann SIGKILL |

`start` ist idempotent: läuft der Worker schon, kommt
`{"started": false, "already_running": true}` statt eines zweiten Prozesses.

### Not-Aus

`neu stop` legt `runtime/STOP` an. Neue Läufe werden mit `E_STOPPED` abgelehnt, laufende Limbs enden samt Kindprozessen in unter 5 Sekunden, Agent-Läufe beim nächsten `status`, und der Kanban-Dispatcher nimmt nichts an und bricht aktive Aufgaben ab. Inbox-Aufträge bleiben liegen. Nur `neu resume` hebt das auf, nie der Automatismus.

### Umgebung der Limbs

Limbs erben die Host-Umgebung nicht. Sie bekommen `PATH`, `LANG`, `LC_ALL`, `TZ`, ein eigenes `HOME` und `TMPDIR` unter `workspace/limbs/<name>/` und die Namen aus ihrem `env_allow` in `limbs/registry.json`. Namen mit `KEY`, `TOKEN`, `SECRET` oder `PASSWORD` scheitern beim Laden. Die einzige Ausnahme ist `FREELLMAPI_KEY`.

### Prozessleichen finden

```bash
ps aux | grep -E "uvicorn|next" | grep -v grep
ss -ltn | grep -E "4001|8731"
```

Der Worker läuft in einer **eigenen Sitzung** — `kill <pid>` beendet nur den
Elternprozess, uvicorn-Kinder überleben. Deshalb beendet `trading.stop` die
Gruppe mit `os.killpg`.

---

## 6. Sandbox-Zustand

In dieser Umgebung wird der Workspace zwischen Sitzungen teilweise
zurückgesetzt:

| Was | Überlebt? |
|---|---|
| Dateien im Repo (committet) | **ja** |
| Dateien im Repo (uncommitted) | meist ja, aber prüfen |
| `frontend/node_modules` | **nein** — `npm ci` erneut |
| `frontend/.next` | **nein** — Build-Cache weg |
| Laufende Prozesse | **nein** |
| `workspace/sigma` (Trading-Install) | meist ja, sonst `install` erneut |

**Konsequenz:** Nach einem Reset kostet der Start ~12 s (`npm ci`) plus
Serverstart. Der Code ist nie betroffen; nur die laufende Instanz.

Ein `git status` nach dem Aufwachen zeigt manchmal einen alten HEAD, während
die Arbeit im Remote liegt. Vor jedem Merge lohnt der Hash-Vergleich:

```bash
git fetch -q origin <branch>
git diff --stat FETCH_HEAD          # leer = identisch
```

---

## 7. Troubleshooting

| Symptom | Wahrscheinliche Ursache | Prüfung / Abhilfe |
|---|---|---|
| UI lädt, aber nichts reagiert | Client-Chunks abgelehnt (Origin) | `allowedDevOrigins` muss `*.e2b.app` enthalten |
| `next: command not found` | `node_modules` fehlt | `cd frontend && npm ci` |
| Alle Widgets `SIM`, Konsole 503 | `TVREMIX_API_KEY` fehlt | Key setzen — kein Bug |
| Telemetrie dauerhaft `STALE` | Python-Produzent läuft nicht | `runtime/telemetry.sock` prüfen |
| Hydration-Mismatch in der Konsole | Server- und Client-Render verschieden | einen `data-layout`-/Größen-Fallback prüfen |
| Deck reagiert nicht auf Klick außerhalb | Backdrop-Handler liegt am falschen Element | Handler am Scrim, `stopPropagation` am Panel |
| Tab verlässt das Deck | Fokus blieb auf dem Trigger | Fokus beim Öffnen in den Dialog setzen |
| Ring überlappt bei `/spawn` | Ellipse nicht nachgeführt | `fitEllipse` + Board-Fallback (siehe [`APOLLO-CORE.md`](APOLLO-CORE.md)) |
| `libnspr4.so: cannot open shared object file` | Chromium ohne NSS | `LD_LIBRARY_PATH` auf die mitgelieferten Libs setzen |
| `upload-pack: not our ref` | `.git` eines Clones fehlt | Limb baut neu auf; Installation löschen |

---

## 8. Health-Checks

```bash
curl -s http://127.0.0.1:4001/            | head -c 100   # UI
curl -s http://127.0.0.1:8731/api/v1/health                 # Trading-Worker
curl -s -o /dev/null -w "%{http_code}\n" \
     http://127.0.0.1:4001/api/market/ohlcv?symbol=BINANCE:BTCUSDT
```

| Antwort | Bedeutung |
|---|---|
| `200` + Daten | Feed gesund |
| `503 TVREMIX_API_KEY not configured` | erwartet ohne Key |
| `502` | Upstream-Problem (Netz oder Limit) |
| `000` | Dienst läuft nicht |

---

## 9. Sicherheitsmodell in Kurzform

| Fläche | Schutz |
|---|---|
| LLM-Proxy | Key nur serverseitig; 200 nur bei echter Completion |
| Sandbox-Kommando | Allowlist, keine Shell, Jail, 5 s, 8 KiB |
| Marktdaten | Key serverseitig; Adapter statt Durchreich |
| Trading-Limb | Pin auf Commit, Sandbox-Home, eigene Prozessgruppe, nur eine Operation mit Netz |
| Orbit/Graph | keine Nutzereingabe wird ausgeführt |

## Agenten-Netzwerk und Egress-Proxy

### Architektur
Agenten-Container laufen isoliert und können nicht direkt auf das Internet oder das Host-Netzwerk zugreifen. Sie sind mit dem internen Docker-Netzwerk `nio-agents` verbunden. Ausgehende Verbindungen erfolgen ausschließlich über den `egress-proxy`, der im Container `nio-egress-proxy` betrieben werden kann, oder sie beschränken sich nur auf das Erreichen des internen FreeLLMAPI-Containers, der in dasselbe Netzwerk verbunden wird.

### Setup prüfen
1. Das Netzwerk muss existieren und isoliert sein:
   ```bash
   docker network inspect nio-agents
   ```
   Achten Sie darauf, dass `Internal` auf `true` steht und in `Options` `com.docker.network.bridge.inhibit_ipv4` aktiviert ist.
2. Das Setup-Skript ist idempotent und kann jederzeit ausgeführt werden, um das Netzwerk anzulegen und den FreeLLMAPI-Container (`freellmapi-freellmapi-1`) zu verbinden:
   ```bash
   bash scripts/agents_network.sh
   ```

### Proxy Logs
Wenn der Proxy aktiv ist, protokolliert er jede CONNECT-Entscheidung auf Stdout, ohne Header oder Body-Inhalte mitzuschneiden. Alle Loopback-, Link-Local- und privaten IPs sind hardcodiert gesperrt.
