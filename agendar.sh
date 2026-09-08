#!/usr/bin/env bash
# Cria as tarefas do radar neste computador -- o par do agendar.bat,
# com temporizadores do systemd na sessão do utilizador (nada de root).
#
# São as três do Windows, mais uma: o painel como serviço, sempre a
# correr, porque em Linux este computador é para ficar a servir o radar
# e não para se abrir o painel à mão de manhã.
#
#   radar-09h.timer / radar-17h.timer  -> radar-verificar.service (verificar.sh)
#   radar-contratos.timer              -> radar-contratos.service (contratos.sh)
#   radar-painel.service               -> .venv/bin/python radar.py --sem-browser
#
# O servico do painel chama o radar.py directamente, nao o iniciar.sh:
# o iniciar.sh pergunta ao systemd se o servico esta activo, e visto de
# dentro do proprio servico a resposta e sim -- saia com "ja esta a
# correr" sem abrir nada (8/09/2026, na primeira instalacao a serio).
#
# Sem as verificações, o radar só recolhe com o painel aberto -- e o
# relógio interno recupera os slots falhados, o que faz parecer que
# correu a horas quando não correu. O painel avisa a vermelho quando os
# dois temporizadores faltam (radar.tarefas_em_falta, que lê o
# `systemctl --user list-timers`): os nomes aqui e lá têm de bater.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
AQUI="$(pwd)"
UNIDADES="$HOME/.config/systemd/user"

if ! command -v systemctl >/dev/null; then
  echo " Não há systemd neste sistema. Agenda o verificar.sh no cron: 0 9,17 * * *"
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  echo " Ainda não há .venv: corre primeiro o instalar.sh."
  exit 1
fi

echo " A criar as tarefas do Radar..."
mkdir -p "$UNIDADES"

cat > "$UNIDADES/radar-verificar.service" <<FIM
[Unit]
Description=Radar DR: verificação (o que as tarefas das 09h e 17h correm)

[Service]
Type=oneshot
WorkingDirectory=$AQUI
ExecStart=$AQUI/verificar.sh
FIM

for H in 09 17; do
cat > "$UNIDADES/radar-${H}h.timer" <<FIM
[Unit]
Description=Radar DR ${H}h

[Timer]
OnCalendar=*-*-* ${H}:00:00
Unit=radar-verificar.service

[Install]
WantedBy=timers.target
FIM
done

cat > "$UNIDADES/radar-contratos.service" <<FIM
[Unit]
Description=Radar DR: corpus de contratos do Portal BASE

[Service]
Type=oneshot
WorkingDirectory=$AQUI
ExecStart=$AQUI/contratos.sh
FIM

cat > "$UNIDADES/radar-contratos.timer" <<FIM
[Unit]
Description=Radar contratos (semanal)

[Timer]
OnCalendar=Mon *-*-* 08:00:00
Unit=radar-contratos.service

[Install]
WantedBy=timers.target
FIM

cat > "$UNIDADES/radar-painel.service" <<FIM
[Unit]
Description=Radar DR: o painel em http://127.0.0.1:8765
After=network-online.target

[Service]
WorkingDirectory=$AQUI
ExecStart=$AQUI/.venv/bin/python $AQUI/radar.py --sem-browser
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
FIM

systemctl --user daemon-reload
systemctl --user enable --now radar-09h.timer radar-17h.timer radar-contratos.timer || exit 1
systemctl --user enable --now radar-painel.service || exit 1

# Sem "linger", a sessão do utilizador -- e com ela os temporizadores e
# o painel -- morre quando ele faz logout, e só nasce quando entra.
# Num computador que vai servir o radar isso tem de ficar ligado.
if loginctl enable-linger "$USER" 2>/dev/null; then
  LINGER="ligado"
else
  LINGER="NÃO ficou ligado: corre  sudo loginctl enable-linger $USER"
fi

echo
echo " Feito. Quatro unidades criadas na sessão de $USER:"
echo "   radar-09h.timer              todos os dias às 09:00"
echo "   radar-17h.timer              todos os dias às 17:00"
echo "   radar-contratos.timer        segundas às 08:00"
echo "   radar-painel.service         o painel, sempre a correr"
echo " Correr sem sessão aberta (linger): $LINGER"
echo
echo " O radar passa a recolher com o painel fechado. Para ver o estado:"
echo "   systemctl --user list-timers"
echo "   systemctl --user status radar-painel.service"
echo "   journalctl --user -u radar-verificar.service -n 50"
