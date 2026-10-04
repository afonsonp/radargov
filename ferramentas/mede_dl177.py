#!/usr/bin/env python3
"""O efeito do DL 177/2026 na parte L do DR, medido (4/10/2026).

    python ferramentas/mede_dl177.py                 # até ao último anúncio
    python ferramentas/mede_dl177.py --ate 2026-11-30
    python ferramentas/mede_dl177.py --pasta ~/Desktop/radar

Sem rede: o `radar.db` abre-se em `mode=ro`. Não entra na bateria.

**A pergunta.** O DL subiu os limiares da consulta prévia (bens e
serviços até 130 000 €, empreitadas até 1 000 000 €), e a consulta prévia
não se anuncia no DR. Em 2025, 28 % dos anúncios estavam nessa faixa (54
% nas obras; `docs/historico/CONCORRENTES-2026-09.md`). É um tecto, não
uma previsão: as entidades publicam por hábito. Esta ferramenta mede o
que acontece de facto.

**As três janelas**, pelo mesmo critério:

- **desde 1/10/2026** até `--ate` (por omissão, o último dia com anúncios);
- **as mesmas datas em 2025** — a sazonalidade do mês (o fim do ano
  orçamental puxa os anúncios para cima em novembro e dezembro);
- **setembro de 2026**, o controlo: o mês antes da lei.

O volume conta-se **por dia com anúncios** (o DR não publica ao fim de
semana), porque as janelas não têm o mesmo número de dias úteis.

**O que se conta**, só nos anúncios do DR (a Vortal fica de fora):

- os anúncios, e por dia;
- a família, pelo «Tipo de Contrato» da secção 6: obras quando diz
  «Empreitada», bens e serviços no resto;
- **na faixa**: com preço base entre o limiar antigo e o novo da
  consulta prévia (bens e serviços 75 000–130 000 €; obras 150 000 €–
  1 000 000 €) — o que a lei passou a deixar fazer sem anúncio. Se a
  lei pegar, esta fatia é a que encolhe primeiro;
- com preço base (facultativo desde 1/10/2026);
- com o preço estimado preenchido (o leitor guarda o «0,00 EUR» como
  vazio);
- com o regime de flexibilização do concurso público a «Sim».

**O que não diz**: porque é que o volume mudou. Uma queda em outubro
pode ser o regime transitório (o que se decidiu em setembro anuncia-se
em outubro pela lei antiga). Uma janela de poucos dias não conclui
nada: corre-se no fim de outubro e no fim de novembro, e os números
vão para o `docs/diario/`.
"""
import argparse
import os
import re
import sqlite3
from datetime import date, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INICIO = date(2026, 10, 1)
CONTROLO = (date(2026, 9, 1), date(2026, 9, 30))
# os limiares da consulta prévia, antes e desde 1/10/2026 (arts. 19.º e
# 20.º; a tabela antes/depois está no CONCORRENTES-2026-09.md)
FAIXA = {"obras": (150_000, 1_000_000), "bens e serviços": (75_000, 130_000)}

RX_TIPO = re.compile(r"Tipo de Contrato:\s*([^\r\n]+)")
RX_FLEXIVEL = re.compile(r"Regime de flexibilização do concurso público:\s*Sim")
RX_EURO = re.compile(r"([\d.]+,\d{2})")


def euros(texto):
    """'1.248.300,00 EUR' -> 1248300.0; None se não for número."""
    m = RX_EURO.search(texto or "")
    if not m:
        return None
    return float(m.group(1).replace(".", "").replace(",", "."))


def familia(texto):
    m = RX_TIPO.search(texto or "")
    if not m:
        return None
    return "obras" if "Empreitada" in m.group(1) else "bens e serviços"


def medir(base, de, ate):
    """Os números de uma janela [de, ate], num dicionário."""
    n = {"anuncios": 0, "dias": set(), "sem tipo": 0,
         "com preço base": 0, "com estimado": 0, "flexível": 0}
    for f in FAIXA:
        n[f] = 0
        n[f + " na faixa"] = 0
    for pub, preco_base, estimado, texto in base.execute(
            "SELECT data_pub, preco_base, preco_estimado, texto FROM anuncios"
            " WHERE COALESCE(fonte,'') != 'vortal'"
            " AND data_pub >= ? AND data_pub < ?",
            (de.isoformat(), (ate + timedelta(days=1)).isoformat())):
        n["anuncios"] += 1
        n["dias"].add(pub[:10])
        valor = euros(preco_base)
        if valor:
            n["com preço base"] += 1
        if euros(estimado):
            n["com estimado"] += 1
        if RX_FLEXIVEL.search(texto or ""):
            n["flexível"] += 1
        f = familia(texto)
        if not f:
            n["sem tipo"] += 1
            continue
        n[f] += 1
        baixo, alto = FAIXA[f]
        if valor and baixo <= valor < alto:
            n[f + " na faixa"] += 1
    n["dias"] = len(n["dias"])
    return n


def pct(parte, todo):
    return "%5.1f %%" % (100.0 * parte / todo) if todo else "    —  "


def linhas(nome, n):
    dias = n["dias"] or 1
    na_faixa = sum(n[f + " na faixa"] for f in FAIXA)
    com_tipo = sum(n[f] for f in FAIXA)
    yield "%s — %d anúncios em %d dias (%.1f por dia)" % (
        nome, n["anuncios"], n["dias"], n["anuncios"] / dias)
    yield "    na faixa da consulta prévia nova: %d de %d com tipo (%s)" % (
        na_faixa, com_tipo, pct(na_faixa, com_tipo).strip())
    for f in FAIXA:
        yield "      %-16s %5d, %5d na faixa (%s)" % (
            f, n[f], n[f + " na faixa"], pct(n[f + " na faixa"], n[f]).strip())
    yield "    com preço base   %s" % pct(n["com preço base"], n["anuncios"])
    yield "    com estimado     %s  (%d)" % (pct(n["com estimado"], n["anuncios"]),
                                            n["com estimado"])
    yield "    flexível «Sim»   %d" % n["flexível"]


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pasta", default=RAIZ, help="onde está o radar.db")
    p.add_argument("--ate", help="último dia a contar (AAAA-MM-DD)")
    args = p.parse_args()
    caminho = os.path.join(os.path.expanduser(args.pasta), "radar.db")
    base = sqlite3.connect("file:%s?mode=ro" % caminho, uri=True)
    ultimo = base.execute("SELECT MAX(data_pub) FROM anuncios WHERE "
                          "COALESCE(fonte,'') != 'vortal'").fetchone()[0]
    ate = date.fromisoformat(args.ate) if args.ate else date.fromisoformat(ultimo[:10])
    if ate < INICIO:
        raise SystemExit("O --ate tem de ser depois de 1/10/2026.")
    um_ano = lambda d: d.replace(year=d.year - 1)
    janelas = (("Desde 1/10/2026, até %s" % ate.strftime("%d/%m/%Y"), INICIO, ate),
               ("As mesmas datas em 2025", um_ano(INICIO), um_ano(ate)),
               ("Setembro de 2026 (antes da lei)",) + CONTROLO)
    medidas = [(nome, medir(base, de, a)) for nome, de, a in janelas]
    for nome, n in medidas:
        print("\n".join(linhas(nome, n)))
        print()
    agora, antes = medidas[0][1], medidas[1][1]
    if agora["dias"] and antes["dias"]:
        print("Por dia, contra 2025: %+.0f %%" % (
            100.0 * (agora["anuncios"] / agora["dias"])
            / (antes["anuncios"] / antes["dias"]) - 100))
    if agora["dias"] < 15:
        print("Atenção: %d dias é pouco para concluir. Repetir no fim de "
              "outubro e de novembro." % agora["dias"])


if __name__ == "__main__":
    main()
