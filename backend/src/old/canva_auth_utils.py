"""Utilidades de autenticación OAuth2 para Canva API."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv, set_key
from requests.auth import HTTPBasicAuth

CANVA_TOKEN_URL = "https://api.canva.com/rest/v1/oauth/token"
CANVA_AUTHORIZE_URL = "https://www.canva.com/api/oauth/authorize"
DEFAULT_CANVA_SCOPE = "design:meta:read design:content:read design:content:write"
BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_LOG_DIRECTORY = BACKEND_DIR / "logs"
DEFAULT_LOG_FILE_PATH = DEFAULT_LOG_DIRECTORY / "canva_auth.log"
DEFAULT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
ACCESS_TOKEN_ENV_VAR = "CANVA_ACCESS_TOKEN"
ACCESS_TOKEN_EXPIRES_AT_ENV_VAR = "CANVA_ACCESS_TOKEN_EXPIRES_AT"

LOGGER = logging.getLogger("canva_auth")


class CanvaAuthError(RuntimeError):
    """Error controlado de OAuth para permitir manejo programático."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        response_body: str | None = None,
        requires_reauthorization: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.response_body = response_body
        self.requires_reauthorization = requires_reauthorization


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


@dataclass(frozen=True)
class CanvaAuthorizationBootstrap:
    authorization_url: str
    code_verifier: str
    code_challenge: str


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


def _extract_error_code(response: requests.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None

    if not isinstance(payload, dict):
        return None

    raw_error = payload.get("error") or payload.get("code")
    return str(raw_error).strip() if raw_error else None


def _persist_env_value(var_name: str, value: str, env_path: Path | None = None) -> None:
    target_path = env_path or Path(os.getenv("CANVA_ENV_PATH", DEFAULT_ENV_PATH))
    if not target_path.exists():
        LOGGER.warning("No se encontró .env para persistir %s en: %s", var_name, target_path)
        return

    set_key(
        str(target_path),
        var_name,
        value,
        quote_mode="never",
        encoding="utf-8",
    )
    LOGGER.info("%s persistido en %s", var_name, target_path)


def _persist_refresh_token(new_refresh_token: str, env_path: Path | None = None) -> None:
    _persist_env_value("CANVA_REFRESH_TOKEN", new_refresh_token, env_path=env_path)


def _persist_access_token(tokens: CanvaTokens, env_path: Path | None = None) -> None:
    _persist_env_value(ACCESS_TOKEN_ENV_VAR, tokens.access_token, env_path=env_path)
    expires_at = int(time.time()) + max(tokens.expires_in, 0)
    _persist_env_value(ACCESS_TOKEN_EXPIRES_AT_ENV_VAR, str(expires_at), env_path=env_path)


def get_cached_access_token(min_ttl_seconds: int = 120) -> str | None:
    access_token = os.getenv(ACCESS_TOKEN_ENV_VAR, "").strip()
    if not access_token:
        return None

    expires_at_raw = os.getenv(ACCESS_TOKEN_EXPIRES_AT_ENV_VAR, "").strip()
    if not expires_at_raw:
        return None

    try:
        expires_at = int(expires_at_raw)
    except ValueError:
        LOGGER.warning(
            "Valor inválido en %s: %s",
            ACCESS_TOKEN_EXPIRES_AT_ENV_VAR,
            expires_at_raw,
        )
        return None

    if expires_at <= int(time.time()) + min_ttl_seconds:
        return None

    return access_token


def _build_code_challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")


def build_authorization_bootstrap(
    code_verifier: str | None = None,
    scope: str | None = None,
    persist_code_verifier: bool = True,
) -> CanvaAuthorizationBootstrap:
    client_id = _get_required_env("CANVA_CLIENT_ID")
    redirect_uri = _get_required_env("CANVA_REDIRECT_URI")

    verifier = (code_verifier or secrets.token_urlsafe(80)).strip()
    if not verifier:
        raise RuntimeError("No se pudo construir CANVA_CODE_VERIFIER")

    challenge = _build_code_challenge(verifier)
    requested_scope = (scope or os.getenv("CANVA_SCOPES", DEFAULT_CANVA_SCOPE)).strip()

    query = urlencode(
        {
            "code_challenge_method": "s256",
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": requested_scope,
            "code_challenge": challenge,
        }
    )

    if persist_code_verifier:
        _persist_env_value("CANVA_CODE_VERIFIER", verifier)

    return CanvaAuthorizationBootstrap(
        authorization_url=f"{CANVA_AUTHORIZE_URL}?{query}",
        code_verifier=verifier,
        code_challenge=challenge,
    )


def exchange_code_for_tokens(
    authorization_code: str | None = None,
    redirect_uri: str | None = None,
    code_verifier: str | None = None,
    persist_refresh_token: bool = True,
    persist_access_token: bool = True,
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
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        auth=_build_auth(),
        timeout=30,
    )
    if response.status_code != 200:
        LOGGER.error("Error al canjear authorization code: %s - %s", response.status_code, response.text)
        raise CanvaAuthError(
            "Canva OAuth exchange falló: "
            f"{response.status_code} {response.text}. "
            "Revisa client_id/client_secret, redirect_uri exacta, "
            "authorization code vigente y code_verifier (PKCE).",
            status_code=response.status_code,
            error_code=_extract_error_code(response),
            response_body=response.text,
        )

    tokens = CanvaTokens.from_response(response.json())
    if persist_access_token and tokens.access_token:
        _persist_access_token(tokens)
    if persist_refresh_token and tokens.refresh_token:
        _persist_refresh_token(tokens.refresh_token)
    LOGGER.info("Authorization code canjeado correctamente")
    return tokens


def refresh_access_token(
    refresh_token: str | None = None,
    persist_refresh_token: bool = True,
    persist_access_token: bool = True,
) -> CanvaTokens:
    """Renueva el access token usando el refresh token vigente."""

    current_refresh_token = refresh_token or _get_required_env("CANVA_REFRESH_TOKEN")
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": current_refresh_token,
    }
    response = requests.post(
        CANVA_TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        auth=_build_auth(),
        timeout=30,
    )

    if response.status_code != 200:
        LOGGER.error("Error renovando access token: %s - %s", response.status_code, response.text)
        error_code = _extract_error_code(response)
        requires_reauthorization = error_code == "invalid_grant"
        hint = (
            " Debes reautorizar manualmente (authorize + exchange)."
            if requires_reauthorization
            else ""
        )
        raise CanvaAuthError(
            f"Canva OAuth refresh falló: {response.status_code} {response.text}.{hint}",
            status_code=response.status_code,
            error_code=error_code,
            response_body=response.text,
            requires_reauthorization=requires_reauthorization,
        )

    tokens = CanvaTokens.from_response(response.json())
    if persist_access_token and tokens.access_token:
        _persist_access_token(tokens)
    if persist_refresh_token and tokens.refresh_token:
        _persist_refresh_token(tokens.refresh_token)

    LOGGER.info("Access token renovado correctamente")
    return tokens


def _build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Utilidades OAuth2 para Canva")
    subparsers = parser.add_subparsers(dest="command", required=True)

    authorize_parser = subparsers.add_parser(
        "authorize",
        help="Generar code_verifier + URL de autorización PKCE",
    )
    authorize_parser.add_argument(
        "--scope",
        dest="scope",
        default=None,
        help="Scopes separados por espacios (default: design:* para lectura/escritura)",
    )
    authorize_parser.add_argument(
        "--code-verifier",
        dest="bootstrap_code_verifier",
        default=None,
        help="Forzar un verifier manual en lugar de autogenerarlo",
    )

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

    if args.command == "authorize":
        bootstrap = build_authorization_bootstrap(
            code_verifier=args.bootstrap_code_verifier,
            scope=args.scope,
            persist_code_verifier=True,
        )
        print(
            json.dumps(
                {
                    "authorization_url": bootstrap.authorization_url,
                    "code_verifier": bootstrap.code_verifier,
                    "code_challenge": bootstrap.code_challenge,
                },
                ensure_ascii=False,
            )
        )
        return

    if args.command == "exchange":
        tokens = exchange_code_for_tokens(
            authorization_code=args.code,
            redirect_uri=args.redirect_uri,
            code_verifier=args.code_verifier,
            persist_refresh_token=True,
            persist_access_token=True,
        )
    else:
        tokens = refresh_access_token(
            refresh_token=args.refresh_token,
            persist_refresh_token=True,
            persist_access_token=True,
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
