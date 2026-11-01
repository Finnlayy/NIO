---
tool: search_symbols
group: symbol-search
server: tv-mcp
access: read-only
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `search_symbols`

Symbolsuche · nur lesend

Löst Ticker oder Firmennamen per unscharfer Suche in `EXCHANGE:TICKER` auf.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `query` | string | ja | Ticker, Firmenname oder Beschreibung |
| `type_filter` | string | nein | `stock etf bond forex index futures crypto`, Standard alle |

## Hinweise

- Erster Schritt, wenn die Börse eines Werts nicht sicher bekannt ist.

Allgemeine Regeln: [Index](../README.md)
