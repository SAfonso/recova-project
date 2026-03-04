"""SVG-based poster composer for lineup rendering (SDD §14.b)."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape


CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
SAFE_ZONE_TOP_Y = 400
SAFE_ZONE_BOTTOM_Y = 1100
SAFE_ZONE_HEIGHT = SAFE_ZONE_BOTTOM_Y - SAFE_ZONE_TOP_Y
LINEUP_X = 540

FOOTER_DATE_Y = 1240
FOOTER_EVENT_ID_Y = 1330

FONT_BASE_SIZE = 84
FONT_MIN_SIZE = 38
FONT_MAX_SIZE = 96
FONT_ENV_VAR = "RECOVA_FONT_PATH"
DEFAULT_FONT_RELATIVE_PATH = Path("backend/assets/fonts/BebasNeue.ttf")
DEFAULT_BASE_POSTER_PATH = Path("/root/RECOVA/backend/assets/templates/base_poster.png")


@dataclass(slots=True)
class NameLayout:
    """Computed text layout for each lineup name."""

    text: str
    x: int
    y: int
    font_size: int


class SVGLineupComposer:
    """Generate SVG posters and delegate PNG rasterization to CairoSVG."""

    def __init__(self, font_path: Path | None = None, base_image_path: Path | None = None) -> None:
        self.font_path = self._resolve_font_path(font_path)
        self.base_image_path = Path(base_image_path) if base_image_path else DEFAULT_BASE_POSTER_PATH
        self._base_image_base64: str | None = None
        self._font_base64: str | None = None

    @staticmethod
    def _resolve_font_path(font_path: Path | None) -> Path:
        if font_path is not None:
            return Path(font_path).expanduser()

        env_font_path = os.getenv(FONT_ENV_VAR)
        if env_font_path:
            return Path(env_font_path).expanduser()

        project_root = Path(__file__).resolve().parents[3]
        candidates = (
            project_root / DEFAULT_FONT_RELATIVE_PATH,
            Path.cwd() / DEFAULT_FONT_RELATIVE_PATH,
            Path.cwd() / "assets" / "fonts" / "BebasNeue.ttf",
        )

        for candidate in candidates:
            try:
                if candidate.is_file():
                    return candidate
            except OSError:
                continue

        # Last-resort reference: path relativa al repo para no acoplar entornos.
        return project_root / DEFAULT_FONT_RELATIVE_PATH

    def _validate_required_assets(self) -> None:
        required_assets = (
            ("font", self.font_path),
            ("base_poster_png", self.base_image_path),
        )
        for asset_name, asset_path in required_assets:
            if not os.path.exists(str(asset_path)):
                raise RuntimeError(f"ERR_ASSET_MISSING: {asset_name} -> {asset_path}")

    def _get_base64_image(self, path: Path) -> str:
        with Path(path).open("rb") as file_obj:
            return base64.b64encode(file_obj.read()).decode("utf-8")

    def _get_base64_font(self, path: Path) -> str:
        with Path(path).open("rb") as file_obj:
            return base64.b64encode(file_obj.read()).decode("utf-8")

    def generate_poster(self, lineup: list[dict[str, Any]], date: str, event_id: str) -> str:
        """Build an SVG poster for the provided lineup and event metadata."""
        self._validate_required_assets()
        if self._base_image_base64 is None:
            self._base_image_base64 = self._get_base64_image(self.base_image_path)
        if self._font_base64 is None:
            self._font_base64 = self._get_base64_font(self.font_path)

        safe_lineup = self._normalize_lineup(lineup)
        safe_date = xml_escape(str(date or "").strip() or "FECHA PENDIENTE")
        safe_event_id = xml_escape(str(event_id or "unknown-event"))

        name_layout = self._compute_name_layout(safe_lineup)
        names_svg = "\n".join(
            (
                f'<text data-text-role="comic-name" x="{item.x}" y="{item.y}" '
                f'font-family="\'Bebas Neue\', sans-serif" font-size="{item.font_size}" '
                f'fill="#ffffff" stroke="#000000" stroke-width="3" paint-order="stroke" '
                f'dominant-baseline="middle" text-anchor="middle" '
                f'textLength="900" lengthAdjust="spacingAndGlyphs">'
                f"{xml_escape(item.text)}</text>"
            )
            for item in name_layout
        )

        font_uri = f"data:font/ttf;base64,{self._font_base64}"
        base_image_uri = f"data:image/png;base64,{self._base_image_base64}"

        return f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<svg xmlns=\"http://www.w3.org/2000/svg\" xmlns:xlink=\"http://www.w3.org/1999/xlink\" width=\"{CANVAS_WIDTH}\" height=\"{CANVAS_HEIGHT}\" viewBox=\"0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}\" role=\"img\" aria-label=\"Cartel de lineup\">
  <image xlink:href=\"{base_image_uri}\" x=\"0\" y=\"0\" width=\"{CANVAS_WIDTH}\" height=\"{CANVAS_HEIGHT}\" preserveAspectRatio=\"xMidYMid slice\"/>
  <g id=\"overlay-text\">
    <style>
      @font-face {{
        font-family: 'Bebas Neue';
        src: url('{font_uri}') format('truetype');
      }}
    </style>
    {names_svg}
    <text x=\"540\" y=\"{FOOTER_DATE_Y}\" font-family=\"'Bebas Neue', sans-serif\" font-size=\"150\" fill=\"#ffffff\" stroke=\"#000000\" stroke-width=\"3\" paint-order=\"stroke\" text-anchor=\"middle\">{safe_date}</text>
    <text x=\"28\" y=\"{FOOTER_EVENT_ID_Y}\" font-family=\"'Bebas Neue', sans-serif\" font-size=\"24\" fill=\"#ffffff\" opacity=\"0.35\">event_id: {safe_event_id}</text>
  </g>
</svg>
"""

    def _normalize_lineup(self, lineup: list[dict[str, Any]] | Any) -> list[str]:
        if not isinstance(lineup, list):
            return ["LINEUP PENDIENTE"]

        normalized: list[str] = []
        for item in lineup[:8]:
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip()
            else:
                name = ""
            if name:
                normalized.append(name.upper())

        return normalized or ["LINEUP PENDIENTE"]

    def _compute_name_layout(self, lineup_names: list[str]) -> list[NameLayout]:
        count = len(lineup_names)
        if count <= 0:
            return []

        # Safe Zone rule: all comic names live strictly inside Y=400..1100.
        slot_height = SAFE_ZONE_HEIGHT / count
        max_font_for_slot = int(slot_height * 0.70)

        if count > 5:
            # Proportional reduction when N > 5 (SDD v2 requirement).
            proportional_font = int(round(FONT_BASE_SIZE * (5 / count)))
            font_size = min(max_font_for_slot, proportional_font)
        else:
            font_size = min(max_font_for_slot, FONT_BASE_SIZE)

        font_size = max(FONT_MIN_SIZE, min(FONT_MAX_SIZE, font_size))

        layout: list[NameLayout] = []
        for idx, name in enumerate(lineup_names):
            y_center = SAFE_ZONE_TOP_Y + slot_height * (idx + 0.5)
            layout.append(
                NameLayout(
                    text=name,
                    x=LINEUP_X,
                    y=int(round(y_center)),
                    font_size=font_size,
                )
            )

        return layout


def export_to_png(svg_string: str, output_path: str | Path) -> Path:
    """Rasterize an SVG string into PNG using CairoSVG."""
    try:
        import cairosvg
    except ModuleNotFoundError as exc:  # pragma: no cover - depende de entorno.
        raise RuntimeError("CairoSVG no está instalado. Instala 'cairosvg' para exportar PNG.") from exc

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    cairosvg.svg2png(
        bytestring=svg_string.encode("utf-8"),
        write_to=str(destination),
        output_width=CANVAS_WIDTH,
        output_height=CANVAS_HEIGHT,
    )
    return destination
