#!/usr/bin/env python3
"""Procura informação repetida na documentação viva.

    python ferramentas/repetido.py            # o relatório
    python ferramentas/repetido.py --curto    # só a contagem por par

Nasceu a 19/09/2026, do pedido dele: «quero garantir que não tenho
informação repetida». Até aí a verificação era assunto a assunto, à
mão — o que garante os assuntos que se escolheram, e mais nada.

**Como mede.** Normaliza o texto (minúsculas, sem acentos, sem
pontuação, sem markdown nem blocos de código), parte-o em janelas de
`N` palavras e procura janelas que apareçam em mais do que um sítio.
Depois junta janelas contíguas, para reportar a passagem inteira e não
palavras soltas. Dá ficheiro e linha dos dois lados.

**O que NÃO faz: julgar.** Duas afirmações do mesmo facto para
**públicos diferentes** não são duplicação — o manual explica um gesto
ao Afonso, as armadilhas avisam quem programa, e é legítimo que as duas
digam a mesma frase. Duplicação é a mesma afirmação para o mesmo
público. Isso é leitura humana; isto é a lista de candidatos.

**Porque é que o limiar é 12 e não 6.** Abaixo disto o relatório
enche-se de frases feitas da casa («não se filtra nada à entrada», «um
número que um ecrã mostra») que são vocabulário partilhado de
propósito, não repetição. Medido a 19/09/2026: com N=12 saíram 43
candidatos, dos quais dois eram duplicação verdadeira dentro do mesmo
ficheiro — o `docs/armadilhas.md` a repetir a mesma frase de 29
palavras em duas áreas, e o `docs/referencia.md` a dizer a mesma coisa
em dois parágrafos seguidos.
"""
import io
import os
import re
import sys
import unicodedata
from collections import defaultdict

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Os ficheiros VIVOS. O arquivo (docs/diario/, docs/historico/) fica de
# fora de propósito: são instantâneos, repetem-se entre si por
# definição, e não se editam.
# O `docs/referencia.md` **não** está aqui, e é decisão de
# 19/09/2026. Ele próprio se declara «contexto histórico» no
# cabeçalho, escreve no passado («havia quatro documentos HTML») e a
# tabela dos donos põe-no ao lado do `docs/historico/` — é o «porquê,
# com data». Conferi-lo contra o código de hoje dava ~15 falsos
# positivos permanentes, e uma ferramenta que acusa sempre o mesmo
# deixa de se ler.
VIVOS = ["CLAUDE.md", "ESTADO.md", "BACKLOG.md", "LEIA-ME.md",
         "docs/FUNCIONAL.md", "docs/armadilhas.md", "docs/design.md",
         "docs/seguranca.md"]

N = 12               # palavras por janela
MIN_PALAVRAS = 14    # só se reporta uma passagem a partir daqui


def limpa(t):
    """Tira o que é forma e não conteúdo, guardando as mudanças de linha."""
    t = re.sub(r"```.*?```", lambda m: "\n" * m.group().count("\n"), t,
               flags=re.S)
    t = re.sub(r"`[^`]*`", " ", t)                    # código em linha
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)    # ligações
    return re.sub(r"[|>#*_~-]", " ", t)               # markdown


def palavras_com_linha(t):
    """[(palavra, nº da linha)], para o relatório poder apontar."""
    saida = []
    for n, linha in enumerate(limpa(t).splitlines(), 1):
        linha = unicodedata.normalize("NFKD", linha.lower())
        linha = "".join(c for c in linha if not unicodedata.combining(c))
        saida.extend((p, n) for p in re.findall(r"[a-z0-9]+", linha))
    return saida


def carrega(base):
    dados = {}
    for f in VIVOS:
        p = os.path.join(base, f)
        if os.path.exists(p):
            dados[f] = palavras_com_linha(io.open(p, encoding="utf-8").read())
    return dados


def junta(indices):
    """[3,4,5,9,10] -> [(3,5),(9,10)]"""
    saida, inicio, ant = [], None, None
    for i in sorted(indices):
        if inicio is None:
            inicio = ant = i
        elif i == ant + 1:
            ant = i
        else:
            saida.append((inicio, ant))
            inicio = ant = i
    if inicio is not None:
        saida.append((inicio, ant))
    return saida


def procura(base=RAIZ):
    """[(a, linha_a, b, linha_b, n_palavras, trecho)], maior primeiro."""
    dados = carrega(base)
    onde = defaultdict(list)
    for f, ws in dados.items():
        for i in range(len(ws) - N + 1):
            onde[" ".join(p for p, _ in ws[i:i + N])].append((f, i))

    pares = defaultdict(list)
    for sitios in onde.values():
        if len(sitios) < 2:
            continue
        for a, ia in sitios:
            for b, ib in sitios:
                if (a, ia) < (b, ib):
                    pares[(a, b)].append((ia, ib))

    achados = []
    for (a, b), ocorrencias in pares.items():
        # junta pelo lado esquerdo, e guarda onde caiu do lado direito
        direito = {}
        for ia, ib in ocorrencias:
            direito.setdefault(ia, ib)
        for i, j in junta(direito):
            n = j - i + N
            if n < MIN_PALAVRAS:
                continue
            achados.append((
                a, dados[a][i][1],
                b, dados[b][direito[i]][1],
                n, " ".join(p for p, _ in dados[a][i:j + N])))
    achados.sort(key=lambda x: -x[4])
    return achados


def main():
    achados = procura()

    if "--curto" in sys.argv:
        por_par = defaultdict(int)
        for a, _, b, _, _, _ in achados:
            por_par[(a, b)] += 1
        for (a, b), n in sorted(por_par.items(), key=lambda x: -x[1]):
            print("%3d  %s  <->  %s" % (n, a, b))
        print("\n%d passagens de %d+ palavras" % (len(achados), MIN_PALAVRAS))
        return

    dentro = [x for x in achados if x[0] == x[2]]
    entre = [x for x in achados if x[0] != x[2]]

    print("=" * 74)
    print("NO MESMO FICHEIRO  —  não têm defesa: mesmo público, mesmo sítio")
    print("=" * 74)
    for a, la, _, lb, n, trecho in dentro:
        print("\n%s:%d  e  :%d   [%d palavras]" % (a, la, lb, n))
        print("  %s" % trecho[:300])
    if not dentro:
        print("\nnenhuma.")

    print()
    print("=" * 74)
    print("ENTRE FICHEIROS  —  candidatos: julga se o público é o mesmo")
    print("=" * 74)
    for a, la, b, lb, n, trecho in entre:
        print("\n%s:%d  <->  %s:%d   [%d palavras]" % (a, la, b, lb, n))
        print("  %s" % trecho[:300])

    print("\n%d no mesmo ficheiro, %d entre ficheiros."
          % (len(dentro), len(entre)))


if __name__ == "__main__":
    main()
