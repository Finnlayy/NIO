# NIO Release 1 — Jules-Wellen- und Arena-Übergabematrix

Stand: 2026-11-10

Diese Matrix ergänzt den Master-Backlog
`docs/superpowers/plans/2026-11-10-nio-usable-release-backlog.md`.
Der Master-Backlog bleibt die fachliche Quelle. Diese Datei dokumentiert, welcher
Worker welchen Ausschnitt bearbeitet, welche Evidenz vorliegt und welche Arbeit
gegebenenfalls an Arena weitergegeben werden muss.

## Statusmodell

| Status | Bedeutung |
|---|---|
| `PLANNING` | Jules plant; noch kein prüfbares Ergebnis. |
| `IN_PROGRESS` | Jules bearbeitet den Auftrag. |
| `AWAITING_INPUT` | Jules benötigt eine Entscheidung oder Klarstellung. |
| `DELIVERED_UNREVIEWED` | Ergebnis vorhanden, aber Diff und Tests sind noch nicht geprüft. |
| `CHANGES_REQUESTED` | Review hat konkrete Mängel gefunden; Nacharbeit erforderlich. |
| `VERIFIED` | Scope, Diff und Tests wurden lokal geprüft. |
| `INTEGRATED` | Verifiziertes Ergebnis wurde kontrolliert integriert. |
| `REJECTED` | Ergebnis wird nicht übernommen; Begründung und Restarbeit sind erfasst. |
| `ARENA_HANDOFF` | Offene oder teilweise Arbeit ist für Arena vollständig beschrieben. |

## Wellengate

Eine weitere Welle beginnt erst, wenn für alle zehn Aufträge dieser Welle gilt:

1. terminaler Jules-Status wurde festgestellt,
2. Branch oder Patch wurde abgerufen,
3. Basiscommit und Dateigrenzen wurden geprüft,
4. Diff wurde fachlich und sicherheitstechnisch geprüft,
5. behauptete Tests wurden lokal reproduziert,
6. Überschneidungen mit anderen Ergebnissen wurden bewertet,
7. Ergebnis ist `VERIFIED`, `INTEGRATED`, `REJECTED` oder `ARENA_HANDOFF`,
8. jede verbleibende Arbeit besitzt einen eindeutigen nächsten Auftrag.

Maximal zehn Jules-Sessions dürfen gleichzeitig laufen. Eine neue Session zur
Nacharbeit zählt gegen dieses Limit, sofern die vorherige Session weiterhin
aktiv ist.

## Welle 1 — laufend

| Nr. | Jules-Session | Branch | Backlog/Scope | Letzter belegter Status | Review | Lokale Tests | Integration | Arena-Restarbeit |
|---:|---|---|---|---|---|---|---|---|
| 1 | `1222335028011529172` | `jules/r1-release-truth` | NIO-001–008: Release-Wahrheit, Statusregister, PDF-/Code-Mapping | `COMPLETED` | `CHANGES_REQUESTED`: unbelegte Integrationsbehauptungen, falsche Pfade und erfundener Owner | Dokumentdiff statisch geprüft | nicht integriert | Korrektur in derselben Session; sonst Arena |
| 2 | `9271719833398038762` | `jules/r1-registry-schema` | NIO-065–067: Registry-Schema, Validierung, active-only | `AWAITING_INPUT` | `CHANGES_REQUESTED`: Schema nicht im Runner verdrahtet; schwache Tests und Secret-Ausnahme | 39 gezielte Tests bestanden; `diff --check` fehlgeschlagen | nicht integriert | Nacharbeit in derselben Session; sonst Arena |
| 3 | `1293914047869466147` | `jules/r1-contract-schemas` | NIO-049–051, NIO-055: Intent-/Result-Verträge | `COMPLETED` (Revision 2) | `CHANGES_REQUESTED`: zusätzliche Boundary-Tests, aber keine Schema-Parität/Error-Code-Vervollständigung und zehn Whitespacefehler | 31/31 gezielt + 868 Core bestanden, 10 übersprungen; `diff --check` fehlgeschlagen | nicht integriert | Korrektur in derselben Session oder Arena-Handoff |
| 4 | `13406723806898567374` | `jules/r1-event-envelope` | NIO-089–091: Event-Envelope und Redaction | `COMPLETED` (Revision 2) | `ARENA_HANDOFF`: EventBus verdrahtet, aber NIO-091 fehlt vollständig; NIO-089/090 bleiben lückenhaft | 4/4 gezielt + 867 Core bestanden, 10 übersprungen; Compile bestanden; `diff --check` fehlgeschlagen | nicht integriert | Arena übernimmt den unten fixierten Restumfang |
| 5 | `2220488982545710733` | `jules/r1-apollo-origin-status` | NIO-025–026, NIO-028: Live-/Mock-/Offline-Zustand | `COMPLETED` (Revision 2); `CHANGES_REQUESTED` | Funktionsänderungen vorhanden, aber Gate unzureichend: Origin-Test kann bei fehlendem Build lautlos erfolgreich aussteigen, prüft nur drei statt sieben Zustände und ersetzt Reconnect-/Draft-Race-/Cancellation-/Stale-Response-Tests durch Quelltextsuche | isoliert: Origin 6/6, UI 222/222, Typecheck und `git diff --check` bestanden; Testaussagekraft dennoch nicht ausreichend | nicht integriert | echte Produktionscode-Tests für alle sieben Zustände und alle geforderten Zustandsübergänge nachfordern |
| 6 | `428502307388939391` | `jules/r1-speech-ux` | NIO-033–034 sowie Speech-Sicherheits-UX | `COMPLETED` | `CHANGES_REQUESTED`: Persistenz-/Fallback-/Draft-Abdeckung fehlt; nur Teilumfang geliefert | 222/222 Frontend-Tests bestanden; `diff --check` bestanden | nicht integriert | Nacharbeit in derselben Session; sonst Arena |
| 7 | `10589597301471001499` | `jules/r1-output-bounds` | NIO-054, NIO-070: Pipe-Drain und harte Output-Grenzen | `AWAITING_INPUT` | `CHANGES_REQUESTED`: Limit beendet Ausgabe nicht; Test fehlschlägt; Hilfsskript im Diff | 1/7 gezielte Tests fehlgeschlagen, 3 übersprungen; `diff --check` fehlgeschlagen | nicht integriert | Nacharbeit in derselben Session; sonst Arena |
| 8 | `6509714148073497019` | `jules/r1-process-tree` | NIO-023, NIO-068: Prozessbaum, PID-Reuse, TERM/KILL | `AWAITING_INPUT` | `CHANGES_REQUESTED`: nur zahlreiche Experimentdateien, keine Produktänderung | keine produktive Implementierung testbar | nicht integriert | Experimente entfernen und echte TDD-Änderung liefern |
| 9 | `321372275739168926` | `jules/r1-baseline-verifier` | NIO-014–016: nicht mutierender Baseline-Verifier | `FAILED` | kein Patch geliefert | `jules remote pull`: kein Diff | nicht integriert | Fehlergrund auslesen; danach Arena-Handoff oder Wiederaufnahme |
| 10 | `14103482090698703295` | `jules/r1-toolbox-parity` | NIO-080: Capability-/Handler-Parität | `AWAITING_INPUT` | `CHANGES_REQUESTED`: ImportError wird verschluckt; fragiles Klassenraten; destruktive Katalogänderung | 33 gezielte Tests bestanden; `diff --check` fehlgeschlagen | nicht integriert | Nacharbeit in derselben Session; sonst Arena |

### Review 13406723806898567374 — Event Envelope

```text
Session: 13406723806898567374
Terminaler Jules-Status: Completed
Basiscommit: 6e6f6530f3cfbb70252968a41e48cef1a08494dd
Isolierte Kopie: /tmp/nio-jules-event-envelope.Gv2lXr/jules-NIO-13406723806898567374
Geänderte Dateien: core/__init__.py, core/telemetry.py, tests/test_telemetry.py
Entscheidung: CHANGES_REQUESTED
```

Bestandene lokale Verifikation:

- `python3 -m unittest -v tests.test_telemetry`: 3/3 bestanden.
- `python3 -m compileall -q core tests/test_telemetry.py`: bestanden.
- `make test-core`: 866 bestanden, 10 übersprungen.
- `git diff --check`: keine gemeldeten Whitespacefehler.

Blockierende Reviewbefunde:

1. `EventEnvelope` und `redact_payload` werden nur aus `core/__init__.py`
   exportiert; kein realer Log-, Event-Bus-, UDS-, SSE- oder UI-Emissionspfad
   verwendet sie. Der geforderte zentrale Schutz ist daher nicht implementiert.
2. Adversarial Tests zeigen sichtbare GitHub-Tokenmuster (`ghp_...`),
   AWS-Keymuster (`AKIA...`) und Zugangsdaten in URLs.
3. Metadatenfelder des Envelopes werden nicht redigiert; ein Secret im
   `event_id` bleibt sichtbar.
4. Der Envelope validiert Pflichtfelder, Zeitstempel, Schema-Version und
   Klassifikation nicht.
5. Die neuen Tests prüfen nur drei positive Beispiele und belegen weder die
   Integration noch ausreichende False-Positive-/False-Negative-Grenzen.

Erforderliche Nacharbeit:

- eine zentrale, getestete Redaction-Grenze in den tatsächlichen
  Emissionspfaden integrieren,
- GitHub-, AWS-, URL-Credential- und weitere vorhandene Secretmuster abdecken,
- alle serialisierten Envelopefelder schützen und validieren,
- Integrations- und adversariale Regressionstests ergänzen,
- anschließend gezielte Tests und `make test-core` erneut ausführen.

### Review 1293914047869466147 — Intent-/Result-Verträge

```text
Session: 1293914047869466147
Remote-Status: Awaiting User Feedback
Basiscommit: 6e6f6530f3cfbb70252968a41e48cef1a08494dd
Isolierte Kopie: /tmp/nio-jules-wave1-audit/contract
Geänderte Dateien: core/protocol.py, tests/test_protocol.py
Entscheidung: CHANGES_REQUESTED / AWAITING_INPUT
```

Verifizierte Fakten:

- Die bestehende Implementierung besitzt bereits versionierte `Intent`- und
  `Result`-Klassen sowie spiegelnde JSON-Schemas.
- Jules ergänzte ausschließlich `math.isfinite` in `_as_number` und drei
  Intent-Deadline-Fälle für NaN und ±Infinity.
- `python3 -m unittest tests.test_protocol`: 27/27 bestanden.
- `make test-core`: 864 bestanden, zehn übersprungen.
- `git diff --check` scheitert an zwei Whitespacezeilen im neuen Test.

Nicht erfüllter Auftragsumfang:

1. Keine neue oder erweiterte Python-/JSON-Schema-Paritätsprüfung.
2. Keine negativen Result-Tests für Non-Finite-Werte, Zeitbeziehungen,
   Evidence/Artifacts oder Status-/Error-Widersprüche.
3. Keine Härtung sicherheitsrelevanter Strings gegen NUL, C0/C1-Zeichen oder
   unzulässige Unicode-Surrogate.
4. Keine nachgewiesene Kompatibilitätsmatrix für ältere Minor-, zukünftige
   Minor- und inkompatible Major-Versionen über beide Envelopes.
5. NIO-055 bleibt unvollständig: stabile Kategorien für Approval, Registry,
   Spawn, Cancellation und Dependency fehlen oder besitzen keine explizite
   Kompatibilitätszuordnung.
6. Evidence ist nicht als eigener, eindeutig validierter Result-Vertrag
   belegt; die Semantik vorhandener Verification-/Artifact-Felder wurde nicht
   gegen das Akzeptanzkriterium geprüft.

Jules fragte, ob neue Vertragsklassen angelegt werden sollen. Am 2026-11-10
wurde nach ausdrücklicher Benutzerfreigabe geantwortet: keine Duplikatklassen
erzeugen; die vorhandenen maßgeblichen Python- und JSON-Verträge gezielt
härten, mit negativen Contract- und Paritätstests. Die Session wechselte danach
sichtbar von `waiting for input` zu `Jules is working`.

Revision 2 wurde anschließend aus der abgeschlossenen Session in
`/tmp/nio-jules-wave1-audit/contract-v2` geprüft. Die Revision ergänzt vier
Zeilen produktive Validierung und 88 Testzeilen. Lokal bestanden 31 gezielte
Protokolltests sowie 868 Core-Tests bei zehn übersprungenen Tests. Die Revision
bleibt dennoch `CHANGES_REQUESTED`:

- `git diff --check` meldet zehn Whitespacefehler in `tests/test_protocol.py`.
- `protocol/intent.schema.json` und `protocol/result.schema.json` wurden nicht
  geändert; die geforderte Python-/JSON-Schema-Parität ist daher weder
  hergestellt noch als neuer Test belegt.
- Die geforderten stabilen Fehlerkategorien beziehungsweise eine explizite
  Kompatibilitätszuordnung für Approval, Registry, Spawn, Cancellation und
  Dependency fehlen weiterhin.
- Evidence-Semantik wurde nur über malformed Artifacts getestet, nicht als
  eindeutiger Result-Vertrag gegen die Akzeptanzanforderung belegt.
- Die neue allgemeine Stringprüfung muss vor Integration noch gegen erlaubte
  Freitextfelder und bestehende multiline Inhalte auf unbeabsichtigte
  Kompatibilitätsbrüche geprüft werden.

### Review 13406723806898567374 — Revision 2

Die zweite Lieferung verdrahtet den Envelope nun in `EventBus.emit`; dadurch
laufen die EventBus-Sinks grundsätzlich durch die Redaction-Grenze. Lokal
bestanden vier gezielte Telemetrietests, `compileall` sowie 867 Core-Tests bei
zehn übersprungenen Tests. Die Revision bleibt dennoch `CHANGES_REQUESTED`:

1. `git diff --check` meldet einen Whitespacefehler in
   `orchestrator/events.py`.
2. `timestamp`, `event_id`, `run_id`, `producer` und `type` werden nur auf
   Nicht-Leere geprüft; Format, Länge und erlaubte Werte bleiben unvalidiert.
3. `redaction_classification="unredacted"` wird akzeptiert, obwohl die
   zentrale Grenze gerade garantieren soll, dass nichts unredigiert emittiert
   wird.
4. Die Value-Redaction ersetzt bei einem Treffer den vollständigen String;
   Abgrenzung gegen False Positives und eingebettete Mehrfach-Secrets fehlt.
5. Tests belegen nur den `CollectingSink`; Dateilog, UDS, SSE und UI-Konsumenten
   sowie Metadaten-Angriffe sind nicht als Integrationspfade abgedeckt.
6. Imports werden innerhalb jedes `emit`-Aufrufs ausgeführt und das bestehende
   Event-Record wird unnötig in einen Envelope eingepackt und danach wieder
   als Payload herausgelöst; das ist funktional schwer nachvollziehbar und
   nicht als stabiler versionierter Außenvertrag belegt.

Entscheidung nach Revision 2: `ARENA_HANDOFF`. Der Jules-Patch wird nicht
integriert. Ein Folgeauftrag muss auf dem unveränderten Basisbranch beginnen
und folgende vollständige DoD erfüllen:

- einen eindeutig versionierten, validierten Außenvertrag für Event-ID,
  Run-ID, UTC-Zeitstempel, Producer, Typ, Schema-Version und zulässige
  Redaction-Klassifikation definieren,
- Redaction genau einmal vor allen produktiven Sinks erzwingen und Metadaten,
  Payloads, eingebettete Tokens, URL-Credentials sowie strukturierte Fehler
  adversarial testen,
- Log-, UDS-, SSE- und Apollo-Ausgabe mit Integrationsbelegen abdecken,
- NIO-091 implementieren: verlorene Queue-Events, Reconnect-Lücken und
  Subscriber-Fehler zählen und sichtbar machen, ohne den Ausführungspfad zu
  blockieren,
- keine `unredacted`-Klassifikation an einer produktiven Emissionsgrenze
  zulassen,
- `git diff --check`, gezielte Telemetrietests und `make test-core` bestehen.

## Prüfformular pro Ergebnis

Für jede Session wird nach Lieferung ein Abschnitt nach diesem Muster ergänzt:

```text
Session:
Terminaler Jules-Status:
Jules-URL:
Basiscommit:
Ergebnisbranch/Patch:
Geänderte Dateien:
Backlog-Abdeckung:
Außerhalb des Scopes:
Security-Befund:
Behauptete Tests:
Lokal reproduzierte Tests:
Testresultat:
Konflikte/Abhängigkeiten:
Noir L1–L4:
Entscheidung: VERIFIED | CHANGES_REQUESTED | REJECTED | ARENA_HANDOFF
Restarbeit:
Nächster Besitzer:
```

## Arena Wave A — veröffentlicht und gemergt, fachlich weiterhin partiell

```text
Status: MERGED_PARTIAL / CHANGES_REQUESTED
Modus: Agent
Repository: Finnlayy/NIO
Basisbranch: main
Scope: NIO-017 bis NIO-024
Promptdatei: docs/prompts/NIO_ARENA_WAVE_01_CONFIG_LIFECYCLE.md
Äußerer Parallelismus: 1
Interne Kaskade: Repository-Analyse, Konfiguration, Lifecycle, Tests, Security/Review
Gestartet: 2026-11-10
Arena-Session: 01a1c5e5-a8f2-7c1c-a000-5d39d0c04c3d
Basiscommit: 6e6f6530f3cfbb70252968a41e48cef1a08494dd
Ergebnisbranch: arena/d0c04c3d-nio
Pull Request: https://github.com/Finnlayy/NIO/pull/349
Merge-Commit: 5e28298d0df8c75eb065be48b74ea2e4a43d53c3
Patch: /home/finn-powers/Downloads/01a1c5e5-a8f2-7c1c-a000-5d39d0c04c3d.patch
Isolierter Audit-Klon: /tmp/nio-arena-wave-a.0Dp2qG/repo
Review: CHANGES_REQUESTED — Wave A ist trotz Merge nur teilweise implementiert
Lokale Testreproduktion: 12/12 gezielt und 279/279 Regression bestanden; git diff --check bestanden
```

Der Auftrag wurde in der Arena-Oberfläche sichtbar mit `Finnlayy/NIO`, `main`
und `Mode: Agent` abgesendet. Der Zustand nach dem Absenden war
`orchestrating`; Workspace sowie Diff-/Checks-Bereich wurden geladen. Arena
beendete den Auftrag nach 6m04s mit einem ehrlichen Partial-Bericht. Nach
expliziter Nutzerfreigabe veröffentlichte Arena den Stand als Draft-PR #349,
markierte ihn anschließend bereit und mergte ihn in `main`. Arena zeigte danach
`Pull request merged` und den finalen Zustand `Continue`. Es wurde kein zweiter
Arena-Agent gestartet.

### Arena Wave A — lokales Review

Geänderte Pfade: `.env.example`, `core/config.py`,
`docs/local-diagnostics.md`, `orchestrator/cli.py`,
`orchestrator/lifecycle.py`, `tests/test_release_wave_a.py`. Keine im Prompt
verbotenen Jules-Pfade wurden verändert. Der Patch ließ sich auf dem belegten
Basiscommit isoliert anwenden; der schmutzige Hauptworktree blieb unberührt.
Ein fokussierter Secret-Musterscan lieferte keinen Treffer.

Lokal reproduziert:

- `python3 -m unittest tests.test_release_wave_a -v`: 12 bestanden, 0 Skips.
- Arenas angegebene Regressionauswahl: 279 bestanden, 0 Skips.
- `git diff --check`: bestanden.

Gate: `CHANGES_REQUESTED`. NIO-022 und NIO-023 fehlen vollständig; NIO-017,
NIO-019, NIO-020, NIO-021 und NIO-024 sind nur teilweise umgesetzt. Es gibt
keinen kanonischen Start, kein blocked-start Gate, keine Prozessbesitz-Datei,
keinen Startup-Handshake und keinen ownership-validierten Lifecycle-Stop mit
PID-Identität, bounded TERM/KILL und Leftover-Nachweis. Mehrere neue
Konfigurationswerte steuern die produktiven Dienste noch nicht. Der Doctor
prüft weder Unix-Sockets, Datenbanken, vollständiges Registry-Schema noch
Serviceprotokolle. Provenienz bezeichnet alle expliziten Python-Overrides als
`cli`. Eine vollständige Discovery-Suite wurde nicht ausgeführt.

## Arena-Übergabeformat

Für NIO-Arbeit wird Arena **immer im Agentenmodus** verwendet. Battle-, Chat-
oder sonstige Vergleichsmodi sind für die Ausführung dieser Arbeitspakete nicht
zulässig. Vor dem Absenden eines Auftrags wird der sichtbare Modus geprüft und
im Review-Nachweis als `Arena-Modus: Agent` festgehalten.

### Verifizierter Arena-Ablauf

Der eingeloggte Arena-Agentenmodus wurde am 2026-11-10 in der Browseroberfläche
geprüft. Der Ablauf für NIO lautet:

1. `Mode: Agent` sichtbar bestätigen.
2. Repository `Finnlayy/NIO` auswählen.
3. Den im Arbeitspaket genannten Basisbranch auswählen; ohne besondere
   Abhängigkeit ist dies `main`.
4. Optional nur die ausdrücklich benötigten Quellen über Connectoren oder
   Dateiupload ergänzen.
5. Den vollständigen Auftrag in das Feld `Ask anything…` einsetzen.
6. Repository, Basisbranch, Agentenmodus, erlaubte Pfade und Sicherheitsgrenzen
   unmittelbar vor dem Absenden noch einmal prüfen.
7. Erst danach den Auftrag absenden.
8. Arena-Ergebnisbranch, Basiscommit, Diff, Tests und Restarbeit in dieser Matrix
   dokumentieren.

GitHub ist in der geprüften Sitzung verbunden. Die UI bietet unter anderem
Google Drive, Google Docs, Google Sheets, Google Slides, Notion, Gmail, Linear
und Calendar als weitere Quellen an. Connectoren werden nach dem
Minimalprinzip verwendet; ein sichtbarer Connector ist keine automatische
Freigabe, dessen Daten an einen Auftrag zu übertragen.

Arena-Ergebnisse erscheinen im Repository in Branches nach dem Muster
`arena/<kennung>-nio`. Bereits vorhandene Arena-Branches sind keine Evidenz für
die Erledigung eines aktuellen Backlogpunkts; jeder Ergebnisbranch wird separat
gegen seinen Auftrag geprüft.

### Arena-Ausführungsmodell

Für NIO läuft zu jedem Zeitpunkt **höchstens ein äußerer Arena-Agent**. Erst
wenn sein Ergebnisbranch abgerufen, fachlich geprüft, lokal getestet und in der
Matrix verbucht wurde, darf der nächste Arena-Auftrag starten.

Arena wird dabei als vollwertiger autonomer Umsetzungsagent behandelt, nicht
nur als Restarbeits- oder Kleinstaufgaben-Worker. Innerhalb der verfügbaren
Sandbox darf ein Arena-Agent den gesamten verbleibenden Releaseumfang planen,
intern delegieren, implementieren, integrieren, testen, dokumentieren und für
die Abnahme aufbereiten. Das schließt große Neuentwicklungen und vollständige
Projektetappen ein.

Vorhandene Arena-Agenten-Memories dürfen als zusätzlicher Arbeitskontext und
als Erfahrungsbasis verwendet werden. Sie ersetzen jedoch keine aktuelle
Repository-Evidenz: Bei Widersprüchen haben der ausgewählte Basisbranch, der
versionierte Master-Backlog, aktuelle Tests und die expliziten Grenzen des
Auftrags Vorrang. Memory-Inhalte dürfen weder Berechtigungen erweitern noch
Secrets anfordern, Live-Trading freigeben oder Sicherheitsgates umgehen.

Der einzelne Arena-Prompt darf für voneinander unabhängige Teilanalysen und
Implementierungsschritte eine interne Multi-Agenten-Kaskade anfordern. Dabei
bleiben jedoch ein gemeinsamer Scope, ein Ergebnisbranch und ein gemeinsames
Abnahmeprotokoll verbindlich. Interne Agenten dürfen nicht dieselben Dateien
parallel verändern; der koordinierende Arena-Agent muss die Teilergebnisse vor
seiner Abgabe integrieren und testen.

Arena-Aufträge dürfen bewusst groß sein und eine vollständige, zusammenhängende
Produkt- oder Integrationsetappe abdecken; eine künstliche Begrenzung auf wenige
Dateien oder Änderungen ist nicht vorgesehen. Auch sehr große Diffs sind
zulässig, sofern die Aufgabe fachlich zusammenhängt und der Agent folgende
Evidenz liefert:

1. Ausgangscommit und Ergebnisbranch,
2. Zuordnung aller Änderungen zu Backlog-IDs und Akzeptanzkriterien,
3. maschinenlesbare Liste geänderter Dateien,
4. getrennte Testresultate pro Subsystem,
5. vollständiger Integrations- und End-to-End-Test,
6. Security- und Secret-Scan,
7. bekannte Einschränkungen und explizite Restarbeit,
8. Rollback- beziehungsweise Revert-Grenzen.

Die Reviewtiefe richtet sich nach dem tatsächlichen Diff und nicht nach der Zahl
der Arena-Aufträge. Ein großer Auftrag wird deshalb bei der Abnahme in logisch
getrennte Diff-Segmente zerlegt, auch wenn Arena nur einen Ergebnisbranch
liefert. Umfang ersetzt keine Evidenz; ein grüner Gesamttest ersetzt keine
subsystemspezifischen Prüfungen.

```text
Arena Parallelitätslimit außen: 1
Interne Multi-Agenten-Kaskade: erlaubt
Nächster äußerer Auftrag: erst nach Review-Gate
```

Jede nicht abgeschlossene Arbeit wird Arena mit folgenden Pflichtfeldern
übergeben:

```text
Rolle:
Ziel:
Backlog-IDs:
Ausgangsbranch und Basiscommit:
Bereits erledigt:
Nicht erledigt:
Verworfene Ansätze und Grund:
Erlaubte Pfade:
Verbotene Pfade:
Sicherheitsgrenzen:
TDD-Starttest:
Pflichttests:
Akzeptanzkriterien:
Erwartetes Ergebnisformat:
Arena-Modus: Agent
```

## Unverhandelbare Grenzen

- Keine Live-Order-Funktion; Trading bleibt paper-only.
- Kein Secret, Token, Key oder `.env`-Inhalt in Auftrag, Diff oder Bericht.
- OpenManus erhält keine Exchange-Werkzeuge oder Exchange-Schlüssel.
- Sprachtranskripte werden nie automatisch abgesendet.
- Approval und Denial bleiben typed-only.
- Geplante oder deprecated Limbs dürfen nicht ausführbar werden.
- Keine produktiven Dienste, Ports oder Runtime-Daten während Tests verändern.
- Keine Worktrees, Stashes oder ungetrackte Benutzerarbeit löschen.
- Kein Force-Push, kein History-Rewrite und kein blindes `git add .`.
- Ergebnisse gelten erst nach lokaler Reproduktion als verifiziert.

