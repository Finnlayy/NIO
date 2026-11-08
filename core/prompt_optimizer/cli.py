"""CLI des Prompt-Optimierers: ``python -m core.prompt_optimizer``.

Beispiele::

    # Baseline + Stufe 1, dann Stopp am Gate
    python -m core.prompt_optimizer optimize --draft entwurf.md --out workspace/po

    # Gate freigeben und Stufe 2 fahren
    python -m core.prompt_optimizer optimize --draft entwurf.md --out workspace/po --approve

    # Alle vier Stufen am Stück (DEEP-CHAIN), mit Quellen-Fixture
    python -m core.prompt_optimizer optimize --draft entwurf.md --out workspace/po \\
        --mode deep-chain --all --research-fixture quellen.json --checker .

Der Exit-Code ist 0 bei Erfolg, 2 wenn das Stufen-Gate geschlossen bleibt und
3 bei einem Sperr-/Coverage-Bruch.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .model import Mode
from .pipeline import ApprovalRequired, CoverageError, OptimizerError, PromptOptimizer, StageOrderError
from .research import FixtureProvider, LocalSourceChecker, load_fixture
from .scorecard import LockViolation

__all__ = ["build_parser", "main"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prompt-optimizer", description="Alternierender Prompt-Optimierer (4 Stufen).")
    parser.add_argument("command", choices=("optimize", "normal", "inspect"), help="optimize = Kette, normal = Single-Pass, inspect = Zustand zeigen")
    parser.add_argument("--draft", type=Path, help="Rohentwurf (Markdown)")
    parser.add_argument("--out", type=Path, required=True, help="Export-Verzeichnis")
    parser.add_argument("--mode", default=None, help="normal | deep-chain (ohne Angabe: Standard NORMAL)")
    parser.add_argument("--stage", type=int, default=None, help="genau eine Stufe 1..4 ausführen")
    parser.add_argument("--all", action="store_true", help="alle vier Stufen am Stück (nur mit deep-chain)")
    parser.add_argument("--approve", action="store_true", help="Stufen-Gate vor dem Lauf öffnen")
    parser.add_argument("--research-fixture", type=Path, default=None, help="JSON mit Quellen je Research-Blatt")
    parser.add_argument("--checker", type=Path, default=None, help="Repo-Wurzel für die Prüfung von repo:-Quellen")
    parser.add_argument("--title", default="", help="Titel überschreiben")
    parser.add_argument("--quiet", action="store_true", help="nur Scorecards, keine Pfade")
    return parser


def _optimizer(args: argparse.Namespace) -> PromptOptimizer:
    if args.draft is None:
        raise SystemExit("--draft fehlt")
    draft = args.draft.read_text(encoding="utf-8")
    provider = FixtureProvider(load_fixture(args.research_fixture)) if args.research_fixture else None
    checker = LocalSourceChecker(args.checker) if args.checker else None
    # "--all" ist selbst der ausdrückliche Befehl für die volle Kette.
    mode = args.mode or ("deep-chain" if args.all else None)
    return PromptOptimizer(
        draft,
        out_dir=args.out,
        mode=mode,
        auto_approve=bool(args.all),
        provider=provider,
        checker=checker,
        title=args.title,
    )


def _print(results: list) -> None:
    for result in results:
        print(result.render())


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "inspect":
        state_path = args.out / "run_state.json"
        if not state_path.exists():
            print(f"inspect: kein Lauf in {args.out}")
            return 2
        print(state_path.read_text(encoding="utf-8"))
        return 0

    optimizer = _optimizer(args)
    if args.command == "normal":
        result = optimizer.run_normal()
        _print([result])
        return 0

    if optimizer.mode is not Mode.DEEP_CHAIN:
        print("optimize (Stufenkette) verlangt einen ausdrücklichen Befehl: --mode deep-chain oder --all.")
        print("Für den Einzeldurchlauf: python3 -m core.prompt_optimizer normal --draft … --out …")
        return 3
    if args.approve:
        optimizer.approve()
    try:
        if args.all:
            _print(optimizer.run_all())
            return 0
        if args.stage is None:
            if optimizer.current_stage == 0:
                _print([optimizer.prepare()])
            _print([optimizer.run_stage(optimizer.current_stage + 1)])
            return 0
        _print([optimizer.run_stage(args.stage)])
        return 0
    except ApprovalRequired as error:
        print(f"Stufen-Gate: {error}")
        return 2
    except (LockViolation, CoverageError, StageOrderError) as error:
        print(f"Abbruch: {error}")
        return 3
    except OptimizerError as error:  # pragma: no cover - Oberklasse, defensiv
        print(f"Fehler: {error}")
        return 3


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
