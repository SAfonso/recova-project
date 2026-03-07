"""Tests TDD — CustomScoringProposer (Sprint 10, v0.15.0).

Cubre (spec custom_scoring_spec §CustomScoringProposer):
  propose — Gemini propone reglas de scoring desde campos no canónicos
  lista vacía → devuelve [] sin llamar a Gemini
  strip de markdown fences
  ValueError en JSON inválido
  Gemini puede omitir campos sin sentido
"""

from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock

import pytest

# Inyecta mock de google.genai antes de importar CustomScoringProposer.
_mock_genai = MagicMock()
sys.modules.setdefault("google.genai", _mock_genai)
sys.modules.setdefault("google.genai.types", MagicMock())
# Siempre apuntar al mock que realmente está en sys.modules.
_mock_genai = sys.modules["google.genai"]

from backend.src.core.custom_scoring_proposer import CustomScoringProposer  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

UNMAPPED_FIELDS = ["¿Haces humor negro?", "¿Tienes material nuevo?"]

PROPOSED_RULES = [
    {
        "field": "¿Haces humor negro?",
        "condition": "equals",
        "value": "Sí",
        "points": 10,
        "enabled": True,
        "description": "Bono por humor negro",
    },
    {
        "field": "¿Tienes material nuevo?",
        "condition": "equals",
        "value": "Sí",
        "points": 5,
        "enabled": True,
        "description": "Bono por material nuevo",
    },
]


def _setup_gemini_mock(payload: list | str) -> None:
    """Configura el mock de Gemini para devolver el payload dado."""
    response = MagicMock()
    if isinstance(payload, list):
        response.text = json.dumps({"rules": payload})
    else:
        response.text = payload
    _mock_genai.Client.return_value.models.generate_content.return_value = response


def _make_proposer() -> CustomScoringProposer:
    return CustomScoringProposer(api_key="test-key")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_propose_returns_rules_list():
    """Lista de campos no canónicos → lista de reglas con estructura correcta."""
    _setup_gemini_mock(PROPOSED_RULES)

    proposer = _make_proposer()
    result = proposer.propose(UNMAPPED_FIELDS)

    assert isinstance(result, list)
    assert len(result) == 2

    rule = result[0]
    assert rule["field"] == "¿Haces humor negro?"
    assert rule["condition"] == "equals"
    assert rule["value"] == "Sí"
    assert rule["points"] == 10
    assert rule["enabled"] is True
    assert "description" in rule


def test_propose_empty_fields_returns_empty():
    """Sin unmapped_fields → devuelve [] sin llamar a Gemini."""
    _mock_genai.Client.return_value.models.generate_content.reset_mock()

    proposer = _make_proposer()
    result = proposer.propose([])

    assert result == []
    _mock_genai.Client.return_value.models.generate_content.assert_not_called()


def test_propose_strips_markdown_fences():
    """Gemini devuelve ```json ... ``` → se parsea correctamente."""
    raw = f"```json\n{json.dumps({'rules': PROPOSED_RULES})}\n```"
    _setup_gemini_mock(raw)

    proposer = _make_proposer()
    result = proposer.propose(UNMAPPED_FIELDS)

    assert len(result) == 2
    assert result[0]["field"] == "¿Haces humor negro?"


def test_propose_raises_on_invalid_json():
    """JSON inválido devuelto por Gemini → ValueError con el raw text."""
    _setup_gemini_mock("esto no es json {{{")

    proposer = _make_proposer()
    with pytest.raises(ValueError, match="Gemini devolvió JSON inválido"):
        proposer.propose(UNMAPPED_FIELDS)


def test_propose_skips_fields_gemini_omits():
    """Gemini puede omitir campos sin sentido para scoring — OK, lista más corta."""
    partial_rules = [PROPOSED_RULES[0]]  # solo "¿Haces humor negro?"
    _setup_gemini_mock(partial_rules)

    proposer = _make_proposer()
    result = proposer.propose(UNMAPPED_FIELDS)

    # Gemini devolvió 1 regla aunque había 2 campos — es válido
    assert len(result) == 1
    assert result[0]["field"] == "¿Haces humor negro?"
