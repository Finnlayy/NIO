import logging
from pathlib import Path
import json
import datetime

logger = logging.getLogger(__name__)

class PostMortemTrigger:
    """Triggers post-mortem analysis when execution results indicate failure or anomalies."""

    def __init__(self, genai_client=None):
        self.genai_client = genai_client
        self.triggers_dir = Path("Architect/runtime/post_mortems")
        self.triggers_dir.mkdir(parents=True, exist_ok=True)

    def check_conditions(self, execution_result: dict) -> bool:
        """Evaluate if post-mortem should be triggered."""
        if not isinstance(execution_result, dict):
            execution_result = {"raw": str(execution_result)}

        verdict = execution_result.get("verdict", "")
        errors = execution_result.get("errors", [])
        timeout_occurred = execution_result.get("timeout", False)
        safety_net_activated = execution_result.get("safety_net_activated", False)

        triggered = (
            verdict == "rejected"
            or len(errors) > 0
            or timeout_occurred
            or safety_net_activated
        )
        return triggered

    def trigger(self, post_mortem_data: dict) -> dict:
        """Execute post-mortem: emit event, call GenAI reflection, save result."""
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        result = {
            "timestamp": timestamp,
            "triggered": True,
            "post_mortem_reference": post_mortem_data.get("job_id") or post_mortem_data.get("execution_result", "unknown"),
            "analysis": None,
            "event_emitted": False,
        }

        # Call GenAI reflection (real or LM Studio fallback via GenAIClient)
        if self.genai_client:
            try:
                reflection = self.genai_client.reflect_dsr(post_mortem_data)
                result["analysis"] = reflection
                result["analysis_source"] = reflection.get("source", "unknown")
            except Exception as exc:
                logger.error("GenAI reflection call failed in PostMortemTrigger: %s", exc)
                result["analysis"] = {"error": str(exc), "structured_reflection": {"diagnosis": "trigger_failed", "summary": "GenAI reflection unavailable during post-mortem.", "recommendation": "Check GenAI connection (Gemini or LM Studio).", "confidence": 0.0, "risk_flags": ["trigger_failure"]}}
        else:
            result["analysis"] = {
                "structured_reflection": {
                    "diagnosis": "manual_trigger",
                    "summary": "Post-mortem triggered without GenAI integration.",
                    "recommendation": "Integrate GenAIClient for automated DSR.",
                    "confidence": 0.0,
                    "risk_flags": ["no_genai_client"],
                },
            }

        # Persist trigger record
        self.triggers_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"post_mortem_{timestamp.replace(':', '-')}.json"
        file_path = self.triggers_dir / file_name
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            logger.info("Post-mortem trigger saved to %s", file_path)
        except Exception as exc:
            logger.error("Failed to persist post-mortem trigger to %s: %s", file_path, exc)

        result["saved_to"] = str(file_path)
        return result
