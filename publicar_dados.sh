#!/usr/bin/env bash
# Envia o radar.db para a release "dados" no GitHub, para o trazer para
# outro computador com o trazer_dados.sh -- o par do publicar_dados.bat.
# Só o radar.db: o contratos.db refaz-se em minutos com
# "python radar.py --contratos".
cd "$(dirname "$(readlink -f "$0")")" || exit 1

if ! command -v gh >/dev/null; then
  echo " Falta o gh (a linha de comandos do GitHub):  sudo apt install gh"
  echo " e depois  gh auth login"
  exit 1
fi
if [ ! -f radar.db ]; then
  echo " Não há radar.db nesta pasta. Nada a enviar."
  exit 1
fi

echo " ATENÇÃO: pára o painel e as tarefas antes de continuar -- enviar o"
echo " radar.db com o radar a escrever nele pode levar uma cópia a meio"
echo " de uma escrita. Se corre como serviço:"
echo "   systemctl --user stop radar-painel.service radar-hora.timer"
echo
read -r -p " Já está parado, posso continuar? [s/N] " RESP
[ "$RESP" = "s" ] || [ "$RESP" = "S" ] || exit 1

echo
echo " A enviar o radar.db para o GitHub (pode demorar, é mais de 1 GB)..."
if gh release view dados >/dev/null 2>&1; then
  gh release upload dados radar.db --clobber
else
  gh release create dados radar.db --title "Base de dados (radar.db)" --notes "Última base enviada por publicar_dados."
fi || { echo " Falhou o envio. Verifica a ligação e o \"gh auth status\"."; exit 1; }

echo
echo " Pronto. A base está na release \"dados\" do GitHub."
