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
7. As contagens do `docs/FUNCIONAL.md` §2.1 e §2.2 batem com as bases —
   cada secção contra a **sua** —, e, se o ficheiro mudou nesta
   release, a data do cabeçalho dele é de hoje.

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


def funcional_medido():
    """As contagens do `docs/FUNCIONAL.md` §2.1, contra a base.

    **Deriva a tabela inteira em vez de listar as linhas à mão.** Cada
    linha da forma `| \\`tabela\\` | N | …` é uma promessa conferível, e
    uma tabela nova fica coberta sem ninguém se lembrar de a
    acrescentar aqui — que é o erro que esta ferramenta toda existe
    para não repetir.

    Medido a 19/09/2026, quando ele perguntou se o funcional estava
    actualizado: **sete das doze contagens estavam velhas**, todas
    porque a aplicação tinha corrido às 09:00. Não é desleixo — é a
    natureza de um número medido, e por isso precisa de máquina.
    """
    import sqlite3
    maus = []
    texto = _ficheiro("docs/FUNCIONAL.md")
    # **Cada secção contra a SUA base.** A primeira versão varria o
    # ficheiro todo e acusava `contrato_cpv` de não existir no
    # radar.db (está no contratos.db) e `responsavel` de não ser uma
    # tabela (é uma coluna, da tabela das colunas de `propostas`).
    # Doze falsos positivos, e o achado verdadeiro — um `slots`
    # desactualizado — perdido no meio. Por isso o âmbito é explícito.
    for marca, ficheiro in (("### 2.1 ", "radar.db"),
                            ("### 2.2 ", "contratos.db")):
        base = os.path.join(RAIZ, ficheiro)
        if marca not in texto or not os.path.exists(base):
            continue
        bloco = texto.split(marca, 1)[1]
        # a tabela das TABELAS acaba onde começa a das colunas
        bloco = re.split(r"\n\*\*As colunas|\n### ", bloco)[0]
        c = sqlite3.connect("file:%s?mode=ro" % base, uri=True)
        try:
            existem = {r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            for linha in bloco.splitlines():
                # **Só as linhas que prometem um número exacto.** Uma
                # que diga «~210 mil» ou «uma por verificação» não
                # casa aqui, e é de propósito: as tabelas que crescem
                # sozinhas ficavam velhas antes de o commit chegar ao
                # GitHub. A 22/09/2026 fez-se um commit só para mudar
                # o `historico` de 622 para 623, e nessa manhã já ia
                # em 625 — trabalho a fingir, e o caminho mais curto
                # para alguém começar a usar `--no-verify`.
                m = re.match(r"\|\s*((?:`\w+`\s*·?\s*)+)\|\s*([\d\s*·\u00a0]+)\|",
                             linha)
                if not m:
                    continue
                tabelas = re.findall(r"`(\w+)`", m.group(1))
                numeros = [_numero(x) for x in
                           re.split(r"·", m.group(2).replace("*", ""))]
                numeros = [x for x in numeros if x and x.isdigit()]
                if len(tabelas) != len(numeros):
                    continue
                for tabela, diz in zip(tabelas, numeros):
                    if tabela not in existem:
                        maus.append(("`%s`, citada no %s" % (tabela, marca.strip()),
                                     "existe na doc", "não existe no " + ficheiro))
                    elif int(diz) != c.execute(
                            "SELECT count(*) FROM %s" % tabela).fetchone()[0]:
                        real = c.execute(
                            "SELECT count(*) FROM %s" % tabela).fetchone()[0]
                        maus.append(("`%s` no %s" % (tabela, marca.strip()),
                                     diz, str(real)))
        finally:
            c.close()
    return maus


def data_do_funcional():
    """A data do `FUNCIONAL`, **se ele mudou desde a última release**.

    Não se exige que a data mexa em todas as releases: se o ficheiro
    não foi tocado, a data dele continua verdadeira. Exige-se quando
    foi — e a 19/09/2026 levou nove commits num dia com o cabeçalho a
    dizer «última revisão: 18 de setembro».
    """
    ultima = git("describe", "--tags", "--abbrev=0", "HEAD")
    if ultima and not git("diff", "--name-only", ultima + "..HEAD",
                          "--", "docs/FUNCIONAL.md"):
        return None                            # não mudou; a data vale
    m = re.search(r"Última revisão: (\d{1,2}) de (\w+) de (\d{4})",
                  _ficheiro("docs/FUNCIONAL.md"))
    if not m:
        return "não encontrada"
    hoje = date.today()
    if (int(m.group(1)), m.group(2).lower(), int(m.group(3))) == (
            hoje.day, MESES[hoje.month - 1], hoje.year):
        return None
    return "%s de %s de %s" % m.groups()


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

    # O documento funcional, a pedido dele a 19/09/2026: «quero que o
    # funcional faça parte dos docs actualizados antes de um push».
    fun = funcional_medido()
    if fun:
        problemas.append(
            ("%d contagens do docs/FUNCIONAL.md §2.1 estão velhas" % len(fun),
             "\n".join("       %s: diz «%s», é «%s»" % m for m in fun)))
    else:
        print("  ok   as contagens do FUNCIONAL §2.1 batem com a base")

    velha_f = data_do_funcional()
    if velha_f:
        problemas.append(
            ("o FUNCIONAL mudou nesta release e a data dele é de %s"
             % velha_f,
             "põe a de hoje no cabeçalho, e a versão que vais cortar"))
    else:
        print("  ok   a data do FUNCIONAL está de acordo com o que mudou")

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
