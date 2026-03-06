"""Tests unitarios para seed_full.py.

Mockea psycopg2.connect para no necesitar BD real.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest


def _run_main():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: cur
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("psycopg2.connect", return_value=conn), \
         patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}), \
         patch("backend.scripts.seed_full.load_dotenv"):
        from backend.scripts import seed_full
        seed_full.main()

    return conn, cur


class TestSeedFull:
    def test_inserts_one_proveedor(self):
        conn, cur = _run_main()
        prov_calls = [
            c for c in cur.execute.call_args_list
            if "INSERT INTO silver.proveedores" in str(c.args[0])
        ]
        assert len(prov_calls) == 1

    def test_inserts_three_open_mics(self):
        conn, cur = _run_main()
        om_calls = [
            c for c in cur.execute.call_args_list
            if "INSERT INTO silver.open_mics" in str(c.args[0])
        ]
        assert len(om_calls) == 3

    def test_inserts_thirty_comics_total(self):
        conn, cur = _run_main()
        comic_calls = [
            c for c in cur.execute.call_args_list
            if "INSERT INTO silver.comicos" in str(c.args[0])
        ]
        assert len(comic_calls) == 30

    def test_inserts_thirty_bronze_solicitudes(self):
        conn, cur = _run_main()
        bronze_calls = [
            c for c in cur.execute.call_args_list
            if "INSERT INTO bronze.solicitudes" in str(c.args[0])
        ]
        assert len(bronze_calls) == 30

    def test_inserts_thirty_silver_solicitudes(self):
        conn, cur = _run_main()
        silver_calls = [
            c for c in cur.execute.call_args_list
            if "INSERT INTO silver.solicitudes" in str(c.args[0])
        ]
        assert len(silver_calls) == 30

    def test_commits_on_success(self):
        conn, _ = _run_main()
        conn.commit.assert_called_once()

    def test_rollback_on_error(self):
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = lambda s: cur
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur.execute.side_effect = Exception("DB error")

        with patch("psycopg2.connect", return_value=conn), \
             patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}), \
             patch("backend.scripts.seed_full.load_dotenv"):
            from backend.scripts import seed_full
            with pytest.raises(RuntimeError):
                seed_full.main()

        conn.rollback.assert_called_once()

    def test_prints_summary(self, capsys):
        _run_main()
        out = capsys.readouterr().out
        assert "Proveedor creado" in out
        assert "Open mic 1" in out
        assert "Open mic 2" in out
        assert "Open mic 3" in out
        assert "Seed completo" in out
