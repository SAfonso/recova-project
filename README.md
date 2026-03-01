# AI LineUp Architect 🎭

**Estado del Proyecto:** 🛠️ En desarrollo activo
**Versión:** `0.5.42`
**Metodología:** Spec-Driven Development (SDD)

Sistema para ingesta, curación y generación automática de cartel de Open Mics, con trazabilidad completa desde formularios hasta artefacto final publicado.

## 1. Fuente de verdad técnica (v0.5.42)

En esta versión se consolidan los siguientes cambios estructurales:

- **Servidor MCP de render (implementado):** `backend/src/mcp_server.py` expone `render_lineup` con lock global de concurrencia, gate de seguridad para `reference_image_url`, fallback automático a plantilla `active`, render Playwright con `--no-sandbox`, espera `window.renderReady` y salida PNG en `/tmp/render_{event_id}.png` con trazabilidad de recuperación.
- **Suite de integración MCP Server (TDD asíncrono):** nueva batería en `backend/tests/mcp/test_server_integration.py` para contrato de orquestación end-to-end (éxito, recuperación por fallo de seguridad, lock de concurrencia y caja negra de metadatos sensibles) usando `pytest-asyncio` y `unittest.mock` para evitar navegador real.
- **Implementación del Data Binder (SDD §13):** `backend/src/core/data_binder.py` incorpora `generate_injection_script(lineup, max_slots)` (alias `generate_injection_js`) con inyección exclusiva de `name` por selector `.slot-n .name`, ocultación de slots vacíos con `style.display = 'none'`, FitText en pasos de `1px` hasta `12px` mínimo y señal final `window.renderReady = true` para sincronización Playwright.
- **TDD de capa de seguridad MCP:** se incorpora `backend/tests/mcp/test_security.py` para validar HTTPS-only, bloqueo de wrappers (Google Drive/Dropbox), inspección de Magic Bytes (PNG/JPEG/WebP) y manejo de timeout de red con recuperación no bloqueante (`USE_ACTIVE_TEMPLATE`).
- **Nueva capa MCP Agnostic Renderer (spec-first):** se define el contrato agnóstico de entrada/salida, trazabilidad y modos `template_catalog`/`vision_generated` en `specs/mcp_agnostic_renderer_spec.md` como Fuente de Verdad previa a implementación.
- **Security Gate para imágenes de referencia:** `reference_image_url` exige pre-fetch de 32 bytes + inspección de Magic Bytes (PNG/JPEG/WebP), rechazo `ERR_INVALID_FILE_TYPE` y política de origen `Direct Link Only`/Supabase con bloqueo de wrappers HTML (`ERR_ACCESS_DENIED_OR_NOT_DIRECT_LINK`).
- **Jerarquía de resiliencia MCP (2 niveles):** se formaliza `Active Mode` por intent y fallback local obligatorio a `backend/src/templates/catalog/fallback/`, con warning de trazabilidad `SYSTEM_FALLBACK_TRIGGERED` en `trace.warnings`.
- **Persistencia condicional eficiente (`design-archive`):** solo `vision_generated` archiva `final.png`, `generated.html`, `generated.css`, `reference.png` y `metadata.json`; `template_catalog` no duplica almacenamiento en archivo.
- **Estándar de Unidad Atómica de Diseño (Sección 12):** cada `template_id` se define como carpeta autocontenida en `backend/src/templates/catalog/` con `template.html`, `style.css`, `manifest.json` y `assets/`, declarando que `manifest.json` es la única fuente de configuración de render.
- **Contrato técnico del `manifest.json`:** campos obligatorios `template_id`, `version`, `display_name`, `canvas.width/height`, `capabilities.min_slots/max_slots` y `font_strategy` (Google Fonts por `@import`).
- **Pre-vuelo de capacidad con override auditado:** validación `len(lineup)` vs `manifest.capabilities.max_slots`, error `TEMPLATE_CAPACITY_EXCEEDED`, soporte de `intent.force_capacity_override` y log obligatorio `CAPACITY_OVERRIDE_ACTIVE` con advertencia de riesgo estético bajo responsabilidad del Host.
- **Sección 13 del SDD (inyección visual + FitText + output mínimo):** se formaliza el binding estricto `lineup[n].name -> .slot-(n+1) .name`, la exclusión visual de `lineup[n].instagram`, el auto-ajuste tipográfico por overflow (`scrollWidth` vs `clientWidth`, paso 2px hasta `min-font-size` del `manifest.json`) y la responsabilidad única de salida (`public_url` + `trace`).
- **Sección 14 del SDD (Fallo No Bloqueante):** se formaliza política `HTTP 200 OK` para render exitoso (incluyendo recuperación), matriz obligatoria de auto-recuperación (`ERR_CONTRACT_INVALID`, `ERR_INVALID_FILE_TYPE`, `ERR_NOT_DIRECT_LINK`, `ERR_CAPACITY_EXCEEDED`), trazabilidad `trace.status = recovered_with_warnings` + `trace.recovery_notes` y abortos reales acotados a `ERR_RENDER_ENGINE_CRASH` / `ERR_STORAGE_UNREACHABLE`.
- **Hardening de workflows n8n:** `workflows/n8n/LineUp.json` elimina credenciales/hosts hardcodeados y usa variables de entorno (`$env`) para Supabase y renderer.
- **Nueva variable de entorno para render en n8n:** `N8N_BACKEND_RENDER_URL` documentada en `.env.example`.
- **Deprecación de Canva:** la integración con Canva API queda retirada del flujo productivo.
- **Motor de diseño propio:** el render final se realiza con `PlaywrightRenderer`.
- **Desacople por puertos (SDD):**
  - **Webhook Ingesta (Flask):** `:5000`
  - **Renderer API (Flask + Gunicorn):** `:5050`
- **Infraestructura objetivo:** ejecución directa en **VPS Ubuntu** con **PM2** para persistencia de procesos.
- **Salida de render:** PNG subido al bucket `posters` de Supabase Storage, devolviendo `public_url`.

## 2. Arquitectura de sistema

```mermaid
flowchart LR
    A[Google Forms] --> B[n8n Orquestador]

    B --> C[Webhook Ingesta\nFlask :5000]
    C --> D[(Supabase\nBronze/Silver/Gold)]

    B --> E[App de Curación\nReact en Vercel]
    E --> D

    B --> F[Renderer API\nFlask + Gunicorn :5050]
    F --> G[PlaywrightRenderer]
    G --> H[(Supabase Storage\nBucket posters)]
    H --> I[public_url PNG]

    I --> B
```

## 3. Stack tecnológico e infraestructura

| Capa | Tecnología | Rol en el sistema |
|---|---|---|
| Hosting | VPS Ubuntu | Entorno principal de ejecución en producción. |
| Orquestación | n8n | Coordinación de flujos (ingesta, validación y render). |
| Ingesta API | Flask (`backend/src/webhook_listener.py`) | Endpoint webhook para normalización y paso Bronze → Silver en `:5000`. |
| Render API | Flask + Gunicorn (`backend/src/app.py`) | Endpoint `POST /render-lineup` en `:5050`. |
| Motor de Cartelería | Playwright + Jinja2 (`PlaywrightRenderer`) | Generación del PNG final en runtime local. |
| Persistencia de procesos | PM2 | Gestión de procesos `webhook-ingesta` y `recova-renderer`. |
| Base de datos | Supabase PostgreSQL | Capas `bronze`, `silver`, `gold` para trazabilidad y scoring. |
| Almacenamiento de artefactos | Supabase Storage (`posters`) | Hosting del cartel final y emisión de `public_url`. |
| Curación operativa | React en Vercel | Validación manual del lineup antes de render final. |

## 4. APIs de producción

### 4.1 Webhook de ingesta (`:5000`)

- Endpoint principal de disparo:
  - `POST /ingest`
- Uso típico:
  - n8n recibe trigger y envía payload al webhook.
  - El servicio procesa reglas de normalización y persiste en Supabase.

Ejemplo local:

```bash
curl -X POST http://localhost:5000/ingest \
  -H "Content-Type: application/json" \
  -d '{"trigger":"n8n"}'
```

### 4.2 Renderer API (`:5050`)

- Endpoint productivo:
  - `POST /render-lineup`
- Contrato:
  - Valida payload según spec SDD de renderer.
  - Renderiza PNG con `PlaywrightRenderer`.
  - Sube archivo a Supabase Storage (`posters`).
  - Responde con `public_url` y metadatos del render.

#### Ejecución recomendada con Gunicorn (producción)

```bash
./.venv/bin/gunicorn -w 4 -b 0.0.0.0:5050 backend.src.app:app
```

#### Gestión con PM2

```bash
pm2 start "./.venv/bin/gunicorn -w 4 -b 0.0.0.0:5050 backend.src.app:app" --name recova-renderer
pm2 start "./.venv/bin/python backend/src/webhook_listener.py" --name webhook-ingesta
```

## 5. Almacenamiento de carteles (Supabase Storage)

Flujo de salida de cartelería:

1. Renderer genera PNG temporal local.
2. El archivo se sube al bucket `posters`.
3. Se publica URL accesible (`public_url`).
4. Se elimina el temporal local tras upload exitoso.

Ruta lógica esperada del archivo:

- `YYYY-MM-DD/lineup_{request_id}.png`

## 6. Modelo de datos y pipeline

- **Bronze:** ingesta cruda de formularios.
- **Silver:** datos normalizados y consistentes para operación.
- **Gold:** capa de scoring/histórico para selección de lineup.

Resumen del pipeline:

1. n8n recibe trigger externo.
2. n8n invoca Webhook Ingesta (`:5000`).
3. La curación operativa se realiza desde la app React en Vercel.
4. n8n solicita render final a Renderer API (`:5050`).
5. El PNG queda en `posters` y se devuelve `public_url`.

## 7. Operación y desarrollo

### 7.1 Preparación

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
playwright install-deps
```

> Nota VPS/producción: instalar Chromium y dependencias del sistema evita el fallback local de render y mejora la trazabilidad de errores reales de arranque del navegador.

### 7.2 Base de datos (setup)

```bash
./.venv/bin/python setup_db.py
./.venv/bin/python setup_db.py --seed
./.venv/bin/python setup_db.py --reset --seed
```

### 7.3 Tests

```bash
./.venv/bin/python -m pytest -q
./.venv/bin/python -m pytest -q backend/tests/unit
./.venv/bin/python -m pytest -q backend/tests/integration
```

## 8. Estructura del repositorio (alto nivel)

```text
.
├── AGENTS.md
├── README.md
├── CHANGELOG.md
├── requirements.txt
├── pyproject.toml
├── package.json
├── setup_db.py
├── backups/
│   └── .gitkeep
├── backend/
│   ├── database/
│   │   └── setup_frontend_logic.sql
│   ├── logs/
│   │   ├── canva_auth.log
│   │   ├── canva_auth.log.2026-02-18
│   │   ├── canva_auth.log.2026-02-19
│   │   └── canva_builder.log
│   ├── src/
│   │   ├── app.py
│   │   ├── bronze_to_silver_ingestion.py
│   │   ├── playwright_renderer.py
│   │   ├── scoring_engine.py
│   │   ├── old/
│   │   │   ├── canva_auth_utils.py
│   │   │   ├── canva_builder.py
│   │   │   ├── getVeri.py
│   │   │   ├── ingestion_cli_backup.py
│   │   │   ├── test.py
│   │   │   └── test/
│   │   │       └── test_canva_builder.py
│   │   ├── triggers/
│   │   │   └── webhook_listener.py
│   │   └── templates/
│   │       ├── lineup_v1.html
│   │       └── lineup_v2.html
│   ├── tests/
│   │   ├── .gitkeep
│   │   ├── conftest.py
│   │   ├── unit/
│   │   │   ├── test_app.py
│   │   │   ├── test_bronze_to_silver_ingestion.py
│   │   │   ├── test_n8n_workflows_security.py
│   │   │   ├── test_playwright_renderer.py
│   │   │   ├── test_scoring_engine.py
│   │   │   ├── test_setup_db.py
│   │   │   └── test_webhook_listener.py
│   │   ├── integration/
│   │   │   ├── test_supabase_storage.py
│   │   │   └── test_supabase_upload.py
│   │   └── sql/
│   │       └── test_sql_contracts.py
├── docs/
│   ├── bronze-multi-proveedor-master-data.md
│   ├── bronze-silver-comicos-sync.md
│   ├── bronze-solo-solicitudes-linaje-silver.md
│   ├── canva-oauth-pkce-builder.md
│   ├── curacion-lineup-validacion-estados-gold-silver.md
│   ├── esquemas-bronze-silver.md
│   ├── github-actions-deploy-dev.md
│   ├── ingesta-atomica-n8n.md
│   ├── ingesta-batch-bronze-queue.md
│   ├── ingesta-bronze-silver-error-handling.md
│   ├── ingesta-bronze-silver-reserva.md
│   ├── ingesta-constraint-unicidad-proveedor-slug.md
│   ├── ingesta-logs-auditoria.md
│   ├── ingesta-whatsapp-show-cercano-origen.md
│   ├── mcp-agnostic-renderer-spec.md
│   ├── n8n-workflows-secretos-entorno.md
│   ├── proveedor-default-recova.md
│   ├── refactor-validacion-bronze-silver.md
│   ├── render-api-produccion.md
│   ├── scoring-batch-n8n-fix.md
│   ├── seed-data-casos-borde.md
│   ├── seed-unique-comico-fecha-fix.md
│   ├── setup-db-backup-local.md
│   ├── setup-db-backup-reset-seed.md
│   ├── setup-db-migraciones.md
│   ├── silver-relacional.md
│   ├── stack-tecnologico-infraestructura-mvp.md
│   ├── tests-backend.md
│   └── webhook-listener-n8n-ingesta.md
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── postcss.config.js
│   ├── tailwind.config.js
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       ├── index.css
│       ├── main.jsx
│       └── supabaseClient.js
├── specs/
│   ├── mcp_agnostic_renderer_spec.md
│   ├── playwright_renderer_spec.md
│   ├── workflows/
│   │   └── n8n_workflow_secret_externalization.md
│   └── sql/
│       ├── bronze_multi_proveedor_master.sql
│       ├── gold_relacional.sql
│       ├── seed_data.sql
│       ├── silver_relacional.sql
│       └── migrations/
│           ├── 20260212_alter_tipo_solicitud_status.sql
│           ├── 20260217_drop_score_final_from_silver_solicitudes.sql
│           ├── 20260217_fix_anon_update_policy_silver_comicos.sql
│           ├── 20260217_sync_lineup_validation_states.sql
│           └── 20260218_create_lineup_candidates_and_validate_lineup.sql
├── workflows/
│   ├── main_pipeline.json
│   └── n8n/
│       ├── Ingesta-Solicitudes.json
│       ├── LineUp.json
│       └── Scoring & Draft.json
└── .env.example
```

## 9. Referencias internas recomendadas

- `specs/playwright_renderer_spec.md`
- `specs/mcp_agnostic_renderer_spec.md`
- `docs/mcp-agnostic-renderer-spec.md`
- `docs/render-api-produccion.md`
- `docs/webhook-listener-n8n-ingesta.md`
- `docs/tests-backend.md`

---

Este README define el estado operativo objetivo de la versión `0.5.36` y debe tratarse como referencia principal para decisiones de implementación y despliegue.
