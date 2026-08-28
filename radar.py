#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Radar de Concursos, Diario da Republica.

Vigia a parte L da serie II do DR, filtra os anuncios que interessam
e apresenta-os num painel local. Verifica sozinho as 09:00 e as 17:00.

Fonte unica: o servico de pesquisa do proprio portal do DR, chamado
com os cabecalhos de uma captura feita uma vez no browser (curl_DR.txt).

Arranque:  python radar.py             painel em http://localhost:8765
           python radar.py --uma-vez   verifica e sai, para as tarefas
           python radar.py --historico N   puxa N dias de historico
           python radar.py --reler     reanalisa o texto ja guardado
           python radar.py --importar-cpv F   carrega o vocabulario CPV
"""

import csv
import html
import io
import json
import os
import re
import queue
import shlex
import smtplib
import subprocess
import sqlite3
import sys
import tempfile
import threading
import time
import unicodedata
import webbrowser
import zipfile
from datetime import datetime, timedelta
from email.message import EmailMessage
from urllib.parse import parse_qsl, quote, unquote, urlencode

try:
    import requests
    from flask import Flask, redirect, request, Response, send_file
except ImportError:
    print("Falta instalar. Corre:  python -m pip install -r requirements.txt")
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "radar.db")
CONFIG = os.path.join(BASE_DIR, "config.json")
AMOSTRAS = os.path.join(BASE_DIR, "amostras")
# Os documentos ficam em ficheiro, nao na base: mantem o radar.db pequeno
# e rapido, e e o que se leva melhor para um servidor ou para
# armazenamento de objectos, se um dia isto sair deste PC.
DOCS = os.path.join(BASE_DIR, "documentos")
PORTA = 8765

ACAO = ("https://diariodarepublica.pt/dr/screenservices/dr/Pesquisas/"
        "PesquisaResultado/DataActionGetPesquisas")

CONFIG_INICIAL = {
    "horas_verificacao": ["09:00", "17:00"],
    "dias_catchup": 15,
    "recuperar_slot_falhado": True,
    "abrir_browser_ao_encontrar": False,
    "detalhes_por_volta": 40,
    # Copia do radar.db antes de cada verificacao. So a triagem e o
    # historico e que nao se recuperam de lado nenhum.
    "copia_de_seguranca": True,
    "copias_a_guardar": 7,
    # Alertas: os filtros guardados marcados como alerta dao um resumo
    # diario. E o que faz o radar deixar de precisar de ser aberto.
    "alertas": True,
    # A conta que **envia**. O destino ("para") pode ser qualquer um; a
    # palavra-passe vai num ficheiro a parte (email_senha.txt), nunca
    # aqui -- este ficheiro abre-se sem pensar. Os valores de origem sao
    # os do Gmail, que precisa de uma palavra-passe de aplicacao.
    "email": {
        "para": "",
        "de": "",
        "servidor": "smtp.gmail.com",
        "porta": 587,
        "hora_resumo": "17:00",
    },
    # A rotina so le o detalhe dos anuncios publicados nesta janela.
    # Entre publicacao e prazo vao ~18 dias em media, por isso mais atras
    # que isto ja fechou: o CPV desses so interessa como historico, e
    # esses sao lidos quando se abre a ficha. Poe a 0 para ler tudo.
    "detalhe_dias": 60,
    # Modelo que le o Caderno de Encargos e o Programa, na Groq. Vazio =
    # o de origem. A lista destas plataformas muda, por isso fica a jeito.
    "modelo_pecas": "",
    # Modelo por fornecedor da cadeia, p.ex. {"openrouter": "z-ai/glm-5.2:free"}.
    # Vazio = o de origem de cada um (ver FORNECEDORES).
    "modelos_pecas": {},
    # Prende a leitura a um so fornecedor ("groq", "openrouter", "nvidia").
    # Vazio = a cadeia toda, por ordem. Serve para comparar leituras.
    "fornecedor_pecas": "",
    "por_pagina": 25,
    # Tecto de seguranca, nao um alvo: o pedido para de pedir paginas
    # assim que o portal devolver menos que uma pagina cheia. So entra
    # em jogo para nao ficar preso num ciclo infinito se algo correr mal.
    "paginas": 5000,
    # Nada e filtrado a entrada. Estes termos servem so para varrer o
    # portal: com "" pede tudo, e a lista de reserva entra se o portal
    # nao aceitar pesquisa sem termo.
    "termos_de_pesquisa": [""],
    "termos_de_reserva": [
        "aquisição", "serviços", "fornecimento", "prestação",
        "concurso", "contratação"
    ],
}


# ----------------------------------------------------------------- base

def liga():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    # WAL: deixa ler enquanto outro escreve. Sem isto, o painel e a recolha
    # em fundo tropecam um no outro ("database is locked"). E persistente,
    # fica gravado na base, mas repete-se aqui porque e barato.
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=30000")
    return c


# As colunas com que o quadro comeca, vindas do desenho. Nao sao fixas:
# renomeiam-se no sitio, acrescentam-se e apagam-se no proprio quadro.
FASES_INICIAIS = ("Por analisar", "A preparar proposta", "Em revisão",
                  "Submetido", "Resultado")


def semear_fases(c):
    """Poe as fases de origem numa base que ainda nao as tenha.

    Nao mexe em fases que o utilizador ja tenha criado ou renomeado: so
    actua se o quadro estiver vazio, ou se tiver apenas a coluna
    'Guardados' que as primeiras versoes criavam sozinha -- essa e
    aproveitada como primeira fase, para nao desgarrar os cartoes que
    ja lhe estejam atribuidos."""
    fases = c.execute("SELECT id, nome FROM fases ORDER BY ordem, id").fetchall()
    if fases and not (len(fases) == 1 and fases[0]["nome"] == "Guardados"):
        return
    if fases:
        c.execute("UPDATE fases SET nome=?, ordem=1 WHERE id=?",
                  (FASES_INICIAIS[0], fases[0]["id"]))
        restantes = FASES_INICIAIS[1:]
        proxima = 2
    else:
        restantes = FASES_INICIAIS
        proxima = 1
    for nome in restantes:
        c.execute("INSERT INTO fases (nome, ordem) VALUES (?,?)", (nome, proxima))
        proxima += 1


def iniciar_db():
    with liga() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS anuncios (
            ref TEXT PRIMARY KEY, titulo TEXT, entidade TEXT,
            data_pub TEXT, tipo TEXT, url TEXT,
            cpv TEXT DEFAULT '', prazo TEXT DEFAULT '',
            preco_base TEXT DEFAULT '', plataforma TEXT DEFAULT '',
            detalhe_lido INTEGER DEFAULT 0,
            estado TEXT DEFAULT 'novo', visto_em TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS slots (
            dia TEXT, hora TEXT, corrido_em TEXT, novos INTEGER,
            PRIMARY KEY (dia, hora))""")
        c.execute("""CREATE TABLE IF NOT EXISTS estado (
            chave TEXT PRIMARY KEY, valor TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS cpv_dict (
            codigo TEXT PRIMARY KEY, codigo8 TEXT, descricao TEXT, simples TEXT)""")
        c.execute("""CREATE INDEX IF NOT EXISTS ix_cpv_dict_codigo8
                     ON cpv_dict(codigo8)""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_anuncios_data ON anuncios(data_pub)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_anuncios_cpv ON anuncios(cpv)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_anuncios_estado ON anuncios(estado)")
        c.execute("""CREATE TABLE IF NOT EXISTS fases (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, ordem INTEGER)""")
        c.execute("""CREATE TABLE IF NOT EXISTS etiquetas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, cor TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS anuncio_etiquetas (
            ref TEXT, etiqueta_id INTEGER, PRIMARY KEY (ref, etiqueta_id))""")
        c.execute("""CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT, nome TEXT,
            ficheiro TEXT, tamanho INTEGER, origem TEXT, obtido_em TEXT)""")
        c.execute("""CREATE INDEX IF NOT EXISTS ix_documentos_ref
                     ON documentos(ref)""")
        c.execute("""CREATE TABLE IF NOT EXISTS analise (
            ref TEXT PRIMARY KEY, objecto TEXT, equipa TEXT,
            documentos_proposta TEXT, preco_anormalmente_baixo TEXT,
            localizacao TEXT, modelo TEXT, fontes TEXT, quando TEXT)""")
        cols_an = [r["name"] for r in c.execute("PRAGMA table_info(analise)")]
        for nome in ("preco_anormalmente_baixo", "localizacao"):
            if nome not in cols_an:
                c.execute("ALTER TABLE analise ADD COLUMN %s TEXT" % nome)
        cols_doc = [r["name"] for r in c.execute("PRAGMA table_info(documentos)")]
        for nome, tipo in (("texto", "TEXT"), ("texto_estado", "TEXT")):
            if nome not in cols_doc:
                c.execute("ALTER TABLE documentos ADD COLUMN %s %s" % (nome, tipo))
        # Pessoas e rasto de quem fez o que. Ha uma so pessoa hoje, mas a
        # aplicacao ha-de ser partilhada, e historico nao se inventa depois.
        c.execute("""CREATE TABLE IF NOT EXISTS pessoas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE)""")
        # Conjuntos de filtros com nome. O que se guarda e a query string
        # da lista, nao as condicoes SQL: assim um filtro guardado e uma
        # ligacao, e o que aprender a fazer amanha na lista funciona nos
        # filtros de ontem sem migracao nenhuma.
        c.execute("""CREATE TABLE IF NOT EXISTS filtros_guardados (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE,
            consulta TEXT, quem TEXT, criado_em TEXT)""")
        # Os contratos passaram a ter filtros guardados proprios, e o
        # mesmo nome ("Software") pode servir nas duas listas. A
        # unicidade tem de sair de `nome` para (vista, nome), e isso nao
        # se faz com ALTER TABLE -- recria-se, uma vez so, guardando o
        # que la esta como filtro de anuncios, que e o que era.
        cols_f = [r["name"] for r in
                  c.execute("PRAGMA table_info(filtros_guardados)")]
        if "vista" not in cols_f:
            c.execute("ALTER TABLE filtros_guardados RENAME TO _filtros_velhos")
            c.execute("""CREATE TABLE filtros_guardados (
                id INTEGER PRIMARY KEY AUTOINCREMENT, vista TEXT,
                nome TEXT, consulta TEXT, quem TEXT, criado_em TEXT,
                UNIQUE (vista, nome))""")
            c.execute("""INSERT INTO filtros_guardados
                (vista, nome, consulta, quem, criado_em)
                SELECT 'anuncios', nome, consulta, quem, criado_em
                FROM _filtros_velhos""")
            c.execute("DROP TABLE _filtros_velhos")
        # Um filtro guardado que avisa. So os marcados: guardar um filtro
        # para uma consulta pontual nao pode encher a caixa de correio.
        # Depois da reconstrucao acima, senao perdia-se com ela.
        if "alerta" not in [r["name"] for r in
                            c.execute("PRAGMA table_info(filtros_guardados)")]:
            c.execute("ALTER TABLE filtros_guardados "
                      "ADD COLUMN alerta INTEGER DEFAULT 0")
        # O que ja foi avisado, para nao avisar duas vezes do mesmo e para
        # o separador poder mostrar o que ja saiu.
        c.execute("""CREATE TABLE IF NOT EXISTS alertas_vistos (
            filtro_id INTEGER, ref TEXT, visto_em TEXT, enviado_em TEXT,
            PRIMARY KEY (filtro_id, ref))""")
        c.execute("""CREATE INDEX IF NOT EXISTS ix_alertas_envio
                     ON alertas_vistos(enviado_em)""")
        c.execute("""CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT, quem TEXT,
            accao TEXT, detalhe TEXT, quando TEXT)""")
        c.execute("""CREATE INDEX IF NOT EXISTS ix_historico_ref
                     ON historico(ref)""")
        colunas = [r["name"] for r in c.execute("PRAGMA table_info(anuncios)")]
        # Migracoes idempotentes: correm sempre, nao fazem nada se ja existirem.
        for nome, tipo in (("fase_id", "INTEGER"), ("texto", "TEXT"),
                           ("pdf_url", "TEXT"), ("link_pecas", "TEXT"),
                           ("docs_estado", "TEXT"), ("responsavel", "TEXT"),
                           # o NIPC da entidade, que o DR publica sempre
                           ("nif", "TEXT")):
            if nome not in colunas:
                c.execute("ALTER TABLE anuncios ADD COLUMN %s %s" % (nome, tipo))
        semear_fases(c)


def ler_config():
    if os.path.exists(CONFIG):
        try:
            with open(CONFIG, encoding="utf-8") as f:
                guardada = json.load(f)
            cfg = dict(CONFIG_INICIAL)
            cfg.update(guardada)
            return cfg
        except ValueError:
            # Ficheiro estragado. Guarda-se uma copia antes de repor os
            # valores de origem -- caso contrario as horas, a janela de
            # datas e o resto do que o utilizador afinou desapareciam sem
            # aviso, e ler_config() corre a cada pagina.
            salvado = CONFIG + ".estragado"
            try:
                os.replace(CONFIG, salvado)
                print("config.json ilegivel; copia guardada em " + salvado)
            except OSError:
                pass
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(CONFIG_INICIAL, f, ensure_ascii=False, indent=2)
    return dict(CONFIG_INICIAL)


def importar_cpv_dict(caminho):
    """Le um ficheiro tipo [{"codigo":"72267100-0","descricao":"..."}]
    e enche a tabela cpv_dict. Corre-se uma vez; depois a base fica
    autonoma e este ficheiro deixa de ser preciso."""
    with open(caminho, encoding="utf-8") as f:
        itens = json.load(f)
    linhas = []
    for item in itens:
        codigo = str(item.get("codigo") or "").strip()
        descricao = str(item.get("descricao") or "").strip()
        if not codigo:
            continue
        codigo8 = re.sub(r"\D", "", codigo)[:8]
        linhas.append((codigo, codigo8, descricao, simplifica(descricao)))
    iniciar_db()
    with liga() as c:
        c.execute("DELETE FROM cpv_dict")
        c.executemany("INSERT INTO cpv_dict VALUES (?,?,?,?)", linhas)
    return len(linhas)


def cpv_por_termo(termo):
    """Codigos de 8 digitos cuja descricao contem o termo (sem acentos)."""
    alvo = "%" + simplifica(termo) + "%"
    with liga() as c:
        linhas = c.execute(
            "SELECT DISTINCT codigo8 FROM cpv_dict WHERE simples LIKE ?",
            (alvo,)).fetchall()
    return [r["codigo8"] for r in linhas if r["codigo8"]]


def marca(chave, valor):
    with liga() as c:
        c.execute("INSERT OR REPLACE INTO estado VALUES (?,?)",
                  (chave, str(valor)))


def le_marca(chave, omissao=""):
    with liga() as c:
        linha = c.execute("SELECT valor FROM estado WHERE chave=?",
                          (chave,)).fetchone()
    return linha["valor"] if linha else omissao


# -------------------------------------------------------------- pessoas
#
# Nao ha palavra-passe: hoje isto corre no PC de uma pessoa so, e um
# ecra de login seria atrito sem beneficio. O que existe e identidade,
# para o rasto ficar registado e os concursos poderem ser atribuidos.
# Quando isto for para um servidor partilhado, e aqui que entra a
# autenticacao a serio -- o modelo de dados ja esta preparado.

def listar_pessoas():
    with liga() as c:
        return [r["nome"] for r in
                c.execute("SELECT nome FROM pessoas ORDER BY nome")]


def criar_pessoa(nome):
    nome = (nome or "").strip()[:60]
    if not nome:
        return ""
    with liga() as c:
        c.execute("INSERT OR IGNORE INTO pessoas (nome) VALUES (?)", (nome,))
    return nome


def quem_sou():
    """Quem esta a usar a aplicacao, lido do cookie. Vazio se ninguem
    se identificou ainda -- e valido, nada bloqueia por causa disso."""
    return (request.cookies.get("quem") or "").strip()


def registar(ref, accao, detalhe=""):
    with liga() as c:
        c.execute("""INSERT INTO historico (ref,quem,accao,detalhe,quando)
                     VALUES (?,?,?,?,?)""",
                  (ref, quem_sou() or "(sem nome)", accao, detalhe,
                   datetime.now().strftime("%Y-%m-%d %H:%M")))


# --------------------------------------------------------------- quadro

CORES_ETIQUETA = ("#c0392b", "#d68910", "#1e8449", "#1f4e79",
                   "#6c3483", "#616a6b")


def listar_fases():
    with liga() as c:
        return c.execute("SELECT * FROM fases ORDER BY ordem, id").fetchall()


def primeira_fase():
    fases = listar_fases()
    return fases[0]["id"] if fases else None


def dias_restantes(prazo):
    """(dias que faltam, ja passou) a partir de 'YYYY-MM-DD', ou None."""
    if not prazo:
        return None, False
    try:
        alvo = datetime.strptime(prazo, "%Y-%m-%d").date()
    except ValueError:
        return None, False
    delta = (alvo - datetime.now().date()).days
    return delta, delta < 0


# ------------------------------------------------------------- captura

def simplifica(texto):
    """Sem acentos e em minusculas, para comparar sem surpresas."""
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


def carregar_curl(nome_base="curl_DR"):
    for nome in (nome_base + ".txt", nome_base + ".txt.txt"):
        caminho = os.path.join(BASE_DIR, nome)
        if os.path.exists(caminho):
            with open(caminho, encoding="utf-8", errors="ignore") as f:
                conteudo = f.read().strip()
            if conteudo:
                return conteudo
    return ""


def parse_curl(texto):
    """Entende o Copy as cURL nos formatos cmd e bash."""
    if '^"' in texto or "^%" in texto:
        texto = re.sub(r"\^(.)", r"\1", texto)      # o cmd escapa com ^
    texto = re.sub(r"\s*\^?\\?\r?\n\s*", " ", texto.strip())

    partes = shlex.split(texto)
    if partes and partes[0].lower().startswith("curl"):
        partes = partes[1:]

    pedido = {"url": ACAO, "headers": {}, "body": ""}
    ignorar = ("content-length", "host", "accept-encoding")
    i = 0
    while i < len(partes):
        p = partes[i]
        if p in ("-H", "--header") and i + 1 < len(partes):
            chave, _, valor = partes[i + 1].partition(":")
            if chave.strip().lower() not in ignorar:
                pedido["headers"][chave.strip()] = valor.strip()
            i += 2
        elif p in ("-b", "--cookie") and i + 1 < len(partes):
            pedido["headers"]["Cookie"] = partes[i + 1]; i += 2
        elif p in ("--data-raw", "--data", "--data-binary", "-d") and i + 1 < len(partes):
            pedido["body"] = partes[i + 1]; i += 2
        elif p in ("-A", "--user-agent") and i + 1 < len(partes):
            pedido["headers"]["User-Agent"] = partes[i + 1]; i += 2
        elif p in ("--url",) and i + 1 < len(partes):
            pedido["url"] = partes[i + 1]; i += 2
        elif p.startswith("http"):
            pedido["url"] = p; i += 1
        else:
            i += 1
    return pedido


# O Copy as cURL (cmd) do Chrome nao escreve acentos, engole-os.
# Um filtro estropiado faz o DR devolver zero sem se queixar.
VALORES_FIXOS = {"parte": "L - Contratos públicos"}


def repara_filtros(filtros):
    for chave, correcto in VALORES_FIXOS.items():
        valor = filtros.get(chave)
        if isinstance(valor, str) and valor and valor != correcto:
            if simplifica(valor).replace(" ", "")[:10] == \
               simplifica(correcto).replace(" ", "")[:10]:
                filtros[chave] = correcto


def limpa_resultados(variaveis):
    """O corpo capturado traz a resposta anterior colada. Sai daqui."""
    for chave in ("ResultadosElastic", "OSFormatedElasticResults"):
        try:
            variaveis[chave]["Hits"]["Hits"]["List"] = []
        except (KeyError, TypeError):
            pass


# ------------------------------------------------------------- leitura

def campo(origem, *nomes):
    """Le um campo sem se importar com maiusculas ou minusculas."""
    if not isinstance(origem, dict):
        return ""
    baixo = {str(k).lower(): v for k, v in origem.items()}
    for nome in nomes:
        valor = baixo.get(nome.lower())
        if valor not in (None, ""):
            return valor
    return ""


def anuncios_da_resposta(dados):
    """O DR embrulha o resultado do Elasticsearch num campo de texto,
    por isso o texto que parecer JSON tambem e aberto e percorrido."""
    encontrados = []

    def anda(no, nivel=0):
        if nivel > 14:
            return
        if isinstance(no, str):
            if no.lstrip()[:1] in ("{", "[") and len(no) > 40:
                try:
                    anda(json.loads(no), nivel + 1)
                except ValueError:
                    pass
            return
        if isinstance(no, dict):
            for chave in ("_source", "source"):
                fonte = no.get(chave)
                if isinstance(fonte, dict) and campo(fonte, "numero"):
                    encontrados.append(fonte)
                    return
            for valor in no.values():
                anda(valor, nivel + 1)
        elif isinstance(no, list):
            for item in no:
                anda(item, nivel + 1)

    anda(dados)
    return encontrados


def recolher(cfg):
    """Pergunta ao DR. Devolve (correu_bem, mensagem, novos guardados).

    O booleano vem a parte de proposito: ja se decidiu isto testando se
    a palavra "ok" aparecia na mensagem, e "Connection broken" contem
    "ok" -- uma falha de rede passava por sucesso."""
    comando = carregar_curl()
    if not comando:
        return False, "falta o curl_DR.txt, ver LEIA-ME seccao 3", 0

    pedido = parse_curl(comando)
    try:
        molde = json.loads(pedido["body"])
        variaveis = molde["screenData"]["variables"]
        filtros = variaveis["FiltrosDePesquisa"]
    except (ValueError, KeyError, TypeError):
        return False, "o curl_DR.txt nao tem um corpo legivel, refaz a captura", 0

    limpa_resultados(variaveis)
    repara_filtros(filtros)

    fim = datetime.now()
    inicio = fim - timedelta(days=int(cfg["dias_catchup"]))
    filtros["dataPublicacaoDe"] = inicio.strftime("%Y-%m-%d")
    filtros["dataPublicacaoAte"] = fim.strftime("%Y-%m-%d")
    variaveis["DataDe"] = filtros["dataPublicacaoDe"]
    variaveis["DataAte"] = filtros["dataPublicacaoAte"]
    variaveis["TipoOrdenacaoId"] = 8          # data, mais recente primeiro

    por_pagina = int(cfg["por_pagina"])
    variaveis["ResultadosPorPaginaId"] = 4 if por_pagina >= 25 else 1

    termos = list(cfg["termos_de_pesquisa"]) or [""]
    vistos, colhidos, avarias = set(), [], []
    for termo in termos:
        filtros["texto"] = termo
        variaveis["Pesquisa"] = {"List": [termo]} if termo else {"List": []}
        variaveis["TermoPesquisaAvancadaByConteudo"] = termo

        for pagina in range(int(cfg["paginas"])):
            variaveis["StartIndex"] = pagina * por_pagina
            corpo = json.dumps(molde, ensure_ascii=False).encode("utf-8")
            try:
                resposta = requests.post(pedido["url"], headers=pedido["headers"],
                                         data=corpo, timeout=60)
            except requests.RequestException as erro:
                avarias.append(str(erro)[:80])
                break

            if "json" not in resposta.headers.get("Content-Type", ""):
                guardar_amostra("resposta_inesperada.txt",
                                "HTTP %d, termo %s\n\n%s"
                                % (resposta.status_code, termo,
                                   resposta.text[:3000]))
                return False, ("o DR respondeu %d sem JSON. O token da captura "
                               "pode ter expirado, ver "
                               "amostras/resposta_inesperada.txt"
                               % resposta.status_code), 0
            try:
                dados = resposta.json()
            except ValueError:
                break

            registos = anuncios_da_resposta(dados)
            if not registos:
                break
            for origem in registos:
                numero = str(campo(origem, "numero")).strip()
                if not numero or numero in vistos:
                    continue
                vistos.add(numero)
                dbid = str(campo(origem, "dbId", "dbid")).strip()
                colhidos.append({
                    "ref": numero,
                    "tipo": str(campo(origem, "tipo")),
                    "titulo": str(campo(origem, "sumario", "title")).strip(),
                    "entidade": str(campo(origem, "emissor")),
                    "data_pub": str(campo(origem, "dataPublicacao",
                                          "dataDisponibilizacao"))[:10],
                    "url": ("https://diariodarepublica.pt/dr/detalhe/"
                            "anuncio-procedimento/"
                            + numero.replace("/", "-") + "-" + dbid),
                })
            if len(registos) < por_pagina:
                break
            time.sleep(1)

    if not colhidos and termos == [""] and cfg.get("termos_de_reserva"):
        # o portal nao aceitou pesquisa sem termo: varre pelos termos largos
        cfg = dict(cfg, termos_de_pesquisa=cfg["termos_de_reserva"])
        return recolher(cfg)

    if not colhidos:
        if avarias:
            return False, "sem ligação ao DR: " + avarias[0], 0
        return False, "o DR não devolveu anúncios nesta janela", 0

    novos = guardar(colhidos)
    guardar_amostra("ultima_colheita.json",
                    json.dumps(colhidos[:10], ensure_ascii=False, indent=2))
    return True, "ok, %d anúncios lidos" % len(colhidos), novos


# O DR escreve o CPV com oito digitos, as vezes com o digito de
# controlo a seguir: 72261000 ou 72261000-9.
CPV = re.compile(r"\b(\d{8})(?:\s*-\s*(\d))?\b")
DATA = re.compile(r"(\d{4}-\d{2}-\d{2}|\d{2}[-/]\d{2}[-/]\d{4})")
EURO = re.compile(r"(?:€|EUR)?\s*([\d\.\s]{1,15},\d{2})\s*(?:€|EUR|euros)?", re.I)
# A ordem conta: "compraspt" tem de vir antes de "compraspublicas", senao
# um endereco compraspt.com nunca chega a ser testado contra o primeiro.
PLATAFORMAS = ("acingov", "anogov", "vortal", "compraspt", "saphety",
               "gatewit", "compraspublicas", "ambisig", "construlink",
               "bizgov")


# O texto do anuncio vem em seccoes numeradas ("13 - CONDICOES DE
# APRESENTACAO") com linhas "Chave: Valor" dentro. Confirmado estavel:
# 21 seccoes presentes em 10/10 anuncios de amostra.
SECCAO = re.compile(r"^(\d{1,2})\s*-\s*(.+)$")


def seccoes_do_texto(texto):
    """Parte o anuncio em [(numero, titulo, [(chave, valor), ...]), ...].
    Guarda os pares pela ordem em que aparecem e admite chaves repetidas
    (ha anuncios com varios lotes, que repetem as mesmas chaves)."""
    seccoes, actual = [], None
    for linha_bruta in (texto or "").splitlines():
        linha_txt = linha_bruta.strip()
        if not linha_txt:
            continue
        m = SECCAO.match(linha_txt)
        if m and m.group(2).strip() == m.group(2).strip().upper():
            actual = (m.group(1), m.group(2).strip(), [])
            seccoes.append(actual)
            continue
        if actual is None:
            actual = ("", "", [])
            seccoes.append(actual)
        if ":" in linha_txt:
            chave, _, valor = linha_txt.partition(":")
            actual[2].append((chave.strip(), valor.strip()))
        else:
            actual[2].append(("", linha_txt))
    return seccoes


def valor_de(seccoes, *nomes):
    """Primeiro valor cuja chave bata certo (sem acentos, sem maiusculas)."""
    alvos = [simplifica(n) for n in nomes]
    for _, _, pares in seccoes:
        for chave, valor in pares:
            if valor and simplifica(chave) in alvos:
                return valor
    return ""


def campos_do_detalhe(texto):
    """Le do texto do anuncio os campos que servem para filtrar e listar."""
    achados = {"cpv": "", "prazo": "", "preco_base": "", "plataforma": "",
               "link_pecas": "", "nif": ""}
    seccoes = seccoes_do_texto(texto)

    # O NIPC da entidade adjudicante. Medido: o DR publica-o em **100%**
    # dos anuncios, e e o mesmo numero por que o BASE identifica a
    # entidade -- vale mais do que qualquer compararacao de nomes, que
    # falhava em 6% (sub-unidades e "EPE" contra "E. P. E.").
    nipc = valor_de(seccoes, "NIPC", "NIF", "Número de Identificação Fiscal")
    m = re.search(r"\d{9}", nipc or "")
    if not m:
        # ha anuncios em que vem colado ao nome da entidade, fora das
        # chaves numeradas
        m = re.search(r"(?:NIPC|NIF)\D{0,20}(\d{9})", texto or "", re.I)
        if m:
            m = re.match(r"(\d{9})", m.group(1))
    achados["nif"] = m.group(0) if m else ""

    # CPV: le-se das chaves de vocabulario, que trazem "72268000 - Servicos
    # de ...". Ha varios quando o procedimento tem lotes.
    codigos = []
    for _, _, pares in seccoes:
        for chave, valor in pares:
            if simplifica(chave) in ("vocabulario principal",
                                     "vocabulario complementar"):
                m = CPV.match(valor.strip())
                if m:
                    codigos.append(m.group(1) + ("-" + m.group(2) if m.group(2) else ""))
    achados["cpv"] = ", ".join(dict.fromkeys(codigos))[:120]

    prazo = valor_de(seccoes, "Prazo para apresentação das propostas",
                     "Prazo para apresentação das propostas ou pedidos de participação",
                     "Data limite para apresentação das propostas")
    if prazo:
        m = DATA.search(prazo)
        if m:
            achados["prazo"] = normaliza_data(m.group(1))

    preco = valor_de(seccoes, "Valor do preço base do procedimento",
                     "Preço base s/IVA", "Preço base")
    if preco:
        m = EURO.search(preco)
        if m:
            achados["preco_base"] = " ".join(m.group(1).split()) + " EUR"

    achados["link_pecas"] = valor_de(
        seccoes, "Link para acesso às peças do concurso (URL)",
        "Endereço da plataforma electrónica onde as peças estão disponíveis")

    # A plataforma le-se do URL de apresentacao, e so em ultimo recurso do
    # texto todo, para nao apanhar uma mencao de passagem.
    pistas = " ".join((valor_de(seccoes, "URL para Apresentação"),
                       valor_de(seccoes, "Plataforma eletrónica utilizada "
                                          "pela entidade adjudicante"),
                       achados["link_pecas"]))
    alvo = simplifica(pistas) or simplifica(texto)
    for nome in PLATAFORMAS:
        if nome in alvo:
            achados["plataforma"] = nome
            break
    else:
        if "acin" in alvo:
            achados["plataforma"] = "acingov"
    return achados


def normaliza_data(bruta):
    bruta = bruta.replace("/", "-")
    if len(bruta) == 10 and bruta[4] == "-":
        return bruta
    dia, mes, ano = bruta.split("-")
    return "%s-%s-%s" % (ano, mes, dia)


def _molde_detalhe():
    """(pedido, molde) a partir da captura, ou (None, aviso)."""
    comando = carregar_curl("curl_detalhe")
    if not comando:
        return None, "sem curl_detalhe.txt"
    pedido = parse_curl(comando)
    try:
        molde = json.loads(pedido["body"])
        molde["screenData"]["variables"]
    except (ValueError, KeyError, TypeError):
        return None, "curl_detalhe.txt ilegivel"
    return (pedido, molde), ""


def _guardar_detalhe(ref, dados):
    """Caminhos exactos, confirmados na resposta do DR."""
    conteudo = (dados.get("data") or {}).get("DetalheConteudo") or {}
    texto = conteudo.get("Texto") or ""
    campos = campos_do_detalhe(texto)
    with liga() as c:
        c.execute("""UPDATE anuncios SET cpv=?, prazo=?, preco_base=?,
                     plataforma=?, texto=?, pdf_url=?, link_pecas=?, nif=?,
                     detalhe_lido=1 WHERE ref=?""",
                  (campos["cpv"], campos["prazo"], campos["preco_base"],
                   campos["plataforma"], texto, conteudo.get("URL_PDF") or "",
                   campos["link_pecas"], campos["nif"], ref))
    return texto


def ler_detalhe_de(ref):
    """Le o detalhe de UM anuncio, agora. E o que corre quando se abre a
    ficha de um anuncio que ainda nao foi lido: um pedido, ~1 segundo."""
    par, aviso = _molde_detalhe()
    if not par:
        return False, aviso
    pedido, molde = par
    with liga() as c:
        a = c.execute("SELECT url FROM anuncios WHERE ref=?", (ref,)).fetchone()
    if not a:
        return False, "anúncio desconhecido"
    variaveis = molde["screenData"]["variables"]
    variaveis["Key"] = a["url"].rsplit("/", 1)[-1]
    variaveis["Tipo"] = "anuncio-procedimento"
    try:
        r = requests.post(pedido["url"], headers=pedido["headers"],
                          data=json.dumps(molde, ensure_ascii=False).encode("utf-8"),
                          timeout=60)
        if "json" not in r.headers.get("Content-Type", ""):
            return False, "o DR respondeu sem JSON, a captura pode ter expirado"
        _guardar_detalhe(ref, r.json())
        return True, ""
    except (requests.RequestException, ValueError) as erro:
        return False, "falhou a leitura do anúncio: %s" % str(erro)[:100]


def ler_detalhes(limite=40, dias=None):
    """Le o detalhe dos anuncios que ainda nao o tem, do mais recente
    para o mais antigo.

    `dias` limita aos publicados nesse periodo. Serve para a rotina so
    tratar do que ainda da para concorrer: entre a publicacao e o prazo
    vao ~18 dias em media, por isso um anuncio de ha 3 meses ja fechou e
    o CPV dele so interessa como historico. Os antigos sao lidos quando
    se abre a ficha, e nao em massa.

    O texto fica na base, por isso reanalisar nunca mais precisa de rede."""
    par, aviso = _molde_detalhe()
    if not par:
        return 0, aviso
    pedido, molde = par
    variaveis = molde["screenData"]["variables"]

    condicao, valores = "detalhe_lido=0", []
    if dias:
        condicao += " AND data_pub >= ?"
        valores.append((datetime.now() - timedelta(days=int(dias)))
                       .strftime("%Y-%m-%d"))
    valores.append(limite)

    with liga() as c:
        pendentes = c.execute(
            "SELECT ref,url FROM anuncios WHERE " + condicao +
            " ORDER BY data_pub DESC LIMIT ?", valores).fetchall()

    feitos = 0
    for a in pendentes:
        variaveis["Key"] = a["url"].rsplit("/", 1)[-1]   # 21171-2026-1160416962
        variaveis["Tipo"] = "anuncio-procedimento"
        try:
            r = requests.post(pedido["url"], headers=pedido["headers"],
                              data=json.dumps(molde, ensure_ascii=False).encode("utf-8"),
                              timeout=60)
            if "json" not in r.headers.get("Content-Type", ""):
                return feitos, "o detalhe respondeu sem JSON, captura expirada?"
            dados = r.json()
        except (requests.RequestException, ValueError):
            break
        _guardar_detalhe(a["ref"], dados)
        feitos += 1
        time.sleep(1)
    return feitos, ""


def reparsear(limite=None):
    """Reanalisa o texto ja guardado, sem tocar na rede. E o que se corre
    depois de melhorar campos_do_detalhe()."""
    with liga() as c:
        linhas = c.execute(
            "SELECT ref,texto FROM anuncios WHERE texto IS NOT NULL AND texto != ''"
            + (" LIMIT %d" % int(limite) if limite else "")).fetchall()
    feitos = 0
    with liga() as c:
        for a in linhas:
            campos = campos_do_detalhe(a["texto"])
            c.execute("""UPDATE anuncios SET cpv=?, prazo=?, preco_base=?,
                         plataforma=?, link_pecas=?, nif=? WHERE ref=?""",
                      (campos["cpv"], campos["prazo"], campos["preco_base"],
                       campos["plataforma"], campos["link_pecas"],
                       campos["nif"], a["ref"]))
            feitos += 1
    return feitos


# --------------------------------------------------------- documentos
#
# As pecas do procedimento (Programa de Concurso, Caderno de Encargos,
# anexos) nao estao no DR: estao na plataforma electronica indicada no
# anuncio, na seccao 15. O que se consegue, por plataforma:
#
#   acingov  ~45%  um GET no link devolve um ZIP com tudo. Directo.
#   vortal   ~45%  o link e uma pagina em JavaScript, mas por tras tem
#                  API publica. Tres saltos: o identificador cifrado do
#                  link -> GetPublicTenderInformation -> o PT1.NTC.x ->
#                  GetContractNoticeDocuments -> lista com URL de cada um.
#   anogov    ~8%  a pagina lista os documentos e cada um sai de um
#   compraspt ~1%  'decryptservlet'. Mesma aplicacao JSF, mesmo codigo.
#
# Nenhum destes precisa de browser nem de credenciais.

NAVEGADOR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")
VORTAL_INFO = ("https://community.vortal.biz/public/api/PublicTenderDocuments/"
               "GetPublicTenderInformation")
VORTAL_DOCS = ("https://community.vortal.biz/public/api/ContractNoticeDetail/"
               "GetContractNoticeDocuments")


def pasta_do_anuncio(ref):
    return os.path.join(DOCS, re.sub(r"[^0-9A-Za-z._-]", "-", ref))


def nome_seguro(nome):
    """So o nome do ficheiro, sem caminhos, para um ZIP nao poder escrever
    fora da pasta do anuncio."""
    nome = os.path.basename((nome or "").replace("\\", "/").rstrip("/"))
    nome = re.sub(r'[<>:"|?*\x00-\x1f]', "_", nome).strip(". ")
    return nome[:150] or "documento"


def _pecas_acingov(sessao, link):
    """Devolve [(nome, bytes)] a partir do ZIP das pecas."""
    _, bruto = _descarregar(sessao, link, limite=MAX_FICHEIRO * 4)
    if not bruto or not bruto.startswith(b"PK"):
        return [], (["o ZIP das peças"] if bruto is None else [])
    saida, grandes = [], []
    with zipfile.ZipFile(io.BytesIO(bruto)) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            if info.file_size > MAX_FICHEIRO:
                grandes.append(info.filename)
                continue
            saida.append((nome_seguro(info.filename), z.read(info)))
    return saida, grandes


def _pecas_vortal(sessao, link):
    identificador = link.rstrip("/").rsplit("/", 1)[-1]
    info = sessao.get(VORTAL_INFO, timeout=90, params={
        "uniqueIdentifierEncrypted": identificador, "languageCode": "pt"}).json()
    aviso = info.get("contractNoticeUrl") or ""
    m = re.search(r"(PT\d+\.NTC\.\d+)", aviso)
    if not m:
        return [], []
    lista = sessao.get(VORTAL_DOCS, timeout=90,
                       params={"contractNoticeUId": m.group(1)}).json()
    saida, grandes = [], []
    for doc in lista if isinstance(lista, list) else []:
        endereco = doc.get("downloadUrl")
        if not endereco:
            continue
        nome, dados = _descarregar(sessao, endereco)
        if dados is None:
            if doc.get("name"):
                grandes.append(doc["name"])
            continue
        saida.append((nome_seguro(doc.get("name") or nome or "documento"), dados))
    return saida, grandes


# Aquelas de que se conseguem trazer as pecas sem sessao iniciada. Serve
# tambem para o ecra de indicadores nao chamar "sem acesso" ao que se
# obtem, nem prometer o que nao se obtem.
PLATAFORMAS_COM_PECAS = ("acingov", "vortal", "compraspt", "anogov")

# Valor que representa "o anuncio nao diz qual e", no filtro e no ecra de
# indicadores. Nao e uma plataforma, e a ausencia de uma.
SEM_PLATAFORMA = "(nenhuma)"

# anogov, compraspt e a plataforma da ESPAP sao a mesma aplicacao JSF,
# do mesmo fornecedor: 'faces/app/acessoDocs.jsp' lista os documentos em
# HTML e cada ficheiro sai de um 'decryptservlet' no mesmo servidor.
#
# Reconhece-se pela assinatura da aplicacao e nao pelo dominio: os
# concursos da ESPAP (plataforma-sncp.espap.gov.pt) vinham marcados como
# anogov no DR mas com link noutro host, e ficavam de fora -- a ficha
# dizia "nao sei trazer as pecas da plataforma anogov" com a plataforma
# bem identificada. Sao 14 na base, e vem mais com cada camara que
# estreie o seu proprio dominio.
# Comparada contra link.lower(), como o RX_DOC_JSF que e re.I: as duas
# metades da mesma decisao tem de concordar.
ASSINATURA_JSF = "/faces/app/acessodocs.jsp"
RX_DOC_JSF = re.compile(r'href="(https://[^"]*/decryptservlet\?[^"]*)"', re.I)


def docs_jsf_da_pagina(pagina, link):
    """Os documentos listados, so os que estao no mesmo servidor.

    A pagina e conteudo vindo de fora: um endereco noutro servidor nao e
    coisa para se ir buscar so porque ela o listou.
    """
    origem = re.match(r"https?://[^/]+", link)
    origem = origem.group(0) if origem else ""
    achados = []
    for endereco in dict.fromkeys(RX_DOC_JSF.findall(pagina)):
        endereco = html.unescape(endereco)
        if origem and endereco.startswith(origem + "/") and endereco not in achados:
            achados.append(endereco)
    return achados


def _pecas_jsf(sessao, link):
    """Pecas da anogov, da ComprasPT e da ESPAP. O nome vem no
    Content-Disposition.

    A pagina responde a um GET com o codigo de acesso que vem no anuncio,
    sem sessao iniciada. **O codigo tem ~50 caracteres**: se aparecer
    curto, foi truncado por quem o imprimiu, e a pagina responde
    "nao foi encontrado nenhum documento" -- que se confunde facilmente
    com "esta plataforma nao da acesso". Deu-se essa volta duas vezes."""
    pagina = sessao.get(link, timeout=120)
    pagina.encoding = "windows-1252"
    saida, grandes = [], []
    for endereco in docs_jsf_da_pagina(pagina.text, link):
        nome, dados = _descarregar(sessao, endereco)
        if dados is None:
            if nome:
                grandes.append(nome)
            continue
        saida.append((nome_seguro(nome or "documento"), dados))
    return saida, grandes


# Tecto por ficheiro. A Infraestruturas de Portugal publica anexos
# tecnicos enormes -- um anuncio real trouxe 551 MB num unico ZIP. Sem
# isto, uma triagem de dez anuncios enche o disco e a memoria, porque o
# conteudo era todo juntado antes de se decidir o que fazer com ele.
MAX_FICHEIRO = 60 * 1024 * 1024


def _descarregar(sessao, endereco, limite=MAX_FICHEIRO):
    """(nome, bytes) ou (nome, None) se passar do tecto.

    Le por pedacos e desiste a meio: assim um ficheiro de 500 MB custa o
    tamanho do pedaco, nao 500 MB de memoria."""
    with sessao.get(endereco, timeout=180, stream=True) as r:
        if r.status_code != 200:
            return "", None
        nome = _nome_da_resposta(r)
        declarado = r.headers.get("Content-Length")
        if declarado and declarado.isdigit() and int(declarado) > limite:
            return nome, None
        pedacos, total = [], 0
        for pedaco in r.iter_content(262144):
            total += len(pedaco)
            if total > limite:
                return nome, None
            pedacos.append(pedaco)
    return nome, (b"".join(pedacos) or None)


# --------------------------------------------- texto das peças (PDF)
#
# O passo anterior a qualquer analise: tirar o texto dos PDFs. E
# independente de quem os venha a ler depois, e por isso faz-se ja.
#
# Medido sobre 12 Cadernos de Encargos e Programas reais: 10 dao texto
# (5 a 16 mil tokens cada, 10 a 27 paginas) e 2 sao digitalizacoes sem
# camada de texto, onde isto nao chega -- ficam marcados como 'scan'.

# Abaixo disto por pagina, o PDF e imagem: nao vale a pena guardar.
CHARS_POR_PAGINA_MINIMO = 120


def texto_do_pdf(caminho):
    """(texto, estado). Estado: 'ok', 'scan', ou 'erro: ...'."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return "", "erro: falta o pypdf (python -m pip install pypdf)"
    try:
        leitor = PdfReader(caminho)
        paginas = len(leitor.pages)
        texto = "\n".join((p.extract_text() or "") for p in leitor.pages)
    except Exception as erro:
        # os PDFs do anuncio do DR vem cifrados com AES e rebentam aqui,
        # mas nao fazem falta: o texto do anuncio ja veio do portal
        return "", "erro: %s" % str(erro)[:80]
    if paginas and len(texto) / paginas < CHARS_POR_PAGINA_MINIMO:
        return "", "scan"
    return texto, "ok"


def e_pdf(caminho):
    """Pelos primeiros bytes, e nao pela extensao.

    A vortal entrega ficheiros sem extensao nenhuma -- um anuncio trazia
    um "Caderno de Encargos" de 291 KB, PDF por dentro, que ficava
    marcado como "nao e PDF" e por ler.
    """
    try:
        with open(caminho, "rb") as f:
            cabeca = f.read(1024)
    except OSError:
        return False
    # Um ZIP com um PDF la dentro por comprimir traz o "%PDF" no byte 46
    # -- e o zipfile.writestr guarda assim, por omissao. Sem esta linha
    # o pacote dava-se por PDF: o extrair_textos pergunta aqui antes de
    # ir ao texto_do_zip, e o ZIP nunca chegava a ser aberto.
    if cabeca.startswith(b"PK\x03\x04"):
        return False
    # A norma tolera lixo antes da assinatura, e ha ferramentas que
    # deixam la um BOM ou uma linha em branco; o pypdf le-os na mesma,
    # por isso nao se exige o byte 0.
    return b"%PDF" in cabeca


def texto_do_zip(caminho, papeis):
    """O texto das peças que vierem dentro de um ZIP.

    Ha entidades que entregam o Caderno de Encargos como
    "1_CE_Clausulas_Juridicas_Tecnicas.zip", com as clausulas juridicas
    num PDF e as tecnicas noutro. Sem abrir, ficavam por ler.
    """
    try:
        with zipfile.ZipFile(caminho) as z:
            dentro = [n for n in z.namelist() if n.lower().endswith(".pdf")]
            if not dentro:
                return "", "não é PDF"
            # Se algum PDF de dentro for da peça que se procura, é esse
            # que conta; senão vão todos, que o ZIP já se chama assim.
            proprios = [n for n in dentro if papeis_da_peca(n) & papeis]
            partes, estados = [], []
            with tempfile.TemporaryDirectory() as temporaria:
                for nome in (proprios or dentro):
                    alvo = os.path.join(
                        temporaria, nome_seguro(os.path.basename(nome)))
                    with open(alvo, "wb") as f:
                        f.write(z.read(nome))
                    texto, estado = texto_do_pdf(alvo)
                    estados.append(estado)
                    if estado == "ok":
                        partes.append(texto)
    except (zipfile.BadZipFile, OSError, KeyError) as erro:
        return "", "erro: %s" % str(erro)[:80]
    if partes:
        return "\n\n".join(partes), "ok"
    # Nao sai texto por duas razoes muito diferentes, e dize-las trocadas
    # manda a pessoa buscar a ferramenta errada: um PDF cifrado nao se
    # resolve com OCR.
    erros = [e for e in estados if e.startswith("erro")]
    return "", (erros[0] if erros else "scan")


def extrair_textos(ref):
    """Guarda o texto dos PDFs deste anuncio. Devolve (lidos, digitalizados)."""
    with liga() as c:
        docs = c.execute("SELECT id,nome FROM documentos WHERE ref=? "
                         "AND texto_estado IS NULL", (ref,)).fetchall()
    pasta = pasta_do_anuncio(ref)
    lidos = scans = 0
    for d in docs:
        caminho = os.path.join(pasta, d["nome"])
        papeis = papeis_da_peca(d["nome"])
        if not os.path.exists(caminho):
            estado, texto = "não é PDF", ""
        elif e_pdf(caminho):
            texto, estado = texto_do_pdf(caminho)
        elif papeis and zipfile.is_zipfile(caminho):
            texto, estado = texto_do_zip(caminho, papeis)
        else:
            estado, texto = "não é PDF", ""
        with liga() as c:
            c.execute("UPDATE documentos SET texto=?, texto_estado=? WHERE id=?",
                      (texto, estado, d["id"]))
        if estado == "ok":
            lidos += 1
        elif estado == "scan":
            scans += 1
    return lidos, scans


# ------------------------------------------- leitura das peças por modelo
#
# Tres campos que o anuncio do DR nao tem e que so estao no Caderno de
# Encargos e no Programa de Concurso. Sao os unicos que justificam um
# modelo -- todo o resto sai do texto do anuncio ou de calculo.
#
# So vao documentos publicos: Cadernos de Encargos e Programas de
# Concurso, que as entidades publicam para quem os quiser. Propostas,
# CVs e trabalho proprio nao passam por aqui.

NOMES_CHAVE = ("chave_api.txt", "groq_API_KEY.txt", "groq_api_key.txt")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
# Pesos abertos. O contexto do modelo (131 mil tokens) nao e a
# limitacao: o tecto da conta e de 8000 tokens por minuto, e e esse que
# manda no tamanho do pedido. Fica no config.json porque a lista de
# modelos destas plataformas muda.
GROQ_MODELO = "openai/gpt-oss-120b"
# A cadeia de reserva. O tecto diario da Groq (200 mil tokens) chega ao
# fim a meio de uma releitura do acervo, e ate ai a fila ficava parada
# de um dia para o outro. Todos estes falam o dialecto da OpenAI
# (/chat/completions, Bearer, response_format), por isso a cadeia e uma
# lista de enderecos e nao tres clientes diferentes.
#
# So entra quem tiver chave: um fornecedor por configurar custava uma
# volta e um 401 a cada pergunta. Ordem = prioridade; a Groq fica a
# frente por ser a unica com leituras julgadas boas.
#
# Os nomes dos ficheiros de chave ja estao cobertos pelo .gitignore
# (*[Aa][Pp][Ii]_[Kk][Ee][Yy]*), de proposito largo.
#
# O ultimo campo sao extras a juntar ao corpo do pedido, que nao sao
# iguais em todos. Medido a 2026-08-27 no 21507/2026, recorte de 3770
# caracteres:
#
# | fornecedor | tempo | nota                                        |
# |------------|-------|---------------------------------------------|
# | groq       |  1,2s | a referencia                                |
# | nvidia     |  168s | com o raciocinio por omissao                |
# | nvidia     |  3,5s | com reasoning_effort=low                    |
# | openrouter |  429  | pool gratuito partilhado, esgotado a montante |
#
# Os 168 segundos do NVIDIA nao cabiam no timeout de 180: dois dos tres
# pedidos de um concurso estouravam. E o mesmo gpt-oss-120b da Groq, mas
# aqui vem com o raciocinio ligado -- e o raciocinio nao serve para
# nada nisto, que e extraccao de texto que esta a vista. O
# reasoning_effort nao vai para os outros porque nem todos o aceitam, e
# um 400 por um parametro a mais tirava o fornecedor da cadeia.
FORNECEDORES = (
    ("groq", GROQ_URL, GROQ_MODELO, NOMES_CHAVE, "GROQ_API_KEY", {}),
    ("nvidia", "https://integrate.api.nvidia.com/v1/chat/completions",
     "openai/gpt-oss-120b", ("nvidia_API_KEY.txt",), "NVIDIA_API_KEY",
     {"reasoning_effort": "low"}),
    # Fica em ultimo por ser o unico que le com outro modelo, e o unico
    # que ja recusou por falta de vaga no pool gratuito.
    ("openrouter", "https://openrouter.ai/api/v1/chat/completions",
     "z-ai/glm-5.2:free", ("openrouter_API_KEY.txt",), "OPENROUTER_API_KEY",
     {}),
)
# Cada campo tem o seu recorte e o seu pedido. Juntos num so, as
# ancoras do objecto gastavam o orcamento antes de se chegar a tabela de
# perfis: num Caderno de Encargos de 167 mil caracteres ela estava na
# posicao 136 mil, e o modelo respondia "conforme o Anexo I do Caderno
# de Encargos" -- que e verdade e nao serve para nada. Separados, a
# equipa disputa 5 titulos em vez de 21, e quatro deles sao a zona
# certa.
# 7000 caracteres sao ~2 mil tokens (o portugues destes documentos anda
# nos 3,5 caracteres por token); tres pedidos cabem no tecto de 8000 por
# minuto.
TECTO_RECORTE = 7000

# Onde e que mora cada campo. O numero e a prioridade: quando o
# orcamento acaba, corta-se pelos 3 antes de tocar nos 1.
# Comparadas contra simplifica(): sem acentos e em minusculas.
ANCORAS_OBJECTO = (
    (1, r"objec?to\b|\bsolucao|\bambito|enquadramento"),
    # O regime -- presencial, remoto ou hibrido -- vem no mesmo pedido que
    # o objecto, por ser o mesmo documento. Prioridade 1 para nao ser o
    # primeiro a ser cortado quando o recorte enche: e uma clausula curta,
    # custa pouco, e sem ela o campo fica vazio de vez.
    (1, r"local d[aeo]|instalacoes|teletrabalho|presencial|regime de trabalho"),
    (2, r"requisitos|especificacoes|funcionalidades|servicos a prestar"),
    (3, r"niveis de servico|entregaveis|plano de trabalhos"),
)
ANCORAS_EQUIPA = (
    (1, r"\bequipa|perfil|profissiona|recursos humanos|senioridade"),
    (2, r"composicao|afetacao|alocacao|quadro de pessoal"),
)
ANCORAS_PROGRAMA = (
    (1, r"documentos.{0,25}proposta|proposta.{0,25}documentos"),
    (2, r"apresentacao da proposta|termos.{0,20}proposta"),
    (2, r"anormalmente baixo"),
    (3, r"habilitacao|criterio"),
)

PREAMBULO = """És um analista de concursos públicos portugueses. Lês
peças de um procedimento e extrais o que te for pedido.

Responde SÓ com JSON. Se algo não constar das peças, põe exactamente
"não consta". Não inventes, e não mandes o leitor consultar outro
documento: se a informação está nas peças, transcreve-a. Escreve em
português de Portugal."""

INSTRUCOES_OBJECTO = PREAMBULO + """

Extrai duas coisas do Caderno de Encargos:

- "objecto": o âmbito do serviço decomposto em pontos concretos, um por
  linha começada por "- ". UMA LINHA POR OBRIGAÇÃO ou requisito técnico
  principal. Sem introduções e sem texto jurídico acessório: nada de "o
  presente caderno de encargos tem por objecto". Não repitas o título do
  concurso — enumera o que tem mesmo de ser feito (desenvolvimento,
  migração, integrações, formação, garantia, suporte, prazos parciais).

- "localizacao": onde e como o serviço é prestado. Começa pelo REGIME
  numa palavra — presencial, remoto ou híbrido — e a seguir o que o
  documento exige em concreto: as instalações nomeadas, quantos dias por
  semana se exige presença, deslocações previstas. Exemplos do formato:
  "Presencial, nas instalações do INFARMED em Lisboa"; "Híbrido: 2 dias
  por semana presenciais"; "Remoto, com deslocações pontuais a Lisboa
  para reuniões de acompanhamento".
  Se o documento não disser nada sobre presença nem regime, responde
  "não consta" — NÃO deduzas o regime a partir da morada da entidade.

Responde SÓ com {"objecto": "...", "localizacao": "..."}."""

INSTRUCOES_EQUIPA = PREAMBULO + """

Extrai os PERFIS exigidos para a equipa. Um bloco por perfil, com esta
estrutura exacta e uma linha em branco entre blocos:

Nome do perfil tal e qual está no documento
Formação: área e grau exigidos, ou —
Experiência geral: X anos, ou —
Experiência específica: tecnologia, sector ou dimensão; se for mais do
que uma, as seguintes em linhas próprias começadas por "- "
Certificações: a lista exacta, ou —
Outras condições: dedicação, presença, preço máximo/hora, ou —

Regras duras:
- Copia o nome do perfil TAL E QUAL. Não acrescentes "sénior", "júnior"
  nem qualquer qualificador que não esteja lá.
- Cada requisito numa linha autónoma.
- Se o documento não quantifica, escreve a expressão exacta que lá está,
  sem interpretar: "experiência relevante" fica "experiência relevante".
- Onde não houver exigência, escreve — (travessão). Não inventes e não
  deixes a linha de fora.
- N perfis no documento, N blocos na resposta. Se há uma tabela de
  perfis, passa-a toda.
- Transcreve os números que lá estão. Nunca escrevas "conforme o Anexo"
  nem "experiência comprovada".

Repara SEMPRE se os requisitos são de cada perfil ou da equipa "em
conjunto": não é a mesma coisa para quem concorre — sete certificações
numa pessoa ou espalhadas por quatro. Não atribuas a um perfil o que o
documento exige ao conjunto; para esse faz um bloco final com o nome
"Em conjunto, a equipa deve deter".

Responde SÓ com {"equipa": "..."}."""

INSTRUCOES_PROPOSTA = PREAMBULO + """

Extrai duas coisas do Programa de Concurso:

- "documentos_proposta": a lista NUMERADA dos documentos que o
  CONCORRENTE tem de entregar na proposta, assim:

  1. Designação do documento
  Condições especiais: em que casos é exigido, ou o que tem de conter

  A linha "Condições especiais" só aparece quando há mesmo alguma; um
  documento que se entregue sempre e sem condições fica só com o número
  e o nome.

  Escreve o NOME CURTO de cada documento, não o texto da alínea. Isto é
  uma lista para preparar a proposta, não uma citação do Programa: cinco
  a dez palavras no nome. Escreve "1. DEUCP", e não "1. Documento
  Europeu Único de Contratação Pública, aprovado pelo Regulamento de
  Execução (EU) 2016/7 da Comissão, de 5 de janeiro de 2016, cujo
  modelo pré-preenchido (...)".

  Usa a sigla quando ela é corrente (DEUCP, CV, certidão permanente).
  Guarda o anexo ou modelo a usar, que muda o que há a fazer
  ("2. Modelo da Proposta (Anexo II)"). Deita fora números de
  regulamento, datas de diplomas e as fórmulas jurídicas de rotina.

  NÃO omitas nenhum documento e NÃO fundas as regras de documentos
  distintos: se o Programa tem sete alíneas, a lista tem sete números.
- "preco_anormalmente_baixo": o limiar a partir do qual o preço da
  proposta é tido por anormalmente baixo (art. 71.º do CCP) — a
  percentagem ou o valor. Muitos Programas não fixam nenhum: nesse caso
  responde "não consta". Não confundas com o preço base.

ATENÇÃO a uma confusão frequente: "documentos que constituem a proposta"
(o que tu entregas) NÃO é o mesmo que "peças que constituem o
procedimento" (anúncio, programa, caderno de encargos). Queremos o
primeiro.

Responde SÓ com {"documentos_proposta": "...",
"preco_anormalmente_baixo": "..."}."""

# Uma leitura por campo: que documentos ler, onde procurar, o que pedir.
LEITURAS = (
    ("objecto", "encargos", ANCORAS_OBJECTO, INSTRUCOES_OBJECTO),
    ("equipa", "encargos", ANCORAS_EQUIPA, INSTRUCOES_EQUIPA),
    ("proposta", "programa", ANCORAS_PROGRAMA, INSTRUCOES_PROPOSTA),
)


def ler_chave(nomes, variavel):
    """A chave fica num ficheiro a parte, fora do git. Tambem se aceita
    a variavel de ambiente."""
    for nome in nomes:
        caminho = os.path.join(BASE_DIR, nome)
        if os.path.exists(caminho):
            with open(caminho, encoding="utf-8") as f:
                chave = f.read().strip()
            if chave:
                return chave
    return (os.environ.get(variavel) or "").strip()


def modelo_do_fornecedor(cfg, nome, omissao):
    """O modelo a usar num fornecedor: config, senao o de origem.

    O config antigo tinha um so "modelo_pecas", e era o da Groq --
    continua a valer para ela, senao a linha que la esta passava a
    escolher o modelo do fornecedor errado no dia em que a cadeia
    entrasse.
    """
    mapa = cfg.get("modelos_pecas") or {}
    if isinstance(mapa, dict) and (mapa.get(nome) or "").strip():
        return mapa[nome].strip()
    if nome == "groq" and (cfg.get("modelo_pecas") or "").strip():
        return cfg["modelo_pecas"].strip()
    return omissao


def cadeia_de_fornecedores(cfg=None):
    """Os fornecedores com chave, por ordem de prioridade.

    Devolve tuplos (nome, url, modelo, chave, extras). Vazia quer dizer
    que nao ha chave nenhuma configurada -- e o mesmo que o antigo
    "falta a chave da API".
    """
    cfg = ler_config() if cfg is None else cfg
    so_este = (cfg.get("fornecedor_pecas") or "").strip()
    cadeia = []
    for nome, url, omissao, nomes, variavel, extras in FORNECEDORES:
        if so_este and nome != so_este:
            continue
        chave = ler_chave(nomes, variavel)
        if chave:
            cadeia.append((nome, url, modelo_do_fornecedor(cfg, nome, omissao),
                           chave, extras))
    return cadeia


RX_MARCADOR = re.compile(r"^(clausula|artigo|anexo|capitulo|seccao|apendice)\b")
RX_NUMERADO = re.compile(r"^[0-9IVXivx]+\s*[.)ºª-]+\s*[A-ZÀ-Ý]")


def e_titulo(crua, curta):
    """Um titulo de seccao, e nao uma frase do corpo com a palavra dentro.

    A diferenca que conta: um titulo nao acaba em pontuacao de frase e
    comeca por maiuscula ou por marcador -- "Clausula 1a - Objeto",
    "3. Equipa", "Perfil de Equipa". Ja "as rejeicoes sao objeto de
    notificacao ao adjudicatario." e corpo, e nao vale o orcamento.
    """
    if not (3 < len(crua) <= 70) or crua[-1] in ".,;:":
        return False
    return bool(RX_MARCADOR.match(curta) or RX_NUMERADO.match(crua)
                or crua[0].isupper())


# As primeiras paginas de um Caderno de Encargos sao o indice, e o
# indice casa com todas as ancoras: "Artigo 1.o | Objeto ....... 2".
# Sem isto, o recorte do 21275/2026 era o sumario -- e o modelo
# respondia "nao consta" com o documento inteiro por ler ao lado.
# Sao 2% das linhas do acervo; as unicas que nao sao indice sao os
# espacos para preencher dos anexos ("em ........, na qualidade de").
RX_LINHA_DE_INDICE = re.compile(r"\.\s*\.\s*\.\s*\.\s*\.")


def sem_indice(texto):
    """O texto sem as linhas pontilhadas do sumario."""
    return "\n".join(l for l in texto.split("\n")
                      if not RX_LINHA_DE_INDICE.search(l))


def recorte_relevante(texto, ancoras, tecto, janela=3500):
    """As partes do documento que respondem ao que se procura.

    Um Caderno de Encargos tem 50 mil caracteres e so uns 10 mil dizem
    respeito ao objecto e a equipa; o resto sao clausulas de rotina
    (forca maior, subcontratacao, penalidades). O tecto de tokens por
    minuto da API obriga a escolher, e escolher tambem melhora a
    leitura, por tirar ruido do caminho do modelo.
    """
    pos, titulos = 0, []
    for linha in texto.split("\n"):
        crua = linha.strip()
        curta = simplifica(crua)
        if e_titulo(crua, curta):
            for peso, padrao in ancoras:
                if re.search(padrao, curta):
                    titulos.append((peso, pos))
                    break
        pos += len(linha) + 1
    if not titulos:
        return texto[:tecto]

    marca, gasto = bytearray(len(texto)), 0
    for _, p in sorted(titulos):
        if gasto >= tecto:
            break
        for i in range(max(0, p - 200), min(len(texto), p + janela)):
            if not marca[i]:
                marca[i] = 1
                gasto += 1

    partes, i, n = [], 0, len(texto)
    while i < n:
        if not marca[i]:
            i += 1
            continue
        j = i
        while j < n and marca[j]:
            j += 1
        partes.append(texto[i:j])
        i = j
    return "\n[...]\n".join(partes)[:tecto]


# As entidades gravam os ficheiros como lhes apetece.
# "1_02_CE_28_2026_CP_DO_signed.pdf" e um Caderno de Encargos e nao tem
# 'caderno' nem 'encargos' no nome; "2_01_PP_28_2026..." e um Programa.
# Sem isto ficavam por ler, com o texto ja extraido e ali a jeito.
#
# Vai-se pelo nome e nao pelo conteudo: os Programas citam o Caderno de
# Encargos logo nas primeiras paginas, e ate o "Lista.pdf" -- que e o
# indice das pecas -- diz "Caderno de Encargos". Pelo nome nao ha um
# unico engano no acervo; pelo conteudo havia varios.
#
# O \b do re nao serve, que trata o '_' como letra: em "_CE_" nao ha
# fronteira nenhuma. Dai a espreitadela por caracteres alfanumericos.
def _sigla(letras):
    return r"(?<![a-z0-9])" + letras + r"(?![a-z0-9])"


RX_PECA_ENCARGOS = re.compile(r"caderno|encargos|" + _sigla("(?:ce|cde)"))
# "cp" fica de fora de proposito: e "Concurso Publico", nao "Programa".
RX_PECA_PROGRAMA = re.compile(r"programa|procedimento|" + _sigla("pp")
                              + "|" + _sigla("pc"))


# Um anexo nao e a peca, e as siglas de duas letras aparecem-lhes no
# nome por acaso: "Anexo.2-PC-Anexo.II-Prop.Preco.xlsx" nao e o Programa
# de Concurso. Nos anexos exige-se a palavra por extenso.
RX_ACESSORIO = re.compile(r"anexo|modelo|formulario|minuta|declaracao")
RX_PECA_ENCARGOS_EXTENSO = re.compile(r"caderno|encargos")
RX_PECA_PROGRAMA_EXTENSO = re.compile(r"programa|procedimento")


def papeis_da_peca(nome):
    """Que peca(s) o ficheiro e. Ha quem junte as duas num so PDF."""
    n = simplifica(nome)
    acessorio = bool(RX_ACESSORIO.search(n))
    encargos = (RX_PECA_ENCARGOS_EXTENSO if acessorio else RX_PECA_ENCARGOS)
    programa = (RX_PECA_PROGRAMA_EXTENSO if acessorio else RX_PECA_PROGRAMA)
    papeis = set()
    if encargos.search(n):
        papeis.add("encargos")
    if programa.search(n):
        papeis.add("programa")
    return papeis


def documentos_com_texto(ref):
    with liga() as c:
        return c.execute(
            "SELECT nome, texto FROM documentos WHERE ref=? AND texto_estado='ok' "
            "AND texto != '' ORDER BY nome", (ref,)).fetchall()


def pecas_para_analise(docs, quais, ancoras, tecto=TECTO_RECORTE):
    """O que interessa, dos documentos que fazem o papel `quais`.

    Recebe os documentos ja lidos: sao tres recortes por concurso e a
    mesma consulta repetida tres vezes trazia da base o texto todo --
    690 mil caracteres, num Caderno de Encargos grande, para produzir 21
    mil.
    """
    partes, usados = [], []
    for d in docs:
        if quais not in papeis_da_peca(d["nome"]):
            continue
        partes.append("### %s\n%s" % (
            d["nome"],
            recorte_relevante(sem_indice(d["texto"]), ancoras, tecto)))
        usados.append(d["nome"])
    return "\n\n".join(partes)[:tecto * 2], usados


def limpa_campo(valor):
    r"""As mudancas de linha, que o modelo devolve escapadas a dobrar.

    Sem isto o "\n" aparece a letra no meio do texto, porque o modelo
    escreveu "\\n" no JSON e o json.loads so desfaz uma camada.
    """
    texto = str(valor or "").replace("\\n", "\n").replace("\\t", " ")
    # Uma linha em branco separa blocos -- a equipa vem em blocos por
    # perfil, e sem isto os 21 do INFARMED saiam numa parede de 126
    # linhas seguidas. Duas ou mais em branco continuam a valer uma, e
    # nas pontas nao fica nenhuma. O CSS da ficha e white-space:pre-line,
    # por isso o que aqui se guardar e o que la se ve.
    fora = []
    for linha in (x.strip() for x in texto.split("\n")):
        if linha or (fora and fora[-1]):
            fora.append(linha)
    while fora and not fora[-1]:
        fora.pop()
    return "\n".join(fora)


# A conta tem dois tectos, e so um deles se ve nos cabecalhos. O de
# tokens por minuto passa sozinho; o do DIA (200 mil) nao passa hoje.
# Esperar e repetir num limite diario e tempo deitado fora: uma
# releitura do acervo levou uma hora a nao fazer nada, porque cada
# pedido gastava dois minutos de espera antes de desistir.
SEM_ORCAMENTO_HOJE = ("o orçamento diário do modelo acabou (200 mil "
                      "tokens); recomeça amanhã ou passa a conta a Dev Tier")


def orcamento_do_dia_esgotado(resposta):
    corpo = simplifica(resposta.text or "")
    return "tokens per day" in corpo or "(tpd)" in corpo


# Quem ja bateu no tecto do dia, e em que dia. O tecto diario nao cede
# antes de amanha: sem esta memoria, cada um dos tres pedidos de cada
# concurso da fila voltava a bater na mesma porta fechada -- que foi
# exactamente a hora deitada fora que o SEM_ORCAMENTO_HOJE veio evitar.
# Vive so enquanto o processo viver; a meia-noite a data muda e limpa-se
# sozinha.
_ESGOTADOS = {}


def hoje_texto():
    return datetime.now().strftime("%Y-%m-%d")


def marcar_esgotado(nome, dia=None):
    _ESGOTADOS[nome] = dia or hoje_texto()


def esta_esgotado(nome, dia=None):
    return _ESGOTADOS.get(nome) == (dia or hoje_texto())


def cadeia_esgotada(cadeia):
    """Todos os fornecedores da cadeia bateram no tecto do dia?

    So entao e que a mensagem do tecto diario e verdade. Com "algum
    esgotado" bastava a Groq acabar para o painel anunciar que o dia
    tinha acabado, com o OpenRouter ainda a responder ao lado.
    """
    return bool(cadeia) and all(esta_esgotado(f[0]) for f in cadeia)


def espera_pedida(resposta, tecto=70):
    """Quantos segundos esperar depois de um 429, segundo a propria API."""
    cabecalho = resposta.headers.get("retry-after", "")
    if cabecalho.replace(".", "", 1).isdigit():
        return min(float(cabecalho) + 1, tecto)
    # sem cabecalho, a mensagem costuma dizer "try again in 12.4s"
    achado = re.search(r"in \s*([\d]+(?:\.[\d]+)?)s", resposta.text or "")
    return min(float(achado.group(1)) + 1, tecto) if achado else 20.0


CAMPOS_DA_ANALISE = ("objecto", "equipa", "documentos_proposta",
                     "preco_anormalmente_baixo", "localizacao")


def juntar_leituras(dados, anterior):
    """Os campos lidos agora, guardando os de antes onde faltarem.

    Sao tres pedidos por concurso: se um apanhar um 429, a chave dele
    nem vem. Sem isto, o INSERT apagava o campo que ja estava bom --
    aconteceu, e a tabela de 20 perfis do INFARMED desapareceu numa
    releitura. Chave ausente e pedido falhado; "nao consta" e resposta
    do modelo, e essa substitui.
    """
    def antes(nome):
        try:
            return (anterior[nome] if anterior else "") or ""
        except (KeyError, IndexError):
            return ""
    return {c: limpa_campo(dados[c]) if c in dados else antes(c)
            for c in CAMPOS_DA_ANALISE}


def juntar_fontes(usados, anteriores, parcial):
    """As peças de onde veio o que fica guardado, e não só as desta vez.

    Companheiro do juntar_leituras: se ele guarda campos lidos numa
    leitura anterior, as fontes dessa leitura têm de ficar com eles.
    Sem isto, uma releitura em que só o Programa respondesse punha
    fontes="Programa.pdf" por cima, e a ficha passava a dizer "objecto
    lido de Programa.pdf" a texto que veio do Caderno de Encargos.
    """
    juntas = list(usados)
    if parcial or not juntas:
        for f in (anteriores or "").split(","):
            f = f.strip()
            if f and f not in juntas:
                juntas.append(f)
    return ", ".join(juntas)


RX_CERCA_ABRE = re.compile(r"^```[a-zA-Z]*\s*")
RX_CERCA_FECHA = re.compile(r"\s*```$")


def json_da_resposta(conteudo):
    """O JSON da resposta, mesmo vindo dentro de cercas markdown.

    A Groq honra o response_format; os modelos gratuitos das outras
    plataformas nem sempre, e devolvem a mesma coisa embrulhada em
    ```json ... ```. Sem isto a cadeia descia para o fornecedor
    seguinte com a resposta boa na mao.
    """
    conteudo = (conteudo or "").strip()
    if conteudo.startswith("```"):
        conteudo = RX_CERCA_FECHA.sub("", RX_CERCA_ABRE.sub("", conteudo))
    return json.loads(conteudo)


def _um_pedido(url, chave, modelo, instrucao, texto, extras=None):
    """Uma pergunta a um fornecedor. Devolve (dados, aviso)."""
    corpo = {"model": modelo, "temperature": 0,
             "response_format": {"type": "json_object"},
             "messages": [{"role": "system", "content": instrucao},
                          {"role": "user", "content": texto}]}
    corpo.update(extras or {})
    try:
        for tentativa in (1, 2, 3):
            r = requests.post(url, timeout=180,
                              headers={"Authorization": "Bearer " + chave,
                                       "Content-Type": "application/json"},
                              json=corpo)
            if r.status_code == 429 and orcamento_do_dia_esgotado(r):
                return None, SEM_ORCAMENTO_HOJE
            if r.status_code != 429 or tentativa == 3:
                break
            # A conta tem um tecto de tokens por minuto, e sao tres
            # perguntas por concurso. Isto corre em fundo, sem ninguem a
            # ver: esperar o minuto vale mais do que desistir.
            time.sleep(espera_pedida(r))
        if r.status_code != 200:
            return None, "respondeu %d: %s" % (r.status_code, r.text[:160])
        return json_da_resposta(r.json()["choices"][0]["message"]["content"]), ""
    except (requests.RequestException, ValueError, KeyError, IndexError) as erro:
        return None, "falhou a leitura pelo modelo: %s" % str(erro)[:140]


def _perguntar(cadeia, instrucao, texto):
    """A mesma pergunta, descendo a cadeia ate alguem responder.

    Devolve (dados, aviso, usado), em que "usado" identifica quem
    respondeu -- vai para a coluna analise.modelo, para se saber depois
    que leitura veio de que modelo. Uma leitura da Groq e uma leitura
    de um modelo gratuito nao valem o mesmo, e a ficha tem de o dizer.
    """
    avisos = []
    for nome, url, modelo, chave, extras in cadeia:
        if esta_esgotado(nome):
            avisos.append("%s: %s" % (nome, SEM_ORCAMENTO_HOJE))
            continue
        dados, aviso = _um_pedido(url, chave, modelo, instrucao, texto, extras)
        if dados is not None:
            return dados, "", "%s:%s" % (nome, modelo)
        if aviso == SEM_ORCAMENTO_HOJE:
            marcar_esgotado(nome)
        avisos.append("%s: %s" % (nome, aviso))
    return None, "; ".join(avisos), ""


def analisar_pecas(ref):
    """Le as pecas com o modelo e guarda os quatro campos. (ok, aviso)."""
    cadeia = cadeia_de_fornecedores()
    if not cadeia:
        return False, ("falta a chave da API: põe-na em chave_api.txt, "
                       "na pasta do radar")

    docs = documentos_com_texto(ref)
    recortes = [(nome, pecas_para_analise(docs, quais, ancoras), instrucao)
                for nome, quais, ancoras, instrucao in LEITURAS]
    if not any(texto for _, (texto, _), _ in recortes):
        # As pecas trazidas antes de haver extracao de texto ficaram sem
        # ele. Estao em disco: extrai-se agora, sem voltar a rede.
        extrair_textos(ref)
        docs = documentos_com_texto(ref)
        recortes = [(nome, pecas_para_analise(docs, quais, ancoras), instrucao)
                    for nome, quais, ancoras, instrucao in LEITURAS]
    if not any(texto for _, (texto, _), _ in recortes):
        with liga() as c:
            scans = c.execute("SELECT COUNT(*) n FROM documentos WHERE ref=? "
                              "AND texto_estado='scan'", (ref,)).fetchone()["n"]
        return False, ("os documentos deste concurso são digitalizações, sem "
                       "texto para ler" if scans else
                       "ainda não há Caderno de Encargos nem Programa em disco")

    dados, usados, falhas, modelos = {}, [], [], []
    for nome, (texto, fontes), instrucao in recortes:
        if not texto:
            falhas.append("%s: falta o documento" % nome)
            continue
        resposta, aviso, usado = _perguntar(cadeia, instrucao, texto)
        if resposta is None:
            falhas.append("%s: %s" % (nome, aviso))
            continue
        dados.update(resposta)
        usados += [f for f in fontes if f not in usados]
        if usado not in modelos:
            modelos.append(usado)
    # O tecto do dia nao cede antes de amanha: nao ha mais nada util a
    # dizer, e a mensagem vai inteira para quem a procura no --ler-pecas.
    # Espremida no meio das outras falhas, o corte apagava-a e a fila
    # continuava a moer contra um limite que nao ia ceder. O que se leu
    # antes de o tecto bater guarda-se na mesma -- sair aqui deitava
    # fora dois campos bons, nao marcava erro nenhum (o obter_documentos
    # so o faz quando isto devolve False) e ainda dizia "pecas lidas
    # pelo modelo" a quem carregou no botao.
    # So se conta como "acabou o dia" quando a cadeia inteira bateu no
    # tecto: com um "algum" bastava a Groq acabar para o painel dar o
    # dia por perdido, com o fornecedor seguinte ainda a responder.
    sem_orcamento = cadeia_esgotada(cadeia)
    if not dados:
        return False, (SEM_ORCAMENTO_HOJE if sem_orcamento
                       else "; ".join(falhas)[:200])

    anterior = analise_de(ref)
    campos = juntar_leituras(dados, anterior)
    fontes = juntar_fontes(usados, anterior["fontes"] if anterior else "",
                           bool(falhas))
    # Mesmo problema das fontes, e a mesma solucao: agora que esta coluna
    # diz quem respondeu, uma releitura em que so um fornecedor entrasse
    # apagava o registo do modelo que leu os outros campos -- e os campos
    # ficavam (juntar_leituras guarda-os) a dizer que vinham de quem nao
    # os leu.
    modelos = juntar_fontes(modelos, anterior["modelo"] if anterior else "",
                            bool(falhas))

    with liga() as c:
        c.execute("""INSERT OR REPLACE INTO analise
            (ref,objecto,equipa,documentos_proposta,preco_anormalmente_baixo,
             localizacao,modelo,fontes,quando) VALUES (?,?,?,?,?,?,?,?,?)""",
                  (ref, campos["objecto"], campos["equipa"],
                   campos["documentos_proposta"],
                   campos["preco_anormalmente_baixo"],
                   campos["localizacao"], modelos, fontes,
                   datetime.now().strftime("%Y-%m-%d %H:%M")))
    if sem_orcamento:
        return True, SEM_ORCAMENTO_HOJE
    # Leitura parcial e melhor do que nenhuma, mas tem de se saber.
    return True, ("não deu para ler tudo — " + "; ".join(falhas)[:160]
                  if falhas else "")


def analise_de(ref):
    with liga() as c:
        return c.execute("SELECT * FROM analise WHERE ref=?", (ref,)).fetchone()


def _nome_da_resposta(r):
    """O nome do ficheiro que o servidor anuncia, se anunciar algum."""
    disp = r.headers.get("Content-Disposition") or ""
    m = re.search(r"filename\*=UTF-8''([^;]+)", disp)
    if m:
        return unquote(m.group(1).replace("+", " "))
    m = re.search(r'filename="?([^";]+)"?', disp)
    return m.group(1).strip() if m else ""


def obter_documentos(ref):
    """Traz as pecas do procedimento para disco. Devolve (quantos, aviso)."""
    with liga() as c:
        a = c.execute("SELECT ref,plataforma,link_pecas,pdf_url FROM anuncios "
                      "WHERE ref=?", (ref,)).fetchone()
    if not a:
        return 0, "anúncio desconhecido"

    sessao = requests.Session()
    sessao.headers.update({"User-Agent": NAVEGADOR,
                           "Accept": "application/json, text/plain, */*"})
    ficheiros, aviso = [], ""

    # O PDF oficial do anuncio existe sempre e nao depende de plataforma.
    if a["pdf_url"]:
        try:
            r = sessao.get(a["pdf_url"], timeout=120)
            if r.status_code == 200 and r.content.startswith(b"%PDF"):
                ficheiros.append(("Anúncio DR.pdf", r.content))
        except requests.RequestException:
            pass

    link = a["link_pecas"] or ""
    plataforma = a["plataforma"] or ""
    grandes = []
    try:
        if link and "acingov" in link:
            novos, grandes = _pecas_acingov(sessao, link)
        elif link and "vortal" in link:
            novos, grandes = _pecas_vortal(sessao, link)
        elif link and ASSINATURA_JSF in link.lower():
            novos, grandes = _pecas_jsf(sessao, link)
        elif link:
            novos = []
            aviso = ("não sei trazer as peças da plataforma %s; usa o botão "
                     "que a abre" % (plataforma or "indicada"))
        else:
            novos = []
            aviso = "o anúncio não indica link para as peças"
        ficheiros += novos
    except (requests.RequestException, ValueError, zipfile.BadZipFile) as erro:
        aviso = "falhou a ir buscar as peças: %s" % str(erro)[:120]

    if grandes:
        # Dizer quais ficaram de fora: sao normalmente os anexos tecnicos,
        # e o utilizador tem de saber que existem para os ir buscar a mao.
        aviso = ("%d ficheiro(s) acima de %d MB não foram trazidos (%s); "
                 "vai buscá-los pelo botão que abre a plataforma"
                 % (len(grandes), MAX_FICHEIRO // (1024 * 1024),
                    ", ".join(n[:40] for n in grandes[:3])))

    if not ficheiros:
        with liga() as c:
            c.execute("UPDATE anuncios SET docs_estado=? WHERE ref=?",
                      ("falhou", ref))
        return 0, aviso or "não veio nenhum documento"

    pasta = pasta_do_anuncio(ref)
    os.makedirs(pasta, exist_ok=True)
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    guardados = 0
    with liga() as c:
        c.execute("DELETE FROM documentos WHERE ref=?", (ref,))
        vistos = set()
        for nome, dados in ficheiros:
            if nome in vistos:
                continue
            vistos.add(nome)
            with open(os.path.join(pasta, nome), "wb") as f:
                f.write(dados)
            c.execute("""INSERT INTO documentos
                (ref,nome,ficheiro,tamanho,origem,obtido_em) VALUES (?,?,?,?,?,?)""",
                      (ref, nome, nome, len(dados), plataforma or "dr", agora))
            guardados += 1
    extrair_textos(ref)
    # A leitura pelo modelo faz parte de trazer as pecas. Fica antes de
    # se marcar o estado para a ficha so deixar de dizer "a trazer as
    # peças" quando ja ca esta tudo, incluindo o objecto e a equipa --
    # doutro modo a pagina recarregava a meio e mostrava a tabela por
    # preencher. Sao segundos, ao lado de uma descarga que demora muito
    # mais; e se falhar, as pecas ficam na mesma e ha o botao a mao.
    if cadeia_de_fornecedores() and not analise_de(ref):
        lido, porque = analisar_pecas(ref)
        if not lido:
            marca("analise_ultimo_erro", "%s: %s" % (ref, porque))
    # "parcial" quando veio alguma coisa mas as pecas falharam: o PDF
    # do anuncio vem sempre, e sozinho dava um "ok" que escondia o
    # facto de o Caderno de Encargos nao ter chegado.
    with liga() as c:
        c.execute("UPDATE anuncios SET docs_estado=? WHERE ref=?",
                  ("parcial" if aviso else "ok", ref))
    return guardados, aviso


# Fila de descargas em fundo. Um unico trabalhador, para nao abrir vinte
# ligacoes as plataformas quando se tria depressa; e o erro fica gravado
# em vez de morrer dentro da thread sem ninguem dar por ele.
_FILA_DOCS = queue.Queue()
_TRABALHADOR = None
_TRABALHADOR_LOCK = threading.Lock()


def _servir_fila():
    while True:
        ref = _FILA_DOCS.get()
        try:
            n, aviso = obter_documentos(ref)
            if not n:
                marca("docs_ultimo_erro", "%s: %s" % (ref, aviso or "sem documentos"))
        except Exception as erro:
            # Tem de ficar num estado terminal: se ficasse "pendente", a
            # ficha esperava para sempre por peças que nunca vinham.
            try:
                with liga() as c:
                    c.execute("UPDATE anuncios SET docs_estado='falhou' WHERE ref=?",
                              (ref,))
                marca("docs_ultimo_erro", "%s: %s" % (ref, str(erro)[:200]))
            except Exception:
                pass
        finally:
            _FILA_DOCS.task_done()


def pedir_documentos(ref):
    """Poe o anuncio na fila e garante que ha quem a sirva."""
    with liga() as c:
        c.execute("UPDATE anuncios SET docs_estado='pendente' WHERE ref=?", (ref,))
    global _TRABALHADOR
    with _TRABALHADOR_LOCK:
        if _TRABALHADOR is None or not _TRABALHADOR.is_alive():
            _TRABALHADOR = threading.Thread(target=_servir_fila, daemon=True)
            _TRABALHADOR.start()
    _FILA_DOCS.put(ref)


def guardar_amostra(nome, conteudo):
    os.makedirs(AMOSTRAS, exist_ok=True)
    with open(os.path.join(AMOSTRAS, nome), "w", encoding="utf-8") as f:
        f.write(conteudo)


def guardar(colhidos, cfg=None):
    """Entra tudo. A triagem e feita por ti, no painel."""
    novos = 0
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    with liga() as c:
        for a in colhidos:
            # OR IGNORE em vez de perguntar primeiro: duas recolhas a
            # correrem ao mesmo tempo (o relogio e o botao) passavam ambas
            # pela verificacao e a segunda rebentava na chave primaria.
            cur = c.execute("""INSERT OR IGNORE INTO anuncios
                (ref,titulo,entidade,data_pub,tipo,url,estado,visto_em)
                VALUES (?,?,?,?,?,?,'novo',?)""",
                            (a["ref"], a["titulo"], a["entidade"], a["data_pub"],
                             a.get("tipo", ""), a["url"], agora))
            novos += cur.rowcount
    return novos


# As tarefas que o agendar.bat cria. Se nao existirem, o radar so
# recolhe com o painel aberto -- e como o relogio interno recupera os
# slots falhados, a tabela `slots` fica preenchida e parece que correu a
# horas. Foi assim que isto passou semanas sem se notar.
TAREFAS = ("Radar DR 09h", "Radar DR 17h")
_TAREFAS_VISTAS = None


def tarefas_em_falta():
    """Quais das tarefas do Windows nao estao criadas.

    A resposta guarda-se: e um subprocesso, e o painel monta paginas
    muitas vezes. Fora do Windows devolve vazio -- nao ha o que avisar.
    """
    global _TAREFAS_VISTAS
    if _TAREFAS_VISTAS is not None:
        return _TAREFAS_VISTAS
    if os.name != "nt":
        _TAREFAS_VISTAS = []
        return _TAREFAS_VISTAS
    try:
        r = subprocess.run(["schtasks", "/query", "/fo", "csv", "/nh"],
                           capture_output=True, text=True, timeout=20,
                           encoding="utf-8", errors="replace")
        havidas = r.stdout or ""
    except (OSError, subprocess.SubprocessError):
        _TAREFAS_VISTAS = []            # nao se sabe: nao se inventa aviso
        return _TAREFAS_VISTAS
    _TAREFAS_VISTAS = [t for t in TAREFAS if t not in havidas]
    return _TAREFAS_VISTAS


COPIAS = os.path.join(BASE_DIR, "copias")


def copia_de_seguranca(guardar=7):
    """Copia o radar.db, e deita fora as mais velhas.

    So o radar.db: o contratos.db refaz-se com `--contratos` e a pasta
    documentos/ volta a descarregar-se, mas a **triagem, as fases do
    quadro, os responsaveis e o historico nao se recuperam de lado
    nenhum** -- nao estao no git, por serem uma base, e nao havia copia
    nenhuma.

    `VACUUM INTO` e nao copiar o ficheiro: o SQLite fa-lo a quente, com
    a base aberta e em WAL, e o que sai e uma base consistente e ja
    compactada. Copiar o .db com o .wal ao lado dava uma copia
    truncada.
    """
    os.makedirs(COPIAS, exist_ok=True)
    # Uma por dia, e o nome e a data: a segunda verificacao do dia
    # encontra o ficheiro feito e nao faz nada. Medido, o VACUUM INTO de
    # 44 MB leva 37 s -- a cada verificacao era tempo a mais, e duas
    # copias do mesmo dia nao valem o dobro.
    destino = os.path.join(
        COPIAS, "radar-%s.db" % datetime.now().strftime("%Y-%m-%d"))
    if os.path.exists(destino):
        return destino
    with liga() as c:
        c.execute("VACUUM INTO ?", (destino,))
    velhas = sorted(f for f in os.listdir(COPIAS)
                    if re.fullmatch(r"radar-[\d-]+\.db", f))
    for f in velhas[:-guardar] if guardar else []:
        try:
            os.remove(os.path.join(COPIAS, f))
        except OSError:
            pass                        # o OneDrive as vezes segura o ficheiro
    return destino


# Marca posta no que ja estava na base quando o alerta foi ligado: nao
# foi avisado, mas tambem nao e novidade -- senao o primeiro resumo
# trazia o acervo todo.
ACERVO = "acervo"


def filtros_de_alerta():
    with liga() as c:
        return c.execute(
            "SELECT id, nome, consulta FROM filtros_guardados "
            "WHERE vista='anuncios' AND alerta=1 "
            "ORDER BY nome COLLATE NOCASE").fetchall()


def registar_alertas():
    """Anota que anuncios caem em que alerta, sem os enviar.

    Separa-se de proposito o **reconhecer** do **enviar**: a verificacao
    corre duas vezes por dia e o resumo sai uma; e a tabela guarda o que
    ja foi visto, por isso um anuncio nunca e avisado duas vezes, nem que
    a verificacao corra dez vezes.

    Corre depois de `ler_detalhes()`: um alerta por CPV so apanha o
    anuncio depois do CPV estar lido.
    """
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    novos = 0
    for f in filtros_de_alerta():
        args = dict(parse_qsl(f["consulta"] or "", keep_blank_values=True))
        # o estado nao entra: procuram-se anuncios que correspondem, e a
        # triagem deles e outra conversa
        args.pop("estado", None)
        onde, valores = condicoes(dict(args, estado=""))
        with liga() as c:
            # Sem LIMIT: com um tecto, cada volta descobria "novos" que
            # eram so os seguintes da fila -- 200 na primeira, 153 na
            # segunda, e assim ate ao fim do acervo. A clausula de
            # exclusao ja limita isto sozinha depois da primeira volta.
            refs = [r["ref"] for r in c.execute(
                "SELECT ref FROM anuncios" + onde +
                " AND ref NOT IN (SELECT ref FROM alertas_vistos WHERE filtro_id=?)"
                " ORDER BY data_pub DESC, ref DESC",
                valores + [f["id"]])]
            c.executemany(
                "INSERT OR IGNORE INTO alertas_vistos "
                "(filtro_id, ref, visto_em) VALUES (?,?,?)",
                [(f["id"], r, agora) for r in refs])
        novos += len(refs)
    return novos


def alertas_por_enviar():
    """[(filtro, [anuncios])] do que esta reconhecido e ainda nao saiu."""
    fora = []
    with liga() as c:
        for f in filtros_de_alerta():
            linhas = c.execute(
                "SELECT a.ref, a.titulo, a.entidade, a.data_pub, a.prazo, "
                "a.preco_base, a.cpv FROM alertas_vistos v "
                "JOIN anuncios a ON a.ref = v.ref "
                "WHERE v.filtro_id=? AND v.enviado_em IS NULL "
                "ORDER BY a.prazo != '' DESC, a.prazo, a.data_pub DESC",
                (f["id"],)).fetchall()
            if linhas:
                fora.append((f, linhas))
    return fora


def marcar_alertas_enviados(achados):
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    with liga() as c:
        for f, linhas in achados:
            c.executemany(
                "UPDATE alertas_vistos SET enviado_em=? "
                "WHERE filtro_id=? AND ref=?",
                [(agora, f["id"], a["ref"]) for a in linhas])


def texto_do_resumo(achados):
    """O resumo em texto simples, que serve de corpo do e-mail e de
    AVISOS.txt. Um so formato: dois divergiam ao primeiro arranjo."""
    total = sum(len(x[1]) for x in achados)
    linhas = ["Radar de Concursos -- %d anuncio%s novo%s nos teus alertas"
              % (total, "" if total == 1 else "s", "" if total == 1 else "s"),
              datetime.now().strftime("%d/%m/%Y %H:%M"), ""]
    for f, anuncios in achados:
        linhas.append("== %s (%d)" % (f["nome"], len(anuncios)))
        linhas.append("")
        for a in anuncios:
            dias, passou = dias_restantes(a["prazo"])
            if dias is None:
                prazo = "sem prazo lido"
            elif passou:
                # conta_dias() diz "termina hoje" para dias <= 0, o que
                # num prazo de ha dois meses e mentira
                prazo = "PRAZO EXPIRADO em %s" % data_pt(a["prazo"])
            else:
                prazo = "propostas ate %s (%s)" % (data_pt(a["prazo"]),
                                                   conta_dias(dias))
            linhas.append("  %s" % (a["titulo"] or "(sem titulo)")[:88])
            linhas.append("    %s" % (a["entidade"] or "")[:80])
            linhas.append("    %s | %s | %s"
                          % (a["ref"], prazo, a["preco_base"] or "sem preco base"))
            linhas.append("    http://localhost:%d/anuncio/%s"
                          % (PORTA, quote(a["ref"], safe="")))
            linhas.append("")
    return "\n".join(linhas)


def enviar_email(assunto, corpo, cfg=None):
    """Manda o resumo. Devolve (correu bem, o que dizer ao utilizador).

    A palavra-passe le-se de `email_senha.txt` ou da variavel
    RADAR_EMAIL_SENHA -- nunca fica na configuracao, que e um ficheiro
    que se abre sem pensar. O `.gitignore` ja cobre o nome.
    """
    cfg = cfg or ler_config()
    e = cfg.get("email") or {}
    para = (e.get("para") or "").strip()
    de = (e.get("de") or "").strip()
    servidor = (e.get("servidor") or "").strip()
    if not (para and de and servidor):
        return False, "e-mail por configurar"
    senha = ler_chave(("email_senha.txt",), "RADAR_EMAIL_SENHA")
    if not senha:
        return False, "falta a palavra-passe em email_senha.txt"

    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = de
    msg["To"] = para
    msg.set_content(corpo)
    porta = int(e.get("porta") or 587)
    try:
        if porta == 465:
            ligacao = smtplib.SMTP_SSL(servidor, porta, timeout=30)
        else:
            ligacao = smtplib.SMTP(servidor, porta, timeout=30)
        with ligacao as smtp:
            if porta != 465:
                smtp.starttls()
            smtp.login(de, senha)
            smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        return False, ("o servidor recusou a palavra-passe. No Gmail tem de "
                       "ser uma palavra-passe de aplicação, não a da conta")
    except (smtplib.SMTPException, OSError) as erro:
        return False, "%s: %s" % (type(erro).__name__, str(erro)[:120])
    return True, "enviado para %s" % para


def enviar_resumo(cfg=None, forcar=False):
    """O resumo diario. Um por dia: a verificacao corre duas vezes e o
    resumo sai uma, senao eram dois e-mails com metade das coisas."""
    cfg = cfg or ler_config()
    hoje = datetime.now().strftime("%Y-%m-%d")
    if not forcar and le_marca("ultimo_resumo", "") == hoje:
        return False, "o resumo de hoje já saiu"
    achados = alertas_por_enviar()
    if not achados:
        return False, "nada de novo para avisar"

    corpo = texto_do_resumo(achados)
    with open(AVISOS, "w", encoding="utf-8") as f:
        f.write(corpo)                  # fica sempre, mesmo sem e-mail

    total = sum(len(x[1]) for x in achados)
    bem, porque = enviar_email(
        "Radar: %d anúncio%s nos teus alertas" % (total, "" if total == 1 else "s"),
        corpo, cfg)

    # Sem e-mail configurado, **o ficheiro e a entrega** -- da-se por
    # avisado e o estado avanca. Se ficassem pendentes, o painel dizia
    # "153 por avisar" para sempre e o mesmo resumo era reescrito a cada
    # volta. Uma falha a serio (palavra-passe recusada, rede em baixo) e
    # outra coisa: essa nao marca, para voltar a tentar.
    sem_canal = porque in ("e-mail por configurar",
                           "falta a palavra-passe em email_senha.txt")
    entregue = bem or sem_canal
    if entregue:
        marcar_alertas_enviados(achados)
        marca("ultimo_resumo", hoje)
    marca("ultimo_resumo_estado",
          porque if bem else
          ("só no AVISOS.txt (%s)" % porque) if sem_canal else
          "por enviar (%s)" % porque)
    marca("ultimo_resumo_quantos", str(total))
    return entregue, porque


AVISOS = os.path.join(BASE_DIR, "AVISOS.txt")


def verificar(cfg=None):
    cfg = cfg or ler_config()
    iniciar_db()
    # Antes de mexer na base, nao depois: se a recolha a deixar num
    # estado mau, a copia e de antes disso.
    if cfg.get("copia_de_seguranca", True):
        try:
            copia_de_seguranca(int(cfg.get("copias_a_guardar", 7)))
        except (sqlite3.Error, OSError) as erro:
            print("aviso: copia de seguranca falhou (%s)" % erro)
    bem, mensagem, novos = recolher(cfg)
    if bem:
        feitos, aviso = ler_detalhes(int(cfg.get("detalhes_por_volta", 40)),
                                     dias=int(cfg.get("detalhe_dias", 60)) or None)
        if aviso:
            bem = False
            mensagem += " (%s)" % aviso
    # Os avisos correm depois de ler os detalhes: um filtro por CPV so
    # apanha o anuncio depois de o CPV estar lido, e ler os detalhes e a
    # ultima coisa que a verificacao faz.
    quantos_avisos = 0
    if bem and cfg.get("alertas", True):
        try:
            quantos_avisos = registar_alertas()
            # O resumo sai uma vez por dia, a partir da hora marcada: a
            # verificacao corre duas vezes e nao se mandam dois e-mails
            # com metade das coisas cada.
            hora = str((cfg.get("email") or {}).get("hora_resumo") or "17:00")
            if datetime.now().strftime("%H:%M") >= hora:
                enviar_resumo(cfg)
        except (sqlite3.Error, OSError) as erro:
            print("aviso: os alertas falharam (%s)" % erro)
    if quantos_avisos:
        mensagem += " &middot; %d para os alertas" % quantos_avisos

    marca("ultima_verificacao", datetime.now().strftime("%Y-%m-%d %H:%M"))
    marca("ultima_mensagem", mensagem)
    marca("ultima_ok", "1" if bem else "0")
    if novos and cfg.get("abrir_browser_ao_encontrar"):
        try:
            webbrowser.open("http://localhost:%d/" % PORTA)
        except Exception:
            pass
    return mensagem, novos


# ------------------------------------------ contratos celebrados (BASE)
#
# Corpus historico para inteligencia de mercado: quem ganhou o que, por
# quanto, de que entidade. Nao sao oportunidades -- sao contratos ja
# assinados -- e por isso nao entram na tabela `anuncios` nem no funil.
#
# Vive num ficheiro proprio, pelo mesmo motivo que as pecas vivem em
# `documentos/`: o radar.db e para o trabalho do dia e tem de continuar
# pequeno. Um ano de contratos sao ~160 mil linhas; o acervo desde 2012
# passa o milhao, e nao tem nada que fazer ao lado de 5 mil anuncios.
# Para cruzar os dois faz-se ATTACH (ver `com_corpus()`).
#
# A fonte e o dump semanal do IMPIC no dados.gov, dominio publico, sem
# token nem sessao. Nao e o conjunto "OCDS" do mesmo portal: esse esta
# vazio e parado desde Outubro de 2022 -- ver o ESTADO.md.

CORPUS = os.path.join(BASE_DIR, "contratos.db")

# O identificador do conjunto no dados.gov. Diz "2025" e ja vai em 2026:
# o nome ficou congelado quando o conjunto foi criado, e e por ele que a
# API responde. Nao o "corrijas".
CONJUNTO_CONTRATOS = ("contratos-publicos-portal-base-impic-"
                      "contratos-de-2012-a-2025")
API_DADOS_GOV = "https://dados.gov.pt/api/1/datasets/%s/"


def liga_corpus():
    c = sqlite3.connect(CORPUS, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=30000")
    return c


def iniciar_corpus():
    """Migracoes idempotentes, como o iniciar_db(): corre sempre."""
    with liga_corpus() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS contratos (
            id INTEGER PRIMARY KEY, ano INTEGER, n_anuncio TEXT,
            tipo_procedimento TEXT, objecto TEXT,
            adjudicante_nif TEXT, adjudicante TEXT, adjudicante_norm TEXT,
            data_publicacao TEXT, data_celebracao TEXT,
            preco_contratual REAL, preco_base REAL,
            prazo_execucao INTEGER, local_execucao TEXT,
            cpv TEXT, fundamentacao TEXT)""")
        # Um contrato pode ter varios adjudicatarios (agrupamentos) e
        # varios CPV. Em tabelas proprias, para se poder perguntar "quem
        # ganhou nesta divisao de CPV" com indice em vez de LIKE.
        c.execute("""CREATE TABLE IF NOT EXISTS contrato_adjudicatario (
            contrato_id INTEGER, nif TEXT, nome TEXT, nome_norm TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS contrato_cpv (
            contrato_id INTEGER, cpv8 TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS corpus_estado (
            chave TEXT PRIMARY KEY, valor TEXT)""")
        # Quantos adjudicatarios tem o contrato, gravado em vez de contado.
        # Um contrato ganho por um agrupamento reparte-se por eles no
        # grafico de quem ganha, senao um contrato de tres inflacionava o
        # mercado tres vezes -- e ha um com 35. Contar isso por subconsulta
        # a cada linha levava 2,1 s no corpus todo; em coluna e imediato.
        cols = [r["name"] for r in c.execute("PRAGMA table_info(contratos)")]
        if "n_adj" not in cols:
            c.execute("ALTER TABLE contratos ADD COLUMN n_adj INTEGER")
        c.execute("""UPDATE contratos SET n_adj =
                     MAX(1, (SELECT COUNT(*) FROM contrato_adjudicatario a
                             WHERE a.contrato_id = contratos.id))
                     WHERE n_adj IS NULL""")
        # A chave da entidade: o NIF quando existe. Ver chave_entidade().
        if "adjudicante_chave" not in cols:
            c.execute("ALTER TABLE contratos ADD COLUMN adjudicante_chave TEXT")
        cols_a = [r["name"] for r in
                  c.execute("PRAGMA table_info(contrato_adjudicatario)")]
        if "chave" not in cols_a:
            c.execute("ALTER TABLE contrato_adjudicatario ADD COLUMN chave TEXT")
        # Nome canonico por entidade: o mais usado. Medido, e o unico
        # criterio que da o nome certo -- o mais curto dava "Servicos
        # Centrais" para o IEFP e "CP" para os comboios.
        c.execute("""CREATE TABLE IF NOT EXISTS entidades (
            chave TEXT PRIMARY KEY, nif TEXT, nome TEXT, variantes INTEGER)""")
        # Todos os nomes por que uma entidade ja apareceu, normalizados.
        # E por aqui que o nome que o DR escreve num anuncio chega a
        # entidade do corpus -- a `entidades` so tem o nome canonico, e
        # o DR pode ter escrito uma das outras 86.
        c.execute("""CREATE TABLE IF NOT EXISTS entidade_nomes (
            nome_norm TEXT PRIMARY KEY, chave TEXT)""")
        for ddl in (
            "CREATE INDEX IF NOT EXISTS ix_ctr_nif ON contratos(adjudicante_nif)",
            "CREATE INDEX IF NOT EXISTS ix_ctr_norm ON contratos(adjudicante_norm)",
            "CREATE INDEX IF NOT EXISTS ix_ctr_anuncio ON contratos(n_anuncio)",
            "CREATE INDEX IF NOT EXISTS ix_ctr_ano ON contratos(ano)",
            # A lista ordena por data de celebracao. Sem indice, mostrar
            # as primeiras 20 de 1,36 milhoes obrigava a ordenar tudo:
            # 6 segundos so nesta consulta. O `id` vai junto porque e o
            # desempate, e assim o indice serve a ordenacao inteira.
            "CREATE INDEX IF NOT EXISTS ix_ctr_data "
            "ON contratos(data_celebracao, id)",
            # O <select> dos procedimentos conta-os a cada visita; com
            # indice e uma passagem pelo indice e nao pela tabela.
            "CREATE INDEX IF NOT EXISTS ix_ctr_proc "
            "ON contratos(tipo_procedimento)",
            "CREATE INDEX IF NOT EXISTS ix_cpv_v ON contrato_cpv(cpv8)",
            "CREATE INDEX IF NOT EXISTS ix_adj_nif ON contrato_adjudicatario(nif)",
        ):
            c.execute(ddl)
        # Os indices unicos das tabelas filhas nao sao so para procurar:
        # sao o que impede duplicados. Ha contratos que aparecem no
        # ficheiro de dois anos (e ate duas vezes no mesmo); o pai era
        # substituido pela chave primaria e os filhos acumulavam --
        # medido, 917 CPV e 971 adjudicatarios a dobrar em dois anos.
        # Com o indice, o INSERT OR IGNORE trata disso sozinho.
        for nome, ddl, limpeza in (
            ("ux_cpv",
             "CREATE UNIQUE INDEX ux_cpv ON contrato_cpv(contrato_id, cpv8)",
             "DELETE FROM contrato_cpv WHERE rowid NOT IN "
             "(SELECT MIN(rowid) FROM contrato_cpv GROUP BY contrato_id, cpv8)"),
            ("ux_adj",
             "CREATE UNIQUE INDEX ux_adj ON "
             "contrato_adjudicatario(contrato_id, nif, nome)",
             "DELETE FROM contrato_adjudicatario WHERE rowid NOT IN "
             "(SELECT MIN(rowid) FROM contrato_adjudicatario "
             " GROUP BY contrato_id, nif, nome)"),
        ):
            ja = c.execute("SELECT 1 FROM sqlite_master WHERE type='index' "
                           "AND name=?", (nome,)).fetchone()
            if not ja:
                c.execute(limpeza)     # so a primeira vez, nao a cada arranque
                c.execute(ddl)
        for ddl in (
            "CREATE INDEX IF NOT EXISTS ix_ctr_chave "
            "ON contratos(adjudicante_chave)",
            "CREATE INDEX IF NOT EXISTS ix_adj_chave "
            "ON contrato_adjudicatario(chave)",
        ):
            c.execute(ddl)
        # Corpus que veio de antes das chaves: enche-se o que falta e
        # resolvem-se os nomes. Idempotente -- so corre quando ha buracos.
        falta = c.execute("SELECT 1 FROM contratos "
                          "WHERE adjudicante_chave IS NULL LIMIT 1").fetchone()
        vazia = not c.execute("SELECT 1 FROM entidades LIMIT 1").fetchone()
        tem = c.execute("SELECT 1 FROM contratos LIMIT 1").fetchone()
        if falta or (vazia and tem):
            _preencher_chaves(c)
            resolver_entidades(c)


def norma_entidade(nome):
    """Nome de entidade reduzido ao que da para comparar entre fontes.

    O radar guarda o nome como o DR o escreve; o BASE guarda "NIF - nome".
    Medido sobre 898 entidades do radar contra o corpus de dois anos:
    93,7% acham-se assim, sem uma unica ambiguidade. Tirar tambem os
    sufixos de forma juridica (EPE, SA, IP) e trocar "Camara Municipal"
    por "Municipio" so acrescentava dois casos em 898 -- e arriscava
    juntar entidades diferentes. Nao vale a pena: fica so o basico.
    """
    s = unicodedata.normalize("NFKD", nome or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().replace("&", " e ")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def _nif_e_nome(valor):
    """O BASE escreve as partes como ['123456789 - Nome'], por vezes so
    o nome. Devolve (nif, nome) com o que houver.

    Quando o NIF nao e publico -- pessoas singulares -- o BASE escreve
    um traco no lugar dele ("- - Filomena Ferreira"). Sem tirar esse
    traco, o nome ficava com o "- - " colado e aparecia assim no painel.
    """
    if isinstance(valor, list):
        valor = valor[0] if valor else ""
    valor = valor or ""
    m = re.match(r"\s*(\d{9})\s*-\s*(.*)$", valor)
    if m:
        return m.group(1), m.group(2).strip()
    return "", re.sub(r"^\s*-\s*-\s*", "", valor).strip()


def chave_entidade(nif, nome):
    """A identidade de uma entidade, para agrupar.

    O NIF quando existe, o nome normalizado quando nao. **O nome nao e a
    identidade**: medido, a Universidade do Porto aparece com 84 nomes
    (faculdades e servicos) e a MEO com 81, todos com o mesmo NIF.
    Agrupar por nome partia uma entidade em dezenas.

    Sem NIF ficam as pessoas singulares, que o BASE nao identifica: 11%
    das linhas de adjudicatario, 5% do valor. Essas agrupam-se pelo nome,
    que e o que ha -- dai o prefixo, para nunca colidirem com um NIF.
    """
    nif = (nif or "").strip()
    return nif if re.fullmatch(r"\d{9}", nif) else "n:" + norma_entidade(nome)


def _partes(valor):
    """A mesma coisa, para os campos que sao mesmo uma lista."""
    if not isinstance(valor, list):
        valor = [valor] if valor else []
    return [_nif_e_nome(v) for v in valor if v]


def _data_iso(valor):
    """O BASE escreve DD/MM/AAAA. Guarda-se ISO, para ordenar como texto."""
    try:
        return datetime.strptime((valor or "").strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return ""


def _cpv8(valor):
    """['72210000-0 - Servicos de ...'] -> ['72210000']."""
    fora = []
    for v in (valor if isinstance(valor, list) else [valor]):
        m = re.match(r"\s*(\d{8})", v or "")
        if m:
            fora.append(m.group(1))
    return fora


def objectos_do_array(texto):
    """Ceia um array JSON objecto a objecto.

    Um ano de contratos sao 268 MB de JSON; um `json.loads` disso
    constroi a lista toda em memoria de uma vez. Assim so fica o texto
    mais o objecto da vez.
    """
    dec = json.JSONDecoder()
    i, n = texto.index("[") + 1, len(texto)
    while True:
        while i < n and texto[i] in " \t\r\n,":
            i += 1
        if i >= n or texto[i] == "]":
            return
        obj, i = dec.raw_decode(texto, i)
        yield obj


def recursos_contratos():
    """{ano: endereco} dos zips anuais.

    O endereco traz a data da actualizacao no meio do caminho e muda
    todas as semanas. Resolve-se sempre pela API do dados.gov e nunca se
    guarda -- um endereco guardado deixa de servir na semana seguinte.
    """
    r = requests.get(API_DADOS_GOV % CONJUNTO_CONTRATOS, timeout=60)
    r.raise_for_status()
    fora = {}
    for rec in r.json().get("resources", []):
        m = re.match(r"contratos(\d{4})\.zip$", (rec.get("title") or "").strip(),
                     re.I)
        if m:
            fora[int(m.group(1))] = rec["url"]
    return fora


def anos_pedidos(pedido, hoje=None):
    """Le os anos da linha de comando: nada, "2024", "2019-2026", varios.

    Sem nada, o ano corrente e o anterior -- em Janeiro o ano corrente
    ainda quase nao tem contratos, e um corpus so com ele nao servia
    para nada.
    """
    ano_hoje = (hoje or datetime.now()).year
    anos = set()
    for p in pedido:
        m = re.fullmatch(r"(\d{4})\s*-\s*(\d{4})", p.strip())
        if m:
            anos.update(range(int(m.group(1)), int(m.group(2)) + 1))
        elif re.fullmatch(r"\d{4}", p.strip()):
            anos.add(int(p.strip()))
    return sorted(anos) or [ano_hoje - 1, ano_hoje]


def importar_contratos(anos, avisar=print):
    """Traz os anos pedidos do dados.gov e enche o corpus.

    Reimportar um ano substitui-o: apaga-se o ano inteiro antes de
    inserir, para uma segunda passagem nao duplicar. E o que torna isto
    seguro de correr todas as semanas.
    """
    iniciar_corpus()
    disponiveis = recursos_contratos()
    faltam = [a for a in anos if a not in disponiveis]
    if faltam:
        avisar("sem dados para: %s (ha %s)"
               % (", ".join(str(a) for a in faltam),
                  ", ".join(str(a) for a in sorted(disponiveis))))
    total = 0
    for ano in [a for a in anos if a in disponiveis]:
        ini = time.time()
        avisar("%d: a descarregar..." % ano)
        r = requests.get(disponiveis[ano], timeout=600)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
        texto = z.read(z.namelist()[0]).decode("utf-8")
        avisar("%d: %.0f MB, a carregar..." % (ano, len(r.content) / 1e6))
        n = _gravar_contratos(ano, objectos_do_array(texto))
        total += n
        avisar("%d: %d contratos em %.0f s" % (ano, n, time.time() - ini))
    with liga_corpus() as c:
        # Os nomes canonicos dependem das contagens de todo o corpus, por
        # isso resolvem-se no fim e nao ano a ano.
        avisar("a resolver as entidades...")
        _preencher_chaves(c)
        resolver_entidades(c)
        c.execute("INSERT OR REPLACE INTO corpus_estado VALUES (?,?)",
                  ("ultima_importacao", datetime.now().strftime("%Y-%m-%d %H:%M")))
    return total


def _gravar_contratos(ano, registos):
    with liga_corpus() as c:
        velhos = [r[0] for r in
                  c.execute("SELECT id FROM contratos WHERE ano=?", (ano,))]
        if velhos:
            c.execute("DELETE FROM contratos WHERE ano=?", (ano,))
            c.executemany("DELETE FROM contrato_cpv WHERE contrato_id=?",
                          [(i,) for i in velhos])
            c.executemany("DELETE FROM contrato_adjudicatario WHERE contrato_id=?",
                          [(i,) for i in velhos])
        n = 0
        linhas, cpvs, adjs = [], [], []
        for k in registos:
            cid = k.get("idcontrato")
            if cid is None:
                continue
            nif, nome = _nif_e_nome(k.get("adjudicante"))
            ganhadores = _partes(k.get("adjudicatarios"))
            linhas.append((
                cid, ano, (k.get("nAnuncio") or "").strip(),
                k.get("tipoprocedimento") or "",
                k.get("objectoContrato") or k.get("descContrato") or "",
                nif, nome, norma_entidade(nome),
                _data_iso(k.get("dataPublicacao")),
                _data_iso(k.get("dataCelebracaoContrato")),
                k.get("precoContratual") or 0.0,
                k.get("precoBaseProcedimento") or 0.0,
                k.get("prazoExecucao") or 0,
                ", ".join(x for x in (k.get("localExecucao") or []) if x)
                if isinstance(k.get("localExecucao"), list)
                else (k.get("localExecucao") or ""),
                ", ".join(_cpv8(k.get("cpv"))),
                k.get("fundamentacao") or "",
                # nunca zero: e divisor no grafico de quem ganha
                max(1, len(ganhadores)),
                chave_entidade(nif, nome)))
            for v in _cpv8(k.get("cpv")):
                cpvs.append((cid, v))
            for anif, anome in ganhadores:
                adjs.append((cid, anif, anome, norma_entidade(anome),
                             chave_entidade(anif, anome)))
            n += 1
            if len(linhas) >= 5000:
                _despejar(c, linhas, cpvs, adjs)
                linhas, cpvs, adjs = [], [], []
        _despejar(c, linhas, cpvs, adjs)
    return n


# As colunas de cada tabela, por ordem, e a unica fonte da verdade sobre
# elas: o SQL e as suas interrogacoes saem daqui. Duas vezes ja se
# acrescentou uma coluna e o INSERT posicional partiu em silencio -- com
# isto, acrescentar uma coluna que ninguem enche da erro no teste, nao a
# meio de uma importacao de meia hora.
COLS_CONTRATO = ("id", "ano", "n_anuncio", "tipo_procedimento", "objecto",
                 "adjudicante_nif", "adjudicante", "adjudicante_norm",
                 "data_publicacao", "data_celebracao", "preco_contratual",
                 "preco_base", "prazo_execucao", "local_execucao", "cpv",
                 "fundamentacao", "n_adj", "adjudicante_chave")
COLS_CPV = ("contrato_id", "cpv8")
COLS_ADJ = ("contrato_id", "nif", "nome", "nome_norm", "chave")


def _inserir(c, tabela, colunas, linhas, modo="OR IGNORE"):
    if not linhas:
        return
    c.executemany("INSERT %s INTO %s (%s) VALUES (%s)"
                  % (modo, tabela, ", ".join(colunas),
                     ",".join("?" * len(colunas))), linhas)


def _despejar(c, linhas, cpvs, adjs):
    _inserir(c, "contratos", COLS_CONTRATO, linhas, "OR REPLACE")
    _inserir(c, "contrato_cpv", COLS_CPV, cpvs)
    _inserir(c, "contrato_adjudicatario", COLS_ADJ, adjs)


def _preencher_chaves(c):
    """A mesma regra do chave_entidade(), em SQL, para nao trazer 400 mil
    linhas ao Python so para lhes por a chave. So mexe no que falta."""
    digitos = "[0-9]" * 9
    c.execute("UPDATE contratos SET adjudicante_chave = CASE"
              " WHEN adjudicante_nif GLOB '%s' THEN adjudicante_nif"
              " ELSE 'n:' || adjudicante_norm END"
              " WHERE adjudicante_chave IS NULL" % digitos)
    c.execute("UPDATE contrato_adjudicatario SET chave = CASE"
              " WHEN nif GLOB '%s' THEN nif ELSE 'n:' || nome_norm END"
              " WHERE chave IS NULL" % digitos)


def resolver_entidades(c):
    """Escolhe o nome por que cada entidade fica conhecida.

    O mais usado, com o mais curto a desempatar. Medido: da
    "Universidade do Porto" (1137 vezes) e nao uma das 84 faculdades, e
    "Instituto do Emprego e da Formacao Profissional, IP" e nao
    "Servicos Centrais". Uma entidade pode comprar e ganhar, por isso
    contam-se os dois lados.
    """
    c.execute("DELETE FROM entidades")
    c.execute("""
        WITH todos AS (
            SELECT adjudicante_chave chave, adjudicante_nif nif,
                   adjudicante nome, COUNT(*) k
            FROM contratos WHERE adjudicante_chave IS NOT NULL
              AND adjudicante != '' GROUP BY 1,2,3
            UNION ALL
            SELECT chave, nif, nome, COUNT(*) k
            FROM contrato_adjudicatario WHERE chave IS NOT NULL
              AND nome != '' GROUP BY 1,2,3
        ),
        somado AS (SELECT chave, nif, nome, SUM(k) k FROM todos
                   GROUP BY chave, nif, nome),
        melhor AS (
            SELECT chave, nif, nome,
                   ROW_NUMBER() OVER (PARTITION BY chave
                                      ORDER BY k DESC, LENGTH(nome)) pos,
                   COUNT(*) OVER (PARTITION BY chave) variantes
            FROM somado)
        INSERT INTO entidades (chave, nif, nome, variantes)
        SELECT chave, nif, nome, variantes FROM melhor WHERE pos = 1""")

    # E agora o caminho inverso: de qualquer nome para a entidade. Um
    # nome normalizado pode servir duas entidades com NIF diferente
    # (homonimos); fica com a que mais o usa.
    c.execute("DELETE FROM entidade_nomes")
    c.execute("""
        WITH todos AS (
            SELECT adjudicante_norm nm, adjudicante_chave chave, COUNT(*) k
            FROM contratos WHERE adjudicante_norm != '' GROUP BY 1,2
            UNION ALL
            SELECT nome_norm, chave, COUNT(*) k
            FROM contrato_adjudicatario WHERE nome_norm != '' GROUP BY 1,2
        ),
        somado AS (SELECT nm, chave, SUM(k) k FROM todos GROUP BY nm, chave),
        melhor AS (SELECT nm, chave,
                          ROW_NUMBER() OVER (PARTITION BY nm ORDER BY k DESC) pos
                   FROM somado)
        INSERT INTO entidade_nomes (nome_norm, chave)
        SELECT nm, chave FROM melhor WHERE pos = 1""")


def marca_corpus(chave, valor):
    with liga_corpus() as c:
        c.execute("INSERT OR REPLACE INTO corpus_estado VALUES (?,?)",
                  (chave, str(valor)))


def le_marca_corpus(chave, omissao=""):
    if not os.path.exists(CORPUS):
        return omissao
    try:
        with liga_corpus() as c:
            r = c.execute("SELECT valor FROM corpus_estado WHERE chave=?",
                          (chave,)).fetchone()
        return r["valor"] if r else omissao
    except sqlite3.Error:
        return omissao


# A actualizacao corre numa thread: um ano sao ~60 s e um pedido HTTP
# parado esse tempo parece o painel pendurado. O estado fica na base,
# para a pagina o mostrar e voltar a pedir-se sozinha.
_ACTUALIZAR = threading.Lock()


def actualizacao_a_correr():
    """Se ha mesmo uma actualizacao a decorrer, agora, neste processo.

    Nao basta olhar para a marca na base: ela fica gravada, e a thread
    que a limpa vive neste processo. Se o painel fechar a meio -- ou se
    o processo morrer -- a marca fica "a correr" para sempre e o botao
    nunca mais voltava. O trinco e a verdade; a marca so serve para
    mostrar o passo em que ia.
    """
    if _ACTUALIZAR.acquire(blocking=False):
        _ACTUALIZAR.release()
        return False
    return True


def actualizar_corpus(anos=None):
    """Traz de novo os anos pedidos. Por omissao, o ano corrente e o
    anterior -- e onde entram contratos novos; os anos fechados nao
    mudam. Reimportar substitui o ano, por isso e seguro repetir."""
    if not _ACTUALIZAR.acquire(blocking=False):
        return False                    # ja vai uma a caminho
    def trabalho():
        try:
            marca_corpus("actualizacao", "a correr")
            n = importar_contratos(anos or anos_pedidos([]),
                                   avisar=lambda m: marca_corpus("actualizacao_passo", m))
            marca_corpus("actualizacao", "ok")
            marca_corpus("actualizacao_passo", "%s contratos revistos" % mil_pt(n))
        except Exception as erro:       # rede, disco, dump mal formado
            marca_corpus("actualizacao", "falhou")
            marca_corpus("actualizacao_passo", str(erro)[:200])
        finally:
            _ACTUALIZAR.release()
    threading.Thread(target=trabalho, daemon=True).start()
    return True


def ha_corpus():
    """Se o corpus existe e tem alguma coisa la dentro. O painel usa isto
    para nao prometer historico a quem ainda nao o importou."""
    if not os.path.exists(CORPUS):
        return 0
    try:
        with liga_corpus() as c:
            return c.execute("SELECT COUNT(*) n FROM contratos").fetchone()["n"]
    except sqlite3.Error:
        return 0


def com_corpus(c):
    """Poe o corpus ao lado da base de trabalho, como `corpus`, para se
    poderem cruzar numa consulta so. Devolve se conseguiu."""
    if not os.path.exists(CORPUS):
        return False
    try:
        c.execute("ATTACH DATABASE ? AS corpus", (CORPUS,))
        return True
    except sqlite3.Error:
        return False


def historico_entidade(entidade, cpv="", limite=25, nif=""):
    """Contratos ja celebrados por esta entidade **no CPV do anuncio**.

    A entidade acha-se pelo nome normalizado: o radar so guarda o nome
    que o DR escreve, e o BASE guarda o NIF ao lado. Medido, 93,7% das
    entidades do radar acham-se assim -- ver `norma_entidade()`.

    O CPV **restringe**, nao apenas ordena. Antes vinham os do CPV a
    frente e o resto por baixo, e as 25 linhas enchiam-se de contratos
    de limpeza e de refeicoes que nada diziam sobre o concurso em maos.
    Sem CPV no anuncio -- ou sem nada da entidade nesse CPV -- devolve
    vazio e quem chama diz porque.

    Devolve (linhas, quantos_ao_todo, quantos_do_cpv, chave).
    """
    if not ha_corpus():
        return [], 0, 0, ""
    # Pela chave e nao pelo nome: o DR escreve "Universidade do Porto" e o
    # contrato pode estar assinado por uma das 86 faculdades, todas com o
    # mesmo NIF. Ver entidade_do_anuncio().
    alvo = entidade_do_anuncio(nif, entidade)
    if not alvo:
        return [], 0, 0, ""
    prefixos = [p for p in (prefixo_cpv(x) for x in (cpv or "").split(",")) if p]
    with liga_corpus() as c:
        ao_todo = c.execute("SELECT COUNT(*) n FROM contratos "
                            "WHERE adjudicante_chave=?", (alvo,)).fetchone()["n"]
        if not ao_todo:
            return [], 0, 0, ""
        if not prefixos:
            return [], ao_todo, 0, alvo
        # `IN` e nao `JOIN`: um contrato com varios CPV da mesma divisao
        # aparecia uma vez por CPV.
        no_cpv = ("c.id IN (SELECT contrato_id FROM contrato_cpv WHERE %s)"
                  % " OR ".join("cpv8 LIKE ?" for _ in prefixos))
        como_cpv = [p + "%" for p in prefixos]
        do_cpv = c.execute(
            "SELECT COUNT(*) n FROM contratos c "
            "WHERE c.adjudicante_chave=? AND " + no_cpv,
            [alvo] + como_cpv).fetchone()["n"]
        if not do_cpv:
            return [], ao_todo, 0, alvo
        valores = [alvo] + como_cpv + [limite]
        linhas = c.execute(
            "WITH pag AS (SELECT c.* FROM contratos c "
            " WHERE c.adjudicante_chave=? AND " + no_cpv +
            " ORDER BY c.data_celebracao DESC, c.id DESC LIMIT ?)"
            " SELECT p.*,"
            " (SELECT group_concat(COALESCE(g.nome, a.nome), '|')"
            "  FROM contrato_adjudicatario a"
            "  LEFT JOIN entidades g ON g.chave=a.chave"
            "  WHERE a.contrato_id=p.id) AS ganhou,"
            " (SELECT group_concat(a.chave, '|') FROM contrato_adjudicatario a"
            "  WHERE a.contrato_id=p.id) AS ganhou_ch"
            " FROM pag p ORDER BY p.data_celebracao DESC, p.id DESC",
            valores).fetchall()
    return linhas, ao_todo, do_cpv, alvo


def condicoes_contratos(args):
    """Traduz os filtros do separador dos contratos em SQL.

    Irma da condicoes(), mas nao a mesma: sao listas diferentes. Aqui
    procura-se por quem ganhou, por tipo de procedimento e por valor, que
    nos anuncios nem existem -- um anuncio ainda nao tem vencedor.
    """
    onde, valores = ["1=1"], []

    def procura(texto, coluna):
        pedacos = [p.strip() for p in (texto or "").split("|") if p.strip()]
        if not pedacos:
            return
        ors = []
        for p in pedacos:
            ors.append("%s LIKE ? ESCAPE '%s'" % (coluna, ESCAPE_LIKE))
            valores.append("%" + para_like(p) + "%")
        onde.append("(" + " OR ".join(ors) + ")")

    procura(args.get("q"), "c.objecto")
    procura(args.get("adj"), "c.adjudicante")

    # Quem ganhou vive numa tabela a parte (um contrato pode ter varios
    # adjudicatarios). EXISTS e nao JOIN: com JOIN, um contrato ganho por
    # um agrupamento de tres aparecia tres vezes na lista.
    # `IN` e nao `EXISTS`: as duas dao o mesmo (e nenhuma repete linhas,
    # que era o problema do JOIN), mas o EXISTS obriga a passar por todos
    # os contratos a perguntar por cada um. Com o IN, a tabela filha
    # varre-se uma vez e sai o conjunto de ids -- 183 ms contra 517 no
    # corpus de sete anos, e a diferenca cresce com ele.
    ganhou = [p.strip() for p in (args.get("ganhou") or "").split("|") if p.strip()]
    if ganhou:
        onde.append("c.id IN (SELECT contrato_id FROM contrato_adjudicatario "
                    "WHERE %s)"
                    % " OR ".join("nome LIKE ? ESCAPE '%s'" % ESCAPE_LIKE
                                  for _ in ganhou))
        valores += ["%" + para_like(p) + "%" for p in ganhou]

    prefixos = [p for p in (prefixo_cpv(x)
                            for x in (args.get("cpv") or "").split("|")) if p]
    if prefixos:
        onde.append("c.id IN (SELECT contrato_id FROM contrato_cpv WHERE %s)"
                    % " OR ".join("cpv8 LIKE ?" for _ in prefixos))
        valores += [p + "%" for p in prefixos]
    elif (args.get("cpv") or "").strip():
        onde.append("1=0")            # codigo que nao da prefixo: vazio, nao tudo

    # Por entidade, e nao por nome: e o que a ficha da entidade usa nos
    # atalhos. Filtrar pelo nome mostrava menos contratos do que o numero
    # que a ficha promete, porque a mesma entidade assina com varios.
    #
    # Chamam-se `entid`/`vencid` e nao `ent`/`venc` porque nos anuncios o
    # `ent` e a caixa de texto da entidade -- dois campos com o mesmo
    # nome e sentidos diferentes eram um erro a espera de acontecer.
    ent = (args.get("entid") or "").strip()
    if ent:
        onde.append("c.adjudicante_chave = ?")
        valores.append(ent)
    venc = (args.get("vencid") or "").strip()
    if venc:
        onde.append("c.id IN (SELECT contrato_id FROM contrato_adjudicatario "
                    "WHERE chave=?)")
        valores.append(venc)

    proc = (args.get("proc") or "").strip()
    if proc:
        onde.append("c.tipo_procedimento = ?")
        valores.append(proc)

    de = (args.get("de") or "").strip()
    if de:
        onde.append("c.data_celebracao >= ?")
        valores.append(de)
    ate = (args.get("ate") or "").strip()
    if ate:
        onde.append("c.data_celebracao <= ?")
        valores.append(ate)

    minimo = (args.get("min") or "").strip().replace(" ", "").replace(",", ".")
    if minimo:
        try:
            valores.append(float(minimo))
            onde.append("c.preco_contratual >= ?")
        except ValueError:
            pass                       # lixo na URL nao filtra nada
    return " WHERE " + " AND ".join(onde), valores


# ---------------------------------------------------------- agendamento

def slot_corrido(dia, hora):
    with liga() as c:
        return c.execute("SELECT 1 FROM slots WHERE dia=? AND hora=?",
                         (dia, hora)).fetchone() is not None


def registar_slot(dia, hora, novos):
    with liga() as c:
        c.execute("INSERT OR REPLACE INTO slots VALUES (?,?,?,?)",
                  (dia, hora, datetime.now().strftime("%H:%M"), novos))


def relogio():
    """Enquanto o painel estiver aberto, vigia as horas marcadas.
    Se o PC esteve desligado, apanha o slot em falta quando ligar."""
    while True:
        try:
            cfg = ler_config()
            agora = datetime.now()
            dia = agora.strftime("%Y-%m-%d")
            for hora in cfg["horas_verificacao"]:
                h, m = (int(x) for x in hora.split(":"))
                marcado = agora.replace(hour=h, minute=m, second=0, microsecond=0)
                passou = agora >= marcado
                atrasado = cfg.get("recuperar_slot_falhado", True)
                if passou and not slot_corrido(dia, hora):
                    if agora - marcado < timedelta(minutes=5) or atrasado:
                        _, novos = verificar(cfg)
                        registar_slot(dia, hora, novos)
        except Exception as erro:
            # Engolir isto em silencio fazia com que uma avaria persistente
            # parecesse "ainda nao chegou a hora": o painel continuava a
            # mostrar a ultima verificacao boa, dias a fio.
            try:
                marca("ultimo_erro_relogio", "%s: %s"
                      % (datetime.now().strftime("%Y-%m-%d %H:%M"), str(erro)[:200]))
            except Exception:
                pass
        time.sleep(60)



# ---------------------------------------------------------------- painel

app = Flask(__name__)

# A aparencia vem de um desenho feito no Claude Design ("Alertas de
# Concursos Publicos"). Uma folha de estilo e um esqueleto unicos,
# partilhados pelos quatro ecras -- antes cada um repetia o seu HTML
# completo, com estilos ligeiramente diferentes.
#
# O CSS vive numa constante propria e entra por substituicao, nao no
# texto do molde: assim as percentagens (50%, 100vh, flex:1 1 30%) nao
# precisam de ser escapadas como %% e o ficheiro fica legivel.

CSS = r"""
:root{
 --ink:#12141a; --azul:#1f4e79; --verde:#1e8449; --verm:#c0392b;
 --laranja:#d68910; --coral:#ff6b57;
 --papel:#f6f4ef; --creme:#fbfaf7; --linha:#e2ded4; --linha2:#f0eee9;
 --t1:#12141a; --t2:#4a5058; --t3:#7b8189; --t4:#8c9199; --t5:#9ba0a7; --t6:#b4b0a6;
 --sans:Archivo,system-ui,-apple-system,'Segoe UI',sans-serif;
 --mono:'JetBrains Mono',ui-monospace,Consolas,monospace;
}
*{box-sizing:border-box}
body{margin:0;background:var(--papel);font-family:var(--sans);color:var(--t1);
 -webkit-font-smoothing:antialiased}
a{color:var(--azul);text-decoration:none}
a:hover{color:var(--ink)}
::-webkit-scrollbar{width:10px;height:10px}
::-webkit-scrollbar-thumb{background:#c9c4b8;border-radius:6px}
.app{display:flex;min-height:100vh}

/* barra lateral */
aside{width:236px;flex:none;background:var(--ink);color:#fff;display:flex;
 flex-direction:column;position:sticky;top:0;height:100vh}
.marca{padding:26px 22px 20px;border-bottom:1px solid rgba(255,255,255,.09)}
.marca .logo{font:700 17px/1 var(--sans);letter-spacing:-.4px}
.marca .logo span{color:var(--coral)}
.marca .sub{font:500 10px/1.4 var(--mono);color:rgba(255,255,255,.45);
 letter-spacing:.08em;margin-top:6px;text-transform:uppercase}
.marca .meta{font:400 10.5px/1.4 var(--mono);color:rgba(255,255,255,.3);margin-top:9px}
aside nav{padding:14px 10px;display:flex;flex-direction:column;gap:2px}
aside nav a{display:flex;align-items:center;gap:10px;
 padding:9px 12px;border-radius:7px;color:rgba(255,255,255,.62)}
aside nav a:hover{background:rgba(255,255,255,.09);color:#fff}
aside nav a.on{background:rgba(255,255,255,.08);color:#fff}
aside nav a b{font:500 13.5px/1.2 var(--sans)}
.caixa{margin:16px 14px 0;padding:12px 13px;border-radius:8px;background:rgba(255,255,255,.05)}
.caixa .r{font:500 9.5px/1 var(--sans);color:rgba(255,255,255,.4);
 text-transform:uppercase;letter-spacing:.09em}
.caixa .h{font:500 11.5px/1.5 var(--mono);color:rgba(255,255,255,.72);margin-top:7px}
.caixa .n{font:400 11px/1.5 var(--sans);color:rgba(255,255,255,.42);margin-top:4px}
.sou{margin-top:auto;padding:16px 22px;border-top:1px solid rgba(255,255,255,.09)}
.sou .r{font:500 9.5px/1 var(--sans);color:rgba(255,255,255,.4);
 text-transform:uppercase;letter-spacing:.09em}
.sou form{display:flex;align-items:center;gap:8px;margin-top:9px}
.sou .av{width:26px;height:26px;border-radius:50%;background:#3a3f4a;flex:none;
 font:600 10px/26px var(--sans);color:#cfd3da;text-align:center}
.sou input{flex:1;min-width:0;background:transparent;border:0;
 border-bottom:1px solid rgba(255,255,255,.18);color:#fff;
 font:500 12.5px/1.6 var(--sans);padding:2px 0}
.sou input::placeholder{color:rgba(255,255,255,.3)}
.sou input:focus{outline:none;border-bottom-color:var(--coral)}
.sou button{background:none;border:0;color:rgba(255,255,255,.35);cursor:pointer;
 font:400 11px/1.2 var(--sans);padding:0;flex:none}
.sou button:hover{color:#fff}

/* zona principal */
main{flex:1;min-width:0;display:flex;flex-direction:column}
.topo{padding:16px 34px 0;border-bottom:1px solid var(--linha);background:var(--creme);
 position:sticky;top:0;z-index:5}
.migalhas{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.migalhas .b{display:flex;align-items:center;gap:8px;min-width:0;
 font:500 11.5px/1 var(--sans);color:var(--t3)}
.migalhas .b s{text-decoration:none;color:#c9c4b8}
.migalhas .b em{font-style:normal;color:var(--ink)}
.accoes-topo{margin-left:auto;display:flex;align-items:center;gap:8px}
/* tudo o que altera dados e um <form method=post>; estas regras fazem
   com que continue a parecer um botao ou uma ligacao */
form.accao{display:inline-block;margin:0}
form.accao button{font-family:inherit}
.bt{cursor:pointer;padding:8px 13px;border-radius:7px;border:1px solid var(--linha);
 background:#fff;font:600 12px/1 var(--sans);color:var(--t2);display:inline-block}
.bt:hover{border-color:var(--ink);color:var(--ink)}
.bt.forte{background:var(--azul);color:#fff;border-color:var(--azul)}
.bt.forte:hover{background:var(--ink);border-color:var(--ink);color:#fff}
.bt.verde{background:var(--verde);color:#fff;border-color:var(--verde)}
.bt.verde:hover{background:#16663a;color:#fff;border-color:#16663a}
h1.tit{margin:8px 0 0;font:600 20px/1.25 var(--sans);color:var(--ink);
 letter-spacing:-.4px;max-width:900px;text-wrap:pretty}
p.subtit{margin:5px 0 0;font:400 12.5px/1.3 var(--sans);color:var(--t3)}
.abas{display:flex;align-items:center;gap:6px;margin-top:14px}
.abas a{padding:9px 14px;border-radius:7px 7px 0 0;font:600 12.5px/1 var(--sans);
 background:transparent;color:var(--t3);border:1px solid transparent;
 border-bottom:none;margin-bottom:-1px}
.abas a.on{background:#fff;color:var(--ink);border-color:var(--linha)}
.abas a i{font:500 11px/1 var(--mono);font-style:normal;color:var(--t6);margin-left:3px}
.abas a.on i{color:var(--t5)}
.vazio-topo{height:16px}
.corpo{padding:24px 34px 60px}
.larg{max-width:1240px}

/* pecas comuns */
.cx{background:#fff;border:1px solid var(--linha);border-radius:11px;
 box-shadow:0 1px 2px rgba(0,0,0,.06)}
.rot{font:600 12px/1 var(--sans);color:var(--ink);text-transform:uppercase;
 letter-spacing:.07em}
.nota{font:400 11.5px/1.5 var(--sans);color:var(--t4)}
.vazio{background:#fff;border:1px solid var(--linha);border-radius:11px;
 padding:40px;text-align:center;color:var(--t5);font:400 13px/1.5 var(--sans)}
.flash{background:#eef4fa;border:1px solid #cfe0ef;border-radius:9px;
 padding:11px 15px;margin-bottom:14px;font:500 12.5px/1.4 var(--sans);
 color:var(--azul)}
.flash.mau{background:#fbe9e6;border-color:#f0c9c3;color:var(--verm)}
.flash code{font:500 11.5px/1 var(--mono);background:rgba(0,0,0,.06);
 padding:2px 6px;border-radius:4px}
.tag{font:500 10.5px/1 var(--sans);padding:4px 7px;border-radius:4px;
 background:var(--linha2);color:#5c6169;white-space:nowrap}
.tag.mono{font-family:var(--mono)}
.tag.ok{background:#e6f2ea;color:var(--verde);font-weight:600}
.tag.avisa{background:#fdf1de;color:#8a5307;font-weight:600}
.tag.mau{background:#fbe3e0;color:var(--verm);font-weight:600}
.tag.info{background:#eef4fa;color:var(--azul);font-weight:600}
.ponto{width:7px;height:7px;border-radius:50%;flex:none;display:inline-block}

/* filtros */
.filtros{display:flex;align-items:center;gap:10px;flex-wrap:wrap;
 padding:14px 16px;margin-bottom:12px}
.filtros input[type=text]{flex:1;min-width:220px;padding:9px 12px;
 border:1px solid var(--linha);border-radius:8px;background:var(--creme);
 font:400 12.5px/1.2 var(--sans);color:var(--ink)}
.filtros input[type=date]{padding:9px 12px;border:1px solid var(--linha);
 border-radius:8px;background:var(--creme);font:500 12.5px/1.2 var(--mono);color:var(--ink)}
.filtros select{padding:9px 12px;border:1px solid var(--linha);border-radius:8px;
 background:var(--creme);font:400 12.5px/1.2 var(--sans);color:var(--ink);
 /* o select cresce com a opcao mais longa ("Ao abrigo de acordo-quadro
    (art.o 259.o)") e punha a pagina a rolar de lado num ecra estreito */
 max-width:100%;min-width:0}
.filtros label{font:500 12px/1 var(--sans);color:var(--t3)}
.filtros button{cursor:pointer;padding:10px 18px;border-radius:8px;border:0;
 background:var(--azul);color:#fff;font:600 12.5px/1 var(--sans)}
.filtros button:hover{background:var(--ink)}
.filtros a.limpar{padding:10px 12px;font:500 12.5px/1 var(--sans);color:var(--t5)}
.filtros a.limpar:hover{color:var(--ink)}
/* separador dos alertas */
.alertas{display:flex;flex-direction:column;gap:10px}
.alerta{display:flex;align-items:center;gap:14px;background:#fff;
 border:1px solid var(--linha);border-radius:10px;padding:14px 16px;
 box-shadow:0 1px 2px rgba(0,0,0,.06)}
.alerta.on{border-color:#bcd4e8;background:#fbfdff}
.alerta .sobre{display:flex;flex-direction:column;gap:4px;min-width:0;flex:1}
.alerta .sobre a{font:600 13.5px/1.2 var(--sans);color:var(--ink)}
.alerta.on .sobre a{color:var(--azul)}
.alerta .sobre a:hover{text-decoration:underline}
.alerta .q{font:400 11.5px/1.4 var(--sans);color:var(--t5);
 overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.alerta .conta{font:400 11.5px/1.4 var(--sans);color:var(--t5);
 text-align:right;flex:none}
.alerta .conta b{color:var(--azul);font-weight:600}
.alerta form{display:flex;flex:none}
.interruptor{cursor:pointer;width:42px;height:24px;border-radius:99px;
 border:1px solid var(--linha);background:var(--linha2);padding:0;
 position:relative;transition:background .12s}
.interruptor i{position:absolute;top:2px;left:2px;width:18px;height:18px;
 border-radius:50%;background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.2);
 transition:left .12s}
.interruptor.on{background:var(--azul);border-color:var(--azul)}
.interruptor.on i{left:21px}

/* barra do corpus, no topo dos contratos */
.corpus-barra{display:flex;align-items:center;gap:12px;flex-wrap:wrap;
 margin-bottom:12px;font:400 11.5px/1.4 var(--sans);color:var(--t5)}
.corpus-barra .accao{margin-left:auto}
.corpus-barra .a-correr{margin-left:auto;font:500 12px/1 var(--sans);
 color:var(--azul);display:inline-flex;align-items:center;gap:8px}
.corpus-barra .a-correr::before{content:'';width:9px;height:9px;flex:none;
 border-radius:50%;background:var(--azul);animation:pisca 1.1s infinite}
@keyframes pisca{0%,100%{opacity:1}50%{opacity:.25}}

/* ficha da entidade */
.ent-cab{padding:20px 24px;margin-bottom:14px}
.ent-cab .n{font:600 22px/1.25 var(--sans);color:var(--ink);letter-spacing:-.3px}
.ent-cab .m{font:500 12px/1 var(--mono);color:var(--t5);margin-top:7px}
.ent-nomes{margin-top:12px}
.ent-nomes summary{cursor:pointer;font:400 11.5px/1.4 var(--sans);color:var(--t5)}
.ent-nomes summary:hover{color:var(--ink)}
.ent-nomes>div{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.ent-nomes span{font:400 10.5px/1.3 var(--sans);color:var(--t4);
 background:var(--linha2);padding:4px 8px;border-radius:4px}
.kpis.dois{grid-template-columns:repeat(2,minmax(0,1fr))}
.kpi .r{font:600 11px/1 var(--sans);color:var(--t5);text-transform:uppercase;
 letter-spacing:.07em}
.ent-atalhos{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}
.ent-atalhos a{padding:9px 14px;border:1px solid var(--linha);border-radius:8px;
 background:#fff;font:500 12px/1 var(--sans);color:var(--t3);
 box-shadow:0 1px 2px rgba(0,0,0,.06)}
.ent-atalhos a:hover{border-color:var(--ink);color:var(--ink)}
.ent-filtros{margin-bottom:14px}
.periodos{display:flex;align-items:center;gap:6px;flex-wrap:wrap;
 flex-basis:100%;margin-top:2px}
.periodos span{font:400 11px/1 var(--sans);color:var(--t6);margin-right:2px}
.periodos a{padding:6px 11px;border:1px solid var(--linha);border-radius:99px;
 background:var(--creme);font:500 11.5px/1 var(--sans);color:var(--t4)}
.periodos a:hover{border-color:var(--t6);color:var(--ink)}
.periodos a.on{background:var(--azul);border-color:var(--azul);color:#fff}
.graf-corpo.solto{padding:0}
.bh .t a{color:var(--azul)}
.bh .t a:hover{color:var(--ink);text-decoration:underline}
.tab-contratos td a{color:var(--azul)}
.tab-contratos td a:hover{text-decoration:underline}

/* graficos dos contratos */
.graf-corpo{padding:16px 18px;display:grid;
 grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:14px}
.graf-corpo>.graf:last-child{grid-column:1/-1}
.graf{padding:16px 18px}
.barras-h{display:flex;flex-direction:column;gap:9px}
.bh{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(60px,2fr) 76px 84px;
 align-items:center;gap:10px}
.bh .t{font:400 11.5px/1.3 var(--sans);color:var(--t2);overflow:hidden;
 text-overflow:ellipsis;white-space:nowrap}
.bh .r{display:block;height:9px;border-radius:5px;background:var(--linha2)}
.bh .r i{display:block;height:100%;border-radius:5px;background:var(--azul)}
.bh .v{font:600 11.5px/1 var(--mono);color:var(--ink);text-align:right}
.bh .k{font:400 10.5px/1 var(--sans);color:var(--t6);text-align:right}
.graf .barras{height:150px}
.graf .barras .v{font:600 10.5px/1 var(--mono)}
.graf .barras .b{background:var(--azul)}
.graf .barras .col.parcial .b{background:repeating-linear-gradient(135deg,
 var(--azul) 0 4px,rgba(31,78,121,.35) 4px 8px)}
.graf .barras .col.parcial .v,.graf .barras .col.parcial .l{color:var(--t5)}
.graf .barras .col.destaque .b{background:var(--verde)}
.graf .barras .col.destaque .v{color:var(--verde)}
.graf .barras .col.destaque .l{color:var(--verde);font-weight:600}
.conc-n{font:700 34px/1 var(--mono);color:var(--ink);letter-spacing:-1.5px;
 margin-bottom:12px}
.conc-b{display:flex;height:22px;border-radius:5px;overflow:hidden;
 background:var(--linha2)}
.conc-b i{display:block;height:100%}
@media (max-width:900px){.graf-corpo{grid-template-columns:minmax(0,1fr)}}

/* separador dos contratos */
.tab-cx{padding:0;overflow-x:auto}
.tab-contratos{width:100%;border-collapse:collapse;min-width:900px}
.tab-contratos th{text-align:left;padding:11px 12px;background:var(--creme);
 border-bottom:1px solid var(--linha);font:600 10.5px/1 var(--sans);
 color:var(--t5);text-transform:uppercase;letter-spacing:.06em;white-space:nowrap}
.tab-contratos td{padding:10px 12px;border-bottom:1px solid var(--linha2);
 font:400 12px/1.4 var(--sans);color:var(--t3);vertical-align:top}
.tab-contratos tr:last-child td{border-bottom:0}
.tab-contratos tr:hover td{background:var(--creme)}
.tab-contratos td.d{font-family:var(--mono);white-space:nowrap;color:var(--t5)}
.tab-contratos td.o{color:var(--ink);max-width:340px}
.tab-contratos td.g{color:var(--ink);font-weight:500;max-width:220px}
.tab-contratos th.p,.tab-contratos td.p{text-align:right;white-space:nowrap;
 font-family:var(--mono);color:var(--ink)}
.vazio code,.larg>.nota code{font:500 11.5px/1 var(--mono);
 background:var(--linha2);padding:2px 6px;border-radius:4px}
.vazio.comecar{display:flex;flex-direction:column;gap:10px;padding:48px 40px}
.vazio.comecar b{font:600 15px/1.3 var(--sans);color:var(--ink)}
.vazio.comecar span{max-width:620px;margin:0 auto}
.vazio.comecar .p{font-size:11.5px;color:var(--t6)}

/* historico de adjudicacoes, na ficha */
.mercado{padding:16px 18px;margin-top:14px}
.tab-mercado{width:100%;border-collapse:collapse}
.tab-mercado th{text-align:left;padding:7px 10px;border-bottom:1px solid var(--linha);
 font:600 10.5px/1 var(--sans);color:var(--t5);text-transform:uppercase;
 letter-spacing:.06em;white-space:nowrap}
.tab-mercado td{padding:8px 10px;border-bottom:1px solid var(--linha2);
 font:400 12px/1.35 var(--sans);color:var(--t3);vertical-align:top}
.tab-mercado td.d{font-family:var(--mono);white-space:nowrap;color:var(--t5)}
.tab-mercado td.g{color:var(--ink);font-weight:500}
.tab-mercado th.p,.tab-mercado td.p{text-align:right;white-space:nowrap;
 font-family:var(--mono)}
.tab-mercado td.o{color:var(--ink);max-width:300px}
.tab-mercado tr:last-child td{border-bottom:0}
/* a coluna do objecto pode ser longa; a tabela rola dentro da caixa em
   vez de empurrar a ficha toda para o lado */
.ref-preco{border:1px solid var(--linha);border-radius:9px;padding:14px 16px;
 margin-bottom:14px;background:var(--creme);
 font:400 12.5px/1.5 var(--sans);color:var(--t3)}
.ref-preco b.bom{color:var(--verde)}
.ref-preco b.mau{color:var(--verm)}
.escada{display:flex;gap:8px;margin:12px 0 4px}
.escada span{flex:1;display:flex;flex-direction:column;gap:4px;padding:8px 6px;
 border-radius:6px;background:#fff;border:1px solid var(--linha);
 font:400 10px/1 var(--sans);color:var(--t6);text-align:center}
.escada span b{font:600 12px/1 var(--mono);color:var(--ink)}
.escada span.med{border-color:var(--azul);background:#eef4fa}
.escada span.med b{color:var(--azul)}
.mercado-tab{overflow-x:auto}
.mercado-tab .tab-mercado{min-width:720px}
.mercado code{font:500 11.5px/1 var(--mono);background:var(--linha2);
 padding:2px 5px;border-radius:4px}
.guardados{display:flex;align-items:center;gap:8px;flex-wrap:wrap;
 padding:12px 16px;margin-bottom:12px}
.guardados .rot{margin-right:4px}
.guardados .nada{font:400 12px/1 var(--sans);color:var(--t6)}
.guardado{display:inline-flex;align-items:center;border:1px solid var(--linha);
 border-radius:99px;background:var(--creme);overflow:hidden}
.guardado a{padding:7px 4px 7px 13px;font:500 12.5px/1 var(--sans);color:var(--t3)}
.guardado:hover{border-color:var(--t6)}
.guardado:hover a{color:var(--ink)}
.guardado.on{border-color:var(--azul);background:#eef4fa}
.guardado.on a{color:var(--azul);font-weight:600}
.guardado form{display:inline-flex}
.guardado button{cursor:pointer;border:0;background:none;color:var(--t6);
 padding:7px 11px 7px 6px;font:500 14px/1 var(--sans)}
.guardado button:hover{color:var(--verm)}
.guardados .guardar{display:flex;align-items:center;gap:8px;margin-left:auto}
.guardados .guardar input{padding:8px 12px;min-width:200px;
 border:1px solid var(--linha);border-radius:8px;background:var(--creme);
 font:400 12.5px/1.2 var(--sans);color:var(--ink)}
.guardados .guardar button{cursor:pointer;padding:9px 15px;border-radius:8px;
 border:1px solid var(--linha);background:#fff;color:var(--t3);
 font:600 12.5px/1 var(--sans)}
.guardados .guardar button:hover{border-color:var(--ink);color:var(--ink)}
.cpv-activo{display:flex;align-items:center;gap:9px;padding:10px 14px;
 border:1px solid #cfe0ef;background:#eef4fa;border-radius:9px;margin-bottom:12px;
 font:500 12px/1.3 var(--sans);color:var(--azul)}
.cpv-activo b{font:600 12px/1.3 var(--mono)}
.cpv-activo a{text-decoration:underline}

/* arvore de CPV */
details.arvore{margin-bottom:16px;overflow:hidden;background:#fff;
 border:1px solid var(--linha);border-radius:11px;box-shadow:0 1px 2px rgba(0,0,0,.06)}
details.arvore>summary{cursor:pointer;display:flex;align-items:center;gap:10px;
 padding:14px 18px;background:var(--creme);list-style:none}
details.arvore>summary::-webkit-details-marker{display:none}
details.arvore>summary::before{content:'\25B8';font:500 11px/1 var(--mono);color:var(--t3)}
details.arvore[open]>summary::before{content:'\25BE'}
.arv-tit{font:600 13px/1 var(--sans);color:var(--ink)}
.arv-sub{font:400 12px/1 var(--sans);color:var(--t5)}
.arv-chip{margin-left:auto;font:600 11px/1 var(--sans);padding:4px 8px;
 border-radius:5px;background:var(--linha2);color:var(--t5)}
.arvore-topo{display:flex;align-items:center;gap:10px;flex-wrap:wrap;
 padding:14px 18px 12px;border-top:1px solid var(--linha)}
.arvore-topo input{flex:1;min-width:220px;padding:8px 12px;border:1px solid var(--linha);
 border-radius:8px;background:var(--creme);font:400 12.5px/1.2 var(--sans)}
.arvore-topo button{cursor:pointer;padding:9px 14px;border-radius:7px;border:0;
 background:var(--azul);color:#fff;font:600 12px/1 var(--sans)}
.arvore-topo button.claro{background:#fff;color:var(--t3);border:1px solid var(--linha)}
#arvore-contagem{font:400 11.5px/1 var(--sans);color:var(--t5)}
#arvore-corpo{max-height:330px;overflow-y:auto;border:1px solid var(--linha2);
 border-radius:9px;padding:8px 6px;background:#fdfcfa;margin:0 18px 14px}
#arvore-corpo details{margin-left:22px}
#arvore-corpo summary{cursor:pointer;list-style:revert}
#arvore-corpo .no{display:flex;align-items:center;gap:9px;padding:5px 8px;
 border-radius:6px}
#arvore-corpo .no:hover{background:#f3f1ec}
#arvore-corpo .cod{font:500 10.5px/1 var(--mono);color:var(--t5);flex:none}
#arvore-corpo .lbl{font:500 12px/1.35 var(--sans);color:var(--azul);min-width:0;
 overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#arvore-corpo .n{font:400 10.5px/1 var(--sans);color:var(--t6);flex:none}
#arvore-corpo .escondido{display:none}
.arv-pe{padding:0 18px 16px;font:400 11px/1.5 var(--sans);color:var(--t5)}

/* lista */
.linha-conta{display:flex;align-items:center;gap:10px;margin-bottom:12px;
 font:400 12px/1 var(--sans);color:var(--t5)}
.linha-conta a{margin-left:auto;color:var(--t5)}
.linha-conta a:hover{color:var(--ink)}
.paginas{display:flex;align-items:center;justify-content:center;gap:5px;
 flex-wrap:wrap;margin-top:16px}
.paginas a,.paginas b,.paginas span{min-width:32px;padding:7px 10px;
 border-radius:6px;text-align:center;font:500 12.5px/1 var(--sans)}
.paginas a{background:#fff;border:1px solid var(--linha);color:var(--t4);
 box-shadow:0 1px 2px rgba(0,0,0,.06)}
.paginas a:hover{border-color:var(--t6);color:var(--ink)}
.paginas b.on{background:var(--ink);border:1px solid var(--ink);color:#fff;
 font-weight:600}
.paginas .morto{border:1px solid transparent;color:var(--t6);opacity:.5}
.paginas .corte{border:1px solid transparent;color:var(--t6);min-width:0;
 padding:7px 2px}
.lista{display:flex;flex-direction:column;gap:10px}
.item{display:grid;grid-template-columns:64px minmax(0,1fr) 210px;background:#fff;
 border:1px solid var(--linha);border-radius:6px;box-shadow:0 1px 2px rgba(0,0,0,.06);
 overflow:hidden}
.item-data{padding:16px 0;text-align:center;border-right:1px solid var(--linha2);
 background:var(--creme)}
.item-data .dia{font:700 21px/1 var(--mono);color:var(--ink)}
.item-data .mes{font:500 10px/1.4 var(--sans);color:var(--t5);
 text-transform:uppercase;letter-spacing:.06em}
.item-corpo{padding:15px 18px;min-width:0}
.item-titulo{font:700 14.5px/1.35 var(--sans);color:var(--azul);display:block;
 text-wrap:pretty}
.item-titulo:hover{color:var(--ink)}
.item-entidade{font:400 12.5px/1.4 var(--sans);color:#6e747c;margin-top:5px}
.item-meta{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}
.item-lado{padding:15px 18px;border-left:1px solid var(--linha2);display:flex;
 flex-direction:column;align-items:flex-end;justify-content:center;gap:10px}
.item-preco{font:600 15px/1.2 var(--mono);color:var(--ink)}
.item-accoes{display:flex;gap:7px}
.mini{cursor:pointer;padding:7px 12px;border-radius:6px;font:600 11.5px/1 var(--sans);
 border:1px solid var(--linha);color:var(--t3);background:#fff;display:inline-block}
.mini:hover{border-color:var(--verm);color:var(--verm)}
.mini.verde{background:var(--verde);color:#fff;border-color:var(--verde)}
.mini.verde:hover{background:#16663a;color:#fff;border-color:#16663a}
.rodape{margin-top:18px;padding:12px 16px;border:1px solid var(--linha);
 border-radius:8px;background:var(--creme);display:flex;align-items:center;gap:10px}
.rodape .e{font:500 12px/1 var(--sans);color:var(--t2)}
.rodape .d{font:400 12px/1 var(--sans);color:var(--t5)}

/* ficha */
.ficha-topo{display:flex;align-items:center;gap:10px;margin-bottom:14px;flex-wrap:wrap}
.ficha-topo .dir{display:flex;align-items:center;gap:6px;margin-left:auto;flex-wrap:wrap}
.ficha{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:20px;align-items:start}
.ficha-esq{display:flex;flex-direction:column;gap:14px;min-width:0}
.ficha-dir{display:flex;flex-direction:column;gap:14px}
.cabeca{padding:24px 26px}
.cabeca .chips{display:flex;align-items:center;gap:9px;margin-bottom:11px;flex-wrap:wrap}
.cabeca .ref{font:500 11px/1 var(--mono);color:var(--t4)}
.cabeca h2{margin:0 0 6px;font:700 22px/1.3 var(--sans);color:var(--azul);
 letter-spacing:-.4px;text-wrap:pretty}
.cabeca .ent{font:400 13px/1.4 var(--sans);color:#6e747c;margin-bottom:20px}
.cabeca .ent a{color:var(--azul)}
.cabeca .ent a:hover{text-decoration:underline}
.factos{display:flex;flex-wrap:wrap;gap:1px;background:var(--linha);
 border:1px solid var(--linha);border-radius:9px;overflow:hidden}
.facto{background:var(--creme);padding:13px 16px;flex:1 1 30%;min-width:0}
.facto .k{font:500 9.5px/1 var(--sans);color:var(--t5);text-transform:uppercase;
 letter-spacing:.08em}
.facto .v{font:600 13px/1.4 var(--sans);color:var(--ink);margin-top:6px}
.facto.larg{flex:1 1 100%}
.facto .v.ok{color:var(--verde)}
.facto .v.mau{color:var(--verm)}
.modos{display:flex;align-items:center;gap:8px}
.modos .r{font:400 11.5px/1 var(--sans);color:var(--t5)}
.modos a{padding:7px 13px;border-radius:7px;font:600 12px/1 var(--sans);
 background:#fff;color:var(--t3);border:1px solid var(--linha)}
.modos a.on{background:var(--ink);color:#fff;border-color:var(--ink)}
.modos .dir{margin-left:auto;font:400 11.5px/1 var(--sans);color:var(--t5)}
details.sec{overflow:hidden;background:#fff;border:1px solid var(--linha);
 border-radius:11px;box-shadow:0 1px 2px rgba(0,0,0,.06)}
details.sec>summary{cursor:pointer;display:flex;align-items:center;gap:10px;
 padding:15px 22px;list-style:none}
details.sec>summary::-webkit-details-marker{display:none}
details.sec>summary::before{content:'\25B8';font:500 11px/1 var(--mono);color:var(--t5)}
details.sec[open]>summary::before{content:'\25BE'}
details.sec .st{font:600 11.5px/1 var(--sans);color:var(--ink);
 text-transform:uppercase;letter-spacing:.07em}
details.sec .sh{margin-left:auto;font:400 11.5px/1 var(--sans);color:var(--t5);
 white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:45%}
details.sec dl{margin:0;padding:2px 22px 20px}
details.sec .par{display:grid;grid-template-columns:210px minmax(0,1fr);gap:18px;
 padding:10px 0;border-top:1px solid var(--papel)}
details.sec dt{font:400 12.5px/1.45 var(--sans);color:var(--t4)}
details.sec dd{margin:0;font:500 12.5px/1.5 var(--sans);color:var(--ink);
 white-space:pre-line;text-wrap:pretty;word-break:break-word}
.essencial dl{margin:0;padding:6px 22px 18px}
.essencial .par{display:grid;grid-template-columns:230px minmax(0,1fr);
 gap:18px;padding:11px 0;border-top:1px solid var(--papel)}
.essencial .par:first-child{border-top:0}
.essencial dt{font:400 12.5px/1.45 var(--sans);color:var(--t4)}
.essencial dd{margin:0;font:600 13px/1.5 var(--sans);color:var(--ink);
 text-wrap:pretty;word-break:break-word;white-space:pre-line}
.em-falta{font-weight:400;color:var(--t6);font-style:italic}
.nota-campo{display:block;margin-top:3px;font:400 11.5px/1.45 var(--sans);
 color:var(--t5)}
.a-trazer{color:var(--azul)}
.a-trazer::before{content:'';display:inline-block;width:7px;height:7px;
 border-radius:50%;background:var(--azul);margin-right:7px;
 animation:pulsa 1s ease-in-out infinite}
@keyframes pulsa{0%,100%{opacity:1}50%{opacity:.25}}
.prazo-cx{background:var(--ink);border-radius:11px;padding:22px;color:#fff}
.prazo-cx .r{font:500 10px/1 var(--sans);color:rgba(255,255,255,.5);
 text-transform:uppercase;letter-spacing:.1em}
.prazo-cx .d{font:700 30px/1 var(--mono);margin:10px 0 4px;letter-spacing:-1.5px}
.prazo-cx .n{font:400 12.5px/1.4 var(--sans);color:rgba(255,255,255,.6)}
.barra-prazo{height:5px;border-radius:3px;background:rgba(255,255,255,.15);
 margin-top:16px;overflow:hidden}
.barra-prazo i{display:block;height:100%;background:var(--coral)}
.lado-cx{padding:20px}
.lado-cx .cab{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.docs{display:flex;flex-direction:column;gap:2px;margin-top:8px}
.doc{display:flex;align-items:center;gap:10px;padding:9px 0;
 border-top:1px solid var(--papel)}
.doc a{font:500 12.5px/1.35 var(--sans);min-width:0;overflow:hidden;
 text-overflow:ellipsis;white-space:nowrap}
.doc .t{margin-left:auto;flex:none;font:400 11px/1 var(--mono);color:var(--t5)}
.resp{display:flex;align-items:center;gap:9px;padding:9px 12px;
 border:1px solid var(--linha);border-radius:8px;background:var(--creme)}
.resp .av{width:24px;height:24px;border-radius:50%;background:#e6e2da;flex:none;
 font:600 9.5px/24px var(--sans);color:#5c6169;text-align:center}
.resp input{flex:1;min-width:0;border:0;background:transparent;
 font:500 12.5px/1.4 var(--sans);color:var(--ink)}
.resp input:focus{outline:none}
.resp button{background:none;border:0;color:var(--t5);cursor:pointer;
 font:400 11.5px/1 var(--sans);flex:none}
.resp button:hover{color:var(--ink)}
.hist{display:flex;gap:10px;align-items:baseline;padding:9px 0;
 border-top:1px solid var(--papel)}
.hist .t{font:400 12px/1.4 var(--sans);color:var(--t2);min-width:0}
.hist .q{margin-left:auto;flex:none;font:400 10.5px/1 var(--mono);color:var(--t5)}

/* quadro */
.quadro-topo{display:flex;align-items:center;gap:10px;margin-bottom:16px;flex-wrap:wrap}
.quadro-topo .d{font:400 12.5px/1 var(--sans);color:var(--t4)}
.quadro-topo form{margin-left:auto;display:flex;gap:8px}
.quadro-topo input{padding:8px 12px;border:1px solid var(--linha);border-radius:7px;
 background:#fff;font:400 12.5px/1.2 var(--sans)}
.quadro{display:flex;gap:14px;align-items:flex-start;overflow-x:auto;padding-bottom:14px}
.coluna{flex:none;width:282px;background:var(--linha2);border:1px solid var(--linha);
 border-radius:8px;padding:12px}
.coluna-cab{display:flex;align-items:center;gap:8px;margin-bottom:12px}
.coluna-cab form{flex:1;min-width:0}
.fase-nome{border:0;background:transparent;font:600 12.5px/1.2 var(--sans);
 color:var(--ink);width:100%;padding:2px}
.fase-nome:focus{outline:none;background:#fff;border-radius:4px}
.coluna-conta{font:600 10.5px/1 var(--mono);color:var(--t4)}
.fase-apagar{background:none;border:0;color:var(--t6);cursor:pointer;
 font:500 14px/1 var(--sans);padding:0 2px}
.fase-apagar:hover{color:var(--verm)}
.coluna-corpo{display:flex;flex-direction:column;gap:9px;min-height:60px}
.coluna-corpo.sobre{outline:2px dashed #cfcabd;outline-offset:3px;border-radius:6px}
.coluna-vazia{padding:16px 9px;border:1px dashed #cfcabd;border-radius:6px;
 text-align:center;font:400 11.5px/1.4 var(--sans);color:var(--t5)}
.carta{background:#fff;border:1px solid var(--linha);border-radius:6px;padding:13px;
 box-shadow:0 1px 2px rgba(0,0,0,.06);cursor:grab}
.carta.arrastando{opacity:.4}
.carta-titulo{font:700 13px/1.35 var(--sans);color:var(--azul);text-wrap:pretty;
 display:block}
.carta-entidade{font:400 11.5px/1.35 var(--sans);color:var(--t4);margin-top:5px}
.carta-meta{display:flex;align-items:center;gap:9px;margin-top:9px;flex-wrap:wrap}
.carta-preco{font:600 11.5px/1 var(--mono);color:var(--t2)}
.carta-etq{display:flex;flex-wrap:wrap;gap:5px;margin-top:10px;align-items:center}
.etq{display:flex;align-items:center;gap:5px;padding:3px 7px;border-radius:4px;
 color:#fff;font:600 10.5px/1.3 var(--sans)}
.etq form.accao{display:inline-flex}
button.etq-x{background:none;border:0;color:#fff;opacity:.6;cursor:pointer;
 padding:0;font-size:12px;line-height:1}
button.etq-x:hover{opacity:1}
button.tirar{background:none;border:0;padding:0;cursor:pointer;
 font:400 11px/1 var(--sans);color:var(--t6)}
button.tirar:hover{color:var(--verm)}
.etq-form input{padding:3px 7px;border-radius:4px;border:1px dashed #cfcabd;
 background:transparent;font:500 10.5px/1.3 var(--sans);color:var(--t5);width:78px}
.etq-form input:focus{outline:none;border-style:solid;border-color:var(--azul)}
.carta-pe{display:flex;align-items:center;margin-top:11px;padding-top:9px;
 border-top:1px solid var(--papel)}
.carta-pe a{font:400 11px/1 var(--sans);color:var(--t6)}
.carta-pe a:hover{color:var(--verm)}
.carta-pe .av{margin-left:auto;width:20px;height:20px;border-radius:50%;
 background:#e6e2da;font:600 9px/20px var(--sans);color:#5c6169;text-align:center}

/* calendario */
.grade-caixa{background:#fff;border:1px solid var(--linha);border-radius:8px;
 overflow:hidden;box-shadow:0 1px 2px rgba(0,0,0,.06)}
.grade-rolo{overflow-x:auto}
.linha-grade{display:grid;border-bottom:1px solid var(--papel);align-items:center;
 min-width:max-content}
.linha-grade.cab{background:var(--creme);border-bottom:1px solid var(--linha)}
.cel-titulo{padding:13px 16px;position:sticky;left:0;background:#fff;z-index:2;
 border-right:1px solid var(--linha2);min-width:0}
.linha-grade.cab .cel-titulo{background:var(--creme);
 font:600 10px/1 var(--sans);color:var(--t5);text-transform:uppercase;
 letter-spacing:.09em;padding:11px 16px}
.cel-titulo a{font:600 12.5px/1.3 var(--sans);display:block;white-space:nowrap;
 overflow:hidden;text-overflow:ellipsis}
.cel-titulo .ent{font:400 11px/1.3 var(--sans);color:var(--t5);margin-top:3px;
 white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cel-dia{padding:8px 0;text-align:center;border-left:1px solid var(--linha2)}
.cel-dia .s{font:500 9px/1.2 var(--sans);color:var(--t6);text-transform:lowercase}
.cel-dia .n{font:600 11px/1.2 var(--mono);color:var(--t4)}
.cel-dia .m{font:400 9px/1.3 var(--sans);color:var(--t6);text-transform:uppercase}
.cel-dia.fds{background:#f1efe9}
.cel-dia.fds .s,.cel-dia.fds .n{color:var(--t5)}
.cel-dia.mes-novo{border-left:2px solid var(--linha)}
.cel-dia.hoje{background:#eef4fa}
.cel-dia.hoje .n,.cel-dia.hoje .s{color:var(--azul);font-weight:700}
.cel-pilula{padding:4px 3px}
.pilula{display:block;padding:6px 4px;border-radius:5px;font:600 9.5px/1.2 var(--sans);
 text-align:center;white-space:nowrap;overflow:hidden}

/* indicadores */
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
.kpi{background:#fff;border:1px solid var(--linha);border-radius:8px;padding:20px;
 box-shadow:0 1px 2px rgba(0,0,0,.06)}
.kpi .r{font:500 10px/1 var(--sans);color:var(--t5);text-transform:uppercase;
 letter-spacing:.09em}
.kpi .v{font:700 30px/1 var(--mono);color:var(--ink);letter-spacing:-1.5px;margin:12px 0 6px}
.kpi .d{font:500 11.5px/1.4 var(--sans);color:var(--t4)}
.ind-grelha{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:14px;
 align-items:start}
.barras{display:flex;align-items:flex-end;gap:16px;height:180px}
.barras .col{flex:1;display:flex;flex-direction:column;align-items:center;gap:9px;
 height:100%;justify-content:flex-end}
.barras .v{font:600 12px/1 var(--mono);color:var(--ink)}
.barras .b{width:100%;border-radius:4px 4px 0 0}
.barras .l{font:400 11px/1.2 var(--sans);color:var(--t4);text-align:center}
.saude{display:flex;flex-direction:column;gap:12px}
.saude .l{display:flex;align-items:center;gap:10px}
.saude .t{font:400 12px/1.4 var(--sans);color:var(--t2);min-width:0}
.saude .v{margin-left:auto;flex:none;font:600 11.5px/1 var(--mono);color:var(--ink)}
.aviso-prop{padding:12px 16px;border:1px dashed #cfcabd;border-radius:8px;
 font:400 12px/1.5 var(--sans);color:var(--t4)}

@media (max-width:1100px){
 .ficha{grid-template-columns:minmax(0,1fr)}
 .kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
 .ind-grelha{grid-template-columns:minmax(0,1fr)}
}
"""


BASE = """<!doctype html><html lang="pt"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(titulo_aba)s</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>%(css)s</style></head><body>
<div class="app">
<aside>
 <div class="marca">
  <div class="logo">Radar<span>DR</span></div>
  <div class="sub">%(fontes)s</div>
  <div class="meta">localhost:%(porta)d &middot; %(acervo)s</div>
 </div>
 <nav>%(nav)s</nav>
 <div class="caixa">
  <div class="r">Verificação automática</div>
  <div class="h">%(horas)s</div>
  <div class="n">%(ultima)s</div>
 </div>
 <div class="sou">
  <div class="r">Sou</div>
  <form method="post" action="/sou">
   <div class="av">%(iniciais)s</div>
   <input type="text" name="nome" value="%(quem)s" list="pessoas" placeholder="o teu nome">
   <button type="submit">mudar</button>
  </form>
 </div>
</aside>
<main>
 <div class="topo">
  <div class="migalhas">
   <div class="b">%(migalhas)s</div>
   <div class="accoes-topo">%(accoes_topo)s</div>
  </div>
  <h1 class="tit">%(titulo)s</h1>
  <p class="subtit">%(subtitulo)s</p>
  %(abas)s
 </div>
 <div class="corpo">%(aviso)s%(conteudo)s</div>
</main>
</div>
<datalist id="pessoas">%(lista_pessoas)s</datalist>
%(script)s
</body></html>"""

# (chave da vista, etiqueta, destino). A rota deixou de aparecer ao lado
# do nome: era ruido de programador num painel que e para trabalhar.
NAV = (("anuncios", "Anúncios", "/"),
       ("alertas", "Alertas", "/alertas"),
       ("contratos", "Contratos", "/contratos"),
       ("quadro", "Quadro", "/quadro"),
       ("calendario", "Calendário", "/calendario"),
       ("indicadores", "Indicadores", "/indicadores"))


def migalhas_de(vista, folha=""):
    """As migalhas de uma pagina, a partir do separador em que ela vive.

    Os separadores sao irmaos, nao filhos dos anuncios: antes, todas as
    paginas comecavam por "Anúncios ›", o que punha os contratos, o
    quadro e os indicadores dentro da lista de anuncios. Cada pagina
    comeca agora no seu separador, e so as fichas e que penduram uma
    folha por baixo dele.
    """
    for chave, etiqueta, destino in NAV:
        if chave == vista:
            if not folha:
                return "<em>%s</em>" % html.escape(etiqueta)
            return ("<a href='%s'>%s</a><s>&rsaquo;</s><em>%s</em>"
                    % (destino, html.escape(etiqueta), html.escape(folha)))
    return "<em>%s</em>" % html.escape(folha or "Radar")


def accao(destino, etiqueta, classe="bt", confirmar=""):
    """Um botao que faz POST. Tudo o que altera dados passa por aqui:
    como <a href> isto respondia a um prefetch do browser ou a qualquer
    coisa que siga links, e ha aqui accoes que mudam a base."""
    ao_submeter = (" onsubmit=\"return confirm('%s')\"" % confirmar) if confirmar else ""
    return ("<form class='accao' method='post' action='%s'%s>"
            "<button type='submit' class='%s'>%s</button></form>"
            % (destino, ao_submeter, classe, etiqueta))


def _iniciais(nome):
    partes = [p for p in (nome or "").split() if p]
    if not partes:
        return "&mdash;"
    if len(partes) == 1:
        return html.escape(partes[0][:2].upper())
    return html.escape((partes[0][0] + partes[-1][0]).upper())


def envolver(activo, titulo, subtitulo, conteudo, migalhas="",
             abas="", script="", titulo_aba=None):
    """Monta uma pagina completa a partir do esqueleto partilhado."""
    cfg = ler_config()
    with liga() as c:
        total = c.execute("SELECT COUNT(*) n FROM anuncios").fetchone()["n"]
    quem = quem_sou()

    itens = []
    for chave, etiqueta, destino in NAV:
        itens.append("<a class='%s' href='%s'><b>%s</b></a>"
                     % ("on" if chave == activo else "", destino,
                        html.escape(etiqueta)))

    mensagem = le_marca("ultima_mensagem", "ainda não verificou")
    quando = le_marca("ultima_verificacao", "nunca")
    ultima = ("última: %s &mdash; %s" % (html.escape(quando), html.escape(mensagem))
              if quando != "nunca" else "ainda não verificou")

    if not migalhas:
        migalhas = migalhas_de(activo)

    # Aviso de uma accao acabada de fazer, passado no proprio
    # redireccionamento. Nao vai para a base: e da vez, nao do sistema --
    # e assim nao se confunde "peças trazidas" com "verificação correu bem".
    texto_aviso = (request.args.get("aviso") or "").strip()
    aviso = ("<div class='flash'>%s</div>" % html.escape(texto_aviso)) \
        if texto_aviso else ""

    # O aviso que faltava. Sem as tarefas do Windows, o radar so recolhe
    # com o painel aberto -- e como o relogio interno recupera os slots
    # falhados, a tabela `slots` fica preenchida e parece que correu a
    # horas. Foi assim que isto passou semanas sem se notar. E aviso do
    # sistema e nao da vez, por isso nao vai pela query string.
    faltam = tarefas_em_falta()
    if faltam:
        aviso += (
            "<div class='flash mau'>O radar <b>não está a verificar "
            "sozinho</b>: %s por criar no Agendador do Windows. Enquanto "
            "assim for, só recolhe quando este painel está aberto. Corre "
            "o <code>agendar.bat</code> uma vez.</div>"
            % ("a tarefa &ldquo;%s&rdquo; está" % html.escape(faltam[0])
               if len(faltam) == 1
               else "as tarefas %s estão"
               % " e ".join("&ldquo;%s&rdquo;" % html.escape(t)
                            for t in faltam)))

    n_corpus = ha_corpus()
    return BASE % {
        "titulo_aba": html.escape(titulo_aba or titulo),
        "css": CSS, "porta": PORTA,
        # A aplicacao passou a ter duas fontes e o cabecalho so falava
        # do DR: num separador de contratos, dizer "parte L" e mentira.
        "fontes": ("Anúncios do DR &middot; contratos do BASE" if n_corpus
                   else "DR II série &middot; parte L"),
        "acervo": ("%s anúncios &middot; %s contratos"
                   % (mil_pt(total), mil_pt(n_corpus)) if n_corpus
                   else "%s anúncios" % mil_pt(total)),
        "nav": "".join(itens),
        "horas": " &middot; ".join(cfg["horas_verificacao"]),
        "ultima": ultima,
        "iniciais": _iniciais(quem),
        "quem": html.escape(quem, quote=True),
        "migalhas": migalhas,
        "titulo": html.escape(titulo),
        "subtitulo": subtitulo,
        "conteudo": conteudo,
        "abas": abas or "<div class='vazio-topo'></div>",
        "aviso": aviso,
        # "Verificar agora" vai ao DR buscar anuncios: so faz sentido
        # onde os anuncios estao. Nos contratos aparecia ao lado do
        # "Actualizar contratos" a dizer outra coisa parecida, e nos
        # indicadores nao dizia nada.
        "accoes_topo": (accao("/verificar", "Verificar agora")
                        if activo in ("anuncios", "quadro", "calendario")
                        else ""),
        "lista_pessoas": "".join("<option value='%s'>" % html.escape(n, quote=True)
                                 for n in listar_pessoas()),
        "script": script,
    }


# Tecto do CSV de contratos. Um filtro largo pode apanhar centenas de
# milhares de linhas, e a folha de calculo do outro lado tambem tem
# limites -- mais vale um ficheiro que abre do que um que rebenta.
TECTO_CSV = 50000

# Quantas linhas a lista mostra de uma vez. E um limite de apresentacao,
# nao da base: o filtro apanha o que apanhar, a pagina mostra 20 e o
# resto alcanca-se pelo paginador.
POR_PAGINA = 20

MESES = ("jan", "fev", "mar", "abr", "mai", "jun",
         "jul", "ago", "set", "out", "nov", "dez")
# indexado por date.weekday(): 0 = segunda. Iniciais soltas nao servem
# em portugues -- segunda/sexta/sabado e quarta/quinta repetem-se.
DIAS_SEMANA = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")


def conta_dias(dias):
    """'hoje', 'amanhã', '1 dia', 'N dias' -- com concordancia."""
    if dias <= 0:
        return "termina hoje"
    if dias == 1:
        return "amanhã"
    return "%d dias" % dias


def etiqueta_prazo(prazo):
    """(texto, classe) para o distintivo de prazo. Verde folgado, amarelo
    a menos de uma semana, vermelho expirado ou a acabar hoje."""
    dias, passou = dias_restantes(prazo)
    if dias is None:
        return "", ""
    if passou:
        return "prazo expirado", "mau"
    if dias == 0:
        return "termina hoje", "mau"
    return conta_dias(dias), ("avisa" if dias <= 7 else "ok")


def linha(a):
    try:
        data = datetime.strptime(a["data_pub"], "%Y-%m-%d")
        data_html = ("<div class='dia'>%02d</div><div class='mes'>%s</div>"
                     % (data.day, MESES[data.month - 1]))
    except ValueError:
        data_html = "<div class='dia'>&mdash;</div>"

    tags = []
    if a["cpv"]:
        tags.append("<span class='tag mono'>%s</span>" % html.escape(a["cpv"]))
    if a["plataforma"]:
        # verde quando dela se conseguem trazer as peças, cinzento quando
        # e preciso ir la a mao
        tags.append("<span class='tag %s'>%s</span>"
                    % ("ok" if a["plataforma"] in PLATAFORMAS_COM_PECAS else "",
                       html.escape(a["plataforma"])))
    if a["tipo"]:
        tags.append("<span class='tag'>%s</span>" % html.escape(a["tipo"]))
    texto_prazo, classe_prazo = etiqueta_prazo(a["prazo"])
    if texto_prazo:
        tags.append("<span class='tag %s'>%s</span>" % (classe_prazo, texto_prazo))
    rotulo_estado = {"novo": "por ver", "interessa": "interessa",
                     "descartado": "descartado"}.get(a["estado"], a["estado"])
    classe_estado = {"interessa": "ok", "descartado": ""}.get(a["estado"], "info")
    tags.append("<span class='tag %s'>%s</span>" % (classe_estado, rotulo_estado))

    preco = ("<div class='item-preco'>%s</div>" % html.escape(a["preco_base"])) \
        if a["preco_base"] else ""

    return (
        "<div class='item'>"
        "<div class='item-data'>%s</div>"
        "<div class='item-corpo'>"
        "<a href='/anuncio/%s' class='item-titulo'>%s</a>"
        "<div class='item-entidade'>%s</div>"
        "<div class='item-meta'>%s</div></div>"
        "<div class='item-lado'>%s<div class='item-accoes'>%s%s</div></div></div>"
        % (data_html, a["ref"], html.escape((a["titulo"] or "")[:190]),
           html.escape(a["entidade"] or ""), "".join(tags), preco,
           accao("/estado/%s/interessa" % a["ref"], "interessa", "mini verde"),
           accao("/estado/%s/descartado" % a["ref"], "descartar", "mini")))


ARVORE_JS = """<script>
var ARV_DADOS = null, ARV_SEL = new Set(), ARV_FILHOS = {}, ARV_CHK = {};

function arvoreCarregar() {
  if (ARV_DADOS) return;
  // de onde se conta vem no proprio <details>: nos anuncios conta
  // anuncios, nos contratos conta contratos
  var de = document.querySelector('details.arvore').dataset.de || 'anuncios';
  fetch('/cpv.json?de=' + de).then(function(r) { return r.json(); }).then(function(dados) {
    ARV_DADOS = dados;
    arvoreConstruir(dados);
  }).catch(function() {
    document.getElementById('arvore-corpo').textContent = 'falhou a carregar.';
  });
}

function nivelSignificativo(cod) {
  var i = 8;
  while (i > 2 && cod[i - 1] === '0') i--;
  return i;
}

function arvoreConstruir(dados) {
  var porCodigo = {}, filhos = {}, raizes = [];
  dados.forEach(function(d) { porCodigo[d.codigo8] = d; });
  dados.forEach(function(d) {
    var nivel = nivelSignificativo(d.codigo8), pai = null;
    for (var L = nivel - 1; L >= 2; L--) {
      var candidato = d.codigo8.slice(0, L) + '0'.repeat(8 - L);
      if (candidato !== d.codigo8 && porCodigo[candidato]) { pai = candidato; break; }
    }
    if (pai) { (filhos[pai] = filhos[pai] || []).push(d.codigo8); }
    else { raizes.push(d.codigo8); }
  });
  raizes.sort();
  Object.keys(filhos).forEach(function(k) { filhos[k].sort(); });
  ARV_FILHOS = filhos;

  var total = {};
  function acumula(cod) {
    if (cod in total) return total[cod];
    var soma = porCodigo[cod].n;
    (filhos[cod] || []).forEach(function(f) { soma += acumula(f); });
    total[cod] = soma;
    return soma;
  }
  raizes.forEach(acumula);
  Object.keys(filhos).forEach(function(k) { filhos[k].forEach(acumula); });

  var corpo = document.getElementById('arvore-corpo');
  corpo.innerHTML = '';
  raizes.forEach(function(cod) { corpo.appendChild(arvoreNo(cod, porCodigo, filhos, total)); });
  document.getElementById('arvore-contagem').textContent =
      dados.length + ' códigos, ' + raizes.length + ' divisões';
  arvoreMarcarSemeados();
}

function arvoreMarcarSemeados() {
  // Poe as caixas de acordo com o filtro que ja esta em uso. Sem isto a
  // arvore abria em branco por cima de um filtro cheio de CPV -- e como
  // "Aplicar" escreve o que a arvore tem, aplicar limpava o filtro.
  ARV_SEL.forEach(function(cod) {
    if (!ARV_CHK[cod]) return;
    ARV_CHK[cod].checked = true;
    arvoreDescendentes(cod).forEach(function(f) {
      if (ARV_CHK[f]) ARV_CHK[f].checked = true;
    });
    // abrir os antepassados: marcado dentro de um <details> fechado nao
    // se ve, e o que nao se ve parece nao estar la
    var no = ARV_CHK[cod].closest('.no-envolve');
    while (no) {
      if (no.tagName === 'DETAILS') no.open = true;
      no = no.parentElement ? no.parentElement.closest('.no-envolve') : null;
    }
  });
}

function arvoreSemear() {
  // O filtro em uso e a verdade de onde a arvore parte. Guarda-se tudo o
  // que la esta, ate o que nao e codigo (o filtro tambem aceita palavras):
  // assim "Aplicar" nao deita fora o que a arvore nao sabe desenhar.
  var campo = document.getElementById('filtro-cpv');
  if (!campo) return;
  campo.value.split('|').forEach(function(p) {
    p = p.trim();
    if (p) ARV_SEL.add(p);
  });
  arvoreChip();
}

function arvoreNo(cod, porCodigo, filhos, total) {
  var item = porCodigo[cod], temFilhos = filhos[cod] && filhos[cod].length;
  var det = document.createElement(temFilhos ? 'details' : 'div');
  det.className = 'no-envolve';
  det.dataset.codigo8 = cod;
  det.dataset.texto = (cod + ' ' + item.descricao).toLowerCase();
  var resumo = document.createElement(temFilhos ? 'summary' : 'div');
  resumo.className = 'no';
  var chk = document.createElement('input');
  chk.type = 'checkbox';
  chk.addEventListener('click', function(e) { e.stopPropagation(); });
  chk.addEventListener('change', function() { arvoreMudou(cod, chk.checked); });
  resumo.appendChild(chk);
  ARV_CHK[cod] = chk;
  var cs = document.createElement('span');
  cs.className = 'cod'; cs.textContent = cod;
  resumo.appendChild(cs);
  var ls = document.createElement('span');
  ls.className = 'lbl'; ls.textContent = item.descricao;
  resumo.appendChild(ls);
  var ns = document.createElement('span');
  ns.className = 'n'; ns.textContent = '(' + total[cod] + ')';
  resumo.appendChild(ns);
  det.appendChild(resumo);
  if (temFilhos) {
    filhos[cod].forEach(function(f) { det.appendChild(arvoreNo(f, porCodigo, filhos, total)); });
  }
  return det;
}

function arvoreDescendentes(cod) {
  var fora = [];
  (ARV_FILHOS[cod] || []).forEach(function(f) {
    fora.push(f);
    fora = fora.concat(arvoreDescendentes(f));
  });
  return fora;
}

function arvoreMudou(cod, marcado) {
  // ARV_SEL guarda so o que foi marcado directamente: o filtro ja apanha
  // os descendentes com o codigo do grupo (zeros a direita tirados no
  // servidor), nao vale a pena mandar cada um na URL.
  if (marcado) { ARV_SEL.add(cod); } else { ARV_SEL.delete(cod); }
  // as caixas dos descendentes marcam-se so para se ver o que ficou
  // incluido; .checked por script nao dispara 'change'
  arvoreDescendentes(cod).forEach(function(f) {
    if (ARV_CHK[f]) { ARV_CHK[f].checked = marcado; }
  });
  arvoreChip();
}

function arvoreChip() {
  var chip = document.getElementById('arvore-chip');
  if (!chip) return;
  var n = ARV_SEL.size;
  chip.textContent = n ? (n + (n === 1 ? ' seleccionado' : ' seleccionados'))
                       : 'nenhum seleccionado';
}

function arvoreAplicar() {
  var campo = document.getElementById('filtro-cpv');
  campo.value = Array.from(ARV_SEL).join('|');
  campo.form.submit();
}

function arvoreLimpar() {
  ARV_SEL.clear();
  document.querySelectorAll('#arvore-corpo input[type=checkbox]').forEach(
      function(c) { c.checked = false; });
  arvoreChip();
}

function arvoreFiltra(no, alvo) {
  if (!alvo) { no.classList.remove('escondido'); return true; }
  var acha = no.dataset.texto.indexOf(alvo) >= 0, algumFilho = false;
  Array.from(no.children).forEach(function(filho) {
    if (filho.dataset && filho.dataset.codigo8) {
      if (arvoreFiltra(filho, alvo)) algumFilho = true;
    }
  });
  var mostra = acha || algumFilho;
  no.classList.toggle('escondido', !mostra);
  if (no.tagName === 'DETAILS' && algumFilho) no.open = true;
  return mostra;
}

document.querySelector('details.arvore').addEventListener('toggle', function() {
  if (this.open) arvoreCarregar();
});
document.getElementById('arvore-busca').addEventListener('input', function() {
  var alvo = this.value.trim().toLowerCase();
  Array.from(document.getElementById('arvore-corpo').children).forEach(
      function(no) { arvoreFiltra(no, alvo); });
});
arvoreSemear();
</script>"""


def pagina_pedida(args):
    """Le ?pag= sem rebentar com lixo na URL. Fora do sitio, e a 1."""
    try:
        return int(args.get("pag", 1))
    except (TypeError, ValueError):
        return 1


def args_da_lista(args, **muda):
    """Os argumentos da lista de agora, sem os que sao da vez. O que vem
    em `muda` entra depois da limpeza -- e assim que o paginador pode pedir
    uma pagina sem que ela seja apagada a seguir."""
    novos = args.to_dict()
    for campo in CAMPOS_DA_VEZ:
        novos.pop(campo, None)
    novos.update(muda)
    return novos


def sem_pagina(args, **muda):
    """Liga da lista com os filtros de agora. Mexer num filtro volta a
    pagina 1: a pagina 7 do filtro anterior nao existe no novo."""
    novos = args_da_lista(args, **muda)
    return "/?" + urlencode(novos) if novos else "/"


def paginador(pagina, paginas, args, base="/"):
    """Barra de paginas. Mostra uma janela a volta da actual em vez de
    todas -- com 65 mil anuncios sao 3300 paginas e nao cabem na linha.

    O `base` e a rota que se pagina: a mesma barra serve os anuncios e os
    contratos, que sao listas diferentes com filtros diferentes."""
    if paginas <= 1:
        return ""

    def liga_pag(n, etiqueta=None, classe=""):
        args_n = args_da_lista(args, pag=str(n))
        return ("<a class='%s' href='%s?%s'>%s</a>"
                % (classe, base, urlencode(args_n), etiqueta or n))

    pecas = []
    pecas.append(liga_pag(pagina - 1, "&larr; anterior")
                 if pagina > 1
                 else "<span class='morto'>&larr; anterior</span>")

    # janela de duas paginas para cada lado, com a primeira e a ultima
    # sempre presentes -- e delas que se salta para as pontas
    janela = {1, paginas}
    janela.update(range(max(1, pagina - 2), min(paginas, pagina + 2) + 1))
    anterior = 0
    for n in sorted(janela):
        if n - anterior > 1:
            pecas.append("<span class='corte'>&hellip;</span>")
        pecas.append("<b class='on'>%d</b>" % n if n == pagina
                     else liga_pag(n))
        anterior = n

    pecas.append(liga_pag(pagina + 1, "seguinte &rarr;")
                 if pagina < paginas
                 else "<span class='morto'>seguinte &rarr;</span>")
    return "<div class='paginas'>" + "".join(pecas) + "</div>"


@app.route("/")
def painel():
    onde, valores = condicoes(request.args)
    with liga() as c:
        # Com paginas de 20 a contagem deixa de ser dispensavel: e ela que
        # diz quantas paginas ha. Faz-se sempre, antes da consulta das
        # linhas, para se poder segurar a pagina pedida dentro do que
        # existe -- pedir a pagina 900 de 12 devolvia uma lista vazia.
        correspondem = c.execute("SELECT COUNT(*) n FROM anuncios" + onde,
                                 valores).fetchone()["n"]
        paginas = max(1, -(-correspondem // POR_PAGINA))
        pagina = min(max(1, pagina_pedida(request.args)), paginas)
        linhas = c.execute("SELECT * FROM anuncios" + onde +
                           " ORDER BY data_pub DESC, ref DESC LIMIT ? OFFSET ?",
                           valores + [POR_PAGINA,
                                      (pagina - 1) * POR_PAGINA]).fetchall()
        contas = {e: c.execute("SELECT COUNT(*) n FROM anuncios WHERE estado=?",
                               (e,)).fetchone()["n"]
                  for e in ("novo", "interessa", "descartado")}
        total = c.execute("SELECT COUNT(*) n FROM anuncios").fetchone()["n"]
        porler = c.execute("SELECT COUNT(*) n FROM anuncios "
                           "WHERE detalhe_lido=0").fetchone()["n"]
        n_cpv = c.execute("SELECT COUNT(*) n FROM cpv_dict").fetchone()["n"]
        plataformas = c.execute(
            "SELECT COALESCE(NULLIF(plataforma,''),?) p, COUNT(*) n "
            "FROM anuncios WHERE detalhe_lido=1 GROUP BY p ORDER BY n DESC",
            (SEM_PLATAFORMA,)).fetchall()

    mil = mil_pt

    estado_actual = request.args.get("estado", "novo")
    abas = ["<div class='abas'>"]
    for valor, etiqueta, quantos in (("novo", "Por ver", contas["novo"]),
                                     ("interessa", "Interessa", contas["interessa"]),
                                     ("descartado", "Descartados", contas["descartado"]),
                                     ("", "Todos", total)):
        abas.append("<a class='%s' href='%s'>%s <i>%s</i></a>"
                    % ("on" if valor == estado_actual else "",
                       sem_pagina(request.args, estado=valor),
                       etiqueta, mil(quantos)))
    abas.append("</div>")

    cpv_actual = request.args.get("cpv", "")
    if cpv_actual:
        faixa_cpv = ("<div class='cpv-activo'>Filtro CPV activo: <b>%s</b>"
                     "<a href='%s'>tirar</a></div>"
                     % (html.escape(cpv_actual),
                        sem_pagina(request.args, cpv="")))
    else:
        faixa_cpv = ""

    # A plataforma decide se as peças se conseguem trazer, por isso vale
    # a pena poder isolá-la -- ver só acingov/vortal/compraspt é ver o que
    # dá para trabalhar sem ir ao site.
    plat_actual = (request.args.get("plat") or "").strip()
    opcoes_plat = ["<option value=''>todas as plataformas</option>"]
    for r in plataformas:
        opcoes_plat.append(
            "<option value='%s'%s>%s (%s)</option>"
            % (html.escape(r["p"], quote=True),
               " selected" if r["p"] == plat_actual else "",
               html.escape(r["p"]), mil(r["n"])))

    filtros = (
        "<form class='cx filtros' method='get' action='/'>"
        "<input type='text' name='q' value='%s' placeholder='Nome do concurso ou objecto…'>"
        "<input type='text' name='ent' value='%s' placeholder='Entidade adjudicante…'>"
        "<input type='hidden' id='filtro-cpv' name='cpv' value='%s'>"
        "<select name='plat'>%s</select>"
        "<label>de</label><input type='date' name='de' value='%s'>"
        "<label>até</label><input type='date' name='ate' value='%s'>"
        "<input type='hidden' name='estado' value='%s'>"
        "<button type='submit'>Filtrar</button>"
        "<a class='limpar' href='/'>limpar</a>"
        "</form>"
        % (html.escape(request.args.get("q", ""), quote=True),
           html.escape(request.args.get("ent", ""), quote=True),
           html.escape(cpv_actual, quote=True),
           "".join(opcoes_plat),
           html.escape(request.args.get("de", ""), quote=True),
           html.escape(request.args.get("ate", ""), quote=True),
           html.escape(estado_actual, quote=True)))

    caixa_guardados = caixa_de_filtros(request.args, "anuncios")

    arvore = arvore_html(n_cpv, "anuncios")

    if linhas:
        corpo_lista = "<div class='lista'>" + "".join(linha(a) for a in linhas) + "</div>"
    else:
        corpo_lista = ("<div class='vazio'>Nada corresponde a este filtro. "
                       "<a href='/'>limpar</a></div>")

    # a pagina mostra 20; a contagem tem de dizer quantos o filtro apanhou
    # mesmo, senao "20 de 65 869" parece um filtro que nao filtrou nada
    if correspondem > len(linhas):
        primeiro = (pagina - 1) * POR_PAGINA + 1
        conta = ("Mais recentes primeiro &middot; %s&ndash;%s de %s que "
                 "correspondem &middot; página %s de %s"
                 % (mil(primeiro), mil(primeiro + len(linhas) - 1),
                    mil(correspondem), mil(pagina), mil(paginas)))
    else:
        conta = ("Mais recentes primeiro &middot; %s %s"
                 % (mil(correspondem),
                    "resultado" if correspondem == 1 else "resultados"))
    conta += " &middot; %s na base" % mil(total)
    if porler:
        conta += " &middot; %s ainda sem detalhe lido" % mil(porler)

    # Os avisos da ultima verificacao. O ficheiro AVISOS.txt serve para
    # quem nao tem o painel aberto; aqui e para quem tem, e da o caminho
    # para o filtro em vez de o obrigar a procurar.
    por_enviar = sum(len(x[1]) for x in alertas_por_enviar())
    if por_enviar:
        faixa_avisos = (
            "<div class='flash'><b>%s anúncio%s</b> nos teus alertas, "
            "por avisar. <a href='/alertas'>ver os alertas</a></div>"
            % (mil_pt(por_enviar), "" if por_enviar == 1 else "s"))
    else:
        faixa_avisos = ""

    mensagem = le_marca("ultima_mensagem", "ainda não verificou")
    bom = le_marca("ultima_ok", "") != "0"
    rodape = ("<div class='rodape'>"
              "<span class='ponto' style='background:%s'></span>"
              "<span class='e'>%s</span>"
              "<span class='d'>última verificação %s &middot; verifica às %s</span>"
              "</div>"
              % ("#1e8449" if bom else "#c0392b", html.escape(mensagem),
                 html.escape(le_marca("ultima_verificacao", "nunca")),
                 " e ".join(ler_config()["horas_verificacao"])))

    # A ordem e sempre a mesma nas duas listas: filtros, faixa do CPV
    # activo, arvore, e so depois os filtros guardados. A arvore e onde
    # se escolhe o CPV, por isso vem antes de se guardar a escolha.
    conteudo = ("<div class='larg'>" + faixa_avisos +
                filtros + faixa_cpv + arvore + caixa_guardados +
                "<div class='linha-conta'>" + conta +
                "<a href='/csv%s'>exportar CSV</a></div>"
                % (("?" + request.query_string.decode())
                   if request.query_string else "") +
                corpo_lista + paginador(pagina, paginas, request.args) +
                rodape + "</div>")

    return envolver(
        "anuncios", "Anúncios da parte L",
        "Entra tudo o que o DR publica &mdash; a triagem faz-se aqui, "
        "por palavras, entidade, datas, CPV e estado.",
        conteudo, abas="".join(abas), script=ARVORE_JS,
        titulo_aba="Radar de Concursos, DR")


# Caractere de escape do LIKE. Usa-se "!" e nao a barra invertida de
# propósito: a barra teria de sobreviver ao literal de Python e ao literal
# de SQL ao mesmo tempo, e conta-las erra-se com facilidade.
ESCAPE_LIKE = "!"


def para_like(termo):
    """Escapa os caracteres especiais do LIKE. Sem isto, procurar "50%"
    devolvia tudo o que tem "50", e "CP_2026" tratava o _ como coringa."""
    for ch in (ESCAPE_LIKE, "%", "_"):
        termo = termo.replace(ch, ESCAPE_LIKE + ch)
    return termo


# Os campos que fazem um filtro, por ordem fixa. A ordem importa: e ela
# que deixa comparar a consulta guardada com a de agora por igualdade de
# texto, para se saber qual dos filtros guardados esta em uso.
CAMPOS_FILTRO = ("q", "ent", "cpv", "plat", "de", "ate", "estado")

# Argumentos que a lista usa mas nao definem o filtro, e por isso nao se
# guardam nem se arrastam para as ligacoes: a pagina e onde se esta, o
# aviso e da vez.
CAMPOS_DA_VEZ = ("pag", "aviso")


# Os campos que fazem um filtro de contratos. Lista propria porque a
# lista e outra: um anuncio nao tem vencedor nem valor final.
CAMPOS_FILTRO_CONTRATOS = ("q", "adj", "ganhou", "cpv", "proc", "de", "ate",
                           "min", "entid", "vencid")

# (campos do filtro, rota da lista) por separador. E o que deixa os
# filtros guardados servirem os dois sem duas copias do codigo.
VISTAS = {"anuncios": (CAMPOS_FILTRO, "/"),
          "contratos": (CAMPOS_FILTRO_CONTRATOS, "/contratos")}


def filtro_actual(args, vista="anuncios"):
    """A query string canonica do filtro em uso, para guardar e comparar."""
    pares = []
    for campo in VISTAS[vista][0]:
        if campo == "estado":
            # o mesmo criterio de condicoes(): ausente e "novo", presente
            # e vazio e "todos". Sao vistas diferentes, e a diferenca tem
            # de sobreviver a ida a base -- por isso o estado entra
            # sempre, mesmo quando esta vazio.
            valor = args.get("estado")
            valor = "novo" if valor is None else valor.strip()
        else:
            valor = (args.get(campo) or "").strip()
            if not valor:
                continue
        pares.append((campo, valor))
    return urlencode(pares)


# Como se le cada campo na descricao de um filtro guardado.
_NOMES_FILTRO = {"q": "objecto", "ent": "entidade", "cpv": "CPV",
                 "plat": "plataforma", "de": "desde", "ate": "até",
                 "adj": "entidade", "ganhou": "ganho por",
                 "proc": "procedimento", "min": "desde €",
                 "entid": "entidade", "vencid": "ganho por"}
_NOMES_ESTADO = {"novo": "por ver", "interessa": "interessa",
                 "descartado": "descartados", "": "todos"}


def resumo_filtro(consulta, vista="anuncios"):
    """Diz por palavras o que um filtro guardado apanha, para a legenda."""
    campos = dict(parse_qsl(consulta or "", keep_blank_values=True))
    partes = []
    for campo in VISTAS[vista][0]:
        valor = campos.get(campo)
        if valor is None:
            continue
        if campo == "estado":
            partes.append(_NOMES_ESTADO.get(valor, valor))
        elif valor:
            partes.append("%s %s" % (_NOMES_FILTRO[campo], valor))
    return " · ".join(partes) or "sem filtro"


def arvore_html(n_cpv, de):
    """A arvore de CPV, igual nos dois separadores.

    O `de` diz de onde vem a contagem de cada codigo (anuncios ou
    contratos) e vai no proprio elemento, num data-*: o JS e o mesmo nos
    dois sitios e le dali a rota que ha-de pedir. Duas copias do JS
    divergiam ao primeiro arranjo.
    """
    quantos = {"anuncios": "anúncios", "contratos": "contratos"}[de]
    return (
        "<details class='arvore' data-de='%s'><summary>"
        "<span class='arv-tit'>Escolher CPV na árvore</span>"
        "<span class='arv-sub'>%s códigos &middot; contagens acumuladas "
        "de %s</span>"
        "<span class='arv-chip' id='arvore-chip'>nenhum seleccionado</span>"
        "</summary>"
        "<div class='arvore-topo'>"
        "<input type='text' id='arvore-busca' placeholder='filtrar a árvore, ex. software'>"
        "<button type='button' onclick='arvoreAplicar()'>Aplicar seleccionados ao filtro</button>"
        "<button type='button' class='claro' onclick='arvoreLimpar()'>Limpar selecção</button>"
        "<span id='arvore-contagem'></span>"
        "</div>"
        "<div id='arvore-corpo'>a carregar…</div>"
        "<div class='arv-pe'>Marcar uma divisão marca visualmente os descendentes; "
        "ao filtro vai só o código do grupo &mdash; os zeros à direita apanham "
        "tudo o que está por baixo.</div>"
        "</details>" % (de, mil_pt(n_cpv), quantos))


def prefixo_cpv(pedaco):
    """De um codigo CPV para o prefixo com que se procura.

    So os 8 digitos do codigo, sem o digito de controlo, que descola do
    formato guardado (o traco nao entra na conta). Os zeros a direita sao
    estrutura no CPV, por isso tira-los alarga do codigo para o grupo:
    "72000000" apanha "72267100".

    Mas nunca abaixo de dois digitos, que e a largura da divisao:
    "30000000".rstrip("0") daria "3" e apanhava as divisoes 31, 33, 34,
    35, 37, 38 e 39 por engano -- medido, 4592 anuncios em vez de 440.

    Devolve "" quando nao sobra digito nenhum. E aqui, e nao em cada
    sitio que procura por CPV, para o corpus de contratos procurar com o
    mesmo criterio da lista -- duas copias desta regra divergiam.
    """
    digitos = re.sub(r"\D", "", pedaco or "")[:8]
    if not digitos:
        return ""
    curto = digitos.rstrip("0")
    return curto if len(curto) >= 2 else digitos[:2]


def condicoes(args):
    """Traduz os filtros do painel em SQL. Nada e apagado, so escondido."""
    onde, valores = [], []

    def procura(texto, coluna):
        """Varias palavras separadas por | -- qualquer uma serve."""
        pedacos = [p.strip() for p in (texto or "").split("|") if p.strip()]
        if not pedacos:
            return
        ors = []
        for p in pedacos:
            ors.append("%s LIKE ? ESCAPE '%s'" % (coluna, ESCAPE_LIKE))
            valores.append("%" + para_like(p) + "%")
        onde.append("(" + " OR ".join(ors) + ")")

    # Duas caixas, e nao uma sobre as duas colunas: procurar "Lisboa"
    # devolvia tanto os concursos com Lisboa no objecto como todos os da
    # Camara de Lisboa, sem se poder separar. Entre elas e E, nao OU --
    # serve para "software" na entidade "SPMS".
    procura(args.get("q"), "titulo")
    procura(args.get("ent"), "entidade")
    cpv = (args.get("cpv") or "").strip()
    if cpv:
        # cada pedaco e um codigo (72, 72267100-0) ou uma palavra da
        # descricao oficial (software, manutencao); qualquer um serve
        ors = []
        for pedaco in (p.strip() for p in cpv.split("|")):
            if not pedaco:
                continue
            if re.fullmatch(r"[\d\-\s]+", pedaco):
                prefixos = [prefixo_cpv(pedaco)]
            else:
                prefixos = cpv_por_termo(pedaco)
            for prefixo in prefixos:
                if prefixo:
                    ors.append("(cpv LIKE ? OR cpv LIKE ?)")
                    valores += [prefixo + "%", "%, " + prefixo + "%"]
        # termo que nao corresponde a nada: mostra vazio, nao tudo
        onde.append("(" + " OR ".join(ors) + ")" if ors else "1=0")
    plat = (args.get("plat") or "").strip()
    if plat:
        if plat == SEM_PLATAFORMA:
            onde.append("(plataforma IS NULL OR plataforma = '')")
        else:
            onde.append("plataforma = ?"); valores.append(plat)
    de = (args.get("de") or "").strip()
    if de:
        onde.append("data_pub >= ?"); valores.append(de)
    ate = (args.get("ate") or "").strip()
    if ate:
        onde.append("data_pub <= ?"); valores.append(ate)
    estado = args.get("estado")
    if estado is None:
        estado = "novo"
    if estado:
        onde.append("estado = ?"); valores.append(estado)
    return (" WHERE " + " AND ".join(onde) if onde else ""), valores


def caixa_de_filtros(args, vista, rota=None, campos=None):
    """A caixa dos filtros guardados, igual em todas as paginas.

    Aplicar um filtro e seguir uma ligacao -- so leitura, nada muda na
    base -- mas guardar e apagar sao POST, como o resto do que escreve.
    O que muda entre vistas e a lista de campos e a rota; o resto e o
    mesmo, e duas copias divergiam ao primeiro arranjo.

    `rota` e `campos` servem as paginas que **usam** os filtros de uma
    vista sem serem a lista dela: a ficha da entidade aplica os filtros
    dos contratos aos contratos daquela entidade, e por isso a ligacao
    tem de voltar a ficha e levar so os campos que ela entende.
    """
    rota = rota or VISTAS[vista][1]
    so_estes = set(campos) if campos else None
    agora = filtro_actual(args, vista)
    with liga() as c:
        guardados = c.execute(
            "SELECT * FROM filtros_guardados WHERE vista=? "
            "ORDER BY nome COLLATE NOCASE", (vista,)).fetchall()

    fichas, nome_activo = [], ""
    for f in guardados:
        consulta = f["consulta"] or ""
        if so_estes is not None:
            # so os campos que esta pagina entende; os outros ja estao
            # respondidos por ela (a entidade, na ficha)
            consulta = urlencode([(k, v) for k, v in
                                  parse_qsl(consulta, keep_blank_values=True)
                                  if k in so_estes and v])
        activo = consulta == agora
        if activo:
            nome_activo = f["nome"]
        fichas.append(
            "<span class='guardado%s'>"
            "<a href='%s?%s' title='%s'>%s</a>"
            "<form method='post' action='/filtros/%d/apagar' "
            "onsubmit='return confirm(\"Apagar o filtro guardado &quot;%s&quot;? "
            "Não se apaga nada além do filtro.\")'>"
            "<input type='hidden' name='volta' value='%s'>"
            "<button type='submit' title='apagar este filtro'>&times;</button>"
            "</form></span>"
            % (" on" if activo else "", rota,
               html.escape(consulta, quote=True),
               html.escape(resumo_filtro(f["consulta"] or "", vista),
                           quote=True),
               html.escape(f["nome"]), f["id"],
               html.escape(f["nome"], quote=True),
               html.escape(agora, quote=True)))

    legenda = "" if fichas else (
        "<span class='nada'>ainda nenhum &mdash; escolhe os filtros acima e "
        "dá-lhes um nome</span>")
    # O nome do filtro em uso vem preenchido de proposito: gravar por cima
    # do mesmo nome e como se actualiza um filtro depois de o afinar.
    guardar = (
        "<form class='guardar' method='post' action='/filtros/guardar'>"
        "<input type='hidden' name='vista' value='%s'>"
        "<input type='hidden' name='consulta' value='%s'>"
        "<input type='text' name='nome' required maxlength='60' value='%s' "
        "placeholder='dar nome a estes filtros…'>"
        "<button type='submit' class='bt forte'>Guardar filtro</button>"
        "</form>" % (vista, html.escape(agora, quote=True),
                     html.escape(nome_activo, quote=True)))

    return ("<div class='cx guardados'><span class='rot'>"
            "Filtros guardados</span>%s%s%s</div>"
            % ("".join(fichas), legenda, guardar))


def volta_a_lista(consulta, vista="anuncios", aviso=""):
    """Volta para a lista de onde se veio, com os filtros que estavam."""
    rota = VISTAS.get(vista, VISTAS["anuncios"])[1]
    partes = [p for p in (consulta, urlencode({"aviso": aviso}) if aviso else "")
              if p]
    return redirect(rota + "?" + "&".join(partes) if partes else rota)


def _vista_pedida(valor):
    """Nunca deixar um valor de fora escolher uma rota a esmo."""
    valor = (valor or "").strip()
    return valor if valor in VISTAS else "anuncios"


@app.route("/filtros/guardar", methods=["POST"])
def filtro_guardar():
    """Guarda os filtros de agora com um nome. Gravar por cima do mesmo
    nome actualiza-o -- e assim que se afina um filtro sem ficar com dois
    quase iguais e sem saber qual deles esta em uso.

    O mesmo nome pode servir nas duas listas: a unicidade e por (vista,
    nome), porque "Software" quer dizer coisas diferentes em cada uma.
    """
    nome = (request.form.get("nome") or "").strip()
    consulta = (request.form.get("consulta") or "").strip()
    vista = _vista_pedida(request.form.get("vista"))
    if not nome:
        return volta_a_lista(consulta, vista)
    with liga() as c:
        antes = c.execute("SELECT id FROM filtros_guardados "
                          "WHERE vista=? AND nome=?", (vista, nome)).fetchone()
        c.execute("""INSERT INTO filtros_guardados
                       (vista,nome,consulta,quem,criado_em)
                     VALUES (?,?,?,?,?)
                     ON CONFLICT(vista,nome) DO UPDATE SET
                       consulta=excluded.consulta, quem=excluded.quem,
                       criado_em=excluded.criado_em""",
                  (vista, nome, consulta, quem_sou() or "(sem nome)",
                   datetime.now().strftime("%Y-%m-%d %H:%M")))
    return volta_a_lista(consulta, vista, "Filtro %s: %s"
                         % ("actualizado" if antes else "guardado", nome))


@app.route("/filtros/<int:filtro_id>/apagar", methods=["POST"])
def filtro_apagar(filtro_id):
    """Apaga so o filtro. Nem os anuncios nem os contratos se mexem -- um
    filtro esconde, nao apaga, e tira-lo devolve a lista inteira."""
    with liga() as c:
        linha = c.execute("SELECT nome, vista FROM filtros_guardados "
                          "WHERE id=?", (filtro_id,)).fetchone()
        c.execute("DELETE FROM filtros_guardados WHERE id=?", (filtro_id,))
    return volta_a_lista((request.form.get("volta") or "").strip(),
                         linha["vista"] if linha else "anuncios",
                         "Filtro apagado: %s" % linha["nome"] if linha else "")


# {fonte: (chave de frescura, corpo JSON)} -- ver cpv_json()
_CPV_CACHE = {}


def _contagens_cpv_anuncios():
    """(chave de frescura, {codigo8: quantos anuncios})."""
    contagens = {}
    with liga() as c:
        lidos = c.execute("SELECT COUNT(*) n FROM anuncios "
                          "WHERE detalhe_lido=1").fetchone()["n"]
        for row in c.execute("SELECT cpv FROM anuncios WHERE cpv != ''"):
            for pedaco in row["cpv"].split(","):
                codigo8 = re.sub(r"\D", "", pedaco)[:8]
                if len(codigo8) == 8:
                    contagens[codigo8] = contagens.get(codigo8, 0) + 1
    return lidos, contagens


def _contagens_cpv_contratos():
    """A mesma coisa para o corpus. A arvore do separador dos contratos
    tem de contar contratos: mostrar ali as contagens dos anuncios dizia
    ao Afonso que uma divisao esta vazia quando tem milhares de
    contratos, ou o contrario."""
    if not ha_corpus():
        return 0, {}
    with liga_corpus() as c:
        quantos = c.execute("SELECT COUNT(*) n FROM contratos").fetchone()["n"]
        contagens = {r["cpv8"]: r["n"] for r in c.execute(
            "SELECT cpv8, COUNT(*) n FROM contrato_cpv GROUP BY cpv8")}
    return quantos, contagens


# De onde a arvore conta. A chave e o ?de= da rota.
FONTES_CPV = {"anuncios": _contagens_cpv_anuncios,
              "contratos": _contagens_cpv_contratos}


@app.route("/cpv.json")
def cpv_json():
    """O vocabulario CPV inteiro, com a contagem que cada codigo tem na
    fonte pedida (?de=anuncios, por omissao, ou ?de=contratos). Alimenta
    a arvore dos dois separadores; o agrupamento em ramos e feito no
    browser."""
    de = request.args.get("de", "anuncios")
    conta = FONTES_CPV.get(de)
    if not conta:
        return Response('{"erro":"fonte desconhecida"}',
                        mimetype="application/json", status=400)
    chave, contagens = conta()

    # As contagens so mudam quando a fonte muda (mais um anuncio com
    # detalhe lido, ou uma importacao de contratos). Guardar o resultado
    # poupa varrer a tabela e serializar ~780 KB a cada abertura da
    # arvore. Uma entrada por fonte: com uma so, alternar de separador
    # deitava fora a cache do outro a cada visita.
    if _CPV_CACHE.get(de, (None,))[0] == chave:
        return Response(_CPV_CACHE[de][1], mimetype="application/json")

    with liga() as c:
        linhas = c.execute(
            "SELECT codigo8, descricao FROM cpv_dict ORDER BY codigo8").fetchall()
    dados = [{"codigo8": r["codigo8"], "descricao": r["descricao"],
              "n": contagens.get(r["codigo8"], 0)} for r in linhas]
    corpo = json.dumps(dados, ensure_ascii=False)
    _CPV_CACHE[de] = (chave, corpo)
    return Response(corpo, mimetype="application/json")


@app.route("/verificar", methods=["POST"])
def verificar_agora():
    verificar()
    return redirect("/")


@app.route("/estado/<path:ref>/<novo>", methods=["POST"])
def mudar_estado(ref, novo):
    if novo in ("novo", "interessa", "descartado"):
        with liga() as c:
            if novo == "interessa":
                c.execute("""UPDATE anuncios SET estado=?,
                             fase_id=COALESCE(fase_id, ?) WHERE ref=?""",
                          (novo, primeira_fase(), ref))
            else:
                c.execute("UPDATE anuncios SET estado=? WHERE ref=?", (novo, ref))
        registar(ref, "estado", novo)
        if novo == "interessa":
            # Marcar interessa e o sinal de que vais mesmo trabalhar isto,
            # por isso as pecas vem sozinhas -- mas por uma fila, nao uma
            # thread por clique: triar vinte anuncios seguidos abria vinte
            # descargas de varios MB ao mesmo tempo.
            pedir_documentos(ref)
    return redirect(request.referrer or "/")


@app.route("/sou", methods=["POST"])
def definir_quem():
    """Guarda num cookie quem esta a trabalhar. Sem palavra-passe: e
    identificacao, nao autenticacao, e isso e dito na interface."""
    nome = criar_pessoa(request.form.get("nome"))
    resposta = redirect(request.referrer or "/")
    if nome:
        resposta.set_cookie("quem", nome, max_age=60 * 60 * 24 * 365)
    return resposta


@app.route("/responsavel/<path:ref>", methods=["POST"])
def definir_responsavel(ref):
    nome = criar_pessoa(request.form.get("nome")) if request.form.get("nome") else ""
    with liga() as c:
        c.execute("UPDATE anuncios SET responsavel=? WHERE ref=?", (nome, ref))
    registar(ref, "responsável", nome or "(ninguém)")
    return redirect(request.referrer or ("/anuncio/" + ref))


@app.route("/csv")
def exportar():
    """Exporta exactamente o que o filtro esta a mostrar."""
    onde, valores = condicoes(request.args)
    with liga() as c:
        linhas = c.execute(
            "SELECT ref,data_pub,tipo,entidade,titulo,cpv,prazo,preco_base,"
            "estado,url FROM anuncios" + onde +
            " ORDER BY data_pub DESC", valores).fetchall()
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";")
    escritor.writerow(["Anúncio", "Publicado", "Tipo", "Entidade", "Objecto",
                       "CPV", "Prazo", "Preço base", "Estado", "Endereço"])
    for a in linhas:
        escritor.writerow([a[k] for k in a.keys()])
    return Response("\ufeff" + saida.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition":
                             "attachment; filename=concursos.csv"})




# -------------------------------------------------------- separador alertas
#
# Um alerta e um filtro guardado com a marca posta. Nao ha aqui uma
# segunda forma de descrever o que interessa: o que se procura na lista
# e o que se guarda, e o que se guarda e o que avisa. Isso e o que
# garante que o e-mail traz exactamente o que a lista mostraria.

@app.route("/alertas")
def alertas():
    cfg = ler_config()
    e = cfg.get("email") or {}
    with liga() as c:
        filtros = c.execute(
            "SELECT f.*, "
            "(SELECT COUNT(*) FROM alertas_vistos v WHERE v.filtro_id=f.id "
            " AND v.enviado_em IS NULL) por_enviar, "
            "(SELECT COUNT(*) FROM alertas_vistos v WHERE v.filtro_id=f.id "
            " AND v.enviado_em = ?) acervo, "
            "(SELECT COUNT(*) FROM alertas_vistos v WHERE v.filtro_id=f.id "
            " AND v.enviado_em IS NOT NULL AND v.enviado_em != ?) avisados "
            "FROM filtros_guardados f WHERE f.vista='anuncios' "
            "ORDER BY f.alerta DESC, f.nome COLLATE NOCASE",
            (ACERVO, ACERVO)).fetchall()
        ultimos = c.execute(
            "SELECT v.ref, v.enviado_em, a.titulo, a.entidade, a.prazo, "
            "f.nome AS filtro FROM alertas_vistos v "
            "JOIN anuncios a ON a.ref=v.ref "
            "JOIN filtros_guardados f ON f.id=v.filtro_id "
            "WHERE v.enviado_em IS NOT NULL AND v.enviado_em != ? "
            "ORDER BY v.enviado_em DESC LIMIT 25", (ACERVO,)).fetchall()

    linhas = []
    for f in filtros:
        ligado = bool(f["alerta"])
        linhas.append(
            "<div class='alerta %s'>"
            "<form method='post' action='/alertas/%d/trocar'>"
            "<button type='submit' class='interruptor %s' title='%s'>"
            "<i></i></button></form>"
            "<div class='sobre'><a href='/?%s'>%s</a>"
            "<span class='q'>%s</span></div>"
            "<div class='conta'>%s</div>"
            "</div>"
            % ("on" if ligado else "", f["id"],
               "on" if ligado else "",
               "desligar o alerta" if ligado else "ligar o alerta",
               html.escape(f["consulta"] or "", quote=True),
               html.escape(f["nome"]),
               html.escape(resumo_filtro(f["consulta"], "anuncios")),
               ("<b>%s</b> por avisar &middot; %s já avisados &middot; "
                "%s do acervo"
                % (mil_pt(f["por_enviar"]), mil_pt(f["avisados"]),
                   mil_pt(f["acervo"]))
                if ligado else "não avisa")))
    if not linhas:
        lista = ("<div class='vazio'>Ainda não guardaste nenhum filtro nos "
                 "anúncios. Um alerta <b>é</b> um filtro guardado com a "
                 "marca posta: vai à <a href='/'>lista dos anúncios</a>, "
                 "afina a pesquisa, dá-lhe um nome, e ele aparece aqui.</div>")
    else:
        lista = "<div class='alertas'>%s</div>" % "".join(linhas)

    # --- estado do e-mail
    tem_senha = bool(ler_chave(("email_senha.txt",), "RADAR_EMAIL_SENHA"))
    pronto = bool((e.get("para") or "").strip() and (e.get("de") or "").strip()
                  and tem_senha)
    passos = [
        ("Destino", e.get("para") or "por preencher", bool(e.get("para"))),
        ("Conta que envia", e.get("de") or "por preencher", bool(e.get("de"))),
        ("Servidor", "%s:%s" % (e.get("servidor") or "—", e.get("porta") or "—"),
         bool(e.get("servidor"))),
        ("Palavra-passe", "em email_senha.txt" if tem_senha
         else "falta o ficheiro email_senha.txt", tem_senha),
        ("Hora do resumo", e.get("hora_resumo") or "17:00", True),
    ]
    estado_envio = le_marca("ultimo_resumo_estado", "")
    if estado_envio:
        passos.append(("Último envio", html.escape(estado_envio),
                       not estado_envio.startswith("por enviar")))

    if pronto:
        accao_email = accao("/alertas/enviar", "Enviar o resumo agora", "bt forte")
    else:
        accao_email = ""
    caixa_email = (
        "<div class='cx' style='padding:20px 22px'>"
        "<div class='rot' style='margin-bottom:6px'>Resumo por e-mail</div>"
        "<div class='nota' style='margin-bottom:16px'>Um por dia, a partir "
        "das %s, e só se houver novidade. O destino pode ser qualquer "
        "endereço; o que precisa de conta própria é quem envia. Configura-se "
        "no <code>config.json</code>, e a palavra-passe fica no ficheiro "
        "<code>email_senha.txt</code> &mdash; nunca na configuração.</div>"
        "<div class='saude'>%s</div>%s%s</div>"
        % (html.escape(str(e.get("hora_resumo") or "17:00")),
           linhas_de_saude(passos, "#d68910"),
           "<div style='margin-top:16px'>%s</div>" % accao_email
           if accao_email else "",
           "" if pronto else
           "<div class='nota' style='margin-top:14px'>Sem e-mail "
           "configurado o radar continua a escrever o "
           "<code>AVISOS.txt</code> na pasta, e a lista aqui em baixo "
           "mostra o mesmo.</div>"))

    if ultimos:
        hist = "".join(
            "<tr><td class='d'>%s</td><td class='o'>"
            "<a href='/anuncio/%s'>%s</a></td><td>%s</td><td>%s</td></tr>"
            % (data_pt(r["enviado_em"]), quote(r["ref"], safe=""),
               html.escape((r["titulo"] or r["ref"])[:80]),
               html.escape((r["entidade"] or "")[:44]),
               html.escape(r["filtro"]))
            for r in ultimos)
        historico = ("<div class='cx tab-cx'><table class='tab-contratos'>"
                     "<thead><tr><th>Avisado</th><th>Anúncio</th>"
                     "<th>Entidade</th><th>Alerta</th></tr></thead>"
                     "<tbody>%s</tbody></table></div>" % hist)
    else:
        historico = ("<div class='nota'>Ainda não saiu nenhum aviso. Sai no "
                     "resumo a seguir à próxima verificação.</div>")

    conteudo = ("<div class='larg'>" + lista +
                "<div style='height:16px'></div>" + caixa_email +
                "<div class='rot' style='margin:22px 0 12px'>Últimos avisos"
                "</div>" + historico + "</div>")

    return envolver(
        "alertas", "Alertas",
        "Os filtros guardados que te avisam quando entra um anúncio que "
        "lhes corresponde.", conteudo,
        titulo_aba="Alertas, Radar de Concursos")


@app.route("/alertas/<int:filtro_id>/trocar", methods=["POST"])
def alerta_trocar(filtro_id):
    with liga() as c:
        c.execute("UPDATE filtros_guardados SET alerta = 1 - COALESCE(alerta,0) "
                  "WHERE id=?", (filtro_id,))
    # ao ligar um alerta, o que ja esta na base conta como visto e nao
    # como novidade -- senao o primeiro resumo trazia o acervo todo
    registar_alertas()
    with liga() as c:
        ligou = c.execute("SELECT alerta FROM filtros_guardados WHERE id=?",
                          (filtro_id,)).fetchone()
        if ligou and ligou["alerta"]:
            c.execute("UPDATE alertas_vistos SET enviado_em=? "
                      "WHERE filtro_id=? AND enviado_em IS NULL",
                      (ACERVO, filtro_id))
    return redirect("/alertas")


@app.route("/alertas/enviar", methods=["POST"])
def alertas_enviar():
    bem, porque = enviar_resumo(forcar=True)
    return redirect("/alertas?aviso=" +
                    quote(("Resumo %s" % porque) if bem else porque))


# ------------------------------------------------------ separador contratos
#
# Lista propria, e nao uma vista da dos anuncios: sao coisas diferentes.
# Um anuncio e uma oportunidade a que se pode concorrer; um contrato ja
# esta assinado e o que dele se quer saber e quem ganhou e por quanto.
# Ate os filtros sao outros -- um anuncio nao tem vencedor nem valor
# final. Por isso separador proprio, tabela propria, ficheiro proprio.

GRAFICOS_JS = """<script>
(function() {
  var det = document.querySelector('details.graficos');
  if (!det) return;
  var feito = false;
  det.addEventListener('toggle', function() {
    if (!det.open || feito) return;
    feito = true;
    // os mesmos filtros da lista, menos a pagina: os graficos sao do
    // filtro todo e nao das 20 linhas que estao a dar
    var p = new URLSearchParams(location.search);
    p.delete('pag');
    fetch('/contratos/resumo?' + p.toString())
      .then(function(r) { return r.text(); })
      .then(function(html) {
        document.getElementById('graf-corpo').innerHTML = html;
      })
      .catch(function() {
        document.getElementById('graf-corpo').textContent = 'falhou a carregar.';
      });
  });
})();
</script>"""


def resumo_contratos(args):
    """Os numeros dos graficos, sobre o mesmo filtro da lista.

    E o que faz os graficos valerem a pena: o filtro e a pergunta ("CPV
    72, ultimos 12 meses") e estes numeros sao a resposta. Fixos, seriam
    a resposta a uma pergunta que ninguem fez.
    """
    onde, valores = condicoes_contratos(args)
    with liga_corpus() as c:
        # Quem ganha e a concentracao saem da mesma passagem: as duas
        # agregam por adjudicatario, e o SUM/COUNT OVER () traz o total e
        # o numero de empresas sem uma segunda varredura (poupa ~450 ms).
        #
        # O valor reparte-se pelos adjudicatarios (c.n_adj): um contrato
        # ganho por um agrupamento de tres nao vale tres vezes o mercado
        # -- e ha um com 35.
        # Agrupa-se pela chave da entidade, nao pelo nome: o nome nao e a
        # identidade. Sem isto a MEO aparecia partida pelos 81 nomes com
        # que assina, e nenhum deles chegava ao topo.
        ganha = c.execute(
            "WITH por_empresa AS ("
            " SELECT a.chave ch, SUM(c.preco_contratual/c.n_adj) v, COUNT(*) k"
            " FROM contratos c JOIN contrato_adjudicatario a"
            "   ON a.contrato_id=c.id" + onde +
            " GROUP BY +a.chave),"
            # o nome vai buscar-se so as 10 que ficam: juntar a
            # `entidades` antes do LIMIT eram 68 mil buscas ao indice
            " topo AS (SELECT ch, v, k, SUM(v) OVER () total,"
            "          COUNT(*) OVER () quantas FROM por_empresa"
            "          ORDER BY v DESC LIMIT 10)"
            " SELECT t.ch, COALESCE(e.nome, t.ch) n, t.v, t.k, t.total,"
            " t.quantas FROM topo t LEFT JOIN entidades e ON e.chave = t.ch"
            " ORDER BY t.v DESC", valores).fetchall()
        # O `+` desliga o indice de proposito: com ele, o SQLite varre o
        # indice e vai buscar cada linha ao acaso -- 1443 ms contra 477.
        compra = c.execute(
            "WITH por_entidade AS ("
            " SELECT c.adjudicante_chave ch, SUM(c.preco_contratual) v,"
            " COUNT(*) k FROM contratos c" + onde +
            " GROUP BY +c.adjudicante_chave"
            " ORDER BY v DESC LIMIT 10)"
            " SELECT p.ch, COALESCE(e.nome, p.ch) n, p.v, p.k"
            " FROM por_entidade p LEFT JOIN entidades e ON e.chave = p.ch"
            " ORDER BY p.v DESC", valores).fetchall()
        proc = c.execute(
            "SELECT c.tipo_procedimento p, COUNT(*) k, "
            "SUM(c.preco_contratual) v FROM contratos c" + onde +
            " GROUP BY p ORDER BY v DESC LIMIT 8", valores).fetchall()
        # Por trimestre enquanto couberem; com sete anos sao 27 barras e
        # os rotulos deixam de se ler, e entao agrupa-se por ano. A
        # legenda diz qual e -- um grafico que muda de unidade sem avisar
        # e pior do que um grafico apertado.
        trim = c.execute(
            "SELECT substr(c.data_celebracao,1,4) || ' T' || "
            "  ((CAST(substr(c.data_celebracao,6,2) AS INTEGER)+2)/3) t, "
            "COUNT(*) k, SUM(c.preco_contratual) v FROM contratos c" + onde +
            " AND c.data_celebracao!='' GROUP BY t ORDER BY t", valores).fetchall()
        if len(trim) > MAX_BARRAS_TEMPO:
            trim = c.execute(
                "SELECT substr(c.data_celebracao,1,4) t, COUNT(*) k, "
                "SUM(c.preco_contratual) v FROM contratos c" + onde +
                " AND c.data_celebracao!='' GROUP BY t ORDER BY t",
                valores).fetchall()
        # Escaloes de valor em vez da mediana exacta: ordenar 400 mil
        # precos para tirar o do meio levava 953 ms, e a pergunta a que
        # isto responde -- "ha aqui contratos do meu tamanho?" -- le-se
        # melhor na distribuicao do que num numero solto. A mediana sai
        # depois do escalao onde cai a contagem acumulada.
        # o CASE sai dos mesmos limites que as etiquetas, para nao se
        # mudar um sem o outro
        escada = " ".join("WHEN c.preco_contratual < %d THEN %d" % (lim, i)
                          for i, lim in enumerate(LIMITES_ESCALAO))
        escal = c.execute(
            "SELECT CASE %s ELSE %d END e, COUNT(*) k, "
            "SUM(c.preco_contratual) v FROM contratos c"
            % (escada, len(LIMITES_ESCALAO)) + onde +
            " AND c.preco_contratual > 0 GROUP BY e ORDER BY e",
            valores).fetchall()
    return ganha, compra, proc, trim, escal


def entidade_do_anuncio(nif, nome):
    """A chave da entidade de um anuncio, no corpus.

    **Pelo NIPC primeiro.** O DR publica-o em praticamente todos os
    anuncios (medido: 99,3% dos que tem detalhe lido) e e o mesmo numero
    por que o BASE identifica a entidade -- e portanto a mesma chave, sem
    comparacao nenhuma pelo meio.

    O nome fica de reserva, para os anuncios antigos sem NIPC lido, e
    resolve 94,3%: falha nas sub-unidades ("Centro de Emprego de Entre
    Douro e Vouga" contra o IEFP que assina o anuncio) e nas variantes
    ("EPE" contra "E. P. E.").
    """
    if not ha_corpus():
        return ""
    nif = (nif or "").strip()
    if re.fullmatch(r"\d{9}", nif):
        with liga_corpus() as c:
            r = c.execute("SELECT chave FROM entidades WHERE chave=?",
                          (nif,)).fetchone()
        if r:
            return nif
    norm = norma_entidade(nome)
    if not norm:
        return ""
    with liga_corpus() as c:
        r = c.execute("SELECT chave FROM entidade_nomes WHERE nome_norm=?",
                      (norm,)).fetchone()
    return r["chave"] if r else ""


# Os campos que a propria ficha da entidade aceita. Sao os da lista de
# contratos menos os que ja estao respondidos pela ficha (a entidade) e
# menos os que nao fazem sentido aqui.
CAMPOS_FICHA = ("q", "cpv", "proc", "de", "ate", "min")


def filtro_da_ficha(args):
    """Traduz os filtros da ficha da entidade em SQL, para se somarem a
    entidade. Reaproveita a condicoes_contratos() e tira-lhe o `1=1`."""
    if not args:
        return "", []
    limpos = {c: args.get(c) for c in CAMPOS_FICHA if (args.get(c) or "").strip()}
    if not limpos:
        return "", []
    onde, valores = condicoes_contratos(limpos)
    return onde.replace(" WHERE 1=1", "", 1), valores


def ha_filtro_na_ficha(args):
    return any((args.get(campo) or "").strip() for campo in CAMPOS_FICHA)


def ficha_entidade(chave, args=None):
    """Tudo o que o corpus sabe sobre uma entidade, nos dois papeis.

    A mesma entidade compra e ganha -- um municipio adjudica obras e
    ganha candidaturas -- e por isso a ficha tem os dois lados em vez de
    haver uma pagina de compradores e outra de fornecedores.

    O `args` sao os filtros da propria ficha (objecto, CPV, procedimento,
    datas, valor), que se somam a entidade em todos os blocos. Sem eles,
    uma entidade com 2000 contratos obrigava a sair para a lista para
    perguntar o que quer que fosse.
    """
    e, ev = filtro_da_ficha(args)
    with liga_corpus() as c:
        ident = c.execute("SELECT * FROM entidades WHERE chave=?",
                          (chave,)).fetchone()
        if not ident:
            return None
        d = {"chave": chave, "nome": ident["nome"], "nif": ident["nif"],
             "variantes": ident["variantes"]}
        # os nomes e as datas do acervo sao da entidade, nao do filtro:
        # sao identidade, e mudarem com o filtro so confundia
        d["nomes"] = [r["nome_norm"] for r in c.execute(
            "SELECT nome_norm FROM entidade_nomes WHERE chave=? "
            "ORDER BY nome_norm LIMIT 40", (chave,))]

        # --- como comprador
        d["compra"] = c.execute(
            "SELECT COUNT(*) k, COALESCE(SUM(c.preco_contratual),0) v "
            "FROM contratos c WHERE c.adjudicante_chave=?" + e,
            [chave] + ev).fetchone()
        d["fornecedores"] = c.execute(
            "WITH p AS (SELECT a.chave ch, SUM(c.preco_contratual/c.n_adj) v, "
            " COUNT(*) k FROM contratos c JOIN contrato_adjudicatario a "
            " ON a.contrato_id=c.id WHERE c.adjudicante_chave=?" + e +
            " GROUP BY +a.chave ORDER BY v DESC LIMIT 10) "
            "SELECT p.ch, COALESCE(x.nome,p.ch) n, p.v, p.k FROM p "
            "LEFT JOIN entidades x ON x.chave=p.ch ORDER BY p.v DESC",
            [chave] + ev).fetchall()
        d["compra_proc"] = c.execute(
            "SELECT c.tipo_procedimento p, COUNT(*) k, "
            "SUM(c.preco_contratual) v FROM contratos c "
            "WHERE c.adjudicante_chave=?" + e +
            " GROUP BY p ORDER BY v DESC LIMIT 8", [chave] + ev).fetchall()
        d["compra_cpv"] = c.execute(
            "SELECT v.cpv8 cod, COUNT(*) k, SUM(c.preco_contratual/"
            " (SELECT COUNT(*) FROM contrato_cpv x WHERE x.contrato_id=c.id)) v "
            "FROM contratos c JOIN contrato_cpv v ON v.contrato_id=c.id "
            "WHERE c.adjudicante_chave=?" + e +
            " GROUP BY v.cpv8 ORDER BY v DESC LIMIT 10",
            [chave] + ev).fetchall()

        # --- como fornecedor
        d["ganha"] = c.execute(
            "SELECT COUNT(*) k, COALESCE(SUM(c.preco_contratual/c.n_adj),0) v "
            "FROM contratos c JOIN contrato_adjudicatario a "
            "ON a.contrato_id=c.id WHERE a.chave=?" + e,
            [chave] + ev).fetchone()
        d["clientes"] = c.execute(
            "WITH p AS (SELECT c.adjudicante_chave ch, "
            " SUM(c.preco_contratual/c.n_adj) v, COUNT(*) k "
            " FROM contratos c JOIN contrato_adjudicatario a "
            " ON a.contrato_id=c.id WHERE a.chave=?" + e +
            " GROUP BY +c.adjudicante_chave ORDER BY v DESC LIMIT 10) "
            "SELECT p.ch, COALESCE(x.nome,p.ch) n, p.v, p.k FROM p "
            "LEFT JOIN entidades x ON x.chave=p.ch ORDER BY p.v DESC",
            [chave] + ev).fetchall()
        d["ganha_cpv"] = c.execute(
            "SELECT v.cpv8 cod, COUNT(*) k, SUM(c.preco_contratual/c.n_adj/"
            " (SELECT COUNT(*) FROM contrato_cpv x WHERE x.contrato_id=c.id)) v "
            "FROM contratos c JOIN contrato_adjudicatario a "
            " ON a.contrato_id=c.id JOIN contrato_cpv v ON v.contrato_id=c.id "
            "WHERE a.chave=?" + e +
            " GROUP BY v.cpv8 ORDER BY v DESC LIMIT 10",
            [chave] + ev).fetchall()
        d["ganha_trim"] = _evolucao_de(
            c, "JOIN contrato_adjudicatario a ON a.contrato_id=c.id "
               "WHERE a.chave=?", "c.preco_contratual/c.n_adj",
            [chave] + ev, e)
        d["compra_trim"] = _evolucao_de(
            c, "WHERE c.adjudicante_chave=?", "c.preco_contratual",
            [chave] + ev, e)
        d["recentes"] = c.execute(
            "SELECT c.id, c.data_celebracao, c.objecto, c.preco_contratual, "
            "c.tipo_procedimento, c.adjudicante_chave, "
            "COALESCE(x.nome,c.adjudicante) outro "
            "FROM contratos c JOIN contrato_adjudicatario a "
            " ON a.contrato_id=c.id "
            "LEFT JOIN entidades x ON x.chave=c.adjudicante_chave "
            "WHERE a.chave=?" + e +
            " ORDER BY c.data_celebracao DESC LIMIT 12",
            [chave] + ev).fetchall()
    return d


def _evolucao_de(c, juncao, valor, params, extra):
    """A serie do tempo de um lado da ficha, por trimestre ou por ano.
    Mesma regra do resumo: acima de MAX_BARRAS_TEMPO passa a anos."""
    base = ("SELECT %s t, COUNT(*) k, SUM(" + valor + ") v FROM contratos c "
            + juncao + extra + " AND c.data_celebracao!='' "
            "GROUP BY t ORDER BY t")
    tri = ("substr(c.data_celebracao,1,4) || ' T' || "
           "((CAST(substr(c.data_celebracao,6,2) AS INTEGER)+2)/3)")
    linhas = c.execute(base % tri, params).fetchall()
    if len(linhas) > MAX_BARRAS_TEMPO:
        linhas = c.execute(base % "substr(c.data_celebracao,1,4)",
                           params).fetchall()
    return linhas


# Escaloes de valor, escolhidos pelo Afonso a olhar para o mercado que
# lhe interessa. O SQL do resumo tem de os seguir: os limites estao nos
# dois sitios porque um e CASE e o outro e texto, mas sao a mesma escada.
ESCALOES = ("< 20 k€", "20 – 75 k€", "75 – 250 k€", "250 – 750 k€",
            "750 k€ – 1 M€", "> 1 M€")
LIMITES_ESCALAO = (20000, 75000, 250000, 750000, 1000000)


def escaloes_html(escal):
    """Quantos contratos ha de cada tamanho, e onde cai a mediana."""
    if not escal:
        return ""
    por_e = {r["e"]: r for r in escal}
    total = sum(r["k"] for r in escal)
    # o escalao onde a contagem acumulada passa metade e o da mediana
    acumulado, mediano = 0, None
    for i in range(len(ESCALOES)):
        acumulado += por_e[i]["k"] if i in por_e else 0
        if mediano is None and acumulado >= total / 2.0:
            mediano = ESCALOES[i]
    linhas = [{"t": ESCALOES[i], "v": float(por_e[i]["k"]) if i in por_e else 0.0,
               "k": por_e[i]["k"] if i in por_e else 0}
              for i in range(len(ESCALOES))]
    return barras_v(
        linhas, "Tamanho dos contratos",
        "Quantos contratos há de cada tamanho. Metade fica em <b>%s</b> "
        "ou abaixo." % html.escape(mediano or "—"),
        destaque=mediano, fmt=mil_pt_f)


def mil_pt_f(v):
    """mil_pt() para as barras, que passam o valor como float."""
    return mil_pt(int(round(v or 0)))


def concentracao_html(ganha):
    """Quanto do mercado levam os maiores.

    Diz se vale a pena entrar: um mercado onde cinco empresas levam
    quatro quintos joga-se de outra maneira -- ou nao se joga.
    """
    if not ganha:
        return ""
    total = ganha[0]["total"] or 0
    quantas = ganha[0]["quantas"] or 0
    if not total:
        return ""
    topo = ganha[:5]
    quota = sum(x["v"] for x in topo)
    cores = ("#1f4e79", "#2f6ea6", "#4f8dc0", "#7fadd2", "#aecbe4")
    fatias = []
    for cor, x in zip(cores, topo):
        fatias.append("<i style='width:%.2f%%;background:%s' title='%s — %s'></i>"
                      % (100.0 * x["v"] / total, cor,
                         html.escape(x["n"], quote=True), euros_curto(x["v"])))
    resto = total - quota
    if resto > 0:
        fatias.append("<i style='width:%.2f%%;background:var(--linha2)' "
                      "title='as outras %s empresas — %s'></i>"
                      % (100.0 * resto / total, mil_pt(max(0, quantas - 5)),
                         euros_curto(resto)))
    return ("<div class='cx graf'><div class='rot'>Concentração</div>"
            "<div class='nota' style='margin:5px 0 14px'>Que fatia levam os "
            "cinco maiores, entre as %s empresas que ganharam alguma "
            "coisa.</div>"
            "<div class='conc-n'>%.0f%%</div>"
            "<div class='conc-b'>%s</div>"
            "<div class='nota' style='margin-top:10px'>Os cinco maiores "
            "levam %s dos %s adjudicados.</div></div>"
            % (mil_pt(quantas), 100.0 * quota / total, "".join(fatias),
               euros_curto(quota), euros_curto(total)))


def barras_h(linhas, titulo, nota="", ligar=False):
    """Barras horizontais: os nomes sao longos e nao cabem por baixo.

    Com `ligar`, o nome leva a ficha da entidade -- e preciso que as
    linhas tragam um `ch` com a chave. Sem chave, fica texto: mais vale
    um nome sem ligacao do que uma ligacao para lado nenhum.
    """
    if not linhas:
        return ""
    maior = max(l["v"] for l in linhas) or 1
    corpo = []
    for l in linhas:
        chave = l["ch"] if ligar and "ch" in l.keys() else ""
        etiqueta = (liga_entidade(chave, l["n"]) if chave
                    else html.escape(l["n"]))
        corpo.append(
            "<div class='bh'><span class='t' title='%s'>%s</span>"
            "<span class='r'><i style='width:%.1f%%'></i></span>"
            "<span class='v'>%s</span><span class='k'>%s</span></div>"
            % (html.escape(l["n"], quote=True), etiqueta,
               100.0 * l["v"] / maior, euros_curto(l["v"]),
               "%d contrato%s" % (l["k"], "" if l["k"] == 1 else "s")))
    return ("<div class='cx graf'><div class='rot'>%s</div>%s"
            "<div class='barras-h'>%s</div></div>"
            % (titulo,
               "<div class='nota' style='margin:5px 0 12px'>%s</div>" % nota
               if nota else "<div style='height:10px'></div>",
               "".join(corpo)))


# Acima disto, o eixo do tempo passa de trimestres para anos: com sete
# anos sao 27 barras e os rotulos deixam de se ler.
MAX_BARRAS_TEMPO = 16


def evolucao_html(linhas, titulo="Evolução"):
    """O gráfico do tempo, em trimestres ou em anos conforme o que couber.

    O periodo a decorrer vai as riscas nos dois casos: sem isso, o
    trimestre (ou o ano) corrente aparece como uma queda a pique e a
    conclusao que se tira dali -- "este mercado secou" -- e falsa.
    """
    if not linhas:
        return ""
    por_ano = len(linhas[0]["t"]) == 4      # "2026" e nao "2026 T3"
    agora = datetime.now()
    return barras_v(
        linhas, titulo,
        "Valor celebrado por %s. O %s a decorrer vai às riscas &mdash; "
        "ainda não acabou." % (("ano", "ano") if por_ano
                               else ("trimestre", "trimestre")),
        parcial=str(agora.year) if por_ano else trimestre_de(agora))


def trimestre_de(quando):
    """'2026-08-27' -> '2026 T3'. O mesmo formato que o SQL produz."""
    return "%s T%d" % (quando.year, (quando.month + 2) // 3)


def barras_v(linhas, titulo, nota="", parcial="", destaque="", fmt=None):
    """Barras verticais para o tempo, como as dos indicadores.

    O `parcial` e o periodo que ainda esta a decorrer: desenha-se as
    riscas e diz-se que esta a meio. Sem isso, o trimestre corrente
    aparece como uma queda a pique quando e so nao ter acabado -- e a
    conclusao que se tirava dali ("este mercado secou") era falsa.
    """
    if not linhas:
        return ""
    fmt = fmt or euros_curto
    maior = max(l["v"] for l in linhas) or 1
    cols = []
    for l in linhas:
        meio = bool(parcial) and l["t"] == parcial
        realce = bool(destaque) and l["t"] == destaque
        classes = "".join((" parcial" if meio else "",
                           " destaque" if realce else ""))
        cols.append(
            "<div class='col%s'><span class='v'>%s</span>"
            "<div class='b' style='height:%.1f%%' title='%s contratos%s'>"
            "</div><span class='l'>%s</span></div>"
            % (classes, fmt(l["v"]),
               max(2.0, 100.0 * l["v"] / maior), l["k"],
               ", trimestre a decorrer" if meio else
               (", é aqui que cai a mediana" if realce else ""),
               html.escape(l["t"]) + (" ·" if meio else "")))
    return ("<div class='cx graf'><div class='rot'>%s</div>%s"
            "<div class='barras'>%s</div></div>"
            % (titulo,
               "<div class='nota' style='margin:5px 0 16px'>%s</div>" % nota
               if nota else "<div style='height:14px'></div>",
               "".join(cols)))


@app.route("/contratos/resumo")
def contratos_resumo():
    """Os graficos, em HTML, pedidos so quando se abre o painel.

    Sao ~800 ms de consultas sem filtro: a correr a cada visita punham a
    lista lenta para quem so quer a tabela. Devolve HTML e nao JSON de
    proposito -- desenhar continua a ser em Python, como o resto do
    painel, e o JS so tem de o pendurar no sitio.
    """
    if not ha_corpus():
        return Response("", mimetype="text/html")
    ganha, compra, proc, trim, escal = resumo_contratos(request.args)
    if not proc:
        return Response("<div class='nota'>Nada a resumir neste filtro.</div>",
                        mimetype="text/html")
    partes = [
        barras_h(ganha, "Quem ganha",
                 "Valor adjudicado, do maior para o menor. Um contrato "
                 "ganho por um agrupamento reparte-se pelos membros. "
                 "Carrega no nome para a ficha da empresa.", ligar=True),
        barras_h(compra, "Quem compra",
                 "As entidades que mais adjudicaram, por valor.", ligar=True),
        barras_h([{"n": p["p"], "v": p["v"], "k": p["k"]} for p in proc],
                 "Como se compra",
                 "Por tipo de procedimento. O que não é concurso não teve "
                 "anúncio &mdash; não era concorrível."),
        concentracao_html(ganha),
        escaloes_html(escal),
        evolucao_html(trim),
    ]
    return Response("".join(partes), mimetype="text/html")


def liga_entidade(chave, nome, classe=""):
    """O nome de uma entidade, a levar para a ficha dela."""
    if not chave:
        return html.escape(nome or "—")
    return ("<a class='%s' href='/entidade/%s'>%s</a>"
            % (classe, quote(chave, safe=""), html.escape(nome or chave)))


def cpv_html(linhas, titulo, nota, ligar):
    """Os CPV mais fortes, com a descricao do vocabulario quando ha."""
    if not linhas:
        return ""
    with liga() as c:
        desc = {r["codigo8"]: r["descricao"] for r in c.execute(
            "SELECT codigo8, descricao FROM cpv_dict WHERE codigo8 IN (%s)"
            % ",".join("?" * len(linhas)), [l["cod"] for l in linhas])}
    itens = [{"n": "%s — %s" % (l["cod"], desc.get(l["cod"], "sem descrição")),
              "v": l["v"], "k": l["k"], "cod": l["cod"]} for l in linhas]
    return barras_h(itens, titulo, nota, ligar=ligar)


def periodos_rapidos():
    """(etiqueta, de, ate) dos atalhos de tempo da ficha.

    Anos inteiros mais "12 meses" e "3 anos": ver uma entidade so no ano
    passado, ou so no que vai de ano, e a pergunta que se faz a seguir a
    abrir a ficha, e obrigar a escrever duas datas para isso era atrito.
    """
    hoje = datetime.now().date()
    fora = [("12 meses", (hoje - timedelta(days=365)).isoformat(),
             hoje.isoformat()),
            ("3 anos", (hoje - timedelta(days=3 * 365)).isoformat(),
             hoje.isoformat())]
    for ano in range(hoje.year, hoje.year - 4, -1):
        fora.append((str(ano), "%d-01-01" % ano, "%d-12-31" % ano))
    return fora


def filtros_da_ficha(chave, d):
    """A caixa de pesquisa da propria ficha, com atalhos de periodo."""
    def v(nome):
        return html.escape(request.args.get(nome, ""), quote=True)

    de_agora = (request.args.get("de") or "").strip()
    ate_agora = (request.args.get("ate") or "").strip()
    chips = []
    for etiqueta, de, ate in periodos_rapidos():
        activo = de_agora == de and ate_agora == ate
        args = {c: (request.args.get(c) or "").strip()
                for c in CAMPOS_FICHA if (request.args.get(c) or "").strip()}
        if activo:                      # carregar de novo tira o periodo
            args.pop("de", None)
            args.pop("ate", None)
        else:
            args["de"], args["ate"] = de, ate
        chips.append("<a class='%s' href='/entidade/%s?%s'>%s</a>"
                     % ("on" if activo else "", quote(chave, safe=""),
                        urlencode(args), html.escape(etiqueta)))

    limpar = ("<a class='limpar' href='/entidade/%s'>limpar</a>"
              % quote(chave, safe="")) if ha_filtro_na_ficha(request.args) else ""
    cpv_agora = (request.args.get("cpv") or "").strip()
    faixa = ""
    if cpv_agora:
        outros = {c: (request.args.get(c) or "").strip() for c in CAMPOS_FICHA
                  if c != "cpv" and (request.args.get(c) or "").strip()}
        faixa = ("<div class='cpv-activo'>Filtro CPV activo: <b>%s</b>"
                 "<a href='/entidade/%s?%s'>tirar</a></div>"
                 % (html.escape(cpv_agora), quote(chave, safe=""),
                    urlencode(outros)))

    with liga() as c:
        n_cpv = c.execute("SELECT COUNT(*) n FROM cpv_dict").fetchone()["n"]

    # O campo do CPV e escondido e quem escolhe e a arvore, como nas duas
    # listas: onde se pode procurar por CPV, pode-se escolher mais que um.
    return (
        "<form class='cx filtros ent-filtros' method='get' action='/entidade/%s'>"
        "<input type='text' name='q' value='%s' placeholder='Objecto do contrato…'>"
        "<input type='hidden' id='filtro-cpv' name='cpv' value='%s'>"
        "<label>de</label><input type='date' name='de' value='%s'>"
        "<label>até</label><input type='date' name='ate' value='%s'>"
        "<input type='text' name='min' value='%s' placeholder='€ mínimo' "
        "style='min-width:0;width:110px;flex:none'>"
        "<button type='submit'>Filtrar</button>%s"
        "<div class='periodos'><span>rápido:</span>%s</div>"
        "</form>%s%s%s"
        % (quote(chave, safe=""), v("q"), v("cpv"), v("de"), v("ate"),
           v("min"), limpar, "".join(chips), faixa,
           arvore_html(n_cpv, "contratos"),
           # os mesmos filtros guardados dos contratos, mas a voltar para
           # esta ficha e so com os campos que ela entende
           caixa_de_filtros(request.args, "contratos",
                            rota="/entidade/" + quote(chave, safe=""),
                            campos=CAMPOS_FICHA)))


@app.route("/entidade/<path:chave>")
def entidade(chave):
    if not ha_corpus():
        return sem_corpus_html("Entidade")
    d = ficha_entidade(chave, request.args)
    if not d:
        return ("Entidade não encontrada no corpus. "
                "<a href='/contratos'>voltar</a>", 404)

    filtrada = ha_filtro_na_ficha(request.args)
    compra, ganha = d["compra"], d["ganha"]
    kpis = []
    for etiqueta, quantos, valor, sufixo in (
            ("Compra", compra["k"], compra["v"], "adjudicado a outros"),
            ("Ganha", ganha["k"], ganha["v"], "adjudicado a si")):
        kpis.append("<div class='cx kpi'><div class='r'>%s</div>"
                    "<div class='v'>%s</div><div class='d'>%s contrato%s "
                    "&middot; %s</div></div>"
                    % (etiqueta, euros_curto(valor), mil_pt(quantos),
                       "" if quantos == 1 else "s", sufixo))

    # Ligacoes para a lista, ja filtrada por esta entidade nos dois
    # papeis. Levam tambem o filtro da ficha, senao a lista mostrava
    # outra coisa daquela que se esta a ver.
    def para_lista(campo):
        args = {c: v for c, v in ((c, (request.args.get(c) or "").strip())
                                  for c in CAMPOS_FICHA) if v}
        args[campo] = chave
        return "/contratos?" + urlencode(args)

    ligacoes = []
    if compra["k"]:
        ligacoes.append("<a href='%s'>ver os %s contratos que adjudicou</a>"
                        % (para_lista("entid"), mil_pt(compra["k"])))
    if ganha["k"]:
        ligacoes.append("<a href='%s'>ver os %s que ganhou</a>"
                        % (para_lista("vencid"), mil_pt(ganha["k"])))
    atalhos = "<div class='ent-atalhos'>%s</div>" % "".join(ligacoes)

    blocos = []
    if compra["k"]:
        blocos.append(barras_h(d["fornecedores"], "A quem compra",
                               "Os fornecedores que mais receberam desta "
                               "entidade.", ligar=True))
        blocos.append(cpv_html(d["compra_cpv"], "O que compra",
                               "Por CPV, valor repartido quando o contrato "
                               "tem vários.", ligar=False))
        blocos.append(barras_h(
            [{"n": p["p"], "v": p["v"], "k": p["k"]} for p in d["compra_proc"]],
            "Como compra",
            "Por tipo de procedimento. O que não é concurso não teve "
            "anúncio &mdash; não era concorrível."))
        blocos.append(evolucao_html(d["compra_trim"],
                                    "Quanto adjudicou, ao longo do tempo"))
    if ganha["k"]:
        blocos.append(barras_h(d["clientes"], "A quem vende",
                               "As entidades que mais lhe adjudicaram.",
                               ligar=True))
        blocos.append(cpv_html(d["ganha_cpv"], "O que ganha",
                               "Por CPV, com o valor repartido.", ligar=False))
        blocos.append(evolucao_html(d["ganha_trim"],
                                    "Quanto ganhou, ao longo do tempo"))

    if d["recentes"]:
        linhas_r = "".join(
            "<tr><td class='d'>%s</td><td class='o'>%s</td>"
            "<td class='g'>%s</td><td>%s</td><td class='p'>%s</td></tr>"
            % (data_pt(r["data_celebracao"]),
               html.escape((r["objecto"] or "")[:130]),
               liga_entidade(r["adjudicante_chave"], r["outro"]),
               html.escape(r["tipo_procedimento"] or ""),
               euros(r["preco_contratual"]))
            for r in d["recentes"])
        recentes = ("<div class='cx tab-cx' style='margin-top:14px'>"
                    "<table class='tab-contratos'><thead><tr>"
                    "<th>Celebrado</th><th>Objecto</th><th>De quem</th>"
                    "<th>Procedimento</th><th class='p'>Preço</th></tr></thead>"
                    "<tbody>%s</tbody></table></div>" % linhas_r)
    elif filtrada:
        # sem isto, um filtro que nao apanha nada deixava a pagina
        # aparentemente na mesma, so com os numeros a zero
        recentes = ("<div class='vazio'>Esta entidade não tem contratos que "
                    "correspondam ao filtro. "
                    "<a href='/entidade/%s'>ver tudo</a></div>"
                    % quote(chave, safe=""))
    else:
        recentes = ""

    # Os outros nomes por que assina. E o que explica porque e que somar
    # "a olho" pelo nome dava outro numero.
    if d["variantes"] > 1:
        nomes = ("<details class='ent-nomes'><summary>Assina com %d nomes "
                 "diferentes &mdash; todos contam para estes números"
                 "</summary><div>%s</div></details>"
                 % (d["variantes"],
                    "".join("<span>%s</span>" % html.escape(n)
                            for n in d["nomes"])))
    else:
        nomes = ""

    ident = ("<div class='cx ent-cab'><div class='n'>%s</div>"
             "<div class='m'>%s</div>%s</div>"
             % (html.escape(d["nome"]),
                ("NIF %s" % html.escape(d["nif"])) if d["nif"]
                else "sem NIF público &mdash; identificada pelo nome",
                nomes))

    conteudo = ("<div class='larg'>" + ident + filtros_da_ficha(chave, d) +
                "<div class='kpis dois'>" + "".join(kpis) + "</div>" +
                atalhos + "<div class='graf-corpo solto'>" +
                "".join(blocos) + "</div>" + recentes + "</div>")

    return envolver(
        "contratos", d["nome"],
        "O que esta entidade compra e ganha, segundo o Portal BASE.",
        conteudo, script=ARVORE_JS,
        migalhas=migalhas_de("contratos", d["nome"][:44]),
        titulo_aba="%s, Radar de Concursos" % d["nome"][:40])


def sem_corpus_html(titulo):
    return envolver(
        "contratos", titulo,
        "Contratos já celebrados, do Portal BASE &mdash; quem ganhou "
        "o quê, por quanto.",
        "<div class='larg'><div class='vazio'>"
        "O corpus de contratos ainda não foi importado.<br><br>"
        "Corre <code>python radar.py --contratos</code> para o trazer do "
        "dados.gov &mdash; domínio público, sem chave nem sessão. "
        "Dois anos são cerca de dois minutos.</div></div>",
        migalhas=migalhas_de("contratos"),
        titulo_aba="Contratos, Radar de Concursos")


@app.route("/contratos/csv")
def contratos_csv():
    """Exporta o que o filtro apanhou. Os anuncios ja tinham isto e os
    contratos nao -- e sao estes que dao trabalho de analise a serio.

    Sem filtro nao exporta: seriam 1,36 milhoes de linhas e meio GB de
    CSV, que nao e o que ninguem queria pedir.
    """
    if not ha_corpus():
        return redirect("/contratos")
    if not any((request.args.get(campo) or "").strip()
               for campo in CAMPOS_FILTRO_CONTRATOS):
        return redirect("/contratos?aviso=" +
                        quote("Filtra primeiro: o corpus inteiro não se exporta."))
    onde, valores = condicoes_contratos(request.args)
    with liga_corpus() as c:
        linhas = c.execute(
            "SELECT c.data_celebracao, c.objecto, "
            "COALESCE(e.nome, c.adjudicante) adjudicante, "
            "(SELECT group_concat(COALESCE(g.nome, a.nome), ' + ') "
            " FROM contrato_adjudicatario a "
            " LEFT JOIN entidades g ON g.chave=a.chave "
            " WHERE a.contrato_id=c.id) adjudicatarios, "
            "c.tipo_procedimento, c.preco_contratual, c.preco_base, "
            "c.cpv, c.prazo_execucao, c.local_execucao, c.n_anuncio "
            "FROM contratos c LEFT JOIN entidades e "
            " ON e.chave=c.adjudicante_chave" + onde +
            " ORDER BY c.data_celebracao DESC, c.id DESC LIMIT ?",
            valores + [TECTO_CSV]).fetchall()
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";")
    escritor.writerow(["Celebrado", "Objecto", "Entidade adjudicante",
                       "Quem ganhou", "Procedimento", "Preço contratual",
                       "Preço base", "CPV", "Prazo (dias)", "Local",
                       "Anúncio"])
    for a in linhas:
        escritor.writerow([a[k] for k in a.keys()])
    return Response("﻿" + saida.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition":
                             "attachment; filename=contratos.csv"})


@app.route("/contratos/actualizar", methods=["POST"])
def contratos_actualizar():
    actualizar_corpus()
    return redirect("/contratos?" + urlencode(args_da_lista(request.args)))


def espera_corpus():
    """Enquanto a actualizacao corre, a pagina volta a pedir-se sozinha.
    A thread poe sempre um estado terminal (ok/falhou), por isso isto
    para -- nao fica em ciclo."""
    if not actualizacao_a_correr():
        return ""
    return "<script>setTimeout(function(){location.reload()},4000)</script>"


def barra_corpus(anos):
    """Quando foi a ultima vez, e o botao de trazer o que ha de novo."""
    estado = le_marca_corpus("actualizacao", "")
    passo = le_marca_corpus("actualizacao_passo", "")
    quando = le_marca_corpus("ultima_importacao", "nunca")
    a_correr = actualizacao_a_correr()
    if not a_correr and estado == "a correr":
        # ficou a meio quando o painel fechou: nao se perde nada (a
        # importacao substitui o ano inteiro da proxima vez), mas o
        # estado tem de deixar de mentir
        estado, passo = "interrompida", ""
    if a_correr:
        direita = ("<span class='a-correr'>a actualizar&hellip; %s</span>"
                   % html.escape(passo))
    else:
        # leva os filtros de agora, para se voltar ao que se estava a ver
        seguir = urlencode(args_da_lista(request.args))
        direita = accao("/contratos/actualizar" + ("?" + seguir if seguir else ""),
                        "Actualizar contratos")
    aviso = ""
    if estado == "falhou":
        aviso = ("<div class='cpv-activo' style='border-color:#f0c9c3;"
                 "background:#fbe9e6;color:var(--verm)'>A última "
                 "actualização falhou: %s</div>" % html.escape(passo))
    elif estado == "interrompida":
        aviso = ("<div class='cpv-activo'>A última actualização ficou a "
                 "meio &mdash; o painel foi fechado antes de acabar. Nada "
                 "se perdeu: carrega outra vez para a repetir.</div>")
    return ("<div class='corpus-barra'>"
            "<span>Corpus do Portal BASE (IMPIC, dados.gov) &middot; "
            "%s contratos de %s &middot; trazido em %s</span>%s</div>%s"
            % (mil_pt(ha_corpus()),
               "%d a %d" % (anos[0], anos[-1]) if len(anos) > 1
               else (str(anos[0]) if anos else "—"),
               html.escape(quando), direita, aviso))


@app.route("/contratos")
def contratos():
    if not ha_corpus():
        return sem_corpus_html("Contratos celebrados")

    # Sem filtro nao se mostra lista nenhuma. Sao 1,36 milhoes de
    # contratos: por data, sem mais nada, as primeiras 20 nao dizem nada
    # a ninguem -- e era essa consulta que punha a pagina a 48 segundos.
    # Aqui a pergunta vem primeiro, ao contrario dos anuncios, onde a
    # lista inteira e o acervo por triar e faz sentido ve-la.
    ha_pergunta = any((request.args.get(campo) or "").strip()
                      for campo in CAMPOS_FILTRO_CONTRATOS)

    onde, valores = condicoes_contratos(request.args)
    correspondem = valor = 0
    paginas = pagina = 1
    linhas = []
    with liga_corpus() as c:
        if ha_pergunta:
            resumo = c.execute(
                "SELECT COUNT(*) n, COALESCE(SUM(c.preco_contratual),0) v "
                "FROM contratos c" + onde, valores).fetchone()
            correspondem, valor = resumo["n"], resumo["v"]
            paginas = max(1, -(-correspondem // POR_PAGINA))
            pagina = min(max(1, pagina_pedida(request.args)), paginas)
            # Escolhem-se primeiro as 20 linhas, e so depois se lhes vao
            # buscar os nomes: com o LEFT JOIN e as subconsultas por
            # linha a correrem antes do LIMIT, isto levava 45 segundos no
            # corpus de sete anos. E a mesma armadilha do "quem ganha".
            linhas = c.execute(
                "WITH pag AS (SELECT c.* FROM contratos c" + onde +
                " ORDER BY c.data_celebracao DESC, c.id DESC LIMIT ? OFFSET ?)"
                " SELECT p.*, COALESCE(e.nome, p.adjudicante) adj_nome,"
                " (SELECT group_concat(COALESCE(g.nome, a.nome), '|')"
                "  FROM contrato_adjudicatario a"
                "  LEFT JOIN entidades g ON g.chave=a.chave"
                "  WHERE a.contrato_id=p.id) ganhou,"
                " (SELECT group_concat(a.chave, '|') FROM contrato_adjudicatario a"
                "  WHERE a.contrato_id=p.id) ganhou_ch"
                " FROM pag p LEFT JOIN entidades e"
                "  ON e.chave=p.adjudicante_chave"
                " ORDER BY p.data_celebracao DESC, p.id DESC",
                valores + [POR_PAGINA, (pagina - 1) * POR_PAGINA]).fetchall()
        procs = [r["p"] for r in c.execute(
            "SELECT tipo_procedimento p, COUNT(*) n FROM contratos "
            "WHERE tipo_procedimento!='' GROUP BY p ORDER BY n DESC")]
        anos = [r["a"] for r in c.execute(
            "SELECT DISTINCT ano a FROM contratos ORDER BY a")]
    with liga() as c:
        n_cpv = c.execute("SELECT COUNT(*) n FROM cpv_dict").fetchone()["n"]

    proc_actual = (request.args.get("proc") or "").strip()
    opcoes = ["<option value=''>todos os procedimentos</option>"]
    for p in procs:
        opcoes.append("<option value='%s'%s>%s</option>"
                      % (html.escape(p, quote=True),
                         " selected" if p == proc_actual else "",
                         html.escape(p)))

    def v(nome):
        return html.escape(request.args.get(nome, ""), quote=True)

    filtros = (
        "<form class='cx filtros' method='get' action='/contratos'>"
        "<input type='text' name='q' value='%s' placeholder='Objecto do contrato…'>"
        "<input type='text' name='adj' value='%s' placeholder='Entidade adjudicante…'>"
        "<input type='text' name='ganhou' value='%s' placeholder='Quem ganhou…'>"
        # Escondido, como nos anuncios: quem escolhe o CPV e a arvore, e
        # uma caixa de texto ao lado dela so convidava a escrever a mao um
        # codigo que a arvore a seguir apagava. O id e o mesmo nos dois
        # separadores -- e por ele que a arvore le e escreve.
        "<input type='hidden' id='filtro-cpv' name='cpv' value='%s'>"
        "<select name='proc'>%s</select>"
        "<label>de</label><input type='date' name='de' value='%s'>"
        "<label>até</label><input type='date' name='ate' value='%s'>"
        "<label>desde</label><input type='text' name='min' value='%s' "
        "placeholder='€ mínimo' style='min-width:0;width:110px;flex:none'>"
        "<button type='submit'>Filtrar</button>"
        "<a class='limpar' href='/contratos'>limpar</a>"
        "</form>"
        % (v("q"), v("adj"), v("ganhou"), v("cpv"), "".join(opcoes),
           v("de"), v("ate"), v("min")))

    if linhas:
        corpo = []
        for l in linhas:
            # os adjudicatarios vem em duas listas paralelas (nome e
            # chave), separadas por | -- a virgula ja aparece nos nomes
            nomes = (l["ganhou"] or "").split("|")
            chaves = (l["ganhou_ch"] or "").split("|")
            venceu = " + ".join(
                liga_entidade(ch, n) for n, ch in zip(nomes, chaves)
                if n) or "—"
            corpo.append(
                "<tr><td class='d'>%s</td><td class='o'>%s</td>"
                "<td>%s</td><td class='g'>%s</td><td>%s</td>"
                "<td class='p'>%s</td></tr>"
                % (data_pt(l["data_celebracao"]),
                   html.escape((l["objecto"] or "")[:150]),
                   liga_entidade(l["adjudicante_chave"], l["adj_nome"] or ""),
                   venceu,
                   html.escape(l["tipo_procedimento"] or ""),
                   euros(l["preco_contratual"])))
        tabela = ("<div class='cx tab-cx'><table class='tab-contratos'>"
                  "<thead><tr><th>Celebrado</th><th>Objecto</th>"
                  "<th>Entidade</th><th>Quem ganhou</th><th>Procedimento</th>"
                  "<th class='p'>Preço</th></tr></thead><tbody>%s</tbody>"
                  "</table></div>" % "".join(corpo))
    elif ha_pergunta:
        tabela = ("<div class='vazio'>Nada corresponde a este filtro. "
                  "<a href='/contratos'>limpar</a></div>")
    else:
        # A pergunta vem primeiro. Um milhao e meio de contratos por data
        # nao e uma resposta a nada.
        tabela = ("<div class='vazio comecar'>"
                  "<b>Faz uma pergunta ao corpus.</b>"
                  "<span>Escolhe um CPV na árvore, escreve quem ganhou ou "
                  "que entidade comprou, aperta as datas ou o valor. Os "
                  "gráficos e a lista respondem ao filtro que puseres.</span>"
                  "<span class='p'>São %s contratos: sem filtro, os mais "
                  "recentes não dizem nada sobre nada.</span></div>"
                  % mil_pt(ha_corpus()))

    if ha_pergunta:
        conta = "Celebrados mais recentes primeiro &middot; "
        if correspondem > len(linhas):
            primeiro = (pagina - 1) * POR_PAGINA + 1
            conta += ("%s&ndash;%s de %s &middot; página %s de %s"
                      % (mil_pt(primeiro), mil_pt(primeiro + len(linhas) - 1),
                         mil_pt(correspondem), mil_pt(pagina), mil_pt(paginas)))
        else:
            conta += "%s %s" % (mil_pt(correspondem),
                                "contrato" if correspondem == 1 else "contratos")
        # O somatorio e do filtro todo, nao da pagina: e o numero que diz
        # quanto vale este mercado, e por pagina nao queria dizer nada.
        conta += " &middot; <b>%s</b> no total" % euros(valor)
        linha_conta = ("<div class='linha-conta'>" + conta +
                       "<a href='/contratos/csv?%s'>exportar CSV</a></div>"
                       % urlencode(args_da_lista(request.args)))
    else:
        linha_conta = ""

    fonte = ("<div class='nota' style='margin-top:14px'>O dump do IMPIC é "
             "semanal: os contratos das últimas semanas podem ainda não lá "
             "estar. Anos fechados não mudam &mdash; o botão só volta a "
             "trazer o ano corrente e o anterior. Para anos mais antigos, "
             "<code>python radar.py --contratos 2015-2019</code>.</div>")

    # O campo do CPV e escondido, por isso um filtro activo nao se via em
    # lado nenhum a nao ser no chip da arvore, fechada. A faixa diz o que
    # esta a filtrar e da onde carregar para o tirar.
    cpv_actual = (request.args.get("cpv") or "").strip()
    faixas = []
    if cpv_actual:
        sem = args_da_lista(request.args, cpv="")
        faixas.append("<div class='cpv-activo'>Filtro CPV activo: <b>%s</b>"
                      "<a href='/contratos?%s'>tirar</a></div>"
                      % (html.escape(cpv_actual), urlencode(sem)))
    # A chave da entidade e opaca na URL: diz-se de quem e, e da-se a
    # ficha ao lado.
    for campo, papel in (("entid", "adjudicadas por"),
                         ("vencid", "ganhas por")):
        valor = (request.args.get(campo) or "").strip()
        if not valor:
            continue
        with liga_corpus() as c:
            r = c.execute("SELECT nome FROM entidades WHERE chave=?",
                          (valor,)).fetchone()
        sem = args_da_lista(request.args, **{campo: ""})
        faixas.append("<div class='cpv-activo'>Só as %s <b>%s</b>"
                      "<a href='/entidade/%s'>ficha</a>"
                      "<a href='/contratos?%s'>tirar</a></div>"
                      % (papel, html.escape(r["nome"] if r else valor),
                         quote(valor, safe=""), urlencode(sem)))
    faixa_cpv = "".join(faixas)

    # Pedidos so ao abrir, como a arvore: sao ~800 ms de consultas e a
    # tabela nao tem de esperar por eles. Sem filtro nem aparecem: sobre
    # o corpus inteiro demoravam muito e respondiam a pergunta nenhuma.
    graficos = (
        "<details class='arvore graficos'><summary>"
        "<span class='arv-tit'>Ver em gráficos</span>"
        "<span class='arv-sub'>quem ganha, quem compra, como se compra, "
        "concentração, tamanho, evolução &mdash; deste filtro</span></summary>"
        "<div id='graf-corpo' class='graf-corpo'>a carregar…</div>"
        "</details>") if ha_pergunta else ""

    conteudo = ("<div class='larg'>" + barra_corpus(anos) + filtros +
                faixa_cpv + arvore_html(n_cpv, "contratos") +
                caixa_de_filtros(request.args, "contratos") +
                graficos + linha_conta +
                tabela +
                paginador(pagina, paginas, request.args, "/contratos") +
                (fonte if ha_pergunta else "") + "</div>")

    return envolver(
        "contratos", "Contratos celebrados",
        "O que já foi assinado &mdash; quem ganhou, por quanto, de quem. "
        "Não são oportunidades: servem para saber com quem se concorre.",
        conteudo, script=ARVORE_JS + GRAFICOS_JS + espera_corpus(),
        migalhas=migalhas_de("contratos"),
        titulo_aba="Contratos, Radar de Concursos")


# -------------------------------------------------------- ficha do anuncio

def descricoes_cpv(campo_cpv):
    """['72268000 — Servicos de fornecimento de software', ...]

    Uma consulta so para todos os codigos: abrir uma ligacao por codigo
    dentro do ciclo custava tambem dois PRAGMA por volta."""
    codigos = [c8 for c8 in (re.sub(r"\D", "", p)[:8]
                             for p in (campo_cpv or "").split(",")) if c8]
    if not codigos:
        return []
    with liga() as c:
        achados = {r["codigo8"]: r["descricao"] for r in c.execute(
            "SELECT codigo8, descricao FROM cpv_dict WHERE codigo8 IN (%s)"
            % ",".join("?" * len(codigos)), codigos)}
    return ["%s%s" % (c8, " &mdash; " + html.escape(achados[c8])
                      if c8 in achados else "") for c8 in codigos]


def tamanho_legivel(n):
    n = int(n or 0)
    if n >= 1024 * 1024:
        return "%.1f MB" % (n / (1024.0 * 1024))
    if n >= 1024:
        return "%d KB" % (n // 1024)
    return "%d B" % n


def _facto(rotulo, valor, classe="", largo=False):
    if not valor:
        return ""
    return ("<div class='facto%s'><div class='k'>%s</div>"
            "<div class='v %s'>%s</div></div>"
            % (" larg" if largo else "", rotulo, classe, valor))


def criterio_de_adjudicacao(seccoes):
    """Le a seccao 21, que vem de duas maneiras.

    Monofator:  Multifator: Não / Monofator: / Nome: Preço
    Multifator: Multifator: Sim / (Fator: / Nome: X / Ponderação: 50%)+

    Quando o Nome e "Outros", o nome verdadeiro esta em "Outro Nome"."""
    pares = next((p for n, _, p in seccoes if n == "21"), [])
    if not pares:
        return ""                     # ha anuncios sem seccao 21 de todo

    # "Nome: Outros" nunca e o nome verdadeiro -- esse esta em "Outro
    # nome", e vale nos dois ramos. Ler so o "Nome" fazia 9,8% dos
    # anuncios mostrarem "Outros" como criterio, que nao diz nada.
    fatores, nome, outro = [], "", ""

    def resolvido():
        return outro if (not nome or simplifica(nome) == "outros") and outro \
            else nome

    for chave, valor in pares:
        c = radar_chave(chave)
        if c == "nome":
            nome, outro = valor, ""
        elif c in ("outro nome", "outro fator"):
            outro = valor
        elif c == "ponderacao" and resolvido():
            fatores.append("%s %s" % (resolvido(), valor))
            nome, outro = "", ""

    if fatores:
        # ponto literal, nao a entidade: este valor passa por html.escape()
        # ao ser desenhado, e "&middot;" sairia escrito tal e qual
        return " · ".join(fatores)
    return resolvido()                # monofator, ou multifator sem pesos


def radar_chave(chave):
    """A chave sem acentos nem maiusculas, para comparar."""
    return simplifica(chave).strip()


# Os campos que o Afonso quer ver ao abrir um concurso. Os cinco ultimos
# nao estao no anuncio do DR -- vivem no Programa de Concurso e no
# Caderno de Encargos, e ficam assinalados em vez de omitidos, para se
# ver o que falta em vez de parecer que nao existe.
FALTA_CE = "só consta do Caderno de Encargos"
FALTA_PC = "só consta do Programa de Concurso"


def prazo_de_esclarecimentos(data_pub, prazo):
    """Data-limite para pedir esclarecimentos, ou None.

    Regra supletiva do artigo 50.º do CCP: os esclarecimentos pedem-se no
    primeiro terço do prazo fixado para a apresentacao das propostas.
    Encontrada literalmente em 4 dos 6 Programas de Concurso legiveis que
    se leram; os outros dois fixam prazo proprio.

    Por isso isto e um calculo, nao uma leitura do documento -- e aparece
    sempre marcado como supletivo, para se confirmar no PC."""
    try:
        pub = datetime.strptime(data_pub or "", "%Y-%m-%d").date()
        fim = datetime.strptime(prazo or "", "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    dias = (fim - pub).days
    if dias <= 0:
        return None
    return pub + timedelta(days=dias // 3)


def essencial_do_anuncio(a, seccoes, analise=None):
    """[(rotulo, valor, em_falta, nota)] com o essencial para decidir.

    `em_falta` diz onde procurar quando o anuncio nao traz o campo.
    `nota` acompanha um valor que existe mas nao conta a historia toda."""
    def v(*nomes):
        return valor_de(seccoes, *nomes)

    concelho, distrito = v("Concelho"), v("Distrito")
    local = concelho if concelho == distrito else \
        ", ".join(x for x in (concelho, distrito) if x)
    duracao = v("Prazo de execução do contrato")
    if duracao and simplifica(v("Previsão de renovações")) == "sim":
        duracao += " (com renovações previstas)"

    # E um prazo que se perde em silencio: passa muito antes do prazo das
    # propostas e nao ha aviso nenhum quando fecha.
    limite = prazo_de_esclarecimentos(a["data_pub"], a["prazo"])
    if limite:
        dias, passou = dias_restantes(limite.strftime("%Y-%m-%d"))
        esclarecimentos = "%s (%s)" % (
            limite.strftime("%d/%m/%Y"),
            "já passou" if passou else conta_dias(dias))
        esclarec_falta = ""
        esclarec_nota = ("calculado pela regra supletiva do art. 50.º do CCP "
                         "(1.º terço do prazo); confirmar no Programa de Concurso")
    else:
        esclarecimentos, esclarec_nota = "", ""
        esclarec_falta = FALTA_PC

    # Os tres campos que so existem nas pecas vem da leitura pelo modelo,
    # se ela ja tiver corrido. "nao consta" e resposta valida do modelo e
    # trata-se como ausencia.
    def das_pecas(campo):
        if not analise:
            return ""
        try:
            valor = (analise[campo] or "").strip()
        except (KeyError, IndexError):
            # Campo acrescentado depois: uma linha gravada antes dele nao
            # o tem, e um sqlite3.Row rebenta em vez de devolver vazio.
            # E a mesma licao do juntar_leituras -- a ficha inteira nao
            # pode ir abaixo por causa de um campo que ainda nao foi lido.
            return ""
        return "" if simplifica(valor) in ("", "nao consta", "não consta") else valor

    # Nomear as pecas que foram mesmo lidas: numa leitura parcial, dizer
    # "do Caderno de Encargos e do Programa" e afirmar o que nao houve.
    nota_pecas = ("lido de %s por %s — confirmar no documento"
                  % (analise["fontes"] or "peças do procedimento",
                     analise["modelo"])) if analise else ""
    regime = das_pecas("localizacao")
    # Lido o Programa e nao havendo limiar, isso e uma resposta -- e nao a
    # mesma coisa que ainda nao se ter ido ver.
    anormal = das_pecas("preco_anormalmente_baixo")
    anormal_falta = "" if anormal else (
        "o Programa de Concurso não fixa nenhum" if analise else FALTA_PC)

    return [
        ("Nome do projeto", a["titulo"] or v("Designação do contrato"), "", ""),
        ("Entidade adjudicante", a["entidade"], "", ""),
        ("Critério de adjudicação", criterio_de_adjudicacao(seccoes), "", ""),
        ("Preço base", a["preco_base"], "", ""),
        ("Preço anormalmente baixo", anormal, anormal_falta,
         nota_pecas if anormal else ""),
        ("Duração do contrato", duracao, "", ""),
        # O DR chama a esta seccao "LOCAL DA EXECUCAO DO CONTRATO
        # (PROCEDIMENTO)" e o que la esta e, quase sempre, a morada da
        # entidade -- que nao diz se o trabalho e presencial, remoto ou
        # hibrido, que e o que decide se ha alguem para o fazer. Esse
        # regime so esta no Caderno de Encargos: quando a leitura o
        # trouxer, e ele que manda, com o concelho a seguir.
        ("Local de prestação de serviços",
         "%s\n(%s, segundo o anúncio)" % (regime, local) if regime and local
         else (regime or local), "",
         nota_pecas if regime else
         "localização do procedimento; o regime presencial, remoto ou "
         "híbrido consta do Caderno de Encargos e ainda não foi lido"),
        ("Data de esclarecimentos", esclarecimentos, esclarec_falta,
         esclarec_nota),
        ("Data de submissão da proposta", data_pt(a["prazo"], ""), "", ""),
        ("Objeto, âmbito e características", das_pecas("objecto"),
         "" if das_pecas("objecto") else FALTA_CE, nota_pecas),
        ("Equipa", das_pecas("equipa"),
         "" if das_pecas("equipa") else FALTA_CE, nota_pecas),
        ("Documentos que constituem a proposta", das_pecas("documentos_proposta"),
         "" if das_pecas("documentos_proposta") else FALTA_PC, nota_pecas),
    ]


def data_pt(iso, vazio="—"):
    """'2026-08-21' -> '21/08/2026'.

    Guarda-se ISO porque ordena como texto; mostra-se a portuguesa
    porque e assim que se le. Todo o painel passa por aqui -- havia
    tabelas a mostrar a data em ISO e outras a mostra-la em portugues.
    """
    iso = (iso or "").strip()
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return iso or vazio


def mil_pt(n):
    """65869 -> '65 869'. A portuguesa, e com espaco inquebravel: com
    um espaco normal, o browser parte "1 363 300" ao fim da linha e a
    leitura fica com um numero em cada linha."""
    return "{:,}".format(int(n)).replace(",", " ")


def euros(v):
    """1234567.8 -> '1 234 568 EUR'. Os centimos nao ajudam a decidir."""
    return "{:,.0f}".format(v or 0).replace(",", " ") + " €"


def euros_curto(v):
    """Para os graficos, onde '1 661 400 000 EUR' nao se le de relance."""
    v = v or 0
    for corte, sufixo in ((1e9, " mM€"), (1e6, " M€"), (1e3, " k€")):
        if abs(v) >= corte:
            return ("%.1f" % (v / corte)).replace(".", ",") + sufixo
    return "%.0f €" % v


def euros_do_texto(texto):
    """'175.000,00 EUR' -> 175000.0. Formato portugues: o ponto separa
    os milhares e a virgula os centimos, ao contrario do que Python le."""
    m = re.search(r"[\d.,]+", texto or "")
    if not m:
        return None
    try:
        return float(m.group(0).replace(".", "").replace(",", "."))
    except ValueError:
        return None


def referencia_de_preco(chave, cpv, limite=200):
    """Como e que esta entidade tem fechado contratos neste CPV.

    O anuncio traz o preco base; o corpus traz o que se pagou de facto.
    Postos lado a lado dizem se o preco base deste concurso e generoso
    ou apertado para o que esta entidade costuma pagar -- que e a
    pergunta que se faz antes de decidir a proposta.
    """
    prefixos = [p for p in (prefixo_cpv(x) for x in (cpv or "").split(",")) if p]
    if not (chave and prefixos and ha_corpus()):
        return None
    with liga_corpus() as c:
        precos = [r["p"] for r in c.execute(
            "SELECT c.preco_contratual p FROM contratos c "
            "WHERE c.adjudicante_chave=? AND c.preco_contratual > 0 AND "
            "c.id IN (SELECT contrato_id FROM contrato_cpv WHERE %s) "
            "ORDER BY c.data_celebracao DESC LIMIT ?"
            % " OR ".join("cpv8 LIKE ?" for _ in prefixos),
            [chave] + [p + "%" for p in prefixos] + [limite])]
    if len(precos) < 3:                 # com dois contratos nao ha padrao
        return None
    ordenados = sorted(precos)
    meio = len(ordenados) // 2
    mediana = (ordenados[meio] if len(ordenados) % 2
               else (ordenados[meio - 1] + ordenados[meio]) / 2.0)
    return {"quantos": len(precos), "mediana": mediana,
            "menor": ordenados[0], "maior": ordenados[-1],
            "p25": ordenados[len(ordenados) // 4],
            "p75": ordenados[(3 * len(ordenados)) // 4]}


def _mercado_cx(nota, corpo=""):
    return ("<div class='cx mercado'>"
            "<div class='rot'>Histórico de adjudicações</div>"
            "<div class='nota' style='margin:6px 0 12px'>%s</div>%s</div>"
            % (nota, corpo))


def mercado(a):
    """O que esta entidade ja adjudicou **no CPV deste anuncio**.

    E o cruzamento que justifica isto ser uma aplicacao e nao duas: o
    anuncio diz o que vem ai, e o corpus diz como esta entidade se tem
    portado neste tipo de compra -- quem costuma ganhar, por quanto, e
    por que procedimento.

    O CPV restringe e nao so ordena: com a entidade toda, as 25 linhas
    enchiam-se de contratos de limpeza e de refeicoes que nada diziam
    sobre o concurso em maos.
    """
    if not ha_corpus():
        return _mercado_cx(
            "O corpus de contratos ainda não foi importado. Corre "
            "<code>python radar.py --contratos</code> para o trazer do "
            "dados.gov (domínio público, sem chave).")

    linhas, ao_todo, do_cpv, chave = historico_entidade(
        a["entidade"] or "", a["cpv"] or "", nif=a["nif"] or "")
    ficha_ent = ("<a href='/entidade/%s'>ficha da entidade</a>"
                 % quote(chave, safe="")) if chave else ""
    if not ao_todo:
        return _mercado_cx(
            "Não há contratos desta entidade no corpus. Ou nunca adjudicou "
            "nada nos anos importados, ou escreve o nome de outra maneira "
            "no Portal BASE.")
    if not a["cpv"]:
        return _mercado_cx(
            "Este anúncio ainda não tem CPV lido, e sem ele não dá para "
            "escolher o histórico que interessa. A entidade tem %s "
            "contratos no corpus &middot; %s"
            % (mil_pt(ao_todo), ficha_ent))
    if not linhas:
        return _mercado_cx(
            "Esta entidade tem %s contratos no corpus, mas <b>nenhum no CPV "
            "%s</b> &mdash; é a primeira vez que compra isto, pelo menos "
            "nos anos importados. &middot; %s"
            % (mil_pt(ao_todo), html.escape(a["cpv"]), ficha_ent))

    corpo = []
    for l in linhas:
        nomes = (l["ganhou"] or "").split("|")
        chaves = (l["ganhou_ch"] or "").split("|")
        venceu = " + ".join(liga_entidade(ch, n)
                            for n, ch in zip(nomes, chaves) if n) or "—"
        corpo.append(
            "<tr><td class='d'>%s</td><td class='o'>%s</td><td>%s</td>"
            "<td class='g'>%s</td><td class='p'>%s</td></tr>"
            % (data_pt(l["data_celebracao"]),
               html.escape((l["objecto"] or "")[:140]),
               html.escape(l["tipo_procedimento"] or ""),
               venceu,
               euros(l["preco_contratual"])))

    resumo = ("<b>%s contratos desta entidade no CPV %s</b>%s &middot; "
              "de %s ao todo &middot; %s"
              % (mil_pt(do_cpv), html.escape(a["cpv"]),
                 ", os %s mais recentes" % len(linhas)
                 if do_cpv > len(linhas) else "",
                 mil_pt(ao_todo), ficha_ent))

    # O preco base do anuncio contra o que esta entidade tem pago neste
    # CPV. E a informacao que nenhum portal da: diz se o preco base e
    # generoso ou apertado antes de se gastar dias numa proposta.
    ref_preco = ""
    base = euros_do_texto(a["preco_base"])
    r = referencia_de_preco(chave, a["cpv"])
    if r:
        if base:
            razao = base / r["mediana"] if r["mediana"] else 0
            if razao >= 1.25:
                leitura = ("<b class='bom'>acima</b> do que costuma pagar "
                           "&mdash; folga face ao histórico")
            elif razao <= 0.8:
                leitura = ("<b class='mau'>abaixo</b> do que costuma pagar "
                           "&mdash; margem apertada")
            else:
                leitura = "<b>em linha</b> com o que costuma pagar"
            comparacao = ("Preço base deste anúncio: <b>%s</b> &mdash; %s."
                          % (euros(base), leitura))
        else:
            comparacao = ("Este anúncio ainda não tem preço base lido, "
                          "por isso não há com que comparar.")
        ref_preco = (
            "<div class='ref-preco'>%s<div class='escada'>"
            "<span>mais barato<b>%s</b></span>"
            "<span>25%%<b>%s</b></span>"
            "<span class='med'>mediana<b>%s</b></span>"
            "<span>75%%<b>%s</b></span>"
            "<span>mais caro<b>%s</b></span></div>"
            "<div class='nota'>Sobre os %s contratos mais recentes desta "
            "entidade neste CPV. O preço contratual é o de partida, não o "
            "valor final &mdash; adicionais não entram.</div></div>"
            % (comparacao, euros_curto(r["menor"]), euros_curto(r["p25"]),
               euros_curto(r["mediana"]), euros_curto(r["p75"]),
               euros_curto(r["maior"]), mil_pt(r["quantos"])))

    return _mercado_cx(
        resumo,
        ref_preco +
        "<div class='mercado-tab'><table class='tab-mercado'><thead><tr>"
        "<th>Celebrado</th><th>Objecto</th><th>Procedimento</th>"
        "<th>Quem ganhou</th><th class='p'>Preço</th></tr></thead>"
        "<tbody>%s</tbody></table></div>"
        "<div class='nota' style='margin-top:10px'>Contratos já celebrados "
        "por esta entidade neste CPV, do Portal BASE. Não são oportunidades "
        "&mdash; servem para saber com quem se concorre.</div>"
        % "".join(corpo))


@app.route("/anuncio/<path:ref>")
def ficha(ref):
    with liga() as c:
        a = c.execute("SELECT * FROM anuncios WHERE ref=?", (ref,)).fetchone()
    if not a:
        return "Anúncio não encontrado. <a href='/'>voltar</a>", 404

    # Se este anuncio ainda nao foi lido, le-se agora: um pedido, ~1 seg.
    # E o mesmo principio dos documentos -- so se vai buscar o que se abre.
    aviso_leitura = ""
    if not (a["texto"] or ""):
        ok, aviso_leitura = ler_detalhe_de(ref)
        if ok:
            with liga() as c:
                a = c.execute("SELECT * FROM anuncios WHERE ref=?", (ref,)).fetchone()

    with liga() as c:
        docs = c.execute("SELECT * FROM documentos WHERE ref=? ORDER BY nome",
                         (ref,)).fetchall()
        passos = c.execute("SELECT * FROM historico WHERE ref=? "
                           "ORDER BY id DESC LIMIT 12", (ref,)).fetchall()

    completo = request.args.get("modo") == "completo"
    dias, passou = dias_restantes(a["prazo"])

    # --- cabecalho
    rotulo_estado = {"novo": "por ver"}.get(a["estado"], a["estado"])
    classe_estado = {"interessa": "ok", "descartado": ""}.get(a["estado"], "info")
    chips = ["<span class='ref'>Anúncio %s</span>" % html.escape(ref)]
    if a["tipo"]:
        chips.append("<span class='tag'>%s</span>" % html.escape(a["tipo"]))
    chips.append("<span class='tag %s'>%s</span>" % (classe_estado, rotulo_estado))

    if dias is None:
        prazo_v, prazo_c = "", ""
    elif passou:
        prazo_v, prazo_c = "%s (expirado)" % data_pt(a["prazo"]), "mau"
    else:
        prazo_v = "%s (%s)" % (data_pt(a["prazo"]), conta_dias(dias))
        prazo_c = "mau" if dias == 0 else "ok"

    factos = "".join((
        _facto("Publicado", data_pt(a["data_pub"], "")),
        _facto("Propostas até", prazo_v, prazo_c),
        _facto("Preço base", html.escape(a["preco_base"] or "")),
        _facto("Plataforma", html.escape(a["plataforma"] or "")),
        _facto("Estado", rotulo_estado),
        _facto("CPV", "<br>".join(descricoes_cpv(a["cpv"])), largo=True),
    ))

    # O nome da entidade leva à ficha dela quando o corpus a conhece: de
    # um anúncio chega-se ao que aquela entidade costuma comprar sem
    # passar pelo separador dos contratos.
    ch_ent = entidade_do_anuncio(a["nif"] or "", a["entidade"] or "")
    cabeca = ("<div class='cx cabeca'><div class='chips'>%s</div>"
              "<h2>%s</h2><div class='ent'>%s</div>"
              "<div class='factos'>%s</div></div>"
              % ("".join(chips), html.escape(a["titulo"] or ""),
                 liga_entidade(ch_ent, a["entidade"] or "")
                 if ch_ent else html.escape(a["entidade"] or ""),
                 factos))

    # --- accoes
    accoes = []
    if a["estado"] != "interessa":
        accoes.append(accao("/estado/%s/interessa" % ref, "Interessa", "bt verde"))
    if a["estado"] != "descartado":
        accoes.append(accao("/estado/%s/descartado" % ref, "Descartar"))
    if a["estado"] != "novo":
        accoes.append(accao("/estado/%s/novo" % ref, "Pôr por ver"))
    if a["pdf_url"]:
        accoes.append("<a class='bt' href='%s' target='_blank'>PDF oficial</a>"
                      % html.escape(a["pdf_url"], quote=True))
    accoes.append("<a class='bt' href='%s' target='_blank'>Ver no DR</a>"
                  % html.escape(a["url"], quote=True))
    if a["link_pecas"]:
        accoes.append("<a class='bt' href='%s' target='_blank'>Abrir plataforma</a>"
                      % html.escape(a["link_pecas"], quote=True))

    topo = ("<div class='ficha-topo'>"
            "<a class='bt' href='/'>&larr; Voltar à lista</a>"
            "<div class='dir'>%s</div></div>" % "".join(accoes))

    # --- seccoes do anuncio
    seccoes = seccoes_do_texto(a["texto"])

    # No modo essencial mostra-se a tabela do que interessa para decidir,
    # e nao as seccoes em bruto: o DR espalha estes campos por meia duzia
    # de seccoes numeradas, e a maior parte do anuncio e burocracia.
    if seccoes and not completo:
        linhas_ess = []
        for rotulo, valor, em_falta, nota in essencial_do_anuncio(
                a, seccoes, analise_de(ref)):
            if em_falta:
                celula = "<span class='em-falta'>%s</span>" % html.escape(em_falta)
            elif valor:
                celula = html.escape(valor)
                if nota:
                    celula += "<span class='nota-campo'>%s</span>" % html.escape(nota)
            else:
                celula = "<span class='em-falta'>o anúncio não indica</span>"
            linhas_ess.append("<div class='par'><dt>%s</dt><dd>%s</dd></div>"
                              % (html.escape(rotulo), celula))
        seccoes_html = ("<div class='cx essencial'><dl>%s</dl></div>"
                        % "".join(linhas_ess))
        nota_modo = "%d secções lidas do anúncio" % len([s for s in seccoes if s[2]])
    elif seccoes:
        blocos = []
        for numero, titulo_sec, pares in seccoes:
            if not pares:
                continue
            itens = []
            for chave, valor in pares:
                if valor.startswith("http"):
                    valor_html = ("<a href='%s' target='_blank'>%s</a>"
                                  % (html.escape(valor, quote=True), html.escape(valor)))
                else:
                    valor_html = html.escape(valor)
                itens.append("<div class='par'><dt>%s</dt><dd>%s</dd></div>"
                             % (html.escape(chave) if chave else "&nbsp;", valor_html))
            # a dica e o primeiro valor com substancia, para se saber o que
            # ha dentro sem ter de abrir
            dica = next((v for _, v in pares if v and len(v) < 60), "")
            # travessao literal, nao a entidade: isto passa por html.escape()
            # a seguir, e "&mdash;" sairia escrito tal e qual. O titulo fica
            # como vem (ja e maiusculas no DR); o .title() estropiava as
            # preposicoes -- "Objeto Do Contrato".
            cabecalho = ("%s — %s" % (numero, titulo_sec)) \
                if titulo_sec else "Outros"
            blocos.append(
                "<details class='sec'%s><summary>"
                "<span class='st'>%s</span><span class='sh'>%s</span></summary>"
                "<dl>%s</dl></details>"
                % (" open" if len(blocos) < 2 else "", html.escape(cabecalho),
                   html.escape(dica), "".join(itens)))
        seccoes_html = "".join(blocos)
        nota_modo = ("%d secções lidas do anúncio"
                     % len([s for s in seccoes if s[2]]))
    else:
        seccoes_html = ("<div class='vazio'>Não foi possível ler o texto deste "
                        "anúncio: %s</div>"
                        % (html.escape(aviso_leitura) if aviso_leitura else
                           "o DR não devolveu conteúdo."))
        nota_modo = ""

    args_ess = dict(request.args.to_dict()); args_ess.pop("modo", None)
    args_com = dict(request.args.to_dict(), modo="completo")
    modos = ("<div class='modos'><span class='r'>Texto do anúncio:</span>"
             "<a class='%s' href='/anuncio/%s?%s'>Essencial</a>"
             "<a class='%s' href='/anuncio/%s?%s'>Anúncio completo</a>"
             "<span class='dir'>%s</span></div>"
             % ("" if completo else "on", ref, urlencode(args_ess),
                "on" if completo else "", ref, urlencode(args_com), nota_modo))

    # --- coluna da direita
    if dias is None:
        prazo_cx = ""
    else:
        # a barra mostra quanto do prazo ja passou, contando da publicacao
        try:
            pub = datetime.strptime(a["data_pub"], "%Y-%m-%d").date()
            fim = datetime.strptime(a["prazo"], "%Y-%m-%d").date()
            total_dias = max((fim - pub).days, 1)
            decorrido = max(min(total_dias - dias, total_dias), 0)
            pct = int(100.0 * decorrido / total_dias)
        except ValueError:
            pct = 100 if passou else 0
        prazo_cx = ("<div class='prazo-cx'><div class='r'>Propostas até</div>"
                    "<div class='d'>%s</div><div class='n'>%s%s</div>"
                    "<div class='barra-prazo'><i style='width:%d%%'></i></div></div>"
                    % (data_pt(a["prazo"]),
                       "prazo expirado" if passou else conta_dias(dias),
                       (" &middot; " + html.escape(a["plataforma"])) if a["plataforma"] else "",
                       100 if passou else pct))

    # O 'pendente' vem antes do 'docs': ao carregar em "Actualizar peças"
    # ja ca estao as antigas, e a caixa dizia-se pronta enquanto as novas
    # vinham em fundo -- e o obter_documentos apaga-as e volta a inserir.
    if a["docs_estado"] == "pendente":
        # As peças vêm em fundo e demoram entre 1 e 10 segundos. Sem isto
        # a página era desenhada antes de elas existirem e parecia que não
        # tinham vindo -- só recarregando à mão é que apareciam.
        corpo_docs = ("<div class='nota a-trazer'>A trazer as peças da "
                      "plataforma… a página actualiza-se sozinha.</div>")
    elif docs:
        linhas_doc = "".join(
            "<div class='doc'><a href='/documento/%s/%s'>%s</a>"
            "<span class='t'>%s</span></div>"
            % (ref, html.escape(d["nome"], quote=True), html.escape(d["nome"]),
               tamanho_legivel(d["tamanho"]))
            for d in docs)
        # Sucesso parcial tem de se ver: o PDF do anuncio vem sempre, e
        # sozinho parecia que estava tudo trazido.
        if a["docs_estado"] == "parcial":
            cabeca_docs = ("<div class='nota' style='color:#8a5307'>Só veio o "
                           "PDF do anúncio &mdash; as peças do procedimento "
                           "não foi possível trazer da plataforma.</div>")
        elif a["docs_estado"] == "falhou":
            # Falhar a actualizacao com peças antigas em disco nao se via
            # em lado nenhum: a lista continuava ali e parecia recente.
            cabeca_docs = ("<div class='nota' style='color:#8a5307'>Não foi "
                           "possível actualizar as peças na plataforma &mdash; "
                           "as que estão em baixo são as de antes.</div>")
        else:
            cabeca_docs = ("<div class='nota'>Guardadas em documentos/%s.</div>"
                           % html.escape(re.sub(r"[^0-9A-Za-z._-]", "-", ref)))
        analise = analise_de(ref)
        botao_ler = accao("/analisar/%s" % ref,
                          "Reler pelo modelo" if analise else "Ler as peças",
                          "bt" if analise else "bt forte")
        corpo_docs = (cabeca_docs + "<div class='docs'>%s</div>"
                      "<div class='accoes' style='margin-top:14px'>%s%s</div>"
                      % (linhas_doc, botao_ler,
                         accao("/documentos/%s" % ref, "Actualizar peças")))
    else:
        if a["docs_estado"] == "falhou":
            nota = ("Não foi possível trazer as peças automaticamente. A "
                    "plataforma indicada pode exigir sessão iniciada.")
        else:
            nota = ("Ainda não foram trazidas. Vêm sozinhas ao marcar "
                    "&ldquo;interessa&rdquo;.")
        corpo_docs = ("<div class='nota'>%s</div><div style='margin-top:14px'>%s</div>"
                      % (nota, accao("/documentos/%s" % ref, "Trazer peças", "bt forte")))

    chip_plat = ("<span class='tag ok' style='margin-left:auto'>%s</span>"
                 % html.escape(a["plataforma"])) if a["plataforma"] else ""
    docs_cx = ("<div class='cx lado-cx'><div class='cab'>"
               "<span class='rot'>Peças do procedimento</span>%s</div>%s</div>"
               % (chip_plat, corpo_docs))

    resp = a["responsavel"] or ""
    resp_cx = ("<div class='cx lado-cx'><div class='rot' style='margin-bottom:12px'>"
               "Responsável</div>"
               "<form class='resp' method='post' action='/responsavel/%s'>"
               "<div class='av'>%s</div>"
               "<input type='text' name='nome' value='%s' list='pessoas' "
               "placeholder='ninguém atribuído'>"
               "<button type='submit'>guardar</button></form></div>"
               % (ref, _iniciais(resp), html.escape(resp, quote=True)))

    if passos:
        linhas_hist = "".join(
            "<div class='hist'><span class='t'>%s %s %s</span>"
            "<span class='q'>%s</span></div>"
            % (html.escape(p["quem"]), html.escape(p["accao"]),
               html.escape(p["detalhe"] or ""), html.escape(p["quando"]))
            for p in passos)
    else:
        linhas_hist = "<div class='nota'>Ainda não há registo de alterações.</div>"
    hist_cx = ("<div class='cx lado-cx'><div class='rot' style='margin-bottom:6px'>"
               "Histórico</div>%s</div>" % linhas_hist)

    conteudo = ("<div class='larg'>" + topo +
                "<div class='ficha'>"
                "<div class='ficha-esq'>" + cabeca + modos + seccoes_html +
                mercado(a) + "</div>"
                "<div class='ficha-dir'>" + prazo_cx + docs_cx + resp_cx +
                hist_cx + "</div></div></div>")

    migalhas = migalhas_de("anuncios", ref)
    # Enquanto as peças não chegam, a página volta a pedir-se sozinha. O
    # trabalhador põe sempre um estado terminal (ok/parcial/falhou), por
    # isso isto pára -- não fica em ciclo.
    espera = ("<script>setTimeout(function(){location.reload()},3000)</script>"
              if a["docs_estado"] == "pendente" else "")

    return envolver("anuncios", a["titulo"] or ref,
                    "/anuncio/%s &middot; %s" % (html.escape(ref),
                                                 html.escape(a["entidade"] or "")),
                    conteudo, migalhas=migalhas, script=espera,
                    titulo_aba="%s, Radar de Concursos" % ref)


@app.route("/documentos/<path:ref>", methods=["POST"])
def trazer_documentos(ref):
    """Poe na fila em vez de esperar aqui.

    Trazer as pecas e le-las pelo modelo chega a demorar minutos -- tres
    perguntas, cada uma com esperas de ate 70 segundos quando bate no
    tecto por minuto. Feito aqui dentro, o pedido do browser ficava
    pendurado esse tempo todo. A ficha ja sabe mostrar "a trazer as
    pecas..." e recarregar-se sozinha, que e o mesmo caminho de quando
    se marca interessa.

    Sem aviso na ligacao de proposito: o recarregar e um location.reload()
    e leva a query string atras, por isso um "a trazer as pecas..." posto
    aqui ficava colado a pagina depois de a descarga ter acabado -- ou
    falhado. Quem diz em que pe isto vai e a caixa das pecas, que sabe o
    estado a serio.
    """
    pedir_documentos(ref)
    return redirect("/anuncio/" + ref)


@app.route("/analisar/<path:ref>", methods=["POST"])
def analisar(ref):
    """Le o Caderno de Encargos e o Programa com o modelo. Sincrono de
    proposito: demora poucos segundos e o utilizador esta a espera."""
    ok, aviso = analisar_pecas(ref)
    registar(ref, "análise", "peças lidas" if ok else (aviso or "falhou"))
    return redirect("/anuncio/" + ref + "?" + urlencode(
        {"aviso": "peças lidas pelo modelo" if ok else aviso}))


@app.route("/documento/<path:ref>/<nome>")
def servir_documento(ref, nome):
    """Serve um ficheiro guardado. O nome vem da base, mas confirma-se na
    mesma que o caminho final fica dentro da pasta do anuncio."""
    pasta = os.path.abspath(pasta_do_anuncio(ref))
    caminho = os.path.abspath(os.path.join(pasta, nome_seguro(nome)))
    if not caminho.startswith(pasta + os.sep) or not os.path.exists(caminho):
        return "Documento não encontrado. <a href='/anuncio/%s'>voltar</a>" % ref, 404
    return send_file(caminho, as_attachment=False,
                     download_name=os.path.basename(caminho))


# --------------------------------------------------------------- quadro

QUADRO_JS = """<script>
document.querySelectorAll('.carta').forEach(function(carta) {
  carta.addEventListener('dragstart', function(e) {
    e.dataTransfer.setData('text/plain', carta.dataset.ref);
    carta.classList.add('arrastando');
  });
  carta.addEventListener('dragend', function() {
    carta.classList.remove('arrastando');
  });
});
document.querySelectorAll('.coluna-corpo').forEach(function(corpo) {
  corpo.addEventListener('dragover', function(e) {
    e.preventDefault(); corpo.classList.add('sobre');
  });
  corpo.addEventListener('dragleave', function() {
    corpo.classList.remove('sobre');
  });
  corpo.addEventListener('drop', function(e) {
    e.preventDefault();
    corpo.classList.remove('sobre');
    var ref = e.dataTransfer.getData('text/plain');
    var carta = document.querySelector('.carta[data-ref="' + CSS.escape(ref) + '"]');
    if (!carta) return;
    var vazio = corpo.querySelector('.coluna-vazia');
    if (vazio) vazio.remove();
    corpo.appendChild(carta);
    fetch('/quadro/mover', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ref: ref, fase_id: corpo.dataset.fase})
    }).then(function(r) {
      // o cartao ja foi movido no ecra; se o servidor recusou, o ecra
      // esta a mentir e tem de voltar ao que a base diz
      if (!r.ok) { alert('Não foi possível mover o cartão.'); location.reload(); }
    }).catch(function() {
      alert('Falhou a gravar, recarrega a página.'); location.reload();
    });
  });
});
</script>"""


def cartao(a, etiquetas_por_ref):
    texto_prazo, classe_prazo = etiqueta_prazo(a["prazo"])
    prazo_html = ("<span class='tag %s'>&#9679; %s</span>"
                  % (classe_prazo, texto_prazo)) if texto_prazo else ""
    preco_html = ("<span class='carta-preco'>%s</span>"
                  % html.escape(a["preco_base"])) if a["preco_base"] else ""
    etiquetas_html = "".join(
        "<span class='etq' style='background:%s'>%s%s</span>"
        % (e["cor"], html.escape(e["nome"]),
           accao("/quadro/etiqueta/%s/tirar/%d" % (a["ref"], e["id"]),
                 "&times;", "etq-x"))
        for e in etiquetas_por_ref.get(a["ref"], []))
    dono = ("<span class='av'>%s</span>" % _iniciais(a["responsavel"])) \
        if a["responsavel"] else ""
    return (
        "<div class='carta' draggable='true' data-ref='%s'>"
        "<a href='/anuncio/%s' class='carta-titulo'>%s</a>"
        "<div class='carta-entidade'>%s</div>"
        "<div class='carta-meta'>%s%s</div>"
        "<div class='carta-etq'>%s"
        "<form class='etq-form' method='post' action='/quadro/etiqueta/%s/nova'>"
        "<input type='text' name='nome' placeholder='+ etiqueta' "
        "list='etiquetas-existentes' maxlength='24'></form></div>"
        "<div class='carta-pe'>%s%s</div>"
        "</div>"
        % (a["ref"], a["ref"], html.escape(a["titulo"][:120]),
           html.escape(a["entidade"]), preco_html, prazo_html,
           etiquetas_html, a["ref"],
           accao("/estado/%s/novo" % a["ref"], "tirar do quadro", "tirar"), dono))


@app.route("/quadro")
def quadro():
    fases = listar_fases()
    with liga() as c:
        cartas = c.execute(
            "SELECT * FROM anuncios WHERE estado='interessa' "
            "ORDER BY data_pub DESC").fetchall()
        todas_etiquetas = c.execute("SELECT * FROM etiquetas ORDER BY nome").fetchall()
        pares = c.execute("SELECT * FROM anuncio_etiquetas").fetchall()

    etiquetas_por_id = {e["id"]: e for e in todas_etiquetas}
    etiquetas_por_ref = {}
    for p in pares:
        if p["etiqueta_id"] in etiquetas_por_id:
            etiquetas_por_ref.setdefault(p["ref"], []).append(
                etiquetas_por_id[p["etiqueta_id"]])

    por_fase = {}
    for a in cartas:
        por_fase.setdefault(a["fase_id"], []).append(a)

    colunas = []
    for f in fases:
        itens = por_fase.get(f["id"], [])
        corpo = "".join(cartao(a, etiquetas_por_ref) for a in itens) or \
            "<div class='coluna-vazia'>sem cartões, arrasta um para aqui</div>"
        colunas.append(
            "<div class='coluna'><div class='coluna-cab'>"
            "<form method='post' action='/quadro/fase/%d/renomear'>"
            "<input class='fase-nome' type='text' name='nome' value='%s' "
            "onblur='this.form.requestSubmit()'></form>"
            "<span class='coluna-conta'>%d</span>"
            "<form method='post' action='/quadro/fase/%d/apagar' "
            "onsubmit='return confirm(\"Apagar esta fase? Os cartões voltam "
            "para a primeira fase.\")'>"
            "<button type='submit' class='fase-apagar' title='apagar fase'>"
            "&times;</button></form></div>"
            "<div class='coluna-corpo' data-fase='%d'>%s</div></div>"
            % (f["id"], html.escape(f["nome"], quote=True), len(itens),
               f["id"], f["id"], corpo))

    datalist = "".join("<option value='%s'>" % html.escape(e["nome"], quote=True)
                       for e in todas_etiquetas)

    conteudo = ("<div class='quadro-topo'>"
                "<span class='d'>Só entram anúncios marcados como "
                "&ldquo;interessa&rdquo; &middot; arrastar move de fase &middot; "
                "o nome da fase edita-se no sítio</span>"
                "<form method='post' action='/quadro/fase/nova'>"
                "<input type='text' name='nome' placeholder='nome da nova fase' required>"
                "<button type='submit' class='bt forte'>+ Nova fase</button>"
                "</form></div>"
                "<div class='quadro'>%s</div>"
                "<datalist id='etiquetas-existentes'>%s</datalist>"
                % ("".join(colunas), datalist))

    migalhas = migalhas_de("quadro")
    return envolver("quadro", "Quadro",
                    "Fases editáveis &middot; só anúncios marcados como "
                    "&ldquo;interessa&rdquo;.",
                    conteudo, migalhas=migalhas, script=QUADRO_JS,
                    titulo_aba="Quadro, Radar de Concursos")


# ----------------------------------------------------------- calendario

DIAS_CALENDARIO = 45


@app.route("/calendario")
def calendario():
    hoje = datetime.now().date()
    with liga() as c:
        cartas = c.execute(
            "SELECT * FROM anuncios WHERE estado='interessa' AND prazo != '' "
            "ORDER BY prazo").fetchall()
        fases_por_id = {f["id"]: f["nome"] for f in listar_fases()}

    migalhas = migalhas_de("calendario")
    envolve = lambda corpo: envolver(
        "calendario", "Calendário",
        "Prazos dos anúncios interessados, %d dias a partir de hoje."
        % DIAS_CALENDARIO, corpo, migalhas=migalhas,
        titulo_aba="Calendário, Radar de Concursos")

    if not cartas:
        return envolve("<div class='vazio'>Sem anúncios interessados com prazo. "
                       "Marca alguns como &ldquo;interessa&rdquo; na lista.</div>")

    grelha = "grid-template-columns:260px repeat(%d,52px)" % DIAS_CALENDARIO

    def classes_do_dia(i, dia):
        """Sem isto a grade e uma tira de 45 numeros onde nao se distingue
        um sabado de uma terca -- e um prazo ao fim-de-semana importa."""
        cs = ["cel-dia"]
        if i == 0:
            cs.append("hoje")
        if dia.weekday() >= 5:
            cs.append("fds")
        if dia.day == 1 and i:
            cs.append("mes-novo")
        return " ".join(cs)

    cabecalho = ["<div class='linha-grade cab' style='%s'>"
                 "<div class='cel-titulo'>Anúncio &middot; %d dias a partir de hoje</div>"
                 % (grelha, DIAS_CALENDARIO)]
    for i in range(DIAS_CALENDARIO):
        dia = hoje + timedelta(days=i)
        cabecalho.append("<div class='%s'><div class='s'>%s</div>"
                         "<div class='n'>%02d</div><div class='m'>%s</div></div>"
                         % (classes_do_dia(i, dia), DIAS_SEMANA[dia.weekday()],
                            dia.day, MESES[dia.month - 1]))
    cabecalho.append("</div>")

    cores = {"ok": ("#e6f2ea", "#1e8449"), "avisa": ("#fdf1de", "#8a5307"),
             "mau": ("#fbe3e0", "#c0392b")}
    linhas, fora = [], 0
    for a in cartas:
        try:
            alvo = datetime.strptime(a["prazo"], "%Y-%m-%d").date()
        except ValueError:
            continue
        posicao = (alvo - hoje).days
        if posicao < 0 or posicao >= DIAS_CALENDARIO:
            fora += 1
            continue
        _, classe = etiqueta_prazo(a["prazo"])
        fundo, frente = cores.get(classe, ("#eef4fa", "#1f4e79"))
        fase_nome = fases_por_id.get(a["fase_id"], "") or "prazo"
        celulas = []
        for i in range(DIAS_CALENDARIO):
            classes = classes_do_dia(i, hoje + timedelta(days=i))
            if i == posicao:
                celulas.append("<div class='%s cel-pilula'>"
                               "<a class='pilula' style='background:%s;color:%s' "
                               "href='/anuncio/%s' title='%s'>%s</a></div>"
                               % (classes, fundo, frente, a["ref"],
                                  html.escape(a["prazo"], quote=True),
                                  html.escape(fase_nome)))
            else:
                celulas.append("<div class='%s'></div>" % classes)
        linhas.append("<div class='linha-grade' style='%s'>"
                      "<div class='cel-titulo'><a href='/anuncio/%s'>%s</a>"
                      "<div class='ent'>%s</div></div>%s</div>"
                      % (grelha, a["ref"], html.escape(a["titulo"][:70]),
                         html.escape(a["entidade"]), "".join(celulas)))

    nota = ("<div class='nota' style='margin-top:14px'>%d anúncio(s) "
            "interessado(s) têm prazo fora da janela de %d dias e não "
            "aparecem na grade &mdash; continuam no quadro.</div>"
            % (fora, DIAS_CALENDARIO)) if fora else ""

    return envolve("<div class='larg'><div class='grade-caixa'>"
                   "<div class='grade-rolo'>%s%s</div></div>%s</div>"
                   % ("".join(cabecalho), "".join(linhas), nota))


# --------------------------------------------------------- indicadores

def funil_anuncios():
    """Como corre a triagem: quanto entra, quanto se olha, quanto vinga.

    Os indicadores contavam estados e mais nada. O que falta saber e o
    movimento -- quanto do que entra chega a interessar, quanto tempo
    fica por ver, e em que CPV se descarta sempre. Isso diz onde se
    perde tempo, que as contagens paradas nao dizem.
    """
    hoje = datetime.now().date()
    d = {}
    with liga() as c:
        d["entrados"] = c.execute(
            "SELECT COUNT(*) n FROM anuncios WHERE data_pub >= ?",
            ((hoje - timedelta(days=30)).isoformat(),)).fetchone()["n"]
        d["triados"] = c.execute(
            "SELECT COUNT(*) n FROM anuncios WHERE estado != 'novo'").fetchone()["n"]
        d["interessa"] = c.execute(
            "SELECT COUNT(*) n FROM anuncios WHERE estado='interessa'").fetchone()["n"]
        d["descartados"] = c.execute(
            "SELECT COUNT(*) n FROM anuncios WHERE estado='descartado'").fetchone()["n"]
        d["total"] = c.execute("SELECT COUNT(*) n FROM anuncios").fetchone()["n"]
        # Por ver e com prazo a passar: e a fila que custa dinheiro, e
        # nenhum ecra a mostrava.
        d["urgentes_por_ver"] = c.execute(
            "SELECT COUNT(*) n FROM anuncios WHERE estado='novo' "
            "AND prazo >= ? AND prazo <= ?",
            (hoje.isoformat(),
             (hoje + timedelta(days=10)).isoformat())).fetchone()["n"]
        d["expirados_por_ver"] = c.execute(
            "SELECT COUNT(*) n FROM anuncios WHERE estado='novo' "
            "AND prazo != '' AND prazo < ?", (hoje.isoformat(),)).fetchone()["n"]
        # Onde a triagem tem acontecido, por divisao de CPV
        d["por_divisao"] = c.execute(
            "SELECT substr(cpv,1,2) div, "
            " SUM(estado='interessa') sim, SUM(estado='descartado') nao, "
            " COUNT(*) tudo FROM anuncios WHERE cpv != '' AND estado != 'novo' "
            "GROUP BY div ORDER BY tudo DESC LIMIT 8").fetchall()
    return d


def linhas_de_saude(itens, cor_ma="#c0392b"):
    """As linhas de (rotulo, valor, esta_bem) da coluna dos indicadores."""
    return "".join(
        "<div class='l'><span class='ponto' style='background:%s'></span>"
        "<span class='t'>%s</span><span class='v'>%s</span></div>"
        % ("#1e8449" if bom else cor_ma, t, v) for t, v, bom in itens)


@app.route("/indicadores")
def indicadores():
    """Numeros sobre a propria base. Sem servicos externos: e tudo SQL
    sobre o radar.db."""
    hoje = datetime.now().date()
    with liga() as c:
        total = c.execute("SELECT COUNT(*) n FROM anuncios").fetchone()["n"]
        hoje_n = c.execute("SELECT COUNT(*) n FROM anuncios WHERE data_pub=?",
                           (hoje.strftime("%Y-%m-%d"),)).fetchone()["n"]
        interessa = c.execute("SELECT COUNT(*) n FROM anuncios "
                              "WHERE estado='interessa'").fetchone()["n"]
        urgentes = c.execute(
            "SELECT COUNT(*) n FROM anuncios WHERE estado='interessa' "
            "AND prazo >= ? AND prazo <= ?",
            (hoje.strftime("%Y-%m-%d"),
             (hoje + timedelta(days=7)).strftime("%Y-%m-%d"))).fetchone()["n"]
        porler = c.execute("SELECT COUNT(*) n FROM anuncios "
                           "WHERE detalhe_lido=0").fetchone()["n"]
        fases = listar_fases()
        por_fase = {f["id"]: 0 for f in fases}
        for r in c.execute("SELECT fase_id, COUNT(*) n FROM anuncios "
                           "WHERE estado='interessa' GROUP BY fase_id"):
            if r["fase_id"] in por_fase:
                por_fase[r["fase_id"]] = r["n"]
        plataformas = c.execute(
            "SELECT COALESCE(NULLIF(plataforma,''),'(nenhuma)') p, COUNT(*) n "
            "FROM anuncios WHERE detalhe_lido=1 GROUP BY p ORDER BY n DESC").fetchall()
        com_detalhe = c.execute("SELECT COUNT(*) n FROM anuncios "
                                "WHERE detalhe_lido=1").fetchone()["n"]
        n_docs = c.execute("SELECT COUNT(*) n FROM documentos").fetchone()["n"]

    mil = mil_pt

    kpis = [("Anúncios na base", mil(total), "%s com detalhe lido" % mil(com_detalhe), ""),
            ("Novos hoje", mil(hoje_n), "a parte L publica ~60-70/dia", ""),
            ("Interessa", mil(interessa),
             "%s com prazo a menos de 7 dias" % mil(urgentes),
             "color:#c0392b" if urgentes else ""),
            ("Sem detalhe lido", mil(porler),
             "lidos ao abrir a ficha, ou em rotina", "color:#d68910" if porler else "")]
    kpis_html = "".join(
        "<div class='kpi'><div class='r'>%s</div><div class='v'>%s</div>"
        "<div class='d' style='%s'>%s</div></div>" % (r, v, estilo, d)
        for r, v, d, estilo in kpis)

    maior = max(list(por_fase.values()) + [1])
    cores_barra = ("#c9c4b8", "#1f4e79", "#d68910", "#12141a", "#1e8449")
    barras = "".join(
        "<div class='col'><span class='v'>%d</span>"
        "<div class='b' style='height:%d%%;background:%s'></div>"
        "<span class='l'>%s</span></div>"
        % (por_fase[f["id"]], int(88.0 * por_fase[f["id"]] / maior) + 6,
           cores_barra[i % len(cores_barra)], html.escape(f["nome"]))
        for i, f in enumerate(fases))
    if not fases:
        barras = "<div class='nota'>Ainda não há fases no quadro.</div>"

    tem_dr = "válido" if carregar_curl() else "em falta"
    tem_det = "válido" if carregar_curl("curl_detalhe") else "em falta"
    saude = [("Captura curl_DR.txt", tem_dr, tem_dr == "válido"),
             ("Captura curl_detalhe.txt", tem_det, tem_det == "válido")]
    # "(nenhuma)" nao e uma plataforma que recuse acesso: sao anuncios
    # onde o proprio DR nao diz qual e. Dizer "sem acesso" a vermelho
    # fazia parecer um bloqueio que nao existe.
    for p in plataformas:
        pct = 100.0 * p["n"] / max(com_detalhe, 1)
        nome = p["p"]
        if nome == "(nenhuma)":
            rotulo, valor, bom = ("Anúncios sem plataforma indicada",
                                  "%.1f%%" % pct, True)
        else:
            obtem = nome in PLATAFORMAS_COM_PECAS
            rotulo = "Peças &middot; %s" % html.escape(nome)
            valor = "%.1f%%%s" % (pct, "" if obtem else " sem acesso")
            bom = obtem
        saude.append((rotulo, valor, bom))
    saude.append(("Documentos guardados", mil(n_docs), True))
    try:
        tam = os.path.getsize(DB) / (1024.0 * 1024)
        with liga() as c:
            modo = c.execute("PRAGMA journal_mode").fetchone()[0]
        saude.append(("Base de dados", "%.0f MB &middot; %s" % (tam, modo.upper()), True))
    except OSError:
        pass

    # O corpus do BASE e a segunda metade da aplicacao, e estava fora
    # desta pagina -- os indicadores diziam que estava tudo bem sem
    # sequer olhar para ele.
    n_corpus = ha_corpus()
    if n_corpus:
        with liga_corpus() as c:
            anos_c = [r["a"] for r in
                      c.execute("SELECT DISTINCT ano a FROM contratos ORDER BY a")]
            n_ent = c.execute("SELECT COUNT(*) n FROM entidades").fetchone()["n"]
        quando = le_marca_corpus("ultima_importacao", "nunca")
        # o dump e semanal; passar de duas semanas quer dizer que ficou
        # para tras, e e a unica coisa aqui que pode estar "mal"
        fresco = True
        try:
            dias = (datetime.now()
                    - datetime.strptime(quando[:10], "%Y-%m-%d")).days
            fresco = dias <= 14
            idade = ("hoje" if dias == 0 else
                     "ontem" if dias == 1 else "há %d dias" % dias)
        except ValueError:
            idade = quando
        corpus = [
            ("Contratos no corpus", mil(n_corpus), True),
            ("Anos cobertos", "%d a %d" % (anos_c[0], anos_c[-1])
             if len(anos_c) > 1 else str(anos_c[0]), True),
            ("Entidades identificadas", mil(n_ent), True),
            ("Última importação", idade, fresco),
            ("Ficheiro do corpus",
             "%.0f MB" % (os.path.getsize(CORPUS) / (1024.0 * 1024)), True),
        ]
    else:
        corpus = [("Corpus de contratos", "por importar", False)]
    # o corpus avisa a amarelo e a recolha a vermelho: um corpus velho
    # e uma coisa a fazer quando der jeito, uma captura expirada e o
    # radar parado
    corpus_html = linhas_de_saude(corpus, "#d68910")
    saude_html = linhas_de_saude(saude)

    # O funil: o que entra, o que se olha, o que vinga. Os indicadores
    # contavam estados parados e nao diziam nada sobre o movimento.
    f = funil_anuncios()
    porver = f["total"] - f["triados"]
    passos = [("Entrados (30 dias)", f["entrados"], "var(--t3)"),
              ("Por ver", porver, "#d68910"),
              ("Triados", f["triados"], "var(--azul)"),
              ("Interessa", f["interessa"], "var(--verde)")]
    maior_f = max([p[1] for p in passos] + [1])
    funil_html = "".join(
        "<div class='col'><span class='v'>%s</span>"
        "<div class='b' style='height:%d%%;background:%s'></div>"
        "<span class='l'>%s</span></div>"
        % (mil_pt(n), int(88.0 * n / maior_f) + 6, cor, etiqueta)
        for etiqueta, n, cor in passos)

    if f["triados"]:
        taxa = 100.0 * f["interessa"] / f["triados"]
        leitura = ("De tudo o que já triaste, <b>%.0f%%</b> ficou como "
                   "interessa." % taxa)
    else:
        leitura = "Ainda não triaste nada, por isso não há taxa a mostrar."
    alertas = []
    if f["urgentes_por_ver"]:
        alertas.append("<b>%s por ver com prazo a menos de 10 dias</b>"
                       % mil_pt(f["urgentes_por_ver"]))
    if f["expirados_por_ver"]:
        alertas.append("%s por ver já com o prazo passado"
                       % mil_pt(f["expirados_por_ver"]))
    if alertas:
        leitura += " " + " &middot; ".join(alertas) + "."

    if f["por_divisao"]:
        with liga() as c:
            nomes_div = {r["codigo8"][:2]: r["descricao"] for r in c.execute(
                "SELECT codigo8, descricao FROM cpv_dict WHERE codigo8 IN (%s)"
                % ",".join("?" * len(f["por_divisao"])),
                [r["div"] + "000000" for r in f["por_divisao"]])}
        divisoes = "".join(
            "<div class='l'><span class='t'>%s &mdash; %s</span>"
            "<span class='v'>%s de %s</span></div>"
            % (html.escape(r["div"]),
               html.escape(nomes_div.get(r["div"], "sem descrição"))[:40],
               mil_pt(r["sim"]), mil_pt(r["tudo"]))
            for r in f["por_divisao"])
        divisoes = ("<div class='rot' style='margin:22px 0 16px'>Onde a "
                    "triagem tem dito que sim</div><div class='saude'>%s</div>"
                    % divisoes)
    else:
        divisoes = ("<div class='nota' style='margin-top:16px'>Ainda não há "
                    "triagem que chegue para dizer em que CPV costumas "
                    "dizer que sim.</div>")

    # Montado a parte e passado como argumento: a `leitura` traz um "%"
    # (a taxa de conversao) e, concatenado no template, o `%` de baixo
    # tentava interpreta-lo como conversao.
    funil_cx = ("<div class='cx' style='padding:22px 24px'>"
                "<div class='rot' style='margin-bottom:6px'>Funil da "
                "triagem</div>"
                "<div class='nota' style='margin-bottom:18px'>" + leitura +
                "</div><div class='barras'>" + funil_html + "</div>" +
                divisoes + "</div>")

    conteudo = (
        "<div class='larg' style='display:flex;flex-direction:column;gap:18px'>"
        "<div class='kpis'>%s</div>"
        "%s"
        "<div class='ind-grelha'>"
        "<div class='cx' style='padding:22px 24px'>"
        "<div class='rot' style='margin-bottom:22px'>Interessados por fase do quadro</div>"
        "<div class='barras'>%s</div></div>"
        "<div class='cx' style='padding:22px 24px'>"
        "<div class='rot' style='margin-bottom:16px'>Estado da recolha</div>"
        "<div class='saude'>%s</div>"
        "<div class='rot' style='margin:22px 0 16px'>Corpus de contratos "
        "(Portal BASE)</div><div class='saude'>%s</div>"
        "<div class='nota' style='margin-top:14px'>Ficheiro à parte, "
        "<code>contratos.db</code>. Actualiza-se em "
        "<a href='/contratos'>Contratos</a>.</div></div>"
        "</div></div>" % (kpis_html, funil_cx, barras, saude_html, corpus_html))

    migalhas = migalhas_de("indicadores")
    return envolver("indicadores", "Indicadores",
                    "Consultas directas às duas bases &mdash; os anúncios do "
                    "DR e o corpus do BASE. Sem serviços externos.",
                    conteudo, migalhas=migalhas,
                    titulo_aba="Indicadores, Radar de Concursos")


@app.route("/quadro/mover", methods=["POST"])
def quadro_mover():
    dados = request.get_json(silent=True) or {}
    ref, fase_id = dados.get("ref"), dados.get("fase_id")
    if not ref or not fase_id:
        return {"ok": False, "erro": "faltam dados"}, 400
    try:
        fase_id = int(fase_id)
    except (TypeError, ValueError):
        return {"ok": False, "erro": "fase inválida"}, 400
    with liga() as c:
        # A fase tem de existir: sem isto um fase_id inventado punha o
        # cartao numa coluna que nao e desenhada em lado nenhum, e ele
        # desaparecia do quadro sem voltar a lista.
        fase = c.execute("SELECT nome FROM fases WHERE id=?", (fase_id,)).fetchone()
        if not fase:
            return {"ok": False, "erro": "fase inexistente"}, 404
        cur = c.execute("UPDATE anuncios SET fase_id=? "
                        "WHERE ref=? AND estado='interessa'", (fase_id, ref))
        if not cur.rowcount:
            return {"ok": False, "erro": "anúncio não está no quadro"}, 404
    registar(ref, "fase", fase["nome"])
    return {"ok": True}


@app.route("/quadro/fase/nova", methods=["POST"])
def fase_nova():
    nome = (request.form.get("nome") or "").strip()
    if nome:
        with liga() as c:
            maior = c.execute("SELECT MAX(ordem) m FROM fases").fetchone()["m"] or 0
            c.execute("INSERT INTO fases (nome, ordem) VALUES (?,?)", (nome, maior + 1))
    return redirect("/quadro")


@app.route("/quadro/fase/<int:fase_id>/renomear", methods=["POST"])
def fase_renomear(fase_id):
    nome = (request.form.get("nome") or "").strip()
    if nome:
        with liga() as c:
            c.execute("UPDATE fases SET nome=? WHERE id=?", (nome, fase_id))
    return redirect("/quadro")


@app.route("/quadro/fase/<int:fase_id>/apagar", methods=["POST"])
def fase_apagar(fase_id):
    with liga() as c:
        total = c.execute("SELECT COUNT(*) n FROM fases").fetchone()["n"]
        if total > 1:
            sobra = c.execute(
                "SELECT id FROM fases WHERE id != ? ORDER BY ordem, id LIMIT 1",
                (fase_id,)).fetchone()
            c.execute("UPDATE anuncios SET fase_id=? WHERE fase_id=?",
                      (sobra["id"], fase_id))
            c.execute("DELETE FROM fases WHERE id=?", (fase_id,))
    return redirect("/quadro")


@app.route("/quadro/etiqueta/<path:ref>/nova", methods=["POST"])
def etiqueta_nova(ref):
    nome = (request.form.get("nome") or "").strip()
    if nome:
        with liga() as c:
            existente = c.execute(
                "SELECT id FROM etiquetas WHERE nome=? COLLATE NOCASE", (nome,)).fetchone()
            if existente:
                etiqueta_id = existente["id"]
            else:
                n = c.execute("SELECT COUNT(*) n FROM etiquetas").fetchone()["n"]
                cor = CORES_ETIQUETA[n % len(CORES_ETIQUETA)]
                cur = c.execute("INSERT INTO etiquetas (nome, cor) VALUES (?,?)", (nome, cor))
                etiqueta_id = cur.lastrowid
            c.execute("INSERT OR IGNORE INTO anuncio_etiquetas VALUES (?,?)",
                      (ref, etiqueta_id))
    return redirect("/quadro")


@app.route("/quadro/etiqueta/<path:ref>/tirar/<int:etiqueta_id>", methods=["POST"])
def etiqueta_tirar(ref, etiqueta_id):
    with liga() as c:
        c.execute("DELETE FROM anuncio_etiquetas WHERE ref=? AND etiqueta_id=?",
                  (ref, etiqueta_id))
    return redirect("/quadro")


# ------------------------------------------------------------- arranque

def main():
    iniciar_db()
    cfg = ler_config()

    if "--importar-cpv" in sys.argv:
        i = sys.argv.index("--importar-cpv")
        caminho = sys.argv[i + 1] if i + 1 < len(sys.argv) else \
            os.path.join(BASE_DIR, "cpv-2024.json")
        n = importar_cpv_dict(caminho)
        print("dicionario de CPV importado: %d codigos" % n)
        return

    if "--contratos" in sys.argv:
        # Corpus de contratos ja celebrados, do dump semanal do IMPIC.
        # Nao e o funil: e o historico para saber quem ganha o que.
        # "--contratos" sozinho traz o ano corrente e o anterior;
        # "--contratos 2019-2026" ou "--contratos 2024 2025" tambem servem.
        i = sys.argv.index("--contratos")
        pedido = [a for a in sys.argv[i + 1:] if not a.startswith("--")]
        anos = anos_pedidos(pedido)
        print("a trazer contratos de %s do dados.gov (dominio publico, "
              "sem chave). Cada ano sao dezenas de MB." %
              ", ".join(str(a) for a in anos))
        n = importar_contratos(anos)
        print("%d contratos no corpus deste arranque; %d ao todo em %s"
              % (n, ha_corpus(), os.path.basename(CORPUS)))
        return

    if "--historico" in sys.argv:
        i = sys.argv.index("--historico")
        dias = int(sys.argv[i + 1]) if i + 1 < len(sys.argv) else 730
        print("a puxar %d dias de historico, isto demora (uma pagina por "
              "segundo, para nao castigar o portal)..." % dias)
        cfg_historico = dict(cfg, dias_catchup=dias)
        mensagem, novos = verificar(cfg_historico)
        print(mensagem)
        return

    if "--reler" in sys.argv:
        # Manutencao, nao uso diario: so faz sentido depois de mexer em
        # campos_do_detalhe(). Nao toca na rede -- reanalisa o texto que
        # ja esta guardado, uns segundos para a base toda.
        ini = time.time()
        n = reparsear()
        print("%d anúncios reanalisados a partir do texto guardado, "
              "em %.1f segundos (nenhum pedido ao DR)" % (n, time.time() - ini))
        return

    if "--ler-pecas" in sys.argv:
        # Para os concursos cujas pecas chegaram antes de haver leitura
        # pelo modelo. O tecto de tokens por minuto trava isto a cerca de
        # um por minuto; o 429 e esperado e a espera esta la dentro.
        # "tudo" rele tambem os que ja tem analise -- serve depois de se
        # mexer nas instrucoes ou nas ancoras.
        tudo = "tudo" in sys.argv
        with liga() as c:
            porler = [r["ref"] for r in c.execute(
                "SELECT DISTINCT d.ref ref FROM documentos d "
                "LEFT JOIN analise a ON a.ref = d.ref" +
                ("" if tudo else " WHERE a.ref IS NULL"))]
        print("%d concurso(s) com peças por ler." % len(porler))
        lidos = 0
        for i, ref in enumerate(porler, 1):
            ini = time.time()
            ok, porque = analisar_pecas(ref)
            estado = porque[:80] if porque else "lido"
            print("  [%d/%d] %-14s %s (%.0fs)" % (
                i, len(porler), ref, estado, time.time() - ini))
            lidos += 1 if ok and not porque else 0
            if SEM_ORCAMENTO_HOJE in (porque or ""):
                print("Parado: %s" % SEM_ORCAMENTO_HOJE)
                break
        print("%d lido(s) por inteiro." % lidos)
        return
    if "--uma-vez" in sys.argv:
        mensagem, novos = verificar(cfg)
        hora = min(cfg["horas_verificacao"],
                   key=lambda h: abs((datetime.now()
                                      - datetime.now().replace(
                                          hour=int(h[:2]), minute=int(h[3:]),
                                          second=0)).total_seconds()))
        registar_slot(datetime.now().strftime("%Y-%m-%d"), hora, novos)
        print(mensagem)
        return

    threading.Thread(target=relogio, daemon=True).start()
    print("Radar de Concursos, Diário da República")
    print("Painel em http://localhost:%d" % PORTA)
    print("Fecha esta janela para parar. Ctrl+C tambem serve.")
    try:
        webbrowser.open("http://localhost:%d/" % PORTA)
    except Exception:
        pass
    app.run(host="127.0.0.1", port=PORTA, debug=False)


if __name__ == "__main__":
    main()
