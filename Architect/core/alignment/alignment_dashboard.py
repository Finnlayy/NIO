"""Alignment dashboard — headless data service (Phase 5 — Self-Model & Insights).

Persists alignment snapshots per plan and aggregates them over time. The PyQt6
tab (`gui/views/alignment_dashboard.py`) is a thin shell over this module.

Storage: `Architect/runtime/alignment/<plan_id>_<timestamp>.json`
"""

import json
import logging
import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class AlignmentDashboard:
    """Save / load / aggregate alignment metrics for plans."""

    def __init__(self, alignment_dir: str = "Architect/runtime/alignment", event_bus=None):
        self.alignment_dir = Path(alignment_dir)
        self.alignment_dir.mkdir(parents=True, exist_ok=True)
        self.event_bus = event_bus

    def save_metrics(self, plan_id: str, alignment_result: dict) -> Path:
        """Persist one alignment snapshot (`<plan_id>_<timestamp>.json`)."""
        result = dict(alignment_result)
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
        result.setdefault("plan_id", plan_id)
        result.setdefault("saved_at", datetime.datetime.utcnow().isoformat() + "Z")
        path = self.alignment_dir / f"{plan_id}_{timestamp}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        if self.event_bus:
            self.event_bus.emit(self.event_bus.build_event(
                event_kind="alignment_updated",
                job_id=plan_id,
                message=f"Alignment updated for {plan_id}: score={result.get('alignment_score')}.",
                plan_id=plan_id,
                alignment_score=result.get("alignment_score"),
            ))
        logger.info("Alignment metrics saved: %s", path)
        return path

    def load_metrics(self, plan_id: str) -> list:
        """All snapshots for a plan, oldest first."""
        snapshots = []
        for path in sorted(self.alignment_dir.glob(f"{plan_id}_*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    snapshots.append(json.load(f))
            except Exception as exc:
                logger.error("Failed to load alignment snapshot %s: %s", path, exc)
        return snapshots

    def latest(self, plan_id: str) -> dict:
        """Most recent snapshot for a plan (empty dict if none)."""
        snapshots = self.load_metrics(plan_id)
        return snapshots[-1] if snapshots else {}

    def aggregate_metrics(self, plan_id: str) -> dict:
        """Time-series summary: score history plus min/max/mean per metric."""
        snapshots = self.load_metrics(plan_id)
        if not snapshots:
            return {"plan_id": plan_id, "snapshot_count": 0, "history": []}

        def series(key):
            return [round(float(s.get(key, 0.0)), 4) for s in snapshots if s.get(key) is not None]

        def stats(values):
            if not values:
                return None
            return {
                "min": min(values),
                "max": max(values),
                "mean": round(sum(values) / len(values), 4),
            }

        return {
            "plan_id": plan_id,
            "snapshot_count": len(snapshots),
            "history": [
                {
                    "saved_at": s.get("saved_at"),
                    "alignment_score": s.get("alignment_score"),
                    "safety_score": s.get("safety_score"),
                    "learning_efficiency": s.get("learning_efficiency"),
                }
                for s in snapshots
            ],
            "alignment_score_stats": stats(series("alignment_score")),
            "safety_score_stats": stats(series("safety_score")),
            "learning_efficiency_stats": stats(series("learning_efficiency")),
        }
