import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
import json
from pathlib import Path

from gui.views.feedback_dialog import FeedbackSubmission, FeedbackDialog, PYQT6_AVAILABLE
from core.schema_utils import SchemaInvalid

OUTCOME_SUMMARY = {
    "outcome_id": "job_77",
    "verdict": "accept",
    "elapsed_s": 3.2,
    "errors": [],
}


class TestFeedbackSubmission(unittest.TestCase):
    """Headless submit logic (runs without PyQt6)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.system_log = Path(self.tmpdir) / "system.log"
        from core.events import EventBus
        self.bus = EventBus(system_log_path=str(self.system_log))
        self.bus.event_sinks = {"stderr": False, "file": True}
        self.submission = FeedbackSubmission(feedback_dir=str(Path(self.tmpdir) / "feedback"),
                                             event_bus=self.bus)

    def test_build_valid_feedback(self):
        feedback = self.submission.build_feedback(OUTCOME_SUMMARY, rating=5,
                                                  preference="A > B", comment="sharp execution")
        self.assertEqual(feedback["rating"], 5)
        self.assertEqual(feedback["preference"], {"chosen": "A", "rejected": "B"})
        self.assertEqual(feedback["outcome_id"], "job_77")
        self.assertIn("T", feedback["timestamp"])

    def test_rating_required_and_bounded(self):
        for bad in (None, 0, 6, "x"):
            with self.assertRaises(SchemaInvalid):
                self.submission.build_feedback(OUTCOME_SUMMARY, rating=bad)

    def test_preference_optional(self):
        feedback = self.submission.build_feedback(OUTCOME_SUMMARY, rating=3, preference=None)
        self.assertIsNone(feedback["preference"])
        equal_feedback = self.submission.build_feedback(OUTCOME_SUMMARY, rating=3, preference="A == B")
        self.assertIsNone(equal_feedback["preference"])
        with self.assertRaises(SchemaInvalid):
            self.submission.build_feedback(OUTCOME_SUMMARY, rating=3, preference="C > D")

    def test_outcome_id_required(self):
        with self.assertRaises(SchemaInvalid):
            self.submission.build_feedback({}, rating=4)

    def test_submit_persists_and_emits_event(self):
        feedback = self.submission.build_feedback(OUTCOME_SUMMARY, rating=2, comment="too slow")
        path = self.submission.submit(feedback)
        self.assertTrue(Path(path).exists())
        self.assertIn("job_77", str(path))
        with open(path, "r", encoding="utf-8") as f:
            stored = json.load(f)
        self.assertEqual(stored["rating"], 2)
        log_text = self.system_log.read_text(encoding="utf-8")
        self.assertIn("feedback_submitted", log_text)

    def test_submission_matches_feedback_schema(self):
        from core.schema_utils import load_schema, validate_against_schema, default_schema_path
        feedback = self.submission.build_feedback(OUTCOME_SUMMARY, rating=1, preference="B > A")
        schema = load_schema(default_schema_path("feedback.schema.json"))
        errors = validate_against_schema(feedback, schema)
        self.assertEqual(errors, [])


@unittest.skipUnless(PYQT6_AVAILABLE, "PyQt6 not installed")
class TestFeedbackDialogWidget(unittest.TestCase):
    """Widget-level tests (only in a full desktop environment)."""

    def test_dialog_flow(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        tmpdir = tempfile.mkdtemp()
        submission = FeedbackSubmission(feedback_dir=str(Path(tmpdir) / "feedback"))
        dialog = FeedbackDialog(OUTCOME_SUMMARY, submission=submission)
        dialog.rating_spin.setValue(5)
        dialog.comment_edit.setPlainText("great")
        dialog.submit()
        self.assertIsNotNone(dialog.get_result())
        self.assertEqual(dialog.get_result()["rating"], 5)
        self.assertEqual(dialog.result(), dialog.DialogCode.Accepted)

    def test_dialog_requires_dict_summary(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        with self.assertRaises(TypeError):
            FeedbackDialog("not a dict")


if __name__ == "__main__":
    unittest.main()
