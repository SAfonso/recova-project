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

Copiar y rellenar el `.env` raíz (fuente única de verdad para todo el proyecto):
```bash
cp .env.example .env
# editar .env con tus credenciales
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
python setup_db.py          # aplica esquema
python setup_db.py --seed   # seed estático (datos de ejemplo fijos)
```

### Scripts de utilidad de seed

```bash
# Rellena open mics sin solicitudes con 10 cómicos aleatorios cada uno
PYTHONPATH=. python backend/scripts/seed_conditional.py

# Crea un escenario completo desde cero: 1 proveedor + 3 open mics + 30 cómicos
PYTHONPATH=. python backend/scripts/seed_full.py

# Borra todos los datos (mantiene esquemas), con backup CSV previo
PYTHONPATH=. python backend/scripts/reset_data.py
PYTHONPATH=. python backend/scripts/reset_data.py --yes             # sin confirmación
PYTHONPATH=. python backend/scripts/reset_data.py --include-auth    # también borra telegram_users
PYTHONPATH=. python backend/scripts/reset_data.py --no-backup       # sin CSV de respaldo
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
