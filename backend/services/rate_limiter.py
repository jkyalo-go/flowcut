import time
from collections import defaultdict, deque
from threading import Lock


class RateLimitExceeded(Exception):
    pass


class SlidingWindowRateLimiter:
    def __init__(self, max_calls: int = 20, window_sec: int = 86400):
        self.max_calls = max_calls
        self.window_sec = window_sec
        self._windows: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def _key(self, workspace_id: str, platform: str) -> str:
        return f"{workspace_id}:{platform}"

    def check_and_record(self, workspace_id: str, platform: str) -> None:
        key = self._key(workspace_id, platform)
        now = time.time()
        cutoff = now - self.window_sec
        with self._lock:
            dq = self._windows[key]
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= self.max_calls:
                raise RateLimitExceeded(
                    f"Rate limit {self.max_calls}/{self.window_sec}s exceeded "
                    f"for {workspace_id}:{platform}"
                )
            dq.append(now)

    def remaining(self, workspace_id: str, platform: str) -> int:
        key = self._key(workspace_id, platform)
        now = time.time()
        cutoff = now - self.window_sec
        with self._lock:
            dq = self._windows[key]
            active = sum(1 for t in dq if t > cutoff)
            return max(0, self.max_calls - active)
