"""Tests TDD para los endpoints de validacion via Telegram.

Endpoints cubiertos (spec §8):
  POST /api/lineup/prepare-validation
  GET  /api/validate-view/lineup
  POST /api/validate-view/validate
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

os.environ.setdefault("WEBHOOK_API_KEY", "test-key")
os.environ.setdefault("SUPABASE_URL", "http://fake-supabase")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-service-key")
os.environ.setdefault("TELEGRAM_BOT_USERNAME", "recova_bot")
os.environ.setdefault("FRONTEND_URL", "https://recova-project-z5zp.vercel.app")

from backend.src.triggers.webhook_listener import app  # noqa: E402

API_KEY = "test-key"
AUTH = {"X-API-KEY": API_KEY, "Content-Type": "application/json"}
OPEN_MIC_ID = "11111111-0000-0000-0000-000000000001"
HOST_ID = "22222222-0000-0000-0000-000000000002"
TOKEN = "33333333-0000-0000-0000-000000000003"
FECHA = "2026-03-09"
FUTURE = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
PAST = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

OPEN_MIC_CONFIG = {
    "id": OPEN_MIC_ID,
    "proveedor_id": "prov-001",
    "config": {"info": {"dia_semana": "Lunes", "hora": "21:00"}},
}

CANDIDATES = [
    {"solicitud_id": "sol-1", "nombre": "Carlos Ruiz", "instagram": "carlosruiz", "score_aplicado": 85},
    {"solicitud_id": "sol-2", "nombre": "Ana Lopez",   "instagram": "analopez",   "score_aplicado": 72},
]

TOKEN_ROW = {
    "token": TOKEN,
    "host_id": HOST_ID,
    "open_mic_id": OPEN_MIC_ID,
    "fecha_evento": FECHA,
    "expires_at": FUTURE,
}


# ---------------------------------------------------------------------------
# Helpers de mock
# ---------------------------------------------------------------------------

def _chain(data):
    """Mock Supabase totalmente encadenable."""
    m = MagicMock()
    m.execute.return_value = MagicMock(data=data)
    for method in ("eq", "select", "insert", "update", "delete", "order",
                   "single", "limit", "in_", "neq"):
        getattr(m, method).return_value = m
    return m


def _make_sb(schema_dispatch: dict):
    """
    schema_dispatch: { "silver": callable(table) → chain, "gold": callable(table) → chain }
    """
    def _schema(name):
        mock = MagicMock()
        dispatch = schema_dispatch.get(name, {})
        if callable(dispatch):
            mock.from_.side_effect = dispatch
        else:
            mock.from_.side_effect = lambda t: dispatch.get(t, _chain([]))
        # RPC support
        rpc_dispatch = schema_dispatch.get(f"{name}_rpc", {})
        def _rpc(func, params):
            data = rpc_dispatch.get(func, 1)
            r = MagicMock()
            r.execute.return_value = MagicMock(data=data)
            return r
        mock.rpc.side_effect = _rpc
        return mock

    sb = MagicMock()
    sb.schema.side_effect = _schema

    # Top-level rpc (gold schema uses schema().rpc sometimes)
    top_rpc = schema_dispatch.get("top_rpc", {})
    def _top_rpc(func, params):
        data = top_rpc.get(func, 1)
        r = MagicMock()
        r.execute.return_value = MagicMock(data=data)
        return r
    sb.rpc.side_effect = _top_rpc

    return sb


# ---------------------------------------------------------------------------
# POST /api/lineup/prepare-validation
# ---------------------------------------------------------------------------

def test_prepare_validation_happy_path():
    """200 con lineup, validate_url y fecha_evento."""
    sb = _make_sb({
        "silver": {
            "open_mics": _chain([OPEN_MIC_CONFIG]),
            "organization_members": _chain([{"user_id": HOST_ID}]),
            "validation_tokens": _chain([{"token": TOKEN}]),
        },
        "gold": {
            "lineup_candidates": _chain(CANDIDATES),
        },
    })
    future_dt = datetime.now(timezone.utc) + timedelta(days=3)

    with patch("backend.src.triggers.blueprints.lineup._sb_client", return_value=sb), \
         patch("backend.src.triggers.blueprints.lineup.execute_scoring", return_value={"status": "ok"}), \
         patch("backend.src.triggers.blueprints.lineup._next_event_datetime", return_value=future_dt):
        with app.test_client() as c:
            resp = c.post("/api/lineup/prepare-validation",
                          json={"host_id": HOST_ID, "open_mic_id": OPEN_MIC_ID},
                          headers=AUTH)

    assert resp.status_code == 200
    data = resp.get_json()
    assert "validate_url" in data
    assert "recova-project" in data["validate_url"]
    assert TOKEN in data["validate_url"]
    assert "lineup" in data
    assert len(data["lineup"]) == 2
    assert "fecha_evento" in data


def test_prepare_validation_no_upcoming_show():
    """409 si el show ya empezo esta semana."""
    sb = _make_sb({
        "silver": {
            "open_mics": _chain([OPEN_MIC_CONFIG]),
            "organization_members": _chain([{"user_id": HOST_ID}]),
        },
    })

    with patch("backend.src.triggers.blueprints.lineup._sb_client", return_value=sb), \
         patch("backend.src.triggers.blueprints.lineup._next_event_datetime", return_value=None):
        with app.test_client() as c:
            resp = c.post("/api/lineup/prepare-validation",
                          json={"host_id": HOST_ID, "open_mic_id": OPEN_MIC_ID},
                          headers=AUTH)

    assert resp.status_code == 409


def test_prepare_validation_missing_config():
    """404 si el open mic no tiene dia_semana u hora configurados."""
    no_config = {"id": OPEN_MIC_ID, "proveedor_id": "prov-001", "config": {"info": {}}}
    sb = _make_sb({"silver": {
        "open_mics": _chain([no_config]),
        "organization_members": _chain([{"user_id": HOST_ID}]),
    }})

    with patch("backend.src.triggers.blueprints.lineup._sb_client", return_value=sb):
        with app.test_client() as c:
            resp = c.post("/api/lineup/prepare-validation",
                          json={"host_id": HOST_ID, "open_mic_id": OPEN_MIC_ID},
                          headers=AUTH)

    assert resp.status_code == 404


def test_prepare_validation_requires_api_key():
    with app.test_client() as c:
        resp = c.post("/api/lineup/prepare-validation",
                      json={"host_id": HOST_ID, "open_mic_id": OPEN_MIC_ID},
                      headers={"Content-Type": "application/json"})
    assert resp.status_code == 401


def test_prepare_validation_missing_fields():
    with app.test_client() as c:
        resp = c.post("/api/lineup/prepare-validation",
                      json={"host_id": HOST_ID},
                      headers=AUTH)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/validate-view/lineup
# ---------------------------------------------------------------------------

def test_lineup_view_happy_path():
    """200 con candidates e is_validated=False."""
    sb = _make_sb({
        "silver": {
            "validation_tokens": _chain([TOKEN_ROW]),
            "lineup_slots": _chain([]),  # no slots → not validated
        },
        "gold": {
            "lineup_candidates": _chain(CANDIDATES),
        },
    })

    with patch("backend.src.triggers.blueprints.lineup._sb_client", return_value=sb):
        with app.test_client() as c:
            resp = c.get(f"/api/validate-view/lineup?token={TOKEN}")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["is_validated"] is False
    assert len(data["candidates"]) == 2
    assert data["open_mic_id"] == OPEN_MIC_ID
    assert data["fecha_evento"] == FECHA


def test_lineup_view_already_validated():
    """is_validated=True si hay slots confirmados."""
    sb = _make_sb({
        "silver": {
            "validation_tokens": _chain([TOKEN_ROW]),
            "lineup_slots": _chain([{"id": "slot-1"}]),
        },
        "gold": {
            "lineup_candidates": _chain(CANDIDATES),
        },
    })

    with patch("backend.src.triggers.blueprints.lineup._sb_client", return_value=sb):
        with app.test_client() as c:
            resp = c.get(f"/api/validate-view/lineup?token={TOKEN}")

    assert resp.status_code == 200
    assert resp.get_json()["is_validated"] is True


def test_lineup_view_token_not_found():
    sb = _make_sb({"silver": {"validation_tokens": _chain([])}})

    with patch("backend.src.triggers.blueprints.lineup._sb_client", return_value=sb):
        with app.test_client() as c:
            resp = c.get(f"/api/validate-view/lineup?token=nonexistent")

    assert resp.status_code == 404


def test_lineup_view_token_expired():
    expired_row = {**TOKEN_ROW, "expires_at": PAST}
    sb = _make_sb({"silver": {"validation_tokens": _chain([expired_row])}})

    with patch("backend.src.triggers.blueprints.lineup._sb_client", return_value=sb):
        with app.test_client() as c:
            resp = c.get(f"/api/validate-view/lineup?token={TOKEN}")

    assert resp.status_code == 410


# ---------------------------------------------------------------------------
# POST /api/validate-view/validate
# ---------------------------------------------------------------------------

def test_validate_view_happy_path():
    """200, RPCs llamados, token eliminado."""
    token_chain = _chain([TOKEN_ROW])
    sb = _make_sb({
        "silver": {
            "validation_tokens": token_chain,
        },
        "gold_rpc": {"validate_lineup": None},
        "silver_rpc": {"upsert_confirmed_lineup": 3},
    })

    with patch("backend.src.triggers.blueprints.lineup._sb_client", return_value=sb):
        with app.test_client() as c:
            resp = c.post("/api/validate-view/validate",
                          json={"token": TOKEN, "solicitud_ids": ["sol-1", "sol-2"]},
                          headers={"Content-Type": "application/json"})

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "validated"


def test_validate_view_invalid_token():
    sb = _make_sb({"silver": {"validation_tokens": _chain([])}})

    with patch("backend.src.triggers.blueprints.lineup._sb_client", return_value=sb):
        with app.test_client() as c:
            resp = c.post("/api/validate-view/validate",
                          json={"token": "bad-token", "solicitud_ids": ["sol-1"]},
                          headers={"Content-Type": "application/json"})

    assert resp.status_code == 404


def test_validate_view_empty_solicitud_ids():
    with app.test_client() as c:
        resp = c.post("/api/validate-view/validate",
                      json={"token": TOKEN, "solicitud_ids": []},
                      headers={"Content-Type": "application/json"})

    assert resp.status_code == 400
