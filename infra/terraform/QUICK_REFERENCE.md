# Terraform Quick Reference Guide

## Common Commands

### Initial Setup
```bash
make init          # Initialize Terraform
make validate      # Validate configuration
make plan          # Preview changes
make apply         # Apply changes
```

### Deployment
```bash
make deploy-all    # Complete deployment (infra + app + migrations)
make deploy-app    # Deploy application only
make push-image    # Build and push Docker image
```

### Monitoring
```bash
make logs          # Tail application logs
make logs-errors   # Show recent errors
make dashboard     # Open CloudWatch dashboard
make service-status # Show ECS service status
```

### Database
```bash
make db-migrate    # Run database migrations
make db-shell      # Get database connection string
```

### Utilities
```bash
make shell         # Open shell in container
make url           # Show application URL
make output        # Show all Terraform outputs
make secrets       # Show application secrets (careful!)
```

### Cleanup
```bash
make destroy       # Destroy all infrastructure (WARNING!)
make clean         # Clean Terraform cache
```

## Important Outputs

```bash
# Application URL
terraform output application_url

# ECR Repository
terraform output ecr_repository_url

# Database Endpoint
terraform output rds_endpoint

# Redis Endpoint
terraform output redis_endpoint

# All outputs
terraform output
```

## Quick Troubleshooting

### Service Not Starting
```bash
make logs
make service-status
aws ecs describe-tasks --cluster $(terraform output -raw ecs_cluster_name) --tasks <task-id>
```

### High Latency
```bash
# Check ECS metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=$(terraform output -raw ecs_service_name)

# Scale up
terraform apply -var="ecs_desired_count=8"
```

### Database Issues
```bash
# Check connections
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name DatabaseConnections \
  --dimensions Name=DBInstanceIdentifier,Value=$(terraform output -raw rds_endpoint | cut -d: -f1)
```

## Environment Variables

Set these before running Terraform:

```bash
export AWS_REGION=us-east-1
export AWS_PROFILE=your-profile
export TF_VAR_environment=prod
```

## Cost Optimization Tips

1. **Use Spot Instances for Dev**
   ```hcl
   # In terraform.tfvars for dev
   ecs_capacity_provider = "FARGATE_SPOT"
   ```

2. **Reduce Instance Sizes for Dev**
   ```hcl
   db_instance_class = "db.t4g.micro"
   redis_node_type = "cache.t4g.micro"
   ecs_task_cpu = 512
   ecs_task_memory = 1024
   ```

3. **Disable Multi-AZ for Dev**
   ```hcl
   redis_num_cache_nodes = 1
   availability_zones_count = 2
   ```

4. **Reduce Backup Retention**
   ```hcl
   db_backup_retention_days = 1
   log_retention_days = 7
   ```

## Security Checklist

- [ ] Rotate secrets regularly
- [ ] Enable MFA on AWS account
- [ ] Review IAM policies
- [ ] Enable CloudTrail
- [ ] Enable GuardDuty
- [ ] Scan ECR images
- [ ] Review security groups
- [ ] Enable VPC Flow Logs
- [ ] Configure WAF rules (if needed)
- [ ] Set up AWS Config

## Backup and Recovery

### Manual Database Backup
```bash
aws rds create-db-snapshot \
  --db-instance-identifier $(terraform output -raw rds_endpoint | cut -d: -f1) \
  --db-snapshot-identifier manual-backup-$(date +%Y%m%d-%H%M%S)
```

### Restore from Backup
```bash
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier new-instance \
  --db-snapshot-identifier snapshot-id
```

### Export Terraform State
```bash
terraform state pull > terraform-state-backup-$(date +%Y%m%d).json
```

## Performance Tuning

### Database
```sql
-- Check slow queries
SELECT * FROM pg_stat_statements 
ORDER BY total_time DESC 
LIMIT 10;

-- Check connection count
SELECT count(*) FROM pg_stat_activity;
```

### Redis
```bash
# Connect to Redis
redis-cli -h $(terraform output -raw redis_endpoint) -a $(aws secretsmanager get-secret-value --secret-id $(terraform output -raw redis_credentials_secret_arn) --query SecretString --output text | jq -r '.auth_token')

# Check memory usage
INFO memory

# Check connected clients
CLIENT LIST
```

### ECS
```bash
# Check task metrics
aws ecs describe-services \
  --cluster $(terraform output -raw ecs_cluster_name) \
  --services $(terraform output -raw ecs_service_name)
```

## Useful AWS CLI Commands

```bash
# List all ECS tasks
aws ecs list-tasks --cluster $(terraform output -raw ecs_cluster_name)

# Describe a specific task
aws ecs describe-tasks --cluster $(terraform output -raw ecs_cluster_name) --tasks <task-id>

# View CloudWatch logs
aws logs tail $(terraform output -raw cloudwatch_log_group_name) --follow

# List ECR images
aws ecr list-images --repository-name $(terraform output -raw ecr_repository_url | cut -d'/' -f2)

# Get secret value
aws secretsmanager get-secret-value --secret-id $(terraform output -raw app_secrets_arn)
```

## Emergency Procedures

### Scale Down (Cost Saving)
```bash
terraform apply -var="ecs_desired_count=0"
```

### Scale Up (High Load)
```bash
terraform apply -var="ecs_desired_count=10"
```

### Emergency Rollback
```bash
# Revert to previous image
aws ecs update-service \
  --cluster $(terraform output -raw ecs_cluster_name) \
  --service $(terraform output -raw ecs_service_name) \
  --task-definition <previous-task-definition-arn>
```

### Stop All Traffic
```bash
# Deregister targets from ALB
aws elbv2 deregister-targets \
  --target-group-arn <target-group-arn> \
  --targets Id=<target-id>
```

## Links

- [Full Documentation](README.md)
- [Deployment Guide](../../DEPLOYMENT.md)
- [Architecture](../../architecture.md)
- [Terraform Registry](https://registry.terraform.io/)
- [AWS Documentation](https://docs.aws.amazon.com/)