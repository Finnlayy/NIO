---
tool: get_alerts
group: alerts
server: tv-mcp
access: read-only
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `get_alerts`

Alerts · nur lesend

Liefert den vollständigen Inhalt bestimmter Alerts.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `alert_ids` | integer[] | ja | Alert-IDs |

## Hinweise

- Nötig, bevor ein Alert mit geänderter Bedingung neu angelegt wird.
- Nachricht und Webhook-URL werden herausgefiltert, es kommt nur `has_webhook`.

Allgemeine Regeln: [Index](../README.md)
