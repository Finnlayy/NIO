---
name: neural-intelligence-network
description: Routes tasks through the Neural Intelligence Network (NIO) orchestrator API — classify, urgency-wrap, and execute via POST /api/task. Use when the user invokes NIN, NIO, neural intelligence network, /nin, or wants to prompt the neural core, run a domain task, or query the orchestrator middleware.
---

# Neural Intelligence Network

Prompt the local NIO stack: middleware classifies tasks, wraps complex workflows with urgency context, and returns core output.

## Invoke

User attaches this skill or types intent like:
- `/nin Solve knapsack with DP`
- `prompt the neural intelligence network: compare XGBoost vs transformer`
- `run this through NIO`

## Ports

| Service | Port | URL |
|---------|------|-----|
| API | 4000 | `http://localhost:4000` |
| UI | 4001 | `http://localhost:4001` |

Repo root: `C:\Users\finnp\Downloads\NIO` (or cloned `NIO` repo).

## Workflow

```
- [ ] 1. Health-check API
- [ ] 2. Start services if down
- [ ] 3. Map user request → task payload
- [ ] 4. POST /api/task
- [ ] 5. Present result clearly
```

### Step 1 — Health check

```powershell
curl.exe -s http://localhost:4000/health
```

Expect: `{"status":"ok","service":"neural-orchestrator"}`

### Step 2 — Start if needed

`ERR_CONNECTION_REFUSED` or health fails → start both (two terminals or background):

```powershell
cd C:\Users\finnp\Downloads\NIO
npm start          # API :4000

cd C:\Users\finnp\Downloads\NIO
npm run ui:dev     # UI :4001
```

`EADDRINUSE` → already running; skip start.

### Step 3 — Build payload

Required fields:

| Field | Type | Notes |
|-------|------|-------|
| `taskDescription` | string | User's task in natural language |
| `isComplexWorkflow` | boolean | `true` → urgency wrapping |
| `domainHint` | string? | `ml_30core` \| `dev_dp` \| `generic` |
| `algorithmTag` | string? | e.g. `knapsack_01`, `lcs`, `transformer_selection` |
| `politenessTier` | string? | `very_polite` \| `polite` \| `neutral` \| `rude` \| `very_rude` |

**Domain routing heuristics:**

| User intent | domainHint | algorithmTag | isComplex |
|-------------|------------|--------------|-----------|
| ML, XGBoost, transformers, NAS | `ml_30core` | `transformer_selection` | true |
| DP, knapsack, LCS, Bellman-Ford | `dev_dp` | `knapsack_01` / `lcs` | true |
| Simple greeting, trivial Q | omit | omit | false |
| Cross-domain synthesis | `ml_30core` | omit | true |

Default `politenessTier`: `neutral`. Use `very_rude` for max directness (84.8% benchmark tier).

### Step 4 — Execute

```powershell
curl.exe -s -X POST http://localhost:4000/api/task `
  -H "Content-Type: application/json" `
  -d "{\"taskDescription\":\"TASK_HERE\",\"isComplexWorkflow\":true,\"domainHint\":\"dev_dp\",\"algorithmTag\":\"knapsack_01\",\"politenessTier\":\"neutral\"}"
```

Response shape:

```json
{
  "coreNodeId": "deterministic-core",
  "output": "system_prompt_length=...;user_prompt_length=...;is_complex=true;domain=dev_dp;expected_accuracy=0.848",
  "latencyMs": 0,
  "metadata": { "urgencyBlockLength": 0, "politenessTier": "neutral" }
}
```

Parse `output` semicolon fields for the user. `expected_accuracy=0.848` is the empirical benchmark.

### Step 5 — Reply format

```markdown
## Neural Core response

**Task:** [one-line summary]
**Domain:** [domain from output]
**Complex:** [yes/no]
**Expected accuracy:** [value]

[Interpret output for the user — what was classified, wrapped, executed]

**Raw:** `[output string]`
```

## Public access (ngrok)

```powershell
cd C:\Users\finnp\Downloads\NIO
npm run tunnel   # tunnels API :4000
```

Read URL: `http://127.0.0.1:4040/api/tunnels` → `public_url`

Replace `localhost:4000` with ngrok URL for remote calls.

## Do not

- Call `npm start` on port 3000 (deprecated; use 4000)
- Assume UI (:4001) runs tasks — only API executes
- Skip health check before blaming "broken" orchestrator

## More

Preset payloads and node mapping: [reference.md](reference.md)
