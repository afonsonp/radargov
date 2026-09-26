#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estado do Radar de Concursos, num relance.

Le a base directamente, em vez de importar o radar.py: assim continua a
correr mesmo que o programa esteja a meio de uma alteracao que nao
compila. Nao escreve nada.
"""

import json
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

    # Desde 23/09/2026 (F1) o trabalho de cada empresa e outro ficheiro,
    # empresas/<id>/empresa.db, e desde 15/09 a escada e das propostas:
    # a tabela `fases` e o `anuncios.estado` ja nao dizem nada da triagem.
    print("\nEMPRESAS")
    pasta = os.path.join(PASTA, "empresas")
    ids = sorted(int(n) for n in (os.listdir(pasta) if os.path.isdir(pasta) else [])
                 if n.isdigit() and os.path.exists(os.path.join(pasta, n, "empresa.db")))
    if not ids:
        print("  nenhuma")
    for id_ in ids:
        try:
            with open(os.path.join(pasta, str(id_), "config.json"), encoding="utf-8") as f:
                nome = json.load(f).get("nome_da_empresa") or ""
        except (OSError, ValueError):
            nome = ""
        e = sqlite3.connect("file:%s?mode=ro" % os.path.join(pasta, str(id_), "empresa.db"),
                            uri=True)
        qe = lambda s, *a: e.execute(s, a).fetchone()[0]
        escada = ", ".join("%s %d" % par for par in e.execute(
            "SELECT estado, COUNT(*) FROM propostas GROUP BY estado ORDER BY 2 DESC"))
        print("  %d · %s" % (id_, nome or "Empresa %d" % id_))
        print("     propostas: %d%s" % (qe("SELECT COUNT(*) FROM propostas"),
                                        " (%s)" % escada if escada else ""))
        print("     tarefas por fazer: %d  |  contactos: %d"
              % (qe("SELECT COUNT(*) FROM tarefas WHERE feita_em IS NULL"),
                 qe("SELECT COUNT(*) FROM contactos")))
        refs = [r[0] for r in e.execute("SELECT ref FROM propostas WHERE ref IS NOT NULL")]
        e.close()
        if refs:
            urg = q("SELECT COUNT(*) FROM anuncios WHERE prazo>=? AND prazo<=? "
                    "AND ref IN (%s)" % ",".join("?" * len(refs)),
                    hoje.strftime("%Y-%m-%d"),
                    (hoje + timedelta(days=7)).strftime("%Y-%m-%d"), *refs)
            if urg:
                print("  !! %d com prazo a menos de 7 dias" % urg)

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
    activas = "radar-hora.timer" in timers   # de hora a hora desde 23/09/2026
    print("  tarefas agendadas: %s" % ("activas" if activas else "não encontradas"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
