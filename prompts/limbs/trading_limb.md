# Rollen-Spezifikation: Trading-Limb (Phase 5)

Version 1.0 · Ziel-Datei `limbs/trading_limb.py` · Register-Name `trading`
· Donor: [Sigma](https://github.com/Finnlayy/Sigma) @ `e6635c01cde0b13edaab4ada8a47873ee25d4cbb`

Der Trading-Limb ist **kein Fork und kein Vendor-Drop**. Sigma besitzt eine
deterministische, vollständig getestete Handels-Engine (TradingView-Scraper,
tvremix/TradingView-MCP mit CSV-Interchange, DuckDB/Parquet-Lake) — und keinen
funktionierenden Orchestrator mehr. NEU besitzt genau das Gegenteil. Der Limb
ist die Naht dazwischen:

```
Intent  ->  trading_limb  ->  HTTP (stdlib urllib)  ->  Sigma-Worker (uvicorn)
        <-  Result       <-                          <-
```

**Sigmas Suite bleibt der Vertrag.** Nichts am Donor wird gepatcht; der Limb
pinnt einen Commit und spricht ausschließlich über Sigmas öffentliche
`/api/*`-Routen. Ändert sich Sigma, bricht der Pin — nicht das Verhalten.

---

## 1. Auftragsumfang

| Operation | Risk | Netz | Verhalten |
|---|---|---|---|
| `trading.ping` | none | nein | installiert? läuft der Worker? Pin, Port, Health |
| `trading.install` | write | **ja** | Sparse-Clone auf Pin, `.git` entfernen, venv, `pip install` |
| `trading.start` | none | nein | uvicorn als eigene Prozessgruppe, wartet auf Health |
| `trading.stop` | none | nein | SIGTERM auf die **Gruppe**, danach SIGKILL |
| `trading.status` | read | nein | Health + Lake-Kurzfassung als Betriebsnachweis |
| `trading.lake_summary` | read | nein | `total_rows`, `total_files`, `total_size_mb`, `symbols[]` |
| `trading.lake_compact` | write | nein | Partitionen nach Parquet verdichten |
| `trading.backtest_run` | read | nein | Backtest über den TV-MCP-CSV-Pfad |

`trading.install` ist die einzige Operation mit Netzzugriff. Alles andere
spricht ausschließlich `127.0.0.1:<port>` (Default `8731`).

---

## 2. Warum Sparse-Checkout

Sigma ist als Repository ~818 MB — davon ~166 MB fremde
`claude-desktop_*.deb.part-*`-Dateien und Historie. Gebraucht wird Code:

```bash
git clone --depth 1 --filter=blob:none --sparse <repo>
git sparse-checkout set --no-cone /app/ /sigma/ /tests/ /config/ \
                              /requirements.txt /pytest.ini
```

| | Arbeitsbaum | Dauer |
|---|---:|---:|
| vollständiger Clone | 818 MB | ~60 s |
| Sparse + Blobless | **2,2 MB** | **~6 s** |

`/sigma/` ist Pflicht: `app/server/routes_sigma.py` importiert
`sigma.orchestration.paper_validation_rotator` auf Modulebene. Fehlt das
Paket, startet der Worker nicht (`ModuleNotFoundError: No module named 'sigma'`).

Nach dem Checkout wird `.git` gelöscht (167 MB für 2,2 MB Code). Die
Provenienz steht im Marker:

```json
{ "ref": "e6635c01…", "resolved_sha": "e6635c01…", "install_bytes": 2234505 }
```

Ein erneutes `trading.install` baut den Baum deshalb **neu auf**, statt in
einem `.git`-losen Verzeichnis zu `fetch`en (das schlug zuvor mit
`upload-pack: not our ref` fehl).

---

## 3. Harte Regeln für den Limb

1. **Kein Shell-String.** Jedes Kommando ist eine argv-Liste. Es gibt keinen
   Punkt, an dem Intent-Daten in eine Shell interpretiert werden.
2. **Pfade durch die Policy.** `ctx.resolve()` hält Installation, venv, Daten,
   Logs und Cache in der Sandbox des Knotens.
3. **Eigene Prozessgruppe.** `start_new_session=True`; `stop` beendet die
   Gruppe (`os.killpg`), damit uvicorn-Kinder nicht verwaisen.
4. **Eigenes Zuhause.** `HOME`, `TMPDIR`, `XDG_CACHE_HOME` und
   `SIGMA_DATA_DIR` zeigen in die Sandbox. Ohne das schreibt Sigma in echtes
   `~/.cache`; der Test `TradingSandboxIsolationTests` bewacht das.
5. **Fail-closed.** Ist der Worker tot, gibt es `E_IO` mit Hinweis auf
   `trading.start` — niemals erfundene Kennzahlen.
6. **Nur deklarierte Felder.** `trading.backtest_run` reicht ausschließlich
   `strategyType`, `assetPair`, `interval`, `candleCount`, `initialBalance`,
   `parameters` und `strategyId` weiter. Alles andere wird verworfen.

---

## 4. Betriebsprofil

Der Worker startet mit Fakes, damit der Limb ohne Börse und ohne Netz
hochkommt:

| Variable | Wert im Limb | Grund |
|---|---|---|
| `SIGMA_ALLOW_FAKE_REDIS` | `1` | kein Redis-Container nötig |
| `SIGMA_DATA_DIR` | `<sandbox>/data` | DuckDB + Parquet bleiben in der Sandbox |

Sigma loggt beim Start `TV MCP adapter ready (fake)` und blockiert Einträge,
solange der Contagion-Endpunkt (`127.0.0.1:8001`) fehlt — **fail-closed, wie
gewünscht**. Der Lake wird trotzdem mit synthetischen Candles geseedet.

Health liegt unter **`/api/v1/health`** (nicht `/api/health` — das ist 404).

---

## 5. Nachweise

Belegt am 2026-10-27 in dieser Sandbox:

| Schritt | Ergebnis |
|---|---|
| `trading.install` | success, **32,3 s**, **2 234 505 B** |
| `trading.start` | success, **2,1 s**, PID gesetzt |
| `trading.status` | `{"status":"paused", …}`, Lake **30 240 Zeilen / 4 Dateien / 1,34 MB** |
| `trading.backtest_run` | success, `tv_541cc810da`, 300 Candles, **17 Trades**, 10 000 → 9 982,66 |
| `trading.stop` | success, Port geschlossen, PID weg |
| NIO-Suite | **360 Tests OK** (337 bestehend + 23 neu) |
| Sigma-Suite | **912 passed, 1 skipped** (zweimal, identisch) |

---

## 6. Grenzen

* **Kein Ersatz für Sigmas Orchestrator.** Der Limb startet/stoppt und
  protokolliert; er fährt keine Strategie-Loops, kein Deadman, keine
  Scheduler-Matrix. Die laufen im Worker (16 Tasks) und sind hier nicht
  Gegenstand.
* **Kein Live-Broker.** Kraken-Routen existieren in Sigma, werden vom Limb aber
  nicht exponiert.
* **Kein Qdrant.** Candles sind tabellarisch, nicht vektoriell; ein Embedding
  einer OHLC-Zeile hat keinen Sinn. Semantische Erinnerung bleibt Sache von
  `Architect/limbs/intelligence/qdrant_memory_engine.py`.
