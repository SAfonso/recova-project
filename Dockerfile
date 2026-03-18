FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY backend/ ./backend/
COPY backend/assets/ ./backend/assets/
COPY pyproject.toml .
COPY .env.example .

# Asegurar que los paquetes son importables como backend.src.*
RUN touch backend/__init__.py \
    backend/src/__init__.py \
    backend/src/triggers/__init__.py \
    backend/src/core/__init__.py

ENV PYTHONPATH=/app

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "120", \
     "backend.src.triggers.webhook_listener:app"]
