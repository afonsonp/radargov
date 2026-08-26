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
import sqlite3
import sys
import threading
import time
import unicodedata
import webbrowser
import zipfile
from datetime import datetime, timedelta
from urllib.parse import unquote, urlencode

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
    # A rotina so le o detalhe dos anuncios publicados nesta janela.
    # Entre publicacao e prazo vao ~18 dias em media, por isso mais atras
    # que isto ja fechou: o CPV desses so interessa como historico, e
    # esses sao lidos quando se abre a ficha. Poe a 0 para ler tudo.
    "detalhe_dias": 60,
    # Modelo que le o Caderno de Encargos e o Programa. Vazio = o de
    # origem. A lista destas plataformas muda, por isso fica a jeito.
    "modelo_pecas": "",
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
            modelo TEXT, fontes TEXT, quando TEXT)""")
        cols_an = [r["name"] for r in c.execute("PRAGMA table_info(analise)")]
        if "preco_anormalmente_baixo" not in cols_an:
            c.execute("ALTER TABLE analise ADD COLUMN "
                      "preco_anormalmente_baixo TEXT")
        cols_doc = [r["name"] for r in c.execute("PRAGMA table_info(documentos)")]
        for nome, tipo in (("texto", "TEXT"), ("texto_estado", "TEXT")):
            if nome not in cols_doc:
                c.execute("ALTER TABLE documentos ADD COLUMN %s %s" % (nome, tipo))
        # Pessoas e rasto de quem fez o que. Ha uma so pessoa hoje, mas a
        # aplicacao ha-de ser partilhada, e historico nao se inventa depois.
        c.execute("""CREATE TABLE IF NOT EXISTS pessoas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE)""")
        c.execute("""CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT, quem TEXT,
            accao TEXT, detalhe TEXT, quando TEXT)""")
        c.execute("""CREATE INDEX IF NOT EXISTS ix_historico_ref
                     ON historico(ref)""")
        colunas = [r["name"] for r in c.execute("PRAGMA table_info(anuncios)")]
        # Migracoes idempotentes: correm sempre, nao fazem nada se ja existirem.
        for nome, tipo in (("fase_id", "INTEGER"), ("texto", "TEXT"),
                           ("pdf_url", "TEXT"), ("link_pecas", "TEXT"),
                           ("docs_estado", "TEXT"), ("responsavel", "TEXT")):
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
               "link_pecas": ""}
    seccoes = seccoes_do_texto(texto)

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
                     plataforma=?, texto=?, pdf_url=?, link_pecas=?,
                     detalhe_lido=1 WHERE ref=?""",
                  (campos["cpv"], campos["prazo"], campos["preco_base"],
                   campos["plataforma"], texto, conteudo.get("URL_PDF") or "",
                   campos["link_pecas"], ref))
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
                         plataforma=?, link_pecas=? WHERE ref=?""",
                      (campos["cpv"], campos["prazo"], campos["preco_base"],
                       campos["plataforma"], campos["link_pecas"], a["ref"]))
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

# anogov e compraspt sao a mesma aplicacao JSF, do mesmo fornecedor:
# 'faces/app/acessoDocs.jsp' lista os documentos em HTML e cada ficheiro
# sai de um 'decryptservlet' no mesmo servidor.
PLATAFORMAS_JSF = ("anogov.com", "compraspt.com")
RX_DOC_JSF = re.compile(
    r'href="(https://[^"]*(?:anogov|compraspt)\.com/[^"]*decryptservlet[^"]*)"')


def _pecas_jsf(sessao, link):
    """Pecas da anogov e da ComprasPT. O nome vem no Content-Disposition.

    A pagina responde a um GET com o codigo de acesso que vem no anuncio,
    sem sessao iniciada. **O codigo tem ~50 caracteres**: se aparecer
    curto, foi truncado por quem o imprimiu, e a pagina responde
    "nao foi encontrado nenhum documento" -- que se confunde facilmente
    com "esta plataforma nao da acesso". Deu-se essa volta duas vezes."""
    pagina = sessao.get(link, timeout=120)
    pagina.encoding = "windows-1252"
    saida, vistos, grandes = [], set(), []
    for endereco in dict.fromkeys(RX_DOC_JSF.findall(pagina.text)):
        endereco = html.unescape(endereco)
        if endereco in vistos:
            continue
        vistos.add(endereco)
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


def extrair_textos(ref):
    """Guarda o texto dos PDFs deste anuncio. Devolve (lidos, digitalizados)."""
    with liga() as c:
        docs = c.execute("SELECT id,nome FROM documentos WHERE ref=? "
                         "AND texto_estado IS NULL", (ref,)).fetchall()
    pasta = pasta_do_anuncio(ref)
    lidos = scans = 0
    for d in docs:
        caminho = os.path.join(pasta, d["nome"])
        if not d["nome"].lower().endswith(".pdf") or not os.path.exists(caminho):
            estado, texto = "não é PDF", ""
        else:
            texto, estado = texto_do_pdf(caminho)
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
# 8000 tokens por minuto, contando a resposta. Sobram uns 5500 para a
# entrada, e o portugues destes documentos anda nos 3,5 caracteres por
# token -- daqui os 19 mil.
MAX_CHARS_PROMPT = 19000
TECTO_ENCARGOS = 11500
TECTO_PROGRAMA = 7000

# Onde e que mora cada campo. O numero e a prioridade: quando o
# orcamento acaba, corta-se pelos 3 antes de tocar nos 1.
# Comparadas contra simplifica(): sem acentos e em minusculas.
ANCORAS_ENCARGOS = (
    (1, r"objec?to\b|\bsolucao|\bambito|enquadramento"),
    (1, r"equipa|perfil|recursos humanos|composicao|afetacao"),
    (2, r"requisitos|especificacoes|funcionalidades|servicos a prestar"),
    (3, r"niveis de servico|entregaveis|plano de trabalhos"),
)
ANCORAS_PROGRAMA = (
    (1, r"documentos.{0,25}proposta|proposta.{0,25}documentos"),
    (2, r"apresentacao da proposta|termos.{0,20}proposta"),
    (2, r"anormalmente baixo"),
    (3, r"habilitacao|criterio"),
)

INSTRUCOES = """És um analista de concursos públicos portugueses. Lês o
Programa de Concurso e o Caderno de Encargos e extrais quatro coisas.

Responde SÓ com JSON, com estas chaves exactas:

{"objecto": "...", "equipa": "...", "documentos_proposta": "...",
 "preco_anormalmente_baixo": "..."}

- "objecto": o âmbito do serviço decomposto em pontos concretos, um por
  linha começada por "- ". Não repitas o título do concurso: enumera o
  que tem mesmo de ser feito (desenvolvimento, migração, integrações,
  formação, garantia, suporte, prazos parciais).
- "equipa": os perfis exigidos e os requisitos, um por linha começada
  por "- ". Repara SEMPRE se o documento pede os requisitos a cada
  perfil ou à equipa "em conjunto": não é a mesma coisa para quem
  concorre — sete certificações numa pessoa ou espalhadas por quatro.
  Não atribuas a um perfil o que o documento exige ao conjunto; nesse
  caso escreve uma linha "- Em conjunto, a equipa deve deter: ...".
- "documentos_proposta": a lista dos documentos que o CONCORRENTE tem de
  entregar na proposta, um por linha começada por "- ".
- "preco_anormalmente_baixo": o limiar a partir do qual o preço da
  proposta é tido por anormalmente baixo (art. 71.º do CCP) — a
  percentagem ou o valor. Muitos Programas não fixam nenhum: nesse caso
  responde "não consta". Não confundas com o preço base.

ATENÇÃO a uma confusão frequente: "documentos que constituem a proposta"
(o que tu entregas) NÃO é o mesmo que "peças que constituem o
procedimento" (anúncio, programa, caderno de encargos). Queremos o
primeiro.

Se algo não constar dos documentos, põe exactamente "não consta".
Não inventes. Escreve em português de Portugal."""


def ler_chave_api():
    """A chave fica num ficheiro a parte, fora do git. Tambem se aceita
    a variavel de ambiente GROQ_API_KEY."""
    for nome in NOMES_CHAVE:
        caminho = os.path.join(BASE_DIR, nome)
        if os.path.exists(caminho):
            with open(caminho, encoding="utf-8") as f:
                chave = f.read().strip()
            if chave:
                return chave
    return (os.environ.get("GROQ_API_KEY") or "").strip()


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

    marca = bytearray(len(texto))
    for _, p in sorted(titulos):
        if sum(marca) >= tecto:
            break
        for i in range(max(0, p - 200), min(len(texto), p + janela)):
            marca[i] = 1

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


def pecas_para_analise(ref):
    """O que interessa do Caderno de Encargos e do Programa deste anuncio."""
    with liga() as c:
        docs = c.execute(
            "SELECT nome, texto FROM documentos WHERE ref=? AND texto_estado='ok' "
            "AND texto != '' ORDER BY nome", (ref,)).fetchall()
    partes, usados = [], []
    for d in docs:
        if re.search(r"caderno|encargos", d["nome"], re.I):
            ancoras, tecto = ANCORAS_ENCARGOS, TECTO_ENCARGOS
        elif re.search(r"programa|procedimento", d["nome"], re.I):
            ancoras, tecto = ANCORAS_PROGRAMA, TECTO_PROGRAMA
        else:
            continue
        partes.append("### %s\n%s" % (
            d["nome"], recorte_relevante(d["texto"], ancoras, tecto)))
        usados.append(d["nome"])
    return "\n\n".join(partes)[:MAX_CHARS_PROMPT], usados


def limpa_campo(valor):
    """As mudancas de linha, que o modelo devolve escapadas a dobrar.

    Sem isto o "\n" aparece a letra no meio do texto, porque o modelo
    escreveu "\\n" no JSON e o json.loads so desfaz uma camada.
    """
    texto = str(valor or "").replace("\\n", "\n").replace("\\t", " ")
    return "\n".join(l for l in (x.strip() for x in texto.split("\n")) if l)


def espera_pedida(resposta, tecto=70):
    """Quantos segundos esperar depois de um 429, segundo a propria API."""
    cabecalho = resposta.headers.get("retry-after", "")
    if cabecalho.replace(".", "", 1).isdigit():
        return min(float(cabecalho) + 1, tecto)
    # sem cabecalho, a mensagem costuma dizer "try again in 12.4s"
    achado = re.search(r"in \s*([\d]+(?:\.[\d]+)?)s", resposta.text or "")
    return min(float(achado.group(1)) + 1, tecto) if achado else 20.0


def analisar_pecas(ref):
    """Le as pecas com o modelo e guarda os tres campos. (ok, aviso)."""
    chave = ler_chave_api()
    if not chave:
        return False, ("falta a chave da API: põe-na em chave_api.txt, "
                       "na pasta do radar")
    modelo = ler_config().get("modelo_pecas") or GROQ_MODELO
    texto, usados = pecas_para_analise(ref)
    if not texto:
        # As pecas trazidas antes de haver extracao de texto ficaram sem
        # ele. Estao em disco: extrai-se agora, sem voltar a rede.
        extrair_textos(ref)
        texto, usados = pecas_para_analise(ref)
    if not texto:
        with liga() as c:
            scans = c.execute("SELECT COUNT(*) n FROM documentos WHERE ref=? "
                              "AND texto_estado='scan'", (ref,)).fetchone()["n"]
        return False, ("os documentos deste concurso são digitalizações, sem "
                       "texto para ler" if scans else
                       "ainda não há Caderno de Encargos nem Programa em disco")
    try:
        for tentativa in (1, 2):
            r = requests.post(GROQ_URL, timeout=180,
                              headers={"Authorization": "Bearer " + chave,
                                       "Content-Type": "application/json"},
                              json={"model": modelo, "temperature": 0,
                                    "response_format": {"type": "json_object"},
                                    "messages": [
                                        {"role": "system", "content": INSTRUCOES},
                                        {"role": "user", "content": texto}]})
            if r.status_code != 429 or tentativa == 2:
                break
            # A conta tem um tecto de tokens por minuto e marcar tres
            # concursos seguidos bate nele. Isto corre em fundo, sem
            # ninguem a ver: esperar o minuto vale mais do que desistir.
            time.sleep(espera_pedida(r))
        if r.status_code != 200:
            return False, "o modelo respondeu %d: %s" % (
                r.status_code, r.text[:160])
        conteudo = r.json()["choices"][0]["message"]["content"]
        dados = json.loads(conteudo)
    except (requests.RequestException, ValueError, KeyError, IndexError) as erro:
        return False, "falhou a leitura pelo modelo: %s" % str(erro)[:140]

    with liga() as c:
        c.execute("""INSERT OR REPLACE INTO analise
            (ref,objecto,equipa,documentos_proposta,preco_anormalmente_baixo,
             modelo,fontes,quando) VALUES (?,?,?,?,?,?,?,?)""",
                  (ref, limpa_campo(dados.get("objecto")),
                   limpa_campo(dados.get("equipa")),
                   limpa_campo(dados.get("documentos_proposta")),
                   limpa_campo(dados.get("preco_anormalmente_baixo")), modelo,
                   ", ".join(usados),
                   datetime.now().strftime("%Y-%m-%d %H:%M")))
    return True, ""


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
        elif link and any(h in link for h in PLATAFORMAS_JSF):
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
    if ler_chave_api() and not analise_de(ref):
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


def verificar(cfg=None):
    cfg = cfg or ler_config()
    iniciar_db()
    bem, mensagem, novos = recolher(cfg)
    if bem:
        feitos, aviso = ler_detalhes(int(cfg.get("detalhes_por_volta", 40)),
                                     dias=int(cfg.get("detalhe_dias", 60)) or None)
        if aviso:
            bem = False
            mensagem += " (%s)" % aviso
    marca("ultima_verificacao", datetime.now().strftime("%Y-%m-%d %H:%M"))
    marca("ultima_mensagem", mensagem)
    marca("ultima_ok", "1" if bem else "0")
    if novos and cfg.get("abrir_browser_ao_encontrar"):
        try:
            webbrowser.open("http://localhost:%d/" % PORTA)
        except Exception:
            pass
    return mensagem, novos


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
aside nav a{display:flex;align-items:center;justify-content:space-between;gap:10px;
 padding:9px 12px;border-radius:7px;color:rgba(255,255,255,.62)}
aside nav a:hover{background:rgba(255,255,255,.09);color:#fff}
aside nav a.on{background:rgba(255,255,255,.08);color:#fff}
aside nav a b{font:500 13.5px/1.2 var(--sans)}
aside nav a i{font:500 9.5px/1 var(--mono);font-style:normal;color:rgba(255,255,255,.28)}
aside nav a.on i{color:rgba(255,255,255,.55)}
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
 background:var(--creme);font:400 12.5px/1.2 var(--sans);color:var(--ink)}
.filtros label{font:500 12px/1 var(--sans);color:var(--t3)}
.filtros button{cursor:pointer;padding:10px 18px;border-radius:8px;border:0;
 background:var(--azul);color:#fff;font:600 12.5px/1 var(--sans)}
.filtros button:hover{background:var(--ink)}
.filtros a.limpar{padding:10px 12px;font:500 12.5px/1 var(--sans);color:var(--t5)}
.filtros a.limpar:hover{color:var(--ink)}
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
  <div class="sub">DR II série &middot; parte L</div>
  <div class="meta">localhost:%(porta)d &middot; %(total_fmt)s anúncios</div>
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

NAV = (("lista", "Lista", "/", "/"),
       ("quadro", "Quadro", "/quadro", "/quadro"),
       ("calendario", "Calendário", "/calendario", "/calendario"),
       ("indicadores", "Indicadores", "/indicadores", "/indicadores"))


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
    for chave, etiqueta, destino, rota in NAV:
        itens.append("<a class='%s' href='%s'><b>%s</b><i>%s</i></a>"
                     % ("on" if chave == activo else "", destino,
                        html.escape(etiqueta), html.escape(rota)))

    mensagem = le_marca("ultima_mensagem", "ainda não verificou")
    quando = le_marca("ultima_verificacao", "nunca")
    ultima = ("última: %s &mdash; %s" % (html.escape(quando), html.escape(mensagem))
              if quando != "nunca" else "ainda não verificou")

    if not migalhas:
        migalhas = "<a href='/'>Lista</a>"

    # Aviso de uma accao acabada de fazer, passado no proprio
    # redireccionamento. Nao vai para a base: e da vez, nao do sistema --
    # e assim nao se confunde "peças trazidas" com "verificação correu bem".
    texto_aviso = (request.args.get("aviso") or "").strip()
    aviso = ("<div class='flash'>%s</div>" % html.escape(texto_aviso)) \
        if texto_aviso else ""

    return BASE % {
        "titulo_aba": html.escape(titulo_aba or titulo),
        "css": CSS, "porta": PORTA,
        "total_fmt": "{:,}".format(total).replace(",", " "),
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
        "accoes_topo": accao("/verificar", "Verificar agora"),
        "lista_pessoas": "".join("<option value='%s'>" % html.escape(n, quote=True)
                                 for n in listar_pessoas()),
        "script": script,
    }


# Quantas linhas a lista mostra de uma vez. E um limite de apresentacao,
# nao da base.
LIMITE_LISTA = 500

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
  fetch('/cpv.json').then(function(r) { return r.json(); }).then(function(dados) {
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
</script>"""


@app.route("/")
def painel():
    onde, valores = condicoes(request.args)
    with liga() as c:
        # Menos um por cento: pede-se uma linha a mais que o limite de
        # apresentacao. Se ela vier, sabe-se que ha mais sem correr a
        # consulta filtrada uma segunda vez so para contar -- com um
        # filtro por palavras isso era outra passagem por 65 mil linhas.
        linhas = c.execute("SELECT * FROM anuncios" + onde +
                           " ORDER BY data_pub DESC, ref DESC LIMIT ?",
                           valores + [LIMITE_LISTA + 1]).fetchall()
        ha_mais = len(linhas) > LIMITE_LISTA
        linhas = linhas[:LIMITE_LISTA]
        correspondem = (c.execute("SELECT COUNT(*) n FROM anuncios" + onde,
                                  valores).fetchone()["n"]
                        if ha_mais else len(linhas))
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

    def mil(n):
        return "{:,}".format(n).replace(",", " ")

    estado_actual = request.args.get("estado", "novo")
    abas = ["<div class='abas'>"]
    for valor, etiqueta, quantos in (("novo", "Por ver", contas["novo"]),
                                     ("interessa", "Interessa", contas["interessa"]),
                                     ("descartado", "Descartados", contas["descartado"]),
                                     ("", "Todos", total)):
        args = dict(request.args.to_dict(), estado=valor)
        abas.append("<a class='%s' href='/?%s'>%s <i>%s</i></a>"
                    % ("on" if valor == estado_actual else "",
                       urlencode(args), etiqueta, mil(quantos)))
    abas.append("</div>")

    cpv_actual = request.args.get("cpv", "")
    if cpv_actual:
        sem_cpv = dict(request.args.to_dict(), cpv="")
        faixa_cpv = ("<div class='cpv-activo'>Filtro CPV activo: <b>%s</b>"
                     "<a href='/?%s'>tirar</a></div>"
                     % (html.escape(cpv_actual), urlencode(sem_cpv)))
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
        "<input type='text' name='q' value='%s' placeholder='Nome do concurso ou objeto…'>"
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

    arvore = (
        "<details class='arvore'><summary>"
        "<span class='arv-tit'>Escolher CPV na árvore</span>"
        "<span class='arv-sub'>%s códigos &middot; contagens acumuladas</span>"
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
        "</details>" % mil(n_cpv))

    if linhas:
        corpo_lista = "<div class='lista'>" + "".join(linha(a) for a in linhas) + "</div>"
    else:
        corpo_lista = ("<div class='vazio'>Nada corresponde a este filtro. "
                       "<a href='/'>limpar</a></div>")

    # o LIMIT 500 e de apresentacao; a contagem tem de dizer quantos o
    # filtro apanhou mesmo, senao "500 de 65 869" parece um filtro que
    # nao filtrou nada
    if correspondem > len(linhas):
        conta = ("Mais recentes primeiro &middot; a mostrar %s dos %s que "
                 "correspondem" % (mil(len(linhas)), mil(correspondem)))
    else:
        conta = ("Mais recentes primeiro &middot; %s %s"
                 % (mil(correspondem),
                    "resultado" if correspondem == 1 else "resultados"))
    conta += " &middot; %s na base" % mil(total)
    if porler:
        conta += " &middot; %s ainda sem detalhe lido" % mil(porler)

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

    conteudo = ("<div class='larg'>" + filtros + faixa_cpv + arvore +
                "<div class='linha-conta'>" + conta +
                "<a href='/csv%s'>exportar CSV</a></div>"
                % (("?" + request.query_string.decode())
                   if request.query_string else "") +
                corpo_lista + rodape + "</div>")

    return envolver(
        "lista", "Anúncios da parte L",
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
                # so os 8 digitos do codigo, sem o digito de controlo, que
                # descola do formato guardado (o traço nao entra na conta).
                # Os zeros a direita sao estrutura no CPV, por isso tira-los
                # alarga do codigo para o grupo: "72000000" apanha "72267100".
                #
                # Mas nunca abaixo de dois digitos, que e a largura da
                # divisao: "30000000".rstrip("0") daria "3" e apanhava as
                # divisoes 31, 33, 34, 35, 37, 38 e 39 por engano -- medido,
                # 4592 anuncios em vez de 440.
                digitos = re.sub(r"\D", "", pedaco)[:8]
                curto = digitos.rstrip("0")
                prefixos = [curto if len(curto) >= 2 else digitos[:2]]
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


# (anuncios com detalhe lido, corpo JSON) -- ver cpv_json()
_CPV_CACHE = None


@app.route("/cpv.json")
def cpv_json():
    """O vocabulario CPV inteiro, com a contagem de anuncios guardados
    (nao filtrados por estado) que tem cada codigo. Alimenta a arvore
    do painel; o agrupamento em ramos e feito no browser."""
    with liga() as c:
        lidos = c.execute("SELECT COUNT(*) n FROM anuncios "
                          "WHERE detalhe_lido=1").fetchone()["n"]
    # As contagens so mudam quando mais algum anuncio passa a ter detalhe
    # lido. Guardar o resultado poupa varrer a tabela e serializar ~780 KB
    # a cada abertura da arvore.
    global _CPV_CACHE
    if _CPV_CACHE and _CPV_CACHE[0] == lidos:
        return Response(_CPV_CACHE[1], mimetype="application/json")

    contagens = {}
    with liga() as c:
        for row in c.execute("SELECT cpv FROM anuncios WHERE cpv != ''"):
            for pedaco in row["cpv"].split(","):
                codigo8 = re.sub(r"\D", "", pedaco)[:8]
                if len(codigo8) == 8:
                    contagens[codigo8] = contagens.get(codigo8, 0) + 1
        linhas = c.execute(
            "SELECT codigo8, descricao FROM cpv_dict ORDER BY codigo8").fetchall()
    dados = [{"codigo8": r["codigo8"], "descricao": r["descricao"],
              "n": contagens.get(r["codigo8"], 0)} for r in linhas]
    corpo = json.dumps(dados, ensure_ascii=False)
    _CPV_CACHE = (lidos, corpo)
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
            limite, "já passou" if passou else conta_dias(dias))
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
        valor = (analise[campo] or "").strip()
        return "" if simplifica(valor) in ("", "nao consta", "não consta") else valor

    nota_pecas = ("lido do Caderno de Encargos e do Programa por %s — confirmar "
                  "no documento" % analise["modelo"]) if analise else ""
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
        # entidade. Onde o servico e mesmo prestado -- remoto, hibrido,
        # ou instalacoes nomeadas -- consta do Caderno de Encargos.
        ("Local de prestação de serviços", local, "",
         "localização do procedimento; regime presencial, remoto ou "
         "híbrido consta do Caderno de Encargos"),
        ("Data de esclarecimentos", esclarecimentos, esclarec_falta,
         esclarec_nota),
        ("Data de submissão da proposta", a["prazo"], "", ""),
        ("Objeto, âmbito e características", das_pecas("objecto"),
         "" if das_pecas("objecto") else FALTA_CE, nota_pecas),
        ("Equipa", das_pecas("equipa"),
         "" if das_pecas("equipa") else FALTA_CE, nota_pecas),
        ("Documentos que constituem a proposta", das_pecas("documentos_proposta"),
         "" if das_pecas("documentos_proposta") else FALTA_PC, nota_pecas),
    ]


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
        prazo_v, prazo_c = "%s (expirado)" % a["prazo"], "mau"
    else:
        prazo_v = "%s (%s)" % (a["prazo"], conta_dias(dias))
        prazo_c = "mau" if dias == 0 else "ok"

    factos = "".join((
        _facto("Publicado", a["data_pub"]),
        _facto("Propostas até", prazo_v, prazo_c),
        _facto("Preço base", html.escape(a["preco_base"] or "")),
        _facto("Plataforma", html.escape(a["plataforma"] or "")),
        _facto("Estado", rotulo_estado),
        _facto("CPV", "<br>".join(descricoes_cpv(a["cpv"])), largo=True),
    ))

    cabeca = ("<div class='cx cabeca'><div class='chips'>%s</div>"
              "<h2>%s</h2><div class='ent'>%s</div>"
              "<div class='factos'>%s</div></div>"
              % ("".join(chips), html.escape(a["titulo"] or ""),
                 html.escape(a["entidade"] or ""), factos))

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
                    % (html.escape(a["prazo"]),
                       "prazo expirado" if passou else conta_dias(dias),
                       (" &middot; " + html.escape(a["plataforma"])) if a["plataforma"] else "",
                       100 if passou else pct))

    if docs:
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
    elif a["docs_estado"] == "pendente":
        # As peças vêm em fundo e demoram entre 1 e 10 segundos. Sem isto
        # a página era desenhada antes de elas existirem e parecia que não
        # tinham vindo -- só recarregando à mão é que apareciam.
        corpo_docs = ("<div class='nota a-trazer'>A trazer as peças da "
                      "plataforma… a página actualiza-se sozinha.</div>")
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
                "<div class='ficha-esq'>" + cabeca + modos + seccoes_html + "</div>"
                "<div class='ficha-dir'>" + prazo_cx + docs_cx + resp_cx +
                hist_cx + "</div></div></div>")

    migalhas = ("<a href='/'>Lista</a><s>&rsaquo;</s><em>/anuncio/%s</em>"
                % html.escape(ref))
    # Enquanto as peças não chegam, a página volta a pedir-se sozinha. O
    # trabalhador põe sempre um estado terminal (ok/parcial/falhou), por
    # isso isto pára -- não fica em ciclo.
    espera = ("<script>setTimeout(function(){location.reload()},3000)</script>"
              if a["docs_estado"] == "pendente" else "")

    return envolver("lista", a["titulo"] or ref,
                    "/anuncio/%s &middot; %s" % (html.escape(ref),
                                                 html.escape(a["entidade"] or "")),
                    conteudo, migalhas=migalhas, script=espera,
                    titulo_aba="%s, Radar de Concursos" % ref)


@app.route("/documentos/<path:ref>", methods=["POST"])
def trazer_documentos(ref):
    n, aviso = obter_documentos(ref)
    if n and aviso:
        aviso = "%d ficheiro(s) trazido(s), mas: %s" % (n, aviso)
    elif n:
        aviso = "%d ficheiro(s) trazido(s)." % n
    return redirect("/anuncio/" + ref + "?" + urlencode({"aviso": aviso}))


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

    migalhas = "<a href='/'>Lista</a><s>&rsaquo;</s><em>Quadro</em>"
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

    migalhas = "<a href='/'>Lista</a><s>&rsaquo;</s><em>Calendário</em>"
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

    def mil(n):
        return "{:,}".format(int(n)).replace(",", " ")

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
    saude_html = "".join(
        "<div class='l'><span class='ponto' style='background:%s'></span>"
        "<span class='t'>%s</span><span class='v'>%s</span></div>"
        % ("#1e8449" if bom else "#c0392b", t, v) for t, v, bom in saude)

    conteudo = (
        "<div class='larg' style='display:flex;flex-direction:column;gap:18px'>"
        "<div class='kpis'>%s</div>"
        "<div class='ind-grelha'>"
        "<div class='cx' style='padding:22px 24px'>"
        "<div class='rot' style='margin-bottom:22px'>Interessados por fase do quadro</div>"
        "<div class='barras'>%s</div></div>"
        "<div class='cx' style='padding:22px 24px'>"
        "<div class='rot' style='margin-bottom:16px'>Estado da recolha</div>"
        "<div class='saude'>%s</div></div>"
        "</div></div>" % (kpis_html, barras, saude_html))

    migalhas = "<a href='/'>Lista</a><s>&rsaquo;</s><em>Indicadores</em>"
    return envolver("indicadores", "Indicadores",
                    "Consultas directas ao radar.db &mdash; sem serviços externos.",
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
        with liga() as c:
            porler = [r["ref"] for r in c.execute(
                "SELECT DISTINCT d.ref ref FROM documentos d "
                "LEFT JOIN analise a ON a.ref = d.ref WHERE a.ref IS NULL")]
        print("%d concurso(s) com peças por ler." % len(porler))
        lidos = 0
        for i, ref in enumerate(porler, 1):
            ini = time.time()
            ok, porque = analisar_pecas(ref)
            print("  [%d/%d] %-14s %s (%.0fs)" % (
                i, len(porler), ref, "lido" if ok else porque[:70],
                time.time() - ini))
            lidos += 1 if ok else 0
        print("%d lido(s)." % lidos)
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
