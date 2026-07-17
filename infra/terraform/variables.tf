variable "project_name" {
  description = "Lowercase project name used in resource names."
  type        = string
  default     = "expenseguard"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,20}$", var.project_name))
    error_message = "project_name must be 3-21 lowercase letters, digits, or hyphens."
  }
}

variable "environment" {
  description = "Deployment environment. This module is intentionally optimized for a short-lived lab."
  type        = string
  default     = "lab"
  validation {
    condition     = contains(["lab", "production"], var.environment)
    error_message = "environment must be lab or production."
  }
}

variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.40.0.0/16"
}

variable "hosted_zone_id" {
  description = "Existing public Route53 hosted zone ID. Domain registration is out of scope."
  type        = string
}

variable "domain_name" {
  description = "Fully qualified application domain covered by the existing hosted zone."
  type        = string
}

variable "image_uri" {
  description = "Immutable ECR image URI including sha256 digest, never a mutable tag."
  type        = string
  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.image_uri))
    error_message = "image_uri must end in an OCI sha256 digest."
  }
}

variable "desired_count" {
  type    = number
  default = 1
  validation {
    condition     = var.desired_count >= 1 && var.desired_count <= 10
    error_message = "desired_count must be between 1 and 10."
  }
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "log_retention_days" {
  type    = number
  default = 30
}

