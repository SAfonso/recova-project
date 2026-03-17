"""Tests for the rate_limit decorator in shared.py."""

import os

os.environ.setdefault("WEBHOOK_API_KEY", "test-key")
os.environ.setdefault("SUPABASE_URL", "http://fake-supabase")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-service-key")

from flask import Flask, jsonify

from backend.src.triggers.shared import rate_limit, _rate_limit_store

app = Flask(__name__)


@app.route("/test-rate-default", methods=["POST"])
@rate_limit(max_requests=3, window_seconds=60)
def endpoint_rate_default():
    return jsonify({"ok": True}), 200


@app.route("/test-rate-tight", methods=["GET"])
@rate_limit(max_requests=1, window_seconds=10)
def endpoint_rate_tight():
    return jsonify({"ok": True}), 200


class TestRateLimitDecorator:
    """Tests para @rate_limit."""

    def setup_method(self):
        _rate_limit_store.clear()

    def test_allows_requests_within_limit(self):
        with app.test_client() as c:
            for _ in range(3):
                resp = c.post("/test-rate-default")
                assert resp.status_code == 200

    def test_blocks_request_exceeding_limit(self):
        with app.test_client() as c:
            for _ in range(3):
                c.post("/test-rate-default")
            resp = c.post("/test-rate-default")
            assert resp.status_code == 429
            body = resp.get_json()
            assert body["error"]["code"] == "RATE_LIMITED"

    def test_429_includes_retry_after_header(self):
        with app.test_client() as c:
            c.post("/test-rate-default")
            c.post("/test-rate-default")
            c.post("/test-rate-default")
            resp = c.post("/test-rate-default")
            assert resp.status_code == 429
            assert resp.headers.get("Retry-After") == "60"

    def test_429_includes_ratelimit_headers(self):
        with app.test_client() as c:
            for _ in range(3):
                c.post("/test-rate-default")
            resp = c.post("/test-rate-default")
            assert resp.headers.get("X-RateLimit-Limit") == "3"
            assert resp.headers.get("X-RateLimit-Remaining") == "0"
            assert resp.headers.get("X-RateLimit-Reset") == "60"

    def test_successful_response_includes_ratelimit_headers(self):
        with app.test_client() as c:
            resp = c.post("/test-rate-default")
            assert resp.status_code == 200
            assert resp.headers.get("X-RateLimit-Limit") == "3"
            assert resp.headers.get("X-RateLimit-Remaining") == "2"
            assert resp.headers.get("X-RateLimit-Reset") == "60"

    def test_remaining_decreases_with_each_request(self):
        with app.test_client() as c:
            resp1 = c.post("/test-rate-default")
            assert resp1.headers.get("X-RateLimit-Remaining") == "2"
            resp2 = c.post("/test-rate-default")
            assert resp2.headers.get("X-RateLimit-Remaining") == "1"
            resp3 = c.post("/test-rate-default")
            assert resp3.headers.get("X-RateLimit-Remaining") == "0"

    def test_different_endpoints_have_separate_limits(self):
        with app.test_client() as c:
            # Agotar límite del endpoint tight
            c.get("/test-rate-tight")
            resp_tight = c.get("/test-rate-tight")
            assert resp_tight.status_code == 429

            # El endpoint default sigue disponible
            resp_default = c.post("/test-rate-default")
            assert resp_default.status_code == 200

    def test_window_expiry_resets_counter(self):
        """Simula expiración de ventana manipulando timestamps."""
        import time
        from unittest.mock import patch

        with app.test_client() as c:
            # Agotar límite
            c.get("/test-rate-tight")
            resp = c.get("/test-rate-tight")
            assert resp.status_code == 429

            # Simular que pasaron 11 segundos avanzando monotonic
            original_monotonic = time.monotonic
            offset = 11

            with patch("backend.src.triggers.shared.time") as mock_time:
                mock_time.monotonic.return_value = original_monotonic() + offset
                resp = c.get("/test-rate-tight")
                assert resp.status_code == 200

    def test_single_request_limit(self):
        with app.test_client() as c:
            resp1 = c.get("/test-rate-tight")
            assert resp1.status_code == 200
            assert resp1.headers.get("X-RateLimit-Remaining") == "0"

            resp2 = c.get("/test-rate-tight")
            assert resp2.status_code == 429
