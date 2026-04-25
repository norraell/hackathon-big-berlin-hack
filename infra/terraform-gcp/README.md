# Terraform Infrastructure for AI Claims Intake System (Google Cloud Platform)

This directory contains Terraform Infrastructure as Code (IaC) for deploying the AI Claims Intake System to Google Cloud Platform (GCP).

## Architecture Overview

The infrastructure includes:

- **VPC Network**: Custom VPC with private Google access
- **Cloud SQL PostgreSQL**: Managed PostgreSQL database
- **Memorystore Redis**: Managed Redis for session state
- **Cloud Run**: Serverless container platform
- **Cloud Load Balancing**: Global load balancer with WebSocket support
- **Secret Manager**: Secure credential storage
- **Cloud Monitoring**: Logging and monitoring
- **Artifact Registry**: Docker image registry

## Prerequisites

1. **GCP Account** with billing enabled
2. **Terraform** >= 1.5.0 ([Install](https://www.terraform.io/downloads))
3. **gcloud CLI** configured ([Install](https://cloud.google.com/sdk/docs/install))
4. **Docker** for building images ([Install](https://docs.docker.com/get-docker/))
5. **GCP Project** created

## Quick Start

### 1. Set up GCP Project

```bash
# Set your project ID
export PROJECT_ID="your-gcp-project-id"

# Set the project
gcloud config set project $PROJECT_ID

# Enable billing (if not already enabled)
gcloud beta billing projects link $PROJECT_ID --billing-account=YOUR_BILLING_ACCOUNT_ID

# Authenticate
gcloud auth application-default login
```

### 2. Configure Variables

```bash
cd infra/terraform-gcp
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

```hcl
# Required: GCP Configuration
gcp_project_id = "your-gcp-project-id"
gcp_region     = "us-central1"
environment    = "dev"

# Required: Twilio Credentials
twilio_account_sid  = "your_actual_sid"
twilio_auth_token   = "your_actual_token"
twilio_phone_number = "+1234567890"

# Required: AI Service API Keys
gemini_api_key  = "your_actual_key"
groq_api_key    = "your_actual_key"
gradium_api_key = "your_actual_key"

# Required: Application Secret
secret_key = "generate_a_strong_random_key_here"

# Optional: Domain Configuration
domain_name      = "claims.yourdomain.com"
create_dns_record = true
dns_zone_name    = "your-dns-zone"

# Optional: Monitoring
alert_email = "alerts@yourdomain.com"
```

### 3. Initialize and Deploy

```bash
# Initialize Terraform
terraform init

# Review the plan
terraform plan

# Deploy infrastructure
terraform apply
```

### 4. Build and Deploy Application

```bash
# Get Artifact Registry location
export REGISTRY=$(terraform output -raw artifact_registry_url)
export PROJECT_ID=$(terraform output -raw project_id)
export REGION=$(terraform output -raw region)

# Configure Docker for Artifact Registry
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# Build and push image
cd ../..
docker build -t ${REGISTRY}/claims-intake:latest -f infra/Dockerfile .
docker push ${REGISTRY}/claims-intake:latest

# Deploy to Cloud Run
cd infra/terraform-gcp
terraform apply -var="app_image_tag=latest"
```

### 5. Run Database Migrations

```bash
# Get Cloud Run service URL
SERVICE_URL=$(terraform output -raw cloud_run_url)

# Run migrations via Cloud Run Jobs or Cloud Build
gcloud run jobs create db-migrate \
  --image ${REGISTRY}/claims-intake:latest \
  --command alembic \
  --args "upgrade,head" \
  --region ${REGION} \
  --vpc-connector $(terraform output -raw vpc_connector_name) \
  --set-env-vars DATABASE_URL=$(terraform output -raw database_url)

gcloud run jobs execute db-migrate --region ${REGION}
```

### 6. Configure Twilio Webhooks

```bash
# Get your application URL
terraform output cloud_run_url
```

Configure your Twilio phone number:
- **Voice URL**: `https://your-cloud-run-url.run.app/twilio/voice` (HTTP POST)
- **Status Callback URL**: `https://your-cloud-run-url.run.app/twilio/status` (HTTP POST)
- **Media Stream URL**: `wss://your-cloud-run-url.run.app/media-stream`

## GCP Services Used

### Compute
- **Cloud Run**: Serverless container platform (auto-scaling 0-100 instances)
- **VPC Access Connector**: Connects Cloud Run to VPC

### Database
- **Cloud SQL PostgreSQL**: Managed PostgreSQL 16
- **Memorystore Redis**: Managed Redis 7.x

### Networking
- **VPC Network**: Custom network with private Google access
- **Cloud NAT**: Outbound internet access
- **Cloud Load Balancing**: Global HTTPS load balancer
- **Cloud Armor**: DDoS protection and WAF

### Storage
- **Artifact Registry**: Docker image storage
- **Cloud Storage**: Backup storage

### Security
- **Secret Manager**: Encrypted secrets storage
- **IAM**: Service accounts and permissions
- **Cloud KMS**: Encryption key management

### Monitoring
- **Cloud Logging**: Centralized logging
- **Cloud Monitoring**: Metrics and dashboards
- **Cloud Trace**: Distributed tracing
- **Error Reporting**: Error aggregation

## Cost Estimation

### Development Environment (~$50-80/month)
- Cloud Run: $10-20 (minimal traffic)
- Cloud SQL (db-f1-micro): $7-10
- Memorystore Redis (1GB): $25-30
- Networking: $5-10
- Logging/Monitoring: $5-10

### Production Environment (~$200-400/month)
- Cloud Run: $50-100 (moderate traffic)
- Cloud SQL (db-n1-standard-1): $50-80
- Memorystore Redis (5GB, HA): $80-120
- Load Balancer: $20-30
- Networking: $20-40
- Logging/Monitoring: $20-30

## Key Features

✅ **Serverless**: Cloud Run auto-scales from 0 to 100 instances
✅ **Managed Services**: No server management required
✅ **Global**: Cloud Load Balancing with global anycast IPs
✅ **Secure**: Private VPC, Secret Manager, IAM
✅ **Observable**: Cloud Logging, Monitoring, Trace
✅ **Cost-Effective**: Pay only for what you use
✅ **WebSocket Support**: Full support for Twilio Media Streams
✅ **High Availability**: Multi-zone deployment

## Useful Commands

### View Outputs
```bash
terraform output
```

### View Logs
```bash
gcloud logging read "resource.type=cloud_run_revision" --limit 50 --format json
```

### Update Cloud Run Service
```bash
gcloud run services update claims-intake-dev \
  --region us-central1 \
  --image ${REGISTRY}/claims-intake:latest
```

### Connect to Database
```bash
# Get connection name
terraform output database_connection_name

# Connect via Cloud SQL Proxy
cloud-sql-proxy $(terraform output -raw database_connection_name)
```

### Scale Cloud Run
```bash
gcloud run services update claims-intake-dev \
  --region us-central1 \
  --min-instances 2 \
  --max-instances 20
```

## Monitoring

### View Metrics
```bash
# Open Cloud Console
echo "https://console.cloud.google.com/monitoring/dashboards?project=$(terraform output -raw project_id)"
```

### View Logs
```bash
# Tail logs
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=claims-intake-dev"
```

### View Errors
```bash
# View error reporting
echo "https://console.cloud.google.com/errors?project=$(terraform output -raw project_id)"
```

## Troubleshooting

### Cloud Run Not Starting
```bash
# Check logs
gcloud logging read "resource.type=cloud_run_revision" --limit 10

# Check service status
gcloud run services describe claims-intake-dev --region us-central1
```

### Database Connection Issues
```bash
# Test connection
gcloud sql connect $(terraform output -raw database_instance_name) --user=claims_user

# Check private IP
gcloud sql instances describe $(terraform output -raw database_instance_name)
```

### High Latency
```bash
# Check Cloud Run metrics
gcloud monitoring time-series list \
  --filter='metric.type="run.googleapis.com/request_latencies"'
```

## Security Best Practices

1. **Enable VPC Service Controls** (for production)
2. **Use Workload Identity** for service authentication
3. **Enable Cloud Armor** for DDoS protection
4. **Rotate secrets regularly** via Secret Manager
5. **Enable audit logging** via Cloud Audit Logs
6. **Use least-privilege IAM** roles
7. **Enable Binary Authorization** for container security

## Cleanup

```bash
# WARNING: This will delete all resources!
terraform destroy
```

## Support

- [GCP Documentation](https://cloud.google.com/docs)
- [Terraform GCP Provider](https://registry.terraform.io/providers/hashicorp/google/latest/docs)
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud SQL Documentation](https://cloud.google.com/sql/docs)

## Next Steps

1. Set up CI/CD with Cloud Build
2. Configure custom domain with Cloud DNS
3. Enable Cloud CDN for static assets
4. Set up Cloud Armor security policies
5. Configure alerting policies
6. Implement backup strategies
7. Set up disaster recovery procedures