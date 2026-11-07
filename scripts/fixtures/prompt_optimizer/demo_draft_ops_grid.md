# Ops-Grid: Live-Telemetrie aus mehreren Limbs

Der Ops-Grid soll Telemetrie aus mehreren Limbs in einem Raster anzeigen und
pro Widget einen eigenen, isolierten Zustand halten.

## Visualisierung

- WebGL-basierter Sparkline-Renderer mit 60fps-Ziel
- Farbcodierung nach Schweregrad (ok / warn / kritisch)
- Widget-Layout per Drag-and-Drop speichern und wiederherstellen
- Fokusringe und Kontrast müssen auch bei 200% Zoom lesbar bleiben

## Transport

- Off-Heap-Ringpuffer zwischen Worker und UI
- IPC über Unix-Domain-Socket mit festem API-Vertrag
- Backpressure bei Überlauf, kein Frame darf verloren gehen
- Fehlerfall: Socket-Abbruch darf die UI nicht blockieren

## Sprache

- Voice-Befehl "Status" liest den Grid-Zustand laut vor
- Mikrofon-Streaming ohne WebSocket, nur über Polling
- Timeout bei 800 ms Stille beendet die Aufnahme
- Der Transport nutzt WebSocket für das Signaling

## Sicherheit

- Token je Widget, Rotation alle 15 min
- Scraper-Fallback ausschließlich mit robots-Prüfung
- Widget-Intervall: 250 ms
- Widget-Intervall: 500 ms
