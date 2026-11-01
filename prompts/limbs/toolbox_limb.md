# Rollen-Spezifikation: Toolbox-Limb (Phase 6)

Version 1.0 · Ziel-Datei `limbs/toolbox_limb.py` · Register-Name `toolbox`

Die Werkzeugkiste, die Agenten mitziehen. Statt jedes Tool im Kontextfenster zu
tragen, kennt ein Agent nur diesen Limb und lädt ein Werkzeug erst, wenn er es braucht.

| Operation | Risk | Zweck |
|---|---|---|
| `toolbox.ping` | none | Anzahl der Werkzeuge je Quelle |
| `toolbox.search` | read | Suche; eine Kurzzeile pro Treffer |
| `toolbox.describe` | read | Volle Beschreibung genau eines Werkzeugs |

## Ablauf

1. `toolbox.search` mit Suchwörtern aufrufen, z. B. `{"query": "earnings"}`.
2. Für das passende Werkzeug `toolbox.describe` mit `{"tool": "<name>"}` aufrufen.
3. Das Werkzeug über den Limb oder MCP-Server ausführen, dem es gehört.

## Katalog

Der Katalog entsteht bei jedem Aufruf neu und driftet deshalb nicht:

* `protocol/operations.json` für alle NEU-Operationen
* `docs/knowledge/<paket>/tools/*.md` für externe Tools

Ein neues Leaf mit Frontmatter (`tool`, `group`, `access`) genügt, Code ist nicht nötig.

## Grenzen

* **Die Kiste führt nichts aus.** Sie liest nur, braucht kein Netz und keine Zugangsdaten.
* **`access: write` heißt Freigabe einholen**, bevor das Werkzeug aufgerufen wird.
* **Toolnamen prüfen:** Ein Leaf nennt den Namen aus der Doku. Der Name auf dem Server
  kann abweichen, siehe `docs/knowledge/tradingview-mcp/README.md`.
