---
tool: get_dividends_calendar
group: calendars
server: tv-mcp
access: read-only
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `get_dividends_calendar`

Kalender · nur lesend

Liefert Dividendendaten pro Symbol oder per Marktscreening.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `symbols` | string[] | nein | Pro-Symbol-Modus |
| `market` | string | nein | Screening-Modus, z. B. `america` |
| `date_from` | string | nein | Ex-Tag-Fenster, Standard jetzt |
| `date_to` | string | nein | Ex-Tag-Fenster, Standard +30 Tage |
| `limit` | integer | nein | Screening-Modus, Standard 50, max. 200 |

## Hinweise

- Enthält Ex-Tage, Betrag, Rendite und Zahltag.

Allgemeine Regeln: [Index](../README.md)
