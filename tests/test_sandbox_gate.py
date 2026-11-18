"""Tests fuer tools/selfcode/sandbox_gate.py (Audit 2026-11-08, SC-05).

Jeder Test baut ein eigenes Mini-Live-Repo plus Git-Worktree in einem Temp-Verzeichnis
und ruft das Gate als echten Subprozess auf. Das echte Repo und dessen ``workspace``
werden nie angefasst; die Test-Suite des echten Repos wird nicht rekursiv gestartet.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE = REPO_ROOT / "tools" / "selfcode" / "sandbox_gate.py"

GIT_ENV = {
    "GIT_AUTHOR_NAME": "gate-test", "GIT_AUTHOR_EMAIL": "gate-test@example.invalid",
    "GIT_COMMITTER_NAME": "gate-test", "GIT_COMMITTER_EMAIL": "gate-test@example.invalid",
    "GIT_CONFIG_NOSYSTEM": "1",
}

LIVE_FILES = {
    "app.py": "def value():\n    return 1\n",
    "core/__init__.py": "",
    "core/kernel.py": "KERNEL = True\n",
    "orchestrator/__init__.py": "",
    "orchestrator/__main__.py": textwrap.dedent("""\
        import sys
        sys.exit(0 if "status" in sys.argv and "--runtime-dir" in sys.argv else 3)
        """),
    "tests/__init__.py": "",
    "tests/test_app.py": textwrap.dedent("""\
        import os
        import time
        import unittest

        import app


        class AppTest(unittest.TestCase):
            def test_value(self):
                time.sleep(float(os.environ.get("GATE_FIXTURE_SLEEP", "0")))
                self.assertEqual(app.value(), 1)
        """),
    "neu.config.json": json.dumps({"human_only_globs": ["core/kernel.py", "neu.config.json"]}),
}


def _load_gate_module():
    spec = importlib.util.spec_from_file_location("sandbox_gate_under_test", GATE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses brauchen das Modul in sys.modules
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


class SandboxGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="sandbox-gate-test-")
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.live = base / "live"
        self.wt = base / "wt"
        self.live.mkdir()
        self.git(self.live, "init", "-q", "-b", "main")
        self.write(self.live, LIVE_FILES)
        self.commit(self.live, "live")
        self.git(self.live, "worktree", "add", "-q", str(self.wt), "-b", "kanban/r1")

    # --- Hilfen ---------------------------------------------------------------

    def git(self, repo: Path, *args: str) -> str:
        env = {**os.environ, **GIT_ENV}
        proc = subprocess.run(["git", "-C", str(repo), "-c", "commit.gpgsign=false", *args],
                              capture_output=True, text=True, env=env, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def write(self, root: Path, files: dict[str, str]) -> None:
        for rel, content in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def commit(self, repo: Path, msg: str) -> None:
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-q", "-m", msg)

    def worker_commits(self, files: dict[str, str]) -> None:
        self.write(self.wt, files)
        self.commit(self.wt, "worker")

    def run_gate(self, *extra: str, worktree: Path | None = None, env: dict[str, str] | None = None):
        argv = [sys.executable, str(GATE), "--worktree", str(worktree or self.wt),
                "--run-id", "r1", "--live-repo", str(self.live), *extra]
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=60,
                              env={**os.environ, **(env or {})}, check=False)
        lines = proc.stdout.splitlines()
        self.assertEqual(len(lines), 1, f"genau eine JSON-Zeile erwartet:\n{proc.stdout}\n{proc.stderr}")
        return proc.returncode, json.loads(lines[0])

    def statuses(self, report: dict) -> dict[str, str]:
        return {s["name"]: s["status"] for s in report["stages"]}

    # --- Faelle ---------------------------------------------------------------

    def test_harmlose_aenderung_besteht_alle_stufen(self) -> None:
        self.worker_commits({"feature.py": "def neu():\n    return 42\n"})
        code, report = self.run_gate()
        self.assertEqual(code, 0, report)
        self.assertTrue(report["passed"])
        self.assertIsNone(report["failed_stage"])
        self.assertEqual(self.statuses(report),
                         {"policy": "passed", "compile": "passed", "unittest": "passed", "smoke": "passed"})
        self.assertEqual(report["changed_files"], ["feature.py"])
        self.assertEqual(report["run_id"], "r1")

    def test_kaputter_code_faellt_in_den_live_tests_durch(self) -> None:
        self.worker_commits({"app.py": "def value():\n    return 2\n"})
        code, report = self.run_gate()
        self.assertEqual(code, 1)
        self.assertEqual(report["failed_stage"], "unittest")
        self.assertEqual(self.statuses(report)["smoke"], "skipped")

    def test_testaenderung_ist_policy_rot(self) -> None:
        # Klassischer Reward-Hack: Code kaputt, Test passend umgeschrieben.
        self.worker_commits({
            "app.py": "def value():\n    return 2\n",
            "tests/test_app.py": "import unittest\nclass T(unittest.TestCase):\n    def test_x(self):\n        pass\n",
        })
        code, report = self.run_gate()
        self.assertEqual(code, 1)
        self.assertEqual(report["failed_stage"], "policy")
        self.assertIn("tests/test_app.py", report["stages"][0]["output_tail"])

    def test_geloeschter_test_ist_policy_rot(self) -> None:
        self.git(self.wt, "rm", "-q", "tests/test_app.py")
        self.commit(self.wt, "worker loescht test")
        code, report = self.run_gate()
        self.assertEqual(code, 1)
        self.assertEqual(report["failed_stage"], "policy")

    def test_gate_selbst_ist_geschuetzt(self) -> None:
        self.worker_commits({"tools/selfcode/sandbox_gate.py": "import sys\nsys.exit(0)\n"})
        code, report = self.run_gate()
        self.assertEqual(code, 1)
        self.assertEqual(report["failed_stage"], "policy")

    def test_human_only_aus_live_config_ist_geschuetzt(self) -> None:
        self.worker_commits({"core/kernel.py": "KERNEL = False\n"})
        code, report = self.run_gate()
        self.assertEqual(code, 1)
        self.assertEqual(report["failed_stage"], "policy")
        self.assertIn("core/kernel.py", report["stages"][0]["output_tail"])

    def test_live_tests_ersetzen_worktree_tests(self) -> None:
        # Ohne Policy-Stufe (Schutzliste leer) muss das Gate trotzdem rot sein,
        # weil es die Tests aus dem Live-Repo nimmt, nicht die umgeschriebenen.
        self.worker_commits({
            "app.py": "def value():\n    return 2\n",
            "tests/test_app.py": "import unittest\nclass T(unittest.TestCase):\n    def test_x(self):\n        pass\n",
        })
        gate = _load_gate_module()
        gate.load_protected_globs = lambda _live: []
        with contextlib.redirect_stderr(io.StringIO()):
            report = gate.run_gate(self.wt.resolve(), "r1", live_repo=self.live.resolve(), timeout_s=60)
        self.assertFalse(report["passed"])
        self.assertEqual(self.statuses(report)["policy"], "passed")
        self.assertEqual(report["failed_stage"], "unittest")

    def test_syntaxfehler_stoppt_bei_compile(self) -> None:
        self.worker_commits({"feature.py": "def broken(:\n"})
        code, report = self.run_gate()
        self.assertEqual(code, 1)
        self.assertEqual(report["failed_stage"], "compile")
        self.assertTrue(any("feature.py" in line for line in report["stages"][1]["output_tail"]))
        self.assertEqual(self.statuses(report)["unittest"], "skipped")
        self.assertEqual(self.statuses(report)["smoke"], "skipped")

    def test_kaputter_start_ist_smoke_rot(self) -> None:
        self.worker_commits({"orchestrator/__main__.py": "import sys\nsys.exit(1)\n"})
        code, report = self.run_gate()
        self.assertEqual(code, 1)
        self.assertEqual(report["failed_stage"], "smoke")

    def test_geprueft_wird_nur_der_committete_stand(self) -> None:
        self.worker_commits({"feature.py": "X = 1\n"})
        (self.wt / "app.py").write_text("def value(:\n", encoding="utf-8")  # uncommittet
        code, report = self.run_gate()
        self.assertEqual(code, 0, report)

    def test_timeout_ist_rot(self) -> None:
        self.worker_commits({"feature.py": "X = 1\n"})
        code, report = self.run_gate("--timeout", "1.5", env={"GATE_FIXTURE_SLEEP": "10"})
        self.assertEqual(code, 1)
        self.assertEqual(report["failed_stage"], "unittest")
        self.assertTrue(report["stages"][2]["timed_out"])

    def test_kein_git_repo_ist_rot(self) -> None:
        plain = Path(self._tmp.name) / "plain"
        plain.mkdir()
        code, report = self.run_gate(worktree=plain)
        self.assertEqual(code, 1)
        self.assertFalse(report["passed"])
        self.assertTrue(report["error"])

    def test_fehlender_worktree_ist_usage_fehler(self) -> None:
        code, report = self.run_gate(worktree=Path(self._tmp.name) / "gibt-es-nicht")
        self.assertEqual(code, 2)
        self.assertFalse(report["passed"])


if __name__ == "__main__":
    unittest.main()
