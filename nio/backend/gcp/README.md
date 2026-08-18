# NIO Neural Orchestrator — Cloud Run

Deploy the manifest-driven LLM backend to Google Cloud Run.

## Prerequisites

1. Local verification passed:
   - `npm run build --workspace=backend`
   - `GET /health` reports `"coreAdapter": "live"`
   - `POST /api/task` returns real LLM output (not deterministic metadata)
2. GCP project with APIs enabled (Run, Artifact Registry, Secret Manager, Cloud Build)
3. Runtime service account: `nio-orchestrator-run-sa@PROJECT_ID.iam.gserviceaccount.com`
4. Secrets in Secret Manager:
   - `nio-orchestrator-openrouter-key`
   - `nio-orchestrator-openai-key`
   - `nio-orchestrator-anthropic-key`

## Manual deploy

```bash
cd nio
export PROJECT_ID=your-gcp-project-id
export REGION=europe-west3
chmod +x backend/gcp/deploy.sh
./backend/gcp/deploy.sh
```

## Cloud Build (CI)

From repo root:

```bash
gcloud builds submit nio \
  --config=nio/backend/gcp/cloudbuild.yaml \
  --substitutions=_SERVICE_NAME=nio-orchestrator-dev
```

## Adapter modes

| Mode | Trigger |
|------|---------|
| `live` | Any LLM API key set, or `CORE_ADAPTER_MODE=live` |
| `deterministic` | No keys and no override (integration tests / CI without secrets) |

Cloud Run sets `CORE_ADAPTER_MODE=live` and injects keys via Secret Manager.
