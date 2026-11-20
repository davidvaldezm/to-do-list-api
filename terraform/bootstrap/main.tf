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

resource "aws_cloudformation_stack" "state_bucket" {
  name = "todo-dvm-p4-terraform-backend"
  # Learner Lab denies GetBucketObjectLockConfiguration, called unconditionally
  # by aws_s3_bucket. CloudFormation's supported S3 handler avoids that lookup.
  template_body = jsonencode({
    AWSTemplateFormatVersion = "2010-09-09"
    Resources = {
      StateBucket = {
        Type                = "AWS::S3::Bucket"
        DeletionPolicy      = "Retain"
        UpdateReplacePolicy = "Retain"
        Properties = {
          BucketName              = var.state_bucket
          VersioningConfiguration = { Status = "Enabled" }
          BucketEncryption = {
            ServerSideEncryptionConfiguration = [{ ServerSideEncryptionByDefault = { SSEAlgorithm = "AES256" } }]
          }
          PublicAccessBlockConfiguration = {
            BlockPublicAcls       = true
            BlockPublicPolicy     = true
            IgnorePublicAcls      = true
            RestrictPublicBuckets = true
          }
          Tags = [
            { Key = "Project", Value = "todo-dvm-p4" },
            { Key = "ManagedBy", Value = "Terraform" }
          ]
        }
      }
    }
  })
  lifecycle {
    prevent_destroy = true
  }
}

output "bucket" {
  value = var.state_bucket
}
