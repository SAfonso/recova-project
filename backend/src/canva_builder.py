"""Generador de cartelería en Canva mediante autofill API."""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
import unicodedata
from dataclasses import dataclass
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from canva_auth_utils import (
    CanvaAuthError,
    exchange_code_for_tokens,
    get_cached_access_token,
    refresh_access_token,
)

CANVA_AUTOFILL_URL = "https://api.canva.com/rest/v1/autofills"
AUTOFILL_POLL_INTERVAL_SECONDS = 5
AUTOFILL_MAX_POLL_ATTEMPTS = 60
AUTOFILL_UNKNOWN_STATUS_MAX_ITERATIONS = 3
BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_LOG_DIRECTORY = BACKEND_DIR / "logs"
DEFAULT_LOG_FILE_PATH = DEFAULT_LOG_DIRECTORY / "canva_builder.log"
LOGGER = logging.getLogger("canva_builder")


@dataclass(frozen=True)
class ComicEntry:
    nombre: str
    instagram: str


@dataclass(frozen=True)
class PosterRequest:
    fecha: str
    comicos: list[ComicEntry]


def configure_logging() -> None:
    log_directory = Path(
        os.getenv("CANVA_LOG_DIRECTORY", str(DEFAULT_LOG_DIRECTORY))
    )
    log_file_path = Path(
        os.getenv("CANVA_BUILDER_LOG_FILE_PATH", str(DEFAULT_LOG_FILE_PATH))
    )
    log_directory.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    rotating_handler = TimedRotatingFileHandler(
        str(log_file_path),
        when="midnight",
        interval=1,
        backupCount=14,
        encoding="utf-8",
    )
    rotating_handler.setFormatter(formatter)
    logger.addHandler(rotating_handler)


def _normalize_instagram(value: str) -> str:
    cleaned = value.strip().replace("@", "")
    return cleaned


def _sanitize_text(value: Any, fallback: str = " ") -> str:
    text = str(value or "")
    sanitized = "".join(
        character
        for character in text
        if unicodedata.category(character)
        not in {
            "Cc",  # Control chars
            "Cf",  # Format chars
            "Cs",  # Surrogates
            "Co",  # Private use
            "Cn",  # Unassigned
            "So",  # Symbols (incluye la mayoría de emojis)
        }
    )
    sanitized = sanitized.strip()
    return sanitized if sanitized else fallback


def parse_cli_payload(raw_payload: str) -> PosterRequest:
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Payload JSON inválido: {exc}") from exc

    fecha = str(payload.get("fecha") or payload.get("fecha_evento") or "").strip()
    if not fecha:
        raise ValueError("El payload debe incluir 'fecha' o 'fecha_evento'")

    raw_comics = payload.get("comicos")
    if not isinstance(raw_comics, list):
        raise ValueError("El payload debe incluir 'comicos' como array")

    comics: list[ComicEntry] = []
    for index, raw_comic in enumerate(raw_comics, start=1):
        if not isinstance(raw_comic, dict):
            raise ValueError(f"comicos[{index}] debe ser un objeto")
        nombre = str(raw_comic.get("nombre", "")).strip()
        instagram = _normalize_instagram(str(raw_comic.get("instagram", "")))
        if not nombre or not instagram:
            raise ValueError(f"comicos[{index}] requiere 'nombre' e 'instagram'")
        comics.append(ComicEntry(nombre=nombre, instagram=instagram))

    if len(comics) > 5:
        raise ValueError("El payload debe incluir como máximo 5 cómicos")

    while len(comics) < 5:
        comics.append(ComicEntry(nombre=" ", instagram=" "))

    return PosterRequest(fecha=fecha, comicos=comics)


def build_autofill_payload(request_payload: PosterRequest) -> dict[str, Any]:
    template_id = os.getenv("CANVA_TEMPLATE_ID", "").strip()
    if not template_id:
        raise RuntimeError("Falta CANVA_TEMPLATE_ID en variables de entorno")

    data_payload: dict[str, dict[str, str]] = {
        "fecha": {
            "type": "text",
            "text": _sanitize_text(request_payload.fecha),
        }
    }
    for index, comico in enumerate(request_payload.comicos, start=1):
        data_payload[f"comico_{index}_nombre"] = {
            "type": "text",
            "text": _sanitize_text(comico.nombre),
        }
        data_payload[f"comico_{index}_instagram"] = {
            "type": "text",
            "text": _sanitize_text(comico.instagram),
        }

    field_overrides = os.getenv("CANVA_FIELD_OVERRIDES_JSON", "").strip()
    if field_overrides:
        overrides = json.loads(field_overrides)
        for source_key, target_key in overrides.items():
            if source_key in data_payload and isinstance(target_key, str) and target_key.strip():
                data_payload[target_key.strip()] = data_payload.pop(source_key)

    return {
        "brand_template_id": template_id,
        "data": data_payload,
    }


def resolve_access_token() -> str:
    try:
        LOGGER.info("Solicitando token fresco con CANVA_REFRESH_TOKEN")
        tokens = refresh_access_token(
            persist_refresh_token=True,
            persist_access_token=True,
        )
        return tokens.access_token
    except CanvaAuthError as refresh_error:
        if refresh_error.requires_reauthorization:
            raise RuntimeError(
                "Refresh token de Canva inválido o revocado (invalid_grant). "
                "Debes reautorizar manualmente: ejecuta `canva_auth_utils.py authorize` y luego `exchange`."
            ) from refresh_error
        LOGGER.warning("No se pudo renovar token con refresh token: %s", refresh_error)
        cached_token = get_cached_access_token()
        if cached_token:
            LOGGER.info("Usando access token cacheado como fallback")
            return cached_token
        if os.getenv("CANVA_AUTHORIZATION_CODE", "").strip():
            LOGGER.info("Intentando recuperación con authorization code...")
            tokens = exchange_code_for_tokens(
                persist_refresh_token=True,
                persist_access_token=True,
            )
            return tokens.access_token
        raise RuntimeError("No se pudo obtener un access token válido para Canva") from refresh_error
    except Exception as refresh_error:
        LOGGER.warning("No se pudo renovar token con refresh token: %s", refresh_error)
        cached_token = get_cached_access_token()
        if cached_token:
            LOGGER.info("Usando access token cacheado como fallback")
            return cached_token
        if os.getenv("CANVA_AUTHORIZATION_CODE", "").strip():
            LOGGER.info("Intentando recuperación con authorization code...")
            tokens = exchange_code_for_tokens(
                persist_refresh_token=True,
                persist_access_token=True,
            )
            return tokens.access_token
        raise RuntimeError("No se pudo obtener un access token válido para Canva") from refresh_error


def request_canva_autofill(access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": "recova-canva-builder/1.0",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    response = requests.post(
        CANVA_AUTOFILL_URL,
        headers=headers,
        json=payload,
        timeout=45,
    )

    if response.status_code not in (200, 201):
        LOGGER.error("Error Canva autofill: %s - %s", response.status_code, response.text)
        raise RuntimeError(f"Canva autofill falló: {response.status_code} {response.text}")

    return response.json()


def _extract_job_id(response_payload: dict[str, Any]) -> str:
    candidates = [
        (response_payload.get("job") or {}).get("id"),
        response_payload.get("job_id"),
        response_payload.get("id"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    raise RuntimeError(
        f"No se pudo extraer job.id de la respuesta inicial de Canva: {response_payload}"
    )


def request_canva_autofill_status(access_token: str, job_id: str) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": "recova-canva-builder/1.0",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    response = requests.get(
        f"{CANVA_AUTOFILL_URL}/{job_id}",
        headers=headers,
        timeout=45,
    )

    if response.status_code != 200:
        LOGGER.error(
            "Error consultando estado de autofill (%s): %s - %s",
            job_id,
            response.status_code,
            response.text,
        )
        raise RuntimeError(
            f"Canva estado autofill falló ({job_id}): {response.status_code} {response.text}"
        )

    return response.json()


def wait_for_autofill_completion(access_token: str, initial_response: dict[str, Any]) -> dict[str, Any]:
    job_id = _extract_job_id(initial_response)
    LOGGER.info("Autofill job creado: %s", job_id)
    started_at = time.monotonic()
    unknown_status_count = 0

    for attempt in range(1, AUTOFILL_MAX_POLL_ATTEMPTS + 1):
        elapsed_seconds = int(time.monotonic() - started_at)
        try:
            status_payload = request_canva_autofill_status(access_token, job_id)
            status = str(status_payload.get("status", "")).strip().lower()

            print(
                "Esperando a Canva... "
                f"(Intento {attempt}/{AUTOFILL_MAX_POLL_ATTEMPTS} - "
                f"{elapsed_seconds}s transcurridos) - Estado: {status or 'desconocido'}"
            )
            if status in {"", "desconocido", "unknown", "none", "null"}:
                unknown_status_count += 1
                if unknown_status_count > AUTOFILL_UNKNOWN_STATUS_MAX_ITERATIONS:
                    raise RuntimeError(
                        "Canva devolvió estado desconocido/nulo durante más de "
                        f"{AUTOFILL_UNKNOWN_STATUS_MAX_ITERATIONS} iteraciones "
                        f"para el job_id={job_id}. Revisa los logs de Canva."
                    )
            else:
                unknown_status_count = 0

            if status == "success":
                return status_payload
            if status == "failed":
                raise RuntimeError(f"Autofill job falló ({job_id}): {status_payload}")
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as request_error:
            print(
                "Red lenta, reintentando... "
                f"(Intento {attempt}/{AUTOFILL_MAX_POLL_ATTEMPTS} - "
                f"{elapsed_seconds}s transcurridos)"
            )
            LOGGER.warning(
                "Fallo de red consultando estado del autofill %s en intento %s/%s: %s",
                job_id,
                attempt,
                AUTOFILL_MAX_POLL_ATTEMPTS,
                request_error,
            )

        if attempt < AUTOFILL_MAX_POLL_ATTEMPTS:
            time.sleep(AUTOFILL_POLL_INTERVAL_SECONDS)

    raise RuntimeError(
        "Timeout esperando finalización de Canva "
        f"({job_id}) tras {AUTOFILL_MAX_POLL_ATTEMPTS} intentos "
        f"y {int(time.monotonic() - started_at)}s"
    )


def extract_design_url(response_payload: dict[str, Any]) -> str:
    candidates = [
        response_payload.get("design_url"),
        response_payload.get("url"),
        ((response_payload.get("job") or {}).get("result") or {}).get("design_url"),
        ((response_payload.get("result") or {}).get("design") or {}).get("url"),
        ((response_payload.get("design") or {}).get("urls") or {}).get("edit_url"),
    ]

    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    raise RuntimeError(f"No se pudo extraer URL del diseño desde la respuesta de Canva: {response_payload}")


def _build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generador de cartelería Canva")
    parser.add_argument(
        "payload_json",
        help="Payload JSON con fecha y 5 cómicos",
    )
    return parser


def ejecutar_generacion_poster(request_payload: PosterRequest) -> str:
    access_token = resolve_access_token()
    autofill_payload = build_autofill_payload(request_payload)

    LOGGER.info(
        "Solicitando autofill a Canva para brand_template_id=%s",
        os.getenv("CANVA_TEMPLATE_ID", ""),
    )
    initial_response = request_canva_autofill(access_token, autofill_payload)
    completed_payload = wait_for_autofill_completion(access_token, initial_response)
    return extract_design_url(completed_payload)


def main() -> None:
    load_dotenv()
    configure_logging()

    parser = _build_cli()
    args = parser.parse_args()

    poster_request = parse_cli_payload(args.payload_json)
    design_url = ejecutar_generacion_poster(poster_request)

    LOGGER.info("Diseño generado correctamente: %s", design_url)
    print(design_url)


if __name__ == "__main__":
    main()
