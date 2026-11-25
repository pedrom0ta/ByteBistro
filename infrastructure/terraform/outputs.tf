output "application_url" {
  value = "https://${local.public_domain}"
}

output "ecr_repositories" {
  value = { for name, repository in aws_ecr_repository.main : name => repository.repository_url }
}

output "postgres_address" {
  value = aws_db_instance.postgres.address
}

output "postgres_admin_secret_arn" {
  value = aws_db_instance.postgres.master_user_secret[0].secret_arn
}

output "assets_bucket" {
  value = aws_s3_bucket.assets.id
}

output "audit_bucket" {
  value = aws_s3_bucket.audit.id
}

output "queue_url" {
  value = aws_sqs_queue.jobs.url
}

output "notification_topic_arn" {
  value = aws_sns_topic.notifications.arn
}

output "alarms_topic_arn" {
  value = aws_sns_topic.alarms.arn
}

output "notifications_kms_key_arn" {
  value = aws_kms_key.notifications.arn
}

output "s3_vpc_endpoint_id" {
  value = aws_vpc_endpoint.s3.id
}

output "api_alb_dns" {
  value = aws_lb.api.dns_name
}
