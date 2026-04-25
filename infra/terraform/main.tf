# Main Terraform configuration for AI Claims Intake System
# Provider: Google Cloud Platform (GCP)

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

  # Uncomment for remote state management
  # backend "gcs" {
  #   bucket = "your-terraform-state-bucket"
  #   prefix = "claims-intake/terraform.tfstate"
  # }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

provider "google-beta" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

# Data sources
data "google_project" "project" {
  project_id = var.gcp_project_id
}

data "google_compute_zones" "available" {
  region = var.gcp_region
}

# Random suffix for unique resource names
resource "random_string" "suffix" {
  length  = 8
  special = false
  upper   = false
}

locals {
  name_prefix = "${var.project_name}-${var.environment}"
  common_labels = {
    project     = var.project_name
    environment = var.environment
    managed_by  = "terraform"
  }
}

# Enable required APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "compute.googleapis.com",
    "servicenetworking.googleapis.com",
    "sqladmin.googleapis.com",
    "redis.googleapis.com",
    "run.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "secretmanager.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "artifactregistry.googleapis.com",
    "vpcaccess.googleapis.com",
  ])

  service            = each.value
  disable_on_destroy = false
}