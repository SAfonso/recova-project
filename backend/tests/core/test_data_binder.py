from __future__ import annotations

from backend.src.core.data_binder import generate_injection_js


def test_fit_text_script_reduces_font_size_for_long_names() -> None:
    long_name = "A" * 50
    script = generate_injection_js([{"name": long_name, "instagram": "long_name"}], total_slots=8)

    assert long_name in script
    assert "while (scrollWidth > clientWidth" in script
    assert "currentFontSize -= 1" in script
    assert "el.style.fontSize" in script


def test_slot_mapping_hides_unused_slots_from_4_to_8() -> None:
    lineup = [
        {"name": "Comico 1", "instagram": "c1"},
        {"name": "Comico 2", "instagram": "c2"},
        {"name": "Comico 3", "instagram": "c3"},
    ]

    script = generate_injection_js(lineup, total_slots=8)

    for slot in range(1, 4):
        assert f".slot-{slot} .name" in script
    for slot in range(4, 9):
        assert f".slot-{slot}" in script
        assert f"slotEl{slot}.style.display = 'none'" in script
