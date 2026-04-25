resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${local.name_prefix}"
  retention_in_days = 30
}

# ----- IAM ------------------------------------------------------------------

data "aws_iam_policy_document" "task_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "task_execution" {
  name               = "${local.name_prefix}-task-exec"
  assume_role_policy = data.aws_iam_policy_document.task_assume.json
}

resource "aws_iam_role_policy_attachment" "task_execution_managed" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Task execution role also needs to read the secrets it injects.
data "aws_iam_policy_document" "task_secrets" {
  statement {
    actions = ["secretsmanager:GetSecretValue"]
    resources = concat(
      [for s in aws_secretsmanager_secret.provider : s.arn],
      [aws_secretsmanager_secret.db_url.arn, aws_secretsmanager_secret.redis_url.arn],
    )
  }
}

resource "aws_iam_policy" "task_secrets" {
  name   = "${local.name_prefix}-task-secrets"
  policy = data.aws_iam_policy_document.task_secrets.json
}

resource "aws_iam_role_policy_attachment" "task_secrets" {
  role       = aws_iam_role.task_execution.name
  policy_arn = aws_iam_policy.task_secrets.arn
}

resource "aws_iam_role" "task" {
  name               = "${local.name_prefix}-task"
  assume_role_policy = data.aws_iam_policy_document.task_assume.json
}

# ----- Task definition ------------------------------------------------------

locals {
  task_secrets = [
    {
      name      = "TWILIO_API_KEY_SID"
      valueFrom = aws_secretsmanager_secret.provider["twilio-api-key-sid"].arn
    },
    {
      name      = "TWILIO_API_KEY_SECRET"
      valueFrom = aws_secretsmanager_secret.provider["twilio-api-key-secret"].arn
    },
    {
      name      = "GEMINI_API_KEY"
      valueFrom = aws_secretsmanager_secret.provider["gemini-api-key"].arn
    },
    {
      name      = "GRADIUM_API_KEY"
      valueFrom = aws_secretsmanager_secret.provider["gradium-api-key"].arn
    },
    {
      name      = "DATABASE_URL"
      valueFrom = aws_secretsmanager_secret.db_url.arn
    },
    {
      name      = "REDIS_URL"
      valueFrom = aws_secretsmanager_secret.redis_url.arn
    },
  ]

  task_env = [
    { name = "PUBLIC_BASE_URL", value = local.public_url },
    { name = "DEFAULT_LANGUAGE", value = var.default_language },
    { name = "SUPPORTED_LANGUAGES", value = var.supported_languages },
    { name = "COMPANY_NAME", value = var.company_name },
    { name = "SLA_HOURS", value = tostring(var.sla_hours) },
    { name = "LOG_LEVEL", value = "INFO" },
    # Operator-supplied; placeholders here so the app boots.
    { name = "TWILIO_ACCOUNT_SID", value = "REPLACE_ME" },
    { name = "TWILIO_PHONE_NUMBER", value = "REPLACE_ME" },
    { name = "GRADIUM_VOICE_ID", value = "REPLACE_ME" },
  ]
}

resource "aws_ecs_task_definition" "app" {
  family                   = "${local.name_prefix}-app"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "app"
      image     = local.container_image
      essential = true
      portMappings = [
        {
          containerPort = var.container_port
          protocol      = "tcp"
        },
      ]
      environment = local.task_env
      secrets     = local.task_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.app.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "app"
        }
      }
    },
  ])
}

# ----- Service --------------------------------------------------------------

resource "aws_ecs_service" "app" {
  name            = "${local.name_prefix}-app"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "app"
    container_port   = var.container_port
  }

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  depends_on = [
    aws_lb_listener.http,
  ]

  lifecycle {
    ignore_changes = [task_definition] # let CI/CD update the image without TF churn
  }
}
