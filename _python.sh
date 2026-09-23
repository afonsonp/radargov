# Escolhe que Python usar. É lido (com "source") por todos os outros .sh.
#
# Se houver um .venv dentro da pasta -- o instalar.sh cria-o -- é esse
# que manda: é onde estão o flask, o pymupdf e o resto, que o python3
# do Ubuntu não traz.
#
# Se não houver, usa-se o python3 do sistema, e é provável que falte
# tudo: corre primeiro o instalar.sh.
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -x "$AQUI/.venv/bin/python" ]; then
  PY="$AQUI/.venv/bin/python"
else
  PY="python3"
fi
