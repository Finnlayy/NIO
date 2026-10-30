from __future__ import annotations

import json
import unittest
from pathlib import Path

from core.schemacheck import validate
from orchestrator.kanban.models import (
    AuditEntry,
    Experience,
    KanbanEvent,
    KanbanTask,
    RustLimb,
    RustLimbRequest,
    RustLimbResponse,
    ToolCall,
    Worker,
)

BASE_DIR = Path(__file__).parent.parent

class TestKanbanContracts(unittest.TestCase):
    def setUp(self) -> None:
        self.schemas_dir = BASE_DIR / "protocol" / "kanban"
        self.fixtures_dir = BASE_DIR / "tests" / "fixtures" / "kanban"

        self.models_map = {
            "task": KanbanTask,
            "worker": Worker,
            "experience": Experience,
            "audit_entry": AuditEntry,
            "event": KanbanEvent,
            "tool_call": ToolCall,
            "rust_limb_request": RustLimbRequest,
            "rust_limb_response": RustLimbResponse,
            "rust_limb": RustLimb,
        }

    def _load_json(self, path: Path) -> dict:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_fixtures_against_schemas_and_models(self) -> None:
        for schema_name, model_cls in self.models_map.items():
            schema_path = self.schemas_dir / f"{schema_name}.schema.json"
            schema = self._load_json(schema_path)

            fixtures = []
            for f in self.fixtures_dir.glob("*.json"):
                if f.name.startswith(f"{schema_name}_"):
                    if schema_name == "rust_limb" and ("request" in f.name or "response" in f.name):
                        continue
                    fixtures.append(f)

            self.assertTrue(len(fixtures) >= 2, f"Mindestens 2 Fixtures fuer {schema_name} erwartet")

            for fixture_path in fixtures:
                fixture = self._load_json(fixture_path)

                # 1. Validate against schema
                errors = validate(fixture, schema)
                self.assertEqual(errors, [], f"Schema-Validierung fehlgeschlagen fuer {fixture_path.name}")

                # 2. X.from_dict(fixture).to_dict() == fixture
                obj = model_cls.from_dict(fixture)
                self.assertEqual(obj.to_dict(), fixture, f"De/Serialisierung veraendert Daten fuer {fixture_path.name}")

                # 3. set(schema["properties"]) == set(X(...).to_dict())
                self.assertEqual(
                    set(schema["properties"]),
                    set(obj.to_dict()),
                    f"Drift zwischen Dataclass und Schema in {schema_name}"
                )

    def test_schema_rejects_additional_properties(self) -> None:
        schema = self._load_json(self.schemas_dir / "task.schema.json")
        fixture = self._load_json(self.fixtures_dir / "task_minimal.json")
        fixture["extra_field"] = 42

        errors = validate(fixture, schema)
        self.assertTrue(any("extra_field" in e or "unbekannter Schluessel" in e or "additionalProperties" in e for e in errors),
                        "Schema sollte zusaetzliche Felder ablehnen")

if __name__ == "__main__":
    unittest.main()
