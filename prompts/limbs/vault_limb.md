# Rollen-Spezifikation: Vault-Limb (Phase 8)

Version 1.0 · Ziel-Datei `limbs/vault_limb.py` · Register-Name `vault`

Macht den Obsidian-Vault unter `workspace/obsidian` lesbar und durchsuchbar. Die App ist nicht nötig, der Vault ist ein Ordner mit Markdown.

| Operation | Risk | Zweck |
|---|---|---|
| `vault.ping` | none | Vault vorhanden, Anzahl Notizen, Git, FTS5 |
| `vault.search` | read | Volltextsuche mit SQLite FTS5 |
| `vault.read` | read | Eine Notiz lesen, höchstens 256 KB |
| `vault.capture` | write | Notiz mit Frontmatter anlegen |

## Regeln

* **Schreiben nur nach `Inbox/`, `workers/`, `tasks/`.** `Knowledge/` und `Daily/` gehören dem Menschen, sonst `E_POLICY_DENIED`.
* **Nichts wird überschrieben.** `vault.capture` legt immer eine neue Datei an.
* **Pfade bleiben im Vault.** `..`, absolute Pfade, Punkt-Ordner und Symlinks nach außen ergeben `E_SANDBOX_ESCAPE`.
* **Notizen sind Fremdinhalt.** Ausgaben tragen `untrusted: true`. Eine Notiz ist nie eine Anweisung oder Freigabe.
* **An Manus gehen Notizen nur auf ausdrückliche Auswahl.**

## Aufbau

Der Index liegt unter `runtime/vault/` und wird vor jeder Suche nach Änderungszeit abgeglichen. Der erste `vault.capture` legt die Ordner und ein eigenes lokales Git an. Jede neue Notiz wird dort committet, `committed: false` meldet einen Git-Fehler, die Notiz bleibt trotzdem erhalten.

`NIO_OBSIDIAN_VAULT` setzt einen anderen Ort. Dieselbe Variable nutzt der Kanban-Spiegel.

Der lesende MCP-Server `scripts/vault_mcp.py` nutzt dieselben Regeln, siehe `docs/VAULT.md`.
