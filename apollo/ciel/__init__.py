"""Ciel JIT-Tool-Orchestrator (NCM + Sandbox-Agent).

Zweistufige Orchestrator-Schicht zwischen Apollo, FastMCP und den
ausführenden Sandbox-Agenten:

* **Modul A** (``registry``): Cold-Storage Skill Registry — fängt alle
  FastMCP-Tools beim Start ab (In-Memory + SQLite/JSON-Cache), statt sie in
  den LLM-Kontext zu injizieren.
* **Modul B** (``ncm_gate``): System-1 NCM Gatekeeper — Pfad 1 (Direct
  Bypass, 0 Tokens) ab Confidence ``>= 0.88`` bei vollständigem State,
  sonst Pfad 2 (JIT Top-3 Injection).
* **Modul C** (``sandbox_agent``): Isolierter Sandbox-Agent mit hart
  hinterlegtem System-Prompt und exakt einem Meta-Tool
  (``request_additional_skill``) zum JIT-Nachladen.
* **Modul D** (``synthesizer``): Macro-Skill Synthesizer — verschmilzt
  3x hintereinander erfolgreiche Ketten zu einem Makro-Tool.

Schnellstart::

    from apollo.ciel import build_ciel_layer

    ciel = build_ciel_layer(fastmcp_server=mcp)  # wrappt, bricht nichts
    decision = await ciel.gate.route("Tickets schließen", state={...})
    result = await ciel.agent.run("Tickets schließen", state={...})
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .bus import CIEL_EVENT_KINDS
from .embeddings import AutoEmbeddingProvider, EmbeddingProvider, HashEmbeddingProvider, OnnxEmbeddingProvider, cosine_similarity
from .errors import CielConfigError, CielError, ToolNotExecutable, ToolNotFound, ToolTimeout
from .models import (
    HAVE_PYDANTIC,
    AgentResult,
    AssistantMessage,
    BaseModel,
    GateDecision,
    MacroSynthesis,
    ScoredTool,
    ToolCall,
    ToolResult,
    ToolSchema,
)
from .ncm_gate import BYPASS_THRESHOLD, JIT_TOP_K, NCMGate, RegistryFunctionExecutor, ToolExecutor, run_handler
from .registry import CielFastMCPWrapper, ColdStorageRegistry
from .sandbox_agent import (
    META_TOOL_NAME,
    REQUEST_ADDITIONAL_SKILL_SCHEMA,
    SANDBOX_SYSTEM_PROMPT,
    LLMClient,
    NoOpLLMClient,
    OpenAICompatLLMClient,
    SandboxAgent,
    ScriptedLLMClient,
)
from .synthesizer import MACRO_PREFIX, SYNTHESIS_THRESHOLD, MacroSkillSynthesizer


@dataclass
class CielLayer:
    """Verdrahtete Ciel-Schicht (Registry + Gate + Agent + Synthesizer)."""

    registry: ColdStorageRegistry
    gate: NCMGate
    agent: SandboxAgent
    synthesizer: MacroSkillSynthesizer
    wrapper: CielFastMCPWrapper | None = None


async def build_ciel_layer(
    fastmcp_server: Any | None = None,
    limb_registry: Any | None = None,
    *,
    llm: LLMClient | None = None,
    executor: ToolExecutor | None = None,
    event_bus: Any | None = None,
    embedder: EmbeddingProvider | None = None,
    cache_path: str | Path | None = None,
    synth_path: str | Path | None = None,
    bypass_threshold: float = BYPASS_THRESHOLD,
    top_k: int = JIT_TOP_K,
    max_turns: int = 6,
) -> CielLayer:
    """Baut und verdrahtet die komplette Ciel-Schicht (async, ein Aufruf).

    * ``fastmcp_server``: wird per :class:`CielFastMCPWrapper` abgefangen
      (Bestandsinstanz läuft unverändert weiter) und alle Tools werden ins
      Cold-Storage übernommen.
    * ``limb_registry``: NEU-``LimbRegistry`` wird lesend als Tools gespiegelt.
    * Beide ``None``: leere Registry (Tools via ``registry.register*``).
    """
    active_embedder = embedder or HashEmbeddingProvider()
    registry = ColdStorageRegistry(embedder=active_embedder, cache_path=cache_path, event_bus=event_bus)
    wrapper: CielFastMCPWrapper | None = None
    if fastmcp_server is not None:
        inner = fastmcp_server.wrapped if isinstance(fastmcp_server, CielFastMCPWrapper) else fastmcp_server
        wrapper = fastmcp_server if isinstance(fastmcp_server, CielFastMCPWrapper) else CielFastMCPWrapper(inner, registry=registry)
        if wrapper.registry is not registry:
            # Bereits existierender Wrapper mit eigener Registry → übernehmen.
            registry = wrapper.registry
        else:
            await wrapper.ainit()
    if limb_registry is not None:
        limb_mirror = ColdStorageRegistry.from_limb_registry(limb_registry, embedder=active_embedder, event_bus=event_bus)
        for name in limb_mirror.names():
            record = limb_mirror.require(name)
            if name not in registry:
                registry.register(record, origin="limb", persist=False)
        if registry.cache_path is not None:
            registry.save_cache(registry.cache_path)
    active_executor: ToolExecutor = executor or RegistryFunctionExecutor(registry)
    gate = NCMGate(
        registry,
        embedder=active_embedder,
        executor=active_executor,
        event_bus=event_bus,
        bypass_threshold=bypass_threshold,
        top_k=top_k,
    )
    agent = SandboxAgent(registry=registry, gate=gate, llm=llm, executor=active_executor, event_bus=event_bus, max_turns=max_turns)
    synthesizer = MacroSkillSynthesizer(registry, event_bus=event_bus, persist_path=synth_path)
    return CielLayer(registry=registry, gate=gate, agent=agent, synthesizer=synthesizer, wrapper=wrapper)


__all__ = [
    "BYPASS_THRESHOLD",
    "CIEL_EVENT_KINDS",
    "HAVE_PYDANTIC",
    "JIT_TOP_K",
    "MACRO_PREFIX",
    "META_TOOL_NAME",
    "REQUEST_ADDITIONAL_SKILL_SCHEMA",
    "SANDBOX_SYSTEM_PROMPT",
    "SYNTHESIS_THRESHOLD",
    "AgentResult",
    "AssistantMessage",
    "AutoEmbeddingProvider",
    "BaseModel",
    "CielConfigError",
    "CielError",
    "CielFastMCPWrapper",
    "CielLayer",
    "ColdStorageRegistry",
    "EmbeddingProvider",
    "GateDecision",
    "HashEmbeddingProvider",
    "LLMClient",
    "MacroSkillSynthesizer",
    "MacroSynthesis",
    "NCMGate",
    "NoOpLLMClient",
    "OnnxEmbeddingProvider",
    "OpenAICompatLLMClient",
    "RegistryFunctionExecutor",
    "SandboxAgent",
    "ScoredTool",
    "ScriptedLLMClient",
    "ToolCall",
    "ToolExecutor",
    "ToolNotExecutable",
    "ToolNotFound",
    "ToolResult",
    "ToolSchema",
    "ToolTimeout",
    "build_ciel_layer",
    "cosine_similarity",
    "run_handler",
]
