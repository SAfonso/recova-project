> Nota v0.5.56: la plantilla activa embebe el micrófono en SVG (sin URL externa), reduce tipografía de `.comico` a 60px, y `capture_screenshot` usa `goto(..., wait_until="networkidle")` + `await page.wait_for_timeout(2000)` con viewport 1080x1350 para evitar capturas incompletas.

> Nota v0.5.57: se incorpora `backend/src/core/svg_composer.py` como núcleo del SDD v2 para composición vectorial pura (Safe Zone `Y=400..1100`), coexistiendo por ahora con el flujo Playwright actual.

> Nota v0.5.58: el `SVGLineupComposer` pasa a modo híbrido de producción con `base_poster.png` como fondo y capa de texto SVG; el engine valida assets (`font` + `base image`) y falla con `ERR_ASSET_MISSING` si falta alguno.

> Nota v0.5.59: el compositor SVG embebe `base_poster.png` y la fuente TTF como `data URI` en Base64 para que CairoSVG renderice de forma determinista sin depender de rutas `file://`.

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
2. Renderiza `template.html` con Jinja2 en `backend/src/mcp_server.py` usando datos del payload (`lineup`, `event_id`, `date/event.date/metadata.date_text`) y escribe el HTML expandido en un archivo temporal.
3. Delega la captura a `capture_screenshot(...)` en `backend/src/core/render.py` (único punto Playwright), pasando el HTML ya procesado y un script mínimo de sincronización (`window.renderReady = true;`).
4. El renderer:
   - genera HTML desde `backend/src/templates/lineup_v1.html`,
   - captura PNG,
   - sube a bucket `posters` en Supabase.
5. La API devuelve:
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

### Render Jinja2 previo a Playwright

El servidor MCP elimina la dependencia de `backend/src/core/data_binder.py` para inyección de lineup en este flujo. La expansión de bucles `{% for ... %}` y variables `{{ ... }}` ocurre en backend con Jinja2 antes de abrir Chromium, evitando que la imagen final contenga placeholders sin resolver.

## Cierre seguro de Playwright
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
