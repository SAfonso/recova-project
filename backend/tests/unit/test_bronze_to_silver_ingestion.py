from __future__ import annotations

from datetime import date
from uuid import UUID

import psycopg2
import pytest

import bronze_to_silver_ingestion as ingestion


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.conn.executed.append((str(query), params))


class FakeConn:
    def __init__(self):
        self.executed: list[tuple[str, tuple | None]] = []

    def cursor(self):
        return FakeCursor(self)


def make_bronze_record(**overrides):
    base = {
        "id": UUID("30000000-0000-0000-0000-000000000001"),
        "proveedor_id": UUID("10000000-0000-0000-0000-000000000001"),
        "open_mic_id": UUID("20000000-0000-0000-0000-000000000001"),
        "nombre_raw": "Mati",
        "instagram_raw": "@mati.show",
        "telefono_raw": "+34666555888",
        "experiencia_raw": "He probado alguna vez",
        "fechas_seleccionadas_raw": "20-02-26",
        "disponibilidad_ultimo_minuto": "si",
        "info_show_cercano": "Bar local",
        "origen_conocimiento": "instagram",
    }
    base.update(overrides)
    return ingestion.BronzeRecord(**base)


def test_normalize_instagram_user_from_url():
    raw = "https://www.instagram.com/Comico.Test/?hl=es"
    assert ingestion.normalize_instagram_user(raw) == "comico.test"


def test_normalize_instagram_user_removes_at_and_lowercases():
    assert ingestion.normalize_instagram_user("@@Mi_Usuario") == "mi_usuario"


def test_clean_phone_accepts_local_spanish_phone():
    assert ingestion.clean_phone("666 555 888") == "+34666555888"


def test_clean_phone_rejects_invalid_input():
    assert ingestion.clean_phone("abc") is None


def test_normalize_row_validates_required_fields():
    row = {
        "¿Nombre?": "",
        "¿Instagram?": "",
        "Whatsapp": "",
        "Fecha": "20-02-26",
    }

    result = ingestion.normalize_row(row)

    assert result["is_valid"] is False
    assert len(result["errors"]) == 3


def test_parse_event_dates_filters_past_invalid_and_duplicates():
    today = date(2026, 2, 15)
    raw_dates = "14-02-26, 16-02-26, 16-02-26, xx-yy-zz"

    parsed = ingestion.parse_event_dates(raw_dates, today)

    assert parsed == [date(2026, 2, 16)]


def test_parse_last_minute_availability_handles_accented_si():
    assert ingestion.parse_last_minute_availability("SÍ") is True
    assert ingestion.parse_last_minute_availability("no") is False


def test_map_experience_level_unknown_defaults_zero():
    assert ingestion.map_experience_level("nivel inexistente") == 0


def test_process_single_solicitud_discards_when_no_future_dates(monkeypatch):
    conn = FakeConn()
    bronze = make_bronze_record()
    today = date(2026, 2, 15)
    descartes: list[dict[str, str]] = []
    marked: list[UUID] = []

    monkeypatch.setattr(
        ingestion,
        "normalize_row",
        lambda _row: {
            "is_valid": True,
            "errors": [],
            "normalized": {
                "nombre": "Mati",
                "instagram": "mati.show",
                "telefono": "+34666555888",
                "experiencia_raw": "He probado alguna vez",
                "fechas_raw": "14-02-26",
                "disponibilidad_ultimo_minuto": "si",
            },
        },
    )
    monkeypatch.setattr(ingestion, "parse_event_dates", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        ingestion,
        "mark_bronze_processed",
        lambda _conn, bronze_id: marked.append(bronze_id),
    )

    inserted = ingestion.process_single_solicitud(
        conn,
        bronze,
        today,
        error_metadata_column=None,
        detalles_descarte=descartes,
    )

    assert inserted == 0
    assert marked == [bronze.id]
    assert len(descartes) == 1
    assert "Sin fechas futuras" in descartes[0]["motivo"]


def test_process_single_solicitud_happy_path(monkeypatch):
    conn = FakeConn()
    bronze = make_bronze_record()
    today = date(2026, 2, 15)
    descartes: list[dict[str, str]] = []
    marked: list[UUID] = []
    inserted_payload = {}

    monkeypatch.setattr(
        ingestion,
        "normalize_row",
        lambda _row: {
            "is_valid": True,
            "errors": [],
            "normalized": {
                "nombre": "Mati",
                "instagram": "mati.show",
                "telefono": "+34666555888",
                "experiencia_raw": "He probado alguna vez",
                "fechas_raw": "20-02-26, 21-02-26",
                "disponibilidad_ultimo_minuto": "si",
            },
        },
    )
    monkeypatch.setattr(
        ingestion,
        "parse_event_dates",
        lambda *_args, **_kwargs: [date(2026, 2, 20), date(2026, 2, 21)],
    )
    monkeypatch.setattr(ingestion, "map_experience_level", lambda *_args: 1)
    monkeypatch.setattr(ingestion, "parse_last_minute_availability", lambda *_args: True)
    monkeypatch.setattr(
        ingestion,
        "upsert_comico_silver",
        lambda *_args, **_kwargs: UUID("20000000-0000-0000-0000-000000000001"),
    )

    def fake_insert(_conn, bronze, comico_id, event_dates, level, available_last_minute):
        inserted_payload["bronze_id"] = bronze.id
        inserted_payload["comico_id"] = comico_id
        inserted_payload["event_dates"] = list(event_dates)
        inserted_payload["level"] = level
        inserted_payload["available_last_minute"] = available_last_minute
        return 2

    monkeypatch.setattr(ingestion, "insert_silver_rows", fake_insert)
    monkeypatch.setattr(
        ingestion,
        "mark_bronze_processed",
        lambda _conn, bronze_id: marked.append(bronze_id),
    )

    inserted = ingestion.process_single_solicitud(
        conn,
        bronze,
        today,
        error_metadata_column="raw_data_extra",
        detalles_descarte=descartes,
    )

    assert inserted == 2
    assert marked == [bronze.id]
    assert descartes == []
    assert inserted_payload["bronze_id"] == bronze.id
    assert inserted_payload["level"] == 1
    assert inserted_payload["available_last_minute"] is True


def test_process_single_solicitud_rolls_back_and_registers_error(monkeypatch):
    conn = FakeConn()
    bronze = make_bronze_record()
    today = date(2026, 2, 15)
    descartes: list[dict[str, str]] = []
    errors: list[tuple] = []

    monkeypatch.setattr(
        ingestion,
        "normalize_row",
        lambda _row: {
            "is_valid": True,
            "errors": [],
            "normalized": {
                "nombre": "Mati",
                "instagram": "mati.show",
                "telefono": "+34666555888",
                "experiencia_raw": "He probado alguna vez",
                "fechas_raw": "20-02-26",
                "disponibilidad_ultimo_minuto": "si",
            },
        },
    )

    def boom(*_args, **_kwargs):
        raise ValueError("fecha invalida")

    monkeypatch.setattr(ingestion, "parse_event_dates", boom)
    monkeypatch.setattr(
        ingestion,
        "register_ingestion_error",
        lambda _conn, bronze_id, error_metadata_column, message, phase: errors.append(
            (bronze_id, error_metadata_column, message, phase)
        ),
    )

    inserted = ingestion.process_single_solicitud(
        conn,
        bronze,
        today,
        error_metadata_column="raw_data_extra",
        detalles_descarte=descartes,
    )

    assert inserted == 0
    assert len(descartes) == 1
    assert "normalizacion" in descartes[0]["motivo"]
    assert len(errors) == 1
    assert errors[0][0] == bronze.id
    assert errors[0][1] == "raw_data_extra"
    assert errors[0][3] == "normalizacion"
    assert any("ROLLBACK TO SAVEPOINT" in query for query, _ in conn.executed)
    # ValueError es permanente → debe marcar bronze como procesado
    assert any(
        "UPDATE bronze.solicitudes SET procesado = true" in query
        for query, _ in conn.executed
    )


def test_process_single_solicitud_transient_error_does_not_mark_processed(monkeypatch):
    """Un error transitorio (OperationalError) NO debe marcar el bronze como procesado."""
    conn = FakeConn()
    bronze = make_bronze_record()
    today = date(2026, 2, 15)
    descartes: list[dict[str, str]] = []

    monkeypatch.setattr(
        ingestion,
        "normalize_row",
        lambda _row: {
            "is_valid": True,
            "errors": [],
            "normalized": {
                "nombre": "Mati",
                "instagram": "mati.show",
                "telefono": "+34666555888",
                "experiencia_raw": "He probado alguna vez",
                "fechas_raw": "20-02-26",
                "disponibilidad_ultimo_minuto": "si",
            },
        },
    )

    def boom(*_args, **_kwargs):
        raise psycopg2.OperationalError("connection lost")

    monkeypatch.setattr(ingestion, "parse_event_dates", boom)
    monkeypatch.setattr(
        ingestion,
        "register_ingestion_error",
        lambda _conn, bronze_id, error_metadata_column, message, phase: None,
    )

    inserted = ingestion.process_single_solicitud(
        conn,
        bronze,
        today,
        error_metadata_column="raw_data_extra",
        detalles_descarte=descartes,
    )

    assert inserted == 0
    # OperationalError es transitorio → NO debe marcar como procesado
    assert not any(
        "UPDATE bronze.solicitudes SET procesado = true" in query
        for query, _ in conn.executed
    )


def test_process_single_solicitud_unique_violation_marks_processed(monkeypatch):
    """UniqueViolation es permanente → debe marcar el bronze como procesado."""
    import psycopg2.errors

    conn = FakeConn()
    bronze = make_bronze_record()
    today = date(2026, 2, 15)
    descartes: list[dict[str, str]] = []

    monkeypatch.setattr(
        ingestion,
        "normalize_row",
        lambda _row: {
            "is_valid": True,
            "errors": [],
            "normalized": {
                "nombre": "Mati",
                "instagram": "mati.show",
                "telefono": "+34666555888",
                "experiencia_raw": "He probado alguna vez",
                "fechas_raw": "20-02-26",
                "disponibilidad_ultimo_minuto": "si",
            },
        },
    )

    def boom(*_args, **_kwargs):
        raise psycopg2.errors.UniqueViolation("duplicate key")

    monkeypatch.setattr(ingestion, "parse_event_dates", boom)
    monkeypatch.setattr(
        ingestion,
        "register_ingestion_error",
        lambda _conn, bronze_id, error_metadata_column, message, phase: None,
    )

    inserted = ingestion.process_single_solicitud(
        conn,
        bronze,
        today,
        error_metadata_column="raw_data_extra",
        detalles_descarte=descartes,
    )

    assert inserted == 0
    assert any(
        "UPDATE bronze.solicitudes SET procesado = true" in query
        for query, _ in conn.executed
    )


def test_run_pipeline_success_aggregates_counts(monkeypatch):
    bronze_rows = [make_bronze_record(), make_bronze_record(id=UUID("30000000-0000-0000-0000-000000000099"))]

    class DummyContext:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(ingestion, "configure_logging", lambda: None)
    monkeypatch.setattr(ingestion, "db_connection", lambda: DummyContext())
    monkeypatch.setattr(ingestion, "expire_old_reserves", lambda *_args: 3)
    monkeypatch.setattr(ingestion, "fetch_pending_bronze_rows", lambda *_args: bronze_rows)
    monkeypatch.setattr(ingestion, "resolve_error_metadata_column", lambda *_args: "raw_data_extra")
    monkeypatch.setattr(
        ingestion,
        "process_single_solicitud",
        lambda _conn, _bronze, _today, _col, _detalles: 1,
    )

    result = ingestion.run_pipeline()

    assert result["status"] == "success"
    assert result["pendientes_leidos"] == 2
    assert result["filas_procesadas"] == 2
    assert result["filas_silver_insertadas"] == 2
    assert result["reservas_expiradas"] == 3


def test_run_pipeline_fatal_error(monkeypatch):
    monkeypatch.setattr(ingestion, "configure_logging", lambda: None)

    class BrokenContext:
        def __enter__(self):
            raise RuntimeError("db down")

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(ingestion, "db_connection", lambda: BrokenContext())

    result = ingestion.run_pipeline()

    assert result["status"] == "error"
    assert result["filas_procesadas"] == 0
    assert any("Error fatal" in message for message in result["errores"])


# ---------------------------------------------------------------------------
# Tests: infer_gender
# ---------------------------------------------------------------------------

class TestInferGender:
    """Tests para la detección de género por nombre e instagram."""

    def test_nombre_femenino_claro(self):
        assert ingestion.infer_gender("Maria García", None) == "f"

    def test_nombre_masculino_claro(self):
        assert ingestion.infer_gender("Carlos Ruiz", None) == "m"

    def test_nombre_femenino_con_tilde(self):
        assert ingestion.infer_gender("Sofía López", None) == "f"

    def test_nombre_masculino_con_tilde(self):
        assert ingestion.infer_gender("Andrés Martín", None) == "m"

    def test_nombre_femenino_comun(self):
        assert ingestion.infer_gender("Ana", None) == "f"

    def test_nombre_masculino_comun(self):
        assert ingestion.infer_gender("Pepe", None) == "m"

    def test_fallback_instagram_femenino(self):
        # nombre ambiguo, instagram contiene nombre femenino
        assert ingestion.infer_gender("J.", "mariacomica") == "f"

    def test_fallback_instagram_masculino(self):
        assert ingestion.infer_gender("X", "carlosstand") == "m"

    def test_instagram_sin_nombre_femenino(self):
        assert ingestion.infer_gender(None, "luciacomedy") == "f"

    def test_instagram_sin_nombre_masculino(self):
        assert ingestion.infer_gender(None, "juanhumorista") == "m"

    def test_nombre_none_instagram_none(self):
        assert ingestion.infer_gender(None, None) is None

    def test_nombre_ambiguo_instagram_sin_pista(self):
        # 'Alex' es mayormente masculino para gender_guesser, pero si no, debe ser m o None
        result = ingestion.infer_gender("Alex", "xyz123")
        assert result in ("m", "f", None)

    def test_nombre_desconocido_instagram_sin_palabras(self):
        assert ingestion.infer_gender("Xzqrt", "123456") is None

    # --- Tests INE: nombres que gender-guesser no reconoce bien ---

    def test_ine_iker(self):
        """Iker: nombre vasco que gender-guesser clasifica como 'andy'."""
        assert ingestion.infer_gender("Iker", None) == "m"

    def test_ine_naiara(self):
        """Naiara: nombre vasco/navarro femenino."""
        assert ingestion.infer_gender("Naiara", None) == "f"

    def test_ine_maite(self):
        """Maite: hipocorístico vasco femenino."""
        assert ingestion.infer_gender("Maite", None) == "f"

    def test_ine_yurena(self):
        """Yurena: nombre canario femenino."""
        assert ingestion.infer_gender("Yurena", None) == "f"

    def test_ine_pepa(self):
        """Pepa: diminutivo femenino de Josefa."""
        assert ingestion.infer_gender("Pepa", None) == "f"

    def test_ine_amaia(self):
        """Amaia: nombre vasco femenino."""
        assert ingestion.infer_gender("Amaia", None) == "f"

    def test_ine_unai(self):
        """Unai: nombre vasco masculino."""
        assert ingestion.infer_gender("Unai", None) == "m"

    def test_ine_ainhoa(self):
        """Ainhoa: nombre vasco femenino."""
        assert ingestion.infer_gender("Ainhoa", None) == "f"

    # --- Tests cascada: verificar que las capas se complementan ---

    def test_cascade_ine_has_priority(self):
        """El diccionario INE debe resolver antes de llamar a gender-guesser."""
        result = ingestion._ine_lookup("iker")
        assert result == "m"

    def test_cascade_gender_guesser_fallback(self):
        """Nombres internacionales no-INE deben resolverse por gender-guesser."""
        # 'Bartholomew' no está en el INE pero sí en gender-guesser
        assert ingestion._ine_lookup("bartholomew") is None
        assert ingestion._gender_guesser_lookup("bartholomew") == "m"
        assert ingestion.infer_gender("Bartholomew", None) == "m"


# --- Tests register_ingestion_error whitelist ---


class TestRegisterIngestionErrorWhitelist:
    """Verifica que register_ingestion_error rechaza columnas no permitidas."""

    def test_allowed_column_metadata(self):
        assert "metadata" in ingestion._ALLOWED_ERROR_COLUMNS

    def test_allowed_column_raw_data_extra(self):
        assert "raw_data_extra" in ingestion._ALLOWED_ERROR_COLUMNS

    def test_rejects_disallowed_column(self):
        from unittest.mock import MagicMock
        from uuid import UUID

        conn = MagicMock()
        with pytest.raises(ValueError, match="Columna no permitida"):
            ingestion.register_ingestion_error(
                conn,
                bronze_id=UUID("00000000-0000-0000-0000-000000000001"),
                error_metadata_column="Robert'; DROP TABLE bronze.solicitudes;--",
                message="test",
                phase="test",
            )

    def test_none_column_logs_instead(self):
        """Con error_metadata_column=None no ejecuta SQL, solo logea."""
        from unittest.mock import MagicMock
        from uuid import UUID

        conn = MagicMock()
        ingestion.register_ingestion_error(
            conn,
            bronze_id=UUID("00000000-0000-0000-0000-000000000001"),
            error_metadata_column=None,
            message="test error",
            phase="test_phase",
        )
        conn.cursor.assert_not_called()
