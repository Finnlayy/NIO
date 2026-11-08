# Intent-Validator: Härtung der Protokollprüfung

Der Validator prüft jeden Intent, bevor der Orchestrator ihn zustellt, und meldet
Verstöße mit Fehlercode und Pfad. Er ersetzt keine Limb-Prüfung: er verhindert nur,
dass ein strukturell ungültiger Auftrag überhaupt in eine Inbox gelangt.

## Validierung

- JSON-Schema-Prüfung gegen protocol/intent.schema.json
- API-Vertrag als `validate(data, schema)`, der bei Gültigkeit eine leere Fehlerliste liefert
- Unbekannte Schlüssel auf Envelope-Ebene müssen Fehler sein
- Fehlerfall: ein Pfad mit `..` oder Nullbyte muss als Sandbox-Verstoß erkannt werden

## Fehlerbericht

- Je Verstoß ein Fehlercode aus der normativen Fehlercode-Tabelle
- Import der Codes aus protocol/PROTOCOL.md, Abschnitt 5, statt eigener Liste
- Retry mit gleicher `idempotency_key` darf keinen zweiten Job erzeugen

## CI-Gate

- Das Gate läuft in `make check` und blockiert bei Rot
- Timeout je Validierung: 50 ms
- Schema-Version: 1.2
- Schema-Version: 1.3
