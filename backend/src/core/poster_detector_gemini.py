"""Variante B — Detector de placeholders via Gemini Flash (visión).

Envía el PNG sucio a Gemini Flash y le pide un JSON con las coordenadas
de cada placeholder COMICO_N. No requiere OCR local.

Dependencia: google-genai>=1.0.0  (pip install google-genai)
Variable de entorno: GEMINI_API_KEY
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .poster_detector_base import AbstractDetector, PlaceholderAnchor

GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
DEFAULT_MODEL = "gemini-2.5-flash"

_DETECT_PROMPT = """\
Analyze this poster image (1080x1350 pixels).
Find ALL text placeholders that look like COMICO_N (where N is a number 1, 2, 3...).
The text may appear as "COMICO_1", "COMICO 1", "comico_1", etc.

For each placeholder found, return a JSON array. Each element must have:
- "placeholder": the normalized text (e.g. "COMICO_1")
- "slot": integer N
- "center_x": horizontal center in pixels (0=left edge, 1080=right edge)
- "center_y": vertical center in pixels (0=top edge, 1350=bottom edge)
- "font_size": estimated text height in pixels
- "color": hex color of the text (e.g. "#ffffff")

Return ONLY a valid JSON array. No explanation. No markdown code fences.\
"""

# Elimina ```json ... ``` o ``` ... ``` si Gemini los añade igualmente
_FENCE_RE = re.compile(r"^```[a-z]*\n?|\n?```$", re.MULTILINE)


class GeminiDetector(AbstractDetector):
    """Detecta placeholders COMICO_N usando Gemini Flash Vision.

    Uso::

        detector = GeminiDetector()          # usa GEMINI_API_KEY del entorno
        anchors = detector.detect(Path("suxio.png"))
        # [PlaceholderAnchor(placeholder='COMICO_1', slot=1, center_x=..., ...), ...]
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        self._api_key = api_key or os.getenv(GEMINI_API_KEY_ENV)
        if not self._api_key:
            raise RuntimeError(
                f"ERR_MISSING_KEY: establece la variable de entorno {GEMINI_API_KEY_ENV}"
            )
        self._model = model

    # ── Detección ─────────────────────────────────────────────────────────────

    def detect(self, dirty_path: Path) -> list[PlaceholderAnchor]:
        """Detecta los placeholders COMICO_N usando visión de Gemini.

        Args:
            dirty_path: Ruta al PNG con los placeholders visibles.

        Returns:
            Lista de PlaceholderAnchor ordenada por slot.

        Raises:
            RuntimeError: Si la clave API falta o el JSON es malformado.
        """
        from google import genai  # noqa: PLC0415
        from google.genai import types  # noqa: PLC0415

        client = genai.Client(api_key=self._api_key)

        with open(dirty_path, "rb") as f:
            img_bytes = f.read()

        response = client.models.generate_content(
            model=self._model,
            contents=[
                types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                _DETECT_PROMPT,
            ],
        )

        raw = response.text.strip()
        raw = _FENCE_RE.sub("", raw).strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"ERR_GEMINI_PARSE: respuesta no es JSON válido — {exc}\nRaw: {raw[:200]}"
            ) from exc

        anchors: list[PlaceholderAnchor] = []
        for item in data:
            anchors.append(
                PlaceholderAnchor(
                    placeholder=str(item.get("placeholder", f"COMICO_{item['slot']}")),
                    slot=int(item["slot"]),
                    center_x=int(item["center_x"]),
                    center_y=int(item["center_y"]),
                    font_size=int(item["font_size"]),
                    color=str(item.get("color", "#ffffff")),
                )
            )

        return sorted(anchors, key=lambda a: a.slot)
