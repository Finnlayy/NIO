---
tool: get_financial_history
group: fundamentals
server: tv-mcp
access: read-only
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `get_financial_history`

Fundamentaldaten & Prognosen · nur lesend

Liefert die Quartals- oder Jahreshistorie der Fundamentaldaten.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `symbol` | string | ja | Symbol als `EXCHANGE:TICKER` |
| `period` | string | nein | `fq` oder `fy`, Standard `fq` |
| `date_from` | string | nein | ISO-Datum, Beginn |
| `date_to` | string | nein | ISO-Datum, Ende |

## Hinweise

- Richtige Quelle für berichtete Zahlen vergangener Quartale, nicht `get_earnings_calendar`.

Allgemeine Regeln: [Index](../README.md)
