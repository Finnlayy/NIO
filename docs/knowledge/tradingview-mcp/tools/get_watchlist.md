---
tool: get_watchlist
group: watchlists
server: mcp-watchlist
access: read-only
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `get_watchlist`

Watchlists · nur lesend

Liefert eine Watchlist samt Werten über ihre ID.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `watchlist_id` | string | ja | Numerische Watchlist-ID |

## Hinweise

- Findet auch öffentlich geteilte Listen anderer Nutzer. Die kommen mit `read_only=true` und lassen sich nicht ändern.

Allgemeine Regeln: [Index](../README.md)
