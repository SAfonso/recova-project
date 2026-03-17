"""Test E2E smoke — Happy path completo del flujo principal.

Simula el ciclo:
  1. Form submission → INSERT bronze.solicitudes
  2. run_pipeline() → normalización + INSERT silver.solicitudes + silver.comicos
  3. execute_scoring() → scoring + INSERT gold.solicitudes + gold.comicos
  4. Verificación: los datos fluyen correctamente de Bronze a Gold

Todas las capas de BD están mockeadas a nivel de psycopg2 cursor.
El test NO toca red; valida que la lógica de negocio encadena correctamente.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch
from uuid import uuid4

import pytest

os.environ.setdefault("WEBHOOK_API_KEY", "test-key")
os.environ.setdefault("SUPABASE_URL", "http://fake-supabase")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-service-key")
os.environ.setdefault("DATABASE_URL", "postgresql://fake:fake@localhost/fake")

from backend.src.triggers.webhook_listener import app  # noqa: E402

API_KEY = "test-key"
AUTH = {"X-API-KEY": API_KEY, "Content-Type": "application/json"}

OPEN_MIC_ID = str(uuid4())
PROVEEDOR_ID = str(uuid4())
COMICO_ID = str(uuid4())
SOLICITUD_BRONZE_ID = str(uuid4())
SOLICITUD_SILVER_ID = str(uuid4())

# Fecha futura para que las fechas sean válidas
NEXT_FRIDAY = date.today() + timedelta(days=(4 - date.today().weekday() + 7) % 7 or 7)
FECHA_STR = NEXT_FRIDAY.strftime("%d-%m-%y")


# ---------------------------------------------------------------------------
# Helpers — Mock Supabase (para el endpoint /api/form-submission)
# ---------------------------------------------------------------------------

def _make_sb_mock():
    """Mock de Supabase client para el endpoint de form-submission."""
    sb = MagicMock()

    # silver.open_mics → devuelve proveedor_id
    silver_chain = MagicMock()
    silver_chain.from_.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"proveedor_id": PROVEEDOR_ID}]
    )
    # bronze insert
    bronze_chain = MagicMock()
    bronze_chain.from_.return_value.insert.return_value.execute.return_value = MagicMock(data=[{}])

    def schema_router(name):
        if name == "silver":
            return silver_chain
        if name == "bronze":
            return bronze_chain
        return MagicMock()

    sb.schema = MagicMock(side_effect=schema_router)
    return sb


# ---------------------------------------------------------------------------
# Helpers — Mock psycopg2 cursor (para run_pipeline + execute_scoring)
# ---------------------------------------------------------------------------

def _build_cursor_mock():
    """Cursor que simula las queries de Bronze→Silver→Gold."""
    cursor = MagicMock()
    cursor.rowcount = 0
    cursor.fetchone.return_value = None
    cursor.fetchall.return_value = []
    call_count = {"execute": 0}

    # Estado mutable que las queries van actualizando
    state = {
        "bronze_fetched": False,
        "silver_inserted": False,
        "gold_scored": False,
    }

    def execute_side_effect(sql, params=None):
        sql_lower = sql.strip().lower() if isinstance(sql, str) else ""
        call_count["execute"] += 1

        # --- INGESTION: Bronze → Silver ---

        # fetch_pending_bronze_rows
        if "from bronze.solicitudes" in sql_lower and "procesado = false" in sql_lower:
            state["bronze_fetched"] = True
            cursor.fetchall.return_value = [
                (
                    SOLICITUD_BRONZE_ID,    # id
                    PROVEEDOR_ID,            # proveedor_id
                    OPEN_MIC_ID,             # open_mic_id
                    "María García",          # nombre_raw
                    "@mariacomica",          # instagram_raw
                    "+34612345678",           # telefono_raw
                    "Entre 1 y 5",           # experiencia_raw
                    FECHA_STR,               # fechas_seleccionadas_raw
                    "Sí",                    # disponibilidad_ultimo_minuto
                    None,                    # info_show_cercano
                    "Instagram",             # origen_conocimiento
                )
            ]

        # resolve_error_metadata_column
        elif "information_schema.columns" in sql_lower:
            cursor.fetchone.return_value = ("metadata",)

        # expire_old_reserves
        elif "update silver.solicitudes" in sql_lower and "expirado" in sql_lower:
            cursor.rowcount = 0

        # upsert_comico_silver → RETURNING id
        elif "insert into silver.comicos" in sql_lower:
            cursor.fetchone.return_value = (COMICO_ID,)

        # insert_silver_rows (check duplicates)
        elif "select 1 from silver.solicitudes" in sql_lower:
            cursor.fetchone.return_value = None  # no duplicate

        # insert INTO silver.solicitudes (v3 with open_mic_id or legacy)
        elif "insert into silver.solicitudes" in sql_lower and "values" in sql_lower:
            state["silver_inserted"] = True
            cursor.rowcount = 1

        # mark_bronze_processed
        elif "update bronze.solicitudes" in sql_lower and "procesado" in sql_lower:
            pass

        # --- SCORING: Silver → Gold ---

        # fetch_scoring_config (psycopg2 returns JSONB as dict)
        elif "select config from silver.open_mics" in sql_lower:
            cursor.fetchone.return_value = (
                {"scoring_type": "basic"},
            )

        # fetch_silver_requests (column order: solicitud_id, comico_id, nombre,
        #   telefono, instagram, genero, categoria, fechas, marca_temporal, metadata)
        elif "from silver.solicitudes" in sql_lower and "silver.comicos" in sql_lower:
            cursor.fetchall.return_value = [
                (
                    SOLICITUD_SILVER_ID,     # solicitud_id
                    COMICO_ID,               # comico_id
                    "María García",          # nombre
                    "+34612345678",           # telefono
                    "mariacomica",           # instagram
                    "f",                     # genero
                    "general",               # categoria_silver
                    FECHA_STR,               # fechas_disponibles
                    datetime.now(timezone.utc),  # marca_temporal
                    {},                      # metadata
                )
            ]

        # upsert_comico (gold)
        elif "insert into gold.comicos" in sql_lower:
            cursor.fetchone.return_value = (COMICO_ID, "standard")

        # has_recent_acceptance_penalty → no penalty
        elif "silver.lineup_slots" in sql_lower and "ultimas_ediciones" in sql_lower:
            cursor.fetchone.return_value = (False,)

        # persist_pending_score: INSERT gold.solicitudes
        elif "insert into gold.solicitudes" in sql_lower:
            state["gold_scored"] = True

        # persist_pending_score: UPDATE gold.solicitudes estado
        elif "update gold.solicitudes" in sql_lower:
            pass

        # persist_pending_score: UPDATE silver.solicitudes status=scorado
        elif "update silver.solicitudes" in sql_lower and "scorado" in sql_lower:
            pass

        # persist_pending_score: UPDATE gold.comicos score_actual
        elif "update gold.comicos" in sql_lower:
            pass

        # SAVEPOINT / ROLLBACK TO SAVEPOINT
        elif "savepoint" in sql_lower:
            pass

    cursor.execute = MagicMock(side_effect=execute_side_effect)
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)

    return cursor, state


def _build_conn_mock(cursor):
    """Connection mock que devuelve siempre el mismo cursor."""
    conn = MagicMock()
    conn.cursor.return_value = cursor
    conn.autocommit = False
    return conn


# ---------------------------------------------------------------------------
# TEST E2E
# ---------------------------------------------------------------------------

class TestE2EHappyPath:
    """Flujo completo: form submission → ingesta → scoring → gold."""

    def test_full_pipeline_form_to_gold(self):
        """
        Simula el happy path completo:
          1. POST /api/form-submission → inserta en bronze
          2. run_pipeline() → normaliza y crea silver.solicitudes + silver.comicos
          3. execute_scoring() → puntúa y persiste en gold.solicitudes + gold.comicos
        """
        sb = _make_sb_mock()
        cursor, state = _build_cursor_mock()
        conn = _build_conn_mock(cursor)

        # --- FASE 1: Form submission (HTTP endpoint) ---
        with patch("backend.src.triggers.blueprints.ingestion._sb_client", return_value=sb), \
             patch("backend.src.triggers.blueprints.ingestion.run_ingestion_async"):
            with app.test_client() as client:
                resp = client.post("/api/form-submission", json={
                    "open_mic_id": OPEN_MIC_ID,
                    "Nombre artístico": "María García",
                    "Instagram (sin @)": "@mariacomica",
                    "WhatsApp": "+34612345678",
                    "¿Cuántas veces has actuado en un open mic?": "Entre 1 y 5",
                    "¿Qué fechas te vienen bien?": FECHA_STR,
                    "¿Estarías disponible si nos falla alguien de última hora?": "Sí",
                    "¿Cómo nos conociste?": "Instagram",
                }, headers=AUTH)

        assert resp.status_code == 200, f"Form submission failed: {resp.get_json()}"
        assert resp.get_json()["status"] == "ok"

        # Verificar que se insertó en bronze
        sb.schema.assert_any_call("bronze")
        bronze_insert = sb.schema("bronze").from_("solicitudes").insert
        bronze_insert.assert_called_once()
        insert_data = bronze_insert.call_args[0][0]
        assert insert_data["nombre_raw"] == "María García"
        assert insert_data["open_mic_id"] == OPEN_MIC_ID
        assert insert_data["proveedor_id"] == PROVEEDOR_ID

        # --- FASE 2: Ingesta Bronze → Silver ---
        from backend.src.bronze_to_silver_ingestion import run_pipeline

        with patch("backend.src.bronze_to_silver_ingestion.db_connection") as mock_db:
            mock_db.return_value.__enter__ = MagicMock(return_value=conn)
            mock_db.return_value.__exit__ = MagicMock(return_value=False)

            result = run_pipeline()

        assert result["status"] == "success", f"Ingestion failed: {result}"
        assert result["pendientes_leidos"] == 1
        assert result["filas_procesadas"] == 1
        assert result["filas_silver_insertadas"] >= 1
        assert state["bronze_fetched"], "Bronze rows were not fetched"
        assert state["silver_inserted"], "Silver row was not inserted"

        # --- FASE 3: Scoring Silver → Gold ---
        from backend.src.scoring_engine import execute_scoring

        # Reset cursor state for scoring phase
        cursor_scoring, state_scoring = _build_cursor_mock()
        conn_scoring = _build_conn_mock(cursor_scoring)

        with patch("backend.src.scoring_engine.db_connection") as mock_db:
            mock_db.return_value.__enter__ = MagicMock(return_value=conn_scoring)
            mock_db.return_value.__exit__ = MagicMock(return_value=False)

            result = execute_scoring(OPEN_MIC_ID)

        assert result["status"] == "ok", f"Scoring failed: {result}"
        assert result["open_mic_id"] == OPEN_MIC_ID
        assert result["filas_procesadas"] == 1
        assert result["filas_insertadas_gold"] == 1
        assert state_scoring["gold_scored"], "Gold score was not persisted"

        # Verificar top sugerido
        top = result["top_sugeridos"]
        assert len(top) == 1
        assert top[0]["nombre"] == "María García"
        assert top[0]["instagram"] == "mariacomica"
        assert top[0]["genero"] == "f"
        assert top[0]["score_final"] > 0
        assert top[0]["penalizado"] is False

    def test_full_pipeline_gender_detected_correctly(self):
        """Verifica que la inferencia de género funciona en el flujo e2e.

        María → 'f' vía INE (no depende de gender-guesser).
        """
        from backend.src.bronze_to_silver_ingestion import infer_gender

        # La cascada INE debe resolver María como femenino
        assert infer_gender("María García", "@mariacomica") == "f"

    def test_full_pipeline_scoring_produces_positive_score(self):
        """Verifica que un candidato estándar sin penalización recibe score > 0."""
        from backend.src.core.scoring_config import ScoringConfig

        config = ScoringConfig.default(OPEN_MIC_ID)
        score = config.compute_score("standard", has_recency_penalty=False, is_single_date=False)
        assert score is not None
        assert score > 0

    def test_full_pipeline_restricted_category_excluded(self):
        """Verifica que categoría 'restricted' recibe score=None (excluida)."""
        from backend.src.core.scoring_config import ScoringConfig

        config = ScoringConfig.default(OPEN_MIC_ID)
        score = config.compute_score("restricted", has_recency_penalty=False, is_single_date=False)
        assert score is None
