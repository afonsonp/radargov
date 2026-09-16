#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Radar de Concursos, Diario da Republica.

Vigia a parte L da serie II do DR, filtra os anuncios que interessam
e apresenta-os num painel local. Verifica sozinho as 09:00 e as 17:00.

Fonte unica: o servico de pesquisa do proprio portal do DR, chamado
com os cabecalhos de uma captura feita uma vez no browser (curl_DR.txt).

Arranque:  python radar.py             painel em http://127.0.0.1:8765
           python radar.py --sem-browser   o mesmo, sem abrir o browser (servico)
           python radar.py --uma-vez   verifica e sai, para as tarefas
           python radar.py --historico N   puxa N dias de historico
           python radar.py --historico DE ATE   varre um intervalo, por janelas
           python radar.py --detalhes [N|tudo]   le o detalhe do que falta
           python radar.py --reler     reanalisa o texto ja guardado
           python radar.py --descartar-expirados   arruma os por ver com prazo passado
           python radar.py --importar-cpv F   carrega o vocabulario CPV
"""

import bisect
import copy
import csv
import html
import io
import json
import mimetypes
import os
import re
import queue
import shlex
import smtplib
import statistics
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
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import casa                      # o registo da casa (casa.py importa o radar por dentro)
import contas                    # as contas e as sessoes (contas.py nao importa o radar)
from email.message import EmailMessage
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlparse

try:
    import requests
    from flask import abort, Flask, g, has_request_context, redirect, \
        request, Response, send_file
    from werkzeug.middleware.proxy_fix import ProxyFix
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
LISBOA = ZoneInfo("Europe/Lisbon")
# O painel atende em 127.0.0.1 -- e o endereco escreve-se assim, e nao
# "localhost", em todo o lado. Nao e cosmetica: no Windows da pen o
# `localhost` resolvia para ::1 ANTES de 127.0.0.1, e ninguem estava a
# escutar em IPv6; ligar a uma porta reservada e sem escuta la nao era
# recusado -- bloqueava --, portanto o browser esperava pelo IPv6,
# desistia, e so entao tentava o IPv4. Medido a 04/09/2026, no browser e
# na mesma pagina: 208 ms por pedido por `localhost` contra 37 ms por
# 127.0.0.1. E um imposto fixo em cada clique do painel.
#
# A alternativa era pôr o servidor a atender tambem em ::1, com uma
# segunda thread. Nao se fez: o painel e local por desenho, e trocar o
# endereco custa uma constante e nao arrisca segundos servidores no
# mesmo processo. Quem tiver `localhost:8765` nos favoritos ganha em
# trocar por 127.0.0.1:8765.
ENDERECO = "127.0.0.1"
LOCAL = "http://%s:%d" % (ENDERECO, PORTA)


def endereco_do_painel(cfg=None):
    """O endereco que vai nos links do e-mail: o publico, se houver.

    Com o painel a sair do PC (o tunel com nome para radargov.pt,
    8/09/2026), um link `127.0.0.1:8765` no e-mail so abre neste
    computador. `endereco_publico` no config.json e o que o
    substitui; vazio, fica o local, que e o que sempre foi.
    """
    cfg = cfg if cfg is not None else ler_config()
    publico = (cfg.get("endereco_publico") or "").strip().rstrip("/")
    if publico and not publico.startswith(("http://", "https://")):
        publico = "https://" + publico
    return publico or LOCAL

ACAO = ("https://diariodarepublica.pt/dr/screenservices/dr/Pesquisas/"
        "PesquisaResultado/DataActionGetPesquisas")

CONFIG_INICIAL = {
    "horas_verificacao": ["09:00", "17:00"],
    # Um pedido vindo deste computador (127.0.0.1, sem tunel a meio)
    # entra sem login, como o unico utilizador. E o que mantem o
    # desenvolvimento e os testes sem fazerem login a cada pedido. Num
    # servidor poe-se a False -- e o arranque recusa-se a ouvir fora
    # do localhost com isto a True (arranque_permitido()).
    "acesso_livre_local": True,
    # O endereco publico do painel (https://radargov.pt), para os links
    # do e-mail. Vazio: 127.0.0.1:8765, que so abre neste computador.
    "endereco_publico": "",
    "dias_catchup": 15,
    "recuperar_slot_falhado": True,
    "abrir_browser_ao_encontrar": False,
    "detalhes_por_volta": 40,
    # Quantos anuncios NA ESCADA se releem por verificacao, a procura de
    # prorrogacoes e precos base novos (B05). Marcado = tem proposta.
    "relidos_por_volta": 25,
    # A janela do "urgente", em dias (B13). Edita-se tambem em /alertas.
    "dias_urgente": 10,
    # O INTERESSE (01/09/2026): o recorte permanente da lista de
    # anuncios, por CPV. Define-se em Alertas › Interesse. Nao e um
    # filtro -- e o que a casa faz; um filtro guardado esquece-se de se
    # pôr e apaga-se sem querer. Com "interesse_activo" a False, ou sem
    # CPV escolhido, a lista volta ao acervo todo. Formato dos dois
    # campos: codigos separados por "|", como o filtro.
    # Quem somos nos, para o cruzamento com o Portal BASE saber se a
    # adjudicacao foi nossa (etapa 4). Vazios de origem, e a
    # funcionalidade vale na mesma: sem eles o ecra mostra a quem foi
    # adjudicado e PERGUNTA se fomos nos, que e o que ja fazia.
    "nome_da_casa": "",
    "nif_da_casa": "",
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

class Ligacao(sqlite3.Connection):
    """Uma ligacao que se FECHA ao sair do `with`.

    O `with` do sqlite3 de origem so faz commit/rollback: a ligacao fica
    aberta ate o garbage collector a apanhar, e com ciclos de
    referencia (cursores, Rows) isso demora. Medido a 8/09/2026, no
    painel a servir radargov.pt: 501 ligacoes abertas ao radar.db, 1024
    descritores -- o limite do processo -- e o servidor a rodar a 100%
    de CPU sem conseguir aceitar mais ninguem (EMFILE no accept, em
    ciclo) durante quase quatro horas. Sao 118 `with liga() as c` e
    24 `with liga_corpus() as c`; fechar num sitio so e o que os
    protege a todos. Quem precisar da ligacao depois do bloco nao a
    tem: e um ProgrammingError, alto, e nao um descritor a mais.
    """

    def __exit__(self, tipo, valor, rasto):
        try:
            return super().__exit__(tipo, valor, rasto)
        finally:
            self.close()


_BASE_PROTEGIDA = set()


def liga():
    if DB not in _BASE_PROTEGIDA and os.path.exists(DB):
        _BASE_PROTEGIDA.add(DB)
        so_o_dono(DB)
    c = sqlite3.connect(DB, timeout=30, factory=Ligacao)
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


# As seis colunas do quadro viveram aqui, com a tabela `fases`, os
# papeis e o semeador que as punha numa base por estrear. Sairam a
# 15/09/2026 (etapa 2 do docs/historico/CRM.md): o vocabulario da casa
# sao as oito palavras de ESTADOS_DA_CASA, escritas no codigo, e uma
# tabela de fases renomeaveis por cima disso fazia o quadro dizer uma
# palavra e as abas outra para o mesmo estado. As chaves das seis
# primeiras palavras sao, de proposito, as que `fases.papel` usava.
# Estao no historico do git, com o `atribuir_papeis()` que reconhecia
# "Relatorio Preleminar" escrito assim na base dele.


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
                    "Falta de CV's", "Não faz parte da oferta")
MOTIVOS_PERDA = ("Preço", "CV's", "Proposta técnica", "Certificações")

# O que a casa decide sobre cada concurso, de ambito fechado como os
# motivos: "consulting" ou "turnkey", e sim/nao para o CV e a proposta
# tecnica. Vieram da tabela que o Afonso mandou a 14/09/2026 e ficaram
# quando ela se fundiu na escada.
TIPOLOGIAS = ("consulting", "turnkey")
SIM_NAO = ("sim", "não")


# ------------------------------------------------- a escada da casa (CRM)
#
# O vocabulario da casa, decidido pelo Afonso a 15/09/2026 (D1 do
# docs/historico/CRM.md): oito palavras, e mais nenhuma. O Excel e o Zoho
# traduzem-se para esta lista.
#
# As CHAVES das seis primeiras sao, de proposito, as mesmas que
# `fases.papel` ja usava (FASES_DE_ORIGEM): assim a passagem de um
# cartao do quadro para uma proposta e por igualdade de chave, sem mapa
# de traducao nenhum a adivinhar. As duas ultimas ("nao_fomos",
# "cancelado") nunca foram colunas do quadro -- o "nao fomos" e o
# `estado='descartado'` de hoje, com nome novo e os mesmos motivos.
ESTADOS_DA_CASA = (("analisar", "Por analisar"),
                   ("proposta", "A preparar proposta"),
                   ("submetido", "Submetido"),
                   ("relatorio", "Relatório preliminar"),
                   ("ganho", "Ganho"),
                   ("perdido", "Perdido"),
                   ("nao_fomos", "Não fomos"),
                   ("cancelado", "Cancelado"))

# Onde a proposta ainda se mexe, e onde ja parou. Uma proposta que entra
# num estado fechado grava `fechada_em` -- e e isso, e nao a coluna onde
# o cartao parou, que faz o funil esvaziar (§1.2 do plano: ate
# 15/09/2026 um Ganho ficava `interessa` para sempre).
ESTADOS_FECHADOS = ("ganho", "perdido", "nao_fomos", "cancelado")
ESTADOS_ABERTOS = tuple(ch for ch, _ in ESTADOS_DA_CASA
                        if ch not in ESTADOS_FECHADOS)

# As duas ranhuras das PONTAS, que nao sao estados da casa nenhum: o
# antes (ninguem olhou ainda) e o fora (o prazo passou e ninguem olhou).
# Nao ha proposta nenhuma nelas -- sao recorte de leitura sobre os
# anuncios, como as abas de hoje.
#
# Porque e que tem de existir, e nao chegavam as oito: a 15/09/2026 as
# abas diziam "Por ver 1 263 · Abandonados 198 305", e os 198 305 eram
# TODOS anuncios expirados sem ninguem olhar -- zero descartes na base.
# Sem a entrada, os 1 263 vivos caiam em "Por analisar" e o funil
# deixava de dizer o que diz; sem o cemiterio, 198 mil anuncios que
# ninguem viu contavam como decisao da casa.
ENTRADA_DA_ESCADA = ("porver", "Por ver")
CEMITERIO_DA_ESCADA = ("expirou", "Expirou sem ver")

# A escada inteira, pela ordem em que se sobe. E esta a ordem das abas.
ESCADA = (ENTRADA_DA_ESCADA,) + ESTADOS_DA_CASA + (CEMITERIO_DA_ESCADA,)

ROTULOS_DA_ESCADA = dict(ESCADA)
CHAVES_DA_CASA = tuple(ch for ch, _ in ESTADOS_DA_CASA)

# Como se pergunta o motivo, por estado. Era a lista do que cada coluna
# do quadro anunciava no cabecalho ("pede o preco proposto"); com o
# quadro fora (15/09/2026) nao ha cabecalho de coluna nenhum, e o que
# resta e o rotulo do campo do motivo na ficha -- que so os dois estados
# com motivo tem. As entradas do "submetido" e do "relatorio" sairam por
# nao terem quem as lesse: um rotulo que ninguem mostra e uma promessa
# que se esquece de cumprir.
#
# A regra que elas guardavam continua, e esta no `_campos_que_a_ranhura_pede()`:
# um campo pertence a um estado e a mais nenhum. Perguntar o lugar a uma
# proposta "por analisar" e ruido, e perguntar o preco proposto antes de
# haver proposta e perguntar por adivinhas.
PEDIDO_DO_ESTADO = {"perdido": "porque se perdeu",
                    "nao_fomos": "porque não se foi"}

# A partir do "Submetido" o numero que conta e o que se propos, nao o
# preco base (decisao de 01/09/2026, que se mantem). Vale para o cartao
# e para a soma da coluna.
ESTADOS_COM_PROPOSTO = ("submetido", "relatorio", "ganho", "perdido")

# Que lista de motivos cada estado usa. Os dois sao de ambito FECHADO
# (decisao de 01/09/2026): texto livre da, ao fim de um mes, cinquenta
# maneiras de escrever "preco" e nenhuma conta que se possa fazer.
MOTIVOS_DO_ESTADO = {"perdido": MOTIVOS_PERDA, "nao_fomos": MOTIVOS_ABANDONO}


def estado_da_casa(chave):
    """O rotulo de um estado, ou "" se a chave nao e de estado nenhum.

    Pura: e por aqui que se valida o que vem de um formulario, e devolver
    "" (em vez de rebentar) e o que deixa a rota responder com aviso."""
    return ROTULOS_DA_ESCADA.get(chave or "", "")


# As colunas de CRM que viviam no `anuncios` sairam a 15/09/2026 (etapa
# 2 do docs/historico/CRM.md): o que a casa decide mora agora na
# `propostas`. A `fases` sai com elas -- as oito palavras da casa sao
# vocabulario do codigo (ESTADOS_DA_CASA), e uma tabela de fases
# renomeaveis por cima disso fazia o quadro dizer uma palavra e as abas
# outra para o mesmo estado.
#
# Sem espelho nem periodo de convivencia porque nao ha o que proteger: a
# base estava no estado zero quando isto se fez, e a aplicacao em teste.
# O que uma base com dados teria de fazer, se alguma vez isto correr num
# disco onde alguem triou: ler as colunas ANTES de as largar e criar uma
# proposta por cada anuncio que tenha fase ou qualquer campo preenchido.
# As colunas que a escada substituiu. Numa base NOVA nao se criam; numa
# que ja as tenha, **ficam onde estao** -- e a lista existe para se saber
# quais sao e para o teste provar que nenhuma e lida.
#
# Porque e que nao se apagam, que era o que este ficheiro dizia primeiro:
# o `ALTER TABLE ... DROP COLUMN` do SQLite **reescreve a tabela
# inteira**, uma vez por coluna. Medido a 15/09/2026 na base dele (209
# 894 anuncios, 1,2 GB, com o `anuncios.texto` a valer 843 MB desses):
# doze colunas sao doze reescritas de 1,2 GB, e ao fim de 45 s a primeira
# ainda nao tinha acabado com o WAL ja acima do tamanho da propria base.
# Num arranque do `radar-painel.service` isso le-se como o painel
# pendurado; e uma migracao que pode ficar sem disco a meio deixa a base
# num estado que ninguem planeou.
#
# O que se ganhava era cosmetica: doze colunas a NULL em cada linha, que
# codigo nenhum le. O que se perdia era o arranque. Ficam.
COLUNAS_QUE_SAIRAM = ("fase_id", "motivo", "preco_proposto", "posicao",
                      "top3", "motivo_perda", "tipologia", "cv",
                      "proposta_tecnica", "notas", "coe", "responsavel")


def largar_o_que_a_escada_substituiu(c):
    """Tira a tabela `fases`, que a escada substituiu. Idempotente.

    Sao seis linhas: sai num instante, ao contrario das colunas (ver o
    comentario em COLUNAS_QUE_SAIRAM). E tem de sair mesmo, e nao so de
    deixar de se criar: enquanto existisse, um restauro de um
    `triagem.jsonl` antigo voltava a enche-la e ficava um vocabulario
    de fases ao lado do da casa, sem nada a dizer qual manda.
    """
    try:
        c.execute("DROP TABLE IF EXISTS fases")
    except sqlite3.OperationalError:
        pass


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
        # (As migracoes de uso unico do saneamento de 30/08/2026 -- A1,
        # A2, A3 e a limpeza do indice pecas_fts -- sairam a 14/09/2026:
        # correram em todas as instalacoes desde a v1.0.0, e uma base
        # de antes disso ja nao existe. O diario de Agosto guarda-as.)
        # As propostas: o que a CASA esta a fazer, que nao e o mesmo que o
        # estado de um anuncio (etapa 1 do docs/historico/CRM.md,
        # 15/09/2026). Existe por duas razoes que o estado do anuncio nao
        # consegue ser, ambas decididas pelo Afonso nesse dia:
        #
        #   D2 -- uma consulta previa, um ajuste directo ou um convite
        #   nao tem anuncio no DR. `ref` a NULL e um caso legitimo, e nao
        #   um orfao: o `porque_sem_ref` diz porque.
        #   D3 -- um concurso de tres lotes pode acabar com o L1 ganho e
        #   o L2 perdido. Um anuncio, uma linha e um estado nao cabem
        #   dois resultados. `lote`: >=1 um lote, 0 o conjunto, NULL um
        #   anuncio sem lotes.
        #
        # E o Portal BASE adjudica POR LOTE -- sem esta granularidade a
        # etapa 4 (o desvio real face a quem ganhou) nao tem comparacao
        # que fazer.
        c.execute("""CREATE TABLE IF NOT EXISTS propostas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref TEXT, porque_sem_ref TEXT, lote INTEGER,
            entidade TEXT DEFAULT '', titulo TEXT DEFAULT '',
            estado TEXT DEFAULT 'analisar', motivo TEXT,
            responsavel TEXT, tipologia TEXT, coe TEXT,
            preco_base TEXT, valor_proposta TEXT, ebitda REAL,
            lugar INTEGER, top3 TEXT, cv TEXT, proposta_tecnica TEXT,
            notas TEXT, criada_em TEXT, fechada_em TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_propostas_ref ON propostas(ref)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_propostas_estado "
                  "ON propostas(estado)")
        # Uma proposta por (anuncio, lote): sem isto, dois cliques no
        # "preparar proposta" faziam duas linhas para o mesmo lote e o
        # funil passava a contar o negocio duas vezes. As propostas sem
        # anuncio (ref NULL) escapam ao indice por definicao do SQL -- em
        # UNIQUE, dois NULL nao sao iguais -- e e o que se quer: duas
        # consultas previas distintas nao colidem uma com a outra.
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_propostas_ref_lote "
                  "ON propostas(ref, COALESCE(lote, -1))")
        # As tarefas (etapa 3 do plano; a tabela nasce aqui para a
        # exportacao do B15 nao ter de mudar duas vezes). `ref` sozinho,
        # sem proposta, serve o que ainda nao virou negocio.
        c.execute("""CREATE TABLE IF NOT EXISTS tarefas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposta_id INTEGER, ref TEXT, o_que TEXT,
            quando TEXT, quem TEXT, feita_em TEXT,
            origem TEXT DEFAULT 'mão', criada_em TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_tarefas_quando "
                  "ON tarefas(quando)")
        # Os contactos (etapa 6): sao da ENTIDADE e nao do concurso -- a
        # pessoa que responde aos esclarecimentos do IPL responde aos do
        # ano que vem tambem. A chave e o NIF quando se sabe, senao o
        # nome normalizado, que e a mesma que a ficha da entidade usa.
        c.execute("""CREATE TABLE IF NOT EXISTS contactos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entidade_chave TEXT, entidade TEXT, nome TEXT, papel TEXT,
            email TEXT, telefone TEXT, notas TEXT, criado_em TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_contactos_chave "
                  "ON contactos(entidade_chave)")
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
        # 13/09/2026: os filtros guardados sem alerta deixaram de ter
        # ecra (decisao do Afonso: apagam-se, nao se convertem). Uma vez,
        # por marca -- desligar um alerta depois disto deixa-o na tabela
        # com alerta=0, e nao pode ser apagado no arranque seguinte.
        if not c.execute("SELECT 1 FROM estado "
                         "WHERE chave='filtros_sem_alerta_apagados'").fetchone():
            c.execute("DELETE FROM alertas_vistos WHERE filtro_id IN "
                      "(SELECT id FROM filtros_guardados "
                      " WHERE COALESCE(alerta,0)=0)")
            c.execute("DELETE FROM filtros_guardados WHERE COALESCE(alerta,0)=0")
            c.execute("INSERT OR REPLACE INTO estado "
                      "VALUES ('filtros_sem_alerta_apagados','1')")
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
        for nome, tipo in (("texto", "TEXT"),
                           ("pdf_url", "TEXT"), ("link_pecas", "TEXT"),
                           ("docs_estado", "TEXT"),
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
                           # (o motivo, o preco proposto, o lugar, os
                           # tres primeiros e o motivo da perda sairam
                           # daqui a 15/09/2026: sao da proposta)
                           # A republicacao: `altera` e o ref que o texto
                           # deste anuncio declara alterar (NULL = texto
                           # ainda nao lido com esta regra; '' = nao e
                           # alteracao); `alterado_por` fica no ORIGINAL
                           # e aponta para a alteracao mais recente, cujo
                           # prazo e preco sao os que estao em vigor.
                           ("altera", "TEXT"), ("alterado_por", "TEXT"),
                           # os lotes declarados no anuncio, em JSON
                           # (lotes_do_texto); '' quando nao ha
                           ("lotes", "TEXT"),
                           # quando se viu pela ultima vez a lista das
                           # pecas na plataforma (vigiar_pecas, 14/09/2026)
                           ("pecas_vigiadas_em", "TEXT")):
                           # (a tipologia, o CV, a proposta tecnica, as
                           # notas e o CoE viveram aqui um dia -- 14 a
                           # 15/09/2026 -- e sao da proposta, como as
                           # outras sete de COLUNAS_QUE_SAIRAM)
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
        # Pelo mesmo motivo, e pela mesma razao que o `ix_ctr_desconto`:
        # a tabela `anuncios` e larga -- o `texto` do anuncio sozinho sao
        # 377 dos 438 MB dela --, e QUALQUER varrimento arrasta o texto
        # todo do disco. Enquanto so 9% tinham detalhe lido isso nao se
        # via; quando o `--detalhes tudo` acabou (04/09/2026, 66 404 de
        # 66 498) a pagina inicial passou a fazer nove varrimentos de
        # 440 MB, e numa pen a 42 MB/s a frio isso nao e um pormenor.
        # Estes tres cobrem as consultas todas da lista, do calendario e
        # dos indicadores: medido numa copia, 0,74 s de SQL para 0,02 s.
        #
        # `_lista`: o `ORDER BY data_pub DESC, ref DESC` da primeira
        # pagina -- com a ordem no indice nao ha B-tree temporaria
        # (0,116 s para 0,001 s).
        c.execute("CREATE INDEX IF NOT EXISTS ix_anuncios_lista "
                  "ON anuncios(estado, data_pub DESC, ref DESC)")
        # `_triagem`: as contagens das abas e das etiquetas, que sao
        # sempre `estado` + prazo/data_pub + detalhe_lido + plataforma.
        # As cinco colunas estao ca para o indice COBRIR a consulta: uma
        # que falte manda o SQLite a tabela buscar a linha inteira.
        c.execute("CREATE INDEX IF NOT EXISTS ix_anuncios_triagem "
                  "ON anuncios(estado, prazo, data_pub, detalhe_lido, "
                  "plataforma)")
        # `_detalhe`: o "quantos faltam ler", que nao filtra por estado
        # nenhum.
        c.execute("CREATE INDEX IF NOT EXISTS ix_anuncios_detalhe "
                  "ON anuncios(detalhe_lido, plataforma)")
        # `_acervo`: o mapa das plataformas da lista. Era o `_detalhe` a
        # servi-lo, e a 05/09/2026 deixou de chegar -- **o comentario
        # dizia "nao filtram por estado nenhum" e a consulta passou a
        # filtrar**, com `estado != 'alteracao'` e o recorte por cima.
        # Faltando duas colunas ao indice, o SQLite ia a tabela buscar
        # cada linha: com 66 mil anuncios passava despercebido, com
        # 209 177 e uma tabela de 843 MB sao 0,45 s numa pagina.
        # Medido numa copia: **0,446 s -> 0,037 s**, e o indice
        # constroi-se em 1 s e nao acrescenta nada de medivel ao
        # ficheiro. A licao esta na armadilha: um indice de cobertura
        # so cobre a consulta para que foi feito, e uma coluna nova no
        # WHERE desfa-lo em silencio.
        c.execute("CREATE INDEX IF NOT EXISTS ix_anuncios_acervo "
                  "ON anuncios(detalhe_lido, estado, plataforma, cpv)")
        # O `SELECT DISTINCT plataforma` da caixa dos alertas, e o
        # `GROUP BY substr(cpv,1,2)` dos indicadores.
        c.execute("CREATE INDEX IF NOT EXISTS ix_anuncios_plataforma "
                  "ON anuncios(plataforma)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_anuncios_estado_cpv "
                  "ON anuncios(estado, cpv)")
        largar_o_que_a_escada_substituiu(c)
        traduzir_filtros_guardados(c)
        casa.iniciar_tabelas(c)     # o registo da casa (Excel; um dia o Zoho)
        contas.iniciar_tabelas(c)   # utilizadores, sessoes, o trinco do login
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


def so_o_dono(caminho):
    """Deixa o ficheiro legivel so pelo dono (0600). E para o que tem
    segredos -- a base (hashes, sessoes, a triagem), as capturas (os
    cookies do DR), as chaves e a palavra-passe do e-mail -- que estavam
    a 644 e 755 (auditoria de 14/09/2026)."""
    try:
        os.chmod(caminho, 0o600)
    except OSError:
        pass


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


def limpa_erro(chave):
    """Apaga a marca de "ultimo erro" quando a coisa volta a correr bem.

    Sem isto a marca so cresce: escrevia-se na falha e nunca mais saia
    do ecra. A 04/09/2026 o painel mostrava um `git push` recusado a
    31/08 -- depois de dezenas de pushes bem sucedidos, incluindo o
    dessa manha -- e uma leitura falhada do 22005/2026 das 11:20, que
    tinha corrido bem as 12:45 do MESMO dia. Um erro que ja nao existe
    lido como "o ultimo erro" e pior do que erro nenhum: manda procurar
    uma avaria que ja nao ha.

    A historia NAO se perde: a serie fica na tabela `erros` (C3), que e
    exactamente o sitio para onde ela foi mandada. A marca responde a
    "esta alguma coisa avariada agora?"; a serie a "o que e que ja
    correu mal?".

    DUAS marcas nao se limpam, de proposito. O relogio (`relogio()`)
    passa a cada 60 s e quase sempre nao faz nada: limpar no sucesso
    apagava a marca um minuto depois da avaria, e ninguem chegava a
    ve-la. E a expiracao do token nao e um erro, e uma data -- diz
    quando a captura deixou de servir, e isso continua a ser verdade
    depois de renovada.
    """
    try:
        with liga() as c:
            c.execute("DELETE FROM estado WHERE chave=?", (chave,))
    except sqlite3.Error:
        pass                            # limpar nunca pode derrubar o sucesso


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


# ------------------------------------------------------------- comum
#
# Utilidades puras: formatar, validar e contar. Nao tocam na base, nao
# escrevem HTML e nao dependem de nada a frente -- so o `dias_urgente()`
# le o config, que e da banda `base`, acima.
#
# Vieram para aqui a 03/09/2026. Estavam espalhadas pelo painel, pela
# ficha do anuncio e pelo quadro, e eram chamadas de fora dessas bandas:
# o `data_pt()` por seis funcoes de quatro bandas, o `dias_restantes()`
# a viver no quadro e a ser usado pelo resumo por e-mail. Medido no
# grafo de chamadas: era o que fechava tres dos seis ciclos entre as
# fatias do ficheiro -- as fontes, o mercado e a rotina estavam presas
# ao painel por causa de formatadores, e nao por causa de painel.


def simplifica(texto):
    """Sem acentos e em minusculas, para comparar sem surpresas."""
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


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


def conta_dias(dias):
    """'hoje', 'amanhã', '1 dia', 'N dias' -- com concordancia."""
    if dias <= 0:
        return "termina hoje"
    if dias == 1:
        return "amanhã"
    return "%d dias" % dias


def duracao_pt(segundos):
    """10 -> '10s', 90 -> '2 min', 5400 -> '1h30', 61200 -> '17h'. Para
    dizer quanto falta numa recolha longa.

    Abaixo do minuto conta em segundos, e nao arredondado a '1 min':
    numa corrida que comeca por ler cinco anuncios em dez segundos, o
    '1 min decorridos' punha em duvida tudo o resto que a linha diz.
    Acima disso arredonda os minutos PARA CIMA, pela razao simetrica --
    'faltam 0 min' com meio minuto a faltar le-se como se tivesse
    acabado."""
    segundos = max(0, int(segundos or 0))
    if segundos < 60:
        return "%ds" % segundos
    minutos = -(-segundos // 60)          # para cima
    if minutos < 60:
        return "%d min" % minutos
    horas, resto = divmod(minutos, 60)
    return "%dh" % horas if not resto else "%dh%02d" % (horas, resto)


def etiqueta_prazo(prazo, urgente=None):
    """(texto, classe) para o distintivo de prazo. Verde folgado, amarelo
    dentro da janela do urgente, vermelho expirado ou a acabar hoje.

    O `urgente` e essa janela em dias; sem ele le-se de dias_urgente().
    Esteve aqui um 7 escrito a mao com o filtro a 10: um prazo a 9 dias
    saia verde ("folgado") na lista e na ficha e contava como urgente no
    filtro, no cartao dos indicadores e nos avisos -- o ecra a mostrar um
    numero que a ligacao dele nao dava. A janela e UMA so, e vem daqui.

    Quem chama em ciclo (a lista, o calendario) le a janela uma
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


def data_do_texto(escrito):
    """'21/08/2026' -> '2026-08-21'. O inverso do `data_pt()`.

    Guarda-se ISO porque ordena como texto; escreve-se a portuguesa
    porque e assim que se le -- e ate 15/09/2026 so METADE disso estava
    feita: o painel mostrava sempre dd/mm/aaaa e a unica caixa que pedia
    uma data era um `<input type=date>`, que cada browser desenha na
    lingua DELE. Num Chrome em ingles saia "mm/dd/yyyy" no meio de uma
    aplicacao inteira em portugues. Palavra dele: "a data deve ser
    sempre dd/mm/aaaa".

    Aceita 1 ou 2 digitos no dia e no mes ("1/9/2026"), e devolve ""
    para o que nao se perceba -- que e o que faz uma data mal escrita
    ficar por preencher em vez de ir para a base como lixo. E aceita ISO
    tal e qual, para quem colar de outro sitio.
    """
    escrito = (escrito or "").strip()
    if not escrito:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", escrito):
        return escrito
    m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", escrito)
    if not m:
        return ""
    dia, mes, ano = (int(x) for x in m.groups())
    try:
        return datetime(ano, mes, dia).strftime("%Y-%m-%d")
    except ValueError:
        return ""


def data_de_filtro(valor):
    """So aceita AAAA-MM-DD; o resto ignora-se em vez de filtrar.

    Um "de=lixo" vindo de um URL guardado comparava datas com texto e
    esvaziava a lista em silencio -- enquanto o euro minimo com lixo era
    ignorado. Dois silencios com efeitos opostos; agora e um so, e a
    lista avisa (avisos_de_datas)."""
    valor = (valor or "").strip()
    return valor if re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor) else ""


def mil_pt(n, espaco=" "):
    """65869 -> '65 869'. A portuguesa, e com espaco inquebravel: com
    um espaco normal, o browser parte "1 363 300" ao fim da linha e a
    leitura fica com um numero em cada linha.

    Passa-se `espaco=" "` para a CONSOLA, onde o inquebravel nao faz
    falta e numa consola sem UTF-8 sai como lixo ("60?215")."""
    return "{:,}".format(int(n)).replace(",", espaco)


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


def para_like(termo):
    """Escapa os caracteres especiais do LIKE. Sem isto, procurar "50%"
    devolvia tudo o que tem "50", e "CP_2026" tratava o _ como coringa."""
    for ch in (ESCAPE_LIKE, "%", "_"):
        termo = termo.replace(ch, ESCAPE_LIKE + ch)
    return termo


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



def frag_de_texto(texto, coluna, norma=simplifica):
    """(fragmento, valores) da procura por palavras: varias separadas
    por |, qualquer uma serve.

    **Nao toca em lista nenhuma** -- quem chama decide onde o fragmento
    entra, que e o que deixa o `op=ou` junta-lo ao do CPV sem baralhar a
    ordem dos placeholders (ha um teste que conta os `?`).

    Procura-se sempre na coluna normalizada e com o termo normalizado
    pela MESMA norma: o LIKE do SQLite so baixa maiusculas de letras
    ASCII, e para ele "C" com cedilha nao e "c" com cedilha. Medido
    duas vezes, e as duas custou ~11% dos resultados sem aviso nenhum:
    nos anuncios (9 383 titulos escritos todos em maiusculas) e nos
    contratos (68 295, 11,8%, porque o IMPIC escreve muito em
    maiusculas). A `norma` e argumento porque nao e a mesma nas duas
    populacoes: `simplifica` para titulos e objectos, `norma_entidade`
    para nomes de entidade -- e essa troca "&" por " e ".

    Estava escrita duas vezes, uma em cada condicoes(); veio para aqui
    a 03/09/2026. As duas listas continuam a ser dois motores, de
    proposito -- o que se partilha e so esta traducao.
    """
    pedacos = [p.strip() for p in (texto or "").split("|") if p.strip()]
    if not pedacos:
        return "", []
    ors, vals = [], []
    for p in pedacos:
        ors.append("%s LIKE ? ESCAPE '%s'" % (coluna, ESCAPE_LIKE))
        vals.append("%" + para_like(norma(p)) + "%")
    return "(" + " OR ".join(ors) + ")", vals


def frag_de_exclusao(texto, coluna, norma=simplifica):
    """A frag_de_texto() invertida: o que corresponder fica de fora.

    O COALESCE nao e decorativo: `NOT (NULL LIKE x)` e NULL, e a linha
    com a coluna por preencher desaparecia da lista -- excluir "obras"
    nao pode esconder um anuncio que ainda nem titulo tem.
    """
    pedacos = [p.strip() for p in (texto or "").split("|") if p.strip()]
    if not pedacos:
        return "", []
    ors, vals = [], []
    for p in pedacos:
        ors.append("COALESCE(%s,'') LIKE ? ESCAPE '%s'" % (coluna, ESCAPE_LIKE))
        vals.append("%" + para_like(norma(p)) + "%")
    return "NOT (" + " OR ".join(ors) + ")", vals


def aparelho_do_agente(agente):
    """O nome do aparelho por tras de um User-Agent: "iPhone", "Android",
    "Windows", "Mac", "Linux", ou "outro aparelho". E o que a lista das
    sessoes mostra (13/09/2026): "Mozilla/5.0 (iPhone; CPU iPhone OS
    18_7 like Mac OS X) AppleWebKit/605" nao diz nada a ninguem. A ordem
    importa: um iPad diz "like Mac OS X", um Android diz "Linux"."""
    a = (agente or "").lower()
    for marca, nome in (("iphone", "iPhone"), ("ipad", "iPad"),
                        ("android", "Android"), ("windows", "Windows"),
                        ("mac os", "Mac"), ("macintosh", "Mac"),
                        ("linux", "Linux")):
        if marca in a:
            return nome
    return "outro aparelho"


# -------------------------------------------------------------- pessoas
#
# Ate 8/09/2026 nao havia palavra-passe: o nome vinha de um cookie
# `quem` que se escrevia num campo da barra lateral. Com o radar a sair
# do PC (docs/historico/ONLINE.md, etapa 1) passou a haver conta e
# sessao -- as tabelas e a criptografia estao no contas.py; o que e do
# pedido HTTP (o cookie `sessao`, o `before_request`, o /entrar) esta na
# banda do painel, em "a porta". A tabela `pessoas` fica como esta: e a
# lista de nomes para o "responsavel", que pode ser um colega sem conta.

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
    """O nome de quem esta a usar a aplicacao, posto em `g` pela porta
    (porta_de_entrada()). Vazio fora de um pedido, ou no acesso livre
    local antes de haver conta -- e valido, nada bloqueia por isso."""
    if not has_request_context():
        return ""
    return ((g.get("utilizador") or {}).get("nome") or "").strip()


def registar(ref, accao, detalhe="", quem=None):
    """O `quem` explicito serve o trabalho em fundo: fora de um pedido do
    browser nao ha cookie nenhum para ler, e quem_sou() rebentava."""
    with liga() as c:
        c.execute("""INSERT INTO historico (ref,quem,accao,detalhe,quando)
                     VALUES (?,?,?,?,?)""",
                  (ref, quem or quem_sou() or "(sem nome)", accao, detalhe,
                   datetime.now().strftime("%Y-%m-%d %H:%M")))


# ------------------------------------------------------------- lotes
#
# Era a banda do quadro, que saiu a 15/09/2026. O que fica é o que os
# lotes obrigam -- a cor das etiquetas e o resumo de a que lotes se foi,
# que a ficha mostra -- e continua antes das propostas porque é delas
# que a escada precisa.

CORES_ETIQUETA = ("#c0392b", "#d68910", "#1e8449", "#1f4e79",
                   "#6c3483", "#616a6b")


# Os lotes (decisao do Afonso a 02/09/2026, desenhada a 08/09/2026): "nos
# anuncios diz se tem lotes; um cartao por anuncio, mas os cartoes que
# tem lotes devem identificar a que lotes fomos e se fomos a todos, e no
# final, perdido ou ganho, separam-se os cartoes". O anuncio traz os
# lotes (`anuncios.lotes`, lidos por lotes_do_texto()); a que lotes se
# foi, e com que resultado, so o registo da casa sabe (`casa.lote`:
# >= 1 e um lote, 0 e o conjunto, NULL e por identificar).
ESTADO_DO_LOTE = {"ganho": ("ganho", "ok"), "perdido": ("perdido", "mau"),
                  "submetido": ("submetido", "info"),
                  "nao fomos": ("não fomos", "")}


def lotes_de(a):
    """A lista de lotes de um anuncio, da coluna JSON. Vazia se nao tem."""
    try:
        return json.loads(_valor(a, "lotes") or "[]") or []
    except ValueError:
        return []


def resumo_dos_lotes(lotes, linhas_casa=()):
    """O que se sabe de cada lote, juntando o anuncio ao registo da casa.

    Devolve {"lotes": [{n, id, descricao, preco_base, estado, rotulo,
    classe, proposta, lugar}], "fomos": [n, ...], "conjunto": linha ou
    None, "por_estado": {estado: [n, ...]}} -- ou None se o anuncio nao
    tem lotes. Puro: nao le a base, para se poder testar com o caso
    real do 1947/2026 (tres lotes, L1 perdido, L2 ganho, L3 perdido).
    """
    if not lotes:
        return None
    por_n = {}
    conjunto = None
    for linha in linhas_casa or ():
        lote = linha.get("lote")
        if lote == 0:
            conjunto = linha
        elif lote:
            por_n.setdefault(int(lote), linha)
    saida, fomos, por_estado = [], [], {}
    for l in lotes:
        n = int(l.get("n") or 0)
        linha = por_n.get(n)
        estado = casa.estado_do_lote(linha) if linha else ""
        rotulo, classe = ESTADO_DO_LOTE.get(estado, ("", ""))
        if linha:
            fomos.append(n)
            if estado:
                por_estado.setdefault(estado, []).append(n)
        saida.append({"n": n, "id": l.get("id") or "", "descricao": l.get("descricao") or "",
                      "preco_base": l.get("preco_base") or "",
                      "estado": estado, "rotulo": rotulo, "classe": classe,
                      "proposta": (linha or {}).get("valor_proposta"),
                      "lugar": (linha or {}).get("lugar")})
    return {"lotes": saida, "fomos": fomos, "conjunto": conjunto,
            "por_estado": por_estado}


def frase_dos_lotes(resumo):
    """A frase curta: "fomos a 3 dos 8 lotes", "fomos ao conjunto dos 2
    lotes", "8 lotes; sem registo de a que fomos"."""
    if not resumo:
        return ""
    total = len(resumo["lotes"])
    if resumo["fomos"]:
        if total == 1:
            return "fomos ao único lote"
        if len(resumo["fomos"]) == total:
            return "fomos a todos os %d lotes" % total
        return "fomos a %d dos %d lotes" % (len(resumo["fomos"]), total)
    if resumo["conjunto"]:
        return "fomos ao conjunto dos %d lotes" % total
    return "%d lote%s; sem registo de a que fomos" % (total, "" if total == 1 else "s")


# ------------------------------------------------------------ propostas
#
# O que a casa esta a fazer com cada concurso. Etapa 1 do
# docs/historico/CRM.md -- le o §3 antes de mexer aqui.
#
# A regra que manda: **a escada e o estado da PROPOSTA, nao do anuncio**.
# O anuncio guarda o que o DR publicou, que e facto e nao muda; a
# proposta guarda o que a casa decidiu, que muda todos os dias. Ate
# 15/09/2026 as duas coisas viviam na mesma linha (doze colunas
# penduradas em `anuncios`), e era isso que fazia o "Em curso" e a aba
# "interessados" serem a mesma consulta.


def preco_base_do_lote(a, lote):
    """O preco base que pertence a esta proposta: o do LOTE quando ela e
    de um lote, o do procedimento quando e do conjunto ou nao ha lotes.

    A proposta do lote 2 mostrava os 212 400 EUR do procedimento inteiro
    (visto no ecra a 15/09/2026, na etapa 2): o numero do anuncio posto
    numa linha que representa uma parte dele. E a mentira mais cara que
    esta tabela pode contar -- e dela que sai o desvio face ao proposto,
    e e com ela que a etapa 4 ha-de comparar o que o Portal BASE
    adjudicou, que tambem e por lote.

    Sem preco do lote lido, fica VAZIO -- nao o do procedimento. Um
    campo em branco pergunta-se; um numero errado acredita-se.
    """
    if not lote:                      # None (sem lotes) ou 0 (o conjunto)
        return _valor(a, "preco_base") or ""
    for l in lotes_de(a):
        if int(l.get("n") or 0) == int(lote):
            return l.get("preco_base") or ""
    return ""


def proposta(id_):
    with liga() as c:
        return c.execute("SELECT * FROM propostas WHERE id=?", (id_,)).fetchone()


def propostas_de(ref):
    """As propostas de um anuncio, por lote. Lista vazia e resposta
    valida: quer dizer que a casa ainda nao decidiu nada sobre ele."""
    if not ref:
        return []
    with liga() as c:
        return c.execute("SELECT * FROM propostas WHERE ref=? "
                         "ORDER BY COALESCE(lote, 0), id", (ref,)).fetchall()


def criar_proposta(ref=None, lote=None, entidade="", titulo="",
                   porque_sem_ref="", estado="analisar", quem=None):
    """Poe um concurso na escada, e devolve o id.

    **Idempotente por (ref, lote)**: chamar duas vezes devolve a mesma
    proposta em vez de fazer uma segunda. Sem isto, dois cliques no
    "preparar proposta" -- ou um duplo clique, que e o caso normal --
    punham o mesmo negocio duas vezes no funil e a soma da coluna
    passava a mentir. As propostas sem `ref` (D2) nao se podem comparar
    assim e criam-se sempre: duas consultas previas distintas nao sao a
    mesma coisa so por nenhuma ter anuncio.

    Do anuncio copia-se o que a proposta precisa de ter por si (entidade,
    titulo, preco base): uma proposta sem `ref` tem de os trazer, e uma
    com `ref` nao pode ficar dependente de um JOIN para se mostrar numa
    lista de mil linhas.
    """
    if estado not in CHAVES_DA_CASA:
        estado = "analisar"
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    preco_base = ""
    with liga() as c:
        if ref:
            ja = c.execute("SELECT id FROM propostas WHERE ref=? AND "
                           "COALESCE(lote,-1)=COALESCE(?,-1)",
                           (ref, lote)).fetchone()
            if ja:
                return ja["id"]
            a = c.execute("SELECT titulo, entidade, preco_base, lotes "
                          "FROM anuncios WHERE ref=?", (ref,)).fetchone()
            if a:
                entidade = entidade or (a["entidade"] or "")
                titulo = titulo or (a["titulo"] or "")
                preco_base = preco_base_do_lote(a, lote)
        # Nascer JA numa ranhura fechada leva carimbo: sem ele a proposta
        # some-se do quadro, porque as quatro colunas do fim mostram o
        # trimestre e um `fechada_em` vazio nunca cabe nele. Acontece
        # sempre que o registo da casa importa um concurso antigo -- que
        # e, por D4, para que serve o Excel.
        fechada = agora if estado in ESTADOS_FECHADOS else None
        cur = c.execute(
            "INSERT INTO propostas (ref, porque_sem_ref, lote, entidade, "
            "titulo, estado, preco_base, criada_em, fechada_em) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (ref or None, porque_sem_ref or None, lote, entidade, titulo,
             estado, preco_base, agora, fechada))
        id_ = cur.lastrowid
    registar(ref or "", "proposta criada",
             "%s%s" % (estado_da_casa(estado),
                       " — lote %d" % lote if lote else ""), quem)
    # as datas do DR viram tarefas na hora, e nao so na verificacao
    # seguinte: por um concurso na escada e o momento em que se quer ver
    # o que falta fazer
    if ref:
        sincronizar_tarefas(ref)
    return id_


def mover_proposta(id_, estado, quem=None):
    """Poe a proposta noutra ranhura da escada. Devolve (ok, recado).

    Quem grava o `fechada_em` e esta funcao, e so ela: e o carimbo que
    faz o funil esvaziar, e se ficasse a cargo de quem chama havia de
    faltar num dos caminhos. Voltar a um estado aberto limpa-o -- um
    "Perdido" que se reabre por impugnacao nao pode continuar a contar
    como fechado no trimestre em que se fechou.
    """
    if estado not in CHAVES_DA_CASA:
        return False, "«%s» não é um estado da casa." % (estado or "")
    rotulo = estado_da_casa(estado)
    with liga() as c:
        antes = c.execute("SELECT * FROM propostas WHERE id=?", (id_,)).fetchone()
        if not antes:
            return False, "Essa proposta já não existe."
        if antes["estado"] == estado:
            return True, ""
        fechada = (datetime.now().strftime("%Y-%m-%d %H:%M")
                   if estado in ESTADOS_FECHADOS else None)
        # O motivo pertence ao ESTADO, e sai com ele. Um "Preço base
        # baixo" pendurado numa proposta que voltou ao Submetido é uma
        # mentira à espera de ser lida -- e foi o que a prova de fumo da
        # etapa 2 apanhou. Limpa-se aqui, e nao em quem chama, para
        # valer tambem ao arrastar no quadro; quem move para um estado
        # que PEDE motivo grava-o a seguir.
        # Guarda-se o que ainda faz sentido: as duas listas nao sao a
        # mesma, e "Preço base baixo" (porque nao se foi) nao e resposta
        # a "porque se perdeu".
        motivo = (antes["motivo"]
                  if antes["motivo"] in (MOTIVOS_DO_ESTADO.get(estado) or ())
                  else None)
        c.execute("UPDATE propostas SET estado=?, fechada_em=?, motivo=? "
                  "WHERE id=?", (estado, fechada, motivo, id_))
    registar(antes["ref"] or "", "estado", rotulo, quem)
    # Fechar uma proposta tira as tarefas que ainda lhe restavam: um
    # "entregar a proposta" pendurado num concurso perdido e a mesma
    # mentira que o motivo pendurado, na vista que menos a tolera -- a
    # que existe para dizer o que falta fazer.
    if antes["ref"]:
        sincronizar_tarefas(antes["ref"])
    return True, ""


def traduzir_filtros_guardados(c):
    """Poe o vocabulario da escada nas consultas ja guardadas.

    Um filtro (ou um alerta) guardado antes de 15/09/2026 tem
    "estado=novo" ou "estado=interessa" escrito na consulta. Duas coisas
    partiam-se sem isto, e as duas em silencio: a consulta guardada
    deixava de ser igual a canonica de hoje, e portanto o filtro em uso
    nunca mais se reconhecia a si proprio (o botao de guardar so oferecia
    criar outro com o mesmo nome); e um alerta com "estado=interessa"
    passava a procurar por um valor que a coluna ja nao tem, sem
    encontrar nada e sem nada no ecra a dize-lo.

    Idempotente, como todas as migracoes: corre a cada arranque e nao faz
    nada quando ja esta feito.
    """
    for linha in c.execute("SELECT id, consulta FROM filtros_guardados").fetchall():
        pares = parse_qsl(linha["consulta"] or "", keep_blank_values=True)
        mudou = False
        novos = []
        for chave, valor in pares:
            if chave == "estado" and valor in ABAS_ANTIGAS:
                valor = ABAS_ANTIGAS[valor]
                mudou = True
            novos.append((chave, valor))
        if mudou:
            c.execute("UPDATE filtros_guardados SET consulta=? WHERE id=?",
                      (urlencode(novos), linha["id"]))


def gravar_motivo(id_, motivo):
    """O motivo de uma proposta, ou a limpeza dele."""
    with liga() as c:
        c.execute("UPDATE propostas SET motivo=? WHERE id=?",
                  (motivo or None, id_))


def _tirar_da_escada(ref, antes):
    """Voltar ao "por ver": a proposta sai. Devolve o rotulo do aviso, ou
    None se nao havia nada para tirar.

    So se apaga a proposta que nao tem nada escrito. Uma com preco
    proposto, notas, lugar ou CoE e TRABALHO, e trabalho nao se deita
    fora com um clique de "repor" -- essa volta a "Por analisar", e o
    aviso diz porque, senao o gesto parece nao ter funcionado.
    """
    if not antes:
        return None
    escrito = ("valor_proposta", "notas", "lugar", "top3", "coe", "ebitda")
    if any(antes[campo] for campo in escrito):
        mover_proposta(antes["id"], "analisar")
        return ("reposto em «Por analisar» — tem trabalho escrito, "
                "não se deita fora")
    with liga() as c:
        c.execute("DELETE FROM propostas WHERE id=?", (antes["id"],))
    registar(ref, "estado", "voltou a por ver")
    return "reposto em por ver"


def gravar_campos_da_proposta(id_, campos, valores, quem=None):
    """Grava uma lista de campos de uma proposta, e deixa no historico o
    que MUDOU -- carregar em "gravar" sem tocar em nada nao e um
    acontecimento, e um historico cheio disso e um historico que ninguem
    le. Os nomes dos campos vem de listas fixas do codigo
    (CAMPOS_EDITAVEIS_DA_PROPOSTA), nunca do formulario: interpolar um
    nome de coluna que o browser mandou era deixar o SQL a quem pedisse.
    """
    if not campos:
        return
    seguros = set(COLUNAS_DA_PROPOSTA)
    assert all(nome in seguros for nome in campos), campos
    with liga() as c:
        antes = c.execute("SELECT * FROM propostas WHERE id=?", (id_,)).fetchone()
        if not antes:
            return
        c.execute("UPDATE propostas SET " + ", ".join(n + "=?" for n in campos)
                  + " WHERE id=?", list(valores) + [id_])
    for nome, valor in zip(campos, valores):
        if (antes[nome] or None) != (valor or None):
            registar(antes["ref"] or "", nome, str(valor or "(apagado)"), quem)


def _prazos_das_propostas(c, propostas):
    """Os prazos dos anuncios das propostas, numa consulta so. Um SELECT
    por cartao dentro do ciclo do HTML e o erro que este painel ja pagou
    uma vez."""
    refs = sorted({p["ref"] for p in propostas if p["ref"]})
    if not refs:
        return {}
    return {r["ref"]: r["prazo"] for r in c.execute(
        "SELECT ref, prazo FROM anuncios WHERE ref IN (%s)"
        % ",".join("?" * len(refs)), refs)}


# --- as tarefas (etapa 3 do docs/historico/CRM.md, 15/09/2026)
#
# O quadro responde a "onde e que as coisas estao". Um CRM responde a "o
# que tenho de fazer hoje", e e isso que estas trinta linhas trazem.
#
# Duas naturezas, e a diferenca entre elas e o ponto todo:
#
#   AUTOMATICAS (`origem` em ORIGENS_AUTOMATICAS) -- derivam de uma data
#   que o DR publica. Nao se escrevem: sincronizam-se. Se o DR prorrogar
#   o prazo, a tarefa acompanha; se a proposta fechar ou sair da escada,
#   desaparece. Ninguem lhes muda o texto nem a data a mao, porque a
#   proxima sincronizacao desfazia isso em silencio.
#
#   A MAO (`origem` = "mão") -- alguem as escreveu. **Nunca sao tocadas
#   pela sincronizacao**, nem sequer para as apagar: uma nota de "ligar
#   ao Dr. X" nao pode evaporar-se porque o prazo mudou.
#
# Uma automatica que ja esteja feita fica feita, e nao ressuscita quando
# a data muda: marcar uma coisa como feita e um facto, e a
# sincronizacao nao apaga factos.

ORIGENS_AUTOMATICAS = ("esclarecimentos", "entrega")

# O que cada data automatica pede, dito na primeira pessoa do trabalho.
TEXTO_AUTOMATICO = {
    "esclarecimentos": "pedir esclarecimentos (prazo supletivo do CCP)",
    "entrega": "entregar a proposta",
}

# So as ranhuras onde ainda ha o que fazer geram tarefas. Um "Ganho" nao
# tem prazo de entrega para cumprir, e um "Nao fomos" muito menos.
ESTADOS_COM_TAREFAS = ("analisar", "proposta")


def datas_automaticas(a):
    """{origem: data} do que as datas do anuncio obrigam, ou vazio.

    Puro: recebe a linha do anuncio e devolve datas. E de proposito que
    nao le a base -- assim a regra testa-se sem montar propostas, e o
    prazo de esclarecimentos continua a ser UM calculo, feito num sitio
    so (prazo_de_esclarecimentos, na banda comum).
    """
    if not a:
        return {}
    datas = {}
    esclarec = prazo_de_esclarecimentos(_valor(a, "data_pub"), _valor(a, "prazo"))
    if esclarec:
        datas["esclarecimentos"] = esclarec.isoformat()
    if _valor(a, "prazo"):
        datas["entrega"] = a["prazo"]
    return datas


def sincronizar_tarefas(ref=None):
    """Poe as tarefas automaticas de acordo com as datas de hoje.

    Sem `ref`, corre sobre tudo o que esta na escada -- e o que a
    verificacao chama depois de ler os detalhes, para uma prorrogacao do
    DR chegar as tarefas no mesmo dia. Com `ref`, so esse procedimento.

    Devolve (criadas, actualizadas, apagadas). Idempotente: correr duas
    vezes seguidas da (0, 0, 0) na segunda.
    """
    criadas = mudadas = apagadas = 0
    with liga() as c:
        onde, vals = "", []
        if ref:
            onde, vals = " WHERE p.ref = ?", [ref]
        linhas = c.execute(
            "SELECT p.id, p.ref, p.estado, a.data_pub, a.prazo "
            "FROM propostas p LEFT JOIN anuncios a ON a.ref = p.ref" + onde,
            vals).fetchall()
        # As que existem, para nao ser uma consulta por proposta
        ids = [l["id"] for l in linhas]
        actuais = {}
        if ids:
            for t in c.execute(
                    "SELECT * FROM tarefas WHERE proposta_id IN (%s) AND "
                    "origem IN (%s)"
                    % (",".join("?" * len(ids)),
                       ",".join("?" * len(ORIGENS_AUTOMATICAS))),
                    ids + list(ORIGENS_AUTOMATICAS)):
                actuais[(t["proposta_id"], t["origem"])] = t
        agora = datetime.now().strftime("%Y-%m-%d %H:%M")
        for l in linhas:
            quer = (datas_automaticas(l)
                    if l["estado"] in ESTADOS_COM_TAREFAS else {})
            for origem in ORIGENS_AUTOMATICAS:
                tem = actuais.get((l["id"], origem))
                data = quer.get(origem)
                if data and not tem:
                    c.execute(
                        "INSERT INTO tarefas (proposta_id, ref, o_que, quando,"
                        " origem, criada_em) VALUES (?,?,?,?,?,?)",
                        (l["id"], l["ref"], TEXTO_AUTOMATICO[origem], data,
                         origem, agora))
                    criadas += 1
                elif data and tem and tem["quando"] != data and not tem["feita_em"]:
                    # o DR prorrogou: a tarefa acompanha. Uma ja feita
                    # fica como esta -- marcar como feita e um facto.
                    c.execute("UPDATE tarefas SET quando=? WHERE id=?",
                              (data, tem["id"]))
                    mudadas += 1
                elif not data and tem and not tem["feita_em"]:
                    # a proposta fechou, saiu da escada, ou o anuncio
                    # perdeu a data: deixa de haver o que fazer
                    c.execute("DELETE FROM tarefas WHERE id=?", (tem["id"],))
                    apagadas += 1
    return criadas, mudadas, apagadas


def criar_tarefa(o_que, quando, proposta_id=None, ref=None, quem=None):
    """Uma tarefa escrita a mao. Devolve o id, ou None se nao tem texto.

    O `ref` sozinho, sem proposta, serve o que ainda nao virou negocio --
    "ver se vale a pena" num anuncio por ver e uma tarefa legitima.
    """
    o_que = " ".join((o_que or "").split())[:200]
    if not o_que:
        return None
    if proposta_id and not ref:
        p = proposta(proposta_id)
        ref = p["ref"] if p else None
    with liga() as c:
        cur = c.execute(
            "INSERT INTO tarefas (proposta_id, ref, o_que, quando, quem,"
            " origem, criada_em) VALUES (?,?,?,?,?,?,?)",
            (proposta_id, ref, o_que, quando or None,
             quem or quem_sou() or None, "mão",
             datetime.now().strftime("%Y-%m-%d %H:%M")))
        id_ = cur.lastrowid
    registar(ref or "", "tarefa", o_que, quem)
    return id_


def marcar_tarefa(id_, feita=True, quem=None):
    """Risca ou desrisca uma tarefa. Devolve a linha, ou None."""
    with liga() as c:
        t = c.execute("SELECT * FROM tarefas WHERE id=?", (id_,)).fetchone()
        if not t:
            return None
        c.execute("UPDATE tarefas SET feita_em=? WHERE id=?",
                  (datetime.now().strftime("%Y-%m-%d %H:%M") if feita else None,
                   id_))
    registar(t["ref"] or "", "tarefa",
             "%s: %s" % ("feita" if feita else "por fazer", t["o_que"]), quem)
    return t


def tarefas_por_proposta(ids):
    """{proposta_id: [tarefas por fazer]}, numa consulta so. As feitas
    ficam de fora: o cartao mostra o que FALTA, e uma lista de coisas
    feitas num cartao e ruido que empurra o resto para baixo."""
    ids = [i for i in ids if i]
    if not ids:
        return {}
    fora = {}
    with liga() as c:
        for t in c.execute(
                "SELECT * FROM tarefas WHERE feita_em IS NULL AND "
                "proposta_id IN (%s) ORDER BY COALESCE(quando,'9999'), id"
                % ",".join("?" * len(ids)), ids):
            fora.setdefault(t["proposta_id"], []).append(t)
    return fora


# ------------------------------------------------------------- captura

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
        limpa_erro("pecas_dr_ultimo_erro")
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

    # A janela: por omissao os ultimos `dias_catchup` dias, que e o que
    # a rotina diaria quer. O varrimento historico passa datas
    # explicitas em `data_de`/`data_ate` -- e a razao de nao ir tudo
    # numa janela so esta em recolher_intervalo().
    fim = datetime.now()
    inicio = fim - timedelta(days=int(cfg["dias_catchup"]))
    filtros["dataPublicacaoDe"] = (cfg.get("data_de")
                                   or inicio.strftime("%Y-%m-%d"))
    filtros["dataPublicacaoAte"] = (cfg.get("data_ate")
                                    or fim.strftime("%Y-%m-%d"))
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

    if (not colhidos and not avarias and termos == [""]
            and cfg.get("termos_de_reserva")):
        # O portal respondeu mas nao deu nada a pesquisa sem termo: varre
        # pelos termos largos. Nunca se viu disparar (14/09/2026); o `not
        # avarias` e de proposito, porque um corte de rede tambem deixa
        # `colhidos` vazio, e responder a um timeout com seis varrimentos
        # era o contrario de «um aviso verdadeiro para logo». O que vier
        # por aqui diz que veio, para uma janela filtrada nao passar por
        # uma janela completa.
        cfg = dict(cfg, termos_de_pesquisa=cfg["termos_de_reserva"])
        ok, msg, novos = recolher(cfg)
        return ok, msg + (" (pelos termos de reserva)" if ok else ""), novos

    if not colhidos:
        if avarias:
            return False, "sem ligação ao DR: " + avarias[0], 0
        return False, "o DR não devolveu anúncios nesta janela", 0

    novos = guardar(colhidos)
    guardar_amostra("ultima_colheita.json",
                    json.dumps(colhidos[:10], ensure_ascii=False, indent=2))
    return True, "ok, %d anúncios lidos" % len(colhidos), novos


# O varrimento historico faz-se por JANELAS de datas, e nao numa janela
# grande. Duas razoes, as duas medidas contra o portal a 04/09/2026:
#
# - **o recolher() so grava no fim**, depois de percorrer todas as
#   paginas da janela. De 2015 a 2024 sao ~6 800 paginas e mais de
#   quatro horas; um corte de rede a meio nao gravava nada. Por janela,
#   o que ja se trouxe esta na base.
# - **a ordem do DR deixa de ser cronologica nas paginas fundas.** Com a
#   janela 2015-2026 e ordenacao por data, StartIndex 20 000 devolve
#   2024, mas 60 000 devolve 2019 e 120 000 e 200 000 devolvem 2022. E
#   estavel (tres voltas, sempre o mesmo), mas nao e por data -- e uma
#   ordenacao que se desfaz em profundidade, como e habitual num
#   Elasticsearch sem desempate. Com janelas de um mes o StartIndex
#   nunca passa das dezenas de paginas e a janela responde por si.
#
# Nao ha limite de profundidade (200 000 responde), portanto o que
# obriga as janelas nao e um tecto: e a ordem e a gravacao.
#
# Repetir uma janela nao custa nada de errado: o guardar() e INSERT OR
# IGNORE, por isso o comando e idempotente e retomavel de graca --
# volta-se a corre-lo e as janelas ja trazidas nao acrescentam nada.
PASSO_HISTORICO = 30


def janelas_de_datas(de, ate, passo=PASSO_HISTORICO):
    """[(de, ate), ...] a cobrir [de, ate] em pedacos de `passo` dias.

    Do mais recente para o mais antigo, como o `--detalhes`: se a
    corrida for interrompida, o que ficou por trazer e o mais velho,
    que e o que menos falta faz.

    Os dois limites sao INCLUSIVOS, como o filtro do DR -- e por isso
    que a janela seguinte comeca no dia a seguir e nao no mesmo dia.
    Um `passo` de 30 sobre um mes de 31 dias parte-o em dois, e nao ha
    mal nenhum nisso; sobrepor tambem nao teria, mas perder um dia
    teria.
    """
    inicio = datetime.strptime(de, "%Y-%m-%d")
    fim = datetime.strptime(ate, "%Y-%m-%d")
    passo = max(1, int(passo))
    janelas = []
    while fim >= inicio:
        abre = max(inicio, fim - timedelta(days=passo - 1))
        janelas.append((abre.strftime("%Y-%m-%d"), fim.strftime("%Y-%m-%d")))
        fim = abre - timedelta(days=1)
    return janelas


def _diz_ja(*partes):
    """print() que sai na hora. Numa corrida de horas, o stdout
    redireccionado fica em buffer de 8 KB -- sessenta janelas de
    progresso que so aparecem no fim, e ate la a corrida parece
    pendurada. Foi o que aconteceu a 04/09/2026."""
    print(*partes, flush=True)


def recolher_intervalo(cfg, de, ate, passo=PASSO_HISTORICO, avisar=_diz_ja,
                       recolha=None):
    """Varre [de, ate] janela a janela, gravando cada uma.

    Devolve (novos, janelas_por_trazer). As janelas que falharem sao
    devolvidas em vez de rebentarem a corrida: numa recolha de horas, um
    minuto de rede em baixo nao pode deitar fora o resto -- e como e
    idempotente, basta voltar a correr o comando com as mesmas datas.

    O `recolha` injecta-se para os testes: a condicao a provar e que
    cada janela e pedida uma vez e gravada a seguir, e isso nao se prova
    contra o portal.
    """
    recolha = recolha or recolher
    janelas = janelas_de_datas(de, ate, passo)
    novos_ao_todo, falhadas = 0, []
    ini = time.time()
    avisar("%d janelas de %d dias, de %s a %s. Ctrl-C pára e não perde "
           "nada: cada janela fica gravada." % (len(janelas), passo, de, ate))
    for n, (abre, fecha) in enumerate(janelas, 1):
        ok, mensagem, novos = recolha(dict(cfg, data_de=abre, data_ate=fecha))
        novos_ao_todo += novos
        if not ok:
            falhadas.append((abre, fecha, mensagem))
        decorrido = time.time() - ini
        avisar("  [%d/%d] %s a %s: %s (%s novos ao todo, %s decorridos, "
               "faltam ~%s)"
               % (n, len(janelas), abre, fecha, mensagem,
                  mil_pt(novos_ao_todo, " "), duracao_pt(decorrido),
                  duracao_pt(decorrido / n * (len(janelas) - n))))
    return novos_ao_todo, falhadas


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


# Os lotes de um procedimento. Medido a 02/09/2026: o DR escreve
# "Procedimento com lotes? Sim", "Nº Máx. de Lotes Autorizado: N" e, no
# objecto, um bloco "Lotes:" com "Nº: LOT-0001", "Descrição do Lote:" e o
# preco base de cada um ("Preço base s/IVA:" ou "Valor Estimado do
# Lote:"), ate a seccao numerada seguinte. E por aqui que uma linha do
# Excel da casa -- que tem o preco base DO LOTE -- se liga ao lote certo.
RX_LOTE_N = re.compile(r"^\s*N[ºo°]?\.?\s*:\s*(LOT-?\s*0*(\d+)|(\d+))\s*$", re.I)


def lotes_do_texto(texto):
    """[{n, id, descricao, preco_base}] dos lotes declarados no anuncio;
    vazio quando o procedimento nao tem lotes."""
    if not texto or not re.search(r"Procedimento com lotes\?\s*Sim", texto, re.I):
        return []
    m = re.search(r"^\s*Lotes:\s*$", texto, re.M)
    if not m:
        return []
    fora, actual = [], None
    for linha in texto[m.end():].split("\n"):
        s = linha.strip()
        if re.match(r"^\d+\s*-\s*[A-ZÀ-Ú]", s):       # a seccao seguinte
            break
        mn = RX_LOTE_N.match(s)
        if mn:
            actual = {"n": int(mn.group(2) or mn.group(3)),
                      "id": mn.group(1).strip(), "descricao": "", "preco_base": ""}
            fora.append(actual)
            continue
        if actual is None or ":" not in s:
            continue
        chave, _, valor = s.partition(":")
        k = re.sub(r"[^a-z0-9]+", " ", simplifica(chave)).strip()
        if k == "descricao do lote":
            actual["descricao"] = valor.strip()[:200]
        elif (k in ("preco base s iva", "valor estimado do lote", "preco base")
              and not actual["preco_base"]):
            actual["preco_base"] = valor.strip()[:40]
    return fora


def campos_do_detalhe(texto):
    """Le do texto do anuncio os campos que servem para filtrar e listar."""
    lotes = lotes_do_texto(texto)
    achados = {"cpv": "", "prazo": "", "preco_base": "", "plataforma": "",
               "link_pecas": "", "nif": "", "altera": anuncio_alterado(texto),
               "lotes": json.dumps(lotes, ensure_ascii=False) if lotes else ""}
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
# (o CAMPOS_DA_TRIAGEM viveu aqui: era a lista do que passava de uma
# alteracao para o original. Desde 15/09/2026 o que passa e a PROPOSTA
# inteira, e a lista deixou de ter quem a lesse.)
CAMPOS_EM_VIGOR = ("prazo", "preco_base", "cpv", "plataforma", "link_pecas",
                   "lotes")


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


def _decidido(a, c=None):
    """Se a casa ja decidiu alguma coisa sobre este anuncio.

    Era `estado != 'novo' or fase_id`, quando a decisao morava na linha
    do anuncio. Desde 15/09/2026 mora numa proposta, e a pergunta passa
    a ser se existe alguma. A `c` opcional serve quem ja tem ligacao
    aberta -- isto corre dentro do laco das alteracoes."""
    if a["estado"] != "novo":
        return True
    if c is not None:
        return bool(c.execute("SELECT 1 FROM propostas WHERE ref=?",
                              (a["ref"],)).fetchone())
    return bool(propostas_de(a["ref"]))


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
        # O que passa e a PROPOSTA (15/09/2026): era um punhado de
        # colunas do anuncio, e agora e a linha inteira -- com o preco
        # proposto, o lugar e o motivo, que e o que custa mais a
        # reescrever. Uma decisao a serio na alteracao GANHA a uma
        # diferente no original: a alteracao e a publicacao mais recente,
        # e foi sobre ela que se decidiu por ultimo. A migracao de
        # 01/09/2026 nao fazia isto e deixou um «interessa» do Afonso
        # (21924/2026) por baixo de um descarte antigo do original; o
        # item sumiu-se dos Interessados.
        da_alteracao = c.execute(
            "SELECT * FROM propostas WHERE ref=? ORDER BY COALESCE(lote,0), id",
            (ref,)).fetchall()
        do_original = c.execute(
            "SELECT estado FROM propostas WHERE ref=?", (raiz_ref,)).fetchall()
        if da_alteracao and (not do_original
                             or da_alteracao[0]["estado"] != do_original[0]["estado"]):
            if do_original:
                era = estado_da_casa(do_original[0]["estado"])
            # A do original sai: a mais recente e a que vale, e deixar as
            # duas dava dois cartoes do mesmo procedimento no quadro.
            c.execute("DELETE FROM propostas WHERE ref=?", (raiz_ref,))
            c.execute("UPDATE propostas SET ref=? WHERE ref=?", (raiz_ref, ref))
            c.execute("INSERT OR IGNORE INTO anuncio_etiquetas (ref, etiqueta_id)"
                      " SELECT ?, etiqueta_id FROM anuncio_etiquetas WHERE ref=?",
                      (raiz_ref, ref))
            herdou = (estado_da_casa(da_alteracao[0]["estado"])
                      + (" (%s)" % da_alteracao[0]["motivo"]
                         if da_alteracao[0]["motivo"] else ""))
        elif a["estado"] not in ("novo", "alteracao") and r["estado"] == "novo":
            # Sem proposta, o unico que ha para passar e o estado, e so
            # para um original que ainda esteja por decidir.
            c.execute("UPDATE anuncios SET estado=? WHERE ref=?",
                      (a["estado"], raiz_ref))
            herdou = _NOMES_ESTADO.get(a["estado"], a["estado"])
        if a["estado"] != "alteracao":
            c.execute("UPDATE anuncios SET estado='alteracao' "
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
                         altera=?, lotes=?, detalhe_lido=1 WHERE ref=?""",
                      (campos["cpv"], campos["prazo"], campos["preco_base"],
                       campos["plataforma"], texto, conteudo.get("URL_PDF") or "",
                       campos["link_pecas"], campos["nif"], altera,
                       campos["lotes"], ref))
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


def ler_detalhes(limite=40, dias=None, intervalo=1):
    """Le o detalhe dos anuncios que ainda nao o tem, do mais recente
    para o mais antigo.

    `dias` limita aos publicados nesse periodo. Serve para a rotina so
    tratar do que ainda da para concorrer: entre a publicacao e o prazo
    vao ~18 dias em media, por isso um anuncio de ha 3 meses ja fechou e
    o CPV dele so interessa como historico. Os antigos sao lidos quando
    se abre a ficha, e nao em massa.

    `intervalo` e a pausa entre pedidos, para nao castigar o portal do
    DR -- 1s por omissao, o que a rotina diaria sempre usou. So o
    `--detalhes` (via detalhes_em_lote()) pede um intervalo mais curto:
    decisao do Afonso a 3/09/2026, depois de lhe dizer que o DR nao tem
    rate-limit conhecido e que o risco de bloqueio de IP era desconhecido
    mas nao confirmado -- ver docs/diario/2026-09.md.

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
        time.sleep(intervalo)
    return feitos, ""


def ler_detalhes_paralelo(limite=40, dias=None, concorrencia=8):
    """Como ler_detalhes(), mas com `concorrencia` pedidos ao portal ao
    mesmo tempo em vez de um a seguir ao outro. So serve o `--detalhes`
    -- a rotina diaria (09h/17h) continua em ler_detalhes() sequencial,
    a 1s de intervalo, decisao separada.

    Medido a 3/09/2026 contra o portal, 150 pedidos em graus 1/2/4/8:
    zero erros e latencia estavel em todos, ~4x mais rapido que
    sequencial a 8 threads (0,118s/anuncio de throughput contra 0,3s+
    do sleep sequencial). Ver docs/diario/2026-09.md.

    Cada pedido leva a SUA PROPRIA copia do molde, com o `Key` escrito
    nessa copia -- ao contrario de ler_detalhes(), que reescreve o
    mesmo `variaveis` partilhado a cada volta do ciclo (seguro porque e
    sequencial). Em paralelo, threads a escrever no mesmo dicionario
    trocavam o Key de um pedido pelo de outro a meio do POST -- e foi
    exactamente esse bug que o ensaio da experiencia expos e corrigiu
    antes de isto aqui existir.

    O `_guardar_detalhe()` grava por conta propria (abre a sua ligacao);
    threads em paralelo escrevem em anuncios DIFERENTES (um ref por
    pedido), por isso nao ha corrida de escrita na base -- so a leitura
    do molde precisava de isolamento.

    Um "casca"/"apiVersion" nao para os pedidos ja lancados (o lote e
    pequeno, limite normalmente 40): deixa-os acabar, e so DEPOIS
    reporta o aviso -- detalhes_em_lote() para na volta seguinte."""
    par, aviso = _molde_detalhe()
    if not par:
        return 0, aviso
    pedido_base, molde_base = par

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
    if not pendentes:
        return 0, ""

    def um(ref, url):
        molde = copy.deepcopy(molde_base)
        variaveis = molde["screenData"]["variables"]
        variaveis["Key"] = url.rsplit("/", 1)[-1]
        variaveis["Tipo"] = "anuncio-procedimento"
        return ref, perguntar_ao_dr(pedido_base, molde)

    feitos, motivo = 0, ""
    with ThreadPoolExecutor(max_workers=concorrencia) as ex:
        futuros = [ex.submit(um, a["ref"], a["url"]) for a in pendentes]
        for f in as_completed(futuros):
            ref, (dados, erro) = f.result()
            if erro in ("casca", "apiVersion"):
                motivo = erro
                continue
            if erro:
                continue
            _guardar_detalhe(ref, dados)
            feitos += 1
    if motivo:
        registar_expiracao_token("curl_detalhe", "o detalhe nao foi aceite "
                                 "(%s) nem depois de renovar as peças" % motivo)
        return feitos, ("o DR não aceitou o detalhe (%s) nem depois de "
                        "renovar as peças; refaz a captura" % motivo)
    return feitos, ""


# O ritmo do `--detalhes` teve tres versoes no mesmo dia (3/09/2026),
# cada uma medida contra o portal antes de ficar:
#   1s sequencial (o da rotina diaria) -> 0,3s sequencial -> 0,1s
#   sequencial, REVERTIDO por nao ter dado mais rapido (0,78-0,82s
#   medidos, PIOR que os 0,68s a 0,3s, sem erro nenhum -- ver o
#   comentario que ficou em ler_detalhes() e o docs/diario/2026-09.md)
#   -> concorrencia=8 (ler_detalhes_paralelo()), a versao que ficou.
#
# CONCORRENCIA_DETALHES: 150 pedidos de ensaio em graus 1/2/4/8, zero
# erros e latencia estavel em todos os graus -- ver
# ler_detalhes_paralelo(). Decisao do Afonso, sabendo que o risco de
# bloqueio de IP por rajada nao esta medido nem confirmado nem
# afastado (docs/armadilhas.md): o grau MAIS ALTO testado, nao um
# meio-termo.
CONCORRENCIA_DETALHES = 8

# 0,118s no ensaio isolado (um lote so, uma ThreadPoolExecutor). O
# --detalhes de verdade e mais lento que isso -- 632 anuncios em 120s
# = 0,19s, medido com o comando completo a correr -- porque cada volta
# de `lote` (40) abre a SUA PROPRIA pool de threads e le o
# curl_detalhe.txt outra vez; o ensaio isolado nao paga essa
# sobrecarga repetida. Serve so para a estimativa que o comando
# imprime ANTES de comecar; a partir da primeira volta o que se mostra
# e o ritmo verdadeiro.
SEGUNDOS_POR_DETALHE = 0.19
VOLTAS_VAZIAS = 3           # quantos blips de rede se toleram de seguida
ESPERA_ENTRE_VAZIAS = 30    # segundos


def detalhes_em_lote(alvo, lote, contar, concorrencia=CONCORRENCIA_DETALHES,
                     ler=None, esperar=None, diz=None):
    """Le o detalhe de `alvo` anuncios em voltas de `lote`. Devolve
    quantos leu.

    Serve o `--detalhes`, que enche o detalhe de toda a base -- por
    omissao com `concorrencia` pedidos ao portal ao mesmo tempo
    (`ler_detalhes_paralelo()`; ver ali a medicao que sustenta o grau).
    O contrato e ser retomavel e nao desistir a primeira: um pedido que
    falhe de rede ou traga JSON ilegivel nao para a volta -- so conta
    menos "feitos" que o lote, aviso vazio --, e numa corrida de horas
    isso e um blip: parar ai perdia a noite por causa de um segundo.
    Tolera VOLTAS_VAZIAS seguidas, com ESPERA_ENTRE_VAZIAS entre elas,
    e so depois desiste.

    Um aviso -- captura recusada pelo portal -- para logo: bater outra
    vez na mesma porta nao a abre.

    `contar` diz quantos faltam, e e o que distingue "acabou" de "falhou
    a rede"; `ler`, `esperar` e `diz` sao injectaveis para o teste poder
    forcar as voltas vazias sem rede, sem threads verdadeiras e sem
    sleeps de verdade -- quando injectado, `ler` decide a propria
    concorrencia e este parametro nao se aplica."""
    ler = ler or (lambda n, dias=None: ler_detalhes_paralelo(
        n, dias=dias, concorrencia=concorrencia))
    esperar = esperar or time.sleep
    diz = diz or (lambda t: print("  " + t))
    ini, feitos_total, vazios = time.time(), 0, 0
    try:
        while feitos_total < alvo:
            feitos, aviso = ler(min(lote, alvo - feitos_total), dias=None)
            feitos_total += feitos
            if aviso:
                diz("Parado: %s" % aviso)
                break
            if not feitos:
                if not contar():
                    break               # acabou de verdade
                vazios += 1
                if vazios >= VOLTAS_VAZIAS:
                    diz("Parado: %d voltas seguidas sem ler nada (rede?). "
                        "Repete o comando mais tarde." % VOLTAS_VAZIAS)
                    break
                diz("nada nesta volta (%d/%d); espero %ds e tento outra vez"
                    % (vazios, VOLTAS_VAZIAS, ESPERA_ENTRE_VAZIAS))
                esperar(ESPERA_ENTRE_VAZIAS)
                continue
            vazios = 0
            decorrido = time.time() - ini
            diz("%s/%s (%.1f%%), %s decorridos, faltam ~%s"
                % (mil_pt(feitos_total, " "), mil_pt(alvo, " "),
                   100.0 * feitos_total / alvo, duracao_pt(decorrido),
                   duracao_pt((alvo - feitos_total) * decorrido / feitos_total)))
    except KeyboardInterrupt:
        diz("Interrompido.")
    return feitos_total


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
                "SELECT ref, estado FROM anuncios WHERE ref=?",
                (alvo,)).fetchone()
            ja = c.execute(
                "SELECT 1 FROM historico WHERE ref=? AND accao='rectificado'"
                " AND detalhe LIKE ?",
                (alvo, "%" + r["ref"] + "%")).fetchone()
        if not original or ja:
            continue
        registar(alvo, "rectificado", "pelo anúncio %s" % r["ref"],
                 quem="DR")
        if _decidido(original):
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

    Marcado = tem proposta na escada: e o que esta a ser
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
            " AND EXISTS (SELECT 1 FROM propostas p WHERE p.ref = a.ref)"
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
                             plataforma=?, link_pecas=?, nif=?, altera=?, lotes=?
                             WHERE ref=?""",
                          (campos["cpv"], campos["prazo"], campos["preco_base"],
                           campos["plataforma"], campos["link_pecas"],
                           campos["nif"], altera, campos["lotes"], a["ref"]))
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
    return "{:,.2f}".format(float(valor)).translate(str.maketrans(",.", ".,")) + " EUR"


def hora_de_lisboa(iso):
    """A data/hora UTC da Vortal na hora legal de Portugal continental.

    A API devolve tudo em UTC ("2026-09-03T22:59:00Z") e a propria
    Vortal mostra 23:59 na pagina: no Verao, Lisboa e UTC+1. Escrever o
    UTC na ficha punha o prazo uma hora mais cedo do que a plataforma
    diz -- e um prazo e a informacao pela qual se perde uma proposta.

    A regra da hora de Verao e a da UE, e quem a sabe e o zoneinfo
    (ate 14/09/2026 fazia-se a conta a mao, porque o Windows da pen nao
    garantia os dados de fusos). Devolve ISO "AAAA-MM-DD HH:MM"; o que
    nao for data volta como veio.
    """
    m = re.match(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})", (iso or "").strip())
    if not m:
        return " ".join(str(iso or "").split())
    quando = datetime.strptime(m.group(1) + " " + m.group(2), "%Y-%m-%d %H:%M")
    return (quando.replace(tzinfo=timezone.utc).astimezone(LISBOA)
            .strftime("%Y-%m-%d %H:%M"))


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


def ref_de_pasta(ref):
    """A ref como nome de UMA pasta dentro de documentos/.

    O `re.sub` sozinho nao chegava: trocava a barra por hifen, mas
    deixava `..` passar inteiro -- e `documentos/..` e a pasta do
    radar. Como as rotas das pecas recebem `<path:ref>`, um pedido a
    /peca/../radar.db servia a base, o config.json ou as capturas do
    curl a quem tivesse sessao. Os pontos das pontas caem, como em
    nome_seguro(); uma ref verdadeira ("12345/2026") nao muda.
    """
    ref = re.sub(r"[^0-9A-Za-z._-]", "-", ref or "").strip(". ")
    return ref[:150] or "anuncio"


def pasta_do_anuncio(ref):
    return os.path.join(DOCS, ref_de_pasta(ref))


def caminho_na_pasta(ref, nome):
    """O ficheiro `nome` da pasta do anuncio `ref`, ou None.

    None se nao existir, se o nome saltar da pasta, ou se a propria
    pasta cair fora de documentos/ -- sem esta ultima, a guarda media
    o caminho contra um sitio que o proprio pedido tinha escolhido.
    E o unico sitio por onde as quatro rotas que servem ficheiros
    chegam ao disco.
    """
    raiz = os.path.abspath(DOCS)
    pasta = os.path.abspath(pasta_do_anuncio(ref))
    caminho = os.path.abspath(os.path.join(pasta, nome_seguro(nome)))
    if not pasta.startswith(raiz + os.sep) and pasta != raiz:
        return None
    if not caminho.startswith(pasta + os.sep):
        return None
    return caminho if os.path.exists(caminho) else None


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
# As plataformas que ainda existem (14/09/2026, a pedido do Afonso: «as
# que hoje ja nao tens acesso e porque ja nao existem -- juntamos todas
# como outras»). O resto -- saphety (ultimo anuncio em 2024),
# compraspublicas (2020), gatewit e construlink (2016), bizgov (2017)
# -- fica na base tal como esta, mas nos selectores e um balde so,
# OUTRAS_PLATAFORMAS. O filtro por nome continua a aceitar qualquer
# uma: um alerta antigo com plat=saphety nao parte.
PLATAFORMAS_ACTIVAS = ("acingov", "vortal", "anogov", "compraspt")
OUTRAS_PLATAFORMAS = "(outras)"


def agrupar_plataformas(contagens):
    """{plataforma: n} -> [(plataforma, n)] para um selector: as activas
    pela contagem, depois "outras" com a soma das que ja nao existem,
    e a "(nenhuma)" no fim. As chaves especiais passam intactas."""
    activas, outras, especiais = {}, 0, {}
    for p, n in contagens.items():
        if p in PLATAFORMAS_ACTIVAS:
            activas[p] = n
        elif p in (SEM_PLATAFORMA, POR_LER):
            especiais[p] = n
        else:
            outras += n
    saida = sorted(activas.items(), key=lambda x: -x[1])
    if outras:
        saida.append((OUTRAS_PLATAFORMAS, outras))
    saida.extend(especiais.items())
    return saida


def rotulo_da_plataforma(p):
    if p == SEM_PLATAFORMA:
        return "sem plataforma indicada"
    if p == POR_LER:
        return "ainda sem detalhe lido"
    if p == OUTRAS_PLATAFORMAS:
        return "outras (já não existem)"
    return p

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


def _nome_sem_corpo(sessao, endereco):
    """O nome que a plataforma da a um ficheiro, sem descarregar o corpo.

    Abre o pedido em stream e fecha-o depois dos cabecalhos: o nome vem
    no Content-Disposition e o corpo nunca se le. E o que deixa VIGIAR a
    lista da anogov/ComprasPT/ESPAP, onde o nome nao esta na pagina --
    so na resposta de cada descarga."""
    try:
        with sessao.get(endereco, timeout=90, stream=True) as r:
            return _nome_da_resposta(r) if r.status_code == 200 else ""
    except requests.RequestException:
        return ""


def _buscar_do_endereco(sessao, endereco):
    """Uma funcao que descarrega este endereco quando for chamada."""
    def buscar():
        _, dados = _descarregar(sessao, endereco)
        return dados
    return buscar


def _buscar_do_zip(bruto, dentro):
    """Uma funcao que tira este membro do ZIP que ja esta em memoria."""
    def buscar():
        with zipfile.ZipFile(io.BytesIO(bruto)) as z:
            info = z.getinfo(dentro)
            return None if info.file_size > MAX_FICHEIRO else z.read(dentro)
    return buscar


def pecas_disponiveis(sessao, link):
    """([(nome, buscar)], aviso) das pecas que a plataforma mostra AGORA.

    `buscar` e uma funcao sem argumentos que devolve os bytes dessa
    peca, ou None; so se chama para as que sao novas, e e isso que
    deixa vigiar a lista sem trazer o procedimento inteiro a cada
    verificacao.

    **O obter_documentos() NAO serve para vigiar.** Faz
    `DELETE FROM documentos WHERE ref=?` e volta a trazer tudo -- o que
    apagava o texto ja extraido e os veredictos do OCR, e mandava as
    ~7 s por pagina outra vez em cada digitalizacao. Vigiar e ler a
    lista e trazer so o que falta.

    Cada plataforma da o que da:
      - vortal: os nomes vem na resposta JSON, sem descarregar nada;
      - acingov: a lista E o ZIP -- nao ha endereco de listagem (a
        pagina do procedimento exige sessao, medido a 01/09/2026), por
        isso o ZIP vem para memoria e le-se o infolist() dele;
      - anogov/ComprasPT/ESPAP: os enderecos estao na pagina e o nome
        vem no cabecalho de cada um (_nome_sem_corpo).
    """
    link = link or ""
    if "acingov" in link:
        _, bruto = _descarregar(sessao, link, limite=MAX_FICHEIRO * 4)
        if not bruto or not bruto.startswith(b"PK"):
            return [], "o ZIP das peças não veio"
        with zipfile.ZipFile(io.BytesIO(bruto)) as z:
            nomes = [i.filename for i in z.infolist() if not i.is_dir()]
        return [(nome_seguro(n), _buscar_do_zip(bruto, n)) for n in nomes], ""
    if "vortal" in link:
        lista = []
        m = re.search(r"(PT\d+\.NTC\.\d+)", link)
        if not m:
            lista, endereco = _info_vortal(sessao, link)
            m = re.search(r"(PT\d+\.NTC\.\d+)", endereco)
        if not lista:
            if not m:
                return [], "a Vortal não deu o identificador do procedimento"
            try:
                resposta = sessao.get(VORTAL_DOCS, timeout=90, params={
                    "contractNoticeUId": m.group(1)}).json()
            except (requests.RequestException, ValueError):
                return [], "a Vortal não respondeu à lista das peças"
            lista = resposta if isinstance(resposta, list) else []
        fora = []
        for doc in lista:
            endereco = doc.get("downloadUrl")
            if not endereco:
                continue
            # As duas respostas nao chamam o nome do ficheiro o mesmo.
            rotulo = doc.get("name") or doc.get("documentName") or "documento"
            fora.append((nome_seguro(rotulo),
                         _buscar_do_endereco(sessao, endereco)))
        return fora, ""
    if ASSINATURA_JSF in link.lower():
        try:
            pagina = sessao.get(link, timeout=120)
        except requests.RequestException as erro:
            return [], "a plataforma não respondeu (%s)" % str(erro)[:60]
        pagina.encoding = "windows-1252"
        fora = []
        for endereco in docs_jsf_da_pagina(pagina.text, link):
            nome = _nome_sem_corpo(sessao, endereco) or "documento"
            fora.append((nome_seguro(nome),
                         _buscar_do_endereco(sessao, endereco)))
        return fora, ""
    return [], ""


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


# ------------------------------ desenhar e procurar dentro do PDF
#
# O visualizador proprio da peca: desenhar a pagina no servidor e a
# unica maneira de ela abrir SEMPRE dentro da aplicacao, e a procura
# por pagina e o que deixa destacar o termo la dentro.

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
        # A mesma marca de pagina entre PDFs do mesmo ZIP: a numeracao
        # segue pelo conjunto fora, e a ficha diz "pag. N do texto
        # extraido" -- num ZIP com varios PDFs nao ha outra verdade.
        return "\n\f\n".join(partes), "ok"
    # Nao sai texto por duas razoes muito diferentes, e dize-las trocadas
    # manda a pessoa buscar a ferramenta errada: um PDF cifrado nao e
    # uma digitalizacao.
    erros = [e for e in estados if e.startswith("erro")]
    return "", (erros[0] if erros else "scan")


def extrair_textos(ref):
    """Guarda o texto dos PDFs deste anuncio. Devolve (lidos, digitalizados).

    Le o que ainda nao tem estado e retenta os "erro:". Um PDF sem
    camada de texto fica em 'scan' e ai fica: e um veredicto sobre o
    conteudo, nao uma falha da ferramenta.
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
            # 'ocr' e legado: o OCR saiu a 03/09/2026, mas o texto
            # que ele extraiu na altura e texto a serio e continua a servir.
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


# As duas razoes por que a leitura nao acontece SEM que o modelo tenha
# falhado: nao ha o que ler. Nao sao erros da leitura, sao o estado das
# pecas -- e ate 04/09/2026 iam parar todas ao "Ultimo erro da leitura
# pelo modelo", onde acusavam o modelo de uma coisa que era da
# plataforma. Dos tres que la estavam nesse dia, um era uma consulta
# preliminar (que nao TEM Caderno de Encargos), outro um anuncio cujo
# link_pecas e a pagina de entrada da Vortal, sem codigo de
# procedimento. Ficam no historico da ficha, que e onde interessam.
SEM_NADA_PARA_LER = (
    "ainda não há Caderno de Encargos nem Programa em disco",
    "os documentos deste concurso são digitalizações, sem "
    "texto que se possa ler",
)


def e_falta_de_pecas(porque):
    """Se o "nao leu" foi por nao haver o que ler, e nao por falha."""
    return (porque or "").strip() in SEM_NADA_PARA_LER


def analisar_pecas(ref):
    """Le as pecas com o modelo e guarda os quatro campos. (ok, aviso).

    Um `aviso` de `SEM_NADA_PARA_LER` nao e falha do modelo: quem
    chamar nao o deve registar como erro de leitura -- ver
    `e_falta_de_pecas()`.
    """
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
        return False, ("os documentos deste concurso são digitalizações, sem "
                       "texto que se possa ler" if scans else
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
        if lido and not porque:
            limpa_erro("analise_ultimo_erro")
        elif not lido and not e_falta_de_pecas(porque):
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
            if n and not aviso:
                limpa_erro("docs_ultimo_erro")
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


# --- vigiar a lista das pecas dos anuncios marcados (14/09/2026)
#
# O reler_marcados() vigia o prazo e o preco base na pagina do DR. Mas
# um esclarecimento ou uma errata NAO passam pelo DR: aparecem na
# plataforma, na lista de documentos do procedimento, e ninguem os
# encontrava sem abrir a plataforma a mao (o 21830/2026: o CE original
# pedia o Office E1, a resposta aos esclarecimentos dizia E3).
#
# Existiu a 3/09/2026 a vigiar TODOS os marcados a cada verificacao, e
# saiu no dia seguinte por vigiar seis anuncios. Voltou a 14/09/2026
# com um desenho diferente, o que o Afonso pediu: nao se vigia sempre,
# vigia-se quando ha uma RAZAO -- passou a data de esclarecimentos, ou
# houve uma prorrogacao do prazo ou um preco base novo -- e ha um botao
# na ficha para quando se quer olhar agora. `pecas_vigiadas_em` e a
# memoria de quando se olhou pela ultima vez; a razao conta desde ai.

CAMPO_PECA_NOVA = "peca_nova"

# As pecas que o radar acrescenta e a plataforma nao tem: se nao se
# excluissem, o "Anúncio DR.pdf" contava como peca desaparecida numa
# ponta e nova na outra a cada verificacao.
PECAS_DO_RADAR = ("Anúncio DR.pdf",)


def _guardar_pecas_novas(ref, plataforma, disponiveis):
    """Guarda e avisa as pecas que ainda nao estao na base. Devolve quantas.

    Traz a peca nova e acrescenta a linha -- **sem apagar as que ja
    estao**, que e a diferenca em relacao ao obter_documentos(). Uma
    peca ja avisada nao se avisa outra vez mesmo que nao se consiga
    guardar (ficheiro acima do tecto): sem essa guarda, o mesmo
    esclarecimento saia no resumo a cada verificacao, duas vezes por
    dia, para sempre.
    """
    with liga() as c:
        tinha = {r["nome"] for r in c.execute(
            "SELECT nome FROM documentos WHERE ref=?", (ref,))}
        avisadas = {r["depois"] for r in c.execute(
            "SELECT depois FROM alteracoes WHERE ref=? AND campo=?",
            (ref, CAMPO_PECA_NOVA))}
    pasta = pasta_do_anuncio(ref)
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    quantas = 0
    for nome, buscar in disponiveis:
        if nome in tinha or nome in avisadas or nome in PECAS_DO_RADAR:
            continue
        try:
            dados = buscar()
        except (requests.RequestException, ValueError, zipfile.BadZipFile,
                KeyError, OSError):
            dados = None
        if dados:
            os.makedirs(pasta, exist_ok=True)
            with open(os.path.join(pasta, nome), "wb") as f:
                f.write(dados)
            with liga() as c:
                c.execute("INSERT INTO documentos (ref,nome,ficheiro,tamanho,"
                          "origem,obtido_em) VALUES (?,?,?,?,?,?)",
                          (ref, nome, nome, len(dados),
                           plataforma or "dr", agora))
        with liga() as c:
            c.execute("INSERT INTO alteracoes (ref, campo, antes, depois,"
                      " detectado_em) VALUES (?,?,?,?,?)",
                      (ref, CAMPO_PECA_NOVA, "", nome, agora))
        registar(ref, "alterou", "peça nova na plataforma: %s%s"
                 % (nome, "" if dados else " (não se conseguiu trazer)"),
                 quem="plataforma")
        quantas += 1
    if quantas:
        # So as novas: as outras linhas nao estao a NULL e o
        # extrair_textos() nao lhes toca.
        extrair_textos(ref)
    return quantas


def razao_para_vigiar(a, hoje, alteracoes_desde):
    """Porque e que vale a pena ir a plataforma ver a lista das pecas
    deste anuncio AGORA, ou "" se nao vale.

    `a` traz data_pub, prazo e pecas_vigiadas_em; `alteracoes_desde(ref,
    desde)` diz se houve prorrogacao ou preco base novo detectados
    depois de `desde`. Duas razoes, as que o Afonso pediu:

      - passou a data de esclarecimentos (prazo_de_esclarecimentos, a
        regra do primeiro terco) e ainda nao se olhou depois dela: e a
        altura em que as respostas e as erratas aparecem;
      - houve uma prorrogacao do prazo ou um preco base novo desde a
        ultima vez que se olhou: quase sempre vem com peças revistas.
    """
    desde = (a["pecas_vigiadas_em"] or "")[:10]
    limite = prazo_de_esclarecimentos(a["data_pub"], a["prazo"])
    if limite and hoje > limite and (not desde or desde <= limite.isoformat()):
        return "passou a data de esclarecimentos (%s)" % data_pt(limite.isoformat())
    if alteracoes_desde(a["ref"], a["pecas_vigiadas_em"] or ""):
        return "o prazo ou o preço base mudaram"
    return ""


def _alteracoes_desde(ref, desde):
    with liga() as c:
        return c.execute(
            "SELECT 1 FROM alteracoes WHERE ref=? AND campo IN ('prazo','preco_base')"
            " AND detectado_em > ? LIMIT 1", (ref, desde)).fetchone() is not None


def anuncios_a_vigiar(limite=10, hoje=None):
    """[(anuncio, razao)] dos marcados que tem uma razao para se ir ver
    a plataforma. Marcado = tem proposta na escada, com prazo
    aberto, com link das pecas e com pecas ja trazidas -- sem uma lista
    de partida nao ha com que comparar, e cada peca contaria como nova."""
    hoje = hoje or datetime.now().date()
    with liga() as c:
        marcados = c.execute(
            "SELECT ref, plataforma, link_pecas, data_pub, prazo, pecas_vigiadas_em"
            " FROM anuncios"
            " WHERE EXISTS (SELECT 1 FROM propostas p WHERE p.ref = anuncios.ref)"
            " AND docs_estado IN ('ok','parcial')"
            " AND COALESCE(link_pecas,'') != ''"
            " AND COALESCE(prazo,'') != '' AND prazo >= ?"
            " ORDER BY prazo", (hoje.isoformat(),)).fetchall()
    escolhidos = []
    for a in marcados:
        razao = razao_para_vigiar(a, hoje, _alteracoes_desde)
        if razao:
            escolhidos.append((a, razao))
            if len(escolhidos) >= limite:
                break
    return escolhidos


def _sessao_das_pecas():
    sessao = requests.Session()
    sessao.headers.update({"User-Agent": NAVEGADOR,
                           "Accept": "application/json, text/plain, */*"})
    return sessao


def vigiar_anuncio(a, sessao=None, razao="a pedido", reler=None):
    """Vai a plataforma ver a lista das pecas DESTE anuncio e guarda as
    novas. (quantas novas, aviso). Marca `pecas_vigiadas_em` so quando a
    plataforma respondeu: uma lista vazia e a plataforma a falhar, nao
    "as pecas desapareceram" (a regra do diferencas_do_detalhe(): so se
    conta o que tem valor dos dois lados), e a razao fica de pe para a
    volta seguinte.

    `reler(ref)` chama-se quando ha peca nova (decisao do Afonso a
    14/09/2026: "se tem peça nova deve logo ser revisto pelo modelo").
    Injectavel: a verificacao le em linha, o botao poe na fila.
    """
    sessao = sessao or _sessao_das_pecas()
    try:
        disponiveis, aviso = pecas_disponiveis(sessao, a["link_pecas"])
    except (requests.RequestException, ValueError, zipfile.BadZipFile,
            OSError) as erro:
        disponiveis, aviso = [], str(erro)[:100]
    if aviso or not disponiveis:
        return 0, aviso or "a plataforma não deu a lista das peças"
    novas = _guardar_pecas_novas(a["ref"], a["plataforma"], disponiveis)
    with liga() as c:
        c.execute("UPDATE anuncios SET pecas_vigiadas_em=? WHERE ref=?",
                  (datetime.now().strftime("%Y-%m-%d %H:%M"), a["ref"]))
    if not novas:
        registar(a["ref"], "verificou as peças",
                 "nenhuma peça nova na plataforma (%s)" % razao, quem="plataforma")
    elif reler is not None:
        reler(a["ref"])
    return novas, ""


def vigiar_pecas(limite=10, hoje=None):
    """Peca nova (esclarecimento, errata) nos anuncios marcados que tem
    uma razao para isso (razao_para_vigiar): avisa. (novas, aviso)."""
    escolhidos = anuncios_a_vigiar(limite, hoje)
    if not escolhidos:
        return 0, ""
    sessao = _sessao_das_pecas()
    novas, falhas = 0, []
    for a, razao in escolhidos:
        # em linha, nao pela fila: no --uma-vez a fila morria com o processo
        n, aviso = vigiar_anuncio(
            a, sessao, razao,
            reler=lambda ref: ler_pecas_e_registar(ref, "plataforma"))
        if aviso:
            falhas.append("%s: %s" % (a["ref"], aviso))
        novas += n
    if falhas:
        marca_erro("docs_ultimo_erro", "pecas", "%s · a vigiar peças · %s"
                   % (datetime.now().strftime("%Y-%m-%d %H:%M"),
                      " | ".join(falhas[:3])))
    return novas, (" | ".join(falhas) if falhas else "")


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


def ler_pecas_e_registar(ref, quem=""):
    """analisar_pecas() com o rasto: a linha no historico e a marca de
    erro. E o corpo da fila, e tambem o que a vigilancia das pecas chama
    em linha (14/09/2026): no processo do `--uma-vez` a fila e uma
    thread daemon que morria com o processo antes de ler."""
    try:
        ok, porque = analisar_pecas(ref)
        # "leitura", nao "análise": e o nome que o ecra usa (§7 do
        # ESQUELETO). Os registos antigos traduzem-se ao mostrar.
        registar(ref, "leitura",
                 "peças lidas" if (ok and not porque) else (porque or "falhou"),
                 quem=quem)
        if ok and not porque:
            limpa_erro("analise_ultimo_erro")
        elif not ok and not e_falta_de_pecas(porque):
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


def _servir_analise():
    while True:
        ref, quem = _FILA_ANALISE.get()
        try:
            ler_pecas_e_registar(ref, quem)
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


# As tarefas que o agendar.sh cria: os temporizadores do systemd na
# sessao do utilizador, procurados pelo nome da unidade na saida de
# `systemctl --user list-timers --all`. Se nao existirem, o radar so
# recolhe com o painel aberto -- e como o relogio interno recupera os
# slots falhados, a tabela `slots` fica preenchida e parece que correu a
# horas. Foi assim que isto passou semanas sem se notar (no Windows, com
# o schtasks; e ate 8/09/2026 fora do Windows devolvia-se vazio, "nao ha
# o que avisar", que era o modo de falha que o aviso existe para apanhar).
TAREFAS_LINUX = ("radar-09h.timer", "radar-17h.timer")
_TAREFAS_VISTAS = None
_TAREFAS_QUANDO = 0.0
# A resposta guarda-se durante um minuto e nao para sempre. Era para
# sempre: correr o agendar.sh com o painel aberto deixava o aviso
# vermelho no ecra ate se reiniciar o painel, e apagar uma tarefa nunca
# chegava a ser notado. E o aviso que impede o pior modo de falha desta
# aplicacao -- parecer viva sem estar a recolher nada -- e era o que
# menos se actualizava.
TAREFAS_VALIDADE = 60


def comando_das_tarefas(sistema=None):
    """O comando que lista as tarefas agendadas neste sistema, e os
    nomes que la se procuram. `None` onde nao ha agendador que se saiba
    consultar (macOS, por exemplo): ai nao se inventa aviso."""
    sistema = sistema or sys.platform
    if sistema.startswith("linux"):
        return (["systemctl", "--user", "list-timers", "--all",
                 "--no-legend", "--plain"], TAREFAS_LINUX)
    return None, ()


def tarefas_em_falta(listar=None, sistema=None):
    """Quais das tarefas agendadas nao estao criadas.

    A resposta guarda-se por um minuto: e um subprocesso, e o painel
    monta paginas muitas vezes. `listar` e a funcao que corre o comando
    e devolve a saida (injectavel nos testes; por omissao corre-o
    mesmo). Onde nao ha agendador conhecido devolve vazio.
    """
    global _TAREFAS_VISTAS, _TAREFAS_QUANDO
    if (_TAREFAS_VISTAS is not None
            and time.time() - _TAREFAS_QUANDO < TAREFAS_VALIDADE):
        return _TAREFAS_VISTAS
    _TAREFAS_QUANDO = time.time()
    comando, nomes = comando_das_tarefas(sistema)
    if not comando:
        _TAREFAS_VISTAS = []
        return _TAREFAS_VISTAS
    try:
        havidas = (listar or _saida_de)(comando) or ""
    except (OSError, subprocess.SubprocessError):
        _TAREFAS_VISTAS = []            # nao se sabe: nao se inventa aviso
        return _TAREFAS_VISTAS
    _TAREFAS_VISTAS = [t for t in nomes if t not in havidas]
    return _TAREFAS_VISTAS


def _saida_de(comando):
    r = subprocess.run(comando, capture_output=True, text=True, timeout=20,
                       encoding="utf-8", errors="replace")
    return r.stdout or ""


def como_agendar():
    """A frase do aviso: onde e que as tarefas faltam, e o que correr."""
    return "nos temporizadores do systemd", "agendar.sh"


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
    # encontra o ficheiro feito e nao faz nada. Medido a 15/09/2026, em
    # Ubuntu e com a base nos 1,23 GB: 3,4 s e 16 MB de RSS. O numero
    # que aqui estava -- "44 MB leva 37 s" -- era do Windows na pen, e
    # dava a entender que uma copia a cada verificacao era tempo a
    # mais; nao e, e o tempo deixou de ser a razao. A razao e o disco:
    # sao 1,23 GB por copia e sete guardadas, ~8,6 GB, e duas do mesmo
    # dia nao valem o dobro.
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
            pass                        # permissoes, disco: nao se estraga
                                        # a copia nova por causa das velhas
    return destino


def copia_de_seguranca_com_nome(marca_nome):
    """Uma copia fora da rotacao diaria, com um nome que diz porque:
    copias/radar-<nome>-<data>.db. Nao se apaga sozinha."""
    os.makedirs(COPIAS, exist_ok=True)
    destino = os.path.join(COPIAS, "radar-%s-%s.db"
                           % (marca_nome, datetime.now().strftime("%Y-%m-%d")))
    if os.path.exists(destino):
        os.remove(destino)
    with liga() as c:
        c.execute("VACUUM INTO ?", (destino,))
    return destino


def repor_estado_zero():
    """A aplicacao como acabada de instalar, SEM perder o acervo.

    Apaga (decisao do Afonso a 8/09/2026): a escada inteira (as
    propostas e as tarefas -- tudo volta a "por ver"), as etiquetas, o
    historico, os responsaveis e a lista de pessoas, os filtros
    guardados e os alertas, as entidades seguidas, o interesse, o
    registo da casa, a fila de alteracoes, e o destino do resumo por
    e-mail. Mantem: os anuncios e os detalhes, as republicacoes (estado
    'alteracao'), os documentos e a analise, as contas e sessoes, a
    recolha, e quem envia o e-mail.
    Devolve as contagens do que apagou."""
    n = {}
    with liga() as c:
        # A triagem deixou de morar no anuncio (15/09/2026): o que se
        # repoe aqui e o responsavel e um estado que nao seja o de
        # origem; a escada inteira sai com a tabela `propostas`, na
        # lista de baixo.
        n["triagem reposta"] = c.execute(
            "SELECT COUNT(*) FROM anuncios WHERE estado NOT IN "
            "('novo','alteracao')").fetchone()[0]
        c.execute("UPDATE anuncios SET estado='novo' "
                  "WHERE estado NOT IN ('novo','alteracao')")
        for tabela in ("propostas", "tarefas", "contactos",
                       "anuncio_etiquetas", "etiquetas", "historico", "pessoas",
                       "filtros_guardados", "alertas_vistos", "entidades_seguidas",
                       "seguidas_vistos", "casa", "alteracoes"):
            try:
                n[tabela] = c.execute("SELECT COUNT(*) FROM %s" % tabela).fetchone()[0]
                c.execute("DELETE FROM %s" % tabela)
            except sqlite3.OperationalError:
                n[tabela] = "(não existe)"
    gravar_config({"interesse_activo": False, "interesse_cpv": "", "interesse_cpv_excl": "",
                   "email": {"para": ""}})
    marca("ultimo_resumo_estado", "")
    return n


def copia_com_marca(guardar=7):
    """A copia diaria, com o resultado numa marca que o painel mostra.

    A falha fazia so print() para uma consola que ninguem ve -- as
    tarefas correm pelo systemd, sem terminal, e o print vai para o
    journal, onde ninguem olha todos os dias -- e uma copia a falhar
    dias seguidos (disco cheio, permissoes) passava em silencio,
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


def ultima_copia():
    """O ficheiro mais recente da rotacao diaria em copias/, ou None."""
    if not os.path.isdir(COPIAS):
        return None
    nomes = sorted(f for f in os.listdir(COPIAS)
                   if re.fullmatch(r"radar-[\d-]+\.db", f))
    return os.path.join(COPIAS, nomes[-1]) if nomes else None


TABELAS_DO_ENSAIO = ("anuncios", "historico", "utilizadores", "etiquetas")


def ensaiar_copia(copia=None):
    """Prova que a copia se restaura, sem a restaurar: abre-a so de
    leitura, passa-lhe o integrity_check, e conta o que nela ha contra
    a base viva -- os anuncios, a triagem (interessa + descartado), o
    historico, as contas. Uma copia que abre mas tem 0 anuncios, ou um
    integrity_check que nao diz «ok», e uma copia que nao serve, e
    isso queria-se saber ANTES do dia em que e precisa.

    Devolve um dicionario: ficheiro, integridade, e por cada contagem
    o par (copia, viva). A marca `ultimo_ensaio_copia` fica com o
    resultado, para a saude dos Indicadores.

    Nao e um restauro: esse e parar o servico, copiar o ficheiro por
    cima do radar.db e arrancar -- esta no LEIA-ME, seccao 13. Isto e
    o que se corre uma vez por mes para saber que esse dia corre bem.
    """
    copia = copia or ultima_copia()
    if not copia or not os.path.exists(copia):
        raise FileNotFoundError("não há cópia nenhuma em %s" % COPIAS)
    contagens = {}

    def conta(c):
        n = {}
        for t in TABELAS_DO_ENSAIO:
            try:
                n[t] = c.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
            except sqlite3.OperationalError:
                n[t] = None
        n["triagem"] = c.execute(
            "SELECT COUNT(*) FROM anuncios "
            "WHERE estado IN ('interessa','descartado')").fetchone()[0]
        return n

    # mode=ro: o ensaio nunca escreve na copia -- nem um -journal ao lado
    uri = "file:%s?mode=ro" % os.path.abspath(copia).replace("?", "%3F")
    lida = sqlite3.connect(uri, uri=True)
    try:
        integridade = lida.execute("PRAGMA integrity_check").fetchone()[0]
        da_copia = conta(lida)
    finally:
        lida.close()
    with liga() as c:
        da_viva = conta(c)
    for chave in da_copia:
        contagens[chave] = (da_copia[chave], da_viva[chave])
    serve = integridade == "ok" and (da_copia["anuncios"] or 0) > 0
    resultado = {"ficheiro": copia, "integridade": integridade,
                 "serve": serve, "contagens": contagens}
    marca("ultimo_ensaio_copia", "%s: %s a %s (%s anúncios, %s na triagem)"
          % ("ok" if serve else "FALHOU", os.path.basename(copia),
             datetime.now().strftime("%Y-%m-%d %H:%M"),
             mil_pt(da_copia["anuncios"] or 0), mil_pt(da_copia["triagem"])))
    return resultado


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
# As colunas das tabelas do CRM, numa lista so: a exportacao, a
# reposicao e os testes leem daqui. Escritas a mao e nao por
# PRAGMA table_info, de proposito -- uma coluna nova tem de passar por
# uma decisao de a exportar ou nao, e um `SELECT *` fazia essa decisao
# sozinho e ao contrario (mudava a ordem do ficheiro a cada migracao,
# e o B15 promete um ficheiro deterministico).
COLUNAS_DA_PROPOSTA = ("id", "ref", "porque_sem_ref", "lote", "entidade",
                       "titulo", "estado", "motivo", "responsavel",
                       "tipologia", "coe", "preco_base", "valor_proposta",
                       "ebitda", "lugar", "top3", "cv", "proposta_tecnica",
                       "notas", "criada_em", "fechada_em")
COLUNAS_DA_TAREFA = ("id", "proposta_id", "ref", "o_que", "quando", "quem",
                     "feita_em", "origem", "criada_em")
COLUNAS_DO_CONTACTO = ("id", "entidade_chave", "entidade", "nome", "papel",
                       "email", "telefone", "notas", "criado_em")

_TABELAS_TRIAGEM = (
    # Do anuncio ja so sai o que o DR nao refaz: quem e o responsavel, e
    # um estado que nao seja o de origem. A decisao da casa saiu daqui
    # para a `propostas`, que vai inteira (15/09/2026).
    ("anuncios", ("ref", "estado", "visto_em"),
     "SELECT ref, estado, visto_em FROM anuncios "
     "WHERE estado NOT IN ('novo', 'alteracao') ORDER BY ref"),
    # As propostas -- o que a casa decidiu, e a parte mais irrecuperavel
    # de todas: e escrita a mao e nao ha fonte nenhuma que a refaca (o DR
    # nao devolve o preco que se propos). Entram INTEIRAS, colunas todas.
    #
    # Isto e o que faltava ao B15 ate 15/09/2026 e ninguem tinha dado por
    # isso: as doze colunas de CRM que viviam em `anuncios` nunca foram
    # acrescentadas aqui, e o BACKLOG dava o R2 (perda do PC) por fechado
    # por inteiro. Quem acrescentar uma coluna a `propostas` acrescenta-a
    # tambem a esta lista -- ou ela deixa de sair do computador, em
    # silencio e sem nada no ecra a dize-lo.
    ("propostas", COLUNAS_DA_PROPOSTA,
     "SELECT " + ", ".join(COLUNAS_DA_PROPOSTA) + " FROM propostas ORDER BY id"),
    # Os contactos: um nome e um telefone que alguem escreveu, e que
    # fonte nenhuma refaz. A mesma razao das propostas.
    ("contactos", COLUNAS_DO_CONTACTO,
     "SELECT " + ", ".join(COLUNAS_DO_CONTACTO) + " FROM contactos ORDER BY id"),
    ("tarefas", COLUNAS_DA_TAREFA,
     "SELECT " + ", ".join(COLUNAS_DA_TAREFA) + " FROM tarefas ORDER BY id"),
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
    # interrompido a meio nao pode deixar meio ficheiro a fazer de copia.
    # O numero do processo no nome e o que faltava: as 17:00 correm dois
    # (o temporizador do sistema e o relogio de dentro do painel, que
    # nao se veem um ao outro porque a guarda de "uma verificacao de
    # cada vez" e uma variavel na memoria de UM processo). Com um nome
    # so, o segundo a chegar ia mudar o nome a um rascunho que o
    # primeiro ja tinha levado -- e o FileNotFoundError, que e um
    # OSError, saltava o empurrar_triagem() do mesmo try.
    tmp = "%s.%d.tmp" % (caminho, os.getpid())
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
    quieto = {"cwd": pasta, "capture_output": True}

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
            limpa_erro("ultimo_erro_triagem_git")
            return True, "sem mudanças por empurrar"
        feito = corre(["git", "push", "origin", "master"], 180)
        if feito.returncode != 0:
            raise RuntimeError("git push: %s" % porque_do_git(feito))
        limpa_erro("ultimo_erro_triagem_git")
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
                c.execute("UPDATE anuncios SET estado=?, visto_em=? "
                          "WHERE ref=?",
                          (reg["estado"], reg["visto_em"], reg["ref"]))
                escritas += 1
            elif t in ("propostas", "tarefas", "contactos"):
                # A proposta SEM anuncio nao e um orfao: e a consulta
                # previa, o ajuste directo, o convite (D2 do plano). Se
                # levasse a regra das outras tabelas -- "o ref nao esta
                # na base, fica por repor" -- perdia-se no restauro
                # exactamente a parte do pipeline que nao vem do DR, e o
                # relatorio final diria "reposto" na mesma, porque essas
                # linhas nem sequer tem ref para listar. So se adia a que
                # CITA um anuncio que ainda nao voltou.
                colunas = {"propostas": COLUNAS_DA_PROPOSTA,
                           "tarefas": COLUNAS_DA_TAREFA,
                           "contactos": COLUNAS_DO_CONTACTO}[t]
                if reg.get("ref") and reg["ref"] not in existe:
                    por_repor.setdefault(t, []).append(reg["ref"])
                    continue
                c.execute("INSERT OR REPLACE INTO %s (%s) VALUES (%s)"
                          % (t, ", ".join(colunas),
                             ", ".join("?" * len(colunas))),
                          [reg.get(k) for k in colunas])
                escritas += 1
            elif t == "fases":
                # Um triagem.jsonl de antes de 15/09/2026 traz as fases,
                # e a tabela ja nao existe. Ignora-se em silencio de
                # PROPOSITO: rebentar aqui fazia um restauro inteiro
                # falhar por causa de seis linhas que ja nao servem, e
                # e o restauro que existe para os dias maus.
                pass
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
            linhas.append("    " + endereco_do_painel() + "/anuncio/%s"
                          % (quote(a["ref"], safe=""),))
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
                elif x["campo"] == CAMPO_PECA_NOVA:
                    # Nao ha "antes -> depois" numa peca que apareceu:
                    # o antes e vazio, e "-> Errata.pdf" nao se le.
                    linhas.append("    peça nova na plataforma: %s"
                                  % x["depois"])
                else:
                    linhas.append("    %s: %s -> %s"
                                  % (rotulos.get(x["campo"], x["campo"]),
                                     _valor_vigiado(x["campo"], x["antes"]),
                                     _valor_vigiado(x["campo"], x["depois"])))
            linhas.append("    " + endereco_do_painel() + "/anuncio/%s"
                          % (quote(ref, safe=""),))
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
                linhas.append("    " + endereco_do_painel() + "/anuncio/%s"
                              % (quote(a["ref"], safe=""),))
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
_EM_SANS = "system-ui,-apple-system,'Segoe UI',Arial,sans-serif"
_EM_MONO = "Consolas,Menlo,monospace"
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
    return endereco_do_painel() + "/anuncio/%s" % (quote(ref, safe=""),)


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
                elif x["campo"] == CAMPO_PECA_NOVA:
                    itens.append("peça nova na plataforma: <b>%s</b>"
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
        # de antes ia parar ao journal do systemd, onde ninguem olha.
        copia_com_marca(int(cfg.get("copias_a_guardar", 7)))
    # B15: a exportacao da triagem, a seguir a copia -- custa nada e
    # fica sempre fresca no triagem.jsonl. Uma falha aqui nao pode
    # travar a recolha. O commit+push automatico e a sub-decisao do
    # Afonso (31/08/2026: "grava logo la consoante o uso").
    try:
        exportar_triagem()
        # Limpar a marca faz parte de a pôr: sem isto, a falha das
        # 17:00 de 8/09/2026 ficava no painel para sempre, porque
        # `ultima_exportacao_triagem` só se escrevia e nunca se
        # apagava. O empurrar_triagem() já limpava a dele.
        limpa_erro("ultima_exportacao_triagem")
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
    # As tarefas automaticas seguem as datas do DR, e as datas acabaram
    # de ser relidas: uma prorrogacao publicada de manha tem de chegar a
    # vista "Hoje" na mesma verificacao, e nao no dia seguinte. Barato
    # (uma consulta e os que mudaram) e idempotente.
    try:
        sincronizar_tarefas()
    except sqlite3.Error as erro:
        print("aviso: a sincronização das tarefas falhou (%s)" % erro)
    # A lista das pecas dos marcados que tem razao para isso (passou a
    # data de esclarecimentos, ou o prazo/preco mudaram -- e o reler
    # acima e que descobre isso, por isso vem depois dele). Nao depende
    # do DR nem o estraga, e vai antes dos alertas para as pecas novas
    # entrarem no resumo do mesmo dia.
    diz("a ver se apareceram peças novas nos anúncios marcados")
    try:
        n_pecas, _ = vigiar_pecas(int(cfg.get("pecas_vigiadas_por_volta", 10)))
        if n_pecas:
            mensagem += (" · %d peça%s nova%s"
                         % (n_pecas, "" if n_pecas == 1 else "s",
                            "" if n_pecas == 1 else "s"))
    except Exception as erro:
        marca_erro("docs_ultimo_erro", "pecas", "%s · a vigiar peças: %s"
                   % (datetime.now().strftime("%Y-%m-%d %H:%M"),
                      str(erro)[:150]))
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
            else:
                limpa_erro("vortal_ultimo_erro")
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
        # o ponto e o caracter, nao a entidade: a mensagem passa por
        # html.escape() na barra lateral e "&middot;" saia escrito
        mensagem += " · %d para os alertas" % quantos_avisos

    marca("ultima_verificacao", datetime.now().strftime("%Y-%m-%d %H:%M"))
    marca("ultima_mensagem", mensagem)
    marca("ultima_ok", "1" if bem else "0")
    if novos and cfg.get("abrir_browser_ao_encontrar"):
        try:
            webbrowser.open(LOCAL + "/")
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
# Os dois NAO se cruzam em SQL: cada base tem a sua ligacao
# (liga() e liga_corpus()) e o que junta os resultados e Python.
# Havia uma com_corpus() com um ATTACH, documentada em tres sitios
# como se fosse o mecanismo -- nunca chegou a ser chamada, e saiu a
# 03/09/2026. Se um dia fizer falta, esta em `git show 6b8ea69`.
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
    c = sqlite3.connect(CORPUS, timeout=30, factory=Ligacao)
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
        # A lista dos tipos de procedimento enche uma caixa de filtro em
        # /contratos e outra em /alertas, e sem indice era um GROUP BY
        # sobre os 1,99 milhoes: 0,18 s a quente em cada uma das duas
        # paginas. O indice cobre a consulta inteira.
        c.execute("CREATE INDEX IF NOT EXISTS ix_ctr_tipo "
                  "ON contratos(tipo_procedimento)")


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
    para nao prometer historico a quem ainda nao o importou.

    A resposta guarda-se PARA O PEDIDO, no `g` do Flask: a barra, a
    arvore e o corpo de uma pagina chamam isto quatro ou cinco vezes, e
    cada chamada abria a ligacao ao corpus e contava 1,99 milhoes de
    linhas -- 0,025 s a quente cada uma, e numa pen a frio muito mais.
    Dentro do mesmo pedido o corpus nao muda; entre pedidos volta a
    contar-se, para a importacao semanal aparecer no numero sem ninguem
    ter de limpar nada. Fora de um pedido (o `--contratos`, as threads
    de fundo) conta sempre, como antes."""
    if has_request_context() and "n_corpus" in g:
        return g.n_corpus
    quantos = 0
    if os.path.exists(CORPUS):
        try:
            with liga_corpus() as c:
                quantos = c.execute(
                    "SELECT COUNT(*) n FROM contratos").fetchone()["n"]
        except sqlite3.Error:
            quantos = 0
    if has_request_context():
        g.n_corpus = quantos
    return quantos


def primeiro_ano_corpus(omissao=2015):
    """O ano mais antigo que o corpus conhece.

    O painel dizia "desde 2020" escrito a mao. A 03/09/2026 o corpus
    passou a comecar em 2015 e a frase ficou falsa no mesmo dia -- um
    numero que um ecra mostra tem de sair dos dados, nao do teclado.
    Ha indice em `ano` (ix_ctr_ano), portanto o MIN e imediato.

    A omissao e 2015 e nao 2012: o conjunto do dados.gov anuncia zips
    de 2012, 2013 e 2014, mas os tres tem zero bytes -- medido a
    03/09/2026, e o importador trouxe "0 contratos em 0 s" nos tres.
    """
    if not os.path.exists(CORPUS):
        return omissao
    try:
        with liga_corpus() as c:
            r = c.execute("SELECT MIN(ano) a FROM contratos").fetchone()
        return (r and r["a"]) or omissao
    except sqlite3.Error:
        return omissao


_TIPOS_DO_CORPUS = (None, [])


def tipos_de_procedimento():
    """Os tipos de procedimento que o corpus conhece, do mais comum para
    o menos, para as caixas de filtro de /contratos e de /alertas.

    Estava escrito duas vezes, e as duas custava 0,17 s: agrupar 1,99
    milhoes de linhas por uma coluna de texto e trabalho de CPU que o
    indice `ix_ctr_tipo` cobre mas nao evita. E uma lista de uma duzia
    de nomes que so muda quando a importacao semanal corre, portanto
    guarda-se em memoria.

    A chave da cache e a IDENTIDADE DO FICHEIRO -- data e tamanho, do
    corpus e do `-wal` ao lado. Nao e um prazo de validade: um prazo
    mostrava numeros velhos durante N minutos depois de uma importacao,
    e a importacao e justamente a unica coisa que mexe nisto. Dois
    `stat` custam microssegundos, mesmo na pen."""
    global _TIPOS_DO_CORPUS
    if not os.path.exists(CORPUS):
        return []
    marca = []
    for f in (CORPUS, CORPUS + "-wal"):
        try:
            e = os.stat(f)
            marca.append((f, e.st_mtime_ns, e.st_size))
        except OSError:
            marca.append((f, 0, 0))
    marca = tuple(marca)
    if _TIPOS_DO_CORPUS[0] == marca:
        return _TIPOS_DO_CORPUS[1]
    try:
        with liga_corpus() as c:
            tipos = [r["p"] for r in c.execute(
                "SELECT tipo_procedimento p, COUNT(*) n FROM contratos "
                "WHERE tipo_procedimento!='' GROUP BY p ORDER BY n DESC")]
    except sqlite3.Error:
        return []
    _TIPOS_DO_CORPUS = (marca, tipos)
    return tipos


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

    # A mesma traducao da condicoes(), da banda `comum`. Aqui a `norma`
    # importa: os nomes de entidade procuram-se com norma_entidade e nao
    # com simplifica -- e ela que enche adjudicante_norm e nome_norm.
    frag_texto = frag_de_texto

    def procura(texto, coluna, norma=simplifica):
        frag, vals = frag_de_texto(texto, coluna, norma)
        if frag:
            onde.append(frag)
            valores.extend(vals)

    def exclui(texto, coluna, norma=simplifica):
        frag, vals = frag_de_exclusao(texto, coluna, norma)
        if frag:
            valores.extend(vals)
            onde.append(frag)

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
    # Com a chave (entid/vencid, escolhida na sugestao) o texto do nome
    # fica so para mostrar (14/09/2026): com ele tambem, prendia-se a
    # uma grafia so -- a mesma regra do NIF nos anuncios.
    if not (args.get("entid") or "").strip():
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
    if ganhou and (args.get("vencid") or "").strip():
        ganhou = []                      # a chave manda; o nome e so texto
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

# O trinco ENTRE processos (14/09/2026, o P0 do BACKLOG). O dicionario
# acima vale dentro de um processo; o temporizador do systemd arranca
# outro (`--uma-vez`), que nao ve o relogio do painel -- e a 8/09, as
# 17:00, correram os dois sobre a mesma base. Este vive na tabela
# `estado`, que os dois leem: uma linha com o pid e a hora de arranque,
# tomada numa transaccao IMMEDIATE (quem chega segundo espera pelo
# busy_timeout e ve a linha do primeiro). Um trinco de um processo
# morto nao prende ninguem: ou o pid ja nao existe, ou passou o prazo.
TRINCO_VERIFICACAO = "verificacao_em_curso"
HORAS_DE_TRINCO = 3


def processo_vivo(pid):
    """True se o processo existe. (Isto so vale em POSIX: no Windows um
    os.kill(pid, 0) MATA o processo, e enquanto o radar la correu
    valia so o prazo.)"""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _le_trinco(c):
    linha = c.execute("SELECT valor FROM estado WHERE chave=?",
                      (TRINCO_VERIFICACAO,)).fetchone()
    if not linha:
        return None, None
    try:
        dono, desde = linha[0].split("|", 1)
        return int(dono), datetime.strptime(desde, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None, None


def tomar_trinco(agora=None, pid=None, vivo=None):
    """(tomou, porque). O `agora`, o `pid` e o `vivo` sao injectaveis
    para os testes fazerem o segundo processo sem o arrancar."""
    agora = agora or datetime.now()
    pid = pid or os.getpid()
    vivo = vivo or processo_vivo
    c = liga()
    try:
        c.execute("BEGIN IMMEDIATE")
        dono, desde = _le_trinco(c)
        if dono is not None and dono != pid and vivo(dono) \
                and agora - desde < timedelta(hours=HORAS_DE_TRINCO):
            c.rollback()
            return False, ("já está a verificar noutro processo (pid %d, "
                           "desde as %s)" % (dono, desde.strftime("%H:%M")))
        c.execute("INSERT OR REPLACE INTO estado VALUES (?,?)",
                  (TRINCO_VERIFICACAO,
                   "%d|%s" % (pid, agora.strftime("%Y-%m-%d %H:%M:%S"))))
        c.commit()
        return True, ""
    finally:
        c.close()


def largar_trinco(pid=None):
    """So o dono larga: um processo que perdeu o trinco por prazo nao
    pode apagar o do que o tomou a seguir."""
    pid = pid or os.getpid()
    with liga() as c:
        dono, _ = _le_trinco(c)
        if dono == pid:
            c.execute("DELETE FROM estado WHERE chave=?", (TRINCO_VERIFICACAO,))


def verificacao_noutro_processo(agora=None, vivo=None):
    """A hora desde que outro processo esta a verificar, ou "". E o que
    o painel mostra quando o temporizador esta a correr a esta hora."""
    agora = agora or datetime.now()
    vivo = vivo or processo_vivo
    try:
        with liga() as c:
            dono, desde = _le_trinco(c)
    except sqlite3.OperationalError:
        return ""
    if dono is None or dono == os.getpid() or not vivo(dono) \
            or agora - desde >= timedelta(hours=HORAS_DE_TRINCO):
        return ""
    return desde.strftime("%H:%M")


def verificacao_a_correr():
    """O passo em que vai, ou "" se nao estiver a correr -- aqui ou
    noutro processo (o `--uma-vez` do temporizador)."""
    if _VERIFICACAO["a_correr"]:
        return _VERIFICACAO["passo"]
    desde = verificacao_noutro_processo()
    return ("noutro processo, desde as %s" % desde) if desde else ""


def comecar_verificacao(slot=None):
    """Arranca a verificacao numa thread. (arrancou, porque).

    O `slot` e o par (dia, hora) quando quem pede e o relogio: e o que
    marca a hora como corrida, no fim e so se correu bem. O botao do
    painel nao passa nada -- um clique a mao nao e um slot.
    """
    with _VERIFICACAO_TRINCO:
        if _VERIFICACAO["a_correr"]:
            return False, "já está a verificar — %s" % _VERIFICACAO["passo"]
        tomou, porque = tomar_trinco()
        if not tomou:
            return False, porque
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
            largar_trinco()

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
# Atras de um tunel ou de um Caddy, o IP e o esquema (https) vem em
# cabecalhos X-Forwarded-*: sem isto todos os visitantes eram 127.0.0.1
# -- o que abria o acesso livre local a quem viesse pelo tunel -- e o
# cookie da sessao nunca levava `Secure`. Um so salto de confianca.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# Tecto de um pedido (auditoria de 14/09/2026): o Excel do registo da
# casa e a colagem das capturas eram os unicos corpos grandes e nao
# tinham limite nenhum -- um POST de gigabytes enchia o disco antes de
# alguem o ler. 20 MB chega para o modelo preenchido com folga.
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

# Os cabecalhos de seguranca, em todas as respostas (auditoria de
# 14/09/2026). Nao havia nenhum. O CSP e o que o painel aguenta: os
# scripts e os estilos sao em linha (unsafe-inline), a letra vem do
# Google Fonts, o <embed> das pecas e do proprio sitio (object-src), e
# ninguem de fora pode meter o painel numa moldura nem mandar um
# formulario dele para outro sitio. O HSTS so por HTTPS, que e o que o
# tunel da: em 127.0.0.1 nao faz sentido e prendia o browser ao https.
CABECALHOS_DE_SEGURANCA = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "font-src 'self'; img-src 'self' data:; "
        "object-src 'self'; frame-ancestors 'self'; form-action 'self'; "
        "base-uri 'self'; connect-src 'self'"),
}


@app.after_request
def cabecalhos_de_seguranca(resposta):
    for nome, valor in CABECALHOS_DE_SEGURANCA.items():
        resposta.headers.setdefault(nome, valor)
    if request.is_secure:
        resposta.headers.setdefault("Strict-Transport-Security",
                                    "max-age=15552000")
    return resposta


def volta_ao_referer(omissao):
    """Redirecciona para a pagina de onde o formulario veio, se for
    desta aplicacao; senao para `omissao`. Um Referer e um cabecalho
    como outro qualquer, e devolve-lo cru era um redireccionamento
    aberto (auditoria de 14/09/2026)."""
    vindo = request.referrer or ""
    partes = urlparse(vindo)
    if partes.scheme in ("http", "https") and partes.netloc and \
            nome_de_anfitriao(partes.hostname) == nome_de_anfitriao(
                (request.host or "").split(":")[0]):
        caminho = partes.path or "/"
        if partes.query:
            caminho += "?" + partes.query
        return redirect(destino_seguro(caminho))
    return redirect(omissao)


# --- a porta: sessoes e login (docs/historico/ONLINE.md, etapa 1)
#
# Tudo o que nao seja /entrar exige sessao -- ou um pedido local com
# "acesso_livre_local" ligado. A sessao e um cookie `sessao` com um
# token que a tabela `sessoes` conhece; nao ha secret_key do Flask nem
# cookie assinado, e "sair" apaga a linha e invalida de imediato.

# /saude: a rota do vigilante de fora. /tipo: os ficheiros das fontes,
# que a propria pagina de entrar precisa de carregar antes de haver
# sessao -- sao fontes de licenca aberta, e a lista branca em TIPOS e o
# que impede que "/tipo/<nome>" chegue a outro ficheiro qualquer.
ROTAS_ABERTAS = ("/entrar", "/saude", "/tipo")
LOOPBACK = ("127.0.0.1", "::1")

# O que so o admin abre (13/09/2026, "Mudancas na plataforma RADAR"):
# as seccoes do sistema, os indicadores, o "Verificar agora" e a gestao
# das contas. Por prefixo, para os POST de cada seccao entrarem com o
# GET. Um tester que la bata leva 403 -- nao um redirect para o login,
# que ele ja fez.
ROTAS_SO_ADMIN = ("/indicadores", "/configuracoes/indicadores",
                  "/configuracoes/recolha", "/configuracoes/leitura",
                  "/configuracoes/capturas", "/configuracoes/copias",
                  "/configuracoes/conta/utilizadores", "/verificar",
                  "/alertas/remetente")


def sou_admin():
    """No acesso livre local sem conta nenhuma tambem e admin: e o
    computador do Afonso antes de haver contas, e sem isto nem se
    chegava a Conta para as criar."""
    if not has_request_context():
        return True
    utilizador = g.get("utilizador")
    if not utilizador:
        return bool(g.get("livre"))
    return contas.e_admin(utilizador)


def so_admin(caminho):
    return any(caminho == r or caminho.startswith(r + "/")
               for r in ROTAS_SO_ADMIN)


def pedido_e_local():
    """True se o pedido vem deste computador e NAO passou por um tunel.

    O cloudflared liga-se ao painel a partir de 127.0.0.1: so pelo IP,
    todos os visitantes do tunel eram locais. Por isso conta tambem o
    que o tunel acrescenta -- os cabecalhos de proxy e o Host publico
    -- e qualquer um deles chega para o pedido deixar de ser local.
    """
    if request.remote_addr not in LOOPBACK:
        return False
    for cabecalho in ("X-Forwarded-For", "Cf-Connecting-Ip", "X-Real-Ip",
                      "X-Forwarded-Host"):
        if request.headers.get(cabecalho):
            return False
    anfitriao = (request.host or "").lower()
    if anfitriao.startswith("[::1]"):
        return True
    return anfitriao.split(":")[0] in ("127.0.0.1", "localhost", "")


def origem_e_nossa():
    """Para um POST sem sessao (acesso livre): se o browser disser de
    onde vem, tem de ser daqui. Um pedido sem Origin nem Referer passa
    -- e o caso dos testes e do curl, e nao ha sessao para roubar."""
    origem = request.headers.get("Origin") or request.headers.get("Referer")
    if not origem:
        return True
    # So o nome, sem a porta, e os tres nomes do loopback contam como
    # um: o browser pode ter 127.0.0.1 nos favoritos e o Referer vir com
    # localhost, e a porta ja e a mesma por definicao.
    return (nome_de_anfitriao(urlparse(origem).hostname or "")
            == nome_de_anfitriao((request.host or "").split(":")[0]))


def nome_de_anfitriao(nome):
    nome = (nome or "").lower().strip("[]")
    return "127.0.0.1" if nome in ("localhost", "::1", "127.0.0.1") else nome


@app.before_request
def porta_de_entrada():
    g.sessao = None
    g.utilizador = None
    g.livre = False
    token = request.cookies.get("sessao")
    # Uma base que ainda nao passou pelo iniciar_db() -- os testes que
    # usam o cliente sem base propria -- nao tem as tabelas das contas;
    # isso e "sem sessao", nao um 500 em todas as paginas.
    # A ligacao fecha-se aqui a mao: isto corre em TODOS os pedidos, e
    # o `with liga()` so faz commit -- deixava uma ligacao por pedido a
    # espera do gc (os testes contavam-nas, de 327 avisos para 719).
    # E o liga() fica dentro do try (15/09/2026): com a base indisponivel
    # tudo dava 500 aqui, incluindo o /saude, que existe para dizer 503.
    c = None
    try:
        c = liga()
        if token:
            g.utilizador = contas.utilizador_da_sessao(c, token)
            c.commit()
            if g.utilizador:
                g.sessao = token
        if not g.utilizador and ler_config().get("acesso_livre_local", True) \
                and pedido_e_local():
            g.livre = True
            g.utilizador = contas.unico_utilizador(c)   # None ate haver conta
    except sqlite3.OperationalError:
        g.sessao = None
        if not g.livre and ler_config().get("acesso_livre_local", True) \
                and pedido_e_local():
            g.livre = True
    finally:
        if c is not None:
            c.close()
    # As fontes sao "/tipo/<nome>", e por isso esta e por prefixo e nao
    # por igualdade -- a lista branca de TIPOS e que fecha a porta la,
    # nao esta linha.
    if request.path in ROTAS_ABERTAS or request.path.startswith("/tipo/"):
        return None
    if not g.utilizador and not g.livre:
        if request.method == "GET":
            para = request.full_path.rstrip("?")
            return redirect("/entrar?para=" + quote(para, safe=""))
        return Response("sessão em falta", 403, mimetype="text/plain")
    if so_admin(request.path) and not sou_admin():
        return Response("só o admin abre isto", 403, mimetype="text/plain")
    if request.method == "POST":
        if g.sessao:
            apresentado = (request.form.get("csrf")
                           or request.headers.get("X-CSRF"))
            if not contas.csrf_bate(g.sessao, apresentado):
                return Response("pedido recusado: falta o token da sessão "
                                "(recarrega a página e volta a tentar)",
                                403, mimetype="text/plain")
        elif not origem_e_nossa():
            return Response("pedido recusado: vem de outro sítio", 403,
                            mimetype="text/plain")
    return None


# ------------------------------------------- os erros, e a saude
#
# 15/09/2026, da lista «20 coisas a proteger antes de um site vibecoded
# ir para o publico»: das vinte, tres faltavam mesmo -- uma pagina de
# erro propria, uma rota de saude para alguem de fora vigiar, e um
# ensaio de restauro da copia (esse esta em baixo, ao pe das copias).
#
# A pagina de erro e fora do BASE de proposito: o BASE le a sessao e a
# barra, e um 500 a meio disso dava outro 500 em cima do primeiro. E o
# molde do /entrar, com um titulo e uma linha.

PAGINA_ERRO = """<!doctype html><html lang="pt" data-pele="novo" data-tipo="plex"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(titulo)s — RadarGov</title><style>%(css)s</style></head>
<body class="entrar-fundo"><main class="entrar">
 <div class="logo">Radar<span>Gov</span></div>
 <h1>%(titulo)s</h1>
 <p class="nota">%(texto)s</p>
 <p><a class="bt primario" href="/">Voltar aos anúncios</a></p>
</main></body></html>"""

ERROS_DO_PAINEL = {
    403: ("Não é para aqui", "Esta página é só do admin, ou o pedido veio "
                              "de outro sítio."),
    404: ("Não há nada aqui", "A ligação está errada ou a página deixou "
                              "de existir."),
    500: ("Correu mal", "O painel deu um erro. Ficou registado nos "
                        "Indicadores; se voltar a acontecer, diz."),
}


def pagina_de_erro(codigo):
    titulo, texto = ERROS_DO_PAINEL.get(codigo, ERROS_DO_PAINEL[500])
    return Response(PAGINA_ERRO % {"css": CSS_TUDO, "titulo": titulo,
                                   "texto": texto},
                    codigo, mimetype="text/html")


@app.errorhandler(404)
def nao_encontrado(_erro):
    return pagina_de_erro(404)


@app.errorhandler(403)
def recusado(_erro):
    # So os abort(403): as recusas da porta continuam em texto, porque
    # um POST de formulario ou de fetch quer a frase, nao um ecra.
    return pagina_de_erro(403)


@app.errorhandler(500)
def rebentou(_erro):
    """Um 500 mostrava a pagina nua do Werkzeug e nao ficava em lado
    nenhum: o Afonso via «Internal Server Error» e ninguem mais sabia.
    Passa a marca `painel_ultimo_erro` (a saude dos Indicadores le-a)
    mais a linha na serie, e uma pagina da casa. O registo nunca pode
    derrubar a resposta: se a base e que esta mal, fica so a pagina."""
    causa = getattr(_erro, "original_exception", None) or _erro
    try:
        marca_erro("painel_ultimo_erro", "painel",
                   "%s em %s %s: %s" % (datetime.now().strftime("%Y-%m-%d %H:%M"),
                                        request.method, request.path[:80],
                                        ("%s: %s" % (type(causa).__name__, causa))[:200]))
    except Exception:
        pass
    return pagina_de_erro(500)


@app.route("/saude")
def saude():
    """Para um vigilante de fora (o UptimeRobot, ou o que for) bater de
    cinco em cinco minutos: sem sessao, e sem dizer nada de dentro. So
    «ok» se a base abre e responde, 503 se nao -- e o que um monitor
    de disponibilidade sabe ler. Esta em ROTAS_ABERTAS porque um ping
    que caia no /entrar dava sempre 200, e o monitor nunca veria o
    painel cair de facto."""
    try:
        c = liga()
        try:
            c.execute("SELECT 1 FROM estado LIMIT 1").fetchall()
        finally:
            c.close()
    except sqlite3.Error:
        return Response("base indisponível", 503, mimetype="text/plain")
    return Response("ok", 200, mimetype="text/plain",
                    headers={"Cache-Control": "no-store"})


def csrf_da_pagina():
    """O token que os formularios desta pagina levam. Vazio no acesso
    livre: sem sessao nao ha de que o derivar, e a guarda e a origem."""
    return contas.token_csrf(g.sessao) if g.get("sessao") else ""


def com_csrf(pagina):
    """Poe o campo escondido em TODOS os <form method=post> da pagina.

    Sao 26 formularios e ha-de haver mais; um helper a chamar em cada
    um era um formulario novo esquecido e uma accao a dar 403. Aqui e
    um so sitio, e o teste que percorre o app.url_map garante a outra
    metade: que o servidor recusa sem o campo.
    """
    token = csrf_da_pagina()
    if not token:
        return pagina
    campo = "<input type='hidden' name='csrf' value='%s'>" % token
    return re.sub(r"(<form\b[^>]*\bmethod=['\"]post['\"][^>]*>)",
                  lambda m: m.group(1) + campo, pagina, flags=re.I)


def destino_seguro(para):
    """So um caminho desta aplicacao: nada de //outro.site nem http://."""
    para = (para or "").strip()
    if para.startswith("/") and not para.startswith("//") and "\\" not in para:
        return para
    return "/"


PAGINA_ENTRAR = """<!doctype html><html lang="pt" data-pele="novo" data-tipo="plex"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Entrar — RadarGov</title><style>%(css)s</style></head>
<body class="entrar-fundo"><main class="entrar">
 <div class="logo">Radar<span>Gov</span></div>
 <h1>Entrar</h1>
 %(aviso)s
 <form method="post" action="/entrar">
  <input type="hidden" name="para" value="%(para)s">
  <label>Utilizador<input type="text" name="email" value="%(email)s" autocomplete="username" autocapitalize="off" required autofocus></label>
  <label>Palavra-passe<input type="password" name="senha" autocomplete="current-password" required></label>
  <button type="submit" class="bt primario">Entrar</button>
 </form>
</main></body></html>"""


def pagina_entrar(aviso="", email="", para="/", codigo=200):
    return Response(PAGINA_ENTRAR % {
        "css": CSS_TUDO,
        "aviso": ("<div class='flash mau'>%s</div>" % html.escape(aviso)
                  if aviso else ""),
        "email": html.escape(email, quote=True),
        "para": html.escape(destino_seguro(para), quote=True),
    }, codigo, mimetype="text/html")


@app.route("/entrar", methods=["GET", "POST"])
def entrar():
    """Um ecra, uma tarefa: e-mail, palavra-passe, Entrar."""
    if g.get("utilizador") and g.get("sessao"):
        return redirect(destino_seguro(request.values.get("para")))
    with liga() as c:
        ha_contas = bool(contas.utilizadores(c))
    if not ha_contas:
        return pagina_entrar(
            "Ainda não há nenhuma conta. Na pasta do radar, corre "
            "python radar.py --criar-utilizador NOME e volta aqui.",
            para=request.values.get("para"))
    if request.method == "GET":
        return pagina_entrar(para=request.args.get("para"))
    if not origem_e_nossa():
        return pagina_entrar("O pedido veio de outro sítio.", codigo=403)
    email = request.form.get("email") or ""
    with liga() as c:
        token, resultado = contas.entrar(
            c, email, request.form.get("senha") or "",
            ip=request.remote_addr or "",
            agente=request.headers.get("User-Agent") or "")
    if not token:
        marca_erro("login", "login", "falhou para %s de %s: %s"
                   % (contas.email_limpo(email)[:60], request.remote_addr,
                      resultado))
        return pagina_entrar(resultado, email=email,
                             para=request.form.get("para"),
                             codigo=429 if "espera" in resultado else 200)
    registar("", "entrou", request.remote_addr or "", quem=resultado["nome"])
    resposta = redirect(destino_seguro(request.form.get("para")))
    resposta.set_cookie("sessao", token,
                        max_age=60 * 60 * 24 * contas.DIAS_DE_SESSAO,
                        httponly=True, samesite="Lax",
                        secure=request.is_secure)
    return resposta


@app.route("/sair", methods=["POST"])
def sair():
    if g.get("sessao"):
        with liga() as c:
            contas.sair(c, g.sessao)
    resposta = redirect("/entrar")
    resposta.delete_cookie("sessao")
    return resposta


@app.route("/sair-de-todos", methods=["POST"])
def sair_de_todos():
    n = 0
    if g.get("sessao") and g.get("utilizador"):
        with liga() as c:
            n = contas.sair_de_todos(c, g.utilizador["id"])
        registar("", "saiu de todos os aparelhos", "%d sessões" % n,
                 quem=g.utilizador.get("nome"))
    resposta = redirect("/entrar")
    resposta.delete_cookie("sessao")
    return resposta


def bloco_da_conta():
    """O canto da barra lateral que era o campo "quem esta a trabalhar?".

    Com sessao: o nome e o "sair". No acesso livre local: o nome do
    unico utilizador, ou a nota de que ainda nao ha conta -- sem
    formulario, porque nao ha nada para sair.
    """
    utilizador = g.get("utilizador") or {}
    nome = utilizador.get("nome") or ""
    if g.get("sessao"):
        return ("<details class='sou'><summary><span class='av'>%s</span>%s"
                "</summary><div class='sou-menu'>"
                "<a class='sou-conta' href='/configuracoes/conta'>a conta</a>"
                "<form method='post' action='/sair'>"
                "<button type='submit'>sair</button></form>"
                "<form method='post' action='/sair-de-todos'>"
                "<button type='submit'>sair de todos os aparelhos</button>"
                "</form></div></details>"
                % (_iniciais(nome), html.escape(nome)))
    if nome:
        return ("<div class='sou'><div class='so-nome'><span class='av'>%s"
                "</span>%s</div></div>" % (_iniciais(nome), html.escape(nome)))
    return ("<div class='sou'><div class='so-nome'><span class='av'>&mdash;"
            "</span>sem conta ainda</div></div>")


def arranque_permitido(cfg, endereco):
    """(True, '') se o painel pode arrancar neste endereco; senao a
    razao. A guarda contra por o servidor de pe com a porta aberta por
    engano: o acesso livre local so faz sentido a ouvir no localhost."""
    if cfg.get("acesso_livre_local", True) and endereco not in LOOPBACK \
            and endereco != "localhost":
        return False, ("acesso_livre_local está ligado no config.json e o "
                       "painel ia ouvir em %s: qualquer pedido de fora entrava "
                       "sem login. Põe \"acesso_livre_local\": false, ou ouve "
                       "só em 127.0.0.1." % endereco)
    return True, ""


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
 /* o "Gov" do logotipo: azul, a pedido dele (14/09/2026); sobre a barra
    escura o --azul nao se le, por isso ha um claro so para la */
 --azul-claro:#7cbcf0;
 --sans:system-ui,-apple-system,'Segoe UI',sans-serif;
 --mono:ui-monospace,Consolas,monospace;
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
.barra :focus-visible{outline-color:var(--coral)}
body{margin:0;background:var(--papel);font-family:var(--sans);color:var(--t1);
 -webkit-font-smoothing:antialiased}
a{color:var(--azul);text-decoration:none}
a:hover{color:var(--ink)}
::-webkit-scrollbar{width:10px;height:10px}
::-webkit-scrollbar-thumb{background:var(--traco);border-radius:6px}
.app{display:flex;flex-direction:column;min-height:100vh}

/* A barra, em cima (13/09/2026, "Mudancas na plataforma RADAR"). Foi
   lateral de 140px ate aqui; o que la vivia alem da navegacao -- as
   fontes, as contagens, o endereco, a hora da ultima verificacao -- saiu
   do ecra: as contagens estao nos Indicadores e a ultima verificacao
   tambem. Fica a marca, os tres itens, Configuracoes e quem esta. E a
   mesma barra em todos os tamanhos: o que era o bloco do telemovel
   passou a ser a regra. */
.barra{display:flex;flex-direction:row;flex-wrap:wrap;align-items:center;
 gap:6px 14px;padding:10px 20px;background:var(--ink);color:#fff;
 position:sticky;top:0;z-index:20;box-sizing:border-box}
.marca{flex:none}
.marca .logo{font:700 15px/1 var(--sans);letter-spacing:-.3px;color:#fff}
.marca .logo span{color:var(--azul-claro)}
.barra nav{display:flex;flex-direction:row;flex-wrap:nowrap;gap:2px;margin:0 0 0 8px;
 overflow-x:auto;scrollbar-width:none;min-width:0}
.barra nav a{display:block;padding:7px 9px;border-radius:5px;white-space:nowrap;flex:none;
 color:var(--barra-t2);font:500 12.5px/1.25 var(--sans)}
.barra nav a:hover{background:var(--barra-on);color:#fff}
.barra nav a.on{background:var(--barra-on);color:#fff}
.barra nav a b{font:inherit;font-weight:600}
/* as duas vistas de um item aberto (Em curso, Mercado) */
.barra nav a.sub{padding:7px 9px}
.barra nav a.sub b{font-weight:400;font-size:12px}
.barra nav a.sub.on b{font-weight:600}
.caixa{display:flex;align-items:center;gap:10px;margin-left:auto}
.caixa a.conf{padding:7px 9px;border-radius:5px;font:500 12.5px/1.25 var(--sans);
 color:var(--barra-t2)}
.caixa a.conf:hover{background:var(--barra-on);color:#fff}
.caixa a.conf.on{background:var(--barra-on);color:#fff}
/* Quem esta. Fechado por omissao; aberto, o menu cai por baixo da barra
   em vez de a esticar. */
.sou{flex:none;position:relative}
.sou > summary{display:flex;align-items:center;gap:7px;cursor:pointer;
 list-style:none;color:var(--barra-t3);font:500 10.5px/1.3 var(--sans);
 padding:4px 0;min-height:24px;box-sizing:border-box}
.sou > summary::-webkit-details-marker{display:none}
.sou > summary:hover{color:#fff}
.sou .sou-menu{position:absolute;right:0;top:100%;margin-top:6px;background:var(--ink);
 border:1px solid var(--barra-linha);border-radius:7px;padding:8px 12px;
 display:flex;flex-direction:column;gap:4px;min-width:190px;z-index:30}
.sou form{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
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
.sou .sou-menu a{color:var(--barra-t2);font:400 10.5px/1.2 var(--sans);padding:6px 5px;
 margin:-6px 0;min-height:24px;box-sizing:border-box;display:inline-block}
.sou .sou-menu a:hover{color:#fff}
.sou .so-nome{display:flex;align-items:center;gap:7px;color:var(--barra-t3);
 font:500 10.5px/1.3 var(--sans)}
/* O ecra de entrar: uma tarefa, sem barra lateral. */
.entrar-fundo{display:flex;align-items:center;justify-content:center;min-height:100vh}
.entrar{flex:none;display:block;width:min(360px,92vw);background:var(--creme);border:1px solid var(--linha);
 border-radius:12px;padding:28px 28px 24px}
.entrar .logo{font:700 15px/1 var(--sans);color:var(--ink);letter-spacing:.02em}
.entrar .logo span{color:var(--azul)}
.entrar h1{font:600 20px/1.2 var(--sans);margin:18px 0 14px}
.entrar label{display:block;font:500 11.5px/1.4 var(--sans);color:var(--t3);margin:0 0 12px}
.entrar input{display:block;width:100%;margin-top:4px;padding:9px 10px;border:1px solid var(--linha);
 border-radius:7px;font:400 14px/1.3 var(--sans);color:var(--t1);background:#fff}
.entrar input:focus{border-color:var(--azul)}
.entrar .bt{width:100%;margin-top:6px;min-height:36px}
.entrar .flash{margin:0 0 14px}

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
/* A escada (15/09/2026): dez ranhuras mais o "todos" nao cabem numa
   linha de tabuladores como as quatro abas de antes. Rolam na
   horizontal, e as tres naturezas distinguem-se -- as duas pontas (a
   entrada e o cemiterio) e o "todos" nao sao estados da casa, e pinta-
   las como as oito dizia que ha dez estados quando ha dez coisas de
   tres naturezas. O separador vertical entre a entrada e as oito e
   onde a escada da casa comeca. */
/* Onze abas -- dez ranhuras mais o "Todos" -- nao cabem numa linha num
   ecra normal, e rolar de lado com a barra de rolamento a vista era a
   coisa mais feia do ecra (palavra dele). Passam a QUEBRAR: a fila
   continua, mais abaixo, e nao ha nada a esconder-se. O tipo desce de
   12,5 para 11,5 px e o espaco aperta, que e o que faz caber uma linha
   so na maior parte dos ecras -- em 900 px vao a duas, e e essa a
   intencao.
   A nota da UX-Auditoria mantem-se: o alvo continua acima de 24 px de
   altura, que e o que a regra da casa exige. */
.abas-escada{flex-wrap:wrap;row-gap:0;padding-bottom:1px}
.abas-escada a{white-space:nowrap;flex:0 0 auto;padding:8px 10px;
 font-size:11.5px}
.abas-escada a.ponta{color:var(--t5)}
.abas-escada a.ponta:hover{color:var(--t2)}
.abas-escada a.entrada{border-right:1px solid var(--linha);
 border-radius:7px 0 0 0;margin-right:6px;padding-right:16px}
.abas-escada a.entrada.on{border-right-color:var(--linha)}
.abas-escada a.cemiterio{margin-left:6px}
/* As quatro fechadas (ganho, perdido, nao fomos, cancelado) sao o
   arquivo: ja nao pedem accao, e uma escada que as pinte com o mesmo
   peso das abertas poe o fim ao lado do que esta a acontecer. */
.abas-escada a.fechada{color:var(--t5)}
.abas-escada a.fechada.on{color:var(--ink)}
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
/* a arvore por cima dos campos (14/09/2026): a caixa dos filtros
   encosta-se a ela */
.painel-filtros details.arvore{margin-bottom:10px}
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

/* A lista das propostas (era a do "Em curso", que se fundiu na escada a
   15/09/2026). O `min-width` de 1400 px era para as treze colunas de
   entao; hoje sao nove, e um minimo dessa largura punha a rolar de lado
   uma tabela que cabe.
   E saiu o `.tab-lista td form{display:contents}`: existia para um
   `<form>` poder envolver celulas, que e coisa que o HTML nao deixa --
   e com os formularios por linha fora, o que ele fazia era derrotar o
   `display:flex` do selector de ranhura, que ficava espremido a mostrar
   "A pr" onde diz "A preparar proposta". Visto no ecra nessa noite. */
.tab-lista{min-width:900px}
.tab-lista td.o{max-width:280px}
.tab-lista td.curta{width:96px}
.tab-lista td.d.esclarec{color:var(--t3)}

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
/* O somario do desfecho: os numeros que fecham o funil (contratado,
   quem ganhou, quanto abaixo da base) lidos de relance, antes da
   tabela dos lotes. Envolve em vez de cortar -- ha adjudicatarios com
   nomes de setenta caracteres, e um agrupamento de tres nao cabe. */
.desfecho-som{display:flex;flex-wrap:wrap;gap:14px 30px;
 padding:12px 14px;background:var(--creme);border:1px solid var(--linha2);
 border-radius:6px}
.desfecho-som>div{display:flex;flex-direction:column;gap:4px;min-width:110px}
.desfecho-som b{font:600 15px/1.35 var(--sans);color:var(--ink)}
.desfecho-som b a{color:var(--azul)}
.desfecho-som span{font:400 11px/1 var(--sans);color:var(--t4);
 text-transform:uppercase;letter-spacing:.06em}
.desfecho-som b span{text-transform:none;letter-spacing:0}
.guardados{display:flex;align-items:center;gap:8px;flex-wrap:wrap;
 padding:10px 14px;margin-bottom:8px;background:var(--creme);box-shadow:none}
.guardados .rot{margin-right:4px}
.guardados .nada{font:400 12px/1 var(--sans);color:var(--t6)}
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
.linha-conta .teclas{font:500 11px/1 var(--mono);color:var(--t5);
 border:1px solid var(--linha);border-radius:4px;padding:3px 6px;cursor:help}
/* O anuncio focado pelo teclado (j/k). So o teclado o poe: o rato
   continua a ler sem contornos. */
.item.foco{border-color:var(--azul);box-shadow:0 0 0 2px var(--azul-borda)}
/* Os tres blocos de filtro dentro de um <details>, recolhidos por
   omissao. A summary tem o resumo do filtro em uso; o resto vive
   igual la dentro. */
details.painel-filtros{margin-bottom:10px}
details.painel-filtros>summary{cursor:pointer;display:flex;align-items:center;gap:10px;
 list-style:none;padding:9px 12px;background:var(--creme);border:1px solid var(--linha);
 border-radius:8px;min-height:24px}
details.painel-filtros[open]>summary{margin-bottom:8px}
details.painel-filtros>summary::-webkit-details-marker{display:none}
details.painel-filtros>summary::before{content:'\25B8';font:500 11px/1 var(--mono);color:var(--t3)}
details.painel-filtros[open]>summary::before{content:'\25BE'}
details.painel-filtros .pf-tit{font:700 11px/1 var(--sans);color:var(--t2);
 text-transform:uppercase;letter-spacing:.07em}
details.painel-filtros .pf-sub{font:400 12px/1.4 var(--sans);color:var(--t4)}
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
/* O `display` de uma regra ganha ao atributo `hidden`, que vem da
   folha do browser. Desde 15/09/2026 a caixa tem DOIS grupos de
   motivos -- um por estado -- e esconde um deles pelo `hidden`:
   sem esta linha, o dialogo do "Perdido" mostrava tambem os
   quatro motivos do "Nao fomos", oito opcoes para escolher uma.
   Visto no ecra. */
dialog.modal .escolhas[hidden]{display:none}
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
/* Configuracoes: o indice a esquerda, preso ao rolar como o da ficha,
   e a seccao a direita. Cada seccao e uma caixa com um formulario. */
.conf{display:grid;grid-template-columns:200px minmax(0,1fr);gap:22px;align-items:start}
.conf-indice{position:sticky;top:16px;display:flex;flex-direction:column;gap:2px}
.conf-indice a{display:block;padding:8px 10px;border-radius:7px;color:var(--t2);
 min-height:24px}
.conf-indice a b{display:block;font:600 12.5px/1.3 var(--sans)}
.conf-indice a i{display:block;font:400 10.5px/1.3 var(--sans);color:var(--t5);font-style:normal}
.conf-indice a:hover{background:var(--linha2);color:var(--ink)}
.conf-indice a.on{background:#fff;border:1px solid var(--linha);color:var(--ink)}
.conf-cx{padding:18px 22px 22px}
.conf-form{display:flex;flex-direction:column;gap:12px;max-width:560px}
.conf-campo{display:flex;flex-direction:column;gap:4px;font:500 11.5px/1.4 var(--sans);color:var(--t3)}
.conf-campo input[type=text],.conf-campo input[type=password],.conf-campo input[type=email],
.conf-campo select,.conf-form textarea{padding:9px 12px;border:1px solid var(--linha);
 border-radius:7px;font:400 13px/1.3 var(--sans);color:var(--t1);background:#fff}
.conf-campo input:disabled{background:var(--linha2);color:var(--t4)}
.conf-campo small{font:400 11px/1.4 var(--sans);color:var(--t5)}
.conf-check{flex-direction:row;align-items:center;gap:8px;flex-wrap:wrap}
.conf-check input{width:16px;height:16px;margin:0}
.conf-check small{flex-basis:100%}
.conf-form button{align-self:flex-start;margin-top:4px}
.conf-form textarea{font-family:var(--mono);font-size:11.5px;width:100%;max-width:560px}
.conf-forn{margin-top:18px;padding-top:16px;border-top:1px solid var(--linha2)}
.conf-campo input[type=file]{font:400 12.5px/1.3 var(--sans);color:var(--t2)}
.tab-ensaio tr.erro td{background:var(--verm-fundo)}
.tab-ensaio td .mau{color:var(--verm);font-weight:500}
.tab-ensaio td .aviso{color:var(--laranja)}
.tab-ensaio td .ok{color:var(--verde);font-weight:600}
.tab-ensaio td.n{font:500 12px/1.4 var(--mono);white-space:nowrap}
.conf-forn .saude{margin:6px 0 10px}
@media (max-width:1100px){.conf{grid-template-columns:minmax(0,1fr)}.conf-indice{position:static;flex-direction:row;flex-wrap:wrap}}
.em-falta{font-weight:400;color:var(--t6);font-style:italic}
.em-falta-frase{margin:0;padding:12px 22px 16px;border-top:1px solid var(--linha2);
 font:400 12.5px/1.6 var(--sans);color:var(--t4)}
.em-falta-frase b{font-weight:600;color:var(--t3)}
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

/* As etiquetas: viviam no cartão do quadro e, com ele fora, vivem no
   bloco «A nossa proposta» da ficha. */
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
.prop-etq{margin-top:14px;padding-top:12px;border-top:1px dashed var(--traco)}
.prop-etq .rot{margin-bottom:8px}
.prop-etq .etq{display:inline-flex;margin:0 5px 5px 0}
/* a tabela dos lotes, na ficha */
.tab-lotes td.n{font:600 12px/1.4 var(--mono);white-space:nowrap}
.tab-lotes td.s{white-space:nowrap}
.tab-lotes .lote-prop{font:400 11.5px/1.4 var(--sans);color:var(--t4)}

/* o selector de ranhura, na linha da lista e na ficha (15/09/2026).
   Com o quadro fora, é este o controlo que move um concurso na escada:
   oito destinos não cabem em botões, e dois botões de avançar/recuar
   davam vários gestos a qualquer salto -- e saltar é o caso. */
/* Na mesma linha dos botoes e nao por baixo deles: a linha da lista
   ficava com duas alturas, e vinte linhas assim sao um ecra a mais. */
.item-accoes{display:flex;align-items:center;gap:6px;flex-wrap:wrap;
 justify-content:flex-end}
.ranhura{display:flex;align-items:center;gap:4px}
/* A coluna da ranhura tem de caber a palavra mais comprida ("A
   preparar proposta"): numa `td.curta` o select encolhia e mostrava "A
   prep", que nao diz o estado nenhum. Visto no ecra a 15/09/2026. */
td.celula-ranhura{white-space:nowrap;width:1%}
.ranhura select{font:400 11.5px/1.2 var(--sans);padding:5px 7px;
 border:1px solid var(--linha);border-radius:5px;background:#fff;
 color:var(--t2);min-height:24px;box-sizing:border-box}
.ranhura select:hover{border-color:var(--azul)}
/* o botão «ir» é para quem não tem JS: com JS o select grava sozinho ao
   mudar, e um botão a mais em cada uma de vinte linhas é ruído. O
   esconder é feito PELO JS (classe no <html>), e não ao contrário: sem
   JS a folha sozinha tem de o deixar visível. */
.com-js .ranhura button{display:none}

/* o bloco «A nossa proposta» na ficha: a casa do que o cartão fazia */
.prop{border:1px solid var(--linha);border-radius:6px;padding:14px;
 margin-bottom:12px;background:var(--linha2)}
.prop:last-child{margin-bottom:0}
.prop-topo{display:flex;align-items:center;gap:10px;flex-wrap:wrap;
 margin-bottom:12px}
.prop-nome{font:700 13px/1.3 var(--sans);color:var(--ink);flex:1}
.prop-campos{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
 gap:10px;align-items:end}
.prop-campos label{display:flex;flex-direction:column;gap:4px;
 font:600 9.5px/1 var(--sans);color:var(--t4);letter-spacing:.04em;
 text-transform:uppercase}
.prop-campos label.largo{grid-column:1/-1}
.prop-campos input,.prop-campos select{font:400 12px/1.3 var(--sans);
 padding:6px 8px;border:1px solid var(--linha);border-radius:5px;
 background:#fff;color:var(--t2);text-transform:none;letter-spacing:0}
.prop-campos button{cursor:pointer;font:600 11px/1 var(--sans);padding:7px 12px;
 border:1px solid var(--linha);border-radius:5px;background:#fff;color:var(--t3);
 min-height:24px;box-sizing:border-box}
.prop-campos button:hover{border-color:var(--azul);color:var(--azul)}
.prop-accoes{display:flex;gap:6px;flex-wrap:wrap}
/* o que falta fazer, por proposta */
.prop-tarefas{margin-top:14px;padding-top:12px;border-top:1px dashed var(--traco)}
.prop-tarefas .rot{margin-bottom:8px}
ul.tarefas{list-style:none;margin:0 0 10px;padding:0;display:flex;
 flex-direction:column;gap:6px}
ul.tarefas li{display:flex;align-items:center;gap:7px;
 font:400 12px/1.4 var(--sans);color:var(--t2)}
ul.tarefas li .t{flex:1}
button.tq{cursor:pointer;width:24px;min-height:24px;padding:0;flex:none;
 border:1px solid var(--linha);border-radius:4px;background:#fff;
 color:var(--t4);font:600 11px/1 var(--sans);box-sizing:border-box}
button.tq:hover{border-color:var(--verde);color:var(--verde)}
.tarefa-nova{display:flex;gap:6px;flex-wrap:wrap}
.tarefa-nova input[type=text]{flex:1;min-width:140px}
.tarefa-nova input,.tarefa-nova button{font:400 11.5px/1.2 var(--sans);
 padding:6px 8px;border:1px solid var(--linha);border-radius:5px;
 background:#fff;color:var(--t2);min-height:24px;box-sizing:border-box}
.tarefa-nova button{cursor:pointer;font-weight:600;color:var(--t3)}

/* A faixa que propõe fechar uma proposta com o que o Portal BASE diz
   (etapa 4). Cor de informação e não de alarme: é um facto que chegou,
   não um problema -- e o vermelho desta folha é o do prazo expirado. */
.desfecho-propoe{margin-top:14px;padding:12px 14px;border-radius:6px;
 background:var(--azul-fundo);border:1px solid var(--linha)}
.dp-facto{font:400 12px/1.5 var(--sans);color:var(--t2)}
.dp-botoes{display:flex;align-items:center;gap:8px;margin-top:10px;
 flex-wrap:wrap}
.dp-botoes a.bt-leve{margin-left:auto}

/* As barras horizontais dos motivos (etapa 5): são poucas e de nome
   longo, e em pé ficavam com o rótulo de lado a não se ler. */
.lh{display:flex;align-items:center;gap:10px}
.lh .t{flex:0 0 180px;font:400 11.5px/1.3 var(--sans);color:var(--t3);
 text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lh .bh{height:12px;border-radius:3px;background:var(--azul);min-width:3px}
.lh .n{font:600 11px/1 var(--mono);color:var(--t3)}
/* o subtítulo de um número do bloco do negócio: diz sobre o que é que
   ele conta, que é o que separa um facto de um número solto */
.desfecho-som .sub{font:400 10.5px/1.3 var(--sans);color:var(--t5);
 text-transform:none;letter-spacing:0}

/* Um número que ainda não existe diz-se por extenso, e não com um
   travessão: com a base quase vazia o bloco ficava a ser três
   travessões seguidos, o que dá ar de avariado em vez de «ainda não».
   Fica mais pequeno de propósito -- é uma nota, não um facto. */
.desfecho-som .por-haver b{font:400 12px/1.4 var(--sans);color:var(--t4)}
.desfecho-som .por-haver{min-width:150px}
/* As propostas por fechar, no aviso do bloco do negócio: cada uma é um
   clique para arrumar, e por isso são ligações e não uma frase. */
.por-fechar{display:flex;flex-wrap:wrap;gap:6px 14px;margin-top:8px}
.por-fechar a{font:500 12px/1.4 var(--sans)}
/* Os contactos (etapa 6) */
.ct{padding:9px 0;border-bottom:1px solid var(--papel);position:relative}
.ct:last-of-type{border-bottom:0}
.ct-nome{font:600 12.5px/1.4 var(--sans);color:var(--ink)}
.ct-papel{font:400 11px/1 var(--sans);color:var(--t4);margin-left:6px}
.ct-l{display:inline-block;margin-right:12px;font:400 11.5px/1.5 var(--sans);
 color:var(--t3)}
a.ct-l{color:var(--azul)}
.ct-notas{font:400 11.5px/1.4 var(--sans);color:var(--t4);margin-top:3px}
.ct-x{position:absolute;top:6px;right:0}
.ct-x button.etq-x{color:var(--t5)}
.ct-x button.etq-x:hover{color:var(--verm);opacity:1}
.ct-novo{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px;
 padding-top:12px;border-top:1px dashed var(--traco)}
.ct-novo input{flex:1 1 130px;font:400 11.5px/1.2 var(--sans);padding:6px 8px;
 border:1px solid var(--linha);border-radius:5px;background:#fff;color:var(--t2);
 min-height:24px;box-sizing:border-box}
.ct-novo button{cursor:pointer;font:600 11px/1 var(--sans);padding:6px 12px;
 border:1px solid var(--linha);border-radius:5px;background:#fff;color:var(--t3);
 min-height:24px;box-sizing:border-box}
.ct-novo button:hover{border-color:var(--azul);color:var(--azul)}

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

@media (max-width:1100px){
 .ind-grelha{grid-template-columns:minmax(0,1fr)}
}

/* Ecras estreitos (8/09/2026, pedido do Afonso: "quero que o frontend
   seja responsive"). Ate aqui a barra lateral de 140px comia um terco
   de um telemovel, a linha da lista transbordava e o titulo da ficha
   vinha com 22px numa coluna de 230. A regra: a barra passa para cima
   e fica so com a marca, a navegacao e a porta das Configuracoes; tudo
   o que e grelha de duas colunas passa a uma; o que e largo por
   natureza (quadro, tabelas, abas, indice da ficha) rola de lado
   dentro do seu contentor, nunca a pagina. Um so ponto de corte, 900px,
   mais um afinamento a 600 para os telemoveis mesmo pequenos. */
@media (max-width:900px){
 .barra{padding:10px 14px}
 /* a navegacao vai para uma segunda linha, inteira, e rola de lado se
    nao caber: espremida ao lado da marca empilhava-se em coluna */
 .barra nav{order:10;flex-basis:100%;margin:2px 0 0}
 .topo{padding:12px 16px 0}
 .corpo{padding:14px 12px 44px}
 h1.tit{font-size:19px}
 .abas{overflow-x:auto;flex-wrap:nowrap;scrollbar-width:none}
 .abas a{white-space:nowrap;padding:9px 10px}
 .linha-conta{flex-wrap:wrap}
 .linha-conta a{margin-left:0}
 .item{grid-template-columns:minmax(0,1fr)}
 .item-corpo{padding:12px 14px}
 .item-lado{border-left:0;border-top:1px solid var(--linha2);flex-direction:row;
  flex-wrap:wrap;justify-content:space-between;align-items:center;padding:10px 14px;gap:8px}
 .item-accoes{justify-content:flex-start}
 .filtros input[type=text]{min-width:0;flex-basis:100%}
 .filtros select,.filtros input[type=date]{flex:1 1 40%;min-width:0}
 .filtros input#filtro-cpv-excl{width:auto!important;flex:1 1 40%!important}
 details.painel-filtros .pf-sub{display:none}
 .guardados .guardar{margin-left:0;flex-basis:100%}
 .guardados .guardar input{min-width:0;flex:1}
 .paginas{flex-wrap:wrap}
 .cabeca{padding:16px 16px}
 .cabeca h2{font-size:17px}
 .essencial dl{padding:4px 14px 14px}
 .essencial .par{grid-template-columns:minmax(0,1fr);gap:2px}
 .em-falta-frase{padding:10px 14px 14px}
 .ficha-cab{flex-wrap:wrap}
 .ficha-cab .t{font-size:13px;flex-basis:calc(100% - 40px)}
 .ficha-indice{gap:14px;overflow-x:auto;flex-wrap:nowrap;scrollbar-width:none}
 .ficha-indice>a{white-space:nowrap}
 .ficha-indice .dir{display:none}
 .lado-cx{padding:14px}
 .coluna{width:min(282px,86vw)}
 .escada{flex-wrap:wrap}
 .escada span{flex:1 1 40%;min-width:0}
 .barras{gap:8px}
 .barras .col{min-width:0}
 .barras .l{white-space:normal;text-align:center;overflow-wrap:anywhere}
 .kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
 .conf-indice a i{display:none}
 .conf-cx{padding:14px}
 .conf-form textarea{max-width:none}
 dialog.modal{width:94vw}
}
@media (max-width:600px){
 .barra nav a{padding:7px 7px;font-size:12px}
 h1.tit{font-size:17px}
 .kpis{grid-template-columns:minmax(0,1fr)}
 .filtros select,.filtros input[type=date]{flex-basis:100%}
 .filtros input#filtro-cpv-excl{flex-basis:100%!important}
 .entrar{padding:20px 18px 18px}
}
"""

# A camada nova de aspecto (docs/design.md, 16/09/2026). Vive a parte do
# CSS de cima e esta TODA dentro de [data-pele=novo] / [data-tipo=*].
#
# **Fase 1, aplicada a 16/09/2026** ("avanca", palavra dele): os tres
# moldes -- BASE, PAGINA_ERRO e PAGINA_ENTRAR -- carimbam
# `data-pele="novo" data-tipo="plex"` no <html>, e mais nada mudou. O
# truque e os tokens ANTIGOS (--papel, --creme, --linha2) apontarem para
# os valores novos, o que faz as 1196 linhas de CSS de cima herdarem a
# paleta inteira sem se tocar numa regra. Tirar os dois atributos repoe
# o aspecto de antes -- e por isso que o `CSS` fica como estava e os
# testes que medem a paleta antiga continuam a medi-la.
#
# A /amostra continua a servir para comparar: e a unica pagina que
# escolhe a pele e a letra pela query string, e por isso e a unica que
# nao passa pelo envolver().
#
# Os @font-face ficam fora do ambito de proposito: declarar uma familia
# nao a carrega (o browser so pede o ficheiro quando alguma coisa a usa),
# e assim o mesmo bloco serve as tres opcoes do selector.
CSS_NOVO = r"""
@font-face{font-family:'Inter';src:url('/tipo/inter.woff2') format('woff2');
 font-weight:100 900;font-style:normal;font-display:swap}
@font-face{font-family:'Plex Sans';src:url('/tipo/plex-sans.woff2') format('woff2');
 font-weight:100 700;font-style:normal;font-display:swap}
@font-face{font-family:'Plex Mono';src:url('/tipo/plex-mono-400.woff2') format('woff2');
 font-weight:400;font-style:normal;font-display:swap}
@font-face{font-family:'Plex Mono';src:url('/tipo/plex-mono-600.woff2') format('woff2');
 font-weight:600;font-style:normal;font-display:swap}

[data-tipo=inter]{--sans:'Inter',system-ui,sans-serif;
 --mono:'Plex Mono',ui-monospace,Consolas,monospace}
[data-tipo=plex]{--sans:'Plex Sans',system-ui,sans-serif;
 --mono:'Plex Mono',ui-monospace,Consolas,monospace}
/* data-tipo=sistema nao redefine nada: fica o que o CSS de cima diz */

/* A paleta. Medida sobre TODOS os fundos que existem, nao so sobre o
   papel: pior caso 4,52 (docs/design.md §4). A escala de texto passou a
   ter cinco degraus, todos AA sobre tudo -- o --t6 aponta para o --t5
   porque um sexto cinzento que so funciona em metade dos fundos e uma
   armadilha, e foi o que ja partiu as .coluna-pede a 2/09. */
[data-pele=novo]{
 --fundo:#f5f6f8; --sup:#ffffff; --sup2:#eef0f4;
 --papel:#f5f6f8; --creme:#ffffff; --linha2:#eef0f4;
 --linha:#e3e6eb; --traco:#c3c9d2; --ink:#111418;
 --t1:#111418; --t2:#343a42; --t3:#4a515b; --t4:#5a626d;
 --t5:#646d7a; --t6:#646d7a;
 --azul:#1b5fc1; --verde:#12704a; --verm:#b3261e; --laranja:#9a4a06;
 --coral:#e08b2c;
 --azul-fundo:#e8f0fd; --azul-borda:#cfe0fb;
 --verde-fundo:#e4f2ea; --laranja-fundo:#fcefe1; --verm-fundo:#fdeae8;
 --azul-claro:#79b4f5;
 --barra-t1:rgba(255,255,255,.95); --barra-t2:#c3c9d2; --barra-t3:#98a1ae;
 --barra-linha:rgba(255,255,255,.13); --barra-on:rgba(255,255,255,.11);
 /* A escala: seis degraus, no lugar dos dezanove tamanhos soltos.
    Os valores sao os da Plex Sans, que e a letra escolhida (decisao
    dele a 16/09/2026). A Plex tem altura-de-x 52 contra 54 da Inter --
    le-se 3,8% mais pequena ao mesmo tamanho --, e por isso a escala
    sobe meio pixel em vez de se copiar a da Inter. Nao custa densidade:
    medido, a mesma frase a 13,5px em Plex da 625,7px contra 637,3px a
    13px em Inter, que e 1,8% MAIS estreita ao mesmo tamanho optico. */
 --f1:11.5px; --f2:12.5px; --f3:13.5px; --f4:15px; --f5:17.5px; --f6:25px;
 --r:8px;
 --sombra:0 1px 2px rgba(17,20,24,.04), 0 1px 3px rgba(17,20,24,.05);
}
/* Regra 4: os numeros alinham por algarismo. Dinheiro, prazos, datas,
   referencias e CPV sao metade do que este ecra mostra, e sem isto uma
   coluna de precos nao se compara de relance. */
[data-pele=novo] body{background:var(--fundo);
 font-variant-numeric:tabular-nums}

/* Regra 3: as superficies separam-se por tom, nao por risco. */
[data-pele=novo] .item,[data-pele=novo] .cx,[data-pele=novo] .sec,
[data-pele=novo] .kpi,[data-pele=novo] .conf-cx,[data-pele=novo] .prop{
 border-color:var(--linha);border-radius:var(--r);box-shadow:var(--sombra)}

/* Regra 1: hierarquia pelo tamanho e pelo peso. */
[data-pele=novo] h1.tit{font:680 var(--f6)/1.2 var(--sans);letter-spacing:-.6px}
[data-pele=novo] .item-titulo{font:620 var(--f5)/1.3 var(--sans);
 letter-spacing:-.2px}
[data-pele=novo] .abas a,[data-pele=novo] .bt{font-size:var(--f3)}

/* Regra d do diagnostico: as maiusculas espacadas saem. Um rotulo de
   bloco passa a caixa normal, peso 600, --f2 -- le-se melhor, ocupa
   menos, e deixa de obrigar a letra a descer a 9px para caber. */
[data-pele=novo] .rot,[data-pele=novo] .kpi .r,[data-pele=novo] .facto .k,
[data-pele=novo] details.sec .st,[data-pele=novo] .prop-campos label,
[data-pele=novo] .tab-contratos th,[data-pele=novo] .tab-mercado th,
[data-pele=novo] details.painel-filtros .pf-tit,
[data-pele=novo] .desfecho-som span{
 text-transform:none;letter-spacing:0;font-size:var(--f2);font-weight:600;
 color:var(--t4)}

/* Os botoes (docs/design.md §5). Cinco classes, e a funcao ve-se pela
   cor e pelo preenchimento antes de se ler a palavra.
   Os dois perigosos comecam em contorno e so se enchem ao passar ou ao
   receber foco: um botao vermelho cheio numa lista de vinte linhas e um
   alvo -- puxa o olho e convida ao clique errado, que e o contrario do
   que uma accao irreversivel quer. */
[data-pele=novo] .bt{border-radius:6px;font-weight:600;
 background:var(--sup);border-color:var(--traco);color:var(--t2)}
[data-pele=novo] .bt:hover{border-color:var(--t3);color:var(--t1)}
[data-pele=novo] .bt.forte{background:var(--azul);border-color:var(--azul);
 color:#fff}
[data-pele=novo] .bt.forte:hover{background:#17509f;border-color:#17509f}
[data-pele=novo] .bt.ok,[data-pele=novo] .bt.verde{background:var(--verde);
 border-color:var(--verde);color:#fff}
[data-pele=novo] .bt.ok:hover,[data-pele=novo] .bt.verde:hover{
 background:#0e5c3c;border-color:#0e5c3c;color:#fff}
[data-pele=novo] .bt.cuidado{background:var(--sup);color:var(--laranja);
 border-color:#e0b48a}
[data-pele=novo] .bt.cuidado:hover,[data-pele=novo] .bt.cuidado:focus-visible{
 background:var(--laranja);border-color:var(--laranja);color:#fff}
[data-pele=novo] .bt.perigo{background:var(--sup);color:var(--verm);
 border-color:#e5a9a2}
[data-pele=novo] .bt.perigo:hover,[data-pele=novo] .bt.perigo:focus-visible{
 background:var(--verm);border-color:var(--verm);color:#fff}

/* O `.mini` e o botao DA LINHA, e o `.bt` e o botao DA PAGINA. A
   diferenca nao e so o tamanho: numa lista de vinte linhas com dois
   botoes cada, encher quarenta botoes de cor faz quarenta alvos e
   nenhuma hierarquia. Por isso a regra do `.mini` e a mesma que a dos
   perigosos: **contorno com a cor do significado, e enche ao passar ou
   ao receber o foco**. O `.bt.forte` e o `.bt.ok` continuam cheios,
   porque sao um por bloco.

   E o `.mini` deixa de ficar VERMELHO ao passar por cima. Ficava, em
   todos -- no "ir" do selector, no "desfazer", no "X lotes" --, o que e
   o ponto (c) do diagnostico em estado puro: a cor de alarme a sair em
   coisas que nao alarmam nada, e por isso a nao querer dizer nada onde
   devia. Quem apaga mesmo leva `.mini.perigo`. */
[data-pele=novo] .mini{border-radius:6px;font-size:var(--f1);
 background:var(--sup);border-color:var(--traco);color:var(--t3)}
[data-pele=novo] .mini:hover{border-color:var(--t3);color:var(--t1);
 background:var(--sup)}
[data-pele=novo] .mini.verde,[data-pele=novo] .mini.ok{color:var(--verde);
 border-color:#9ac4ae}
[data-pele=novo] .mini.verde:hover,[data-pele=novo] .mini.ok:hover,
[data-pele=novo] .mini.verde:focus-visible,[data-pele=novo] .mini.ok:focus-visible{
 background:var(--verde);border-color:var(--verde);color:#fff}
[data-pele=novo] .mini.cuidado{color:var(--laranja);border-color:#e0b48a}
[data-pele=novo] .mini.cuidado:hover,
[data-pele=novo] .mini.cuidado:focus-visible{
 background:var(--laranja);border-color:var(--laranja);color:#fff}
[data-pele=novo] .mini.perigo{color:var(--verm);border-color:#e5a9a2}
[data-pele=novo] .mini.perigo:hover,
[data-pele=novo] .mini.perigo:focus-visible{
 background:var(--verm);border-color:var(--verm);color:#fff}

/* O separador de milhares e um espaco INQUEBRAVEL (mil_pt), e faz falta:
   com um normal, o browser parte "1 363 300" ao fim da linha. Mas a
   30px, na Plex, esse espaco tem a largura de um algarismo e "209 903"
   le-se como dois numeros. Aperta-se so aqui, no numero de display --
   a 11 ou 12px o espaco esta certo e nao se toca. Nao se troca o
   caractere: o mil_pt serve tambem a consola e os dois CSV. */
[data-pele=novo] .kpi .v{word-spacing:-.3em}
"""

# As duas folhas juntas uma vez so, e nao a cada pedido: os tres moldes
# (BASE, PAGINA_ERRO, PAGINA_ENTRAR) recebem esta. O `CSS` fica como
# estava de proposito -- e a paleta de recurso se o `data-pele` sair do
# <html>, e os testes que a medem continuam a medi-la.
CSS_TUDO = CSS + CSS_NOVO


BASE = """<!doctype html><html lang="pt" data-pele="novo" data-tipo="plex"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="csrf" content="%(csrf)s">
<title>%(titulo_aba)s</title>
<style>%(css)s</style></head><body>
<div class="app">
<header class="barra">
 <div class="marca"><a class="logo" href="/">Radar<span>Gov</span></a></div>
 <nav>%(nav)s</nav>
 <div class="caixa">
  <a class="n conf %(conf_on)s" href="/configuracoes" title="A conta, o interesse, os alertas e o resto das configurações">Configurações</a>
 </div>
 %(conta)s
</header>
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
# 15/09/2026 (D7): "Anuncios" e "Em curso" fundiram-se em **Concursos**.
# Eram dois itens sobre a mesma escada -- e enquanto o "Em curso" foi
# `estado='interessa'`, sobre a mesma POPULACAO, que e a pergunta que
# deu origem ao CRM. Com as dez ranhuras nas abas, o que sobra sao tres
# maneiras de ver a mesma lista, e isso e uma vista e nao um separador.
# A "Lista" saiu daqui: e a lista, e a lista e a primeira vista.
# 15/09/2026, segunda arrumacao do mesmo dia: o **quadro sai** e a
# **lista deixa de ser uma vista** para ser a propria pagina. Oito
# colunas e oito abas eram a mesma coisa duas vezes, e a diferenca era o
# arrastar -- que so compensa quando se ve tudo ao mesmo tempo. Com uma
# coluna por aba nao ha para onde arrastar, e a ranhura muda-se no
# selector da linha. Sobra o calendario, que e a unica forma diferente
# de olhar para o mesmo: uma grelha de dias, para ver choques de datas.
NAV = (("anuncios", "Concursos", "/",
        (("calendario", "Calendário", "/calendario"),)),
       ("mercado", "Mercado", "/contratos",
        (("contratos", "Contratos", "/contratos"),
         # as renovacoes fundiram-se nos contratos como modo (6.1-A);
         # a rota antiga /renovacoes redirecciona para ca
         ("renovacoes", "Renovações", "/contratos?ver=fim"))))
# Alertas saiu do primeiro nivel a 8/09/2026 (docs/historico/ONLINE.md,
# etapa 2): passou a seccao de Configuracoes, que vive em baixo, ao
# lado da zona de estado, como os Indicadores -- e o sitio onde se vai
# de vez em quando, nao uma intencao diaria. Reverte a decisao 11.6-A
# do esqueleto ("nao criar pagina Definicoes"): o que era "afinar o que
# o radar vigia" mais "o que se edita a mao no JSON" mais "cinco
# ficheiros de chaves na pasta" deixou de caber em tres sitios quando
# o painel passou a abrir-se de fora, onde nao se abre o Bloco de Notas.

# Que item da navegacao acende para cada pagina. As paginas mantem as
# chaves que sempre tiveram (as vistas de filtros incluidas); o item e
# hierarquia por cima delas, nao um nome novo.
ITEM_DA_PAGINA = {pagina: chave for chave, _, _, vistas in NAV
                  for pagina in [chave] + [v[0] for v in vistas]}

# Onde o botao "Verificar agora" aparece: SO na lista dos anuncios
# (decisao 11.8-A, que sobrevive a fusao). O botao vai ao DR buscar
# anuncios novos e os novos aterram no por ver -- e la que o resultado
# se ve. No quadro e no calendario parecia dizer respeito ao que esta
# no ecra, e nao dizia.
PAGINAS_COM_VERIFICAR = ("anuncios",)   # a lista, e so ela


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
        # a unica pagina fora da navegacao (os Indicadores eram outra;
        # desde 13/09/2026 sao uma seccao de Configuracoes)
        if vista != "configuracoes":
            return "<em>%s</em>" % html.escape(folha or "Radar")
        passos = [("Configurações", "/configuracoes")]

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


def accao(destino, etiqueta, classe="bt", confirmar="", campos=None):
    """Um botao que faz POST. Tudo o que altera dados passa por aqui:
    como <a href> isto respondia a um prefetch do browser ou a qualquer
    coisa que siga links, e ha aqui accoes que mudam a base.

    Os `campos` vao como <input hidden> (15/09/2026): ha rotas que leem
    o que fazer do CORPO e nao do caminho -- o `/escada/...`, porque um
    <select> nao sabe escrever um URL -- e um botao que lhes chame tem
    de as poder alimentar.
    """
    ao_submeter = (" onsubmit=\"return confirm('%s')\"" % confirmar) if confirmar else ""
    escondidos = "".join(
        "<input type='hidden' name='%s' value='%s'>"
        % (html.escape(k, quote=True), html.escape(str(v), quote=True))
        for k, v in (campos or {}).items())
    return ("<form class='accao' method='post' action='%s'%s>%s"
            "<button type='submit' class='%s'>%s</button></form>"
            % (destino, ao_submeter, escondidos, classe, etiqueta))


def forma_abandonar(ref, classe="mini cuidado", etiqueta="abandonar",
                    titulo=""):
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
            "action='/estado/%s/nao_fomos' data-titulo='%s'>"
            "<button type='submit' class='%s'>%s</button></form>"
            % (ref, html.escape(titulo or ref, quote=True), classe, etiqueta))


# A caixa e UMA por pagina, partilhada por todos os botoes: vinte copias
# do mesmo dialogo numa lista de vinte linhas seria o mesmo erro dos
# vinte selectores, com mais HTML.
def opcoes_html(pares, actual):
    """As <option> de um selector, marcada a que esta em uso. Cada par e
    (valor, rotulo); um valor sozinho e o seu proprio rotulo."""
    pares = [p if isinstance(p, tuple) else (p, p) for p in pares]
    return "".join("<option value='%s'%s>%s</option>"
                   % (html.escape(v, quote=True),
                      " selected" if v == (actual or "") else "",
                      html.escape(r)) for v, r in pares)


def _opcoes(nome, valores, actual, vazio="\u2014"):
    return ("<select name='%s'>%s</select>"
            % (nome, opcoes_html([("", vazio)] + list(valores), actual)))


def selector_de_ranhura(accao, actual, titulo=""):
    """O `<select>` das oito palavras, com o «tirar da escada» no fim.

    **Só para quem já está na escada** (decisão dele a 15/09/2026). Para
    um concurso por decidir há os dois botões de sempre -- «interessa»,
    que vai directo a «Por analisar», e «abandonar», que vai a «Não
    fomos» e pergunta porquê. Um selector a dizer «— pôr na escada» era
    uma palavra inventada ao lado de oito palavras a sério, e punha a
    dois gestos o que é o gesto de 90% das linhas do «Por ver».

    O `data-motivos` diz ao JS quais das opcoes pedem motivo, para ele
    abrir a caixa em vez de gravar logo. Sem JS o `<select>` muda e o
    botao grava; o servidor recusa por falta de motivo e diz porque --
    degradacao a dizer o que se passa, e nao um controlo morto.
    """
    opcoes = []
    for chave, rotulo in ESTADOS_DA_CASA:
        opcoes.append("<option value='%s'%s>%s</option>"
                      % (chave, " selected" if chave == actual else "",
                         html.escape(rotulo)))
    opcoes.append("<option value='%s'>tirar da escada</option>"
                  % ENTRADA_DA_ESCADA[0])
    return ("<form class='ranhura escada-js' method='post' action='%s' "
            "data-titulo='%s' data-motivos='%s'>"
            "<select name='estado'>%s</select>"
            "<button type='submit' class='mini'>ir</button></form>"
            % (html.escape(accao, quote=True),
               html.escape(titulo, quote=True),
               " ".join(MOTIVOS_DO_ESTADO),
               "".join(opcoes)))


def caixa_do_motivo():
    """O <dialog> do motivo, mais o JS que o abre. Serve os dois estados
    que pedem porquê -- «Não fomos» e «Perdido» --, e as duas listas não
    são a mesma: «Preço base baixo» é porque não se foi, e não é resposta
    a «porque se perdeu».

    Era o `caixa_do_motivo()`, só do abandono. Generalizou-se quando o
    selector de ranhura passou a poder pôr um concurso em qualquer das
    duas (15/09/2026); o `abandonar-js` da lista continua a funcionar
    pelo mesmo diálogo, para o botão «abandonar» não perder o gesto.
    """
    grupos = "".join(
        "<div class='escolhas' data-para='%s' hidden>%s</div>"
        % (estado,
           "".join("<label><input type='radio' name='motivo' value='%s'>"
                   "<span>%s</span></label>"
                   % (html.escape(m, quote=True), html.escape(m))
                   for m in motivos))
        for estado, motivos in MOTIVOS_DO_ESTADO.items())
    titulos = json.dumps({e: estado_da_casa(e) for e in MOTIVOS_DO_ESTADO})
    return ("<dialog class='modal' id='dlg-motivo'>"
            "<form method='post' class='accao' id='form-motivo'>"
            "<input type='hidden' name='estado' id='dlg-motivo-estado'>"
            "<h3 id='dlg-motivo-titulo'></h3>"
            "<p class='alvo' id='dlg-motivo-alvo'></p>"
            "<p class='nota'>Não apaga nada: fica na escada e pode "
            "voltar. O motivo é para daqui a um mês se saber porquê.</p>"
            "%s"
            "<div class='modal-pe'>"
            "<button type='button' id='dlg-motivo-nao'>Cancelar</button>"
            "<button type='submit'>Gravar</button>"
            "</div></form></dialog>"
            "<script>\n"
            "(function () {\n"
            "  // com JS, o selector grava sozinho e o botao \"ir\" esconde-se;\n"
            "  // sem JS a folha deixa-o visivel, que e o unico caminho\n"
            "  document.documentElement.classList.add('com-js');\n"
            "  var d = document.getElementById('dlg-motivo');\n"
            "  if (!d || !d.showModal) return;   // sem <dialog>, o POST segue\n"
            "  var f = document.getElementById('form-motivo');\n"
            "  var TITULOS = %s;\n"
            "  function abrir(accao, titulo, estado) {\n"
            "    f.action = accao;\n"
            "    document.getElementById('dlg-motivo-estado').value = estado;\n"
            "    document.getElementById('dlg-motivo-titulo').textContent =\n"
            "        (TITULOS[estado] || 'Motivo') + ': porquê?';\n"
            "    document.getElementById('dlg-motivo-alvo').textContent = titulo || '';\n"
            "    f.querySelectorAll('.escolhas').forEach(function (g) {\n"
            "      var meu = g.dataset.para === estado;\n"
            "      g.hidden = !meu;\n"
            "      g.querySelectorAll('input').forEach(function (r) {\n"
            "        r.checked = false; r.required = meu;\n"
            "      });\n"
            "    });\n"
            "    d.showModal();\n"
            "  }\n"
            "  // o selector de ranhura: so as que pedem motivo abrem a caixa\n"
            "  document.addEventListener('change', function (e) {\n"
            "    var sel = e.target;\n"
            "    if (!sel.name || sel.name !== 'estado') return;\n"
            "    var form = sel.form;\n"
            "    if (!form || !form.classList.contains('escada-js')) return;\n"
            "    var pedem = (form.dataset.motivos || '').split(' ');\n"
            "    if (pedem.indexOf(sel.value) >= 0) {\n"
            "      abrir(form.action, form.dataset.titulo, sel.value);\n"
            "    } else {\n"
            "      form.requestSubmit();\n"
            "    }\n"
            "  });\n"
            "  // o botao \"abandonar\" da lista, que e sempre o nao_fomos\n"
            "  document.addEventListener('submit', function (e) {\n"
            "    var origem = e.target;\n"
            "    if (!origem.classList || !origem.classList.contains('abandonar-js')) return;\n"
            "    e.preventDefault();\n"
            "    abrir(origem.action, origem.dataset.titulo, 'nao_fomos');\n"
            "  }, true);\n"
            "  document.getElementById('dlg-motivo-nao').addEventListener(\n"
            "      'click', function () { d.close(); });\n"
            "})();\n"
            "</script>" % (grupos, titulos))


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

    # A ultima verificacao saiu da barra a 13/09/2026: esta nos
    # Indicadores (linha_da_ultima_verificacao()), que passaram a seccao
    # de Configuracoes. O sinal de vida enquanto corre fica no topo.
    a_verificar = verificacao_a_correr()

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

    # O aviso que faltava. Sem as tarefas agendadas, o radar so recolhe
    # com o painel aberto -- e como o relogio interno recupera os slots
    # falhados, a tabela `slots` fica preenchida e parece que correu a
    # horas. Foi assim que isto passou semanas sem se notar. E aviso do
    # sistema e nao da vez, por isso nao vai pela query string.
    faltam = tarefas_em_falta()
    if faltam:
        onde, guiao = como_agendar()
        aviso += (
            "<div class='flash mau'>O radar <b>não está a verificar "
            "sozinho</b>: %s por criar %s. Enquanto "
            "assim for, só recolhe quando este painel está aberto. Corre "
            "o <code>%s</code> uma vez.</div>"
            % ("a tarefa &ldquo;%s&rdquo; está" % html.escape(faltam[0])
               if len(faltam) == 1
               else "as tarefas %s estão"
               % " e ".join("&ldquo;%s&rdquo;" % html.escape(t)
                            for t in faltam), onde, guiao))

    return com_csrf(BASE % {
        "titulo_aba": html.escape(titulo_aba or titulo),
        "css": CSS_TUDO,
        "csrf": csrf_da_pagina(),
        "conta": bloco_da_conta(),
        "conf_on": "on" if activo == "configuracoes" else "",
        "nav": "".join(itens),
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
            if activo in PAGINAS_COM_VERIFICAR and sou_admin() else ""),
        "lista_pessoas": "".join("<option value='%s'>" % html.escape(n, quote=True)
                                 for n in listar_pessoas()),
        # Enquanto a verificacao correr, a pagina volta a pedir-se
        # sozinha -- o mesmo que a actualizacao do corpus ja fazia. A
        # thread poe sempre um estado terminal, por isso isto para.
        "script": script + ("<script>setTimeout(function(){location.reload()},"
                            "5000)</script>" if a_verificar else ""),
    })


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


def corta(texto, tecto):
    """Corta e diz que cortou. Sem as reticencias, um objecto cortado a
    meio de palavra ("...suporte do Hardware Oracle onde residem as Base
    de Dado") lia-se como dado estragado e nao como texto cortado."""
    texto = texto or ""
    return texto if len(texto) <= tecto else texto[:tecto].rstrip() + "…"


def linha(a, vista="", urgente=None, na_escada=None):
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
    # Em que ranhura da escada esta, quando nao e a que se esta a ver.
    # Sai da PROPOSTA -- a decisao da casa deixou de morar no anuncio a
    # 15/09/2026 -- e vem de um mapa montado uma vez por pagina, nao de
    # uma consulta por linha.
    for p in (na_escada or {}).get(a["ref"], ()):
        if p["estado"] == vista:
            continue
        tags.append("<span class='tag %s'>%s%s</span>"
                    % ("" if p["estado"] in ESTADOS_FECHADOS else "ok",
                       html.escape(estado_da_casa(p["estado"])),
                       " L%d" % p["lote"] if p["lote"] else ""))
        # Porque e que nao se foi, ou porque se perdeu, na propria
        # linha: e o que faz a ranhura valer alguma coisa passado um
        # mes. Os que expiraram sem ninguem ver nao tem motivo -- e nao
        # se lhes inventa um.
        if p["motivo"]:
            tags.append("<span class='tag'>%s</span>" % html.escape(p["motivo"]))

    preco = ("<div class='item-preco'>%s</div>" % html.escape(a["preco_base"])) \
        if a["preco_base"] else ""

    # Os botoes dependem do estado em que o anuncio esta. Eram sempre os
    # mesmos dois: em Descartados nao havia forma nenhuma de repor um
    # descarte (o caminho era marcar interessa e depois "tirar do quadro"),
    # e em Interessa o botao "interessa" continuava la e nao era inocuo --
    # cada clique voltava a pedir as pecas e a descarrega-las outra vez.
    # O selector, e nao dois botoes (15/09/2026, decisao dele): a lista
    # passou a ser o unico sitio onde se anda na escada, e "interessa" e
    # "abandonar" cobriam duas das oito palavras. O "interessa" fica ao
    # lado enquanto nao ha decisao nenhuma, porque e o gesto de 90% das
    # linhas do "Por ver" e nao se troca um clique por dois.
    # Uma coisa OU a outra, nunca as duas (decisao dele a 15/09/2026):
    # por decidir, os dois botoes de sempre -- o "interessa" vai directo
    # a "Por analisar" e o "abandonar" a "Nao fomos", a perguntar
    # porque; ja na escada, o selector das oito palavras. Um selector a
    # dizer "pôr na escada" era uma palavra inventada ao lado de oito
    # palavras a serio.
    aqui = list((na_escada or {}).get(a["ref"], ()))
    botoes = []
    if not aqui:
        botoes.append(accao("/estado/%s/analisar" % quote(a["ref"], safe=""),
                            "interessa", "mini verde"))
        botoes.append(forma_abandonar(a["ref"], titulo=a["titulo"] or ""))
    else:
        botoes.append(selector_de_ranhura(
            "/escada/" + quote(a["ref"], safe=""), aqui[0]["estado"],
            titulo=a["titulo"] or a["ref"]))
    if len(aqui) > 1:
        # Com lotes ha uma proposta por lote e o selector move a
        # primeira: dizer qual, e mandar a ficha, e melhor do que mover
        # uma delas em silencio.
        botoes.append("<a class='mini' href='/anuncio/%s#proposta'>%d lotes"
                      "</a>" % (quote(a["ref"], safe=""), len(aqui)))

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
// O painel dos filtros lembra-se de ter ficado aberto: quem abriu os
// filtros uma vez quer encontra-los abertos, e quem nunca abriu nao.
(function () {
  var d = document.getElementById('painel-filtros');
  if (!d) return;
  var chave = 'radar-filtros-abertos';
  try { if (localStorage.getItem(chave) === '1') d.open = true; } catch (x) {}
  d.addEventListener('toggle', function () {
    try { localStorage.setItem(chave, d.open ? '1' : '0'); } catch (x) {}
  });
})();
// Teclado na lista (UX-Auditoria, Parkinson): j/k anuncio seguinte e
// anterior, i interessa, a abandonar (abre a caixa do motivo), Enter
// abre a ficha. Triar vinte cartoes era vinte vezes levar o rato a dois
// botoes de 25px no canto direito de cada um. Nada disto dispara com o
// foco num campo de texto.
(function () {
  var itens = Array.prototype.slice.call(document.querySelectorAll('.item'));
  if (!itens.length) return;
  var i = -1;
  function foca(n) {
    if (i >= 0) itens[i].classList.remove('foco');
    i = Math.max(0, Math.min(itens.length - 1, n));
    itens[i].classList.add('foco');
    itens[i].scrollIntoView({block: 'nearest'});
  }
  function accao(selector) {
    if (i < 0) return;
    var f = itens[i].querySelector(selector);
    if (f) f.requestSubmit();
  }
  document.addEventListener('keydown', function (e) {
    var t = e.target;
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' ||
              t.tagName === 'SELECT' || t.isContentEditable)) return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (document.querySelector('dialog[open]')) return;
    if (e.key === 'j') { foca(i + 1); e.preventDefault(); }
    else if (e.key === 'k') { foca(i - 1); e.preventDefault(); }
    else if (e.key === 'i') { accao("form.accao[action$='/interessa']"); }
    else if (e.key === 'a') { accao('form.abandonar-js'); }
    else if (e.key === 'Enter' && i >= 0) {
      var a = itens[i].querySelector('.item-titulo');
      if (a) location.href = a.href;
    }
  });
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

// A pagina pode nao ter arvore (a lista com interesse definido,
// 13/09/2026): sem ela nao ha nada a ligar, e um addEventListener em
// null era um erro na consola em todas as paginas da lista.
var ARV_DET = document.querySelector('details.arvore');
if (ARV_DET) {
  ARV_DET.addEventListener('toggle', function() {
    if (this.open) arvoreCarregar();
  });
  // a arvore que ja vem aberta carrega-se logo: o `toggle` de um
  // <details open> e uma tarefa em fila, e nao se conta com ele
  if (ARV_DET.open) arvoreCarregar();
  document.getElementById('arvore-busca').addEventListener('input', function() {
    var alvo = this.value.trim().toLowerCase();
    Array.from(document.getElementById('arvore-corpo').children).forEach(
        function(no) { arvoreFiltra(no, alvo); });
  });
  arvoreSemear();
}
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


def campos_escondidos(args, nomes):
    """Campos que sairam do ecra mas continuam a valer na URL (um alerta
    antigo, a ligacao dos urgentes): passam escondidos para nao se
    perderem ao voltar a filtrar. So os que vierem com valor."""
    return "".join(
        "<input type='hidden' name='%s' value='%s'>"
        % (nome, html.escape((args.get(nome) or "").strip(), quote=True))
        for nome in nomes if (args.get(nome) or "").strip())


# As sugestoes de entidade (14/09/2026: «se estou a escrever SP... ele
# deve sugerir as SP»). Um <datalist> que o JS enche a cada tecla com o
# que /entidades.json devolve: as entidades que publicam, com o texto
# no nome, as que COMECAM por ele primeiro e depois por quantos
# anuncios tem. Nao e uma lista estatica: sao dezenas de milhares.
ENTIDADES_JS = """<script>
(function () {
  var campos = document.querySelectorAll("input[data-sugere]");
  if (!campos.length) return;
  var pedido = 0;
  campos.forEach(function (campo) {
    // de onde vem (anuncios ou contratos) e em que campo escondido do
    // mesmo formulario fica a chave: e por ela que se filtra quando a
    // sugestao foi escolhida, e limpa-se assim que o texto deixa de ser
    // uma sugestao (o nome escrito a mao e so texto)
    var de = campo.dataset.sugere, lista = document.getElementById(campo.getAttribute('list'));
    var chave = campo.form ? campo.form.querySelector("input[name='" + campo.dataset.chaveEm + "']") : null;
    var nifs = {};
    function acertar() { if (chave) chave.value = nifs[campo.value.trim()] || ''; }
    campo.addEventListener('change', acertar);
    campo.addEventListener('input', function () {
      acertar();
      var texto = campo.value.trim();
      if (texto.length < 2 || !lista) return;
      var meu = ++pedido;
      fetch('/entidades.json?de=' + de + '&q=' + encodeURIComponent(texto))
        .then(function (r) { return r.json(); })
        .then(function (entidades) {
          if (meu !== pedido) return;   // ja ha um pedido mais recente
          lista.innerHTML = '';
          entidades.forEach(function (e) {
            var o = document.createElement('option');
            o.value = e.nome;
            o.label = de === 'anuncios' ? e.n + ' anúncios' : (e.nif ? 'NIF ' + e.nif : '');
            lista.appendChild(o);
            nifs[e.nome] = e.nif || '';
          });
          acertar();
        }).catch(function () {});
    });
  });
})();
</script>"""


@app.route("/entidades.json")
def entidades_json():
    de = (request.args.get("de") or "anuncios").strip()
    q = request.args.get("q") or ""
    lista = (sugestoes_de_entidade_do_corpus(q) if de == "contratos"
             else sugestoes_de_entidade(q))
    return Response(json.dumps(lista, ensure_ascii=False),
                    mimetype="application/json")


def sugestoes_de_entidade_do_corpus(texto, limite=10):
    """[{nome, nif, n}] das entidades do corpus (quem compra e quem
    ganha, na mesma tabela `entidades`) cujo nome -- qualquer dos nomes
    por que ja apareceram, `entidade_nomes` -- contem `texto`. A chave e
    o NIF; `n` e o numero de nomes com que a entidade ja assinou, que e
    o que a tabela tem a mao (contar contratos por entidade a cada
    tecla era uma varredura). As que comecam pelo texto primeiro."""
    alvo = norma_entidade(texto or "").strip()
    if len(alvo) < 2 or not ha_corpus():
        return []
    padrao = para_like(alvo)
    with liga_corpus() as c:
        linhas = c.execute(
            "SELECT e.chave, e.nome, COALESCE(e.variantes,1) n,"
            " MAX(n.nome_norm LIKE ? ESCAPE '%s') comeca"
            " FROM entidade_nomes n JOIN entidades e ON e.chave = n.chave"
            " WHERE n.nome_norm LIKE ? ESCAPE '%s'"
            " GROUP BY e.chave ORDER BY comeca DESC, n DESC LIMIT ?"
            % (ESCAPE_LIKE, ESCAPE_LIKE),
            (padrao + "%", "%" + padrao + "%", limite)).fetchall()
    return [{"nome": r["nome"], "nif": r["chave"], "n": r["n"]} for r in linhas]


def sugestoes_de_entidade(texto, limite=10):
    """[{nome, nif, n}] das entidades que publicam anuncios cujo nome
    contem `texto`: as que comecam por ele primeiro, depois as mais
    frequentes. Procura pelo nome normalizado (sem acentos), que e o
    que o filtro tambem usa.

    Agrupadas pelo NIF (14/09/2026): a SPMS tem tres grafias na base e
    apareciam tres vezes. Uma linha por NIF, com a grafia mais
    frequente e a soma de todas; o que nao tem NIF agrupa-se pelo nome.
    """
    alvo = simplifica(texto or "").strip()
    if len(alvo) < 2:
        return []
    padrao = para_like(alvo)
    with liga() as c:
        linhas = c.execute(
            "SELECT entidade, COALESCE(nif,'') nif, COUNT(*) n, "
            " MAX(entidade_norm LIKE ? ESCAPE '%s') comeca"
            " FROM anuncios WHERE entidade_norm LIKE ? ESCAPE '%s'"
            " AND COALESCE(entidade,'') != ''"
            " GROUP BY entidade, nif ORDER BY n DESC"
            % (ESCAPE_LIKE, ESCAPE_LIKE),
            (padrao + "%", "%" + padrao + "%")).fetchall()
    # Uma grafia que aparece com NIF numas linhas e sem NIF noutras (24%
    # dos anuncios vieram sem ele) e a mesma entidade: dobra-se no grupo
    # do NIF, senao a SPMS saia duas vezes com o mesmo nome.
    nif_da_grafia = {r["entidade"]: r["nif"] for r in linhas if r["nif"]}
    grupos = {}
    for r in linhas:
        nif = r["nif"] or nif_da_grafia.get(r["entidade"], "")
        chave = nif or ("nome:" + r["entidade"])
        g = grupos.setdefault(chave, {"nome": r["entidade"], "nif": nif,
                                      "n": 0, "comeca": 0})
        g["n"] += r["n"]                   # a primeira grafia e a mais frequente
        g["comeca"] = max(g["comeca"], r["comeca"])
    saida = sorted(grupos.values(), key=lambda g: (-g["comeca"], -g["n"]))[:limite]
    return [{"nome": g["nome"], "nif": g["nif"], "n": g["n"]} for g in saida]


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
    if estado is None or estado == ENTRADA_DA_ESCADA[0]:
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


# As abas antigas, e a ranhura da escada que hoje diz o que elas diziam.
# As ligacoes antigas (e os filtros guardados de antes de 15/09/2026)
# trazem `?estado=novo` e `?estado=interessa` nas query strings: em vez
# de as deixar cair numa aba que nao existe -- e devolver a lista vazia
# sem nada a dize-lo --, traduzem-se a entrada.
ABAS_ANTIGAS = {"novo": "porver", "interessa": "analisar",
                "descartado": "nao_fomos"}

# Um anuncio ja tem decisao da casa quando ha uma proposta sobre ele.
# E o que apura a entrada: um anuncio que se pos "a preparar proposta"
# nao pode continuar a aparecer em "Por ver" a pedir triagem.
_EXISTE_PROPOSTA = "EXISTS (SELECT 1 FROM propostas p WHERE p.ref = anuncios.ref%s)"
SQL_TEM_PROPOSTA = _EXISTE_PROPOSTA % ""
SQL_PROPOSTA_NO_ESTADO = _EXISTE_PROPOSTA % " AND p.estado = ?"


def condicao_da_aba(estado, hoje=None, cfg=None):
    """(fragmento, valores) do que cada aba da lista de ANUNCIOS mostra.

    A escada de 15/09/2026 (D7, `docs/historico/CRM.md` §3.1). Das dez
    ranhuras, so tres se respondem sobre a tabela dos anuncios -- as
    duas das pontas e o "todos". As oito da casa contam anuncios com
    proposta naquele estado, e servem so para o NUMERO da aba: a lista
    delas e de propostas, e nao de anuncios (`_lista_de_propostas()`),
    porque uma proposta sem anuncio do DR (D2) nao esta aqui para ser
    encontrada.

    - **por ver** (`porver`): por decidir E ainda respondivel -- prazo
      aberto; sem prazo lido, vale a data de publicacao dentro de
      detalhe_dias (entre publicacao e prazo vao ~18 dias em media, 60
      e folga, e e a mesma janela que a rotina le). E **sem proposta**:
      decidido ja nao e por decidir.
    - **expirou sem ver** (`expirou`): o prazo passou e ninguem olhou.
      Nao e decisao de ninguem, e por isso nao e ranhura da casa -- a
      15/09/2026 eram 198 305 dos 199 568, e a base nao tinha um unico
      descarte. Nada muda na base: e recorte de leitura, e um expirado
      que seja rectificado com prazo novo volta sozinho ao por ver.
    - **todos** (`""`): sem recorte.

    Aplica-se por cima de condicoes() com com_recorte() -- o motor
    nunca leva isto (alertas!).
    """
    estado = ABAS_ANTIGAS.get(estado, estado)
    if not estado:
        return "", []
    if estado in CHAVES_DA_CASA:
        return SQL_PROPOSTA_NO_ESTADO, [estado]
    hoje = hoje or datetime.now().date()
    cfg = ler_config() if cfg is None else cfg
    try:
        dias = int(cfg.get("detalhe_dias", 60)) or 60
    except (TypeError, ValueError):
        dias = 60
    corte = (hoje - timedelta(days=dias)).isoformat()
    vivo = ("((prazo IS NOT NULL AND prazo != '' AND prazo >= ?) OR "
            "(COALESCE(prazo, '') = '' AND data_pub >= ?))")
    if estado == "porver":
        return ("estado = 'novo' AND " + vivo + " AND NOT " + SQL_TEM_PROPOSTA,
                [hoje.isoformat(), corte])
    if estado == "expirou":
        return ("estado = 'novo' AND NOT " + vivo + " AND NOT " + SQL_TEM_PROPOSTA,
                [hoje.isoformat(), corte])
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


def prefixos_do_cpv(texto):
    """Os prefixos de CPV de um texto de filtro ("72000000|48700000",
    ou palavras da descricao oficial), como fragmento_cpv() os le --
    mas para a tabela contrato_cpv, que guarda o codigo de 8 digitos
    por linha e se pergunta por prefixo."""
    prefixos = []
    for pedaco in (p.strip() for p in (texto or "").split("|")):
        if not pedaco:
            continue
        if re.fullmatch(r"[\d\-\s]+", pedaco):
            candidatos = [prefixo_cpv(pedaco)]
        else:
            candidatos = cpv_por_termo(pedaco)
        prefixos.extend(p for p in candidatos if p)
    return prefixos


def condicao_do_interesse_contratos(args=None, cfg=None):
    """(fragmento, valores) do interesse no MERCADO (14/09/2026, a
    pedido do Afonso: «no mercado, após definir o interesse, deve também
    só aparecer o CPV marcado, tal como nos anúncios»).

    A mesma leitura do interesse que condicao_do_interesse(), mas sobre
    a tabela contrato_cpv (um contrato tem varios CPV, um por linha), e
    com o `?interesse=nao` a levanta-lo da mesma maneira. Entra por
    filtros_dos_contratos(), que e o recorte de pagina dos contratos
    (a lista, o CSV e os graficos filtram os tres por la) -- e NAO por
    condicoes_contratos(), que serve os alertas e a ficha da entidade.
    """
    args = request.args if args is None else args
    if (args.get("interesse") or "").strip() == "nao":
        return "", []
    ligado, dentro, fora = interesse_definido(cfg)
    if not ligado or not dentro.strip():
        return "", []
    dentro_p = prefixos_do_cpv(dentro)
    if not dentro_p:
        return "1=0", []          # um termo que nao e nada: vazio, nao tudo
    frag = ("c.id IN (SELECT contrato_id FROM contrato_cpv WHERE %s)"
            % " OR ".join("cpv8 LIKE ?" for _ in dentro_p))
    vals = [p + "%" for p in dentro_p]
    fora_p = prefixos_do_cpv(fora)
    if fora_p:
        frag += (" AND c.id NOT IN (SELECT contrato_id FROM contrato_cpv WHERE %s)"
                 % " OR ".join("cpv8 LIKE ?" for _ in fora_p))
        vals += [p + "%" for p in fora_p]
    return frag, vals


def contar_a_escada(onde_base=None, valores_base=(), cfg=None):
    """Quantos ha em cada uma das dez ranhuras, DENTRO do filtro em uso.

    As contagens eram sobre a base inteira e diziam "Por ver 66 007 ·
    Todos 66 009" por cima de uma lista de 234 -- o numero e o destino
    do mesmo botao discordavam. Cada ranhura conta com o SEU recorte,
    porque a regra da casa e que um numero tem de abrir exactamente a
    lista que o confirma.

    As oito da casa contam **anuncios com proposta naquele estado**, e
    nao propostas: e o numero que o filtro da pagina sabe responder. A
    lista delas mostra tambem as propostas sem anuncio (D2), por isso
    pode ter MAIS linhas do que a aba diz -- e a `_lista_de_propostas()`
    que o explica ao pe do numero, em vez de se calar.
    """
    cfg = ler_config() if cfg is None else cfg
    if onde_base is None:
        # Sem filtro nenhum, a base NAO e vazia: e a mesma do motor com
        # `estado=""` -- que tira as alteracoes, porque "todos" sao todos
        # os PROCEDIMENTOS e uma republicacao e o mesmo concurso outra
        # vez. Sem isto o "Todos" dizia 209 894 na lista das propostas e
        # 199 631 na dos anuncios: o mesmo botao com dois numeros, que e
        # exactamente o que a regra da casa proibe. Visto no ecra.
        onde_base, valores_base = condicoes({"estado": ""})
    contas = {}
    with liga() as c:
        for chave, _ in ESCADA + (("", "Todos"),):
            onde, valores = com_recorte(onde_base, list(valores_base),
                                        *recorte_da_lista(chave, cfg))
            contas[chave] = c.execute(
                "SELECT COUNT(*) n FROM anuncios" + onde, valores).fetchone()["n"]
    return contas


def barra_das_abas(rota, actual, contas):
    """As dez ranhuras mais o "todos", desenhadas uma vez para as duas
    listas. Sem isto eram dois sitios a desenhar a mesma barra, e o
    primeiro a mudar deixava o outro a mostrar abas que ja nao existem.

    As duas das pontas levam classe propria: nao sao estados da casa (a
    entrada e o cemiterio), e um ecra que as pinte como as outras oito
    diz que sao oito estados quando sao dez coisas de tres naturezas.
    """
    pecas = ["<div class='abas abas-escada'>"]
    for chave, rotulo in ESCADA + (("", "Todos"),):
        if chave == ENTRADA_DA_ESCADA[0]:
            classe = "ponta entrada"
        elif chave == CEMITERIO_DA_ESCADA[0]:
            classe = "ponta cemiterio"
        elif not chave:
            classe = "ponta"
        else:
            classe = "casa" + (" fechada" if chave in ESTADOS_FECHADOS else "")
        if chave == actual:
            classe += " on"
        pecas.append("<a class='%s' href='%s'>%s <i>%s</i></a>"
                     % (classe, sem_pagina(request.args, rota, estado=chave),
                        html.escape(rotulo), mil_pt(contas.get(chave, 0))))
    pecas.append("</div>")
    return "".join(pecas)


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


def aba_pedida():
    """A ranhura da escada que o pedido pede, ja traduzida do vocabulario
    antigo. Sem `?estado=` nenhum, e a entrada: quem abre o painel quer
    ver o que chegou, e nao o acervo de 199 mil."""
    pedida = request.args.get("estado")
    if pedida is None:
        return ENTRADA_DA_ESCADA[0]
    pedida = pedida.strip()
    return ABAS_ANTIGAS.get(pedida, pedida)


@app.route("/")
def painel():
    """A lista, com as dez ranhuras da escada a apartar (§3.1 do
    docs/historico/CRM.md).

    Duas listas por baixo de uma barra de abas, e nao uma: as ranhuras
    das pontas e o "todos" mostram ANUNCIOS (o que o DR publicou, com o
    arsenal de filtros que 199 mil linhas obrigam); as oito da casa
    mostram PROPOSTAS (o que a casa decidiu, com as colunas que isso
    pede). Nao e uma inconsistencia -- sao populacoes diferentes: uma
    proposta de consulta previa nao tem anuncio nenhum para aparecer na
    primeira, e um anuncio por ver nao tem valor proposto para mostrar
    na segunda.
    """
    if aba_pedida() in CHAVES_DA_CASA:
        return _lista_de_propostas()
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
    estado_da_aba = aba_pedida()
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
        # Em que ranhura da escada esta cada anuncio DESTA pagina, num
        # mapa montado com UMA consulta. Um SELECT por linha dentro do
        # ciclo do HTML e o erro que as listas deste painel ja pagaram
        # uma vez -- e sao 20 linhas por pagina.
        na_escada = {}
        refs = [a["ref"] for a in linhas]
        if refs:
            for p in c.execute(
                    "SELECT * FROM propostas WHERE ref IN (%s) "
                    "ORDER BY COALESCE(lote, 0), id" % ",".join("?" * len(refs)),
                    refs):
                na_escada.setdefault(p["ref"], []).append(p)
        onde_sem_estado, val_sem_estado = condicoes(
            args_da_lista(request.args, estado=""))
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

    # A escada (15/09/2026): dez ranhuras mais o "todos", desenhadas
    # pela barra_das_abas() para as duas listas as terem iguais.
    estado_actual = estado_da_aba
    contas = contar_a_escada(onde_sem_estado, val_sem_estado, cfg)
    abas = [barra_das_abas(rota, estado_actual, contas)]

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
    opcoes_plat = [("", "todas as plataformas (%s)" % mil(no_filtro))]
    if porler:
        opcoes_plat.append((POR_LER, "ainda sem detalhe lido (%s)" % mil(porler_filtro)))
    # as plataformas que ja nao existem vao num balde so, "outras"
    # (14/09/2026); a contagem do balde e a soma delas dentro do filtro
    conta_agrupada = dict(agrupar_plataformas(conta_plat))
    opcoes_plat += [(p, "%s (%s)" % (rotulo_da_plataforma(p), mil(conta_agrupada.get(p, 0))))
                    for p, _ in agrupar_plataformas({r["p"]: r["n"] for r in plataformas})]

    prazo_actual = (request.args.get("prazo") or "").strip()
    # A janela do urgente le-se UMA vez por pedido: serve o rotulo do
    # selector e a etiqueta de prazo de cada linha, e dias_urgente() abre
    # o config.json a cada chamada.
    urgente = dias_urgente()
    opcoes_prazo = opcoes_html(
        (("", "prazo: tanto faz"),
         ("aberto", "só os que ainda dão para concorrer"),
         ("urgente", "só os que acabam em %d dias" % urgente),
         ("expirado", "só os de prazo passado")), prazo_actual)

    # Quatro campos (14/09/2026, a pedido do Afonso: «so quero nome do
    # anuncio ou objecto; entidade; plataforma; e data x a data y»). O
    # CPV vem da arvore, por cima, e escreve-se num campo escondido; o
    # "excluir CPV" fica escondido tambem, porque e onde a arvore poe o
    # que se desmarca dentro de uma divisao. Sairam do ecra "excluir
    # palavras", o E/OU e o prazo -- o motor continua a entende-los na
    # URL (um alerta antigo, a ligacao do cartao dos urgentes), e o que
    # vier por la passa em campos escondidos para nao se perder ao
    # voltar a filtrar.
    filtros = (
        "<form class='cx filtros' method='get' action='%s'>"
        "<input type='text' name='q' value='%s' placeholder='Nome do anúncio ou objecto…'>"
        "<input type='text' name='ent' value='%s' placeholder='Entidade que publica…' "
        "list='entidades' autocomplete='off' data-sugere='anuncios' data-chave-em='nif'>"
        "<input type='hidden' name='nif' value='%s'>"
        "<input type='hidden' id='filtro-cpv' name='cpv' value='%s'>"
        "<input type='hidden' id='filtro-cpv-excl' name='cpv_excl' value='%s'>"
        "%s"
        "<select name='plat'>%s</select>"
        "<label>de</label><input type='date' name='de' value='%s'>"
        "<label>até</label><input type='date' name='ate' value='%s'>"
        "<input type='hidden' name='estado' value='%s'>"
        "<button type='submit'>Filtrar</button>"
        "<a class='limpar' href='%s'>limpar</a>"
        "</form><datalist id='entidades'></datalist>"
        % (html.escape(rota, quote=True),
           html.escape(request.args.get("q", ""), quote=True),
           html.escape(request.args.get("ent", ""), quote=True),
           html.escape(re.sub(r"\D", "", request.args.get("nif", "")), quote=True),
           html.escape(cpv_actual, quote=True),
           html.escape(request.args.get("cpv_excl", ""), quote=True),
           campos_escondidos(request.args, ("q_excl", "op", "prazo")),
           opcoes_html(opcoes_plat, plat_actual),
           html.escape(request.args.get("de", ""), quote=True),
           html.escape(request.args.get("ate", ""), quote=True),
           html.escape(estado_actual, quote=True),
           html.escape(href_limpar(rota, estado_actual), quote=True)))

    # Com interesse definido a lista fica so com o filtro de texto (e os
    # selectores): a arvore e o "excluir CPV" saem, porque o CPV ja esta
    # decidido no Interesse (13/09/2026). Sem interesse, a arvore fica.
    ligado_i, dentro_i, _ = interesse_definido(cfg)
    com_interesse = bool(ligado_i and dentro_i)
    arvore = "" if com_interesse else arvore_html(n_cpv, "anuncios")

    filtro_em_uso = filtro_actual(request.args, "anuncios")
    if linhas:
        corpo_lista = ("<div class='lista'>"
                       + "".join(linha(a, estado_actual, urgente, na_escada)
                                 for a in linhas)
                       + "</div>")
    elif filtro_em_uso == "estado=" + estado_actual and escondidos_interesse:
        # Sem filtro nenhum, mas com o interesse a tapar: dizer "o que
        # entrou esta triado" com 1290 anuncios escondidos era uma
        # afirmacao falsa por cima da faixa que diz o contrario.
        corpo_lista = ("<div class='vazio'>Nada aqui <b>dentro do "
                       "interesse</b> &mdash; há %s de fora dele. "
                       "<a href='%s'>ver tudo</a> ou "
                       "<a href='/configuracoes/interesse'>mudar o interesse</a>."
                       "</div>"
                       % (mil(escondidos_interesse),
                          html.escape(sem_pagina(request.args, rota,
                                                 interesse="nao"),
                                      quote=True)))
    elif (estado_actual == ENTRADA_DA_ESCADA[0]
          and filtro_em_uso == "estado=" + ENTRADA_DA_ESCADA[0]):
        # O vazio proprio da entrada sem filtro: nada por decidir e
        # diferente de um filtro que nao apanhou nada.
        corpo_lista = ("<div class='vazio'>Nada por decidir: o que "
                       "entrou está triado, e o que expirou passou "
                       "sozinho para o <a href='/?estado=expirou'>"
                       "&ldquo;expirou sem ver&rdquo;</a>.</div>")
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
    if estado_actual == ENTRADA_DA_ESCADA[0]:
        conta += " &middot; só o que ainda dá para responder, e por decidir"
    elif estado_actual == CEMITERIO_DA_ESCADA[0]:
        conta += " &middot; o prazo passou e ninguém chegou a olhar"

    # Os avisos da ultima verificacao. O ficheiro AVISOS.txt serve para
    # quem nao tem o painel aberto; aqui e para quem tem, e da o caminho
    # para o filtro em vez de o obrigar a procurar.
    por_enviar = sum(len(x[1]) for x in alertas_por_enviar())
    if por_enviar:
        faixa_avisos = (
            "<div class='flash'><b>%s anúncio%s</b> nos teus alertas, "
            "por avisar. <a href='/configuracoes/alertas'>ver os alertas</a></div>"
            % (mil_pt(por_enviar), "" if por_enviar == 1 else "s"))
    else:
        faixa_avisos = ""

    # O rodape que repetia a hora da ultima verificacao e as horas
    # marcadas saiu: era o mesmo que a barra lateral ja diz, duas vezes
    # no mesmo ecra. O ponto verde/vermelho foi para la.

    # A ordem: a arvore em cima (14/09/2026), os campos, a faixa do CPV
    # activo. (Os filtros
    # guardados sairam da lista a 13/09/2026: o que era guardar um filtro
    # passou a ser o Interesse, e os alertas criam-se em Configuracoes.)
    # O CSV leva a marca da lista: o recorte da aba e da pagina e nao
    # do filtro, e sem isto o "exportar as N linhas" do por ver
    # exportava tambem os expirados -- o numero da ligacao mentia.
    qs = request.query_string.decode()
    qs_csv = (qs + "&" if qs else "") + urlencode({"ambito": "anuncios"})

    # Os blocos de filtro (campos, arvore) recolhidos
    # por omissao (UX-Auditoria, Hick/Tesler, decisao do Afonso a
    # 8/09/2026): a lista abria com 60% do ecra em filtros e 42 alvos
    # antes do primeiro anuncio, e a triagem e "ler o cartao, decidir".
    # Abrem sozinhos quando ha filtro aplicado; o resumo fica na linha.
    # O JS lembra-se de ter ficado aberto (localStorage).
    ha_filtro = filtro_em_uso != "estado=" + estado_actual
    painel_filtros = (
        "<details class='painel-filtros' id='painel-filtros'%s><summary>"
        "<span class='pf-tit'>Filtros</span>"
        "<span class='pf-sub'>%s</span></summary>"
        "%s</details>"
        % (" open" if ha_filtro else "",
           html.escape(resumo_filtro(filtro_em_uso, "anuncios")),
           arvore + filtros + faixa_cpv))
    conteudo = ("<div class='larg'>" + faixa_avisos +
                faixa_de_avisos_de_datas(request.args) +
                faixa_interesse + painel_filtros +
                "<div class='linha-conta'><span class='teclas' "
                "title='j/k: anúncio seguinte/anterior · i: interessa · "
                "a: abandonar · Enter: abrir a ficha'>j k i a &#9166;</span>"
                + conta +
                # dizer quantas linhas e que saem: a ligacao esta encostada
                # ao "1-20" e exportava as 66 mil sem avisar
                "<a href='/csv?%s'>exportar as %s linhas (CSV)</a></div>"
                % (html.escape(qs_csv, quote=True), mil(correspondem)) +
                corpo_lista + paginador(pagina, paginas, request.args, rota) +
                "</div>")

    return envolver(
        "anuncios", "Concursos",
        "Entra tudo o que o DR publica &mdash; e, da Vortal, as "
        "consultas preliminares. <b>Por ver</b> é o que ainda dá para "
        "responder e ainda ninguém decidiu; o que expira sem ninguém "
        "olhar passa sozinho para o fim da escada. As oito ranhuras do "
        "meio são o que a casa está a fazer.",
        conteudo, abas="".join(abas),
        script=("" if com_interesse else ARVORE_JS) + LISTA_JS + ENTIDADES_JS
        + caixa_do_motivo(),
        titulo_aba="Radar de Concursos, DR")


# --- a lista das oito ranhuras da casa (etapa 2 do CRM, 15/09/2026)
#
# A vista das propostas, por baixo da mesma barra de abas da lista dos
# anuncios. Sao tabelas diferentes de proposito (ver `painel()`): esta
# nao tem selector de CPV nem de plataforma, e nao e esquecimento. O
# arsenal de filtros da outra existe porque ha 199 mil anuncios e sem
# ele nao se encontra nada; um pipeline sao dezenas de linhas, e a
# procura por texto chega. Um selector de CPV por cima de doze linhas e
# um controlo que ninguem usa e que ocupa o primeiro ecra.

COLUNAS_DA_PIPELINE = ("Concurso", "Cliente", "Lote", "Preço base",
                       "Proposto", "Entrega", "Responsável", "Ranhura", "")


def _preco_da_proposta(p):
    """O numero que conta, e dito pelo que e. A partir do Submetido e o
    proposto; antes disso e o preco base -- e enquanto o proposto nao
    estiver preenchido mostra-se o base **dito como base**, que e
    diferente de o mostrar como se fosse a proposta."""
    if p["estado"] in ESTADOS_COM_PROPOSTO and p["valor_proposta"]:
        return html.escape(p["valor_proposta"])
    return "&mdash;"


def linha_da_pipeline(p, urgente, prazos):
    """Uma proposta na tabela. A ligacao e para a ficha do anuncio
    quando ha anuncio, e para a propria proposta quando nao ha (D2) --
    uma consulta previa nao tem ficha do DR para abrir."""
    prazo = prazos.get(p["ref"] or "")
    if prazo:
        texto_prazo, classe_prazo = etiqueta_prazo(prazo, urgente)
        # A partir do Submetido o prazo ter passado e o estado normal: a
        # proposta foi entregue. A pilula vermelha e a cor de alarme da
        # lista, e nao pode estar a puxar o olho para uma coisa que nao
        # pede accao nenhuma.
        if p["estado"] in ESTADOS_COM_PROPOSTO:
            col_prazo = ("%s <span class='tag'>entregue</span>"
                         % data_pt(prazo))
        else:
            col_prazo = ("%s <span class='tag %s'>%s</span>"
                         % (data_pt(prazo), classe_prazo,
                            html.escape(texto_prazo)))
    else:
        col_prazo = "&mdash;"
    if p["ref"]:
        alvo = "/anuncio/" + quote(p["ref"], safe="")
        nome = corta(p["titulo"] or p["ref"], 80)
    else:
        alvo = "/proposta/%d" % p["id"]
        nome = corta(p["titulo"] or "(sem título)", 80)
    return ("<tr><td class='o'><a href='%s'>%s</a>%s</td>"
            "<td class='g'>%s</td><td class='curta'>%s</td>"
            "<td class='p'>%s</td><td class='p'>%s</td>"
            "<td class='d'>%s</td><td class='curta'>%s</td>"
            "<td class='celula-ranhura'>%s</td><td class='curta'>%s</td></tr>"
            % (alvo, html.escape(nome),
               "" if p["ref"] else
               " <span class='tag info' title='%s'>sem anúncio</span>"
               % html.escape(p["porque_sem_ref"] or "não vem do DR", quote=True),
               html.escape(corta(p["entidade"] or "", 45)),
               "L%d" % p["lote"] if p["lote"] else
               ("conjunto" if p["lote"] == 0 else "&mdash;"),
               html.escape(p["preco_base"] or "") or "&mdash;",
               _preco_da_proposta(p), col_prazo,
               html.escape(p["responsavel"] or "") or "&mdash;",
               # a mesma escada da outra lista, e pela proposta: uma sem
               # anuncio nao tem `ref` por onde lhe pegar
               selector_de_ranhura("/proposta/%d/escada" % p["id"],
                                   p["estado"],
                                   titulo=p["titulo"] or p["entidade"] or ""),
               "<a href='%s'>abrir</a>" % alvo))


def _lista_de_propostas():
    """As propostas de uma ranhura da casa, em tabela.

    O que esta lista mostra e a outra nao: as propostas **sem anuncio**
    (D2 -- consulta previa, ajuste directo, convite) e o **lote** (D3).
    Sao as duas razoes de a tabela `propostas` existir; se esta vista as
    escondesse, a tabela nao servia para nada.
    """
    rota = "/"
    cfg = ler_config()
    estado_actual = aba_pedida()
    urgente = dias_urgente()
    procura = " ".join((request.args.get("q") or "").split())
    onde = ["estado = ?"]
    valores = [estado_actual]
    if procura:
        # Procura simples, e nao o motor: `condicoes()` serve tambem os
        # alertas e os filtros guardados, e nao se lhe acrescenta um
        # recorte desta vista (armadilha do motor de filtros).
        onde.append("(titulo LIKE ? ESCAPE ? OR entidade LIKE ? ESCAPE ?)")
        como = para_like(procura)
        valores += [como, ESCAPE_LIKE, como, ESCAPE_LIKE]
    with liga() as c:
        linhas = c.execute(
            "SELECT * FROM propostas WHERE " + " AND ".join(onde)
            + " ORDER BY COALESCE(fechada_em, criada_em) DESC, id DESC",
            valores).fetchall()
        # Os prazos vem dos anuncios, numa consulta so: um SELECT por
        # linha dentro do ciclo do HTML e o erro que as listas deste
        # painel ja pagaram uma vez.
        refs = [p["ref"] for p in linhas if p["ref"]]
        prazos = {}
        if refs:
            prazos = {r["ref"]: r["prazo"] for r in c.execute(
                "SELECT ref, prazo FROM anuncios WHERE ref IN (%s)"
                % ",".join("?" * len(refs)), refs)}
    contas = contar_a_escada(cfg=cfg)
    # A aba conta anuncios com proposta; esta lista traz tambem as que
    # nao tem anuncio nenhum. Os dois numeros podem discordar, e a regra
    # da casa manda dize-lo em vez de deixar o ecra a mentir baixinho.
    sem_anuncio = sum(1 for p in linhas if not p["ref"])
    if linhas:
        corpo = ("<div class='cx tab-cx'><table class='tab-contratos tab-lista'>"
                 "<thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>"
                 % ("".join("<th>%s</th>" % html.escape(t)
                            for t in COLUNAS_DA_PIPELINE),
                    "".join(linha_da_pipeline(p, urgente, prazos)
                            for p in linhas)))
    else:
        corpo = ("<div class='vazio'>Nada em &ldquo;%s&rdquo;. "
                 "Põe um concurso aqui a partir da ficha dele, ou "
                 "<a href='/proposta/nova'>cria uma proposta sem anúncio</a> "
                 "(consulta prévia, ajuste directo).</div>"
                 % html.escape(estado_da_casa(estado_actual)))
    conta = "%s %s" % (mil_pt(len(linhas)),
                       "proposta" if len(linhas) == 1 else "propostas")
    if sem_anuncio:
        conta += (" &middot; %s sem anúncio do DR (a aba conta só as que "
                  "têm)" % mil_pt(sem_anuncio))
    caixa = ("<form class='pf' method='get' action='/'>"
             "<input type='hidden' name='estado' value='%s'>"
             "<input type='search' name='q' value='%s' "
             "placeholder='procurar no título ou no cliente…'>"
             "<button type='submit'>procurar</button>%s</form>"
             % (html.escape(estado_actual, quote=True),
                html.escape(procura, quote=True),
                (" <a href='/?estado=%s'>limpar</a>" % estado_actual)
                if procura else ""))
    conteudo = ("<div class='larg'>" + caixa +
                "<div class='linha-conta'>" + conta +
                "<a href='/proposta/nova'>nova proposta</a></div>"
                + corpo + "</div>")
    return envolver(
        "anuncios", "Concursos",
        "O que a casa está a fazer. As propostas sem anúncio do DR "
        "&mdash; consulta prévia, ajuste directo, convite &mdash; "
        "vivem aqui e não na lista dos anúncios.",
        conteudo, abas=barra_das_abas(rota, estado_actual, contas),
        script=caixa_do_motivo(),
        titulo_aba="%s, Concursos" % estado_da_casa(estado_actual))


# Caractere de escape do LIKE. Usa-se "!" e nao a barra invertida de
# propósito: a barra teria de sobreviver ao literal de Python e ao literal
# de SQL ao mesmo tempo, e conta-las erra-se com facilidade.
ESCAPE_LIKE = "!"


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
                 "ent", "nif", "plat", "estado", "prazo",   # so os anuncios
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
                 "nif", "plat", "estado", "prazo"),
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
            valor = (ENTRADA_DA_ESCADA[0] if valor is None
                     else ABAS_ANTIGAS.get(valor.strip(), valor.strip()))
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
                 "ent": "entidade que publica", "nif": "NIF", "plat": "plataforma",
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


def quantos_cpv():
    with liga() as c:
        return c.execute("SELECT COUNT(*) n FROM cpv_dict").fetchone()["n"]


def arvore_html(n_cpv, de, submeter=True, aberta=False,
                botao="Aplicar seleccionados ao filtro", rodape=True):
    """A arvore de CPV, igual nos dois separadores.

    O `de` diz de onde vem a contagem de cada codigo (anuncios ou
    contratos) e vai no proprio elemento, num data-*: o JS e o mesmo nos
    dois sitios e le dali a rota que ha-de pedir. Duas copias do JS
    divergiam ao primeiro arranjo.

    `aberta`, `botao` e `rodape` sao do Interesse (13/09/2026): la a
    arvore e o ecra inteiro, ja aberta, o botao chama-se "Guardar o
    interesse" e grava logo, e o paragrafo do rodape nao entra.
    """
    quantos = {"anuncios": "anúncios", "contratos": "contratos"}[de]
    pe = ("<div class='arv-pe'>Marcar uma divisão apanha tudo o que está por "
          "baixo dela &mdash; ao filtro vai só o código do grupo, e os zeros à "
          "direita fazem o resto. <b>Desmarcar um código lá dentro tira só "
          "esse</b>: vai para &ldquo;excluir CPV&rdquo; e a divisão continua a "
          "contar, incluindo os anúncios que só trazem o código dela.</div>"
          if rodape else "")
    return (
        "<details class='arvore' data-de='%s'%s%s><summary>"
        "<span class='arv-tit'>Escolher CPV na árvore</span>"
        "<span class='arv-sub'>%s códigos &middot; contagens acumuladas "
        "de %s</span>"
        "<span class='arv-chip' id='arvore-chip'>nenhum seleccionado</span>"
        "</summary>"
        "<div class='arvore-topo'>"
        "<input type='text' id='arvore-busca' placeholder='filtrar a árvore, ex. software'>"
        "<button type='button' onclick='arvoreAplicar()'>%s</button>"
        "<button type='button' class='claro' onclick='arvoreLimpar()'>Limpar selecção</button>"
        "<span id='arvore-contagem'></span>"
        "</div>"
        "<div id='arvore-corpo'>a carregar…</div>"
        "%s</details>" % (de, "" if submeter else " data-submeter='nao'",
                          " open" if aberta else "",
                          mil_pt(n_cpv), quantos, html.escape(botao), pe))


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

    # A traducao de "texto com |" para SQL vive na banda `comum`
    # (frag_de_texto/frag_de_exclusao): e a mesma nas duas listas, e a
    # regra do LIKE sem acentos ja se pagou duas vezes. O que fica aqui
    # e so onde o fragmento entra -- e e isso que o op=ou precisa.
    frag_texto = frag_de_texto

    def procura(texto, coluna):
        frag, vals = frag_de_texto(texto, coluna)
        if frag:
            onde.append(frag)
            valores.extend(vals)

    def exclui(texto, coluna):
        frag, vals = frag_de_exclusao(texto, coluna)
        if frag:
            valores.extend(vals)
            onde.append(frag)

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
    # A entidade pelo NIF (14/09/2026: «as entidades nao estao agrupadas
    # por NIF?»). Quando a sugestao foi escolhida, o formulario manda o
    # NIF e o nome; filtra-se pelo NIF -- que apanha as varias grafias
    # -- e, para os anuncios que ainda vieram sem NIF (24%), pelas
    # mesmas grafias que esse NIF tem na base. O texto do nome fica so
    # para mostrar: com ele tambem, prendia-se a uma grafia so.
    nif = re.sub(r"\D", "", args.get("nif") or "")
    if nif:
        onde.append("(nif = ? OR entidade IN (SELECT DISTINCT entidade "
                    "FROM anuncios WHERE nif = ?))")
        valores.extend([nif, nif])
    else:
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
        elif plat == OUTRAS_PLATAFORMAS:
            # as que ja nao existem, todas num balde (14/09/2026)
            onde.append("(detalhe_lido = 1 AND plataforma IS NOT NULL AND "
                        "plataforma != '' AND plataforma NOT IN (%s))"
                        % ",".join("?" for _ in PLATAFORMAS_ACTIVAS))
            valores.extend(PLATAFORMAS_ACTIVAS)
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
        estado = ENTRADA_DA_ESCADA[0]
    estado = ABAS_ANTIGAS.get(estado, estado)
    if estado in CHAVES_DA_CASA:
        # Um filtro guardado (ou um alerta) que pede uma ranhura da casa.
        # Traduz-se para a proposta, que e onde esse estado passou a
        # viver a 15/09/2026. **Isto nao e o recorte da pagina** -- esse
        # continua de fora, no condicao_da_aba(): e um campo que quem
        # guardou o filtro escolheu, e cala-lo fazia o filtro deixar de
        # ver o que sempre viu. Deixar cair no `estado = ?` de baixo era
        # pior: 'interessa' ja nao e valor nenhum da coluna, e o alerta
        # passava a nao encontrar nada, em silencio.
        onde.append(SQL_PROPOSTA_NO_ESTADO)
        valores.append(estado)
    elif estado in (ENTRADA_DA_ESCADA[0], CEMITERIO_DA_ESCADA[0]):
        # As duas pontas sao anuncios 'novo'; o que as aparta e o prazo,
        # e isso e recorte da pagina, nao do motor.
        onde.append("estado = 'novo'")
    elif estado:
        onde.append("estado = ?"); valores.append(estado)
    else:
        # "todos" sao todos os PROCEDIMENTOS. Uma alteracao e a
        # republicacao de um anuncio que ja esta na lista, com o prazo
        # e o preco dela ja postos nele; mostra-la era contar o mesmo
        # concurso duas vezes -- e um alerta avisar dele duas vezes.
        onde.append("estado != 'alteracao'")
    return (" WHERE " + " AND ".join(onde) if onde else ""), valores


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
            "<a href='/configuracoes/interesse'>interesse</a>: <b>%s</b>%s%s"
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
    return _opcoes("proc", procs, actual, vazio)


# A caixa "Filtros guardados" que vivia aqui, nas tres listas, saiu a
# 13/09/2026 ("Mudancas na plataforma RADAR"): o que era guardar um
# filtro para o reaplicar passou a ser o Interesse, e o que era guardar
# um filtro para avisar passou a ser so "Criar alerta", em Configuracoes.
# A tabela filtros_guardados fica: e onde os alertas vivem.


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
    Com `alerta` a None mantem-se a marca que ja tinha. Desde 13/09/2026
    so o "Criar alerta" grava aqui, e grava com a marca posta -- um
    filtro sem alerta deixou de ter ecra. Devolve se ja existia.
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


@app.route("/filtros/<int:filtro_id>/apagar", methods=["POST"])
def filtro_apagar(filtro_id):
    """Apaga so o filtro. Nem os anuncios nem os contratos se mexem -- um
    filtro esconde, nao apaga, e tira-lo devolve a lista inteira."""
    with liga() as c:
        linha = c.execute("SELECT nome FROM filtros_guardados WHERE id=?",
                          (filtro_id,)).fetchone()
        c.execute("DELETE FROM filtros_guardados WHERE id=?", (filtro_id,))
        c.execute("DELETE FROM alertas_vistos WHERE filtro_id=?", (filtro_id,))
    return volta_para((request.form.get("volta") or "/configuracoes/alertas").strip(), "",
                      "Filtro apagado: %s" % linha["nome"] if linha else "")


# {fonte: (chave de frescura, corpo JSON)} -- ver cpv_json()
_CPV_CACHE = {}


def _contagens_cpv_anuncios():
    """(chave de frescura, {codigo8: quantos anuncios})."""
    with liga() as c:
        lidos = c.execute("SELECT COUNT(*) n FROM anuncios "
                          "WHERE detalhe_lido=1").fetchone()["n"]
        codigos = [re.sub(r"\D", "", pedaco)[:8]
                   for row in c.execute("SELECT cpv FROM anuncios WHERE cpv != ''")
                   for pedaco in row["cpv"].split(",")]
    return lidos, Counter(c8 for c8 in codigos if len(c8) == 8)


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
    """Triar um anuncio: po-lo na escada, tira-lo dela, ou dizer que nao
    se vai.

    Ate 15/09/2026 isto escrevia `anuncios.estado`. Agora **cria ou move
    uma proposta**, e o `anuncios.estado` fica so com o que o DR diz
    ('novo', 'alteracao'): a decisao da casa deixou de morar na linha do
    anuncio. Os nomes antigos da accao continuam a servir, porque as
    ligacoes e o teclado da lista os usam -- traduzem-se a entrada.
    """
    accao = ABAS_ANTIGAS.get(novo, novo)
    if accao not in CHAVES_DA_CASA and accao != ENTRADA_DA_ESCADA[0]:
        return volta_ao_referer("/")
    # Nao ir exige motivo, de ambito fechado (decisao do Afonso a
    # 01/09/2026). Passado um mes, "nao fomos" sozinho nao diz nada: nao
    # se sabe se foi o preco, se foi falta de certificacoes, nem se vale
    # a pena voltar a olhar para aquela entidade.
    # request.values e nao request.form: o "desfazer" leva o motivo
    # antigo na propria accao do formulario (?motivo=...), porque o aviso
    # vem pela query string.
    motivo = (request.values.get("motivo") or "").strip()
    permitidos = MOTIVOS_DO_ESTADO.get(accao)
    if permitidos and motivo not in permitidos:
        return _volta_com_aviso("Escolhe o motivo antes de continuar.")
    with liga() as c:
        actual = c.execute("SELECT estado, titulo, altera FROM anuncios "
                           "WHERE ref=?", (ref,)).fetchone()
    if not actual:
        return volta_ao_referer("/")
    if actual["estado"] == "alteracao":
        # A alteracao nao se tria: a decisao e do procedimento, e o
        # procedimento e o anuncio original -- que ja tem o prazo desta.
        with liga() as c:
            raiz = raiz_da_alteracao(c, ref, actual["altera"] or "")
        return _volta_com_aviso(
            "O anúncio %s é uma alteração do %s: decide-se na ficha dele."
            % (ref, raiz or "original"))

    existentes = propostas_de(ref)
    # O que havia ANTES le-se agora: depois de mover, o estado anterior
    # ja nao esta em lado nenhum senao no historico, e e dele que o
    # "desfazer" precisa.
    antes = existentes[0] if existentes else None
    antes_estado = antes["estado"] if antes else ""
    antes_motivo = (antes["motivo"] if antes else "") or ""

    if accao == ENTRADA_DA_ESCADA[0]:
        rotulo = _tirar_da_escada(ref, antes)
        if rotulo is None:
            return volta_ao_referer("/")
    else:
        ja_estava = bool(antes) and antes_estado == accao
        if antes:
            ok, recado = mover_proposta(antes["id"], accao)
            if not ok:
                return _volta_com_aviso(recado)
            id_ = antes["id"]
        else:
            id_ = criar_proposta(ref, estado=accao)
        # Sair de um estado com motivo limpa-o: um motivo pendurado numa
        # proposta que mudou de ranhura e uma mentira a espera de ser
        # lida.
        if motivo or permitidos:
            gravar_motivo(id_, motivo)
        if accao == "analisar" and not ja_estava:
            # Por na escada e o sinal de que vais mesmo trabalhar isto,
            # por isso as pecas vem sozinhas -- mas por uma fila, nao uma
            # thread por clique: triar vinte anuncios seguidos abria
            # vinte descargas de varios MB ao mesmo tempo. E so quando o
            # estado muda mesmo: com o botao a aparecer tambem em quem ja
            # la estava, cada clique repetido voltava a descarregar tudo.
            pedir_documentos(ref)
        rotulo = estado_da_casa(accao) + (" (%s)" % motivo if motivo else "")

    texto = "«%s»: %s." % (corta(actual["titulo"] or ref, 70), rotulo)
    # O caminho de volta. Se o estado anterior tinha motivo, o motivo vai
    # na accao do desfazer: sem ele o servidor recusava a reposicao.
    desfazer = None
    if antes_estado != accao:
        alvo = antes_estado or ENTRADA_DA_ESCADA[0]
        desfazer = "/estado/%s/%s" % (ref, alvo)
        if antes_motivo:
            desfazer += "?" + urlencode({"motivo": antes_motivo})
    return _volta_com_aviso(texto, desfazer)


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


@app.route("/responsavel/<path:ref>", methods=["POST"])
def definir_responsavel(ref):
    """Quem trata deste concurso.

    Escreve na PROPOSTA (15/09/2026): quem trata de um concurso e quem
    trata da proposta, e um anuncio por ver nao tem dono porque ainda nao
    ha nada para tratar. Se ainda nao houver proposta nenhuma, atribuir
    um responsavel E po-lo na escada -- que e o que o gesto quer dizer.
    """
    nome = criar_pessoa(request.form.get("nome")) if request.form.get("nome") else ""
    existentes = propostas_de(ref)
    if not existentes:
        if not nome:
            return volta_ao_referer("/anuncio/" + ref)
        existentes = [proposta(criar_proposta(ref))]
    with liga() as c:
        c.execute("UPDATE propostas SET responsavel=? WHERE ref=?", (nome, ref))
    registar(ref, "responsável", nome or "(ninguém)")
    return volta_ao_referer("/anuncio/" + ref)


def celula_csv(valor):
    """Uma celula de texto que o Excel nao executa. Um objecto de
    anuncio que comece por =, +, - ou @ era uma formula ao abrir o CSV
    (auditoria de 14/09/2026): leva um apostrofo a frente, que o Excel
    mostra como texto. Os numeros nao passam por aqui."""
    if isinstance(valor, str) and valor[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + valor
    return valor


def linha_csv(escritor, valores):
    escritor.writerow([celula_csv(v) for v in valores])


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
        estado = aba_pedida()
        onde, valores = com_recorte(
            *condicoes(args_da_lista(request.args, estado="")),
            *recorte_da_lista(estado))
    else:
        onde, valores = condicoes(request.args)
    with liga() as c:
        linhas = c.execute(
            "SELECT ref,data_pub,tipo,entidade,titulo,cpv,prazo,preco_base,"
            "estado,url, (SELECT p.estado || COALESCE(' (' || p.motivo || ')','')"
            " FROM propostas p WHERE p.ref = anuncios.ref ORDER BY p.id LIMIT 1)"
            " AS na_casa FROM anuncios" + onde +
            " ORDER BY data_pub DESC", valores).fetchall()
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";")
    # "Triagem" e nao "Estado": e o rotulo do grupo por ver/interessa/
    # descartados em todo o lado (§7 do ESQUELETO) — "estado" reserva-se
    # para sistema e itens (peças, leitura).
    linha_csv(escritor, ["Anúncio", "Publicado", "Tipo", "Entidade", "Objecto",
                       "CPV", "Prazo", "Preço base (EUR)", "Triagem",
                       "Motivo do abandono", "Endereço"])
    for a in linhas:
        # Datas em DD/MM/AAAA como no resto da aplicacao -- o ISO e para a
        # base, e um CSV e para ver -- e o preco como um numero que o
        # Excel portugues some. "1.326.675,00 EUR" era texto para ele.
        # O estado idem: "novo" e chave interna que nenhum ecra mostra;
        # a coluna diz "por ver", como os separadores.
        linha_csv(escritor, [a["ref"], data_pt(a["data_pub"]), a["tipo"],
                           a["entidade"], a["titulo"], a["cpv"],
                           data_pt(a["prazo"]), numero_csv(a["preco_base"]),
                           estado_da_casa((a["na_casa"] or "").split(" (")[0])
                           or _NOMES_ESTADO.get(a["estado"], a["estado"]),
                           (a["na_casa"] or "").partition(" (")[2].rstrip(")"),
                           a["url"]])
    return resposta_csv(saida, "anuncios")




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

@app.route("/alertas/interesse")
def interesse():
    """Passou a Configuracoes > Interesse (8/09/2026); redirecciona."""
    qs = request.query_string.decode()
    return redirect("/configuracoes/interesse" + ("?" + qs if qs else ""))


def _conteudo_interesse():
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
    # So a arvore, ja aberta (13/09/2026): o que esta guardado vem
    # semeado nela, e o botao da arvore grava. Uma linha diz o que esta
    # em vigor -- sem ela, "Guardar" nao deixava rasto nenhum no ecra.
    if apanha_ver is None:
        estado = ("<div class='nota' style='margin:0 0 12px'>Ainda sem "
                  "interesse: a <a href='/'>lista de anúncios</a> mostra "
                  "tudo. Marca os CPV e carrega em &ldquo;Guardar o "
                  "interesse&rdquo;.</div>")
    else:
        estado = ("<div class='nota' style='margin:0 0 12px'>Em vigor: "
                  "<b>%s</b>%s &mdash; apanha <b>%s</b> dos anúncios por ver "
                  "e <b>%s</b> do acervo. A <a href='/'>lista</a> mostra só "
                  "isto, em todas as abas.</div>"
                  % (html.escape(dentro),
                     (", sem <b>%s</b>" % html.escape(fora)) if fora else "",
                     mil_pt(apanha_ver), mil_pt(apanha_tudo)))
    formulario = (
        "<div class='cx novo-filtro'>%s"
        "<form method='post' action='/alertas/interesse' class='filtros'>"
        "<input type='hidden' id='filtro-cpv' name='cpv' value='%s'>"
        "<input type='hidden' id='filtro-cpv-excl' name='cpv_excl' value='%s'>"
        "</form>%s</div>"
        % (estado, html.escape(dentro, quote=True), html.escape(fora, quote=True),
           arvore_html(n_cpv, "anuncios", aberta=True,
                       botao="Guardar o interesse", rodape=False)))
    return formulario


@app.route("/alertas/interesse", methods=["POST"])
def interesse_gravar():
    """Grava o interesse. Desde 13/09/2026 nao ha caixa de ligar: com
    CPV escolhido esta ligado, com a arvore vazia esta desligado. (A
    chave `interesse_activo` fica no config.json porque e ela que
    condicao_do_interesse() e os testes leem.)"""
    dentro = " ".join((request.form.get("cpv") or "").split())
    fora = " ".join((request.form.get("cpv_excl") or "").split())
    activo = bool(dentro)
    gravar_config({"interesse_activo": activo, "interesse_cpv": dentro,
                   "interesse_cpv_excl": fora})
    if activo:
        aviso = "Interesse guardado: a lista de anúncios passa a mostrar só %s." % dentro
    else:
        aviso = "Interesse vazio: a lista de anúncios volta a mostrar tudo."
    return redirect("/configuracoes/interesse?" + urlencode({"aviso": aviso}))


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
        "onsubmit='return confirm(\"Apagar o alerta &quot;%s&quot;? "
        "Não se apaga nada além do alerta.\")'>"
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
    senha_por_variavel = bool((os.environ.get("RADAR_EMAIL_SENHA") or "").strip())
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

    # O tester ve so o destino e a hora (13/09/2026); a conta que envia
    # e do sistema, e so o admin a ve -- a porta recusa-lhe o POST.
    if not sou_admin():
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
            "</form></div>"
            % (html.escape(str(e.get("para") or ""), quote=True),
               html.escape(str(e.get("hora_resumo") or "17:00"), quote=True)))
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
        "<div class='nota' style='margin-bottom:14px'>A conta que manda o "
        "resumo. A palavra-passe grava-se no <code>email_senha.txt</code>, "
        "nunca no <code>config.json</code>; o campo fica vazio de "
        "propósito e só escreve se puseres uma nova.%s</div>"
        "<form class='form-email' method='post' action='/alertas/remetente'>"
        "<label>Conta que envia<input type='email' name='de' value='%s' "
        "placeholder='o.teu@gmail.com'></label>"
        "<label>Servidor<input type='text' name='servidor' value='%s' "
        "placeholder='smtp.gmail.com'></label>"
        "<label>Porta<input type='text' name='porta' value='%s'></label>"
        "<label>Palavra-passe<input type='password' name='senha' value='' "
        "autocomplete='new-password'%s></label>"
        "<button type='submit' class='bt forte'>Guardar</button>"
        "</form>"
        "<div class='saude'>%s</div>%s</div>"
        % (html.escape(str(e.get("para") or ""), quote=True),
           html.escape(str(e.get("hora_resumo") or "17:00"), quote=True),
           (" Está definida pela variável de ambiente e não se edita aqui."
            if senha_por_variavel else ""),
           html.escape(str(e.get("de") or ""), quote=True),
           html.escape(str(e.get("servidor") or ""), quote=True),
           html.escape(str(e.get("porta") or "587"), quote=True),
           " disabled" if senha_por_variavel else "",
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
        return redirect("/configuracoes/alertas?aviso=" +
                        quote("“%s” não é um número de dias." % bruto))
    if not 1 <= n <= 90:
        return redirect("/configuracoes/alertas?aviso=" +
                        quote("A janela do urgente vai de 1 a 90 dias."))
    gravar_config({"dias_urgente": n})
    return redirect("/configuracoes/alertas?aviso=" +
                    quote("Urgente passa a ser: prazo a menos de %d dias."
                          % n))


@app.route("/alertas")
def alertas():
    """A pagina passou a Configuracoes > Alertas (8/09/2026). A rota
    fica a redireccionar com a query string atras, para os avisos dos
    POST antigos e as ligacoes guardadas continuarem a abrir."""
    qs = request.query_string.decode()
    return redirect("/configuracoes/alertas" + ("?" + qs if qs else ""))


def _conteudo_alertas():
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
        plataformas = [p for p, _ in agrupar_plataformas(
            {r["p"]: r["n"] for r in c.execute(
                "SELECT plataforma p, COUNT(*) n FROM anuncios "
                "WHERE plataforma IS NOT NULL AND plataforma != '' GROUP BY p")})]
    # Os tipos de procedimento sao do corpus, e o corpus pode nao existir.
    procs = tipos_de_procedimento()[:25]

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
        lista = ("<div class='vazio'>Ainda não há alertas. Cria um aqui em "
                 "baixo: o que entrar e corresponder vai no resumo por "
                 "e-mail.</div>")

    # O que se tinha escrito quando a validacao recusou: vem na query
    # string do redirect e volta para os campos, em vez de se perder.
    def pv(campo):
        return html.escape(request.args.get(campo, ""), quote=True)

    def marca_sel(campo, valor, omissao=""):
        return " selected" if request.args.get(campo, omissao) == valor else ""

    # Criar um filtro aqui, sem ter de ir a uma lista primeiro.
    novo = (
        "<div class='cx novo-filtro'><div class='rot'>Filtro de alertas</div>"
        "<div class='nota' style='margin:6px 0 14px'>Um alerta é um "
        "conjunto de campos: o que entrar e corresponder vai no resumo "
        "por e-mail. Um alerta por CPV ou por palavras avisa dos "
        "anúncios; os campos dos contratos (quem ganhou, valor) não "
        "avisam de nada.</div>"
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
        # Os mesmos campos da lista de anuncios (14/09/2026, a pedido do
        # Afonso), mais o nome: e por estes que o alerta avisa. A arvore
        # de CPV vem por cima e escreve no campo do CPV, que aqui fica a
        # ver -- nao ha lista por baixo a mostrar o resultado. Sairam
        # "excluir palavras", "excluir CPV" (fica escondido, e onde a
        # arvore poe o que se desmarca), o E/OU, a triagem, o prazo e o
        # grupo dos contratos, que nao avisava de nada.
        "%s"
        "<form method='post' action='/alertas/criar' class='filtros'>"
        "<input type='text' name='nome' required maxlength='60' value='%s' "
        "placeholder='nome do alerta…'>"
        "<input type='text' name='q' value='%s' placeholder='Nome do anúncio ou objecto…'>"
        "<input type='text' id='filtro-cpv' name='cpv' value='%s' readonly "
        "placeholder='CPV — escolhe na árvore aqui em cima'>"
        "<input type='hidden' id='filtro-cpv-excl' name='cpv_excl' value='%s'>"
        "<input type='text' name='ent' value='%s' placeholder='Entidade que "
        "publica…' list='entidades' autocomplete='off' data-sugere='anuncios' "
        "data-chave-em='nif'>"
        "<input type='hidden' name='nif' value='%s'>"
        "<select name='plat'>%s</select>"
        "<label>de</label><input type='date' name='de' value='%s'>"
        "<label>até</label><input type='date' name='ate' value='%s'>"
        "<button type='submit'>Criar alerta</button>"
        "</form><datalist id='entidades'></datalist></div>"
        % (arvore_html(quantos_cpv(), "anuncios", submeter=False),
           pv("nome"), pv("q"), pv("cpv"), pv("cpv_excl"), pv("ent"), pv("nif"),
           "".join(["<option value=''>plataforma: qualquer uma</option>"]
                   + ["<option value='%s'%s>%s</option>"
                      % (html.escape(p, quote=True), marca_sel("plat", p),
                         html.escape(rotulo_da_plataforma(p)))
                      for p in plataformas]
                   + ["<option value='%s'%s>sem plataforma indicada</option>"
                      % (html.escape(SEM_PLATAFORMA, quote=True),
                         marca_sel("plat", SEM_PLATAFORMA)),
                      "<option value='%s'%s>ainda sem detalhe lido</option>"
                      % (html.escape(POR_LER, quote=True),
                         marca_sel("plat", POR_LER))]),
           pv("de"), pv("ate")))

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

    conteudo = ("<div class='larg'>" + lista +
                caixa_seguidas +
                "<div style='height:16px'></div>" + novo +
                "<div style='height:16px'></div>" + _caixa_email(cfg) +
                _caixa_urgente() +
                "<div class='rot' style='margin:22px 0 12px'>Últimos avisos"
                "</div>" + historico + "</div>")

    return conteudo


# ------------------------------------- configuracoes (ONLINE.md, etapa 2)
#
# Uma rota por seccao, cada uma UM formulario que grava uma coisa e
# volta a dizer o que ficou -- nao e um formulario unico com tudo: quem
# grava o e-mail nao quer arriscar as horas da recolha pelo caminho.
# Cada gravacao passa por gravar_config_registado(), que junta sem
# apagar o resto E deixa no historico (ref='') a chave e os valores
# antes e depois: "desde quando e que isto esta assim?" tem resposta.
# As chaves e a palavra-passe do e-mail NUNCA vao ao config.json --
# escrevem-se nos ficheiros de sempre (ler_chave() le-os), e quando
# vem por variavel de ambiente o ecra di-lo e nao deixa editar.

# (chave, titulo, descricao, so_admin). A ordem e a do documento de
# 13/09/2026: primeiro o que e de quem usa (conta, interesse, alertas,
# importar), depois o que e do sistema, que so o admin ve.
SECCOES_CONFIG = (
    ("conta", "Conta", "palavra-passe, sessões, a nossa empresa, utilizadores", False),
    ("interesse", "Interesse", "os CPV que a casa trabalha", False),
    ("alertas", "Alertas", "filtros de alerta, entidades, o resumo por e-mail", False),
    ("importar", "Importar dados", "o registo da casa, pelo modelo Excel", False),
    ("indicadores", "Indicadores", "a saúde do sistema e os números", True),
    ("capturas", "Capturas", "os dois pedidos ao DR", True),
    ("recolha", "Recolha", "horas, janelas, a Vortal", True),
    ("leitura", "Leitura das peças", "fornecedor, modelo e chaves", True),
    ("copias", "Cópias", "a cópia diária e a triagem no git", True),
)


def seccoes_visiveis():
    """As seccoes que quem esta pode abrir: todas ao admin, as quatro
    primeiras ao tester. A porta (ROTAS_SO_ADMIN) e quem recusa; isto
    e so o indice."""
    return [sc for sc in SECCOES_CONFIG if not sc[3] or sou_admin()]

# O que fica no config.json de proposito, sem formulario: termos de
# pesquisa e de reserva, paginas, por_pagina, abrir_browser_ao_encontrar,
# acesso_livre_local, endereco_publico. Sao afinacao de quem mexe no
# codigo, e um campo para cada um seria ruido sem uso previsto.
CHAVES_PROIBIDAS_NO_CONFIG = ("senha", "palavra_passe", "api_key", "chave",
                              "token", "password")


def gravar_config_registado(mudancas, quem=None):
    """gravar_config() com o rasto: uma linha de historico por chave que
    mudou, com o antes e o depois. Recusa chaves que parecem segredos
    -- e a guarda contra uma palavra-passe acabar no config.json."""
    for chave in mudancas:
        if any(p in chave.lower() for p in CHAVES_PROIBIDAS_NO_CONFIG):
            raise ValueError("a chave %r não pode ir para o config.json" % chave)
    antes = ler_config()
    depois = gravar_config(mudancas)
    for chave, valor in mudancas.items():
        if isinstance(valor, dict):
            for sub, v in valor.items():
                velho = (antes.get(chave) or {}).get(sub)
                if velho != v:
                    registar("", "configuração", "%s.%s: %s → %s"
                             % (chave, sub, json.dumps(velho, ensure_ascii=False),
                                json.dumps(v, ensure_ascii=False)), quem=quem)
        elif antes.get(chave) != valor:
            registar("", "configuração", "%s: %s → %s"
                     % (chave, json.dumps(antes.get(chave), ensure_ascii=False),
                        json.dumps(valor, ensure_ascii=False)), quem=quem)
    return depois


def pagina_config(seccao, conteudo, script=""):
    """O esqueleto comum: o indice das seccoes a esquerda, preso ao
    rolar como o da ficha, e a seccao a direita."""
    titulo = dict((c, t) for c, t, _, _ in SECCOES_CONFIG)[seccao]
    indice = "".join(
        "<a class='%s' href='/configuracoes/%s'><b>%s</b><i>%s</i></a>"
        % ("on" if c == seccao else "", c, html.escape(t), html.escape(d))
        for c, t, d, _ in seccoes_visiveis())
    return envolver(
        "configuracoes", titulo,
        "Dizer ao radar como quero que ele trabalhe. Cada secção grava "
        "só o que mostra.",
        "<div class='conf'><nav class='conf-indice'>%s</nav>"
        "<div class='conf-corpo'>%s</div></div>" % (indice, conteudo),
        migalhas=migalhas_de("configuracoes", titulo), script=script,
        titulo_aba="%s, Configurações" % titulo)


def volta_config(seccao, aviso):
    return redirect("/configuracoes/%s?%s" % (seccao, urlencode({"aviso": aviso})))


def _campo(rotulo, nome, valor, tipo="text", nota="", extra=""):
    return ("<label class='conf-campo'><span>%s</span>"
            "<input type='%s' name='%s' value='%s'%s>%s</label>"
            % (html.escape(rotulo), tipo, nome, html.escape(str(valor), quote=True),
               (" " + extra) if extra else "",
               ("<small>%s</small>" % nota) if nota else ""))


def _interruptor(rotulo, nome, ligado, nota=""):
    return ("<label class='conf-campo conf-check'><input type='checkbox' "
            "name='%s' value='1'%s><span>%s</span>%s</label>"
            % (nome, " checked" if ligado else "", html.escape(rotulo),
               ("<small>%s</small>" % nota) if nota else ""))


def _inteiro(form, nome, minimo, maximo, rotulo):
    """Um inteiro do formulario dentro de limites, ou ValueError com a
    frase para o ecra. Uma janela de detalhe de 0 dias cala a recolha
    em silencio -- e por isso que ha limites e nao so int()."""
    bruto = (form.get(nome) or "").strip()
    try:
        n = int(bruto)
    except ValueError:
        raise ValueError("«%s» não é um número (%s)." % (bruto, rotulo))
    if not minimo <= n <= maximo:
        raise ValueError("%s vai de %d a %d." % (rotulo, minimo, maximo))
    return n


@app.route("/configuracoes")
def configuracoes():
    return redirect("/configuracoes/conta")


@app.route("/configuracoes/alertas")
def config_alertas():
    return pagina_config("alertas", _conteudo_alertas(), script=ARVORE_JS + ENTIDADES_JS)


@app.route("/configuracoes/interesse")
def config_interesse():
    return pagina_config("interesse", _conteudo_interesse(), script=ARVORE_JS)


@app.route("/alertas/remetente", methods=["POST"])
def alertas_remetente():
    """Quem envia o resumo: conta, servidor, porta para o config.json;
    a palavra-passe para o email_senha.txt, e so se vier preenchida."""
    de = (request.form.get("de") or "").strip()
    servidor = (request.form.get("servidor") or "").strip()
    try:
        porta = _inteiro(request.form, "porta", 1, 65535, "a porta")
    except ValueError as erro:
        return volta_config("alertas", str(erro))
    gravar_config_registado({"email": {"de": de, "servidor": servidor,
                                       "porta": porta}})
    senha = request.form.get("senha") or ""
    if senha.strip() and not (os.environ.get("RADAR_EMAIL_SENHA") or "").strip():
        with open(os.path.join(BASE_DIR, "email_senha.txt"), "w",
                  encoding="utf-8") as f:
            f.write(senha.strip() + "\n")
        so_o_dono(os.path.join(BASE_DIR, "email_senha.txt"))
        registar("", "configuração", "email_senha.txt: palavra-passe nova")
    return volta_config("alertas", "Conta que envia guardada.")


@app.route("/configuracoes/recolha", methods=["GET", "POST"])
def config_recolha():
    cfg = ler_config()
    if request.method == "POST":
        try:
            horas = []
            for h in (request.form.get("horas") or "").replace(";", ",").split(","):
                h = h.strip()
                if not h:
                    continue
                if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", h):
                    raise ValueError("«%s» não é uma hora HH:MM." % h)
                horas.append(h)
            if not horas:
                raise ValueError("É precisa pelo menos uma hora de verificação.")
            mudancas = {
                "horas_verificacao": sorted(set(horas)),
                "dias_catchup": _inteiro(request.form, "dias_catchup", 0, 90,
                                         "a janela de recuperação"),
                "detalhe_dias": _inteiro(request.form, "detalhe_dias", 1, 3650,
                                         "a janela do detalhe"),
                "detalhes_por_volta": _inteiro(request.form, "detalhes_por_volta",
                                               1, 500, "detalhes por volta"),
                "relidos_por_volta": _inteiro(request.form, "relidos_por_volta",
                                              0, 200, "relidos por volta"),
                "vortal_preliminares": bool(request.form.get("vortal_preliminares")),
                "recuperar_slot_falhado": bool(request.form.get("recuperar_slot_falhado")),
            }
        except ValueError as erro:
            return volta_config("recolha", str(erro))
        gravar_config_registado(mudancas)
        return volta_config("recolha", "Recolha guardada. As horas novas "
                            "valem no relógio interno já; os temporizadores "
                            "do sistema mudam com o agendar.sh.")
    faltam = tarefas_em_falta()
    corpo = (
        "<form method='post' action='/configuracoes/recolha' class='conf-form'>"
        + _campo("Horas da verificação", "horas",
                 ", ".join(cfg.get("horas_verificacao") or []),
                 nota="HH:MM, separadas por vírgula. É o relógio interno do painel; "
                      "as tarefas do sistema (systemd) têm as suas, criadas pelo agendar.sh.")
        + _campo("Janela de recuperação (dias)", "dias_catchup", cfg.get("dias_catchup", 15),
                 nota="quantos dias para trás o radar volta a olhar quando falha um slot")
        + _campo("Janela do detalhe (dias)", "detalhe_dias", cfg.get("detalhe_dias", 60),
                 nota="a rotina só lê o detalhe (CPV, prazo, preço) dos anúncios destes últimos dias")
        + _campo("Detalhes por volta", "detalhes_por_volta", cfg.get("detalhes_por_volta", 40))
        + _campo("Relidos por volta", "relidos_por_volta", cfg.get("relidos_por_volta", 25),
                 nota="anúncios interessa/quadro com prazo aberto que se releem para apanhar alterações")
        + _interruptor("Trazer as consultas preliminares da Vortal", "vortal_preliminares",
                       cfg.get("vortal_preliminares", True))
        + _interruptor("Recuperar um slot falhado na verificação seguinte",
                       "recuperar_slot_falhado", cfg.get("recuperar_slot_falhado", True))
        + "<button type='submit' class='bt forte'>Guardar</button></form>"
        + ("<div class='flash mau' style='margin-top:16px'>As tarefas agendadas "
           "estão por criar (%s): corre o agendar.sh.</div>"
           % html.escape(", ".join(faltam)) if faltam else
           "<div class='nota' style='margin-top:16px'>As tarefas agendadas do "
           "sistema estão criadas.</div>"))
    return pagina_config("recolha", "<div class='cx conf-cx'>" + corpo + "</div>")


def _estado_da_chave(nomes, variavel):
    """(texto, esta_bem, por_variavel) para o ecra das chaves."""
    if (os.environ.get(variavel) or "").strip():
        return "definida pela variável %s" % variavel, True, True
    for nome in nomes:
        caminho = os.path.join(BASE_DIR, nome)
        if os.path.exists(caminho):
            try:
                with open(caminho, encoding="utf-8") as f:
                    if f.read().strip():
                        return ("no %s desde %s" % (
                            nome, datetime.fromtimestamp(
                                os.path.getmtime(caminho)).strftime("%d/%m/%Y")),
                            True, False)
            except OSError:
                pass
    return "falta", False, False


@app.route("/configuracoes/leitura", methods=["GET", "POST"])
def config_leitura():
    cfg = ler_config()
    nomes_forn = [f[0] for f in FORNECEDORES]
    if request.method == "POST":
        forn = (request.form.get("fornecedor_pecas") or "").strip()
        if forn and forn not in nomes_forn:
            return volta_config("leitura", "Fornecedor desconhecido: %s" % forn)
        modelos = dict(cfg.get("modelos_pecas") or {})
        for nome in nomes_forn:
            modelos[nome] = (request.form.get("modelo_" + nome) or "").strip()
        gravar_config_registado({"fornecedor_pecas": forn, "modelos_pecas": modelos})
        # as chaves: so as que vieram preenchidas, e nunca por cima de
        # uma variavel de ambiente
        escritas = []
        for nome, _, _, ficheiros, variavel, _ in FORNECEDORES:
            nova = (request.form.get("chave_" + nome) or "").strip()
            if nova and not (os.environ.get(variavel) or "").strip():
                with open(os.path.join(BASE_DIR, ficheiros[-1] if nome != "groq"
                                       else "groq_API_KEY.txt"), "w",
                          encoding="utf-8") as f:
                    f.write(nova + "\n")
                so_o_dono(f.name)
                escritas.append(nome)
                registar("", "configuração", "chave de %s: nova" % nome)
        return volta_config("leitura", "Leitura das peças guardada%s."
                            % (" e chave%s de %s gravada%s"
                               % ("s" if len(escritas) > 1 else "",
                                  ", ".join(escritas),
                                  "s" if len(escritas) > 1 else "")
                               if escritas else ""))
    opcoes = "".join(
        "<option value='%s'%s>%s</option>"
        % (v, " selected" if v == (cfg.get("fornecedor_pecas") or "") else "", t)
        for v, t in [("", "a cadeia, por ordem (Groq → NVIDIA → OpenRouter)")]
        + [(n, n) for n in nomes_forn])
    linhas = []
    for nome, _, omissao, ficheiros, variavel, _ in FORNECEDORES:
        texto, bem, por_var = _estado_da_chave(ficheiros, variavel)
        linhas.append(
            "<div class='conf-forn'><div class='rot'>%s</div>"
            "<div class='saude'>%s</div>%s%s</div>"
            % (html.escape(nome),
               linhas_de_saude([("Chave", html.escape(texto), bem)], "#d68910"),
               _campo("Modelo", "modelo_" + nome,
                      modelo_do_fornecedor(cfg, nome, omissao),
                      nota="de origem: %s" % html.escape(omissao)),
               "" if por_var else
               _campo("Chave nova", "chave_" + nome, "", tipo="password",
                      nota="só escreve se puseres uma; fica no %s" % ficheiros[-1],
                      extra="autocomplete='new-password'")))
    corpo = (
        "<form method='post' action='/configuracoes/leitura' class='conf-form'>"
        "<label class='conf-campo'><span>Fornecedor em uso</span>"
        "<select name='fornecedor_pecas'>%s</select>"
        "<small>Cada pedido desce a cadeia até alguém responder; escolher "
        "um fixa-o como primeiro.</small></label>%s"
        "<button type='submit' class='bt forte'>Guardar</button></form>"
        % (opcoes, "".join(linhas)))
    return pagina_config("leitura", "<div class='cx conf-cx'>" + corpo + "</div>")


def _estado_da_captura(nome_base):
    caminho = os.path.join(BASE_DIR, nome_base + ".txt")
    if not os.path.exists(caminho):
        return "em falta", False
    texto = carregar_curl(nome_base)
    try:
        pedido = parse_curl(texto) if texto else None
    except ValueError:
        pedido = None
    if not pedido or not pedido.get("headers"):
        return "ilegível — refaz a captura", False
    idade = datetime.fromtimestamp(os.path.getmtime(caminho))
    return ("válida, de %s (%d cabeçalhos)"
            % (idade.strftime("%d/%m/%Y"), len(pedido["headers"])), True)


@app.route("/configuracoes/capturas", methods=["GET", "POST"])
def config_capturas():
    if request.method == "POST":
        qual = (request.form.get("qual") or "").strip()
        if qual not in ("curl_DR", "curl_detalhe"):
            return volta_config("capturas", "Captura desconhecida.")
        texto = (request.form.get("texto") or "").strip()
        # valida-se ANTES de tocar no ficheiro: uma colagem a meio nao
        # pode deixar a recolha sem captura nenhuma
        try:
            pedido = parse_curl(texto) if texto else None
        except ValueError as erro:
            pedido = None
            porque = str(erro)
        else:
            porque = "não parece um «Copy as cURL»"
        if not pedido or not pedido.get("headers"):
            return volta_config("capturas", "Não gravei: %s." % porque)
        if qual == "curl_DR" and not pedido.get("body"):
            return volta_config("capturas", "Não gravei: a captura da pesquisa "
                                "tem de trazer o corpo do pedido (--data-raw).")
        with open(os.path.join(BASE_DIR, qual + ".txt"), "w", encoding="utf-8") as f:
            f.write(texto + "\n")
        so_o_dono(os.path.join(BASE_DIR, qual + ".txt"))
        registar("", "configuração", "%s.txt: captura nova (%d cabeçalhos)"
                 % (qual, len(pedido["headers"])))
        return volta_config("capturas", "Captura %s.txt gravada." % qual)
    blocos = []
    for nome_base, titulo, nota in (
            ("curl_DR", "curl_DR.txt — a pesquisa",
             "o pedido da lista de anúncios; leva o corpo (--data-raw)"),
            ("curl_detalhe", "curl_detalhe.txt — o detalhe",
             "o pedido da página de um anúncio")):
        texto, bem = _estado_da_captura(nome_base)
        blocos.append(
            "<div class='conf-forn'><div class='rot'>%s</div>"
            "<div class='nota' style='margin:6px 0 10px'>%s. Como se faz a "
            "captura está no LEIA-ME, secção 3.</div>"
            "<div class='saude'>%s</div>"
            "<form method='post' action='/configuracoes/capturas' class='conf-form'>"
            "<input type='hidden' name='qual' value='%s'>"
            "<textarea name='texto' rows='5' placeholder='cola aqui o Copy as cURL'></textarea>"
            "<button type='submit' class='bt forte'>Gravar esta captura</button>"
            "</form></div>"
            % (html.escape(titulo), html.escape(nota),
               linhas_de_saude([("Estado", html.escape(texto), bem)]),
               nome_base))
    return pagina_config("capturas", "<div class='cx conf-cx'>" + "".join(blocos) + "</div>")


@app.route("/configuracoes/copias", methods=["GET", "POST"])
def config_copias():
    cfg = ler_config()
    if request.method == "POST":
        try:
            mudancas = {
                "copia_de_seguranca": bool(request.form.get("copia_de_seguranca")),
                "copias_a_guardar": _inteiro(request.form, "copias_a_guardar", 1, 60,
                                             "cópias a guardar"),
                "triagem_no_git": bool(request.form.get("triagem_no_git")),
            }
        except ValueError as erro:
            return volta_config("copias", str(erro))
        gravar_config_registado(mudancas)
        return volta_config("copias", "Cópias guardadas.")
    existentes = []
    if os.path.isdir(COPIAS):
        for nome in sorted(os.listdir(COPIAS), reverse=True):
            caminho = os.path.join(COPIAS, nome)
            if nome.endswith(".db") and os.path.isfile(caminho):
                existentes.append(
                    "<div class='l'><span class='t'>%s</span><span class='v'>%s MB</span></div>"
                    % (html.escape(nome), mil_pt(os.path.getsize(caminho) // (1024 * 1024))))
    ultima = le_marca("ultima_copia", "ainda nenhuma")
    corpo = (
        "<form method='post' action='/configuracoes/copias' class='conf-form'>"
        + _interruptor("Cópia diária do radar.db", "copia_de_seguranca",
                       cfg.get("copia_de_seguranca", True),
                       nota="a triagem, o quadro e o histórico não se recuperam de mais lado nenhum")
        + _campo("Cópias a guardar", "copias_a_guardar", cfg.get("copias_a_guardar", 7),
                 nota="uma por dia; as mais velhas apagam-se. A base tem 1,3 GB — conta com isso")
        + _interruptor("Empurrar a triagem para o GitHub (triagem.jsonl)", "triagem_no_git",
                       cfg.get("triagem_no_git", True),
                       nota="commit e push em cada verificação em que mude")
        + "<button type='submit' class='bt forte'>Guardar</button></form>"
        + "<div class='rot' style='margin:22px 0 6px'>O que existe em copias/</div>"
        + "<div class='nota' style='margin-bottom:10px'>Última: %s</div>" % html.escape(ultima)
        + "<div class='nota' style='margin-bottom:10px'>Ensaio de restauro: %s "
          "<span style='color:var(--t5)'>(python radar.py --ensaiar-copia)</span></div>"
          % html.escape(le_marca("ultimo_ensaio_copia", "ainda nenhum"))
        + "<div class='saude'>%s</div>" % ("".join(existentes) or
                                           "<div class='nota'>nenhuma ainda</div>"))
    return pagina_config("copias", "<div class='cx conf-cx'>" + corpo + "</div>")


IMPORTACOES = os.path.join(BASE_DIR, casa.PASTA_IMPORTACOES)


def _nome_de_importacao(nome):
    """So um nome de ficheiro dentro de importacoes/: nada de caminhos."""
    nome = os.path.basename((nome or "").strip())
    return nome if re.fullmatch(r"[\w.\-]+\.xlsx", nome) else ""


def _tabela_do_ensaio(linhas):
    corpo = []
    for l in linhas:
        problemas = "".join("<div class='mau'>%s</div>" % html.escape(pr) for pr in l["problemas"])
        avisos = "".join("<div class='aviso'>%s</div>" % html.escape(av) for av in l.get("avisos", []))
        corpo.append(
            "<tr class='%s'><td class='d'>%d</td><td class='n'>%s</td><td class='o'>%s</td>"
            "<td class='d'>%s</td><td>%s</td><td class='p'>%s</td><td>%s</td></tr>"
            % ("ok" if l["ok"] else "erro", l["linha"], html.escape(l["ref"] or "—"),
               html.escape(corta(l["titulo"] or "", 90)),
               "L%d" % l["lote"] if l["lote"] is not None else "—",
               html.escape(l["status"] or "—"),
               html.escape(_texto_do_preco(l["valor_proposta"])) if l["valor_proposta"] else "—",
               (problemas + avisos) or "<span class='ok'>liga</span>"))
    return ("<div class='mercado-tab'><table class='tab-mercado tab-ensaio'><thead><tr>"
            "<th>Linha</th><th>Referência</th><th>Anúncio</th><th>Lote</th><th>Estado</th>"
            "<th class='p'>Proposta</th><th>Ensaio</th></tr></thead><tbody>%s</tbody></table></div>"
            % "".join(corpo))


@app.route("/configuracoes/importar", methods=["GET", "POST"])
def config_importar():
    """O registo da casa entra por aqui: descarregar o modelo, carregar o
    ficheiro preenchido, ver o ensaio, confirmar. Decisao do Afonso a
    8/09/2026 -- o Excel antigo deixou de contar para a aplicacao."""
    if request.method == "POST":
        ficheiro = request.files.get("ficheiro")
        if not ficheiro or not ficheiro.filename:
            return volta_config("importar", "Escolhe o ficheiro .xlsx preenchido.")
        if not ficheiro.filename.lower().endswith(".xlsx"):
            return volta_config("importar", "Só .xlsx: é o formato do modelo.")
        os.makedirs(IMPORTACOES, exist_ok=True)
        nome = "%s-%s" % (datetime.now().strftime("%Y%m%d-%H%M%S"),
                          re.sub(r"[^\w.\-]+", "_", os.path.basename(ficheiro.filename))[-60:])
        if not nome.endswith(".xlsx"):
            nome += ".xlsx"
        caminho = os.path.join(IMPORTACOES, nome)
        ficheiro.save(caminho)
        try:
            linhas = casa.ler_modelo(caminho)
        except Exception as erro:            # openpyxl levanta de tudo num ficheiro estragado
            os.remove(caminho)
            return volta_config("importar", "Não consegui ler o ficheiro: %s" % str(erro)[:120])
        with liga() as c:
            linhas, contagens = casa.ensaio_modelo(c, linhas)
        if not linhas:
            os.remove(caminho)
            return volta_config("importar", "O ficheiro não tem linhas preenchidas na folha «Registo».")
        confirmar = (
            "<form method='post' action='/configuracoes/importar/confirmar' class='conf-form' "
            "style='margin-top:16px'><input type='hidden' name='ficheiro' value='%s'>"
            "<button type='submit' class='bt forte'%s>Confirmar: gravar %d linha%s e a triagem</button>"
            "<small>As linhas com erro ficam de fora. Uma linha repetida (mesma referência e "
            "lote) substitui a que já lá estava.</small></form>"
            % (html.escape(nome, quote=True), "" if contagens["ok"] else " disabled",
               contagens["ok"], "" if contagens["ok"] == 1 else "s"))
        corpo = (
            "<div class='rot'>Ensaio de %s</div>"
            "<div class='nota' style='margin:6px 0 12px'>%d linha%s lida%s: <b>%d liga%s</b> "
            "a %d anúncio%s, <b>%d com erro</b>. Nada foi gravado ainda.</div>%s%s"
            % (html.escape(ficheiro.filename), contagens["total"],
               "" if contagens["total"] == 1 else "s", "" if contagens["total"] == 1 else "s",
               contagens["ok"], "" if contagens["ok"] == 1 else "m",
               contagens["anuncios"], "" if contagens["anuncios"] == 1 else "s",
               contagens["com_erro"], _tabela_do_ensaio(linhas), confirmar))
        return pagina_config("importar", "<div class='cx conf-cx'>" + corpo + "</div>")
    with liga() as c:
        n_modelo = c.execute("SELECT COUNT(*), COUNT(DISTINCT ref) FROM casa "
                             "WHERE folha='modelo'").fetchone()
        ultima = c.execute("SELECT MAX(importado_em) FROM casa WHERE folha='modelo'").fetchone()[0]
    corpo = (
        "<div class='rot'>1. O modelo</div>"
        "<div class='nota' style='margin:6px 0 12px'>Um Excel vazio com as colunas que o radar "
        "precisa e listas de escolha no estado e na razão. Uma linha por concurso, ou por lote "
        "quando o concurso tem lotes. A chave é a referência do anúncio no DR (ex. "
        "<code>1947/2026</code>), tal como a ficha a mostra.</div>"
        "<a class='bt' href='/configuracoes/importar/modelo.xlsx'>Descarregar o modelo</a>"
        "<div class='rot' style='margin:26px 0 6px'>2. O ficheiro preenchido</div>"
        "<div class='nota' style='margin-bottom:12px'>Primeiro vês um ensaio: o que liga a que "
        "anúncio, o que não liga e porquê. Só grava quando confirmares.</div>"
        "<form method='post' action='/configuracoes/importar' enctype='multipart/form-data' "
        "class='conf-form'><label class='conf-campo'><span>Ficheiro .xlsx</span>"
        "<input type='file' name='ficheiro' accept='.xlsx' required></label>"
        "<button type='submit' class='bt forte'>Ver o ensaio</button></form>"
        "<div class='rot' style='margin:26px 0 6px'>O que já está</div>"
        "<div class='nota'>%s</div>"
        % ("%s linha%s do modelo, em %s anúncio%s; última importação a %s."
           % (mil_pt(n_modelo[0]), "" if n_modelo[0] == 1 else "s", mil_pt(n_modelo[1]),
              "" if n_modelo[1] == 1 else "s", html.escape(data_hora_pt(ultima)))
           if n_modelo[0] else "Ainda não entrou nenhuma linha pelo modelo."))
    return pagina_config("importar", "<div class='cx conf-cx'>" + corpo + "</div>")


@app.route("/configuracoes/importar/modelo.xlsx")
def config_importar_modelo():
    os.makedirs(IMPORTACOES, exist_ok=True)
    caminho = os.path.join(IMPORTACOES, "modelo-registo-da-casa.xlsx")
    casa.escrever_modelo(caminho)
    return send_file(caminho, as_attachment=True,
                     download_name="registo-da-casa.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/configuracoes/importar/confirmar", methods=["POST"])
def config_importar_confirmar():
    nome = _nome_de_importacao(request.form.get("ficheiro"))
    caminho = os.path.join(IMPORTACOES, nome) if nome else ""
    if not nome or not os.path.exists(caminho):
        return volta_config("importar", "O ficheiro do ensaio já não está cá; carrega-o outra vez.")
    linhas = casa.ler_modelo(caminho)
    with liga() as c:
        linhas, contagens = casa.ensaio_modelo(c, linhas)
        resultado = casa.aplicar_modelo(c, linhas, quem=quem_sou() or "modelo")
    registar("", "importação", "%d linhas do modelo, %d anúncios, %d com triagem aplicada (%s)"
             % (resultado["gravadas"], resultado["anuncios"], resultado["aplicadas"], nome))
    return volta_config("importar", "Importado: %d linha%s em %d anúncio%s; %d com a triagem "
                        "aplicada, %d com erro ficaram de fora."
                        % (resultado["gravadas"], "" if resultado["gravadas"] == 1 else "s",
                           resultado["anuncios"], "" if resultado["anuncios"] == 1 else "s",
                           resultado["aplicadas"], contagens["com_erro"]))


@app.route("/configuracoes/conta", methods=["GET", "POST"])
def config_conta():
    utilizador = g.get("utilizador")
    if not utilizador:
        return pagina_config("conta", "<div class='cx conf-cx'><div class='nota'>"
                             "Ainda não há conta. Na pasta do radar: "
                             "<code>python radar.py --criar-utilizador NOME</code>."
                             "</div></div>")
    if request.method == "POST":
        # So a palavra-passe: o "nome a mostrar" saiu a 13/09/2026 (o
        # utilizador chega), e o utilizador em si nao se muda.
        actual = request.form.get("actual") or ""
        nova = request.form.get("nova") or ""
        outra = request.form.get("outra") or ""
        # o registar() fica FORA do `with`: la dentro a transaccao esta
        # aberta e a segunda ligacao ficava a espera dela (database is
        # locked -- apanhado pelo teste)
        with liga() as c:
            linha = c.execute("SELECT hash FROM utilizadores WHERE id=?",
                              (utilizador["id"],)).fetchone()
            if not contas.verifica_senha(actual, linha["hash"]):
                return volta_config("conta", "A palavra-passe actual não está certa.")
            if nova != outra:
                return volta_config("conta", "As duas palavras-passe novas não são iguais.")
            try:
                contas.criar_utilizador(c, utilizador["email"], nova)
            except ValueError as erro:
                return volta_config("conta", "Não gravei: %s." % erro)
        registar("", "conta", "palavra-passe mudada")
        return volta_config("conta", "Palavra-passe mudada.")
    with liga() as c:
        sessoes = contas.sessoes_de(c, utilizador["id"])
        todos = contas.utilizadores(c) if sou_admin() else []
    # "iPhone até 10/10/2026 14:35", nao o User-Agent inteiro (13/09/2026)
    linhas = "".join(
        "<div class='l'><span class='ponto' style='background:%s'></span>"
        "<span class='t'>%s%s</span><span class='v'>até %s</span></div>"
        % ("#1e8449" if s_["token"] == g.get("sessao") else "#9db1c4",
           aparelho_do_agente(s_["agente"]),
           " (esta)" if s_["token"] == g.get("sessao") else "",
           html.escape(data_hora_pt(s_["expira"][:16])))
        for s_ in sessoes) or "<div class='nota'>nenhuma sessão: estás pelo acesso livre local</div>"
    corpo = (
        "<form method='post' action='/configuracoes/conta' class='conf-form'>"
        + _campo("Utilizador", "utilizador", utilizador["email"], extra="disabled")
        + _campo("Palavra-passe actual", "actual", "", tipo="password",
                 extra="autocomplete='current-password'")
        + _campo("Nova palavra-passe", "nova", "", tipo="password",
                 nota="8 caracteres ou mais",
                 extra="autocomplete='new-password'")
        + _campo("Outra vez", "outra", "", tipo="password",
                 extra="autocomplete='new-password'")
        + "<button type='submit' class='bt forte'>Guardar</button></form>"
        + "<div class='rot' style='margin:22px 0 6px'>Sessões abertas</div>"
        + "<div class='saude'>%s</div>" % linhas
        + ("<div style='margin-top:14px'>%s</div>"
           % accao("/sair-de-todos", "Sair de todos os aparelhos", "bt")
           if sessoes else ""))
    if sou_admin():
        corpo += _bloco_da_casa()
        corpo += _bloco_utilizadores(todos, utilizador["id"])
    return pagina_config("conta", "<div class='cx conf-cx'>" + corpo + "</div>")


def _bloco_da_casa(cfg=None):
    """Quem somos nós, para o cruzamento com o Portal BASE.

    Sem isto o radar sabe a quem o procedimento foi adjudicado mas não
    sabe se esse alguém somos nós -- e pergunta, em vez de adivinhar. Com
    o NIF preenchido, adianta a resposta; o gesto de fechar continua a
    ser de quem lê (etapa 4 do `docs/historico/CRM.md`).

    O NIF, e não só o nome: o dump do IMPIC traz o NIF do adjudicatário,
    e um nome de empresa escreve-se de cinco maneiras («LDA», «Lda.»,
    «, S.A.») -- comparar por nome sozinho dava falsos negativos
    justamente nos concursos que interessam.
    """
    nome, nif = _nome_da_casa(cfg)
    return ("<div class='rot' style='margin:22px 0 6px'>A nossa empresa</div>"
            "<div class='nota' style='margin-bottom:10px'>Para o radar saber, "
            "ao cruzar com o Portal BASE, se a adjudicação foi nossa. "
            "Enquanto estiver vazio, a ficha mostra a quem foi e pergunta."
            "</div>"
            "<form method='post' action='/configuracoes/conta/casa' "
            "class='conf-form'>"
            + _campo("Nome", "nome_da_casa", nome,
                     nota="como aparece nos contratos")
            + _campo("NIF", "nif_da_casa", nif,
                     nota="nove dígitos; é por aqui que a ligação é certa")
            + "<button type='submit' class='bt'>Guardar</button></form>")


@app.route("/configuracoes/conta/casa", methods=["POST"])
def config_casa():
    """Grava quem somos nós. O NIF fica só com os dígitos: o dump do
    IMPIC guarda-o assim, e um espaço ou um ponto a meio fazia a
    comparação falhar sem nada no ecrã a dizer porquê."""
    nome = " ".join((request.form.get("nome_da_casa") or "").split())[:120]
    nif = re.sub(r"\D", "", request.form.get("nif_da_casa") or "")[:9]
    gravar_config_registado({"nome_da_casa": nome, "nif_da_casa": nif})
    return volta_config("conta", "A nossa empresa: guardada.")


def _bloco_utilizadores(todos, eu):
    """A gestao das contas, so ao admin (13/09/2026): quem existe, de que
    tipo, e o formulario para criar outra. Tirar uma conta e um botao
    com confirmacao; o ultimo admin nao se tira (contas.apagar_utilizador
    recusa)."""
    linhas = "".join(
        "<div class='l'><span class='ponto' style='background:%s'></span>"
        "<span class='t'>%s%s</span><span class='v'>%s%s</span></div>"
        % ("#1e8449" if u["papel"] == "admin" else "#9db1c4",
           html.escape(u["email"]), " (eu)" if u["id"] == eu else "",
           html.escape(u["papel"]),
           "" if u["id"] == eu else
           " &middot; " + accao("/configuracoes/conta/utilizadores/%d/apagar" % u["id"],
                                "tirar", "mini perigo",
                                "Tirar a conta %s? As sessões dela fecham já."
                                % html.escape(u["email"], quote=True)))
        for u in todos)
    return (
        "<div class='rot' style='margin:26px 0 6px'>Utilizadores</div>"
        "<div class='nota' style='margin-bottom:10px'>O <b>admin</b> vê tudo "
        "e cria contas; o <b>tester</b> vê os anúncios, o que está em curso, "
        "o mercado, e nas configurações só a conta, o interesse, os alertas "
        "e o importar.</div>"
        "<div class='saude'>%s</div>"
        "<form method='post' action='/configuracoes/conta/utilizadores' "
        "class='conf-form' style='margin-top:16px'>"
        "%s%s"
        "<label class='conf-campo'><span>Tipo</span><select name='papel'>"
        "<option value='tester'>tester</option>"
        "<option value='admin'>admin</option></select></label>"
        "<button type='submit' class='bt forte'>Criar utilizador</button></form>"
        % (linhas,
           _campo("Utilizador", "email", "", extra="autocomplete='off'"),
           _campo("Palavra-passe", "senha", "", tipo="password",
                  nota="8 caracteres ou mais",
                  extra="autocomplete='new-password'")))


@app.route("/configuracoes/conta/utilizadores", methods=["POST"])
def conta_criar_utilizador():
    email = (request.form.get("email") or "").strip()
    papel = (request.form.get("papel") or "tester").strip()
    with liga() as c:
        if c.execute("SELECT 1 FROM utilizadores WHERE email=?",
                     (contas.email_limpo(email),)).fetchone():
            return volta_config("conta", "Já existe um utilizador %s." % email)
        try:
            contas.criar_utilizador(c, email, request.form.get("senha") or "",
                                    papel=papel)
        except ValueError as erro:
            return volta_config("conta", "Não criei: %s." % erro)
    registar("", "conta", "criou o utilizador %s (%s)"
             % (contas.email_limpo(email), papel))
    return volta_config("conta", "Utilizador %s criado, como %s."
                        % (contas.email_limpo(email), papel))


@app.route("/configuracoes/conta/utilizadores/<int:utilizador_id>/apagar",
           methods=["POST"])
def conta_apagar_utilizador(utilizador_id):
    if utilizador_id == (g.get("utilizador") or {}).get("id"):
        return volta_config("conta", "A tua própria conta não se tira daqui.")
    with liga() as c:
        linha = c.execute("SELECT email FROM utilizadores WHERE id=?",
                          (utilizador_id,)).fetchone()
        try:
            houve = contas.apagar_utilizador(c, utilizador_id)
        except ValueError as erro:
            return volta_config("conta", "Não tirei: %s." % erro)
    if not houve:
        return volta_config("conta", "Essa conta já não existe.")
    registar("", "conta", "tirou o utilizador %s" % linha["email"])
    return volta_config("conta", "Conta %s tirada." % linha["email"])


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
        return redirect("/configuracoes/alertas?" + urlencode(
            [("aviso", mensagem), ("nome", nome)] + pares))

    if not nome:
        return recusa("O alerta precisa de nome.")
    consulta = urlencode(pares)
    if not [k for k, v in pares if v and k not in ("estado", "op")]:
        return recusa("Preenche pelo menos um campo além do estado.")
    # Nasce ligado (13/09/2026: "Criar alerta", nao "criar filtro"), e o
    # acervo que ja la esta fica marcado como tal, como ao ligar o
    # interruptor -- senao o primeiro resumo trazia tudo.
    havia = gravar_filtro(nome, consulta, alerta=1)
    registar_alertas()
    return redirect("/configuracoes/alertas?aviso=" +
                    quote("Alerta %s: %s"
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
    return redirect("/configuracoes/alertas?aviso=" + quote("Configuração do e-mail guardada."))


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
    return redirect("/configuracoes/alertas")


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
                 % (html.escape(termo), primeiro_ano_corpus()))
    return envolver(
        "contratos", "Procurar entidade",
        "Nome ou NIF; a procura cobre todas as grafias com que cada "
        "entidade já assinou.",
        corpo, migalhas=migalhas_de("contratos", "procurar"),
        titulo_aba="Procurar entidade, Radar de Concursos")


@app.route("/alertas/enviar", methods=["POST"])
def alertas_enviar():
    bem, porque = enviar_resumo(forcar=True)
    return redirect("/configuracoes/alertas?aviso=" +
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
    mediana = statistics.median(descontos)
    contagens = [0] * (len(LIMITES_DESCONTO) + 1)
    for d in descontos:
        contagens[bisect.bisect_right(LIMITES_DESCONTO, 100.0 * d)] += 1
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
           arvore_html(n_cpv, "contratos"), ""))


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
    if not pergunta_feita(request.args, vista):
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
    linha_csv(escritor, ["Celebrado", "Fim estimado", "Objecto",
                       "Entidade que comprou",
                       "Quem ganhou", "Procedimento", "Preço contratual (EUR)",
                       "Preço base (EUR)", "CPV", "Prazo (dias)", "Local",
                       "Anúncio"])
    for a in linhas:
        # o mesmo formato do CSV dos anuncios: data portuguesa e numero
        # com virgula decimal. Eram duas exportacoes da mesma aplicacao a
        # escrever dinheiro de duas maneiras, e nenhuma servia o Excel.
        linha_csv(escritor, [data_pt(a["data_celebracao"]),
                           data_pt(a["fim_estimado"], ""), a["objecto"],
                           a["adjudicante"], a["adjudicatarios"],
                           a["tipo_procedimento"],
                           numero_csv(a["preco_contratual"]),
                           numero_csv(a["preco_base"]), a["cpv"],
                           a["prazo_execucao"], a["local_execucao"],
                           a["n_anuncio"]])
    return resposta_csv(saida, "contratos")


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


def ganhadores_da_linha(linha):
    """[(chave, nome), ...] de uma linha com `ganhou`/`ganhou_ch`.

    Os adjudicatarios vem em duas listas paralelas separadas por `|` (a
    virgula ja aparece nos nomes), e ate 04/09/2026 cada sitio fazia o
    seu `zip(nomes, chaves)`. Esse zip mentia em silencio: os dois
    campos sao `group_concat`s, e o das chaves vem **NULL** quando
    NENHUM adjudicatario daquele contrato tem chave. Aí
    `"".split("|")` dava uma lista de UM, o zip truncava pelo mais
    curto, e um agrupamento de cinco aparecia com um nome so -- sem
    erro, sem aviso, e com ar de estar certo.

    No corpus verdadeiro as chaves estao cheias (`_preencher_chaves`
    corre na importacao), por isso isto nunca se viu no ecra; quem o
    apanhou foi um teste do desfecho contra um corpus sem essa
    migracao. E e por nunca se ver que tinha de deixar de depender
    disso: os tres sitios que mostram "quem ganhou" passam por aqui.
    """
    nomes = [n for n in (linha["ganhou"] or "").split("|") if n]
    chaves = (linha["ganhou_ch"] or "").split("|")
    chaves += [""] * (len(nomes) - len(chaves))
    return list(zip(chaves, nomes))


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
    cfg = ler_config()
    # com interesse definido, o Mercado fica como os anuncios: sem
    # arvore nem "excluir CPV" -- o CPV ja esta decidido no Interesse
    ligado_i, dentro_i, _ = interesse_definido(cfg)
    com_interesse = bool(ligado_i and dentro_i)
    # A pergunta e um filtro OU o interesse (14/09/2026: «abre-se e nao
    # se ve contrato nenhum»). Com interesse definido o Mercado abre
    # logo com os contratos dos CPV da casa -- medido, 0,4 s a contar e
    # a listar 72 mil; os graficos continuam a pedir-se so ao abrir.
    ha_pergunta = pergunta_feita(request.args, vista, cfg)

    onde, valores = filtros_dos_contratos(request.args, cfg=cfg)
    escondidos_interesse = 0
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
            if com_interesse and condicao_do_interesse_contratos(cfg=cfg)[0]:
                # quantos e que o interesse tapa dentro deste filtro: um
                # recorte que nao diga quanto esconde e um recorte que
                # se esquece (a mesma regra da lista de anuncios)
                onde_livre, val_livre = filtros_dos_contratos(
                    request.args, com_interesse=False, cfg=cfg)
                escondidos_interesse = c.execute(
                    "SELECT COUNT(*) n FROM contratos c" + onde_livre,
                    val_livre).fetchone()["n"] - correspondem
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
        procs = tipos_de_procedimento()
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

    # Sem "excluir palavras", sem "excluir CPV" a ver e sem o E/OU
    # (14/09/2026, como nos anuncios); as duas entidades sugerem-se do
    # corpus e, escolhida a sugestao, a chave (o NIF) vai em entid/vencid,
    # que a ficha da entidade ja usava. O que vier na URL passa escondido.
    filtros = (
        "<form class='cx filtros' method='get' action='/contratos'>"
        "%s"
        "<input type='text' name='q' value='%s' placeholder='Objecto do contrato…'>"
        "<input type='text' name='adj' value='%s' placeholder='Entidade que comprou…' "
        "list='entidades-contratos' autocomplete='off' data-sugere='contratos' "
        "data-chave-em='entid'>"
        "<input type='hidden' name='entid' value='%s'>"
        "<input type='text' name='ganhou' value='%s' placeholder='%s' "
        "list='entidades-contratos' autocomplete='off' data-sugere='contratos' "
        "data-chave-em='vencid'>"
        "<input type='hidden' name='vencid' value='%s'>"
        "<input type='hidden' id='filtro-cpv' name='cpv' value='%s'>"
        "<input type='hidden' id='filtro-cpv-excl' name='cpv_excl' value='%s'>"
        "%s"
        "%s%s"
        "<label>de</label><input type='date' name='de' value='%s'%s>"
        "<label>até</label><input type='date' name='ate' value='%s'%s>"
        "<label>desde</label><input type='text' name='min' value='%s' "
        "placeholder='€ mínimo' style='min-width:0;width:110px;flex:none'>"
        "<button type='submit'>Filtrar</button>"
        "<a class='limpar' href='%s'>limpar</a>"
        "</form><datalist id='entidades-contratos'></datalist>"
        % (escondidos_modo, v("q"), v("adj"), v("entid"), v("ganhou"),
           "Quem tem o contrato…" if fim else "Quem ganhou…",
           v("vencid"), v("cpv"), v("cpv_excl"),
           campos_escondidos(request.args, ("q_excl", "op")),
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
            venceu = " + ".join(
                liga_entidade(ch, n)
                for ch, n in ganhadores_da_linha(l)) or "—"
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
                  "<span class='p'>Com o <a href='/configuracoes/interesse'>"
                  "interesse</a> definido, esta página abre logo com os "
                  "contratos dos teus CPV.</span>"
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
                  "recentes não dizem nada sobre nada. Com o "
                  "<a href='/configuracoes/interesse'>interesse</a> definido, "
                  "esta página abre logo com os contratos dos teus CPV.</span>"
                  "</div>"
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
             "trazer o ano corrente e o anterior. O corpus começa em %d "
             "&mdash; é o mais antigo que o dados.gov chega a dar, os "
             "zips de 2012 a 2014 vêm vazios. Para trazer um ano de "
             "novo, <code>python radar.py --contratos %d</code>.</div>"
             % (primeiro_ano_corpus(), primeiro_ano_corpus()))

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
    faixa_interesse = _faixa_do_interesse("/contratos", escondidos_interesse, cfg)
    if com_interesse:
        filtros = filtros.replace("<input type='text' id='filtro-cpv-excl'",
                                  "<input type='hidden' id='filtro-cpv-excl'")

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
                faixa_interesse + filtros +
                faixa_cpv + ("" if com_interesse else arvore_html(n_cpv, "contratos")) +
                graficos + linha_conta +
                (titulo_tabela if ha_pergunta else "") +
                tabela +
                paginador(pagina, paginas, request.args, "/contratos") +
                nota_estimativa +
                (fonte if ha_pergunta else "") + "</div>")

    if fim:
        return envolver(
            "renovacoes", "Renovações",
            "Os mesmos contratos do Portal BASE, vistos pelo <b>fim "
            "estimado</b>: o que está a chegar ao fim no teu mercado deve "
            "voltar a concurso, e quem o vê antes do anúncio prepara-se "
            "com tempo. O fim é celebração mais prazo &mdash; as "
            "prorrogações não constam.",
            conteudo, abas=abas,
            script=("" if com_interesse else ARVORE_JS) + GRAFICOS_JS + ENTIDADES_JS
            + espera_corpus(),
            migalhas=migalhas_de("renovacoes"),
            titulo_aba="Renovações, Radar de Concursos")
    return envolver(
        "contratos", "Contratos celebrados",
        "O que já foi assinado, do Portal BASE, pela <b>data de "
        "celebração</b> &mdash; quem ganhou, por quanto, de quem. Não são "
        "oportunidades: servem para saber com quem se concorre. As "
        "<a href='/contratos?ver=fim'>Renovações</a> são estes mesmos "
        "contratos vistos pelo fim.",
        conteudo, abas=abas,
        script=("" if com_interesse else ARVORE_JS) + GRAFICOS_JS + ENTIDADES_JS
        + espera_corpus(),
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


def pergunta_feita(args, vista, cfg=None):
    """Se o Mercado tem uma pergunta a que responder: um campo do filtro
    preenchido (o `op` nao conta -- e um modo, nao um filtro; e no modo
    fim as datas tambem nao, que o modo as poe de lado) OU o interesse
    definido e nao levantado (14/09/2026). Sem pergunta nao se mostra
    lista: sao dois milhoes de contratos, e os mais recentes por data
    nao dizem nada a ninguem."""
    if any((args.get(campo) or "").strip()
           for campo in campos_da_vista(vista) if campo != "op"):
        return True
    return bool(condicao_do_interesse_contratos(args, cfg)[0])


def filtros_dos_contratos(args, com_interesse=True, cfg=None):
    """(onde, valores) da lista de contratos, com o modo e o interesse
    aplicados. `com_interesse=False` da a mesma conta sem o interesse:
    e o que diz quantos ficam de fora.

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
    onde += condicao_do_modo(args)
    # O interesse (14/09/2026), como recorte de pagina: a lista, o CSV
    # e os graficos filtram os tres por aqui, e e por isso que entra
    # aqui e nao em condicoes_contratos().
    if com_interesse:
        frag_i, vals_i = condicao_do_interesse_contratos(args, cfg)
        if frag_i:
            onde += " AND (%s)" % frag_i
            valores = list(valores) + vals_i
    return onde, valores


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


def lotes_cx(a):
    """O bloco dos lotes na ficha: os que o anuncio declara, com o preco
    base de cada um, e -- quando o registo da casa os conhece -- a que
    fomos, com que proposta, em que lugar e como acabou. Vazio quando o
    procedimento nao tem lotes: um bloco a dizer "sem lotes" em 77% das
    fichas era ruido."""
    lotes = lotes_de(a)
    if not lotes:
        return ""
    with liga() as c:
        linhas_casa = casa.linhas_de_lotes(c, [a["ref"]]).get(a["ref"], ())
    resumo = resumo_dos_lotes(lotes, linhas_casa)
    ha_registo = bool(resumo["fomos"] or resumo["conjunto"])
    corpo = []
    for l in resumo["lotes"]:
        if ha_registo:
            if l["estado"]:
                situacao = ("<span class='tag %s'>%s</span>%s%s"
                            % (l["classe"], l["rotulo"],
                               (" <span class='lote-prop'>proposta %s</span>"
                                % html.escape(_texto_do_preco(l["proposta"])))
                               if l["proposta"] else "",
                               (" <span class='lote-prop'>%dº lugar</span>" % int(l["lugar"]))
                               if l["lugar"] else ""))
            elif l["n"] in resumo["fomos"]:
                situacao = "<span class='tag'>fomos, sem desfecho registado</span>"
            elif resumo["conjunto"]:
                situacao = "<span class='em-falta'>no conjunto</span>"
            else:
                situacao = "<span class='em-falta'>não fomos</span>"
        else:
            situacao = ""
        corpo.append("<tr><td class='n'>L%d</td><td class='o'>%s</td>"
                     "<td class='p'>%s</td>%s</tr>"
                     % (l["n"], html.escape(l["descricao"] or l["id"] or "—"),
                        html.escape(l["preco_base"] or "—"),
                        ("<td class='s'>%s</td>" % situacao) if ha_registo else ""))
    if resumo["conjunto"]:
        conj = resumo["conjunto"]
        estado = casa.estado_do_lote(conj)
        rotulo, classe = ESTADO_DO_LOTE.get(estado, ("sem desfecho registado", ""))
        nota_conj = ("<div class='nota' style='margin-top:10px'>O registo da casa "
                     "tem uma linha para o <b>conjunto</b> dos lotes, não lote a "
                     "lote: <span class='tag %s'>%s</span>%s</div>"
                     % (classe, rotulo,
                        (" proposta %s" % html.escape(_texto_do_preco(conj["valor_proposta"])))
                        if conj.get("valor_proposta") else ""))
    else:
        nota_conj = ""
    return ("<div class='cx lotes' id='lotes'><div class='rot'>Lotes</div>"
            "<div class='nota' style='margin:6px 0 12px'>%s. %s</div>"
            "<div class='mercado-tab'><table class='tab-mercado tab-lotes'><thead><tr>"
            "<th>Lote</th><th>Descrição</th><th class='p'>Preço base</th>%s"
            "</tr></thead><tbody>%s</tbody></table></div>%s</div>"
            % (html.escape(frase_dos_lotes(resumo)[0].upper() + frase_dos_lotes(resumo)[1:]),
               "O que se sabe de cada um vem do registo da casa (o Excel), "
               "lote a lote." if ha_registo else
               "Os lotes são os que o anúncio declara; a que fomos só o "
               "registo da casa sabe, e ainda não tem esta linha.",
               "<th>A casa</th>" if ha_registo else "",
               "".join(corpo), nota_conj))


def frase_dos_campos_em_falta(sem_valor):
    """A frase, por baixo do essencial, com os campos que nao tem valor,
    agrupados pela razao: [(razao, rotulo)] -> HTML, vazio se nao ha.

    Mantem a ordem em que as razoes aparecem e a dos campos dentro de
    cada uma, para a leitura ser a da tabela que substitui."""
    if not sem_valor:
        return ""
    grupos = []
    for razao, rotulo in sem_valor:
        for g in grupos:
            if g[0] == razao:
                g[1].append(rotulo)
                break
        else:
            grupos.append((razao, [rotulo]))
    partes = ["<b>%s</b>: %s" % (html.escape(razao),
                                 ", ".join(html.escape(r) for r in rotulos))
              for razao, rotulos in grupos]
    n = len(sem_valor)
    return ("<p class='em-falta-frase'>%d campo%s sem valor aqui &mdash; %s. "
            "<a href='#pecas'>Peças</a></p>"
            % (n, "" if n == 1 else "s", "; ".join(partes)))


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
        venceu = " + ".join(liga_entidade(ch, n)
                            for ch, n in ganhadores_da_linha(l)) or "—"
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


# Do anuncio ao contrato leva tempo, e o tempo mediu-se: a 04/09/2026,
# sobre os 38 666 anuncios da base que ja tinham contrato no corpus, a
# distancia entre a publicacao do anuncio e a celebracao era p25 45
# dias, mediana 68, p75 98, p90 139. E o que decide quando o silencio
# vale a pena ser dito: um anuncio de ha um mes sem contrato nao diz
# nada, um de ha seis meses ja diz.
DIAS_ATE_CONTRATO = 180


def desfecho_do_anuncio(ref):
    """Os contratos que este anuncio deu, do corpus do Portal BASE.

    Ligacao por CHAVE e nao por semelhanca: o dump do IMPIC traz o
    numero do anuncio do DR em `n_anuncio`, no mesmo formato do `ref`
    do radar ("13108/2026"), e ha indice (`ix_ctr_anuncio`). E o que
    distingue isto dos homologos, que sao um palpite por termos do
    titulo -- aqui ou e o mesmo procedimento ou nao e nada.

    Varias linhas sao os lotes do mesmo procedimento, e e por isso que
    a conta do desconto soma antes de dividir (desconto_do_desfecho).
    """
    if not (ref and ha_corpus()):
        return []
    with liga_corpus() as c:
        return c.execute(
            "SELECT c.id, c.data_celebracao, c.objecto, c.tipo_procedimento,"
            " c.preco_contratual, c.preco_base, c.prazo_execucao,"
            " (SELECT group_concat(COALESCE(g.nome, a.nome), '|')"
            "  FROM contrato_adjudicatario a"
            "  LEFT JOIN entidades g ON g.chave=a.chave"
            "  WHERE a.contrato_id=c.id) AS ganhou,"
            " (SELECT group_concat(a.chave, '|') FROM contrato_adjudicatario a"
            "  WHERE a.contrato_id=c.id) AS ganhou_ch"
            " FROM contratos c WHERE c.n_anuncio=?"
            " ORDER BY c.data_celebracao, c.id", (ref,)).fetchall()


def desconto_do_desfecho(linhas, base_do_anuncio=0.0):
    """(desconto 0..1 ou None, base usada, de onde veio a base).

    A mesma regra do grafico do corpus (`descontos_por_procedimento`):
    **o procedimento e a unidade, e os lotes somam-se ANTES de
    dividir**. Por linha, cada lote comparava-se com a base do
    procedimento inteiro, e a media ingenua dava -18,9% no corpus --
    um numero que mente com ar de certo.

    Devolve None quando nao se sabe ler: sem base, base a VARIAR entre
    lotes (ai a base e por lote e a semantica e outra) e soma
    contratual acima da base. Quando o dump nao traz base nenhuma cai
    para a do anuncio, e diz que caiu -- sao duas fontes e o ecra tem
    de dizer qual esta a usar.
    """
    bases = [l["preco_base"] or 0.0 for l in linhas]
    soma = sum(l["preco_contratual"] or 0.0 for l in linhas)
    base, fonte = (max(bases) if bases else 0.0), "corpus"
    if base <= 0:
        base, fonte = base_do_anuncio or 0.0, "anuncio"
    if base <= 0 or soma <= 0 or soma > base:
        return None, base, fonte
    if fonte == "corpus" and min(bases) != max(bases):
        return None, base, fonte
    return 1.0 - soma / base, base, fonte


def _dias_desde(data):
    """Dias entre uma data ISO e hoje. Datas ilegiveis contam zero, que
    e o lado que nao afirma nada."""
    try:
        return (datetime.now().date()
                - datetime.strptime((data or "")[:10], "%Y-%m-%d").date()).days
    except (ValueError, TypeError):
        return 0


def desfecho_cx(a):
    """Como este anuncio acabou: os contratos celebrados, do Portal BASE.

    E o inverso do atalho que ja existia (`refs_com_anuncio`, que leva
    do contrato ao anuncio). Aqui a pergunta e a outra e e a que fecha
    o funil: o procedimento que triamos deu no que, a quem, e por
    quanto abaixo da base.
    """
    if not ha_corpus():
        return ""
    linhas = desfecho_do_anuncio(a["ref"])
    if not linhas:
        # Sem contrato so vale a pena dize-lo quando ja passou tempo que
        # chegue para ele existir -- antes disso o silencio e o normal,
        # e uma caixa a dizer "nada" em todos os anuncios recentes era
        # ruido em 46% da lista.
        dias = _dias_desde(a["data_pub"])
        if dias < DIAS_ATE_CONTRATO:
            return ""
        return ("<div class='cx mercado' id='desfecho'>"
                "<div class='rot'>Desfecho</div>"
                "<div class='nota' style='margin:6px 0 0'>"
                "Publicado há %s e <b>ainda sem contrato celebrado</b> no "
                "Portal BASE. Passado este tempo já não costuma ser espera: "
                "metade dos procedimentos fecha em 68 dias e nove em cada "
                "dez em 139. Ou ficou deserto ou anulado, ou o contrato não "
                "chegou ao dump semanal do IMPIC.</div></div>"
                % ("%s dias" % mil_pt(dias)))

    soma = sum(l["preco_contratual"] or 0.0 for l in linhas)
    desconto, base, fonte = desconto_do_desfecho(
        linhas, euros_do_texto(a["preco_base"] or ""))

    # Os adjudicatarios do procedimento inteiro, sem repetir quem ganhou
    # dois lotes. Pela chave e nao pelo nome, que e a regra do corpus.
    ganhadores = {}
    for l in linhas:
        for chave, nome in ganhadores_da_linha(l):
            ganhadores.setdefault(chave or "n:" + nome, nome)
    # Com muitos lotes o somario deixava de ser um somario: o 10011/2026
    # tem dez lotes e dez vencedores, e a lista dos nomes no cartao era
    # um paragrafo que empurrava os numeros para fora do olho. Acima de
    # tres conta-se, e os nomes lêem-se na tabela -- que so existe
    # quando ha mais de uma linha. Num contrato so, um agrupamento de
    # cinco escreve-se por extenso: nao ha outro sitio onde apareca.
    quem = " + ".join(liga_entidade(ch, n) for ch, n in ganhadores.items())
    if len(ganhadores) > 3 and len(linhas) > 1:
        quem = ("%d adjudicatários <span>na tabela abaixo</span>"
                % len(ganhadores))

    somario = [("Contratado", euros(soma)),
               ("Quem ganhou", quem or "—")]
    if base > 0:
        somario.append(("Preço base", euros(base)
                        + ("" if fonte == "corpus"
                           else " <span>do anúncio</span>")))
    if desconto is not None:
        somario.append(("Abaixo da base", pct_pt(desconto)))
    somario.append(("Celebrado", data_pt(linhas[-1]["data_celebracao"])))

    corpo = []
    for l in linhas:
        venceu = " + ".join(liga_entidade(ch, n)
                            for ch, n in ganhadores_da_linha(l)) or "—"
        corpo.append(
            "<tr><td class='d'>%s</td><td class='o'>%s</td>"
            "<td class='g'>%s</td><td class='d'>%s</td><td class='p'>%s</td></tr>"
            % (data_pt(l["data_celebracao"]),
               html.escape(corta(l["objecto"] or "", 140)),
               venceu,
               ("%s dias" % mil_pt(l["prazo_execucao"]))
               if l["prazo_execucao"] else "—",
               euros(l["preco_contratual"])))

    # Uma linha so nao e um lote: a tabela por baixo do somario nao se
    # desenha, porque repetia os mesmos numeros noutra forma.
    tabela = ("<div class='mercado-tab'><table class='tab-mercado'><thead><tr>"
              "<th>Celebrado</th><th>Objecto</th><th>Quem ganhou</th>"
              "<th>Execução</th><th class='p'>Preço</th></tr></thead>"
              "<tbody>%s</tbody></table></div>" % "".join(corpo)
              ) if len(linhas) > 1 else ""

    return ("<div class='cx mercado' id='desfecho'>"
            "<div class='rot'>Desfecho</div>"
            "<div class='nota' style='margin:6px 0 12px'>"
            "%s, do Portal BASE. Liga-se pelo número deste anúncio "
            "(<code>%s</code>) e não por semelhança, por isso ou é este "
            "procedimento ou não aparece.%s</div>"
            "<div class='desfecho-som'>%s</div>%s</div>"
            % ("O que este procedimento deu" if len(linhas) == 1
               else "Os %d contratos deste procedimento" % len(linhas),
               html.escape(a["ref"]),
               " Os lotes somam-se antes de dividir: o desconto é do "
               "procedimento, não de cada linha." if len(linhas) > 1 else "",
               "".join("<div><b>%s</b><span>%s</span></div>" % (v, r)
                       for r, v in somario),
               tabela))


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
        venceu = " + ".join(liga_entidade(ch, n)
                            for ch, n in ganhadores_da_linha(l)) or "—"
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
    if vindo.path in ("/", "/calendario"):
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
    for p in propostas_de(a["ref"]):
        chips.append("<span class='tag %s'>%s%s</span>"
                     % ("" if p["estado"] in ESTADOS_FECHADOS else "ok",
                        html.escape(estado_da_casa(p["estado"])),
                        " L%d" % p["lote"] if p["lote"] else ""))
        if p["motivo"]:
            chips.append("<span class='tag'>%s</span>" % html.escape(p["motivo"]))

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
    # Só enquanto o concurso NÃO está na escada (15/09/2026). A partir
    # daí quem manda é o selector do bloco «A nossa proposta», logo por
    # baixo: dois controlos para o mesmo estado, a um palmo um do
    # outro, é a ficha a perguntar duas vezes o que já respondeu.
    if not propostas_de(ref) and not e_alteracao:
        decidir.append(accao("/estado/%s/analisar" % quote(ref, safe=""),
                             "Interessa", "bt verde"))
        decidir.append(forma_abandonar(ref, "bt cuidado", "Abandonar",
                                       a["titulo"] or ref))
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
        # As linhas sem valor saem da tabela para uma frase por baixo
        # (UX-Auditoria, Miller/Pragnanz, decisao do Afonso a 8/09/2026):
        # num "por ver" sem pecas lidas eram 8 linhas em 12 a dizer "so
        # consta das pecas", e o bloco mais rapido de ler era o que tinha
        # mais linhas sem conteudo. Agrupam-se por razao, para a frase
        # continuar a dizer ONDE cada campo esta.
        sem_valor = []
        for rotulo, valor, em_falta, nota in essencial_do_anuncio(
                a, seccoes, analise_de(ref)):
            if em_falta or not valor:
                sem_valor.append((em_falta or "o anúncio não indica", rotulo))
                continue
            celula = desenha_valor(valor)
            if nota:
                celula += "<span class='nota-campo'>%s</span>" % html.escape(nota)
            linhas_ess.append("<div class='par'><dt>%s</dt><dd>%s</dd></div>"
                              % (html.escape(rotulo), celula))
        seccoes_html = ("<div class='cx essencial'><dl>%s</dl>%s</div>"
                        % ("".join(linhas_ess),
                           frase_dos_campos_em_falta(sem_valor)))
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
    # O desfecho desenha-se aqui, antes do indice, porque e ele que diz
    # se ha entrada no indice: um chip que salta para um bloco que nao
    # existe e a mesma mentira de um numero que abre outra lista.
    desfecho_html = desfecho_cx(a)
    lotes_html = lotes_cx(a)
    args_ess = dict(request.args.to_dict()); args_ess.pop("modo", None)
    args_com = dict(request.args.to_dict(), modo="completo")
    indice = ("<div class='ficha-indice'>"
              "<a class='%s' href='/anuncio/%s?%s'>Essencial</a>"
              "<a class='%s' href='/anuncio/%s?%s'>Anúncio completo</a>"
              "%s"
              "<a href='#pecas'>Peças</a>"
              "%s"
              "<a href='#mercado'>Mercado</a>"
              "<a href='#historico'>Histórico</a>"
              "<span class='dir'>%s%s</span></div>"
              % ("on" if not completo else "", ref, urlencode(args_ess),
                 "on" if completo else "", ref, urlencode(args_com),
                 "<a href='#lotes'>Lotes</a>" if lotes_html else "",
                 "<a href='#desfecho'>Desfecho</a>" if desfecho_html else "",
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
            # "Ver se há peças novas" (14/09/2026): a lista da plataforma
            # comparada com a da base, sem apagar nada -- o "Actualizar
            # peças" ao lado apaga e traz tudo, e leva o texto extraido.
            vigiadas = a["pecas_vigiadas_em"] if "pecas_vigiadas_em" in a.keys() else ""
            accoes_docs = (
                "<div class='accoes' style='margin-top:14px'>%s%s%s</div>%s"
                % (accao("/analisar/%s" % ref,
                         "Reler pelo modelo" if analise else "Ler as peças",
                         "bt" if analise else "bt forte"),
                   accao("/pecas-novas/%s" % ref, "Ver se há peças novas"),
                   accao("/documentos/%s" % ref, "Actualizar peças"),
                   ("<div class='nota' style='margin-top:8px'>Peças novas "
                    "verificadas na plataforma a %s. O radar volta lá sozinho "
                    "depois da data de esclarecimentos e quando o prazo ou o "
                    "preço base mudam.</div>" % html.escape(data_hora_pt(vigiadas)))
                   if vigiadas else
                   "<div class='nota' style='margin-top:8px'>O radar vai à "
                   "plataforma ver se há peças novas depois da data de "
                   "esclarecimentos e quando o prazo ou o preço base mudam.</div>"))
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
        caminho = caminho_na_pasta(ref, peca_aberta)
        if caminho:
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

    # O responsavel e da proposta; com lotes, todos os cartoes do mesmo
    # procedimento tem o mesmo, e por isso basta ler o primeiro.
    propostas_aqui = propostas_de(ref)
    resp = (propostas_aqui[0]["responsavel"] if propostas_aqui else "") or ""
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
                # "a pagina do anuncio e sempre a mesma" (15/09/2026): com
                # o quadro fora, e aqui que a proposta se trabalha -- a
                # ranhura, os campos que ela pede, as etiquetas e o que
                # falta fazer. Vai logo a seguir ao cabecalho porque e a
                # primeira pergunta de quem abre a ficha de um concurso
                # que ja esta na escada.
                proposta_cx(a) +
                seccoes_html + lotes_html +
                docs_cx +
                desfecho_html +
                "<div id='mercado'>" + homologos_cx(a, ch_ent) +
                mercado(a) + "</div>" +
                contactos_cx(a) +
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
                    script=espera + caixa_do_motivo(),
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


@app.route("/pecas-novas/<path:ref>", methods=["POST"])
def pecas_novas(ref):
    """O botao "Ver se há peças novas". Corre dentro do pedido, de
    proposito: e UM anuncio, a lista da plataforma vem em segundos, e
    quem carregou quer ver a resposta -- "2 peças novas: X, Y" ou
    "nenhuma" -- e nao um "a verificar..." para ir ver ao historico."""
    with liga() as c:
        a = c.execute("SELECT ref, plataforma, link_pecas, docs_estado "
                      "FROM anuncios WHERE ref=?", (ref,)).fetchone()
    if not a:
        return redirect("/anuncio/" + ref)
    if not (a["link_pecas"] or "").strip():
        aviso = "Este anúncio não indica onde estão as peças."
    elif a["docs_estado"] not in ("ok", "parcial"):
        aviso = "Traz primeiro as peças: sem elas não há com que comparar."
    else:
        antes = set(nomes_das_pecas(ref))
        quem = quem_sou() or "plataforma"
        novas, erro = vigiar_anuncio(a, razao="a pedido, pela ficha",
                                     reler=lambda r: pedir_analise(r, quem))
        if erro:
            aviso = "Não consegui ver a lista das peças: %s." % erro
        elif novas:
            nomes = [n for n in nomes_das_pecas(ref) if n not in antes]
            aviso = "%d peça%s nova%s: %s. A reler pelo modelo." % (
                novas, "" if novas == 1 else "s", "" if novas == 1 else "s",
                ", ".join(nomes) or "ver a lista")
        else:
            aviso = "Nenhuma peça nova na plataforma."
    return redirect("/anuncio/%s?%s" % (ref, urlencode({"aviso": aviso})))


def nomes_das_pecas(ref):
    with liga() as c:
        return [r["nome"] for r in c.execute(
            "SELECT nome FROM documentos WHERE ref=? ORDER BY nome", (ref,))]


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
    caminho = caminho_na_pasta(ref, nome)
    if not caminho:
        return ("Documento não encontrado. <a href='/anuncio/%s'>voltar</a>"
                % html.escape(ref, quote=True)), 404
    # So o que e inofensivo abre dentro do browser. As pecas vem das
    # plataformas, e um .html ou .svg servido em linha corria no
    # dominio do painel, com a sessao (auditoria de 14/09/2026): o
    # resto descarrega-se, e leva um CSP de caixa fechada por via das
    # duvidas.
    tipo = abre_no_browser(caminho)
    inofensivo = bool(tipo)
    resposta = send_file(caminho, as_attachment=not inofensivo,
                         download_name=os.path.basename(caminho),
                         mimetype=tipo if inofensivo else "application/octet-stream")
    if not inofensivo:
        resposta.headers["Content-Security-Policy"] = "sandbox"
    return resposta


# O que pode abrir em linha: o visualizador do browser para PDF, as
# imagens e o texto simples. Um nome sem extensao conhecida e "outra
# coisa" e descarrega-se.
EXTENSOES_INOFENSIVAS = (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".txt")


def abre_no_browser(caminho):
    """O tipo MIME com que a peca pode abrir em linha, ou None. Pela
    extensao; e, sem extensao conhecida, pelos primeiros bytes: as
    pecas da anogov/ComprasPT chegam com o nome que a plataforma da
    ("Caderno de Encargos", sem .pdf) e sao PDF na mesma -- e sem o tipo
    certo o browser descarregava-as, mesmo em linha."""
    ext = os.path.splitext(caminho)[1].lower()
    if ext in EXTENSOES_INOFENSIVAS:
        return mimetypes.guess_type(caminho)[0] or "application/octet-stream"
    try:
        with open(caminho, "rb") as f:
            inicio = f.read(8)
    except OSError:
        return None
    for magia, tipo in ((b"%PDF", "application/pdf"), (b"\x89PNG", "image/png"),
                        (b"\xff\xd8\xff", "image/jpeg"), (b"GIF8", "image/gif")):
        if inicio.startswith(magia):
            return tipo
    return None


@app.route("/peca-pagina/<path:ref>/<nome>/<int:n>.png")
def peca_pagina(ref, nome, n):
    """Uma pagina da peca desenhada pelo servidor (PNG). E o que faz o
    visualizador proprio funcionar em qualquer browser."""
    caminho = caminho_na_pasta(ref, nome)
    if not caminho:
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
        return ("<details class='sec' style='margin-top:14px'><summary>"
                "<span class='st'>Texto extraído da peça</span>"
                "<span class='sh'>pesquisável com o Ctrl+F da página, mesmo "
                "quando o visualizador não abre</span></summary>%s</details>"
                % "".join(paginas_html))
    # 'imagem' e legado do OCR que saiu a 03/09/2026 e quer dizer o
    # mesmo que 'scan': o PDF nao tem texto que se possa ler.
    if d and d["texto_estado"] in ("scan", "imagem"):
        return ("<div class='nota' style='margin-top:14px'>Este PDF é "
                "uma digitalização: não tem texto extraível. Abre-se no "
                "visualizador, mas não se procura lá dentro.</div>")
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
    caminho = caminho_na_pasta(ref, nome)
    if not caminho:
        return envolver(
            "anuncios", "Peça não encontrada",
            "O ficheiro já não está na pasta dos documentos.",
            "<div class='vazio'>Volta à <a href='/anuncio/%s'>ficha do "
            "anúncio</a> e carrega em &ldquo;Actualizar peças&rdquo;."
            "</div>" % html.escape(ref, quote=True),
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


@app.route("/tarefa/nova", methods=["POST"])
def tarefa_nova():
    """Uma tarefa escrita à mão, da ficha. A proposta vem no formulário
    -- com lotes há uma por lote, e adivinhar qual pela `ref` punha a
    tarefa no cartão errado."""
    ref = " ".join((request.form.get("ref") or "").split()) or None
    try:
        proposta_id = int(request.form.get("proposta_id") or 0) or None
    except ValueError:
        proposta_id = None
    criar_tarefa(request.form.get("o_que"),
                 data_do_texto(request.form.get("quando")),
                 proposta_id=proposta_id, ref=ref)
    return volta_ao_referer("/anuncio/" + (ref or ""))


@app.route("/tarefa/<int:id_>/feita", methods=["POST"])
def tarefa_feita(id_):
    t = marcar_tarefa(id_, True)
    if not t:
        return volta_ao_referer("/")
    return _volta_com_aviso("«%s» feita." % corta(t["o_que"], 60),
                            "/tarefa/%d/por-fazer" % id_)


@app.route("/tarefa/<int:id_>/por-fazer", methods=["POST"])
def tarefa_por_fazer(id_):
    """O desfazer do «feita». Sem ele, riscar a tarefa errada numa lista
    de vinte não tinha volta -- e é o erro mais fácil de cometer."""
    marcar_tarefa(id_, False)
    return volta_ao_referer("/")


# --- mudar de ranhura a partir da linha (15/09/2026, decisao dele)
#
# "o quadro deixa de ser preciso tal como a lista. na verdade eu devo
# conseguir passar entre estados aqui" -- e tinha razao: oito colunas e
# oito abas sao a mesma coisa duas vezes, e a diferenca era o arrastar,
# que so compensa quando se ve tudo ao mesmo tempo. Com uma coluna por
# aba nao ha para onde arrastar.
#
# O que fica no lugar e um selector por linha. E o unico controlo que
# cabe numa linha com oito destinos: dois botoes de avancar/recuar
# davam um gesto ao percurso normal e varios a qualquer salto, e saltar
# e o caso -- um "Nao fomos" nao vem a seguir ao "Relatorio preliminar".


@app.route("/escada/<path:ref>", methods=["POST"])
def escada_do_anuncio(ref):
    """Muda a ranhura de um concurso do DR. O estado vem no CORPO e nao
    no caminho, ao contrario do `/estado/<ref>/<novo>`: um `<select>` nao
    sabe escrever um URL, e sem isto o selector precisava de JS para
    funcionar de todo -- e o que degrada mal e um controlo que nao faz
    nada com o JS desligado."""
    return mudar_estado(ref, (request.form.get("estado") or "").strip())


@app.route("/proposta/<int:id_>/escada", methods=["POST"])
def escada_da_proposta(id_):
    """O mesmo para uma proposta SEM anuncio (D2): essas nao tem `ref`
    por onde lhes pegar, e o `/estado/<ref>/...` nao lhes serve."""
    p = proposta(id_)
    if not p:
        return volta_ao_referer("/")
    if p["ref"]:
        return mudar_estado(p["ref"], (request.form.get("estado") or "").strip())
    estado = (request.form.get("estado") or "").strip()
    motivo = (request.form.get("motivo") or "").strip()
    permitidos = MOTIVOS_DO_ESTADO.get(estado)
    if permitidos and motivo not in permitidos:
        return _volta_com_aviso("Escolhe o motivo antes de continuar.")
    ok, recado = mover_proposta(id_, estado)
    if not ok:
        return _volta_com_aviso(recado)
    if motivo or permitidos:
        gravar_motivo(id_, motivo)
    return _volta_com_aviso("«%s»: %s."
                            % (corta(p["titulo"] or p["entidade"] or "", 70),
                               estado_da_casa(estado)))


# --- fechar o ciclo com o Portal BASE (etapa 4, 15/09/2026)
#
# Submetemos uma proposta; meses depois o Estado publica em quem caiu o
# procedimento e por quanto. O radar ja tinha as duas pontas -- a
# proposta na escada e o `contratos.db` -- e faltava liga-las.
#
# **A ligacao e por CHAVE, e nao por semelhanca.** Medido a 15/09/2026
# na base dele: o `contratos.n_anuncio` do dump do IMPIC vem no mesmo
# formato do `ref` ("17161/2026"), e 69,4% dos anuncios de 2024 ja tem
# contrato celebrado (contra 5,3% dos de 2026, que e o ciclo a demorar
# meses). O plano previa o maquinario de semelhanca do `casa.py`
# (LIMIAR, FOLGA); nao e preciso nenhum -- ou e o mesmo procedimento ou
# nao e nada. O `desfecho_do_anuncio()`, que ja existia para a ficha,
# faz exactamente essa juncao.
#
# **Propoe, nunca decide** (palavra dele: "isto avanca-se sempre com a
# confirmacao de um humano para fechar o resultado"). O que o Portal
# BASE sabe e a quem foi adjudicado; se esse alguem somos nos, so a
# casa sabe -- e por isso os dois botoes ficam ao lado do facto, e nao
# um estado escrito nas nossas costas.


def _nome_da_casa(cfg=None):
    """(nome, nif) da empresa, do config.json. Vazios enquanto ninguem os
    escrever -- e a funcionalidade tem de valer na mesma: sem eles, o
    ecra mostra a quem foi adjudicado e pergunta se fomos nos."""
    cfg = ler_config() if cfg is None else cfg
    return ((cfg.get("nome_da_casa") or "").strip(),
            re.sub(r"\D", "", cfg.get("nif_da_casa") or ""))


def fomos_nos(linhas, cfg=None):
    """Se a casa está entre os adjudicatários deste desfecho.

    Devolve True, False, ou **None quando não se pode saber** -- que é o
    caso enquanto o NIF da casa não estiver no `config.json`. Três
    respostas e não duas de propósito: um False de quem não sabe é uma
    afirmação falsa, e era com base nele que a proposta ia fechar.
    """
    nome, nif = _nome_da_casa(cfg)
    if not (nome or nif):
        return None
    for l in linhas:
        for chave in (l["ganhou_ch"] or "").split("|"):
            if nif and re.sub(r"\D", "", chave or "") == nif:
                return True
        for quem in (l["ganhou"] or "").split("|"):
            if nome and simplifica(nome) and simplifica(nome) in simplifica(quem):
                return True
    return False


def propostas_por_fechar(limite=50):
    """As propostas ainda abertas cujo procedimento JÁ foi adjudicado.

    São as que ficam meses em «Submetido» à espera de alguém se lembrar
    de as fechar -- e o Estado já publicou o desfecho. Só as das
    ranhuras onde ainda se espera resposta: uma «A preparar proposta»
    com contrato celebrado quer dizer que se perdeu o prazo, e isso não
    se fecha sozinho, olha-se.
    """
    if not ha_corpus():
        return []
    with liga() as c:
        abertas = c.execute(
            "SELECT * FROM propostas WHERE estado IN ('submetido','relatorio') "
            "AND ref IS NOT NULL ORDER BY COALESCE(fechada_em, criada_em)"
        ).fetchall()
    fora = []
    for p in abertas:
        linhas = desfecho_do_anuncio(p["ref"])
        if linhas:
            fora.append((p, linhas))
        if len(fora) >= limite:
            break
    return fora


def desvio_do_proposto(valor_proposta, linhas):
    """(desvio 0..1, o que ganhou) entre o que propusemos e o que o
    procedimento foi adjudicado, ou (None, None).

    É o número que a etapa 4 existe para dar -- «perdeste para a X por
    18% abaixo do teu preço» --, e é uma conta que só se pode fazer
    quando as duas pontas são do mesmo âmbito: o nosso preço proposto e
    a soma dos contratos daquele procedimento. Com lotes soma-se antes
    de dividir, que é a mesma regra do `desconto_do_desfecho()`; por
    linha, cada lote comparava-se com a nossa proposta inteira e dava um
    número que mente com ar de certo.
    """
    nosso = euros_do_texto(valor_proposta)
    if not nosso:
        return None, None
    ganhou = sum(l["preco_contratual"] or 0.0 for l in linhas)
    if not ganhou:
        return None, None
    return (nosso - ganhou) / nosso, ganhou


def faixa_do_desfecho(p, linhas, cfg=None):
    """A faixa que propõe fechar uma proposta, no bloco da ficha.

    Diz o facto -- a quem foi adjudicado, por quanto, quando -- e
    oferece os dois botões. **Não decide**: quando o NIF da casa está
    configurado adianta qual dos dois é, mas o gesto continua a ser de
    quem lê.
    """
    if not linhas or p["estado"] in ESTADOS_FECHADOS:
        return ""
    quem = []
    for l in linhas:
        quem += [q for q in (l["ganhou"] or "").split("|") if q]
    ganhou = sum(l["preco_contratual"] or 0.0 for l in linhas)
    quando = max((l["data_celebracao"] or "") for l in linhas)
    nosso, _ = _nome_da_casa(cfg)
    somos = fomos_nos(linhas, cfg)
    if somos is True:
        veredicto = "<b>A adjudicação é nossa.</b>"
    elif somos is False:
        veredicto = "<b>Não fomos nós.</b>"
    else:
        veredicto = ("Não sei se fomos nós: falta o NIF da casa em "
                     "<a href='/configuracoes/conta'>Configurações › Conta</a>.")
    desvio, _ = desvio_do_proposto(p["valor_proposta"], linhas)
    conta = ""
    if desvio is not None and somos is not True:
        conta = (" A nossa proposta estava <b>%s%.1f%%</b> %s."
                 % ("+" if desvio < 0 else "", abs(desvio) * 100,
                    "acima" if desvio > 0 else "abaixo"))
    return ("<div class='desfecho-propoe'>"
            "<div class='dp-facto'>O Portal BASE diz que este procedimento "
            "foi adjudicado a <b>%s</b> por <b>%s</b>%s. %s%s</div>"
            "<div class='dp-botoes'>%s%s<a class='bt-leve' href='#desfecho'>"
            "ver os contratos</a></div></div>"
            % (html.escape(" · ".join(dict.fromkeys(quem)) or "alguém"),
               euros(ganhou) if ganhou else "valor não publicado",
               (", a " + data_pt(quando)) if quando else "",
               veredicto, conta,
               accao("/proposta/%d/escada" % p["id"], "Ganhámos", "mini verde",
                     campos={"estado": "ganho"}),
               accao("/proposta/%d/escada" % p["id"], "Perdemos", "mini",
                     campos={"estado": "perdido", "motivo": "Preço"})))


# --- os contactos (etapa 6, 15/09/2026)
#
# Quem e a pessoa do lado de la. Foi a ultima etapa do plano de
# proposito -- e do que se sente falta mais tarde, quando ja ha
# concursos que se repetem com o mesmo cliente.
#
# Sao da ENTIDADE e nao do concurso: a pessoa que responde aos
# esclarecimentos do IPL responde aos do ano que vem tambem. A chave e a
# `entidade_chave` do corpus dos contratos (o NIF, quando se sabe) com
# recurso ao nome normalizado -- a mesma que a ficha da entidade usa,
# para os contactos e o historico de contratos falarem do mesmo cliente.


def chave_da_entidade(a):
    """A chave por onde os contactos de um anuncio se procuram: o NIF se
    o anuncio o trouxer, senao o nome normalizado.

    Duas fontes e uma so chave, de proposito: o radar so guarda o nome
    que o DR escreve, e 93,7% das entidades acham-se pelo nome
    normalizado (medido, ver `norma_entidade()`). Uma entidade cujo NIF
    apareca so mais tarde continua a achar os contactos que ja tinha --
    porque a procura tenta as duas.
    """
    nif = re.sub(r"\D", "", _valor(a, "nif") or "")
    return nif or norma_entidade(_valor(a, "entidade") or "")


def contactos_de(chaves):
    """Os contactos de uma entidade, por qualquer das suas chaves."""
    chaves = [c for c in (chaves if isinstance(chaves, (list, tuple))
                          else [chaves]) if c]
    if not chaves:
        return []
    with liga() as c:
        return c.execute(
            "SELECT * FROM contactos WHERE entidade_chave IN (%s) "
            "ORDER BY nome" % ",".join("?" * len(chaves)), chaves).fetchall()


def criar_contacto(chave, nome, papel="", email="", telefone="", notas="",
                   entidade="", quem=None):
    """Um contacto novo. Devolve o id, ou None sem nome -- um contacto
    sem nome nao se encontra depois, que e o mesmo que nao existir."""
    nome = " ".join((nome or "").split())[:120]
    if not (nome and chave):
        return None
    with liga() as c:
        cur = c.execute(
            "INSERT INTO contactos (entidade_chave, entidade, nome, papel,"
            " email, telefone, notas, criado_em) VALUES (?,?,?,?,?,?,?,?)",
            (chave, " ".join((entidade or "").split())[:160], nome,
             " ".join((papel or "").split())[:80],
             " ".join((email or "").split())[:120],
             " ".join((telefone or "").split())[:40],
             " ".join((notas or "").split())[:300],
             datetime.now().strftime("%Y-%m-%d %H:%M")))
        id_ = cur.lastrowid
    registar("", "contacto", "%s (%s)" % (nome, entidade or chave), quem)
    return id_


def contactos_cx(a):
    """O bloco dos contactos na ficha. São da ENTIDADE: a pessoa que
    responde aos esclarecimentos deste concurso responde aos do ano que
    vem, e é por isso que aparecem em todos os concursos dela."""
    chave = chave_da_entidade(a)
    if not chave:
        return ""
    linhas = contactos_de(chave)
    postos = "".join(
        "<div class='ct'><div class='ct-nome'>%s%s</div>%s%s%s"
        "<div class='ct-x'>%s</div></div>"
        % (html.escape(l["nome"]),
           " <span class='ct-papel'>%s</span>" % html.escape(l["papel"])
           if l["papel"] else "",
           "<a class='ct-l' href='mailto:%s'>%s</a>"
           % (html.escape(l["email"], quote=True), html.escape(l["email"]))
           if l["email"] else "",
           "<span class='ct-l'>%s</span>" % html.escape(l["telefone"])
           if l["telefone"] else "",
           "<div class='ct-notas'>%s</div>" % html.escape(l["notas"])
           if l["notas"] else "",
           accao("/contacto/%d/apagar" % l["id"], "&times;", "etq-x",
                 confirmar="Apagar o contacto «%s»?"
                           % (l["nome"] or "").replace("'", " ")))
        for l in linhas) or "<p class='nota'>Ainda não há contactos aqui.</p>"
    return ("<div class='cx lado-cx' id='contactos'>"
            "<div class='rot' style='margin-bottom:4px'>Contactos</div>"
            "<div class='nota' style='margin-bottom:12px'>De <b>%s</b>, e "
            "não deste concurso: aparecem em todos os que forem dela.</div>"
            "%s"
            "<form class='ct-novo' method='post' action='/contacto/nova'>"
            "<input type='hidden' name='chave' value='%s'>"
            "<input type='hidden' name='entidade' value='%s'>"
            "<input type='hidden' name='volta' value='%s'>"
            "<input type='text' name='nome' placeholder='nome' required "
            "maxlength='120'>"
            "<input type='text' name='papel' placeholder='cargo' maxlength='80'>"
            "<input type='email' name='email' placeholder='e-mail' maxlength='120'>"
            "<input type='text' name='telefone' placeholder='telefone' "
            "maxlength='40'>"
            "<button type='submit'>juntar</button></form></div>"
            % (html.escape(a["entidade"] or "esta entidade"), postos,
               html.escape(chave, quote=True),
               html.escape(a["entidade"] or "", quote=True),
               html.escape(a["ref"], quote=True)))


@app.route("/contacto/nova", methods=["POST"])
def contacto_novo():
    ref = (request.form.get("volta") or "").strip()
    criar_contacto(
        (request.form.get("chave") or "").strip(),
        request.form.get("nome"), request.form.get("papel"),
        request.form.get("email"), request.form.get("telefone"),
        request.form.get("notas"), request.form.get("entidade"))
    return volta_ao_referer("/anuncio/" + quote(ref, safe="") if ref else "/")


@app.route("/contacto/<int:id_>/apagar", methods=["POST"])
def contacto_apagar(id_):
    with liga() as c:
        l = c.execute("SELECT * FROM contactos WHERE id=?", (id_,)).fetchone()
        if l:
            c.execute("DELETE FROM contactos WHERE id=?", (id_,))
    if l:
        registar("", "contacto", "apagado: %s" % l["nome"])
    return volta_ao_referer("/")


# --- o bloco "A nossa proposta" na ficha (15/09/2026)
#
# "e a pagina do anuncio e sempre a mesma" -- palavra dele. Com o quadro
# fora, este bloco e a casa de tudo o que o cartao fazia: a ranhura, os
# campos que ela pede, o que a casa decide (tipologia, CV, proposta
# tecnica, CoE, notas), as etiquetas e o que falta fazer.
#
# Com LOTES ha uma proposta por lote (D3), e por isso ha um destes por
# cada: e o mesmo procedimento, e sao decisoes diferentes.

CAMPOS_DA_CASA = (("tipologia", "Tipologia", TIPOLOGIAS),
                  ("cv", "CV", SIM_NAO),
                  ("proposta_tecnica", "Proposta técnica", SIM_NAO))


def _campos_que_a_ranhura_pede(p):
    """Os campos do estado, para a ficha. O mesmo âmbito do cartão do
    quadro -- cada campo pertence a uma ranhura e a mais nenhuma --, e a
    mesma rota que os grava."""
    estado = p["estado"]
    pecas = []
    if estado in ESTADOS_COM_PROPOSTO:
        pecas.append(
            "<label>Preço proposto<input type='text' name='valor_proposta' "
            "value='%s' placeholder='ex. 118.500,00'></label>"
            % html.escape(p["valor_proposta"] or "", quote=True))
    if estado in ("relatorio", "ganho", "perdido"):
        pecas.append(
            "<label>Lugar<input type='number' name='lugar' min='1' max='99' "
            "value='%s'></label>"
            % ("" if p["lugar"] is None else int(p["lugar"])))
        pecas.append(
            "<label>Os três primeiros<input type='text' name='top3' "
            "value='%s' placeholder='1º … · 2º … · 3º …'></label>"
            % html.escape(p["top3"] or "", quote=True))
    permitidos = MOTIVOS_DO_ESTADO.get(estado)
    if permitidos:
        pecas.append(
            "<label>%s<select name='motivo'>"
            "<option value=''>escolhe…</option>%s</select></label>"
            % (html.escape(PEDIDO_DO_ESTADO.get(estado, "Motivo")),
               "".join("<option value='%s'%s>%s</option>"
                       % (html.escape(m, quote=True),
                          " selected" if m == (p["motivo"] or "") else "",
                          html.escape(m)) for m in permitidos)))
    return "".join(pecas)


def _tarefas_da_ficha(p):
    """O que falta fazer nesta proposta, e a caixa de acrescentar.

    As automáticas dizem-se automáticas: quem as lê tem de saber que a
    data vem do DR e muda sozinha se houver prorrogação.
    """
    por_fazer = tarefas_por_proposta([p["id"]]).get(p["id"], [])
    linhas = []
    for t in por_fazer:
        texto_prazo, classe = etiqueta_prazo(t["quando"], dias_urgente())
        linhas.append(
            "<li>%s<span class='t'>%s</span>%s%s</li>"
            % (accao("/tarefa/%d/feita" % t["id"], "&#10003;", "tq"),
               html.escape(t["o_que"]),
               ("<span class='tag %s'>%s</span>"
                % (classe, html.escape(texto_prazo or data_pt(t["quando"]))))
               if t["quando"] else "",
               "<span class='tag' title='vem das datas do DR e "
               "acompanha-as'>automática</span>"
               if t["origem"] in ORIGENS_AUTOMATICAS else ""))
    lista = ("<ul class='tarefas'>%s</ul>" % "".join(linhas)) if linhas else (
        "<p class='nota'>Nada por fazer.</p>")
    juntar = ("<form class='tarefa-nova' method='post' action='/tarefa/nova'>"
              "<input type='hidden' name='ref' value='%s'>"
              "<input type='hidden' name='proposta_id' value='%d'>"
              "<input type='text' name='o_que' maxlength='200' required "
              "placeholder='o que falta fazer…'>"
              "<input type='text' name='quando' inputmode='numeric' "
              "placeholder='dd/mm/aaaa' maxlength='10' "
              "pattern='\\d{1,2}/\\d{1,2}/\\d{4}'>"
              "<button type='submit'>juntar</button></form>"
              % (html.escape(p["ref"] or "", quote=True), p["id"]))
    return ("<div class='prop-tarefas'><div class='rot'>O que falta fazer"
            "</div>%s%s</div>" % (lista, juntar))


def _etiquetas_da_ficha(ref):
    """As etiquetas viviam no cartão do quadro; com o quadro fora, a casa
    delas é a ficha. Sem isto a funcionalidade ficava na base e sem
    porta nenhuma no ecrã."""
    if not ref:
        return ""
    with liga() as c:
        minhas = c.execute(
            "SELECT e.* FROM etiquetas e JOIN anuncio_etiquetas ae "
            "ON ae.etiqueta_id = e.id WHERE ae.ref=? ORDER BY e.nome",
            (ref,)).fetchall()
        todas = c.execute("SELECT nome FROM etiquetas ORDER BY nome").fetchall()
    postas = "".join(
        "<span class='etq' style='background:%s'>%s%s</span>"
        % (e["cor"], html.escape(e["nome"]),
           accao("/etiqueta/%s/tirar/%d" % (quote(ref, safe=""), e["id"]),
                 "&times;", "etq-x"))
        for e in minhas)
    return ("<div class='prop-etq'><div class='rot'>Etiquetas</div>%s"
            "<form class='etq-form' method='post' action='/etiqueta/%s/nova'>"
            "<input type='text' name='nome' placeholder='+ etiqueta' "
            "list='etiquetas-existentes' maxlength='24'></form>"
            "<datalist id='etiquetas-existentes'>%s</datalist></div>"
            % (postas, quote(ref, safe=""),
               "".join("<option value='%s'>" % html.escape(t["nome"], quote=True)
                       for t in todas)))


def proposta_cx(a):
    """O bloco «A nossa proposta» da ficha. Um por lote quando há lotes.

    Sem proposta nenhuma, mostra a porta de entrada e mais nada: um
    formulário de dez campos por cima de um concurso que ainda não se
    decidiu é uma pergunta antes do tempo.
    """
    ref = a["ref"]
    minhas = propostas_de(ref)
    if not minhas:
        return ("<div class='cx lado-cx' id='proposta'>"
                "<div class='rot' style='margin-bottom:12px'>A nossa proposta"
                "</div><p class='nota'>Este concurso ainda não está na "
                "escada.</p><div class='prop-accoes'>%s%s</div></div>"
                % (accao("/estado/%s/analisar" % quote(ref, safe=""),
                         "pôr na escada", "mini verde"),
                   forma_abandonar(ref, titulo=a["titulo"] or "")))
    # O desfecho do Portal BASE, uma vez por ficha e nao uma por lote:
    # a juncao e pelo `ref` do procedimento, e com tres lotes seriam
    # tres consultas iguais ao corpus de 2,4 GB.
    desfecho = desfecho_do_anuncio(ref)
    cfg = ler_config()
    blocos = []
    for p in minhas:
        cabeca = estado_da_casa(p["estado"])
        if p["lote"]:
            cabeca = "Lote %d &middot; %s" % (p["lote"], cabeca)
        elif p["lote"] == 0:
            cabeca = "Conjunto &middot; %s" % cabeca
        blocos.append(
            "<div class='prop'><div class='prop-topo'>"
            "<span class='prop-nome'>%s</span>%s</div>"
            "<form class='prop-campos' method='post' action='/proposta/%d/ficha'>"
            "%s%s"
            "<label>Responsável<input type='text' name='responsavel' "
            "value='%s' list='pessoas' placeholder='ninguém'></label>"
            "<label>CoE<input type='text' name='coe' value='%s' "
            "maxlength='60'></label>"
            "<label class='largo'>Notas<input type='text' name='notas' "
            "value='%s' maxlength='500' placeholder='notas…'></label>"
            "<button type='submit'>gravar</button></form>%s</div>"
            % (cabeca,
               selector_de_ranhura("/proposta/%d/escada" % p["id"],
                                   p["estado"], titulo=a["titulo"] or ref),
               p["id"], _campos_que_a_ranhura_pede(p),
               "".join("<label>%s%s</label>"
                       % (rotulo, _opcoes(nome, valores, p[nome]))
                       for nome, rotulo, valores in CAMPOS_DA_CASA),
               html.escape(p["responsavel"] or "", quote=True),
               html.escape(p["coe"] or "", quote=True),
               html.escape(p["notas"] or "", quote=True),
               faixa_do_desfecho(p, desfecho, cfg) + _tarefas_da_ficha(p)))
    return ("<div class='cx lado-cx' id='proposta'>"
            "<div class='rot' style='margin-bottom:12px'>A nossa proposta</div>"
            "%s%s</div>" % ("".join(blocos), _etiquetas_da_ficha(ref)))


@app.route("/proposta/<int:id_>/ficha", methods=["POST"])
def proposta_da_ficha(id_):
    """Grava o bloco da ficha. Cada campo só muda se vier no formulário,
    e só o que mudou vai para o histórico."""
    p = proposta(id_)
    if not p:
        return volta_ao_referer("/")
    campos, valores = [], []
    if "valor_proposta" in request.form:
        bruto = " ".join((request.form.get("valor_proposta") or "").split())
        # No formato do preco base ("118.500,00 EUR"), que e o que o
        # euros_do_texto() e as somas sabem ler -- **nao** no do euros(),
        # que poe espaco nos milhares e faz ler "118" de "118 500 €".
        valor = euros_do_texto(bruto)
        campos.append("valor_proposta")
        valores.append((_texto_do_preco(valor) if valor else bruto) or None)
    if "lugar" in request.form:
        bruto = (request.form.get("lugar") or "").strip()
        try:
            campos.append("lugar")
            valores.append(int(bruto) if bruto else None)
        except ValueError:
            campos.pop()
    for nome, tecto in (("top3", 300), ("coe", 60), ("notas", 500)):
        if nome in request.form:
            campos.append(nome)
            valores.append(" ".join((request.form.get(nome) or "").split())[:tecto]
                           or None)
    for nome, _, permitidos in CAMPOS_DA_CASA:
        if nome in request.form:
            valor = (request.form.get(nome) or "").strip()
            if valor and valor not in permitidos:
                return _volta_com_aviso("«%s» não é um valor de %s."
                                        % (valor, nome))
            campos.append(nome)
            valores.append(valor or None)
    if "motivo" in request.form:
        motivo = (request.form.get("motivo") or "").strip()
        if motivo and motivo not in (MOTIVOS_DO_ESTADO.get(p["estado"]) or ()):
            return _volta_com_aviso("Esse motivo não existe para esta ranhura.")
        campos.append("motivo")
        valores.append(motivo or None)
    if "responsavel" in request.form:
        campos.append("responsavel")
        valores.append(criar_pessoa(request.form.get("responsavel")))
    gravar_campos_da_proposta(id_, campos, valores)
    return volta_ao_referer("/anuncio/" + (p["ref"] or ""))


@app.route("/etiqueta/<path:ref>/nova", methods=["POST"])
def etiqueta_nova(ref):
    nome = (request.form.get("nome") or "").strip()
    if nome:
        with liga() as c:
            existente = c.execute(
                "SELECT id FROM etiquetas WHERE nome=? COLLATE NOCASE",
                (nome,)).fetchone()
            if existente:
                etiqueta_id = existente["id"]
            else:
                n = c.execute("SELECT COUNT(*) n FROM etiquetas").fetchone()["n"]
                cur = c.execute("INSERT INTO etiquetas (nome, cor) VALUES (?,?)",
                                (nome, CORES_ETIQUETA[n % len(CORES_ETIQUETA)]))
                etiqueta_id = cur.lastrowid
            c.execute("INSERT OR IGNORE INTO anuncio_etiquetas VALUES (?,?)",
                      (ref, etiqueta_id))
    return volta_ao_referer("/anuncio/" + ref)


@app.route("/etiqueta/<path:ref>/tirar/<int:etiqueta_id>", methods=["POST"])
def etiqueta_tirar(ref, etiqueta_id):
    with liga() as c:
        c.execute("DELETE FROM anuncio_etiquetas WHERE ref=? AND etiqueta_id=?",
                  (ref, etiqueta_id))
    return volta_ao_referer("/anuncio/" + ref)


# --- a ficha da proposta, e a proposta sem anuncio (D2)
#
# Um concurso do DR tem ficha propria (/anuncio/<ref>) e e la que a
# proposta dele se trabalha -- esta pagina e para o que NAO vem do DR: a
# consulta previa, o ajuste directo, o convite. Sem ela, a decisao D2
# ficava escrita no plano e sem porta no ecra.

CAMPOS_EDITAVEIS_DA_PROPOSTA = (
    ("titulo", "título", 200), ("entidade", "cliente", 120),
    ("porque_sem_ref", "porque não tem anúncio", 120),
    ("preco_base", "preço base", 40), ("valor_proposta", "proposto", 40),
    ("coe", "CoE", 60), ("top3", "os três primeiros", 300),
    ("notas", "notas", 500))


@app.route("/proposta/nova", methods=["GET", "POST"])
def proposta_nova():
    """Uma proposta que nao vem do Diario da Republica (D2).

    Pede so o que nao se pode adivinhar -- cliente e titulo -- e o resto
    edita-se depois na ficha. Um formulario de quinze campos para criar
    uma linha e a maneira de ninguem a criar.
    """
    if request.method == "POST":
        entidade = " ".join((request.form.get("entidade") or "").split())[:120]
        titulo = " ".join((request.form.get("titulo") or "").split())[:200]
        porque = " ".join((request.form.get("porque_sem_ref") or "").split())[:120]
        if not (entidade or titulo):
            return redirect("/proposta/nova?" + urlencode(
                {"aviso": "Uma proposta sem cliente nem título não se "
                          "encontra depois. Escreve pelo menos um."}))
        id_ = criar_proposta(entidade=entidade, titulo=titulo,
                             porque_sem_ref=porque or "não vem do DR")
        return redirect("/proposta/%d?" % id_ + urlencode(
            {"aviso": "Proposta criada. O resto edita-se aqui."}))
    corpo = (
        "<div class='cx'><form method='post' class='form-largo'>"
        "<label>Cliente<input type='text' name='entidade' maxlength='120' "
        "placeholder='ex. Instituto Politécnico de Leiria' autofocus></label>"
        "<label>Título<input type='text' name='titulo' maxlength='200' "
        "placeholder='o objecto do procedimento'></label>"
        "<label>Porque não tem anúncio"
        "<input type='text' name='porque_sem_ref' maxlength='120' "
        "value='consulta prévia' list='sem-ref'></label>"
        "<datalist id='sem-ref'>%s</datalist>"
        "<button type='submit'>criar</button></form></div>"
        % ("".join("<option value='%s'>" % html.escape(v, quote=True)
                   for v in ("consulta prévia", "ajuste directo", "convite",
                             "anterior a 2025", "não sei"))))
    return envolver("anuncios", "Nova proposta",
                    "O que não vem do Diário da República: consulta "
                    "prévia, ajuste directo, convite. O que vem do DR "
                    "põe-se na escada a partir da ficha do anúncio.",
                    "<div class='larg'>" + corpo + "</div>",
                    migalhas=migalhas_de("anuncios", "Nova proposta"),
                    titulo_aba="Nova proposta")


@app.route("/proposta/<int:id_>")
def ficha_da_proposta(id_):
    """A ficha de uma proposta. Para as que tem anuncio, e um atalho: a
    ficha do procedimento e a do anuncio, e e la que esta o que decide
    (as pecas, o CPV, o historico do cliente)."""
    p = proposta(id_)
    if not p:
        return pagina_de_erro(404)
    if p["ref"]:
        return redirect("/anuncio/" + quote(p["ref"], safe=""))
    escada = "".join(
        "<option value='%s'%s>%s</option>"
        % (ch, " selected" if ch == p["estado"] else "", html.escape(rot))
        for ch, rot in ESTADOS_DA_CASA)
    permitidos = MOTIVOS_DO_ESTADO.get(p["estado"])
    motivo_html = ""
    if permitidos:
        motivo_html = (
            "<label>%s<select name='motivo'>"
            "<option value=''>escolhe…</option>%s</select></label>"
            % (html.escape(PEDIDO_DO_ESTADO.get(p["estado"], "motivo")),
               "".join("<option value='%s'%s>%s</option>"
                       % (html.escape(m, quote=True),
                          " selected" if m == (p["motivo"] or "") else "",
                          html.escape(m)) for m in permitidos)))
    campos = "".join(
        "<label>%s<input type='text' name='%s' value='%s' maxlength='%d'></label>"
        % (html.escape(rotulo), nome,
           html.escape(p[nome] or "", quote=True), tecto)
        for nome, rotulo, tecto in CAMPOS_EDITAVEIS_DA_PROPOSTA)
    corpo = (
        "<div class='cx'><form method='post' action='/proposta/%d/gravar' "
        "class='form-largo'>"
        "<label>Estado<select name='estado'>%s</select></label>%s%s"
        "<label>Responsável<input type='text' name='responsavel' value='%s' "
        "list='pessoas'></label>"
        "<button type='submit'>gravar</button></form></div>"
        "<p class='nota'>Sem anúncio do DR: %s. Criada a %s.%s</p>"
        % (id_, escada, motivo_html, campos,
           html.escape(p["responsavel"] or "", quote=True),
           html.escape(p["porque_sem_ref"] or "não vem do DR"),
           html.escape(p["criada_em"] or "?"),
           " Fechada a %s." % html.escape(p["fechada_em"])
           if p["fechada_em"] else ""))
    nome = p["titulo"] or p["entidade"] or "proposta %d" % id_
    return envolver("anuncios", corta(nome, 80),
                    html.escape(p["entidade"] or ""),
                    "<div class='larg'>" + corpo + "</div>",
                    migalhas=migalhas_de("anuncios", corta(nome, 40)),
                    titulo_aba=corta(nome, 60))


@app.route("/proposta/<int:id_>/gravar", methods=["POST"])
def proposta_gravar(id_):
    """Grava a ficha de uma proposta sem anuncio. Cada campo so muda se
    vier no formulario, e so o que mudou vai para o historico."""
    p = proposta(id_)
    if not p:
        return pagina_de_erro(404)
    if "estado" in request.form:
        ok, recado = mover_proposta(id_, (request.form.get("estado") or "").strip())
        if not ok:
            return redirect("/proposta/%d?" % id_ + urlencode({"aviso": recado}))
    if "motivo" in request.form:
        motivo = (request.form.get("motivo") or "").strip()
        permitidos = MOTIVOS_DO_ESTADO.get(
            (request.form.get("estado") or p["estado"]).strip()) or ()
        if motivo and motivo not in permitidos:
            return redirect("/proposta/%d?" % id_ + urlencode(
                {"aviso": "Esse motivo não existe para este estado."}))
        gravar_motivo(id_, motivo)
    campos, valores = [], []
    for nome, _, tecto in CAMPOS_EDITAVEIS_DA_PROPOSTA:
        if nome in request.form:
            campos.append(nome)
            valores.append(" ".join((request.form.get(nome) or "").split())[:tecto]
                           or None)
    if "responsavel" in request.form:
        campos.append("responsavel")
        valores.append(criar_pessoa(request.form.get("responsavel")))
    if campos:
        gravar_campos_da_proposta(id_, campos, valores)
    return redirect("/proposta/%d?" % id_ + urlencode({"aviso": "Guardado."}))


# ----------------------------------------------------------- calendario

DIAS_CALENDARIO = 45


def _linhas_do_calendario(estado):
    """(linhas, o que se esta a ver) da grade, para a ranhura pedida.

    "Calendário para tudo" (palavra dele a 15/09/2026): a grade deixa de
    ser só dos interessados. Sem `?estado=`, mostra o que a casa tem em
    aberto -- as quatro ranhuras que ainda se mexem --, que e a pergunta
    que um calendario responde. Com `?estado=porver` mostra a entrada, e
    os por ver com prazo a chegar sao a fila que custa dinheiro: era o
    que nenhum ecra mostrava.

    Cada linha e um dicionario com o que a grade desenha, venha de uma
    proposta ou de um anuncio -- assim a grade tem um so caminho, e nao
    dois quase iguais que divergem ao primeiro conserto.
    """
    with liga() as c:
        if estado in CHAVES_DA_CASA or not estado:
            alvo = [estado] if estado else list(ESTADOS_ABERTOS)
            propostas = c.execute(
                "SELECT * FROM propostas WHERE estado IN (%s) AND ref IS NOT NULL"
                % ",".join("?" * len(alvo)), alvo).fetchall()
            prazos = _prazos_das_propostas(c, propostas)
            linhas = [{"ref": p["ref"], "titulo": p["titulo"],
                       "entidade": p["entidade"],
                       "prazo": prazos.get(p["ref"]) or "",
                       "rotulo": estado_da_casa(p["estado"]),
                       # o quadro saiu a 15/09/2026: a volta e para a
                       # ranhura em que a proposta esta, que e onde o
                       # calendario a foi buscar
                       "alvo": "/?estado=" + p["estado"],
                       "volta": "na lista"}
                      for p in propostas]
            o_que = (("as propostas em «%s»" % estado_da_casa(estado))
                     if estado else "o que a casa tem em aberto")
        else:
            frag, vals = condicao_da_aba(estado)
            onde, valores = com_recorte("", [], frag, vals)
            anuncios = c.execute(
                "SELECT ref, titulo, entidade, prazo FROM anuncios" + onde
                + (" AND" if onde else " WHERE") + " prazo != ''",
                valores).fetchall()
            linhas = [{"ref": a["ref"], "titulo": a["titulo"],
                       "entidade": a["entidade"], "prazo": a["prazo"],
                       "rotulo": "prazo", "alvo": "/?estado=" + estado,
                       "volta": "na lista"}
                      for a in anuncios]
            o_que = "os anúncios em «%s»" % (ROTULOS_DA_ESCADA.get(estado)
                                             or "todos")
    linhas = [l for l in linhas if l["prazo"]]
    linhas.sort(key=lambda l: l["prazo"])
    return linhas, o_que


@app.route("/calendario")
def calendario():
    hoje = datetime.now().date()
    urgente = dias_urgente()  # uma leitura por pedido, nao uma por linha
    estado = request.args.get("estado")
    estado = "" if estado is None else ABAS_ANTIGAS.get(estado.strip(),
                                                        estado.strip())
    cartas, o_que = _linhas_do_calendario(estado)

    migalhas = migalhas_de("calendario")
    envolve = lambda corpo: envolver(
        "calendario", "Calendário",
        "Prazos de %s, %d dias a partir de hoje."
        % (o_que, DIAS_CALENDARIO), corpo, migalhas=migalhas,
        titulo_aba="Calendário, Em curso")

    if not cartas:
        return envolve("<div class='vazio'>Nada com prazo em %s. "
                       "<a href='/'>ver a lista</a>.</div>" % html.escape(o_que))

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
                 "<div class='cel-titulo'>Concurso &middot; %d dias a partir de hoje</div>"
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
        fundo, frente = cores.get(classe, ("var(--azul-fundo)", "var(--azul)"))
        celulas = []
        for i in range(DIAS_CALENDARIO):
            classes = classes_do_dia(i, hoje + timedelta(days=i))
            if i == posicao:
                celulas.append("<div class='%s cel-pilula'>"
                               "<a class='pilula' style='background:%s;color:%s' "
                               "href='/anuncio/%s' title='%s'>%s</a></div>"
                               % (classes, fundo, frente,
                                  quote(a["ref"], safe=""),
                                  html.escape(a["prazo"], quote=True),
                                  html.escape(a["rotulo"])))
            else:
                celulas.append("<div class='%s'></div>" % classes)
        # A ancora e a ligacao de volta: quadro <-> calendario sao duas
        # vistas do mesmo conjunto, e cada linha aponta para o SEU cartao
        # (§5 do ESQUELETO). A ligacao vai em linha propria: no .ent, o
        # nowrap+ellipsis da entidade comia-a nos nomes longos.
        ref_ancora = a["ref"].replace("/", "-")
        linhas.append("<div class='linha-grade' id='c-%s' style='%s'>"
                      "<div class='cel-titulo'><a href='/anuncio/%s'>%s</a>"
                      "<div class='ent'>%s</div>"
                      "<div class='ent'><a href='%s'>%s</a></div></div>%s</div>"
                      % (ref_ancora, grelha, quote(a["ref"], safe=""),
                         html.escape(corta(a["titulo"] or a["ref"], 70)),
                         html.escape(a["entidade"] or ""),
                         html.escape(a["alvo"], quote=True),
                         html.escape(a["volta"]), "".join(celulas)))

    nota = ("<div class='nota' style='margin-top:14px'>%d com prazo fora da "
            "janela de %d dias, que não aparecem na grade &mdash; continuam "
            "na lista.</div>"
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
    de_, ate = janela_urgente(hoje)
    with liga() as c:
        # Uma passagem pela tabela, com um SUM por barra (eram nove
        # COUNT separados). As quatro barras do funil na MESMA janela
        # de 30 dias: estavam misturadas, "Entrados (30 dias) 2 476"
        # seguido de "Por ver 66 007" de sempre, o que num funil e
        # impossivel. As alteracoes (republicacoes) nao sao triagem de
        # ninguem: sem as tirar, 763 delas contavam como "triadas". E
        # os urgentes por ver sao a fila que custa dinheiro, que nenhum
        # ecra mostrava.
        d = dict(c.execute(
            "SELECT COUNT(*) total, "
            " SUM(data_pub >= :d) entrados, "
            " SUM(data_pub >= :d AND estado = 'novo') porver_30, "
            " SUM(data_pub >= :d AND estado NOT IN ('novo','alteracao')) triados_30, "
            " SUM(data_pub >= :d AND estado = 'interessa') interessa_30, "
            " SUM(estado NOT IN ('novo','alteracao')) triados, "
            " SUM(estado = 'interessa') interessa, "
            " SUM(estado = 'descartado') descartados, "
            " SUM(estado = 'novo' AND prazo >= :de AND prazo <= :ate) urgentes_por_ver "
            "FROM anuncios", {"d": desde, "de": de_, "ate": ate}).fetchone())
        # (numa base vazia o SUM da NULL; as barras querem 0)
        d = {k: v or 0 for k, v in d.items()}
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
                            pecas_dr=None, painel=None):
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
                          ("Último erro a renovar as peças do DR",
                           pecas_dr),
                          ("Último erro do painel", painel)):
        if (valor or "").strip():
            # numa linha so antes de cortar: um erro de varias linhas
            # gastava metade dos 80 caracteres em mudancas de linha e
            # indentacao que o HTML nem mostra
            limpo = re.sub(r"\s+", " ", valor).strip()
            linhas.append((rotulo, html.escape(corta(limpo, 80)), False))
    return linhas


# --- os indicadores comerciais (etapa 5, 15/09/2026)
#
# Os indicadores mediam o funil da TRIAGEM: quanto entra, quanto se
# olha, quanto vinga (`funil_anuncios()`). O que faltava era o do
# NEGOCIO -- quanto esta em jogo, quanto se ganha, e porque se perde.
#
# Tudo o que esta aqui sai das `propostas`, e nada disto adivinha:
# quando o numero nao se pode fazer, a funcao diz None e o ecra diz
# porque. Uma taxa de vitoria calculada sobre tres concursos e um
# numero com ar de certo -- ha um minimo declarado (MINIMO_PARA_TAXA).


# Abaixo disto uma taxa nao se mostra. Com dois concursos fechados uma
# "taxa de vitoria de 50%" e ruido com ar de facto, e as decisoes que se
# tomam com ela custam dinheiro.
MINIMO_PARA_TAXA = 5


def _euros(linhas, coluna):
    return sum(v for v in (euros_do_texto(l[coluna]) for l in linhas) if v)


def pipeline_em_euros():
    """Quanto está em jogo, por ranhura aberta, e o total.

    O número de cada ranhura é o mesmo que a soma da coluna do quadro
    fazia: o preço base até ao Submetido, o proposto daí para a frente.
    Um pipeline somado a preços base é o tecto das entidades e não o que
    está em jogo, com o mesmo ar de número certo.
    """
    fora = {}
    with liga() as c:
        for estado in ESTADOS_ABERTOS:
            linhas = c.execute("SELECT * FROM propostas WHERE estado=?",
                               (estado,)).fetchall()
            coluna = ("valor_proposta" if estado in ESTADOS_COM_PROPOSTO
                      else "preco_base")
            soma = _euros(linhas, coluna)
            # sem proposto lido, o base serve de aproximação -- e diz-se
            if estado in ESTADOS_COM_PROPOSTO:
                faltam = [l for l in linhas if not l["valor_proposta"]]
                soma += _euros(faltam, "preco_base")
            else:
                faltam = [l for l in linhas if not l["preco_base"]]
            fora[estado] = {"quantas": len(linhas), "euros": soma,
                            "sem_preco": len(faltam)}
    return fora


def taxa_de_vitoria(por=None, minimo=MINIMO_PARA_TAXA):
    """Quantos se ganham dos que se decidiram, ao todo ou por dimensão.

    O denominador são os **decididos** -- ganhos mais perdidos -- e não
    tudo o que fechou: um «Não fomos» é uma decisão nossa de não
    concorrer, e metê-lo no denominador faz a taxa cair por se ter sido
    selectivo, que é o contrário do que ela devia dizer. O «Cancelado»
    idem: não foi decidido por ninguém.

    `por` é o nome de uma coluna da proposta (`tipologia`, `coe`,
    `responsavel`) ou "entidade". Devolve uma lista de
    (nome, ganhos, decididos, taxa ou None) ordenada pelos decididos --
    e a taxa é None abaixo do mínimo, que é como se diz «ainda não sei»
    em vez de inventar.
    """
    coluna = por if por in ("tipologia", "coe", "responsavel", "entidade") else None
    with liga() as c:
        if coluna:
            linhas = c.execute(
                "SELECT COALESCE(NULLIF(%s,''),'(sem)') k,"
                " SUM(estado='ganho') g, COUNT(*) n FROM propostas "
                "WHERE estado IN ('ganho','perdido') GROUP BY k "
                "ORDER BY n DESC" % coluna).fetchall()
        else:
            linhas = c.execute(
                "SELECT 'total' k, SUM(estado='ganho') g, COUNT(*) n "
                "FROM propostas WHERE estado IN ('ganho','perdido')").fetchall()
    fora = []
    for l in linhas:
        if not l["n"]:
            continue
        taxa = (1.0 * l["g"] / l["n"]) if l["n"] >= minimo else None
        fora.append((l["k"], l["g"], l["n"], taxa))
    return fora


def nomes_das_divisoes(divisoes):
    """{«72»: «Serviços de TI»} para as divisões pedidas (as duas
    primeiras casas do CPV).

    A tabela `cpv_dict` guarda o código a oito casas, e a divisão é o
    código com seis zeros atrás -- «72» é «72000000». Uma divisão que a
    tabela não conheça sai de fora, e quem chama decide o que escrever
    no lugar dela.
    """
    divisoes = [d for d in dict.fromkeys(divisoes) if d]
    if not divisoes:
        return {}
    with liga() as c:
        return {r["codigo8"][:2]: r["descricao"] for r in c.execute(
            "SELECT codigo8, descricao FROM cpv_dict WHERE codigo8 IN (%s)"
            % ",".join("?" * len(divisoes)),
            [d + "000000" for d in divisoes])}


def taxa_por_divisao_cpv(minimo=MINIMO_PARA_TAXA):
    """A taxa de vitória por divisão de CPV -- as duas primeiras casas,
    que é a área do negócio. O CPV está no ANÚNCIO e não na proposta, e
    por isso isto junta as duas tabelas; uma proposta sem anúncio (D2)
    não tem CPV e fica de fora, que é diferente de contar como zero."""
    with liga() as c:
        linhas = c.execute(
            "SELECT substr(a.cpv,1,2) d, SUM(p.estado='ganho') g, COUNT(*) n "
            "FROM propostas p JOIN anuncios a ON a.ref = p.ref "
            "WHERE p.estado IN ('ganho','perdido') AND a.cpv != '' "
            "GROUP BY d ORDER BY n DESC LIMIT 10").fetchall()
    return [(l["d"], l["g"], l["n"],
             (1.0 * l["g"] / l["n"]) if l["n"] >= minimo else None)
            for l in linhas]


def porque_se_perde():
    """Os motivos de perda agregados. São vocabulário fechado
    (MOTIVOS_PERDA), e é por isso que dão contas -- texto livre daria,
    ao fim de um mês, cinquenta maneiras de escrever «preço» e nenhuma
    soma."""
    with liga() as c:
        return c.execute(
            "SELECT COALESCE(NULLIF(motivo,''),'(por dizer)') m, COUNT(*) n "
            "FROM propostas WHERE estado='perdido' GROUP BY m "
            "ORDER BY n DESC").fetchall()


def porque_nao_se_vai():
    """O mesmo para o «Não fomos» (MOTIVOS_ABANDONO). Vale tanto como o
    outro e diz outra coisa: onde é que a casa não chega -- falta de
    certificações, falta de CV's -- é o que se pode ir corrigir."""
    with liga() as c:
        return c.execute(
            "SELECT COALESCE(NULLIF(motivo,''),'(por dizer)') m, COUNT(*) n "
            "FROM propostas WHERE estado='nao_fomos' GROUP BY m "
            "ORDER BY n DESC").fetchall()


def dias_parados(limite=10):
    """As propostas abertas que há mais tempo não se mexem.

    Mede-se pela última linha do histórico daquele `ref`, e não pela
    criação: uma proposta que se mexeu ontem não está parada, por muito
    antiga que seja. Sem histórico nenhum vale a data de criação.
    """
    hoje = datetime.now().date()
    with liga() as c:
        linhas = c.execute(
            "SELECT p.*, (SELECT MAX(h.quando) FROM historico h "
            "  WHERE h.ref = p.ref) AS mexeu "
            "FROM propostas p WHERE p.estado IN (%s)"
            % ",".join("?" * len(ESTADOS_ABERTOS)),
            list(ESTADOS_ABERTOS)).fetchall()
    fora = []
    for p in linhas:
        quando = (p["mexeu"] or p["criada_em"] or "")[:10]
        try:
            dias = (hoje - datetime.strptime(quando, "%Y-%m-%d").date()).days
        except ValueError:
            continue
        fora.append((p, dias))
    fora.sort(key=lambda x: -x[1])
    return fora[:limite]


def desconto_medio_dos_ganhos():
    """(desconto médio 0..1, sobre quantos) nos concursos ganhos.

    Quanto abaixo do preço base é que se ganha -- o número que diz se a
    casa está a deixar dinheiro em cima da mesa ou a comprar trabalho.
    Só conta quem tem os dois preços lidos, e diz sobre quantos: somar
    uns e calar os outros parecia a média de todos.
    """
    with liga() as c:
        linhas = c.execute(
            "SELECT preco_base, valor_proposta FROM propostas "
            "WHERE estado='ganho'").fetchall()
    descontos = []
    for l in linhas:
        base = euros_do_texto(l["preco_base"])
        nosso = euros_do_texto(l["valor_proposta"])
        if base and nosso and nosso <= base:
            descontos.append((base - nosso) / base)
    if not descontos:
        return None, 0
    return sum(descontos) / len(descontos), len(descontos)


def negocio_cx():
    """O bloco dos indicadores COMERCIAIS (etapa 5, 15/09/2026).

    Os indicadores mediam o funil da triagem -- quanto entra, quanto se
    olha, quanto vinga. Faltava o do negócio: quanto está em jogo,
    quanto se ganha, e porque se perde.

    **Cada número abre a lista que o confirma**, que é a regra da casa.
    E o que não se pode saber diz-se: uma taxa sobre três concursos é
    ruído com ar de facto, e as decisões que se tomam com ela custam
    dinheiro.
    """
    pipeline = pipeline_em_euros()
    em_jogo = sum(v["euros"] for v in pipeline.values())
    abertas = sum(v["quantas"] for v in pipeline.values())
    sem_preco = sum(v["sem_preco"] for v in pipeline.values())
    totais = taxa_de_vitoria()
    ganhos, decididos, taxa = (totais[0][1], totais[0][2], totais[0][3]) \
        if totais else (0, 0, None)
    desconto, sobre = desconto_medio_dos_ganhos()

    def numero(rotulo, valor, nota):
        """Um número do cabeçalho -- ou, quando ainda não há que contar,
        a frase que o diz.

        **Sem número não se põe um travessão** (arranjo pedido por ele a
        15/09/2026): com a base quase vazia o bloco ficava a ser três
        travessões seguidos com legendas compridas por baixo, o que dá ar
        de avariado em vez de «ainda não». A frase ocupa o lugar do
        número, mais pequena, e diz o que falta para ele existir.
        """
        if valor is None:
            return ("<div class='por-haver'><b>%s</b><span>%s</span></div>"
                    % (nota, rotulo))
        return ("<div><b>%s</b><span>%s</span><span class='sub'>%s</span></div>"
                % (valor, rotulo, nota))

    cabeca = "".join((
        numero("em jogo",
               euros_curto(em_jogo) if em_jogo else None,
               ("%d proposta%s aberta%s%s"
                % (abertas, "" if abertas == 1 else "s",
                   "" if abertas == 1 else "s",
                   "; %d sem preço lido" % sem_preco if sem_preco else ""))
               if em_jogo else
               ("as %d abertas ainda não têm preço lido" % abertas
                if abertas else "ainda não há propostas abertas")),
        numero("taxa de vitória",
               "%.0f%%" % (taxa * 100) if taxa is not None else None,
               ("%d de %d decididos" % (ganhos, decididos)) if taxa is not None
               else ("%d decidido%s: faltam %d para contar"
                     % (decididos, "" if decididos == 1 else "s",
                        MINIMO_PARA_TAXA - decididos)) if decididos
               else "ainda não há decididos"),
        numero("desconto médio",
               "%.1f%%" % (desconto * 100) if desconto is not None else None,
               "nos %d ganhos com os dois preços lidos" % sobre if sobre
               else "ainda não há ganhos com os dois preços lidos")))

    # o pipeline por ranhura, cada barra a abrir a sua lista
    maior = max([v["euros"] for v in pipeline.values()] + [1.0])
    barras = "".join(
        "<div class='col'><span class='v'>%s</span>"
        "<a class='b' href='/?estado=%s' style='height:%d%%' "
        "title='%d proposta(s)'></a><span class='l'>%s</span></div>"
        % (euros_curto(pipeline[ch]["euros"]) if pipeline[ch]["euros"] else "0",
           ch, int(88.0 * pipeline[ch]["euros"] / maior) + 6,
           pipeline[ch]["quantas"], html.escape(estado_da_casa(ch)))
        for ch in ESTADOS_ABERTOS)

    def tabela(titulo, linhas, vazio):
        if not linhas:
            return ("<div class='rot' style='margin:22px 0 6px'>%s</div>"
                    "<div class='nota'>%s</div>" % (titulo, vazio))
        maior_n = max(l["n"] for l in linhas)
        return ("<div class='rot' style='margin:22px 0 10px'>%s</div>"
                "<div class='barras-h'>%s</div>"
                % (titulo, "".join(
                    "<div class='lh'><span class='t'>%s</span>"
                    "<span class='bh' style='width:%d%%'></span>"
                    "<span class='n'>%d</span></div>"
                    % (html.escape(l["m"]), int(100.0 * l["n"] / maior_n), l["n"])
                    for l in linhas)))

    # As propostas que o Estado já fechou e nós não (etapa 4). É a
    # pergunta mais accionável deste bloco -- cada uma é um clique para
    # arrumar -- e por isso vem no topo e não no fim.
    por_fechar = propostas_por_fechar(limite=6)
    aviso_fechar = ""
    if por_fechar:
        aviso_fechar = (
            "<div class='flash' style='margin:0 0 18px'>"
            "<b>%d proposta%s</b> ainda em aberto cujo procedimento o "
            "Portal BASE já diz adjudicado. Abre cada uma e fecha-a: o "
            "facto está lá, a decisão é tua.<div class='por-fechar'>%s</div>"
            "</div>"
            % (len(por_fechar), "" if len(por_fechar) == 1 else "s",
               "".join("<a href='/anuncio/%s'>%s</a>"
                       % (quote(p["ref"], safe=""),
                          html.escape(corta(p["titulo"] or p["ref"], 52)))
                       for p, _ in por_fechar)))

    # A taxa por área de CPV: onde é que a casa ganha e onde é que
    # insiste sem ganhar. Só as divisões com decididos que cheguem --
    # abaixo disso a `taxa_por_divisao_cpv()` devolve None, e a linha
    # di-lo em vez de mostrar uma percentagem inventada.
    por_cpv = taxa_por_divisao_cpv()
    nomes = nomes_das_divisoes(d for d, _, _, _ in por_cpv)
    cpv_html = ""
    if por_cpv:
        cpv_html = (
            "<div class='rot' style='margin:22px 0 10px'>Onde se ganha, "
            "por área</div><div class='barras-h'>%s</div>"
            % "".join(
                "<div class='lh'><span class='t'>%s</span>"
                "<span class='bh' style='width:%d%%;background:%s'></span>"
                "<span class='n'>%s</span></div>"
                % (html.escape("%s — %s" % (d, corta(nomes.get(d, "sem descrição"), 34))),
                   int(100.0 * (taxa if taxa is not None else 0)) or 3,
                   "var(--verde)" if taxa else "var(--traco)",
                   ("%.0f%% de %d" % (taxa * 100, n)) if taxa is not None
                   else "%d de %d, poucos" % (g, n))
                for d, g, n, taxa in por_cpv))

    parados = dias_parados(5)
    lista_parados = "".join(
        "<div class='l'><span class='t'><a href='%s'>%s</a></span>"
        "<span class='v'>%d dias</span></div>"
        % ("/anuncio/" + quote(p["ref"], safe="") if p["ref"]
           else "/proposta/%d" % p["id"],
           html.escape(corta(p["titulo"] or p["entidade"] or "?", 48)), dias)
        for p, dias in parados) or "<div class='nota'>nada parado</div>"

    return ("<div class='cx' style='padding:22px 24px'>"
            "<div class='rot' style='margin-bottom:6px'>O negócio</div>"
            "<div class='nota' style='margin-bottom:18px'>O que está em "
            "jogo, o que se ganha e porque se perde. Uma taxa só aparece "
            "com %d decididos ou mais.</div>"
            "%s<div class='desfecho-som'>%s</div>"
            "<div class='rot' style='margin:22px 0 10px'>Em jogo, por "
            "ranhura</div><div class='barras'>%s</div>"
            "%s%s%s"
            "<div class='rot' style='margin:22px 0 6px'>Há mais tempo sem "
            "se mexerem</div><div class='saude'>%s</div>"
            "</div>"
            % (MINIMO_PARA_TAXA, aviso_fechar, cabeca, barras,
               tabela("Porque se perde", porque_se_perde(),
                      "ainda não há perdidos"),
               tabela("Porque não se vai", porque_nao_se_vai(),
                      "ainda não há «não fomos»"), cpv_html,
               lista_parados))


@app.route("/indicadores")
def indicadores_antigo():
    """Passou a Configuracoes > Indicadores (13/09/2026); redirecciona."""
    return redirect("/configuracoes/indicadores")


def linha_da_ultima_verificacao():
    """(rotulo, valor, bom) da ultima verificacao, para a saude dos
    Indicadores. Vivia na barra lateral ate 13/09/2026."""
    mensagem = le_marca("ultima_mensagem", "ainda não verificou")
    quando = le_marca("ultima_verificacao", "nunca")
    bom = le_marca("ultima_ok", "") != "0"
    a_correr = verificacao_a_correr()
    if a_correr:
        return ("Última verificação", "a verificar agora &mdash; %s"
                % html.escape(a_correr), True)
    if quando == "nunca":
        return ("Última verificação", "ainda não verificou", False)
    return ("Última verificação", "%s &mdash; %s"
            % (html.escape(data_hora_pt(quando)), html.escape(mensagem)), bom)


@app.route("/configuracoes/indicadores")
def indicadores():
    """Numeros sobre a propria base. Sem servicos externos: e tudo SQL
    sobre o radar.db."""
    hoje = datetime.now().date()
    with liga() as c:
        total = c.execute("SELECT COUNT(*) n FROM anuncios").fetchone()["n"]
        hoje_n = c.execute("SELECT COUNT(*) n FROM anuncios WHERE data_pub=?",
                           (hoje.strftime("%Y-%m-%d"),)).fetchone()["n"]
        interessa = c.execute("SELECT COUNT(*) n FROM propostas").fetchone()["n"]
        # A MESMA janela do filtro prazo=urgente (janela_urgente): havia
        # aqui um 7 escrito a mao com o filtro a 10, e o numero do cartao
        # nao abria lista nenhuma que o confirmasse.
        urgentes = c.execute(
            "SELECT COUNT(*) n FROM anuncios a WHERE a.prazo >= ? "
            "AND a.prazo <= ? AND EXISTS (SELECT 1 FROM propostas p "
            "WHERE p.ref = a.ref AND p.estado IN (%s))"
            % ",".join("?" * len(ESTADOS_ABERTOS)),
            list(janela_urgente(hoje)) + list(ESTADOS_ABERTOS)).fetchone()["n"]
        porler = c.execute("SELECT COUNT(*) n FROM anuncios "
                           "WHERE detalhe_lido=0").fetchone()["n"]
        por_estado = {ch: 0 for ch in CHAVES_DA_CASA}
        for r in c.execute("SELECT estado, COUNT(*) n FROM propostas "
                           "GROUP BY estado"):
            if r["estado"] in por_estado:
                por_estado[r["estado"]] = r["n"]
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

    maior = max(list(por_estado.values()) + [1])
    # As ranhuras sao um caminho, como o funil: uma cor so, a escurecer
    # do principio para o fim. Eram cinco cores sem sistema (bege, azul,
    # laranja, preto, verde) e duas delas vinham das cores de estado --
    # a coluna "Submetido" a laranja parecia um aviso e nao e.
    cores_barra = ("#c3ced9", "#9db1c4", "#7994ae", "#5c809f", "#17557f")
    # Cada barra abre a lista que a confirma: a regra da casa e que um
    # numero que um ecra mostra tem de dar exactamente a lista que a
    # ligacao dele abre, e ate 15/09/2026 estas nao abriam nada.
    barras = "".join(
        "<div class='col'><span class='v'>%d</span>"
        "<a class='b' href='/?estado=%s' style='height:%d%%;background:%s'"
        " title='ver as %d'></a>"
        "<span class='l'>%s</span></div>"
        % (por_estado[ch], ch,
           int(88.0 * por_estado[ch] / maior) + 6,
           cores_barra[i % len(cores_barra)], por_estado[ch],
           html.escape(rotulo))
        for i, (ch, rotulo) in enumerate(ESTADOS_DA_CASA))

    tem_dr = "válido" if carregar_curl() else "em falta"
    tem_det = "válido" if carregar_curl("curl_detalhe") else "em falta"
    saude = [("Verificação automática",
              " &middot; ".join(ler_config()["horas_verificacao"]), True),
             linha_da_ultima_verificacao(),
             ("Captura curl_DR.txt", tem_dr, tem_dr == "válido"),
             ("Captura curl_detalhe.txt", tem_det, tem_det == "válido")]
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
    # 15/09/2026: o ensaio de restauro (--ensaiar-copia); so aparece
    # depois de correr uma vez. O 500 do painel esta nos ultimos erros.
    ensaio = le_marca("ultimo_ensaio_copia", "")
    if ensaio:
        saude.append(("Ensaio de restauro", html.escape(corta(ensaio, 80)),
                      ensaio.startswith("ok")))

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
                                    le_marca("painel_ultimo_erro", ""))
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
        nomes_div = nomes_das_divisoes(r["div"] for r in f["por_divisao"])
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
        # o bloco do negocio como ARGUMENTO e nao concatenado: o `%` de
        # baixo aplica-se a ultima string da cadeia, e um `+` a meio
        # partia a formatacao de tudo o que vem depois
        "%s"
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
        "</div></div>" % (kpis_html, negocio_cx(), funil_cx, barras, saude_html,
                          corpus_html))

    return pagina_config("indicadores", conteudo)


# --- a lista do "Em curso" fundiu-se na lista unica (15/09/2026)
#
# Nasceu a 14/09/2026 com as colunas que o Afonso mandou -- titulo,
# cliente, preco, esclarecimentos, entrega, tipologia, estado, CV,
# proposta tecnica, notas, plataforma, CoE, responsavel -- e durou um
# dia. Com a escada, os mesmos interessados numa tabela e exactamente a
# lista das ranhuras da casa (`_lista_de_propostas()`), e um separador
# proprio era a mesma pagina com outro nome. As colunas que a casa
# decide passaram todas para a `propostas`.
#
# A rota fica: as ligacoes antigas e o marcador do browser dele nao se
# partem por uma arrumacao nossa.

def resposta_csv(saida, prefixo):
    """O CSV como transferencia, com o BOM que faz o Excel ler UTF-8."""
    return Response("﻿" + saida.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition":
                             "attachment; filename=" + nome_csv(prefixo)})


@app.route("/lista")
def lista_em_curso():
    """Redirecciona para a escada. A lista das propostas e a mesma coisa
    que esta era, e com o lote e as que nao vem do DR por cima."""
    return redirect("/?estado=analisar")


@app.route("/lista/<path:ref>", methods=["POST"])
def lista_gravar(ref):
    """Os campos que esta rota gravava vivem agora na proposta. Manda
    para a ficha do anuncio, que e onde se editam."""
    return redirect("/anuncio/" + quote(ref, safe=""))


@app.route("/proposta/<int:id_>/apagar", methods=["POST"])
def proposta_apagar(id_):
    """Apaga uma proposta SEM anuncio. As que vieram do DR tiram-se da
    escada com o "voltar a por ver", que as devolve a lista; uma consulta
    previa nao tem lista nenhuma para onde voltar, e por isso o unico
    gesto possivel e apagar."""
    p = proposta(id_)
    if not p:
        return volta_ao_referer("/quadro")
    if p["ref"]:
        return _volta_com_aviso(
            "Esta proposta veio do DR: tira-se da escada com «voltar a "
            "por ver», e o anúncio volta à lista.")
    with liga() as c:
        c.execute("DELETE FROM propostas WHERE id=?", (id_,))
    registar("", "proposta apagada", p["titulo"] or p["entidade"] or str(id_))
    return redirect("/?" + urlencode({"estado": p["estado"],
                                      "aviso": "Proposta apagada."}))


# --------------------------------- a amostra do desenho (docs/design.md)
#
# Uma pagina que mostra os componentes todos num sitio, para ele ver e
# decidir antes de um ecra mudar (pedido dele a 16/09/2026, ponto 2).
# Nao passa pelo BASE de proposito: e a unica pagina que carimba
# `data-pele` e `data-tipo` no <html>, e e isso que lhe deixa desenhar a
# direccao inteira sem mexer no resto da aplicacao.

# As fontes sao servidas daqui e de mais lado nenhum: a regra da casa e
# que o painel nao pede nada a nenhum dominio de fora, e o CSP diz
# `font-src 'self'`. Lista branca de nomes -- nao ha caminho nenhum a
# juntar a mao, e por isso nao ha travessia possivel.
TIPOS = {"inter.woff2", "plex-sans.woff2",
         "plex-mono-400.woff2", "plex-mono-600.woff2"}


@app.route("/tipo/<nome>")
def tipo(nome):
    if nome not in TIPOS:
        abort(404)
    caminho = os.path.join(BASE_DIR, "tipo", nome)
    if not os.path.exists(caminho):
        abort(404)
    resposta = send_file(caminho, mimetype="font/woff2")
    # uma fonte com a licenca OFL nao muda; o browser nao tem de a voltar
    # a pedir a cada pagina
    resposta.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resposta


# (chave, rotulo, o que se ganha, o que se perde) -- o selector de letra.
LETTERINGS = (
    ("plex", "IBM Plex Sans + Plex Mono",
     "a escolhida: institucional, uma família só para texto e números, e a "
     "mais estreita das três (5,4% menos que a Inter, na mesma frase a 13px)",
     "altura-de-x 52 contra 54 da Inter: lê-se 3,8% mais pequena ao mesmo "
     "tamanho, e é por isso que a escala sobe meio pixel"),
    ("inter", "Inter + Plex Mono",
     "desenhada para interface a 11–14px; algarismos tabulares; variável",
     "é comum, não tem voz própria, e é a mais larga das três"),
    ("sistema", "Sistema (o de hoje)",
     "não pede ficheiro nenhum",
     "muda de computador para computador"),
)

AMOSTRA_PAGINA = """<!doctype html>
<html lang="pt" data-pele="%(pele)s" data-tipo="%(tipo)s">
<head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Amostra do desenho</title>
<style>%(css)s</style><style>%(css_novo)s</style>
<style>
/* O selector fica preso e o `.topo` nao: sao dois irmaos ambos em
   `position:sticky;top:0`, e o segundo tapava o primeiro assim que se
   rolava -- numa pagina que existe para comparar, o comparador tem de
   estar sempre a mao. So aqui: o `.topo` das outras paginas nao muda. */
.am-topo{display:flex;align-items:center;gap:18px;flex-wrap:wrap;
 padding:12px 34px;background:var(--creme);border-bottom:1px solid var(--linha);
 position:sticky;top:44px;z-index:12}
.topo{position:static}
.am-topo .g{display:flex;align-items:center;gap:7px}
.am-topo label{font:600 11.5px/1 var(--sans);color:var(--t4)}
.am-topo a{padding:6px 10px;border-radius:6px;border:1px solid var(--linha);
 font:600 12px/1 var(--sans);color:var(--t3);background:var(--creme)}
.am-topo a.on{background:var(--ink);border-color:var(--ink);color:#fff}
.am-sec{margin:0 0 30px}
.am-sec > h2{font:650 15px/1.3 var(--sans);color:var(--ink);margin:0 0 4px}
.am-sec > p{font:400 12.5px/1.5 var(--sans);color:var(--t4);margin:0 0 12px;
 max-width:760px}
.am-cx{background:var(--creme);border:1px solid var(--linha);border-radius:9px;
 padding:18px}
.am-fila{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.am-grelha{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));
 gap:12px}
.am-bt{display:flex;flex-direction:column;gap:5px}
.am-bt small{font:400 11px/1.4 var(--sans);color:var(--t4)}
.am-cor{display:flex;align-items:center;gap:9px;font:500 11.5px/1.3 var(--sans);
 color:var(--t3)}
.am-cor i{width:26px;height:26px;border-radius:6px;flex:none;
 border:1px solid rgba(0,0,0,.08)}
.am-cor code{font:500 11px/1 var(--mono);color:var(--t4)}
.am-prova{font:400 20px/1.5 var(--sans);color:var(--t1);margin:0 0 10px;
 text-wrap:pretty}
.am-num{font:500 15px/1.6 var(--mono);color:var(--t2)}
.am-esc div{margin:0 0 7px;color:var(--t1)}
.am-esc span{font:500 10.5px/1 var(--mono);color:var(--t5);margin-left:10px}
</style></head><body>
<div class="app">
<header class="barra">
 <div class="marca"><a class="logo" href="/">Radar<span>Gov</span></a></div>
 <nav><a class="on"><b>Concursos</b></a><a><b>Mercado</b></a></nav>
 <div class="caixa"><a class="conf">Configurações</a></div>
</header>
<main>
 <div class="am-topo">
  <div class="g"><label>Letra</label>%(sel_tipo)s</div>
  <div class="g"><label>Pele</label>%(sel_pele)s</div>
  <div class="g" style="margin-left:auto"><a href="/">voltar ao painel</a></div>
 </div>
 <div class="topo">
  <div class="migalhas"><div class="b"><em>Amostra</em></div>
   <div class="accoes-topo"><button class="bt forte">Acção principal</button></div>
  </div>
  <h1 class="tit">Amostra do desenho</h1>
  <p class="subtit">Os componentes todos num sítio, para decidir antes de
   um ecrã mudar. O caminho está escrito em <code>docs/design.md</code>.</p>
 </div>
 <div class="corpo"><div class="larg">%(corpo)s</div></div>
</main>
</div>
<script>
// cada degrau diz o tamanho que o CSS lhe deu, e nao o que alguem
// escreveu ao lado -- a escala muda e a legenda acompanha sozinha
var raiz = getComputedStyle(document.documentElement);
document.querySelectorAll('[data-degrau]').forEach(function (b) {
  b.textContent = raiz.getPropertyValue(b.dataset.degrau).trim()
                      .replace('.', ',') || '(a pele de hoje não tem escala)';
});
</script>
</body></html>"""


def _am_seccao(titulo, nota, corpo):
    return ("<section class='am-sec'><h2>%s</h2><p>%s</p>"
            "<div class='am-cx'>%s</div></section>" % (titulo, nota, corpo))


@app.route("/amostra")
def amostra():
    tipo_ = request.args.get("tipo", "plex")
    if tipo_ not in {ch for ch, _, _, _ in LETTERINGS}:
        tipo_ = "plex"
    pele = "novo" if request.args.get("pele", "novo") != "velho" else ""

    def botoes(nome, valores, actual):
        saida = []
        for chave, rotulo in valores:
            args = {"tipo": tipo_, "pele": "novo" if pele else "velho"}
            args[nome] = chave
            saida.append("<a class='%s' href='/amostra?%s'>%s</a>"
                         % ("on" if chave == actual else "",
                            html.escape(urlencode(args), quote=True),
                            html.escape(rotulo)))
        return "".join(saida)

    sel_tipo = botoes("tipo", [(ch, ro) for ch, ro, _, _ in LETTERINGS], tipo_)
    sel_pele = botoes("pele", [("novo", "Nova"), ("velho", "A de hoje")],
                      "novo" if pele else "velho")

    partes = []

    # --- o lettering -------------------------------------------------
    escolhido = next(l for l in LETTERINGS if l[0] == tipo_)
    partes.append(_am_seccao(
        "A letra", "Ganha: %s. Perde: %s. A frase de prova leva os "
        "diacríticos todos do português &mdash; uma cedilha em falta no "
        "subconjunto «latin» só se vê no dia em que aparece um "
        "«Direcção-Geral»." % (escolhido[2], escolhido[3]),
        "<p class='am-prova'>Aquisição de serviços de manutenção "
        "à Direcção-Geral: prevenção, câmaras, órgãos e ação. "
        "ãõçáéíóúàâêô ÃÕÇÁÉÍÓÚÀÂÊÔ</p>"
        "<p class='am-num'>23012/2026 &nbsp; 71318100 &nbsp; "
        "174.950,00 EUR &nbsp; 16/09/2026 &nbsp; 0123456789 Il1 O0</p>"
        # O tamanho de cada degrau NAO se escreve aqui: escreve-o o JS a
        # partir do que o CSS calculou. Escrito a mao, ficou a dizer
        # "13px" no minuto em que a escala subiu meio pixel para a Plex
        # -- e um numero que o ecra mostra e nao se pode comparar com o
        # que ele descreve e a mesma avaria que a regra da casa proibe
        # nas listas.
        "<div class='am-esc' style='margin-top:16px'>" + "".join(
            "<div style='font:%s var(--f%d)/1.3 var(--sans)'>%s"
            "<span>--f%d &middot; <b data-degrau='--f%d'></b></span></div>"
            % (peso, n, texto, n, n)
            for n, peso, texto in (
                (6, "680", "Título da página"),
                (5, "620", "Título de anúncio ou de bloco"),
                (4, "400", "Texto corrido e valores da ficha"),
                (3, "500", "Interface: botões, abas, linhas"),
                (2, "500", "Metadados: entidade, data, plataforma"),
                (1, "550", "Etiquetas, contadores, pílulas")))
        + "</div>"))

    # --- a cor -------------------------------------------------------
    # O segundo token de cada superficie e o nome antigo: na pele "a de
    # hoje" os tres novos nao existem, e a amostra desenhava tres
    # quadrados vazios que se leem como avaria em vez de comparacao.
    cores = (("--azul", "", "Podes fazer isto: acção, ligação, seleccionado"),
             ("--verde", "", "Correu bem, ou avança no negócio"),
             ("--laranja", "", "Atenção sem ser erro; sai do fluxo sem apagar"),
             ("--verm", "", "Perdeu-se, ou destrói"),
             ("--t1", "", "Texto principal"), ("--t3", "", "Texto secundário"),
             ("--t5", "", "O cinzento mais fraco que ainda passa AA"),
             ("--fundo", "--papel", "O fundo da página"),
             ("--sup", "--creme", "Cartões e linhas"),
             ("--sup2", "--linha2", "Encaixes: cabeçalho de tabela, campo"),
             ("--linha", "", "O fio entre dados"),
             ("--traco", "", "Decoração: setas, molduras"))
    partes.append(_am_seccao(
        "A cor", "Uma cor só entra quando quer dizer alguma coisa. Toda a "
        "escala de texto passa AA sobre todos os fundos que existem &mdash; "
        "pior caso 4,52, medido e não estimado.",
        "<div class='am-grelha'>" + "".join(
            "<div class='am-cor'><i style='background:var(%s)'></i>"
            "<div><code>%s</code><br>%s</div></div>"
            % (t + (",var(%s)" % velho if velho else ""), t, o)
            for t, velho, o in cores) + "</div>"))

    # --- os botoes ---------------------------------------------------
    bts = (("bt forte", "Filtrar", "A acção principal do bloco. Uma por bloco"),
           ("bt ok", "Interessa", "Confirma e avança no negócio"),
           ("bt", "Limpar", "Secundário: cancelar, voltar, alternativas"),
           ("bt cuidado", "Abandonar", "Sai do fluxo, mas não apaga nada"),
           ("bt perigo", "Apagar contacto", "Irreversível: destrói dados"))
    partes.append(_am_seccao(
        "Os botões", "Vê-se o que cada um faz pela cor e pelo "
        "preenchimento, antes de se ler a palavra. Os dois perigosos "
        "começam em contorno e só se enchem ao passar por cima ou ao "
        "receber o foco &mdash; um botão vermelho cheio numa lista de vinte "
        "linhas é um alvo, e convida ao clique errado. <b>Passa por cima "
        "dos dois últimos.</b>",
        "<div class='am-grelha'>" + "".join(
            "<div class='am-bt'><div><button class='%s'>%s</button></div>"
            "<small>%s</small></div>" % (c, r, o) for c, r, o in bts)
        + "</div>"))

    # --- etiquetas e pilulas -----------------------------------------
    partes.append(_am_seccao(
        "Etiquetas e prazos", "As mesmas classes da lista. A cor do prazo "
        "sai da janela única (<code>dias_urgente()</code>), e a etiqueta "
        "conta pela mesma conta que o número que a abre.",
        "<div class='am-fila'>"
        "<span class='chip-prazo ok'>31 dias</span>"
        "<span class='chip-prazo avisa'>3 dias</span>"
        "<span class='chip-prazo mau'>expirado</span>"
        "<span class='chip-prazo'>prazo 03/08/2026</span>"
        "<span class='tag'>71318100</span><span class='tag'>vortal</span>"
        "<span class='tag'>Anúncio de procedimento</span>"
        "<span class='etq'>obra</span><span class='etq'>lote 2</span>"
        "</div>"))

    # --- o selector da ranhura ---------------------------------------
    partes.append(_am_seccao(
        "O selector da ranhura", "É este o controlo que move um concurso "
        "na escada, desde que o quadro saiu. O botão «ir» só aparece a "
        "quem não tem JS.",
        "<div class='am-fila'>%s</div>"
        % selector_de_ranhura("/amostra", "preparar", "Amostra")))

    # --- a tabela ----------------------------------------------------
    linhas = (("30/11/2023", "Iluminação decorativa de Natal 2023",
               "Concurso público", "Impactplan Unipessoal, Lda", "72 750 €"),
              ("27/11/2023", "Iluminação decorativa de Natal 2023",
               "Concurso público", "CASTROS, ILUMINAÇÕES FESTIVAS, S.A.",
               "66 050 €"),
              ("25/11/2022", "Iluminação decorativa de Natal 2022",
               "Concurso público", "Impactplan Unipessoal, Lda", "64 934 €"))
    partes.append(_am_seccao(
        "A tabela", "Os números alinham por algarismo e o dinheiro alinha à "
        "direita &mdash; é a diferença entre uma coluna que se compara de "
        "relance e uma que se lê linha a linha.",
        "<table class='tab-contratos'><thead><tr><th>Celebrado</th>"
        "<th>Objecto</th><th>Procedimento</th><th>Quem ganhou</th>"
        "<th class='dir'>Preço</th></tr></thead><tbody>" + "".join(
            "<tr><td>%s</td><td>%s</td><td>%s</td>"
            "<td><a href='#'>%s</a></td><td class='dir'>%s</td></tr>" % l
            for l in linhas) + "</tbody></table>"))

    # --- formularios -------------------------------------------------
    partes.append(_am_seccao(
        "Os formulários", "Os mesmos campos da lista: objecto, entidade, "
        "plataforma e as duas datas.",
        "<div class='filtros'>"
        "<input placeholder='Nome do anúncio ou objecto…'>"
        "<input placeholder='Entidade que publica…'>"
        "<select><option>todas as plataformas (1 269)</option></select>"
        "<input type='date'><input type='date'>"
        "<button class='bt forte'>Filtrar</button>"
        "<a class='bt-leve' href='#'>limpar</a></div>"))

    # --- avisos ------------------------------------------------------
    partes.append(_am_seccao(
        "Os avisos e os estados vazios", "O aviso da vez, o do sistema, e "
        "o que um ecrã diz quando não tem nada. Um estado vazio tem sempre "
        "uma saída.",
        "<div class='flash'>«Iluminação decorativa da Quadra Natalícia» "
        "marcado como interessa<form class='accao desfazer'>"
        "<button class='mini'>desfazer</button></form></div>"
        "<div class='flash mau'>As tarefas agendadas não estão criadas: o "
        "radar só recolhe com o painel aberto.</div>"
        "<div class='nota' style='margin:12px 0'>3 contratos desta entidade "
        "neste CPV &mdash; de 3 983 ao todo.</div>"
        "<div class='vazio'>Nada corresponde a este filtro. "
        "<a href='#'>limpar</a></div>"))

    return AMOSTRA_PAGINA % {
        "pele": pele, "tipo": tipo_, "css": CSS, "css_novo": CSS_NOVO,
        "sel_tipo": sel_tipo, "sel_pele": sel_pele,
        "corpo": "".join(partes)}


# ------------------------------------------------------------- arranque

def porta_atende(porta, espera=0.5):
    """True se ja houver quem aceite ligacoes nesta porta do localhost.

    `espera` e por tentativa e curta de proposito: no Windows da pen,
    a uma porta com bind feito mas ainda sem listen -- o instante em
    que o Flask esta a arrancar -- nao vinha recusa, vinha timeout.
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
                webbrowser.open("http://%s:%d/" % (ENDERECO, porta))
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
        # Duas formas. `--historico N` sao N dias a contar de hoje, numa
        # janela so -- e o que sempre foi, e serve para recuperar dias
        # falhados. `--historico DE ATE` varre um intervalo por janelas
        # de 30 dias, gravando cada uma: e a forma de trazer anos, e a
        # razao de nao ser uma janela grande esta em recolher_intervalo().
        i = sys.argv.index("--historico")
        resto = [a for a in sys.argv[i + 1:] if not a.startswith("--")]
        datas = [a for a in resto[:2] if re.match(r"^\d{4}-\d{2}-\d{2}$", a)]
        if len(datas) == 2:
            de, ate = sorted(datas)
            passo = PASSO_HISTORICO
            ini = time.time()
            novos, falhadas = recolher_intervalo(cfg, de, ate, passo)
            print("\n%s anúncios novos em %s."
                  % (mil_pt(novos, " "), duracao_pt(time.time() - ini)))
            if falhadas:
                # Nomeadas, e nao contadas: o comando e idempotente, por
                # isso a resposta a uma falha e voltar a corre-lo com
                # estas datas -- mas so se souber quais sao.
                print("%d janela(s) por trazer. Volta a correr o comando "
                      "com estas datas:" % len(falhadas))
                for abre, fecha, mensagem in falhadas:
                    print("  --historico %s %s   (%s)" % (abre, fecha, mensagem))
            return
        dias = int(resto[0]) if resto else 730
        print("a puxar %d dias de historico, isto demora (uma pagina por "
              "segundo, para nao castigar o portal)..." % dias)
        cfg_historico = dict(cfg, dias_catchup=dias)
        mensagem, novos = verificar(cfg_historico)
        print(mensagem)
        return

    if "--detalhes" in sys.argv:
        # Preenche o detalhe -- CPV, prazo, preco base, plataforma, link
        # das pecas, texto -- dos anuncios que ainda nao o tem, do mais
        # recente para o mais antigo.
        #
        # Porque e que faz falta um comando: a verificacao le 40 por
        # volta e SO os ultimos `detalhe_dias` (60) dias, de proposito
        # -- entre a publicacao e o prazo vao ~18 dias, e o detalhe de
        # um anuncio fechado nao muda a decisao de hoje. Mas o que ficou
        # de tras nunca chegava a ser lido em massa (60 215 dos 66 387 a
        # 3/09/2026), e um anuncio sem detalhe e MUDO para o filtro por
        # CPV, para a arvore, para o preco e para os indicadores: conta
        # na base e nao aparece em nada disso.
        #
        # Nao gasta modelo nenhum -- e HTTP ao portal mais parsing; o
        # que gasta modelo e `--ler-pecas`. O que isto custa e tempo:
        # CONCORRENCIA_DETALHES pedidos ao portal ao mesmo tempo
        # (ler_detalhes_paralelo()). Retomavel por construcao, porque
        # cada anuncio fica gravado com detalhe_lido=1 assim que e
        # lido: um Ctrl-C, um corte de rede ou um reinicio nao perdem o
        # que ja se leu, e o comando repetido continua de onde ia.
        i = sys.argv.index("--detalhes")
        resto = [a for a in sys.argv[i + 1:] if not a.startswith("--")]
        tecto = None if not resto or resto[0] == "tudo" else int(resto[0])
        lote = int(cfg.get("detalhes_por_volta", 40))

        def por_ler():
            # A mesma condicao de ler_detalhes(): so a fonte do DR. As
            # preliminares da Vortal tambem passam por detalhe_lido=0 e
            # o detalhe delas e outro endpoint.
            with liga() as c:
                return c.execute(
                    "SELECT COUNT(*) n FROM anuncios WHERE detalhe_lido=0 "
                    "AND COALESCE(fonte,'dr')='dr'").fetchone()["n"]

        falta = por_ler()
        alvo = falta if tecto is None else min(tecto, falta)
        if not alvo:
            print("Não há anúncios do DR sem detalhe: está tudo lido.")
            return
        print("%s anúncio(s) do DR sem detalhe. Vou ler %s, %d por volta,\n"
              "%d pedidos ao portal ao mesmo tempo -- conta cerca de %s.\n"
              "Ctrl-C pára e não perde nada: o que já foi lido está gravado."
              % (mil_pt(falta, " "), mil_pt(alvo, " "), lote,
                 CONCORRENCIA_DETALHES, duracao_pt(alvo * SEGUNDOS_POR_DETALHE)))
        ini = time.time()
        feitos_total = detalhes_em_lote(alvo, lote, contar=por_ler)
        print("%s detalhe(s) lidos em %s; ficam %s por ler."
              % (mil_pt(feitos_total, " "), duracao_pt(time.time() - ini),
                 mil_pt(por_ler(), " ")))
        return

    # Os comandos --importar-excel e --casa-ligar sairam a 8/09/2026: o
    # Excel antigo deixou de contar para a aplicacao, e o registo da casa
    # entra pelo modelo, em Configuracoes > Importar dados. O leitor
    # antigo saiu do casa.py a 15/09/2026 -- esta no historico do git.

    if "--estado-zero" in sys.argv:
        # Pedido do Afonso a 8/09/2026: a aplicacao como acabada de
        # instalar, sem perder o acervo. Faz copia antes; pede confirmacao.
        if "--sim" not in sys.argv:
            if input("Isto apaga a triagem, o quadro, as etiquetas, o histórico, "
                     "os filtros, os alertas, o interesse e o registo da casa. "
                     "Escreve ZERO para continuar: ").strip() != "ZERO":
                print("Nada mudou.")
                return
        copia = copia_de_seguranca_com_nome("antes-estado-zero")
        n = repor_estado_zero()
        print("Cópia de antes em %s." % copia)
        for k, v in sorted(n.items()):
            print("  %-22s %s" % (k, v))
        print("Estado zero. O acervo ficou.")
        return

    if "--ensaiar-copia" in sys.argv:
        # 15/09/2026: prova que a ultima copia (ou a que se indicar) se
        # restaura, sem tocar em nada. Sai com 1 se nao servir.
        i = sys.argv.index("--ensaiar-copia")
        qual = sys.argv[i + 1] if len(sys.argv) > i + 1 else None
        try:
            r = ensaiar_copia(qual)
        except FileNotFoundError as erro:
            print("aviso: %s" % erro)
            sys.exit(1)
        print("Cópia: %s" % r["ficheiro"])
        print("Integridade: %s" % r["integridade"])
        for chave, (na_copia, na_viva) in r["contagens"].items():
            print("  %-14s cópia %-9s viva %s" % (chave, na_copia, na_viva))
        print("Serve." if r["serve"] else "NÃO SERVE: não restaures esta cópia.")
        if not r["serve"]:
            sys.exit(1)
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

    for bandeira in ("--criar-utilizador", "--palavra-passe"):
        if bandeira in sys.argv:
            # A mesma funcao para os dois: cria se nao existe, troca a
            # palavra-passe se existe. Por getpass e nao por argumento,
            # para a senha nao ficar no historico da consola. Recuperar
            # o acesso e isto, por SSH -- nao ha "esqueci-me" por e-mail.
            import getpass
            i = sys.argv.index(bandeira)
            email = sys.argv[i + 1] if len(sys.argv) > i + 1 else ""
            if not email or email.startswith("--"):
                print("Uso: python radar.py %s UTILIZADOR" % bandeira)
                return
            nome, papel = "", None
            if bandeira == "--criar-utilizador":
                papel = (input("Tipo (admin ou tester; Enter para admin): ")
                         .strip().lower() or "admin")
            senha = getpass.getpass("Palavra-passe (8 caracteres ou mais): ")
            if senha != getpass.getpass("Outra vez: "):
                print("Não são iguais. Nada mudou.")
                return
            try:
                with liga() as c:
                    contas.criar_utilizador(c, email, senha, nome, papel)
            except ValueError as erro:
                print("Não deu: %s" % erro)
                return
            print("Conta de %s pronta. Entra em %s/entrar."
                  % (contas.email_limpo(email), LOCAL))
            return

    if "--uma-vez" in sys.argv:
        # O mesmo trinco do painel: se o relogio de dentro dele ja
        # arrancou esta hora, este processo desiste em vez de correr a
        # segunda verificacao sobre a mesma base (8/09/2026, 17:00).
        tomou, porque = tomar_trinco()
        if not tomou:
            print("Não verifiquei: %s." % porque)
            return
        try:
            mensagem, novos = verificar(cfg)
        finally:
            largar_trinco()
        hora = min(cfg["horas_verificacao"],
                   key=lambda h: abs((datetime.now()
                                      - datetime.now().replace(
                                          hour=int(h[:2]), minute=int(h[3:]),
                                          second=0)).total_seconds()))
        registar_slot(datetime.now().strftime("%Y-%m-%d"), hora, novos)
        print(mensagem)
        return

    pode, porque = arranque_permitido(cfg, ENDERECO)
    if not pode:
        print("Não arranco: " + porque)
        return
    threading.Thread(target=relogio, daemon=True).start()
    print("Radar de Concursos, Diário da República")
    print("Painel em " + LOCAL)
    print("Fecha esta janela para parar. Ctrl+C tambem serve.")
    # Em thread, e a espera da porta: o app.run() so devolve quando o
    # painel fechar, portanto quem abre o browser tem de ser outro.
    # `--sem-browser` e para o painel a correr como servico (o
    # radar-painel.service que o agendar.sh cria): ai nao ha ninguem a
    # quem abrir uma janela, e num ambiente de trabalho com sessao
    # aberta cada reinicio do servico abria mais um separador.
    if "--sem-browser" not in sys.argv:
        threading.Thread(target=abrir_no_browser, daemon=True).start()
    app.run(host=ENDERECO, port=PORTA, debug=False)


if __name__ == "__main__":
    main()
