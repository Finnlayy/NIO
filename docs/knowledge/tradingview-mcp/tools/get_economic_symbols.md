---
tool: get_economic_symbols
group: market-data
server: tv-mcp
access: read-only
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `get_economic_symbols`

Marktdaten · nur lesend

Katalog der Ticker für `get_economic_data`.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `country` | string | nein | Zweistelliger Code wie `US`, `DE`, `EU`, `CN`; liefert fertige Ticker |
| `category` | string | nein | `gdp lbr prce hlth mny trd gov bsnss cnsm hse txs enrg clmt` |
| `search` | string | nein | Teilstring in Code oder Name |

## Hinweise

- Ohne Argumente kommt eine Übersicht mit Kategorien und allen Ländercodes.

Allgemeine Regeln: [Index](../README.md)
