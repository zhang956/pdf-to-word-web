from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
import shutil
from threading import Lock
import time
from uuid import uuid4


@dataclass
class TaskStatus:
    id: str
    original_name: str
    input_path: Path
    output_path: Path
    state: str = "pending"
    current_page: int = 0
    total_pages: int = 0
    error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            self.updated_at = self.created_at

    @property
    def progress(self) -> int:
        if self.state == "completed":
            return 100
        if self.total_pages <= 0:
            return 0
        return min(99, round(self.current_page * 100 / self.total_pages))


class TaskStore:
    def __init__(self, root: Path, ttl: int):
        self.root = Path(root)
        self.ttl = ttl
        self.root.mkdir(parents=True, exist_ok=True)
        self._tasks: dict[str, TaskStatus] = {}
        self._lock = Lock()
        self._cleanup_orphan_directories()

    def _cleanup_orphan_directories(self) -> None:
        cutoff = time.time() - self.ttl
        for entry in self.root.iterdir():
            if entry.is_symlink() or not entry.is_dir():
                continue
            try:
                if entry.stat().st_mtime < cutoff:
                    shutil.rmtree(entry)
            except FileNotFoundError:
                continue

    def create(self, original_name: str) -> TaskStatus:
        task_id = uuid4().hex
        task_dir = self.root / task_id
        task_dir.mkdir(parents=True, exist_ok=False)
        task = TaskStatus(
            id=task_id,
            original_name=original_name,
            input_path=task_dir / "input.pdf",
            output_path=task_dir / "output.docx",
        )
        with self._lock:
            self._tasks[task_id] = task
        return replace(task)

    def get(self, task_id: str) -> TaskStatus | None:
        with self._lock:
            task = self._tasks.get(task_id)
            return replace(task) if task is not None else None

    def update(self, task_id: str, **changes) -> TaskStatus:
        with self._lock:
            task = self._tasks[task_id]
            for name, value in changes.items():
                if not hasattr(task, name):
                    raise AttributeError(name)
                setattr(task, name, value)
            if "updated_at" not in changes:
                task.updated_at = datetime.now(timezone.utc)
            return replace(task)

    def delete(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.pop(task_id, None)
        if task is None:
            return False
        shutil.rmtree(task.input_path.parent, ignore_errors=True)
        return True

    def cleanup_expired(self) -> int:
        cutoff = datetime.now(timezone.utc).timestamp() - self.ttl
        with self._lock:
            expired_ids = [
                task_id
                for task_id, task in self._tasks.items()
                if task.state in {"completed", "failed"}
                and task.updated_at is not None
                and task.updated_at.timestamp() < cutoff
            ]
        for task_id in expired_ids:
            self.delete(task_id)
        return len(expired_ids)
