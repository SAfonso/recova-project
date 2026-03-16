"""Unit tests for /ingest and /scoring endpoints (n8n blueprint).

These tests validate the direct-call pipeline (no subprocess).
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("WEBHOOK_API_KEY", "test-key")
os.environ.setdefault("SUPABASE_URL", "http://fake-supabase")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-service-key")

from backend.src.triggers.webhook_listener import app  # noqa: E402

API_KEY = "test-key"
AUTH = {"X-API-KEY": API_KEY, "Content-Type": "application/json"}


def test_ingest_requires_api_key():
    with app.test_client() as c:
        resp = c.post("/ingest", headers={"Content-Type": "application/json"})
    assert resp.status_code == 401


def test_ingest_happy_path():
    """200 cuando run_pipeline devuelve resultado."""
    fake_result = {"inserted": 5, "processed": 10}

    with patch("backend.src.triggers.blueprints.n8n.run_pipeline", return_value=fake_result):
        with app.test_client() as c:
            resp = c.post("/ingest", headers=AUTH)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "success"
    assert data["output"] == fake_result


def test_ingest_returns_500_on_error():
    """500 cuando run_pipeline lanza excepción."""
    with patch("backend.src.triggers.blueprints.n8n.run_pipeline", side_effect=Exception("boom")):
        with app.test_client() as c:
            resp = c.post("/ingest", headers=AUTH)

    assert resp.status_code == 500
    data = resp.get_json()
    assert data["status"] == "error"


def test_scoring_requires_api_key():
    with app.test_client() as c:
        resp = c.post("/scoring", headers={"Content-Type": "application/json"})
    assert resp.status_code == 401


def test_scoring_happy_path():
    """200 cuando execute_scoring devuelve resultado."""
    expected = {"status": "ok", "lineup": ["ana", "luis"]}

    with patch("backend.src.triggers.blueprints.n8n.execute_scoring", return_value=expected):
        with app.test_client() as c:
            resp = c.post("/scoring", headers=AUTH)

    assert resp.status_code == 200
    assert resp.get_json() == expected


def test_scoring_returns_500_on_error():
    """500 cuando execute_scoring lanza excepción."""
    with patch("backend.src.triggers.blueprints.n8n.execute_scoring", side_effect=Exception("boom")):
        with app.test_client() as c:
            resp = c.post("/scoring", headers=AUTH)

    assert resp.status_code == 500
    data = resp.get_json()
    assert data["status"] == "error"
