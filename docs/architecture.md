# Arquitectura del sistema

**Versión:** 0.11.1

## Diagrama

```mermaid
flowchart TD
    subgraph Frontend ["Frontend (React/Vite)"]
        Login --> Selector[OpenMicSelector]
        Selector --> Detail[OpenMicDetail]
        Detail --> App[Lineup App]
    end

    subgraph Backend ["Backend (Flask :5000)"]
        WH[webhook_listener.py]
        FB[google_form_builder.py]
        WH --> FB
    end

    subgraph n8n ["n8n Orquestador"]
        Ingesta[Ingesta-Solicitudes]
        Scoring[Scoring & Draft]
        Render[LineUp / Render]
    end

    subgraph Supabase
        DB[(Bronze / Silver / Gold)]
        Storage[(Storage: posters, poster-backgrounds)]
    end

    subgraph Google
        GF[Google Forms]
        GS[Google Sheets]
    end

    subgraph Renderer ["Renderer API (:5050)"]
        Playwright[PlaywrightRenderer]
    end

    %% Flujo principal
    Selector -- "POST /api/open-mic/create-form" --> WH
    FB -- "Forms API + Sheets API (OAuth2)" --> GF
    FB -- "Sheets API" --> GS

    GF -- "respuestas → Sheet" --> GS
    GS -- "trigger" --> Ingesta
    Ingesta -- "POST /ingest" --> WH
    WH -- "bronze_to_silver_ingestion.py" --> DB

    App -- "scoring / lineup" --> DB
    App -- "valida lineup" --> Scoring
    Scoring --> DB

    App -- "POST /render-lineup" --> Playwright
    Playwright --> Storage

    Frontend -- "auth + data" --> Supabase
```

## Capas de datos (Medallion)

| Capa | Tabla principal | Rol |
|------|----------------|-----|
| Bronze | `bronze.solicitudes` | Ingesta cruda de formularios |
| Silver | `silver.open_mics`, `silver.comicos`, `silver.solicitudes` | Datos normalizados y operativos |
| Gold | `gold.lineup_candidates` (view) | Candidatos con scoring para curación |

## Servicios en producción (VPS)

| Servicio | Puerto | Proceso PM2 |
|----------|--------|-------------|
| Webhook ingesta | `:5000` | `webhook-ingesta` |
| Renderer API | `:5050` | `recova-renderer` |

## Variables de entorno clave

### `.env` (raíz — fuente única de verdad)
```
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
DATABASE_URL=
WEBHOOK_API_KEY=
BACKEND_URL=
FRONTEND_URL=
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_OAUTH_REFRESH_TOKEN=
TELEGRAM_BOT_USERNAME=
N8N_BACKEND_INGEST_URL=
N8N_BACKEND_SCORING_URL=
N8N_BACKEND_RENDER_URL=
```

### `frontend/.env` (solo variables Vite)
```
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
VITE_BACKEND_URL=
VITE_WEBHOOK_API_KEY=
VITE_N8N_WEBHOOK_URL=
```
