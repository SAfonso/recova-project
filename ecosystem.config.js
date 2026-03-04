module.exports = {
  apps: [
    {
      name: "recova-mcp-http",
      cwd: "/home/sergio/Desktop/Recova Project/recova-project",
      script: "./.venv/bin/python",
      args: "-m backend.src.mcp_server",
      interpreter: "none",
      env: {
        PYTHONUNBUFFERED: "1",
        MCP_HOST: "127.0.0.1",
        MCP_PORT: "8000"
      },
      autorestart: true,
      max_restarts: 10,
      time: true
    }
  ]
};
