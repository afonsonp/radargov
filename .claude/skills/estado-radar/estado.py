#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estado do Radar de Concursos, num relance.

Le a base directamente, em vez de importar o radar.py: assim continua a
correr mesmo que o programa esteja a meio de uma alteracao que nao
compila. Nao escreve nada.
"""

import io
import os
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace")

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
    # O `pwsh` (PowerShell 7) primeiro, o `powershell` (5.1) como reserva:
    # o 7 nem sempre esta instalado, o 5.1 esta sempre. Pedia-se o 5.1
    # directamente, e numa maquina com o 7 instalado era a unica coisa
    # deste projecto a abrir o velho.
    vivo = None
    for exe in ("pwsh", "powershell"):
        try:
            vivo = subprocess.run(
                [exe, "-NoProfile", "-Command",
                 "if (Get-NetTCPConnection -LocalPort 8765 "
                 "-ErrorAction SilentlyContinue) {'sim'} else {'nao'}"],
                capture_output=True, text=True)
            break
        except OSError:
            continue
    print("  painel a correr: %s"
          % ("sim, http://localhost:8765"
             if vivo and "sim" in vivo.stdout else "não"))
    tarefas = subprocess.run(["schtasks", "/Query", "/TN", "Radar DR 09h"],
                             capture_output=True, text=True)
    print("  tarefas agendadas: %s"
          % ("activas" if tarefas.returncode == 0 else "não encontradas"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
