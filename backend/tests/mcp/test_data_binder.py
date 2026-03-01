"""Contract tests for backend.src.core.data_binder (SDD §13).

These tests intentionally target the future public API. Because
`data_binder.py` is currently empty, they are expected to fail with
`AttributeError` until the module is implemented.
"""

from backend.src.core import data_binder


def test_generate_injection_js_basic():
    lineup = [
        {"name": "Comica Uno", "instagram": "@comica1"},
        {"name": "Comico Dos", "instagram": "@comico2"},
        {"name": "Comica Tres", "instagram": "@comica3"},
    ]

    script = data_binder.generate_injection_js(lineup)

    assert ".slot-1 .name" in script
    assert ".slot-2 .name" in script
    assert ".slot-3 .name" in script


def test_instagram_exclusion_invariant():
    lineup = [
        {"name": "Comica Uno", "instagram": "@comica1"},
        {"name": "Comico Dos", "instagram": "@comico2"},
    ]

    script = data_binder.generate_injection_js(lineup)

    assert "comica1" not in script
    assert "comico2" not in script
    assert "instagram" not in script.lower()


def test_fit_text_script_structure():
    lineup = [{"name": "Nombre Muy Largo Para Ajuste", "instagram": "@fit_text"}]

    script = data_binder.generate_injection_js(lineup)

    assert "scrollWidth" in script
    assert "clientWidth" in script
    assert "scrollWidth >" in script or "scrollWidth>" in script


def test_empty_lineup_handling():
    script_empty = data_binder.generate_injection_js([])
    script_partial = data_binder.generate_injection_js([
        {"name": "Solo Uno", "instagram": "@solo"}
    ])

    assert ".style.display = 'none'" in script_empty or '.style.display = "none"' in script_empty
    assert ".style.display = 'none'" in script_partial or '.style.display = "none"' in script_partial
