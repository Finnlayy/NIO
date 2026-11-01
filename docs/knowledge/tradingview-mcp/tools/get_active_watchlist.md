---
tool: get_active_watchlist
group: watchlists
server: mcp-watchlist
access: read-only
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `get_active_watchlist`

Watchlists · nur lesend

Liefert die aktive Watchlist samt Werten.

## Parameter

Keine.

## Hinweise

- Trotz „read-only“ mit Nebenwirkung: Ist keine Liste aktiv, wird die erste eigene aktiviert. Gibt es gar keine, legt der Server eine Standardliste an.

Allgemeine Regeln: [Index](../README.md)
