import time

from services.circuit_breaker import CircuitBreaker, CircuitOpen


def test_circuit_opens_after_threshold():
    cb = CircuitBreaker("test_platform", failure_threshold=3, recovery_sec=60)
    for _ in range(3):
        cb.record_failure()
    assert cb.is_open()


def test_circuit_blocks_calls_when_open():
    cb = CircuitBreaker("test_platform2", failure_threshold=2, recovery_sec=60)
    cb.record_failure()
    cb.record_failure()
    try:
        cb.check()
        assert False, "should have raised"
    except CircuitOpen:
        pass


def test_circuit_resets_on_success():
    cb = CircuitBreaker("test_platform3", failure_threshold=3, recovery_sec=60)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    assert not cb.is_open()
    assert cb._failure_count == 0


def test_circuit_half_open_after_recovery_window(monkeypatch):
    cb = CircuitBreaker("test_platform4", failure_threshold=2, recovery_sec=1)
    cb.record_failure()
    cb.record_failure()
    assert cb.is_open()
    # Advance time past recovery window
    real_time = time.time()
    monkeypatch.setattr(time, "time", lambda: real_time + 2)
    assert not cb.is_open()  # half-open — allows one probe
