#!/bin/bash
# =============================================================================
# NIO Neural Orchestrator — Manual Cloud Run deployment
# Run after local verification (npm run build + live /api/task test).
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MONOREPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-europe-west3}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
SERVICE_NAME="${SERVICE_NAME:-nio-orchestrator-${ENVIRONMENT}}"
REPO_NAME="${REPO_NAME:-nio-orchestrator-docker}"
IMAGE_NAME="${IMAGE_NAME:-nio-orchestrator}"
RUNTIME_SERVICE_ACCOUNT="${RUNTIME_SERVICE_ACCOUNT:-nio-orchestrator-run-sa@${PROJECT_ID}.iam.gserviceaccount.com}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

if [ -z "$PROJECT_ID" ]; then
  log_error "PROJECT_ID is required"
  echo ""
  echo "Usage:"
  echo "  export PROJECT_ID=your-gcp-project-id"
  echo "  export REGION=europe-west3          # optional"
  echo "  export ENVIRONMENT=dev              # optional"
  echo "  ./gcp/deploy.sh"
  echo ""
  exit 1
fi

log_info "Building TypeScript (local sanity check)..."
cd "$MONOREPO_ROOT"
npm run build --workspace=backend

log_info "Building Docker image..."
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}"
SHORT_SHA="$(git -C "$MONOREPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo local)"

docker build \
  -f backend/Dockerfile \
  -t "${IMAGE_URI}:${SHORT_SHA}" \
  -t "${IMAGE_URI}:latest" \
  "$MONOREPO_ROOT"

log_info "Pushing image..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
docker push "${IMAGE_URI}:${SHORT_SHA}"
docker push "${IMAGE_URI}:latest"

log_info "Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --image="${IMAGE_URI}:${SHORT_SHA}" \
  --platform=managed \
  --allow-unauthenticated \
  --service-account="$RUNTIME_SERVICE_ACCOUNT" \
  --port=8080 \
  --set-env-vars="NODE_ENV=production,CORE_ADAPTER_MODE=live,MODEL_MANIFEST_PATH=/app/twin/model-manifest.json" \
  --set-secrets="OPENROUTER_API_KEY=nio-orchestrator-openrouter-key:latest,OPENAI_API_KEY=nio-orchestrator-openai-key:latest,ANTHROPIC_API_KEY=nio-orchestrator-anthropic-key:latest" \
  --memory=512Mi \
  --cpu=1 \
  --timeout=300 \
  --min-instances=0 \
  --max-instances=10 \
  --concurrency=40

SERVICE_URL="$(gcloud run services describe "$SERVICE_NAME" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format='value(status.url)')"

log_info "Health check..."
curl -f "${SERVICE_URL}/health"

echo ""
log_success "Deployed: ${SERVICE_URL}"
echo "  Health:  ${SERVICE_URL}/health"
echo "  Task:    POST ${SERVICE_URL}/api/task"
