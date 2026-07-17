output "application_url" {
  value = "https://${var.domain_name}"
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  value = aws_ecs_service.app.name
}

output "receipt_bucket" {
  value = aws_s3_bucket.receipts.id
}

output "rds_secret_arn" {
  value     = aws_db_instance.main.master_user_secret[0].secret_arn
  sensitive = true
}

