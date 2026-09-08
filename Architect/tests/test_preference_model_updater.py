import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
import json
from pathlib import Path

from core.events import EventBus
from core.learning.preference_model_updater import PreferenceModelUpdater

REPO_ROOT = Path(__file__).resolve().parents[2]
RLHF_DATASET = str(REPO_ROOT / "evals" / "datasets" / "rlhf_samples.json")


def _write_samples(tmpdir, samples, name="train.json"):
    path = Path(tmpdir) / name
    with open(path, "w", encoding="utf-8") as f:
        json.dump(samples, f)
    return str(path)


def _read_json(path):
    """Read JSON without leaking the file handle.

    Passing a bare ``open(...)`` straight into ``json.load`` closes the handle
    only at GC time, which trips ``-W error::ResourceWarning`` -- the standard
    this repo's root suite and CI already enforce (see Makefile ``test`` and
    ci/neu.yml).
    """
    return json.loads(Path(path).read_text(encoding="utf-8"))


class TestPreferenceModelUpdater(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.models_dir = Path(self.tmpdir) / "models"
        self.system_log = Path(self.tmpdir) / "system.log"
        self.bus = EventBus(system_log_path=str(self.system_log))
        self.bus.event_sinks = {"stderr": False, "file": True}
        self.updater = PreferenceModelUpdater(models_dir=str(self.models_dir), event_bus=self.bus)

    def test_load_model_defaults_to_zero_model(self):
        model = self.updater.load_model()
        self.assertEqual(model["model_type"], "preference_logistic_v1")
        self.assertEqual(model["weights"], [0.0] * model["vocab_size"])
        self.assertAlmostEqual(model["bias"], 0.0)

    def test_update_trains_and_saves(self):
        result = self.updater.update(RLHF_DATASET)
        self.assertEqual(result["trained_samples"], 4)
        self.assertIsNotNone(result["final_loss"])
        self.assertGreaterEqual(result["final_loss"], 0.0)
        updated = list(self.models_dir.glob("updated_*.json"))
        self.assertEqual(len(updated), 1)
        self.assertTrue((self.models_dir / "current_model.json").exists())

    def test_update_is_deterministic(self):
        # Two fresh updaters, same seed, same data -> identical weight digests.
        other_dir = Path(self.tmpdir) / "models2"
        other = PreferenceModelUpdater(models_dir=str(other_dir))
        first = self.updater.update(RLHF_DATASET)
        second = other.update(RLHF_DATASET)
        self.assertEqual(first["digest"], second["digest"])

    def test_predictions_improve_with_training(self):
        # Before training, all predictions are 0.5.
        samples = _read_json(RLHF_DATASET)
        model = self.updater.load_model()
        baseline = [self.updater._predict_score(model, s["agentOutput"]) for s in samples]
        self.assertTrue(all(abs(p - 0.5) < 1e-9 for p in baseline))
        # After training, predictions separate high/low feedback samples.
        self.updater.update(RLHF_DATASET)
        trained = self.updater.load_model()
        preds = [self.updater._predict_score(trained, s["agentOutput"]) for s in samples]
        targets = [s["feedbackScore"] for s in samples]
        high_pred = max(p for p, t in zip(preds, targets) if t > 0.8)
        low_pred = min(p for p, t in zip(preds, targets) if t < 0.6)
        self.assertGreater(high_pred, low_pred)

    def test_validate_emits_model_updated(self):
        update_result = self.updater.update(RLHF_DATASET)
        validation = self.updater.validate(update_result["model_path"], RLHF_DATASET)
        self.assertTrue(validation["passed"])
        self.assertGreaterEqual(validation["validation_score"], self.updater.validation_threshold)
        log_text = self.system_log.read_text(encoding="utf-8")
        self.assertIn("model_updated", log_text)
        self.assertNotIn("model_validation_failed", log_text)

    def test_validate_emits_model_validation_failed(self):
        # Train on one distribution, validate on a contradictory one.
        train = _write_samples(self.tmpdir, [
            {"id": "t1", "prompt": "alpha", "agentOutput": "alpha reply", "feedbackScore": 0.95},
            {"id": "t2", "prompt": "alpha beta", "agentOutput": "alpha beta reply", "feedbackScore": 0.9},
        ], "train.json")
        test = _write_samples(self.tmpdir, [
            {"id": "v1", "prompt": "gamma", "agentOutput": "gamma reply", "feedbackScore": 0.0},
            {"id": "v2", "prompt": "delta", "agentOutput": "delta reply", "feedbackScore": 0.05},
        ], "test.json")
        updater = PreferenceModelUpdater(models_dir=str(self.models_dir), event_bus=self.bus,
                                         validation_threshold=0.99)
        update_result = updater.update(train)
        validation = updater.validate(update_result["model_path"], test)
        self.assertFalse(validation["passed"])
        log_text = self.system_log.read_text(encoding="utf-8")
        self.assertIn("model_validation_failed", log_text)

    def test_rollback_restores_backup(self):
        # Update #1 creates the initial lineage; update #2 continues training
        # from it (weights move) and must be recoverable via rollback.
        self.updater.update(RLHF_DATASET)
        first_digest = _read_json(self.models_dir / "current_model.json")["weights_sha256"]
        self.updater.update(RLHF_DATASET)
        second_digest = _read_json(self.models_dir / "current_model.json")["weights_sha256"]
        self.assertNotEqual(first_digest, second_digest)  # continued training moved the weights
        rollback = self.updater.rollback()
        self.assertTrue(rollback["rolled_back"])
        restored = _read_json(self.models_dir / "current_model.json")
        self.assertEqual(restored["weights_sha256"], first_digest)

    def test_rollback_without_backups(self):
        result = self.updater.rollback()
        self.assertFalse(result["rolled_back"])
        self.assertEqual(result["reason"], "no_backups")

    def test_update_missing_dataset_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.updater.update("/nonexistent/samples.json")


if __name__ == "__main__":
    unittest.main()
