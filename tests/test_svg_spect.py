from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.src.core.svg_composer import SVGLineupComposer, export_to_png


OUTPUT_DIR = ROOT_DIR / "tests" / "output"


def _is_usable_font(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _resolve_font_path() -> Path | None:
    candidates = (
        ROOT_DIR / "backend" / "assets" / "fonts" / "BebasNeue.ttf",
        Path.cwd() / "backend" / "assets" / "fonts" / "BebasNeue.ttf",
        Path.cwd() / "assets" / "fonts" / "BebasNeue.ttf",
    )
    for candidate in candidates:
        if _is_usable_font(candidate):
            return candidate
    return None


def _resolve_base_image_path() -> Path | None:
    candidates = (
        ROOT_DIR / "backend" / "assets" / "templates" / "base_poster.png",
        Path.cwd() / "backend" / "assets" / "templates" / "base_poster.png",
        Path.cwd() / "assets" / "templates" / "base_poster.png",
    )
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def _build_lineups() -> dict[str, list[dict[str, str]]]:
    long_name = "MAXIMILIANO DE LA ROSA Y COMPAÑÍA"
    return {
        "test_3.png": [
            {"name": "LUCÍA PÉREZ", "instagram": "luciaperez"},
            {"name": long_name, "instagram": "maxdelarosa"},
            {"name": "DIEGO MORA", "instagram": "diegomora"},
        ],
        "test_5.png": [
            {"name": "LUCÍA PÉREZ", "instagram": "luciaperez"},
            {"name": long_name, "instagram": "maxdelarosa"},
            {"name": "DIEGO MORA", "instagram": "diegomora"},
            {"name": "ANA RUIZ", "instagram": "anaruiz"},
            {"name": "JORGE SANTOS", "instagram": "jorgesantos"},
        ],
        "test_8.png": [
            {"name": "LUCÍA PÉREZ", "instagram": "luciaperez"},
            {"name": long_name, "instagram": "maxdelarosa"},
            {"name": "DIEGO MORA", "instagram": "diegomora"},
            {"name": "ANA RUIZ", "instagram": "anaruiz"},
            {"name": "JORGE SANTOS", "instagram": "jorgesantos"},
            {"name": "MARÍA LÓPEZ", "instagram": "marialopez"},
            {"name": "ALBERTO VEGA", "instagram": "albertovega"},
            {"name": "CLARA ROMÁN", "instagram": "clararoman"},
        ],
    }


def run_svg_spect() -> bool:
    font_path = _resolve_font_path()
    if font_path is None:
        print(
            "FAIL: fuente no encontrada en rutas esperadas: "
            "backend/assets/fonts/BebasNeue.ttf"
        )
        return False
    base_image_path = _resolve_base_image_path()
    if base_image_path is None:
        print(
            "FAIL: base poster no encontrado en rutas esperadas: "
            "backend/assets/templates/base_poster.png"
        )
        return False

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    composer = SVGLineupComposer(font_path=font_path, base_image_path=base_image_path)

    for filename, lineup in _build_lineups().items():
        output_path = OUTPUT_DIR / filename
        try:
            svg = composer.generate_poster(
                lineup=lineup,
                date="2026-03-03",
                event_id=f"spect-{output_path.stem}",
            )
            export_to_png(svg, output_path)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: {filename} -> {exc}")
            return False

        if not output_path.exists() or output_path.stat().st_size == 0:
            print(f"FAIL: {filename} no se generó correctamente")
            return False

    print("PASS")
    return True


if __name__ == "__main__":
    sys.exit(0 if run_svg_spect() else 1)
