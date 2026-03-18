"""Motor de scoring para proponer lineups semanales desde datos Silver/Gold.

v3: la configuración de scoring ya no es hardcodeada; se carga desde
silver.open_mics.config (JSONB) a través de ScoringConfig.

Cambios respecto a la versión anterior:
  · CATEGORY_BONUS / CATEGORY_ALIASES eliminados → ScoringConfig.compute_score()
  · compute_score() standalone eliminado
  · has_recent_acceptance_penalty() ahora recibe open_mic_id y ScoringConfig
    → la ventana de recencia es scoped por open_mic, no global
    → fuente de verdad: silver.lineup_slots WHERE status = 'confirmed'
  · fetch_silver_requests() filtra por open_mic_id
  · fetch_scoring_config() carga el JSONB desde silver.open_mics
  · persist_pending_score() escribe open_mic_id en gold.solicitudes
  · execute_scoring() acepta open_mic_id obligatorio
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from typing import Any
from uuid import uuid4

from pathlib import Path
from dotenv import load_dotenv

_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"

from backend.src.core.scoring_config import ScoringConfig, _SINGLE_DATE_BONUS

LOGGER = logging.getLogger("scoring_engine")
LOG_DIRECTORY = str(Path(__file__).resolve().parents[1] / "logs")
LOG_FILE_PATH  = str(Path(__file__).resolve().parents[1] / "logs" / "scoring_engine.log")

# Mapeo Silver → Gold para el campo categoria de gold.comicos.
# Silver usa 'general'; Gold usa 'standard' como nombre del enum.
_SILVER_TO_GOLD_CATEGORY: dict[str, str] = {
    "general":    "standard",
    "priority":   "priority",
    "gold":       "gold",
    "restricted": "restricted",
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

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
    solicitud_id: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class CandidateScore:
    nombre: str
    telefono: str
    instagram: str
    genero: str
    comico_id: str
    categoria: str
    open_mic_id: str
    score_final: int
    marca_temporal: datetime | None
    fecha_evento: date
    penalizado_por_recencia: bool
    puede_hoy: bool = False
    is_single_date: bool = False
    solicitud_id: str = ""
    score_breakdown: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Carga de configuración
# ---------------------------------------------------------------------------

def fetch_scoring_config(conn, open_mic_id: str) -> ScoringConfig:
    """Carga el JSONB config de silver.open_mics y construye un ScoringConfig.

    Si el open_mic no existe o su config está vacía, devuelve los valores
    por defecto (ScoringConfig.default) para no interrumpir el pipeline.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT config FROM silver.open_mics WHERE id = %s",
            (open_mic_id,),
        )
        row = cur.fetchone()

    raw: dict[str, Any] = row[0] if row and row[0] else {}
    return ScoringConfig.from_dict(open_mic_id, raw)


# ---------------------------------------------------------------------------
# Fetch Silver
# ---------------------------------------------------------------------------

def fetch_silver_requests(conn, open_mic_id: str) -> list[SilverRequest]:
    """Obtiene solicitudes Silver pendientes de scoring para un open_mic."""
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                s.id::text          AS solicitud_id,
                s.comico_id::text   AS comico_id,
                COALESCE(c.nombre, b.nombre_raw, '') AS nombre,
                c.telefono          AS telefono,
                COALESCE(c.instagram, '') AS instagram,
                COALESCE(c.genero, 'unknown') AS genero,
                c.categoria::text   AS categoria_silver,
                to_char(s.fecha_evento, 'YYYY-MM-DD') AS fechas_disponibles,
                s.created_at        AS marca_temporal,
                COALESCE(s.metadata, '{}') AS metadata
            FROM silver.solicitudes s
            JOIN silver.comicos c ON c.id = s.comico_id
            LEFT JOIN bronze.solicitudes b ON b.id = s.bronze_id
            WHERE s.open_mic_id = %s
              AND c.telefono IS NOT NULL
              AND s.status IN ('normalizado', 'scorado')
            ORDER BY s.created_at ASC NULLS LAST
            """,
            (open_mic_id,),
        )
        rows = cursor.fetchall()

    return [
        SilverRequest(
            solicitud_id=row[0],
            comico_id=row[1],
            nombre=row[2],
            telefono=row[3],
            instagram=row[4],
            genero=row[5],
            categoria_silver=row[6],
            fechas_disponibles=row[7],
            marca_temporal=row[8],
            metadata=row[9] if isinstance(row[9], dict) else {},
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Upsert Gold cómico
# ---------------------------------------------------------------------------

def _map_to_gold_category(categoria_silver: str | None) -> str:
    normalized = (categoria_silver or "general").strip().lower()
    return _SILVER_TO_GOLD_CATEGORY.get(normalized, "standard")


def upsert_comico(conn, request: SilverRequest) -> tuple[str, str]:
    """Sincroniza el perfil del cómico en gold.comicos.

    Devuelve (comico_id, categoria_silver_normalizada).
    La categoria devuelta usa los nombres Silver (standard/priority/gold/restricted)
    para que ScoringConfig pueda resolver la regla correcta.
    """
    categoria_gold = _map_to_gold_category(request.categoria_silver)
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO gold.comicos (id, telefono, instagram, nombre, genero, categoria)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET telefono  = EXCLUDED.telefono,
                instagram = EXCLUDED.instagram,
                nombre    = COALESCE(EXCLUDED.nombre, gold.comicos.nombre),
                genero    = EXCLUDED.genero,
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
        return request.comico_id, categoria_gold

    comico_id, cat_gold = upserted
    # Devolver en nomenclatura Silver (gold.comicos usa los mismos nombres excepto standard→general)
    return comico_id, cat_gold


# ---------------------------------------------------------------------------
# Penalización de recencia (scoped por open_mic_id)
# ---------------------------------------------------------------------------

def has_recent_acceptance_penalty(
    conn,
    comico_id: str,
    open_mic_id: str,
    config: ScoringConfig,
) -> bool:
    """True si el cómico actuó en las últimas N ediciones de ESTE open_mic.

    Fuente de verdad: silver.lineup_slots WHERE status = 'confirmed'.
    La ventana N viene de config.recency_last_n_editions.
    Si la penalización está desactivada en config, devuelve False directamente.
    """
    if not config.recency_penalty_enabled:
        return False

    with conn.cursor() as cursor:
        cursor.execute(
            """
            WITH ultimas_ediciones AS (
                SELECT DISTINCT fecha_evento
                FROM silver.lineup_slots
                WHERE open_mic_id = %s
                  AND status = 'confirmed'
                ORDER BY fecha_evento DESC
                LIMIT %s
            )
            SELECT EXISTS (
                SELECT 1
                FROM silver.lineup_slots ls
                JOIN silver.solicitudes   s ON s.id = ls.solicitud_id
                WHERE s.comico_id   = %s
                  AND ls.open_mic_id = %s
                  AND ls.status      = 'confirmed'
                  AND ls.fecha_evento IN (SELECT fecha_evento FROM ultimas_ediciones)
            )
            """,
            (open_mic_id, config.recency_last_n_editions, comico_id, open_mic_id),
        )
        result = cursor.fetchone()

    return bool(result[0]) if result else False


# ---------------------------------------------------------------------------
# Helpers de fecha
# ---------------------------------------------------------------------------

def has_single_date(fechas_disponibles: str) -> bool:
    """True si el cómico marcó exactamente UNA fecha disponible."""
    tokens = [t.strip() for t in (fechas_disponibles or "").split(",") if t.strip()]
    return len(tokens) == 1


def parse_primary_date(fechas_disponibles: str) -> date:
    tokens = [t.strip() for t in (fechas_disponibles or "").split(",") if t.strip()]
    for token in tokens:
        for pattern in ("%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y"):
            try:
                return datetime.strptime(token, pattern).date()
            except ValueError:
                continue
    return datetime.now(timezone.utc).date()



# ---------------------------------------------------------------------------
# Persistencia Gold
# ---------------------------------------------------------------------------

def persist_pending_score(conn, candidate: CandidateScore) -> None:
    """Escribe/actualiza el score en gold.solicitudes y gold.comicos."""
    solicitud_id = candidate.solicitud_id or str(uuid4())
    breakdown_json = json.dumps(candidate.score_breakdown) if candidate.score_breakdown else None
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO gold.solicitudes (
                id,
                comico_id,
                fecha_evento,
                open_mic_id,
                estado,
                score_aplicado,
                marca_temporal,
                puede_hoy,
                is_single_date,
                score_breakdown
            )
            VALUES (%s, %s, %s, %s, 'scorado', %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET comico_id        = EXCLUDED.comico_id,
                fecha_evento     = EXCLUDED.fecha_evento,
                open_mic_id      = EXCLUDED.open_mic_id,
                score_aplicado   = EXCLUDED.score_aplicado,
                marca_temporal   = EXCLUDED.marca_temporal,
                puede_hoy        = EXCLUDED.puede_hoy,
                is_single_date   = EXCLUDED.is_single_date,
                score_breakdown  = EXCLUDED.score_breakdown
            WHERE gold.solicitudes.estado IN ('pendiente', 'scorado')
            """,
            (
                solicitud_id,
                candidate.comico_id,
                candidate.fecha_evento,
                candidate.open_mic_id,
                float(candidate.score_final),
                candidate.marca_temporal,
                candidate.puede_hoy,
                candidate.is_single_date,
                breakdown_json,
            ),
        )
        cursor.execute(
            """
            UPDATE gold.solicitudes
            SET estado = 'scorado'
            WHERE id = %s
              AND estado IN ('pendiente', 'scorado')
            """,
            (solicitud_id,),
        )
        if candidate.solicitud_id:
            cursor.execute(
                """
                UPDATE silver.solicitudes
                SET status     = 'scorado',
                    updated_at = now()
                WHERE id = %s
                  AND status <> 'aprobado'
                """,
                (candidate.solicitud_id,),
            )
        cursor.execute(
            """
            UPDATE gold.comicos
            SET score_actual = %s,
                modified_at  = now()
            WHERE id = %s
            """,
            (float(candidate.score_final), candidate.comico_id),
        )


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def build_ranking(
    conn,
    requests: list[SilverRequest],
    config: ScoringConfig,
) -> tuple[list[CandidateScore], int]:
    """Puntúa y ordena candidatos según las reglas del ScoringConfig.

    Devuelve (ranking, n_descartados_por_restricción).
    Si gender_parity_enabled=True, alterna f/nb ↔ m; si no, orden puro por score.
    """
    scored: list[CandidateScore] = []
    skipped_restricted = 0

    for request in requests:
        try:
            comico_id, categoria_gold = upsert_comico(conn, request)

            # Resolver la categoría efectiva para scoring:
            # gold.comicos puede devolver 'standard' donde silver tenía 'general'
            # ScoringConfig entiende ambos nombres (gold y silver usan standard)
            if config.is_restricted(categoria_gold):
                skipped_restricted += 1
                LOGGER.info("Descartado por restricción: %s", request.instagram)
                continue

            penalty        = has_recent_acceptance_penalty(conn, comico_id, config.open_mic_id, config)
            single_date    = has_single_date(request.fechas_disponibles)
            score          = config.compute_score(categoria_gold, penalty, is_single_date=single_date)

            if score is None:
                # compute_score devuelve None si la categoría es restringida
                skipped_restricted += 1
                continue

            custom_bonus = config.apply_custom_rules(request.metadata)
            score += custom_bonus

            # Build score breakdown for audit trail
            rule = config.category_rule(categoria_gold)
            breakdown: dict[str, Any] = {
                "base_score": rule.base_score or 0,
                "categoria": categoria_gold,
            }
            if config.recency_penalty_enabled and penalty:
                breakdown["recency_penalty"] = -config.recency_penalty_points
            if config.single_date_priority_enabled and single_date:
                breakdown["single_date_bonus"] = _SINGLE_DATE_BONUS
            if custom_bonus != 0:
                breakdown["custom_rules_bonus"] = custom_bonus
            breakdown["total"] = score

            backup_val = str(request.metadata.get('backup', '')).strip().lower()
            scored.append(
                CandidateScore(
                    nombre=request.nombre,
                    telefono=request.telefono,
                    instagram=request.instagram,
                    genero=request.genero,
                    comico_id=comico_id,
                    categoria=categoria_gold,
                    open_mic_id=config.open_mic_id,
                    score_final=score,
                    marca_temporal=request.marca_temporal,
                    fecha_evento=parse_primary_date(request.fechas_disponibles),
                    penalizado_por_recencia=penalty,
                    puede_hoy=backup_val in ('sí', 'si', 'yes', 'true', '1'),
                    is_single_date=single_date,
                    solicitud_id=request.solicitud_id,
                    score_breakdown=breakdown,
                )
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception(
                "Error procesando solicitud instagram=%s: %s",
                request.instagram,
                exc,
            )

    def sort_key(c: CandidateScore):
        return (-c.score_final, c.marca_temporal or datetime.max.replace(tzinfo=timezone.utc))

    # Deduplicar por comico_id (quedarse con el de mayor score)
    seen: set[str] = set()

    if not config.gender_parity_enabled:
        # Sin paridad: orden puro por score
        ranked: list[CandidateScore] = []
        for c in sorted(scored, key=sort_key):
            if c.comico_id not in seen:
                ranked.append(c); seen.add(c.comico_id)
        return ranked, skipped_restricted

    # Con paridad: alternancia f/nb/unknown ↔ m
    _F_NB = {"f", "nb", "unknown"}
    f_nb = sorted([c for c in scored if c.genero in _F_NB],            key=sort_key)
    m    = sorted([c for c in scored if c.genero == "m"],              key=sort_key)
    unk  = sorted([c for c in scored if c.genero not in (_F_NB | {"m"})], key=sort_key)

    balanced: list[CandidateScore] = []
    idx_f = idx_m = 0

    while idx_f < len(f_nb) or idx_m < len(m):
        if idx_f < len(f_nb):
            c = f_nb[idx_f]; idx_f += 1
            if c.comico_id not in seen:
                balanced.append(c); seen.add(c.comico_id)
        if idx_m < len(m):
            c = m[idx_m]; idx_m += 1
            if c.comico_id not in seen:
                balanced.append(c); seen.add(c.comico_id)

    for c in unk:
        if c.comico_id not in seen:
            balanced.append(c); seen.add(c.comico_id)

    return balanced, skipped_restricted


# ---------------------------------------------------------------------------
# Punto de entrada principal
# ---------------------------------------------------------------------------

def execute_scoring(open_mic_id: str) -> dict[str, Any]:
    """Ejecuta el ciclo completo de scoring para un open_mic concreto.

    1. Carga ScoringConfig desde silver.open_mics.config
    2. Obtiene solicitudes Silver pendientes del open_mic
    3. Puntúa y rankea candidatos
    4. Persiste scores en Gold

    Args:
        open_mic_id: UUID del open_mic a procesar.
    """
    with db_connection() as conn:
        config   = fetch_scoring_config(conn, open_mic_id)
        requests = fetch_silver_requests(conn, open_mic_id)
        ranking, skipped = build_ranking(conn, requests, config)

        for candidate in ranking:
            persist_pending_score(conn, candidate)

    top_n = config.available_slots
    return {
        "status": "ok",
        "open_mic_id": open_mic_id,
        "filas_procesadas": len(requests),
        "filas_insertadas_gold": len(ranking),
        "filas_descartadas_restriccion": skipped,
        "top_sugeridos": [
            {
                "nombre":           c.nombre,
                "instagram":        c.instagram,
                "genero":           c.genero,
                "categoria":        c.categoria,
                "score_final":      c.score_final,
                "penalizado":       c.penalizado_por_recencia,
                "is_single_date":   c.is_single_date,
                "marca_temporal":   c.marca_temporal.isoformat() if c.marca_temporal else None,
                "score_breakdown":  c.score_breakdown,
            }
            for c in ranking[:top_n]
        ],
    }


if __name__ == "__main__":
    import sys

    load_dotenv(dotenv_path=_ROOT_ENV)
    configure_logging()

    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: scoring_engine.py <open_mic_id>"}, ensure_ascii=False))
        sys.exit(1)

    result = execute_scoring(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False))
