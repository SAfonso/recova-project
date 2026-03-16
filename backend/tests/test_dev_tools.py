"""Tests TDD para endpoints /api/dev/* (Sprint 12, v0.17.0).

Cobertura (spec dev_tools_spec):
  - Auth JWT: 401 sin token, 401 token inválido
  - seed-open-mic: happy path, 400 sin open_mic_id, 404 not found, 409 ya sembrado
  - trigger-ingest: happy path, 401
  - trigger-scoring: happy path, 401
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("WEBHOOK_API_KEY", "test-key")
os.environ.setdefault("SUPABASE_URL", "http://fake-supabase")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-service-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("TELEGRAM_BOT_USERNAME", "recova_bot")
os.environ.setdefault("FRONTEND_URL", "https://recova-project-z5zp.vercel.app")
os.environ.setdefault("GOOGLE_OAUTH_CLIENT_ID", "fake-client-id")
os.environ.setdefault("GOOGLE_OAUTH_CLIENT_SECRET", "fake-client-secret")
os.environ.setdefault("GOOGLE_OAUTH_REFRESH_TOKEN", "fake-refresh-token")

from backend.src.triggers.webhook_listener import app  # noqa: E402

# ---------------------------------------------------------------------------
# JWT mock helpers
# ---------------------------------------------------------------------------

VALID_USER_PAYLOAD = {"sub": "user-123", "email": "test@example.com"}
VALID_AUTH = {"Authorization": "Bearer valid.jwt.token", "Content-Type": "application/json"}


def _patch_auth_valid():
    """Contexto que hace que _is_authenticated_user devuelva un payload válido."""
    return patch(
        "backend.src.triggers.blueprints.dev._is_authenticated_user",
        return_value=VALID_USER_PAYLOAD,
    )


def _patch_auth_invalid():
    """Contexto que hace que _is_authenticated_user devuelva None (token inválido)."""
    return patch(
        "backend.src.triggers.blueprints.dev._is_authenticated_user",
        return_value=None,
    )


# ---------------------------------------------------------------------------
# Supabase mock helpers
# ---------------------------------------------------------------------------

def _chain(data):
    m = MagicMock()
    m.execute.return_value = MagicMock(data=data)
    for method in ("eq", "select", "insert", "update", "delete", "order",
                   "single", "limit", "in_", "neq", "not_", "filter"):
        getattr(m, method).return_value = m
    return m


def _make_sb(schema_dispatch: dict):
    mocks: dict = {}

    def _schema(name):
        if name not in mocks:
            mock = MagicMock()
            dispatch = schema_dispatch.get(name, {})
            if callable(dispatch):
                mock.from_.side_effect = dispatch
            else:
                mock.from_.side_effect = lambda t, d=dispatch: d.get(t, _chain([]))
            mocks[name] = mock
        return mocks[name]

    sb = MagicMock()
    sb.schema.side_effect = _schema
    sb._mocks = mocks
    return sb


OM_WITH_CONFIG = {
    "id": "om-001",
    "proveedor_id": "prov-001",
    "config": {},
}

OM_ALREADY_SEEDED = {
    "id": "om-001",
    "proveedor_id": "prov-001",
    "config": {"seed_used": True},
}

# ---------------------------------------------------------------------------
# Tests: seed-open-mic
# ---------------------------------------------------------------------------

def test_seed_requires_jwt():
    """401 sin header Authorization."""
    with app.test_client() as c:
        resp = c.post("/api/dev/seed-open-mic",
                      json={"open_mic_id": "om-001"},
                      headers={"Content-Type": "application/json"})
    assert resp.status_code == 401


def test_seed_invalid_jwt():
    """401 con token inválido."""
    with _patch_auth_invalid():
        with app.test_client() as c:
            resp = c.post("/api/dev/seed-open-mic",
                          json={"open_mic_id": "om-001"},
                          headers=VALID_AUTH)
    assert resp.status_code == 401


def test_seed_requires_open_mic_id():
    """400 si open_mic_id está ausente."""
    with _patch_auth_valid():
        with app.test_client() as c:
            resp = c.post("/api/dev/seed-open-mic", json={}, headers=VALID_AUTH)
    assert resp.status_code == 400


def test_seed_open_mic_not_found():
    """404 si el open mic no existe."""
    sb = _make_sb({"silver": {"open_mics": _chain([])}})

    with _patch_auth_valid(), \
         patch("backend.src.triggers.blueprints.dev.create_client", return_value=sb):
        with app.test_client() as c:
            resp = c.post("/api/dev/seed-open-mic",
                          json={"open_mic_id": "om-999"},
                          headers=VALID_AUTH)
    assert resp.status_code == 404


def test_seed_already_seeded():
    """409 si config.seed_used es true."""
    sb = _make_sb({"silver": {"open_mics": _chain([OM_ALREADY_SEEDED])}})

    with _patch_auth_valid(), \
         patch("backend.src.triggers.blueprints.dev.create_client", return_value=sb):
        with app.test_client() as c:
            resp = c.post("/api/dev/seed-open-mic",
                          json={"open_mic_id": "om-001"},
                          headers=VALID_AUTH)
    assert resp.status_code == 409


def test_seed_happy_path():
    """200: inserta 10 bronze, lanza Popen, marca seed_used."""
    sb = _make_sb({
        "silver": {
            "open_mics": _chain([OM_WITH_CONFIG]),
            "organization_members": _chain([{"user_id": VALID_USER_PAYLOAD["sub"]}]),
        },
        "bronze": {"solicitudes": _chain([{"id": "new"}])},
    })

    with _patch_auth_valid(), \
         patch("backend.src.triggers.blueprints.dev.create_client", return_value=sb), \
         patch("backend.src.triggers.blueprints.dev.run_ingestion_async") as mock_popen:

        with app.test_client() as c:
            resp = c.post("/api/dev/seed-open-mic",
                          json={"open_mic_id": "om-001"},
                          headers=VALID_AUTH)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["seeded"] == 10

    # Verificar 10 inserciones en bronze
    bronze_chain = sb._mocks["bronze"].from_("solicitudes")
    assert bronze_chain.insert.call_count == 10

    # Verificar que se lanzó b2s
    mock_popen.assert_called_once()

    # Verificar RPC seed_used
    silver_mock = sb._mocks["silver"]
    silver_mock.rpc.assert_called_once_with(
        "update_open_mic_config_keys",
        {"p_open_mic_id": "om-001", "p_keys": {"seed_used": True}},
    )


# ---------------------------------------------------------------------------
# Tests: trigger-ingest
# ---------------------------------------------------------------------------

def test_trigger_ingest_requires_jwt():
    """401 sin Authorization."""
    with app.test_client() as c:
        resp = c.post("/api/dev/trigger-ingest",
                      json={"open_mic_id": "om-001"},
                      headers={"Content-Type": "application/json"})
    assert resp.status_code == 401


def test_trigger_ingest_happy_path():
    """200 y lanza los dos Popen de ingesta."""
    with _patch_auth_valid(), \
         patch("backend.src.triggers.blueprints.dev.run_ingestion_async") as mock_popen:

        with app.test_client() as c:
            resp = c.post("/api/dev/trigger-ingest",
                          json={"open_mic_id": "om-001"},
                          headers=VALID_AUTH)

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"
    assert mock_popen.call_count >= 1


# ---------------------------------------------------------------------------
# Tests: trigger-scoring
# ---------------------------------------------------------------------------

def test_trigger_scoring_requires_jwt():
    """401 sin Authorization."""
    with app.test_client() as c:
        resp = c.post("/api/dev/trigger-scoring",
                      json={"open_mic_id": "om-001"},
                      headers={"Content-Type": "application/json"})
    assert resp.status_code == 401


def test_trigger_scoring_happy_path():
    """200 y devuelve resultado de execute_scoring."""
    fake_result = {"status": "ok", "scored": 10}
    sb = _make_sb({
        "silver": {
            "open_mics": _chain([{"proveedor_id": "prov-001"}]),
            "organization_members": _chain([{"user_id": VALID_USER_PAYLOAD["sub"]}]),
        },
    })

    with _patch_auth_valid(), \
         patch("backend.src.triggers.blueprints.dev.create_client", return_value=sb), \
         patch("backend.src.triggers.blueprints.dev.execute_scoring",
               return_value=fake_result):

        with app.test_client() as c:
            resp = c.post("/api/dev/trigger-scoring",
                          json={"open_mic_id": "om-001"},
                          headers=VALID_AUTH)

    assert resp.status_code == 200
    assert resp.get_json()["result"] == fake_result
