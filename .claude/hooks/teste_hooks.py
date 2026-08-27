#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Os hooks tem logica, e logica errada num hook custa caro dos dois lados.

Cada caso aqui corresponde a uma decisao que se quer mesmo: travar o que
destroi dados, e -- tao importante -- deixar passar o que e rotina. Um
hook que recusa trabalho legitimo nao e um hook seguro, e um hook que se
desliga.

Os casos ficam num ficheiro e nao num comando de propos: o texto dos
casos leva comandos perigosos la dentro, e o proprio proteger_dados.py
recusaria o comando que os corresse. Aconteceu duas vezes.

    python .claude/hooks/teste_hooks.py
"""

import io
import json
import os
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace")

AQUI = os.path.dirname(os.path.abspath(__file__))

# (hook, o que se esta a fazer, entrada, codigo esperado: 0 passa, 2 trava)
CASOS = (
    # --- proteger_dados: o que tem mesmo de ser travado
    ("proteger_dados.py", "Write na base",
     {"file_path": "C:/x/radar.db"}, 2),
    ("proteger_dados.py", "Write numa captura",
     {"file_path": "curl_DR.txt"}, 2),
    ("proteger_dados.py", "apagar a base",
     {"command": "rm -f radar.db"}, 2),
    ("proteger_dados.py", "reescrever uma captura",
     {"command": "echo abc > curl_DR.txt"}, 2),
    ("proteger_dados.py", "sed -i numa captura",
     {"command": "sed -i s/a/b/ curl_detalhe.txt"}, 2),
    ("proteger_dados.py", "sqlite3 a apagar linhas",
     {"command": 'sqlite3 radar.db "DELETE FROM anuncios"'}, 2),
    ("proteger_dados.py", "escrita pela base de trabalho",
     {"command": "python -c \"import radar; "
                 "radar.liga().execute('DELETE FROM analise')\""}, 2),
    ("proteger_dados.py", "PowerShell a remover a base",
     {"command": "Remove-Item radar.db -Force"}, 2),

    # --- proteger_dados: o que NAO pode ser travado
    ("proteger_dados.py", "escrever no proprio programa",
     {"file_path": "radar.py"}, 0),
    ("proteger_dados.py", "ler a base por SQL",
     {"command": 'sqlite3 radar.db "SELECT COUNT(*) FROM anuncios"'}, 0),
    ("proteger_dados.py", "ler a base pelo radar",
     {"command": "python -c \"import radar; "
                 "print(radar.liga().execute('SELECT 1').fetchone())\""}, 0),
    ("proteger_dados.py", "ensaio sobre uma copia",
     {"command": "python -c \"import radar; radar.DB = copia; "
                 "radar.liga().execute('DELETE FROM analise WHERE ref=?')\""}, 0),
    # Este passou a ser deixado passar depois de recusar trabalho a serio:
    # um guiao que acrescenta uma coluna ao radar.py leva SQL dentro das
    # aspas, e esse SQL e texto a escrever num .py, nao uma ordem a correr.
    ("proteger_dados.py", "editar SQL que vive dentro do radar.py",
     {"command": 'python - <<F\nt = t.replace("ALTER TABLE analise ADD '
                 'COLUMN x TEXT")\nF'}, 0),
    ("proteger_dados.py", "um cat inofensivo ao pe de um rm noutro sitio",
     {"command": "cat radar.db | wc -c && rm outra-coisa.txt"}, 0),
    ("proteger_dados.py", "git a fazer o seu trabalho",
     {"command": "git status --short"}, 0),

    # --- testes_antes_do_commit: so o commit
    ("testes_antes_do_commit.py", "git add passa",
     {"command": "git add -A"}, 0),
    ("testes_antes_do_commit.py", "git log passa",
     {"command": "git log --oneline"}, 0),

    # --- verificar_sintaxe: nunca trava, so avisa
    ("verificar_sintaxe.py", "ficheiro escrito pela ferramenta",
     {"file_path": "radar.py"}, 0),
    ("verificar_sintaxe.py", "ficheiro escrito por comando",
     {"command": "sed -i s/a/a/ radar.py"}, 0),
    ("verificar_sintaxe.py", "comando que nao toca em Python",
     {"command": "git status"}, 0),
)


def main():
    falhas = 0
    for hook, o_que, entrada, esperado in CASOS:
        r = subprocess.run([sys.executable, os.path.join(AQUI, hook)],
                           input=json.dumps({"tool_input": entrada}),
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        certo = r.returncode == esperado
        falhas += not certo
        print("%s %-22s %-45s esperado %d, deu %d"
              % ("ok " if certo else "MAL", hook.replace(".py", ""),
                 o_que, esperado, r.returncode))
    print("\n%d caso(s), %d falha(s)." % (len(CASOS), falhas))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
