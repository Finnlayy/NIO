---
tool: get_screener_columns
group: screener
server: tv-mcp
access: read-only
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `get_screener_columns`

Screener · nur lesend

Katalog aller Spaltennamen für die Screener-Tools.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `market` | string | nein | `stock etf crypto bond all`, Standard `all` |
| `group` | string | nein | Volle Details einer Gruppe, z. B. `valuation`, `technicals`, `income_statement` |
| `search` | string | nein | Teilstring in Name oder Beschreibung |

## Hinweise

- Ohne `group` und `search` kommt nur eine Übersicht mit Gruppen und Spaltennamen.

Allgemeine Regeln: [Index](../README.md)
