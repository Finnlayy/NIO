---
tool: remove_from_watchlist
group: watchlists
server: mcp-watchlist
access: write
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `remove_from_watchlist`

Watchlists · **schreibend**

Entfernt Werte aus einer Watchlist.

**Vor dem Aufruf:** Ändert das TradingView-Konto des Nutzers, also nur nach ausdrücklicher Freigabe ausführen.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `watchlist_id` | string | ja | Numerische Watchlist-ID |
| `symbols` | string[] | ja | Werte im Format `EXCHANGE:TICKER` |

Allgemeine Regeln: [Index](../README.md)
