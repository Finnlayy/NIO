#!/usr/bin/env python3
"""End-to-End-Nachweis: REA-Subagent von null bis zur Rekonstruktion.

Der Ablauf ist absichtlich derselbe, den ein Mensch in der CLI tippen wuerde --
das Skript zeigt bei jedem Schritt den aequivalenten Befehl.

    1. Subagent anlegen                 subagent create
    2. REA in der Sandbox installieren  subagent install [--with-pwntools]
    3. Ziele importieren                subagent import
    4. Spiel analysieren                subagent run --op rea.analyze
    5. Binaerlayout analysieren         subagent run --op rea.analyze (ELF)
    6. Rekonstruktion pruefen           scripts/rea_recover_orbit.py

Exit 0 nur, wenn alle Schritte gelingen *und* die Rekonstruktion das Original
reproduziert. Alles andere ist ein Befund, kein Erfolg.

Beispiele:
    python3 scripts/rea_demo.py                  # nutzt eine bestehende Installation
    python3 scripts/rea_demo.py --install        # installiert (git) neu/frisch
    python3 scripts/rea_demo.py --install --with-pwntools
    python3 scripts/rea_demo.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.config import NeuConfig  # noqa: E402
from orchestrator.subagent import SubagentManager  # noqa: E402
from scripts.rea_recover_orbit import (  # noqa: E402  (Repo-Wurzel wird oben ergaenzt)
    DEFAULT_GAME,
    OrbitDodge,
    compare,
    load_evidence,
    recover_constants,
    recover_functions,
)

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "rea" / "orbit-dodge"
GAME_APP = FIXTURE / "app"


class Demo:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.config = NeuConfig.load(REPO_ROOT)
        self.manager = SubagentManager(self.config)
        self.steps: list[dict[str, Any]] = []
        self.ok = True
        self.sandbox = ""

    # ------------------------------------------------------------------ Ausgabe
    def say(self, message: str) -> None:
        if not self.args.json:
            print(message)

    def step(self, name: str, *, ok: bool, detail: dict[str, Any] | None = None, command: str = "") -> None:
        self.steps.append({"step": name, "ok": ok, "command": command, "detail": detail or {}})
        if self.args.json:
            return
        mark = "ok  " if ok else "FAIL"
        print(f"[{mark}] {name}")
        if command:
            print(f"       $ {command}")
        if detail:
            for key, value in detail.items():
                print(f"       {key}: {value}")
        print()

    # ------------------------------------------------------------------ Schritte
    def ensure_agent(self) -> None:
        command = f"python3 -m orchestrator subagent create {self.args.agent}"
        record = self.manager.ensure(self.args.agent)
        self.sandbox = record.sandbox
        self.step("Subagent angelegt", ok=True, command=command, detail={"sandbox": record.sandbox, "limb": record.limb})

    def install(self) -> None:
        status = self.manager.status(self.args.agent)
        installed = bool(status["rea"]["installed"])
        wants_pwntools = self.args.with_pwntools and not status["rea"]["pwntools"]
        if installed and not self.args.install and not wants_pwntools:
            self.step(
                "REA bereits installiert",
                ok=True,
                command=f"python3 -m orchestrator subagent install {self.args.agent}",
                detail={"version": status["rea"]["version"], "source": status["rea"]["source"]},
            )
            return
        command = f"python3 -m orchestrator subagent install {self.args.agent}"
        if self.args.with_pwntools:
            command += " --with-pwntools"
        if self.args.install:
            command += " --force"
        outcome = self.manager.install(
            self.args.agent,
            source=self.args.source,
            with_pwntools=self.args.with_pwntools,
            force=self.args.install,
            deadline_s=None,
        )
        output = outcome.attempts[-1].result.output if outcome.attempts else {}
        ok = outcome.ok and bool(output.get("installed"))
        self.ok = self.ok and ok
        self.step(
            "REA installiert" if ok else "REA-Installation fehlgeschlagen",
            ok=ok,
            command=command,
            detail={
                "status": outcome.status,
                "version": output.get("version"),
                "source": output.get("source"),
                "pwntools": (output.get("pwntools") or {}).get("ok"),
                "duration_s": output.get("duration_s"),
            },
        )

    def import_targets(self) -> None:
        targets = [("orbit-dodge", GAME_APP)]
        if not self.args.skip_native:
            targets.append(("orbit-native", FIXTURE / "native"))
        for name, source in targets:
            command = f"python3 -m orchestrator subagent import {self.args.agent} {source.relative_to(REPO_ROOT)} --name {name} --replace"
            try:
                manifest = self.manager.import_target(self.args.agent, source, name=name, replace=True)
            except Exception as exc:  # Demo berichtet, sie wirft nicht
                self.ok = False
                self.step(f"Import {name} fehlgeschlagen", ok=False, command=command, detail={"error": str(exc)})
                continue
            self.step(
                f"Ziel importiert: {name}",
                ok=True,
                command=command,
                detail={"files": manifest["files"], "bytes": manifest["bytes"], "sha256": manifest["sha256_root"][:24]},
            )

    def analyze_app(self) -> Path | None:
        params = {
            "command": "analyze-javascript-application",
            "target": "targets/orbit-dodge",
            "out": "out/orbit-dodge-evidence.json",
        }
        command = (
            f"python3 -m orchestrator subagent run {self.args.agent} --goal 'Spiel rekonstruieren' "
            f"--op rea.analyze --params '{json.dumps(params)}'"
        )
        outcome = self.manager.run(
            self.args.agent,
            goal="Orbit Dodge: Anwendungsgraph rekonstruieren",
            operation="rea.analyze",
            params=params,
            deadline_s=600.0,
            soft_deadline_s=570.0,
            title="JavaScript-Anwendung",
            objective="Statische Rekonstruktion der Anwendung inkl. Evidence.",
        )
        output = outcome.attempts[-1].result.output if outcome.attempts else {}
        ok = bool(outcome.ok and output.get("evidence_id"))
        self.ok = self.ok and ok
        self.step(
            "Anwendung analysiert" if ok else "Analyse fehlgeschlagen",
            ok=ok,
            command=command,
            detail={
                "status": outcome.status,
                "evidence_id": output.get("evidence_id"),
                "raw_bytes": (output.get("raw") or {}).get("bytes"),
                "raw_path": (output.get("raw") or {}).get("path"),
                "summary": (output.get("summary") or {}).get("semantic_graph"),
            },
        )
        raw = (output.get("raw") or {}).get("path")
        return REPO_ROOT / raw if raw else None

    def analyze_binary(self) -> None:
        if self.args.skip_native:
            return
        status = self.manager.status(self.args.agent)
        if not status["rea"]["pwntools"]:
            self.step(
                "Binaerlayout uebersprungen (pwntools-venv fehlt)",
                ok=True,
                command=f"python3 -m orchestrator subagent install {self.args.agent} --with-pwntools",
                detail={"grund": "ELF-Provider braucht REA_PWNTOOLS_PYTHON"},
            )
            return
        params = {"command": "inspect-binary-layout", "target": "targets/orbit-native/orbit-game"}
        command = (
            f"python3 -m orchestrator subagent run {self.args.agent} --goal 'Binaerlayout' "
            f"--op rea.analyze --params '{json.dumps(params)}'"
        )
        outcome = self.manager.run(
            self.args.agent,
            goal="Orbit Dodge: ELF-Layout des nativen Zwillings",
            operation="rea.analyze",
            params=params,
            deadline_s=300.0,
            soft_deadline_s=280.0,
            title="Binaerlayout",
        )
        output = outcome.attempts[-1].result.output if outcome.attempts else {}
        layout = (output.get("summary") or {}).get("binary_layout") or {}
        ok = bool(outcome.ok and layout)
        self.ok = self.ok and ok
        self.step(
            "Binaerlayout analysiert" if ok else "Binaerlayout fehlgeschlagen",
            ok=ok,
            command=command,
            detail={
                "status": outcome.status,
                "format": layout.get("format"),
                "sections": (layout.get("sections") or {}).get("count"),
                "symbols": (layout.get("symbols") or {}).get("named"),
                "mitigations": layout.get("mitigations"),
            },
        )

    def recover(self, evidence: Path | None) -> None:
        if evidence is None or not evidence.is_file():
            self.ok = False
            self.step("Rekonstruktion", ok=False, detail={"grund": f"keine Evidence: {evidence}"})
            return
        evidence_payload = load_evidence(evidence)
        constants = recover_constants(evidence_payload)
        functions = recover_functions(evidence_payload)
        port = OrbitDodge(constants["values"])
        results = compare(port, DEFAULT_GAME, [1, 2, 42, 1337, 20260101], [300, 900, 1200])
        failures = [item for item in results if not item["ok"]]
        ok = not failures
        self.ok = self.ok and ok
        self.step(
            "Rekonstruktion reproduziert das Original" if ok else "Rekonstruktion weicht ab",
            ok=ok,
            command="python3 scripts/rea_recover_orbit.py",
            detail={
                "cases": len(results),
                "failures": len(failures),
                "constants": {k: constants["values"][k] for k in ("comboWindowMs", "comboStep", "maxCombo", "spawnEveryMs")},
                "functions": functions["count"],
                "unknowns": functions["unknowns"],
            },
        )

    def run(self) -> int:
        self.say("=" * 78)
        self.say("REA-Subagent: Demo vom leeren Knoten bis zur Rekonstruktion")
        self.say("=" * 78)
        self.say("")
        self.ensure_agent()
        self.install()
        self.import_targets()
        evidence = self.analyze_app()
        self.analyze_binary()
        self.recover(evidence if not self.args.skip_recovery else None)
        if self.args.json:
            print(json.dumps({"ok": self.ok, "agent": self.args.agent, "sandbox": self.sandbox, "steps": self.steps}, ensure_ascii=False, indent=2))
            return 0 if self.ok else 1
        self.say("=" * 78)
        self.say("ERGEBNIS: " + ("alle Schritte bestanden." if self.ok else "mindestens ein Schritt ist fehlgeschlagen."))
        self.say(f"Status:  python3 -m orchestrator --json subagent status {self.args.agent}")
        self.say("=" * 78)
        return 0 if self.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="REA-Subagent end-to-end demonstrieren")
    parser.add_argument("--agent", default="rea-lab", help="Subagent-ID (Default: rea-lab)")
    parser.add_argument("--install", action="store_true", help="Installation erzwingen (force)")
    parser.add_argument("--source", choices=("git", "npm"), default="git", help="Installationsquelle")
    parser.add_argument("--with-pwntools", action="store_true", help="pwntools-venv fuer den ELF-Provider anlegen")
    parser.add_argument("--skip-native", action="store_true", help="Binaer-Teil ueberspringen")
    parser.add_argument("--skip-recovery", action="store_true", help="nur analysieren, nicht rekonstruieren")
    parser.add_argument("--json", action="store_true", help="Maschinenlesbarer Bericht")
    args = parser.parse_args(argv)
    return Demo(args).run()


if __name__ == "__main__":
    sys.exit(main())
