# =============================================================================
# NEXUS — Google Cloud Agent Operations
# Main Terraform Configuration
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }

  backend "gcs" {
    # Bucket will be specified during initialization
    # terraform init -backend-config="bucket=nexus-terraform-state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# =============================================================================
# Random Suffix for Unique Resource Names
# =============================================================================

resource "random_id" "suffix" {
  byte_length = 4
}

locals {
  name_suffix  = random_id.suffix.hex
  service_name = "${var.app_name}-${var.environment}"

  # APIs are enabled declaratively by Terraform. The principal running Terraform
  # needs roles/serviceusage.serviceUsageAdmin during bootstrap. Runtime and build
  # identities MUST NOT receive that administrative role.
  required_services = toset([
    "serviceusage.googleapis.com",
    "iam.googleapis.com",
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "aiplatform.googleapis.com",
    "workflows.googleapis.com",
    "pubsub.googleapis.com",
    "eventarc.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "cloudtrace.googleapis.com",
    "vpcaccess.googleapis.com",
  ])
  
  # Common labels for all resources
  common_labels = merge(var.tags, {
    environment = var.environment
    suffix      = local.name_suffix
  })
}

# =============================================================================
# Project Service Bootstrap
# =============================================================================

resource "google_project_service" "required" {
  for_each = local.required_services

  project                    = var.project_id
  service                    = each.value
  disable_on_destroy         = false
  disable_dependent_services = false
}

# =============================================================================
# Service Accounts
# =============================================================================

# Cloud Run Service Account
resource "google_service_account" "cloud_run" {
  account_id   = "${var.app_name}-run-sa"
  display_name = "Cloud Run Service Account for ${var.app_name}"
  description  = "Service account for Cloud Run deployment of Nexus Console"

  depends_on = [google_project_service.required]
}

# Cloud Build Service Account
resource "google_service_account" "cloud_build" {
  count        = var.enable_cloud_build ? 1 : 0
  account_id   = "${var.app_name}-build-sa"
  display_name = "Cloud Build Service Account for ${var.app_name}"
  description  = "Service account for Cloud Build CI/CD pipeline"

  depends_on = [google_project_service.required]
}

# Vertex AI Agent Engine Service Account
resource "google_service_account" "vertex_ai" {
  account_id   = "${var.app_name}-vertex-sa"
  display_name = "Vertex AI Service Account for ${var.app_name}"
  description  = "Service account for Vertex AI Agent Engine"

  depends_on = [google_project_service.required]
}

# =============================================================================
# IAM Roles and Permissions
# =============================================================================

# Cloud Run Service Account Roles
resource "google_project_iam_member" "cloud_run_roles" {
  project = var.project_id
  for_each = toset([
    "roles/run.invoker",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/cloudtrace.agent",
    "roles/secretmanager.secretAccessor",
    "roles/cloudsql.client",
  ])
  role   = each.value
  member = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Cloud Build Service Account Roles
resource "google_project_iam_member" "cloud_build_roles" {
  project = var.project_id
  for_each = var.enable_cloud_build ? toset([
    "roles/cloudbuild.builds.builder",
    "roles/storage.admin",
    "roles/run.admin",
    "roles/iam.serviceAccountUser",
  ]) : toset([])

  role   = each.value
  member = "serviceAccount:${google_service_account.cloud_build[0].email}"
}

# Vertex AI Service Account Roles
resource "google_project_iam_member" "vertex_ai_roles" {
  project = var.project_id
  for_each = toset([
    "roles/aiplatform.user",
    "roles/logging.logWriter",
    "roles/storage.objectViewer",
    "roles/serviceusage.serviceUsageConsumer",
  ])
  role   = each.value
  member = "serviceAccount:${google_service_account.vertex_ai.email}"
}

# =============================================================================
# Cloud Run Service
# =============================================================================

resource "google_cloud_run_v2_service" "nexus_console" {
  name     = local.service_name
  location = var.region
  ingress  = var.allowed_ingress

  template {
    timeout         = "${var.timeout}s"
    service_account = google_service_account.cloud_run.email

    scaling {
      max_instance_count = var.max_instances
      min_instance_count = var.min_instances
    }
    
    containers {
      image = var.bootstrap_container_image
      
      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
      }
      
      env {
        name  = "NODE_ENV"
        value = "production"
      }
      
      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }
      
      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      
      env {
        name  = "VERTEX_AI_LOCATION"
        value = var.region
      }
      
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
    }
    
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.nexus.connection_name]
      }
    }
    
    dynamic "vpc_access" {
      for_each = var.enable_vpc_connector ? [1] : []
      content {
        connector = var.vpc_connector_id
        egress    = "ALL_TRAFFIC"
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  labels = local.common_labels
}

# Cloud Run IAM - Allow unauthenticated invocations
resource "google_cloud_run_service_iam_member" "unauthenticated" {
  location = google_cloud_run_v2_service.nexus_console.location
  project  = google_cloud_run_v2_service.nexus_console.project
  service  = google_cloud_run_v2_service.nexus_console.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# =============================================================================
# Cloud SQL PostgreSQL Instance
# =============================================================================

resource "google_sql_database_instance" "nexus" {
  name                = var.database_instance_name
  database_version    = "POSTGRES_15"
  region              = var.region
  deletion_protection = true

  depends_on = [google_project_service.required]

  settings {
    tier              = "db-f1-micro"
    availability_type = "ZONAL"
    
    disk_autoresize = true
    disk_size       = 10
    disk_type       = "PD_SSD"
    
    backup_configuration {
      enabled                        = true
      start_time                     = "02:00"
      point_in_time_recovery_enabled = true
    }
    
    ip_configuration {
      # Cloud Run connects through the Cloud SQL connector and Unix socket.
      # Model a google_compute_network separately before switching to private IP.
      ipv4_enabled = true
      require_ssl  = true
    }
    
    insights_config {
      query_insights_enabled  = true
      query_string_length     = 1024
      record_application_tags = true
      record_client_address   = true
    }
  }

  labels = local.common_labels
}

resource "google_sql_database" "nexus" {
  name     = var.database_name
  instance = google_sql_database_instance.nexus.name
}

resource "google_sql_user" "nexus" {
  name     = var.database_user
  instance = google_sql_database_instance.nexus.name
  password = random_password.database_password.result
}

# =============================================================================
# Secret Manager - Database Password
# =============================================================================

resource "random_password" "database_password" {
  length  = 32
  special = true
}

resource "google_secret_manager_secret" "db_password" {
  secret_id = var.database_password_secret_id

  depends_on = [google_project_service.required]
  
  replication {
    auto {}
  }
  
  labels = local.common_labels
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.database_password.result
}

resource "google_secret_manager_secret" "database_url" {
  secret_id = "${var.app_name}-${var.environment}-database-url"

  replication {
    auto {}
  }

  labels = local.common_labels
}

resource "google_secret_manager_secret_version" "database_url" {
  secret = google_secret_manager_secret.database_url.id
  secret_data = format(
    "postgresql://%s:%s@/%s?host=/cloudsql/%s",
    var.database_user,
    urlencode(random_password.database_password.result),
    var.database_name,
    google_sql_database_instance.nexus.connection_name,
  )
}

# =============================================================================
# Artifact Registry
# =============================================================================

resource "google_artifact_registry_repository" "docker" {
  location      = var.region
  repository_id = "${var.app_name}-docker"
  description   = "Docker repository for ${var.app_name}"
  format        = "DOCKER"
  
  labels = local.common_labels
}

# =============================================================================
# Cloud Build Configuration (if enabled)
# =============================================================================

resource "google_cloudbuild_trigger" "main" {
  count       = var.enable_cloud_build ? 1 : 0
  name        = "${var.app_name}-deploy"
  description = "Deploy ${var.app_name} on main branch push"
  
  repository_event_config {
    repository = "projects/${var.project_id}/locations/${var.region}/connections/${var.github_connection_id}/repositories/${var.github_repository}"
    pull_request {
      branch = "main"
    }
  }
  
  filename = "gcp/cloudbuild.yaml"
  
  included_files = [
    "src/**",
    "package.json",
    "package-lock.json",
    "next.config.ts",
    "tsconfig.json"
  ]
  
  labels = local.common_labels

  lifecycle {
    precondition {
      condition     = var.github_connection_id != "" && var.github_repository != ""
      error_message = "Cloud Build trigger requires github_connection_id and github_repository."
    }
  }
}

# =============================================================================
# Cloud Monitoring Dashboard
# =============================================================================

resource "google_monitoring_dashboard" "nexus" {
  count = var.enable_monitoring ? 1 : 0
  
  dashboard_json = jsonencode({
    displayName = "Nexus Console Dashboard"
    gridLayout = {
      columns = 2
      widgets = [
        {
          title = "Cloud Run Request Count"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type=\"cloud_run_revision\" AND resource.label.\"service_name\"=\"${local.service_name}\" AND metric.type=\"run.googleapis.com/request_count\""
                }
              }
            }]
          }
        },
        {
          title = "Cloud Run Latency (p99)"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type=\"cloud_run_revision\" AND resource.label.\"service_name\"=\"${local.service_name}\" AND metric.type=\"run.googleapis.com/request_latencies\""
                }
              }
            }]
          }
        },
        {
          title = "Cloud SQL CPU Utilization"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type=\"cloudsql_database\" AND resource.label.\"database_id\"=\"${google_sql_database_instance.nexus.name}\" AND metric.type=\"cloudsql.googleapis.com/database/cpu/utilization\""
                }
              }
            }]
          }
        },
        {
          title = "Error Rate"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type=\"cloud_run_revision\" AND resource.label.\"service_name\"=\"${local.service_name}\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.label.\"response_code\"=~\"5..\""
                }
              }
            }]
          }
        }
      ]
    }
  })
}

# =============================================================================
# Cloud Monitoring Alert Policy
# =============================================================================

resource "google_monitoring_alert_policy" "high_error_rate" {
  count        = var.enable_alerting ? 1 : 0
  display_name = "${local.service_name} - High Error Rate"
  combiner     = "OR"
  
  conditions {
    display_name = "Error rate > 5%"
    
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND resource.label.\"service_name\"=\"${local.service_name}\" AND metric.type=\"run.googleapis.com/request_count\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.05
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }
  
  notification_channels = var.alert_email != "" ? [google_monitoring_notification_channel.email[0].id] : []
  
  labels = local.common_labels
}

resource "google_monitoring_notification_channel" "email" {
  count        = var.enable_alerting && var.alert_email != "" ? 1 : 0
  display_name = "Nexus Alert Email"
  type         = "email"
  
  labels = {
    email_address = var.alert_email
  }
}

# =============================================================================
# Outputs
# =============================================================================

output "cloud_run_url" {
  description = "Cloud Run service URL"
  value       = google_cloud_run_v2_service.nexus_console.uri
}

output "cloud_run_service_name" {
  description = "Cloud Run service name"
  value       = google_cloud_run_v2_service.nexus_console.name
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL instance connection name"
  value       = google_sql_database_instance.nexus.connection_name
}

output "artifact_registry_url" {
  description = "Artifact Registry URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker.repository_id}"
}

output "service_account_email" {
  description = "Cloud Run service account email"
  value       = google_service_account.cloud_run.email
}
