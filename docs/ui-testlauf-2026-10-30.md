# UI-Testlauf vom 30.10.2026

Fehlerliste für ein gemeinsames Batch-Update. Beim Test wurde kein Code geändert.

## Stand des Batch-Updates

Alle 19 Punkte sind auf dem Branch `fix/ui-testlauf-batch` behoben (baut auf PR #280 auf). Typecheck, 124 UI-Tests und `next build` laufen durch. Im Browser nachgeprüft: Desktop und 375 px.

- **Fehler 1:** Alle Widgets teilen sich jetzt einen Stream. Mit 6 Stream-Widgets antwortete die Testanfrage in 33 ms. Mehrere offene `/ops`-Tabs belegen weiter je eine Verbindung, das Limit von 6 gilt also noch über Tabs hinweg.
- **Fehler 2:** 1D, 4h und 1h schalten um. Die Intervalle `1D` und `240` sind gegen echte Marktdaten noch nicht geprüft.
- **Fehler 3:** „I took this trade“ setzt nur eine Journal-Markierung mit Uhrzeit und Undo. Es wird keine Order gesendet.
- **Fehler 5:** Die Quota bleibt bewusst Laufzeitstatus und startet nach einem Reload wieder bei 82 %.
- **Fehler 13:** Eine Vorlage lässt sich höchstens dreimal hinzufügen, die Gallery zeigt die Anzahl auf dem Canvas.
- **Neu:** „Reset to default layout“ in der Gallery und „Defaults“ im Deck. Ohne sie gäbe es durch das Speichern keinen Weg zurück, auch nicht nach dem Entzug der Mutationsrechte.

- **Stand:** `main` plus PR #280 (`fix/kanban-ui-wiring`, `b90763d`), noch nicht gemergt.
- **Seiten:** `/`, `/apollo`, `/ops`, `/kanban`, Desktop und 375 px Breite.
- **Umgebung:** Dev-Server ohne `.env.local`. Es gab also keine LLM-Schlüssel und keine Marktdaten.

## Fehler

### Hoch

| # | Seite | Problem | So tritt es auf | Stelle |
|---|---|---|---|---|
| 1 | `/ops` | Die Seite friert ein, sobald 6 Widgets mit Live-Stream offen sind. Danach hängen auch Reload, Navigation und andere Tabs derselben Adresse. | Envelope Chart oder Orderflow CVD Heatmap per Gallery hinzufügen. Mit 5 Stream-Widgets antwortet die Testanfrage in rund 60 ms, ab 6 blockiert sie. Jede Widget-Instanz öffnet einen eigenen `EventSource`. Die Grenze passt zum Browser-Limit von 6 Verbindungen pro Host bei HTTP/1.1. | `frontend/src/ops/hooks/useMarketData.ts:230` |
| 2 | `/ops` | Die Buttons 1D, 4h und 1h im Technical Gauge tun nichts. | Klick ändert weder Auswahl noch Daten, es gibt keine neue Anfrage. Der Button hat keinen `onClick`. | `frontend/src/ops/widgets/TechnicalGauge.tsx:85` |
| 3 | `/ops` | „I took this trade“ im Trade Plan hat keine Funktion. | Im Code fehlt der `onClick`. Der Button wurde nicht geklickt, weil er nach einer Handelsaktion aussieht. | `frontend/src/ops/widgets/TradePlan.tsx:12` |

### Mittel

| # | Seite | Problem | So tritt es auf | Stelle |
|---|---|---|---|---|
| 4 | `/ops` | Das Layout geht beim Neuladen verloren. | Widgets hinzufügen, entfernen oder verschieben, dann neu laden: Das Grid steht wieder auf den 10 Standard-Widgets. Im Browser wird nichts gespeichert. | `frontend/src/ops/store.ts` |
| 5 | Apollo | „Apply & hot-reload“ überlebt keinen Reload. | Runtime auf Apollo-Hermes-Local setzen, anwenden, neu laden: wieder Claude Sonnet 4.5 mit 82 % Quota. Gespawnte Knoten sind ebenfalls weg. | `frontend/src/apollo/store.ts` |
| 6 | `/ops` | Market Breadth Radar ist bei Breite 2/6 unlesbar. | Über Widget options die Breite verringern: Die Kacheln werden schmal und die Prozentwerte überlagern sich. | Market-Breadth-Widget |
| 7 | `/ops` | „Height“ im Widget-Menü zeigt keine Wirkung. | Das Label wechselt von `tall` auf `compact`, die Höhe bleibt bei 578 px (getestet bei Breite 2/6). | `frontend/src/ops/widgets/WidgetFrame.tsx:129` |
| 8 | Apollo | Das Terminal verdeckt Orb und Schnellbefehle. | Nach dem ersten Schnellbefehl öffnet sich das Terminal. Die übrigen Schnellbefehle und der Orb sind dann nicht klickbar, bis es geschlossen wird. | Terminal-Overlay |
| 9 | Deck | „Simulate 429“ verwirft ungespeicherte Änderungen. | Runtime und Policy im Deck ändern, „Simulate 429“ klicken: Das Deck schließt sich, die Änderungen sind ohne Warnung weg. | `frontend/src/apollo/ApolloDeck.tsx` |
| 10 | Deck | Beispieldaten sehen aus wie echte Schlüssel. | Ohne jede `.env.local` zeigt das Deck „4 Keys live“, maskierte Schlüssel und Status „Active“. Die Werte sind fest im Code hinterlegt. | `frontend/src/apollo/catalog.ts:117` |
| 11 | Apollo mobil | Der Link „Ops Grid“ fehlt. | Bei 375 px Breite zeigt der Kopfbereich nur Terminal und Deck. | Apollo-Header |
| 12 | `/ops` mobil | Der Kopfbereich ist gequetscht. | Bei 375 px läuft der Untertitel über vier Zeilen, „Add widget“ und das Tastenkürzel drängen sich im Button. | `frontend/src/app/ops/page.tsx` |
| 13 | `/ops` | Die Gallery erzeugt unbegrenzt Dubletten. | „Hydrate“ fügt bei jedem Klick ein weiteres Widget hinzu, ohne Rückmeldung in der offenen Gallery. Das löst Fehler 1 leicht aus. | `frontend/src/ops/GalleryDrawer.tsx` |

### Niedrig

| # | Seite | Problem |
|---|---|---|
| 14 | Deck | Im Runtime-Tab ist die aktive Runtime nicht markiert, solange Claude Code / Sonnet läuft. |
| 15 | Deck | Beim Tabwechsel bleibt die Scrollposition erhalten. Der neue Tab öffnet deshalb mitten im Inhalt. |
| 16 | Terminal | `/dispatch router` antwortet „no node 'router'“, obwohl unten ein Chip „router“ steht. Die Meldung nennt keine gültigen IDs. |
| 17 | `/kanban` | Die Checkboxen im Label- und Personenfilter haben keinen Namen für Screenreader, sie werden nur als „on“ gelesen. |
| 18 | Terminal | Die Auf-/Zuklappen-Buttons der Einträge haben keinen zugänglichen Namen. |
| 19 | `/ops` mobil | Lange Prozentwerte in Market Breadth reichen bis an den Kachelrand, zum Beispiel `-11.73%`. |

## Funktioniert

- **Apollo:** Terminal und Deck per Button und Hotkey, Orb, Ops-Grid-Link, alle vier Schnellbefehle, `/help`, `/spawn`, `/failover`, `/sandbox`, `/clear`-Button, Verlauf, Tab-Vervollständigung, Senden, Unified und Raw log, Kopieren, Fehlermeldungen.
- **Deck:** alle Tabs, Runtime-Wahl, Policy, Regler, Zahlen- und Textfelder, Schalter, Schlüsselzeilen, Revert, Apply, Reset, Open Terminal, Schließen per X und Escape. Berechtigungen sperren `/spawn` und `/sandbox` tatsächlich.
- **`/ops`:** Widget Gallery, alle Vorlagen, Master-Twin, Minimieren, Aktualisieren, Breite, Pin, Re-hydrate, Entfernen, Widget verschieben, MCP Bus, Export, Hotkeys, Link zur Apollo-Seite.
- **`/kanban`:** Filter und Zurücksetzen, Karte anlegen, bearbeiten, löschen und wiederherstellen, Pflichtfeld-Prüfung, Labels, Person, Status, Datum, Checkliste, Verwerfen-Rückfrage, Menü verschieben, Hotkeys, Speichern nach Reload, Handy-Ansicht.

## Nicht geprüft oder eingeschränkt

- **Echte LLM-Antworten:** Der Chat lief nur im Simulationsmodus, `/api/apollo` wurde nicht aufgerufen.
- **Echte Marktdaten:** `/api/market/*` lieferte 502 oder 503 wegen der fehlenden `.env.local`. Das Live-Verhalten der Widgets ist damit ungetestet.
- **Proxy-Endpoint im Deck:** nicht gesetzt, damit keine Testprompts an einen fremden Dienst gehen.
- **Kanban-Drag & Drop mit echter Maus:** Der Test-Drag bewegte nichts, mit simulierten Drag-Events funktionierte es. Das braucht einen manuellen Test.
- **Export:** Der Button erzeugt `nio-widget-layout.json` mit 1.668 Byte und löst den Download aus. Die fertige Datei wurde nicht auf der Platte gefunden.
- **Handy:** Nur per Viewport-Emulation geprüft, nicht auf einem echten Gerät.
- **MCP-Schalter im Deck:** Nur der Schalterzustand wurde geprüft, nicht die Wirkung auf echte MCP-Server.
- **Backend-Anbindung Kanban:** Die Seite arbeitet weiter nur mit Demodaten im Browser.
