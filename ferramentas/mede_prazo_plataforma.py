#!/usr/bin/env python3
"""L0.2 do plano de Outubro: a hora do prazo, o DR contra a Vortal.

    python ferramentas/mede_prazo_plataforma.py                # 100 anúncios
    python ferramentas/mede_prazo_plataforma.py --amostra 10   # ensaio
    python ferramentas/mede_prazo_plataforma.py --sem-rede     # só o lado do DR
    python ferramentas/mede_prazo_plataforma.py --pasta ~/Desktop/radar

Só leitura: o `radar.db` abre-se em `mode=ro`, e nada do que se pede à
Vortal se grava. Não entra na bateria, porque faz rede.

**O lado do DR.** A coluna `anuncios.prazo` é só a data; a hora está no
texto do anúncio, na linha «Prazo para apresentação das propostas:
03-10-2026 23:59». Lê-se daí — **do último anúncio da cadeia**
(pelo `altera`, como na ficha), que é o prazo que o radar mostra: a primeira corrida
comparou com o anúncio original, e as prorrogações já publicadas no DR
contaram como divergências.

**O lado da plataforma.** Dois pedidos por anúncio, os mesmos que as
peças já fazem: o link cifrado do DR dá o `PT1.NTC.x`
(`_info_vortal()`), e o detalhe desse procedimento traz o campo
`AJ7_SchedulingCN_DueDateForReceivingReplies` («Data Limite de Recepção
de Candidaturas/Propostas»), em UTC — passa-se à hora de Lisboa com o
`hora_de_lisboa()`.

**Porque só a Vortal.** A acinGov não mostra o prazo em público: a
listagem tem cinco colunas sem data, e «consultar procedimento» pede
que se inicie sessão (conferido a 30/09/2026).
"""
import argparse
import os
import random
import re
import sqlite3
import sys
import time
from collections import Counter

import requests

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
import radar  # noqa: E402  (as constantes e os dois saltos da Vortal)

CAMPO_PRAZO = "AJ7_SchedulingCN_DueDateForReceivingReplies"
LINHA_DR = re.compile(r"Prazo para apresenta\w+ d\w+ \w+:\s*"
                      r"(\d{2})-(\d{2})-(\d{4})(?:\s+(\d{2}:\d{2}))?")
SEMENTE = 20260930
PAUSA = 1.0


def prazo_do_dr(texto):
    """("AAAA-MM-DD", "HH:MM" ou "") da linha do prazo, ou None."""
    m = LINHA_DR.search(texto or "")
    if not m:
        return None
    return "%s-%s-%s" % (m.group(3), m.group(2), m.group(1)), m.group(4) or ""


def ultimo_da_cadeia(base, ref, texto):
    """(ref, texto) do anúncio em vigor na cadeia de alterações.

    A mesma regra do `cadeia_do_anuncio()`: os membros são os que
    apontam para a raiz pelo `altera` (`membros_da_cadeia()`), e vale o
    mais recente por data e número. O `alterado_por` não chega: há
    alterações que o original não regista (o 22888/2026)."""
    membros = radar.membros_da_cadeia(base, ref)
    if not membros:
        return ref, texto
    ultimo = max(membros, key=lambda m: (m["data_pub"] or "",
                                         radar._numero_do_ref(m["ref"])))
    return ultimo["ref"], base.execute(
        "SELECT texto FROM anuncios WHERE ref=?", (ultimo["ref"],)).fetchone()[0]


def prazo_da_vortal(sessao, link):
    """"AAAA-MM-DD HH:MM" de Lisboa, "" sem prazo, ou None se falhou."""
    m = re.search(r"(PT\d+\.NTC\.\d+)", link or "")
    if not m:
        _, endereco = radar._info_vortal(sessao, link)
        m = re.search(r"(PT\d+\.NTC\.\d+)", endereco)
        time.sleep(PAUSA)
    if not m:
        return None
    try:
        dados = sessao.get(radar.VORTAL_REGIAO, timeout=60, params={
            "contractNoticeUId": m.group(1), "langCode": "pt"}).json()
    except (requests.RequestException, ValueError):
        return None
    for campo in (dados or {}).get("regionConfiguration") or []:
        if isinstance(campo, dict) and campo.get("name") == CAMPO_PRAZO:
            valor = campo.get("value") or {}
            return radar.hora_de_lisboa(valor.get("dateValue") or "")
    return ""


def comparar(dr, plataforma):
    """A categoria de um anúncio."""
    if plataforma is None:
        return "a Vortal não respondeu"
    if not plataforma:
        return "a Vortal sem prazo"
    if not dr[1]:
        return "o DR sem hora"
    lado_dr = "%s %s" % dr
    if plataforma == lado_dr:
        return "iguais"
    dia = "no mesmo dia" if plataforma[:10] == dr[0] else "noutro dia"
    lado = "mais cedo" if plataforma < lado_dr else "mais tarde"
    return "a Vortal %s, %s" % (lado, dia)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--amostra", type=int, default=100)
    p.add_argument("--sem-rede", action="store_true")
    p.add_argument("--pasta", default=RAIZ, help="onde está o radar.db")
    a = p.parse_args()
    base = sqlite3.connect("file:%s?mode=ro" % os.path.join(
        os.path.expanduser(a.pasta), "radar.db"), uri=True)
    base.row_factory = sqlite3.Row
    # fonte!='vortal': as consultas preliminares vêm da própria Vortal e
    # não têm lado do DR para comparar.
    linhas = base.execute(
        "SELECT ref, link_pecas, texto FROM anuncios"
        " WHERE plataforma='vortal'"
        " AND COALESCE(fonte,'')!='vortal' AND prazo>=date('now')"
        " AND link_pecas!='' ORDER BY ref").fetchall()
    linhas = random.Random(SEMENTE).sample(linhas, min(a.amostra, len(linhas)))
    contas, exemplos = Counter(), {}
    sessao = requests.Session()
    sessao.headers["User-Agent"] = radar.NAVEGADOR
    for ref, link, texto in linhas:
        ultimo, texto = ultimo_da_cadeia(base, ref, texto)
        if ultimo != ref:
            contas["(com alteração no DR, lida a última)"] += 1
        dr = prazo_do_dr(texto)
        if dr is None:
            contas["o DR sem linha do prazo"] += 1
            continue
        if a.sem_rede:
            contas["o DR com hora" if dr[1] else "o DR sem hora"] += 1
            continue
        plataforma = prazo_da_vortal(sessao, link)
        time.sleep(PAUSA)
        categoria = comparar(dr, plataforma)
        contas[categoria] += 1
        if categoria != "iguais":
            exemplos.setdefault(categoria, []).append(
                "%s: DR %s %s, Vortal %s" % (ref, dr[0], dr[1], plataforma))
    print("### A hora do prazo em %d anúncios da Vortal\n" % len(linhas))
    print("| categoria | anúncios |\n|---|---|")
    for categoria, n in contas.most_common():
        print("| %s | %d |" % (categoria, n))
    for categoria, casos in sorted(exemplos.items()):
        print("\n%s:\n" % categoria)
        for caso in casos[:10]:
            print("- %s" % caso)


if __name__ == "__main__":
    main()
