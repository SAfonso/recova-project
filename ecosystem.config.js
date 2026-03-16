module.exports = {
  apps: [
    {
      name: "webhook-ingesta",
      cwd: "/root/RECOVA",
      script: "/root/RECOVA/backend/src/triggers/webhook_listener.py",
      interpreter: "/root/RECOVA/venv/bin/python3",
      env: {
        PYTHONPATH: "/root/RECOVA",
        PYTHONUNBUFFERED: "1"
      },
      autorestart: true,
      max_restarts: 10,
      time: true
    }
  ]
};
