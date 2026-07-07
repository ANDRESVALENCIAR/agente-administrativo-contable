#!/usr/bin/env bash
# Arranca dashboard + agente en tmux (Linux / Cloud)
set -e
cd "$(dirname "$0")"
TMUX="tmux -f /exec-daemon/tmux.portal.conf"

chmod +x iniciar_dashboard.sh iniciar_agente.sh

if ! $TMUX has-session -t streamlit-dashboard 2>/dev/null; then
  $TMUX new-session -d -s streamlit-dashboard -c "$PWD" -- "${SHELL:-bash}" -l
  $TMUX send-keys -t streamlit-dashboard:0.0 './iniciar_dashboard.sh' C-m
  echo "✓ Dashboard → http://localhost:8501"
else
  echo "· Dashboard ya activo"
fi

if ! $TMUX has-session -t agente-backend 2>/dev/null; then
  $TMUX new-session -d -s agente-backend -c "$PWD" -- "${SHELL:-bash}" -l
  $TMUX send-keys -t agente-backend:0.0 './iniciar_agente.sh' C-m
  echo "✓ Agente backend activo (agente.log)"
else
  echo "· Agente ya activo"
fi

echo ""
echo "Detener: tmux -f /exec-daemon/tmux.portal.conf kill-session -t streamlit-dashboard"
echo "         tmux -f /exec-daemon/tmux.portal.conf kill-session -t agente-backend"
