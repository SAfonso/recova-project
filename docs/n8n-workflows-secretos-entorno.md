# Workflows n8n: secretos y variables de entorno

## Objetivo

Estandarizar los exports versionados de n8n (`workflows/n8n/*.json`) para que no contengan secretos ni endpoints sensibles hardcodeados.

Este cambio sigue la spec: `specs/workflows/n8n_workflow_secret_externalization.md`.

## Variables requeridas en n8n

Configura estas variables en el runtime real de n8n (Coolify/Docker/PM2/systemd):

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `WEBHOOK_API_KEY`
- `N8N_BACKEND_INGEST_URL`
- `N8N_BACKEND_SCORING_URL`

Nota: que existan en el `.env` del repo no garantiza que n8n las vea. Deben estar cargadas en el proceso de n8n.

## Regla de exportacion

Antes de versionar un workflow:

1. Sustituye credenciales en nodos HTTP por expresiones `{{$env...}}`.
2. No dejes IPs/hosts internos de backend en claro.
3. Construye endpoints REST de Supabase desde `SUPABASE_URL`.
4. Verifica JSON valido y pasa el test de contrato.

## Ejemplos de expresiones (n8n)

- `={{ $env.SUPABASE_KEY }}`
- `={{ 'Bearer ' + $env.SUPABASE_KEY }}`
- `={{ $env.SUPABASE_URL + '/rest/v1/comicos' }}`
- `={{ $env.N8N_BACKEND_INGEST_URL }}`

## Verificacion local (repo)

1. Validar JSON de exports:

```bash
python3 - <<'PY'
import json, glob
for p in glob.glob('workflows/n8n/*.json'):
    json.load(open(p, 'r', encoding='utf-8'))
    print('OK', p)
PY
```

2. Ejecutar contrato anti-hardcode:

```bash
./.venv/bin/python -m pytest -q backend/tests/unit/test_n8n_workflows_security.py
```

## Archivos afectados en la primera migracion

- `workflows/n8n/Ingesta-Solicitudes.json`
- `workflows/n8n/Scoring & Draft.json`
- `workflows/n8n/LineUp.json`
- `.env` / `.env.example`
