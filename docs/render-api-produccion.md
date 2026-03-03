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
2. Genera `injection_js` con el Data Binder y delega la captura a `capture_screenshot(...)` en `backend/src/core/render.py` (único punto Playwright).
   - El Data Binder reemplaza placeholders literales de plantilla (`{{ ... }}` / `{% ... %}`) y aplica binding por selectores (`.slot-n .name` y `.lineup .comico`) antes de la captura.
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


## Servidor MCP HTTP para n8n (FastMCP + REST)

Además del endpoint Flask histórico, el proyecto incorpora `backend/src/mcp_server.py` en modo HTTP para integración con n8n:

- Host: `127.0.0.1`
- Puerto: `5050`
- Endpoint REST n8n: `POST /tools/render_lineup`
- Healthcheck: `GET /healthz`
- Transporte MCP streamable (si `mcp[http]` está disponible): `POST /mcp`

### Contrato de respuesta del endpoint MCP REST
- Éxito: devuelve directamente el PNG renderizado como stream (`Content-Type: image/png`) usando `FileResponse(path=output_path, media_type="image/png", filename="cartel.png")`.
- Error de motor de render: devuelve `HTTP 500` con `detail` JSON:

```json
{
  "error": "Render engine failed",
  "details": "..."
}
```

- Si el archivo no existe tras el render, responde `HTTP 500` con `detail: "El archivo no se generó correctamente"`.

Nota operativa: el artefacto físico en `/tmp` puede limpiarse tras la respuesta (background task o limpieza periódica) para evitar saturación del disco del VPS.

### Logging de tráfico
Cada request HTTP registra `path` y `event_id` en `backend/logs/mcp_render.log` para auditoría operativa.

### Cierre seguro de Playwright
El flujo de render cierra `BrowserContext` y `Browser` en bloque `finally`, evitando procesos zombie de Chromium en el VPS.

### PM2 recomendado

```bash
pm2 start ecosystem.config.js --only recova-mcp-http
```

Comando equivalente directo:

```bash
pm2 start "./.venv/bin/python -m backend.src.mcp_server" --name recova-mcp-http
```


## Motor Playwright desacoplado

Desde `v0.5.45`, la integración con Playwright vive exclusivamente en `backend/src/core/render.py` mediante `capture_screenshot(html_path, injection_js, output_path)`.

Este módulo aplica hardening para VPS root (`--no-sandbox`, `--disable-dev-shm-usage`), sincroniza la captura con `window.renderReady === true` y garantiza `browser.close()` con `try/finally` para evitar procesos zombie.
