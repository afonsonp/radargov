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

# O portao da release (19/09/2026). Os hooks do git vivem em
# `.git/hooks/`, que NAO viaja no repositorio -- por isso o nosso esta
# em `.githooks/`, versionado, e aqui diz-se ao git para o usar. Sem
# esta linha, uma instalacao nova empurrava tags sem conferir nada, e
# o portao existia so no computador de quem o escreveu.
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git config core.hooksPath .githooks
  echo " Portão da release ligado (corre ao empurrar uma tag vX.Y.Z)."
fi

"$PY" -c "import flask, requests, pypdf, pymupdf, cryptography, openpyxl; print('   Está tudo. Corre agora o iniciar.sh.')"
