from __future__ import annotations

from datetime import datetime, timezone

import scoring_engine as engine


def test_normalize_category_aliases_to_expected_business_values():
    assert engine.normalize_category("priority") == "preferred"
    assert engine.normalize_category("restricted") == "blacklist"
    assert engine.normalize_category("gold") == "gold"


def test_compute_score_applies_category_bonus_penalty_and_single_bullet_bonus():
    assert engine.compute_score("gold", penalty_recent_acceptance=False, single_date=False) == 12
    assert engine.compute_score("preferred", penalty_recent_acceptance=False, single_date=True) == 30
    assert engine.compute_score("standard", penalty_recent_acceptance=True, single_date=False) == -100


def test_has_single_date_detects_single_or_multiple_tokens():
    assert engine.has_single_date("2026-03-14") is True
    assert engine.has_single_date("2026-03-14,2026-03-21") is False


def test_run_dummy_scoring_test_executes_without_assertion_error():
    engine.run_dummy_scoring_test()


def test_sorting_prioritizes_oldest_timestamp_when_score_ties():
    older = engine.CandidateScore(
        nombre="A",
        telefono="+34111111111",
        instagram="a",
        comico_id="id-a",
        categoria="preferred",
        score_final=30,
        marca_temporal=datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc),
        fecha_evento=datetime(2026, 3, 10, tzinfo=timezone.utc).date(),
        penalizado_por_recencia=False,
        bono_bala_unica=True,
    )
    newer = engine.CandidateScore(
        nombre="B",
        telefono="+34222222222",
        instagram="b",
        comico_id="id-b",
        categoria="preferred",
        score_final=30,
        marca_temporal=datetime(2026, 2, 2, 10, 0, tzinfo=timezone.utc),
        fecha_evento=datetime(2026, 3, 10, tzinfo=timezone.utc).date(),
        penalizado_por_recencia=False,
        bono_bala_unica=True,
    )

    ranking = sorted(
        [newer, older],
        key=lambda item: (
            -item.score_final,
            item.marca_temporal,
        ),
    )

    assert ranking[0].telefono == older.telefono
