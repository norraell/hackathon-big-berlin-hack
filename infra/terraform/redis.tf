# ElastiCache Redis Cluster

# Security Group for Redis
resource "aws_security_group" "redis" {
  name_prefix = "${local.name_prefix}-redis-"
  description = "Security group for ElastiCache Redis"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Redis from ECS tasks"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-redis-sg"
    }
  )

  lifecycle {
    create_before_destroy = true
  }
}

# ElastiCache Subnet Group
resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.name_prefix}-redis-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-redis-subnet-group"
    }
  )
}

# ElastiCache Parameter Group
resource "aws_elasticache_parameter_group" "main" {
  name_prefix = "${local.name_prefix}-redis-"
  family      = "redis7"
  description = "Custom parameter group for Redis 7"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  parameter {
    name  = "timeout"
    value = "300"
  }

  tags = local.common_tags

  lifecycle {
    create_before_destroy = true
  }
}

# ElastiCache Replication Group (Redis Cluster)
resource "aws_elasticache_replication_group" "main" {
  replication_group_id       = "${local.name_prefix}-redis"
  replication_group_description = "Redis cluster for ${local.name_prefix}"
  
  engine               = "redis"
  engine_version       = var.redis_engine_version
  node_type            = var.redis_node_type
  num_cache_clusters   = var.redis_num_cache_nodes
  parameter_group_name = aws_elasticache_parameter_group.main.name
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token_enabled         = true
  auth_token                 = random_password.redis_auth_token.result

  automatic_failover_enabled = var.redis_num_cache_nodes > 1 ? true : false
  multi_az_enabled           = var.redis_num_cache_nodes > 1 ? true : false

  snapshot_retention_limit = var.enable_backup ? 5 : 0
  snapshot_window          = "03:00-05:00"
  maintenance_window       = "mon:05:00-mon:07:00"

  auto_minor_version_upgrade = true
  apply_immediately          = var.environment != "prod"

  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis_slow_log.name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "slow-log"
  }

  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis_engine_log.name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "engine-log"
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-redis"
    }
  )

  lifecycle {
    ignore_changes = [auth_token]
  }
}

# Generate random auth token for Redis
resource "random_password" "redis_auth_token" {
  length  = 32
  special = false
}

# CloudWatch Log Groups for Redis
resource "aws_cloudwatch_log_group" "redis_slow_log" {
  name              = "/aws/elasticache/${local.name_prefix}/slow-log"
  retention_in_days = var.log_retention_days

  tags = local.common_tags
}

resource "aws_cloudwatch_log_group" "redis_engine_log" {
  name              = "/aws/elasticache/${local.name_prefix}/engine-log"
  retention_in_days = var.log_retention_days

  tags = local.common_tags
}

# Store Redis credentials in Secrets Manager
resource "aws_secretsmanager_secret" "redis_credentials" {
  name_prefix             = "${local.name_prefix}-redis-credentials-"
  description             = "Redis credentials for ${local.name_prefix}"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0

  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "redis_credentials" {
  secret_id = aws_secretsmanager_secret.redis_credentials.id
  secret_string = jsonencode({
    auth_token = random_password.redis_auth_token.result
    host       = aws_elasticache_replication_group.main.primary_endpoint_address
    port       = aws_elasticache_replication_group.main.port
    url        = "rediss://:${random_password.redis_auth_token.result}@${aws_elasticache_replication_group.main.primary_endpoint_address}:${aws_elasticache_replication_group.main.port}/0"
  })
}

# CloudWatch Alarms for Redis
resource "aws_cloudwatch_metric_alarm" "redis_cpu" {
  alarm_name          = "${local.name_prefix}-redis-cpu-utilization"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Average"
  threshold           = "75"
  alarm_description   = "This metric monitors Redis CPU utilization"
  alarm_actions       = var.alarm_email != "" ? [aws_sns_topic.alerts[0].arn] : []

  dimensions = {
    CacheClusterId = "${aws_elasticache_replication_group.main.id}-001"
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "redis_memory" {
  alarm_name          = "${local.name_prefix}-redis-memory-utilization"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseMemoryUsagePercentage"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors Redis memory utilization"
  alarm_actions       = var.alarm_email != "" ? [aws_sns_topic.alerts[0].arn] : []

  dimensions = {
    CacheClusterId = "${aws_elasticache_replication_group.main.id}-001"
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "redis_evictions" {
  alarm_name          = "${local.name_prefix}-redis-evictions"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Evictions"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Sum"
  threshold           = "1000"
  alarm_description   = "This metric monitors Redis evictions"
  alarm_actions       = var.alarm_email != "" ? [aws_sns_topic.alerts[0].arn] : []

  dimensions = {
    CacheClusterId = "${aws_elasticache_replication_group.main.id}-001"
  }

  tags = local.common_tags
}