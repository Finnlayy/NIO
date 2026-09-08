"""Risk guards — learning engine safety (Phase 4 — RLHF Integration).

Pre-execution guard that evaluates new plans / modifications / model updates
against the risk invariants (`TheJudgeM8`), the schedule policy (`Policy`) and
known error patterns, so a learned "improvement" can never bypass the
constitution. Python counterpart of blueprint `RiskGuard` in
`src/learning/schemas.ts`.

Storage: `Architect/runtime/learning/risk_guards/<guard_id>.json`
Events:  `risk_guard_failed`, `risk_guard_warning` (whitelisted in events.py)
"""

import json
import logging
import datetime
import hashlib
from pathlib import Path

from core.learning.error_patterns import DEFAULT_ALERT_THRESHOLD

logger = logging.getLogger(__name__)


class _DefaultRiskLimits:
    """Fallback risk limits mirroring `core/config.py` defaults (stdlib-only tests)."""

    MAX_TOTAL_LEVERAGE = 5.0
    MAX_SLIPPAGE_BPS = 15.0
    MIN_VAULT_RESERVE_RATIO = 0.10


def make_guard_id(plan_id: str, timestamp: str) -> str:
    return "rg_" + hashlib.sha1(f"{plan_id}|{timestamp}".encode("utf-8")).hexdigest()[:12]


class RiskGuardEngine:
    """Check plans/updates/modifications against invariants, policy and error memory."""

    def __init__(self, judge=None, policy=None, event_bus=None, config=None):
        # Lazy imports keep this module import-safe without pydantic_settings.
        if judge is None:
            from limbs.math.the_judge_m8 import TheJudgeM8
            judge = TheJudgeM8(config or _DefaultRiskLimits())
        if policy is None:
            from core.policy import Policy
            policy = Policy()
        self.judge = judge
        self.policy = policy
        self.event_bus = event_bus

    def check(self, plan_or_update: dict, current_state: dict = None) -> dict:
        """Evaluate a plan/update against all guards; returns a RiskGuardResult dict.

        Fields: `passed` (bool), `failed` (list[str]), `warnings` (list[str]),
        `checks` (list[dict]), `recommendation` (str), `assessment_timestamp`,
        `guard_id`, `plan_id`.
        """
        current_state = current_state or {}
        now = datetime.datetime.utcnow().isoformat() + "Z"
        plan = plan_or_update if isinstance(plan_or_update, dict) else {"raw": str(plan_or_update)}
        plan_id = plan.get("plan_id") or plan.get("job_id") or "unknown_plan"
        checks = []
        failed = []
        warnings = []

        # Guard 1: TheJudgeM8 risk invariants (when risk parameters are present).
        risk_params = plan.get("risk_parameters") or {}
        if risk_params:
            ok, detail = self.judge.check_invariants(
                leverage=risk_params.get("leverage", 0.0),
                slippage=risk_params.get("slippage_bps", 0.0),
                power_factor=risk_params.get("power_factor", 1.0),
                vault_ratio=risk_params.get("vault_ratio", 1.0),
                in_forbidden_zone=bool(risk_params.get("in_forbidden_zone", False)),
                feed_live=bool(risk_params.get("feed_live", True)),
            )
            checks.append({"name": "judge_m8_invariants", "passed": bool(ok), "detail": detail})
            if not ok:
                failed.append(f"judge_m8_invariants: {detail}")
        else:
            checks.append({"name": "judge_m8_invariants", "passed": True,
                           "detail": "No risk parameters in plan; invariant check skipped."})

        # Guard 2: schedule policy (fail-fast trigger validation).
        schedule = plan.get("schedule")
        if schedule is not None:
            ok, detail = self.policy.check_schedule(schedule)
            checks.append({"name": "policy_schedule", "passed": bool(ok), "detail": detail})
            if not ok:
                failed.append(f"policy_schedule: {detail}")
        else:
            checks.append({"name": "policy_schedule", "passed": True,
                           "detail": "No schedule in plan; policy check skipped."})

        # Guard 3: constitution — human approval for human-only files.
        approved_by = plan.get("approved_by", "system")
        for target in plan.get("file_targets", []) or []:
            ok, detail = self.policy.constitution_guard("modify", target, approved_by=approved_by)
            checks.append({"name": "constitution_guard", "passed": bool(ok), "detail": detail})
            if not ok:
                failed.append(f"constitution_guard: {detail}")

        # Guard 4: known error patterns above threshold (learning memory).
        threshold = current_state.get("error_pattern_threshold", DEFAULT_ALERT_THRESHOLD)
        risky_patterns = []
        for pattern in current_state.get("error_patterns", []) or []:
            frequency = pattern.get("frequency", 0) if isinstance(pattern, dict) else getattr(pattern, "frequency", 0)
            if frequency > threshold:
                ptype = pattern.get("error_type", "?") if isinstance(pattern, dict) else getattr(pattern, "error_type", "?")
                risky_patterns.append(f"{ptype} (freq={frequency})")
        if risky_patterns:
            warnings.append("Known recurring errors may repeat: " + ", ".join(risky_patterns))
            checks.append({"name": "error_pattern_memory", "passed": True,
                           "detail": "Warning-level: " + ", ".join(risky_patterns)})
        else:
            checks.append({"name": "error_pattern_memory", "passed": True,
                           "detail": "No error patterns above threshold."})

        # Warnings: low-confidence plans.
        confidence = plan.get("confidence_score")
        if confidence is not None:
            try:
                if float(confidence) < 0.7:
                    warnings.append(f"Plan confidence {confidence} below 0.7 dispatch gate.")
            except (TypeError, ValueError):
                warnings.append(f"Non-numeric confidence_score: {confidence!r}")

        guard_result = {
            "guard_id": make_guard_id(str(plan_id), now),
            "plan_id": plan_id,
            "passed": len(failed) == 0,
            "failed": failed,
            "warnings": warnings,
            "checks": checks,
            "recommendation": self._recommendation(failed, warnings),
            "assessment_timestamp": now,
        }
        logger.info("Risk guard assessed plan %s: passed=%s failed=%d warnings=%d",
                    plan_id, guard_result["passed"], len(failed), len(warnings))
        return guard_result

    @staticmethod
    def _recommendation(failed: list, warnings: list) -> str:
        if failed:
            return "BLOCK: resolve failed guards before dispatching this plan."
        if warnings:
            return "PROCEED WITH CAUTION: review warnings; human approval advised."
        return "SAFE: all guards passed."


class RiskGuardStorage:
    """Persistence for risk guard assessments."""

    def __init__(self, guards_dir: str = "Architect/runtime/learning/risk_guards"):
        self.guards_dir = Path(guards_dir)
        self.guards_dir.mkdir(parents=True, exist_ok=True)

    def save(self, guard_result: dict) -> Path:
        path = self.guards_dir / f"{guard_result.get('guard_id', 'unknown')}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(guard_result, f, indent=2, ensure_ascii=False)
        logger.info("Risk guard assessment saved: %s", path)
        return path

    def load_all(self) -> list:
        results = []
        for path in sorted(self.guards_dir.glob("*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    results.append(json.load(f))
            except Exception as exc:
                logger.error("Failed to load risk guard %s: %s", path, exc)
        return results

    def pass_rate(self) -> float:
        results = self.load_all()
        if not results:
            return 0.0
        return sum(1 for r in results if r.get("passed")) / len(results)


class RiskGuardAlert:
    """Event emission for failed / warning risk assessments."""

    def __init__(self, event_bus=None):
        self.event_bus = event_bus

    def emit_if_failed(self, guard_result: dict) -> list:
        """Emit `risk_guard_failed` and/or `risk_guard_warning`; returns kinds emitted."""
        emitted = []
        if not self.event_bus or not isinstance(guard_result, dict):
            return emitted
        if guard_result.get("passed") is False:
            self.event_bus.emit(self.event_bus.build_event(
                event_kind="risk_guard_failed",
                job_id=guard_result.get("plan_id"),
                message="; ".join(guard_result.get("failed", [])) or "Risk guard failed.",
                guard_id=guard_result.get("guard_id"),
            ))
            emitted.append("risk_guard_failed")
        for warning in guard_result.get("warnings", []) or []:
            self.event_bus.emit(self.event_bus.build_event(
                event_kind="risk_guard_warning",
                job_id=guard_result.get("plan_id"),
                message=str(warning),
                guard_id=guard_result.get("guard_id"),
            ))
            if "risk_guard_warning" not in emitted:
                emitted.append("risk_guard_warning")
        return emitted
