---
tool: get_economic_data
group: market-data
server: tv-mcp
access: read-only
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `get_economic_data`

Marktdaten · nur lesend

Liefert die Zeitreihe eines Wirtschaftsindikators.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `symbol` | string | ja | `ECONOMICS:<LAND><INDIKATOR>`, z. B. `ECONOMICS:USIRYY` |
| `date_from` | string | nein | ISO-Datum, Beginn inklusive |
| `date_to` | string | nein | ISO-Datum, Ende inklusive |

## Hinweise

- Ticker nicht raten, sondern mit `get_economic_symbols` ermitteln.
- Antwort: `{date, value}` mit dem tatsächlich veröffentlichten Wert, dazu Einheit und Skala, wenn vorhanden.

Allgemeine Regeln: [Index](../README.md)
