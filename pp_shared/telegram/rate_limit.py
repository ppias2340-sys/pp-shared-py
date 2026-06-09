import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

log = logging.getLogger(__name__)

_RATE_LIMIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS rate_limit_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    attempted_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rate_limit_key_time
    ON rate_limit_attempts(key, attempted_at);
"""


@dataclass
class RateLimitDecision:
    allowed: bool
    retry_after_sec: float = 0.0
    current_count: int = 0


class RateLimiter:
    def __init__(
        self,
        db_path: str | Path,
        max_requests: int,
        window_sec: int,
    ):
        self._db_path = str(db_path)
        self._max = max_requests
        self._window_sec = window_sec
        self._lock = Lock()
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript(_RATE_LIMIT_SCHEMA)

    def check(self, user_id: int, command: str) -> RateLimitDecision:
        key = f"{user_id}:{command}"
        now = time.time()
        window_start = now - self._window_sec

        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("DELETE FROM rate_limit_attempts WHERE attempted_at < ?", (window_start,))
                count = conn.execute(
                    "SELECT COUNT(*) FROM rate_limit_attempts WHERE key = ? AND attempted_at >= ?",
                    (key, window_start),
                ).fetchone()[0]

                if count >= self._max:
                    oldest = conn.execute(
                        "SELECT attempted_at FROM rate_limit_attempts WHERE key = ? AND attempted_at >= ? ORDER BY attempted_at ASC LIMIT 1",
                        (key, window_start),
                    ).fetchone()
                    retry_after = (oldest[0] + self._window_sec) - now if oldest else self._window_sec
                    return RateLimitDecision(allowed=False, retry_after_sec=max(0.0, retry_after), current_count=count)

                conn.execute(
                    "INSERT INTO rate_limit_attempts (key, attempted_at) VALUES (?, ?)",
                    (key, now),
                )
                conn.commit()

        return RateLimitDecision(allowed=True, current_count=count + 1)

    def cleanup_stale(self) -> int:
        cutoff = time.time() - self._window_sec
        with sqlite3.connect(self._db_path) as conn:
            deleted = conn.execute(
                "DELETE FROM rate_limit_attempts WHERE attempted_at < ?", (cutoff,)
            ).rowcount
            conn.commit()
            return deleted
