#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estado do Radar de Concursos, num relance.

Le a base directamente, em vez de importar o radar.py: assim continua a
correr mesmo que o programa esteja a meio de uma alteracao que nao
compila. Nao escreve nada.
"""

import os
import socket
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta

# .claude/skills/estado-radar/ -> tres niveis acima e a pasta do radar.
# (Enquanto o .claude viveu na pasta de cima era preciso mais um salto e
# o nome "radar" no fim; de dentro do projecto, o caminho e este.)
PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "..", "..")
PASTA = os.path.abspath(PASTA)
DB = os.path.join(PASTA, "radar.db")


def mil(n):
    return "{:,}".format(int(n)).replace(",", " ")


def main():
    if not os.path.exists(DB):
        print("Não encontrei a base em %s" % DB)
        return 1
    c = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
    c.row_factory = sqlite3.Row
    q = lambda s, *a: c.execute(s, a).fetchone()[0]
    hoje = date.today()

    print("RECOLHA")
    tot = q("SELECT COUNT(*) FROM anuncios")
    lidos = q("SELECT COUNT(*) FROM anuncios WHERE detalhe_lido=1")
    print("  anúncios: %s  |  com detalhe lido: %s" % (mil(tot), mil(lidos)))
    try:
        dias = int(q("SELECT valor FROM estado WHERE chave='detalhe_dias'"))
    except Exception:
        dias = 60
    corte = (hoje - timedelta(days=dias)).strftime("%Y-%m-%d")
    falta = q("SELECT COUNT(*) FROM anuncios WHERE detalhe_lido=0 AND data_pub>=?",
              corte)
    print("  na janela dos %d dias, por ler: %s%s"
          % (dias, mil(falta), "  (~%d min)" % (falta // 60) if falta else ""))
    ult = c.execute("SELECT valor FROM estado WHERE chave='ultima_verificacao'").fetchone()
    ok = c.execute("SELECT valor FROM estado WHERE chave='ultima_ok'").fetchone()
    msg = c.execute("SELECT valor FROM estado WHERE chave='ultima_mensagem'").fetchone()
    print("  última verificação: %s  [%s]"
          % (ult["valor"] if ult else "nunca",
             "ok" if (ok and ok["valor"] != "0") else (msg["valor"] if msg else "?")))
    erro = c.execute("SELECT valor FROM estado WHERE chave='ultimo_erro_relogio'").fetchone()
    if erro:
        print("  !! erro no relógio: %s" % erro["valor"][:90])

    print("\nTRIAGEM")
    for e, rot in (("novo", "por ver"), ("interessa", "interessa"),
                   ("descartado", "descartados")):
        print("  %-12s %s" % (rot, mil(q("SELECT COUNT(*) FROM anuncios WHERE estado=?", e))))
    urg = q("SELECT COUNT(*) FROM anuncios WHERE estado='interessa' "
            "AND prazo>=? AND prazo<=?", hoje.strftime("%Y-%m-%d"),
            (hoje + timedelta(days=7)).strftime("%Y-%m-%d"))
    if urg:
        print("  !! %s com prazo a menos de 7 dias" % mil(urg))
    for f in c.execute("SELECT f.nome, COUNT(a.ref) n FROM fases f "
                       "LEFT JOIN anuncios a ON a.fase_id=f.id AND a.estado='interessa' "
                       "GROUP BY f.id ORDER BY f.ordem"):
        print("     %-24s %d" % (f["nome"], f["n"]))

    print("\nCAPTURAS")
    for nome in ("curl_DR.txt", "curl_detalhe.txt"):
        caminho = os.path.join(PASTA, nome)
        if os.path.exists(caminho):
            idade = (datetime.now()
                     - datetime.fromtimestamp(os.path.getmtime(caminho))).days
            print("  %-18s presente, %d dias" % (nome, idade))
        else:
            print("  %-18s EM FALTA" % nome)

    print("\nSISTEMA")
    print("  base: %.0f MB" % (os.path.getsize(DB) / 1048576))
    print("  documentos: %s ficheiros" % mil(q("SELECT COUNT(*) FROM documentos")))
    # Desde 8/09/2026 o radar corre em Ubuntu: o painel ve-se pela porta,
    # e as tarefas sao os temporizadores do systemd que o agendar.sh cria
    # (os mesmos nomes que o aviso vermelho do painel procura).
    try:
        with socket.create_connection(("127.0.0.1", 8765), timeout=0.3):
            vivo = True
    except OSError:
        vivo = False
    print("  painel a correr: %s" % ("sim, http://localhost:8765" if vivo else "não"))
    try:
        timers = subprocess.run(["systemctl", "--user", "list-timers", "--all",
                                 "--no-legend", "--plain"],
                                capture_output=True, text=True).stdout
    except OSError:
        timers = ""
    activas = all(nome in timers for nome in ("radar-09h.timer", "radar-17h.timer"))
    print("  tarefas agendadas: %s" % ("activas" if activas else "não encontradas"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
