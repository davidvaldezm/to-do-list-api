"""Regression tests submitted through a PR to exercise required CI checks."""
from unittest.mock import Mock

from fastapi.testclient import TestClient

from src.database import DatabaseUnavailable
from src.main import create_app


def test_missing_title_is_rejected_before_database_write():
    repository = Mock()
    with TestClient(create_app(repository, start_monitor=False)) as client:
        response = client.post("/tasks", json={"done": False})
    assert response.status_code == 422
    repository.create_task.assert_not_called()


def test_completing_task_returns_503_when_database_is_down():
    repository = Mock()
    repository.update_task.side_effect = DatabaseUnavailable("database offline")
    with TestClient(create_app(repository, start_monitor=False)) as client:
        response = client.patch("/tasks/1", json={"done": True})
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
