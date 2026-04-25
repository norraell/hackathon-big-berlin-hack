# Terraform Outputs

# VPC Outputs
output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "vpc_cidr" {
  description = "CIDR block of the VPC"
  value       = aws_vpc.main.cidr_block
}

output "public_subnet_ids" {
  description = "IDs of public subnets"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs of private subnets"
  value       = aws_subnet.private[*].id
}

# Database Outputs
output "rds_endpoint" {
  description = "RDS instance endpoint"
  value       = aws_db_instance.main.endpoint
}

output "rds_database_name" {
  description = "RDS database name"
  value       = aws_db_instance.main.db_name
}

output "rds_credentials_secret_arn" {
  description = "ARN of the secret containing RDS credentials"
  value       = aws_secretsmanager_secret.db_credentials.arn
  sensitive   = true
}

# Redis Outputs
output "redis_endpoint" {
  description = "Redis primary endpoint"
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "redis_port" {
  description = "Redis port"
  value       = aws_elasticache_replication_group.main.port
}

output "redis_credentials_secret_arn" {
  description = "ARN of the secret containing Redis credentials"
  value       = aws_secretsmanager_secret.redis_credentials.arn
  sensitive   = true
}

# Load Balancer Outputs
output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "Zone ID of the Application Load Balancer"
  value       = aws_lb.main.zone_id
}

output "alb_arn" {
  description = "ARN of the Application Load Balancer"
  value       = aws_lb.main.arn
}

output "alb_security_group_id" {
  description = "Security group ID of the ALB"
  value       = aws_security_group.alb.id
}

# ECS Outputs
output "ecs_cluster_id" {
  description = "ID of the ECS cluster"
  value       = aws_ecs_cluster.main.id
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "Name of the ECS service"
  value       = aws_ecs_service.app.name
}

output "ecs_task_definition_arn" {
  description = "ARN of the ECS task definition"
  value       = aws_ecs_task_definition.app.arn
}

output "ecs_security_group_id" {
  description = "Security group ID of ECS tasks"
  value       = aws_security_group.ecs_tasks.id
}

# ECR Outputs
output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = aws_ecr_repository.app.repository_url
}

output "ecr_repository_arn" {
  description = "ARN of the ECR repository"
  value       = aws_ecr_repository.app.arn
}

# Secrets Manager Outputs
output "app_secrets_arn" {
  description = "ARN of the application secrets in Secrets Manager"
  value       = aws_secretsmanager_secret.app_secrets.arn
  sensitive   = true
}

# CloudWatch Outputs
output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group for ECS"
  value       = aws_cloudwatch_log_group.ecs.name
}

output "cloudwatch_dashboard_name" {
  description = "Name of the CloudWatch dashboard"
  value       = aws_cloudwatch_dashboard.main.dashboard_name
}

# Domain Outputs
output "application_url" {
  description = "URL to access the application"
  value       = var.domain_name != "" ? "https://${var.domain_name}" : "http://${aws_lb.main.dns_name}"
}

output "certificate_arn" {
  description = "ARN of the ACM certificate (if domain is configured)"
  value       = var.domain_name != "" ? aws_acm_certificate.main[0].arn : null
}

# SNS Outputs
output "sns_alerts_topic_arn" {
  description = "ARN of the SNS topic for alerts"
  value       = var.alarm_email != "" ? aws_sns_topic.alerts[0].arn : null
}

# Deployment Information
output "deployment_instructions" {
  description = "Instructions for deploying the application"
  value = <<-EOT
    
    ========================================
    Deployment Instructions
    ========================================
    
    1. Build and push Docker image:
       aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${aws_ecr_repository.app.repository_url}
       docker build -t ${aws_ecr_repository.app.repository_url}:latest -f infra/Dockerfile .
       docker push ${aws_ecr_repository.app.repository_url}:latest
    
    2. Run database migrations:
       aws ecs execute-command --cluster ${aws_ecs_cluster.main.name} \
         --task <task-id> \
         --container app \
         --interactive \
         --command "alembic upgrade head"
    
    3. Configure Twilio webhook:
       Voice URL: ${var.domain_name != "" ? "https://${var.domain_name}" : "http://${aws_lb.main.dns_name}"}/twilio/voice
       Media Stream URL: ${var.domain_name != "" ? "wss://${var.domain_name}" : "ws://${aws_lb.main.dns_name}"}/media-stream
    
    4. Access CloudWatch Dashboard:
       https://console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}
    
    5. View application logs:
       aws logs tail ${aws_cloudwatch_log_group.ecs.name} --follow
    
    ========================================
    
  EOT
}

# Summary Output
output "infrastructure_summary" {
  description = "Summary of deployed infrastructure"
  value = {
    environment         = var.environment
    region              = var.aws_region
    vpc_id              = aws_vpc.main.id
    database_endpoint   = aws_db_instance.main.endpoint
    redis_endpoint      = aws_elasticache_replication_group.main.primary_endpoint_address
    load_balancer_dns   = aws_lb.main.dns_name
    ecs_cluster         = aws_ecs_cluster.main.name
    ecr_repository      = aws_ecr_repository.app.repository_url
    application_url     = var.domain_name != "" ? "https://${var.domain_name}" : "http://${aws_lb.main.dns_name}"
  }
}