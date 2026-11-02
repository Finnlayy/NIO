---
tool: get_symbol_data
group: screener
server: tv-mcp
access: read-only
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `get_symbol_data`

Screener · nur lesend

Holt beliebige Screener-Spalten für ein Symbol.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `symbol` | string | ja | Symbol als `EXCHANGE:TICKER` |
| `columns` | string[] | nein | Spalten; Standard: `name description close change change_abs volume market_cap_basic price_earnings_ttm sector industry` |

## Hinweise

- Gilt für Aktien, ETFs, Krypto, Forex, Futures, Indizes, Anleihen und Staatsanleihen-Renditen.
- Gültige Spalten liefert `get_screener_columns`.

Allgemeine Regeln: [Index](../README.md)
