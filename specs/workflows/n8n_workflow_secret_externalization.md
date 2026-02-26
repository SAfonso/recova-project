# Spec: n8n Workflow Secret Externalization

- Estado: Accepted
- Fecha: 2026-02-26
- Version objetivo: 0.5.24
- Alcance: `workflows/n8n/*.json`

## Contexto

Los exports de n8n se versionan en Git para trazabilidad operativa. Estos JSON no deben incluir secretos ni valores de infraestructura sensibles (tokens, API keys o hosts/IPs internas) en claro.

Se detectaron hardcodes en workflows de ingesta, scoring y lineup (Supabase REST, `X-API-KEY` y endpoints del backend).

## Objetivo

Externalizar credenciales y endpoints sensibles de workflows n8n usando variables de entorno de n8n (`$env`) y dejar un contrato automatizado que impida regresiones.

## Requisitos funcionales

1. Los workflows en `workflows/n8n/` no deben contener secretos hardcodeados en nodos HTTP.
2. Los headers `apikey`, `Authorization` y `X-API-KEY` deben resolverse desde `{{$env...}}`.
3. Las URLs del backend (`/ingest`, `/scoring`) deben resolverse desde variables de entorno de n8n.
4. Las URLs REST de Supabase deben construirse desde `SUPABASE_URL`, sin dominio fijo en el JSON.
5. Debe existir documentación operativa para configurar estas variables en el runtime de n8n.
6. Debe existir un test de contrato versionado que valide:
   - ausencia de patrones hardcodeados conocidos
   - presencia de referencias `{{$env...}}` esperadas
   - validez JSON de los exports

## Variables de entorno requeridas (n8n runtime)

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `WEBHOOK_API_KEY`
- `N8N_BACKEND_INGEST_URL`
- `N8N_BACKEND_SCORING_URL`

## Mapeo esperado (workflows actuales)

- `workflows/n8n/Ingesta-Solicitudes.json`
  - `url` POST ingesta -> `{{$env.N8N_BACKEND_INGEST_URL}}`
  - `X-API-KEY` -> `{{$env.WEBHOOK_API_KEY}}`
  - REST `/comicos` -> `{{$env.SUPABASE_URL + '/rest/v1/comicos'}}`
  - headers `apikey`/`Authorization` -> `{{$env.SUPABASE_KEY}}` y `{{'Bearer ' + $env.SUPABASE_KEY}}`
- `workflows/n8n/Scoring & Draft.json`
  - `url` scoring -> `{{$env.N8N_BACKEND_SCORING_URL}}`
- `workflows/n8n/LineUp.json`
  - REST `/lineup_candidates` -> `{{$env.SUPABASE_URL + '/rest/v1/lineup_candidates'}}`
  - headers `apikey`/`Authorization` -> `{{$env.SUPABASE_KEY}}` y `{{'Bearer ' + $env.SUPABASE_KEY}}`

## Criterios de aceptacion

1. `rg` no encuentra valores hardcodeados previamente usados (keys/IPs/dominio Supabase REST) dentro de `workflows/n8n/*.json`.
2. Los 3 exports de `workflows/n8n/` son JSON validos.
3. `pytest -q backend/tests/unit/test_n8n_workflows_security.py` pasa en local.
4. `README.md`, `CHANGELOG.md` y una doc en `docs/` reflejan el cambio y la politica de secretos.

## Fuera de alcance

- Rotacion de claves en Supabase/n8n.
- Encriptado de secretos dentro de n8n (se gestiona por la propia plataforma).
- Refactor de `workflows/main_pipeline.json` legado (no forma parte de este cambio).
