"""Background Task Manager.
======================

Background task processing with SQLite persistence.
Provides task queue, retry logic, and result storage.

Features:
- SQLite database for task persistence
- Background asyncio workers
- Task retry with exponential backoff
- Progress tracking via WebSocket
- Automatic task cleanup

Environment Variables:
- WORKER_CONCURRENCY: Number of concurrent workers (default: 4)
- WORKER_MAX_RETRIES: Maximum retry attempts (default: 3)

Usage:
    from backend.worker import enqueue_task, get_task_result

    # Enqueue a task
    task_id = await enqueue_task("process_file", kwargs={"filepath": "/path/to/file"})

    # Get result
    result = await get_task_result(task_id)
"""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Configuration
WORKER_CONCURRENCY = 4
WORKER_MAX_RETRIES = 3
TASK_RESULT_TTL = 86400  # 24 hours


class TaskStatus(str, Enum):
    """Task status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Background task data."""

    id: str
    name: str
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    result: Any = None
    error: str | None = None
    retry_count: int = 0
    progress: int = 0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
            "progress": self.progress,
            "metadata": self.metadata
        }


class TaskDatabase:
    """SQLite-backed task storage."""

    def __init__(self) -> None:
        self._db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "db", "tasks.db"
        )
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                args TEXT NOT NULL DEFAULT '[]',
                kwargs TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at REAL NOT NULL,
                started_at REAL,
                completed_at REAL,
                result TEXT,
                error TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                progress INTEGER NOT NULL DEFAULT 0,
                metadata TEXT NOT NULL DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at)
        """)
        conn.commit()
        conn.close()

    def create_task(self, task: Task) -> None:
        """Create a new task."""
        import json
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            """INSERT INTO tasks (id, name, args, kwargs, status, created_at, progress, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task.id,
                task.name,
                json.dumps(task.args),
                json.dumps(task.kwargs),
                task.status.value,
                task.created_at,
                task.progress,
                json.dumps(task.metadata)
            )
        )
        conn.commit()
        conn.close()

    def get_task(self, task_id: str) -> Task | None:
        """Get task by ID."""
        import json
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return Task(
            id=row["id"],
            name=row["name"],
            args=json.loads(row["args"]),
            kwargs=json.loads(row["kwargs"]),
            status=TaskStatus(row["status"]),
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            result=json.loads(row["result"]) if row["result"] else None,
            error=row["error"],
            retry_count=row["retry_count"],
            progress=row["progress"],
            metadata=json.loads(row["metadata"])
        )

    def update_task(self, task: Task) -> None:
        """Update task."""
        import json
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            """UPDATE tasks SET
               status = ?, started_at = ?, completed_at = ?,
               result = ?, error = ?, retry_count = ?, progress = ?
               WHERE id = ?""",
            (
                task.status.value,
                task.started_at,
                task.completed_at,
                json.dumps(task.result) if task.result is not None else None,
                task.error,
                task.retry_count,
                task.progress,
                task.id
            )
        )
        conn.commit()
        conn.close()

    def get_pending_tasks(self, limit: int = 10) -> list[Task]:
        """Get pending tasks."""
        import json
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM tasks WHERE status = 'pending'
               ORDER BY created_at ASC LIMIT ?""",
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()

        tasks = []
        for row in rows:
            tasks.append(Task(
                id=row["id"],
                name=row["name"],
                args=json.loads(row["args"]),
                kwargs=json.loads(row["kwargs"]),
                status=TaskStatus(row["status"]),
                created_at=row["created_at"],
                started_at=row["started_at"],
                completed_at=row["completed_at"],
                result=json.loads(row["result"]) if row["result"] else None,
                error=row["error"],
                retry_count=row["retry_count"],
                progress=row["progress"],
                metadata=json.loads(row["metadata"])
            ))

        return tasks

    def cleanup_old_tasks(self, ttl: int = TASK_RESULT_TTL) -> int:
        """Remove old completed tasks."""
        cutoff = time.time() - ttl
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute(
            """DELETE FROM tasks WHERE
               status IN ('completed', 'failed', 'cancelled') AND
               completed_at < ?""",
            (cutoff,)
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected


# Global database instance
task_db = TaskDatabase()


class TaskQueue:
    """SQLite-backed task queue with asyncio workers.

    Features:
    - SQLite persistence
    - Background workers
    - Retry with exponential backoff
    - Progress tracking
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._started = False

    async def start(self) -> None:
        """Start worker pool."""
        if self._started:
            return

        self._running = True
        self._started = True

        # Start worker coroutines
        for i in range(WORKER_CONCURRENCY):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)

        logger.info(f"Task queue started with {WORKER_CONCURRENCY} workers")

    async def stop(self) -> None:
        """Stop all workers."""
        self._running = False

        # Wait for queue to drain
        await asyncio.sleep(0.5)

        # Cancel workers
        for worker in self._workers:
            worker.cancel()

        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

        logger.info("Task queue stopped")

    async def enqueue(self, task_id: str, task_name: str, args: tuple = (),
                      kwargs: dict | None = None, metadata: dict | None = None) -> str:
        """Add task to queue."""
        task = Task(
            id=task_id,
            name=task_name,
            args=args,
            kwargs=kwargs or {},
            metadata=metadata or {}
        )

        # Save to database
        task_db.create_task(task)

        # Add to queue
        await self._queue.put(task_id)

        logger.debug(f"Task enqueued: {task_id} ({task_name})")
        return task_id

    async def get_result(self, task_id: str) -> dict | None:
        """Get task result."""
        task = task_db.get_task(task_id)
        if not task:
            return None
        return task.to_dict()

    async def _worker(self, worker_id: int) -> None:
        """Worker coroutine."""
        logger.debug(f"Worker {worker_id} started")

        while self._running:
            try:
                # Get task from queue
                try:
                    task_id = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    # Check for new tasks in database
                    pending = task_db.get_pending_tasks(limit=1)
                    if pending:
                        await self._queue.put(pending[0].id)
                    continue

                task = task_db.get_task(task_id)
                if not task:
                    continue

                # Mark as processing
                task.status = TaskStatus.PROCESSING
                task.started_at = time.time()
                task_db.update_task(task)
                await self._update_progress(task)

                try:
                    # Get handler function
                    handler = _task_handlers.get(task.name)
                    if not handler:
                        raise ValueError(f"Unknown task: {task.name}")

                    # Execute task
                    result = await handler(**task.kwargs)

                    # Mark as completed
                    task.status = TaskStatus.COMPLETED
                    task.result = result
                    task.completed_at = time.time()
                    task.progress = 100
                    task_db.update_task(task)

                    logger.info(f"Task {task_id} completed successfully")

                except asyncio.CancelledError:
                    # Task was cancelled
                    task.status = TaskStatus.CANCELLED
                    task.completed_at = time.time()
                    task_db.update_task(task)
                    raise

                except Exception as e:
                    # Handle failure
                    task.error = str(e)
                    task.retry_count += 1

                    if task.retry_count < WORKER_MAX_RETRIES:
                        # Retry with backoff
                        delay = 2 ** task.retry_count
                        logger.warning(f"Task {task_id} failed, retrying in {delay}s (attempt {task.retry_count})")
                        task.status = TaskStatus.PENDING
                        task_db.update_task(task)
                        asyncio.create_task(self._retry_later(task_id, delay))
                    else:
                        task.status = TaskStatus.FAILED
                        task.completed_at = time.time()
                        task_db.update_task(task)
                        logger.error(f"Task {task_id} failed after {task.retry_count} attempts: {e}")

                # Update progress
                await self._update_progress(task)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")

        logger.debug(f"Worker {worker_id} stopped")

    async def _retry_later(self, task_id: str, delay: float) -> None:
        """Retry task after delay."""
        await asyncio.sleep(delay)
        task = task_db.get_task(task_id)
        if task and task.status == TaskStatus.PENDING:
            await self._queue.put(task_id)

    async def _update_progress(self, task: Task) -> None:
        """Send progress update via WebSocket."""
        try:
            from backend.websocket import ws_manager
            await ws_manager.send_progress(
                task.id,
                task.progress,
                task.status.value,
                {"result": task.result, "error": task.error}
            )
        except ImportError:
            pass  # WebSocket not initialized yet


# Task handlers registry
_task_handlers: dict[str, Callable] = {}


def register_task(name: str) -> Callable:
    """Decorator to register a task handler."""
    def decorator(func: Callable) -> Callable:
        _task_handlers[name] = func
        return func
    return decorator


# Global task queue instance
task_queue = TaskQueue()


# ═══════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

async def enqueue_task(task_name: str, kwargs: dict | None = None,
                       metadata: dict | None = None) -> str:
    """Enqueue a background task."""
    task_id = f"task_{uuid.uuid4().hex[:12]}"
    return await task_queue.enqueue(
        task_id,
        task_name,
        kwargs=kwargs or {},
        metadata=metadata or {}
    )


async def get_task_result(task_id: str) -> dict | None:
    """Get task result."""
    return await task_queue.get_result(task_id)


async def start_worker() -> None:
    """Start the background worker pool."""
    await task_queue.start()


async def stop_worker() -> None:
    """Stop the background worker pool."""
    await task_queue.stop()


# ═══════════════════════════════════════════════════════════════════════════
# TASK HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

@register_task("process_file")
async def process_file(filepath: str, options: dict | None = None) -> dict:
    """Process a file in background."""
    logger.info(f"Processing file: {filepath}")

    # Simulate processing
    for _i in range(10):
        await asyncio.sleep(0.5)

    return {"status": "completed", "filepath": filepath, "processed": True}


@register_task("export_rooms")
async def export_rooms(project_id: str, floors: int = 100) -> dict:
    """Export rooms for a project in background."""
    logger.info(f"Exporting {floors} floors for project {project_id}")

    # Simulate export
    rooms = []
    for floor in range(floors):
        for room in range(10):
            rooms.append({
                "id": f"room-{floor}-{room}",
                "floor": floor,
                "room": room,
                "area": 25.0
            })

    return {
        "status": "completed",
        "project_id": project_id,
        "total_rooms": len(rooms),
        "floors": floors
    }


@register_task("convert_dwg")
async def convert_dwg(input_path: str, output_format: str = "dxf") -> dict:
    """Convert DWG file in background."""
    logger.info(f"Converting {input_path} to {output_format}")

    # Simulate conversion
    await asyncio.sleep(2)

    return {
        "status": "completed",
        "input": input_path,
        "output": input_path.replace(".dwg", f".{output_format}"),
        "format": output_format
    }
