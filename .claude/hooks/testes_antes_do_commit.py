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

import io
import json
import os
import re
import subprocess
import sys

# A consola do Windows e cp1252 e o unittest escreve os nomes dos testes
# em portugues; sem isto a explicacao chegava estropiada.
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                              errors="replace")

PASTA = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", ".."))
TESTES = os.path.join(PASTA, "teste_radar.py")


def interpretador():
    """O mesmo criterio do _python.bat: se ha um Python dentro da pasta, e
    esse que manda. O hook corre no Python do sistema, que pode nao ter as
    dependencias -- e entao os testes "falhavam" todos por ImportError."""
    proprio = os.path.join(PASTA, "python", "python.exe")
    if os.path.exists(proprio):
        return proprio
    # Em Linux (8/09/2026) o equivalente e o .venv que o instalar.sh cria:
    # o python3 do Ubuntu nao traz flask nem pymupdf, e sem isto o hook
    # travava todos os commits por ImportError.
    venv = os.path.join(PASTA, ".venv", "bin", "python")
    return venv if os.path.exists(venv) else sys.executable

# O `git commit` de que se fala aqui e o de gravar. O `git commit --help`
# ou uma mensagem que por acaso contenha as palavras nao contam.
RX_COMMIT = re.compile(r"(?:^|[|;&]\s*)git\s+(?:-\S+\s+)*commit\b")


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
