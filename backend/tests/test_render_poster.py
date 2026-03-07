"""Tests TDD para POST /api/render-poster (Sprint 11, v0.16.0).

Cobertura (spec render_poster_spec):
  - Auth: 401 sin API key
  - 400 si lineup vacío o ausente
  - 200 + Content-Type image/png en happy path
  - PosterComposer.render llamado con args correctos
  - 500 si PosterComposer lanza excepción
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

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


def _mock_composer_render(output_path_kwarg: str = "output_path"):
    """Devuelve un mock de PosterComposer cuyo render escribe un PNG mínimo."""
    mock = MagicMock()

    def fake_render(**kwargs):
        path = kwargs.get(output_path_kwarg) or kwargs.get("output_path")
        Path(str(path)).write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)

    mock.return_value.render.side_effect = fake_render
    return mock


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
    with patch("backend.src.triggers.webhook_listener.PosterComposer", _mock_composer_render()):
        with app.test_client() as c:
            # Sin lineup
            resp = c.post("/api/render-poster", json={"event_id": "evt-1"}, headers=AUTH)
            assert resp.status_code == 400

            # Lineup vacío
            resp = c.post("/api/render-poster", json={"event_id": "evt-1", "lineup": []}, headers=AUTH)
            assert resp.status_code == 400


def test_render_poster_returns_png():
    """200 con Content-Type image/png en happy path."""
    with patch("backend.src.triggers.webhook_listener.PosterComposer", _mock_composer_render()):
        with app.test_client() as c:
            resp = c.post("/api/render-poster", json=VALID_BODY, headers=AUTH)

    assert resp.status_code == 200
    assert "image/png" in resp.content_type


def test_render_poster_calls_composer_with_correct_args():
    """PosterComposer.render se llama con lineup, date y event_id correctos."""
    MockComposer = _mock_composer_render()

    with patch("backend.src.triggers.webhook_listener.PosterComposer", MockComposer):
        with app.test_client() as c:
            c.post("/api/render-poster", json=VALID_BODY, headers=AUTH)

    call_kwargs = MockComposer.return_value.render.call_args[1]
    assert call_kwargs["lineup"] == LINEUP
    assert call_kwargs["date"] == "15 ABR"
    assert call_kwargs["event_id"] == "2026-04-15"


def test_render_poster_returns_500_on_render_error():
    """500 si PosterComposer.render lanza excepción."""
    MockComposer = MagicMock()
    MockComposer.return_value.render.side_effect = RuntimeError("Pillow error")

    with patch("backend.src.triggers.webhook_listener.PosterComposer", MockComposer):
        with app.test_client() as c:
            resp = c.post("/api/render-poster", json=VALID_BODY, headers=AUTH)

    assert resp.status_code == 500
    assert "error" in resp.get_json()
