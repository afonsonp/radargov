#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hook PostToolUse: compila o ficheiro Python que acabou de ser escrito.

Existe porque os erros que passaram despercebidos neste projecto foram
todos de sintaxe e de escapes -- barras invertidas a mais num literal,
aspas mal fechadas -- e so apareciam quando o painel ja estava a arrancar.

`-W error::SyntaxWarning` faz com que avisos como "invalid escape
sequence" contem como erro: foi exactamente esse o caso do `\\%` no LIKE.

Apanha tambem o que for escrito por comando: um `sed -i` ou um heredoc no
Bash ou no PowerShell nao traz `file_path` nenhum, e ate aqui passava ao
lado -- justamente o caminho onde os escapes se perdem, que e o erro que
este hook existe para apanhar. Nesse caso compilam-se os ficheiros .py
nomeados no comando, e so esses: um comando que nao mexa em Python nao
paga nada por isto.

Nao trava nada. Escreve o erro, para ser visto e corrigido a seguir.
"""

import io
import json
import os
import re
import subprocess
import sys

# A consola do Windows e cp1252 e as mensagens do py_compile citam a
# linha do ficheiro -- que aqui vem cheia de portugues acentuado.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace")

RX_PY = re.compile(r"[\w./\\:\-]+\.py\b")


def alvos(dados):
    caminho = dados.get("file_path") or ""
    if caminho:
        return [caminho] if caminho.lower().endswith(".py") else []
    # Sem file_path, foi por comando: fica o que la estiver nomeado.
    return [c for c in RX_PY.findall(dados.get("command") or "")
            if os.path.exists(c)]


def main():
    try:
        entrada = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    for caminho in alvos(entrada.get("tool_input") or {}):
        r = subprocess.run([sys.executable, "-W", "error::SyntaxWarning",
                            "-m", "py_compile", caminho],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode:
            saida = (r.stderr or r.stdout or "").strip().splitlines()
            print("py_compile falhou em %s:" % caminho)
            for linha in saida[-6:]:
                print("  " + linha)
    return 0


if __name__ == "__main__":
    sys.exit(main())
