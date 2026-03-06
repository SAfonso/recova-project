# Historial de Sprints y Fases

## Sprint 6 — Ingesta Multi-Tenant + Scripts de Utilidad (v0.11.0) — 2026-03-07 ✅

### Objetivo
Implementar ingesta diaria de solicitudes desde todas las Google Sheets de los open mics (multi-tenant), integrando clasificación de género con Gemini antes del scoring diario. Añadir scripts de utilidad para desarrollo local.

### Completado

#### Ingesta desde Sheets
- **Spec SDD** — `specs/ingest_from_sheets_spec.md`
- **`SheetIngestor`** — `backend/src/core/sheet_ingestor.py`: lee rango A:K, filtra por `n8n_procesado` vacío; marca procesadas con `"si"` en columna K via `batchUpdate`
- **`POST /api/ingest-from-sheets`**: itera `silver.open_mics` con `sheet_id`, ingesta batch multi-tenant, lanza `bronze_to_silver_ingestion.py` en background
- **`POST /api/form-submission`**: ingesta individual desde Apps Script `onFormSubmit`
- **`GoogleFormBuilder`** actualizado: nuevo cliente `script`, `deploy_submit_webhook()`, columna `n8n_procesado` en Sheet

#### n8n
- **`Ingesta-Solicitudes.json`** reescrito: Schedule 09:00 → `POST /api/ingest-from-sheets` → clasificador de género con Gemini (`silver.comicos.genero`)

#### Scripts de utilidad
- **`backend/scripts/seed_conditional.py`**: rellena con 10 cómicos los open mics sin solicitudes
- **`backend/scripts/seed_full.py`**: crea escenario completo (1 proveedor + 3 open mics + 30 cómicos)
- **`backend/scripts/reset_data.py`**: TRUNCATE con backup CSV; flags `--yes`, `--include-auth`, `--no-backup`

#### Tests (TDD)
- `test_form_submission.py`: 7/7
- `test_ingest_from_sheets.py`: 12/12
- `tests/scripts/test_seed_conditional.py`: 7/7
- `tests/scripts/test_seed_full.py`: 8/8
- `tests/scripts/test_reset_data.py`: 9/9

→ Spec: `specs/ingest_from_sheets_spec.md`, `specs/seed_scripts_spec.md`

---

## Sprint 5 — Validación de Lineup via Telegram (v0.10.0) — 2026-03-06 ✅

### Objetivo
Permitir al host validar el lineup desde Telegram sin acceder a la app web: el cron diario genera un link único (token UUID) que abre una vista standalone `/validate` donde puede seleccionar los 5 cómicos y confirmar. La validación queda reflejada en DB y en la app web.

### Completado
- **Spec SDD** — `specs/telegram_validate_lineup_spec.md`
- **Migración SQL** — `silver.validation_tokens`: token UUID, host_id, open_mic_id, fecha_evento, expires_at
- **Backend**:
  - `POST /api/lineup/prepare-validation`: scoring + token + validate_url
  - `GET /api/validate-view/lineup?token=xxx`: candidatos + is_validated
  - `POST /api/validate-view/validate`: confirma lineup via RPCs Gold+Silver, borra token
  - `_next_event_datetime(dia_semana, hora)`: calcula próxima ocurrencia semanal
- **Tests** — `backend/tests/test_validate_lineup_view.py`: 12/12 verdes
- **Frontend** — `ValidateView.jsx`: vista standalone sin auth (token-based), estética papel arrugado, sello VALIDADO animado
- **n8n Scoring & Draft** reconstruido multi-tenant: itera hosts→open_mics, llama prepare-validation, envía lineup+link por Telegram
- **n8n Test BOT** — `Tool_Lineup_Link` conectado al AI Agent: host pide lineup → recibe link de validación
- **Fix** — URL doble `==` en nodo Supabase del Test BOT

→ Spec: `specs/telegram_validate_lineup_spec.md`

---

## Sprint 4b — Telegram Register Endpoint (v0.9.1) — 2026-03-06 ✅

### Objetivo
Cerrar el loop del QR: procesar el mensaje `/start RCV-XXXX` que envía Telegram cuando el host escanea el QR, validar el código y registrar al host en `silver.telegram_users`.

### Completado
- **Spec SDD** — `specs/telegram_register_spec.md`
- **Tests TDD** — `backend/tests/test_telegram_register.py`: 10/10 verdes
- **Endpoint Flask** — `POST /api/telegram/register`: valida código, registra host, idempotente
  - Lógica: código existe → usuario ya registrado? → 200 `already_registered:true`; código usado → 409; expirado → 410; nuevo → INSERT + UPDATE used
- **Idempotencia** — reutilizar el QR no rompe ni duplica el registro

### Completado (continuacion)
- **Workflow n8n** — `workflows/n8n/Test BOT.json` actualizado:
  - `If (¿Registro QR?)`: detecta `/start RCV-` antes del flow existente
  - `HTTP (Register)`: llama `POST /api/telegram/register` con `neverError: true`
  - `If (¿Registro OK?)` + `If (¿Ya registrado?)`: ramifica respuestas
  - Mensajes: "Cuenta conectada." / "Tu cuenta ya estaba conectada." / errores diferenciados

→ Spec: `specs/telegram_register_spec.md`

---

## Sprint 4a — Telegram QR Self-Registration (v0.9.0) — 2026-03-06 ✅

### Objetivo
Permitir al host vincular su cuenta de Telegram sin intervención manual en BD, mediante un código temporal y QR.

### Completado
- **Spec SDD** — `specs/telegram_qr_connect_spec.md`
- **Tests TDD** — `backend/tests/test_telegram_generate_code.py`: 5/5 verdes
- **Endpoint Flask** — `POST /api/telegram/generate-code`: genera `RCV-[A-Z0-9]{4}`, inserta en `silver.telegram_registration_codes`
- **Frontend** — icono Telegram (esquina superior derecha del card), tooltip "¡Click Me!" (localStorage), modal con QR (`qrcode.react`)
- **Variable de entorno** — `TELEGRAM_BOT_USERNAME=ailineup_bot` en servidor

→ Spec: `specs/telegram_qr_connect_spec.md`

---

## Sprint 3 — Telegram Lineup Agent (v0.8.0) — 2026-03-06 ✅

### Objetivo
Permitir al host consultar y gestionar el lineup desde Telegram en lenguaje natural, usando un agente LLM con tools MCP expuestas como endpoints REST.

### Completado
- **Spec SDD** — `specs/telegram_lineup_agent_spec.md`
- **Migración SQL** — `silver.telegram_users` + `silver.telegram_registration_codes`
- **Endpoints Flask `/mcp/*`** — 5 endpoints con auth `X-API-Key`
  - `GET /mcp/open-mics` (query via `organization_members → proveedor_id`)
  - `GET /mcp/lineup`, `GET /mcp/candidates`, `POST /mcp/run-scoring`, `POST /mcp/reopen-lineup`
- **Tests** — 11/11 verdes en `backend/tests/mcp/test_lineup_mcp_endpoints.py`
- **Workflow n8n** — `telegram-lineup-agent` operativo:
  - LLM: Gemini 2.5 Flash
  - Validación host en `silver.telegram_users` → rechazo automático si no registrado
  - 5 tools conectadas al backend Flask
  - Redirección a web si el host no tiene open mics
- **Fix deploy servidor** — `.env` en `/root/RECOVA/.env`, `SUPABASE_SERVICE_KEY` correcta

→ Spec: `specs/telegram_lineup_agent_spec.md`

---

## Sprint 2 — Google Forms + Integración Backend (v0.7.0) — 2026-03-05

### Completado
- **Auto-creación de Google Form** al crear un open mic (fire-and-forget desde `OpenMicSelector`)
- **GoogleFormBuilder con OAuth2** — migración desde service account (las SA tienen quota:0 en Drive)
- **Sheet propia vía Sheets API** — la Forms API no genera `linkedSheetId` por API
- **Columna `open_mic_id`** con ARRAYFORMULA en col J de la Sheet
- **Botón manual fallback** en `OpenMicDetail` para open mics existentes
- **CORS habilitado** en Flask (`flask-cors`)
- **Script de autorización OAuth2** — `backend/scripts/google_oauth_setup.py`
- **`config.form`** en `silver.open_mics.config`: `form_id`, `form_url`, `sheet_id`, `sheet_url`
- **23 tests unitarios** de `GoogleFormBuilder` con mocks de Google APIs
- **Spec v1.1** actualizada con arquitectura real

### Pendiente
- [ ] `confirm_lineup()` RPC → `silver.lineup_slots`
- [ ] Backend del renderer lee `config.poster.base_image_url`
- [ ] n8n webhook post-validación dispara renderer con `open_mic_id`
- [ ] Penalización recencia operativa
- [ ] Deploy frontend en producción

→ Spec: `specs/google_form_autocreation_spec.md`

---

## Sprint 1 — Pivot SaaS Multi-Tenant (v0.6.0) — 2026-03-04

Pivot completo desde sistema single-tenant a arquitectura SaaS multi-tenant.

### Completado
- **Esquema v3 Medallion extendido:** `silver.organization_members`, `silver.open_mics` (config JSONB), `silver.lineup_slots`, `confirm_lineup()` RPC, RLS por host
- **Auth magic link:** Supabase OTP, solo hosts pre-registrados (`shouldCreateUser: false`)
- **Navegación Root:** `Login → OpenMicSelector → OpenMicDetail → App`
- **OpenMicSelector:** lista open mics del host, roles `host`/`collaborator`, solo `host` puede crear
- **OpenMicDetail:** hub del open mic — info + config scoring + form + zona de peligro
- **ScoringConfig** (`scoring_config.py`): lee config JSONB de `silver.open_mics` — **27 tests verdes**
- **Scoring engine v3:** `execute_scoring(open_mic_id)` con recencia scoped por open mic
- **ScoringConfigurator:** componente React para editar config JSONB en tiempo real
- **Ingesta Bronze → Silver v3:** `BronzeRecord` con `open_mic_id`, pipeline v3/legacy bifurcado
- **Aislamiento multi-tenant:** RLS en Silver+Gold, `lineup_candidates` filtra por `open_mic_id`
- **Poster config:** upload de imagen de fondo a Supabase Storage (bucket: `poster-backgrounds`)

---

## Fase SVG Renderer (v0.5.57–0.5.61) — 2026-03-03

Compositor vectorial SVG como alternativa al renderer Playwright.

- **SVGLineupComposer** (`svg_composer.py`): composición nativa SVG `1080x1350` + exportación PNG con CairoSVG
- **Safe Zone Y=400..1100:** distribución equitativa de cómicos con algoritmo adaptativo de `font_size`
- **Modelo híbrido:** `base_poster.png` como capa base + overlay de texto SVG
- **Assets embebidos en Base64:** imagen y fuente TTF embebidos en el SVG para evitar dependencias de rutas `file://`
- **Hardening visual:** orden de capas blindado (`<image>` → `<g id="overlay-text">`), estilos inline

---

## Fase MCP Renderer + Frontend UI (v0.5.33–0.5.56) — 2026-03-01/03

Renderer de carteles via Playwright con servidor HTTP y spec SDD completa.

### MCP Agnostic Renderer Spec (SDD-first, v0.5.33–0.5.38)
- Spec completa del MCP Renderer en `specs/mcp_agnostic_renderer_spec.md` (§1–§14)
- Template catalog: estructura atómica por `template_id` con `manifest.json`
- Jerarquía de resiliencia: `Active Mode` + fallback local a `/catalog/fallback/`
- Filosofía de fallo no bloqueante: `HTTP 200 OK` + `trace.recovery_notes`
- Security Gate: pre-fetch 32 bytes + Magic Bytes (PNG/JPEG/WebP) + bloqueo SSRF

### Implementación TDD (v0.5.39–0.5.56)
- **Security Gate** (`security.py`): tests primero → implementación. HTTPS-only, bloqueo RFC1918
- **Data Binder** (`data_binder.py`): binding `lineup[n].name → .slot-(n+1) .name`, FitText, `window.renderReady`
- **Render core** (`render.py`): Playwright agnóstico con `--no-sandbox`, espera `renderReady`, cierre garantizado
- **MCP Server** (`mcp_server.py`): FastAPI HTTP en `:5050`, `POST /tools/render_lineup`, `asyncio.Lock` para serializar renders, logging en `backend/logs/mcp_render.log`
- **Jinja2 server-side:** `template.html` renderizado antes de Playwright (elimina Data Binder en flujo MCP)
- **Frontend UI notebook/cartoon** (v0.5.50): componentes `Header`, `NotebookSheet`, `ExpandedView`, `ComicCard`, `ValidateButton` con estilos `paint-bg`/`notebook-lines`
- **Regla del Espejo:** consolidación de tests para evitar `import file mismatch` en CI
- **PM2:** `ecosystem.config.js` para persistencia de procesos en VPS

---

## Fase Playwright Renderer v1 (v0.5.25–0.5.32) — 2026-02-26/27

Primera implementación del renderer de carteles con Playwright + Supabase Storage.

- **PlaywrightRenderer TDD** (`playwright_renderer.py`): spec-first — tests antes de implementación, contrato MCP-ready, normalización/truncado de nombres, warning `LINEUP_UNDER_MINIMUM`
- **Template `lineup_v1.html`**: diseño Dark Premium (Bebas Neue, gradientes, hasta 8 slots nombre+instagram)
- **Supabase Storage:** upload a bucket `posters` con naming `YYYY-MM-DD/lineup_{request_id}.png`, limpieza del PNG temporal post-upload
- **Flask API** (`app.py`): `POST /render-lineup`, validación de payload SDD §2.2, respuesta con `public_url`
- **Chromium headless:** flags `--no-sandbox`, `--disable-setuid-sandbox`, `--disable-dev-shm-usage` para entorno root/VPS; fallback `_DummyBrowser` cuando Playwright no puede arrancar
- **Hardening secretos n8n** (v0.5.32): workflows `LineUp.json`, `Ingesta-Solicitudes.json`, `Scoring & Draft.json` migran URLs y API keys a variables `$env.*`; `.env.example` con placeholders

---

## Fase Canva Integration (v0.5.16–0.5.24) — 2026-02-25/26 *(deprecada)*

Integración con Canva API para generación de carteles — reemplazada por motor Playwright propio.

- **`canva_auth_utils.py`**: OAuth2 PKCE flow completo (authorize → exchange → refresh), CLI `authorize`/`exchange`/`refresh`, persistencia de tokens en `.env` con `dotenv.set_key`
- **`canva_builder.py`**: entrypoint para n8n — valida payload (5 cómicos + fecha), resuelve token (refresh-first), ejecuta autofill contra Canva API, devuelve URL por stdout
- **Autofill asíncrono**: polling por `job_id` con reintentos ante timeout/ConnectionError, límite de intentos, feedback de progreso
- **Sanitización**: `_sanitize_text()` limpia caracteres de control/emojis; padding automático a 5 slots con `" "`
- **Hardening secretos n8n** (v0.5.24): spec SDD + test automático para detectar secretos hardcodeados en `workflows/n8n/*.json`

---

## Fase Ingesta + Infraestructura (v0.4.0–0.4.9) — 2026-02-14/15

Maduración del pipeline de ingesta y despliegue en producción.

- **Ingesta atómica para n8n** (v0.4.0): migración de batch a CLI atómico con `argparse`, inserta primero en Bronze con `SAVEPOINT` y rollback parcial por fila
- **Proveedor default** (v0.4.1): `DEFAULT_PROVEEDOR_ID` constante global, elimina argumento CLI; unicidad `(comico_id, fecha_evento)` con constraint idempotente
- **Webhook listener** (v0.4.6): Flask `POST /ingest` con validación `X-API-KEY`, arranca ingesta vía `subprocess`
- **GitHub Actions deploy** (v0.4.7): `.github/workflows/deploy.yml` — push a `dev` → SSH → PM2 restart de `webhook-ingesta`; gate de pytest previo al deploy (v0.5.0)
- **Ingesta batch sobre cola Bronze** (v0.4.5): vuelta a modo batch procesando `bronze.solicitudes WHERE procesado = false`; error por fila en `metadata.error_ingesta`
- **Logs rotativos y auditoría** (v0.4.8): `TimedRotatingFileHandler` diario, retención 7 días, `detalles_descarte` en salida JSON
- **Normalización WhatsApp/Instagram** (v0.4.9): `clean_phone()` con regex E.164, prefijo `+34` por defecto; extracción de username desde URL de Instagram

---

## Fase Bronze + Silver + Seed (v0.1.0–0.3.0) — 2026-02-10/13

Construcción desde cero del esquema Medallion y el pipeline de ingesta.

### Proyecto inicial (v0.1.0)
- `AGENTS.md`: roles y responsabilidades del sistema
- Estructura de versionado híbrida (`package.json` + `pyproject.toml`)
- Roadmap inicial del MVP

### Esquema SQL Bronze + Silver (v0.1.1–0.1.2)
- **Capa Bronze** (`bronze_multi_proveedor_master.sql`): infraestructura multi-proveedor, master data de cómicos
- **Capa Silver** (`silver_relacional.sql`): tablas `comicos_master` y `solicitudes_silver`, restricciones de calidad, unicidad semanal de aprobados, RLS `service_role`

### Ingesta Bronze → Silver v1 (v0.1.3–0.1.4)
- **`bronze_to_silver_ingestion.py`**: normalización de identidad, explosión de fechas, anti-duplicados `(comico_id, fecha_evento)`, expiración de reservas a 60 días
- **`setup_db.py`**: despliegue secuencial de SQL, opción `--reset`, backup automático a CSV con timestamp, flag `--seed`
- **Seed data** (v0.1.5): 2 proveedores, 11 cómicos, 18 solicitudes con casos de borde (spammer, doblete, restringido)

### Schemas por esquema real (v0.2.0)
- Separación física Bronze/Silver en esquemas `bronze.*` y `silver.*` (antes en `public.*`)
- Enums migrados a `silver.tipo_categoria` / `silver.tipo_status`
- `setup_db.py` y `bronze_to_silver_ingestion.py` actualizados a tablas schema-qualified

### Simplificación del linaje (v0.3.0)
- Eliminación de `bronze.comicos` — solo `bronze.solicitudes` como tabla cruda
- FK obligatoria `bronze_id → bronze.solicitudes(id)` en Silver
- Consolidación maestras Silver: `silver.comicos`, `silver.proveedores`, `silver.solicitudes`

---

## Fase Pipeline Inicial + Gold Layer (v0.5.0–0.5.15) — 2026-02-16/18

Construcción del pipeline Bronze→Silver→Gold, scoring engine y curación de lineup.

### Medallion Schema (v0.5.0–0.5.7)
- **Capa Gold** (`gold_relacional.sql`): enums `genero_comico`/`categoria_comico`/`estado_solicitud`, tablas `gold.comicos` y `gold.solicitudes`, índices de recencia/estado
- **Scoring engine v1** (`scoring_engine.py`): ranking Silver→Gold con persistencia, descarte de blacklist, salida JSON `top_10_sugeridos`
- **Normalización Silver** (v0.5.4): `nombre_artistico → nombre`, `instagram_user → instagram` en `silver.comicos`; campo `genero` añadido a Silver y Gold
- **RLS y políticas** (v0.5.5–0.5.7): grants `anon` en Silver, políticas `p_anon_select/update_silver_comicos`, migraciones idempotentes

### Scoring y Lineup Validation (v0.5.8–0.5.15)
- **Scoring fixes** (v0.5.8–0.5.10): intercalado estricto por género (F/NB → M → Unknown) con punteros independientes; deduplicación por `comico_id`; `build_ranking` con continuidad al agotar bucket
- **Vista `gold.lineup_candidates`** + RPC `gold.validate_lineup` (v0.5.11–0.5.13): sincroniza estados `aprobado`/`no_seleccionado` en Gold y Silver; GRANT a `anon`/`authenticated`; vista expone `estado` y `contacto`
- **Estado `scorado`** (v0.5.15): persistencia del scoring en `gold.solicitudes.estado`, actualiza `gold.comicos.score_actual`; `App.jsx` prioriza candidatos `scorado` en el draft inicial
- **`setup_db.py`**: gestión completa del ciclo Bronze/Silver/Gold; `SQL_SEQUENCE` con todas las migraciones
