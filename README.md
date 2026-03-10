# AI LineUp Architect

**Versión:** `0.17.9` · **Estado:** Desarrollo activo · **Metodología:** SDD + TDD

SaaS multi-tenant para gestión de open mics de comedia. Automatiza la recogida de solicitudes (Google Forms), el scoring con IA y la generación del cartel en PNG.

---

## Arquitectura

```mermaid
flowchart TD
    classDef google fill:#4285F4,color:#fff,stroke:#2a6dd9
    classDef supabase fill:#3ECF8E,color:#fff,stroke:#29a870
    classDef flask fill:#FF6B35,color:#fff,stroke:#cc5520
    classDef frontend fill:#61DAFB,color:#1a1a1a,stroke:#38b2cc
    classDef n8n fill:#EA4B71,color:#fff,stroke:#c73059
    classDef storage fill:#9B59B6,color:#fff,stroke:#7d3f9e

    Host(["👤 Host\n(Google OAuth)"])
    Comico(["🎤 Cómico\n(formulario)"])

    subgraph FE ["🖥️ Frontend React/Vite"]
        Login["🔐 Login"]
        Selector["📋 OpenMicSelector"]
        Detail["🎯 OpenMicDetail"]
        App["✏️ Lineup App"]
    end

    subgraph BE ["⚙️ Backend Flask :5000"]
        WH["🪝 webhook_listener"]
        FB["📝 GoogleFormBuilder"]
    end

    subgraph Renderer ["🖼️ recova-renderer :5050"]
        MCP["🎨 mcp_server\nGemini Vision + Pillow"]
    end

    subgraph Google ["🔵 Google"]
        GF["📋 Google Forms"]
        GS["📊 Google Sheets"]
    end

    subgraph Pipe ["🔄 n8n"]
        Ingesta["📥 Ingesta"]
        Scoring["🧮 Scoring"]
        Render["🎨 Render"]
    end

    subgraph DB ["🗄️ Supabase"]
        Bronze["🥉 Bronze"]
        Silver["🥈 Silver"]
        Gold["🥇 Gold"]
    end

    Storage[("☁️ Supabase Storage")]

    Comico -->|rellena| GF
    Host -->|gestiona| FE
    Selector -->|POST /create-form| WH
    WH --> FB --> GF -->|respuestas| GS

    GS -->|trigger| Ingesta -->|POST /ingest| WH
    WH --> Bronze --> Silver --> Gold --> App

    App -->|valida lineup| Scoring --> Silver
    App -->|dispara render| Render -->|POST /tools/render_lineup| MCP --> Storage

    FE <-->|auth + data| DB

    class GF,GS google
    class Bronze,Silver,Gold supabase
    class WH,FB flask
    class Login,Selector,Detail,App frontend
    class Ingesta,Scoring,Render n8n
    class Storage storage
```

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Frontend | React + Vite + Tailwind |
| Backend | Python / Flask :5000 |
| Renderer | mcp_server.py — FastAPI :5050 (Gemini Vision + Pillow) |
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
│   │   ├── triggers/         # webhook_listener.py (Flask :5000)
│   │   ├── bronze_to_silver_ingestion.py
│   │   ├── scoring_engine.py
│   │   └── mcp_server.py     # Renderer API (FastAPI :5050)
│   └── tests/
│       ├── core/             # Tests módulos core
│       ├── mcp/              # Tests renderer
│       ├── scripts/          # Tests scripts utilidad
│       └── unit/             # Tests unitarios generales
├── frontend/
│   └── src/
│       ├── components/       # OpenMicSelector, OpenMicDetail, ScoringConfigurator…
│       ├── App.jsx           # Lineup app (curación)
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
PYTHONPATH=. python -m backend.src.mcp_server                  # Renderer :5050

# Frontend
cd frontend && npm install && npm run dev
```

Variables de entorno: [`docs/setup.md`](docs/setup.md)

---

## Tests

```bash
source backend/venv/bin/activate
PYTHONPATH=. pytest backend/tests/        # 312 tests backend
cd frontend && npm test                   # 20 tests frontend
```

---

## Documentación

| Documento | Descripción |
|-----------|-------------|
| [`docs/architecture.md`](docs/architecture.md) | Variables de entorno y capas |
| [`docs/setup.md`](docs/setup.md) | Setup local y producción |
| [`docs/sprints.md`](docs/sprints.md) | Historial de sprints y roadmap |
| [`CHANGELOG.md`](CHANGELOG.md) | Historial de versiones |
