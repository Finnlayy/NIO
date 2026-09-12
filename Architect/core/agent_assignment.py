import logging
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# Agent capability registry mapping agent roles to implementing modules
AGENT_REGISTRY = {
    "judge_m8_agent": {
        "capabilities": ["risk_invariant_check", "execution_validation", "post_mortem_assessment"],
        "module": "limbs.math_engines.the_judge_m8",
        "class": "TheJudgeM8",
        "description": "Checks 6 trading risk invariants (feed, zone, leverage, slippage, power factor, vault reserve).",
    },
    "microstructure_agent": {
        "capabilities": ["orderbook_imbalance", "footprint_map", "volume_delta"],
        "module": "limbs.intelligence.microstructure_engine",
        "class": "MicrostructureEngine",
        "description": "Calculates OBI and intra-bar footprint maps from orderbook and trade data.",
    },
    "gravity_agent": {
        "capabilities": ["ac_gravity", "forbidden_zone_detection", "power_factor"],
        "module": "limbs.math_engines.ac_gravity_engine",
        "class": "ACGravityEngine",
        "description": "Computes AC power fields and detects forbidden zones at 99.9% quantile.",
    },
    "genai_agent": {
        "capabilities": ["journal_generation", "dsr_reflection", "analysis", "planning_support"],
        "module": "limbs.intelligence.genai_client",
        "class": "GenAIClient",
        "description": "Gemini-powered reflection, journal writing, and structured analysis.",
    },
    "memory_agent": {
        "capabilities": ["vector_memory", "context_retrieval", "anomaly_detection"],
        "module": "limbs.intelligence.qdrant_memory_engine",
        "class": "QdrantMemoryEngine",
        "description": "Qdrant vector memory for flash-crash anomaly detection and context retrieval.",
    },
    "ml_agent": {
        "capabilities": ["clustering", "regime_detection", "pattern_recognition"],
        "module": "limbs.ml.hdbscan_engine",
        "class": "HDBSCANEngine",
        "description": "HDBSCAN clustering for market regime detection and structural pattern recognition.",
    },
}

class AgentAssignment:
    """Maps plans and tasks to agent roles based on capability requirements."""

    def __init__(self):
        self.registry = AGENT_REGISTRY
        self.assignments_dir = Path("Architect/runtime/assignments")
        self.assignments_dir.mkdir(parents=True, exist_ok=True)

    def map_agent_to_task(self, task_description: str, required_capabilities: list = None) -> str:
        """Find the best agent for a given task description and capability list."""
        best_agent = None
        best_score = -1
        for agent_id, info in self.registry.items():
            capabilities = info.get("capabilities", [])
            score = 0
            if required_capabilities:
                for cap in required_capabilities:
                    if cap in capabilities:
                        score += 1
            else:
                # Fallback: match keywords in task description
                desc_lower = task_description.lower()
                for cap in capabilities:
                    cap_words = cap.replace("_", " ")
                    if cap_words in desc_lower:
                        score += 1
            if score > best_score:
                best_score = score
                best_agent = agent_id
        return best_agent if best_agent else "manual_review_agent"

    def assign_agents(self, plan: dict) -> dict:
        """Assign agents to all steps in a plan."""
        steps = plan.get("steps", [])
        updated_steps = []
        for step in steps:
            action = step.get("action", "")
            agent = step.get("agent")
            if not agent or agent == "manual_review_agent":
                agent = self.map_agent_to_task(action, required_capabilities=step.get("required_capabilities"))
            step["agent"] = agent
            updated_steps.append(step)
        plan["steps"] = updated_steps
        plan["agent_assignments_mapped"] = True
        return plan

    def get_agent_info(self, agent_id: str) -> dict:
        return self.registry.get(agent_id, {
            "capabilities": ["unknown"],
            "module": "unknown",
            "class": "Unknown",
            "description": "Agent not found in registry.",
        })
