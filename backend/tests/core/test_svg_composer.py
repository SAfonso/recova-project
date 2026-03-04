from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.src.core.svg_composer import (
    FOOTER_DATE_Y,
    SAFE_ZONE_BOTTOM_Y,
    SAFE_ZONE_TOP_Y,
    SVGLineupComposer,
)


def _extract_y_values(svg: str) -> list[int]:
    y_matches = re.findall(r'<text data-text-role="comic-name" x="540" y="(\d+)"', svg)
    return [int(value) for value in y_matches]


def _extract_font_sizes(svg: str) -> list[int]:
    size_matches = re.findall(r'data-text-role="comic-name" x="540" y="\d+" font-family="\'Bebas Neue\', sans-serif" font-size="(\d+)"', svg)
    return [int(value) for value in size_matches]


def _build_composer(tmp_path: Path) -> SVGLineupComposer:
    font_path = tmp_path / "BebasNeue.ttf"
    base_image_path = tmp_path / "base_poster.png"
    font_path.write_bytes(b"fake-font")
    base_image_path.write_bytes(b"fake-png")
    return SVGLineupComposer(font_path=font_path, base_image_path=base_image_path)


def test_generate_poster_includes_required_layers_and_assets(tmp_path: Path) -> None:
    composer = _build_composer(tmp_path)
    svg = composer.generate_poster(
        lineup=[{"name": "Ada Torres"}, {"name": "Bruno Gil"}],
        date="2026-03-10",
        event_id="evt-123",
    )

    assert 'width="1080" height="1350"' in svg
    assert 'xmlns:xlink="http://www.w3.org/1999/xlink"' in svg
    assert '<image xlink:href="data:image/png;base64,' in svg
    assert '<pattern id="halftone"' not in svg
    assert "<polygon" not in svg
    assert '<rect x="0" y="0"' not in svg
    assert "data:font/ttf;base64," in svg
    assert "file://" not in svg
    assert "ADA TORRES" in svg
    assert "BRUNO GIL" in svg
    assert 'data-text-role="comic-name"' in svg
    assert 'text-anchor="middle"' in svg
    assert 'textLength="900"' in svg
    assert 'lengthAdjust="spacingAndGlyphs"' in svg
    assert '<g id="overlay-text">' in svg
    assert 'fill="#ffffff"' in svg
    assert 'stroke="#000000"' in svg
    assert 'stroke-width="3"' in svg
    assert 'opacity="0.35"' in svg
    assert "2026-03-10" in svg
    assert f'y="{FOOTER_DATE_Y}"' in svg


def test_base_image_is_painted_before_text_overlay(tmp_path: Path) -> None:
    composer = _build_composer(tmp_path)
    svg = composer.generate_poster(
        lineup=[{"name": "Ada Torres"}, {"name": "Bruno Gil"}],
        date="2026-03-10",
        event_id="evt-order",
    )

    image_idx = svg.index('<image xlink:href="data:image/png;base64,')
    overlay_idx = svg.index('<g id="overlay-text">')
    name_idx = svg.index("ADA TORRES")
    date_idx = svg.index("2026-03-10")

    assert image_idx < overlay_idx
    assert image_idx < name_idx
    assert image_idx < date_idx
    assert '<rect x="0" y="0" width="1080" height="1350"' not in svg


def test_layout_spacing_is_larger_for_three_than_six_names(tmp_path: Path) -> None:
    composer = _build_composer(tmp_path)

    svg_three = composer.generate_poster(
        lineup=[{"name": "A"}, {"name": "B"}, {"name": "C"}],
        date="2026-03-10",
        event_id="evt-three",
    )
    svg_six = composer.generate_poster(
        lineup=[
            {"name": "A"},
            {"name": "B"},
            {"name": "C"},
            {"name": "D"},
            {"name": "E"},
            {"name": "F"},
        ],
        date="2026-03-10",
        event_id="evt-six",
    )

    y_three = _extract_y_values(svg_three)
    y_six = _extract_y_values(svg_six)

    assert len(y_three) == 3
    assert len(y_six) == 6

    gap_three = y_three[1] - y_three[0]
    gap_six = y_six[1] - y_six[0]

    assert gap_three > gap_six


def test_lineup_fallback_when_empty_or_invalid(tmp_path: Path) -> None:
    composer = _build_composer(tmp_path)

    svg_empty = composer.generate_poster(lineup=[], date="2026-03-10", event_id="evt-empty")
    svg_invalid = composer.generate_poster(lineup="invalid", date="2026-03-10", event_id="evt-invalid")

    assert "LINEUP PENDIENTE" in svg_empty
    assert "LINEUP PENDIENTE" in svg_invalid


def test_all_comic_y_positions_stay_inside_safe_zone(tmp_path: Path) -> None:
    composer = _build_composer(tmp_path)
    svg = composer.generate_poster(
        lineup=[
            {"name": "A"},
            {"name": "B"},
            {"name": "C"},
            {"name": "D"},
            {"name": "E"},
            {"name": "F"},
            {"name": "G"},
            {"name": "H"},
        ],
        date="2026-03-10",
        event_id="evt-safe-zone",
    )

    y_values = _extract_y_values(svg)
    assert len(y_values) == 8
    assert min(y_values) >= SAFE_ZONE_TOP_Y
    assert max(y_values) <= SAFE_ZONE_BOTTOM_Y


def test_font_size_reduces_when_count_above_five(tmp_path: Path) -> None:
    composer = _build_composer(tmp_path)

    svg_five = composer.generate_poster(
        lineup=[{"name": "A"}, {"name": "B"}, {"name": "C"}, {"name": "D"}, {"name": "E"}],
        date="2026-03-10",
        event_id="evt-five",
    )
    svg_six = composer.generate_poster(
        lineup=[{"name": "A"}, {"name": "B"}, {"name": "C"}, {"name": "D"}, {"name": "E"}, {"name": "F"}],
        date="2026-03-10",
        event_id="evt-six-font",
    )

    font_size_five = _extract_font_sizes(svg_five)[0]
    font_size_six = _extract_font_sizes(svg_six)[0]
    assert font_size_six < font_size_five


def test_raise_err_asset_missing_when_required_assets_are_absent(tmp_path: Path) -> None:
    missing_font = tmp_path / "missing_font.ttf"
    missing_base = tmp_path / "missing_base_poster.png"
    composer = SVGLineupComposer(font_path=missing_font, base_image_path=missing_base)

    with pytest.raises(RuntimeError, match="ERR_ASSET_MISSING"):
        composer.generate_poster(
            lineup=[{"name": "Ada Torres"}],
            date="2026-03-10",
            event_id="evt-missing-assets",
        )


def test_assets_are_base64_cached_after_first_generation(tmp_path: Path) -> None:
    composer = _build_composer(tmp_path)
    image_reads = 0
    font_reads = 0

    original_get_image = composer._get_base64_image
    original_get_font = composer._get_base64_font

    def counting_image(path: Path) -> str:
        nonlocal image_reads
        image_reads += 1
        return original_get_image(path)

    def counting_font(path: Path) -> str:
        nonlocal font_reads
        font_reads += 1
        return original_get_font(path)

    composer._get_base64_image = counting_image
    composer._get_base64_font = counting_font

    composer.generate_poster(
        lineup=[{"name": "Ada Torres"}, {"name": "Bruno Gil"}],
        date="2026-03-10",
        event_id="evt-cache-1",
    )
    composer.generate_poster(
        lineup=[{"name": "Ada Torres"}, {"name": "Bruno Gil"}],
        date="2026-03-11",
        event_id="evt-cache-2",
    )

    assert image_reads == 1
    assert font_reads == 1
