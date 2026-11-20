from datetime import datetime
from unittest.mock import Mock, patch

import pymysql
import pytest
from fastapi.testclient import TestClient

from src.database import DatabaseUnavailable, TaskRepository
from src.main import create_app
from src.telemetry import Telemetry


@pytest.fixture
def repo():
    result = Mock()
    result.list_tasks.return_value = [{"id": 1, "title": "Estudiar", "done": False}]
    result.create_task.return_value = {"id": 2, "title": "Estudiar AWS", "done": False}
    result.health.return_value = 1
    return result


@pytest.fixture
def client(repo):
    with TestClient(create_app(repo, start_monitor=False)) as result:
        yield result


def test_list_tasks(client, repo):
    response = client.get("/tasks")
    assert response.status_code == 200
    assert response.json() == [{"id": 1, "title": "Estudiar", "done": False}]
    repo.list_tasks.assert_called_once()


def test_create_task(client, repo):
    response = client.post("/tasks", json={"title": "  Estudiar AWS  ", "done": False})
    assert response.status_code == 201
    assert response.json()["id"] == 2
    repo.create_task.assert_called_once_with("Estudiar AWS", False)


@pytest.mark.parametrize("title", ["", "   ", "x" * 201])
def test_invalid_title_does_not_write(client, repo, title):
    assert client.post("/tasks", json={"title": title}).status_code == 422
    repo.create_task.assert_not_called()


def test_version(client):
    assert client.get("/version").json()["version"]


def test_health_checks_database_and_returns_timestamp(client, repo):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["database"] == "connected"
    assert data["version"]
    assert datetime.fromisoformat(data["timestamp"]).tzinfo is not None
    repo.health.assert_called_once()


def test_health_failure_is_503_and_keeps_version(client, repo):
    repo.health.side_effect = DatabaseUnavailable("private connection info")
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"
    assert response.json()["version"]
    assert "private" not in response.text


def test_rds_failure_returns_503_without_secrets(client, repo):
    repo.list_tasks.side_effect = DatabaseUnavailable("password=secret")
    response = client.get("/tasks")
    assert response.status_code == 503
    assert "secret" not in response.text


def test_complete_task(client, repo):
    repo.update_task.return_value = {"id": 1, "title": "Estudiar", "done": True}
    response = client.patch("/tasks/1", json={"done": True})
    assert response.json()["done"] is True
    repo.update_task.assert_called_once_with(1, True)


def test_complete_missing_task(client, repo):
    repo.update_task.return_value = None
    assert client.patch("/tasks/999", json={"done": True}).status_code == 404


def test_rds_error_emits_metric():
    telemetry = Mock()
    repository = TaskRepository(telemetry)
    repository.credentials = Mock(return_value={"host": "db", "username": "u", "password": "p", "dbname": "tasks"})
    with patch("src.database.pymysql.connect", side_effect=pymysql.OperationalError(2003, "connection refused")):
        with pytest.raises(DatabaseUnavailable):
            repository.list_tasks()
    telemetry.emit.assert_called_once_with("RdsErrors", 1)


def test_metric_uses_boto3_and_fixed_dimensions(monkeypatch):
    monkeypatch.setenv("CLOUDWATCH_ENABLED", "true")
    telemetry = Telemetry()
    telemetry._client = Mock()
    telemetry.emit("PendingTasks", 7)
    payload = telemetry._client.put_metric_data.call_args.kwargs
    assert payload["Namespace"] == "ToDoList/API"
    assert payload["MetricData"][0]["Value"] == 7
    assert payload["MetricData"][0]["Unit"] == "Count"


def test_telemetry_outage_does_not_break_api(monkeypatch):
    monkeypatch.setenv("CLOUDWATCH_ENABLED", "true")
    telemetry = Telemetry()
    telemetry._client = Mock()
    telemetry._client.put_metric_data.side_effect = RuntimeError("CloudWatch down")
    telemetry.emit("PendingTasks", 1)


def test_secrets_read_at_runtime_and_cached(monkeypatch):
    monkeypatch.setenv("DB_SECRET_ARN", "arn:aws:secretsmanager:us-east-1:123:secret:db")
    repository = TaskRepository(Mock())
    repository._secrets_client = Mock()
    repository._secrets_client.get_secret_value.return_value = {"SecretString": '{"username":"runtime"}'}
    assert repository.credentials()["username"] == "runtime"
    repository.credentials()
    repository._secrets_client.get_secret_value.assert_called_once_with(
        SecretId="arn:aws:secretsmanager:us-east-1:123:secret:db"
    )
