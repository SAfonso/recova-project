from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.src import scoring_engine as engine
from backend.src.core.scoring_config import ScoringConfig

OM_ID = "om-test-00000000-0000-0000-0000-000000000001"


# ---------------------------------------------------------------------------
# Helpers de test
# ---------------------------------------------------------------------------

class RecordingCursor:
    def __init__(self, fetchall_rows=None, fetchone_result=None):
        self.executed: list[tuple[str, tuple | None]] = []
        self._fetchall_rows = list(fetchall_rows or [])
        self._fetchone_result = fetchone_result

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.executed.append((str(query), params))

    def fetchall(self):
        return list(self._fetchall_rows)

    def fetchone(self):
        return self._fetchone_result


class RecordingConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


def _default_config() -> ScoringConfig:
    return ScoringConfig.default(OM_ID)


def _make_request(**kwargs) -> engine.SilverRequest:
    defaults = dict(
        comico_id="id-x",
        nombre="Test",
        telefono="+34000000000",
        instagram="test",
        genero="f",
        categoria_silver="priority",
        fechas_disponibles="2026-03-14",
        marca_temporal=datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc),
    )
    return engine.SilverRequest(**{**defaults, **kwargs})


def _make_candidate(**kwargs) -> engine.CandidateScore:
    defaults = dict(
        nombre="Test",
        telefono="+34000000000",
        instagram="test",
        genero="f",
        comico_id="id-x",
        categoria="priority",
        open_mic_id=OM_ID,
        score_final=70,
        marca_temporal=datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc),
        fecha_evento=datetime(2026, 3, 14, tzinfo=timezone.utc).date(),
        penalizado_por_recencia=False,
        bono_bala_unica=True,
        solicitud_id="22222222-2222-2222-2222-222222222222",
    )
    return engine.CandidateScore(**{**defaults, **kwargs})


# ---------------------------------------------------------------------------
# _map_to_gold_category (sustituto de map_silver_category_to_gold)
# ---------------------------------------------------------------------------

def test_map_to_gold_category_covers_all_silver_categories():
    assert engine._map_to_gold_category("general")    == "standard"
    assert engine._map_to_gold_category("priority")   == "priority"
    assert engine._map_to_gold_category("gold")       == "gold"
    assert engine._map_to_gold_category("restricted") == "restricted"
    assert engine._map_to_gold_category("unknown")    == "standard"
    assert engine._map_to_gold_category(None)         == "standard"


# ---------------------------------------------------------------------------
# has_single_date
# ---------------------------------------------------------------------------

def test_has_single_date_detects_single_or_multiple_tokens():
    assert engine.has_single_date("2026-03-14") is True
    assert engine.has_single_date("2026-03-14,2026-03-21") is False


# ---------------------------------------------------------------------------
# Ordenación por marca_temporal cuando hay empate de score
# ---------------------------------------------------------------------------

def test_sorting_prioritizes_oldest_timestamp_when_score_ties():
    older = _make_candidate(comico_id="id-a", telefono="+34111111111", instagram="a",
                            genero="f",  marca_temporal=datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc))
    newer = _make_candidate(comico_id="id-b", telefono="+34222222222", instagram="b",
                            genero="m",  marca_temporal=datetime(2026, 2, 2, 10, 0, tzinfo=timezone.utc))

    ranking = sorted(
        [newer, older],
        key=lambda c: (-c.score_final, c.marca_temporal),
    )
    assert ranking[0].telefono == older.telefono


# ---------------------------------------------------------------------------
# build_ranking — deduplicación y orden por género
# ---------------------------------------------------------------------------

def _fake_upsert(_, request):
    return request.comico_id, "priority"


def _fake_no_penalty(*_args, **_kwargs):
    return False


def test_build_ranking_deduplicates_comico_id(monkeypatch):
    requests = [
        _make_request(comico_id="dup-id", instagram="dup_f", genero="f"),
        _make_request(comico_id="m-1",    instagram="m1",    genero="m",
                      marca_temporal=datetime(2026, 2, 2, 10, 0, tzinfo=timezone.utc)),
        _make_request(comico_id="dup-id", instagram="dup_u", genero="unknown",
                      marca_temporal=datetime(2026, 2, 3, 10, 0, tzinfo=timezone.utc)),
    ]

    monkeypatch.setattr(engine, "upsert_comico", _fake_upsert)
    monkeypatch.setattr(engine, "has_recent_acceptance_penalty", _fake_no_penalty)

    ranking, skipped = engine.build_ranking(conn=None, requests=requests, config=_default_config())

    assert skipped == 0
    assert [c.comico_id for c in ranking] == ["dup-id", "m-1"]


def test_build_ranking_continues_when_a_gender_bucket_is_exhausted(monkeypatch):
    requests = [
        _make_request(comico_id="f-1", instagram="f1", genero="f",
                      marca_temporal=datetime(2026, 2, 1, tzinfo=timezone.utc)),
        _make_request(comico_id="m-1", instagram="m1", genero="m",
                      marca_temporal=datetime(2026, 2, 2, tzinfo=timezone.utc)),
        _make_request(comico_id="m-2", instagram="m2", genero="m",
                      marca_temporal=datetime(2026, 2, 3, tzinfo=timezone.utc)),
        _make_request(comico_id="u-1", instagram="u1", genero="unknown",
                      marca_temporal=datetime(2026, 2, 4, tzinfo=timezone.utc)),
        _make_request(comico_id="u-2", instagram="u2", genero="unknown",
                      marca_temporal=datetime(2026, 2, 5, tzinfo=timezone.utc)),
    ]

    monkeypatch.setattr(engine, "upsert_comico", _fake_upsert)
    monkeypatch.setattr(engine, "has_recent_acceptance_penalty", _fake_no_penalty)

    ranking, skipped = engine.build_ranking(conn=None, requests=requests, config=_default_config())

    assert skipped == 0
    assert [c.comico_id for c in ranking] == ["f-1", "m-1", "m-2", "u-1", "u-2"]


def test_build_ranking_alternates_gender_buckets(monkeypatch):
    requests = [
        _make_request(comico_id="f-1", instagram="f1", genero="f",
                      marca_temporal=datetime(2026, 2, 1, tzinfo=timezone.utc)),
        _make_request(comico_id="f-2", instagram="f2", genero="f",
                      marca_temporal=datetime(2026, 2, 2, tzinfo=timezone.utc)),
        _make_request(comico_id="m-1", instagram="m1", genero="m",
                      marca_temporal=datetime(2026, 2, 1, 10, 30, tzinfo=timezone.utc)),
        _make_request(comico_id="m-2", instagram="m2", genero="m",
                      marca_temporal=datetime(2026, 2, 2, 10, 30, tzinfo=timezone.utc)),
        _make_request(comico_id="m-3", instagram="m3", genero="m",
                      marca_temporal=datetime(2026, 2, 3, 10, 30, tzinfo=timezone.utc)),
        _make_request(comico_id="u-1", instagram="u1", genero="unknown",
                      marca_temporal=datetime(2026, 2, 4, 10, 30, tzinfo=timezone.utc)),
    ]

    monkeypatch.setattr(engine, "upsert_comico", _fake_upsert)
    monkeypatch.setattr(engine, "has_recent_acceptance_penalty", _fake_no_penalty)

    ranking, skipped = engine.build_ranking(conn=None, requests=requests, config=_default_config())

    assert skipped == 0
    assert [c.comico_id for c in ranking] == ["f-1", "m-1", "f-2", "m-2", "m-3", "u-1"]


def test_build_ranking_skips_restricted_category(monkeypatch):
    requests = [
        _make_request(comico_id="ok-1",         instagram="ok1",   categoria_silver="priority"),
        _make_request(comico_id="restricted-1",  instagram="restr", categoria_silver="restricted"),
    ]

    def fake_upsert(_, request):
        # restricted devuelve 'restricted'; ok devuelve 'priority'
        return request.comico_id, request.categoria_silver

    monkeypatch.setattr(engine, "upsert_comico", fake_upsert)
    monkeypatch.setattr(engine, "has_recent_acceptance_penalty", _fake_no_penalty)

    ranking, skipped = engine.build_ranking(conn=None, requests=requests, config=_default_config())

    assert skipped == 1
    assert all(c.comico_id != "restricted-1" for c in ranking)


def test_build_ranking_applies_recency_penalty(monkeypatch):
    requests = [
        _make_request(comico_id="penalizado", instagram="pen",  genero="f"),
        _make_request(comico_id="limpio",      instagram="limp", genero="f",
                      marca_temporal=datetime(2026, 2, 2, tzinfo=timezone.utc)),
    ]

    monkeypatch.setattr(engine, "upsert_comico", _fake_upsert)
    # penalizado=True solo para 'penalizado'
    monkeypatch.setattr(engine, "has_recent_acceptance_penalty",
                        lambda _conn, comico_id, _om_id, _cfg: comico_id == "penalizado")

    config = _default_config()
    ranking, _ = engine.build_ranking(conn=None, requests=requests, config=config)

    assert ranking[0].comico_id == "limpio"
    assert ranking[1].comico_id == "penalizado"
    assert ranking[1].score_final == ranking[0].score_final - config.recency_penalty_points


# ---------------------------------------------------------------------------
# fetch_silver_requests — no debe referenciar score_final
# ---------------------------------------------------------------------------

def test_fetch_silver_requests_query_does_not_reference_score_final():
    cursor = RecordingCursor(fetchall_rows=[])
    conn   = RecordingConnection(cursor)

    requests = engine.fetch_silver_requests(conn, open_mic_id=OM_ID)

    assert requests == []
    assert len(cursor.executed) == 1
    query = cursor.executed[0][0].lower()
    assert "from silver.solicitudes" in query
    assert "score_final" not in query
    assert OM_ID in str(cursor.executed[0][1])


# ---------------------------------------------------------------------------
# persist_pending_score — escribe open_mic_id y marca silver como scorado
# ---------------------------------------------------------------------------

def test_persist_pending_score_writes_open_mic_id_and_marks_silver_scorado():
    cursor = RecordingCursor()
    conn   = RecordingConnection(cursor)
    candidate = _make_candidate()

    engine.persist_pending_score(conn, candidate)

    assert len(cursor.executed) == 4

    insert_query, insert_params = cursor.executed[0]
    assert "open_mic_id" in insert_query.lower()
    assert "score_final" not in insert_query.lower()
    assert candidate.open_mic_id in insert_params

    gold_update_query, gold_update_params = cursor.executed[1]
    assert "update gold.solicitudes" in gold_update_query.lower()
    assert "set estado = 'scorado'" in gold_update_query.lower()
    assert gold_update_params == (candidate.solicitud_id,)

    silver_update_query, silver_update_params = cursor.executed[2]
    assert "update silver.solicitudes" in silver_update_query.lower()
    assert "status" in silver_update_query.lower() and "'scorado'" in silver_update_query.lower()
    assert "score_final" not in silver_update_query.lower()
    assert silver_update_params == (candidate.solicitud_id,)
