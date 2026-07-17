data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "cloudtrail" {
  #checkov:skip=CKV2_AWS_62:EXC-IAC-013 notifications require an operated response destination, not an unconsumed lab topic
  #checkov:skip=CKV_AWS_144:EXC-IAC-006 cross-region replication is a production resilience control
  #checkov:skip=CKV_AWS_18:EXC-IAC-007 CloudTrail log delivery is the bucket's sole purpose and access path
  #checkov:skip=CKV_AWS_145:EXC-IAC-008 SSE-S3 is approved for synthetic lab evidence; customer-managed KMS requires cost approval
  bucket_prefix = "${local.name}-cloudtrail-"
  force_destroy = var.environment == "lab"
}

resource "aws_s3_bucket_public_access_block" "cloudtrail" {
  bucket                  = aws_s3_bucket.cloudtrail.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id
  rule {
    id     = "expire-lab-trail-evidence"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
    expiration {
      days = var.environment == "lab" ? 30 : 365
    }
    noncurrent_version_expiration {
      noncurrent_days = var.environment == "lab" ? 30 : 365
    }
  }
}

data "aws_iam_policy_document" "cloudtrail" {
  statement {
    sid       = "CloudTrailAclCheck"
    effect    = "Allow"
    actions   = ["s3:GetBucketAcl"]
    resources = [aws_s3_bucket.cloudtrail.arn]
    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceArn"
      values   = ["arn:aws:cloudtrail:${var.aws_region}:${data.aws_caller_identity.current.account_id}:trail/${local.name}"]
    }
  }
  statement {
    sid       = "CloudTrailWrite"
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.cloudtrail.arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/*"]
    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-acl"
      values   = ["bucket-owner-full-control"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceArn"
      values   = ["arn:aws:cloudtrail:${var.aws_region}:${data.aws_caller_identity.current.account_id}:trail/${local.name}"]
    }
  }
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.cloudtrail.arn, "${aws_s3_bucket.cloudtrail.arn}/*"]
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

resource "aws_s3_bucket_policy" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id
  policy = data.aws_iam_policy_document.cloudtrail.json
}

resource "aws_cloudtrail" "main" {
  #checkov:skip=CKV_AWS_35:EXC-IAC-014 SSE-S3 is approved for the synthetic lab; CMK is production-required
  #checkov:skip=CKV_AWS_252:EXC-IAC-015 no SNS destination is operated during a short lab deployment
  #checkov:skip=CKV2_AWS_10:EXC-IAC-016 validated S3 delivery is authoritative lab evidence; CloudWatch integration is production-required
  name                          = local.name
  s3_bucket_name                = aws_s3_bucket.cloudtrail.id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true
  depends_on                    = [aws_s3_bucket_policy.cloudtrail]

  event_selector {
    read_write_type           = "All"
    include_management_events = true
    data_resource {
      type   = "AWS::S3::Object"
      values = ["${aws_s3_bucket.receipts.arn}/"]
    }
  }
}

resource "aws_cloudwatch_log_metric_filter" "login_failure" {
  name           = "${local.name}-login-failure"
  pattern        = "{ $.action = \"auth.login\" && $.outcome = \"failure\" }"
  log_group_name = aws_cloudwatch_log_group.app.name
  metric_transformation {
    name      = "AuthenticationFailures"
    namespace = "ExpenseGuard/Security"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "login_failure" {
  alarm_name          = "${local.name}-authentication-failures"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "AuthenticationFailures"
  namespace           = "ExpenseGuard/Security"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  treat_missing_data  = "notBreaching"
}
