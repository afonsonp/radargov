#!/usr/bin/env bash
# Traz o radar.db da release "dados" do GitHub, para um computador novo
# arrancar sem recolher onze anos de anúncios outra vez -- o par do
# trazer_dados.bat. O contratos.db não vem por aqui: refaz-se com
# "python radar.py --contratos" (ou o contratos.sh), em minutos.
cd "$(dirname "$(readlink -f "$0")")" || exit 1

if ! command -v gh >/dev/null; then
  echo " Falta o gh (a linha de comandos do GitHub):  sudo apt install gh"
  echo " e depois  gh auth login"
  exit 1
fi
if [ -f radar.db ]; then
  echo " Já há um radar.db nesta pasta. Para não arriscar substituir dados"
  echo " mais recentes por um transporte antigo, este script não mexe nele."
  echo " Se é mesmo para trazer o de fora, muda-lhe o nome à mão primeiro"
  echo " -- por exemplo radar-antes-de-trazer.db -- e volta a correr isto."
  exit 1
fi

echo " A trazer o radar.db da release \"dados\" do GitHub (mais de 1 GB, demora)..."
if ! gh release download dados --pattern radar.db --dir .; then
  echo " Falhou. Confirma que há uma release \"dados\" com o radar.db anexado"
  echo " -- o publicar_dados.sh cria-a -- e que o \"gh auth status\" está bem."
  exit 1
fi

echo
echo " Pronto: radar.db trazido. Falta o contratos.db -- corre agora o"
echo " contratos.sh para o reconstruir a partir do dump público."
