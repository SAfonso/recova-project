"""Tests unitarios para seed_conditional.py.

Mockea psycopg2.connect para no necesitar BD real.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, call, patch

import pytest


def _make_conn(open_mics_rows):
    """Devuelve un mock de psycopg2.connect con los open mics configurados."""
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: cur
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    # Primera query: SELECT open_mics con COUNT
    cur.fetchall.return_value = open_mics_rows
    # INSERT comico: RETURNING id
    cur.fetchone.return_value = ("fake-comico-id",)

    return conn, cur


def _run_main(open_mics_rows):
    conn, cur = _make_conn(open_mics_rows)
    with patch("psycopg2.connect", return_value=conn), \
         patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}), \
         patch("backend.scripts.seed_conditional.load_dotenv"):
        from backend.scripts import seed_conditional
        seed_conditional.main()
    return conn, cur


class TestSeedConditional:
    def test_skips_open_mic_with_solicitudes(self, capsys):
        """Si total > 0, no se ejecutan INSERTs de seed."""
        open_mics = [
            ("om-uuid-1", "prov-uuid-1", "Recova Open Mic", 5),
        ]
        conn, cur = _run_main(open_mics)
        out = capsys.readouterr().out
        assert "[skip]" in out
        assert "[seed]" not in out

    def test_seeds_open_mic_without_solicitudes(self, capsys):
        """Si total == 0, se insertan cómicos, bronze y silver."""
        open_mics = [
            ("om-uuid-2", "prov-uuid-1", "Comedy Lab", 0),
        ]
        conn, cur = _run_main(open_mics)
        out = capsys.readouterr().out
        assert "[seed]" in out

        # Debe haber llamadas a execute con INSERT
        executed_sqls = [str(c.args[0]) for c in cur.execute.call_args_list]
        assert any("INSERT INTO silver.comicos" in s for s in executed_sqls)
        assert any("INSERT INTO bronze.solicitudes" in s for s in executed_sqls)
        assert any("INSERT INTO silver.solicitudes" in s for s in executed_sqls)

    def test_inserts_ten_comics_per_open_mic(self):
        """Se insertan exactamente 10 cómicos por open mic sin solicitudes."""
        open_mics = [
            ("om-uuid-3", "prov-uuid-1", "Test Mic", 0),
        ]
        conn, cur = _run_main(open_mics)

        insert_comico_calls = [
            c for c in cur.execute.call_args_list
            if "INSERT INTO silver.comicos" in str(c.args[0])
        ]
        assert len(insert_comico_calls) == 10

    def test_instagram_contains_open_mic_prefix(self):
        """El instagram de cada cómico incluye los primeros 8 chars del open_mic_id."""
        open_mic_id = "abcdef12-0000-0000-0000-000000000099"
        open_mics = [
            (open_mic_id, "prov-uuid-1", "Test Mic", 0),
        ]
        conn, cur = _run_main(open_mics)

        # Params del primer INSERT de comicos
        insert_calls = [
            c for c in cur.execute.call_args_list
            if "INSERT INTO silver.comicos" in str(c.args[0])
        ]
        for c in insert_calls:
            instagram = c.args[1][1]  # segundo param: instagram
            assert "abcdef12" in instagram

    def test_commits_on_success(self):
        open_mics = [("om-uuid-4", "prov-uuid-1", "Test", 0)]
        conn, _ = _run_main(open_mics)
        conn.commit.assert_called_once()

    def test_rollback_on_error(self):
        """Si un INSERT falla, se ejecuta rollback."""
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = lambda s: cur
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur.fetchall.return_value = [("om-uuid-5", "prov-uuid-1", "Test", 0)]
        cur.fetchone.side_effect = Exception("DB error")

        with patch("psycopg2.connect", return_value=conn), \
             patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}), \
             patch("backend.scripts.seed_conditional.load_dotenv"):
            from backend.scripts import seed_conditional
            with pytest.raises(RuntimeError):
                seed_conditional.main()

        conn.rollback.assert_called_once()

    def test_no_open_mics_exits_cleanly(self, capsys):
        """Sin open mics, termina sin errores ni INSERTs."""
        conn, cur = _run_main([])
        out = capsys.readouterr().out
        assert "No hay open mics" in out
        insert_calls = [
            c for c in cur.execute.call_args_list
            if "INSERT" in str(c.args[0])
        ]
        assert len(insert_calls) == 0
