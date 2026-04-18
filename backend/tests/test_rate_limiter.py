from services.rate_limiter import RateLimitExceeded, SlidingWindowRateLimiter


def test_allows_requests_under_limit():
    rl = SlidingWindowRateLimiter(max_calls=5, window_sec=60)
    for _ in range(5):
        rl.check_and_record("ws1", "youtube")


def test_blocks_requests_over_limit():
    rl = SlidingWindowRateLimiter(max_calls=3, window_sec=60)
    for _ in range(3):
        rl.check_and_record("ws2", "tiktok")
    try:
        rl.check_and_record("ws2", "tiktok")
        assert False, "should have raised"
    except RateLimitExceeded:
        pass


def test_independent_buckets_per_platform():
    rl = SlidingWindowRateLimiter(max_calls=2, window_sec=60)
    rl.check_and_record("ws3", "youtube")
    rl.check_and_record("ws3", "youtube")
    # Different platform — separate bucket
    rl.check_and_record("ws3", "tiktok")
    rl.check_and_record("ws3", "tiktok")
