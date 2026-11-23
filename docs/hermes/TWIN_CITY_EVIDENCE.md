# Twin-City — Quellen, Befunde und offene Nachweise

Stand: 22.11.2026. Dieses Register begleitet die Planrevision; es ist keine Produktabnahme. **Quellenabnahme bleibt offen: drei von vier Notebook-Audios wurden lokal transkribiert und ausgewertet; AUDIO-UI ist wegen abgelaufener Anmeldung nicht ausgewertet.** Kein Worker wurde durch diese Revision gestartet. Die Aufgaben bleiben blockiert.

## 1. Herkunft und Aussagegrenzen

Notebook: [NIO](https://notebooklm.google.com/notebook/ce01064b-fe24-4a24-8803-00d86e3e8b1a), ID `ce01064b-fe24-4a24-8803-00d86e3e8b1a`. Inventar vom 21.11.: 75 Quellen und sieben Studio-Artefakte, darunter vier Audios. Nicht alle 75 Quellen wurden vollständig gelesen. Priorisiert wurden neue Twin-City-Unterlagen, Fehleranalyse, Architekturberichte und Audioinhalte. Umfangreiche Graphify-/Hermes-Quellen wurden gezielt ausgewertet; daraus wird keine vollständige Laufzeitabdeckung abgeleitet.

Originalabrufe, Inventare und Transkripte liegen unter `/home/finn-powers/.cache/nio-twincity-plan-20261121/`. `studio.json` enthält temporäre Downloadadressen und gehört nicht ins Repository. Das begleitende [Prüfsummenregister](TWIN_CITY_SOURCE_HASHES.json) nennt nur Pfade, Größen und Hashes. Transkription: vorhandener lokaler Speaches-Dienst, `Systran/faster-whisper-small`, Deutsch; keine Audioübertragung an einen Cloud-Transkriptionsdienst. Automatische Transkripte können Namen, Zahlen und Fachbegriffe falsch erkennen. Gegen Quellcode und normative Verträge prüfen.

Beobachtete Repository-Basen: NIO `38c0c59f29895889c3988f1eb1d6a04c4da09362`, Agent-Quest `1c16b40eac3267e5d6b0d161284dbdccf0723684`. Beide Arbeitsbäume enthielten uncommittete Änderungen. Diese Hashes allein reproduzieren den gelesenen Arbeitsbaum nicht. Vor Ausführung verlangt P0 eine neue Dirty-Baseline; fremde Änderungen wurden nicht übernommen, zurückgesetzt oder committet.

## 2. Quellenkennungen des Manifests

| Kennung | Primärquelle / Fundstelle | Konsequenz |
|---|---|---|
| SRC27 | Notebook `d216335d-a06d-4f61-9027-ed85cb1ff183`, FAILED / Lesson Learned | Guide darf NIO nicht ersetzen; kleiner zerlegen; alte Completed-Meldungen keine Abnahme |
| SRC28 | Notebook `d9001bda-01c6-4308-b97e-2c4a8ece3898`, Handover | Reuse, Ausführungsblockaden, belegbarer Folgelauf |
| AQ-EDITOR | Agent-Quest `client/src/editor/game/scenes/EditorScene.ts:734`, `:764`, `:1347`; `server/src/map/routes.ts:79`; `client/src/editor/types/map.ts:106` | Terrain, Dekor, Pfade, Gebäude, NPCs, Spawn und Skalierung erhalten; Save bereits serverseitig |
| AQ-RENDER | `client/src/game/scenes/VillageScene.ts:454`, `:478`, `:561`, `:717`; `game/entities/Building.ts:28` | Rich Renderer behalten; prozeduralen Offlinebestand nur im Twin-Pfad ersetzen; Pointeraktionen zugänglich ergänzen |
| AQ-ISOLATION | `client/src/game/EventBridge.ts:48`; `game/data/road-network.ts:59`, `:248`; `editor/EditorBridge.ts:84`; `editor/state/editor-store.ts:138` | Globale Instanzen/Straßengraph trennen; BFS-Direktfallback nicht als gültigen Weg ausgeben |
| WB-PERSIST | NIO `world_bridge/state.py:8`, `:64`; `bridge.py:68`, `:73`, `:81`; `adapters.py:107` | RAM, Snapshotüberschreibung, Cursor-/Subscribe-Race und unbegrenzte Queues gezielt beheben |
| WB-PROMOTE | `world_bridge/router.py:29`, `:76`; `mcp_tools.py:8` | Behaupteten Promotionerfolg ohne Merge sperren; echte Commit-/Verdictbindung; Karten-APIs ergänzen |
| NB-NOIR | Studio `1a91dce2-c29b-4c59-8a70-c6cf34d765f0`, 21.11., Noir Sandbox-Gate/HITL-Report | Unabhängige Prüfbelege und Commitbindung übernehmen; behauptete Implementierung nicht ungeprüft glauben; Reject parkt |
| WCAG22 | [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/) | AA-Abnahme vollständiger Abläufe; Fokus, Tastatur, Drag-Alternative, Namen, Reflow und Status |
| AUDIO-TWIN | Studio `98a39e0e-dcea-470f-8815-d8a74f13abd7` | Stadtmetapher und Datenfluss; Korrekturen siehe Audioledger |
| AUDIO-GRAPH | Studio `d67c9919-5858-4428-9534-ea7a33885110` | Statische Beziehungen und Laufzeitbelege auseinanderhalten |
| AUDIO-NEU | Studio `3c257085-12e3-4677-84c8-4c44d4d08cf6` | Python-Verträge/Timer, isolierte Prüfungen, Crashberichte; keine absoluten Garantien übernehmen |
| AUDIO-UI | Studio `8e919334-bc72-4341-a47f-dcbaa4aae88e` | **Offen**, Inhalt nicht als gelesen behandeln |

Quellcodepfade in AQ-Zeilen beziehen sich auf `/home/finn-powers/Projects/Agent-Quest`, übrige auf dieses Repository. Zeilennummern sind Beobachtungspunkte, keine unveränderlichen Identitäten.

Weitere ausgewertete Notebook-Unterlagen:

- `e8094680-e2fa-4090-95f6-160e0a7aebcb` (25, DP-Plan) und `d4121546-72e5-4b63-a28c-95b210a0d15e` (26, Fortschritt): historische falsche 17-Tasks-/Delivered-Framings durch SRC27 aufgehoben.
- `901e1217-5dad-4f87-afee-5f18db3738ed` (22, Plan/Runtime): historischen Zustand von neuer Abnahme trennen.
- `91768bc4-9b7e-4432-8db5-a07befcdac23` (21, Graphify): extrahierte und abgeleitete Kanten unterscheiden; keine Laufzeitgarantie.
- `76047987-1793-460d-9512-0308b896c9df` (First-Principles-Audit): erzeugte Artefakte nachweisen; Optimierung ist keine Ausführung.
- `8e3538e1-06fe-4f97-93ae-8c6b2cd3c098` (Toolstrategie): B/MRU plus Metatool als Kontext; Prompt-Prefix-Umbau DORMANT.
- `f099970f-4cf2-4c51-aa4d-e995d235bc13` (v8.2) und `154cb39f-9d25-4ae0-aaa5-27db046f0239` (v8.1): konzeptionelle Vorgaben, kein aktueller Ausführungsnachweis.
- `0b13b3b5-59bd-4bd8-a55d-3fd36713af6d` (Circuit Breaker/Bus): begrenzte Recovery übernehmen, keine neuen Broker einführen.
- `db86d19d-6032-47db-a583-4f956907c829` (Nexus): Architekturkontext.
- Studio `e77fc5e4-c5cf-4925-bf7c-ec27032aed1d` (interaktiver Architekturreport): report_content gelesen; eingebettete interaktive Elemente nicht vollständig geprüft.
- Notizen `8c2bfd83-87ff-41a3-9878-1c7b276bcd62` und `dc48e170-af55-4786-8ccb-ffd413d43b66`: historischer Runtime-/UI-Kontext; Simulation widerspricht D2 und bleibt DORMANT.

## 3. Audioledger

### AUDIO-TWIN — Selbstprogrammierende KI als 3D-Stadt kontrollieren

Vollständige automatische Transkription, etwa 23:49. Übernommen: Informationsfluss als Stadt; Worker als Helden; geparkte Limbs/Taverne; Gate und Orb als sichtbare Systemzustände; gebatchte Updates gegenüber flüssiger Darstellung unterscheiden.

Korrigiert: Titel/Erzählung von 3D autorisieren keinen Rendererwechsel; Agent-Quest bleibt 2D-Pixelart. Eine world_id ist keine kryptografische Autorisierung. Ein Diff allein ist keine unabhängige Ergebnisprüfung. 17 große Tasks und angenommene 900 Sekunden bleiben durch den FAILED-Bericht widerlegt; vor Dispatch effektive Grenze messen. Aussagen über Modellgröße/Leistung sind kein aktueller Providerbeleg. „Kein lokaler Zustand“ betrifft bestätigte Datenautorität, nicht Kamera oder ungespeicherte Entwürfe. Bei 22:30–22:40 verlangter physischer Klick wird als bewusste autorisierte Entscheidung umgesetzt, auch per Tastatur/Screenreader.

### AUDIO-GRAPH — Der Graphify-Report der NIO-Codebasis auf dem Prüfstand

Vollständige automatische Transkription, etwa 16:35. Die Debatte problematisiert abgeleitete Kanten, isolierte Knoten und dynamische Verknüpfungen. Insbesondere etwa 14:10–16:20: statischer Codegraph ist kein Beleg aktueller Laufzeit, und eine fehlende Kante beweist keine fehlende dynamische Integration. Konsequenz: Request → Dispatch → Worker → Result → sichtbarer Zustand muss mit Runbelegen geprüft werden. Keine neue Graphplattform im Twin-City-Scope.

### AUDIO-NEU — Wie der NEU-Kern KI-Agenten bändigt

Vollständige automatische Streaming-Transkription; Mediendauer 1341,93 s (22:22), letzte ASR-Segmentgrenze 1342,72 s. Diese geringe ASR-Abweichung ist kein Beleg fehlender Audiodaten.

- 01:10–04:10: stdlib, Protocol 1.2, Dateitransport. Result läuft als JSON-Zeile über stdout; die Briefkastenmetapher darf nicht zu einer erfundenen Result-Dateiroute führen. Persistente Intentdatei allein beweist kein korrektes automatisches Recovery.
- 04:20–08:10: Deadline/Unlimited, Kontrolljobs und Safety-Net. Tatsächliche Konfiguration messen; Kontrolljobs verbrauchen kein Iterationsbudget, nicht pauschal jeder wartende Job. Ein CI-Skript beweist getestete Eigenschaften, keine universelle Schleifenfreiheit.
- 08:10–10:40: Prozessüberwachung, TERM/KILL und synthetischer Crashbericht. Zeitwerte und Eskalation vor Nutzung im Eigentümercode prüfen; UI darf Timer nicht bestimmen.
- 10:40–14:40: REA-Sandbox und historische Spiele-/Trading-Beispiele. Als Architekturmotivation gelesen; „Host niemals gefährdet“, „keine Halluzinationen“ und historische Erfolgsquoten sind keine belastbaren Garantien dieses Plans. Keine fremden Binaries für diese Planrevision ausführen.
- 14:40–18:40: isolierte Testverzeichnisse, Outcomes und Skillbewertung. Live-Worker niemals als Testfixture nutzen; Lernsystem-Neuentwicklung bleibt DORMANT. stdlib-Regel gilt für den NEU-Core, nicht pauschal für alle unabhängigen Stacks dieses Repos.
- 18:40–22:22: behauptete jahrzehntelange Deterministik und automatisches atomisches Drive-/Merkle-Rollback sind **nicht verifiziert**. Kein automatisches Löschen fehlerhafter Historie übernehmen. D5 verlangt Parken und nachvollziehbare Recovery.

### AUDIO-UI — Das perfekte Interface für autonome KI

**Nicht ausgewertet.** CLI-Download zweimal fehlgeschlagen; direkter Mediaabruf lieferte HTML statt Audio. Authentifizierter Download meldete Weiterleitung zur Loginseite. `nlm login` konnte keinen Anmeldebrowser starten, weil Chrome bereits läuft (Exit 21). Keine Nutzerfenster geschlossen und keine Cookies ausgegeben. Die irreführende HTML-Datei trägt im Cache `.login.html`, nicht `.m4a`.

Abschlussvoraussetzung: NotebookLM-Sitzung erneuern, gültigen Audiostream laden und Typ/Dauer prüfen, lokal transkribieren, UI-Aussagen gegen bestehenden Editor und Accessibility-Vertrag abgleichen, Plan bei Abweichung revidieren und Quellenreview erneut durchführen. **PLAN_REVIEW bleibt bis dahin offen; keine automatische Freigabe von P0.**

## 4. Reverse Engineering und visuelle Referenz

Quellcode zeigt acht feste funktionale Gebäudetypen (`building-layout.ts:37`, Validator `server/src/map/validator.ts:25`), fünf Slots, Template-/Default-Laden und Slot-Reset (`server/src/map/routes.ts`). Kein Nachweis beliebig vieler funktionaler Städte oder NIO-Worker-Provisionierung durch NPC-Platzierung. Diese Grenzen sind konkrete Anpassungsstellen, kein Grund zum Editor-Neubau.

In der laufenden Oberfläche auf :4445 wurden Dorf und Editor betrachtet: Terrain, Bäume, Gebäude und Sprites; Editoranzeige acht Gebäude, 51 NPCs, 1276 Terrainobjekte, 660 Dekorationen und zehn Pfade. NPC-Palette und Slot-/Template-Aktionen sichtbar. Keine Karte gespeichert, platziert, gelöscht oder aktiviert. Spritesheet-Fehler, etwa `archer-blue-noarms`, wurden beobachtet und bleiben Baselinefehler für P5. Visuelle Beobachtung ist kein persistenter Screenshotbeleg und keine komplette Funktionsabnahme.

REA-MCP konnte zuvor nicht starten. Ein tatsächlicher MCP-Neustart wurde nicht bestätigt. Default-Node 20 scheiterte an fehlendem `node:zlib`-Export `zstdDecompress`. Mit bereits installiertem Node 24.22.3 antwortete die REA-CLI; keine Installation oder globale Konfigurationsänderung. Doctor: Registrierung für Codex gesund, optionale native Engines fehlen; dies beweist nicht MCP-Gesundheit.

REA `list_browser_targets`, CDP :9222, Origin `http://localhost:4445`: keine passenden offenen Targets. Evidence-ID `ev_ed1c8a214e9dfc5926b85f310c28d7cb41f658065147f1f14a7d7c9c3dc8c73b`. Das belegt ausschließlich die Targetsuche, **keine REA-Analyse des Frontends**. Die belastbaren Frontendbefunde stammen aus Quellcode und gesonderter Browserbeobachtung. Ein REA-Laufzeitcapture bleibt nach funktionsfähiger Verbindung offen.

## 5. Aktueller NIO-Zustand und historische Fehler

Lesender Kanban-Abruf am 22.11.: 92 Aufgaben, davon 47 blocked und 45 completed; keine ready/in_progress. Fünf Worker idle. Board `b-5fb62933ab27` (Apollo), Shadow `b-6dbbabed81b9`. Offene Beispiele: `t-e2859679b442` TwinCity-P1-Blueprint, `t-db173071f92f` Nexus-Learnings, `t-1765d446ba44` Stadt-Spawn, `t-61df7b5f61a4` interne LILITH-Kommunikation. Kein Boardstatus wurde geändert. Historische completed-Meldungen bleiben von Produktabnahme getrennt; veraltete Option-A/B-Tasks bedürfen späterer Triage.

R1–R4 aus SRC27 sind historische Befunde, keine pauschale aktuelle Diagnose. Am 22.11. lagen bereits fremde uncommittete Änderungen in `orchestrator/kanban/sandbox.py`, `worker_entry.py` und zugehörigen Tests vor, die Task-Repo-Mount und Error-only-Erkennung adressieren. Daher erst verifizieren und nur verbleibende Lücken reparieren: Git-common-dir bei Worktrees, tatsächliche Tool-/Modellfähigkeit, effektive Deadlines und eigener Ergebnisnachweis. Keine Secrets oder Modellkonfiguration verändert.

Der generierte Noir-Report nennt `tools/selfcode/sandbox_gate.py`; dieser Pfad wurde im NIO-Bestand nicht gefunden. HMAC-/Gate-/Rollback-Beschreibungen daraus sind Anforderungen beziehungsweise Behauptungen, keine nachgewiesene Implementation. API :4000 war beim Healthcheck nicht erreichbar; ihr DeterministicCoreAdapter ist kein Ersatz für reale Kanban-Ausführung.

## 6. Review und Freigabegrenze

Erster Noir-Review: 6/8, Sicherheitsanteil 2/2, lokale/reversible Planänderung; Freigabe wegen sachlicher Planlücken verweigert. Korrekturen: Validator vor Parität/Save, zusätzliche Template-/Default-/Reset-/Migrationseinheiten, getrennte Stack-Receipts, gesonderter bedingter Deployment- und Runtime-Smoke-Schritt. Manifest nun 143 Aufgaben statt exakt 128; die Zahl ist kein Optimierungsziel.

Diese Revision erzeugt Dokumente, keine Produktlieferung. Kein Commit, Push, Merge, Deployment oder Kanban-Dispatch. **Offen bleiben AUDIO-UI-Abgleich und echter REA-Laufzeitnachweis; die Quellenabnahme ist deshalb nicht abgeschlossen.**

Abschließender gezielter Noir-Review (22.11.): **8/8, Sicherheitsanteil 2/2**, keine verbleibenden materiellen Dokumentfehler. Geltungsbereich ausschließlich konditionelle Dokumentlieferung. Verifiziert: 143 eindeutige Aufgaben, azyklische serielle Dependencies, Validator vor Regression/Save, zusätzliche Editor-/Migrationsabdeckung, getrennte Stackprüfungen, bedingtes Deployment vor Runtime-Smoke/Gesamtabnahme, MD/JSON-Parität, alle Quellenkennungen aufgelöst, Artefaktmetadaten konsistent und alle 44 lokalen Quellenhashes identisch. `git diff --check -- docs/hermes` erfolgreich. **Dies gibt PLAN_REVIEW nicht frei:** AUDIO-UI und REA-Laufzeitnachweis bleiben offen. Nach deren Ergänzung erneuter Quellen-/Planreview erforderlich.
