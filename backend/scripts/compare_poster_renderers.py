"""Script de prueba del renderer de cartel (Gemini Flash).

Genera en --output:
  output_poster.png  ← render con posiciones detectadas por Gemini
  anchors.json       ← anchors detectados

Uso:
  python backend/scripts/compare_poster_renderers.py \\
    --names "Ada Torres,Bruno Gil,Clara Moreno,Diego Ruiz,Eva Sanz" \\
    --date "04 MAR" \\
    --dirty  /home/sergio/Downloads/recova-posters/pre/suxio.png \\
    --clean  /home/sergio/Downloads/recova-posters/pre/limpio.png \\
    --output /tmp/recova-test/
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from backend.src.core.poster_detector_base import PlaceholderAnchor, render_on_anchors
from backend.src.core.poster_detector_gemini import GeminiDetector

# ── Defaults ──────────────────────────────────────────────────────────────────

_ROOT           = Path(__file__).resolve().parents[2]
_DEFAULT_DIRTY  = Path("/home/sergio/Downloads/recova-posters/pre/suxio.png")
_DEFAULT_CLEAN  = Path("/home/sergio/Downloads/recova-posters/pre/limpio.png")
_DEFAULT_OUTPUT = Path("/tmp/recova-test/")
_DEFAULT_NAMES  = "Ada Torres,Bruno Gil,Clara Moreno,Diego Ruiz,Eva Sanz"
_DEFAULT_DATE   = "04 MAR"
_FONT_PATH      = _ROOT / "backend" / "assets" / "fonts" / "BebasNeue.ttf"

_DATE_ANCHOR    = (540, 1240)
_DATE_FONT_SIZE = 110


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Prueba el renderer de cartel.")
    parser.add_argument("--names",  default=_DEFAULT_NAMES)
    parser.add_argument("--date",   default=_DEFAULT_DATE)
    parser.add_argument("--dirty",  type=Path, default=_DEFAULT_DIRTY)
    parser.add_argument("--clean",  type=Path, default=_DEFAULT_CLEAN)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    names = [n.strip() for n in args.names.split(",")]

    print(f"Dirty : {args.dirty}")
    print(f"Clean : {args.clean}")
    print(f"Names : {names}")
    print(f"Date  : {args.date}")
    print(f"Output: {args.output}")

    print("\nLlamando a Gemini Flash Vision...")
    detector = GeminiDetector()
    anchors = detector.detect(args.dirty)

    print(f"Detectados {len(anchors)} placeholders:")
    for a in anchors:
        print(f"  {a.placeholder} → ({a.center_x}, {a.center_y}) fs={a.font_size} color={a.color}")

    assignments = [
        (names[i] if i < len(names) else f"CÓMICO {i+1}", anchor)
        for i, anchor in enumerate(anchors)
    ]

    output_path = args.output / "output_poster.png"
    render_on_anchors(
        clean_path=args.clean,
        assignments=assignments,
        font_path=_FONT_PATH,
        date=args.date,
        date_anchor=_DATE_ANCHOR,
        date_font_size=_DATE_FONT_SIZE,
        output_path=output_path,
    )
    print(f"\n✓ PNG guardado: {output_path}")

    anchors_file = args.output / "anchors.json"
    anchors_file.write_text(json.dumps([asdict(a) for a in anchors], indent=2, ensure_ascii=False))
    print(f"✓ Anchors guardados: {anchors_file}")


if __name__ == "__main__":
    main()
