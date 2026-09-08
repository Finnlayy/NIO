"""SM-2 spaced repetition (Phase 4 — RLHF Integration).

Classic SuperMemo-2 algorithm for scheduling skill/knowledge reviews:
  EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)),  EF' >= 1.3
  interval' = interval * EF'  if quality >= 3  else 1 day

Storage: `Architect/runtime/learning/reviews/<item_id>.json`
Aligned with blueprint `Skill.intervalDays` / `Skill.easeFactor` and
`OMEGA_JULES_TODO.md` Phase 4 (SM-2 Spaced Repetition).
"""

import json
import logging
import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_EASE_FACTOR = 2.5
DEFAULT_INTERVAL_DAYS = 1.0
MIN_EASE_FACTOR = 1.3
MAX_QUALITY = 5
MIN_QUALITY = 0


class SpacedRepetitionEngine:
    """SM-2 review scheduling for learning items (skills, knowledge entries)."""

    def __init__(self, reviews_dir: str = "Architect/runtime/learning/reviews",
                 event_bus=None, clock_fn=None):
        self.reviews_dir = Path(reviews_dir)
        self.reviews_dir.mkdir(parents=True, exist_ok=True)
        self.event_bus = event_bus
        self.clock_fn = clock_fn or datetime.datetime.utcnow
        self._reviews = {}
        self.load_reviews()

    # ---- Core SM-2 ------------------------------------------------------------

    @staticmethod
    def update_ease_factor(ease_factor: float, quality: float) -> float:
        """SM-2 ease-factor update; quality is 0-5 (fractional allowed)."""
        q = max(MIN_QUALITY, min(MAX_QUALITY, quality))
        new_ef = ease_factor + (0.1 - (MAX_QUALITY - q) * (0.08 + (MAX_QUALITY - q) * 0.02))
        return round(max(MIN_EASE_FACTOR, new_ef), 4)

    @staticmethod
    def update_interval(interval_days: float, new_ease_factor: float, quality: float) -> float:
        """SM-2 interval update per TODO: `interval * EF` if quality >= 3 else reset to 1."""
        if quality >= 3:
            return round(max(1.0, interval_days * new_ease_factor), 4)
        return 1.0

    def review(self, item_id: str, quality: float) -> dict:
        """Apply one review with quality 0-5; returns the updated review record."""
        record = self._reviews.get(item_id, self._new_record(item_id))
        new_ef = self.update_ease_factor(record["ease_factor"], quality)
        new_interval = self.update_interval(record["interval_days"], new_ef, quality)

        now = self.clock_fn()
        record.update({
            "ease_factor": new_ef,
            "interval_days": new_interval,
            "repetitions": record["repetitions"] + 1 if quality >= 3 else 0,
            "last_quality": max(MIN_QUALITY, min(MAX_QUALITY, quality)),
            "last_reviewed": now.isoformat() + "Z",
        })
        # Next review derives from the NEW interval (not the previously stored one).
        record["next_review_at"] = (now + datetime.timedelta(days=new_interval)).isoformat() + "Z"
        self._reviews[item_id] = record
        self.save_reviews()
        logger.info("SM-2 review applied: %s (q=%s, EF=%.2f, interval=%.2fd)",
                    item_id, quality, new_ef, new_interval)
        return record

    def _new_record(self, item_id: str) -> dict:
        return {
            "item_id": item_id,
            "ease_factor": DEFAULT_EASE_FACTOR,
            "interval_days": DEFAULT_INTERVAL_DAYS,
            "repetitions": 0,
            "last_quality": None,
            "last_reviewed": None,
            "next_review_at": None,
        }

    # ---- Scheduling -----------------------------------------------------------

    def schedule_review(self, item_id: str, now: datetime.datetime = None) -> str:
        """Next review timestamp (ISO8601) = now + interval_days."""
        record = self._reviews.get(item_id, self._new_record(item_id))
        now = now or self.clock_fn()
        next_at = now + datetime.timedelta(days=record["interval_days"])
        return next_at.isoformat() + "Z"

    def due_reviews(self, now: datetime.datetime = None) -> list:
        """Items whose next_review_at <= now; emits `review_due` events."""
        now = now or self.clock_fn()
        due = []
        for item_id, record in self._reviews.items():
            next_at = record.get("next_review_at")
            if not next_at:
                continue
            try:
                next_dt = datetime.datetime.fromisoformat(next_at.replace("Z", ""))
            except ValueError:
                continue
            if next_dt <= now:
                due.append(item_id)
                if self.event_bus:
                    self.event_bus.emit(self.event_bus.build_event(
                        event_kind="review_due",
                        job_id=item_id,
                        message=f"Review due for learning item {item_id}.",
                        item_id=item_id,
                        interval_days=record.get("interval_days"),
                    ))
        return due

    # ---- Persistence ----------------------------------------------------------

    def save_reviews(self):
        self.reviews_dir.mkdir(parents=True, exist_ok=True)
        for item_id, record in self._reviews.items():
            path = self.reviews_dir / f"{item_id}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2, ensure_ascii=False)

    def load_reviews(self):
        self._reviews = {}
        if not self.reviews_dir.exists():
            return self._reviews
        for path in self.reviews_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    record = json.load(f)
                self._reviews[record.get("item_id", path.stem)] = record
            except Exception as exc:
                logger.error("Failed to load review record %s: %s", path, exc)
        return self._reviews

    def get_review(self, item_id: str) -> dict:
        return self._reviews.get(item_id, self._new_record(item_id))


class ReviewScheduler:
    """Thin facade: decides *what* should be reviewed and delegates to the engine."""

    def __init__(self, engine: SpacedRepetitionEngine, event_bus=None):
        self.engine = engine
        self.event_bus = event_bus

    def review_item(self, item_id: str, quality: float) -> dict:
        return self.engine.review(item_id, quality)

    def items_due(self, now: datetime.datetime = None) -> list:
        return self.engine.due_reviews(now=now)

    def next_review(self, item_id: str) -> str:
        return self.engine.get_review(item_id)["next_review_at"]
