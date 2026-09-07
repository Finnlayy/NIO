import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
from pathlib import Path

from core.learning.knowledge_base import KnowledgeBase, KnowledgeEntryParser


class TestKnowledgeBase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.kb = KnowledgeBase(kb_dir=str(Path(self.tmpdir) / "knowledge"))

    def _entry(self, title="Feed stall play", content="When the feed stalls, halve leverage first.",
               tags=("reflection", "feed"), **kwargs):
        entry = {"title": title, "content": content, "tags": list(tags),
                 "source": "reflection", "confidence": 0.7}
        entry.update(kwargs)
        return entry

    def test_save_assigns_entry_id_and_persists(self):
        saved = self.kb.save(self._entry())
        self.assertTrue(saved["entry_id"].startswith("kb_"))
        files = list(Path(self.tmpdir, "knowledge").glob("*.json"))
        self.assertEqual(len(files), 1)

    def test_save_is_idempotent_for_same_entry(self):
        first = self.kb.save(self._entry())
        second = self.kb.save(self._entry())
        self.assertEqual(first["entry_id"], second["entry_id"])
        self.assertEqual(len(self.kb.all()), 1)

    def test_load_and_all(self):
        saved = self.kb.save(self._entry())
        loaded = self.kb.load(saved["entry_id"])
        self.assertEqual(loaded["title"], "Feed stall play")
        self.assertEqual(len(self.kb.all()), 1)
        with self.assertRaises(FileNotFoundError):
            self.kb.load("kb_missing")

    def test_search_by_tag(self):
        self.kb.save(self._entry())
        self.kb.save(self._entry(title="Regime note", content="Chop regime active.",
                                 tags=("regime",)))
        hits = self.kb.search(query_tags=["feed"])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["entry"]["title"], "Feed stall play")
        self.assertEqual(hits[0]["matched_tags"], ["feed"])

    def test_search_by_content(self):
        self.kb.save(self._entry())
        self.kb.save(self._entry(title="Other", content="Unrelated body text.", tags=("misc",)))
        hits = self.kb.search(query_content="halve leverage")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["content_hits"], 1)

    def test_search_ranking_and_limit(self):
        for i in range(15):
            self.kb.save(self._entry(title=f"entry {i}", content=f"leverage note {i}", tags=("feed",)))
        hits = self.kb.search(query_tags=["feed"], limit=10)
        self.assertEqual(len(hits), 10)

    def test_search_no_match(self):
        self.kb.save(self._entry())
        self.assertEqual(self.kb.search(query_tags=["nope"], query_content="zzz"), [])

    def test_query_convenience(self):
        self.kb.save(self._entry())
        hits = self.kb.query("leverage")
        self.assertGreaterEqual(len(hits), 1)


class TestKnowledgeEntryParser(unittest.TestCase):
    def test_extract_from_dsr_reflection(self):
        reflection = {
            "structured_reflection": {
                "diagnosis": "Feed connection stalled",
                "summary": "Execution used a stale feed",
                "recommendation": "Add a watchdog on the tick loop",
                "confidence": 0.8,
                "risk_flags": ["stale_feed"],
            }
        }
        entries = KnowledgeEntryParser.extract_from_reflection(reflection)
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertIn("Feed connection stalled", entry["title"])
        self.assertIn("watchdog", entry["content"])
        self.assertIn("dsr", entry["tags"])
        self.assertEqual(entry["source"], "reflection")
        self.assertEqual(entry["confidence"], 0.8)

    def test_extract_from_journal_reflection(self):
        reflection = {
            "structured_insights": {
                "summary": "Clean execution window",
                "observations": ["OBI flipped positive", "Gravity field stable"],
                "anomalies": ["Volume spike at 13:00"],
                "hypothesis": "Regime shifting to BTC satellite",
            }
        }
        entries = KnowledgeEntryParser.extract_from_reflection(reflection)
        # 1 journal body + 1 anomaly entry
        self.assertEqual(len(entries), 2)
        self.assertIn("Regime shifting", entries[0]["content"])
        self.assertTrue(entries[1]["title"].startswith("Anomaly:"))

    def test_extract_from_plain_string(self):
        entries = KnowledgeEntryParser.extract_from_reflection("Always verify feed integrity before dispatch.")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["source"], "reflection")

    def test_extract_from_garbage(self):
        self.assertEqual(KnowledgeEntryParser.extract_from_reflection(None), [])
        self.assertEqual(KnowledgeEntryParser.extract_from_reflection(""), [])
        self.assertEqual(KnowledgeEntryParser.extract_from_reflection(42), [])

    def test_extracted_entries_are_saved_and_searchable(self):
        tmpdir = tempfile.mkdtemp()
        kb = KnowledgeBase(kb_dir=str(Path(tmpdir) / "kb"))
        for entry in KnowledgeEntryParser.extract_from_reflection({
            "structured_reflection": {
                "diagnosis": "Stale feed", "summary": "used stale feed",
                "recommendation": "watchdog", "confidence": 0.7, "risk_flags": [],
            }
        }):
            kb.save(entry)
        hits = kb.search(query_tags=["dsr"])
        self.assertEqual(len(hits), 1)


if __name__ == "__main__":
    unittest.main()
