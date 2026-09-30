#!/usr/bin/env python3
"""L0.3 do plano de Outubro: quanto antes do fim uma entidade republica.

    python ferramentas/mede_antecipacao.py                 # todos os contratos
    python ferramentas/mede_antecipacao.py --amostra 20000 # ensaio
    python ferramentas/mede_antecipacao.py --pasta ~/Desktop/radar

Sem rede: o `contratos.db` e o `radar.db` abrem-se em `mode=ro`. Não
entra na bateria.

**A conta.** Para cada contrato com `fim_estimado` entre 2022 e 2025 e
um NIPC de adjudicante (nove dígitos — as chaves `n:` são nomes, e o
plano manda nunca cruzar por nome), procura os anúncios do DR da mesma
entidade, pelo NIPC, na mesma divisão de CPV, publicados entre
`fim_estimado − 12 meses` e `fim_estimado + 3 meses`. A antecipação é
`fim_estimado − data_pub`, em dias; positiva é antes do fim.

**Qual anúncio é «o seguinte».** Uma entidade que publica muito no mesmo
CPV tem vários na janela, e a escolha pesa. Toma-se o primeiro
publicado depois da celebração do contrato; e mede-se à parte o
subconjunto limpo, com um só anúncio na janela, onde não há escolha.
Se as duas medianas divergirem muito, a regra do L6 deve usar a limpa.

**Por tipo de entidade não há**: o corpus não classifica as entidades.
Sai por divisão de CPV e por entidade, que é o que o L6 precisa.
"""
import argparse
import bisect
import os
import random
import sqlite3
import statistics
from collections import Counter, defaultdict
from datetime import date, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANTES = timedelta(days=365)
DEPOIS = timedelta(days=91)
CASOS_POR_ENTIDADE = 3     # o limiar do L6: abaixo disto, a mediana do CPV
SEMENTE = 20260930


def data(texto):
    try:
        return date.fromisoformat((texto or "")[:10])
    except ValueError:
        return None


def anuncios_por_chave(base):
    """{(nif, divisão): [datas ordenadas]} dos anúncios do DR."""
    por_chave = defaultdict(list)
    for nif, cpv, pub in base.execute(
            "SELECT nif, cpv, data_pub FROM anuncios"
            " WHERE COALESCE(fonte,'')!='vortal' AND length(nif)=9"
            " AND length(cpv)>=2"):
        d = data(pub)
        if d and nif.isdigit():
            por_chave[(nif, cpv[:2])].append(d)
    for datas in por_chave.values():
        datas.sort()
    return por_chave


def resumo(valores):
    if not valores:
        return "—", "—", "—"
    if len(valores) < 4:
        return statistics.median(valores), "—", "—"
    q1, q2, q3 = statistics.quantiles(valores, n=4)
    return round(q2), round(q1), round(q3)


def tabela(cabecalho, linhas):
    saida = ["| " + " | ".join(cabecalho) + " |",
             "|" + "---|" * len(cabecalho)]
    saida += ["| " + " | ".join(str(c) for c in linha) + " |"
              for linha in linhas]
    return "\n".join(saida)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--amostra", type=int, default=0)
    p.add_argument("--pasta", default=RAIZ)
    a = p.parse_args()
    pasta = os.path.expanduser(a.pasta)
    base = sqlite3.connect("file:%s?mode=ro" % os.path.join(pasta, "radar.db"),
                           uri=True)
    corpus = sqlite3.connect("file:%s?mode=ro" % os.path.join(
        pasta, "contratos.db"), uri=True)
    por_chave = anuncios_por_chave(base)
    contratos = corpus.execute(
        "SELECT adjudicante_chave, cpv, fim_estimado, data_celebracao,"
        " tipo_procedimento FROM contratos"
        " WHERE fim_estimado BETWEEN '2022-01-01' AND '2025-12-31'"
        " AND length(adjudicante_chave)=9 AND length(cpv)>=2").fetchall()
    if a.amostra:
        contratos = random.Random(SEMENTE).sample(
            contratos, min(a.amostra, len(contratos)))

    por_tipo = defaultdict(Counter)
    todos, limpos = [], []
    por_cpv = defaultdict(list)
    por_entidade = defaultdict(list)
    for chave, cpv, fim, celebracao, tipo in contratos:
        fim, celebrado = data(fim), data(celebracao)
        if not fim:
            continue
        divisao = cpv[:2]
        datas = por_chave.get((chave, divisao), [])
        inicio = max(fim - ANTES, celebrado + timedelta(days=1)) \
            if celebrado else fim - ANTES
        i = bisect.bisect_left(datas, inicio)
        j = bisect.bisect_right(datas, fim + DEPOIS)
        tipo = (tipo or "").split(" (")[0][:40]
        por_tipo[tipo]["contratos"] += 1
        if i >= j:
            continue
        por_tipo[tipo]["com anúncio"] += 1
        antecipacao = (fim - datas[i]).days
        todos.append(antecipacao)
        if j - i == 1:
            limpos.append(antecipacao)
            por_tipo[tipo]["um só"] += 1
            por_cpv[divisao].append(antecipacao)
            por_entidade[(chave, divisao)].append(antecipacao)

    print("### A antecipação: %d contratos com fim entre 2022 e 2025\n"
          % len(contratos))
    print(tabela(["procedimento", "contratos", "com anúncio na janela",
                  "com um só"],
                 [[t, c["contratos"], "%d (%.0f%%)" % (
                     c["com anúncio"], 100.0 * c["com anúncio"] / c["contratos"]),
                   c["um só"]]
                  for t, c in sorted(por_tipo.items(),
                                     key=lambda x: -x[1]["contratos"])[:10]]))
    print()
    print(tabela(["conjunto", "casos", "mediana (dias)", "1.º quartil",
                  "3.º quartil"],
                 [["o primeiro depois da celebração", len(todos)]
                  + list(resumo(todos)),
                  ["só um anúncio na janela", len(limpos)]
                  + list(resumo(limpos))]))
    print()
    maiores = sorted(por_cpv.items(), key=lambda x: -len(x[1]))[:15]
    print(tabela(["divisão CPV", "casos", "mediana", "1.º quartil",
                  "3.º quartil"],
                 [[d, len(v)] + list(resumo(v)) for d, v in maiores]))
    print()
    com_regra = [v for v in por_entidade.values()
                 if len(v) >= CASOS_POR_ENTIDADE]
    print("Pares entidade × divisão com casos limpos: %d; com %d ou mais"
          " (a regra da entidade no L6): %d, que somam %d dos %d casos."
          % (len(por_entidade), CASOS_POR_ENTIDADE, len(com_regra),
             sum(len(v) for v in com_regra), len(limpos)))


if __name__ == "__main__":
    main()
