"""Map of source ids to target ids, written ahead of every create.

Entries are keyed `<kind>:<source id>`. A create first saves the entry as `pending`, then as
`done` with the target id, so a crash between the two is visible on the next run.

Each change is appended to `<state>.journal` and flushed to disk, which costs the same no
matter how big the project is. `save()` folds the journal back into the state file; the CLI
does that at the start and end of every apply.
"""

from __future__ import annotations

import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from project_migrate.api import Abort


class State:
    def __init__(self, path: Path, dry: bool):
        self.path = path
        self.journal_path = path.with_suffix(".journal")
        self.dry = dry
        self.data: dict = {"version": 1, "entries": {}}
        self._lock = None
        self._journal = None
        if path.exists():
            self.data = json.loads(path.read_text())
        self._replay_journal()

    def _replay_journal(self) -> None:
        if not self.journal_path.exists():
            return
        for line in self.journal_path.read_text().splitlines():
            try:
                change = json.loads(line)
            except ValueError:
                continue  # a line torn by a crash mid-write; the change it held never finished
            self.data["entries"].setdefault(change["key"], {}).update(change["fields"])

    def lock(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_suffix(".lock")
        # Left open on purpose: the lock is held until the process exits.
        self._lock = open(lock_path, "w")
        try:
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Abort(f"another apply holds {lock_path}") from None

    def get(self, key: str) -> dict | None:
        return self.data["entries"].get(key)

    def entries(self, prefix: str) -> dict[str, dict]:
        return {k: v for k, v in self.data["entries"].items() if k.startswith(prefix)}

    def put(self, key: str, **fields: Any) -> None:
        if self.dry:
            return
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.data["entries"].setdefault(key, {}).update(fields)
        if self._journal is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._journal = open(self.journal_path, "a")
        self._journal.write(json.dumps({"key": key, "fields": fields}, ensure_ascii=False) + "\n")
        self._journal.flush()
        os.fsync(self._journal.fileno())

    def save(self) -> None:
        """Write everything to the state file atomically, then empty the journal."""
        if self.dry:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1, ensure_ascii=False))
        os.replace(tmp, self.path)
        if self._journal is not None:
            self._journal.close()
            self._journal = None
        self.journal_path.unlink(missing_ok=True)
