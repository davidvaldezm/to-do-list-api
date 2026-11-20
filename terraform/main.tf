data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "tls_private_key" "ec2" {
  algorithm = "ED25519"
}

resource "aws_key_pair" "api" {
  key_name   = "${var.project_name}-key"
  public_key = tls_private_key.ec2.public_key_openssh
}

resource "aws_security_group" "api" {
  name        = "${var.project_name}-api"
  description = "Demo HTTP API; no SSH ingress"
  vpc_id      = data.aws_vpc.default.id
  ingress {
    description = "To-do API"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [var.api_allowed_cidr]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "database" {
  name        = "${var.project_name}-rds"
  description = "MySQL only from EC2 API security group"
  vpc_id      = data.aws_vpc.default.id
  ingress {
    from_port       = 3306
    to_port         = 3306
    protocol        = "tcp"
    security_groups = [aws_security_group.api.id]
  }
}

resource "aws_db_subnet_group" "database" {
  name       = "${var.project_name}-db-subnets"
  subnet_ids = sort(data.aws_subnets.default.ids)
}

resource "random_password" "database" {
  length  = 32
  special = false
}

resource "aws_db_instance" "database" {
  identifier                 = "${var.project_name}-mysql"
  engine                     = "mysql"
  instance_class             = var.db_instance_class
  allocated_storage          = 20
  storage_type               = "gp2"
  storage_encrypted          = true
  db_name                    = "todolist"
  username                   = "todoadmin"
  password                   = random_password.database.result
  db_subnet_group_name       = aws_db_subnet_group.database.name
  vpc_security_group_ids     = [aws_security_group.database.id]
  publicly_accessible        = false
  multi_az                   = false
  backup_retention_period    = 0
  skip_final_snapshot        = true
  deletion_protection        = false
  auto_minor_version_upgrade = true
}

resource "aws_secretsmanager_secret" "database" {
  name_prefix             = "${var.project_name}-rds-"
  description             = "Runtime MySQL credentials; consumed using LabInstanceProfile"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "database" {
  secret_id = aws_secretsmanager_secret.database.id
  secret_string = jsonencode({
    engine   = "mysql"
    host     = aws_db_instance.database.address
    port     = aws_db_instance.database.port
    dbname   = aws_db_instance.database.db_name
    username = aws_db_instance.database.username
    password = random_password.database.result
  })
}

resource "aws_instance" "api" {
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = var.ec2_instance_type
  subnet_id                   = sort(data.aws_subnets.default.ids)[0]
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.api.id]
  key_name                    = aws_key_pair.api.key_name
  iam_instance_profile        = var.instance_profile_name
  user_data_replace_on_change = true
  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    repository_url    = var.repository_url
    repository_branch = var.repository_branch
    secret_arn        = aws_secretsmanager_secret.database.arn
    region            = var.aws_region
  })
  depends_on = [aws_secretsmanager_secret_version.database]
  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }
  root_block_device {
    volume_size = 8
    volume_type = "gp3"
    encrypted   = true
  }
  tags = { Name = "${var.project_name}-api" }
}

resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.notification_email
}

locals {
  dimensions  = { Application = "to-do-list-api", Environment = "learner-lab" }
  alarm_specs = jsondecode(file("${path.module}/../alerting/alarms.json"))
}

resource "aws_cloudwatch_metric_alarm" "metrics" {
  for_each            = local.alarm_specs
  alarm_name          = "${var.project_name}-${each.key}"
  alarm_description   = each.value.description
  namespace           = each.value.namespace
  metric_name         = each.value.metric_name
  comparison_operator = each.value.comparison_operator
  threshold           = each.value.threshold
  period              = each.value.period
  evaluation_periods  = each.value.evaluation_periods
  datapoints_to_alarm = each.value.datapoints_to_alarm
  statistic           = each.value.statistic
  treat_missing_data  = "notBreaching"
  dimensions          = each.key == "cpu-high" ? { InstanceId = aws_instance.api.id } : local.dimensions
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project_name}-dashboard"
  dashboard_body = templatefile("${path.module}/../alerting/cloudwatch-dashboard.json", {
    region      = var.aws_region
    instance_id = aws_instance.api.id
  })
}
