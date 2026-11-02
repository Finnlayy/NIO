---
tool: delete_alert
group: alerts
server: tv-mcp
access: write
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `delete_alert`

Alerts · **schreibend**

Löscht Alerts über ihre IDs.

**Vor dem Aufruf:** Ändert das TradingView-Konto des Nutzers, also nur nach ausdrücklicher Freigabe ausführen.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `alert_ids` | integer[] | ja | Alert-IDs |

## Hinweise

- Die Auslöse-Historie wird mitgelöscht. Zum Pausieren `stop_alerts` nutzen.

Allgemeine Regeln: [Index](../README.md)
