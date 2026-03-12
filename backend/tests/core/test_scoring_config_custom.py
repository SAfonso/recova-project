"""Tests TDD — ScoringConfig con custom_scoring_rules (Sprint 10, v0.15.0).

Cubre (spec custom_scoring_spec §ScoringConfig):
  CustomRule.matches — comparación case-insensitive
  CustomRule disabled — no hace match nunca
  ScoringConfig.apply_custom_rules — suma puntos de reglas activas
  apply_custom_rules devuelve 0 si scoring_type != 'custom'
  ScoringConfig.from_dict carga custom_rules como lista de CustomRule
"""

from __future__ import annotations

import pytest

from backend.src.core.scoring_config import CustomRule, ScoringConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

OM_ID = "om-sprint10-uuid"


def _make_rule(**kwargs) -> CustomRule:
    defaults = dict(
        field="¿Haces humor negro?",
        condition="equals",
        value="Sí",
        points=10,
        enabled=True,
        description="Bono por humor negro",
    )
    return CustomRule(**{**defaults, **kwargs})


def _make_config(scoring_type: str = "custom", rules: list[dict] | None = None) -> ScoringConfig:
    raw = {
        "scoring_type": scoring_type,
        "custom_scoring_rules": rules or [
            {
                "field": "¿Haces humor negro?",
                "condition": "equals",
                "value": "Sí",
                "points": 10,
                "enabled": True,
                "description": "Bono por humor negro",
            }
        ],
    }
    return ScoringConfig.from_dict(OM_ID, raw)


# ---------------------------------------------------------------------------
# CustomRule.matches
# ---------------------------------------------------------------------------

def test_custom_rule_matches_case_insensitive():
    """La comparación ignora mayúsculas: 'sí' == 'Sí' → True."""
    rule = _make_rule(value="Sí")
    metadata = {"¿Haces humor negro?": "sí"}
    assert rule.matches(metadata) is True


def test_custom_rule_no_match():
    """Valor distinto al esperado → False."""
    rule = _make_rule(value="Sí")
    metadata = {"¿Haces humor negro?": "No"}
    assert rule.matches(metadata) is False


def test_custom_rule_disabled_no_match():
    """Regla con enabled=False → False siempre, aunque el valor coincida."""
    rule = _make_rule(value="Sí", enabled=False)
    metadata = {"¿Haces humor negro?": "Sí"}
    assert rule.matches(metadata) is False


def test_custom_rule_missing_field_no_match():
    """Campo ausente en metadata → False (no KeyError)."""
    rule = _make_rule(field="¿Campo inexistente?", value="Sí")
    metadata = {}
    assert rule.matches(metadata) is False


# ---------------------------------------------------------------------------
# ScoringConfig.apply_custom_rules
# ---------------------------------------------------------------------------

def test_apply_custom_rules_sums_points():
    """Dos reglas activas que coinciden → suma de sus puntos."""
    config = ScoringConfig.from_dict(OM_ID, {
        "scoring_type": "custom",
        "custom_scoring_rules": [
            {"field": "¿Haces humor negro?", "condition": "equals", "value": "Sí", "points": 10, "enabled": True},
            {"field": "¿Tienes material nuevo?", "condition": "equals", "value": "Sí", "points": 5, "enabled": True},
        ],
    })
    metadata = {"¿Haces humor negro?": "Sí", "¿Tienes material nuevo?": "Sí"}

    result = config.apply_custom_rules(metadata)

    assert result == 15


def test_apply_custom_rules_returns_zero_if_not_custom():
    """Si scoring_type != 'custom', apply_custom_rules devuelve 0."""
    config = ScoringConfig.from_dict(OM_ID, {
        "scoring_type": "basic",
        "custom_scoring_rules": [
            {"field": "¿Haces humor negro?", "condition": "equals", "value": "Sí", "points": 10, "enabled": True},
        ],
    })
    metadata = {"¿Haces humor negro?": "Sí"}

    assert config.apply_custom_rules(metadata) == 0


def test_scoring_config_loads_custom_rules_from_dict():
    """from_dict con custom_scoring_rules → lista de objetos CustomRule."""
    config = _make_config()

    assert len(config.custom_scoring_rules) == 1
    rule = config.custom_scoring_rules[0]
    assert isinstance(rule, CustomRule)
    assert rule.field == "¿Haces humor negro?"
    assert rule.points == 10
    assert rule.enabled is True


def test_scoring_config_empty_custom_rules_by_default():
    """Config sin custom_scoring_rules → lista vacía, sin error."""
    config = ScoringConfig.from_dict(OM_ID, {"scoring_type": "custom"})

    assert config.custom_scoring_rules == []
    assert config.apply_custom_rules({"cualquier": "campo"}) == 0


# ---------------------------------------------------------------------------
# apply_custom_rules — campo 'backup' reservado (v0.19.0)
# ---------------------------------------------------------------------------

def test_apply_custom_rules_ignores_backup_field():
    """Regla con field='backup' no suma puntos aunque el metadata coincida."""
    config = ScoringConfig.from_dict(OM_ID, {
        "scoring_type": "custom",
        "custom_scoring_rules": [
            {"field": "backup", "condition": "equals", "value": "Sí", "points": 20, "enabled": True},
        ],
    })
    metadata = {"backup": "Sí"}

    assert config.apply_custom_rules(metadata) == 0


def test_apply_custom_rules_ignores_backup_but_applies_other_rules():
    """Regla backup ignorada; otras reglas activas sí puntúan."""
    config = ScoringConfig.from_dict(OM_ID, {
        "scoring_type": "custom",
        "custom_scoring_rules": [
            {"field": "backup", "condition": "equals", "value": "Sí", "points": 20, "enabled": True},
            {"field": "¿Haces humor negro?", "condition": "equals", "value": "Sí", "points": 10, "enabled": True},
        ],
    })
    metadata = {"backup": "Sí", "¿Haces humor negro?": "Sí"}

    assert config.apply_custom_rules(metadata) == 10
