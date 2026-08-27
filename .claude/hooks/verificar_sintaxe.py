#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hook PostToolUse: compila o ficheiro Python que acabou de ser escrito.

Existe porque os erros que passaram despercebidos neste projecto foram
todos de sintaxe e de escapes -- barras invertidas a mais num literal,
aspas mal fechadas -- e so apareciam quando o painel ja estava a arrancar.

`-W error::SyntaxWarning` faz com que avisos como "invalid escape
sequence" contem como erro: foi exactamente esse o caso do `\\%` no LIKE.

Nao trava nada. Escreve o erro, para ser visto e corrigido a seguir.
"""

import json
import subprocess
import sys


def main():
    try:
        entrada = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    caminho = (entrada.get("tool_input") or {}).get("file_path") or ""
    if not caminho.lower().endswith(".py"):
        return 0
    r = subprocess.run([sys.executable, "-W", "error::SyntaxWarning",
                        "-m", "py_compile", caminho],
                       capture_output=True, text=True)
    if r.returncode:
        saida = (r.stderr or r.stdout or "").strip().splitlines()
        print("py_compile falhou em %s:" % caminho)
        for linha in saida[-6:]:
            print("  " + linha)
    return 0


if __name__ == "__main__":
    sys.exit(main())
