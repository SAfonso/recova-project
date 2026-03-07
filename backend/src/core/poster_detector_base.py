"""Tipos y contrato compartido para los detectores de placeholders en carteles.

Ambas variantes (OCR y Gemini) implementan AbstractDetector y devuelven
una lista de PlaceholderAnchor que luego render_on_anchors usa para
estampar los nombres reales sobre el PNG limpio.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


# ── Contrato de tipos ─────────────────────────────────────────────────────────

@dataclass(slots=True)
class PlaceholderAnchor:
    """Posición y estilo detectados para un placeholder COMICO_N."""

    placeholder: str  # e.g. "COMICO_1"
    slot: int         # 1-based
    center_x: int     # px desde izquierda
    center_y: int     # px desde arriba
    font_size: int    # altura estimada en px
    color: str = "#ffffff"


class AbstractDetector(ABC):
    """Interfaz común para todos los detectores de placeholders."""

    @abstractmethod
    def detect(self, dirty_path: Path) -> list[PlaceholderAnchor]:
        """Detecta los placeholders COMICO_N en el PNG sucio.

        Args:
            dirty_path: Ruta al PNG con los placeholders visibles.

        Returns:
            Lista de PlaceholderAnchor ordenada por slot (1, 2, 3...).
            Lista vacía si no se detecta ningún placeholder.
        """


# ── Motor de render basado en anchors ────────────────────────────────────────

STROKE_FILL  = "#000000"
STROKE_WIDTH = 3


def render_on_anchors(
    clean_path: Path,
    assignments: list[tuple[str, PlaceholderAnchor]],
    font_path: Path,
    date: str,
    date_anchor: tuple[int, int],
    date_font_size: int,
    output_path: Path,
) -> Path:
    """Renderiza nombres sobre el PNG limpio usando las posiciones detectadas.

    Args:
        clean_path:     PNG de fondo sin texto de cómicos.
        assignments:    Pares (nombre, anchor) — uno por cómico.
        font_path:      Ruta al .ttf/.otf a usar.
        date:           Texto de fecha (e.g. "04 MAR").
        date_anchor:    (center_x, center_y) de la fecha en px.
        date_font_size: Tamaño de fuente para la fecha en px.
        output_path:    Destino del PNG generado.

    Returns:
        Path del PNG generado.
    """
    img = Image.open(clean_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    for name, anchor in assignments:
        font = ImageFont.truetype(str(font_path), size=anchor.font_size)
        draw.text(
            xy=(anchor.center_x, anchor.center_y),
            text=name.upper(),
            font=font,
            fill=anchor.color,
            stroke_fill=STROKE_FILL,
            stroke_width=STROKE_WIDTH,
            anchor="mm",
        )

    # Fecha
    date_font = ImageFont.truetype(str(font_path), size=date_font_size)
    draw.text(
        xy=date_anchor,
        text=date.upper(),
        font=date_font,
        fill="#ffffff",
        stroke_fill=STROKE_FILL,
        stroke_width=STROKE_WIDTH,
        anchor="mm",
    )

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(destination), format="PNG", optimize=False)
    return destination
