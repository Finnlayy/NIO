#!/usr/bin/env python3
"""Fremdes Spiel, keine Quellen: reicht REA fuer eine Rekonstruktion?

Der Orbit-Dodge-Fixture ist ein selbst gebautes Ziel -- er beweist, dass die
Kette funktioniert, aber nicht, dass sie an einem *fremden* Artefakt greift.
Dieses Skript schliesst die Luecke mit einem echten Drittanbieter-Spiel:

1. **Holen** -- einen festen Commit von ``jakesgordon/javascript-tetris`` (MIT)
   klonen. Nichts wird vendort; das Ziel liegt unter ``workspace/_external/``
   (git-ignoriert) und wird bei Bedarf neu gebaut.
2. **Ausliefern, wie es ausgeliefert wird** -- das inline-Skript aus
   ``index.html`` extrahieren und mit esbuild minifizieren. Der Subagent sieht
   danach nur ``dist/`` (Bundle + Vendor-Datei + Seite), keine Quellen.
3. **Analysieren** -- ``rea.analyze analyze-javascript-application`` im
   Subagenten ``rea-lab``; Evidence landet in dessen ``out/``.
4. **Zurueckgewinnen** -- Konstanten aus der Evidence (Rollen-Keys wie
   ``speed:property:decrement:0.005``), die Baustein-Tabelle aus dem Artefakt
   (gegen die Rollen-Keys ``size``/``color`` geprueft), Funktionen aus dem
   semantischen Graph.
5. **Pruefen** -- ein Python-Port des Spiels muss den *ausgelieferten* Bundle
   Bit fuer Bit reproduzieren: gleiche Punktzahl, gleiche Reihen, gleiches
   Brett (SHA-256) ueber mehrere Seeds und Frame-Zahlen. Der Bundle laeuft dafuer
   in ``scripts/tetris_harness.cjs`` (Canvas-/DOM-Attrappe, gesetzter PRNG).

Der Port ist absichtlich nicht "schoen": er bildet auch die Eigenheiten des
Originals ab (Reihe 0 wird nie geprueft, ``dt``-Akkumulation, Bag aus 4x7
Teilen, Spawn-Spalte per ``Math.round``). Genau daran scheitert eine
Rekonstruktion, die nur die offensichtlichen Konstanten abschreibt.

Exit 0 = Analyse + Rekonstruktion stimmen. Exit 1 = Abweichung. Exit 2 = das
Ziel konnte nicht geholt/gebaut werden.

Aufruf:
    python3 scripts/rea_probe_tetris.py                # holen, bauen, analysieren, pruefen
    python3 scripts/rea_probe_tetris.py --reuse         # vorhandene Evidence/Bundle nutzen
    python3 scripts/rea_probe_tetris.py --seeds 7,42 --bot-frames 6000 --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.config import NeuConfig  # noqa: E402
from orchestrator.subagent import SubagentManager  # noqa: E402

UPSTREAM = "https://github.com/jakesgordon/javascript-tetris.git"
PINNED_COMMIT = "e5c0c42f7dac0f3514a55eff656c6e22e95d68ed"
TARGET_NAME = "tetris-bundle"
ESBUILD = "esbuild@0.25.10"

EXTERNAL_ROOT = REPO_ROOT / "workspace" / "_external"
HARNESS = REPO_ROOT / "scripts" / "tetris_harness.cjs"


# --------------------------------------------------------------------------- #
# 1. Holen und so bauen, wie das Spiel ausgeliefert wird
# --------------------------------------------------------------------------- #
def run(argv: list[str], *, cwd: Path | None = None, timeout: float = 600.0) -> subprocess.CompletedProcess[str]:
    done = subprocess.run(argv, cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout, check=False)
    if done.returncode != 0:
        raise SystemExit(
            f"[fehlt] {' '.join(argv[:3])} ... -> {done.returncode}\n"
            f"stdout: {done.stdout[-1500:]}\nstderr: {done.stderr[-1500:]}"
        )
    return done


def fetch_source(dest: Path, *, ref: str = PINNED_COMMIT) -> dict[str, Any]:
    """Klonen (nur den festen Commit) -- idempotent."""
    head = dest / ".git"
    if head.is_dir():
        current = run(["git", "-C", str(dest), "rev-parse", "HEAD"]).stdout.strip()
        if current.startswith(ref):
            return {"path": str(dest), "commit": current, "reused": True}
        shutil.rmtree(dest, ignore_errors=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "init", "-q", str(dest)])
    run(["git", "-C", str(dest), "remote", "add", "origin", UPSTREAM])
    run(["git", "-C", str(dest), "fetch", "--depth", "1", "origin", ref], timeout=900.0)
    run(["git", "-C", str(dest), "checkout", "-q", "FETCH_HEAD"])
    commit = run(["git", "-C", str(dest), "rev-parse", "HEAD"]).stdout.strip()
    return {"path": str(dest), "commit": commit, "reused": False}


def extract_game_script(index_html: Path) -> str:
    html = index_html.read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
    if not scripts:
        raise SystemExit(f"[fehlt] kein inline-<script> in {index_html}")
    return cast(str, max(scripts, key=len))


def build_bundle(source_dir: Path, build_dir: Path) -> dict[str, Any]:
    """Inline-Spiel -> eigenstaendiges, minifiziertes Bundle + Seite."""
    game = extract_game_script(source_dir / "index.html")
    build_dir.mkdir(parents=True, exist_ok=True)
    src = build_dir / "game.src.js"
    src.write_text(game, encoding="utf-8")

    dist = build_dir / "dist"
    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir()

    # ``--tsconfig-raw={}``: dieses Repository hat eine strikte tsconfig.json.
    # esbuild wuerde sie sonst auf die .js-Datei anwenden, ``"use strict"``
    # voranstellen und damit das Spiel beim Start brechen (es setzt ein
    # implizites Global ``now``). Der Bundle soll sich verhalten wie die Seite,
    # nicht wie dieses Repository.
    run(["npx", "--yes", ESBUILD, str(src), "--minify", "--target=es2020",
         "--tsconfig-raw={}", "--legal-comments=none", f"--outfile={dist / 'game.min.js'}"],
        cwd=build_dir, timeout=600.0)
    for name in ("stats.js", "texture.jpg"):
        if (source_dir / name).is_file():
            shutil.copy2(source_dir / name, dist / name)

    html = (source_dir / "index.html").read_text(encoding="utf-8")
    html = re.sub(r"<script>.*?</script>", '<script src="game.min.js"></script>', html, count=1, flags=re.S)
    (dist / "index.html").write_text(html, encoding="utf-8")

    files = sorted(p for p in dist.rglob("*") if p.is_file())
    return {
        "dist": str(dist),
        "source_bytes": len(game),
        "files": [
            {"name": str(p.relative_to(dist)), "bytes": p.stat().st_size,
             "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in files
        ],
    }


# --------------------------------------------------------------------------- #
# 2. Analysieren (Subagent, eigene Sandbox)
# --------------------------------------------------------------------------- #
def analyse(manager: SubagentManager, agent: str, dist: Path) -> tuple[dict[str, Any], Path]:
    manifest = manager.import_target(agent, dist, name=TARGET_NAME, replace=True)
    params = {
        "command": "analyze-javascript-application",
        "target": f"targets/{TARGET_NAME}",
        "out": f"out/{TARGET_NAME}-evidence.json",
    }
    outcome = manager.run(
        agent,
        goal="Fremdes Spiel: Anwendungsgraph aus dem ausgelieferten Bundle",
        operation="rea.analyze",
        params=params,
        deadline_s=600.0,
        soft_deadline_s=580.0,
        title="Tetris-Bundle",
        objective="Statische Rekonstruktion eines fremden Spiel-Bundles ohne Quellen.",
    )
    output = outcome.attempts[-1].result.output if outcome.attempts else {}
    raw = (output.get("raw") or {}).get("path")
    if not raw:
        raise SystemExit(f"[fehlt] Analyse lieferte keine Evidence (status={outcome.status})")
    evidence = REPO_ROOT / raw
    return {"status": outcome.status, "target": manifest, "summary": output.get("summary"), "evidence": str(evidence)}, evidence


# --------------------------------------------------------------------------- #
# 3. Zurueckgewinnen: nur aus der Evidence
# --------------------------------------------------------------------------- #
#: Was der Port mindestens braucht. Fehlt etwas, wird nicht geraten.
REQUIRED_ROLES = ("nx", "ny", "start", "decrement", "min")

_ROLE_NOISE = {"binding", "property", "literal", "scope", "program", "function", "variable",
               "expression", "module", "parameter", "call-site"}


def role_name(role: str) -> str | None:
    """``...:binding:speed:property:decrement:0.005`` -> ``decrement``.

    Der Rollen-Key ist eine Kette aus Bereich, Bindung und Eigenschaft; der
    naechste Bezeichner vor dem Wert ist der Name, unter dem der Wert im
    Programm steht.
    """
    tokens = role.split(":")[:-1]
    for token in reversed(tokens):
        if token in _ROLE_NOISE:
            continue
        if re.fullmatch(r"[A-Za-z_$][\w$]*", token):
            return token
    return None


def _semantic(evidence: dict[str, Any]) -> dict[str, Any]:
    return (evidence.get("normalized_result") or {}).get("semantic_graph") or {}


def _literal_nodes(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    semantic = _semantic(evidence)
    return [n for n in semantic.get("nodes") or [] if isinstance(n, dict) and n.get("kind") == "literal"]


def recover_constants(evidence: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    provenance: dict[str, str] = {}
    for node in _literal_nodes(evidence):
        identity = node.get("identity") or {}
        role = str(identity.get("role_key") or "")
        name = role_name(role)
        if not name:
            continue
        values.setdefault(name, (node.get("properties") or {}).get("value"))
        provenance.setdefault(name, f"{(identity.get('module_path') or '')}#{role}")
    for name in REQUIRED_ROLES:
        if name not in values:
            raise SystemExit(f"[fehlt] Rolle '{name}' nicht in der Evidence -- Rekonstruktion waere geraten.")
    return {"values": values, "provenance": provenance}


def recover_piece_roles(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Rollen-Keys der Bausteine: ``binding:t:property:size:3`` -> ``t.size = 3``."""
    out: dict[str, dict[str, Any]] = {}
    for node in _literal_nodes(evidence):
        role = str((node.get("identity") or {}).get("role_key") or "")
        match = re.search(r"binding:([A-Za-z_$][\w$]*):property:(size|color):", role)
        if not match:
            continue
        out.setdefault(match.group(1), {})[match.group(2)] = (node.get("properties") or {}).get("value")
    return out


@dataclass
class PieceTable:
    """Die 7 Bausteine, gelesen aus dem *Artefakt* (nicht aus den Quellen)."""

    order: list[str]
    sizes: dict[str, int]
    masks: dict[str, list[int]]
    colors: dict[str, str]

    def digest(self) -> str:
        payload = json.dumps(
            {"order": self.order, "sizes": self.sizes, "masks": self.masks, "colors": self.colors},
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()


def recover_pieces(bundle: Path) -> PieceTable:
    """Baugroessen, Rotationsmasken, Farben und Bag-Reihenfolge aus dem Bundle.

    Ein 6-KB-Bundle ist kein Quelltext: die Tabelle steht als
    ``i={size:4,blocks:[3840,...],color:"cyan"}`` und der Beutel als
    ``pieces=[i,i,i,i,j,...]``. Beides ist ein Muster im Artefakt, und der
    Differenztest beweist anschliessend, dass es die richtige Deutung ist.
    """
    text = bundle.read_text(encoding="utf-8")
    declarations = re.findall(
        r'([A-Za-z_$][\w$]*)\s*=\s*\{\s*size\s*:\s*(\d+)\s*,\s*blocks\s*:\s*\[([0-9,\s]+)\]\s*,\s*color\s*:\s*"([^"]+)"',
        text,
    )
    if not declarations:
        raise SystemExit(f"[fehlt] keine Baustein-Tabelle in {bundle}")
    sizes, masks, colors = {}, {}, {}
    for name, size, blocks, color in declarations:
        sizes[name] = int(size)
        masks[name] = [int(value) for value in blocks.replace(" ", "").split(",") if value]
        colors[name] = color

    bag_match = re.search(r"pieces\s*=\s*\[([A-Za-z_$][\w$]*(?:\s*,\s*[A-Za-z_$][\w$]*)*)\]", text)
    if not bag_match:
        raise SystemExit(f"[fehlt] keine Bag-Reihenfolge in {bundle}")
    names = [part.strip() for part in bag_match.group(1).split(",")]
    order = list(dict.fromkeys(names))
    unknown = [name for name in order if name not in masks]
    if unknown:
        raise SystemExit(f"[fehlt] Bag nennt unbekannte Bausteine: {unknown}")
    return PieceTable(order=order, sizes=sizes, masks=masks, colors=colors)


def cross_check(table: PieceTable, roles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Die Evidence muss dieselben Groessen/Farben nennen wie das Artefakt."""
    checked, mismatches = 0, []
    for name, values in roles.items():
        if name not in table.sizes:
            continue
        if "size" in values:
            checked += 1
            if int(values["size"]) != table.sizes[name]:
                mismatches.append(f"{name}.size evidence={values['size']} artefakt={table.sizes[name]}")
        if "color" in values:
            checked += 1
            if str(values["color"]).strip('"') != table.colors[name]:
                mismatches.append(f"{name}.color evidence={values['color']} artefakt={table.colors[name]}")
    if mismatches:
        raise SystemExit(f"[fehlt] Evidence und Artefakt widersprechen sich: {mismatches}")
    return {"checked": checked, "pieces": len(table.sizes), "mismatches": 0}


def recover_functions(evidence: dict[str, Any]) -> dict[str, Any]:
    semantic = _semantic(evidence)
    functions = []
    for node in semantic.get("nodes") or []:
        if not isinstance(node, dict) or node.get("kind") != "function":
            continue
        identity = node.get("identity") or {}
        functions.append({"label": node.get("label"), "module": identity.get("module_path")})
    return {"count": len(functions), "names": sorted({str(f["label"]) for f in functions if f["label"]})}


# --------------------------------------------------------------------------- #
# 4. Der Port -- nur mit den zurueckgewonnenen Zahlen
# --------------------------------------------------------------------------- #
MASK32 = 0xFFFFFFFF


class Mulberry32:
    """Der PRNG, mit dem der Harness ``Math.random`` ersetzt (bitgleich zu JS)."""

    def __init__(self, seed: int) -> None:
        self.state = seed & MASK32

    def __call__(self) -> float:
        self.state = (self.state + 0x6D2B79F5) & MASK32
        t = self.state
        t = ((t ^ (t >> 15)) * (t | 1)) & MASK32
        t = (t ^ ((t + (((t ^ (t >> 7)) * (t | 61)) & MASK32)) & MASK32)) & MASK32
        return ((t ^ (t >> 14)) & MASK32) / 4294967296.0


def js_round(value: float) -> int:
    return math.floor(value + 0.5)


@dataclass
class Piece:
    key: str
    direction: int
    x: int
    y: int


@dataclass
class Tetris:
    """Port des Spiels, gebaut aus der Evidence (Zahlen) und dem Artefakt (Tabelle)."""

    nx: int
    ny: int
    start: float
    decrement: float
    minimum: float
    seed: int
    table: PieceTable
    score_per_piece: int = 10
    line_base: int = 100

    def __post_init__(self) -> None:
        self.rand = Mulberry32(self.seed)
        self.blocks: list[list[str | None]] = []
        self.actions: list[int] = []
        self.bag: list[str] = []
        self.current: Piece | None = None
        self.next: Piece | None = None
        self.score = 0
        self.rows = 0
        self.step = self.start
        self.dt = 0.0
        self.playing = False

    # -- Geometrie ---------------------------------------------------------
    def each_block(self, key: str, x: int, y: int, direction: int):
        mask = self.table.masks[key][direction]
        row = col = 0
        bit = 0x8000
        while bit > 0:
            if mask & bit:
                yield x + col, y + row
            col += 1
            if col == 4:
                col = 0
                row += 1
            bit >>= 1

    def occupied(self, key: str, x: int, y: int, direction: int) -> bool:
        for bx, by in self.each_block(key, x, y, direction):
            if bx < 0 or bx >= self.nx or by < 0 or by >= self.ny or self.get_block(bx, by):
                return True
        return False

    def get_block(self, x: int, y: int) -> str | None:
        if x < 0 or x >= len(self.blocks):
            return None
        column = self.blocks[x]
        if y < 0 or y >= len(column):
            return None
        return column[y]

    def set_block(self, x: int, y: int, value: str | None) -> None:
        while len(self.blocks) <= x:
            self.blocks.append([])
        column = self.blocks[x]
        while len(column) <= y:
            column.append(None)
        column[y] = value

    # -- Zufall ------------------------------------------------------------
    def random_piece(self) -> Piece:
        if not self.bag:
            self.bag = [key for key in self.table.order for _ in range(4)]
        index = int(self.rand() * (len(self.bag) - 1))
        key = self.bag.pop(index)
        x = js_round(self.rand() * (self.nx - self.table.sizes[key]))
        return Piece(key, 0, x, 0)

    # -- Zustand -----------------------------------------------------------
    def set_rows(self, value: int) -> None:
        self.rows = value
        self.step = max(self.minimum, self.start - self.decrement * value)

    def reset(self) -> None:
        self.dt = 0.0
        self.actions.clear()
        self.blocks = []
        self.set_rows(0)
        self.score = 0
        self.current = self.next or self.random_piece()
        self.next = self.random_piece()

    def load(self) -> None:
        """Was beim Laden des Bundles passiert: ``run()`` -> ``reset()`` + erster Frame."""
        self.reset()
        self.update(0.0)

    def play(self) -> None:
        self.reset()
        self.playing = True

    def lose(self) -> None:
        self.playing = False

    # -- Bewegung ----------------------------------------------------------
    def move(self, direction: int) -> bool:
        assert self.current is not None
        x, y = self.current.x, self.current.y
        if direction == 1:
            x += 1
        elif direction == 3:
            x -= 1
        elif direction == 2:
            y += 1
        if not self.occupied(self.current.key, x, y, self.current.direction):
            self.current.x, self.current.y = x, y
            return True
        return False

    def rotate(self) -> None:
        assert self.current is not None
        new_direction = 0 if self.current.direction == 3 else self.current.direction + 1
        if not self.occupied(self.current.key, self.current.x, self.current.y, new_direction):
            self.current.direction = new_direction

    def drop(self) -> None:
        assert self.current is not None
        if self.move(2):
            return
        self.score += self.score_per_piece
        for x, y in self.each_block(self.current.key, self.current.x, self.current.y, self.current.direction):
            self.set_block(x, y, self.current.key)
        self.remove_lines()
        self.current = self.next
        self.next = self.random_piece()
        self.actions.clear()
        assert self.current is not None
        if self.occupied(self.current.key, self.current.x, self.current.y, self.current.direction):
            self.lose()

    def remove_lines(self) -> None:
        x_count, y, cleared = self.nx, self.ny, 0
        while y > 0:  # Original: for(y=ny; y>0; --y) -- Reihe 0 wird nie geprueft
            if all(self.get_block(x, y) for x in range(x_count)):
                self.remove_line(y)
                y += 1
                cleared += 1
            y -= 1
        if cleared:
            self.set_rows(self.rows + cleared)
            self.score += self.line_base * (2 ** (cleared - 1))  # 1:100 2:200 3:400 4:800

    def remove_line(self, n: int) -> None:
        for y in range(n, -1, -1):
            for x in range(self.nx):
                self.set_block(x, y, None if y == 0 else self.get_block(x, y - 1))

    def handle(self, action: int | None) -> None:
        if action == 3:
            self.move(3)
        elif action == 1:
            self.move(1)
        elif action == 0:
            self.rotate()
        elif action == 2:
            self.drop()  # die Taste ist ein Soft-Drop, kein Schritt: sie legt am Boden sofort ab

    def update(self, idt: float) -> None:
        if not self.playing:
            return
        action = self.actions.pop(0) if self.actions else None
        self.handle(action)
        self.dt += idt
        if self.dt > self.step:
            self.dt -= self.step
            self.drop()

    # -- Planung (nur fuer den Bot; das Spiel entscheidet weiterhin selbst) --
    def board_copy(self) -> list[list[str | None]]:
        return [list(column) for column in self.blocks]

    def can_place(self, key: str, x: int, y: int, rotation: int) -> bool:
        for bx, by in self.each_block(key, x, y, rotation):
            if bx < 0 or bx >= self.nx or by < 0 or by >= self.ny or self.get_block(bx, by):
                return False
        return True

    def landing_y(self, key: str, x: int, rotation: int) -> int | None:
        if not self.can_place(key, x, 0, rotation):
            return None
        y = 0
        while self.can_place(key, x, y + 1, rotation):
            y += 1
        return y

    def preview(self, key: str, x: int, rotation: int) -> tuple[list[list[str | None]], int] | None:
        """Brett (nx x ny) nach einem geraden Fall + Anzahl Raeumungen."""
        y = self.landing_y(key, x, rotation)
        if y is None:
            return None
        grid: list[list[str | None]] = [[self.get_block(xx, yy) for yy in range(self.ny)] for xx in range(self.nx)]
        for bx, by in self.each_block(key, x, y, rotation):
            if 0 <= bx < self.nx and 0 <= by < self.ny:
                grid[bx][by] = key
        cleared = 0
        row = self.ny - 1
        while row > 0:
            if all(grid[xx][row] for xx in range(self.nx)):
                for drop in range(row, -1, -1):
                    for xx in range(self.nx):
                        grid[xx][drop] = None if drop == 0 else grid[xx][drop - 1]
                row += 1
                cleared += 1
            row -= 1
        return grid, cleared

    def plan_for(self, key: str) -> list[int]:
        """Beste Ablage fuer den aktuellen Baustein: Rotation + Spalte + Soft-Drops."""
        best: tuple[float, int, int] | None = None
        for rotation in range(4):
            for x in range(self.nx):
                preview = self.preview(key, x, rotation)
                if preview is None:
                    continue
                board, cleared = preview
                holes, aggregate, peak = self.metrics(board)
                score = cleared * 10000 - holes * 120 - aggregate * 8 - peak * 12
                if best is None or score > best[0]:
                    best = (score, rotation, x)
        if best is None or self.current is None:
            return []
        _, rotation, target_x = best
        plan = [0] * rotation
        dx = target_x - self.current.x
        plan += [1] * dx if dx > 0 else [3] * (-dx)
        plan += [2] * (self.ny + 4)
        return plan

    def metrics(self, board: list[list[str | None]]) -> tuple[int, int, int]:
        """Loecher, Summe der Saeulenhoehen, hoechste Saeule (y=0 ist oben)."""
        heights: list[int] = []
        holes = 0
        for x in range(self.nx):
            column = board[x] if x < len(board) else []
            first = None
            for y in range(self.ny):
                filled = y < len(column) and column[y]
                if filled and first is None:
                    first = y
                elif first is not None and not filled:
                    holes += 1
            heights.append(0 if first is None else self.ny - first)
        return holes, sum(heights), max(heights) if heights else 0

    # -- Beobachtung -------------------------------------------------------
    def digest(self) -> str:
        chars = []
        for x in range(self.nx):
            for y in range(self.ny):
                key = self.get_block(x, y)
                chars.append(self.table.colors[key][0] if key else ".")
        return hashlib.sha256("".join(chars).encode()).hexdigest()[:16]


def simulate(model: Tetris, frames: int) -> dict[str, Any]:
    """Dieselbe Uhr, dieselben Tasten, dieselbe Aufzeichnung wie der Harness."""
    model.load()
    model.play()
    last_piece = model.current  # der Harness zaehlt ab dem ersten Tastendruck, nicht ab play()
    now_ms = 1_000_000.0
    last = now_ms
    trace: list[dict[str, Any]] = []
    pieces = 0
    for frame in range(frames):
        now_ms += 1000.0 / 60.0
        idt = min(1.0, (now_ms - last) / 1000.0)
        last = now_ms
        model.update(idt)
        if model.playing:
            if frame % 7 == 0:
                model.actions.append(0)
            if frame % 11 == 0:
                model.actions.append(3)
            if frame % 13 == 0:
                model.actions.append(1)
            if frame % 29 == 0:
                model.actions.append(2)
        if model.current is not last_piece:
            last_piece = model.current
            pieces += 1
            if len(trace) < 400:
                assert model.current is not None
                trace.append({
                    "frame": frame,
                    "score": model.score,
                    "rows": model.rows,
                    "piece": model.table.colors[model.current.key],
                    "x": model.current.x,
                    "y": model.current.y,
                    "board": model.digest(),
                })
        if not model.playing and frame > 60:
            break
    return {
        "frames": frames,
        "score": model.score,
        "rows": model.rows,
        "playing": model.playing,
        "pieces": pieces,
        "step": model.step,
        "board": model.digest(),
        "trace": trace,
    }


KEY_CODES = {0: 38, 1: 39, 2: 40, 3: 37}  # UP, RIGHT, DOWN, LEFT


def run_harness(bundle: Path, seed: int, frames: int, inputs_file: Path | None = None) -> dict[str, Any]:
    node = shutil.which("node")
    if not node:
        raise SystemExit("[fehlt] node nicht gefunden")
    argv = [node, str(HARNESS), str(bundle), "--seed", str(seed), "--frames", str(frames)]
    if inputs_file is not None:
        argv += ["--inputs-file", str(inputs_file)]
    done = run(argv, timeout=900.0)
    return cast(dict[str, Any], json.loads(done.stdout))


def simulate_bot(model: Tetris, frames: int) -> tuple[list[list[int]], dict[str, Any]]:
    """Spielt das Spiel mit einem gierigen Planer und protokolliert die Tasten.

    Der Planer rechnet auf dem Port; die Tasten gehen anschliessend an das
    *Original-Bundle*, das allein darueber entscheidet, was sie bewirken. Damit
    ist der Vergleich kein Selbstgespraech.
    """
    model.load()
    model.play()
    last_piece = model.current
    plan: list[int] = []
    inputs: list[list[int]] = []
    trace: list[dict[str, Any]] = []
    pieces = 0
    now_ms = 1_000_000.0
    last = now_ms
    for frame in range(frames):
        now_ms += 1000.0 / 60.0
        idt = min(1.0, (now_ms - last) / 1000.0)
        last = now_ms
        model.update(idt)
        if model.current is not last_piece:
            last_piece = model.current
            pieces += 1
            assert model.current is not None
            trace.append({
                "frame": frame, "score": model.score, "rows": model.rows,
                "piece": model.table.colors[model.current.key],
                "x": model.current.x, "y": model.current.y, "board": model.digest(),
            })
            plan = model.plan_for(model.current.key) if model.playing else []
        if model.playing and plan:
            action = plan.pop(0)
            model.actions.append(action)
            inputs.append([frame, KEY_CODES[action]])
        if not model.playing and frame > 60:
            break
    return inputs, {
        "frames": frames, "score": model.score, "rows": model.rows, "playing": model.playing,
        "pieces": pieces, "step": model.step, "board": model.digest(), "trace": trace,
    }


def compare_bot(seed: int, frames: int, recovered: dict[str, Any], table: PieceTable, bundle: Path,
                inputs_path: Path) -> dict[str, Any]:
    values = recovered["values"]
    model = Tetris(
        nx=int(values["nx"]), ny=int(values["ny"]), start=float(values["start"]),
        decrement=float(values["decrement"]), minimum=float(values["min"]), seed=seed, table=table,
    )
    inputs, actual = simulate_bot(model, frames)
    inputs_path.parent.mkdir(parents=True, exist_ok=True)
    inputs_path.write_text(json.dumps(inputs), encoding="utf-8")
    expected = run_harness(bundle, seed, frames, inputs_path)
    keys = ("score", "rows", "playing", "pieces", "board")
    deviations = [f"{key}: harness={expected[key]!r} port={actual[key]!r}" for key in keys if expected[key] != actual[key]]
    if len(expected["trace"]) != len(actual["trace"]):
        deviations.append(f"trace_len: harness={len(expected['trace'])} port={len(actual['trace'])}")
    mismatches = [i for i, (a, b) in enumerate(zip(expected["trace"], actual["trace"], strict=False)) if a != b]
    if mismatches:
        first = mismatches[0]
        deviations.append(f"trace[{first}]: harness={expected['trace'][first]} port={actual['trace'][first]}")
    return {
        "seed": seed, "frames": frames, "mode": "bot", "ok": not deviations, "deviations": deviations,
        "harness": {key: expected[key] for key in keys}, "port": {key: actual[key] for key in keys},
        "trace_entries": len(expected["trace"]), "inputs": len(inputs),
    }


def compare(seed: int, frames: int, recovered: dict[str, Any], table: PieceTable, bundle: Path) -> dict[str, Any]:
    values = recovered["values"]
    model = Tetris(
        nx=int(values["nx"]),
        ny=int(values["ny"]),
        start=float(values["start"]),
        decrement=float(values["decrement"]),
        minimum=float(values["min"]),
        seed=seed,
        table=table,
    )
    expected = run_harness(bundle, seed, frames)
    actual = simulate(model, frames)
    keys = ("score", "rows", "playing", "pieces", "board")
    deviations = [f"{key}: harness={expected[key]!r} port={actual[key]!r}" for key in keys if expected[key] != actual[key]]
    trace_mismatch = [i for i, (a, b) in enumerate(zip(expected["trace"], actual["trace"], strict=False)) if a != b]
    if len(expected["trace"]) != len(actual["trace"]):
        deviations.append(f"trace_len: harness={len(expected['trace'])} port={len(actual['trace'])}")
    if trace_mismatch:
        first = trace_mismatch[0]
        deviations.append(f"trace[{first}]: harness={expected['trace'][first]} port={actual['trace'][first]}")
    return {
        "seed": seed,
        "frames": frames,
        "mode": "pattern",
        "ok": not deviations,
        "deviations": deviations,
        "harness": {key: expected[key] for key in keys},
        "port": {key: actual[key] for key in keys},
        "trace_entries": len(expected["trace"]),
    }


# --------------------------------------------------------------------------- #
# 5. Ablauf
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fremdes Spiel-Bundle analysieren und rekonstruieren")
    parser.add_argument("--agent", default="rea-lab", help="Subagent (Default: rea-lab)")
    parser.add_argument("--reuse", action="store_true", help="vorhandenes Bundle/Evidence weiterverwenden")
    parser.add_argument("--seeds", default="7,42,1337", help="kommagetrennte PRNG-Seeds")
    parser.add_argument("--pattern-frames", type=int, default=4000, help="Frames fuer den festen Tastenplan")
    parser.add_argument("--bot-frames", type=int, default=6000, help="Frames fuer den Planer-Lauf (raeumt Reihen)")
    parser.add_argument("--json", action="store_true", help="Maschinenlesbarer Bericht")
    args = parser.parse_args(argv)

    source_dir = EXTERNAL_ROOT / "javascript-tetris"
    build_dir = EXTERNAL_ROOT / "javascript-tetris-build"
    report: dict[str, Any] = {"upstream": UPSTREAM, "commit": PINNED_COMMIT}

    if not args.reuse or not (build_dir / "dist" / "game.min.js").is_file():
        report["fetch"] = fetch_source(source_dir)
        report["build"] = build_bundle(source_dir, build_dir)
    else:
        report["fetch"] = {"path": str(source_dir), "commit": "reused"}
        report["build"] = {"dist": str(build_dir / "dist"), "files": [], "reused": True}

    dist = Path(report["build"]["dist"])
    config = NeuConfig.load(REPO_ROOT)
    manager = SubagentManager(config)
    report["agent"] = args.agent

    if not args.reuse:
        analysed, evidence_path = analyse(manager, args.agent, dist)
        report["analysis"] = {k: v for k, v in analysed.items() if k != "target"}
    else:
        evidence_path = manager.sandbox(args.agent) / "out" / f"{TARGET_NAME}-evidence.json"
        report["analysis"] = {"evidence": str(evidence_path), "reused": True}

    if not evidence_path.is_file():
        raise SystemExit(f"[fehlt] Evidence nicht gefunden: {evidence_path}")
    evidence = cast(dict[str, Any], json.loads(evidence_path.read_text(encoding="utf-8")))
    recovered = recover_constants(evidence)
    table = recover_pieces(dist / "game.min.js")
    report["recovered"] = {
        "constants": {k: recovered["values"][k] for k in REQUIRED_ROLES},
        "provenance": {k: recovered["provenance"][k] for k in REQUIRED_ROLES},
        "pieces": {
            "order": table.order, "sizes": table.sizes, "colors": table.colors, "masks": table.masks,
            "digest": table.digest(),
            "cross_check": cross_check(table, recover_piece_roles(evidence)),
        },
        "functions": recover_functions(evidence),
    }

    seeds = [int(part) for part in args.seeds.split(",") if part.strip()]
    bundle = dist / "game.min.js"
    cases = [compare(seed, args.pattern_frames, recovered, table, bundle) for seed in seeds]
    inputs_dir = EXTERNAL_ROOT / "bot-inputs"
    cases += [compare_bot(seed, args.bot_frames, recovered, table, bundle, inputs_dir / f"inputs-{seed}.json")
              for seed in seeds]
    report["cases"] = cases
    report["ok"] = all(case["ok"] for case in cases)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1

    print("=" * 78)
    print("Fremdes Spiel: Analyse und Rekonstruktion")
    print("=" * 78)
    print(f"Quelle       {UPSTREAM} @ {PINNED_COMMIT[:12]}")
    print(f"Bundle       {bundle}  ({bundle.stat().st_size} Bytes)")
    for entry in report["build"].get("files", []):
        print(f"             {entry['name']:<16} {entry['bytes']:>7} B  sha256={entry['sha256'][:16]}")
    print(f"Analyse      {report['analysis'].get('status', 'reused')}"
          f"  evidence={report['analysis'].get('evidence', '')}")
    print(f"Konstanten   {report['recovered']['constants']}")
    print(f"Bausteine    {len(table.masks)} x 4 Rotationen  sha256={table.digest()[:16]}"
          f"  Rollen-Abgleich={report['recovered']['pieces']['cross_check']}")
    print(f"Funktionen   {report['recovered']['functions']['count']} im semantischen Graph")
    print()
    for case in cases:
        mark = "ok  " if case["ok"] else "FAIL"
        print(f"[{mark}] {case['mode']:<7} seed={case['seed']:<6} frames={case['frames']:<6} "
              f"score={case['harness']['score']:<6} rows={case['harness']['rows']:<3} "
              f"pieces={case['harness']['pieces']:<3} board={case['harness']['board']}")
        for deviation in case["deviations"]:
            print(f"         {deviation}")
    print()
    print("ERGEBNIS: " + ("der Port reproduziert das fremde Bundle." if report["ok"] else "Abweichung -- nicht akzeptiert."))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
