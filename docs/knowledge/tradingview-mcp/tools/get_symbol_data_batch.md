---
tool: get_symbol_data_batch
group: screener
server: tv-mcp
access: read-only
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `get_symbol_data_batch`

Screener · nur lesend

Holt Kurse oder Spalten für bis zu 50 Symbole in einem Aufruf.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `symbols` | string[] | ja | Bis zu 50 `EXCHANGE:TICKER`, Dubletten werden entfernt |
| `columns` | string[] | nein | Spalten; Standard wie bei `get_symbol_data` |

## Hinweise

- Unbekannte Symbole stehen mit Grund unter `missing`, es gibt keine erfundenen Nullen.
- Backend-Fehler (429/5xx) kommen als `success=false`. Fielen nur einige Märkte aus, kommt `partial=true` mit `warnings`. Solche Symbole sind nicht verfügbar, aber nicht unbekannt.

Allgemeine Regeln: [Index](../README.md)
