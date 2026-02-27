# API de producción: Render + Upload (Flask)

## Objetivo
Exponer un endpoint HTTP para conectar el payload de n8n con el motor `PlaywrightRenderer`, generar el PNG final y publicarlo en Supabase Storage.

## Endpoint
- Método: `POST`
- Ruta: `/render-lineup`
- Módulo: `backend/src/app.py`

## Validación de contrato (SDD §2.2)
La API valida antes de renderizar:
- `request_id` UUID válido.
- `schema_version = "1.0"`.
- `event.date` formato `YYYY-MM-DD` y fecha válida.
- `event.timezone = "Europe/Madrid"`.
- `lineup` entre 1 y 8 elementos, `order` positivo sin duplicados, `name` no vacío.
- `instagram` limpio (sin `@` ni URL completa).
- `template.template_id = "lineup_default_v1"` + `width/height` enteros positivos + `theme = "default"`.
- `render.format = "png"`, `quality` 1..100, `scale > 0`, `timeout_ms` entre 3000 y 60000.
- `metadata.initiated_at` ISO-8601 y `trace_id` no vacío.

## Flujo de ejecución
1. Recibe JSON y valida el contrato.
2. Invoca `PlaywrightRenderer.render(payload)`.
3. El renderer:
   - genera HTML desde `backend/src/templates/lineup_v1.html`,
   - captura PNG,
   - sube a bucket `posters` en Supabase.
4. La API devuelve:
   - `public_url` para consumo directo,
   - objeto `mcp` con el contrato rico de salida (storage/artifact/timing/meta).

## Códigos HTTP
- `200` éxito.
- `400` validación de esquema.
- `404` template no encontrado.
- `422` lineup inválido procesable.
- `502` fallo de upload a storage.
- `504` timeout de render.
- `500` resto de errores internos.

## Despliegue
Gunicorn con 4 workers:

```bash
playwright install chromium
playwright install-deps
./.venv/bin/gunicorn -w 4 -b 0.0.0.0:8000 backend.src.app:app
```

PM2 gestionando Gunicorn:

```bash
pm2 start "./.venv/bin/gunicorn -w 4 -b 0.0.0.0:8000 backend.src.app:app" --name recova-renderer
```


## Modo fallback y warnings (SDD §3.1)
Si Chromium no arranca, el renderer mantiene `status: success` y devuelve warning estructurado `PLAYWRIGHT_FALLBACK_ACTIVE` en `warnings[]`, incluyendo `details.stage`, `details.reason` y `retryable` para debug operativo en VPS.
