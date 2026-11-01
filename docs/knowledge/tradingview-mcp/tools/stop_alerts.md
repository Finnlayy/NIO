---
tool: stop_alerts
group: alerts
server: tv-mcp
access: write
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `stop_alerts`

Alerts · **schreibend**

Pausiert Alerts, ohne sie zu löschen.

**Vor dem Aufruf:** Ändert das TradingView-Konto des Nutzers, also nur nach ausdrücklicher Freigabe ausführen.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `alert_ids` | integer[] | ja | Alert-IDs |

## Hinweise

- ID, Historie und Einstellungen bleiben erhalten.

Allgemeine Regeln: [Index](../README.md)
