from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import setup_db


class FakeCursor:
    def __init__(self, fetchone_values: list[tuple] | None = None):
        self.fetchone_values = list(fetchone_values or [])
        self.fetchall_values: list[tuple] = []
        self.description = []
        self.executed: list[tuple[object, tuple | None]] = []

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchone(self):
        return self.fetchone_values.pop(0)

    def fetchall(self):
        return self.fetchall_values


def test_split_table_ref():
    assert setup_db.split_table_ref("silver.solicitudes") == ("silver", "solicitudes")


def test_table_exists_true():
    cursor = FakeCursor(fetchone_values=[("silver.solicitudes",)])
    assert setup_db.table_exists(cursor, "silver.solicitudes") is True


def test_table_exists_false():
    cursor = FakeCursor(fetchone_values=[(None,)])
    assert setup_db.table_exists(cursor, "silver.solicitudes") is False


def test_table_has_data_true():
    cursor = FakeCursor(fetchone_values=[(True,)])
    assert setup_db.table_has_data(cursor, "silver.solicitudes") is True


def test_table_has_data_false():
    cursor = FakeCursor(fetchone_values=[(False,)])
    assert setup_db.table_has_data(cursor, "silver.solicitudes") is False


def test_execute_sql_file_executes_content(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(setup_db, "ROOT_DIR", tmp_path)
    sql_file = tmp_path / "specs" / "sql" / "sample.sql"
    sql_file.parent.mkdir(parents=True)
    sql_file.write_text("SELECT 1;", encoding="utf-8")

    cursor = FakeCursor()
    setup_db.execute_sql_file(cursor, sql_file)

    assert len(cursor.executed) == 1
    assert cursor.executed[0][0] == "SELECT 1;"
    assert "Esquema aplicado" in capsys.readouterr().out


def test_execute_sql_file_missing_raises(tmp_path):
    cursor = FakeCursor()
    missing = tmp_path / "nope.sql"

    with pytest.raises(FileNotFoundError):
        setup_db.execute_sql_file(cursor, missing)


def test_verify_enums_uses_expected_refs(monkeypatch):
    expected = {
        "silver.tipo_categoria": True,
        "silver.tipo_status": False,
    }

    def fake_enum_exists(_cursor, schema_name, enum_name):
        return expected[f"{schema_name}.{enum_name}"]

    cursor = FakeCursor()
    monkeypatch.setattr(setup_db, "enum_exists", fake_enum_exists)

    assert setup_db.verify_enums(cursor) == expected


def test_export_current_data_generates_csv(tmp_path, monkeypatch):
    cursor = FakeCursor()
    cursor.description = [SimpleNamespace(name="id"), SimpleNamespace(name="name")]
    cursor.fetchall_values = [("1", "Recova")]

    monkeypatch.setattr(setup_db, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(setup_db, "BACKUP_TABLES", ("silver.proveedores",))
    monkeypatch.setattr(setup_db, "table_exists", lambda _cursor, _table_ref: True)
    monkeypatch.setattr(setup_db, "table_has_data", lambda _cursor, _table_ref: True)

    setup_db.export_current_data(cursor, tmp_path)

    generated = list(tmp_path.glob("silver_proveedores_*.csv"))
    assert len(generated) == 1
    assert generated[0].read_text(encoding="utf-8").splitlines()[0] == "id,name"


def test_get_database_url_from_env(monkeypatch):
    monkeypatch.setattr(setup_db, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.setenv("DATABASE_URL", "postgresql://example")

    assert setup_db.get_database_url() == "postgresql://example"


def test_get_database_url_raises_when_missing(monkeypatch):
    monkeypatch.setattr(setup_db, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        setup_db.get_database_url()


def test_ensure_backup_dir_creates_path(tmp_path, monkeypatch):
    backup_path = tmp_path / "backups"
    monkeypatch.setattr(setup_db, "BACKUP_DIR", backup_path)

    result = setup_db.ensure_backup_dir()

    assert result == backup_path
    assert backup_path.exists()
    assert backup_path.is_dir()


def test_sql_sequence_files_exist():
    for path in setup_db.SQL_SEQUENCE:
        assert isinstance(path, Path)
        assert path.exists(), f"No existe archivo SQL en secuencia: {path}"

    assert setup_db.SEED_SQL_PATH.exists(), "No existe archivo seed_data.sql"
