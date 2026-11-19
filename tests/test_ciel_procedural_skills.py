"""NIO Phase 5: Prozedurale Skills, Wilson-Ranking, Distiller, Meta-Tool ``load_skill`` und Post-Run-Hook."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from apollo.ciel.models import AssistantMessage, ToolResult
from apollo.ciel.procedural_skills import (
    LOAD_SKILL_TOOL_NAME,
    ProceduralSkillRegistry,
    ProceduralSkillSpec,
    SkillStepSpec,
    TrajectorySkillDistiller,
    TrajectoryStep,
    build_compact_header_index,
    load_skill_payload,
    trajectory_from_messages,
    wilson_lower_bound,
)
from apollo.ciel.registry import ColdStorageRegistry
from apollo.ciel.sandbox_agent import SandboxAgent, ScriptedLLMClient
from apollo.ciel.synthesizer import SKILL_EPISODE_CATEGORY, MacroSkillSynthesizer


def _trajectory() -> list[TrajectoryStep]:
    return [
        TrajectoryStep(tool="lookup_token", arguments={"symbol": "ABC"}, output={"mint_address": "0xabc", "name": "ABC"}),
        TrajectoryStep(tool="token_risk", arguments={"token_address": "0xabc", "depth": 5}, output={"score": 0.2}),
    ]


def _spec(skill_id: str = "skill_risk") -> ProceduralSkillSpec:
    steps = [
        SkillStepSpec(tool="lookup_token", static_args={"symbol": "ABC"}),
        SkillStepSpec(tool="token_risk", input_bindings={"token_address": "step_0.mint_address"}, static_args={"depth": 5}),
    ]
    return ProceduralSkillSpec(skill_id=skill_id, name="Token-Risiko", description="Prüft das Risiko eines Tokens.", steps=steps)


def _registry_with_tools() -> ColdStorageRegistry:
    registry = ColdStorageRegistry()
    for name in ("lookup_token", "token_risk"):
        registry.register({"name": name, "description": f"{name} tool.", "parameters": {"type": "object", "properties": {}}})
    return registry


class _CapturingLLM(ScriptedLLMClient):
    def __init__(self, script: list[dict[str, Any]]) -> None:
        super().__init__(script)
        self.seen_tool_names: list[list[str]] = []
        self.seen_messages: list[list[dict[str, Any]]] = []

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        token: Any = None,
    ) -> AssistantMessage:
        self.seen_messages.append([dict(m) for m in messages])
        self.seen_tool_names.append([str(t.get("name")) for t in tools])
        return await super().complete(system=system, messages=messages, tools=tools, token=token)


# ---------------------------------------------------------------------------
# Distiller
# ---------------------------------------------------------------------------


def test_distiller_detects_dataflow_and_static_args() -> None:
    spec = TrajectorySkillDistiller().distill(_trajectory(), intent="Risiko prüfen")
    assert spec is not None
    assert spec.steps[1].input_bindings == {"token_address": "step_0.mint_address"}
    assert spec.steps[1].static_args == {"depth": 5}
    assert spec.steps[0].static_args == {"symbol": "ABC"}
    assert spec.required_tools() == ["lookup_token", "token_risk"]
    spec.validate_spec()


def test_distiller_needs_two_distinct_tools() -> None:
    same = [
        TrajectoryStep(tool="token_risk", arguments={"depth": 1}, output={"score": 0.1}),
        TrajectoryStep(tool="token_risk", arguments={"depth": 2}, output={"score": 0.2}),
    ]
    assert TrajectorySkillDistiller().distill(same) is None


def test_validate_spec_rejects_forward_or_bad_reference() -> None:
    forward = ProceduralSkillSpec(
        skill_id="bad",
        name="bad",
        steps=[SkillStepSpec(tool="a", input_bindings={"x": "step_1.out"}), SkillStepSpec(tool="b")],
    )
    with pytest.raises(ValueError):
        forward.validate_spec()
    malformed = ProceduralSkillSpec(skill_id="bad2", name="bad2", steps=[SkillStepSpec(tool="a", input_bindings={"x": "output"})])
    with pytest.raises(ValueError):
        malformed.validate_spec()


def test_trajectory_from_messages_keeps_only_successful_calls() -> None:
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "c1", "name": "lookup_token", "arguments": {"symbol": "ABC"}},
                {"id": "c2", "name": "token_risk", "arguments": {"token_address": "0xabc"}},
            ],
        }
    ]
    results = [
        ToolResult(call_id="c1", name="lookup_token", ok=True, result={"mint_address": "0xabc"}),
        ToolResult(call_id="c2", name="token_risk", ok=False, error="boom"),
    ]
    steps = trajectory_from_messages(messages, results)
    assert [s.tool for s in steps] == ["lookup_token"]
    assert steps[0].output == {"mint_address": "0xabc"}


# ---------------------------------------------------------------------------
# Playbook und Registry
# ---------------------------------------------------------------------------


def test_playbook_has_yaml_frontmatter_and_bindings() -> None:
    text = _spec().to_markdown_playbook()
    assert text.startswith("---\n")
    head, _, _body = text[4:].partition("\n---\n")
    assert 'skill_id: "skill_risk"' in head
    assert 'required_tools: ["lookup_token", "token_risk"]' in head
    assert "token_address ← step_0.mint_address" in text
    assert "depth = 5" in text


def test_wilson_lower_bound_reference_values() -> None:
    assert wilson_lower_bound(15, 16) == pytest.approx(0.7167, abs=1e-3)
    assert wilson_lower_bound(1, 1) == pytest.approx(0.2066, abs=1e-3)
    assert wilson_lower_bound(0, 0) == 0.0


def test_wilson_ranking_prefers_15_of_16_over_1_of_1() -> None:
    reg = ProceduralSkillRegistry()
    reg.register(_spec("skill_a"))
    reg.register(_spec("skill_b"))
    for _ in range(15):
        reg.record_outcome("skill_a", success=True)
    reg.record_outcome("skill_a", success=False)
    reg.record_outcome("skill_b", success=True)
    ranked = reg.ranked()
    assert [r.skill_id for r in ranked] == ["skill_a", "skill_b"]
    assert (ranked[0].successes, ranked[0].attempts) == (15, 16)
    assert ranked[0].wilson > ranked[1].wilson
    with pytest.raises(KeyError):
        reg.record_outcome("unknown", success=True)


def test_register_keeps_statistics_on_update() -> None:
    reg = ProceduralSkillRegistry()
    reg.register(_spec("skill_a"))
    reg.record_outcome("skill_a", success=True)
    reg.register(_spec("skill_a"))
    assert reg.ranked()[0].attempts == 1


def test_header_index_is_compact_and_has_no_steps() -> None:
    reg = ProceduralSkillRegistry()
    reg.register(_spec("skill_a"))
    index = build_compact_header_index(reg)
    assert "skill_a" in index
    assert "steps" not in index
    assert "step_0" not in index


def test_load_skill_payload_returns_playbook_or_none() -> None:
    reg = ProceduralSkillRegistry()
    reg.register(_spec("skill_a"))
    payload = load_skill_payload(reg, "skill_a")
    assert payload is not None
    assert payload["required_tools"] == ["lookup_token", "token_risk"]
    assert "## Schritte" in payload["playbook"]
    assert load_skill_payload(reg, "missing") is None


# ---------------------------------------------------------------------------
# Meta-Tool load_skill im Agenten
# ---------------------------------------------------------------------------


def test_load_skill_puts_playbook_in_buffer_and_activates_tools() -> None:
    skills = ProceduralSkillRegistry()
    skills.register(_spec("skill_a"))
    llm = _CapturingLLM(
        [
            {"content": "", "tool_calls": [{"id": "l1", "name": LOAD_SKILL_TOOL_NAME, "arguments": {"skill_id": "skill_a"}}]},
            {"content": "fertig", "tool_calls": []},
        ]
    )
    agent = SandboxAgent(registry=_registry_with_tools(), llm=llm, skill_registry=skills)

    result = asyncio.run(agent.run_scoped("Risiko prüfen", {}, session_id="s-load"))

    assert result.final_answer == "fertig"
    # Der erste Call sieht load_skill, der zweite die aktivierten Tools.
    assert LOAD_SKILL_TOOL_NAME in llm.seen_tool_names[0]
    assert "lookup_token" in llm.seen_tool_names[1]
    assert "token_risk" in llm.seen_tool_names[1]
    # Das Playbook steht als Tool-Result im Buffer.
    tool_msg = next(m for m in llm.seen_messages[1] if m.get("role") == "tool" and m.get("tool_call_id") == "l1")
    assert "## Schritte" in str(tool_msg["content"])
    assert "token_risk" in str(tool_msg["content"])


def test_load_skill_reports_missing_tools() -> None:
    skills = ProceduralSkillRegistry()
    skills.register(
        ProceduralSkillSpec(
            skill_id="skill_ghost",
            name="ghost",
            steps=[SkillStepSpec(tool="lookup_token"), SkillStepSpec(tool="ghost_tool")],
        )
    )
    llm = _CapturingLLM(
        [
            {"content": "", "tool_calls": [{"id": "l1", "name": LOAD_SKILL_TOOL_NAME, "arguments": {"skill_id": "skill_ghost"}}]},
            {"content": "ok", "tool_calls": []},
        ]
    )
    agent = SandboxAgent(registry=_registry_with_tools(), llm=llm, skill_registry=skills)

    result = asyncio.run(agent.run_scoped("ghost", {}, session_id="s-ghost"))

    load = next(r for r in result.tool_results if r.name == LOAD_SKILL_TOOL_NAME)
    assert load.ok is True
    assert load.result["activated"] == ["lookup_token"]
    assert load.result["missing"] == ["ghost_tool"]


def test_load_skill_unknown_id_is_error() -> None:
    skills = ProceduralSkillRegistry()
    llm = _CapturingLLM(
        [
            {"content": "", "tool_calls": [{"id": "l1", "name": LOAD_SKILL_TOOL_NAME, "arguments": {"skill_id": "nope"}}]},
            {"content": "ok", "tool_calls": []},
        ]
    )
    agent = SandboxAgent(registry=_registry_with_tools(), llm=llm, skill_registry=skills)
    result = asyncio.run(agent.run_scoped("x", {}, session_id="s-unknown"))
    load = next(r for r in result.tool_results if r.name == LOAD_SKILL_TOOL_NAME)
    assert load.ok is False
    assert "Unbekannter Skill" in load.error


def test_load_skill_not_offered_without_registry() -> None:
    llm = _CapturingLLM([{"content": "ok", "tool_calls": []}])
    agent = SandboxAgent(registry=_registry_with_tools(), llm=llm)
    asyncio.run(agent.run_scoped("x", {}, session_id="s-none"))
    assert LOAD_SKILL_TOOL_NAME not in llm.seen_tool_names[0]


# ---------------------------------------------------------------------------
# Post-Run-Hook des Synthesizers
# ---------------------------------------------------------------------------


class _EpisodeSpy:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def store_episode(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return str(kwargs.get("memory_id"))


def test_post_run_hook_distills_on_success_and_stores_episode() -> None:
    skills = ProceduralSkillRegistry()
    episodes = _EpisodeSpy()
    synth = MacroSkillSynthesizer(_registry_with_tools(), skill_registry=skills, episode_sink=episodes)

    spec = asyncio.run(
        synth.post_run_hook(session_id="s-hook", intent="Risiko prüfen", steps=_trajectory(), success=True)
    )

    assert spec is not None
    assert spec.skill_id in skills
    assert len(episodes.calls) == 1
    assert episodes.calls[0]["category"] == SKILL_EPISODE_CATEGORY
    assert episodes.calls[0]["memory_id"] == f"skill:{spec.skill_id}"


def test_post_run_hook_skips_failures_and_single_tool_runs() -> None:
    skills = ProceduralSkillRegistry()
    synth = MacroSkillSynthesizer(_registry_with_tools(), skill_registry=skills)

    assert asyncio.run(synth.post_run_hook(session_id="s", intent="x", steps=_trajectory(), success=False)) is None
    single = [TrajectoryStep(tool="token_risk", arguments={"depth": 1}, output={"score": 0.1})]
    assert asyncio.run(synth.post_run_hook(session_id="s", intent="x", steps=single, success=True)) is None
    assert len(skills.ranked()) == 0


def test_macro_synthesizer_still_works_without_skill_registry() -> None:
    synth = MacroSkillSynthesizer(_registry_with_tools())
    assert asyncio.run(synth.post_run_hook(session_id="s", intent="x", steps=_trajectory(), success=True)) is None
