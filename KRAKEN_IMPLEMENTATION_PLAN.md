# Kraken Implementation Plan — NIO (ALPHA) ↔ kraken-cli

> **Status:** REV 3 — P0a DONE (source ground truth v0.4.1, 2026-09-13).
> P0b (binary verification on target box) pending — script ready.
> **Normative Quellen:**
> (a) Ciel-Direktive "ARCHITEKTUR-REPARATUR" (§1),
> (b) Ciel "ANTWORTEN ZU DEN 5 ARCHITEKTUR-FRAGEN" (§1b, mit P0a-Befund je Punkt),
> (c) kraken-cli v0.4.1 Quelle (clap-derive, maßgeblich bei Syntax-Widerspruch).
> **Repo context:** `BLUEPRINT-SIGMA.md` (§4.3, §17.3, §20, §21, §23, §32, §33, §36),
> `GLINT-POLYMARKET-WIRING.md`, `Architect/core/config.py`
> **Artefakte:** `tests/fixtures/kraken_cli/kraken-cli-0.4.1.source.json` (P0a),
> `scripts/kraken_p0_verify.sh` (P0b).

---

## 1. Directive (Ciel — Architektur-Reparatur, maßgeblich)

**Kernproblem:** Bisher hat die KI redundanten Broker-Code neu geschrieben.
Das lief an der fertigen `kraken-cli` vorbei und erzeugte Fehler.

**Reparatur (verbindlich):**

- **NIO schreibt KEINEN Broker-Code mehr selbst.**
- **NIO sendet nur Signale an die `kraken-cli` via Subprocess.**
- Sizing/Risk (Kelly, M8/Judge, Brackets, Deadman-Puls, Exchange-Clock) bleibt lokal —
  aber **Ausführung = ausschließlich `kraken` Subprocess mit JSON-Output**.
- Jeder Order-Pfad, der an der CLI vorbei direkt gegen REST/FIX handelt, ist ein
  Architekturverstoß. P0a-Befund: **keine Ausnahme nötig** — `server-time`,
  L2/L3-Books und WS-Streams liefert die CLI selbst (§3).

## 1b. Ciel-Antworten (5 Fragen) + P0a-Befund je Punkt

Quellbelege: `kraken-cli-0.4.1/src/…` (Datei:Zeile). ✅ = bestätigt, ❌ = widerlegt,
⚠️ = teilweise/deviant.

### Frage 1 — Syntax: ✅ Prinzip, ❌ konkretes Profil

- Ciel: Dual-Format-`KrakenCliWrapper`, Standard = Top-Level
  (`kraken buy/sell/cancel/cancel-after … -o json`).
- **P0a: Top-Level-Orders existieren NICHT.** Belegt: `src/commands/mod.rs`
  (`Order(OrderCommand)` als Subcommand), `src/commands/trade.rs:18`
  (`OrderCommand::{Buy,Sell,Batch,Amend,Edit,Cancel,CancelBatch,CancelAll,CancelAfter}`),
  kein Alias `buy/sell/trade` im gesamten Command-Tree.
- **Folge:** Wrapper-Prinzip bleibt (richtig + versionssicher), aber das
  **verifizierte Default-Profil ist `order-namespace`** (§4). `top-level` wird
  als inaktives Forward-Compat-Profil mitgeführt.

### Frage 2 — Schnittstellen-Volltext: ✅ großteils, 4 Korrekturen

- **[A] Marktdaten ✅** (alle Top-Level, `market.rs:16`): `ticker`, `ohlc`,
  `orderbook`, `trades`, dazu `status`, `server-time` (!), `assets`, `pairs`.
  Korrekturen: **`spreads` (Plural**, Ciel: `spread`); **Orderbook-Tiefe heißt
  `--count`** (Default 25, max 500 — Ciel: `--depth N`); `trades --since` ✅.
- **[B] Account ✅** (`account.rs:23`, Top-Level): `balance`, `trade-balance`,
  `open-orders`, `closed-orders`, `ledgers`, dazu `extended-balance`,
  **`orderbook-l3`** (authentisiertes L3-Book — Glint-relevant), `positions`,
  `trades-history`, `volume`, Export-Reports. Korrektur: `ledgers` filtert via
  `--asset/--type/Pagination`, **kein direktes `--since`**.
- **[C] WebSocket ❌ Syntax.** Real (`ws/mod.rs:52`, `ws/channels.rs`):
  `kraken ws <channel>` — **kein `subscribe`-Verb**. Kanäle: `ticker`,
  `trades`, `book` (`--depth 10|25|100|500|1000`), `ohlc`, `instrument`,
  `executions` (= Fills + Order-Status, auth), `balances` (auth),
  `level3` (auth). **Kein `--token`-Flag** — Auth-Channels nutzen konfigurierte
  Credentials. Bonus: One-Shot-Methoden `ws add-order/amend-order/cancel-order/
  cancel-all/cancel-after/batch-add/batch-cancel/ping` (Alternative, nicht Standard).
- **[D] Paper ✅ Prinzip, Präzisierung:** Ciel (lokaler NIO-Simulator) bleibt
  kanonisch für deterministische Fills — aber die CLI hat **eigene Paper-Engines**:
  `kraken paper …` (Spot, `paper.rs:25`) und **`kraken futures paper …`
  (Futures, `futures_paper.rs:20`)**. Beide sind zulässige Engine-Profile hinter
  derselben Simulator-Schnittstelle (§3.3).

### Frage 3 — Futures-Paper: ⚠️ Sandbox-Flag existiert NICHT

- Ciel: `--sandbox`/`--demo` leitet auf Demo um. **P0a: kein solcher Flag,
  keine demo-URL in der Quelle** (grep über `src/` + `crates/` negativ).
- **Realer Mechanismus:** `--futures-url` / `KRAKEN_FUTURES_URL` (`cli.rs`)
  als Base-URL-Override (+ `--danger-allow-any-url-host` falls Host-Prüfung
  greift). Demo-Verhalten damit auf der Zielbox in P0b zu beweisen.
- Ciel-Entscheid "ohne Demo-Keys lokal simulieren" bleibt gültig und wird
  durch `kraken futures paper` als zweite Option ergänzt.

### Frage 4 — Bracket-Flags: ✅ VOLL BESTÄTIGT

- `OrderRequest` (`trade.rs:55`): `--close-ordertype`, `--close-price`,
  **`--close-price2`** — native Bracket-Pflicht (§20) direkt abbildbar,
  keine OCO-Notlösung nötig (OCO bleibt Fallback für Futures-Live:
  Futures-`OrderRequest` hat kein close-Flag → dort `--stop-price`/
  `--trigger-signal` + Reduce-Only-Folgeorder, §3.1).

### Frage 5 — FIX & Staking: ✅ Prinzip, ❌ Earn-Verben

- FIX out of scope ✅ (kein FIX-Pfad in der CLI-Quelle; WS v2 ist der
  Echtzeit-Pfad). `KRAKEN_ENABLE_FIX` bleibt Jules-only.
- Staking-Hintergrund-Job ✅ — aber: **`kraken earn stake/unstake`
  existiert NICHT.** Real (`earn.rs:14`): `allocate / deallocate /
  allocate-status / deallocate-status / strategies / allocations`
  mit `<STRATEGY_ID> <AMOUNT>`.

---

## 2. Verifizierte Befehlsmatrix (v0.4.1 Quelle — maßgeblich)

Vollständige Tabelle: `tests/fixtures/kraken_cli/kraken-cli-0.4.1.source.json`.
Globale Flags (`cli.rs:531`): `-o/--output table|json`, `-v`, `--api-url`
(`KRAKEN_SPOT_URL`), `--futures-url` (`KRAKEN_FUTURES_URL`), 4× WS-URL-Overrides,
`--api-key/--api-secret[-stdin/-file]`, Spot/Futures-Key-Envs, `--otp`,
`--workspace`, `--yes`. Exit-Codes: **0 ok / 1 Fehler / 2 clap-Parsefehler**
(`main.rs`).

| Absicht | Verifiziert (v0.4.1) | Ciel-Aussage | BLUEPRINT (STALE → P7) |
|---|---|---|---|
| Spot-Order | `kraken order buy\|sell <PAIR> <VOL> [--type …] [--price P] … -o json` | `kraken buy\|sell …` ❌ | `kraken trade add-order …` ❌ |
| Bracket | `--close-ordertype/--close-price[--close-price2]` ✅ | ✅ | `--close-*` ✅ (Glück gehabt) |
| Cancel | `kraken order cancel <TXID…> [--cl-ord-id]` | `kraken cancel --txid` ❌ Form | — |
| Cancel alle | `kraken order cancel-all` | ✅ (Namespace ❌) | `cancel_all` ✅ |
| Dead-Man | `kraken order cancel-after <SECS>` (0 = aus) | `kraken cancel-after` ❌ Namespace | 1800 s ✅ |
| Batch | `kraken order batch <JSON_FILE> [--pair] [--deadline] [--validate]` | `kraken batch` ❌ Namespace | — |
| Amend/Edit | `kraken order amend …` / `edit <TXID> …` | — | — |
| JSON | `-o json` ✅ | ✅ | stdout-Text (→ P7) |
| Ticker/OHLC/Book/Trades | `kraken ticker|ohlc|orderbook|trades …` ✅ | ✅ (Details §1b) | — |
| Spread | `kraken spreads` (Plural) | `spread` ⚠️ | — |
| Server-Time | `kraken server-time` ✅ (Clock via CLI!) | — | REST `/0/public/Time` (→ P7) |
| Account | `kraken balance|trade-balance|open-orders|closed-orders|ledgers…` ✅ | ✅ | — |
| L3-Book | `kraken orderbook-l3` ✅ | — | — (Glint-Upgrade prüfen) |
| WS Spot | `kraken ws ticker|trades|book|ohlc|instrument|executions|balances|level3` | `ws subscribe …` ❌ | — |
| WS-Methoden | `kraken ws add-order|…|cancel-after|batch-add|…|ping` | — | — |
| Spot-Paper | `kraken paper init|buy|sell|orders|cancel|cancel-all|history|…` ✅ | Simulator ✅ | `kraken paper …` ✅ grob |
| Futures-Live | `kraken futures order buy\|sell <SYM> <SIZE> …` | — | — |
| Futures-Paper | `kraken futures paper init|buy|sell|…|set-leverage` ✅ | — | `kraken futures paper …` ✅ |
| Futures-Demo | `--futures-url` Override (P0b-Beweis offen) | `--sandbox/--demo` ❌ | Sandbox-URL ✅ Idee |
| Earn | `kraken earn allocate|deallocate|…|strategies|allocations` | `stake/unstake` ❌ | — |
| MCP | `kraken mcp [-s …] [--allow-dangerous]` | — | `KrakenMCPBridge`-Ersatz ✅ |

---

## 3. Kanonische Schnittstellen (§1b-korrigiert, P0b zu bestätigen)

### 3.1 Live Trading

```bash
# Spot
kraken order buy  <PAIR> <VOL> [--type limit --price <P>] [--close-ordertype stop-loss --close-price <P>] [--validate] -o json
kraken order sell <PAIR> <VOL> [--type limit --price <P>] [--close-ordertype stop-loss --close-price <P>] [--validate] -o json
kraken order cancel <TXID...> [-o json] | kraken order cancel-all -o json
kraken order batch <FILE> [--deadline <RFC3339>] [--validate] -o json
kraken order amend (--txid <T>|--cl-ord-id <ID>) [--limit-price <P>] [--order-qty <Q>] -o json
# Futures-Live (kein close-Flag → SL via --stop-price/--trigger-signal + Reduce-Only-Folgeorder)
kraken futures order buy|sell <SYM> <SIZE> [--type limit --price <P>] [--client-order-id <ID>] [--reduce-only] -o json
```

### 3.2 Notfall & Dead-Man

```bash
kraken order cancel-after <SECS> -o json          # Spot (0 = deaktivieren)
kraken futures cancel-after ...                   # Futures-Pendant prüfen (P0b)
kraken order cancel-all -o json                   # KILL_SWITCH/PAUSE → sofort
```

Puls-Regel unverändert (§20): nur bei erfolgreichem Time-Ping; 1800 s Offline →
Entry-Limits canceln wenn `has_native_stop_loss`, sonst `close_all_market`.

### 3.3 Paper (kanonisch: NIO-Simulator; CLI-Engines als Profile)

- **Default:** lokaler NIO-Simulator vs. WS-L2-Book (deterministisch, Spot+Futures).
- **Profil `cli-paper`:** `kraken paper init --capital … / buy|sell / orders /
  cancel / history / status` (auth-frei, Workspace-scoped).
- **Profil `cli-futures-paper`:** `kraken futures paper init / buy|sell /
  positions / fills / set-leverage …` (Symbol z. B. `PF_XBTUSD`).
- Futures-Demo-REST: nur via `--futures-url`-Override (P0b-Beweis offen);
  kein `--sandbox/--demo`.

### 3.4 Marktdaten (alle via CLI)

```bash
kraken server-time -o json
kraken ticker <PAIR...> -o json
kraken ohlc <PAIR> --interval <M> [--since <TS>] -o json
kraken orderbook <PAIR> --count <N> -o json
kraken trades <PAIR> [--since <TS>] [--count <N>] -o json
kraken spreads <PAIR> [--since <TS>] -o json
```

### 3.5 Account (alle via CLI)

```bash
kraken balance | kraken extended-balance | kraken trade-balance -o json
kraken open-orders [--trades] [--cl-ord-id <ID>] | kraken closed-orders -o json
kraken positions | kraken trades-history | kraken ledgers [--asset A] [--type T] -o json
kraken orderbook-l3 ...   # Glint-Upgrade-Kandidat (autorisiertes L3-Book)
```

### 3.6 WebSocket-v2 (FIX-Ersatz, < 15 ms)

```bash
kraken ws ticker|trades <PAIRS...> [--snapshot]
kraken ws book <PAIRS...> --depth <10|25|100|500|1000>
kraken ws ohlc <PAIRS...> --interval <M>
kraken ws executions [--snap-trades] [--snap-orders]   # Fills + Order-Status (auth)
kraken ws balances                                     # (auth)
kraken ws level3 <PAIRS...> [--depth 10|100|1000]      # (auth)
```

Auth = konfigurierte Credentials (Env/Config), **kein `--token`**.
Speist Simulator-Book, `KrakenDepthAdapter` (2 %-Band, Spread bps, Age < 3 s →
`GlintOrderbookVerifier`) und Exchange-Clock-Fallback.

### 3.7 Earn (Hintergrund-Job, nie in der Trading-Schleife)

```bash
kraken earn strategies [--asset A]
kraken earn allocate <STRATEGY_ID> <AMOUNT> | kraken earn deallocate <STRATEGY_ID> <AMOUNT>
kraken earn allocate-status|deallocate-status <STRATEGY_ID> | kraken earn allocations
```

---

## 4. Architektur: Bridge + Wrapper (Subprocess-only)

`app/execution/KrakenCliBridge.py` + `app/execution/KrakenCliWrapper.py`
(beide noch nicht existent).

```text
TV-Signal → SafetyGuard → ONNX/Kelly → Judge/M8 → Dispatcher ─┬─ paper → Simulator ─┐
                                                                └─ live ─────────────┤
                                                              KrakenCliBridge (Subprocess, JSON-Envelope, E3000)
                                                                          │ argv via
                                                              KrakenCliWrapper (kanonische Signatur → Profil)
                                                                          ▼
                                                              `kraken … -o json`  (+ `kraken ws …` Streams)
                                                                          │
                                     orders.jsonl ← stdout-Envelope + Exit-Code (0/1/2) + stderr-Fallback
```

**Wrapper-Profile (P0a-fixiert):** `order-namespace` = **aktiv/default**
(verifiziert v0.4.1) · `top-level` = inaktiv, Forward-Compat (Ciel-Form) ·
`trade-legacy` = deprecated (BLUEPRINT-Form). P0b bestätigt per `--help`-Diff.

**Kanonische NIO-Signatur** (stabil über CLI-Versionen): `place(side, pair,
vol, price?, ordertype, close_*?, validate?, cl_ord_id?)`, `cancel/cancel_all/
batch/amend`, `deadman_arm/pulse`, `ticker/ohlc/orderbook/trades/spreads/
server_time`, `balance/…/ledgers`, `ws_subscribe(channel, …)` → NDJSON,
`paper_*` (Simulator-Default, CLI-Profile optional), `earn_*` (Job),
Futures: `f_*` (order/cancel-after/paper/`--futures-url`-Demo).

**Bridge-Regeln (hart):**

1. **Subprocess-only.** Genau ein Modul ruft `kraken …` auf.
2. **Fehlervertrag (§17.3, P0a-präzisiert):** `-o json` → stdout trägt **immer**
   JSON (Erfolg **oder** Fehler-Envelope `{error, message, …}`,
   `output/json.rs:34`), Exit 0/1. Venue-Strings (`EOrder:`/`EGeneral:`/`EAPI:`)
   bleiben in `message` erhalten → Envelope-Kategorie **primär**, E-String-Match
   **Fallback** (stderr, Exit 2 = clap-Nutzungsfehler → eigenes Mapping).
3. **E3000** (§36.2): `ERR_KRAKEN_INSUFFICIENT_FUNDS`, `ERR_KRAKEN_RATE_LIMIT_429`
   (eigene `RateLimit`-Kategorie mit `retryable`-Hint!), `ERR_KRAKEN_DEADMAN_TIMEOUT`,
   `ERR_KRAKEN_CLI_NOT_FOUND` (+ `ERR_KRAKEN_VALIDATE_REJECT`, `ERR_KRAKEN_USAGE`
   für Exit 2). Mappingtabelle + Tests.
4. **Idempotenz:** Schema-A-`idempotency_key` → `--cl-ord-id` (Spot) /
   `--client-order-id` (Futures); sonst Dedupe-Fenster in `orders.jsonl` + DuckDB.
5. **Secrets:** Env/CLI-Config; Live nur bei `SIGMA_LIVE_TRADING=1` **und**
   `LIVE_APPROVED`. Least-Privilege (kein Deposit/Withdraw).
6. **Rate-Limits:** Token-Bucket + 80 %-Soft-Cap; CLI-`rate_limit`-Envelope →
   E3000 + Backoff (kein Retry-Sturm).
7. **Logging:** jede Invocation → `orders.jsonl`; Fehler → `errors.jsonl`
   (`subsystem: kraken-bridge`).

---

## 5. Phasen & Aufgaben

### P0a — Quellen-Verifikation (✅ DONE 2026-09-13, Sandbox)

- [x] v0.4.1-Quelle via codeload gezogen (release-assets im Sandbox-Netz blockiert —
  Installer-`curl` schlägt hier fehl, siehe P0a-Protokoll unten).
- [x] Clap-Tree vollständig vermessen; Matrix in §2 + Fixture
  `tests/fixtures/kraken_cli/kraken-cli-0.4.1.source.json` abgelegt.
- [x] Ciel-Abweichungen dokumentiert (§1b, §9); `order-namespace` als Default fixiert.
- [x] P0b-Script `scripts/kraken_p0_verify.sh` bereitgestellt.

**P0a-Protokoll (Netz):** Sandbox-Egress erlaubt u. a. `github.com`,
`api.github.com`, `codeload.github.com`, `pypi.org`, `registry.npmjs.org`;
blockiert: `release-assets.githubusercontent.com` (TLS-Reset),
`raw.githubusercontent.com`, `crates.io`, `proxy.golang.org` u. a.
→ **Kein Binary, kein Rust-Build in der Sandbox möglich.**
npm-Paket `kraken-cli@0.0.6` ist ein fremdes Squat-Paket — **nicht installieren**.

### P0b — Binary-Verifikation (⌛ Zielbox, 1 Befehl)

- [ ] Auf der Zielbox: Installer-`curl` (User-Vorgabe) ausführen, dann
  `bash scripts/kraken_p0_verify.sh` → Fixtures unter
  `tests/fixtures/kraken_cli/help/` + Live-Samples committen.
- [ ] `--help`-Diff gegen P0a-Fixture (Version drift? → Nachtrag hier).
- [ ] Keyed-Checks manuell (`balance`, `--validate`-Dry-Run, `cancel-after`-Test).
- [ ] `--futures-url`-Demo-Beweis (oder als unmachbar + Simulator-Entscheid schließen).

### P1 — Wrapper + Bridge-Kern

- [ ] `KrakenCliWrapper.py`: kanonische Signatur × Profile
  (`order-namespace` aktiv; `top-level`/`trade-legacy` gemappt, getestet, inaktiv).
- [ ] `KrakenCliBridge.py`: `place/cancel/cancel_all`, Subprocess + Timeout,
  Envelope-Parse (stdout), stderr/Exit-2-Fallback.
- [ ] `ERR_KRAKEN_CLI_NOT_FOUND` + Installations-Hint; `orders.jsonl`-Writer.
- [ ] Tests: Mapping-Matrix (Calls × Profile) + Envelope-Matrix
  (ok/fail × Kategorien × Exit 0/1/2).

### P2 — Safety: Deadman + E3000

- [ ] `deadman_arm/pulse` (`order cancel-after`), Puls an `server-time` gekoppelt.
- [ ] Exception→Code-Mapping §36 (+ `VALIDATE_REJECT`, `USAGE`) + `errors.jsonl`.
- [ ] KILL_SWITCH/PAUSE → `cancel-all` + Test.

### P3 — Simulator-Paper + Graduation

- [ ] NIO-Simulator (Default) vs. WS-L2-Book; Profile `cli-paper`,
  `cli-futures-paper` hinter gleicher Schnittstelle.
- [ ] Futures-Demo nur per `--futures-url` (nach P0b-Beweis), sonst Simulator.
- [ ] Gates §32.1 im Core; Scout Loop D hart auf Paper; Live-Budget = 0.

### P4 — WS-v2 + Marktdaten + Depth

- [ ] `ws`-Client (NDJSON, Reconnect/Backoff, Credentials für private Channels).
- [ ] Snapshot-Calls §3.4/§3.5 über Wrapper; `server-time` als Exchange-Clock.
- [ ] `KrakenDepthAdapter` aus WS-Book (L3-Upgrade via `orderbook-l3` evaluieren).

### P5 — Brackets, Batch, Amend (+ Futures-SL-Pattern)

- [ ] Spot-Brackets nativ (`--close-*`); Futures-SL = `--stop-price`/
  `--trigger-signal` + Reduce-Only-Folgeorder (testen!).
- [ ] `batch` (2–15, `--deadline`, `--validate`-Vorlauf); `amend`/`edit`.

### P6 — Pre-Live-Härtung + Earn-Job

- [ ] `--validate`-Pflicht + CI-Smoke (mockbar ohne Keys).
- [ ] Rate-Limiter (Bucket, Soft-Cap, `retryable`-Auswertung).
- [ ] Live-Gate E2E (Default: Simulator); `earn`-Job (entkoppelt) + Tests.
- [ ] Runbook `docs/KRAKEN-RUNBOOK.md`.

### P7 — Doku-Nachzug (nach P0b)

- [ ] BLUEPRINT §4.3/§20/§32.2: `trade add-order` → verifizierte Syntax;
  `server-time`-Clock; Simulator-Begriff; `KrakenMCPBridge`-Ersetzung bestätigen.
- [ ] Kopf-Nachtrag: verifizierte Zielbox-Version.

### OUT OF SCOPE

Eigener REST-/FIX-Orderpfad, ccxt-Execution, Pionex-Live, FIX-Ausbau,
`mcp`-Standardbetrieb (nur Evaluierung).

---

## 6. Datei- & Konfigurationskarte

| Artefakt | Pfad | Bemerkung |
|---|---|---|
| Bridge / Wrapper | `app/execution/KrakenCliBridge.py`, `KrakenCliWrapper.py` | neu (P1) |
| Simulator | `app/execution/PaperSimulator.py` | neu (P3) |
| WS-Client | `app/market/KrakenWsClient.py` | neu (P4) |
| Dispatcher | `app/execution/reliable_order_dispatcher.py` | Routing |
| Earn-Job | `app/jobs/EarnCompoundJob.py` | neu (P6) |
| Symbol-Map / Clock / Limiter | `app/tv/symbol_map.py`, `app/core/exchange_clock.py`, `app/core/rate_limiter.py` | — |
| Depth-Adapter | (bestehend, Glint-Wiring) | aus WS-Book |
| Logs | `./data/logs/orders.jsonl`, `./data/logs/errors.jsonl` | — |
| Config | `config/autonomy-level-4.yaml` | `execution_modes`, `kraken_paper_engine` |
| Kill-Dateien | `./data/signals/KILL_SWITCH`, `PAUSE` | → 503 + `cancel-all` |
| P0a-Fixture | `tests/fixtures/kraken_cli/kraken-cli-0.4.1.source.json` | ✅ eingecheckt |
| P0b-Fixtures | `tests/fixtures/kraken_cli/help/`, `*.sample.*` | via Script (P0b) |
| P0b-Script | `scripts/kraken_p0_verify.sh` | ✅ bereit |
| Runbook | `docs/KRAKEN-RUNBOOK.md` | P6 |

---

## 7. Abnahme

- [ ] P0a ✅ (Fixture); P0b: `--help`-Diff sauber, Live-Samples committed.
- [ ] Mapping-Matrix grün (kanonische Calls × Profile).
- [ ] Paper-E2E (Simulator + beide CLI-Profile); 20 Trades für Gate 2→3 simulierbar.
- [ ] Live-Gate-Negativ-Test (kein Order-Subprocess ohne Flag + Approval).
- [ ] Deadman-Test (Puls-Stopp → `cancel-after` greift).
- [ ] Error-Matrix grün (Envelope-Kategorien × E-String-Fallback × Exit 0/1/2).
- [ ] Kill-Test (Datei → 503 + `cancel-all` im Log).
- [ ] WS-Soak 10 min + Reconnect-Beweis.
- [ ] P7: keine `trade add-order`-Strings mehr im Blueprint.

---

## 8. Fragen-Log

1. ~~Syntax~~ → Dual-Format-Wrapper ✅; Profil per P0a korrigiert:
   `order-namespace` aktiv (Ciel-Top-Level widerlegt, als Compat-Profil behalten).
2. ~~Schnittstellen-Volltext~~ → übernommen mit 4 Korrekturen (§1b:
   `spreads`, `--count`, kein `subscribe`, kein `--token`).
3. ~~Futures-Paper~~ → `--sandbox/--demo` widerlegt; `--futures-url` + Simulator +
   `futures paper` (P0b-Beweis für Demo-URL offen).
4. ~~Brackets~~ → ✅ voll bestätigt (`--close-*` + `--close-price2`).
5. ~~FIX & Staking~~ → ✅ Prinzip; Earn-Verben korrigiert
   (`allocate/deallocate/…` statt `stake/unstake`).

---

## 9. Ciel-Rückmeldung (P0a-Korrekturen, Belege v0.4.1-Quelle)

1. **Orders sind `kraken order …`, nicht Top-Level.** Beleg: `commands/mod.rs`
   (`Order(OrderCommand)`), `commands/trade.rs:18`. Kein `buy/sell`-Alias im Tree.
2. **WS heißt `kraken ws <channel>`, kein `subscribe`.** Beleg: `commands/ws/mod.rs:52`,
   `commands/ws/channels.rs`. Auth ohne `--token` (Credentials aus Env/Config).
3. **Earn heißt `allocate/deallocate/strategies/allocations`.** Beleg: `commands/earn.rs:14`.
4. **Kein `--sandbox/--demo`.** Beleg: negativer Grep; Demo-Weg ist
   `--futures-url`/`KRAKEN_FUTURES_URL` (`cli.rs:531` + folgende).
5. **Kleinigkeiten:** `spreads` (Plural), Orderbook-Tiefe `--count`,
   `ledgers` ohne direktes `--since` (Pagination).
6. **Bestätigt und übernommen:** `-o json`, `--validate`, `--cl-ord-id`,
   `--close-*` (+`--close-price2`), `cancel-after`, Datei-Batch, Market-/Account-
   Top-Level, `futures paper`-Engine, Wrapper-Prinzip, Simulator-Default,
   FIX-Out-of-Scope, Earn-Hintergrund-Job.
7. **Neu gefunden (nicht in der Direktive):** `kraken server-time`
   (Exchange-Clock ohne REST-Ausnahme), `kraken orderbook-l3`,
   WS-One-Shot-Methoden (`ws add-order/…/ping`), JSON-Fehler-Envelope auf stdout
   bei Exit 1, Exit 2 für Nutzungsfehler, eigene `RateLimit`-Kategorie mit
   `retryable`-Hint, `--yes`, `--workspace`-Scoping, `mcp -s/--allow-dangerous`.
