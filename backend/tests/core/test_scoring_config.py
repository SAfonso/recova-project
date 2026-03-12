"""Tests unitarios para ScoringConfig."""

from __future__ import annotations

import pytest

from backend.src.core.scoring_config import CategoryRule, ScoringConfig, _DEFAULTS


# ---------------------------------------------------------------------------
# CategoryRule
# ---------------------------------------------------------------------------


def test_category_rule_standard_not_restricted() -> None:
    rule = CategoryRule(base_score=50, enabled=True)
    assert not rule.is_restricted


def test_category_rule_none_score_is_restricted() -> None:
    rule = CategoryRule(base_score=None, enabled=True)
    assert rule.is_restricted


def test_category_rule_disabled_is_restricted() -> None:
    rule = CategoryRule(base_score=70, enabled=False)
    assert rule.is_restricted


def test_category_rule_from_dict() -> None:
    rule = CategoryRule.from_dict({"base_score": 90, "enabled": True})
    assert rule.base_score == 90
    assert rule.enabled is True
    assert not rule.is_restricted


# ---------------------------------------------------------------------------
# ScoringConfig.from_dict — con config completa
# ---------------------------------------------------------------------------


FULL_CONFIG = {
    "available_slots": 6,
    "categories": {
        "standard":   {"base_score": 50,   "enabled": True},
        "priority":   {"base_score": 70,   "enabled": True},
        "gold":       {"base_score": 90,   "enabled": True},
        "restricted": {"base_score": None, "enabled": True},
    },
    "recency_penalty": {
        "enabled": True,
        "last_n_editions": 3,
        "penalty_points": 30,
    },
    "single_date_boost": {
        "enabled": True,
        "boost_points": 15,
    },
    "gender_parity": {
        "enabled": True,
        "target_female_nb_pct": 50,
    },
}


def test_from_dict_parses_available_slots() -> None:
    cfg = ScoringConfig.from_dict("om-001", FULL_CONFIG)
    assert cfg.available_slots == 6


def test_from_dict_parses_recency_fields() -> None:
    cfg = ScoringConfig.from_dict("om-001", FULL_CONFIG)
    assert cfg.recency_penalty_enabled is True
    assert cfg.recency_last_n_editions == 3
    assert cfg.recency_penalty_points == 30


def test_from_dict_parses_single_date_boost() -> None:
    cfg = ScoringConfig.from_dict("om-001", FULL_CONFIG)
    assert cfg.single_date_boost_enabled is True
    assert cfg.single_date_boost_points == 15


def test_from_dict_parses_gender_parity() -> None:
    cfg = ScoringConfig.from_dict("om-001", FULL_CONFIG)
    assert cfg.gender_parity_enabled is True
    assert cfg.gender_parity_target_pct == 50


def test_from_dict_stores_open_mic_id() -> None:
    cfg = ScoringConfig.from_dict("om-xyz", FULL_CONFIG)
    assert cfg.open_mic_id == "om-xyz"


# ---------------------------------------------------------------------------
# ScoringConfig.from_dict — config vacía usa defaults
# ---------------------------------------------------------------------------


def test_empty_config_uses_defaults() -> None:
    cfg = ScoringConfig.from_dict("om-002", {})
    assert cfg.available_slots == _DEFAULTS["available_slots"]
    assert cfg.recency_penalty_enabled == _DEFAULTS["recency_penalty"]["enabled"]
    assert cfg.recency_last_n_editions == _DEFAULTS["recency_penalty"]["last_n_editions"]
    assert cfg.recency_penalty_points  == _DEFAULTS["recency_penalty"]["penalty_points"]
    assert cfg.single_date_boost_points == _DEFAULTS["single_date_boost"]["boost_points"]


def test_empty_config_has_all_default_categories() -> None:
    cfg = ScoringConfig.from_dict("om-002", {})
    for cat in ("standard", "priority", "gold", "restricted"):
        assert cat in cfg.categories


def test_partial_config_merges_with_defaults() -> None:
    partial = {"available_slots": 10}
    cfg = ScoringConfig.from_dict("om-003", partial)
    assert cfg.available_slots == 10
    # El resto debe venir de defaults
    assert cfg.recency_penalty_points == _DEFAULTS["recency_penalty"]["penalty_points"]


def test_non_dict_config_falls_back_to_defaults() -> None:
    cfg = ScoringConfig.from_dict("om-004", None)  # type: ignore[arg-type]
    assert cfg.available_slots == _DEFAULTS["available_slots"]


# ---------------------------------------------------------------------------
# ScoringConfig.default
# ---------------------------------------------------------------------------


def test_default_constructor_is_equivalent_to_empty_from_dict() -> None:
    cfg_default   = ScoringConfig.default("om-005")
    cfg_from_dict = ScoringConfig.from_dict("om-005", {})
    assert cfg_default == cfg_from_dict


# ---------------------------------------------------------------------------
# is_restricted
# ---------------------------------------------------------------------------


def test_is_restricted_for_restricted_category() -> None:
    cfg = ScoringConfig.default("om-006")
    assert cfg.is_restricted("restricted") is True


def test_is_restricted_false_for_standard() -> None:
    cfg = ScoringConfig.default("om-006")
    assert cfg.is_restricted("standard") is False


def test_is_restricted_unknown_category_falls_back_to_standard() -> None:
    cfg = ScoringConfig.default("om-006")
    assert cfg.is_restricted("unknown_cat") is False


# ---------------------------------------------------------------------------
# compute_score
# ---------------------------------------------------------------------------


def test_compute_score_base_no_modifiers() -> None:
    cfg = ScoringConfig.default("om-007")
    score = cfg.compute_score("standard", has_recency_penalty=False, is_single_date=False)
    assert score == 50  # base_score por defecto de 'standard'


def test_compute_score_gold_no_modifiers() -> None:
    cfg = ScoringConfig.default("om-007")
    score = cfg.compute_score("gold", has_recency_penalty=False, is_single_date=False)
    assert score == 90


def test_compute_score_applies_recency_penalty() -> None:
    cfg = ScoringConfig.default("om-007")
    score_with    = cfg.compute_score("standard", has_recency_penalty=True,  is_single_date=False)
    score_without = cfg.compute_score("standard", has_recency_penalty=False, is_single_date=False)
    assert score_with == score_without - cfg.recency_penalty_points


def test_compute_score_applies_single_date_boost() -> None:
    cfg = ScoringConfig.default("om-007")
    score_with    = cfg.compute_score("standard", has_recency_penalty=False, is_single_date=True)
    score_without = cfg.compute_score("standard", has_recency_penalty=False, is_single_date=False)
    assert score_with == score_without + cfg.single_date_boost_points


def test_compute_score_applies_both_modifiers() -> None:
    cfg = ScoringConfig.default("om-007")
    score = cfg.compute_score("priority", has_recency_penalty=True, is_single_date=True)
    expected = 70 - cfg.recency_penalty_points + cfg.single_date_boost_points
    assert score == expected


def test_compute_score_returns_none_for_restricted() -> None:
    cfg = ScoringConfig.default("om-007")
    assert cfg.compute_score("restricted", has_recency_penalty=False, is_single_date=False) is None


def test_compute_score_penalty_disabled_has_no_effect() -> None:
    cfg = ScoringConfig.from_dict("om-008", {
        **FULL_CONFIG,
        "recency_penalty": {"enabled": False, "last_n_editions": 2, "penalty_points": 30},
    })
    score_with    = cfg.compute_score("standard", has_recency_penalty=True,  is_single_date=False)
    score_without = cfg.compute_score("standard", has_recency_penalty=False, is_single_date=False)
    assert score_with == score_without


def test_compute_score_boost_disabled_has_no_effect() -> None:
    cfg = ScoringConfig.from_dict("om-009", {
        **FULL_CONFIG,
        "single_date_boost": {"enabled": False, "boost_points": 15},
    })
    score_with    = cfg.compute_score("standard", has_recency_penalty=False, is_single_date=True)
    score_without = cfg.compute_score("standard", has_recency_penalty=False, is_single_date=False)
    assert score_with == score_without


# ---------------------------------------------------------------------------
# Categorías extra en JSONB
# ---------------------------------------------------------------------------


def test_extra_category_in_jsonb_is_registered() -> None:
    cfg = ScoringConfig.from_dict("om-010", {
        **FULL_CONFIG,
        "categories": {
            **FULL_CONFIG["categories"],
            "vip": {"base_score": 100, "enabled": True},
        },
    })
    assert "vip" in cfg.categories
    assert cfg.categories["vip"].base_score == 100


def test_extra_category_score_is_computed() -> None:
    cfg = ScoringConfig.from_dict("om-010", {
        **FULL_CONFIG,
        "categories": {
            **FULL_CONFIG["categories"],
            "vip": {"base_score": 100, "enabled": True},
        },
    })
    assert cfg.compute_score("vip", False, False) == 100
