---
tool: restart_alerts
group: alerts
server: tv-mcp
access: write
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `restart_alerts`

Alerts · **schreibend**

Setzt pausierte Alerts fort.

**Vor dem Aufruf:** Ändert das TradingView-Konto des Nutzers, also nur nach ausdrücklicher Freigabe ausführen.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `alert_ids` | integer[] | ja | Alert-IDs |

Allgemeine Regeln: [Index](../README.md)
