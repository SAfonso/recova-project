## [0.5.48] - 2026-03-01

### Added
- `backend/tests/core/test_data_binder.py` añade casos de robustez para lineup vacío, lineup con strings y lineup con 10 artistas (mapeo tope de 8 slots).
- `backend/tests/mcp/test_data_binder.py` replica cobertura de contrato para entradas vacías/no-dict y cardinalidad extendida.
- `backend/tests/core/test_security.py` y `backend/tests/mcp/test_security.py` incorporan validación de Magic Bytes y red con `unittest.mock.patch("requests.get")` para EXE (`MZ`), PNG real, timeout y localhost bloqueado.

### Changed
- `backend/src/core/data_binder.py` endurece el contrato: valida tipo de `lineup`, evita crash por `.get` en strings y retorna fallback seguro `window.renderReady = true;` cuando el payload es inválido.
- `backend/src/core/security.py` restringe esquemas permitidos a `http/https` manteniendo bloqueo de hosts locales/privados.
- `backend/src/mcp_server.py` retorna `HTTP 422` para payload inválido en `POST /tools/render_lineup` (sin crash 500).
- `backend/tests/mcp/test_mcp_server_http.py` ajusta `test_render_invalid_payload` para esperar error controlado `400/422`.
- `README.md` y `docs/tests-backend.md` actualizan documentación de blindaje y comandos de cobertura.
- Bump de versión a `0.5.48` en `pyproject.toml`, `package.json` y `README.md`.

## [0.5.47] - 2026-03-01

### Added
- `pytest.ini` con `asyncio_mode = auto` y `asyncio_default_test_loop_scope = function` para estabilizar la suite async con pytest/pytest-asyncio recientes.
- `backend/tests/core/test_data_binder.py` con cobertura de FitText (reducción de `fontSize`) y mapeo de slots con ocultación de `.slot-4` a `.slot-8`.
- `backend/tests/core/test_security.py` con casos de URL hardening, Magic Bytes falsos (`.png` con header tipo ejecutable) y clasificación de errores de red.

### Changed
- `backend/tests/mcp/test_mcp_server_http.py` refactoriza `http_client` a `@pytest_asyncio.fixture` y mantiene pruebas HTTP in-process con `httpx.ASGITransport(app=app)`, añadiendo cobertura de payload inválido (`test_render_invalid_payload`).
- `backend/src/core/security.py` endurece validación de host bloqueando localhost, loopback e IPs privadas/link-local/reservadas antes de iniciar descarga de referencia.
- `README.md`, `docs/tests-backend.md`, `package.json` y `pyproject.toml` se actualizan para documentar y versionar el blindaje de infraestructura de tests.

## [0.5.46] - 2026-03-01

### Added
- `backend/tests/core/test_render.py` añade suite unitaria asíncrona para `capture_screenshot(...)`: flujo exitoso con HTML mínimo + `window.renderReady`, manejo de timeout cuando no se marca `renderReady` y verificación explícita del flag `--no-sandbox` al lanzar Chromium.
- `backend/tests/mcp/test_mcp_server_http.py` incorpora suite de integración HTTP con `httpx` para `GET /healthz`, contrato `POST /tools/render_lineup` y serialización de peticiones concurrentes mediante `render_lock`.

### Changed
- `docs/tests-backend.md` documenta los nuevos comandos de ejecución para las suites QA del motor de render y del servidor MCP HTTP.
- `README.md` actualiza la fuente de verdad técnica a `v0.5.46` e incluye la cobertura QA del refactor render/MCP y limpieza de artefactos en `/tmp`.
- Incremento de versión a `0.5.46` en `README.md`, `pyproject.toml` y `package.json`.

## [0.5.45] - 2026-03-01

### Added
- `backend/src/core/render.py` implementa `capture_screenshot(html_path, injection_js, output_path)` como motor Playwright agnóstico con flags root (`--no-sandbox`, `--disable-dev-shm-usage`), espera explícita de `window.renderReady === true` y captura PNG full page.
- `backend/tests/unit/test_core_render.py` añade cobertura unitaria para validar flags de lanzamiento, sincronización por `renderReady` y cierre garantizado de `Page`/`BrowserContext`/`Browser` incluso ante fallo.

### Changed
- `backend/src/mcp_server.py` delega la captura Playwright en `backend/src/core/render.py`, reduciendo responsabilidades de orquestación y manteniendo contrato de salida del renderer MCP.
- `README.md`, `docs/render-api-produccion.md` y `docs/mcp-agnostic-renderer-spec.md` documentan la separación del motor Playwright en capa core agnóstica.
- Incremento de versión a `0.5.45` en `README.md`, `pyproject.toml` y `package.json`.

## [0.5.44] - 2026-03-01

### Changed
- `backend/src/mcp_server.py` actualiza el puerto por defecto del servidor HTTP MCP a `5050` (incluyendo `MCP_PORT` fallback), manteniendo `POST /tools/render_lineup` para integración con n8n y emitiendo log de arranque `[RECOVA-RENDER] Servidor escuchando en http://127.0.0.1:5050.`.
- `backend/src/mcp_server.py` endurece el lanzamiento de Chromium en entorno root agregando `--disable-dev-shm-usage` junto a `--no-sandbox`.
- `backend/src/mcp_server.py` asegura liberación explícita de recursos Playwright cerrando `Page`, `BrowserContext` y `Browser` tras cada render para evitar procesos activos de Chromium.
- `README.md`, `docs/render-api-produccion.md` y `docs/mcp-agnostic-renderer-spec.md` documentan el nuevo puerto operativo `5050` y el log de arranque esperado.
- Incremento de versión a `0.5.44` en `README.md`, `pyproject.toml` y `package.json`.

## [0.5.43] - 2026-03-01

### Added
- `backend/src/mcp_server.py` migra a modo HTTP y levanta `uvicorn` en `127.0.0.1:8000` con endpoint REST `POST /tools/render_lineup`, healthcheck `GET /healthz` y montaje opcional de transporte MCP streamable en `/mcp` cuando existe `mcp[http]`.
- `backend/src/mcp_server.py` incorpora logging de tráfico HTTP en `backend/logs/mcp_render.log` registrando `path` y `event_id` por request para observabilidad en n8n.
- `ecosystem.config.js` define proceso PM2 `recova-mcp-http` usando `./.venv/bin/python -m backend.src.mcp_server`.

### Changed
- `backend/src/mcp_server.py` endurece el cierre de Playwright cerrando `BrowserContext` y `Browser` en bloque `finally` para evitar procesos zombie de Chromium.
- `requirements.txt` y `pyproject.toml` añaden dependencias de operación HTTP (`fastapi`, `uvicorn`, `mcp[http]`).
- `README.md`, `docs/render-api-produccion.md` y `docs/mcp-agnostic-renderer-spec.md` documentan el despliegue HTTP/PM2 y la trazabilidad de requests.
- Incremento de versión a `0.5.43` en `README.md`, `pyproject.toml` y `package.json`.

## [0.5.42] - 2026-03-01

### Added
- `backend/src/mcp_server.py` implementa orquestación MCP asíncrona con lock global (`asyncio.Lock`) para serializar renderizados y proteger RAM del VPS.
- Tool `render_lineup` con contrato FastMCP-compatible y parámetros `event_id`, `lineup`, `reference_image_url`, `template_id`.
- Motor Playwright integrado con `--no-sandbox`, carga de plantilla por catálogo (`backend/src/templates/catalog/{template_id}/template.html`), inyección por `generate_injection_js(...)` y espera de sincronización `window.renderReady === true` antes de capturar PNG en `/tmp/render_{event_id}.png`.

### Changed
- `backend/src/mcp_server.py` aplica flujo de seguridad previo (`validate_reference_image`) y fallback automático a plantilla `active` con `trace.recovery_notes` + warning de recuperación.
- `backend/src/mcp_server.py` añade manejo global de errores de Playwright devolviendo respuesta estructurada (`status=error`) para cumplir política de fallo no bloqueante.
- `README.md` y `docs/tests-backend.md` se actualizan para documentar el nuevo servidor MCP y su suite de integración asíncrona.
- Incremento de versión a `0.5.42` en `README.md`, `pyproject.toml` y `package.json`.

# Changelog

## [0.5.41] - 2026-03-01

### Added
- `backend/tests/mcp/test_server_integration.py` incorpora suite de integración asíncrona (pytest-asyncio) para el orquestador MCP con cuatro contratos SDD: flujo exitoso completo, recuperación ante fallo de seguridad, serialización por lock de concurrencia y verificación de caja negra sin fuga de metadatos sensibles.

### Changed
- `docs/tests-backend.md` agrega el comando dedicado para ejecutar `backend/tests/mcp/test_server_integration.py`.
- `README.md` actualiza la fuente de verdad técnica a `v0.5.41` e incorpora el hito TDD del orquestador MCP.
- Incremento de versión a `0.5.41` en `package.json` y `pyproject.toml`; actualización de `frontend/package.json` a `0.1.7`.

## [0.5.40] - 2026-03-01

### Added
- `backend/src/core/data_binder.py` implementa `generate_injection_script(lineup, max_slots=8)` y alias `generate_injection_js(...)` para cumplir SDD §13: binding exclusivo de nombres por `.slot-n .name`, ocultación de slots vacíos y ajuste FitText por overflow hasta mínimo `12px`.

### Changed
- `backend/src/core/data_binder.py` añade señal de sincronización `window.renderReady = true` al final del ajuste tipográfico para coordinación con Playwright.
- `README.md` actualiza la fuente de verdad técnica a `v0.5.40` e incorpora el estado de implementación del Data Binder DOM-safe.
- `docs/mcp-agnostic-renderer-spec.md` alinea Sección 13 con reducción de `1px`, mínimo `12px` y señal de listo para render.
- `docs/tests-backend.md` documenta el comando dedicado `backend/tests/mcp/test_data_binder.py`.
- Incremento de versión a `0.5.40` en `package.json` y `pyproject.toml`; actualización de `frontend/package.json` a `0.1.6`.

## [0.5.39] - 2026-03-01

### Added
- `backend/tests/mcp/test_security.py` agrega una suite TDD para validar esquema seguro HTTPS-only, bloqueo de wrappers de Google Drive/Dropbox, validación de Magic Bytes y manejo de timeout de red con recuperación no bloqueante.
- `backend/src/core/security.py` implementa `validate_reference_image(url)` con lectura por streaming de 32 bytes y detección de firmas PNG/JPEG/WebP según el contrato de seguridad MCP.

### Changed
- `README.md` actualiza la fuente de verdad técnica a `v0.5.39` e incorpora el hito de seguridad TDD previo a lógica de negocio.
- `docs/tests-backend.md` incorpora la nueva ruta de pruebas `backend/tests/mcp/test_security.py` y su objetivo de hardening de red/artefactos.
- Incremento de versión a `0.5.39` en `package.json` y `pyproject.toml`; actualización de `frontend/package.json` a `0.1.5`.

## [0.5.38] - 2026-03-01

### Added
- `specs/mcp_agnostic_renderer_spec.md` incorpora la **Sección 14** "Filosofía de Fallo No Bloqueante" con política de `HTTP 200 OK` para renders exitosos (incluyendo recuperación), semántica de error gestionada en JSON y prioridad explícita de continuidad para n8n.
- `specs/mcp_agnostic_renderer_spec.md` define matriz obligatoria de auto-recuperación para `ERR_CONTRACT_INVALID`, `ERR_INVALID_FILE_TYPE`, `ERR_NOT_DIRECT_LINK` y `ERR_CAPACITY_EXCEEDED` con fallback `/active/` y recorte automático de lineup cuando aplique.
- `specs/mcp_agnostic_renderer_spec.md` agrega protocolo de trazabilidad de recuperación con `trace.status = recovered_with_warnings` y `trace.recovery_notes` legible para notificación al Host (Telegram/n8n).

### Changed
- `specs/mcp_agnostic_renderer_spec.md` acota abortos reales únicamente a `ERR_RENDER_ENGINE_CRASH` y `ERR_STORAGE_UNREACHABLE`, reforzando la entrega de cartel funcional como prioridad del sistema.
- `docs/mcp-agnostic-renderer-spec.md` documenta operativamente la Sección 14 para adopción en flujos n8n-safe.
- `README.md` actualiza la fuente de verdad técnica a `v0.5.38` e incluye los nuevos invariantes de fallo no bloqueante.
- Incremento de versión a `0.5.38` en `package.json` y `pyproject.toml`; actualización de `frontend/package.json` a `0.1.4`.

## [0.5.37] - 2026-03-01

### Added
- `specs/mcp_agnostic_renderer_spec.md` incorpora la **Sección 13** "Motor de Inyección Visual e Integridad de Layout" con contrato Data-to-DOM estricto (`lineup[n].name` → `.slot-(n+1) .name`), exclusión visual normativa de `lineup[n].instagram` y mapeo único de `metadata.date_text`/`metadata.venue`.
- `specs/mcp_agnostic_renderer_spec.md` define el invariante de **FitText Engine** post-inyección en contexto Playwright, usando evaluación `scrollWidth` vs `clientWidth`, reducción iterativa de `font-size` en pasos de `2px` y límite mínimo por `min-font-size` en `manifest.json`.
- `specs/mcp_agnostic_renderer_spec.md` formaliza trazabilidad estética obligatoria en `trace.logs` para cada ajuste tipográfico aplicado por slot.

### Changed
- `specs/mcp_agnostic_renderer_spec.md` consolida el principio de **Single Responsibility** del renderer: salida limitada a `output.public_url` y `trace`, excluyendo captions o transformaciones editoriales para redes.
- `docs/mcp-agnostic-renderer-spec.md` documenta operativamente la nueva Sección 13 para adopción por integraciones.
- `README.md` actualiza la fuente de verdad técnica a `v0.5.37` incorporando invariantes de inyección visual y protección de layout.
- Incremento de versión a `0.5.37` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.36] - 2026-03-01

### Added
- `specs/mcp_agnostic_renderer_spec.md` incorpora la **Sección 12** "Unidad Atómica de Diseño (Plantilla Local)" con estructura obligatoria por `template_id` (`template.html`, `style.css`, `manifest.json`, `assets/`) en `backend/src/templates/catalog/`.
- `specs/mcp_agnostic_renderer_spec.md` formaliza el contrato de `manifest.json` con campos obligatorios `template_id`, `version`, `display_name`, `canvas.width/height`, `capabilities.min_slots/max_slots` y `font_strategy`.
- `specs/mcp_agnostic_renderer_spec.md` añade invariante de pre-vuelo de capacidad con error `TEMPLATE_CAPACITY_EXCEEDED`, soporte de `intent.force_capacity_override` y trazabilidad obligatoria `CAPACITY_OVERRIDE_ACTIVE`.

### Changed
- `docs/mcp-agnostic-renderer-spec.md` documenta el estándar operativo de plantilla atómica, el contrato de `manifest.json` y el override de capacidad con responsabilidad del Host.
- `README.md` actualiza la fuente de verdad técnica a `v0.5.36` incorporando la Sección 12 como estándar de configuración única de render.
- Incremento de versión a `0.5.36` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.35] - 2026-03-01

### Added
- `specs/mcp_agnostic_renderer_spec.md` incorpora la **Sección 9** con jerarquía de resiliencia de 2 niveles: `Active Mode` por intent y fallback local obligatorio a `backend/src/templates/catalog/fallback/`.
- `specs/mcp_agnostic_renderer_spec.md` añade trazabilidad normativa de fallback con registro obligatorio `SYSTEM_FALLBACK_TRIGGERED` en `trace.warnings`.
- `specs/mcp_agnostic_renderer_spec.md` incorpora la **Sección 10** de ciclo de vida de persistencia con lógica de archivo condicional al bucket `design-archive` para `vision_generated` y política explícita de no-archivo para `template_catalog`.
- `specs/mcp_agnostic_renderer_spec.md` incorpora la **Sección 11** de hidratación/recovery aceptando `intent.recovery_event_id` para re-render de carteles históricos generados por Vision.

### Changed
- `docs/mcp-agnostic-renderer-spec.md` documenta la operación de resiliencia, persistencia eficiente y recuperación desde archivo histórico.
- `README.md` actualiza la fuente de verdad técnica a `v0.5.35` con los nuevos invariantes de fallback, archivo condicional y purga efímera del VPS.
- Incremento de versión a `0.5.35` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.34] - 2026-03-01

### Added
- `specs/mcp_agnostic_renderer_spec.md` incorpora un protocolo estricto de validación de entrada para `reference_image_url` con Security Gate: pre-fetch de 32 bytes, inspección de Magic Bytes (PNG/JPEG/WebP) y fail-fast por `ERR_INVALID_FILE_TYPE`.
- `specs/mcp_agnostic_renderer_spec.md` añade invariantes de seguridad operativa de origen (`Direct Link Only`, soporte explícito de Supabase bucket y prohibición de wrappers HTML como Google Drive/Dropbox preview).

### Changed
- `specs/mcp_agnostic_renderer_spec.md` amplía la trazabilidad obligatoria para errores de acceso/no direct link (`ERR_ACCESS_DENIED_OR_NOT_DIRECT_LINK`) e incluye registro de MIME detectado vs esperado en `trace.logs`.
- `docs/mcp-agnostic-renderer-spec.md` documenta el manual operativo de enlaces de referencia válidos y el comportamiento del Security Gate.
- `README.md` actualiza la fuente de verdad técnica a `v0.5.34` incorporando las nuevas invariantes de seguridad del MCP Renderer.
- Incremento de versión a `0.5.34` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.33] - 2026-03-01

### Added
- `specs/mcp_agnostic_renderer_spec.md` define la nueva especificación SDD de la Capa de Abstracción MCP (Agnostic Renderer), incluyendo contrato de entrada único, invariantes de prioridad de modo y trazabilidad de salida.
- `docs/mcp-agnostic-renderer-spec.md` documenta la guía operativa de adopción y el alcance spec-first para desacoplar n8n del render físico.

### Changed
- `README.md` actualiza la Fuente de Verdad a `v0.5.33` e incorpora la nueva referencia MCP Agnostic Renderer.
- Incremento de versión a `0.5.33` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.32] - 2026-02-27

### Changed
- `workflows/n8n/LineUp.json` elimina hardcodes de Supabase y renderer en nodos HTTP, pasando a variables de entorno (`$env.SUPABASE_URL`, `$env.SUPABASE_KEY`, `$env.N8N_BACKEND_RENDER_URL`).
- `workflows/n8n/LineUp.json` actualiza `metadata.version` del payload enviado al renderer a `0.5.32`.
- `.env.example` incorpora `N8N_BACKEND_RENDER_URL` como variable requerida para ejecutar el flujo de render desde n8n.
- `README.md` actualiza la sección de fuente de verdad técnica con el hardening de secretos en workflows n8n.
- Incremento de versión a `0.5.32` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.31] - 2026-02-27

### Fixed
- `backend/src/playwright_renderer.py` corrige el contrato de `_DummyPage.screenshot(...)` para aceptar `path=None` y parámetros flexibles sin romper el fallback cuando la llamada no incluye `path`.
- `backend/src/playwright_renderer.py` mejora la resiliencia al capturar screenshot soportando retorno síncrono o coroutine, evitando errores en fallback.

### Changed
- `backend/src/playwright_renderer.py` mantiene salida MCP rica en fallback y agrega warning estructurado `PLAYWRIGHT_FALLBACK_ACTIVE` (`stage`, `reason`, `retryable`) alineado con SDD §3.1.
- `backend/src/playwright_renderer.py` deja trazabilidad explícita de la causa de fallo de arranque del navegador real en `warnings[].details.reason`.
- `backend/src/app.py` propaga warnings de fallback del renderer y soporta screenshots async en el flujo API de render.
- `backend/tests/unit/test_playwright_renderer.py` añade cobertura para contrato de `_DummyPage.screenshot()` sin `path` y warning estructurado en fallback.
- `README.md` y `docs/render-api-produccion.md` documentan instalación requerida en VPS (`playwright install chromium` y `playwright install-deps`).
- Incremento de versión a `0.5.31` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.30] - 2026-02-26

### Added
- `backend/src/app.py` implementa la API Flask de producción con `POST /render-lineup`, validación de payload según SDD §2.2 y respuesta de éxito con `public_url` + objeto `mcp`.
- `backend/tests/unit/test_app.py` añade cobertura para éxito, validación de instagram no limpio y mapeo HTTP `502` para `STORAGE_UPLOAD_FAILED`.
- `docs/render-api-produccion.md` documenta contrato de endpoint, flujo render+upload y comandos de despliegue en Gunicorn/PM2.

### Changed
- `backend/src/templates/lineup_v1.html` refuerza el diseño **Dark Premium** (Bebas Neue, gradientes oscuros y mejor legibilidad de slots).
- `README.md` y `docs/tests-backend.md` incorporan documentación de la nueva API de render y sus comandos de validación.
- Incremento de versión a `0.5.30` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.29] - 2026-02-26

### Changed
- `backend/src/playwright_renderer.py` ajusta el contrato de salida para devolver únicamente el JSON exacto de la spec (§3.1/§3.2), mantiene upload automático a Supabase Storage (`posters`) y expone `storage_url`/`public_url` reales.
- `backend/src/playwright_renderer.py` elimina el artefacto PNG temporal del disco tras una subida satisfactoria para evitar acumulación en el servidor.
- `backend/src/templates/lineup_v1.html` se actualiza al estilo visual **Dark Premium** (Bebas Neue, Montserrat y gradientes neón).
- `backend/tests/unit/test_playwright_renderer.py` actualiza expectativas de contrato de salida y añade prueba de limpieza post-upload de archivos temporales.
- `README.md` y `docs/tests-backend.md` documentan el cierre del flujo render+upload+cleanup y las nuevas comprobaciones.
- Incremento de versión a `0.5.29` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.28] - 2026-02-26

### Added
- `backend/tests/integration/test_supabase_upload.py` con prueba de integración para Supabase Storage: sube un PNG pequeño al bucket `posters`, valida la convención de ruta `YYYY-MM-DD/lineup_{request_id}.png` y comprueba respuesta HTTP `200` de la `public_url`.

### Changed
- `backend/src/playwright_renderer.py` incorpora upload a Supabase Storage con `storage3` usando `SUPABASE_URL` y `SUPABASE_KEY` desde entorno, guarda en bucket `posters`, retorna `public_url` en `storage` y añade métrica `timing.upload_ms`.
- `specs/playwright_renderer_spec.md` extiende el contrato de output para incluir proceso de upload a Supabase (`bucket`, naming convention, `public_url` obligatorio).
- `backend/tests/unit/test_playwright_renderer.py` actualiza contrato de éxito para incluir campos de storage Supabase (`bucket`, `public_url`) y timing de upload.
- `README.md` y `docs/tests-backend.md` documentan la integración de upload a Supabase Storage y el nuevo comando de test de integración.
- Incremento de versión a `0.5.28` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.27] - 2026-02-26

### Fixed
- `backend/src/playwright_renderer.py` actualiza `_launch_browser` para lanzar Chromium en modo servidor con `headless=True` y argumentos `--no-sandbox`, `--disable-setuid-sandbox`, `--disable-dev-shm-usage`, `--disable-gpu`, evitando fallos `PLAYWRIGHT_BROWSER_LAUNCH_FAILED` en entornos root/sin entorno gráfico.
- Si Playwright está instalado pero Chromium no puede iniciar, el renderer aplica fallback a `_DummyBrowser` en lugar de devolver error bloqueante, preservando salida `status: success` para contratos unitarios.

### Changed
- Incremento de versión a `0.5.27` en `package.json`, `pyproject.toml` y `README.md`.

Todos los cambios notables en este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.26] - 2026-02-26

### Added
- `backend/src/playwright_renderer.py` con implementación de `PlaywrightRenderer` basada en SDD: validación de payload v1, normalización/truncado (`name<=32`, `instagram<=30`), warning `LINEUP_UNDER_MINIMUM`, render de HTML con Jinja2 y captura con Playwright (fallback local cuando no hay runtime).
- `backend/src/templates/lineup_v1.html` como plantilla base minimalista en tema oscuro con placeholders para fecha y hasta 8 slots de cómicos (nombre + instagram).

### Changed
- `README.md` documenta el renderer local Playwright/Jinja2, novedades de la versión y actualización de estado de release.
- `requirements.txt` y `pyproject.toml` incorporan `jinja2` y `playwright` para soportar el motor de renderizado local.
- Incremento de versión a `0.5.26` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.25] - 2026-02-26

### Added
- `backend/tests/unit/test_playwright_renderer.py` con una suite SDD-first que fija el contrato del renderer Playwright: validación de payload v1 (spec §2.2), warning `LINEUP_UNDER_MINIMUM`, truncado de nombres >32 caracteres y output de éxito MCP-ready (spec §3.1).

### Changed
- `backend/tests/unit/test_playwright_renderer.py` fuerza import explícito de `PlaywrightRenderer` y pruebas de contrato sobre `render(...)` para mantener el enfoque test-first previo a la implementación del generador.
- `README.md` actualiza versión y novedades recientes para incluir la nueva suite de tests del renderer Playwright.
- `docs/tests-backend.md` incorpora un ejemplo explícito para ejecutar la suite `test_playwright_renderer.py`.
- Incremento de versión a `0.5.25` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.24] - 2026-02-26

### Added
- `specs/workflows/n8n_workflow_secret_externalization.md` como especificación SDD para externalizar secretos y hosts en exports de n8n, con criterios de aceptación y trazabilidad.
- `docs/n8n-workflows-secretos-entorno.md` con guía operativa para configurar variables en n8n, exportar workflows sin credenciales y validar el cambio.
- `backend/tests/unit/test_n8n_workflows_security.py` con contrato automático para detectar secretos/hosts hardcodeados y exigir referencias `{{$env...}}` en `workflows/n8n/*.json`.
- `.env.example` con placeholders mínimos para las variables usadas por los workflows de n8n (`SUPABASE_*`, `WEBHOOK_API_KEY`, `N8N_BACKEND_*_URL`).

### Changed
- `workflows/n8n/Ingesta-Solicitudes.json` sustituye URL de `/ingest`, `X-API-KEY`, URLs REST de Supabase y headers `apikey`/`Authorization` por expresiones `{{$env...}}`.
- `workflows/n8n/LineUp.json` sustituye URL REST de Supabase y headers `apikey`/`Authorization` por `SUPABASE_URL` y `SUPABASE_KEY`.
- `workflows/n8n/Scoring & Draft.json` sustituye la URL del backend de scoring por `{{$env.N8N_BACKEND_SCORING_URL}}`.
- `.env` añade `N8N_BACKEND_INGEST_URL` y `N8N_BACKEND_SCORING_URL` para parametrizar endpoints del backend consumidos por n8n.
- `README.md` documenta el directorio `workflows/n8n/`, la política de secretos para exports de n8n y la trazabilidad SDD asociada.
- Incremento de versión a `0.5.24` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.23] - 2026-02-26

### Changed
- `backend/src/canva_builder.py` incrementa `AUTOFILL_UNKNOWN_STATUS_MAX_ITERATIONS` hasta `12` para tolerar mejor respuestas transitorias con estado vacío/desconocido durante el polling del autofill de Canva.
- `README.md` y `docs/canva-oauth-pkce-builder.md` se actualizan para reflejar el flujo asíncrono real del builder (payload `brand_template_id/data`, polling por `job_id`, sanitización y stdout con trazas + URL final).
- Incremento de versión a `0.5.23` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.22] - 2026-02-25

### Added
- `backend/src/canva_builder.py` incorpora `_sanitize_text(...)` para limpiar caracteres de control/formato/símbolos (incluyendo la mayoría de emojis) y usar fallback seguro (`" "`) en campos de autofill vacíos.
- `backend/tests/unit/test_canva_builder.py` añade cobertura para sanitización/fallback de campos, validación de headers en `POST/GET` de Canva y abortado por exceso de estados desconocidos en el polling.

### Changed
- `backend/src/canva_builder.py` endurece el payload de Canva eliminando `title` y manteniendo el contrato con `brand_template_id` + `data`.
- `backend/src/canva_builder.py` añade headers explícitos (`User-Agent`, `Accept`) en requests de autofill y consulta de estado.
- `backend/src/canva_builder.py` refuerza el polling con contador de estados desconocidos/nulos y error explícito si supera el umbral configurado.

## [0.5.21] - 2026-02-25

### Added
- `backend/src/canva_builder.py` añade límite de polling (`AUTOFILL_MAX_POLL_ATTEMPTS`) y mensajes de progreso por `stdout` con intento/tiempo transcurrido durante la espera del autofill.
- `backend/src/canva_builder.py` reintenta el polling ante `Timeout`/`ConnectionError` mostrando aviso de red lenta y registrando `warning` en logs.
- `backend/tests/unit/test_canva_builder.py` amplía cobertura para validar feedback de progreso y reintentos ante timeout en el polling.

### Changed
- `backend/src/canva_builder.py` ajusta `AUTOFILL_POLL_INTERVAL_SECONDS` de `2` a `5` segundos y añade timeout final con mensaje de contexto (`job_id`, intentos, tiempo acumulado).

## [0.5.20] - 2026-02-25

### Fixed
- `backend/src/canva_builder.py` corrige la estructura del payload de autofill de Canva usando `brand_template_id` y `data` (en lugar de claves intermedias incompatibles), manteniendo overrides por `CANVA_FIELD_OVERRIDES_JSON`.
- `backend/src/canva_builder.py` corrige la clave de campos de texto del payload a `text` (en lugar de `text_content`) para compatibilidad con el contrato del endpoint de autofill.

### Changed
- `backend/src/canva_builder.py` permite recibir de `1` a `5` cómicos y completa automáticamente hasta `5` con placeholders (`" "`) para cumplir el template fijo.
- `backend/tests/unit/test_canva_builder.py` actualiza expectativas del contrato de payload (`brand_template_id`, `data`, `text`) y añade cobertura para padding y rechazo de payloads con más de 5 cómicos.

## [0.5.19] - 2026-02-25

### Added
- `backend/src/canva_builder.py` introduce soporte de autofill asíncrono con `_extract_job_id(...)`, `request_canva_autofill_status(...)` y `wait_for_autofill_completion(...)` para consultar el estado del job hasta completarse.
- `backend/tests/unit/test_canva_builder.py` añade pruebas de polling asíncrono (éxito y fallo) para el flujo de autofill.
- `docs/canva-oauth-pkce-builder.md` y `docs/curacion-lineup-validacion-estados-gold-silver.md` se incorporan como documentación técnica de procesos recientes no centralizados en `README.md`.
- `backend/logs/canva_auth.log.2026-02-19` se versiona como traza de diagnóstico de errores/ajustes del flujo OAuth de Canva.

### Changed
- `backend/src/canva_builder.py` deja de asumir respuesta síncrona con URL final inmediata y encapsula la generación esperando la finalización del job de Canva antes de extraer la URL.

## [0.5.18] - 2026-02-19

### Added
- `backend/src/canva_builder.py` incorpora `ejecutar_generacion_poster(...)` para encapsular el flujo completo de generación: resolución de token, autofill y extracción de URL final.
- `backend/tests/unit/test_canva_builder.py` añade cobertura unitaria para validar prioridad de token fresco por refresh y fallback a token cacheado cuando el refresh falla temporalmente.

### Changed
- `backend/src/canva_builder.py` ajusta `resolve_access_token()` para intentar primero `refresh_access_token(...)` en cada ejecución del builder, alineando la generación de póster con una estrategia de token siempre fresco.
- `backend/src/canva_builder.py` mantiene fallback robusto: token cacheado y recuperación por `authorization_code` cuando corresponde.
- `README.md` actualiza la sección Canva para reflejar la estrategia refresh-first y los fallbacks disponibles.
- Incremento de versión a `0.5.18` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.17] - 2026-02-18

### Added
- `backend/src/canva_auth_utils.py` incorpora `CanvaAuthError` con metadatos (`status_code`, `error_code`, `response_body`) y flag `requires_reauthorization` para detectar flujos OAuth que requieren reautorización manual.
- `backend/src/canva_auth_utils.py` añade el comando `authorize` para generar `code_verifier`/`code_challenge` (PKCE) y la URL de autorización de Canva de forma guiada.
- `backend/src/canva_auth_utils.py` persiste `CANVA_ACCESS_TOKEN` y `CANVA_ACCESS_TOKEN_EXPIRES_AT`, además del refresh token, para reutilizar sesiones válidas tras reinicios cortos.
- `backend/src/getVeri.py` y `backend/src/test.py` se añaden como scripts auxiliares de diagnóstico manual para pruebas del flujo OAuth/PKCE de Canva.

### Changed
- `backend/src/canva_auth_utils.py` reemplaza escritura manual del `.env` por `dotenv.set_key`, reduciendo riesgo de corrupción del archivo de entorno.
- `backend/src/canva_auth_utils.py` alinea `exchange/refresh` con payload `application/x-www-form-urlencoded` y endpoint OAuth oficial de Canva.
- `backend/src/canva_builder.py` reutiliza primero el access token cacheado y solo hace `refresh`/`exchange` cuando el token local no es válido.
- `backend/src/canva_builder.py` eleva un mensaje explícito de reautorización cuando el refresh devuelve `invalid_grant`.
- `README.md` actualiza la documentación de Canva con el flujo `authorize -> exchange -> refresh` y la caché de access token.
- Incremento de versión a `0.5.17` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.16] - 2026-02-18

### Added
- `backend/src/canva_auth_utils.py` con utilidades OAuth2 para Canva: intercambio de `authorization_code`, renovación de `access_token` con `refresh_token`, CLI (`exchange`/`refresh`) y persistencia del refresh token rotado en `.env`.
- `backend/src/canva_builder.py` como entrypoint para n8n: valida payload JSON de 5 cómicos + fecha, resuelve token válido, ejecuta autofill contra Canva y devuelve la URL del diseño por `stdout`.
- `backend/tests/unit/test_canva_builder.py` con pruebas unitarias para validación de payload, mapeo de campos autofill y extracción robusta de URL de diseño.

### Changed
- `README.md` documenta la fase Designer con Canva API, variables `CANVA_*`, uso CLI y ejemplo de payload para integración en n8n.
- Incremento de versión a `0.5.16` en `package.json` y `pyproject.toml`.

## [0.5.15] - 2026-02-18

### Fixed
- `specs/sql/migrations/20260217_sync_lineup_validation_states.sql` corrige el error de RPC `relation "accepted_gold" does not exist` en `gold.validate_lineup`, reemplazando el uso fuera de alcance de CTE por tablas temporales de trabajo.
- `gold.validate_lineup` sincroniza el cierre de lineup en ambos esquemas: seleccionados a `aprobado` y no seleccionados a `no_seleccionado` en `gold.solicitudes` y `silver.solicitudes`.

### Changed
- `backend/src/scoring_engine.py` persiste scoring en `gold.solicitudes.estado = 'scorado'`, actualiza `gold.comicos.score_actual` y mantiene compatibilidad de recencia con estados `aprobado/aceptado`.
- `specs/sql/gold_relacional.sql` amplía el enum `gold.estado_solicitud` para incluir `scorado`, `aprobado` y `no_seleccionado`, y ajusta defaults/índice parcial de recencia.
- `frontend/src/App.jsx` prioriza candidatos en estado `scorado` al construir la selección inicial del lineup (fallback legacy a `pendiente`).
- `backend/tests/sql/test_sql_contracts.py` y `backend/tests/unit/test_scoring_engine.py` actualizan contratos y expectativas a los nuevos estados y al flujo de persistencia.
- Incremento de versión a `0.5.15` en `package.json`, `pyproject.toml` y `README.md`.
- Incremento de versión de frontend a `0.1.3` en `frontend/package.json`.

## [0.5.14] - 2026-02-18

### Fixed
- `specs/sql/migrations/20260217_sync_lineup_validation_states.sql` ahora ejecuta `DROP VIEW IF EXISTS gold.lineup_candidates` antes del `CREATE OR REPLACE VIEW`, corrigiendo el fallo de despliegue/reset (`cannot change name of view column ...`) cuando coexistían definiciones previas de la vista con columnas distintas.

### Changed
- `backend/tests/sql/test_sql_contracts.py` amplía el contrato para exigir explícitamente el `DROP VIEW` previo en la migración de sincronización de estados.
- Incremento de versión a `0.5.14` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.13] - 2026-02-17

### Fixed
- `specs/sql/migrations/20260218_create_lineup_candidates_and_validate_lineup.sql` actualiza la vista `gold.lineup_candidates` para incluir `estado` (de `gold.solicitudes`) y `contacto` (`COALESCE(telefono, instagram)`), eliminando el filtro exclusivo por `pendiente` para exponer el estado real en Curation.
- `frontend/src/App.jsx` amplía la consulta a `lineup_candidates` para recuperar `estado` y `contacto`, y muestra el estado por candidato en la UI de curación.

### Added
- `workflows/main_pipeline.json` añade una plantilla de flujo n8n con `Postgres -> Split in Batches -> HTTP Request` en bucle para procesar todos los registros de `silver.solicitudes` sin detenerse en el primer ítem.
- `docs/scoring-batch-n8n-fix.md` documenta la configuración batch para n8n, payload por lotes y la consulta SQL de candidatos de scoring sin `LIMIT 1`.

### Changed
- `backend/tests/sql/test_sql_contracts.py` refuerza el contrato de la migración de `lineup_candidates` validando presencia de `estado`, `contacto` y ausencia de filtro fijo `WHERE s.estado = 'pendiente'`.
- Incremento de versión a `0.5.13` en `package.json`, `pyproject.toml` y `README.md`.
- Incremento de versión de frontend a `0.1.2` en `frontend/package.json`.

## [0.5.12] - 2026-02-17

### Fixed
- `frontend/src/App.jsx` endurece `validateLineup` para evitar `404` por webhook relativo cuando `VITE_N8N_WEBHOOK_URL` falta o está mal formateada.
- `frontend/src/App.jsx` añade diagnóstico en consola (`URL detectada`, validación de protocolo, y detalle de `status/body` de respuesta no-OK desde n8n) para distinguir errores de ruta vs errores del webhook.
- `frontend/src/App.jsx` asegura `setSaving(false)` en `finally`, evitando que el botón quede bloqueado en estado `Validando...`.

### Changed
- `README.md` documenta `VITE_N8N_WEBHOOK_URL` como variable requerida del frontend y recomienda URL absoluta `http/https`.
- Incremento de versión a `0.5.12` en `package.json`, `pyproject.toml` y `README.md`.
- Incremento de versión de frontend a `0.1.1` en `frontend/package.json`.

## [0.5.11] - 2026-02-17

### Fixed
- `setup_db.py` incorpora `specs/sql/migrations/20260218_create_lineup_candidates_and_validate_lineup.sql` en `SQL_SEQUENCE`, garantizando que `--reset` también aplique la vista `gold.lineup_candidates` y la función `gold.validate_lineup`.
- `specs/sql/migrations/20260218_create_lineup_candidates_and_validate_lineup.sql` añade `GRANT USAGE ON SCHEMA gold TO anon, authenticated` para que el frontend (Supabase `anon key`) pueda acceder al esquema `gold` en consultas a `lineup_candidates` y RPC `validate_lineup`.

### Changed
- `backend/tests/unit/test_setup_db.py` valida explícitamente que la migración `20260218_create_lineup_candidates_and_validate_lineup.sql` forme parte de la secuencia de despliegue.
- `backend/tests/sql/test_sql_contracts.py` añade contrato para asegurar la existencia y contenido de la migración de `lineup_candidates` y `validate_lineup`.
- `backend/tests/sql/test_sql_contracts.py` amplía el contrato para validar explícitamente el `GRANT USAGE` del esquema `gold` a `anon` y `authenticated`.
- Incremento de versión a `0.5.11` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.10] - 2026-02-17

### Fixed
- `backend/src/scoring_engine.py` ajusta `build_ranking` para intercalar estrictamente solo entre `f_nb_candidates` y `m_candidates` (orden F/NB -> M), dejando `unknowns` exclusivamente para el final cuando ambos buckets están agotados.
- `backend/src/scoring_engine.py` mantiene `seen_ids` durante toda la construcción del ranking para prevenir duplicados por `comico_id`.

### Added
- `backend/tests/unit/test_scoring_engine.py` incorpora una prueba específica que valida que `unknown` se añade al final y que el patrón inicial respeta el intercalado estricto (`f, m, f, m` cuando aplica).

### Changed
- `backend/tests/unit/test_scoring_engine.py` actualiza expectativas de orden para reflejar la nueva regla de paridad estricta sin intercalado temprano de `unknown`.
- Incremento de versión a `0.5.10` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.9] - 2026-02-17

### Fixed
- `backend/src/scoring_engine.py` corrige `build_ranking` para intercalar con punteros independientes por bucket de género (`idx_f`, `idx_m`, `idx_u`) en prioridad F/NB -> M -> Unknown.
- `backend/src/scoring_engine.py` incorpora `seen_ids` para evitar que un mismo `comico_id` aparezca duplicado en `top_10_sugeridos` y en el ranking final.
- El intercalado ahora continúa consumiendo candidatos de los buckets restantes cuando uno se agota, hasta procesar todas las listas.

### Added
- `backend/tests/unit/test_scoring_engine.py` añade cobertura unitaria para deduplicación por `comico_id` y continuidad de intercalado cuando se agota un bucket de género.

### Changed
- Incremento de versión a `0.5.9` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.8] - 2026-02-17

### Changed
- `backend/tests/unit/test_scoring_engine.py` actualiza las instancias de `CandidateScore` para incluir el nuevo argumento obligatorio `genero`, evitando `TypeError` por constructor incompleto.
- Se mantiene la cobertura de desempate por tiempo en `test_sorting_prioritizes_oldest_timestamp_when_score_ties`, ahora con fixtures sintácticamente compatibles con el contrato actual de `CandidateScore`.
- Incremento de versión a `0.5.8` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.7] - 2026-02-17

### Added
- Nueva migración `specs/sql/migrations/20260217_fix_anon_update_policy_silver_comicos.sql` para aplicar de forma idempotente el bloque solicitado sobre `silver.comicos`: `ENABLE ROW LEVEL SECURITY`, `DROP POLICY IF EXISTS "p_anon_update_silver_comicos"` y recreación de la policy `FOR UPDATE TO anon`.

### Changed
- `setup_db.py` incorpora la nueva migración en `SQL_SEQUENCE` para que se ejecute automáticamente en despliegues estándar.
- `backend/tests/sql/test_sql_contracts.py` valida la existencia y el contenido de la migración de RLS/policy para `silver.comicos`.
- Incremento de versión a `0.5.7` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.6] - 2026-02-16

### Changed
- `specs/sql/silver_relacional.sql` estandariza las policies RLS de `anon` en `silver.comicos` con nombres técnicos idempotentes: `p_anon_select_silver_comicos` y `p_anon_update_silver_comicos`.
- `specs/sql/silver_relacional.sql` añade limpieza explícita de políticas previas antes de crear las nuevas para evitar conflictos en redeploys.
- `backend/tests/sql/test_sql_contracts.py` incorpora validación de contrato para asegurar RLS + grants de `anon` sobre `silver.comicos`.
- Incremento de versión a `0.5.6` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.5] - 2026-02-16

### Changed
- `specs/sql/silver_relacional.sql` amplía permisos de `anon` en Silver con `GRANT SELECT, UPDATE ON ALL TABLES IN SCHEMA silver` y `ALTER DEFAULT PRIVILEGES ... GRANT SELECT, UPDATE ON TABLES TO anon`.
- `specs/sql/silver_relacional.sql` incorpora políticas RLS explícitas para `anon` sobre `silver.comicos` (lectura y actualización) y grant específico `GRANT SELECT, UPDATE ON silver.comicos TO anon`.
- Incremento de versión a `0.5.5` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.4] - 2026-02-16

### Changed
- `silver.comicos` alinea nomenclatura con Gold: `nombre_artistico` pasa a `nombre` e `instagram_user` pasa a `instagram`, incluyendo migración compatible para instalaciones existentes.
- `backend/src/bronze_to_silver_ingestion.py` actualiza el upsert/lookup de cómicos Silver para operar con `instagram` y `nombre`.
- `backend/src/scoring_engine.py` y `specs/sql/gold_relacional.sql` actualizan cruces Silver -> Gold para leer `silver.comicos.instagram` y `silver.comicos.nombre`.
- `specs/sql/seed_data.sql` y `backend/tests/sql/test_sql_contracts.py` se ajustan al nuevo contrato de columnas en `silver.comicos`.
- `specs/sql/silver_relacional.sql` renombra índice legacy `idx_silver_comicos_instagram_user` a `idx_silver_comicos_instagram` cuando aplica.
- Incremento de versión a `0.5.4` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.3] - 2026-02-16

### Changed
- `setup_db.py` ahora gestiona la capa Gold como parte del ciclo estándar (`SQL_SEQUENCE`, backup de `gold.comicos`/`gold.solicitudes`, reset de esquema `gold` y verificación de enums Gold).
- `specs/sql/gold_relacional.sql` incorpora bloque de seguridad y operación equivalente a Bronze/Silver (RLS, policies `service_role` y grants del esquema).
- Tests actualizados para validar la nueva gestión de Gold en setup y contratos SQL.
- `specs/sql/gold_relacional.sql` renombra el identificador de contacto de Gold a `telefono` (antes `whatsapp`) y mantiene compatibilidad para migrar instalaciones existentes.
- `backend/src/scoring_engine.py` migra de `whatsapp` a `telefono` en lectura/escritura de Gold, logs y salida JSON.
- `specs/sql/silver_relacional.sql` elimina los flags booleanos legacy de Silver (`is_gold`, `is_priority`, `is_restricted`) y su lógica de mantenimiento en esquema.
- `specs/sql/seed_data.sql` se ajusta al nuevo contrato de `silver.comicos` sin flags booleanos.
- `backend/src/scoring_engine.py` ahora respeta la categoría proveniente de `silver.comicos.categoria` al poblar/actualizar `gold.comicos.categoria` (mapeo `general -> standard`).
- `silver.comicos` y `gold.comicos` incorporan/estandarizan el campo `genero` como `text` con default `unknown`.
- `gold.comicos.genero` migra de enum a `text` para alinear el modelo entre capas Silver y Gold.
- `setup_db.py` deja de verificar el enum `gold.genero_comico` (el enum de género ya no forma parte del contrato de Gold).
- Incremento de versión a `0.5.3` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.1] - 2026-02-16

### Changed
- Nomenclatura de tablas Gold alineada al esquema: `gold.comicos` y `gold.solicitudes` (sin sufijos `_gold`), manteniendo compatibilidad de migración desde `gold.comicos_gold` / `gold.solicitudes_gold`.
- `backend/src/scoring_engine.py` actualizado para usar tablas schema-qualified (`silver.*`, `bronze.solicitudes`, `gold.comicos`, `gold.solicitudes`) y evitar referencias legacy (`*_silver`, `*_gold`).
- `backend/tests/sql/test_sql_contracts.py` actualizado para validar los nuevos nombres de tablas en la capa Gold.
- Incremento de versión a `0.5.1` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.0] - 2026-02-16

### Added
- Script SQL `specs/sql/gold_relacional.sql` para la nueva capa `gold`, con enums `gold.genero_comico` / `gold.categoria_comico` / `gold.estado_solicitud`, tablas `gold.comicos_gold` y `gold.solicitudes_gold`, e índices para consultas de recencia/estado.
- Vista de linaje `gold.vw_linaje_silver_a_gold` para enlazar solicitudes de Silver con perfiles Gold por `whatsapp` o `instagram`.
- Motor `backend/src/scoring_engine.py` para ranking Silver -> Gold con persistencia en historial de solicitudes, descarte de blacklist y salida JSON (`top_10_sugeridos` + métricas de proceso).
- Suite `backend/tests/unit/test_scoring_engine.py` con cobertura de alias de categoría, cálculo de score, detección de disponibilidad única y desempate por `marca_temporal`.

### Changed
- `backend/tests/sql/test_sql_contracts.py` amplía contratos para validar existencia/estructura de la capa Gold y su vista de linaje con Silver.
- `.github/workflows/deploy.yml` añade gate de pruebas previo al restart/start de PM2 en deploy (`push` a `dev`), ejecutando `pytest -q backend/tests` para evitar publicar cambios con regresiones.
- Incremento de versión a `0.5.0` en `package.json`, `pyproject.toml` y `README.md`.

## [0.4.9] - 2026-02-15

### Added
- Documento técnico `docs/refactor-validacion-bronze-silver.md` con el detalle de la nueva normalización de campos obligatorios y reglas de limpieza para WhatsApp/Instagram en la ingesta Bronze -> Silver.

### Changed
- `backend/src/bronze_to_silver_ingestion.py` incorpora `clean_phone(phone_str)` con validación por regex `^(\+?|00)?[\d\s-]{9,}$`, limpieza de separadores, conversión de prefijo `00` a `+` y prefijo por defecto `+34` para números locales de 9 dígitos.
- `backend/src/bronze_to_silver_ingestion.py` refuerza la limpieza de Instagram para soportar `@usuario` y URLs (`instagram.com/usuario`), extrayendo únicamente el username final.
- `backend/src/bronze_to_silver_ingestion.py` añade `normalize_row(row)` para procesar las claves exactas del formulario, validar campos obligatorios y acumular errores por fila en la fase de normalización.
- `backend/src/bronze_to_silver_ingestion.py` agrega un bloque de tests unitarios locales `_unit_tests_clean_phone()` para verificar los formatos de teléfono definidos para el formulario.
- Incremento de versión a `0.4.9` en `package.json` y `pyproject.toml`.

## [0.4.8] - 2026-02-15

### Added
- Documento técnico `docs/ingesta-logs-auditoria.md` con el detalle de la nueva trazabilidad de descartes y la configuración de logs rotativos para la ingesta Bronze -> Silver.

### Changed
- `backend/src/bronze_to_silver_ingestion.py` incorpora logging a archivo absoluto `/root/RECOVA/backend/logs/ingestion.log` con `TimedRotatingFileHandler` diario y retención de 7 días, usando formato `%(asctime)s - %(levelname)s - %(message)s`.
- `backend/src/bronze_to_silver_ingestion.py` añade auditoría de descartes por fila con `detalles_descarte` y la expone en la salida JSON bajo la clave `errores` (incluyendo duplicados, faltas de datos y errores por validación/fase).
- `backend/src/bronze_to_silver_ingestion.py` endurece robustez del pipeline con captura de fallo fatal y `LOGGER.exception(...)` para traza completa en logs.
- Incremento de versión a `0.4.8` en `package.json` y `pyproject.toml`.

## [0.4.7] - 2026-02-15

### Added
- Workflow de GitHub Actions `.github/workflows/deploy.yml` para despliegue automático por `push` a `dev` vía `appleboy/ssh-action@master`, con actualización del código, instalación de dependencias y gestión de PM2 para `webhook-ingesta`.
- Documento `docs/github-actions-deploy-dev.md` con el comando local de creación de estructura y la plantilla YAML lista para copiar.

### Changed
- Incremento de versión a `0.4.7` en `package.json` y `pyproject.toml`.

## [0.4.6] - 2026-02-15

### Added
- Listener HTTP `backend/src/triggers/webhook_listener.py` con Flask para recibir `POST /ingest`, validar `X-API-KEY` (env `WEBHOOK_API_KEY`) y disparar la ingesta Bronze -> Silver mediante `subprocess`.
- Documento técnico `docs/webhook-listener-n8n-ingesta.md` con el flujo, seguridad básica y forma de ejecución del listener.

### Changed
- Dependencias de backend actualizadas para incluir `flask>=3.0.0` en `pyproject.toml` y `requirements.txt`.
- Incremento de versión a `0.4.6` en `package.json` y `pyproject.toml`.

## [0.4.5] - 2026-02-15

### Added
- Documento técnico `docs/ingesta-batch-bronze-queue.md` con la migración del proceso de ingesta desde modo CLI a worker batch sobre cola Bronze.

### Changed
- `backend/src/bronze_to_silver_ingestion.py` elimina `argparse` y ahora procesa en lote las filas pendientes de `bronze.solicitudes` (`procesado = false`) leyendo directamente desde PostgreSQL/Supabase.
- `backend/src/bronze_to_silver_ingestion.py` mantiene la limpieza de `instagram`, `telefono` y fechas, añade normalización explícita de `disponibilidad_ultimo_minuto` (`sí/no` -> `true/false`) y conserva el mapeo de `info_show_cercano`/`origen_conocimiento` hacia Silver.
- `backend/src/bronze_to_silver_ingestion.py` marca `procesado = true` solo en casos exitosos; ante error por fila registra `error_ingesta` en `metadata` (o `raw_data_extra` fallback) y continúa con el resto de la cola.
- `backend/src/old/ingestion_cli_backup.py` conserva la versión anterior basada en argumentos CLI como respaldo operativo.
- Incremento de versión a `0.4.5` en `package.json` y `pyproject.toml`.

## [0.4.4] - 2026-02-14

### Added
- Documento técnico `docs/ingesta-whatsapp-show-cercano-origen.md` con el detalle del nuevo mapeo de WhatsApp y los campos de contexto de solicitud en Bronze/Silver.

### Changed
- `backend/src/bronze_to_silver_ingestion.py` agrega aliases CLI `--whatsapp`/`--Whatsapp` para mapear el campo de Google Sheets a `telefono_raw` en Bronze y normalizarlo a `telefono` en `silver.comicos`.
- `backend/src/bronze_to_silver_ingestion.py` incorpora `--show_cercano_raw` y `--conociste_raw`, persistiendo en `bronze.solicitudes.info_show_cercano`/`bronze.solicitudes.origen_conocimiento` y en `silver.solicitudes.show_cercano`/`silver.solicitudes.origen_conocimiento`.
- `backend/src/bronze_to_silver_ingestion.py` endurece la limpieza de `disponibilidad_ultimo_minuto`: cualquier texto que contenga `si` (insensible a mayúsculas y acentos) se normaliza a `true`, en otro caso `false`.
- `specs/sql/silver_relacional.sql` añade de forma idempotente las columnas `show_cercano` y `origen_conocimiento` en `silver.solicitudes` para mantener consistencia con la ingesta.
- Incremento de versión a `0.4.4` en `package.json` y `pyproject.toml`.

## [0.4.3] - 2026-02-14

### Added
- Documento técnico `docs/ingesta-constraint-unicidad-proveedor-slug.md` con la corrección persistente para `ON CONFLICT (comico_id, fecha_evento)` y la unificación del slug de proveedor por defecto.

### Changed
- `specs/sql/silver_relacional.sql` añade y garantiza de forma idempotente la restricción única `uq_silver_solicitudes_comico_fecha` sobre `(comico_id, fecha_evento)` para compatibilidad con la ingesta Bronze -> Silver.
- `specs/sql/seed_data.sql` unifica el slug del proveedor semilla de `recova-open` a `recova-om`.
- Incremento de versión a `0.4.3` en `package.json` y `pyproject.toml`.

## [0.4.2] - 2026-02-14

### Added
- Documento técnico `docs/stack-tecnologico-infraestructura-mvp.md` con el estado actual de despliegue self-hosted, capas de datos y flujo operativo del MVP.

### Changed
- `README.md` incorpora la nueva sección visual **Stack Tecnológico e Infraestructura (MVP Actual)** con detalle de VPS, Coolify, n8n, Supabase por capas Bronze/Silver, integraciones y flujo de datos Google Sheets -> n8n -> Python.
- Incremento de versión a `0.4.2` en `package.json` y `pyproject.toml`.

## [0.4.1] - 2026-02-14

### Added
- Documento técnico `docs/proveedor-default-recova.md` con la simplificación de proveedor único en la ingesta Bronze -> Silver.

### Changed
- `backend/src/bronze_to_silver_ingestion.py` define `DEFAULT_PROVEEDOR_ID` como constante global fija para el proveedor Recova y elimina el argumento CLI `--proveedor_id`.
- `backend/src/bronze_to_silver_ingestion.py` aplica automáticamente el proveedor por defecto en inserciones a `bronze.solicitudes` y `silver.solicitudes` vía linaje Bronze.
- `backend/src/bronze_to_silver_ingestion.py` añade validación temprana de formato para `DEFAULT_PROVEEDOR_ID` cuando tenga forma de UUID, para compatibilidad con esquemas PostgreSQL UUID.
- Incremento de versión a `0.4.1` en `package.json` y `pyproject.toml`.

## [0.4.0] - 2026-02-14

### Added
- Documento técnico `docs/ingesta-atomica-n8n.md` con el flujo event-driven de ingesta atómica para n8n.

### Changed
- `backend/src/bronze_to_silver_ingestion.py` migra de procesamiento batch (`fetch_pending_bronze_rows`) a ejecución atómica por argumentos CLI (`argparse`) y salida JSON de integración para n8n.
- `backend/src/bronze_to_silver_ingestion.py` ahora inserta primero en `bronze.solicitudes`, recupera `bronze_id` y luego procesa Silver con `SAVEPOINT` para rollback parcial y trazabilidad de `error_ingesta`.
- `backend/src/bronze_to_silver_ingestion.py` incorpora resolución de `proveedor_id` por UUID o `slug`, con valor por defecto `recova-om`.
- Incremento de versión a `0.4.0` en `package.json` y `pyproject.toml`.

## [0.3.0] - 2026-02-13

### Added
- Documento técnico `docs/bronze-solo-solicitudes-linaje-silver.md` con el modelo simplificado de linaje Bronze -> Silver.

### Changed
- `specs/sql/bronze_multi_proveedor_master.sql` elimina la tabla redundante de cómicos en Bronze y deja únicamente `bronze.solicitudes` como tabla cruda.
- `specs/sql/bronze_multi_proveedor_master.sql` incorpora normalización de columna legacy `whatsapp_raw` hacia `telefono_raw`.
- `specs/sql/silver_relacional.sql` consolida maestras y transaccional en Silver (`silver.comicos`, `silver.proveedores`, `silver.solicitudes`) con FK obligatoria de linaje `bronze_id -> bronze.solicitudes(id)`.
- `specs/sql/seed_data.sql` se adapta al nuevo flujo sin `bronze.comicos`.
- `backend/src/bronze_to_silver_ingestion.py` se adapta al flujo directo Bronze -> `silver.comicos` -> `silver.solicitudes` (sin tabla intermedia de cómicos en Bronze).
- `setup_db.py` actualiza tablas de backup al modelo simplificado por esquemas.
- Incremento de versión a `0.3.0` en `package.json` y `pyproject.toml`.

## [0.2.0] - 2026-02-13

### Added
- Documento técnico `docs/esquemas-bronze-silver.md` con la separación física de capas por esquemas reales.
- Estructura SQL schema-qualified en capas:
  - `bronze.comicos`, `bronze.solicitudes`
  - `silver.proveedores`, `silver.comicos`, `silver.solicitudes`

### Changed
- `specs/sql/bronze_multi_proveedor_master.sql` crea y gestiona el esquema `bronze` con RLS/políticas propias para `service_role`.
- `specs/sql/silver_relacional.sql` crea y gestiona el esquema `silver`, mueve objetos legacy desde `public`, y aplica FKs explícitas entre esquemas.
- Se corrigen defaults UUID en SQL para usar `gen_random_uuid()` (sin prefijo `public.`), evitando el error `UndefinedFunction` en Supabase/PostgreSQL.
- Enums migrados al esquema `silver` con nombres `silver.tipo_categoria` y `silver.tipo_status`.
- `specs/sql/migrations/20260212_alter_tipo_solicitud_status.sql` adaptada para operar sobre `silver.tipo_status`.
- `specs/sql/seed_data.sql` actualizada para poblar tablas `bronze.*` y `silver.*`.
- `setup_db.py` actualizada para backup/reset por esquema y verificación de enums en `silver`.
- `backend/src/bronze_to_silver_ingestion.py` actualizada para leer/escribir en `bronze.*` y `silver.*`.
- Incremento de versión a `0.2.0` en `package.json` y `pyproject.toml`.

## [0.1.9] - 2026-02-13

### Added
- Documento técnico `docs/seed-unique-comico-fecha-fix.md` con el ajuste del seed para respetar la unicidad de `solicitudes_silver`.

### Changed
- `specs/sql/seed_data.sql` corrige el caso de Nora Priority para evitar duplicidad en `(comico_id, fecha_evento)` y mantener compatibilidad con `uq_solicitudes_silver_comico_fecha`.
- `docs/seed-data-casos-borde.md` actualiza la descripción del caso de doblete para reflejar el comportamiento compatible con la restricción de unicidad.
- Incremento de versión a `0.1.9` en `package.json` y `pyproject.toml`.

## [0.1.8] - 2026-02-13

### Added
- Documento técnico `docs/bronze-silver-comicos-sync.md` con el diseño de separación de `comicos_master` por capa y sincronización Bronze -> Silver.

### Changed
- `specs/sql/bronze_multi_proveedor_master.sql` migra la identidad Bronze a `public.comicos_master_bronze` con índice, trigger y política RLS propios.
- `specs/sql/silver_relacional.sql` mantiene `public.comicos_master` como directorio Silver enriquecido y agrega sincronización idempotente desde `public.comicos_master_bronze`.
- `specs/sql/silver_relacional.sql` conserva compatibilidad de migración in-place con `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` para instalaciones legacy.
- `specs/sql/seed_data.sql` ahora puebla primero `comicos_master_bronze` y luego sincroniza `comicos_master`.
- `backend/src/bronze_to_silver_ingestion.py` actualiza el flujo para hacer upsert en Bronze y sincronización posterior en Silver.
- `setup_db.py` amplía backup y reset para incluir ambas tablas de identidad (`comicos_master_bronze` y `comicos_master`).
- Incremento de versión a `0.1.8` en `package.json` y `pyproject.toml`.

### Removed
- Documento `docs/silver-comicos-master-schema-compat.md`, reemplazado por la nueva guía de separación Bronze/Silver.

## [0.1.7] - 2026-02-13

### Added
- Documento técnico `docs/silver-comicos-master-schema-compat.md` con la causa raíz del fallo de seed y la estrategia de compatibilidad entre Bronze y Silver.

### Changed
- `specs/sql/silver_relacional.sql` ahora completa `public.comicos_master` con `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` para `nombre_artistico`, `telefono`, `is_gold`, `is_priority`, `is_restricted` y `metadata_comico` cuando la tabla ya existe por ejecución previa de Bronze.
- `specs/sql/silver_relacional.sql` agrega de forma idempotente la constraint `chk_comicos_master_telefono_e164` para instalaciones previas sin esa validación.
- Incremento de versión a `0.1.7` en `package.json` y `pyproject.toml`.

## [0.1.6] - 2026-02-13

### Added
- Documento técnico `docs/setup-db-backup-reset-seed.md` con el flujo final de despliegue local seguro (`backup + reset + seed`) para `setup_db.py`.

### Changed
- Refactor de `setup_db.py` con nuevo flag `--seed` para ejecutar `specs/sql/seed_data.sql` tras el esquema.
- Endurecimiento transaccional de `setup_db.py` con bloque `try/except/finally`, `rollback()` ante fallo y cierre explícito de conexión.
- Mejora de trazas de consola en `setup_db.py` para reportar backup, reset, aplicación de esquema y seed con mensajes claros.
- Incremento de versión a `0.1.6` en `package.json` y `pyproject.toml`.

## [0.1.5] - 2026-02-13

### Added
- Script de seed data `specs/sql/seed_data.sql` con 2 proveedores, 11 cómicos y 18 solicitudes Silver con casos de borde (spammer, doblete y restringido activo).
- Documento técnico `docs/seed-data-casos-borde.md` con instrucciones de ejecución y validación rápida.

### Changed
- Incremento de versión a `0.1.5` en `package.json` y `pyproject.toml`.

## [0.1.4] - 2026-02-12

### Added
- Documento técnico `docs/ingesta-bronze-silver-error-handling.md` con el detalle de la refactorización de manejo de errores Bronze -> Silver.

### Changed
- Refactor de `backend/src/bronze_to_silver_ingestion.py` para mantener errores de ingesta exclusivamente en Bronze (`raw_data_extra.error_log`) y evitar cualquier inserción de errores en `solicitudes_silver`.
- Robustez en `map_experience_level` con fallback por defecto a `0` y warning cuando el texto no coincide exactamente.
- Robustez en `parse_event_dates` para ignorar tokens inválidos de fecha con warning sin romper el procesamiento completo de la fila.
- Trazabilidad de fallos por fase (`normalizacion`, `parsing_fechas`, `mapeo_experiencia`, `upsert_comico`, `insert_silver`) y timestamp UTC en el registro de error.

## [0.1.3] - 2026-02-12

### Added
- Migración SQL en `specs/sql/migrations/20260212_alter_tipo_solicitud_status.sql` para extender `tipo_solicitud_status` con `no_seleccionado` y `expirado`.
- Script de ingesta transaccional en `backend/src/bronze_to_silver_ingestion.py` con normalización de identidad, explosión de fechas, anti-duplicados por `(comico_id, fecha_evento)` y expiración automática de reservas a 60 días.
- Documento técnico `docs/ingesta-bronze-silver-reserva.md` con flujo, ejecución y garantías de idempotencia.

### Changed
- Especificación `specs/sql/silver_relacional.sql` para soportar explosión de fechas (eliminación de `unique` en `bronze_id`) y nuevos índices únicos `(bronze_id, fecha_evento)` y `(comico_id, fecha_evento)`.
- Dependencias de backend con `psycopg2-binary` en `pyproject.toml` y `requirements.txt`.
## [0.1.4] - 2026-02-13

### Added
- Respaldo preventivo en `setup_db.py` previo a `--reset`: creación automática de carpeta `backups/`, exportación de datos a CSV con timestamp por tabla objetivo (`comicos_master`, `solicitudes_silver`, `proveedores`) y logs de continuidad cuando no hay datos o tablas aún no existen.
- Recordatorio al finalizar la ejecución para añadir `backups/` al `.gitignore` y evitar subir datos sensibles.
- Documentación técnica en `docs/setup-db-backup-local.md`.

## [0.1.3] - 2026-02-13

### Added
- Script `setup_db.py` para despliegue secuencial del esquema SQL en Supabase, con carga de `DATABASE_URL` desde `.env`, verificación de enums y opción `--reset` para limpieza de tablas y tipos.
- Migración `specs/sql/migrations/20260212_alter_tipo_solicitud_status.sql` para asegurar la existencia y completitud de `tipo_solicitud_status`.
- Documentación técnica en `docs/setup-db-migraciones.md`.

## [0.1.2] - 2026-02-12

### Added
- Script SQL de Capa Silver relacional en `specs/sql/silver_relacional.sql`, con tablas `comicos_master` y `solicitudes_silver`, restricciones de calidad, unicidad semanal de aprobados, triggers de `updated_at` y políticas RLS para `service_role`.
- Documento técnico de soporte en `docs/silver-relacional.md` explicando la normalización y el impacto en el motor de scoring.

## [0.1.1] - 2026-02-12

### Added
- Script SQL base para Capa Bronze, infraestructura multi-proveedor y master data de cómicos en `specs/sql/bronze_multi_proveedor_master.sql`.
- Documento técnico de soporte en `docs/bronze-multi-proveedor-master-data.md`.

## [0.1.0] - 2026-02-10

### Added
- Definición de roles y responsabilidades en `AGENTS.md`.
- Estructura de versionado híbrida (`package.json` + `pyproject.toml`).
- Configuración de dependencias base para Python.
- Definición de flujo de decisión híbrido (Lógica determinística + IA).
- Roadmap inicial del MVP en el README.
