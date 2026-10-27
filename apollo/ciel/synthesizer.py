"""Modul D: Macro-Skill Synthesizer.

Loggt erfolgreiche Tool-Ketten (z. B. ``Tool_A -> Tool_B``). Wird dieselbe
Sequenz mindestens 3-mal erfolgreich **hintereinander** ausgeführt, verschmilzt
der Synthesizer sie automatisch zu einem einzigen registrierten
**Makro-FastMCP-Tool**, damit künftige Aufrufe in einem einzigen Turn (oder
per System-1 Bypass) durchlaufen.

Die Makro-Ausführung läuft über :class:`RegistryFunctionExecutor`-Pipelines:
Jeder Schritt erhält die Original-Argumente plus ``previous_result``.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .bus import emit
from .models import MacroSynthesis, ToolSchema
from .registry import ColdStorageRegistry, utc_now_iso

#: Ab wie vielen aufeinanderfolgenden Erfolgen synthetisiert wird.
SYNTHESIS_THRESHOLD = 3

#: Präfix aller synthetisierten Makro-Tools (Namensraum-Trennung).
MACRO_PREFIX = "macro__"

#: Trennzeichen für Ketten-Schlüssel (darf nicht in Tool-Namen vorkommen).
_CHAIN_SEP = ""


class MacroSkillSynthesizer:
    """Beobachtet Tool-Ketten und synthetisiert Makro-Tools (Schwelle: 3)."""

    def __init__(
        self,
        registry: ColdStorageRegistry,
        *,
        threshold: int = SYNTHESIS_THRESHOLD,
        event_bus: Any | None = None,
        persist_path: str | Path | None = None,
    ) -> None:
        self._registry = registry
        self._threshold = max(2, threshold)
        self._bus = event_bus
        self._persist_path = Path(persist_path) if persist_path is not None else None
        self._streaks: dict[str, int] = {}
        if self._persist_path is not None and self._persist_path.is_file():
            self._load()

    @property
    def registry(self) -> ColdStorageRegistry:
        return self._registry

    @property
    def threshold(self) -> int:
        return self._threshold

    @property
    def streaks(self) -> dict[str, int]:
        return dict(self._streaks)

    @staticmethod
    def chain_key(chain: Sequence[str]) -> str:
        return _CHAIN_SEP.join(chain)

    @staticmethod
    def macro_name(chain: Sequence[str]) -> str:
        safe = [seg.strip().replace(" ", "_").replace(".", "_")[:40] or "x" for seg in chain]
        return f"{MACRO_PREFIX}{'__'.join(safe)}"[:120]

    async def log_execution(self, chain: Sequence[str], *, success: bool) -> MacroSynthesis | None:
        """Loggt eine Tool-Kette; gibt bei erreichter Schwelle die Synthese zurück.

        * ``success=True``: Streak der Kette +1. Bei Erreichen der Schwelle und
          noch nicht existierendem Makro → :meth:`synthesize`.
        * ``success=False``: Streak der Kette wird zurückgesetzt (nur
          *hintereinander* erfolgreiche Sequenzen zählen).
        """
        names = [str(step) for step in chain if str(step)]
        if len(names) < 2:
            return None
        key = self.chain_key(names)
        macro = self.macro_name(names)
        if not success:
            self._streaks.pop(key, None)
            self._save()
            return MacroSynthesis(macro_name=macro, chain=names, runs_observed=0, created=False)
        streak = self._streaks.get(key, 0) + 1
        self._streaks[key] = streak
        emit(self._bus, "ciel.synth.chain_observed", {"chain": names, "streak": streak, "threshold": self._threshold})
        self._save()
        if streak >= self._threshold and macro not in self._registry:
            record = await self.synthesize(names)
            return MacroSynthesis(macro_name=record.name, chain=names, runs_observed=streak, created=True)
        return MacroSynthesis(macro_name=macro, chain=names, runs_observed=streak, created=False)

    async def synthesize(self, chain: Sequence[str]) -> ToolSchema:
        """Verschmilzt eine Kette zu einem registrierten Makro-Tool (Pipeline)."""
        names = [str(step) for step in chain if str(step)]
        if len(names) < 2:
            raise ValueError("Makro-Synthese braucht mindestens 2 Tools.")
        missing = [name for name in names if name not in self._registry]
        if missing:
            raise ValueError(f"Makro-Synthese unmöglich, unbekannte Tools: {', '.join(missing)}")
        records = [self._registry.require(name) for name in names]
        properties: dict[str, Any] = {}
        required: list[str] = []
        for record in records:
            params = record.parameters or {}
            props = params.get("properties") if isinstance(params, dict) else None
            if isinstance(props, dict):
                for key, schema in props.items():
                    properties.setdefault(str(key), schema)
            req = params.get("required") if isinstance(params, dict) else None
            if isinstance(req, list):
                for key in req:
                    if str(key) not in required:
                        required.append(str(key))
        # previous_result ist ein Ketten-Artefakt, kein Nutzer-Parameter.
        properties.pop("previous_result", None)
        if "previous_result" in required:
            required.remove("previous_result")
        deterministic = all(r.is_deterministic for r in records)
        timeout = max([r.timeout_sec for r in records] + [30.0]) * len(records)
        state_keys: list[str] = []
        for record in records:
            for key in record.required_state_keys:
                if key not in state_keys:
                    state_keys.append(key)
        macro = self.macro_name(names)
        record = self._registry.register(
            {
                "name": macro,
                "description": f"Macro skill: {' -> '.join(names)}. Auto-synthesized after {self._threshold} consecutive successful runs.",
                "parameters": {"type": "object", "properties": properties, "required": required},
                "meta": {
                    "pipeline": names,
                    "synthesized_at": utc_now_iso(),
                    "synthesis_runs": self._streaks.get(self.chain_key(names), self._threshold),
                },
            },
            origin="macro",
            required_state_keys=state_keys,
            is_deterministic=deterministic,
            timeout_sec=float(timeout),
        )
        emit(self._bus, "ciel.synth.macro_created", {"macro": macro, "chain": names})
        return record

    def reset(self, chain: Sequence[str] | None = None) -> None:
        """Setzt Streaks zurück (eine Kette oder alle)."""
        if chain is None:
            self._streaks.clear()
        else:
            self._streaks.pop(self.chain_key([str(s) for s in chain]), None)
        self._save()

    def _save(self) -> None:
        if self._persist_path is None:
            return
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._persist_path.write_text(json.dumps(self._streaks, sort_keys=True), encoding="utf-8")
        except OSError:
            pass

    def _load(self) -> None:
        assert self._persist_path is not None
        try:
            data = json.loads(self._persist_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if isinstance(data, dict):
            self._streaks = {str(k): int(v) for k, v in data.items() if isinstance(v, int) and v > 0}


__all__ = ["MACRO_PREFIX", "SYNTHESIS_THRESHOLD", "MacroSkillSynthesizer"]
