"""Utilidades de autenticación OAuth2 para Canva API."""

from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

CANVA_TOKEN_URL = "https://api.canva.com/rest/v1/oauth/token"
BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_LOG_DIRECTORY = BACKEND_DIR / "logs"
DEFAULT_LOG_FILE_PATH = DEFAULT_LOG_DIRECTORY / "canva_auth.log"
DEFAULT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"

LOGGER = logging.getLogger("canva_auth")


@dataclass(frozen=True)
class CanvaTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str

    @classmethod
    def from_response(cls, payload: dict[str, Any]) -> "CanvaTokens":
        return cls(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token", ""),
            expires_in=int(payload.get("expires_in", 3600)),
            token_type=payload.get("token_type", "Bearer"),
        )


def configure_logging() -> None:
    log_directory = Path(
        os.getenv("CANVA_LOG_DIRECTORY", str(DEFAULT_LOG_DIRECTORY))
    )
    log_file_path = Path(
        os.getenv("CANVA_AUTH_LOG_FILE_PATH", str(DEFAULT_LOG_FILE_PATH))
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


def _get_required_env(variable_name: str) -> str:
    value = os.getenv(variable_name, "").strip()
    if not value:
        raise RuntimeError(f"Falta variable de entorno requerida: {variable_name}")
    return value


def _build_auth() -> HTTPBasicAuth:
    client_id = _get_required_env("CANVA_CLIENT_ID")
    client_secret = _get_required_env("CANVA_CLIENT_SECRET")
    return HTTPBasicAuth(client_id, client_secret)


def _persist_refresh_token(new_refresh_token: str, env_path: Path | None = None) -> None:
    target_path = env_path or Path(os.getenv("CANVA_ENV_PATH", DEFAULT_ENV_PATH))
    if not target_path.exists():
        LOGGER.warning("No se encontró .env para persistir refresh token en: %s", target_path)
        return

    lines = target_path.read_text(encoding="utf-8").splitlines()
    updated = False
    for index, line in enumerate(lines):
        if line.startswith("CANVA_REFRESH_TOKEN="):
            lines[index] = f"CANVA_REFRESH_TOKEN={new_refresh_token}"
            updated = True
            break

    if not updated:
        lines.append(f"CANVA_REFRESH_TOKEN={new_refresh_token}")

    target_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    LOGGER.info("Refresh token persistido en %s", target_path)


def exchange_code_for_tokens(
    authorization_code: str | None = None,
    redirect_uri: str | None = None,
    code_verifier: str | None = None,
    persist_refresh_token: bool = True,
) -> CanvaTokens:
    """Intercambia un authorization code por access y refresh token."""

    code = authorization_code or _get_required_env("CANVA_AUTHORIZATION_CODE")
    callback = redirect_uri or _get_required_env("CANVA_REDIRECT_URI")
    pkce_code_verifier = code_verifier or _get_required_env("CANVA_CODE_VERIFIER")

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": callback,
        "code_verifier": pkce_code_verifier,
    }
    response = requests.post(
        CANVA_TOKEN_URL,
        data=payload,
        auth=_build_auth(),
        timeout=30,
    )
    if response.status_code != 200:
        LOGGER.error("Error al canjear authorization code: %s - %s", response.status_code, response.text)
        raise RuntimeError(
            "Canva OAuth exchange falló: "
            f"{response.status_code} {response.text}. "
            "Revisa client_id/client_secret, redirect_uri exacta, "
            "authorization code vigente y code_verifier (PKCE)."
        )

    tokens = CanvaTokens.from_response(response.json())
    if persist_refresh_token and tokens.refresh_token:
        _persist_refresh_token(tokens.refresh_token)
    LOGGER.info("Authorization code canjeado correctamente")
    return tokens


def refresh_access_token(refresh_token: str | None = None, persist_refresh_token: bool = True) -> CanvaTokens:
    """Renueva el access token usando el refresh token vigente."""

    current_refresh_token = refresh_token or _get_required_env("CANVA_REFRESH_TOKEN")
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": current_refresh_token,
    }
    response = requests.post(
        CANVA_TOKEN_URL,
        data=payload,
        auth=_build_auth(),
        timeout=30,
    )

    if response.status_code != 200:
        LOGGER.error("Error renovando access token: %s - %s", response.status_code, response.text)
        raise RuntimeError(f"Canva OAuth refresh falló: {response.status_code} {response.text}")

    tokens = CanvaTokens.from_response(response.json())
    if persist_refresh_token and tokens.refresh_token:
        _persist_refresh_token(tokens.refresh_token)

    LOGGER.info("Access token renovado correctamente")
    return tokens


def _build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Utilidades OAuth2 para Canva")
    subparsers = parser.add_subparsers(dest="command", required=True)

    exchange_parser = subparsers.add_parser("exchange", help="Canjear code inicial")
    exchange_parser.add_argument("--code", dest="code", help="Authorization code", default=None)
    exchange_parser.add_argument("--redirect-uri", dest="redirect_uri", default=None)
    exchange_parser.add_argument(
        "--code-verifier",
        dest="code_verifier",
        help="PKCE code verifier usado al pedir el authorization code",
        default=None,
    )

    refresh_parser = subparsers.add_parser("refresh", help="Renovar access token")
    refresh_parser.add_argument("--refresh-token", dest="refresh_token", default=None)

    return parser


def main() -> None:
    load_dotenv()
    configure_logging()

    parser = _build_cli()
    args = parser.parse_args()

    if args.command == "exchange":
        tokens = exchange_code_for_tokens(
            authorization_code=args.code,
            redirect_uri=args.redirect_uri,
            code_verifier=args.code_verifier,
            persist_refresh_token=True,
        )
    else:
        tokens = refresh_access_token(
            refresh_token=args.refresh_token,
            persist_refresh_token=True,
        )

    print(
        json.dumps(
            {
                "access_token": tokens.access_token,
                "refresh_token": tokens.refresh_token,
                "expires_in": tokens.expires_in,
                "token_type": tokens.token_type,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
