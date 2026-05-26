import logging
import sqlite3
import threading
import time
from pathlib import Path

log = logging.getLogger(__name__)

_DELETION_SCHEMA = """
CREATE TABLE IF NOT EXISTS pending_message_deletions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    delete_at_ts REAL NOT NULL,
    created_ts REAL NOT NULL,
    source TEXT
);
CREATE INDEX IF NOT EXISTS idx_pending_deletions_due
    ON pending_message_deletions(delete_at_ts);
"""


def ensure_deletion_schema(db_path: str | Path) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(_DELETION_SCHEMA)


def schedule_deletion(
    db_path: str | Path,
    chat_id: int,
    message_id: int,
    *,
    delete_after_sec: float = 900,
    source: str = "unknown",
) -> bool:
    now = time.time()
    delete_at = now + delete_after_sec
    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO pending_message_deletions "
                "(chat_id, message_id, delete_at_ts, created_ts, source) "
                "VALUES (?, ?, ?, ?, ?)",
                (chat_id, message_id, delete_at, now, str(source)[:64]),
            )
            conn.commit()
        return True
    except Exception:
        log.exception("Failed to schedule deletion for %s/%s", chat_id, message_id)
        return False


def pop_due(
    db_path: str | Path,
    *,
    now_ts: float | None = None,
    limit: int = 200,
    batch_size: int = 50,
) -> list[tuple[int, int]]:
    now = now_ts if now_ts is not None else time.time()
    try:
        with sqlite3.connect(str(db_path)) as conn:
            rows = conn.execute(
                "SELECT id, chat_id, message_id FROM pending_message_deletions "
                "WHERE delete_at_ts <= ? ORDER BY delete_at_ts ASC LIMIT ?",
                (now, limit),
            ).fetchall()
            if not rows:
                return []
            ids = [r[0] for r in rows]
            placeholders = ",".join("?" for _ in ids)
            conn.execute(
                f"DELETE FROM pending_message_deletions WHERE id IN ({placeholders})", ids
            )
            conn.commit()
            return [(r[1], r[2]) for r in rows]
    except Exception:
        log.exception("Failed to pop due deletions")
        return []


class DeletionQueue:
    def __init__(self, db_path: str | Path):
        self._db_path = db_path
        self._lock = threading.Lock()
        ensure_deletion_schema(db_path)

    def schedule(self, chat_id: int, message_id: int, *, delete_after_sec: float = 900, source: str = "unknown") -> bool:
        with self._lock:
            return schedule_deletion(self._db_path, chat_id, message_id, delete_after_sec=delete_after_sec, source=source)

    def pop_due(self, *, now_ts: float | None = None, limit: int = 200) -> list[tuple[int, int]]:
        with self._lock:
            return pop_due(self._db_path, now_ts=now_ts, limit=limit)
