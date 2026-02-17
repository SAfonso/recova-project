from __future__ import annotations

from datetime import datetime, timezone

import scoring_engine as engine


def test_normalize_category_aliases_to_expected_business_values():
    assert engine.normalize_category("priority") == "preferred"
    assert engine.normalize_category("restricted") == "blacklist"
    assert engine.normalize_category("gold") == "gold"


def test_map_silver_category_to_gold_uses_expected_equivalences():
    assert engine.map_silver_category_to_gold("general") == "standard"
    assert engine.map_silver_category_to_gold("priority") == "priority"
    assert engine.map_silver_category_to_gold("gold") == "gold"
    assert engine.map_silver_category_to_gold("restricted") == "restricted"
    assert engine.map_silver_category_to_gold("unknown") == "standard"


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
        genero="f",
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
        genero="m",
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


def test_build_ranking_deduplicates_comico_id_with_strict_gender_order(monkeypatch):
    requests = [
        engine.SilverRequest(
            comico_id="dup-id",
            nombre="Comica Dup",
            telefono="+34111111111",
            instagram="dup_f",
            genero="f",
            categoria_silver="priority",
            fechas_disponibles="2026-03-14",
            marca_temporal=datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc),
        ),
        engine.SilverRequest(
            comico_id="m-1",
            nombre="Comico Uno",
            telefono="+34222222222",
            instagram="m1",
            genero="m",
            categoria_silver="priority",
            fechas_disponibles="2026-03-14",
            marca_temporal=datetime(2026, 2, 2, 10, 0, tzinfo=timezone.utc),
        ),
        engine.SilverRequest(
            comico_id="dup-id",
            nombre="Comica Dup Repetida",
            telefono="+34333333333",
            instagram="dup_u",
            genero="unknown",
            categoria_silver="priority",
            fechas_disponibles="2026-03-14",
            marca_temporal=datetime(2026, 2, 3, 10, 0, tzinfo=timezone.utc),
        ),
    ]

    monkeypatch.setattr(engine, "upsert_comico", lambda _conn, request: (request.comico_id, "preferred"))
    monkeypatch.setattr(engine, "has_recent_acceptance_penalty", lambda _conn, _comico_id: False)

    ranking, skipped = engine.build_ranking(conn=None, requests=requests)

    assert skipped == 0
    assert [candidate.comico_id for candidate in ranking] == ["dup-id", "m-1"]


def test_build_ranking_continues_when_a_gender_bucket_is_exhausted(monkeypatch):
    requests = [
        engine.SilverRequest(
            comico_id="f-1",
            nombre="Comica",
            telefono="+34111111111",
            instagram="f1",
            genero="f",
            categoria_silver="priority",
            fechas_disponibles="2026-03-14",
            marca_temporal=datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc),
        ),
        engine.SilverRequest(
            comico_id="m-1",
            nombre="Comico Uno",
            telefono="+34222222222",
            instagram="m1",
            genero="m",
            categoria_silver="priority",
            fechas_disponibles="2026-03-14",
            marca_temporal=datetime(2026, 2, 2, 10, 0, tzinfo=timezone.utc),
        ),
        engine.SilverRequest(
            comico_id="m-2",
            nombre="Comico Dos",
            telefono="+34333333333",
            instagram="m2",
            genero="m",
            categoria_silver="priority",
            fechas_disponibles="2026-03-14",
            marca_temporal=datetime(2026, 2, 3, 10, 0, tzinfo=timezone.utc),
        ),
        engine.SilverRequest(
            comico_id="u-1",
            nombre="Comique X",
            telefono="+34444444444",
            instagram="u1",
            genero="unknown",
            categoria_silver="priority",
            fechas_disponibles="2026-03-14",
            marca_temporal=datetime(2026, 2, 4, 10, 0, tzinfo=timezone.utc),
        ),
        engine.SilverRequest(
            comico_id="u-2",
            nombre="Comique Y",
            telefono="+34555555555",
            instagram="u2",
            genero="unknown",
            categoria_silver="priority",
            fechas_disponibles="2026-03-14",
            marca_temporal=datetime(2026, 2, 5, 10, 0, tzinfo=timezone.utc),
        ),
    ]

    monkeypatch.setattr(engine, "upsert_comico", lambda _conn, request: (request.comico_id, "preferred"))
    monkeypatch.setattr(engine, "has_recent_acceptance_penalty", lambda _conn, _comico_id: False)

    ranking, skipped = engine.build_ranking(conn=None, requests=requests)

    assert skipped == 0
    assert [candidate.comico_id for candidate in ranking] == ["f-1", "m-1", "m-2", "u-1", "u-2"]


def test_build_ranking_places_unknowns_only_after_fnb_and_m_buckets(monkeypatch):
    requests = [
        engine.SilverRequest(
            comico_id="f-1",
            nombre="Comica Uno",
            telefono="+34111111111",
            instagram="f1",
            genero="f",
            categoria_silver="priority",
            fechas_disponibles="2026-03-14",
            marca_temporal=datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc),
        ),
        engine.SilverRequest(
            comico_id="f-2",
            nombre="Comica Dos",
            telefono="+34111111112",
            instagram="f2",
            genero="f",
            categoria_silver="priority",
            fechas_disponibles="2026-03-14",
            marca_temporal=datetime(2026, 2, 2, 10, 0, tzinfo=timezone.utc),
        ),
        engine.SilverRequest(
            comico_id="m-1",
            nombre="Comico Uno",
            telefono="+34222222221",
            instagram="m1",
            genero="m",
            categoria_silver="priority",
            fechas_disponibles="2026-03-14",
            marca_temporal=datetime(2026, 2, 1, 10, 30, tzinfo=timezone.utc),
        ),
        engine.SilverRequest(
            comico_id="m-2",
            nombre="Comico Dos",
            telefono="+34222222222",
            instagram="m2",
            genero="m",
            categoria_silver="priority",
            fechas_disponibles="2026-03-14",
            marca_temporal=datetime(2026, 2, 2, 10, 30, tzinfo=timezone.utc),
        ),
        engine.SilverRequest(
            comico_id="m-3",
            nombre="Comico Tres",
            telefono="+34222222223",
            instagram="m3",
            genero="m",
            categoria_silver="priority",
            fechas_disponibles="2026-03-14",
            marca_temporal=datetime(2026, 2, 3, 10, 30, tzinfo=timezone.utc),
        ),
        engine.SilverRequest(
            comico_id="u-1",
            nombre="Comique X",
            telefono="+34333333331",
            instagram="u1",
            genero="unknown",
            categoria_silver="priority",
            fechas_disponibles="2026-03-14",
            marca_temporal=datetime(2026, 2, 4, 10, 30, tzinfo=timezone.utc),
        ),
    ]

    monkeypatch.setattr(engine, "upsert_comico", lambda _conn, request: (request.comico_id, "preferred"))
    monkeypatch.setattr(engine, "has_recent_acceptance_penalty", lambda _conn, _comico_id: False)

    ranking, skipped = engine.build_ranking(conn=None, requests=requests)

    assert skipped == 0
    assert [candidate.comico_id for candidate in ranking] == ["f-1", "m-1", "f-2", "m-2", "m-3", "u-1"]
