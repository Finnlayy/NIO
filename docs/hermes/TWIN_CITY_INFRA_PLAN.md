# Twin-City — überarbeiteter Ausführungsplan

Stand: 22.11.2026. Auftrag: **zuerst planen**, mit NIO-Notebook, Audios und Agent-Quest-Bestand. Dies ist ein Ausführungsplan, keine Implementierungsabnahme. Der vorherige Run bleibt **FAILED**; „all delivered“ und Guide-Finish sind aufgehoben. [Unveränderter Altplan](archive/TWIN_CITY_INFRA_PLAN_2026-11-21_FAILED.md).

**Planstand: 143 atomare Aufgaben. Quellenabnahme offen:** drei von vier Audios ausgewertet; AUDIO-UI benötigt erneuerte NotebookLM-Anmeldung. PLAN_REVIEW und alle Ausführungsaufgaben bleiben blockiert, bis der letzte Audioabgleich und die offene REA-Laufzeitprüfung abgeschlossen sind.

## 1. RGCCO und Zielbild

**Role:** Guide plant, überwacht später NIO und prüft Ergebnisse. NIO-Kanban-Worker erzeugen Produktänderungen.
**Goal:** Zwei getrennte NIO-Welten als vollwertige Agent-Quest-Pixelart-Städte mit Terrain, Gebäuden, Helden, NPCs, Wetter und dem bestehenden Karteneditor. Karten gestalten/speichern/laden; reale Arbeit und Gate-Entscheidungen sichtbar und bedienbar machen.
**Constraints:** WIP = 1; bestehende Dienste und uncommittete Arbeit schützen; keine Ersatzimplementierung durch den Guide.
**Context:** [Quellen und Befunde](TWIN_CITY_EVIDENCE.md), [Blueprint](TWIN_CITY_ARCHITECTURE_BLUEPRINT.md).
**Output:** [atomare Aufgaben](TWIN_CITY_TASKS.md), [maschinenlesbares Planmanifest](TWIN_CITY_TASKS.json).

**Non-Goals / DORMANT:** Neuer 3D-Renderer, Ersatz für VillageScene oder Editor, ungeprüfter A*-Umbau, neue Message-Broker/Java-Runtime, Prompt-Caching-Umbau, Trading-Logik, Worker-Erstellung durch NPC-Platzierung, beliebige weitere Ausführungswelten.

## 2. Invarianten

- **D1 Serverautorität:** NIO hält bestätigte Karten, Districts, NPCs, Gates und Ausführungszustand. Clientseitig zulässig: Kamera, Auswahl, Animation und sichtbar ungespeicherter flüchtiger Entwurf. Keine persistente Browser-Ersatzwahrheit. Speicherbestätigung erst nach erfolgreicher Serverpersistenz; Editorentwürfe lösen keine Jobs aus.
- **D2 Ehrliche Zustände:** Ohne gültigen Backendzustand nur Orb und lesbarer Verbindungsstatus; keine prozedural erfundenen Gebäude/Worker. Bei Abbruch Mutationen sperren, Weltinhalt ausblenden und Status anzeigen; keine blinden Command-Retries. Authentifizierte leere Welt, Fehler, getrennte Verbindung und Laden unterscheiden.
- **D3 Isolation:** world_id bei jedem Zugriff/Befehl. Getrennte Speicherbereiche, Boards, Repos, Gate-Autorität und Ausführung. Auch EventBridge, Straßengraph, Stores und Szenen trennen. Gleiche Entity-IDs in zwei Welten dürfen nicht kollidieren.
- **D4 Wiederverwendung:** VillageScene, EditorScene, TerrainRenderer, MapConfigRenderer, Building, HeroSprite, NpcSprite, Assets und vorhandene BFS bleiben Grundlage. Bun-Watcher/Session-Parser entfallen nur im Twin-City-Produktpfad; keine Editorfähigkeit entfällt dadurch.
- **D5 Git-Nachweis:** NIO verwaltet Worktrees. Run-ID, Worker-ID, tatsächliches Modell, Basis-/Ergebnis-Commit, Diff und Prüfbelege gehören zusammen. Reject und Timeout parken Arbeit. Kein automatisches Löschen, Force-Push oder Umdeuten von Guide-Arbeit zu Worker-Erfolg.
- **D6 Zugänglichkeit:** Gleichwertige DOM-Bedienung zusätzlich zur Karte. Stadt-, Objekt-, Speicher- und Gate-Aktionen per Tastatur, Screenreader und Einzelzeiger ohne Ziehen ermöglichen.
- **D7 Ergebnisnachweis:** Exit-Code, Commit oder grüne Tests allein sind keine Produktabnahme. Funktion, visuelle Qualität, Isolation und tatsächliche NIO-Produktion jeweils belegen.

## 3. Korrigierter Bestand

Agent-Quest besitzt fünf Kartenslots, aktive Karte, Templates, Terrain, Dekorationen, Pfade, Gebäudebewegung, NPC-Erstellung, Spawn und Skalierung. Speichern erfolgt bereits serverseitig. **Editor löschen wegen „lokaler Persistenz“ war falsch.** Acht funktionale Gebäude sind fest definiert; freie Hausdekoration ist noch kein neuer funktionaler District.

World-Bridge prüfen und nur belegte Lücken ergänzen: aktuell RAM-Zustand, kein dauerhafter Karten-/NPC-Speicher, Snapshot überschreibt dynamische Districts, Promotion-Erfolg ohne Merge. Alte Testzahlen sind keine Abnahme dieser Eigenschaften.

Agent-Quest bleibt laufendes Nutzerwerkzeug und Referenz. Sein Arbeitsbaum enthält fremde Änderungen; ein sauberer Commit bildet diesen Baum nicht vollständig ab. Am 22.11. vorhandene fremde Laufzeitänderungen adressieren bereits Mount und Error-only-Erkennung; P0 prüft deren Wirkung und verbleibende Lücken. Vor Umsetzung Basis und relevante uncommittete Änderungen inventarisieren, kein pauschales Stash/Reset/Übernehmen.

## 4. Architekturentscheidungen

1. **Welt ≠ Stadt:** world_id = live|shadow. map_id = Karte; slot_id = zunächst einer von fünf Speicherplätzen je Welt. Aktivierung nur in ihrer Welt. „Stadt neu“ erzeugt keine weitere Ausführungswelt.
2. **Typ ≠ Instanz:** district_id stabil und frei innerhalb der Welt; asset_type bestimmt Darstellung; district_type/Capability verbindet NIO-Funktion. Zwei Schmieden können verschiedene IDs haben.
3. **NPC ≠ Worker:** Dekorative Bewohner mit eigener ID und Placement; keine Prozesse durch Platzierung. Helden repräsentieren serverbestätigte Worker.
4. **Serverpersistenz:** Versionierte MapConfig-Dokumente und Metadaten im bestehenden NIO-/Redis-Bereich; atomare Revision-/Idempotenzprüfung mit kleinem Lua-Skript und bestehendem Redis-Zugriff. Kein zweites Datenbank-Framework. AOF/Recovery vor Neustartversprechen prüfen; Redis-Ausfall darf keine Speicherbestätigung liefern. Python ist Eigentümer; Bridge adaptiert.
5. **Reproduzierbares Layout:** Logische Raster-/Pfaddaten, Assetreferenzen und Layoutversion speichern, keine browserabhängigen Bildschirmkoordinaten. Bestehende MapConfig-Weltkoordinaten verlustfrei migrieren; Einheiten/Umrechnung festlegen. Automatische Slots nur als Vorgabe für neue Districts; manuelle Layouts nicht bei Snapshot neu verteilen.
6. **Transport:** Versionierte Snapshots/Deltas, Sequenz je Welt plus Neustartkennung. Resync bei Lücke/Epochwechsel. Snapshot-Abonnement ohne verlorenes Zwischenereignis, begrenzte Clientqueues, kontrollierter Reconnect, Fehler je Welt isoliert.
7. **Datenrate ≠ Pollrate:** Maximal 15 gebatchte Ausgaben/s/Welt als Obergrenze; vorhandene SSE-/Bus-Events nutzen, keine 15 vollständigen Backendabfragen/s ableiten. 60 FPS als gemessenes Renderziel auf dokumentierter Hardware. Gate-Updates dürfen nicht verhungern.
8. **Browserauth:** Backendtokens serverseitig; keine langfristigen Tokens in Bundle, LocalStorage oder WS-URL. Bestehende NIO-Authentifizierung zuerst prüfen; eng begrenzte Sitzung oder kurzlebiges WS-Ticket, Origin-/CSRF- und Weltprüfung. Keine allgemeine IAM-Neuentwicklung.
9. **Promotion:** Falschen Erfolg zuerst sperren. Danach gespeicherten Verdict an Repo, Basis, Kandidaten-Commit und Diff binden, Autorität/Gültigkeit prüfen, Orchestrator-Merge ausführen, Receipt zurückgeben. Request-Flags sind keine Freigabe. Geänderter Head invalidiert den Verdict.
10. **Reject:** Branch/Worktree mit Grund und Hash parken. Löschbeschreibung des generierten Noir-Reports wird wegen D5 nicht übernommen.

## 5. Phasen und harte Gates

Genaue Einzelaufgaben stehen im Manifest. Phasen seriell, höchstens eine aktive Aufgabe. Accessibility beginnt beim Vertrag.

| Phase | Ergebnis | Gate vor nächster Phase |
|---|---|---|
| P0 Ausführungsfähigkeit | Mount, Modell/Tools, Deadlines, Hollow-Guard, Provenienz | NIO-Canary und Cross-Repo-Canary mit echten Artefakten/Commits; Error-only abgewiesen |
| P1 Verträge/Reuse | Feldmapping, Datenautorität, Quellenkonflikte, Assets/Buildgrenze | Kein verlorenes Editorfeld; Welt/Stadt/NPC/Worker eindeutig |
| P2 Persistenz/Isolation | Revisionen, Events, Resync, Ausfälle | Gleiche IDs unabhängig; neuer Client, Reconnect und Neustart bewahren bestätigte Daten |
| P3 APIs/Gates | Kartenbefehle, Auth, echte Entscheidungen/Promotion | Fremde Welt, gefälschte Freigabe, veralteter Head abgewiesen; echter Merge-Receipt; Reject parkt |
| P4 Village | Rich Rendering aus NIO-Daten, isolierte Szenen | Reales Gebäude, gültige Heldenwege, kein erfundener Offlinezustand |
| P5 Editor | Werkzeuge, fünf Slots, Save/Load/Activate, Konflikte | Alle MapConfig-Felder im Roundtrip; NPC erzeugt keinen Worker |
| P6 Accessibility | Vollständige alternative Bedienwege | Tastatur/Screenreader, Kontrast, Reflow, Zielgrößen, reduzierte Bewegung |
| P7 Integration/Betrieb | Echte NIO-Ausführung, Twin-View, Fehlerfälle, Deployment/Rückweg | Visuelle Referenz, technische Gates und Worker-Provenienz am ausgelieferten Stand |

## 6. Aufgabenvertrag und Monitor

Jede Einheit: RGCCO-Ziel, begrenzte Dateien, Quellen, Dependencies, Abnahme, Prüfverfahren, Artefakte, Budget, Fehleraktion. Zielbudget 300 s, zunächst höchstens 450 s. Historischer OpenCode-Default 600 s; vor Dispatch zählt das **gemessene Minimum** aller Modell-/Tool-/Worker-/Sandbox-/Jobdeadlines abzüglich Start-, Prüf- und Commitreserve. Zu große Einheit teilen. Taskzahl ist kein Optimierungsziel.

Plan-IDs erst beim späteren Import auf echte Kanban-IDs abbilden. Titel „Schritt N — …“, Beschreibung endet „- [offen]“. Alle blocked anlegen; einzeln nach erfüllten Dependencies ready. Kein Bulk-Backlog mit unerwartetem Autodispatch.

**API-Abgleich:** Aktuelles TaskCreate hat workspace_repo und dependencies, aber **kein workspace_kind**. worktree ist Planmetadata, kein ungeprüft sendbares API-Feld. Dispatcher erzeugt den Worktree anhand workspace_repo. Aktuelles Schema vor Import erneut prüfen. Codeaufgaben brauchen required_skills=code.

Codeerfolg: passendes Run-Result, tatsächlicher Diff im zugewiesenen Worktree, Prüfungen am exakten Head. Prüftask: gehashtes Berichtartefakt zulässig, kein künstlicher Produktcommit. Vorgängercommit nicht als eigene Arbeit zählen.

Bei Timeout, Error-only-Tools, leerem Diff oder falscher Funktion: offen/blocked lassen; Ursache klassifizieren; Ausführungsblockade als begrenzte Voraussetzung reparieren oder Task teilen; erneut NIO ausführen lassen. **Kein Guide-Finish.** Heartbeats ersetzen keinen Fortschrittsnachweis; Retry begrenzen und Ursache dokumentieren.

Phasenbeleg: reviewed_commit, Exit-Codes, Hashes, manuelle Protokolle, Restlücken, Freigabe. Skip wegen fehlendem Docker/Browser/Dependencies bedeutet nicht bestanden. Stack-Gates passend zur Änderung; Runtime-/GUI-Abnahme separat.

## 7. Accessibility-Abnahme

Ziel WCAG 2.2 AA für komplette Bedienabläufe. Native HTML-Controls, sichtbarer/unverdeckter Fokus, benannte Felder, verständliche Fehler, dosierte Statusmeldungen. Canvas erhält DOM-Liste mit Auswahl, Positionsfeldern und Aktionen; Dragging optional. Zweidimensionale Karte darf räumlich bleiben; Formulare/Listen/Dialoge bleiben bei Reflow bedienbar.

Kriterien: 2.1.1 Tastatur, 2.1.2 keine Falle, 2.4.7 Fokus sichtbar, 2.4.11 Fokus nicht verdeckt, 2.5.7 Drag-Alternative, 2.5.8 Zielgröße, 1.4.3/1.4.11 Kontrast, 1.4.10 Reflow, 4.1.2 Name/Rolle/Wert, 4.1.3 Status. Projektziel mindestens 24×24 CSS-Pixel je Control ohne Abstandsausnahme; Normaltext 4.5:1, großer Text/relevante UI-Grenzen 3:1. Reduced Motion und abschaltbare Wetter-/Orb-Effekte; Weltstatus nicht nur farblich. 2.4.13 Focus Appearance ist AAA, kein AA-Kriterium.

[Normative Referenz W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/). Automatisierte Checks ergänzen Tastatur-, Screenreader-, Zoom- und Touchprüfung; DOM-Snapshot allein beweist keine Konformität.

## 8. Produkt-DoD

1. NIO erzeugt nachweisbar eine Änderung, sichtbar als echtes Gebäude mit Straße und gültiger Heldenbewegung.
2. Stadt bearbeiten, NPC setzen, Gebäude ändern, speichern, aktivieren, neu laden und Neustart bewahren bestätigte Felder.
3. Gleiche IDs, gleichzeitige Szenen, Reconnect und schnelle Weltwechsel verletzen Isolation nicht.
4. Gate-Aktion gilt exakt dem geprüften Stand; Promotion liefert Orchestrator-Beleg; Reject bewahrt Arbeit.
5. Backendverlust/leere Zustände erzeugen keine fiktive Aktivität; Save/Dispatch zeigen Fehler ehrlich.
6. Abläufe ohne Mausziehen; visuelle Qualität entspricht Agent-Quest; Asset-Ladefehler geklärt.
7. Ausgelieferter Commit, Assets, Backend und Belege passen zusammen; Rückweg dokumentiert; Nutzer-Agent-Quest funktioniert weiter.

## 9. Revisionsstatus

Nur Planung/Evidenz beauftragt. Keine Produktaufgabe gestartet oder abgeschlossen, keine Änderung an nio.env, Modellen, Diensten oder Boards.

NIN-Legacy-API :4000 beim Healthcheck nicht erreichbar. Ihr DeterministicCoreAdapter liefert Promptmetadaten, keine produktive Kanban-Ausführung. Ein Start allein würde diese Lücke nicht beheben; aktuelle Anweisung „zuerst Plan“ bleibt maßgeblich.

REA konnte MCP nicht starten; CLI antwortet mit vorhandenem Node 24, aber die Targetsuche ersetzt keine Frontendanalyse und bestätigt keinen MCP-Neustart. Quellcode- und Browserbefunde separat belegt. Quellen-/Audioabdeckung und Grenzen: [Evidenzregister](TWIN_CITY_EVIDENCE.md). Späterer Start beginnt mit P0.
