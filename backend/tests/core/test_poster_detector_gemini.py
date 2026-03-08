"""Tests unitarios — GeminiDetector (Variante B)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image as _PILImage

# Inyecta mocks del nuevo SDK google-genai antes de importar GeminiDetector
# para que funcione aunque la librería no esté instalada en el entorno de CI.
_mock_genai = MagicMock()
_mock_types = MagicMock()
sys.modules.setdefault("google.genai", _mock_genai)
sys.modules.setdefault("google.genai.types", _mock_types)
# Siempre apuntar al mock que realmente está en sys.modules (puede haber sido
# registrado antes por otro test file si pytest los carga en un orden distinto)
_mock_genai = sys.modules["google.genai"]
_mock_types = sys.modules["google.genai.types"]

from backend.src.core.poster_detector_gemini import GeminiDetector  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_valid_png(path: Path, width: int = 100, height: int = 100) -> None:
    """Crea un PNG válido mínimo para que Pillow pueda abrirlo."""
    img = _PILImage.new("RGB", (width, height), color=(0, 0, 0))
    img.save(path, format="PNG")


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_gemini_response(payload: list[dict] | dict | str) -> MagicMock:
    """Mock de response de Gemini con texto JSON."""
    response = MagicMock()
    if isinstance(payload, (list, dict)):
        response.text = json.dumps(payload)
    else:
        response.text = payload
    return response


def _valid_payload(n: int = 3) -> dict:
    """Formato nuevo: objeto con font_name + placeholders."""
    return {
        "font_name": "Bebas Neue",
        "placeholders": [
            {
                "placeholder": f"COMICO_{i+1}",
                "slot": i + 1,
                "center_x": 490 + i * 5,
                "center_y": 500 + i * 80,
                "font_size": 45,
                "color": "#ffffff",
            }
            for i in range(n)
        ],
    }


def _valid_payload_legacy(n: int = 3) -> list[dict]:
    """Formato legacy: array directo."""
    return [
        {
            "placeholder": f"COMICO_{i+1}",
            "slot": i + 1,
            "center_x": 490 + i * 5,
            "center_y": 500 + i * 80,
            "font_size": 45,
            "color": "#ffffff",
        }
        for i in range(n)
    ]


# ── Tests de inicialización ───────────────────────────────────────────────────

def test_raises_on_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ERR_MISSING_KEY"):
        GeminiDetector(api_key=None)


def test_accepts_explicit_api_key() -> None:
    detector = GeminiDetector(api_key="test-key-123")
    assert detector._api_key == "test-key-123"


def test_reads_api_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "env-key-abc")
    detector = GeminiDetector()
    assert detector._api_key == "env-key-abc"


# ── Tests de detección ────────────────────────────────────────────────────────

def _setup_genai_mock(response: MagicMock) -> None:
    """Configura el mock global del nuevo SDK genai para devolver el response dado."""
    _mock_genai.Client.return_value.models.generate_content.return_value = response


def test_detect_parses_valid_json_response(tmp_path: Path) -> None:
    dummy_png = tmp_path / "suxio.png"
    _make_valid_png(dummy_png)

    _setup_genai_mock(_make_gemini_response(_valid_payload(3)))
    detector = GeminiDetector(api_key="test-key")
    anchors = detector.detect(dummy_png)

    assert len(anchors) == 3
    assert anchors[0].slot == 1
    assert anchors[0].center_x == 490
    assert anchors[0].font_size == 45
    assert anchors[0].color == "#ffffff"
    assert anchors[0].font_name == "Bebas Neue"


def test_detect_font_name_propagated(tmp_path: Path) -> None:
    """font_name del objeto raíz se propaga a todos los anchors."""
    dummy_png = tmp_path / "suxio.png"
    _make_valid_png(dummy_png)

    payload = {"font_name": "Impact", "placeholders": _valid_payload_legacy(2)}
    _setup_genai_mock(_make_gemini_response(payload))

    detector = GeminiDetector(api_key="test-key")
    anchors = detector.detect(dummy_png)

    assert all(a.font_name == "Impact" for a in anchors)


def test_detect_legacy_array_format(tmp_path: Path) -> None:
    """Formato legacy (array) sigue funcionando; _detect_font_name se llama como fallback."""
    dummy_png = tmp_path / "suxio.png"
    _make_valid_png(dummy_png)

    _setup_genai_mock(_make_gemini_response(_valid_payload_legacy(2)))
    detector = GeminiDetector(api_key="test-key")
    with patch.object(detector, "_detect_font_name", return_value=""):
        anchors = detector.detect(dummy_png)

    assert len(anchors) == 2
    assert anchors[0].font_name == ""


def test_detect_strips_markdown_fences(tmp_path: Path) -> None:
    dummy_png = tmp_path / "suxio.png"
    _make_valid_png(dummy_png)

    payload_with_fences = f"```json\n{json.dumps(_valid_payload(2))}\n```"
    _setup_genai_mock(_make_gemini_response(payload_with_fences))

    detector = GeminiDetector(api_key="test-key")
    anchors = detector.detect(dummy_png)

    assert len(anchors) == 2


def test_detect_sorts_by_slot(tmp_path: Path) -> None:
    dummy_png = tmp_path / "suxio.png"
    _make_valid_png(dummy_png)

    # Usar placeholders en orden inverso dentro del objeto nuevo
    payload = _valid_payload(4)
    payload["placeholders"] = list(reversed(payload["placeholders"]))
    _setup_genai_mock(_make_gemini_response(payload))

    detector = GeminiDetector(api_key="test-key")
    anchors = detector.detect(dummy_png)

    assert [a.slot for a in anchors] == [1, 2, 3, 4]


def test_detect_raises_on_malformed_json(tmp_path: Path) -> None:
    dummy_png = tmp_path / "suxio.png"
    _make_valid_png(dummy_png)

    _setup_genai_mock(_make_gemini_response("esto no es json {{{"))

    detector = GeminiDetector(api_key="test-key")
    with pytest.raises(RuntimeError, match="ERR_GEMINI_PARSE"):
        detector.detect(dummy_png)


def test_detect_placeholder_normalized_from_slot(tmp_path: Path) -> None:
    """Si Gemini no incluye 'placeholder', se genera desde 'slot'."""
    dummy_png = tmp_path / "suxio.png"
    _make_valid_png(dummy_png)

    payload = [{"slot": 1, "center_x": 500, "center_y": 600, "font_size": 40}]
    _setup_genai_mock(_make_gemini_response(payload))

    detector = GeminiDetector(api_key="test-key")
    anchors = detector.detect(dummy_png)

    assert anchors[0].placeholder == "COMICO_1"
    assert anchors[0].color == "#ffffff"  # default
