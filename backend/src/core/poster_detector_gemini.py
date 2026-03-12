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
from typing import Any

from .poster_detector_base import AbstractDetector, PlaceholderAnchor

GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
DEFAULT_MODEL = "gemini-2.5-flash"

_DETECT_PROMPT_TEMPLATE = """\
Analyze this poster image ({width}x{height} pixels).

Find ALL of these placeholders:
1. Comic name placeholders: text like COMICO_1, COMICO_2, COMICO 1, comico_1, etc.
2. Date placeholder: text like "Fecha", "FECHA", "DATE", "DD/MM", or any obvious date placeholder.

Return a JSON object with exactly two keys:
- "font_name": the font family name used for the placeholder text (e.g. "Bebas Neue", "Impact", "Montserrat"). Use the most common/recognizable name. If unsure, return "".
- "placeholders": a JSON array where each element has:
  - "placeholder": the exact text found (e.g. "COMICO_1" or "Fecha")
  - "slot": for COMICO_N use the integer N; for the date placeholder use 0
  - "center_x": horizontal center in pixels (0=left edge, {width}=right edge)
  - "center_y": vertical center in pixels (0=top edge, {height}=bottom edge)
  - "font_size": estimated text height in pixels
  - "color": hex color of the text (e.g. "#ffffff")

Return ONLY valid JSON. No explanation. No markdown code fences.\
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
        """Detecta los placeholders COMICO_N y Fecha usando visión de Gemini.

        Args:
            dirty_path: Ruta al PNG con los placeholders visibles.

        Returns:
            Lista de PlaceholderAnchor ordenada por slot (0=fecha, 1..N=cómicos).

        Raises:
            RuntimeError: Si la clave API falta o el JSON es malformado.
        """
        from google import genai  # noqa: PLC0415
        from google.genai import types  # noqa: PLC0415
        from PIL import Image as _Image  # noqa: PLC0415

        # Leer dimensiones reales de la imagen para el prompt
        with _Image.open(dirty_path) as _img:
            width, height = _img.size

        prompt = _DETECT_PROMPT_TEMPLATE.format(width=width, height=height)

        client = genai.Client(api_key=self._api_key)

        with open(dirty_path, "rb") as f:
            img_bytes = f.read()

        response = client.models.generate_content(
            model=self._model,
            contents=[
                types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                prompt,
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

        # Soporte formato nuevo {font_name, placeholders} y legacy array
        if isinstance(data, dict):
            font_name = str(data.get("font_name", ""))
            items = data.get("placeholders", data.get("anchors", []))
        else:
            font_name = ""
            items = data

        anchors: list[PlaceholderAnchor] = []
        for item in items:
            anchors.append(
                PlaceholderAnchor(
                    placeholder=str(item.get("placeholder", f"COMICO_{item['slot']}")),
                    slot=int(item["slot"]),
                    center_x=int(item["center_x"]),
                    center_y=int(item["center_y"]),
                    font_size=int(item["font_size"]),
                    color=str(item.get("color", "#ffffff")),
                    font_name=font_name,
                )
            )

        anchors = sorted(anchors, key=lambda a: a.slot)

        # Si Gemini no devolvió font_name, hacer una segunda llamada ligera
        if not font_name and anchors:
            font_name = self._detect_font_name(client, img_bytes) or ""
            for a in anchors:
                a.font_name = font_name

        return anchors

    def _detect_font_name(self, client: Any, img_bytes: bytes) -> str:
        """Llamada secundaria a Gemini para identificar solo el nombre de fuente."""
        try:
            from google.genai import types as _types  # noqa: PLC0415
            resp = client.models.generate_content(
                model=self._model,
                contents=[
                    _types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                    "What is the font family name used for the text in this image? "
                    "Reply with ONLY the font name (e.g. 'Bangers', 'Impact'). "
                    "No explanation, no quotes.",
                ],
            )
            return resp.text.strip().strip('"').strip("'")
        except Exception:
            return ""
