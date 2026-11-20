"""MySQL repository. Secrets are fetched at runtime using the EC2 role."""

import json
import logging
import os
import time
from contextlib import contextmanager

import boto3
import pymysql
from botocore.config import Config

log = logging.getLogger(__name__)


class DatabaseUnavailable(Exception):
    pass


class TaskRepository:
    def __init__(self, telemetry):
        self.telemetry = telemetry
        self._secret = None
        self._secret_time = 0
        self._secrets_client = None

    def credentials(self):
        if self._secret is None or time.monotonic() - self._secret_time > 300:
            if self._secrets_client is None:
                self._secrets_client = boto3.client(
                    "secretsmanager",
                    region_name=os.getenv("AWS_REGION", "us-east-1"),
                    config=Config(connect_timeout=3, read_timeout=3, retries={"max_attempts": 1}),
                )
            result = self._secrets_client.get_secret_value(SecretId=os.environ["DB_SECRET_ARN"])
            self._secret = json.loads(result["SecretString"])
            self._secret_time = time.monotonic()
        return self._secret

    @contextmanager
    def connection(self):
        conn = None
        try:
            secret = self.credentials()
            ssl = {"ca": os.environ["RDS_CA_BUNDLE"], "check_hostname": True} if os.getenv("RDS_CA_BUNDLE") else None
            conn = pymysql.connect(
                host=secret["host"], port=int(secret.get("port", 3306)),
                user=secret["username"], password=secret["password"],
                database=secret["dbname"], connect_timeout=3, read_timeout=5,
                write_timeout=5, autocommit=True,
                cursorclass=pymysql.cursors.DictCursor, ssl=ssl,
            )
            yield conn
            self.telemetry.emit("RdsErrors", 0)
        except (pymysql.MySQLError, OSError) as exc:
            self._secret_time = 0
            self.telemetry.emit("RdsErrors", 1)
            log.exception("RDS read/write failed")
            raise DatabaseUnavailable("Database unavailable") from exc
        finally:
            if conn:
                conn.close()

    def initialize(self):
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS tasks (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                title VARCHAR(200) NOT NULL,
                done BOOLEAN NOT NULL DEFAULT FALSE
            )""")

    def pending(self, cur):
        cur.execute("SELECT COUNT(*) AS count FROM tasks WHERE done = FALSE")
        count = cur.fetchone()["count"]
        self.telemetry.emit("PendingTasks", count)
        return count

    def list_tasks(self):
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, title, done FROM tasks ORDER BY id")
            tasks = cur.fetchall()
            self.pending(cur)
            return [{**task, "done": bool(task["done"])} for task in tasks]

    def create_task(self, title, done):
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO tasks (title, done) VALUES (%s, %s)", (title, done))
            task = {"id": cur.lastrowid, "title": title, "done": done}
            self.pending(cur)
            return task

    def update_task(self, task_id, done):
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, title, done FROM tasks WHERE id = %s", (task_id,))
            task = cur.fetchone()
            if task is None:
                return None
            cur.execute("UPDATE tasks SET done = %s WHERE id = %s", (done, task_id))
            self.pending(cur)
            return {**task, "done": done}

    def health(self):
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 AS connected")
            cur.fetchone()
            return self.pending(cur)
