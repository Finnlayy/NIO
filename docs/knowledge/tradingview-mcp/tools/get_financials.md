---
tool: get_financials
group: fundamentals
server: tv-mcp
access: read-only
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `get_financials`

Fundamentaldaten & Prognosen · nur lesend

Liefert eine aktuelle Fundamental-Momentaufnahme.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `symbol` | string | ja | Symbol als `EXCHANGE:TICKER` |
| `metric` | string[] | nein | Teilmenge, Aliase wie `pe roe revenue fcf` oder TV-Spalten |
| `period` | string | nein | `fy fq ttm fh current`, Standard `ttm` |

## Hinweise

- Enthält u. a. KGV, KBV, Margen, ROE/ROA, TTM-Werte und YoY-Wachstum.

Allgemeine Regeln: [Index](../README.md)
