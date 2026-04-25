# AWS Secrets Manager for Application Secrets

# Application Secrets
resource "aws_secretsmanager_secret" "app_secrets" {
  name_prefix             = "${local.name_prefix}-app-secrets-"
  description             = "Application secrets for ${local.name_prefix}"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0

  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "app_secrets" {
  secret_id = aws_secretsmanager_secret.app_secrets.id
  secret_string = jsonencode({
    # Twilio Configuration
    TWILIO_ACCOUNT_SID   = var.twilio_account_sid
    TWILIO_AUTH_TOKEN    = var.twilio_auth_token
    TWILIO_PHONE_NUMBER  = var.twilio_phone_number

    # AI Service API Keys
    GEMINI_API_KEY  = var.gemini_api_key
    GROQ_API_KEY    = var.groq_api_key
    GRADIUM_API_KEY = var.gradium_api_key

    # Gradium TTS Configuration
    GRADIUM_TTS_VOICE_ID  = var.gradium_tts_voice_id
    GRADIUM_TTS_ENDPOINT  = "wss://api.gradium.ai/api/speech/tts"

    # Application Configuration
    SECRET_KEY        = var.secret_key
    DEFAULT_LANGUAGE  = var.default_language
    SUPPORTED_LANGUAGES = var.supported_languages

    # Data Retention
    AUDIO_RETENTION_DAYS      = tostring(var.audio_retention_days)
    TRANSCRIPT_RETENTION_DAYS = tostring(var.transcript_retention_days)

    # Database URL (from RDS secret)
    DATABASE_URL = jsondecode(aws_secretsmanager_secret_version.db_credentials.secret_string).url

    # Public Base URL (will be set after ALB creation)
    PUBLIC_BASE_URL = var.domain_name != "" ? "https://${var.domain_name}" : "https://${aws_lb.main.dns_name}"

    # Logging
    LOG_LEVEL = "INFO"
  })

  depends_on = [
    aws_secretsmanager_secret_version.db_credentials
  ]
}

# IAM Policy for ECS tasks to read secrets
resource "aws_iam_policy" "secrets_access" {
  name_prefix = "${local.name_prefix}-secrets-access-"
  description = "Allow ECS tasks to read secrets from Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          aws_secretsmanager_secret.app_secrets.arn,
          aws_secretsmanager_secret.db_credentials.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "secretsmanager.${var.aws_region}.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = local.common_tags
}