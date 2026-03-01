"""Contract tests for backend.src.core.data_binder (SDD §13)."""

from backend.src.core import data_binder


def test_injection_mapping():
    lineup = [
        {"name": "Ana Pérez", "instagram": "@ana"},
        {"name": "Luis Gómez", "instagram": "@luis"},
    ]

    script = data_binder.generate_injection_js(lineup)

    assert ".slot-1 .name" in script
    assert ".slot-2 .name" in script
    assert "Ana Pérez" in script
    assert "Luis Gómez" in script


def test_instagram_exclusion():
    lineup = [
        {"name": "Ana Pérez", "instagram": "@ana"},
        {"name": "Luis Gómez", "instagram": "@luis"},
    ]

    script = data_binder.generate_injection_js(lineup)

    assert "instagram" not in script.lower()
    assert "@ana" not in script
    assert "@luis" not in script


def test_fit_text_injection():
    lineup = [{"name": "Nombre Extremadamente Largo Para Ajuste", "instagram": "@fit"}]

    script = data_binder.generate_injection_js(lineup)

    assert "scrollWidth" in script
    assert "clientWidth" in script
    assert "scrollWidth > clientWidth" in script or "scrollWidth>clientWidth" in script


def test_overflow_slots_hidden():
    lineup = [
        {"name": "Comico 1", "instagram": "@c1"},
        {"name": "Comico 2", "instagram": "@c2"},
        {"name": "Comico 3", "instagram": "@c3"},
        {"name": "Comico 4", "instagram": "@c4"},
    ]

    script = data_binder.generate_injection_js(lineup, total_slots=8)

    for slot in range(5, 9):
        assert f".slot-{slot}" in script
    assert ".style.display = 'none'" in script or '.style.display = "none"' in script


def test_empty_lineup_supported():
    script = data_binder.generate_injection_js([], total_slots=8)
    for slot in range(1, 9):
        assert f"slotEl{slot}.style.display = 'none'" in script


def test_lineup_with_string_entries_supported():
    script = data_binder.generate_injection_js(["Ana", "Luis"], total_slots=8)
    assert ".slot-1 .name" in script
    assert ".slot-2 .name" in script


def test_lineup_with_ten_people_only_maps_first_eight():
    lineup = [{"name": f"Comico {idx}", "instagram": f"@c{idx}"} for idx in range(1, 11)]
    script = data_binder.generate_injection_js(lineup, total_slots=8)
    for idx in range(1, 9):
        assert f"Comico {idx}" in script
    assert "Comico 9" not in script
    assert "Comico 10" not in script
