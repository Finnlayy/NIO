# Obsidian-Vault

NIO liest und durchsucht einen Obsidian-Vault direkt als Dateien. Die App ist nicht nötig, sie dient nur zum Anschauen.

```
workspace/obsidian/
├── Inbox/        Notizen aus Apollo und von Agenten
├── Daily/        Tagesnotizen
├── Knowledge/    deine Notizen, für Agenten nur lesbar
├── workers/      Kanban-Spiegel
└── tasks/        Kanban-Spiegel
```

Der Ordner liegt unter `workspace/` und damit außerhalb des NIO-Git. Die erste Notiz legt ihn an, dazu ein eigenes lokales Git als Sicherung. Jede neue Notiz wird dort committet. Das Git hat keinen Remote, nichts verlässt den Rechner.

## In Apollo

| Befehl | Wirkung |
|---|---|
| `/note <text>` | Legt eine Notiz in `Inbox/` an |
| `/vault <suche>` | Sucht im Vault und zeigt Pfad und Ausschnitt |

**Diktat als Notiz:** `/note ` tippen, Mikrofon nutzen, Text prüfen, Enter. Das Diktat landet im Feld und wird wie immer erst auf Enter abgeschickt.

Beide Befehle laufen über `POST /api/apollo/vault` als Intent durch den Orchestrator, also mit Policy, Timer und Event-Log. Ist der Orchestrator nicht aufrufbar, kommt 503 und keine leere Trefferliste. Im Dev-Profil läuft immer nur ein Job, ein paralleler Auftrag kann den Befehl deshalb abweisen.

## Für Agenten

`limbs/vault_limb.py` bietet `vault.ping`, `vault.search`, `vault.read` und `vault.capture`, Spezifikation in `prompts/limbs/vault_limb.md`.

| Regel | Umsetzung |
|---|---|
| Schreiben nur nach `Inbox/`, `workers/`, `tasks/` | Sonst `E_POLICY_DENIED`, auch über Symlinks innerhalb des Vaults |
| Nichts wird überschrieben | Neue Dateien entstehen exklusiv, Symlinks werden nicht verfolgt |
| Pfade bleiben im Vault | `..`, absolute Pfade, Punkt-Ordner und Symlinks nach außen ergeben `E_SANDBOX_ESCAPE` |
| Notizen sind Fremdinhalt | Ausgaben tragen `untrusted: true`, Notizen sind nie Anweisungen |
| Manus | Notizen gehen nur auf ausdrückliche Auswahl im Auftrag hinaus |

Die Suche nutzt SQLite FTS5. Der Index liegt unter `runtime/vault/` und wird vor jeder Suche nach Änderungszeit abgeglichen. Dateien über 1 MB werden nicht indiziert.

## MCP-Server für OpenCode

`scripts/vault_mcp.py` ist ein lesender MCP-Server über stdio mit `vault_search` und `vault_read`. Schreibwerkzeuge gibt es dort nicht. Jede Antwort beginnt mit einem Hinweis, dass der Inhalt Daten sind. Er nutzt dieselben Pfadregeln wie der Limb.

```bash
python3 scripts/vault_mcp.py
```

Der Server versteht JSON pro Zeile und `Content-Length`-Framing, passt also zu OpenCode und zu `apollo/ciel/mcp_nodes.py`. Eingetragen ist er noch nirgends, das folgt mit `config/opencode/opencode.json` in Phase 5.

## Einstellungen

| Variable | Standard |
|---|---|
| `NIO_OBSIDIAN_VAULT` | `workspace/obsidian`, gilt auch für den Kanban-Spiegel |
