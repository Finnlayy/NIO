#!/bin/bash
# =============================================================================
# NEXUS — Google Cloud Agent Operations
# Terraform Infrastructure Deployment Script
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuration
PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-europe-west3}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
STATE_BUCKET="${STATE_BUCKET:-${PROJECT_ID}-nexus-terraform-state}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Nexus Console - Terraform Deploy${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Validate
if [ -z "$PROJECT_ID" ]; then
    log_error "PROJECT_ID is required"
    exit 1
fi

for command in gcloud gsutil terraform; do
    if ! command -v "$command" &> /dev/null; then
        log_error "$command is required but not installed"
        exit 1
    fi
done

if ! gcloud auth print-access-token &> /dev/null; then
    log_error "No active Google Cloud authentication. Run gcloud auth login."
    exit 1
fi

log_info "API lifecycle is managed by Terraform google_project_service resources."
log_info "The current bootstrap principal needs temporary roles/serviceusage.serviceUsageAdmin."
log_info "Runtime and build service accounts must never receive that role."

# Create state bucket if it doesn't exist
log_info "Ensuring state bucket exists..."
if ! gsutil ls -b "gs://${STATE_BUCKET}" &> /dev/null; then
    gsutil mb -p "$PROJECT_ID" -l "$REGION" "gs://${STATE_BUCKET}"
    gsutil versioning set on "gs://${STATE_BUCKET}"
    log_success "State bucket created: gs://${STATE_BUCKET}"
else
    log_success "State bucket exists: gs://${STATE_BUCKET}"
fi

# Enable versioning
gsutil versioning set on "gs://${STATE_BUCKET}" 2>/dev/null || true

# Initialize Terraform
log_info "Initializing Terraform..."
terraform init \
    -backend-config="bucket=${STATE_BUCKET}" \
    -backend-config="prefix=nexus-console/${ENVIRONMENT}"

# Create terraform.tfvars if it doesn't exist
if [ ! -f "terraform.tfvars" ]; then
    log_info "Creating terraform.tfvars..."
    cat > terraform.tfvars << EOF
project_id    = "${PROJECT_ID}"
region        = "${REGION}"
environment   = "${ENVIRONMENT}"
alert_email   = ""
EOF
    log_warning "Please review and update terraform.tfvars with your settings"
fi

# Plan
log_info "Running Terraform plan..."
terraform plan -out=tfplan

# Apply
read -p "Apply Terraform changes? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "Applying Terraform changes..."
    terraform apply tfplan
    log_success "Infrastructure deployed!"
    
    # Output important information
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Deployment Outputs${NC}"
    echo -e "${GREEN}========================================${NC}"
    terraform output
else
    log_warning "Deployment cancelled"
fi

# Cleanup
rm -f tfplan
