"""Preference model updater (Phase 4 — RLHF Integration).

Learns a preference model from human feedback (`rlhf_samples.json` shaped
records) so the system can predict how a human would rate a candidate output
*before* dispatching it.

**Documented divergence (see Architect/docs/DIVERGENCES.md):** the TODO sketch
suggested ONNX weights; the learning core is stdlib-only, so the preference
model is a deterministic logistic regressor over hashed bag-of-words features
stored as JSON + SHA-256 (trainable/predictable without torch/onnx). The ONNX
regime model (`models/weights/omega_regime_16d.onnx`) remains untouched.

Storage:  `Architect/runtime/models/current_model.json`
          `Architect/runtime/models/updated_<timestamp>.json`
Backups:  `Architect/runtime/models/backups/`
Events:   `model_updated`, `model_validation_failed`
"""

import json
import hashlib
import logging
import datetime
import math
import random
import re
from pathlib import Path

logger = logging.getLogger(__name__)

VOCAB_SIZE = 256
_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


def _featurize(text: str) -> list:
    """Hashed bag-of-words feature indices for a piece of text."""
    tokens = _TOKEN_RE.findall((text or "").lower())
    return [int(hashlib.sha1(t.encode("utf-8")).hexdigest(), 16) % VOCAB_SIZE for t in tokens]


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    return math.exp(x) / (1.0 + math.exp(x))


def _sample_text(sample: dict) -> str:
    return " ".join(str(sample.get(k, "")) for k in ("prompt", "agentOutput", "expectedOutcome"))


def _sample_target(sample: dict) -> float:
    """Supervision target in [0, 1] from feedbackScore / humanFeedbackCategory."""
    if "feedbackScore" in sample:
        try:
            return max(0.0, min(1.0, float(sample["feedbackScore"])))
        except (TypeError, ValueError):
            pass
    category = sample.get("humanFeedbackCategory", "")
    return {"approved": 0.9, "modified": 0.5, "rejected": 0.1}.get(category, 0.5)


class PreferenceModelUpdater:
    """Load / update / validate / rollback the preference model."""

    def __init__(self, models_dir: str = "Architect/runtime/models", event_bus=None,
                 learning_rate: float = 0.05, epochs: int = 60, seed: int = 42,
                 validation_threshold: float = 0.5):
        self.models_dir = Path(models_dir)
        self.backups_dir = self.models_dir / "backups"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self.event_bus = event_bus
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.seed = seed
        self.validation_threshold = validation_threshold

    # ---- Model primitives -------------------------------------------------------

    def _empty_model(self) -> dict:
        return {
            "model_type": "preference_logistic_v1",
            "vocab_size": VOCAB_SIZE,
            "weights": [0.0] * VOCAB_SIZE,
            "bias": 0.0,
            "trained_samples": 0,
            "final_loss": None,
            "updated_at": None,
            "source_dataset": None,
        }

    def _predict_score(self, model: dict, text: str) -> float:
        feats = _featurize(text)
        weights = model["weights"]
        z = model["bias"]
        for idx in feats:
            z += weights[idx]
        return _sigmoid(z)

    def _digest(self, model: dict) -> str:
        payload = json.dumps({"w": model["weights"], "b": model["bias"]}, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # ---- Persistence --------------------------------------------------------------

    def load_model(self) -> dict:
        """Load the current model: latest `updated_*.json` wins, else `current_model.json`,
        else a fresh zero model."""
        candidates = sorted(self.models_dir.glob("updated_*.json"))
        current = self.models_dir / "current_model.json"
        path = candidates[-1] if candidates else (current if current.exists() else None)
        if path is None:
            logger.info("No persisted preference model found; starting from zero model.")
            return self._empty_model()
        with open(path, "r", encoding="utf-8") as f:
            model = json.load(f)
        logger.info("Preference model loaded from %s (trained_samples=%s)",
                    path, model.get("trained_samples"))
        return model

    def save_model(self, model: dict, filename: str) -> Path:
        model["weights_sha256"] = self._digest(model)
        path = self.models_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(model, f, indent=2, ensure_ascii=False)
        logger.info("Preference model saved: %s", path)
        return path

    # ---- Training -------------------------------------------------------------------

    def update(self, preference_data_path) -> dict:
        """Train on preference data and save `updated_<timestamp>.json`.

        Previous current model is backed up to `backups/`. Returns a result dict
        with `model_path`, `trained_samples`, `final_loss`.
        """
        dataset = self._load_dataset(preference_data_path)
        if not dataset:
            raise ValueError(f"No training samples found in {preference_data_path}")

        model = self.load_model()
        # Backup current model before overwriting the lineage.
        current = self.models_dir / "current_model.json"
        if current.exists():
            timestamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
            with open(current, "r", encoding="utf-8") as fsrc:
                payload = fsrc.read()
            with open(self.backups_dir / f"current_model_{timestamp}.json", "w", encoding="utf-8") as fdst:
                fdst.write(payload)

        rng = random.Random(self.seed)
        indices = list(range(len(dataset)))
        weights = model["weights"]
        bias = model["bias"]
        lr = self.learning_rate
        final_loss = None
        for _epoch in range(self.epochs):
            rng.shuffle(indices)
            epoch_loss = 0.0
            for i in indices:
                sample = dataset[i]
                feats = _featurize(_sample_text(sample))
                y = _sample_target(sample)
                pred = 0.0
                for idx in feats:
                    pred += weights[idx]
                pred += bias
                p = _sigmoid(pred)
                error = p - y
                for idx in feats:
                    weights[idx] -= lr * error
                bias -= lr * error
                epoch_loss += -(y * math.log(max(p, 1e-9)) + (1 - y) * math.log(max(1 - p, 1e-9)))
            final_loss = epoch_loss / len(dataset)

        model.update({
            "weights": weights,
            "bias": bias,
            "trained_samples": model.get("trained_samples", 0) + len(dataset),
            "final_loss": round(final_loss, 6),
            "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
            "source_dataset": str(preference_data_path),
        })
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        model_path = self.save_model(model, f"updated_{timestamp}.json")

        # Keep current_model.json pointing at the newest lineage for simple loads.
        with open(self.models_dir / "current_model.json", "w", encoding="utf-8") as f:
            json.dump(model, f, indent=2, ensure_ascii=False)

        return {
            "model_path": str(model_path),
            "trained_samples": len(dataset),
            "final_loss": model["final_loss"],
            "digest": model["weights_sha256"],
        }

    # ---- Validation / rollback ---------------------------------------------------------

    def validate(self, updated_model_path, test_dataset_path) -> dict:
        """Validate a model against a held-out dataset (MAE-based score in [0, 1]).

        Emits `model_updated` (score >= threshold) or `model_validation_failed`.
        """
        with open(updated_model_path, "r", encoding="utf-8") as f:
            model = json.load(f)
        dataset = self._load_dataset(test_dataset_path)
        if not dataset:
            raise ValueError(f"No validation samples found in {test_dataset_path}")
        absolute_errors = []
        for sample in dataset:
            pred = self._predict_score(model, _sample_text(sample))
            absolute_errors.append(abs(pred - _sample_target(sample)))
        mae = sum(absolute_errors) / len(absolute_errors)
        validation_score = round(max(0.0, 1.0 - mae), 4)
        passed = validation_score >= self.validation_threshold

        if self.event_bus:
            kind = "model_updated" if passed else "model_validation_failed"
            self.event_bus.emit(self.event_bus.build_event(
                event_kind=kind,
                job_id="preference_model",
                message=(f"Preference model validation score {validation_score} "
                         f"(threshold {self.validation_threshold})."),
                model_path=str(updated_model_path),
                validation_score=validation_score,
                mae=round(mae, 6),
            ))

        result = {
            "model_path": str(updated_model_path),
            "validation_score": validation_score,
            "mae": round(mae, 6),
            "threshold": self.validation_threshold,
            "passed": passed,
            "dataset_size": len(dataset),
        }
        logger.info("Preference model validation: score=%.4f passed=%s", validation_score, passed)
        return result

    def rollback(self) -> dict:
        """Restore the most recent backup into `current_model.json`."""
        backups = sorted(self.backups_dir.glob("current_model_*.json"))
        if not backups:
            logger.warning("Preference model rollback: no backups available.")
            return {"rolled_back": False, "reason": "no_backups"}
        latest = backups[-1]
        with open(latest, "r", encoding="utf-8") as fsrc:
            payload = fsrc.read()
        with open(self.models_dir / "current_model.json", "w", encoding="utf-8") as fdst:
            fdst.write(payload)
        logger.info("Preference model rolled back from %s", latest)
        return {"rolled_back": True, "restored_from": str(latest)}

    # ---- Helpers -----------------------------------------------------------------------

    @staticmethod
    def _load_dataset(dataset_path) -> list:
        path = Path(dataset_path)
        if not path.exists():
            # Fall back to repo-root-relative resolution (rlhf_samples.json lives at repo root).
            repo_root = Path(__file__).resolve().parents[3]
            fallback = repo_root / dataset_path
            if fallback.exists():
                path = fallback
        if not path.exists():
            raise FileNotFoundError(f"Preference dataset not found: {dataset_path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("samples"), list):
            return data["samples"]
        return []
