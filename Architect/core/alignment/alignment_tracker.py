"""Alignment tracking (Phase 5 — Self-Model & Insights).

Computes how well the system's behavior agrees with human preferences and
safety invariants, plus how fast it is improving.

Formula (documented in Architect/docs/PHASES.md and docs/ARCHITECTURE.md):

    alignment_score = 0.5 * feedback_preference_ratio
                    + 0.3 * risk_guard_pass_rate
                    + 0.2 * learning_efficiency

    safety_score     = share of risk guard assessments (and executions) fully passed
    learning_efficiency = slope of the quality metric over the trajectory window,
                          mapped through clamp01(0.5 + k * slope); error-style
                          metrics are inverted.
"""

import logging
import datetime

logger = logging.getLogger(__name__)

ALIGNMENT_WEIGHTS = {
    "feedback_preference_ratio": 0.5,
    "risk_guard_pass_rate": 0.3,
    "learning_efficiency": 0.2,
}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


class AlignmentTracker:
    """Compute alignment / safety / learning-efficiency metrics."""

    # ---- Safety -------------------------------------------------------------

    def compute_safety_score(self, risk_guards: list, execution_results: list = None) -> float:
        """Share of risk guard assessments passed (in [0, 1]).

        When `execution_results` are provided they must *also* pass (all
        invariants ok) for an execution to count as safe; the score is the
        ratio of clean executions over all evaluated items.
        """
        assessments = [g for g in (risk_guards or []) if isinstance(g, dict)]
        executions = [e for e in (execution_results or []) if isinstance(e, dict)]
        total = len(assessments) + len(executions)
        if total == 0:
            return 0.0
        clean = sum(1 for g in assessments if g.get("passed") is True)
        for result in executions:
            verdict_ok = result.get("verdict") in ("accept",)
            no_errors = not (result.get("errors") or [])
            if verdict_ok and no_errors:
                clean += 1
        return _clamp01(clean / total)

    # ---- Learning efficiency --------------------------------------------------

    def compute_learning_efficiency(self, trajectory_points: list, metric_key: str = None) -> float:
        """Improvement rate over time in [-0..1] via normalized metric slope.

        - Uses `metrics[metric_key]` (default: `success_rate`, falling back to
          `1 - error_rate` when only `error_rate` is recorded).
        - Slope is a least-squares fit over normalized time (first point = 0,
          last point = 1) so point spacing does not distort the rate.
        - efficiency = clamp01(0.5 + 5 * slope) for quality metrics (flat = 0.5
          neutral); error metrics are inverted (declining error rate raises
          efficiency).
        - Fewer than 2 usable points -> 0.0 (no evidence of improvement).
        """
        points = trajectory_points or []
        values = []
        resolved_key = None
        for point in points:
            metrics = getattr(point, "metrics", None) or (point.get("metrics") if isinstance(point, dict) else None)
            if not metrics:
                continue
            key = metric_key or self._default_metric_key(metrics)
            if resolved_key is None:
                resolved_key = key
            if key not in metrics or metrics[key] is None:
                continue
            try:
                values.append(float(metrics[key]))
            except (TypeError, ValueError):
                continue
        if len(values) < 2:
            return 0.0

        n = len(values)
        # Normalized time axis: 0 .. 1 across the observed window.
        xs = [i / (n - 1) for i in range(n)]
        mean_x = sum(xs) / n
        mean_y = sum(values) / n
        denom = sum((x - mean_x) ** 2 for x in xs)
        if denom == 0:
            return 0.0
        slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values)) / denom

        # Error-style metrics are inverted (a *declining* error rate improves).
        effective_key = metric_key or resolved_key or ""
        if "error" in effective_key:
            slope = -slope
        return _clamp01(0.5 + 5.0 * slope)

    @staticmethod
    def _default_metric_key(metrics: dict) -> str:
        if "success_rate" in metrics:
            return "success_rate"
        if "error_rate" in metrics:
            return "error_rate"
        if "quality" in metrics:
            return "quality"
        return next(iter(metrics), "")

    # ---- Feedback -------------------------------------------------------------

    @staticmethod
    def _preference_ratio(feedback_aggregates) -> float:
        """Preference ratio from feedback aggregates; falls back to normalized rating."""
        aggregates = [a for a in (feedback_aggregates or []) if isinstance(a, dict)]
        if not aggregates:
            return 0.0
        ratios = [a.get("preference_ratio") for a in aggregates if a.get("preference_ratio") is not None]
        if ratios:
            return _clamp01(sum(ratios) / len(ratios))
        normalized = [a.get("average_rating_normalized") for a in aggregates
                      if a.get("average_rating_normalized") is not None]
        if normalized:
            return _clamp01(sum(normalized) / len(normalized))
        return 0.0

    # ---- Composite ---------------------------------------------------------------

    def compute_alignment_score(self, trajectory_points: list, feedback_aggregates: list,
                                risk_guards: list) -> dict:
        """Compute the composite alignment score (see module docstring for formula)."""
        preference_ratio = self._preference_ratio(feedback_aggregates)
        guard_rate = _clamp01(risk_guards.get("pass_rate", 0.0)) if isinstance(risk_guards, dict) \
            else self.compute_safety_score(risk_guards)
        learning_efficiency = self.compute_learning_efficiency(trajectory_points)

        alignment_score = (
            ALIGNMENT_WEIGHTS["feedback_preference_ratio"] * preference_ratio
            + ALIGNMENT_WEIGHTS["risk_guard_pass_rate"] * guard_rate
            + ALIGNMENT_WEIGHTS["learning_efficiency"] * learning_efficiency
        )
        result = {
            "alignment_score": round(alignment_score, 4),
            "components": {
                "feedback_preference_ratio": round(preference_ratio, 4),
                "risk_guard_pass_rate": round(guard_rate, 4),
                "learning_efficiency": round(learning_efficiency, 4),
            },
            "weights": dict(ALIGNMENT_WEIGHTS),
            "trajectory_points": len(trajectory_points or []),
            "computed_at": datetime.datetime.utcnow().isoformat() + "Z",
        }
        logger.info("Alignment computed: score=%.4f (pref=%.2f guard=%.2f learn=%.2f)",
                    alignment_score, preference_ratio, guard_rate, learning_efficiency)
        return result

    def compute_all(self, trajectory_points: list, feedback_aggregates: list,
                    risk_guards: list, execution_results: list = None) -> dict:
        """Alignment + safety + efficiency in one result dict."""
        result = self.compute_alignment_score(trajectory_points, feedback_aggregates, risk_guards)
        result["safety_score"] = round(self.compute_safety_score(risk_guards, execution_results), 4)
        result["learning_efficiency"] = result["components"]["learning_efficiency"]
        return result
