"""Tests TDD — FormIngestor (Sprint 9, v0.14.0).

Cubre (spec smart_form_ingestion_spec §FormIngestor):
  get_form_questions — extrae preguntas de la estructura del form
  get_responses      — lee respuestas y aplica field_mapping
  constructor        — valida env vars
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

# Env vars mínimas para que el constructor no explote al importar
os.environ.setdefault("GOOGLE_OAUTH_CLIENT_ID", "fake-client-id")
os.environ.setdefault("GOOGLE_OAUTH_CLIENT_SECRET", "fake-client-secret")
os.environ.setdefault("GOOGLE_OAUTH_REFRESH_TOKEN", "fake-refresh-token")


# ---------------------------------------------------------------------------
# Fixtures de respuesta de Forms API
# ---------------------------------------------------------------------------

FORM_GET_STANDARD = {
    "formId": "form-abc",
    "items": [
        {
            "title": "Nombre artístico",
            "questionItem": {
                "question": {"questionId": "q001", "textQuestion": {}}
            },
        },
        {
            "title": "Instagram (sin @)",
            "questionItem": {
                "question": {"questionId": "q002", "textQuestion": {}}
            },
        },
        {
            "title": "¿Cuántas veces has actuado en un open mic?",
            "questionItem": {
                "question": {"questionId": "q003", "choiceQuestion": {"type": "RADIO"}}
            },
        },
        # Ítem sin questionItem (sección) — debe ignorarse
        {"title": "Sección: datos personales"},
    ],
}

FORM_GET_WITH_EXTRA = {
    "formId": "form-extra",
    "items": [
        {
            "title": "Nombre artístico",
            "questionItem": {"question": {"questionId": "q001", "textQuestion": {}}},
        },
        {
            "title": "¿De dónde eres?",
            "questionItem": {"question": {"questionId": "q-extra", "textQuestion": {}}},
        },
    ],
}

FIELD_MAPPING_STANDARD = {
    "Nombre artístico": "nombre_artistico",
    "Instagram (sin @)": "instagram",
    "¿Cuántas veces has actuado en un open mic?": "experiencia",
}

FIELD_MAPPING_WITH_NULL = {
    "Nombre artístico": "nombre_artistico",
    "¿De dónde eres?": None,
}

RESPONSES_ONE = {
    "responses": [
        {
            "responseId": "resp-001",
            "createTime": "2026-03-06T10:30:00Z",
            "answers": {
                "q001": {
                    "questionId": "q001",
                    "textAnswers": {"answers": [{"value": "Juan García"}]},
                },
                "q002": {
                    "questionId": "q002",
                    "textAnswers": {"answers": [{"value": "juangarcia"}]},
                },
                "q003": {
                    "questionId": "q003",
                    "textAnswers": {"answers": [{"value": "Llevo tiempo haciendo stand-up"}]},
                },
            },
        }
    ]
}

RESPONSES_WITH_UNMAPPED = {
    "responses": [
        {
            "responseId": "resp-002",
            "createTime": "2026-03-06T11:00:00Z",
            "answers": {
                "q001": {
                    "questionId": "q001",
                    "textAnswers": {"answers": [{"value": "Ana López"}]},
                },
                "q-extra": {
                    "questionId": "q-extra",
                    "textAnswers": {"answers": [{"value": "Madrid"}]},
                },
            },
        }
    ]
}

RESPONSES_EMPTY_ANSWER = {
    "responses": [
        {
            "responseId": "resp-003",
            "createTime": "2026-03-06T12:00:00Z",
            "answers": {
                "q001": {
                    "questionId": "q001",
                    "textAnswers": {"answers": []},  # sin valor
                },
            },
        }
    ]
}

RESPONSES_CHOICE = {
    "responses": [
        {
            "responseId": "resp-004",
            "createTime": "2026-03-06T13:00:00Z",
            "answers": {
                "q003": {
                    "questionId": "q003",
                    "textAnswers": {"answers": [{"value": "Es mi primera vez"}]},
                },
            },
        }
    ]
}

RESPONSES_EMPTY = {"responses": []}


# ---------------------------------------------------------------------------
# Helper — construye FormIngestor con cliente mockeado (sin auth real)
# ---------------------------------------------------------------------------

def _make_ingestor(form_get=None, responses=None):
    """Devuelve FormIngestor con _forms mockeado."""
    from backend.src.core.form_ingestor import FormIngestor

    ingestor = FormIngestor.__new__(FormIngestor)
    svc = MagicMock()
    if form_get is not None:
        svc.forms().get().execute.return_value = form_get
    if responses is not None:
        svc.forms().responses().list().execute.return_value = responses
    ingestor._forms = svc
    return ingestor


# ---------------------------------------------------------------------------
# Tests: get_form_questions
# ---------------------------------------------------------------------------

def test_get_form_questions_returns_list():
    """Devuelve lista de dicts con question_id, title y kind."""
    ingestor = _make_ingestor(form_get=FORM_GET_STANDARD)
    questions = ingestor.get_form_questions("form-abc")

    assert len(questions) == 3
    assert questions[0] == {"question_id": "q001", "title": "Nombre artístico", "kind": "textQuestion"}
    assert questions[1] == {"question_id": "q002", "title": "Instagram (sin @)", "kind": "textQuestion"}
    assert questions[2] == {"question_id": "q003", "title": "¿Cuántas veces has actuado en un open mic?", "kind": "choiceQuestion"}


def test_get_form_questions_ignores_non_question_items():
    """Secciones e imágenes (sin questionItem) se ignoran."""
    ingestor = _make_ingestor(form_get=FORM_GET_STANDARD)
    questions = ingestor.get_form_questions("form-abc")

    titles = [q["title"] for q in questions]
    assert "Sección: datos personales" not in titles
    assert len(questions) == 3


# ---------------------------------------------------------------------------
# Tests: get_responses
# ---------------------------------------------------------------------------

def test_get_responses_maps_canonical_fields():
    """Campos con mapeo canónico aparecen en el dict raíz."""
    ingestor = _make_ingestor(form_get=FORM_GET_STANDARD, responses=RESPONSES_ONE)
    results = ingestor.get_responses("form-abc", FIELD_MAPPING_STANDARD)

    assert len(results) == 1
    r = results[0]
    assert r["nombre_artistico"] == "Juan García"
    assert r["instagram"] == "juangarcia"
    assert r["experiencia"] == "Llevo tiempo haciendo stand-up"


def test_get_responses_unmapped_to_metadata_extra():
    """Campos sin mapeo (None) van a metadata_extra."""
    ingestor = _make_ingestor(form_get=FORM_GET_WITH_EXTRA, responses=RESPONSES_WITH_UNMAPPED)
    results = ingestor.get_responses("form-extra", FIELD_MAPPING_WITH_NULL)

    assert len(results) == 1
    r = results[0]
    assert r["nombre_artistico"] == "Ana López"
    assert "metadata_extra" in r
    assert r["metadata_extra"]["¿De dónde eres?"] == "Madrid"


def test_get_responses_empty_answer_is_empty_string():
    """Respuesta sin valores devuelve string vacío."""
    ingestor = _make_ingestor(form_get=FORM_GET_STANDARD, responses=RESPONSES_EMPTY_ANSWER)
    results = ingestor.get_responses("form-abc", FIELD_MAPPING_STANDARD)

    assert len(results) == 1
    assert results[0]["nombre_artistico"] == ""


def test_get_responses_choice_question_single():
    """Opción única de choiceQuestion devuelve string plano (no lista)."""
    ingestor = _make_ingestor(form_get=FORM_GET_STANDARD, responses=RESPONSES_CHOICE)
    results = ingestor.get_responses("form-abc", FIELD_MAPPING_STANDARD)

    assert len(results) == 1
    assert results[0]["experiencia"] == "Es mi primera vez"
    assert isinstance(results[0]["experiencia"], str)


def test_get_responses_includes_response_id_and_timestamp():
    """Cada resultado incluye _response_id y _submitted_at."""
    ingestor = _make_ingestor(form_get=FORM_GET_STANDARD, responses=RESPONSES_ONE)
    results = ingestor.get_responses("form-abc", FIELD_MAPPING_STANDARD)

    assert results[0]["_response_id"] == "resp-001"
    assert results[0]["_submitted_at"] == "2026-03-06T10:30:00Z"


def test_get_responses_empty_form():
    """Form sin respuestas devuelve lista vacía."""
    ingestor = _make_ingestor(form_get=FORM_GET_STANDARD, responses=RESPONSES_EMPTY)
    results = ingestor.get_responses("form-abc", FIELD_MAPPING_STANDARD)

    assert results == []


# ---------------------------------------------------------------------------
# Tests: constructor
# ---------------------------------------------------------------------------

def test_constructor_raises_without_env_vars(monkeypatch: pytest.MonkeyPatch):
    """ValueError si faltan variables de entorno OAuth."""
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_REFRESH_TOKEN", raising=False)

    with patch("backend.src.core.form_ingestor.Credentials"), \
         patch("backend.src.core.form_ingestor.Request"), \
         patch("backend.src.core.form_ingestor.build"):
        from backend.src.core.form_ingestor import FormIngestor
        with pytest.raises(ValueError, match="Faltan variables de entorno"):
            FormIngestor()
