"""Proceso batch de ingesta Bronze -> Silver leyendo solicitudes pendientes."""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
from typing import Iterable
from uuid import UUID

import psycopg2
from pathlib import Path
from dotenv import load_dotenv

try:
    import gender_guesser.detector as _gender_detector
    _GENDER_DETECTOR = _gender_detector.Detector()
except ImportError:
    _GENDER_DETECTOR = None

# --- INE dictionary (54k+ Spanish names from Padrón Continuo) ---
_INE_NAMES: dict[str, str] = {}
_INE_PATH = Path(__file__).resolve().parents[1] / "data" / "ine_nombres.json"
try:
    with open(_INE_PATH, "r", encoding="utf-8") as _f:
        _INE_NAMES = json.load(_f)
except (FileNotFoundError, json.JSONDecodeError):
    pass

_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"

LOGGER = logging.getLogger("bronze_to_silver_ingestion")
LOG_DIRECTORY = str(Path(__file__).resolve().parents[1] / "logs")
LOG_FILE_PATH = str(Path(__file__).resolve().parents[1] / "logs" / "ingestion.log")

INSTAGRAM_SANITIZER = re.compile(r"^@+")
PHONE_E164_PATTERN = re.compile(r"^\+[1-9][0-9]{7,14}$")
PHONE_INPUT_PATTERN = re.compile(r"^(\+?|00)?[\d\s-]{9,}$")
INSTAGRAM_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9._]+)",
    flags=re.IGNORECASE,
)
EXPERIENCE_MAP = {
    # Opciones v3 (Google Form estandarizado — specs/google_form_campos_spec.md)
    "Es mi primera vez": 0,
    "He probado alguna vez": 1,
    "Llevo tiempo haciendo stand-up": 2,
    "Soy un profesional / tengo cachés": 3,
    # Opciones legacy (formulario anterior — compatibilidad hacia atrás)
    "Llevo tiempo": 2,
    "No me conoces? ....¿Tu tampoco?": 3,
}


@dataclass(frozen=True)
class BronzeRecord:
    id: UUID
    proveedor_id: UUID
    open_mic_id: UUID | None      # None en registros legacy (pre-v3)
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
    os.makedirs(LOG_DIRECTORY, exist_ok=True)

    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    rotating_handler = TimedRotatingFileHandler(
        LOG_FILE_PATH,
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8",
    )
    rotating_handler.setFormatter(formatter)
    logger.addHandler(rotating_handler)


def normalize_instagram_user(instagram_raw: str | None) -> str:
    cleaned = (instagram_raw or "").strip().lower()
    if not cleaned:
        return ""

    url_match = INSTAGRAM_URL_PATTERN.search(cleaned)
    if url_match:
        cleaned = url_match.group(1)
    elif "instagram.com/" in cleaned:
        cleaned = cleaned.split("instagram.com/")[-1]

    cleaned = cleaned.split("?")[0].split("#")[0].strip("/")
    cleaned = INSTAGRAM_SANITIZER.sub("", cleaned)
    return cleaned


def clean_phone(phone_str: str | None) -> str | None:
    if not phone_str:
        return None

    candidate = phone_str.strip()
    if not PHONE_INPUT_PATTERN.match(candidate):
        return None

    compact = re.sub(r"[\s-]+", "", candidate)
    if compact.startswith("00"):
        compact = "+" + compact[2:]

    if compact.startswith("+"):
        normalized = compact
    else:
        digits = re.sub(r"\D", "", compact)
        if len(digits) == 9:
            normalized = f"+34{digits}"
        elif len(digits) >= 10:
            normalized = f"+{digits}"
        else:
            return None

    return normalized if PHONE_E164_PATTERN.match(normalized) else None


def normalize_phone(phone_raw: str | None) -> str | None:
    return clean_phone(phone_raw)


def normalize_row(row: dict[str, str | None]) -> dict[str, object]:
    errors: list[str] = []

    # Campos de nombre: v3 primero, fallback a nombre legacy
    nombre = (
        row.get("Nombre artístico")
        or row.get("¿Nombre?")
        or ""
    ).strip().title()

    # Campos de instagram: v3 primero, fallback legacy
    instagram = normalize_instagram_user(
        row.get("Instagram (sin @)")
        or row.get("¿Instagram?")
    )

    # Campos de teléfono: v3 primero, fallback legacy
    telefono = clean_phone(
        row.get("WhatsApp")
        or row.get("Whatsapp")
    )

    if not nombre:
        errors.append("Campo obligatorio inválido/vacío: Nombre artístico")
    if not instagram:
        errors.append("Campo obligatorio inválido/vacío: Instagram (sin @)")
    if not telefono:
        errors.append("Campo obligatorio inválido/vacío: WhatsApp")

    # Fechas: v3 primero, fallback legacy
    fechas_raw = (
        row.get("¿Qué fechas te vienen bien?")
        or row.get("Fecha")
        or ""
    ).strip()
    fechas_lista = [token.strip() for token in fechas_raw.split(",") if token.strip()]

    normalized = {
        "nombre": nombre,
        "instagram": instagram,
        "telefono": telefono,
        "experiencia_raw": (
            row.get("¿Cuántas veces has actuado en un open mic?")
            or row.get("¿Has actuado alguna vez?")
            or ""
        ).strip(),
        "fechas_raw": fechas_raw,
        "fechas_lista": fechas_lista,
        "disponibilidad_ultimo_minuto": (
            row.get("¿Estarías disponible si nos falla alguien de última hora?")
            or row.get("Si nos falla alguien en ultimo momento ¿Te podemos llamar?")
            or ""
        ).strip(),
        "info_show_cercano": (
            row.get("¿Tienes algún show próximo que quieras mencionar?")
            or row.get("¿Tienes algun Show cercano o algo?")
            or ""
        ).strip(),
        "origen_conocimiento": (
            row.get("¿Cómo nos conociste?")
            or row.get("¿Por donde nos conociste?")
            or ""
        ).strip(),
    }

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "normalized": normalized,
    }


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


def fetch_pending_bronze_rows(conn) -> list[BronzeRecord]:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                proveedor_id,
                open_mic_id,
                nombre_raw,
                instagram_raw,
                telefono_raw,
                experiencia_raw,
                fechas_seleccionadas_raw,
                disponibilidad_ultimo_minuto,
                info_show_cercano,
                origen_conocimiento
            FROM bronze.solicitudes
            WHERE procesado = false
            ORDER BY created_at ASC NULLS LAST, id ASC
            """
        )
        rows = cursor.fetchall()

    return [BronzeRecord(*row) for row in rows]


def resolve_error_metadata_column(conn) -> str | None:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'bronze'
              AND table_name = 'solicitudes'
              AND column_name IN ('metadata', 'raw_data_extra')
            ORDER BY CASE column_name
                WHEN 'metadata' THEN 1
                WHEN 'raw_data_extra' THEN 2
                ELSE 3
            END
            LIMIT 1
            """
        )
        row = cursor.fetchone()

    return row[0] if row else None


_INSTAGRAM_WORD_RE = re.compile(r"[a-zA-Z]{3,}")

# --- Genderize.io (último recurso, 100 calls/día free) ---
_GENDERIZE_URL = "https://api.genderize.io"


def _normalize_name(word: str) -> str:
    """Quita tildes y devuelve lowercase."""
    return unicodedata.normalize("NFKD", word).encode("ascii", "ignore").decode().lower()


def _ine_lookup(word: str) -> str | None:
    """Capa 1: diccionario INE (~55k nombres españoles del Padrón Continuo)."""
    if not _INE_NAMES:
        return None
    key = _normalize_name(word)
    return _INE_NAMES.get(key)


def _gender_guesser_lookup(word: str) -> str | None:
    """Capa 2: gender-guesser (corpus internacional ~40k nombres)."""
    if _GENDER_DETECTOR is None:
        return None
    normalized = _normalize_name(word)
    if not normalized:
        return None
    result = _GENDER_DETECTOR.get_gender(normalized.capitalize())
    if result in ("male", "mostly_male"):
        return "m"
    if result in ("female", "mostly_female"):
        return "f"
    return None


def _genderize_lookup(word: str) -> str | None:
    """Capa 3: genderize.io API (100 calls/día free, localizado a ES)."""
    try:
        import urllib.request
        normalized = _normalize_name(word)
        if not normalized or len(normalized) < 3:
            return None
        url = f"{_GENDERIZE_URL}?name={normalized}&country_id=ES"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
        if data.get("gender") and data.get("probability", 0) >= 0.7:
            return "m" if data["gender"] == "male" else "f"
    except Exception:
        pass
    return None


def _detect_from_word(word: str) -> str | None:
    """Cascada: INE → gender-guesser → genderize.io."""
    for layer in (_ine_lookup, _gender_guesser_lookup, _genderize_lookup):
        result = layer(word)
        if result:
            return result
    return None


def infer_gender(nombre: str | None, instagram: str | None) -> str | None:
    """Infiere género ('m'/'f') a partir del nombre y, si no, del handle de instagram.

    Cascada de 3 capas:
      1. Diccionario INE (55k nombres españoles, offline)
      2. gender-guesser (corpus internacional, offline)
      3. genderize.io (API, 100 calls/día free, localizado a ES)

    Devuelve 'm', 'f', o None si no se puede determinar con suficiente confianza.
    Nunca devuelve 'nb' — ese valor se asigna en el frontend para los no clasificados.
    """
    # 1. Intentar con el primer nombre
    if nombre:
        first = nombre.strip().split()[0] if nombre.strip() else ""
        if first:
            detected = _detect_from_word(first)
            if detected:
                return detected

    # 2. Fallback: segmentos del handle de instagram (divididos por números/guiones bajos)
    if instagram:
        handle = re.sub(r"^@+", "", instagram).lower()
        segments = re.split(r"[0-9_\-\.]+", handle)
        for seg in segments:
            if len(seg) < 3:
                continue
            # Probar prefijos del segmento (4..len) — los nombres suelen ir al inicio
            for end in range(4, len(seg) + 1):
                detected = _detect_from_word(seg[:end])
                if detected:
                    return detected

    return None


def upsert_comico_silver(
    conn,
    instagram: str,
    nombre: str | None,
    telefono: str | None,
    genero: str | None = None,
) -> UUID:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO silver.comicos (
                instagram,
                nombre,
                telefono,
                genero
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (instagram) DO UPDATE
                SET nombre    = COALESCE(EXCLUDED.nombre, silver.comicos.nombre),
                    telefono  = COALESCE(EXCLUDED.telefono, silver.comicos.telefono),
                    genero    = COALESCE(silver.comicos.genero, EXCLUDED.genero)
            RETURNING id
            """,
            (instagram, nombre, telefono, genero),
        )
        row = cursor.fetchone()

        if row:
            return row[0]

        cursor.execute(
            "SELECT id FROM silver.comicos WHERE instagram = %s",
            (instagram,),
        )
        existing = cursor.fetchone()

    if not existing:
        raise RuntimeError(
            "No se pudo obtener/crear comico en silver.comicos para instagram=%s"
            % instagram
        )

    return existing[0]


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

    # Pipeline v3: tiene open_mic_id → usa constraint multi-tenant
    # Pipeline legacy: open_mic_id es None → usa constraint anterior
    is_v3 = bronze.open_mic_id is not None

    with conn.cursor() as cursor:
        for event_date in event_dates:
            if is_v3:
                cursor.execute(
                    """
                    INSERT INTO silver.solicitudes (
                        bronze_id,
                        proveedor_id,
                        open_mic_id,
                        comico_id,
                        fecha_evento,
                        nivel_experiencia,
                        disponibilidad_ultimo_minuto,
                        show_cercano,
                        origen_conocimiento,
                        status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'normalizado')
                    ON CONFLICT (comico_id, open_mic_id, fecha_evento) DO NOTHING
                    """,
                    (
                        str(bronze.id),
                        str(bronze.proveedor_id),
                        str(bronze.open_mic_id),
                        str(comico_id),
                        event_date,
                        level,
                        available_last_minute,
                        bronze.info_show_cercano,
                        bronze.origen_conocimiento,
                    ),
                )
            else:
                # Legacy: sin open_mic_id, constraint original (comico_id, fecha_evento)
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

    return inserted_count


def mark_bronze_processed(conn, bronze_id: UUID) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            "UPDATE bronze.solicitudes SET procesado = true WHERE id = %s",
            (str(bronze_id),),
        )


def register_ingestion_error(
    conn,
    bronze_id: UUID,
    error_metadata_column: str | None,
    message: str,
    phase: str,
) -> None:
    error_timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    if error_metadata_column:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE bronze.solicitudes
                SET {error_metadata_column} = COALESCE({error_metadata_column}, '{{}}'::jsonb)
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
                (message, error_timestamp, phase, str(bronze_id)),
            )
        return

    LOGGER.error(
        "Error de ingesta bronze_id=%s | phase=%s | message=%s",
        bronze_id,
        phase,
        message,
    )


def process_single_solicitud(
    conn,
    bronze: BronzeRecord,
    today: date,
    error_metadata_column: str | None,
    detalles_descarte: list[dict[str, str]],
) -> int:
    savepoint_name = f"bronze_{str(bronze.id).replace('-', '_')}"
    phase = "inicio"

    with conn.cursor() as cursor:
        cursor.execute(f"SAVEPOINT {savepoint_name}")

    try:
        phase = "normalizacion"
        # Usar nombres de campos v3 (normalize_row soporta fallback a legacy)
        form_row = {
            "Nombre artístico":                                           bronze.nombre_raw,
            "Instagram (sin @)":                                          bronze.instagram_raw,
            "WhatsApp":                                                   bronze.telefono_raw,
            "¿Cuántas veces has actuado en un open mic?":                bronze.experiencia_raw,
            "¿Qué fechas te vienen bien?":                               bronze.fechas_seleccionadas_raw,
            "¿Estarías disponible si nos falla alguien de última hora?": bronze.disponibilidad_ultimo_minuto,
            "¿Tienes algún show próximo que quieras mencionar?":         bronze.info_show_cercano,
            "¿Cómo nos conociste?":                                      bronze.origen_conocimiento,
        }
        normalized_result = normalize_row(form_row)
        if not normalized_result["is_valid"]:
            joined_errors = "; ".join(normalized_result["errors"])
            raise ValueError(joined_errors)

        normalized = normalized_result["normalized"]
        instagram = str(normalized["instagram"])
        telefono = str(normalized["telefono"])
        nombre = str(normalized["nombre"])

        phase = "parsing_fechas"
        event_dates = parse_event_dates(str(normalized["fechas_raw"]), today)

        phase = "mapeo_experiencia"
        level = map_experience_level(str(normalized["experiencia_raw"]))

        phase = "mapeo_disponibilidad_ultimo_minuto"
        available_last_minute = parse_last_minute_availability(
            str(normalized["disponibilidad_ultimo_minuto"])
        )

        if not event_dates:
            motivo = "Sin fechas futuras válidas"
            detalles_descarte.append({"id": str(bronze.id), "motivo": motivo})
            LOGGER.info("Bronze %s descartado: %s", bronze.id, motivo)
            mark_bronze_processed(conn, bronze.id)
            return 0

        phase = "upsert_comico_silver"
        genero = infer_gender(nombre, instagram)
        comico_id = upsert_comico_silver(
            conn,
            instagram=instagram,
            nombre=nombre,
            telefono=telefono,
            genero=genero,
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
        mark_bronze_processed(conn, bronze.id)

        if inserted == 0:
            motivo = "Duplicado en Silver (sin nuevas filas para insertar)"
            detalles_descarte.append({"id": str(bronze.id), "motivo": motivo})
            LOGGER.warning("Bronze %s descartado: %s", bronze.id, motivo)

        LOGGER.info(
            "Bronze %s procesado | comico_id=%s | fechas_insertadas=%s",
            bronze.id,
            comico_id,
            len(event_dates),
        )
        return inserted
    except Exception as exc:  # noqa: BLE001
        motivo = f"Error de validación/procesamiento en fase '{phase}': {exc}"
        detalles_descarte.append({"id": str(bronze.id), "motivo": motivo})
        LOGGER.exception(
            "Error procesando Bronze %s en fase=%s: %s",
            bronze.id,
            phase,
            exc,
        )
        with conn.cursor() as cursor:
            cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")

        register_ingestion_error(
            conn,
            bronze_id=bronze.id,
            error_metadata_column=error_metadata_column,
            message=str(exc),
            phase=phase,
        )
        return 0


def run_pipeline() -> dict[str, object]:
    load_dotenv(dotenv_path=_ROOT_ENV)
    configure_logging()
    today = date.today()
    detalles_descarte: list[dict[str, str]] = []

    try:
        with db_connection() as conn:
            expired = expire_old_reserves(conn, today)
            pending_rows = fetch_pending_bronze_rows(conn)
            error_metadata_column = resolve_error_metadata_column(conn)

            inserted_total = 0
            processed_total = 0

            for bronze in pending_rows:
                inserted_total += process_single_solicitud(
                    conn,
                    bronze,
                    today,
                    error_metadata_column,
                    detalles_descarte,
                )
                processed_total += 1

        result = {
            "status": "success",
            "pendientes_leidos": len(pending_rows),
            "filas_procesadas": processed_total,
            "filas_silver_insertadas": inserted_total,
            "reservas_expiradas": expired,
            "errores": [
                f"ID {item['id']}: {item['motivo']}" for item in detalles_descarte
            ],
        }
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Error fatal durante la ejecución de la ingesta: %s", exc)
        result = {
            "status": "error",
            "pendientes_leidos": 0,
            "filas_procesadas": 0,
            "filas_silver_insertadas": 0,
            "reservas_expiradas": 0,
            "errores": [f"Error fatal: {exc}"],
        }

    print(json.dumps(result))
    return result


def _unit_tests_clean_phone() -> None:
    test_cases = {
        "666555888": "+34666555888",
        "666-555-888": "+34666555888",
        "66-65-55-88-8": "+34666555888",
        "666 555 888": "+34666555888",
        "+34666555888": "+34666555888",
        "0034666555888": "+34666555888",
    }

    for raw_phone, expected in test_cases.items():
        cleaned = clean_phone(raw_phone)
        assert cleaned == expected, (
            f"clean_phone falló para '{raw_phone}'. "
            f"Esperado={expected} | obtenido={cleaned}"
        )


if __name__ == "__main__":
    run_pipeline()
