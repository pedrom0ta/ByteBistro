resource "aws_ecr_repository" "main" {
  for_each             = local.roles
  name                 = "${var.name}/${each.key}"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_cloudwatch_log_group" "app" {
  for_each          = local.roles
  name              = "/bytebistro/${var.name}/${each.key}"
  retention_in_days = 30
}

resource "aws_iam_role" "instance" {
  for_each = local.fleets
  name     = "${var.name}-${each.key}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  for_each   = local.fleets
  role       = aws_iam_role.instance[each.key].name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

locals {
  fleet_services = { web = ["web", "api"], worker = ["worker"] }
  images = var.runtime == null ? {} : {
    web    = var.runtime.web_digest
    api    = var.runtime.api_digest
    worker = var.runtime.worker_digest
  }
}

resource "aws_iam_role_policy" "runtime" {
  for_each = var.runtime == null ? toset([]) : local.fleets
  role     = aws_iam_role.instance[each.key].name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
        {
          Effect   = "Allow"
          Action   = ["ecr:BatchCheckLayerAvailability", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
          Resource = [for service in local.fleet_services[each.key] : aws_ecr_repository.main[service].arn]
        },
        {
          Effect   = "Allow"
          Action   = ["secretsmanager:GetSecretValue"]
          Resource = [for service in local.fleet_services[each.key] : var.runtime.runtime_secret_arns[service]]
        },
        {
          Effect   = "Allow"
          Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
          Resource = [for service in local.fleet_services[each.key] : "${aws_cloudwatch_log_group.app[service].arn}:log-stream:*"]
        }
      ],
      [
        for statement in [
          {
            Effect   = "Allow"
            Action   = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:ChangeMessageVisibility"]
            Resource = aws_sqs_queue.jobs.arn
          },
          {
            Effect   = "Allow"
            Action   = ["sns:Publish"]
            Resource = aws_sns_topic.notifications.arn
          },
          {
            Effect   = "Allow"
            Action   = ["kms:GenerateDataKey", "kms:Decrypt"]
            Resource = aws_kms_key.notifications.arn
            Condition = {
              StringEquals = { "kms:ViaService" = "sns.${var.region}.amazonaws.com" }
            }
          }
        ] : statement if each.key == "worker"
      ]
    )
  })
}

resource "aws_iam_instance_profile" "main" {
  for_each = local.fleets
  name     = "${var.name}-${each.key}"
  role     = aws_iam_role.instance[each.key].name
}

resource "aws_launch_template" "main" {
  for_each               = var.runtime == null ? toset([]) : local.fleets
  name_prefix            = "${var.name}-${each.key}-"
  image_id               = var.runtime.ami_id
  instance_type          = var.instance_type
  update_default_version = true
  monitoring {
    enabled = true
  }
  iam_instance_profile {
    arn = aws_iam_instance_profile.main[each.key].arn
  }
  vpc_security_group_ids = [aws_security_group.main[each.key].id]
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }
  user_data = base64encode(replace(templatefile("${path.module}/bootstrap.sh.tftpl", {
    region        = var.region
    fleet         = each.key
    registry      = split("/", aws_ecr_repository.main[each.key].repository_url)[0]
    domain        = local.public_domain
    origin_domain = local.origin_domain
    queue_url     = aws_sqs_queue.jobs.url
    topic_arn     = aws_sns_topic.notifications.arn
    services = {
      for service in local.fleet_services[each.key] : service => {
        image     = "${aws_ecr_repository.main[service].repository_url}@${local.images[service]}"
        secret    = var.runtime.runtime_secret_arns[service]
        log_group = aws_cloudwatch_log_group.app[service].name
      }
    }
    service_order = each.key == "web" ? tolist(["api", "web"]) : tolist(["worker"])
  }), "\r\n", "\n"))
}

resource "aws_autoscaling_group" "main" {
  for_each                  = aws_launch_template.main
  name                      = "${var.name}-${each.key}"
  min_size                  = 2
  enabled_metrics           = ["GroupInServiceInstances"]
  max_size                  = 6
  desired_capacity          = 2
  vpc_zone_identifier       = [for subnet in aws_subnet.private : subnet.id]
  target_group_arns         = each.key == "web" ? [aws_lb_target_group.web.arn] : []
  health_check_type         = each.key == "web" ? "ELB" : "EC2"
  health_check_grace_period = 300
  default_instance_warmup   = 300
  launch_template {
    id      = each.value.id
    version = each.value.latest_version
  }
  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 100
      max_healthy_percentage = 150
    }
  }
  lifecycle {
    ignore_changes = [desired_capacity]
  }
  depends_on = [aws_iam_role_policy.runtime, aws_lb_listener_rule.cloudfront, aws_route_table_association.private]
}

resource "aws_autoscaling_policy" "cpu" {
  for_each               = aws_autoscaling_group.main
  name                   = "${var.name}-${each.key}-cpu"
  policy_type            = "TargetTrackingScaling"
  autoscaling_group_name = each.value.name
  target_tracking_configuration {
    target_value = 55
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }
  }
}

resource "aws_autoscaling_policy" "job_backlog" {
  count                  = var.runtime == null ? 0 : 1
  name                   = "${var.name}-worker-backlog"
  policy_type            = "TargetTrackingScaling"
  autoscaling_group_name = aws_autoscaling_group.main["worker"].name
  target_tracking_configuration {
    target_value = 20
    customized_metric_specification {
      metrics {
        id = "jobs"
        metric_stat {
          metric {
            namespace   = "AWS/SQS"
            metric_name = "ApproximateNumberOfMessagesVisible"
            dimensions {
              name  = "QueueName"
              value = aws_sqs_queue.jobs.name
            }
          }
          stat = "Average"
        }
      }
      metrics {
        id = "workers"
        metric_stat {
          metric {
            namespace   = "AWS/AutoScaling"
            metric_name = "GroupInServiceInstances"
            dimensions {
              name  = "AutoScalingGroupName"
              value = aws_autoscaling_group.main["worker"].name
            }
          }
          stat = "Average"
        }
      }
      metrics {
        id          = "backlog"
        expression  = "IF(workers>0,jobs/workers,0)"
        return_data = true
      }
    }
  }
}
