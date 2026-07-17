resource "aws_s3_bucket" "receipts" {
  #checkov:skip=CKV2_AWS_62:EXC-IAC-005 CloudTrail S3 data events provide the lab notification trail
  #checkov:skip=CKV_AWS_144:EXC-IAC-006 cross-region replication is a production resilience control
  #checkov:skip=CKV_AWS_18:EXC-IAC-007 object data events are enabled in CloudTrail instead of duplicate server access logs
  #checkov:skip=CKV_AWS_145:EXC-IAC-008 SSE-S3 is approved for synthetic lab data; customer-managed KMS requires cost approval
  bucket_prefix = "${local.name}-receipts-"
  force_destroy = var.environment == "lab"
}

resource "aws_s3_bucket_public_access_block" "receipts" {
  bucket                  = aws_s3_bucket.receipts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "receipts" {
  bucket = aws_s3_bucket.receipts.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "receipts" {
  bucket = aws_s3_bucket.receipts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "receipts" {
  bucket = aws_s3_bucket.receipts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "receipts" {
  bucket = aws_s3_bucket.receipts.id
  rule {
    id     = "abort-incomplete-uploads"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

data "aws_iam_policy_document" "receipts" {
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.receipts.arn, "${aws_s3_bucket.receipts.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "receipts" {
  bucket = aws_s3_bucket.receipts.id
  policy = data.aws_iam_policy_document.receipts.json
}

resource "aws_db_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.database[*].id
}

resource "aws_db_instance" "main" {
  #checkov:skip=CKV_AWS_354:EXC-IAC-009 Performance Insights CMK is production-required and has a separate cost
  #checkov:skip=CKV_AWS_118:EXC-IAC-010 enhanced RDS monitoring is production-required and omitted from the short lab
  #checkov:skip=CKV2_AWS_30:EXC-IAC-011 log_statement=all can expose sensitive values; slow/error logging is reviewed separately
  identifier                          = local.name
  engine                              = "postgres"
  engine_version                      = "17"
  instance_class                      = var.db_instance_class
  allocated_storage                   = 20
  max_allocated_storage               = 100
  storage_type                        = "gp3"
  storage_encrypted                   = true
  db_name                             = "expenseguard"
  username                            = "expenseguard"
  manage_master_user_password         = true
  iam_database_authentication_enabled = true
  db_subnet_group_name                = aws_db_subnet_group.main.name
  vpc_security_group_ids              = [aws_security_group.database.id]
  publicly_accessible                 = false
  multi_az                            = var.environment == "production"
  backup_retention_period             = 7
  copy_tags_to_snapshot               = true
  auto_minor_version_upgrade          = true
  deletion_protection                 = var.environment == "production"
  skip_final_snapshot                 = var.environment == "lab"
  final_snapshot_identifier           = var.environment == "production" ? "${local.name}-final" : null
  performance_insights_enabled        = true
  enabled_cloudwatch_logs_exports     = ["postgresql", "upgrade"]
}

resource "aws_ecr_repository" "app" {
  #checkov:skip=CKV_AWS_136:EXC-IAC-012 AES256 protects synthetic lab images; customer-managed KMS requires cost approval
  name                 = local.name
  image_tag_mutability = "IMMUTABLE"
  force_delete         = var.environment == "lab"
  encryption_configuration {
    encryption_type = "AES256"
  }
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Retain the most recent 20 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 20
      }
      action = { type = "expire" }
    }]
  })
}
