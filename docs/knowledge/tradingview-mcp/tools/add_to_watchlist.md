---
tool: add_to_watchlist
group: watchlists
server: mcp-watchlist
access: write
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `add_to_watchlist`

Watchlists · **schreibend**

Fügt Werte zu einer Watchlist hinzu.

**Vor dem Aufruf:** Ändert das TradingView-Konto des Nutzers, also nur nach ausdrücklicher Freigabe ausführen.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `watchlist_id` | string | ja | Numerische Watchlist-ID |
| `symbols` | string[] | ja | Werte im Format `EXCHANGE:TICKER` |

## Hinweise

- Ein bereits enthaltener Wert rückt ans Ende der Liste.

Allgemeine Regeln: [Index](../README.md)
