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
           python radar.py --descartar-expirados   arruma os por ver com prazo passado
           python radar.py --importar-cpv F   carrega o vocabulario CPV
           python radar.py --importar-excel F [--ensaio] [--sem-rede]
                                       o Excel de analise de concursos da casa
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
import socket
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

import casa                      # o registo da casa (casa.py importa o radar por dentro)
from email.message import EmailMessage
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlparse

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
    # Quantos anuncios marcados (interessa/quadro) se releem por
    # verificacao, a procura de prorrogacoes e precos base novos (B05).
    "relidos_por_volta": 25,
    # A janela do "urgente", em dias (B13). Edita-se tambem em /alertas.
    "dias_urgente": 10,
    # O INTERESSE (01/09/2026): o recorte permanente da lista de
    # anuncios, por CPV. Define-se em Alertas › Interesse. Nao e um
    # filtro -- e o que a casa faz; um filtro guardado esquece-se de se
    # pôr e apaga-se sem querer. Com "interesse_activo" a False, ou sem
    # CPV escolhido, a lista volta ao acervo todo. Formato dos dois
    # campos: codigos separados por "|", como o filtro.
    "interesse_activo": False,
    "interesse_cpv": "",
    "interesse_cpv_excl": "",
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
    # B15: depois de exportar o triagem.jsonl, fazer tambem commit+push
    # do ficheiro (so dele) em cada verificacao em que mude. Decisao do
    # Afonso a 31/08/2026 -- e o que poe a triagem fora do PC sem
    # ninguem se lembrar de o fazer. A False, o export continua e o
    # push volta a ser manual.
    "triagem_no_git": True,
    # B14: a segunda fonte -- as consultas preliminares da pesquisa
    # publica da Vortal, que a parte L nao publica. So esse tipo entra
    # (zero duplicacao com o DR, decisao do Afonso a 31/08/2026).
    # A False, a verificacao volta a ser so DR.
    "vortal_preliminares": True,
    "ocr": True,                  # digitalizacoes pelo RapidOCR, se instalado
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
    # Afinacao das leituras pelo modelo (B08), campo a campo: "objecto",
    # "equipa" e "proposta", cada um com "quais" ("encargos"|"programa"),
    # "ancoras" ([[prioridade, regex], ...]) e "instrucao". Vazio = as de
    # origem (LEITURAS). Exemplo funcional, para copiar e afinar:
    #   "leituras": {"equipa": {
    #       "quais": "encargos",
    #       "ancoras": [[1, "perfis"], [2, "equipa"], [3, "recursos humanos"]],
    #       "instrucao": "Extrai os perfis exigidos, um por linha."}}
    # O invalido (regex que nao compila, "quais" desconhecido) deixa
    # ficar o de origem -- nunca cala uma leitura em silencio.
    "leituras": {},
    # Da RECOLHA: quantos resultados por pagina se pedem ao portal do DR.
    # Nao confundir com POR_PAGINA_LISTA, a paginacao da lista no painel.
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
    # O LIKE do SQLite so baixa maiusculas de letras ASCII: para ele "Ç" e
    # "ç" sao letras diferentes, e procurar "aquisição" perdia os 14% de
    # titulos escritos todos em maiusculas. Registar a funcao aqui deixa
    # encher as colunas normalizadas em SQL, sem ciclo em Python.
    c.create_function("simplifica", 1, simplifica)
    return c


# As colunas do quadro. Sao SEIS e sao estas (decisao do Afonso a
# 01/09/2026: "a criacao de novas fases desaparece, ja nao e preciso") --
# o quadro passou a ser o funil da casa e nao um kanban em branco.
# Renomear continua a dar; criar e apagar nao.
#
# Cada fase tem um PAPEL, e e o papel -- nao o nome -- que manda no que o
# cartao pede e mostra: no "submetido" o preco e o proposto, no
# "relatorio" pergunta-se o lugar e os tres primeiros, no "perdido"
# pergunta-se porque. Se fosse pelo nome, renomear a coluna calava o
# campo em silencio.
FASES_DE_ORIGEM = (("analisar", "Por analisar"),
                   ("proposta", "A preparar proposta"),
                   ("submetido", "Submetido"),
                   ("relatorio", "Relatório preliminar"),
                   ("ganho", "Ganho"),
                   ("perdido", "Perdido"))
FASES_INICIAIS = tuple(nome for _, nome in FASES_DE_ORIGEM)

# Como se reconhece o papel de uma fase que ja existe, pelo nome que
# tem. Compara-se contra simplifica(nome), por isso sem acentos; sao
# pedacos e nao nomes inteiros porque a base do Afonso tem "Relatorio
# Preleminar" escrito assim. A ordem conta: quem apanha primeiro, fica.
PISTAS_DE_PAPEL = (("perd", "perdido"), ("ganh", "ganho"),
                   ("relat", "relatorio"), ("prelim", "relatorio"),
                   ("submet", "submetido"), ("propost", "proposta"),
                   ("analis", "analisar"))


def papel_pelo_nome(nome):
    """O papel que um nome de fase denuncia, ou "" se nenhum."""
    alvo = simplifica(nome or "")
    for pista, papel in PISTAS_DE_PAPEL:
        if pista in alvo:
            return papel
    return ""


def atribuir_papeis(c):
    """Poe o papel em cada fase e garante que as seis existem.

    Idempotente, como todas as migracoes: corre a cada arranque e nao faz
    nada quando ja esta feito. Separada de semear_fases() de proposito --
    essa so actua num quadro por estrear, e os papeis tem de chegar
    tambem aos quadros que ja estao em uso.
    """
    fases = c.execute("SELECT id, nome, ordem, papel FROM fases "
                      "ORDER BY ordem, id").fetchall()
    tem = set()
    for f in fases:
        papel = f["papel"] or papel_pelo_nome(f["nome"])
        if papel and papel != f["papel"]:
            c.execute("UPDATE fases SET papel=? WHERE id=?", (papel, f["id"]))
        if papel:
            tem.add(papel)
    faltam = [(papel, nome) for papel, nome in FASES_DE_ORIGEM
              if papel not in tem]
    if not faltam:
        return
    proxima = max([f["ordem"] or 0 for f in fases] or [0]) + 1
    for papel, nome in faltam:
        c.execute("INSERT INTO fases (nome, ordem, papel) VALUES (?,?,?)",
                  (nome, proxima, papel))
        proxima += 1


# Porque e que um anuncio foi abandonado, e porque e que um concurso se
# perdeu. Ambito FECHADO nos dois casos, por decisao do Afonso a
# 01/09/2026: uma caixa de texto livre da, ao fim de um mes, cinquenta
# maneiras de escrever "preco" e nenhuma conta que se possa fazer. Se
# um motivo novo for preciso, acrescenta-se aqui -- e uma decisao, nao
# um campo.
# O Excel da casa traz mais duas razoes ("Fora do ambito", "Prazo curto",
# em casa.MAPA_RAZAO); entram aqui quando a triagem do registo da casa
# passar a aplicar-se -- decisao do Afonso a 02/09/2026: nada muda no
# front antes de o registo estar consolidado.
MOTIVOS_ABANDONO = ("Preço base baixo", "Falta de certificações",
                    "Falta de CV's")
MOTIVOS_PERDA = ("Preço", "CV's", "Proposta técnica", "Certificações")


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


def _modelo_com_fornecedor(valor):
    """Poe a coluna analise.modelo no formato actual, fornecedor:modelo.

    Antes da cadeia de fornecedores (27/08/2026) so a Groq respondia e a
    coluna guardava o modelo sem prefixo ("openai/gpt-oss-120b"). Um
    segmento sem ":" e desse tempo, e foi a Groq que o escreveu -- os
    outros fornecedores nasceram ja com o prefixo posto, por isso a
    atribuicao nao e adivinhada. Segmentos ja prefixados ficam como
    estao: aplicar isto duas vezes da o mesmo resultado."""
    partes = [p.strip() for p in (valor or "").split(",") if p.strip()]
    return ", ".join(p if ":" in p else "groq:" + p for p in partes)


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
        # Saneamento 30/08/2026 (A1): 30 documentos ficaram presos em
        # "erro: cryptography>=3.1 is required for AES algorithm", de
        # quando a dependencia ainda nao estava instalada. A causa ja
        # nao existe; limpa-se o estado para voltarem a fila de
        # extraccao (texto_estado IS NULL). Uma vez, por marca -- e o
        # extrair_textos() passou a retentar qualquer "erro:", por isso
        # nenhum erro de extraccao volta a ser terminal para sempre.
        if not c.execute("SELECT 1 FROM estado "
                         "WHERE chave='erros_extraccao_limpos'").fetchone():
            c.execute("UPDATE documentos SET texto=NULL, texto_estado=NULL "
                      "WHERE texto_estado LIKE 'erro:%cryptography%'")
            c.execute("INSERT OR REPLACE INTO estado "
                      "VALUES ('erros_extraccao_limpos','1')")
        # Saneamento 30/08/2026 (A2): as analises de antes da cadeia de
        # fornecedores guardavam o modelo sem prefixo. Converte-se para o
        # formato actual -- a regra esta em _modelo_com_fornecedor(), que
        # nao mexe no que ja tem prefixo. Uma vez, por marca.
        if not c.execute("SELECT 1 FROM estado "
                         "WHERE chave='modelo_com_fornecedor'").fetchone():
            for r in c.execute("SELECT ref, modelo FROM analise "
                               "WHERE COALESCE(modelo,'') != ''").fetchall():
                novo = _modelo_com_fornecedor(r["modelo"])
                if novo != r["modelo"]:
                    c.execute("UPDATE analise SET modelo=? WHERE ref=?",
                              (novo, r["ref"]))
            c.execute("INSERT OR REPLACE INTO estado "
                      "VALUES ('modelo_com_fornecedor','1')")
        # Pessoas e rasto de quem fez o que. Ha uma so pessoa hoje, mas a
        # aplicacao ha-de ser partilhada, e historico nao se inventa depois.
        c.execute("""CREATE TABLE IF NOT EXISTS pessoas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE)""")
        # O que ja foi avisado, para nao avisar duas vezes do mesmo e para
        # o separador poder mostrar o que ja saiu.
        c.execute("""CREATE TABLE IF NOT EXISTS alertas_vistos (
            filtro_id INTEGER, ref TEXT, visto_em TEXT, enviado_em TEXT,
            PRIMARY KEY (filtro_id, ref))""")
        # Filtros com nome. O que se guarda e a query string, nao as
        # condicoes SQL: assim um filtro e uma ligacao, e o que a lista
        # aprender a filtrar amanha funciona nos filtros de ontem.
        #
        # **Um filtro nao pertence a um separador.** E um conjunto de
        # campos, e cada pagina aplica os que entende -- um filtro por
        # CPV serve os anuncios e os contratos, que era o que a divisao
        # por vista impedia. Quando a tabela ainda tem a forma antiga,
        # recria-se: os filtros de entao tinham vista e a ideia mudou.
        cols_f = [r["name"] for r in
                  c.execute("PRAGMA table_info(filtros_guardados)")]
        if cols_f and ("vista" in cols_f or "alerta" not in cols_f):
            c.execute("DROP TABLE filtros_guardados")
            c.execute("DELETE FROM alertas_vistos")
        c.execute("""CREATE TABLE IF NOT EXISTS filtros_guardados (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE,
            consulta TEXT, alerta INTEGER DEFAULT 0,
            quem TEXT, criado_em TEXT)""")
        c.execute("""CREATE INDEX IF NOT EXISTS ix_alertas_envio
                     ON alertas_vistos(enviado_em)""")
        c.execute("""CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT, quem TEXT,
            accao TEXT, detalhe TEXT, quando TEXT)""")
        c.execute("""CREATE INDEX IF NOT EXISTS ix_historico_ref
                     ON historico(ref)""")
        # As alteracoes que o DR fez a anuncios ja lidos (B05): a fila do
        # resumo diario, com a marca de avisado -- o reconhecer e o
        # enviar separados, como nos alertas. O historico da ficha conta
        # a mesma historia, mas e para ler; esta tabela e para saber o
        # que ainda nao foi avisado.
        c.execute("""CREATE TABLE IF NOT EXISTS alteracoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT, campo TEXT,
            antes TEXT, depois TEXT, detectado_em TEXT, avisado_em TEXT)""")
        c.execute("""CREATE INDEX IF NOT EXISTS ix_alteracoes_envio
                     ON alteracoes(avisado_em)""")
        # C3: a serie dos erros. As marcas *_ultimo_erro sao sobrescritas
        # e um dia mau apagava a historia; aqui guarda-se cada ocorrencia
        # (marca_erro faz o INSERT alem da marca). Leitura por SQL chega
        # para comecar; a poda guarda ~200 por tipo -- o suficiente para
        # a serie dizer alguma coisa sem crescer para sempre.
        c.execute("""CREATE TABLE IF NOT EXISTS erros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quando TEXT, tipo TEXT, texto TEXT)""")
        c.execute("""DELETE FROM erros WHERE id NOT IN (
            SELECT e2.id FROM erros e2 WHERE e2.tipo = erros.tipo
            ORDER BY e2.id DESC LIMIT 200)""")
        # A pesquisa nas pecas (B09) foi implementada e RETIRADA a
        # 30/08/2026, por decisao do Afonso: as pecas so existem depois
        # de marcar "interessa", por isso a pesquisa chegava sempre
        # tarde demais para ajudar a decidir -- nao se estava a ganhar
        # nada. A versao que valeria a pena (ver o PDF dentro da
        # aplicacao, com pesquisa la dentro) esta no BACKLOG, por fazer
        # so quando for pedida. Isto limpa o indice de quem chegou a
        # ter a versao retirada; DROP IF EXISTS e idempotente e gratis.
        c.execute("DROP TRIGGER IF EXISTS documentos_fts_ai")
        c.execute("DROP TRIGGER IF EXISTS documentos_fts_ad")
        c.execute("DROP TRIGGER IF EXISTS documentos_fts_au")
        c.execute("DROP TABLE IF EXISTS pecas_fts")
        c.execute("DELETE FROM estado WHERE chave='fts_povoado'")
        # Saneamento 30/08/2026 (A3): chaves do esquema de avisos antigo,
        # que o codigo actual nao le nem escreve -- o esquema de hoje e o
        # reconhecer/enviar de alertas_vistos. Recria-las nao tinha
        # sentido; apagar e idempotente e gratis, como a limpeza acima.
        c.execute("DELETE FROM estado WHERE chave IN "
                  "('ultimo_aviso','ultimo_aviso_texto')")
        # As entidades seguidas (B10) vivem na base de trabalho e nao no
        # corpus: o corpus refaz-se com --contratos, a triagem nao. O
        # nome guarda-se por comodidade (mostrar sem ir ao corpus); a
        # identidade e a chave, como sempre.
        c.execute("""CREATE TABLE IF NOT EXISTS entidades_seguidas (
            chave TEXT PRIMARY KEY, nome TEXT, desde TEXT)""")
        # A fila do resumo das seguidas, com o mesmo par
        # reconhecer/enviar dos alertas -- e o mesmo ACERVO ao seguir,
        # senao o primeiro resumo trazia tudo o que a entidade ja tem.
        c.execute("""CREATE TABLE IF NOT EXISTS seguidas_vistos (
            chave TEXT, ref TEXT, visto_em TEXT, enviado_em TEXT,
            PRIMARY KEY (chave, ref))""")
        colunas = [r["name"] for r in c.execute("PRAGMA table_info(anuncios)")]
        # Migracoes idempotentes: correm sempre, nao fazem nada se ja existirem.
        for nome, tipo in (("fase_id", "INTEGER"), ("texto", "TEXT"),
                           ("pdf_url", "TEXT"), ("link_pecas", "TEXT"),
                           ("docs_estado", "TEXT"), ("responsavel", "TEXT"),
                           # o NIPC da entidade, que o DR publica sempre
                           ("nif", "TEXT"),
                           # o titulo e a entidade sem acentos e em
                           # minusculas: e por aqui que a pesquisa procura
                           ("titulo_norm", "TEXT"), ("entidade_norm", "TEXT"),
                           # B14: de onde o anuncio veio. 'dr' e a fonte
                           # de sempre; 'vortal' sao as consultas
                           # preliminares, que a parte L nao publica --
                           # e por esta coluna que as releituras do DR
                           # sabem nao lhes tocar
                           ("fonte", "TEXT DEFAULT 'dr'"),
                           # O endereco da PAGINA do procedimento na
                           # plataforma, que nao e o das pecas. So a
                           # Vortal precisa de o resolver por rede;
                           # guarda-se para nao repetir a ida.
                           ("link_proc", "TEXT"),
                           # Porque e que se abandonou. Ambito fechado
                           # (MOTIVOS_ABANDONO): sem motivo nao se
                           # abandona, senao daqui a um mes ninguem
                           # sabe porque e que aquele ficou de fora.
                           ("motivo", "TEXT"),
                           # O que se propos, que a partir do
                           # "Submetido" e o numero que conta -- o
                           # preco base deixa de ser noticia.
                           ("preco_proposto", "TEXT"),
                           # Relatorio preliminar: em que lugar
                           # ficamos e quem sao os tres primeiros.
                           ("posicao", "INTEGER"), ("top3", "TEXT"),
                           # Porque e que se perdeu, ambito fechado
                           # (MOTIVOS_PERDA).
                           ("motivo_perda", "TEXT"),
                           # A republicacao: `altera` e o ref que o texto
                           # deste anuncio declara alterar (NULL = texto
                           # ainda nao lido com esta regra; '' = nao e
                           # alteracao); `alterado_por` fica no ORIGINAL
                           # e aponta para a alteracao mais recente, cujo
                           # prazo e preco sao os que estao em vigor.
                           ("altera", "TEXT"), ("alterado_por", "TEXT")):
            if nome not in colunas:
                c.execute("ALTER TABLE anuncios ADD COLUMN %s %s" % (nome, tipo))
        # Enche o que ainda estiver por normalizar. Corre sempre e nao faz
        # nada quando ja esta feito -- e a mesma regra das outras
        # migracoes. A primeira vez sao uns segundos para a base inteira.
        c.execute("UPDATE anuncios SET titulo_norm=simplifica(titulo), "
                  "entidade_norm=simplifica(entidade) WHERE titulo_norm IS NULL")
        # Indices para a pesquisa. Nao servem para saltar linhas -- um
        # LIKE com % a frente varre sempre --, servem para varrer o
        # indice em vez da tabela: as colunas normalizadas ficaram no fim
        # da linha, depois do `texto` do anuncio inteiro, e chegar la
        # obrigava a desserializar alguns KB por linha. Com o indice a
        # cobrir a consulta, a pesquisa voltou dos 4,7 s aos 0,4 s.
        c.execute("CREATE INDEX IF NOT EXISTS ix_anuncios_titulo_norm "
                  "ON anuncios(titulo_norm)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_anuncios_entidade_norm "
                  "ON anuncios(entidade_norm)")
        if "papel" not in [r["name"] for r in c.execute(
                "PRAGMA table_info(fases)")]:
            c.execute("ALTER TABLE fases ADD COLUMN papel TEXT")
        semear_fases(c)
        atribuir_papeis(c)
        casa.iniciar_tabelas(c)     # o registo da casa (Excel; um dia o Zoho)
        # B12, uma vez, por marca: os textos extraidos antes das marcas
        # de pagina (\f) nao sabem dizer de que pagina veio o recorte.
        # Reextrai-se o que ainda existir em disco; o que nao existir
        # fica como esta -- apagar um texto bom por nao ter o ficheiro
        # seria trocar a leitura pela cosmetica. A reextraccao corre
        # DEPOIS desta transaccao (extrair_textos abre a sua ligacao).
        # B14, uma vez, por marca: as consultas preliminares recolhidas
        # antes de 01/09/2026 entraram com detalhe_lido=1 e sem CPV nem
        # NIPC -- a pesquisa da Vortal nao os traz e ninguem ia buscar o
        # detalhe. Voltam a por ler para ler_preliminares() as encher na
        # verificacao seguinte. Marca e nao WHERE cpv='': ha consultas
        # que podem mesmo nao ter CPV, e essas nao se retentam para
        # sempre.
        if not c.execute("SELECT 1 FROM estado "
                         "WHERE chave='preliminares_com_detalhe'").fetchone():
            c.execute("UPDATE anuncios SET detalhe_lido=0 "
                      "WHERE fonte='vortal' AND COALESCE(cpv,'')=''")
            c.execute("INSERT OR REPLACE INTO estado "
                      "VALUES ('preliminares_com_detalhe','1')")
        refazer = []
        if not c.execute("SELECT 1 FROM estado "
                         "WHERE chave='texto_com_paginas'").fetchone():
            for d in c.execute("SELECT id, ref, nome FROM documentos "
                               "WHERE texto_estado='ok'").fetchall():
                caminho = os.path.join(pasta_do_anuncio(d["ref"]), d["nome"])
                if os.path.exists(caminho):
                    c.execute("UPDATE documentos SET texto=NULL, "
                              "texto_estado=NULL WHERE id=?", (d["id"],))
                    if d["ref"] not in refazer:
                        refazer.append(d["ref"])
            c.execute("INSERT OR REPLACE INTO estado "
                      "VALUES ('texto_com_paginas','1')")
    for ref in refazer:
        extrair_textos(ref)
    # As alteracoes (republicacoes) que ja estavam na base antes de se
    # saber reconhece-las: uma vez, por marca -- o WHERE que as encontra
    # le colunas depois do `texto` e varre a tabela inteira (ver a regra
    # das migracoes sem indice no CLAUDE.md). As que chegarem depois
    # ligam-se ao ler o detalhe, em _guardar_detalhe().
    if le_marca("alteracoes_agrupadas") != "1":
        agrupar_alteracoes()
        marca("alteracoes_agrupadas", "1")


def gravar_config(mudancas):
    """Grava alteracoes na configuracao, sem tocar no resto.

    Serve o painel: o e-mail configura-se no ecra e nao a mao num
    ficheiro JSON, onde uma virgula a mais deixa a aplicacao sem
    configuracao nenhuma. A palavra-passe **nao passa por aqui** -- essa
    vive em email_senha.txt, porque o config.json abre-se sem pensar.
    """
    cfg = ler_config()
    for chave, valor in mudancas.items():
        if isinstance(valor, dict) and isinstance(cfg.get(chave), dict):
            cfg[chave] = dict(cfg[chave], **valor)
        else:
            cfg[chave] = valor
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return cfg


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


def marca_erro(chave, tipo, texto):
    """C3: a marca de sempre (o ecra le-a) MAIS uma linha na serie.

    As marcas *_ultimo_erro sao sobrescritas -- um dia mau apagava a
    historia toda. A tabela `erros` guarda cada ocorrencia; a poda dos
    ~200 por tipo vive no iniciar_db(). O registo da serie nunca pode
    derrubar o caminho do erro: se falhar, fica so a marca.
    """
    marca(chave, texto)
    try:
        with liga() as c:
            c.execute("INSERT INTO erros (quando, tipo, texto) "
                      "VALUES (?,?,?)",
                      (datetime.now().strftime("%Y-%m-%d %H:%M"), tipo,
                       str(texto)[:500]))
    except sqlite3.Error:
        pass


def registar_expiracao_token(qual, mensagem):
    """E4: guarda QUANDO o token expirou e de quando era a captura.

    Desde 02/09/2026 so se chega aqui quando o DR nao aceita o pedido
    NEM depois de perguntar_ao_dr() renovar as pecas a forca: o token e
    a apiVersion ja nao vem da captura, vem do proprio portal. O que
    resta a captura e a forma do corpo, e e essa que se refaz.

    A frequencia de expiracao nunca foi reconstruivel -- as marcas eram
    sobrescritas e o token e opaco (nao traz validade). Sabe-se so o
    piso (>= 8 dias, medido a 31/08/2026); esta serie e o instrumento
    que ha-de dizer quanto tempo as capturas duram mesmo. O `qual` e o
    nome-base da captura (curl_DR ou curl_detalhe): a idade dela no
    momento da expiracao e a medida que interessa.
    """
    idade = ""
    for nome in (qual + ".txt", qual + ".txt.txt"):
        caminho = os.path.join(BASE_DIR, nome)
        if os.path.exists(caminho):
            try:
                feita = datetime.fromtimestamp(os.path.getmtime(caminho))
                idade = (" · captura de %s (%.1f dias)"
                         % (feita.strftime("%Y-%m-%d %H:%M"),
                            (datetime.now() - feita).total_seconds()
                            / 86400.0))
            except OSError:
                pass
            break
    marca_erro("token_ultimo_erro", "token", mensagem + idade)


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


def registar(ref, accao, detalhe="", quem=None):
    """O `quem` explicito serve o trabalho em fundo: fora de um pedido do
    browser nao ha cookie nenhum para ler, e quem_sou() rebentava."""
    with liga() as c:
        c.execute("""INSERT INTO historico (ref,quem,accao,detalhe,quando)
                     VALUES (?,?,?,?,?)""",
                  (ref, quem or quem_sou() or "(sem nome)", accao, detalhe,
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


# ------------------------------------ as pecas do DR renovam-se sozinhas
#
# Medido a 02/09/2026 (medir_captura.py, tres voltas contra o portal):
# o "token" das capturas nao e de sessao nenhuma. O DR e uma aplicacao
# OutSystems e o x-csrftoken e o AnonymousCSRFToken publicado, a claras,
# em /dr/scripts/OutSystems.js -- so muda quando o DR actualiza a
# plataforma, e foi por isso que a captura de 23/08 ainda servia a
# 02/09. Sem cookie o DR nem o verifica (ate um inventado passa); com
# cookie verifica-o contra o crf do cookie. A moduleVersion nao tranca:
# o DR ja tinha republicado (hasModuleVersionChanged) e respondia na
# mesma. A unica tranca real e a apiVersion de cada accao, que vive no
# script compilado do ecra (dr.Pesquisas.PesquisaResultado.mvc.js), e
# esse script esta listado, com a versao, no manifest.urlVersions do
# moduleinfo -- que responde a um GET sem sessao. Errada, o DR responde
# JSON vazio com versionInfo.hasApiVersionChanged=true.
#
# Portanto tres GETs (moduleinfo, OutSystems.js, o script do ecra)
# renovam as tres pecas, e provou-se com pedidos de pesquisa e de
# detalhe feitos so com cabecalhos minimos e o corpo da captura. As
# capturas ficam a servir pela FORMA do corpo (as variaveis do ecra),
# e essa nao expira. Quando renovar nao der (sem rede, o DR mudou de
# forma) fica-se com a captura tal como esta, que e o comportamento
# de sempre; o aviso de expiracao so se regista quando nem a renovacao
# a forca salva o pedido.

DR_RAIZ = "https://diariodarepublica.pt"
DR_MODULEINFO = DR_RAIZ + "/dr/moduleservices/moduleinfo"
DR_OUTSYSTEMS_JS = "/dr/scripts/OutSystems.js"
VALIDADE_PECAS_DR = 6 * 3600     # segundos; a forca quando o DR o pede
_PECAS_DR = {"quando": 0.0, "token": "", "modulo": "", "api": {}}
_TRINCO_PECAS_DR = threading.Lock()


def script_do_ecra(url_accao):
    """De .../screenservices/dr/Pesquisas/PesquisaResultado/DataActionX
    para ('/dr/scripts/dr.Pesquisas.PesquisaResultado.mvc.js', 'DataActionX').
    E a convencao do OutSystems: o script do ecra chama-se pelo caminho
    da accao, com pontos."""
    partes = urlparse(url_accao).path.split("/screenservices/", 1)
    if len(partes) != 2:
        return "", ""
    pedacos = partes[1].strip("/").split("/")
    if len(pedacos) < 2:
        return "", ""
    return "/dr/scripts/" + ".".join(pedacos[:-1]) + ".mvc.js", pedacos[-1]


def api_version_do_script(js, accao):
    """A apiVersion da accao no script compilado do ecra. Lido de um
    script real: controller.callDataAction("DataActionGetPesquisas",
    "screenservices/dr/Pesquisas/PesquisaResultado/DataActionGetPesquisas",
    "PRsQKjEXDVBC3ZSqkS8k6A", ...)."""
    m = re.search(r'callDataAction\(\s*"%s"\s*,\s*"[^"]*"\s*,\s*"([^"]+)"'
                  % re.escape(accao), js)
    return m.group(1) if m else ""


def renovar_pecas_dr(url_accoes, forcar=False, buscar=None):
    """As tres pecas de cada accao do DR, renovadas por GET.

    Devolve {"token", "modulo", "api": {url_accao: apiVersion}} ou None
    quando nao da (sem rede, o DR mudou de forma) -- nunca levanta, e
    quem chama fica com a captura tal como esta. Cache por processo
    com validade; `forcar` ignora-a, e e o que se faz quando o DR
    responde a casca ou hasApiVersionChanged. `buscar` e o requests.get,
    trocavel nos testes.
    """
    buscar = buscar or requests.get
    cabecalhos = {"User-Agent": NAVEGADOR, "Accept": "*/*"}
    with _TRINCO_PECAS_DR:
        cache = _PECAS_DR
        faltam = [u for u in url_accoes if u not in cache["api"]]
        fresca = time.time() - cache["quando"] < VALIDADE_PECAS_DR
        if cache["token"] and not faltam and fresca and not forcar:
            return {"token": cache["token"], "modulo": cache["modulo"],
                    "api": dict(cache["api"])}
        try:
            manifesto = buscar(DR_MODULEINFO, headers=cabecalhos,
                               timeout=60).json()["manifest"]
            modulo = str(manifesto["versionToken"])
            versoes = manifesto["urlVersions"]
            js = buscar(DR_RAIZ + DR_OUTSYSTEMS_JS
                        + versoes.get(DR_OUTSYSTEMS_JS, ""),
                        headers=cabecalhos, timeout=60).text
            m = re.search(r'AnonymousCSRFToken\s*=\s*"([^"]+)"', js)
            if not m:
                raise ValueError("o OutSystems.js nao traz AnonymousCSRFToken")
            token = m.group(1)
            api = {}
            for url in url_accoes:
                caminho, accao = script_do_ecra(url)
                if caminho not in versoes:
                    raise ValueError("%s nao esta no manifesto" % caminho)
                js = buscar(DR_RAIZ + caminho + versoes[caminho],
                            headers=cabecalhos, timeout=60).text
                valor = api_version_do_script(js, accao)
                if not valor:
                    raise ValueError("sem apiVersion para " + accao)
                api[url] = valor
        except (requests.RequestException, ValueError, KeyError,
                TypeError, AttributeError) as erro:
            marca_erro("pecas_dr_ultimo_erro", "pecas-dr", str(erro)[:200])
            return None
        cache["quando"], cache["token"], cache["modulo"] = time.time(), token, modulo
        cache["api"].update(api)
        return {"token": token, "modulo": modulo, "api": dict(cache["api"])}


def pedido_renovado(pedido, molde, pecas):
    """(cabecalhos, corpo) do pedido da captura com as pecas por cima:
    sem Cookie (com cookie o DR verifica o token contra o crf de la;
    sem cookie aceita o token publico), o token, a moduleVersion e a
    apiVersion da accao. Sem pecas, a captura tal como esta."""
    if not pecas or pedido["url"] not in pecas.get("api", {}):
        return pedido["headers"], molde
    cabecalhos = {k: v for k, v in pedido["headers"].items()
                  if k.lower() not in ("cookie", "x-csrftoken")}
    cabecalhos["X-CSRFToken"] = pecas["token"]
    corpo = json.loads(json.dumps(molde))
    versao = corpo.setdefault("versionInfo", {})
    versao["moduleVersion"] = pecas["modulo"]
    versao["apiVersion"] = pecas["api"][pedido["url"]]
    return cabecalhos, corpo


def perguntar_ao_dr(pedido, molde, enviar=None, renovar=None):
    """Um POST ao DR pela porta unica. (dados, erro), com erro "" quando
    correu, "rede: ..." sem ligacao, "json" com JSON ilegivel, e "casca"
    ou "apiVersion" quando o DR nao aceitou o pedido NEM depois de
    renovar as pecas a forca e repetir uma vez -- so ai e que ha
    expiracao a registar. A casca fica em amostras/resposta_inesperada.txt.
    """
    enviar = enviar or requests.post
    renovar = renovar or renovar_pecas_dr
    pecas = renovar([pedido["url"]])
    motivo = ""
    for tentativa in (1, 2):
        cabecalhos, corpo = pedido_renovado(pedido, molde, pecas)
        try:
            r = enviar(pedido["url"], headers=cabecalhos,
                       data=json.dumps(corpo, ensure_ascii=False).encode("utf-8"),
                       timeout=60)
        except requests.RequestException as erro:
            return None, "rede: " + str(erro)[:80]
        if "json" in r.headers.get("Content-Type", ""):
            try:
                dados = r.json()
            except ValueError:
                return None, "json"
            versao = dados.get("versionInfo") if isinstance(dados, dict) else None
            if not (isinstance(versao, dict) and versao.get("hasApiVersionChanged")):
                return dados, ""
            motivo = "apiVersion"
        else:
            motivo = "casca"
            guardar_amostra("resposta_inesperada.txt",
                            "HTTP %d, tentativa %d\n\n%s"
                            % (r.status_code, tentativa, r.text[:3000]))
        if tentativa == 1:
            pecas = renovar([pedido["url"]], forcar=True) or pecas
    return None, motivo


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
            dados, erro = perguntar_ao_dr(pedido, molde)
            if erro.startswith("rede"):
                avarias.append(erro[6:])
                break
            if erro in ("casca", "apiVersion"):
                registar_expiracao_token(
                    "curl_DR", "a pesquisa nao foi aceite (%s) nem depois "
                    "de renovar as peças" % erro)
                return False, ("o DR não aceitou a pesquisa (%s) nem depois de "
                               "renovar as peças; ver amostras/"
                               "resposta_inesperada.txt e refaz a captura"
                               % erro), 0
            if erro:
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

# Pistas de reserva para quando nenhum nome de PLATAFORMAS aparece por
# extenso: ha anuncios em que a acingov so se denuncia pelo dominio do
# grupo ACIN (acin.pt). Cada valor TEM de existir em PLATAFORMAS -- isto
# e um apelido, nunca uma plataforma nova; ha um teste a garanti-lo.
# (Era um `if "acin" in alvo` solto dentro do campos_do_detalhe.)
SINONIMOS_PLATAFORMA = {"acin": "acingov"}


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


# A republicacao de um anuncio no DR. Medido a 01/09/2026 sobre os 5 661
# textos lidos: 763 (13,5%) comecam por "Alteracao do Anuncio de
# procedimento n.º 18372/2026, de 2026-07-17, com o ID ..." -- e e a
# UNICA forma que aparece (os 763 prefixos sao "alteracao do"). E a
# chave exacta do mesmo procedimento publicado outra vez, com prazo ou
# preco novos. Ate aqui cada republicacao entrava como anuncio novo: o
# mesmo concurso aparecia duas e tres vezes no por ver, e o Afonso
# descartou 511 vezes procedimentos que ja tinha descartado. Titulo
# igual na mesma entidade NAO serve de chave: 58 pares assim sem
# citacao sao procedimentos diferentes (repetem-se todos os anos).
RX_ALTERACAO = re.compile(
    r"^\s*Altera[çc][ãa]o do An[úu]ncio de (?:procedimento|concurso urgente)"
    r"\s*n\.?\s*[ºo°]?\s*(\d+)\s*/\s*(\d{4})", re.I)


def anuncio_alterado(texto):
    """O ref do anuncio que este texto declara alterar, ou ''."""
    m = RX_ALTERACAO.match((texto or "")[:400])
    return "%s/%s" % (m.group(1), m.group(2)) if m else ""


def campos_do_detalhe(texto):
    """Le do texto do anuncio os campos que servem para filtrar e listar."""
    achados = {"cpv": "", "prazo": "", "preco_base": "", "plataforma": "",
               "link_pecas": "", "nif": "", "altera": anuncio_alterado(texto)}
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
    # texto todo, para nao apanhar uma mencao de passagem. O .strip() nao
    # e decorativo: o join de pistas vazias da "  ", truthy, e o ultimo
    # recurso esteve morto desde sempre -- medido a 31/08/2026, custava
    # 28 anuncios sem plataforma (todos acingov, com a plataforma dita
    # por extenso no texto e nenhuma mencao de passagem entre eles).
    pistas = " ".join((valor_de(seccoes, "URL para Apresentação"),
                       valor_de(seccoes, "Plataforma eletrónica utilizada "
                                          "pela entidade adjudicante"),
                       achados["link_pecas"]))
    alvo = simplifica(pistas).strip() or simplifica(texto)
    for nome in PLATAFORMAS:
        if nome in alvo:
            achados["plataforma"] = nome
            break
    else:
        for pista, nome in SINONIMOS_PLATAFORMA.items():
            if pista in alvo:
                achados["plataforma"] = nome
                break
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


# Os campos que se vigiam entre releituras do detalhe, e como se chamam
# no aviso. So o prazo e o preco base: sao os que mudam decisoes -- uma
# prorrogacao da tempo, um preco base novo muda a conta da proposta.
CAMPOS_VIGIADOS = (("prazo", "prazo de propostas"),
                   ("preco_base", "preço base"))


def diferencas_do_detalhe(antes, depois):
    """[(campo, valor antigo, valor novo)] entre duas leituras.

    So conta quando ha valor DOS DOIS lados: um campo que passa a vazio
    e quase sempre o parser a tropecar num texto reformatado, e avisar
    "o prazo desapareceu" por causa disso era o rapaz que gritava lobo
    -- ao terceiro aviso falso ninguem lia o verdadeiro.
    """
    fora = []
    for campo, _ in CAMPOS_VIGIADOS:
        a = (antes.get(campo) or "").strip()
        d = (depois.get(campo) or "").strip()
        if a and d and a != d:
            fora.append((campo, a, d))
    return fora


def _valor_vigiado(campo, valor):
    """Datas a portuguesa no aviso; o resto como o DR o escreve."""
    return data_pt(valor) if campo == "prazo" else valor


def registar_alteracoes(ref, difs):
    """Grava o que mudou entre leituras, em dois sitios de proposito: na
    fila `alteracoes` (que sabe o que ja foi avisado, como os alertas) e
    no historico da ficha (que conta a historia a quem a abre)."""
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    rotulos = dict(CAMPOS_VIGIADOS)
    with liga() as c:
        c.executemany(
            "INSERT INTO alteracoes (ref, campo, antes, depois, detectado_em)"
            " VALUES (?,?,?,?,?)",
            [(ref, campo, a, d, agora) for campo, a, d in difs])
    for campo, a, d in difs:
        registar(ref, "alterou",
                 "%s: %s → %s" % (rotulos.get(campo, campo),
                                  _valor_vigiado(campo, a),
                                  _valor_vigiado(campo, d)),
                 quem="DR")


# --- as republicacoes (alteracoes) do DR
#
# O DR nao emenda um anuncio: publica outro, com ref novo, cujo texto
# comeca por "Alteracao do Anuncio de procedimento n.º X". Para o radar
# sao dois anuncios; para quem tria e o mesmo concurso. A regra da casa
# e que o ORIGINAL e a ficha do procedimento -- e nele que vive a
# triagem, o quadro, as pecas e a leitura -- e a alteracao fica na base
# com o proprio texto mas fora das listas (estado 'alteracao'), depois
# de lhe passar ao original o que mudou: prazo, preco base, CPV,
# plataforma e link das pecas, que sao os campos que decidem. A
# alternativa (passar a triagem para o anuncio mais recente) mudava o
# ref de tudo o que ja estava feito a cada republicacao.
#
# 103 das 763 citam a alteracao anterior e nao o original (21505 ->
# 20771 -> 18372): segue-se a cadeia ate a raiz. E a ordem de chegada
# nao pode importar -- ler_detalhes() le do mais recente para o mais
# antigo --, por isso o original toma sempre os campos do membro mais
# RECENTE da cadeia, seja qual for o que acabou de ser lido.

# O que e triagem de um anuncio, e passa da alteracao para o original
# quando foi na alteracao que alguem decidiu (aconteceu 513 vezes antes
# de haver esta ligacao: 511 descartes e 2 interessa).
CAMPOS_DA_TRIAGEM = ("estado", "motivo", "fase_id", "responsavel",
                     "preco_proposto", "posicao", "top3", "motivo_perda")
CAMPOS_EM_VIGOR = ("prazo", "preco_base", "cpv", "plataforma", "link_pecas")


def raiz_da_alteracao(c, ref, altera):
    """O anuncio ORIGINAL de uma cadeia de alteracoes: segue `altera`
    ate um anuncio que nao altera nenhum. Quando o citado nao esta na
    base, a raiz e o ultimo que esta; quando nem o primeiro citado esta,
    devolve None e o anuncio fica como esta, a representar sozinho o
    procedimento."""
    vistos = {ref}
    raiz, actual = None, altera
    while actual and actual not in vistos:
        vistos.add(actual)
        linha = c.execute("SELECT ref, altera FROM anuncios WHERE ref=?",
                          (actual,)).fetchone()
        if not linha:
            break
        raiz, actual = linha["ref"], (linha["altera"] or "")
    return raiz


def membros_da_cadeia(c, raiz):
    """Todos os anuncios que, directa ou indirectamente, alteram a raiz."""
    fora, fila = [], [raiz]
    while fila:
        actual = fila.pop()
        for m in c.execute("SELECT ref, data_pub FROM anuncios WHERE altera=?",
                           (actual,)):
            if m["ref"] != raiz and m["ref"] not in [f["ref"] for f in fora]:
                fora.append(m)
                fila.append(m["ref"])
    return fora


def _decidido(a):
    return a["estado"] != "novo" or a["fase_id"] is not None


def aplicar_alteracao(ref, avisar=True):
    """Liga a alteracao `ref` ao anuncio original e poe nele o que esta
    em vigor. Devolve o ref da raiz, ou '' quando nao ha nada a ligar.

    `avisar` manda os campos que mudaram para a fila `alteracoes` (o
    resumo diario), e so quando o original esta marcado -- e o mesmo
    criterio do reler_marcados(): uma prorrogacao num anuncio que
    ninguem quer nao e noticia. A migracao dos 763 que ja la estavam
    corre sem avisar; o historico da ficha fica sempre.
    """
    with liga() as c:
        a = c.execute("SELECT * FROM anuncios WHERE ref=?", (ref,)).fetchone()
        if not a or not a["altera"]:
            return ""
        raiz_ref = raiz_da_alteracao(c, ref, a["altera"])
        if not raiz_ref or raiz_ref == ref:
            return ""
        r = c.execute("SELECT * FROM anuncios WHERE ref=?",
                      (raiz_ref,)).fetchone()
        herdou, era = "", ""
        # Foi na alteracao que se decidiu: a decisao e do procedimento.
        # E uma decisao a serio (interessa/descartado) na alteracao
        # GANHA a uma diferente no original -- a alteracao e a
        # publicacao mais recente, e foi sobre ela que se decidiu por
        # ultimo. A migracao de 01/09/2026 nao fazia isto e deixou um
        # «interessa» do Afonso (21924/2026) por baixo de um descarte
        # antigo do original; o item sumiu-se dos Interessados. Um
        # 'novo' com fase nao e decisao: copia-se so para um original
        # por decidir.
        decisao = a["estado"] not in ("novo", "alteracao")
        if ((_decidido(a) and not _decidido(r))
                or (decisao and a["estado"] != r["estado"])):
            if _decidido(r) and r["estado"] != a["estado"]:
                era = _NOMES_ESTADO.get(r["estado"], r["estado"])
            c.execute("UPDATE anuncios SET %s WHERE ref=?"
                      % ", ".join("%s=?" % k for k in CAMPOS_DA_TRIAGEM),
                      [a[k] for k in CAMPOS_DA_TRIAGEM] + [raiz_ref])
            c.execute("INSERT OR IGNORE INTO anuncio_etiquetas (ref, etiqueta_id)"
                      " SELECT ?, etiqueta_id FROM anuncio_etiquetas WHERE ref=?",
                      (raiz_ref, ref))
            herdou = a["estado"] + (" (%s)" % a["motivo"] if a["motivo"] else "")
        if a["estado"] != "alteracao":
            c.execute("UPDATE anuncios SET estado='alteracao', fase_id=NULL "
                      "WHERE ref=?", (ref,))
        # O que esta em vigor e o membro mais recente da cadeia, que
        # pode nao ser este (ordem de leitura invertida, ou uma segunda
        # alteracao ja lida).
        membros = membros_da_cadeia(c, raiz_ref)
        recente = max(membros, key=lambda m: (m["data_pub"] or "",
                                              _numero_do_ref(m["ref"])))
        vigor = c.execute("SELECT ref, data_pub, texto FROM anuncios WHERE ref=?",
                          (recente["ref"],)).fetchone()
        campos = campos_do_detalhe(vigor["texto"])
        difs = [(k, r[k] or "", campos[k] or "") for k in CAMPOS_EM_VIGOR
                if (r[k] or "") != (campos[k] or "")]
        c.execute("UPDATE anuncios SET alterado_por=?, %s WHERE ref=?"
                  % ", ".join("%s=?" % k for k in CAMPOS_EM_VIGOR),
                  [vigor["ref"]] + [campos[k] for k in CAMPOS_EM_VIGOR] + [raiz_ref])
        marcado = _decidido(r) or bool(herdou)
        # Idempotente tambem no historico: voltar a passar (--reler,
        # --repor-triagem seguido de --reler) nao repete a linha.
        ja_dito = c.execute("SELECT 1 FROM historico WHERE ref=? AND accao=?",
                            (ref, "alteração")).fetchone()
    if not ja_dito:
        registar(ref, "alteração",
                 "do anúncio %s, publicado a %s; a triagem faz-se lá"
                 % (raiz_ref, data_pt(r["data_pub"], "")), quem="DR")
    if herdou:
        registar(raiz_ref, "estado", "%s, decidido na alteração %s%s"
                 % (herdou, ref, " (era «%s»)" % era if era else ""),
                 quem="DR")
    if difs:
        rotulos = dict(CAMPOS_VIGIADOS)
        registar(raiz_ref, "alterou",
                 "pelo anúncio %s de %s: %s"
                 % (vigor["ref"], data_pt(vigor["data_pub"], ""),
                    "; ".join("%s %s → %s" % (rotulos.get(k, k),
                                              _valor_vigiado(k, antes) or "—",
                                              _valor_vigiado(k, depois) or "—")
                              for k, antes, depois in difs)), quem="DR")
        vigiados = [(k, antes, depois) for k, antes, depois in difs
                    if k in rotulos and antes and depois]
        if avisar and marcado and vigiados:
            agora = datetime.now().strftime("%Y-%m-%d %H:%M")
            with liga() as c:
                c.executemany(
                    "INSERT INTO alteracoes (ref, campo, antes, depois, "
                    "detectado_em) VALUES (?,?,?,?,?)",
                    [(raiz_ref, k, antes, depois, agora)
                     for k, antes, depois in vigiados])
    return raiz_ref


def _numero_do_ref(ref):
    try:
        return int(str(ref).split("/")[0])
    except ValueError:
        return 0


def agrupar_alteracoes():
    """Reconhece e liga as alteracoes que ja estao na base: enche
    `altera` onde o texto ainda nao foi lido com esta regra, e aplica
    as que ainda nao estao ligadas, da mais antiga para a mais recente.
    Idempotente -- uma alteracao ligada esta em 'alteracao' e nao volta
    a entrar; uma cujo original nao esta na base fica como anuncio, e
    volta a tentar-se de graca. Devolve (reconhecidas, ligadas).

    Varre a tabela (as colunas ficam depois do `texto`): e para correr
    por marca no arranque e no --reler, nao a cada pedido."""
    with liga() as c:
        pendentes = c.execute(
            "SELECT ref, texto FROM anuncios WHERE altera IS NULL "
            "AND detalhe_lido=1 AND texto IS NOT NULL AND texto != ''").fetchall()
        for a in pendentes:
            alvo = anuncio_alterado(a["texto"])
            c.execute("UPDATE anuncios SET altera=? WHERE ref=?",
                      ("" if alvo == a["ref"] else alvo, a["ref"]))
        por_ligar = [r["ref"] for r in c.execute(
            "SELECT ref FROM anuncios WHERE COALESCE(altera,'') != '' "
            "AND estado != 'alteracao' ORDER BY data_pub, ref")]
    ligadas = sum(1 for ref in por_ligar if aplicar_alteracao(ref, avisar=False))
    return len(pendentes), ligadas


def _guardar_detalhe(ref, dados):
    """Caminhos exactos, confirmados na resposta do DR."""
    conteudo = (dados.get("data") or {}).get("DetalheConteudo") or {}
    texto = conteudo.get("Texto") or ""
    campos = campos_do_detalhe(texto)
    altera = campos["altera"] if campos["altera"] != ref else ""
    with liga() as c:
        # A leitura anterior, antes de a esmagar: e a comparacao entre
        # as duas que da os avisos de alteracao (B05).
        antigo = c.execute("SELECT prazo, preco_base, detalhe_lido, alterado_por "
                           "FROM anuncios WHERE ref=?", (ref,)).fetchone()
        ja_alterado = bool(antigo and antigo["alterado_por"])
        if ja_alterado:
            # Este anuncio ja foi alterado por outro mais recente: a
            # pagina DELE no DR e a versao antiga, e escrever-lhe o
            # prazo de la repunha o prazo velho por cima do que esta em
            # vigor -- e registava uma "alteracao" falsa. Guarda-se o
            # texto; os campos que decidem sao os da alteracao.
            c.execute("UPDATE anuncios SET texto=?, pdf_url=?, nif=?, "
                      "altera=?, detalhe_lido=1 WHERE ref=?",
                      (texto, conteudo.get("URL_PDF") or "", campos["nif"],
                       altera, ref))
        else:
            c.execute("""UPDATE anuncios SET cpv=?, prazo=?, preco_base=?,
                         plataforma=?, texto=?, pdf_url=?, link_pecas=?, nif=?,
                         altera=?, detalhe_lido=1 WHERE ref=?""",
                      (campos["cpv"], campos["prazo"], campos["preco_base"],
                       campos["plataforma"], texto, conteudo.get("URL_PDF") or "",
                       campos["link_pecas"], campos["nif"], altera, ref))
    # Daqui para baixo ja fora da transaccao: aplicar_alteracao() e
    # registar_alteracoes() abrem a sua ligacao e tem de ver o que ficou
    # escrito acima.
    if antigo and antigo["detalhe_lido"] and not ja_alterado:
        difs = diferencas_do_detalhe(dict(antigo), campos)
        if difs:
            registar_alteracoes(ref, difs)
    if altera:
        # Pode ser uma alteracao lida DEPOIS da seguinte (ler_detalhes
        # vai do mais recente para o mais antigo): so agora se sabe de
        # quem e, e a raiz verdadeira fica a saber.
        aplicar_alteracao(ref)
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
    dados, erro = perguntar_ao_dr(pedido, molde)
    if erro in ("casca", "apiVersion"):
        registar_expiracao_token("curl_detalhe", "o detalhe nao foi aceite "
                                 "(%s) nem depois de renovar as peças" % erro)
        return False, ("o DR não aceitou o pedido do detalhe (%s) nem depois "
                       "de renovar as peças; refaz a captura" % erro)
    if erro:
        return False, "falhou a leitura do anúncio: %s" % erro[:100]
    _guardar_detalhe(ref, dados)
    return True, ""


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

    # So a fonte do DR. As consultas preliminares da Vortal (B14)
    # tambem passam por detalhe_lido=0, mas o detalhe delas e outro
    # endpoint -- sem este filtro, o rsplit abaixo mandava um
    # "PT1.NTC.3785462" ao portal do DR como se fosse uma chave dele, e
    # a resposta sem JSON acabava a marcar o token como expirado. Um
    # falso alarme de captura expirada e pior que nao ler nada.
    condicao, valores = "detalhe_lido=0 AND COALESCE(fonte,'dr')='dr'", []
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
        dados, erro = perguntar_ao_dr(pedido, molde)
        if erro in ("casca", "apiVersion"):
            registar_expiracao_token("curl_detalhe", "o detalhe nao foi aceite "
                                     "(%s) nem depois de renovar as peças" % erro)
            return feitos, ("o DR não aceitou o detalhe (%s) nem depois de "
                            "renovar as peças; refaz a captura" % erro)
        if erro:
            break
        _guardar_detalhe(a["ref"], dados)
        feitos += 1
        time.sleep(1)
    return feitos, ""


# O DR publica rectificacoes como ANUNCIOS NOVOS, com o original citado
# no titulo ("Retificação ao Anúncio de procedimento n.º 19900/2026").
# Medido a 30/08/2026: 6 em dois anos, 4 com o ref extraivel. Anulacoes
# nao tem formato nenhum (3 titulos em texto livre em dois anos) e ficam
# de fora -- ver BACKLOG.md.
PADRAO_RETIFICACAO = re.compile(
    r"retifica[cç][aã]o\s+(?:a|ao|do)\s+an[uú]ncio[^0-9]*?(\d+/\d{4})",
    re.I)


def ligar_retificacoes():
    """Liga as rectificacoes ao anuncio original (B05).

    A releitura dos marcados nao as via: uma rectificacao e um ref novo,
    nao uma republicacao. Fica no historico do original sempre; entra na
    fila do resumo so quando o original esta marcado -- o resto e ruido.
    Idempotente pelo proprio historico.
    """
    with liga() as c:
        candidatos = c.execute(
            "SELECT ref, titulo FROM anuncios "
            "WHERE titulo_norm LIKE '%retificacao%anuncio%'").fetchall()
    ligadas = 0
    for r in candidatos:
        m = PADRAO_RETIFICACAO.search(r["titulo"] or "")
        if not m:
            continue
        alvo = m.group(1)
        with liga() as c:
            original = c.execute(
                "SELECT estado, fase_id FROM anuncios WHERE ref=?",
                (alvo,)).fetchone()
            ja = c.execute(
                "SELECT 1 FROM historico WHERE ref=? AND accao='rectificado'"
                " AND detalhe LIKE ?",
                (alvo, "%" + r["ref"] + "%")).fetchone()
        if not original or ja:
            continue
        registar(alvo, "rectificado", "pelo anúncio %s" % r["ref"],
                 quem="DR")
        if original["estado"] == "interessa" or original["fase_id"]:
            with liga() as c:
                c.execute(
                    "INSERT INTO alteracoes (ref, campo, antes, depois,"
                    " detectado_em) VALUES (?,?,?,?,?)",
                    (alvo, "retificacao", "", r["ref"],
                     datetime.now().strftime("%Y-%m-%d %H:%M")))
        ligadas += 1
    return ligadas


def reler_marcados(limite=25):
    """Rele o detalhe dos anuncios MARCADOS com prazo aberto (B05).

    Marcado = "interessa" ou com fase no quadro: e o que esta a ser
    trabalhado, e uma prorrogacao ou um preco base novo ai muda
    decisoes. A base toda nao se rele -- 5 mil anuncios a 1 s cada eram
    85 minutos por verificacao a vigiar o que ninguem quer.

    A comparacao com o guardado e do _guardar_detalhe(), que poe as
    diferencas na fila `alteracoes` e no historico da ficha. Os de
    prazo passado ficam de fora: o que muda num anuncio fechado ja nao
    muda decisao nenhuma.
    """
    par, aviso = _molde_detalhe()
    if not par:
        return 0, aviso
    pedido, molde = par
    variaveis = molde["screenData"]["variables"]
    hoje = datetime.now().date().isoformat()
    with liga() as c:
        # So a fonte do DR: uma consulta preliminar da Vortal (B14) nao
        # tem pagina de detalhe no DR para reler
        # Um original ja alterado rele-se pela pagina da ALTERACAO mais
        # recente, que e a versao em vigor: a pagina dele no DR nunca
        # muda, e rele-la punha o prazo antigo por cima do novo.
        marcados = c.execute(
            "SELECT COALESCE(a.alterado_por, a.ref) ref,"
            " COALESCE((SELECT x.url FROM anuncios x WHERE x.ref=a.alterado_por),"
            " a.url) url"
            " FROM anuncios a WHERE a.detalhe_lido=1"
            " AND COALESCE(fonte,'dr')='dr'"
            " AND (a.estado='interessa' OR a.fase_id IS NOT NULL)"
            " AND a.prazo != '' AND a.prazo >= ?"
            " ORDER BY a.prazo LIMIT ?", (hoje, limite)).fetchall()
    feitos = 0
    for a in marcados:
        variaveis["Key"] = a["url"].rsplit("/", 1)[-1]
        variaveis["Tipo"] = "anuncio-procedimento"
        dados, erro = perguntar_ao_dr(pedido, molde)
        if erro in ("casca", "apiVersion"):
            registar_expiracao_token("curl_detalhe", "o detalhe nao foi aceite "
                                     "(%s) nem depois de renovar as peças" % erro)
            return feitos, ("o DR não aceitou o detalhe (%s) nem depois de "
                            "renovar as peças; refaz a captura" % erro)
        if erro:
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
            altera = campos["altera"] if campos["altera"] != a["ref"] else ""
            # Um original ja alterado fica com os campos em vigor, que
            # sao os da alteracao e nao os do proprio texto (a mesma
            # guarda do _guardar_detalhe); agrupar_alteracoes() volta a
            # po-los a seguir, e este UPDATE nao os pode desfazer antes.
            if (c.execute("SELECT alterado_por FROM anuncios WHERE ref=?",
                          (a["ref"],)).fetchone() or {"alterado_por": None}
                    )["alterado_por"]:
                c.execute("UPDATE anuncios SET nif=?, altera=? WHERE ref=?",
                          (campos["nif"], altera, a["ref"]))
            else:
                c.execute("""UPDATE anuncios SET cpv=?, prazo=?, preco_base=?,
                             plataforma=?, link_pecas=?, nif=?, altera=?
                             WHERE ref=?""",
                          (campos["cpv"], campos["prazo"], campos["preco_base"],
                           campos["plataforma"], campos["link_pecas"],
                           campos["nif"], altera, a["ref"]))
            feitos += 1
    agrupar_alteracoes()
    return feitos


# ------------------------------------ segunda fonte: Vortal (B14)
#
# Decisao do Afonso a 31/08/2026: avancar, MAS so com o que a parte L
# nao publica -- consultas preliminares -- e sem duplicar anuncios do
# DR. A pesquisa publica da Vortal (medida nesse dia; receita completa
# no BACKLOG, seccao B14) devolve JSON com tudo; filtra-se por tipo e
# pais, e cada consulta entra como anuncio com fonte='vortal' e um ref
# natural (o PT1.NTC.x), que nunca colide com os refs do DR -- e o
# INSERT OR IGNORE garante que rever a mesma consulta nao mexe na
# triagem dela.
# [LEGAL] [RISCO] os avisos do BACKLOG mantem-se: endpoint nao
# documentado, pode mudar (R4/R5). A falha e isolada -- a recolha do
# DR nunca espera por isto -- e desliga-se com "vortal_preliminares":
# false no config.json.

VORTAL_PESQUISA = ("https://community.vortal.biz/public/api/Tendering/"
                   "SearchTenders")
VORTAL_FICHA = "https://community.vortal.biz/Public/contract-notice-view/%s/"
# O rotulo do tipo muda com o idioma da sessao: "GovPT - Consulta
# Preliminar" em pt e "Quick Tender GovPT" em en -- verificado item a
# item a 31/08/2026 (o mesmo PT1.NTC com os dois rotulos). Compara-se
# em minusculas e aceitam-se os dois.
TIPOS_PRELIMINAR = ("govpt - consulta preliminar", "quick tender govpt")

# O detalhe da consulta preliminar. Medido a 01/09/2026 nas 24 que ja
# estavam na base: 100% com CPV, 100% com NIPC, 100% com local, 75% com
# pecas -- e zero falhas, por requests puro, sem sessao iniciada e com o
# PT1.NTC as claras. A pesquisa (SearchTenders) NAO traz nada disto: os
# 16 campos dela sao titulo, entidade, datas, estado e tipo, e mais
# nada. Sem esta segunda chamada, uma consulta preliminar entrava sem
# CPV -- invisivel a todos os filtros por CPV, ao recorte do interesse e
# aos alertas -- e sem NIPC, que e a chave por onde a entidade se cruza
# com o corpus de contratos.
#
# Nao confundir com GetPublicTenderInformation, o primeiro salto das
# pecas: esse so aceita o identificador cifrado que o DR publica e
# responde 500 ao PT1.NTC (medido nos mesmos anuncios).
VORTAL_REGIAO = ("https://community.vortal.biz/public/api/"
                 "ContractNoticeDetail/GetRegionConfigurationByContractNoticeUId")

# As seccoes do texto que se monta a partir do detalhe, na ordem em que
# aparecem na ficha. A chave e o **nome** do campo na API e nunca o
# rotulo: o rotulo muda com o idioma da sessao, licao que o tipo do
# procedimento ja tinha dado (TIPOS_PRELIMINAR aceita dois rotulos do
# mesmo tipo por causa disso).
CAMPOS_PRELIMINAR = (
    ("2 - CONSULTA", (
        ("AE2_RequestInfoCN_RequestReference", "Referência da consulta"),
        ("AE3_RequestInfoCN_RequestName", "Designação"),
        ("AE4_RequestInfoCN_Phase", "Fase"),
        ("AE7_RequestInfoCN_Description", "Descrição"),
        ("AE9_RequestInfoCN_ProcedureType", "Tipo de consulta"),
    )),
    ("3 - CLASSIFICAÇÃO CPV", (
        ("AG1_CPVClassificationCN_MainVocabulary", "Vocabulário principal"),
    )),
    ("4 - OBJECTO DO CONTRATO", (
        ("AI1_ObjectOfContractCN_TypeOfContract", "Tipo de contrato"),
        ("AI7_ObjectOfContractCN_FullLocation", "Local de execução"),
    )),
    ("5 - PRAZOS", (
        ("AJ3_SchedulingCN_RequestOnlinePublishingDate", "Publicação"),
        ("AJ7_SchedulingCN_DueDateForReceivingReplies",
         "Data limite de recepção de propostas"),
    )),
)
CAMPO_CARTAO = "AA1_ManagingAuthorityCN_BusinessCard"
CAMPO_CPV = "AG1_CPVClassificationCN_MainVocabulary"
CAMPO_DOCS = "EA2_AvailableDocumentssCN_ContractDocuments"
CAMPO_QUESTIONARIO = "CB1_SummaryCN_QuestionnaireHTML"


def _texto_do_preco(valor):
    """Um float da API no formato portugues da coluna preco_base
    ("478.500,00 EUR"), que e o que euros_do_texto() e o resto da
    aplicacao ja sabem ler."""
    if not valor:
        return ""
    s = "{:,.2f}".format(float(valor))
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".") + " EUR"


def _domingo_final(ano, mes):
    """O ultimo domingo de um mes de 31 dias."""
    ultimo = datetime(ano, mes, 31)
    return ultimo - timedelta(days=(ultimo.weekday() + 1) % 7)


def hora_de_lisboa(iso):
    """A data/hora UTC da Vortal na hora legal de Portugal continental.

    A API devolve tudo em UTC ("2026-09-03T22:59:00Z") e a propria
    Vortal mostra 23:59 na pagina: no Verao, Lisboa e UTC+1. Escrever o
    UTC na ficha punha o prazo uma hora mais cedo do que a plataforma
    diz -- e um prazo e a informacao pela qual se perde uma proposta.

    A regra e a da UE e nao muda: hora de Verao do ultimo domingo de
    Marco as 01:00 UTC ao ultimo domingo de Outubro as 01:00 UTC.
    Faz-se a conta a mao porque a biblioteca padrao so traz fusos com
    nome a partir do zoneinfo, que depende de dados do sistema que este
    Windows nao garante. Devolve ISO "AAAA-MM-DD HH:MM"; o que nao for
    data volta como veio.
    """
    m = re.match(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})", (iso or "").strip())
    if not m:
        return " ".join(str(iso or "").split())
    quando = datetime.strptime(m.group(1) + " " + m.group(2), "%Y-%m-%d %H:%M")
    verao = (_domingo_final(quando.year, 3) + timedelta(hours=1)
             <= quando
             < _domingo_final(quando.year, 10) + timedelta(hours=1))
    if verao:
        quando += timedelta(hours=1)
    return quando.strftime("%Y-%m-%d %H:%M")


def _valor_do_campo(valor):
    """O valor de um campo do detalhe, ja como texto.

    A API mistura tres formas no mesmo sitio: texto simples, uma data
    (dict com `dateValue` em UTC) e o cartao da entidade (dict com nome,
    NIF e localizacao). Um str() ingenuo escrevia o dicionario inteiro
    na ficha.
    """
    if isinstance(valor, dict):
        if valor.get("dateValue"):
            return data_hora_pt(hora_de_lisboa(str(valor["dateValue"])))
        return ""
    return " ".join(str(valor or "").split())


def _campos_da_preliminar(dados):
    """A regionConfiguration achatada em {nome: valor}."""
    if not isinstance(dados, dict):
        return {}
    return {x.get("name"): x.get("value")
            for x in (dados.get("regionConfiguration") or [])
            if isinstance(x, dict) and x.get("name")}


def _artigos_do_questionario(sessao, endereco):
    """As linhas da tabela de artigos do questionario publico.

    Numa consulta preliminar isto E o conteudo: a entidade lista o que
    quer comprar, item a item, com quantidade e unidade -- e e a unica
    parte que diz mais do que o titulo. Vem em HTML com o CSS todo
    inline (6 KB de estilos para 500 caracteres de tabela), por isso
    tira-se o <style> ANTES de despir as etiquetas, senao o texto sai
    com a folha de estilos dentro.
    """
    if not endereco:
        return []
    try:
        pagina = sessao.get(endereco, timeout=60).text
    except requests.RequestException:
        return []
    pagina = re.sub(r"(?is)<(style|script).*?</\1>", " ", pagina)
    # O cabecalho da tabela vem em <th> soltos dentro do <thead>, sem
    # <tr> nenhum -- medido no HTML que a Vortal serve. Sem esta linha,
    # "1 | Luvas | 1500,00 | UNID" nao dizia qual dos numeros e a
    # quantidade.
    blocos = []
    cabeca = re.search(r"(?is)<thead[^>]*>(.*?)</thead>", pagina)
    if cabeca and "<tr" not in cabeca.group(1).lower():
        blocos.append(cabeca.group(1))
    blocos.extend(re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", pagina))
    linhas = []
    for bruta in blocos:
        celulas = []
        for celula in re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", bruta):
            limpa = html.unescape(re.sub(r"<[^>]+>", " ", celula))
            limpa = " ".join(limpa.split())
            if limpa:
                celulas.append(limpa)
        if celulas:
            linhas.append(" | ".join(celulas))
    return linhas


def detalhe_da_preliminar(sessao, ref, com_artigos=True):
    """(campos, aviso) do detalhe de uma consulta preliminar.

    `campos` e o dicionario pronto a gravar (cpv, nif, entidade, texto,
    link_pecas); `aviso` e a razao quando nao houve resposta. Nunca
    levanta: a recolha do DR nao pode cair por causa desta segunda
    fonte.
    """
    try:
        resposta = sessao.get(VORTAL_REGIAO, timeout=60,
                              params={"contractNoticeUId": ref,
                                      "langCode": "pt"})
        dados = resposta.json()
    except (requests.RequestException, ValueError) as erro:
        return {}, "o detalhe de %s falhou: %s" % (ref, str(erro)[:100])
    campos = _campos_da_preliminar(dados)
    if not campos:
        return {}, "o detalhe de %s veio vazio" % ref

    cartao = campos.get(CAMPO_CARTAO)
    cartao = cartao if isinstance(cartao, dict) else {}
    entidade = " ".join(str(cartao.get("name") or "").split())
    nif = re.sub(r"\D", "", str(cartao.get("nif") or ""))[:9]

    # A coluna `cpv` guarda 8 digitos sem digito de controlo, separados
    # por ", " -- e o formato que prefixo_cpv() e a arvore ja leem. A
    # Vortal escreve "33140000-3 - Material medico de consumo (CPV)".
    cpv = ", ".join(dict.fromkeys(
        re.findall(r"\b(\d{8})-\d\b",
                   str(campos.get(CAMPO_CPV) or ""))))

    partes = ["Consulta preliminar %s, na plataforma Vortal" % ref, ""]
    partes.append("1 - ENTIDADE ADJUDICANTE")
    if entidade:
        partes.append("Designação da entidade adjudicante: " + entidade)
    if nif:
        partes.append("NIPC: " + nif)
    if cartao.get("location"):
        partes.append("Localização: "
                      + " ".join(str(cartao["location"]).split()))
    for titulo, linhas in CAMPOS_PRELIMINAR:
        escritas = []
        for nome, rotulo in linhas:
            valor = _valor_do_campo(campos.get(nome))
            if valor:
                escritas.append("%s: %s" % (rotulo, valor))
        if escritas:
            partes.append("")
            partes.append(titulo)
            partes.extend(escritas)

    if com_artigos:
        artigos = _artigos_do_questionario(
            sessao, _valor_do_campo(campos.get(CAMPO_QUESTIONARIO)))
        if artigos:
            partes.append("")
            partes.append("6 - ARTIGOS SOLICITADOS")
            partes.extend(artigos)

    documentos = campos.get(CAMPO_DOCS)
    documentos = documentos if isinstance(documentos, list) else []
    if documentos:
        partes.append("")
        partes.append("7 - DOCUMENTOS DISPONÍVEIS")
        for doc in documentos:
            if isinstance(doc, dict) and doc.get("name"):
                partes.append("Documento: " + str(doc["name"]))

    return {"cpv": cpv, "nif": nif, "entidade": entidade,
            "texto": "\n".join(partes), "documentos": len(documentos)}, ""


def ler_preliminares(limite=25):
    """Le o detalhe das consultas preliminares que ainda o nao tem.

    Separada da recolha pela mesma razao que ler_detalhes() e separada
    de recolher(): a pesquisa da uma linha por consulta e o detalhe e um
    pedido por consulta. Corre sobre `detalhe_lido=0`, que e o que a
    fila do DR usa -- e por isso ler_detalhes() filtra a fonte, senao
    pescava um PT1.NTC para ir procurar no diariodarepublica.pt.

    A entidade so se sobrescreve quando o detalhe traz nome: a pesquisa
    ja tinha posto um, e trocar um nome bom por vazio era perder
    informacao. Devolve (lidas, aviso).
    """
    with liga() as c:
        pendentes = [r["ref"] for r in c.execute(
            "SELECT ref FROM anuncios WHERE fonte='vortal' AND detalhe_lido=0"
            " ORDER BY data_pub DESC LIMIT ?", (limite,)).fetchall()]
    if not pendentes:
        return 0, ""
    sessao = requests.Session()
    sessao.headers["User-Agent"] = NAVEGADOR
    lidas, aviso = 0, ""
    for ref in pendentes:
        campos, falha = detalhe_da_preliminar(sessao, ref)
        if falha:
            aviso = aviso or falha
            continue
        with liga() as c:
            c.execute(
                "UPDATE anuncios SET cpv=?, nif=?, texto=?, detalhe_lido=1,"
                " entidade=COALESCE(NULLIF(?,''), entidade),"
                " entidade_norm=simplifica(COALESCE(NULLIF(?,''), entidade))"
                " WHERE ref=?",
                (campos["cpv"], campos["nif"], campos["texto"],
                 campos["entidade"], campos["entidade"], ref))
        lidas += 1
        time.sleep(0.4)
    return lidas, aviso


def _guardar_preliminar(item):
    """Poe uma consulta preliminar na base. Devolve 1 se era nova."""
    ref = (item.get("uniqueIdentifier") or "").strip()
    if not ref:
        return 0
    titulo = " ".join((item.get("description") or "").split())
    entidade = (item.get("authorityName") or "").strip()
    ligacao = VORTAL_FICHA % ref
    # detalhe_lido=0 de proposito: a pesquisa nao traz CPV nem NIPC, e
    # quem os vai buscar e ler_preliminares(), que corre logo a seguir.
    # Marcar como lido aqui era dizer que o anuncio esta completo quando
    # lhe falta o campo por que toda a gente filtra.
    with liga() as c:
        feito = c.execute(
            "INSERT OR IGNORE INTO anuncios (ref, titulo, entidade, "
            "data_pub, tipo, url, prazo, preco_base, plataforma, "
            "detalhe_lido, link_pecas, fonte, titulo_norm, entidade_norm) "
            "VALUES (?,?,?,?,?,?,?,?,?,0,?,'vortal',?,?)",
            (ref, titulo, entidade,
             hora_de_lisboa(item.get("publishDate") or "")[:10],
             "Consulta preliminar", ligacao,
             hora_de_lisboa(item.get("deadline") or "")[:10],
             _texto_do_preco(item.get("basePrice")), "vortal",
             ligacao, simplifica(titulo), simplifica(entidade)))
        return feito.rowcount


def recolher_vortal(paginas=6, dias=7):
    """Traz as consultas preliminares da pesquisa publica da Vortal.

    So o tipo preliminar e o pais PT. A lista vem por data de
    publicacao descendente: para-se quando a pagina inteira ja e mais
    antiga que a janela de `dias`, ou no tecto de `paginas` -- com duas
    verificacoes por dia, uma janela de 7 dias nunca deixa nada por
    apanhar. Devolve (novas, aviso).
    """
    piso = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")
    sessao = requests.Session()
    sessao.headers["User-Agent"] = NAVEGADOR
    novas = 0
    for pagina in range(1, paginas + 1):
        try:
            r = sessao.post(VORTAL_PESQUISA, timeout=60, json={
                "contractNoticeActive": True,
                "pageNumber": pagina, "pageSize": 50})
            dados = r.json()
        except (requests.RequestException, ValueError) as erro:
            return novas, "a pesquisa da Vortal falhou: %s" % str(erro)[:120]
        itens = dados.get("items") or []
        if not itens:
            break
        for item in itens:
            if (item.get("country") or "").strip() != "PT":
                continue
            tipo = (item.get("procedureTypeLabel") or "").strip().lower()
            if tipo not in TIPOS_PRELIMINAR:
                continue
            if (item.get("publishDate") or "")[:10] < piso:
                continue
            novas += _guardar_preliminar(item)
        if (itens[-1].get("publishDate") or "")[:10] < piso:
            break
        time.sleep(1)
    # A pesquisa da a linha; o CPV, o NIPC e o conteudo vem do detalhe,
    # um pedido por consulta. O limite serve as que ficaram para tras
    # quando o endpoint esteve em baixo -- com duas verificacoes por dia
    # e ~3 consultas novas por dia, 25 apanha sempre a folga.
    _, aviso = ler_preliminares()
    return novas, aviso


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
    # O link do DR traz um identificador cifrado, que se troca pelo
    # PT1.NTC.x via GetPublicTenderInformation. O link das consultas
    # preliminares (B14) ja traz o PT1.NTC.x as claras -- salta-se o
    # primeiro salto e a cadeia e a mesma dai para a frente.
    lista = []
    m = re.search(r"(PT\d+\.NTC\.\d+)", link)
    if not m:
        lista, aviso = _info_vortal(sessao, link)
        m = re.search(r"(PT\d+\.NTC\.\d+)", aviso)
    if not lista:
        # Sem documentos no primeiro salto: e o anuncio publicado na
        # comunidade, e a lista dele sai do segundo.
        if not m:
            return [], []
        resposta = sessao.get(VORTAL_DOCS, timeout=90,
                              params={"contractNoticeUId": m.group(1)}).json()
        lista = resposta if isinstance(resposta, list) else []
    saida, grandes = [], []
    for doc in lista:
        endereco = doc.get("downloadUrl")
        if not endereco:
            continue
        # As duas respostas nao chamam o nome do ficheiro o mesmo:
        # "name" na do anuncio, "documentName" na do procedimento.
        rotulo = doc.get("name") or doc.get("documentName") or ""
        nome, dados = _descarregar(sessao, endereco)
        if dados is None:
            if rotulo:
                grandes.append(rotulo)
            continue
        saida.append((nome_seguro(rotulo or nome or "documento"), dados))
    return saida, grandes


def _info_vortal(sessao, link):
    """(documentos, endereco do anuncio) do primeiro salto da Vortal.

    O link do DR traz um identificador cifrado; GetPublicTenderInformation
    troca-o pelo que ha. **Medido a 01/09/2026: a resposta vem de duas
    formas** e o radar so sabia ler uma --

      - com `contractNoticeUrl`, e `documentList` vazia: o procedimento
        esta publicado na comunidade e as pecas saem do segundo salto
        (GetContractNoticeDocuments), que e o caminho de sempre;
      - com `documentList` cheia e **sem** `contractNoticeUrl`: as pecas
        vem ja aqui, cada uma com o seu `downloadUrl`.

    A segunda forma era metade dos anuncios da Vortal e dava zero peças
    em silencio -- o radar trazia o anuncio e mais nada (visto no
    22005/2026). Devolve-se tambem o endereco do anuncio porque e dele
    que sai o link do procedimento (link_proc), o que "Abrir plataforma"
    passou a abrir.
    """
    identificador = link.rstrip("/").rsplit("/", 1)[-1]
    try:
        info = sessao.get(VORTAL_INFO, timeout=90, params={
            "uniqueIdentifierEncrypted": identificador,
            "languageCode": "pt"}).json()
    except (requests.RequestException, ValueError):
        return [], ""
    if not isinstance(info, dict):
        return [], ""
    docs = [d for d in (info.get("documentList") or [])
            if isinstance(d, dict) and d.get("downloadUrl")]
    return docs, (info.get("contractNoticeUrl") or "")


# Aquelas de que se conseguem trazer as pecas sem sessao iniciada. Serve
# tambem para o ecra de indicadores nao chamar "sem acesso" ao que se
# obtem, nem prometer o que nao se obtem.
PLATAFORMAS_COM_PECAS = ("acingov", "vortal", "compraspt", "anogov")

# --- o procedimento na plataforma, que nao e o mesmo que as pecas
#
# O DR nunca publica o endereco da PAGINA do procedimento: os dois URL
# que traz sao o da raiz da plataforma ("URL para Apresentacao", que da
# sempre na porta de entrada) e o das pecas. "Abrir plataforma" abria o
# segundo, e isso levava a sitios que nao sao o procedimento -- na
# acingov descarregava um ZIP, na Vortal abria a lista dos ficheiros.
# O que ha, medido a 01/09/2026, plataforma a plataforma:
#
#   vortal     ha pagina publica do procedimento
#              (Public/contract-notice-view/PT1.NTC.x) e resolve-se pela
#              API a partir do link cifrado das pecas. Guarda-se em
#              anuncios.link_proc para nao se ir la duas vezes.
#   anogov     o acessoDocs.jsp E a pagina publica do procedimento: traz
#   compraspt  a referencia interna, o objecto e o tipo por cima da
#              lista dos documentos. Nao existe outra -- o resto da
#              aplicacao e JSF por POST, sem endereco proprio.
#   acingov    **nao ha.** A lista publica tem um botao "consultar
#              procedimento" que so abre "para aceder a este
#              procedimento inicie sessao". O que se pode oferecer e a
#              pesquisa publica, e o botao di-lo em vez de prometer.
VORTAL_PROCEDIMENTO = "https://community.vortal.biz/Public/contract-notice-view/%s/"
ACINGOV_PESQUISA = ("https://www.acingov.pt/acingovprod/2/zonaPublica/"
                    "zona_publica_c/indexProcedimentos")


def link_do_procedimento(a):
    """(endereco, rotulo, dica) do botao que abre o procedimento.

    Sem rede: o que precisa de rede (a Vortal) passa pela rota
    /plataforma/<ref>, que resolve uma vez e guarda. Devolve
    (None, "", "") quando nao ha nada que se possa abrir.
    """
    plat = (a["plataforma"] or "").strip()
    link = (a["link_pecas"] or "").strip()
    proc = (_valor(a, "link_proc") or "").strip()
    if plat == "vortal":
        if proc:
            return proc, "Abrir na Vortal", "a página do procedimento"
        if re.search(r"(PT\d+\.NTC\.\d+)", link):
            return (VORTAL_PROCEDIMENTO % re.search(r"(PT\d+\.NTC\.\d+)",
                                                    link).group(1),
                    "Abrir na Vortal", "a página do procedimento")
        if link:
            return ("/plataforma/" + quote(a["ref"], safe=""),
                    "Abrir na Vortal", "a página do procedimento")
    if plat == "acingov":
        return (ACINGOV_PESQUISA, "Procurar na acingov",
                "a acingov não tem página pública do procedimento — só se "
                "vê com sessão iniciada; isto abre a pesquisa pública")
    if link:
        # anogov, compraspt e a ESPAP: o acessoDocs e a pagina do
        # procedimento. Para o resto, e o unico endereco que ha.
        return (link, "Abrir na plataforma" if not plat
                else "Abrir na " + plat, "a página do procedimento")
    return None, "", ""


def _valor(linha, coluna, omissao=None):
    """Uma coluna de um sqlite3.Row que pode nao existir na base ainda.

    A migracao corre no arranque, mas os testes montam bases a mao: uma
    coluna nova nao pode rebentar quem so quer desenhar a ficha.
    """
    try:
        return linha[coluna]
    except (IndexError, KeyError):
        return omissao


# Um prazo a menos de tantos dias e "urgente". E o mesmo numero no filtro
# da lista e no aviso dos indicadores, de proposito: o numero que os
# indicadores mostram tem de dar exactamente a lista que a ligacao abre.
# E a omissao; o valor em uso le-se por dias_urgente(), que aceita o
# config.json por cima (B13).
DIAS_URGENTE = 10


def dias_urgente(cfg=None):
    """A janela do "urgente", em dias: o config.json (dias_urgente) por
    cima da omissao. Lixo, zero ou negativo voltam a omissao -- uma
    janela de 0 dias esvaziava o filtro em silencio. Continua a ser UMA
    janela: quem a le sao janela_urgente() e os rotulos, todos daqui."""
    cfg = ler_config() if cfg is None else cfg
    try:
        n = int(cfg.get("dias_urgente", DIAS_URGENTE))
    except (TypeError, ValueError):
        return DIAS_URGENTE
    return n if n >= 1 else DIAS_URGENTE

# Abaixo disto nao se mostra percentagem de triagem. "100% ficou como
# interessa" sobre dois casos e ruido com ar de conclusao.
MINIMO_PARA_TAXA = 20

# Abaixo disto nao se desenha a regua de quartis do historico de precos.
# Com 3 contratos, "mais barato" e "25%" sao o mesmo contrato repetido:
# quartis de meia duzia de pontos sao decoracao, nao estatistica. A
# tabela dos proprios contratos, que fica, diz mais.
MINIMO_PARA_ESCADA = 8

# Valor que representa "o anuncio nao diz qual e", no filtro e no ecra de
# indicadores. Nao e uma plataforma, e a ausencia de uma.
#
# **So conta os que ja tem detalhe lido.** O rotulo do selector dizia
# "(nenhuma) (56)" e a lista devolvia 60 645, porque no rotulo era "lido,
# sem plataforma" e no filtro era "sem plataforma" -- e sem detalhe lido
# ainda nao ha plataforma nenhuma. Quem ainda nao foi lido tem balde
# proprio, o de baixo, que antes nao existia em lado nenhum.
SEM_PLATAFORMA = "(nenhuma)"
POR_LER = "(por ler)"

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
        # O \f em linha propria marca a fronteira de pagina (B12): e por
        # ele que a ficha diz de que paginas veio o recorte. Linha
        # propria de proposito -- colado a primeira linha da pagina, o
        # sem_indice levava a marca junto com uma linha de sumario.
        texto = "\n\f\n".join((p.extract_text() or "") for p in leitor.pages)
    except Exception as erro:
        # os PDFs do anuncio do DR vem cifrados com AES e rebentam aqui,
        # mas nao fazem falta: o texto do anuncio ja veio do portal
        return "", "erro: %s" % str(erro)[:80]
    if paginas and len(texto) / paginas < CHARS_POR_PAGINA_MINIMO:
        return "", "scan"
    return texto, "ok"


# ---------------------------------------- OCR das pecas digitalizadas
#
# Medido a 02/09/2026: dos 12 CE/PC reais, 2 sao digitalizacoes sem
# camada de texto -- ficavam em 'scan' e a leitura pelo modelo nem
# arrancava. O RapidOCR (os modelos PP-OCR em ONNX, sem o framework
# PaddlePaddle) le portugues com acentos e cedilhas com o modelo que a
# propria roda traz, sem descarregar nada: numa pagina sintetica A4 a
# 150 dpi, 10 linhas em 10 e "175.000,00 EUR" certo. O modelo chines/
# ingles do rapidocr_onnxruntime 1.4 perdia os acentos E lia
# "175.oo0,00", que o euros_do_texto() nao come -- nao e alternativa.
# Custa 6 s por pagina em CPU no PC, isolado, e 8 s pelo `--ocr`, que
# tambem carrega o motor e grava (medido a 03/09/2026 a escala 2,5; o
# "~28 s por pagina" de 02/09 NAO se reproduz, e numa escala mais alta
# -- ver o ESTADO.md): um CE de 20 paginas sao 2 a 3 minutos, em
# thread de fundo (a fila das pecas ou a da analise).
#
# O radar funciona sem o pacote, como ate aqui. Com ele, os 'scan'
# passam a 'ocr' (texto com as marcas \f de sempre, que a ficha e a
# analise ja entendem) ou a 'imagem' (o OCR correu e nao achou texto).
# 'scan' passa a querer dizer "sem camada de texto e ainda sem OCR
# tentado": e o que a segunda passagem do extrair_textos() apanha
# quando ha motor, uma vez por documento. Desliga-se com "ocr": false
# no config.json.

# A escala mede-se pelos VALORES lidos, nunca pelo aspecto do texto.
# Medido a 03/09/2026 nos dois digitalizados da base (o CE de 20
# paginas do 20968/2026 e o [CA] de 6 do 21295/2026), de 1,0 a 4,0:
#
#   escala   s/pag   preco base   artigo 332   tabela "≥170 cv"
#   1,0       3,9        ok           --            "110"
#   1,25      4,2        ok           --            "110"
#   1,5       3,6        ok           ok             "10"
#   1,75      4,9        ok           --        "170" (sem o ≥)
#   2,0       5,1     PERDIDO     PERDIDO             ok
#   2,5       6,0        ok           ok              ok
#   3,0       5,5        ok           ok              ok
#   4,0       6,0        ok           ok              ok
#
# Abaixo de 2,0 o modelo nao desfaz a linha: ADIVINHA-A. Leu "110" e
# "10" onde a pagina diz "≥170 cv" (confirmado a olho na pagina 14), e
# no [CA] o 2,0 leu 2036.08.06 onde esta 2026.08.06. Um numero errado
# passa pelo euros_do_texto() e pelo modelo como se fosse dado; uma
# linha desfeita ve-se. Por isso a metrica "linhas desfeitas" mente ao
# contrario -- premeia a escala que troca falha visivel por erro
# silencioso -- e a decisao e sempre pelo valor confirmado na pagina.
#
# 2,5 e a escala mais baixa em que os dois documentos leem certo todos
# os valores confirmados; acima nao ganha nada e comeca a perder
# caracteres. O 2,0 anterior perdia a clausula do preco base inteira.
OCR_ESCALA = 2.5                  # 180 dpi sobre um PDF a 72
OCR_MINIMO_POR_PAGINA = 20        # chars por pagina; abaixo e imagem
_OCR = {"motor": None, "erro": ""}


def ocr_ligado():
    return bool(ler_config().get("ocr", True))


def ocr_instalado():
    """Sem carregar o motor: e para a saude dos indicadores."""
    import importlib.util
    return importlib.util.find_spec("rapidocr") is not None


def motor_ocr():
    """O RapidOCR, carregado uma vez por processo (0,4 s e ~60 MB).

    None quando nao esta instalado ou nao arranca; a razao fica na
    marca `ocr_ultimo_erro`, que os indicadores mostram, e nao se volta
    a tentar neste processo -- um import que falha a cada documento
    era o mesmo erro repetido cem vezes.
    """
    if _OCR["motor"] is None and not _OCR["erro"]:
        try:
            from rapidocr import RapidOCR
            _OCR["motor"] = RapidOCR(params={"Global.log_level": "warning"})
        except ImportError:
            _OCR["erro"] = "rapidocr por instalar"
        except Exception as erro:
            _OCR["erro"] = (str(erro)[:200] or type(erro).__name__)
            marca_erro("ocr_ultimo_erro", "ocr", _OCR["erro"])
    return _OCR["motor"]


def texto_por_ocr(caminho, motor=None, escala=OCR_ESCALA):
    """(texto, estado) de um PDF sem camada de texto, pelo OCR.

    'ocr' com o texto por pagina (marca \f em linha propria, como o
    pypdf), 'imagem' quando o OCR corre e nao encontra texto, 'scan'
    quando nao ha motor nem PyMuPDF, e 'erro: ...' quando o ficheiro
    nao se desenha. Cada pagina desenha-se com o PyMuPDF (o mesmo do
    visualizador) e vai ao motor como imagem BGR, que e o que ele
    espera; as linhas saem pela ordem de leitura que o detector da.
    """
    motor = motor or motor_ocr()
    if motor is None:
        return "", "scan"
    try:
        import numpy
        import pymupdf
    except ImportError:
        return "", "scan"
    paginas = []
    try:
        with pymupdf.open(caminho) as doc:
            for pagina in doc:
                pix = pagina.get_pixmap(matrix=pymupdf.Matrix(escala, escala),
                                        colorspace=pymupdf.csRGB, alpha=False)
                imagem = numpy.frombuffer(pix.samples, dtype=numpy.uint8)
                imagem = imagem.reshape(pix.h, pix.w, pix.n)[:, :, ::-1]
                resultado = motor(numpy.ascontiguousarray(imagem))
                linhas = getattr(resultado, "txts", None) or ()
                paginas.append("\n".join(l for l in linhas if l))
    except Exception as erro:
        return "", "erro: ocr: %s" % str(erro)[:70]
    texto = "\n\f\n".join(paginas)
    if not paginas or len(texto) / len(paginas) < OCR_MINIMO_POR_PAGINA:
        return "", "imagem"
    return texto, "ocr"


def paginas_do_pdf_imagem(caminho):
    """Quantas paginas o visualizador proprio consegue desenhar.

    0 quando nao ha PyMuPDF (vive em libs/; o import e preguicoso para
    o resto do radar nao depender dele) ou o ficheiro nao abre -- e ai
    a pagina da peca cai para o <embed> do browser, como antes.
    """
    try:
        import pymupdf
    except ImportError:
        return 0
    try:
        with pymupdf.open(caminho) as doc:
            return doc.page_count
    except Exception:
        return 0


def imagem_da_pagina(caminho, n, escala=2.0, procurar=""):
    """PNG da pagina n (1-based) do PDF, ou None se nao der.

    E o visualizador proprio do radar: desenhar no servidor e a unica
    maneira de a peca abrir SEMPRE dentro da aplicacao -- o <embed>
    dependia da definicao do browser (com "transferir PDFs em vez de
    abrir" ligada, o Chrome mostra um cartao e o Abrir descarrega, que
    foi o que aconteceu ao Afonso a 31/08/2026). A escala 2x e para o
    texto ficar nitido em ecras normais.

    Com `procurar`, as ocorrencias do termo saem MARCADAS na propria
    pagina (destaque amarelo): a pesquisa acontece no documento, nao
    num bloco de texto a parte. A anotacao vive so nesta abertura do
    ficheiro -- nada se grava no PDF.
    """
    try:
        import pymupdf
    except ImportError:
        return None
    try:
        with pymupdf.open(caminho) as doc:
            if not 1 <= n <= doc.page_count:
                return None
            pagina = doc[n - 1]
            if procurar:
                try:
                    for sitio in pagina.search_for(procurar):
                        pagina.add_highlight_annot(sitio)
                except Exception:
                    pass       # pesquisa que falhe nao tira a pagina
            pix = pagina.get_pixmap(
                matrix=pymupdf.Matrix(escala, escala))
            return pix.tobytes("png")
    except Exception:
        return None


def paginas_com_termo(caminho, termo):
    """[(pagina, ocorrencias)] do termo no PDF, pela mesma pesquisa que
    desenha os destaques (case-insensitive, tal e qual esta escrito no
    documento). Vazio quando nao ha PyMuPDF ou o ficheiro nao abre."""
    if not (termo or "").strip():
        return []
    try:
        import pymupdf
    except ImportError:
        return []
    try:
        with pymupdf.open(caminho) as doc:
            saida = []
            for i, pagina in enumerate(doc, 1):
                achados = pagina.search_for(termo)
                if achados:
                    saida.append((i, len(achados)))
            return saida
    except Exception:
        return []


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


def texto_do_zip(caminho, papeis, motor=None):
    """O texto das peças que vierem dentro de um ZIP.

    Ha entidades que entregam o Caderno de Encargos como
    "1_CE_Clausulas_Juridicas_Tecnicas.zip", com as clausulas juridicas
    num PDF e as tecnicas noutro. Sem abrir, ficavam por ler. Com
    `motor`, um PDF de dentro que seja digitalizacao vai ao OCR.
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
                    if estado == "scan" and motor is not None:
                        texto, estado = texto_por_ocr(alvo, motor)
                    estados.append(estado)
                    if estado in ("ok", "ocr"):
                        partes.append(texto)
    except (zipfile.BadZipFile, OSError, KeyError) as erro:
        return "", "erro: %s" % str(erro)[:80]
    if partes:
        # A mesma marca de pagina entre PDFs do mesmo ZIP: a numeracao
        # segue pelo conjunto fora, e a ficha diz "pag. N do texto
        # extraido" -- num ZIP com varios PDFs nao ha outra verdade.
        return ("\n\f\n".join(partes),
                "ocr" if "ocr" in estados else "ok")
    # Nao sai texto por duas razoes muito diferentes, e dize-las trocadas
    # manda a pessoa buscar a ferramenta errada: um PDF cifrado nao se
    # resolve com OCR.
    erros = [e for e in estados if e.startswith("erro")]
    return "", (erros[0] if erros else "scan")


def extrair_textos(ref, motor=None):
    """Guarda o texto dos PDFs deste anuncio. Devolve (lidos, digitalizados).

    Duas passagens: a de sempre (o que ainda nao tem estado, e os
    "erro:" que se retentam) e, se houver OCR, a dos 'scan' com
    ficheiro em disco -- e essa que transforma um veredicto de
    digitalizacao em texto, uma vez por documento. O `motor` e o do
    motor_ocr() por omissao; nos testes e um falso.
    """
    with liga() as c:
        # Um "erro: ..." retenta-se: nao e um veredicto sobre o conteudo,
        # e uma falha da ferramenta, e a causa pode ter desaparecido --
        # 30 documentos ficaram presos num erro de dependencia em falta
        # que ja estava instalada. "scan" e "nao e PDF" sao veredictos e
        # esses ficam. Retenta-se aqui, e nao por botao, porque isto e
        # local, sem rede e sem orcamento, e so corre quando alguem ja
        # pediu as pecas ou a leitura deste anuncio.
        docs = c.execute("SELECT id,nome FROM documentos WHERE ref=? "
                         "AND (texto_estado IS NULL OR "
                         "texto_estado LIKE 'erro:%')", (ref,)).fetchall()
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
    # Segunda passagem: os 'scan' com ficheiro, se houver OCR. O motor
    # so se carrega quando ha mesmo o que ler -- um 'scan' sem ficheiro
    # (documento apagado do disco) fica como esta.
    with liga() as c:
        digitalizados = c.execute("SELECT id,nome FROM documentos WHERE ref=? "
                                  "AND texto_estado='scan'", (ref,)).fetchall()
    com_ficheiro = [(d, os.path.join(pasta, d["nome"])) for d in digitalizados
                    if os.path.exists(os.path.join(pasta, d["nome"]))]
    if com_ficheiro and ocr_ligado():
        motor = motor or motor_ocr()
    else:
        motor = None                # desligado no config: nem com motor
    if com_ficheiro and motor is not None:
        for d, caminho in com_ficheiro:
            papeis = papeis_da_peca(d["nome"])
            if e_pdf(caminho):
                texto, estado = texto_por_ocr(caminho, motor)
            elif papeis and zipfile.is_zipfile(caminho):
                texto, estado = texto_do_zip(caminho, papeis, motor)
            else:
                continue
            if estado == "scan":
                continue            # sem motor afinal: o veredicto fica
            with liga() as c:
                c.execute("UPDATE documentos SET texto=?, texto_estado=? "
                          "WHERE id=?", (texto, estado, d["id"]))
            if estado == "ocr":
                lidos += 1
                scans = max(0, scans - 1)
    return lidos, scans


def ocr_pendentes(ref=None, motor=None, diz=print):
    """Le pelo OCR os 'scan' com ficheiro em disco -- de um anuncio, ou
    de todos. E o `--ocr`: a segunda passagem do extrair_textos() so
    corre quando alguem pede as pecas ou a leitura DESSE anuncio, e os
    'scan' que ja estavam na base antes do OCR existir ficavam a
    espera de uma ficha aberta. Diz o que fez, documento a documento,
    com o tempo -- e o instrumento para medir o custo por pagina no PC.
    Devolve (lidos, sem_texto, por_fazer)."""
    with liga() as c:
        docs = c.execute(
            "SELECT ref, nome FROM documentos WHERE texto_estado='scan'"
            + (" AND ref=?" if ref else "") + " ORDER BY ref, nome",
            (ref,) if ref else ()).fetchall()
    if not docs:
        diz("não há digitalizações por ler" + (" em " + ref if ref else ""))
        return 0, 0, 0
    if not ocr_ligado():
        diz("o OCR está desligado no config.json (\"ocr\": false)")
        return 0, 0, len(docs)
    motor = motor or motor_ocr()
    if motor is None:
        diz("sem OCR: %s" % (_OCR["erro"] or "rapidocr por instalar"))
        return 0, 0, len(docs)
    lidos = sem_texto = por_fazer = 0
    for d in docs:
        caminho = os.path.join(pasta_do_anuncio(d["ref"]), d["nome"])
        if not os.path.exists(caminho):
            por_fazer += 1
            diz("  %s · %s: sem ficheiro em disco" % (d["ref"], d["nome"]))
            continue
        ini = time.time()
        extrair_textos(d["ref"], motor)
        with liga() as c:
            depois = c.execute("SELECT texto_estado, texto FROM documentos "
                               "WHERE ref=? AND nome=?",
                               (d["ref"], d["nome"])).fetchone()
        estado = depois["texto_estado"] if depois else "?"
        paginas = (depois["texto"] or "").count("\f") + 1 if depois and depois["texto"] else 0
        diz("  %s · %s: %s%s, %.0f s" % (
            d["ref"], d["nome"], estado,
            (" (%d páginas, %d caracteres)" % (paginas, len(depois["texto"])))
            if estado == "ocr" else "", time.time() - ini))
        if estado == "ocr":
            lidos += 1
        elif estado == "imagem":
            sem_texto += 1
        else:
            por_fazer += 1
    diz("%d lidos, %d sem texto, %d por fazer" % (lidos, sem_texto, por_fazer))
    return lidos, sem_texto, por_fazer


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


def _ancoras_do_config(bruto):
    """Valida ancoras vindas do config: lista de [prioridade, regex].

    Devolve tuplos como os de origem, ou None quando algo nao serve --
    e quem chama fica com as de origem. Um regex estragado no config
    nao pode calar uma leitura em silencio."""
    if not isinstance(bruto, list) or not bruto:
        return None
    fora = []
    for par in bruto:
        try:
            prioridade = int(par[0])
            padrao = str(par[1])
            re.compile(padrao)
        except (re.error, ValueError, TypeError, IndexError, KeyError):
            return None
        fora.append((prioridade, padrao))
    return tuple(fora)


def leituras_activas(cfg=None):
    """As leituras a fazer: as de origem, com o config.json por cima.

    B08: as ancoras e a instrucao de cada campo podem afinar-se sem
    mexer no codigo, em "leituras" no config.json:

        "leituras": {"objecto": {"quais": "programa",
                                 "ancoras": [[1, "objec?to"], [2, "sla"]],
                                 "instrucao": "..."}}

    So se substitui o que la estiver escrito E valido; o resto fica o de
    origem -- uma entrada estragada nunca desliga uma leitura. Campos
    NOVOS nao se aceitam por aqui: a tabela `analise` tem colunas fixas,
    e o 4o campo definido pelo utilizador fica para quando o caso de uso
    aparecer (registado no BACKLOG).
    """
    cfg = ler_config() if cfg is None else cfg
    por_cima = cfg.get("leituras")
    if not isinstance(por_cima, dict) or not por_cima:
        return list(LEITURAS)
    fora = []
    for nome, quais, ancoras, instrucao in LEITURAS:
        muda = por_cima.get(nome)
        if isinstance(muda, dict):
            if muda.get("quais") in ("encargos", "programa"):
                quais = muda["quais"]
            ancoras = _ancoras_do_config(muda.get("ancoras")) or ancoras
            if isinstance(muda.get("instrucao"), str) and muda["instrucao"].strip():
                instrucao = muda["instrucao"].strip()
        fora.append((nome, quais, ancoras, instrucao))
    return fora


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


def _janelas_do_recorte(texto, ancoras, tecto, janela=3500):
    """[(inicio, fim)] das zonas que o recorte leva, por ordem no texto.

    Vazio quando nenhuma ancora pega -- o recorte passa a ser o inicio
    do texto. E a parte comum de recorte_relevante() e de
    paginas_do_recorte(): o texto que vai ao modelo e as paginas que a
    ficha declara tem de sair DAS MESMAS janelas, senao a fonte mentia.
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
        return []

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
        partes.append((i, j))
        i = j
    return partes


def recorte_relevante(texto, ancoras, tecto, janela=3500):
    """As partes do documento que respondem ao que se procura.

    Um Caderno de Encargos tem 50 mil caracteres e so uns 10 mil dizem
    respeito ao objecto e a equipa; o resto sao clausulas de rotina
    (forca maior, subcontratacao, penalidades). O tecto de tokens por
    minuto da API obriga a escolher, e escolher tambem melhora a
    leitura, por tirar ruido do caminho do modelo.
    """
    janelas = _janelas_do_recorte(texto, ancoras, tecto, janela)
    if not janelas:
        return texto[:tecto]
    return "\n[...]\n".join(texto[i:j] for i, j in janelas)[:tecto]


def paginas_do_recorte(texto, ancoras, tecto, janela=3500):
    """As paginas (a contar de 1) de onde o recorte veio (B12).

    So quando o texto tem as marcas de pagina (\\f) que o extractor poe:
    os textos extraidos antes das marcas nao sabem paginas, e devolve-se
    [] em vez de as inventar. A pagina de um offset e contar os \\f
    antes dele."""
    if "\f" not in texto:
        return []
    janelas = (_janelas_do_recorte(texto, ancoras, tecto, janela)
               or [(0, min(len(texto), tecto))])
    paginas = []
    for i, j in janelas:
        for p in range(texto.count("\f", 0, i) + 1,
                       texto.count("\f", 0, j) + 2):
            if p not in paginas:
                paginas.append(p)
    return paginas


def rotulo_com_paginas(nome, paginas):
    """"CE.pdf" + [2,3,4,7] -> "CE.pdf (pág. 2–4, 7)".

    E o que vai para analise.fontes e dali para a ficha: diz de que
    paginas veio o recorte que sustentou a leitura. Sem paginas fica so
    o nome, como sempre foi."""
    if not paginas:
        return nome
    grupos, inicio, anterior = [], paginas[0], paginas[0]
    for p in paginas[1:]:
        if p == anterior + 1:
            anterior = p
            continue
        grupos.append((inicio, anterior))
        inicio = anterior = p
    grupos.append((inicio, anterior))
    pedacos = ["%d" % a if a == b else "%d–%d" % (a, b) for a, b in grupos]
    return "%s (pág. %s)" % (nome, ", ".join(pedacos))


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
            "SELECT nome, texto FROM documentos WHERE ref=? "
            "AND texto_estado IN ('ok','ocr') "
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
        limpo = sem_indice(d["texto"])
        partes.append("### %s\n%s" % (
            d["nome"],
            recorte_relevante(limpo, ancoras, tecto)))
        # A fonte leva as paginas do recorte (B12), quando o texto tem
        # as marcas; e por leitura, por isso o mesmo CE pode aparecer
        # nas fontes com paginas diferentes -- objecto e equipa leem
        # zonas diferentes, e e isso mesmo que se quer declarar.
        usados.append(rotulo_com_paginas(
            d["nome"], paginas_do_recorte(limpo, ancoras, tecto)))
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

    leituras = leituras_activas()      # as de origem, com o config por cima
    docs = documentos_com_texto(ref)
    recortes = [(nome, pecas_para_analise(docs, quais, ancoras), instrucao)
                for nome, quais, ancoras, instrucao in leituras]
    if not any(texto for _, (texto, _), _ in recortes):
        # As pecas trazidas antes de haver extracao de texto ficaram sem
        # ele. Estao em disco: extrai-se agora, sem voltar a rede.
        extrair_textos(ref)
        docs = documentos_com_texto(ref)
        recortes = [(nome, pecas_para_analise(docs, quais, ancoras), instrucao)
                    for nome, quais, ancoras, instrucao in leituras]
    if not any(texto for _, (texto, _), _ in recortes):
        with liga() as c:
            scans = c.execute("SELECT COUNT(*) n FROM documentos WHERE ref=? "
                              "AND texto_estado IN ('scan','imagem')",
                              (ref,)).fetchone()["n"]
        if scans and not ocr_instalado():
            return False, ("os documentos deste concurso são digitalizações, e "
                           "o OCR está por instalar (pip install rapidocr "
                           "onnxruntime)")
        return False, ("os documentos deste concurso são digitalizações em que "
                       "o OCR não encontrou texto" if scans else
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
            marca_erro("analise_ultimo_erro", "leitura", "%s · %s: %s"
                       % (datetime.now().strftime("%Y-%m-%d %H:%M"),
                          ref, porque))
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
                # A data vai na marca (C1 do saneamento) e a serie fica
                # na tabela erros (C3): a marca diz o ultimo, a serie
                # conta a historia.
                marca_erro("docs_ultimo_erro", "pecas", "%s · %s: %s"
                           % (datetime.now().strftime("%Y-%m-%d %H:%M"),
                              ref, aviso or "sem documentos"))
        except Exception as erro:
            # Tem de ficar num estado terminal: se ficasse "pendente", a
            # ficha esperava para sempre por peças que nunca vinham.
            try:
                with liga() as c:
                    c.execute("UPDATE anuncios SET docs_estado='falhou' WHERE ref=?",
                              (ref,))
                marca_erro("docs_ultimo_erro", "pecas", "%s · %s: %s"
                           % (datetime.now().strftime("%Y-%m-%d %H:%M"),
                              ref, str(erro)[:200]))
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


# A leitura pelo modelo, tambem em fila.
#
# Corria dentro do pedido, com o comentario a dizer "demora poucos
# segundos". Sao tres perguntas ao modelo e cada uma espera ate 70
# segundos quando bate no tecto por minuto -- o botao ficava pendurado
# minutos, sem sinal, ao lado do "Trazer peças" que ja tinha fila e ja
# dizia em que pe ia.
_FILA_ANALISE = queue.Queue()
_ANALISTA = None
_ANALISTA_LOCK = threading.Lock()
_A_ANALISAR = set()


def analise_a_correr(ref):
    return ref in _A_ANALISAR


def _servir_analise():
    while True:
        ref, quem = _FILA_ANALISE.get()
        try:
            ok, porque = analisar_pecas(ref)
            # "leitura", nao "análise": e o nome que o ecra usa (§7 do
            # ESQUELETO). Os registos antigos traduzem-se ao mostrar.
            registar(ref, "leitura",
                     "peças lidas" if (ok and not porque) else (porque or "falhou"),
                     quem=quem)
            if not ok:
                marca_erro("analise_ultimo_erro", "leitura", "%s · %s: %s"
                           % (datetime.now().strftime("%Y-%m-%d %H:%M"),
                              ref, porque))
        except Exception as erro:
            try:
                marca_erro("analise_ultimo_erro", "leitura", "%s · %s: %s"
                           % (datetime.now().strftime("%Y-%m-%d %H:%M"),
                              ref, str(erro)[:200]))
            except Exception:
                pass
        finally:
            _A_ANALISAR.discard(ref)
            _FILA_ANALISE.task_done()


def pedir_analise(ref, quem=""):
    """Poe a leitura na fila. Devolve False se ja la estiver."""
    global _ANALISTA
    with _ANALISTA_LOCK:
        if ref in _A_ANALISAR:
            return False
        _A_ANALISAR.add(ref)
        if _ANALISTA is None or not _ANALISTA.is_alive():
            _ANALISTA = threading.Thread(target=_servir_analise, daemon=True)
            _ANALISTA.start()
    _FILA_ANALISE.put((ref, quem))
    return True


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
                (ref,titulo,entidade,data_pub,tipo,url,estado,visto_em,
                 titulo_norm,entidade_norm)
                VALUES (?,?,?,?,?,?,'novo',?,simplifica(?),simplifica(?))""",
                            (a["ref"], a["titulo"], a["entidade"], a["data_pub"],
                             a.get("tipo", ""), a["url"], agora,
                             a["titulo"], a["entidade"]))
            novos += cur.rowcount
    return novos


# As tarefas que o agendar.bat cria. Se nao existirem, o radar so
# recolhe com o painel aberto -- e como o relogio interno recupera os
# slots falhados, a tabela `slots` fica preenchida e parece que correu a
# horas. Foi assim que isto passou semanas sem se notar.
TAREFAS = ("Radar DR 09h", "Radar DR 17h")
_TAREFAS_VISTAS = None
_TAREFAS_QUANDO = 0.0
# A resposta guarda-se durante um minuto e nao para sempre. Era para
# sempre: correr o agendar.bat com o painel aberto deixava o aviso
# vermelho no ecra ate se reiniciar o painel, e apagar uma tarefa nunca
# chegava a ser notado. E o aviso que impede o pior modo de falha desta
# aplicacao -- parecer viva sem estar a recolher nada -- e era o que
# menos se actualizava.
TAREFAS_VALIDADE = 60


def tarefas_em_falta():
    """Quais das tarefas do Windows nao estao criadas.

    A resposta guarda-se por um minuto: e um subprocesso, e o painel
    monta paginas muitas vezes. Fora do Windows devolve vazio -- nao ha
    o que avisar.
    """
    global _TAREFAS_VISTAS, _TAREFAS_QUANDO
    if (_TAREFAS_VISTAS is not None
            and time.time() - _TAREFAS_QUANDO < TAREFAS_VALIDADE):
        return _TAREFAS_VISTAS
    _TAREFAS_QUANDO = time.time()
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


def copia_com_marca(guardar=7):
    """A copia diaria, com o resultado numa marca que o painel mostra.

    A falha fazia so print() para uma consola que ninguem ve -- as
    tarefas correm em pythonw -- e uma copia a falhar dias seguidos
    (OneDrive a segurar o ficheiro, disco cheio) passava em silencio,
    exactamente no unico dado que nao se recupera de lado nenhum. A
    marca `ultima_copia` aparece na saude dos indicadores."""
    try:
        destino = copia_de_seguranca(guardar)
        marca("ultima_copia", "ok: %s" % os.path.basename(destino))
        return True
    except (sqlite3.Error, OSError) as erro:
        marca_erro("ultima_copia", "copia", "falhou a %s: %s"
                   % (datetime.now().strftime("%Y-%m-%d %H:%M"),
                      str(erro)[:150]))
        print("aviso: copia de seguranca falhou (%s)" % erro)
        return False


# ------------------------------------------- exportacao da triagem (B15)
#
# O remoto do git poe o CODIGO fora do PC; a triagem -- o unico dado
# declaradamente irrecuperavel -- vivia so no disco, porque a base esta
# no .gitignore. A saida e o tamanho: a parte irrecuperavel cabe num
# ficheiro de texto que viaja no repositorio, e cada push passa a ser
# uma copia da triagem fora do PC. O ficheiro leva as decisoes dele e o
# historico com o nome de quem agiu: repositorio privado, dados dele --
# mas fica dito, porque passa a estar fora do PC.

TRIAGEM_EXPORT = os.path.join(BASE_DIR, "triagem.jsonl")

# O que entra -- e nada mais: o resto refaz-se (os anuncios voltam do
# DR, o corpus do IMPIC, as pecas das plataformas). Cada entrada e
# (tabela, colunas, consulta com ordem deterministica): a ordem nao e
# estetica, e o que faz o git diff mostrar O QUE MUDOU HOJE em vez de
# um ficheiro inteiro reescrito. As fases, etiquetas e filtros levam o
# id porque outras linhas apontam para ele (fase_id, etiqueta_id,
# filtro_id).
_TABELAS_TRIAGEM = (
    ("anuncios", ("ref", "estado", "fase_id", "responsavel", "visto_em"),
     "SELECT ref, estado, fase_id, responsavel, visto_em FROM anuncios "
     "WHERE estado NOT IN ('novo', 'alteracao') OR fase_id IS NOT NULL "
     "OR COALESCE(responsavel,'') != '' ORDER BY ref"),
    ("fases", ("id", "nome", "ordem"),
     "SELECT id, nome, ordem FROM fases ORDER BY id"),
    ("etiquetas", ("id", "nome", "cor"),
     "SELECT id, nome, cor FROM etiquetas ORDER BY id"),
    ("anuncio_etiquetas", ("ref", "etiqueta_id"),
     "SELECT ref, etiqueta_id FROM anuncio_etiquetas "
     "ORDER BY ref, etiqueta_id"),
    ("historico", ("ref", "quem", "accao", "detalhe", "quando"),
     "SELECT ref, quem, accao, detalhe, quando FROM historico ORDER BY id"),
    ("filtros_guardados",
     ("id", "nome", "consulta", "alerta", "quem", "criado_em"),
     "SELECT id, nome, consulta, alerta, quem, criado_em "
     "FROM filtros_guardados ORDER BY id"),
    ("entidades_seguidas", ("chave", "nome", "desde"),
     "SELECT chave, nome, desde FROM entidades_seguidas ORDER BY chave"),
    # as marcas de ja-avisado: sem elas, o primeiro resumo depois de um
    # restauro trazia o acervo inteiro outra vez
    ("alertas_vistos", ("filtro_id", "ref", "visto_em", "enviado_em"),
     "SELECT filtro_id, ref, visto_em, enviado_em FROM alertas_vistos "
     "ORDER BY filtro_id, ref"),
    ("seguidas_vistos", ("chave", "ref", "visto_em", "enviado_em"),
     "SELECT chave, ref, visto_em, enviado_em FROM seguidas_vistos "
     "ORDER BY chave, ref"),
)


def exportar_triagem(caminho=None):
    """B15: a parte irrecuperavel da base num ficheiro de texto.

    Um registo por linha (JSON com chaves ordenadas), tabelas e linhas
    em ordem deterministica. Corre a seguir a copia diaria, dentro do
    verificar() -- sao milhares de linhas, custa nada, e assim esta
    sempre fresco. Sair do PC exige um push; por agora e manual
    (sub-decisao registada no BACKLOG: manual ou tarefa semanal).
    Devolve (n registos, caminho)."""
    caminho = caminho or TRIAGEM_EXPORT
    linhas = []
    with liga() as c:
        for tabela, colunas, sql in _TABELAS_TRIAGEM:
            for r in c.execute(sql):
                registo = {"tabela": tabela}
                registo.update({k: r[k] for k in colunas})
                linhas.append(json.dumps(registo, ensure_ascii=False,
                                         sort_keys=True))
    # escrita por ficheiro temporario + os.replace: um export
    # interrompido a meio nao pode deixar meio ficheiro a fazer de copia
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
    os.replace(tmp, caminho)
    return len(linhas), caminho


def porque_do_git(feito, tecto=150):
    """A razao de um comando git falhado, sem o cabecalho a tapa-la.

    Um push recusado escreve "To <url>" na primeira linha e a razao so
    na segunda, e o "error: failed to push some refs" na terceira nao
    acrescenta nada. Com os 80 caracteres da linha dos indicadores, o
    endereco do repositorio comia a mensagem inteira: lia-se
    "git push: To https://github.com/..." e ficava-se sem saber porque
    e que falhou -- que era o unico ponto de a gravar. Tira-se a linha
    do endereco e o "error:" final, e junta-se o resto numa linha so,
    que e como isto vai ser mostrado.
    """
    saida = (feito.stderr or feito.stdout or b"")
    if isinstance(saida, bytes):
        saida = saida.decode("utf-8", "ignore")
    linhas = [l.strip() for l in saida.splitlines() if l.strip()]
    uteis = [l for l in linhas
             if not l.startswith("To ") and not l.startswith("error: failed")]
    return " ".join(uteis or linhas)[:tecto]


def empurrar_triagem(pasta=None):
    """B15, sub-decisao fechada a 31/08/2026 pelo Afonso: automatico,
    "grava logo la consoante o uso". Depois do export, se o
    triagem.jsonl mudou face ao que o git tem, faz commit SO desse
    ficheiro (mensagem padronizada) e push.

    O push falhado NAO se perde: o commit local fica, e a proxima
    verificacao ve os commits a frente do origin e volta a empurrar --
    um diff limpo sozinho nao chega para dizer "esta la fora".
    Qualquer falha (sem git, sem rede) vai para a serie de erros e
    espera pela proxima volta; a exportacao em si ja esta no disco.
    Desliga-se com "triagem_no_git": false no config.json.
    Devolve (correu bem, o que aconteceu)."""
    pasta = pasta or BASE_DIR
    # sem janela de consola: as tarefas correm em pythonw
    quieto = {"cwd": pasta, "capture_output": True,
              "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}

    def corre(args, timeout):
        return subprocess.run(args, timeout=timeout, **quieto)

    try:
        mudou = corre(["git", "diff", "--quiet", "HEAD", "--",
                       "triagem.jsonl"], 30).returncode != 0
        if mudou:
            feito = corre(["git", "commit", "-m", "triagem: " +
                           datetime.now().strftime("%Y-%m-%d %H:%M"),
                           "--", "triagem.jsonl"], 60)
            if feito.returncode != 0:
                raise RuntimeError("git commit: %s" % porque_do_git(feito))
        a_frente = corre(["git", "rev-list", "--count",
                          "origin/master..master"], 30)
        if a_frente.returncode != 0:
            raise RuntimeError("git rev-list: %s" % porque_do_git(a_frente))
        if int(a_frente.stdout.strip() or 0) == 0:
            return True, "sem mudanças por empurrar"
        feito = corre(["git", "push", "origin", "master"], 180)
        if feito.returncode != 0:
            raise RuntimeError("git push: %s" % porque_do_git(feito))
        return True, "triagem empurrada para o remoto"
    except (OSError, ValueError, RuntimeError,
            subprocess.TimeoutExpired) as erro:
        marca_erro("ultimo_erro_triagem_git", "triagem-git",
                   "%s: %s" % (datetime.now().strftime("%Y-%m-%d %H:%M"),
                               str(erro)[:200]))
        return False, str(erro)[:200]


def repor_triagem(caminho=None):
    """B15: repoe a triagem exportada numa base ja refeita pela recolha.

    Idempotente -- correr duas vezes nao duplica nada. O ficheiro
    guarda decisoes, nao anuncios: um ref que ainda nao exista na base
    NAO se inventa, fica no relatorio final para se saber o que ficou
    por repor (sem isto o restauro parecia completo e nao era; os
    anuncios em falta voltam do DR e repoe-se outra vez).
    Devolve (n escritas, {tabela: [refs por repor]})."""
    caminho = caminho or TRIAGEM_EXPORT
    if not os.path.exists(caminho):
        return 0, {"ficheiro": [caminho + " não existe"]}
    registos = []
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if linha:
                registos.append(json.loads(linha))
    iniciar_db()
    escritas = 0
    por_repor = {}
    with liga() as c:
        existe = {r["ref"] for r in c.execute("SELECT ref FROM anuncios")}
        for reg in registos:
            t = reg.get("tabela")
            if t == "anuncios":
                if reg["ref"] not in existe:
                    por_repor.setdefault(t, []).append(reg["ref"])
                    continue
                c.execute("UPDATE anuncios SET estado=?, fase_id=?, "
                          "responsavel=?, visto_em=? WHERE ref=?",
                          (reg["estado"], reg["fase_id"],
                           reg["responsavel"], reg["visto_em"],
                           reg["ref"]))
                escritas += 1
            elif t == "fases":
                c.execute("INSERT OR REPLACE INTO fases (id, nome, ordem) "
                          "VALUES (?,?,?)",
                          (reg["id"], reg["nome"], reg["ordem"]))
                escritas += 1
            elif t == "etiquetas":
                c.execute("INSERT OR REPLACE INTO etiquetas (id, nome, cor) "
                          "VALUES (?,?,?)",
                          (reg["id"], reg["nome"], reg["cor"]))
                escritas += 1
            elif t == "anuncio_etiquetas":
                if reg["ref"] not in existe:
                    por_repor.setdefault(t, []).append(reg["ref"])
                    continue
                c.execute("INSERT OR REPLACE INTO anuncio_etiquetas "
                          "(ref, etiqueta_id) VALUES (?,?)",
                          (reg["ref"], reg["etiqueta_id"]))
                escritas += 1
            elif t == "historico":
                # o historico nao tem chave natural na tabela: a
                # idempotencia e por igualdade da linha inteira
                ja = c.execute(
                    "SELECT 1 FROM historico WHERE ref=? AND quem=? AND "
                    "accao=? AND COALESCE(detalhe,'')=? AND quando=?",
                    (reg["ref"], reg["quem"], reg["accao"],
                     reg["detalhe"] or "", reg["quando"])).fetchone()
                if not ja:
                    c.execute("INSERT INTO historico "
                              "(ref, quem, accao, detalhe, quando) "
                              "VALUES (?,?,?,?,?)",
                              (reg["ref"], reg["quem"], reg["accao"],
                               reg["detalhe"], reg["quando"]))
                    escritas += 1
            elif t == "filtros_guardados":
                c.execute("INSERT OR REPLACE INTO filtros_guardados "
                          "(id, nome, consulta, alerta, quem, criado_em) "
                          "VALUES (?,?,?,?,?,?)",
                          (reg["id"], reg["nome"], reg["consulta"],
                           reg["alerta"], reg["quem"], reg["criado_em"]))
                escritas += 1
            elif t == "entidades_seguidas":
                c.execute("INSERT OR REPLACE INTO entidades_seguidas "
                          "(chave, nome, desde) VALUES (?,?,?)",
                          (reg["chave"], reg["nome"], reg["desde"]))
                escritas += 1
            elif t == "alertas_vistos":
                c.execute("INSERT OR REPLACE INTO alertas_vistos "
                          "(filtro_id, ref, visto_em, enviado_em) "
                          "VALUES (?,?,?,?)",
                          (reg["filtro_id"], reg["ref"], reg["visto_em"],
                           reg["enviado_em"]))
                escritas += 1
            elif t == "seguidas_vistos":
                c.execute("INSERT OR REPLACE INTO seguidas_vistos "
                          "(chave, ref, visto_em, enviado_em) "
                          "VALUES (?,?,?,?)",
                          (reg["chave"], reg["ref"], reg["visto_em"],
                           reg["enviado_em"]))
                escritas += 1
    return escritas, por_repor


# Marca posta no que ja estava na base quando o alerta foi ligado: nao
# foi avisado, mas tambem nao e novidade -- senao o primeiro resumo
# trazia o acervo todo.
ACERVO = "acervo"


def filtros_de_alerta():
    with liga() as c:
        return c.execute(
            "SELECT id, nome, consulta FROM filtros_guardados "
            "WHERE alerta=1 ORDER BY nome COLLATE NOCASE").fetchall()


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
        # So a parte que os anuncios entendem. Passar o filtro inteiro a
        # condicoes() deixava os campos de contratos cairem em silencio,
        # e um alerta "CPV 72 + ganho por MEO" passava a avisar de todos
        # os anuncios de CPV 72. O separador marca esses filtros.
        aplicavel, fora = filtro_para(f["consulta"] or "", "anuncios")
        args = dict(parse_qsl(aplicavel, keep_blank_values=True))
        # o estado nao entra: procuram-se anuncios que correspondem, e a
        # triagem deles e outra conversa
        args.pop("estado", None)
        if not args:
            continue                    # nada aqui e sobre anuncios
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
                "AND a.estado != 'alteracao' "
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


def registar_seguidas(marcar_como=None, so_chave=None):
    """Anota que anuncios novos sao das entidades seguidas (B10).

    O mesmo reconhecer/enviar dos alertas. O casamento e pelo NIPC
    (`anuncios.nif` = chave), que o DR publica em 99,3% dos anuncios com
    detalhe lido -- e a mesma chave do corpus, sem comparacao de nomes
    pelo meio. Chaves "n:" (entidades sem NIF) nao casam com anuncios:
    a ficha delas continua a mostrar os contratos, mas nao ha aviso.

    `marcar_como` serve o momento de comecar a seguir: o que ja esta na
    base entra como ACERVO, senao o primeiro resumo trazia tudo. O
    `so_chave` limita a passagem a essa entidade -- e o que impede o
    ACERVO de uma engolir as novidades por enviar das outras.
    """
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    novos = 0
    with liga() as c:
        if so_chave:
            seguidas = c.execute("SELECT chave FROM entidades_seguidas "
                                 "WHERE chave=?", (so_chave,)).fetchall()
        else:
            seguidas = c.execute("SELECT chave FROM entidades_seguidas").fetchall()
        for s in seguidas:
            if s["chave"].startswith("n:"):
                continue
            refs = [r["ref"] for r in c.execute(
                "SELECT ref FROM anuncios WHERE nif=? AND ref NOT IN "
                "(SELECT ref FROM seguidas_vistos WHERE chave=?)",
                (s["chave"], s["chave"]))]
            c.executemany(
                "INSERT OR IGNORE INTO seguidas_vistos "
                "(chave, ref, visto_em, enviado_em) VALUES (?,?,?,?)",
                [(s["chave"], r, agora, marcar_como) for r in refs])
            novos += len(refs)
    return novos


def seguidas_por_avisar():
    """[(chave, nome, [anuncios])] do que as seguidas publicaram e ainda
    nao foi avisado."""
    fora = []
    with liga() as c:
        for s in c.execute("SELECT chave, nome FROM entidades_seguidas "
                           "ORDER BY nome COLLATE NOCASE"):
            linhas = c.execute(
                "SELECT a.ref, a.titulo, a.entidade, a.data_pub, a.prazo, "
                "a.preco_base FROM seguidas_vistos v "
                "JOIN anuncios a ON a.ref = v.ref "
                "WHERE v.chave=? AND v.enviado_em IS NULL "
                "ORDER BY a.data_pub DESC", (s["chave"],)).fetchall()
            if linhas:
                fora.append((s["chave"], s["nome"], linhas))
    return fora


def marcar_seguidas_enviadas(seguidas):
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    with liga() as c:
        for chave, _, linhas in seguidas:
            c.executemany(
                "UPDATE seguidas_vistos SET enviado_em=? "
                "WHERE chave=? AND ref=?",
                [(agora, chave, a["ref"]) for a in linhas])


def alteracoes_por_avisar():
    """As alteracoes detectadas e ainda nao avisadas, com o anuncio ao
    lado para o resumo ter o que dizer."""
    with liga() as c:
        return c.execute(
            "SELECT t.id, t.ref, t.campo, t.antes, t.depois, "
            "a.titulo, a.entidade FROM alteracoes t "
            "JOIN anuncios a ON a.ref = t.ref "
            "WHERE t.avisado_em IS NULL ORDER BY t.ref, t.id").fetchall()


def marcar_alteracoes_avisadas(alteradas):
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    with liga() as c:
        c.executemany("UPDATE alteracoes SET avisado_em=? WHERE id=?",
                      [(agora, x["id"]) for x in alteradas])


def texto_do_resumo(achados, alteradas=(), seguidas=()):
    """O resumo em texto simples, que serve de corpo do e-mail e de
    AVISOS.txt. Um so formato: dois divergiam ao primeiro arranjo.

    As `alteradas` sao as linhas de alteracoes_por_avisar(): anuncios ja
    conhecidos a que o DR mudou o prazo ou o preco base (B05). As
    `seguidas` vem de seguidas_por_avisar(): o que as entidades seguidas
    publicaram (B10). Cada grupo vai na sua seccao -- sao perguntas
    diferentes.
    """
    total = sum(len(x[1]) for x in achados)
    n_alt = len({x["ref"] for x in alteradas})
    n_seg = sum(len(x[2]) for x in seguidas)
    cabeca = []
    if total or not (n_alt or n_seg):
        cabeca.append("%d anuncio%s novo%s nos teus alertas"
                      % (total, "" if total == 1 else "s",
                         "" if total == 1 else "s"))
    if n_alt:
        cabeca.append("%d alterado%s" % (n_alt, "" if n_alt == 1 else "s"))
    if n_seg:
        cabeca.append("%d das entidades seguidas" % n_seg)
    linhas = ["Radar de Concursos -- " + " · ".join(cabeca),
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
    if alteradas:
        rotulos = dict(CAMPOS_VIGIADOS)
        por_ref = {}
        for x in alteradas:
            por_ref.setdefault(x["ref"], []).append(x)
        linhas.append("== Alterados desde a última leitura (%d)" % len(por_ref))
        linhas.append("")
        for ref, mudancas in por_ref.items():
            primeiro = mudancas[0]
            linhas.append("  %s" % (primeiro["titulo"] or "(sem titulo)")[:88])
            linhas.append("    %s" % (primeiro["entidade"] or "")[:80])
            for x in mudancas:
                if x["campo"] == "retificacao":
                    linhas.append("    rectificado pelo anúncio %s"
                                  % x["depois"])
                else:
                    linhas.append("    %s: %s -> %s"
                                  % (rotulos.get(x["campo"], x["campo"]),
                                     _valor_vigiado(x["campo"], x["antes"]),
                                     _valor_vigiado(x["campo"], x["depois"])))
            linhas.append("    http://localhost:%d/anuncio/%s"
                          % (PORTA, quote(ref, safe="")))
            linhas.append("")
    if seguidas:
        linhas.append("== Das entidades que segues (%d)"
                      % sum(len(x[2]) for x in seguidas))
        linhas.append("")
        for _, nome, anuncios in seguidas:
            linhas.append("  %s (%d)" % ((nome or "")[:80], len(anuncios)))
            for a in anuncios:
                linhas.append("    %s" % (a["titulo"] or "(sem titulo)")[:84])
                linhas.append("    publicado %s | %s"
                              % (data_pt(a["data_pub"]),
                                 a["preco_base"] or "sem preco base"))
                linhas.append("    http://localhost:%d/anuncio/%s"
                              % (PORTA, quote(a["ref"], safe="")))
            linhas.append("")
    return "\n".join(linhas)


# O e-mail "bonito" (02/09/2026): o mesmo resumo em HTML, ao lado do
# texto. Tudo em estilos em linha e em tabelas, que e o que os clientes
# de e-mail percebem -- nem <style>, nem fontes externas, nem flex. As
# cores sao as da paleta "ardosia e ambar" do painel, copiadas a mao
# porque um e-mail nao le o CSS da aplicacao.
_EM_INK = "#14181e"
_EM_PAPEL = "#eef1f4"
_EM_LINHA = "#dbe0e6"
_EM_T2 = "#333c46"
_EM_T3 = "#4d5661"
_EM_AZUL = "#17557f"
_EM_SANS = "Archivo,system-ui,-apple-system,'Segoe UI',Arial,sans-serif"
_EM_MONO = "'JetBrains Mono',Consolas,Menlo,monospace"
_EM_CORES = {"ok": ("#e7f3ec", "#1a7a4d"),
             "avisa": ("#fbeee2", "#a8450e"),
             "mau": ("#fbe9e5", "#b0341a"),
             "": ("#eceff2", "#4d5661")}


def _em_pilula(texto, classe=""):
    fundo, cor = _EM_CORES.get(classe, _EM_CORES[""])
    return ("<span style=\"display:inline-block;padding:2px 8px;"
            "border-radius:10px;background:%s;color:%s;font:600 11.5px/1.5 %s;"
            "white-space:nowrap\">%s</span>"
            % (fundo, cor, _EM_SANS, html.escape(texto)))


def _em_ligacao(ref):
    return "http://localhost:%d/anuncio/%s" % (PORTA, quote(ref, safe=""))


def _em_prazo(prazo, urgente):
    """[(texto, classe)] para a linha do prazo: a data e a pilula."""
    dias, passou = dias_restantes(prazo)
    if dias is None:
        return "", _em_pilula("sem prazo lido")
    if passou:
        return ("propostas até %s" % data_pt(prazo),
                _em_pilula("prazo expirado", "mau"))
    texto, classe = etiqueta_prazo(prazo, urgente)
    return "propostas até %s" % data_pt(prazo), _em_pilula(texto, classe)


def _em_cartao(a, urgente, mostrar_prazo=True):
    """Um anuncio: titulo com a ligacao, entidade, e a linha do ref,
    prazo e preco base. O titulo vai inteiro -- no texto corta-se aos
    88 caracteres e "(SaaS" a meio era a primeira coisa que se via."""
    titulo = html.escape(a["titulo"] or "(sem título)")
    entidade = html.escape(a["entidade"] or "")
    preco = html.escape(a["preco_base"] or "sem preço base")
    metas = ["<span style=\"font:500 12px/1.5 %s;color:%s\">%s</span>"
             % (_EM_MONO, _EM_T3, html.escape(a["ref"]))]
    if mostrar_prazo:
        data, pilula = _em_prazo(a["prazo"], urgente)
        if data:
            metas.append(html.escape(data))
        metas.append(pilula)
    else:
        metas.append("publicado %s" % html.escape(data_pt(a["data_pub"])))
    metas.append("<b style=\"color:%s\">%s</b>" % (_EM_T2, preco))
    sep = "<span style=\"color:#b9c1cb;padding:0 7px\">·</span>"
    return ("<tr><td style=\"padding:12px 16px;border-top:1px solid %s\">"
            "<a href=\"%s\" style=\"font:600 14.5px/1.35 %s;color:%s;"
            "text-decoration:none\">%s</a>"
            "<div style=\"font:400 12.5px/1.45 %s;color:%s;margin-top:2px\">%s</div>"
            "<div style=\"font:400 12.5px/1.9 %s;color:%s;margin-top:4px\">%s</div>"
            "</td></tr>"
            % (_EM_LINHA, _em_ligacao(a["ref"]), _EM_SANS, _EM_INK, titulo,
               _EM_SANS, _EM_T3, entidade,
               _EM_SANS, _EM_T3, sep.join(metas)))


def _em_seccao(rotulo, n, linhas):
    """Um bloco branco com o cabecalho da seccao em cima."""
    return ("<table role=\"presentation\" width=\"100%%\" cellpadding=\"0\" "
            "cellspacing=\"0\" style=\"background:#fff;border:1px solid %s;"
            "border-radius:8px;margin:0 0 16px;border-collapse:separate\">"
            "<tr><td style=\"padding:11px 16px 9px;font:700 11px/1.4 %s;"
            "color:%s;text-transform:uppercase;letter-spacing:.06em\">%s "
            "<span style=\"color:%s;font-weight:500\">(%d)</span></td></tr>"
            "%s</table>"
            % (_EM_LINHA, _EM_SANS, _EM_T2, html.escape(rotulo), _EM_T3, n,
               "".join(linhas)))


def html_do_resumo(achados, alteradas=(), seguidas=()):
    """O mesmo resumo de texto_do_resumo(), em HTML, para o e-mail ir
    com as duas partes (o texto continua a ser o AVISOS.txt e a
    alternativa para quem nao le HTML). As seccoes e as contagens sao
    as mesmas, de proposito: um teste compara os dois."""
    total = sum(len(x[1]) for x in achados)
    n_alt = len({x["ref"] for x in alteradas})
    n_seg = sum(len(x[2]) for x in seguidas)
    urgente = dias_urgente()
    cabeca = []
    if total or not (n_alt or n_seg):
        cabeca.append("%d anúncio%s novo%s nos teus alertas"
                      % (total, "" if total == 1 else "s",
                         "" if total == 1 else "s"))
    if n_alt:
        cabeca.append("%d alterado%s" % (n_alt, "" if n_alt == 1 else "s"))
    if n_seg:
        cabeca.append("%d das entidades seguidas" % n_seg)

    blocos = []
    for f, anuncios in achados:
        blocos.append(_em_seccao(f["nome"], len(anuncios),
                                 [_em_cartao(a, urgente) for a in anuncios]))
    if alteradas:
        rotulos = dict(CAMPOS_VIGIADOS)
        por_ref = {}
        for x in alteradas:
            por_ref.setdefault(x["ref"], []).append(x)
        linhas = []
        for ref, mudancas in por_ref.items():
            primeiro = mudancas[0]
            itens = []
            for x in mudancas:
                if x["campo"] == "retificacao":
                    itens.append("rectificado pelo anúncio <b>%s</b>"
                                 % html.escape(x["depois"]))
                else:
                    itens.append(
                        "%s: <s style=\"color:%s\">%s</s> &rarr; <b>%s</b>"
                        % (html.escape(rotulos.get(x["campo"], x["campo"])),
                           _EM_T3,
                           html.escape(_valor_vigiado(x["campo"], x["antes"])),
                           html.escape(_valor_vigiado(x["campo"], x["depois"]))))
            linhas.append(
                "<tr><td style=\"padding:12px 16px;border-top:1px solid %s\">"
                "<a href=\"%s\" style=\"font:600 14.5px/1.35 %s;color:%s;"
                "text-decoration:none\">%s</a>"
                "<div style=\"font:400 12.5px/1.45 %s;color:%s;margin-top:2px\">%s</div>"
                "<div style=\"font:400 12.5px/1.7 %s;color:%s;margin-top:4px\">%s</div>"
                "</td></tr>"
                % (_EM_LINHA, _em_ligacao(ref), _EM_SANS, _EM_INK,
                   html.escape(primeiro["titulo"] or "(sem título)"),
                   _EM_SANS, _EM_T3, html.escape(primeiro["entidade"] or ""),
                   _EM_SANS, _EM_T2, "<br>".join(itens)))
        blocos.append(_em_seccao("Alterados desde a última leitura",
                                 len(por_ref), linhas))
    if seguidas:
        linhas = []
        for _, nome, anuncios in seguidas:
            linhas.append(
                "<tr><td style=\"padding:10px 16px 2px;border-top:1px solid %s;"
                "font:600 12.5px/1.4 %s;color:%s\">%s "
                "<span style=\"color:%s;font-weight:500\">(%d)</span></td></tr>"
                % (_EM_LINHA, _EM_SANS, _EM_T2, html.escape(nome or ""),
                   _EM_T3, len(anuncios)))
            linhas.extend(_em_cartao(a, urgente, mostrar_prazo=False)
                          for a in anuncios)
        blocos.append(_em_seccao("Das entidades que segues", n_seg, linhas))

    return (
        "<!DOCTYPE html><html lang=\"pt\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width\">"
        "<title>Radar de Concursos</title></head>"
        "<body style=\"margin:0;padding:0;background:%(papel)s\">"
        "<table role=\"presentation\" width=\"100%%\" cellpadding=\"0\" "
        "cellspacing=\"0\" style=\"background:%(papel)s\"><tr><td align=\"center\" "
        "style=\"padding:24px 12px\">"
        "<table role=\"presentation\" width=\"100%%\" cellpadding=\"0\" "
        "cellspacing=\"0\" style=\"max-width:640px\">"
        "<tr><td style=\"background:%(ink)s;border-radius:8px 8px 0 0;"
        "padding:18px 20px 16px\">"
        "<div style=\"font:700 12px/1 %(sans)s;color:rgba(255,255,255,.7);"
        "text-transform:uppercase;letter-spacing:.08em\">"
        "<span style=\"color:#e08b2c\">&#9679;</span>&nbsp; Radar de Concursos</div>"
        "<div style=\"font:600 18px/1.3 %(sans)s;color:#fff;margin-top:8px\">%(cabeca)s</div>"
        "<div style=\"font:400 12px/1.4 %(sans)s;color:rgba(255,255,255,.55);"
        "margin-top:4px\">%(quando)s</div>"
        "</td></tr>"
        "<tr><td style=\"padding:16px 0 0\">%(blocos)s</td></tr>"
        "<tr><td style=\"padding:4px 4px 0;font:400 11.5px/1.5 %(sans)s;"
        "color:%(t3)s\">As ligações abrem no PC onde o radar corre. "
        "O mesmo resumo fica em <span style=\"font-family:%(mono)s\">AVISOS.txt</span>."
        "</td></tr>"
        "</table></td></tr></table></body></html>"
        % {"papel": _EM_PAPEL, "ink": _EM_INK, "sans": _EM_SANS,
           "mono": _EM_MONO, "t3": _EM_T3,
           "cabeca": html.escape(" · ".join(cabeca)),
           "quando": datetime.now().strftime("%d/%m/%Y %H:%M"),
           "blocos": "".join(blocos)})


def enviar_email(assunto, corpo, cfg=None, html_corpo=None):
    """Manda o resumo. Devolve (correu bem, o que dizer ao utilizador).

    A palavra-passe le-se de `email_senha.txt` ou da variavel
    RADAR_EMAIL_SENHA -- nunca fica na configuracao, que e um ficheiro
    que se abre sem pensar. O `.gitignore` ja cobre o nome.

    Com `html_corpo`, a mensagem vai em duas partes (multipart/
    alternative): o texto e a primeira, o HTML a segunda, e o cliente
    mostra a que souber. O texto fica sempre -- e o AVISOS.txt e o que
    se le num cliente sem HTML.
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
    if html_corpo:
        msg.add_alternative(html_corpo, subtype="html")
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
    alteradas = alteracoes_por_avisar()
    seguidas = seguidas_por_avisar()
    if not achados and not alteradas and not seguidas:
        return False, "nada de novo para avisar"

    corpo = texto_do_resumo(achados, alteradas, seguidas)
    with open(AVISOS, "w", encoding="utf-8") as f:
        f.write(corpo)                  # fica sempre, mesmo sem e-mail

    total = sum(len(x[1]) for x in achados)
    n_alt = len({x["ref"] for x in alteradas})
    n_seg = sum(len(x[2]) for x in seguidas)
    pedacos = []
    if total:
        pedacos.append("%d anúncio%s nos teus alertas"
                       % (total, "" if total == 1 else "s"))
    if n_alt:
        pedacos.append("%d alterado%s" % (n_alt, "" if n_alt == 1 else "s"))
    if n_seg:
        pedacos.append("%d das seguidas" % n_seg)
    bem, porque = enviar_email("Radar: " + " · ".join(pedacos), corpo, cfg,
                               html_do_resumo(achados, alteradas, seguidas))

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
        marcar_alteracoes_avisadas(alteradas)
        marcar_seguidas_enviadas(seguidas)
        marca("ultimo_resumo", hoje)
    marca("ultimo_resumo_estado",
          porque if bem else
          ("só no AVISOS.txt (%s)" % porque) if sem_canal else
          "por enviar (%s)" % porque)
    marca("ultimo_resumo_quantos", str(total))
    return entregue, porque


AVISOS = os.path.join(BASE_DIR, "AVISOS.txt")


def verificar(cfg=None, passo=None):
    """O trabalho da verificacao. O `passo` e um sinal de vida opcional:
    quem corre isto numa thread passa uma funcao que diz ao ecra em que
    fase vai. Na linha de comandos nao se passa nada e nada muda."""
    diz = passo or (lambda _: None)
    cfg = cfg or ler_config()
    iniciar_db()
    # Antes de mexer na base, nao depois: se a recolha a deixar num
    # estado mau, a copia e de antes disso.
    if cfg.get("copia_de_seguranca", True):
        diz("a guardar a cópia de segurança")
        # O resultado fica em marca visivel (C2 do saneamento): o print
        # de antes ia para uma consola que o pythonw nao tem.
        copia_com_marca(int(cfg.get("copias_a_guardar", 7)))
    # B15: a exportacao da triagem, a seguir a copia -- custa nada e
    # fica sempre fresca no triagem.jsonl. Uma falha aqui nao pode
    # travar a recolha. O commit+push automatico e a sub-decisao do
    # Afonso (31/08/2026: "grava logo la consoante o uso").
    try:
        exportar_triagem()
        if cfg.get("triagem_no_git", True):
            diz("a empurrar a triagem para o remoto")
            empurrar_triagem()
    except (sqlite3.Error, OSError) as erro:
        marca_erro("ultima_exportacao_triagem", "exportacao",
                   "%s: %s" % (datetime.now().strftime("%Y-%m-%d %H:%M"),
                               str(erro)[:150]))
    diz("a pedir os anúncios ao Diário da República")
    bem, mensagem, novos = recolher(cfg)
    if bem:
        diz("a ler o detalhe dos anúncios novos")
        feitos, aviso = ler_detalhes(int(cfg.get("detalhes_por_volta", 40)),
                                     dias=int(cfg.get("detalhe_dias", 60)) or None)
        if aviso:
            bem = False
            mensagem += " (%s)" % aviso
    if bem:
        # So depois dos novos: se a captura expirou, ja se soube acima e
        # nao vale a pena bater outra vez na mesma porta.
        diz("a reler os anúncios marcados, à procura de alterações")
        try:
            reler_marcados(int(cfg.get("relidos_por_volta", 25)))
            # As rectificacoes chegam como anuncios novos: liga-as ao
            # original pelo titulo. Barato (so titulos) e idempotente.
            ligar_retificacoes()
        except (sqlite3.Error, OSError) as erro:
            print("aviso: a releitura dos marcados falhou (%s)" % erro)
    # B14: a segunda fonte, ANTES dos alertas -- as consultas
    # preliminares tambem contam para eles. Falha isolada: a Vortal em
    # baixo nao estraga a verificacao do DR.
    if cfg.get("vortal_preliminares", True):
        diz("a ver as consultas preliminares na Vortal")
        try:
            n_vortal, aviso_v = recolher_vortal()
            if aviso_v:
                marca_erro("vortal_ultimo_erro", "vortal", "%s: %s"
                           % (datetime.now().strftime("%Y-%m-%d %H:%M"),
                              aviso_v))
            if n_vortal:
                mensagem += (" &middot; %d consulta%s preliminar%s da "
                             "Vortal" % (n_vortal,
                                         "" if n_vortal == 1 else "s",
                                         "" if n_vortal == 1 else "es"))
        except Exception as erro:
            marca_erro("vortal_ultimo_erro", "vortal", "%s: %s"
                       % (datetime.now().strftime("%Y-%m-%d %H:%M"),
                          str(erro)[:150]))
    # Os avisos correm depois de ler os detalhes: um filtro por CPV so
    # apanha o anuncio depois de o CPV estar lido, e ler os detalhes e a
    # ultima coisa que a verificacao faz.
    quantos_avisos = 0
    if bem and cfg.get("alertas", True):
        diz("a passar os alertas pelos anúncios novos")
        try:
            quantos_avisos = registar_alertas()
            registar_seguidas()
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
    # Como na liga(): e com ela que a migracao enche objecto_norm.
    c.create_function("simplifica", 1, simplifica)
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
        #
        # Enche-se uma vez, por marca, como o _desescapar_html(). Sem a
        # marca isto era o arranque todo: o "WHERE n_adj IS NULL" e a
        # unica das quatro migracoes desta funcao sem indice que a sirva,
        # e varria os 1,6 GB do corpus a cada arranque para nao encontrar
        # linha nenhuma. Medido a 01/09/2026, na pen: 38,9 s a frio
        # (0,8 s a quente, que e o que escondia isto), contra 0,00 s das
        # outras tres. O importador ja enche a coluna -- esta no
        # COLS_CONTRATO, com max(1, len(ganhadores)) -- portanto isto so
        # serve o corpus que veio de antes dela.
        cols = [r["name"] for r in c.execute("PRAGMA table_info(contratos)")]
        if "n_adj" not in cols:
            c.execute("ALTER TABLE contratos ADD COLUMN n_adj INTEGER")
        if not c.execute("SELECT 1 FROM corpus_estado "
                         "WHERE chave='n_adj_cheio'").fetchone():
            c.execute("""UPDATE contratos SET n_adj =
                         MAX(1, (SELECT COUNT(*) FROM contrato_adjudicatario a
                                 WHERE a.contrato_id = contratos.id))
                         WHERE n_adj IS NULL""")
            c.execute("INSERT OR REPLACE INTO corpus_estado VALUES "
                      "('n_adj_cheio', ?)",
                      (datetime.now().strftime("%Y-%m-%d %H:%M"),))
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
        # Saneamento 30/08/2026 (A3): indices de um esquema antigo que o
        # codigo actual nao cria -- os unicos ux_cpv/ux_adj comecam por
        # contrato_id e cobrem os mesmos acessos. Num corpus refeito de
        # raiz nao existiam; apagar poe o corpus existente igual ao que
        # o codigo produz, e poupa a manutencao deles na importacao.
        c.execute("DROP INDEX IF EXISTS ix_cpv_c")
        c.execute("DROP INDEX IF EXISTS ix_adj_c")
        for ddl in (
            "CREATE INDEX IF NOT EXISTS ix_ctr_chave "
            "ON contratos(adjudicante_chave)",
            "CREATE INDEX IF NOT EXISTS ix_adj_chave "
            "ON contrato_adjudicatario(chave)",
        ):
            c.execute(ddl)
        # Corpus que veio de antes do desescape: o dump do IMPIC chega
        # escapado para HTML e 5 998 entidades chamavam-se "&amp;" no
        # ecra e nao se encontravam na pesquisa. Corre uma vez, por
        # marca; o importador ja desescapa a entrada.
        _desescapar_html(c)
        # Corpus que veio de antes das chaves: enche-se o que falta e
        # resolvem-se os nomes. Idempotente -- so corre quando ha buracos.
        falta = c.execute("SELECT 1 FROM contratos "
                          "WHERE adjudicante_chave IS NULL LIMIT 1").fetchone()
        vazia = not c.execute("SELECT 1 FROM entidades LIMIT 1").fetchone()
        tem = c.execute("SELECT 1 FROM contratos LIMIT 1").fetchone()
        if falta or (vazia and tem):
            _preencher_chaves(c)
            resolver_entidades(c)
        # A pesquisa por objecto precisa da coluna normalizada, como os
        # anuncios: o LIKE nao baixa o "Ç" e o IMPIC escreve muitos
        # objectos em maiusculas -- 11,8% de cada pesquisa perdidos.
        # Vem DEPOIS do desescape, para normalizar o texto ja limpo.
        if "objecto_norm" not in cols:
            c.execute("ALTER TABLE contratos ADD COLUMN objecto_norm TEXT")
        c.execute("UPDATE contratos SET objecto_norm = simplifica(objecto) "
                  "WHERE objecto_norm IS NULL")
        # O indice nao e para saltar linhas (um LIKE '%...%' nunca salta):
        # e para varrer so a coluna em vez de desserializar a linha
        # inteira, como o ix_anuncios_titulo_norm.
        c.execute("CREATE INDEX IF NOT EXISTS ix_ctr_objecto_norm "
                  "ON contratos(objecto_norm)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_adj_nome_norm "
                  "ON contrato_adjudicatario(nome_norm)")
        # O fim estimado do contrato (celebracao + prazo em dias), em
        # coluna e nao em expressao: e por ele que a vista das renovacoes
        # ordena e filtra, e calcular a data em cada linha de 1,36
        # milhoes a cada pedido nao e ordem que um indice sirva. O
        # importador ja o traz (fim_estimado()); isto enche o corpus que
        # veio de antes. O date() do SQLite devolve NULL para os prazos
        # absurdos do dump (ha um de 365 milhoes de dias): fica "".
        if "fim_estimado" not in cols:
            c.execute("ALTER TABLE contratos ADD COLUMN fim_estimado TEXT")
        c.execute("""UPDATE contratos SET fim_estimado = CASE
                     WHEN data_celebracao != '' AND prazo_execucao > 0
                     THEN COALESCE(date(data_celebracao,
                                        '+' || prazo_execucao || ' days'), '')
                     ELSE '' END
                     WHERE fim_estimado IS NULL""")
        # O `id` junto pelo mesmo motivo do ix_ctr_data: e o desempate da
        # ordenacao, e assim o indice serve-a inteira.
        c.execute("CREATE INDEX IF NOT EXISTS ix_ctr_fim "
                  "ON contratos(fim_estimado, id)")
        # O grafico do desconto agrupa por n_anuncio so nas linhas com
        # anuncio e com os dois precos. O indice parcial cobre a
        # consulta inteira e poupa o varrimento da tabela: medido, 1,0 s
        # para 0,07 no corpus todo.
        c.execute("""CREATE INDEX IF NOT EXISTS ix_ctr_desconto ON
                     contratos(n_anuncio, preco_base, preco_contratual)
                     WHERE n_anuncio != '' AND preco_base > 0
                     AND preco_contratual > 0""")


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


def _des_html(texto):
    """Desfaz as entidades HTML que o dump do IMPIC traz por desescapar.

    O dump chega com o texto escapado ("Ramos &amp; Filhos") e, guardado
    assim, o painel escapava OUTRA vez ao desenhar -- via-se literalmente
    "&amp;" no ecra -- e procurar "Ramos & Filhos" nao encontrava nada,
    porque o que estava na base era outro texto. Medido: 5 998 entidades
    e 141 objectos.

    Ate estabilizar, nao uma vez so: 1 413 adjudicatarios vinham
    escapados DUAS vezes ("&amp;amp;") e uma passagem unica tirava uma
    capa e deixava a outra. Nenhum nome verdadeiro contem "&amp;". O
    tecto de voltas e por prudencia, nao por necessidade medida.
    """
    if not texto:
        return texto or ""
    for _ in range(4):
        if "&" not in texto:
            break
        novo = html.unescape(texto)
        if novo == texto:
            break
        texto = novo
    return texto


# As entidades que denunciam texto escapado. "&#" apanha as numericas.
_PADROES_ESCAPADOS = ("%&amp;%", "%&quot;%", "%&lt;%", "%&gt;%",
                      "%&apos;%", "%&#%")


def _desescapar_html(c):
    """Repara um corpus importado antes do _des_html(). Uma vez, por marca.

    Alem do texto, refaz as colunas derivadas dele: as normalizadas e as
    chaves "n:" (um nome com "&amp;" normalizava com um "amp" la dentro,
    e a mesma empresa escrita limpa noutra fonte ficava noutra chave).
    No fim resolve as entidades de novo, porque os nomes canonicos e o
    mapa entidade_nomes saem dessas colunas.
    """
    ja = c.execute("SELECT 1 FROM corpus_estado "
                   "WHERE chave='html_desescapado'").fetchone()
    if ja:
        return
    sujos = " OR ".join("%s LIKE ?" for _ in _PADROES_ESCAPADOS)
    mexeu_nomes = False

    afectados = c.execute(
        "SELECT id, objecto, adjudicante, adjudicante_nif, local_execucao, "
        "fundamentacao FROM contratos WHERE "
        + " OR ".join(("(" + sujos + ")") % ((col,) * len(_PADROES_ESCAPADOS))
                      for col in ("objecto", "adjudicante", "local_execucao",
                                  "fundamentacao")),
        _PADROES_ESCAPADOS * 4).fetchall()
    arranjos = []
    for r in afectados:
        nome = _des_html(r["adjudicante"])
        arranjos.append((_des_html(r["objecto"]), nome, norma_entidade(nome),
                         chave_entidade(r["adjudicante_nif"], nome),
                         _des_html(r["local_execucao"]),
                         _des_html(r["fundamentacao"]), r["id"]))
        if nome != r["adjudicante"]:
            mexeu_nomes = True
    c.executemany(
        "UPDATE contratos SET objecto=?, adjudicante=?, adjudicante_norm=?, "
        "adjudicante_chave=?, local_execucao=?, fundamentacao=? WHERE id=?",
        arranjos)

    ganhadores = c.execute(
        "SELECT rowid, nif, nome FROM contrato_adjudicatario "
        "WHERE " + sujos % ((("nome",) * len(_PADROES_ESCAPADOS))),
        _PADROES_ESCAPADOS).fetchall()
    arranjos = []
    for r in ganhadores:
        nome = _des_html(r["nome"])
        arranjos.append((nome, norma_entidade(nome),
                         chave_entidade(r["nif"], nome), r["rowid"]))
    if arranjos:
        mexeu_nomes = True
    c.executemany("UPDATE contrato_adjudicatario SET nome=?, nome_norm=?, "
                  "chave=? WHERE rowid=?", arranjos)

    if mexeu_nomes:
        resolver_entidades(c)
    c.execute("INSERT OR REPLACE INTO corpus_estado VALUES "
              "('html_desescapado', ?)",
              (datetime.now().strftime("%Y-%m-%d %H:%M"),))


def _nif_e_nome(valor):
    """O BASE escreve as partes como ['123456789 - Nome'], por vezes so
    o nome. Devolve (nif, nome) com o que houver.

    Quando o NIF nao e publico -- pessoas singulares -- o BASE escreve
    um traco no lugar dele ("- - Filomena Ferreira"). Sem tirar esse
    traco, o nome ficava com o "- - " colado e aparecia assim no painel.
    O nome desescapa-se aqui (_des_html), por isso tudo o que dele deriva
    -- normalizacao, chave, entidades -- ja nasce limpo.
    """
    if isinstance(valor, list):
        valor = valor[0] if valor else ""
    valor = valor or ""
    m = re.match(r"\s*(\d{9})\s*-\s*(.*)$", valor)
    if m:
        return m.group(1), _des_html(m.group(2).strip())
    return "", _des_html(re.sub(r"^\s*-\s*-\s*", "", valor).strip())


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
            # o texto desescapa-se todo a entrada (_des_html): o dump
            # vem escapado para HTML e "Ramos &amp; Filhos" nao e nome
            objecto = _des_html(k.get("objectoContrato")
                                or k.get("descContrato") or "")
            linhas.append((
                cid, ano, (k.get("nAnuncio") or "").strip(),
                _des_html(k.get("tipoprocedimento") or ""),
                objecto,
                nif, nome, norma_entidade(nome),
                _data_iso(k.get("dataPublicacao")),
                _data_iso(k.get("dataCelebracaoContrato")),
                k.get("precoContratual") or 0.0,
                k.get("precoBaseProcedimento") or 0.0,
                k.get("prazoExecucao") or 0,
                _des_html(", ".join(x for x in (k.get("localExecucao") or [])
                                    if x)
                          if isinstance(k.get("localExecucao"), list)
                          else (k.get("localExecucao") or "")),
                ", ".join(_cpv8(k.get("cpv"))),
                _des_html(k.get("fundamentacao") or ""),
                # nunca zero: e divisor no grafico de quem ganha
                max(1, len(ganhadores)),
                chave_entidade(nif, nome),
                simplifica(objecto),
                fim_estimado(_data_iso(k.get("dataCelebracaoContrato")),
                             k.get("prazoExecucao"))))
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


def fim_estimado(data_celebracao, prazo_dias):
    """Data estimada do fim do contrato: celebracao + prazo em dias.

    E o que alimenta a vista das renovacoes. "" quando nao da para
    estimar: sem data, sem prazo, ou com um prazo absurdo do dump (ha um
    de 365 milhoes de dias) que estourava o calendario. E estimativa e
    di-lo na pagina -- as prorrogacoes nao constam do dump.
    """
    try:
        prazo = int(prazo_dias or 0)
    except (TypeError, ValueError):
        return ""
    if not data_celebracao or prazo <= 0:
        return ""
    try:
        d = datetime.strptime(data_celebracao, "%Y-%m-%d").date()
        return (d + timedelta(days=prazo)).isoformat()
    except (ValueError, OverflowError):
        return ""


# As colunas de cada tabela, por ordem, e a unica fonte da verdade sobre
# elas: o SQL e as suas interrogacoes saem daqui. Duas vezes ja se
# acrescentou uma coluna e o INSERT posicional partiu em silencio -- com
# isto, acrescentar uma coluna que ninguem enche da erro no teste, nao a
# meio de uma importacao de meia hora.
COLS_CONTRATO = ("id", "ano", "n_anuncio", "tipo_procedimento", "objecto",
                 "adjudicante_nif", "adjudicante", "adjudicante_norm",
                 "data_publicacao", "data_celebracao", "preco_contratual",
                 "preco_base", "prazo_execucao", "local_execucao", "cpv",
                 "fundamentacao", "n_adj", "adjudicante_chave",
                 "objecto_norm", "fim_estimado")
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


def data_de_filtro(valor):
    """So aceita AAAA-MM-DD; o resto ignora-se em vez de filtrar.

    Um "de=lixo" vindo de um URL guardado comparava datas com texto e
    esvaziava a lista em silencio -- enquanto o euro minimo com lixo era
    ignorado. Dois silencios com efeitos opostos; agora e um so, e a
    lista avisa (avisos_de_datas)."""
    valor = (valor or "").strip()
    return valor if re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor) else ""


def avisos_de_datas(args):
    """O que ha de errado com as datas do filtro, por palavras.

    Duas coisas que davam lista vazia (ou filtro nenhum) sem uma palavra:
    uma data que nao se percebe, e um intervalo com o fim antes do
    principio. O intervalo invertido continua a devolver vazio -- trocar
    as datas as escondidas seria outro silencio -- mas agora diz porque."""
    fora = []
    de_bruto = (args.get("de") or "").strip()
    ate_bruto = (args.get("ate") or "").strip()
    de, ate = data_de_filtro(de_bruto), data_de_filtro(ate_bruto)
    for bruto, limpo in ((de_bruto, de), (ate_bruto, ate)):
        if bruto and not limpo:
            fora.append("A data “%s” não se percebe e foi ignorada." % bruto)
    if de and ate and de > ate:
        fora.append("O intervalo está invertido — de %s até %s não "
                    "apanha nada." % (data_pt(de), data_pt(ate)))
    return fora


def faixa_de_avisos_de_datas(args):
    """Os avisos das datas prontos a pôr na página, ou nada."""
    return "".join("<div class='flash mau'>%s</div>" % html.escape(a)
                   for a in avisos_de_datas(args))


def condicoes_contratos(args):
    """Traduz os filtros do separador dos contratos em SQL.

    Irma da condicoes(), mas nao a mesma: sao listas diferentes. Aqui
    procura-se por quem ganhou, por tipo de procedimento e por valor, que
    nos anuncios nem existem -- um anuncio ainda nao tem vencedor.
    """
    onde, valores = ["1=1"], []

    def frag_texto(texto, coluna, norma=simplifica):
        # Nas colunas normalizadas e com o termo normalizado do mesmo
        # modo, como na condicoes(): o LIKE do SQLite nao baixa o "Ç", e
        # o IMPIC escreve muitos objectos todos em maiusculas. Medido:
        # procurar "aquisição" no objecto cru perdia 68 295 contratos
        # (11,8%) sem aviso nenhum -- o mesmo defeito ja pago nos
        # anuncios, vivo no separador onde se estuda a concorrencia.
        # Devolve (fragmento, valores) sem tocar no onde, pela mesma
        # razao da condicoes(): o op=ou junta-o ao do CPV.
        pedacos = [p.strip() for p in (texto or "").split("|") if p.strip()]
        if not pedacos:
            return "", []
        ors, vals = [], []
        for p in pedacos:
            ors.append("%s LIKE ? ESCAPE '%s'" % (coluna, ESCAPE_LIKE))
            vals.append("%" + para_like(norma(p)) + "%")
        return "(" + " OR ".join(ors) + ")", vals

    def procura(texto, coluna, norma=simplifica):
        frag, vals = frag_texto(texto, coluna, norma)
        if frag:
            onde.append(frag)
            valores.extend(vals)

    def exclui(texto, coluna, norma=simplifica):
        # a procura() invertida, com o mesmo COALESCE da condicoes(): um
        # NOT sobre NULL e NULL, e a linha por preencher sumia-se
        pedacos = [p.strip() for p in (texto or "").split("|") if p.strip()]
        if not pedacos:
            return
        ors = []
        for p in pedacos:
            ors.append("COALESCE(%s,'') LIKE ? ESCAPE '%s'"
                       % (coluna, ESCAPE_LIKE))
            valores.append("%" + para_like(norma(p)) + "%")
        onde.append("NOT (" + " OR ".join(ors) + ")")

    # Os nomes de entidades procuram-se com a norma deles
    # (norma_entidade): e ela que enche adjudicante_norm e nome_norm, e e
    # ela que troca o "&" por " e " -- procurar "Ramos & Filhos" so
    # encontra "ramos e filhos" se o termo levar o mesmo caminho.
    #
    # O op=ou junta o objecto ao CPV, como na condicoes() (B07).
    frag_q, vals_q = frag_texto(args.get("q"), "c.objecto_norm")
    prefixos_cpv = [p for p in (prefixo_cpv(x)
                                for x in (args.get("cpv") or "").split("|"))
                    if p]
    if prefixos_cpv:
        frag_c = ("c.id IN (SELECT contrato_id FROM contrato_cpv WHERE %s)"
                  % " OR ".join("cpv8 LIKE ?" for _ in prefixos_cpv))
        vals_c = [p + "%" for p in prefixos_cpv]
    elif (args.get("cpv") or "").strip():
        frag_c, vals_c = "1=0", []    # codigo sem prefixo: vazio, nao tudo
    else:
        frag_c, vals_c = "", []
    juntos = ((args.get("op") or "").strip() == "ou"
              and frag_q and frag_c and frag_c != "1=0")
    if not juntos and frag_q:
        onde.append(frag_q)
        valores.extend(vals_q)
    procura(args.get("adj"), "c.adjudicante_norm", norma_entidade)
    exclui(args.get("q_excl"), "c.objecto_norm")

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
                    % " OR ".join("nome_norm LIKE ? ESCAPE '%s'" % ESCAPE_LIKE
                                  for _ in ganhou))
        valores += ["%" + para_like(norma_entidade(p)) + "%" for p in ganhou]

    if juntos:
        onde.append("(%s OR %s)" % (frag_q, frag_c))
        valores.extend(vals_q)
        valores.extend(vals_c)
    elif frag_c and not ((args.get("op") or "").strip() == "ou"
                         and frag_q and frag_c == "1=0"):
        onde.append(frag_c)
        valores.extend(vals_c)

    # A exclusao por CPV, com o mesmo NOT IN sobre a tabela filha do
    # filtro positivo. Um codigo que nao da prefixo nao exclui nada --
    # ao contrario do positivo, o vazio aqui e um nao-filtro.
    fora_cpv = [p for p in (prefixo_cpv(x)
                            for x in (args.get("cpv_excl") or "").split("|"))
                if p]
    if fora_cpv:
        onde.append("c.id NOT IN (SELECT contrato_id FROM contrato_cpv "
                    "WHERE %s)"
                    % " OR ".join("cpv8 LIKE ?" for _ in fora_cpv))
        valores += [p + "%" for p in fora_cpv]

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

    de = data_de_filtro(args.get("de"))
    if de:
        onde.append("c.data_celebracao >= ?")
        valores.append(de)
    ate = data_de_filtro(args.get("ate"))
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


# A verificacao pedida pelo botao, fora do pedido do browser.
#
# "Verificar agora" corria dentro do pedido: recolhe paginas do portal
# com pausas, le ate 40 detalhes a um segundo cada e ainda passa os
# alertas -- minutos com a pagina em branco, sem sinal de que arrancou e
# sem nada a impedir um segundo clique de comecar tudo de novo. Ao lado,
# no mesmo painel, "Actualizar contratos" ja corria em thread com o
# estado a vista e "Trazer peças" numa fila. Eram tres trabalhos longos
# com tres comportamentos; passa a ser um.
_VERIFICACAO = {"a_correr": False, "passo": ""}
_VERIFICACAO_TRINCO = threading.Lock()


def verificacao_a_correr():
    """O passo em que vai, ou "" se nao estiver a correr."""
    return _VERIFICACAO["passo"] if _VERIFICACAO["a_correr"] else ""


def comecar_verificacao(slot=None):
    """Arranca a verificacao numa thread. (arrancou, porque).

    O `slot` e o par (dia, hora) quando quem pede e o relogio: e o que
    marca a hora como corrida, no fim e so se correu bem. O botao do
    painel nao passa nada -- um clique a mao nao e um slot.
    """
    with _VERIFICACAO_TRINCO:
        if _VERIFICACAO["a_correr"]:
            return False, "já está a verificar — %s" % _VERIFICACAO["passo"]
        _VERIFICACAO["a_correr"] = True
        _VERIFICACAO["passo"] = "a arrancar"

    def correr():
        try:
            _, novos = verificar(
                passo=lambda p: _VERIFICACAO.__setitem__("passo", p))
            if slot:
                registar_slot(slot[0], slot[1], novos)
        except Exception as erro:
            # A thread morre em silencio; o painel tem de ficar a saber.
            marca("ultima_verificacao", datetime.now().strftime("%Y-%m-%d %H:%M"))
            marca("ultima_mensagem", "a verificação falhou: %s" % str(erro)[:150])
            marca("ultima_ok", "0")
        finally:
            _VERIFICACAO["a_correr"] = False
            _VERIFICACAO["passo"] = ""

    threading.Thread(target=correr, daemon=True).start()
    return True, ""


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
                        # Pela mesma porta do botao "Verificar agora", e
                        # nao pelo verificar() directo. Sao duas coisas
                        # que faltavam: o TRINCO, porque o relogio podia
                        # apanhar um clique a meio e por duas
                        # verificacoes na mesma base, e o `passo`, que e
                        # o que a barra lateral mostra. Um slot falhado
                        # dispara isto no ARRANQUE do painel -- copia de
                        # 93 MB, push da triagem, recolha toda, ~5
                        # minutos -- e ate 01/09/2026 nao havia nada no
                        # ecra a explicar a lentidao. Nao espera pelo
                        # fim: se o trinco recusar, o slot fica por
                        # correr e tenta-se no minuto seguinte.
                        comecar_verificacao(slot=(dia, hora))
        except Exception as erro:
            # Engolir isto em silencio fazia com que uma avaria persistente
            # parecesse "ainda nao chegou a hora": o painel continuava a
            # mostrar a ultima verificacao boa, dias a fio.
            try:
                marca_erro("ultimo_erro_relogio", "relogio", "%s: %s"
                           % (datetime.now().strftime("%Y-%m-%d %H:%M"),
                              str(erro)[:200]))
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
/* Paleta "ardosia e ambar" (escolhida a 31/08/2026, fase de desenho
   visual). Os nomes das variaveis sao os de sempre -- mudam os valores,
   e o CSS todo vem atras. Duas regras que nao se quebram:
   - todos os --t* passam AA (4.5:1) sobre --papel, que e o pior fundo.
     A escala antiga descia a #b4b0a6, que dava 2.5:1 em texto de 10px;
   - o que e decoracao (setas, separadores, molduras) usa --traco ou
     --linha, nunca um --t*. Foi a confusao entre os dois que fez
     nascer os cinzentos ilegiveis. */
:root{
 --ink:#14181e; --azul:#17557f; --verde:#1a7a4d; --verm:#b0341a;
 --laranja:#a8450e; --coral:#e08b2c;
 --papel:#eef1f4; --creme:#f8fafb; --linha:#dbe0e6; --linha2:#eceff2;
 --t1:#14181e; --t2:#333c46; --t3:#4d5661; --t4:#5c6570; --t5:#67707c; --t6:#69727e;
 --traco:#b9c1cb;
 /* fundos das notas: cada um so acompanha a cor de texto do mesmo nome */
 --azul-fundo:#eaf2f8; --azul-borda:#cddfeb;
 --verde-fundo:#e7f3ec; --laranja-fundo:#fbeee2; --verm-fundo:#fbe9e5;
 /* na barra escura o contraste conta ao contrario: estes tres sao os
    unicos claros que la vivem */
 --barra-t1:rgba(255,255,255,.94); --barra-t2:rgba(255,255,255,.7);
 --barra-t3:rgba(255,255,255,.55); --barra-linha:rgba(255,255,255,.14);
 --barra-on:rgba(255,255,255,.13);
 --ok-claro:#57c894; --mau-claro:#ff8a6a;
 --sans:Archivo,system-ui,-apple-system,'Segoe UI',sans-serif;
 --mono:'JetBrains Mono',ui-monospace,Consolas,monospace;
}
*{box-sizing:border-box}
/* Foco de teclado visivel e igual em toda a aplicacao. O contorno de
   omissao do browser sao 0,8px quase pretos, que numa lista de vinte
   accoes nao se ve; e ha campos que o desligam para o trocar por uma
   pista propria (o nome da fase, o responsavel, o "quem trabalha"),
   o que deixava a aplicacao com tres ideias diferentes de foco.
   :focus-visible e nao :focus -- so aparece a quem navega por teclado,
   e nao a cada clique do rato. */
:focus-visible{outline:2px solid var(--azul);outline-offset:2px;
 border-radius:4px}
aside :focus-visible{outline-color:var(--coral)}
body{margin:0;background:var(--papel);font-family:var(--sans);color:var(--t1);
 -webkit-font-smoothing:antialiased}
a{color:var(--azul);text-decoration:none}
a:hover{color:var(--ink)}
::-webkit-scrollbar{width:10px;height:10px}
::-webkit-scrollbar-thumb{background:var(--traco);border-radius:6px}
.app{display:flex;min-height:100vh}

/* Barra lateral, 140px. Era 236 e ocupava um quinto de um portatil para
   quatro palavras; o Afonso pediu-a estreita. A 140 sobram 116px de
   conteudo, e e por isso que aqui tudo tem medidas proprias em vez de
   herdar as da zona principal: os textos partem-se em linhas curtas em
   vez de encolherem. Encolher a largura sem refazer o espacamento e o
   que a partia -- com o padding antigo de 22px sobravam 77px. */
aside{width:140px;flex:none;background:var(--ink);color:#fff;display:flex;
 flex-direction:column;position:sticky;top:0;height:100vh;padding:16px 12px;
 box-sizing:border-box}
.marca{padding:0 0 12px;border-bottom:1px solid var(--barra-linha)}
.marca .logo{font:700 15px/1 var(--sans);letter-spacing:-.3px}
.marca .logo span{color:var(--coral)}
.marca .sub{font:500 9.5px/1.45 var(--sans);color:var(--barra-t3);margin-top:7px}
.marca .meta{font:500 9.5px/1.6 var(--mono);color:var(--barra-t2);margin-top:7px}
aside nav{display:flex;flex-direction:column;gap:1px;margin:12px -6px 0}
aside nav a{display:block;padding:7px 8px;border-radius:5px;
 color:var(--barra-t2);font:500 12.5px/1.25 var(--sans)}
aside nav a:hover{background:var(--barra-on);color:#fff}
aside nav a.on{background:var(--barra-on);color:#fff}
aside nav a b{font:inherit;font-weight:600}
/* as duas vistas de um item aberto (Em curso, Mercado) */
aside nav a.sub{padding:5px 8px 5px 16px}
aside nav a.sub b{font-weight:400;font-size:11.5px}
aside nav a.sub.on b{font-weight:600}
.caixa{margin:16px 0 0;padding:12px 0 0;border-top:1px solid var(--barra-linha)}
.caixa .r{font:600 8.5px/1 var(--sans);color:var(--barra-t3);
 text-transform:uppercase;letter-spacing:.1em}
.caixa .h{font:500 10px/1.5 var(--mono);color:var(--barra-t2);margin-top:6px}
.caixa .n{font:400 10.5px/1.5 var(--sans);color:var(--barra-t2);margin-top:5px}
/* o ponto da ultima verificacao e a porta dos Indicadores (11.6-A) */
.caixa a.n{display:block}
.caixa a.n:hover{color:#fff}
/* Quem esta a trabalhar. Fechado por omissao: e uma escolha que se faz
   uma vez e ocupava permanentemente o canto da barra. */
.sou{margin-top:auto;padding:12px 0 0;border-top:1px solid var(--barra-linha)}
.sou > summary{display:flex;align-items:center;gap:7px;cursor:pointer;
 list-style:none;color:var(--barra-t3);font:500 10.5px/1.3 var(--sans)}
.sou > summary::-webkit-details-marker{display:none}
.sou > summary:hover{color:#fff}
.sou form{display:flex;align-items:center;gap:6px;margin-top:9px;flex-wrap:wrap}
.sou .av{width:22px;height:22px;border-radius:50%;background:var(--barra-on);
 flex:none;font:600 9px/22px var(--sans);color:#fff;text-align:center}
.sou input{flex:1;min-width:0;background:transparent;border:0;
 border-bottom:1px solid var(--barra-linha);color:#fff;
 font:500 11.5px/1.6 var(--sans);padding:2px 0}
.sou input::placeholder{color:var(--barra-t3)}
.sou input:focus{border-bottom-color:var(--coral)}
.sou input:focus:not(:focus-visible){outline:none}
.sou button{background:none;border:0;color:var(--barra-t3);cursor:pointer;
 font:400 10.5px/1.2 var(--sans);flex:none;
 padding:6px 5px;margin:-6px 0;min-height:24px;box-sizing:border-box}
.sou button:hover{color:#fff}

/* zona principal */
main{flex:1;min-width:0;display:flex;flex-direction:column}
.topo{padding:16px 34px 0;border-bottom:1px solid var(--linha);background:var(--creme);
 position:sticky;top:0;z-index:5}
.migalhas{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.migalhas .b{display:flex;align-items:center;gap:8px;min-width:0;
 font:500 11.5px/1 var(--sans);color:var(--t3)}
/* o separador das migalhas e um caractere, nao um risco: leva cor de
   texto, ainda que a mais fraca da escala */
.migalhas .b s{text-decoration:none;color:var(--t5)}
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
.bt.verde:hover{background:#155f3c;color:#fff;border-color:#155f3c}
/* A escala tem degraus a serio. Estava tudo entre 10 e 13,5px e a
   hierarquia fazia-se so por peso e cor -- numa pagina densa lia-se
   tudo ao mesmo nivel. */
h1.tit{margin:8px 0 0;font:700 22px/1.25 var(--sans);color:var(--ink);
 letter-spacing:-.4px;max-width:900px;text-wrap:pretty}
p.subtit{margin:5px 0 0;font:400 12.5px/1.45 var(--sans);color:var(--t3);
 max-width:820px;text-wrap:pretty}
.abas{display:flex;align-items:center;gap:4px;margin-top:14px}
.abas a{padding:9px 14px;border-radius:7px 7px 0 0;font:600 12.5px/1 var(--sans);
 background:transparent;color:var(--t3);border:1px solid transparent;
 border-bottom:none;margin-bottom:-1px}
.abas a:hover{color:var(--ink)}
.abas a.on{background:#fff;color:var(--ink);border-color:var(--linha);font-weight:700}
.abas a i{font:500 11px/1 var(--mono);font-style:normal;color:var(--t5);margin-left:4px}
.abas a.on i{color:var(--t3)}
.vazio-topo{height:16px}
/* A folga lateral e o tecto do conteudo acompanham o ecra. Com o
   .larg preso em 1240 sobravam 530px vazios num monitor de 1920 e
   1170 num de 2560 -- quase metade do ecra por usar. O tecto
   continua a existir: sem ele, uma linha de texto atravessava um
   ecra largo de ponta a ponta e deixava de se ler. */
.corpo{padding:24px clamp(20px,2.4vw,44px) 60px}
.larg{max-width:1560px}

/* pecas comuns */
.cx{background:#fff;border:1px solid var(--linha);border-radius:8px;
 box-shadow:0 1px 2px rgba(20,24,30,.04)}
.rot{font:700 11px/1 var(--sans);color:var(--t2);text-transform:uppercase;
 letter-spacing:.07em}
.nota{font:400 11.5px/1.5 var(--sans);color:var(--t4)}
.vazio{background:#fff;border:1px solid var(--linha);border-radius:8px;
 padding:40px;text-align:center;color:var(--t4);font:400 13px/1.55 var(--sans)}
.flash{background:var(--azul-fundo);border:1px solid var(--azul-borda);border-radius:9px;
 padding:11px 15px;margin-bottom:14px;font:500 12.5px/1.4 var(--sans);
 color:var(--azul)}
.flash.mau{background:var(--verm-fundo);border-color:#f0cfc7;color:var(--verm)}
.flash form.desfazer{margin-left:10px;vertical-align:middle}
.flash code{font:500 11.5px/1 var(--mono);background:rgba(0,0,0,.06);
 padding:2px 6px;border-radius:4px}
.tag{font:500 10.5px/1 var(--sans);padding:4px 7px;border-radius:4px;
 background:var(--linha2);color:var(--t3);white-space:nowrap}
.tag.mono{font-family:var(--mono)}
.tag.ok{background:var(--verde-fundo);color:var(--verde);font-weight:600}
.tag.avisa{background:var(--laranja-fundo);color:var(--laranja);font-weight:600}
.tag.mau{background:var(--verm-fundo);color:var(--verm);font-weight:600}
.tag.info{background:var(--azul-fundo);color:var(--azul);font-weight:600}
.ponto{width:7px;height:7px;border-radius:50%;flex:none;display:inline-block}
.caixa .n .ponto{margin-right:6px}
.ponto.pulsa{animation:pisca 1.1s infinite}
/* "Verificar agora" enquanto corre: o botao sai e fica o sinal de vida,
   para nao haver dois clientes a comecar duas recolhas. */
.accoes-topo .a-correr{font:500 12px/1 var(--sans);color:var(--laranja);
 display:inline-flex;align-items:center;gap:7px;white-space:nowrap}
.accoes-topo .a-correr::before{content:'';width:8px;height:8px;flex:none;
 border-radius:50%;background:var(--laranja);animation:pisca 1.1s infinite}

/* Filtros. A zona de controlo sao tres caixas irmas (campos, arvore de
   CPV, filtros guardados) e todas tinham o peso do conteudo: fundo
   branco, sombra e 14px de folga. Empilhadas antes do primeiro anuncio
   ocupavam meio ecra. Continuam as tres -- so as duas de baixo baixam
   de nivel, com o fundo do papel e sem sombra. */
.filtros{display:flex;align-items:center;gap:9px;flex-wrap:wrap;
 padding:12px 14px;margin-bottom:8px}
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
/* Um campo desactivado tem de o parecer. No modo "por fim estimado" o
   de/ate desactiva-se com a explicacao no title (dois eixos do tempo na
   mesma pagina confundiam) -- mas desenhado igual aos outros, so quem
   tentasse escrever la e que descobria. */
.filtros input:disabled,.filtros select:disabled{background:var(--linha2);
 color:var(--t5);border-style:dashed;cursor:not-allowed}
.filtros:has(input:disabled) label{color:var(--t5)}
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
.alerta.on{border-color:var(--azul-borda);background:var(--creme)}
.alerta .sobre{display:flex;flex-direction:column;gap:4px;min-width:0;flex:1}
.alerta .sobre a{font:600 13.5px/1.2 var(--sans);color:var(--ink)}
.alerta.on .sobre a{color:var(--azul)}
.alerta .sobre a:hover{text-decoration:underline}
.alerta .q{font:400 11.5px/1.4 var(--sans);color:var(--t5);
 overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.alerta .conta{font:400 11.5px/1.4 var(--sans);color:var(--t5);
 text-align:right;flex:none}
.alerta .conta b{color:var(--azul);font-weight:600}
.alerta .sobre b{font:600 13.5px/1.2 var(--sans);color:var(--ink)}
.alerta.on .sobre b{color:var(--azul)}
.alerta .onde{font:400 11px/1.3 var(--sans);color:var(--t6)}
.alerta .onde a{color:var(--t5)}
.alerta .onde a:hover{color:var(--azul);text-decoration:underline}
.alerta .avisa-mal{display:block;font:400 10.5px/1.4 var(--sans);
 color:var(--laranja);margin-top:3px}
.alerta .apagar{cursor:pointer;border:0;background:none;color:var(--t6);
 font:500 17px/1 var(--sans);padding:0 4px;
 min-width:24px;min-height:24px;box-sizing:border-box}
.alerta .apagar:hover{color:var(--verm)}
.alerta form{display:flex;flex:none}
.conf-email{padding:20px 22px}
.form-email{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end}
.form-email label{display:flex;flex-direction:column;gap:5px;
 font:500 11px/1 var(--sans);color:var(--t5);flex:1;min-width:150px}
.form-email input{padding:9px 12px;border:1px solid var(--linha);
 border-radius:8px;background:var(--creme);
 font:400 12.5px/1.2 var(--sans);color:var(--ink)}
.form-email button{flex:none}
.novo-filtro{padding:20px 22px}
.novo-filtro .filtros{padding:0;margin:0;box-shadow:none;border:0;
 background:none;gap:8px}
/* Treze campos em fila davam um muro onde nenhum se destacava. Os
   campos nao mudam nem mudam de ordem -- ganham um degrau de largura
   (o texto livre cresce, os selectores ficam do tamanho do que
   escolhem) e o botao corta a linha, para ser o fim de uma frase e nao
   mais uma caixa igual as outras. */
.novo-filtro .filtros input[type=text]{flex:1 1 200px;min-width:0}
.novo-filtro .filtros select{flex:0 1 auto}
.novo-filtro .filtros button{flex-basis:100%;max-width:150px;margin-top:4px}
.guardado.parcial{border-style:dashed}
.guardado i{font:400 9.5px/1 var(--sans);font-style:normal;color:var(--t6);
 margin-left:6px;padding-right:11px}
.guardados .gerir{font:500 11.5px/1 var(--sans);color:var(--t5);
 padding:8px 10px}
.guardados .gerir:hover{color:var(--ink)}
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
 margin-bottom:12px;font:400 11.5px/1.4 var(--sans);color:var(--t3)}
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
 grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:14px}
.graf-corpo>.graf:last-child{grid-column:1/-1}
.graf{padding:16px 18px}
.barras-h{display:flex;flex-direction:column;gap:9px}
/* O nome levava 1.4fr contra 2fr da barra e saia "Capgemin…" em quase
   todas as linhas: numa lista de quem ganha, o nome e metade do que ha
   para ler. A barra e comparativa -- perde largura sem perder sentido. */
.bh{display:grid;grid-template-columns:minmax(0,2fr) minmax(50px,1.3fr) 76px 84px;
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
 color:var(--t4);text-transform:uppercase;letter-spacing:.06em;white-space:nowrap}
.tab-contratos td{padding:10px 12px;border-bottom:1px solid var(--linha2);
 font:400 12.5px/1.45 var(--sans);color:var(--t3);vertical-align:top}
.tab-contratos tr:last-child td{border-bottom:0}
.tab-contratos tr:hover td{background:var(--creme)}
.tab-contratos td.d{font-family:var(--mono);white-space:nowrap;color:var(--t4)}
/* O objecto e a coluna que responde a pergunta e era a mais apagada da
   tabela: os nomes de entidade, sendo ligacoes azuis, puxavam o olho
   primeiro. Invertido pelo peso, sem tirar o azul -- sao ligacoes e tem
   de o parecer. */
.tab-contratos td.o{color:var(--t1);font-weight:600;max-width:340px}
.tab-contratos td.g{color:var(--t2);max-width:220px}
.tab-contratos td a{font-weight:400}
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
 font:400 10px/1 var(--sans);color:var(--t4);text-align:center}
.escada span b{font:600 12px/1 var(--mono);color:var(--ink)}
/* o rotulo desta esta sobre fundo azul-claro e nao sobre branco: com
   --t4 ficava a 4,3:1, por baixo do limite */
.escada span.med{border-color:var(--azul);background:var(--azul-fundo)}
.escada span.med{color:var(--t3)}
.escada span.med b{color:var(--azul)}
.mercado-tab{overflow-x:auto}
.mercado-tab .tab-mercado{min-width:720px}
.mercado code{font:500 11.5px/1 var(--mono);background:var(--linha2);
 padding:2px 5px;border-radius:4px}
.guardados{display:flex;align-items:center;gap:8px;flex-wrap:wrap;
 padding:10px 14px;margin-bottom:8px;background:var(--creme);box-shadow:none}
.guardados .rot{margin-right:4px}
.guardados .nada{font:400 12px/1 var(--sans);color:var(--t6)}
/* O que o filtro em uso tem e esta pagina nao aplica. Estava so no
   `title` do chip: quem nao passasse o rato por cima nunca o via. */
.parcial-nota{flex-basis:100%;order:9;font:400 12px/1.5 var(--sans);
 color:var(--t5);border-left:2px solid var(--laranja);padding:2px 0 2px 10px}
.parcial-nota b{color:var(--t3);font-weight:600}
.guardado{display:inline-flex;align-items:center;border:1px solid var(--linha);
 border-radius:99px;background:var(--creme);overflow:hidden}
.guardado a{padding:7px 4px 7px 13px;font:500 12.5px/1 var(--sans);color:var(--t3)}
.guardado:hover{border-color:var(--t6)}
.guardado:hover a{color:var(--ink)}
.guardado.on{border-color:var(--azul);background:var(--azul-fundo)}
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
 border:1px solid var(--azul-borda);background:var(--azul-fundo);border-radius:9px;margin-bottom:12px;
 font:500 12px/1.3 var(--sans);color:var(--azul)}
.cpv-activo b{font:600 12px/1.3 var(--mono)}
.cpv-activo a{text-decoration:underline}

/* arvore de CPV */
details.arvore{margin-bottom:8px;overflow:hidden;background:var(--creme);
 border:1px solid var(--linha);border-radius:8px}
details.arvore[open]{background:#fff}
details.arvore>summary{cursor:pointer;display:flex;align-items:center;gap:10px;
 padding:11px 16px;background:var(--creme);list-style:none}
details.arvore>summary::-webkit-details-marker{display:none}
details.arvore>summary::before{content:'\25B8';font:500 11px/1 var(--mono);color:var(--t3)}
details.arvore[open]>summary::before{content:'\25BE'}
.arv-tit{font:600 13px/1 var(--sans);color:var(--ink)}
.arv-sub{font:400 12px/1 var(--sans);color:var(--t5)}
/* --t5 sobre --linha2 dava 4,35:1 -- a unica falha de AA que sobrou da
   passagem toda, e por pouco. Sobre um fundo que nao e branco a escala
   perde meio ponto de contraste: e por isso que os --t* se medem sobre
   o --papel e nao sobre o branco. */
.arv-chip{margin-left:auto;font:600 11px/1 var(--sans);padding:4px 8px;
 border-radius:5px;background:var(--linha2);color:var(--t3)}
.arvore-topo{display:flex;align-items:center;gap:10px;flex-wrap:wrap;
 padding:14px 18px 12px;border-top:1px solid var(--linha)}
.arvore-topo input{flex:1;min-width:220px;padding:8px 12px;border:1px solid var(--linha);
 border-radius:8px;background:var(--creme);font:400 12.5px/1.2 var(--sans)}
.arvore-topo button{cursor:pointer;padding:9px 14px;border-radius:7px;border:0;
 background:var(--azul);color:#fff;font:600 12px/1 var(--sans)}
.arvore-topo button.claro{background:#fff;color:var(--t3);border:1px solid var(--linha)}
#arvore-contagem{font:400 11.5px/1 var(--sans);color:var(--t5)}
#arvore-corpo{max-height:330px;overflow-y:auto;border:1px solid var(--linha2);
 border-radius:9px;padding:8px 6px;background:var(--creme);margin:0 18px 14px}
#arvore-corpo details{margin-left:22px}
#arvore-corpo summary{cursor:pointer;list-style:revert}
#arvore-corpo .no{display:flex;align-items:center;gap:9px;padding:5px 8px;
 border-radius:6px}
#arvore-corpo .no:hover{background:var(--linha2)}
/* codigo tirado a mao de dentro de um grupo marcado: fica riscado, para
   se ver de relance o que e que a divisao apanha e o que nao */
#arvore-corpo .no.excluido .lbl{text-decoration:line-through}
#arvore-corpo .no.excluido .cod{text-decoration:line-through}
#arvore-corpo .no.excluido{background:var(--linha2)}
#arvore-corpo .no .fora{font:600 9.5px/1 var(--sans);color:var(--verm);
 letter-spacing:.04em;text-transform:uppercase;flex:none}
#arvore-corpo .cod{font:500 10.5px/1 var(--mono);color:var(--t5);flex:none}
#arvore-corpo .lbl{font:500 12px/1.35 var(--sans);color:var(--azul);min-width:0;
 overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#arvore-corpo .n{font:400 10.5px/1 var(--sans);color:var(--t6);flex:none}
/* codigo sem nada nesta fonte de contagem: escolhe-lo da lista vazia
   garantida, por isso esbatido -- mas nao escondido, que a mesma arvore
   conta doutras coisas no outro separador */
#arvore-corpo .no.zero .lbl,#arvore-corpo .no.zero .cod{color:var(--t6)}
#arvore-corpo .no.zero{opacity:.65}
#arvore-corpo .escondido{display:none}
.arv-pe{padding:0 18px 16px;font:400 11px/1.5 var(--sans);color:var(--t5)}

/* lista */
.linha-conta{display:flex;align-items:center;gap:10px;margin:12px 0;
 font:400 12px/1.5 var(--sans);color:var(--t4)}
.linha-conta a{margin-left:auto;color:var(--t4)}
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
.paginas .morto{border:1px solid transparent;color:var(--t4)}
.paginas .corte{border:1px solid transparent;color:var(--t4);min-width:0;
 padding:7px 2px}
/* Saltar para uma pagina. Com 3300 paginas, andar de dez em dez nao la
   chega, e a unica forma de ver o meio do acervo era por filtro. */
.ir-pagina{display:flex;align-items:center;gap:6px;margin-left:10px}
.ir-pagina label{font:400 12px/1 var(--sans);color:var(--t3);padding:0}
.ir-pagina input{width:72px;padding:6px 8px;border:1px solid var(--linha);
 border-radius:6px;font:500 12.5px/1 var(--sans);background:#fff;color:var(--ink)}
.ir-pagina button{padding:7px 11px;border:1px solid var(--linha);border-radius:6px;
 background:#fff;color:var(--t4);font:500 12.5px/1 var(--sans);cursor:pointer}
.ir-pagina button:hover{border-color:var(--t6);color:var(--ink)}
.lista{display:flex;flex-direction:column;gap:9px}
.item{display:grid;grid-template-columns:minmax(0,1fr) 200px;background:#fff;
 border:1px solid var(--linha);border-radius:7px;box-shadow:0 1px 2px rgba(20,24,30,.04);
 overflow:hidden}
.item:hover{border-color:var(--traco)}
.item-corpo{padding:14px 17px;min-width:0}
.item-titulo{font:700 15px/1.35 var(--sans);color:var(--azul);display:block;
 letter-spacing:-.1px;text-wrap:pretty}
.item-titulo:hover{color:var(--ink)}
.item-entidade{font:400 12.5px/1.4 var(--sans);color:var(--t2);margin-top:5px}
.item-entidade .quando{color:var(--t4)}
.item-meta{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}
.item-lado{padding:14px 17px;border-left:1px solid var(--linha2);display:flex;
 flex-direction:column;align-items:flex-end;justify-content:center;gap:8px}
/* O prazo e o que decide, e le-se antes do preco. As tres cores sao as
   mesmas das etiquetas de estado (etiqueta_prazo devolve a classe): o
   que muda e o peso -- aqui e um numero, nao um distintivo. */
.item-prazo{font:700 13.5px/1 var(--mono);color:var(--t3)}
.item-prazo.mau{color:var(--verm)}
.item-prazo.avisa{color:var(--laranja)}
.item-prazo.ok{color:var(--verde)}
.item-preco{font:600 13px/1.2 var(--mono);color:var(--ink)}
.item-accoes{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}
/* o motivo do abandono pergunta-se numa caixa por cima (decisao do
   Afonso a 01/09/2026): um selector ao lado do botao punha uma pergunta
   permanente em cada uma das vinte linhas da lista, e a lista e para
   ler anuncios */
dialog.modal{border:0;border-radius:12px;padding:0;max-width:440px;width:92vw;
 box-shadow:0 18px 48px rgba(0,0,0,.28);color:var(--ink)}
dialog.modal::backdrop{background:rgba(20,24,30,.42)}
dialog.modal form{padding:22px 24px 18px;margin:0;display:block}
dialog.modal h3{font:700 15px/1.3 var(--sans);color:var(--ink);margin:0 0 4px}
dialog.modal .alvo{font:400 12.5px/1.45 var(--sans);color:var(--t3);
 margin:0 0 12px;text-wrap:pretty}
dialog.modal .nota{font:400 11.5px/1.5 var(--sans);color:var(--t5);
 margin:0 0 14px}
dialog.modal .escolhas{display:flex;flex-direction:column;gap:2px;
 margin-bottom:18px}
dialog.modal .escolhas label{display:flex;align-items:center;gap:9px;
 padding:9px 10px;border-radius:7px;border:1px solid var(--linha);
 font:500 12.5px/1.3 var(--sans);color:var(--t2);cursor:pointer}
dialog.modal .escolhas label:hover{border-color:var(--t4);background:var(--creme)}
dialog.modal .escolhas input{margin:0;flex:none}
dialog.modal .modal-pe{display:flex;justify-content:flex-end;gap:8px}
dialog.modal .modal-pe button{cursor:pointer;font:600 12px/1 var(--sans);
 padding:10px 16px;border-radius:7px;border:1px solid var(--linha);
 background:#fff;color:var(--t3)}
dialog.modal .modal-pe button[type=submit]{background:var(--verm);
 border-color:var(--verm);color:#fff}
dialog.modal .modal-pe button[type=submit]:hover{filter:brightness(1.08)}
.mini{cursor:pointer;padding:7px 12px;border-radius:6px;font:600 11.5px/1 var(--sans);
 border:1px solid var(--linha);color:var(--t3);background:#fff;display:inline-block}
.mini:hover{border-color:var(--verm);color:var(--verm)}
/* "interessa" em contorno e nao em bloco cheio: numa lista de vinte,
   vinte blocos verdes puxavam o olho todo para a coluna das accoes e
   os titulos -- o que se le para decidir -- ficavam em segundo plano. */
.mini.verde{background:#fff;color:var(--verde);border-color:var(--verde)}
.mini.verde:hover{background:var(--verde);color:#fff;border-color:var(--verde)}
.rodape{margin-top:18px;padding:12px 16px;border:1px solid var(--linha);
 border-radius:8px;background:var(--creme);display:flex;align-items:center;gap:10px}
.rodape .e{font:500 12px/1 var(--sans);color:var(--t2)}
.rodape .d{font:400 12px/1 var(--sans);color:var(--t5)}

/* Ficha: composicao em dossier (A1-C, escolha do Afonso a 31/08/2026).
   Uma coluna so, por ordem de leitura, com o cabecalho fino e o indice
   presos ao rolar. A coluna da direita desapareceu: esgotava-se a um
   quinto da pagina e os outros 80% do rolo eram uma coluna unica na
   mesma, com o texto lido pelo modelo a ocupar tudo. */
.ficha-cab{display:flex;align-items:center;gap:10px;padding:2px 0 10px;
 border-bottom:1px solid var(--linha)}
.ficha-cab .volta{font:600 15px/1 var(--sans);color:var(--t3);flex:none;
 padding:4px 2px}
.ficha-cab .volta:hover{color:var(--ink)}
.ficha-cab .t{flex:1;min-width:0;font:700 14.5px/1.3 var(--sans);color:var(--ink);
 overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ficha-cab form.accao{flex:none}
.chip-prazo{flex:none;font:700 12px/1 var(--mono);padding:6px 9px;border-radius:5px;
 background:var(--linha2);color:var(--t2);white-space:nowrap}
.chip-prazo.mau{background:var(--verm-fundo);color:var(--verm)}
.chip-prazo.avisa{background:var(--laranja-fundo);color:var(--laranja)}
.chip-prazo.ok{background:var(--verde-fundo);color:var(--verde)}
.ficha-indice{display:flex;align-items:center;gap:20px;flex-wrap:wrap;
 padding:0 0 2px}
.ficha-indice>a{padding:10px 0;font:600 12px/1 var(--sans);color:var(--t3);
 border-bottom:2px solid transparent;margin-bottom:-1px}
.ficha-indice>a:hover{color:var(--ink)}
.ficha-indice>a.on{color:var(--ink);border-bottom-color:var(--azul)}
.ficha-indice .dir{margin-left:auto;display:flex;align-items:center;gap:12px;
 flex-wrap:wrap}
.ficha-indice .nota-modo{font:400 11.5px/1 var(--sans);color:var(--t4)}
/* accoes de segunda linha: sao ligacoes, nao botoes -- competiam com o
   "Interessa" quando eram seis caixas iguais lado a lado */
.bt-leve{cursor:pointer;background:none;border:0;
 font:500 11.5px/1 var(--sans);color:var(--t3);display:inline-block;
 padding:6px 5px;margin:-6px 0;min-height:24px;box-sizing:border-box}
.bt-leve:hover{color:var(--azul);text-decoration:underline}
.ficha-dossier{display:flex;flex-direction:column;gap:14px}
.ficha-dossier>#mercado{display:flex;flex-direction:column;gap:14px}
.ficha-pe{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:14px;
 align-items:start}
@media (max-width:900px){.ficha-pe{grid-template-columns:minmax(0,1fr)}}
/* um titulo vazio nao ocupa espaco: a ficha nao usa o cabecalho grande */
h1.tit:empty,p.subtit:empty{display:none}
.cabeca{padding:24px 26px}
.cabeca .chips{display:flex;align-items:center;gap:9px;margin-bottom:11px;flex-wrap:wrap}
.cabeca .ref{font:500 11px/1 var(--mono);color:var(--t4)}
.cabeca h2{margin:0 0 6px;font:700 22px/1.3 var(--sans);color:var(--azul);
 letter-spacing:-.4px;text-wrap:pretty}
.cabeca .ent{font:400 13px/1.4 var(--sans);color:var(--t2);margin-bottom:20px}
.cabeca .ent a{color:var(--azul)}
.cabeca .ent a:hover{text-decoration:underline}
/* Os factos repartem a linha entre os que existirem. Era `flex:1 1 30%`
   e com cinco campos dava tres numa linha e depois duas linhas de um --
   celulas do tamanho de um cartaz. Uma grelha de colunas fixas resolvia
   isso e trazia o contrario: numa consulta preliminar, que so tem tres
   factos, sobrava uma celula cinzenta vazia a parecer avaria. */
.factos{display:flex;flex-wrap:wrap;gap:1px;background:var(--linha);
 border:1px solid var(--linha);border-radius:8px;overflow:hidden}
.facto{background:var(--creme);padding:12px 15px;flex:1 1 180px;min-width:0}
.facto .k{font:600 9.5px/1 var(--sans);color:var(--t4);text-transform:uppercase;
 letter-spacing:.08em}
.facto .v{font:600 13px/1.4 var(--sans);color:var(--ink);margin-top:6px}
.facto.larg{flex-basis:100%}
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
 text-wrap:pretty;word-break:break-word;white-space:pre-line;
 max-width:86ch}
/* ... mas uma grelha de perfis ou uma lista nao e texto corrido:
   essas querem toda a largura que houver */
.essencial dd:has(.perfis){max-width:none}
/* As tres formas dos campos longos lidos das pecas (desenha_valor).
   O texto e o mesmo -- o que muda e ter degraus: um perfil le-se como
   um cartao, uma enumeracao le-se como lista. Em bloco corrido, os 20
   perfis deste anuncio eram 3 200 caracteres com o peso do essencial. */
/* A linha de um campo de perfis abre-se a toda a largura: o rotulo
   sobe para cima e os cartoes ficam com a pagina inteira. Espremidos
   na coluna do valor davam duas colunas de 240px, e "Certificação
   Gestão de Projeto" partia em tres linhas. */
.essencial .par:has(.perfis){grid-template-columns:minmax(0,1fr);gap:8px}
.perfis{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));
 gap:10px;margin-top:2px}
.perfil{border:1px solid var(--linha);border-radius:7px;padding:11px 13px;
 background:var(--creme)}
.perfil>b{display:block;font:700 12.5px/1.35 var(--sans);color:var(--ink);
 margin-bottom:7px}
.perfil dl{display:grid;grid-template-columns:minmax(0,104px) minmax(0,1fr);
 gap:3px 9px;margin:0}
.perfil dt{font:400 11px/1.45 var(--sans);color:var(--t4)}
.perfil dd{margin:0;font:500 11px/1.45 var(--sans);color:var(--t2);min-width:0}
.pontos{margin:2px 0 0;padding:0 0 0 16px;display:flex;flex-direction:column;
 gap:6px}
.pontos li{font:400 12.5px/1.55 var(--sans);color:var(--t2);
 text-wrap:pretty;padding-left:2px;max-width:88ch}
.pontos li::marker{color:var(--traco)}
.numerados{margin:2px 0 0;padding:0 0 0 20px;display:flex;
 flex-direction:column;gap:8px}
.numerados li{font:400 12.5px/1.55 var(--sans);color:var(--t2)}
.numerados li::marker{font-family:var(--mono);font-size:11px;color:var(--t4)}
.numerados li b{display:block;font-weight:600;color:var(--ink)}
.numerados li span{display:block;text-wrap:pretty;max-width:88ch}
.em-falta{font-weight:400;color:var(--t6);font-style:italic}
.nota-campo{display:block;margin-top:3px;font:400 11.5px/1.45 var(--sans);
 color:var(--t5)}
.a-trazer{color:var(--azul)}
.a-trazer::before{content:'';display:inline-block;width:7px;height:7px;
 border-radius:50%;background:var(--azul);margin-right:7px;
 animation:pulsa 1s ease-in-out infinite}
@keyframes pulsa{0%,100%{opacity:1}50%{opacity:.25}}
/* A caixa preta do prazo era o melhor elemento da aplicacao e nao
   sobreviveu a composicao em dossier -- vivia na coluna da direita. O
   prazo passou a facto do cabecalho, e a barra do decorrido veio com
   ele: e a mesma conta, noutro fundo. */
.facto .conta{display:inline-block;margin-left:8px;font:600 11.5px/1 var(--sans);
 color:var(--t3)}
.facto .conta.mau{color:var(--verm)}
.facto .conta.avisa{color:var(--laranja)}
.facto .conta.ok{color:var(--verde)}
.barra-prazo{display:block;height:4px;border-radius:2px;background:var(--linha);
 margin-top:9px;overflow:hidden}
.barra-prazo i{display:block;height:100%;background:var(--traco)}
.lado-cx{padding:18px 22px}
.lado-cx .cab{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.docs{display:flex;flex-direction:column;gap:2px;margin-top:8px}
.doc{display:flex;align-items:center;gap:10px;padding:9px 0;
 border-top:1px solid var(--linha2)}
.doc a{font:500 12.5px/1.35 var(--sans);min-width:0;overflow:hidden;
 text-overflow:ellipsis;white-space:nowrap}
.doc .t{margin-left:auto;flex:none;font:400 11px/1 var(--mono);color:var(--t4)}
/* a peca que esta aberta no leitor aqui em baixo */
.doc.aberta a{color:var(--ink);font-weight:700}
.doc.aberta{position:relative}
.doc.aberta::before{content:'';position:absolute;left:-22px;top:9px;bottom:9px;
 width:3px;border-radius:2px;background:var(--azul)}

/* O leitor da peca, dentro da ficha e por baixo da lista das pecas
   (pedido do Afonso a 31/08/2026). A pagina propria /peca continua a
   existir e usa o mesmo codigo -- ver visualizador_de_peca(). */
.leitor{margin-top:16px;border:1px solid var(--linha);border-radius:8px;
 overflow:hidden;background:var(--creme)}
.leitor-cab{display:flex;align-items:center;gap:12px;padding:11px 15px;
 border-bottom:1px solid var(--linha);background:#fff}
.leitor-cab .n{flex:1;min-width:0;font:600 12.5px/1.3 var(--sans);color:var(--ink);
 overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.leitor>.nota{padding:10px 15px 0}
.leitor .filtros{margin:10px 15px;box-shadow:none}
/* Os resultados da procura sao uma frase com ligacoes no fim, nao um
   chip: reaproveitavam o .cpv-activo, que e flex, e cada <b> e cada
   "pag. N" virava uma coluna -- a frase lia-se em bocados. */
.achados{padding:10px 14px;border:1px solid var(--azul-borda);
 background:var(--azul-fundo);border-radius:8px;margin-bottom:12px;
 font:400 12.5px/1.9 var(--sans);color:var(--azul)}
.achados b{font-weight:700}
.achados a{text-decoration:underline;text-underline-offset:2px;
 white-space:nowrap;margin-right:4px}
.leitor .achados{margin:0 15px 12px}
.leitor>details.sec{margin:0 15px 15px}
.peca-folhas{padding:0 0 8px}
/* Dentro da ficha as folhas rolam na sua propria janela: 68 paginas a
   correr no meio do dossier empurravam o mercado e o historico para
   longe de mais. Na pagina propria da peca o documento e a pagina, e ai
   nao ha rolo dentro de rolo. */
.leitor .peca-folhas{padding:0 15px 15px;max-height:78vh;overflow-y:auto;
 background:var(--linha2)}
.peca-pag{display:block;width:100%;max-width:960px;margin:14px auto 0;
 border:1px solid var(--linha);border-radius:5px;background:#fff;
 box-shadow:0 1px 3px rgba(20,24,30,.08)}
.resp{display:flex;align-items:center;gap:9px;padding:9px 12px;
 border:1px solid var(--linha);border-radius:8px;background:var(--creme)}
.resp .av{width:24px;height:24px;border-radius:50%;background:var(--linha);flex:none;
 font:600 9.5px/24px var(--sans);color:var(--t3);text-align:center}
.resp input{flex:1;min-width:0;border:0;background:transparent;
 font:500 12.5px/1.4 var(--sans);color:var(--ink)}
.resp input:focus:not(:focus-visible){outline:none}
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
.quadro{display:flex;gap:14px;align-items:flex-start;overflow-x:auto;padding-bottom:14px}
/* A coluna era var(--linha2) sobre var(--papel): dois cinzentos a um
   passo um do outro, e o quadro lia-se como cartoes soltos sem colunas
   nenhumas -- justamente o unico sitio onde a coluna E a informacao. */
.coluna{flex:none;width:282px;background:var(--linha2);
 border:1px solid var(--traco);border-radius:8px;padding:12px}
/* o cabecalho em duas linhas: o nome tinha de partilhar 282px com a
   contagem e a soma, e saia "A preparar pr" */
.coluna-cab{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;
 margin-bottom:12px}
/* o nome ocupa a primeira linha inteira; a contagem fica na segunda */
.coluna-cab>form:first-child{flex:1 1 100%;min-width:0}
.fase-nome{border:0;background:transparent;font:700 13px/1.3 var(--sans);
 color:var(--ink);width:100%;padding:2px}
.fase-nome:focus{background:#fff;border-radius:4px}
.fase-nome:focus:not(:focus-visible){outline:none}
.coluna-conta{font:600 10.5px/1 var(--mono);color:var(--t3)}
/* o que a coluna pergunta, para se ver sem ter de lá pôr um cartão */
.coluna-pede{flex:1 1 100%;font:500 10.5px/1.3 var(--sans);color:var(--t4);
 letter-spacing:.01em}
/* o que a fase pede ao cartao: so aparece na coluna que o pede, e por
   isso e um bloco proprio e nao mais uma linha da meta */
.carta-campos{display:flex;flex-wrap:wrap;gap:5px;align-items:center;
 margin-top:10px;padding-top:9px;border-top:1px dashed var(--traco)}
.carta-campos label{font:600 9.5px/1 var(--sans);color:var(--t4);
 letter-spacing:.04em;text-transform:uppercase;flex:none}
.carta-campos input,.carta-campos select{font:400 11px/1.2 var(--sans);
 padding:5px 7px;border:1px solid var(--linha);border-radius:5px;
 background:#fff;color:var(--t2);flex:1;min-width:0}
.carta-campos input.curto{flex:none;width:56px}
/* numa coluna de 282px, "os três primeiros" ao lado do lugar sobrava
   um campo de 12px: leva a linha inteira */
.carta-campos input.largo{flex:1 1 100%}
.carta-campos button{cursor:pointer;font:600 10.5px/1 var(--sans);
 padding:6px 9px;border:1px solid var(--linha);border-radius:5px;
 background:#fff;color:var(--t3);flex:none}
.carta-campos button:hover{border-color:var(--azul);color:var(--azul)}
.coluna-corpo{display:flex;flex-direction:column;gap:9px;min-height:60px}
.coluna-corpo.sobre{outline:2px dashed var(--traco);outline-offset:3px;border-radius:6px}
.coluna-vazia{padding:16px 9px;border:1px dashed var(--traco);border-radius:6px;
 text-align:center;font:400 11.5px/1.4 var(--sans);color:var(--t3)}
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
 font-size:12px;line-height:1;padding:6px;margin:-6px -4px -6px 0;
 min-width:24px;min-height:24px;box-sizing:border-box}
button.etq-x:hover{opacity:1}
button.tirar{background:none;border:0;cursor:pointer;
 font:400 11px/1 var(--sans);color:var(--t6);
 padding:7px 4px;margin:-7px 0;min-height:24px;box-sizing:border-box}
button.tirar:hover{color:var(--verm)}
.etq-form input{padding:3px 7px;border-radius:4px;border:1px dashed var(--traco);
 background:transparent;font:500 10.5px/1.3 var(--sans);color:var(--t5);width:78px}
.etq-form input:focus{border-style:solid;border-color:var(--azul)}
.etq-form input:focus:not(:focus-visible){outline:none}
.carta-pe{display:flex;align-items:center;margin-top:11px;padding-top:9px;
 border-top:1px solid var(--papel)}
.carta-pe a{font:400 11px/1 var(--sans);color:var(--t6);display:inline-block;
 padding:7px 4px;margin:-7px 0;min-height:24px;box-sizing:border-box}
.carta-pe a:hover{color:var(--verm)}
.carta-pe .av{margin-left:auto;width:20px;height:20px;border-radius:50%;
 background:var(--linha);font:600 9px/20px var(--sans);color:var(--t3);text-align:center}

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
/* O dia e o eixo desta pagina e era o texto mais apagado dela: o
   numero em --t4 sobre branco, as iniciais do dia da semana em --t6. */
.cel-dia{padding:8px 0;text-align:center;border-left:1px solid var(--linha2)}
.cel-dia .s{font:500 9px/1.2 var(--sans);color:var(--t4);text-transform:lowercase}
.cel-dia .n{font:700 12px/1.3 var(--mono);color:var(--t1)}
.cel-dia .m{font:400 9px/1.3 var(--sans);color:var(--t4);text-transform:uppercase}
.cel-dia.fds{background:var(--linha2)}
.cel-dia.fds .s,.cel-dia.fds .n{color:var(--t3)}
.cel-dia.mes-novo{border-left:2px solid var(--traco)}
.cel-dia.hoje{background:var(--azul-fundo)}
.cel-dia.hoje .n,.cel-dia.hoje .s{color:var(--azul);font-weight:700}
.cel-pilula{padding:4px 3px}
/* a pilula cortava sem reticencias e lia-se "Por analis" -- e dado
   estragado, nao texto cortado (regra da casa: toda a truncagem
   visivel poe reticencias) */
.pilula{display:block;padding:6px 5px;border-radius:5px;font:600 9.5px/1.2 var(--sans);
 text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

/* indicadores */
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));
 gap:14px}
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
/* A linha de saude tem de aguentar valores de qualquer comprimento: as
   marcas de ultimo erro sao frases de 80 caracteres em mono, e com
   `flex:none` no valor a linha transbordava da caixa e o rotulo partia
   palavra a palavra a tentar dar-lhe espaco. Agora o valor encolhe,
   quebra e, se nao couber de todo, passa para a linha de baixo. */
.saude .l{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.saude .t{font:400 12px/1.45 var(--sans);color:var(--t2);flex:1 1 auto;min-width:0}
.saude .v{margin-left:auto;flex:0 1 auto;min-width:0;
 font:600 11.5px/1.5 var(--mono);color:var(--ink);text-align:right;
 word-break:break-word;overflow-wrap:anywhere}
/* legenda: diz sobre o que e que as linhas seguintes contam */
.saude .legenda{margin-top:6px}
.saude .legenda .t{font:400 11px/1.45 var(--sans);color:var(--t5);
 font-style:italic}
/* entidade sem NIF no corpus: agrupa-se pelo nome e pode ser a mesma
   empresa que outra linha */
.sem-nif{display:inline-block;margin-left:6px;padding:2px 5px;border-radius:4px;
 background:var(--linha2);color:var(--t4);font:600 9px/1.3 var(--sans);
 text-transform:uppercase;letter-spacing:.06em;vertical-align:middle}
.aviso-prop{padding:12px 16px;border:1px dashed var(--traco);border-radius:8px;
 font:400 12px/1.5 var(--sans);color:var(--t4)}

@media (max-width:1100px){
 .ind-grelha{grid-template-columns:minmax(0,1fr)}
}
"""


BASE = """<!doctype html><html lang="pt"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(titulo_aba)s</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet" media="print" onload="this.media='all'">
<noscript><link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet"></noscript>
<style>%(css)s</style></head><body>
<div class="app">
<aside>
 <div class="marca">
  <div class="logo">Radar<span>DR</span></div>
  <div class="sub">%(fontes)s</div>
  <div class="meta">%(acervo)s<br>localhost:%(porta)d</div>
 </div>
 <nav>%(nav)s</nav>
 <div class="caixa">
  <div class="r">Verificação automática</div>
  <div class="h">%(horas)s</div>
  <a class="n" href="/indicadores" title="Abrir os indicadores — a saúde completa do sistema">%(ultima)s</a>
 </div>
 <details class="sou">
  <summary><span class="av">%(iniciais)s</span>%(quem_visivel)s</summary>
  <form method="post" action="/sou">
   <input type="text" name="nome" value="%(quem)s" list="pessoas" placeholder="o teu nome">
   <button type="submit">mudar</button>
  </form>
 </details>
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

# (chave do item, etiqueta, destino, vistas agrupadas). Cinco itens de
# primeiro nivel, por ordem de uso real -- cada um e uma intencao, nao
# uma tabela (ESQUELETO §2). A rota deixou de aparecer ao lado do nome:
# era ruido de programador num painel que e para trabalhar.
#
# "Em curso" e "Mercado" agrupam duas vistas da mesma populacao
# (decisoes 11.4 e 6.1-A; a fusao das renovacoes em modo e do andamento
# 3 -- aqui so se agrupam na navegacao). A primeira vista de cada grupo
# e a que o item abre. Os Indicadores NAO constam: saem da navegacao e
# entram pela zona de estado da barra lateral (decisao 11.6-A, sem
# atalho secundario).
# A Triagem e a Pesquisa fundiram-se numa lista so a 31/08/2026, por
# decisao do Afonso depois de usar ("ambas sao a mesma coisa"): as
# abas por ver / interessados / abandonados / todos fazem o trabalho
# que as duas paginas faziam, e /anuncios redirecciona para "/".
NAV = (("anuncios", "Anúncios", "/", ()),
       ("emcurso", "Em curso", "/quadro",
        (("quadro", "Quadro", "/quadro"),
         ("calendario", "Calendário", "/calendario"))),
       ("mercado", "Mercado", "/contratos",
        (("contratos", "Contratos", "/contratos"),
         # as renovacoes fundiram-se nos contratos como modo (6.1-A);
         # a rota antiga /renovacoes redirecciona para ca
         ("renovacoes", "Renovações", "/contratos?ver=fim"))),
       ("alertas", "Alertas", "/alertas", ()))

# Que item da navegacao acende para cada pagina. As paginas mantem as
# chaves que sempre tiveram (as vistas de filtros incluidas); o item e
# hierarquia por cima delas, nao um nome novo.
ITEM_DA_PAGINA = {"anuncios": "anuncios",
                  "quadro": "emcurso", "calendario": "emcurso",
                  "contratos": "mercado", "renovacoes": "mercado",
                  "alertas": "alertas"}

# Paginas que vivem fora da navegacao, para as migalhas: os Indicadores
# alcancam-se pelo ponto da ultima verificacao na barra lateral.
PAGINAS_FORA_DA_NAV = {"indicadores": "Indicadores"}

# Onde o botao "Verificar agora" aparece: SO na lista dos anuncios
# (decisao 11.8-A, que sobrevive a fusao). O botao vai ao DR buscar
# anuncios novos e os novos aterram no por ver -- e la que o resultado
# se ve. No quadro e no calendario parecia dizer respeito ao que esta
# no ecra, e nao dizia.
PAGINAS_COM_VERIFICAR = ("anuncios",)


def migalhas_de(vista, folha=""):
    """As migalhas de uma pagina, a partir do item em que ela vive.

    Os itens sao intencoes e as paginas agrupadas sao vistas deles: o
    quadro e "Em curso › Quadro", os contratos "Mercado › Contratos" --
    deixaram de ser separadores irmaos. Uma pagina que e o proprio item
    (Triagem, Pesquisa, Alertas) mostra so o nome, e as fichas penduram
    uma folha por baixo do que ja la esta.
    """
    passos = []
    for chave, etiqueta, destino, vistas in NAV:
        if chave == vista:
            passos = [(etiqueta, destino)]
            break
        for v_chave, v_etiqueta, v_destino in vistas:
            if v_chave == vista:
                passos = [(etiqueta, destino), (v_etiqueta, v_destino)]
                break
        if passos:
            break
    if not passos:
        nome = PAGINAS_FORA_DA_NAV.get(vista)
        if not nome:
            return "<em>%s</em>" % html.escape(folha or "Radar")
        passos = [(nome, "/" + vista)]

    pedacos = []
    for etiqueta, destino in passos[:-1]:
        pedacos.append("<a href='%s'>%s</a><s>&rsaquo;</s>"
                       % (destino, html.escape(etiqueta)))
    etiqueta, destino = passos[-1]
    if folha:
        pedacos.append("<a href='%s'>%s</a><s>&rsaquo;</s><em>%s</em>"
                       % (destino, html.escape(etiqueta), html.escape(folha)))
    else:
        pedacos.append("<em>%s</em>" % html.escape(etiqueta))
    return "".join(pedacos)


def accao(destino, etiqueta, classe="bt", confirmar=""):
    """Um botao que faz POST. Tudo o que altera dados passa por aqui:
    como <a href> isto respondia a um prefetch do browser ou a qualquer
    coisa que siga links, e ha aqui accoes que mudam a base."""
    ao_submeter = (" onsubmit=\"return confirm('%s')\"" % confirmar) if confirmar else ""
    return ("<form class='accao' method='post' action='%s'%s>"
            "<button type='submit' class='%s'>%s</button></form>"
            % (destino, ao_submeter, classe, etiqueta))


def forma_abandonar(ref, classe="mini", etiqueta="abandonar", titulo=""):
    """O botao de abandonar. O motivo pergunta-se numa caixa por cima.

    Decisao do Afonso a 01/09/2026: pop-up e nao selector ao lado. Um
    selector colado ao botao punha a pergunta em cada uma das vinte
    linhas da lista antes de alguem a fazer -- e a lista e para ler
    anuncios, nao para responder a vinte perguntas por pagina.

    Continua a ser um `<form>` que faz POST: o JS intercepta o submit e
    abre a caixa. **Sem JS o pedido segue** e o servidor recusa por
    falta de motivo, com o aviso a dizer porque -- e degradacao a dizer
    o que se passa, nao um botao morto.
    """
    return ("<form class='accao abandonar-js' method='post' "
            "action='/estado/%s/descartado' data-titulo='%s'>"
            "<button type='submit' class='%s'>%s</button></form>"
            % (ref, html.escape(titulo or ref, quote=True), classe, etiqueta))


# A caixa e UMA por pagina, partilhada por todos os botoes: vinte copias
# do mesmo dialogo numa lista de vinte linhas seria o mesmo erro dos
# vinte selectores, com mais HTML.
def caixa_de_abandono():
    """O <dialog> do motivo, mais o JS que o abre. Vai nas paginas que
    tenham botao de abandonar (a lista e a ficha)."""
    escolhas = "".join(
        "<label><input type='radio' name='motivo' value='%s' required>"
        "<span>%s</span></label>"
        % (html.escape(m, quote=True), html.escape(m))
        for m in MOTIVOS_ABANDONO)
    return ("<dialog class='modal' id='dlg-abandonar'>"
            "<form method='post' class='accao' id='form-abandonar'>"
            "<h3>Abandonar este anúncio</h3>"
            "<p class='alvo' id='dlg-abandonar-alvo'></p>"
            "<p class='nota'>Não apaga nada: fica nos Abandonados e "
            "pode ser reposto. O motivo é para daqui a um mês se saber "
            "porquê.</p>"
            "<div class='escolhas'>%s</div>"
            "<div class='modal-pe'>"
            "<button type='button' id='dlg-abandonar-nao'>Cancelar</button>"
            "<button type='submit'>Abandonar</button>"
            "</div></form></dialog>"
            "<script>\n"
            "(function () {\n"
            "  var d = document.getElementById('dlg-abandonar');\n"
            "  if (!d || !d.showModal) return;   // sem <dialog>, o POST segue\n"
            "  var f = document.getElementById('form-abandonar');\n"
            "  document.addEventListener('submit', function (e) {\n"
            "    var origem = e.target;\n"
            "    if (!origem.classList || !origem.classList.contains('abandonar-js')) return;\n"
            "    e.preventDefault();\n"
            "    f.action = origem.action;\n"
            "    document.getElementById('dlg-abandonar-alvo').textContent =\n"
            "        origem.dataset.titulo || '';\n"
            "    f.querySelectorAll(\"input[name='motivo']\").forEach(\n"
            "        function (r) { r.checked = false; });\n"
            "    d.showModal();\n"
            "  }, true);\n"
            "  document.getElementById('dlg-abandonar-nao').addEventListener(\n"
            "      'click', function () { d.close(); });\n"
            "})();\n"
            "</script>" % escolhas)


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

    # As vistas agrupadas so se mostram dentro do item aberto: a barra
    # tem cinco itens exactos (decisao 11.6-A), e e ao entrar em "Em
    # curso" ou "Mercado" que as duas vistas de cada um aparecem.
    item_activo = ITEM_DA_PAGINA.get(activo)
    itens = []
    for chave, etiqueta, destino, vistas in NAV:
        no_item = chave == item_activo
        itens.append("<a class='%s' href='%s'><b>%s</b></a>"
                     % ("on" if no_item else "", destino,
                        html.escape(etiqueta)))
        if no_item:
            for v_chave, v_etiqueta, v_destino in vistas:
                itens.append("<a class='sub %s' href='%s'><b>%s</b></a>"
                             % ("on" if v_chave == activo else "",
                                v_destino, html.escape(v_etiqueta)))

    # O ponto verde/vermelho vive aqui, na barra lateral, e nao num rodape
    # a repetir a mesma coisa no fim de cada lista. Eram as mesmas tres
    # informacoes duas vezes no mesmo ecra.
    mensagem = le_marca("ultima_mensagem", "ainda não verificou")
    quando = le_marca("ultima_verificacao", "nunca")
    bom = le_marca("ultima_ok", "") != "0"
    # Os pontos vivem sobre a barra escura, onde o contraste conta ao
    # contrario: o verde e o vermelho da paleta clara desapareciam la.
    ultima = (("<span class='ponto' style='background:%s'></span>"
               "última: %s &mdash; %s"
               % ("var(--ok-claro)" if bom else "var(--mau-claro)",
                  html.escape(data_hora_pt(quando)), html.escape(mensagem)))
              if quando != "nunca" else "ainda não verificou")
    a_verificar = verificacao_a_correr()
    if a_verificar:
        ultima = ("<span class='ponto pulsa' style='background:var(--coral)'></span>"
                  "a verificar agora &mdash; %s" % html.escape(a_verificar))

    if not migalhas:
        migalhas = migalhas_de(activo)

    # Aviso de uma accao acabada de fazer, passado no proprio
    # redireccionamento. Nao vai para a base: e da vez, nao do sistema --
    # e assim nao se confunde "peças trazidas" com "verificação correu bem".
    texto_aviso = (request.args.get("aviso") or "").strip()
    desfazer = (request.args.get("desfazer") or "").strip()
    aviso = ""
    if texto_aviso:
        # O "desfazer" e a segunda metade do aviso (UX-Auditoria.md,
        # 02/09/2026): triar a linha errada numa lista de vinte com dois
        # botoes por linha e o erro mais facil de cometer, e ate aqui o
        # cartao desaparecia sem uma palavra -- o caminho de volta era ir
        # a outra aba procura-lo. So se aceita um caminho de estado, nao
        # um endereco qualquer vindo da query string.
        volta = ""
        if desfazer.startswith("/estado/"):
            volta = ("<form class='accao desfazer' method='post' action='%s'>"
                     "<button type='submit' class='mini'>desfazer</button>"
                     "</form>" % html.escape(desfazer, quote=True))
        aviso = "<div class='flash'>%s%s</div>" % (html.escape(texto_aviso), volta)

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
        # Uma contagem por linha: na barra estreita cabem 20 caracteres,
        # e "66 205 anuncios · 1 363 300 contratos" numa linha so partia
        # em qualquer sitio menos nos que interessam.
        "acervo": ("%s anúncios<br>%s contratos"
                   % (mil_pt(total), mil_pt(n_corpus)) if n_corpus
                   else "%s anúncios" % mil_pt(total)),
        "nav": "".join(itens),
        "horas": " &middot; ".join(cfg["horas_verificacao"]),
        "ultima": ultima,
        "iniciais": _iniciais(quem),
        "quem": html.escape(quem, quote=True),
        "quem_visivel": html.escape(quem) if quem else "quem está a trabalhar?",
        "migalhas": migalhas,
        "titulo": html.escape(titulo),
        "subtitulo": subtitulo,
        "conteudo": conteudo,
        "abas": abas or "<div class='vazio-topo'></div>",
        "aviso": aviso,
        # "Verificar agora" vai ao DR buscar anuncios novos, e os novos
        # aterram na Triagem: e o UNICO sitio com o botao (11.8-A). No
        # quadro e no calendario parecia dizer respeito ao que esta no
        # ecra; nos contratos ja aparecera ao lado do "Actualizar
        # contratos" a dizer outra coisa parecida.
        "accoes_topo": (
            ("<span class='a-correr'>a verificar&hellip;</span>"
             if a_verificar else accao("/verificar", "Verificar agora"))
            if activo in PAGINAS_COM_VERIFICAR else ""),
        "lista_pessoas": "".join("<option value='%s'>" % html.escape(n, quote=True)
                                 for n in listar_pessoas()),
        # Enquanto a verificacao correr, a pagina volta a pedir-se
        # sozinha -- o mesmo que a actualizacao do corpus ja fazia. A
        # thread poe sempre um estado terminal, por isso isto para.
        "script": script + ("<script>setTimeout(function(){location.reload()},"
                            "5000)</script>" if a_verificar else ""),
    }


# Tecto do CSV de contratos. Um filtro largo pode apanhar centenas de
# milhares de linhas, e a folha de calculo do outro lado tambem tem
# limites -- mais vale um ficheiro que abre do que um que rebenta.
TECTO_CSV = 50000

# Quantas linhas a lista mostra de uma vez. E um limite de apresentacao,
# nao da base: o filtro apanha o que apanhar, a pagina mostra 20 e o
# resto alcanca-se pelo paginador.
POR_PAGINA_LISTA = 20

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


def etiqueta_prazo(prazo, urgente=None):
    """(texto, classe) para o distintivo de prazo. Verde folgado, amarelo
    dentro da janela do urgente, vermelho expirado ou a acabar hoje.

    O `urgente` e essa janela em dias; sem ele le-se de dias_urgente().
    Esteve aqui um 7 escrito a mao com o filtro a 10: um prazo a 9 dias
    saia verde ("folgado") na lista e na ficha e contava como urgente no
    filtro, no cartao dos indicadores e nos avisos -- o ecra a mostrar um
    numero que a ligacao dele nao dava. A janela e UMA so, e vem daqui.

    Quem chama em ciclo (a lista, o quadro, o calendario) le a janela uma
    vez e passa-a: dias_urgente() abre o config.json a cada chamada, e a
    lista tem uma linha por anuncio."""
    dias, passou = dias_restantes(prazo)
    if dias is None:
        return "", ""
    if passou:
        return "prazo expirado", "mau"
    if dias == 0:
        return "termina hoje", "mau"
    if urgente is None:
        urgente = dias_urgente()
    return conta_dias(dias), ("avisa" if dias <= urgente else "ok")


def corta(texto, tecto):
    """Corta e diz que cortou. Sem as reticencias, um objecto cortado a
    meio de palavra ("...suporte do Hardware Oracle onde residem as Base
    de Dado") lia-se como dado estragado e nao como texto cortado."""
    texto = texto or ""
    return texto if len(texto) <= tecto else texto[:tecto].rstrip() + "…"


def linha(a, vista="", urgente=None):
    """Uma linha da lista. O `vista` e o estado que a lista esta a
    mostrar: no separador "Por ver" a etiqueta "por ver" e sempre
    verdade, portanto nao diz nada e so disputa espaco com o CPV, a
    plataforma e o prazo, que sao os que se leem. O `urgente` e a janela
    do urgente, lida uma vez por pedido por quem faz o ciclo."""
    # A data de publicacao passou de bloco proprio a uma nota ao lado da
    # entidade. Era uma coluna de 64px a repetir "31 AGO" vinte vezes na
    # lista de um dia -- peso de titulo para o dado que menos decide,
    # enquanto o prazo, que decide tudo, era uma etiqueta de 10px.
    try:
        data = datetime.strptime(a["data_pub"], "%Y-%m-%d")
        publicado = "publicado %02d %s" % (data.day, MESES[data.month - 1])
    except ValueError:
        publicado = ""

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
    # O prazo sai das etiquetas e sobe a numero forte na coluna da
    # direita: e o que manda em "concorro ou nao", e no meio das outras
    # tags lia-se ao mesmo nivel do codigo CPV.
    texto_prazo, classe_prazo = etiqueta_prazo(a["prazo"], urgente)
    prazo_html = ("<div class='item-prazo %s'>%s</div>"
                  % (classe_prazo, texto_prazo)) if texto_prazo else ""
    if a["estado"] != vista:
        rotulo_estado = {"novo": "por ver", "interessa": "interessa",
                         "descartado": "abandonado"}.get(a["estado"], a["estado"])
        classe_estado = {"interessa": "ok",
                         "descartado": ""}.get(a["estado"], "info")
        tags.append("<span class='tag %s'>%s</span>"
                    % (classe_estado, rotulo_estado))
    # Porque e que foi abandonado, na propria linha: e o que faz a aba
    # dos abandonados valer alguma coisa passado um mes. Os que caem la
    # por terem expirado nao tem motivo -- e nao se lhes inventa um.
    if a["estado"] == "descartado" and _valor(a, "motivo"):
        tags.append("<span class='tag'>%s</span>"
                    % html.escape(a["motivo"]))

    preco = ("<div class='item-preco'>%s</div>" % html.escape(a["preco_base"])) \
        if a["preco_base"] else ""

    # Os botoes dependem do estado em que o anuncio esta. Eram sempre os
    # mesmos dois: em Descartados nao havia forma nenhuma de repor um
    # descarte (o caminho era marcar interessa e depois "tirar do quadro"),
    # e em Interessa o botao "interessa" continuava la e nao era inocuo --
    # cada clique voltava a pedir as pecas e a descarrega-las outra vez.
    botoes = []
    if a["estado"] != "interessa":
        botoes.append(accao("/estado/%s/interessa" % a["ref"],
                            "interessa", "mini verde"))
    if a["estado"] != "descartado":
        botoes.append(forma_abandonar(a["ref"], titulo=a["titulo"] or ""))
    if a["estado"] != "novo":
        botoes.append(accao("/estado/%s/novo" % a["ref"],
                            "repor por ver", "mini"))

    return (
        "<div class='item' id='a-%s'>"
        "<div class='item-corpo'>"
        "<a href='/anuncio/%s' class='item-titulo'>%s</a>"
        "<div class='item-entidade'>%s%s</div>"
        "<div class='item-meta'>%s</div></div>"
        "<div class='item-lado'>%s%s<div class='item-accoes'>%s</div></div></div>"
        % (html.escape(a["ref"].replace("/", "-"), quote=True),
           a["ref"], html.escape(corta(a["titulo"], 190)),
           html.escape(a["entidade"] or ""),
           (" <span class='quando'>&middot; %s</span>" % publicado)
           if publicado else "",
           "".join(tags), prazo_html, preco, "".join(botoes)))


LISTA_JS = """<script>
// Triar e o trabalho: cada "interessa"/"descartar" e um POST com
// redireccionamento, e a pagina voltava sempre ao topo. No decimo oitavo
// item da lista isso e descer tudo outra vez -- e como o anuncio triado
// desaparece do separador "Por ver", os de baixo sobem uma posicao e o
// clique seguinte cai no anuncio errado.
(function () {
  var chave = 'radar-pos:' + location.pathname + location.search;
  document.addEventListener('submit', function (e) {
    if (e.target && e.target.classList && e.target.classList.contains('accao')) {
      try { sessionStorage.setItem(chave, String(window.scrollY)); } catch (x) {}
    }
  }, true);
  var guardado = null;
  try { guardado = sessionStorage.getItem(chave); } catch (x) {}
  if (guardado !== null) {
    try { sessionStorage.removeItem(chave); } catch (x) {}
    window.scrollTo(0, parseInt(guardado, 10) || 0);
  }
})();
</script>"""


ARVORE_JS = """<script>
// ARV_SEL e o que se escolheu; ARV_EXC e o que se tirou de dentro do
// escolhido. As duas juntas sao o par de campos do filtro (cpv e
// cpv_excl) -- a arvore escreve nos dois. Antes so escrevia no
// primeiro, e por isso um filho de uma divisao marcada tinha a caixa
// trancada: marcar o 72 obrigava a levar o 72 inteiro. Quem quer o 72
// sem dois ramos ficava sem forma de o dizer, e tirar o 72 perdia os
// anuncios que so trazem o codigo da divisao.
var ARV_DADOS = null, ARV_SEL = new Set(), ARV_EXC = new Set(),
    ARV_FILHOS = {}, ARV_PAI = {}, ARV_CHK = {};

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
  var porCodigo = {}, filhos = {}, pais = {}, raizes = [];
  dados.forEach(function(d) { porCodigo[d.codigo8] = d; });
  dados.forEach(function(d) {
    var nivel = nivelSignificativo(d.codigo8), pai = null;
    for (var L = nivel - 1; L >= 2; L--) {
      var candidato = d.codigo8.slice(0, L) + '0'.repeat(8 - L);
      if (candidato !== d.codigo8 && porCodigo[candidato]) { pai = candidato; break; }
    }
    if (pai) { (filhos[pai] = filhos[pai] || []).push(d.codigo8); pais[d.codigo8] = pai; }
    else { raizes.push(d.codigo8); }
  });
  raizes.sort();
  Object.keys(filhos).forEach(function(k) { filhos[k].sort(); });
  ARV_FILHOS = filhos;
  ARV_PAI = pais;

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
  var abrir = Array.from(ARV_SEL).concat(Array.from(ARV_EXC));
  abrir.forEach(function(cod) {
    if (!ARV_CHK[cod]) return;
    // abrir os antepassados: marcado dentro de um <details> fechado nao
    // se ve, e o que nao se ve parece nao estar la
    var no = ARV_CHK[cod].closest('.no-envolve');
    while (no) {
      if (no.tagName === 'DETAILS') no.open = true;
      no = no.parentElement ? no.parentElement.closest('.no-envolve') : null;
    }
  });
  arvorePintar();
}

function arvoreSemear() {
  // O filtro em uso e a verdade de onde a arvore parte. Guarda-se tudo o
  // que la esta, ate o que nao e codigo (o filtro tambem aceita palavras):
  // assim "Aplicar" nao deita fora o que a arvore nao sabe desenhar.
  var campo = document.getElementById('filtro-cpv');
  if (campo) {
    campo.value.split('|').forEach(function(p) {
      p = p.trim();
      if (p) ARV_SEL.add(p);
    });
  }
  var fora = document.getElementById('filtro-cpv-excl');
  if (fora) {
    fora.value.split('|').forEach(function(p) {
      p = p.trim();
      if (p) ARV_EXC.add(p);
    });
  }
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
  var fs = document.createElement('span');
  fs.className = 'fora'; fs.textContent = '';
  resumo.appendChild(fs);
  // Um codigo a zero escolhe-se na mesma (pode interessar no outro
  // separador), mas esbatido: filtrar a arvore por "software" enterrava
  // os ramos com anuncios no meio de dezenas de (0).
  if (!total[cod]) resumo.classList.add('zero');
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

function arvoreAntepassados(cod) {
  var fora = [], p = ARV_PAI[cod];
  while (p) { fora.push(p); p = ARV_PAI[p]; }
  return fora;
}

function arvoreEstado(cod) {
  // Quem decide se um codigo esta dentro do filtro e o antepassado mais
  // proximo (ou o proprio) que apareca numa das duas listas: se estiver
  // nos escolhidos, entra; se estiver nos tirados, fica de fora.
  if (ARV_EXC.has(cod)) return 'fora';
  if (ARV_SEL.has(cod)) return 'dentro';
  var caminho = arvoreAntepassados(cod);
  for (var i = 0; i < caminho.length; i++) {
    if (ARV_EXC.has(caminho[i])) return 'fora';
    if (ARV_SEL.has(caminho[i])) return 'dentro';
  }
  return 'fora';
}

function arvoreDesexcluir(cod) {
  // Tira `cod` (e o que tem por baixo) das exclusoes. Se quem estiver
  // excluido for um ANTEPASSADO, a exclusao empurra-se para baixo:
  // exclui-se cada irmao do caminho, e assim volta este ramo sem voltar
  // o resto. E o unico modo de o par (cpv, cpv_excl) exprimir o que a
  // arvore mostra -- o filtro sabe somar e sabe subtrair uma vez, nao
  // sabe alternar.
  ARV_EXC.delete(cod);
  arvoreDescendentes(cod).forEach(function(f) { ARV_EXC.delete(f); });
  var caminho = arvoreAntepassados(cod), abaixo = cod;
  for (var i = 0; i < caminho.length; i++) {
    var a = caminho[i];
    if (ARV_EXC.has(a)) {
      ARV_EXC.delete(a);
      (ARV_FILHOS[a] || []).forEach(function(f) {
        if (f !== abaixo) ARV_EXC.add(f);
      });
    }
    abaixo = a;
  }
}

function arvoreMudou(cod, marcado) {
  // ARV_SEL guarda so o que foi marcado directamente: o filtro ja apanha
  // os descendentes com o codigo do grupo (zeros a direita tirados no
  // servidor), nao vale a pena mandar cada um na URL. ARV_EXC guarda o
  // que se tirou de dentro desses grupos.
  if (marcado) {
    arvoreDesexcluir(cod);
    if (arvoreEstado(cod) !== 'dentro') {
      ARV_SEL.add(cod);
      // marcar a divisao por cima torna o filho redundante: o codigo do
      // grupo ja o apanha, e deixa-lo escrito enchia a URL de ruido
      arvoreDescendentes(cod).forEach(function(f) { ARV_SEL.delete(f); });
    }
  } else {
    // Ao desmarcar tiram-se tambem os descendentes do conjunto. Sem
    // isto, marcar 72610000, marcar a divisao 72 por cima e desmarcar a
    // divisao deixava a arvore inteira em branco com o chip a dizer "1
    // seleccionado" -- e "Aplicar" filtrava por um codigo que nao
    // estava marcado em lado nenhum.
    ARV_SEL.delete(cod);
    arvoreDescendentes(cod).forEach(function(f) {
      ARV_SEL.delete(f);
      ARV_EXC.delete(f);
    });
    // desmarcar por dentro de um grupo marcado nao apaga o grupo: tira
    // este ramo, que e o que o Afonso pediu -- "escolher o 72 e tirar um
    // ou outro que nao faca sentido"
    if (arvoreEstado(cod) === 'dentro') ARV_EXC.add(cod);
  }
  arvorePintar();
}

function arvorePintar() {
  // As caixas sao um desenho do estado, nao o estado: redesenham-se
  // todas a cada mudanca. Com o estado espalhado pelas caixas, um
  // descendente marcado "so para se ver" acabava dentro do filtro.
  Object.keys(ARV_CHK).forEach(function(cod) {
    var dentro = arvoreEstado(cod) === 'dentro';
    ARV_CHK[cod].checked = dentro;
    ARV_CHK[cod].title = ARV_EXC.has(cod)
        ? 'tirado à mão de dentro de um grupo marcado acima'
        : '';
    var resumo = ARV_CHK[cod].parentElement;
    if (!resumo) return;
    resumo.classList.toggle('excluido', ARV_EXC.has(cod));
    var etq = resumo.querySelector('.fora');
    if (etq) etq.textContent = ARV_EXC.has(cod) ? 'tirado' : '';
  });
  arvoreChip();
}

function arvoreChip() {
  var chip = document.getElementById('arvore-chip');
  if (!chip) return;
  var n = ARV_SEL.size, f = ARV_EXC.size;
  var texto = n ? (n + (n === 1 ? ' seleccionado' : ' seleccionados'))
                : 'nenhum seleccionado';
  if (f) texto += ' · ' + f + (f === 1 ? ' tirado' : ' tirados');
  chip.textContent = texto;
}

function arvoreAplicar() {
  var campo = document.getElementById('filtro-cpv');
  campo.value = Array.from(ARV_SEL).join('|');
  // O que se tirou vai para o campo de excluir CPV, que e o mesmo que
  // se escreve a mao -- uma so leitura no servidor, nao duas.
  var fora = document.getElementById('filtro-cpv-excl');
  if (fora) fora.value = Array.from(ARV_EXC).join('|');
  // Numa lista, aplicar e pesquisar logo. Num formulario que ainda esta
  // a ser preenchido -- o "novo filtro" dos alertas -- submeter aqui
  // mandava o formulario sem o nome, e a escolha do CPV nao dava nada.
  var det = document.querySelector('details.arvore');
  if (det && det.dataset.submeter === 'nao') {
    det.open = false;
    return;
  }
  campo.form.submit();
}

function arvoreLimpar() {
  ARV_SEL.clear();
  ARV_EXC.clear();
  arvorePintar();
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


def sem_pagina(args, base="/", **muda):
    """Liga da lista com os filtros de agora. Mexer num filtro volta a
    pagina 1: a pagina 7 do filtro anterior nao existe no novo. O `base`
    e a rota da lista: a mesma funcao serve a Triagem ("/") e a
    Pesquisa ("/anuncios")."""
    novos = args_da_lista(args, **muda)
    return base + "?" + urlencode(novos) if novos else base


def href_limpar(rota, estado=None):
    """O "limpar" tira o filtro, nao muda de separador.

    Apontava sempre para "/": limpar a pesquisa em Descartados atirava
    para "Por ver". O estado e o separador onde se esta, nao parte do
    filtro que se quer tirar. `None` e paginas sem separadores."""
    if estado is None or estado == "novo":
        return rota
    return rota + "?" + urlencode([("estado", estado)])


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

    # Caixa para saltar. A barra mostra uma janela a volta da pagina
    # actual, portanto sem isto a unica forma de chegar ao meio de 3300
    # paginas era clicar 1650 vezes ou apertar o filtro.
    if paginas > 5:
        escondidos = "".join(
            "<input type='hidden' name='%s' value='%s'>"
            % (html.escape(str(k), quote=True), html.escape(str(v), quote=True))
            for k, v in args_da_lista(args).items())
        pecas.append(
            "<form class='ir-pagina' method='get' action='%s'>%s"
            "<label for='ir-pag'>ir para</label>"
            "<input id='ir-pag' type='number' name='pag' min='1' max='%d' "
            "value='%d'><button type='submit'>ir</button></form>"
            % (base, escondidos, paginas, pagina))
    return "<div class='paginas'>" + "".join(pecas) + "</div>"


def com_recorte(onde, valores, frag, vals):
    """Junta um fragmento de recorte POR CIMA do que condicoes() deu.

    O recorte e da PAGINA (as abas da lista de anuncios), nunca do
    motor: condicoes() serve tambem os alertas (registar_alertas) e os
    filtros guardados, e um recorte la dentro fazia um alerta deixar de
    ver, em silencio, tudo o que hoje ve. Nao o acrescentes a
    condicoes().
    """
    if not frag:
        return onde, valores
    if onde:
        return onde + " AND (" + frag + ")", valores + vals
    return " WHERE (" + frag + ")", valores + vals


def condicao_da_aba(estado, hoje=None, cfg=None):
    """(fragmento, valores) do que cada aba da lista mostra.

    Decisao do Afonso a 31/08/2026, depois de usar, a substituir a
    Triagem e a Pesquisa separadas (11.2-A/11.5-B revistas por ele):
    UMA lista, e "o que ja nao e possivel responder" conta como
    abandonado. As abas:

    - por ver ('novo'): por decidir E ainda respondivel -- prazo
      aberto; sem prazo lido, vale a data de publicacao dentro de
      detalhe_dias (entre publicacao e prazo vao ~18 dias em media, 60
      e folga -- e e a mesma janela que a rotina le).
    - interessados: TODOS os interessa. Um interessa com prazo passado
      e trabalho em curso (proposta entregue, a aguardar decisao) e
      nao se esconde por expirar -- regra antiga da casa.
    - abandonados ('descartado'): os descartados a mao MAIS os por ver
      que ja nao sao respondiveis. Nada muda na base: e recorte de
      leitura, e por isso um expirado que seja rectificado com prazo
      novo volta sozinho ao por ver.
    - todos (""): sem recorte.

    Aplica-se por cima de condicoes() com com_recorte() -- o motor
    nunca leva isto (alertas!).
    """
    if estado == "interessa":
        return "estado = ?", ["interessa"]
    if not estado:
        return "", []
    hoje = hoje or datetime.now().date()
    cfg = ler_config() if cfg is None else cfg
    try:
        dias = int(cfg.get("detalhe_dias", 60)) or 60
    except (TypeError, ValueError):
        dias = 60
    corte = (hoje - timedelta(days=dias)).isoformat()
    vivo = ("((prazo IS NOT NULL AND prazo != '' AND prazo >= ?) OR "
            "(COALESCE(prazo, '') = '' AND data_pub >= ?))")
    if estado == "novo":
        return "estado = 'novo' AND " + vivo, [hoje.isoformat(), corte]
    if estado == "descartado":
        return ("(estado = 'descartado' OR (estado = 'novo' AND NOT "
                + vivo + "))"), [hoje.isoformat(), corte]
    return "estado = ?", [estado]


def interesse_definido(cfg=None):
    """(ligado, cpv, cpv a tirar) do interesse. Le so o config.json."""
    cfg = ler_config() if cfg is None else cfg
    return (bool(cfg.get("interesse_activo")),
            (cfg.get("interesse_cpv") or "").strip(),
            (cfg.get("interesse_cpv_excl") or "").strip())


def condicao_do_interesse(args=None, cfg=None):
    """(fragmento, valores) do INTERESSE: o recorte permanente da lista
    de anuncios, por CPV, definido em Alertas › Interesse.

    Decisao do Afonso a 01/09/2026: a lista de anuncios e para ver o que
    a casa faz, nao o que o Diario da Republica publica. Um filtro
    guardado nao servia -- esquece-se de o pôr e volta tudo; e um filtro
    a mais na barra e um filtro que se apaga sem querer.

    E recorte de PAGINA, como as abas: entra por com_recorte() e **nao**
    por condicoes(). O motor serve tambem os alertas e os filtros
    guardados, e um interesse la dentro cegava-os em silencio -- um
    alerta deixaria de ver o que ve hoje sem ninguem lhe ter tocado.

    O `?interesse=nao` levanta-o para o pedido em curso: e a porta de
    saida, e a lista di-lo por cima de si mesma. Sem interesse definido,
    ou desligado, nao ha recorte nenhum.
    """
    args = request.args if args is None else args
    if (args.get("interesse") or "").strip() == "nao":
        return "", []
    ligado, dentro, fora = interesse_definido(cfg)
    if not ligado:
        return "", []
    frag, vals = fragmento_cpv(dentro)
    if not frag:
        # interesse ligado mas por definir: nao esconde nada. Um ecra em
        # branco sem se ter escolhido codigo nenhum le-se como avaria.
        return "", []
    frag_fora, vals_fora = fragmento_cpv(fora, coluna="COALESCE(cpv,'')")
    if frag_fora and frag_fora != "1=0":
        return ("(%s) AND NOT (%s)" % (frag, frag_fora), vals + vals_fora)
    return frag, vals


def recorte_da_lista(estado, cfg=None):
    """(fragmento, valores) do que a lista de anuncios mostra: a aba MAIS
    o interesse.

    Num sitio so, de proposito. O recorte aplica-se em quatro consultas
    da mesma pagina -- a lista, a contagem de cada aba, o selector das
    plataformas e o total do filtro -- e um numero que conte com outro
    recorte e um numero que abre uma lista diferente da que promete.

    O `cfg` passa-se de fora para o config.json se abrir UMA vez por
    pedido: as duas condicoes leem-no, sao sete chamadas por lista, e
    isto corre de uma pen a 8,7 ms por ficheiro pequeno a frio.
    """
    cfg = ler_config() if cfg is None else cfg
    frag_a, vals_a = condicao_da_aba(estado, cfg=cfg)
    frag_i, vals_i = condicao_do_interesse(cfg=cfg)
    if frag_a and frag_i:
        return "(%s) AND (%s)" % (frag_a, frag_i), vals_a + vals_i
    return (frag_a or frag_i), (vals_a if frag_a else vals_i)


@app.route("/")
def painel():
    """A lista dos anuncios: triagem e acervo na MESMA pagina, com as
    abas a apartar (por ver / interessados / abandonados / todos)."""
    return _lista_de_anuncios()


@app.route("/anuncios")
def pesquisa():
    """A Pesquisa fundiu-se na lista unica (decisao do Afonso a
    31/08/2026). A rota redirecciona com o filtro atras, para nao
    partir filtros guardados nem ligacoes antigas. O `arquivo` do
    interruptor antigo cai: deixou de haver janela para desligar."""
    novos = args_da_lista(request.args)
    novos.pop("arquivo", None)
    return redirect("/?" + urlencode(novos) if novos else "/")


def _lista_de_anuncios():
    """A lista de anuncios, uma so (decisao do Afonso a 31/08/2026:
    "a triagem e a pesquisa nao fazem sentido estarem separados").

    O estado da aba NAO vai ao motor: tira-se dos args e aplica-se por
    cima como recorte (condicao_da_aba), porque a aba dos abandonados
    e uma uniao (descartados + expirados) que um simples estado=? nao
    diz. A identidade dos filtros guardados nao muda: o `estado`
    continua na consulta canonica como sempre.
    """
    rota = "/"
    # UMA leitura do config.json por pedido: as condicoes da aba e do
    # interesse leem-no as duas, e sao sete chamadas nesta funcao.
    cfg = ler_config()
    estado_da_aba = request.args.get("estado")
    estado_da_aba = "novo" if estado_da_aba is None else estado_da_aba.strip()
    onde, valores = com_recorte(
        *condicoes(args_da_lista(request.args, estado="")),
        *recorte_da_lista(estado_da_aba, cfg))
    with liga() as c:
        # Com paginas de 20 a contagem deixa de ser dispensavel: e ela que
        # diz quantas paginas ha. Faz-se sempre, antes da consulta das
        # linhas, para se poder segurar a pagina pedida dentro do que
        # existe -- pedir a pagina 900 de 12 devolvia uma lista vazia.
        correspondem = c.execute("SELECT COUNT(*) n FROM anuncios" + onde,
                                 valores).fetchone()["n"]
        paginas = max(1, -(-correspondem // POR_PAGINA_LISTA))
        pagina = min(max(1, pagina_pedida(request.args)), paginas)
        linhas = c.execute("SELECT * FROM anuncios" + onde +
                           " ORDER BY data_pub DESC, ref DESC LIMIT ? OFFSET ?",
                           valores + [POR_PAGINA_LISTA,
                                      (pagina - 1) * POR_PAGINA_LISTA]).fetchall()
        # As abas contam DENTRO do filtro. Contavam a base inteira: com
        # CPV 72 posto diziam "Por ver 66 007 · Todos 66 009" por cima
        # de uma lista de 234, e as proprias ligacoes levavam o filtro
        # atras -- o numero e o destino do mesmo botao discordavam.
        # Cada aba conta com o SEU recorte (condicao_da_aba): o numero
        # tem de abrir exactamente a lista que o confirma.
        onde_sem_estado, val_sem_estado = condicoes(
            args_da_lista(request.args, estado=""))
        contas = {}
        for e in ("novo", "interessa", "descartado", ""):
            onde_aba, val_aba = com_recorte(onde_sem_estado,
                                            val_sem_estado,
                                            *recorte_da_lista(e, cfg))
            contas[e] = c.execute(
                "SELECT COUNT(*) n FROM anuncios" + onde_aba,
                val_aba).fetchone()["n"]
        # Quanto e que o interesse esta a tapar, nesta aba e dentro deste
        # filtro. Um recorte permanente que nao diga quanto esconde e um
        # recorte que se esquece: passado um mes, "nao ha nada" tanto
        # pode ser "nao entrou nada" como "nao entrou nada disto", e
        # nada no ecra separa os dois.
        escondidos_interesse = 0
        if condicao_do_interesse(cfg=cfg)[0]:
            onde_livre, val_livre = com_recorte(
                onde_sem_estado, val_sem_estado,
                *condicao_da_aba(estado_da_aba, cfg=cfg))
            escondidos_interesse = c.execute(
                "SELECT COUNT(*) n FROM anuncios" + onde_livre,
                val_livre).fetchone()["n"] - correspondem
        total = c.execute("SELECT COUNT(*) n FROM anuncios").fetchone()["n"]
        porler = c.execute("SELECT COUNT(*) n FROM anuncios "
                           "WHERE detalhe_lido=0").fetchone()["n"]
        n_cpv = c.execute("SELECT COUNT(*) n FROM cpv_dict").fetchone()["n"]
        # A lista das plataformas que existem vem da base toda -- para se
        # poder MUDAR de plataforma sem sair do filtro -- mas os numeros
        # contam dentro do filtro, sem a parte da plataforma, como os
        # separadores. Era o unico controlo do ecra com outra aritmetica:
        # com um CPV posto e a lista em 118, oferecia "acingov (2 637)".
        plataformas = c.execute(
            "SELECT COALESCE(NULLIF(plataforma,''),?) p, COUNT(*) n "
            "FROM anuncios WHERE detalhe_lido=1 GROUP BY p ORDER BY n DESC",
            (SEM_PLATAFORMA,)).fetchall()
        onde_sem_plat, val_sem_plat = com_recorte(
            *condicoes(args_da_lista(request.args, plat="", estado="")),
            *recorte_da_lista(estado_da_aba, cfg))
        no_filtro = c.execute("SELECT COUNT(*) n FROM anuncios"
                              + onde_sem_plat, val_sem_plat).fetchone()["n"]
        porler_filtro = c.execute(
            "SELECT COUNT(*) n FROM anuncios" + onde_sem_plat +
            (" AND" if onde_sem_plat else " WHERE") + " detalhe_lido=0",
            val_sem_plat).fetchone()["n"]
        conta_plat = {r["p"]: r["n"] for r in c.execute(
            "SELECT COALESCE(NULLIF(plataforma,''),?) p, COUNT(*) n "
            "FROM anuncios" + onde_sem_plat +
            (" AND" if onde_sem_plat else " WHERE") + " detalhe_lido=1 "
            "GROUP BY p", [SEM_PLATAFORMA] + val_sem_plat)}

    mil = mil_pt

    # Os rotulos sao os que o Afonso pediu a 31/08/2026: por ver ·
    # interessados · abandonados · todos. "Abandonados" junta os
    # descartados a mao com os que expiraram por ver -- e recorte de
    # leitura (condicao_da_aba), a base nao muda.
    estado_actual = estado_da_aba
    abas = ["<div class='abas'>"]
    for valor, etiqueta, quantos in (
            ("novo", "Por ver", contas["novo"]),
            ("interessa", "Interessados", contas["interessa"]),
            ("descartado", "Abandonados", contas["descartado"]),
            ("", "Todos", contas[""])):
        abas.append("<a class='%s' href='%s'>%s <i>%s</i></a>"
                    % ("on" if valor == estado_actual else "",
                       sem_pagina(request.args, rota, estado=valor),
                       etiqueta, mil(quantos)))
    abas.append("</div>")

    cpv_actual = request.args.get("cpv", "")
    faixa_cpv = faixa_cpv_activo(request.args,
                                 sem_pagina(request.args, rota, cpv=""))
    faixa_interesse = _faixa_do_interesse(rota, escondidos_interesse, cfg)

    # A plataforma decide se as peças se conseguem trazer, por isso vale
    # a pena poder isolá-la -- ver só acingov/vortal/compraspt é ver o que
    # dá para trabalhar sem ir ao site.
    plat_actual = (request.args.get("plat") or "").strip()
    # O rotulo diz sobre quantos e que conta. Antes dizia "(nenhuma) (56)"
    # e devolvia 60 645: os numeros do selector saem dos anuncios com
    # detalhe lido, que sao 8% da base, e nao havia nada a dize-lo nem
    # forma nenhuma de pedir os outros 92%.
    opcoes_plat = ["<option value=''>todas as plataformas (%s)</option>"
                   % mil(no_filtro)]
    if porler:
        opcoes_plat.append(
            "<option value='%s'%s>ainda sem detalhe lido (%s)</option>"
            % (html.escape(POR_LER, quote=True),
               " selected" if plat_actual == POR_LER else "",
               mil(porler_filtro)))
    for r in plataformas:
        etiqueta = ("sem plataforma indicada" if r["p"] == SEM_PLATAFORMA
                    else r["p"])
        opcoes_plat.append(
            "<option value='%s'%s>%s (%s)</option>"
            % (html.escape(r["p"], quote=True),
               " selected" if r["p"] == plat_actual else "",
               html.escape(etiqueta), mil(conta_plat.get(r["p"], 0))))

    prazo_actual = (request.args.get("prazo") or "").strip()
    # A janela do urgente le-se UMA vez por pedido: serve o rotulo do
    # selector e a etiqueta de prazo de cada linha, e dias_urgente() abre
    # o config.json a cada chamada.
    urgente = dias_urgente()
    opcoes_prazo = "".join(
        "<option value='%s'%s>%s</option>"
        % (v, " selected" if v == prazo_actual else "", t)
        for v, t in (("", "prazo: tanto faz"),
                     ("aberto", "só os que ainda dão para concorrer"),
                     ("urgente", "só os que acabam em %d dias" % urgente),
                     ("expirado", "só os de prazo passado")))

    filtros = (
        "<form class='cx filtros' method='get' action='%s'>"
        "<input type='text' name='q' value='%s' placeholder='Nome do anúncio ou objecto…'>"
        # As exclusoes ao lado das inclusoes: palavras a tirar e CPV a
        # tirar. O cpv_excl continua a aceitar o que se escreva a mao
        # (codigos ou palavras, separados por |), mas desde 01/09/2026 e
        # tambem onde a arvore escreve o que se desmarcou dentro de uma
        # divisao marcada -- por isso leva id, que e por onde ela le.
        "<input type='text' name='q_excl' value='%s' placeholder='Excluir palavras…'>"
        "<input type='text' name='ent' value='%s' placeholder='Entidade que publica…'>"
        "<input type='hidden' id='filtro-cpv' name='cpv' value='%s'>"
        "<input type='text' id='filtro-cpv-excl' name='cpv_excl' value='%s' "
        "placeholder='Excluir CPV…' "
        "style='min-width:0;width:150px;flex:none'>"
        "<select name='op' title='como juntar as palavras e o CPV'>%s</select>"
        "<select name='plat'>%s</select>"
        "<select name='prazo'>%s</select>"
        "<label>de</label><input type='date' name='de' value='%s'>"
        "<label>até</label><input type='date' name='ate' value='%s'>"
        "<input type='hidden' name='estado' value='%s'>"
        "<button type='submit'>Filtrar</button>"
        "<a class='limpar' href='%s'>limpar</a>"
        "</form>"
        % (html.escape(rota, quote=True),
           html.escape(request.args.get("q", ""), quote=True),
           html.escape(request.args.get("q_excl", ""), quote=True),
           html.escape(request.args.get("ent", ""), quote=True),
           html.escape(cpv_actual, quote=True),
           html.escape(request.args.get("cpv_excl", ""), quote=True),
           opcoes_op(request.args),
           "".join(opcoes_plat), opcoes_prazo,
           html.escape(request.args.get("de", ""), quote=True),
           html.escape(request.args.get("ate", ""), quote=True),
           html.escape(estado_actual, quote=True),
           html.escape(href_limpar(rota, estado_actual), quote=True)))

    caixa_guardados = caixa_de_filtros(request.args, "anuncios", rota)

    arvore = arvore_html(n_cpv, "anuncios")

    filtro_em_uso = filtro_actual(request.args, "anuncios")
    if linhas:
        corpo_lista = ("<div class='lista'>"
                       + "".join(linha(a, estado_actual, urgente) for a in linhas)
                       + "</div>")
    elif filtro_em_uso == "estado=" + estado_actual and escondidos_interesse:
        # Sem filtro nenhum, mas com o interesse a tapar: dizer "o que
        # entrou esta triado" com 1290 anuncios escondidos era uma
        # afirmacao falsa por cima da faixa que diz o contrario.
        corpo_lista = ("<div class='vazio'>Nada aqui <b>dentro do "
                       "interesse</b> &mdash; há %s de fora dele. "
                       "<a href='%s'>ver tudo</a> ou "
                       "<a href='/alertas/interesse'>mudar o interesse</a>."
                       "</div>"
                       % (mil(escondidos_interesse),
                          html.escape(sem_pagina(request.args, rota,
                                                 interesse="nao"),
                                      quote=True)))
    elif estado_actual == "novo" and filtro_em_uso == "estado=novo":
        # O vazio proprio do "por ver" sem filtro: nada por decidir e
        # diferente de um filtro que nao apanhou nada.
        corpo_lista = ("<div class='vazio'>Nada por decidir: o que "
                       "entrou está triado, e o que expirou passou "
                       "sozinho para os <a href='/?estado=descartado'>"
                       "Abandonados</a>.</div>")
    else:
        corpo_lista = ("<div class='vazio'>Nada corresponde a este filtro. "
                       "<a href='%s'>limpar</a></div>"
                       % html.escape(href_limpar(rota, estado_actual),
                                     quote=True))

    # a pagina mostra 20; a contagem tem de dizer quantos o filtro apanhou
    # mesmo, senao "20 de 65 869" parece um filtro que nao filtrou nada
    if correspondem > len(linhas):
        primeiro = (pagina - 1) * POR_PAGINA_LISTA + 1
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
    # a aba diz o que o seu recorte faz -- o numero nao pode parecer o
    # acervo todo sem o ser (P4)
    if estado_actual == "novo":
        conta += " &middot; só o que ainda dá para responder"
    elif estado_actual == "descartado":
        conta += " &middot; abandonados à mão e expirados"

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

    # O rodape que repetia a hora da ultima verificacao e as horas
    # marcadas saiu: era o mesmo que a barra lateral ja diz, duas vezes
    # no mesmo ecra. O ponto verde/vermelho foi para la.

    # A ordem: filtros, faixa do CPV activo, arvore, e so depois os
    # filtros guardados. A arvore e onde se escolhe o CPV, por isso vem
    # antes de se guardar a escolha.
    # O CSV leva a marca da lista: o recorte da aba e da pagina e nao
    # do filtro, e sem isto o "exportar as N linhas" do por ver
    # exportava tambem os expirados -- o numero da ligacao mentia.
    qs = request.query_string.decode()
    qs_csv = (qs + "&" if qs else "") + urlencode({"ambito": "anuncios"})

    conteudo = ("<div class='larg'>" + faixa_avisos +
                faixa_de_avisos_de_datas(request.args) +
                faixa_interesse + filtros + faixa_cpv + arvore +
                caixa_guardados +
                "<div class='linha-conta'>" + conta +
                # dizer quantas linhas e que saem: a ligacao esta encostada
                # ao "1-20" e exportava as 66 mil sem avisar
                "<a href='/csv?%s'>exportar as %s linhas (CSV)</a></div>"
                % (html.escape(qs_csv, quote=True), mil(correspondem)) +
                corpo_lista + paginador(pagina, paginas, request.args, rota) +
                "</div>")

    return envolver(
        "anuncios", "Anúncios",
        "Entra tudo o que o DR publica &mdash; e, da Vortal, as "
        "consultas preliminares. <b>Por ver</b> é o que ainda dá para "
        "responder; o que expira passa sozinho para os "
        "<b>Abandonados</b>.",
        conteudo, abas="".join(abas),
        script=ARVORE_JS + LISTA_JS + caixa_de_abandono(),
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


# TODOS os campos que um filtro pode ter, por ordem fixa. A ordem
# importa: e ela que deixa comparar a consulta guardada com a de agora
# por igualdade de texto, para se saber qual dos filtros esta em uso.
#
# **Um filtro nao pertence a um separador.** Guarda os campos que tiver,
# e cada pagina aplica os que entende -- por isso um filtro por CPV
# serve os anuncios, os contratos e a ficha de uma entidade.
CAMPOS_FILTRO = ("q", "q_excl", "cpv", "cpv_excl",   # entendem-nos todos
                 "op",                               # E/OU entre q e cpv
                 "de", "ate",
                 "ent", "plat", "estado", "prazo",   # so os anuncios
                 "adj", "ganhou", "proc", "min", "entid", "vencid")
# (O "arquivo" do interruptor da Pesquisa viveu aqui entre as duas
# decisoes de 31/08/2026: entrou com a janela dos 12 meses e saiu
# quando a lista se tornou uma so, sem janela nenhuma. Um filtro
# guardado que o tenha fica marcado parcial, declarado.)

# Argumentos que a lista usa mas nao definem o filtro, e por isso nao se
# guardam nem se arrastam para as ligacoes: a pagina e onde se esta, o
# aviso e da vez, e o ambito e da vista que o poe (so o CSV o le).
CAMPOS_DA_VEZ = ("pag", "aviso", "ambito")

# O que cada pagina sabe fazer. Um campo que a pagina nao conhece nao se
# aplica em silencio: o chip fica marcado como parcial e diz o que ficou
# de fora. Aplicar "ganho por MEO" aos anuncios, onde nao ha vencedor,
# seria alargar o filtro sem avisar.
CAMPOS_POR_VISTA = {
    "anuncios": ("q", "q_excl", "cpv", "cpv_excl", "op", "de", "ate", "ent",
                 "plat", "estado", "prazo"),
    "contratos": ("q", "q_excl", "cpv", "cpv_excl", "op", "de", "ate", "adj",
                  "ganhou", "proc", "min", "entid", "vencid"),
    "entidade": ("q", "q_excl", "cpv", "cpv_excl", "op", "de", "ate", "proc",
                 "min"),
    # A vista do modo "fim estimado" dos contratos (6.1-A; era a pagina
    # /renovacoes): os mesmos campos, MENOS as datas de celebracao -- o
    # modo ja tem um eixo do tempo (a janela do fim estimado) e dois
    # confundem. Um filtro com de/ate entra na mesma e fica marcado
    # como parcial, e o ecra explica que as datas ficaram de lado.
    "renovacoes": ("q", "q_excl", "cpv", "cpv_excl", "op", "adj", "ganhou",
                   "proc", "min", "entid", "vencid"),
}
# A rota generica de cada vista. Desde a fusao de 31/08/2026, a lista
# dos anuncios e uma so e vive em "/".
ROTA_DA_VISTA = {"anuncios": "/", "contratos": "/contratos",
                 "renovacoes": "/renovacoes"}


def campos_da_vista(vista):
    return CAMPOS_POR_VISTA.get(vista, CAMPOS_FILTRO)


def filtro_actual(args, vista="anuncios"):
    """A query string canonica do filtro em uso, para guardar e comparar."""
    pares = []
    for campo in CAMPOS_FILTRO:
        if campo not in campos_da_vista(vista):
            continue
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


def filtro_para(consulta, vista):
    """(query string aplicavel nesta vista, campos que ficaram de fora)."""
    sabe = campos_da_vista(vista)
    dentro, fora = [], []
    for k, v in parse_qsl(consulta or "", keep_blank_values=True):
        if k in sabe:
            dentro.append((k, v))
        elif v:
            fora.append(k)
    return urlencode(dentro), fora


# Como se le cada campo na descricao de um filtro.
# Os nomes que aparecem na legenda de um filtro. `ent` e `adj` sao campos
# diferentes com o mesmo sentido em tabelas diferentes, e chamar
# "entidade" aos dois produzia o aviso mais confuso da aplicacao:
# "entidade Município de Lisboa — aqui não se aplica: entidade". Os
# rotulos das caixas dizem agora o mesmo que estes.
_NOMES_FILTRO = {"q": "objecto", "cpv": "CPV", "de": "desde", "ate": "até",
                 "q_excl": "sem", "cpv_excl": "sem CPV",
                 "op": "palavras/CPV",
                 "ent": "entidade que publica", "plat": "plataforma",
                 "prazo": "prazo",
                 "adj": "entidade que comprou", "ganhou": "ganho por",
                 "proc": "procedimento", "min": "desde €",
                 "entid": "entidade que comprou", "vencid": "ganho por"}
# O "urgente" nao esta aqui: o numero dele e configuravel (B13) e
# resolve-se na hora, em resumo_filtro().
_NOMES_PRAZO = {"aberto": "prazo por fechar", "expirado": "prazo passado"}
_NOMES_ESTADO = {"novo": "por ver", "interessa": "interessa",
                 "descartado": "abandonado", "alteracao": "alteração",
                 "": "todos"}
# Traducao das accoes antigas do historico para o vocabulario actual
# (§7 do ESQUELETO: "análise" nao aparece no ecra — chama-se leitura).
# Os registos gravados antes da mudanca ficam na base como estao; e ao
# mostrar que se traduzem.
_NOMES_ACCAO = {"análise": "leitura"}


def resumo_filtro(consulta, vista=None):
    """Diz por palavras o que um filtro apanha, para a legenda. Sem
    vista, descreve o filtro inteiro."""
    campos = dict(parse_qsl(consulta or "", keep_blank_values=True))
    sabe = campos_da_vista(vista) if vista else CAMPOS_FILTRO
    partes = []
    for campo in CAMPOS_FILTRO:
        if campo not in sabe or campo not in campos:
            continue
        valor = campos[campo]
        if campo == "estado":
            partes.append(_NOMES_ESTADO.get(valor, valor))
        elif campo == "prazo" and valor:
            partes.append("prazo a menos de %d dias" % dias_urgente()
                          if valor == "urgente"
                          else _NOMES_PRAZO.get(valor, valor))
        elif campo == "op" and valor:
            # "op ou" nao diz nada; a legenda diz o que o modo faz
            partes.append("palavras OU CPV" if valor == "ou" else valor)
        elif valor:
            partes.append("%s %s" % (_NOMES_FILTRO[campo], valor))
    return " · ".join(partes) or "sem filtro"


def opcoes_op(args):
    """As duas opcoes do E/OU, com a redaccao da Tendios traduzida:
    mais restrito / mais amplo. Igual nos formularios todos."""
    ou = (args.get("op") or "").strip() == "ou"
    return ("<option value=''%s>palavras E CPV — mais restrito</option>"
            "<option value='ou'%s>palavras OU CPV — mais amplo</option>"
            % ("" if ou else " selected", " selected" if ou else ""))


def quantos_cpv():
    with liga() as c:
        return c.execute("SELECT COUNT(*) n FROM cpv_dict").fetchone()["n"]


def arvore_html(n_cpv, de, submeter=True):
    """A arvore de CPV, igual nos dois separadores.

    O `de` diz de onde vem a contagem de cada codigo (anuncios ou
    contratos) e vai no proprio elemento, num data-*: o JS e o mesmo nos
    dois sitios e le dali a rota que ha-de pedir. Duas copias do JS
    divergiam ao primeiro arranjo.
    """
    quantos = {"anuncios": "anúncios", "contratos": "contratos"}[de]
    return (
        "<details class='arvore' data-de='%s'%s><summary>"
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
        "<div class='arv-pe'>Marcar uma divisão apanha tudo o que está por "
        "baixo dela &mdash; ao filtro vai só o código do grupo, e os zeros à "
        "direita fazem o resto. <b>Desmarcar um código lá dentro tira só "
        "esse</b>: vai para &ldquo;excluir CPV&rdquo; e a divisão continua a "
        "contar, incluindo os anúncios que só trazem o código dela.</div>"
        "</details>" % (de, "" if submeter else " data-submeter='nao'",
                        mil_pt(n_cpv), quantos))


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


def janela_urgente(hoje):
    """(hoje, hoje + dias_urgente()), em ISO. E UMA janela so.

    Usam-na o filtro prazo=urgente e o cartao "Interessa" dos
    indicadores. Ja houve um "7" escrito a mao no cartao com o filtro a
    10: o numero do ecra nao abria lista nenhuma que o confirmasse."""
    return (hoje.isoformat(),
            (hoje + timedelta(days=dias_urgente())).isoformat())


def fragmento_cpv(texto, coluna="cpv"):
    """(fragmento, valores) do filtro por CPV. Cada pedaco e um codigo
    (72, 72267100-0) ou uma palavra da descricao oficial (software,
    manutencao); qualquer um serve. Um termo que nao corresponde a nada
    da "1=0": mostra vazio, nao tudo.

    Esta fora de condicoes() para o recorte do interesse (o limite
    permanente da lista, definido em /alertas) usar exactamente a mesma
    leitura de CPV que o filtro -- duas leituras divergiam ao primeiro
    arranjo, que e o que ja aconteceu com o prefixo_cpv.
    """
    cpv = (texto or "").strip()
    if not cpv:
        return "", []
    ors, vals = [], []
    for pedaco in (p.strip() for p in cpv.split("|")):
        if not pedaco:
            continue
        if re.fullmatch(r"[\d\-\s]+", pedaco):
            prefixos = [prefixo_cpv(pedaco)]
        else:
            prefixos = cpv_por_termo(pedaco)
        for prefixo in prefixos:
            if prefixo:
                ors.append("(%s LIKE ? OR %s LIKE ?)" % (coluna, coluna))
                vals += [prefixo + "%", "%, " + prefixo + "%"]
    return ("(" + " OR ".join(ors) + ")" if ors else "1=0"), vals


def condicoes(args):
    """Traduz os filtros do painel em SQL. Nada e apagado, so escondido."""
    onde, valores = [], []

    def frag_texto(texto, coluna):
        """(fragmento, valores) da procura por palavras -- varias
        separadas por |, qualquer uma serve. Nao toca no onde: quem
        chama decide onde o fragmento entra, que e o que deixa o op=ou
        junta-lo ao do CPV sem baralhar a ordem dos placeholders.

        Procura-se nas colunas normalizadas (`titulo_norm`,
        `entidade_norm`) e com o termo normalizado do mesmo modo. O LIKE
        do SQLite so baixa maiusculas de letras ASCII: escrever
        "aquisição" devolvia 25 868 dos 29 058 anuncios que contem mesmo
        a palavra, porque os 9 383 titulos escritos todos em maiusculas
        tem "Ç" e para o LIKE isso nao e "ç". Eram 11% de cada pesquisa,
        perdidos sem aviso nenhum.
        """
        pedacos = [p.strip() for p in (texto or "").split("|") if p.strip()]
        if not pedacos:
            return "", []
        ors, vals = [], []
        for p in pedacos:
            ors.append("%s LIKE ? ESCAPE '%s'" % (coluna, ESCAPE_LIKE))
            vals.append("%" + para_like(simplifica(p)) + "%")
        return "(" + " OR ".join(ors) + ")", vals

    def procura(texto, coluna):
        frag, vals = frag_texto(texto, coluna)
        if frag:
            onde.append(frag)
            valores.extend(vals)

    def exclui(texto, coluna):
        """Como procura(), invertida: o que corresponder fica de fora.

        O COALESCE nao e decorativo: NOT (NULL LIKE x) e NULL, e a linha
        com a coluna por preencher desaparecia da lista -- excluir
        "obras" nao pode esconder um anuncio que ainda nem titulo tem.
        """
        pedacos = [p.strip() for p in (texto or "").split("|") if p.strip()]
        if not pedacos:
            return
        ors = []
        for p in pedacos:
            ors.append("COALESCE(%s,'') LIKE ? ESCAPE '%s'"
                       % (coluna, ESCAPE_LIKE))
            valores.append("%" + para_like(simplifica(p)) + "%")
        onde.append("NOT (" + " OR ".join(ors) + ")")

    frag_cpv = fragmento_cpv

    # Duas caixas, e nao uma sobre as duas colunas: procurar "Lisboa"
    # devolvia tanto os concursos com Lisboa no objecto como todos os da
    # Camara de Lisboa, sem se poder separar. Entre elas e E, nao OU --
    # serve para "software" na entidade "SPMS".
    #
    # Entre as palavras e o CPV, o op escolhe (B07): por omissao E
    # (pesquisa mais restrita); com op=ou, OU (mais ampla) -- e a
    # traducao da Tendios para humano. Um CPV que nao corresponde a nada
    # no modo OU nao acrescenta nada, em vez de esvaziar o lado das
    # palavras com um 1=0.
    frag_q, vals_q = frag_texto(args.get("q"), "titulo_norm")
    frag_c, vals_c = frag_cpv(args.get("cpv"))
    juntos = ((args.get("op") or "").strip() == "ou"
              and frag_q and frag_c and frag_c != "1=0")
    if not juntos and frag_q:
        onde.append(frag_q)
        valores.extend(vals_q)
    procura(args.get("ent"), "entidade_norm")
    # A exclusao por palavras: "vigilancia" sem "videovigilancia". Tres
    # dos quatro concorrentes observados tem-na (ver CONCORRENTES.md), e
    # sem ela um filtro largo obriga a descartar o mesmo ruido a mao
    # todas as semanas.
    exclui(args.get("q_excl"), "titulo_norm")
    if juntos:
        onde.append("(%s OR %s)" % (frag_q, frag_c))
        valores.extend(vals_q)
        valores.extend(vals_c)
    elif frag_c and not ((args.get("op") or "").strip() == "ou"
                         and frag_q and frag_c == "1=0"):
        onde.append(frag_c)
        valores.extend(vals_c)
    cpv_ex = (args.get("cpv_excl") or "").strip()
    if cpv_ex:
        # a mesma leitura do campo positivo -- codigos ou palavras da
        # descricao oficial -- mas invertida. O COALESCE pela mesma razao
        # do exclui(): um anuncio ainda sem CPV lido nao e "CPV 72", e
        # excluir o 72 nao o pode esconder.
        ors = []
        for pedaco in (p.strip() for p in cpv_ex.split("|")):
            if not pedaco:
                continue
            if re.fullmatch(r"[\d\-\s]+", pedaco):
                prefixos = [prefixo_cpv(pedaco)]
            else:
                prefixos = cpv_por_termo(pedaco)
            for prefixo in prefixos:
                if prefixo:
                    ors.append("(COALESCE(cpv,'') LIKE ? OR "
                               "COALESCE(cpv,'') LIKE ?)")
                    valores += [prefixo + "%", "%, " + prefixo + "%"]
        # ao contrario do filtro positivo, um termo que nao corresponde a
        # nada nao exclui nada: e um nao-filtro, nao um "1=0"
        if ors:
            onde.append("NOT (" + " OR ".join(ors) + ")")
    plat = (args.get("plat") or "").strip()
    if plat:
        if plat == SEM_PLATAFORMA:
            # o mesmo criterio do numero que o selector mostra: sem
            # detalhe lido ainda nao ha plataforma, e isso e outro balde
            onde.append("(detalhe_lido = 1 AND "
                        "(plataforma IS NULL OR plataforma = ''))")
        elif plat == POR_LER:
            onde.append("detalhe_lido = 0")
        else:
            onde.append("plataforma = ?"); valores.append(plat)
    # So datas a serio: "de=lixo" num URL guardado comparava texto com
    # datas e esvaziava a lista em silencio. Ignora-se e a lista avisa.
    de = data_de_filtro(args.get("de"))
    if de:
        onde.append("data_pub >= ?"); valores.append(de)
    ate = data_de_filtro(args.get("ate"))
    if ate:
        onde.append("data_pub <= ?"); valores.append(ate)
    # O prazo, que separa a oportunidade do arquivo. Depois de entrarem os
    # dois anos de historico, 3982 dos "por ver" ja tinham o prazo passado
    # e estavam misturados com os de hoje, sem forma nenhuma de os apartar.
    # A etiqueta vermelha ja existia na linha; faltava poder pedir a lista
    # sem eles.
    prazo = (args.get("prazo") or "").strip()
    if prazo in ("aberto", "expirado", "urgente"):
        inicio, fim = janela_urgente(datetime.now().date())
        onde.append("(prazo IS NOT NULL AND prazo != '' AND prazo %s ?%s)"
                    % ("<" if prazo == "expirado" else ">=",
                       " AND prazo <= ?" if prazo == "urgente" else ""))
        valores.append(inicio)
        if prazo == "urgente":
            valores.append(fim)
    estado = args.get("estado")
    if estado is None:
        estado = "novo"
    if estado:
        onde.append("estado = ?"); valores.append(estado)
    else:
        # "todos" sao todos os PROCEDIMENTOS. Uma alteracao e a
        # republicacao de um anuncio que ja esta na lista, com o prazo
        # e o preco dela ja postos nele; mostra-la era contar o mesmo
        # concurso duas vezes -- e um alerta avisar dele duas vezes.
        onde.append("estado != 'alteracao'")
    return (" WHERE " + " AND ".join(onde) if onde else ""), valores


GUARDAR_JS = """<script>
function confirmarGravar(f) {
  var nomes = [];
  try { nomes = JSON.parse(f.dataset.nomes || '[]'); } catch (x) {}
  var nome = (f.nome.value || '').trim();
  for (var i = 0; i < nomes.length; i++) {
    if (nomes[i].toLowerCase() === nome.toLowerCase()) {
      return confirm('Já existe um filtro chamado "' + nomes[i] +
                     '". Gravar por cima substitui o que lá está.');
    }
  }
  return true;
}
</script>"""


def faixa_cpv_activo(args, tirar_href):
    """A faixa "Filtro CPV activo", UMA so para as paginas com arvore
    (decisao 6.3-A). O campo do CPV e escondido -- quem escolhe e a
    arvore -- e sem a faixa um CPV posto nao se via em lado nenhum.
    Eram quatro copias "com pequenas diferencas" a divergir.
    """
    cpv = (args.get("cpv") or "").strip()
    if not cpv:
        return ""
    return ("<div class='cpv-activo'>Filtro CPV activo: <b>%s</b>"
            "<a href='%s'>tirar</a></div>"
            % (html.escape(cpv), html.escape(tirar_href, quote=True)))


def _faixa_do_interesse(rota, escondidos, cfg=None):
    """A faixa que diz que a lista esta limitada ao interesse -- ou que
    ele foi levantado neste pedido.

    Um recorte que nao se ve e um recorte que engana: a lista mostrava
    trinta anuncios e o Afonso nao tinha como saber se eram trinta ou
    trezentos. Diz o que apanha, quanto tapa, e tem as duas portas --
    levantar e voltar a pôr.
    """
    levantado = (request.args.get("interesse") or "").strip() == "nao"
    ligado, dentro, fora = interesse_definido(cfg)
    if not ligado or not dentro:
        return ""
    if levantado:
        return ("<div class='cpv-activo'>Interesse levantado nesta vista "
                "&mdash; vês o acervo todo.<a href='%s'>voltar ao interesse"
                "</a></div>"
                % html.escape(sem_pagina(request.args, rota, interesse=""),
                              quote=True))
    quantos = ("<span class='d'> &middot; %s de fora</span>"
               % mil_pt(escondidos)) if escondidos > 0 else ""
    return ("<div class='cpv-activo'>Limitado ao "
            "<a href='/alertas/interesse'>interesse</a>: <b>%s</b>%s%s"
            "<a href='%s'>ver tudo</a></div>"
            % (html.escape(dentro),
               (" <span class='d'>sem %s</span>" % html.escape(fora))
               if fora else "", quantos,
               html.escape(sem_pagina(request.args, rota, interesse="nao"),
                           quote=True)))


def selector_procedimento(procs, actual, vazio="todos os procedimentos"):
    """O <select name='proc'>, UM so (decisao 6.4-A): estava montado
    tres vezes e cada copia divergia ao primeiro arranjo. O `vazio` e o
    rotulo da opcao sem filtro, que muda com o contexto."""
    opcoes = ["<option value=''>%s</option>" % html.escape(vazio)]
    for p in procs:
        opcoes.append("<option value='%s'%s>%s</option>"
                      % (html.escape(p, quote=True),
                         " selected" if p == actual else "",
                         html.escape(p)))
    return "<select name='proc'>%s</select>" % "".join(opcoes)


def caixa_de_filtros(args, vista, rota=None, extra=""):
    """A caixa dos filtros guardados, igual em todas as paginas.

    Aplicar um filtro e seguir uma ligacao -- so leitura, nada muda na
    base -- mas guardar e apagar sao POST, como o resto do que escreve.

    Os filtros sao os mesmos em todo o lado; o que muda e o que cada
    pagina sabe aplicar. Um filtro com campos que esta pagina nao conhece
    entra na mesma, com a parte que serve, e **fica marcado como
    parcial** a dizer o que ficou de fora -- aplicar "ganho por MEO" aos
    anuncios, onde nao ha vencedor, seria alargar o filtro em silencio.

    O `extra` e da vista, nao do filtro (p.ex. "ver=fim" no modo fim
    estimado dos contratos): cola-se a frente da consulta em cada
    ligacao, para aplicar um filtro sem sair do modo em que se esta.
    """
    rota = rota or ROTA_DA_VISTA.get(vista, "/")
    agora = filtro_actual(args, vista)

    def destino(consulta):
        pedacos = [x for x in (extra, consulta) if x]
        return rota + ("?" + "&".join(pedacos) if pedacos else "")
    with liga() as c:
        guardados = c.execute(
            "SELECT * FROM filtros_guardados "
            "ORDER BY nome COLLATE NOCASE").fetchall()

    fichas, nome_activo, fora_activo = [], "", ()
    for f in guardados:
        consulta, de_fora = filtro_para(f["consulta"] or "", vista)
        activo = consulta == agora
        if activo:
            nome_activo = f["nome"]
            fora_activo = de_fora
        titulo = resumo_filtro(f["consulta"] or "")
        if de_fora:
            titulo += " — aqui não se aplica: %s" % ", ".join(
                _NOMES_FILTRO.get(k, k) for k in de_fora)
        fichas.append(
            "<span class='guardado%s%s'>"
            "<a href='%s' title='%s'>%s%s</a></span>"
            % (" on" if activo else "", " parcial" if de_fora else "",
               html.escape(destino(consulta), quote=True),
               html.escape(titulo, quote=True), html.escape(f["nome"]),
               "<i>parcial</i>" if de_fora else ""))

    if fichas:
        legenda = ""
    else:
        legenda = ("<span class='nada'>ainda nenhum &mdash; guarda o filtro "
                   "de agora, ou cria um em <a href='/alertas'>Alertas</a>"
                   "</span>")

    # O que ficou de fora do filtro em uso, escrito e nao escondido. A
    # regra e boa -- um filtro nunca se aplica a meio em silencio -- mas
    # o que ficava a vista era so a palavra "parcial", e a lista dos
    # campos vivia no `title`, que so aparece a quem deixe o rato quieto
    # em cima e nao existe fora do rato.
    if fora_activo:
        legenda += (
            "<span class='parcial-nota'>Este filtro tem campos que esta "
            "página não aplica: <b>%s</b>. Está a filtrar só pelo resto."
            "</span>" % html.escape(", ".join(
                _NOMES_FILTRO.get(k, k) for k in fora_activo)))

    # O nome do filtro em uso vem preenchido de proposito: gravar por cima
    # do mesmo nome e como se actualiza um filtro depois de o afinar. Mas
    # e por isso mesmo que se confirma: afinar um filtro, mudar de ideias
    # e gravar substituia outro sem perguntar nada e sem forma de voltar
    # atras -- o "Filtro actualizado" so aparecia depois de estar feito.
    nomes = [f["nome"] for f in guardados]
    guardar = (
        "<form class='guardar' method='post' action='/filtros/guardar' "
        "data-nomes='%s' onsubmit='return confirmarGravar(this)'>"
        "<input type='hidden' name='consulta' value='%s'>"
        "<input type='hidden' name='volta' value='%s'>"
        "<input type='text' name='nome' required maxlength='60' value='%s' "
        "placeholder='dar nome a estes filtros…'>"
        "<button type='submit' class='bt forte'>Guardar filtro</button>"
        "</form>" % (html.escape(json.dumps(nomes, ensure_ascii=False),
                                 quote=True),
                     html.escape(agora, quote=True),
                     html.escape(destino(""), quote=True),
                     html.escape(nome_activo, quote=True)))

    return ("<div class='cx guardados'><span class='rot'>"
            "Filtros guardados</span>%s%s%s%s"
            "<a class='gerir' href='/alertas'>gerir</a></div>"
            % ("".join(fichas), legenda, guardar, GUARDAR_JS))


def volta_para(rota, consulta="", aviso=""):
    """Volta para a pagina de onde se veio, com os filtros que estavam.

    A rota vem de um campo escondido do formulario, e por isso
    confirma-se: nunca se redirecciona para o que la vier. A rota pode
    ja trazer query string ("/contratos?ver=fim") -- ai junta-se com &,
    senao saia "?ver=fim?consulta" e o modo perdia-se.
    """
    if not (rota or "").startswith("/") or "//" in (rota or ""):
        rota = "/"
    partes = [x for x in (consulta, urlencode({"aviso": aviso}) if aviso else "")
              if x]
    separa = "&" if "?" in rota else "?"
    return redirect(rota + separa + "&".join(partes) if partes else rota)


def gravar_filtro(nome, consulta, alerta=None):
    """Guarda ou actualiza pelo nome.

    Gravar por cima do mesmo nome actualiza-o -- e assim que se afina um
    filtro sem ficar com dois quase iguais e sem saber qual esta em uso.
    Com `alerta` a None mantem-se a marca que ja tinha: guardar de novo
    a partir de uma lista nao pode desligar um alerta sem se dar por
    isso. Devolve se ja existia.
    """
    with liga() as c:
        antes = c.execute("SELECT id, alerta FROM filtros_guardados "
                          "WHERE nome=?", (nome,)).fetchone()
        manter = antes["alerta"] if antes else 0
        c.execute("""INSERT INTO filtros_guardados
                       (nome,consulta,alerta,quem,criado_em)
                     VALUES (?,?,?,?,?)
                     ON CONFLICT(nome) DO UPDATE SET
                       consulta=excluded.consulta, alerta=excluded.alerta,
                       quem=excluded.quem, criado_em=excluded.criado_em""",
                  (nome, consulta,
                   manter if alerta is None else int(bool(alerta)),
                   quem_sou() or "(sem nome)",
                   datetime.now().strftime("%Y-%m-%d %H:%M")))
    return bool(antes)


@app.route("/filtros/guardar", methods=["POST"])
def filtro_guardar():
    nome = (request.form.get("nome") or "").strip()
    consulta = (request.form.get("consulta") or "").strip()
    volta = (request.form.get("volta") or "/").strip()
    if not nome:
        return volta_para(volta, consulta)
    havia = gravar_filtro(nome, consulta)
    return volta_para(volta, consulta, "Filtro %s: %s"
                      % ("actualizado" if havia else "guardado", nome))


@app.route("/filtros/<int:filtro_id>/apagar", methods=["POST"])
def filtro_apagar(filtro_id):
    """Apaga so o filtro. Nem os anuncios nem os contratos se mexem -- um
    filtro esconde, nao apaga, e tira-lo devolve a lista inteira."""
    with liga() as c:
        linha = c.execute("SELECT nome FROM filtros_guardados WHERE id=?",
                          (filtro_id,)).fetchone()
        c.execute("DELETE FROM filtros_guardados WHERE id=?", (filtro_id,))
        c.execute("DELETE FROM alertas_vistos WHERE filtro_id=?", (filtro_id,))
    return volta_para((request.form.get("volta") or "/alertas").strip(), "",
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
    """Arranca e responde. Quem espera e a barra lateral, que se
    recarrega sozinha enquanto isto correr -- nao o pedido do browser.
    E volta a pagina de onde se carregou: o botao esta no topo de tres
    separadores e atirava sempre para a lista de anuncios."""
    arrancou, porque = comecar_verificacao()
    volta = request.referrer or "/"
    if not arrancou:
        junta = "&" if "?" in volta else "?"
        return redirect(volta + junta + urlencode({"aviso": porque}))
    return redirect(volta)


def _volta_com_aviso(texto, desfazer=None):
    """De volta a pagina de onde se carregou, com um aviso por cima.

    O mesmo caminho do "Verificar agora": a accao vem de tres sitios
    diferentes (lista, ficha, quadro) e cada um tem de voltar ao seu.

    O `desfazer` e o caminho POST que repoe o que se acabou de fazer, e
    envolver() desenha-o como botao dentro do aviso. O aviso anterior
    sai da query string antes de se por o novo: quem desfaz a partir de
    uma pagina que ja tinha ?aviso=... voltava com os dois.
    """
    partes = urlparse(request.referrer or "/")
    fica = [(k, v) for k, v in parse_qsl(partes.query, keep_blank_values=True)
            if k not in ("aviso", "desfazer")]
    fica.append(("aviso", texto))
    if desfazer:
        fica.append(("desfazer", desfazer))
    return redirect(partes._replace(query=urlencode(fica)).geturl())


@app.route("/estado/<path:ref>/<novo>", methods=["POST"])
def mudar_estado(ref, novo):
    if novo in ("novo", "interessa", "descartado"):
        # Abandonar exige motivo, de ambito fechado (decisao do Afonso a
        # 01/09/2026). Passado um mes, "abandonado" sozinho nao diz nada:
        # nao se sabe se foi o preco, se foi falta de certificacoes, nem
        # se vale a pena voltar a olhar para aquela entidade.
        # request.values e nao request.form: o "desfazer" de um
        # abandono reposto leva o motivo antigo na propria accao do
        # formulario (?motivo=...), porque o aviso vem pela query string
        motivo = (request.values.get("motivo") or "").strip()
        if novo == "descartado" and motivo not in MOTIVOS_ABANDONO:
            return _volta_com_aviso("Escolhe o motivo antes de abandonar.")
        with liga() as c:
            actual = c.execute("SELECT estado, altera FROM anuncios WHERE ref=?",
                               (ref,)).fetchone()
            if actual and actual["estado"] == "alteracao":
                raiz = raiz_da_alteracao(c, ref, actual["altera"] or "")
        if actual and actual["estado"] == "alteracao":
            # A alteracao nao se tria: a decisao e do procedimento, e o
            # procedimento e o anuncio original -- que ja tem o prazo
            # desta.
            return _volta_com_aviso(
                "O anúncio %s é uma alteração do %s: decide-se na ficha dele."
                % (ref, raiz or "original"))
        with liga() as c:
            antes = c.execute("SELECT estado, titulo, motivo FROM anuncios "
                              "WHERE ref=?", (ref,)).fetchone()
            ja_estava = bool(antes) and antes["estado"] == novo
            if novo == "interessa":
                c.execute("""UPDATE anuncios SET estado=?, motivo=NULL,
                             fase_id=COALESCE(fase_id, ?) WHERE ref=?""",
                          (novo, primeira_fase(), ref))
            else:
                # Sair de abandonado limpa o motivo: um motivo pendurado
                # num anuncio que voltou ao por ver e uma mentira a
                # espera de ser lida.
                c.execute("UPDATE anuncios SET estado=?, motivo=? WHERE ref=?",
                          (novo, motivo or None, ref))
        if not ja_estava:
            registar(ref, "estado",
                     "%s (%s)" % (novo, motivo) if motivo else novo)
        if novo == "interessa" and not ja_estava:
            # Marcar interessa e o sinal de que vais mesmo trabalhar isto,
            # por isso as pecas vem sozinhas -- mas por uma fila, nao uma
            # thread por clique: triar vinte anuncios seguidos abria vinte
            # descargas de varios MB ao mesmo tempo.
            #
            # E so quando o estado muda mesmo: com o botao "interessa" a
            # aparecer tambem em quem ja estava interessado, cada clique
            # repetido voltava a descarregar as pecas todas.
            pedir_documentos(ref)
        if not antes:
            return redirect(request.referrer or "/")
        # O aviso diz o que se fez e a quem, e traz o caminho de volta.
        # Se o estado anterior era um abandono com motivo, o motivo vai
        # na accao do desfazer: sem ele o servidor recusava a reposicao.
        rotulo = {"interessa": "marcado como interessa",
                  "descartado": "abandonado" + (" (%s)" % motivo if motivo else ""),
                  "novo": "reposto em por ver"}[novo]
        texto = "\u00ab%s\u00bb %s." % (corta(antes["titulo"] or ref, 70), rotulo)
        desfazer = None
        if not ja_estava and (antes["estado"] != "descartado" or antes["motivo"]):
            desfazer = "/estado/%s/%s" % (ref, antes["estado"])
            if antes["estado"] == "descartado":
                desfazer += "?" + urlencode({"motivo": antes["motivo"]})
        return _volta_com_aviso(texto, desfazer)
    return redirect(request.referrer or "/")


@app.route("/plataforma/<path:ref>")
def abrir_procedimento(ref):
    """Leva a pagina do procedimento na plataforma.

    So a Vortal precisa desta volta: o endereco que o DR publica e o das
    pecas, cifrado, e o do procedimento sai da API. Resolve-se UMA vez e
    guarda-se em `link_proc` -- a ficha nao pode ir a rede de cada vez
    que alguem a abre.

    Quando nao ha pagina publica do procedimento (a Vortal tambem
    publica anuncios que ficam so na lista das pecas), volta-se a ficha
    a dizer porque, em vez de mandar o Afonso para uma pagina que nao e
    o que o botao prometia.
    """
    with liga() as c:
        a = c.execute("SELECT ref, plataforma, link_pecas, link_proc "
                      "FROM anuncios WHERE ref=?", (ref,)).fetchone()
    if not a:
        return "Anúncio não encontrado. <a href='/'>voltar</a>", 404
    if a["link_proc"]:
        return redirect(a["link_proc"])
    sessao = requests.Session()
    sessao.headers["User-Agent"] = NAVEGADOR
    _, anuncio = _info_vortal(sessao, a["link_pecas"] or "")
    achado = re.search(r"(PT\d+\.NTC\.\d+)", anuncio or "")
    if not achado:
        return redirect(
            "/anuncio/%s?%s"
            % (quote(ref, safe=""),
               urlencode({"aviso": "A Vortal não publica página deste "
                                   "procedimento — só a lista das peças."})))
    endereco = VORTAL_PROCEDIMENTO % achado.group(1)
    with liga() as c:
        c.execute("UPDATE anuncios SET link_proc=? WHERE ref=?",
                  (endereco, ref))
    return redirect(endereco)


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


def numero_csv(valor):
    """Um numero como o Excel português o come: virgula decimal, sem
    simbolo e sem separador de milhares.

    As duas exportacoes formatavam dinheiro de maneiras diferentes e
    nenhuma servia. Nos anuncios saia "1.326.675,00 EUR", que o Excel le
    como texto e nao soma; nos contratos saia "7546.5", que num Excel
    portugues da setenta e cinco mil. Exporta-se para trabalhar os
    numeros, e era justamente isso que nao dava.
    """
    if valor is None or valor == "":
        return ""
    if isinstance(valor, str):
        valor = euros_do_texto(valor)
        if valor is None:
            return ""
    return ("%.2f" % float(valor)).replace(".", ",")


def nome_csv(prefixo):
    """concursos.csv, concursos(1).csv e concursos(2).csv na pasta das
    descargas nao dizem qual e qual. A data e o prefixo dizem."""
    return "%s-%s.csv" % (prefixo, datetime.now().strftime("%Y-%m-%d"))


@app.route("/csv")
def exportar():
    """Exporta exactamente o que a lista esta a mostrar.

    Com `ambito` posto (as ligacoes da lista poem-no), o CSV aplica o
    MESMO recorte da lista que a pagina aplica (a aba e o interesse):
    sem isto, o "exportar as N linhas" do por ver exportava tambem os
    expirados e o numero da ligacao nao batia com o ficheiro. Sem
    ambito (ligacoes antigas), exporta o filtro tal e qual.
    """
    if (request.args.get("ambito") or "").strip():
        estado = request.args.get("estado")
        estado = "novo" if estado is None else estado.strip()
        onde, valores = com_recorte(
            *condicoes(args_da_lista(request.args, estado="")),
            *recorte_da_lista(estado))
    else:
        onde, valores = condicoes(request.args)
    with liga() as c:
        linhas = c.execute(
            "SELECT ref,data_pub,tipo,entidade,titulo,cpv,prazo,preco_base,"
            "estado,motivo,url FROM anuncios" + onde +
            " ORDER BY data_pub DESC", valores).fetchall()
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";")
    # "Triagem" e nao "Estado": e o rotulo do grupo por ver/interessa/
    # descartados em todo o lado (§7 do ESQUELETO) — "estado" reserva-se
    # para sistema e itens (peças, leitura).
    escritor.writerow(["Anúncio", "Publicado", "Tipo", "Entidade", "Objecto",
                       "CPV", "Prazo", "Preço base (EUR)", "Triagem",
                       "Motivo do abandono", "Endereço"])
    for a in linhas:
        # Datas em DD/MM/AAAA como no resto da aplicacao -- o ISO e para a
        # base, e um CSV e para ver -- e o preco como um numero que o
        # Excel portugues some. "1.326.675,00 EUR" era texto para ele.
        # O estado idem: "novo" e chave interna que nenhum ecra mostra;
        # a coluna diz "por ver", como os separadores.
        escritor.writerow([a["ref"], data_pt(a["data_pub"]), a["tipo"],
                           a["entidade"], a["titulo"], a["cpv"],
                           data_pt(a["prazo"]), numero_csv(a["preco_base"]),
                           _NOMES_ESTADO.get(a["estado"], a["estado"]),
                           a["motivo"] or "", a["url"]])
    return Response("\ufeff" + saida.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition":
                             "attachment; filename=" + nome_csv("anuncios")})




# -------------------------------------------------------- separador alertas
#
# Um alerta e um filtro guardado com a marca posta. Nao ha aqui uma
# segunda forma de descrever o que interessa: o que se procura na lista
# e o que se guarda, e o que se guarda e o que avisa. Isso e o que
# garante que o e-mail traz exactamente o que a lista mostraria.
#
# Ao lado deles vive o INTERESSE, que e outra coisa e nao se confunde:
# um alerta AVISA quando entra alguma coisa; o interesse LIMITA o que a
# lista de anuncios mostra, sempre, sem ninguem ter de o pôr. Sao os
# CPV que a casa faz.

def _caixa_interesse():
    """O resumo do interesse na pagina dos alertas, com a porta para o
    ecra onde se escolhe.

    O ecra e outro por uma razao pratica: a arvore de CPV e uma so por
    pagina -- o JS fala com um `details.arvore` e um `#filtro-cpv` -- e
    /alertas ja gasta a sua no "Novo filtro". Duas arvores na mesma
    pagina obrigavam a mudar o JS que serve quatro paginas.
    """
    ligado, dentro, fora = interesse_definido()
    if dentro:
        estado = ("<b>ligado</b>" if ligado else
                  "<b>desligado</b> &mdash; a lista mostra o acervo todo")
        resumo = ("<div class='nota' style='margin:6px 0 10px'>Está %s. "
                  "CPV: <b>%s</b>%s</div>"
                  % (estado, html.escape(dentro),
                     (", sem <b>%s</b>" % html.escape(fora)) if fora else ""))
    else:
        resumo = ("<div class='nota' style='margin:6px 0 10px'>Ainda não "
                  "está definido: a lista de anúncios mostra tudo o que a "
                  "parte L publica.</div>")
    return ("<div class='cx novo-filtro' style='margin-top:16px'>"
            "<div class='rot'>Interesse</div>"
            "<div class='nota' style='margin:6px 0 10px'>O interesse "
            "limita a <a href='/'>lista de anúncios</a> aos CPV que a "
            "casa trabalha &mdash; em todas as abas e sem se ter de pôr "
            "um filtro. Não é um alerta: um alerta avisa, o interesse "
            "esconde o resto.</div>%s"
            "<div class='arvore-topo' style='padding:0 0 4px'>"
            "<a class='bt' href='/alertas/interesse'>Definir o interesse"
            "</a></div></div>" % resumo)


@app.route("/alertas/interesse")
def interesse():
    """Onde se escolhem os CPV do interesse, com a arvore."""
    cfg = ler_config()
    ligado, dentro, fora = interesse_definido(cfg)
    with liga() as c:
        n_cpv = c.execute("SELECT COUNT(*) n FROM cpv_dict").fetchone()["n"]
        # Quanto e que este interesse apanha hoje, para nao se guardar as
        # cegas: o numero da aba "por ver" e o da base inteira.
        apanha_ver = apanha_tudo = None
        frag, vals = fragmento_cpv(dentro)
        if frag:
            frag_fora, vals_fora = fragmento_cpv(
                fora, coluna="COALESCE(cpv,'')")
            if frag_fora and frag_fora != "1=0":
                frag = "(%s) AND NOT (%s)" % (frag, frag_fora)
                vals = vals + vals_fora
            aba, vals_aba = condicao_da_aba("novo")
            apanha_ver = c.execute(
                "SELECT COUNT(*) n FROM anuncios WHERE (%s) AND (%s)"
                % (aba, frag), vals_aba + vals).fetchone()["n"]
            apanha_tudo = c.execute(
                "SELECT COUNT(*) n FROM anuncios WHERE " + frag,
                vals).fetchone()["n"]
    if apanha_ver is None:
        conta = ("<div class='nota'>Escolhe os códigos na árvore e carrega "
                 "em &ldquo;Aplicar seleccionados ao filtro&rdquo; &mdash; "
                 "depois grava aqui em baixo.</div>")
    else:
        conta = ("<div class='nota'>Este interesse apanha <b>%s</b> dos "
                 "anúncios por ver e <b>%s</b> do acervo todo. (O acervo "
                 "antigo em grande parte ainda não tem CPV lido, e sem "
                 "CPV nenhum anúncio entra no interesse.)</div>"
                 % (mil_pt(apanha_ver), mil_pt(apanha_tudo)))
    formulario = (
        "<div class='cx novo-filtro'><div class='rot'>Os CPV do "
        "interesse</div>"
        "<div class='nota' style='margin:6px 0 14px'>Enquanto estiver "
        "ligado, a <a href='/'>lista de anúncios</a> só mostra o que "
        "corresponde &mdash; nas quatro abas. A lista di-lo por cima de "
        "si mesma e tem sempre a porta de saída (&ldquo;ver tudo&rdquo;). "
        "Os alertas e os contratos não são tocados: o interesse é um "
        "recorte de leitura da lista, não um filtro.</div>"
        "<form method='post' action='/alertas/interesse' class='filtros'>"
        "<label><input type='checkbox' name='activo' value='1'%s> "
        "limitar a lista de anúncios a estes CPV</label>"
        "<input type='text' id='filtro-cpv' name='cpv' value='%s' readonly "
        "placeholder='CPV — escolhe na árvore aqui em baixo'>"
        "<input type='text' id='filtro-cpv-excl' name='cpv_excl' value='%s' "
        "placeholder='CPV a tirar de dentro desses…'>"
        "<button type='submit'>Guardar o interesse</button>"
        "</form>%s%s</div>"
        % (" checked" if ligado else "",
           html.escape(dentro, quote=True), html.escape(fora, quote=True),
           conta, arvore_html(n_cpv, "anuncios", submeter=False)))
    return envolver(
        "alertas", "Interesse",
        "Os CPV que a casa trabalha. A lista de anúncios passa a mostrar "
        "só isso.",
        "<div class='larg'>" + formulario + "</div>",
        migalhas=migalhas_de("alertas", "Interesse"), script=ARVORE_JS,
        titulo_aba="Interesse, Radar de Concursos")


@app.route("/alertas/interesse", methods=["POST"])
def interesse_gravar():
    """Grava o interesse. Ligado sem CPV nenhum nao esconde nada -- e o
    que condicao_do_interesse() faz --, por isso avisa-se aqui em vez de
    deixar o Afonso a pensar que ficou a limitar."""
    dentro = " ".join((request.form.get("cpv") or "").split())
    fora = " ".join((request.form.get("cpv_excl") or "").split())
    activo = bool(request.form.get("activo"))
    gravar_config({"interesse_activo": activo, "interesse_cpv": dentro,
                   "interesse_cpv_excl": fora})
    if activo and not dentro:
        aviso = ("Interesse ligado mas sem CPV escolhido — a lista "
                 "continua a mostrar tudo.")
    elif activo:
        aviso = "Interesse guardado: a lista de anúncios passa a mostrar só %s." % dentro
    else:
        aviso = "Interesse guardado e desligado: a lista mostra tudo."
    return redirect("/alertas/interesse?" + urlencode({"aviso": aviso}))


def _linha_filtro(f):
    """Um filtro na lista de gestao: o interruptor, o que apanha, e onde
    o aplicar. As ligacoes vao para as duas listas, porque o mesmo filtro
    serve as duas."""
    ligado = bool(f["alerta"])
    onde, fora_anuncios = filtro_para(f["consulta"] or "", "anuncios")
    onde_c, fora_contratos = filtro_para(f["consulta"] or "", "contratos")
    aplicar = []
    if not fora_anuncios or onde:
        aplicar.append("<a href='/?%s'>anúncios%s</a>"
                       % (html.escape(onde, quote=True),
                          " (parcial)" if fora_anuncios else ""))
    if not fora_contratos or onde_c:
        aplicar.append("<a href='/contratos?%s'>contratos%s</a>"
                       % (html.escape(onde_c, quote=True),
                          " (parcial)" if fora_contratos else ""))
    # A taxa de acerto (B06), como a Tendios mostra na ficha do alerta:
    # em que estados acabou o que este filtro marcou. So conta os
    # triados -- por ver ainda nao e opiniao -- e so aparece quando ha
    # historia que chegue para dizer alguma coisa.
    triagem = ""
    marcou = (f["interessou"] or 0) + (f["descartou"] or 0) + (f["por_triar"] or 0)
    if marcou:
        triados = (f["interessou"] or 0) + (f["descartou"] or 0)
        taxa = (" &middot; acerto <b>%s</b>" % pct_pt(f["interessou"] / triados)
                if triados else " &middot; ainda nada triado")
        triagem = ("<span class='onde'>dos %s que marcou: %s interessa "
                   "&middot; %s descartados &middot; %s por ver%s</span>"
                   % (mil_pt(marcou), mil_pt(f["interessou"] or 0),
                      mil_pt(f["descartou"] or 0), mil_pt(f["por_triar"] or 0),
                      taxa))
    return (
        "<div class='alerta %s'>"
        "<form method='post' action='/alertas/%d/trocar'>"
        "<button type='submit' class='interruptor %s' title='%s'><i></i>"
        "</button></form>"
        "<div class='sobre'><b>%s</b><span class='q'>%s</span>"
        "<span class='onde'>aplicar a: %s</span>%s</div>"
        "<div class='conta'>%s</div>"
        "<form method='post' action='/filtros/%d/apagar' "
        "onsubmit='return confirm(\"Apagar o filtro &quot;%s&quot;? "
        "Não se apaga nada além do filtro.\")'>"
        "<input type='hidden' name='volta' value='/alertas'>"
        "<button type='submit' class='apagar' title='apagar'>&times;</button>"
        "</form></div>"
        % ("on" if ligado else "", f["id"], "on" if ligado else "",
           "desligar o alerta" if ligado else "ligar o alerta",
           html.escape(f["nome"]),
           html.escape(resumo_filtro(f["consulta"] or "")),
           " &middot; ".join(aplicar) or "sem campos",
           triagem,
           ("<span class='avisa-mal'>não avisa: nada aqui é sobre "
            "anúncios</span>" if ligado and not onde else
            "<b>%s</b> por avisar &middot; %s avisados &middot; %s do acervo%s"
            % (mil_pt(f["por_enviar"]), mil_pt(f["avisados"]),
               mil_pt(f["acervo"]),
               "<span class='avisa-mal'>avisa só por %s</span>"
               % html.escape(resumo_filtro(onde)) if fora_anuncios else "")
            if ligado else "não avisa"),
           f["id"], html.escape(f["nome"], quote=True)))


def _caixa_email(cfg):
    """O destino e a hora configuram-se no ecra; a conta que **envia**
    nao.

    Quem envia sao tres coisas que andam juntas -- endereco, servidor e
    porta -- e a quarta, a palavra-passe, nunca podia estar aqui. Ter
    metade no ecra e metade num ficheiro convidava a preencher o ecra e
    a achar que estava feito. Fica tudo do lado de fora, e o painel
    mostra o que ja esta posto.
    """
    e = cfg.get("email") or {}
    tem_senha = bool(ler_chave(("email_senha.txt",), "RADAR_EMAIL_SENHA"))
    tem_conta = bool((e.get("de") or "").strip() and (e.get("servidor") or "").strip())
    pronto = bool((e.get("para") or "").strip() and tem_conta and tem_senha)
    estado = le_marca("ultimo_resumo_estado", "")

    envio = [
        ("Conta que envia", e.get("de") or "por configurar", tem_conta),
        ("Servidor", "%s:%s" % (e.get("servidor") or "—", e.get("porta") or "—"),
         tem_conta),
        ("Palavra-passe",
         "lida de email_senha.txt" if tem_senha
         else "falta o ficheiro email_senha.txt", tem_senha),
    ]
    if estado:
        envio.append(("Último envio", html.escape(estado),
                      not estado.startswith("por enviar")))

    return (
        "<div class='cx conf-email'>"
        "<div class='rot'>Resumo por e-mail</div>"
        "<div class='nota' style='margin:6px 0 16px'>Um por dia, a partir "
        "da hora marcada, e só se houver novidade.</div>"
        "<form class='form-email' method='post' action='/alertas/email'>"
        "<label>Enviar para<input type='email' name='para' value='%s' "
        "placeholder='o.teu@email.pt'></label>"
        "<label>Hora do resumo<input type='time' name='hora_resumo' "
        "value='%s'></label>"
        "<button type='submit' class='bt forte'>Guardar</button>"
        "</form>"
        "<div class='rot' style='margin:22px 0 6px'>Quem envia</div>"
        "<div class='nota' style='margin-bottom:14px'>Configura-se fora do "
        "painel, no <code>config.json</code> e no <code>email_senha.txt</code> "
        "&mdash; uma palavra-passe não se escreve num ecrã que fica aberto.</div>"
        "<div class='saude'>%s</div>%s</div>"
        % (html.escape(str(e.get("para") or ""), quote=True),
           html.escape(str(e.get("hora_resumo") or "17:00"), quote=True),
           linhas_de_saude(envio, "#d68910"),
           ("<div style='margin-top:16px'>%s</div>"
            % accao("/alertas/enviar", "Enviar o resumo agora", "bt")
            if pronto else
            "<div class='nota' style='margin-top:14px'>Enquanto não estiver "
            "pronto, o radar escreve o <code>AVISOS.txt</code> na pasta e a "
            "lista aqui em baixo mostra o mesmo.</div>")))


def _caixa_urgente():
    """A janela do "urgente", editavel no painel (B13). E UM numero,
    usado pelo filtro, pelo cartao dos indicadores e pelos rotulos --
    por isso edita-se num sitio so, e todos leem dias_urgente()."""
    return ("<div class='cx novo-filtro' style='margin-top:16px'>"
            "<div class='rot'>Janela do &ldquo;urgente&rdquo;</div>"
            "<div class='nota' style='margin:6px 0 10px'>Um anúncio é "
            "&ldquo;urgente&rdquo; quando o prazo acaba nos próximos N "
            "dias. O mesmo número serve o filtro da lista, o cartão dos "
            "indicadores e os avisos &mdash; mudar aqui muda em todo o "
            "lado.</div>"
            "<form method='post' action='/alertas/urgente' class='filtros'>"
            "<label>prazos a menos de</label>"
            "<input type='text' name='dias' value='%d' "
            "style='min-width:0;width:70px;flex:none'>"
            "<label>dias</label>"
            "<button type='submit'>Guardar</button></form></div>"
            % dias_urgente())


@app.route("/alertas/urgente", methods=["POST"])
def alertas_urgente():
    """Grava a janela do urgente (B13), com a validacao a vista: um 0
    ou lixo esvaziava o filtro sem uma palavra."""
    bruto = (request.form.get("dias") or "").strip()
    try:
        n = int(bruto)
    except ValueError:
        return redirect("/alertas?aviso=" +
                        quote("“%s” não é um número de dias." % bruto))
    if not 1 <= n <= 90:
        return redirect("/alertas?aviso=" +
                        quote("A janela do urgente vai de 1 a 90 dias."))
    gravar_config({"dias_urgente": n})
    return redirect("/alertas?aviso=" +
                    quote("Urgente passa a ser: prazo a menos de %d dias."
                          % n))


@app.route("/alertas")
def alertas():
    cfg = ler_config()
    with liga() as c:
        filtros = c.execute(
            "SELECT f.*, "
            "(SELECT COUNT(*) FROM alertas_vistos v WHERE v.filtro_id=f.id "
            " AND v.enviado_em IS NULL) por_enviar, "
            "(SELECT COUNT(*) FROM alertas_vistos v WHERE v.filtro_id=f.id "
            " AND v.enviado_em = ?) acervo, "
            "(SELECT COUNT(*) FROM alertas_vistos v WHERE v.filtro_id=f.id "
            " AND v.enviado_em IS NOT NULL AND v.enviado_em != ?) avisados, "
            # A taxa de acerto (B06): em que estados acabou o que o
            # alerta marcou. E o unico sinal de que um alerta esta mal
            # afinado -- muitos descartados e poucos interessa.
            "(SELECT COUNT(*) FROM alertas_vistos v JOIN anuncios a "
            " ON a.ref=v.ref WHERE v.filtro_id=f.id "
            " AND a.estado='interessa') interessou, "
            "(SELECT COUNT(*) FROM alertas_vistos v JOIN anuncios a "
            " ON a.ref=v.ref WHERE v.filtro_id=f.id "
            " AND a.estado='descartado') descartou, "
            "(SELECT COUNT(*) FROM alertas_vistos v JOIN anuncios a "
            " ON a.ref=v.ref WHERE v.filtro_id=f.id "
            " AND a.estado='novo') por_triar "
            "FROM filtros_guardados f "
            "ORDER BY f.alerta DESC, f.nome COLLATE NOCASE",
            (ACERVO, ACERVO)).fetchall()
        ultimos = c.execute(
            "SELECT v.ref, v.enviado_em, a.titulo, a.entidade, "
            "f.nome AS filtro FROM alertas_vistos v "
            "JOIN anuncios a ON a.ref=v.ref "
            "JOIN filtros_guardados f ON f.id=v.filtro_id "
            "WHERE v.enviado_em IS NOT NULL AND v.enviado_em != ? "
            "ORDER BY v.enviado_em DESC LIMIT 25", (ACERVO,)).fetchall()
        plataformas = [r["p"] for r in c.execute(
            "SELECT DISTINCT plataforma p FROM anuncios "
            "WHERE plataforma IS NOT NULL AND plataforma != '' ORDER BY p")]
    # Os tipos de procedimento sao do corpus, e o corpus pode nao existir.
    procs = []
    if ha_corpus():
        with liga_corpus() as c:
            procs = [r["p"] for r in c.execute(
                "SELECT tipo_procedimento p, COUNT(*) n FROM contratos "
                "WHERE tipo_procedimento!='' GROUP BY p ORDER BY n DESC "
                "LIMIT 25")]

    # As entidades seguidas (B10), ao lado dos alertas: sao a outra fonte
    # do resumo diario, e gere-se aqui o que se ve, segue-se na ficha.
    with liga() as c:
        seguidas = c.execute("SELECT chave, nome FROM entidades_seguidas "
                             "ORDER BY nome COLLATE NOCASE").fetchall()
    if seguidas:
        caixa_seguidas = (
            "<div class='cx novo-filtro' style='margin-top:16px'>"
            "<div class='rot'>Entidades seguidas</div>"
            "<div class='nota' style='margin:6px 0 10px'>Os anúncios "
            "novos destas entidades entram no resumo diário. Segue-se e "
            "deixa-se de seguir na ficha de cada uma.</div>"
            "<div class='guardados'>%s</div></div>"
            % "".join("<span class='guardado'><a href='/entidade/%s'>%s"
                      "</a></span>"
                      % (quote(s["chave"], safe=""), html.escape(s["nome"]))
                      for s in seguidas))
    else:
        caixa_seguidas = ""

    if filtros:
        lista = "<div class='alertas'>%s</div>" % "".join(
            _linha_filtro(f) for f in filtros)
    else:
        lista = ("<div class='vazio'>Ainda não há filtros. Cria um aqui em "
                 "baixo, ou afina a pesquisa na <a href='/anuncios'>"
                 "Pesquisa</a> ou nos <a href='/contratos'>contratos</a> e "
                 "guarda-a com um nome &mdash; é o mesmo filtro.</div>")

    # O que se tinha escrito quando a validacao recusou: vem na query
    # string do redirect e volta para os campos, em vez de se perder.
    def pv(campo):
        return html.escape(request.args.get(campo, ""), quote=True)

    def marca_sel(campo, valor, omissao=""):
        return " selected" if request.args.get(campo, omissao) == valor else ""

    # Criar um filtro aqui, sem ter de ir a uma lista primeiro.
    novo = (
        "<div class='cx novo-filtro'><div class='rot'>Novo filtro</div>"
        "<div class='nota' style='margin:6px 0 14px'>Um filtro é um "
        "conjunto de campos. Cada página aplica os que entende &mdash; um "
        "filtro por CPV serve os anúncios e os contratos; um por "
        "&ldquo;quem ganhou&rdquo; só faz sentido nos contratos, e nos "
        "anúncios fica marcado como parcial.</div>"
        # Os campos todos, e nao metade. O formulario oferecia seis dos
        # treze campos que um filtro tem: nao dava para criar aqui um
        # filtro por plataforma, por estado, por tipo de procedimento nem
        # por valor -- coisas que se punham nas outras paginas e se
        # guardavam de la. Eram dois caminhos para a mesma coisa, e um
        # deles secretamente mais fraco do que o outro.
        #
        # POST, como tudo o que escreve. E os campos vem preenchidos da
        # query string: quando a validacao recusa, o redirect traz o que
        # se tinha escrito -- antes vinha tudo vazio, nome incluido.
        "<form method='post' action='/alertas/criar' class='filtros'>"
        "<input type='text' name='nome' required maxlength='60' value='%s' "
        "placeholder='nome do filtro…'>"
        "<input type='text' name='q' value='%s' placeholder='Objecto…'>"
        "<input type='text' name='q_excl' value='%s' "
        "placeholder='Excluir palavras…'>"
        # a ver e nao escondido: aqui nao ha lista por baixo a mostrar o
        # resultado, e sem isto nao se sabia o que a arvore tinha posto
        "<input type='text' id='filtro-cpv' name='cpv' value='%s' readonly "
        "placeholder='CPV — escolhe na árvore aqui em baixo'>"
        "<input type='text' id='filtro-cpv-excl' name='cpv_excl' value='%s' "
        "placeholder='Excluir CPV — escreve os códigos…'>"
        "<select name='op' title='como juntar as palavras e o CPV'>%s</select>"
        "<input type='text' name='ent' value='%s' placeholder='Entidade que "
        "publica (anúncios)…'>"
        "<input type='text' name='adj' value='%s' placeholder='Entidade que "
        "comprou (contratos)…'>"
        "<input type='text' name='ganhou' value='%s' "
        "placeholder='Quem ganhou (contratos)…'>"
        "<select name='plat'>%s</select>"
        "<select name='estado'>%s</select>"
        "<select name='prazo'>%s</select>"
        "%s"
        "<label>de</label><input type='date' name='de' value='%s'>"
        "<label>até</label><input type='date' name='ate' value='%s'>"
        "<label>desde</label><input type='text' name='min' value='%s' "
        "placeholder='€ mínimo (contratos)' "
        "style='min-width:0;width:150px;flex:none'>"
        "<button type='submit'>Criar filtro</button>"
        "</form>%s</div>"
        % (pv("nome"), pv("q"), pv("q_excl"), pv("cpv"), pv("cpv_excl"),
           opcoes_op(request.args), pv("ent"), pv("adj"), pv("ganhou"),
           "".join(["<option value=''>plataforma: qualquer uma "
                    "(anúncios)</option>"]
                   + ["<option value='%s'%s>%s</option>"
                      % (html.escape(p, quote=True), marca_sel("plat", p),
                         html.escape(p))
                      for p in plataformas]
                   + ["<option value='%s'%s>sem plataforma indicada</option>"
                      % (html.escape(SEM_PLATAFORMA, quote=True),
                         marca_sel("plat", SEM_PLATAFORMA)),
                      "<option value='%s'%s>ainda sem detalhe lido</option>"
                      % (html.escape(POR_LER, quote=True),
                         marca_sel("plat", POR_LER))]),
           # "triagem" e nao "estado": e o nome do grupo por ver/
           # interessa/descartados em todo o lado (§7 do ESQUELETO)
           "".join("<option value='%s'%s>%s</option>"
                   % (v, marca_sel("estado", v, omissao="novo"), t)
                   for v, t in (("novo", "triagem: só os por ver"),
                                ("", "triagem: todos"),
                                ("interessa", "triagem: só os interessa"),
                                ("descartado", "triagem: só os abandonados"))),
           "".join("<option value='%s'%s>%s</option>"
                   % (v, marca_sel("prazo", v), t)
                   for v, t in (("", "prazo: tanto faz"),
                                ("aberto", "prazo: só os que ainda dão"),
                                ("urgente", "prazo: só os que acabam em %d "
                                            "dias" % dias_urgente()),
                                ("expirado", "prazo: só os passados"))),
           (selector_procedimento(procs,
                                  (request.args.get("proc") or "").strip(),
                                  "procedimento: todos (contratos)")
            if procs else ""),
           pv("de"), pv("ate"), pv("min"),
           arvore_html(quantos_cpv(), "anuncios", submeter=False)))

    if ultimos:
        hist = "".join(
            "<tr><td class='d'>%s</td><td class='o'>"
            "<a href='/anuncio/%s'>%s</a></td><td>%s</td><td>%s</td></tr>"
            % (data_pt(r["enviado_em"]), quote(r["ref"], safe=""),
               html.escape(corta(r["titulo"] or r["ref"], 80)),
               html.escape(corta(r["entidade"], 44)),
               html.escape(r["filtro"]))
            for r in ultimos)
        historico = ("<div class='cx tab-cx'><table class='tab-contratos'>"
                     "<thead><tr><th>Avisado</th><th>Anúncio</th>"
                     "<th>Entidade</th><th>Filtro</th></tr></thead>"
                     "<tbody>%s</tbody></table></div>" % hist)
    else:
        historico = ("<div class='nota'>Ainda não saiu nenhum aviso. Sai no "
                     "resumo a seguir à próxima verificação.</div>")

    conteudo = ("<div class='larg'>" + _caixa_interesse() + lista +
                caixa_seguidas +
                "<div style='height:16px'></div>" + novo +
                "<div style='height:16px'></div>" + _caixa_email(cfg) +
                _caixa_urgente() +
                "<div class='rot' style='margin:22px 0 12px'>Últimos avisos"
                "</div>" + historico + "</div>")

    return envolver(
        "alertas", "Filtros e alertas",
        "Os filtros são os mesmos em toda a aplicação. Os que marcares "
        "como alerta avisam-te quando entra um anúncio que lhes "
        "corresponde.", conteudo, script=ARVORE_JS,
        titulo_aba="Alertas, Radar de Concursos")


@app.route("/alertas/criar", methods=["POST"])
def alerta_criar():
    """Cria um filtro a partir do formulario do separador.

    POST, como tudo o que escreve -- foi GET, com a justificacao de que
    os campos vinham de um formulario de pesquisa, mas o gravar_filtro
    escreve na base e a regra da casa nao abre excepcoes. Quando a
    validacao recusa, o redirect leva os campos na query string e o
    formulario volta preenchido: perdia-se tudo, nome incluido."""
    nome = (request.form.get("nome") or "").strip()
    # O `estado` entra mesmo vazio, como em condicoes() e em
    # filtro_actual(): ausente e "por ver", vazio e "todos". Sem esta
    # excepcao, escolher "todos" aqui gravava um filtro sem estado, que
    # e o mesmo que "por ver" -- o contrario do que se pediu.
    pares = []
    for k in CAMPOS_FILTRO:
        valor = (request.form.get(k) or "").strip()
        if valor or (k == "estado" and request.form.get(k) is not None):
            pares.append((k, valor))

    def recusa(mensagem):
        return redirect("/alertas?" + urlencode(
            [("aviso", mensagem), ("nome", nome)] + pares))

    if not nome:
        return recusa("O filtro precisa de nome.")
    consulta = urlencode(pares)
    if not [k for k, v in pares if v and k not in ("estado", "op")]:
        return recusa("Preenche pelo menos um campo além do estado.")
    havia = gravar_filtro(nome, consulta)
    return redirect("/alertas?aviso=" +
                    quote("Filtro %s: %s"
                          % ("actualizado" if havia else "criado", nome)))


@app.route("/alertas/email", methods=["POST"])
def alertas_email():
    """So o destino e a hora. A conta que envia nao passa por aqui: um
    formulario que a aceitasse convidava a preencher meia configuracao e
    a achar que estava feita, com a palavra-passe sempre de fora."""
    gravar_config({"email": {
        "para": (request.form.get("para") or "").strip(),
        "hora_resumo": (request.form.get("hora_resumo") or "17:00").strip(),
    }})
    return redirect("/alertas?aviso=" + quote("Configuração do e-mail guardada."))


@app.route("/alertas/<int:filtro_id>/trocar", methods=["POST"])
def alerta_trocar(filtro_id):
    with liga() as c:
        c.execute("UPDATE filtros_guardados SET alerta = 1 - COALESCE(alerta,0) "
                  "WHERE id=?", (filtro_id,))
    # Ao ligar um alerta, o que ja esta na base conta como acervo e nao
    # como novidade -- senao o primeiro resumo trazia o acervo todo.
    registar_alertas()
    with liga() as c:
        r = c.execute("SELECT alerta FROM filtros_guardados WHERE id=?",
                      (filtro_id,)).fetchone()
        if r and r["alerta"]:
            c.execute("UPDATE alertas_vistos SET enviado_em=? "
                      "WHERE filtro_id=? AND enviado_em IS NULL",
                      (ACERVO, filtro_id))
    return redirect("/alertas")


@app.route("/entidade/procurar")
def entidade_procurar():
    """11.7-B, reaberta pelo Afonso a 31/08/2026: procurar uma entidade
    por nome ou NIF e ir directo a ficha, sem abrir um contrato
    qualquer so para la chegar. A resolucao passa por entidade_nomes --
    a tabela que ja mapeia qualquer das 87 grafias de uma entidade a
    chave dela; o custo era so de ecra."""
    if not ha_corpus():
        return sem_corpus_html("Procurar entidade")
    termo = (request.args.get("q") or "").strip()
    if not termo:
        return redirect("/contratos?aviso=" +
                        quote("Escreve um nome ou um NIF para procurar."))
    with liga_corpus() as c:
        # Um NIF e a propria chave do corpus: vai directo
        digitos = re.sub(r"\D", "", termo)
        if digitos and digitos == termo.replace(" ", ""):
            r = c.execute("SELECT chave FROM entidades WHERE chave=?",
                          (digitos,)).fetchone()
            if r:
                return redirect("/entidade/" + quote(r["chave"], safe=""))
        # O nome procura-se em TODAS as grafias (entidade_nomes), com a
        # norma certa -- procurar com simplifica() perdia 11,8%
        achadas = c.execute(
            "SELECT DISTINCT e.chave, e.nome, e.variantes "
            "FROM entidade_nomes n JOIN entidades e ON e.chave = n.chave "
            "WHERE n.nome_norm LIKE ? ESCAPE '%s' "
            "ORDER BY e.nome COLLATE NOCASE LIMIT 25" % ESCAPE_LIKE,
            ("%" + para_like(norma_entidade(termo)) + "%",)).fetchall()
    if len(achadas) == 1:
        return redirect("/entidade/" + quote(achadas[0]["chave"], safe=""))
    if achadas:
        linhas = "".join(
            "<div class='hist'><a href='/entidade/%s'>%s</a>%s</div>"
            % (quote(e["chave"], safe=""), html.escape(e["nome"] or ""),
               "<span class='sem-nif'>sem NIF</span>"
               if e["chave"].startswith("n:") else "")
            for e in achadas)
        corpo = ("<div class='larg'><div class='cx lado-cx'>"
                 "<div class='rot' style='margin-bottom:10px'>"
                 "%d entidades respondem a &ldquo;%s&rdquo; &mdash; "
                 "escolhe a ficha</div>%s</div></div>"
                 % (len(achadas), html.escape(termo), linhas))
    else:
        corpo = ("<div class='larg'><div class='vazio'>Nenhuma entidade "
                 "do corpus responde a &ldquo;%s&rdquo;. O corpus só "
                 "conhece quem já assinou contratos desde %s. "
                 "<a href='/contratos'>Voltar aos contratos</a></div></div>"
                 % (html.escape(termo), "2020"))
    return envolver(
        "contratos", "Procurar entidade",
        "Nome ou NIF; a procura cobre todas as grafias com que cada "
        "entidade já assinou.",
        corpo, migalhas=migalhas_de("contratos", "procurar"),
        titulo_aba="Procurar entidade, Radar de Concursos")


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

    O modo dos contratos (6.1-A) entra na conta: no modo fim estimado
    os graficos respondem sobre os contratos a acabar na janela -- o
    mesmo conjunto que a tabela mostra, senao o grafico e a lista
    discordavam no mesmo ecra.
    """
    onde, valores = filtros_dos_contratos(args)
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
        # O desconto agrega por procedimento, nao por linha -- ver
        # descontos_por_procedimento(), que tambem diz o que fica de fora.
        desc = descontos_por_procedimento(c, onde, valores)
    return ganha, compra, proc, trim, escal, desc


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
CAMPOS_FICHA = CAMPOS_POR_VISTA["entidade"]


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
    return any((args.get(campo) or "").strip() for campo in CAMPOS_FICHA
               if campo != "op")


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


# Escaloes do desconto sobre o preco base, em percentagem: cada corte e
# o limite superior do escalao, e o ultimo apanha o resto. As etiquetas
# constroem-se desta lista, para nao se mudar uma sem a outra.
LIMITES_DESCONTO = (5, 10, 20, 30, 50)

# Abaixo disto nao ha padrao, ha meia duzia de casos: nem o grafico nem
# a linha da ficha aparecem.
MINIMO_PARA_DESCONTO = 5


def escaloes_de_desconto(descontos):
    """([(etiqueta, quantos)], mediana) dos descontos por procedimento.

    Os descontos vem em fraccao (0..1). A mediana e exacta -- os
    conjuntos aqui sao pequenos, nao os 400 mil dos escaloes de valor.
    """
    if not descontos:
        return [], None
    ordenados = sorted(descontos)
    meio = len(ordenados) // 2
    mediana = (ordenados[meio] if len(ordenados) % 2
               else (ordenados[meio - 1] + ordenados[meio]) / 2.0)
    contagens = [0] * (len(LIMITES_DESCONTO) + 1)
    for d in descontos:
        for i, lim in enumerate(LIMITES_DESCONTO):
            if 100.0 * d < lim:
                contagens[i] += 1
                break
        else:
            contagens[-1] += 1
    etiquetas, baixo = [], 0
    for lim in LIMITES_DESCONTO:
        etiquetas.append("%d–%d%%" % (baixo, lim))
        baixo = lim
    etiquetas.append("%d%%+" % baixo)
    return list(zip(etiquetas, contagens)), mediana


def pct_pt(fraccao):
    """0.073 -> '7,3%'. Virgula decimal, como o resto dos numeros."""
    return ("%.1f" % (100.0 * fraccao)).replace(".", ",") + "%"


def descontos_por_procedimento(c, onde, valores):
    """Os descontos (0..1) sobre o preco base, POR PROCEDIMENTO.

    Agregado por `n_anuncio` e nunca por linha: num procedimento com
    lotes, cada linha traz o preco base do procedimento inteiro, e a
    conta por linha compara um lote pequeno com a base toda -- a media
    ingenua dava -18,9%% no corpus, um numero que mente (B04, validado
    contra 20 casos a mao a 30/08/2026).

    Fica de fora o que nao se sabe ler: procedimentos sem anuncio, sem
    preco base, com a base a VARIAR entre lotes (5 388 grupos; ai a base
    e por lote e a semantica e outra) e com a soma contratual acima da
    base (4 275 grupos de ruido). Sobra o conjunto limpo: 97 130
    procedimentos no corpus inteiro.
    """
    return [r["d"] for r in c.execute(
        "SELECT 1.0 - SUM(c.preco_contratual)/MAX(c.preco_base) d"
        " FROM contratos c" + onde +
        " AND c.n_anuncio != '' AND c.preco_base > 0"
        " AND c.preco_contratual > 0"
        " GROUP BY c.n_anuncio"
        " HAVING MIN(c.preco_base) = MAX(c.preco_base)"
        " AND SUM(c.preco_contratual) <= MAX(c.preco_base)", valores)]


def desconto_html(descontos):
    """O grafico do desconto: por quanto abaixo do preco base se tem
    fechado. E a versao honesta da 'previsao de preco' dos concorrentes:
    sem numero inventado, so o que os pares base/contratual do dump
    mostram."""
    if len(descontos) < MINIMO_PARA_DESCONTO:
        return ""
    escaloes, mediana = escaloes_de_desconto(descontos)
    linhas = [{"t": e, "v": float(k), "k": mil_pt(k)} for e, k in escaloes]
    return barras_v(
        linhas, "Desconto sobre o preço base",
        "Por procedimento &mdash; os lotes somam-se antes de dividir, "
        "senão o número mentia. Só onde o dump traz anúncio e preço base "
        "sem ambiguidade: %s procedimento%s. Desconto mediano: <b>%s</b>."
        % (mil_pt(len(descontos)), "" if len(descontos) == 1 else "s",
           pct_pt(mediana)),
        fmt=mil_pt_f, unidade="procedimentos")


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


def barras_v(linhas, titulo, nota="", parcial="", destaque="", fmt=None,
             unidade="contratos"):
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
            "<div class='b' style='height:%.1f%%' title='%s %s%s'>"
            "</div><span class='l'>%s</span></div>"
            % (classes, fmt(l["v"]),
               max(2.0, 100.0 * l["v"] / maior), l["k"], unidade,
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
    ganha, compra, proc, trim, escal, desc = resumo_contratos(request.args)
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
        desconto_html(desc),
        evolucao_html(trim),
    ]
    return Response("".join(partes), mimetype="text/html")


def liga_entidade(chave, nome, classe=""):
    """O nome de uma entidade, a levar para a ficha dela.

    Quem nao tem NIF fica marcado. 10% dos adjudicatarios do dump do
    IMPIC vem sem NIF e agrupam-se pelo nome, o que faz a mesma empresa
    aparecer duas vezes no "quem ganha" -- uma pelo NIF, com 31
    contratos, e outra pelo nome, com um. Sao dados do IMPIC e nao ha
    como junta-los, mas uma linha explicada deixa de parecer um erro de
    contagem.
    """
    if not chave:
        return html.escape(nome or "—")
    sem_nif = ("<span class='sem-nif' title='este contrato veio do IMPIC sem "
               "NIF; agrupa-se pelo nome e pode ser a mesma empresa que "
               "outra linha'>sem NIF</span>") if chave.startswith("n:") else ""
    return ("<a class='%s' href='/entidade/%s'>%s</a>%s"
            % (classe, quote(chave, safe=""), html.escape(nome or chave),
               sem_nif))


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
    outros = {c: (request.args.get(c) or "").strip() for c in CAMPOS_FICHA
              if c != "cpv" and (request.args.get(c) or "").strip()}
    faixa = faixa_cpv_activo(request.args,
                             "/entidade/%s?%s" % (quote(chave, safe=""),
                                                  urlencode(outros)))

    with liga() as c:
        n_cpv = c.execute("SELECT COUNT(*) n FROM cpv_dict").fetchone()["n"]

    # O campo do CPV e escondido e quem escolhe e a arvore, como nas duas
    # listas: onde se pode procurar por CPV, pode-se escolher mais que um.
    return (
        "<form class='cx filtros ent-filtros' method='get' action='/entidade/%s'>"
        "<input type='text' name='q' value='%s' placeholder='Objecto do contrato…'>"
        "<input type='text' name='q_excl' value='%s' "
        "placeholder='Excluir palavras…'>"
        "<input type='hidden' id='filtro-cpv' name='cpv' value='%s'>"
        "<input type='text' id='filtro-cpv-excl' name='cpv_excl' value='%s' "
        "placeholder='Excluir CPV…' "
        "style='min-width:0;width:120px;flex:none'>"
        "<label>de</label><input type='date' name='de' value='%s'>"
        "<label>até</label><input type='date' name='ate' value='%s'>"
        "<input type='text' name='min' value='%s' placeholder='€ mínimo' "
        "style='min-width:0;width:110px;flex:none'>"
        "<button type='submit'>Filtrar</button>%s"
        "<div class='periodos'><span>rápido:</span>%s</div>"
        "</form>%s%s%s%s"
        % (quote(chave, safe=""), v("q"), v("q_excl"), v("cpv"),
           v("cpv_excl"), v("de"), v("ate"),
           v("min"), limpar, "".join(chips),
           faixa_de_avisos_de_datas(request.args), faixa,
           arvore_html(n_cpv, "contratos"),
           # os mesmos filtros guardados dos contratos, mas a voltar para
           # esta ficha e so com os campos que ela entende
           caixa_de_filtros(request.args, "entidade",
                            rota="/entidade/" + quote(chave, safe=""))))


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
        # "o que desta entidade esta a acabar" e a pergunta comercial da
        # ficha (atalho da §5 do ESQUELETO): o modo fim com a mesma chave
        ligacoes.append("<a href='%s&ver=fim'>o que está a acabar "
                        "(fim estimado)</a>" % para_lista("entid"))
    if ganha["k"]:
        ligacoes.append("<a href='%s'>ver os %s que ganhou</a>"
                        % (para_lista("vencid"), mil_pt(ganha["k"])))
    atalhos = "<div class='ent-atalhos'>%s</div>" % "".join(ligacoes)

    # Seguir a entidade (B10): os anuncios novos dela entram no resumo
    # diario, ao lado dos alertas. O botao diz o estado e troca-o.
    with liga() as c:
        seguida = c.execute("SELECT 1 FROM entidades_seguidas WHERE chave=?",
                            (chave,)).fetchone() is not None
    if chave.startswith("n:"):
        seguir_cx = ""     # sem NIF nao ha como casar com os anuncios
    else:
        seguir_cx = (
            "<div class='ent-atalhos'>%s%s</div>"
            % (accao("/entidade/%s/seguir" % quote(chave, safe=""),
                     "Deixar de seguir" if seguida else
                     "Seguir esta entidade",
                     "bt" if seguida else "bt forte"),
               "<span class='nota' style='align-self:center'>"
               "a seguir &mdash; os anúncios novos dela entram no resumo "
               "diário</span>" if seguida else ""))

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
               # corta(), nunca [:n] cru: "…as Base de Dado" le-se como
               # dado estragado -- era o ultimo [:n] visivel que restava
               html.escape(corta(r["objecto"] or "", 130)),
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
                atalhos + seguir_cx + "<div class='graf-corpo solto'>" +
                "".join(blocos) + "</div>" + recentes + "</div>")

    return envolver(
        "contratos", d["nome"],
        "O que esta entidade compra e ganha, segundo o Portal BASE.",
        conteudo, script=ARVORE_JS,
        migalhas=migalhas_de("contratos", d["nome"][:44]),
        titulo_aba="%s, Radar de Concursos" % d["nome"][:40])


@app.route("/entidade/<path:chave>/seguir", methods=["POST"])
def entidade_seguir(chave):
    """Liga ou desliga o seguimento (B10). Ao ligar, o que a entidade ja
    tem na base entra como ACERVO -- o primeiro resumo nao traz tudo."""
    with liga() as c:
        seguida = c.execute("SELECT 1 FROM entidades_seguidas WHERE chave=?",
                            (chave,)).fetchone()
    if seguida:
        with liga() as c:
            c.execute("DELETE FROM entidades_seguidas WHERE chave=?", (chave,))
            c.execute("DELETE FROM seguidas_vistos WHERE chave=?", (chave,))
        aviso = "Deixaste de seguir a entidade."
    else:
        nome = chave
        if ha_corpus():
            with liga_corpus() as c:
                r = c.execute("SELECT nome FROM entidades WHERE chave=?",
                              (chave,)).fetchone()
            if r:
                nome = r["nome"]
        with liga() as c:
            c.execute("INSERT OR REPLACE INTO entidades_seguidas VALUES (?,?,?)",
                      (chave, nome, datetime.now().strftime("%Y-%m-%d")))
        registar_seguidas(marcar_como=ACERVO, so_chave=chave)
        aviso = "A seguir. Os anúncios novos desta entidade entram no resumo diário."
    return redirect("/entidade/%s?aviso=%s"
                    % (quote(chave, safe=""), quote(aviso)))


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
    vista = "renovacoes" if modo_fim(request.args) else "contratos"
    if not any((request.args.get(campo) or "").strip()
               for campo in campos_da_vista(vista)):
        return redirect("/contratos?aviso=" +
                        quote("Filtra primeiro: o corpus inteiro não se exporta."))
    # O mesmo filtro E o mesmo modo da lista (6.1-A): a ligacao
    # "exportar as N linhas" do modo fim tem de dar as mesmas N.
    onde, valores = filtros_dos_contratos(request.args)
    ordem = (" ORDER BY c.fim_estimado, c.id" if modo_fim(request.args)
             else " ORDER BY c.data_celebracao DESC, c.id DESC")
    with liga_corpus() as c:
        linhas = c.execute(
            "SELECT c.data_celebracao, c.fim_estimado, c.objecto, "
            "COALESCE(e.nome, c.adjudicante) adjudicante, "
            "(SELECT group_concat(COALESCE(g.nome, a.nome), ' + ') "
            " FROM contrato_adjudicatario a "
            " LEFT JOIN entidades g ON g.chave=a.chave "
            " WHERE a.contrato_id=c.id) adjudicatarios, "
            "c.tipo_procedimento, c.preco_contratual, c.preco_base, "
            "c.cpv, c.prazo_execucao, c.local_execucao, c.n_anuncio "
            "FROM contratos c LEFT JOIN entidades e "
            " ON e.chave=c.adjudicante_chave" + onde +
            ordem + " LIMIT ?",
            valores + [TECTO_CSV]).fetchall()
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";")
    escritor.writerow(["Celebrado", "Fim estimado", "Objecto",
                       "Entidade que comprou",
                       "Quem ganhou", "Procedimento", "Preço contratual (EUR)",
                       "Preço base (EUR)", "CPV", "Prazo (dias)", "Local",
                       "Anúncio"])
    for a in linhas:
        # o mesmo formato do CSV dos anuncios: data portuguesa e numero
        # com virgula decimal. Eram duas exportacoes da mesma aplicacao a
        # escrever dinheiro de duas maneiras, e nenhuma servia o Excel.
        escritor.writerow([data_pt(a["data_celebracao"]),
                           data_pt(a["fim_estimado"], ""), a["objecto"],
                           a["adjudicante"], a["adjudicatarios"],
                           a["tipo_procedimento"],
                           numero_csv(a["preco_contratual"]),
                           numero_csv(a["preco_base"]), a["cpv"],
                           a["prazo_execucao"], a["local_execucao"],
                           a["n_anuncio"]])
    return Response("﻿" + saida.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition":
                             "attachment; filename=" + nome_csv("contratos")})


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
               html.escape(data_hora_pt(quando)), direita, aviso))


def refs_com_anuncio(refs):
    """Dos n_anuncio dados, quais existem mesmo como anuncios na base.

    E o inverso do B02 (atalho da §5 do ESQUELETO): um contrato cujo
    procedimento teve anuncio no radar leva a ficha dele. So quando o
    ref existe -- 4 917 dos 5 391 comuns tinham ficha na ultima
    medicao, e nos outros a ligacao dava um 404.
    """
    limpos = [r for r in {(r or "").strip() for r in refs} if r]
    if not limpos:
        return set()
    with liga() as c:
        return {r["ref"] for r in c.execute(
            "SELECT ref FROM anuncios WHERE ref IN (%s)"
            % ",".join("?" * len(limpos)), limpos)}


@app.route("/contratos")
def contratos():
    if not ha_corpus():
        return sem_corpus_html("Contratos celebrados")

    # Dois modos, um ecra (decisao 6.1-A): "ver por celebracao" (o que
    # ja se comprou) ou "ver por fim estimado" (o que vai acabar -- as
    # antigas Renovacoes). O modo diz-se por extenso no titulo da
    # tabela, nao so no selector: e a defesa contra o ecra bifacetado.
    fim = modo_fim(request.args)
    vista = "renovacoes" if fim else "contratos"
    meses = meses_pedidos(request.args)

    # Sem filtro nao se mostra lista nenhuma. Sao 1,36 milhoes de
    # contratos: por data, sem mais nada, as primeiras 20 nao dizem nada
    # a ninguem -- e era essa consulta que punha a pagina a 48 segundos.
    # Aqui a pergunta vem primeiro, ao contrario dos anuncios, onde a
    # lista inteira e o acervo por triar e faz sentido ve-la.
    # O "op" nao conta como pergunta: e um modo, nao um filtro -- sozinho
    # nao restringe nada e abria o corpus inteiro. No modo fim, de/ate
    # tambem nao contam: o modo poe-nos de lado (campos da vista).
    ha_pergunta = any((request.args.get(campo) or "").strip()
                      for campo in campos_da_vista(vista)
                      if campo != "op")

    onde, valores = filtros_dos_contratos(request.args)
    ordem_c = (" ORDER BY c.fim_estimado, c.id" if fim
               else " ORDER BY c.data_celebracao DESC, c.id DESC")
    ordem_p = (" ORDER BY p.fim_estimado, p.id" if fim
               else " ORDER BY p.data_celebracao DESC, p.id DESC")
    correspondem = valor = 0
    paginas = pagina = 1
    linhas = []
    with liga_corpus() as c:
        if ha_pergunta:
            resumo = c.execute(
                "SELECT COUNT(*) n, COALESCE(SUM(c.preco_contratual),0) v "
                "FROM contratos c" + onde, valores).fetchone()
            correspondem, valor = resumo["n"], resumo["v"]
            paginas = max(1, -(-correspondem // POR_PAGINA_LISTA))
            pagina = min(max(1, pagina_pedida(request.args)), paginas)
            # Escolhem-se primeiro as 20 linhas, e so depois se lhes vao
            # buscar os nomes: com o LEFT JOIN e as subconsultas por
            # linha a correrem antes do LIMIT, isto levava 45 segundos no
            # corpus de sete anos. E a mesma armadilha do "quem ganha".
            linhas = c.execute(
                "WITH pag AS (SELECT c.* FROM contratos c" + onde +
                ordem_c + " LIMIT ? OFFSET ?)"
                " SELECT p.*, COALESCE(e.nome, p.adjudicante) adj_nome,"
                " (SELECT group_concat(COALESCE(g.nome, a.nome), '|')"
                "  FROM contrato_adjudicatario a"
                "  LEFT JOIN entidades g ON g.chave=a.chave"
                "  WHERE a.contrato_id=p.id) ganhou,"
                " (SELECT group_concat(a.chave, '|') FROM contrato_adjudicatario a"
                "  WHERE a.contrato_id=p.id) ganhou_ch"
                " FROM pag p LEFT JOIN entidades e"
                "  ON e.chave=p.adjudicante_chave" + ordem_p,
                valores + [POR_PAGINA_LISTA, (pagina - 1) * POR_PAGINA_LISTA]).fetchall()
        procs = [r["p"] for r in c.execute(
            "SELECT tipo_procedimento p, COUNT(*) n FROM contratos "
            "WHERE tipo_procedimento!='' GROUP BY p ORDER BY n DESC")]
        anos = [r["a"] for r in c.execute(
            "SELECT DISTINCT ano a FROM contratos ORDER BY a")]
        # O fim da janela vem do mesmo relogio que a filtra: e o date()
        # do SQLite que define "+N meses", nao uma conta de dias a parte
        # que dissesse outra data no cabecalho.
        fim_janela = c.execute("SELECT date('now', '+%d months') f"
                               % meses).fetchone()["f"] if fim else ""
    with liga() as c:
        n_cpv = c.execute("SELECT COUNT(*) n FROM cpv_dict").fetchone()["n"]

    def v(nome):
        return html.escape(request.args.get(nome, ""), quote=True)

    # No modo fim, de/ate desactivam-se COM explicacao (B03: dois eixos
    # do tempo na mesma pagina confundiam) -- um campo que some sem
    # explicacao e o silencio que a P3 proibe. Desactivado nao submete,
    # e o motor tambem os ignora (filtros_dos_contratos).
    trava_datas = (" disabled title='no modo por fim estimado o eixo do "
                   "tempo é a janela do fim — as datas de celebração não "
                   "se aplicam'" if fim else "")
    escondidos_modo = ("<input type='hidden' name='ver' value='fim'>"
                       if fim else "")
    opcoes_meses = ("<select name='meses'>%s</select>" % "".join(
        "<option value='%d'%s>terminam em %d meses</option>"
        % (m, " selected" if m == meses else "", m)
        for m in MESES_RENOVACOES)) if fim else ""
    modo_limpo = "/contratos?ver=fim" if fim else "/contratos"

    filtros = (
        "<form class='cx filtros' method='get' action='/contratos'>"
        "%s"
        "<input type='text' name='q' value='%s' placeholder='Objecto do contrato…'>"
        "<input type='text' name='q_excl' value='%s' placeholder='Excluir palavras…'>"
        "<input type='text' name='adj' value='%s' placeholder='Entidade que comprou…'>"
        "<input type='text' name='ganhou' value='%s' placeholder='%s'>"
        # Escondido, como nos anuncios: quem escolhe o CPV e a arvore, e
        # uma caixa de texto ao lado dela so convidava a escrever a mao um
        # codigo que a arvore a seguir apagava. O id e o mesmo nos dois
        # separadores -- e por ele que a arvore le e escreve. A exclusao
        # e caixa de texto: a arvore nao lhe toca.
        "<input type='hidden' id='filtro-cpv' name='cpv' value='%s'>"
        "<input type='text' id='filtro-cpv-excl' name='cpv_excl' value='%s' "
        "placeholder='Excluir CPV…' "
        "style='min-width:0;width:130px;flex:none'>"
        "<select name='op' title='como juntar as palavras e o CPV'>%s</select>"
        "%s%s"
        "<label>de</label><input type='date' name='de' value='%s'%s>"
        "<label>até</label><input type='date' name='ate' value='%s'%s>"
        "<label>desde</label><input type='text' name='min' value='%s' "
        "placeholder='€ mínimo' style='min-width:0;width:110px;flex:none'>"
        "<button type='submit'>Filtrar</button>"
        "<a class='limpar' href='%s'>limpar</a>"
        "</form>"
        % (escondidos_modo, v("q"), v("q_excl"), v("adj"), v("ganhou"),
           "Quem tem o contrato…" if fim else "Quem ganhou…",
           v("cpv"), v("cpv_excl"), opcoes_op(request.args),
           selector_procedimento(procs,
                                 (request.args.get("proc") or "").strip()),
           opcoes_meses,
           "" if fim else v("de"), trava_datas,
           "" if fim else v("ate"), trava_datas,
           v("min"), html.escape(modo_limpo, quote=True)))

    hoje = datetime.now().date()
    if linhas:
        # o inverso do B02: quando o procedimento teve anuncio no radar,
        # a linha leva a ficha dele (so os refs que existem mesmo)
        com_ficha = refs_com_anuncio([l["n_anuncio"] for l in linhas])
        corpo = []
        for l in linhas:
            # os adjudicatarios vem em duas listas paralelas (nome e
            # chave), separadas por | -- a virgula ja aparece nos nomes
            nomes = (l["ganhou"] or "").split("|")
            chaves = (l["ganhou_ch"] or "").split("|")
            venceu = " + ".join(
                liga_entidade(ch, n) for n, ch in zip(nomes, chaves)
                if n) or "—"
            objecto = html.escape(corta(l["objecto"], 150))
            if (l["n_anuncio"] or "").strip() in com_ficha:
                objecto += (" &middot; <a href='/anuncio/%s'>anúncio</a>"
                            % (l["n_anuncio"] or "").strip())
            if fim:
                # o fim primeiro, com a contagem: e o eixo deste modo
                try:
                    dias = (datetime.strptime(l["fim_estimado"],
                                              "%Y-%m-%d").date() - hoje).days
                    falta = ("hoje" if dias <= 0 else
                             "em %s dia%s" % (mil_pt(dias),
                                              "" if dias == 1 else "s"))
                except (TypeError, ValueError):
                    falta = ""
                corpo.append(
                    "<tr><td class='d'><b>%s</b><br>"
                    "<span class='nota'>%s</span></td>"
                    "<td class='o'>%s</td><td>%s</td><td class='g'>%s</td>"
                    "<td class='d'>%s</td><td class='p'>%s</td></tr>"
                    % (data_pt(l["fim_estimado"]), falta, objecto,
                       liga_entidade(l["adjudicante_chave"],
                                     l["adj_nome"] or ""),
                       venceu, data_pt(l["data_celebracao"]),
                       euros(l["preco_contratual"])))
            else:
                corpo.append(
                    "<tr><td class='d'>%s</td><td class='d'>%s</td>"
                    "<td class='o'>%s</td>"
                    "<td>%s</td><td class='g'>%s</td><td>%s</td>"
                    "<td class='p'>%s</td></tr>"
                    % (data_pt(l["data_celebracao"]),
                       data_pt(l["fim_estimado"], "—"),
                       objecto,
                       liga_entidade(l["adjudicante_chave"],
                                     l["adj_nome"] or ""),
                       venceu,
                       html.escape(l["tipo_procedimento"] or ""),
                       euros(l["preco_contratual"])))
        if fim:
            cabecalhos = ("<th>Fim estimado</th><th>Objecto</th>"
                          "<th>Entidade</th><th>Quem tem o contrato</th>"
                          "<th>Celebrado</th><th class='p'>Preço</th>")
        else:
            # O fim estimado ao lado da celebracao: um contrato em curso
            # le-se pelo fim, nao so pelo principio. O travessao e "sem
            # prazo no dump", nao zero.
            cabecalhos = ("<th>Celebrado</th><th>Fim estimado</th>"
                          "<th>Objecto</th><th>Entidade</th>"
                          "<th>Quem ganhou</th><th>Procedimento</th>"
                          "<th class='p'>Preço</th>")
        tabela = ("<div class='cx tab-cx'><table class='tab-contratos'>"
                  "<thead><tr>%s</tr></thead><tbody>%s</tbody>"
                  "</table></div>" % (cabecalhos, "".join(corpo)))
    elif ha_pergunta:
        tabela = ("<div class='vazio'>%s "
                  "<a href='%s'>limpar</a></div>"
                  % ("Nada deste filtro termina nos próximos %d meses."
                     % meses if fim else
                     "Nada corresponde a este filtro.",
                     html.escape(modo_limpo, quote=True)))
    elif fim:
        tabela = ("<div class='vazio comecar'>"
                  "<b>De que mercado queres ver os fins de contrato?</b>"
                  "<span>Escolhe um CPV na árvore ou escreve uma entidade: "
                  "a lista mostra os contratos desse mercado que terminam "
                  "na janela, do mais próximo para o mais distante. Um "
                  "contrato a acabar volta muitas vezes a concurso &mdash; "
                  "quem o vê antes do anúncio prepara-se com tempo.</span>"
                  "</div>")
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

    # O modo dito por extenso no titulo da tabela, nao so no selector:
    # era a unica defesa contra o "ecra bifacetado" que o custo da
    # opcao A (6.1) previa.
    if fim:
        titulo_tabela = ("<div class='rot' style='margin:16px 0 10px'>"
                         "Contratos por <b>fim estimado</b> &mdash; o que "
                         "vai acabar até %s</div>" % data_pt(fim_janela))
    else:
        titulo_tabela = ("<div class='rot' style='margin:16px 0 10px'>"
                         "Contratos por <b>data de celebração</b> &mdash; "
                         "o que já se comprou</div>")

    if ha_pergunta:
        if fim:
            conta = ("Do fim mais próximo para o mais distante &middot; "
                     "%s contrato%s a terminar até %s"
                     % (mil_pt(correspondem),
                        "" if correspondem == 1 else "s",
                        data_pt(fim_janela)))
            if correspondem > len(linhas):
                conta += (" &middot; página %s de %s"
                          % (mil_pt(pagina), mil_pt(paginas)))
        else:
            conta = "Celebrados mais recentes primeiro &middot; "
            if correspondem > len(linhas):
                primeiro = (pagina - 1) * POR_PAGINA_LISTA + 1
                conta += ("%s&ndash;%s de %s &middot; página %s de %s"
                          % (mil_pt(primeiro),
                             mil_pt(primeiro + len(linhas) - 1),
                             mil_pt(correspondem), mil_pt(pagina),
                             mil_pt(paginas)))
            else:
                conta += "%s %s" % (mil_pt(correspondem),
                                    "contrato" if correspondem == 1
                                    else "contratos")
        # O somatorio e do filtro todo, nao da pagina: e o numero que diz
        # quanto vale este mercado, e por pagina nao queria dizer nada.
        conta += " &middot; <b>%s</b> no total" % euros(valor)
        # a ligacao diz quantas linhas e que saem: encostada ao "1-20"
        # exportava as dezenas de milhares sem avisar. Leva ver/meses,
        # por isso o CSV exporta o mesmo modo que a lista mostra.
        linha_conta = ("<div class='linha-conta'>" + conta +
                       "<a href='/contratos/csv?%s'>exportar as %s linhas "
                       "(CSV)</a></div>"
                       % (urlencode(args_da_lista(request.args)),
                          mil_pt(min(correspondem, TECTO_CSV))))
    else:
        linha_conta = ""

    fonte = ("<div class='nota' style='margin-top:14px'>O dump do IMPIC é "
             "semanal: os contratos das últimas semanas podem ainda não lá "
             "estar. Anos fechados não mudam &mdash; o botão só volta a "
             "trazer o ano corrente e o anterior. Para anos mais antigos, "
             "<code>python radar.py --contratos 2015-2019</code>.</div>")

    # O campo do CPV e escondido, por isso um filtro activo nao se via em
    # lado nenhum a nao ser no chip da arvore, fechada. A faixa diz o que
    # esta a filtrar e da onde carregar para o tirar. As ligacoes "tirar"
    # levam ver/meses atras (args_da_lista guarda-os): tirar um campo
    # nao pode trocar de modo.
    faixas = [faixa_cpv_activo(
        request.args,
        "/contratos?" + urlencode(args_da_lista(request.args, cpv="")))]
    # A chave da entidade e opaca na URL: diz-se de quem e, e da-se a
    # ficha ao lado.
    for campo, papel in (("entid", "adjudicadas por"),
                         ("vencid", "detidas por" if fim else "ganhas por")):
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
    # de/ate vindos de fora (um filtro guardado, uma ligacao antiga)
    # ficam de lado no modo fim -- e diz-se, nunca em silencio (P3).
    if fim and ((request.args.get("de") or "").strip()
                or (request.args.get("ate") or "").strip()):
        faixas.append("<div class='cpv-activo'>As datas de celebração do "
                      "filtro <b>não se aplicam</b> neste modo: o eixo do "
                      "tempo é a janela do fim estimado. Estão postas de "
                      "lado, não perdidas &mdash; voltam no modo por "
                      "celebração.</div>")
    faixa_cpv = "".join(faixas)

    # Pedidos so ao abrir, como a arvore: sao ~800 ms de consultas e a
    # tabela nao tem de esperar por eles. Sem filtro nem aparecem: sobre
    # o corpus inteiro demoravam muito e respondiam a pergunta nenhuma.
    # O pedido leva a query string inteira, ver/meses incluidos: os
    # graficos respondem ao mesmo conjunto que a tabela mostra.
    graficos = (
        "<details class='arvore graficos'><summary>"
        "<span class='arv-tit'>Ver em gráficos</span>"
        "<span class='arv-sub'>quem ganha, quem compra, como se compra, "
        "concentração, tamanho, evolução &mdash; deste filtro</span></summary>"
        "<div id='graf-corpo' class='graf-corpo'>a carregar…</div>"
        "</details>") if ha_pergunta else ""

    # A troca de modo e uma troca de vista, nao de pagina: leva o filtro
    # inteiro (P3). Vai no lugar das abas, como os estados da Triagem.
    para_celebracao = args_da_lista(request.args)
    para_celebracao.pop("ver", None)
    para_celebracao.pop("meses", None)
    para_fim = args_da_lista(request.args, ver="fim")
    abas = ("<div class='abas'>"
            "<a class='%s' href='/contratos%s'>Por celebração</a>"
            "<a class='%s' href='/contratos?%s'>Por fim estimado</a>"
            "</div>"
            % ("" if fim else "on",
               ("?" + urlencode(para_celebracao)) if para_celebracao else "",
               "on" if fim else "", urlencode(para_fim)))

    nota_estimativa = (
        "<div class='nota' style='margin:14px 0 4px'>O fim é <b>estimado</b>: "
        "data de celebração mais o prazo de execução declarado ao IMPIC. "
        "Prorrogações e cessações antecipadas não constam do dump &mdash; "
        "confirma antes de contar com a data.</div>") if fim else ""

    # 11.7-B: a porta directa para a ficha de uma entidade, por nome ou
    # NIF -- o sinal que a reabriu foi exactamente "abrir um contrato
    # qualquer so para chegar a ficha".
    procura_entidade = (
        "<form class='cx filtros' method='get' action='/entidade/procurar'>"
        "<label>Ficha de entidade</label>"
        "<input type='text' name='q' value='' "
        "placeholder='Nome ou NIF — abre a ficha directamente…'>"
        "<button type='submit'>Procurar</button></form>")

    conteudo = ("<div class='larg'>" + barra_corpus(anos) +
                procura_entidade +
                ("" if fim else faixa_de_avisos_de_datas(request.args)) +
                filtros +
                faixa_cpv + arvore_html(n_cpv, "contratos") +
                caixa_de_filtros(request.args, vista, "/contratos",
                                 extra="ver=fim&meses=%d" % meses
                                 if fim else "") +
                graficos + linha_conta +
                (titulo_tabela if ha_pergunta else "") +
                tabela +
                paginador(pagina, paginas, request.args, "/contratos") +
                nota_estimativa +
                (fonte if ha_pergunta else "") + "</div>")

    if fim:
        return envolver(
            "renovacoes", "Contratos celebrados",
            "Vistos pelo fim estimado &mdash; o que está a chegar ao fim "
            "no teu mercado deve voltar a concurso, e quem o vê antes do "
            "anúncio prepara-se com tempo.",
            conteudo, abas=abas,
            script=ARVORE_JS + GRAFICOS_JS + espera_corpus(),
            migalhas=migalhas_de("renovacoes"),
            titulo_aba="Renovações, Radar de Concursos")
    return envolver(
        "contratos", "Contratos celebrados",
        "O que já foi assinado &mdash; quem ganhou, por quanto, de quem. "
        "Não são oportunidades: servem para saber com quem se concorre.",
        conteudo, abas=abas,
        script=ARVORE_JS + GRAFICOS_JS + espera_corpus(),
        migalhas=migalhas_de("contratos"),
        titulo_aba="Contratos, Radar de Concursos")


# --------------------------------- modo "fim estimado" dos contratos
#
# As antigas Renovacoes, fundidas em /contratos por decisao 6.1-A
# (31/08/2026): contratos vistos pelo fim e nao pelo principio -- o que
# esta a acabar no meu mercado vai provavelmente voltar a concurso, e
# quem chega antes do anuncio chega a horas. E a pergunta que a Armilar
# vende como "Previsão de Contratos" e a SpotGov como "Pipeline Radar"
# -- ver CONCORRENTES.md e o B03 do BACKLOG.md.
#
# Deixou de ser pagina irma (~80% decalcada, "corrigido numa, vivo na
# outra") e passou a modo do MESMO ecra: ver=fim na query string, com o
# modo declarado por extenso no titulo da tabela. A rota /renovacoes
# fica a responder como redireccionamento, para nao partir filtros
# guardados nem ligacoes antigas (§9 linha 8 do ESQUELETO).
#
# O fim e ESTIMADO: celebracao + prazo de execucao do dump. As
# prorrogacoes e as cessacoes antecipadas nao constam do IMPIC, e a
# pagina di-lo em vez de fingir precisao.

# Janelas oferecidas, em meses. Whitelist: o valor entra numa expressao
# de data do SQL, e fora desta lista volta a omissao.
MESES_RENOVACOES = (3, 6, 12, 24)


def meses_pedidos(args):
    """A janela pedida, so se for uma das oferecidas; 6 por omissao."""
    try:
        m = int(args.get("meses", 6))
    except (TypeError, ValueError):
        return 6
    return m if m in MESES_RENOVACOES else 6


def modo_fim(args):
    """True quando os contratos estao no modo "ver por fim estimado"."""
    return (args.get("ver") or "").strip() == "fim"


def condicao_do_modo(args):
    """Fragmento SQL do modo ('' no modo celebracao). A janela vai por
    interpolacao mas SO depois da whitelist: meses_pedidos() devolve um
    dos MESES_RENOVACOES, nunca texto da URL."""
    if not modo_fim(args):
        return ""
    return (" AND c.fim_estimado >= date('now')"
            " AND c.fim_estimado <= date('now', '+%d months')"
            % meses_pedidos(args))


def filtros_dos_contratos(args):
    """(onde, valores) da lista de contratos, com o modo aplicado.

    E por aqui que a lista, o CSV e os graficos filtram -- os tres com
    a MESMA conta, senao o numero de um nao abria a lista do outro. No
    modo fim, `de`/`ate` NAO entram: o eixo do tempo e a janela do fim,
    e dois eixos em simultaneo confundiam (B03). A pagina desactiva os
    campos com explicacao em vez de os deixar cair em silencio.
    """
    if modo_fim(args) and ((args.get("de") or "").strip()
                           or (args.get("ate") or "").strip()):
        limpos = dict(args.to_dict() if hasattr(args, "to_dict") else args)
        limpos.pop("de", None)
        limpos.pop("ate", None)
        args = limpos
    onde, valores = condicoes_contratos(args)
    return onde + condicao_do_modo(args), valores


@app.route("/renovacoes")
def renovacoes():
    """A pagina fundiu-se nos contratos como modo "fim estimado"
    (decisao 6.1-A). A rota fica a responder como redireccionamento,
    com o filtro que trouxer: um filtro guardado ou uma ligacao antiga
    para /renovacoes continua a abrir a mesma lista."""
    novos = args_da_lista(request.args, ver="fim")
    return redirect("/contratos?" + urlencode(novos))


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


# Uma linha "Chave: valor" dentro de um bloco de perfil. O dois-pontos
# tem de vir depois de uma chave curta -- senao qualquer frase com dois
# pontos a meio virava uma linha de tabela.
RX_PAR_PERFIL = re.compile(r"^([^:]{2,40}):\s*(.*)$")
RX_ITEM_LISTA = re.compile(r"^\s*[-–•]\s+(.+)$")
RX_ITEM_NUM = re.compile(r"^\s*(\d{1,2})\.\s+(.+)$")


def desenha_valor(valor):
    """O valor de um campo do essencial, com a estrutura que ele tiver.

    Os campos lidos das pecas pelo modelo sao os mais compridos da ficha
    -- a "Equipa" deste anuncio do INFARMED sao 3 200 caracteres em 146
    linhas -- e sairem como um bloco corrido no mesmo corpo e peso do
    resto era o que fazia 80% do rolo da ficha ler-se ao mesmo nivel.
    Nada aqui muda o texto: mudam-lhe os degraus.

    Tres formas, todas reconhecidas pelo que o texto ja e:
    - blocos separados por linha em branco, com pares "Chave: valor"
      -> um cartao por bloco (os perfis da equipa);
    - linhas comecadas por travessao -> lista;
    - linhas "1. Nome" seguidas de detalhe -> lista numerada.
    O que nao tiver forma nenhuma sai como sempre saiu.
    """
    texto = (valor or "").strip()
    if not texto:
        return ""

    blocos = [b for b in re.split(r"\n\s*\n", texto) if b.strip()]
    if len(blocos) >= 2:
        cartoes, todos_com_pares = [], True
        for bloco in blocos:
            linhas = [l.strip() for l in bloco.split("\n") if l.strip()]
            pares = [RX_PAR_PERFIL.match(l) for l in linhas[1:]]
            if len(linhas) < 2 or not all(pares):
                todos_com_pares = False
                break
            cartoes.append(
                "<div class='perfil'><b>%s</b><dl>%s</dl></div>"
                % (html.escape(linhas[0]),
                   "".join("<dt>%s</dt><dd>%s</dd>"
                           % (html.escape(m.group(1)), html.escape(m.group(2)))
                           for m in pares)))
        if todos_com_pares and cartoes:
            return "<div class='perfis'>%s</div>" % "".join(cartoes)

    linhas = [l for l in texto.split("\n") if l.strip()]
    itens = [RX_ITEM_LISTA.match(l) for l in linhas]
    if len(linhas) >= 2 and all(itens):
        return ("<ul class='pontos'>%s</ul>"
                % "".join("<li>%s</li>" % html.escape(m.group(1))
                          for m in itens))

    # numerados: cada numero abre um item e o que vem a seguir, ate ao
    # numero seguinte, e o detalhe dele
    if len(linhas) >= 2 and RX_ITEM_NUM.match(linhas[0]):
        itens, actual = [], None
        for linha in linhas:
            m = RX_ITEM_NUM.match(linha)
            if m:
                actual = [m.group(2), []]
                itens.append(actual)
            elif actual is not None:
                actual[1].append(linha.strip())
            else:
                itens = []
                break
        if itens:
            return ("<ol class='numerados'>%s</ol>"
                    % "".join(
                        "<li><b>%s</b>%s</li>"
                        % (html.escape(nome),
                           ("<span>%s</span>" % html.escape(" ".join(det)))
                           if det else "")
                        for nome, det in itens))

    return html.escape(texto)


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
    #
    # Os subfactores sao de outro nivel e sairam para dentro de
    # parenteses. Antes ia tudo na mesma linha e com o mesmo peso visual:
    # "Preço 45% · Início 10% · Qualidade 45% · Plano de Trabalhos 70% ·
    # Memória Descritiva 30%" soma 200%, porque os dois ultimos sao
    # subfactores da Qualidade e nao criterios de topo. E o campo que
    # decide se vale a pena concorrer.
    fatores, nome, outro, em_sub = [], "", "", False

    def resolvido():
        return outro if (not nome or simplifica(nome) == "outros") and outro \
            else nome

    for chave, valor in pares:
        c = simplifica(chave).strip()
        if c == "fator":
            em_sub = False
            nome, outro = "", ""
        elif c == "subfatores":
            # "Subfatores: Sim" ou "Não" e a resposta do factor; a mesma
            # chave sozinha, sem valor, e o que abre a lista dos
            # subfactores do factor anterior.
            if not valor.strip():
                em_sub = True
            nome, outro = "", ""
        elif c == "nome":
            nome, outro = valor, ""
        elif c in ("outro nome", "outro fator"):
            outro = valor
        elif c == "ponderacao" and resolvido():
            # o DR escreve "70%; " nos subfactores
            texto = "%s %s" % (resolvido(), valor.strip().rstrip(";").strip())
            if em_sub and fatores:
                fatores[-1][1].append(texto)
            else:
                fatores.append([texto, []])
            nome, outro = "", ""

    if fatores:
        # ponto literal, nao a entidade: este valor passa por html.escape()
        # ao ser desenhado, e "&middot;" sairia escrito tal e qual
        return " · ".join(
            ("%s (%s)" % (texto, ", ".join(subs))) if subs else texto
            for texto, subs in fatores)
    return resolvido()                # monofator, ou multifator sem pesos


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

    def foi_lido(campo):
        """Se a leitura chegou a perguntar por este campo.

        "Lido e nao consta" e "ainda nao lido" sao respostas diferentes e
        a ficha diz qual e qual. Uma linha de analise gravada antes de o
        campo existir nao o leu -- dizer "foi lido e nao fixa" ai seria
        afirmar uma leitura que nao houve."""
        if not analise:
            return False
        try:
            return analise[campo] is not None
        except (KeyError, IndexError):
            return False

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
        "o Programa de Concurso não fixa nenhum"
        if foi_lido("preco_anormalmente_baixo") else FALTA_PC)

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
         # A mesma distincao do preco anormalmente baixo: depois da
         # leitura, "ainda nao foi lido" era mentira -- e mandava abrir
         # um documento que a ferramenta ja tinha visto nao dizer nada.
         ("localização do procedimento; o Caderno de Encargos foi lido e "
          "não fixa o regime presencial, remoto ou híbrido"
          if foi_lido("localizacao") else
          "localização do procedimento; o regime presencial, remoto ou "
          "híbrido consta do Caderno de Encargos e ainda não foi lido")),
        ("Data de esclarecimentos", esclarecimentos, esclarec_falta,
         esclarec_nota),
        ("Data de submissão da proposta", data_pt(a["prazo"], ""), "", ""),
        ("Objeto, âmbito e características", das_pecas("objecto"),
         "" if das_pecas("objecto") else
         ("o Caderno de Encargos foi lido e não o descreve"
          if foi_lido("objecto") else FALTA_CE), nota_pecas),
        ("Equipa", das_pecas("equipa"),
         "" if das_pecas("equipa") else
         ("o Caderno de Encargos foi lido e não fixa requisitos de equipa"
          if foi_lido("equipa") else FALTA_CE), nota_pecas),
        ("Documentos que constituem a proposta", das_pecas("documentos_proposta"),
         "" if das_pecas("documentos_proposta") else
         ("o Programa de Concurso foi lido e não os enumera"
          if foi_lido("documentos_proposta") else FALTA_PC), nota_pecas),
    ]


def data_hora_pt(texto, vazio="—"):
    """"2026-08-29 18:54" -> "29/08/2026 18:54".

    A regra da casa e ISO na base e DD/MM a vista, e valia em todo o lado
    menos em tres sitios: o historico da ficha, a barra do corpus e a
    "ultima" da barra lateral. O que nao parecer data passa como esta --
    ha marcas antigas com texto livre ("nunca")."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})[ T]?(.*)$", (texto or "").strip())
    if not m:
        return texto or vazio
    resto = (" " + m.group(4).strip()) if m.group(4).strip() else ""
    return "%s/%s/%s%s" % (m.group(3), m.group(2), m.group(1), resto)


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


def descontos_da_entidade(chave, cpv):
    """Os descontos por procedimento desta entidade neste CPV, para a
    linha da ficha do anuncio. A mesma agregacao (e as mesmas exclusoes)
    de descontos_por_procedimento()."""
    prefixos = [p for p in (prefixo_cpv(x) for x in (cpv or "").split(",")) if p]
    if not (chave and prefixos and ha_corpus()):
        return []
    onde = (" WHERE c.adjudicante_chave=? AND "
            "c.id IN (SELECT contrato_id FROM contrato_cpv WHERE %s)"
            % " OR ".join("cpv8 LIKE ?" for _ in prefixos))
    with liga_corpus() as c:
        return descontos_por_procedimento(
            c, onde, [chave] + [p + "%" for p in prefixos])


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


# As palavras que todos os titulos tem e nada distinguem: o vocabulario
# burocratico da contratacao e as preposicoes compridas. Ficam de fora
# dos termos com que se procuram homologos -- "aquisicao de servicos"
# apanhava o corpus inteiro da entidade.
_PALAVRAS_OCAS = frozenset((
    "aquisicao", "fornecimento", "prestacao", "servico", "servicos",
    "contratacao", "contrato", "concurso", "publico", "publica",
    "procedimento", "ajuste", "direto", "directo", "empreitada",
    "aluguer", "locacao", "celebracao", "acordo", "quadro",
    "obra", "obras", "parte", "fase", "zona",
    "para", "com", "sem", "por", "dos", "das", "aos", "nas", "nos",
    "pela", "pelo", "pelas", "pelos", "entre", "sobre", "ate",
    "anos", "ano", "meses", "lote", "lotes", "diversos", "varios",
    "varias", "diversas", "destinado", "destinada", "ambito", "necessidades",
))


def termos_do_titulo(titulo, maximo=6):
    """Os termos do titulo com que se procuram procedimentos homologos.

    Sem acentos e em minusculas (simplifica), como o objecto_norm do
    corpus -- e a regra da casa: procurar com a norma da coluna. So
    palavras com 4 ou mais letras, sem o vocabulario da contratacao e
    sem numeros soltos (anos, referencias), que nada distinguem.
    """
    termos = []
    for p in re.findall(r"[a-z0-9]{4,}", simplifica(titulo)):
        if p in _PALAVRAS_OCAS or p in termos or p.isdigit():
            continue
        termos.append(p)
        if len(termos) == maximo:
            break
    return termos


def homologos_do_anuncio(chave, titulo, ref="", limite=8):
    """Contratos da mesma entidade com objecto parecido com este anuncio.

    E a pergunta "quanto e que isto custou da ultima vez, e quem ganhou"
    -- a edicao anterior do mesmo concurso, quando existe. O historico
    por CPV (mercado()) responde ao segmento; isto responde ao concurso.

    Parecido = partilha termos do titulo (termos_do_titulo) no
    objecto_norm. Com dois ou mais termos exigem-se pelo menos dois em
    comum: um so ("manutencao") arrastava a manutencao toda da entidade.
    Ordena por termos em comum e depois por data. O proprio anuncio fica
    de fora pelo n_anuncio, que e o ref do radar.

    Devolve (linhas, termos usados) -- os termos mostram-se, para se
    saber porque e que cada contrato aparece.
    """
    termos = termos_do_titulo(titulo)
    if not (chave and termos and ha_corpus()):
        return [], termos
    minimo = 2 if len(termos) >= 2 else 1
    pontos = " + ".join(
        "(COALESCE(c.objecto_norm,'') LIKE ? ESCAPE '%s')" % ESCAPE_LIKE
        for _ in termos)
    valores = (["%" + para_like(t) + "%" for t in termos]
               + [chave, ref, minimo, limite])
    with liga_corpus() as c:
        linhas = c.execute(
            "WITH marcados AS (SELECT c.id, c.n_anuncio, c.data_celebracao,"
            " c.objecto, c.tipo_procedimento, c.preco_contratual,"
            " (" + pontos + ") pontos FROM contratos c"
            " WHERE c.adjudicante_chave=? AND COALESCE(c.n_anuncio,'') != ?),"
            " pag AS (SELECT * FROM marcados WHERE pontos >= ?"
            "  ORDER BY pontos DESC, data_celebracao DESC, id DESC LIMIT ?)"
            " SELECT p.*,"
            " (SELECT group_concat(COALESCE(g.nome, a.nome), '|')"
            "  FROM contrato_adjudicatario a"
            "  LEFT JOIN entidades g ON g.chave=a.chave"
            "  WHERE a.contrato_id=p.id) AS ganhou,"
            " (SELECT group_concat(a.chave, '|') FROM contrato_adjudicatario a"
            "  WHERE a.contrato_id=p.id) AS ganhou_ch"
            " FROM pag p"
            " ORDER BY p.pontos DESC, p.data_celebracao DESC, p.id DESC",
            valores).fetchall()
    return linhas, termos


def homologos_cx(a, chave):
    """A caixa dos procedimentos homologos na ficha do anuncio.

    So aparece quando ha o que mostrar: o estado do corpus e da entidade
    ja e dito pela caixa do historico logo abaixo, e uma segunda caixa a
    dizer "nada" era ruido."""
    if not (chave and ha_corpus()):
        return ""
    linhas, termos = homologos_do_anuncio(chave, a["titulo"] or "", a["ref"])
    if not linhas:
        return ""

    # Quando o contrato aponta para um anuncio que o radar tem, a ficha
    # dele fica a um clique -- e la que estao as pecas e a leitura.
    refs = [l["n_anuncio"] for l in linhas if l["n_anuncio"]]
    conhecidos = set()
    if refs:
        with liga() as c:
            conhecidos = {r["ref"] for r in c.execute(
                "SELECT ref FROM anuncios WHERE ref IN (%s)"
                % ",".join("?" * len(refs)), refs)}

    corpo = []
    for l in linhas:
        nomes = (l["ganhou"] or "").split("|")
        chaves = (l["ganhou_ch"] or "").split("|")
        venceu = " + ".join(liga_entidade(ch, n)
                            for n, ch in zip(nomes, chaves) if n) or "—"
        objecto = html.escape(corta(l["objecto"] or "", 140))
        if l["n_anuncio"] in conhecidos:
            objecto += (" <a href='/anuncio/%s'>anúncio</a>"
                        % quote(l["n_anuncio"], safe=""))
        corpo.append(
            "<tr><td class='d'>%s</td><td class='o'>%s</td><td>%s</td>"
            "<td class='g'>%s</td><td class='p'>%s</td></tr>"
            % (data_pt(l["data_celebracao"]), objecto,
               html.escape(l["tipo_procedimento"] or ""),
               venceu, euros(l["preco_contratual"])))

    return ("<div class='cx mercado'>"
            "<div class='rot'>Procedimentos homólogos</div>"
            "<div class='nota' style='margin:6px 0 12px'>"
            "Contratos desta entidade com objecto parecido com o deste "
            "anúncio &mdash; as edições anteriores, com quem ganhou e por "
            "quanto. Parecido = tem em comum %s: <b>%s</b>.</div>"
            "<div class='mercado-tab'><table class='tab-mercado'><thead><tr>"
            "<th>Celebrado</th><th>Objecto</th><th>Procedimento</th>"
            "<th>Quem ganhou</th><th class='p'>Preço</th></tr></thead>"
            "<tbody>%s</tbody></table></div></div>"
            % ("estes termos do título" if len(termos) > 1
               else "este termo do título",
               html.escape(", ".join(termos)), "".join(corpo)))


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
               html.escape(corta(l["objecto"] or "", 140)),
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
        # A regua de quartis so com contratos que cheguem: com 3, "mais
        # barato" e "25%" eram o mesmo contrato repetido. A comparacao
        # com a mediana e a tabela ficam -- e dizem sobre quantos e.
        escada = ""
        if r["quantos"] >= MINIMO_PARA_ESCADA:
            escada = (
                "<div class='escada'>"
                "<span>mais barato<b>%s</b></span>"
                "<span>25%%<b>%s</b></span>"
                "<span class='med'>mediana<b>%s</b></span>"
                "<span>75%%<b>%s</b></span>"
                "<span>mais caro<b>%s</b></span></div>"
                % (euros_curto(r["menor"]), euros_curto(r["p25"]),
                   euros_curto(r["mediana"]), euros_curto(r["p75"]),
                   euros_curto(r["maior"])))
        ref_preco = (
            "<div class='ref-preco'>%s%s"
            "<div class='nota'>Sobre os %s contratos mais recentes desta "
            "entidade neste CPV. O preço contratual é o de partida, não o "
            "valor final &mdash; adicionais não entram.</div></div>"
            % (comparacao, escada, mil_pt(r["quantos"])))

    # O desconto com que esta entidade tem fechado neste CPV -- por
    # procedimento e nao por linha (B04). Diz por quanto abaixo do preco
    # base os vencedores tem levado, que e o que se quer saber antes de
    # pensar o preco da proposta.
    descs = descontos_da_entidade(chave, a["cpv"])
    if len(descs) >= MINIMO_PARA_DESCONTO:
        _, med = escaloes_de_desconto(descs)
        ref_preco += (
            "<div class='nota' style='margin-top:8px'>Desconto mediano "
            "face ao preço base, nesta entidade e CPV: <b>%s</b> &mdash; "
            "sobre %s procedimentos com anúncio e preço base no corpus."
            "</div>" % (pct_pt(med), mil_pt(len(descs))))

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


def volta_a_lista():
    """A lista de onde se veio, com o filtro e a pagina que tinha.

    So aceita caminhos desta aplicacao que sejam mesmo listas: um
    `referrer` de outro sitio, ou de uma ficha, nao serve de volta.
    """
    vindo = urlparse(request.referrer or "")
    if vindo.netloc and vindo.netloc != urlparse(request.host_url).netloc:
        return "/"
    if vindo.path in ("/", "/anuncios", "/quadro", "/calendario",
                      "/alertas"):
        return vindo.path + (("?" + vindo.query) if vindo.query else "")
    return "/"


@app.route("/anuncio/<path:ref>")
def ficha(ref):
    with liga() as c:
        a = c.execute("SELECT * FROM anuncios WHERE ref=?", (ref,)).fetchone()
    if not a:
        # Com a pagina toda, e nao uma linha de texto solta: era o unico
        # ecra da aplicacao que nao parecia a aplicacao -- sem barra
        # lateral, sem navegacao e sem forma de continuar a trabalhar.
        return envolver(
            "anuncios", "Esse anúncio não existe",
            "Não há nenhum anúncio com a referência "
            "<b>%s</b> nesta base." % html.escape(ref),
            "<div class='vazio'>Pode ter sido apagado numa limpeza do "
            "histórico, ou a referência estar mal escrita. "
            "<a href='/'>Voltar à lista</a> ou "
            "<a href='/?estado='>procurar em todos</a>.</div>",
            migalhas=migalhas_de("anuncios", ref)), 404

    # Se este anuncio ainda nao foi lido, le-se agora: um pedido, ~1 seg.
    # E o mesmo principio dos documentos -- so se vai buscar o que se
    # abre. So a fonte do DR: uma consulta preliminar da Vortal (B14)
    # nao tem pagina de detalhe no DR para ler.
    aviso_leitura = ""
    e_do_dr = (a["fonte"] or "dr") == "dr"
    if not (a["texto"] or "") and e_do_dr:
        ok, aviso_leitura = ler_detalhe_de(ref)
        if ok:
            with liga() as c:
                a = c.execute("SELECT * FROM anuncios WHERE ref=?", (ref,)).fetchone()

    with liga() as c:
        docs = c.execute("SELECT * FROM documentos WHERE ref=? ORDER BY nome",
                         (ref,)).fetchall()
        passos = c.execute("SELECT * FROM historico WHERE ref=? "
                           "ORDER BY id DESC LIMIT 12", (ref,)).fetchall()
        # A republicacao. Numa alteracao, a ficha aponta para o original,
        # onde a triagem se faz; num original ja alterado, o texto que
        # se mostra e o da alteracao mais recente -- e o que esta em
        # vigor, e os factos do cabecalho ja sao os dela.
        raiz_ref = (raiz_da_alteracao(c, ref, _valor(a, "altera") or "")
                    if a["estado"] == "alteracao" else "")
        vigor = (c.execute("SELECT ref, data_pub, texto FROM anuncios WHERE ref=?",
                           (a["alterado_por"],)).fetchone()
                 if _valor(a, "alterado_por") else None)
    texto_vigente = (vigor["texto"] if vigor and vigor["texto"] else a["texto"])
    faixa_alteracao = ""
    if a["estado"] == "alteracao":
        faixa_alteracao = (
            "<div class='flash'>Este anúncio é uma <b>alteração</b> do anúncio "
            "<a href='/anuncio/%s'>%s</a>%s. O prazo e o preço daqui já estão "
            "na ficha dele, e é lá que se decide.</div>"
            % (html.escape(raiz_ref, quote=True), html.escape(raiz_ref),
               "" if raiz_ref else " original, que não está nesta base")
            if raiz_ref else
            "<div class='flash'>Este anúncio altera o anúncio <b>%s</b>, que "
            "não está nesta base; fica a representar o procedimento.</div>"
            % html.escape(_valor(a, "altera") or ""))
    elif vigor:
        faixa_alteracao = (
            "<div class='flash'>Alterado pelo anúncio <a href='/anuncio/%s'>%s"
            "</a>, publicado a %s: os factos acima e o texto abaixo são os da "
            "versão em vigor. O histórico diz o que mudou.</div>"
            % (html.escape(vigor["ref"], quote=True), html.escape(vigor["ref"]),
               data_pt(vigor["data_pub"], "")))

    completo = request.args.get("modo") == "completo"
    # Qual das pecas esta aberta no leitor, por baixo da lista delas.
    # Viaja na query string e nao em estado nenhum: a ficha com uma peca
    # aberta e uma ligacao que se guarda e se manda a alguem.
    peca_aberta = (request.args.get("peca") or "").strip()
    dias, passou = dias_restantes(a["prazo"])

    # --- cabecalho
    rotulo_estado = _NOMES_ESTADO.get(a["estado"], a["estado"])
    classe_estado = {"interessa": "ok", "descartado": "",
                     "alteracao": ""}.get(a["estado"], "info")
    chips = ["<span class='ref'>%s %s</span>"
             % ("Anúncio" if e_do_dr else "Consulta", html.escape(ref))]
    if a["tipo"]:
        chips.append("<span class='tag'>%s</span>" % html.escape(a["tipo"]))
    chips.append("<span class='tag %s'>%s</span>" % (classe_estado, rotulo_estado))
    if a["estado"] == "descartado" and _valor(a, "motivo"):
        chips.append("<span class='tag'>%s</span>" % html.escape(a["motivo"]))

    # O "Propostas até" voltou aos factos. Tinha saido daqui porque
    # aparecia duas vezes no mesmo ecra -- aqui e na caixa preta da
    # coluna da direita; com a composicao em dossier (escolha do Afonso
    # a 31/08/2026) essa coluna deixou de existir, e o prazo passou a
    # estar em dois sitios com papeis diferentes: aqui e o dado da
    # tabela, la em cima e a referencia que acompanha o rolar.
    # "Estado" continua de fora: esse repetia-se mesmo, com o chip.
    if dias is None:
        facto_prazo = ""
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
        _, classe_prazo = etiqueta_prazo(a["prazo"])
        facto_prazo = _facto(
            "Propostas até",
            "%s <span class='conta %s'>%s</span>"
            "<span class='barra-prazo'><i style='width:%d%%'></i></span>"
            % (data_pt(a["prazo"]), classe_prazo,
               "prazo expirado" if passou else conta_dias(dias),
               100 if passou else pct))

    cpv_facto = "<br>".join(descricoes_cpv(a["cpv"]))
    if cpv_facto:
        # "Que mais ha disto?" — a Pesquisa com o(s) CPV do anuncio e
        # todos os estados fecha o ciclo ficha -> acervo (atalho da §5
        # do ESQUELETO). O campo cpv aceita varios codigos por |.
        codigos = "|".join(p.strip() for p in (a["cpv"] or "").split(",")
                           if p.strip())
        cpv_facto += ("<br><a href='/anuncios?%s'>ver anúncios deste CPV "
                      "na Pesquisa</a>"
                      % html.escape(urlencode({"cpv": codigos, "estado": ""}),
                                    quote=True))
    factos = "".join((
        _facto("Publicado", data_pt(a["data_pub"], "")),
        facto_prazo,
        _facto("Preço base", html.escape(a["preco_base"] or "")),
        _facto("Plataforma", html.escape(a["plataforma"] or "")),
        _facto("CPV", cpv_facto, largo=True),
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
    # As duas de triagem ficam no cabecalho fino, que acompanha o rolar:
    # sao as unicas que se querem ao alcance em qualquer ponto da ficha.
    # As outras (as que abrem coisas fora daqui, e o repor) vao para a
    # direita do indice, onde nao disputam o olho com o titulo.
    decidir, sair = [], []
    e_alteracao = a["estado"] == "alteracao"
    if a["estado"] != "interessa" and not e_alteracao:
        decidir.append(accao("/estado/%s/interessa" % ref, "Interessa", "bt verde"))
    if a["estado"] != "descartado" and not e_alteracao:
        decidir.append(forma_abandonar(ref, "bt", "Abandonar",
                                       a["titulo"] or ref))
    if a["estado"] != "novo" and not e_alteracao:
        sair.append(accao("/estado/%s/novo" % ref, "Pôr por ver", "bt-leve"))
    if a["pdf_url"]:
        sair.append("<a class='bt-leve' href='%s' target='_blank'>PDF oficial</a>"
                    % html.escape(a["pdf_url"], quote=True))
    sair.append("<a class='bt-leve' href='%s' target='_blank'>%s</a>"
                % (html.escape(a["url"], quote=True),
                   "Ver no DR" if e_do_dr else "Ver na Vortal"))
    # Duas coisas diferentes, dois botoes: o procedimento na plataforma
    # e as pecas. Estavam no mesmo -- "Abrir plataforma" abria o link
    # das pecas, que na acingov descarrega um ZIP e na Vortal da na
    # lista dos ficheiros; nenhum dos dois e o procedimento.
    destino, rotulo, dica = link_do_procedimento(a)
    if destino:
        sair.append("<a class='bt-leve' href='%s' target='_blank' "
                    "title='%s'>%s</a>"
                    % (html.escape(destino, quote=True),
                       html.escape(dica, quote=True), html.escape(rotulo)))
    if a["link_pecas"] and a["link_pecas"] != destino:
        sair.append("<a class='bt-leve' href='%s' target='_blank' "
                    "title='o endereço das peças que o anúncio indica'>"
                    "Peças na plataforma</a>"
                    % html.escape(a["link_pecas"], quote=True))

    # Voltar para a lista **de onde se veio**, com o filtro e a pagina.
    # Estava preso a "/": filtrar por CPV, ir a pagina 7, abrir um anuncio
    # e carregar aqui devolvia "Por ver, pagina 1, sem filtro" -- o botao
    # estava no sitio onde se espera o caminho certo e era o errado, e ao
    # fim de duas vezes deixava de se usar.
    chip_prazo = ("<span class='chip-prazo %s'>%s &middot; %s</span>"
                  % (etiqueta_prazo(a["prazo"])[1], data_pt(a["prazo"]),
                     "expirado" if passou else conta_dias(dias))) \
        if dias is not None else ""
    ficha_cab = ("<div class='ficha-cab'>"
                 "<a class='volta' href='%s'>&larr;</a>"
                 "<span class='t'>%s</span>%s%s</div>"
                 % (html.escape(volta_a_lista(), quote=True),
                    html.escape(a["titulo"] or ref), chip_prazo,
                    "".join(decidir)))

    # --- seccoes do anuncio (as da versao em vigor, quando foi alterado)
    seccoes = seccoes_do_texto(texto_vigente)

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
                celula = desenha_valor(valor)
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
    elif not e_do_dr:
        # B14: uma consulta preliminar nao tem anuncio no DR -- o que se
        # sabe dela e o que a listagem publica da Vortal deu (os factos
        # do cabecalho) e o resto esta na plataforma.
        seccoes_html = (
            "<div class='vazio'>Isto é uma <b>consulta preliminar</b>, "
            "trazida da pesquisa pública da Vortal &mdash; a parte L do "
            "DR não a publica, por isso não há anúncio para mostrar. O "
            "que se sabe está nos factos acima; o resto está na "
            "<a href='%s' target='_blank'>página da consulta na Vortal"
            "</a>.</div>" % html.escape(a["url"] or "", quote=True))
        nota_modo = ""
    else:
        seccoes_html = ("<div class='vazio'>Não foi possível ler o texto deste "
                        "anúncio: %s</div>"
                        % (html.escape(aviso_leitura) if aviso_leitura else
                           "o DR não devolveu conteúdo."))
        nota_modo = ""

    # O indice: as duas primeiras entradas trocam mesmo de vista (sao as
    # que a barra "Texto do anúncio" era), as outras sao ancoras para os
    # blocos que ficam todos abertos por baixo. Fica preso ao rolar, que
    # e o que paga a composicao em dossier: numa ficha de oito mil
    # pixeis, saber onde se esta e poder saltar vale a coluna que se
    # perdeu.
    args_ess = dict(request.args.to_dict()); args_ess.pop("modo", None)
    args_com = dict(request.args.to_dict(), modo="completo")
    indice = ("<div class='ficha-indice'>"
              "<a class='%s' href='/anuncio/%s?%s'>Essencial</a>"
              "<a class='%s' href='/anuncio/%s?%s'>Anúncio completo</a>"
              "<a href='#pecas'>Peças</a>"
              "<a href='#mercado'>Mercado</a>"
              "<a href='#historico'>Histórico</a>"
              "<span class='dir'>%s%s</span></div>"
              % ("on" if not completo else "", ref, urlencode(args_ess),
                 "on" if completo else "", ref, urlencode(args_com),
                 ("<span class='nota-modo'>%s</span>" % nota_modo)
                 if nota_modo else "", "".join(sair)))

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
        # Um PDF abre AQUI, por baixo desta lista (pedido do Afonso na
        # fase de desenho, 31/08/2026): ler a peca deixou de ser sair da
        # ficha. A rota propria /peca/<ref>/<nome> continua a responder,
        # que e o que segura as ligacoes antigas; o que muda e para onde
        # a lista aponta. O resto (ZIPs, etc.) descarrega-se como antes.
        args_peca = dict(request.args.to_dict())
        args_peca.pop("procurar", None)   # procura nova para cada peca
        linhas_doc = []
        for d in docs:
            e_pdf = d["nome"].lower().endswith(".pdf")
            if e_pdf:
                destino = "/anuncio/%s?%s#pecas" % (
                    ref, urlencode(dict(args_peca, peca=d["nome"])))
            else:
                destino = "/documento/%s/%s" % (
                    ref, quote(d["nome"], safe=""))
            linhas_doc.append(
                "<div class='doc%s'><a href='%s'>%s</a>"
                "<span class='t'>%s</span></div>"
                % (" aberta" if e_pdf and d["nome"] == peca_aberta else "",
                   html.escape(destino, quote=True),
                   html.escape(d["nome"]), tamanho_legivel(d["tamanho"])))
        linhas_doc = "".join(linhas_doc)
        # Sucesso parcial tem de se ver: o PDF do anuncio vem sempre, e
        # sozinho parecia que estava tudo trazido.
        if a["docs_estado"] == "parcial":
            cabeca_docs = ("<div class='nota' style='color:var(--laranja)'>Só veio o "
                           "PDF do anúncio &mdash; as peças do procedimento "
                           "não foi possível trazer da plataforma.</div>")
        elif a["docs_estado"] == "falhou":
            # Falhar a actualizacao com peças antigas em disco nao se via
            # em lado nenhum: a lista continuava ali e parecia recente.
            cabeca_docs = ("<div class='nota' style='color:var(--laranja)'>Não foi "
                           "possível actualizar as peças na plataforma &mdash; "
                           "as que estão em baixo são as de antes.</div>")
        else:
            cabeca_docs = ("<div class='nota'>Guardadas em documentos/%s.</div>"
                           % html.escape(re.sub(r"[^0-9A-Za-z._-]", "-", ref)))
        analise = analise_de(ref)
        if analise_a_correr(ref):
            # A leitura corre em fila, como a descarga: o que se mostra e
            # o sinal de vida, e nao um botao que ja nao faz nada.
            accoes_docs = ("<div class='nota a-trazer'>A ler as peças pelo "
                           "modelo… a página actualiza-se sozinha.</div>")
        else:
            accoes_docs = (
                "<div class='accoes' style='margin-top:14px'>%s%s</div>"
                % (accao("/analisar/%s" % ref,
                         "Reler pelo modelo" if analise else "Ler as peças",
                         "bt" if analise else "bt forte"),
                   accao("/documentos/%s" % ref, "Actualizar peças")))
        corpo_docs = (cabeca_docs + "<div class='docs'>%s</div>%s"
                      % (linhas_doc, accoes_docs))
    else:
        if a["docs_estado"] == "falhou":
            nota = ("Não foi possível trazer as peças automaticamente. A "
                    "plataforma indicada pode exigir sessão iniciada.")
        else:
            nota = ("Ainda não foram trazidas. Vêm sozinhas ao marcar "
                    "&ldquo;interessa&rdquo;.")
        corpo_docs = ("<div class='nota'>%s</div><div style='margin-top:14px'>%s</div>"
                      % (nota, accao("/documentos/%s" % ref, "Trazer peças", "bt forte")))

    # O leitor da peca escolhida, por baixo da lista e dentro da mesma
    # caixa. Se o nome nao corresponder a nenhum ficheiro em disco (uma
    # ligacao velha, uma peca que a actualizacao apagou), nao se abre
    # nada e a lista fica como estava -- nunca uma moldura vazia.
    leitor = ""
    if peca_aberta:
        pasta = os.path.abspath(pasta_do_anuncio(ref))
        caminho = os.path.abspath(os.path.join(pasta, nome_seguro(peca_aberta)))
        if caminho.startswith(pasta + os.sep) and os.path.exists(caminho):
            args_fechar = dict(request.args.to_dict())
            args_fechar.pop("peca", None); args_fechar.pop("procurar", None)
            # O `action` vai sem query string de proposito: um GET
            # substitui-a inteira pelos campos do formulario, e o que
            # tem de sobreviver a procura viaja nos escondidos.
            aviso_leitor, visual = visualizador_de_peca(
                ref, peca_aberta, caminho,
                "/documento/%s/%s" % (ref, quote(peca_aberta, safe="")),
                (request.args.get("procurar") or "").strip(),
                "/anuncio/%s#pecas" % ref,
                ocultos=dict(args_fechar, peca=peca_aberta),
                limpar="/anuncio/%s?%s#pecas"
                       % (ref, urlencode(dict(args_fechar, peca=peca_aberta))))
            leitor = (
                "<div class='leitor'>"
                "<div class='leitor-cab'><span class='n'>%s</span>"
                "<a class='bt-leve' href='/documento/%s/%s' download>"
                "Descarregar</a>"
                "<a class='bt-leve' href='/anuncio/%s?%s#pecas'>Fechar</a>"
                "</div><div class='nota'>%s</div>%s%s</div>"
                % (html.escape(peca_aberta), ref,
                   quote(peca_aberta, safe=""), ref,
                   html.escape(urlencode(args_fechar), quote=True),
                   aviso_leitor, visual, texto_da_peca(ref, peca_aberta)))

    chip_plat = ("<span class='tag ok' style='margin-left:auto'>%s</span>"
                 % html.escape(a["plataforma"])) if a["plataforma"] else ""
    docs_cx = ("<div class='cx lado-cx' id='pecas'><div class='cab'>"
               "<span class='rot'>Peças do procedimento</span>%s</div>%s%s</div>"
               % (chip_plat, corpo_docs, leitor))

    resp = a["responsavel"] or ""
    resp_cx = ("<div class='cx lado-cx meia'><div class='rot' style='margin-bottom:12px'>"
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
            % (html.escape(p["quem"]),
               html.escape(_NOMES_ACCAO.get(p["accao"], p["accao"])),
               html.escape(p["detalhe"] or ""),
               html.escape(data_hora_pt(p["quando"])))
            for p in passos)
    else:
        linhas_hist = "<div class='nota'>Ainda não há registo de alterações.</div>"
    hist_cx = ("<div class='cx lado-cx meia' id='historico'>"
               "<div class='rot' style='margin-bottom:6px'>"
               "Histórico</div>%s</div>" % linhas_hist)

    # Composicao em dossier (escolha do Afonso, 31/08/2026): uma coluna
    # so, por ordem de leitura, com o cabecalho e o indice presos ao
    # rolar. Nenhum bloco entrou nem saiu -- os quatro que viviam na
    # coluna da direita passaram a estar nesta, e o prazo, que era a
    # caixa preta, e agora um facto do cabecalho mais o chip do indice.
    conteudo = ("<div class='larg ficha-dossier'>" + cabeca + faixa_alteracao +
                seccoes_html +
                docs_cx +
                "<div id='mercado'>" + homologos_cx(a, ch_ent) +
                mercado(a) + "</div>"
                "<div class='ficha-pe'>" + hist_cx + resp_cx + "</div></div>")

    # A ficha pendura-se na Pesquisa: e o acervo completo que a contem
    # sempre, venha-se da Triagem, do quadro ou de um homologo. A volta
    # com contexto continua a ser a do referrer (volta_a_lista).
    migalhas = migalhas_de("anuncios", ref)
    # Enquanto as peças não chegam, a página volta a pedir-se sozinha. O
    # trabalhador põe sempre um estado terminal (ok/parcial/falhou), por
    # isso isto pára -- não fica em ciclo.
    espera = ("<script>setTimeout(function(){location.reload()},3000)</script>"
              if (a["docs_estado"] == "pendente" or analise_a_correr(ref))
              else "")

    # O titulo e a entidade nao vao para o cabecalho grande da pagina:
    # nesta composicao quem manda no topo e o cabecalho fino, que fica
    # preso ao rolar e tem de caber numa linha. Os dois continuam a
    # ler-se no cartao de identidade, logo por baixo -- e o titulo
    # inteiro esta la, sem corte.
    return envolver("anuncios", "", "",
                    conteudo, migalhas=migalhas,
                    script=espera + caixa_de_abandono(),
                    abas=ficha_cab + indice,
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
    """Poe na fila, como o "Trazer peças" ao lado.

    Sem aviso na ligacao de proposito, pela mesma razao que as pecas: o
    recarregar leva a query string atras e um aviso posto aqui ficava
    colado a pagina depois de a leitura ter acabado. Quem diz em que pe
    isto vai e a caixa das pecas.
    """
    pedir_analise(ref, quem_sou())
    return redirect("/anuncio/" + ref)


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


@app.route("/peca-pagina/<path:ref>/<nome>/<int:n>.png")
def peca_pagina(ref, nome, n):
    """Uma pagina da peca desenhada pelo servidor (PNG). E o que faz o
    visualizador proprio funcionar em qualquer browser."""
    pasta = os.path.abspath(pasta_do_anuncio(ref))
    caminho = os.path.abspath(os.path.join(pasta, nome_seguro(nome)))
    if not caminho.startswith(pasta + os.sep) or not os.path.exists(caminho):
        return "", 404
    png = imagem_da_pagina(caminho, n,
                           procurar=(request.args.get("procurar")
                                     or "").strip())
    if png is None:
        return "", 404
    # as pecas nao mudam depois de trazidas: o browser pode guardar as
    # paginas um dia e poupar o desenho na visita seguinte (o termo
    # procurado faz parte do URL, por isso cada pesquisa tem a sua)
    return Response(png, mimetype="image/png",
                    headers={"Cache-Control": "max-age=86400"})


def texto_da_peca(ref, nome):
    """O texto extraido da peca, por paginas, dentro de um <details>.

    E o mesmo texto que alimenta a leitura pelo modelo (com as marcas de
    pagina). Fica na pagina porque o Ctrl+F do browser pesquisa nele
    mesmo quando o visualizador do PDF nao abre."""
    with liga() as c:
        d = c.execute("SELECT texto, texto_estado FROM documentos "
                      "WHERE ref=? AND nome=?", (ref, nome)).fetchone()
    if d and (d["texto"] or "").strip():
        paginas_html = []
        for i, pagina in enumerate((d["texto"] or "").split("\f"), 1):
            if not pagina.strip():
                continue
            paginas_html.append(
                "<div class='nota' style='margin:14px 0 4px'>&mdash; "
                "pág. %d &mdash;</div>"
                "<div style='white-space:pre-wrap;"
                "font:400 12px/1.6 var(--mono)'>%s</div>"
                % (i, html.escape(pagina.strip())))
        por_ocr = d["texto_estado"] == "ocr"
        return ("<details class='sec' style='margin-top:14px'><summary>"
                "<span class='st'>Texto extraído da peça%s</span>"
                "<span class='sh'>pesquisável com o Ctrl+F da página, mesmo "
                "quando o visualizador não abre%s</span></summary>%s</details>"
                % (" (por OCR)" if por_ocr else "",
                   "; lido por OCR de uma digitalização, pode ter erros"
                   if por_ocr else "",
                   "".join(paginas_html)))
    if d and d["texto_estado"] == "scan":
        return ("<div class='nota' style='margin-top:14px'>Este PDF é "
                "uma digitalização: não tem texto extraível. %s</div>"
                % ("O OCR lê-o na próxima leitura das peças."
                   if ocr_instalado() else
                   "Com o OCR instalado (pip install rapidocr onnxruntime) "
                   "o radar lê-o."))
    if d and d["texto_estado"] == "imagem":
        return ("<div class='nota' style='margin-top:14px'>Este PDF é "
                "uma digitalização e o OCR não encontrou texto nela.</div>")
    return ""


def visualizador_de_peca(ref, nome, caminho, origem, procurar, rota,
                         ocultos=None, limpar=None):
    """(aviso, html) do documento desenhado pagina a pagina.

    O mesmo codigo serve dois sitios: a pagina propria da peca
    (/peca/<ref>/<nome>, que as ligacoes antigas continuam a abrir) e o
    bloco que abre DENTRO da ficha, por baixo das pecas -- foi ai que o
    Afonso o quis, na fase de desenho de 31/08/2026. O que muda entre os
    dois e o `rota`, para onde a caixa de procura submete, e os
    `ocultos`: um GET substitui a query string inteira pelos campos do
    formulario, e sem eles procurar dentro da ficha perdia o `peca=` --
    a pagina voltava com a procura feita e o leitor fechado."""
    n_paginas = paginas_do_pdf_imagem(caminho)
    if not n_paginas:
        # Sem PyMuPDF (ou com um ficheiro que ele nao abra) cai-se para o
        # <embed>, que fica a merce da definicao "transferir PDFs em vez
        # de abrir" do browser -- por isso o aviso di-lo.
        return (
            "Pesquisa dentro do documento com o Ctrl+F do visualizador. "
            "Se em vez do documento vires um cartão &ldquo;Abrir&rdquo;, "
            "o teu browser está configurado para <b>transferir PDFs em "
            "vez de os abrir</b> &mdash; o texto extraído fica aqui em "
            "baixo. ",
            "<embed src='%s' type='application/pdf' "
            "style='width:100%%;height:82vh;border:1px solid var(--linha);"
            "border-radius:8px;background:#fff'>"
            % html.escape(origem, quote=True))

    base_img = "/peca-pagina/%s/%s" % (ref, quote(nome, safe=""))
    sufixo = ("?" + urlencode({"procurar": procurar})) if procurar else ""
    # cada pagina tem ancora propria: e para ela que as ligacoes da
    # pesquisa saltam
    paginas_img = "".join(
        "<img id='pag-%d' src='%s/%d.png%s' loading='lazy' "
        "alt='página %d' class='peca-pag'>"
        % (i, html.escape(base_img, quote=True), i,
           html.escape(sufixo, quote=True), i)
        for i in range(1, n_paginas + 1))

    # A pesquisa DENTRO do documento (pedida pelo Afonso a 31/08/2026: o
    # Ctrl+F levava-o ao texto extraido, e ele queria o resultado no
    # PDF). O termo marca-se a amarelo nas paginas desenhadas e a faixa
    # lista onde ele esta, com salto directo.
    escondidos = "".join(
        "<input type='hidden' name='%s' value='%s'>"
        % (html.escape(k, quote=True), html.escape(v, quote=True))
        for k, v in sorted((ocultos or {}).items()) if v)
    caixa = (
        "<form class='cx filtros peca-procura' method='get' action='%s'>%s"
        "<input type='text' name='procurar' value='%s' "
        "placeholder='Procurar no documento…'>"
        "<button type='submit'>Procurar</button>%s</form>"
        % (html.escape(rota, quote=True), escondidos,
           html.escape(procurar, quote=True),
           ("<a class='limpar' href='%s'>limpar</a>"
            % html.escape(limpar or rota, quote=True)) if procurar else ""))
    if procurar:
        achadas = paginas_com_termo(caminho, procurar)
        if achadas:
            saltos = " ".join(
                "<a href='#pag-%d'>pág. %d%s</a>"
                % (p, p, " (%d×)" % vezes if vezes > 1 else "")
                for p, vezes in achadas)
            resultados = (
                "<div class='achados'>&ldquo;%s&rdquo; aparece em "
                "<b>%d página%s</b> (%d vez%s), marcado a amarelo: %s</div>"
                % (html.escape(procurar), len(achadas),
                   "" if len(achadas) == 1 else "s",
                   sum(v for _, v in achadas),
                   "" if sum(v for _, v in achadas) == 1 else "es", saltos))
        else:
            resultados = (
                "<div class='achados'>&ldquo;%s&rdquo; não aparece "
                "no documento &mdash; a procura é tal e qual está "
                "escrito (acentos contam).</div>" % html.escape(procurar))
    else:
        resultados = ""
    return (
        "Documento desenhado pelo radar, página a página (%d). "
        "Procura com a caixa aqui em baixo: as ocorrências ficam "
        "marcadas a amarelo nas páginas, com salto directo. " % n_paginas,
        caixa + resultados + "<div class='peca-folhas'>%s</div>" % paginas_img)


@app.route("/peca/<path:ref>/<nome>")
def ver_peca(ref, nome):
    """A peca aberta dentro da aplicacao, com pesquisa la dentro.

    Estava em "Não fazer" desde a retirada do B09; o Afonso pediu-a a
    31/08/2026. E a versao que ele queria da pesquisa nas pecas: em vez
    de uma caixa solta (que chegava sempre tarde -- as pecas so existem
    depois do "interessa"), o proprio PDF no visualizador do browser,
    que ja pesquisa com Ctrl+F. O caminho barato do BACKLOG: um <embed>
    do ficheiro que ja esta em documentos/."""
    pasta = os.path.abspath(pasta_do_anuncio(ref))
    caminho = os.path.abspath(os.path.join(pasta, nome_seguro(nome)))
    if not caminho.startswith(pasta + os.sep) or not os.path.exists(caminho):
        return envolver(
            "anuncios", "Peça não encontrada",
            "O ficheiro já não está na pasta dos documentos.",
            "<div class='vazio'>Volta à <a href='/anuncio/%s'>ficha do "
            "anúncio</a> e carrega em &ldquo;Actualizar peças&rdquo;."
            "</div>" % ref,
            migalhas=migalhas_de("anuncios", ref)), 404
    origem = "/documento/%s/%s" % (ref, quote(nome, safe=""))
    texto_cx = texto_da_peca(ref, nome)
    aviso_topo, visual = visualizador_de_peca(
        ref, nome, caminho, origem,
        (request.args.get("procurar") or "").strip(),
        "/peca/%s/%s" % (ref, quote(nome, safe="")))

    corpo = (
        "<div class='larg'>"
        "<div class='nota' style='margin-bottom:10px'>%s"
        "<a href='%s' download>Descarregar</a> &middot; "
        "<a href='/anuncio/%s'>voltar à ficha</a></div>"
        "%s"
        "%s"
        "</div>" % (aviso_topo, html.escape(origem, quote=True), ref,
                    visual, texto_cx))
    return envolver(
        "anuncios", nome, "Peça do anúncio %s." % html.escape(ref),
        corpo, migalhas=migalhas_de("anuncios", ref),
        titulo_aba="%s, Radar de Concursos" % nome)


# --------------------------------------------------------------- quadro

QUADRO_JS = """<script>
function contarColunas() {
  // As contagens do cabecalho sao desenhadas no servidor e ficavam como
  // estavam depois de arrastar: duas colunas passavam a dizer o
  // contrario do que se via dentro delas, ate alguem recarregar a mao.
  document.querySelectorAll('.coluna').forEach(function(col) {
    var conta = col.querySelector('.coluna-conta');
    var corpo = col.querySelector('.coluna-corpo');
    if (conta && corpo) {
      conta.textContent = corpo.querySelectorAll('.carta').length;
    }
  });
}

function renomearFase(campo) {
  // Submeter no onblur, sempre, recarregava a pagina inteira so por se
  // ter clicado no campo e clicado fora. E o nome vazio era ignorado em
  // silencio no servidor: a pagina voltava com o nome antigo, o que se
  // le como avaria e nao como recusa.
  var novo = campo.value.trim();
  if (!novo) { campo.value = campo.dataset.antes; return; }
  if (novo === campo.dataset.antes) return;
  campo.value = novo;
  campo.form.requestSubmit();
}

function ligarCarta(carta) {
  carta.addEventListener('dragstart', function(e) {
    e.dataTransfer.setData('text/plain', carta.dataset.ref);
    carta.classList.add('arrastando');
  });
  carta.addEventListener('dragend', function() {
    carta.classList.remove('arrastando');
  });
}
document.querySelectorAll('.carta').forEach(ligarCarta);
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
    var donde = carta.parentElement;
    corpo.appendChild(carta);
    if (donde && donde !== corpo && !donde.querySelector('.carta')) {
      var nada = document.createElement('div');
      nada.className = 'coluna-vazia';
      nada.textContent = 'sem cartões, arrasta um para aqui';
      donde.appendChild(nada);
    }
    contarColunas();
    fetch('/quadro/mover', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ref: ref, fase_id: corpo.dataset.fase})
    }).then(function(r) {
      // o cartao ja foi movido no ecra; se o servidor recusou, o ecra
      // esta a mentir e tem de voltar ao que a base diz
      if (!r.ok) { alert('Não foi possível mover o cartão.'); location.reload(); return null; }
      return r.json();
    }).then(function(d) {
      if (!d) return;
      // O cartao que foi arrastado e o MESMO no DOM, com o HTML da
      // coluna de onde veio. Quem o desenha e o servidor, e o que ele
      // desenha depende da fase -- arrastar para "Submetido" mudava a
      // coluna e nao fazia aparecer o campo do preco proposto, nem
      // trocava o preco base pelo proposto, nem corrigia a soma no
      // cabecalho das duas colunas (o Afonso arrastou um cartao para o
      // Submetido e "nao aconteceu nada"). Ate 02/09/2026 a resposta
      // era recarregar a pagina; agora o servidor devolve o cartao
      // redesenhado e as contagens das duas colunas, e troca-se so isso.
      var molde = document.createElement('div');
      molde.innerHTML = d.carta || '';
      var nova = molde.firstElementChild;
      if (nova) { carta.replaceWith(nova); ligarCarta(nova); }
      Object.keys(d.contas || {}).forEach(function(fase) {
        var corpo2 = document.querySelector('.coluna-corpo[data-fase="' + fase + '"]');
        var coluna = corpo2 && corpo2.closest('.coluna');
        var conta = coluna && coluna.querySelector('.coluna-conta');
        if (conta) conta.outerHTML = d.contas[fase];
      });
    }).catch(function() {
      alert('Falhou a gravar, recarrega a página.'); location.reload();
    });
  });
});

</script>"""


# A partir do "Submetido" o numero que conta e o que se propos, nao o
# preco base -- decisao do Afonso a 01/09/2026. Vale para o cartao e
# para a soma da coluna: uma coluna de submetidos somada a precos base
# nao e o valor que esta em jogo, e o preco base ate ja se sabe que nao
# e o preco.
FASES_COM_PROPOSTO = ("submetido", "relatorio", "ganho", "perdido")


# O que cada fase pergunta, dito no cabecalho da coluna. Existe porque
# o campo so aparece quando ha um cartao la dentro: com o quadro vazio
# -- ou com tudo em "Por analisar", que e o caso normal -- nao havia
# nada no ecra a dizer que o "Submetido" pede o preco proposto, e a
# funcionalidade parecia nao existir. Foi o que o Afonso viu.
PEDIDO_DA_FASE = {"submetido": "pede o preço proposto",
                  "relatorio": "pede o lugar e os três primeiros",
                  "perdido": "pede porque se perdeu"}


def _campos_da_fase(a, papel):
    """O que a fase pede ao cartao, em formulario.

    Cada campo pertence a uma fase e a mais nenhuma: perguntar o lugar
    no relatorio preliminar a um cartao que ainda esta "por analisar" e
    ruido, e perguntar o preco proposto antes de haver proposta e
    perguntar por adivinhas. As fases sem nada a apontar ("Por
    analisar", "A preparar proposta", "Ganho") nao mostram formulario
    nenhum -- e o que o Afonso disse, por essas palavras.
    """
    accao_ = "/quadro/campos/" + a["ref"]
    if papel == "submetido":
        return ("<form class='carta-campos' method='post' action='%s' draggable='false'>"
                "<label>proposto</label>"
                "<input type='text' name='preco_proposto' value='%s' "
                "placeholder='ex. 118.500,00'>"
                "<button type='submit'>gravar</button></form>"
                % (accao_,
                   html.escape(_valor(a, "preco_proposto") or "", quote=True)))
    if papel == "relatorio":
        lugar = _valor(a, "posicao")
        return ("<form class='carta-campos' method='post' action='%s' draggable='false'>"
                "<label>lugar</label>"
                "<input type='number' name='posicao' min='1' max='99' "
                "value='%s' class='curto'>"
                "<label>os três primeiros</label>"
                "<input type='text' name='top3' value='%s' class='largo' "
                "placeholder='1º … · 2º … · 3º …'>"
                "<button type='submit'>gravar</button></form>"
                % (accao_, "" if lugar is None else int(lugar),
                   html.escape(_valor(a, "top3") or "", quote=True)))
    if papel == "perdido":
        actual = _valor(a, "motivo_perda") or ""
        opcoes = "".join(
            "<option value='%s'%s>%s</option>"
            % (html.escape(m, quote=True), " selected" if m == actual else "",
               html.escape(m))
            for m in MOTIVOS_PERDA)
        return ("<form class='carta-campos' method='post' action='%s' draggable='false'>"
                "<label>porque se perdeu</label>"
                "<select name='motivo_perda' required>"
                "<option value=''>escolhe…</option>%s</select>"
                "<button type='submit'>gravar</button></form>"
                % (accao_, opcoes))
    return ""


def cartao(a, etiquetas_por_ref, urgente=None, papel=""):
    if papel in FASES_COM_PROPOSTO and a["prazo"]:
        # A partir do "Submetido" o prazo ter passado e o estado normal:
        # a proposta foi entregue. A pilula vermelha "prazo expirado" e a
        # cor de alarme da lista, e a auditoria de 02/09/2026 encontrou-a
        # em 4 dos 9 cartoes do quadro, todos em fases pos-submissao --
        # a puxar o olho para uma coisa que nao pede accao nenhuma e a
        # roubar forca ao "3 dias" laranja de quem ainda prepara proposta.
        prazo_html = ("<span class='tag' title='prazo das propostas; a partir "
                      "do Submetido já não é alarme'>prazo %s</span>"
                      % data_pt(a["prazo"]))
    else:
        texto_prazo, classe_prazo = etiqueta_prazo(a["prazo"], urgente)
        prazo_html = ("<span class='tag %s'>&#9679; %s</span>"
                      % (classe_prazo, texto_prazo)) if texto_prazo else ""
    # Quadro <-> Calendario sao duas vistas do mesmo conjunto (§5 do
    # ESQUELETO): o cartao aponta para a SUA linha na grade, por ancora.
    # So quando o prazo cabe na janela -- fora dela a ancora nao existe
    # e a ligacao prometia o que a grade nao mostra.
    ref_ancora = a["ref"].replace("/", "-")
    dias, passou = dias_restantes(a["prazo"])
    vai_calendario = ("<a href='/calendario#c-%s' "
                      "style='margin-left:10px'>no calendário</a>"
                      % ref_ancora
                      if dias is not None and not passou
                      and dias < DIAS_CALENDARIO else "")
    # O preco do cartao muda de significado com a coluna. Antes do
    # "Submetido" e o preco base (o tecto que a entidade pos); dai para a
    # frente e o que se propos -- e enquanto o proposto nao estiver
    # preenchido mostra-se o base **dito como base**, que e diferente de
    # o mostrar como se fosse a proposta.
    if papel in FASES_COM_PROPOSTO and _valor(a, "preco_proposto"):
        texto_preco, dica_preco = a["preco_proposto"], "preço proposto"
    elif papel in FASES_COM_PROPOSTO:
        texto_preco = ("base " + a["preco_base"]) if a["preco_base"] else ""
        dica_preco = "preço base — o proposto ainda não está preenchido"
    else:
        texto_preco, dica_preco = a["preco_base"] or "", "preço base"
    preco_html = ("<span class='carta-preco' title='%s'>%s</span>"
                  % (dica_preco, html.escape(texto_preco))) \
        if texto_preco else ""
    etiquetas_html = "".join(
        "<span class='etq' style='background:%s'>%s%s</span>"
        % (e["cor"], html.escape(e["nome"]),
           accao("/quadro/etiqueta/%s/tirar/%d" % (a["ref"], e["id"]),
                 "&times;", "etq-x"))
        for e in etiquetas_por_ref.get(a["ref"], []))
    dono = ("<span class='av'>%s</span>" % _iniciais(a["responsavel"])) \
        if a["responsavel"] else ""
    return (
        "<div class='carta' id='c-%s' draggable='true' data-ref='%s'>"
        "<a href='/anuncio/%s' class='carta-titulo'>%s</a>"
        "<div class='carta-entidade'>%s</div>"
        "<div class='carta-meta'>%s%s</div>%s"
        "<div class='carta-etq'>%s"
        "<form class='etq-form' method='post' action='/quadro/etiqueta/%s/nova'>"
        "<input type='text' name='nome' placeholder='+ etiqueta' "
        "list='etiquetas-existentes' maxlength='24'></form></div>"
        "<div class='carta-pe'>%s%s%s</div>"
        "</div>"
        % (ref_ancora, a["ref"], a["ref"],
           html.escape(corta(a["titulo"], 120)),
           html.escape(a["entidade"]), preco_html, prazo_html,
           _campos_da_fase(a, papel),
           etiquetas_html, a["ref"],
           # o botao repunha o estado em "por ver" e chamava-se "tirar do
           # quadro": quem le isso espera perder a fase, nao a triagem --
           # e o anuncio voltava para a caixa de entrada com 66 mil
           accao("/estado/%s/novo" % a["ref"], "voltar a por ver", "tirar",
                 confirmar="Isto tira a marca de interessa e devolve o "
                           "anúncio à lista dos por ver. Continuar?"),
           vai_calendario, dono))


def conta_da_coluna(itens, papel):
    """O <span class='coluna-conta'> de uma coluna do quadro: quantos
    cartoes e, se houver precos lidos, a soma.

    B11: o valor da fase ao lado da contagem, como o kanban da SpotGov.
    So os precos lidos contam, e o title di-lo. A partir do "Submetido"
    soma-se o PROPOSTO: a soma dos precos base numa coluna de submetidos
    e o tecto da entidade, nao o que esta em jogo, e tinha o mesmo ar de
    numero certo.

    Vive em funcao propria porque /quadro/mover a devolve para as duas
    colunas tocadas: e assim que o quadro deixa de recarregar a pagina
    depois de um arrasto.
    """
    coluna_preco = ("preco_proposto" if papel in FASES_COM_PROPOSTO
                    else "preco_base")
    soma, com_preco = soma_precos_base(itens, coluna_preco)
    valor_fase = ""
    if soma:
        valor_fase = (" <span title='soma dos preços %s: %d de "
                      "%d anúncios têm preço'>· %s</span>"
                      % ("propostos" if coluna_preco == "preco_proposto"
                         else "base lidos",
                         com_preco, len(itens), euros_curto(soma)))
    return "<span class='coluna-conta'>%d%s</span>" % (len(itens), valor_fase)


def carta_e_contas(ref, fases_tocadas):
    """Para o /quadro/mover: o cartao redesenhado na fase em que esta e
    a contagem de cada coluna tocada, por id de fase (em texto, porque
    vai em JSON)."""
    urgente = dias_urgente()
    fases = {f["id"]: f for f in listar_fases()}
    with liga() as c:
        a = c.execute("SELECT * FROM anuncios WHERE ref=?", (ref,)).fetchone()
        etiquetas = c.execute(
            "SELECT e.* FROM etiquetas e JOIN anuncio_etiquetas ae "
            "ON ae.etiqueta_id = e.id WHERE ae.ref=? ORDER BY e.nome",
            (ref,)).fetchall()
        contas = {}
        for fid in fases_tocadas:
            if fid not in fases:
                continue
            itens = c.execute("SELECT * FROM anuncios WHERE estado='interessa' "
                              "AND fase_id=?", (fid,)).fetchall()
            contas[str(fid)] = conta_da_coluna(
                itens, _valor(fases[fid], "papel") or "")
    papel = (_valor(fases[a["fase_id"]], "papel") or "") \
        if a and a["fase_id"] in fases else ""
    carta = cartao(a, {ref: list(etiquetas)}, urgente, papel) if a else ""
    return carta, contas


def soma_precos_base(itens, coluna="preco_base"):
    """(soma, quantos com preco) de uma coluna do quadro.

    O preco e texto ("175.000,00 EUR") e passa por euros_do_texto(); os
    anuncios sem preco nao contam, e o cabecalho diz sobre quantos e que
    a soma e -- somar uns e calar os outros parecia o valor da fase
    inteira.

    A `coluna` existe porque a partir do "Submetido" o valor em jogo e o
    proposto: somar precos base numa coluna de submetidos dava o tecto
    da entidade e nao a proposta, com o mesmo ar de numero certo.
    """
    valores = [v for v in (euros_do_texto(_valor(a, coluna)) for a in itens)
               if v]
    return sum(valores), len(valores)


@app.route("/quadro")
def quadro():
    fases = listar_fases()
    urgente = dias_urgente()  # uma leitura por pedido, nao uma por cartao
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
        papel = _valor(f, "papel") or ""
        corpo = "".join(cartao(a, etiquetas_por_ref, urgente, papel)
                        for a in itens) or \
            "<div class='coluna-vazia'>sem cartões, arrasta um para aqui</div>"
        # B11: o valor da fase ao lado da contagem, como o kanban da
        # SpotGov. So os precos lidos contam, e o title di-lo. A partir
        # do "Submetido" soma-se o PROPOSTO: a soma dos precos base numa
        # coluna de submetidos e o tecto da entidade, nao o que esta em
        # jogo, e tinha o mesmo ar de numero certo.
        # O que a coluna pergunta, dito no cabecalho: com tudo em "Por
        # analisar" (o caso normal) nao havia nada no ecra a dizer que o
        # "Submetido" pede o preco proposto, e a funcionalidade parecia
        # nao existir.
        pede = PEDIDO_DA_FASE.get(papel, "")
        colunas.append(
            "<div class='coluna'><div class='coluna-cab'>"
            "<form method='post' action='/quadro/fase/%d/renomear'>"
            "<input class='fase-nome' type='text' name='nome' value='%s' "
            "data-antes='%s' required onblur='renomearFase(this)'></form>"
            "%s%s</div>"
            "<div class='coluna-corpo' data-fase='%d'>%s</div></div>"
            % (f["id"], html.escape(f["nome"], quote=True),
               html.escape(f["nome"], quote=True),
               conta_da_coluna(itens, papel),
               ("<span class='coluna-pede'>%s</span>" % html.escape(pede))
               if pede else "",
               f["id"], corpo))

    datalist = "".join("<option value='%s'>" % html.escape(e["nome"], quote=True)
                       for e in todas_etiquetas)

    # As seis colunas sao o funil da casa e nao se criam nem se apagam
    # (decisao do Afonso a 01/09/2026): o formulario "+ Nova fase" saiu
    # daqui, e o "x" de apagar saiu do cabecalho de cada coluna.
    conteudo = ("<div class='quadro-topo'>"
                "<span class='d'>Só entram anúncios marcados como "
                "&ldquo;interessa&rdquo; &middot; arrastar move de fase "
                "&middot; o nome da fase edita-se no sítio &middot; cada "
                "fase pede o que lhe falta</span></div>"
                "<div class='quadro'>%s</div>"
                "<datalist id='etiquetas-existentes'>%s</datalist>"
                % ("".join(colunas), datalist))

    migalhas = migalhas_de("quadro")
    return envolver("quadro", "Quadro",
                    "As seis fases do funil &middot; só anúncios marcados "
                    "como &ldquo;interessa&rdquo;.",
                    conteudo, migalhas=migalhas, script=QUADRO_JS,
                    titulo_aba="Quadro, Radar de Concursos")


# ----------------------------------------------------------- calendario

DIAS_CALENDARIO = 45


@app.route("/calendario")
def calendario():
    hoje = datetime.now().date()
    urgente = dias_urgente()  # uma leitura por pedido, nao uma por linha
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
                       "Marca alguns como &ldquo;interessa&rdquo; nos "
                       "<a href='/'>Anúncios</a>.</div>")

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

    # As cores da paleta, e nao as antigas escritas a mao: a pilula tem
    # 9,5px e a combinacao de antes ficava a 4,1:1 sobre o proprio fundo.
    cores = {"ok": ("var(--verde-fundo)", "var(--verde)"),
             "avisa": ("var(--laranja-fundo)", "var(--laranja)"),
             "mau": ("var(--verm-fundo)", "var(--verm)")}
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
        _, classe = etiqueta_prazo(a["prazo"], urgente)
        fundo, frente = cores.get(classe,
                                  ("var(--azul-fundo)", "var(--azul)"))
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
        # A ancora e a ligacao de volta: quadro <-> calendario sao duas
        # vistas do mesmo conjunto, e cada linha aponta para o SEU
        # cartao (§5 do ESQUELETO). A ligacao vai em linha propria: no
        # .ent, o nowrap+ellipsis da entidade comia-a nos nomes longos.
        ref_ancora = a["ref"].replace("/", "-")
        linhas.append("<div class='linha-grade' id='c-%s' style='%s'>"
                      "<div class='cel-titulo'><a href='/anuncio/%s'>%s</a>"
                      "<div class='ent'>%s</div>"
                      "<div class='ent'><a href='/quadro#c-%s'>no quadro"
                      "</a></div></div>%s</div>"
                      % (ref_ancora, grelha, a["ref"],
                         html.escape(corta(a["titulo"], 70)),
                         html.escape(a["entidade"]), ref_ancora,
                         "".join(celulas)))

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
    desde = (hoje - timedelta(days=30)).isoformat()
    d = {}
    with liga() as c:
        d["entrados"] = c.execute(
            "SELECT COUNT(*) n FROM anuncios WHERE data_pub >= ?",
            (desde,)).fetchone()["n"]
        # As quatro barras do funil na MESMA janela de 30 dias. Estavam
        # misturadas: "Entrados (30 dias) 2 476" seguido de "Por ver
        # 66 007" de sempre, o que num funil e impossivel -- a segunda
        # barra maior do que a primeira -- e so era possivel porque as
        # duas mediam periodos diferentes.
        d["porver_30"] = c.execute(
            "SELECT COUNT(*) n FROM anuncios WHERE data_pub >= ? "
            "AND estado = 'novo'", (desde,)).fetchone()["n"]
        # As alteracoes (republicacoes) nao sao triagem de ninguem: sem
        # as tirar, 763 delas contavam como "triadas".
        d["triados_30"] = c.execute(
            "SELECT COUNT(*) n FROM anuncios WHERE data_pub >= ? "
            "AND estado NOT IN ('novo', 'alteracao')", (desde,)).fetchone()["n"]
        d["interessa_30"] = c.execute(
            "SELECT COUNT(*) n FROM anuncios WHERE data_pub >= ? "
            "AND estado = 'interessa'", (desde,)).fetchone()["n"]
        d["triados"] = c.execute(
            "SELECT COUNT(*) n FROM anuncios "
            "WHERE estado NOT IN ('novo', 'alteracao')").fetchone()["n"]
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
            janela_urgente(hoje)).fetchone()["n"]
        # (o "expirados por ver" saiu a 31/08/2026: com a lista unica,
        # um por ver expirado conta como abandonado por definicao da
        # aba -- deixou de haver fila a mostrar)
        # Onde a triagem tem acontecido, por divisao de CPV
        d["por_divisao"] = c.execute(
            "SELECT substr(cpv,1,2) div, "
            " SUM(estado='interessa') sim, SUM(estado='descartado') nao, "
            " COUNT(*) tudo FROM anuncios WHERE cpv != '' "
            " AND estado NOT IN ('novo', 'alteracao') "
            "GROUP BY div ORDER BY tudo DESC LIMIT 8").fetchall()
    return d


def linhas_de_saude(itens, cor_ma="#c0392b"):
    """As linhas de (rotulo, valor, esta_bem) da coluna dos indicadores.

    Com `esta_bem` a None a linha e uma legenda: sem ponto e sem juizo,
    para dizer sobre o que e que as linhas seguintes contam."""
    saida = []
    for t, v, bom in itens:
        if bom is None:
            saida.append("<div class='l legenda'><span class='t'>%s</span>"
                         "<span class='v'>%s</span></div>" % (t, v))
        else:
            saida.append(
                "<div class='l'><span class='ponto' style='background:%s'>"
                "</span><span class='t'>%s</span><span class='v'>%s</span>"
                "</div>" % ("#1e8449" if bom else cor_ma, t, v))
    return "".join(saida)


def linhas_de_ultimos_erros(relogio=None, pecas=None, analise=None,
                            token=None, triagem=None, vortal=None,
                            pecas_dr=None, ocr=None):
    """As marcas de ultimo erro que so se viam por SQL (C1 do saneamento).

    So aparece o que existe: sem erro gravado nao ha linha nenhuma --
    uma linha verde "sem erros" era ruido. As marcas trazem a data de
    quando aconteceram, e mostram-se a amarelo (quem chama passa a cor):
    um erro antigo e diagnostico, nao um alarme de agora. A do token
    (E4) traz a idade da captura no momento da expiracao -- e a serie
    completa fica na tabela `erros` (C3), por SQL.

    A da triagem e a da Vortal chegaram com o B15 e o B14, DEPOIS do
    saneamento, e ficaram a escrever para um sitio que nenhum ecra lia
    -- exactamente o C1 outra vez. Quem acrescentar um marca_erro()
    novo acrescenta-o tambem aqui, senao o erro so existe para quem
    abrir a base a mao.
    """
    linhas = []
    for rotulo, valor in (("Último erro do relógio interno", relogio),
                          ("Último erro ao trazer peças", pecas),
                          ("Último erro da leitura pelo modelo", analise),
                          ("Última expiração do token", token),
                          ("Último erro a gravar a triagem no git", triagem),
                          ("Último erro na Vortal", vortal),
                          ("Último erro a renovar as peças do DR", pecas_dr),
                          ("Último erro do OCR", ocr)):
        if (valor or "").strip():
            # numa linha so antes de cortar: um erro de varias linhas
            # gastava metade dos 80 caracteres em mudancas de linha e
            # indentacao que o HTML nem mostra
            limpo = re.sub(r"\s+", " ", valor).strip()
            linhas.append((rotulo, html.escape(corta(limpo, 80)), False))
    return linhas


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
        # A MESMA janela do filtro prazo=urgente (janela_urgente): havia
        # aqui um 7 escrito a mao com o filtro a 10, e o numero do cartao
        # nao abria lista nenhuma que o confirmasse.
        urgentes = c.execute(
            "SELECT COUNT(*) n FROM anuncios WHERE estado='interessa' "
            "AND prazo >= ? AND prazo <= ?",
            janela_urgente(hoje)).fetchone()["n"]
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

    # "0 novos" ao sabado com "~60-70/dia" ao lado lia-se como recolha
    # avariada; a parte L nao publica ao fim-de-semana e o cartao di-lo.
    nota_hoje = ("fim-de-semana: a parte L não publica"
                 if hoje.weekday() >= 5 else "a parte L publica ~60-70/dia")
    # O numero dos urgentes abre a lista que o confirma -- um numero sem
    # saida obrigava a reconstruir o filtro a mao (e com outro limiar).
    # A lista e a Pesquisa com o arquivo: conta-se sobre a base toda, e
    # a Triagem so mostra a janela dos detalhe_dias.
    nota_urgentes = "%s com prazo a menos de %d dias" % (mil(urgentes),
                                                         dias_urgente())
    if urgentes:
        nota_urgentes = ("<a href='/?estado=interessa&amp;prazo=urgente' "
                         "style='color:inherit;text-decoration:underline'>"
                         "%s</a>" % nota_urgentes)
    kpis = [("Anúncios na base", mil(total), "%s com detalhe lido" % mil(com_detalhe), ""),
            ("Novos hoje", mil(hoje_n), nota_hoje, ""),
            ("Interessa", mil(interessa), nota_urgentes,
             "color:var(--verm)" if urgentes else ""),
            ("Sem detalhe lido", mil(porler),
             "lidos ao abrir a ficha, ou em rotina", "color:var(--laranja)" if porler else "")]
    kpis_html = "".join(
        "<div class='kpi'><div class='r'>%s</div><div class='v'>%s</div>"
        "<div class='d' style='%s'>%s</div></div>" % (r, v, estilo, d)
        for r, v, d, estilo in kpis)

    maior = max(list(por_fase.values()) + [1])
    # As fases sao um caminho, como o funil: uma cor so, a escurecer do
    # principio para o fim. Eram cinco cores sem sistema (bege, azul,
    # laranja, preto, verde) e duas delas vinham das cores de estado --
    # a coluna "Submetido" a laranja parecia um aviso e nao e.
    cores_barra = ("#c3ced9", "#9db1c4", "#7994ae", "#5c809f", "#17557f")
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
    tem_ocr = ocr_instalado()
    saude = [("Captura curl_DR.txt", tem_dr, tem_dr == "válido"),
             ("Captura curl_detalhe.txt", tem_det, tem_det == "válido"),
             ("OCR das digitalizações",
              ("instalado" if ocr_ligado() else "instalado, desligado no "
               "config.json") if tem_ocr else
              "por instalar (pip install rapidocr onnxruntime)", tem_ocr)]
    # O denominador, escrito. As percentagens das plataformas sao sobre
    # os anuncios com detalhe lido -- 8% da base -- e ficavam ao lado de
    # um cartao a dizer "Sem detalhe lido 60 589". Lidas em conjunto, a
    # unica leitura possivel era a errada: que 1% da base nao tinha
    # plataforma, quando eram 92%.
    saude.append(("as percentagens abaixo são sobre os %s anúncios com "
                  "detalhe lido, não sobre a base toda" % mil(com_detalhe),
                  "", None))
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
    # "Peças", como em todo o lado: "documentos" no ecra e so os da
    # proposta (vocabulario da §7 do ESQUELETO).
    saude.append(("Peças guardadas", mil(n_docs), True))
    try:
        tam = os.path.getsize(DB) / (1024.0 * 1024)
        with liga() as c:
            modo = c.execute("PRAGMA journal_mode").fetchone()[0]
        saude.append(("Base de dados", "%.0f MB &middot; %s" % (tam, modo.upper()), True))
    except OSError:
        pass
    # A copia de seguranca: falhava em silencio (C2 do saneamento). So
    # ha linha quando ja correu alguma vez; vermelho quando a ultima
    # tentativa falhou, que e estado presente, nao historia.
    copia = le_marca("ultima_copia", "")
    if copia:
        saude.append(("Cópia de segurança", html.escape(corta(copia, 80)),
                      copia.startswith("ok")))

    # O corpus do BASE e a segunda metade da aplicacao, e estava fora
    # desta pagina -- os indicadores diziam que estava tudo bem sem
    # sequer olhar para ele.
    n_corpus = ha_corpus()
    if n_corpus:
        with liga_corpus() as c:
            anos_c = [r["a"] for r in
                      c.execute("SELECT DISTINCT ano a FROM contratos ORDER BY a")]
            n_ent = c.execute("SELECT COUNT(*) n FROM entidades").fetchone()["n"]
            # Quantas e que tem mesmo NIF. "Entidades identificadas
            # 137 904" prometia uma identificacao que 45% delas nao tem:
            # 10% dos adjudicatarios do dump do IMPIC vem sem NIF e ficam
            # agarrados a uma chave feita do nome, que pode ser outra
            # grafia de uma entidade que ja la esta.
            n_ent_nif = c.execute("SELECT COUNT(*) n FROM entidades "
                                  "WHERE chave NOT LIKE 'n:%'").fetchone()["n"]
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
            ("Entidades com NIF", mil(n_ent_nif), True),
            ("Entidades só com nome", mil(n_ent - n_ent_nif),
             (n_ent - n_ent_nif) * 2 < n_ent),
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
    # Os ultimos erros gravados, que so se viam por SQL (C1): a amarelo,
    # porque a marca e sobrescrita e pode ser antiga -- a data vai nela.
    erros = linhas_de_ultimos_erros(le_marca("ultimo_erro_relogio", ""),
                                    le_marca("docs_ultimo_erro", ""),
                                    le_marca("analise_ultimo_erro", ""),
                                    le_marca("token_ultimo_erro", ""),
                                    le_marca("ultimo_erro_triagem_git", ""),
                                    le_marca("vortal_ultimo_erro", ""),
                                    le_marca("pecas_dr_ultimo_erro", ""),
                                    le_marca("ocr_ultimo_erro", ""))
    saude_html = (linhas_de_saude(saude)
                  + linhas_de_saude(erros, "#d68910"))

    # O funil: o que entra, o que se olha, o que vinga. Os indicadores
    # contavam estados parados e nao diziam nada sobre o movimento.
    f = funil_anuncios()
    # As quatro barras sao um degrade de uma cor so, do mais claro ao
    # mais escuro: sao passos do mesmo caminho, nao quatro categorias.
    # Estavam em cinzento, laranja, azul e verde -- quatro cores sem
    # sistema, e as duas ultimas roubadas as cores de estado, que aqui
    # nao significam "bom" nem "a avisar".
    passos = [("Entrados", f["entrados"], "#b9c6d2"),
              ("Por ver", f["porver_30"], "#8ba3ba"),
              ("Triados", f["triados_30"], "#5c809f"),
              ("Interessa", f["interessa_30"], "var(--azul)")]
    maior_f = max([p[1] for p in passos] + [1])
    funil_html = "".join(
        "<div class='col'><span class='v'>%s</span>"
        "<div class='b' style='height:%d%%;background:%s'></div>"
        "<span class='l'>%s</span></div>"
        % (mil_pt(n), int(88.0 * n / maior_f) + 6, cor, etiqueta)
        for etiqueta, n, cor in passos)

    # Uma percentagem sobre dois casos e ruido com ar de conclusao: "de
    # tudo o que ja triaste, 100% ficou como interessa" com n=2 nao diz
    # nada sobre nada.
    if f["triados"] >= MINIMO_PARA_TAXA:
        taxa = 100.0 * f["interessa"] / f["triados"]
        leitura = ("De tudo o que já triaste, <b>%.0f%%</b> ficou como "
                   "interessa." % taxa)
    elif f["triados"]:
        leitura = ("Só %s anúncio%s triado%s até agora &mdash; poucos para "
                   "uma percentagem dizer alguma coisa."
                   % (mil_pt(f["triados"]), "" if f["triados"] == 1 else "s",
                      "" if f["triados"] == 1 else "s"))
    else:
        leitura = "Ainda não triaste nada, por isso não há taxa a mostrar."

    # Os numeros levam ao sitio: eram duas contagens numa frase corrida,
    # sem forma de chegar aos anuncios que contavam. A saida e a
    # Pesquisa com o arquivo: as contas sao sobre a base toda, e a
    # Triagem so mostra a janela dos detalhe_dias.
    alertas = []
    if f["urgentes_por_ver"]:
        alertas.append(
            "<a href='/?estado=novo&prazo=urgente'>"
            "<b>%s por ver com prazo a menos de %d dias</b></a>"
            % (mil_pt(f["urgentes_por_ver"]), dias_urgente()))
    # os "expirados por ver" deixaram de existir como alerta: desde a
    # fusao de 31/08/2026 um por ver expirado E um abandonado, por
    # definicao da aba -- nao ha fila a limpar nem numero a mostrar
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
               html.escape(corta(nomes_div.get(r["div"], "sem descrição"), 40)),
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
        antes = c.execute("SELECT fase_id FROM anuncios WHERE ref=? "
                          "AND estado='interessa'", (ref,)).fetchone()
        if not antes:
            return {"ok": False, "erro": "anúncio não está no quadro"}, 404
        c.execute("UPDATE anuncios SET fase_id=? WHERE ref=?", (fase_id, ref))
    registar(ref, "fase", fase["nome"])
    # O cartao redesenhado e as contagens das duas colunas, para o
    # cliente trocar so isso em vez de recarregar a pagina: quem decide o
    # que o cartao mostra e o servidor, pela fase (o campo do proposto, o
    # preco que se le, a soma no cabecalho), e ate 02/09/2026 a unica
    # forma de o ecra ficar certo era um location.reload() depois de cada
    # arrasto.
    carta, contas = carta_e_contas(ref, {antes["fase_id"], fase_id})
    return {"ok": True, "carta": carta, "contas": contas}


# As fases criam-se e apagam-se? Ja nao (decisao do Afonso a
# 01/09/2026). O quadro passou a ser o funil da casa -- seis colunas com
# papel definido, e o cartao muda com a coluna em que esta. Criar uma
# setima coluna nao teria papel nenhum, e apagar uma das seis levaria
# consigo o campo que ela pede. Renomear continua a dar.


@app.route("/quadro/fase/<int:fase_id>/renomear", methods=["POST"])
def fase_renomear(fase_id):
    nome = (request.form.get("nome") or "").strip()
    if nome:
        with liga() as c:
            c.execute("UPDATE fases SET nome=? WHERE id=?", (nome, fase_id))
    return redirect("/quadro")


@app.route("/quadro/campos/<path:ref>", methods=["POST"])
def quadro_campos(ref):
    """Os campos que cada fase pede, gravados a partir do cartao.

    Um so caminho para os tres, e nao tres rotas quase iguais: o que
    manda e o papel da fase em que o cartao esta, e cada campo so se
    grava se vier no formulario. O historico fica com o que mudou --
    "submetido a 118 500 EUR" vale mais, tres meses depois, do que a
    coluna onde o cartao parou.
    """
    campos, registos = [], []
    valores = []
    if "preco_proposto" in request.form:
        bruto = " ".join((request.form.get("preco_proposto") or "").split())
        # Guarda-se no formato do preco base ("118.500,00 EUR"), que e o
        # que euros_do_texto() e as somas do quadro ja sabem ler --
        # **nao** no de euros(), que poe espaco nos milhares e faz o
        # euros_do_texto() ler "118" de "118 500 €". Um numero que nao
        # se perceba fica como foi escrito, em vez de virar zero em
        # silencio.
        valor = euros_do_texto(bruto)
        texto = (_texto_do_preco(valor) if valor else bruto)
        campos.append("preco_proposto=?")
        valores.append(texto or None)
        registos.append(("preço proposto", texto or "(apagado)"))
    if "posicao" in request.form or "top3" in request.form:
        bruto = (request.form.get("posicao") or "").strip()
        try:
            lugar = int(bruto) if bruto else None
        except ValueError:
            lugar = None
        top3 = " ".join((request.form.get("top3") or "").split())[:300]
        campos.append("posicao=?")
        valores.append(lugar)
        campos.append("top3=?")
        valores.append(top3 or None)
        registos.append(("relatório preliminar",
                         "%s%s" % ("%dº lugar" % lugar if lugar else "sem lugar",
                                   " — " + top3 if top3 else "")))
    if "motivo_perda" in request.form:
        motivo = (request.form.get("motivo_perda") or "").strip()
        if motivo and motivo not in MOTIVOS_PERDA:
            return _volta_com_aviso("Esse motivo de perda não existe.")
        campos.append("motivo_perda=?")
        valores.append(motivo or None)
        registos.append(("porque se perdeu", motivo or "(apagado)"))
    if not campos:
        return redirect(request.referrer or "/quadro")
    with liga() as c:
        c.execute("UPDATE anuncios SET " + ", ".join(campos) + " WHERE ref=?",
                  valores + [ref])
    for accao_, detalhe in registos:
        registar(ref, accao_, detalhe)
    return redirect(request.referrer or "/quadro")


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

def porta_atende(porta, espera=0.5):
    """True se ja houver quem aceite ligacoes nesta porta do localhost.

    Cuidado com o que isto custa no Windows: a uma porta onde ninguem
    fez bind, a ligacao e recusada logo; a uma porta com bind feito mas
    ainda SEM listen -- que e exactamente o instante em que o Flask
    esta a arrancar -- nao vem recusa nenhuma, vem WSAEWOULDBLOCK ao
    fim do timeout inteiro. Por isso `espera` e por tentativa e curta.
    """
    with socket.socket() as s:
        s.settimeout(espera)
        return s.connect_ex(("127.0.0.1", porta)) == 0


def abrir_no_browser(porta=None, espera=15.0):
    """Abre o painel no browser DEPOIS de a porta atender.

    O open() era chamado antes do app.run() e chegava la antes de haver
    servidor: medido a 01/09/2026, o browser aos 0,98 s e a porta a
    responder aos 1,91 s. Com o browser ja aberto -- que e o caso normal
    -- o separador novo apanhava a porta fechada e ficava num erro que
    so um F5 tirava; parecia que o radar demorava a arrancar.

    Espera pela porta em vez de adivinhar um tempo, porque o arranque
    varia com o disco (isto corre de uma pen). Se nao atender dentro da
    espera nao abre nada: o endereco ja foi impresso na consola, e uma
    janela de erro nao ajuda ninguem.
    """
    porta = porta or PORTA
    limite = time.time() + espera
    while time.time() < limite:
        if porta_atende(porta):
            try:
                webbrowser.open("http://localhost:%d/" % porta)
            except Exception:
                pass
            return True
        time.sleep(0.1)
    return False


def main():
    iniciar_db()
    # As migracoes do corpus tambem correm no arranque, nao so na
    # importacao: um corpus ja em disco levava as colunas novas (o
    # desescape do HTML, o objecto_norm da pesquisa) so quando o Afonso
    # carregasse em "Actualizar contratos", e a pesquisa mentia ate la.
    if os.path.exists(CORPUS):
        iniciar_corpus()
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

    if "--importar-excel" in sys.argv:
        # O Excel de analise de concursos da casa. Sem caminho, repete o
        # da ultima importacao (marca `excel_casa`). --ensaio calcula e
        # nao grava; --sem-rede nao vai ao DR desempatar pelo preco base.
        i = sys.argv.index("--importar-excel")
        caminho = (sys.argv[i + 1] if len(sys.argv) > i + 1
                   and not sys.argv[i + 1].startswith("--") else le_marca("excel_casa"))
        if not caminho or not os.path.exists(caminho):
            print("Diz-me o ficheiro: python radar.py --importar-excel "
                  "<caminho do .xlsm> [--ensaio] [--sem-rede]")
            return
        ini = time.time()
        rel = casa.importar(caminho, ensaio="--ensaio" in sys.argv,
                            ler="--sem-rede" not in sys.argv,
                            triagem="--com-triagem" in sys.argv)
        print(casa.texto_do_relatorio(rel))
        print("(%.0f s)" % (time.time() - ini))
        return

    if "--casa-ligar" in sys.argv:
        # Liga a mao uma linha do registo da casa a um anuncio:
        # python radar.py --casa-ligar 94 4284/2026
        i = sys.argv.index("--casa-ligar")
        try:
            ide, ref = int(sys.argv[i + 1]), sys.argv[i + 2]
        except (IndexError, ValueError):
            print("Uso: python radar.py --casa-ligar <id do Excel> <ref do anúncio>")
            return
        with liga() as c:
            ok, msg = casa.ligar_a_mao(c, ide, ref, quem="Afonso",
                                       triagem="--com-triagem" in sys.argv)
        print(msg)
        return

    if "--casa-desfazer" in sys.argv:
        # Desfaz a triagem que uma importacao escreveu, a partir de uma
        # copia da base feita antes dela (copias/radar-antes-excel-*.db).
        i = sys.argv.index("--casa-desfazer")
        copia = sys.argv[i + 1] if len(sys.argv) > i + 1 else ""
        if not copia or not os.path.exists(copia):
            print("Uso: python radar.py --casa-desfazer <cópia da base de antes>")
            return
        repostos, apagadas = casa.desaplicar_da_copia(copia)
        print("%d anúncios com a triagem reposta como estava na cópia; "
              "%d linhas de histórico do Excel apagadas" % (repostos, apagadas))
        return

    if "--reler" in sys.argv:
        # Manutencao, nao uso diario: so faz sentido depois de mexer em
        # campos_do_detalhe(). Nao toca na rede -- reanalisa o texto que
        # ja esta guardado, uns segundos para a base toda.
        ini = time.time()
        n = reparsear()
        with liga() as c:
            n_alt = c.execute("SELECT COUNT(*) n FROM anuncios "
                              "WHERE estado='alteracao'").fetchone()["n"]
        print("%d anúncios reanalisados a partir do texto guardado, "
              "em %.1f segundos (nenhum pedido ao DR); %d são alterações "
              "ligadas ao anúncio original" % (n, time.time() - ini, n_alt))
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
    if "--exportar-triagem" in sys.argv:
        # B15: tambem corre sozinho em cada verificacao; o comando serve
        # para exportar a mao antes de um commit.
        n, caminho = exportar_triagem()
        print("%d registos de triagem em %s" % (n, os.path.basename(caminho)))
        return

    if "--repor-triagem" in sys.argv:
        # B15: correr DEPOIS de a base ser refeita pela recolha -- o
        # ficheiro guarda decisoes, nao anuncios. Idempotente.
        i = sys.argv.index("--repor-triagem")
        caminho = sys.argv[i + 1] if (i + 1 < len(sys.argv) and
                                      not sys.argv[i + 1].startswith("--")) \
            else None
        escritas, por_repor = repor_triagem(caminho)
        print("%d registo(s) repostos." % escritas)
        for tabela, refs in sorted(por_repor.items()):
            print("  por repor em %s (%d) — os anúncios ainda não estão "
                  "na base; volta a correr depois da recolha: %s%s"
                  % (tabela, len(refs), ", ".join(refs[:8]),
                     "…" if len(refs) > 8 else ""))
        return

    if "--ocr" in sys.argv:
        # Le pelo OCR as digitalizacoes que ja estavam na base (as
        # novas leem-se sozinhas quando se pedem as pecas). Com um ref a
        # seguir, so esse anuncio.
        i = sys.argv.index("--ocr")
        ref = sys.argv[i + 1] if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--") else None
        ocr_pendentes(ref)
        return

    if "--descartar-expirados" in sys.argv:
        # Arruma a fila de triagem: um anuncio por ver cujo prazo ja
        # passou deixou de ser oportunidade. So os "por ver" -- um
        # "interessa" com prazo passado e trabalho em curso (proposta
        # entregue, a aguardar decisao) e nao se descarta por ele. E so
        # quem tem prazo lido: sem detalhe nao ha data para julgar.
        hoje = datetime.now().date().isoformat()
        with liga() as c:
            refs = [r["ref"] for r in c.execute(
                "SELECT ref FROM anuncios WHERE estado='novo' "
                "AND prazo IS NOT NULL AND prazo != '' AND prazo < ?",
                (hoje,))]
            c.execute(
                "UPDATE anuncios SET estado='descartado' "
                "WHERE estado='novo' AND prazo IS NOT NULL "
                "AND prazo != '' AND prazo < ?", (hoje,))
            # o registo vai na mesma transaccao: 4 mil registar() avulsos
            # eram 4 mil transaccoes, e em fundo nao ha cookie -- o quem
            # e explicito, como no resto do trabalho fora de pedido
            quando = datetime.now().strftime("%Y-%m-%d %H:%M")
            c.executemany(
                "INSERT INTO historico (ref,quem,accao,detalhe,quando) "
                "VALUES (?,?,?,?,?)",
                [(ref, "radar", "estado", "descartado (prazo passado)",
                  quando) for ref in refs])
        print("%d anúncio(s) por ver com prazo passado passaram a "
              "descartados." % len(refs))
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
    # Em thread, e a espera da porta: o app.run() so devolve quando o
    # painel fechar, portanto quem abre o browser tem de ser outro.
    threading.Thread(target=abrir_no_browser, daemon=True).start()
    app.run(host="127.0.0.1", port=PORTA, debug=False)


if __name__ == "__main__":
    main()
