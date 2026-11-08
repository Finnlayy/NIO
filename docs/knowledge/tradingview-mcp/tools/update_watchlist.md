---
tool: update_watchlist
group: watchlists
server: mcp-watchlist
access: write
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `update_watchlist`

Watchlists · **schreibend**

Ändert Name oder Beschreibung einer Watchlist.

**Vor dem Aufruf:** Ändert das TradingView-Konto des Nutzers, also nur nach ausdrücklicher Freigabe ausführen.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `watchlist_id` | string | ja | Numerische Watchlist-ID |
| `name` | string | nein | Neuer Name, max. 500 Zeichen |
| `description` | string | nein | Neue Beschreibung |

## Hinweise

- Mindestens `name` oder `description` muss gesetzt sein.

Allgemeine Regeln: [Index](../README.md)
