"""Discover the current IP (Learner Lab may change it) and validate /health."""
import json
import os
import urllib.request
from datetime import datetime, timezone

import boto3


def discover_instance():
    ec2 = boto3.client("ec2", region_name=os.getenv("AWS_REGION", "us-east-1"))
    result = ec2.describe_instances(Filters=[
        {"Name": "tag:Project", "Values": ["todo-dvm-p4"]},
        {"Name": "instance-state-name", "Values": ["running"]},
    ])
    instances = [i for r in result["Reservations"] for i in r["Instances"]]
    if len(instances) != 1:
        raise RuntimeError(f"Expected one running project instance, found {len(instances)}")
    return instances[0]


def check_health():
    instance = discover_instance()
    base = f'http://{instance["PublicIpAddress"]}:8000'
    with urllib.request.urlopen(base + "/health", timeout=20) as response:
        health = json.load(response)
    with urllib.request.urlopen(base + "/version", timeout=10) as response:
        version = json.load(response)["version"]
    assert health["status"] == "ok" and health["database"] == "connected", health
    assert health["version"] == version, health
    timestamp = datetime.fromisoformat(health["timestamp"])
    assert timestamp.tzinfo is not None
    assert abs((datetime.now(timezone.utc) - timestamp).total_seconds()) < 120
    print(json.dumps({"url": base, **health}, indent=2))


if __name__ == "__main__":
    check_health()
