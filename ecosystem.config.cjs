module.exports = {
  apps: [{
    name: 'ghostpost-api',
    script: '.venv/bin/uvicorn',
    args: 'src.main:app --host 127.0.0.1 --port 8000 --workers 1 --log-level warning',
    cwd: '/home/athena/ghostpost',
    interpreter: 'none',
    env: {
      DOTENV_PATH: '/home/athena/ghostpost/.env'
    }
  }]
};
