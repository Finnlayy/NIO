---
tool: get_alerts_log
group: alerts
server: tv-mcp
access: read-only
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `get_alerts_log`

Alerts · nur lesend

Liefert die Auslöse-Historie der Alerts.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `days` | integer | nein | Rückblick in Tagen, Standard 7 |
| `symbol` | string | nein | Filter im Format `EXCHANGE:TICKER` |
| `limit` | integer | nein | Standard 100, max. 2000 |

Allgemeine Regeln: [Index](../README.md)
