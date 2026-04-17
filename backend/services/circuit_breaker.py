import time
from threading import Lock


class CircuitOpen(Exception):
    pass


class CircuitBreaker:
    """In-process circuit breaker per platform. Not distributed — use Redis for multi-pod."""

    def __init__(self, platform: str, failure_threshold: int = 5, recovery_sec: int = 120):
        self.platform = platform
        self.failure_threshold = failure_threshold
        self.recovery_sec = recovery_sec
        self._failure_count = 0
        self._opened_at: float | None = None
        self._lock = Lock()

    def is_open(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return False
            if time.time() - self._opened_at >= self.recovery_sec:
                self._opened_at = None
                self._failure_count = 0
                return False
            return True

    def check(self) -> None:
        if self.is_open():
            raise CircuitOpen(f"Circuit open for platform={self.platform}")

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._opened_at = time.time()

    def record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._opened_at = None


_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(platform: str) -> CircuitBreaker:
    if platform not in _breakers:
        _breakers[platform] = CircuitBreaker(platform)
    return _breakers[platform]
