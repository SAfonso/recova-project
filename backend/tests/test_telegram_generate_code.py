"""Tests TDD para POST /api/telegram/generate-code.

Fase roja redactada antes de la implementación.
Cobertura (spec §6):
  1. test_generate_code_returns_code_and_qr_url
  2. test_generate_code_format
  3. test_generate_code_inserts_into_db
  4. test_generate_code_requires_api_key
  5. test_generate_code_requires_host_id
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

HOST_ID     = "00000000-0000-0000-0000-000000000099"
API_KEY     = "test-key"
AUTH_HEADERS = {"X-API-KEY": API_KEY, "Content-Type": "application/json"}
ENDPOINT    = "/api/telegram/generate-code"


def _sb_insert_mock():
    """Mock de Supabase que acepta una cadena insert().execute() sin error."""
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[{"code": "RCV-TEST"}])
    chain.insert.return_value = chain

    schema = MagicMock()
    schema.from_.return_value = chain

    client = MagicMock()
    client.schema.return_value = schema
    return client


# ---------------------------------------------------------------------------
# 1. Happy path — 200 con code y qr_url
# ---------------------------------------------------------------------------

def test_generate_code_returns_code_and_qr_url():
    sb = _sb_insert_mock()
    with patch("backend.src.triggers.blueprints.telegram._sb_client", return_value=sb):
        with app.test_client() as client:
            resp = client.post(
                ENDPOINT,
                json={"host_id": HOST_ID},
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
    sb = _sb_insert_mock()
    with patch("backend.src.triggers.blueprints.telegram._sb_client", return_value=sb):
        with app.test_client() as client:
            resp = client.post(
                ENDPOINT,
                json={"host_id": HOST_ID},
                headers=AUTH_HEADERS,
            )

    code = resp.get_json()["code"]
    assert re.fullmatch(r"RCV-[A-Z0-9]{4}", code), f"Formato incorrecto: {code!r}"


# ---------------------------------------------------------------------------
# 3. Side-effect — INSERT en silver.telegram_registration_codes
# ---------------------------------------------------------------------------

def test_generate_code_inserts_into_db():
    sb = _sb_insert_mock()
    with patch("backend.src.triggers.blueprints.telegram._sb_client", return_value=sb):
        with app.test_client() as client:
            resp = client.post(
                ENDPOINT,
                json={"host_id": HOST_ID},
                headers=AUTH_HEADERS,
            )

    assert resp.status_code == 200
    # Verificar que se llamó a schema("silver").from_("telegram_registration_codes").insert(...)
    sb.schema.assert_called_with("silver")
    schema_mock = sb.schema.return_value
    schema_mock.from_.assert_called_with("telegram_registration_codes")
    insert_call_kwargs = schema_mock.from_.return_value.insert.call_args
    inserted = insert_call_kwargs[0][0]  # primer argumento posicional del insert
    assert inserted["host_id"] == HOST_ID
    assert re.fullmatch(r"RCV-[A-Z0-9]{4}", inserted["code"])


# ---------------------------------------------------------------------------
# 4. Auth — sin X-API-KEY → 401
# ---------------------------------------------------------------------------

def test_generate_code_requires_api_key():
    with app.test_client() as client:
        resp = client.post(
            ENDPOINT,
            json={"host_id": HOST_ID},
            headers={"Content-Type": "application/json"},  # sin X-API-KEY
        )

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 5. Validación — host_id ausente → 400
# ---------------------------------------------------------------------------

def test_generate_code_requires_host_id():
    sb = _sb_insert_mock()
    with patch("backend.src.triggers.blueprints.telegram._sb_client", return_value=sb):
        with app.test_client() as client:
            resp = client.post(
                ENDPOINT,
                json={},  # sin host_id
                headers=AUTH_HEADERS,
            )

    assert resp.status_code == 400
    assert "host_id" in resp.get_json()["error"]["message"]
