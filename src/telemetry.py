"""Low-cardinality CloudWatch metrics; telemetry failure never breaks the API."""

import logging
import os

import boto3
from botocore.config import Config

log = logging.getLogger(__name__)
NAMESPACE = "ToDoList/API"
DIMENSIONS = [
    {"Name": "Application", "Value": "to-do-list-api"},
    {"Name": "Environment", "Value": "learner-lab"},
]


class Telemetry:
    def __init__(self):
        self.enabled = os.getenv("CLOUDWATCH_ENABLED", "false").lower() == "true"
        self._client = None

    def emit(self, name: str, value: float):
        if not self.enabled:
            return
        try:
            if self._client is None:
                self._client = boto3.client(
                    "cloudwatch",
                    region_name=os.getenv("AWS_REGION", "us-east-1"),
                    config=Config(connect_timeout=2, read_timeout=2, retries={"max_attempts": 1}),
                )
            self._client.put_metric_data(
                Namespace=NAMESPACE,
                MetricData=[{
                    "MetricName": name,
                    "Dimensions": DIMENSIONS,
                    "Unit": "Count",
                    "Value": value,
                }],
            )
        except Exception:
            log.exception("CloudWatch metric submission failed: %s", name)
