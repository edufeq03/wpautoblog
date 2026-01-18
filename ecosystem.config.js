module.exports = {
  apps: [
    {
      name: "autoblog-web",
      script: "gunicorn",
      args: "--workers 3 --bind 0.0.0.0:8000 app:app",
      interpreter: "python3",
      env: {
        NODE_ENV: "production",
      }
    },
    {
      name: "autoblog-worker",
      script: "scheduler.py",
      interpreter: "python3",
      watch: false,
      env: {
        NODE_ENV: "production",
      }
    }
  ]
};