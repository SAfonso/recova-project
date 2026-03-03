from __future__ import annotations

import re

from backend.src.core.svg_composer import (
    FOOTER_DATE_Y,
    HEADER_MIC_Y,
    HEADER_RECOVA_Y,
    SAFE_ZONE_BOTTOM_Y,
    SAFE_ZONE_TOP_Y,
    SVGLineupComposer,
)


def _extract_y_values(svg: str) -> list[int]:
    y_matches = re.findall(r'<text x="620" y="(\d+)" class="comic-name"', svg)
    return [int(value) for value in y_matches]


def _extract_font_sizes(svg: str) -> list[int]:
    size_matches = re.findall(r'class="comic-name" font-size="(\d+)"', svg)
    return [int(value) for value in size_matches]


def test_generate_poster_includes_required_layers_and_assets() -> None:
    composer = SVGLineupComposer()
    svg = composer.generate_poster(
        lineup=[{"name": "Ada Torres"}, {"name": "Bruno Gil"}],
        date="2026-03-10",
        event_id="evt-123",
    )

    assert 'width="1080" height="1350"' in svg
    assert 'fill="#e61d2b"' in svg
    assert '<pattern id="halftone"' in svg
    assert '<polygon points="0,0 260,110 140,320 0,250"' in svg
    assert '<polygon points="1080,0 820,110 940,320 1080,250"' in svg
    assert "/root/RECOVA/backend/assets/fonts/BebasNeue.ttf" in svg
    assert "ADA TORRES" in svg
    assert "BRUNO GIL" in svg
    assert "2026-03-10" in svg
    assert f'y="{HEADER_RECOVA_Y}" class="title"' in svg
    assert f'y="{HEADER_MIC_Y}" class="title"' in svg
    assert f'y="{FOOTER_DATE_Y}" class="footer-date"' in svg


def test_layout_spacing_is_larger_for_three_than_six_names() -> None:
    composer = SVGLineupComposer()

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


def test_lineup_fallback_when_empty_or_invalid() -> None:
    composer = SVGLineupComposer()

    svg_empty = composer.generate_poster(lineup=[], date="2026-03-10", event_id="evt-empty")
    svg_invalid = composer.generate_poster(lineup="invalid", date="2026-03-10", event_id="evt-invalid")

    assert "LINEUP PENDIENTE" in svg_empty
    assert "LINEUP PENDIENTE" in svg_invalid


def test_all_comic_y_positions_stay_inside_safe_zone() -> None:
    composer = SVGLineupComposer()
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


def test_font_size_reduces_when_count_above_five() -> None:
    composer = SVGLineupComposer()

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
