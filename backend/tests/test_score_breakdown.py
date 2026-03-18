"""Tests for E3 — score_breakdown audit trail in scoring engine."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

os.environ.setdefault("WEBHOOK_API_KEY", "test-key")
os.environ.setdefault("SUPABASE_URL", "http://fake-supabase")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-service-key")
os.environ.setdefault("DATABASE_URL", "postgresql://fake:fake@localhost/fake")

from backend.src.core.scoring_config import ScoringConfig
from backend.src.scoring_engine import (
    CandidateScore,
    SilverRequest,
    build_ranking,
)


def _make_request(
    categoria="general",
    fechas="2026-04-10",
    metadata=None,
    nombre="Test Comic",
    instagram="testcomic",
    genero="m",
) -> SilverRequest:
    return SilverRequest(
        solicitud_id="sol-1",
        comico_id="com-1",
        nombre=nombre,
        telefono="+34600000000",
        instagram=instagram,
        genero=genero,
        categoria_silver=categoria,
        fechas_disponibles=fechas,
        marca_temporal=datetime.now(timezone.utc),
        metadata=metadata or {},
    )


def _mock_conn_no_penalty():
    """Connection mock where upsert_comico returns standard and no recency penalty."""
    conn = MagicMock()
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cursor

    call_count = {"n": 0}

    def execute_side(sql, params=None):
        sql_lower = (sql or "").strip().lower()
        call_count["n"] += 1
        if "insert into gold.comicos" in sql_lower:
            cursor.fetchone.return_value = ("com-1", "standard")
        elif "ultimas_ediciones" in sql_lower:
            cursor.fetchone.return_value = (False,)
        else:
            cursor.fetchone.return_value = None

    cursor.execute = MagicMock(side_effect=execute_side)
    return conn


def _mock_conn_with_penalty():
    """Connection mock where recency penalty is True."""
    conn = MagicMock()
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cursor

    def execute_side(sql, params=None):
        sql_lower = (sql or "").strip().lower()
        if "insert into gold.comicos" in sql_lower:
            cursor.fetchone.return_value = ("com-1", "standard")
        elif "ultimas_ediciones" in sql_lower:
            cursor.fetchone.return_value = (True,)
        else:
            cursor.fetchone.return_value = None

    cursor.execute = MagicMock(side_effect=execute_side)
    return conn


class TestScoreBreakdown:
    """Tests para el desglose de score (score_breakdown)."""

    def test_basic_breakdown_standard(self):
        """Standard category: base_score=50, total=50."""
        config = ScoringConfig.default("om-1")
        conn = _mock_conn_no_penalty()
        req = _make_request(fechas="2026-04-10, 2026-04-17")

        ranking, _ = build_ranking(conn, [req], config)

        assert len(ranking) == 1
        bd = ranking[0].score_breakdown
        assert bd["base_score"] == 50
        assert bd["categoria"] == "standard"
        assert bd["total"] == 50
        assert "recency_penalty" not in bd
        assert "single_date_bonus" not in bd

    def test_breakdown_with_recency_penalty(self):
        """Standard with recency penalty: 50 - 20 = 30."""
        config = ScoringConfig.default("om-1")
        conn = _mock_conn_with_penalty()
        req = _make_request(fechas="2026-04-10, 2026-04-17")

        ranking, _ = build_ranking(conn, [req], config)

        assert len(ranking) == 1
        bd = ranking[0].score_breakdown
        assert bd["base_score"] == 50
        assert bd["recency_penalty"] == -20
        assert bd["total"] == 30

    def test_breakdown_with_single_date_bonus(self):
        """Single date adds +40 bonus."""
        config = ScoringConfig.default("om-1")
        conn = _mock_conn_no_penalty()
        req = _make_request(fechas="2026-04-10")  # single date

        ranking, _ = build_ranking(conn, [req], config)

        assert len(ranking) == 1
        bd = ranking[0].score_breakdown
        assert bd["base_score"] == 50
        assert bd["single_date_bonus"] == 40
        assert bd["total"] == 90

    def test_breakdown_with_recency_and_single_date(self):
        """Both penalty and bonus: 50 - 20 + 40 = 70."""
        config = ScoringConfig.default("om-1")
        conn = _mock_conn_with_penalty()
        req = _make_request(fechas="2026-04-10")

        ranking, _ = build_ranking(conn, [req], config)

        bd = ranking[0].score_breakdown
        assert bd["base_score"] == 50
        assert bd["recency_penalty"] == -20
        assert bd["single_date_bonus"] == 40
        assert bd["total"] == 70

    def test_breakdown_priority_category(self):
        """Priority category: base_score=70."""
        config = ScoringConfig.default("om-1")
        conn = MagicMock()
        cursor = MagicMock()
        cursor.__enter__ = MagicMock(return_value=cursor)
        cursor.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value = cursor

        def execute_side(sql, params=None):
            sql_lower = (sql or "").strip().lower()
            if "insert into gold.comicos" in sql_lower:
                cursor.fetchone.return_value = ("com-1", "priority")
            elif "ultimas_ediciones" in sql_lower:
                cursor.fetchone.return_value = (False,)
            else:
                cursor.fetchone.return_value = None

        cursor.execute = MagicMock(side_effect=execute_side)

        req = _make_request(categoria="priority", fechas="2026-04-10, 2026-04-17")
        ranking, _ = build_ranking(conn, [req], config)

        bd = ranking[0].score_breakdown
        assert bd["base_score"] == 70
        assert bd["categoria"] == "priority"
        assert bd["total"] == 70

    def test_breakdown_with_custom_rules(self):
        """Custom scoring rules add bonus to breakdown."""
        raw_config = {
            "scoring_type": "custom",
            "custom_scoring_rules": [
                {"field": "experience", "condition": "equals", "value": "pro", "points": 15, "enabled": True},
            ],
        }
        config = ScoringConfig.from_dict("om-1", raw_config)
        conn = _mock_conn_no_penalty()
        req = _make_request(metadata={"experience": "pro"}, fechas="2026-04-10, 2026-04-17")

        ranking, _ = build_ranking(conn, [req], config)

        bd = ranking[0].score_breakdown
        assert bd["base_score"] == 50
        assert bd["custom_rules_bonus"] == 15
        assert bd["total"] == 65

    def test_breakdown_custom_rules_zero_not_included(self):
        """Custom rules bonus of 0 is not included in breakdown."""
        raw_config = {
            "scoring_type": "custom",
            "custom_scoring_rules": [
                {"field": "experience", "condition": "equals", "value": "pro", "points": 15, "enabled": True},
            ],
        }
        config = ScoringConfig.from_dict("om-1", raw_config)
        conn = _mock_conn_no_penalty()
        req = _make_request(metadata={"experience": "amateur"}, fechas="2026-04-10, 2026-04-17")

        ranking, _ = build_ranking(conn, [req], config)

        bd = ranking[0].score_breakdown
        assert "custom_rules_bonus" not in bd
        assert bd["total"] == 50

    def test_breakdown_present_in_candidate_score(self):
        """CandidateScore dataclass stores the breakdown dict."""
        cs = CandidateScore(
            nombre="Test",
            telefono="123",
            instagram="test",
            genero="m",
            comico_id="c1",
            categoria="standard",
            open_mic_id="om1",
            score_final=50,
            marca_temporal=None,
            fecha_evento=datetime.now(timezone.utc).date(),
            penalizado_por_recencia=False,
            score_breakdown={"base_score": 50, "total": 50},
        )
        assert cs.score_breakdown["base_score"] == 50
        assert cs.score_breakdown["total"] == 50

    def test_breakdown_total_matches_score_final(self):
        """Breakdown total always matches the candidate's score_final."""
        config = ScoringConfig.default("om-1")
        conn = _mock_conn_with_penalty()
        req = _make_request(fechas="2026-04-10")

        ranking, _ = build_ranking(conn, [req], config)

        c = ranking[0]
        assert c.score_breakdown["total"] == c.score_final
