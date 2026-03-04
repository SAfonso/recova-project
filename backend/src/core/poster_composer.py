"""Compositor de carteles con Pillow + FreeType (motor de producción).

Pipeline: PNG base limpio → estampar tipografía → PNG final.
Determinista, local, sin dependencias de red, navegador ni SVG intermedio.

Contrato de asset:
  - base_poster_clean.png → fondo gráfico puro, sin texto horneado.
  - BebasNeue.ttf         → fuente local, nunca externa.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


# ── Constantes del canvas ─────────────────────────────────────────────────────
CANVAS_W = 1080
CANVAS_H = 1350

# Safe Zone: área donde se distribuyen los nombres de cómicos.
SAFE_ZONE_TOP    = 400
SAFE_ZONE_BOTTOM = 1100
SAFE_ZONE_H      = SAFE_ZONE_BOTTOM - SAFE_ZONE_TOP
CENTER_X         = 540

# Algoritmo adaptativo de fuente (mismo contrato que SDD v2 §5).
FONT_BASE_SIZE = 84
FONT_MIN_SIZE  = 38
FONT_MAX_SIZE  = 96

# Footer
FOOTER_DATE_Y     = 1240
FOOTER_EVENT_ID_Y = 1316

# ── Estilo de texto ───────────────────────────────────────────────────────────
COMIC_FILL         = "#ffffff"
COMIC_STROKE       = "#000000"
COMIC_STROKE_WIDTH = 3

DATE_FILL        = "#ffffff"
DATE_STROKE      = "#000000"
DATE_STROKE_W    = 3
DATE_FONT_SIZE   = 100

EVENT_ID_FILL    = "#ffffff"
EVENT_ID_OPACITY = 0.35   # aplicado post-composición si se requiere
EVENT_ID_SIZE    = 22

# ── Variables de entorno ──────────────────────────────────────────────────────
FONT_ENV_VAR        = "RECOVA_FONT_PATH"
BASE_POSTER_ENV_VAR = "RECOVA_BASE_POSTER_PATH"


@dataclass(slots=True)
class NameLayout:
    """Coordenadas y tamaño de fuente calculados para cada cómico."""
    text: str
    x: int
    y: int
    font_size: int


class PosterComposer:
    """Estampa nombres de cómicos y fecha sobre un PNG de fondo limpio.

    Uso::

        composer = PosterComposer()
        path = composer.render(
            lineup=[{"name": "Ada Torres"}, {"name": "Bruno Gil"}],
            date="04 MAR",
            event_id="evt-001",
            output_path="/tmp/cartel.png",
        )
    """

    def __init__(
        self,
        font_path: Path | None = None,
        base_image_path: Path | None = None,
    ) -> None:
        self.font_path = self._resolve_font(font_path)
        self.base_image_path = self._resolve_base_image(base_image_path)
        self._validate_assets()

    # ── Resolución de assets ──────────────────────────────────────────────────

    @staticmethod
    def _resolve_font(font_path: Path | None) -> Path:
        if font_path:
            return Path(font_path)

        env_path = os.getenv(FONT_ENV_VAR)
        if env_path:
            return Path(env_path)

        project_root = Path(__file__).resolve().parents[3]
        candidates = [
            project_root / "backend" / "assets" / "fonts" / "BebasNeue.ttf",
            Path.cwd() / "backend" / "assets" / "fonts" / "BebasNeue.ttf",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return candidates[0]

    @staticmethod
    def _resolve_base_image(base_image_path: Path | None) -> Path:
        if base_image_path:
            return Path(base_image_path)

        env_path = os.getenv(BASE_POSTER_ENV_VAR)
        if env_path:
            return Path(env_path)

        project_root = Path(__file__).resolve().parents[3]
        # Preferir el PNG limpio; caer en el genérico como fallback de desarrollo.
        candidates = [
            project_root / "backend" / "assets" / "templates" / "base_poster_clean.png",
            project_root / "backend" / "assets" / "templates" / "base_poster.png",
            Path.cwd() / "backend" / "assets" / "templates" / "base_poster_clean.png",
            Path.cwd() / "backend" / "assets" / "templates" / "base_poster.png",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return candidates[0]

    def _validate_assets(self) -> None:
        for name, path in (
            ("font", self.font_path),
            ("base_poster", self.base_image_path),
        ):
            if not Path(path).is_file():
                raise RuntimeError(f"ERR_ASSET_MISSING: {name} → {path}")

    # ── Layout adaptativo ─────────────────────────────────────────────────────

    def _compute_layout(self, names: list[str]) -> list[NameLayout]:
        n = len(names)
        if n == 0:
            return []

        slot_h = SAFE_ZONE_H / n
        max_font_for_slot = int(slot_h * 0.70)

        if n > 5:
            proportional = int(round(FONT_BASE_SIZE * (5 / n)))
            font_size = min(max_font_for_slot, proportional)
        else:
            font_size = min(max_font_for_slot, FONT_BASE_SIZE)

        font_size = max(FONT_MIN_SIZE, min(FONT_MAX_SIZE, font_size))

        return [
            NameLayout(
                text=name,
                x=CENTER_X,
                y=int(round(SAFE_ZONE_TOP + slot_h * (i + 0.5))),
                font_size=font_size,
            )
            for i, name in enumerate(names)
        ]

    @staticmethod
    def _normalize_lineup(lineup: list[dict[str, Any]] | Any) -> list[str]:
        if not isinstance(lineup, list):
            return ["LINEUP PENDIENTE"]
        names = []
        for item in lineup[:8]:
            name = str(item.get("name", "")).strip().upper() if isinstance(item, dict) else ""
            if name:
                names.append(name)
        return names or ["LINEUP PENDIENTE"]

    # ── Helpers de tipografía ─────────────────────────────────────────────────

    def _font(self, size: int) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(str(self.font_path), size=size)

    @staticmethod
    def _draw_outlined_text(
        draw: ImageDraw.ImageDraw,
        xy: tuple[int, int],
        text: str,
        font: ImageFont.FreeTypeFont,
        fill: str,
        stroke_fill: str,
        stroke_width: int,
        anchor: str = "mm",
    ) -> None:
        draw.text(
            xy=xy,
            text=text,
            font=font,
            fill=fill,
            stroke_fill=stroke_fill,
            stroke_width=stroke_width,
            anchor=anchor,
        )

    # ── Motor de render ───────────────────────────────────────────────────────

    def render(
        self,
        lineup: list[dict[str, Any]],
        date: str,
        event_id: str,
        output_path: str | Path,
    ) -> Path:
        """Genera el cartel PNG final.

        Args:
            lineup:      Lista de dicts con clave ``"name"``.
            date:        Texto de fecha visible en el cartel (ej. ``"04 MAR"``).
            event_id:    Identificador del evento para el footer discreto.
            output_path: Ruta absoluta de destino del PNG generado.

        Returns:
            Path del PNG generado.

        Raises:
            RuntimeError: Si algún asset obligatorio no existe (``ERR_ASSET_MISSING``).
            AssertionError: Si el PNG base no tiene las dimensiones esperadas.
        """
        img = Image.open(self.base_image_path).convert("RGB")
        assert img.size == (CANVAS_W, CANVAS_H), (
            f"ERR_CANVAS_SIZE: esperado {CANVAS_W}x{CANVAS_H}, encontrado {img.size}"
        )

        draw = ImageDraw.Draw(img)

        # ── Capa 1: Nombres de cómicos (Safe Zone Y=400..1100) ────────────────
        names = self._normalize_lineup(lineup)
        for item in self._compute_layout(names):
            self._draw_outlined_text(
                draw=draw,
                xy=(item.x, item.y),
                text=item.text,
                font=self._font(item.font_size),
                fill=COMIC_FILL,
                stroke_fill=COMIC_STROKE,
                stroke_width=COMIC_STROKE_WIDTH,
            )

        # ── Capa 2: Fecha del evento (footer principal) ───────────────────────
        safe_date = str(date or "").strip().upper() or "FECHA PENDIENTE"
        self._draw_outlined_text(
            draw=draw,
            xy=(CENTER_X, FOOTER_DATE_Y),
            text=safe_date,
            font=self._font(DATE_FONT_SIZE),
            fill=DATE_FILL,
            stroke_fill=DATE_STROKE,
            stroke_width=DATE_STROKE_W,
        )

        # ── Capa 3: Event ID discreto (footer inferior) ───────────────────────
        draw.text(
            xy=(28, FOOTER_EVENT_ID_Y),
            text=f"event_id: {event_id}",
            font=self._font(EVENT_ID_SIZE),
            fill=EVENT_ID_FILL,
            anchor="lm",
        )

        # ── Guardar ───────────────────────────────────────────────────────────
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(destination), format="PNG", optimize=False)
        return destination
