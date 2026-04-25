# Complete Terraform configuration for AI Claims Intake System on Google Cloud Platform
# This file contains all infrastructure resources for a production-ready deployment

terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

# ============================================================================
# VARIABLES
# ============================================================================

variable "gcp_project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "gcp_region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment (dev/staging/prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "claims-intake"
}

variable "domain_name" {
  description = "Custom domain (optional)"
  type        = string
  default     = ""
}

# Secrets
variable "twilio_account_sid" { type = string; sensitive = true }
variable "twilio_auth_token" { type = string; sensitive = true }
variable "twilio_phone_number" { type = string; sensitive = true }
variable "gemini_api_key" { type = string; sensitive = true }
variable "groq_api_key" { type = string; sensitive = true }
variable "gradium_api_key" { type = string; sensitive = true }
variable "secret_key" { type = string; sensitive = true }

# ============================================================================
# LOCALS
# ============================================================================

locals {
  name_prefix = "${var.project_name}-${var.environment}"
  labels = {
    project     = var.project_name
    environment = var.environment
    managed_by  = "terraform"
  }
}

# ============================================================================
# ENABLE REQUIRED APIS
# ============================================================================

resource "google_project_service" "apis" {
  for_each = toset([
    "compute.googleapis.com",
    "servicenetworking.googleapis.com",
    "sqladmin.googleapis.com",
    "redis.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "artifactregistry.googleapis.com",
    "vpcaccess.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# ============================================================================
# NETWORKING
# ============================================================================

resource "google_compute_network" "vpc" {
  name                    = "${local.name_prefix}-vpc"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.apis]
}

resource "google_compute_subnetwork" "subnet" {
  name          = "${local.name_prefix}-subnet"
  ip_cidr_range = "10.0.1.0/24"
  region        = var.gcp_region
  network       = google_compute_network.vpc.id
  private_ip_google_access = true
}

resource "google_compute_router" "router" {
  name    = "${local.name_prefix}-router"
  region  = var.gcp_region
  network = google_compute_network.vpc.id
}

resource "google_compute_router_nat" "nat" {
  name                               = "${local.name_prefix}-nat"
  router                             = google_compute_router.router.name
  region                             = var.gcp_region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}

resource "google_vpc_access_connector" "connector" {
  name          = "${local.name_prefix}-connector"
  region        = var.gcp_region
  network       = google_compute_network.vpc.name
  ip_cidr_range = "10.8.0.0/28"
  min_instances = 2
  max_instances = 3
  depends_on    = [google_project_service.apis]
}

# ============================================================================
# CLOUD SQL (PostgreSQL)
# ============================================================================

resource "random_password" "db_password" {
  length  = 32
  special = true
}

resource "google_compute_global_address" "private_ip" {
  name          = "${local.name_prefix}-private-ip"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "private_vpc" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip.name]
  depends_on              = [google_project_service.apis]
}

resource "google_sql_database_instance" "postgres" {
  name             = "${local.name_prefix}-db"
  database_version = "POSTGRES_16"
  region           = var.gcp_region

  settings {
    tier = var.environment == "prod" ? "db-n1-standard-1" : "db-f1-micro"
    
    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc.id
    }

    backup_configuration {
      enabled    = true
      start_time = "03:00"
    }

    database_flags {
      name  = "max_connections"
      value = "100"
    }
  }

  deletion_protection = var.environment == "prod"
  depends_on          = [google_service_networking_connection.private_vpc]
}

resource "google_sql_database" "database" {
  name     = "claims_db"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "user" {
  name     = "claims_user"
  instance = google_sql_database_instance.postgres.name
  password = random_password.db_password.result
}

# ============================================================================
# MEMORYSTORE REDIS
# ============================================================================

resource "google_redis_instance" "redis" {
  name           = "${local.name_prefix}-redis"
  tier           = var.environment == "prod" ? "STANDARD_HA" : "BASIC"
  memory_size_gb = var.environment == "prod" ? 5 : 1
  region         = var.gcp_region
  redis_version  = "REDIS_7_0"

  authorized_network = google_compute_network.vpc.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"

  auth_enabled = true
  transit_encryption_mode = "SERVER_AUTHENTICATION"

  depends_on = [google_project_service.apis]
}

# ============================================================================
# SECRET MANAGER
# ============================================================================

resource "google_secret_manager_secret" "app_secrets" {
  secret_id = "${local.name_prefix}-app-secrets"
  
  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "app_secrets" {
  secret = google_secret_manager_secret.app_secrets.id
  
  secret_data = jsonencode({
    TWILIO_ACCOUNT_SID   = var.twilio_account_sid
    TWILIO_AUTH_TOKEN    = var.twilio_auth_token
    TWILIO_PHONE_NUMBER  = var.twilio_phone_number
    GEMINI_API_KEY       = var.gemini_api_key
    GROQ_API_KEY         = var.groq_api_key
    GRADIUM_API_KEY      = var.gradium_api_key
    SECRET_KEY           = var.secret_key
    DATABASE_URL         = "postgresql+asyncpg://claims_user:${random_password.db_password.result}@${google_sql_database_instance.postgres.private_ip_address}:5432/claims_db"
    REDIS_URL            = "redis://:${google_redis_instance.redis.auth_string}@${google_redis_instance.redis.host}:${google_redis_instance.redis.port}/0"
    GRADIUM_TTS_VOICE_ID = "default_voice_id"
    GRADIUM_TTS_ENDPOINT = "wss://api.gradium.ai/api/speech/tts"
    DEFAULT_LANGUAGE     = "en"
    SUPPORTED_LANGUAGES  = "en,de,es,fr,pt"
    LOG_LEVEL            = "INFO"
  })
}

# ============================================================================
# ARTIFACT REGISTRY
# ============================================================================

resource "google_artifact_registry_repository" "repo" {
  location      = var.gcp_region
  repository_id = "${local.name_prefix}-repo"
  format        = "DOCKER"
  
  depends_on = [google_project_service.apis]
}

# ============================================================================
# SERVICE ACCOUNT
# ============================================================================

resource "google_service_account" "cloud_run" {
  account_id   = "${local.name_prefix}-run-sa"
  display_name = "Cloud Run Service Account"
}

resource "google_project_iam_member" "cloud_run_sql" {
  project = var.gcp_project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_secret_manager_secret_iam_member" "cloud_run_secrets" {
  secret_id = google_secret_manager_secret.app_secrets.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
}

# ============================================================================
# CLOUD RUN
# ============================================================================

resource "google_cloud_run_v2_service" "app" {
  name     = "${local.name_prefix}-service"
  location = var.gcp_region

  template {
    service_account = google_service_account.cloud_run.email

    scaling {
      min_instance_count = var.environment == "prod" ? 1 : 0
      max_instance_count = var.environment == "prod" ? 20 : 10
    }

    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = "${var.gcp_region}-docker.pkg.dev/${var.gcp_project_id}/${google_artifact_registry_repository.repo.repository_id}/claims-intake:latest"

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      ports {
        container_port = 8000
      }

      env {
        name = "ENVIRONMENT"
        value = var.environment
      }

      env {
        name = "PUBLIC_BASE_URL"
        value = var.domain_name != "" ? "https://${var.domain_name}" : ""
      }

      env {
        name = "APP_SECRETS"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.app_secrets.secret_id
            version = "latest"
          }
        }
      }
    }

    timeout = "300s"
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.apis,
    google_vpc_access_connector.connector,
    google_sql_database_instance.postgres,
    google_redis_instance.redis
  ]
}

resource "google_cloud_run_service_iam_member" "public_access" {
  service  = google_cloud_run_v2_service.app.name
  location = google_cloud_run_v2_service.app.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ============================================================================
# OUTPUTS
# ============================================================================

output "project_id" {
  value = var.gcp_project_id
}

output "region" {
  value = var.gcp_region
}

output "cloud_run_url" {
  value       = google_cloud_run_v2_service.app.uri
  description = "Cloud Run service URL"
}

output "artifact_registry_url" {
  value       = "${var.gcp_region}-docker.pkg.dev/${var.gcp_project_id}/${google_artifact_registry_repository.repo.repository_id}"
  description = "Artifact Registry URL for pushing images"
}

output "database_connection_name" {
  value       = google_sql_database_instance.postgres.connection_name
  description = "Cloud SQL connection name"
}

output "database_private_ip" {
  value       = google_sql_database_instance.postgres.private_ip_address
  description = "Database private IP"
}

output "redis_host" {
  value       = google_redis_instance.redis.host
  description = "Redis host"
}

output "vpc_connector_name" {
  value       = google_vpc_access_connector.connector.name
  description = "VPC connector name"
}

output "deployment_instructions" {
  value = <<-EOT
    
    ========================================
    Deployment Instructions
    ========================================
    
    1. Build and push Docker image:
       gcloud auth configure-docker ${var.gcp_region}-docker.pkg.dev
       docker build -t ${var.gcp_region}-docker.pkg.dev/${var.gcp_project_id}/${google_artifact_registry_repository.repo.repository_id}/claims-intake:latest -f infra/Dockerfile .
       docker push ${var.gcp_region}-docker.pkg.dev/${var.gcp_project_id}/${google_artifact_registry_repository.repo.repository_id}/claims-intake:latest
    
    2. Deploy to Cloud Run:
       terraform apply
    
    3. Run database migrations:
       gcloud run jobs create db-migrate --image ${var.gcp_region}-docker.pkg.dev/${var.gcp_project_id}/${google_artifact_registry_repository.repo.repository_id}/claims-intake:latest --command alembic --args "upgrade,head" --region ${var.gcp_region} --vpc-connector ${google_vpc_access_connector.connector.name}
       gcloud run jobs execute db-migrate --region ${var.gcp_region}
    
    4. Configure Twilio webhook:
       Voice URL: ${google_cloud_run_v2_service.app.uri}/twilio/voice
       Media Stream URL: ${replace(google_cloud_run_v2_service.app.uri, "https://", "wss://")}/media-stream
    
    5. View logs:
       gcloud logging tail "resource.type=cloud_run_revision"
    
    ========================================
    
  EOT
}