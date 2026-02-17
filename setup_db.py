"""Inicializa el esquema de BD en Supabase/PostgreSQL en orden controlado."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
import os
from pathlib import Path

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
BACKUP_DIR = ROOT_DIR / "backups"
SQL_SEQUENCE = [
    ROOT_DIR / "specs/sql/bronze_multi_proveedor_master.sql",
    ROOT_DIR / "specs/sql/silver_relacional.sql",
    ROOT_DIR / "specs/sql/migrations/20260212_alter_tipo_solicitud_status.sql",
    ROOT_DIR / "specs/sql/migrations/20260217_fix_anon_update_policy_silver_comicos.sql",
    ROOT_DIR / "specs/sql/gold_relacional.sql",
    ROOT_DIR / "specs/sql/migrations/20260218_create_lineup_candidates_and_validate_lineup.sql",
]
SEED_SQL_PATH = ROOT_DIR / "specs/sql/seed_data.sql"
ENUM_TYPES = (
    ("silver", "tipo_categoria"),
    ("silver", "tipo_status"),
    ("gold", "categoria_comico"),
    ("gold", "estado_solicitud"),
)
BACKUP_TABLES = (
    "bronze.solicitudes",
    "silver.comicos",
    "silver.solicitudes",
    "silver.proveedores",
    "gold.comicos",
    "gold.solicitudes",
)

RESET_SQL = """
DROP SCHEMA IF EXISTS gold CASCADE;
DROP SCHEMA IF EXISTS silver CASCADE;
DROP SCHEMA IF EXISTS bronze CASCADE;
DROP FUNCTION IF EXISTS public.set_updated_at() CASCADE;
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ejecuta setup de esquema SQL para AI LineUp Architect."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Limpia tablas y enums críticos antes del despliegue.",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Ejecuta specs/sql/seed_data.sql después de aplicar el esquema.",
    )
    return parser.parse_args()


def get_database_url() -> str:
    load_dotenv(ROOT_DIR / ".env")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("No se encontró DATABASE_URL en .env")
    return database_url


def ensure_backup_dir() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_DIR


def split_table_ref(table_ref: str) -> tuple[str, str]:
    schema_name, table_name = table_ref.split(".", maxsplit=1)
    return schema_name, table_name


def table_exists(cursor: psycopg2.extensions.cursor, table_ref: str) -> bool:
    cursor.execute("SELECT to_regclass(%s);", (table_ref,))
    return cursor.fetchone()[0] is not None


def table_has_data(cursor: psycopg2.extensions.cursor, table_ref: str) -> bool:
    schema_name, table_name = split_table_ref(table_ref)
    cursor.execute(
        sql.SQL("SELECT EXISTS (SELECT 1 FROM {}.{} LIMIT 1);").format(
            sql.Identifier(schema_name),
            sql.Identifier(table_name),
        )
    )
    return bool(cursor.fetchone()[0])


def export_current_data(cursor: psycopg2.extensions.cursor, backup_dir: Path) -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    exported_files: list[Path] = []

    print("\nPreparando respaldo local preventivo antes del reset...")

    for table_ref in BACKUP_TABLES:
        if not table_exists(cursor, table_ref):
            print(f"- Tabla {table_ref} no existe. Se omite backup.")
            continue

        if not table_has_data(cursor, table_ref):
            print(f"- Tabla {table_ref} sin datos. Se omite backup.")
            continue

        schema_name, table_name = split_table_ref(table_ref)
        cursor.execute(
            sql.SQL("SELECT * FROM {}.{};").format(
                sql.Identifier(schema_name),
                sql.Identifier(table_name),
            )
        )
        rows = cursor.fetchall()
        headers = [column.name for column in cursor.description]

        output_file = backup_dir / f"{schema_name}_{table_name}_{timestamp}.csv"
        with output_file.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(headers)
            writer.writerows(rows)

        exported_files.append(output_file)
        print(f"📦 Backup generado: {output_file.relative_to(ROOT_DIR)}")

    if not exported_files:
        print(
            "No se generaron archivos de backup: no hay tablas objetivo o no contienen datos."
        )


def enum_exists(
    cursor: psycopg2.extensions.cursor, enum_schema: str, enum_name: str
) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM pg_type t
            JOIN pg_namespace n ON n.oid = t.typnamespace
            WHERE t.typname = %s
              AND n.nspname = %s
        );
        """,
        (enum_name, enum_schema),
    )
    return bool(cursor.fetchone()[0])


def verify_enums(cursor: psycopg2.extensions.cursor) -> dict[str, bool]:
    status = {
        f"{schema_name}.{enum_name}": enum_exists(cursor, schema_name, enum_name)
        for schema_name, enum_name in ENUM_TYPES
    }
    for enum_ref, exists in status.items():
        print(f"Enum {enum_ref}: {'EXISTE' if exists else 'NO EXISTE'}")
    return status


def execute_sql_file(cursor: psycopg2.extensions.cursor, sql_path: Path) -> None:
    if not sql_path.exists():
        raise FileNotFoundError(f"Archivo SQL no encontrado: {sql_path}")

    sql = sql_path.read_text(encoding="utf-8")
    print(f"🏗️ Esquema aplicado: {sql_path.relative_to(ROOT_DIR)}")
    cursor.execute(sql)


def main() -> None:
    args = parse_args()
    database_url = get_database_url()

    conn = psycopg2.connect(database_url)

    try:
        with conn.cursor() as cur:
            print("Verificando enums antes del despliegue...")
            verify_enums(cur)

            if args.reset:
                backup_dir = ensure_backup_dir()
                export_current_data(cur, backup_dir)
                print("\n--reset detectado: limpiando tablas y enums...")
                cur.execute(RESET_SQL)
                print("🗑️ Reset completado (Tablas y Enums eliminados)")
                print("Estado de enums luego del reset:")
                verify_enums(cur)

            print("\nEjecutando scripts de esquema en orden obligatorio...")
            for sql_file in SQL_SEQUENCE:
                execute_sql_file(cur, sql_file)

            if args.seed:
                execute_sql_file(cur, SEED_SQL_PATH)
                print("🌱 Datos de prueba inyectados correctamente.")

        conn.commit()
    except Exception as exc:
        conn.rollback()
        raise RuntimeError(
            "Error durante setup de BD. Se ejecutó rollback para mantener consistencia."
        ) from exc
    finally:
        conn.close()

    print("\n✅ Setup de base de datos completado correctamente.")
    print(
        "Recuerda añadir la carpeta backups/ a tu .gitignore para no subir datos sensibles al repositorio"
    )


if __name__ == "__main__":
    main()
