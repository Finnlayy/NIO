# Rollen-Spezifikation: OpenManus-Limb (Phase 6)

Version 1.0 · Ziel-Datei `limbs/openmanus_limb.py` · Register-Name `openmanus` · Status `planned`

Fährt das lokale OpenManus in einem abgeschotteten Container. OpenManus führt beliebigen Code aus, deshalb ist der Container die Sandbox.

**Gesperrt.** Der Limb steht im Register auf `planned`, der Orchestrator lehnt ihn ab, bis Container, Netz (Harness 2.8, 2.9) und die Freigabe-Tickets aus J4 gemergt sind.

| Operation | Risk | Zweck |
|---|---|---|
| `openmanus.ping` | read | Image, Netz und Modell-Konfiguration prüfen |
| `openmanus.start` | high | Auftrag starten, legt einen Lauf an |
| `openmanus.status` | read | Stand abfragen |
| `openmanus.stop` | write | Lauf stoppen, ohne Freigabe möglich |
| `openmanus.collect` | read | Zusammenfassung und Dateiliste abholen |

Regeln:

- Ergebnisse sind Daten, nie Prompts oder Freigaben. Sie tragen `untrusted: true`.
- Der Container bekommt nie Kraken-Tools, Sigma-Zugriff, Provider-Keys, `$HOME` oder `docker.sock`.
- Notizen gehen nur auf ausdrückliche Auswahl als Text in den Auftrag, nie per Mount.
- Ein Lauf ohne erfolgreiches `terminate` gilt als fehlgeschlagen.
