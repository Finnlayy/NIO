---
tool: get_earnings_calendar
group: calendars
server: tv-mcp
access: read-only
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `get_earnings_calendar`

Kalender · nur lesend

Zeigt die nächsten Earnings-Termine für eine Symbol-Liste.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `symbols` | string[] | ja | Werte im Format `EXCHANGE:TICKER` |
| `date_from` | string | nein | `YYYY-MM-DD` oder RFC3339, Standard heute |
| `date_to` | string | nein | `YYYY-MM-DD` oder RFC3339, Standard +180 Tage |

## Hinweise

- Keine Historie: pro Symbol nur nächster und letzter Termin, dazu der Konsens fürs nächste Quartal. Ein Datumsfenster filtert nur diese beiden Termine.
- Für Vergangenes `get_financial_history` oder `get_documents` nutzen.

Allgemeine Regeln: [Index](../README.md)
