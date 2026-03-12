"""Tests unitarios para reset_data.py.

Mockea psycopg2.connect e input() para no necesitar BD real ni interacción.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch, call

import pytest


def _make_conn_with_data():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: cur
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    # table_exists → True, table_has_data → True
    cur.fetchone.return_value = ("silver.comicos",)  # to_regclass
    cur.fetchall.return_value = []
    cur.description = []
    return conn, cur


def _run_main(args: list[str], user_input: str = "s"):
    conn, cur = _make_conn_with_data()
    with patch("psycopg2.connect", return_value=conn), \
         patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}), \
         patch("backend.scripts.reset_data.load_dotenv"), \
         patch("builtins.input", return_value=user_input), \
         patch("backend.scripts.reset_data.export_current_data"):
        import sys
        from unittest.mock import patch as p
        with p("sys.argv", ["reset_data.py"] + args):
            from backend.scripts import reset_data
            reset_data.main()
    return conn, cur


class TestResetData:
    def test_requires_confirmation_interactive(self):
        """Sin --yes, llama a input() para pedir confirmación."""
        conn, cur = _make_conn_with_data()
        with patch("psycopg2.connect", return_value=conn), \
             patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}), \
             patch("backend.scripts.reset_data.load_dotenv"), \
             patch("backend.scripts.reset_data.export_current_data"), \
             patch("builtins.input", return_value="s") as mock_input, \
             patch("sys.argv", ["reset_data.py"]):
            from backend.scripts import reset_data
            reset_data.main()
        mock_input.assert_called_once()

    def test_yes_flag_skips_confirmation(self):
        """Con --yes, no llama a input()."""
        conn, cur = _make_conn_with_data()
        with patch("psycopg2.connect", return_value=conn), \
             patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}), \
             patch("backend.scripts.reset_data.load_dotenv"), \
             patch("backend.scripts.reset_data.export_current_data"), \
             patch("builtins.input") as mock_input, \
             patch("sys.argv", ["reset_data.py", "--yes"]):
            from backend.scripts import reset_data
            reset_data.main()
        mock_input.assert_not_called()

    def test_aborts_if_user_says_no(self, capsys):
        """Si el usuario responde 'N', no se ejecuta ningún TRUNCATE."""
        conn, cur = _make_conn_with_data()
        with patch("psycopg2.connect", return_value=conn), \
             patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}), \
             patch("backend.scripts.reset_data.load_dotenv"), \
             patch("backend.scripts.reset_data.export_current_data"), \
             patch("builtins.input", return_value="N"), \
             patch("sys.argv", ["reset_data.py"]):
            from backend.scripts import reset_data
            reset_data.main()

        truncate_calls = [
            c for c in cur.execute.call_args_list
            if "TRUNCATE" in str(c.args[0])
        ]
        assert len(truncate_calls) == 0

    def test_truncates_core_tables(self):
        """Se ejecuta TRUNCATE sobre las tablas principales."""
        conn, cur = _run_main(["--yes"])
        # psycopg2.sql.Composed serializa como Identifier('table'), buscamos por partes
        executed = " ".join(str(c.args[0]) for c in cur.execute.call_args_list)
        assert "TRUNCATE" in executed
        # Identifier('solicitudes') aparece al menos dos veces (silver + bronze)
        assert executed.count("Identifier('solicitudes')") >= 2
        assert "Identifier('bronze')" in executed

    def test_telegram_tables_included_by_default(self):
        """Sin --include-auth, telegram_users y telegram_registration_codes se truncan (son core)."""
        conn, cur = _run_main(["--yes"])
        executed = " ".join(str(c.args[0]) for c in cur.execute.call_args_list)
        assert "telegram_users" in executed
        assert "validation_tokens" not in executed

    def test_include_auth_truncates_validation_tokens(self):
        """Con --include-auth, se truncan también validation_tokens."""
        conn, cur = _run_main(["--yes", "--include-auth"])
        executed = " ".join(str(c.args[0]) for c in cur.execute.call_args_list)
        assert "telegram_users" in executed
        assert "validation_tokens" in executed

    def test_no_backup_skips_export(self):
        """Con --no-backup, no se llama a export_current_data."""
        conn, cur = _make_conn_with_data()
        with patch("psycopg2.connect", return_value=conn), \
             patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}), \
             patch("backend.scripts.reset_data.load_dotenv"), \
             patch("backend.scripts.reset_data.export_current_data") as mock_export, \
             patch("builtins.input", return_value="s"), \
             patch("sys.argv", ["reset_data.py", "--no-backup"]):
            from backend.scripts import reset_data
            reset_data.main()
        mock_export.assert_not_called()

    def test_commits_on_success(self):
        conn, _ = _run_main(["--yes"])
        conn.commit.assert_called_once()

    def test_rollback_on_error(self):
        conn, cur = _make_conn_with_data()
        cur.execute.side_effect = Exception("DB error")
        with patch("psycopg2.connect", return_value=conn), \
             patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}), \
             patch("backend.scripts.reset_data.load_dotenv"), \
             patch("backend.scripts.reset_data.export_current_data"), \
             patch("builtins.input", return_value="s"), \
             patch("sys.argv", ["reset_data.py", "--yes"]):
            from backend.scripts import reset_data
            with pytest.raises(RuntimeError):
                reset_data.main()
        conn.rollback.assert_called_once()
