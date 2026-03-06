"""Tests TDD para los endpoints /mcp/* del Telegram Lineup Agent.

Fase roja: los endpoints aún no existen en webhook_listener.py.
Estos tests definen el contrato antes de la implementación.

Cobertura (spec §9):
  1. test_get_lineup_returns_slots
  2. test_get_lineup_empty_when_no_slots
  3. test_get_candidates_returns_sorted
  4. test_run_scoring_calls_engine
  5. test_reopen_lineup_calls_reset_rpc
  6. test_list_open_mics_filters_by_host
  7. test_mcp_endpoints_require_api_key
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

# Forzar API key de test antes de importar la app
os.environ.setdefault("WEBHOOK_API_KEY", "test-key")
os.environ.setdefault("SUPABASE_URL", "http://fake-supabase")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-service-key")

from backend.src.triggers.webhook_listener import app  # noqa: E402

OM_ID   = "00000000-0000-0000-0000-000000000001"
HOST_ID = "00000000-0000-0000-0000-000000000002"
FECHA   = "2026-03-20"
API_KEY = "test-key"
AUTH_HEADERS = {"X-API-KEY": API_KEY}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sb_mock(data):
    """Construye un mock de Supabase que devuelve `data` al final de cualquier cadena."""
    result = MagicMock()
    result.data = data

    chain = MagicMock()
    chain.execute.return_value = result
    chain.eq.return_value = chain
    chain.select.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.from_.return_value = chain  # noqa: E501 — Supabase usa from_ (keyword)

    schema = MagicMock()
    schema.from_.return_value = chain

    client = MagicMock()
    client.schema.return_value = schema
    client.rpc.return_value = result
    return client


# ---------------------------------------------------------------------------
# 1. GET /mcp/lineup — lineup confirmado con slots
# ---------------------------------------------------------------------------

def test_get_lineup_returns_slots():
    slots = [
        {"slot_order": 1, "solicitud_id": "sol-1",
         "silver_solicitudes": {"silver_comicos": {"nombre": "Ada Torres", "instagram": "ada"}, "categoria_silver": "priority"}},
    ]
    sb = _sb_mock(slots)

    with patch("backend.src.triggers.webhook_listener.create_client", return_value=sb):
        with app.test_client() as client:
            resp = client.get(
                f"/mcp/lineup?open_mic_id={OM_ID}&fecha_evento={FECHA}",
                headers=AUTH_HEADERS,
            )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["open_mic_id"] == OM_ID
    assert body["fecha_evento"] == FECHA
    assert len(body["slots"]) == 1
    assert body["validado"] is True


# ---------------------------------------------------------------------------
# 2. GET /mcp/lineup — sin slots (lineup no validado)
# ---------------------------------------------------------------------------

def test_get_lineup_empty_when_no_slots():
    sb = _sb_mock([])

    with patch("backend.src.triggers.webhook_listener.create_client", return_value=sb):
        with app.test_client() as client:
            resp = client.get(
                f"/mcp/lineup?open_mic_id={OM_ID}&fecha_evento={FECHA}",
                headers=AUTH_HEADERS,
            )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["slots"] == []
    assert body["total"] == 0
    assert body["validado"] is False


# ---------------------------------------------------------------------------
# 3. GET /mcp/candidates — ordenados por score desc
# ---------------------------------------------------------------------------

def test_get_candidates_returns_sorted():
    candidates = [
        {"nombre": "Ada Torres",  "instagram": "ada",  "score_aplicado": 80, "estado": "scorado", "categoria": "priority"},
        {"nombre": "Bob Ruiz",    "instagram": "bob",  "score_aplicado": 50, "estado": "scorado", "categoria": "standard"},
    ]
    sb = _sb_mock(candidates)

    with patch("backend.src.triggers.webhook_listener.create_client", return_value=sb):
        with app.test_client() as client:
            resp = client.get(
                f"/mcp/candidates?open_mic_id={OM_ID}&limit=10",
                headers=AUTH_HEADERS,
            )

    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["candidates"]) == 2
    assert body["candidates"][0]["score_final"] >= body["candidates"][1]["score_final"]


# ---------------------------------------------------------------------------
# 4. POST /mcp/run-scoring — delega a execute_scoring()
# ---------------------------------------------------------------------------

def test_run_scoring_calls_engine():
    scoring_result = {
        "status": "ok",
        "open_mic_id": OM_ID,
        "filas_procesadas": 5,
        "filas_insertadas_gold": 5,
        "filas_descartadas_restriccion": 0,
        "top_sugeridos": [],
    }

    with patch("backend.src.triggers.webhook_listener.execute_scoring", return_value=scoring_result) as mock_scoring:
        with app.test_client() as client:
            resp = client.post(
                "/mcp/run-scoring",
                json={"open_mic_id": OM_ID},
                headers=AUTH_HEADERS,
            )

    assert resp.status_code == 200
    mock_scoring.assert_called_once_with(OM_ID)
    body = resp.get_json()
    assert body["status"] == "ok"
    assert body["open_mic_id"] == OM_ID


# ---------------------------------------------------------------------------
# 5. POST /mcp/reopen-lineup — llama RPC reset_lineup_slots
# ---------------------------------------------------------------------------

def test_reopen_lineup_calls_reset_rpc():
    sb = _sb_mock(None)

    with patch("backend.src.triggers.webhook_listener.create_client", return_value=sb):
        with app.test_client() as client:
            resp = client.post(
                "/mcp/reopen-lineup",
                json={"open_mic_id": OM_ID, "fecha_evento": FECHA},
                headers=AUTH_HEADERS,
            )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert FECHA in body["message"]
    sb.rpc.assert_called_once_with(
        "reset_lineup_slots",
        {"p_open_mic_id": OM_ID, "p_fecha_evento": FECHA},
    )


# ---------------------------------------------------------------------------
# 6. GET /mcp/open-mics — filtra por host_id
# ---------------------------------------------------------------------------

def test_list_open_mics_filters_by_host():
    PROVEEDOR_ID = "00000000-0000-0000-0000-000000000099"
    members_data = [{"proveedor_id": PROVEEDOR_ID}]
    open_mics_data = [
        {"id": OM_ID, "nombre": "Recova Open Mic", "config": {"info": {"icon": "mic"}}},
    ]

    # La query se hace en dos pasos: organization_members → open_mics
    # Alternamos las respuestas según el orden de llamada a execute()
    call_count = {"n": 0}
    responses = [members_data, open_mics_data]

    def _execute_side_effect():
        result = MagicMock()
        result.data = responses[call_count["n"]]
        call_count["n"] += 1
        return result

    chain = MagicMock()
    chain.execute.side_effect = _execute_side_effect
    chain.eq.return_value = chain
    chain.in_.return_value = chain
    chain.select.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.from_.return_value = chain

    schema = MagicMock()
    schema.from_.return_value = chain

    sb = MagicMock()
    sb.schema.return_value = schema

    with patch("backend.src.triggers.webhook_listener.create_client", return_value=sb):
        with app.test_client() as client:
            resp = client.get(
                f"/mcp/open-mics?host_id={HOST_ID}",
                headers=AUTH_HEADERS,
            )

    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["open_mics"]) == 1
    assert body["open_mics"][0]["id"] == OM_ID


# ---------------------------------------------------------------------------
# 7. Todos los endpoints requieren X-API-KEY
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method,url,payload", [
    ("GET",  f"/mcp/lineup?open_mic_id={OM_ID}&fecha_evento={FECHA}", None),
    ("GET",  f"/mcp/candidates?open_mic_id={OM_ID}",                  None),
    ("POST", "/mcp/run-scoring",   {"open_mic_id": OM_ID}),
    ("POST", "/mcp/reopen-lineup", {"open_mic_id": OM_ID, "fecha_evento": FECHA}),
    ("GET",  f"/mcp/open-mics?host_id={HOST_ID}",                     None),
])
def test_mcp_endpoints_require_api_key(method, url, payload):
    with app.test_client() as client:
        if method == "GET":
            resp = client.get(url)  # sin header de auth
        else:
            resp = client.post(url, json=payload)  # sin header de auth

    assert resp.status_code == 401
