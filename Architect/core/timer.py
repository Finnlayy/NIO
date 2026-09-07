import logging
import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class Timer:
    """Timer system supporting deadline and unlimited modes with safety net."""

    def __init__(self, mode: str = "deadline", deadline_s: float = None,
                 soft_deadline_s: float = None, safety_net_s: float = None,
                 t0: float = None, job_id: str = None):
        self.mode = mode  # "deadline" or "unlimited"
        self.deadline_s = deadline_s  # budget in seconds (deadline mode)
        self.soft_deadline_s = soft_deadline_s  # soft limit for warnings
        self.safety_net_s = safety_net_s  # zombie protection / process hygiene
        self.t0 = t0 if t0 is not None else datetime.datetime.utcnow().timestamp()
        self.job_id = job_id
        self.runtime_dir = Path("Architect/runtime")
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

    def tick(self, current_time: float = None) -> dict:
        """Advance timer evaluation; return status dict."""
        current_time = current_time or datetime.datetime.utcnow().timestamp()
        elapsed_s = current_time - self.t0
        status = {
            "mode": self.mode,
            "t0": self.t0,
            "elapsed_s": elapsed_s,
            "current_time": current_time,
            "deadline_s": self.deadline_s,
            "soft_deadline_s": self.soft_deadline_s,
            "safety_net_s": self.safety_net_s,
            "timeout": False,
            "soft_timeout": False,
            "safety_net_triggered": False,
            "remaining_ms": None,
        }
        if self.mode == "deadline" and self.deadline_s is not None:
            remaining = self.deadline_s - elapsed_s
            status["remaining_ms"] = int(remaining * 1000)
            status["timeout"] = remaining <= 0
            status["soft_timeout"] = (self.soft_deadline_s is not None) and (remaining <= (self.deadline_s - self.soft_deadline_s))
        if self.safety_net_s is not None:
            status["safety_net_triggered"] = elapsed_s >= self.safety_net_s
        return status

    def get_state(self) -> dict:
        elapsed_s = datetime.datetime.utcnow().timestamp() - self.t0
        return {
            "mode": self.mode,
            "deadline_s": self.deadline_s,
            "soft_deadline_s": self.soft_deadline_s,
            "safety_net_s": self.safety_net_s,
            "t0": self.t0,
            "elapsed_s": elapsed_s,
            "remaining_ms": int((self.deadline_s - elapsed_s) * 1000) if (self.mode == "deadline" and self.deadline_s) else None,
            "expires_at": datetime.datetime.utcfromtimestamp(self.t0 + self.deadline_s).isoformat() + "Z" if (self.mode == "deadline" and self.deadline_s) else None,
        }

    def save(self):
        """Persist timer state to runtime file."""
        if not self.job_id:
            logger.warning("Timer save called without job_id; skipping persistence.")
            return
        timer_path = self.runtime_dir / f"timer_{self.job_id}.json"
        state = self.get_state()
        state["job_id"] = self.job_id
        with open(timer_path, "w", encoding="utf-8") as f:
            import json
            json.dump(state, f, indent=2, ensure_ascii=False)
        logger.info("Timer state saved: %s", timer_path)

    def load(self, job_id: str):
        timer_path = self.runtime_dir / f"timer_{job_id}.json"
        if not timer_path.exists():
            logger.warning("Timer load: file not found: %s", timer_path)
            return False
        import json
        with open(timer_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        self.mode = state.get("mode", self.mode)
        self.deadline_s = state.get("deadline_s")
        self.soft_deadline_s = state.get("soft_deadline_s")
        self.safety_net_s = state.get("safety_net_s")
        self.t0 = state.get("t0", self.t0)
        self.job_id = job_id
        logger.info("Timer state loaded for job %s (t0=%s)", job_id, self.t0)
        return True
