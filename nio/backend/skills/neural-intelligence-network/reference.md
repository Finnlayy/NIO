# NIN API Reference

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness |
| GET | `/` | API info + example body |
| POST | `/api/task` | Run orchestrator pipeline |

## Preset tasks (from UI network)

### 0/1 Knapsack
```json
{
  "taskDescription": "Solve the 0/1 knapsack problem with dynamic programming, derive the recurrence and complexity.",
  "isComplexWorkflow": true,
  "domainHint": "dev_dp",
  "algorithmTag": "knapsack_01",
  "politenessTier": "neutral"
}
```

### Transformer selection
```json
{
  "taskDescription": "Select between XGBoost and a Transformer architecture for a tabular sequence task.",
  "isComplexWorkflow": true,
  "domainHint": "ml_30core",
  "algorithmTag": "transformer_selection",
  "politenessTier": "very_rude"
}
```

### LCS
```json
{
  "taskDescription": "Compute the longest common subsequence using dynamic programming and prove correctness.",
  "isComplexWorkflow": true,
  "domainHint": "dev_dp",
  "algorithmTag": "lcs",
  "politenessTier": "very_polite"
}
```

### Master synthesis
```json
{
  "taskDescription": "Synthesize cross-domain insights across ML, DP, and prompt engineering benchmarks.",
  "isComplexWorkflow": true,
  "domainHint": "ml_30core",
  "politenessTier": "neutral"
}
```

## Agents (role manifests)

- `agents/roles/ml_architect.json` — `ml_30core`
- `agents/roles/dp_engineer.json` — `dev_dp`

## Pipeline (internal)

```
ingress → classifier → [urgency_wrapper if complex] → core_executor → telemetry
```

Graph: `agents/graphs/core_graph.yaml`

## Benchmarks

Pytest validates 84.8% (`0.848`) expected accuracy from politeness study (Dobariya & Kumar, 2025).

```powershell
npm run build
npm run trace:generate
python -m pytest evals/tests -v
```
