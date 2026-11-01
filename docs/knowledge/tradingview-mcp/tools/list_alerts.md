---
tool: list_alerts
group: alerts
server: tv-mcp
access: read-only
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `list_alerts`

Alerts · nur lesend

Listet alle Alerts, aktive und inaktive.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `symbol` | string | nein | Filter im Format `EXCHANGE:TICKER` |
| `active` | boolean | nein | Filter nach Zustand |

Allgemeine Regeln: [Index](../README.md)
