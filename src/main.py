import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from src.database import DatabaseUnavailable, TaskRepository
from src.telemetry import Telemetry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)


def get_version():
    return os.getenv("APP_VERSION") or Path(__file__).resolve().parents[1].joinpath("VERSION").read_text().strip()


class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    done: bool = False

    @field_validator("title")
    @classmethod
    def meaningful_title(cls, value):
        if not value.strip():
            raise ValueError("title must contain non-whitespace characters")
        return value.strip()


class TaskUpdate(BaseModel):
    done: bool


class Task(TaskInput):
    id: int


def create_app(repository=None, start_monitor=True):
    repo = repository if repository is not None else TaskRepository(Telemetry())

    async def heartbeat():
        while True:
            await asyncio.sleep(60)
            try:
                await asyncio.to_thread(repo.health)
            except Exception:
                log.exception("Database heartbeat failed")

    @asynccontextmanager
    async def lifespan(app):
        await asyncio.to_thread(repo.initialize)
        task = asyncio.create_task(heartbeat()) if start_monitor else None
        yield
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="To-Do List API", version=get_version(), lifespan=lifespan)

    @app.exception_handler(DatabaseUnavailable)
    async def database_error(request, exc):
        return JSONResponse(status_code=503, content={"detail": "Database unavailable"})

    @app.get("/tasks", response_model=list[Task])
    def tasks():
        return repo.list_tasks()

    @app.post("/tasks", response_model=Task, status_code=201)
    def create_task(task: TaskInput):
        return repo.create_task(task.title, task.done)

    @app.patch("/tasks/{task_id}", response_model=Task)
    def update_task(task_id: int, update: TaskUpdate):
        result = repo.update_task(task_id, update.done)
        if result is None:
            raise HTTPException(404, "Task not found")
        return result

    @app.get("/version")
    def version():
        return {"version": get_version()}

    @app.get("/health")
    def health():
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            pending = repo.health()
            return {"status": "ok", "database": "connected", "version": get_version(),
                    "timestamp": timestamp, "pending_tasks": pending}
        except Exception:
            log.exception("Health check failed")
            return JSONResponse(status_code=503, content={
                "status": "unhealthy", "database": "unavailable", "version": get_version(),
                "timestamp": timestamp,
            })

    return app


app = create_app()
