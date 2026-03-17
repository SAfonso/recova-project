const path = require('path');

const PROJECT_ROOT = process.env.PROJECT_ROOT || path.resolve(__dirname);

module.exports = {
  apps: [
    {
      name: "webhook-ingesta",
      cwd: PROJECT_ROOT,
      script: path.join(PROJECT_ROOT, "backend/src/triggers/webhook_listener.py"),
      interpreter: path.join(PROJECT_ROOT, "venv/bin/python3"),
      env: {
        PYTHONPATH: PROJECT_ROOT,
        PYTHONUNBUFFERED: "1"
      },
      autorestart: true,
      max_restarts: 10,
      time: true
    }
  ]
};
