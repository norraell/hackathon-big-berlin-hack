# Makefile for Terraform Infrastructure Management

.PHONY: help init plan apply destroy validate fmt clean logs deploy-app

# Variables
AWS_REGION ?= us-east-1
ENVIRONMENT ?= dev
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

ecr-login: ## Login to ECR
	@echo "Logging in to ECR..."
	@aws ecr get-login-password --region $(AWS_REGION) | \
		docker login --username AWS --password-stdin $$(terraform output -raw ecr_repository_url)

build-image: ## Build Docker image
	@echo "Building Docker image..."
	cd ../.. && docker build -t $$(cd infra/terraform && terraform output -raw ecr_repository_url):$(IMAGE_TAG) -f infra/Dockerfile .

push-image: ecr-login build-image ## Build and push Docker image to ECR
	@echo "Pushing image to ECR..."
	docker push $$(terraform output -raw ecr_repository_url):$(IMAGE_TAG)

deploy-app: push-image ## Deploy application (build, push, and update ECS service)
	@echo "Updating ECS service..."
	@aws ecs update-service \
		--cluster $$(terraform output -raw ecs_cluster_name) \
		--service $$(terraform output -raw ecs_service_name) \
		--force-new-deployment \
		--region $(AWS_REGION)
	@echo "Deployment initiated. Check status with: make service-status"

# Database Commands

db-migrate: ## Run database migrations
	@echo "Running database migrations..."
	@TASK_ID=$$(aws ecs list-tasks \
		--cluster $$(terraform output -raw ecs_cluster_name) \
		--service-name $$(terraform output -raw ecs_service_name) \
		--query 'taskArns[0]' \
		--output text | cut -d'/' -f3) && \
	aws ecs execute-command \
		--cluster $$(terraform output -raw ecs_cluster_name) \
		--task $$TASK_ID \
		--container app \
		--interactive \
		--command "alembic upgrade head" \
		--region $(AWS_REGION)

db-shell: ## Connect to database shell
	@echo "Connecting to database..."
	@DB_URL=$$(aws secretsmanager get-secret-value \
		--secret-id $$(terraform output -raw rds_credentials_secret_arn) \
		--query SecretString \
		--output text | jq -r '.url') && \
	echo "Database URL: $$DB_URL"

# Monitoring Commands

logs: ## Tail application logs
	@echo "Tailing logs from CloudWatch..."
	@aws logs tail $$(terraform output -raw cloudwatch_log_group_name) --follow --region $(AWS_REGION)

logs-errors: ## Show recent error logs
	@echo "Showing recent errors..."
	@aws logs filter-log-events \
		--log-group-name $$(terraform output -raw cloudwatch_log_group_name) \
		--filter-pattern "ERROR" \
		--max-items 50 \
		--region $(AWS_REGION)

dashboard: ## Open CloudWatch dashboard in browser
	@echo "Opening CloudWatch dashboard..."
	@open "https://console.aws.amazon.com/cloudwatch/home?region=$(AWS_REGION)#dashboards:name=$$(terraform output -raw cloudwatch_dashboard_name)"

service-status: ## Show ECS service status
	@aws ecs describe-services \
		--cluster $$(terraform output -raw ecs_cluster_name) \
		--services $$(terraform output -raw ecs_service_name) \
		--region $(AWS_REGION) \
		--query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Pending:pendingCount}' \
		--output table

tasks: ## List running ECS tasks
	@aws ecs list-tasks \
		--cluster $$(terraform output -raw ecs_cluster_name) \
		--service-name $$(terraform output -raw ecs_service_name) \
		--region $(AWS_REGION)

# Utility Commands

shell: ## Open shell in running container
	@echo "Opening shell in container..."
	@TASK_ID=$$(aws ecs list-tasks \
		--cluster $$(terraform output -raw ecs_cluster_name) \
		--service-name $$(terraform output -raw ecs_service_name) \
		--query 'taskArns[0]' \
		--output text | cut -d'/' -f3) && \
	aws ecs execute-command \
		--cluster $$(terraform output -raw ecs_cluster_name) \
		--task $$TASK_ID \
		--container app \
		--interactive \
		--command "/bin/bash" \
		--region $(AWS_REGION)

secrets: ## Show application secrets (use carefully!)
	@echo "Fetching application secrets..."
	@aws secretsmanager get-secret-value \
		--secret-id $$(terraform output -raw app_secrets_arn) \
		--query SecretString \
		--output text | jq .

url: ## Show application URL
	@terraform output application_url

clean: ## Clean Terraform cache and state backups
	rm -rf .terraform
	rm -f .terraform.lock.hcl
	rm -f terraform.tfstate.backup
	rm -f *.tfplan

# Complete Deployment Workflow

deploy-all: init apply deploy-app db-migrate ## Complete deployment (infrastructure + application + migrations)
	@echo "Deployment complete!"
	@echo "Application URL: $$(terraform output application_url)"
	@echo ""
	@echo "Next steps:"
	@echo "1. Configure Twilio webhooks with the URL above"
	@echo "2. Monitor logs with: make logs"
	@echo "3. Check service status with: make service-status"

# Cost Estimation

cost-estimate: ## Estimate infrastructure costs (requires infracost)
	@command -v infracost >/dev/null 2>&1 || { echo "infracost not installed. Visit: https://www.infracost.io/docs/"; exit 1; }
	@infracost breakdown --path .