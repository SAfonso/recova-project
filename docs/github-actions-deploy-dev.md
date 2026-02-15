# GitHub Actions CD para rama `dev`

## Comando para crear la estructura local

```bash
mkdir -p .github/workflows
```

## Archivo de workflow

Crear el archivo `.github/workflows/deploy.yml` con el siguiente contenido:

```yaml
name: Deploy to Hetzner (dev)

on:
  push:
    branches:
      - dev

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Deploy over SSH
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.HOST }}
          username: root
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /root/RECOVA
            git pull origin dev
            ./venv/bin/pip install -r requirements.txt
            if pm2 describe webhook-ingesta > /dev/null 2>&1; then
              pm2 restart webhook-ingesta
            else
              pm2 start /root/RECOVA/backend/src/triggers/webhook_listener.py --name webhook-ingesta --interpreter /root/RECOVA/venv/bin/python3
            fi
```

## Secrets requeridos en GitHub

- `HOST`: IP o dominio del servidor Hetzner.
- `SSH_PRIVATE_KEY`: clave privada SSH con acceso al usuario `root`.
