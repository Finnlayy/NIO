# Twin-City — atomarer NIO-Ausführungsplan

Stand: 2026-11-22. **143 Aufgaben, alle blockiert und nicht ausgeführt. WIP-Limit: 1.**

Maschinenlesbare Quelle: [TWIN_CITY_TASKS.json](TWIN_CITY_TASKS.json). Dies ist ein Planmanifest, kein direkt sendbarer API-Payload. `workspace_kind=worktree` ist nur Planmetadatum: Der aktuelle `TaskCreate` besitzt dieses Feld nicht. Vor Import Plan-IDs in echte Task-IDs auflösen und API-Vertrag erneut prüfen.

NIO erzeugt spätere Produktänderungen. Der Guide überwacht, prüft exakte Workercommits und dokumentiert Blockaden. Fehlgeschlagene Arbeit wird geparkt und nach Ursachenbehebung erneut an NIO gegeben. Aus dieser Planrevision folgt kein Dispatch, Deployment, Merge oder Modellwechsel.

Jede Aufgabe hat standardmäßig 300 Sekunden Zielbudget, höchstens 450 Sekunden. Vor Ausführung das effektive Minimum aus Worker-, Dispatcher- und Providergrenzen messen und Start-/Prüf-/Commitreserve berücksichtigen. Reicht das nicht, weiter zerlegen. Keine künstliche Obergrenze für die Zahl der Arbeitspakete.

Alle Aufgaben hängen seriell vom unmittelbaren Vorgänger ab. Der letzte Task jeder Phase prüft das zugehörige Gate. Nur nach bestandener Abnahme wird genau ein Nachfolger ready gesetzt. Vorhandene korrekte Implementierung wird übernommen; Aufgaben verlangen nur belegte Änderungen.

Belegpflicht: Task-/Run-/Worker-/Modell-ID, Worktree, HEADs, geänderte Pfade, SHA-256, Prüfung, geprüfter Commit und Gateurteil. Reine Prüftasks benötigen ein überprüfbares Berichtartefakt mit Runprovenienz; Produktänderungen benötigen einen eigenen nachgewiesenen Workercommit. Skip, Exit 0 oder completed allein genügen nicht.

Geplante Dateien sind ausdrücklich markiert. Prüfkommandos beschreiben spätere Abnahmen; in diesem Dokument werden keine bestandenen Produktprüfungen behauptet. Tests verwenden eigene Verzeichnisse und Fakeadapter. Runtime-/Docker-/Redis-Proben benötigen ausdrücklich eine isolierte Testumgebung.


## P0 — Ausführungsfähigkeit und Provenienz

TC-001–TC-016; Abschlussgate **G0**.

### TC-001 — Schritt 1 — Repo- und Dirty-Baseline erfassen

- **Ziel/Abnahme:** HEAD, Branch, uncommittete Pfade und Dienstzuordnung beider Repos sind belegt; keine vorhandene Änderung übernommen.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_EXECUTION_BASELINE.md` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** git status --short und git rev-parse HEAD je Repo lesen; Pfadliste im Bericht vergleichen.
- **Abhängigkeit:** Planreview; Phasenvoraussetzung PLAN_REVIEW.
- **Quellen:** SRC27, SRC28, AUDIO-NEU. **Status:** blocked / nicht ausgeführt.

### TC-002 — Schritt 2 — Effektive Zeitgrenze ermitteln

- **Ziel/Abnahme:** Worker-, Dispatcher- und Modellgrenzen sowie Start-/Commitreserve sind dokumentiert; kleinstes Limit gilt.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `orchestrator/kanban/worker_entry.py` (vorhanden); `orchestrator/kanban/config.py` (vorhanden).
- **Prüfung:** Konfiguration ohne Secretwerte lesen; 600s-Default gegen tatsächlich wirksame Laufparameter prüfen.
- **Abhängigkeit:** TC-001; Phasenvoraussetzung PLAN_REVIEW.
- **Quellen:** SRC27, SRC28, AUDIO-NEU. **Status:** blocked / nicht ausgeführt.

### TC-003 — Schritt 3 — Modellroute identifizieren

- **Ziel/Abnahme:** Tatsächlich aufgelöste Modell-ID und Toolfähigkeit sind belegt; Safety-Classifier gilt als ungeeignet.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `config/opencode/opencode.json` (vorhanden).
- **Prüfung:** Einen begrenzten Modellprobebericht mit Antworttyp und aufgelöster Route prüfen; kein Providername aus Wunschliste übernehmen.
- **Abhängigkeit:** TC-002; Phasenvoraussetzung PLAN_REVIEW.
- **Quellen:** SRC27, SRC28, AUDIO-NEU. **Status:** blocked / nicht ausgeführt.

### TC-004 — Schritt 4 — Tool-Roundtrip nachweisen

- **Ziel/Abnahme:** Ein isolierter Probeaufruf liest eine Testdatei per Tool und liefert deren Inhalt; Textantwort allein genügt nicht.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_EXECUTION_BASELINE.md` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Toolaufruf, Exitcode, Dauer und Ergebnis derselben Probe zusammen prüfen; keine externen Schreibaktionen.
- **Abhängigkeit:** TC-003; Phasenvoraussetzung PLAN_REVIEW.
- **Quellen:** SRC27, SRC28, AUDIO-NEU. **Status:** blocked / nicht ausgeführt.

### TC-005 — Schritt 5 — Git-Verzeichnis des Task-Repos auflösen

- **Ziel/Abnahme:** Mountplanung nutzt den kanonischen git-common-dir des erlaubten Task-Repos und erhält NIO-Hilfsmounts.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `orchestrator/kanban/sandbox.py` (vorhanden).
- **Prüfung:** NIO- und Agent-Quest-Fixture mit unterschiedlichen Git-Verzeichnissen vergleichen; Pfad außerhalb Allowlist ablehnen.
- **Abhängigkeit:** TC-004; Phasenvoraussetzung PLAN_REVIEW.
- **Quellen:** SRC27, SRC28, AUDIO-NEU. **Status:** blocked / nicht ausgeführt.

### TC-006 — Schritt 6 — Cross-Repo-Mountregression ergänzen

- **Ziel/Abnahme:** Test beweist korrekten Git-Mount für Fremdrepo und verweigert nicht erlaubte Ziele.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `tests/test_kanban_sandbox.py` (vorhanden).
- **Prüfung:** python3 -m unittest tests.test_kanban_sandbox -v; neue Tests müssen beide Repo-Fälle tatsächlich ausführen.
- **Abhängigkeit:** TC-005; Phasenvoraussetzung PLAN_REVIEW.
- **Quellen:** SRC27, SRC28, AUDIO-NEU. **Status:** blocked / nicht ausgeführt.

### TC-007 — Schritt 7 — Hollow-Erfolg schließen

- **Ziel/Abnahme:** Error-only-Tools ohne geänderten Commit ergeben bei Produktaufgaben keinen completed-Status.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `orchestrator/kanban/worker_entry.py` (vorhanden).
- **Prüfung:** Fixture Exit0 plus ausschließlich fehlerhafte Tools ausführen; Ergebnis blocked oder failed mit Ursache prüfen.
- **Abhängigkeit:** TC-006; Phasenvoraussetzung PLAN_REVIEW.
- **Quellen:** SRC27, SRC28, AUDIO-NEU. **Status:** blocked / nicht ausgeführt.

### TC-008 — Schritt 8 — Hollow-Guard regressionsprüfen

- **Ziel/Abnahme:** Erfolgreicher eigener Commit, leere Antwort und Error-only-Lauf werden unterschieden.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `tests/test_kanban_opencode.py` (vorhanden).
- **Prüfung:** python3 -m unittest tests.test_kanban_opencode -v; Assertions für alle drei Ausgänge prüfen.
- **Abhängigkeit:** TC-007; Phasenvoraussetzung PLAN_REVIEW.
- **Quellen:** SRC27, SRC28, AUDIO-NEU. **Status:** blocked / nicht ausgeführt.

### TC-009 — Schritt 9 — Taskvertrag gegen API abgleichen

- **Ziel/Abnahme:** Importmapping enthält nur unterstützte API-Felder; workspace_kind bleibt Planmetadatum.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `orchestrator/kanban/api.py` (vorhanden); `orchestrator/kanban/models.py` (vorhanden).
- **Prüfung:** TaskCreate und KanbanTask Feldliste lesen; blocked, dependencies, required_skills und workspace_repo einzeln abgleichen.
- **Abhängigkeit:** TC-008; Phasenvoraussetzung PLAN_REVIEW.
- **Quellen:** SRC27, SRC28, AUDIO-NEU. **Status:** blocked / nicht ausgeführt.

### TC-010 — Schritt 10 — Worker-Buildfähigkeit inventarisieren

- **Ziel/Abnahme:** Vorhandene Node-/Python-/Git-Werkzeuge und erlaubte Befehle sind dokumentiert; fehlende Checks gelten als blockiert.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docker/opencode-worker/Dockerfile` (vorhanden); `config/opencode/opencode.json` (vorhanden).
- **Prüfung:** Werkzeugversionen im vorgesehenen Testcontainer lesen; Guide-Hostcheck nur am exakten Worker-Commit zulassen.
- **Abhängigkeit:** TC-009; Phasenvoraussetzung PLAN_REVIEW.
- **Quellen:** SRC27, SRC28, AUDIO-NEU. **Status:** blocked / nicht ausgeführt.

### TC-011 — Schritt 11 — Run-Evidence-Vertrag festlegen

- **Ziel/Abnahme:** Run-ID, Worker, Modell, Worktree, HEADs, Diffpfade, Hashes und Prüfergebnis sind Pflichtbelege.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_EXECUTION_BASELINE.md` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Ein vollständiges und ein unvollständiges Beispiel gegen die dokumentierte Pflichtfeldliste prüfen.
- **Abhängigkeit:** TC-010; Phasenvoraussetzung PLAN_REVIEW.
- **Quellen:** SRC27, SRC28, AUDIO-NEU. **Status:** blocked / nicht ausgeführt.

### TC-012 — Schritt 12 — Timeout-Parken nachweisen

- **Ziel/Abnahme:** Ein abgebrochener Lauf erhält vorhandene WIP-Commits und dokumentiert Restarbeit; kein automatisches Löschen.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `tests/test_kanban_opencode.py` (vorhanden).
- **Prüfung:** Isolierten Testlauf terminieren; Branch und Commit danach lesen; Produktions-Worktrees nicht berühren.
- **Abhängigkeit:** TC-011; Phasenvoraussetzung PLAN_REVIEW.
- **Quellen:** SRC27, SRC28, AUDIO-NEU. **Status:** blocked / nicht ausgeführt.

### TC-013 — Schritt 13 — NIO-Repo-Minimalauftrag beweisen

- **Ziel/Abnahme:** Ein echter NIO-Kanban-Worker erzeugt eine abgegrenzte Teständerung und einen eigenen Commit im vorgesehenen Repo.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_EXECUTION_BASELINE.md` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Task und Run korrelieren; head_before/head_after, git show und Artefakthash gegen Result prüfen.
- **Abhängigkeit:** TC-012; Phasenvoraussetzung PLAN_REVIEW.
- **Quellen:** SRC27, SRC28, AUDIO-NEU. **Status:** blocked / nicht ausgeführt.

### TC-014 — Schritt 14 — Agent-Quest-Minimalauftrag beweisen

- **Ziel/Abnahme:** Ein echter Worker kann im Agent-Quest-Worktree eine isolierte Probeänderung erzeugen und committen.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_EXECUTION_BASELINE.md` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Gleiche Provenienzprüfung wie NIO-Probe; fremde Dirty-Pfade dürfen nicht im Commit erscheinen.
- **Abhängigkeit:** TC-013; Phasenvoraussetzung PLAN_REVIEW.
- **Quellen:** SRC27, SRC28, AUDIO-NEU. **Status:** blocked / nicht ausgeführt.

### TC-015 — Schritt 15 — Seriellen Freigabemechanismus prüfen

- **Ziel/Abnahme:** Genau eine Twin-City-Aufgabe kann aktiv sein; blockierte Nachfolger starten nicht automatisch.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `orchestrator/kanban/dispatcher.py` (vorhanden).
- **Prüfung:** Zwei isolierte abhängige Testaufgaben beobachten; nur eine ready setzen, Startreihenfolge belegen.
- **Abhängigkeit:** TC-014; Phasenvoraussetzung PLAN_REVIEW.
- **Quellen:** SRC27, SRC28, AUDIO-NEU. **Status:** blocked / nicht ausgeführt.

### TC-016 — Schritt 16 — Gate G0 Ausführungsfähigkeit abnehmen

- **Ziel/Abnahme:** Beide echten Repo-Proben und Negativfälle sind belegt; Produktarbeit bleibt bei jeder Lücke blockiert.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_EXECUTION_BASELINE.md` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Noir prüft P0-Belege am jeweiligen Commit; Skip, Timeout und fehlende Toolbelege sind keine bestandene Abnahme.
- **Abhängigkeit:** TC-015; Phasenvoraussetzung PLAN_REVIEW.
- **Quellen:** SRC27, SRC28, AUDIO-NEU. **Status:** blocked / nicht ausgeführt.

## P1 — Verträge und Bestandsgrenzen

TC-017–TC-033; Abschlussgate **G1**.

### TC-017 — Schritt 17 — MapConfig-Felder vollständig zuordnen

- **Ziel/Abnahme:** Weltgröße, Terrain, Dekorationen, Pfade, Gebäude, NPCs, Spawn, Maßstab, Namen und Zeitstempel sind ohne Feldverlust zugeordnet.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/nio_world_api_spec.yaml` (vorhanden).
- **Prüfung:** Gegen client/src/editor/types/map.ts vergleichen; jedes vorhandene Feld erhält Ziel und Migrationsregel.
- **Abhängigkeit:** TC-016; Phasenvoraussetzung G0.
- **Quellen:** AQ-EDITOR, AQ-RENDER, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-018 — Schritt 18 — Identitäten trennen

- **Ziel/Abnahme:** world_id live/shadow, map_id, slot_id, district_id und asset_type haben getrennte Bedeutungen.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/nio_world_api_spec.yaml` (vorhanden).
- **Prüfung:** Beispiele zwei Welten mit gleicher Entity-ID und zwei Gebäude gleichen Assettyps auf Mehrdeutigkeit prüfen.
- **Abhängigkeit:** TC-017; Phasenvoraussetzung G0.
- **Quellen:** AQ-EDITOR, AQ-RENDER, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-019 — Schritt 19 — Kartenrevision und Konflikt festlegen

- **Ziel/Abnahme:** Save trägt erwartete Revision; konkurrierendes Save erzeugt sichtbaren Konflikt statt stillen Überschreibens.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/nio_world_api_spec.yaml` (vorhanden).
- **Prüfung:** Zwei Saves auf Revision n durchspielen; genau eines erzeugt n+1, das zweite Konflikt.
- **Abhängigkeit:** TC-018; Phasenvoraussetzung G0.
- **Quellen:** AQ-EDITOR, AQ-RENDER, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-020 — Schritt 20 — Slot- und Aktivierungsvertrag festlegen

- **Ziel/Abnahme:** Fünf bestehende Kartenslots je Welt und aktiver Slot sind spezifiziert; map_id ist keine neue Ausführungswelt.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/nio_world_api_spec.yaml` (vorhanden).
- **Prüfung:** Slot1 in live und shadow mit verschiedenen Karten darstellen; unabhängige Aktivierung nachvollziehen.
- **Abhängigkeit:** TC-019; Phasenvoraussetzung G0.
- **Quellen:** AQ-EDITOR, AQ-RENDER, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-021 — Schritt 21 — Districtvertrag erweitern

- **Ziel/Abnahme:** Dynamische Instanz-ID, Typ, Assetreferenz und logischer Slot sind definiert; feste acht IDs sind keine Obergrenze.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/nio_world_api_spec.yaml` (vorhanden).
- **Prüfung:** Zwei forge-Instanzen und ein unbekannter Typ gegen Zulassungsregeln prüfen.
- **Abhängigkeit:** TC-020; Phasenvoraussetzung G0.
- **Quellen:** AQ-EDITOR, AQ-RENDER, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-022 — Schritt 22 — NPC- und Workersemantik trennen

- **Ziel/Abnahme:** Dekorative NPCs besitzen Einheit, Farbe, Maßstab und Wanderbereich; Worker werden ausschließlich aus NIO-State dargestellt.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/nio_world_api_spec.yaml` (vorhanden).
- **Prüfung:** NPC create darf keinen Task-/Worker-Aufruf implizieren; Agent-Upsert hat eine echte NIO-Identität.
- **Abhängigkeit:** TC-021; Phasenvoraussetzung G0.
- **Quellen:** AQ-EDITOR, AQ-RENDER, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-023 — Schritt 23 — Assetmanifest-Vertrag festlegen

- **Ziel/Abnahme:** Lokale Asset-ID, Frame-/Animationsdaten und Validierung erlaubter Referenzen sind beschrieben.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/nio_world_api_spec.yaml` (vorhanden).
- **Prüfung:** Vorhandenes Agent-Quest-Manifest feldweise abgleichen; externe URL und Traversal als ungültig spezifizieren.
- **Abhängigkeit:** TC-022; Phasenvoraussetzung G0.
- **Quellen:** AQ-EDITOR, AQ-RENDER, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-024 — Schritt 24 — Map-Commands definieren

- **Ziel/Abnahme:** Map lesen, speichern, Slotliste und Aktivierung haben world_id, Fehlercodes und Authpflicht.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/nio_world_api_spec.yaml` (vorhanden).
- **Prüfung:** Für jeden Command fehlende Welt, fehlende Berechtigung und ungültige Revision dokumentieren.
- **Abhängigkeit:** TC-023; Phasenvoraussetzung G0.
- **Quellen:** AQ-EDITOR, AQ-RENDER, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-025 — Schritt 25 — Template-, Default- und Reset-Verträge festlegen

- **Ziel/Abnahme:** Vorhandenes Template-Laden, Default-Laden/Gebäude-Reset und Slot-Reset sind weltgebunden definiert; kein erfundener Template-Save.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/nio_world_api_spec.yaml` (vorhanden).
- **Prüfung:** Agent-Quest routes.ts und EditorScene.loadTemplate/resetBuildings abgleichen; Dirty-Schutz, Revision und aktive Karte bei Reset spezifizieren.
- **Abhängigkeit:** TC-024; Phasenvoraussetzung G0.
- **Quellen:** AQ-EDITOR, AQ-RENDER, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-026 — Schritt 26 — Event-Epoch und Cursor definieren

- **Ziel/Abnahme:** Cursor ist je Welt getrennt und enthält Neustart-Epoch; Snapshot und Delta haben eindeutige Reihenfolge.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/nio_world_api_spec.yaml` (vorhanden).
- **Prüfung:** Live seq100 und Shadow seq2 sowie Neustart auf neue Epoch durchspielen; keine gültigen Events wegfiltern.
- **Abhängigkeit:** TC-025; Phasenvoraussetzung G0.
- **Quellen:** AQ-EDITOR, AQ-RENDER, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-027 — Schritt 27 — Offline- und Stale-Vertrag präzisieren

- **Ziel/Abnahme:** Disconnected zeigt nur Orb plus Status und deaktivierte Commands; keine erfundenen Agents/Districts.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/nio_world_api_spec.yaml` (vorhanden).
- **Prüfung:** Kaltstart ohne Backend und Verbindungsabbruch nach gültigem Snapshot getrennt als Zustandsfolge beschreiben.
- **Abhängigkeit:** TC-026; Phasenvoraussetzung G0.
- **Quellen:** AQ-EDITOR, AQ-RENDER, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-028 — Schritt 28 — Gate- und Promotionbelege definieren

- **Ziel/Abnahme:** Server-Ticket bindet Welt, Repo, Branch, Basis- und Ziel-HEAD sowie Diff; Erfolg benötigt Merge-Receipt.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/nio_world_api_spec.yaml` (vorhanden).
- **Prüfung:** Clientboolean ohne gespeichertes Ticket muss scheitern; geänderter HEAD entwertet Freigabe.
- **Abhängigkeit:** TC-027; Phasenvoraussetzung G0.
- **Quellen:** AQ-EDITOR, AQ-RENDER, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-029 — Schritt 29 — Ablehnung und Parken definieren

- **Ziel/Abnahme:** Reject hält Branch und Worktree mit Begründung; Cleanup ist eigener späterer Vorgang.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/nio_world_api_spec.yaml` (vorhanden).
- **Prüfung:** NB-NOIR Löschbehauptung gegen D5 auflösen; Ablehnung darf keinen Löschauftrag erzeugen.
- **Abhängigkeit:** TC-028; Phasenvoraussetzung G0.
- **Quellen:** AQ-EDITOR, AQ-RENDER, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-030 — Schritt 30 — Accessibility-Abläufe spezifizieren

- **Ziel/Abnahme:** Stadtwahl, Objektplatzierung, Speichern und Gateentscheid sind vollständig per Tastatur und DOM verfügbar.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_ACCESSIBILITY.md` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Für vier Abläufe Fokusfolge, Beschriftung, Fehlerzustand und Screenreader-Rückmeldung auflisten.
- **Abhängigkeit:** TC-029; Phasenvoraussetzung G0.
- **Quellen:** AQ-EDITOR, AQ-RENDER, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-031 — Schritt 31 — Wiederverwendungsgrenze dokumentieren

- **Ziel/Abnahme:** VillageScene und Editor bleiben; nur Twin-City-Datenquellen/Persistenz werden ersetzt; Agent-Quest-Dienst bleibt.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_ARCHITECTURE_BLUEPRINT.md` (vorhanden).
- **Prüfung:** KEEP/ADAPT/REPLACE gegen konkrete Dateien prüfen; kein pauschales editor-Verzeichnis-DELETE.
- **Abhängigkeit:** TC-030; Phasenvoraussetzung G0.
- **Quellen:** AQ-EDITOR, AQ-RENDER, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-032 — Schritt 32 — Vertragsfixtures vollständig erfassen

- **Ziel/Abnahme:** Referenzkarte und Negativfälle bilden jedes Vertragsfeld ab; noch kein Nachweis eines implementierten Python-Validators.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_CONTRACT_FIXTURES.json` (geplant; vor Ausführung Eigentümerpfad bestätigen).
- **Prüfung:** Feld-für-Feld-Abgleich gegen MapConfig und API-Spezifikation; Fixtures versionieren; Implementierungsparität wird erst nach dem Validator geprüft.
- **Abhängigkeit:** TC-031; Phasenvoraussetzung G0.
- **Quellen:** AQ-EDITOR, AQ-RENDER, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-033 — Schritt 33 — Gate G1 Vertragsabnahme

- **Ziel/Abnahme:** Alle bestehenden Editorfelder und neuen Weltgrenzen sind überprüfbar spezifiziert; keine unaufgelöste Identitätskollision.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_CONTRACT_ACCEPTANCE.md` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Feldmapping und Negativfallmatrix abzeichnen; fehlende Definition blockiert Persistenzimplementierung.
- **Abhängigkeit:** TC-032; Phasenvoraussetzung G0.
- **Quellen:** AQ-EDITOR, AQ-RENDER, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

## P2 — Persistenz, Ereignisse und Isolation

TC-034–TC-049; Abschlussgate **G2**.

### TC-034 — Schritt 34 — Redis-Namespace je Welt ergänzen

- **Ziel/Abnahme:** Bestätigte Karten und Districts liegen unter getrennten live/shadow-Schlüsseln; vorhandener Redis-Zugang wird genutzt.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/state.py` (vorhanden).
- **Prüfung:** Gleiche map_id in beiden Welten schreiben/lesen in isoliertem Testnamespace; Inhalte bleiben getrennt.
- **Abhängigkeit:** TC-033; Phasenvoraussetzung G1.
- **Quellen:** WB-PERSIST, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-035 — Schritt 35 — Map-Lesen an Persistenz anbinden

- **Ziel/Abnahme:** Lesen liefert bestätigte Karte und Revision aus autoritativer Speicherung statt RAM als einziger Quelle.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/state.py` (vorhanden).
- **Prüfung:** Neue Store-Instanz liest identische gespeicherte Daten; fehlende Karte ergibt definierten Fehler.
- **Abhängigkeit:** TC-034; Phasenvoraussetzung G1.
- **Quellen:** WB-PERSIST, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-036 — Schritt 36 — Map-Save atomar implementieren

- **Ziel/Abnahme:** Lua-CAS prüft expected_revision und schreibt Karte plus neue Revision atomar.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/state.py` (vorhanden).
- **Prüfung:** Zwei konkurrierende Writer simulieren; genau ein Erfolg und kein teilweiser Datensatz.
- **Abhängigkeit:** TC-035; Phasenvoraussetzung G1.
- **Quellen:** WB-PERSIST, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-037 — Schritt 37 — Save-Konflikte testen

- **Ziel/Abnahme:** Neue Regression prüft stale Revision, fehlende Revision und Welttrennung.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/tests/test_map_state.py` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Geplante Testdatei erstellen; python3 -m pytest world_bridge/tests/test_map_state.py -q.
- **Abhängigkeit:** TC-036; Phasenvoraussetzung G1.
- **Quellen:** WB-PERSIST, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-038 — Schritt 38 — Slotliste persistent anbinden

- **Ziel/Abnahme:** Fünf Slots pro Welt behalten stabile Identitäten und Kartenreferenzen.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/state.py` (vorhanden).
- **Prüfung:** Leere, belegte und ungültige Slots mit Store-Neuinstanz prüfen.
- **Abhängigkeit:** TC-037; Phasenvoraussetzung G1.
- **Quellen:** WB-PERSIST, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-039 — Schritt 39 — Slotaktivierung atomar machen

- **Ziel/Abnahme:** Aktive Karte wird erst nach Existenz-/Weltprüfung umgestellt und bleibt nach Neustart erhalten.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/state.py` (vorhanden).
- **Prüfung:** Aktiviere shadow Slot2; live aktiv bleibt unverändert; fehlender Slot scheitert ohne Mutation.
- **Abhängigkeit:** TC-038; Phasenvoraussetzung G1.
- **Quellen:** WB-PERSIST, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-040 — Schritt 40 — District-Registrierung persistieren

- **Ziel/Abnahme:** Registrierte funktionale Districts überleben neue Verbindungen und Store-Neustarts.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/state.py` (vorhanden).
- **Prüfung:** District zweimal idempotent registrieren; neu lesen; genau eine Instanz vorhanden.
- **Abhängigkeit:** TC-039; Phasenvoraussetzung G1.
- **Quellen:** WB-PERSIST, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-041 — Schritt 41 — District-Retire konsistent machen

- **Ziel/Abnahme:** Retire entfernt nur gewählte Welt/ID und hinterlässt keinen aktiven Agent-Zielverweis.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/state.py` (vorhanden).
- **Prüfung:** Gleiche District-ID in beiden Welten; nur eine entfernen und verwaiste Ziele erkennen.
- **Abhängigkeit:** TC-040; Phasenvoraussetzung G1.
- **Quellen:** WB-PERSIST, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-042 — Schritt 42 — Snapshot aus autoritativen Quellen zusammensetzen

- **Ziel/Abnahme:** Snapshot kombiniert NIO-Agenten mit persistierten Layouts; statische Districtliste überschreibt keine bestätigten Änderungen.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/adapters.py` (vorhanden).
- **Prüfung:** Manuellen District plus NIO-Agent einlesen; zweiter Client erhält denselben bestätigten District.
- **Abhängigkeit:** TC-041; Phasenvoraussetzung G1.
- **Quellen:** WB-PERSIST, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-043 — Schritt 43 — Snapshot-Subscribe-Race schließen

- **Ziel/Abnahme:** Zwischen Snapshot und Subscription geht kein Event verloren; Sequenzgrenze ist explizit.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/bridge.py` (vorhanden).
- **Prüfung:** Event genau am Snapshotübergang einspeisen; Client erhält Endzustand ohne Lücke oder doppelte Mutation.
- **Abhängigkeit:** TC-042; Phasenvoraussetzung G1.
- **Quellen:** WB-PERSIST, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-044 — Schritt 44 — Cursor je Welt auswerten

- **Ziel/Abnahme:** Resume filtert live und shadow unabhängig; ein hoher Live-Cursor verwirft keine Shadow-Events.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/bridge.py` (vorhanden).
- **Prüfung:** Cursor live100/shadow2 und gemischte Events als Regression ausführen.
- **Abhängigkeit:** TC-043; Phasenvoraussetzung G1.
- **Quellen:** WB-PERSIST, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-045 — Schritt 45 — Epochwechsel resynchronisieren

- **Ziel/Abnahme:** Neustart invalidiert alte Epoch und erzwingt vollständigen Snapshot.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/bridge.py` (vorhanden).
- **Prüfung:** Client mit vorheriger Epoch verbinden; Snapshot muss auch bei kleiner neuer seq eintreffen.
- **Abhängigkeit:** TC-044; Phasenvoraussetzung G1.
- **Quellen:** WB-PERSIST, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-046 — Schritt 46 — Subscriber-Queues begrenzen

- **Ziel/Abnahme:** Langsamer Client verursacht begrenzten Speicher; definierter Resync/Disconnect statt unbegrenztem Wachstum.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/bridge.py` (vorhanden).
- **Prüfung:** Clientkonsum stoppen, Limit erreichen, Speicher-/Queuegrenze und Resyncsignal prüfen.
- **Abhängigkeit:** TC-045; Phasenvoraussetzung G1.
- **Quellen:** WB-PERSIST, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-047 — Schritt 47 — Publisher-Lifecycle schließen

- **Ziel/Abnahme:** Publisher-Ausnahme wird sichtbar; Shutdown beendet Tasks; Neuverbindung startet keinen doppelten Publisher.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/bridge.py` (vorhanden).
- **Prüfung:** Fake-Adapterfehler und Shutdown auslösen; keine verwaisten asyncio Tasks nach Testende.
- **Abhängigkeit:** TC-046; Phasenvoraussetzung G1.
- **Quellen:** WB-PERSIST, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-048 — Schritt 48 — Batching und Änderungsabfrage prüfen

- **Ziel/Abnahme:** Deltas werden höchstens 15Hz versandt; unveränderte Vollsnapshots werden nicht 15mal/s abgefragt.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/batch.py` (vorhanden); `world_bridge/adapters.py` (vorhanden).
- **Prüfung:** Fake-Uhr und Zähler prüfen; Gatepriorität bleibt erhalten, identischer State erzeugt keinen Eventsturm.
- **Abhängigkeit:** TC-047; Phasenvoraussetzung G1.
- **Quellen:** WB-PERSIST, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

### TC-049 — Schritt 49 — Gate G2 Persistenz und Stream abnehmen

- **Ziel/Abnahme:** Reconnect, Epochwechsel, Konkurrenz, zwei Clients und Welttrennung bestehen; Redis-Liveprobe nutzt eigenes Namespace.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/tests/test_bridge.py` (vorhanden); `world_bridge/tests/test_batch.py` (vorhanden); `world_bridge/tests/test_map_state.py` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Gezielte Tests ausführen; optionalen Redis-Test nur mit vorhandener isolierter Umgebung starten, Skip ausdrücklich offen lassen.
- **Abhängigkeit:** TC-048; Phasenvoraussetzung G1.
- **Quellen:** WB-PERSIST, AQ-ISOLATION, SRC28. **Status:** blocked / nicht ausgeführt.

## P3 — Befehle, Authentifizierung und echte Gates

TC-050–TC-070; Abschlussgate **G3**.

### TC-050 — Schritt 50 — Unbelegte Promotion sperren

- **Ziel/Abnahme:** Bisheriger Boolean-Erfolgspfad meldet ohne echte Merge-Ausführung keinen promoted-Erfolg.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/router.py` (vorhanden).
- **Prüfung:** Request mit beiden Clientbooleans senden; bis vollständigem Backendpfad definierte Sperre erwarten.
- **Abhängigkeit:** TC-049; Phasenvoraussetzung G2.
- **Quellen:** WB-PROMOTE, WB-PERSIST, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-051 — Schritt 51 — Map-Read-Route ergänzen

- **Ziel/Abnahme:** Authentifiziertes Lesen akzeptiert nur gültige Welt und Karten-/Slot-ID.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/bridge.py` (vorhanden).
- **Prüfung:** Gültige und fehlende Welt, fremder Slot und fehlende Auth gegen Testclient prüfen.
- **Abhängigkeit:** TC-050; Phasenvoraussetzung G2.
- **Quellen:** WB-PROMOTE, WB-PERSIST, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-052 — Schritt 52 — Map-Validierung übernehmen

- **Ziel/Abnahme:** Agent-Quest-Felder bleiben erlaubt; Typen, Maße, IDs und Assetreferenzen werden begrenzt validiert.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/spec.py` (vorhanden).
- **Prüfung:** Verlustfreie Referenzkarte akzeptieren; doppelte IDs, negative Maße und externe Assetpfade ablehnen.
- **Abhängigkeit:** TC-051; Phasenvoraussetzung G2.
- **Quellen:** WB-PROMOTE, WB-PERSIST, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-053 — Schritt 53 — Implementierten Kartenvalidator regressionsprüfen

- **Ziel/Abnahme:** Python-Validator akzeptiert verlustfreie Referenzkarte und weist alle spezifizierten Negativfälle ab.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/tests/test_contract.py` (vorhanden); `world_bridge/tests/test_spec.py` (vorhanden).
- **Prüfung:** python3 -m pytest world_bridge/tests/test_contract.py world_bridge/tests/test_spec.py -q; Fixtures des P1-Gates verwenden.
- **Abhängigkeit:** TC-052; Phasenvoraussetzung G2.
- **Quellen:** WB-PROMOTE, WB-PERSIST, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-054 — Schritt 54 — Map-Save-Command ergänzen

- **Ziel/Abnahme:** Save validiert vollständige Karte und expected_revision vor atomarem Store-Aufruf.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/router.py` (vorhanden).
- **Prüfung:** Ungültige Karte darf keinen Schreibaufruf erzeugen; gültige Antwort enthält neue Revision.
- **Abhängigkeit:** TC-053; Phasenvoraussetzung G2.
- **Quellen:** WB-PROMOTE, WB-PERSIST, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-055 — Schritt 55 — Slotliste und Aktivierung routen

- **Ziel/Abnahme:** Slots und aktive Karte werden ausschließlich im gewählten Weltadapter geändert.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/router.py` (vorhanden).
- **Prüfung:** Shadow-Aktivierung mit Live-Slotreferenz negativ prüfen; Nebenwirkungen im anderen Adapter müssen null sein.
- **Abhängigkeit:** TC-054; Phasenvoraussetzung G2.
- **Quellen:** WB-PROMOTE, WB-PERSIST, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-056 — Schritt 56 — Template und Default weltgebunden lesen

- **Ziel/Abnahme:** Template/Default werden serverautoritativ aus der angefragten Welt geliefert; kein Cross-World-Fallback.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/router.py` (vorhanden).
- **Prüfung:** Zwei Welten mit verschiedenen Templates sowie fehlendes Template prüfen; Lesen erzeugt keine Jobs.
- **Abhängigkeit:** TC-055; Phasenvoraussetzung G2.
- **Quellen:** WB-PROMOTE, WB-PERSIST, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-057 — Schritt 57 — Slot-Reset revisionsgebunden implementieren

- **Ziel/Abnahme:** Slot-Reset wird atomar mit Revision geprüft; aktive Karte bleibt gemäß Vertrag konsistent; verlorene Antwort führt nicht zu doppelter Mutation.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/router.py` (vorhanden); `world_bridge/state.py` (vorhanden).
- **Prüfung:** Konkurrierendes Save/Reset, falsche Welt und doppelte Command-ID in isoliertem Store prüfen.
- **Abhängigkeit:** TC-056; Phasenvoraussetzung G2.
- **Quellen:** WB-PROMOTE, WB-PERSIST, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-058 — Schritt 58 — Bestehende MapConfig verlustfrei importieren

- **Ziel/Abnahme:** Schema-Version und Weltziel werden explizit gesetzt; Terrain, Gebäude, NPCs, Pfade und Metadaten bleiben erhalten; Original bleibt unverändert.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/map_migration.py` (geplant; vor Ausführung Eigentümerpfad bestätigen).
- **Prüfung:** Kopierte Altkarte importieren, alle Felder vergleichen; unbekannte Assets/NPC-Typen melden und Import anhalten statt still verwerfen.
- **Abhängigkeit:** TC-057; Phasenvoraussetzung G2.
- **Quellen:** WB-PROMOTE, WB-PERSIST, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-059 — Schritt 59 — Import-Wiederholung und Recovery prüfen

- **Ziel/Abnahme:** Erneuter identischer Import ist idempotent; Abbruch erzeugt keine teilbestätigte Karte.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/tests/test_map_migration.py` (geplant; vor Ausführung Eigentümerpfad bestätigen).
- **Prüfung:** Vor/nach Commit abbrechen, erneut importieren und Quellhash/Revision/Inhalt vergleichen; nur temporäre Daten.
- **Abhängigkeit:** TC-058; Phasenvoraussetzung G2.
- **Quellen:** WB-PROMOTE, WB-PERSIST, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-060 — Schritt 60 — District-Commands verbinden

- **Ziel/Abnahme:** Register/Retire nutzen denselben validierten persistenten Pfad wie REST und liefern tatsächliche Revision.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/mcp_tools.py` (vorhanden).
- **Prüfung:** MCP-Registrierung danach via REST lesen; doppelte Registrierung und fremde Welt prüfen.
- **Abhängigkeit:** TC-059; Phasenvoraussetzung G2.
- **Quellen:** WB-PROMOTE, WB-PERSIST, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-061 — Schritt 61 — NPC-Änderungen routen

- **Ziel/Abnahme:** NPC-Änderung ist Kartenänderung mit Revision; kein Worker-/Taskcreate wird ausgelöst.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/router.py` (vorhanden).
- **Prüfung:** Fake-Kanbanclient zählt Aufrufe; NPC erstellen/ändern/entfernen erzeugt ausschließlich Map-State.
- **Abhängigkeit:** TC-060; Phasenvoraussetzung G2.
- **Quellen:** WB-PROMOTE, WB-PERSIST, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-062 — Schritt 62 — Browser-Authvertrag umsetzen

- **Ziel/Abnahme:** Browser kann authentifizieren ohne Langzeittoken in URL, Bundle oder localStorage; kurzlebige Sitzung ist serverseitig geprüft.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/bridge.py` (vorhanden).
- **Prüfung:** Bundle/URL/Storage auf Geheimnisse prüfen; Ablauf, fehlende Sitzung und fremder Origin werden abgelehnt.
- **Abhängigkeit:** TC-061; Phasenvoraussetzung G2.
- **Quellen:** WB-PROMOTE, WB-PERSIST, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-063 — Schritt 63 — Command-Replay begrenzen

- **Ziel/Abnahme:** Mutative Commands besitzen idempotente Request-ID innerhalb Welt/Actor; Wiederholung dupliziert keine Taskanlage.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/router.py` (vorhanden).
- **Prüfung:** Gleiche ID zweimal senden; identisches Receipt und ein Backendaufruf; abweichender Payload unter gleicher ID ablehnen.
- **Abhängigkeit:** TC-062; Phasenvoraussetzung G2.
- **Quellen:** WB-PROMOTE, WB-PERSIST, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-064 — Schritt 64 — Gate-Weltbindung serverseitig prüfen

- **Ziel/Abnahme:** Ticketzugehörigkeit wird aus autoritativer Quelle geprüft; Client-Gate-ID allein verleiht keine Berechtigung.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/router.py` (vorhanden).
- **Prüfung:** Cross-world Gate, unbekanntes Gate und bereits erledigtes Ticket negativ testen.
- **Abhängigkeit:** TC-063; Phasenvoraussetzung G2.
- **Quellen:** WB-PROMOTE, WB-PERSIST, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-065 — Schritt 65 — Gate an geprüften Commit binden

- **Ziel/Abnahme:** Freigabe referenziert exakten Repo-/Branch-/HEAD-/Diffstand und verfällt bei Drift.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/router.py` (vorhanden).
- **Prüfung:** Nach Freigabe Head ändern; Merge bleibt blockiert und erneute Prüfung wird gefordert.
- **Abhängigkeit:** TC-064; Phasenvoraussetzung G2.
- **Quellen:** WB-PROMOTE, WB-PERSIST, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-066 — Schritt 66 — Promotion an Orchestrator übergeben

- **Ziel/Abnahme:** Nur serverbestätigtes Gate startet vorhandenen Orchestrator-Mergepfad; Bridge implementiert keinen zweiten Git-Merger.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/router.py` (vorhanden).
- **Prüfung:** Fake-Orchestratoraufruf enthält geprüfte Referenzen; Ablehnung erzeugt keinen Mergeaufruf.
- **Abhängigkeit:** TC-065; Phasenvoraussetzung G2.
- **Quellen:** WB-PROMOTE, WB-PERSIST, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-067 — Schritt 67 — Merge-Receipt auswerten

- **Ziel/Abnahme:** Erfolg erst nach verifiziertem Merge-Receipt mit resultierendem HEAD; Timeout bleibt pending/failed.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/router.py` (vorhanden).
- **Prüfung:** Pending, Fehler und Erfolg getrennt testen; bloße HTTP-Annahme darf promoted nicht setzen.
- **Abhängigkeit:** TC-066; Phasenvoraussetzung G2.
- **Quellen:** WB-PROMOTE, WB-PERSIST, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-068 — Schritt 68 — Reject parkt Artefakte

- **Ziel/Abnahme:** Ablehnung dokumentiert Gründe und erhält Worktree/Branch; kein force-remove im Ablehnungspfad.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/router.py` (vorhanden).
- **Prüfung:** Temporäres Testrepo ablehnen; Branch und Commit bleiben lesbar, Receipt beschreibt parked.
- **Abhängigkeit:** TC-067; Phasenvoraussetzung G2.
- **Quellen:** WB-PROMOTE, WB-PERSIST, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-069 — Schritt 69 — Auth- und Gate-Negativtests ergänzen

- **Ziel/Abnahme:** Fehlende Auth, gefälschte Booleans, stale HEAD, Replay und Cross-world sind regressionsgesichert.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/tests/test_router.py` (vorhanden); `world_bridge/tests/test_bridge.py` (vorhanden).
- **Prüfung:** python3 -m pytest world_bridge/tests/test_router.py world_bridge/tests/test_bridge.py -q.
- **Abhängigkeit:** TC-068; Phasenvoraussetzung G2.
- **Quellen:** WB-PROMOTE, WB-PERSIST, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-070 — Schritt 70 — Gate G3 Commands und Promotion abnehmen

- **Ziel/Abnahme:** Temporäre Repos beweisen echte Mergewirkung, Reject-Parken und fehlende Nebenwirkungen bei ungültigen Freigaben.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/e2e/test_gates_e2e.py` (vorhanden).
- **Prüfung:** E2E nur in eigenen Testrepos ausführen; keine echten Live-Gates bedienen; Snapshot der Refs vor/nach vergleichen.
- **Abhängigkeit:** TC-069; Phasenvoraussetzung G2.
- **Quellen:** WB-PROMOTE, WB-PERSIST, NB-NOIR. **Status:** blocked / nicht ausgeführt.

## P4 — VillageScene und zwei getrennte Ansichten

TC-071–TC-086; Abschlussgate **G4**.

### TC-071 — Schritt 71 — Twin-City-Einstieg an VillageScene binden

- **Ziel/Abnahme:** Twin-City verwendet bestehenden Scene- und Spritekern; kein Graphics-Quadratersatz.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/game/PhaserGame.tsx` (vorhanden).
- **Prüfung:** Mountpfad und geladene Scene prüfen; Terrain, Gebäudesprites und HeroSprite im Testaufbau sichtbar.
- **Abhängigkeit:** TC-070; Phasenvoraussetzung G3.
- **Quellen:** AQ-RENDER, AQ-ISOLATION, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-072 — Schritt 72 — WorldBridge-Transport prüfen

- **Ziel/Abnahme:** Vorhandenen Transport nur bei belegten Lücken ändern; Events werden vor Sceneübergabe validiert.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/game/city/ws.ts` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Ungültiges Envelope und falsche Welt verwerfen; gültiges Snapshot mit dokumentierter Revision annehmen.
- **Abhängigkeit:** TC-071; Phasenvoraussetzung G3.
- **Quellen:** AQ-RENDER, AQ-ISOLATION, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-073 — Schritt 73 — EventBridge instanziieren

- **Ziel/Abnahme:** Jede Welt besitzt eigene Listener und Sticky-Werte ohne gegenseitiges Überschreiben.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/game/EventBridge.ts` (vorhanden).
- **Prüfung:** Zwei Bridges mit gleicher Agent-ID versorgen; Listener der anderen Instanz bleibt unberührt.
- **Abhängigkeit:** TC-072; Phasenvoraussetzung G3.
- **Quellen:** AQ-RENDER, AQ-ISOLATION, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-074 — Schritt 74 — Scene-Events an Welt binden

- **Ziel/Abnahme:** Scene erhält Weltkontext und abonniert nur dessen Bridge.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/game/scenes/VillageScene.ts` (vorhanden).
- **Prüfung:** Shadow-Agentupdate beobachten; Live-Spritebestand und Auswahl ändern sich nicht.
- **Abhängigkeit:** TC-073; Phasenvoraussetzung G3.
- **Quellen:** AQ-RENDER, AQ-ISOLATION, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-075 — Schritt 75 — Straßengraph instanziieren

- **Ziel/Abnahme:** Waypoints, Kanten und Adjazenz gehören zu einer Weltinstanz statt Modulglobalen.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/game/data/road-network.ts` (vorhanden).
- **Prüfung:** Zwei verschiedene Pfadkarten nacheinander laden; erste Graphantwort bleibt identisch.
- **Abhängigkeit:** TC-074; Phasenvoraussetzung G3.
- **Quellen:** AQ-RENDER, AQ-ISOLATION, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-076 — Schritt 76 — Nicht erreichbare Wege kennzeichnen

- **Ziel/Abnahme:** BFS liefert für getrennte Komponenten keinen direkten Weg durch Hindernisse.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/game/data/road-network.ts` (vorhanden).
- **Prüfung:** Getrennte Pfadkomponenten testen; definierter unreachable-Zustand statt Start-Ziel-Gerade.
- **Abhängigkeit:** TC-075; Phasenvoraussetzung G3.
- **Quellen:** AQ-RENDER, AQ-ISOLATION, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-077 — Schritt 77 — BFS-Isolation regressionsprüfen

- **Ziel/Abnahme:** Bestehende BFS bleibt; Tests decken isolierte Graphen und unerreichbare Ziele ab.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/game/data/road-network.test.ts` (vorhanden).
- **Prüfung:** Vorhandenen Testbefehl aus package.json verwenden; jede neue Assertion muss den früheren Fehler erkennen.
- **Abhängigkeit:** TC-076; Phasenvoraussetzung G3.
- **Quellen:** AQ-RENDER, AQ-ISOLATION, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-078 — Schritt 78 — Dynamische Buildings erzeugen

- **Ziel/Abnahme:** District-Upsert erzeugt Building-Sprite nach Instanz-ID und Assettyp, nicht nur feste BUILDING_DEFS.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/game/scenes/VillageScene.ts` (vorhanden).
- **Prüfung:** Zwei forge-Districts mit verschiedenen IDs darstellen; beide besitzen eigene Auswahl und Position.
- **Abhängigkeit:** TC-077; Phasenvoraussetzung G3.
- **Quellen:** AQ-RENDER, AQ-ISOLATION, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-079 — Schritt 79 — District-Remove rendern

- **Ziel/Abnahme:** Entferntes Gebäude verliert Sprite, Hitarea und Zielzuordnung ohne andere Instanzen zu zerstören.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/game/scenes/VillageScene.ts` (vorhanden).
- **Prüfung:** Einen von zwei gleichen Gebäudetypen entfernen; verbleibendes Objekt bleibt bedienbar.
- **Abhängigkeit:** TC-078; Phasenvoraussetzung G3.
- **Quellen:** AQ-RENDER, AQ-ISOLATION, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-080 — Schritt 80 — NIO-Agenten auf Heroes abbilden

- **Ziel/Abnahme:** Worker-ID ist stabile Hero-ID; Taskwechsel bewegt bestehenden Hero statt ihn zu duplizieren.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/game/scenes/VillageScene.ts` (vorhanden).
- **Prüfung:** Idle→busy→idle und Klassenwechsel mit gleicher ID prüfen; Entityzahl bleibt stabil.
- **Abhängigkeit:** TC-079; Phasenvoraussetzung G3.
- **Quellen:** AQ-RENDER, AQ-ISOLATION, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-081 — Schritt 81 — Dekorative NPCs aus Karte rendern

- **Ziel/Abnahme:** Gespeicherte NPC-Attribute werden verwendet; NPC zählt nicht als aktiver Worker.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/game/entities/NpcSprite.ts` (vorhanden).
- **Prüfung:** Karte mit dekorativem NPC laden; Workerzahl bleibt unverändert und Darstellung stimmt mit Attributen überein.
- **Abhängigkeit:** TC-080; Phasenvoraussetzung G3.
- **Quellen:** AQ-RENDER, AQ-ISOLATION, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-082 — Schritt 82 — Orb in bestehende Stadt integrieren

- **Ziel/Abnahme:** Orbzustände stammen aus Events; vorhandene Shaderquelle wird gezielt wiederverwendet.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/game/city/orb.ts` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Idle/listening/dispatching/alert durch kontrollierte Testevents prüfen; keine Produkt-Simulationsdaten einschleusen.
- **Abhängigkeit:** TC-081; Phasenvoraussetzung G3.
- **Quellen:** AQ-RENDER, AQ-ISOLATION, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-083 — Schritt 83 — Wetter und Twin-Kameras isolieren

- **Ziel/Abnahme:** Live Sonne und Shadow Regen bleiben getrennt; optionale Kamerasynchronisierung bewegt keine Weltobjekte.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/game/scenes/VillageScene.ts` (vorhanden); `client/src/game/PhaserGame.tsx` (vorhanden).
- **Prüfung:** Ansichten getrennt zoomen, dann Sync aktivieren; nur Kamerawerte koppeln und Weltstatus sichtbar halten.
- **Abhängigkeit:** TC-082; Phasenvoraussetzung G3.
- **Quellen:** AQ-RENDER, AQ-ISOLATION, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-084 — Schritt 84 — Offline-Fallback ersetzen

- **Ziel/Abnahme:** Twin-City ohne bestätigten Backendstate zeigt Orb und Disconnectstatus ohne prozedurale Fake-Stadt.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/game/scenes/VillageScene.ts` (vorhanden).
- **Prüfung:** Backend vor Start und nach Verbindung unterbrechen; keine erfundenen Districts oder Agents zurücklassen.
- **Abhängigkeit:** TC-083; Phasenvoraussetzung G3.
- **Quellen:** AQ-RENDER, AQ-ISOLATION, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-085 — Schritt 85 — Scene-Cleanup prüfen

- **Ziel/Abnahme:** Repeated mount/unmount beendet Timer, Listener und Phaserinstanzen; keine Doppelzustellung.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/game/PhaserGame.tsx` (vorhanden); `client/src/game/scenes/VillageScene.ts` (vorhanden).
- **Prüfung:** Zehn Twin-View-Wechsel; Listener-/Canvaszahl stabil, ein Event bewegt genau einen zugehörigen Hero.
- **Abhängigkeit:** TC-084; Phasenvoraussetzung G3.
- **Quellen:** AQ-RENDER, AQ-ISOLATION, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-086 — Schritt 86 — Gate G4 echte Dorfansicht abnehmen

- **Ziel/Abnahme:** Terrain, Häuser, Figuren und Wege entsprechen vorhandener Agent-Quest-Qualität; beide Welten bleiben getrennt.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/game/scenes/VillageScene.ts` (vorhanden).
- **Prüfung:** Browservergleich mit localhost:4445 dokumentieren; Build am exakten Worker-Commit und reale District-/Hero-Events nachweisen.
- **Abhängigkeit:** TC-085; Phasenvoraussetzung G3.
- **Quellen:** AQ-RENDER, AQ-ISOLATION, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

## P5 — Vorhandenen Karteneditor an NIO anbinden

TC-087–TC-104; Abschlussgate **G5**.

### TC-087 — Schritt 87 — Editor-Transport extrahieren

- **Ziel/Abnahme:** Vorhandenes Save/Load wird über kleine Transportgrenze an NIO umgebogen; Werkzeuge bleiben erhalten.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/editor/game/scenes/EditorScene.ts` (vorhanden).
- **Prüfung:** Netzwerkziele für Twin-City prüfen; keine Anfragen an Bun :4444 im Twin-City-Pfad.
- **Abhängigkeit:** TC-086; Phasenvoraussetzung G4.
- **Quellen:** AQ-EDITOR, WB-PERSIST, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-088 — Schritt 88 — Editor-Kontext isolieren

- **Ziel/Abnahme:** Ein expliziter Welt-/Kartenkontext verhindert globale Dirty-/Auswahlzustände zwischen Welten.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/editor/EditorBridge.ts` (vorhanden); `client/src/editor/state/editor-store.ts` (vorhanden).
- **Prüfung:** Editor zwischen live/shadow wechseln; Entwurf und Auswahl bleiben korrekt zugeordnet.
- **Abhängigkeit:** TC-087; Phasenvoraussetzung G4.
- **Quellen:** AQ-EDITOR, WB-PERSIST, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-089 — Schritt 89 — Slotwahl übernehmen

- **Ziel/Abnahme:** Alle fünf Slots werden je Welt angezeigt und geladen; Slotwahl ist kein world_id-Wechsel.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/editor/game/scenes/EditorScene.ts` (vorhanden).
- **Prüfung:** Slot2 live und Slot2 shadow mit verschiedenen Inhalten öffnen; Identitäten und Titel prüfen.
- **Abhängigkeit:** TC-088; Phasenvoraussetzung G4.
- **Quellen:** AQ-EDITOR, WB-PERSIST, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-090 — Schritt 90 — Aktive Karte übernehmen

- **Ziel/Abnahme:** Set Active wartet auf Serverbestätigung; fehlerhafte Antwort ändert den Aktivmarker nicht.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/editor/game/scenes/EditorScene.ts` (vorhanden).
- **Prüfung:** Erfolg und Fehlerantwort simulieren; ausschließlich bestätigte Welt bekommt neuen Aktivmarker.
- **Abhängigkeit:** TC-089; Phasenvoraussetzung G4.
- **Quellen:** AQ-EDITOR, WB-PERSIST, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-091 — Schritt 91 — Terrain verlustfrei speichern

- **Ziel/Abnahme:** Tiles, Frames, Walkability und Weltgröße überleben Save/Reload.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/editor/game/scenes/EditorScene.ts` (vorhanden).
- **Prüfung:** Referenzkarte mit mehreren Tilesets speichern und Feldvergleich nach Reload durchführen.
- **Abhängigkeit:** TC-090; Phasenvoraussetzung G4.
- **Quellen:** AQ-EDITOR, WB-PERSIST, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-092 — Schritt 92 — Dekorationen verlustfrei speichern

- **Ziel/Abnahme:** IDs, Texturen, Frames, Position, Skalierung und Animation überleben Roundtrip.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/editor/game/scenes/EditorScene.ts` (vorhanden).
- **Prüfung:** Zwei gleiche Assets unterschiedlich transformieren; Reload erhält beide vollständigen Datensätze.
- **Abhängigkeit:** TC-091; Phasenvoraussetzung G4.
- **Quellen:** AQ-EDITOR, WB-PERSIST, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-093 — Schritt 93 — Straßen verlustfrei speichern

- **Ziel/Abnahme:** Pfade, Stil und Breite bleiben erhalten; Straßenänderung aktualisiert nur aktuellen Weltgraphen.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/editor/game/scenes/EditorScene.ts` (vorhanden).
- **Prüfung:** Main/trail/plaza-Pfade speichern; Reloadwerte und Hero-Routing der anderen Welt vergleichen.
- **Abhängigkeit:** TC-092; Phasenvoraussetzung G4.
- **Quellen:** AQ-EDITOR, WB-PERSIST, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-094 — Schritt 94 — Dynamische Gebäudeauswahl erweitern

- **Ziel/Abnahme:** Funktionale District-Instanzen sind auswählbar; gleiche Typen behalten unterschiedliche IDs.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/editor/panels/Inspector.tsx` (vorhanden).
- **Prüfung:** Zwei forge-Instanzen im Inspector bearbeiten; nur ausgewählter District ändert sich.
- **Abhängigkeit:** TC-093; Phasenvoraussetzung G4.
- **Quellen:** AQ-EDITOR, WB-PERSIST, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-095 — Schritt 95 — Gebäudeplatzierung anbinden

- **Ziel/Abnahme:** Gebäude-Intent wird servervalidiert; Rendering übernimmt bestätigten logischen Slot, keine lokale Autoritätskopie.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/editor/game/scenes/EditorScene.ts` (vorhanden).
- **Prüfung:** Gültigen und belegten Slot anfordern; abgelehnte Platzierung hinterlässt kein Phantomgebäude.
- **Abhängigkeit:** TC-094; Phasenvoraussetzung G4.
- **Quellen:** AQ-EDITOR, WB-PERSIST, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-096 — Schritt 96 — NPC-Werkzeug erhalten

- **Ziel/Abnahme:** Vorhandene Einheiten, Farben, Skalierung und Wanderbereich bleiben auswählbar und speicherbar.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/editor/game/scenes/EditorScene.ts` (vorhanden).
- **Prüfung:** Warrior und Archer verschiedener Farben erstellen; Reload vergleicht Attribute, Workerzahl unverändert.
- **Abhängigkeit:** TC-095; Phasenvoraussetzung G4.
- **Quellen:** AQ-EDITOR, WB-PERSIST, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-097 — Schritt 97 — NPC-Inspector übernehmen

- **Ziel/Abnahme:** Ändern und Entfernen einzelner NPCs bleibt möglich und revisionsgebunden.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/editor/panels/Inspector.tsx` (vorhanden).
- **Prüfung:** Einen NPC ändern, anderen entfernen, speichern und neu laden; nur beabsichtigte Differenz vorhanden.
- **Abhängigkeit:** TC-096; Phasenvoraussetzung G4.
- **Quellen:** AQ-EDITOR, WB-PERSIST, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-098 — Schritt 98 — Spawn und Hero-Maßstab erhalten

- **Ziel/Abnahme:** Spawnpunkt und Hero-Skalierung werden als Kartenkonfiguration gespeichert.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/editor/game/scenes/EditorScene.ts` (vorhanden).
- **Prüfung:** Spawn/Scale ändern und Reload; keine Änderung an NIO-Workerrechten oder realem Jobzustand.
- **Abhängigkeit:** TC-097; Phasenvoraussetzung G4.
- **Quellen:** AQ-EDITOR, WB-PERSIST, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-099 — Schritt 99 — Save-Konflikt verständlich anzeigen

- **Ziel/Abnahme:** Veraltete Revision zeigt Konflikt und erhält sichtbaren Entwurf bis bewusster Neuentscheidung.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/editor/game/scenes/EditorScene.ts` (vorhanden).
- **Prüfung:** Zwei Editorclients speichern nacheinander; zweiter überschreibt nicht automatisch und kann neu laden.
- **Abhängigkeit:** TC-098; Phasenvoraussetzung G4.
- **Quellen:** AQ-EDITOR, WB-PERSIST, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-100 — Schritt 100 — Ungespeicherte Entwürfe behandeln

- **Ziel/Abnahme:** Welt-/Slotwechsel warnt bei Dirty-Entwurf; Entwurf ist flüchtig und keine persistente zweite Wahrheit.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/editor/state/editor-store.ts` (vorhanden).
- **Prüfung:** Dirty-Wechsel abbrechen und bestätigen; Verhalten sichtbar, kein stiller Datenverlust und keine localStorage-Map.
- **Abhängigkeit:** TC-099; Phasenvoraussetzung G4.
- **Quellen:** AQ-EDITOR, WB-PERSIST, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-101 — Schritt 101 — Template und Default im Editor anbinden

- **Ziel/Abnahme:** Bestehende Lade-/Gebäude-Reset-Aktionen verwenden den Welttransport und schützen ungespeicherte Entwürfe.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/editor/game/scenes/EditorScene.ts` (vorhanden).
- **Prüfung:** Aktionen je Welt ausführen; Dirty-Abbruch bewahrt Entwurf; Laden speichert nicht automatisch und startet keinen Worker.
- **Abhängigkeit:** TC-100; Phasenvoraussetzung G4.
- **Quellen:** AQ-EDITOR, WB-PERSIST, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-102 — Schritt 102 — Slot-Reset mit Konfliktschutz anbinden

- **Ziel/Abnahme:** Expliziter Slot-Reset unterscheidet gespeicherte Karte und lokalen Entwurf; Konflikt/Fehler zeigt keinen falschen Erfolg.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/editor/game/scenes/EditorScene.ts` (vorhanden).
- **Prüfung:** Reset bestätigen/abbrechen, veraltete Revision und Backendausfall testen; andere Welt bleibt unverändert.
- **Abhängigkeit:** TC-101; Phasenvoraussetzung G4.
- **Quellen:** AQ-EDITOR, WB-PERSIST, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-103 — Schritt 103 — Asset-Ladefehler gezielt beheben

- **Ziel/Abnahme:** Beobachtete NPC-Spritesheet-Verarbeitungsfehler erhalten reproduzierbaren Befund und minimale Manifest-/Framekorrektur.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/game/data/asset-loader.ts` (vorhanden).
- **Prüfung:** Betroffene Archer/Pawn-Einträge aus Browserlog reproduzieren; nur belegte Fehler korrigieren, anschließend Palette prüfen.
- **Abhängigkeit:** TC-102; Phasenvoraussetzung G4.
- **Quellen:** AQ-EDITOR, WB-PERSIST, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

### TC-104 — Schritt 104 — Gate G5 Editor-Roundtrip abnehmen

- **Ziel/Abnahme:** Alle MapConfig-Felder, fünf Slots, NPCs und dynamische Districts überstehen Save/Reload und Backend-Neustart.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/editor/game/scenes/EditorScene.ts` (vorhanden).
- **Prüfung:** Vollständige Referenzkarte vor/nach normalisiert vergleichen; Original-Agent-Quest bleibt unverändert betreibbar.
- **Abhängigkeit:** TC-103; Phasenvoraussetzung G4.
- **Quellen:** AQ-EDITOR, WB-PERSIST, SRC28, AUDIO-TWIN. **Status:** blocked / nicht ausgeführt.

## P6 — Accessibility in vollständigen Abläufen

TC-105–TC-120; Abschlussgate **G6**.

### TC-105 — Schritt 105 — DOM-Stadtübersicht ergänzen

- **Ziel/Abnahme:** Geplante semantische Liste erlaubt Stadt-, District- und Agentauswahl als Alternative zur Canvas.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/components/WorldOverview.tsx` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Mit Tastatur jeden Eintrag erreichen; Name, Welt und Status sind für Screenreader verständlich.
- **Abhängigkeit:** TC-104; Phasenvoraussetzung G5.
- **Quellen:** WCAG22, AQ-EDITOR, AQ-RENDER. **Status:** blocked / nicht ausgeführt.

### TC-106 — Schritt 106 — Canvas-Auswahl mit DOM koppeln

- **Ziel/Abnahme:** Canvas- und DOM-Auswahl referenzieren dieselbe Instanz-ID; Auswahl ist nicht nur farblich markiert.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/game/entities/Building.ts` (vorhanden); `client/src/components/WorldOverview.tsx` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Auswahl abwechselnd per Maus und Tastatur setzen; sichtbarer Text und Canvas stimmen überein.
- **Abhängigkeit:** TC-105; Phasenvoraussetzung G5.
- **Quellen:** WCAG22, AQ-EDITOR, AQ-RENDER. **Status:** blocked / nicht ausgeführt.

### TC-107 — Schritt 107 — NPC-Felder beschriften

- **Ziel/Abnahme:** Einheit, Farbe, Maßstab und Wanderradius haben programmatisch zugeordnete Labels.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/editor/panels/Inspector.tsx` (vorhanden).
- **Prüfung:** Accessibilitytree auf Name/Role/Value prüfen; jede Select-/Inputkontrolle ohne visuelle Nachbarschaft verständlich.
- **Abhängigkeit:** TC-106; Phasenvoraussetzung G5.
- **Quellen:** WCAG22, AQ-EDITOR, AQ-RENDER. **Status:** blocked / nicht ausgeführt.

### TC-108 — Schritt 108 — Objektplatzierung ohne Drag ermöglichen

- **Ziel/Abnahme:** Gebäude und NPCs können über benannte Positions-/Slotfelder und Bestätigen platziert werden.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/editor/panels/Inspector.tsx` (vorhanden).
- **Prüfung:** Nur Tastatur: Objekt auswählen, Ziel eingeben, bestätigen, speichern; kein Drag-Schritt erforderlich.
- **Abhängigkeit:** TC-107; Phasenvoraussetzung G5.
- **Quellen:** WCAG22, AQ-EDITOR, AQ-RENDER. **Status:** blocked / nicht ausgeführt.

### TC-109 — Schritt 109 — Kamera ohne Pointergesten bedienen

- **Ziel/Abnahme:** Pan/Zoom/Fit besitzen erreichbare Bedienelemente und dokumentierte Tastatursteuerung.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/game/PhaserGame.tsx` (vorhanden).
- **Prüfung:** Ohne Maus/Pinch beide Stadtansichten vollständig erkunden; Eingabefokus darf keine ungewollte Kamerabewegung auslösen.
- **Abhängigkeit:** TC-108; Phasenvoraussetzung G5.
- **Quellen:** WCAG22, AQ-EDITOR, AQ-RENDER. **Status:** blocked / nicht ausgeführt.

### TC-110 — Schritt 110 — Iconbuttons sinnvoll benennen

- **Ziel/Abnahme:** Wetter-, Welt-, Hilfe- und Aktionsicons erhalten verständliche Namen statt Emoji allein.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/components/WorldOverview.tsx` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Screenreader-Namen ohne Glypheninterpretation prüfen; sichtbare Beschriftung und zugänglicher Name passen zusammen.
- **Abhängigkeit:** TC-109; Phasenvoraussetzung G5.
- **Quellen:** WCAG22, AQ-EDITOR, AQ-RENDER. **Status:** blocked / nicht ausgeführt.

### TC-111 — Schritt 111 — Dialogfokus führen

- **Ziel/Abnahme:** Gate-/Promotedialog enthält Fokus, ist schließbar und gibt Fokus an Auslöser zurück.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/components/GateOverlay.tsx` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Tab/ShiftTab, Escape und Schließen prüfen; kein Hintergrundbutton erreichbar solange Dialog offen.
- **Abhängigkeit:** TC-110; Phasenvoraussetzung G5.
- **Quellen:** WCAG22, AQ-EDITOR, AQ-RENDER. **Status:** blocked / nicht ausgeführt.

### TC-112 — Schritt 112 — Fokus sichtbar und unverdeckt halten

- **Ziel/Abnahme:** Bedienbare Elemente zeigen Fokus und werden nicht vollständig von Overlays verdeckt.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/editor/panels/Inspector.tsx` (vorhanden).
- **Prüfung:** Tastaturfolge bei geöffnetem Inspector und schmalem Viewport manuell prüfen; SC2.4.7/2.4.11 zuordnen.
- **Abhängigkeit:** TC-111; Phasenvoraussetzung G5.
- **Quellen:** WCAG22, AQ-EDITOR, AQ-RENDER. **Status:** blocked / nicht ausgeführt.

### TC-113 — Schritt 113 — Zielgrößen und Abstände prüfen

- **Ziel/Abnahme:** Webziele erfüllen 24x24 CSS-Pixel oder dokumentierte zulässige Abstandsausnahme; keine pauschale Konformitätsbehauptung.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/editor/panels/TilePalette.tsx` (vorhanden).
- **Prüfung:** Gemessene Bounds und Abstände für Palette, Topbar und Inspector protokollieren und belegte Lücken korrigieren.
- **Abhängigkeit:** TC-112; Phasenvoraussetzung G5.
- **Quellen:** WCAG22, AQ-EDITOR, AQ-RENDER. **Status:** blocked / nicht ausgeführt.

### TC-114 — Schritt 114 — Kontrast und Statusdarstellung prüfen

- **Ziel/Abnahme:** Textkontrast und Nichttext-Kontrast erfüllen passende Schwellen; Welt/Fehler/Status haben zusätzlich Text/Symbol.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/components/WorldOverview.tsx` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Vorder-/Hintergrundwerte im tatsächlichen Zustand messen; Rot/Grün allein darf keine Bedeutung tragen.
- **Abhängigkeit:** TC-113; Phasenvoraussetzung G5.
- **Quellen:** WCAG22, AQ-EDITOR, AQ-RENDER. **Status:** blocked / nicht ausgeführt.

### TC-115 — Schritt 115 — Reflow und Textvergrößerung sichern

- **Ziel/Abnahme:** DOM-Bedienung bleibt bei 400% Zoom und 320 CSS-Pixel Breite nutzbar; räumliche Karte hat separaten zugänglichen Zugang.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/editor/panels/Inspector.tsx` (vorhanden).
- **Prüfung:** Speichern und Gatebedienung bei Zoom ohne abgeschnittene Controls durchführen; Karten-Ausnahme nicht auf Formulare ausdehnen.
- **Abhängigkeit:** TC-114; Phasenvoraussetzung G5.
- **Quellen:** WCAG22, AQ-EDITOR, AQ-RENDER. **Status:** blocked / nicht ausgeführt.

### TC-116 — Schritt 116 — Bewegung reduzieren und pausieren

- **Ziel/Abnahme:** Reduced-Motion reduziert Wetter/Orb/Bewegung; dekorative Daueranimation lässt sich pausieren.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/game/scenes/VillageScene.ts` (vorhanden).
- **Prüfung:** Systempräferenz aktivieren, Pause bedienen; Status und Operationen bleiben vollständig verständlich.
- **Abhängigkeit:** TC-115; Phasenvoraussetzung G5.
- **Quellen:** WCAG22, AQ-EDITOR, AQ-RENDER. **Status:** blocked / nicht ausgeführt.

### TC-117 — Schritt 117 — Live-Meldungen dosieren

- **Ziel/Abnahme:** Save/Fehler/Verbindung nutzen passende Statusmeldung; kein 15Hz-Screenreader-Spam.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/components/WorldOverview.tsx` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Eventburst auslösen; nur relevante zusammengefasste Meldungen, Fokus bleibt beim Nutzer.
- **Abhängigkeit:** TC-116; Phasenvoraussetzung G5.
- **Quellen:** WCAG22, AQ-EDITOR, AQ-RENDER. **Status:** blocked / nicht ausgeführt.

### TC-118 — Schritt 118 — Fehler und Authzugang zugänglich machen

- **Ziel/Abnahme:** Fehler sind textlich zugeordnet; Wiederanmeldung erhält Kontext und verlangt keine unnötige Gedächtnisaufgabe.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/components/GateOverlay.tsx` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Ungültige Eingabe und Sitzungsauslauf per Tastatur durchspielen; Korrekturweg und erneute Anmeldung erreichbar.
- **Abhängigkeit:** TC-117; Phasenvoraussetzung G5.
- **Quellen:** WCAG22, AQ-EDITOR, AQ-RENDER. **Status:** blocked / nicht ausgeführt.

### TC-119 — Schritt 119 — Accessibility-Prozessprüfung durchführen

- **Ziel/Abnahme:** Stadtwahl→Objekt→Save und Gate→Entscheidung funktionieren mit Tastatur und einem verfügbaren Screenreader.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `client/src/components/WorldOverview.tsx` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Browser-/Screenreader-Version, Schritte, Befunde und Grenzen protokollieren; automatisierte Prüfung allein genügt nicht.
- **Abhängigkeit:** TC-118; Phasenvoraussetzung G5.
- **Quellen:** WCAG22, AQ-EDITOR, AQ-RENDER. **Status:** blocked / nicht ausgeführt.

### TC-120 — Schritt 120 — Gate G6 Accessibility abnehmen

- **Ziel/Abnahme:** Alle priorisierten UI-Abläufe bestanden; Restlücken und nicht geprüfte Kriterien explizit ausgewiesen.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `docs/twincity/accessibility-acceptance.md` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Noir prüft Messwerte/Manuellprotokoll; keine WCAG-Gesamtkonformität ohne vollständige Prüfung behaupten.
- **Abhängigkeit:** TC-119; Phasenvoraussetzung G5.
- **Quellen:** WCAG22, AQ-EDITOR, AQ-RENDER. **Status:** blocked / nicht ausgeführt.

## P7 — Integration, Betrieb und Abnahme

TC-121–TC-143; Abschlussgate **G7**.

### TC-121 — Schritt 121 — District-bis-Sprite E2E prüfen

- **Ziel/Abnahme:** Registrierung erzeugt persistierten District und echten Building-Sprite im VillageScene-Client.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/e2e/test_district_e2e.py` (vorhanden).
- **Prüfung:** NIO-Testworker registriert Testdistrict; API-, Event- und Browserbelege auf gleiche Welt/ID korrelieren.
- **Abhängigkeit:** TC-120; Phasenvoraussetzung G6.
- **Quellen:** SRC27, SRC28, WB-PERSIST, WB-PROMOTE, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-122 — Schritt 122 — Worker-bis-Hero E2E prüfen

- **Ziel/Abnahme:** Geplante Teststrecke bildet echten Taskstart/Ende auf richtigen Hero und Gebäudestatus ab.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/e2e/test_agents_e2e.py` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Task/Run/Worker-ID mit Event und DOM-Auswahl vergleichen; kein synthetischer Produktworker.
- **Abhängigkeit:** TC-121; Phasenvoraussetzung G6.
- **Quellen:** SRC27, SRC28, WB-PERSIST, WB-PROMOTE, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-123 — Schritt 123 — Editor-Neustart E2E prüfen

- **Ziel/Abnahme:** Gespeicherte vollständige Karte und aktiver Slot überstehen Neustart der isolierten Testinstanz.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/e2e/test_maps_e2e.py` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Karte speichern, Testinstanz neu starten, zwei Clients vergleichen; Produktdienst nicht für Tests neu starten.
- **Abhängigkeit:** TC-122; Phasenvoraussetzung G6.
- **Quellen:** SRC27, SRC28, WB-PERSIST, WB-PROMOTE, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-124 — Schritt 124 — Live-Shadow-Negativmatrix ausführen

- **Ziel/Abnahme:** Map, Gate, District, Agent, Slot und Cursor mit gleichen IDs bleiben über alle Pfade getrennt.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/e2e/test_world_isolation.py` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Geplante E2E-Testdatei nutzt Fakeclients/eigene Repos; keine Live-Nebenwirkung darf auftreten.
- **Abhängigkeit:** TC-123; Phasenvoraussetzung G6.
- **Quellen:** SRC27, SRC28, WB-PERSIST, WB-PROMOTE, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-125 — Schritt 125 — Zwei-Client-Broadcast prüfen

- **Ziel/Abnahme:** Beide Clients sehen dieselben bestätigten Änderungen; langsamer Client erhält definierten Resync.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/tests/test_bridge.py` (vorhanden).
- **Prüfung:** Normalen und gebremsten Consumer gleichzeitig im Test betreiben; Endrevision vergleichen.
- **Abhängigkeit:** TC-124; Phasenvoraussetzung G6.
- **Quellen:** SRC27, SRC28, WB-PERSIST, WB-PROMOTE, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-126 — Schritt 126 — Reconnect und Offline visuell prüfen

- **Ziel/Abnahme:** Disconnect-/Reconnectverhalten folgt D2; keine falschen Success- oder Liveanzeigen.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_ACCEPTANCE.md` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Isolierten Testbackendzugang trennen und wiederherstellen; Screens/Events mit Zeitstempeln protokollieren.
- **Abhängigkeit:** TC-125; Phasenvoraussetzung G6.
- **Quellen:** SRC27, SRC28, WB-PERSIST, WB-PROMOTE, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-127 — Schritt 127 — Promotion mit echten Testrepos prüfen

- **Ziel/Abnahme:** Genehmigter exakter Commit erscheint nach Merge im Ziel-Testrepo; gefälschte Freigabe verändert keine Ref.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/e2e/test_gates_e2e.py` (vorhanden).
- **Prüfung:** Vorher-/Nachher-HEAD, Ticket, Merge-Receipt und Diff überprüfen; nur temporäre Repos verwenden.
- **Abhängigkeit:** TC-126; Phasenvoraussetzung G6.
- **Quellen:** SRC27, SRC28, WB-PERSIST, WB-PROMOTE, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-128 — Schritt 128 — Asset- und Lizenzinventar abnehmen

- **Ziel/Abnahme:** Alle ausgelieferten Assets sind lokal erreichbar und Lizenz-/Attributionsbelege sind vorhanden.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_ASSETS.md` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Buildmanifest mit lokalen Dateien und Lizenztexten abgleichen; Theme-Kommentar allein ist kein Lizenznachweis.
- **Abhängigkeit:** TC-127; Phasenvoraussetzung G6.
- **Quellen:** SRC27, SRC28, WB-PERSIST, WB-PROMOTE, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-129 — Schritt 129 — Twin-City-Buildgrenze prüfen

- **Ziel/Abnahme:** Build enthält keine Bun-Server-/Session-Watcher-Abhängigkeit und keine Tokens; Originaldienst bleibt erhalten.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_ACCEPTANCE.md` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Ausgelieferte Dateien und Netzwerkanfragen prüfen; Buildquellen am konkreten Commit dokumentieren.
- **Abhängigkeit:** TC-128; Phasenvoraussetzung G6.
- **Quellen:** SRC27, SRC28, WB-PERSIST, WB-PROMOTE, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-130 — Schritt 130 — Leistung mit realistischem Bestand messen

- **Ziel/Abnahme:** Einzel-/Twin-View und mehr als 15 Gebäude besitzen gemessene Framezeiten und Speicherwerte auf benanntem Gerät.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_PERFORMANCE.md` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Gleiche Referenzkarte/Testereignisse verwenden; p95-Framezeit, Entityzahl und Messdauer berichten, Zielabweichung offen lassen.
- **Abhängigkeit:** TC-129; Phasenvoraussetzung G6.
- **Quellen:** SRC27, SRC28, WB-PERSIST, WB-PROMOTE, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-131 — Schritt 131 — Betriebseinheit und Gesundheitscheck prüfen

- **Ziel/Abnahme:** Loopback, statischer Buildpfad, vorhandene Abhängigkeiten und kontrollierter Shutdown sind dokumentiert.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `world_bridge/__main__.py` (vorhanden); `world_bridge/README.md` (vorhanden).
- **Prüfung:** Unit/Startparameter nur lesend gegen Quellstand prüfen; geplante Änderung mit Rollback beschreiben.
- **Abhängigkeit:** TC-130; Phasenvoraussetzung G6.
- **Quellen:** SRC27, SRC28, WB-PERSIST, WB-PROMOTE, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-132 — Schritt 132 — Rollbackverfahren erproben

- **Ziel/Abnahme:** Vorheriger Build und persistierte Datenrevision können in isolierter Umgebung wiederhergestellt werden.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_ROLLBACK.md` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Testdeployment vor/zurück wechseln; Datenkompatibilität und Revisionsschutz prüfen, keine echten Nutzerkarten überschreiben.
- **Abhängigkeit:** TC-131; Phasenvoraussetzung G6.
- **Quellen:** SRC27, SRC28, WB-PERSIST, WB-PROMOTE, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-133 — Schritt 133 — NEU-Core-Gate überwacht abnehmen

- **Ziel/Abnahme:** Prüfungen am exakten Commit liefern Exitcodes und gehashte Logs; fehlende Voraussetzungen oder Skip blockieren Abnahme.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_GATE_RECEIPTS.json` (geplant; vor Ausführung Eigentümerpfad bestätigen).
- **Prüfung:** make compile; make lint; make types; make test-core. Zuerst Laufzeit messen: passt die Gruppe nicht in das effektive Workerbudget, in einzelne Befehle und getrennte Start-/Status-/Collect-Jobs zerlegen. Langlaufende Checks nur als persistenter, von NIO überwachter Checkjob im isolierten Testworkspace; kein unbetreuter Hintergrundprozess. WIP1 bis Ergebnis beibehalten.
- **Abhängigkeit:** TC-132; Phasenvoraussetzung G6.
- **Quellen:** SRC27, SRC28, WB-PERSIST, WB-PROMOTE, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-134 — Schritt 134 — Architect-Gate überwacht abnehmen

- **Ziel/Abnahme:** Prüfungen am exakten Commit liefern Exitcodes und gehashte Logs; fehlende Voraussetzungen oder Skip blockieren Abnahme.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_GATE_RECEIPTS.json` (geplant; vor Ausführung Eigentümerpfad bestätigen).
- **Prüfung:** make test-architect. Zuerst Laufzeit messen: passt die Gruppe nicht in das effektive Workerbudget, in einzelne Befehle und getrennte Start-/Status-/Collect-Jobs zerlegen. Langlaufende Checks nur als persistenter, von NIO überwachter Checkjob im isolierten Testworkspace; kein unbetreuter Hintergrundprozess. WIP1 bis Ergebnis beibehalten.
- **Abhängigkeit:** TC-133; Phasenvoraussetzung G6.
- **Quellen:** SRC27, SRC28, WB-PERSIST, WB-PROMOTE, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-135 — Schritt 135 — Apollo- und NEU-E2E-Gate überwacht abnehmen

- **Ziel/Abnahme:** Prüfungen am exakten Commit liefern Exitcodes und gehashte Logs; fehlende Voraussetzungen oder Skip blockieren Abnahme.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_GATE_RECEIPTS.json` (geplant; vor Ausführung Eigentümerpfad bestätigen).
- **Prüfung:** make ui-test; make e2e. Zuerst Laufzeit messen: passt die Gruppe nicht in das effektive Workerbudget, in einzelne Befehle und getrennte Start-/Status-/Collect-Jobs zerlegen. Langlaufende Checks nur als persistenter, von NIO überwachter Checkjob im isolierten Testworkspace; kein unbetreuter Hintergrundprozess. WIP1 bis Ergebnis beibehalten.
- **Abhängigkeit:** TC-134; Phasenvoraussetzung G6.
- **Quellen:** SRC27, SRC28, WB-PERSIST, WB-PROMOTE, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-136 — Schritt 136 — World-Bridge-Gate überwacht abnehmen

- **Ziel/Abnahme:** Prüfungen am exakten Commit liefern Exitcodes und gehashte Logs; fehlende Voraussetzungen oder Skip blockieren Abnahme.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_GATE_RECEIPTS.json` (geplant; vor Ausführung Eigentümerpfad bestätigen).
- **Prüfung:** python3 -m pytest world_bridge/tests -q. Zuerst Laufzeit messen: passt die Gruppe nicht in das effektive Workerbudget, in einzelne Befehle und getrennte Start-/Status-/Collect-Jobs zerlegen. Langlaufende Checks nur als persistenter, von NIO überwachter Checkjob im isolierten Testworkspace; kein unbetreuter Hintergrundprozess. WIP1 bis Ergebnis beibehalten.
- **Abhängigkeit:** TC-135; Phasenvoraussetzung G6.
- **Quellen:** SRC27, SRC28, WB-PERSIST, WB-PROMOTE, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-137 — Schritt 137 — Agent-Quest-Build und Tests überwacht abnehmen

- **Ziel/Abnahme:** Prüfungen am exakten Commit liefern Exitcodes und gehashte Logs; fehlende Voraussetzungen oder Skip blockieren Abnahme.
- **Repo:** `/home/finn-powers/Projects/Agent-Quest`. **Dateien:** `docs/hermes/TWIN_CITY_GATE_RECEIPTS.json` (geplant; vor Ausführung Eigentümerpfad bestätigen).
- **Prüfung:** Deklarierte package.json-Skripte für Client-Typecheck/Build und Server-Tests einzeln ausführen. Zuerst Laufzeit messen: passt die Gruppe nicht in das effektive Workerbudget, in einzelne Befehle und getrennte Start-/Status-/Collect-Jobs zerlegen. Langlaufende Checks nur als persistenter, von NIO überwachter Checkjob im isolierten Testworkspace; kein unbetreuter Hintergrundprozess. WIP1 bis Ergebnis beibehalten.
- **Abhängigkeit:** TC-136; Phasenvoraussetzung G6.
- **Quellen:** SRC27, SRC28, WB-PERSIST, WB-PROMOTE, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-138 — Schritt 138 — Projektgate-Receipts zusammenführen

- **Ziel/Abnahme:** Alle erforderlichen Stack-Prüfungen liegen als exakte Commit-Receipts vor; kein Skip wird als bestanden gewertet.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_ACCEPTANCE.md` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Vorher erstellte Prüfbelege samt Exitcode, Commit, Laufzeit und Restfehlern abgleichen; hier keine vollständigen Suiten erneut starten.
- **Abhängigkeit:** TC-137; Phasenvoraussetzung G6.
- **Quellen:** SRC27, SRC28, WB-PERSIST, WB-PROMOTE, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-139 — Schritt 139 — NIO-Provenienz vollständig auditieren

- **Ziel/Abnahme:** Jede Produktänderung ist einem tatsächlichen NIO-Run und überprüften Commit zugeordnet.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_ACCEPTANCE.md` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Manifest gegen Run-Receipts und git show prüfen; Guide-Artefakte dürfen nicht als Workerlieferung zählen.
- **Abhängigkeit:** TC-138; Phasenvoraussetzung G6.
- **Quellen:** SRC27, SRC28, WB-PERSIST, WB-PROMOTE, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-140 — Schritt 140 — Betriebsübergang vorbereiten und prüfen

- **Ziel/Abnahme:** Konkretes Deploymentpaket mit Buildhash, Datenbackup und Rollback liegt vor; Laufzeitfreigabe bleibt explizit.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_ACCEPTANCE.md` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Vor einer später autorisierten Auslieferung Paket und Rechte prüfen; Planrevision allein löst kein Deployment aus.
- **Abhängigkeit:** TC-139; Phasenvoraussetzung G6.
- **Quellen:** SRC27, SRC28, WB-PERSIST, WB-PROMOTE, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-141 — Schritt 141 — Freigegebenen Kandidaten ausliefern

- **Ziel/Abnahme:** Nur bei dokumentierter gesonderter Betriebsfreigabe werden genau die geprüften Builds ausgeliefert; ohne Freigabe blocked.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_ACCEPTANCE.md` (geplant; vor Ausführung Eigentümerpfad bestätigen).
- **Prüfung:** Freigabe, Kandidatenhash, Backup und Rückweg prüfen; NIO führt dokumentierten Deploymentbefehl aus und protokolliert Receipt. Diese Planrevision erteilt keine Betriebsfreigabe.
- **Abhängigkeit:** TC-140; Phasenvoraussetzung G6.
- **Quellen:** SRC27, SRC28, WB-PERSIST, WB-PROMOTE, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-142 — Schritt 142 — Ausgelieferten Stand zur Laufzeit prüfen

- **Ziel/Abnahme:** Laufende Version/Assets entsprechen den geprüften Hashes; Health, beide Welten und ein autorisierter Smoke-Ablauf sind belegt.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_ACCEPTANCE.md` (geplant; vor Ausführung Eigentümerpfad bestätigen).
- **Prüfung:** Nach Deployment Version und Health lesen; zugängliche Stadtansichten und Isolation prüfen; mutative Smoke-Proben nur in ausgewiesener Testwelt; Fehler blockiert Gesamtabschluss.
- **Abhängigkeit:** TC-141; Phasenvoraussetzung G6.
- **Quellen:** SRC27, SRC28, WB-PERSIST, WB-PROMOTE, NB-NOIR. **Status:** blocked / nicht ausgeführt.

### TC-143 — Schritt 143 — Gate G7 Gesamtprodukt abnehmen

- **Ziel/Abnahme:** Funktion, echte Dorfansicht, Editor, Accessibility, Isolation, Promotion und NIO-Provenienz sind gemeinsam belegt.
- **Repo:** `/home/finn-powers/Projects/NIO`. **Dateien:** `docs/hermes/TWIN_CITY_ACCEPTANCE.md` (geplant; vor Ausführung anlegen oder bestehenden Eigentümerpfad bestätigen).
- **Prüfung:** Alle Phasengates und Original-DoD prüfen; offener Pflichtpunkt verhindert delivered, unabhängig von grünen Teiltests.
- **Abhängigkeit:** TC-142; Phasenvoraussetzung G6.
- **Quellen:** SRC27, SRC28, WB-PERSIST, WB-PROMOTE, NB-NOIR. **Status:** blocked / nicht ausgeführt.
