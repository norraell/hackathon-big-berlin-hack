# Terraform: AWS infrastructure for the voice intake agent

Provisions the runtime needed to host the FastAPI app where Twilio can reach
it (stable HTTPS endpoint with WebSocket support):

* **VPC** — 2 public + 2 private subnets across two AZs.
* **RDS Postgres 16** — single-AZ `db.t4g.micro` in private subnets.
* **ElastiCache Redis 7** — single `cache.t4g.micro` node in private subnets.
* **ECR** — image registry for the FastAPI container.
* **ECS Fargate** — service running `app.main:app`, behind an ALB with
  WebSocket support (sticky sessions enabled).
* **ACM + Route53** *(optional)* — TLS for the ALB hostname Twilio dials
  into. If `domain_name` is empty, the stack uses a plain HTTP listener
  (intended for dev/ngrok-fronted setups only).
* **Secrets Manager** — entries for every API key the app needs; injected
  into the task definition as env vars.

## Files

| File | Purpose |
|---|---|
| `main.tf` | Provider, locals, common tags |
| `versions.tf` | Required providers + min versions |
| `variables.tf` | Input variables (region, image tag, instance sizes, …) |
| `outputs.tf` | ALB hostname, ECR repo URL, RDS endpoint |
| `vpc.tf` | VPC, subnets, IGW, NAT, route tables |
| `security.tf` | Security groups (ALB → app, app → RDS / Redis) |
| `database.tf` | RDS subnet group + instance |
| `cache.tf` | ElastiCache subnet group + Redis cluster |
| `ecr.tf` | ECR repo + lifecycle policy |
| `ecs.tf` | Cluster, task def, service, IAM, ALB target group |
| `alb.tf` | ALB, listeners, target group, optional ACM cert |
| `secrets.tf` | Secrets Manager entries for all provider keys |

## Usage

```bash
cd infra/terraform
terraform init
# Review and (optionally) tweak terraform.tfvars
terraform plan
terraform apply
```

After apply, push the image:

```bash
aws ecr get-login-password --region eu-central-1 \
  | docker login --username AWS --password-stdin "$(terraform output -raw ecr_repo_url)"

docker build -f ../Dockerfile -t voice-intake:latest ../..
docker tag voice-intake:latest "$(terraform output -raw ecr_repo_url):latest"
docker push "$(terraform output -raw ecr_repo_url):latest"

aws ecs update-service \
  --cluster "$(terraform output -raw ecs_cluster_name)" \
  --service "$(terraform output -raw ecs_service_name)" \
  --force-new-deployment
```

Then point the Twilio Voice webhook at:

```
https://<terraform output -raw public_url>/twilio/voice
```

## Notes / non-goals

* This is a hackathon-grade single-environment stack. For prod: multi-AZ
  RDS, autoscaling for ECS, WAF on the ALB, KMS-backed secrets, and a
  remote Terraform backend (S3 + DynamoDB lock).
* Provider API keys are stored in Secrets Manager but **not** populated by
  Terraform — `terraform apply` creates the entries; you run
  `aws secretsmanager put-secret-value` to fill them so they don't end up
  in `terraform.tfstate`.
