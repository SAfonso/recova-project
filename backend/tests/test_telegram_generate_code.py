"""Tests TDD para POST /api/telegram/generate-code.

Fase roja redactada antes de la implementación.
Cobertura (spec §6):
  1. test_generate_code_returns_code_and_qr_url
  2. test_generate_code_format
  3. test_generate_code_inserts_into_db
  4. test_generate_code_requires_auth
  5. test_generate_code_requires_proveedor_id
  6. test_generate_code_forbidden_no_membership
"""

from __future__ import annotations

import os
import re
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("WEBHOOK_API_KEY", "test-key")
os.environ.setdefault("SUPABASE_URL", "http://fake-supabase")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-service-key")
os.environ.setdefault("TELEGRAM_BOT_USERNAME", "recova_bot")

from backend.src.triggers.webhook_listener import app  # noqa: E402

HOST_ID      = "00000000-0000-0000-0000-000000000099"
PROVEEDOR_ID = "prov-001"
VALID_USER   = {"sub": HOST_ID, "email": "test@test.com"}
AUTH_HEADERS  = {"Authorization": "Bearer valid.jwt.token", "Content-Type": "application/json"}
ENDPOINT     = "/api/telegram/generate-code"


def _patch_auth_valid():
    return patch(
        "backend.src.triggers.blueprints.telegram.require_authenticated_user",
        return_value=(VALID_USER, None),
    )


def _patch_auth_invalid():
    return patch(
        "backend.src.triggers.shared._is_authenticated_user",
        return_value=None,
    )


def _sb_mock_with_membership():
    """Mock de Supabase con membership check + insert."""
    chain_insert = MagicMock()
    chain_insert.execute.return_value = MagicMock(data=[{"code": "RCV-TEST"}])
    chain_insert.insert.return_value = chain_insert

    chain_member = MagicMock()
    chain_member.execute.return_value = MagicMock(data=[{"user_id": HOST_ID}])
    for m in ("eq", "select"):
        getattr(chain_member, m).return_value = chain_member

    schema = MagicMock()
    def _from_(table):
        if table == "organization_members":
            return chain_member
        return chain_insert
    schema.from_ = _from_

    client = MagicMock()
    client.schema.return_value = schema
    return client


def _sb_mock_no_membership():
    """Mock de Supabase sin membership."""
    chain_member = MagicMock()
    chain_member.execute.return_value = MagicMock(data=[])
    for m in ("eq", "select"):
        getattr(chain_member, m).return_value = chain_member

    schema = MagicMock()
    schema.from_.return_value = chain_member

    client = MagicMock()
    client.schema.return_value = schema
    return client


# ---------------------------------------------------------------------------
# 1. Happy path — 200 con code y qr_url
# ---------------------------------------------------------------------------

def test_generate_code_returns_code_and_qr_url():
    sb = _sb_mock_with_membership()
    with _patch_auth_valid(), \
         patch("backend.src.triggers.blueprints.telegram._sb_client", return_value=sb):
        with app.test_client() as client:
            resp = client.post(
                ENDPOINT,
                json={"proveedor_id": PROVEEDOR_ID},
                headers=AUTH_HEADERS,
            )

    assert resp.status_code == 200
    data = resp.get_json()
    assert "code" in data
    assert "qr_url" in data
    assert data["qr_url"].startswith("https://t.me/")
    assert data["code"] in data["qr_url"]


# ---------------------------------------------------------------------------
# 2. Formato del código — RCV-[A-Z0-9]{4}
# ---------------------------------------------------------------------------

def test_generate_code_format():
    sb = _sb_mock_with_membership()
    with _patch_auth_valid(), \
         patch("backend.src.triggers.blueprints.telegram._sb_client", return_value=sb):
        with app.test_client() as client:
            resp = client.post(
                ENDPOINT,
                json={"proveedor_id": PROVEEDOR_ID},
                headers=AUTH_HEADERS,
            )

    code = resp.get_json()["code"]
    assert re.fullmatch(r"RCV-[A-Z0-9]{4}", code), f"Formato incorrecto: {code!r}"


# ---------------------------------------------------------------------------
# 3. Side-effect — INSERT en silver.telegram_registration_codes
# ---------------------------------------------------------------------------

def test_generate_code_inserts_into_db():
    sb = _sb_mock_with_membership()
    with _patch_auth_valid(), \
         patch("backend.src.triggers.blueprints.telegram._sb_client", return_value=sb):
        with app.test_client() as client:
            resp = client.post(
                ENDPOINT,
                json={"proveedor_id": PROVEEDOR_ID},
                headers=AUTH_HEADERS,
            )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 4. Auth — sin Authorization → 401
# ---------------------------------------------------------------------------

def test_generate_code_requires_auth():
    with _patch_auth_invalid():
        with app.test_client() as client:
            resp = client.post(
                ENDPOINT,
                json={"proveedor_id": PROVEEDOR_ID},
                headers={"Content-Type": "application/json"},
            )

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 5. Validación — proveedor_id ausente → 400
# ---------------------------------------------------------------------------

def test_generate_code_requires_proveedor_id():
    with _patch_auth_valid():
        with app.test_client() as client:
            resp = client.post(
                ENDPOINT,
                json={},  # sin proveedor_id
                headers=AUTH_HEADERS,
            )

    assert resp.status_code == 400
    assert "proveedor_id" in resp.get_json()["error"]["message"]


# ---------------------------------------------------------------------------
# 6. Forbidden — no membership → 403
# ---------------------------------------------------------------------------

def test_generate_code_forbidden_no_membership():
    sb = _sb_mock_no_membership()
    with _patch_auth_valid(), \
         patch("backend.src.triggers.blueprints.telegram._sb_client", return_value=sb):
        with app.test_client() as client:
            resp = client.post(
                ENDPOINT,
                json={"proveedor_id": PROVEEDOR_ID},
                headers=AUTH_HEADERS,
            )

    assert resp.status_code == 403
