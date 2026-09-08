#!/usr/bin/env bash
# Abre o painel -- o par do iniciar.bat. Se o painel já estiver a correr
# como serviço (agendar.sh cria o radar-painel.service), não arranca um
# segundo: diz onde está o que já corre.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
source ./_python.sh
if systemctl --user is-active --quiet radar-painel.service 2>/dev/null; then
  echo " O painel já está a correr como serviço: http://127.0.0.1:8765"
  echo " Para o parar: systemctl --user stop radar-painel.service"
  exit 0
fi
exec "$PY" radar.py "$@"
