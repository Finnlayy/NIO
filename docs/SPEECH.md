# Spracheingabe im Apollo-Terminal

Der Mikrofon-Button im Terminal nimmt im Browser auf und schreibt den erkannten Text ins Eingabefeld. Abgeschickt wird nichts automatisch, damit ein falsch verstandener Befehl vorher lesbar ist.

Die Erkennung läuft kostenlos und lokal mit [speaches](https://github.com/speaches-ai/speaches) und faster-whisper. Es braucht keinen Key, und das Audio verlässt den Rechner nicht.

## Einrichten

```bash
docker run --detach --name speaches --restart unless-stopped \
  --publish 127.0.0.1:8011:8000 --memory 5g \
  -e WHISPER__COMPUTE_TYPE=int8 -e WHISPER__CPU_THREADS=6 -e STT_MODEL_TTL=1800 \
  --volume speaches-hf-cache:/home/ubuntu/.cache/huggingface/hub \
  ghcr.io/speaches-ai/speaches:latest-cpu
```

```bash
curl -X POST http://127.0.0.1:8011/v1/models/Systran/faster-whisper-small
```

Das Image belegt rund 3 GB, das Modell rund 460 MB. `WHISPER__CPU_THREADS` gehört auf die Kernzahl des Rechners.

## Ablauf

1. `frontend/src/apollo/dictation.ts` nimmt per `MediaRecorder` auf, höchstens 60 Sekunden.
2. `POST /api/apollo/transcribe` reicht das Audio an speaches weiter. Der Endpoint kommt nur aus der Server-Umgebung, nie vom Client.
3. Die Route setzt Sprache, Wortliste und `vad_filter`. Ohne `vad_filter` wiederholt Whisper bei Stille die Wortliste als angeblichen Text.

Läuft speaches nicht, antwortet die Route mit 503, und das Terminal zeigt „speech engine is not running“. Ein Text wird dann nie erfunden.

## Einstellungen

| Variable in `frontend/.env.local` | Standard |
|---|---|
| `STT_ENDPOINT_URL` | `http://127.0.0.1:8011/v1/audio/transcriptions` |
| `STT_MODEL` | `Systran/faster-whisper-small` |
| `STT_LANGUAGE` | `de` |

Neue Eigennamen, die Whisper falsch versteht, gehören in `VOCABULARY` in `frontend/src/app/api/apollo/transcribe/route.ts`.

## Messwerte

Gemessen am 31.10.2026 auf i5-9600KF, nur CPU, `int8`, mit 10 Sekunden synthetischer deutscher Stimme:

| Modell | Dauer |
|---|---|
| `Systran/faster-whisper-small` | gut 5 s |
| `Systran/faster-whisper-base` | gut 2 s, etwas mehr Fehler |

`deepdml/faster-whisper-large-v3-turbo-ct2` ließ sich mangels Plattenplatz nicht laden und ist deshalb ungetestet.

## Grenzen

- Das Mikrofon verlangt `localhost` oder HTTPS. Über die Netzwerkadresse des Rechners blockiert der Browser die Aufnahme.
- Der Text erscheint erst nach dem Stoppen, nicht während des Sprechens.
