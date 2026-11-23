variable "migration_release" {
  description = "Optional release tag for a one-time EC2 migration when CodeBuild is unavailable."
  type        = string
  default     = null

  validation {
    condition     = var.migration_release == null ? true : can(regex("^release-[a-f0-9]{16}$", var.migration_release))
    error_message = "Supply the release tag generated from the source archive."
  }
}

data "aws_ssm_parameter" "migration_ami" {
  count = var.migration_release == null ? 0 : 1
  name  = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_iam_role" "migration_host" {
  count = var.migration_release == null ? 0 : 1
  name  = "${var.name}-migration-host"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["sts:AssumeRole"], Principal = { Service = "ec2.amazonaws.com" } }]
  })
}

resource "aws_iam_instance_profile" "migration_host" {
  count = var.migration_release == null ? 0 : 1
  name  = "${var.name}-migration-host"
  role  = aws_iam_role.migration_host[0].name
}

resource "aws_iam_role_policy" "migration_host" {
  count = var.migration_release == null ? 0 : 1
  role  = aws_iam_role.migration_host[0].name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow", Action = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.assets.arn}/release-source/${var.migration_release}.zip"
      },
      {
        Effect   = "Allow", Action = ["s3:PutObject"]
        Resource = "${aws_s3_bucket.assets.arn}/releases/migrations/${var.migration_release}.json"
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

resource "aws_instance" "migration_host" {
  count                                = var.migration_release == null ? 0 : 1
  ami                                  = data.aws_ssm_parameter.migration_ami[0].value
  instance_type                        = "t3.micro"
  subnet_id                            = values(aws_subnet.private)[0].id
  associate_public_ip_address          = false
  vpc_security_group_ids               = [aws_security_group.migrate.id]
  iam_instance_profile                 = aws_iam_instance_profile.migration_host[0].name
  instance_initiated_shutdown_behavior = "terminate"
  root_block_device {
    encrypted   = true
    volume_type = "gp3"
  }
  metadata_options {
    http_tokens = "required"
  }
  user_data = replace(templatefile("${path.module}/migration-host.sh.tftpl", {
    region        = var.region
    bucket        = aws_s3_bucket.assets.id
    release       = var.migration_release
    db_host       = aws_db_instance.postgres.address
    admin_secret  = aws_db_instance.postgres.master_user_secret[0].secret_arn
    web_secret    = aws_secretsmanager_secret.runtime["web"].arn
    api_secret    = aws_secretsmanager_secret.runtime["api"].arn
    worker_secret = aws_secretsmanager_secret.runtime["worker"].arn
  }), "\r\n", "\n")
  tags = { Name = "${var.name}-migration-host" }
  depends_on = [
    aws_iam_role_policy.migration_host,
    aws_vpc_security_group_ingress_rule.migration_database,
    aws_vpc_security_group_egress_rule.migration_database,
    aws_vpc_security_group_egress_rule.migration_https,
    aws_route_table_association.private,
  ]
}
