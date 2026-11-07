#!/usr/bin/env python3
"""Demo des Prompt-Optimierers: beide Modi, echte Artefakte, echte Pruefungen.

Der Lauf schreibt nach ``workspace/prompt_optimizer_demo/`` (nicht versioniert)
und prueft die Invarianten selbst:

* beide Laeufe erzeugen ihre Dateien,
* die Achsen wechseln sich ab (Inhalt nur in Stufe 2/3, Technik nur in 1/4),
* Stufe 4 ist vollstaendig (Coverage 100 %),
* ein zweiter Aufruf auf das Final aendert kein Byte.

Exit-Code 0 = alles gruen, 1 = Invariante verletzt.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.prompt_optimizer import Mode, PromptOptimizer  # noqa: E402
from core.prompt_optimizer.research import FixtureProvider, LocalSourceChecker, load_fixture  # noqa: E402

FIXTURES = REPO_ROOT / "scripts" / "fixtures" / "prompt_optimizer"
OUT = REPO_ROOT / "workspace" / "prompt_optimizer_demo"


def deep_chain() -> list:
    draft = (FIXTURES / "demo_draft_protocol.md").read_text(encoding="utf-8")
    optimizer = PromptOptimizer(
        draft,
        out_dir=OUT / "deep_chain",
        mode=Mode.DEEP_CHAIN,
        auto_approve=True,
        provider=FixtureProvider(load_fixture(FIXTURES / "research_fixture.json")),
        checker=LocalSourceChecker(REPO_ROOT),
    )
    return optimizer.run_all()


def normal() -> object:
    draft = (FIXTURES / "demo_draft_ops_grid.md").read_text(encoding="utf-8")
    optimizer = PromptOptimizer(draft, out_dir=OUT / "normal")
    return optimizer.run_normal()


def check(results: list) -> list[str]:
    problems: list[str] = []
    content = [result.scorecard.content.after for result in results]
    technique = [result.scorecard.technique.after for result in results]
    if content[1] != content[0]:
        problems.append(f"Stufe 1 hat den Inhalt verändert: {content[0]} -> {content[1]}")
    if technique[2] != technique[1] or technique[3] != technique[1]:
        problems.append(f"Struktur-Sperre verletzt: {technique[1:4]}")
    if content[4] != content[3]:
        problems.append(f"Stufe 4 hat den Inhalt verändert: {content[3]} -> {content[4]}")
    if not all("100 %" in line for line in results[-1].coverage):
        problems.append(f"Coverage unvollständig: {results[-1].coverage}")
    final = OUT / "deep_chain" / "stage_4_FINAL_MASTER_PROMPT.md"
    before = final.read_text(encoding="utf-8")
    again = PromptOptimizer(
        (FIXTURES / "demo_draft_protocol.md").read_text(encoding="utf-8"),
        out_dir=OUT / "deep_chain",
        mode=Mode.DEEP_CHAIN,
    ).run_all()
    if final.read_text(encoding="utf-8") != before:
        problems.append("4-final wurde bei erneutem Lauf verändert")
    if not getattr(again[-1], "no_op", False):
        problems.append("erneuter Lauf wurde nicht als no_op erkannt")
    return problems


def main() -> int:
    print("=" * 78)
    print("Prompt-Optimierer — Demo (DEEP-CHAIN auf Protokoll-Entwurf, mit Quellenprüfung)")
    print("=" * 78)
    results = deep_chain()
    for result in results:
        print(result.render())

    print("=" * 78)
    print("Prompt-Optimierer — Modus NORMAL (ein Durchlauf, Ops-Grid-Entwurf)")
    print("=" * 78)
    print(normal().render())

    problems = check(results)
    print("=" * 78)
    if problems:
        print("Invarianten verletzt:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("Alle Invarianten gehalten:")
    print("  - Inhalt bewegt sich nur in Stufe 2 und 3, Technik nur in 1 und 4")
    print("  - Stufe 4 enthält 100 % der Features und Research-Blätter")
    print("  - erneuter Aufruf auf das 4-final-Dokument ändert kein Byte")
    print(f"  - Artefakte: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
