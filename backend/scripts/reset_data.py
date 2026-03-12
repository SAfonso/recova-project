"""reset_data.py — borra todos los datos de bronze/silver/gold (mantiene esquemas).

Genera backup CSV previo por defecto. Pide confirmación interactiva.

Uso:
    python backend/scripts/reset_data.py [--yes] [--include-auth] [--no-backup]

Flags:
    --yes           Omite confirmación interactiva
    --include-auth  También trunca silver.telegram_users, silver.telegram_registration_codes
                    y silver.validation_tokens
    --no-backup     Omite la generación de CSV de respaldo
"""

from __future__ import annotations

import argparse
import csv
import os
from datetime import datetime
from pathlib import Path

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKUP_DIR = ROOT_DIR / "backups"

_CORE_TABLES = [
    "gold.solicitudes",
    "gold.comicos",
    "silver.lineup_slots",
    "silver.solicitudes",
    "silver.comicos",
    "silver.open_mics",
    "silver.organization_members",
    "silver.proveedores",
    "bronze.solicitudes",
]

_AUTH_TABLES = [
    "silver.telegram_users",
    "silver.telegram_registration_codes",
    "silver.validation_tokens",
]

_BACKUP_TABLES = _CORE_TABLES + _AUTH_TABLES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Borra todos los datos de la BD (mantiene esquemas).")
    parser.add_argument("--yes", "-y", action="store_true", help="Omite confirmación interactiva")
    parser.add_argument("--include-auth", action="store_true", help="Trunca también tablas de auth/telegram")
    parser.add_argument("--no-backup", action="store_true", help="Omite generación de CSV de respaldo")
    return parser.parse_args()


def _table_exists(cur, schema: str, table: str) -> bool:
    cur.execute("SELECT to_regclass(%s);", (f"{schema}.{table}",))
    return cur.fetchone()[0] is not None


def _table_has_data(cur, schema: str, table: str) -> bool:
    cur.execute(
        sql.SQL("SELECT EXISTS (SELECT 1 FROM {}.{} LIMIT 1);").format(
            sql.Identifier(schema), sql.Identifier(table)
        )
    )
    return bool(cur.fetchone()[0])


def export_current_data(cur, backup_dir: Path) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for table_ref in _BACKUP_TABLES:
        schema, table = table_ref.split(".", 1)
        if not _table_exists(cur, schema, table):
            continue
        if not _table_has_data(cur, schema, table):
            continue

        cur.execute(
            sql.SQL("SELECT * FROM {}.{};").format(sql.Identifier(schema), sql.Identifier(table))
        )
        rows = cur.fetchall()
        headers = [col.name for col in cur.description]

        out_file = backup_dir / f"{schema}_{table}_{timestamp}.csv"
        with out_file.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        print(f"Backup generado: {out_file.relative_to(ROOT_DIR)}")


def main() -> None:
    args = parse_args()
    load_dotenv(ROOT_DIR / ".env")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("No se encontró DATABASE_URL en .env")

    tables_to_truncate = list(_CORE_TABLES)
    if args.include_auth:
        tables_to_truncate += _AUTH_TABLES

    if not args.yes:
        print("ADVERTENCIA: se borrarán TODOS los datos de bronze/silver/gold.")
        if args.include_auth:
            print("            También se borrarán datos de auth/telegram.")
        answer = input("¿Continuar? [s/N]: ").strip().lower()
        if answer != "s":
            print("Operación cancelada.")
            return

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            if not args.no_backup:
                export_current_data(cur, BACKUP_DIR)

            print("Truncando tablas...")
            for table_ref in tables_to_truncate:
                schema, table = table_ref.split(".", 1)
                if not _table_exists(cur, schema, table):
                    print(f"  [skip] {table_ref} no existe")
                    continue
                cur.execute(
                    sql.SQL("TRUNCATE {}.{} CASCADE;").format(
                        sql.Identifier(schema), sql.Identifier(table)
                    )
                )
                print(f"  [ok]   {table_ref}")

        conn.commit()
        print("\nReset de datos completado.")
    except Exception as exc:
        conn.rollback()
        raise RuntimeError("Error durante reset. Rollback ejecutado.") from exc
    finally:
        conn.close()


if __name__ == "__main__":
    main()
