# HTTP-API

Alle Routen liegen unter `frontend/src/app/api/`. Alle Endpunkte nutzen
`runtime = "nodejs"` und `dynamic = "force-dynamic"`.

| Route | Methode | Zweck | Geheimnis nötig |
|---|---|---|---|
| `/api/apollo` | GET, POST | Providerstatus / echte Completion | ja, serverseitig für Completion |
| `/api/apollo/providers` | GET, POST | Status lesen / explizite Mini-Completion-Probes | ja für Probes |
| `/api/apollo/transcribe` | GET, POST | Sprachstatus und Diktat über lokales speaches, 503 bei Ausfall ([`SPEECH.md`](SPEECH.md)) | nein |
| `/api/market/[tool]` | GET | Marktdaten über tvremix MCP | ja, serverseitig |
| `/api/sandbox` | POST | read-only Shell-Allowlist | nein |
| `/api/apollo/vault` | POST | Notizen ablegen und suchen über den Vault-Limb ([`VAULT.md`](VAULT.md)) | nein |
| `/api/telemetry/stream` | GET | SSE der Python-Engine | nein |

**Grundregel:** Kein API-Key erreicht je den Browser. Der Client spricht nur
diese Routen an; die Routen sprechen die Außenwelt.

---

## 1. `POST /api/apollo`

Serverseitige Providerauswahl und Secret-Anbindung, ohne simulierten Fallback.
Beispiel (nur Provider-ID, niemals Key):

```json
{
  "providerId": "groq",
  "messages": [{ "role": "user", "content": "Reply with OK." }],
  "temperature": 0,
  "maxTokens": 16
}
```

Ohne `providerId` wählt der Server `NIO_LLM_PROVIDER` bzw. den ersten
konfigurierten Registry-Eintrag. Legacy-`endpointUrl` wird nur für exakt erlaubte
Hosts akzeptiert; keine Substring-Matches. Credentials und Modellkonfiguration
werden serverseitig aus Umgebung oder owner-only `NIO_SECRET_FILE` geladen.
Die gemeinsame Registry ist `orchestrator/provider_catalog.json`.

Limits: 512.000 Body-Zeichen, 24 Nachrichten, 24.000 Zeichen je Nachricht,
16–4096 Output-Tokens (Default 256), 20 Sekunden Timeout, keine Redirects.
OpenAI-kompatible, native Anthropic- und Cohere-Antworten werden validiert.

Erfolg: HTTP 200 mit `{ok:true,text,provider,model,latencyMs}`. Fehlende
Konfiguration/Secrets: 503. Auth-/Quota-/Upstream-/Netzwerkfehler und ungültige
Completions: 502 mit festem Fehlercode; Timeout: 504. Upstream-Fehlertexte werden
nicht roh zurückgegeben. **Kein Fehler wird durch Simulation ersetzt.**

`GET /api/apollo` sowie `GET /api/apollo/providers` liefern nur Statusmetadaten.
`configured` ist Credential-Präsenz, `ready` erfordert eine echte Completion
(höchstens fünf Minuten gültig, bei Rotation ungültig). `POST
/api/apollo/providers` startet explizit einen echten 16-Token-Test pro
konfiguriertem Provider mit Modell; keine automatische Probe bei GET.

Tatsächlicher Stand, offene Blocker, Secret-Setup und Testbelege:
[`LIVE-PROVIDER-AUDIT-2026-11-03.md`](LIVE-PROVIDER-AUDIT-2026-11-03.md).

---

## 2. `GET /api/market/[tool]`

Vollständige Beschreibung der Datenformen: [`DATA-FLOW.md`](DATA-FLOW.md).

### Query-Parameter

| Parameter | Default | Gilt für |
|---|---|---|
| `symbol` | `BINANCE:BTCUSDT` | `quote`, `ohlcv`, `technicals`, `news` |
| `symbols` | erste 12 der Watchlist | `quotes` |
| `interval` | `"60"` (Minuten, String) | `ohlcv`, `technicals` |
| `limit` | `100` | `ohlcv` |

`market: "crypto"` ist in allen Pfaden fest verdrahtet.

### Tools

| `tool` | Antwort in `data` |
|---|---|
| `quote` | `{ symbol, name, price, changePct, decimals }` |
| `quotes` | `{ byBase: { BTC: { price, changePct } } }` |
| `ohlcv` | `{ spark, price, changePct }` |
| `technicals` | `LiveTechnical` |
| `news` | Adapter-Objekt |
| `screener` | Kandidatenliste |
| `tools` | `{ tools: […] }` (MCP-Tool-Liste) |
| *beliebig* | roher `callTool`-Durchreich |

### Umschlag und Fehler

```jsonc
{ "ok": true,  "source": "tvremix", "data": { … } }
{ "ok": false, "source": "error",   "error": "…" }
```

| Status | `error` | Ursache |
|---|---|---|
| 503 | `TVREMIX_API_KEY not configured` | Key fehlt |
| 429 | `Rate limited: …` | MCP-Limit |
| 401/403 | `Auth failed: …` | Key ungültig |
| 502 | `Quote shape not recognized` | Adapter fand keinen Preis |
| 502 | `OHLCV shape not recognized` | < 5 Balken oder kein Close |
| 502 | `No live quotes returned` | alle Einzelquotes scheiterten |
| 502 | `Unparseable MCP response` | Antwort weder JSON noch SSE |

---

## 3. `POST /api/sandbox`

Führt ein Kommando aus einer **festen Allowlist** aus. Kein Shell, keine
Pipes, keine Umleitung.

### Allowlist

```
pwd  ls  cat  echo  date  whoami  head  wc  uname
```

### Request

```json
{ "command": "ls" }
```

### Verhalten

| Eigenschaft | Wert |
|---|---|
| Jail | `<system tmp>/nio-sandbox` |
| Timeout | **5 000 ms** |
| Ausgabe | maximal **8 KiB** |
| Shell-Metazeichen | `;`, `|`, `&` → **400** |
| Nicht in Allowlist | `rm`, `curl`, … → **127** |
| `..` oder absolute Pfade | abgewiesen |

Fehlerantworten enthalten einen `hint`, damit das Apollo-Terminal ihn
einklappbar anzeigen kann.

### Warum das sicher ist

Ein Kommando **aus** einer Allowlist bekommt kein Shell-String-Interpolat.
Argumente sind eine Liste; der Prozess läuft im Jail mit gesetztem Timeout.
`/sandbox exec` ist damit ein Diagnosewerkzeug, kein Zugang.

---

## 4. `GET /api/telemetry/stream`

Server-Sent Events. Details zum Format: [`DATA-FLOW.md`](DATA-FLOW.md).

```http
Content-Type: text/event-stream; charset=utf-8
Cache-Control: no-cache, no-transform
Connection: keep-alive
X-Accel-Buffering: no
```

| Event | Wann | Inhalt |
|---|---|---|
| `hello` | einmal beim Verbinden | `state`, `lastAgeMs`, `producerRunning`, `consumerRunning`, `socket`, `logs[8]` |
| `telemetry` | je Datensatz | `{ kind, symbol, clock_s, payload }` |
| `ping` | alle 15 s | `{ state, at }` |

`maxDuration = 300` verhindert, dass ein Proxy den Strom in einen Stillstand
puffert. Beim Abort des Clients werden Intervall und Subscription freigegeben.

---

## 5. Alle Routen auf einen Blick

| Route | Typ im Build | Auth | Fail-closed |
|---|---|---|---|
| `/` | ○ statisch | — | — |
| `/apollo` | ○ statisch | — | — |
| `/ops` | ○ statisch | — | — |
| `/api/apollo` | ƒ dynamisch | serverseitiger Key | ja |
| `/api/apollo/transcribe` | ƒ dynamisch | Endpoint nur aus der Server-Umgebung | ja |
| `/api/market/[tool]` | ƒ dynamisch | serverseitiger Key | ja |
| `/api/sandbox` | ƒ dynamisch | Allowlist | ja |
| `/api/apollo/vault` | ƒ dynamisch | nur JSON, Aktionen `search` und `capture` | ja |
| `/api/telemetry/stream` | ƒ dynamisch | — | ja (Validierung) |
