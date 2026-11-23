locals {
  release_jobs = {
    build   = "infrastructure/release/buildspec.yml"
    migrate = "infrastructure/release/migrate.yml"
  }
  release_source_arn = "${aws_s3_bucket.assets.arn}/release-source/*"
}

resource "aws_secretsmanager_secret" "runtime" {
  for_each = local.roles
  name     = "${var.name}/runtime/${each.key}"
}

resource "aws_cloudwatch_log_group" "release" {
  for_each          = local.release_jobs
  name              = "/bytebistro/${var.name}/release-${each.key}"
  retention_in_days = 14
}

resource "aws_iam_role" "release" {
  for_each = local.release_jobs
  name     = "${var.name}-release-${each.key}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "codebuild.amazonaws.com" }
      Condition = { StringEquals = {
        "aws:SourceAccount" = data.aws_caller_identity.current.account_id
        "aws:SourceArn"     = "arn:${data.aws_partition.current.partition}:codebuild:${var.region}:${data.aws_caller_identity.current.account_id}:project/${var.name}-${each.key}"
      } }
    }]
  })
}

resource "aws_iam_role_policy" "release_common" {
  for_each = local.release_jobs
  role     = aws_iam_role.release[each.key].name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:GetObject", "s3:GetObjectVersion"], Resource = local.release_source_arn },
      { Effect = "Allow", Action = ["s3:GetBucketLocation"], Resource = aws_s3_bucket.assets.arn },
      {
        Effect   = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.release[each.key].arn}:log-stream:*"
      }
    ]
  })
}

resource "aws_iam_role_policy" "release_build" {
  role = aws_iam_role.release["build"].name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
      {
        Effect   = "Allow"
        Action   = ["ecr:BatchCheckLayerAvailability", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart", "ecr:CompleteLayerUpload", "ecr:PutImage", "ecr:DescribeImages"]
        Resource = [for repository in aws_ecr_repository.main : repository.arn]
      },
      {
        Effect    = "Allow", Action = ["s3:ListBucket"], Resource = aws_s3_bucket.assets.arn
        Condition = { StringLike = { "s3:prefix" = ["static/", "static/*"] } }
      },
      {
        Effect   = "Allow", Action = ["s3:PutObject"]
        Resource = ["${aws_s3_bucket.assets.arn}/static/*", "${aws_s3_bucket.assets.arn}/releases/*"]
      }
    ]
  })
}

resource "aws_security_group" "migrate" {
  name   = "${var.name}-migration"
  vpc_id = aws_vpc.main.id
}

resource "aws_vpc_security_group_ingress_rule" "migration_database" {
  security_group_id            = aws_security_group.main["db"].id
  referenced_security_group_id = aws_security_group.migrate.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_vpc_security_group_egress_rule" "migration_database" {
  security_group_id            = aws_security_group.migrate.id
  referenced_security_group_id = aws_security_group.main["db"].id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_vpc_security_group_egress_rule" "migration_https" {
  security_group_id = aws_security_group.migrate.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

resource "aws_iam_role_policy" "release_migrate" {
  role = aws_iam_role.release["migrate"].name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ec2:CreateNetworkInterface", "ec2:DescribeNetworkInterfaces", "ec2:DeleteNetworkInterface", "ec2:DescribeSubnets", "ec2:DescribeSecurityGroups", "ec2:DescribeDhcpOptions", "ec2:DescribeVpcs"]
        Resource = "*"
      },
      {
        Effect   = "Allow", Action = ["ec2:CreateNetworkInterfacePermission"]
        Resource = "arn:${data.aws_partition.current.partition}:ec2:${var.region}:${data.aws_caller_identity.current.account_id}:network-interface/*"
        Condition = { StringEquals = {
          "ec2:AuthorizedService" = "codebuild.amazonaws.com"
          "ec2:Subnet"            = [for subnet in aws_subnet.private : subnet.arn]
        } }
      },
      {
        Effect   = "Allow", Action = ["secretsmanager:GetSecretValue"]
        Resource = aws_db_instance.postgres.master_user_secret[0].secret_arn
      },
      {
        Effect   = "Allow", Action = ["secretsmanager:ListSecretVersionIds", "secretsmanager:GetSecretValue", "secretsmanager:PutSecretValue"]
        Resource = [for secret in aws_secretsmanager_secret.runtime : secret.arn]
      }
    ]
  })
}

resource "aws_codebuild_project" "build" {
  name                   = "${var.name}-build"
  service_role           = aws_iam_role.release["build"].arn
  build_timeout          = 30
  concurrent_build_limit = 1
  artifacts {
    type = "NO_ARTIFACTS"
  }
  source {
    type      = "S3"
    location  = "${aws_s3_bucket.assets.id}/release-source/source.zip"
    buildspec = local.release_jobs.build
  }
  environment {
    compute_type    = "BUILD_GENERAL1_MEDIUM"
    image           = "aws/codebuild/standard:7.0"
    type            = "LINUX_CONTAINER"
    privileged_mode = true
    dynamic "environment_variable" {
      for_each = {
        WEB_REPOSITORY    = aws_ecr_repository.main["web"].repository_url
        API_REPOSITORY    = aws_ecr_repository.main["api"].repository_url
        WORKER_REPOSITORY = aws_ecr_repository.main["worker"].repository_url
        ARTIFACT_BUCKET   = aws_s3_bucket.assets.id
        RELEASE_TAG       = "release"
      }
      content {
        name  = environment_variable.key
        value = environment_variable.value
      }
    }
  }
  logs_config {
    cloudwatch_logs {
      group_name = aws_cloudwatch_log_group.release["build"].name
    }
  }
  depends_on = [aws_iam_role_policy.release_common, aws_iam_role_policy.release_build]
}

resource "aws_codebuild_project" "migrate" {
  name                   = "${var.name}-migrate"
  service_role           = aws_iam_role.release["migrate"].arn
  build_timeout          = 30
  concurrent_build_limit = 1
  artifacts {
    type = "NO_ARTIFACTS"
  }
  source {
    type      = "S3"
    location  = "${aws_s3_bucket.assets.id}/release-source/source.zip"
    buildspec = local.release_jobs.migrate
  }
  environment {
    compute_type = "BUILD_GENERAL1_SMALL"
    image        = "aws/codebuild/standard:7.0"
    type         = "LINUX_CONTAINER"
    dynamic "environment_variable" {
      for_each = {
        DB_HOST         = aws_db_instance.postgres.address
        DB_ADMIN_SECRET = aws_db_instance.postgres.master_user_secret[0].secret_arn
        WEB_SECRET      = aws_secretsmanager_secret.runtime["web"].arn
        API_SECRET      = aws_secretsmanager_secret.runtime["api"].arn
        WORKER_SECRET   = aws_secretsmanager_secret.runtime["worker"].arn
      }
      content {
        name  = environment_variable.key
        value = environment_variable.value
      }
    }
  }
  vpc_config {
    vpc_id             = aws_vpc.main.id
    subnets            = [for subnet in aws_subnet.private : subnet.id]
    security_group_ids = [aws_security_group.migrate.id]
  }
  logs_config {
    cloudwatch_logs {
      group_name = aws_cloudwatch_log_group.release["migrate"].name
    }
  }
  depends_on = [aws_iam_role_policy.release_common, aws_iam_role_policy.release_migrate]
}

output "runtime_secret_arns" {
  value = { for service, secret in aws_secretsmanager_secret.runtime : service => secret.arn }
}
