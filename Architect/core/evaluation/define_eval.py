"""Evaluation pipelines (`defineEval`) — Phase 4 RLHF Integration.

Python counterpart of blueprint `src/learning/defineEval.ts`: replaces static
heuristics with structured, weighted scorers built on real historical
`rlhf_samples` records.

    eval_cfg = define_eval("rlhf_correctness", criteria, dataset_path, evaluator)
    result   = EvalPipeline().run(eval_cfg)

Results are persisted to `Architect/runtime/learning/evals/<eval_name>_<ts>.json`.
"""

import json
import logging
import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DATASET_PATH = "evals/datasets/rlhf_samples.json"
DEFAULT_EVALS_DIR = "Architect/runtime/learning/evals"

# Repo root (evals/datasets/rlhf_samples.json lives at the repository root);
# resolved from this module so defaults work from any working directory.
_REPO_ROOT = Path(__file__).resolve().parents[3]


def resolve_dataset_path(dataset_path) -> str:
    """Resolve a dataset path as-is, then relative to the repository root."""
    path = Path(dataset_path)
    if path.exists():
        return str(path)
    fallback = _REPO_ROOT / dataset_path
    if fallback.exists():
        return str(fallback)
    return str(dataset_path)


class EvalDataError(RuntimeError):
    """Raised when a dataset cannot be loaded for an evaluation."""


class EvalConfig:
    """Immutable configuration produced by `define_eval`."""

    def __init__(self, eval_name: str, criteria: dict, dataset_path: str,
                 evaluator_func, aggregator_func=None, threshold: float = 85.0,
                 created_at: str = None):
        self.eval_name = eval_name
        self.criteria = criteria or {}
        self.dataset_path = dataset_path
        self.evaluator_func = evaluator_func
        self.aggregator_func = aggregator_func
        self.threshold = threshold
        self.created_at = created_at or datetime.datetime.utcnow().isoformat() + "Z"

    def to_dict(self) -> dict:
        return {
            "eval_name": self.eval_name,
            "criteria": self.criteria,
            "dataset_path": str(self.dataset_path),
            "threshold": self.threshold,
            "created_at": self.created_at,
            "aggregator": getattr(self.aggregator_func, "__name__", "mean"),
        }


def define_eval(eval_name: str, criteria: dict, dataset_path: str,
                evaluator_func, aggregator_func=None, threshold: float = 85.0) -> EvalConfig:
    """Create an `EvalConfig` for the pipeline.

    Args:
        eval_name: unique evaluation name.
        criteria: free-form criteria description, e.g.
            {"metrics": {"correctness": 0.6, "safety": 0.3, "consistency": 0.1}}.
        dataset_path: JSON dataset (list of samples or {"samples": [...]}).
        evaluator_func: callable(sample) -> float | dict {score, passed, reasoning}.
        aggregator_func: callable(list[float]) -> float (default: arithmetic mean).
        threshold: pass mark for the aggregate score (0-100).
    """
    if not callable(evaluator_func):
        raise TypeError("evaluator_func must be callable")
    if aggregator_func is not None and not callable(aggregator_func):
        raise TypeError("aggregator_func must be callable")
    return EvalConfig(eval_name, criteria, dataset_path, evaluator_func,
                      aggregator_func, threshold)


def mean_aggregator(scores: list) -> float:
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _normalize_metric_result(value):
    """Evaluator may return a number or {score, passed, reasoning}."""
    if isinstance(value, dict):
        score = value.get("score", 0.0)
        reasoning = value.get("reasoning", "")
        passed = value.get("passed")
        try:
            score = float(score)
        except (TypeError, ValueError):
            score = 0.0
        return score, bool(passed), str(reasoning)
    try:
        return float(value), None, ""
    except (TypeError, ValueError):
        return 0.0, None, "non-numeric evaluator result"


class EvalPipeline:
    """Load dataset -> evaluate each sample -> aggregate -> persist result."""

    def __init__(self, evals_dir: str = DEFAULT_EVALS_DIR):
        self.evals_dir = Path(evals_dir)
        self.evals_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def load_dataset(dataset_path) -> list:
        path = Path(resolve_dataset_path(dataset_path))
        if not path.exists():
            raise EvalDataError(f"Dataset not found: {dataset_path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("samples"), list):
            return data["samples"]
        raise EvalDataError(f"Dataset format unsupported (expected list or {{samples: []}}): {dataset_path}")

    def run(self, eval_config: EvalConfig, dataset_path=None, rlhf_context=None) -> dict:
        """Execute an evaluation; returns the EvalResult dict (with audit trail)."""
        dataset = self.load_dataset(dataset_path or eval_config.dataset_path)
        results = []
        audit_trail = []
        for index, sample in enumerate(dataset):
            try:
                score, passed, reasoning = _normalize_metric_result(eval_config.evaluator_func(sample))
            except Exception as exc:
                logger.error("Evaluator failed on sample %d of %s: %s",
                             index, eval_config.eval_name, exc)
                score, passed, reasoning = 0.0, False, f"evaluator_error: {exc}"
            sample_id = sample.get("id", f"sample_{index:04d}") if isinstance(sample, dict) else f"sample_{index:04d}"
            results.append(score)
            audit_trail.append({
                "sample_id": sample_id,
                "score": round(score, 4),
                "passed": passed if passed is not None else score >= eval_config.threshold,
                "reasoning": reasoning[:300],
            })

        aggregator = eval_config.aggregator_func or mean_aggregator
        try:
            aggregate_score = float(aggregator(results))
        except Exception as exc:
            logger.error("Aggregator failed for %s: %s", eval_config.eval_name, exc)
            aggregate_score = 0.0

        eval_result = {
            "eval_name": eval_config.eval_name,
            "dataset_path": str(dataset_path or eval_config.dataset_path),
            "dataset_size": len(dataset),
            "results": audit_trail,
            "aggregate_score": round(aggregate_score, 4),
            "threshold": eval_config.threshold,
            "passed": aggregate_score >= eval_config.threshold,
            "criteria": eval_config.criteria,
            "rlhf_context_used": len(rlhf_context) if rlhf_context is not None else 0,
            "evaluated_at": datetime.datetime.utcnow().isoformat() + "Z",
            "audit_trail": {
                "aggregator": getattr(aggregator, "__name__", "custom"),
                "evaluator": getattr(eval_config.evaluator_func, "__name__", "custom"),
                "samples_evaluated": len(results),
                "samples_errored": sum(1 for a in audit_trail if a["reasoning"].startswith("evaluator_error")),
            },
        }
        logger.info("Eval '%s' complete: aggregate=%.2f passed=%s (n=%d)",
                    eval_config.eval_name, aggregate_score, eval_result["passed"], len(dataset))
        return eval_result

    def save_result(self, eval_result: dict, output_path=None) -> Path:
        """Persist an EvalResult; default path embeds eval_name + timestamp."""
        if output_path is None:
            timestamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
            safe_name = str(eval_result.get("eval_name", "eval")).replace("/", "_")
            output_path = self.evals_dir / f"{safe_name}_{timestamp}.json"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(eval_result, f, indent=2, ensure_ascii=False)
        logger.info("Eval result saved: %s", output_path)
        return output_path
