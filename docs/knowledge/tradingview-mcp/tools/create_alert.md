---
tool: create_alert
group: alerts
server: tv-mcp
access: write
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `create_alert`

Alerts · **schreibend**

Legt einen Alert mit einfacher Preisbedingung an.

**Vor dem Aufruf:** Ändert das TradingView-Konto des Nutzers, also nur nach ausdrücklicher Freigabe ausführen.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `symbol` | string | ja | Symbol als `EXCHANGE:TICKER` |
| `price` | number | nein | Preisschwelle |
| `condition` | string | nein | `cross cross_up cross_down greater less`, Standard `cross` |
| `conditions` | object[] | nein | Rohbedingung, überschreibt `price`/`condition`; nur eine einzelne Preisbedingung |
| `message` | string | nein | Max. 4000 Zeichen |
| `name` | string | nein | Max. 300 Zeichen |
| `resolution` | string | nein | Auswertungs-Zeitrahmen wie `1`, `60`, `1D`; Standard `1` |
| `expiration` | string | nein | ISO, Standard +30 Tage |
| `auto_deactivate` | boolean | nein | Nach erstem Auslösen aus, Standard `false` |
| `email` | boolean | nein | Standard `false` |
| `mobile_push` | boolean | nein | Standard `true` |
| `popup` | boolean | nein | Standard `true` |

## Hinweise

- Mehrfach- und Indikator-Bedingungen werden abgelehnt.
- Webhook-Alerts sind über MCP nicht möglich, weil die dafür nötige 2FA-Prüfung fehlt.
- `alert_id` speichern. Der Start läuft asynchron (`status="starting"`), den echten Zustand mit `get_alerts` oder `list_alerts` prüfen.

Allgemeine Regeln: [Index](../README.md)
