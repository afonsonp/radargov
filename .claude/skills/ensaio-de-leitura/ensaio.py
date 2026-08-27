#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A resposta do modelo ao lado do texto de onde ela devia ter vindo.

Serve a unica pergunta que nao se responde a ler codigo: a leitura das
pecas presta? O programa sabe dizer que campos saiu; nao sabe dizer se
o que saiu chega para decidir. Isto poe as duas coisas lado a lado --
cada linha da resposta com o pedaco do documento que a sustenta, ou com
a lista dos termos que nao aparecem la em lado nenhum.

A comparacao e feita sobre texto comprimido: sem acentos, sem
maiusculas, sem espacos e sem pontuacao. Nao e capricho -- o extractor
de PDF parte numeros ("1 2 meses"), e um grep ingenuo por "12 meses"
devolve "nao consta" e produz uma acusacao falsa de invencao. Ja
aconteceu, e esta escrito no ESTADO.md.

Com o modelo (por omissao), a leitura corre sobre uma COPIA da base: a
analise guardada no radar.db nao e tocada, e o ensaio pode repetir-se
sem consequencias. Custa ~6 mil tokens.

    python .claude/skills/ensaio-de-leitura/ensaio.py <ref> [--sem-modelo]

O --sem-modelo julga a analise que ja esta guardada, sem gastar nada.
"""

import io
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import unicodedata

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace")

PASTA = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "..", ".."))
sys.path.insert(0, PASTA)


def comprime(texto):
    """(texto comprimido, mapa de volta para as posicoes do original).

    Um caractere de cada vez, para o mapa nao escorregar: normalizar a
    string toda muda os indices, e sem indices certos a janela que se
    mostra ao lado sai deslocada.
    """
    fora, mapa = [], []
    for i, c in enumerate(texto):
        base = unicodedata.normalize("NFKD", c)[:1]
        if base.isalnum():
            fora.append(base.lower())
            mapa.append(i)
    return "".join(fora), mapa


def janela(texto, mapa, ini, fim, folga=110):
    """O pedaco do documento a volta do que se encontrou, numa linha."""
    a = max(0, mapa[ini] - folga)
    b = min(len(texto), mapa[min(fim, len(mapa) - 1)] + folga)
    return "…" + re.sub(r"\s+", " ", texto[a:b]).strip() + "…"


def termos(linha):
    """As palavras da linha que valem a pena procurar uma a uma."""
    fora = []
    for palavra in re.findall(r"[^\W_]+", linha, re.UNICODE):
        comprimida = comprime(palavra)[0]
        if len(comprimida) >= 4 or (comprimida.isdigit() and comprimida):
            fora.append((palavra, comprimida))
    return fora


def onde_estao(agulha, fonte_comprimida, tecto=60):
    """As posicoes em que a agulha aparece. Poucas, que so servem para
    escolher entre elas."""
    fora, p = [], fonte_comprimida.find(agulha)
    while p >= 0 and len(fora) < tecto:
        fora.append(p)
        p = fonte_comprimida.find(agulha, p + 1)
    return fora


def melhor_sitio(achados, largura=400):
    """O ponto do documento onde mais termos da linha se juntam.

    A primeira ocorrencia nao serve: "Consultor Funcional Senior" aparece
    numa clausula de acompanhamento a meio do Caderno, e a tabela de
    perfis -- que e a fonte a serio daquela linha -- esta noutro sitio.
    Mostrar a primeira mandava os olhos para o lado errado.
    """
    candidatos = [(p, comprimida) for comprimida, posicoes in achados
                  for p in posicoes]
    if not candidatos:
        return None
    melhor, melhor_conta = None, -1
    for centro, _ in candidatos:
        juntos = sum(1 for _, posicoes in achados
                     if any(abs(p - centro) <= largura for p in posicoes))
        if juntos > melhor_conta:
            melhor, melhor_conta = centro, juntos
    return melhor


def apoio(linha, fonte, fonte_comprimida, mapa):
    """(veredicto, explicacao) de uma linha da resposta do modelo."""
    agulha = comprime(linha)[0]
    if not agulha:
        return "", ""
    p = fonte_comprimida.find(agulha)
    if p >= 0:
        return "literal", janela(fonte, mapa, p, p + len(agulha) - 1)

    faltam, achados = [], []
    for palavra, comprimida in termos(linha):
        posicoes = onde_estao(comprimida, fonte_comprimida)
        if posicoes:
            achados.append((comprimida, posicoes))
        else:
            faltam.append(palavra)
    centro = melhor_sitio(achados)
    onde = janela(fonte, mapa, centro, centro) if centro is not None else ""
    if not faltam:
        # Todas as palavras estao no documento, mas nao seguidas: o
        # modelo resumiu ou juntou pedacos de sitios diferentes. E o
        # caso normal de um "objecto decomposto" bem feito.
        return "reescrito", onde
    return "sem apoio", "termos que não aparecem: %s%s" % (
        ", ".join('"%s"' % t for t in faltam[:6]),
        ("\n        mais perto: " + onde) if onde else "")


MARCA = {"literal": "✓", "reescrito": "~", "sem apoio": "?"}


def texto_das_pecas(radar, ref, fontes):
    """O texto inteiro das peças lidas -- não o recorte que o modelo viu.

    De propósito: se a resposta se apoia em texto que existe no
    documento mas ficou fora do recorte, isso não é invenção, é um
    recorte a apertar de mais. São coisas diferentes e devem ver-se
    diferentes.
    """
    docs = radar.documentos_com_texto(ref)
    nomes = [n.strip() for n in (fontes or "").split(",") if n.strip()]
    usados = [d for d in docs if d["nome"] in nomes] or list(docs)
    # sem_indice, como no caminho que leva o texto ao modelo: senao as
    # linhas pontilhadas do sumario servem de apoio a tudo -- dizem os
    # titulos todos e nao dizem nada.
    return ([d["nome"] for d in usados],
            "\n\n".join(radar.sem_indice(d["texto"]) for d in usados))


def analise_com_modelo(radar, ref):
    """Corre a leitura sobre uma cópia da base. A de trabalho fica igual."""
    copia = os.path.join(tempfile.mkdtemp(prefix="ensaio-radar-"), "radar.db")
    origem = sqlite3.connect(radar.DB)
    destino = sqlite3.connect(copia)
    origem.backup(destino)
    destino.close()
    origem.close()
    radar.DB = copia
    # As migracoes correm no arranque do radar.py, e nos so o importamos:
    # sem isto, uma copia de uma base anterior a uma coluna nova rebentava
    # no INSERT ("table analise has no column named localizacao").
    radar.iniciar_db()
    with radar.liga() as c:
        c.execute("DELETE FROM analise WHERE ref=?", (ref,))
    print("a ler as peças pelo modelo (uma cópia da base, ~6 mil tokens)…\n")
    ok, aviso = radar.analisar_pecas(ref)
    if aviso:
        print("  aviso: %s\n" % aviso)
    return radar.analise_de(ref) if ok else None


def main():
    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not argumentos:
        print(__doc__.strip().splitlines()[-3].strip())
        return 2
    ref = argumentos[0].replace("-", "/")
    import radar

    analise = (radar.analise_de(ref) if "--sem-modelo" in sys.argv
               else analise_com_modelo(radar, ref))
    if not analise:
        print("Não há análise para %s. Sem --sem-modelo, o ensaio lê as "
              "peças; com ele, só mostra o que já está guardado." % ref)
        return 1

    nomes, fonte = texto_das_pecas(radar, ref, analise["fontes"])
    if not fonte:
        print("Não há texto de peças em disco para %s: não há contra o que "
              "confrontar." % ref)
        return 1
    fonte_comprimida, mapa = comprime(fonte)

    print("=" * 72)
    print("%s  ·  %s" % (ref, analise["modelo"]))
    print("peças confrontadas: %s  (%s caracteres)"
          % (", ".join(nomes), "{:,}".format(len(fonte)).replace(",", " ")))
    print("=" * 72)

    contas = {"literal": 0, "reescrito": 0, "sem apoio": 0}
    for campo in radar.CAMPOS_DA_ANALISE:
        valor = (analise[campo] or "").strip()
        print("\n── %s ──" % campo)
        if not valor or radar.simplifica(valor) == "nao consta":
            print("   (%s)" % (valor or "vazio"))
            continue
        for linha in valor.split("\n"):
            if not linha.strip():
                continue
            veredicto, onde = apoio(linha, fonte, fonte_comprimida, mapa)
            if not veredicto:
                continue
            contas[veredicto] += 1
            print("  %s %s" % (MARCA[veredicto], linha.strip()))
            if onde:
                print("      %s" % onde)

    print("\n" + "=" * 72)
    print("✓ literal no documento: %d   ~ reescrito, palavras todas lá: %d"
          "   ? sem apoio: %d" % (contas["literal"], contas["reescrito"],
                                  contas["sem apoio"]))
    print("Os '?' são os que exigem os teus olhos: ou o modelo inventou, ou "
          "a peça diz aquilo por outras palavras.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
