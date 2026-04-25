output "alb_dns_name" {
  description = "Public DNS name of the ALB."
  value       = aws_lb.app.dns_name
}

output "public_url" {
  description = "Base URL the app is reachable at (point Twilio's voice webhook here + /twilio/voice)."
  value       = local.public_url
}

output "ecr_repo_url" {
  description = "ECR repository URL — push the app image here."
  value       = aws_ecr_repository.app.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  value = aws_ecs_service.app.name
}

output "rds_endpoint" {
  description = "RDS Postgres host:port."
  value       = "${aws_db_instance.main.address}:${aws_db_instance.main.port}"
}

output "redis_endpoint" {
  description = "ElastiCache Redis primary endpoint."
  value       = aws_elasticache_cluster.main.cache_nodes[0].address
}

output "secret_names" {
  description = "Secrets Manager entries that need to be populated out-of-band before the service is healthy."
  value       = [for s in aws_secretsmanager_secret.provider : s.name]
}
