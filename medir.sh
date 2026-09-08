#!/usr/bin/env bash
# Mede de onde vem o token das capturas do DR (medir_captura.py) -- o
# par do medir.bat. Lê as capturas, nunca as escreve.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
source ./_python.sh
"$PY" medir_captura.py
if [ -f amostras/medicao_captura.txt ]; then
  xdg-open amostras/medicao_captura.txt 2>/dev/null || cat amostras/medicao_captura.txt
fi
