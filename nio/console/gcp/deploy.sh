#!/bin/bash
# =============================================================================
# NEXUS — Google Cloud Agent Operations
# Deployment Script for Google Cloud
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-europe-west3}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
SERVICE_NAME="${SERVICE_NAME:-nexus-console-${ENVIRONMENT}}"
REPO_NAME="${REPO_NAME:-nexus-console-docker}"
IMAGE_NAME="${IMAGE_NAME:-nexus-console}"
DB_INSTANCE_NAME="${DB_INSTANCE_NAME:-nexus-db}"
RUNTIME_SERVICE_ACCOUNT="${RUNTIME_SERVICE_ACCOUNT:-nexus-console-run-sa@${PROJECT_ID}.iam.gserviceaccount.com}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check gcloud
    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI is not installed. Please install from https://cloud.google.com/sdk"
        exit 1
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker Desktop."
        exit 1
    fi
    
    # Check Node.js
    if ! command -v node &> /dev/null; then
        log_error "Node.js is not installed. Please install Node.js 20+."
        exit 1
    fi
    
    log_success "All prerequisites met"
}

check_gcp_auth() {
    log_info "Checking Google Cloud authentication..."
    
    if ! gcloud auth print-access-token &> /dev/null; then
        log_error "Not authenticated with Google Cloud. Run: gcloud auth login"
        exit 1
    fi
    
    # Check project access
    if ! gcloud projects describe "$PROJECT_ID" &> /dev/null; then
        log_error "Cannot access project $PROJECT_ID. Check permissions."
        exit 1
    fi
    
    log_success "Authenticated with project $PROJECT_ID"
}

enable_required_apis() {
    log_info "Checking and enabling required Google Cloud APIs..."
    
    local apis=(
        "serviceusage.googleapis.com"
        "iam.googleapis.com"
        "run.googleapis.com"
        "cloudbuild.googleapis.com"
        "artifactregistry.googleapis.com"
        "sqladmin.googleapis.com"
        "secretmanager.googleapis.com"
        "aiplatform.googleapis.com"
        "workflows.googleapis.com"
        "pubsub.googleapis.com"
        "eventarc.googleapis.com"
        "monitoring.googleapis.com"
        "logging.googleapis.com"
        "cloudtrace.googleapis.com"
        "vpcaccess.googleapis.com"
    )
    local missing=()
    local api
    
    for api in "${apis[@]}"; do
        if ! gcloud services list --enabled --project="$PROJECT_ID" --filter="name:$api" --format="value(name)" | grep -qx "$api"; then
            missing+=("$api")
        fi
    done

    if [ ${#missing[@]} -eq 0 ]; then
        log_success "All required APIs are already enabled"
        return
    fi

    log_info "Enabling ${#missing[@]} missing APIs as one bootstrap operation..."
    if ! gcloud services enable "${missing[@]}" --project="$PROJECT_ID" --quiet; then
        log_error "API activation failed. The deployment principal needs the temporary bootstrap role roles/serviceusage.serviceUsageAdmin."
        log_error "Do not grant this role to Cloud Run, Cloud Build, or Agent Engine runtime service accounts."
        log_error "Use: PROJECT_ID=$PROJECT_ID BOOTSTRAP_PRINCIPAL=user:you@example.com ./gcp/bootstrap-service-usage.sh grant"
        exit 1
    fi
    
    log_success "All required APIs enabled"
}

create_artifact_registry() {
    log_info "Creating Artifact Registry repository..."
    
    if ! gcloud artifacts repositories describe "$REPO_NAME" \
        --project="$PROJECT_ID" \
        --location="$REGION" &> /dev/null; then
        gcloud artifacts repositories create "$REPO_NAME" \
            --project="$PROJECT_ID" \
            --location="$REGION" \
            --repository-format=docker \
            --description="Docker repository for Nexus Console"
    fi
    
    gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
    log_success "Artifact Registry repository ready and Docker authentication configured"
}

build_and_push() {
    log_info "Building and pushing Docker image..."
    
    local image_uri="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}"
    local short_sha=$(git rev-parse --short HEAD 2>/dev/null || echo "local")
    local tag="${image_uri}:${short_sha}"
    local latest_tag="${image_uri}:latest"
    
    # Build
    docker build -t "$tag" -t "$latest_tag" \
        --build-arg DATABASE_URL="postgresql://placeholder" \
        --build-arg PROJECT_ID="$PROJECT_ID" \
        --build-arg VERTEX_AI_LOCATION="$REGION" \
        "$PROJECT_ROOT"
    
    # Push
    docker push "$tag"
    docker push "$latest_tag"
    
    log_success "Image pushed: $tag"
}

deploy_cloud_run() {
    log_info "Deploying to Cloud Run..."
    
    local image_uri="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}"
    local short_sha=$(git rev-parse --short HEAD 2>/dev/null || echo "local")
    local cloud_sql_connection
    cloud_sql_connection=$(gcloud sql instances describe "$DB_INSTANCE_NAME" --project="$PROJECT_ID" --format='value(connectionName)')
    
    gcloud run deploy "$SERVICE_NAME" \
        --project="$PROJECT_ID" \
        --region="$REGION" \
        --image="${image_uri}:${short_sha}" \
        --platform=managed \
        --allow-unauthenticated \
        --service-account="$RUNTIME_SERVICE_ACCOUNT" \
        --add-cloudsql-instances="$cloud_sql_connection" \
        --set-env-vars="NODE_ENV=production,PROJECT_ID=${PROJECT_ID},VERTEX_AI_LOCATION=${REGION}" \
        --set-secrets="DATABASE_URL=${SERVICE_NAME}-database-url:latest" \
        --memory=512Mi \
        --cpu=1 \
        --timeout=300 \
        --min-instances=0 \
        --max-instances=10 \
        --concurrency=80
    
    log_success "Deployed to Cloud Run"
}

run_healthcheck() {
    log_info "Running health check..."
    
    local service_url=$(gcloud run services describe "$SERVICE_NAME" \
        --project="$PROJECT_ID" \
        --region="$REGION" \
        --format='value(status.url)')
    
    local max_retries=5
    local retry_count=0
    
    while [ $retry_count -lt $max_retries ]; do
        if curl -f "${service_url}/api/health" &> /dev/null; then
            log_success "Health check passed: ${service_url}/api/health"
            return 0
        fi
        
        retry_count=$((retry_count + 1))
        log_warning "Health check attempt $retry_count failed. Retrying in 10s..."
        sleep 10
    done
    
    log_error "Health check failed after $max_retries attempts"
    exit 1
}

print_deployment_info() {
    local service_url=$(gcloud run services describe "$SERVICE_NAME" \
        --project="$PROJECT_ID" \
        --region="$REGION" \
        --format='value(status.url)')
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Deployment Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "Service Name:  ${BLUE}${SERVICE_NAME}${NC}"
    echo -e "Region:        ${BLUE}${REGION}${NC}"
    echo -e "Project:       ${BLUE}${PROJECT_ID}${NC}"
    echo -e "Service URL:   ${BLUE}${service_url}${NC}"
    echo -e "Health Check:  ${BLUE}${service_url}/api/health${NC}"
    echo ""
    echo -e "View logs:     ${YELLOW}gcloud run services logs tail ${SERVICE_NAME} --region=${REGION}${NC}"
    echo -e "Update deploy: ${YELLOW}./gcp/deploy.sh${NC}"
    echo -e "Open console:  ${YELLOW}gcloud run services browse ${SERVICE_NAME} --region=${REGION}${NC}"
    echo ""
}

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------
main() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Nexus Console - GCP Deployment${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    
    # Validate inputs
    if [ -z "$PROJECT_ID" ]; then
        log_error "PROJECT_ID environment variable is required"
        echo ""
        echo "Usage:"
        echo "  export PROJECT_ID=your-gcp-project-id"
        echo "  export REGION=europe-west3  # optional"
        echo "  export ENVIRONMENT=dev      # optional"
        echo "  ./gcp/deploy.sh"
        echo ""
        exit 1
    fi
    
    check_prerequisites
    check_gcp_auth
    enable_required_apis
    create_artifact_registry
    build_and_push
    deploy_cloud_run
    run_healthcheck
    print_deployment_info
}

main "$@"
