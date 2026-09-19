#!/usr/bin/env python3
"""O portão antes de cortar uma release.

    python ferramentas/antes_da_release.py v1.8.6

Sai com 0 se está tudo pronto, 1 se não — e **diz o que falta**, não só
que falta.

## Porque existe

O `testes_antes_do_commit.py` já trava um commit com testes a falhar, e
desde 19/09/2026 o validador da documentação corre na bateria: uma
referência morta ou uma contagem derivável errada **já** travam o
commit.

Mas há uma família que nenhum commit pode conferir: os **números
medidos**. Quantos testes há, quantas linhas tem o `radar.py`, qual é a
última release publicada. Só se sabem correndo, e por isso ficam de
fora da bateria — e apodrecem.

Medido a 19/09/2026, ao escrever isto, **com cinco releases cortadas
nesse mesmo dia**:

| o `ESTADO.md` dizia | era |
|---|---|
| `radar.py` 23 165 linhas | 23 197 |
| `teste_radar.py` 13 765 | 13 791 |
| «a última é a `v1.8.1`» | `v1.8.5` |

A última é a que diz tudo: **quatro releases seguidas sem ninguém
reparar**, e a mesma linha já estivera errada a 18/09 (dizia `v1.7.0`
quando era a `v1.8.0`). Não é desleixo — é que ninguém deriva um número
que só se sabe a correr.

## O que confere

1. A árvore está limpa (nada por gravar).
2. A tag ainda não foi publicada no GitHub.
3. Os testes passam, todos.
4. O `valida_docs.py` dá zero, nas referências e nas contagens.
5. Os números **medidos** do `ESTADO.md` batem certo.
6. O `ESTADO.md` já diz a versão que se vai cortar, e a data é de hoje.

## O que NÃO confere, e continua a ser de quem escreve

Se as frases são verdadeiras. «O interesse recorta os alertas» tinha
todos os nomes certos, todas as contagens certas, e estava ao
contrário. Isso mede-se a ler o código.
"""
import io
import os
import re
import subprocess
import sys
from datetime import date

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MESES = ("janeiro fevereiro março abril maio junho julho agosto"
         " setembro outubro novembro dezembro").split()


def git(*args):
    return subprocess.run(["git"] + list(args), cwd=RAIZ,
                          capture_output=True, text=True).stdout.strip()


def _ficheiro(nome):
    return io.open(os.path.join(RAIZ, nome), encoding="utf-8").read()


def _numero(texto):
    """«23 197» e «23197» são o mesmo número."""
    if texto is None:
        return None
    return texto.replace(" ", "").replace("\u00a0", "").strip()


def medidos(versao):
    """[(rótulo, o que a doc diz, o que é)] — só os que não batem."""
    estado = _ficheiro("ESTADO.md")
    testes = _ficheiro("teste_radar.py")

    def diz(padrao):
        m = re.search(padrao, estado)
        return m.group(1) if m else None

    casos = [
        ("testes", diz(r"Testes \| \*\*([\d\s]+)\*\*"),
         str(len(re.findall(r"^    def test_", testes, re.M)))),
        ("linhas do radar.py", diz(r"`radar\.py` ([\d\s]+) linhas"),
         str(len(_ficheiro("radar.py").splitlines()))),
        ("linhas do teste_radar.py", diz(r"`teste_radar\.py` ([\d\s]+)"),
         str(len(testes.splitlines()))),
        ("a última release", diz(r"A última é a \*\*`(v[\d.]+)`\*\*"),
         versao),
    ]
    maus = []
    for rotulo, d, r in casos:
        if d is None:
            maus.append((rotulo, "não encontrado no ESTADO.md", r))
        elif _numero(d) != _numero(r):
            maus.append((rotulo, d.strip(), r))
    return maus


def data_velha_no_estado():
    """A data do ESTADO.md, se não for a de hoje."""
    m = re.search(r"Última actualização: \*\*(\d{1,2}) de (\w+) de (\d{4})\*\*",
                  _ficheiro("ESTADO.md"))
    if not m:
        return "não encontrada"
    hoje = date.today()
    if (int(m.group(1)), m.group(2).lower(), int(m.group(3))) == (
            hoje.day, MESES[hoje.month - 1], hoje.year):
        return None
    return "%s de %s de %s" % m.groups()


def main():
    if len(sys.argv) < 2 or not re.fullmatch(r"v\d+\.\d+\.\d+", sys.argv[1]):
        print("  Falta a versão que vais cortar:\n"
              "  python ferramentas/antes_da_release.py v1.8.6")
        return 2
    versao = sys.argv[1]
    problemas = []
    print(" A conferir antes da %s...\n" % versao)

    if git("status", "--porcelain"):
        problemas.append(("a árvore não está limpa",
                          "grava ou descarta o que falta — `git status`"))
    else:
        print("  ok   a árvore está limpa")

    # **No REMOTO, e não aqui.** A primeira versão perguntava se a tag
    # existia localmente, e isso parecia certo enquanto o portão se
    # corria à mão — antes de a criar. Como hook do `pre-push` está
    # sempre errado: para empurrar uma tag, ela tem de existir. A
    # pergunta que serve nos dois casos é se **já foi publicada**.
    if git("ls-remote", "--tags", "origin", "refs/tags/" + versao):
        problemas.append(("a %s já está publicada no GitHub" % versao,
                          "escolhe outra versão"))
    else:
        print("  ok   a %s ainda não está publicada" % versao)

    r = subprocess.run([sys.executable, "teste_radar.py"], cwd=RAIZ,
                       capture_output=True, text=True)
    linhas = ((r.stderr or r.stdout).strip().splitlines() or [""])
    if r.returncode:
        problemas.append(("os testes falham", linhas[-1]))
    else:
        print("  ok   os testes passam (%s)"
              % next((l for l in linhas if l.startswith("Ran ")), ""))

    sys.path.insert(0, os.path.join(RAIZ, "ferramentas"))
    import valida_docs
    faltam, _ = valida_docs.valida()
    numeros = valida_docs.valida_numeros()
    if faltam:
        problemas.append(("%d referências apontam para o vazio" % len(faltam),
                          "\n".join("       %s `%s` — %s:%d"
                                    % (t, k, o[0][0], o[0][1])
                                    for t, k, o, _ in sorted(faltam)[:8])))
    else:
        print("  ok   nada na documentação aponta para o vazio")
    if numeros:
        problemas.append(("%d contagens deriváveis não batem" % len(numeros),
                          "\n".join("       %s: diz %s, é %s"
                                    % (m[0], m[2], m[3]) for m in numeros)))
    else:
        print("  ok   as contagens deriváveis batem")

    maus = medidos(versao)
    if maus:
        problemas.append(
            ("%d números medidos estão velhos no ESTADO.md" % len(maus),
             "\n".join("       %s: diz «%s», é «%s»" % m for m in maus)))
    else:
        print("  ok   os números medidos do ESTADO.md batem")

    velha = data_velha_no_estado()
    if velha:
        problemas.append(("a data do ESTADO.md é de %s" % velha,
                          "põe a de hoje, ou confirma que nada mudou"))
    else:
        print("  ok   a data do ESTADO.md é de hoje")

    if not problemas:
        print("\n Pronto para cortar a %s:\n" % versao)
        print("   git tag -a %s -m \"...\"" % versao)
        print("   git push origin %s" % versao)
        print("   gh release create %s --notes-file ..." % versao)
        return 0
    print("\n" + "-" * 62)
    print(" %d coisa%s por resolver antes de cortar a %s:\n"
          % (len(problemas), "" if len(problemas) == 1 else "s", versao))
    for o_que, como in problemas:
        print("  x  %s" % o_que)
        print(como if como.startswith("       ") else "       " + como)
        print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
