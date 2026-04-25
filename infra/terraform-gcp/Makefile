# Makefile for GCP Terraform Infrastructure Management

.PHONY: help init plan apply destroy validate fmt clean logs deploy-app

# Variables
PROJECT_ID ?= $(shell terraform output -raw project_id 2>/dev/null || echo "")
REGION ?= $(shell terraform output -raw region 2>/dev/null || echo "us-central1")
REGISTRY ?= $(shell terraform output -raw artifact_registry_url 2>/dev/null || echo "")
IMAGE_TAG ?= latest

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

init: ## Initialize Terraform
	terraform init

validate: ## Validate Terraform configuration
	terraform validate

fmt: ## Format Terraform files
	terraform fmt -recursive

plan: ## Show Terraform execution plan
	terraform plan

apply: ## Apply Terraform configuration
	terraform apply

destroy: ## Destroy all Terraform-managed infrastructure
	@echo "WARNING: This will destroy all infrastructure!"
	@read -p "Are you sure? Type 'yes' to continue: " confirm && [ "$$confirm" = "yes" ]
	terraform destroy

output: ## Show Terraform outputs
	terraform output

# Docker and Deployment Commands

gcloud-auth: ## Authenticate with GCP
	gcloud auth login
	gcloud auth application-default login

docker-auth: ## Configure Docker for Artifact Registry
	@echo "Configuring Docker for Artifact Registry..."
	@gcloud auth configure-docker $(REGION)-docker.pkg.dev

build-image: ## Build Docker image
	@echo "Building Docker image..."
	@cd ../.. && docker build -t $(REGISTRY)/claims-intake:$(IMAGE_TAG) -f infra/Dockerfile .

push-image: docker-auth build-image ## Build and push Docker image
	@echo "Pushing image to Artifact Registry..."
	@docker push $(REGISTRY)/claims-intake:$(IMAGE_TAG)

deploy-app: push-image ## Deploy application (build, push, and update Cloud Run)
	@echo "Updating Cloud Run service..."
	@terraform apply -auto-approve
	@echo "Deployment complete!"

# Database Commands

db-migrate: ## Run database migrations
	@echo "Running database migrations..."
	@gcloud run jobs create db-migrate-$(shell date +%s) \
		--image $(REGISTRY)/claims-intake:$(IMAGE_TAG) \
		--command alembic \
		--args "upgrade,head" \
		--region $(REGION) \
		--vpc-connector $(shell terraform output -raw vpc_connector_name) \
		--execute-now \
		--wait

# Monitoring Commands

logs: ## Tail Cloud Run logs
	@echo "Tailing logs from Cloud Run..."
	@gcloud logging tail "resource.type=cloud_run_revision" --format=json

logs-errors: ## Show recent error logs
	@echo "Showing recent errors..."
	@gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" --limit 50 --format=json

console: ## Open GCP Console
	@echo "Opening GCP Console..."
	@open "https://console.cloud.google.com/run?project=$(PROJECT_ID)"

monitoring: ## Open Cloud Monitoring
	@echo "Opening Cloud Monitoring..."
	@open "https://console.cloud.google.com/monitoring?project=$(PROJECT_ID)"

service-status: ## Show Cloud Run service status
	@gcloud run services describe $(shell terraform output -raw cloud_run_url | sed 's|https://||' | cut -d'.' -f1) \
		--region $(REGION) \
		--format="table(status.conditions[0].type,status.conditions[0].status,status.url)"

# Utility Commands

url: ## Show application URL
	@terraform output cloud_run_url

clean: ## Clean Terraform cache
	rm -rf .terraform
	rm -f .terraform.lock.hcl
	rm -f terraform.tfstate.backup
	rm -f *.tfplan

# Complete Deployment Workflow

deploy-all: init apply deploy-app db-migrate ## Complete deployment (infrastructure + application + migrations)
	@echo ""
	@echo "========================================="
	@echo "Deployment complete!"
	@echo "========================================="
	@echo "Application URL: $(shell terraform output -raw cloud_run_url)"
	@echo ""
	@echo "Next steps:"
	@echo "1. Configure Twilio webhooks with the URL above"
	@echo "2. Monitor logs with: make logs"
	@echo "3. Check service status with: make service-status"
	@echo "========================================="

# Setup Commands

setup-project: ## Set up GCP project (run once)
	@echo "Setting up GCP project..."
	@read -p "Enter your GCP Project ID: " project_id && \
	gcloud config set project $$project_id && \
	gcloud services enable cloudresourcemanager.googleapis.com && \
	echo "Project setup complete!"

create-tfvars: ## Create terraform.tfvars from example
	@if [ ! -f terraform.tfvars ]; then \
		cp terraform.tfvars.example terraform.tfvars; \
		echo "Created terraform.tfvars - please edit with your values"; \
	else \
		echo "terraform.tfvars already exists"; \
	fi