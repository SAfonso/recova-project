"""Motor de scoring para proponer lineups semanales desde datos Silver/Gold."""

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv

LOGGER = logging.getLogger("scoring_engine")
LOG_DIRECTORY = "/root/RECOVA/backend/logs"
LOG_FILE_PATH = "/root/RECOVA/backend/logs/scoring_engine.log"

CATEGORY_BONUS = {
    "gold": 12,
    "preferred": 10,
    "standard": 0,
}

CATEGORY_ALIASES = {
    "priority": "preferred",
    "restricted": "blacklist",
}

SILVER_TO_GOLD_CATEGORY = {
    "general": "standard",
    "priority": "priority",
    "gold": "gold",
    "restricted": "restricted",
}


@dataclass(frozen=True)
class SilverRequest:
    comico_id: str
    nombre: str
    telefono: str
    instagram: str
    genero: str
    categoria_silver: str
    fechas_disponibles: str
    marca_temporal: datetime | None


@dataclass(frozen=True)
class CandidateScore:
    nombre: str
    telefono: str
    instagram: str
    genero: str
    comico_id: str
    categoria: str
    score_final: int
    marca_temporal: datetime | None
    fecha_evento: date
    penalizado_por_recencia: bool
    bono_bala_unica: bool


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
        backupCount=14,
        encoding="utf-8",
    )
    rotating_handler.setFormatter(formatter)
    logger.addHandler(rotating_handler)


def normalize_category(raw_category: str | None) -> str:
    category = (raw_category or "standard").strip().lower()
    return CATEGORY_ALIASES.get(category, category)


def map_silver_category_to_gold(raw_category: str | None) -> str:
    normalized = (raw_category or "general").strip().lower()
    return SILVER_TO_GOLD_CATEGORY.get(normalized, "standard")


@contextmanager
def db_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL no está configurada")

    import psycopg2

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


def fetch_silver_requests(conn) -> list[SilverRequest]:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                s.comico_id::text AS comico_id,
                COALESCE(c.nombre, b.nombre_raw, '') AS nombre,
                c.telefono AS telefono,
                COALESCE(c.instagram, '') AS instagram,
                COALESCE(c.genero, 'unknown') AS genero,
                c.categoria::text AS categoria_silver,
                to_char(s.fecha_evento, 'YYYY-MM-DD') AS fechas_disponibles,
                s.created_at AS marca_temporal
            FROM silver.solicitudes s
            JOIN silver.comicos c ON c.id = s.comico_id
            LEFT JOIN bronze.solicitudes b ON b.id = s.bronze_id
            WHERE c.telefono IS NOT NULL
            ORDER BY s.created_at ASC NULLS LAST
            """
        )
        rows = cursor.fetchall()

    requests: list[SilverRequest] = []
    for row in rows:
        requests.append(
            SilverRequest(
                comico_id=row[0],
                nombre=row[1],
                telefono=row[2],
                instagram=row[3],
                genero=row[4],
                categoria_silver=row[5],
                fechas_disponibles=row[6],
                marca_temporal=row[7],
            )
        )
    return requests


def upsert_comico(conn, request: SilverRequest) -> tuple[str, str]:
    categoria_gold = map_silver_category_to_gold(request.categoria_silver)
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO gold.comicos (id, telefono, instagram, nombre, genero, categoria)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET telefono = EXCLUDED.telefono,
                instagram = EXCLUDED.instagram,
                nombre = COALESCE(EXCLUDED.nombre, gold.comicos.nombre),
                genero = EXCLUDED.genero,
                categoria = EXCLUDED.categoria
            RETURNING id::text, categoria::text
            """,
            (
                request.comico_id,
                request.telefono,
                request.instagram,
                request.nombre,
                request.genero,
                categoria_gold,
            ),
        )
        upserted = cursor.fetchone()

    if not upserted:
        return request.comico_id, normalize_category(categoria_gold)
    return upserted[0], normalize_category(upserted[1])


def has_recent_acceptance_penalty(conn, comico_id: str) -> bool:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            WITH ultimos_shows AS (
                SELECT DISTINCT fecha_evento
                FROM gold.solicitudes
                WHERE estado = 'aceptado'
                ORDER BY fecha_evento DESC
                LIMIT 2
            )
            SELECT EXISTS (
                SELECT 1
                FROM gold.solicitudes sg
                JOIN ultimos_shows us ON us.fecha_evento = sg.fecha_evento
                WHERE sg.comico_id = %s
                  AND sg.estado = 'aceptado'
            )
            """,
            (comico_id,),
        )
        result = cursor.fetchone()

    return bool(result[0]) if result else False


def parse_primary_date(fechas_disponibles: str) -> date:
    tokens = [item.strip() for item in (fechas_disponibles or "").split(",") if item.strip()]
    for token in tokens:
        for pattern in ("%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y"):
            try:
                return datetime.strptime(token, pattern).date()
            except ValueError:
                continue
    return datetime.now(timezone.utc).date()


def has_single_date(fechas_disponibles: str) -> bool:
    tokens = [item.strip() for item in (fechas_disponibles or "").split(",") if item.strip()]
    return len(tokens) == 1


def compute_score(category: str, penalty_recent_acceptance: bool, single_date: bool) -> int:
    score = CATEGORY_BONUS.get(category, 0)
    if penalty_recent_acceptance:
        score -= 100
    if single_date:
        score += 20
    return score


def persist_pending_score(conn, candidate: CandidateScore) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO gold.solicitudes (
                id,
                comico_id,
                fecha_evento,
                estado,
                score_aplicado,
                marca_temporal
            )
            VALUES (%s, %s, %s, 'pendiente', %s, %s)
            """,
            (
                str(uuid4()),
                candidate.comico_id,
                candidate.fecha_evento,
                float(candidate.score_final),
                candidate.marca_temporal,
            ),
        )


def build_ranking(conn, requests: list[SilverRequest]) -> tuple[list[CandidateScore], int]:
    scored_candidates: list[CandidateScore] = []
    skipped_blacklist = 0

    for request in requests:
        try:
            comico_id, category = upsert_comico(conn, request)
            if category == "blacklist":
                skipped_blacklist += 1
                LOGGER.info("Descartado por blacklist: %s", request.telefono)
                continue

            penalty = has_recent_acceptance_penalty(conn, comico_id)
            single_date = has_single_date(request.fechas_disponibles)
            score = compute_score(category, penalty, single_date)

            scored_candidates.append(
                CandidateScore(
                    nombre=request.nombre,
                    telefono=request.telefono,
                    instagram=request.instagram,
                    genero=request.genero,
                    comico_id=comico_id,
                    categoria=category,
                    score_final=score,
                    marca_temporal=request.marca_temporal,
                    fecha_evento=parse_primary_date(request.fechas_disponibles),
                    penalizado_por_recencia=penalty,
                    bono_bala_unica=single_date,
                )
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception(
                "Error procesando solicitud telefono=%s: %s",
                request.telefono,
                exc,
            )

    women_nb_candidates = sorted(
        [candidate for candidate in scored_candidates if candidate.genero in {"f", "nb"}],
        key=lambda item: (
            -item.score_final,
            item.marca_temporal or datetime.max.replace(tzinfo=timezone.utc),
        ),
    )
    men_candidates = sorted(
        [candidate for candidate in scored_candidates if candidate.genero == "m"],
        key=lambda item: (
            -item.score_final,
            item.marca_temporal or datetime.max.replace(tzinfo=timezone.utc),
        ),
    )
    other_candidates = sorted(
        [candidate for candidate in scored_candidates if candidate.genero not in {"m", "f", "nb"}],
        key=lambda item: (
            -item.score_final,
            item.marca_temporal or datetime.max.replace(tzinfo=timezone.utc),
        ),
    )

    balanced_ranking: list[CandidateScore] = []
    women_index = 0
    men_index = 0

    while women_index < len(women_nb_candidates) or men_index < len(men_candidates):
        if women_index < len(women_nb_candidates):
            balanced_ranking.append(women_nb_candidates[women_index])
            women_index += 1
        if men_index < len(men_candidates):
            balanced_ranking.append(men_candidates[men_index])
            men_index += 1

    balanced_ranking.extend(other_candidates)

    return balanced_ranking, skipped_blacklist


def execute_scoring() -> dict[str, Any]:
    with db_connection() as conn:
        requests = fetch_silver_requests(conn)
        ranking, skipped_blacklist = build_ranking(conn, requests)

        for candidate in ranking:
            persist_pending_score(conn, candidate)

    top_10 = [
        {
            "nombre": candidate.nombre,
            "telefono": candidate.telefono,
            "instagram": candidate.instagram,
            "genero": candidate.genero,
            "categoria": candidate.categoria,
            "score_final": candidate.score_final,
            "marca_temporal": candidate.marca_temporal.isoformat()
            if candidate.marca_temporal
            else None,
        }
        for candidate in ranking[:10]
    ]

    return {
        "status": "ok",
        "filas_procesadas": len(requests),
        "filas_insertadas_gold": len(ranking),
        "filas_descartadas_blacklist": skipped_blacklist,
        "top_10_sugeridos": top_10,
    }


def run_dummy_scoring_test() -> None:
    old_request = SilverRequest(
        comico_id="1",
        nombre="Comica A",
        telefono="+34111111111",
        instagram="comica_a",
        genero="f",
        categoria_silver="priority",
        fechas_disponibles="2026-03-10",
        marca_temporal=datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc),
    )
    new_request = SilverRequest(
        comico_id="2",
        nombre="Comico B",
        telefono="+34222222222",
        instagram="comico_b",
        genero="m",
        categoria_silver="priority",
        fechas_disponibles="2026-03-10",
        marca_temporal=datetime(2026, 2, 2, 10, 0, tzinfo=timezone.utc),
    )

    score_a = compute_score("preferred", penalty_recent_acceptance=False, single_date=True)
    score_b = compute_score("preferred", penalty_recent_acceptance=False, single_date=True)

    ranking = sorted(
        [
            CandidateScore(
                nombre=old_request.nombre,
                telefono=old_request.telefono,
                instagram=old_request.instagram,
                genero=old_request.genero,
                comico_id="1",
                categoria="preferred",
                score_final=score_a,
                marca_temporal=old_request.marca_temporal,
                fecha_evento=date(2026, 3, 10),
                penalizado_por_recencia=False,
                bono_bala_unica=True,
            ),
            CandidateScore(
                nombre=new_request.nombre,
                telefono=new_request.telefono,
                instagram=new_request.instagram,
                genero=new_request.genero,
                comico_id="2",
                categoria="preferred",
                score_final=score_b,
                marca_temporal=new_request.marca_temporal,
                fecha_evento=date(2026, 3, 10),
                penalizado_por_recencia=False,
                bono_bala_unica=True,
            ),
        ],
        key=lambda item: (-item.score_final, item.marca_temporal),
    )

    assert ranking[0].telefono == old_request.telefono
    assert compute_score("gold", penalty_recent_acceptance=True, single_date=True) == -68
    assert compute_score("standard", penalty_recent_acceptance=False, single_date=False) == 0


if __name__ == "__main__":
    load_dotenv()
    configure_logging()

    if os.getenv("SCORING_ENGINE_DUMMY_TEST", "false").lower() in {"1", "true", "yes"}:
        run_dummy_scoring_test()
        print(json.dumps({"status": "dummy_test_ok"}, ensure_ascii=False))
    else:
        result = execute_scoring()
        print(json.dumps(result, ensure_ascii=False))
