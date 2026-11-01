---
tool: get_forecasts
group: fundamentals
server: tv-mcp
access: read-only
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `get_forecasts`

Fundamentaldaten & Prognosen · nur lesend

Liefert den Analysten-Konsens.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `symbol` | string | ja | Symbol als `EXCHANGE:TICKER` |

## Hinweise

- Enthält Empfehlung mit Score, Buy/Hold/Sell-Verteilung, Kursziele mit `upside_pct` sowie EPS- und Umsatzschätzungen.

Allgemeine Regeln: [Index](../README.md)
