---
tool: run_screener
group: screener
server: tv-mcp
access: read-only
source: https://www.tradingview.com/mcp/docs
checked: 2026-10-31
---

# `run_screener`

Screener · nur lesend

Führt den TradingView-Screener mit Filtern, Sortierung und Presets aus.

## Parameter

| Name | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `market` | string | nein | Standard `america`; u. a. `crypto forex futures bonds cfd uk germany india japan` |
| `filters` | object | nein | `{Feld: [min, max]}`, `null` = offen; dazu `index`, `sector`, `industry`, `analyst_rating` |
| `sort_by` | string | nein | Standard `volume` |
| `sort_order` | string | nein | `asc` oder `desc`, Standard `desc` |
| `limit` | integer | nein | Standard 100, max. 1000 |
| `columns` | string[] | nein | Rückgabespalten |
| `symbol_types` | string[] | nein | z. B. `["stock"]` |
| `filter_preset` | string | nein | `pullback_with_reversal breakout_with_volume oversold_healthy earnings_runup relative_strength new_highs` |
| `symbolset` | string[] | nein | Festes Universum, z. B. `["SYML:SP;SPX"]` |

## Hinweise

- Antwort enthält Zeilen und `totalCount`.

Allgemeine Regeln: [Index](../README.md)
