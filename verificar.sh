#!/usr/bin/env bash
# O que os temporizadores das 09h e das 17h correm -- o par do verificar.bat.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
source ./_python.sh
# "$@": o temporizador passa --agendada (ver o agendar.sh); à mão, sem
# nada, verifica sempre
exec "$PY" radar.py --uma-vez "$@"
