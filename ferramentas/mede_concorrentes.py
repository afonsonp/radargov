#!/usr/bin/env python3
"""L0.1 e L0.1b do plano de Outubro: o que o detalhe do BASE traz.

    python ferramentas/mede_concorrentes.py                 # 1 000 contratos (~20 min)
    python ferramentas/mede_concorrentes.py --amostra 30    # ensaio de um minuto
    python ferramentas/mede_concorrentes.py --sem-rede      # só a amostra, sem pedidos
    python ferramentas/mede_concorrentes.py --inventario    # só as quatro pesquisas
    python ferramentas/mede_concorrentes.py --pasta ~/Desktop/radar --guardar F.jsonl
    python ferramentas/mede_concorrentes.py --ler F.jsonl       # o relatório, sem rede

Só leitura: o corpus abre-se em `mode=ro` e ao BASE só se fazem POST de
consulta, um por segundo, com um `User-Agent` que diz quem somos. Não
entra na bateria, porque faz rede. Escreve tabelas em Markdown para o
`docs/diario/`.

**A amostra.** Estratificada por procedimento (concurso público,
consulta prévia, ajuste directo do regime geral) e ano (2024-2026),
escolhida ao acaso com semente fixa, para uma segunda corrida pedir os
mesmos contratos. O `id` do corpus é o `id` do BASE.

**O inventário (L0.1b).** Os tipos de pesquisa não têm o nome óbvio;
achados no HTML da página de pesquisa a 30/09/2026: «Modificações
contratuais» é `incrementos`, «Não celebrações de contrato» é `cnccs`,
«Consultas preliminares» é `consultapreliminar`. A das consultas
preliminares devolve `null` quando se ordena por data: só responde sem
ordenação ou por `-id`.
"""
import argparse
import json
import os
import random
import sqlite3
import sys
import time
from collections import Counter

import requests

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENDERECO = "https://www.base.gov.pt/Base4/pt/resultados/"
VERSAO = "108.0"
CABECALHOS = {"X-Requested-With": "XMLHttpRequest",
              "User-Agent": "MiraGov/1.0 (+https://miragov.pt)"}
PAUSA = 1.0          # segundos entre pedidos: o que o plano prometeu
TENTATIVAS = 3
SEMENTE = 20260930
ANOS = (2024, 2025, 2026)
# O rótulo do estrato e o padrão do tipo_procedimento no corpus.
PROCEDIMENTOS = (("concurso público", "Concurso público%"),
                 ("consulta prévia", "Consulta Prévia%"),
                 ("ajuste directo", "Ajuste Direto Regime Geral%"))
INVENTARIO = (("impugnações", "search_impugnacoes", "-publicationDate"),
              ("modificações contratuais", "search_incrementos", "-publicationDate"),
              ("não celebrações de contrato", "search_cnccs", "-publicationDate"),
              ("consultas preliminares", "search_consultapreliminar", "-id"))


class Bloqueado(Exception):
    """A firewall do BASE (WebKnight) cortou este IP."""


def pedir(sessao, dados):
    """O JSON da resposta, ou None depois de três tentativas.

    A firewall responde 999 com uma página HTML, e daí em diante a tudo,
    incluindo a página de pesquisa aberta num browser. Insistir só
    prolonga o corte: levanta-se Bloqueado e pára-se.
    """
    for tentativa in range(TENTATIVAS):
        try:
            r = sessao.post(ENDERECO, data=dict(dados, version=VERSAO),
                            timeout=30)
            if r.status_code == 999 or "WebKnight" in r.text[:400]:
                raise Bloqueado()
            r.raise_for_status()
            return json.loads(r.text)
        except (requests.RequestException, ValueError):
            time.sleep(2 ** (tentativa + 1))
    return None


def amostra(corpus, total):
    """[(estrato, id)], total repartido pelos nove estratos."""
    por_estrato = max(1, total // (len(PROCEDIMENTOS) * len(ANOS)))
    sorte = random.Random(SEMENTE)
    escolhidos = []
    for rotulo, padrao in PROCEDIMENTOS:
        for ano in ANOS:
            ids = [i for i, in corpus.execute(
                "SELECT id FROM contratos WHERE ano=? AND tipo_procedimento"
                " LIKE ? ORDER BY id", (ano, padrao))]
            for i in sorte.sample(ids, min(por_estrato, len(ids))):
                escolhidos.append(("%s %d" % (rotulo, ano), i))
    # Baralhados: uma corrida cortada a meio fica equilibrada entre os
    # estratos, e não com os primeiros cheios e os últimos vazios.
    sorte.shuffle(escolhidos)
    return escolhidos


def contar(detalhe):
    """As bandeiras de um detalhe, para somar."""
    concorrentes = detalhe.get("contestants") or []
    nifs = [str(c.get("nif") or "") for c in concorrentes]
    return {
        "com concorrentes": bool(concorrentes),
        "só um concorrente": len(concorrentes) == 1,
        "com convidados": bool(detalhe.get("invitees")),
        "com agrupamento": bool(detalhe.get("groupMembers")),
        "com concorrentes e o adjudicatário entre eles": bool(
            {str(c.get("nif")) for c in concorrentes}
            & {str(c.get("nif")) for c in detalhe.get("contracted") or []}),
        "com closeDate": bool(detalhe.get("closeDate")),
        "com causesDeadlineChange": bool(detalhe.get("causesDeadlineChange")),
        "com causesPriceChange": bool(detalhe.get("causesPriceChange")),
        "com totalEffectivePrice": bool(detalhe.get("totalEffectivePrice")),
        "_nif_pessoa": sum(n in ("", "-") for n in nifs),
        "_nif_estrangeiro": sum(bool(n) and n != "-" and not n.isdigit()
                                for n in nifs),
        "_nif_total": len(nifs),
    }


def faixa(n):
    return ("0" if n == 0 else "1" if n == 1 else "2" if n == 2
            else "3-5" if n <= 5 else "6-10" if n <= 10 else "11+")


def tabela(cabecalho, linhas):
    saida = ["| " + " | ".join(cabecalho) + " |",
             "|" + "---|" * len(cabecalho)]
    saida += ["| " + " | ".join(str(c) for c in linha) + " |"
              for linha in linhas]
    return "\n".join(saida)


def pedidos(sessao, escolhidos, pausa, guardar):
    """[(estrato, detalhe)] dos que responderam; pára se a firewall cortar."""
    for k, (estrato, i) in enumerate(escolhidos, 1):
        try:
            detalhe = pedir(sessao, {"type": "detail_contratos", "id": str(i)})
        except Bloqueado:
            print("A firewall do BASE cortou ao pedido %d; paro aqui."
                  % k, file=sys.stderr)
            return
        time.sleep(pausa)
        if guardar and isinstance(detalhe, dict):
            guardar.write(json.dumps({"estrato": estrato, "id": i,
                                      "detalhe": detalhe},
                                     ensure_ascii=False) + "\n")
        if k % 50 == 0:
            print("… %d de %d" % (k, len(escolhidos)), file=sys.stderr)
        yield estrato, detalhe


def do_ficheiro(caminho):
    """Os mesmos pares, lidos de um .jsonl do --guardar, sem rede."""
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            registo = json.loads(linha)
            yield registo["estrato"], registo["detalhe"]


def medir(respostas):
    por_estrato, faixas = {}, {}
    falhas = 0
    for estrato, detalhe in respostas:
        if not isinstance(detalhe, dict):
            falhas += 1
            continue
        soma = por_estrato.setdefault(estrato, Counter())
        soma["pedidos"] += 1
        soma.update(contar(detalhe))
        faixas.setdefault(estrato.rsplit(" ", 1)[0], Counter())[
            faixa(len(detalhe.get("contestants") or []))] += 1
    return por_estrato, faixas, falhas


def relatorio(por_estrato, faixas, falhas):
    campos = ["com concorrentes", "só um concorrente", "com convidados",
              "com agrupamento",
              "com concorrentes e o adjudicatário entre eles",
              "com closeDate", "com causesDeadlineChange",
              "com causesPriceChange", "com totalEffectivePrice"]
    linhas = []
    for estrato, soma in sorted(por_estrato.items()):
        n = soma["pedidos"]
        linhas.append([estrato, n] + ["%d (%.0f%%)" % (soma[c], 100.0 * soma[c] / n)
                                      for c in campos])
    respondidos = sum(s["pedidos"] for s in por_estrato.values())
    print("### O detalhe de %d contratos (%d sem resposta)\n"
          % (respondidos, falhas))
    print(tabela(["estrato", "n"] + campos, linhas))
    print()
    ordem = ["0", "1", "2", "3-5", "6-10", "11+"]
    print(tabela(["procedimento"] + ["%s conc." % f for f in ordem],
                 [[p] + [f[o] for o in ordem] for p, f in sorted(faixas.items())]))
    print()
    total = Counter()
    for soma in por_estrato.values():
        total.update(soma)
    if total["_nif_total"]:
        print("NIF dos concorrentes: %d no total; %d sem NIF («-», pessoas);"
              " %d estrangeiros (não numéricos)." % (
                  total["_nif_total"], total["_nif_pessoa"],
                  total["_nif_estrangeiro"]))


def inventario(sessao):
    linhas = []
    for rotulo, tipo, ordem in INVENTARIO:
        try:
            resposta = pedir(sessao, {"type": tipo, "query": "",
                                      "sort": ordem, "page": "0", "size": "1"})
        except Bloqueado:
            print("A firewall do BASE cortou; paro aqui.", file=sys.stderr)
            break
        time.sleep(PAUSA)
        total = resposta.get("total") if isinstance(resposta, dict) else None
        linhas.append([rotulo, "`%s`" % tipo, "—" if total is None else total])
    print("### O inventário: as pesquisas do BASE\n")
    print(tabela(["pesquisa", "tipo do pedido", "registos"], linhas))


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--amostra", type=int, default=1000)
    p.add_argument("--sem-rede", action="store_true")
    p.add_argument("--inventario", action="store_true")
    p.add_argument("--pasta", default=RAIZ, help="onde está o contratos.db")
    p.add_argument("--guardar", help="grava cada detalhe num .jsonl")
    p.add_argument("--ler", help="refaz o relatório de um .jsonl, sem rede")
    p.add_argument("--pausa", type=float, default=PAUSA,
                   help="segundos entre pedidos (1 foi cortado ao 193.º)")
    a = p.parse_args()
    if a.ler:
        relatorio(*medir(do_ficheiro(a.ler)))
        return
    sessao = requests.Session()
    sessao.headers.update(CABECALHOS)
    if a.inventario:
        inventario(sessao)
        return
    corpus = sqlite3.connect("file:%s?mode=ro" % os.path.join(
        os.path.expanduser(a.pasta), "contratos.db"), uri=True)
    escolhidos = amostra(corpus, a.amostra)
    if a.sem_rede:
        print(tabela(["estrato", "contratos"],
                     sorted(Counter(e for e, _ in escolhidos).items())))
        return
    guardar = open(a.guardar, "w", encoding="utf-8") if a.guardar else None
    try:
        resultado = medir(pedidos(sessao, escolhidos, a.pausa, guardar))
    finally:
        if guardar:
            guardar.close()
    relatorio(*resultado)


if __name__ == "__main__":
    main()
