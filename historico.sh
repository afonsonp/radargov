#!/usr/bin/env bash
# Abre o histórico de alterações. Com o gitk
# se estiver instalado (sudo apt install gitk); senão, no terminal.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
if command -v gitk >/dev/null; then
  gitk --all &
else
  git log --graph --oneline --decorate --all
fi
