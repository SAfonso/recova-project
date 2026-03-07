# Recova Project — Memory

## Proyecto
- SaaS multi-tenant para gestión de open mics de comedia
- Stack: React + Vite (frontend), Python/Flask (backend), Supabase (DB/auth), n8n (workflows)
- Arquitectura: Medallion Bronze/Silver/Gold
- Rama activa: `dev` (push siempre a `dev`)
- Versión actual: 0.14.0

## Convenciones
- Siempre SDD: spec primero, luego implementación
- Commits en español con Co-Authored-By Claude
- No hacer merge de ramas, solo push a dev
- El usuario prefiere respuestas cortas y directas

---

## Estado actual (2026-03-07) — Sprint 9 completado

### Sprints completados
- Sprint 3 (v0.8.0) — Telegram Lineup Agent ✅
- Sprint 4a (v0.9.0) — Telegram QR Self-Registration ✅
- Sprint 4b (v0.9.1) — Telegram Register Endpoint ✅
- Sprint 5 (v0.10.0) — Validación de Lineup via Telegram ✅
- Sprint 6 (v0.11.0) — Ingesta Multi-Tenant + Scripts de Utilidad ✅
- Sprint 7 (v0.12.0) — Poster Renderer (Gemini Flash Vision) ✅
- Sprint 8 (v0.13.0) — Google OAuth Open Registration ✅
- Sprint 9 (v0.14.0) — Smart Form Ingestion ✅

### Sprint 9 — Detalle (v0.14.0)
- `FormIngestor`: lee preguntas y respuestas via Forms API (sin sheets vinculados)
  - `get_form_questions(form_id)` → [{question_id, title, kind}]
  - `get_responses(form_id, field_mapping)` → campos canónicos + metadata_extra
  - Scopes OAuth: `forms.body.readonly` + `forms.responses.readonly`
- `FormAnalyzer`: Gemini 2.5 Flash mapea títulos → schema canónico
  - `analyze(questions)` → {titulo → campo_canónico | null}
  - Strip de markdown fences; ValueError en JSON inválido
- `POST /api/open-mic/analyze-form`: orquesta analyze + guarda via RPC
- **Migración aplicada**: `silver.solicitudes.metadata` JSONB + RPC `update_open_mic_config_keys`
- `ScoringTypeSelector.jsx`: radio pills none/basic/custom, persiste via RPC
- `OpenMicDetail.jsx`: campo URL/ID form externo + botón "Analizar campos" + badge estado
- **Tests**: 20 backend (9+5+6) + 14 frontend (7+7) = 34 verdes
- **Pendiente**: regenerar refresh token con scopes `forms.body.readonly` + `forms.responses.readonly`
- **Setup frontend tests**: Vitest + @testing-library/react + happy-dom (jsdom@28 incompatible ESM)
- Spec: `specs/smart_form_ingestion_spec.md`

### Flujo principal implementado y funcionando
1. Host hace login con Google OAuth → `Login` → si nuevo usuario → `OnboardingScreen`
2. Selecciona/crea un open mic → `OpenMicSelector` (icono dinámico)
3. Hub del open mic → `OpenMicDetail` (info + config con subtabs Info/Scoring)
4. Ve el lineup y lo valida → `App` (NotebookSheet + ValidateButton)
5. Al validar: RPC `validate_lineup` (Gold) + RPC `upsert_confirmed_lineup` (Silver) + webhook n8n

### Infra
- **Frontend**: https://recova-project-z5zp.vercel.app (rama `dev`)
- **Backend**: https://api.machango.org (Traefik proxy → Flask PM2 :5000)
- **Bot Telegram**: @ailineup_bot

---

## Backlog pendiente
- [ ] **Regenerar refresh token** con scopes `forms.body.readonly` + `forms.responses.readonly` via `backend/scripts/google_oauth_setup.py`
- [ ] Actualizar `/root/RECOVA/.env` en servidor: `SUPABASE_SERVICE_KEY`, `GOOGLE_OAUTH_*`, `BACKEND_URL`, `FRONTEND_URL`, `GEMINI_API_KEY`
- [ ] Activar `Scoring & Draft` en n8n producción (está `active: false`)
- [ ] Activar `Ingesta-Solicitudes` en n8n producción + configurar schedule
- [ ] Conectar FormIngestor al flujo n8n (`POST /api/ingest-from-forms`)
- [ ] Dockerizar backend + frontend para testing local
- [ ] Conectar renderer al flujo: n8n post-validación → `POST /api/render-poster` → Supabase Storage → Telegram
- [ ] Penalización recencia — `scoring_engine.py:250`

## Roadmap
- **Sprint 10 (v0.15.0)** — Scoring Inteligente Custom
  - Gemini propone reglas desde campos no canónicos del form
  - `CustomScoringConfigurator`: toggle + slider por regla
  - `scoring_engine.py`: aplica `custom_scoring_rules` de config JSONB
  - Prerequisito: Sprint 9 ✅

---

## Arquitectura DB

### Schemas: `silver`, `bronze`, `gold`
**Tablas clave Silver:**
- `silver.open_mics` — config JSONB (scoring, poster, form, field_mapping, scoring_type, external_form_id)
- `silver.solicitudes` — transaccional con linaje Bronze; columna `metadata` JSONB (Sprint 9)
- `silver.lineup_slots` — slots confirmados
- `silver.comicos`, `silver.organization_members`, `silver.telegram_users`

**RPCs clave:**
- `gold.validate_lineup(p_selection, p_event_date)`
- `silver.upsert_confirmed_lineup(p_open_mic_id, p_fecha_evento, p_approved_solicitud_ids)`
- `silver.onboard_new_host(p_nombre_comercial)` — SECURITY DEFINER
- `silver.update_open_mic_config_keys(p_open_mic_id, p_keys)` — merge JSONB config (Sprint 9)

**Vistas:** `gold.lineup_candidates` — filtrable por `open_mic_id`

---

## Archivos clave

### Frontend
- `frontend/src/main.jsx` — Root: Login → OpenMicSelector → OpenMicDetail → App
- `frontend/src/App.jsx` — lineup view
- `frontend/src/components/OpenMicDetail.jsx` — hub del open mic; análisis de form (Sprint 9)
- `frontend/src/components/ScoringConfigurator.jsx` — edita config JSONB; integra ScoringTypeSelector
- `frontend/src/components/ScoringTypeSelector.jsx` — selector none/basic/custom (Sprint 9)
- `frontend/src/components/OpenMicSelector.jsx` — lista/crea open mics
- `frontend/src/utils/formUtils.js` — `extractFormId(urlOrId)` (Sprint 9)
- `frontend/src/test/` — Vitest tests (setup: happy-dom)

### Backend
- `backend/src/triggers/webhook_listener.py` — Flask: todos los endpoints
- `backend/src/core/form_ingestor.py` — `FormIngestor` (Sprint 9)
- `backend/src/core/form_analyzer.py` — `FormAnalyzer` Gemini (Sprint 9)
- `backend/src/core/sheet_ingestor.py` — `SheetIngestor` (legado, sigue activo)
- `backend/src/core/google_form_builder.py` — crea Google Form+Sheet via OAuth2
- `backend/src/core/scoring_config.py` — lee config JSONB de open_mic
- `backend/src/core/poster_detector_gemini.py` — GeminiDetector (Gemini 2.5 Flash Vision)

### Specs/Migrations
- `specs/smart_form_ingestion_spec.md` — SDD Sprint 9
- `specs/sql/migrations/20260307_smart_form_ingestion.sql` — metadata + update_config RPC

---

## Patrones importantes

### Mock google.genai en tests (Python)
Dos archivos usan `sys.modules.setdefault("google.genai", mock)`.
Tras el `setdefault`, siempre reasignar: `_mock_genai = sys.modules["google.genai"]`
para que ambos apunten al mismo objeto independientemente del orden de carga.
Ver `test_form_analyzer.py` y `test_poster_detector_gemini.py`.

### Supabase mock en tests Flask
```python
def _chain(data):
    m = MagicMock()
    m.execute.return_value = MagicMock(data=data)
    for method in ("eq","select","insert","update","delete","order",
                   "single","limit","in_","neq","not_","filter"):
        getattr(m, method).return_value = m
    return m
```

### Google OAuth2 (Forms)
- Scopes actuales: `forms.body`, `spreadsheets`, `drive`
- Scopes pendientes de añadir: `forms.body.readonly`, `forms.responses.readonly`
- Script: `backend/scripts/google_oauth_setup.py`
- SDK Gemini: `google-genai>=1.0.0` (NO `google-generativeai`, deprecado)
- Modelo: `gemini-2.5-flash`

### n8n — notas
- Variables en n8n: NO pueden ser env vars del sistema (auto-hospedado en Coolify)
- Supabase en n8n: usar service role key para bypasear RLS
- `Accept-Profile: silver` obligatorio para queries a schema silver
- URL en n8n: `={{ expr }}` (un solo `=`)
