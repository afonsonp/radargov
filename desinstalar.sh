#!/usr/bin/env bash
# Tira as tarefas e o serviço do painel deste computador -- o par do
# desinstalar.bat. Os pacotes ficam: vivem no .venv desta pasta, não no
# sistema. Para os tirar também, apaga a pasta .venv.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
UNIDADES="$HOME/.config/systemd/user"
echo
echo " Remove as tarefas das 09h, das 17h, a semanal dos contratos e o"
echo " serviço do painel deste computador. A base e a triagem ficam."
echo
read -r -p " Enter para continuar, Ctrl-C para desistir. "
systemctl --user disable --now radar-09h.timer radar-17h.timer radar-contratos.timer radar-painel.service 2>/dev/null
rm -f "$UNIDADES"/radar-09h.timer "$UNIDADES"/radar-17h.timer \
      "$UNIDADES"/radar-contratos.timer "$UNIDADES"/radar-contratos.service \
      "$UNIDADES"/radar-verificar.service "$UNIDADES"/radar-painel.service
systemctl --user daemon-reload
echo
echo " Feito. Para tirar também os pacotes:  rm -rf .venv"
