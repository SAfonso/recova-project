"""Pipeline atómico de ingesta Bronze -> Silver para ejecuciones por evento."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable
from uuid import UUID

import psycopg2
from dotenv import load_dotenv

LOGGER = logging.getLogger("bronze_to_silver_ingestion")

INSTAGRAM_SANITIZER = re.compile(r"^@+")
PHONE_E164_PATTERN = re.compile(r"^\+[1-9][0-9]{7,14}$")
EXPERIENCE_MAP = {
    "Es mi primera vez": 0,
    "He probado alguna vez": 1,
    "Llevo tiempo": 2,
    "No me conoces? ....¿Tu tampoco?": 3,
}
DEFAULT_PROVEEDOR_ID = "recova-om"


@dataclass(frozen=True)
class BronzeRecord:
    id: UUID
    proveedor_id: UUID
    nombre_raw: str | None
    instagram_raw: str | None
    telefono_raw: str | None
    experiencia_raw: str | None
    fechas_seleccionadas_raw: str | None
    disponibilidad_ultimo_minuto: str | None
    info_show_cercano: str | None
    origen_conocimiento: str | None


@contextmanager
def db_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL no está configurada")

    conn = psycopg2.connect(database_url)
    conn.autocommit = False
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def configure_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingesta atómica Bronze -> Silver para una solicitud raw"
    )
    parser.add_argument("--nombre_raw")
    parser.add_argument("--instagram_raw")
    parser.add_argument("--telefono_raw")
    parser.add_argument("--whatsapp", dest="telefono_raw")
    parser.add_argument("--Whatsapp", dest="telefono_raw")
    parser.add_argument("--experiencia_raw")
    parser.add_argument("--fechas_raw")
    parser.add_argument("--disponibilidad_uv")
    parser.add_argument("--show_cercano_raw")
    parser.add_argument("--conociste_raw")
    return parser.parse_args()


def normalize_instagram_user(instagram_raw: str | None) -> str:
    cleaned = (instagram_raw or "").strip().lower()
    cleaned = INSTAGRAM_SANITIZER.sub("", cleaned)
    return cleaned


def normalize_phone(phone_raw: str | None) -> str | None:
    if not phone_raw:
        return None

    compact = re.sub(r"\s+", "", phone_raw.strip())
    return compact if PHONE_E164_PATTERN.match(compact) else None


def map_experience_level(experience_raw: str | None) -> int:
    normalized = (experience_raw or "").strip()
    level = EXPERIENCE_MAP.get(normalized)
    if level is None:
        LOGGER.warning(
            "experiencia_raw desconocido '%s'; se usará nivel por defecto=0",
            experience_raw,
        )
        return 0
    return level


def parse_event_dates(raw_dates: str | None, today: date) -> list[date]:
    if not raw_dates:
        return []

    parsed_dates: list[date] = []
    for chunk in raw_dates.split(","):
        token = chunk.strip()
        if not token:
            continue

        try:
            event_date = datetime.strptime(token, "%d-%m-%y").date()
        except ValueError:
            LOGGER.warning(
                "Token de fecha inválido '%s'; formato esperado DD-MM-YY. Se ignora.",
                token,
            )
            continue

        if event_date >= today:
            parsed_dates.append(event_date)

    return sorted(set(parsed_dates))


def parse_last_minute_availability(value: str | None) -> bool:
    if not value:
        return False

    normalized = unicodedata.normalize("NFD", value.strip().lower())
    normalized = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    )
    return "si" in normalized


def validate_default_proveedor_id() -> None:
    """Valida formato UUID solo cuando la referencia tenga forma de UUID."""
    if DEFAULT_PROVEEDOR_ID.count("-") != 4:
        return

    try:
        UUID(DEFAULT_PROVEEDOR_ID)
    except ValueError as exc:
        raise ValueError(
            "DEFAULT_PROVEEDOR_ID parece UUID pero no es válido. "
            "Si silver.proveedores.id es UUID, usa un UUID correcto."
        ) from exc


def resolve_proveedor_id(conn, proveedor_ref: str) -> UUID:
    with conn.cursor() as cursor:
        try:
            proveedor_uuid = UUID(proveedor_ref)
            cursor.execute(
                "SELECT id FROM silver.proveedores WHERE id = %s",
                (str(proveedor_uuid),),
            )
        except ValueError:
            cursor.execute(
                "SELECT id FROM silver.proveedores WHERE slug = %s",
                (proveedor_ref,),
            )

        row = cursor.fetchone()

    if not row:
        raise ValueError(f"proveedor_id inválido o no encontrado: {proveedor_ref}")

    return row[0]


def insert_bronze_row(conn, args: argparse.Namespace, proveedor_id: UUID) -> BronzeRecord:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO bronze.solicitudes (
                proveedor_id,
                nombre_raw,
                instagram_raw,
                telefono_raw,
                experiencia_raw,
                fechas_seleccionadas_raw,
                disponibilidad_ultimo_minuto,
                info_show_cercano,
                origen_conocimiento,
                procesado,
                raw_data_extra
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, false, '{}'::jsonb)
            RETURNING
                id,
                proveedor_id,
                nombre_raw,
                instagram_raw,
                telefono_raw,
                experiencia_raw,
                fechas_seleccionadas_raw,
                disponibilidad_ultimo_minuto,
                info_show_cercano,
                origen_conocimiento
            """,
            (
                str(proveedor_id),
                args.nombre_raw,
                args.instagram_raw,
                args.telefono_raw,
                args.experiencia_raw,
                args.fechas_raw,
                args.disponibilidad_uv,
                args.show_cercano_raw,
                args.conociste_raw,
            ),
        )
        row = cursor.fetchone()

    return BronzeRecord(*row)


def upsert_comico_silver(
    conn,
    instagram_user: str,
    nombre_artistico: str | None,
    telefono: str | None,
) -> UUID:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO silver.comicos (
                instagram_user,
                nombre_artistico,
                telefono
            )
            VALUES (%s, %s, %s)
            ON CONFLICT (instagram_user) DO UPDATE
            SET nombre_artistico = COALESCE(EXCLUDED.nombre_artistico, silver.comicos.nombre_artistico),
                telefono = CASE
                    WHEN EXCLUDED.telefono IS NOT NULL THEN EXCLUDED.telefono
                    ELSE silver.comicos.telefono
                END,
                updated_at = NOW()
            RETURNING id
            """,
            (instagram_user, nombre_artistico, telefono),
        )
        comico_id = cursor.fetchone()[0]

    return comico_id


def expire_old_reserves(conn, today: date) -> int:
    boundary_date = today - timedelta(days=60)
    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE silver.solicitudes
            SET status = 'expirado',
                updated_at = NOW()
            WHERE status = 'no_seleccionado'
              AND fecha_evento <= %s
            """,
            (boundary_date,),
        )
        return cursor.rowcount


def insert_silver_rows(
    conn,
    bronze: BronzeRecord,
    comico_id: UUID,
    event_dates: Iterable[date],
    level: int,
    available_last_minute: bool,
) -> int:
    inserted_count = 0
    with conn.cursor() as cursor:
        for event_date in event_dates:
            cursor.execute(
                """
                INSERT INTO silver.solicitudes (
                    bronze_id,
                    proveedor_id,
                    comico_id,
                    fecha_evento,
                    nivel_experiencia,
                    disponibilidad_ultimo_minuto,
                    show_cercano,
                    origen_conocimiento,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'normalizado')
                ON CONFLICT (comico_id, fecha_evento) DO NOTHING
                """,
                (
                    str(bronze.id),
                    str(bronze.proveedor_id),
                    str(comico_id),
                    event_date,
                    level,
                    available_last_minute,
                    bronze.info_show_cercano,
                    bronze.origen_conocimiento,
                ),
            )
            inserted_count += cursor.rowcount

        cursor.execute(
            "UPDATE bronze.solicitudes SET procesado = true WHERE id = %s",
            (str(bronze.id),),
        )

    return inserted_count


def process_single_solicitud(conn, bronze: BronzeRecord, today: date) -> int:
    savepoint_name = f"bronze_{str(bronze.id).replace('-', '_')}"
    phase = "inicio"

    with conn.cursor() as cursor:
        cursor.execute(f"SAVEPOINT {savepoint_name}")

    try:
        phase = "normalizacion"
        instagram_user = normalize_instagram_user(bronze.instagram_raw)
        if not instagram_user:
            raise ValueError("instagram_raw inválido")

        telefono = normalize_phone(bronze.telefono_raw)
        phase = "parsing_fechas"
        event_dates = parse_event_dates(bronze.fechas_seleccionadas_raw, today)
        phase = "mapeo_experiencia"
        level = map_experience_level(bronze.experiencia_raw)
        available_last_minute = parse_last_minute_availability(
            bronze.disponibilidad_ultimo_minuto
        )

        if not event_dates:
            LOGGER.info("Bronze %s omitido: sin fechas futuras", bronze.id)
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE bronze.solicitudes SET procesado = true WHERE id = %s",
                    (str(bronze.id),),
                )
            return 0

        phase = "upsert_comico_silver"
        comico_id = upsert_comico_silver(
            conn,
            instagram_user=instagram_user,
            nombre_artistico=bronze.nombre_raw,
            telefono=telefono,
        )

        phase = "insert_silver"
        inserted = insert_silver_rows(
            conn,
            bronze=bronze,
            comico_id=comico_id,
            event_dates=event_dates,
            level=level,
            available_last_minute=available_last_minute,
        )
        LOGGER.info(
            "Bronze %s procesado | comico_id=%s | fechas_insertadas=%s",
            bronze.id,
            comico_id,
            len(event_dates),
        )
        return inserted
    except Exception as exc:  # noqa: BLE001
        error_timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        LOGGER.exception(
            "Error procesando Bronze %s en fase=%s: %s",
            bronze.id,
            phase,
            exc,
        )
        with conn.cursor() as cursor:
            cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
            cursor.execute(
                """
                UPDATE bronze.solicitudes
                SET procesado = true,
                    raw_data_extra = COALESCE(raw_data_extra, '{}'::jsonb)
                      || jsonb_build_object(
                            'estado', 'error_ingesta',
                            'error_log',
                            jsonb_build_object(
                                'message', %s,
                                'timestamp', %s,
                                'phase', %s
                            )
                        )
                WHERE id = %s
                """,
                (str(exc), error_timestamp, phase, str(bronze.id)),
            )
        raise


def run_pipeline() -> None:
    load_dotenv()
    configure_logging()
    args = parse_args()
    today = date.today()

    try:
        validate_default_proveedor_id()
        with db_connection() as conn:
            # Si `silver.proveedores.id` es UUID, configura DEFAULT_PROVEEDOR_ID con un UUID válido.
            proveedor_id = resolve_proveedor_id(conn, DEFAULT_PROVEEDOR_ID)
            bronze = insert_bronze_row(conn, args, proveedor_id)
            expire_old_reserves(conn, today)
            inserted = process_single_solicitud(conn, bronze, today)

        print(
            json.dumps(
                {
                    "status": "success",
                    "bronze_id": str(bronze.id),
                    "fechas_creadas": inserted,
                }
            )
        )
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "error", "message": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    run_pipeline()
