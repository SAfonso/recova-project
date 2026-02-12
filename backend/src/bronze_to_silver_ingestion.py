"""Pipeline de ingesta Bronze -> Silver con gestión de reserva (60 días)."""

from __future__ import annotations

import logging
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, Sequence
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor

LOGGER = logging.getLogger("bronze_to_silver_ingestion")

INSTAGRAM_SANITIZER = re.compile(r"^@+")
PHONE_E164_PATTERN = re.compile(r"^\+[1-9][0-9]{7,14}$")
EXPERIENCE_MAP = {
    "Es mi primera vez": 0,
    "He probado alguna vez": 1,
    "Llevo tiempo": 2,
    "No me conoces? ....¿Tu tampoco?": 3,
}


@dataclass(frozen=True)
class BronzeRecord:
    id: UUID
    proveedor_id: UUID
    nombre_raw: str | None
    instagram_raw: str | None
    whatsapp_raw: str | None
    experiencia_raw: str | None
    fechas_seleccionadas_raw: str | None
    disponibilidad_ultimo_minuto: str | None


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
    if not experience_raw:
        raise ValueError("experiencia_raw vacío")

    if experience_raw not in EXPERIENCE_MAP:
        raise ValueError(f"experiencia_raw desconocido: {experience_raw}")

    return EXPERIENCE_MAP[experience_raw]


def parse_event_dates(raw_dates: str | None, today: date) -> list[date]:
    if not raw_dates:
        return []

    parsed_dates: list[date] = []
    for chunk in raw_dates.split(","):
        token = chunk.strip()
        if not token:
            continue

        event_date = datetime.strptime(token, "%d-%m-%y").date()
        if event_date >= today:
            parsed_dates.append(event_date)

    return sorted(set(parsed_dates))


def parse_last_minute_availability(value: str | None) -> bool:
    if not value:
        return False
    normalized = value.strip().lower()
    return normalized in {"sí", "si", "true", "1", "yes"}


def fetch_pending_bronze_rows(conn) -> Sequence[BronzeRecord]:
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(
            """
            SELECT
                id,
                proveedor_id,
                nombre_raw,
                instagram_raw,
                whatsapp_raw,
                experiencia_raw,
                fechas_seleccionadas_raw,
                disponibilidad_ultimo_minuto
            FROM public.solicitudes_bronze
            WHERE procesado = false
            ORDER BY created_at ASC
            """
        )
        records = cursor.fetchall()

    return [BronzeRecord(**record) for record in records]


def mark_bronze_as_error(conn, bronze_id: UUID, reason: str) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO public.solicitudes_silver (
                bronze_id,
                proveedor_id,
                comico_id,
                fecha_evento,
                nivel_experiencia,
                status,
                metadata_ia
            )
            SELECT
                b.id,
                b.proveedor_id,
                c.id,
                CURRENT_DATE,
                0,
                'error_ingesta',
                jsonb_build_object('error', %s)
            FROM public.solicitudes_bronze b
            JOIN public.comicos_master c ON c.instagram_user = %s
            WHERE b.id = %s
            ON CONFLICT (bronze_id, fecha_evento) DO UPDATE
            SET status = EXCLUDED.status,
                metadata_ia = EXCLUDED.metadata_ia
            """,
            (reason, "error_sistema", str(bronze_id)),
        )


def upsert_comico_identity(
    conn,
    instagram_user: str,
    nombre_artistico: str | None,
    telefono: str | None,
) -> UUID:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO public.comicos_master (
                instagram_user,
                nombre_artistico,
                telefono
            )
            VALUES (%s, %s, %s)
            ON CONFLICT (instagram_user) DO UPDATE
            SET nombre_artistico = COALESCE(EXCLUDED.nombre_artistico, public.comicos_master.nombre_artistico),
                telefono = CASE
                    WHEN EXCLUDED.telefono IS NOT NULL THEN EXCLUDED.telefono
                    ELSE public.comicos_master.telefono
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
            UPDATE public.solicitudes_silver
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
                INSERT INTO public.solicitudes_silver (
                    bronze_id,
                    proveedor_id,
                    comico_id,
                    fecha_evento,
                    nivel_experiencia,
                    disponibilidad_ultimo_minuto,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'normalizado')
                ON CONFLICT (comico_id, fecha_evento) DO NOTHING
                """,
                (
                    str(bronze.id),
                    str(bronze.proveedor_id),
                    str(comico_id),
                    event_date,
                    level,
                    available_last_minute,
                ),
            )
            inserted_count += cursor.rowcount

        cursor.execute(
            "UPDATE public.solicitudes_bronze SET procesado = true WHERE id = %s",
            (str(bronze.id),),
        )

    return inserted_count


def process_pending_bronze(conn, today: date) -> tuple[int, int]:
    pending_rows = fetch_pending_bronze_rows(conn)
    processed = 0
    inserted = 0

    for bronze in pending_rows:
        savepoint_name = f"bronze_{str(bronze.id).replace('-', '_')}"
        try:
            with conn.cursor() as cursor:
                cursor.execute(f"SAVEPOINT {savepoint_name}")

            instagram_user = normalize_instagram_user(bronze.instagram_raw)
            if not instagram_user:
                raise ValueError("instagram_raw inválido")

            telefono = normalize_phone(bronze.whatsapp_raw)
            event_dates = parse_event_dates(bronze.fechas_seleccionadas_raw, today)
            level = map_experience_level(bronze.experiencia_raw)
            available_last_minute = parse_last_minute_availability(
                bronze.disponibilidad_ultimo_minuto
            )

            if not event_dates:
                LOGGER.info("Bronze %s omitido: sin fechas futuras", bronze.id)
                with conn.cursor() as cursor:
                    cursor.execute(
                        "UPDATE public.solicitudes_bronze SET procesado = true WHERE id = %s",
                        (str(bronze.id),),
                    )
                processed += 1
                continue

            comico_id = upsert_comico_identity(
                conn,
                instagram_user=instagram_user,
                nombre_artistico=bronze.nombre_raw,
                telefono=telefono,
            )

            inserted += insert_silver_rows(
                conn,
                bronze=bronze,
                comico_id=comico_id,
                event_dates=event_dates,
                level=level,
                available_last_minute=available_last_minute,
            )
            processed += 1
            LOGGER.info(
                "Bronze %s procesado | comico_id=%s | fechas_insertadas=%s",
                bronze.id,
                comico_id,
                len(event_dates),
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Error procesando Bronze %s: %s", bronze.id, exc)
            with conn.cursor() as cursor:
                cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
                cursor.execute(
                    """
                    UPDATE public.solicitudes_bronze
                    SET procesado = true,
                        raw_data_extra = COALESCE(raw_data_extra, '{}'::jsonb)
                          || jsonb_build_object('ingestion_error', %s)
                    WHERE id = %s
                    """,
                    (str(exc), str(bronze.id)),
                )

    return processed, inserted


def run_pipeline() -> None:
    configure_logging()
    today = date.today()

    with db_connection() as conn:
        expired = expire_old_reserves(conn, today)
        processed, inserted = process_pending_bronze(conn, today)

    LOGGER.info(
        "Ingesta finalizada | reservas_expiradas=%s | bronze_procesados=%s | silver_insertadas=%s",
        expired,
        processed,
        inserted,
    )


if __name__ == "__main__":
    run_pipeline()
