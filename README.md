# AI LineUp Architect

**Versión:** `0.34.5` · **Estado:** Desarrollo activo · **Metodología:** SDD + TDD

SaaS multi-tenant para gestión de open mics de comedia. Automatiza la recogida de solicitudes (Google Forms), el scoring con IA y la notificación del lineup por Telegram.

**Demo en producción:** [recova.machango.org](https://recova.machango.org)

---

## ¿Por qué existe esto?

Llevo años subiéndome a contar mis cosas en open mics de stand-up. Con el tiempo tuve la oportunidad de organizar alguno, y hablé con otros que también lo hacen. Todos coincidíamos en lo mismo: **gestionar el lineup es la parte más horrible del proceso**. Peor incluso que cuando el público no ríe.

Decidí automatizarlo, pero había partes que se me escapaban técnicamente. Hasta que llegó este máster y vi la oportunidad.

El resultado no es solo "un formulario que muestra nombres". El sistema gestiona prioridades según tus preferencias: puedes dar prioridad a los cómicos más veteranos (**lista gold**), a gente de confianza (**priority**), o directamente filtrar a ese tipo que solo hace chistes malos (**restricted**). Puedes aplicar **paridad de género** para que el lineup no sea un monolito, gracias a una IA que infiere el género a partir del nombre e Instagram — y que el host puede corregir si se equivoca. Si alguien solo puede una fecha concreta, también se pondera. Y así con varios criterios más, todos configurables.

Todo esto viene acompañado de **@ailineup_bot**, un bot de Telegram que te informa del lineup de la semana, tus open mics activos y el estado de las solicitudes — sin tener que abrir ningún panel.

---

## Funcionalidades principales

### Gestión de open mics
- Creación y configuración de múltiples open mics por organización (multi-tenant)
- Configuración de cadencia (semanal, quincenal, mensual, único), local, scoring y formulario
- Generación automática de Google Form con campos estándar, descripción contextual y color aleatorio vinculado al open mic

### Recogida y procesamiento de solicitudes
- Ingesta automática desde Google Forms vía Apps Script → webhook → arquitectura Medallion Bronze/Silver
- Deduplicación, normalización y enriquecimiento de datos (género por cascada: INE → gender-guesser → genderize.io)
- Soporte para ingesta manual desde Google Sheets y entrada directa por Telegram

### Scoring con IA
- Motor de scoring configurable por host: experiencia, paridad de género, antigüedad, disponibilidad last-minute
- Auditoría completa en `score_breakdown` JSONB — cada puntuación es trazable
- Soporte para reglas de scoring custom propuestas por Gemini a partir de campos no canónicos del formulario

### Lineup y validación
- Vista curada de candidatos con edición inline (nombre, género, experiencia)
- Validación del lineup con verificación de slots y persistencia en `silver.lineup_slots`

### Notificación por Telegram
- Bot `@ailineup_bot`: los cómicos reciben su confirmación directamente por Telegram
- Registro de usuarios vía QR/link con código temporal (15 min)
- Agente MCP con Gemini para reapertura de lineup y consultas desde Telegram

### Infraestructura y seguridad
- Auth con JWT (Supabase) en todos los endpoints sensibles; sin API keys expuestas en el frontend
- Rate limiting in-memory por endpoint; CORS manual con origin dinámico
- CD automático vía GitHub Actions → SSH → Docker Compose en VPS Hetzner

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
│   ├── assets/               # Fuentes y templates
│   ├── scripts/              # OAuth2, seed, reset
│   ├── src/
│   │   ├── core/             # Módulos: scoring, forms, security
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

