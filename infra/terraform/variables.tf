# Variables for AI Claims Intake System Infrastructure (Google Cloud Platform)

variable "gcp_project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "gcp_region" {
  description = "GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "gcp_zone" {
  description = "GCP zone for zonal resources"
  type        = string
  default     = "us-central1-a"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
  
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "claims-intake"
}

# VPC Configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_cidr" {
  description = "CIDR block for subnet"
  type        = string
  default     = "10.0.1.0/24"
}

# Cloud SQL Configuration
variable "db_tier" {
  description = "Cloud SQL instance tier"
  type        = string
  default     = "db-f1-micro"
}

variable "db_disk_size" {
  description = "Database disk size in GB"
  type        = number
  default     = 20
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "claims_db"
}

variable "db_username" {
  description = "Database master username"
  type        = string
  default     = "claims_user"
  sensitive   = true
}

variable "db_backup_enabled" {
  description = "Enable automated backups"
  type        = bool
  default     = true
}

variable "db_backup_start_time" {
  description = "Backup start time (HH:MM format)"
  type        = string
  default     = "03:00"
}

# Cloud Run Configuration
variable "cloud_run_cpu" {
  description = "CPU allocation for Cloud Run (1000m = 1 vCPU)"
  type        = string
  default     = "1000m"
}

variable "cloud_run_memory" {
  description = "Memory allocation for Cloud Run"
  type        = string
  default     = "2Gi"
}

variable "cloud_run_min_instances" {
  description = "Minimum number of Cloud Run instances"
  type        = number
  default     = 1
}

variable "cloud_run_max_instances" {
  description = "Maximum number of Cloud Run instances"
  type        = number
  default     = 10
}

variable "cloud_run_timeout" {
  description = "Request timeout in seconds"
  type        = number
  default     = 300
}

variable "cloud_run_concurrency" {
  description = "Maximum concurrent requests per instance"
  type        = number
  default     = 80
}

variable "container_port" {
  description = "Port exposed by the container"
  type        = number
  default     = 8000
}

# Application Configuration
variable "app_image_tag" {
  description = "Docker image tag for the application"
  type        = string
  default     = "latest"
}

variable "log_retention_days" {
  description = "Log retention in days"
  type        = number
  default     = 30
}

# Domain Configuration
variable "domain_name" {
  description = "Domain name for the application (optional)"
  type        = string
  default     = ""
}

variable "create_dns_record" {
  description = "Whether to create Cloud DNS record"
  type        = bool
  default     = false
}

variable "dns_zone_name" {
  description = "Cloud DNS zone name (if create_dns_record is true)"
  type        = string
  default     = ""
}

# Secrets Configuration
variable "twilio_account_sid" {
  description = "Twilio Account SID"
  type        = string
  sensitive   = true
}

variable "twilio_auth_token" {
  description = "Twilio Auth Token"
  type        = string
  sensitive   = true
}

variable "twilio_phone_number" {
  description = "Twilio Phone Number"
  type        = string
  sensitive   = true
}

variable "gemini_api_key" {
  description = "Google Gemini API Key"
  type        = string
  sensitive   = true
}

variable "groq_api_key" {
  description = "Groq API Key"
  type        = string
  sensitive   = true
}

variable "gradium_api_key" {
  description = "Gradium API Key"
  type        = string
  sensitive   = true
}

variable "gradium_tts_voice_id" {
  description = "Default Gradium TTS Voice ID"
  type        = string
  default     = "default_voice_id"
}

variable "secret_key" {
  description = "Application secret key for encryption"
  type        = string
  sensitive   = true
}

# Application Settings
variable "default_language" {
  description = "Default language code"
  type        = string
  default     = "en"
}

variable "supported_languages" {
  description = "Comma-separated list of supported languages"
  type        = string
  default     = "en,de,es,fr,pt"
}

variable "audio_retention_days" {
  description = "Number of days to retain audio recordings"
  type        = number
  default     = 30
}

variable "transcript_retention_days" {
  description = "Number of days to retain transcripts"
  type        = number
  default     = 90
}

# Monitoring & Alerting
variable "enable_monitoring" {
  description = "Enable Cloud Monitoring"
  type        = bool
  default     = true
}

variable "alert_email" {
  description = "Email address for alerts"
  type        = string
  default     = ""
}

# Cost Optimization
variable "enable_deletion_protection" {
  description = "Enable deletion protection for critical resources"
  type        = bool
  default     = true
}

variable "enable_high_availability" {
  description = "Enable high availability features (Multi-AZ, etc.)"
  type        = bool
  default     = false
}

# Networking
variable "enable_private_ip" {
  description = "Enable private IP for Cloud SQL"
  type        = bool
  default     = true
}

variable "enable_public_ip" {
  description = "Enable public IP for Cloud SQL (not recommended for production)"
  type        = bool
  default     = false
}