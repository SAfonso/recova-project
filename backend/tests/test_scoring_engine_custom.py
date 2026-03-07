"""Tests TDD — scoring_engine aplica custom_scoring_rules (Sprint 10, v0.15.0).

Cubre (spec custom_scoring_spec §scoring_engine):
  build_ranking aplica bono custom cuando scoring_type='custom' y metadata coincide
  build_ranking NO aplica bono si scoring_type='basic'
  regla disabled → no afecta el score
  puntos negativos → penalización en score final
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.src import scoring_engine as engine
from backend.src.core.scoring_config import ScoringConfig

OM_ID = "om-sprint10-00000000-0000-0000-0000-000000000010"


# ---------------------------------------------------------------------------
# Helpers
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


def _make_request(metadata: dict | None = None, **kwargs) -> engine.SilverRequest:
    defaults = dict(
        comico_id="id-x",
        nombre="Test",
        telefono="+34000000000",
        instagram="test",
        genero="m",
        categoria_silver="standard",
        fechas_disponibles="2026-03-14",
        marca_temporal=datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc),
        solicitud_id="11111111-1111-1111-1111-111111111111",
        metadata=metadata or {},
    )
    return engine.SilverRequest(**{**defaults, **kwargs})


def _fake_upsert(conn, request):
    return request.comico_id, "standard"


def _fake_no_penalty(*_args, **_kwargs):
    return False


def _custom_config(rules: list[dict]) -> ScoringConfig:
    return ScoringConfig.from_dict(OM_ID, {
        "scoring_type": "custom",
        "custom_scoring_rules": rules,
        "single_date_boost": {"enabled": False, "boost_points": 0},
    })


def _basic_config(rules: list[dict] | None = None) -> ScoringConfig:
    return ScoringConfig.from_dict(OM_ID, {
        "scoring_type": "basic",
        "custom_scoring_rules": rules or [],
        "single_date_boost": {"enabled": False, "boost_points": 0},
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_execute_scoring_applies_custom_bonus(monkeypatch):
    """Metadata con campo que coincide → score base + bonus custom."""
    monkeypatch.setattr(engine, "upsert_comico", _fake_upsert)
    monkeypatch.setattr(engine, "has_recent_acceptance_penalty", _fake_no_penalty)

    config = _custom_config([
        {"field": "¿Haces humor negro?", "condition": "equals", "value": "Sí",
         "points": 10, "enabled": True, "description": "Bono humor negro"},
    ])

    request = _make_request(metadata={"¿Haces humor negro?": "Sí"})
    conn = RecordingConnection(RecordingCursor())

    ranking, skipped = engine.build_ranking(conn, [request], config)

    assert len(ranking) == 1
    # base_score standard = 50, custom_bonus = 10 → total 60
    assert ranking[0].score_final == 60


def test_execute_scoring_no_bonus_if_basic(monkeypatch):
    """scoring_type='basic' → custom_scoring_rules no se aplican."""
    monkeypatch.setattr(engine, "upsert_comico", _fake_upsert)
    monkeypatch.setattr(engine, "has_recent_acceptance_penalty", _fake_no_penalty)

    config = _basic_config(rules=[
        {"field": "¿Haces humor negro?", "condition": "equals", "value": "Sí",
         "points": 10, "enabled": True, "description": "Bono humor negro"},
    ])

    request = _make_request(metadata={"¿Haces humor negro?": "Sí"})
    conn = RecordingConnection(RecordingCursor())

    ranking, _ = engine.build_ranking(conn, [request], config)

    assert len(ranking) == 1
    # base_score standard = 50, sin custom_bonus
    assert ranking[0].score_final == 50


def test_execute_scoring_disabled_rule_no_bonus(monkeypatch):
    """Regla con enabled=False → no suma puntos."""
    monkeypatch.setattr(engine, "upsert_comico", _fake_upsert)
    monkeypatch.setattr(engine, "has_recent_acceptance_penalty", _fake_no_penalty)

    config = _custom_config([
        {"field": "¿Haces humor negro?", "condition": "equals", "value": "Sí",
         "points": 10, "enabled": False, "description": "Desactivada"},
    ])

    request = _make_request(metadata={"¿Haces humor negro?": "Sí"})
    conn = RecordingConnection(RecordingCursor())

    ranking, _ = engine.build_ranking(conn, [request], config)

    assert len(ranking) == 1
    assert ranking[0].score_final == 50  # solo base, sin bono


def test_execute_scoring_negative_rule(monkeypatch):
    """Puntos negativos en una regla → penalización en score final."""
    monkeypatch.setattr(engine, "upsert_comico", _fake_upsert)
    monkeypatch.setattr(engine, "has_recent_acceptance_penalty", _fake_no_penalty)

    config = _custom_config([
        {"field": "¿Haces humor negro?", "condition": "equals", "value": "Sí",
         "points": -15, "enabled": True, "description": "Penalización humor negro"},
    ])

    request = _make_request(metadata={"¿Haces humor negro?": "Sí"})
    conn = RecordingConnection(RecordingCursor())

    ranking, _ = engine.build_ranking(conn, [request], config)

    assert len(ranking) == 1
    # base_score standard = 50, custom_bonus = -15 → total 35
    assert ranking[0].score_final == 35
