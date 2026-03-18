## [0.32.0] - 2026-03-18

### Security — Sprint J1: Protección contra Prompt Injection en llamadas a Gemini

- Nuevo módulo **`backend/src/core/prompt_guard.py`** con dos capas de defensa:
  - `detect_injection()` — pattern matching multilingüe (ES, EN, FR, DE, PT, IT, ZH, RU, JA, KO) + delimitadores de escape + Unicode tricks
  - `sanitize_for_prompt()` — strip invisibles, control chars, trunca a 200 chars, escapa delimitadores
  - `validate_fields()` — integra sanitización + detección, lanza `ValueError` si detecta inyección
  - `wrap_user_field()` — envuelve campos en `<user_field>` tags + instrucción defensiva en prompt template
- **`FormAnalyzer.analyze()`** y **`CustomScoringProposer.propose()`** ahora sanitizan y validan inputs antes de enviar a Gemini
- Workflow n8n **Ingesta-Solicitudes**: nodo Code sanitize entre Edit Fields → Aggregate (nombres/instagrams de cómicos)
- Workflow n8n **Test BOT**: nodo Code sanitize + If (¿Bloqueado?) antes de AI Agent + system prompt reforzado

### Tests
- 66 tests nuevos en `test_prompt_guard.py` (patrones multilingües, falsos positivos, sanitización, truncamiento)
- 4 tests de integración en `test_form_analyzer.py` y `test_custom_scoring_proposer.py` (rechazo de inyección + tags `<user_field>`)
- **Total acumulado**: 443 backend + 70 frontend = 513 tests verdes

---

## [0.31.0] - 2026-03-18

### Added — Sprint I5: Error Boundary React

- Componente `ErrorBoundary` (class component) con `getDerivedStateFromError` + `componentDidCatch`
- Envuelve `<Root />` en `main.jsx` — captura errores no manejados en todo el árbol de componentes
- UI amigable: mensaje de error + botón "Recargar página"
- Errores se loguean en consola con `componentStack` para debugging

### Added — Sprint I6: Type hints en blueprints

- `-> tuple` en **23/23** endpoints Flask (16 nuevos + 7 existentes)
- Blueprints actualizados: ingestion (3), lineup (3), telegram (2), dev (3), mcp_agent (5)

### Fixed — Sprints I1, I2: Silent failures + savepoints SQL seguros

- **I1**: Logging en 6 `except` silenciosos — `shared.py` (auth JWT, pipeline async), `lineup.py` (scoring), `poster.py` (cleanup), `poster_detector_gemini.py` (Gemini API), `bronze_to_silver_ingestion.py` (genderize.io)
- **I2**: Reemplazadas f-strings en `SAVEPOINT`/`ROLLBACK TO SAVEPOINT` por `sql.SQL().format(sql.Identifier())` de psycopg2

### Fixed — Bug bronze atascados en bucle infinito

- Clasificador `_is_permanent_error()` distingue errores permanentes (UniqueViolation, CheckViolation, ValueError) de transitorios (OperationalError, timeout)
- `mark_bronze_processed()` se llama tras errores permanentes para evitar reintentos infinitos
- 2 tests nuevos: UniqueViolation marca procesado, OperationalError no lo marca

### Tests
- 4 tests nuevos (2 permanent/transient error + 1 assert actualizado + 1 warning fix)
- **Total acumulado**: 372 backend + 70 frontend = 442 tests verdes

---

## [0.30.0] - 2026-03-18

### Fixed — Sprints I1, I2: Silent failures + savepoints SQL seguros

- Commit intermedio — cambios integrados en v0.31.0

---

## [0.29.0] - 2026-03-18

### Refactor — Sprint I4: Descomponer `process_single_solicitud()` (God Function)

- Extraída **`_parse_bronze_record(bronze, today)`** → dataclass `ParsedSolicitud` con normalización + parsing de fechas/experiencia/disponibilidad
- Extraída **`_persist_solicitud(conn, bronze, parsed)`** → inferencia de género, upsert cómico, insert silver, mark processed
- `process_single_solicitud()` queda como orquestador (~30 líneas): savepoint → parse → check dates → persist → error handling
- Función original: ~107 líneas monolíticas → 3 funciones con responsabilidad única
- **Total acumulado**: 370 backend + 70 frontend = 440 tests verdes

---

## [0.28.0] - 2026-03-18

### Fixed — Sprint I3: Gender parity dead code

- `'unknown'` ahora entra en el bucket `f_nb` del algoritmo de paridad de género, junto con `'f'` y `'nb'`
- Antes: candidatos sin género inferido caían en bucket `unk` y se relegaban al final del ranking — gender parity no los incluía en la alternancia
- Después: `unknown` alterna con `m` como parte del grupo subrepresentado
- Constante `_F_NB = {"f", "nb", "unknown"}` centraliza la pertenencia al grupo
- 2 tests actualizados con nuevo orden esperado de alternancia
- **Total acumulado**: 370 backend + 70 frontend = 440 tests verdes

---

## [0.27.0] - 2026-03-18

### Security — Sprint H2-1: SQL injection fix en `register_ingestion_error()`

- **Whitelist** `_ALLOWED_ERROR_COLUMNS = frozenset({"metadata", "raw_data_extra"})` — `ValueError` si la columna no está en la lista
- **`psycopg2.sql.Identifier()`** para construir la query de forma segura (doble protección)
- Eliminado f-string con interpolación directa de nombre de columna en SQL
- 4 tests nuevos: columnas permitidas, rechazo de inyección SQL, path `None`

### Added — Sprint H2-2: Test de carga concurrente rate limiting

- Test con **100 requests en 20 threads** contra endpoint con `max_requests=3`
- Verifica exactamente 3 pasan (200) y 97 bloqueadas (429)
- Confirma que `_rate_limit_lock` es thread-safe bajo carga concurrente

### Added — Sprint H2-4: Diagramas de secuencia Mermaid

- `docs/sequence-diagram.md` con 5 diagramas:
  - **Flujo principal**: Solicitud → Ingesta Bronze/Silver → Scoring Gold → Validación → n8n
  - **Telegram**: Registro host con código RCV-XXXX
  - **Ingesta batch**: n8n → Sheets → Bronze → Silver
  - **Arquitectura Medallion**: Flowchart Bronze → Silver → Gold
  - **Seguridad por capa**: rate_limit → api_key → validate_json → whitelist SQL

### Tests
- 5 tests nuevos (4 whitelist + 1 carga concurrente)
- **Total acumulado**: 370 backend + 70 frontend = 440 tests verdes

---

## [0.26.0] - 2026-03-17

### Added — Sprint G1: OpenAPI spec

- `docs/openapi.yaml` — Especificación OpenAPI 3.0.3 con las 22 rutas de la API
- Organizada en 8 tags: Ingesta, Lineup, Formularios, Telegram, Poster, MCP Agent, Orquestación, Desarrollo
- Documenta ambos mecanismos de auth (API Key + Bearer JWT), rate limiting y formato de errores unificado
- Schemas reutilizables: `Error`, `CandidateItem`, `SlotItem`
- Respuestas comunes: `Unauthorized`, `ValidationError`, `RateLimited`, `ExternalServiceError`

---

### Added — Sprint F3: Rate limiting in-memory por IP

#### Decorador `@rate_limit(max_requests, window_seconds)`
- Ventana deslizante in-memory con `{endpoint:ip: [timestamps]}`, thread-safe (`threading.Lock`)
- Devuelve **429** con `Retry-After` header si se excede el límite
- Headers informativos en cada respuesta: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- No requiere Redis — el proceso PM2 es único

#### Endpoints protegidos
- `/api/form-submission` — **5 req/min** (dispara pipeline completo)
- `/api/telegram/register` — **10 req/min**
- `/api/validate-view/lineup` — **30 req/min**
- `/api/validate-view/validate` — **30 req/min**

### Tests
- 9 tests nuevos en `test_rate_limit_decorator.py`: límite, 429, headers, ventana, endpoints independientes, expiración
- Fixture `_reset_rate_limit_store` en `conftest.py` (autouse)
- **Total acumulado**: 365 backend + 70 frontend = 435 tests verdes

---

## [0.25.0] - 2026-03-17

### Changed — Sprint F2: Descomponer App.jsx (534 → 120 líneas)

#### Hooks extraídos
- **`useCandidates.js`** (~148 líneas) — data fetching, selectedIds, toggleSelected, isLastMinuteMode, singleDateMode, validación contra `silver.lineup_slots`
- **`useEdits.js`** (~96 líneas) — getDraft, hasPendingEdit, updateDraft, handleGeneroUpdate, handleCategoryUpdate, clearEdits. Exporta `CATEGORY_OPTIONS`
- **`useValidation.js`** (~131 líneas) — validateLineup (RPC + n8n fire-and-forget), handleCambiarAccept (reset slots)

#### Componentes presentacionales extraídos
- **`LoadingSkeleton.jsx`** — skeleton shimmer de 5 filas durante carga
- **`ValidadoStamp.jsx`** — sello animado "VALIDADO" con checkmark SVG
- **`CambiarConfirmModal.jsx`** — modal de confirmación para cambiar lineup validado
- **`RecoveryNotes.jsx`** — textarea de notas de recuperación para Telegram/n8n

#### App.jsx resultante (~120 líneas)
- Solo estado UI local: `activeId`, `activeTab`, `isExpanded`, `recoveryNotes`
- 3 llamadas a hooks + 1 useMemo (`activeCandidate`) + 1 función (`openExpanded`)
- JSX layout puro: wiring de props a componentes existentes y nuevos

### Tests
- 26 tests nuevos: `useEdits.test.js` (10), `useCandidates.test.js` (8), `useValidation.test.js` (8)
- **Total acumulado**: 356 backend + 70 frontend = 426 tests verdes

---

## [0.24.0] - 2026-03-17

### Changed — Sprint E: Red flags defensa (E1 + E2 + E3)

#### E1 — Test E2E smoke (happy path)
- Nuevo test `test_e2e_happy_path.py` que simula el flujo completo sin red: POST `/api/form-submission` → `run_pipeline()` (bronze→silver) → `execute_scoring()` (silver→gold). Mock de Supabase + psycopg2 cursor con pattern matching SQL
- 4 tests: happy path completo, detección de género, score positivo, categoría restricted excluida

#### E2 — Validación de entrada centralizada
- Nuevo decorador `@validate_json(required)` en `shared.py`: valida JSON body, campos obligatorios, tipos. Devuelve 400 con mensaje claro
- Aplicado en **13 endpoints POST** de 6 blueprints: ingestion, form, telegram, dev, lineup, mcp_agent
- Eliminadas validaciones manuales redundantes en `dev.py`
- 11 tests dedicados en `test_validate_json_decorator.py`

#### E3 — Auditoría del scoring (score breakdown)
- Nuevo campo `score_breakdown: dict` en `CandidateScore` dataclass
- `build_ranking()` construye desglose: `{base_score, categoria, recency_penalty, single_date_bonus, custom_rules_bonus, total}`
- `persist_pending_score()` escribe `score_breakdown` como JSONB en `gold.solicitudes`
- `execute_scoring()` incluye `score_breakdown` en respuesta API (`top_sugeridos`)
- Migración SQL: `20260317_add_score_breakdown_to_gold.sql`
- 9 tests dedicados en `test_score_breakdown.py`

### Tests
- **Total acumulado**: 356 backend + 44 frontend = 400 tests verdes

---

## [0.23.0] - 2026-03-16

### Changed — Sprint B+D: Seguridad, calidad y UX

#### Sprint B — Seguridad
- **B2 CORS restringido** — `Access-Control-Allow-Origin: *` reemplazado por origin dinámico: solo acepta `FRONTEND_URL` (Vercel) y `localhost:5173/3000` (dev). Implementado en `shared.py` con `_cors_headers()` y `_cors_origin()`
- **B3 Supabase singleton** — `create_client()` eliminado de todos los blueprints (`form.py`, `ingestion.py`, `dev.py`, `poster.py`). Nueva función `_sb_client()` en `shared.py` con lazy-init singleton. Fixture `_reset_sb_singleton` en `conftest.py` previene leaks entre tests

#### Sprint D — Calidad y argumentación
- **D1 Cascada de género 3 capas** — `infer_gender()` ahora usa: (1) diccionario INE con 54.977 nombres españoles del Padrón Continuo, (2) `gender-guesser` como fallback internacional, (3) `genderize.io` API (100 calls/día, `country_id=ES`, umbral ≥0.7). Resuelve correctamente Iker, Naiara, Maite, Yurena, Pepa, Amaia, Unai, Ainhoa y miles más
- **D2 BD source of truth** — `App.jsx`: `isValidated` se inicializa desde localStorage (caché optimista) pero se reconcilia con `silver.lineup_slots` al montar. Si la BD dice "no confirmado", se limpia localStorage
- **D3 Tutorial UX** — `OnboardingTutorial.jsx`: reactivado botón X, `disableOverlayClose` eliminado, `disableCloseOnEsc={false}`. Al cerrar/skip se muestra modal de confirmación: "El paso de Telegram es obligatorio para usar el bot" con opciones Salir/Continuar
- **D4 Paths portables** — `ecosystem.config.js`: rutas hardcodeadas `/root/RECOVA` reemplazadas por `path.resolve(__dirname)` con soporte para `$PROJECT_ROOT` env var

### Added
- `backend/data/ine_nombres.json` — 54.977 nombres españoles (961 KB) extraídos del INE Padrón Continuo 2022
- `_ine_lookup()`, `_gender_guesser_lookup()`, `_genderize_lookup()` — funciones de capa individual en `bronze_to_silver_ingestion.py`
- `_cors_headers()`, `_cors_origin()`, `_ALLOWED_ORIGINS` — CORS dinámico en `shared.py`

### Tests
- 10 tests nuevos de género (INE + cascada) en `test_bronze_to_silver_ingestion.py`
- 1 test actualizado en `OnboardingTutorial.test.jsx` (modal de confirmación al skip)
- Todos los test patches migrados de `create_client` → `_sb_client` en los módulos correctos
- **Total acumulado**: 332 backend + 44 frontend = 376 tests verdes

---

## [0.22.0] - 2026-03-16

### Changed — Sprint C1+C2: Refactorizar webhook_listener.py + Unificar framework

- **`webhook_listener.py`** — God File de 1.194 líneas refactorizado a app factory de 36 líneas que registra 8 Flask Blueprints + CORS
- **`shared.py`** — nuevo módulo con auth (`_is_authorized`, `_is_authenticated_user`), constantes, helpers (`_next_event_datetime`, `_CANONICAL_TO_BRONZE`) y `run_ingestion_async()` (threading)
- **8 blueprints** en `backend/src/triggers/blueprints/`: `n8n`, `ingestion`, `form`, `lineup`, `mcp_agent`, `telegram`, `dev`, `poster`
- **`/ingest`** — `subprocess.run()` reemplazado por llamada directa a `run_pipeline()`
- **`/scoring`** — `subprocess.run()` reemplazado por llamada directa a `execute_scoring()`
- **`subprocess.Popen`** (ingesta background) — reemplazado por `run_ingestion_async()` con `threading.Thread(daemon=True)`
- **`poster.py`** — absorbe lógica de render de `mcp_server.py`, convertida de async a sync

### Removed

- **`backend/src/mcp_server.py`** — 564 líneas eliminadas (FastAPI renderer, desactivado)
- **`backend/tests/mcp/test_mcp_server_http.py`** y **`test_server_integration.py`** — 9 tests del servidor FastAPI eliminados
- **Dependencias**: `fastapi`, `uvicorn`, `mcp[http]` eliminadas de `requirements.txt` y `pyproject.toml`
- **`ecosystem.config.js`** — app `recova-mcp-http` eliminada (solo queda `webhook-ingesta`)

### Tests

- 14 ficheros de test actualizados (mock paths → blueprints)
- `test_webhook_listener.py` reescrito para testear `/ingest` y `/scoring` con llamadas directas
- **Total acumulado**: 322 backend + 44 frontend = 366 tests verdes
- 22 rutas registradas, 0 cambios de URL (frontend y n8n no se tocan)

---

## [0.21.1] - 2026-03-16

### Fixed — Sprint A: bugs funcionales

- **A1 `scoring_engine.py`** — `build_ranking()` ahora respeta `gender_parity_enabled`: cuando está desactivado (default), el ranking se ordena puramente por score sin alternancia de género; cuando está activado, alterna f/nb ↔ m como antes
- **A2 `scoring_config.py`** — falso positivo: `_SINGLE_DATE_BONUS=40` ya estaba protegido por `single_date_priority_enabled`. Documentada la decisión de diseño de no hacerlo configurable (evitar que cómicos exploten el hack)
- **Tests** — 3 tests existentes actualizados para usar `_parity_config()` (flag `True`); 1 test nuevo `test_build_ranking_no_interleave_when_parity_disabled` que verifica orden puro por score

### Tests

- **Total acumulado**: 397 tests verdes (353 backend + 44 frontend)

---

## [0.21.0] - 2026-03-13

### Added — Tutorial onboarding + fixes CORS y scripts

- **`OnboardingTutorial.jsx`** — tutorial interactivo React Joyride (10 pasos): selector de open mics, crear open mic, pestañas Info/Scoring, lineup, tarjeta cómico, badges "Puede hoy"/"Solo puede hoy", validar lineup, bot Telegram
- **`DevToolsPanel.jsx`** — botón "Resetear tutorial" que elimina la clave `recova_tutorial_done` de localStorage
- **Tutorial multi-página** — modo controlado con `stepIndex` + polling cada 300ms sobre el selector CSS del step actual; pausa con badge `📍` cuando el target no está en el DOM, reanuda automáticamente al detectar el elemento
- **`OpenMicSelector.jsx`** — `[data-tutorial="create-open-mic"]` movido a un `<div>` wrapper siempre presente (el botón solo existe cuando `canCreate=true`, causaba `TARGET_NOT_FOUND` al pulsar "Siguiente")
- **`InfoConfigurator.jsx`** — muestra la fecha de inicio en formato `dd/mm/yyyy` como texto auxiliar bajo el campo de fecha

### Fixed

- **CORS** — elimina `CORS(app, ...)` de flask-cors 6.x (dejó de añadir headers por defecto); reemplazado por `@app.before_request` (OPTIONS → 204) y `@app.after_request` (headers en todas las respuestas)
- **Scripts locales** — `seed_full.py`, `seed_conditional.py`, `reset_data.py` y sus tests añadidos al `.gitignore`; seeds usan el sábado más próximo; `reset_data.py` borra `telegram_users` y `telegram_registration_codes` por defecto
- **CI** — `DummyFlask` en `test_webhook_listener.py` añade `before_request`/`after_request` como decoradores no-op; mockeados módulos faltantes en `load_webhook_module`

### Tests

- **`OnboardingTutorial.test.jsx`** — 4 tests: no activa si `recova_tutorial_done=true`, activa cuando target aparece en DOM, setea localStorage en `finished`/`skipped`
- **Total acumulado**: 339 backend + 44 frontend = 383 tests verdes

---

## [0.20.0] - 2026-03-12

### Added — Sprint 15: Onboarding Tutorial + Security Hardening

- **`specs/onboarding_tutorial_spec.md`** — SDD: tutorial paso a paso para hosts nuevos (React Joyride, 10 steps, solo una vez vía localStorage)
- **Security** — Migraciones SQL para corregir todos los warnings del Supabase Security Advisor:
  - `gold.lineup_candidates`, `gold.v_lineup_host`, `silver.v_lineup_candidatos`, `silver.v_ultimas_ediciones` → `WITH (security_invoker = on)` (respetan RLS del usuario llamante)
  - `public.set_updated_at` → `SET search_path = ''`
  - `public.confirm_lineup` → `SET search_path = silver, public`
- **Server hardening** — iptables: bloqueo externo de `:5000` (Flask) y `:5050` (renderer); solo accesibles desde redes Docker (`10.0.0.0/8`) y loopback; reglas persistidas con `iptables-persistent`
- **Server updates** — Docker CE 29.3.0, containerd.io 2.2.2, docker-compose-plugin 5.1.0, cloud-init 25.3, kernel 6.8.0-101

---

## [0.19.1] - 2026-03-12

### Added — Sprint 14: Prioridad fecha única "Solo puede hoy"

- **`scoring_engine.py`** — `has_single_date(fechas_disponibles)`: devuelve `True` si el cómico tiene exactamente una fecha disponible; `CandidateScore.is_single_date` campo persistido en `gold.solicitudes`; `build_ranking` computa y pasa `is_single_date` a `compute_score`; `persist_pending_score` incluye `is_single_date` en el INSERT/UPDATE SQL
- **`scoring_config.py`** — `_SINGLE_DATE_BONUS = 40` constante interna (no configurable); `single_date_priority_enabled: bool` toggle en `ScoringConfig`; `compute_score(is_single_date=False)` aplica el bono cuando el toggle está activo
- **`ScoringConfigurator.jsx`** — nueva sección "Prioridad fecha única" (toggle, solo en scoring básico) con descripción del efecto (+40 pts internos + badge)
- **`App.jsx`** — `is_single_date` añadido al select de `lineup_candidates`; `singleDateMode` calculado desde `openMicConfig.single_date_priority`; ambos pasados a `ExpandedView`
- **`ExpandedView.jsx`** — prop `singleDateMode`; pasa `singleDateMode` e `isSingleDate` a `ComicCard`
- **`ComicCard.jsx`** — badge rojo "Solo puede hoy" (Bangers, `#DC2626`) cuando `singleDateMode && isSingleDate`
- **Migración SQL** — `specs/sql/migrations/20260312_add_is_single_date_to_gold.sql`: columna `is_single_date boolean NOT NULL DEFAULT false` en `gold.solicitudes`; vista `gold.lineup_candidates` recreada con la nueva columna

### Tests

- **`test_scoring_engine.py`** — `test_has_single_date_detects_single_or_multiple_tokens`, `test_persist_pending_score_includes_is_single_date`, `test_build_ranking_sets_is_single_date_true_for_single_date`, `test_build_ranking_sets_is_single_date_false_for_multiple_dates`
- **`test_scoring_config.py`** — `test_from_dict_parses_single_date_priority`, `test_compute_score_applies_single_date_priority`, `test_compute_score_single_date_disabled_has_no_effect`
- **`ComicCard.test.jsx`** — 3 tests para badge "Solo puede hoy" (`singleDateMode`/`isSingleDate`)
- **Fix** `test_scoring_engine_custom.py` — helpers `_custom_config`/`_basic_config` deshabilitan `single_date_priority` para aislar tests de scoring custom
- **Total acumulado**: 339 backend + 40 frontend = 379 tests verdes

---

## [0.19.0] - 2026-03-12

### Added — Sprint 14: Flag "Puede Hoy" — Last-Minute Availability

- **`scoring_config.py`** — `apply_custom_rules` ignora cualquier regla con `field == "backup"` (el campo canónico ya no puntúa)
- **`custom_scoring_proposer.py`** — filtra `backup` de `unmapped_fields` antes de enviar a Gemini; si solo hay `backup` en la lista, no llama a Gemini
- **`scoring_engine.py`** — `CandidateScore.puede_hoy: bool`; derivado de `metadata['backup']` (truthy: `sí/si/yes/true/1`, case-insensitive); persistido en `gold.solicitudes.puede_hoy`
- **`App.jsx`** — fetch de `openMicConfig`; `isLastMinuteMode` useMemo: activo si `scoring_type==='basic'` ∨ (custom + `backup` en `field_mapping`) y `0 ≤ días_hasta_evento ≤ 1`; `puede_hoy` en select query
- **`ExpandedView.jsx`** — prop `isLastMinuteMode`; pasa `lastMinuteMode` e `isLastMinute` a `ComicCard` (solo si cómico no está seleccionado)
- **`ComicCard.jsx`** — badge ámbar "Puede hoy" (Bangers, `#EAB308`) + clase `last-minute-glow` cuando `lastMinuteMode && isLastMinute`
- **`index.css`** — `@keyframes last-minute-pulse` + `.last-minute-glow` (glow ámbar pulsante)
- **Migración SQL** — `specs/sql/migrations/20260312_add_puede_hoy_to_gold.sql`; backfill desde `silver.solicitudes.metadata->>'backup'`
- **Spec SDD** — `specs/last_minute_flag_spec.md`

### Tests

- **`test_scoring_config_custom.py`** — `test_apply_custom_rules_ignores_backup_field`, `test_apply_custom_rules_ignores_backup_but_applies_other_rules`
- **`test_custom_scoring_proposer.py`** — `test_propose_filters_out_backup_field`, `test_propose_only_backup_returns_empty_without_calling_gemini`
- **`test_scoring_engine.py`** — 8 variantes truthy de `backup` (`puede_hoy=True`), `puede_hoy=False` (No/ausente), persist SQL incluye `puede_hoy`
- **`ComicCard.test.jsx`** — 7 tests: badge visible/ausente + clase `last-minute-glow` según condiciones

---

## [0.18.5] - 2026-03-12

### Changed — UI polish: fondo rojo show + BgIcons globales + chalk underline + fixes

- **`index.css`** — `--c-bg: #8C2020` fondo rojo show mate; `--c-bg-grad` gradiente ámbar/rojo oscuro fixed; `.paint-bg` SIN `background-color` para que BgIcons sean visibles a través de la capa de textura
- **`BgIcons.jsx`** (nuevo) — 14 iconos SVG semitransparentes `position:fixed, z-index:0`; micro, estrella×4, cerveza, libreta×2, foco×2, nota musical×3; renderizado global en `main.jsx` antes de cada vista
- **`main.jsx`** — `<BgIcons />` inserado antes de `<Login />`, `<OpenMicSelector />`, `<OpenMicDetail />` y `<App />`
- **`Header.jsx`** — chalk underline SVG blanco bajo la fecha del lineup: 3 capas (dust blur, trazo 4.5px, hilo luz 1.5px)
- **`ExpandedView.jsx`** — cabecera `bg-[#3D5A3E]` verde bosque mate + `text-[#FEFDF8]` letras blancas; X-button `bg-[#3D5F6C]`
- **`ComicCard.jsx`** — info contacto (instagram, teléfono, estado) en fila separada full-width centrada; fuentes `text-base font-bold` / `text-sm uppercase tracking-widest`
- **`OpenMicSelector.jsx`** — fix: iconos de fondo `bg-[#EDE8DC]` con opacidad 80% (antes heredaban el rojo del body)

---

## [0.18.4] - 2026-03-12

### Fixed — GoogleFormBuilder lazy init

- **`google_form_builder.py`** — `__init__` ya no hace llamadas de red al arrancar; nuevo método `_ensure_services()` inicializa credenciales OAuth2 y clientes de Google API (Forms, Sheets, Drive, Script) de forma lazy la primera vez que se necesitan. Evita crash en PM2 si las variables de entorno de Google no están configuradas o el token es inválido al inicio del proceso.
- **`test_google_form_builder.py`** — stubs de `sys.modules` para `google.*` y `googleapiclient` al inicio del archivo (mismo patrón que otros tests con Gemini); tests `TestInit` actualizados para llamar `_ensure_services()` en lugar de esperar el error en el constructor.

### Tests
- **32 tests** `backend/tests/core/test_google_form_builder.py` — todos verdes (antes fallaban por falta de `google-auth` en venv de tests)
- **Total acumulado**: 321 backend + 30 frontend = 351 tests verdes

---

## [0.18.3] - 2026-03-12

### Changed — Render póster desactivado temporalmente

- **`ScoringConfigurator.jsx`** — sección "Póster del evento" ocultada (toggle, uploads, estados y `handlePosterUpload` comentados); código íntegro conservado para reactivar
- **`webhook_listener.py`** — comentario sobre `/api/render-poster`: endpoint funcional pero no expuesto desde el frontend
- **`mcp_server.py`** — nota en docstring del módulo indicando servidor fuera de uso temporal
- **n8n workflow `This.Render 2`** — nodo `HTTP (render)` eliminado; `Telegram (enviar)` cambiado de `sendPhoto` a `sendMessage` con texto de lineup (nombres + instagrams + fecha)

---

## [0.18.2] - 2026-03-12

### Changed — UI polish: Cartoon-Brutalist refinements

- **`NotebookSheet.jsx`** — pestañas del lineup con clase `paper-note` (mismo tono rugoso que la hoja); color activo vía `style={{ backgroundColor }}` para preservar la textura grain encima del color; hover sutil `#2C4A52/10` en nombres de artistas
- **`OpenMicDetail.jsx`** — pestañas Info/Scoring/Dev también con `paper-note` para coherencia visual con el rest de la interfaz
- **`OpenMicSelector.jsx`** — hover por open mic con color determinístico (array de 6 colores del sistema: petróleo, sage, ochre, terracota, deep-petrol, warm-brown); rotativo por índice, siempre igual para cada posición
- **`ComicCard.jsx`** — tarjeta restricted con fondo rojizo `#FDF0F0` y borde terracota `#A34A42` (antes gris neutro)

---

## [0.18.1] - 2026-03-11

### Changed — Cartoon-Matte Brutalist UI

- **`frontend/src/index.css`** — rediseño completo del sistema de estilos global:
  - `.paint-bg`: fondo rojo oscuro → off-white matte `#F5F5F0` con grano SVG fractal y puntos petróleo sutiles
  - `.comic-shadow`: sombra dura brutalista `4px 4px 0 #000`; hover `3px 3px + translate(1,1)`; active `1px 1px + translate(3,3)` (efecto presión física)
  - `.paper-note` / `.notebook-lines`: `background-color: #EDE8DC` matte; grano SVG fractal; líneas en sage verde `#7B8E7E`; encuadernación en petróleo `#4A6D7C`
  - `.paper-drop`: sombra hard drop-shadow sin desenfoque
  - `.paper-tape::before`: cinta ocre matte `#D4A373`
  - `.btn-back`: rectangular brutalista, hover petróleo
  - Scrollbar: thumb sage verde + borde ink, hover petróleo
  - `:focus-visible`: ring petróleo `#4A6D7C`
  - Overrides globales: `bg-[#fff8e7]` / `bg-[#fffef5]` → `var(--c-paper)`; `[class*="shadow-["]` → hard shadow
  - Nuevas utilidades: `.paper-strip`, `.shadow-hard`, `.border-ink`
  - Variables CSS: `--c-petrol`, `--c-sage`, `--c-ochre`, `--shadow-hard/med/sm/xs`, `--border-ink`
- **`frontend/tailwind.config.js`** — tokens `matte-*` para toda la paleta; presets `boxShadow` hard; font families `bangers`/`hand`

---

## [0.18.0] - 2026-03-11

### Added — Sprint 13: Smart Form Generation

- **Spec SDD** — `specs/smart_form_generation_spec.md`
- **`google_form_builder.py`** — descripción contextual al crear el form (`_build_description`); color aleatorio de paleta curada de 12 colores (`_random_form_color`, `_FORM_BG_PALETTE`); pregunta de fechas como CHECKBOX calculadas dinámicamente según cadencia (`_build_date_options`): semanal (todos los días del mes ≥ hoy), quincenal (4 fechas cada 14 días), mensual (3 fechas, mismo día del mes); omite pregunta de fechas si `cadencia == 'unico'`; `FormCreationResult.bg_color` nuevo campo; `deploy_submit_webhook` aplica `setBackgroundColor` via Apps Script
- **`webhook_listener.py`** — endpoint `POST /api/open-mic/create-form` lee `config.info` del open mic y lo pasa al builder; persiste `bg_color`, `last_date` (última fecha calculada) e `info_changed=false` en `config.form`
- **`InfoConfigurator.jsx`** — selector de cadencia (radio pills: Semanalmente/Quincenalmente/Mensualmente/Evento único); campo `fecha_inicio` (date input); popup modal ⚠️ al guardar si ya existe un form creado; persiste `form.info_changed=true` automáticamente
- **`FormWarningBadges.jsx`** (nuevo) — badge ⚠️ cuando `info_changed=true`; badge 🗓️ cuando `last_date` ≤ 7 días o en el pasado; con tooltips descriptivos
- **`ScoringConfigurator.jsx`** — `FormWarningBadges` integrado en el título de la sección Google Form

### Tests

- **9 tests** `backend/tests/core/test_google_form_builder.py` — `_build_description` (2), `_random_form_color` (1), `_build_date_options` (4), `_add_questions` con info (2) — todos verdes
- **10 tests** `frontend/src/test/OpenMicDetail.test.jsx` — InfoConfigurator cadencia/fecha/popup (5) + FormWarningBadges badges (5) — todos verdes
- **Fix** `ScoringTypeSelector.test.jsx` — actualizado para reflejar eliminación del `disabled` (v0.17.5)
- **Total acumulado**: 321 backend + 30 frontend = 351 tests verdes

---

## [0.17.9] - 2026-03-10

### Fixed — seguridad: autenticación en endpoint form-submission

- **`webhook_listener.py`** — añadido `_is_authorized()` al endpoint `POST /api/form-submission`; cualquier petición sin header `X-API-Key` válido recibe 401. El endpoint era accesible sin autenticación, permitiendo inyectar solicitudes falsas en cualquier open mic.
- **`google_form_builder.py`** — template de Apps Script actualizado para incluir `"X-API-Key": API_KEY` en la cabecera del `UrlFetchApp.fetch`; la clave se bake-in desde `WEBHOOK_API_KEY` en el momento de desplegar el script.
- **`test_form_submission.py`** — todos los tests actualizados con header `X-API-Key`; añadido test `test_form_submission_unauthorized` que verifica el 401.

---

## [0.17.8] - 2026-03-08

### Fixed — pipeline Gemini para tipografía del cartel

- **`mcp_server.py`** — conectado el pipeline completo: si hay `dirty_image_url` en el config del open_mic, `GeminiDetector` analiza el cartel sucio y detecta posición, tamaño y color exactos de cada `COMICO_N`; `render_on_anchors` estampa los nombres reales sobre el cartel limpio con esa tipografía. Fallback a `PosterComposer` si Gemini falla o no detecta anchors.

---

## [0.17.7] - 2026-03-08

### Fixed — mcp_server usa base_image_url del open_mic config

- **`mcp_server.py` `execute_render`** — ahora lee `open_mic_id` del payload y busca `config.poster.base_image_url` en Supabase; descarga la imagen a tempfile y la pasa a `PosterComposer`; fallback a template local si falla. También soporta `intent.reference_image_url` directo
- **n8n `LineUp.json`** — "HTTP (render)" actualizado para llamar al endpoint real de producción (`/tools/render_lineup` en `recova-renderer:5050`) e incluir `open_mic_id` en el payload

---

## [0.17.6] - 2026-03-08

### Fixed — validación persistente + lineup exacto en cartel

- **`isValidated` persistente** — inicializado desde `localStorage` (`validated_${openMicId}`) para sobrevivir remounts del componente; guardado al validar, borrado al "Cambiar"
- **`upsert_confirmed_lineup`** — añadido logging del error para diagnóstico; ya no silencioso
- **Lineup exacto en cartel** — `validateLineup` incluye `lineup: [{name, instagram}]` en el payload del webhook a n8n con los 5 cómicos exactamente como los seleccionó el host
- **n8n `Map Payload`** — usa `webhookBody.lineup` si viene en el payload (fuente de verdad: selección del host); cae en query DB solo si no viene el lineup

---

## [0.17.5] - 2026-03-08

### Fixed — 4 bugs post-deploy

- **Poster viejo** — `handlePosterUpload` añade `?v=Date.now()` a la URL pública de Supabase Storage para romper la caché del CDN al re-subir imagen
- **Nombres extra en cartel** — n8n "Get Approved Comics": añadido filtro `open_mic_id` para no traer cómicos de otros open mics con la misma fecha; corregido `=eq.` → `eq.` en todos los query params (el `=` extra generaba URLs mal formadas)
- **Validar de nuevo al volver** — `upsert_confirmed_lineup` y `setIsValidated(true)` se ejecutan ahora ANTES del webhook a n8n; n8n pasa a ser fire-and-forget → el estado validado persiste aunque n8n falle
- **Scoring personalizado bloqueado** — eliminado el `disabled` en la opción "Scoring personalizado" de `ScoringTypeSelector`; ahora se puede seleccionar siempre y el aviso de "analiza tu formulario" aparece como hint descriptivo cuando aún no hay `field_mapping`

---

## [0.17.4] - 2026-03-08

### Fixed — Telegram render: chat_id vacío + poster viejo

- **n8n `LineUp.json`** — "Get Telegram chat_id": `$json[0].proveedor_id` → `$json.proveedor_id` (n8n ya divide los items, `$json[0]` era `undefined` → lookup fallaba → `chat_id` vacío)
- **n8n `LineUp.json`** — "HTTP (render)": añadido `open_mic_id` al body del render para que el backend sepa qué plantilla usar
- **`render_poster` endpoint** — si llega `open_mic_id`, busca `config.poster.base_image_url` en Supabase, descarga la imagen a un temp file y la pasa a `PosterComposer`; si falla, usa la imagen local como fallback

---

## [0.17.3] - 2026-03-08

### Fixed — UX Telegram en móvil/tablet

- **`OpenMicSelector.jsx`** — detección de dispositivo móvil/tablet via `navigator.userAgent` + `maxTouchPoints` (iPad)
- **Modal Telegram en móvil** — en lugar del QR (imposible de escanear desde el mismo dispositivo), se muestran dos botones: "Sí, abrir Telegram" (deep link directo a `t.me`) y "No tengo Telegram — Descargar" (enlaza a `telegram.org`)
- **Desktop** — comportamiento sin cambios: QR + instrucciones de escaneo

---

## [0.17.2] - 2026-03-08

### Fixed — Correcciones UI post-deploy

- **Crear Open Mic** — día de la semana y hora son ahora campos obligatorios en el formulario de creación; se guardan en `config.info`
- **Poster** — sección dividida en dos uploads: "imagen limpia" (`poster.base_image_url`) e "imagen sucia" (`poster.dirty_image_url`) para que la IA analice el diseño original; aviso de funcionalidad en pruebas (banner amarillo)
- **Sin scoring** — "Slots disponibles" ahora siempre visible, independientemente del tipo de scoring
- **Telegram** — icono semioculto tras el primer uso (más pequeño y con opacidad reducida); soporte para usuarios con múltiples organizaciones (selector de org en el modal)
- **ComicCard** — clic en la categoría ya activa (gold/priority/restricted) la resetea a `standard`; `CATEGORY_OPTIONS` ampliado para incluir `standard` y así el reseteo no quedaba bloqueado por el guard
- **ComicCard** — selector de género M / F / NB en la ficha expandida de cada cómico; propagado via `onUpdateGenero` desde `ExpandedView` y `App`
- **Header lineup** — fecha del evento en `font-['Bangers']` blanco y legible sobre fondo oscuro
- **NotebookSheet** — eliminada pestaña "Config" de la vista de validación del lineup
- **Candidatos** — eliminada conversión forzada `standard → priority` en `fetchCandidates`; los cómicos con categoría `standard` ahora se muestran correctamente en lugar de aparecer todos como "Preferred"

---

## [0.17.1] - 2026-03-08

### Fixed — Hotfixes post-deploy

- **Auth JWT** — `_is_authenticated_user` reemplazado de `jwt.decode` (HS256) a `supabase.auth.get_user()`: Supabase usa ES256 en proyectos nuevos y PyJWT no puede verificarlo sin la clave pública
- **`silver.solicitudes`** — añadida constraint unique `(comico_id, open_mic_id, fecha_evento)` requerida por el `ON CONFLICT` del script de ingesta multi-tenant
- **`App.jsx`** — `schema('silver')` en query `lineup_slots` (devolvía 404 al buscar en schema `public`)
- **`App.jsx`** — `open_mic_id` añadido al body del webhook n8n para que el workflow pueda hacer lookup del `telegram_user_id`
- **`LineUp.json`** — workflow actualizado con nodos "Get Host proveedor_id" y "Get Telegram chat_id" para obtener el `chat_id` de Telegram del host via `open_mics → telegram_users`

---

## [0.17.0] - 2026-03-08

### Added — Sprint 12: Dev Tools Panel

- **Spec SDD** — `specs/dev_tools_spec.md`
- **`dev_users_pool.py`** — pool de 100 usuarios de prueba con campos variados (`nombre`, `instagram`, `telefono`, `experiencia_raw`, `disponibilidad_ultimo_minuto`, `origen_conocimiento`); función `get_random_users(n)`
- **`POST /api/dev/seed-open-mic`** — siembra 10 usuarios aleatorios del pool en un open mic; genera fechas futuras en formato `DD-MM-YY`; marca `config.seed_used=true` para evitar repetición; auth via Supabase JWT (`auth.get_user`)
- **`POST /api/dev/trigger-ingest`** — lanza `bronze_to_silver_ingestion.py` via `subprocess.Popen`; auth Supabase JWT
- **`POST /api/dev/trigger-scoring`** — ejecuta `execute_scoring(open_mic_id)` directamente; auth Supabase JWT
- **`DevToolsPanel.jsx`** (nuevo) — panel con 3 botones: Poblar datos, Forzar ingesta, Forzar scoring; JWT via `supabase.auth.getSession()`; toast 4s; spinner de carga
- **`OpenMicDetail.jsx`** — añadida pestaña "Dev" en la vista Configurar que monta `DevToolsPanel`
- **10 tests** `backend/tests/test_dev_tools.py` — todos verdes

### Added — Sprint 11: n8n Integration

- **Spec SDD** — `specs/forms_batch_ingest_spec.md`, `specs/render_poster_spec.md`
- **`POST /api/ingest-from-forms`** — ingesta batch desde Google Forms con deduplicación por cursor `last_form_ingestion_at`; mapeo canónico → bronze
- **`POST /api/render-poster`** — llama a `PosterComposer` directamente (sin MCP); devuelve PNG binario via `send_file`
- **`workflows/n8n/LineUp.json`** — workflow reescrito: Webhook → Get Comics → Map Payload → HTTP render → Telegram; usa `$env.RECOVA_BACKEND_URL` y `$env.WEBHOOK_API_KEY`
- **`Ingesta-Solicitudes.json`** actualizado para llamar `POST /api/ingest-from-forms`

### Fixed

- **Auth JWT** — `_is_authenticated_user` cambiado de `jwt.decode` (HS256) a `supabase.auth.get_user()` para soportar tokens ES256 que usa Supabase en proyectos nuevos
- **Fechas en seed** — formato corregido de ISO (`YYYY-MM-DD`) a `DD-MM-YY` que espera `parse_event_dates`
- **`silver.solicitudes`** — añadida constraint unique `(comico_id, open_mic_id, fecha_evento)` requerida por el `ON CONFLICT` del script de ingesta
- **`App.jsx`** — añadido `schema('silver')` en query `lineup_slots` que devolvía 404 al buscar en schema `public`

### Tests

- **Total acumulado**: ~300 tests verdes (backend + frontend)

---

## [0.15.0] - 2026-03-07

### Added — Sprint 10: Scoring Inteligente Custom

- **Spec SDD** — `specs/custom_scoring_spec.md`
- **`CustomRule` dataclass** en `scoring_config.py` — regla con `field`, `condition` (`equals`), `value`, `points`, `enabled`, `description`; método `matches(metadata)` insensible a mayúsculas
- **`ScoringConfig.apply_custom_rules(metadata)`** — suma los puntos de las reglas activas que coinciden; devuelve 0 si `scoring_type != 'custom'`
- **`custom_scoring_proposer.py`** — clase `CustomScoringProposer`: envía los campos no mapeados a Gemini 2.5 Flash y recibe una lista de reglas propuestas; devuelve `[]` si la lista de campos está vacía (sin llamada a Gemini); strip de markdown fences; `ValueError` en JSON inválido
- **`POST /api/open-mic/propose-custom-rules`** — carga config del open mic, extrae campos sin mapear, llama a `CustomScoringProposer`, guarda reglas en `config.custom_scoring_rules` via RPC `update_open_mic_config_keys`
- **`scoring_engine.py`** — `SilverRequest.metadata` (nuevo campo, leer `COALESCE(s.metadata, '{}')` de BD); tras calcular `compute_score` se suma `config.apply_custom_rules(request.metadata)`
- **`CustomScoringConfigurator.jsx`** (nuevo) — lista de reglas con toggle (`role="switch"`) y slider de puntos (`min=-50`, `max=50`, `step=5`); estado vacío con botón "Proponer reglas automáticas"
- **`ScoringConfigurator.jsx`** — sección de formulario (URL + análisis) movida a la pestaña Scoring; renderizado condicional por `scoring_type`:
  - `none`: solo `ScoringTypeSelector`
  - `basic`: `ScoringTypeSelector` + form + slots + categorías + recencia + boost + paridad + poster
  - `custom`: `ScoringTypeSelector` + subir form + `CustomScoringConfigurator` + slots + categorías + paridad + poster

### Fixed

- **`ScoringTypeSelector.jsx`** — cambiado `supabase.rpc()` → `supabase.schema('silver').rpc()` (la función `update_open_mic_config_keys` está en schema `silver`, no `public`); corregía un bug donde seleccionar un tipo no persistía
- **`ScoringConfigurator.jsx`** — `onChanged` del `ScoringTypeSelector` cambiado de `onSaved` a `fetchConfig`; `onSaved` llamaba a `setView('info')` y redirigía al hub al cambiar el tipo
- **Variables de entorno en `handlePropose`** — corregidas de `VITE_API_KEY`/`VITE_API_URL` a `VITE_WEBHOOK_API_KEY`/`VITE_BACKEND_URL`; eliminaba el error "Error de red al proponer reglas"
- **`OpenMicDetail.jsx`** — eliminada sección Google Form duplicada (movida a Scoring tab); limpieza de estados e imports innecesarios

### Tests

- 5 tests `backend/tests/core/test_custom_scoring_proposer.py` — todos verdes
- 6 tests `backend/tests/core/test_scoring_config_custom.py` — todos verdes
- 7 tests `backend/tests/test_propose_custom_rules_endpoint.py` — todos verdes
- 4 tests `backend/tests/test_scoring_engine_custom.py` — todos verdes
- 6 tests `frontend/src/test/CustomScoringConfigurator.test.jsx` — todos verdes
- **Total acumulado**: ~268 tests verdes (248 backend + 20 frontend)

---

## [0.14.0] - 2026-03-07

### Added — Sprint 9: Smart Form Ingestion

- **Spec SDD** — `specs/smart_form_ingestion_spec.md`
- **`form_ingestor.py`** — clase `FormIngestor`: lee preguntas y respuestas de cualquier Google Form via Forms API v1 (sin necesidad de Sheet vinculado)
  - `get_form_questions(form_id)` → lista `[{question_id, title, kind}]`
  - `get_responses(form_id, field_mapping)` → campos canónicos + `metadata_extra` para campos no mapeados
- **`form_analyzer.py`** — clase `FormAnalyzer`: envía títulos de preguntas a Gemini 2.5 Flash y recibe `{titulo → campo_canónico | null}`; strip de markdown fences; `ValueError` en JSON inválido
- **`POST /api/open-mic/analyze-form`** — orquesta `FormIngestor` + `FormAnalyzer`, guarda `field_mapping` y `external_form_id` en `silver.open_mics.config` via RPC, devuelve métricas de cobertura
- **`ScoringTypeSelector.jsx`** (nuevo) — radio pills `none / basic / custom`; `custom` deshabilitado si no hay `field_mapping`; persiste via RPC `update_open_mic_config_keys`
- **`OpenMicDetail.jsx`** — sección Google Form ampliada: campo URL/ID + botón "Analizar campos" + badge con resultado (N de M campos mapeados + lista sin mapeo)
- **`ScoringConfigurator.jsx`** — integra `ScoringTypeSelector` en subtab Scoring
- **`frontend/src/utils/formUtils.js`** — `extractFormId(urlOrId)`: extrae el ID de una URL de Google Forms o lo devuelve limpio
- **Migración** — `specs/sql/migrations/20260307_smart_form_ingestion.sql`:
  - `ALTER TABLE silver.solicitudes ADD COLUMN metadata JSONB DEFAULT '{}'`
  - RPC `silver.update_open_mic_config_keys(p_open_mic_id, p_keys)` — merge JSONB seguro
- **34 tests** — 9 `test_form_ingestor.py` + 5 `test_form_analyzer.py` + 6 `test_analyze_form_endpoint.py` + 7 `formUtils.test.js` + 7 `ScoringTypeSelector.test.jsx` — todos verdes
- **Setup Vitest** — `vitest` + `@testing-library/react` + `happy-dom` (jsdom@28 incompatible con ESM)

### Changed

- Google OAuth scopes ampliados: añadidos `forms.body.readonly` y `forms.responses.readonly`
- `google_oauth_setup.py` actualizado con los nuevos scopes; refresh token regenerado y desplegado en servidor

### Fixed

- `POST /api/open-mic/analyze-form`: cambiado `sb.rpc()` → `sb.schema("silver").rpc()` para evitar PGRST202 (función en schema `silver`, no `public`)

---

## [0.13.0] - 2026-03-07

### Added — Sprint 8: Registro Abierto con Google OAuth

- **`LoginScreen.jsx`** — reemplaza magic link por botón "Continuar con Google" (OAuth2)
- **`OnboardingScreen.jsx`** (nuevo) — captura el nombre del venue en el primer login; llama RPC `silver.onboard_new_host`
- **`main.jsx`** — nuevo estado `onboarding` entre `no-session` y `ready`; `checkMembership` detecta si el usuario ya tiene proveedor
- **RPC `silver.onboard_new_host(p_nombre_comercial)`** — crea `silver.proveedores` + `silver.organization_members` (rol `host`); `SECURITY DEFINER`, idempotente, slug generado y sin colisiones
- **Migración** — `specs/sql/migrations/20260307_onboard_new_host.sql`
- **11 tests TDD** en `backend/tests/core/test_onboard_new_host.py` — 11/11 verdes

### Changed

- Cualquier usuario con cuenta Google puede registrarse (antes solo hosts pre-registrados via whitelist)
- `Auth` en tabla Stack actualizada: magic link → Google OAuth

---

## [0.12.0] - 2026-03-07

### Added — Sprint 7: Poster Renderer (Gemini Flash Vision)

- **Spec SDD** — `specs/poster_detector_spec.md`
- **`poster_detector_base.py`** — tipos compartidos: `PlaceholderAnchor`, `AbstractDetector`, función pura `render_on_anchors`
- **`poster_detector_gemini.py`** — `GeminiDetector`: envía el PNG sucio a Gemini 2.5 Flash Vision, recibe JSON con coordenadas/tamaño/color de cada placeholder `COMICO_N`, renderiza sobre PNG limpio con Pillow
- **`backend/scripts/compare_poster_renderers.py`** — script CLI de prueba: `--dirty`, `--clean`, `--names`, `--date`, `--output`
- **Assets** — `backend/assets/templates/base_poster_clean.png` + `base_poster_dirty.png`
- **8 tests** en `backend/tests/core/test_poster_detector_gemini.py` — 8/8 verdes
- **`google-genai>=1.0.0`** añadido a `requirements.txt`
- **`GEMINI_API_KEY`** añadida a `.env` y `.env.example`

### Decision log
- EasyOCR evaluado y descartado: detectó 2/5 placeholders sobre fondo rojo complejo
- Gemini 2.5 Flash detectó los 5/5 con posiciones correctas en el primer intento

---

## [0.11.1] - 2026-03-07

### Changed — Consolidación de variables de entorno

- Todas las variables de entorno unificadas en un único `.env` raíz (antes divididas entre `backend/.env` y raíz)
- `backend/.env` eliminado
- `webhook_listener.py`, `bronze_to_silver_ingestion.py`, `scoring_engine.py`: `load_dotenv()` actualizado para apuntar explícitamente al `.env` raíz via `Path(__file__).parents[N] / ".env"`
- `.env.example` raíz reescrito como fuente única de verdad con todas las variables documentadas
- `backend/.env.example` eliminado (redundante)
- `frontend/.env.example` completado con `VITE_BACKEND_URL`, `VITE_WEBHOOK_API_KEY`, `VITE_N8N_WEBHOOK_URL`

---

## [0.11.0] - 2026-03-07

### Added — Sprint 6: Ingesta Multi-Tenant + Scripts de Utilidad

#### Backend — Ingesta desde Google Sheets
- `POST /api/ingest-from-sheets`: ingesta batch multi-tenant — itera todos los open mics con `sheet_id`, lee filas pendientes via `SheetIngestor`, inserta en Bronze y lanza `bronze_to_silver_ingestion.py` en background; marca filas como procesadas con `n8n_procesado=si`
- `POST /api/form-submission`: ingesta individual desde Apps Script `onFormSubmit`; lookup de `proveedor_id` por `open_mic_id`, INSERT bronze, lanza ingestión
- `backend/src/core/sheet_ingestor.py` — clase `SheetIngestor`:
  - `get_pending_rows(sheet_id)`: lee rango A:K, filtra por `Marca temporal` no vacía y `n8n_procesado` vacío; añade `_row_number` a cada dict
  - `mark_rows_processed(sheet_id, row_numbers)`: `batchUpdate` con `"si"` en columna K

#### Backend — GoogleFormBuilder actualizado
- Nuevos scopes OAuth2: `script.projects`, `forms.currentonly`, `script.external_request`, `script.scriptapp`
- `self._script = build("script", "v1", ...)` — cuarto cliente de API
- `deploy_submit_webhook(form_id, open_mic_id)`: crea proyecto Apps Script bound al form, sube código con trigger `onFormSubmit`, despliega como API executable y ejecuta `setup()`
- `_inject_open_mic_id_column`: escribe `["open_mic_id", "n8n_procesado"]` en J1:K1 (antes solo `open_mic_id`)

#### Scripts de utilidad (`backend/scripts/`)
- `seed_conditional.py`: lee open mics existentes; para cada uno sin solicitudes inserta 10 cómicos aleatorios con bronze+silver solicitudes; skippea los que ya tienen datos
- `seed_full.py`: crea un escenario completo desde cero — 1 proveedor + 3 open mics + 30 cómicos distintos (10 por open mic) con solicitudes en bronze y silver
- `reset_data.py`: TRUNCATE de todas las tablas bronze/silver/gold con backup CSV previo; flags `--yes`, `--include-auth`, `--no-backup`

#### n8n
- `workflows/n8n/Ingesta-Solicitudes.json` reescrito (multi-tenant):
  - Schedule Trigger 09:00 → `POST https://api.machango.org/api/ingest-from-sheets` (URL hardcodeada)
  - → Clasificador de género batch (Gemini): obtiene cómicos con `genero=unknown`, clasifica con LLM, PATCH en `silver.comicos`

#### Spec y Tests
- `specs/ingest_from_sheets_spec.md`: SDD de `POST /api/ingest-from-sheets`
- `specs/seed_scripts_spec.md`: SDD de los tres scripts de utilidad
- `backend/tests/test_form_submission.py`: 7/7 tests verdes
- `backend/tests/test_ingest_from_sheets.py`: 12/12 tests verdes
- `backend/tests/scripts/test_seed_conditional.py`: 7/7 tests verdes
- `backend/tests/scripts/test_seed_full.py`: 8/8 tests verdes
- `backend/tests/scripts/test_reset_data.py`: 9/9 tests verdes
- `backend/tests/core/test_google_form_builder.py`: actualizado para cliente `script` (4 APIs)

### Fixed
- `test_google_form_builder.py`: `KeyError: 'script'` — `_build_side_effect` ahora incluye el cliente `script`; test `test_builds_three_api_clients` actualizado a `{"forms", "sheets", "drive", "script"}`
- `test_ingest_from_sheets_no_open_mics`: early return antes de instanciar `SheetIngestor` evita error de credenciales faltantes en tests

---

## [0.10.0] - 2026-03-06

### Added — Sprint 5: Validación de Lineup via Telegram

#### Backend
- `POST /api/lineup/prepare-validation`: calcula próximo evento (`_next_event_datetime`), ejecuta scoring, genera token UUID en `silver.validation_tokens`, devuelve `lineup + validate_url`
- `GET /api/validate-view/lineup?token=xxx`: valida token, devuelve candidatos e `is_validated`
- `POST /api/validate-view/validate`: valida token, llama `gold.validate_lineup` + `silver.upsert_confirmed_lineup`, elimina token
- `_next_event_datetime(dia_semana, hora)`: calcula próxima ocurrencia semanal; devuelve `None` si el show ya empezó hoy
- Endpoints `/api/validate-view/*` sin autenticación API key (acceso por token UUID)

#### DB
- Migración `specs/sql/migrations/20260306_validation_tokens.sql`: tabla `silver.validation_tokens` (token UUID, host_id, open_mic_id, fecha_evento, expires_at)

#### Frontend
- `frontend/src/components/ValidateView.jsx`: vista standalone de validación (sin auth de sesión)
  - Estados: loading → error | ready | validated
  - Lista de candidatos con toggle (máx 5 seleccionados)
  - Sello "VALIDADO" animado al confirmar
  - Misma estética papel arrugado (paper-drop/tape/rough/notebook-lines)
- `frontend/src/main.jsx`: ruta `/validate` → `<ValidateView />` (sin login)

#### n8n
- `workflows/n8n/Scoring & Draft.json` reconstruido (multi-tenant):
  - Schedule Trigger diario 10:00
  - Obtiene todos los hosts desde `silver.telegram_users`
  - Por cada host: obtiene open mics vía `/mcp/open-mics`
  - `Code (flatten)`: expande 1 host en N items (uno por open mic)
  - Llama `POST /api/lineup/prepare-validation` con `neverError:true`
  - Si hay `validate_url`: formatea mensaje con lineup + link y envía por Telegram
- `workflows/n8n/Test BOT.json`: `Tool_Lineup_Link` añadido al AI Agent
  - Llama `POST /api/lineup/prepare-validation` y devuelve link de validación al host
  - System prompt actualizado: host pide lineup → Tool_Lineup_Link → link (no navegar por app)

#### Spec y Tests
- `specs/telegram_validate_lineup_spec.md`: SDD completo Sprint 5
- `backend/tests/test_validate_lineup_view.py`: 12/12 tests verdes

### Fixed
- `workflows/n8n/Test BOT.json`: URL doble `==` (`=={{ ... }}` → `={{ ... }}`) en nodo `Supabase (Validar Host)1`
- `workflows/n8n/Test BOT.json`: filtro Supabase por `telegram_user_id` del usuario actual (evitaba `[{}]` vacío)
- `backend/tests/unit/test_n8n_workflows_security.py`: contrato Scoring & Draft actualizado a nuevas env vars (`RECOVA_BACKEND_URL`, `SUPABASE_URL`, `WEBHOOK_API_KEY`)

---

## [0.9.1] - 2026-03-06

### Added — Sprint 4b: Telegram Register Endpoint

#### Backend
- `POST /api/telegram/register`: procesa `/start RCV-XXXX` desde n8n
  - Valida codigo en `silver.telegram_registration_codes` (existe, no expirado, no usado)
  - Comprueba si `telegram_user_id` ya esta en `silver.telegram_users` (idempotente)
  - Si ya registrado: marca codigo usado si es necesario y responde `already_registered: true`
  - Si nuevo: INSERT en `silver.telegram_users` + marca codigo usado
  - Errores diferenciados: 404 (no encontrado), 409 (ya usado), 410 (expirado)

#### Spec y Tests
- `specs/telegram_register_spec.md`: SDD completo con logica idempotente
- `backend/tests/test_telegram_register.py`: 10/10 tests verdes

---

## [0.9.0] - 2026-03-06

### Added — Sprint 4a: Telegram QR Self-Registration

#### Frontend
- `frontend/src/components/OpenMicSelector.jsx`: icono Telegram en esquina superior derecha del card (fuera del div)
- Tooltip animado "¡Click Me!" visible solo la primera vez (persiste en `localStorage: tg_btn_seen`)
- Modal con QR code (`qrcode.react`), código `RCV-XXXX` y instrucciones paso a paso
- El código expira en 15 minutos (gestionado por BD)

#### Backend
- `POST /api/telegram/generate-code`: genera código `RCV-[A-Z0-9]{4}`, inserta en `silver.telegram_registration_codes`, devuelve `{code, qr_url}`
- Variable de entorno: `TELEGRAM_BOT_USERNAME`

#### Spec y Tests
- `specs/telegram_qr_connect_spec.md`: SDD completo del flujo de registro
- `backend/tests/test_telegram_generate_code.py`: 5/5 tests verdes

### Infraestructura
- Traefik (Coolify) configurado para proxy HTTPS: `api.machango.org → localhost:5000`
- Config: `/data/coolify/proxy/dynamic/recova-backend.yaml`
- Dominio: `machango.org` (Porkbun) — subdominio `api` apunta a VPS Hetzner `46.225.120.243`
- `VITE_BACKEND_URL` actualizado en Vercel a `https://api.machango.org`

### Fixed
- Nombre del servidor MCP: `recova_mcp_renderer` (guiones → underscores)

---

## [0.8.0] - 2026-03-06

### Added — Sprint 3: Telegram Lineup Agent ✅

#### Backend — endpoints MCP Flask
- `backend/src/triggers/webhook_listener.py`: 5 endpoints `/mcp/*` con auth `X-API-Key`
  - `GET /mcp/open-mics` — lista open mics del host via `organization_members → proveedor_id`
  - `GET /mcp/lineup` — lineup confirmado desde `silver.lineup_slots`
  - `GET /mcp/candidates` — candidatos scoring desde `gold.lineup_candidates`
  - `POST /mcp/run-scoring` — ejecuta scoring engine
  - `POST /mcp/reopen-lineup` — resetea slots de lineup
- Fix: carga de `.env` con búsqueda en múltiples rutas candidatas (`backend/.env`, `../../.env`, `../../../.env`)

#### Tests
- `backend/tests/mcp/test_lineup_mcp_endpoints.py`: 11/11 tests verdes
- Mock actualizado para query en dos pasos en `GET /mcp/open-mics`

#### Infraestructura DB
- Migración `specs/sql/migrations/20260305_telegram_users.sql`: tablas `silver.telegram_users` y `silver.telegram_registration_codes`

#### Workflow n8n
- Workflow `telegram-lineup-agent` operativo con Gemini 2.5 Flash
- 5 nodos tool (`tool_open_mics`, `tool_lineup`, `tool_candidatos`, `tool_run_scoring`, `tool_reopen_lineup`)
- Validación de host en Supabase (`silver.telegram_users`) antes de llegar al agente
- System message con regla de redirección a web cuando no hay open mics: `https://recova-project-z5zp.vercel.app`

### Fixed
- Nombres de nodos tool en n8n: solo caracteres alfanuméricos y underscores (requisito n8n)
- Nombre del servidor MCP: `recova_mcp_renderer` (guiones reemplazados por underscores)
- `SUPABASE_SERVICE_KEY` separada de `SUPABASE_KEY` (publishable) en `.env` del servidor

---

## [0.7.0] - 2026-03-05

### Added — Sprint 2: Google Forms + Integración Backend

#### Auto-creación de Google Form al crear open mic
- `backend/src/core/google_form_builder.py`: migración de service account a OAuth2 con refresh token; crea Sheet propia vía Sheets API (la Forms API no genera `linkedSheetId` por API); Sheet incluye cabeceras estándar (9 campos) + columna `open_mic_id` con ARRAYFORMULA en col J
- `backend/scripts/google_oauth_setup.py`: script de autorización OAuth2 de un solo uso para obtener el refresh token
- `backend/src/triggers/webhook_listener.py`: añade `flask-cors` (CORS habilitado para llamadas desde el navegador)
- `frontend/src/components/OpenMicSelector.jsx`: auto-crea el form en segundo plano (fire-and-forget) al insertar un nuevo open mic
- `frontend/src/components/OpenMicDetail.jsx`: botón manual "Crear Google Form" como fallback; muestra enlaces a form y sheet si ya existen en `config.form`
- `frontend/src/main.jsx`: `handleSelect` acepta `options.isNew` para navegar a vista `config` al crear un open mic nuevo

### Variables de entorno añadidas
- `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REFRESH_TOKEN` en `backend/.env`
- `VITE_BACKEND_URL`, `VITE_WEBHOOK_API_KEY` en `frontend/.env`

### Versioning
- Bump de versión a `0.7.0` en `package.json`, `pyproject.toml` y `README.md`

## [0.6.0] - 2026-03-04

### Added — Sprint 1: Pivot SaaS Multi-Tenant

#### Esquema v3 (Medallion extendido)
- `specs/sql/v3_schema.sql`: extiende Bronze/Silver/Gold con `silver.organization_members`, `silver.open_mics` (config JSONB), `silver.lineup_slots`, `confirm_lineup()` RPC y RLS por host
- `specs/sql/migrations/20260304_add_open_mic_id_to_bronze.sql`: añade `open_mic_id` a `bronze.solicitudes`
- `specs/sql/migrations/20260304_update_lineup_candidates_add_open_mic_id.sql`: añade `open_mic_id` a la view `lineup_candidates` para filtrado multi-tenant

#### Auth (magic link)
- `frontend/src/components/LoginScreen.jsx`: pantalla de login con Supabase OTP; solo hosts pre-registrados (`shouldCreateUser: false`)
- `frontend/src/main.jsx`: componente `Root` con flujo `Login → OpenMicSelector → OpenMicDetail → App`

#### Selección y creación de Open Mics
- `frontend/src/components/OpenMicSelector.jsx`: lista open mics del host vía `organization_members`; soporta roles `host` y `collaborator`; solo `host` puede crear nuevos
- `frontend/src/components/OpenMicDetail.jsx`: hub del open mic — tarjeta info (solo lectura) con resumen de config + vista de edición con `ScoringConfigurator`

#### Scoring configurable por Open Mic
- `backend/src/core/scoring_config.py`: `ScoringConfig.from_dict(open_mic_id, raw)` lee config JSONB de `silver.open_mics`; reemplaza constantes hardcodeadas
- `backend/tests/core/test_scoring_config.py`: 27 tests
- `frontend/src/components/ScoringConfigurator.jsx`: formulario React para editar config JSONB del open mic; integrado en `OpenMicDetail` y pestaña Config del Lineup

#### Scoring engine v3
- `backend/src/scoring_engine.py`: refactorizado — `execute_scoring(open_mic_id)`, penalización de recencia scoped por `open_mic_id` via `silver.lineup_slots`, usa `ScoringConfig`

#### Ingesta Bronze → Silver v3
- `backend/src/bronze_to_silver_ingestion.py`: `BronzeRecord` con `open_mic_id`, `fetch_pending_bronze_rows` filtra `open_mic_id IS NOT NULL`, `insert_silver_rows` bifurca v3/legacy
- `specs/google_form_campos_spec.md`: un Google Form por open mic, campos estandarizados
- `specs/sql/seed_data.sql`: actualizado con `silver.open_mics`, `open_mic_id` en bronze/silver

#### Frontend — aislamiento y navegación
- `frontend/src/App.jsx`: filtra `lineup_candidates` por `open_mic_id`; recibe `openMicId` y `onBack` como props
- `frontend/src/components/open-mic/Header.jsx`: botón "← Volver al Open Mic" y logout
- `frontend/src/components/open-mic/NotebookSheet.jsx`: pestaña Config integrada con `ScoringConfigurator`
- `setup_db.py`: `v3_schema.sql` y migración bronze añadidos a `SQL_SEQUENCE`

### Versioning
- Bump de versión a `0.6.0` en `package.json`, `pyproject.toml` y `README.md`

## [0.5.61] - 2026-03-03

### Fixed
- `backend/src/core/svg_composer.py` aplica reestructuración de emergencia para visibilidad de texto: root `<svg>` con `xmlns:xlink`, imagen base por `xlink:href` y bloque `<g id="overlay-text">` renderizado al final para asegurar overlay por encima del fondo.
- `backend/src/core/svg_composer.py` elimina dependencia de clase `.comic-name` en `<style>` y mueve estilos de cómicos a atributos inline en cada `<text>`.
- `backend/src/core/svg_composer.py` activa contraste extremo de validación (`fill="#00FF00"`, `stroke="#FF00FF"`, `stroke-width="6"`) para confirmar render de nombres/fecha.
- `backend/src/core/svg_composer.py` añade logging de verificación en runtime: `DEBUG: Generando {len(safe_lineup)} nombres sobre el fondo`.
- `backend/tests/core/test_svg_composer.py` actualiza aserciones al nuevo contrato (`xlink:href`, `data-text-role`, estilos inline y orden de capas).

### Changed
- `README.md`, `docs/sdd_v2_svg_renderer.md`, `docs/mcp-agnostic-renderer-spec.md` y `docs/render-api-produccion.md` documentan la fase de validación visual extrema del SDD v2.

### Versioning
- Bump de versión a `0.5.61` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.60] - 2026-03-03

### Fixed
- `backend/src/core/svg_composer.py` fuerza orden de pintado por capas para evitar texto oculto: `<image>` base se emite primero tras abrir `<svg>` y el bloque de overlay (`names_svg` + `safe_date`) se renderiza al final en `<g id="overlay-text">`.
- `backend/src/core/svg_composer.py` mantiene el overlay en blanco con trazo negro fino (`fill: #ffffff`, `stroke: #000000`, `stroke-width: 2`) y asegura que no se inyecta ningún `<rect>` intermedio entre fondo y texto.
- `backend/tests/core/test_svg_composer.py` añade prueba de orden de capas para validar que la imagen base se pinta antes del texto.

### Changed
- `README.md`, `docs/sdd_v2_svg_renderer.md`, `docs/mcp-agnostic-renderer-spec.md` y `docs/render-api-produccion.md` documentan explícitamente el orden de capas del modelo híbrido.

### Versioning
- Bump de versión a `0.5.60` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.59] - 2026-03-03

### Changed
- `backend/src/core/svg_composer.py` añade `_get_base64_image(...)` para serializar el `base_poster.png` y embeberlo como `data:image/png;base64,...` en la etiqueta `<image>`, evitando fallos de resolución `file://` en CairoSVG.
- `backend/src/core/svg_composer.py` embebe también la fuente TTF en `@font-face` como `data:font/ttf;base64,...`, eliminando dependencia de rutas absolutas para rasterización.
- `backend/src/core/svg_composer.py` incorpora caché de assets (`_base_image_base64`, `_font_base64`) para asegurar lectura única desde disco tras la primera generación.
- `backend/tests/core/test_svg_composer.py` actualiza aserciones al contrato Base64 embebido y añade prueba de caché para confirmar una sola lectura de imagen/fuente.
- `README.md`, `docs/sdd_v2_svg_renderer.md`, `docs/mcp-agnostic-renderer-spec.md` y `docs/render-api-produccion.md` documentan el modo embebido Base64 y su motivación operativa.

### Versioning
- Bump de versión a `0.5.59` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.58] - 2026-03-03

### Changed
- `backend/src/core/svg_composer.py` migra al modelo híbrido SDD v2 (`base_poster.png` + capa de texto SVG), manteniendo intacta la Safe Zone de lineup (`Y=400..1100`) y el algoritmo adaptativo de `font_size`/`y_center`.
- `backend/src/core/svg_composer.py` elimina composición de fondo por `<pattern>/<rect>/<polygon>` e inyecta la imagen base `file:///root/RECOVA/backend/assets/templates/base_poster.png` como primera capa del SVG.
- `backend/src/core/svg_composer.py` endurece validación de assets críticos con `os.path.exists()` para fuente `.ttf` y PNG base; cuando falta alguno lanza `ERR_ASSET_MISSING`.
- `backend/src/core/svg_composer.py` ajusta capa de texto dinámica para overlay con `fill: #ffffff`, `stroke: #000000` y `stroke-width: 2`.
- `backend/tests/core/test_svg_composer.py` se actualiza al nuevo contrato híbrido y añade cobertura explícita para `ERR_ASSET_MISSING`.
- `tests/test_svg_spect.py` resuelve también `base_poster.png` y pasa ambos assets (`font_path`, `base_image_path`) al compositor en ejecución local.
- `README.md`, `docs/sdd_v2_svg_renderer.md`, `docs/mcp-agnostic-renderer-spec.md` y `docs/render-api-produccion.md` documentan el modelo híbrido y la validación de assets.

### Versioning
- Bump de versión a `0.5.58` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.57] - 2026-03-03

### Added
- `backend/src/core/svg_composer.py` implementa `SVGLineupComposer` (SDD v2 §14.b) con composición vectorial nativa en lienzo `1080x1350` y exportación `SVG -> PNG` mediante `cairosvg`.
- `backend/tests/core/test_svg_composer.py` añade cobertura de capas base (fondo/patrones/polígonos), posicionamiento dentro de Safe Zone y reducción de `font-size` cuando el lineup supera 5 cómicos.
- `docs/sdd_v2_svg_renderer.md` define arquitectura V2 del renderer SVG (objetivo, algoritmo adaptativo, capas y riesgos técnicos).

### Changed
- `backend/src/core/svg_composer.py` formaliza Safe Zone de lineup en `Y=400..1100` con distribución equitativa de `y_center` por número de cómicos.
- `backend/src/core/svg_composer.py` fija header/footer fuera de Safe Zone para proteger título (`RECOVA MIC`) y fecha del evento.
- `backend/src/core/svg_composer.py` referencia fuente local absoluta `file:///root/RECOVA/backend/assets/fonts/BebasNeue.ttf`.
- `README.md`, `docs/render-api-produccion.md` y `docs/mcp-agnostic-renderer-spec.md` documentan el nuevo compositor SVG y su coexistencia con el flujo Playwright actual.
- `docs/tests-backend.md` incorpora comando focalizado para `backend/tests/core/test_svg_composer.py`.

### Versioning
- Bump de versión a `0.5.57` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.56] - 2026-03-03

### Fixed
- `backend/src/templates/catalog/active/template.html` fuerza render de fondo halftone en captura con `print-color-adjust: exact` y `-webkit-print-color-adjust: exact` dentro de `body`.
- `backend/src/core/render.py` reemplaza la espera genérica por `await page.wait_for_timeout(2000)` antes del screenshot para dar tiempo a pintar puntos, ráfagas y micrófono.
- Se mantiene viewport fijo de Playwright `1080x1350` para coherencia con el canvas CSS del cartel.

### Changed
- `backend/tests/core/test_render.py` actualiza el contrato esperado para validar `page.wait_for_timeout(2000)` en lugar de `asyncio.sleep`.
- `README.md`, `docs/render-api-produccion.md` y `docs/mcp-agnostic-renderer-spec.md` actualizan documentación de sincronización de render.

### Versioning
- Bump de versión a `0.5.56` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.55] - 2026-03-03

### Fixed
- `backend/src/templates/catalog/active/template.html` ajusta el layout para lineup de 5 nombres: `.lineup` pasa a `height: auto` y `.comico` reduce tamaño a `60px` para evitar recortes.
- `backend/src/templates/catalog/active/template.html` elimina la dependencia de imagen remota del micrófono y usa un SVG embebido (`data:image/svg+xml`) para garantizar render sin fallos de red.
- `backend/src/core/render.py` fortalece la captura Playwright con `page.goto(file://..., wait_until="networkidle")`, espera explícita `await asyncio.sleep(2)` antes del screenshot y mantiene viewport `1080x1350` alineado al CSS.
- `backend/tests/core/test_render.py` actualiza aserciones al nuevo contrato de navegación/carga (`networkidle`, pausa de 2s y viewport fijo).

### Changed
- `README.md`, `docs/render-api-produccion.md` y `docs/mcp-agnostic-renderer-spec.md` documentan el hardening visual del template activo y la nueva sincronización de captura.

### Versioning
- Bump de versión a `0.5.55` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.54] - 2026-03-03

### Changed
- `backend/src/mcp_server.py` renderiza `template.html` con `jinja2` antes de invocar Playwright, inyectando `lineup`, `event_id` y fecha (`date` / `event.date` / `metadata.date_text`) para eliminar bucles `{% for %}` en runtime de navegador.
- `backend/src/mcp_server.py` elimina la dependencia de `backend/src/core/data_binder.py` en el flujo MCP (`orchestrate_render -> execute_render`) y usa un script mínimo de sincronización (`window.renderReady = true;`).
- `backend/src/mcp_server.py` genera HTML renderizado en archivo temporal y lo limpia tras la captura para evitar artefactos residuales en `/tmp`.
- `backend/tests/mcp/test_server_integration.py` y `backend/tests/mcp/test_mcp_server_http.py` actualizan mocks del contrato `execute_render(...)` al retirar `injection_script` del flujo MCP.
- `README.md`, `docs/render-api-produccion.md` y `docs/mcp-agnostic-renderer-spec.md` documentan el nuevo pipeline server-side con Jinja2 y la retirada del Data Binder en MCP.

### Versioning
- Bump de versión a `0.5.54` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.53] - 2026-03-03

### Changed
- `backend/src/core/data_binder.py` amplía `generate_injection_js(...)` para soportar plantillas estáticas con placeholders Jinja no renderizados: limpieza de tokens `{{ ... }}` y `{% ... %}` en nodos de texto antes del screenshot.
- `backend/src/core/data_binder.py` añade mapeo dual de datos: mantiene binding por `.slot-n .name` y añade binding para plantilla activa por `.lineup .comico`, creando nodos dinámicos con los nombres del lineup recibido desde n8n.
- `backend/src/core/data_binder.py` añade inyección de fecha en selectores de evento (`.footer`, `.event-date`, `[data-event-date]`) cuando detecta placeholders de fecha en plantilla.
- `backend/tests/core/test_data_binder.py` incorpora pruebas para reglas de reemplazo de placeholders Jinja y para soporte de selectores de la plantilla activa.
- `README.md` y `docs/mcp-agnostic-renderer-spec.md` actualizan contrato operativo del Data Binder para evitar salida con variables sin sustituir.

### Versioning
- Bump de versión a `0.5.53` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.52] - 2026-03-03

### Changed
- `backend/src/mcp_server.py` alinea `POST /tools/render_lineup` al contrato de streaming directo para n8n/Telegram: elimina respuesta JSON de éxito y entrega bytes PNG con `FileResponse(path=output_path, media_type="image/png", filename="cartel.png")`.
- `backend/src/mcp_server.py` añade validación previa de archivo generado con `os.path.exists(output_path)` y error `HTTP 500` (`detail="El archivo no se generó correctamente"`) cuando falta el artefacto.
- `backend/src/mcp_server.py` mantiene fallo de motor como `HTTP 500` con detalle estructurado para diagnóstico operativo.
- `backend/tests/mcp/test_mcp_server_http.py` ajusta aserciones del error 500 al formato `HTTPException` (`response.json()["detail"]`).
- `README.md`, `docs/render-api-produccion.md` y `docs/mcp-agnostic-renderer-spec.md` actualizan contrato del endpoint MCP REST en modo streaming.

### Versioning
- Bump de versión a `0.5.52` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.51] - 2026-03-03

### Changed
- `backend/src/mcp_server.py` cambia la respuesta de `POST /tools/render_lineup` para devolver el PNG generado como stream binario (`FileResponse`, `media_type=image/png`) con filename descriptivo, evitando depender de rutas de archivo visibles fuera del contenedor.
- `backend/src/mcp_server.py` incorpora manejo explícito de fallo de render con `HTTP 500` y JSON estructurado `{ "error": "Render engine failed", "details": ... }`.
- `backend/src/mcp_server.py` documenta nota operativa de limpieza de artefactos en `/tmp` tras entrega del fichero.
- `backend/tests/mcp/test_mcp_server_http.py` actualiza aserciones al contrato binario (`image/png`, firma PNG) y añade prueba de error 500.
- `README.md`, `docs/render-api-produccion.md` y `docs/mcp-agnostic-renderer-spec.md` actualizan la documentación del endpoint MCP HTTP en modo streaming.

### Versioning
- Bump de versión a `0.5.51` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.50] - 2026-03-02

### Added
- Nueva especificación frontend `specs/frontend_lineup_notebook_spec.md` para formalizar la integración visual v0 en React/Vite sin migrar a Next.js ni TypeScript.
- Nuevos componentes visuales `jsx` en `frontend/src/components/open-mic/` (`Header`, `NotebookSheet`, `ExpandedView`, `ComicCard`, `ValidateButton`) con separación explícita entre capa de presentación y lógica de negocio.
- Campo `recoveryNotes` en la UI de curación para trazabilidad SDD durante la validación.

### Changed
- `frontend/src/App.jsx` se refactoriza a layout notebook/cartoon importado desde ZIP v0, manteniendo intacta la lógica funcional crítica: carga de candidatos desde Supabase, edición de draft, selección máxima de 5 y validación con RPC `validate_lineup`.
- `validateLineup` amplía el payload de webhook n8n con `trace: { recovery_notes: recoveryNotes }`.
- `frontend/src/index.css` incorpora estilos extraídos/adaptados de `globals.css` del diseño v0 para fondo, libreta, overlays y comportamiento visual de tarjetas restringidas.
- `docs/curacion-lineup-validacion-estados-gold-silver.md` documenta la nueva interacción de curación por pestañas y el contrato de notas de recuperación.
- `README.md` actualiza versión, fuente de verdad técnica y estructura del frontend con la nueva carpeta de componentes.

### Versioning
- Bump de versión a `0.5.50` en `package.json`, `pyproject.toml` y `README.md`.
- Bump de frontend a `0.1.8` en `frontend/package.json`.

## [0.5.49] - 2026-03-01

### Fixed
- Eliminado el origen de `import file mismatch` en CI al suprimir duplicados con el mismo nombre en rutas distintas:
  - `backend/tests/mcp/test_data_binder.py` (removido)
  - `backend/tests/mcp/test_security.py` (removido)
- Eliminado `backend/tests/unit/test_core_render.py` para mantener la Regla del Espejo: el módulo `backend/src/core/render.py` queda cubierto exclusivamente por `backend/tests/core/test_render.py`.

### Changed
- `backend/tests/core/test_data_binder.py` absorbe cobertura funcional de mapeo/privacidad (inyección de nombres y exclusión de instagram) proveniente de tests duplicados.
- `backend/tests/core/test_security.py` absorbe cobertura de esquema URL (`http/https`) y refuerza validación de `recovery_action` en timeouts de red.
- `backend/tests/core/test_render.py` incorpora verificaciones de cierre de recursos Playwright en ruta de fallo y asserts de contrato en ruta de éxito.
- `docs/tests-backend.md` se reescribe con comandos actualizados y rutas vigentes tras refactor.
- `README.md` actualiza versión, fuente de verdad técnica, path real del webhook (`backend/src/triggers/webhook_listener.py`) y esquema de repositorio.

### Removed
- `backend/tests/integration/test_supabase_storage.py` por deprecación de integración directa backend->Supabase Storage en la estrategia actual (responsabilidad movida al flujo orquestado).

### Versioning
- Bump de versión a `0.5.49` en `package.json`, `pyproject.toml` y `README.md`.

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
