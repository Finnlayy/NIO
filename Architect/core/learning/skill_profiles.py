"""Wilson-score skill profiles (Phase 4 — RLHF Integration).

A learned capability is profiled with a conservative Wilson lower bound on its
success rate, so low-sample skills read as uncertain instead of overconfident.
Direct Python port of blueprint `src/learning/algorithm.ts::wilsonLowerBound`.

Files: `Architect/core/learning/skill_profiles.py`
Storage: `Architect/runtime/learning/skills/<skill_id>.json`
"""

import json
import logging
import datetime
import hashlib
import math
from pathlib import Path

logger = logging.getLogger(__name__)

# Two-sided z-scores for common confidence levels (blueprint default: 1.96).
Z_SCORES = {
    0.90: 1.6449,
    0.95: 1.9600,
    0.98: 2.3263,
    0.99: 2.5758,
}
DEFAULT_CONFIDENCE = 0.95


class WilsonScoreCalculator:
    """Wilson score lower bound for a Bernoulli success estimate."""

    @staticmethod
    def compute(successes: float, total_attempts: float, confidence: float = DEFAULT_CONFIDENCE) -> float:
        """Return the Wilson lower bound in [0, 1].

        wilson = (p_hat + z^2/(2n) - z * sqrt(p_hat*(1-p_hat)/n + z^2/(4n^2))) / (1 + z^2/n)
        """
        n = total_attempts
        if n <= 0:
            return 0.0
        z = Z_SCORES.get(round(confidence, 2), Z_SCORES[DEFAULT_CONFIDENCE])
        p_hat = successes / n
        z2 = z * z
        denominator = 1.0 + z2 / n
        centre = p_hat + z2 / (2.0 * n)
        # Margin exactly as specified (blueprint algorithm.ts + TODO Phase 4):
        #   z * sqrt(p_hat*(1-p_hat)/n + z^2/(4n^2))
        margin = z * math.sqrt(p_hat * (1.0 - p_hat) / n + z2 / (4.0 * n * n))
        score = (centre - margin) / denominator
        return max(0.0, min(1.0, score))


class SkillProfile:
    """A learned capability with a Wilson-scored proficiency estimate."""

    def __init__(self, skill_id: str, name: str, successes: int = 0, total_attempts: int = 0,
                 wilson_score: float = 0.0, last_evaluated: str = None,
                 interval_days: float = 1.0, ease_factor: float = 2.5, meta: dict = None):
        self.skill_id = skill_id
        self.name = name
        self.successes = successes
        self.total_attempts = total_attempts
        self.wilson_score = wilson_score
        self.last_evaluated = last_evaluated
        self.interval_days = interval_days  # consumed by SpacedRepetitionEngine
        self.ease_factor = ease_factor
        self.meta = meta or {}

    def update(self, success: bool):
        """Record one attempt; recompute the Wilson lower bound."""
        self.total_attempts += 1
        if success:
            self.successes += 1
        self.wilson_score = WilsonScoreCalculator.compute(self.successes, self.total_attempts)
        self.last_evaluated = datetime.datetime.utcnow().isoformat() + "Z"

    @property
    def success_rate(self) -> float:
        return self.successes / self.total_attempts if self.total_attempts > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "successes": self.successes,
            "total_attempts": self.total_attempts,
            "wilson_score": round(self.wilson_score, 6),
            "last_evaluated": self.last_evaluated,
            "interval_days": self.interval_days,
            "ease_factor": self.ease_factor,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SkillProfile":
        return cls(
            skill_id=data.get("skill_id", ""),
            name=data.get("name", ""),
            successes=int(data.get("successes", 0)),
            total_attempts=int(data.get("total_attempts", 0)),
            wilson_score=float(data.get("wilson_score", 0.0)),
            last_evaluated=data.get("last_evaluated"),
            interval_days=float(data.get("interval_days", 1.0)),
            ease_factor=float(data.get("ease_factor", 2.5)),
            meta=data.get("meta") or {},
        )

    def save(self, base_dir: str = "Architect/runtime/learning/skills") -> Path:
        base = Path(base_dir)
        base.mkdir(parents=True, exist_ok=True)
        path = base / f"{self.skill_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info("SkillProfile saved: %s (wilson=%.4f)", path, self.wilson_score)
        return path

    @classmethod
    def load(cls, skill_id: str, base_dir: str = "Architect/runtime/learning/skills") -> "SkillProfile":
        path = Path(base_dir) / f"{skill_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"SkillProfile not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


def make_skill_id(domain: str, algorithm_tag: str = None) -> str:
    """Deterministic skill key (blueprint `skillKey(domain, algorithmTag)`)."""
    key = f"{domain}:{algorithm_tag or 'general'}"
    return "skill_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


class SkillProfileUpdater:
    """Registry that creates/updates/persists skill profiles from outcomes."""

    def __init__(self, skills_dir: str = "Architect/runtime/learning/skills", event_bus=None):
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.event_bus = event_bus

    def upsert(self, profile: SkillProfile) -> SkillProfile:
        profile.save(str(self.skills_dir))
        return profile

    def get(self, skill_id: str) -> SkillProfile:
        return SkillProfile.load(skill_id, str(self.skills_dir))

    def record_outcome(self, skill_id: str, success: bool, name: str = None,
                       domain: str = "misc", algorithm_tag: str = None) -> SkillProfile:
        """Record one outcome against a skill; create the profile if missing."""
        try:
            profile = SkillProfile.load(skill_id, str(self.skills_dir))
        except FileNotFoundError:
            profile = SkillProfile(skill_id=skill_id, name=name or skill_id)
        profile.update(success)
        if name:
            profile.name = name
        profile.meta.setdefault("domain", domain)
        if algorithm_tag:
            profile.meta["algorithm_tag"] = algorithm_tag
        self.upsert(profile)
        return profile

    def load_all(self) -> list:
        profiles = []
        for path in sorted(self.skills_dir.glob("*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    profiles.append(SkillProfile.from_dict(json.load(f)))
            except Exception as exc:
                logger.error("Failed to load skill profile %s: %s", path, exc)
        return profiles

    def weakest(self, n: int = 3) -> list:
        profiles = [p for p in self.load_all() if p.total_attempts > 0]
        return sorted(profiles, key=lambda p: p.wilson_score)[:n]

    def strongest(self, n: int = 3) -> list:
        profiles = [p for p in self.load_all() if p.total_attempts > 0]
        return sorted(profiles, key=lambda p: p.wilson_score, reverse=True)[:n]
