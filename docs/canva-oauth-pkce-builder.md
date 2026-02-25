# Proceso Designer (Canva): OAuth PKCE + Builder de Cartelería

## Alcance
Este documento consolida los cambios de proceso introducidos en:
- `0.5.16` (alta de `canva_auth_utils.py` y `canva_builder.py`)
- `0.5.17` (PKCE guiado, caché de access token, manejo de errores OAuth)
- `0.5.18` (estrategia `refresh-first` en el builder + fallbacks)

## Objetivo del proceso
Automatizar la generación del póster final desde n8n usando Canva API:
1. Obtener/renovar credenciales OAuth válidas.
2. Construir el payload de autofill con fecha + 5 cómicos.
3. Solicitar a Canva la generación del diseño.
4. Devolver la URL del diseño por `stdout` para que n8n la consuma.

## Componentes implicados
- `backend/src/canva_auth_utils.py`
  - CLI OAuth (`authorize`, `exchange`, `refresh`)
  - PKCE (`code_verifier` + `code_challenge`)
  - Persistencia segura en `.env` con `dotenv.set_key`
  - Caché de `CANVA_ACCESS_TOKEN` con TTL (`CANVA_ACCESS_TOKEN_EXPIRES_AT`)
- `backend/src/canva_builder.py`
  - Validación del payload de entrada
  - Resolución de token (`refresh-first` + fallbacks)
  - Llamada a `https://api.canva.com/rest/v1/autofills`
  - Extracción de `design_url` desde distintas formas de respuesta

## Flujo OAuth (PKCE) recomendado

### 1. Bootstrap de autorización (PKCE)
Comando:

```bash
python backend/src/canva_auth_utils.py authorize
```

Salida (JSON):
- `authorization_url`
- `code_verifier`
- `code_challenge`

Comportamiento:
- Genera `code_verifier` aleatorio (o usa `--code-verifier` si se fuerza manualmente).
- Calcula `code_challenge` SHA-256 (`S256`).
- Persiste `CANVA_CODE_VERIFIER` en `.env` (si existe).

### 2. Exchange (authorization code -> tokens)
Comando:

```bash
python backend/src/canva_auth_utils.py exchange --code "<code_del_callback>" --code-verifier "<code_verifier>"
```

Comportamiento:
- Usa endpoint OAuth oficial: `https://api.canva.com/rest/v1/oauth/token`
- Envía payload `application/x-www-form-urlencoded`
- Persiste:
  - `CANVA_ACCESS_TOKEN`
  - `CANVA_ACCESS_TOKEN_EXPIRES_AT`
  - `CANVA_REFRESH_TOKEN` (si Canva rota el refresh token)

### 3. Refresh (renovación manual o automática)
Comando:

```bash
python backend/src/canva_auth_utils.py refresh
```

Comportamiento:
- Renueva `access_token` usando `CANVA_REFRESH_TOKEN`.
- Persiste `access_token` y expiración.
- Si Canva devuelve `invalid_grant`, se marca `requires_reauthorization=True` en `CanvaAuthError`.

## Estrategia actual de token en `canva_builder.py` (0.5.18)
`resolve_access_token()` aplica este orden:
1. Intenta `refresh_access_token(...)` al inicio de cada generación (`refresh-first`).
2. Si falla el refresh por error temporal, intenta `get_cached_access_token()`.
3. Si no hay token cacheado válido y existe `CANVA_AUTHORIZATION_CODE`, intenta `exchange_code_for_tokens(...)`.
4. Si el refresh falla con `invalid_grant`, aborta con mensaje explícito de reautorización manual (`authorize` + `exchange`).

Esto prioriza token fresco, pero mantiene continuidad si el refresh falla temporalmente.

## Contrato del payload del builder (CLI / n8n)
Entrada esperada en `backend/src/canva_builder.py`:
- JSON string como único argumento CLI.
- Debe incluir:
  - `fecha` o `fecha_evento`
  - `comicos` (array)
- Reglas:
  - exactamente `5` cómicos
  - cada cómico requiere `nombre` e `instagram`
  - `instagram` se normaliza quitando `@`

Ejemplo:

```json
{
  "fecha": "2026-02-22",
  "comicos": [
    {"nombre": "A", "instagram": "@a"},
    {"nombre": "B", "instagram": "@b"},
    {"nombre": "C", "instagram": "@c"},
    {"nombre": "D", "instagram": "@d"},
    {"nombre": "E", "instagram": "@e"}
  ]
}
```

## Mapeo de campos al template Canva
`build_autofill_payload()` genera por defecto:
- `fecha`
- `comico_1_nombre` ... `comico_5_nombre`
- `comico_1_instagram` ... `comico_5_instagram`

Si el template usa nombres distintos, se puede remapear con:
- `CANVA_FIELD_OVERRIDES_JSON`

Ejemplo:

```dotenv
CANVA_FIELD_OVERRIDES_JSON={"fecha":"fecha_evento","comico_1_nombre":"nombre_1"}
```

## Variables de entorno críticas
- `CANVA_CLIENT_ID`
- `CANVA_CLIENT_SECRET`
- `CANVA_REDIRECT_URI`
- `CANVA_CODE_VERIFIER`
- `CANVA_REFRESH_TOKEN`
- `CANVA_TEMPLATE_ID`

Variables opcionales de soporte:
- `CANVA_AUTHORIZATION_CODE` (bootstrap / recuperación)
- `CANVA_ACCESS_TOKEN`
- `CANVA_ACCESS_TOKEN_EXPIRES_AT`
- `CANVA_ENV_PATH`
- `CANVA_LOG_DIRECTORY`
- `CANVA_AUTH_LOG_FILE_PATH`
- `CANVA_BUILDER_LOG_FILE_PATH`

## Logging operativo
- `backend/logs/canva_auth.log` (rotativo diario, 14 backups)
- `backend/logs/canva_builder.log` (rotativo diario, 14 backups)

Se usan para:
- errores OAuth (`exchange` / `refresh`)
- trazas de persistencia de tokens en `.env`
- errores de `autofill`
- confirmación de generación de diseño

## Manejo de errores (resumen)
- `CanvaAuthError`: error OAuth con metadatos (`status_code`, `error_code`, `response_body`)
- `invalid_grant`: requiere reautorización manual
- Error de autofill (`status != 200/201`): se registra y se propaga como `RuntimeError`
- Si no se encuentra URL de diseño en la respuesta de Canva, se lanza excepción con payload recibido

## Cobertura de tests relevante
`backend/tests/unit/test_canva_builder.py` cubre:
- validación del payload (5 cómicos)
- remapeo de campos (`CANVA_FIELD_OVERRIDES_JSON`)
- extracción de URL de diseño en respuestas anidadas
- prioridad del token fresco por refresh
- fallback a token cacheado si falla el refresh

## Scripts auxiliares de diagnóstico
En `backend/src/` existen `getVeri.py` y `test.py` como scripts manuales de troubleshooting OAuth/PKCE.
- No forman parte del flujo productivo.
- Deben tratarse como material de diagnóstico local.
