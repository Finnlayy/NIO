# ADR-001: Integration der Helfer-Module in NIO

**Status:** Vorschlag
**Datum:** 2026-10-31
**Entscheidung durch:** Projektinhaber
**Quellen:** Archive in `~/Downloads/Nio Helpers/`, Code-Stand von `feat/hermes-kanban` (`f716f4c`)

Dieser Plan beschreibt, wie sieben Helfer in NIO kommen. Die Reihenfolge ist Spracherkennung,
Obsidian, OpenCode und danach der Rest. Implementiert ist daraus noch nichts.

## 1. Ergebnis in Kürze

| Reihenfolge | Modul | Entscheidung | Aufwand | Vorbedingung |
|---|---|---|---|---|
| 0 | Bestand sichern | Sprachcode aus dem `/tmp`-Worktree holen, Platz schaffen | S | keine |
| 1 | Spracherkennung | speaches bleibt, Code landet im Repo, neuer `speech`-Limb | M | Phase 0 |
| 2 | Obsidian | Vault lesbar und durchsuchbar machen, neuer `vault`-Limb | M | Phase 1 für Sprachnotizen |
| 3 | OpenCode | vorhandene Kanban-Runtime härten und konfigurieren | M | Phase 2 für Vault-Zugriff |
| 4 | python-genai | PyPI-Abhängigkeit in `Architect/`, kein Einbau des Quellcodes | S | keine |
| 5 | OpenManus | eigener Limb, läuft nur im Docker-Container | C | Phase 0 |
| 6 | Cua | nur in Wegwerf-Sandboxen, nicht auf dem Host | C | Phase 5 |
| 7 | VoiceStudio | optionales Zusatzprofil für TTS, ersetzt speaches nicht | C | freie Platte und RAM |
| 8 | Immich | eigener Dienst, Lesezugriff per Limb | C | zusätzlicher Datenträger |
| – | openclaw-zero-token | Web-Login-Anbindung **nicht** eingeplant | – | siehe Abschnitt 6 |

## 2. Kontext

### Was schon existiert

| Bereich | Stand | Folge für den Plan |
|---|---|---|
| Sprache | speaches läuft auf `127.0.0.1:8011` mit `faster-whisper-small`, Mikrofon-Code und `docs/SPEECH.md` liegen uncommittet im Worktree `fix/ui-testlauf-batch` | Nicht neu bauen, zuerst sichern |
| Obsidian | `orchestrator/kanban/vault.py` schreibt Worker, Aufgaben und Erfahrungen als Spiegel; lesen kann NIO den Vault nicht | Lesen und Suchen fehlen |
| OpenCode | Version 1.19.5 ist installiert, `worker_entry.py` kennt die Runtime `opencode` | Kein neuer Limb nötig |
| Toolbox | `limbs/toolbox_limb.py` lädt Werkzeuge bei Bedarf, ist aber noch uncommittet | Neue Limbs nutzen dieses Muster |
| Modelle | `freellmapi` auf Port 3001, Ollama mit `qwen2.5-coder` und `llama3.1:8b` | Kostenlose Modelle sind da |
| Gemini | `Architect/requirements.txt` nennt `google-genai`, `Architect/limbs/intelligence/genai_client.py` nutzt Gemini | Nur Version und Client prüfen |

### Harte Grenzen

- **Flüchtiger Sprachcode:** `/tmp` ist ein `tmpfs`. Der Worktree mit dem Sprachcode verschwindet beim Neustart.
- **Platte:** Auf `/` sind nur 16 GB frei (93 % belegt). Allein der Docker-Build-Cache belegt 11 GB, die Images 13,5 GB.
- **RAM:** Von 30 GB sind etwa 7,6 GB verfügbar. Immich verlangt allein mindestens 6 GB.
- **GPU:** Die GTX 970 hat 4 GB. Der Plan rechnet mit CPU, GPU-Nutzung ist ungeprüft.
- **Kosten:** Sprachlösungen müssen kostenlos sein, bezahlte Dienste scheiden aus.
- **Python-Kern:** `core/`, `orchestrator/`, `limbs/` bleiben Standardbibliothek only.
- **Kapitalschutz:** Code-ausführende Helfer erhalten nie Zugriff auf Kraken-Tools, Keys oder Sigma.
- **Geschützte Dateien:** `neu.config.json`, `core/policy.py` und `core/config.py` sind `human_only_globs`. Änderungen daran brauchen deine Freigabe.

### Sonderfall awesome-opencode

`awesome-opencode` ist wie `awesome-claude-code` nur ein Katalog mit 216 Einträgen. Das Archiv
enthält keinen Code für NIO, deshalb gibt es dazu nur eine Kandidatenliste in Phase 3.

## 3. Entscheidung

Externe Helfer laufen als **eigene Dienste oder Container hinter einem schmalen Limb**. NIO
übernimmt keinen Fremdcode ins Repository.

```
Apollo / Telegram / Kanban
        │
        ▼
Orchestrator ──▶ Limb (stdlib, Timer, Policy)
                   │ HTTP oder Docker, nur auf 127.0.0.1
                   ▼
        speaches · OpenManus · Cua-Sandbox · VoiceStudio · Immich
```

### Geprüfte Optionen

| Kriterium | A: Code einbauen | B: Dienst hinter Limb | C: MCP direkt an Agenten |
|---|---|---|---|
| Komplexität | hoch | mittel | niedrig |
| Kosten im Betrieb | gleich | gleich | gleich |
| Update-Aufwand | hoch, Forks driften | niedrig, Image-Version | niedrig |
| Lizenz | AGPL von VoiceStudio und Immich wäre ein Problem | Grenze bleibt klar | Grenze bleibt klar |
| Sicherheit | schwach, Fremdcode im Kern | stark, Policy und Timer greifen | schwach, kein Protokoll-Audit |
| Passt zum Kern | nein, verletzt stdlib-only | ja | teilweise |

**Gewählt wird B.** C bleibt nur für lesende Werkzeuge erlaubt, zum Beispiel Vault-Suche für OpenCode.
A scheidet aus, weil Torch, Pydantic und Co. die stdlib-Regel brechen und AGPL-Code in ein MIT-Repo käme.

### Folgen

- **Einfacher:** Ein Helfer lässt sich austauschen, ohne den Kern anzufassen. Ausfälle bleiben auf einen Limb begrenzt.
- **Schwieriger:** Jeder Dienst braucht Ports, Health-Check und Doku. Mehrere Dienste gleichzeitig sprengen den RAM.
- **Später zu prüfen:** Der `dev`-Grenzwert von einem parallelen Limb bremst lange OpenManus- und Cua-Läufe.

## 4. Gemeinsame Regeln

### Abnahme für jeden neuen Limb

1. `limbs/<name>_limb.py` auf Basis von `LimbBase`, nur Standardbibliothek.
2. Eintrag in `limbs/registry.json` und Operationen in `protocol/operations.json`.
3. Spezifikation in `prompts/limbs/<name>_limb.md`.
4. Test in `tests/test_<name>_limb.py` mit gefälschtem Dienst, der auch Ausfall und Timeout abdeckt.
5. Toolbox-Leaf unter `docs/knowledge/<paket>/tools/*.md`, damit Agenten den Limb nur bei Bedarf laden.
6. Ports und Variablen in `docs/OPERATIONS.md`, Verweis in `docs/INDEX.md`.

### Sicherheit

| Regel | Umsetzung |
|---|---|
| Dienste nur lokal | Ports immer auf `127.0.0.1` binden |
| Versionen festhalten | Images per Tag oder Digest fest, nie `latest` |
| Fremdinhalt ist Daten | Notizen, Transkripte und Webseiten werden nie als Anweisung behandelt |
| Keine Dauerrechte | Host-Zugriff nur über gemountete Arbeitsordner, nie `$HOME` |
| Risiko sichtbar | Code-ausführende Operationen sind `risk: high` mit Elevation |
| Fremde Plugins | Nur nach Durchsicht, mit fester Version und ohne Hooks |

### Portplan

| Dienst | Port | Stand |
|---|---|---|
| speaches | 8011 | läuft |
| OpenManus | 8012 | neu |
| VoiceStudio | 8013 | neu, nur auf Abruf |
| Immich | 2283 | neu, Immich-Standard |

## 5. Phasen

### Phase 0: Bestand sichern (S, Risiko mittel)

Ziel ist, dass nichts mehr verloren gehen kann und genug Platz für die nächsten Phasen da ist.

1. Sprachdateien aus dem Worktree `fix/ui-testlauf-batch` in einen eigenen Branch `feat/speech-input` übernehmen:
   `frontend/src/apollo/dictation.ts`, `frontend/src/app/api/apollo/transcribe/`,
   `frontend/src/ops/__tests__/dictation.test.js`, `docs/SPEECH.md` sowie die Anteile in
   `Terminal.tsx`, `commands.ts`, `store.ts`, `globals.css`, `frontend/.env.example` und `docs/INDEX.md`.
2. Die restlichen UI-Änderungen in diesem Worktree getrennt committen, sie gehören nicht zur Sprache.
3. Toolbox-Limb und seine Tests auf `feat/hermes-kanban` committen.
4. Docker-Build-Cache nach deiner Freigabe leeren, das bringt bis zu 11 GB.
5. `:latest-cpu` von speaches auf eine feste Version umstellen.

**Abnahme:** Sprachtest läuft aus einem frischen Checkout, `git status` zeigt keinen Sprachcode mehr als ungesichert, mindestens 25 GB sind frei.

### Phase 1: Spracherkennung (M, Risiko niedrig)

speaches bleibt die Engine, weil sie schon läuft, gemessen ist und ohne Key auskommt.

| Paket | Inhalt | Dateien |
|---|---|---|
| 1.1 | Terminal-Diktat in `main` bringen, Verhalten bleibt: Text landet im Feld, wird nie automatisch gesendet | siehe Phase 0 |
| 1.2 | `speech`-Limb mit `speech.ping` und `speech.transcribe` (Datei rein, Text raus) | `limbs/speech_limb.py`, `prompts/limbs/speech_limb.md` |
| 1.3 | Wortliste aus dem Code lösen, damit neue Namen keine Code-Änderung brauchen | `frontend/src/app/api/apollo/transcribe/route.ts`, `docs/knowledge/speech/vocabulary.txt` |
| 1.4 | Sprachstatus im Orb: `LISTENING` nutzen, `speech engine is not running` als Zustand zeigen | `frontend/src/apollo/*` |
| 1.5 | Telegram-Sprachnachrichten über `speech.transcribe` | hängt an `feat/telegram-intel` |
| 1.6 | Live-Text beim Sprechen, falls die speaches-Version das stabil kann | Spike, Ergebnis in `docs/SPEECH.md` |

**Abnahme:** 10 Sekunden deutsche Sprache brauchen unter 6 Sekunden, der Ausfall von speaches ergibt 503 statt erfundenem Text, und `speech.transcribe` ist in der Toolbox auffindbar.

**Zu prüfen:** `ffmpeg` fehlt auf dem Host. Der Limb gibt Audio deshalb unverändert an speaches weiter und muss das mit OGG aus Telegram testen.

### Phase 2: Obsidian (M, Risiko niedrig)

Obsidian ist auf diesem Rechner nicht installiert, und `workspace/obsidian` ist leer. Das stört nicht:
Ein Vault ist nur ein Ordner mit Markdown. Die App brauchst du nur zum Lesen, sie ist keine Abhängigkeit.

**Entscheidung:** Der Vault bleibt in `workspace/obsidian`. Dieser Pfad liegt schon im erlaubten Bereich, ein externer Pfad
würde Änderungen an geschützten Dateien verlangen. `workspace/*` steht in `.gitignore`, deshalb bekommt
der Vault ein eigenes lokales Git-Repository als Sicherung.

```
workspace/obsidian/
├── Inbox/        Sprachnotizen und Agenten-Vorschläge
├── Daily/        Tagesnotizen
├── Knowledge/    deine Notizen, für Agenten nur lesbar
├── workers/      bestehender Kanban-Spiegel
└── tasks/        bestehender Kanban-Spiegel
```

| Paket | Inhalt | Dateien |
|---|---|---|
| 2.1 | `vault`-Limb: `vault.ping`, `vault.search`, `vault.read`, `vault.capture` | `limbs/vault_limb.py`, `prompts/limbs/vault_limb.md` |
| 2.2 | Suchindex mit SQLite FTS5, nach Änderungszeit aktualisiert, ohne `.obsidian/` | im Limb, Index unter `runtime/` |
| 2.3 | Schreibregel: Agenten schreiben nur nach `Inbox/`, `workers/` und `tasks/` | im Limb, mit Test für Pfadausbrüche |
| 2.4 | API und Proxy: Kanban-FastAPI mit Operator-Auth, dazu eine Next-Route | `orchestrator/kanban/api.py`, `frontend/src/app/api/apollo/vault/` |
| 2.5 | Apollo-Befehle `/note` und `/vault <suche>`; Diktat lässt sich als Notiz speichern | `frontend/src/apollo/commands.ts` |
| 2.6 | Lesezugriff für OpenCode als MCP-Server | `scripts/vault_mcp.py` |

**Abnahme:** Ein Diktat steht mit Frontmatter und Datum in `Inbox/`. Eine Suche findet es in unter einer Sekunde, und `../`-Pfade werden abgewiesen. Die Kanban-Tests laufen unverändert grün.

**Abstimmung:** Hermes-Phase 2 plant ein eigenes FTS5-Gedächtnis (`apollo/ciel/memory_tier.py`). Beide Indizes bleiben getrennt, Ciel fragt den Vault über den Limb ab.

### Phase 3: OpenCode (M, Risiko hoch)

`worker_entry.py` ruft heute `opencode run <prompt>` ohne Modell, ohne Rechte und ohne Konfiguration auf. `~/.config/opencode` ist leer. Der Aufruf hat dort auch keinen eigenen Timeout, nur die Sandbox begrenzt ihn.

| Paket | Inhalt | Dateien |
|---|---|---|
| 3.1 | Aufruf in eine eigene Funktion ziehen, Timeout setzen, strukturierte Ausgabe statt reinem stdout | `orchestrator/kanban/worker_entry.py` |
| 3.2 | Projekt-Konfiguration mit Ollama und `freellmapi`, Key nur aus der Umgebung | `config/opencode/opencode.json` |
| 3.3 | Rechte: `.env`, `runtime/` und `git push` sperren, Bash nur mit Liste erlaubter Befehle | `config/opencode/opencode.json` |
| 3.4 | Docker-Runtime: eigenes Worker-Image, weil `python:3.12-slim` kein OpenCode enthält und die Snap-Version dort nicht läuft | `docker/opencode-worker/Dockerfile` |
| 3.5 | Netz: `--network none` blockiert auch das Modell, deshalb ein internes Netz nur zum Modell-Endpunkt | `orchestrator/kanban/sandbox.py` |
| 3.6 | Vault-MCP aus Phase 2 einbinden, nur lesend | `config/opencode/opencode.json` |
| 3.7 | Apollo-Befehl `/code <auftrag>` erzeugt eine Kanban-Aufgabe, Diktat funktioniert damit automatisch | `frontend/src/apollo/commands.ts` |

**Abnahme:** Eine Testaufgabe ändert eine Datei und committet lokal auf dem Worker-Branch. Ein Push-Versuch scheitert, und der Timeout beendet einen hängenden Lauf. `kanban`-Tests und ein E2E-Lauf mit `opencode` sind grün.

**Zu prüfen:** CLI-Schalter vor dem Bau mit `opencode run --help` abgleichen. `qwen2.5-coder` belegt 4,7 GB und passt nicht ganz auf die GPU, deshalb Geschwindigkeit messen, bevor es Standardmodell wird.

**Kandidaten aus `awesome-opencode`:** Nur nach Durchsicht installieren, nichts davon ist Voraussetzung.

| Kandidat | Nutzen |
|---|---|
| `envsitter-guard` | zusätzlicher Schutz vor `.env`-Lecks |
| `opencode-tokenscope` | Token-Verbrauch sichtbar machen |
| `jailoc` | Vergleich zur eigenen Docker-Lösung in 3.4 |

### Phase 4: python-genai (S, Risiko niedrig)

Das Archiv ist das offizielle Google-SDK (Version 2.16.0, Apache-2.0). Es ersetzt keine Funktion, sondern ist eine Bibliothek.

1. `google-genai` in `Architect/requirements.txt` auf eine geprüfte Version festlegen.
2. `genai_client.py` gegen die neue Version testen. Das SDK kündigt eine Änderung beim automatischen Function Calling an, deshalb AFC im Client ausdrücklich steuern.
3. Vor dem Bau prüfen, ob Gemini über `freellmapi` schon verfügbar ist. Dann reicht ein Eintrag dort.

**Abnahme:** `Architect/tests` sind grün, und der Fallback auf LM Studio greift weiter, wenn kein Key gesetzt ist. `core/` bleibt frei von diesem Paket.

### Phase 5: OpenManus (C, Risiko hoch)

OpenManus führt über `python_execute` und `bash` beliebigen Code aus, und `use_sandbox` ist in der Beispielkonfiguration aus. Es läuft deshalb nur im Container.

| Paket | Inhalt |
|---|---|
| 5.1 | Eigenes Image aus fester Commit-Version bauen, als Nicht-Root |
| 5.2 | Limits: 2 CPUs, 3 GB RAM, `--read-only`, nur ein Arbeitsordner je Lauf gemountet |
| 5.3 | Netz gesperrt bis auf den Modell-Endpunkt, Freigabe je Auftrag über Parameter |
| 5.4 | `manus`-Limb: `manus.ping`, `manus.run` mit `risk: high` und Elevation, `manus.stop` |
| 5.5 | Ergebnis nur als Artefakte im Arbeitsordner, Rückgabe über das Result-Protokoll |
| 5.6 | Konfiguration für `freellmapi` oder Ollama, nie Provider-Keys im Container |

**Abnahme:** Ein Testauftrag läuft durch. Ein absichtlicher Zugriff auf Host-Dateien, Kraken-Tools und fremde Hosts schlägt fehl. Timeout und Stop beenden den Container vollständig.

### Phase 6: Cua (C, Risiko hoch)

Nutzbar sind `libs/python/cua-sandbox` für Wegwerf-Desktops und `cua-driver` als MCP-Server. Der Host-Desktop bleibt tabu, denn dort sind Browser-Logins und Trading-Oberflächen offen.

1. Einen Test mit `Sandbox.ephemeral(Image.linux(), local=True)` fahren und Plattenbedarf sowie Docker-Tauglichkeit messen.
2. `desktop`-Limb mit `desktop.run` und `desktop.screenshot`, beide nur in der Sandbox.
3. Modellzugriff wie bei OpenManus, Telemetrie in den Paketen vor Nutzung prüfen und abschalten.
4. Spezialwerkzeuge (`cua-bench`, `lume`, die Swift-Apps) entfallen. Lume braucht Apple Silicon.

**Abnahme:** Ein Agent öffnet in der Sandbox eine App und liefert einen Screenshot. Nach dem Lauf bleibt kein Container übrig, und der Host-Bildschirm wurde nie angesprochen.

### Phase 7: VoiceStudio (C, Risiko mittel)

VoiceStudio bringt Text-zu-Sprache, Stimmenklonen, Dubbing und eine zu OpenAI kompatible Audio-API. Als reine Spracherkennung wäre es zu schwer: Das Projekt zieht Torch und viele Engines nach sich, speaches löst die Aufgabe schon.

1. Betrieb über `deploy/docker-compose.yml` nur auf Abruf, nicht dauerhaft.
2. Analytics bleibt aus; die Standardeinstellung vor dem Start prüfen.
3. Nur Modelle mit passender Lizenz laut `backend/config/model_licenses.json`.
4. `voice`-Limb mit `voice.speak` gegen `POST /v1/audio/speech`.
5. Apollo: Antworten optional vorlesen.

**Abnahme:** Eine deutsche Antwort wird ohne Netz vertont. Nach dem Stoppen sind RAM und Port frei, und speaches lief unbeeinträchtigt weiter.

**Lizenz:** VoiceStudio steht unter AGPL-3.0, bleibt also ein getrennter Dienst ohne Code im Repo.

### Phase 8: Immich (C, Risiko mittel)

Immich braucht vier Dienste und mindestens 6 GB RAM. Mit den heutigen Reserven passt das nicht neben den Rest.

1. Vorbedingung: eigener Datenträger für Bibliothek und Datenbank.
2. Betrieb über `docker/docker-compose.yml` mit fester Version, nur auf `127.0.0.1:2283`.
3. API-Key mit reinen Leserechten.
4. `photos`-Limb mit `photos.search` (über `/search/smart` und `/search/metadata`) und `photos.get`, keine Lösch-Operation.
5. Treffer als Link in Vault-Notizen.

**Abnahme:** Eine Textsuche liefert Treffer. Der Limb kann nichts löschen, und ohne laufendes Immich meldet er sauber einen Fehler.

**Lizenz:** Immich steht ebenfalls unter AGPL-3.0, also auch hier nur als getrennter Dienst.

## 6. Nicht eingeplant: openclaw-zero-token

Dieses Projekt fängt Cookies und Bearer-Token aus Browser-Sitzungen von ChatGPT, Claude, Gemini und anderen ab und nutzt
sie für kostenlose API-Aufrufe. Diesen Teil baue ich nicht ein:

- Es umgeht die Bezahlgrenzen der Anbieter. Das Projekt selbst verweist auf deren Nutzungsbedingungen, und deine Konten könnten gesperrt werden.
- `auth.json` enthielte Zugangsdaten deiner Haupt-Konten im Klartext, neben Agenten, die Code ausführen.
- Tool-Aufrufe entstehen über Prompt-Injektion in Web-Oberflächen. Das ist laut Projekt nicht für Dauerlast gedacht und schwer zu prüfen.

Das Ziel „kostenlose Modelle“ ist auch so erfüllt: `freellmapi`, Ollama und der kostenlose Gemini-Key über offizielle Wege.
Bleibt der Wunsch nach Kanälen wie WhatsApp oder Sprachanrufen, ist das Original-OpenClaw mit offiziellen Keys oder Ollama der saubere Weg. Dafür gäbe es einen eigenen Plan.

## 7. Ablauf

```
Phase 0 ─▶ Phase 1 ─▶ Phase 2 ─▶ Phase 3
   │
   ├─▶ Phase 4 (parallel möglich)
   └─▶ Phase 5 ─▶ Phase 6
                  Phase 7 und 8 erst, wenn Ressourcen frei sind
```

Phase 4 berührt keine Dateien der anderen Phasen. Phase 1 bis 3 bauen aufeinander auf, weil jede die vorige nutzt:
Sprache füttert den Vault, der Vault füttert OpenCode.

Jede Phase bekommt einen eigenen Branch und PR. `docs/hermes/RUNTIME_PLAN.md` läuft weiter. Überschneidungen gibt es
nur bei `orchestrator/kanban/api.py` und `frontend/src/apollo/commands.ts`, dort also vor Beginn neu aufsetzen.

## 8. Offene Annahmen

| Annahme | Geprüft durch |
|---|---|
| Der Docker-Build-Cache lässt sich gefahrlos leeren | deine Freigabe in Phase 0 |
| speaches liest Telegram-OGG ohne `ffmpeg` auf dem Host | Test in Paket 1.5 |
| `qwen2.5-coder` ist auf diesem Rechner schnell genug | Messung in Paket 3.2 |
| OpenCode lässt sich ohne Snap in einem Image betreiben | Paket 3.4 |
| Cua-Sandboxen laufen auf diesem Host ohne verschachtelte Virtualisierung | Test in Phase 6 |
| Die GTX 970 bringt für Whisper keinen Vorteil | bewusst nicht geprüft, CPU reicht |

Plattenbedarf von VoiceStudio, Cua und OpenManus ist noch nicht gemessen. Das geschieht zu Beginn der jeweiligen Phase.
