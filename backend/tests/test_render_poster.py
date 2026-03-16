"""Tests TDD para POST /api/render-poster (Sprint 11, v0.16.0).

Cobertura (spec render_poster_spec):
  - Auth: 401 sin API key
  - 400 si lineup vacío o ausente
  - 200 + Content-Type image/png en happy path
  - orchestrate_render llamado con payload correcto
  - 500 si orchestrate_render devuelve error
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("WEBHOOK_API_KEY", "test-key")
os.environ.setdefault("SUPABASE_URL", "http://fake-supabase")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-service-key")
os.environ.setdefault("TELEGRAM_BOT_USERNAME", "recova_bot")
os.environ.setdefault("FRONTEND_URL", "https://recova-project-z5zp.vercel.app")
os.environ.setdefault("GOOGLE_OAUTH_CLIENT_ID", "fake-client-id")
os.environ.setdefault("GOOGLE_OAUTH_CLIENT_SECRET", "fake-client-secret")
os.environ.setdefault("GOOGLE_OAUTH_REFRESH_TOKEN", "fake-refresh-token")

from backend.src.triggers.webhook_listener import app  # noqa: E402

API_KEY = "test-key"
AUTH = {"X-API-KEY": API_KEY, "Content-Type": "application/json"}

LINEUP = [
    {"order": 1, "name": "Ana García",   "instagram": "anagarcia"},
    {"order": 2, "name": "Bruno Torres", "instagram": "brunotorres"},
]

VALID_BODY = {
    "event_id": "2026-04-15",
    "lineup": LINEUP,
    "date": "15 ABR",
}

_TMP_PNG = Path("/tmp/render_2026-04-15.png")


def _mock_orchestrate_ok():
    """Mock sync que escribe un PNG mínimo y devuelve status=success."""
    def _fake(payload):
        _TMP_PNG.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
        return {
            "status": "success",
            "image_path": str(_TMP_PNG),
            "output": {"image_path": str(_TMP_PNG)},
        }
    return _fake


def _mock_orchestrate_error():
    """Mock sync que devuelve status=error."""
    def _fake(payload):
        return {
            "status": "error",
            "output": {"message": "Pillow error"},
        }
    return _fake


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_render_poster_requires_api_key():
    """401 sin X-API-KEY."""
    with app.test_client() as c:
        resp = c.post("/api/render-poster",
                      json=VALID_BODY,
                      headers={"Content-Type": "application/json"})
    assert resp.status_code == 401


def test_render_poster_requires_lineup():
    """400 si lineup está vacío o ausente."""
    with patch("backend.src.triggers.blueprints.poster.orchestrate_render", new=_mock_orchestrate_ok()):
        with app.test_client() as c:
            resp = c.post("/api/render-poster", json={"event_id": "evt-1"}, headers=AUTH)
            assert resp.status_code == 400

            resp = c.post("/api/render-poster", json={"event_id": "evt-1", "lineup": []}, headers=AUTH)
            assert resp.status_code == 400


def test_render_poster_returns_png():
    """200 con Content-Type image/png en happy path."""
    with patch("backend.src.triggers.blueprints.poster.orchestrate_render", new=_mock_orchestrate_ok()):
        with app.test_client() as c:
            resp = c.post("/api/render-poster", json=VALID_BODY, headers=AUTH)

    assert resp.status_code == 200
    assert "image/png" in resp.content_type


def test_render_poster_calls_orchestrate_with_correct_payload():
    """orchestrate_render recibe event_id, lineup y date correctos."""
    received = {}

    def _capture(payload):
        received.update(payload)
        _TMP_PNG.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
        return {"status": "success", "image_path": str(_TMP_PNG), "output": {"image_path": str(_TMP_PNG)}}

    with patch("backend.src.triggers.blueprints.poster.orchestrate_render", new=_capture):
        with app.test_client() as c:
            c.post("/api/render-poster", json=VALID_BODY, headers=AUTH)

    assert received["lineup"] == LINEUP
    assert received["date"] == "15 ABR"
    assert received["event_id"] == "2026-04-15"


def test_render_poster_returns_500_on_render_error():
    """500 si orchestrate_render devuelve status=error."""
    with patch("backend.src.triggers.blueprints.poster.orchestrate_render", new=_mock_orchestrate_error()):
        with app.test_client() as c:
            resp = c.post("/api/render-poster", json=VALID_BODY, headers=AUTH)

    assert resp.status_code == 500
    assert "error" in resp.get_json()
