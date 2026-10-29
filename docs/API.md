# HTTP-API

Alle Routen liegen unter `frontend/src/app/api/`. Vier Endpunkte, alle
`runtime = "nodejs"` und `dynamic = "force-dynamic"`.

| Route | Methode | Zweck | Geheimnis nötig |
|---|---|---|---|
| `/api/apollo` | POST | LLM-Proxy (FreeLLMAPI) | ja, serverseitig |
| `/api/market/[tool]` | GET | Marktdaten über den offiziellen TradingView-MCP | OAuth, serverseitig |
| `/api/sandbox` | POST | read-only Shell-Allowlist | nein |
| `/api/telemetry/stream` | GET | SSE der Python-Engine | nein |

**Grundregel:** Kein API-Key erreicht je den Browser. Der Client spricht nur
diese Routen an; die Routen sprechen die Außenwelt.

---

## 1. `POST /api/apollo`

OpenAI-kompatibler Proxy. Der Client schickt Endpoint und Nachrichten, der
Server setzt den passenden Key aus der Umgebung.

### Request

```jsonc
{
  "endpointUrl": "https://api.groq.com/openai/v1/chat/completions",
  "model": "gpt-4o-mini",
  "messages": [{ "role": "user", "content": "…" }],
  "temperature": 0.4,
  "maxTokens": 1024
}
```

Key-Zuordnung über die Endpoint-URL — der erste Treffer gewinnt:

| Muster | Variable |
|---|---|
| `/openrouter/i` | `OPENROUTER_API_KEY` |
| `/groq/i` | `GROQ_API_KEY` |
| `/googleapis\|generativelanguage/i` | `GOOGLE_API_KEY` |
| `/mistral/i` | `MISTRAL_API_KEY` |
| `/cerebras/i` | `CEREBRAS_API_KEY` |

### Grenzen

| Grenze | Wert |
|---|---|
| Body | **512 000 B** (`MAX_BODY`) |
| Nachrichten | **24** (`MAX_MESSAGES`) |
| Zeichen pro Nachricht | 24 000 |
| `maxTokens` | 16 … 4096, Default 1024 |
| `temperature` | 0 … 2, Default 0.4 |
| Timeout | **20 000 ms**, danach 504 |

Nachrichten mit unbekannter `role` oder nicht-string `content` werden
**übersprungen**, nicht als Fehler behandelt.

### Antworten

Erfolg `200`:

```json
{ "ok": true, "text": "…", "provider": "groq", "model": "…", "latencyMs": 412 }
```

`text` ist auf 12 000 Zeichen geschnitten.

| Status | `error` | Bedeutung |
|---|---|---|
| 400 | `no_endpoint` | `endpointUrl` fehlt/leer |
| 400 | `invalid JSON body` | Body nicht parsebar |
| 400 | `payload too large` | > 512 KB |
| 400 | Scheme/`messages`-Fehler | Endpoint nicht `https?` oder keine Nachrichten |
| 502 | `upstream HTTP <code>` | Upstream antwortete mit Fehlerstatus |
| 502 | `empty_upstream_response` | Upstream gab leeren Text |
| 502 | `upstream_not_json` | Antwort war kein JSON |
| 502 | `upstream_not_openai_compatible` | JSON, aber keine Completion-Struktur |
| 504 | Timeout | nach 20 s |

**Fail-closed:** Ein 200 wird nur zurückgegeben, wenn die Antwort tatsächlich
als OpenAI-Completion geparst wurde. Eine 200 mit fremdem Body wird zu 502 —
sonst würde Müll als Modellantwort im Terminal landen.

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
{ "ok": true,  "source": "tradingview", "data": { … } }
{ "ok": false, "source": "error",   "error": "…" }
```

| Status | `error` | Ursache |
|---|---|---|
| 503 | `TradingView not connected — …` | kein OAuth-Login (`/api/market/oauth/start`) |
| 429 | `Rate limited: …` | MCP-Limit |
| 401 | `TradingView session expired — …` | Refresh abgelehnt, neu anmelden |
| 403 | `Tool … is not a read-only TradingView tool` | Durchreich auf ein Schreib-Tool |
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
| `/api/market/[tool]` | ƒ dynamisch | serverseitiger Key | ja |
| `/api/sandbox` | ƒ dynamisch | Allowlist | ja |
| `/api/telemetry/stream` | ƒ dynamisch | — | ja (Validierung) |
