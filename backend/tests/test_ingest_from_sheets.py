"""Tests TDD para SheetIngestor y POST /api/ingest-from-sheets.

Cobertura (spec ingest_from_sheets_spec §Tests):
  SheetIngestor.get_pending_rows
  SheetIngestor.mark_rows_processed
  POST /api/ingest-from-sheets
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, call, patch

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

OPEN_MIC_1 = {
    "id": "om-0001",
    "proveedor_id": "prov-0001",
    "config": {"form": {"sheet_id": "sheet-aaa"}},
}
OPEN_MIC_2 = {
    "id": "om-0002",
    "proveedor_id": "prov-0002",
    "config": {"form": {"sheet_id": "sheet-bbb"}},
}

# Simula respuesta de Sheets API v4 (spreadsheets.values.get)
HEADERS = [
    "Marca temporal", "Nombre artístico", "Instagram (sin @)", "WhatsApp",
    "¿Cuántas veces has actuado en un open mic?", "¿Qué fechas te vienen bien?",
    "¿Estarías disponible si nos falla alguien de última hora?",
    "¿Tienes algún show próximo que quieras mencionar?", "¿Cómo nos conociste?",
    "open_mic_id", "n8n_procesado",
]

def _make_sheet_row(nombre, procesado=""):
    return [
        "2026-03-06 10:00:00", nombre, "@insta", "612000000",
        "Es mi primera vez", "2026-03-15", "Sí", "", "Instagram",
        "om-0001", procesado,
    ]

SHEET_VALUES_PENDING = {
    "values": [
        HEADERS,
        _make_sheet_row("Ana López"),    # pendiente
        _make_sheet_row("Luis Pérez", procesado="si"),  # ya procesado
        _make_sheet_row("María Sanz"),   # pendiente
    ]
}

SHEET_VALUES_ALL_PROCESSED = {
    "values": [
        HEADERS,
        _make_sheet_row("Ana López", procesado="si"),
    ]
}

SHEET_VALUES_EMPTY = {
    "values": [HEADERS]
}


# ---------------------------------------------------------------------------
# Helpers de mock Supabase (mismo patrón del proyecto)
# ---------------------------------------------------------------------------

def _chain(data):
    m = MagicMock()
    m.execute.return_value = MagicMock(data=data)
    for method in ("eq", "select", "insert", "update", "delete", "order",
                   "single", "limit", "in_", "neq", "not_", "filter"):
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
        return mock

    sb = MagicMock()
    sb.schema.side_effect = _schema
    return sb


# ---------------------------------------------------------------------------
# SheetIngestor.get_pending_rows
# ---------------------------------------------------------------------------

def _make_sheets_service(values_response):
    """Mock del cliente de Google Sheets API."""
    sheets_svc = MagicMock()
    (sheets_svc.spreadsheets().values()
     .get().execute.return_value) = values_response
    return sheets_svc


def test_get_pending_rows_empty_sheet():
    """Sheet sin filas de datos devuelve lista vacía."""
    from backend.src.core.sheet_ingestor import SheetIngestor

    ingestor = SheetIngestor.__new__(SheetIngestor)
    ingestor._sheets = _make_sheets_service(SHEET_VALUES_EMPTY)

    result = ingestor.get_pending_rows("sheet-id")
    assert result == []


def test_get_pending_rows_excludes_processed():
    """Filas con n8n_procesado='si' no se incluyen."""
    from backend.src.core.sheet_ingestor import SheetIngestor

    ingestor = SheetIngestor.__new__(SheetIngestor)
    ingestor._sheets = _make_sheets_service(SHEET_VALUES_ALL_PROCESSED)

    result = ingestor.get_pending_rows("sheet-id")
    assert result == []


def test_get_pending_rows_returns_pending_only():
    """Solo devuelve filas con n8n_procesado vacío."""
    from backend.src.core.sheet_ingestor import SheetIngestor

    ingestor = SheetIngestor.__new__(SheetIngestor)
    ingestor._sheets = _make_sheets_service(SHEET_VALUES_PENDING)

    result = ingestor.get_pending_rows("sheet-id")
    assert len(result) == 2
    nombres = {r["Nombre artístico"] for r in result}
    assert nombres == {"Ana López", "María Sanz"}


def test_get_pending_rows_row_numbers():
    """_row_number es 1-based e ignora la fila de cabecera."""
    from backend.src.core.sheet_ingestor import SheetIngestor

    ingestor = SheetIngestor.__new__(SheetIngestor)
    ingestor._sheets = _make_sheets_service(SHEET_VALUES_PENDING)

    result = ingestor.get_pending_rows("sheet-id")
    # Row 1 = headers, Row 2 = Ana (pendiente), Row 3 = Luis (procesado), Row 4 = María (pendiente)
    row_numbers = {r["_row_number"] for r in result}
    assert row_numbers == {2, 4}


def test_get_pending_rows_includes_all_fields():
    """Cada fila pendiente tiene todos los campos mapeados por cabecera."""
    from backend.src.core.sheet_ingestor import SheetIngestor

    ingestor = SheetIngestor.__new__(SheetIngestor)
    ingestor._sheets = _make_sheets_service({
        "values": [HEADERS, _make_sheet_row("Carlos Ruiz")]
    })

    result = ingestor.get_pending_rows("sheet-id")
    assert len(result) == 1
    row = result[0]
    assert row["Nombre artístico"] == "Carlos Ruiz"
    assert row["Instagram (sin @)"] == "@insta"
    assert row["WhatsApp"] == "612000000"
    assert row["open_mic_id"] == "om-0001"
    assert row["_row_number"] == 2


# ---------------------------------------------------------------------------
# SheetIngestor.mark_rows_processed
# ---------------------------------------------------------------------------

def test_mark_rows_processed_calls_batch_update():
    """Llama a batchUpdate con 'si' en columna K para cada fila."""
    from backend.src.core.sheet_ingestor import SheetIngestor

    sheets_svc = MagicMock()
    ingestor = SheetIngestor.__new__(SheetIngestor)
    ingestor._sheets = sheets_svc

    ingestor.mark_rows_processed("sheet-xyz", [2, 4])

    batch_update = sheets_svc.spreadsheets().values().batchUpdate
    batch_update.assert_called_once()
    call_kwargs = batch_update.call_args[1]
    assert call_kwargs["spreadsheetId"] == "sheet-xyz"
    data = call_kwargs["body"]["data"]
    ranges = {d["range"] for d in data}
    assert "K2" in ranges
    assert "K4" in ranges
    for d in data:
        assert d["values"] == [["si"]]


def test_mark_rows_processed_empty_list():
    """Con lista vacía no llama a batchUpdate."""
    from backend.src.core.sheet_ingestor import SheetIngestor

    sheets_svc = MagicMock()
    ingestor = SheetIngestor.__new__(SheetIngestor)
    ingestor._sheets = sheets_svc

    ingestor.mark_rows_processed("sheet-xyz", [])

    sheets_svc.spreadsheets().values().batchUpdate.assert_not_called()


# ---------------------------------------------------------------------------
# POST /api/ingest-from-sheets
# ---------------------------------------------------------------------------

def test_ingest_from_sheets_requires_api_key():
    """401 sin API key."""
    with app.test_client() as c:
        resp = c.post("/api/ingest-from-sheets",
                      headers={"Content-Type": "application/json"})
    assert resp.status_code == 401


def test_ingest_from_sheets_no_open_mics():
    """200 con rows_ingested=0 si no hay open mics con Sheet."""
    sb = _make_sb({"silver": {"open_mics": _chain([])}})

    with patch("backend.src.triggers.webhook_listener.create_client", return_value=sb):
        with app.test_client() as c:
            resp = c.post("/api/ingest-from-sheets", headers=AUTH)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["rows_ingested"] == 0
    assert data["open_mics_processed"] == 0


def test_ingest_from_sheets_happy_path():
    """200: inserta filas pendientes de todos los open mics y lanza ingesta."""
    sb = _make_sb({
        "silver": {"open_mics": _chain([OPEN_MIC_1, OPEN_MIC_2])},
        "bronze": {"solicitudes": _chain([{"id": "new"}])},
    })

    # open_mic_1: 2 filas pendientes; open_mic_2: 0 filas pendientes
    def _mock_get_pending(sheet_id):
        if sheet_id == "sheet-aaa":
            return [
                {**dict(zip(HEADERS, _make_sheet_row("Ana López"))), "_row_number": 2},
                {**dict(zip(HEADERS, _make_sheet_row("Luis Pérez"))), "_row_number": 3},
            ]
        return []

    with patch("backend.src.triggers.webhook_listener.create_client", return_value=sb), \
         patch("backend.src.triggers.webhook_listener.SheetIngestor") as MockIngestor, \
         patch("backend.src.triggers.webhook_listener.subprocess.Popen") as mock_popen:

        mock_inst = MagicMock()
        mock_inst.get_pending_rows.side_effect = _mock_get_pending
        MockIngestor.return_value = mock_inst

        with app.test_client() as c:
            resp = c.post("/api/ingest-from-sheets", headers=AUTH)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["rows_ingested"] == 2
    assert data["open_mics_processed"] == 2
    mock_popen.assert_called_once()
    mock_inst.mark_rows_processed.assert_called_once_with("sheet-aaa", [2, 3])


def test_ingest_from_sheets_inserts_correct_fields():
    """Los campos se mapean correctamente a bronze.solicitudes."""
    sb = _make_sb({
        "silver": {"open_mics": _chain([OPEN_MIC_1])},
        "bronze": {"solicitudes": _chain([{"id": "new"}])},
    })
    bronze_chain = sb.schema("bronze").from_("solicitudes")

    pending_row = {**dict(zip(HEADERS, _make_sheet_row("Teresa Gil"))), "_row_number": 2}

    with patch("backend.src.triggers.webhook_listener.create_client", return_value=sb), \
         patch("backend.src.triggers.webhook_listener.SheetIngestor") as MockIngestor, \
         patch("backend.src.triggers.webhook_listener.subprocess.Popen"):

        mock_inst = MagicMock()
        mock_inst.get_pending_rows.return_value = [pending_row]
        MockIngestor.return_value = mock_inst

        with app.test_client() as c:
            c.post("/api/ingest-from-sheets", headers=AUTH)

    inserted = bronze_chain.insert.call_args[0][0]
    assert inserted["nombre_raw"] == "Teresa Gil"
    assert inserted["proveedor_id"] == OPEN_MIC_1["proveedor_id"]
    assert inserted["open_mic_id"] == OPEN_MIC_1["id"]
    assert inserted["instagram_raw"] == "@insta"
    assert inserted["telefono_raw"] == "612000000"


def test_ingest_from_sheets_continues_on_sheet_error():
    """Si una Sheet falla, continúa con las demás y devuelve 200."""
    sb = _make_sb({
        "silver": {"open_mics": _chain([OPEN_MIC_1, OPEN_MIC_2])},
        "bronze": {"solicitudes": _chain([{"id": "new"}])},
    })

    def _mock_get_pending(sheet_id):
        if sheet_id == "sheet-aaa":
            raise Exception("Google API error")
        return [{**dict(zip(HEADERS, _make_sheet_row("Luis Pérez"))), "_row_number": 2}]

    with patch("backend.src.triggers.webhook_listener.create_client", return_value=sb), \
         patch("backend.src.triggers.webhook_listener.SheetIngestor") as MockIngestor, \
         patch("backend.src.triggers.webhook_listener.subprocess.Popen"):

        mock_inst = MagicMock()
        mock_inst.get_pending_rows.side_effect = _mock_get_pending
        MockIngestor.return_value = mock_inst

        with app.test_client() as c:
            resp = c.post("/api/ingest-from-sheets", headers=AUTH)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["rows_ingested"] == 1  # solo el open mic 2
