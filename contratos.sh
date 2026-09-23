#!/usr/bin/env bash
# O que o temporizador semanal corre.
# Sem anos: traz o ano corrente e o anterior, que é onde entram
# contratos novos. É o mesmo que o botão "Actualizar contratos" faz.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
source ./_python.sh
exec "$PY" radar.py --contratos
