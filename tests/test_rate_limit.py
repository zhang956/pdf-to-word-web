from starlette.requests import Request

from app.rate_limit import SlidingWindowLimiter, client_ip


def test_limiter_rejects_request_after_limit_and_recovers_after_window():
    limiter = SlidingWindowLimiter(limit=2, window_seconds=600)

    assert limiter.check("192.0.2.1", now=0)
    assert limiter.check("192.0.2.1", now=1)
    assert not limiter.check("192.0.2.1", now=2)
    assert limiter.check("192.0.2.1", now=601)


def test_limiter_keeps_independent_client_buckets():
    limiter = SlidingWindowLimiter(limit=1, window_seconds=600)

    assert limiter.check("192.0.2.1", now=0)
    assert not limiter.check("192.0.2.1", now=1)
    assert limiter.check("192.0.2.2", now=1)


def test_limiter_bounds_number_of_client_buckets():
    limiter = SlidingWindowLimiter(limit=1, window_seconds=600, max_buckets=2)
    assert limiter.check("one", now=0)
    assert limiter.check("two", now=1)
    assert limiter.check("three", now=2)
    assert len(limiter._events) <= 2


def test_render_proxy_uses_rightmost_forwarded_address_to_defeat_spoof_prefix():
    request = Request(
        {
            "type": "http",
            "client": ("10.0.0.9", 1234),
            "headers": [(b"x-forwarded-for", b"spoofed, 198.51.100.20")],
        }
    )
    assert client_ip(request, trust_render_proxy=True) == "198.51.100.20"
