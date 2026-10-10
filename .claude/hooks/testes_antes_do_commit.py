#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hook PreToolUse: nao deixa gravar no git com testes a falhar.

"Correr os testes antes de gravar" era um habito, e um habito falha
precisamente nos dias em que faz falta -- ao fim da noite, na correccao
pequena que "nao podia ter partido nada". Sao centenas de testes em
menos de um segundo: mais barato do que a duvida. (Ja esteve aqui um
numero exacto; envelheceu como todos os numeros exactos em comentarios.)

So trava o `git commit`. O resto do git passa: o `git add`, o `git log`,
o `git diff` nao gravam nada e nao ha nada a proteger neles.

Sai com codigo 2 e o que estiver no stderr volta para o Claude, que fica
a saber que teste caiu e pode corrigi-lo em vez de insistir.
"""

import json
import os
import re
import subprocess
import sys

PASTA = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", ".."))
TESTES = os.path.join(PASTA, "teste_radar.py")


def interpretador():
    """O mesmo criterio do _python.sh: o .venv que o instalar.sh cria, se
    existir. O hook corre no Python do sistema, que nao traz flask nem
    pymupdf -- e entao os testes "falhavam" todos por ImportError."""
    venv = os.path.join(PASTA, ".venv", "bin", "python")
    return venv if os.path.exists(venv) else sys.executable

# O `git commit` de que se fala aqui e o de gravar. Uma mensagem que por
# acaso contenha as palavras nao conta.
#
# Antes do `commit` pode vir uma opcao do git sozinha (`-q`,
# `--git-dir=x`) ou com o valor a seguir (`-C pasta`, `-c chave=valor`,
# `--git-dir pasta`), e o valor pode vir entre aspas. Ate 10/10/2026 so a
# primeira forma era reconhecida, e um `git -C pasta commit` gravava sem
# os testes correrem. E o `git` pode vir pelo caminho (`/usr/bin/git`) ou
# dentro de parenteses.
_VALOR = r"""(?:"[^"]*"|'[^']*'|\S+)"""
_OPCAO = (r"(?:(?:-C|-c|--git-dir|--work-tree|--namespace|--config-env)"
          r"\s+%s|-\S+)" % _VALOR)
RX_COMMIT = re.compile(r"(?:^|[|;&(]\s*)(?:\S*/)?git\s+(?:%s\s+)*commit\b"
                       % _OPCAO)


def main():
    try:
        entrada = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    comando = (entrada.get("tool_input") or {}).get("command") or ""
    if not RX_COMMIT.search(comando) or not os.path.exists(TESTES):
        return 0

    r = subprocess.run([interpretador(), TESTES], cwd=PASTA,
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if not r.returncode:
        return 0

    # O unittest escreve o essencial no stderr e o resumo fica no fim.
    saida = (r.stderr or r.stdout or "").strip().splitlines()
    falhas = [l for l in saida if l.startswith(("FAIL:", "ERROR:"))]
    sys.stderr.write("Commit travado: os testes não passam.\n")
    for linha in (falhas or saida[-8:]):
        sys.stderr.write("  " + linha + "\n")
    sys.stderr.write("Corre `python teste_radar.py` para ver tudo.\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
