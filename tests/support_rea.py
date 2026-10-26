"""Gemeinsame Helfer fuer die Tests des REA-Subagenten.

Die Sandbox eines Limbs muss laut Policy **innerhalb** des Repositories liegen
(``sandbox_root`` wird gegen ``repo_root`` geprueft). Isolierte Testlaeufe
benutzen deshalb ein eigenes Arbeitsverzeichnis unter ``workspace/_tests/``, das
im ``tearDown`` wieder verschwindet -- nicht ``/tmp``, sonst greift die Policy
zu Recht.

Der REA-Limb startet echte Prozesse. Damit die Tests offline und ohne
26-MB-Installation laufen, wird ein **Stub-Einstiegspunkt** (``stub.mjs``) mit
einem gueltigen Installationsmarker hinterlegt. Getestet wird damit die
Mechanik des Limbs (Allowlist, argv, Policy, Artefakte, Timer) -- nicht REA
selbst; das uebernimmt ``scripts/rea_demo.py``.
"""

from __future__ import annotations

import json
import shutil
import unittest
import uuid
from pathlib import Path
from typing import Any

from core.config import NeuConfig
from core.kernel import Kernel, arm_timer
from core.protocol import Intent, Operations

from . import REPO_ROOT

STUB_JS = r"""
const args = process.argv.slice(2);
const command = args[0];
const joined = args.join(" ");
if (command === "--version") {
  process.stdout.write("9.9.9\n");
  process.exit(0);
}
if (joined.includes("broken-app")) {
  console.log(JSON.stringify({
    code: "provider_unavailable",
    category: "unavailable",
    message: "kein Analyse-Provider fuer dieses Ziel",
    remediation: { action: "Engine installieren oder anderes Ziel waehlen" }
  }));
  process.exit(3);
}
if (joined.includes("slow-app")) {
  setTimeout(() => {}, 60000);
} else {
  const payload = {
    evidence_id: "ev_stub_0001",
    operation: "analyze_javascript_application",
    predicate_type: "rea.javascript-application-analysis",
    confidence: "derived",
    provider: { id: "rea-javascript-application", version: "1" },
    subject: { name: "stub", format: "directory", digest: { sha256: "a".repeat(64) } },
    argv: args,
    normalized_result: {
      graph: {
        root_node_ids: ["n0"],
        nodes: [{ kind: "artifact" }, { kind: "javascript-module" }, { kind: "javascript-asset" }],
        edges: [{}, {}]
      },
      semantic_graph: {
        nodes: [
          { kind: "function", label: "f", identity: { module_path: "app.js" } },
          { kind: "call-site" },
          { kind: "module" }
        ],
        relations: [{}],
        unknowns: [{ reason: "dynamic-call" }, { reason: "dynamic-call" }, { reason: "ambiguous-target" }],
        coverage: { status: "partial" }
      },
      statistics: { relevant_files: 3, parsed_javascript_files: 1 },
      summary: { browser_windows: 0, ipc: 0, exposed_api_members: 1 }
    },
    limitations: ["Stub: statische Analyse ohne Ausfuehrung.", "Zweite Grenze."]
  };
  console.log(JSON.stringify(payload));
}
"""


def node_available() -> bool:
    return shutil.which("node") is not None


class ReaCase(unittest.TestCase):
    """Isolierte Konfiguration + Kernel; Sandbox unter ``workspace/_tests/``."""

    def setUp(self) -> None:
        self.workspace = REPO_ROOT / "workspace" / "_tests" / f"rea-{uuid.uuid4().hex[:10]}"
        self.runtime = self.workspace / "runtime"
        self.config = NeuConfig.load(REPO_ROOT, workspace_dir=self.workspace, runtime_dir=self.runtime)
        self.config.ensure_dirs()
        self.operations = Operations.load(self.config.protocol_dir / "operations.json")
        self.kernel = Kernel(self.config, self.operations)

    def tearDown(self) -> None:
        shutil.rmtree(self.workspace, ignore_errors=True)

    # ------------------------------------------------------------------ Aufbau
    def sandbox(self, agent: str = "agent-a") -> Path:
        return self.workspace / "subagents" / agent

    def sandbox_rel(self, agent: str = "agent-a") -> str:
        return self.config.relative(self.sandbox(agent))

    def build(
        self,
        operation: str,
        params: dict[str, Any] | None = None,
        *,
        agent: str = "agent-a",
        limb: str = "rea",
        allow_network: bool = False,
        dry_run: bool = False,
        deadline_s: float | None = 30.0,
        soft_deadline_s: float | None = 20.0,
        **overrides: Any,
    ) -> Intent:
        constraints = {
            "sandbox_root": self.sandbox_rel(agent),
            "allow_network": allow_network,
            "dry_run": dry_run,
        }
        base: dict[str, Any] = {
            "operation": operation,
            "params": dict(params or {}),
            "limb": limb,
            "goal": "Testauftrag fuer den REA-Subagenten",
            "deadline_s": deadline_s,
            "soft_deadline_s": soft_deadline_s,
            "constraints": constraints,
        }
        base.update(overrides)
        intent = self.kernel.build_intent(**base)  # type: ignore[arg-type]
        return arm_timer(intent, config=self.config)

    def fake_install(self, agent: str = "agent-a", *, version: str = "9.9.9") -> Path:
        """Legt einen Stub-Einstiegspunkt + gueltigen Marker in die Sandbox."""
        sandbox = self.sandbox(agent)
        install = sandbox / "rea"
        install.mkdir(parents=True, exist_ok=True)
        (install / "stub.mjs").write_text(STUB_JS, encoding="utf-8")
        marker = {
            "schema": "neu.rea-install/1",
            "source": "test",
            "repository": "",
            "ref": "",
            "package": "",
            "entrypoint": "stub.mjs",
            "version": version,
            "node": {"path": shutil.which("node") or "", "version": "test"},
            "pwntools": {"ok": False, "reason": "test"},
            "installed_at": "2026-01-01T00:00:00Z",
            "duration_s": 0.0,
            "steps": [],
        }
        (install / ".rea-install.json").write_text(json.dumps(marker, indent=2), encoding="utf-8")
        for name, content in (("app", "console.log(1)\n"), ("slow-app", "while (true) {}\n"), ("broken-app", "// x\n")):
            target = sandbox / "targets" / name
            target.mkdir(parents=True, exist_ok=True)
            (target / f"{name}.js").write_text(content, encoding="utf-8")
        return sandbox
