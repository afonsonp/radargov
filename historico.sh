#!/usr/bin/env bash
# Abre o histórico de alterações -- o par do historico.bat. Com o gitk
# se estiver instalado (sudo apt install gitk); senão, no terminal.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
# Num disco NTFS o git pode recusar-se a abrir o repositório por não
# reconhecer o dono. Estas variáveis dizem-lhe que confie, só aqui.
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0='*'
if command -v gitk >/dev/null; then
  gitk --all &
else
  git log --graph --oneline --decorate --all
fi
