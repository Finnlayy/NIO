import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class MemoryPlanner:
    """Memory-driven planning using Qdrant vector memory for context retrieval."""

    def __init__(self, qdrant_engine):
        self.qdrant_engine = qdrant_engine
        self.plans_dir = Path("Architect/runtime/plans")
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir = Path("Architect/core/planning_config")
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def create_plan(self, objective: str, context_vectors: list = None) -> dict:
        """Create a new plan with memory context retrieval."""
        import datetime, uuid
        plan_id = str(uuid.uuid4())[:8]
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"

        memory_context = []
        if context_vectors and self.qdrant_engine:
            try:
                # Use first vector for retrieval (simplified)
                query_vec = context_vectors[0] if isinstance(context_vectors[0], (list, tuple)) else [0.1] * 16
                results = self.qdrant_engine.client.search(
                    collection_name="omega_memory",
                    query_vector=query_vec,
                    limit=5,
                )
                for point in results:
                    memory_context.append({
                        "memory_id": point.id,
                        "score": point.score,
                        "payload": point.payload,
                    })
            except Exception as exc:
                logger.warning("Memory retrieval failed during plan creation: %s", exc)

        steps = [
            {"step_id": "step_01", "action": "analyze_context", "agent": "microstructure_agent", "confidence": 0.75},
            {"step_id": "step_02", "action": "evaluate_risk", "agent": "judge_m8_agent", "confidence": 0.82},
            {"step_id": "step_03", "action": "generate_reflection", "agent": "genai_agent", "confidence": 0.65},
        ]

        plan = {
            "plan_id": plan_id,
            "objective": objective,
            "status": "draft",
            "steps": steps,
            "memory_context": memory_context,
            "timestamp": timestamp,
            "confidence_score": min(s.get("confidence", 0.5) for s in steps) if steps else 0.0,
        }

        self.save_plan(plan)
        return plan

    def update_plan(self, plan_id: str, updates: dict) -> dict:
        plan_path = self.plans_dir / f"{plan_id}.json"
        if not plan_path.exists():
            raise FileNotFoundError(f"Plan {plan_id} not found at {plan_path}")
        with open(plan_path, "r", encoding="utf-8") as f:
            plan = json.load(f)
        plan.update(updates)
        self.save_plan(plan)
        return plan

    def get_plan(self, plan_id: str) -> dict:
        plan_path = self.plans_dir / f"{plan_id}.json"
        if not plan_path.exists():
            return {}
        with open(plan_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_plan(self, plan: dict):
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        plan_path = self.plans_dir / f"{plan['plan_id']}.json"
        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2, ensure_ascii=False)
        logger.info("Plan %s saved to %s", plan.get("plan_id"), plan_path)
