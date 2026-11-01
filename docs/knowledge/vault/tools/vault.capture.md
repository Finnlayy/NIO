---
tool: vault.capture
group: vault
server: neu
access: write
checked: 2026-11-01
---

# `vault.capture`

Vault · schreibend

Legt eine neue Notiz mit Frontmatter im Obsidian-Vault an.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `text` | string | ja | Inhalt, höchstens 64 000 Zeichen |
| `title` | string | nein | Titel, sonst der Textanfang |
| `folder` | string | nein | `Inbox` (Standard), `workers/…` oder `tasks/…` |
| `source` | string | nein | Herkunft, z. B. `apollo` oder `agent` |

## Hinweise

- `Knowledge/` bleibt für Agenten gesperrt.
- Bestehende Dateien werden nie überschrieben.

Einrichtung: [VAULT.md](../../../VAULT.md)
