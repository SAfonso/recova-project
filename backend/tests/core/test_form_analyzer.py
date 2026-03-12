"""Tests TDD — FormAnalyzer (Sprint 9, v0.14.0).

Cubre (spec smart_form_ingestion_spec §FormAnalyzer):
  analyze — mapea títulos de preguntas al schema canónico via Gemini
  manejo de markdown fences
  ValueError en JSON inválido
"""

from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock

import pytest

# Inyecta mock de google.genai antes de importar FormAnalyzer,
# igual que en test_poster_detector_gemini.py para soportar entornos sin la lib.
_mock_google = MagicMock()
_mock_genai = MagicMock()
sys.modules.setdefault("google", _mock_google)
sys.modules.setdefault("google.genai", _mock_genai)
sys.modules.setdefault("google.genai.types", MagicMock())
# Siempre apuntar al mock que realmente está en sys.modules (puede haber sido
# registrado antes por otro test file si pytest los carga en paralelo/orden distinto)
_mock_google = sys.modules["google"]
_mock_genai = sys.modules["google.genai"]
_mock_google.genai = _mock_genai

from backend.src.core.form_analyzer import FormAnalyzer  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CANONICAL_FIELDS = [
    "nombre_artistico", "instagram", "whatsapp", "experiencia",
    "fechas_disponibles", "backup", "show_proximo", "como_nos_conociste",
]

STANDARD_QUESTIONS = [
    "Nombre artístico",
    "Instagram (sin @)",
    "WhatsApp",
    "¿Cuántas veces has actuado en un open mic?",
    "¿Qué fechas te vienen bien?",
    "¿Estarías disponible si nos falla alguien de última hora?",
    "¿Tienes algún show próximo que quieras mencionar?",
    "¿Cómo nos conociste?",
]

STANDARD_MAPPING = {
    "Nombre artístico": "nombre_artistico",
    "Instagram (sin @)": "instagram",
    "WhatsApp": "whatsapp",
    "¿Cuántas veces has actuado en un open mic?": "experiencia",
    "¿Qué fechas te vienen bien?": "fechas_disponibles",
    "¿Estarías disponible si nos falla alguien de última hora?": "backup",
    "¿Tienes algún show próximo que quieras mencionar?": "show_proximo",
    "¿Cómo nos conociste?": "como_nos_conociste",
}

PARTIAL_QUESTIONS = ["Nombre artístico", "¿Cuál es tu Instagram?", "¿De dónde eres?"]
PARTIAL_MAPPING = {
    "Nombre artístico": "nombre_artistico",
    "¿Cuál es tu Instagram?": "instagram",
    "¿De dónde eres?": None,
}


def _setup_gemini_mock(payload: dict | str) -> None:
    """Configura el mock de Gemini para devolver el payload dado."""
    response = MagicMock()
    if isinstance(payload, dict):
        response.text = json.dumps({"field_mapping": payload})
    else:
        response.text = payload
    _mock_genai.Client.return_value.models.generate_content.return_value = response


def _make_analyzer() -> FormAnalyzer:
    return FormAnalyzer(api_key="test-key")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_analyze_maps_standard_fields():
    """Form con los 8 campos estándar → mapping completo al schema canónico."""
    _setup_gemini_mock(STANDARD_MAPPING)

    analyzer = _make_analyzer()
    result = analyzer.analyze(STANDARD_QUESTIONS)

    assert result == STANDARD_MAPPING
    for field in CANONICAL_FIELDS:
        assert field in result.values()


def test_analyze_returns_null_for_unrecognized_fields():
    """Campos que no encajan en el schema canónico → None en el mapping."""
    _setup_gemini_mock(PARTIAL_MAPPING)

    analyzer = _make_analyzer()
    result = analyzer.analyze(PARTIAL_QUESTIONS)

    assert result["¿De dónde eres?"] is None
    assert result["Nombre artístico"] == "nombre_artistico"


def test_analyze_strips_markdown_fences():
    """Gemini devuelve ```json ... ``` → se parsea correctamente."""
    raw = f"```json\n{json.dumps({'field_mapping': STANDARD_MAPPING})}\n```"
    _setup_gemini_mock(raw)

    analyzer = _make_analyzer()
    result = analyzer.analyze(STANDARD_QUESTIONS)

    assert result["Nombre artístico"] == "nombre_artistico"


def test_analyze_raises_on_invalid_json():
    """JSON inválido devuelto por Gemini → ValueError con el raw text."""
    _setup_gemini_mock("esto no es json {{{")

    analyzer = _make_analyzer()
    with pytest.raises(ValueError, match="Gemini devolvió JSON inválido"):
        analyzer.analyze(STANDARD_QUESTIONS)


def test_analyze_partial_mapping():
    """Form con campos mixtos (canónicos + extras) → mapeo parcial con Nones."""
    _setup_gemini_mock(PARTIAL_MAPPING)

    analyzer = _make_analyzer()
    result = analyzer.analyze(PARTIAL_QUESTIONS)

    mapped = [v for v in result.values() if v is not None]
    assert len(mapped) == 2
    assert "nombre_artistico" in mapped
    assert "instagram" in mapped
    assert result["¿De dónde eres?"] is None
