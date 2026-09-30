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
    melhores = melhores_sitios(achados, largura)
    return melhores[0] if melhores else None


def melhores_sitios(achados, largura=400):
    """Todos os pontos empatados no melhor: o mesmo perfil repete-se em
    varias paginas, e a pagina citada so se julga contra todos eles."""
    candidatos = sorted({p for _, posicoes in achados for p in posicoes})
    contas = [(sum(1 for _, posicoes in achados
                   if any(abs(p - centro) <= largura for p in posicoes)), centro)
              for centro in candidatos]
    melhor = max((n for n, _ in contas), default=0)
    return [centro for n, centro in contas if n == melhor and n]


def apoio(linha, fonte, fonte_comprimida, mapa):
    """(veredicto, explicacao, sitios) de uma linha da resposta do modelo.

    `sitios` sao os [(inicio, fim)] no texto onde a linha se achou -- todos
    os que empatam --, para a pagina citada se julgar contra eles."""
    agulha = comprime(linha)[0]
    if not agulha:
        return "", "", []
    p = fonte_comprimida.find(agulha)
    if p >= 0:
        fim = p + len(agulha) - 1
        return "literal", janela(fonte, mapa, p, fim), [
            (mapa[q], mapa[q + len(agulha) - 1]) for q in onde_estao(agulha, fonte_comprimida)]

    faltam, achados = [], []
    for palavra, comprimida in termos(linha):
        posicoes = onde_estao(comprimida, fonte_comprimida)
        if posicoes:
            achados.append((comprimida, posicoes))
        else:
            faltam.append(palavra)
    centro = melhor_sitio(achados)
    onde = janela(fonte, mapa, centro, centro) if centro is not None else ""
    sitio = [(mapa[c], mapa[c]) for c in melhores_sitios(achados)]
    if not faltam:
        # Todas as palavras estao no documento, mas nao seguidas: o
        # modelo resumiu ou juntou pedacos de sitios diferentes. E o
        # caso normal de um "objecto decomposto" bem feito.
        return "reescrito", onde, sitio
    return "sem apoio", "termos que não aparecem: %s%s" % (
        ", ".join('"%s"' % t for t in faltam[:6]),
        ("\n        mais perto: " + onde) if onde else ""), sitio


def pagina_em(fonte, pos, inicios):
    """A pagina de `pos`, contada desde o principio do ficheiro dele (um
    documento, ou um ficheiro dentro de um ZIP); None sem paginas."""
    ini = max(i for i in inicios if i <= pos)
    fim = min([i for i in inicios if i > pos] + [len(fonte)])
    if "\f" not in fonte[ini:fim]:
        return None
    return fonte.count("\f", ini, pos) + 1


def _paginas(a, b):
    return "%d" % a if a == b else "%d–%d" % (a, b)


def nota_da_pagina(linha, fonte, sitios, inicios):
    """A pagina citada confere com a pagina onde a janela foi achada?
    (4.a ronda, 30/09/2026: e a pergunta com que se julga a leitura.)
    Com a linha em varios sitios, basta um deles."""
    if not sitios:
        return ""
    import radar
    citadas = radar.paginas_da_citacao(linha)
    achadas = [(pagina_em(fonte, a, inicios), pagina_em(fonte, b, inicios))
               for a, b in sitios]
    com_paginas = [(a, b) for a, b in achadas if a is not None]
    if not com_paginas:
        return ("✗ citada pág. %s, e o ficheiro não tem páginas"
                % _paginas(min(citadas), max(citadas))) if citadas else ""
    onde = ", ".join(sorted({_paginas(a, b) for a, b in com_paginas},
                            key=lambda x: int(re.match(r"\d+", x).group()))[:4])
    if not citadas:
        return "· sem página citada; encontrada na %s" % onde
    if any(a <= min(citadas) and max(citadas) <= b for a, b in com_paginas):
        return "✓ pág. %s" % _paginas(min(citadas), max(citadas))
    return "✗ citada pág. %s, encontrada na %s" % (_paginas(min(citadas), max(citadas)), onde)


MARCA = {"literal": "✓", "reescrito": "~", "sem apoio": "?"}


def texto_das_pecas(radar, ref, fontes):
    """O texto inteiro das peças lidas -- não o recorte que o modelo viu.

    De propósito: se a resposta se apoia em texto que existe no
    documento mas ficou fora do recorte, isso não é invenção, é um
    recorte a apertar de mais. São coisas diferentes e devem ver-se
    diferentes.
    """
    docs = radar.documentos_com_texto(ref)
    # As fontes trazem « (pág. …)» e, dentro de um ZIP, «zip/membro»
    # (29/09/2026): comparados os nomes inteiros, so batia um .xlsx sem
    # paginas, e o ensaio confrontava a leitura so com ele -- «? sem
    # apoio» falsos em quase todas as linhas da 23389, da 23728 e da
    # 22036. Casa-se pelo ficheiro guardado: o nome sem paginas, e o do
    # ZIP quando a fonte e um membro dele.
    nomes = {nome.split("/", 1)[0] for nome, _ in radar.fontes_por_peca(fontes or "")}
    usados = [d for d in docs if d["nome"] in nomes] or list(docs)
    # sem_indice, como no caminho que leva o texto ao modelo: senao as
    # linhas pontilhadas do sumario servem de apoio a tudo -- dizem os
    # titulos todos e nao dizem nada.
    textos = [radar.sem_indice(d["texto"]) for d in usados]
    fonte = "\n\n".join(textos)
    # onde comeca cada ficheiro -- cada documento, e cada ficheiro dentro
    # de um ZIP --, que e de onde as paginas se contam (como no recorte)
    inicios, pos = [], 0
    for t in textos:
        inicios.append(pos)
        pos += len(t) + 2
    inicios += [m.end() for m in radar.RX_MARCA_DO_FICHEIRO.finditer(fonte)]
    return [d["nome"] for d in usados], fonte, sorted(inicios or [0])


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

    nomes, fonte, inicios = texto_das_pecas(radar, ref, analise["fontes"])
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
    paginas = {"✓": 0, "✗": 0, "·": 0}
    for campo in radar.CAMPOS_DA_ANALISE:
        valor = (analise[campo] or "").strip()
        print("\n── %s ──" % campo)
        if not valor or radar.simplifica(valor) == "nao consta":
            print("   (%s)" % (valor or "vazio"))
            continue
        for linha in valor.split("\n"):
            if not linha.strip():
                continue
            # a pagina citada e a marca de confirmar nao sao do documento
            veredicto, onde, sitios = apoio(radar.sem_a_pagina_citada(linha), fonte,
                                            fonte_comprimida, mapa)
            if not veredicto:
                continue
            contas[veredicto] += 1
            print("  %s %s" % (MARCA[veredicto], linha.strip()))
            if onde:
                print("      %s" % onde)
            nota = nota_da_pagina(linha, fonte, sitios, inicios)
            if nota:
                paginas[nota[0]] += 1
                print("      página: %s" % nota)

    print("\n" + "=" * 72)
    print("✓ literal no documento: %d   ~ reescrito, palavras todas lá: %d"
          "   ? sem apoio: %d" % (contas["literal"], contas["reescrito"],
                                  contas["sem apoio"]))
    print("página: ✓ bate com o sítio achado: %d   ✗ não bate: %d   · sem página "
          "citada: %d" % (paginas["✓"], paginas["✗"], paginas["·"]))
    print("Os '?' são os que exigem os teus olhos: ou o modelo inventou, ou "
          "a peça diz aquilo por outras palavras.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
