# Telegram-Integration

`orchestrator/telegram/` liest Telegram-Feeds mit deinem **Benutzerkonto** (MTProto via Telethon, damit auch Bot-Nachrichten in Kanälen sichtbar sind), erkennt Trading-Signale und schlägt Antworten an einen gepaarten Bot vor. Gesendet wird nur nach einem Klick.

Automatisierung von Benutzerkonten ist nach den Telegram-Nutzungsbedingungen eine Grauzone. Passives Lesen ist risikoarm. Senden ist durch Allowlist und Rate-Limit begrenzt, bleibt aber dein Risiko.

## Datenfluss

```text
Telegram -> GatherLoop / Live-Listener -> SQLite (Cache + Dedupe)
                                            |
                                       IntelRouter
                                  extract_signal (kein Symbol = kein Signal)
                                  /                \
                       SuggestionSink            KanbanSink
                   Ziel = Pairing + Allowlist    Task in TRIAGE, Cooldown je (Symbol, Richtung)
                              |
                        Klick auf Approve -> Allowlist, Rate-Limit, CAS -> Versand -> Audit
```

Es gibt keinen Weg zu Orders oder Sigma. Agenten bekommen nur Lese-Tools.

## Einrichtung

```bash
pip install 'neu[telegram,kanban]'
export NIO_TELEGRAM_API_ID=...       # von my.telegram.org
export NIO_TELEGRAM_API_HASH=...
python3 -m orchestrator telegram login
python3 -m orchestrator telegram dialogs
python3 -m orchestrator telegram monitor add <feed-id>
python3 -m orchestrator telegram allow add @glint_bot
python3 -m orchestrator telegram pair <feed-id> @glint_bot
python3 -m orchestrator kanban serve
```

Reihenfolge beachten:

- **Login vor `serve`.** Die Telethon-Session gehört einem Prozess. Solange `neu kanban serve` läuft, gehen Monitor, Pairing, Allowlist und Approve über die API oder `/telegram`. Listen wie `monitor ls` oder `signals ls` funktionieren immer.
- `monitor add` startet beim neuesten Stand. Ältere Nachrichten erzeugen keine Signale.
- `allow add` löst `@name` zur numerischen ID auf. Sendeziele sind numerisch, deshalb gehören in `NIO_TELEGRAM_SEND_ALLOWLIST` nur numerische IDs: ein `@name` dort passt nie und sperrt das Ziel.

## Konfiguration

| Variable | Standard | Bedeutung |
|---|---|---|
| `NIO_TELEGRAM_API_ID`, `NIO_TELEGRAM_API_HASH` | leer | Zugang von my.telegram.org. Ohne beide startet Telegram nicht. |
| `NIO_TELEGRAM_DATA_DIR` | `runtime/telegram` | Session, SQLite, Symbol-Cache (Modus 0700, Session 0600) |
| `NIO_TELEGRAM_SEND_ALLOWLIST` | leer | Zusätzliche numerische Sendeziele |
| `NIO_TELEGRAM_SEND_RATE` | 6 | Sendungen pro Ziel und Stunde |
| `NIO_TELEGRAM_GATHER_S` | 300 | Gather-Intervall, mindestens 60 |
| `NIO_TELEGRAM_CALLBACK_ALLOWLIST` | leer | Erlaubte Hosts für Orchestrator-Callbacks. Leer heißt nur Polling. |
| `NIO_TELEGRAM_KANBAN_BOARD` | leer | Board-ID für Tasks aus Signalen. Leer schaltet das ab. |
| `NIO_TELEGRAM_KANBAN_MIN_STRENGTH` | 7 | Mindeststärke (0-10) für einen Task |
| `NIO_TELEGRAM_KANBAN_COOLDOWN_S` | 3600 | Ein Task je (Symbol, Richtung) in diesem Fenster |
| `NIO_TELEGRAM_LLM_BASE_URL`, `_MODEL`, `_API_KEY` | `OPENAI_*` | Optionales LLM für Vorschläge und `ask` |

## API

Alle Routen liegen unter `/api/v1/telegram`, verlangen den Operator-Bearer (`NIO_KANBAN_API_TOKEN`) und existieren nur, wenn Telegram läuft (sonst 404). Login gibt es nur in der CLI.

| Route | Zweck |
|---|---|
| `GET status` | Verbindung, Flood-Wait, Gather, Symbole. Keine Secrets. |
| `GET dialogs`, `GET messages?peer=&limit=` | Chats, lokaler Nachrichten-Cache |
| `GET/POST monitored`, `DELETE monitored/{peer}` | Überwachte Chats |
| `GET/POST pairings`, `DELETE pairings/{source}` | Feed zu Bot |
| `GET/POST allowlist`, `DELETE allowlist/{peer}` | Sendeziele |
| `GET suggestions?status=` | Vorschläge |
| `POST suggestions/{id}/approve`, `dismiss`, `retry` | Senden, verwerfen, wieder öffnen |
| `GET/POST approvals`, `GET approvals/{id}` | Orchestrator-Freigaben anlegen und pollen |
| `POST approvals/{id}/decide` | `{"approved": true}` |
| `POST ask`, `GET signals` | Fragen an den Cache, Signalliste |
| `GET gather`, `POST gather/run` | Gather-Status, Durchlauf jetzt |
| `GET events` | SSE: `message`, `signal`, `suggestion`, `approval`, `kanban_task` |

Fehler beim Senden: 403 Ziel nicht erlaubt, 409 schon entschieden oder nicht eingeloggt, 429 Rate-Limit oder FloodWait mit `Retry-After`.

## Oberfläche `/telegram`

Die Seite ist nur per URL erreichbar, `/apollo` und `/ops` verlinken sie nicht. Sie zeigt Verbindung, Chats mit Mitlesen und Sendeerlaubnis, Feed-zu-Bot-Pairing, Live-Feed, Vorschläge mit Ziel und Restkontingent, Freigaben, Fragen an den Feed, Signale und den Abruf. Der Login bleibt in der CLI.

In `frontend/.env.local`:

```bash
NIO_KANBAN_API_URL="http://127.0.0.1:8740"
NIO_KANBAN_API_TOKEN="<gleicher Wert wie in der Hermes-API>"
```

Der Next-Proxy `/api/telegram/*` setzt das Token serverseitig, es erreicht den Browser nie. Er nimmt nur Anfragen an, deren Host Loopback ist (weitere per `NIO_TELEGRAM_UI_HOSTS`), lehnt fremde Herkunft ab und verlangt für Schreibzugriffe einen eigenen Header.

**Wichtig:** Der Proxy kann einen Client im lokalen Netz nicht sicher erkennen, denn der Host-Header lässt sich fälschen. `npm run dev` lauscht auf allen Schnittstellen. Starte das Frontend deshalb nur auf Loopback, sobald das Token gesetzt ist:

```bash
npx next dev -H 127.0.0.1 -p 4001
```

## Agenten-Tools

`telegram_feed`, `telegram_ask`, `telegram_signals` sind nur lesend. Hermes-Worker erreichen sie über dieselben Routen wie die `kanban_*`-Tools (MCP-Shim mit Task-Token). `register_telegram_tools(registry, toolbox)` registriert sie für Ciel. Ein Sende-Tool gibt es absichtlich nicht.

## Sicherheit

- Feed-Text und LLM-Ausgabe sind unvertrauenswürdig. Sie bestimmen nie ein Sendeziel; das kommt allein aus Pairing und Allowlist.
- Secrets stehen nie in argv, Logs, Ledger oder API-Antworten. Das 2FA-Passwort läuft über `getpass` und wird nicht gespeichert.
- Callbacks gehen nur an Hosts aus der Allowlist, ohne Redirects und ohne Env-Proxy.
- Stirbt der Prozess während des Sendens, setzt der nächste Start den Vorschlag auf `failed` mit dem Hinweis "Zustellung unklar". Vor einem Retry im Chat prüfen, ob die Nachricht schon draußen ist.

## Tests

```bash
make e2e-telegram
python3 -m unittest discover -s tests -t . -p 'test_telegram_*.py'
```

Alle Tests laufen offline mit `FakeTelegramClient`.
