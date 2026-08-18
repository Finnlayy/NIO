# =============================================================================
# NEXUS — Google Cloud Agent Operations
# Terraform Backend Configuration
# =============================================================================

# This file is used for remote state storage in Google Cloud Storage
# Initialize with:
#   terraform init \
#     -backend-config="bucket=nexus-terraform-state" \
#     -backend-config="prefix=nexus-console/dev"

# The actual bucket should be created manually before first use:
#   gsutil mb -p PROJECT_ID -l europe-west3 gs://nexus-terraform-state

# For state locking, enable versioning on the bucket:
#   gsutil versioning set on gs://nexus-terraform-state
