#!/usr/bin/env bash
# O que os temporizadores das 09h e das 17h correm -- o par do verificar.bat.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
source ./_python.sh
exec "$PY" radar.py --uma-vez
