#!/usr/bin/env bash
# Manda o modelo reler as peças já guardadas, sem ir à rede.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
source ./_python.sh
echo
echo " RELER AS PEÇAS PELO MODELO"
echo
echo " Volta a ler o Caderno de Encargos e o Programa de todos os"
echo " concursos que já têm peças em disco, e reescreve o Objecto, a"
echo " Equipa, os Documentos da proposta e a Localização."
echo
echo " Serve depois de se mexer na forma como o modelo lê. Demora cerca"
echo " de um minuto por concurso -- não por ser lento, mas porque a"
echo " conta tem um tecto de tokens por minuto e há que esperar."
echo
echo " Se disser que o orçamento do dia acabou, é mesmo isso: são 200"
echo " mil tokens por dia e recomeça amanhã. O que já tinha sido lido"
echo " fica guardado."
echo
read -r -p " Enter para continuar, Ctrl-C para desistir. "
echo
"$PY" radar.py --ler-pecas tudo
