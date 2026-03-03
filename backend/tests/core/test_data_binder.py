from __future__ import annotations

from backend.src.core.data_binder import generate_injection_js


def test_injection_mapping_writes_expected_slots_and_names() -> None:
    lineup = [
        {"name": "Ana Perez", "instagram": "@ana"},
        {"name": "Luis Gomez", "instagram": "@luis"},
    ]

    script = generate_injection_js(lineup, total_slots=8)

    assert ".slot-1 .name" in script
    assert ".slot-2 .name" in script
    assert "Ana Perez" in script
    assert "Luis Gomez" in script


def test_instagram_is_not_injected_in_visual_payload() -> None:
    lineup = [
        {"name": "Ana Perez", "instagram": "@ana"},
        {"name": "Luis Gomez", "instagram": "@luis"},
    ]

    script = generate_injection_js(lineup, total_slots=8)

    assert "instagram" not in script.lower()
    assert "@ana" not in script
    assert "@luis" not in script


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


def test_lineup_empty_hides_all_slots() -> None:
    script = generate_injection_js([], total_slots=8)

    for slot in range(1, 9):
        assert f"slotEl{slot}.style.display = 'none'" in script


def test_lineup_with_non_dict_entries_does_not_crash() -> None:
    script = generate_injection_js(["foo", "bar"], total_slots=8)

    assert ".slot-1 .name" in script
    assert ".slot-2 .name" in script
    # fallback extraction returns empty names, but script must still be generated
    assert "window.renderReady = true;" in script


def test_lineup_with_ten_people_maps_first_eight() -> None:
    lineup = [{"name": f"Comico {idx}", "instagram": f"c{idx}"} for idx in range(1, 11)]

    script = generate_injection_js(lineup, total_slots=8)

    for idx in range(1, 9):
        assert f"Comico {idx}" in script
    assert "Comico 9" not in script
    assert "Comico 10" not in script


def test_invalid_lineup_type_returns_safe_ready_script() -> None:
    script = generate_injection_js("invalid-payload", total_slots=8)

    assert script.strip() == "window.renderReady = true;"


def test_jinja_placeholder_replacement_rules_are_included() -> None:
    lineup = [{"name": "Ada Torres", "instagram": "adatorres"}]

    script = generate_injection_js(lineup, total_slots=8)

    assert "text.includes('{{')" in script
    assert "text.includes('{%')" in script
    assert r"\{\{\s*(comico|comic)\.name\s*\}\}" in script
    assert r"\{\{\s*event\.date\s*\}\}" in script
    assert r"\{%\s*for[^%]*%\}" in script
    assert r"\{%\s*endfor\s*%\}" in script


def test_active_template_selector_mapping_is_included() -> None:
    lineup = [{"name": "Bruno Gil", "instagram": "brunogil"}]

    script = generate_injection_js(lineup, total_slots=8)

    assert "document.querySelector('.lineup')" in script
    assert "querySelector('.comico')" in script
    assert "comicEl.className = 'comico'" in script
    assert "querySelectorAll('.footer, .event-date, [data-event-date]')" in script
