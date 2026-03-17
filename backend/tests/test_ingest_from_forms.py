"""Tests TDD para POST /api/ingest-from-forms (Sprint 11, v0.16.0).

Cobertura (spec forms_batch_ingest_spec):
  - Auth: 401 sin API key
  - Filtrado de open mics sin form configurado
  - Happy path: inserta respuestas nuevas y lanza b2s
  - Mapeo canónico → campos bronze
  - Deduplicación por last_form_ingestion_at
  - Actualización del cursor via RPC
  - Tolerancia a errores por open mic
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

from backend.src.triggers.webhook_listener import app  # noqa: E402

API_KEY = "test-key"
AUTH = {"X-API-KEY": API_KEY, "Content-Type": "application/json"}

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIELD_MAPPING = {
    "Nombre artístico":    "nombre_artistico",
    "Instagram (sin @)":   "instagram",
    "WhatsApp":            "whatsapp",
    "¿Cuántas veces?":     "experiencia",
    "¿Qué fechas?":        "fechas_disponibles",
    "¿Último minuto?":     "backup",
    "¿Show próximo?":      "show_proximo",
    "¿Cómo nos conociste?": "como_nos_conociste",
    "¿Haces humor negro?": None,   # sin mapeo → metadata_extra
}

OPEN_MIC_WITH_FORM = {
    "id": "om-001",
    "proveedor_id": "prov-001",
    "config": {
        "external_form_id": "form-abc123",
        "field_mapping": FIELD_MAPPING,
        "last_form_ingestion_at": "2026-03-01T00:00:00Z",
    },
}

OPEN_MIC_NO_FORM = {
    "id": "om-002",
    "proveedor_id": "prov-002",
    "config": {},
}

OPEN_MIC_SECOND = {
    "id": "om-003",
    "proveedor_id": "prov-003",
    "config": {
        "external_form_id": "form-xyz999",
        "field_mapping": FIELD_MAPPING,
    },
}

# Respuesta nueva (posterior al cursor)
RESPONSE_NEW = {
    "_response_id": "resp-001",
    "_submitted_at": "2026-03-05T10:00:00Z",
    "nombre_artistico":        "Ana García",
    "instagram":               "anagarcia",
    "whatsapp":                "666111222",
    "experiencia":             "Es mi primera vez",
    "fechas_disponibles":      "15-04-26",
    "backup":                  "Sí",
    "show_proximo":            "",
    "como_nos_conociste":      "Instagram",
    "metadata_extra":          {"¿Haces humor negro?": "A veces"},
}

# Respuesta antigua (anterior al cursor)
RESPONSE_OLD = {
    "_response_id": "resp-000",
    "_submitted_at": "2026-02-28T08:00:00Z",
    "nombre_artistico":   "Luis Viejo",
    "instagram":          "luisviejo",
    "whatsapp":           "699000000",
    "metadata_extra":     {},
}


# ---------------------------------------------------------------------------
# Helpers mock Supabase
# ---------------------------------------------------------------------------

def _chain(data):
    m = MagicMock()
    m.execute.return_value = MagicMock(data=data)
    for method in ("eq", "select", "insert", "update", "delete", "order",
                   "single", "limit", "in_", "neq", "not_", "filter"):
        getattr(m, method).return_value = m
    return m


def _make_sb(schema_dispatch: dict):
    """Construye un mock de Supabase client.

    Cachea el mock por nombre de schema para que llamadas múltiples
    a sb.schema('silver') devuelvan el mismo objeto (p. ej. para RPC).
    """
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
    sb._mocks = mocks   # acceso directo en tests
    return sb


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_ingest_from_forms_requires_api_key():
    """401 sin X-API-KEY."""
    with app.test_client() as c:
        resp = c.post("/api/ingest-from-forms",
                      headers={"Content-Type": "application/json"})
    assert resp.status_code == 401


def test_ingest_from_forms_skips_open_mics_without_form():
    """200 con 0 filas si ningún open mic tiene external_form_id configurado."""
    sb = _make_sb({"silver": {"open_mics": _chain([OPEN_MIC_NO_FORM])}})

    with patch("backend.src.triggers.blueprints.ingestion._sb_client", return_value=sb), \
         patch("backend.src.triggers.blueprints.ingestion.run_ingestion_async"):
        with app.test_client() as c:
            resp = c.post("/api/ingest-from-forms", headers=AUTH)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["open_mics_processed"] == 0
    assert data["rows_ingested"] == 0


def test_ingest_from_forms_happy_path():
    """200: inserta respuestas nuevas en bronze y lanza Popen."""
    sb = _make_sb({
        "silver": {"open_mics": _chain([OPEN_MIC_WITH_FORM])},
        "bronze": {"solicitudes": _chain([{"id": "new"}])},
    })

    with patch("backend.src.triggers.blueprints.ingestion._sb_client", return_value=sb), \
         patch("backend.src.triggers.blueprints.ingestion.FormIngestor") as MockIngestor, \
         patch("backend.src.triggers.blueprints.ingestion.run_ingestion_async") as mock_popen:

        mock_inst = MagicMock()
        mock_inst.get_responses.return_value = [RESPONSE_NEW]
        MockIngestor.return_value = mock_inst

        with app.test_client() as c:
            resp = c.post("/api/ingest-from-forms", headers=AUTH)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["open_mics_processed"] == 1
    assert data["rows_ingested"] == 1
    mock_popen.assert_called_once()


def test_ingest_from_forms_maps_canonical_fields_to_bronze():
    """Cada campo canónico llega al campo bronze correcto."""
    sb = _make_sb({
        "silver": {"open_mics": _chain([OPEN_MIC_WITH_FORM])},
        "bronze": {"solicitudes": _chain([{"id": "new"}])},
    })

    with patch("backend.src.triggers.blueprints.ingestion._sb_client", return_value=sb), \
         patch("backend.src.triggers.blueprints.ingestion.FormIngestor") as MockIngestor, \
         patch("backend.src.triggers.blueprints.ingestion.run_ingestion_async"):

        mock_inst = MagicMock()
        mock_inst.get_responses.return_value = [RESPONSE_NEW]
        MockIngestor.return_value = mock_inst

        with app.test_client() as c:
            c.post("/api/ingest-from-forms", headers=AUTH)

    # Acceder al mock bronze después del request (se crea al primer sb.schema("bronze"))
    bronze_chain = sb._mocks["bronze"].from_("solicitudes")
    inserted = bronze_chain.insert.call_args[0][0]
    assert inserted["nombre_raw"]                  == "Ana García"
    assert inserted["instagram_raw"]               == "anagarcia"
    assert inserted["telefono_raw"]                == "666111222"
    assert inserted["experiencia_raw"]             == "Es mi primera vez"
    assert inserted["fechas_seleccionadas_raw"]    == "15-04-26"
    assert inserted["disponibilidad_ultimo_minuto"] == "Sí"
    assert inserted["info_show_cercano"]            == ""
    assert inserted["origen_conocimiento"]          == "Instagram"
    assert inserted["proveedor_id"]                 == OPEN_MIC_WITH_FORM["proveedor_id"]
    assert inserted["open_mic_id"]                  == OPEN_MIC_WITH_FORM["id"]
    # metadata_extra no debe estar en bronze
    assert "metadata_extra" not in inserted
    assert "metadata" not in inserted


def test_ingest_from_forms_deduplication_skips_old_responses():
    """Respuestas con _submitted_at <= last_form_ingestion_at no se insertan."""
    sb = _make_sb({
        "silver": {"open_mics": _chain([OPEN_MIC_WITH_FORM])},
        "bronze": {"solicitudes": _chain([])},
    })

    with patch("backend.src.triggers.blueprints.ingestion._sb_client", return_value=sb), \
         patch("backend.src.triggers.blueprints.ingestion.FormIngestor") as MockIngestor, \
         patch("backend.src.triggers.blueprints.ingestion.run_ingestion_async"):

        mock_inst = MagicMock()
        # Solo respuesta vieja (anterior al cursor 2026-03-01T00:00:00Z)
        mock_inst.get_responses.return_value = [RESPONSE_OLD]
        MockIngestor.return_value = mock_inst

        with app.test_client() as c:
            resp = c.post("/api/ingest-from-forms", headers=AUTH)

    assert resp.status_code == 200
    assert resp.get_json()["rows_ingested"] == 0
    # Verificar que no se intentó insertar nada en bronze
    bronze_chain = sb._mocks["bronze"].from_("solicitudes")
    bronze_chain.insert.assert_not_called()


def test_ingest_from_forms_updates_last_ingestion_timestamp():
    """Llama a update_open_mic_config_keys con el mayor _submitted_at del batch."""
    sb = _make_sb({
        "silver": {"open_mics": _chain([OPEN_MIC_WITH_FORM])},
        "bronze": {"solicitudes": _chain([{"id": "new"}])},
    })

    with patch("backend.src.triggers.blueprints.ingestion._sb_client", return_value=sb), \
         patch("backend.src.triggers.blueprints.ingestion.FormIngestor") as MockIngestor, \
         patch("backend.src.triggers.blueprints.ingestion.run_ingestion_async"):

        mock_inst = MagicMock()
        mock_inst.get_responses.return_value = [RESPONSE_NEW]
        MockIngestor.return_value = mock_inst

        with app.test_client() as c:
            c.post("/api/ingest-from-forms", headers=AUTH)

    silver_mock = sb._mocks["silver"]
    silver_mock.rpc.assert_called_once_with(
        "update_open_mic_config_keys",
        {
            "p_open_mic_id": OPEN_MIC_WITH_FORM["id"],
            "p_keys": {"last_form_ingestion_at": RESPONSE_NEW["_submitted_at"]},
        },
    )


def test_ingest_from_forms_continues_on_form_error():
    """Si get_responses falla en un open mic, continúa con los demás."""
    sb = _make_sb({
        "silver": {"open_mics": _chain([OPEN_MIC_WITH_FORM, OPEN_MIC_SECOND])},
        "bronze": {"solicitudes": _chain([{"id": "new"}])},
    })

    def _responses_side_effect(form_id, field_mapping):
        if form_id == OPEN_MIC_WITH_FORM["config"]["external_form_id"]:
            raise Exception("Google API error")
        return [RESPONSE_NEW]

    with patch("backend.src.triggers.blueprints.ingestion._sb_client", return_value=sb), \
         patch("backend.src.triggers.blueprints.ingestion.FormIngestor") as MockIngestor, \
         patch("backend.src.triggers.blueprints.ingestion.run_ingestion_async"):

        mock_inst = MagicMock()
        mock_inst.get_responses.side_effect = _responses_side_effect
        MockIngestor.return_value = mock_inst

        with app.test_client() as c:
            resp = c.post("/api/ingest-from-forms", headers=AUTH)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["rows_ingested"] == 1        # solo el segundo open mic
    assert data["open_mics_processed"] == 2  # ambos intentados
