"""Feedback processing (Phase 4 — RLHF Integration).

Loads human feedback records (validated against
`Architect/schemas/feedback.schema.json`), aggregates ratings / preference
ratios / comment themes, and persists aggregates for the preference model and
alignment tracker.

Aligned with blueprint `src/learning/schemas.ts` (`Feedback`) and
`OMEGA_JULES_TODO.md` Phase 4 (Feedback Processing).
"""

import json
import logging
import datetime
import re
from collections import Counter
from pathlib import Path

from core.schema_utils import SchemaInvalid, load_schema, validate_against_schema, default_schema_path

logger = logging.getLogger(__name__)

DEFAULT_SCHEMA_PATH = default_schema_path("feedback.schema.json")

# Small English stopword list for naive comment theme extraction.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "so", "to", "of", "in",
    "on", "at", "for", "with", "is", "was", "were", "be", "been", "it", "this",
    "that", "these", "those", "as", "by", "from", "not", "no", "yes", "do",
    "does", "did", "have", "has", "had", "i", "you", "he", "she", "we", "they",
    "my", "your", "our", "their", "its", "would", "should", "could", "can",
    "will", "just", "very", "too", "also", "than",
}


class FeedbackProcessor:
    """Load, validate, aggregate and persist human feedback records."""

    def __init__(self, feedback_dir: str = "Architect/runtime/feedback",
                 aggregates_dir: str = "Architect/runtime/feedback/aggregates",
                 event_bus=None, schema_path: str = DEFAULT_SCHEMA_PATH,
                 genai_client=None):
        self.feedback_dir = Path(feedback_dir)
        self.aggregates_dir = Path(aggregates_dir)
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        self.aggregates_dir.mkdir(parents=True, exist_ok=True)
        self.event_bus = event_bus
        self.schema = load_schema(schema_path)
        self.genai_client = genai_client  # optional: GenAI theme extraction

    # ---- Loading / validation -------------------------------------------------

    def validate_feedback(self, feedback: dict) -> dict:
        """Validate one feedback dict against feedback.schema.json."""
        if not isinstance(feedback, dict):
            raise SchemaInvalid(f"Feedback must be a dict, got {type(feedback).__name__}.")
        errors = validate_against_schema(feedback, self.schema)
        if errors:
            raise SchemaInvalid("; ".join(errors))
        return feedback

    def load_feedback(self, file_path) -> dict:
        """Load and validate one feedback file (JSON). Returns the feedback dict."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Feedback file not found: {file_path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        validated = self.validate_feedback(data)
        logger.info("Feedback loaded: %s (outcome_id=%s, rating=%s)",
                    file_path, validated.get("outcome_id"), validated.get("rating"))
        return validated

    def load_feedback_dir(self, dir_path=None) -> list:
        """Load every valid feedback JSON file in a directory; invalid files are skipped."""
        directory = Path(dir_path) if dir_path else self.feedback_dir
        records = []
        for file_path in sorted(directory.glob("*.json")):
            try:
                records.append(self.load_feedback(file_path))
            except (SchemaInvalid, json.JSONDecodeError) as exc:
                logger.error("Skipping invalid feedback file %s: %s", file_path, exc)
        return records

    def save_feedback(self, feedback: dict, file_path=None) -> Path:
        """Persist a validated feedback record; returns the file path."""
        validated = self.validate_feedback(feedback)
        if file_path is None:
            timestamp = (validated.get("timestamp") or datetime.datetime.utcnow().isoformat()).replace(":", "-")
            file_path = self.feedback_dir / f"{timestamp}_{validated['outcome_id']}.json"
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(validated, f, indent=2, ensure_ascii=False)
        if self.event_bus:
            self.event_bus.emit(self.event_bus.build_event(
                event_kind="feedback_submitted",
                job_id=validated.get("outcome_id"),
                message=f"Feedback submitted (rating={validated.get('rating')}).",
                outcome_id=validated.get("outcome_id"),
                rating=validated.get("rating"),
            ))
        return file_path

    # ---- Aggregation ----------------------------------------------------------

    def aggregate(self, feedback_list: list) -> dict:
        """Aggregate a list of feedback records.

        Returns a dict with: count, average_rating (1-5), average_rating_normalized
        (0-1), rating_histogram, preference_ratio (share of A>B-style preferences
        that favored `chosen`), preference_count, common_themes, themes_source.
        """
        records = [fb for fb in feedback_list if isinstance(fb, dict)]
        if not records:
            return {
                "count": 0,
                "average_rating": None,
                "average_rating_normalized": None,
                "rating_histogram": {},
                "preference_ratio": None,
                "preference_count": 0,
                "common_themes": [],
            }

        ratings = [r["rating"] for r in records if isinstance(r.get("rating"), (int, float))]
        histogram = dict(Counter(ratings))

        preferences = [r.get("preference") for r in records if isinstance(r.get("preference"), dict)]
        preference_ratio = None
        if preferences:
            favored = sum(1 for p in preferences if p.get("chosen") and p.get("rejected"))
            preference_ratio = round(favored / len(preferences), 4)

        avg_rating = round(sum(ratings) / len(ratings), 4) if ratings else None

        aggregate_result = {
            "count": len(records),
            "average_rating": avg_rating,
            "average_rating_normalized": round(avg_rating / 5.0, 4) if avg_rating is not None else None,
            "rating_histogram": {str(k): v for k, v in sorted(histogram.items())},
            "preference_ratio": preference_ratio,
            "preference_count": len(preferences),
            "common_themes": self._extract_themes(records),
        }
        aggregate_result["themes_source"] = "structured_stub"
        return aggregate_result

    def aggregate_for_outcome(self, outcome_id: str, feedback_list: list) -> dict:
        """Aggregate only the feedback records referencing `outcome_id`."""
        filtered = [fb for fb in feedback_list if fb.get("outcome_id") == outcome_id]
        aggregate_result = self.aggregate(filtered)
        aggregate_result["outcome_id"] = outcome_id
        return aggregate_result

    def save_aggregate(self, outcome_id: str, aggregate_result: dict) -> Path:
        """Persist an aggregate to runtime/feedback/aggregates/<outcome_id>.json."""
        self.aggregates_dir.mkdir(parents=True, exist_ok=True)
        aggregate_result = dict(aggregate_result)
        aggregate_result.setdefault("outcome_id", outcome_id)
        aggregate_result.setdefault("saved_at", datetime.datetime.utcnow().isoformat() + "Z")
        path = self.aggregates_dir / f"{outcome_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(aggregate_result, f, indent=2, ensure_ascii=False)
        logger.info("Feedback aggregate saved: %s", path)
        return path

    # ---- Theme extraction -------------------------------------------------------

    def _extract_themes(self, records: list, max_themes: int = 5) -> list:
        """Naive keyword-frequency themes from comments; GenAI extraction when available."""
        comments = [r.get("comment", "") for r in records if isinstance(r.get("comment"), str)]
        comments = [c for c in comments if c.strip()]
        if not comments:
            return []

        if self.genai_client is not None:
            try:
                result = self.genai_client.generate_journal({
                    "task": "feedback_theme_extraction",
                    "comments": comments,
                })
                insights = result.get("structured_insights", {})
                observations = insights.get("observations") or []
                themes = [str(o) for o in observations if o][:max_themes]
                if themes:
                    return themes
            except Exception as exc:
                logger.warning("GenAI theme extraction failed; falling back to keyword mining: %s", exc)

        counter = Counter()
        for comment in comments:
            tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_-]{2,}", comment.lower())
            for token in tokens:
                if token not in _STOPWORDS:
                    counter[token] += 1
        return [theme for theme, _count in counter.most_common(max_themes)]
