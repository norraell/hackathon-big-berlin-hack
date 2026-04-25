# CloudWatch Monitoring and SNS Alerts

# SNS Topic for Alerts
resource "aws_sns_topic" "alerts" {
  count = var.alarm_email != "" ? 1 : 0
  name  = "${local.name_prefix}-alerts"

  tags = local.common_tags
}

resource "aws_sns_topic_subscription" "alerts_email" {
  count     = var.alarm_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alerts[0].arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${local.name_prefix}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ECS", "CPUUtilization", { stat = "Average" }],
            [".", "MemoryUtilization", { stat = "Average" }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "ECS Service Metrics"
          yAxis = {
            left = {
              min = 0
              max = 100
            }
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", { stat = "Average" }],
            [".", "RequestCount", { stat = "Sum" }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "ALB Metrics"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/RDS", "CPUUtilization", { stat = "Average" }],
            [".", "DatabaseConnections", { stat = "Average" }],
            [".", "FreeStorageSpace", { stat = "Average" }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "RDS Metrics"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ElastiCache", "CPUUtilization", { stat = "Average" }],
            [".", "DatabaseMemoryUsagePercentage", { stat = "Average" }],
            [".", "NetworkBytesIn", { stat = "Sum" }],
            [".", "NetworkBytesOut", { stat = "Sum" }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "Database Metrics"
        }
      },
      {
        type = "log"
        properties = {
          query   = "SOURCE '${aws_cloudwatch_log_group.ecs.name}' | fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 20"
          region  = var.aws_region
          title   = "Recent Errors"
        }
      }
    ]
  })
}

# CloudWatch Log Metric Filters
resource "aws_cloudwatch_log_metric_filter" "error_count" {
  name           = "${local.name_prefix}-error-count"
  log_group_name = aws_cloudwatch_log_group.ecs.name
  pattern        = "[time, request_id, level = ERROR*, ...]"

  metric_transformation {
    name      = "ErrorCount"
    namespace = "${local.name_prefix}/Application"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "latency_high" {
  name           = "${local.name_prefix}-high-latency"
  log_group_name = aws_cloudwatch_log_group.ecs.name
  pattern        = "[time, request_id, level, msg, latency > 1500, ...]"

  metric_transformation {
    name      = "HighLatencyCount"
    namespace = "${local.name_prefix}/Application"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "stt_low_confidence" {
  name           = "${local.name_prefix}-stt-low-confidence"
  log_group_name = aws_cloudwatch_log_group.ecs.name
  pattern        = "[time, request_id, level, msg = *low*confidence*, ...]"

  metric_transformation {
    name      = "LowSTTConfidenceCount"
    namespace = "${local.name_prefix}/Application"
    value     = "1"
  }
}

# CloudWatch Alarms for Application Metrics
resource "aws_cloudwatch_metric_alarm" "error_rate" {
  alarm_name          = "${local.name_prefix}-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ErrorCount"
  namespace           = "${local.name_prefix}/Application"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors application error rate"
  alarm_actions       = var.alarm_email != "" ? [aws_sns_topic.alerts[0].arn] : []
  treat_missing_data  = "notBreaching"

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "high_latency_rate" {
  alarm_name          = "${local.name_prefix}-high-latency-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "HighLatencyCount"
  namespace           = "${local.name_prefix}/Application"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors high latency occurrences (>1500ms)"
  alarm_actions       = var.alarm_email != "" ? [aws_sns_topic.alerts[0].arn] : []
  treat_missing_data  = "notBreaching"

  tags = local.common_tags
}

# CloudWatch Insights Queries (saved for easy access)
resource "aws_cloudwatch_query_definition" "error_analysis" {
  name = "${local.name_prefix}-error-analysis"

  log_group_names = [
    aws_cloudwatch_log_group.ecs.name
  ]

  query_string = <<-QUERY
    fields @timestamp, @message, level, request_id
    | filter level = "ERROR"
    | sort @timestamp desc
    | limit 100
  QUERY
}

resource "aws_cloudwatch_query_definition" "latency_analysis" {
  name = "${local.name_prefix}-latency-analysis"

  log_group_names = [
    aws_cloudwatch_log_group.ecs.name
  ]

  query_string = <<-QUERY
    fields @timestamp, request_id, latency_ms
    | filter latency_ms > 1500
    | stats avg(latency_ms) as avg_latency, max(latency_ms) as max_latency, count() as count by bin(5m)
    | sort @timestamp desc
  QUERY
}

resource "aws_cloudwatch_query_definition" "call_success_rate" {
  name = "${local.name_prefix}-call-success-rate"

  log_group_names = [
    aws_cloudwatch_log_group.ecs.name
  ]

  query_string = <<-QUERY
    fields @timestamp, call_id, status
    | stats count() as total_calls, 
            sum(status = "completed") as successful_calls,
            sum(status = "failed") as failed_calls
    | fields (successful_calls / total_calls * 100) as success_rate
  QUERY
}

resource "aws_cloudwatch_query_definition" "stt_confidence_analysis" {
  name = "${local.name_prefix}-stt-confidence-analysis"

  log_group_names = [
    aws_cloudwatch_log_group.ecs.name
  ]

  query_string = <<-QUERY
    fields @timestamp, stt_confidence
    | filter stt_confidence > 0
    | stats avg(stt_confidence) as avg_confidence, 
            min(stt_confidence) as min_confidence,
            count() as total_transcriptions
    | sort @timestamp desc
  QUERY
}

# X-Ray Tracing (optional but recommended for production)
resource "aws_xray_sampling_rule" "main" {
  rule_name      = "${local.name_prefix}-sampling-rule"
  priority       = 1000
  version        = 1
  reservoir_size = 1
  fixed_rate     = 0.05
  url_path       = "*"
  host           = "*"
  http_method    = "*"
  service_type   = "*"
  service_name   = "*"
  resource_arn   = "*"

  attributes = {
    Environment = var.environment
  }
}