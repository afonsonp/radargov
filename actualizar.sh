#!/usr/bin/env bash
# Traz para esta pasta a última release publicada no GitHub -- o par do
# actualizar.bat. Nunca segue o master a cada commit: a programação
# faz-se nas sessões remotas do Claude Code; aqui só se actualiza
# quando há uma tag nova pronta. Se o painel estiver a correr como
# serviço, reinicia-o no fim, para servir o código novo.
cd "$(dirname "$(readlink -f "$0")")" || exit 1

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo " Isto não é um repositório git. Nada a actualizar."
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo " Há alterações por gravar em ficheiros que o git segue --"
  echo " provavelmente o config.json, mexido pelo painel. Confirma com"
  echo " \"git status\" o que é, e faz commit ou \"git checkout -- config.json\""
  echo " antes de actualizar."
  exit 1
fi

echo " A verificar releases no GitHub..."
if ! git fetch --tags --force origin; then
  echo " Não consegui falar com o GitHub. Verifica a ligação."
  exit 1
fi

ULTIMA="$(git tag -l 'v*' --sort=-v:refname | head -n 1)"
if [ -z "$ULTIMA" ]; then
  echo " Ainda não há nenhuma release no GitHub."
  exit 1
fi

AGORA="$(git rev-parse HEAD)"
ALVO="$(git rev-list -n 1 "$ULTIMA")"

# Tres casos, e NENHUM sai daqui: a saida boa e uma so, la em baixo,
# depois do reinicio. Foi um `exit 0` neste sitio que deixou o painel
# dezassete horas a servir codigo velho (19/09/2026) -- dizia "ja esta
# na ultima release" e nao reiniciava nada.
if [ "$AGORA" = "$ALVO" ]; then
  echo " Já está na última release: $ULTIMA"
  FINAL=" Nada a trazer. A pasta está na release $ULTIMA."
elif git merge-base --is-ancestor "$ALVO" "$AGORA"; then
  # A pasta ja contem a release e vai mais alem -- e o que se passa
  # enquanto se trabalha nela. O `git merge --ff-only` aqui dizia
  # "Already up to date" e saia bem, e o guiao acabava a dizer que a
  # pasta estava NA release, quando esta a frente dela.
  echo " A pasta está à frente da release $ULTIMA: $(git describe --tags)"
  FINAL=" Nada a trazer: a pasta está à frente da release $ULTIMA."
else
  echo " A actualizar de ${AGORA:0:7} para a release $ULTIMA..."
  if ! git merge --ff-only "$ULTIMA"; then
    echo
    echo " Não consegui avançar sem misturar histórico -- há commits locais"
    echo " que a release não conhece. Não mexi em nada; resolve isto à mão"
    echo " com o git antes de voltar a tentar."
    exit 1
  fi
  # Dependencias novas na release entram no .venv. So aqui: sem codigo
  # novo nao ha requisitos novos.
  [ -x .venv/bin/python ] && .venv/bin/python -m pip install --quiet -r requirements.txt
  FINAL=" Pronto. A pasta está agora na release $ULTIMA."
fi

# O painel le o radar.py ao arrancar e mais nunca: reinicia-se SEMPRE,
# tambem quando nao houve nada a trazer. Nesta pasta e o caso normal --
# programa-se aqui, por isso nunca ha nada a trazer, e sem isto o
# reinicio nunca acontecia. O `try-restart` nao faz nada se o servico
# nao estiver a correr.
systemctl --user try-restart radar-painel.service 2>/dev/null

echo
echo "$FINAL"
