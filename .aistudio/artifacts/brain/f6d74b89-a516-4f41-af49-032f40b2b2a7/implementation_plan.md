# OMEGA NIO Terminal — Trader-UX & Live-Workflow Upgrade

Dieses Upgrade beseitigt die zentralen Reibungspunkte im täglichen 24/7-Trading-Betrieb: Zeitrahmen lassen sich direkt am Chart mit einem Klick umschalten, offene Paper-Positionen werden sichtbar im Chart eingezeichnet sowie automatisch per Stop-Loss/Take-Profit überwacht, und jedes akustische Synth-Chime-Signal wird von einem 6-Sekunden-Live-Toast samt abrufbarer Glocken-Historie im Header begleitet.

## User Review & Critical Decisions

> [!IMPORTANT]
> Alle Entscheidungen aus der Abstimmung sind hier verbindlich festgehalten:

- **Bestätigte Entscheidung 1 (Funktionsumfang)**: Umsetzung der **direkten Timeframe-Buttons im Chart-Header**, der **Auto-SL/TP-Logik inkl. Chart-Linien für offene Paper-Positionen** sowie der **Live-Event-Toasts passend zu den Audiosignalen**.
- **Bestätigte Entscheidung 2 (Benachrichtigungs-Verhalten)**: Neue Audio-Events (Take-Profit, Stop-Loss, Order-Fill, RVOL-/Volatilitäts-Anomalie) erscheinen als **kompakte Live-Event-Toasts oben rechts**, blenden sich **automatisch nach 6 Sekunden** wieder aus und werden zusätzlich in einer **Benachrichtigungs-Glocke im Header** (mit Ungelesen-Zähler und 1-Klick-Sprung zum Symbol) gespeichert.
- **Empfohlener Standard für Auto-SL/TP bei neuen Paper-Positionen**: Beim Eröffnen einer Paper-Position werden Stop-Loss und Take-Profit automatisch anhand der aktiven Strategie-Parameter (`slAtrMult` und `tpRMultiple` bzw. prozentualer Fallback-Abstand) berechnet und können in der Positions-Tabelle jederzeit per **1-Klick „SL → Break-Even"** abgesichert oder angepasst werden.

---

## 1. Overview & Core Concept

- **Was das Upgrade leistet**:
  1. **1-Klick Timeframe-Bar im Chart-Header**: Eine direkt in die obere Dossier-/Chart-Leiste integrierte Segment-Steuerung (`1m | 5m | 15m | 1h | 4h | 1d`), die den Zeitrahmen sofort umschaltet und den Backtest ohne Umweg über das linke Konfigurationsmenü neu ausführt.
  2. **Auto-SL/TP & Live-Chart-Linien für offene Paper-Positionen**: Offene Paper-Trades für das aktuell ausgewählte Symbol werden direkt als horizontale Preislinien (`PAPER ENTRY`, `PAPER SL`, `PAPER TP` inkl. Live-PnL-Tag) im Kerzenchart dargestellt. Ein Hintergrund-Wächter prüft bei jedem Live-Preistick, ob der Kurs das SL- oder TP-Level erreicht hat, schließt die Position automatisch über die Paper-Bridge und löst den passenden Take-Profit- oder Stop-Loss-Synth-Chime samt Toast aus.
  3. **Synchronisierte Audio-Event-Toasts & Header-Glocke**: Immer wenn ein Marktereignis einen Synth-Chime auslöst (TP erreicht, SL gerissen, Order ausgeführt, RVOL-/Vola-Spike im Screener), erscheint für 6 Sekunden ein kontrastreicher Terminal-Toast. Über das Glocken-Icon im Header lassen sich die letzten 30 Ereignisse jederzeit nachlesen und per Klick direkt im Chart öffnen.
- **Zielgruppe & Kontext**: Aktive Trader, die das Terminal im 24/7-Dauerbetrieb (oft auf einem Zweitmonitor neben anderen Aufgaben) nutzen und sofortiges visuelles wie akustisches Feedback benötigen.
- **Mehrwert**: Keine verpassten Audio-Signale mehr, deutlich schnellere Multi-Timeframe-Analyse am Chart und vollautomatisches Risikomanagement für offene Paper-Positionen.

---

## 2. User Experience & Visual Design

- **Zentrale User Flows**:
  1. **Schneller Timeframe-Wechsel am Chart**: Der Nutzer klickt oben im Chart-Dossier direkt auf `5m`, `15m` oder `4h`. Der aktive Button leuchtet in Cyan (`#00E5FF`), das linke Strategie-Formular synchronisiert sich automatisch und die 8-Provider-Kaskade lädt sofort die neuen Kerzen und Backtest-Ergebnisse.
  2. **Paper-Position mit SL/TP & Chart-Visualisierung**:
     - Beim Klick auf `PAPER BUY` oder `PAPER SELL` (im Orderbook oder im Execution-Tab) wird für die Position automatisch ein Stop-Loss- und Take-Profit-Kurs gesetzt.
     - Im Kerzenchart erscheinen sofort durchgezogene bzw. gestrichelte horizontale Linien für den offenen Paper-Trade (`ENTRY`, `SL`, `TP`) sowie eine Ein-/Ausblend-Option (`Paper-Pos`) in der Chart-Werkzeugleiste.
     - Im Tab `PAPER / LIVE EXECUTION` zeigt jede offene Position ihre aktiven `SL`- und `TP`-Preise, einen **1-Klick „BE" (Break-Even)**-Button (zieht den Stop-Loss auf den Einstiegskurs) sowie den `CLOSE`-Button.
     - Erreicht der Live-Marktpreis das TP- oder SL-Level, wird die Position automatisch glattgestellt, der harmonische TP- bzw. gedämpfte SL-Chime ertönt und ein Live-Toast zeigt den realisierten Gewinn/Verlust.
  3. **Live-Event-Toast & Glocken-Historie**:
     - Ertönt ein Signal (z. B. `RVOL SPIKE: SOL/USD 2.8x` oder `TAKE-PROFIT: BTC/USD +$18.40`), gleitet oben rechts unterhalb des Headers ein kompakter Toast herein.
     - Ein dünner Fortschrittsbalken am unteren Rand des Toasts läuft in 6 Sekunden ab, bevor der Toast sanft ausblendet.
     - Klickt der Nutzer auf den Toast oder öffnet er später die **Benachrichtigungs-Glocke** im Header, springt das Terminal sofort auf das betreffende Handelssymbol.

- **Visual Identity & Theme**:
  - *Ästhetische Richtung*: Institutionelles Quant-Trading-Terminal mit hoher Informationsdichte, flachen Oberflächen (`1px` Rahmen) und null visuellem Ballast.
  - *Farbpalette*:
    - Primärer Hintergrund: `#07090E` (Tiefschwarz-Schiefer) und `#0C1017` (Panel-Oberfläche)
    - Rahmen & Trennlinien: `#1B2230` und `#263042`
    - Semantische Akzente: `#00E5FF` (Fokus / Timeframe aktiv / Order-Fill), `#089981` (Take-Profit / Long / Gewinn), `#F59E0B` (Stop-Loss / Warnung), `#F23645` (Notstopp / Verlust), `#60A5FA` (Screener RVOL-Anomalie)
  - *Typografie & Zahlenformatierung*: Durchgängig tabellarische Monospace-Ziffern (`font-mono tabular-nums`) für alle Preise, Zeitstempel, RVOL-Werte, PnL-Beträge und Countdown-Anzeigen, damit bei Live-Ticks keinerlei Layout-Springen auftritt.

---

## 3. Key Product Decisions & Trade-Offs

- **Entscheidung 1: Kopplung zwischen Audio-Engine und visuellen Toasts**
  - *Gewählter Ansatz*: Eine zentrale Event-Brücke versorgt gleichzeitig den Synthesizer (`arcadeSoundEngine`) und den visuellen Toast-/Glocken-Speicher. Selbst wenn der Ton per Mute-Button stummgeschaltet ist, werden wichtige Markt-Events (TP, SL, Order-Fill, RVOL-Spike) weiterhin stumm in der Glocken-Historie und als Toast protokolliert.
  - *Warum*: So verpasst der Nutzer auch im lautlosen Modus (z. B. während eines Calls) kein einziges Handelssignal.
- **Entscheidung 2: Client-seitige Auto-SL/TP-Überwachung mit Persistenz für Paper-Positionen**
  - *Gewählter Ansatz*: Die SL/TP-Marken offener Paper-Positionen werden deterministisch aus dem Einstiegskurs und dem aktuellen ATR-/Risiko-Setup berechnet, im lokalen Store zwischengepuffert und bei jedem Preis-Update gegen den Live-Kurs geprüft. Ein In-Flight-Execution-Lock verhindert doppelte Schließungs-Orders.
  - *Warum*: Garantiert verzögerungsfreie Reaktion auf Live-WebSocket-Preisticks und übersteht auch einen Browser-Reload im 24/7-Betrieb ohne Datenverlust.
- **Entscheidung 3: Begrenzter Ring-Puffer für Toasts & Glocken-Historie**
  - *Gewählter Ansatz*: Maximal 3 gleichzeitig sichtbare Live-Toasts (6s Lebensdauer) und maximal 30 Einträge in der Glocken-Historie.
  - *Warum*: Bewahrt die 24/7-Speicherstabilität (0% RAM-Wachstum) und hält das Sichtfeld auf dem Chart stets frei.

---

## 4. Technical Architecture & Data Strategy *(Technical Reference)*

- **Architektur- & Datenfluss-Diagramm**:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        OMEGA NIO TERMINAL WORKSPACE                          │
├──────────────────────────────────────────────────────────────────────────────┤
│  TOP HEADER BAR                                                              │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌────────────────────┐  │
│  │ PAPER NAV & 20-CAP   │  │ AUDIO MUTE & CHIMES  │  │ 🔔 EVENT-GLOCKE    │  │
│  │ TELEMETRY            │  │ CONTROLLER           │  │ (Badge + Popover)  │  │
│  └──────────────────────┘  └──────────┬───────────┘  └─────────┬──────────┘  │
├───────────────────────────────────────┼────────────────────────┼─────────────┤
│  CENTER CHART & DOSSIER HEADER        │                        │             │
│  ┌────────────────────────────────────▼────────────────────────▼──────────┐  │
│  │ Symbol Dossier + [ 1m | 5m | 15m | 1h | 4h | 1d ] Direct Timeframe Bar │  │
│  └────────────────────────────────────┬───────────────────────────────────┘  │
│                                       │                                      │
│  ┌────────────────────────────────────▼───────────────────────────────────┐  │
│  │ SVG Candlestick Chart + Live Paper Position Lines (ENTRY / SL / TP)    │  │
│  │ + Floating 6s Auto-Dismiss Live Event Toast Stack (Top-Right Overlay)  │  │
│  └────────────────────────────────────┬───────────────────────────────────┘  │
│                                       │                                      │
│  ┌────────────────────────────────────▼───────────────────────────────────┐  │
│  │ PAPER / LIVE EXECUTION BLOTTER                                         │  │
│  │ Open Positions Table with Live SL / TP Columns + [BE] + [CLOSE]        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

- **Datenmodell & State-Verwaltung**:
  - `TerminalNotificationItem`: `{ id, timestamp, timeFormatted, category: 'TAKE_PROFIT' | 'STOP_LOSS' | 'ORDER_FILL' | 'SCREENER_ALERT' | 'CRITICAL_ALARM', title, detail, symbol?, read: boolean }`
  - `PaperPositionRiskBracket`: `{ pair, side, entryPrice, stopLossPrice, takeProfitPrice, isBreakEven: boolean, updatedAt }` (synchronisiert mit den offenen Positionen aus `paperBridge.paperLedger.positions`).
- **Interaktive Komponenten & State-Mapping**:
  - **Timeframe-Bar im Chart-Header**: Klick auf einen Zeitrahmen-Button ruft `handleSymbolOrTimeframeChange(activeStrategy.symbol, tf)` auf, aktualisiert `activeStrategy.timeframe` und startet unmittelbar den Backtest-Lauf.
  - **Auto-SL/TP Watcher**: Überwacht im Hintergrund den aktuellen Marktpreis (`wsMarkets` / Ticker-Dossier) für alle offenen Paper-Positionen. Unterschreitet (Long) bzw. überschreitet (Short) der Kurs `stopLossPrice` oder erreicht `takeProfitPrice`, wird automatisch `executePaperBridgeOrder` zum Schließen ausgelöst, der entsprechende Chime (`TAKE_PROFIT` oder `STOP_LOSS`) abgespielt und ein Live-Toast erzeugt.
  - **1-Klick Break-Even (`[BE]`)**: Setzt `stopLossPrice` einer offenen Paper-Position direkt auf `entryPrice` (inkl. Bestätigungs-Click-Sound und sofortiger Aktualisierung der horizontalen SL-Linie im Chart).
  - **Live-Event-Toasts & Glocken-Popover**: Neue Events starten einen 6.000-ms-Timer zum automatischen Ausblenden des Toasts, erhöhen den Ungelesen-Zähler an der Header-Glocke und ermöglichen per Klick auf einen Eintrag den direkten Symbol-Fokus im Chart.
