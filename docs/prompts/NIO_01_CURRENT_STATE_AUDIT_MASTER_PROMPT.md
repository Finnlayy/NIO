# NIO Current-State Audit Master Prompt

## Rolle und Ziel

Du bist der leitende read-only Bestandsprüfer für `/home/finn-powers/Projects/NIO`. Ermittle den tatsächlich vorhandenen Entwicklungs- und Runtime-Stand vollständig, beweisgestützt und ohne Änderungen. Dein Bericht ist die verbindliche Grundlage für die spätere Umsetzung des Release-Backlogs.

Wichtig: Erst den Bestand beweisen, dann Lücken bestimmen. In diesem Auftrag implementierst, reparierst, formatierst, installierst, migrierst, stagest, committest, pushst, mergst oder löschst du nichts.

## Maßgebliche Eingaben

Lies vollständig, soweit vorhanden:

- `AGENTS.md` und näher gelegene `AGENTS.md`-Dateien
- `README.md`
- `docs/superpowers/plans/2026-11-10-nio-usable-release-backlog.md`
- `docs/superpowers/specs/2026-11-10-nio-architecture-map-design.md`
- `docs/SPEECH.md`
- `docs/CIEL.md`
- `docs/hermes/RUNTIME_PLAN.md`
- `limbs/registry.json`
- `/home/finn-powers/Downloads/01_final_manas_ciel_edith_lilith_master_prompt.md.pdf`

Die PDF ist eine Spezifikation, kein Implementierungsnachweis.

## Unverhandelbare Regeln

1. Arbeite read-only. Verändere weder Dateien noch Git-Zustand oder Runtime-Daten.
2. Verboten sind insbesondere `git add`, `commit`, `stash`, `switch`, `checkout`, `reset`, `clean`, `rebase`, `merge`, `push`, `pull`, `rm` und mutierende Worktree-Befehle.
3. Bewahre alle uncommitted Änderungen. Behaupte nie, eine fremde Datei sei entbehrlich.
4. Zeige keine Secret-Werte. Melde nur Pfad, Fundklasse und vollständig maskierten Typ.
5. Keine Live-Orders, keine Trading-Konfigurationsänderung, keine externen Schreibzugriffe.
6. Führe nur sichere lokale Tests aus, die keine Installation, Netztransaktion oder dauerhafte Zustandsänderung benötigen.
7. Erfinde nichts. Verwende `UNKNOWN`, `NOT_CHECKED` oder `NOT_PROVEN`.
8. Trenne Quellcode vorhanden, statisch verbunden, getestet, runtime-verifiziert und aktuell laufend.
9. Historische Pläne, Changelogs und Testberichte beweisen den aktuellen Stand nicht.
10. Ein Blocker in einem Bereich stoppt nicht den read-only Audit unabhängiger Bereiche.

## Beweisstufen

- `E0 SPECIFIED`: nur PDF oder Ziel-/Planungsdokument.
- `E1 PRESENT`: aktuelle Datei, Funktion, Route, Registry-Definition oder Konfiguration vorhanden.
- `E2 STATICALLY_CONNECTED`: aktuelle Imports, Aufrufe, Adapter oder Datenflüsse belegen die Verbindung.
- `E3 TESTED`: ein relevanter Test wurde in diesem Audit reproduzierbar erfolgreich ausgeführt.
- `E4 RUNTIME_VERIFIED`: ein sicherer lokaler End-to-End-Test wurde in diesem Audit erfolgreich ausgeführt.
- `E5 OPERATING`: Komponente wurde als aktuell laufend und gesund beobachtet; Zeitpunkt und Methode sind genannt.

Dokumentation allein erreicht höchstens E0, Quellcode allein höchstens E2.

## Statusklassen

- `IMPLEMENTED`: erforderlicher Code und Verbindung vorhanden, mindestens E2.
- `PARTIAL`: Teile vorhanden, vollständiger Zielpfad fehlt oder ist widersprüchlich.
- `SPECIFIED_ONLY`: Ziel beschrieben, Implementierung nicht ausreichend belegt.
- `PLANNED_BLOCKED`: ausdrücklich geplant, deaktiviert oder gesperrt.
- `BROKEN`: vorgesehene Implementierung scheitert reproduzierbar.
- `UNKNOWN`: mit erlaubten Prüfungen nicht entscheidbar.

## Verbindlicher Ablauf

### A. Repository-Identität und Verlustschutz

1. Erfasse read-only: Branch, HEAD, Upstream, `git status --short --branch`, Remotes ohne eingebettete Credentials und jüngste relevante Commits.
2. Erfasse alle Worktrees und Stashes nur lesend.
3. Ordne jede geänderte oder ungetrackte Datei nach Bereich, vermutetem Zweck und möglichem Besitzer ein.
4. Vergleiche relevante uncommitted Inhalte, Stash-Objekte und andere Worktrees ohne sie anzuwenden oder auszuchecken.
5. Bestimme, welche Arbeit von Claude oder anderen Agents noch nicht committed ist, soweit durch Pfade, Metadaten und Inhalte belegbar.
6. Erstelle eine Verlustschutzliste aller Pfade und Git-Objekte, die ein Folgeagent nicht überschreiben, löschen oder vermischen darf.

### B. Repository-Wahrheit

1. Inventarisiere `core/`, `orchestrator/`, `apollo/`, `frontend/`, `limbs/`, relevante Scripts, Konfigurationen und Tests.
2. Trenne Produktivcode von `Architect/`, Plänen, Forschung, Patches, generierten Ausgaben, Build-/Runtime-Artefakten und Agent-Worktrees.
3. Suche Widersprüche zwischen README, Ciel-Dokumentation, Runtime-Plan, Changelog, Blueprints, PDF und aktuellem Code.
4. Nenne für jeden Widerspruch die stärkste aktuelle Quelle und die daraus folgende Einstufung.

### C. Produktive Pfade

Prüfe jeweils Start, Zwischenschritte, Ende, Status, Beweisstufe, Quellen, Tests und fehlendes Glied:

1. Mensch/Mikrofon → lokale oder Browser-Spracherkennung.
2. Spracherkennung → Apollo-Entwurf → explizites Senden.
3. Apollo → Backend/API.
4. Apollo → `apollo/ciel`.
5. `apollo/ciel` → NIO-Haupt-Orchestrator.
6. Orchestrator → `limbs/registry.json` → Subprozess.
7. Ciel/Orchestrator → Event Bus → UDS/SSE → Apollo.
8. Policy/Approval → unmittelbar vor Ausführung.
9. Cancel/Stop → vollständiger Prozessbaum und optionale Container.
10. Result → Audit/Telemetry → Apollo-Anzeige.

### D. PDF-zu-Code-Matrix

Prüfe MANAS: CIEL, Rouge, Noir, Blanche, Jaune, E.D.I.T.H., L.I.L.I.T.H., RGCCO, Deep-Sea, Obsidian Memory, Dynamic Skill Registry, Apollo NCM und Ausgabe-/IPC-Vertrag einzeln. Ähnliche Namen beweisen keine semantische Gleichheit. Nenne Gemeinsamkeiten, Unterschiede und fehlende Verdrahtung.

### E. Limbs

1. Verwende `limbs/registry.json` als primäre Statusquelle.
2. Erfasse jeden Limb genau einmal: Status, Entrypoint, Operationen, Schreib-/Netzwerkverhalten, erlaubte Umgebung, Zielsysteme.
3. Prüfe, ob Entrypoint und Operationen im aktuellen Code existieren.
4. Prüfe, ob `planned`-Limbs beim Routing und Start ausgeschlossen sind.
5. Unterscheide Datei vorhanden, aktiv, konform getestet und produktiv nutzbar.
6. Prüfe Echo, Speech, Bootstrap, Vault, REA, OpenManus, Trading und Toolbox.
7. Belege Paper-/Live-Grenzen statisch, ohne Orders auszuführen.

### F. Konfiguration, Betrieb und Sicherheit

Prüfe Konfigurationsquellen, Start/Stop/Doctor, Demo-/Mock-Kennzeichnung, Secrets, Prozessgruppen, Timeouts, Umgebungsfilter, Output-Limits, Persistenz, Migrationen, Backup/Restore, Telemetrie, Audit-Integrität, Retention, MCP-Grenzen, Netzwerkausgänge und externen Not-Aus.

### G. Testbaseline

1. Inventarisiere alle Testbefehle und Abhängigkeiten.
2. Klassifiziere Tests als sicher lokal, lokal mutierend, netzabhängig oder extern wirksam.
3. Führe nur sichere lokale Tests ohne Installation aus.
4. Beginne mit gezielten Suites für Ciel, Orchestrator, Registry, Speech und aktive Limbs.
5. Dokumentiere Befehl, Zeitpunkt, HEAD, Arbeitsbaumzustand, Ergebnis, Dauer und Skips.
6. Installiere fehlende Abhängigkeiten nicht; melde sie als Blocker.
7. Historische Angaben wie „912 Tests grün“ sind kein aktueller Nachweis.

### H. Backlog-Abgleich

Klassifiziere jede ID `NIO-001` bis `NIO-136` genau einmal als:

- `DONE_VERIFIED`
- `PARTIAL`
- `OPEN`
- `BLOCKED`
- `NOT_APPLICABLE`

`DONE_VERIFIED` verlangt einen aktuellen konkreten Nachweis. Für alle anderen Klassen nenne das kleinste fehlende Ergebnis und Abhängigkeiten.

## Abbruchbedingungen

Stoppe nur die betreffende Prüfung und melde einen Blocker, wenn sie Live-Trading, externe Nachrichten/Schreibzugriffe, bezahlte Dienste, Secret-Offenlegung, Installation, Root-Rechte, dauerhafte Systemänderung oder Veränderung fremder Arbeit erfordern würde.

## Ausgabevertrag

Gib den vollständigen Inhalt für `docs/audits/current-state/NIO_CURRENT_STATE_AUDIT.md` aus, schreibe die Datei im read-only Audit aber nicht selbst. Eine separate Freigabe ist zum Speichern nötig.

Verwende exakt diese Abschnitte:

1. `# Executive Summary`
2. `# Audit Scope and Limitations`
3. `# Repository Identity`
4. `# Branches, Worktrees, Stashes and Uncommitted Work`
5. `# Loss-Protection List`
6. `# Productive Architecture Paths`
7. `# Canonical PDF-to-Code Matrix`
8. `# Apollo and Speech Status`
9. `# Ciel Status and Missing Productive Wiring`
10. `# Orchestrator, Policy and Process Control`
11. `# Limb Inventory`
12. `# Trading Safety Boundary`
13. `# Persistence, Telemetry and Recovery`
14. `# Security Findings`
15. `# Test Baseline`
16. `# Backlog Status NIO-001 through NIO-136`
17. `# Contradictions and Stale Claims`
18. `# Blockers and Unknowns`
19. `# Prioritized Delta for Implementation`
20. `# Machine-Readable Handoff`

Der letzte Abschnitt endet mit genau einem validen JSON-Codeblock mit:

- `audit_version`
- `repository_root`
- `head_commit`
- `branch`
- `working_tree_dirty`
- `protected_paths`
- `verified_runtime_paths`
- `missing_runtime_edges`
- `backlog.done_verified`
- `backlog.partial`
- `backlog.open`
- `backlog.blocked`
- `backlog.not_applicable`
- `test_runs`
- `release_blockers`
- `unknowns`

Das JSON enthält keine Kommentare, Platzhalter oder Widersprüche zum Bericht.

## Abschlussprüfung

Vor Abgabe bestätige:

- keine Datei, Git-Referenz oder Runtime-Daten verändert,
- keine Secret-Werte offengelegt,
- jede zentrale Behauptung belegt oder sichtbar als unbekannt markiert,
- PDF-Ziel und Runtime-Fakt strikt getrennt,
- alle 136 IDs genau einmal klassifiziert,
- Verlustschutzliste vollständig,
- Handoff-JSON valide und konsistent.
