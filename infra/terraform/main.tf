provider "aws" {
  region = var.aws_region
  default_tags {
    tags = local.common_tags
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

resource "random_password" "db_password" {
  length  = 24
  special = false
}

locals {
  name_prefix = "${var.project}-${var.environment}"

  common_tags = merge(
    {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    },
    var.tags,
  )

  azs = slice(data.aws_availability_zones.available.names, 0, var.az_count)

  # If the operator hasn't pinned an image, default to the repo we create
  # in ecr.tf at :latest. The ECS service will fail-fast until an image is
  # pushed — that's intentional, since the AWS infra is otherwise inert.
  container_image = (
    var.container_image != ""
    ? var.container_image
    : "${aws_ecr_repository.app.repository_url}:latest"
  )

  use_https = var.domain_name != ""

  public_url = (
    local.use_https
    ? "https://${var.domain_name}"
    : "http://${aws_lb.app.dns_name}"
  )
}
