from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BRONZE_SQL = PROJECT_ROOT / "specs/sql/bronze_multi_proveedor_master.sql"
SILVER_SQL = PROJECT_ROOT / "specs/sql/silver_relacional.sql"
SEED_SQL = PROJECT_ROOT / "specs/sql/seed_data.sql"
MIGRATION_SQL = PROJECT_ROOT / "specs/sql/migrations/20260212_alter_tipo_solicitud_status.sql"
GOLD_SQL = PROJECT_ROOT / "specs/sql/gold_relacional.sql"


def read_lower(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_sql_files_exist():
    assert BRONZE_SQL.exists()
    assert SILVER_SQL.exists()
    assert SEED_SQL.exists()
    assert MIGRATION_SQL.exists()
    assert GOLD_SQL.exists()


def test_bronze_defines_only_solicitudes_table():
    content = read_lower(BRONZE_SQL)
    assert "create table if not exists bronze.solicitudes" in content
    assert "create table if not exists bronze.comicos" not in content
    assert "drop table bronze.comicos" in content


def test_bronze_solicitudes_contains_raw_fields_and_jsonb():
    content = read_lower(BRONZE_SQL)
    assert "instagram_raw text" in content
    assert "nombre_raw text" in content
    assert "telefono_raw text" in content
    assert "raw_data_extra jsonb" in content


def test_silver_contains_master_and_transactional_tables():
    content = read_lower(SILVER_SQL)
    assert "create table if not exists silver.comicos" in content
    assert "create table if not exists silver.proveedores" in content
    assert "create table if not exists silver.solicitudes" in content
    assert "genero text not null default 'unknown'" in content
    assert "is_gold boolean" not in content
    assert "is_priority boolean" not in content
    assert "is_restricted boolean" not in content


def test_silver_enum_types_live_in_silver_schema():
    content = read_lower(SILVER_SQL)
    assert "create type silver.tipo_categoria" in content
    assert "create type silver.tipo_status" in content


def test_silver_solicitudes_has_lineage_fk_to_bronze():
    content = read_lower(SILVER_SQL)
    assert "foreign key (bronze_id)" in content
    assert "references bronze.solicitudes(id)" in content


def test_silver_comicos_enforces_instagram_normalization():
    content = read_lower(SILVER_SQL)
    assert "chk_silver_comicos_instagram_normalizado" in content
    assert "instagram_user = lower(instagram_user)" in content


def test_seed_uses_bronze_and_silver_with_lineage_column():
    content = read_lower(SEED_SQL)
    assert "insert into bronze.solicitudes" in content
    assert "insert into silver.solicitudes" in content
    assert "bronze_id" in content


def test_seed_avoids_public_schema_inserts():
    content = read_lower(SEED_SQL)
    assert "insert into public." not in content


def test_migration_targets_silver_tipo_status():
    content = read_lower(MIGRATION_SQL)
    assert "create type silver.tipo_status" in content
    assert "alter type silver.tipo_status add value if not exists 'error_ingesta'" in content


def test_gold_contains_master_and_history_tables():
    content = read_lower(GOLD_SQL)
    assert "create table if not exists gold.comicos" in content
    assert "create table if not exists gold.solicitudes" in content
    assert "create table if not exists gold.comicos_gold" not in content
    assert "create table if not exists gold.solicitudes_gold" not in content
    assert "telefono text not null unique" in content
    assert "genero text not null default 'unknown'" in content
    assert "whatsapp text not null unique" not in content


def test_gold_defines_expected_enum_types():
    content = read_lower(GOLD_SQL)
    assert "create type gold.genero_comico" not in content
    assert "create type gold.categoria_comico" in content
    assert "create type gold.estado_solicitud" in content


def test_gold_supports_lineage_bridge_with_silver():
    content = read_lower(GOLD_SQL)
    assert "create or replace view gold.vw_linaje_silver_a_gold" in content
    assert "from silver.solicitudes" in content
    assert "join silver.comicos" in content
    assert "sc.telefono = c.telefono" in content


def test_gold_enforces_rls_and_service_role_permissions():
    content = read_lower(GOLD_SQL)
    assert "alter table gold.comicos enable row level security" in content
    assert "alter table gold.solicitudes enable row level security" in content
    assert "create policy p_service_role_all_gold_comicos" in content
    assert "create policy p_service_role_all_gold_solicitudes" in content
    assert "grant usage on schema gold to service_role" in content
