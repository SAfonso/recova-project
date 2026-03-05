# Setup y desarrollo local

## Requisitos

- Python 3.11+
- Node.js 18+
- Cuenta Supabase
- Cuenta Google Cloud (para Google Forms/Sheets)

## Backend

```bash
cd recova-project/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt   # o: pip install python-dotenv flask flask-cors supabase google-api-python-client google-auth google-auth-oauthlib
```

Crear `backend/.env`:
```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
WEBHOOK_API_KEY=<api key>
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_OAUTH_REFRESH_TOKEN=
```

Autorización OAuth2 de Google (una sola vez):
```bash
python backend/scripts/google_oauth_setup.py --client-secrets /ruta/client_secret.json
```

Arrancar Flask:
```bash
cd recova-project
source backend/venv/bin/activate
PYTHONPATH=. python backend/src/triggers/webhook_listener.py
```

## Frontend

```bash
cd recova-project/frontend
npm install
```

Crear `frontend/.env`:
```
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
VITE_BACKEND_URL=http://localhost:5000
VITE_WEBHOOK_API_KEY=<api key>
VITE_N8N_WEBHOOK_URL=https://n8n.xxx.org/webhook/...
```

Arrancar:
```bash
npm run dev
```

## Base de datos

```bash
source backend/venv/bin/activate
python setup_db.py
python setup_db.py --seed
```

## Tests

```bash
cd recova-project
source backend/venv/bin/activate
PYTHONPATH=. pytest backend/tests/ -v
```

Tests por módulo:
```bash
pytest backend/tests/core/ -v       # Tests unitarios core
pytest backend/tests/unit/ -v       # Tests unitarios generales
pytest backend/tests/mcp/ -v        # Tests MCP/render
```

## Producción (VPS)

Ver `docs/architecture.md` para puertos y servicios PM2.

```bash
pm2 start "PYTHONPATH=/root/RECOVA source /root/RECOVA/backend/venv/bin/activate && python backend/src/triggers/webhook_listener.py" --name webhook-ingesta
pm2 start "./.venv/bin/gunicorn -w 4 -b 0.0.0.0:5050 backend.src.app:app" --name recova-renderer
```
