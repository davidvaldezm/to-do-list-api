"""Deploy a verified, published GitHub release; the EC2 instance downloads its ZIP."""
import json
import os
import re
import shlex
import time
import urllib.request
from pathlib import Path

import boto3

from health_check import discover_instance


def github(path):
    request = urllib.request.Request(
        "https://api.github.com" + path,
        headers={"Authorization": f'Bearer {os.environ["GH_TOKEN"]}',
                 "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main():
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    repository = os.environ["GITHUB_REPOSITORY"]
    event_name = os.environ["GITHUB_EVENT_NAME"]
    if event_name == "release":
        tag = event["release"]["tag_name"]
    elif event_name == "workflow_dispatch":
        tag = event["inputs"]["tag"]
    else:
        sha = event["workflow_run"]["head_sha"]
        releases = github(f"/repos/{repository}/releases?per_page=100")
        candidates = []
        for release in releases:
            if release["draft"] or release["prerelease"]:
                continue
            commit = github(f'/repos/{repository}/commits/{release["tag_name"]}')
            if commit["sha"] == sha:
                candidates.append(release["tag_name"])
        if len(candidates) != 1:
            raise RuntimeError(f"Expected one published release for {sha}; found {candidates}")
        tag = candidates[0]
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise ValueError("Invalid release version")
    release = github(f"/repos/{repository}/releases/tags/{tag}")
    if release["draft"] or release["prerelease"]:
        raise ValueError("Only stable published releases can deploy")
    assets = {asset["name"]: asset for asset in release["assets"]}
    filename = f"to-do-list-api-{tag}.zip"
    zip_url = assets[filename]["browser_download_url"]
    with urllib.request.urlopen(assets["SHA256SUMS"]["browser_download_url"], timeout=30) as response:
        checksum, checksum_filename = response.read().decode().split()
    if checksum_filename != filename or not re.fullmatch(r"[0-9a-f]{64}", checksum):
        raise ValueError("Invalid release checksum manifest")
    if assets[filename].get("digest") and assets[filename]["digest"] != "sha256:" + checksum:
        raise ValueError("Release asset digest mismatch")
    print(f"Deploying published {tag} with SHA256 {checksum}")
    shell = Path("scripts/deploy.sh").read_text()
    prefix = f"export DEPLOY_VERSION={shlex.quote(tag[1:])} DOWNLOAD_URL={shlex.quote(zip_url)} EXPECTED_SHA={shlex.quote(checksum)}\n"
    instance = discover_instance()
    ssm = boto3.client("ssm", region_name="us-east-1")
    result = ssm.send_command(
        InstanceIds=[instance["InstanceId"]], DocumentName="AWS-RunShellScript",
        Comment=f"To-do-list release {tag}",
        Parameters={"commands": [prefix + shell], "executionTimeout": ["900"]},
        TimeoutSeconds=900,
    )
    command_id = result["Command"]["CommandId"]
    deadline = time.monotonic() + 950
    while time.monotonic() < deadline:
        time.sleep(6)
        try:
            invocation = ssm.get_command_invocation(CommandId=command_id, InstanceId=instance["InstanceId"])
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        if invocation["Status"] in {"Pending", "InProgress", "Delayed"}:
            continue
        print(invocation.get("StandardOutputContent", ""))
        if invocation["Status"] != "Success":
            print(invocation.get("StandardErrorContent", ""))
            raise RuntimeError(f'SSM deployment failed: {invocation["Status"]}')
        print(f"SSM {command_id}: Success")
        return
    raise TimeoutError("SSM deployment timed out")


if __name__ == "__main__":
    main()
