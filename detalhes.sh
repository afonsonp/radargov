#!/usr/bin/env bash
# O par do detalhes.bat.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
source ./_python.sh
echo
echo " LER O DETALHE DE TODOS OS ANÚNCIOS"
echo
echo " Vai buscar o CPV, o prazo, o preço base, a plataforma e o texto"
echo " de todos os anúncios que ainda não os têm. A rotina diária lê só"
echo " os últimos 60 dias, e sem detalhe um anúncio não aparece num"
echo " filtro por CPV, nem na árvore, nem nos indicadores: está na base"
echo " e é como se não estivesse."
echo
echo " DEMORA CERCA DE 3 HORAS. São 8 pedidos ao portal do Diário da"
echo " República ao mesmo tempo, em vez de um a seguir ao outro."
echo
echo " Não gasta tokens nem dinheiro: é só ir buscar páginas. O que"
echo " gasta modelo é o reler.sh / --ler-pecas."
echo
echo " Podes dar Ctrl-C ou desligar o computador: cada anúncio fica"
echo " gravado assim que é lido, e voltar a correr isto continua de"
echo " onde ia."
echo
read -r -p " Enter para continuar, Ctrl-C para desistir. "
echo
"$PY" radar.py --detalhes tudo
