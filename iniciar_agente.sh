#!/usr/bin/env bash
# Inicia el agente backend 24/7 — calendario maestro + tareas programadas
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

echo "Agente EIF SAS iniciado. Logs: agente.log"
exec "$PY" agente.py
