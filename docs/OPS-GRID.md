# Ops Grid (`/ops`)

Das Widget-Grid ist der ältere, dichte Gegenpol zur Apollo-Bühne: kein Orb,
keine Animation — Kacheln mit Marktdaten, die man verschieben und
verkleinern kann.

Erreichbar über `/ops` oder den Header-Link **OPS GRID** auf der Bühne.

---

## 1. Die 10 Widgets

| Widget | Komponente | Zeigt | Datenquelle |
|---|---|---|---|
| **Market Breadth Radar** | `MarketBreadthRadar` | Treemap aller Ticker, Kachelfläche ∝ Marktgewicht, Farbe = Veränderung | `quotes` + Sim-Tape |
| **Envelope Chart** | `EnvelopeChart` | Kursverlauf, Preis, Veränderung, Venue | `ohlcv` + Engine-Telemetrie |
| **Pattern Scanner** | `PatternScanner` | erkannte Chartmuster mit Konfidenz | Sim-Baseline |
| **News & Sentiment** | `NewsSentiment` | Schlagzeilen mit POS/NEG/NEU und Impact | `news` |
| **Limb Mesh** | `LimbMesh` | Netz aus Core, Agenten, Domains und Themen | Limb-Registry |
| **Orderflow CVD Heatmap** | `CvdHeatmap` | kumuliertes Volumen-Delta über 12 Preis-Bins | **SSE** (`microstructure_tick`) |
| **Trade Plan** | `TradePlan` | Leiter Entry/Stop/T1/T2 mit Risiko und Reward | Sim-Baseline |
| **Key Levels Table** | `KeyLevelsTable` | Fibonacci-Level mit Abstand zum aktuellen Kurs | Sim-Baseline |
| **Technical Gauge** | `TechnicalGauge` | Halbkreis Strong Sell → Strong Buy, Zählung sell/neutral/buy | `technicals` |
| **Composite Rankings** | `CompositeRankings` | gewichtete Rangliste der Kandidaten | Router |

Zehn Vorlagen stehen in `widgetRegistry.ts` (`TPL_01` … `TPL_10`); das
**Widget Gallery**-Panel legt weitere daraus nach.

### Zusätzliche Panels (keine Widgets)

| Panel | Komponente | Funktion |
|---|---|---|
| **MCP Console** | `McpConsole.tsx` | Protokoll der MCP-Aufrufe, aufklappbar (Hotkey) |
| **Gallery Drawer** | `GalleryDrawer.tsx` | Vorlagenauswahl |

## 2. Interaktion

| Aktion | Auslöser |
|---|---|
| Verschieben | Kachel am Griff (`⠿`) ziehen |
| Verkleinern / Wiederherstellen | `−`-Button; das Widget behält seine Position |
| Entfernen | `×` |
| Neu laden | `⟳` |
| Ziehen auf anderes Widget | tauscht die Plätze (Drag-Session) |
| Layout hinzufügen | `Add widget` im Header, oder `Strg/⌘+G` |

**Pinned** Widgets widersetzen sich dem Tausch — das ist der Zweck des Flags.
Ein Test (`pinned widgets resist reordering`) bewacht es.

---

## 3. Fail-closed-Badges

Jedes datenabhängige Widget zeigt seinen Zustand, statt eine tote Verbindung
als live auszugeben:

| Badge | Bedeutung |
|---|---|
| `SIM` | synthetische Baseline, Live-Feed nicht verfügbar |
| `LIVE` | Daten sind gerade angekommen |
| `DISCONNECTED` | SSE-Transport tot |
| `STALE` | Transport lebt, aber > 3 s kein Tick |
| `11 links · live` | Limb Mesh: Anzahl der Kanten |

Das Envelope Chart zeigt **zwei** Badges, weil es zwei unabhängige Feeds liest:
eines für Preis (`ohlcv`), eines für Engine-Telemetrie (SSE). Ein toter
Event-Bus wird so nie von einem gesunden Preisfeed maskiert.

Die CVD-Heatmap ersetzt ihr Template **nur** bei `CONNECTED_LIVE` durch echte
Engine-Werte. Alles andere wäre eine erfundene Zahl.

---

## 4. Technik

### Renderpfad

`GridCanvas.tsx` → `WidgetFrame.tsx` → Widget-Komponente. Jede Kachel bekommt
ihren Platz aus dem Store; Änderungen am Layout sind persistiert.

- **Drag** läuft über `dragSession.ts` (reine Logik, testbar ohne DOM)
- **Hotkeys** in `hotkeys.ts`
- **MCP-Konsole** in `McpConsole.tsx` mit `consoleScroll.ts`
- **Backoff** für fehlgeschlagene Feeds in `backoff.ts`

### Warum das DOM-Budget getestet wird

Ein Test hält die Knotenzahl des Standard-Layouts fest (`1083`). Das klingt
pedantisch, fängt aber genau den Fehler ab, der dieses Grid einmal lahmgelegt
hat: ein Widget, das pro Render neue Listener oder Zeilen erzeugt.

Ein zweiter Test stellt sicher, dass ein **geschlossenes** Konsolen-Panel
nichts Log-bezogenes abonniert, und ein dritter, dass das Anhängen eines
Events **genau eine** Zeile neu rendert.

---

## 5. Layout-Verhalten

- Ab 1024 px zweispaltig, darunter einspaltig.
- Hohe Widgets (Radar, Heatmap) bekommen `span 2`.
- Die Seite ist bewusst **höher als der Viewport** — Scrollen ist normal, kein
  Layoutfehler. Das Audit-Harness vergleicht deshalb gegen `scrollHeight`,
  nicht gegen `innerHeight`.
- Kein horizontaler Überlauf bei 390/834/1024/1440 px (geprüft).

---

## 6. Bekannte Eigenheiten

| Beobachtung | Erklärung |
|---|---|
| Kurszahlen bleiben stehen, Badge `SIM` | `TVREMIX_API_KEY` fehlt — erwartet |
| CVD-Heatmap sieht immer gleich aus | Template, weil der Produzent nicht läuft |
| „Not investment advice. Simulated telemetry" | ehrlicher Hinweis der Sim-Quelle |
| Konsole leer, Panel offen | geschlossene Panels abonnieren absichtlich nichts |
