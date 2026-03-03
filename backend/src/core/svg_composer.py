"""SVG-based poster composer for lineup rendering (SDD §14.b)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape


CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
DEFAULT_BACKGROUND_COLOR = "#e61d2b"
SAFE_ZONE_TOP_Y = 400
SAFE_ZONE_BOTTOM_Y = 1100
SAFE_ZONE_HEIGHT = SAFE_ZONE_BOTTOM_Y - SAFE_ZONE_TOP_Y
LINEUP_X = 620

HEADER_RECOVA_Y = 250
HEADER_MIC_Y = 395
FOOTER_DATE_Y = 1240
FOOTER_EVENT_ID_Y = 1330

FONT_BASE_SIZE = 84
FONT_MIN_SIZE = 38
FONT_MAX_SIZE = 96
DEFAULT_FONT_ABSOLUTE_PATH = Path("/root/RECOVA/backend/assets/fonts/BebasNeue.ttf")


@dataclass(slots=True)
class NameLayout:
    """Computed text layout for each lineup name."""

    text: str
    x: int
    y: int
    font_size: int


class SVGLineupComposer:
    """Generate SVG posters and delegate PNG rasterization to CairoSVG."""

    def __init__(self, font_path: Path | None = None) -> None:
        self.font_path = font_path or DEFAULT_FONT_ABSOLUTE_PATH

    def generate_poster(self, lineup: list[dict[str, Any]], date: str, event_id: str) -> str:
        """Build an SVG poster for the provided lineup and event metadata."""
        safe_lineup = self._normalize_lineup(lineup)
        safe_date = xml_escape(str(date or "").strip() or "FECHA PENDIENTE")
        safe_event_id = xml_escape(str(event_id or "unknown-event"))

        name_layout = self._compute_name_layout(safe_lineup)
        names_svg = "\n".join(
            (
                f'<text x="{item.x}" y="{item.y}" class="comic-name" '
                f'font-size="{item.font_size}" dominant-baseline="middle">{xml_escape(item.text)}</text>'
            )
            for item in name_layout
        )

        font_uri = f"file://{self.font_path}"

        return f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{CANVAS_WIDTH}\" height=\"{CANVAS_HEIGHT}\" viewBox=\"0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}\" role=\"img\" aria-label=\"Cartel de lineup\">
  <defs>
    <pattern id=\"halftone\" x=\"0\" y=\"0\" width=\"30\" height=\"30\" patternUnits=\"userSpaceOnUse\">
      <circle cx=\"3\" cy=\"3\" r=\"3\" fill=\"#111111\" fill-opacity=\"0.45\"/>
    </pattern>
    <style>
      @font-face {{
        font-family: 'Bebas Neue';
        src: url('{font_uri}') format('truetype');
      }}
      .title {{
        font-family: 'Bebas Neue', sans-serif;
        font-size: 196px;
        fill: #ffffff;
        stroke: #111111;
        stroke-width: 8;
        paint-order: stroke;
        letter-spacing: 2px;
      }}
      .comic-name {{
        font-family: 'Bebas Neue', sans-serif;
        fill: #ffffff;
        stroke: #111111;
        stroke-width: 4;
        paint-order: stroke;
        text-transform: uppercase;
      }}
      .footer-date {{
        font-family: 'Bebas Neue', sans-serif;
        font-size: 150px;
        fill: #ffffff;
        stroke: #111111;
        stroke-width: 6;
        paint-order: stroke;
      }}
      .event-id {{
        font-family: monospace;
        font-size: 12px;
        fill: #ffffff;
        opacity: 0.35;
      }}
    </style>
  </defs>

  <!-- Layer 0: Background -->
  <rect x=\"0\" y=\"0\" width=\"{CANVAS_WIDTH}\" height=\"{CANVAS_HEIGHT}\" fill=\"{DEFAULT_BACKGROUND_COLOR}\"/>
  <rect x=\"0\" y=\"0\" width=\"{CANVAS_WIDTH}\" height=\"{CANVAS_HEIGHT}\" fill=\"url(#halftone)\"/>

  <!-- Layer 1: Graphic elements -->
  <polygon points=\"0,0 260,110 140,320 0,250\" fill=\"#fff200\"/>
  <polygon points=\"1080,0 820,110 940,320 1080,250\" fill=\"#fff200\"/>
  <polygon points=\"0,1350 220,1130 370,1350\" fill=\"#fff200\"/>
  <polygon points=\"1080,1350 860,1130 710,1350\" fill=\"#fff200\"/>

  <g transform=\"translate(160,430)\" fill=\"#111111\" fill-opacity=\"0.28\">
    <rect x=\"0\" y=\"0\" width=\"90\" height=\"430\" rx=\"38\"/>
    <rect x=\"20\" y=\"350\" width=\"50\" height=\"320\" rx=\"20\" transform=\"rotate(18 45 510)\"/>
  </g>

  <!-- Layer 2: Data -->
  <text x=\"120\" y=\"{HEADER_RECOVA_Y}\" class=\"title\">RECOVA</text>
  <text x=\"200\" y=\"{HEADER_MIC_Y}\" class=\"title\">MIC</text>
  {names_svg}

  <!-- Layer 3: Footer -->
  <text x=\"540\" y=\"{FOOTER_DATE_Y}\" class=\"footer-date\" text-anchor=\"middle\">{safe_date}</text>
  <text x=\"28\" y=\"{FOOTER_EVENT_ID_Y}\" class=\"event-id\">event_id: {safe_event_id}</text>
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
