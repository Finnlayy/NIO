---
tool: update_alert
group: alerts
server: tv-mcp
access: write
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `update_alert`

Alerts · **schreibend**

Ändert Einstellungen eines Alerts und startet ihn neu.

**Vor dem Aufruf:** Ändert das TradingView-Konto des Nutzers, also nur nach ausdrücklicher Freigabe ausführen.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `alert_id` | integer | ja | ID des Alerts |
| `message` | string | nein | Weglassen = unverändert |
| `name` | string | nein | Weglassen = unverändert |
| `expiration` | string | nein | ISO; leerer String entfernt den Ablauf (Premium) |
| `auto_deactivate` | boolean | nein | Weglassen = unverändert |
| `email` | boolean | nein | Weglassen = unverändert |
| `mobile_push` | boolean | nein | Weglassen = unverändert |
| `popup` | boolean | nein | Weglassen = unverändert |

## Hinweise

- Bedingung, Symbol und Zeitrahmen sind nicht änderbar: löschen und neu anlegen.
- Alerts mit Webhook lassen sich nur auf tradingview.com bearbeiten.
- Neustart asynchron, Zustand danach prüfen.

Allgemeine Regeln: [Index](../README.md)
