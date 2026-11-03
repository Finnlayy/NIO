# NIO: Live-Provider-Audit – 03.11.2026

## Ergebnis und Geltungsbereich

Geprüft wurde die **laufende Arena-Vorschau dieser Repository-Kopie**, nicht ein
anderer Rechner oder Produktionsserver. Es wurden keine Secret-Werte ausgegeben.

**0 konfigurierte LLM-Provider, 0 erfolgreiche externe Completions.** In der
Prozessumgebung des laufenden Next.js-Servers waren keine der registrierten
Provider-Credentials und kein Kanban-API-Token vorhanden. Es gab keine
`frontend/.env.local`, keinen konfigurierten Secret-Mount und keinen bestehenden
Secret-Manager. Die eingecheckten maskierten „Keys“ waren Demo-Platzhalter.
GitHub-Zugangsdaten wurden ausdrücklich nicht als Provider-Credentials verwendet.

Unauthentifizierte HEAD-Transportprüfungen zu allen elf Registry-Standardendpoints
scheiterten mit `network_or_tls_unreachable`, einschließlich des lokalen
FreeLLMAPI-Gateways. Die externen LLM-Hosts gehören nicht zur Egress-Freigabe dieser
Sandbox. Das ist **kein Nachweis ungültiger Keys**, sondern ein Transportproblem.

Die Completion-Prüfung wurde über die laufende API ausdrücklich angefordert.
Ohne Credential/Modell wird keine unauthentifizierte oder simulierte Completion
abgeschickt. Daher gibt es hier **keinen bestandenen kostenpflichtigen Live-Test**
und keine Providerkosten durch diese Prüfung.

Maschinenlesbare, secret-freie Belege:

- [`audits/2026-11-03-provider-status.json`](audits/2026-11-03-provider-status.json)
- [`audits/2026-11-03-provider-e2e.json`](audits/2026-11-03-provider-e2e.json)

## Tatsächlicher Status jeder Integration

| Integration | Credential in dieser Instanz | Transport / API | Authentifizierte Completion |
|---|---|---|---|
| FreeLLMAPI | fehlt | Standardgateway `127.0.0.1:3001` nicht erreichbar | blockiert; zusätzlich Modell erforderlich |
| OpenRouter | fehlt | HEAD nicht erreichbar | nicht ausführbar: `missing_secret` |
| Groq | fehlt | HEAD nicht erreichbar | nicht ausführbar: `missing_secret` |
| Google Gemini | weder `GOOGLE_API_KEY` noch `GEMINI_API_KEY` | HEAD nicht erreichbar | nicht ausführbar: `missing_secret` |
| Mistral | fehlt | HEAD nicht erreichbar | nicht ausführbar: `missing_secret` |
| Cerebras | fehlt | HEAD nicht erreichbar | nicht ausführbar: `missing_secret` |
| OpenAI | fehlt | HEAD nicht erreichbar | nicht ausführbar: `missing_secret` |
| NVIDIA | fehlt | HEAD nicht erreichbar | nicht ausführbar: `missing_secret` |
| Cohere | fehlt | HEAD nicht erreichbar | nicht ausführbar: `missing_secret` |
| Hugging Face | weder `HF_TOKEN` noch `HUGGINGFACE_API_KEY` | HEAD nicht erreichbar | blockiert; zusätzlich explizites Modell erforderlich |
| Anthropic | fehlt | HEAD nicht erreichbar | blockiert; zusätzlich explizites Modell erforderlich |
| TVremix / Marktdaten | `TVREMIX_API_KEY` fehlt | echte Quote-Route: HTTP 503 | kein Ersatz durch simulierte Kurse/News |
| Lokale Whisper-Spracheingabe | benötigt keinen Provider-Key | Speech-Health-Route: HTTP 503 | lokale Speech-Engine nicht verfügbar |
| Browser-Spracheingabe | kein NIO-Provider-Key | browser-/berechtigungsabhängig | kein externer LLM-Test; hier nicht erneut mit echtem Mikrofon verifiziert |
| Kanban-API | **neuer interner Service-Token**, nicht aus vorhandenen Provider-Keys | authentifizierter Next.js→Kanban-Aufruf erfolgreich | kein LLM-Provider |
| Agent-Worker `apollo-live` | kein OpenRouter-Key | echter Worker-Prozess gestartet | `failed: missing_secret`, Aufgabe `blocked` |

Die Modellnamen in der Registry sind Konfigurationsdefaults, **keine bestätigten
Modellverfügbarkeiten**. Der Live-Test muss nach Bereitstellung der Credentials
und Egress-Freigabe erneut laufen.

## Korrigierte Statusprüfung und Fehlerbehandlung

Vorher:

- `GET /api/apollo` prüfte nur drei Umgebungsvariablen; Google/Mistral/Cerebras
  konnten trotz vorhandenem Key als unkonfiguriert erscheinen.
- Der Browser zeigte erfundene maskierte Keys, `ACTIVE`-Status und eine feste
  Latenz. Die Statuswerte konnten durch Anklicken umgeschaltet werden.
- Fehlgeschlagene Apollo-Completions wurden durch lokale Synthese ersetzt.
- Marktdaten-Widgets ersetzten Ausfälle durch Design-Datensätze, teils mit
  erfundenen Feldern neben echten Daten.

Jetzt:

- Eine gemeinsame Registry (`orchestrator/provider_catalog.json`) definiert IDs,
  Credential-Namen/Aliase, feste Providerendpoints, Protokolle und Modelle.
- `configured` bedeutet ausschließlich „nichtleeres Credential vorhanden“.
- `ready` erfordert eine echte, nichtleere, protokollgültige Completion. Das
  Ergebnis gilt höchstens fünf Minuten und wird bei Credential-/Modellrotation
  ungültig. `GET` selbst führt keine kostenpflichtigen Probes aus.
- Zustände sind getrennt: `missing_secret`, `model_missing`, `unchecked`, `ready`,
  `auth_failed`, `rate_limited`, `upstream_error`, `invalid_response`,
  `network_error`, `timeout`.
- Der explizite Probe-Button macht pro konfiguriertem/modelliertem Provider
  höchstens eine Completion mit 16 Output-Tokens; doppelte Klicks werden für
  30 Sekunden zusammengefasst. Keine Retries oder stiller Providerwechsel.
- Provider-Secrets kommen nie aus einem Client-Payload. Native Anthropic- und
  Cohere-Formate werden neben OpenAI-kompatiblen APIs getrennt behandelt.
- Keine Redirect-Verfolgung. Remote-Provider brauchen HTTPS. Upstream-Fehlertexte
  werden nicht ungefiltert an den Browser weitergegeben.
- Apollo protokolliert Fehlschläge als `ERROR`, markiert den Task `FAILED` und
  lässt den Orb im Fehlerzustand. Es entsteht keine simulierte Assistant-Antwort.
- `/router status` liest echte serverseitige Metadaten. `/tasks` zeigt echte
  Worker-Ergebnisse und Blockierungsgründe.
- TVremix liest dasselbe Secret-Backend. Fehlgeschlagene Live-Marktdaten werden
  als sichtbare Fehler statt als Design-Fallback angezeigt. Während des Ladens
  erscheinen keine erfundenen Kurse. Explizite Graph-/Layout-Demonstrationen sind
  keine Providerbelege und bleiben entsprechend als UI-Demo gekennzeichnet.

## Secret-Anbindung für Apollo und Worker

Neu hinzugefügte Adapter:

- `frontend/src/server/secretManager.ts`
- `orchestrator/secret_manager.py`

Beide lesen dieselbe serverseitige Quelle: Prozessumgebung und optional
`NIO_SECRET_FILE`, einen vom Deployment bereitgestellten JSON-Mount. Die
Umgebung hat Vorrang. Das ist **kein neu erfundener verschlüsselter Vault und
keine Verbindung zu einem externen Secret-Manager-SDK**; ein solcher war in
dieser Instanz nicht vorhanden.

Dateien müssen regulär, dem Service-User zugeordnet, ohne Gruppen-/Fremdrechte
(z. B. `0600`), höchstens 64 KiB groß und ohne Symlink sein. Ungültige Dateien
führen zu einem festen Fehler ohne Parserauszug. Der Dateiinhalt wird nie über
einen API-Endpoint ausgegeben. Secrets gehören nicht ins Git oder in den Chat.

In der Vorschau wurde ausschließlich ein neuer zufälliger **interner**
Kanban-Service-Token in `runtime/provider-secrets.json` angelegt; `runtime/` ist
Git-ignoriert. Apollo und Kanban lesen diesen Token über denselben Adapter.
Es wurden **keine Provider-Keys erzeugt, angenommen oder aus anderen Apps kopiert**.

Für einen vom Betreiber sicher bereitgestellten Mount:

```bash
# Nur Pfade/Namen, keine Secret-Werte als CLI-Argumente:
export NIO_SECRET_FILE=/absoluter/pfad/zum/owner-only-secret-mount.json
export NIO_REPO_ROOT=/absoluter/pfad/zu/NIO
export NIO_LLM_PROVIDER=groq
# Explizite Freigabe: nur dieser Key darf in den gewählten Worker.
export NIO_KANBAN_SECRET_ALLOWLIST=GROQ_API_KEY
```

Der JSON-Mount enthält bei Bedarf auch `NIO_KANBAN_API_TOKEN`. Provider-Keynamen
und Modellvariablen stehen in der Registry. Für Gemini ist `GEMINI_API_KEY` ein
Alias; für Hugging Face ist `HUGGINGFACE_API_KEY` ein Alias von `HF_TOKEN`.
`ANTHROPIC_MODEL`, `HUGGINGFACE_MODEL` und `FREELLMAPI_MODEL` sind ohne Default
explizit zu setzen. Alle anderen Provider haben überschreibbare Defaults.

Apollo kann im Router-Tab eine Provider-ID wählen; leer bedeutet
`NIO_LLM_PROVIDER`, andernfalls den ersten konfigurierten Registry-Eintrag.
Worker verwenden ihren expliziten `provider:`-SOUL-Eintrag oder denselben
Serverstandard. **Eine Apollo-Auswahl ändert nicht heimlich die Identität eines
bestehenden Workers.** Der geprüfte `apollo-live`-Worker hat `provider: openrouter`.
Für gemeinsame Auswahl diesen Eintrag entfernen oder passend konfigurieren.

LLM-Worker bekommen nur das ausgewählte, ausdrücklich allowlistete Credential
als `NIO_LLM_API_KEY`, nicht den kompletten Secret-Mount, keine Operator-Secrets
und keine übrigen Provider-Keys. Werte stehen weder im argv noch im Audit-Ledger.
Worker-Ergebnisse und Experiences redigieren injizierte Keys und Task-Tokens.

## End-to-End: tatsächlich durchlaufen, aber fehlgeschlagen

Browserprüfung gegen die laufenden Dienste, **ohne Fetch-Interception/Mocks**:

1. Apollo öffnen → Controls → FreeLLM Router: elf Provider mit `missing_secret`.
2. Explizite Live-Prüfung: kein Provider `ready`, sichtbar fehlgeschlagen.
3. Terminal-Prompt „Reply with OK.“ → reale Route `/api/apollo` → HTTP 503
   `no_provider_configured`. Fehler sichtbar, keine Assistant-Simulation.
4. `/spawn inference Live-Audit-Worker-…` → authentifizierter Next.js-Kanban-Proxy
   → reale SQLite-Aufgabe → Dispatcher → echter Python-Worker-Prozess.
5. Worker prüft Credential, bricht mit `missing_secret` ab und schreibt
   `result.json` mit `status: failed` und leerem Ergebnis.
6. Circuit-Breaker setzt nach einem Versuch `blocked`; kein erneuter LLM-Versuch.
7. `/tasks` im Apollo-Terminal zeigt `circuit breaker: missing_secret`.
8. Ops-Seite zeigt Live-Marktdatenfehler statt Simulationsersatz.

Belegte Aufgabe: `t-d463396a76a0`. Die Task-ID dient nur als lokaler Testbeleg,
nicht als Provider-Erfolg. Es gab keine Browser-Runtimefehler.

Die Vorschau nutzt ausdrücklich `NIO_KANBAN_SANDBOX=llm-http`: einen neuen,
**HTTP-only Worker-Transport, keine Betriebssystem-Sandbox**. Er erlaubt nur die
fest eingebaute `llm`-Runtime, verweigert andere Runtimes auch nochmals im Kind
und führt niemals Modell-Code, Shell-Kommandos, Datei-Patches oder Tools aus.
Die normale `subprocess`-Sandbox bleibt auf `noop` beschränkt; allgemeine
Code-Ausführung benötigt weiterhin Docker. In dieser Sandbox ist keine
Docker-basierte Agentenausführung belegt. Der Preview-Breaker steht auf einem
Versuch, damit Prüfungen keine versteckten Wiederholungen/Kosten erzeugen.

**Der erfolgreiche externe Weg UI → Provider → Agentenantwort ist weiterhin
blockiert.** Ein gestarteter Worker oder ein erfolgreicher lokaler Fixture-Test
ist dafür kein Ersatz.

## Erneute Prüfung

```bash
# Nur Status lesen (keine Providerkosten):
python3 scripts/audit_live_providers.py

# Explizite echte Mini-Completions + credential-freie HEAD-Prüfungen:
python3 scripts/audit_live_providers.py --probe --transport \
  --output runtime/live-provider-audit.json
```

Exitcode `2` bedeutet: kein Provider `ready`; `1`: Apollo-Audit nicht möglich.
Die Ausgabe enthält ausschließlich erlaubte Statusmetadaten. Eine kostenlose
`/models`-Antwort wird nicht als erfolgreicher Modellaufruf missverstanden.

Nach Freigabe der Providerhosts und sicherer Secret-Bereitstellung: Dienste mit
dem Mount starten, Providerprobes ausführen, Modellverfügbarkeit prüfen, den
Worker auf denselben Provider und seine Secret-Allowlist einstellen und den
E2E-Weg erneut durchlaufen. Eine normale Worker-Completion ist auf 64
Output-Tokens begrenzt. **Diese noch fehlenden Live-Nachweise sind offen.**

## Automatisierte Tests (nicht mit externen Live-Tests verwechseln)

- Frontend: **185 Tests bestanden**, TypeScript-Check; Provider-/Secret-/Fehlerverträge; keine Simulation
  nach Fehlern; Marktfehler-UI; alle bestehenden UI-Tests.
- Kanban-Suite: 80 Tests ausgeführt, 8 wegen nicht vorhandener optionaler
  Integrationen übersprungen.
- Secret-/LLM-Worker-Suite: 10 Tests bestanden. Enthält reale Worker-Subprozesse
  gegen einen **lokalen HTTP-Fixture-Server**: Erfolg mit Redigierung, HTTP 401,
  Redirect-Verweigerung, kein Retry, keine Command-Runtime im HTTP-Transport.
- Ruff für alle geänderten Python-Module: bestanden.
- Mypy für die vier neuen/geänderten Worker-/Secretmodule mit
  `--follow-imports=silent`: bestanden. Der unbeschränkte Import-Check meldet
  zusätzlich einen unveränderten Befund in `orchestrator/runner.py:2110`
  (`no-any-return`); dieser bestehende Fremdbefund wurde nicht still kaschiert
  oder sachfremd geändert.
