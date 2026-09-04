from datetime import datetime, timedelta, timezone
import os

from app.tasks import TaskStore


def test_task_lifecycle_uses_isolated_paths(tmp_path):
    store = TaskStore(tmp_path, ttl=3600)
    task = store.create("报告.pdf")

    assert task.input_path.parent == tmp_path / task.id
    assert task.output_path.parent == task.input_path.parent
    assert task.progress == 0

    store.update(task.id, state="running", current_page=1, total_pages=2)
    assert store.get(task.id).progress == 50

    store.update(task.id, state="completed")
    assert store.get(task.id).progress == 100

    store.delete(task.id)
    assert store.get(task.id) is None
    assert not task.input_path.parent.exists()


def test_cleanup_removes_only_expired_tasks(tmp_path):
    store = TaskStore(tmp_path, ttl=3600)
    expired = store.create("old.pdf")
    current = store.create("new.pdf")
    store.update(expired.id, state="completed")
    store.update(
        expired.id,
        updated_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )

    removed = store.cleanup_expired()

    assert removed == 1
    assert store.get(expired.id) is None
    assert store.get(current.id) is not None


def test_cleanup_keeps_active_tasks_even_when_old(tmp_path):
    store = TaskStore(tmp_path, ttl=3600)
    task = store.create("running.pdf")
    store.update(task.id, state="running")
    store.update(
        task.id,
        updated_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )

    assert store.cleanup_expired() == 0
    assert store.get(task.id) is not None


def test_store_startup_removes_only_stale_orphan_directories(tmp_path):
    stale = tmp_path / "stale-task"
    fresh = tmp_path / "fresh-task"
    stale.mkdir()
    fresh.mkdir()
    old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()
    os.utime(stale, (old_time, old_time))

    TaskStore(tmp_path, ttl=3600)

    assert not stale.exists()
    assert fresh.exists()
