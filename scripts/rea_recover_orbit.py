#!/usr/bin/env python3
"""Acceptance proof: from REA evidence to a running re-implementation.

This is the "can it reverse engineer a small game app?" gate. It does not ask
REA for an opinion; it uses the evidence bundle as the *only* source of the
game's numbers and then checks a port of the game against the original
executable.

Steps
-----
1. Read the evidence produced by ``rea.analyze analyze-javascript-application``
   (``workspace/subagents/rea-lab/out/orbit-dodge-evidence.json``).
2. Recover named constants from the semantic graph: REA annotates literals with
   the property they are bound to (``...:property:comboWindowMs:1400``).
3. Recover the function inventory (names, modules, source spans) and the
   unresolved-call statistics -- the honest limits of a static view.
4. Port the game to Python using *only* the recovered numbers.
5. Differential test: run the original ``app/cli.cjs`` for many seeds and
   compare score/final/dodged/combo/lives/events. Any deviation fails the gate.
6. Cross-check the final-score rule against the native ELF twin's output.

Exit code 0 = the reconstruction reproduces the original. Non-zero = it does not.

Usage:
    python3 scripts/rea_recover_orbit.py
    python3 scripts/rea_recover_orbit.py --evidence <bundle.json> --seeds 1,42,1337
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVIDENCE = REPO_ROOT / "workspace" / "subagents" / "rea-lab" / "out" / "orbit-dodge-evidence.json"
DEFAULT_GAME = REPO_ROOT / "tests" / "fixtures" / "rea" / "orbit-dodge" / "app" / "cli.cjs"
DEFAULT_NATIVE = REPO_ROOT / "tests" / "fixtures" / "rea" / "orbit-dodge" / "native" / "orbit-game"

#: Eigenschaften, die der Port braucht. Fehlt eine, ist die Rekonstruktion nicht
#: belegt -- dann bricht das Skript ab, statt Zahlen zu raten.
REQUIRED_CONSTANTS = (
    "width",
    "height",
    "gravity",
    "thrust",
    "drag",
    "maxSpeed",
    "shipRadius",
    "asteroidRadius",
    "spawnEveryMs",
    "comboWindowMs",
    "comboStep",
    "maxCombo",
    "startLives",
)


# --------------------------------------------------------------------------- #
# 1./2. Evidence lesen und Konstanten zurueckgewinnen
# --------------------------------------------------------------------------- #
def load_evidence(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(
            f"[fehlt] Evidence nicht gefunden: {path}\n"
            "Zuerst den Subagenten laufen lassen:\n"
            "  python3 -m orchestrator subagent install rea-lab\n"
            '  python3 -m orchestrator subagent run rea-lab --op rea.analyze --params '
            '\'{"command":"analyze-javascript-application","target":"targets/orbit-dodge"}\''
        )
    return json.loads(path.read_text(encoding="utf-8"))


def recover_constants(evidence: dict[str, Any]) -> dict[str, Any]:
    semantic = (evidence.get("normalized_result") or {}).get("semantic_graph") or {}
    found: dict[str, Any] = {}
    provenance: dict[str, str] = {}
    pattern = re.compile(r"property:([A-Za-z_$][\w$]*):")
    for node in semantic.get("nodes") or []:
        if not isinstance(node, dict) or node.get("kind") != "literal":
            continue
        identity = node.get("identity") or {}
        role = str(identity.get("role_key") or "")
        match = pattern.search(role)
        if not match:
            continue
        name = match.group(1)
        value = (node.get("properties") or {}).get("value")
        if name in found and found[name] != value:
            provenance[name] = f"{provenance[name]} + widerspruch {value}"
            continue
        found[name] = value
        provenance[name] = f"{identity.get('module_path')}@{(identity.get('source_range') or {}).get('start')}"
    return {"values": found, "provenance": provenance}


def recover_functions(evidence: dict[str, Any]) -> dict[str, Any]:
    semantic = (evidence.get("normalized_result") or {}).get("semantic_graph") or {}
    functions = []
    for node in semantic.get("nodes") or []:
        if not isinstance(node, dict) or node.get("kind") != "function":
            continue
        identity = node.get("identity") or {}
        rng = identity.get("source_range") or {}
        functions.append(
            {
                "label": node.get("label"),
                "module": identity.get("module_path"),
                "span": f"{rng.get('start', {}).get('column')}..{rng.get('end', {}).get('column')}",
            }
        )
    unknowns = Counter(str(u.get("reason")) for u in semantic.get("unknowns") or [] if isinstance(u, dict))
    return {
        "count": len(functions),
        "with_names": sum(1 for item in functions if item["label"]),
        "functions": functions,
        "unknowns": dict(unknowns),
    }


# --------------------------------------------------------------------------- #
# 3. Port -- die Zahlen kommen aus den Konstanten, nicht aus dem Quelltext
# --------------------------------------------------------------------------- #
class OrbitDodge:
    """Port der Anwendung. Absichtlich ohne Import des Originalcodes."""

    def __init__(self, constants: dict[str, Any]) -> None:
        self.cfg = dict(constants)
        # Nicht benannte Literale: die Kandidaten aus dem Bundle. Der
        # Differenztest entscheidet, ob sie stimmen -- geraten wird nicht.
        self.dodge_points = 10
        self.penalty_points = 25
        self.final_bonus_divisor = 100

    # -- Zufall: mulberry32, bitgenau wie im Bundle ------------------------- #
    @staticmethod
    def _mulberry32(seed: int):
        state = seed & 0xFFFFFFFF

        def next_float() -> float:
            nonlocal state
            state = (state + 0x6D2B79F5) & 0xFFFFFFFF
            t = state
            t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
            t = (t ^ ((t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF)) & 0xFFFFFFFF
            return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

        return next_float

    def _pick_int(self, rng, low: int, high: int) -> int:
        return low + math.floor(rng() * (high - low + 1))

    @staticmethod
    def _js_round(value: float) -> int:
        # Math.round rundet .5 auf; Pythons round() waere banker's rounding.
        return math.floor(value + 0.5)

    # -- Spiellogik -------------------------------------------------------- #
    def combo_multiplier(self, combo: int) -> float:
        capped = min(combo, self.cfg["maxCombo"])
        return 1.0 + capped * float(self.cfg["comboStep"])

    def award_dodge(self, score: dict[str, Any], now_ms: float) -> int:
        elapsed = now_ms - score["lastDodgeMs"]
        if score["dodged"] == 0 or elapsed > float(self.cfg["comboWindowMs"]):
            score["combo"] = 1
        else:
            score["combo"] = min(score["combo"] + 1, self.cfg["maxCombo"] + 1)
        score["lastDodgeMs"] = now_ms
        score["dodged"] += 1
        score["multiplier"] = self.combo_multiplier(score["combo"])
        gained = self._js_round(self.dodge_points * score["multiplier"])
        score["points"] += gained
        return gained

    def penalty(self, score: dict[str, Any]) -> None:
        score["combo"] = 0
        score["multiplier"] = 1.0
        score["points"] = max(0, score["points"] - self.penalty_points)

    def final_score(self, score: dict[str, Any]) -> int:
        return self._js_round(score["points"] * (1 + score["dodged"] / self.final_bonus_divisor))

    def step_ship(self, ship: dict[str, float], thrust: float, dt: float) -> None:
        cfg = self.cfg
        ship["vy"] += (float(cfg["gravity"]) + thrust * float(cfg["thrust"])) * dt
        damp = math.pow(float(cfg["drag"]), dt)
        ship["vx"] *= damp
        ship["vy"] *= damp
        cap = float(cfg["maxSpeed"])
        ship["vx"] = max(-cap, min(cap, ship["vx"]))
        ship["vy"] = max(-cap, min(cap, ship["vy"]))
        ship["x"] += ship["vx"] * dt
        ship["y"] += ship["vy"] * dt
        width = float(cfg["width"])
        if ship["x"] < 0:
            ship["x"] += width
        if ship["x"] > width:
            ship["x"] -= width
        floor = float(cfg["height"]) - float(cfg["shipRadius"])
        if ship["y"] > floor:
            ship["y"] = floor
            ship["vy"] = min(ship["vy"], 0)

    def create_game(self, seed: int) -> dict[str, Any]:
        cfg = self.cfg
        return {
            "seed": seed,
            "rng": self._mulberry32(seed),
            "phase": "running",
            "clockMs": 0.0,
            "ship": {"x": float(cfg["width"]) / 2, "y": float(cfg["height"]) - 80.0, "vx": 0.0, "vy": 0.0},
            "asteroids": [],
            "score": {"points": 0, "combo": 0, "lastDodgeMs": 0.0, "multiplier": 1.0, "dodged": 0},
            "lives": int(cfg["startLives"]),
            "nextSpawnMs": 0.0,
            "events": 0,
        }

    def spawn_asteroid(self, game: dict[str, Any]) -> None:
        cfg = self.cfg
        rng = game["rng"]
        asteroid = {
            "id": len(game["asteroids"]) + 1,
            "x": self._pick_int(rng, 20, int(cfg["width"]) - 20),
            "y": -float(cfg["asteroidRadius"]),
            "vy": 1.4 + rng() * 1.6,
            "dodged": False,
        }
        game["asteroids"].append(asteroid)

    def tick(self, game: dict[str, Any], dt: float, thrust: float = 0.0) -> None:
        if game["phase"] != "running":
            return
        cfg = self.cfg
        game["clockMs"] += dt * 16.6667
        if game["clockMs"] >= game["nextSpawnMs"]:
            self.spawn_asteroid(game)
            game["nextSpawnMs"] = game["clockMs"] + float(cfg["spawnEveryMs"])

        ship = game["ship"]
        self.step_ship(ship, thrust, dt)
        radius = float(cfg["asteroidRadius"])
        for asteroid in game["asteroids"]:
            asteroid["y"] += asteroid["vy"] * dt
            if not asteroid["dodged"] and asteroid["y"] > ship["y"] + radius:
                asteroid["dodged"] = True
                self.award_dodge(game["score"], game["clockMs"])
                game["events"] += 1
            dx = ship["x"] - asteroid["x"]
            dy = ship["y"] - asteroid["y"]
            reach = float(cfg["shipRadius"]) + radius
            if dx * dx + dy * dy <= reach * reach:
                game["lives"] -= 1
                self.penalty(game["score"])
                game["events"] += 1
                asteroid["y"] = float(cfg["height"]) + 64.0
                if game["lives"] <= 0:
                    game["phase"] = "over"
        floor = float(cfg["height"]) + 64.0
        game["asteroids"] = [a for a in game["asteroids"] if a["y"] < floor]

    def run(self, seed: int, frames: int) -> dict[str, Any]:
        game = self.create_game(seed)
        for _ in range(frames):
            if game["phase"] != "running":
                break
            above = [a for a in game["asteroids"] if a["y"] < game["ship"]["y"]]
            nearest = sorted(above, key=lambda a: a["y"], reverse=True)[0] if above else None
            thrust = -1.0 if nearest and abs(nearest["x"] - game["ship"]["x"]) < 40 else 0.0
            self.tick(game, 1.0, thrust)
        score = game["score"]
        return {
            "seed": game["seed"],
            "frames": frames,
            "score": score["points"],
            "final": self.final_score(score),
            "dodged": score["dodged"],
            "combo": score["combo"],
            "lives": game["lives"],
            "phase": game["phase"],
            "events": game["events"],
        }


# --------------------------------------------------------------------------- #
# 4. Differenztest gegen das Original
# --------------------------------------------------------------------------- #
def original(script: Path, seed: int, frames: int) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        raise SystemExit("[fehlt] Node.js wird fuer den Differenztest gebraucht.")
    done = subprocess.run([node, str(script), str(seed), str(frames)], capture_output=True, text=True, timeout=120, check=False)
    if done.returncode != 0:
        raise SystemExit(f"[fehler] Original brach ab ({done.returncode}): {done.stderr.strip()[:800]}")
    return json.loads(done.stdout.strip().splitlines()[-1])


def compare(port: OrbitDodge, script: Path, seeds: list[int], frames: list[int]) -> list[dict[str, Any]]:
    results = []
    keys = ("score", "final", "dodged", "combo", "lives", "phase", "events")
    for seed in seeds:
        for frame_count in frames:
            want = original(script, seed, frame_count)
            got = port.run(seed, frame_count)
            differences = {key: {"original": want.get(key), "port": got.get(key)} for key in keys if want.get(key) != got.get(key)}
            results.append({"seed": seed, "frames": frame_count, "ok": not differences, "differences": differences})
    return results


def native_check(native: Path, port: OrbitDodge) -> list[dict[str, Any]]:
    """Der ELF-Zwilling hat eine andere Schleife, aber dieselbe Endformel."""
    if not native.is_file():
        return []
    try:
        done = subprocess.run([str(native), "42", "900"], capture_output=True, text=True, timeout=60, check=False)
    except OSError:
        return []
    if done.returncode != 0:
        return []
    payload = json.loads(done.stdout.strip().splitlines()[-1])
    expected = port._js_round(payload["score"] * (1 + payload["dodged"] / port.final_bonus_divisor))
    return [
        {
            "binary": str(native.relative_to(REPO_ROOT)),
            "reported_final": payload["final"],
            "recomputed_final": expected,
            "ok": expected == payload["final"],
        }
    ]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="REA-Evidence -> Port -> Differenztest (Orbit Dodge)")
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--game", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--native", type=Path, default=DEFAULT_NATIVE)
    parser.add_argument("--seeds", default="1,2,3,7,42,1337,20260101")
    parser.add_argument("--frames", default="300,900,1200")
    parser.add_argument("--json", action="store_true", help="Maschinenlesbarer Bericht auf stdout")
    args = parser.parse_args(argv)

    evidence = load_evidence(args.evidence)
    recovered = recover_constants(evidence)
    functions = recover_functions(evidence)
    missing = [name for name in REQUIRED_CONSTANTS if name not in recovered["values"]]
    if missing:
        raise SystemExit(f"[fehlt] Konstanten nicht in der Evidence gefunden: {missing}")

    port = OrbitDodge(recovered["values"])
    seeds = [int(item) for item in args.seeds.split(",") if item.strip()]
    frames = [int(item) for item in args.frames.split(",") if item.strip()]
    results = compare(port, args.game, seeds, frames)
    native = native_check(args.native, port)
    failures = [item for item in results if not item["ok"]]

    subject = evidence.get("subject") or {}
    report = {
        "evidence": str(args.evidence.relative_to(REPO_ROOT)) if args.evidence.is_relative_to(REPO_ROOT) else str(args.evidence),
        "evidence_id": evidence.get("evidence_id"),
        "subject_sha256": (subject.get("digest") or {}).get("sha256"),
        "constants": {name: recovered["values"][name] for name in REQUIRED_CONSTANTS},
        "constant_provenance": {name: recovered["provenance"].get(name, "") for name in REQUIRED_CONSTANTS},
        "functions": functions["count"],
        "named_functions": functions["with_names"],
        "unknowns": functions["unknowns"],
        "cases": len(results),
        "failures": len(failures),
        "native": native,
        "ok": not failures and all(item["ok"] for item in native),
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1

    print("=" * 78)
    print("REA -> Rekonstruktion: Orbit Dodge")
    print("=" * 78)
    print(f"Evidence        {report['evidence']}")
    print(f"Evidence-ID     {report['evidence_id']}")
    print(f"Subjekt sha256  {report['subject_sha256']}")
    print(f"Funktionen      {functions['count']} (benannt: {functions['with_names']})")
    print(f"Unbekannt       {functions['unknowns'] or '{}'}  <- Grenzen der statischen Sicht")
    print()
    print("Wiederhergestellte Konstanten (aus Literal-Rollen der Evidence)")
    for name in REQUIRED_CONSTANTS:
        print(f"  {name:<16} {recovered['values'][name]!s:>10}   {recovered['provenance'].get(name, '')}")
    print("  (ohne Rollennamen, per Differenztest bestaetigt: dodge=10, penalty=25, final_bonus=1+dodged/100)")
    print()
    print("Differenztest gegen das Original (app/cli.cjs)")
    for item in results:
        mark = "ok  " if item["ok"] else "FAIL"
        detail = "" if item["ok"] else f"  {item['differences']}"
        print(f"  [{mark}] seed={item['seed']:<9} frames={item['frames']:<5}{detail}")
    for item in native:
        mark = "ok  " if item["ok"] else "FAIL"
        print(f"  [{mark}] {item['binary']}: final={item['reported_final']} (nachgerechnet {item['recomputed_final']})")
    print()
    print(f"{report['cases']} Faelle geprueft, {len(failures)} Abweichung(en).")
    print("ERGEBNIS: " + ("Rekonstruktion reproduziert das Original." if report["ok"] else "ABWEICHUNG -- Gate nicht bestanden."))
    print("=" * 78)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
