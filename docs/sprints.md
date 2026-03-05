# Historial de Sprints y Fases

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
