variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "todo-dvm-p4"
}

variable "repository_url" {
  type    = string
  default = "https://github.com/davidvaldezm/to-do-list-api.git"
}

variable "repository_branch" {
  type    = string
  default = "main"
}

variable "notification_email" {
  type        = string
  description = "Email subscribed to all CloudWatch alarms; SNS confirmation is required."
}

variable "instance_profile_name" {
  type    = string
  default = "LabInstanceProfile"
}

variable "ec2_instance_type" {
  type    = string
  default = "t3.micro"
}

variable "db_instance_class" {
  type    = string
  default = "db.t3.micro"
}

variable "api_allowed_cidr" {
  type        = string
  default     = "0.0.0.0/0"
  description = "Public demo API on port 8000. RDS accepts only the API security group; SSH stays closed."
}
