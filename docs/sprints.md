# Historial de Sprints

## Sprint 2 — Google Forms + Integración Backend (v0.7.0) — 2026-03-05

### Completado
- **Auto-creación de Google Form** al crear un open mic (fire-and-forget desde `OpenMicSelector`)
- **GoogleFormBuilder con OAuth2** — migración desde service account (las SA tienen quota:0 en Drive)
- **Sheet propia vía Sheets API** — la Forms API no genera `linkedSheetId` por API
- **Columna `open_mic_id`** con ARRAYFORMULA en col J de la Sheet
- **Botón manual fallback** en `OpenMicDetail` para open mics existentes
- **CORS habilitado** en Flask (`flask-cors`)
- **Script de autorización OAuth2** — `backend/scripts/google_oauth_setup.py`
- **`config.form`** almacenado en `silver.open_mics.config`: `form_id`, `form_url`, `sheet_id`, `sheet_url`
- **23 tests unitarios** de `GoogleFormBuilder` con mocks de Google APIs
- **Spec v1.1** de auto-creación actualizada con arquitectura real

### Spec
→ `specs/google_form_autocreation_spec.md`

---

## Sprint 1 — Pivot SaaS Multi-Tenant (v0.6.0) — 2026-03-04

### Completado
- **Esquema v3 multi-tenant:** `silver.organization_members`, `silver.open_mics` (config JSONB), `silver.lineup_slots`, `confirm_lineup()` RPC, RLS por host
- **Auth magic link:** Supabase OTP, solo hosts pre-registrados
- **Navegación Root:** `Login → OpenMicSelector → OpenMicDetail → App`
- **OpenMicSelector:** lista open mics del host, roles `host`/`collaborator`
- **OpenMicDetail:** hub del open mic (info + config + form + zona de peligro)
- **ScoringConfig:** lee config JSONB de `silver.open_mics` — 27 tests verdes
- **Scoring engine v3:** `execute_scoring(open_mic_id)` con recencia scoped
- **ScoringConfigurator:** componente React para editar config JSONB
- **Ingesta Bronze → Silver v3:** `BronzeRecord` con `open_mic_id`, pipeline v3/legacy

---

## Sprints anteriores (v0.5.x)

Ver `CHANGELOG.md` para el historial completo.

Resumen:
- **v0.5.x** — SVG Renderer con Playwright, MCP HTTP, Data Binder, Security Gate, templates catalog
- **v0.4.x y anteriores** — Pipeline inicial, integración Canva (deprecada), scoring v1/v2

---

## Pendiente Sprint 2

- [ ] Backend del renderer lee `config.poster.base_image_url`
- [ ] n8n webhook post-validación dispara renderer con `open_mic_id`
- [ ] `confirm_lineup()` RPC → `silver.lineup_slots`
- [ ] Penalización recencia operativa
- [ ] Deploy frontend en producción
