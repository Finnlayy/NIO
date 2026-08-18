# =============================================================================
# NEXUS — Google Cloud Agent Operations
# Terraform Variables for GCP Infrastructure
# =============================================================================

variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
}

variable "region" {
  description = "Primary GCP region"
  type        = string
  default     = "europe-west3"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "app_name" {
  description = "Application name used for resource naming"
  type        = string
  default     = "nexus-console"
}

variable "service_account_email" {
  description = "Service account email for Cloud Run"
  type        = string
  default     = ""
}

variable "bootstrap_container_image" {
  description = "Existing image used for the first Terraform Cloud Run revision; the application pipeline replaces it"
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "allowed_ingress" {
  description = "Ingress traffic policy for Cloud Run"
  type        = string
  default     = "all"
}

variable "min_instances" {
  description = "Minimum instances for Cloud Run"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum instances for Cloud Run"
  type        = number
  default     = 10
}

variable "memory" {
  description = "Memory for Cloud Run service"
  type        = string
  default     = "512Mi"
}

variable "cpu" {
  description = "CPU allocation for Cloud Run"
  type        = string
  default     = "1"
}

variable "timeout" {
  description = "Request timeout in seconds"
  type        = number
  default     = 300
}

variable "enable_vpc_connector" {
  description = "Enable VPC connector for Cloud Run"
  type        = bool
  default     = false
}

variable "vpc_connector_id" {
  description = "VPC Connector ID if enabled"
  type        = string
  default     = ""
}

variable "database_instance_name" {
  description = "Cloud SQL instance name"
  type        = string
  default     = "nexus-db"
}

variable "database_name" {
  description = "Database name within Cloud SQL"
  type        = string
  default     = "nexus_db"
}

variable "database_user" {
  description = "Database user"
  type        = string
  default     = "nexus_user"
}

variable "database_password_secret_id" {
  description = "Secret Manager secret ID for database password"
  type        = string
  default     = "nexus-db-password"
}

variable "enable_vector_search" {
  description = "Enable Vertex AI Vector Search"
  type        = bool
  default     = true
}

variable "vector_search_index_id" {
  description = "Vertex AI Vector Search index ID"
  type        = string
  default     = ""
}

variable "enable_cloud_build" {
  description = "Create the Developer Connect Cloud Build trigger; requires connection and repository IDs"
  type        = bool
  default     = false
}

variable "github_connection_id" {
  description = "Cloud Build GitHub connection ID"
  type        = string
  default     = ""
}

variable "github_repository" {
  description = "GitHub repository name"
  type        = string
  default     = ""
}

variable "enable_monitoring" {
  description = "Enable Cloud Monitoring dashboards"
  type        = bool
  default     = true
}

variable "enable_alerting" {
  description = "Enable Cloud Monitoring alerts"
  type        = bool
  default     = true
}

variable "alert_email" {
  description = "Email for alert notifications"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default = {
    project     = "nexus"
    managed_by  = "terraform"
    application = "agent-orchestrator"
  }
}
