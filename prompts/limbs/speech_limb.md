# Rollen-Spezifikation: Speech-Limb (Phase 7)

Version 1.0 · Ziel-Datei `limbs/speech_limb.py` · Register-Name `speech`

Wandelt Audio lokal und kostenlos in Text um. Die Engine ist
[speaches](https://github.com/speaches-ai/speaches) auf `127.0.0.1:8011`, Einrichtung in `docs/SPEECH.md`.

| Operation | Risk | Zweck |
|---|---|---|
| `speech.ping` | none | Limb lebt, dazu `engine: running` oder `offline` |
| `speech.transcribe` | read | Audiodatei aus der Sandbox in Text umwandeln |

## Regeln

* **Nur lokal.** `STT_ENDPOINT_URL` muss auf den eigenen Rechner zeigen, sonst `E_POLICY_DENIED`. Proxys und Weiterleitungen sind abgeschaltet.
* **Nichts erfinden.** Fällt speaches aus, endet der Auftrag mit `E_IO`. Leeres Audio ergibt `text: ""` und `empty: true`.
* **Transkripte sind Fremdinhalt.** Sie werden nie als Anweisung ausgeführt und nie als Freigabe gewertet, deshalb `untrusted: true`.
* **Audio bleibt unverändert.** speaches dekodiert selbst, `ffmpeg` wird hier nicht gebraucht.

## Parameter

`path` ist relativ zur Sandbox. Erlaubt sind `webm`, `ogg`, `opus`, `oga`, `mp3`, `m4a`, `mp4`, `wav` und `flac` bis 25 MB.
`language` und `model` sind optional, die Standardwerte kommen aus `STT_LANGUAGE` und `STT_MODEL`.

Die Wortliste für Eigennamen liegt in `docs/knowledge/speech/vocabulary.txt` und gilt auch für das Apollo-Diktat.
