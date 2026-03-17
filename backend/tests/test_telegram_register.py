"""Tests TDD para POST /api/telegram/register.

Fase roja redactada antes de la implementacion.
Cobertura (spec §5):
  1.  test_register_happy_path
  2.  test_register_already_registered_code_unused
  3.  test_register_already_registered_code_used
  4.  test_register_already_registered_code_expired
  5.  test_register_code_not_found
  6.  test_register_code_already_used
  7.  test_register_code_expired
  8.  test_register_requires_api_key
  9.  test_register_missing_telegram_user_id
  10. test_register_missing_code
"""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, call, patch

import pytest

os.environ.setdefault("WEBHOOK_API_KEY", "test-key")
os.environ.setdefault("SUPABASE_URL", "http://fake-supabase")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-service-key")
os.environ.setdefault("TELEGRAM_BOT_USERNAME", "recova_bot")

from backend.src.triggers.webhook_listener import app  # noqa: E402

ENDPOINT = "/api/telegram/register"
API_KEY = "test-key"
AUTH_HEADERS = {"X-API-KEY": API_KEY, "Content-Type": "application/json"}

TELEGRAM_USER_ID = 123456789
HOST_ID = "00000000-0000-0000-0000-000000000099"
CODE = "RCV-A3X9"

FUTURE = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
PAST = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()


# ---------------------------------------------------------------------------
# Helpers para construir mocks de Supabase
# ---------------------------------------------------------------------------

def _make_sb(code_row=None, user_row=None):
    """
    Construye un mock de Supabase client con dos consultas encadenables:
      - schema("silver").from_("telegram_registration_codes").select(...).eq(...).execute()
      - schema("silver").from_("telegram_users").select(...).eq(...).execute()
      - schema("silver").from_("telegram_users").insert(...).execute()
      - schema("silver").from_("telegram_registration_codes").update(...).eq(...).execute()

    code_row: dict con campos del codigo, o None para simular no encontrado
    user_row: dict con campos del usuario, o None para simular no registrado
    """

    def _chain(data):
        m = MagicMock()
        m.execute.return_value = MagicMock(data=data)
        m.eq.return_value = m
        m.select.return_value = m
        m.insert.return_value = m
        m.update.return_value = m
        return m

    code_chain = _chain([code_row] if code_row else [])
    user_chain = _chain([user_row] if user_row else [])
    insert_chain = _chain([{"telegram_user_id": TELEGRAM_USER_ID}])
    update_chain = _chain([{"code": CODE}])

    call_count = {"n": 0}

    def from_(table):
        # Las llamadas llegan en este orden segun la logica del endpoint:
        # 1. telegram_registration_codes (SELECT codigo)
        # 2. telegram_users              (SELECT usuario)
        # 3. telegram_users              (INSERT — solo si no estaba registrado)
        # 4. telegram_registration_codes (UPDATE used=true)
        call_count["n"] += 1
        n = call_count["n"]
        if table == "telegram_registration_codes" and n == 1:
            return code_chain
        if table == "telegram_users" and n == 2:
            return user_chain
        if table == "telegram_users" and n == 3:
            return insert_chain
        if table == "telegram_registration_codes" and n >= 3:
            return update_chain
        return MagicMock()

    schema_mock = MagicMock()
    schema_mock.from_.side_effect = from_

    client = MagicMock()
    client.schema.return_value = schema_mock
    return client, schema_mock, update_chain, insert_chain


def _code_row(used=False, expires_at=None):
    return {
        "code": CODE,
        "host_id": HOST_ID,
        "used": used,
        "expires_at": expires_at or FUTURE,
    }


def _user_row():
    return {"telegram_user_id": TELEGRAM_USER_ID, "host_id": HOST_ID}


# ---------------------------------------------------------------------------
# 1. Happy path — registro nuevo
# ---------------------------------------------------------------------------

def test_register_happy_path():
    sb, schema_mock, update_chain, insert_chain = _make_sb(
        code_row=_code_row(), user_row=None
    )
    with patch("backend.src.triggers.blueprints.telegram._sb_client", return_value=sb):
        with app.test_client() as client:
            resp = client.post(
                ENDPOINT,
                json={"telegram_user_id": TELEGRAM_USER_ID, "code": CODE},
                headers=AUTH_HEADERS,
            )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["host_id"] == HOST_ID
    assert data["already_registered"] is False
    # INSERT llamado
    insert_chain.insert.assert_called_once()
    # UPDATE used=true llamado
    update_chain.update.assert_called_once()


# ---------------------------------------------------------------------------
# 2. Ya registrado + codigo no usado → 200, UPDATE used, already_registered=true
# ---------------------------------------------------------------------------

def test_register_already_registered_code_unused():
    sb, schema_mock, update_chain, insert_chain = _make_sb(
        code_row=_code_row(used=False), user_row=_user_row()
    )
    with patch("backend.src.triggers.blueprints.telegram._sb_client", return_value=sb):
        with app.test_client() as client:
            resp = client.post(
                ENDPOINT,
                json={"telegram_user_id": TELEGRAM_USER_ID, "code": CODE},
                headers=AUTH_HEADERS,
            )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["already_registered"] is True
    assert data["host_id"] == HOST_ID
    # No debe hacer INSERT en telegram_users
    insert_chain.insert.assert_not_called()
    # Debe marcar el codigo como usado
    update_chain.update.assert_called_once()


# ---------------------------------------------------------------------------
# 3. Ya registrado + codigo ya usado → 200, sin UPDATE, already_registered=true
# ---------------------------------------------------------------------------

def test_register_already_registered_code_used():
    sb, schema_mock, update_chain, insert_chain = _make_sb(
        code_row=_code_row(used=True), user_row=_user_row()
    )
    with patch("backend.src.triggers.blueprints.telegram._sb_client", return_value=sb):
        with app.test_client() as client:
            resp = client.post(
                ENDPOINT,
                json={"telegram_user_id": TELEGRAM_USER_ID, "code": CODE},
                headers=AUTH_HEADERS,
            )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["already_registered"] is True
    insert_chain.insert.assert_not_called()
    update_chain.update.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Ya registrado + codigo expirado → 200, already_registered=true
# ---------------------------------------------------------------------------

def test_register_already_registered_code_expired():
    sb, schema_mock, update_chain, insert_chain = _make_sb(
        code_row=_code_row(used=False, expires_at=PAST), user_row=_user_row()
    )
    with patch("backend.src.triggers.blueprints.telegram._sb_client", return_value=sb):
        with app.test_client() as client:
            resp = client.post(
                ENDPOINT,
                json={"telegram_user_id": TELEGRAM_USER_ID, "code": CODE},
                headers=AUTH_HEADERS,
            )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["already_registered"] is True
    insert_chain.insert.assert_not_called()


# ---------------------------------------------------------------------------
# 5. Codigo no encontrado → 404
# ---------------------------------------------------------------------------

def test_register_code_not_found():
    sb, *_ = _make_sb(code_row=None, user_row=None)
    with patch("backend.src.triggers.blueprints.telegram._sb_client", return_value=sb):
        with app.test_client() as client:
            resp = client.post(
                ENDPOINT,
                json={"telegram_user_id": TELEGRAM_USER_ID, "code": "RCV-XXXX"},
                headers=AUTH_HEADERS,
            )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 6. Codigo ya usado + usuario NO registrado → 409
# ---------------------------------------------------------------------------

def test_register_code_already_used():
    sb, *_ = _make_sb(code_row=_code_row(used=True), user_row=None)
    with patch("backend.src.triggers.blueprints.telegram._sb_client", return_value=sb):
        with app.test_client() as client:
            resp = client.post(
                ENDPOINT,
                json={"telegram_user_id": TELEGRAM_USER_ID, "code": CODE},
                headers=AUTH_HEADERS,
            )

    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# 7. Codigo expirado + usuario NO registrado → 410
# ---------------------------------------------------------------------------

def test_register_code_expired():
    sb, *_ = _make_sb(code_row=_code_row(used=False, expires_at=PAST), user_row=None)
    with patch("backend.src.triggers.blueprints.telegram._sb_client", return_value=sb):
        with app.test_client() as client:
            resp = client.post(
                ENDPOINT,
                json={"telegram_user_id": TELEGRAM_USER_ID, "code": CODE},
                headers=AUTH_HEADERS,
            )

    assert resp.status_code == 410


# ---------------------------------------------------------------------------
# 8. Sin X-API-KEY → 401
# ---------------------------------------------------------------------------

def test_register_requires_api_key():
    with app.test_client() as client:
        resp = client.post(
            ENDPOINT,
            json={"telegram_user_id": TELEGRAM_USER_ID, "code": CODE},
            headers={"Content-Type": "application/json"},
        )

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 9. Body sin telegram_user_id → 400
# ---------------------------------------------------------------------------

def test_register_missing_telegram_user_id():
    with app.test_client() as client:
        resp = client.post(
            ENDPOINT,
            json={"code": CODE},
            headers=AUTH_HEADERS,
        )

    assert resp.status_code == 400
    assert "telegram_user_id" in resp.get_json().get("message", "")


# ---------------------------------------------------------------------------
# 10. Body sin code → 400
# ---------------------------------------------------------------------------

def test_register_missing_code():
    with app.test_client() as client:
        resp = client.post(
            ENDPOINT,
            json={"telegram_user_id": TELEGRAM_USER_ID},
            headers=AUTH_HEADERS,
        )

    assert resp.status_code == 400
    assert "code" in resp.get_json().get("message", "")
