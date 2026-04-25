# Deployment

Two paths are supported: Docker Compose for single-host (dev, small
staging, hackathon demo) and AWS via Terraform for production.

## Path 1 — Docker Compose

Files:

- [`infra/Dockerfile`](../infra/Dockerfile) — Python 3.11 slim, installs
  the package in editable mode, runs `uvicorn app.main:app` on `:8000`.
- [`infra/docker-compose.yml`](../infra/docker-compose.yml) — `app` +
  `postgres:16-alpine` + `redis:7-alpine`, with healthchecks so `app`
  only starts after Postgres / Redis are ready.

```bash
# Start everything (app + Postgres + Redis)
docker compose -f infra/docker-compose.yml up --build

# Or: just dependencies (run the app from your venv)
docker compose -f infra/docker-compose.yml up -d postgres redis
uvicorn app.main:app --reload --port 8000
```

The `app` service reads `../.env` via `env_file:`. Make sure your
`.env` has a `DATABASE_URL` that points at the compose Postgres host
(`postgres`) when running in-compose, or `localhost` when running the
app from your venv.

## Path 2 — AWS via Terraform

Provisions the runtime needed to host the FastAPI app where Twilio can
reach it (stable HTTPS endpoint with WebSocket support).

Files: [`infra/terraform/`](../infra/terraform/).

| Module | Purpose |
|---|---|
| `main.tf`, `versions.tf`, `variables.tf`, `outputs.tf` | Wiring |
| `vpc.tf` | VPC, 2 public + 2 private subnets across two AZs, IGW, NAT |
| `security.tf` | Security groups (ALB → app, app → RDS / Redis) |
| `database.tf` | RDS Postgres 16 (`db.t4g.micro`, single-AZ) |
| `cache.tf` | ElastiCache Redis 7 (`cache.t4g.micro`, single node) |
| `ecr.tf` | ECR repo + lifecycle policy |
| `ecs.tf` | ECS Fargate cluster, task def, service, IAM, ALB target group |
| `alb.tf` | ALB, listeners, target group, optional ACM cert |
| `secrets.tf` | Secrets Manager entries for all provider keys |

### Bring up

```bash
cd infra/terraform
terraform init
# Optionally tweak terraform.tfvars
terraform plan
terraform apply
```

After apply, fill in the API key secrets (Terraform creates the entries
but **does not** populate them, so they don't end up in
`terraform.tfstate`):

```bash
aws secretsmanager put-secret-value --secret-id .../GEMINI_API_KEY    --secret-string "..."
aws secretsmanager put-secret-value --secret-id .../GRADIUM_API_KEY   --secret-string "..."
aws secretsmanager put-secret-value --secret-id .../TWILIO_API_KEY_SECRET --secret-string "..."
```

### Build + push the image

```bash
aws ecr get-login-password --region eu-central-1 \
  | docker login --username AWS --password-stdin "$(terraform output -raw ecr_repo_url)"

docker build -f ../Dockerfile -t voice-intake:latest ../..
docker tag voice-intake:latest "$(terraform output -raw ecr_repo_url):latest"
docker push  "$(terraform output -raw ecr_repo_url):latest"

aws ecs update-service \
  --cluster "$(terraform output -raw ecs_cluster_name)" \
  --service "$(terraform output -raw ecs_service_name)" \
  --force-new-deployment
```

### Point Twilio at the ALB

```
https://<terraform output -raw public_url>/twilio/voice
```

Set this as the Voice webhook on your Twilio number (Console → Phone
Numbers → your number → Voice & Fax → A call comes in → Webhook).

### TLS

If `domain_name` is set in `terraform.tfvars`, the stack provisions an
ACM cert via Route 53 DNS validation and an HTTPS listener on the ALB.
Twilio Programmable Voice **requires** HTTPS for production webhooks —
HTTP is only acceptable in dev (where ngrok terminates TLS for you).

### WebSocket support

The ALB target group is configured with sticky sessions and a long idle
timeout so Twilio Media Streams WebSockets stay alive across an entire
call. Standard ALB WebSocket caveats apply (idle timeout > expected
call length, no per-target connection limit that would terminate active
calls).

## Non-goals (current Terraform stack)

This is a hackathon-grade single-environment stack. For real prod:

- Multi-AZ RDS.
- Autoscaling for ECS (CPU + concurrent-call metric).
- WAF on the ALB.
- KMS-backed Secrets Manager keys.
- Remote Terraform backend (S3 + DynamoDB lock).
- Centralized logging (CloudWatch → S3 archive).
- Per-environment workspaces (`dev` / `stg` / `prod`).

## Pre-deployment checklist

- [ ] `pytest -q` passes locally.
- [ ] `mypy --strict app/` passes.
- [ ] `ruff check .` passes.
- [ ] `.env` (or Secrets Manager equivalents) has every key in
      [`configuration.md`](configuration.md) §"Required variables".
- [ ] The image was rebuilt **after** the most recent code change (don't
      re-deploy the previous tag by mistake).
- [ ] Twilio Voice webhook points at the new public URL.
- [ ] You called the number end-to-end and heard the agent answer
      (`CLAUDE.md` §10: manual smoke test before every release).
