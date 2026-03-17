"""Tests TDD — POST /api/open-mic/propose-custom-rules (Sprint 10, v0.15.0).

Cubre (spec custom_scoring_spec §Endpoint):
  - happy path: 200 con reglas propuestas
  - 400 si falta open_mic_id
  - 422 si config no tiene field_mapping
  - 200 con rules:[] si no hay campos no canónicos
  - 422 si Gemini falla
  - guarda rules en config via RPC
  - 401 sin API key
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

API_KEY = "test-key"
AUTH = {"X-API-KEY": API_KEY, "Content-Type": "application/json"}

OPEN_MIC_ID = "om-sprint10-uuid"

# Config con field_mapping que incluye un campo no canónico (null)
CONFIG_WITH_UNMAPPED = {
    "field_mapping": {
        "Nombre artístico": "nombre_artistico",
        "Instagram (sin @)": "instagram",
        "¿Haces humor negro?": None,
    }
}

# Config donde todos los campos son canónicos (sin nulls)
CONFIG_ALL_CANONICAL = {
    "field_mapping": {
        "Nombre artístico": "nombre_artistico",
        "Instagram (sin @)": "instagram",
    }
}

PROPOSED_RULES = [
    {
        "field": "¿Haces humor negro?",
        "condition": "equals",
        "value": "Sí",
        "points": 10,
        "enabled": True,
        "description": "Bono por humor negro",
    }
]


# ---------------------------------------------------------------------------
# Helper Supabase mock
# ---------------------------------------------------------------------------

def _make_sb(config: dict | None = None):
    """Mock de Supabase con config cargable y RPC disponible."""
    sb = MagicMock()

    # Cadena select → single para cargar config del open mic
    select_chain = MagicMock()
    select_chain.execute.return_value = MagicMock(
        data={"config": config} if config is not None else {"config": {}},
        error=None,
    )
    for method in ("eq", "select", "single"):
        getattr(select_chain, method).return_value = select_chain
    sb.schema.return_value.from_.return_value = select_chain

    # RPC para guardar custom_scoring_rules
    rpc_chain = MagicMock()
    rpc_chain.execute.return_value = MagicMock(data=None, error=None)
    sb.schema.return_value.rpc.return_value = rpc_chain

    return sb


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_propose_returns_200_with_rules():
    """Happy path: 200 con lista de reglas propuestas."""
    sb = _make_sb(CONFIG_WITH_UNMAPPED)

    with patch("backend.src.triggers.blueprints.form._sb_client", return_value=sb), \
         patch("backend.src.triggers.blueprints.form.CustomScoringProposer") as MockProposer:

        MockProposer.return_value.propose.return_value = PROPOSED_RULES

        with app.test_client() as c:
            resp = c.post(
                "/api/open-mic/propose-custom-rules",
                json={"open_mic_id": OPEN_MIC_ID},
                headers=AUTH,
            )

    assert resp.status_code == 200
    data = resp.get_json()
    assert "rules" in data
    assert len(data["rules"]) == 1
    assert data["rules"][0]["field"] == "¿Haces humor negro?"


def test_propose_missing_open_mic_id_400():
    """400 si falta open_mic_id."""
    with app.test_client() as c:
        resp = c.post(
            "/api/open-mic/propose-custom-rules",
            json={},
            headers=AUTH,
        )
    assert resp.status_code == 400
    assert "open_mic_id" in resp.get_json()["error"]["message"]


def test_propose_no_field_mapping_422():
    """422 si config del open mic no tiene field_mapping."""
    sb = _make_sb({})  # config sin field_mapping

    with patch("backend.src.triggers.blueprints.form._sb_client", return_value=sb):
        with app.test_client() as c:
            resp = c.post(
                "/api/open-mic/propose-custom-rules",
                json={"open_mic_id": OPEN_MIC_ID},
                headers=AUTH,
            )

    assert resp.status_code == 422
    data = resp.get_json()
    assert data["status"] == "error"
    assert data["error"]["code"] == "UNPROCESSABLE_ENTITY"
    assert "field_mapping" in data["error"]["message"]


def test_propose_no_unmapped_fields_200_empty():
    """200 con rules:[] si todos los campos del form son canónicos."""
    sb = _make_sb(CONFIG_ALL_CANONICAL)

    with patch("backend.src.triggers.blueprints.form._sb_client", return_value=sb), \
         patch("backend.src.triggers.blueprints.form.CustomScoringProposer") as MockProposer:

        MockProposer.return_value.propose.return_value = []

        with app.test_client() as c:
            resp = c.post(
                "/api/open-mic/propose-custom-rules",
                json={"open_mic_id": OPEN_MIC_ID},
                headers=AUTH,
            )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["rules"] == []
    assert data["proposed_count"] == 0


def test_propose_gemini_invalid_422():
    """422 si CustomScoringProposer lanza ValueError."""
    sb = _make_sb(CONFIG_WITH_UNMAPPED)

    with patch("backend.src.triggers.blueprints.form._sb_client", return_value=sb), \
         patch("backend.src.triggers.blueprints.form.CustomScoringProposer") as MockProposer:

        MockProposer.return_value.propose.side_effect = ValueError("Gemini devolvió JSON inválido: {{{")

        with app.test_client() as c:
            resp = c.post(
                "/api/open-mic/propose-custom-rules",
                json={"open_mic_id": OPEN_MIC_ID},
                headers=AUTH,
            )

    assert resp.status_code == 422
    data = resp.get_json()
    assert data["status"] == "error"
    assert data["error"]["code"] == "UNPROCESSABLE_ENTITY"
    assert "inválido" in data["error"]["message"]


def test_propose_saves_rules_to_config():
    """Llama a RPC update_open_mic_config_keys con custom_scoring_rules."""
    sb = _make_sb(CONFIG_WITH_UNMAPPED)

    with patch("backend.src.triggers.blueprints.form._sb_client", return_value=sb), \
         patch("backend.src.triggers.blueprints.form.CustomScoringProposer") as MockProposer:

        MockProposer.return_value.propose.return_value = PROPOSED_RULES

        with app.test_client() as c:
            c.post(
                "/api/open-mic/propose-custom-rules",
                json={"open_mic_id": OPEN_MIC_ID},
                headers=AUTH,
            )

    sb.schema.assert_called_with("silver")
    silver = sb.schema.return_value
    silver.rpc.assert_called_once()
    rpc_name = silver.rpc.call_args[0][0]
    rpc_params = silver.rpc.call_args[0][1]
    assert rpc_name == "update_open_mic_config_keys"
    assert rpc_params["p_open_mic_id"] == OPEN_MIC_ID
    assert rpc_params["p_keys"]["custom_scoring_rules"] == PROPOSED_RULES


def test_propose_unauthorized_401():
    """401 sin API key."""
    with app.test_client() as c:
        resp = c.post(
            "/api/open-mic/propose-custom-rules",
            json={"open_mic_id": OPEN_MIC_ID},
            headers={"Content-Type": "application/json"},
        )
    assert resp.status_code == 401


def test_propose_response_includes_metadata():
    """La respuesta incluye unmapped_fields y proposed_count."""
    sb = _make_sb(CONFIG_WITH_UNMAPPED)

    with patch("backend.src.triggers.blueprints.form._sb_client", return_value=sb), \
         patch("backend.src.triggers.blueprints.form.CustomScoringProposer") as MockProposer:

        MockProposer.return_value.propose.return_value = PROPOSED_RULES

        with app.test_client() as c:
            resp = c.post(
                "/api/open-mic/propose-custom-rules",
                json={"open_mic_id": OPEN_MIC_ID},
                headers=AUTH,
            )

    data = resp.get_json()
    assert "unmapped_fields" in data
    assert "¿Haces humor negro?" in data["unmapped_fields"]
    assert data["proposed_count"] == 1
