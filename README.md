# AI LineUp Architect

**Versión:** `0.34.3` · **Estado:** Desarrollo activo · **Metodología:** SDD + TDD

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
| Procesos | Docker Compose en VPS Ubuntu (Hetzner) · Traefik — `api.machango.org` |
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
│   │   │   ├── webhook_listener.py   # App factory + /health endpoint
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
├── Dockerfile                # Imagen backend (Gunicorn, 1 worker)
├── docker-compose.yml        # Servicio backend con healthcheck
├── .dockerignore             # Exclusiones para build
└── CHANGELOG.md
```

---

## Inicio rápido

```bash
# Backend (Docker — recomendado)
cp .env.example .env   # rellenar valores
docker compose up -d   # Flask :5000 via Gunicorn

# Backend (local, sin Docker)
pip install -r requirements.txt
PYTHONPATH=. python backend/src/triggers/webhook_listener.py

# Frontend
cd frontend && npm install && npm run dev
```

Variables de entorno: [`docs/setup.md`](docs/setup.md)

---

## Tests

```bash
source backend/venv/bin/activate
PYTHONPATH=. pytest backend/tests/   # 445 tests backend
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
| [`docs/sequence-diagram.md`](docs/sequence-diagram.md) | Diagramas de secuencia Mermaid (flujo completo) |
| [`CHANGELOG.md`](CHANGELOG.md) | Historial de versiones |

---

