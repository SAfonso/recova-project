"""Tests unitarios de GoogleFormBuilder.

Mockea completamente las Google APIs (Forms, Sheets, Drive) y la capa
de autenticación OAuth2 para que los tests no necesiten credenciales reales.

Cubre:
- __init__: falla si faltan env vars; construye clientes si están presentes
- _create_form: llama a forms().create() con el título correcto
- _add_questions: llama a forms().batchUpdate() con 8 preguntas
- _build_item: estructura correcta para textQuestion y choiceQuestion
- _get_linked_sheet_id: devuelve linkedSheetId si existe; crea Sheet si no
- _inject_open_mic_id_column: escribe cabecera y ARRAYFORMULA en col J
- create_form_for_open_mic: flujo completo devuelve FormCreationResult
"""

from __future__ import annotations

import datetime as dt
import os
import sys
import unittest.mock as mock
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Stub google libs para que el módulo sea importable sin instalar las deps
# ---------------------------------------------------------------------------
_mock_google            = MagicMock()
_mock_oauth2            = MagicMock()
_mock_credentials       = MagicMock()
_mock_transport         = MagicMock()
_mock_requests          = MagicMock()
_mock_discovery         = MagicMock()

sys.modules.setdefault("google",                              _mock_google)
sys.modules.setdefault("google.oauth2",                       _mock_oauth2)
sys.modules.setdefault("google.oauth2.credentials",           _mock_credentials)
sys.modules.setdefault("google.auth",                         MagicMock())
sys.modules.setdefault("google.auth.transport",               _mock_transport)
sys.modules.setdefault("google.auth.transport.requests",      _mock_requests)
sys.modules.setdefault("googleapiclient",                     MagicMock())
sys.modules.setdefault("googleapiclient.discovery",           _mock_discovery)

_mock_google.oauth2 = _mock_oauth2
_mock_oauth2.credentials = _mock_credentials
_mock_google.auth = MagicMock()
_mock_google.auth.transport = _mock_transport
_mock_transport.requests = _mock_requests

# ---------------------------------------------------------------------------
# Helpers para construir el builder con todas las APIs mockeadas
# ---------------------------------------------------------------------------

FAKE_ENV = {
    "GOOGLE_OAUTH_CLIENT_ID":     "fake-client-id",
    "GOOGLE_OAUTH_CLIENT_SECRET": "fake-client-secret",
    "GOOGLE_OAUTH_REFRESH_TOKEN": "fake-refresh-token",
}


def _make_builder():
    """Devuelve un GoogleFormBuilder con OAuth2 y clientes de API mockeados."""
    with patch.dict(os.environ, FAKE_ENV), \
         patch("backend.src.core.google_form_builder.Credentials") as MockCreds, \
         patch("backend.src.core.google_form_builder.Request"), \
         patch("backend.src.core.google_form_builder.build") as mock_build:

        mock_creds_instance = MagicMock()
        MockCreds.return_value = mock_creds_instance

        mock_forms  = MagicMock()
        mock_sheets = MagicMock()
        mock_drive  = MagicMock()
        mock_script = MagicMock()

        def _build_side_effect(service, *args, **kwargs):
            return {
                "forms": mock_forms,
                "sheets": mock_sheets,
                "drive": mock_drive,
                "script": mock_script,
            }[service]

        mock_build.side_effect = _build_side_effect

        from backend.src.core.google_form_builder import GoogleFormBuilder
        builder = GoogleFormBuilder()

    # Inyectamos los mocks directamente para usarlos en los tests
    builder._forms  = mock_forms
    builder._sheets = mock_sheets
    builder._drive  = mock_drive
    builder._script = mock_script
    return builder


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestInit:
    def test_raises_if_env_vars_missing(self):
        from backend.src.core.google_form_builder import GoogleFormBuilder
        with patch.dict(os.environ, {}, clear=True), \
             pytest.raises(ValueError, match="GOOGLE_OAUTH_CLIENT_ID"):
            builder = GoogleFormBuilder()
            builder._ensure_services()

    def test_raises_if_partial_env_vars(self):
        from backend.src.core.google_form_builder import GoogleFormBuilder
        partial = {"GOOGLE_OAUTH_CLIENT_ID": "x", "GOOGLE_OAUTH_CLIENT_SECRET": "y"}
        with patch.dict(os.environ, partial, clear=True), \
             pytest.raises(ValueError):
            builder = GoogleFormBuilder()
            builder._ensure_services()

    def test_builds_three_api_clients(self):
        with patch.dict(os.environ, FAKE_ENV), \
             patch("backend.src.core.google_form_builder.Credentials"), \
             patch("backend.src.core.google_form_builder.Request"), \
             patch("backend.src.core.google_form_builder.build") as mock_build:

            mock_build.return_value = MagicMock()
            from backend.src.core.google_form_builder import GoogleFormBuilder
            builder = GoogleFormBuilder()
            builder._ensure_services()

        services = [c.args[0] for c in mock_build.call_args_list]
        assert set(services) == {"forms", "sheets", "drive", "script"}


# ---------------------------------------------------------------------------
# _create_form
# ---------------------------------------------------------------------------

class TestCreateForm:
    def test_calls_forms_create_with_correct_title(self):
        builder = _make_builder()
        builder._forms.forms().create().execute.return_value = {"formId": "form-123"}

        result = builder._create_form("Mi Open Mic")

        create_body = builder._forms.forms().create.call_args.kwargs["body"]
        assert create_body["info"]["title"] == "Solicitudes — Mi Open Mic"
        assert "description" in create_body["info"]
        assert result == "form-123"

    def test_returns_form_id(self):
        builder = _make_builder()
        builder._forms.forms().create().execute.return_value = {"formId": "abc-xyz"}
        assert builder._create_form("Test") == "abc-xyz"


# ---------------------------------------------------------------------------
# _add_questions
# ---------------------------------------------------------------------------

class TestAddQuestions:
    def test_sends_eight_questions(self):
        builder = _make_builder()
        builder._forms.forms().batchUpdate().execute.return_value = {}

        builder._add_questions("form-123")

        call_body = builder._forms.forms().batchUpdate.call_args.kwargs["body"]
        assert len(call_body["requests"]) == 8

    def test_questions_use_create_item(self):
        builder = _make_builder()
        builder._forms.forms().batchUpdate().execute.return_value = {}

        builder._add_questions("form-123")

        body = builder._forms.forms().batchUpdate.call_args.kwargs["body"]
        for i, req in enumerate(body["requests"]):
            assert "createItem" in req
            assert req["createItem"]["location"]["index"] == i

    def test_first_question_title(self):
        builder = _make_builder()
        builder._forms.forms().batchUpdate().execute.return_value = {}

        builder._add_questions("form-123")

        body = builder._forms.forms().batchUpdate.call_args.kwargs["body"]
        first_item = body["requests"][0]["createItem"]["item"]
        assert first_item["title"] == "Nombre artístico"

    def test_choice_question_has_radio_options(self):
        builder = _make_builder()
        builder._forms.forms().batchUpdate().execute.return_value = {}

        builder._add_questions("form-123")

        body = builder._forms.forms().batchUpdate.call_args.kwargs["body"]
        # Pregunta 4 (índice 3) es choiceQuestion
        item = body["requests"][3]["createItem"]["item"]
        choice = item["questionItem"]["question"]["choiceQuestion"]
        assert choice["type"] == "RADIO"
        assert len(choice["options"]) == 4


# ---------------------------------------------------------------------------
# _build_item
# ---------------------------------------------------------------------------

class TestBuildItem:
    def setup_method(self):
        self.builder = _make_builder()

    def test_text_question_structure(self):
        q = {"title": "Test", "required": True, "kind": "textQuestion", "paragraph": False}
        item = self.builder._build_item(q)
        assert item["title"] == "Test"
        assert "questionItem" in item
        assert "textQuestion" in item["questionItem"]["question"]
        assert item["questionItem"]["question"]["required"] is True
        assert item["questionItem"]["question"]["textQuestion"]["paragraph"] is False

    def test_paragraph_question(self):
        q = {"title": "Long", "required": False, "kind": "textQuestion", "paragraph": True}
        item = self.builder._build_item(q)
        assert item["questionItem"]["question"]["textQuestion"]["paragraph"] is True

    def test_choice_question_structure(self):
        q = {
            "title": "Choices",
            "required": True,
            "kind": "choiceQuestion",
            "options": ["A", "B"],
        }
        item = self.builder._build_item(q)
        choice = item["questionItem"]["question"]["choiceQuestion"]
        assert choice["type"] == "RADIO"
        assert choice["options"] == [{"value": "A"}, {"value": "B"}]


# ---------------------------------------------------------------------------
# _get_linked_sheet_id
# ---------------------------------------------------------------------------

class TestGetLinkedSheetId:
    def test_returns_linked_sheet_id_if_present(self):
        builder = _make_builder()
        builder._forms.forms().get().execute.return_value = {"linkedSheetId": "sheet-999"}

        result = builder._get_linked_sheet_id("form-123", "Nombre")

        assert result == "sheet-999"
        builder._sheets.spreadsheets().create.assert_not_called()

    def test_creates_own_sheet_if_no_linked_sheet(self):
        builder = _make_builder()
        builder._forms.forms().get().execute.return_value = {}  # sin linkedSheetId
        builder._sheets.spreadsheets().create().execute.return_value = {
            "spreadsheetId": "new-sheet-id"
        }
        builder._sheets.spreadsheets().values().update().execute.return_value = {}

        result = builder._get_linked_sheet_id("form-123", "Mi Mic")

        assert result == "new-sheet-id"

    def test_new_sheet_title_contains_nombre(self):
        builder = _make_builder()
        builder._forms.forms().get().execute.return_value = {}
        builder._sheets.spreadsheets().create().execute.return_value = {
            "spreadsheetId": "sheet-abc"
        }
        builder._sheets.spreadsheets().values().update().execute.return_value = {}

        builder._get_linked_sheet_id("form-123", "La caja")

        create_body = builder._sheets.spreadsheets().create.call_args.kwargs["body"]
        assert "La caja" in create_body["properties"]["title"]

    def test_new_sheet_writes_nine_headers(self):
        builder = _make_builder()
        builder._forms.forms().get().execute.return_value = {}
        builder._sheets.spreadsheets().create().execute.return_value = {
            "spreadsheetId": "sheet-abc"
        }
        builder._sheets.spreadsheets().values().update().execute.return_value = {}

        builder._get_linked_sheet_id("form-123", "La caja")

        update_body = builder._sheets.spreadsheets().values().update.call_args.kwargs["body"]
        headers = update_body["values"][0]
        assert len(headers) == 9
        assert headers[0] == "Marca temporal"
        assert headers[1] == "Nombre artístico"


# ---------------------------------------------------------------------------
# _inject_open_mic_id_column
# ---------------------------------------------------------------------------

class TestInjectOpenMicIdColumn:
    def test_writes_header_and_arrayformula_in_col_j(self):
        builder = _make_builder()
        builder._sheets.spreadsheets().get().execute.return_value = {
            "sheets": [{"properties": {"title": "Respuestas"}}]
        }
        builder._sheets.spreadsheets().values().update().execute.return_value = {}

        builder._inject_open_mic_id_column("sheet-123", "open-mic-uuid")

        update_call = builder._sheets.spreadsheets().values().update.call_args
        assert update_call.kwargs["range"] == "Respuestas!J1"

    def test_header_is_open_mic_id(self):
        builder = _make_builder()
        builder._sheets.spreadsheets().get().execute.return_value = {
            "sheets": [{"properties": {"title": "Respuestas"}}]
        }
        builder._sheets.spreadsheets().values().update().execute.return_value = {}

        builder._inject_open_mic_id_column("sheet-123", "open-mic-uuid")

        body = builder._sheets.spreadsheets().values().update.call_args.kwargs["body"]
        assert body["values"][0] == ["open_mic_id", "n8n_procesado"]

    def test_arrayformula_contains_open_mic_id(self):
        builder = _make_builder()
        builder._sheets.spreadsheets().get().execute.return_value = {
            "sheets": [{"properties": {"title": "Respuestas"}}]
        }
        builder._sheets.spreadsheets().values().update().execute.return_value = {}

        builder._inject_open_mic_id_column("sheet-123", "my-open-mic-id")

        body = builder._sheets.spreadsheets().values().update.call_args.kwargs["body"]
        formula = body["values"][1][0]
        assert "my-open-mic-id" in formula
        assert "ARRAYFORMULA" in formula


# ---------------------------------------------------------------------------
# create_form_for_open_mic — flujo completo
# ---------------------------------------------------------------------------

class TestCreateFormForOpenMic:
    def _setup_happy_path(self, builder):
        builder._forms.forms().create().execute.return_value = {"formId": "form-abc"}
        builder._forms.forms().batchUpdate().execute.return_value = {}
        builder._forms.forms().get().execute.return_value = {}  # sin linkedSheetId
        builder._sheets.spreadsheets().create().execute.return_value = {
            "spreadsheetId": "sheet-xyz"
        }
        builder._sheets.spreadsheets().get().execute.return_value = {
            "sheets": [{"properties": {"title": "Respuestas"}}]
        }
        builder._sheets.spreadsheets().values().update().execute.return_value = {}

    def test_returns_form_creation_result(self):
        from backend.src.core.google_form_builder import FormCreationResult
        builder = _make_builder()
        self._setup_happy_path(builder)

        result = builder.create_form_for_open_mic("open-mic-123", "La caja")

        assert isinstance(result, FormCreationResult)

    def test_result_form_url_contains_form_id(self):
        builder = _make_builder()
        self._setup_happy_path(builder)

        result = builder.create_form_for_open_mic("open-mic-123", "La caja")

        assert "form-abc" in result.form_url
        assert result.form_url.endswith("/viewform")

    def test_result_sheet_url_contains_sheet_id(self):
        builder = _make_builder()
        self._setup_happy_path(builder)

        result = builder.create_form_for_open_mic("open-mic-123", "La caja")

        assert "sheet-xyz" in result.sheet_url

    def test_result_ids_match(self):
        builder = _make_builder()
        self._setup_happy_path(builder)

        result = builder.create_form_for_open_mic("open-mic-123", "La caja")

        assert result.form_id == "form-abc"
        assert result.sheet_id == "sheet-xyz"


# ---------------------------------------------------------------------------
# Sprint 13 — _build_description
# ---------------------------------------------------------------------------

class TestBuildDescription:
    def test_build_description_completa(self):
        from backend.src.core.google_form_builder import GoogleFormBuilder
        info = {
            "local": "Bar La Recova",
            "direccion": "Gran Vía 28",
            "dia_semana": "Miércoles",
            "cadencia": "semanal",
        }
        desc = GoogleFormBuilder._build_description("Recova Open Mic", info)
        assert "Recova Open Mic" in desc
        assert "Bar La Recova" in desc
        assert "Gran Vía 28" in desc
        assert "semanalmente" in desc

    def test_build_description_parcial(self):
        from backend.src.core.google_form_builder import GoogleFormBuilder
        desc = GoogleFormBuilder._build_description("Mi Open Mic", {})
        assert "Mi Open Mic" in desc
        # Sin contexto extra
        assert "semanalmente" not in desc
        assert "cada dos semanas" not in desc


# ---------------------------------------------------------------------------
# Sprint 13 — _random_form_color
# ---------------------------------------------------------------------------

class TestRandomFormColor:
    def test_random_form_color(self):
        from backend.src.core.google_form_builder import _FORM_BG_PALETTE
        builder = _make_builder()
        color = builder._random_form_color()
        assert color in _FORM_BG_PALETTE
        assert color.startswith("#")
        assert len(color) == 7


# ---------------------------------------------------------------------------
# Sprint 13 — _build_date_options
# ---------------------------------------------------------------------------

class TestBuildDateOptions:
    def test_build_date_options_unico(self):
        builder = _make_builder()
        assert builder._build_date_options({"cadencia": "unico"}) == []

    def test_build_date_options_semanal(self):
        builder = _make_builder()
        info = {"cadencia": "semanal", "dia_semana": "Miércoles"}
        result = builder._build_date_options(info)
        today = dt.date.today()
        assert len(result) > 0
        for ds in result:
            day, mon, yr = int(ds[:2]), int(ds[3:5]), 2000 + int(ds[6:])
            d = dt.date(yr, mon, day)
            assert d >= today
            assert d.weekday() == 2  # Wednesday

    def test_build_date_options_quincenal(self):
        builder = _make_builder()
        info = {"cadencia": "quincenal", "fecha_inicio": "2020-01-01"}
        result = builder._build_date_options(info)
        assert len(result) == 4
        parsed = []
        for ds in result:
            day, mon, yr = int(ds[:2]), int(ds[3:5]), 2000 + int(ds[6:])
            parsed.append(dt.date(yr, mon, day))
        for i in range(1, len(parsed)):
            assert (parsed[i] - parsed[i - 1]).days == 14

    def test_build_date_options_mensual(self):
        builder = _make_builder()
        info = {"cadencia": "mensual", "fecha_inicio": "2020-01-15"}
        result = builder._build_date_options(info)
        assert len(result) == 3
        today = dt.date.today()
        for ds in result:
            day, mon, yr = int(ds[:2]), int(ds[3:5]), 2000 + int(ds[6:])
            d = dt.date(yr, mon, day)
            assert d >= today


# ---------------------------------------------------------------------------
# Sprint 13 — _add_questions con info
# ---------------------------------------------------------------------------

class TestAddQuestionsWithInfo:
    def test_add_questions_checkbox_semanal(self):
        builder = _make_builder()
        builder._forms.forms().batchUpdate().execute.return_value = {}
        with mock.patch.object(
            builder, "_build_date_options", return_value=["12-03-26", "19-03-26"]
        ):
            builder._add_questions("form-123", {"cadencia": "semanal", "dia_semana": "Miércoles"})

        body = builder._forms.forms().batchUpdate.call_args.kwargs["body"]
        date_items = [
            r["createItem"]["item"]
            for r in body["requests"]
            if "fecha" in r["createItem"]["item"]["title"].lower()
        ]
        assert len(date_items) == 1
        choice = date_items[0]["questionItem"]["question"]["choiceQuestion"]
        assert choice["type"] == "CHECKBOX"
        assert len(choice["options"]) == 2

    def test_add_questions_omite_fecha_unico(self):
        builder = _make_builder()
        builder._forms.forms().batchUpdate().execute.return_value = {}
        builder._add_questions("form-123", {"cadencia": "unico"})
        body = builder._forms.forms().batchUpdate.call_args.kwargs["body"]
        assert len(body["requests"]) == 7
        titles = [r["createItem"]["item"]["title"] for r in body["requests"]]
        assert not any("fecha" in t.lower() for t in titles)
