#!/usr/bin/env bash
# O ensaio de leitura: põe o que o modelo escreveu ao lado do texto do
# documento, sem gastar orçamento (--sem-modelo).
cd "$(dirname "$(readlink -f "$0")")" || exit 1
source ./_python.sh
echo
echo " ENSAIO DE LEITURA"
echo " Põe o que o modelo escreveu ao lado do texto do documento."
echo
read -r -p " Referência do concurso (ex: 21295/2026): " REF
[ -z "$REF" ] && exit 0
echo
"$PY" ".claude/skills/ensaio-de-leitura/ensaio.py" "$REF" --sem-modelo
echo
echo " ----------------------------------------------------------------"
echo "  V literal: a frase está no documento tal e qual."
echo "  ~ reescrito: as palavras estão lá, mas não seguidas. Normal."
echo "  ? sem apoio: há termos que não aparecem. Olha para a janela ao"
echo "    lado antes de dar por errado -- costuma ser o modelo a dizer"
echo "    \"Automatização\" onde o documento diz \"Automatizar\"."
echo " ----------------------------------------------------------------"
