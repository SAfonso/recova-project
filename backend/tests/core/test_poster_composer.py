"""Tests unitarios para PosterComposer (motor Pillow + FreeType)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from backend.src.core.poster_composer import (
    CANVAS_H,
    CANVAS_W,
    FONT_BASE_SIZE,
    FONT_MAX_SIZE,
    FONT_MIN_SIZE,
    SAFE_ZONE_BOTTOM,
    SAFE_ZONE_TOP,
    NameLayout,
    PosterComposer,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_composer(tmp_path: Path) -> PosterComposer:
    """PosterComposer con assets mínimos válidos (no render real)."""
    font_path = tmp_path / "BebasNeue.ttf"
    base_path = tmp_path / "base_poster.png"

    # Fuente mínima válida para FreeType
    font_path.write_bytes(b"\x00" * 12)

    # PNG mínimo 1080x1350 RGB
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), color=(162, 6, 39))
    img.save(str(base_path), format="PNG")

    return PosterComposer(font_path=font_path, base_image_path=base_path)


# ── Tests de resolución de assets ─────────────────────────────────────────────

def test_raises_err_asset_missing_when_font_absent(tmp_path: Path) -> None:
    base_path = tmp_path / "base_poster.png"
    Image.new("RGB", (CANVAS_W, CANVAS_H)).save(str(base_path))

    with pytest.raises(RuntimeError, match="ERR_ASSET_MISSING"):
        PosterComposer(
            font_path=tmp_path / "missing.ttf",
            base_image_path=base_path,
        )


def test_raises_err_asset_missing_on_init(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="ERR_ASSET_MISSING"):
        PosterComposer(
            font_path=tmp_path / "no_font.ttf",
            base_image_path=tmp_path / "no_poster.png",
        )


def test_env_var_font_path_is_respected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    font = tmp_path / "env_font.ttf"
    font.write_bytes(b"\x00" * 12)
    monkeypatch.setenv("RECOVA_FONT_PATH", str(font))
    resolved = PosterComposer._resolve_font(None)
    assert resolved == font


def test_env_var_base_poster_is_respected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    poster = tmp_path / "env_poster.png"
    Image.new("RGB", (CANVAS_W, CANVAS_H)).save(str(poster))
    monkeypatch.setenv("RECOVA_BASE_POSTER_PATH", str(poster))
    resolved = PosterComposer._resolve_base_image(None)
    assert resolved == poster


# ── Tests de normalización de lineup ─────────────────────────────────────────

def test_normalize_lineup_uppercases_names() -> None:
    names = PosterComposer._normalize_lineup([{"name": "Ada Torres"}, {"name": "bruno gil"}])
    assert names == ["ADA TORRES", "BRUNO GIL"]


def test_normalize_lineup_strips_empty_names() -> None:
    names = PosterComposer._normalize_lineup([{"name": ""}, {"name": "  "}, {"name": "Diego"}])
    assert names == ["DIEGO"]


def test_normalize_lineup_caps_at_eight() -> None:
    lineup = [{"name": f"Comic {i}"} for i in range(12)]
    names = PosterComposer._normalize_lineup(lineup)
    assert len(names) == 8


def test_normalize_lineup_returns_fallback_for_invalid_input() -> None:
    assert PosterComposer._normalize_lineup("bad") == ["LINEUP PENDIENTE"]
    assert PosterComposer._normalize_lineup([]) == ["LINEUP PENDIENTE"]
    assert PosterComposer._normalize_lineup(None) == ["LINEUP PENDIENTE"]  # type: ignore[arg-type]


# ── Tests del algoritmo de layout (Safe Zone) ─────────────────────────────────

def test_layout_y_positions_stay_inside_safe_zone() -> None:
    composer_cls = PosterComposer
    for n in range(1, 9):
        names = [f"COMIC {i}" for i in range(n)]
        layout = PosterComposer.__new__(PosterComposer)  # sin __init__
        items = layout._compute_layout(names)  # type: ignore[attr-defined]
        for item in items:
            assert SAFE_ZONE_TOP <= item.y <= SAFE_ZONE_BOTTOM, (
                f"n={n}: y={item.y} fuera de Safe Zone [{SAFE_ZONE_TOP}..{SAFE_ZONE_BOTTOM}]"
            )


def test_layout_font_size_within_clamp_bounds() -> None:
    layout = PosterComposer.__new__(PosterComposer)
    for n in range(1, 9):
        names = [f"C{i}" for i in range(n)]
        items = layout._compute_layout(names)  # type: ignore[attr-defined]
        for item in items:
            assert FONT_MIN_SIZE <= item.font_size <= FONT_MAX_SIZE


def test_font_size_decreases_above_five() -> None:
    layout = PosterComposer.__new__(PosterComposer)
    items_five = layout._compute_layout([f"C{i}" for i in range(5)])  # type: ignore[attr-defined]
    items_eight = layout._compute_layout([f"C{i}" for i in range(8)])  # type: ignore[attr-defined]
    assert items_eight[0].font_size < items_five[0].font_size


def test_layout_slot_spacing_decreases_with_more_comics() -> None:
    layout = PosterComposer.__new__(PosterComposer)
    items_3 = layout._compute_layout(["A", "B", "C"])  # type: ignore[attr-defined]
    items_6 = layout._compute_layout(["A", "B", "C", "D", "E", "F"])  # type: ignore[attr-defined]
    gap_3 = items_3[1].y - items_3[0].y
    gap_6 = items_6[1].y - items_6[0].y
    assert gap_3 > gap_6


def test_layout_returns_empty_for_empty_names() -> None:
    layout = PosterComposer.__new__(PosterComposer)
    assert layout._compute_layout([]) == []  # type: ignore[attr-defined]


# ── Test de render real (requiere assets válidos) ─────────────────────────────

def test_render_produces_valid_png(tmp_path: Path) -> None:
    """Render completo con PIL real (sin mock de fuente)."""
    project_root = Path(__file__).resolve().parents[3]
    font_path = project_root / "backend" / "assets" / "fonts" / "BebasNeue.ttf"
    base_path = project_root / "backend" / "assets" / "templates" / "base_poster.png"

    if not font_path.is_file() or not base_path.is_file():
        pytest.skip("Assets reales no disponibles en este entorno")

    composer = PosterComposer(font_path=font_path, base_image_path=base_path)
    output = tmp_path / "test_cartel.png"

    result = composer.render(
        lineup=[
            {"name": "Ada Torres"},
            {"name": "Bruno Gil"},
            {"name": "Clara Moreno"},
        ],
        date="04 MAR",
        event_id="test-evt-001",
        output_path=output,
    )

    assert result == output
    assert output.exists()
    assert output.stat().st_size > 0

    with Image.open(output) as img:
        assert img.size == (CANVAS_W, CANVAS_H)
        assert img.format == "PNG"


def test_render_respects_canvas_size_assertion(tmp_path: Path) -> None:
    """Si el PNG base no es 1080x1350, debe lanzar AssertionError."""
    font_path = tmp_path / "font.ttf"
    font_path.write_bytes(b"\x00" * 12)
    wrong_size_png = tmp_path / "wrong.png"
    Image.new("RGB", (800, 600)).save(str(wrong_size_png))

    composer = PosterComposer(font_path=font_path, base_image_path=wrong_size_png)

    with pytest.raises(AssertionError, match="ERR_CANVAS_SIZE"):
        composer.render(
            lineup=[{"name": "Test"}],
            date="01 ENE",
            event_id="evt-size-check",
            output_path=tmp_path / "out.png",
        )
