"""Kraken Symbol Index und Extractor für die Signal-Erkennung.

Ruft Asset-Paare synchron über asyncio.to_thread via urllib.request ab.
Fällt auf lokalen Cache / Hardcoded Liste zurück.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.atomic import atomic_write_bytes
from core.protocol import utc_now_iso

__all__ = ["SymbolIndex"]

logger = logging.getLogger(__name__)

KRAKEN_PAIRS_URL = "https://api.kraken.com/0/public/AssetPairs"

FALLBACK_BASES = {
    "BTC",
    "XBT",
    "ETH",
    "SOL",
    "XRP",
    "USDT",
    "USDC",
    "ADA",
    "DOGE",
    "AVAX",
    "DOT",
    "LINK",
    "PEPE",
    "SHIB",
    "WIF",
    "LTC",
    "BCH",
    "UNI",
    "ATOM",
    "NEAR",
    "FIL",
    "ARB",
    "OP",
    "INJ",
    "SUI",
    "SEI",
    "TIA",
    "JUP",
    "RENDER",
    "FET",
    "AAVE",
    "MKR",
    "ENA",
    "ONDO",
    "TRX",
    "TON",
    "XLM",
    "ALGO",
    "VET",
    "ICP",
    "APT",
    "IMX",
    "LDO",
    "CRV",
    "SNX",
    "ENS",
    "MANA",
    "SAND",
    "AXS",
    "EGLD",
    "XTZ",
    "EOS",
    "KAVA",
    "ROSE",
    "MINA",
    "DYDX",
    "STRK",
    "BONK",
    "FLOKI",
    "JASMY",
    "TAO",
    "POL",
    "WLD",
    "ORDI",
    "SATS",
    "RNDR",
}

FALLBACK_QUOTES = {"USD", "EUR", "USDT", "USDC", "XBT", "BTC", "GBP", "CAD", "AUD", "CHF", "JPY", "ETH"}

# Ticker, die auch normale (englische) Woerter sind. Klein geschrieben im Fliesstext
# sind sie fast nie gemeint: nur in GROSSSCHRIFT ("OP") oder mit $ ("$op") zaehlen sie.
FALSE_POSITIVES_LOWER = {
    "op",
    "near",
    "one",
    "ton",
    "sun",
    "ai",
    "link",
    "dot",
    "uni",
    "sand",
    "atom",
    "ape",
    "gas",
    "flow",
    "rare",
    "band",
    "mask",
    "pol",
    "sats",
    "fet",
    "jup",
    "ens",
    "bonk",
    "eos",
    "rose",
    "mina",
    "ankr",
    "gal",
    "beam",
    "zeus",
    "ride",
    "super",
}

CACHE_TTL_S = 86400.0
# Nach einem Fehlschlag (Cache/Fallback) frueher erneut live versuchen.
RETRY_TTL_S = 900.0

_PAIR_RE = re.compile(r"\b([A-Z0-9]{2,12})[/\-]([A-Z0-9]{2,12})\b", re.IGNORECASE)


def _default_fetcher(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "NIO/1.0"})
    with urllib.request.urlopen(req, timeout=30.0) as response:
        payload: dict[str, Any] = json.loads(response.read())
        return payload


class SymbolIndex:
    """Kraken-Basiswerte fuer die Symbol-Erkennung in Feed-Texten.

    ``ensure()``: live (AssetPairs) -> Cache-Datei -> eingebaute Liste.
    ``extract()``: erst Paarformate (BASE/QUOTE, BASE-QUOTE), dann der laengste
    bekannte Ticker als ganzes Wort; XBT wird als BTC gemeldet.
    """

    def __init__(
        self,
        cache_path: Path,
        fetcher: Callable[[str], dict[str, Any]] = _default_fetcher,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cache_path = cache_path
        self._fetcher = fetcher
        self._clock = clock
        self.bases: set[str] = set()
        self.quotes: set[str] = set()
        self.source = "none"
        self.loaded_at: str | None = None
        self._next_refresh: float | None = None
        self._lock = asyncio.Lock()
        self._base_re: re.Pattern[str] | None = None
        self._base_re_key: frozenset[str] = frozenset()

    @staticmethod
    def _parse_payload(payload: dict[str, Any]) -> tuple[set[str], set[str]]:
        if payload.get("error"):
            raise ValueError(f"Kraken-Fehler: {payload['error']}")
        bases: set[str] = set()
        quotes: set[str] = set()
        for key, info in (payload.get("result") or {}).items():
            wsname = info.get("wsname")
            if not wsname or info.get("status") not in ("online", None):
                continue
            if key.endswith(".d") or wsname.endswith(".d"):
                continue
            parts = wsname.split("/")
            if len(parts) == 2:
                bases.add(parts[0].upper())
                quotes.add(parts[1].upper())
        if not bases:
            raise ValueError("Keine Basiswerte im Kraken-Payload")
        if "XBT" in bases:
            bases.add("BTC")
        if "XBT" in quotes:
            quotes.add("BTC")
        return bases, quotes

    def _apply(self, bases: set[str], quotes: set[str], source: str, loaded_at: str, ttl: float) -> None:
        self.bases = bases
        self.quotes = quotes
        self.source = source
        self.loaded_at = loaded_at
        self._next_refresh = self._clock() + ttl

    async def ensure(self) -> None:
        async with self._lock:
            if self._next_refresh is not None and self._clock() < self._next_refresh:
                return

            try:
                payload = await asyncio.to_thread(self._fetcher, KRAKEN_PAIRS_URL)
                bases, quotes = self._parse_payload(payload)
            except Exception as exc:
                logger.warning("Kraken-Paare nicht live ladbar (%s): %s", type(exc).__name__, exc)
            else:
                now = utc_now_iso()
                self._apply(bases, quotes, "live", now, CACHE_TTL_S)
                data = json.dumps({"payload": payload, "ts": now}, separators=(",", ":")).encode("utf-8")
                try:
                    await asyncio.to_thread(atomic_write_bytes, self.cache_path, data)
                except OSError as exc:
                    logger.warning("Symbol-Cache nicht schreibbar: %s", exc)
                return

            try:
                cached = json.loads(self.cache_path.read_text(encoding="utf-8"))
                bases, quotes = self._parse_payload(cached["payload"])
            except FileNotFoundError:
                pass
            except Exception as exc:
                logger.warning("Symbol-Cache unlesbar (%s)", type(exc).__name__)
            else:
                self._apply(bases, quotes, "cache", str(cached.get("ts") or utc_now_iso()), RETRY_TTL_S)
                return

            self._apply(set(FALLBACK_BASES), set(FALLBACK_QUOTES), "fallback", utc_now_iso(), RETRY_TTL_S)

    def status(self) -> dict[str, Any]:
        return {
            "count": len(self.bases),
            "source": self.source,
            "loaded_at": self.loaded_at,
            "quotes_count": len(self.quotes),
        }

    def _base_pattern(self) -> re.Pattern[str] | None:
        key = frozenset(b for b in self.bases if len(b) >= 2)
        if not key:
            return None
        if self._base_re is None or key != self._base_re_key:
            alternation = "|".join(re.escape(b) for b in sorted(key, key=len, reverse=True))
            self._base_re = re.compile(rf"(?<![A-Za-z0-9])(\$?)({alternation})(?![A-Za-z0-9])", re.IGNORECASE)
            self._base_re_key = key
        return self._base_re

    def extract(self, text: str) -> str | None:
        if not self.bases:
            return None

        for match in _PAIR_RE.finditer(text):
            base, quote = match.group(1).upper(), match.group(2).upper()
            if base in self.bases and quote in self.quotes and len(base) >= 2:
                return "BTC" if base == "XBT" else base

        pattern = self._base_pattern()
        if pattern is None:
            return None
        # Laengster Treffer gewinnt (PEPE vor PE); bei gleicher Laenge der erste im Text.
        best: str | None = None
        for match in pattern.finditer(text):
            dollar, orig = match.group(1), match.group(2)
            base = orig.upper()
            if base.lower() in FALSE_POSITIVES_LOWER and not dollar and orig != base:
                continue
            if best is None or len(base) > len(best):
                best = base
        if best is None:
            return None
        return "BTC" if best == "XBT" else best
