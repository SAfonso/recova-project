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

import os
from unittest.mock import MagicMock, call, patch

import pytest

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

        def _build_side_effect(service, *args, **kwargs):
            return {"forms": mock_forms, "sheets": mock_sheets, "drive": mock_drive}[service]

        mock_build.side_effect = _build_side_effect

        from backend.src.core.google_form_builder import GoogleFormBuilder
        builder = GoogleFormBuilder()

    # Inyectamos los mocks directamente para usarlos en los tests
    builder._forms  = mock_forms
    builder._sheets = mock_sheets
    builder._drive  = mock_drive
    return builder


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestInit:
    def test_raises_if_env_vars_missing(self):
        from backend.src.core.google_form_builder import GoogleFormBuilder
        with patch.dict(os.environ, {}, clear=True), \
             pytest.raises(ValueError, match="GOOGLE_OAUTH_CLIENT_ID"):
            GoogleFormBuilder()

    def test_raises_if_partial_env_vars(self):
        from backend.src.core.google_form_builder import GoogleFormBuilder
        partial = {"GOOGLE_OAUTH_CLIENT_ID": "x", "GOOGLE_OAUTH_CLIENT_SECRET": "y"}
        with patch.dict(os.environ, partial, clear=True), \
             pytest.raises(ValueError):
            GoogleFormBuilder()

    def test_builds_three_api_clients(self):
        with patch.dict(os.environ, FAKE_ENV), \
             patch("backend.src.core.google_form_builder.Credentials"), \
             patch("backend.src.core.google_form_builder.Request"), \
             patch("backend.src.core.google_form_builder.build") as mock_build:

            mock_build.return_value = MagicMock()
            from backend.src.core.google_form_builder import GoogleFormBuilder
            GoogleFormBuilder()

        services = [c.args[0] for c in mock_build.call_args_list]
        assert set(services) == {"forms", "sheets", "drive"}


# ---------------------------------------------------------------------------
# _create_form
# ---------------------------------------------------------------------------

class TestCreateForm:
    def test_calls_forms_create_with_correct_title(self):
        builder = _make_builder()
        builder._forms.forms().create().execute.return_value = {"formId": "form-123"}

        result = builder._create_form("Mi Open Mic")

        builder._forms.forms().create.assert_called_with(
            body={"info": {"title": "Solicitudes — Mi Open Mic"}}
        )
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
        assert body["values"][0] == ["open_mic_id"]

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
