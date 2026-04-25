# Deployment Guide for AI Claims Intake System

This guide covers deploying the AI Claims Intake System to production using Terraform.

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Infrastructure Deployment](#infrastructure-deployment)
3. [Application Deployment](#application-deployment)
4. [Post-Deployment Configuration](#post-deployment-configuration)
5. [Monitoring and Maintenance](#monitoring-and-maintenance)
6. [Rollback Procedures](#rollback-procedures)
7. [Troubleshooting](#troubleshooting)

## Pre-Deployment Checklist

### Required Accounts and Credentials

- [ ] AWS Account with admin access
- [ ] Twilio account with phone number
- [ ] Google Gemini API key (for STT and LLM)
- [ ] Gradium API key (for TTS)

### Required Tools

- [ ] Terraform >= 1.5.0
- [ ] AWS CLI configured
- [ ] Docker installed
- [ ] Git
- [ ] jq (for JSON parsing)

### Domain Setup (Optional but Recommended)

- [ ] Domain registered
- [ ] Route53 hosted zone created
- [ ] DNS configured

## Infrastructure Deployment

### Step 1: Configure Variables

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with production values:

```hcl
# Production Configuration
environment = "prod"
aws_region  = "us-east-1"

# Network
vpc_cidr                 = "10.0.0.0/16"
availability_zones_count = 3  # Use 3 AZs for production

# Database - Production sizing
db_instance_class         = "db.r6g.large"
db_allocated_storage      = 100
db_max_allocated_storage  = 500
db_backup_retention_days  = 30

# ECS - Production sizing
ecs_task_cpu      = 2048  # 2 vCPU
ecs_task_memory   = 4096  # 4 GB
ecs_desired_count = 4
ecs_min_capacity  = 2
ecs_max_capacity  = 20

# Domain
domain_name           = "claims.yourdomain.com"
create_route53_record = true

# Monitoring
alarm_email = "ops-team@yourdomain.com"

# Security
enable_deletion_protection = true
enable_backup              = true
enable_enhanced_monitoring = true

# Credentials (use environment variables or secrets manager)
twilio_account_sid  = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
twilio_auth_token   = "your_secure_token"
twilio_phone_number = "+1234567890"
gemini_api_key      = "your_gemini_key"
gradium_api_key     = "your_gradium_key"
secret_key          = "generate_strong_random_key_min_32_chars"
```

### Step 2: Initialize and Plan

```bash
# Initialize Terraform
make init

# Validate configuration
make validate

# Review execution plan
make plan
```

Review the plan carefully. Ensure:
- Resource counts match expectations
- No unexpected deletions
- Costs are within budget

### Step 3: Deploy Infrastructure

```bash
# Apply infrastructure
make apply
```

This will create:
- VPC with public/private subnets across 3 AZs
- RDS PostgreSQL database
- ECS Fargate cluster
- Application Load Balancer
- CloudWatch monitoring
- All security groups and IAM roles

**Expected deployment time: 15-20 minutes**

### Step 4: Verify Infrastructure

```bash
# Check outputs
make output

# Verify key resources
terraform output infrastructure_summary
```

## Application Deployment

### Step 1: Build and Push Docker Image

```bash
# Build and push image to ECR
make push-image

# Or manually:
export ECR_REPO=$(terraform output -raw ecr_repository_url)
export AWS_REGION=$(terraform output -raw aws_region)

aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ECR_REPO

cd ../..
docker build -t $ECR_REPO:latest -f infra/Dockerfile .
docker push $ECR_REPO:latest
```

### Step 2: Deploy Application

```bash
cd infra/terraform

# Deploy application to ECS
make deploy-app

# Monitor deployment
make service-status
```

### Step 3: Run Database Migrations

```bash
# Run migrations
make db-migrate

# Verify migrations
make shell
# Inside container:
alembic current
exit
```

### Step 4: Verify Application Health

```bash
# Check application logs
make logs

# Test health endpoint
curl $(terraform output -raw application_url)/health

# Expected response:
# {"status": "healthy", "database": "connected"}
```

## Post-Deployment Configuration

### Configure Twilio Webhooks

1. Get your application URL:
   ```bash
   make url
   ```

2. Log into Twilio Console

3. Configure your phone number:
   - **Voice & Fax** → **Configure**
   - **A Call Comes In**: `https://your-domain.com/twilio/voice` (HTTP POST)
   - **Status Callback URL**: `https://your-domain.com/twilio/status` (HTTP POST)

4. Test the phone number by calling it

### Configure DNS (if not using Route53)

If you're managing DNS outside of Route53:

```bash
# Get ALB DNS name
terraform output alb_dns_name

# Create CNAME record:
# claims.yourdomain.com → your-alb-xxxxx.us-east-1.elb.amazonaws.com
```

### Set Up SSL Certificate Validation

If using ACM certificate:

```bash
# Get certificate validation records
aws acm describe-certificate \
  --certificate-arn $(terraform output -raw certificate_arn) \
  --query 'Certificate.DomainValidationOptions[0].ResourceRecord'
```

Add the CNAME record to your DNS to validate the certificate.

### Configure Monitoring Alerts

1. Confirm SNS subscription email
2. Test alerts:
   ```bash
   # Trigger a test alarm
   aws cloudwatch set-alarm-state \
     --alarm-name claims-intake-prod-error-rate \
     --state-value ALARM \
     --state-reason "Testing alert system"
   ```

## Monitoring and Maintenance

### Daily Monitoring

```bash
# Check service health
make service-status

# View recent logs
make logs

# Check for errors
make logs-errors

# View CloudWatch dashboard
make dashboard
```

### Weekly Maintenance

1. **Review CloudWatch Metrics**
   - CPU/Memory utilization
   - Response times (should be < 1500ms p95)
   - Error rates
   - Database connections

2. **Check Database Performance**
   ```bash
   # View slow queries
   aws rds describe-db-log-files \
     --db-instance-identifier $(terraform output -raw rds_endpoint | cut -d: -f1)
   ```

3. **Review Costs**
   ```bash
   # Estimate costs (requires infracost)
   make cost-estimate
   ```

### Monthly Maintenance

1. **Update Dependencies**
   - Review and update Docker base image
   - Update Python dependencies
   - Update Terraform providers

2. **Security Patches**
   ```bash
   # Scan ECR images
   aws ecr describe-image-scan-findings \
     --repository-name $(terraform output -raw ecr_repository_url | cut -d'/' -f2)
   ```

3. **Backup Verification**
   - Test database restore from backup

4. **Rotate Secrets**
   ```bash
   # Rotate database password
   aws secretsmanager rotate-secret \
     --secret-id $(terraform output -raw rds_credentials_secret_arn)
   ```

## Rollback Procedures

### Application Rollback

```bash
# Rollback to previous image
export PREVIOUS_TAG="v1.2.3"  # Replace with actual tag

# Update ECS service with previous image
aws ecs update-service \
  --cluster $(terraform output -raw ecs_cluster_name) \
  --service $(terraform output -raw ecs_service_name) \
  --task-definition $(terraform output -raw ecs_task_definition_arn | sed "s/:latest/:$PREVIOUS_TAG/")

# Monitor rollback
make service-status
make logs
```

### Database Rollback

```bash
# Rollback migrations
make shell
# Inside container:
alembic downgrade -1  # Rollback one migration
# Or:
alembic downgrade <revision>  # Rollback to specific revision
exit
```

### Infrastructure Rollback

```bash
# Revert to previous Terraform state
terraform state pull > current-state.json
terraform state push previous-state.json

# Or use version control
git checkout <previous-commit>
terraform apply
```

## Troubleshooting

### Issue: ECS Tasks Failing to Start

**Symptoms:**
- Tasks start then immediately stop
- "Essential container exited" errors

**Solutions:**
```bash
# Check logs
make logs

# Common causes:
# 1. Image not found - verify ECR image exists
aws ecr describe-images --repository-name $(terraform output -raw ecr_repository_url | cut -d'/' -f2)

# 2. Secrets access - verify IAM permissions
aws iam get-role-policy \
  --role-name claims-intake-prod-ecs-task-execution-role \
  --policy-name claims-intake-prod-secrets-access

# 3. Health check failing - test health endpoint
curl $(terraform output -raw application_url)/health
```

### Issue: High Latency (>1500ms)

**Symptoms:**
- Slow response times
- Timeout errors
- Poor call quality

**Solutions:**
```bash
# Check ECS metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ClusterName,Value=$(terraform output -raw ecs_cluster_name) \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average

# Scale up if needed
terraform apply -var="ecs_desired_count=8"

# Check database performance
aws rds describe-db-instances \
  --db-instance-identifier $(terraform output -raw rds_endpoint | cut -d: -f1) \
  --query 'DBInstances[0].{CPU:CPUUtilization,Connections:DatabaseConnections}'
```

### Issue: Database Connection Errors

**Symptoms:**
- "Connection refused" errors
- "Too many connections" errors

**Solutions:**
```bash
# Check security groups
aws ec2 describe-security-groups \
  --group-ids $(terraform output -raw ecs_security_group_id)

# Check database status
aws rds describe-db-instances \
  --db-instance-identifier $(terraform output -raw rds_endpoint | cut -d: -f1) \
  --query 'DBInstances[0].DBInstanceStatus'

# Check connection count
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name DatabaseConnections \
  --dimensions Name=DBInstanceIdentifier,Value=$(terraform output -raw rds_endpoint | cut -d: -f1) \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Maximum
```

### Issue: WebSocket Disconnections

**Symptoms:**
- Calls dropping mid-conversation
- "WebSocket closed" errors

**Solutions:**
```bash
# Check ALB target health
aws elbv2 describe-target-health \
  --target-group-arn $(terraform output -raw alb_target_group_arn)

# Check ECS task health
make service-status

# Review application logs for WebSocket errors
make logs | grep -i websocket

# Verify ALB idle timeout (should be high for WebSockets)
aws elbv2 describe-load-balancer-attributes \
  --load-balancer-arn $(terraform output -raw alb_arn) \
  --query 'Attributes[?Key==`idle_timeout.timeout_seconds`]'
```

## Emergency Contacts

- **AWS Support**: [AWS Support Center](https://console.aws.amazon.com/support/)
- **Twilio Support**: [Twilio Support](https://www.twilio.com/help/support)
- **On-Call Engineer**: [Your on-call rotation]
- **DevOps Team**: [Your team contact]

## Additional Resources

- [Terraform Documentation](https://www.terraform.io/docs)
- [AWS ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [Twilio Media Streams](https://www.twilio.com/docs/voice/twiml/stream)
- [Project Architecture](../architecture.md)
- [Application README](../README.md)