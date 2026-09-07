import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
import json
from pathlib import Path

from core.evaluation.define_eval import (
    define_eval,
    EvalPipeline,
    EvalConfig,
    EvalDataError,
    mean_aggregator,
)
from core.evaluation.evaluators import (
    correctness_evaluator,
    safety_evaluator,
    consistency_evaluator,
    weighted_aggregator,
)

RLHF_DATASET = os.path.join(os.path.dirname(__file__), "..", "..", "evals", "datasets", "rlhf_samples.json")


def _write_dataset(tmpdir, samples, name="dataset.json"):
    path = Path(tmpdir) / name
    with open(path, "w", encoding="utf-8") as f:
        json.dump(samples, f)
    return str(path)


class TestDefineEvalInterface(unittest.TestCase):
    def test_define_eval_returns_config(self):
        config = define_eval("rlhf_correctness", {"correctness": 1.0}, RLHF_DATASET, correctness_evaluator)
        self.assertIsInstance(config, EvalConfig)
        self.assertEqual(config.eval_name, "rlhf_correctness")
        self.assertEqual(config.threshold, 85.0)
        self.assertTrue(callable(config.evaluator_func))

    def test_define_eval_rejects_non_callable(self):
        with self.assertRaises(TypeError):
            define_eval("bad", {}, RLHF_DATASET, evaluator_func="not_callable")

    def test_custom_threshold(self):
        config = define_eval("t", {}, RLHF_DATASET, correctness_evaluator, threshold=40.0)
        self.assertEqual(config.threshold, 40.0)


class TestEvalPipeline(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.pipeline = EvalPipeline(evals_dir=str(Path(self.tmpdir) / "evals"))

    def test_run_on_real_rlhf_samples(self):
        config = define_eval("rlhf_correctness", {"correctness": 1.0}, RLHF_DATASET, correctness_evaluator)
        eval_result = self.pipeline.run(config)
        self.assertEqual(eval_result["eval_name"], "rlhf_correctness")
        self.assertEqual(eval_result["dataset_size"], 4)
        self.assertEqual(len(eval_result["results"]), 4)
        self.assertIsInstance(eval_result["aggregate_score"], float)
        self.assertTrue(0.0 <= eval_result["aggregate_score"] <= 100.0)
        self.assertIn("passed", eval_result)
        self.assertIn("audit_trail", eval_result)
        self.assertEqual(eval_result["audit_trail"]["samples_evaluated"], 4)

    def test_per_sample_scores_0_100(self):
        config = define_eval("safety", {}, RLHF_DATASET, safety_evaluator)
        eval_result = self.pipeline.run(config)
        for row in eval_result["results"]:
            self.assertGreaterEqual(row["score"], 0.0)
            self.assertLessEqual(row["score"], 100.0)

    def test_consistency_evaluator(self):
        config = define_eval("consistency", {}, RLHF_DATASET, consistency_evaluator)
        eval_result = self.pipeline.run(config)
        self.assertGreater(eval_result["aggregate_score"], 0.0)

    def test_custom_aggregator(self):
        samples = [
            {"id": "a", "agentOutput": "x", "expectedOutcome": "x", "feedbackScore": 1.0},
            {"id": "b", "agentOutput": "x", "expectedOutcome": "x", "feedbackScore": 0.0},
        ]
        dataset = _write_dataset(self.tmpdir, samples)
        config = define_eval("agg", {}, dataset, correctness_evaluator,
                             aggregator_func=lambda scores: max(scores))
        eval_result = self.pipeline.run(config)
        # Sample a: identical token sets -> F1 = 1.0 -> score 100.
        self.assertEqual(eval_result["aggregate_score"], 100.0)

    def test_save_result_default_naming(self):
        config = define_eval("saved_eval", {}, RLHF_DATASET, correctness_evaluator)
        eval_result = self.pipeline.run(config)
        path = self.pipeline.save_result(eval_result)
        self.assertTrue(Path(path).exists())
        self.assertIn("saved_eval", str(path))
        with open(path, "r", encoding="utf-8") as f:
            stored = json.load(f)
        self.assertEqual(stored["eval_name"], "saved_eval")

    def test_missing_dataset_raises(self):
        config = define_eval("missing", {}, "/nonexistent/dataset.json", correctness_evaluator)
        with self.assertRaises(EvalDataError):
            self.pipeline.run(config)

    def test_evaluator_error_becomes_zero_score(self):
        def bad_evaluator(sample):
            raise RuntimeError("boom")
        dataset = _write_dataset(self.tmpdir, [{"id": "s1"}])
        config = define_eval("boom", {}, dataset, bad_evaluator)
        eval_result = self.pipeline.run(config)
        self.assertEqual(eval_result["aggregate_score"], 0.0)
        self.assertEqual(eval_result["audit_trail"]["samples_errored"], 1)
        self.assertTrue(eval_result["results"][0]["reasoning"].startswith("evaluator_error"))

    def test_samples_dict_format(self):
        dataset = _write_dataset(self.tmpdir, {"samples": [{"id": "s1", "feedbackScore": 1.0}]}, "wrapped.json")
        config = define_eval("wrapped", {}, dataset, correctness_evaluator)
        eval_result = self.pipeline.run(config)
        self.assertEqual(eval_result["dataset_size"], 1)

    def test_weighted_aggregator_factory(self):
        aggregator = weighted_aggregator({"correctness": 0.5})
        self.assertEqual(aggregator([50.0, 100.0]), 75.0)


if __name__ == "__main__":
    unittest.main()
