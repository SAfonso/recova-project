from __future__ import annotations

from datetime import datetime, timezone
import uuid

import app as render_app


def _valid_payload() -> dict:
    request_id = str(uuid.uuid4())
    return {
        "request_id": request_id,
        "schema_version": "1.0",
        "event": {
            "date": "2026-03-05",
            "venue": "Recova Club",
            "city": "Madrid",
            "title": "Open Mic",
            "timezone": "Europe/Madrid",
        },
        "lineup": [
            {"order": 1, "name": "Ana Test", "instagram": "ana.test"},
            {"order": 2, "name": "Beto Demo", "instagram": None},
        ],
        "template": {
            "template_id": "lineup_default_v1",
            "width": 1080,
            "height": 1350,
            "theme": "default",
        },
        "render": {
            "format": "png",
            "quality": 100,
            "scale": 2,
            "timeout_ms": 15000,
        },
        "metadata": {
            "source": "n8n.LineUp",
            "initiated_at": datetime.now(timezone.utc).isoformat(),
            "trace_id": "trace-123",
        },
    }


def test_render_lineup_returns_success_payload(monkeypatch) -> None:
    payload = _valid_payload()
    expected_public_url = "https://example.supabase.co/storage/v1/object/public/posters/2026-03-05/lineup.png"

    class _FakeRenderer:
        def render(self, incoming_payload):
            assert incoming_payload["request_id"] == payload["request_id"]
            return {
                "status": "success",
                "request_id": payload["request_id"],
                "render_id": str(uuid.uuid4()),
                "storage": {"public_url": expected_public_url},
                "artifact": {},
                "timing": {},
                "warnings": [],
                "meta": {"schema_version": "1.0"},
            }

    monkeypatch.setattr(render_app, "PlaywrightRenderer", _FakeRenderer)
    flask_app = render_app.create_app()

    client = flask_app.test_client()
    response = client.post("/render-lineup", json=payload)

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "success"
    assert body["public_url"] == expected_public_url
    assert body["mcp"]["request_id"] == payload["request_id"]


def test_render_lineup_rejects_dirty_instagram() -> None:
    payload = _valid_payload()
    payload["lineup"][0]["instagram"] = "@ana_test"

    flask_app = render_app.create_app()
    client = flask_app.test_client()
    response = client.post("/render-lineup", json=payload)

    assert response.status_code == 400
    body = response.get_json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "INVALID_INPUT_SCHEMA"


def test_render_lineup_maps_storage_error_to_502(monkeypatch) -> None:
    payload = _valid_payload()

    class _FakeRenderer:
        def render(self, _incoming_payload):
            return {
                "status": "error",
                "request_id": payload["request_id"],
                "error": {
                    "code": "STORAGE_UPLOAD_FAILED",
                    "message": "fallo de subida",
                    "details": {"stage": "upload", "retryable": True},
                },
                "meta": {"schema_version": "1.0"},
            }

    monkeypatch.setattr(render_app, "PlaywrightRenderer", _FakeRenderer)
    flask_app = render_app.create_app()

    client = flask_app.test_client()
    response = client.post("/render-lineup", json=payload)

    assert response.status_code == 502
    body = response.get_json()
    assert body["error"]["code"] == "STORAGE_UPLOAD_FAILED"
