variable "project" {
  description = "Short project name used as a prefix on AWS resources."
  type        = string
  default     = "voice-intake"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)."
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "eu-central-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the project VPC."
  type        = string
  default     = "10.42.0.0/16"
}

variable "az_count" {
  description = "Number of AZs to span (must be >= 2 for RDS / ALB)."
  type        = number
  default     = 2
}

variable "container_image" {
  description = "Full ECR image URI:tag the ECS task should run. Defaults to the repo created here with :latest."
  type        = string
  default     = ""
}

variable "container_port" {
  description = "Port the FastAPI app listens on inside the container."
  type        = number
  default     = 8000
}

variable "task_cpu" {
  description = "Fargate task CPU units."
  type        = number
  default     = 512
}

variable "task_memory" {
  description = "Fargate task memory in MiB."
  type        = number
  default     = 1024
}

variable "desired_count" {
  description = "Number of ECS task replicas."
  type        = number
  default     = 1
}

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "RDS allocated storage in GiB."
  type        = number
  default     = 20
}

variable "db_username" {
  description = "Master DB username."
  type        = string
  default     = "intake"
}

variable "redis_node_type" {
  description = "ElastiCache node type."
  type        = string
  default     = "cache.t4g.micro"
}

variable "domain_name" {
  description = "Optional domain (e.g. voice.example.com) for ACM/HTTPS. Empty string = HTTP-only ALB (dev)."
  type        = string
  default     = ""
}

variable "route53_zone_id" {
  description = "Route53 hosted zone ID matching domain_name. Required if domain_name is set."
  type        = string
  default     = ""
}

variable "default_language" {
  description = "DEFAULT_LANGUAGE env var passed to the app."
  type        = string
  default     = "en"
}

variable "supported_languages" {
  description = "SUPPORTED_LANGUAGES env var passed to the app (comma-separated)."
  type        = string
  default     = "en,de,es,fr,pt"
}

variable "company_name" {
  description = "COMPANY_NAME env var passed to the app."
  type        = string
  default     = "Acme Insurance"
}

variable "sla_hours" {
  description = "SLA_HOURS env var passed to the app."
  type        = number
  default     = 24
}

variable "tags" {
  description = "Extra tags merged onto every taggable resource."
  type        = map(string)
  default     = {}
}
