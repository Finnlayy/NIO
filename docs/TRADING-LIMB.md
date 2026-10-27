# Trading-Limb: Sigma als Handels-Knoten

Der Limb `trading` betreibt [Sigma](https://github.com/Finnlayy/Sigma) als
eigenen Worker und spricht ausschließlich über dessen HTTP-API mit ihm.

**Das Verhältnis ist komplementär, nicht konkurrierend:**

| | Sigma | NIO |
|---|---|---|
| hat | deterministische Handels-Engine, TradingView-Scraper, tvremix/TradingView-MCP mit CSV-Interchange, DuckDB/Parquet-Lake, 912 grüne Tests | Orchestrator: Intent/Result-Protokoll, Sandbox, Timer, Prozessgruppen, Nachweise |
| hat nicht | funktionierenden Orchestrator | eine Handels-Engine |

Der Limb ist deshalb **kein Fork und kein Vendor-Drop**. Am Donor wird nichts
gepatcht; Sigmas Suite bleibt der Vertrag. Der Limb pinnt einen Commit und
spricht nur öffentliche Routen an.

```
Intent  →  trading_limb  →  stdlib urllib  →  Sigma-Worker (uvicorn)
        ←  Result        ←                   ←
```

---

## 1. Operationen

| Operation | Risk | Netz | Verhalten |
|---|---|---|---|
| `trading.ping` | none | nein | installiert? läuft der Worker? Pin, Port, Health |
| `trading.install` | write | **ja** | Sparse-Clone auf Pin, `.git` entfernen, venv, `pip install` |
| `trading.start` | none | nein | uvicorn als eigene Prozessgruppe, wartet auf Health |
| `trading.stop` | none | nein | SIGTERM auf die **Gruppe**, dann SIGKILL |
| `trading.status` | read | nein | Health + Lake-Kurzfassung |
| `trading.lake_summary` | read | nein | `total_rows`, `total_files`, `total_size_mb`, `symbols[]` |
| `trading.lake_compact` | write | nein | Partitionen nach Parquet verdichten |
| `trading.backtest_run` | read | nein | Backtest über den TV-MCP-CSV-Pfad |

> **Namensregel:** Das Protokoll erlaubt in Operationsnamen **genau einen
> Punkt** (`^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$`). `trading.lake_summary` ist
> gültig, `trading.lake.summary` nicht — der Validator lehnt es mit
> `E_SCHEMA_INVALID` ab.

Nur `trading.install` hat Netzzugriff. Alles andere spricht ausschließlich
`127.0.0.1:<port>`, Default **8731**.

---

## 2. Installation

Sigma ist als Repository ~818 MB — davon ~166 MB fremde
`claude-desktop_*.deb.part-*`-Dateien und Historie. Gebraucht wird Code:

```bash
git clone --depth 1 --filter=blob:none --sparse <repo>
git sparse-checkout set --no-cone \
    /app/ /sigma/ /tests/ /config/ /requirements.txt /pytest.ini
```

| | Arbeitsbaum | Dauer |
|---|---:|---:|
| vollständiger Clone | 818 MB | ~60 s |
| **Sparse + Blobless** | **2,2 MB** | **~6 s** |

### Warum `/sigma/` im Cone stehen muss

`app/server/routes_sigma.py` importiert auf Modulebene:

```python
from sigma.orchestration.paper_validation_rotator import get_paper_validation_rotator
```

Fehlt das Paket, startet der Worker nicht — `ModuleNotFoundError: No module
named 'sigma'`. Das ist beim ersten Testlauf genau so passiert; der Cone wurde
danach korrigiert.

### Pin statt Branch

```
SIGMA_REF = "e6635c01cde0b13edaab4ada8a47873ee25d4cbb"
```

Ohne Pin ist „die Suite ist grün" keine Aussage über den laufenden Code. Der
Limb prüft nach dem Checkout `git rev-parse HEAD` gegen den Pin und bricht bei
Abweichung mit `E_INTERNAL` ab.

### `.git` wird gelöscht — und warum das einen Bug erzeugte

Nach dem Checkout fallen 167 MB Historie für 2,2 MB Code weg. Der erste Entwurf
hat das `.git` entfernt und beim zweiten `install` in genau diesem Verzeichnis
`git fetch` versucht:

```
fatal: remote error: upload-pack: not our ref e6635c01…
```

Die Lösung ist bewusst kein `fetch`, sondern **Idempotenz über den Marker**:

```python
def _installed(self, layout) -> bool:
    return (self._read_marker(layout) is not None
            and (layout.install / "app").is_dir()
            and layout.python.is_file())
```

Ist das nicht erfüllt, wird der Baum **neu aufgebaut** statt fortgesetzt. Eine
halb fertige Installation wird nie weiterverwendet.

Die Provenienz steht im Marker `.nio-trading-install.json`:

```json
{
  "ref": "e6635c01cde0b13edaab4ada8a47873ee25d4cbb",
  "resolved_sha": "e6635c01cde0b13edaab4ada8a47873ee25d4cbb",
  "version": "sigma-hybrid-1.0",
  "install_s": 32.3,
  "install_bytes": 2234505
}
```

---

## 3. Isolation

| Variable | Wert im Limb | Grund |
|---|---|---|
| `HOME` | `<sandbox>/home` | ohne das schreibt Sigma ins echte `~/.cache` |
| `TMPDIR` | `<sandbox>/tmp` | keine Temp-Leichen im Host |
| `XDG_CACHE_HOME` | `<sandbox>/cache` | dito |
| `SIGMA_DATA_DIR` | `<sandbox>/data` | DuckDB + Parquet bleiben in der Sandbox |
| `PYTHONUNBUFFERED` | `1` | Logs sofort, kein Pufferverlust beim Kill |
| `PYTHONDONTWRITEBYTECODE` | `1` | keine `__pycache__` im geklonten Baum |
| `SIGMA_ALLOW_FAKE_REDIS` | `1` | kein Redis-Container nötig |

Der Test `TradingSandboxIsolationTests` bewacht genau diese Liste. Er ist nicht
kosmetisch: während der Entwicklung hat ein Test, der die *echte* Sandbox
benutzte, über die PID-Datei einen laufenden Worker abgeschossen. Die
Fail-closed-Tests haben seither eine eigene Sandbox
(`workspace/.test-trading-failclosed`).

### Prozessgruppe

`subprocess.Popen(..., start_new_session=True)` macht den Worker zum
Gruppenführer. `trading.stop` beendet die **Gruppe** (`os.killpg`), sonst
überleben uvicorn-Kinder und der Port bleibt belegt:

```python
for sig, wait_s in ((signal.SIGTERM, 5.0), (signal.SIGKILL, 2.0)):
    os.killpg(os.getpgid(pid), sig)
    …
```

---

## 4. Betriebsprofil

Beim Start loggt Sigma `TV MCP adapter ready (fake)`. Ohne den
Contagion-Endpunkt (`127.0.0.1:8001`) bleiben Einträge blockiert — das ist
**fail-closed wie gewünscht**, kein Fehler. Der Lake wird trotzdem mit
synthetischen Candles geseedet, sodass Backtests laufen.

### Health

```
GET /api/v1/health      ← korrekt
GET /api/health         ← 404, nicht verwenden
```

Beispielantwort:

```json
{
  "status": "paused",
  "kill_switch": false,
  "pause": true,
  "scraper_ok": false,
  "scraper": { "ok": false, "base_url": "http://127.0.0.1:8001", "degraded": true }
}
```

`trading.start` pollt `/api/v1/health`, bis der Worker antwortet (Timeout aus
dem Intent-Budget), und bricht ab, wenn der Prozess vorher stirbt — mit dem
Tail aus `logs/worker.log`.

### Zugriff auf den Worker-API

| Route | Methode | Zweck |
|---|---|---|
| `/api/v1/health` | GET | Lebenszeichen |
| `/api/lake/summary` | GET | Lake-Inventar |
| `/api/lake/compact` | POST | Partitionen verdichten |
| `/api/lake/query` | GET | Candles (`?symbol=BTC/USD&limit=50`) |
| `/api/backtest/run` | POST | Backtest |
| `/api/backtest/mcp-status` | GET | TV-MCP-Adapter-Zustand |
| `/api/backtest/ohlc` | GET | **erwartet `pair`, nicht `symbol`** → sonst 422 |

---

## 5. Backtest-Parameter

`trading.backtest_run` reicht **nur deklarierte Felder** weiter — alles andere
wird verworfen (ein Test mit `{"evil": "DROP TABLE"}` bewacht das):

| Limb-Parameter | Sigma-Feld | Default |
|---|---|---|
| `strategy` | `strategyType` | `sma_cross` |
| `pair` | `assetPair` | `BTC/USD` |
| `interval` | `interval` (Minuten) | `60` |
| `candleCount` | `candleCount` | `300` |
| `initialBalance` | `initialBalance` | `10000.0` |
| `params` | `parameters` | — |
| `strategyId` | `strategyId` | — |

---

## 6. Nachweise

Belegt in dieser Umgebung (2026-10-27):

| Schritt | Ergebnis |
|---|---|
| `trading.install` | success, **32,3 s**, **2 234 505 B** |
| `trading.start` | success, **2,1 s**, PID gesetzt |
| `trading.status` | `{"status":"paused"}`, Lake **30 240 Zeilen / 4 Dateien / 1,34 MB** |
| `trading.backtest_run` | `tv_541cc810da`, 300 Candles, **17 Trades**, 10 000 → 9 982,66 |
| `trading.stop` | success, Port geschlossen, PID weg |
| NIO-Suite | **360 Tests OK** (337 bestehend + 23 neu) |
| Sigma-Suite | **912 passed, 1 skipped** — zweimal, identische Zahlen |

Sigma-Suite selbst ausführen:

```bash
cd workspace/sigma
SIGMA_DATA_DIR=/tmp/sigma-check ../venv/bin/python -m pytest tests -q
# 912 passed, 1 skipped
```

---

## 7. Grenzen

| Nicht enthalten | Warum |
|---|---|
| **Ersatz für Sigmas Orchestrator** | Der Limb startet/stoppt und protokolliert. Strategie-Loops, Deadman und Scheduler-Matrix (16 Tasks) laufen im Worker und sind hier nicht Gegenstand. |
| **Live-Broker** | Kraken-Routen existieren in Sigma, werden aber nicht exponiert. |
| **Qdrant** | Candles sind tabellarisch, nicht vektoriell — siehe [`DATA-FLOW.md`](DATA-FLOW.md#warum-qdrant-hier-nicht-hingehört). |

---

## 8. Fehlerbilder

| Meldung | Ursache | Abhilfe |
|---|---|---|
| `E_IO … Worker nicht erreichbar` | nicht gestartet | `trading.start` |
| `E_IO … git clone fehlgeschlagen` | Netz oder Ref | `constraints.allow_network=true` prüfen |
| `ModuleNotFoundError: No module named 'sigma'` | Cone unvollständig | `/sigma/` in `sparse-checkout` |
| `upload-pack: not our ref` | `.git` fehlt, Re-Install | Limb baut jetzt neu auf; alte Installation löschen |
| `E_SCHEMA_INVALID … Format verletzt Muster` | Operationsname mit zwei Punkten | genau ein Punkt |
| `HTTP 422` auf `/api/backtest/ohlc` | `symbol` statt `pair` | `pair` verwenden |
| Worker stirbt sofort | fehlende Dependencies | `logs/worker.log` lesen |
