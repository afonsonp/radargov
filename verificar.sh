#!/usr/bin/env bash
# O que o temporizador de hora a hora corre (radar-hora.timer); o radar
# decide se esta hora conta.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
source ./_python.sh
# "$@": o temporizador passa --agendada (ver o agendar.sh); à mão, sem
# nada, verifica sempre
exec "$PY" radar.py --uma-vez "$@"
