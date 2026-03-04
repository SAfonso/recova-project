from __future__ import annotations

from datetime import date
from uuid import UUID

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
    assert "parsing_fechas" in descartes[0]["motivo"]
    assert len(errors) == 1
    assert errors[0][0] == bronze.id
    assert errors[0][1] == "raw_data_extra"
    assert errors[0][3] == "parsing_fechas"
    assert any("ROLLBACK TO SAVEPOINT" in query for query, _ in conn.executed)


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
