import logging
import time
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class PollStats:
    cycles: int = 0
    errors: int = 0
    last_error: str | None = None
    last_error_ts: float = 0.0
    consecutive_errors: int = 0
    max_consecutive: int = 10
    total_wall_sec: float = 0.0


class PollLoop:
    def __init__(
        self,
        *,
        interval_sec: float = 60,
        max_consecutive_errors: int = 10,
        backoff_factor: float = 2,
        backoff_max: float = 600,
    ):
        self._interval = interval_sec
        self._max_consecutive = max_consecutive_errors
        self._backoff_factor = backoff_factor
        self._backoff_max = backoff_max
        self.stats = PollStats(max_consecutive=max_consecutive_errors)

    def run(self, poll_fn, *, stop_event=None, sleep_fn=time.sleep):
        while True:
            if stop_event is not None and stop_event.is_set():
                break

            start = time.time()
            try:
                poll_fn()
                self.stats.consecutive_errors = 0
            except Exception as e:
                self.stats.errors += 1
                self.stats.last_error = type(e).__name__
                self.stats.last_error_ts = time.time()
                self.stats.consecutive_errors += 1
                log.warning(
                    "Poll failed (%d/%d): %s",
                    self.stats.consecutive_errors,
                    self._max_consecutive,
                    type(e).__name__,
                )
                if self.stats.consecutive_errors >= self._max_consecutive:
                    raise

            elapsed = time.time() - start
            self.stats.cycles += 1
            self.stats.total_wall_sec += elapsed

            if self.stats.consecutive_errors > 0:
                sleep = min(self._interval * (self._backoff_factor ** self.stats.consecutive_errors), self._backoff_max)
            else:
                sleep = max(1.0, self._interval - elapsed)

            if stop_event is not None:
                if stop_event.wait(sleep):
                    break
            else:
                sleep_fn(sleep)
