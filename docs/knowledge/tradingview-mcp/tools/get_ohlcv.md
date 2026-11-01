---
tool: get_ohlcv
group: market-data
server: tv-mcp
access: read-only
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `get_ohlcv`

Marktdaten · nur lesend

Liefert historische OHLCV-Kerzen und eine Zusammenfassung.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `symbol` | string | ja | Symbol als `EXCHANGE:TICKER` |
| `interval` | string | nein | `1m 5m 15m 30m 1h 4h 1D 1W M`, Standard `1D`; Monat auch `1mo`/`month` |
| `count` | integer | nein | Anzahl Kerzen, Standard 300, max. 5000 |
| `summary` | boolean | nein | `true` lässt die Rohkerzen weg |

## Hinweise

- Kerzen kommen als `{t, o, h, l, c, v}`, `t` in Unix-Sekunden UTC.
- `2h` steht hier nicht in der Liste, bei `get_technicals_rating` schon.

Allgemeine Regeln: [Index](../README.md)
