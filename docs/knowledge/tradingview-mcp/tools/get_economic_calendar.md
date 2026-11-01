---
tool: get_economic_calendar
group: calendars
server: tv-mcp
access: read-only
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `get_economic_calendar`

Kalender · nur lesend

Zeigt Makro-Termine wie CPI, BIP oder Zinsen.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `countries` | string | nein | Kommagetrennte Codes, Standard `US` |
| `currencies` | string | nein | Kommagetrennt, z. B. `USD,JPY,EUR` |
| `category` | string | nein | `gdp bonds business consumer goverment health housing labor money prices trade taxes`, Standard alle |
| `date_from` | string | nein | UTC, Standard heute 00:00 |
| `date_to` | string | nein | UTC, Standard heute 23:59 |
| `min_importance` | integer | nein | -1 alle, 0 mittel+hoch, 1 nur hoch; Standard -1 |

## Hinweise

- Daten seit 2003-09-01, nach vorn etwa 31 Tage.
- `goverment` schreibt die API so.

Allgemeine Regeln: [Index](../README.md)
