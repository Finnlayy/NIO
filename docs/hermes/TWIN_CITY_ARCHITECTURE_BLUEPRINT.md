# Twin-City — korrigierter Architektur-Blueprint

Stand 22.11.2026. Ergänzt den [Ausführungsplan](TWIN_CITY_INFRA_PLAN.md).
Historischen Guide-Blueprint ersetzt; [Original archiviert](archive/TWIN_CITY_ARCHITECTURE_BLUEPRINT_2026-11-21_FAILED.md).
Beobachteter Quellstand: NIO 38c0c59f29895889c3988f1eb1d6a04c4da09362;
Agent-Quest 1c16b40eac3267e5d6b0d161284dbdccf0723684, jeweils mit zusätzlich inventarisiertem Dirty-Zustand.

## 1. Vorhandene Architektur und Wiederverwendung

Agent-Quest: React-DOM-Overlays ↔ EventBridge ↔ PhaserGame → BootScene/VillageScene.
Editor: React-Palette/Inspector ↔ EditorBridge/editorStore ↔ EditorScene.
MapConfigRenderer lädt konfigurierte Karten; TerrainRenderer unterstützt die bestehende Darstellung.
Building/HeroSprite/NpcSprite sind getrennte Entitäten. AgentState erzeugt Heroes,
MapConfig.npcs dekorative Bewohner. Die Wege verwenden BFS, nicht A*.

| Bestandteil | Entscheidung | Beleg im Agent-Quest-Repo |
|---|---|---|
| VillageScene und vorhandene Sprites | KEEP + gezielt ADAPT | client/src/game/scenes/VillageScene.ts:454,561,717 |
| Vollständiger Editor samt Inspector/Palette | KEEP + Transport ADAPT | client/src/editor/game/scenes/EditorScene.ts:734,764,1347 |
| MapConfig | Felder bewahren, Version/Welt/Revision ergänzen | client/src/editor/types/map.ts:106 |
| Fünf Karten-Slots, aktive Karte, Template | Fähigkeiten KEEP, Eigentümer nach NIO | server/src/map/routes.ts:79; storage.ts:5 |
| Acht feste funktionale Gebäude | Auf District-Instanzen erweitern | server/src/map/validator.ts:25; game/data/building-layout.ts:37 |
| Assetloader/Manifest/Theme | KEEP, reale Assets und Lizenzdateien prüfen | game/data/asset-loader.ts:10; game/themes/registry.ts:4 |
| EventBridge/EditorBridge/editorStore | Welt- bzw. Editorinstanz statt globaler Singleton | game/EventBridge.ts:48; editor/EditorBridge.ts:84; editor/state/editor-store.ts:138 |
| Straßen/BFS | KEEP, Zustand je Welt und unerreichbares Ziel korrekt behandeln | game/data/road-network.ts:59,248 |
| Scene-Cleanup/Phaser-Lifecycle | KEEP, Twin-View-Regressionen ergänzen | VillageScene.ts:365; PhaserGame.tsx:17 |
| Prozedurales Fallback ohne Map | Nur im Twin-City-Pfad ersetzen: D2 | VillageScene.ts:478 |
| Bun-Watcher/Session-Parser | Aus Twin-City-Build ausschließen | server/src/; Referenzdienst bleibt erhalten |
| Crude TwinCityScene mit Graphics-Quadraten | Nicht als Renderinggrundlage übernehmen | separater AQ-twin-city-Worktree |

**Korrektur:** EditorScene speichert per POST /api/map/{slot}; MapStorage schreibt serverseitig.
D1 rechtfertigt keinen Verlust des Editors. Seine Entwürfe sind flüchtige Bedienzustände.

## 2. Zielgrenzen

Browser → World-Bridge :8750 → vorhandene Python-/Kanban-/Redis-Eigentümer.
Browser sendet Nutzerabsichten und rendert bestätigte Ergebnisse. Python entscheidet
über Berechtigungen, Jobs, Timer, Revisionen und Gates. Frontend hat keine Merge-Autorität.

live|shadow bezeichnet Ausführungswelten. map_id/slot_id bezeichnet Städte/Karten
innerhalb einer Welt. district_id benennt Gebäudeinstanzen, asset_type die Grafik,
district_type die Funktion. npc_id ist kein worker_id.

NIO speichert vollständige versionierte Karten; Terrain, Dekorationen, Pfade, Gebäude,
NPCs, Spawn, Weltgröße und Einstellungen bleiben erhalten. Gespeicherte Weltkoordinaten
werden mit dokumentierten Einheiten in ein deterministisches Layout überführt.
Automatische District-Platzierung ergänzt unplatzierte Districts und überschreibt keine
bewusst gespeicherte Position. Zwei Ansichten besitzen getrennte Event-/Wege-/Szenenzustände.

## 3. Vertragsänderungen — Soll, noch nicht vorhandene APIs

Die bisherigen drei Commands reichen für den Editor nicht aus. Geplant sind
weltgebundene Lese-/Speicher-/Aktivierungsverträge für Kartenslots und vollständige
MapConfig-Dokumente. Vorhandene Quell-API dient als Funktionsinventar, nicht als
ungeprüft kopierter NIO-Vertrag.

Speichern: world_id + map_id + expected_revision + command_id + MapConfig.
Server validiert Welt, Rechte, Assetreferenzen, Größenlimits und Revision, persistiert
atomar und antwortet mit bestätigter Revision. Konflikt bewahrt den lokalen Entwurf;
kein stilles Last-Writer-Wins. Slotwechsel und Reconnect ändern keine fremde Welt.
Schema-Version und einmalige Migration alter Karten sind Bestandteil der Abnahme.

Snapshot: Welt, Kartenrevision, bestätigte Districts/NPCs/Worker/Gates, Serverzeit,
Sequenz und Restart-Epoch. Delta enthält dieselbe Welt/Epoch. Bei Lücke wird synchronisiert,
nicht weitergeraten. Protokollschema und Python-/TS-Typen müssen übereinstimmen.

## 4. Lücken der vorhandenen Bridge

- world_bridge/state.py:8 und :64: RAM-Dictionaries, keine dauerhafte Kartenhaltung.
- world_bridge/bridge.py:68: Adapter-Snapshot überschreibt Store; neue Verbindung
  kann dynamisch registrierte Districts entfernen.
- world_bridge/adapters.py:107: statische Districts statt persistierter Stadt.
- world_bridge/router.py:29: nur dispatch_prompt, resolve_gate, promote_limb_or_config.
- world_bridge/router.py:76: Promotion prüft Client-Booleans; kein Merge-Aufruf.
- world_bridge/bridge.py:73: gemeinsamer last_event_id bei weltweise getrennten
  Sequenzen und Snapshot-vor-Subscription bedürfen Resync-/Race-Tests.
- world_bridge/bridge.py:39 und :81: unbeschränkte Queues; Lastgrenzen und langsame
  Clients sind ausdrücklich zu prüfen.
- world_bridge/bridge.py:132 sowie AQ-twin-city/client/src/game/city/ws.ts:27:
  langfristiger Token im WS-Query ist kein Zielvertrag für Browserauth.

Der Backendbestand ist eine Grundlage, kein bereits abgenommenes Zielsystem.
Gegenbeispiele und Regressionstests gehen dem jeweiligen Delta voraus.

## 5. UI-Abnahme und Accessibility

Rich Pixelart bleibt sichtbar: texturiertes Terrain, Bäume, echte Dach-/Gebäudesprites,
Helden und dekorative Bewohner. Aktive reale Tasks und reine Dekoration sind unterscheidbar.
Wetter/Kamera dürfen View-State sein; Ausführung/Approval/Timer niemals.

Canvas-Aktionen besitzen semantische DOM-Entsprechungen: Objektliste, benannte
Eigenschaften, Positionsfelder und Schaltflächen. Tastaturfokus darf nicht unter Overlays
verschwinden; Dialog schließt mit Escape und gibt Fokus zurück. Weltstatus trägt Text.
Reduced Motion und abschaltbares Wetter; Live-Regions melden keine 15-Hz-Ereignisflut.

Laufzeitbeobachtung 21.11.: Editor mit Terrain/Paths/Decorations/Buildings/NPC/Spawn,
Slots 1–5, Save/Set Active/Load Template sichtbar; NPC-Palette mit Warrior/Archer/Pawn/Tnt/Torch
und fünf Farben. Sichtbare Beispielkarte: 8 Gebäude, 51 NPCs. Keine Karte gespeichert
oder gelöscht. Konsole zeigte Spritesheet-Verarbeitungsfehler: Asset-Parität muss Fehler
aufklären, nicht die Referenz als fehlerfrei voraussetzen.

## 6. Nachweisgrenzen

Quellcodebelege stammen aus lesender Analyse; Browserbelege aus der tatsächlich laufenden
Referenz. Eine sichtbare Save-Schaltfläche beweist noch keinen erfolgreichen Save-Roundtrip.
REA-Status, Notebook-Konflikte und Audionachweise stehen im [Evidenzregister](TWIN_CITY_EVIDENCE.md).
Das aktuelle Produkt wurde hier weder geändert noch neu ausgeliefert.
