---
tool: get_documents
group: documents
server: tv-mcp
access: read-only
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `get_documents`

Dokumente · nur lesend

Listet Filings und Transkripte zu einem Symbol.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `symbol` | string | ja | Symbol als `EXCHANGE:TICKER` |
| `category` | string | nein | `all annual_reports quarterly_reports interim_reports company_events insider_transactions transcripts presentations press_releases other`; auch `10-K 10-Q 8-K` |
| `event` | string | nein | `earning` oder `corporate_event` |
| `start_date` | string | nein | RFC3339, Beginn des Ereignisfensters |
| `end_date` | string | nein | RFC3339, Ende des Ereignisfensters |
| `limit` | integer | nein | Standard 20 |

## Hinweise

- Liefert die `views[].id` für `get_document_view`.

Allgemeine Regeln: [Index](../README.md)
