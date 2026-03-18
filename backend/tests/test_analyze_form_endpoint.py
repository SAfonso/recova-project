"""Tests TDD — POST /api/open-mic/analyze-form (Sprint 9, v0.14.0).

Cubre (spec smart_form_ingestion_spec §Endpoint):
  - happy path: 200 con field_mapping y métricas
  - guarda field_mapping en config del open mic via Supabase RPC
  - 400 si faltan parámetros obligatorios
  - 401 sin JWT
  - 422 si Gemini devuelve JSON inválido
  - métricas de cobertura en la respuesta
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("WEBHOOK_API_KEY", "test-key")
os.environ.setdefault("SUPABASE_URL", "http://fake-supabase")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-service-key")
os.environ.setdefault("TELEGRAM_BOT_USERNAME", "recova_bot")
os.environ.setdefault("FRONTEND_URL", "https://recova-project-z5zp.vercel.app")
os.environ.setdefault("GOOGLE_OAUTH_CLIENT_ID", "fake-client-id")
os.environ.setdefault("GOOGLE_OAUTH_CLIENT_SECRET", "fake-client-secret")
os.environ.setdefault("GOOGLE_OAUTH_REFRESH_TOKEN", "fake-refresh-token")
os.environ.setdefault("GEMINI_API_KEY", "fake-gemini-key")

from backend.src.triggers.webhook_listener import app  # noqa: E402

VALID_USER = {"sub": "user-123", "email": "test@test.com"}
AUTH = {"Authorization": "Bearer valid.jwt.token", "Content-Type": "application/json"}

OPEN_MIC_ID = "om-sprint9-uuid"
FORM_ID = "1BxEfoo123"

QUESTIONS = [
    {"question_id": "q001", "title": "Nombre artístico", "kind": "textQuestion"},
    {"question_id": "q002", "title": "Instagram (sin @)", "kind": "textQuestion"},
    {"question_id": "q003", "title": "WhatsApp", "kind": "textQuestion"},
    {"question_id": "q004", "title": "¿Cuántas veces has actuado en un open mic?", "kind": "choiceQuestion"},
    {"question_id": "q005", "title": "¿Qué fechas te vienen bien?", "kind": "textQuestion"},
    {"question_id": "q006", "title": "¿Estarías disponible si nos falla alguien de última hora?", "kind": "choiceQuestion"},
    {"question_id": "q007", "title": "¿Tienes algún show próximo que quieras mencionar?", "kind": "textQuestion"},
    {"question_id": "q008", "title": "¿Cómo nos conociste?", "kind": "textQuestion"},
    {"question_id": "q009", "title": "¿De dónde eres?", "kind": "textQuestion"},
]

FIELD_MAPPING = {
    "Nombre artístico": "nombre_artistico",
    "Instagram (sin @)": "instagram",
    "WhatsApp": "whatsapp",
    "¿Cuántas veces has actuado en un open mic?": "experiencia",
    "¿Qué fechas te vienen bien?": "fechas_disponibles",
    "¿Estarías disponible si nos falla alguien de última hora?": "backup",
    "¿Tienes algún show próximo que quieras mencionar?": "show_proximo",
    "¿Cómo nos conociste?": "como_nos_conociste",
    "¿De dónde eres?": None,
}


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _patch_auth_valid():
    return patch(
        "backend.src.triggers.blueprints.form.require_authenticated_user",
        return_value=(VALID_USER, None),
    )


def _patch_auth_invalid():
    return patch(
        "backend.src.triggers.shared._is_authenticated_user",
        return_value=None,
    )


def _patch_org_member_ok():
    return patch(
        "backend.src.triggers.blueprints.form.require_org_member",
        return_value=None,
    )


# ---------------------------------------------------------------------------
# Helper Supabase mock
# ---------------------------------------------------------------------------

def _make_sb():
    """Mock mínimo de Supabase para el endpoint analyze-form."""
    sb = MagicMock()
    rpc_chain = MagicMock()
    rpc_chain.execute.return_value = MagicMock(data=None, error=None)
    # El endpoint usa sb.schema("silver").rpc(...)
    sb.schema.return_value.rpc.return_value = rpc_chain
    return sb


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_analyze_form_returns_200_with_mapping():
    """Happy path: 200 con field_mapping en la respuesta."""
    sb = _make_sb()

    with _patch_auth_valid(), \
         _patch_org_member_ok(), \
         patch("backend.src.triggers.blueprints.form._sb_client", return_value=sb), \
         patch("backend.src.triggers.blueprints.form.FormIngestor") as MockIngestor, \
         patch("backend.src.triggers.blueprints.form.FormAnalyzer") as MockAnalyzer:

        MockIngestor.return_value.get_form_questions.return_value = QUESTIONS
        MockAnalyzer.return_value.analyze.return_value = FIELD_MAPPING

        with app.test_client() as c:
            resp = c.post(
                "/api/open-mic/analyze-form",
                json={"open_mic_id": OPEN_MIC_ID, "form_id": FORM_ID},
                headers=AUTH,
            )

    assert resp.status_code == 200
    data = resp.get_json()
    assert "field_mapping" in data
    assert data["field_mapping"]["Nombre artístico"] == "nombre_artistico"
    assert data["field_mapping"]["¿De dónde eres?"] is None


def test_analyze_form_saves_to_config():
    """Llama a la RPC update_open_mic_config_keys con field_mapping y external_form_id."""
    sb = _make_sb()

    with _patch_auth_valid(), \
         _patch_org_member_ok(), \
         patch("backend.src.triggers.blueprints.form._sb_client", return_value=sb), \
         patch("backend.src.triggers.blueprints.form.FormIngestor") as MockIngestor, \
         patch("backend.src.triggers.blueprints.form.FormAnalyzer") as MockAnalyzer:

        MockIngestor.return_value.get_form_questions.return_value = QUESTIONS
        MockAnalyzer.return_value.analyze.return_value = FIELD_MAPPING

        with app.test_client() as c:
            c.post(
                "/api/open-mic/analyze-form",
                json={"open_mic_id": OPEN_MIC_ID, "form_id": FORM_ID},
                headers=AUTH,
            )

    sb.schema.assert_called_with("silver")
    silver = sb.schema.return_value
    silver.rpc.assert_called_once()
    rpc_name, rpc_params = silver.rpc.call_args[0][0], silver.rpc.call_args[0][1]
    assert rpc_name == "update_open_mic_config_keys"
    assert rpc_params["p_open_mic_id"] == OPEN_MIC_ID
    assert rpc_params["p_keys"]["field_mapping"] == FIELD_MAPPING
    assert rpc_params["p_keys"]["external_form_id"] == FORM_ID


def test_analyze_form_missing_params_400():
    """400 si falta open_mic_id o form_id."""
    with _patch_auth_valid(), _patch_org_member_ok():
        with app.test_client() as c:
            resp = c.post(
                "/api/open-mic/analyze-form",
                json={"open_mic_id": OPEN_MIC_ID},  # falta form_id
                headers=AUTH,
            )
    assert resp.status_code == 400
    assert "form_id" in resp.get_json()["error"]["message"]


def test_analyze_form_unauthorized_401():
    """401 sin JWT."""
    with _patch_auth_invalid():
        with app.test_client() as c:
            resp = c.post(
                "/api/open-mic/analyze-form",
                json={"open_mic_id": OPEN_MIC_ID, "form_id": FORM_ID},
                headers={"Content-Type": "application/json"},
            )
    assert resp.status_code == 401


def test_analyze_form_gemini_invalid_422():
    """422 si FormAnalyzer lanza ValueError (Gemini devuelve JSON inválido)."""
    sb = _make_sb()

    with _patch_auth_valid(), \
         _patch_org_member_ok(), \
         patch("backend.src.triggers.blueprints.form._sb_client", return_value=sb), \
         patch("backend.src.triggers.blueprints.form.FormIngestor") as MockIngestor, \
         patch("backend.src.triggers.blueprints.form.FormAnalyzer") as MockAnalyzer:

        MockIngestor.return_value.get_form_questions.return_value = QUESTIONS
        MockAnalyzer.return_value.analyze.side_effect = ValueError("Gemini devolvió JSON inválido: {{{")

        with app.test_client() as c:
            resp = c.post(
                "/api/open-mic/analyze-form",
                json={"open_mic_id": OPEN_MIC_ID, "form_id": FORM_ID},
                headers=AUTH,
            )

    assert resp.status_code == 422
    data = resp.get_json()
    assert data["status"] == "error"
    assert data["error"]["code"] == "UNPROCESSABLE_ENTITY"
    assert "inválido" in data["error"]["message"]


def test_analyze_form_includes_coverage_metrics():
    """La respuesta incluye canonical_coverage, total_questions y unmapped_fields."""
    sb = _make_sb()

    with _patch_auth_valid(), \
         _patch_org_member_ok(), \
         patch("backend.src.triggers.blueprints.form._sb_client", return_value=sb), \
         patch("backend.src.triggers.blueprints.form.FormIngestor") as MockIngestor, \
         patch("backend.src.triggers.blueprints.form.FormAnalyzer") as MockAnalyzer:

        MockIngestor.return_value.get_form_questions.return_value = QUESTIONS
        MockAnalyzer.return_value.analyze.return_value = FIELD_MAPPING

        with app.test_client() as c:
            resp = c.post(
                "/api/open-mic/analyze-form",
                json={"open_mic_id": OPEN_MIC_ID, "form_id": FORM_ID},
                headers=AUTH,
            )

    data = resp.get_json()
    assert data["total_questions"] == 9
    assert data["canonical_coverage"] == 8  # 9 preguntas - 1 sin mapeo (¿De dónde eres?)
    assert "¿De dónde eres?" in data["unmapped_fields"]
