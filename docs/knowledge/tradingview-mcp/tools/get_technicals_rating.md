---
tool: get_technicals_rating
group: screener
server: tv-mcp
access: read-only
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `get_technicals_rating`

Screener · nur lesend

Liefert eine vollständige Indikator-Momentaufnahme für einen Zeitrahmen.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `symbol` | string | ja | Symbol als `EXCHANGE:TICKER` |
| `interval` | string | nein | `1m 5m 15m 30m 1h 2h 4h 1D 1W 1M`, Standard `1D` |

## Hinweise

- Enthält RSI, Stoch K/D, CCI20, ADX, MACD, Momentum, AO, EMA/SMA 10–200, VWMA, HullMA9 und drei Recommend-Werte (Summary, MA, Other).
- Ältere Chart-Intervalle wie `60` oder `240` nennt die Doku nicht. PR #262 übersetzt sie in `toMcpInterval`.

Allgemeine Regeln: [Index](../README.md)
