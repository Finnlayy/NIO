# Datenfluss: Marktdaten und Telemetrie

Zwei **unabhängige** Feeds speisen das Frontend. Sie sind absichtlich getrennt:
ein toter Feed darf nie durch einen gesunden maskiert werden — jedes Widget
zeigt sein eigenes Badge.

```
tvremix MCP  ──►  /api/market/[tool]  ──►  useMarketData()  ──►  SVG-Widgets
(Preise)          (Adapter, TTL)            (Merge mit Sim)

Python-Engine ──►  runtime/telemetry.sock ──► /api/telemetry/stream ──► SSE
(Orderflow,         (UDS-Event-Bus)             (text/event-stream)
 Regime)
```

---

## 1. Preisdaten: tvremix MCP

### Transport

Die Route spricht **serverseitig** JSON-RPC 2.0 über „Streamable HTTP". Der
API-Key verlässt den Server nie.

```http
POST https://tvremix.xyz/api/mcp/v1
Authorization: Bearer $TVREMIX_API_KEY
Accept: application/json, text/event-stream
Mcp-Session-Id: <vom Server zurückgegeben>
Content-Type: application/json

{"jsonrpc":"2.0","id":12345,"method":"tools/call","params":{"name":"get_ohlcv","arguments":{…}}}
```

Zwei Eigenheiten, die der Client abfängt (`src/server/tvremix/client.ts`):

1. **Die Antwort darf SSE sein.** `parseMcpBody()` akzeptiert sowohl reines
   JSON als auch `data:`-Zeilen (Streamable-HTTP erlaubt beides).
2. **Die Argumentnamen sind nicht fest.** `smartCall()`
   (`server/tvremix/args.ts`) liest das `inputSchema` des Tools und bildet die
   kanonischen Parameter auf die tatsächlich deklarierten ab:

   | kanonisch | akzeptierte Server-Namen (Regex) |
   |---|---|
   | `symbol` | `symbol`, `ticker`, `instrument`, `pair`, `security`, `s` |
   | `interval` | `interval`, `timeframe`, `resolution`, `period`, `tf`, `barsize` |
   | `limit` | `limit`, `bars`, `count`, `n`, `maxbars`, `rows`, `quantity` |
   | `market` | `market`, `assetclass`, `asset_class`, `type`, `exchange`, `universe` |

### Rohe Antwort ist untypisiert

Der Adapter (`server/tvremix/adapters.ts`) probiert mehrere Feldnamen, weil die
Upstream-Form nicht garantiert ist:

```ts
raw.bars ?? raw.ohlcv ?? raw.candles ?? raw.data ?? raw      // Balkenliste
bar.close ?? bar.c ?? bar.closePrice ?? bar.price             // Schlusskurs
```

### Was beim Browser ankommt

Jede Route liefert denselben Umschlag:

```jsonc
{ "ok": true,  "source": "tvremix", "data": { … } }
{ "ok": false, "source": "error",   "error": "TVREMIX_API_KEY not configured" }
```

| Route | `data` |
|---|---|
| `quote` | `{ symbol, name, price, changePct, decimals }` |
| `quotes` | `{ byBase: { BTC: { price, changePct }, … } }` |
| `ohlcv` | `{ spark: number[], price: number, changePct: number }` |
| `technicals` | `LiveTechnical` (score, verdict, sell/neutral/buy, rsi, macd, sma50, sma200, Labels) |
| `news` | Adapter-Objekte für die Sentiment-Liste |
| `screener` | sortierte Kandidatenliste |
| alles andere | roher Durchreich (`callTool`) |

**Wichtig — es gibt keine Candles.** `adaptOhlcv()` behält ausschließlich
Schlusskurse und normalisiert sie:

| Feld | Herleitung |
|---|---|
| `spark` | `(c − min) / (max − min)` → **0..1** |
| `price` | letzter Schlusskurs (absolut) |
| `changePct` | `(last − first) / first × 100` |

Open, High, Low, Volumen und Zeitstempel werden **verworfen**. Unter 5 Balken
gibt es `502 OHLCV shape not recognized` statt einer halben Antwort.

### Server-Cache

Damit die 20/min · 200/h · 1500/Tag-Limits des MCP halten, cached die Route
pro Tool:

| Tool | TTL |
|---|---|
| `quote` | 90 s |
| `ohlcv` | 120 s |
| `technicals` | 180 s |
| `news`, `screener` | 300 s |

`quotes` fächert auf und cached **pro Symbol** — gecachte Ticks berühren das
MCP nicht, sonst würde die Breadth-Radar die Limits sprengen.

### Client: Merge statt Ersetzen

`useMarketData<T>()` (`ops/hooks/useMarketData.ts`) startet mit einem
synthetischen Baseline-Objekt und **merged** Live-Felder darüber:

```ts
setState({ data: mergeDeep(fallbackRef.current, json.data) as T, source: "live" })
```

Dadurch bleiben Sim-only-Felder (z. B. `venue`, `tfStats`) erhalten, auch wenn
der Live-Feed sie nicht liefert. Bei Fehler oder `ok: false` bleibt der
Baseline stehen und `source` wird `"sim"`. Das Widget zeigt das Badge; es gibt
**keine stillen Nullen**.

### Fallback-Daten

`ops/marketData.ts` hält `Ticker { symbol, name, price, changePct, decimals }`
und `sparklineFor(symbol, points = 48)` — ein deterministischer Pseudozufalls-
Walk (`seededRandom`), geklemmt auf `0.02…0.98`. Gleicher Symbolname ⇒ gleiche
Kurve, auch nach Reload.

---

## 2. Telemetrie: SSE über UDS

Der Browser kann keinen `AF_UNIX`-Socket öffnen. Deshalb ist
`src/server/telemetryBridge.ts` der **einzige** Konsument von
`runtime/telemetry.sock` und `GET /api/telemetry/stream` publiziert weiter.

### Wire-Format

`Content-Type: text/event-stream; charset=utf-8`, `Cache-Control: no-cache,
no-transform`, `X-Accel-Buffering: no`.

```
event: hello
data: {"state":"stale","lastAgeMs":null,"producerRunning":false,
       "consumerRunning":false,"socket":"/runtime/telemetry.sock","logs":[]}

event: telemetry
data: {"kind":"gravity_tick","symbol":"BTCUSDT","clock_s":1730000000,"payload":{…}}

event: ping
data: {"state":"stale","at":1793000000000}
```

`hello` kommt einmal beim Verbinden (enthält die letzten 8 Logzeilen),
`telemetry` bei jedem Datensatz (der Ringpuffer wird zuerst nachgespielt),
`ping` alle **15 s** als Keepalive.

### Drei Datensatz-Typen

Der Python-Produzent emittiert `event_kind`; die Bridge normalisiert auf `kind`.

| `kind` | `payload` — alle Werte endliche Zahlen |
|---|---|
| `microstructure_tick` | `imbalance_ratio`, `depth_2pct`, `footprint_delta: number[]` (12 Bins → CVD-Heatmap) |
| `gravity_tick` | `l2_depth`, `l3_iceberg`, `polymarket_prob`, `v_total` |
| `regime_tick` | `cluster_id`, `confidence`, `is_forbidden_zone` (**0/1 als Zahl**, kein Boolean) |

### Fail-closed auf beiden Seiten

**Server:** `parseTelemetryLine()` validiert jeden Datensatz gegen den Vertrag.
Ein fehlendes Feld ⇒ Zeile wird verworfen, sie erreicht nie ein Widget.

**Client:** `parseTelemetryRecord()` prüft erneut (ein Proxy könnte Unsinn
durchlassen). Der Zustandsautomat in `nextFeedConnection()`:

| Zustand | Bedeutung |
|---|---|
| `DISCONNECTED` | Transport tot |
| `STALE_CACHE_DEGRADED` | Transport lebt, aber **> 3 s** kein Tick (`STALE_AFTER_MS`) |
| `CONNECTED_LIVE` | Tick innerhalb des Fensters |

Widgets zeigen Werte **nur** bei `CONNECTED_LIVE`. Der Snapshot wird bei einem
Abbruch nie geleert — alte Werte bleiben lesbar, aber als degradiert markiert.

Reconnects laufen mit exponentiellem Backoff (`MAX_BACKOFF_MS`,
`backoffDelayMs`); alle Timer und der `EventSource` werden im Effect-Cleanup
freigegeben, späte Callbacks über ein `stale`-Flag verworfen.

---

## 3. Speicherformate — was wohin gehört

Gemessen an der tatsächlichen Form (`t, symbol, o, h, l, c, v`), nicht geschätzt:

| Zeilen | JSON (MCP-Stil) | JSON flach | CSV | TOON | Parquet snappy | Parquet zstd |
|---:|---:|---:|---:|---:|---:|---:|
| 80 (1 Chart) | 8 985 B | 5 845 B | 4 924 B | 5 094 B | 5 083 B | **4 972 B** |
| 1 440 (1 Tag @1m) | 161 646 B | 104 106 B | 88 225 B | 91 117 B | 53 554 B | **42 368 B** |
| 43 200 (30 Tage) | 4 849 628 B | 3 121 688 B | 2 646 447 B | 2 732 860 B | 1 595 270 B | **1 398 822 B** |

**Parquet + zstd ist ~3,5× kleiner als JSON und ~1,9× kleiner als CSV.**
DuckDB liest es ohne Server: voller Scan über 30 Tage plus stündliche
OHLC-Aggregation in **34 ms**.

### Wann welches Format

| Zweck | Format | Begründung |
|---|---|---|
| Leitung zum Browser | JSON (`spark`, `price`, `changePct`) | klein genug, direkt renderbar |
| Archiv / Lake | **Parquet + zstd** | kolumnar, komprimiert, prädikatgepusht |
| Ad-hoc-Abfrage | **DuckDB über Parquet** | eingebettet, kein Dienst, 34 ms |
| Mensch / Excel | **CSV** | überall lesbar |
| **An ein Modell füttern** | **TOON** | ~40–60 % weniger Tokens als JSON |

### Warum TOON *nicht* für Candles

Die TOON-Spezifikation sagt es selbst: *„Data is purely tabular — CSV is
smaller. TOON's ~5–10 % overhead buys declared lengths, field lists and
delimiter scoping, which is a reliability trade, not a size one."* Die Messung
bestätigt das (2,73 MB vs. 2,65 MB CSV).

TOON (Tabular-Form, §9.3) sieht so aus:

```
bars[3]{t,symbol,o,h,l,c,v}:
  1730000000,BTCUSDT,77400.0,77460.2,77380.1,77440.9,12.4
  1730000060,BTCUSDT,77440.9,77512.0,77420.5,77498.3,9.1
```

Sein Nutzen liegt im **Kontextfenster**, nicht auf der Platte.

### Warum Qdrant hier nicht hingehört

Qdrant ist eine Vektordatenbank — ihre Stärke ist semantische Ähnlichkeit. Die
Identität einer Candle *sind ihre Zahlen*; es gibt nichts zu embedden. Ein
Embedding einer OHLC-Zeile wäre eine teure, verlustbehaftete Kopie derselben
Zahl.

Qdrant bleibt richtig für **News, Sentiment und Gedächtnis-Erinnerung** — dort
existiert bereits `Architect/limbs/intelligence/qdrant_memory_engine.py`
(Cloud mit lokalem Fallback auf `data/qdrant_db`).

Eine sinnvolle spätere Erweiterung wäre **Regime-Embeddings**: aus gleitenden
Fenstern Vektoren über Volatilität und Flow-Form bilden, um „zeig mir ähnliche
frühere Setups" zu beantworten. Das ist eine eigene Funktion, kein
Speicherformat — und bewusst nicht Teil des Trading-Limbs.

---

## 4. Bekannte Fehlerbilder

| Symptom | Ursache | Abhilfe |
|---|---|---|
| Alle Widgets zeigen `SIM` | `TVREMIX_API_KEY` fehlt | Key setzen; MCP-Limits beachten |
| `503 TVREMIX_API_KEY not configured` | erwartet ohne Key | fail-closed, kein Bug |
| `502 No live quotes returned` | alle Einzelquotes scheiterten | Netz oder Limit prüfen |
| `502 upstream_not_openai_compatible` (Apollo) | Endpoint antwortet, aber nicht als OpenAI-Completion | Endpoint-URL prüfen |
| Telemetrie dauerhaft `stale` | Produzent läuft nicht | `Architect/limbs/telemetry_feed.py` starten |
| CVD-Heatmap zeigt Template | `connection !== CONNECTED_LIVE` | wie oben; bewusst fail-closed |
