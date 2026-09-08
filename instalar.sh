#!/usr/bin/env bash
# Instala o que o radar precisa, dentro de um .venv nesta pasta -- o par
# do instalar.bat. Não toca no Python do sistema: o Ubuntu recusa
# `pip install` fora de um ambiente virtual, e é melhor assim.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
echo
echo " A preparar o Python do radar nesta pasta (.venv)..."
if [ ! -x .venv/bin/python ]; then
  if ! python3 -m venv .venv; then
    echo
    echo " Não consegui criar o .venv. Em Ubuntu costuma faltar o pacote:"
    echo "   sudo apt install python3-venv"
    echo " Instala-o e volta a correr isto."
    exit 1
  fi
fi
source ./_python.sh
echo " A instalar o que falta (flask, requests, pypdf, pymupdf, cryptography, openpyxl)..."
"$PY" -m pip install --quiet --upgrade pip
"$PY" -m pip install --quiet -r requirements.txt || exit 1
echo
"$PY" -c "import flask, requests, pypdf, pymupdf, cryptography, openpyxl; print('   Está tudo. Corre agora o iniciar.sh.')"
