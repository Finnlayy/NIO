"""Feedback dialog (Phase 4 — RLHF Integration).

PyQt6 dialog for rating a completed outcome: 1-5 rating, optional A/B
preference, free-text comment. Submission validates against
`feedback.schema.json`, persists to `Architect/runtime/feedback/` and emits a
`feedback_submitted` event.

The submission *logic* lives in `FeedbackSubmission` (headless, stdlib-only)
so it is fully testable without a Qt event loop; the `FeedbackDialog` widget
is a thin PyQt6 shell (import-guarded, since PyQt6 is an optional desktop
dependency — see Architect/docs/DIVERGENCES.md).
"""

import json
import logging
import datetime
from pathlib import Path

from core.schema_utils import SchemaInvalid, load_schema, validate_against_schema, default_schema_path
from core.events import EventBus

logger = logging.getLogger(__name__)

DEFAULT_SCHEMA_PATH = default_schema_path("feedback.schema.json")
PREFERENCE_CHOICES = ["A > B", "A == B", "B > A"]


class FeedbackSubmission:
    """Headless feedback validation + persistence used by the dialog and tests."""

    def __init__(self, feedback_dir: str = "Architect/runtime/feedback",
                 event_bus: EventBus = None, schema_path: str = DEFAULT_SCHEMA_PATH):
        self.feedback_dir = Path(feedback_dir)
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        self.event_bus = event_bus
        self.schema = load_schema(schema_path)

    def build_feedback(self, outcome_summary: dict, rating, preference=None,
                       comment: str = "", rater_id: str = "human") -> dict:
        """Validate dialog inputs and build a schema-conformant feedback dict.

        Args:
            outcome_summary: {job_id / outcome_id, verdict, elapsed_s, errors}.
            rating: int 1-5 (required).
            preference: "A > B" | "A == B" | "B > A" | None.
            comment: free text.
        """
        outcome_id = (outcome_summary or {}).get("outcome_id") or (outcome_summary or {}).get("job_id")
        if not outcome_id:
            raise SchemaInvalid("outcome_summary must contain 'outcome_id' or 'job_id'.")
        try:
            rating_int = int(rating)
        except (TypeError, ValueError):
            raise SchemaInvalid(f"Rating must be an integer 1-5, got {rating!r}.")
        if not 1 <= rating_int <= 5:
            raise SchemaInvalid(f"Rating must be between 1 and 5, got {rating_int}.")

        preference_map = {
            "A > B": {"chosen": "A", "rejected": "B"},
            "B > A": {"chosen": "B", "rejected": "A"},
            "A == B": None,
            "": None,
            None: None,
        }
        if preference not in preference_map:
            raise SchemaInvalid(f"Preference must be one of {PREFERENCE_CHOICES} or None, got {preference!r}.")

        feedback = {
            "outcome_id": str(outcome_id),
            "rater_id": rater_id,
            "rating": rating_int,
            "preference": preference_map[preference],
            "comment": str(comment or ""),
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "outcome_summary": {
                "verdict": (outcome_summary or {}).get("verdict"),
                "elapsed_s": (outcome_summary or {}).get("elapsed_s"),
                "errors": (outcome_summary or {}).get("errors") or [],
            },
        }
        errors = validate_against_schema(feedback, self.schema)
        if errors:
            raise SchemaInvalid("; ".join(errors))
        return feedback

    def submit(self, feedback: dict) -> Path:
        """Persist feedback and emit `feedback_submitted`; returns the file path."""
        timestamp = feedback.get("timestamp", datetime.datetime.utcnow().isoformat()).replace(":", "-")
        file_path = self.feedback_dir / f"{timestamp}_{feedback['outcome_id']}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(feedback, f, indent=2, ensure_ascii=False)
        if self.event_bus:
            self.event_bus.emit(self.event_bus.build_event(
                event_kind="feedback_submitted",
                job_id=feedback["outcome_id"],
                message=f"Feedback submitted via dialog (rating={feedback['rating']}).",
                outcome_id=feedback["outcome_id"],
                rating=feedback["rating"],
            ))
        logger.info("Feedback submitted: %s", file_path)
        return file_path


# ---- PyQt6 shell (import-guarded) ---------------------------------------------

try:  # pragma: no cover - exercised only when PyQt6 is installed
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QSpinBox, QComboBox, QTextEdit, QPushButton, QHBoxLayout

    PYQT6_AVAILABLE = True
except ImportError:  # pragma: no cover
    PYQT6_AVAILABLE = False


if PYQT6_AVAILABLE:

    class FeedbackDialog(QDialog):
        """Modal dialog collecting a 1-5 rating, optional preference and comment."""

        def __init__(self, outcome_summary: dict, submission: FeedbackSubmission = None, parent=None):
            super().__init__(parent)
            if not isinstance(outcome_summary, dict):
                raise TypeError("outcome_summary must be a dict")
            self.outcome_summary = outcome_summary
            self.submission = submission or FeedbackSubmission()
            self.feedback_result = None

            self.setWindowTitle("OMEGA — Rate this outcome")
            layout = QVBoxLayout()
            self.setLayout(layout)

            job_id = outcome_summary.get("job_id") or outcome_summary.get("outcome_id") or "?"
            verdict = outcome_summary.get("verdict", "?")
            elapsed = outcome_summary.get("elapsed_s", "?")
            errors = outcome_summary.get("errors") or []
            summary_text = (f"Outcome: {job_id}\nVerdict: {verdict}\nElapsed: {elapsed}s\n"
                            f"Errors: {len(errors)}" + (f" ({errors[0][:60]}...)" if errors else ""))
            layout.addWidget(QLabel(summary_text))

            self.rating_spin = QSpinBox()
            self.rating_spin.setRange(1, 5)
            self.rating_spin.setValue(3)
            layout.addWidget(self.rating_spin)

            self.preference_combo = QComboBox()
            self.preference_combo.addItems(["(no preference)"] + PREFERENCE_CHOICES)
            layout.addWidget(self.preference_combo)

            self.comment_edit = QTextEdit()
            self.comment_edit.setPlaceholderText("What should OMEGA do differently next time?")
            layout.addWidget(self.comment_edit)

            buttons = QHBoxLayout()
            self.submit_btn = QPushButton("Submit")
            self.submit_btn.clicked.connect(self.submit)
            self.cancel_btn = QPushButton("Cancel")
            self.cancel_btn.clicked.connect(self.reject)
            buttons.addWidget(self.submit_btn)
            buttons.addWidget(self.cancel_btn)
            layout.addLayout(buttons)

        def submit(self):
            """Validate + persist; closes the dialog on success."""
            preference = self.preference_combo.currentText()
            if preference == "(no preference)":
                preference = None
            feedback = self.submission.build_feedback(
                outcome_summary=self.outcome_summary,
                rating=self.rating_spin.value(),
                preference=preference,
                comment=self.comment_edit.toPlainText(),
                rater_id="human",
            )
            self.submission.submit(feedback)
            self.feedback_result = feedback
            self.accept()

        def get_result(self):
            """Return the submitted feedback dict (None until submitted)."""
            return self.feedback_result

else:

    class FeedbackDialog:  # pragma: no cover - fallback when PyQt6 is absent
        """Placeholder raising a clear error when PyQt6 is not installed."""

        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                "FeedbackDialog requires PyQt6. Install Architect requirements "
                "or use the headless FeedbackSubmission API instead."
            )
