"""Dynamischer Prompt-Optimierer (alternierende Orthogonalitaet / Ping-Pong).

Der Optimierer bearbeitet ein Prompt-Dokument in vier Stufen. Pro Stufe ist
genau eine Achse aktiv -- **Prompting-Technik** oder **Fach-Inhalt** --, die
andere Achse ist per Fingerprint gesperrt. Zwischen den Stufen wird gehandovered
(Artefakt + Modell-Checkpoint), der Arbeitskontext geleert und am Stufen-Gate
gestoppt, sofern die Freigabe nicht ausdruecklich automatisch erfolgt.

Schnellstart::

    from core.prompt_optimizer import PromptOptimizer, Mode

    opt = PromptOptimizer(draft_text, out_dir="workspace/po", mode=Mode.DEEP_CHAIN, auto_approve=True)
    results = opt.run_all()
    print(results[-1].scorecard.render())

Ein Durchlauf ohne Kette::

    opt = PromptOptimizer(draft_text, out_dir="workspace/po")
    print(opt.run_normal().markdown)

Der Vertrag der Stufen steht in ``prompts/system/prompt_optimizer.md``.
"""

from __future__ import annotations

from .extract import parse_draft
from .gates import GateFiller, StructuralFiller
from .model import (
    ARTIFACT_NORMAL,
    FINAL_MARKER,
    HARD_GATES,
    REQUIRED_SECTIONS,
    STAGE_ARTIFACTS,
    Axis,
    Feature,
    GateAnswer,
    HardGate,
    Mode,
    ResearchLeaf,
    ScoreCard,
    Source,
    StageDocument,
    Subsystem,
)
from .pipeline import (
    SYNTHESIS_CONTRACT,
    ApprovalRequired,
    CoverageError,
    OptimizerError,
    PromptOptimizer,
    StageOrderError,
    StageResult,
    resolve_mode,
)
from .research import FixtureProvider, LocalSourceChecker, NullProvider, ResearchProvider, harden_document, load_fixture
from .scorecard import LockViolation, Measurement, build_scorecard, measure_content, measure_technique

__all__ = [
    "ARTIFACT_NORMAL",
    "FINAL_MARKER",
    "HARD_GATES",
    "REQUIRED_SECTIONS",
    "STAGE_ARTIFACTS",
    "SYNTHESIS_CONTRACT",
    "ApprovalRequired",
    "Axis",
    "CoverageError",
    "Feature",
    "FixtureProvider",
    "GateAnswer",
    "GateFiller",
    "HardGate",
    "LocalSourceChecker",
    "LockViolation",
    "Measurement",
    "Mode",
    "NullProvider",
    "OptimizerError",
    "PromptOptimizer",
    "ResearchLeaf",
    "ResearchProvider",
    "ScoreCard",
    "Source",
    "StageDocument",
    "StageOrderError",
    "StageResult",
    "StructuralFiller",
    "Subsystem",
    "build_scorecard",
    "harden_document",
    "load_fixture",
    "measure_content",
    "measure_technique",
    "parse_draft",
    "resolve_mode",
]
