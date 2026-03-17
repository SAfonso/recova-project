# AI LineUp Architect

**Versión:** `0.26.0` · **Estado:** Desarrollo activo · **Metodología:** SDD + TDD

SaaS multi-tenant para gestión de open mics de comedia. Automatiza la recogida de solicitudes (Google Forms), el scoring con IA y la notificación del lineup por Telegram.

---

## Arquitectura

![Stack del sistema](docs/architecture.svg)

![Flujo de datos](docs/dataflow.svg)

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Frontend | React + Vite + Tailwind |
| Backend | Python / Flask :5000 (8 blueprints) |
| Base de datos | Supabase (PostgreSQL — Bronze / Silver / Gold) |
| Auth | Supabase (Google OAuth) |
| Orquestación | n8n |
| Formularios | Google Forms + Sheets API (OAuth2) |
| Procesos | PM2 en VPS Ubuntu (Hetzner) · Traefik — `api.machango.org` |
| Bot Telegram | `@ailineup_bot` (n8n + Gemini 2.5 Flash) |

---

## Estructura

```
recova-project/
├── backend/
│   ├── assets/               # Fuentes y posters base (Pillow)
│   ├── scripts/              # OAuth2, seed, reset
│   ├── src/
│   │   ├── core/             # Módulos: scoring, render, forms, security
│   │   ├── triggers/
│   │   │   ├── webhook_listener.py   # App factory (~36 líneas)
│   │   │   ├── shared.py             # Auth, constantes, helpers
│   │   │   └── blueprints/           # 8 blueprints por dominio
│   │   │       ├── n8n.py            # /ingest, /scoring
│   │   │       ├── ingestion.py      # /api/form-submission, ingest-from-*
│   │   │       ├── form.py           # /api/open-mic/create-form, analyze, propose
│   │   │       ├── lineup.py         # /api/lineup/*, validate-view/*
│   │   │       ├── mcp_agent.py      # /mcp/* (Telegram Agent)
│   │   │       ├── telegram.py       # /api/telegram/*
│   │   │       ├── dev.py            # /api/dev/*
│   │   │       └── poster.py         # /api/render-poster
│   │   ├── bronze_to_silver_ingestion.py
│   │   └── scoring_engine.py
│   └── tests/
│       ├── core/             # Tests módulos core
│       ├── mcp/              # Tests MCP agent endpoints
│       ├── scripts/          # Tests scripts utilidad
│       └── unit/             # Tests unitarios generales
├── frontend/
│   └── src/
│       ├── components/       # OpenMicSelector, OpenMicDetail, ScoringConfigurator…
│       ├── hooks/            # useCandidates, useEdits, useValidation
│       ├── App.jsx           # Lineup app — orquestador (~120 líneas)
│       └── main.jsx          # Root: Login → Selector → Detail → App
├── specs/                    # Specs SDD + esquemas y migraciones SQL
├── docs/                     # Documentación técnica
├── workflows/n8n/            # Workflows exportados
└── CHANGELOG.md
```

---

## Inicio rápido

```bash
# Backend
pip install -r requirements.txt
PYTHONPATH=. python backend/src/triggers/webhook_listener.py   # Flask :5000

# Frontend
cd frontend && npm install && npm run dev
```

Variables de entorno: [`docs/setup.md`](docs/setup.md)

---

## Tests

```bash
source backend/venv/bin/activate
PYTHONPATH=. pytest backend/tests/   # 365 tests backend
cd frontend && npm test              # 70 tests frontend
```

---

## Documentación

| Documento | Descripción |
|-----------|-------------|
| [`docs/architecture.md`](docs/architecture.md) | Variables de entorno y capas |
| [`docs/setup.md`](docs/setup.md) | Setup local y producción |
| [`docs/sprints.md`](docs/sprints.md) | Historial de sprints y roadmap |
| [`docs/openapi.yaml`](docs/openapi.yaml) | Especificación OpenAPI 3.0 (22 rutas) |
| [`CHANGELOG.md`](CHANGELOG.md) | Historial de versiones |

---

## Deuda técnica — Sprints de mejora

Revisión técnica (2026-03-16): Sprints A–D completados. Revisión 2 (2026-03-17): 3 red flags → Sprints E–G.

<details>
<summary>Sprints A–D (completados) ✅</summary>

| Sprint | Descripción |
|--------|-------------|
| ~~A~~ | ~~Bugs funcionales~~ — A1 gender_parity fix + A2 falso positivo documentado ✅ |
| ~~B~~ | ~~Seguridad~~ — B2 CORS restringido + B3 singleton Supabase ✅ |
| ~~C~~ | ~~Arquitectura~~ — C1+C2 God File → 8 blueprints ✅ |
| ~~D~~ | ~~Calidad~~ — D1 cascada INE + D2 BD source of truth + D3 tutorial UX + D4 paths portables ✅ |
| ~~E~~ | ~~Red flags defensa~~ — E1 test e2e smoke + E2 `@validate_json` 13 endpoints + E3 score_breakdown JSONB ✅ |
| ~~F2~~ | ~~Descomponer App.jsx~~ — 534→120 líneas, 3 custom hooks + 4 componentes presentacionales ✅ |
| ~~F3~~ | ~~Rate limiting~~ — `@rate_limit` decorador in-memory por IP, headers `X-RateLimit-*`, 9 tests ✅ |
| ~~G1~~ | ~~OpenAPI spec~~ — `docs/openapi.yaml` con 22 rutas, schemas, auth y rate limiting ✅ |

</details>
