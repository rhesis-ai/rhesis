"""Dev log files are rotated and old runs are pruned, so LOG_DIR stays bounded."""

import os
import time

from rhesis.backend.logging.logging_config import _prune_dev_logs


def _touch(path, mtime):
    path.write_text("x")
    os.utime(path, (mtime, mtime))


def test_prune_keeps_newest_runs_and_their_backups(tmp_path):
    now = time.time()
    for i in range(5):
        _touch(tmp_path / f"rhesis_run{i}.log", now - i * 60)
        _touch(tmp_path / f"rhesis_run{i}.log.1", now - i * 60)
    unrelated = tmp_path / "notes.txt"
    unrelated.write_text("keep me")

    _prune_dev_logs(tmp_path, keep=2)

    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "notes.txt",
        "rhesis_run0.log",
        "rhesis_run0.log.1",
        "rhesis_run1.log",
        "rhesis_run1.log.1",
    ]


def test_prune_with_fewer_runs_than_keep_deletes_nothing(tmp_path):
    _touch(tmp_path / "rhesis_only.log", time.time())

    _prune_dev_logs(tmp_path, keep=10)

    assert [p.name for p in tmp_path.iterdir()] == ["rhesis_only.log"]
