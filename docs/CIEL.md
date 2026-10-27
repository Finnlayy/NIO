# Ciel JIT-Tool-Orchestrator (NCM + Sandbox-Agent)

Zweistufige Orchestrator-Schicht zwischen Apollo, FastMCP und den ausführenden
Sandbox-Agenten. Löst das Kontext-Skalierungsproblem (alle Tool-Schemas im
System-Prompt) durch Cold-Storage + Just-in-Time-Injection.

## 1. Ist-Analyse (Befund vor dem Einbau)

Untersucht am 2026-10-27 auf `main` (`a5bf808`):

| Frage | Befund |
| --- | --- |
| Apollo Core-Orchestrator (Python)? | Existiert **nicht** — „Apollo" lebt nur als Frontend-UI (`frontend/src/apollo/`, Next.js). Funktionales Äquivalent: `orchestrator/runner.py::Orchestrator`. |
| **Tool-Registrierung — wo?** | **`orchestrator/runner.py::LimbRegistry.reload()`** liest **`limbs/registry.json`** (Limbs + deren `operations`); Ausführung via `Orchestrator.dispatch()` → `_spawn()` (ein Subprozess pro Limb). |
| FastMCP-Integration (Python)? | **Keine** — FastMCP kommt nur in Docs und im Frontend-Katalog (`frontend/src/apollo/catalog.ts`) vor. Ciel bringt daher einen duck-typed `CielFastMCPWrapper` mit (passt auf echte FastMCP-Server wie auf Dummies). |
| System-1 / JEV / ONNX-Anbindung? | **Kein JEV, kein NCM** im Runtime-Pfad. Einzig: `Architect/models/weights/omega_regime_16d.onnx` (Regime-Klassifikator, bleibt unberührt) + deterministische hashed-BoW-Logistic-Regression in `Architect/core/learning/preference_model_updater.py` (stdlib-only, dokumentierte Divergence). |
| Event-Bus | `orchestrator/events.py::EventBus` (synchron, validiert Kinds bewusst **nicht**). |

**Konsequenz:** Ciel wurde als neues, rein additives Paket `apollo/ciel/`
gebaut — keine einzige Zeile Bestandscode wurde geändert (außer `pyproject.toml`:
`apollo`-Pakete + optionales `ciel`-Extra). Anbindung lesend/delegierend:

- `ColdStorageRegistry.from_limb_registry()` spiegelt Limb-Operations als Tools.
- `CielFastMCPWrapper` delegiert alles per `__getattr__` an die Original-Instanz.
- Ciel-Events (`ciel.*`) sind neue Bus-Kinds — der Bus prüft nicht, also kein Bruch.

## 2. Module

```
apollo/ciel/
  registry.py       Modul A: Cold-Storage Skill Registry (+ FastMCP-Interceptor)
  ncm_gate.py       Modul B: System-1 NCM Gatekeeper (Bypass ≥0.88 | JIT Top-3)
  sandbox_agent.py  Modul C: Isolierter Sandbox-Agent (+ Meta-Tool)
  synthesizer.py    Modul D: Macro-Skill Synthesizer (3× → Makro-Tool)
  embeddings.py     ONNX- (optional) / Hash-Embedding (Default, stdlib-only)
  models.py         pydantic-v2-Modelle mit Stdlib-Fallback
  errors.py, bus.py Fehlertypen / Event-Bus-Anbindung
```

### Modul A — Cold-Storage (`registry.py`)

- `register*()` nimmt FastMCP-Tools (duck-typed: `name`/`description`/`parameters`/
  `inputSchema`, Handler unter `fn`/`handler`/…) oder Dicts entgegen und berechnet
  je Tool einen Concept-Anchor-Vektor.
- Persistenz: In-Memory primär, SQLite (Write-Through) + JSON-Export/Import als
  Cache. Handler sind prozesslokal → nach Reload schema-only, bis
  `register_handler()` sie wieder anhängt.
- `CielFastMCPWrapper`: `ainit()` fängt alle Tools beim Start ab, `@server.tool`
  wird abgefangen (Original-Registrierung läuft weiter + Spiegelung),
  `tools_for_prompt()` liefert bewusst `[]` — Schemas kommen nur per JIT in Prompts.

### Modul B — NCM-Gate (`ncm_gate.py`)

`NCMGate.route(intent, state, event_payload=...)`:

- **Pfad 1 (System-1 Direct Bypass):** Confidence `≥ 0.88` **und** Tool
  deterministisch **und** alle `required_state_keys` im State **und** Handler
  vorhanden → direkte Ausführung, **0 Tokens**. Timeout/Fehler → Fallback auf JIT.
- **Pfad 2 (System-2 JIT):** sonst nur Top-3-Schemas an den Sandbox-Agenten.
- Embedding: `AutoEmbeddingProvider` nutzt ONNX-Runtime nur bei konfiguriertem
  Embedding-Modell + Tokenizer, sonst deterministischen Hash-Vektor (SHA-256-geseedet,
  L2-normalisiert; identische Texte → Cosine 1.0).

### Modul C — Sandbox-Agent (`sandbox_agent.py`)

- System-Prompt ist als `SANDBOX_SYSTEM_PROMPT` im Code hart hinterlegt
  (dynamische Teilmenge, striktes Halluzinationsverbot, Meta-Tool-Pflicht).
- Exakt ein Meta-Tool: `request_additional_skill(intent_query)` — lädt zur
  Laufzeit genau ein weiteres Schema nach (MRU-Arbeitsmenge: Prompt zeigt immer
  die 3 zuletzt benötigten Skills + Meta-Tool).
- **Sandbox-Safety:** jeder Tool-Call unter `asyncio.wait_for(timeout=...)`;
  unbekannte/schema-only Tools, Timeouts und Handler-Fehler werden strukturiert
  gefangen — der Event-Loop blockiert nie.
- LLM-Anbindung per `LLMClient`-Protokoll (`ScriptedLLMClient` für Tests,
  `OpenAICompatLLMClient` für Betrieb, z. B. FreeLLMAPI-Proxy).

### Modul D — Synthesizer (`synthesizer.py`)

- `log_execution(chain, success=...)` zählt **hintereinander** erfolgreiche Ketten;
  Fehlschlag setzt die Streak zurück.
- Ab 3×: `synthesize()` registriert `macro__a__b` (vereinigte Parameter, Pipeline
  in `meta`, deterministisch wenn alle Schritte deterministisch) — künftige
  Aufrufe laufen in einem Turn, ggf. per System-1 Bypass.

## 3. Schnellstart

```python
import asyncio
from apollo.ciel import build_ciel_layer, ScriptedLLMClient

async def main():
    ciel = await build_ciel_layer(fastmcp_server=mcp, llm=llm_client)
    # Pfad 1 oder 2 entscheidet das Gate selbst:
    result = await ciel.agent.run("Ticket T-42 priorisiert eskalieren", state={...})
    print(result.path, result.llm_calls, result.final_answer)
    # Erfolgreiche Ketten für die Makro-Synthese loggen:
    await ciel.synthesizer.log_execution(["tool_a", "tool_b"], success=True)

asyncio.run(main())
```

Ohne FastMCP-Server: `build_ciel_layer(limb_registry=limb_registry)` spiegelt
die NEU-Limb-Operations; ganz ohne Argumente startet eine leere Registry
(Tools via `ciel.registry.register*`, Handler via `register_handler`).

Events auf dem NEU-Bus: `ciel.registry.snapshot`, `ciel.gate.decision`,
`ciel.gate.bypass_executed`, `ciel.sandbox.turn`, `ciel.sandbox.tool_call`,
`ciel.sandbox.skill_reloaded`, `ciel.synth.chain_observed`,
`ciel.synth.macro_created` (Liste auch als `CIEL_EVENT_KINDS`).

## 4. Technische Regeln (eingehalten)

1. **Keine Brüche:** rein additives Paket; Wrapper/Interceptor-Pattern;
   Bestands-Suite 358/358 grün (s. u.).
2. **Async & Typing:** durchgehend `asyncio`, pydantic v2 (mit Stdlib-Fallback,
   damit die Stdlib-only-Laufzeit nie bricht), vollständige Python-3.11+-Hints.
3. **Sandbox-Safety:** `asyncio.wait_for` + Error-Catching pro Tool-Call
   (`sandbox_agent.execute_tool`, Gate-Bypass, Makro-Pipeline).
4. **TDD:** `tests/test_ciel_integration.py` — 11 Tests, grün **mit wie ohne**
   pydantic (Fallback per Import-Blockade verifiziert).

```bash
python3 -m pytest tests/test_ciel_integration.py -q   # 11 passed
python3 -m pytest tests/ -q                            # Bestand + Ciel grün
pip install -e '.[ciel]'                               # optional: pydantic v2
```
