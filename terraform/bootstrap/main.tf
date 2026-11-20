terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.100"
    }
  }
  # First: terraform init && terraform apply -var state_bucket=...
  # Then add backend.generated.tf (see README), and terraform init -migrate-state.
}

provider "aws" {
  region = "us-east-1"
}

variable "state_bucket" {
  type = string
}

resource "aws_s3_bucket" "state" {
  bucket = var.state_bucket
  tags   = { Project = "todo-dvm-p4", ManagedBy = "Terraform", Purpose = "Remote terraform state" }
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

output "bucket" {
  value = aws_s3_bucket.state.id
}
