"""Self-model engine (Phase 5 — Self-Model & Insights).

Generates structured insights (strengths / weaknesses / recommendations) from
trajectory data, alignment metrics, skill profiles and error patterns — the
system's model of *itself*. Deterministic rule-based generation so insights
are auditable (GenAI enrichment can be layered later via `genai_client`).

Storage: `Architect/runtime/insights/<timestamp>.json`
"""

import json
import logging
import datetime
import hashlib
from pathlib import Path

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


class Insight:
    """A structured, auditable self-model insight."""

    def __init__(self, category: str, content: str, confidence: float = 0.5,
                 related_events: list = None, related_plans: list = None,
                 insight_id: str = None, timestamp: str = None):
        if category not in ("strength", "weakness", "recommendation"):
            raise ValueError(f"Insight category must be strength|weakness|recommendation, got {category!r}")
        self.category = category
        self.content = content
        self.confidence = max(0.0, min(1.0, float(confidence)))
        self.related_events = related_events or []
        self.related_plans = related_plans or []
        self.timestamp = timestamp or _now()
        self.insight_id = insight_id or self._make_id()

    def _make_id(self) -> str:
        digest = hashlib.sha1(f"{self.category}|{self.content}|{self.timestamp}".encode("utf-8")).hexdigest()
        return f"ins_{digest[:12]}"

    def to_dict(self) -> dict:
        return {
            "insight_id": self.insight_id,
            "category": self.category,
            "content": self.content,
            "confidence": round(self.confidence, 4),
            "timestamp": self.timestamp,
            "related_events": self.related_events,
            "related_plans": self.related_plans,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Insight":
        return cls(
            category=data.get("category", "strength"),
            content=data.get("content", ""),
            confidence=data.get("confidence", 0.5),
            related_events=data.get("related_events") or [],
            related_plans=data.get("related_plans") or [],
            insight_id=data.get("insight_id"),
            timestamp=data.get("timestamp"),
        )


class SelfModelEngine:
    """Rule-based insight generation from trajectory + alignment + learning data."""

    def __init__(self, insights_dir: str = "Architect/runtime/insights", event_bus=None):
        self.insights_dir = Path(insights_dir)
        self.insights_dir.mkdir(parents=True, exist_ok=True)
        self.event_bus = event_bus

    # ---- Helpers ----------------------------------------------------------------

    @staticmethod
    def _field(point, name, default=None):
        if isinstance(point, dict):
            return point.get(name, default)
        return getattr(point, name, default)

    def _related_event_ids(self, trajectory_points, limit: int = 5) -> list:
        related = []
        for point in trajectory_points or []:
            related.extend(self._field(point, "event_ids", []) or [])
        return related[:limit]

    def _related_plan_ids(self, trajectory_points, fallback_plan_id=None, limit: int = 3) -> list:
        plans = []
        for point in trajectory_points or []:
            pid = self._field(point, "plan_id")
            if pid and pid not in plans:
                plans.append(pid)
        if fallback_plan_id and fallback_plan_id not in plans:
            plans.append(fallback_plan_id)
        return plans[:limit]

    # ---- Insight generation ---------------------------------------------------------

    def generate_insights(self, trajectory_points: list, alignment_metrics: dict = None,
                          skill_profiles: list = None, error_patterns: list = None,
                          plan_id: str = None) -> list:
        """Analyze trajectory + metrics; return list[Insight] (strengths, weaknesses,
        recommendations)."""
        alignment_metrics = alignment_metrics or {}
        skill_profiles = skill_profiles or []
        error_patterns = error_patterns or []
        insights: list = []
        related_events = self._related_event_ids(trajectory_points)
        related_plans = self._related_plan_ids(trajectory_points, fallback_plan_id=plan_id)

        components = alignment_metrics.get("components", {})
        alignment_score = alignment_metrics.get("alignment_score", 0.0)
        safety_score = alignment_metrics.get("safety_score",
                                            components.get("risk_guard_pass_rate", 0.0))
        learning_efficiency = alignment_metrics.get("learning_efficiency",
                                                    components.get("learning_efficiency", 0.0))
        preference_ratio = components.get("feedback_preference_ratio",
                                          alignment_metrics.get("feedback_preference_ratio", 0.0))

        # ---- Strengths ----------------------------------------------------------
        if alignment_score >= 0.7:
            insights.append(Insight(
                category="strength",
                content=f"High alignment with human preferences (alignment_score={alignment_score:.2f}).",
                confidence=min(0.9, 0.5 + alignment_score / 4),
                related_events=related_events, related_plans=related_plans,
            ))
        if safety_score >= 0.8:
            insights.append(Insight(
                category="strength",
                content=f"Risk invariants consistently respected (safety_score={safety_score:.2f}).",
                confidence=0.8,
                related_events=related_events, related_plans=related_plans,
            ))
        for profile in skill_profiles:
            wilson = profile.get("wilson_score") if isinstance(profile, dict) else getattr(profile, "wilson_score", 0)
            attempts = profile.get("total_attempts") if isinstance(profile, dict) else getattr(profile, "total_attempts", 0)
            name = profile.get("name") if isinstance(profile, dict) else getattr(profile, "name", profile)
            if attempts and wilson >= 0.6:
                insights.append(Insight(
                    category="strength",
                    content=f"Skill '{name}' is reliable (wilson_score={wilson:.2f} over {attempts} attempts).",
                    confidence=min(0.9, 0.5 + wilson / 3),
                    related_plans=related_plans,
                ))

        # ---- Weaknesses -----------------------------------------------------------
        if alignment_score < 0.5 and (trajectory_points or skill_profiles or error_patterns):
            insights.append(Insight(
                category="weakness",
                content=f"Alignment below target (alignment_score={alignment_score:.2f} < 0.50).",
                confidence=0.7,
                related_events=related_events, related_plans=related_plans,
            ))
        for profile in skill_profiles:
            wilson = profile.get("wilson_score") if isinstance(profile, dict) else getattr(profile, "wilson_score", 1)
            attempts = profile.get("total_attempts") if isinstance(profile, dict) else getattr(profile, "total_attempts", 0)
            name = profile.get("name") if isinstance(profile, dict) else getattr(profile, "name", profile)
            if attempts and wilson < 0.4:
                insights.append(Insight(
                    category="weakness",
                    content=f"Skill '{name}' is underperforming (wilson_score={wilson:.2f} over {attempts} attempts).",
                    confidence=0.75,
                    related_plans=related_plans,
                ))
        for pattern in error_patterns:
            frequency = pattern.get("frequency") if isinstance(pattern, dict) else getattr(pattern, "frequency", 0)
            error_type = pattern.get("error_type") if isinstance(pattern, dict) else getattr(pattern, "error_type", "?")
            if frequency >= 2:
                insights.append(Insight(
                    category="weakness",
                    content=f"Recurring error pattern {error_type} observed {frequency}x; needs a structural fix.",
                    confidence=min(0.9, 0.5 + 0.05 * frequency),
                    related_events=related_events, related_plans=related_plans,
                ))
        if learning_efficiency < 0.3 and len(trajectory_points or []) >= 2:
            insights.append(Insight(
                category="weakness",
                content=f"Learning efficiency is low ({learning_efficiency:.2f}); metrics are not improving over the trajectory window.",
                confidence=0.65,
                related_events=related_events, related_plans=related_plans,
            ))

        # ---- Recommendations ----------------------------------------------------------
        effective_preference = preference_ratio if preference_ratio is not None else 0.0
        if effective_preference < 0.6:
            insights.append(Insight(
                category="recommendation",
                content=f"Collect more human feedback: preference ratio {effective_preference:.2f} "
                        "is below the 0.60 target.",
                confidence=0.6,
                related_plans=related_plans,
            ))
        weak_skills = []
        for profile in skill_profiles:
            wilson = profile.get("wilson_score") if isinstance(profile, dict) else getattr(profile, "wilson_score", 1)
            attempts = profile.get("total_attempts") if isinstance(profile, dict) else getattr(profile, "total_attempts", 0)
            skill_id = profile.get("skill_id") if isinstance(profile, dict) else getattr(profile, "skill_id", None)
            if attempts and wilson < 0.5 and skill_id:
                weak_skills.append(str(skill_id))
        if weak_skills:
            insights.append(Insight(
                category="recommendation",
                content="Schedule SM-2 review sessions for weak skills: " + ", ".join(weak_skills[:5]) + ".",
                confidence=0.7,
                related_plans=related_plans,
            ))
        top_pattern = None
        if error_patterns:
            sorted_patterns = sorted(
                error_patterns,
                key=lambda p: (p.get("frequency") if isinstance(p, dict) else getattr(p, "frequency", 0)),
                reverse=True,
            )
            top = sorted_patterns[0]
            frequency = top.get("frequency") if isinstance(top, dict) else getattr(top, "frequency", 0)
            error_type = top.get("error_type") if isinstance(top, dict) else getattr(top, "error_type", "?")
            if frequency >= 2:
                top_pattern = error_type
                insights.append(Insight(
                    category="recommendation",
                    content=f"Prioritize a remediation task for error pattern {error_type} "
                            f"(highest frequency: {frequency}x).",
                    confidence=0.75,
                    related_events=related_events, related_plans=related_plans,
                ))
        if not insights:
            insights.append(Insight(
                category="recommendation",
                content="Insufficient trajectory/alignment data to model the self; run more plans to build a baseline.",
                confidence=0.4,
                related_plans=related_plans,
            ))

        logger.info("SelfModelEngine generated %d insight(s).", len(insights))
        return insights

    # ---- Persistence -------------------------------------------------------------

    def save_insights(self, insights: list, output_path=None) -> Path:
        """Persist insights to `runtime/insights/<timestamp>.json`."""
        if output_path is None:
            timestamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
            output_path = self.insights_dir / f"{timestamp}.json"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "saved_at": _now(),
            "insight_count": len(insights),
            "insights": [i.to_dict() if isinstance(i, Insight) else i for i in insights],
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        logger.info("Insights saved: %s", output_path)
        return output_path
