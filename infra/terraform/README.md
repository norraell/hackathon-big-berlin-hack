# Terraform Infrastructure for AI Claims Intake System

This directory contains Terraform Infrastructure as Code (IaC) for deploying the AI Claims Intake System to AWS.

## Architecture Overview

The infrastructure includes:

- **VPC**: Multi-AZ VPC with public and private subnets
- **RDS PostgreSQL**: Managed database for claims storage
- **ECS Fargate**: Containerized application hosting
- **Application Load Balancer**: HTTP/HTTPS/WebSocket traffic routing
- **Secrets Manager**: Secure credential storage
- **CloudWatch**: Logging, monitoring, and alerting
- **ECR**: Docker image registry

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **Terraform** >= 1.5.0 ([Install](https://www.terraform.io/downloads))
3. **AWS CLI** configured with credentials ([Install](https://aws.amazon.com/cli/))
4. **Docker** for building and pushing images ([Install](https://docs.docker.com/get-docker/))

## Quick Start

### 1. Configure Variables

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your actual values:

```hcl
# Required: AWS Configuration
aws_region  = "us-east-1"
environment = "dev"

# Required: Twilio Credentials
twilio_account_sid  = "your_actual_sid"
twilio_auth_token   = "your_actual_token"
twilio_phone_number = "+1234567890"

# Required: AI Service API Keys
gemini_api_key  = "your_actual_key"
gradium_api_key = "your_actual_key"

# Required: Application Secret
secret_key = "generate_a_strong_random_key_here"

# Optional: Domain Configuration
domain_name           = "claims.yourdomain.com"
create_route53_record = true

# Optional: Monitoring
alarm_email = "alerts@yourdomain.com"
```

### 2. Initialize Terraform

```bash
terraform init
```

### 3. Review the Plan

```bash
terraform plan
```

### 4. Deploy Infrastructure

```bash
terraform apply
```

Review the changes and type `yes` to confirm.

### 5. Build and Push Docker Image

After infrastructure is deployed, get the ECR repository URL from outputs:

```bash
export ECR_REPO=$(terraform output -raw ecr_repository_url)
export AWS_REGION=$(terraform output -raw aws_region)

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ECR_REPO

# Build and push image
cd ../..  # Back to project root
docker build -t $ECR_REPO:latest -f infra/Dockerfile .
docker push $ECR_REPO:latest
```

### 6. Run Database Migrations

Get an ECS task ID and run migrations:

```bash
# Get task ID
TASK_ID=$(aws ecs list-tasks \
  --cluster $(terraform output -raw ecs_cluster_name) \
  --service-name $(terraform output -raw ecs_service_name) \
  --query 'taskArns[0]' \
  --output text | cut -d'/' -f3)

# Run migrations
aws ecs execute-command \
  --cluster $(terraform output -raw ecs_cluster_name) \
  --task $TASK_ID \
  --container app \
  --interactive \
  --command "alembic upgrade head"
```

### 7. Configure Twilio Webhooks

Get your application URL:

```bash
terraform output application_url
```

Configure your Twilio phone number:
- **Voice URL**: `https://your-domain.com/twilio/voice` (HTTP POST)
- **Status Callback URL**: `https://your-domain.com/twilio/status` (HTTP POST)

For Media Streams, the WebSocket URL is: `wss://your-domain.com/media-stream`

## Infrastructure Components

### Networking

- **VPC**: Isolated network with CIDR `10.0.0.0/16`
- **Public Subnets**: For ALB (2 AZs)
- **Private Subnets**: For ECS, RDS (2 AZs)
- **NAT Gateways**: For outbound internet access from private subnets
- **VPC Flow Logs**: Network traffic monitoring

### Database

- **Engine**: PostgreSQL 16
- **Instance Class**: Configurable (default: `db.t4g.micro`)
- **Storage**: Auto-scaling from 20GB to 100GB
- **Backups**: Automated daily backups (7-day retention)
- **Encryption**: At-rest encryption enabled
- **Multi-AZ**: Enabled for production environments

### Cache

- **Encryption**: In-transit and at-rest encryption
- **Auth**: Token-based authentication
- **Backups**: Automated snapshots (5-day retention)

### Application

- **Platform**: ECS Fargate
- **CPU**: 1 vCPU (configurable)
- **Memory**: 2GB (configurable)
- **Auto-scaling**: CPU and memory-based (1-10 tasks)
- **Health Checks**: ALB health checks on `/health`
- **Deployment**: Rolling updates with circuit breaker

### Load Balancer

- **Type**: Application Load Balancer
- **Listeners**: HTTP (80) and HTTPS (443)
- **SSL/TLS**: ACM certificate (if domain configured)
- **WebSocket**: Full support for Twilio Media Streams
- **Stickiness**: Enabled for WebSocket connections

### Security

- **Secrets Manager**: All sensitive credentials encrypted
- **IAM Roles**: Least-privilege access for ECS tasks
- **Security Groups**: Restrictive ingress/egress rules
- **Encryption**: At-rest and in-transit encryption everywhere

### Monitoring

- **CloudWatch Logs**: Centralized application logging
- **CloudWatch Metrics**: CPU, memory, latency, errors
- **CloudWatch Alarms**: Automated alerting via SNS
- **CloudWatch Dashboard**: Real-time infrastructure overview
- **X-Ray**: Distributed tracing (optional)

## Cost Estimation

Approximate monthly costs for a development environment:

| Service | Configuration | Monthly Cost |
|---------|--------------|--------------|
| ECS Fargate | 2 tasks (1 vCPU, 2GB) | ~$30 |
| RDS PostgreSQL | db.t4g.micro | ~$15 |
| Application Load Balancer | Standard | ~$20 |
| NAT Gateway | 2 AZs | ~$65 |
| Data Transfer | Moderate usage | ~$10 |
| CloudWatch | Logs + Metrics | ~$10 |
| **Total** | | **~$162/month** |

Production costs will be higher due to:
- Multi-AZ RDS (~2x database cost)
- Larger instance sizes
- More ECS tasks
- Higher data transfer

## Environments

### Development

```hcl
environment                = "dev"
db_instance_class          = "db.t4g.micro"
ecs_desired_count          = 1
enable_deletion_protection = false
```

### Staging

```hcl
environment                = "staging"
db_instance_class          = "db.t4g.small"
ecs_desired_count          = 2
enable_deletion_protection = false
```

### Production

```hcl
environment                = "prod"
db_instance_class          = "db.r6g.large"
ecs_desired_count          = 4
ecs_max_capacity           = 20
enable_deletion_protection = true
enable_enhanced_monitoring = true
```

## Useful Commands

### View Outputs

```bash
terraform output
```

### View Specific Output

```bash
terraform output application_url
terraform output ecr_repository_url
```

### View Logs

```bash
aws logs tail /ecs/claims-intake-dev --follow
```

### Update ECS Service

After pushing a new image:

```bash
aws ecs update-service \
  --cluster $(terraform output -raw ecs_cluster_name) \
  --service $(terraform output -raw ecs_service_name) \
  --force-new-deployment
```

### Access CloudWatch Dashboard

```bash
echo "https://console.aws.amazon.com/cloudwatch/home?region=$(terraform output -raw aws_region)#dashboards:name=$(terraform output -raw cloudwatch_dashboard_name)"
```

### Connect to Database

```bash
# Get credentials from Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id $(terraform output -raw rds_credentials_secret_arn) \
  --query SecretString \
  --output text | jq -r '.url'
```

## Maintenance

### Updating Infrastructure

1. Modify Terraform files or variables
2. Run `terraform plan` to review changes
3. Run `terraform apply` to apply changes

### Scaling

Update variables in `terraform.tfvars`:

```hcl
ecs_desired_count = 4
ecs_max_capacity  = 10
```

Then apply:

```bash
terraform apply
```

### Backup and Recovery

**Database Backups:**
- Automated daily backups (7-day retention)
- Manual snapshots available via AWS Console

- Point-in-time recovery available

**Disaster Recovery:**
```bash
# Restore from RDS snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier new-instance \
  --db-snapshot-identifier snapshot-id
```

## Troubleshooting

### ECS Tasks Not Starting

Check CloudWatch logs:
```bash
aws logs tail /ecs/claims-intake-dev --follow
```

Common issues:
- Image not found in ECR
- Secrets Manager permissions
- Security group configuration

### Database Connection Issues

Verify security groups allow traffic from ECS tasks:
```bash
aws ec2 describe-security-groups \
  --group-ids $(terraform output -raw ecs_security_group_id)
```

### High Latency

Check CloudWatch metrics:
- ALB target response time
- ECS CPU/Memory utilization
- RDS CPU/Connections

### WebSocket Connection Failures

Verify:
- ALB listener configuration
- Security group rules
- ECS task health
- Application logs

## Security Best Practices

1. **Rotate Secrets Regularly**
   ```bash
   aws secretsmanager rotate-secret \
     --secret-id $(terraform output -raw app_secrets_arn)
   ```

2. **Enable MFA for AWS Account**

3. **Review IAM Policies Regularly**

4. **Enable AWS CloudTrail**

5. **Use AWS Config for Compliance**

6. **Regular Security Audits**
   ```bash
   aws ecr describe-image-scan-findings \
     --repository-name $(terraform output -raw ecr_repository_url | cut -d'/' -f2)
   ```

## Cleanup

To destroy all infrastructure:

```bash
# WARNING: This will delete all resources including data!
terraform destroy
```

For production, ensure you have:
- Database backups
- Exported configuration
- Documented any manual changes

## Remote State (Recommended for Teams)

Configure S3 backend in `main.tf`:

```hcl
terraform {
  backend "s3" {
    bucket         = "your-terraform-state-bucket"
    key            = "claims-intake/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}
```

Create the S3 bucket and DynamoDB table:

```bash
aws s3 mb s3://your-terraform-state-bucket
aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

## Support

For issues or questions:
- Check CloudWatch logs and metrics
- Review AWS service health dashboard
- Consult Terraform documentation
- Open a GitHub issue

## License

See [LICENSE](../../LICENSE) file.