#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hook PreToolUse: recusa escritas em ficheiros que sao dados, nao codigo.

As capturas levam o token da sessao do browser e a base de dados leva o
trabalho todo. Nenhum dos dois se edita a maos -- se algo os quiser
reescrever, e engano.

Apanha as ferramentas de escrita (Edit, Write, NotebookEdit) pelo
`file_path`, e o Bash e o PowerShell pelo texto do comando. Esta segunda
metade existe porque a primeira, sozinha, era uma porta com a parede ao
lado: um `rm radar.db` ou um `echo ... > curl_DR.txt` passavam sem uma
palavra.

O que NAO apanha, e de proposito: ler a base. O `sqlite3 radar.db
"SELECT ..."` e o `python -c "...radar.liga()..."` sao rotina -- a
propria skill estado-radar le assim -- e travar leituras so ensinava a
desligar o hook. Recusa-se a escrita, com o verbo a vista: uma
redireccao, um rm/mv/cp, um sed -i, ou SQL que altera.

Fica um buraco assumido: um `python -c` que abra a base de trabalho e
escreva la dentro sem dizer "radar.db" no comando passa. Contra isso vale
o habito de apontar a copia (`radar.DB = ...`), que e o que o comando tem
de fazer para ser deixado passar quando traz SQL de escrita.

Sai com codigo 2 para travar a ferramenta; o que for escrito no stderr
volta para o Claude como explicacao.
"""

import io
import json
import os
import re
import sys

# A consola do Windows e cp1252 e a recusa vai escrita em portugues: sem
# isto, "sessão" chegava ao Claude como "sess?o" -- ou pior, rebentava a
# leitura de quem esta do outro lado.
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                              errors="replace")

# (padrao do nome, porque e que nao se mexe)
PROTEGIDOS = (
    (r"^curl_.*\.txt$", "leva o token da sessão do browser; refaz a captura "
                        "no DevTools em vez de editar o ficheiro"),
    (r"^radar\.db(-wal|-shm)?$", "é a base de dados; se for mesmo preciso, "
                                 "mexe-lhe por SQL e com cópia antes"),
)

# Os mesmos nomes, agora para procurar no meio de um comando.
# (padrao, como se diz o nome na recusa, porque e que nao se mexe)
NOMES = (
    (r"curl_[\w.\-]*\.txt", "curl_*.txt",
     "leva o token da sessão do browser; refaz a captura no DevTools em "
     "vez de reescrever o ficheiro"),
    (r"radar\.db(?:-wal|-shm)?", "radar.db",
     "é a base de dados; se for mesmo preciso, mexe-lhe por SQL e com "
     "cópia antes"),
)

# Verbos de escrita. O %s e o nome protegido; o [^|;&]* nao deixa a
# procura saltar para outro comando da mesma linha, senao um
# "cat radar.db | wc -c && rm outra-coisa" dava-se por perigoso.
ESCRITAS = (
    r">>?\s*['\"]?[^|;&'\"]*%s",
    r"\b(?:rm|mv|cp|tee|truncate|shred|dd)\b[^|;&]*%s",
    r"\bsed\b[^|;&]*-i[^|;&]*%s",
    r"\b(?:Set-Content|Add-Content|Out-File|Remove-Item|Move-Item|"
    r"Copy-Item|New-Item|Clear-Content)\b[^|;&]*%s",
    r"\bsqlite3\b[^|;&]*%s[^|;&]*"
    r"\b(?:INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|VACUUM)\b",
)

# SQL de escrita sem dizer a que base -- a de trabalho, por omissao. Deixa
# passar quem tenha apontado a base para outro lado (um ensaio sobre uma
# copia faz exactamente isso).
SQL_ESCRITA = re.compile(
    r"\b(?:INSERT\s+(?:OR\s+\w+\s+)?INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|"
    r"DROP\s+TABLE|ALTER\s+TABLE)\b", re.I)
APONTA_NOUTRO_SITIO = re.compile(r"\bradar\s*\.\s*DB\s*=", re.I)


def por_caminho(caminho):
    nome = os.path.basename(caminho)
    for padrao, motivo in PROTEGIDOS:
        if re.match(padrao, nome, re.I):
            return "%s %s" % (nome, motivo)
    return ""


def por_comando(comando):
    for nome, rotulo, motivo in NOMES:
        for verbo in ESCRITAS:
            if re.search(verbo % nome, comando, re.I | re.S):
                return "o comando escreve em %s, que %s" % (rotulo, motivo)
    if SQL_ESCRITA.search(comando) and not APONTA_NOUTRO_SITIO.search(comando):
        return ("o comando tem SQL que altera dados e não diz sobre que base "
                "-- fica a de trabalho. Faz uma cópia e aponta-lhe o "
                "radar.DB, como no ensaio-de-leitura")
    return ""


def main():
    try:
        entrada = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0                      # sem dados legiveis, nao estorva
    dados = entrada.get("tool_input") or {}
    motivo = (por_caminho(dados.get("file_path") or "")
              or por_comando(dados.get("command") or ""))
    if motivo:
        sys.stderr.write("Recusado: %s.\n" % motivo)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
