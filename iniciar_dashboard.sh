#!/usr/bin/env bash
# Inicia el dashboard Streamlit — AGENTE ADMIN SHAKI · EIF SAS
set -e
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Creado .env desde .env.example (modo demo)"
fi

if [ -d .venv ]; then
  PY=".venv/bin/python"
else
  PY="python3"
fi

echo "Dashboard: http://localhost:8501"
exec "$PY" -m streamlit run dashboard/app.py --server.port 8501 --server.address 0.0.0.0
