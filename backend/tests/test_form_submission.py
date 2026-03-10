"""Tests TDD para el endpoint POST /api/form-submission.

Endpoint cubierto (spec ingesta_multitenant_spec §2):
  POST /api/form-submission
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("WEBHOOK_API_KEY", "test-key")
os.environ.setdefault("SUPABASE_URL", "http://fake-supabase")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-service-key")
os.environ.setdefault("TELEGRAM_BOT_USERNAME", "recova_bot")
os.environ.setdefault("FRONTEND_URL", "https://recova-project-z5zp.vercel.app")

from backend.src.triggers.webhook_listener import app  # noqa: E402

OPEN_MIC_ID = "aaaaaaaa-0000-0000-0000-000000000001"
PROVEEDOR_ID = "10000000-0000-0000-0000-000000000001"

OPEN_MIC_ROW = {"id": OPEN_MIC_ID, "proveedor_id": PROVEEDOR_ID}

VALID_PAYLOAD = {
    "open_mic_id": OPEN_MIC_ID,
    "Nombre artístico": "Juan García",
    "Instagram (sin @)": "@juangarcia",
    "WhatsApp": "612345678",
    "¿Cuántas veces has actuado en un open mic?": "Sí, varias veces",
    "¿Qué fechas te vienen bien?": "2026-03-15",
    "¿Estarías disponible si nos falla alguien de última hora?": "Sí",
    "¿Tienes algún show próximo que quieras mencionar?": "",
    "¿Cómo nos conociste?": "Instagram",
}


# ---------------------------------------------------------------------------
# Helpers de mock (mismo patrón que el resto de tests)
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
    def _schema(name):
        mock = MagicMock()
        dispatch = schema_dispatch.get(name, {})
        if callable(dispatch):
            mock.from_.side_effect = dispatch
        else:
            mock.from_.side_effect = lambda t: dispatch.get(t, _chain([]))
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
    return sb


# ---------------------------------------------------------------------------
# POST /api/form-submission
# ---------------------------------------------------------------------------

def test_form_submission_happy_path():
    """200: inserta en bronze y lanza ingesta."""
    sb = _make_sb({
        "silver": {"open_mics": _chain([OPEN_MIC_ROW])},
        "bronze": {"solicitudes": _chain([{"id": "new-id"}])},
    })

    with patch("backend.src.triggers.webhook_listener.create_client", return_value=sb), \
         patch("backend.src.triggers.webhook_listener.subprocess.Popen") as mock_popen:
        with app.test_client() as c:
            resp = c.post("/api/form-submission",
                          json=VALID_PAYLOAD,
                          headers={"Content-Type": "application/json", "X-API-Key": "test-key"})

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"
    mock_popen.assert_called_once()


def test_form_submission_unauthorized():
    """401 si falta el header X-API-Key."""
    with app.test_client() as c:
        resp = c.post("/api/form-submission",
                      json=VALID_PAYLOAD,
                      headers={"Content-Type": "application/json"})

    assert resp.status_code == 401


def test_form_submission_missing_open_mic_id():
    """400 si falta open_mic_id en el payload."""
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "open_mic_id"}

    with app.test_client() as c:
        resp = c.post("/api/form-submission",
                      json=payload,
                      headers={"Content-Type": "application/json", "X-API-Key": "test-key"})

    assert resp.status_code == 400


def test_form_submission_open_mic_not_found():
    """404 si el open_mic_id no existe en silver.open_mics."""
    sb = _make_sb({
        "silver": {"open_mics": _chain([])},  # no rows
    })

    with patch("backend.src.triggers.webhook_listener.create_client", return_value=sb):
        with app.test_client() as c:
            resp = c.post("/api/form-submission",
                          json={**VALID_PAYLOAD, "open_mic_id": "nonexistent-uuid"},
                          headers={"Content-Type": "application/json", "X-API-Key": "test-key"})

    assert resp.status_code == 404


def test_form_submission_inserts_correct_proveedor_id():
    """El proveedor_id insertado en bronze viene del open mic, no hardcodeado."""
    bronze_chain = _chain([{"id": "new-id"}])
    sb = _make_sb({
        "silver": {"open_mics": _chain([OPEN_MIC_ROW])},
        "bronze": {"solicitudes": bronze_chain},
    })

    with patch("backend.src.triggers.webhook_listener.create_client", return_value=sb), \
         patch("backend.src.triggers.webhook_listener.subprocess.Popen"):
        with app.test_client() as c:
            c.post("/api/form-submission",
                   json=VALID_PAYLOAD,
                   headers={"Content-Type": "application/json", "X-API-Key": "test-key"})

    # Verificar que el insert se llamó con el proveedor_id correcto
    insert_call_args = bronze_chain.insert.call_args
    assert insert_call_args is not None
    inserted_data = insert_call_args[0][0]
    assert inserted_data["proveedor_id"] == PROVEEDOR_ID
    assert inserted_data["open_mic_id"] == OPEN_MIC_ID


def test_form_submission_maps_form_fields():
    """Los campos del form se mapean correctamente a las columnas de bronze."""
    bronze_chain = _chain([{"id": "new-id"}])
    sb = _make_sb({
        "silver": {"open_mics": _chain([OPEN_MIC_ROW])},
        "bronze": {"solicitudes": bronze_chain},
    })

    with patch("backend.src.triggers.webhook_listener.create_client", return_value=sb), \
         patch("backend.src.triggers.webhook_listener.subprocess.Popen"):
        with app.test_client() as c:
            c.post("/api/form-submission",
                   json=VALID_PAYLOAD,
                   headers={"Content-Type": "application/json", "X-API-Key": "test-key"})

    inserted_data = bronze_chain.insert.call_args[0][0]
    assert inserted_data["nombre_raw"] == "Juan García"
    assert inserted_data["instagram_raw"] == "@juangarcia"
    assert inserted_data["telefono_raw"] == "612345678"
    assert inserted_data["fechas_seleccionadas_raw"] == "2026-03-15"
    assert inserted_data["origen_conocimiento"] == "Instagram"
    assert inserted_data["experiencia_raw"] == "Sí, varias veces"
    assert inserted_data["disponibilidad_ultimo_minuto"] == "Sí"


def test_form_submission_optional_fields_default_none():
    """Campos opcionales ausentes del payload se insertan como None."""
    payload_minimal = {
        "open_mic_id": OPEN_MIC_ID,
        "Nombre artístico": "María Sanz",
    }
    bronze_chain = _chain([{"id": "new-id"}])
    sb = _make_sb({
        "silver": {"open_mics": _chain([OPEN_MIC_ROW])},
        "bronze": {"solicitudes": bronze_chain},
    })

    with patch("backend.src.triggers.webhook_listener.create_client", return_value=sb), \
         patch("backend.src.triggers.webhook_listener.subprocess.Popen"):
        with app.test_client() as c:
            resp = c.post("/api/form-submission",
                          json=payload_minimal,
                          headers={"Content-Type": "application/json", "X-API-Key": "test-key"})

    assert resp.status_code == 200
    inserted_data = bronze_chain.insert.call_args[0][0]
    assert inserted_data["nombre_raw"] == "María Sanz"
    assert inserted_data["instagram_raw"] is None
    assert inserted_data["telefono_raw"] is None
    assert inserted_data["experiencia_raw"] is None
    assert inserted_data["fechas_seleccionadas_raw"] is None
    assert inserted_data["disponibilidad_ultimo_minuto"] is None
    assert inserted_data["info_show_cercano"] is None
    assert inserted_data["origen_conocimiento"] is None


def test_form_submission_ingesta_launched_with_ingest_script():
    """subprocess.Popen se llama con el path del script de ingesta."""
    sb = _make_sb({
        "silver": {"open_mics": _chain([OPEN_MIC_ROW])},
        "bronze": {"solicitudes": _chain([{"id": "new-id"}])},
    })

    with patch("backend.src.triggers.webhook_listener.create_client", return_value=sb), \
         patch("backend.src.triggers.webhook_listener.subprocess.Popen") as mock_popen:
        with app.test_client() as c:
            c.post("/api/form-submission",
                   json=VALID_PAYLOAD,
                   headers={"Content-Type": "application/json", "X-API-Key": "test-key"})

    args = mock_popen.call_args[0][0]  # primer argumento posicional (lista del comando)
    assert any("ingestion" in str(a) or "ingest" in str(a) for a in args)
