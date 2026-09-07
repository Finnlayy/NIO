import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class BaselineRetriever:
    """Retrieves and compares baseline plans against current plans for reflection tracking."""

    def __init__(self):
        self.baselines_dir = Path("Architect/runtime/baselines")
        self.baselines_dir.mkdir(parents=True, exist_ok=True)

    def load_baseline(self, plan_id: str) -> dict:
        baseline_path = self.baselines_dir / f"{plan_id}.json"
        if not baseline_path.exists():
            logger.warning("Baseline not found for plan %s at %s", plan_id, baseline_path)
            return {}
        try:
            with open(baseline_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.error("Failed to load baseline for plan %s: %s", plan_id, exc)
            return {}

    def compare(self, current_plan: dict, baseline_plan: dict) -> dict:
        """Compare current plan against baseline; return delta metrics."""
        comparison = {
            "current_plan_id": current_plan.get("plan_id", "unknown"),
            "baseline_plan_id": baseline_plan.get("plan_id", "unknown"),
            "delta": {},
            "added_steps": [],
            "removed_steps": [],
            "changed_steps": [],
            "confidence_delta": 0.0,
        }

        current_steps = {step.get("step_id"): step for step in current_plan.get("steps", [])}
        baseline_steps = {step.get("step_id"): step for step in baseline_plan.get("steps", [])}

        for step_id in current_steps:
            if step_id not in baseline_steps:
                comparison["added_steps"].append(step_id)

        for step_id in baseline_steps:
            if step_id not in current_steps:
                comparison["removed_steps"].append(step_id)

        for step_id in current_steps:
            if step_id in baseline_steps:
                current_step = current_steps[step_id]
                baseline_step = baseline_steps[step_id]
                if current_step.get("action") != baseline_step.get("action"):
                    comparison["changed_steps"].append({
                        "step_id": step_id,
                        "current_action": current_step.get("action"),
                        "baseline_action": baseline_step.get("action"),
                    })
                current_conf = current_step.get("confidence", 0.5)
                baseline_conf = baseline_step.get("confidence", 0.5)
                delta = current_conf - baseline_conf
                if abs(delta) > 0.01:
                    comparison["changed_steps"].append({
                        "step_id": step_id,
                        "confidence_delta": delta,
                    })

        current_confidence = current_plan.get("confidence_score", 0.0)
        baseline_confidence = baseline_plan.get("confidence_score", 0.0)
        comparison["confidence_delta"] = current_confidence - baseline_confidence

        return comparison

    def save_baseline(self, plan: dict):
        plan_id = plan.get("plan_id", "unknown")
        self.baselines_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.baselines_dir / f"{plan_id}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(plan, f, indent=2, ensure_ascii=False)
            logger.info("Baseline saved for plan %s to %s", plan_id, file_path)
        except Exception as exc:
            logger.error("Failed to save baseline for plan %s: %s", plan_id, exc)
