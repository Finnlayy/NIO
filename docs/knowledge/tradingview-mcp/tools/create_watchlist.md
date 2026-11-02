---
tool: create_watchlist
group: watchlists
server: mcp-watchlist
access: write
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `create_watchlist`

Watchlists · **schreibend**

Legt eine neue Watchlist an.

**Vor dem Aufruf:** Ändert das TradingView-Konto des Nutzers, also nur nach ausdrücklicher Freigabe ausführen.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `name` | string | nein | Name, max. 500 Zeichen |
| `symbols` | string[] | nein | Startwerte im Format `EXCHANGE:TICKER` |

Allgemeine Regeln: [Index](../README.md)
