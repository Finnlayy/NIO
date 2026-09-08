"""Outcome ingestion (Phase 4 — RLHF Integration).

Reads execution result files, validates them against
`Architect/schemas/outcome.schema.json`, persists normalized outcomes to
`Architect/runtime/learning/outcomes/` and emits `execution_complete` events
on the event bus. This is the entry point of the RLHF data flow:

    execution -> outcome ingestion -> feedback -> model update -> validation

Aligned with blueprint `src/learning/` (`Outcome` in `schemas.ts`,
`input.ts` ingestion) and `OMEGA_JULES_TODO.md` Phase 4.
"""

import json
import logging
from pathlib import Path

from core.schema_utils import SchemaInvalid, load_schema, validate_against_schema, default_schema_path

logger = logging.getLogger(__name__)

DEFAULT_SCHEMA_PATH = default_schema_path("outcome.schema.json")
VALID_VERDICTS = ["accept", "reject", "escalate", "timeout"]


class OutcomeParser:
    """Parse and validate outcome records against outcome.schema.json."""

    def __init__(self, schema_path: str = DEFAULT_SCHEMA_PATH):
        self.schema_path = schema_path
        self.schema = load_schema(schema_path)

    def validate_dict(self, outcome: dict) -> dict:
        """Validate an outcome dict; returns it normalized or raises SchemaInvalid."""
        if not isinstance(outcome, dict):
            raise SchemaInvalid(f"Outcome must be a dict, got {type(outcome).__name__}.")
        errors = validate_against_schema(outcome, self.schema)
        if errors:
            raise SchemaInvalid("; ".join(errors))
        return outcome

    def parse(self, file_path) -> dict:
        """Read a result file (JSON), validate against the schema, return the Outcome dict.

        Raises SchemaInvalid on validation failure, FileNotFoundError if missing,
        json.JSONDecodeError on malformed JSON.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Outcome file not found: {file_path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        validated = self.validate_dict(data)
        logger.info("Outcome parsed and validated: %s (job_id=%s, verdict=%s)",
                    file_path, validated.get("job_id"), validated.get("verdict"))
        return validated


class OutcomeIngestion:
    """Pipeline: result files -> validated outcomes -> store + event bus."""

    def __init__(self, event_bus=None, outcomes_dir: str = "Architect/runtime/learning/outcomes",
                 schema_path: str = DEFAULT_SCHEMA_PATH):
        self.parser = OutcomeParser(schema_path=schema_path)
        self.event_bus = event_bus
        self.outcomes_dir = Path(outcomes_dir)
        self.outcomes_dir.mkdir(parents=True, exist_ok=True)

    def ingest(self, outcome: dict) -> dict:
        """Validate an in-memory outcome, persist and emit `execution_complete`."""
        validated = self.parser.validate_dict(outcome)
        return self._persist_and_emit(validated)

    def ingest_file(self, file_path) -> dict:
        """Read a result file, validate, persist and emit `execution_complete`."""
        validated = self.parser.parse(file_path)
        return self._persist_and_emit(validated)

    def ingest_directory(self, dir_path, pattern: str = "*.json") -> list:
        """Ingest every result file matching `pattern` in a directory."""
        ingested = []
        for file_path in sorted(Path(dir_path).glob(pattern)):
            try:
                ingested.append(self.ingest_file(file_path))
            except (SchemaInvalid, json.JSONDecodeError) as exc:
                logger.error("Skipping invalid outcome file %s: %s", file_path, exc)
        return ingested

    def _persist_and_emit(self, validated: dict) -> dict:
        job_id = validated.get("job_id", "unknown_job")
        outcome_path = self.outcomes_dir / f"{job_id}.json"
        with open(outcome_path, "w", encoding="utf-8") as f:
            json.dump(validated, f, indent=2, ensure_ascii=False)
        logger.info("Outcome stored: %s", outcome_path)

        if self.event_bus:
            self.event_bus.emit(self.event_bus.build_event(
                event_kind="execution_complete",
                job_id=job_id,
                intent_id=validated.get("intent_id"),
                limb=validated.get("limb"),
                clock_s=validated.get("clock_s"),
                message=f"Outcome ingested (verdict={validated.get('verdict')}).",
                outcome_id=job_id,
                verdict=validated.get("verdict"),
            ))
        return validated
