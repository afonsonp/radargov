#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes do Radar de Concursos.  Correr:  python teste_radar.py

Sao as verificacoes que se foram fazendo a mao e se perdiam a seguir.
Cada uma corresponde a um erro que existiu mesmo -- o comentario diz
qual, para nao se "simplificar" de volta para o erro.

Nao tocam na rede nem na base: so funcoes puras. Correm em menos de um
segundo, por isso nao ha desculpa para nao os correr antes de gravar.

Quando o DR mudar o formato dos anuncios, e o teste do parser que avisa.
"""

import contextlib
import datetime
import gc
import html
import inspect
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import unittest
import unittest.mock
from urllib.parse import parse_qsl, quote, unquote, unquote_plus, urlencode, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radar
import empresa


class TestPrefixoCPV(unittest.TestCase):
    """O filtro de CPV chegou a devolver 4592 anuncios em vez de 440."""

    def prefixos(self, codigo):
        onde, valores = radar.condicoes({"cpv": codigo, "estado": ""})
        # os valores vem aos pares: "prefixo%" e "%, prefixo%"
        return [v.rstrip("%") for v in valores[::2]]

    def test_divisao_redonda_nao_encolhe_a_um_digito(self):
        # "30000000".rstrip("0") == "3", e LIKE '3%' apanhava as divisoes
        # 31, 33, 34, 35, 37, 38 e 39 por engano
        for codigo in ("30000000", "50000000", "60000000",
                       "70000000", "80000000", "90000000"):
            with self.subTest(codigo=codigo):
                self.assertEqual(self.prefixos(codigo), [codigo[:2]])

    def test_divisao_normal(self):
        self.assertEqual(self.prefixos("72000000"), ["72"])
        self.assertEqual(self.prefixos("03000000"), ["03"])

    def test_codigo_completo_mantem_se(self):
        self.assertEqual(self.prefixos("45214200"), ["452142"])

    def test_digito_de_controlo_e_ignorado(self):
        # "72267100-0" chegou a virar "722671000" (nove digitos) e nunca
        # batia certo com o valor guardado, que leva o traco
        self.assertEqual(self.prefixos("72267100-0"), ["722671"])

    def test_termo_sem_correspondencia_nao_devolve_tudo(self):
        onde, _ = radar.condicoes({"cpv": "  ", "estado": ""})
        self.assertNotIn("1=0", onde)          # espaco em branco e ignorado


class TestEscapeLike(unittest.TestCase):
    """Procurar "50%" devolvia tudo o que tivesse "50"."""

    def test_percentagem_e_sublinhado_sao_escapados(self):
        self.assertEqual(radar.para_like("50%"), "50!%")
        self.assertEqual(radar.para_like("CP_26"), "CP!_26")

    def test_o_proprio_escape_e_escapado(self):
        self.assertEqual(radar.para_like("a!b"), "a!!b")

    def test_texto_normal_fica_intacto(self):
        self.assertEqual(radar.para_like("aquisição"), "aquisição")

    def test_a_clausula_declara_o_escape(self):
        onde, _ = radar.condicoes({"q": "50%", "estado": ""})
        self.assertIn("ESCAPE '!'", onde)


class TestCaixasDePesquisa(unittest.TestCase):
    """Objecto e entidade sao caixas separadas, e entre elas e E."""

    def test_objecto_procura_so_no_titulo(self):
        onde, _ = radar.condicoes({"q": "software", "estado": ""})
        self.assertIn("titulo_norm LIKE", onde)
        self.assertNotIn("entidade_norm LIKE", onde)

    def test_entidade_procura_so_na_entidade(self):
        onde, _ = radar.condicoes({"ent": "Camara", "estado": ""})
        self.assertIn("entidade_norm LIKE", onde)
        self.assertNotIn("titulo_norm LIKE", onde)

    def test_as_duas_juntam_se_com_AND(self):
        onde, valores = radar.condicoes(
            {"q": "software", "ent": "Camara", "estado": ""})
        self.assertIn(") AND (", onde)
        self.assertEqual(len(valores), 2)      # um termo por caixa

    def test_barra_vertical_e_OU_dentro_da_mesma_caixa(self):
        onde, _ = radar.condicoes({"q": "a|b", "estado": ""})
        self.assertIn(" OR ", onde)


class TestContagemDeDias(unittest.TestCase):
    """Um prazo que acaba hoje dizia "0 dias"; o dia seguinte, "1 dias"."""

    def test_hoje_nao_e_zero_dias(self):
        self.assertEqual(radar.conta_dias(0), "termina hoje")

    def test_um_dia_concorda(self):
        self.assertEqual(radar.conta_dias(1), "amanhã")

    def test_plural(self):
        self.assertEqual(radar.conta_dias(5), "5 dias")

    def test_hoje_e_urgente_nao_folgado(self):
        from datetime import date
        _, classe = radar.etiqueta_prazo(date.today().strftime("%Y-%m-%d"))
        self.assertEqual(classe, "mau")

    def test_prazo_vazio_nao_rebenta(self):
        self.assertEqual(radar.etiqueta_prazo(""), ("", ""))
        self.assertEqual(radar.etiqueta_prazo("nao-e-data"), ("", ""))


class TestNomeSeguro(unittest.TestCase):
    """Um ZIP nao pode escrever fora da pasta do anuncio."""

    def test_tira_caminhos(self):
        self.assertEqual(radar.nome_seguro("../../radar.db"), "radar.db")
        self.assertEqual(radar.nome_seguro(r"..\..\radar.db"), "radar.db")
        self.assertEqual(radar.nome_seguro("/etc/passwd"), "passwd")

    def test_tira_caracteres_que_um_sistema_de_ficheiros_recusa(self):
        self.assertNotIn(":", radar.nome_seguro("a:b.pdf"))
        self.assertNotIn("?", radar.nome_seguro("a?b.pdf"))

    def test_nunca_devolve_vazio(self):
        self.assertTrue(radar.nome_seguro(""))
        self.assertTrue(radar.nome_seguro("..."))

    def test_mantem_acentos(self):
        self.assertEqual(radar.nome_seguro("Anúncio DR.pdf"), "Anúncio DR.pdf")


class TestParserDoAnuncio(unittest.TestCase):
    """Se o DR mudar o formato, e aqui que se percebe primeiro."""

    TEXTO = """
1 - IDENTIFICAÇÃO E CONTACTOS DA ENTIDADE ADJUDICANTE
Designação da entidade adjudicante: Município de Exemplo
NIPC: 501234567

6 - OBJETO DO CONTRATO
Vocabulário Principal: 72268000 - Serviços de fornecimento de software
Preço base s/IVA: 21.500,00 EUR

13 - CONDIÇÕES DE APRESENTAÇÃO
Plataforma eletrónica utilizada pela entidade adjudicante: ACIN
URL para Apresentação: https://www.acingov.pt
Prazo para apresentação das propostas: 23-08-2026 23:59

15 - FORNECIMENTO DAS PEÇAS DO CONCURSO
Link para acesso às peças do concurso (URL): https://www.acingov.pt/x/y
"""

    def test_parte_em_seccoes_numeradas(self):
        seccoes = radar.seccoes_do_texto(self.TEXTO)
        numeros = [n for n, _, _ in seccoes]
        self.assertEqual(numeros, ["1", "6", "13", "15"])

    def test_le_os_campos_que_interessam(self):
        campos = radar.campos_do_detalhe(self.TEXTO)
        self.assertEqual(campos["cpv"], "72268000")
        self.assertEqual(campos["prazo"], "2026-08-23")
        self.assertEqual(campos["preco_base"], "21.500,00 EUR")
        self.assertEqual(campos["plataforma"], "acingov")
        self.assertEqual(campos["link_pecas"], "https://www.acingov.pt/x/y")

    def test_texto_vazio_nao_rebenta(self):
        self.assertEqual(radar.seccoes_do_texto(""), [])
        self.assertEqual(radar.campos_do_detalhe("")["cpv"], "")

    def test_compraspt_e_reconhecida(self):
        # esteve por reconhecer e caia num balde chamado "(nenhuma)"
        texto = ("13 - CONDIÇÕES DE APRESENTAÇÃO\n"
                 "Plataforma eletrónica utilizada pela entidade adjudicante: COMPRASPT\n"
                 "URL para Apresentação: https://www.compraspt.com/cpt-x/faces\n")
        self.assertEqual(radar.campos_do_detalhe(texto)["plataforma"], "compraspt")

    def test_chaves_repetidas_dos_lotes(self):
        texto = ("6 - OBJETO DO CONTRATO\n"
                 "Vocabulário Principal: 45214200 - Escolas\n"
                 "Vocabulário Principal: 45232400 - Esgotos\n")
        self.assertEqual(radar.campos_do_detalhe(texto)["cpv"],
                         "45214200, 45232400")


class TestTectoDeFicheiro(unittest.TestCase):
    """Um anúncio real trouxe 551 MB num só ZIP, tudo para memória."""

    class FalsaResposta:
        def __init__(self, tamanho, declarado=None):
            self.status_code = 200
            self._tamanho = tamanho
            self.headers = {"Content-Disposition":
                            "attachment; filename=\"grande.zip\""}
            if declarado is not None:
                self.headers["Content-Length"] = str(declarado)

        def iter_content(self, n):
            restante = self._tamanho
            while restante > 0:
                pedaco = min(n, restante)
                restante -= pedaco
                yield b"x" * pedaco

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class FalsaSessao:
        def __init__(self, resposta):
            self.resposta = resposta

        def get(self, *a, **k):
            return self.resposta

    def test_ficheiro_pequeno_passa(self):
        s = self.FalsaSessao(self.FalsaResposta(1000))
        nome, dados = radar._descarregar(s, "http://x", limite=5000)
        self.assertEqual(len(dados), 1000)
        self.assertEqual(nome, "grande.zip")

    def test_ficheiro_grande_e_recusado(self):
        s = self.FalsaSessao(self.FalsaResposta(9000))
        nome, dados = radar._descarregar(s, "http://x", limite=5000)
        self.assertIsNone(dados)
        self.assertEqual(nome, "grande.zip")   # o nome volta, para avisar

    def test_content_length_evita_descarregar_de_todo(self):
        # se o servidor declara o tamanho, nem se comeca
        s = self.FalsaSessao(self.FalsaResposta(9000, declarado=9000))
        _, dados = radar._descarregar(s, "http://x", limite=5000)
        self.assertIsNone(dados)

    def test_ha_um_tecto_por_omissao(self):
        self.assertGreater(radar.MAX_FICHEIRO, 0)


class TestNomeDaResposta(unittest.TestCase):

    class R:
        def __init__(self, disp):
            self.headers = {"Content-Disposition": disp} if disp else {}

    def test_utf8_com_mais_como_espaco(self):
        r = self.R("attachment; filename*=UTF-8''Programa+de+Concurso.pdf")
        self.assertEqual(radar._nome_da_resposta(r), "Programa de Concurso.pdf")

    def test_percentagem_descodificada(self):
        r = self.R("attachment; filename*=UTF-8''An%C3%BAncio.pdf")
        self.assertEqual(radar._nome_da_resposta(r), "Anúncio.pdf")

    def test_formato_simples(self):
        r = self.R('attachment; filename="Caderno de Encargos.pdf"')
        self.assertEqual(radar._nome_da_resposta(r), "Caderno de Encargos.pdf")

    def test_sem_cabecalho(self):
        self.assertEqual(radar._nome_da_resposta(self.R(None)), "")


class TestPlataformasJSF(unittest.TestCase):
    """anogov e compraspt sao a mesma aplicacao: um so obtentor serve."""

    def test_reconhece_os_hosts_conhecidos(self):
        for host in ("www.anogov.com", "www.compraspt.com",
                     "plataforma-sncp.espap.gov.pt"):
            with self.subTest(host=host):
                pagina = ('href="https://%s/x/decryptservlet?'
                          'papId=1&amp;fichId=2"' % host)
                achados = radar.docs_jsf_da_pagina(
                    pagina, "https://%s/x/faces/app/acessoDocs.jsp?c=1" % host)
                self.assertEqual(len(achados), 1)
                self.assertIn("fichId=2", achados[0])

    def test_a_espap_tem_a_assinatura_da_aplicacao(self):
        # vinha marcada como anogov no DR mas com link noutro host, e o
        # obtentor nunca era escolhido -- 14 concursos calados
        self.assertIn(radar.ASSINATURA_JSF,
                      "https://plataforma-sncp.espap.gov.pt/espap/faces/app/"
                      "acessoDocs.jsp?codigoAcesso=abc".lower())

    def test_a_assinatura_nao_depende_de_maiusculas(self):
        # o RX_DOC_JSF é re.I; as duas metades da decisão têm de
        # concordar, senão o link cai no "não sei trazer as peças"
        link = "https://x.pt/FACES/App/AcessoDocs.jsp?codigoAcesso=abc"
        self.assertIn(radar.ASSINATURA_JSF, link.lower())

    def test_nao_vai_buscar_a_outro_servidor(self):
        # a pagina e conteudo de fora: nao se segue para onde ela mandar
        pagina = 'href="https://outro-qualquer.pt/decryptservlet?fichId=2"'
        self.assertEqual(radar.docs_jsf_da_pagina(
            pagina, "https://www.anogov.com/x/faces/app/acessoDocs.jsp?c=1"), [])

    def test_nao_repete_o_mesmo_documento(self):
        um = 'href="https://www.anogov.com/d/decryptservlet?fichId=2"'
        self.assertEqual(len(radar.docs_jsf_da_pagina(
            um + " " + um,
            "https://www.anogov.com/x/faces/app/acessoDocs.jsp?c=1")), 1)

    def test_ambas_contam_como_obteniveis(self):
        # esteve escrito que a anogov nao dava; era um codigo de acesso
        # truncado a 78 caracteres, nao um bloqueio da plataforma
        for p in ("anogov", "compraspt", "acingov", "vortal"):
            self.assertIn(p, radar.PLATAFORMAS_COM_PECAS)


class TestCriterioDeAdjudicacao(unittest.TestCase):
    """A secção 21 vem de duas maneiras muito diferentes."""

    def criterio(self, texto):
        return radar.criterio_de_adjudicacao(radar.seccoes_do_texto(texto))

    def test_monofator(self):
        self.assertEqual(self.criterio(
            "21 - CRITÉRIO DE ADJUDICAÇÃO\n"
            "Multifator: Não\nMonofator: \nNome: Preço\n"), "Preço")

    def test_multifator_com_ponderacoes(self):
        # "Outro Nome" é o nome verdadeiro quando o Nome é "Outros"
        c = self.criterio(
            "21 - CRITÉRIO DE ADJUDICAÇÃO\n"
            "Multifator: Sim\n"
            "Fator: \nNome: Preço\nPonderação: 50%\n"
            "Fator: \nNome: Outros\nOutro Nome: Experiência da equipa\n"
            "Ponderação: 50%\n")
        self.assertIn("Preço 50%", c)
        self.assertIn("Experiência da equipa 50%", c)
        self.assertNotIn("Outros", c)

    def test_usa_ponto_literal_nao_a_entidade(self):
        # o valor passa por html.escape() ao ser desenhado: "&middot;"
        # sairia escrito tal e qual
        c = self.criterio(
            "21 - CRITÉRIO DE ADJUDICAÇÃO\nMultifator: Sim\n"
            "Nome: A\nPonderação: 60%\nNome: B\nPonderação: 40%\n")
        self.assertNotIn("&", c)

    def test_seccao_ausente(self):
        self.assertEqual(self.criterio("6 - OBJETO DO CONTRATO\nX: y\n"), "")

    def test_monofator_com_nome_outros(self):
        # 9,8% dos anúncios reais escrevem "Nome: Outros" e põem o nome
        # verdadeiro em "Outro nome". Ler só o "Nome" mostrava "Outros",
        # que não diz nada a ninguém.
        self.assertEqual(self.criterio(
            "21 - CRITÉRIO DE ADJUDICAÇÃO\n"
            "Multifator: Não\nMonofator: \nNome: Outros\n"
            "Outro nome: Fator Preço\n"), "Fator Preço")

    def test_nunca_devolve_a_palavra_outros(self):
        for texto in (
            "21 - CRITÉRIO DE ADJUDICAÇÃO\nMultifator: Não\n"
            "Nome: Outros\nOutro nome: Preço\n",
            "21 - CRITÉRIO DE ADJUDICAÇÃO\nMultifator: Sim\n"
            "Nome: Outros\nOutro nome: Qualidade técnica\nPonderação: 70%\n",
        ):
            self.assertNotIn("Outros", self.criterio(texto))


class TestTabelaEssencial(unittest.TestCase):
    """Os 12 campos que o Afonso quer ver ao abrir um concurso."""

    TEXTO = """
9 - LOCAL DA EXECUÇÃO DO CONTRATO
Concelho: Montijo
Distrito: Setúbal

10 - PRAZO DE EXECUÇÃO DO CONTRATO
Prazo de execução do contrato: 36 MESES
Previsão de renovações: Não

21 - CRITÉRIO DE ADJUDICAÇÃO
Multifator: Não
Nome: Preço
"""

    ANUNCIO = {"titulo": "Aquisição de X", "entidade": "Município Y",
               "preco_base": "150.000,00 EUR", "prazo": "2026-09-01",
               "data_pub": "2026-08-18"}

    # o que o modelo devolve depois de ler as pecas
    LIDO = {"objecto": "- fazer X", "equipa": "- um gestor",
            "documentos_proposta": "- DEUCP",
            "preco_anormalmente_baixo": "não consta",
            "localizacao": "Híbrido: 2 dias por semana presenciais",
            "fontes": "Caderno_de_Encargos.pdf, Programa.pdf",
            "modelo": "openai/gpt-oss-120b"}

    def tabela(self, texto=None, anuncio=None, analise=None):
        return radar.essencial_do_anuncio(
            anuncio or self.ANUNCIO,
            radar.seccoes_do_texto(texto if texto is not None else self.TEXTO),
            analise)

    def test_tem_os_doze_campos(self):
        self.assertEqual(len(self.tabela()), 12)

    def test_preenche_o_que_vem_do_anuncio(self):
        d = {r: v for r, v, _, _ in self.tabela()}
        self.assertEqual(d["Nome do projeto"], "Aquisição de X")
        self.assertEqual(d["Entidade adjudicante"], "Município Y")
        self.assertEqual(d["Preço base"], "150.000,00 EUR")
        # a data mostra-se a portuguesa; guarda-se ISO porque ordena
        self.assertEqual(d["Data de submissão da proposta"], "01/09/2026")
        self.assertEqual(d["Duração do contrato"], "36 MESES")
        self.assertEqual(d["Critério de adjudicação"], "Preço")

    def test_local_junta_concelho_e_distrito(self):
        d = {r: v for r, v, _, _ in self.tabela()}
        self.assertEqual(d["Local de prestação de serviços"], "Montijo, Setúbal")

    def test_local_nao_se_repete_quando_sao_iguais(self):
        t = "9 - LOCAL DA EXECUÇÃO DO CONTRATO\nConcelho: Lisboa\nDistrito: Lisboa\n"
        d = {r: v for r, v, _, _ in self.tabela(t)}
        self.assertEqual(d["Local de prestação de serviços"], "Lisboa")

    def test_renovacoes_aparecem_na_duracao(self):
        t = ("10 - PRAZO DE EXECUÇÃO DO CONTRATO\n"
             "Prazo de execução do contrato: 12 MESES\n"
             "Previsão de renovações: Sim\n")
        d = {r: v for r, v, _, _ in self.tabela(t)}
        self.assertIn("renovações", d["Duração do contrato"])

    def test_os_que_faltam_estao_assinalados(self):
        # nao se omitem: se nao aparecessem, parecia que nao existiam.
        # A data de esclarecimentos saiu desta lista quando passou a ser
        # calculada pela regra supletiva do CCP.
        faltam = {r for r, _, f, _ in self.tabela() if f}
        self.assertEqual(faltam, {
            "Preço anormalmente baixo",
            "Objeto, âmbito e características", "Equipa",
            "Documentos que constituem a proposta"})

    def test_diz_em_que_documento_esta_o_que_falta(self):
        for _, _, falta, _ in self.tabela():
            if falta:
                self.assertTrue("Caderno de Encargos" in falta
                                or "Programa de Concurso" in falta)

    def test_local_avisa_que_nao_e_o_local_de_trabalho(self):
        # a secção 9 do DR chama-se "LOCAL DA EXECUÇÃO DO CONTRATO
        # (PROCEDIMENTO)" e traz quase sempre a morada da entidade;
        # remoto, híbrido ou instalações nomeadas constam do CE
        nota = next(n for r, _, _, n in self.tabela()
                    if r == "Local de prestação de serviços")
        self.assertIn("Caderno de Encargos", nota)


    def test_pecas_lidas_preenchem_os_campos_que_faltavam(self):
        d = {r: v for r, v, _, _ in self.tabela(analise=self.LIDO)}
        self.assertEqual(d["Objeto, âmbito e características"], "- fazer X")
        self.assertEqual(d["Equipa"], "- um gestor")
        self.assertEqual(d["Documentos que constituem a proposta"], "- DEUCP")

    def test_lido_o_programa_sem_limiar_nao_se_promete_o_que_nao_ha(self):
        # dizer "so consta do Programa de Concurso" depois de o termos
        # lido e mandar procurar o que la nao esta: a maioria dos
        # Programas nao fixa limiar nenhum
        falta = next(f for r, _, f, _ in self.tabela(analise=self.LIDO)
                     if r == "Preço anormalmente baixo")
        self.assertIn("não fixa", falta)
        self.assertNotIn("só consta", falta)

    def test_com_limiar_mostra_o_valor_e_diz_de_onde_veio(self):
        lido = dict(self.LIDO, preco_anormalmente_baixo="40% do preço base")
        linha = next(l for l in self.tabela(analise=lido)
                     if l[0] == "Preço anormalmente baixo")
        self.assertEqual(linha[1], "40% do preço base")
        self.assertEqual(linha[2], "")
        self.assertIn("confirmar", linha[3])

    def test_o_regime_das_pecas_manda_no_local_do_anuncio(self):
        # a morada da entidade não diz se o trabalho é presencial,
        # remoto ou híbrido -- e é isso que decide se há quem o faça
        linha = next(l for l in self.tabela(analise=self.LIDO)
                     if l[0] == "Local de prestação de serviços")
        self.assertIn("Híbrido", linha[1])
        self.assertIn("segundo o anúncio", linha[1])
        self.assertIn("confirmar no documento", linha[3])

    def test_sem_leitura_o_local_continua_a_ser_o_do_anuncio(self):
        linha = next(l for l in self.tabela()
                     if l[0] == "Local de prestação de serviços")
        self.assertNotIn("Híbrido", linha[1])
        self.assertIn("ainda não foi lido", linha[3])

    def test_analise_sem_o_campo_novo_nao_deita_a_ficha_abaixo(self):
        # linha gravada antes de a coluna existir: um sqlite3.Row
        # rebenta em vez de devolver vazio, e ia a ficha inteira atrás
        antiga = {k: v for k, v in self.LIDO.items() if k != "localizacao"}
        linha = next(l for l in self.tabela(analise=antiga)
                     if l[0] == "Local de prestação de serviços")
        self.assertIn("ainda não foi lido", linha[3])

    def test_a_nota_nomeia_as_pecas_que_foram_mesmo_lidas(self):
        # numa leitura parcial, dizer "do Caderno de Encargos e do
        # Programa" era afirmar o que não houve
        so_o_programa = dict(self.LIDO, fontes="Programa.pdf")
        nota = next(n for r, _, _, n in self.tabela(analise=so_o_programa)
                    if r == "Equipa")
        self.assertIn("Programa.pdf", nota)
        self.assertNotIn("Caderno de Encargos", nota)


class TestSemIndice(unittest.TestCase):
    """O sumário empresa com todas as âncoras e não diz nada."""

    def test_tira_as_linhas_pontilhadas(self):
        d = ("Artigo 1.º | Objeto ............................ 2" + chr(10) +
             "O presente caderno tem por objeto o fornecimento de X.")
        r = radar.sem_indice(d)
        self.assertNotIn("Artigo 1.º | Objeto", r)
        self.assertIn("fornecimento de X", r)

    def test_nao_mexe_no_texto_normal(self):
        d = "Uma frase normal. Outra frase. E outra." + chr(10) + "Mais texto."
        self.assertEqual(radar.sem_indice(d), d)

    def test_pontos_espacados_tambem_contam(self):
        # o pdf devolve "..... ..... ....." com espaços pelo meio
        self.assertEqual(
            radar.sem_indice("Cláusula 5ª Preço . . . . . . 7"), "")


class TestEPdf(unittest.TestCase):
    """Pelos bytes e não pela extensão."""

    def caminho(self, conteudo):
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".seja-o-que-for")
        f.write(conteudo); f.close()
        self.addCleanup(lambda: os.path.exists(f.name) and os.remove(f.name))
        return f.name

    def test_pdf_sem_extensao(self):
        # a vortal entrega ficheiros sem extensão nenhuma; um anúncio
        # trazia um "Caderno de Encargos" de 291 KB que ficava por ler
        self.assertTrue(radar.e_pdf(self.caminho(b"%PDF-1.7 tralha")))

    def test_pdf_com_lixo_antes_da_assinatura(self):
        # a norma tolera-o e o pypdf lê-os na mesma
        self.assertTrue(radar.e_pdf(self.caminho(b"\r\n   %PDF-1.4 x")))

    def test_o_que_nao_e_pdf(self):
        self.assertFalse(radar.e_pdf(self.caminho(b"PK" + bytes(2000))))

    def test_zip_com_pdf_por_comprimir_nao_e_pdf(self):
        # o "%PDF" fica no byte 46 e a janela de 1 KB apanhava-o: o
        # extrair_textos mandava o pacote ao pypdf e nunca o abria
        import io, zipfile
        saco = io.BytesIO()
        with zipfile.ZipFile(saco, "w") as z:
            z.writestr("CE_Clausulas.pdf", b"%PDF-1.7 conteudo")
        self.assertFalse(radar.e_pdf(self.caminho(saco.getvalue())))

    def test_ficheiro_que_nao_existe(self):
        self.assertFalse(radar.e_pdf("nao-existe-de-certeza.pdf"))


class TestTextoDoZip(unittest.TestCase):
    """Há entidades que entregam a peça dentro de um ZIP."""

    def zip_com(self, ficheiros):
        import zipfile
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        f.close()
        with zipfile.ZipFile(f.name, "w") as z:
            for nome, dados in ficheiros:
                z.writestr(nome, dados)
        self.addCleanup(
            lambda: os.path.exists(f.name) and os.remove(f.name))
        return f.name

    def test_zip_sem_pdf_nenhum(self):
        caminho = self.zip_com([("leia.txt", b"nada")])
        self.assertEqual(radar.texto_do_zip(caminho, {"encargos"}),
                         ("", "não é PDF"))

    def test_pdf_ilegivel_nao_e_digitalizacao(self):
        # dizer "scan" a um PDF cifrado manda a pessoa procurar uma
        # digitalização quando o que falta é um pacote de Python
        caminho = self.zip_com([("CE_Clausulas.pdf", b"%PDF-1.7 estragado")])
        _, estado = radar.texto_do_zip(caminho, {"encargos"})
        self.assertTrue(estado.startswith("erro"), estado)

    def test_ficheiro_que_nao_e_zip(self):
        _, estado = radar.texto_do_zip("nao-existe-de-certeza.zip",
                                       {"encargos"})
        self.assertTrue(estado.startswith("erro"), estado)


class TestPecaOuAcessorio(unittest.TestCase):
    """As siglas de duas letras aparecem nos anexos por acaso."""

    def test_anexo_com_sigla_nao_e_a_peca(self):
        # "PC" aqui é o nome do anexo, não Programa de Concurso
        self.assertEqual(
            radar.papeis_da_peca("Anexo.2-PC-Anexo.II-Prop.Preco.xlsx"),
            set())

    def test_anexo_por_extenso_continua_a_contar(self):
        self.assertEqual(
            radar.papeis_da_peca("Anexo I - Caderno de Encargos.pdf"),
            {"encargos"})

    def test_sigla_vale_fora_dos_anexos(self):
        self.assertEqual(
            radar.papeis_da_peca("2026.06.30_PC_Outsourcing_vf_ass.pdf"),
            {"programa"})


class TestJuntarLeituras(unittest.TestCase):
    """Uma leitura parcial não pode apagar o que já estava lido."""

    ANTES = {"objecto": "- fazer X", "equipa": "- 20 perfis com preços",
             "documentos_proposta": "- DEUCP",
             "preco_anormalmente_baixo": "40%"}

    def test_o_pedido_que_falhou_mantem_o_valor_antigo(self):
        # a tabela de 20 perfis do INFARMED desapareceu assim: 429 no
        # pedido da equipa, chave ausente, INSERT por cima
        junto = radar.juntar_leituras({"objecto": "- fazer Y"}, self.ANTES)
        self.assertEqual(junto["objecto"], "- fazer Y")
        self.assertEqual(junto["equipa"], "- 20 perfis com preços")
        self.assertEqual(junto["documentos_proposta"], "- DEUCP")

    def test_nao_consta_e_resposta_e_substitui(self):
        junto = radar.juntar_leituras({"equipa": "não consta"}, self.ANTES)
        self.assertEqual(junto["equipa"], "não consta")

    def test_sem_leitura_anterior_fica_vazio(self):
        junto = radar.juntar_leituras({"objecto": "- fazer X"}, None)
        self.assertEqual(junto["objecto"], "- fazer X")
        self.assertEqual(junto["equipa"], "")

    def test_devolve_sempre_os_quatro_campos(self):
        self.assertEqual(set(radar.juntar_leituras({}, None)),
                         set(radar.CAMPOS_DA_ANALISE))


class TestJuntarFontes(unittest.TestCase):
    """As fontes têm de acompanhar os campos que o juntar_leituras guarda."""

    ANTES = "Caderno de Encargos.pdf, Programa.pdf"

    def test_leitura_parcial_nao_perde_a_peca_de_antes(self):
        # o objecto ficou do Caderno de Encargos lido antes; dizer só
        # "Programa.pdf" era atribuí-lo à peça errada na ficha
        juntas = radar.juntar_fontes(["Programa.pdf"], self.ANTES, True)
        self.assertIn("Caderno de Encargos.pdf", juntas)
        self.assertIn("Programa.pdf", juntas)

    def test_leitura_inteira_fica_so_com_as_desta_vez(self):
        # sem falhas, o que está guardado veio todo daqui: uma peça que
        # deixou de existir não pode continuar a ser citada
        self.assertEqual(radar.juntar_fontes(["Programa.pdf"], self.ANTES, False),
                         "Programa.pdf")

    def test_sem_fontes_novas_ficam_as_de_antes(self):
        self.assertEqual(radar.juntar_fontes([], self.ANTES, False), self.ANTES)

    def test_nao_repete(self):
        self.assertEqual(
            radar.juntar_fontes(["Programa.pdf"], "Programa.pdf", True),
            "Programa.pdf")

    def test_sem_leitura_anterior(self):
        self.assertEqual(radar.juntar_fontes(["Programa.pdf"], None, True),
                         "Programa.pdf")
        self.assertEqual(radar.juntar_fontes([], None, True), "")


class TestPapeisDaPeca(unittest.TestCase):
    """Que peça é cada ficheiro, pelo nome que a entidade lhe deu."""

    def test_nomes_por_extenso(self):
        for nome in ("1_Caderno_de_Encargos.pdf", "Caderno de Encargos.pdf",
                     "CADERNO_ENCARGOS_INFARMED(PRR)_WEBSITE_20260267.pdf"):
            self.assertEqual(radar.papeis_da_peca(nome), {"encargos"}, nome)
        for nome in ("2_Programa_do_Procedimento.pdf", "ProgramaConcurso.pdf",
                     "EPVL_CPi02-2627_ProgramaConsurso-Energia_signed.pdf"):
            self.assertEqual(radar.papeis_da_peca(nome), {"programa"}, nome)

    def test_siglas(self):
        # ficavam por ler com o texto ja extraido e ali a jeito
        self.assertEqual(radar.papeis_da_peca("1_02_CE_28_2026_CP_DO_signed.pdf"),
                         {"encargos"})
        self.assertEqual(radar.papeis_da_peca("1_2026.06.30_CE_Outsourcing_vf.pdf"),
                         {"encargos"})
        self.assertEqual(radar.papeis_da_peca("2_01_PP_28_2026_CP_DO_signed.pdf"),
                         {"programa"})

    def test_cp_e_concurso_publico_nao_programa(self):
        # "CP" no meio do nome é Concurso Público
        self.assertNotIn("programa", radar.papeis_da_peca("02_CE_28_CP_DO.pdf"))

    def test_um_ficheiro_pode_ser_as_duas_pecas(self):
        self.assertEqual(radar.papeis_da_peca("Programa_CE_12027226.pdf"),
                         {"encargos", "programa"})

    def test_o_que_nao_e_peca(self):
        # o "Lista.pdf" é o índice das peças e diz "Caderno de Encargos"
        # lá dentro -- por isso é que se vai pelo nome e não pelo conteúdo
        for nome in ("Lista.pdf", "Minuta do anúncio.pdf", "Anúncio DR.pdf",
                     "419971092.pdf", "espd-request.zip", "Anuncio_JOUE.pdf"):
            self.assertEqual(radar.papeis_da_peca(nome), set(), nome)


class TestOrcamentoDoDia(unittest.TestCase):
    """A conta tem dois tectos e só um se vê nos cabeçalhos."""

    class FalsaResposta:
        def __init__(self, texto):
            self.text, self.headers = texto, {}

    def test_reconhece_o_tecto_do_dia(self):
        # esperar e repetir num limite diário é tempo deitado fora:
        # uma releitura levou uma hora a não fazer nada
        self.assertTrue(radar.orcamento_do_dia_esgotado(self.FalsaResposta(
            "Rate limit reached ... on tokens per day (TPD): Limit 200000")))

    def test_nao_confunde_com_o_tecto_do_minuto(self):
        # esse passa sozinho ao fim de segundos, e vale a pena esperar
        self.assertFalse(radar.orcamento_do_dia_esgotado(self.FalsaResposta(
            "Rate limit reached ... on tokens per minute (TPM): Limit 8000")))

    def test_aguenta_resposta_vazia(self):
        self.assertFalse(radar.orcamento_do_dia_esgotado(
            self.FalsaResposta("")))


class TestEsperaPedida(unittest.TestCase):
    """Quanto esperar depois de um 429 -- o tecto de tokens por minuto.

    Marcar tres concursos seguidos bate no tecto; desistir a primeira
    perdia a leitura de um deles sem ninguem dar por isso.
    """

    class FalsaResposta:
        def __init__(self, cabecalhos, texto):
            self.headers, self.text = cabecalhos, texto

    def test_usa_o_cabecalho_da_api(self):
        self.assertEqual(radar.espera_pedida(
            self.FalsaResposta({"retry-after": "12.5"}, "")), 13.5)

    def test_sem_cabecalho_le_a_mensagem(self):
        self.assertEqual(radar.espera_pedida(self.FalsaResposta(
            {}, "Please try again in 8.42s. Visit...")), 9.42)

    def test_sem_pistas_espera_o_bastante(self):
        self.assertEqual(radar.espera_pedida(
            self.FalsaResposta({}, "nada")), 20.0)

    def test_ha_um_tecto_para_nao_ficar_pendurado(self):
        self.assertEqual(radar.espera_pedida(
            self.FalsaResposta({"retry-after": "9999"}, "")), 70)


class TestPrazoDeEsclarecimentos(unittest.TestCase):
    """Regra supletiva do art. 50.º CCP: 1.º terço do prazo das propostas.

    Não se lê do Programa de Concurso — calcula-se do que o anúncio já
    dá. Encontrada literalmente em 4 dos 6 PCs legíveis que se leram."""

    def esc(self, pub, prazo):
        d = radar.prazo_de_esclarecimentos(pub, prazo)
        return str(d) if d else None

    def test_primeiro_terco(self):
        # 27 dias entre publicação e prazo -> 9 dias depois da publicação
        self.assertEqual(self.esc("2026-08-25", "2026-09-21"), "2026-09-03")
        self.assertEqual(self.esc("2026-08-18", "2026-09-01"), "2026-08-22")

    def test_prazo_muito_curto(self):
        # 3 dias -> 1 dia; arredonda para baixo, nunca ultrapassa o terço
        self.assertEqual(self.esc("2026-08-25", "2026-08-28"), "2026-08-26")

    def test_datas_em_falta_ou_invalidas(self):
        for pub, prazo in (("2026-08-25", ""), ("", "2026-09-01"),
                           ("lixo", "2026-09-01"), (None, None)):
            with self.subTest(pub=pub, prazo=prazo):
                self.assertIsNone(self.esc(pub, prazo))

    def test_prazo_antes_da_publicacao_nao_inventa_data(self):
        self.assertIsNone(self.esc("2026-09-01", "2026-08-25"))
        self.assertIsNone(self.esc("2026-08-25", "2026-08-25"))

    def test_aparece_na_tabela_marcado_como_supletivo(self):
        anuncio = dict(TestTabelaEssencial.ANUNCIO, data_pub="2026-08-18")
        linha = next(l for l in radar.essencial_do_anuncio(anuncio, [])
                     if l[0] == "Data de esclarecimentos")
        rotulo, valor, falta, nota = linha
        self.assertIn("22/08/2026", valor)   # prazo 01/09/2026
        self.assertFalse(falta)              # deixou de estar em falta
        self.assertIn("supletiva", nota)     # mas diz que é calculado


class TestTextoDoPdf(unittest.TestCase):
    """Nunca rebentar: um PDF ilegível não pode parar a recolha."""

    def test_ficheiro_inexistente_devolve_erro_nao_excepcao(self):
        texto, estado = radar.texto_do_pdf("nao-existe-de-todo.pdf")
        self.assertEqual(texto, "")
        self.assertTrue(estado.startswith("erro"))

    def test_ficheiro_que_nao_e_pdf(self):
        texto, estado = radar.texto_do_pdf(__file__)   # este .py
        self.assertEqual(texto, "")
        self.assertTrue(estado.startswith("erro"))

    def test_ha_um_limiar_para_distinguir_digitalizacoes(self):
        # abaixo de N chars por página o PDF é imagem, e guardar o
        # "texto" dele seria guardar lixo
        self.assertGreater(radar.CHARS_POR_PAGINA_MINIMO, 0)


class TestDatas(unittest.TestCase):

    def test_normaliza_para_iso(self):
        self.assertEqual(radar.normaliza_data("23-08-2026"), "2026-08-23")
        self.assertEqual(radar.normaliza_data("23/08/2026"), "2026-08-23")
        self.assertEqual(radar.normaliza_data("2026-08-23"), "2026-08-23")


class TestETitulo(unittest.TestCase):
    """Distinguir um titulo de seccao de uma frase do corpo.

    Sem isto o orcamento de tokens gastava-se em frases que so por acaso
    tinham a palavra la dentro, e o anexo do fim do Caderno de Encargos
    -- que e onde mora o objecto -- ficava de fora do que se enviava.
    """

    def titulo(self, linha):
        return radar.e_titulo(linha.strip(), radar.simplifica(linha.strip()))

    def test_titulos_reais(self):
        for linha in ("Cláusula 1ª - Objeto do procedimento",
                      "Artigo 9.º  - Documentos da proposta",
                      "Anexo I - Especificações Técnicas",
                      "1. Objeto da Solução Tecnológica",
                      "3. Equipa",
                      "Perfil de Equipa"):
            self.assertTrue(self.titulo(linha), linha)

    def test_frases_do_corpo_nao_sao_titulos(self):
        # acabam em pontuacao de frase, ou comecam por minuscula
        for linha in ("2. As rejeições de serviços são objeto de notificação.",
                      "no âmbito do contrato;",
                      "equipa, em conjunto:",
                      "à prestação de serviços objeto do presente Caderno.",
                      "h)  Não subcontratar a execução do objeto do contrato, se"):
            self.assertFalse(self.titulo(linha), linha)

    def test_linha_comprida_nao_e_titulo(self):
        self.assertFalse(self.titulo("Verificação de Requisitos Legais: "
                                     "Funcionalidade para assinalar a "
                                     "conformidade de cada documento"))


class TestAncorasDoRecorte(unittest.TestCase):

    def empresa(self, linha, ancoras):
        import re
        curta = radar.simplifica(linha)
        return any(re.search(padrao, curta) for _, padrao in ancoras)

    def test_resolucao_nao_e_solucao(self):
        # "Clausula 24a - Resolucao do contrato" casava com "solucao" por
        # nao haver fronteira de palavra, e comia o orcamento todo
        self.assertFalse(self.empresa("Cláusula 24ª - Resolução do contrato",
                                   radar.ANCORAS_OBJECTO))
        self.assertFalse(self.empresa("Cláusula 35ª - Resolução de litígios",
                                   radar.ANCORAS_OBJECTO))
        self.assertTrue(self.empresa("1. Objeto da Solução Tecnológica",
                                  radar.ANCORAS_OBJECTO))

    def test_o_que_interessa_empresa(self):
        self.assertTrue(self.empresa("3. Equipa", radar.ANCORAS_EQUIPA))
        self.assertTrue(self.empresa("Cláusula 39ª Profissionais",
                                  radar.ANCORAS_EQUIPA))
        self.assertTrue(self.empresa("Artigo 9.º - Documentos da proposta",
                                  radar.ANCORAS_PROGRAMA))


class TestRecorteRelevante(unittest.TestCase):
    """O anexo do fim tem de sobreviver ao corte."""

    def documento(self):
        rotina = ("Cláusula %d - Penalidades" + chr(10) +
                  "Texto de rotina. " * 60 + chr(10))
        corpo = "".join(rotina % n for n in range(1, 20))
        return (corpo + chr(10) + "3. Equipa" + chr(10) +
                "A equipa é composta por um gestor e um arquiteto." + chr(10))

    def test_apanha_o_anexo_do_fim(self):
        d = self.documento()
        r = radar.recorte_relevante(d, radar.ANCORAS_EQUIPA, 4000)
        self.assertIn("3. Equipa", r)
        self.assertIn("gestor e um arquiteto", r)

    def test_respeita_o_tecto(self):
        # o tecto e o limite de tokens por minuto da API: passar dele e 413
        d = self.documento()
        self.assertLessEqual(len(radar.recorte_relevante(
            d, radar.ANCORAS_EQUIPA, 2000)), 2000)

    def test_a_equipa_nao_disputa_o_orcamento_com_o_objecto(self):
        # num Caderno de Encargos de 167 mil caracteres, a tabela de
        # perfis estava na posicao 136 mil e as ancoras do objecto
        # gastavam o orcamento muito antes; o modelo respondia
        # "conforme o Anexo I", que e verdade e nao serve
        cabeca = ("Cláusula %d Objeto e âmbito da solução" + chr(10) +
                  "Texto de rotina sobre o objeto. " * 40 + chr(10))
        documento = ("".join(cabeca % n for n in range(1, 30)) + chr(10) +
                     "Cláusula 39ª Profissionais" + chr(10) +
                     "Gestor de Projeto 8 anos Certificação em Gestão" + chr(10))
        r = radar.recorte_relevante(documento, radar.ANCORAS_EQUIPA, 4000)
        self.assertIn("Gestor de Projeto 8 anos", r)

    def test_sem_ancoras_devolve_o_principio(self):
        d = "Texto sem titulos nenhuns. " * 300
        r = radar.recorte_relevante(d, radar.ANCORAS_OBJECTO, 500)
        self.assertEqual(r, d[:500])


class TestLimpaCampo(unittest.TestCase):

    def test_desfaz_o_escape_a_dobrar(self):
        # o modelo escreve "\\n" no JSON e o json.loads so desfaz uma
        # camada, pelo que o "\n" aparecia a letra no meio do texto
        self.assertEqual(radar.limpa_campo("- um\\n- dois"),
                         "- um" + chr(10) + "- dois")

    def test_tira_espacos_e_colapsa_as_linhas_em_branco(self):
        # a linha em branco passou a valer: separa os blocos por perfil
        # da equipa. Continua a colapsar as seguidas e a limpar as
        # pontas -- era isso que este teste protegia, e continua a
        # proteger
        self.assertEqual(radar.limpa_campo("  a  \\n\\n  b "),
                         "a" + chr(10) + chr(10) + "b")
        self.assertEqual(radar.limpa_campo("a\\n\\n\\n\\nb"),
                         "a" + chr(10) + chr(10) + "b")
        self.assertEqual(radar.limpa_campo("\\n\\n a \\n\\n"), "a")

    def test_aguenta_vazio(self):
        self.assertEqual(radar.limpa_campo(None), "")


class TestCadeiaDeFornecedores(unittest.TestCase):
    """Quem entra na cadeia de reserva, e por que ordem.

    Um fornecedor sem chave configurada custava uma volta e um 401 a
    cada uma das três perguntas de cada concurso da fila — o contrário
    do que a cadeia existe para fazer.
    """

    FALSOS = (
        ("groq", "https://groq/x", "modelo-groq", ("g.txt",), "G_KEY", {}),
        ("openrouter", "https://or/x", "modelo-or", ("o.txt",), "O_KEY", {}),
        ("nvidia", "https://nv/x", "modelo-nv", ("n.txt",), "N_KEY",
         {"reasoning_effort": "low"}),
    )

    def setUp(self):
        self.enterContext(unittest.mock.patch.object(
            radar, "FORNECEDORES", self.FALSOS))
        # com_chaves() troca o ler_chave dentro do teste; o patch so
        # garante que volta ao verdadeiro no fim
        self.enterContext(unittest.mock.patch.object(
            radar, "ler_chave", radar.ler_chave))

    def com_chaves(self, *quais):
        radar.ler_chave = lambda nomes, var: ("k" if nomes[0][0] in quais
                                              else "")

    def test_so_entra_quem_tem_chave(self):
        self.com_chaves("g", "n")
        self.assertEqual([f[0] for f in radar.cadeia_de_fornecedores({})],
                         ["groq", "nvidia"])

    def test_a_ordem_e_a_da_lista(self):
        # a Groq à frente por ser a única com leituras julgadas boas
        self.com_chaves("o", "g")
        self.assertEqual([f[0] for f in radar.cadeia_de_fornecedores({})],
                         ["groq", "openrouter"])

    def test_sem_chave_nenhuma_a_cadeia_e_vazia(self):
        # é o que faz o analisar_pecas dizer "falta a chave da API"
        self.com_chaves()
        self.assertEqual(radar.cadeia_de_fornecedores({}), [])

    def test_fornecedor_pecas_prende_a_um_so(self):
        # serve para comparar leituras entre modelos sem mexer no código
        self.com_chaves("g", "o", "n")
        cadeia = radar.cadeia_de_fornecedores({"fornecedor_pecas": "openrouter"})
        self.assertEqual([f[0] for f in cadeia], ["openrouter"])

    def test_os_extras_viajam_com_o_fornecedor(self):
        # o reasoning_effort do NVIDIA vale 3,5s em vez de 168s, e é só
        # dele: um parâmetro a mais dava 400 noutro e tirava-o da cadeia
        self.com_chaves("n")
        self.assertEqual(radar.cadeia_de_fornecedores({})[0][4],
                         {"reasoning_effort": "low"})


class TestModeloDoFornecedor(unittest.TestCase):
    """O "modelo_pecas" do config antigo é da Groq, e só dela.

    Aplicado à cadeia toda, escolhia o modelo do fornecedor errado: um
    "openai/gpt-oss-120b" no config passava a pedir esse nome ao
    OpenRouter, onde não existe.
    """

    def test_sem_config_fica_o_de_origem(self):
        self.assertEqual(
            radar.modelo_do_fornecedor({}, "openrouter", "origem"), "origem")

    def test_o_config_antigo_so_vale_para_a_groq(self):
        cfg = {"modelo_pecas": "outro"}
        self.assertEqual(radar.modelo_do_fornecedor(cfg, "groq", "origem"),
                         "outro")
        self.assertEqual(radar.modelo_do_fornecedor(cfg, "nvidia", "origem"),
                         "origem")

    def test_o_mapa_por_fornecedor_manda(self):
        cfg = {"modelo_pecas": "antigo", "modelos_pecas": {"groq": "novo"}}
        self.assertEqual(radar.modelo_do_fornecedor(cfg, "groq", "origem"),
                         "novo")

    def test_valores_vazios_nao_contam(self):
        # um "" no config não é uma escolha -- é o campo por preencher
        cfg = {"modelo_pecas": "  ", "modelos_pecas": {"groq": ""}}
        self.assertEqual(radar.modelo_do_fornecedor(cfg, "groq", "origem"),
                         "origem")


class TestOrcamentoPorFornecedor(unittest.TestCase):
    """O tecto do dia é de cada fornecedor, não da cadeia."""

    def setUp(self):
        radar._ESGOTADOS.clear()

    tearDown = setUp

    def test_esgotado_e_por_dia(self):
        # à meia-noite a data muda e a memória limpa-se sozinha
        radar.marcar_esgotado("groq", "2026-08-27")
        self.assertTrue(radar.esta_esgotado("groq", "2026-08-27"))
        self.assertFalse(radar.esta_esgotado("groq", "2026-08-28"))

    def test_um_esgotado_nao_esgota_a_cadeia(self):
        # com "algum", bastava a Groq acabar para o painel dar o dia por
        # perdido com o NVIDIA ainda a responder ao lado
        cadeia = [("groq", "u", "m", "k", {}), ("nvidia", "u", "m", "k", {})]
        radar.marcar_esgotado("groq")
        self.assertFalse(radar.cadeia_esgotada(cadeia))

    def test_todos_esgotados_esgotam_a_cadeia(self):
        cadeia = [("groq", "u", "m", "k", {}), ("nvidia", "u", "m", "k", {})]
        radar.marcar_esgotado("groq")
        radar.marcar_esgotado("nvidia")
        self.assertTrue(radar.cadeia_esgotada(cadeia))

    def test_cadeia_vazia_nao_esta_esgotada(self):
        # sem chaves a mensagem certa é "falta a chave", não "acabou o dia"
        self.assertFalse(radar.cadeia_esgotada([]))


class TestJsonDaResposta(unittest.TestCase):
    """Os modelos gratuitos embrulham o JSON em cercas markdown.

    A Groq honra o response_format; os outros nem sempre. Sem desfazer
    a cerca, a cadeia descia para o fornecedor seguinte com a resposta
    boa na mão.
    """

    def test_json_simples(self):
        self.assertEqual(radar.json_da_resposta('{"a": 1}'), {"a": 1})

    def test_dentro_de_cerca_com_linguagem(self):
        self.assertEqual(
            radar.json_da_resposta('```json' + chr(10) + '{"a": 1}' +
                                   chr(10) + '```'), {"a": 1})

    def test_dentro_de_cerca_sem_linguagem(self):
        self.assertEqual(
            radar.json_da_resposta('```' + chr(10) + '{"a": 1}' +
                                   chr(10) + '```'), {"a": 1})

    def test_lixo_continua_a_ser_erro(self):
        # tem de continuar a falhar: é o ValueError que faz a cadeia
        # descer para o fornecedor seguinte
        with self.assertRaises(ValueError):
            radar.json_da_resposta("desculpe, não percebi")


class TestPerguntarDesceACadeia(unittest.TestCase):
    """A cadeia salta para o seguinte quando um fornecedor esgota.

    Era este o ponto: o tecto diário da Groq acabava a meio de uma
    releitura do acervo e a fila ficava parada até ao dia seguinte.
    """

    def setUp(self):
        radar._ESGOTADOS.clear()
        self.addCleanup(radar._ESGOTADOS.clear)
        # responder() troca o _um_pedido dentro do teste; o patch so
        # garante que volta ao verdadeiro no fim
        self.enterContext(unittest.mock.patch.object(
            radar, "_um_pedido", radar._um_pedido))
        self.chamados = []

    def responder(self, respostas):
        """respostas: {nome do modelo: (dados, aviso)}."""
        def falso(url, chave, modelo, instrucao, texto, extras=None):
            self.chamados.append(modelo)
            self.extras = extras
            return respostas.get(modelo, (None, "sem resposta"))
        radar._um_pedido = falso

    CADEIA = [("groq", "u", "m-groq", "k", {}),
              ("nvidia", "u", "m-nv", "k", {"reasoning_effort": "low"})]

    def test_o_primeiro_que_responde_ganha(self):
        self.responder({"m-groq": ({"objecto": "x"}, "")})
        dados, aviso, usado = radar._perguntar(self.CADEIA, "i", "t")
        self.assertEqual(dados, {"objecto": "x"})
        self.assertEqual(usado, "groq:m-groq")
        self.assertEqual(self.chamados, ["m-groq"])

    def test_esgotado_o_primeiro_desce_para_o_segundo(self):
        self.responder({"m-groq": (None, radar.SEM_ORCAMENTO_HOJE),
                        "m-nv": ({"objecto": "y"}, "")})
        dados, aviso, usado = radar._perguntar(self.CADEIA, "i", "t")
        self.assertEqual(dados, {"objecto": "y"})
        self.assertEqual(usado, "nvidia:m-nv")

    def test_o_tecto_do_dia_fica_marcado_e_nao_se_repete(self):
        # sem esta memória, cada uma das três perguntas de cada concurso
        # voltava a bater na mesma porta fechada -- a hora deitada fora
        # que o SEM_ORCAMENTO_HOJE veio evitar
        self.responder({"m-groq": (None, radar.SEM_ORCAMENTO_HOJE),
                        "m-nv": ({"objecto": "y"}, "")})
        radar._perguntar(self.CADEIA, "i", "t")
        radar._perguntar(self.CADEIA, "i", "t")
        self.assertTrue(radar.esta_esgotado("groq"))
        self.assertEqual(self.chamados.count("m-groq"), 1)

    def test_uma_falha_normal_nao_marca_esgotado(self):
        # um 500 passageiro não pode encerrar o fornecedor até amanhã
        self.responder({"m-groq": (None, "respondeu 500: ..."),
                        "m-nv": ({"objecto": "y"}, "")})
        radar._perguntar(self.CADEIA, "i", "t")
        self.assertFalse(radar.esta_esgotado("groq"))

    def test_falhando_todos_o_aviso_diz_quem_falhou(self):
        self.responder({})
        dados, aviso, usado = radar._perguntar(self.CADEIA, "i", "t")
        self.assertIsNone(dados)
        self.assertEqual(usado, "")
        self.assertIn("groq", aviso)
        self.assertIn("nvidia", aviso)


class TestModeloGuardadoNaReleitura(unittest.TestCase):
    """A coluna analise.modelo passou a dizer quem respondeu.

    Sendo agora variável, uma releitura parcial apagava o registo do
    modelo que leu os outros campos -- o mesmo erro que o juntar_fontes
    já tinha pago na coluna irmã, e por isso é ele que se reutiliza.
    """

    def test_releitura_parcial_guarda_o_modelo_anterior(self):
        self.assertEqual(
            radar.juntar_fontes(["openrouter:m-or"], "groq:m-groq", True),
            "openrouter:m-or, groq:m-groq")

    def test_leitura_completa_substitui(self):
        # sem falhas, o que está agora é o retrato inteiro
        self.assertEqual(
            radar.juntar_fontes(["groq:m-groq"], "openrouter:m-or", False),
            "groq:m-groq")


class TestFiltroCanonico(unittest.TestCase):
    """A consulta guardada tem de ser sempre a mesma para os mesmos
    filtros, senao o filtro guardado nunca se reconhece como o que esta
    em uso -- e o botao de guardar nunca oferecia actualizar, so criar
    outro com o mesmo nome.
    """

    def test_estado_ausente_e_por_ver(self):
        # condicoes() trata a falta de estado como a entrada da escada; se
        # a consulta guardada nao dissesse isso, o filtro voltava como
        # "todos". Desde 15/09/2026 a palavra e "porver" e nao "novo"
        self.assertEqual(radar.filtro_actual({}), "estado=porver")

    def test_a_consulta_guardada_fala_o_vocabulario_de_hoje(self):
        """Um filtro guardado antes de 15/09/2026 tem "estado=novo"
        escrito. A consulta canonica traduz-o, senao o filtro em uso
        nunca se reconhecia a si proprio e o botao de guardar so oferecia
        criar outro com o mesmo nome -- que e o erro que esta classe
        inteira existe para travar."""
        self.assertEqual(radar.filtro_actual({"estado": "novo"}),
                         "estado=porver")
        self.assertEqual(radar.filtro_actual({"estado": "interessa"}),
                         "estado=analisar")

    def test_estado_vazio_e_todos_e_nao_se_perde(self):
        # vazio nao e a mesma coisa que ausente, e nao se pode deixar cair
        # por ser vazio: e a aba "Todos"
        self.assertEqual(radar.filtro_actual({"estado": ""}), "estado=")

    def test_ordem_fixa_seja_qual_for_a_ordem_da_url(self):
        um = radar.filtro_actual({"estado": "porver", "q": "software"})
        outro = radar.filtro_actual({"q": "software", "estado": "porver"})
        self.assertEqual(um, outro)
        self.assertEqual(um, "q=software&estado=porver")

    def test_pagina_e_aviso_ficam_de_fora(self):
        # guardar na pagina 3 gravava a pagina 3, e o filtro abria sempre
        # a meio; o aviso pegava-se ao filtro e reaparecia a cada vez
        consulta = radar.filtro_actual(
            {"q": "software", "pag": "3", "aviso": "Filtro guardado"})
        self.assertNotIn("pag", consulta)
        self.assertNotIn("aviso", consulta)

    def test_campos_vazios_nao_entram(self):
        # senao "q=&ent=&cpv=" era diferente de "" e o chip nao marcava
        self.assertEqual(radar.filtro_actual({"q": "", "ent": "  "}),
                         "estado=porver")


class TestArgsDaLista(unittest.TestCase):
    """O paginador pede uma pagina e a limpeza apagava-lha a seguir: o
    `pop` dos campos da vez corria depois do `update`, e todas as
    ligacoes do paginador apontavam para a pagina 1.
    """

    class _Args(dict):
        def to_dict(self):
            return dict(self)

    def test_a_pagina_pedida_sobrevive_a_limpeza(self):
        saiu = radar.args_da_lista(self._Args({"q": "a", "pag": "1"}), pag="7")
        self.assertEqual(saiu["pag"], "7")

    def test_sem_pagina_pedida_a_pagina_cai(self):
        # mexer num filtro volta a pagina 1: a pagina 7 do filtro anterior
        # nao existe no filtro novo
        saiu = radar.args_da_lista(self._Args({"q": "a", "pag": "7"}))
        self.assertNotIn("pag", saiu)

    def test_o_aviso_nao_se_arrasta(self):
        saiu = radar.args_da_lista(self._Args({"q": "a", "aviso": "guardado"}))
        self.assertNotIn("aviso", saiu)
        self.assertEqual(saiu["q"], "a")


class TestNormaEntidade(unittest.TestCase):
    """Ligar uma entidade do radar às adjudicações dela no corpus do BASE.

    O radar guarda o nome como o DR o escreve, o BASE guarda "NIF - nome".
    Medido sobre as 898 entidades do radar contra dois anos de corpus:
    93,7% acham-se só com esta normalização, sem uma única ambiguidade.
    Normalizar mais (tirar EPE/SA/IP, unificar Município com Câmara
    Municipal) acrescentava dois casos em 898 e arriscava juntar
    entidades diferentes -- por isso NÃO se faz, e é o que estes testes
    seguram.
    """

    def test_tira_acentos_maiusculas_e_pontuacao(self):
        self.assertEqual(radar.norma_entidade("Município de Oeiras"),
                         "municipio de oeiras")
        self.assertEqual(radar.norma_entidade("MUNICÍPIO  DE  OEIRAS!"),
                         "municipio de oeiras")

    def test_e_comercial_vira_palavra(self):
        # "Mentores & Tutores" e "Mentores e Tutores" sao a mesma entidade
        self.assertEqual(radar.norma_entidade("Mentores & Tutores"),
                         radar.norma_entidade("Mentores e Tutores"))

    def test_nao_unifica_o_que_e_mesmo_diferente(self):
        # de proposito: sao nomes diferentes e juntar entidades distintas
        # e pior do que nao achar uma
        self.assertNotEqual(radar.norma_entidade("Município de Felgueiras"),
                            radar.norma_entidade("Câmara Municipal de Felgueiras"))

    def test_nome_vazio_nao_rebenta(self):
        # sem isto, um anuncio sem entidade ia procurar "" no corpus e
        # trazia tudo o que tambem tivesse nome vazio
        self.assertEqual(radar.norma_entidade(""), "")
        self.assertEqual(radar.norma_entidade(None), "")


class TestPrefixoCPVSozinho(unittest.TestCase):
    """A regra do prefixo saiu de dentro da condicoes() para o corpus de
    contratos poder procurar com o mesmo critério. Duas cópias da regra
    divergiam -- e a de baixo de dois dígitos já custou 4592 anúncios em
    vez de 440 uma vez.
    """

    def test_concorda_com_o_filtro_da_lista(self):
        for codigo in ("72000000", "30000000", "45214200", "72267100-0", "03000000"):
            with self.subTest(codigo=codigo):
                _, valores = radar.condicoes({"cpv": codigo, "estado": ""})
                self.assertEqual(radar.prefixo_cpv(codigo),
                                 valores[0].rstrip("%"))

    def test_sem_digitos_nao_da_prefixo(self):
        # "" tem de ser falso, senao LIKE '%' apanhava o corpus inteiro
        self.assertEqual(radar.prefixo_cpv("-"), "")
        self.assertEqual(radar.prefixo_cpv(""), "")
        self.assertEqual(radar.prefixo_cpv(None), "")


class TestAnosPedidos(unittest.TestCase):
    """Os anos do --contratos, lidos da linha de comando."""

    HOJE = datetime.datetime(2026, 8, 27)

    def test_sem_nada_traz_o_corrente_e_o_anterior(self):
        # so o ano corrente nao servia: em Janeiro estava quase vazio
        self.assertEqual(radar.anos_pedidos([], self.HOJE), [2025, 2026])

    def test_intervalo(self):
        self.assertEqual(radar.anos_pedidos(["2019-2022"], self.HOJE),
                         [2019, 2020, 2021, 2022])

    def test_anos_soltos_saem_ordenados_e_sem_repetir(self):
        self.assertEqual(radar.anos_pedidos(["2026", "2024", "2024"], self.HOJE),
                         [2024, 2026])

    def test_lixo_cai_no_valor_de_origem(self):
        self.assertEqual(radar.anos_pedidos(["ontem"], self.HOJE), [2025, 2026])


class TestObjectosDoArray(unittest.TestCase):
    """Um ano de contratos são 268 MB de JSON: lê-se objecto a objecto,
    porque um json.loads disso constrói a lista toda em memória.
    """

    def test_le_um_a_um(self):
        self.assertEqual(list(radar.objectos_do_array('[{"a":1},{"a":2}]')),
                         [{"a": 1}, {"a": 2}])

    def test_aguenta_aninhamento_e_virgulas_dentro(self):
        # o corte ingenuo pela virgula partia os campos que sao listas,
        # e todos os campos do BASE que interessam sao listas
        texto = '[{"cpv":["72000000-0 - a, b"],"n":[1,2]},{"cpv":[]}]'
        self.assertEqual(list(radar.objectos_do_array(texto)),
                         [{"cpv": ["72000000-0 - a, b"], "n": [1, 2]},
                          {"cpv": []}])

    def test_array_vazio_e_espacos(self):
        self.assertEqual(list(radar.objectos_do_array("  [ ]  ")), [])
        self.assertEqual(list(radar.objectos_do_array('[\n  {"a":1}\n]')),
                         [{"a": 1}])


class TestPartesDoBase(unittest.TestCase):
    """Os campos do dump do BASE, que vêm quase todos como lista."""

    def test_nif_e_nome_separam_se(self):
        self.assertEqual(radar._nif_e_nome(["503093742 - AdP - Águas, SA"]),
                         ("503093742", "AdP - Águas, SA"))

    def test_sem_nif_fica_so_o_nome(self):
        # ha registos antigos sem NIF; nao se perde o nome por causa disso
        self.assertEqual(radar._nif_e_nome(["Entidade Antiga"]),
                         ("", "Entidade Antiga"))

    def test_lista_vazia_nao_rebenta(self):
        self.assertEqual(radar._nif_e_nome([]), ("", ""))
        self.assertEqual(radar._nif_e_nome(None), ("", ""))

    def test_cpv_fica_com_oito_digitos(self):
        # o digito de controlo descola do formato guardado nos anuncios
        self.assertEqual(radar._cpv8(["72210000-0 - Serviços", "48000000-8 - x"]),
                         ["72210000", "48000000"])
        self.assertEqual(radar._cpv8(None), [])

    def test_data_passa_a_iso_para_ordenar_como_texto(self):
        self.assertEqual(radar._data_iso("23/02/2026"), "2026-02-23")
        self.assertEqual(radar._data_iso(""), "")
        self.assertEqual(radar._data_iso("sem data"), "")


class TestCondicoesContratos(unittest.TestCase):
    """Os filtros do separador dos contratos. Lista própria e filtros
    próprios: um anúncio não tem vencedor nem valor final, por isso
    "quem ganhou" e "desde € X" só existem aqui.
    """

    def test_quem_ganhou_por_subconsulta_e_nunca_por_join(self):
        # com JOIN, um contrato ganho por um agrupamento de três aparecia
        # três vezes na lista -- e há um com 35 adjudicatários. Vale
        # qualquer forma que não repita linhas (hoje é `IN`, foi `EXISTS`);
        # o que não pode voltar é o JOIN.
        onde, _ = radar.condicoes_contratos({"ganhou": "Bayer"})
        self.assertNotIn("JOIN", onde.upper())
        self.assertIn("contrato_adjudicatario", onde)

    def test_cpv_por_subconsulta_pelo_mesmo_motivo(self):
        # um contrato pode ter vários CPV da mesma divisão
        onde, valores = radar.condicoes_contratos({"cpv": "72000000"})
        self.assertNotIn("JOIN", onde.upper())
        self.assertIn("contrato_cpv", onde)
        self.assertIn("72*", valores)

    def test_cpv_sem_prefixo_nao_devolve_tudo(self):
        # "-" não dá prefixo; sem o 1=0, o filtro caía e mostrava o
        # corpus inteiro como se não houvesse filtro nenhum
        onde, _ = radar.condicoes_contratos({"cpv": "-"})
        self.assertIn("1=0", onde)

    def test_preco_minimo_com_lixo_nao_filtra_nem_rebenta(self):
        onde, valores = radar.condicoes_contratos({"min": "muito"})
        self.assertNotIn("preco_contratual", onde)
        self.assertEqual(valores, [])

    def test_preco_minimo_aceita_virgula_e_espacos(self):
        _, valores = radar.condicoes_contratos({"min": "1 000,50"})
        self.assertEqual(valores, [1000.5])

    def test_filtros_juntam_se_com_AND(self):
        onde, valores = radar.condicoes_contratos(
            {"adj": "Oeiras", "proc": "Consulta Prévia"})
        self.assertIn(" AND ", onde)
        self.assertEqual(len(valores), 2)

    def test_sem_filtro_nenhum_nao_produz_where_partido(self):
        # o WHERE tem de ser sempre válido: a rota concatena-o sempre
        onde, valores = radar.condicoes_contratos({})
        self.assertTrue(onde.strip().startswith("WHERE"))
        self.assertEqual(valores, [])


class TestExclusoesNoFiltro(unittest.TestCase):
    """B01: excluir palavras e CPV do filtro. Três dos quatro
    concorrentes observados têm-no (ver CONCORRENTES.md); sem isto, um
    filtro largo obrigava a descartar o mesmo ruído à mão todas as
    semanas. As armadilhas são duas: o NOT sobre NULL é NULL (a linha
    por preencher sumia-se), e a exclusão vazia não pode virar 1=0.
    """

    def test_excluir_palavra_normaliza_como_a_pesquisa(self):
        # a mesma norma da procura: "videovigilância" tem de excluir os
        # títulos escritos todos em maiúsculas com "VIDEOVIGILÂNCIA"
        onde, valores = radar.condicoes(
            {"q_excl": "videovigilância", "estado": ""})
        self.assertIn("NOT (", onde)
        self.assertIn("%videovigilancia%", valores)

    def test_excluir_nao_esconde_quem_nao_tem_o_campo(self):
        # NOT (NULL LIKE x) é NULL: sem COALESCE, excluir "obras"
        # escondia também os anúncios ainda sem título normalizado
        onde, _ = radar.condicoes({"q_excl": "obras", "estado": ""})
        self.assertIn("COALESCE", onde)
        onde, _ = radar.condicoes({"cpv_excl": "72000000", "estado": ""})
        self.assertIn("COALESCE", onde)

    def test_excluir_cpv_alarga_ao_grupo_como_o_positivo(self):
        # a mesma regra do prefixo: excluir "72000000" exclui a divisão
        onde, valores = radar.condicoes({"cpv_excl": "72000000", "estado": ""})
        self.assertIn("NOT (", onde)
        self.assertIn("72%", valores)

    def test_exclusao_sem_prefixo_nao_filtra_nada(self):
        # ao contrário do positivo (que dá 1=0), excluir nada é não
        # excluir: um "-" no campo não pode esvaziar nem esconder nada
        onde, _ = radar.condicoes({"cpv_excl": "-", "estado": ""})
        self.assertNotIn("1=0", onde)
        self.assertNotIn("NOT (", onde)

    def test_excluir_nos_contratos_usa_a_tabela_filha(self):
        onde, valores = radar.condicoes_contratos(
            {"q_excl": "limpeza", "cpv_excl": "90000000"})
        self.assertIn("NOT (", onde)
        self.assertIn("NOT IN", onde)
        self.assertIn("contrato_cpv", onde)
        self.assertIn("90*", valores)
        self.assertIn("%limpeza%", valores)

    def test_as_exclusoes_entram_no_filtro_canonico(self):
        # senão o filtro guardado com exclusão nunca se reconhecia como
        # o que está em uso
        consulta = radar.filtro_actual({"q_excl": "obras"})
        self.assertIn("q_excl=obras", consulta)

    def test_todas_as_vistas_entendem_as_exclusoes(self):
        # um filtro com exclusão não pode ficar "parcial" em página
        # nenhuma: as três sabem excluir
        for vista in ("anuncios", "contratos", "entidade"):
            with self.subTest(vista=vista):
                dentro, fora = radar.filtro_para(
                    "q_excl=obras&cpv_excl=45", vista)
                self.assertEqual(fora, [])
                self.assertIn("q_excl=obras", dentro)


class TestEOuEntrePalavrasECpv(unittest.TestCase):
    """B07: por omissão as palavras e o CPV juntam-se por E (pesquisa
    mais restrita); com op=ou, por OU (mais ampla). A armadilha é a
    ordem dos placeholders: juntar os dois fragmentos não pode baralhar
    a correspondência entre os ? do SQL e a lista de valores.
    """

    def test_por_omissao_e_E(self):
        onde, _ = radar.condicoes({"q": "software", "cpv": "72", "estado": ""})
        # duas condições separadas, unidas por AND
        self.assertIn(") AND (", onde)

    def test_op_ou_junta_as_duas(self):
        onde, valores = radar.condicoes(
            {"q": "software", "cpv": "72", "op": "ou", "estado": ""})
        self.assertIn("') OR ((cpv LIKE ?", onde)
        # os valores das palavras vêm antes dos do CPV, como no SQL
        self.assertEqual(valores[0], "%software%")
        self.assertIn("72%", valores[1:])

    def test_op_ou_so_com_um_lado_nao_muda_nada(self):
        so_q = radar.condicoes({"q": "software", "estado": ""})
        com_op = radar.condicoes({"q": "software", "op": "ou", "estado": ""})
        self.assertEqual(so_q, com_op)

    def test_op_ou_com_cpv_sem_correspondencia_fica_so_as_palavras(self):
        # no modo OU, um CPV que não corresponde a nada não acrescenta
        # nada — não pode esvaziar o lado das palavras com um 1=0
        onde, _ = radar.condicoes(
            {"q": "software", "cpv": "-", "op": "ou", "estado": ""})
        self.assertNotIn("1=0", onde)
        self.assertIn("%software%", radar.condicoes(
            {"q": "software", "cpv": "-", "op": "ou", "estado": ""})[1])

    def test_sem_op_o_cpv_sem_correspondencia_continua_a_esvaziar(self):
        # o comportamento antigo não muda: em modo E, lixo dá vazio
        onde, _ = radar.condicoes({"q": "software", "cpv": "-", "estado": ""})
        self.assertIn("1=0", onde)

    def test_nos_contratos_tambem(self):
        onde, valores = radar.condicoes_contratos(
            {"q": "limpeza", "cpv": "90910000", "op": "ou"})
        self.assertIn(" OR c.id IN (SELECT contrato_id FROM contrato_cpv",
                      onde)
        self.assertEqual(valores[0], "%limpeza%")
        self.assertIn("9091*", valores)   # zeros à direita: código -> grupo

    def test_a_ordem_dos_valores_segue_a_dos_pontos_de_interrogacao(self):
        # com op=ou e mais campos no meio, cada ? tem de casar com o seu
        onde, valores = radar.condicoes(
            {"q": "software", "ent": "camara", "cpv": "72",
             "op": "ou", "estado": ""})
        self.assertEqual(onde.count("?"), len(valores))
        # a entidade vem antes do bloco (q OR cpv) no SQL — e nos valores
        self.assertEqual(valores[0], "%camara%")
        self.assertEqual(valores[1], "%software%")

    def test_o_op_entra_na_legenda_por_palavras(self):
        saiu = radar.resumo_filtro("q=software&cpv=72&op=ou")
        self.assertIn("palavras OU CPV", saiu)
        self.assertNotIn("op ou", saiu)


class TestTermosDoTitulo(unittest.TestCase):
    """B02: os homólogos acham-se pelos termos do título no
    objecto_norm do corpus. Sem tirar o vocabulário da contratação,
    "aquisição de serviços" apanhava o corpus inteiro da entidade.
    """

    def test_tira_o_vocabulario_da_contratacao(self):
        t = radar.termos_do_titulo(
            "Aquisição de serviços de manutenção de elevadores")
        self.assertEqual(t, ["manutencao", "elevadores"])

    def test_normaliza_como_o_objecto_norm(self):
        # maiúsculas e acentos fora, como simplifica(): é com esta norma
        # que o objecto_norm do corpus está escrito
        t = radar.termos_do_titulo("VIGILÂNCIA E SEGURANÇA")
        self.assertEqual(t, ["vigilancia", "seguranca"])

    def test_numeros_soltos_e_palavras_curtas_ficam_fora(self):
        # "2026" é um ano, "gás" tem três letras: nenhum distingue nada
        t = radar.termos_do_titulo("Fornecimento de gás para 2026")
        self.assertEqual(t, [])

    def test_nao_repete_termos(self):
        t = radar.termos_do_titulo("Manutenção preventiva e manutenção correctiva")
        self.assertEqual(t.count("manutencao"), 1)

    def test_no_maximo_seis(self):
        t = radar.termos_do_titulo(
            "alfa bravo charlie delta echo foxtrot golfe hotel")
        self.assertEqual(len(t), 6)

    def test_sem_titulo_sem_termos(self):
        self.assertEqual(radar.termos_do_titulo(None), [])
        self.assertEqual(radar.termos_do_titulo(""), [])


class TestArvoreNosDoisSeparadores(unittest.TestCase):
    """A mesma árvore serve os anúncios e os contratos. O que muda é de
    onde vêm as contagens, e isso viaja no `data-de` do próprio elemento
    -- é dali que o JS lê a rota a pedir. Duas cópias do JS divergiam ao
    primeiro arranjo; contagens trocadas diziam que uma divisão está
    vazia quando tem milhares de contratos.
    """

    def test_a_fonte_vai_no_elemento(self):
        for de in ("anuncios", "contratos"):
            with self.subTest(de=de):
                self.assertIn("data-de='%s'" % de, radar.arvore_html(9454, de))

    def test_o_subtitulo_diz_o_que_se_esta_a_contar(self):
        self.assertIn("de anúncios", radar.arvore_html(9454, "anuncios"))
        self.assertIn("de contratos", radar.arvore_html(9454, "contratos"))

    def test_o_campo_que_a_arvore_escreve_e_o_mesmo_nos_dois(self):
        # arvoreAplicar() e arvoreSemear() procuram por este id; se um
        # dos separadores lhe chamasse outra coisa, ali a árvore abria
        # em branco e "Aplicar" limpava o filtro
        self.assertIn("arvoreAplicar()", radar.ARVORE_JS)
        self.assertIn("getElementById('filtro-cpv')", radar.ARVORE_JS)

    def test_ha_uma_fonte_de_contagem_por_separador(self):
        self.assertEqual(sorted(radar.FONTES_CPV), ["anuncios", "contratos"])


class TestEurosCurto(unittest.TestCase):
    """Nos gráficos, "1 661 400 000 €" não se lê de relance."""

    def test_escalas(self):
        self.assertEqual(radar.euros_curto(1661400000), "1,7 mM€")
        self.assertEqual(radar.euros_curto(35800000), "35,8 M€")
        self.assertEqual(radar.euros_curto(9500), "9,5 k€")
        self.assertEqual(radar.euros_curto(420), "420 €")

    def test_virgula_decimal_a_portuguesa(self):
        self.assertNotIn(".", radar.euros_curto(35800000))

    def test_zero_e_none_nao_rebentam(self):
        self.assertEqual(radar.euros_curto(0), "0 €")
        self.assertEqual(radar.euros_curto(None), "0 €")


class TestArvoreNaoSubmeteAoCriar(unittest.TestCase):
    """A arvore de CPV serve dois sitios com necessidades opostas.

    Numa lista, "Aplicar" e pesquisar logo. No formulario de criar um
    filtro, submeter ali mandava o formulario **antes de o nome estar
    escrito**, e escolher CPV nao dava nada -- foi o que o Afonso
    apanhou. O `data-submeter='nao'` e o que separa os dois casos.
    """

    def test_a_lista_submete(self):
        self.assertNotIn("data-submeter", radar.arvore_html(9454, "anuncios"))

    def test_o_formulario_de_criar_nao_submete(self):
        saiu = radar.arvore_html(9454, "anuncios", submeter=False)
        self.assertIn("data-submeter='nao'", saiu)

    def test_o_js_le_a_marca_do_elemento(self):
        # o JS e um so; se deixasse de ler a marca, voltava o erro
        self.assertIn("dataset.submeter", radar.ARVORE_JS)


class TestFiltroUnicoEntreVistas(unittest.TestCase):
    """Um filtro nao pertence a um separador: guarda os campos que tiver
    e cada pagina aplica os que entende. O que NAO pode acontecer e um
    campo cair em silencio -- um alerta "CPV 72 + ganho por MEO"
    aplicado aos anuncios passaria a avisar de todos os de CPV 72.
    """

    def test_campos_comuns_servem_todas_as_paginas(self):
        for vista in ("anuncios", "contratos", "entidade"):
            with self.subTest(vista=vista):
                dentro, fora = radar.filtro_para("cpv=72000000&q=obras", vista)
                self.assertEqual(fora, [])
                self.assertIn("cpv=72000000", dentro)

    def test_campo_so_dos_contratos_nao_entra_nos_anuncios(self):
        dentro, fora = radar.filtro_para("ganhou=MEO&min=50000", "anuncios")
        self.assertEqual(dentro, "")
        self.assertEqual(sorted(fora), ["ganhou", "min"])

    def test_campo_so_dos_anuncios_nao_entra_nos_contratos(self):
        dentro, fora = radar.filtro_para("estado=interessa&plat=vortal",
                                         "contratos")
        self.assertEqual(dentro, "")
        self.assertEqual(sorted(fora), ["estado", "plat"])

    def test_parte_aplica_se_e_o_resto_e_nomeado(self):
        dentro, fora = radar.filtro_para("cpv=72000000&ganhou=MEO", "anuncios")
        self.assertEqual(dentro, "cpv=72000000")
        self.assertEqual(fora, ["ganhou"])

    def test_campo_vazio_nao_conta_como_ficando_de_fora(self):
        # "ganhou=" nao filtra nada, por isso nao ha nada a avisar
        dentro, fora = radar.filtro_para("cpv=72&ganhou=", "anuncios")
        self.assertEqual(fora, [])

    def test_o_resumo_descreve_o_filtro_inteiro_sem_vista(self):
        saiu = radar.resumo_filtro("cpv=72000000&ganhou=MEO")
        self.assertIn("CPV", saiu)
        self.assertIn("ganho por MEO", saiu)


class TestResumoDosAlertas(unittest.TestCase):
    """O texto do resumo e o mesmo no e-mail e no AVISOS.txt: dois
    formatos divergiam ao primeiro arranjo."""

    class FalsoFiltro(dict):
        pass

    def anuncio(self, **k):
        base = {"ref": "1/2026", "titulo": "Aquisicao de licencas",
                "entidade": "Municipio X", "data_pub": "2026-08-01",
                "prazo": "", "preco_base": "", "cpv": ""}
        base.update(k)
        return base

    def resumo(self, anuncios):
        return radar.texto_do_resumo([({"nome": "TI"}, anuncios)])

    def test_conta_no_cabecalho(self):
        saiu = self.resumo([self.anuncio(), self.anuncio(ref="2/2026")])
        self.assertIn("2 anuncios novos", saiu)

    def test_singular(self):
        self.assertIn("1 anuncio novo", self.resumo([self.anuncio()]))

    def test_prazo_expirado_nao_diz_termina_hoje(self):
        # conta_dias() diz "termina hoje" para dias <= 0, o que num prazo
        # de ha dois meses e mentira
        saiu = self.resumo([self.anuncio(prazo="2020-01-01")])
        self.assertIn("PRAZO EXPIRADO", saiu)
        self.assertNotIn("termina hoje", saiu)

    def test_sem_prazo_diz_que_nao_ha(self):
        self.assertIn("sem prazo lido", self.resumo([self.anuncio()]))

    def test_leva_a_ligacao_para_a_ficha(self):
        saiu = self.resumo([self.anuncio(ref="123/2026")])
        self.assertIn("/anuncio/123%2F2026", saiu)


class TestDuracaoPt(unittest.TestCase):
    """Duas fronteiras, com razões simétricas. Abaixo do minuto conta em
    segundos, porque "1 min decorridos" numa volta de dez segundos punha
    em dúvida tudo o resto que a linha diz. Acima, arredonda os minutos
    PARA CIMA, porque "faltam 0 min" com meio minuto a faltar lê-se como
    se tivesse acabado."""

    def test_menos_de_uma_hora_em_minutos(self):
        self.assertEqual(radar.duracao_pt(90), "2 min")
        self.assertEqual(radar.duracao_pt(3540), "59 min")

    def test_abaixo_do_minuto_conta_em_segundos(self):
        self.assertEqual(radar.duracao_pt(1), "1s")
        self.assertEqual(radar.duracao_pt(29), "29s")
        self.assertEqual(radar.duracao_pt(59), "59s")

    def test_a_fronteira_do_minuto_troca_de_unidade_uma_vez_so(self):
        self.assertEqual(radar.duracao_pt(59), "59s")
        self.assertEqual(radar.duracao_pt(60), "1 min")
        self.assertEqual(radar.duracao_pt(61), "2 min")

    def test_arredonda_para_cima_e_nunca_esconde_tempo_a_faltar(self):
        # 59 min e 1 s arredonda a 60 min, e 60 min mostram-se como "1h":
        # o arredondamento para cima pode fazer subir de unidade
        self.assertEqual(radar.duracao_pt(3541), "1h")
        self.assertEqual(radar.duracao_pt(3601), "1h01")
        self.assertEqual(radar.duracao_pt(0), "0s")

    def test_horas_redondas_sem_minutos_pendurados(self):
        self.assertEqual(radar.duracao_pt(3600), "1h")
        self.assertEqual(radar.duracao_pt(61200), "17h")

    def test_horas_e_minutos_com_dois_digitos(self):
        # "1h3" lia-se como uma hora e trinta; os zeros são obrigatórios
        self.assertEqual(radar.duracao_pt(5400), "1h30")
        self.assertEqual(radar.duracao_pt(3780), "1h03")

    def test_negativo_e_nada_nao_estouram(self):
        self.assertEqual(radar.duracao_pt(-5), "0s")
        self.assertEqual(radar.duracao_pt(None), "0s")


class TestDetalhesEmLote(unittest.TestCase):
    """O ciclo do `--detalhes`, que enche o detalhe de toda a base --
    horas de relógio a um pedido por segundo.

    `ler_detalhes()` sai do ciclo EM SILÊNCIO quando um pedido falha de
    rede ou traz JSON ilegível: devolve menos do que o lote e aviso
    vazio. Desistir à primeira perdia a noite por causa de um segundo,
    por isso há um último recurso -- tolerar VOLTAS_VAZIAS seguidas --,
    e é ele que este teste força. A espera e a leitura são injectadas:
    um teste cujo sucesso dependa de um sleep verdadeiro é um teste
    instável que ainda não falhou.
    """

    def _correr(self, respostas, faltam, alvo=100, lote=40):
        """Corre o ciclo com `respostas` enfileiradas. `faltam` é o que
        o contador diz quando lhe perguntam."""
        chamadas, esperas, ditos = [], [], []

        def ler(n, dias=None):
            chamadas.append(n)
            return respostas.pop(0) if respostas else (0, "")

        return (radar.detalhes_em_lote(
            alvo, lote, contar=lambda: faltam, ler=ler,
            esperar=esperas.append, diz=ditos.append),
            chamadas, esperas, ditos)

    def test_corre_por_voltas_ate_ao_alvo_e_nao_pede_mais_que_isso(self):
        feitos, chamadas, esperas, _ = self._correr(
            [(40, ""), (40, ""), (20, "")], faltam=1000)
        self.assertEqual(feitos, 100)
        # a última volta pede 20, não 40: o alvo é um tecto
        self.assertEqual(chamadas, [40, 40, 20])
        self.assertEqual(esperas, [])

    def test_um_blip_de_rede_nao_para_a_corrida(self):
        # volta vazia no meio, e depois continua
        feitos, chamadas, esperas, _ = self._correr(
            [(40, ""), (0, ""), (40, ""), (20, "")], faltam=1000)
        self.assertEqual(feitos, 100)
        self.assertEqual(esperas, [radar.ESPERA_ENTRE_VAZIAS])

    def test_o_ultimo_recurso_dispara_as_tres_voltas_vazias(self):
        # nunca lê nada, mas o contador insiste que faltam: desiste ao
        # fim de VOLTAS_VAZIAS e espera entre elas -- uma vez menos que
        # as voltas, porque a última não espera, desiste
        feitos, chamadas, esperas, ditos = self._correr([], faltam=1000)
        self.assertEqual(feitos, 0)
        self.assertEqual(len(chamadas), radar.VOLTAS_VAZIAS)
        self.assertEqual(esperas,
                         [radar.ESPERA_ENTRE_VAZIAS] * (radar.VOLTAS_VAZIAS - 1))
        self.assertIn("Parado", " ".join(ditos))

    def test_o_contador_a_zero_para_logo_e_sem_esperar(self):
        # é o que distingue "acabou" de "falhou a rede": sem o contador,
        # o fim normal da fila gastava as três voltas e 60 segundos
        feitos, chamadas, esperas, ditos = self._correr([], faltam=0)
        self.assertEqual((feitos, len(chamadas), esperas), (0, 1, []))
        self.assertNotIn("Parado", " ".join(ditos))

    def test_um_aviso_do_portal_para_a_primeira(self):
        # captura recusada: bater outra vez na mesma porta não a abre
        feitos, chamadas, esperas, ditos = self._correr(
            [(5, "o DR não aceitou o detalhe")], faltam=1000)
        self.assertEqual((feitos, len(chamadas), esperas), (5, 1, []))
        self.assertIn("Parado", " ".join(ditos))

    def test_ctrl_c_devolve_o_que_ja_leu(self):
        # o trabalho está gravado anúncio a anúncio; a contagem tem de o
        # dizer em vez de estourar por cima do relatório final
        def ler(n, dias=None):
            if n == 40:
                return 40, ""
            raise KeyboardInterrupt

        ditos = []
        feitos = radar.detalhes_em_lote(100, 40, contar=lambda: 1000,
                                        ler=ler, esperar=lambda s: None,
                                        diz=ditos.append)
        self.assertEqual(feitos, 80)
        self.assertIn("Interrompido", " ".join(ditos))

    def test_o_ler_por_omissao_usa_a_concorrencia_pedida(self):
        # sem `ler` injectado, detalhes_em_lote() constroi um a partir
        # de ler_detalhes_paralelo() com a `concorrencia` recebida -- e
        # a rotina diaria (que chama ler_detalhes() sequencial
        # directamente, sem passar por aqui) fica intocada
        vistos = []

        def ler_paralelo_falso(limite, dias=None, concorrencia=8):
            vistos.append(concorrencia)
            return 0, ""

        antigo = radar.ler_detalhes_paralelo
        radar.ler_detalhes_paralelo = ler_paralelo_falso
        try:
            radar.detalhes_em_lote(40, 40, contar=lambda: 0,
                                   concorrencia=4, esperar=lambda s: None,
                                   diz=lambda t: None)
        finally:
            radar.ler_detalhes_paralelo = antigo
        self.assertEqual(vistos, [4])

    def test_a_rotina_diaria_continua_a_um_segundo_por_omissao(self):
        # o parametro novo nao pode ter mudado o valor por omissao de
        # ler_detalhes(), que e o que verificar() chama sem `intervalo`
        import inspect
        assinatura = inspect.signature(radar.ler_detalhes)
        self.assertEqual(assinatura.parameters["intervalo"].default, 1)


class TestDiferencasDoDetalhe(unittest.TestCase):
    """B05: a releitura dos marcados compara o prazo e o preço base com
    o que estava guardado. Uma prorrogação perdida é pior que nenhuma
    promessa — mas um aviso falso por o parser tropeçar num texto
    reformatado é o rapaz que gritava lobo. Só se avisa quando há valor
    dos dois lados e são diferentes.
    """

    def test_prorrogacao_de_prazo(self):
        difs = radar.diferencas_do_detalhe(
            {"prazo": "2026-09-10", "preco_base": "100,00 EUR"},
            {"prazo": "2026-09-24", "preco_base": "100,00 EUR"})
        self.assertEqual(difs, [("prazo", "2026-09-10", "2026-09-24")])

    def test_sem_mudanca_sem_aviso(self):
        difs = radar.diferencas_do_detalhe(
            {"prazo": "2026-09-10", "preco_base": ""},
            {"prazo": "2026-09-10", "preco_base": ""})
        self.assertEqual(difs, [])

    def test_campo_que_desaparece_nao_grita_lobo(self):
        # o parser a falhar parece o prazo a desaparecer; nao e alteracao
        difs = radar.diferencas_do_detalhe(
            {"prazo": "2026-09-10"}, {"prazo": ""})
        self.assertEqual(difs, [])

    def test_campo_que_aparece_tambem_nao(self):
        # detalhe enriquecido nao e o DR a mudar o anuncio
        difs = radar.diferencas_do_detalhe(
            {"prazo": ""}, {"prazo": "2026-09-10"})
        self.assertEqual(difs, [])

    def test_prazo_e_preco_juntos(self):
        difs = radar.diferencas_do_detalhe(
            {"prazo": "2026-09-10", "preco_base": "100,00 EUR"},
            {"prazo": "2026-09-24", "preco_base": "120,00 EUR"})
        self.assertEqual([c for c, _, _ in difs], ["prazo", "preco_base"])

    def test_datas_no_aviso_saem_a_portuguesa(self):
        # a regra da empresa: nunca uma data ISO num texto para ler
        self.assertEqual(radar._valor_vigiado("prazo", "2026-09-10"),
                         "10/09/2026")
        self.assertEqual(radar._valor_vigiado("preco_base", "100,00 EUR"),
                         "100,00 EUR")


class TestPadraoDeRetificacao(unittest.TestCase):
    """B05: o DR publica rectificações como anúncios NOVOS, com o
    original citado no título. O padrão tem de apanhar as quatro formas
    vistas na base — e não pode confundir 'canulação' com 'anulação',
    que foi o falso positivo da investigação."""

    def alvo(self, titulo):
        m = radar.PADRAO_RETIFICACAO.search(titulo)
        return m.group(1) if m else None

    def test_as_formas_vistas_na_base(self):
        for titulo, ref in (
            ("Retificação ao Anúncio de procedimento n.º 19900/2026, "
             "Publicado em DR", "19900/2026"),
            ("Retificação ao Anúncio de procedimento n.º 16831/2026; "
             "Publicado em DR", "16831/2026"),
            ("Requalificação da USF — 2.º Procedimento — retificação "
             "ao anúncio n.º 17682/2026", "17682/2026"),
        ):
            with self.subTest(titulo=titulo[:40]):
                self.assertEqual(self.alvo(titulo), ref)

    def test_titulo_normal_nao_e_rectificacao(self):
        self.assertIsNone(self.alvo("Aquisição de sistemas de canulação "
                                    "da via biliar - Ano 2025"))
        self.assertIsNone(self.alvo("Empreitada de Retificação do ramal "
                                    "de esgoto debaixo do prédio"))


class TestResumoComAlterados(unittest.TestCase):
    """B05: os alterados entram no resumo diário numa secção própria —
    não são novidades, são mudanças a anúncios já conhecidos."""

    def alteracao(self, **k):
        base = {"id": 1, "ref": "9/2026", "campo": "prazo",
                "antes": "2026-09-10", "depois": "2026-09-24",
                "titulo": "Aquisicao de licencas", "entidade": "Municipio X"}
        base.update(k)
        return base

    def test_seccao_dos_alterados(self):
        saiu = radar.texto_do_resumo([], [self.alteracao()])
        self.assertIn("Alterados desde a última leitura (1)", saiu)
        self.assertIn("prazo de propostas: 10/09/2026 -> 24/09/2026", saiu)
        self.assertIn("/anuncio/9%2F2026", saiu)

    def test_so_alterados_nao_diz_zero_novos(self):
        saiu = radar.texto_do_resumo([], [self.alteracao()])
        self.assertNotIn("0 anuncios novos", saiu)
        self.assertIn("1 alterado", saiu)

    def test_duas_mudancas_do_mesmo_anuncio_contam_uma_vez(self):
        saiu = radar.texto_do_resumo(
            [], [self.alteracao(), self.alteracao(id=2, campo="preco_base",
                                                  antes="1", depois="2")])
        self.assertIn("(1)", saiu)

    def test_rectificacao_diz_o_anuncio_e_nao_a_seta(self):
        saiu = radar.texto_do_resumo(
            [], [self.alteracao(campo="retificacao", antes="",
                                depois="21065/2026")])
        self.assertIn("rectificado pelo anúncio 21065/2026", saiu)
        self.assertNotIn("->", saiu.split("== Alterados")[1])

    def test_sem_alterados_o_resumo_e_o_de_sempre(self):
        saiu = radar.texto_do_resumo(
            [({"nome": "TI"}, [{"ref": "1/2026", "titulo": "t",
                                "entidade": "e", "data_pub": "2026-08-01",
                                "prazo": "", "preco_base": "", "cpv": ""}])])
        self.assertIn("1 anuncio novo", saiu)
        self.assertNotIn("Alterados", saiu)


class TestDiasUrgente(unittest.TestCase):
    """B13: a janela do urgente lê-se do config.json, mas lixo, zero ou
    negativo voltam à omissão — uma janela de 0 dias esvaziava o filtro
    em silêncio."""

    def test_config_por_cima_da_omissao(self):
        self.assertEqual(radar.dias_urgente({"dias_urgente": 5}), 5)
        self.assertEqual(radar.dias_urgente({}), radar.DIAS_URGENTE)

    def test_lixo_e_zero_voltam_a_omissao(self):
        self.assertEqual(radar.dias_urgente({"dias_urgente": "muitos"}),
                         radar.DIAS_URGENTE)
        self.assertEqual(radar.dias_urgente({"dias_urgente": 0}),
                         radar.DIAS_URGENTE)
        self.assertEqual(radar.dias_urgente({"dias_urgente": -3}),
                         radar.DIAS_URGENTE)


# A classe TestSomaPrecosBase saiu a 15/09/2026 com o que ela testava: o `soma_precos_base()` somava colunas do quadro, e o quadro saiu nesse dia


class TestPaginasDoRecorte(unittest.TestCase):
    """B12: a ficha diz de que páginas veio o recorte. As páginas saem
    das MESMAS janelas que o texto que foi ao modelo — de outro sítio
    qualquer, a fonte mentia."""

    def texto(self):
        # tres "paginas" separadas pela marca \f em linha propria, como
        # o extractor as poe; o titulo com ancora esta na segunda
        pag1 = "clausulas de rotina\n" * 5
        pag2 = "1. Objecto do contrato\ncorpo do objecto aqui\n" + "x\n" * 5
        pag3 = "mais rotina\n" * 5
        return "\n\f\n".join((pag1, pag2, pag3))

    def test_da_as_paginas_da_janela(self):
        paginas = radar.paginas_do_recorte(
            self.texto(), ((1, r"objec?to"),), tecto=4000, janela=30)
        # a janela recua 200 antes do titulo, por isso apanha a pag. 1
        self.assertIn(2, paginas)
        self.assertEqual(paginas, sorted(paginas))

    def test_sem_marcas_nao_inventa(self):
        # texto extraido antes das marcas: nao ha paginas para declarar
        paginas = radar.paginas_do_recorte(
            "1. Objecto\ncorpo", ((1, r"objec?to"),), tecto=4000)
        self.assertEqual(paginas, [])

    def test_o_recorte_em_si_nao_mudou(self):
        # a refactoracao nao pode ter mudado o texto que vai ao modelo
        saiu = radar.recorte_relevante(
            self.texto(), ((1, r"objec?to"),), tecto=4000, janela=30)
        self.assertIn("1. Objecto do contrato", saiu)

    def test_rotulo_comprime_intervalos(self):
        self.assertEqual(radar.rotulo_com_paginas("CE.pdf", [2, 3, 4, 7]),
                         "CE.pdf (pág. 2–4, 7)")
        self.assertEqual(radar.rotulo_com_paginas("CE.pdf", [5]),
                         "CE.pdf (pág. 5)")
        self.assertEqual(radar.rotulo_com_paginas("CE.pdf", []), "CE.pdf")


class TestPesquisaNasPecasRetirada(unittest.TestCase):
    """B09, implementado e RETIRADO a 30/08/2026 por decisão do Afonso:
    as peças só existem depois de marcar "interessa", por isso a
    pesquisa chegava sempre tarde demais para ajudar a decidir. Este
    teste impede o regresso acidental — a versão que valeria a pena
    (ver o PDF dentro da aplicação, com pesquisa) está no BACKLOG e
    faz-se só quando for pedida."""

    def test_a_lista_nao_filtra_pelas_pecas(self):
        onde, _ = radar.condicoes({"q_pecas": "penalidades", "estado": ""})
        self.assertNotIn("pecas_fts", onde)
        self.assertNotIn("q_pecas", radar.CAMPOS_FILTRO)

    def test_o_motor_da_pesquisa_saiu_todo(self):
        # meio motor esquecido convidava a "só ligar outra vez"
        for nome in ("pesquisa_nas_pecas", "excerto_de", "termos_fts",
                     "ha_fts"):
            self.assertFalse(hasattr(radar, nome), nome)


class TestLeiturasConfiguraveis(unittest.TestCase):
    """B08: as âncoras e a instrução de cada leitura afinam-se no
    config.json sem mexer no código. Uma entrada estragada nunca pode
    desligar uma leitura em silêncio — fica a de origem.
    """

    def test_sem_config_ficam_as_de_origem(self):
        self.assertEqual(radar.leituras_activas({}), list(radar.LEITURAS))
        self.assertEqual(radar.leituras_activas({"leituras": {}}),
                         list(radar.LEITURAS))

    def test_instrucao_substitui_se(self):
        cfg = {"leituras": {"objecto": {"instrucao": "pergunta nova"}}}
        saiu = dict((n, i) for n, _, _, i in radar.leituras_activas(cfg))
        self.assertEqual(saiu["objecto"], "pergunta nova")
        self.assertEqual(saiu["equipa"], radar.INSTRUCOES_EQUIPA)

    def test_ancoras_validas_substituem(self):
        cfg = {"leituras": {"equipa": {"ancoras": [[1, "alvara"],
                                                   [2, "certificacao"]]}}}
        saiu = {n: a for n, _, a, _ in radar.leituras_activas(cfg)}
        self.assertEqual(saiu["equipa"], ((1, "alvara"), (2, "certificacao")))

    def test_regex_estragado_fica_a_origem(self):
        # "[" nao compila; calar a leitura por causa disso era pior que
        # ignorar o config
        cfg = {"leituras": {"equipa": {"ancoras": [[1, "["]]}}}
        saiu = {n: a for n, _, a, _ in radar.leituras_activas(cfg)}
        self.assertEqual(saiu["equipa"], radar.ANCORAS_EQUIPA)

    def test_quais_so_dos_conhecidos(self):
        cfg = {"leituras": {"objecto": {"quais": "propostas"}}}
        saiu = {n: q for n, q, _, _ in radar.leituras_activas(cfg)}
        self.assertEqual(saiu["objecto"], "encargos")

    def test_campo_novo_nao_entra(self):
        # a tabela analise tem colunas fixas; um 4.º campo fica para
        # quando o caso de uso aparecer
        cfg = {"leituras": {"alvara": {"quais": "programa",
                                       "instrucao": "que alvará exige?"}}}
        self.assertEqual([n for n, _, _, _ in radar.leituras_activas(cfg)],
                         ["objecto", "equipa", "proposta"])


class TestResumoComSeguidas(unittest.TestCase):
    """B10: o que as entidades seguidas publicaram vai numa secção
    própria do resumo — não é um alerta, é outra pergunta."""

    def seguidas(self):
        return [("500498601", "CP - Comboios de Portugal",
                 [{"ref": "5/2026", "titulo": "Reparação de motores",
                   "entidade": "CP", "data_pub": "2026-08-29",
                   "prazo": "", "preco_base": ""}])]

    def test_seccao_das_seguidas(self):
        saiu = radar.texto_do_resumo([], (), self.seguidas())
        self.assertIn("Das entidades que segues (1)", saiu)
        self.assertIn("CP - Comboios de Portugal (1)", saiu)
        self.assertIn("/anuncio/5%2F2026", saiu)

    def test_cabecalho_conta_as_seguidas_sem_zero_novos(self):
        saiu = radar.texto_do_resumo([], (), self.seguidas())
        self.assertIn("1 das entidades seguidas", saiu)
        self.assertNotIn("0 anuncios novos", saiu)


class TestEnvioSemConfiguracao(unittest.TestCase):
    """Cada falha de envio tem de dizer o que e: "nao funciona" nao
    chega para se saber o que preencher."""

    def test_sem_nada_configurado(self):
        bem, porque = radar.enviar_email("x", "y", {"email": {}})
        self.assertFalse(bem)
        self.assertIn("por configurar", porque)

    def test_com_destino_mas_sem_conta_que_envia(self):
        bem, porque = radar.enviar_email("x", "y", {"email": {"para": "a@b.pt"}})
        self.assertFalse(bem)
        self.assertIn("por configurar", porque)


class TestResumoEmHtml(unittest.TestCase):
    """O e-mail sai em duas partes (02/09/2026): o texto de sempre e um
    HTML "bonito". O HTML tem de dizer o mesmo que o texto -- as
    mesmas seccoes, as mesmas contagens, as mesmas ligacoes -- senao
    voltavamos a ter dois resumos a divergir ao primeiro arranjo, que
    foi a razao de haver um so formato. E tudo o que vem da base passa
    por html.escape: um titulo com '&' ou '<' nao pode partir o e-mail."""

    def anuncio(self, **k):
        base = {"ref": "1/2026", "titulo": "Aquisicao de licencas",
                "entidade": "Municipio X", "data_pub": "2026-08-01",
                "prazo": "", "preco_base": "", "cpv": ""}
        base.update(k)
        return base

    def alteracao(self, **k):
        base = {"id": 1, "ref": "9/2026", "campo": "prazo",
                "antes": "2026-09-10", "depois": "2026-09-24",
                "titulo": "Aquisicao de licencas", "entidade": "Municipio X"}
        base.update(k)
        return base

    def seguidas(self):
        return [("500498601", "CP - Comboios de Portugal",
                 [{"ref": "5/2026", "titulo": "Reparação de motores",
                   "entidade": "CP", "data_pub": "2026-08-29",
                   "prazo": "", "preco_base": ""}])]

    def test_e_um_documento_html_com_o_cabecalho_do_texto(self):
        saiu = radar.html_do_resumo([({"nome": "TI"}, [self.anuncio(),
                                                      self.anuncio(ref="2/2026")])])
        self.assertTrue(saiu.startswith("<!DOCTYPE html>"))
        self.assertIn("2 anúncios novos nos teus alertas", saiu)
        self.assertIn("TI <span", saiu)

    def test_a_ligacao_para_a_ficha_e_um_href(self):
        saiu = radar.html_do_resumo([({"nome": "TI"},
                                      [self.anuncio(ref="123/2026")])])
        # pelo IP, não por "localhost": neste Windows o `localhost`
        # resolve primeiro para ::1, onde ninguém atende, e a ligação
        # bloqueia até desistir — 208 ms contra 37 ms, medido a
        # 04/09/2026. O endereço vem de `endereco_do_painel()`, para o
        # teste continuar a valer se a porta mudar -- e desde 8/09/2026
        # o config.json verdadeiro tem `endereco_publico` (radargov.pt),
        # que é o que o e-mail passa a levar.
        self.assertIn('href="%s/anuncio/123%%2F2026"' % radar.endereco_do_painel(), saiu)
        self.assertNotIn("localhost", saiu)

    def test_escapa_o_que_vem_da_base(self):
        saiu = radar.html_do_resumo([({"nome": "A & B"}, [self.anuncio(
            titulo="Suporte <urgente> & manutenção",
            entidade="Ramos & Filhos")])])
        self.assertNotIn("<urgente>", saiu)
        self.assertIn("Suporte &lt;urgente&gt; &amp; manutenção", saiu)
        self.assertIn("Ramos &amp; Filhos", saiu)
        self.assertIn("A &amp; B", saiu)

    def test_o_titulo_vai_inteiro(self):
        # No texto corta-se aos 88; no e-mail "(SaaS" a meio era a
        # primeira coisa que se via
        titulo = "Subscrição de licenças de software Autodesk na modalidade " \
                 "de Software-as-a-Service (SaaS) para a frota"
        saiu = radar.html_do_resumo([({"nome": "TI"},
                                      [self.anuncio(titulo=titulo)])])
        self.assertIn(html.escape(titulo), saiu)

    def test_prazo_expirado_e_sem_prazo_dizem_o_que_sao(self):
        saiu = radar.html_do_resumo([({"nome": "TI"}, [
            self.anuncio(prazo="2020-01-01"), self.anuncio(ref="2/2026")])])
        self.assertIn("prazo expirado", saiu)
        self.assertIn("propostas até 01/01/2020", saiu)
        self.assertIn("sem prazo lido", saiu)
        self.assertNotIn("termina hoje", saiu)

    def test_prazo_aberto_leva_a_cor_da_janela_do_urgente(self):
        # A pilula do e-mail vem de etiqueta_prazo(), com a janela de
        # dias_urgente(): o mesmo prazo nao pode ser laranja na lista e
        # verde no e-mail
        dentro = (datetime.date.today() + datetime.timedelta(days=2)).isoformat()
        fora = (datetime.date.today() + datetime.timedelta(days=radar.dias_urgente() + 30)
                ).isoformat()
        saiu = radar.html_do_resumo([({"nome": "TI"}, [
            self.anuncio(prazo=dentro), self.anuncio(ref="2/2026", prazo=fora)])])
        laranja, verde = radar._EM_CORES["avisa"][1], radar._EM_CORES["ok"][1]
        self.assertIn(laranja, saiu)
        self.assertIn(verde, saiu)

    def test_alterados_com_o_antes_riscado_e_o_depois_a_negrito(self):
        saiu = radar.html_do_resumo([], [self.alteracao(), self.alteracao(
            id=2, campo="retificacao", antes="", depois="21065/2026")])
        self.assertIn("Alterados desde a última leitura", saiu)
        self.assertIn("<s style", saiu)
        self.assertIn("10/09/2026</s> &rarr; <b>24/09/2026</b>", saiu)
        self.assertIn("rectificado pelo anúncio <b>21065/2026</b>", saiu)
        self.assertIn("1 alterado", saiu)
        self.assertNotIn("0 anúncios novos", saiu)

    def test_seguidas_com_a_data_de_publicacao(self):
        saiu = radar.html_do_resumo([], (), self.seguidas())
        self.assertIn("Das entidades que segues", saiu)
        self.assertIn("CP - Comboios de Portugal", saiu)
        self.assertIn("publicado 29/08/2026", saiu)
        self.assertIn("/anuncio/5%2F2026", saiu)

    def test_diz_o_mesmo_que_o_texto(self):
        # As mesmas ligacoes, na mesma ordem: e o teste que segura os
        # dois formatos juntos
        achados = [({"nome": "TI"}, [self.anuncio(), self.anuncio(ref="2/2026")]),
                   ({"nome": "Obras"}, [self.anuncio(ref="3/2026")])]
        texto = radar.texto_do_resumo(achados, [self.alteracao()], self.seguidas())
        em_html = radar.html_do_resumo(achados, [self.alteracao()], self.seguidas())
        ligacoes = re.compile(r"http://localhost:\d+/anuncio/[^\s\"<]+")
        self.assertEqual(ligacoes.findall(texto), ligacoes.findall(em_html))


class TestEnvioComHtml(unittest.TestCase):
    """A mensagem vai em multipart/alternative: o texto primeiro e o
    HTML depois, para o cliente que nao le HTML ver o texto. Sem o
    HTML, a mensagem e a de sempre, so texto."""

    def apanhar(self, html_corpo):
        from unittest import mock
        apanhado = {}

        class FalsoSMTP:
            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def starttls(self):
                pass

            def login(self, *a):
                pass

            def send_message(self, msg):
                apanhado["msg"] = msg

        cfg = {"email": {"para": "a@b.pt", "de": "c@d.pt",
                         "servidor": "smtp.x", "porta": 587}}
        with mock.patch.object(radar.smtplib, "SMTP", FalsoSMTP), \
                mock.patch.object(radar, "ler_chave", lambda *a, **k: "s"):
            bem, porque = radar.enviar_email("Assunto", "texto simples", cfg,
                                             html_corpo)
        self.assertTrue(bem, porque)
        return apanhado["msg"]

    def test_com_html_vai_em_duas_partes(self):
        msg = self.apanhar("<p>bonito</p>")
        self.assertEqual(msg.get_content_type(), "multipart/alternative")
        tipos = [p.get_content_type() for p in msg.iter_parts()]
        self.assertEqual(tipos, ["text/plain", "text/html"])
        self.assertIn("texto simples", msg.get_body(("plain",)).get_content())
        self.assertIn("bonito", msg.get_body(("html",)).get_content())

    def test_sem_html_e_so_texto(self):
        msg = self.apanhar(None)
        self.assertEqual(msg.get_content_type(), "text/plain")


class TestEurosDoTexto(unittest.TestCase):
    """O DR escreve "175.000,00 EUR": o ponto separa os milhares e a
    virgula os centimos, ao contrario do que o float() de Python le. Ler
    isto ingenuamente dava 175,0 em vez de 175 000 -- e a comparacao com
    o mercado dizia o contrario do que devia.
    """

    def test_formato_portugues(self):
        self.assertEqual(radar.euros_do_texto("175.000,00 EUR"), 175000.0)
        self.assertEqual(radar.euros_do_texto("1.234.567,89 EUR"), 1234567.89)

    def test_sem_milhares(self):
        self.assertEqual(radar.euros_do_texto("500,00 EUR"), 500.0)

    def test_sem_numero_nenhum(self):
        self.assertIsNone(radar.euros_do_texto(""))
        self.assertIsNone(radar.euros_do_texto(None))
        self.assertIsNone(radar.euros_do_texto("a combinar"))


class TestDataPortuguesa(unittest.TestCase):
    """Guarda-se ISO porque ordena como texto, mostra-se DD/MM/AAAA porque
    e assim que se le. Havia tabelas a mostrar uma coisa e outras a
    mostrar a outra."""

    def test_converte(self):
        self.assertEqual(radar.data_pt("2026-08-21"), "21/08/2026")

    def test_data_com_hora_tambem(self):
        self.assertEqual(radar.data_pt("2026-08-21 14:30"), "21/08/2026")

    def test_vazio_da_o_tracinho(self):
        self.assertEqual(radar.data_pt(""), "—")
        self.assertEqual(radar.data_pt(None), "—")

    def test_vazio_pode_ser_outra_coisa(self):
        self.assertEqual(radar.data_pt("", ""), "")

    def test_lixo_passa_a_letra_em_vez_de_rebentar(self):
        # o DR ja escreveu datas que nao sao datas; melhor mostrar o que
        # la esta do que deitar a pagina abaixo
        self.assertEqual(radar.data_pt("sem data"), "sem data")


class TestEspacoInquebravel(unittest.TestCase):
    """Os milhares separam-se com espaco inquebravel (U+00A0), nao com um
    espaco normal: com espaco normal o browser parte "1 363 300" ao fim
    da linha e fica meio numero em cada uma. Os tres formatadores tem de
    concordar -- o cabecalho usava um e o resto do painel o outro.
    """

    def test_os_tres_usam_o_inquebravel(self):
        for saiu in (radar.mil_pt(1363300), radar.euros(1234567),
                     radar.euros_curto(35800000)):
            with self.subTest(saiu=saiu):
                self.assertIn(" ", saiu)
                self.assertNotIn(" ", saiu)


class TestTrimestre(unittest.TestCase):
    """Tem de dar exactamente o mesmo texto que o SQL do resumo produz,
    senão o trimestre a decorrer nunca se reconhecia e a barra parcial
    aparecia como uma queda a pique."""

    def test_fronteiras(self):
        for mes, esperado in ((1, "T1"), (3, "T1"), (4, "T2"), (6, "T2"),
                              (7, "T3"), (9, "T3"), (10, "T4"), (12, "T4")):
            with self.subTest(mes=mes):
                self.assertEqual(radar.trimestre_de(datetime.date(2026, mes, 1)),
                                 "2026 " + esperado)


class TestBarras(unittest.TestCase):
    """As barras são divs dimensionados no servidor -- sem biblioteca,
    como o resto do painel."""

    def linhas(self):
        return [{"n": "A", "v": 100.0, "k": 3}, {"n": "B", "v": 25.0, "k": 1}]

    def test_a_maior_enche_e_as_outras_sao_relativas(self):
        saiu = radar.barras_h(self.linhas(), "Quem ganha")
        self.assertIn("width:100.0%", saiu)
        self.assertIn("width:25.0%", saiu)

    def test_singular_e_plural_dos_contratos(self):
        saiu = radar.barras_h(self.linhas(), "Quem ganha")
        self.assertIn("3 contratos", saiu)
        self.assertIn("1 contrato<", saiu)

    def test_sem_dados_nao_desenha_caixa_vazia(self):
        self.assertEqual(radar.barras_h([], "Quem ganha"), "")
        self.assertEqual(radar.barras_v([], "Evolução"), "")

    def test_o_periodo_a_decorrer_vai_marcado(self):
        # sem isto, o trimestre corrente parecia uma queda a pique e a
        # conclusão que se tirava dali ("este mercado secou") era falsa
        trim = [{"t": "2026 T2", "v": 200.0, "k": 9},
                {"t": "2026 T3", "v": 60.0, "k": 2}]
        saiu = radar.barras_v(trim, "Evolução", parcial="2026 T3")
        self.assertIn("col parcial", saiu)
        self.assertIn("trimestre a decorrer", saiu)
        # e só esse: o anterior está completo
        self.assertEqual(saiu.count("col parcial"), 1)

    def test_barra_minima_para_o_periodo_nao_desaparecer(self):
        # um trimestre com 0,1% do maior desenhava uma barra invisível e
        # parecia que o período não existia
        trim = [{"t": "A", "v": 1000.0, "k": 1}, {"t": "B", "v": 0.5, "k": 1}]
        self.assertIn("height:2.0%", radar.barras_v(trim, "x"))


class TestEscaloes(unittest.TestCase):
    """"Há aqui contratos do meu tamanho?" -- lê-se melhor na distribuição
    do que num número solto, e ordenar 400 mil preços para tirar a mediana
    exacta levava 953 ms. A mediana sai do escalão onde a contagem
    acumulada passa metade.
    """

    def escaloes(self, contagens):
        return [{"e": i, "k": k, "v": float(k * 1000)}
                for i, k in enumerate(contagens) if k]

    def test_a_mediana_e_o_escalao_que_passa_metade(self):
        # 10 + 10 = 20 de 40; a metade cai no segundo escalão
        saiu = radar.escaloes_html(self.escaloes([10, 10, 10, 10, 0, 0]))
        self.assertIn("Metade fica em <b>%s</b>" % radar.ESCALOES[1], saiu)

    def test_a_maioria_no_primeiro_escalao_puxa_a_mediana_para_la(self):
        saiu = radar.escaloes_html(self.escaloes([90, 5, 5, 0, 0, 0]))
        self.assertIn("Metade fica em <b>%s</b>"
                      % radar.ESCALOES[0].replace("<", "&lt;"), saiu)

    def test_as_etiquetas_e_o_sql_tem_a_mesma_escada(self):
        # os limites vivem em dois sítios (um é CASE, o outro é texto);
        # mudar um sem o outro dava barras com etiquetas erradas
        self.assertEqual(len(radar.ESCALOES), len(radar.LIMITES_ESCALAO) + 1)
        self.assertEqual(sorted(radar.LIMITES_ESCALAO),
                         list(radar.LIMITES_ESCALAO))

    def test_escaloes_em_falta_nao_rebentam(self):
        # o SQL só devolve os escalões com contratos; os vazios faltam
        saiu = radar.escaloes_html([{"e": 5, "k": 3, "v": 9e6}])
        self.assertIn("&gt; 1 M€", saiu)

    def test_desenha_os_seis_escaloes_mesmo_os_vazios(self):
        # um buraco no meio diz alguma coisa: escondê-lo mentia sobre a
        # forma da distribuição
        saiu = radar.escaloes_html(self.escaloes([5, 0, 0, 0, 0, 5]))
        for etiqueta in radar.ESCALOES:
            with self.subTest(etiqueta=etiqueta):
                self.assertIn(etiqueta.replace("<", "&lt;").replace(">", "&gt;"),
                              saiu)

    def test_sem_dados_nao_desenha(self):
        self.assertEqual(radar.escaloes_html([]), "")


class TestConcentracao(unittest.TestCase):
    """Diz se vale a pena entrar: um mercado onde cinco empresas levam
    quatro quintos joga-se de outra maneira, ou não se joga."""

    def ganha(self, valores, total=None, quantas=50):
        total = total if total is not None else sum(valores)
        return [{"n": "E%d" % i, "v": v, "k": 1,
                 "total": total, "quantas": quantas}
                for i, v in enumerate(valores)]

    def test_quota_dos_cinco_maiores(self):
        # 5 x 16 = 80 de 100
        saiu = radar.concentracao_html(self.ganha([16] * 5, total=100.0))
        self.assertIn(">80%<", saiu)

    def test_as_fatias_incluem_o_resto_do_mercado(self):
        saiu = radar.concentracao_html(self.ganha([10] * 5, total=100.0))
        self.assertIn("as outras 45 empresas", saiu)

    def test_sem_resto_nao_inventa_fatia(self):
        # cinco empresas e mais nada: não há "outras"
        saiu = radar.concentracao_html(self.ganha([20] * 5, total=100.0, quantas=5))
        self.assertNotIn("as outras", saiu)

    def test_total_zero_nao_divide_por_zero(self):
        self.assertEqual(radar.concentracao_html(self.ganha([0], total=0.0)), "")
        self.assertEqual(radar.concentracao_html([]), "")


class TestDestaqueNasBarras(unittest.TestCase):
    """O realce da mediana e o tracejado do período a decorrer são coisas
    diferentes e não se podem trocar."""

    def linhas(self):
        return [{"t": "A", "v": 10.0, "k": 1}, {"t": "B", "v": 20.0, "k": 2}]

    def test_destaque_marca_so_a_barra_pedida(self):
        saiu = radar.barras_v(self.linhas(), "x", destaque="B")
        self.assertEqual(saiu.count("col destaque"), 1)
        self.assertIn("cai a mediana", saiu)

    def test_destaque_e_parcial_nao_se_confundem(self):
        saiu = radar.barras_v(self.linhas(), "x", parcial="A", destaque="B")
        self.assertIn("col parcial", saiu)
        self.assertIn("col destaque", saiu)
        self.assertIn("trimestre a decorrer", saiu)

    def test_sem_nenhum_dos_dois_nao_marca_nada(self):
        saiu = radar.barras_v(self.linhas(), "x")
        self.assertNotIn("parcial", saiu)
        self.assertNotIn("destaque", saiu)

    def test_formatador_proprio_para_contagens(self):
        # os escalões contam contratos, não euros
        saiu = radar.barras_v([{"t": "A", "v": 64313.0, "k": 64313}], "x",
                              fmt=radar.mil_pt_f)
        self.assertIn("64 313", saiu)
        self.assertNotIn("€", saiu)


class TestNipcDoAnuncio(unittest.TestCase):
    """O DR publica o NIPC da entidade adjudicante em praticamente todos
    os anúncios -- medido, 99,3% dos que têm detalhe lido -- e é o mesmo
    número por que o BASE a identifica. Ligar por aí é exacto; ligar pelo
    nome falhava em 6% (sub-unidades e "EPE" contra "E. P. E.").
    """

    def campos(self, texto):
        return radar.campos_do_detalhe(texto)

    def test_le_o_nipc_da_chave_numerada(self):
        texto = ("1 - Entidade adjudicante\n"
                 "Designação: Município X\n"
                 "NIPC: 501073655\n")
        self.assertEqual(self.campos(texto)["nif"], "501073655")

    def test_le_o_nipc_mesmo_fora_das_chaves(self):
        # ha anúncios em que vem colado ao nome, fora das secções
        texto = "Município de Viseu (NIPC 506697320) faz saber que..."
        self.assertEqual(self.campos(texto)["nif"], "506697320")

    def test_sem_nipc_fica_vazio_e_nao_rebenta(self):
        self.assertEqual(self.campos("Anúncio sem número fiscal")["nif"], "")
        self.assertEqual(self.campos("")["nif"], "")

    def test_nao_apanha_numeros_que_nao_sao_nipc(self):
        # um preço de nove dígitos não é um NIPC
        texto = "Preço base: 123456789 EUR\nPrazo: 30 dias"
        self.assertEqual(self.campos(texto)["nif"], "")


class TestChaveDeEntidade(unittest.TestCase):
    """**O nome não é a identidade.** Medido no corpus: a Universidade do
    Porto aparece com 87 nomes (faculdades e serviços) e a MEO com 81,
    todos com o mesmo NIF. Agrupar por nome partia uma entidade em
    dezenas e nenhuma das partes chegava ao topo dos gráficos.
    """

    def test_o_nif_manda_quando_existe(self):
        self.assertEqual(radar.chave_entidade("501413197", "Universidade do Porto"),
                         "501413197")

    def test_o_mesmo_nif_com_nomes_diferentes_da_a_mesma_chave(self):
        a = radar.chave_entidade("501413197", "Universidade do Porto")
        b = radar.chave_entidade("501413197", "UP - Faculdade de Arquitetura")
        self.assertEqual(a, b)

    def test_sem_nif_cai_no_nome_normalizado(self):
        # pessoas singulares: 11% das linhas, 5% do valor
        ch = radar.chave_entidade("", "Filomena Guimarães Ferreira")
        self.assertEqual(ch, "n:filomena guimaraes ferreira")

    def test_a_chave_por_nome_nunca_colide_com_um_nif(self):
        # sem o prefixo, alguém chamado "123456789" colidia com esse NIF
        self.assertTrue(radar.chave_entidade("", "123456789").startswith("n:"))

    def test_nif_mal_formado_nao_passa_por_nif(self):
        for mau in ("-", "12345", "1234567890", "abc123456"):
            with self.subTest(mau=mau):
                self.assertTrue(radar.chave_entidade(mau, "X").startswith("n:"))


class TestNifENomeComTraco(unittest.TestCase):
    """Quando o NIF não é público o BASE escreve um traço no lugar dele.
    Sem o tirar, o nome ficava com o "- - " colado e aparecia assim no
    painel."""

    def test_traco_no_lugar_do_nif(self):
        self.assertEqual(radar._nif_e_nome(["- - Filomena Ferreira"]),
                         ("", "Filomena Ferreira"))

    def test_nif_a_serio_continua_a_separar_se(self):
        self.assertEqual(radar._nif_e_nome(["504615947 - MEO, S.A."]),
                         ("504615947", "MEO, S.A."))

    def test_nome_que_comeca_por_traco_a_serio_nao_e_comido(self):
        # um traço só não é o padrão do NIF em falta, que são dois
        self.assertEqual(radar._nif_e_nome(["- Alguma coisa"])[1],
                         "- Alguma coisa")


class TestFiltroPorEntidade(unittest.TestCase):
    """Os atalhos da ficha filtram por entidade e não por nome: contado
    por NIF, o número da ficha era maior do que o que a lista mostrava
    ao filtrar pelo nome."""

    def test_adjudicante_por_chave(self):
        onde, valores = radar.condicoes_contratos({"entid": "501413197"})
        self.assertIn("c.adjudicante_chave = ?", onde)
        self.assertIn("501413197", valores)

    def test_vencedor_por_chave_sem_join(self):
        onde, valores = radar.condicoes_contratos({"vencid": "504615947"})
        self.assertNotIn("JOIN", onde.upper())
        self.assertIn("chave=?", onde)
        self.assertIn("504615947", valores)

    def test_os_dois_ao_mesmo_tempo(self):
        # "o que a MEO ganhou à Universidade do Porto"
        onde, valores = radar.condicoes_contratos(
            {"entid": "501413197", "vencid": "504615947"})
        self.assertEqual(len(valores), 2)
        self.assertIn(" AND ", onde)

    def test_nao_se_chamam_ent_nem_venc(self):
        # nos anúncios o `ent` é a caixa de texto da entidade; dois campos
        # com o mesmo nome e sentidos diferentes eram um erro à espera de
        # acontecer, e por isso o `ent` aqui não pode filtrar nada
        _, valores = radar.condicoes_contratos({"ent": "501413197",
                                                "venc": "504615947"})
        self.assertEqual(valores, [])


class TestFiltrosGuardadosNasDuasVistas(unittest.TestCase):
    """Os contratos passaram a ter filtros guardados próprios. As listas
    têm campos diferentes -- um anúncio não tem vencedor nem valor final
    -- por isso cada vista tem a sua lista de campos, e o mesmo nome
    ("Software") pode servir nas duas.
    """

    def test_cada_pagina_sabe_os_seus_campos(self):
        # (o ROTA_DA_VISTA saiu a 15/09/2026 com os filtros guardados,
        # que morreram a 13/09: era o mapa que levava um filtro à página
        # dele, e deixou de haver filtros para levar)
        self.assertNotEqual(radar.campos_da_vista("anuncios"),
                            radar.campos_da_vista("contratos"))

    def test_todos_os_campos_das_paginas_existem_no_filtro(self):
        # um campo que uma página use e o filtro não conheça nunca se
        # guardava, e o filtro guardado saía diferente do que estava
        for vista in radar.CAMPOS_POR_VISTA:
            for campo in radar.campos_da_vista(vista):
                with self.subTest(vista=vista, campo=campo):
                    self.assertIn(campo, radar.CAMPOS_FILTRO)

    def test_o_filtro_de_contratos_nao_leva_estado(self):
        # "estado" é a triagem dos anúncios; um contrato assinado não tem
        consulta = radar.filtro_actual({"q": "software"}, "contratos")
        self.assertEqual(consulta, "q=software")

    def test_o_filtro_de_anuncios_continua_a_levar_estado_sempre(self):
        self.assertEqual(radar.filtro_actual({"q": "software"}, "anuncios"),
                         "q=software&estado=porver")

    def test_campos_so_dos_contratos(self):
        consulta = radar.filtro_actual(
            {"ganhou": "MEO", "min": "50000", "proc": "Consulta Prévia"},
            "contratos")
        for pedaco in ("ganhou=MEO", "min=50000", "proc=Consulta"):
            with self.subTest(pedaco=pedaco):
                self.assertIn(pedaco, consulta)

    def test_ordem_fixa_tambem_nos_contratos(self):
        # é ela que deixa reconhecer o filtro em uso por igualdade de texto
        um = radar.filtro_actual({"min": "1000", "q": "obras"}, "contratos")
        outro = radar.filtro_actual({"q": "obras", "min": "1000"}, "contratos")
        self.assertEqual(um, outro)

    def test_a_pagina_fica_de_fora_nas_duas(self):
        for vista in ("anuncios", "contratos"):
            with self.subTest(vista=vista):
                self.assertNotIn("pag", radar.filtro_actual(
                    {"q": "x", "pag": "4"}, vista))

    def test_resumo_le_os_campos_da_vista_certa(self):
        self.assertIn("ganho por MEO",
                      radar.resumo_filtro("ganhou=MEO", "contratos"))

    def test_rota_de_fora_nao_manda_para_qualquer_lado(self):
        # a rota de volta vem de um campo escondido do formulário
        for mau in ("", None, "http://outro.site", "//outro.site", "javascript:x"):
            with self.subTest(mau=mau):
                self.assertEqual(radar.volta_para(mau).headers["Location"], "/")
        self.assertTrue(radar.volta_para("/contratos")
                        .headers["Location"].startswith("/contratos"))


class TestPerguntaAntesDaLista(unittest.TestCase):
    """Nos contratos a pergunta vem primeiro: sem filtro não se mostra
    lista nenhuma. São 1,36 milhões de contratos e por data não dizem nada
    -- e era essa consulta que punha a página a 48 segundos.

    A regra é "algum dos campos do filtro tem valor", e é por isso que
    tem de ser exactamente a lista da vista: um campo novo que fique de
    fora não acordava a lista, e o filtro parecia não funcionar.
    """

    def ha_pergunta(self, args):
        # a mesma condição da rota /contratos
        return any((args.get(campo) or "").strip()
                   for campo in radar.campos_da_vista("contratos"))

    def test_sem_nada_nao_ha_pergunta(self):
        self.assertFalse(self.ha_pergunta({}))
        self.assertFalse(self.ha_pergunta({"pag": "3", "aviso": "x"}))

    def test_campos_vazios_nao_contam(self):
        self.assertFalse(self.ha_pergunta({"q": "", "cpv": "  ", "min": ""}))

    def test_qualquer_campo_do_filtro_acorda_a_lista(self):
        for campo in radar.campos_da_vista("contratos"):
            with self.subTest(campo=campo):
                self.assertTrue(self.ha_pergunta({campo: "x"}))


class TestActualizacaoPresa(unittest.TestCase):
    """Se o painel fechar a meio de uma actualização, a marca fica gravada
    como "a correr" para sempre e o botão nunca mais voltava -- a thread
    que a limpa vive no processo que morreu. O trinco é a verdade; a
    marca só serve para mostrar o passo em que ia.
    """

    def test_trinco_livre_quer_dizer_que_nao_corre(self):
        self.assertFalse(radar.actualizacao_a_correr())

    def test_trinco_preso_quer_dizer_que_corre(self):
        radar._ACTUALIZAR.acquire()
        try:
            self.assertTrue(radar.actualizacao_a_correr())
        finally:
            radar._ACTUALIZAR.release()

    def test_perguntar_nao_fica_com_o_trinco(self):
        # se a pergunta ficasse com ele, uma visita à página impedia a
        # actualização seguinte
        radar.actualizacao_a_correr()
        radar.actualizacao_a_correr()
        self.assertTrue(radar._ACTUALIZAR.acquire(blocking=False))
        radar._ACTUALIZAR.release()


class TestColunasDoImportador(unittest.TestCase):
    """As colunas do INSERT saem de uma lista só. Duas vezes se
    acrescentou uma coluna à tabela e o VALUES posicional partiu -- a
    segunda a meio de uma importação de sete anos.
    """

    def test_as_interrogacoes_saem_do_numero_de_colunas(self):
        vistas = []

        class FalsaLigacao:
            def executemany(self, sql, linhas):
                vistas.append(sql)

        radar._inserir(FalsaLigacao(), "t", ("a", "b", "c"), [(1, 2, 3)])
        self.assertIn("(a, b, c)", vistas[0])
        self.assertIn("VALUES (?,?,?)", vistas[0])

    def test_sem_linhas_nao_toca_na_base(self):
        class Explode:
            def executemany(self, *a):
                raise AssertionError("não devia ter escrito nada")

        radar._inserir(Explode(), "t", ("a",), [])

    def test_as_listas_de_colunas_nao_estao_vazias(self):
        for cols in (radar.COLS_CONTRATO, radar.COLS_CPV, radar.COLS_ADJ):
            with self.subTest(cols=cols[:1]):
                self.assertTrue(cols)
                self.assertEqual(len(cols), len(set(cols)))


class TestFimEstimado(unittest.TestCase):
    """B03: a vista das renovações ordena e filtra pelo fim estimado
    (celebração + prazo em dias). O dump traz prazos absurdos — há um de
    365 milhões de dias — e datas em falta: nesses casos a resposta é
    "", nunca uma data inventada nem uma excepção a meio da importação.
    """

    def test_conta_em_dias(self):
        self.assertEqual(radar.fim_estimado("2020-10-21", 672), "2022-08-24")

    def test_sem_prazo_ou_sem_data_nao_ha_estimativa(self):
        self.assertEqual(radar.fim_estimado("2020-10-21", 0), "")
        self.assertEqual(radar.fim_estimado("2020-10-21", None), "")
        self.assertEqual(radar.fim_estimado("", 100), "")

    def test_prazo_absurdo_nao_rebenta(self):
        # 365744304 dias é o maior do dump; ano > 9999 estoura o date
        self.assertEqual(radar.fim_estimado("2020-01-01", 365744304), "")

    def test_lixo_nao_rebenta(self):
        self.assertEqual(radar.fim_estimado("ontem", 30), "")
        self.assertEqual(radar.fim_estimado("2020-01-01", "muito"), "")

    def test_a_coluna_esta_no_importador(self):
        # senão o INSERT posicional partia — é a regra das colunas
        self.assertIn("fim_estimado", radar.COLS_CONTRATO)

    def test_janela_so_das_oferecidas(self):
        # o valor entra numa expressão de data do SQL: fora da lista
        # volta à omissão, nunca à URL
        self.assertEqual(radar.meses_pedidos({"meses": "12"}), 12)
        self.assertEqual(radar.meses_pedidos({"meses": "7"}), 6)
        self.assertEqual(radar.meses_pedidos({"meses": "lixo"}), 6)
        self.assertEqual(radar.meses_pedidos({}), 6)


class TestEscaloesDeDesconto(unittest.TestCase):
    """B04: o desconto agrega-se por procedimento antes de dividir — a
    média ingénua por linha dava -18,9% no corpus, porque cada lote
    compara com a base do procedimento inteiro. Estes testes guardam a
    parte pura: os escalões e a mediana.
    """

    def test_mediana_impar_e_par(self):
        _, m = radar.escaloes_de_desconto([0.10, 0.20, 0.30])
        self.assertAlmostEqual(m, 0.20)
        _, m = radar.escaloes_de_desconto([0.10, 0.20, 0.30, 0.40])
        self.assertAlmostEqual(m, 0.25)

    def test_fronteira_cai_no_escalao_de_cima(self):
        # 5% nao e "0–5": os cortes sao limites superiores exclusivos
        escaloes, _ = radar.escaloes_de_desconto([0.05])
        contagens = dict(escaloes)
        self.assertEqual(contagens["5–10%"], 1)
        self.assertEqual(contagens["0–5%"], 0)

    def test_acima_do_ultimo_corte_vai_ao_resto(self):
        escaloes, _ = radar.escaloes_de_desconto([0.75])
        self.assertEqual(dict(escaloes)["50%+"], 1)

    def test_vazio_nao_rebenta(self):
        escaloes, mediana = radar.escaloes_de_desconto([])
        self.assertEqual(escaloes, [])
        self.assertIsNone(mediana)

    def test_etiquetas_saem_dos_cortes(self):
        escaloes, _ = radar.escaloes_de_desconto([0.01])
        self.assertEqual(len(escaloes), len(radar.LIMITES_DESCONTO) + 1)

    def test_percentagem_com_virgula(self):
        # numeros a portuguesa, como o resto do painel
        self.assertEqual(radar.pct_pt(0.073), "7,3%")
        self.assertEqual(radar.pct_pt(0.5), "50,0%")

    def test_a_agregacao_e_por_procedimento_e_exclui_o_ambiguo(self):
        # o SQL tem de agrupar por n_anuncio e deitar fora os grupos com
        # a base a variar (semantica ambigua) e a soma acima da base
        vistos = []

        class FalsaLigacao:
            def execute(self, sql, valores):
                vistos.append(sql)
                return []

        radar.descontos_por_procedimento(FalsaLigacao(), " WHERE 1=1", [])
        self.assertIn("GROUP BY c.n_anuncio", vistos[0])
        self.assertIn("MIN(c.preco_base) = MAX(c.preco_base)", vistos[0])
        self.assertIn("SUM(c.preco_contratual) <= MAX(c.preco_base)",
                      vistos[0])


class TestPesquisaSemAcentos(unittest.TestCase):
    """A caixa de pesquisa perdia 11% dos resultados.

    O LIKE do SQLite só baixa maiúsculas de letras ASCII: para ele "Ç" e
    "ç" são letras diferentes. Escrever "aquisição" devolvia 25 868 dos
    29 058 anúncios que contêm mesmo a palavra, porque os 9 383 títulos
    escritos todos em maiúsculas ficavam de fora. Procura-se em colunas
    normalizadas e com o termo normalizado do mesmo modo.
    """

    def valor(self, args):
        _, valores = radar.condicoes(args)
        return valores[0]

    def test_o_termo_vai_normalizado(self):
        self.assertEqual(self.valor({"q": "Aquisição", "estado": ""}),
                         "%aquisicao%")

    def test_maiusculas_acentuadas_dao_o_mesmo_termo(self):
        self.assertEqual(self.valor({"q": "AQUISIÇÃO", "estado": ""}),
                         self.valor({"q": "aquisição", "estado": ""}))

    def test_a_entidade_tambem(self):
        self.assertEqual(self.valor({"ent": "MUNICÍPIO", "estado": ""}),
                         "%municipio%")

    def test_procura_se_nas_colunas_normalizadas(self):
        onde, _ = radar.condicoes({"q": "x", "ent": "y", "estado": ""})
        self.assertIn("titulo_norm LIKE", onde)
        self.assertIn("entidade_norm LIKE", onde)

    def test_o_escape_do_like_continua_a_valer(self):
        # normalizar não pode desfazer o escape: "50%" tem de continuar a
        # procurar por "50%" e não por tudo o que tem "50"
        self.assertEqual(self.valor({"q": "50%", "estado": ""}),
                         "%50" + radar.ESCAPE_LIKE + "%%")


class TestBaldeSemPlataforma(unittest.TestCase):
    """O selector dizia "(nenhuma) (56)" e a lista devolvia 60 645.

    O número do rótulo conta os anúncios com detalhe lido; o filtro
    apanhava todos os que não tinham plataforma, incluindo os 60 589 que
    ainda ninguém tinha lido -- e sem detalhe lido ainda não há
    plataforma nenhuma. São dois baldes diferentes.
    """

    def test_sem_plataforma_exige_detalhe_lido(self):
        onde, _ = radar.condicoes({"plat": radar.SEM_PLATAFORMA, "estado": ""})
        self.assertIn("detalhe_lido = 1", onde)

    def test_por_ler_e_o_outro_balde(self):
        onde, _ = radar.condicoes({"plat": radar.POR_LER, "estado": ""})
        self.assertIn("detalhe_lido = 0", onde)
        self.assertNotIn("plataforma", onde)

    def test_uma_plataforma_a_serio_continua_igual(self):
        onde, valores = radar.condicoes({"plat": "vortal", "estado": ""})
        self.assertIn("plataforma = ?", onde)
        self.assertEqual(valores, ["vortal"])

    def test_os_dois_baldes_nao_sao_o_mesmo_valor(self):
        self.assertNotEqual(radar.SEM_PLATAFORMA, radar.POR_LER)


class TestFiltroPorPrazo(unittest.TestCase):
    """3 982 dos "por ver" já tinham o prazo passado e não havia forma de
    os apartar: a lista só ordenava por data de publicação e a etiqueta
    vermelha era só uma etiqueta."""

    def test_aberto_pede_prazo_daqui_para_a_frente(self):
        onde, valores = radar.condicoes({"prazo": "aberto", "estado": ""})
        self.assertIn("prazo >= ?", onde)
        self.assertEqual(len(valores), 1)

    def test_expirado_pede_o_contrario(self):
        onde, _ = radar.condicoes({"prazo": "expirado", "estado": ""})
        self.assertIn("prazo < ?", onde)

    def test_urgente_e_uma_janela_com_dois_limites(self):
        onde, valores = radar.condicoes({"prazo": "urgente", "estado": ""})
        self.assertIn("prazo >= ?", onde)
        self.assertIn("prazo <= ?", onde)
        self.assertEqual(len(valores), 2)
        # o fim da janela é o mesmo número de dias que os indicadores
        # anunciam: o número mostrado tem de dar a lista que o link abre.
        # Contra dias_urgente() e NUNCA contra DIAS_URGENTE, que é só a
        # omissão: com a janela posta a 8 no painel (config.json), este
        # teste falhava sem nada estar partido -- exactamente o limiar à
        # mão que a regra da empresa proíbe.
        ini = datetime.date.fromisoformat(valores[0])
        fim = datetime.date.fromisoformat(valores[1])
        self.assertEqual((fim - ini).days, radar.dias_urgente())

    def test_o_prazo_vazio_nao_filtra_nada(self):
        onde, _ = radar.condicoes({"prazo": "", "estado": ""})
        self.assertNotIn("prazo", onde)

    def test_valor_inventado_nao_filtra(self):
        onde, _ = radar.condicoes({"prazo": "qualquer coisa", "estado": ""})
        self.assertNotIn("prazo", onde)

    def test_o_prazo_e_um_campo_dos_anuncios(self):
        self.assertIn("prazo", radar.CAMPOS_FILTRO)
        self.assertIn("prazo", radar.CAMPOS_POR_VISTA["anuncios"])
        self.assertNotIn("prazo", radar.CAMPOS_POR_VISTA["contratos"])


class TestCorta(unittest.TestCase):
    """Os títulos cortavam a meio de palavra e sem reticências.

    "...suporte do Hardware Oracle onde residem as Base de Dado" lia-se
    como dado estragado e não como texto cortado.
    """

    def test_curto_fica_igual(self):
        self.assertEqual(radar.corta("abc", 10), "abc")

    def test_no_limite_nao_corta(self):
        self.assertEqual(radar.corta("abcde", 5), "abcde")

    def test_cortado_leva_reticencias(self):
        self.assertEqual(radar.corta("abcdefgh", 5), "abcde…")

    def test_nao_deixa_espaco_antes_das_reticencias(self):
        self.assertEqual(radar.corta("abcd efgh", 5), "abcd…")

    def test_vazio_e_none_nao_rebentam(self):
        self.assertEqual(radar.corta("", 5), "")
        self.assertEqual(radar.corta(None, 5), "")


class TestBotoesDaLinha(unittest.TestCase):
    """Os botões de cada linha eram sempre os mesmos dois.

    Em Descartados não havia forma nenhuma de repor um descarte -- o
    caminho era marcar interessa e depois "tirar do quadro" -- e em
    Interessa o botão "interessa" continuava lá e não era inócuo: cada
    clique voltava a pedir as peças e a descarregá-las outra vez.

    (15/09/2026: a decisão deixou de morar no anúncio, e o que decide os
    botões é a PROPOSTA. O erro que a classe guarda é o mesmo.)
    """

    def anuncio(self):
        return {"ref": "1/2026", "titulo": "T", "entidade": "E",
                "data_pub": "2026-08-01", "tipo": "", "cpv": "",
                "plataforma": "", "prazo": "", "preco_base": "",
                "estado": "novo"}

    def _na_escada(self, *estados):
        return {"1/2026": [{"ref": "1/2026", "estado": e, "lote": None,
                            "motivo": None} for e in estados]}

    def test_por_ver_oferece_os_dois_botoes_e_nao_o_selector(self):
        """Uma coisa OU a outra (decisão dele a 15/09/2026): por decidir
        são os dois botões de sempre -- «interessa» vai directo a «Por
        analisar», «abandonar» vai a «Não fomos» e pergunta porquê. Um
        selector a dizer «— pôr na escada» era uma palavra inventada ao
        lado de oito palavras a sério, e punha a dois gestos o que é o
        gesto de 90% das linhas do «Por ver»."""
        h = radar.linha(self.anuncio(), na_escada={})
        self.assertIn("/estado/1%2F2026/analisar", h)
        self.assertIn("abandonar-js", h)
        self.assertNotIn("escada-js", h)
        self.assertNotIn("pôr na escada", h)

    def test_quem_ja_esta_na_escada_tira_se_pelo_selector(self):
        """15/09/2026: os botões deram lugar ao selector, e «tirar da
        escada» é a última opção dele."""
        h = radar.linha(self.anuncio(), na_escada=self._na_escada("nao_fomos"))
        self.assertIn("action='/escada/1%2F2026'", h)
        self.assertIn("<option value='porver'>tirar da escada</option>", h)
        self.assertNotIn("abandonar-js", h)     # já está nessa ranhura

    def test_em_analise_nao_repete_o_botao_interessa(self):
        h = radar.linha(self.anuncio(), na_escada=self._na_escada("analisar"))
        self.assertNotIn("/estado/1/2026/analisar", h)

    def test_a_etiqueta_da_ranhura_some_na_vista_dessa_ranhura(self):
        # na aba "Submetido" a etiqueta "Submetido" é sempre verdade,
        # portanto não diz nada e só disputa espaço com o CPV e o prazo.
        # Mede-se no bloco da META e não na linha toda: o selector tem a
        # palavra em todas as suas <option>, sempre.
        escada = self._na_escada("submetido")

        def meta(vista):
            h = radar.linha(self.anuncio(), vista, na_escada=escada)
            return h.split("item-meta'>")[1].split("</div>")[0]

        self.assertNotIn("Submetido", meta("submetido"))
        self.assertIn("Submetido", meta(""))

    def test_um_anuncio_com_dois_lotes_mostra_os_dois(self):
        """D3: o L1 ganho e o L2 perdido são duas etiquetas na mesma
        linha. Com o estado no anúncio não havia forma de o dizer."""
        escada = {"1/2026": [
            {"ref": "1/2026", "estado": "ganho", "lote": 1, "motivo": None},
            {"ref": "1/2026", "estado": "perdido", "lote": 2, "motivo": "Preço"}]}
        h = radar.linha(self.anuncio(), "", na_escada=escada)
        self.assertIn("Ganho L1", h)
        self.assertIn("Perdido L2", h)
        self.assertIn(">Preço<", h)


class TestListaEmCurso(unittest.TestCase):
    """A tabela do «Em curso» durou um dia (14 a 15/09/2026).

    Nasceu com as colunas que o Afonso mandou -- título, cliente, preço,
    esclarecimentos, entrega, tipologia, estado, CV, proposta técnica,
    notas, plataforma, CoE, responsável -- e a escada absorveu-a: os
    mesmos interessados numa tabela são exactamente a lista das ranhuras
    da empresa, e um separador próprio era a mesma página com outro nome.

    O que esta classe guarda agora é que as ligações antigas não se
    partem por uma arrumação nossa.
    """

    def test_a_lista_redirecciona_para_a_escada(self):
        r = radar.app.test_client().get("/lista")
        self.assertEqual(r.status_code, 302)
        self.assertIn("estado=analisar", r.headers["Location"])

    def test_gravar_uma_linha_leva_a_ficha_do_anuncio(self):
        """Os campos que essa rota gravava vivem na proposta, e editam-se
        na ficha: mandar para lá é melhor do que um 404 a quem tinha o
        formulário aberto."""
        r = radar.app.test_client().post("/lista/60%2F2026",
                                         data={"notas": "x"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("/anuncio/60", r.headers["Location"])

    def test_as_colunas_que_a_empresa_decide_estao_na_proposta(self):
        """Cada uma delas tem de ter sítio: a tabela saiu, os campos não."""
        for coluna in ("tipologia", "cv", "proposta_tecnica", "notas", "coe",
                       "responsavel", "valor_proposta", "lugar", "top3"):
            self.assertIn(coluna, radar.COLUNAS_DA_PROPOSTA, coluna)


class TestSubfatoresDoCriterio(unittest.TestCase):
    """Os pesos somavam 200%.

    O DR põe os subfactores a seguir ao factor com "Subfatores:" sem
    valor. Iam todos na mesma linha e com o mesmo peso visual: "Preço
    45% · Início 10% · Qualidade 45% · Plano de Trabalhos 70% · Memória
    30%" -- os dois últimos são subfactores da Qualidade.
    """

    def criterio(self, texto):
        return radar.criterio_de_adjudicacao(radar.seccoes_do_texto(texto))

    ANUNCIO = ("21 - CRITÉRIO DE ADJUDICAÇÃO\n"
               "Multifator: Sim\n"
               "Fator: \nNome: Preço\nPonderação: 45%\nSubfatores: Não\n"
               "Fator: \nNome: Outros\nOutro Nome: Início da Execução\n"
               "Ponderação: 10%\nSubfatores: Não\n"
               "Fator: \nNome: Qualidade\nPonderação: 45%\nSubfatores: Sim\n"
               "Subfatores: \n"
               "Nome: Plano de Trabalhos\nPonderação : 70%; \n"
               "Nome: Memória Descritiva\nPonderação : 30%; \n")

    def test_os_de_topo_somam_cem(self):
        c = self.criterio(self.ANUNCIO)
        pesos = [int(p) for p in re.findall(r"(\d+)%", c.split("(")[0])]
        self.assertEqual(sum(pesos), 100)

    def test_os_subfatores_ficam_dentro_de_parenteses(self):
        c = self.criterio(self.ANUNCIO)
        self.assertIn("Qualidade 45% (Plano de Trabalhos 70%", c)
        self.assertIn("Memória Descritiva 30%)", c)

    def test_o_ponto_e_virgula_do_dr_nao_passa(self):
        self.assertNotIn(";", self.criterio(self.ANUNCIO))

    def test_sem_subfatores_nao_ha_parenteses(self):
        c = self.criterio("21 - CRITÉRIO DE ADJUDICAÇÃO\nMultifator: Sim\n"
                          "Fator: \nNome: A\nPonderação: 60%\n"
                          "Fator: \nNome: B\nPonderação: 40%\n")
        self.assertEqual(c, "A 60% · B 40%")


class TestNumeroDoCSV(unittest.TestCase):
    """As duas exportações escreviam dinheiro de maneiras diferentes e
    nenhuma servia o Excel português: nos anúncios "1.326.675,00 EUR",
    que é texto e não soma; nos contratos "7546.5", que em português dá
    setenta e cinco mil."""

    def test_texto_portugues_vira_numero_portugues(self):
        self.assertEqual(radar.numero_csv("1.326.675,00 EUR"), "1326675,00")

    def test_float_do_corpus_leva_virgula(self):
        self.assertEqual(radar.numero_csv(7546.5), "7546,50")

    def test_vazio_fica_vazio(self):
        self.assertEqual(radar.numero_csv(""), "")
        self.assertEqual(radar.numero_csv(None), "")

    def test_texto_sem_numero_nao_rebenta(self):
        self.assertEqual(radar.numero_csv("a combinar"), "")

    def test_nunca_leva_separador_de_milhares(self):
        # o ponto dos milhares faria o Excel ler outra coisa
        self.assertNotIn(".", radar.numero_csv("1.326.675,00 EUR"))

    def test_o_nome_do_ficheiro_leva_data(self):
        nome = radar.nome_csv("anuncios")
        self.assertTrue(nome.startswith("anuncios-"))
        self.assertTrue(nome.endswith(".csv"))
        datetime.date.fromisoformat(nome[len("anuncios-"):-len(".csv")])


class TestNomesDosCamposDoFiltro(unittest.TestCase):
    """"entidade Município de Lisboa — aqui não se aplica: entidade".

    `ent` (anúncios) e `adj` (contratos) são campos diferentes e tinham
    ambos o nome "entidade", o que produzia o aviso mais confuso da
    aplicação. As caixas dizem agora o mesmo que estes nomes.
    """

    def test_a_entidade_dos_anuncios_e_a_dos_contratos_tem_nomes_diferentes(self):
        self.assertNotEqual(radar._NOMES_FILTRO["ent"],
                            radar._NOMES_FILTRO["adj"])

    def test_os_dois_campos_de_entidade_dos_contratos_concordam(self):
        # `adj` é a caixa de texto e `entid` é a chave: o mesmo sentido
        self.assertEqual(radar._NOMES_FILTRO["adj"],
                         radar._NOMES_FILTRO["entid"])

    def test_todos_os_campos_tem_nome(self):
        for campo in radar.CAMPOS_FILTRO:
            if campo == "estado":
                continue          # o estado descreve-se por _NOMES_ESTADO
            with self.subTest(campo=campo):
                self.assertIn(campo, radar._NOMES_FILTRO)


class TestUmaVerificacaoDeCadaVez(unittest.TestCase):
    """"Verificar agora" corria dentro do pedido: minutos com a página em
    branco, sem sinal de que tinha arrancado e sem nada a impedir um
    segundo clique de começar tudo de novo."""

    def setUp(self):
        self.antes = dict(radar._VERIFICACAO)
        # o trinco entre processos (14/09/2026) le a base verdadeira; aqui
        # so se testa o dicionario deste processo
        self.enterContext(unittest.mock.patch.object(
            radar, "verificacao_noutro_processo", lambda **k: ""))

    def tearDown(self):
        radar._VERIFICACAO.clear()
        radar._VERIFICACAO.update(self.antes)

    def test_a_correr_recusa_a_segunda(self):
        radar._VERIFICACAO["a_correr"] = True
        radar._VERIFICACAO["passo"] = "a ler o detalhe"
        arrancou, porque = radar.comecar_verificacao()
        self.assertFalse(arrancou)
        self.assertIn("a ler o detalhe", porque)

    def test_parada_nao_diz_nada(self):
        radar._VERIFICACAO["a_correr"] = False
        radar._VERIFICACAO["passo"] = "a ler o detalhe"
        self.assertEqual(radar.verificacao_a_correr(), "")

    def test_a_correr_diz_em_que_passo_vai(self):
        radar._VERIFICACAO["a_correr"] = True
        radar._VERIFICACAO["passo"] = "a guardar a cópia"
        self.assertEqual(radar.verificacao_a_correr(), "a guardar a cópia")


class TestEntidadeSemNif(unittest.TestCase):
    """A mesma empresa aparecia duas vezes no "quem ganha", sem explicação.

    10% dos adjudicatários do dump do IMPIC vêm sem NIF e agrupam-se pelo
    nome. São dados do IMPIC e não há como juntá-los, mas uma linha
    explicada deixa de parecer um erro de contagem.
    """

    def test_chave_por_nome_fica_marcada(self):
        h = radar.liga_entidade("n:inetum espana", "Inetum España")
        self.assertIn("sem NIF", h)

    def test_chave_com_nif_nao_leva_marca(self):
        h = radar.liga_entidade("980079659", "INETUM ESPAÑA, S.A.")
        self.assertNotIn("sem NIF", h)

    def test_sem_chave_nao_ha_ligacao_nem_marca(self):
        h = radar.liga_entidade("", "Alguém")
        self.assertNotIn("<a", h)
        self.assertNotIn("sem NIF", h)


class TestPesquisaContratosNormalizada(unittest.TestCase):
    """Procurar "aquisição" nos contratos perdia 68 295 (11,8%).

    O IMPIC escreve muitos objectos todos em maiúsculas e o LIKE do
    SQLite não baixa o "Ç": a pesquisa dos contratos fazia LIKE cru
    sobre as colunas originais -- o mesmo defeito já corrigido nos
    anúncios, vivo no separador onde se estuda a concorrência.
    """

    def test_objecto_procura_na_coluna_normalizada(self):
        onde, valores = radar.condicoes_contratos({"q": "Aquisição"})
        self.assertIn("objecto_norm", onde)
        self.assertNotIn("c.objecto LIKE", onde)
        self.assertIn("%aquisicao%", valores)

    def test_quem_comprou_procura_pela_norma_de_entidade(self):
        onde, valores = radar.condicoes_contratos({"adj": "Câmara Municipal"})
        self.assertIn("adjudicante_norm", onde)
        self.assertIn("%camara municipal%", valores)

    def test_quem_ganhou_procura_pela_norma_de_entidade(self):
        # "Ramos & Filhos" só encontra "ramos e filhos" se o termo levar
        # o mesmo caminho da coluna (norma_entidade troca & por " e ")
        onde, valores = radar.condicoes_contratos({"ganhou": "Ramos & Filhos"})
        self.assertIn("nome_norm", onde)
        self.assertIn("%ramos e filhos%", valores)

    def test_o_importador_enche_a_coluna_normalizada(self):
        # a coluna nova tem de estar no COLS_CONTRATO, senão o INSERT
        # posicional parte -- já partiu duas vezes por isto
        self.assertIn("objecto_norm", radar.COLS_CONTRATO)


class TestDesescapeDoImportador(unittest.TestCase):
    """5 998 entidades chamavam-se "&amp;" no ecrã e não se encontravam.

    O dump do IMPIC vem escapado para HTML; guardado assim, o painel
    escapava outra vez ao desenhar ("Ernst &amp;amp; Young") e procurar
    "Ramos & Filhos" não encontrava nada.
    """

    def test_o_nome_desescapa_a_entrada(self):
        nif, nome = radar._nif_e_nome("512345678 - Ramos &amp; Filhos, Lda")
        self.assertEqual(nif, "512345678")
        self.assertEqual(nome, "Ramos & Filhos, Lda")

    def test_tambem_sem_nif(self):
        _, nome = radar._nif_e_nome("- - Marques &amp; Marques")
        self.assertEqual(nome, "Marques & Marques")

    def test_desescapa_ate_estabilizar(self):
        # 1 413 adjudicatários vinham escapados DUAS vezes; uma passagem
        # única tirava uma capa e deixava a outra
        self.assertEqual(radar._des_html("A &amp;amp; B"), "A & B")
        self.assertEqual(radar._des_html("A &amp; B"), "A & B")

    def test_texto_limpo_passa_intacto(self):
        self.assertEqual(radar._des_html("A & B"), "A & B")
        self.assertEqual(radar._des_html(""), "")
        self.assertEqual(radar._des_html(None), "")

    def test_a_chave_sai_do_nome_limpo(self):
        # com "&amp;" a chave "n:" levava um "amp" lá dentro e a mesma
        # empresa escrita limpa noutra fonte ficava noutra chave
        _, nome = radar._nif_e_nome("- - A &amp; B Lda")
        self.assertEqual(radar.chave_entidade("", nome),
                         radar.chave_entidade("", "A & B Lda"))


class TestDatasDeFiltro(unittest.TestCase):
    """"de=lixo" num URL guardado esvaziava a lista em silêncio.

    Comparar datas com texto dava sempre falso; e o € mínimo com lixo
    era ignorado -- dois silêncios com efeitos opostos. Agora ignora-se
    nas duas listas e a página avisa por palavras.
    """

    def test_data_valida_passa(self):
        self.assertEqual(radar.data_de_filtro("2026-08-01"), "2026-08-01")

    def test_lixo_e_ignorado(self):
        self.assertEqual(radar.data_de_filtro("lixo"), "")
        self.assertEqual(radar.data_de_filtro(None), "")

    def test_a_escrita_portuguesa_tambem_passa(self):
        """Os campos deixaram de ser `<input type=date>` a 16/09/2026: o
        nativo desenha-se no idioma do BROWSER e não no da página, e num
        browser em inglês dizia `mm/dd/yyyy` numa aplicação escrita em
        português. Passaram a texto com `dd/mm/aaaa`, e por isso esta
        função tem de ler as duas escritas — os atalhos de período
        continuam a pôr ISO no endereço."""
        self.assertEqual(radar.data_de_filtro("01/08/2026"), "2026-08-01")
        self.assertEqual(radar.data_de_filtro("1/8/2026"), "2026-08-01")
        self.assertEqual(radar.data_de_filtro(" 31/12/2025 "), "2025-12-31")

    def test_um_dia_que_nao_existe_nao_e_data(self):
        """31 de Fevereiro escreve-se e não é um dia. Sem esta guarda
        entrava no SQL como "2026-02-31" e comparava-se com datas a
        sério, que é o silêncio que esta classe existe para travar."""
        self.assertEqual(radar.data_de_filtro("31/02/2026"), "")
        self.assertEqual(radar.data_de_filtro("32/01/2026"), "")

    def test_o_campo_escreve_se_em_portugues(self):
        """O que o campo mostra é `dd/mm/aaaa`, venha de onde vier — do
        atalho de período (ISO) ou do que se escreveu. O que não se lê
        passa como está: o campo é onde o erro se corrige."""
        self.assertEqual(radar.data_para_campo("2026-08-01"), "01/08/2026")
        self.assertEqual(radar.data_para_campo("01/08/2026"), "01/08/2026")
        self.assertEqual(radar.data_para_campo("lixo"), "lixo")
        self.assertEqual(radar.data_para_campo(None), "")

    def test_condicoes_dos_anuncios_ignoram_a_data_invalida(self):
        onde, _ = radar.condicoes({"de": "lixo", "estado": ""})
        self.assertNotIn("data_pub", onde)

    def test_condicoes_dos_contratos_ignoram_a_data_invalida(self):
        onde, _ = radar.condicoes_contratos({"de": "lixo"})
        self.assertNotIn("data_celebracao", onde)

    def test_data_invalida_avisa_por_palavras(self):
        avisos = radar.avisos_de_datas({"de": "lixo"})
        self.assertEqual(len(avisos), 1)
        self.assertIn("lixo", avisos[0])
        self.assertIn("ignorada", avisos[0])

    def test_intervalo_invertido_avisa_e_diz_as_datas(self):
        avisos = radar.avisos_de_datas({"de": "2026-08-01",
                                        "ate": "2026-07-01"})
        self.assertEqual(len(avisos), 1)
        self.assertIn("invertido", avisos[0])
        self.assertIn("01/08/2026", avisos[0])   # DD/MM, nunca ISO

    def test_intervalo_direito_nao_avisa(self):
        self.assertEqual(radar.avisos_de_datas({"de": "2026-07-01",
                                                "ate": "2026-08-01"}), [])
        self.assertEqual(radar.avisos_de_datas({}), [])


class TestJanelaUrgente(unittest.TestCase):
    """O cartão dos indicadores dizia "7 dias" com o filtro a 10.

    O número do ecrã não abria lista nenhuma que o confirmasse. A janela
    é UMA (janela_urgente) e o filtro prazo=urgente usa exactamente ela.
    """

    def test_a_janela_usa_o_dias_urgente(self):
        hoje = datetime.date(2026, 8, 29)
        inicio, fim = radar.janela_urgente(hoje)
        self.assertEqual(inicio, "2026-08-29")
        # dias_urgente() e nao DIAS_URGENTE: o segundo e a omissao, e a
        # janela em uso vem do config.json (esta a 8, nao a 10)
        self.assertEqual(fim, (hoje + datetime.timedelta(
            days=radar.dias_urgente())).isoformat())

    def test_o_filtro_urgente_usa_a_mesma_janela(self):
        _, valores = radar.condicoes({"prazo": "urgente", "estado": ""})
        inicio, fim = radar.janela_urgente(datetime.date.today())
        self.assertIn(inicio, valores)
        self.assertIn(fim, valores)


class TestEtiquetaPrazoSegueAJanela(unittest.TestCase):
    """A etiqueta de prazo tinha um 7 escrito à mão com o filtro a 10.

    Um anúncio a 9 dias saía verde ("folgado") na lista, no quadro, no
    calendário e na ficha, e ao mesmo tempo contava como urgente no
    filtro prazo=urgente, no cartão dos indicadores e nos avisos. É a
    mesma armadilha do cartão que dizia "7 dias": o número que um ecrã
    mostra tem de dar exactamente a lista que a ligação dele abre. A
    janela é UMA — dias_urgente() — e a etiqueta acompanha-a.
    """

    def setUp(self):
        # com_janela() troca o ler_config dentro do teste; o patch so
        # garante que volta ao verdadeiro no fim
        self.enterContext(unittest.mock.patch.object(
            radar, "ler_config", radar.ler_config))

    def com_janela(self, dias):
        radar.ler_config = lambda: {"dias_urgente": dias}

    def daqui_a(self, dias):
        return (datetime.date.today()
                + datetime.timedelta(days=dias)).isoformat()

    def test_a_classe_acompanha_a_janela_do_config(self):
        # 9 dias: dentro de uma janela de 10, fora de uma de 7
        self.com_janela(10)
        self.assertEqual(radar.etiqueta_prazo(self.daqui_a(9))[1], "avisa")
        self.com_janela(7)
        self.assertEqual(radar.etiqueta_prazo(self.daqui_a(9))[1], "ok")

    def test_janela_larga_avisa_mais_cedo(self):
        self.com_janela(20)
        self.assertEqual(radar.etiqueta_prazo(self.daqui_a(15))[1], "avisa")
        self.com_janela(3)
        self.assertEqual(radar.etiqueta_prazo(self.daqui_a(15))[1], "ok")

    def test_a_janela_passada_manda_e_nao_le_o_config(self):
        # quem chama em ciclo (lista, quadro, calendario) le a janela uma
        # vez e passa-a; se o config fosse lido na mesma, era uma abertura
        # de ficheiro por linha -- e valores diferentes no mesmo ecra
        def rebenta():
            raise AssertionError("etiqueta_prazo leu o config com a janela dada")
        radar.ler_config = rebenta
        self.assertEqual(radar.etiqueta_prazo(self.daqui_a(9), 10)[1], "avisa")
        self.assertEqual(radar.etiqueta_prazo(self.daqui_a(9), 7)[1], "ok")

    def test_o_expirado_e_o_hoje_nao_dependem_da_janela(self):
        self.com_janela(1)
        self.assertEqual(radar.etiqueta_prazo(self.daqui_a(0))[1], "mau")
        self.assertEqual(radar.etiqueta_prazo(self.daqui_a(-1))[1], "mau")

    def test_a_etiqueta_e_o_filtro_concordam_na_fronteira(self):
        # o ultimo dia da janela do filtro tem de sair "avisa" na etiqueta
        self.com_janela(10)
        hoje = datetime.date.today()
        _, fim = radar.janela_urgente(hoje)
        self.assertEqual(radar.etiqueta_prazo(fim)[1], "avisa")
        depois = (datetime.date.fromisoformat(fim)
                  + datetime.timedelta(days=1)).isoformat()
        self.assertEqual(radar.etiqueta_prazo(depois)[1], "ok")


class TestDataHoraPT(unittest.TestCase):
    """O histórico da ficha, a barra do corpus e a "última" da barra
    lateral mostravam "2026-08-29 18:54" -- ISO à vista, contra a regra
    da empresa de ISO na base e DD/MM no ecrã."""

    def test_data_com_hora(self):
        self.assertEqual(radar.data_hora_pt("2026-08-29 18:54"),
                         "29/08/2026 18:54")

    def test_data_sem_hora(self):
        self.assertEqual(radar.data_hora_pt("2026-08-29"), "29/08/2026")

    def test_texto_livre_passa_como_esta(self):
        # há marcas antigas com texto livre ("nunca")
        self.assertEqual(radar.data_hora_pt("nunca"), "nunca")
        self.assertEqual(radar.data_hora_pt(""), "—")


class TestLimparMantemEstado(unittest.TestCase):
    """"limpar" apontava sempre para "/": limpar a pesquisa no separador
    Descartados atirava para "Por ver". O estado é o separador onde se
    está, não parte do filtro que se quer tirar."""

    def test_por_ver_volta_a_raiz(self):
        self.assertEqual(radar.href_limpar("/", "porver"), "/")

    def test_outro_separador_fica_onde_esta(self):
        self.assertEqual(radar.href_limpar("/", "descartado"),
                         "/?estado=descartado")
        self.assertEqual(radar.href_limpar("/", "interessa"),
                         "/?estado=interessa")

    def test_todos_e_estado_vazio_e_nao_ausente(self):
        # ausente é "por ver", vazio é "todos" -- a diferença tem de
        # sobreviver ao limpar, como em condicoes()
        self.assertEqual(radar.href_limpar("/", ""), "/?estado=")

    def test_paginas_sem_separadores_ficam_como_estavam(self):
        self.assertEqual(radar.href_limpar("/contratos"), "/contratos")


class TestTabelaEssencialDepoisDeLido(unittest.TestCase):
    """"só consta do Caderno de Encargos" depois de o CE ter sido lido.

    O modelo respondia "não consta" à equipa e a ficha mandava abrir um
    documento que a leitura já tinha visto não dizer nada -- parecia a
    leitura avariada exactamente quando funcionou. "Lido e não consta"
    e "ainda não lido" são respostas diferentes.
    """

    LIDO_SEM_NADA = {"objecto": "- fazer X", "equipa": "não consta",
                     "documentos_proposta": "não consta",
                     "preco_anormalmente_baixo": "não consta",
                     "localizacao": "não consta",
                     "fontes": "CE.pdf, PC.pdf", "modelo": "m"}

    def tabela(self, analise=None):
        return radar.essencial_do_anuncio(
            TestTabelaEssencial.ANUNCIO,
            radar.seccoes_do_texto(TestTabelaEssencial.TEXTO), analise)

    def campo(self, rotulo, analise=None):
        return next(l for l in self.tabela(analise) if l[0] == rotulo)

    def test_equipa_lida_diz_que_nao_fixa_e_nao_manda_abrir_o_ce(self):
        falta = self.campo("Equipa", self.LIDO_SEM_NADA)[2]
        self.assertIn("foi lido", falta)
        self.assertNotIn("só consta", falta)

    def test_sem_leitura_continua_a_apontar_para_o_ce(self):
        self.assertEqual(self.campo("Equipa")[2], radar.FALTA_CE)

    def test_local_lido_sem_regime_nao_diz_ainda_nao_foi_lido(self):
        nota = self.campo("Local de prestação de serviços",
                          self.LIDO_SEM_NADA)[3]
        self.assertIn("foi lido", nota)
        self.assertNotIn("ainda não foi lido", nota)

    def test_analise_antiga_sem_o_campo_nao_afirma_leitura_que_nao_houve(self):
        # linha gravada antes de o campo existir: o campo NÃO foi lido,
        # e "foi lido e não fixa" seria mentira ao contrário
        antiga = {k: v for k, v in self.LIDO_SEM_NADA.items()
                  if k != "equipa"}
        self.assertEqual(self.campo("Equipa", antiga)[2], radar.FALTA_CE)

    def test_documentos_lidos_apontam_para_o_programa(self):
        falta = self.campo("Documentos que constituem a proposta",
                           self.LIDO_SEM_NADA)[2]
        self.assertIn("foi lido", falta)
        self.assertNotIn("só consta", falta)


class TestCriarFiltroNaoPerdeOQueSeEscreveu(unittest.TestCase):
    """A validação recusava e o redirect deitava fora os treze campos.

    E o formulário era GET -- escrevia na base contra a regra da empresa de
    que tudo o que escreve é POST. A recusa agora leva os campos na
    query string e o formulário volta preenchido.
    """

    def setUp(self):
        self.cliente = radar.app.test_client()

    def test_recusa_devolve_o_que_se_escreveu(self):
        # nome posto mas nenhum campo de filtro: recusa sem tocar na base
        r = self.cliente.post("/alertas/criar",
                              data={"nome": "O meu filtro", "estado": "novo"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("aviso=", r.headers["Location"])
        self.assertIn("nome=O+meu+filtro", r.headers["Location"])
        self.assertIn("estado=novo", r.headers["Location"])

    def test_get_ja_nao_cria(self):
        r = self.cliente.get("/alertas/criar?nome=X&q=consultoria")
        self.assertEqual(r.status_code, 405)


class TestMinimoParaEscada(unittest.TestCase):
    """Com 3 contratos, "mais barato" e "25%" eram o mesmo contrato
    repetido: quartis de meia dúzia de pontos são decoração."""

    def test_o_minimo_existe_e_e_maior_que_o_piso_da_referencia(self):
        # referencia_de_preco devolve a partir de 3; a régua pede mais
        self.assertGreaterEqual(radar.MINIMO_PARA_ESCADA, 5)


# A classe TestModeloComFornecedor saiu a 15/09/2026 com o que ela testava: o `_modelo_com_fornecedor()` era uma migração de uso único que já não corria no arranque


class BaseTemporaria(unittest.TestCase):
    """Esqueleto para os testes de migração: uma base TEMPORÁRIA — nunca
    a verdadeira —, criada e deitada fora por teste. Continua sem rede e
    em milissegundos."""

    def setUp(self):
        self.pasta = tempfile.mkdtemp()
        # a limpeza corre em ordem inversa: repoe DB e DOCS, depois o
        # gc.collect() fecha ligacoes penduradas do liga(), e so entao a
        # pasta vai fora. Os patches repoem-se mesmo que o setUp rebente
        # a meio (o tearDown nao corria nesse caso, e o DB ficava a
        # apontar para uma pasta ja apagada -- os testes seguintes caiam
        # por arrasto).
        self.addCleanup(shutil.rmtree, self.pasta, ignore_errors=True)
        self.addCleanup(gc.collect)
        self.enterContext(unittest.mock.patch.object(
            radar, "DB", os.path.join(self.pasta, "ensaio.db")))
        self.enterContext(unittest.mock.patch.object(
            radar, "DOCS", os.path.join(self.pasta, "documentos")))
        # E o `config.json` TAMBÉM (16/09/2026). Sem isto os testes liam
        # o config verdadeiro dele, e o uso normal da aplicação partia a
        # bateria: apanhado nesta sessão, quando ele ligou o Interesse no
        # painel e três testes da escada passaram a contar 0 em vez de 4
        # — o recorte por CPV escondia os anúncios do fixture, que não
        # têm CPV nenhum. Pior do que um teste vermelho: o hook
        # `testes_antes_do_commit.py` trava o commit, e a causa está num
        # ficheiro que ninguém associa aos testes.
        #
        # O `BASE_DIR` vai atrás porque é dele que saem as chaves e as
        # capturas, e um teste que grave lá escrevia na pasta real (a
        # `TestConfiguracoes` já o fazia por si; agora é de todos).
        self.enterContext(unittest.mock.patch.object(
            radar, "BASE_DIR", self.pasta))
        self.enterContext(unittest.mock.patch.object(
            radar, "CONFIG", os.path.join(self.pasta, "config.json")))
        radar.iniciar_db()          # cria o esquema e põe as marcas


class TestRecuoParaTermosDeReserva(BaseTemporaria):
    """O último recurso de recolher(): se o portal não devolver nada à
    pesquisa sem termo, varre pelos `termos_de_reserva` (LEIA-ME, «o
    que o radar vigia»). Nunca se viu disparar e nunca teve teste, e a
    condição era só `not colhidos`, que também é verdadeira num corte
    de rede: o radar respondia a um timeout com seis varrimentos. Este
    teste força o recurso e fixa quando ele NÃO deve disparar."""

    CFG = dict(radar.CONFIG_INICIAL, dias_catchup=7, por_pagina=25, paginas=3,
               termos_de_pesquisa=[""],
               termos_de_reserva=["aquisição", "serviços"])
    CURL = ("curl 'https://dr/pesquisa' -H 'a: b' --data-raw "
            "'{\"screenData\":{\"variables\":{\"FiltrosDePesquisa\":{}}}}'")

    def setUp(self):
        super().setUp()
        self.enterContext(unittest.mock.patch.object(
            radar, "carregar_curl", return_value=self.CURL))
        self.enterContext(unittest.mock.patch.object(
            radar, "guardar_amostra", lambda nome, conteudo: None))
        self.enterContext(unittest.mock.patch.object(radar.time, "sleep"))
        self.pedidos = []

    def _portal(self, resposta):
        def perguntar(pedido, molde):
            lista = molde["screenData"]["variables"]["Pesquisa"]["List"]
            termo = lista[0] if lista else ""
            self.pedidos.append(termo)
            return resposta(termo)
        return unittest.mock.patch.object(radar, "perguntar_ao_dr",
                                         side_effect=perguntar)

    @staticmethod
    def _pagina(quantos, prefixo):
        return ({"data": {"List": [{"_source": {
            "numero": "%s%d/2026" % (prefixo, i), "dbId": "k%d" % i,
            "sumario": "t", "emissor": "E", "dataPublicacao": "2026-09-01",
            "tipo": "Anúncio de procedimento"}} for i in range(quantos)]}}, "")

    def test_pesquisa_vazia_sem_nada_cai_nos_termos_de_reserva(self):
        with self._portal(lambda t: self._pagina(0, "") if t == ""
                          else self._pagina(2, t[:3])):
            ok, msg, novos = radar.recolher(dict(self.CFG))
        self.assertTrue(ok)
        self.assertEqual(self.pedidos, ["", "aquisição", "serviços"])
        self.assertEqual(novos, 4)
        self.assertIn("pelos termos de reserva", msg)

    def test_com_anuncios_nao_ha_recuo(self):
        with self._portal(lambda t: self._pagina(2, "x")):
            ok, msg, novos = radar.recolher(dict(self.CFG))
        self.assertTrue(ok)
        self.assertEqual(self.pedidos, [""])
        self.assertNotIn("reserva", msg)

    def test_corte_de_rede_nao_dispara_o_recuo(self):
        with self._portal(lambda t: (None, "rede: timeout")):
            ok, msg, novos = radar.recolher(dict(self.CFG))
        self.assertFalse(ok)
        self.assertIn("sem ligação ao DR", msg)
        self.assertEqual(self.pedidos, [""])


class TestLerDetalhesParalelo(BaseTemporaria):
    """ler_detalhes_paralelo() manda `concorrencia` pedidos ao DR ao
    mesmo tempo. O risco especifico da concorrencia -- que nao existe
    na versao sequencial -- e threads a escrever no mesmo `molde`
    partilhado e trocarem o Key de um pedido pelo de outro a meio do
    POST. Foi esse bug que o ensaio de 3/09/2026 expos antes de isto
    aqui existir: cada pedido tem de levar a SUA PROPRIA copia."""

    def _preparar(self, n, prefixo="ref"):
        with radar.liga() as c:
            for i in range(n):
                c.execute(
                    "INSERT INTO anuncios (ref, titulo, url, data_pub) "
                    "VALUES (?,?,?,?)",
                    ("%s-%03d" % (prefixo, i), "titulo %d" % i,
                     "https://x/anuncio-procedimento/chave-%03d" % i,
                     "2026-01-%02d" % (i % 28 + 1)))

    def _falso_molde(self):
        return (({"url": "https://dr/detalhe", "headers": {}, "body": "{}"},
                 {"screenData": {"variables": {}}}), "")

    def test_cada_pedido_grava_o_seu_proprio_ref_sem_trocar_com_outro(self):
        # o teste que teria apanhado o bug: cada resposta falsa ecoa o
        # Key que RECEBEU no proprio texto guardado -- se uma thread
        # escrevesse por cima do Key de outra antes do "POST", o texto
        # gravado nao bateria certo com o ref da linha
        self._preparar(40)

        def perguntar_falso(pedido, molde):
            key = molde["screenData"]["variables"]["Key"]
            time.sleep(0.01)          # dar tempo a uma troca, se houver
            return {"data": {"DetalheConteudo": {
                "Texto": "MARCA:" + key, "URL_PDF": ""}}}, ""

        with unittest.mock.patch.object(radar, "_molde_detalhe",
                                        side_effect=lambda: self._falso_molde()), \
             unittest.mock.patch.object(radar, "perguntar_ao_dr",
                                        side_effect=perguntar_falso):
            feitos, aviso = radar.ler_detalhes_paralelo(40, concorrencia=8)

        self.assertEqual((feitos, aviso), (40, ""))
        with radar.liga() as c:
            linhas = c.execute("SELECT ref, url, texto, detalhe_lido "
                              "FROM anuncios").fetchall()
        self.assertEqual(len(linhas), 40)
        for linha in linhas:
            chave_esperada = linha["url"].rsplit("/", 1)[-1]
            self.assertEqual(linha["texto"], "MARCA:" + chave_esperada)
            self.assertEqual(linha["detalhe_lido"], 1)

    def test_casca_ou_apiversion_reporta_aviso_mas_guarda_os_que_deram(self):
        self._preparar(10)

        def perguntar_meio_falha(pedido, molde):
            key = molde["screenData"]["variables"]["Key"]
            if key.endswith(("005", "006", "007", "008", "009")):
                return None, "casca"
            return {"data": {"DetalheConteudo": {
                "Texto": "MARCA:" + key, "URL_PDF": ""}}}, ""

        with unittest.mock.patch.object(radar, "_molde_detalhe",
                                        side_effect=lambda: self._falso_molde()), \
             unittest.mock.patch.object(radar, "perguntar_ao_dr",
                                        side_effect=perguntar_meio_falha), \
             unittest.mock.patch.object(radar, "registar_expiracao_token"):
            feitos, aviso = radar.ler_detalhes_paralelo(10, concorrencia=4)

        self.assertEqual(feitos, 5)
        self.assertIn("casca", aviso)

    def test_sem_captura_devolve_o_aviso_sem_tocar_na_base(self):
        with unittest.mock.patch.object(
                radar, "_molde_detalhe",
                side_effect=lambda: (None, "sem curl_detalhe.txt")):
            feitos, aviso = radar.ler_detalhes_paralelo(10)
        self.assertEqual((feitos, aviso), (0, "sem curl_detalhe.txt"))

    def test_sem_pendentes_nao_manda_pedido_nenhum(self):
        chamou = []
        with unittest.mock.patch.object(radar, "_molde_detalhe",
                                        side_effect=lambda: self._falso_molde()), \
             unittest.mock.patch.object(radar, "perguntar_ao_dr",
                                        side_effect=lambda *a: chamou.append(1)):
            feitos, aviso = radar.ler_detalhes_paralelo(10)
        self.assertEqual((feitos, aviso), (0, ""))
        self.assertEqual(chamou, [])


class TestRetentativaDeExtraccao(BaseTemporaria):
    """A1: extrair_textos() só processava texto_estado IS NULL, e um
    "erro:" ficava terminal para sempre — 30 documentos presos num erro
    de dependência que entretanto foi instalada. Um erro é falha da
    ferramenta e retenta-se; "scan" e "não é PDF" são veredictos sobre
    o conteúdo e esses ficam."""

    def test_erro_retenta_se_veredictos_ficam(self):
        with radar.liga() as c:
            c.executemany(
                "INSERT INTO documentos (ref,nome,texto,texto_estado) "
                "VALUES (?,?,?,?)",
                [("9/2026", "a.pdf", "", "erro: qualquer coisa"),
                 ("9/2026", "b.pdf", None, None),
                 ("9/2026", "c.pdf", "", "scan"),
                 ("9/2026", "d.pdf", "t", "ok"),
                 ("9/2026", "e.zip", "", "não é PDF")])
        # sem ficheiros em disco, o que for reavaliado sai "não é PDF" —
        # é o bastante para se ver QUEM foi reavaliado
        radar.extrair_textos("9/2026")
        with radar.liga() as c:
            estados = dict(c.execute("SELECT nome, texto_estado "
                                     "FROM documentos WHERE ref='9/2026'"))
        self.assertEqual(estados["a.pdf"], "não é PDF")   # erro: retentado
        self.assertEqual(estados["b.pdf"], "não é PDF")   # NULL: como sempre
        self.assertEqual(estados["c.pdf"], "scan")        # veredicto fica
        self.assertEqual(estados["d.pdf"], "ok")
        self.assertEqual(estados["e.zip"], "não é PDF")


class TestSinonimosDePlataforma(unittest.TestCase):
    """D3 do saneamento de 30/08/2026: a plataforma decidia-se com um
    `if "acin" in alvo` solto, fora da lista PLATAFORMAS. Agora é um
    sinónimo declarado ao lado da lista — e um sinónimo aponta sempre
    para uma plataforma que existe, nunca inventa uma nova."""

    def test_todo_o_sinonimo_aponta_para_uma_plataforma_da_lista(self):
        for pista, nome in radar.SINONIMOS_PLATAFORMA.items():
            self.assertIn(nome, radar.PLATAFORMAS, pista)
            # um sinónimo igual a um nome da lista nunca seria testado
            self.assertNotIn(pista, radar.PLATAFORMAS, pista)

    # As pistas vêm da secção do link das peças, como num anúncio real.
    MOLDE = ("15 - PUBLICAÇÃO\n"
             "Link para acesso às peças do concurso (URL): %s")

    def test_acin_continua_a_dar_acingov(self):
        campos = radar.campos_do_detalhe(
            self.MOLDE % "https://plataforma.acin.pt/abc")
        self.assertEqual(campos["plataforma"], "acingov")

    def test_o_nome_por_extenso_ganha_ao_sinonimo(self):
        campos = radar.campos_do_detalhe(
            self.MOLDE % "https://www.acingov.pt/abc")
        self.assertEqual(campos["plataforma"], "acingov")

    def test_sem_pistas_o_texto_todo_serve_de_ultimo_recurso(self):
        # O «último recurso do texto todo» esteve morto desde sempre: o
        # join de pistas vazias dava "  ", truthy, e nunca se caía para
        # o texto. Corrigido a 31/08/2026 com um strip(), depois de
        # medido: 28 anúncios reais diziam a plataforma por extenso no
        # corpo ("apresentados através da plataforma eletrónica acinGov")
        # e ficavam sem ela.
        campos = radar.campos_do_detalhe(
            "6 - MODO\nOs documentos que constituem a proposta devem ser "
            "apresentados através da plataforma eletrónica acinGov "
            "(www.acingov.pt)")
        self.assertEqual(campos["plataforma"], "acingov")

    def test_com_pistas_reais_o_texto_nao_entra(self):
        # a pista existe mas não bate em plataforma nenhuma: o texto
        # todo NÃO pode entrar — era a protecção contra menções de
        # passagem, e continua de pé
        campos = radar.campos_do_detalhe(
            (self.MOLDE % "https://portal-desconhecido.example.pt/x")
            + "\nA vortal foi mencionada de passagem noutro contexto.")
        self.assertEqual(campos["plataforma"], "")


class TestLinhasDeUltimosErros(unittest.TestCase):
    """C1 do saneamento de 30/08/2026: `ultimo_erro_relogio`,
    `docs_ultimo_erro` e `analise_ultimo_erro` existiam na base e não
    apareciam em ecrã nenhum — uma avaria persistente do relógio só se
    via por SQL. Passam a linhas na saúde dos indicadores."""

    def test_sem_erros_nao_ha_linha_nenhuma(self):
        # uma linha verde "sem erros" era ruído
        self.assertEqual(radar.linhas_de_ultimos_erros(), [])
        self.assertEqual(radar.linhas_de_ultimos_erros("", "  ", None), [])

    def test_so_aparece_o_que_existe(self):
        linhas = radar.linhas_de_ultimos_erros(pecas="2026-08-30 09:00 · 1/2026: 404")
        self.assertEqual(len(linhas), 1)
        rotulo, valor, bom = linhas[0]
        self.assertIn("peças", rotulo)
        self.assertIn("1/2026", valor)
        self.assertFalse(bom)

    def test_o_texto_do_erro_e_escapado(self):
        # o erro vem de excepções — pode trazer o que calhar
        linhas = radar.linhas_de_ultimos_erros(relogio="x <script> y")
        self.assertNotIn("<script>", linhas[0][1])

    def test_erro_comprido_e_cortado_com_reticencias(self):
        linhas = radar.linhas_de_ultimos_erros(analise="e" * 300)
        self.assertLess(len(linhas[0][1]), 120)
        self.assertIn("…", linhas[0][1])

    def test_a_triagem_e_a_vortal_tambem_se_veem(self):
        # 01/09/2026: o B15 e o B14 acrescentaram marca_erro() novos e
        # não os ligaram aqui — voltaram a ser erros que só existiam
        # para quem abrisse a base à mão. Foi assim que um "remote
        # rejected" de 31/08 esteve um dia inteiro sem aparecer em lado
        # nenhum.
        linhas = radar.linhas_de_ultimos_erros(
            triagem="2026-08-31 17:00: git push: cannot lock ref",
            vortal="2026-08-31 17:00: 503 na SearchTenders")
        self.assertEqual(len(linhas), 2)
        self.assertIn("triagem", linhas[0][0])
        self.assertIn("cannot lock ref", linhas[0][1])
        self.assertIn("Vortal", linhas[1][0])

    def test_erro_de_varias_linhas_fica_numa(self):
        # o git escreve em três linhas; metade dos 80 caracteres ia-se
        # em mudanças de linha e indentação que o HTML nem mostra
        linhas = radar.linhas_de_ultimos_erros(
            triagem="git push:\n  ! [remote rejected]\n  error: x")
        self.assertNotIn("\n", linhas[0][1])
        self.assertIn("git push: ! [remote rejected]", linhas[0][1])

    def test_os_indicadores_leem_as_sete_marcas(self):
        # o rótulo e a marca que o alimenta têm de andar juntos: já
        # aconteceu a função saber mostrar e ninguém lhe passar o valor
        import inspect
        fonte = inspect.getsource(radar.indicadores)
        for chave in ("ultimo_erro_relogio", "docs_ultimo_erro",
                      "analise_ultimo_erro", "token_ultimo_erro",
                      "ultimo_erro_triagem_git", "vortal_ultimo_erro",
                      "pecas_dr_ultimo_erro"):
            self.assertIn(chave, fonte)


class TestCopiaComMarca(BaseTemporaria):
    """C2 do saneamento de 30/08/2026: a falha da cópia de segurança
    fazia print() para uma consola que ninguém vê (pythonw). Passa a
    marca `ultima_copia`, visível na saúde dos indicadores."""

    def test_falha_grava_marca_com_data(self):
        def rebenta(guardar=7):
            raise OSError("disco cheio")
        import contextlib
        import io
        antigo = radar.copia_de_seguranca
        radar.copia_de_seguranca = rebenta
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertFalse(radar.copia_com_marca())
        finally:
            radar.copia_de_seguranca = antigo
        valor = radar.le_marca("ultima_copia")
        self.assertTrue(valor.startswith("falhou"))
        self.assertIn("disco cheio", valor)
        self.assertRegex(valor, r"\d{4}-\d{2}-\d{2}")   # diz de quando é

    def test_sucesso_grava_ok_com_o_nome_do_ficheiro(self):
        antigo = radar.copia_de_seguranca
        radar.copia_de_seguranca = lambda guardar=7: os.path.join(
            "copias", "radar-2026-08-30.db")
        try:
            self.assertTrue(radar.copia_com_marca())
        finally:
            radar.copia_de_seguranca = antigo
        self.assertEqual(radar.le_marca("ultima_copia"),
                         "ok: radar-2026-08-30.db")


class TestNavegacaoPorIntencoes(BaseTemporaria):
    """A navegação por intenções (31/08/2026): primeiro cinco itens, e
    na mesma noite quatro — o Afonso, depois de usar, fundiu a Triagem
    e a Pesquisa numa lista só ("ambas são a mesma coisa"). O que isto
    trava: repor os Indicadores na barra (saíram por decisão 11.6-A) ou
    voltar a separar a lista em duas páginas."""

    def test_dois_itens_por_ordem_de_uso(self):
        # a 8/09/2026 Alertas saiu do primeiro nivel: passou a seccao de
        # Configuracoes, que vive em baixo ao lado da zona de estado.
        # A 15/09/2026 "Anuncios" e "Em curso" fundiram-se em Concursos:
        # eram dois itens sobre a mesma escada, e enquanto o "Em curso"
        # foi `estado='interessa'`, sobre a mesma populacao -- que e a
        # pergunta que deu origem ao CRM.
        # A 16/09/2026 entrou o "Hoje" (fase 4 do docs/design.md) e SAIU
        # no mesmo dia, por decisao dele: a abertura fica onde estava, e
        # quem la leva e o logotipo. Um item ao lado da marca era o
        # mesmo destino duas vezes a 30px de distancia.
        self.assertEqual([n[0] for n in radar.NAV], ["anuncios", "mercado"])
        self.assertEqual([n[1] for n in radar.NAV], ["Concursos", "Mercado"])
        self.assertEqual(radar.NAV[0][2], radar.LISTA)
        html_ = radar.app.test_client().get(radar.LISTA).get_data(as_text=True)
        self.assertIn('href="/configuracoes"', html_)
        # e o "Hoje" nao volta a ser um botao da barra
        self.assertNotIn(">Hoje<", html_.split("</header>")[0])

    def test_o_logotipo_e_o_hoje_e_acende_la(self):
        """O caminho para a abertura e a marca (16/09/2026, decisao
        dele). Como e o unico, tem de se ver que e um: leva o `title` que
        diz o que e, e acende quando se esta la -- senao um logotipo e
        uma decoracao, e ninguem carrega em decoracoes."""
        cliente = radar.app.test_client()
        cabeca = cliente.get("/").get_data(as_text=True).split("</header>")[0]
        self.assertIn('class="logo on"', cabeca)
        self.assertIn('title="Hoje', cabeca)
        # e noutra pagina apaga-se
        cabeca = (cliente.get(radar.LISTA).get_data(as_text=True)
                  .split("</header>")[0])
        self.assertIn('class="logo "', cabeca)
        # as migalhas da abertura dizem "Hoje", e nao "Radar"
        self.assertIn("<em>Hoje</em>", radar.migalhas_de("inicio"))

    def test_indicadores_fora_da_navegacao(self):
        chaves = {n[0] for n in radar.NAV}
        chaves.update(v[0] for n in radar.NAV for v in n[3])
        self.assertNotIn("indicadores", chaves)
        # desde 13/09/2026 sao uma seccao de Configuracoes (so do admin)
        self.assertIn("indicadores", [c for c, _, _, _, _ in radar.SECCOES_CONFIG])
        self.assertIn("Configurações", radar.migalhas_de("configuracoes"))

    def test_so_o_calendario_sobrevive_como_vista(self):
        """15/09/2026, segunda arrumação do dia: o **quadro sai** e a
        **lista deixa de ser uma vista** para ser a própria página. Oito
        colunas e oito abas eram a mesma coisa duas vezes, e a diferença
        era o arrastar -- que só compensa quando se vê tudo ao mesmo
        tempo. Sobra o calendário, que é a única forma diferente de olhar
        para o mesmo: uma grelha de dias, para ver choques de datas."""
        # o Calendário é vista do item Concursos, que é o primeiro da
        # barra desde que o Hoje passou para o logotipo (16/09/2026)
        self.assertEqual([v[1] for v in radar.NAV[0][3]], ["Calendário"])
        self.assertEqual(radar.ITEM_DA_PAGINA["calendario"], "anuncios")
        self.assertNotIn("quadro", radar.ITEM_DA_PAGINA)

    def test_contratos_e_renovacoes_vivem_sob_mercado(self):
        self.assertEqual(radar.ITEM_DA_PAGINA["contratos"], "mercado")
        self.assertEqual(radar.ITEM_DA_PAGINA["renovacoes"], "mercado")

    def test_migalhas_das_vistas_agrupadas(self):
        # deixaram de ser separadores irmãos: são vistas de um item
        self.assertIn("Concursos", radar.migalhas_de("calendario"))
        self.assertIn("<em>Calendário</em>", radar.migalhas_de("calendario"))
        self.assertIn("Mercado", radar.migalhas_de("contratos"))

    def test_migalhas_da_lista_unica(self):
        """A lista é a primeira vista de Concursos e partilha a chave com
        o item, por isso a migalha diz só «Concursos» — e não
        «Concursos › Lista», que repetia a mesma palavra duas vezes."""
        self.assertEqual(radar.migalhas_de("anuncios"), "<em>Concursos</em>")

    def test_verificar_agora_so_na_lista_de_anuncios(self):
        # decisão 11.8-A, que sobrevive à fusão: o botão vai ao DR e os
        # novos aterram no por ver; no quadro e no calendário parecia
        # agir sobre o ecrã
        self.assertEqual(radar.PAGINAS_COM_VERIFICAR, ("anuncios",))


class TestAbasDaListaUnica(unittest.TestCase):
    """A fusão de 31/08/2026 (o Afonso, depois de usar): a Triagem e a
    Pesquisa são UMA lista, e as abas fazem o trabalho — por ver /
    interessados / abandonados / todos, com «já não é possível
    responder» a contar como abandonado. A armadilha de sempre
    mantém-se: o recorte da aba é da PÁGINA, aplicado por cima, e NUNCA
    de condicoes() — o motor serve os alertas e os filtros guardados,
    e o recorte lá dentro fazia um alerta deixar de ver, em silêncio,
    tudo o que hoje vê."""

    HOJE = datetime.date(2026, 8, 31)
    CFG = {"detalhe_dias": 60}

    def _aba(self, estado):
        return radar.condicao_da_aba(estado, hoje=self.HOJE, cfg=self.CFG)

    def test_condicoes_continua_sem_recorte_nenhum(self):
        onde, _ = radar.condicoes({})
        self.assertNotIn("data_pub", onde)
        self.assertNotIn("prazo >=", onde)

    def test_por_ver_e_novo_e_ainda_respondivel(self):
        frag, valores = self._aba("porver")
        self.assertIn("estado = 'novo'", frag)
        self.assertIn("prazo >= ?", frag)          # com prazo lido
        self.assertIn("data_pub >= ?", frag)       # sem prazo: publicação
        self.assertEqual(valores, ["2026-08-31", "2026-07-02"])
        self.assertEqual(frag.count("?"), len(valores))

    def test_o_cemiterio_e_so_o_que_ninguem_olhou(self):
        """A escada de 15/09/2026 parte a antiga aba «abandonados» em
        duas, e a distinção é o ponto todo (D6): «Não fomos» é uma
        DECISÃO, com motivo; «expirou sem ver» é o prazo a passar sem
        ninguém olhar. Estavam juntos, e a 15/09/2026 os 198 305
        «abandonados» eram TODOS expirados — zero decisões na base. Um
        número que junta as duas coisas faz o ruído do DR parecer
        trabalho da empresa."""
        frag, valores = self._aba("expirou")
        self.assertIn("estado = 'novo' AND NOT", frag)
        self.assertIn("NOT EXISTS", frag)     # e sem proposta: decidido não conta
        self.assertNotIn("descartado", frag)
        self.assertEqual(frag.count("?"), len(valores))

    def test_a_entrada_exclui_o_que_ja_tem_decisao(self):
        """Um anúncio que se pôs «a preparar proposta» não pode continuar
        em «Por ver» a pedir triagem. Antes da escada isto vinha de
        graça, porque o estado era do anúncio e mudava; agora a decisão
        vive noutra tabela e a exclusão tem de ser pedida."""
        frag, _ = self._aba("porver")
        self.assertIn("NOT EXISTS", frag)
        self.assertIn("propostas", frag)

    def test_uma_ranhura_da_empresa_conta_anuncios_com_proposta(self):
        frag, valores = self._aba("submetido")
        self.assertIn("EXISTS", frag)
        self.assertNotIn("NOT EXISTS", frag)
        self.assertEqual(valores, ["submetido"])

    def test_um_submetido_com_prazo_passado_nao_se_esconde(self):
        """A regra antiga da empresa, no vocabulário novo: uma proposta
        entregue à espera de decisão tem o prazo passado por definição, e
        esconder-se por isso era perder de vista o trabalho em curso. A
        ranhura da empresa não leva recorte de prazo nenhum."""
        frag, _ = self._aba("submetido")
        self.assertNotIn("prazo", frag)
        self.assertNotIn("data_pub", frag)

    def test_as_abas_antigas_traduzem_se_a_entrada(self):
        """As ligações antigas e os filtros guardados de antes de
        15/09/2026 trazem `?estado=novo` e `?estado=interessa`. Cair numa
        aba que não existe devolvia a lista vazia, sem nada a dizê-lo."""
        self.assertEqual(self._aba("novo"), self._aba("porver"))
        self.assertEqual(self._aba("interessa"), self._aba("analisar"))
        self.assertEqual(self._aba("descartado"), self._aba("nao_fomos"))

    def test_todos_nao_recorta_nada(self):
        self.assertEqual(self._aba(""), ("", []))

    def test_o_recorte_aplica_se_por_cima_do_motor(self):
        onde, valores = radar.com_recorte(
            *radar.condicoes({"q": "software", "estado": ""}),
            *self._aba("porver"))
        self.assertIn("estado = 'novo'", onde)
        self.assertEqual(onde.count("?"), len(valores))

    def test_sem_onde_o_recorte_abre_o_where(self):
        onde, valores = radar.com_recorte("", [], "estado = ?", ["novo"])
        self.assertTrue(onde.startswith(" WHERE"))
        self.assertEqual(valores, ["novo"])

    def test_sem_recorte_nada_muda(self):
        self.assertEqual(
            radar.com_recorte(" WHERE estado = ?", ["novo"], "", []),
            (" WHERE estado = ?", ["novo"]))

    def test_o_arquivo_do_interruptor_antigo_saiu_do_filtro(self):
        # o interruptor viveu entre as duas decisões de 31/08/2026 e
        # caiu com a lista única; um filtro guardado que o tenha fica
        # marcado parcial em todo o lado, declarado — nunca em silêncio
        self.assertNotIn("arquivo", radar.CAMPOS_FILTRO)
        self.assertNotIn("arquivo", radar.CAMPOS_POR_VISTA["anuncios"])
        _, fora = radar.filtro_para("arquivo=1&cpv=72", "anuncios")
        self.assertEqual(fora, ["arquivo"])

    def test_o_ambito_do_csv_nao_e_filtro(self):
        # o `ambito` das ligações de exportar é da vez, como a página:
        # colar-se ao filtro guardado prendia o recorte ao filtro
        self.assertIn("ambito", radar.CAMPOS_DA_VEZ)
        self.assertNotIn("ambito", radar.CAMPOS_FILTRO)


class TestVocabularioNoEcra(unittest.TestCase):
    """Andamento 2 do esqueleto (§7): um conceito, um nome. "análise"
    não aparece no ecrã — chama-se leitura — e os registos antigos do
    histórico, gravados como "análise", traduzem-se ao mostrar em vez
    de se reescrever a base."""

    def test_analise_traduz_se_para_leitura(self):
        self.assertEqual(radar._NOMES_ACCAO.get("análise"), "leitura")

    def test_accao_desconhecida_passa_como_esta(self):
        # o histórico tem acções livres ("interessa", "rectificado"):
        # traduzir só o que está no mapa, nunca calar o resto
        self.assertEqual(radar._NOMES_ACCAO.get("interessa", "interessa"),
                         "interessa")


class TestLigacaoContratoAnuncio(BaseTemporaria):
    """Atalho da §5: uma linha de contrato com n_anuncio leva à ficha do
    anúncio — mas SÓ quando o ref existe na base (4 917 dos 5 391
    comuns na última medição). Sem o crivo, 474 ligações davam 404."""

    def test_so_os_refs_que_existem(self):
        with radar.liga() as c:
            c.execute("INSERT INTO anuncios (ref, titulo) VALUES (?,?)",
                      ("21877/2026", "Ensaio"))
        achados = radar.refs_com_anuncio(
            ["21877/2026", "99999/2026", "", None])
        self.assertEqual(achados, {"21877/2026"})

    def test_lista_vazia_nao_consulta_nada(self):
        self.assertEqual(radar.refs_com_anuncio([]), set())
        self.assertEqual(radar.refs_com_anuncio(["", None]), set())


class TestModoFimDosContratos(unittest.TestCase):
    """Andamento 3 (decisão 6.1-A): as renovações fundiram-se nos
    contratos como modo «ver por fim estimado». O que estes testes
    travam: a janela entrar sem whitelist, os dois eixos do tempo
    voltarem a andar juntos, e a lista/CSV/gráficos filtrarem com
    contas diferentes."""

    def test_o_modo_le_se_da_query(self):
        self.assertTrue(radar.modo_fim({"ver": "fim"}))
        self.assertFalse(radar.modo_fim({}))
        self.assertFalse(radar.modo_fim({"ver": ""}))
        self.assertFalse(radar.modo_fim({"ver": "celebracao"}))

    def test_a_janela_passa_pela_whitelist(self):
        # meses vem da URL e entra por interpolação: fora da whitelist
        # volta à omissão, nunca texto no SQL
        frag = radar.condicao_do_modo({"ver": "fim", "meses": "12"})
        self.assertIn("+12 months", frag)
        frag = radar.condicao_do_modo({"ver": "fim", "meses": "DROP TABLE"})
        self.assertIn("+6 months", frag)
        frag = radar.condicao_do_modo({"ver": "fim", "meses": "7"})
        self.assertIn("+6 months", frag)

    def test_sem_modo_nao_ha_fragmento(self):
        self.assertEqual(radar.condicao_do_modo({}), "")

    def test_no_modo_fim_as_datas_ficam_de_lado(self):
        # dois eixos do tempo na mesma página confundiam (B03): de/ate
        # não entram no modo fim — e o ecrã di-lo, não é silêncio
        com_datas = radar.filtros_dos_contratos(
            {"ver": "fim", "q": "software", "de": "2024-01-01",
             "ate": "2025-01-01"})
        sem_datas = radar.filtros_dos_contratos(
            {"ver": "fim", "q": "software"})
        self.assertEqual(com_datas, sem_datas)
        self.assertNotIn("data_celebracao >=", com_datas[0])

    def test_no_modo_celebracao_as_datas_aplicam_se(self):
        onde, valores = radar.filtros_dos_contratos(
            {"q": "software", "de": "2024-01-01"})
        self.assertIn("data_celebracao", onde)
        self.assertIn("2024-01-01", valores)

    def test_placeholders_e_valores_concordam(self):
        # a janela do modo vai por interpolação (zero placeholders):
        # a ordem dos ? tem de continuar a bater com a dos valores
        onde, valores = radar.filtros_dos_contratos(
            {"ver": "fim", "q": "a|b", "cpv": "72", "min": "1000"})
        self.assertEqual(onde.count("?"), len(valores))

    def test_a_vista_do_modo_continua_sem_de_ate(self):
        # é a vista "renovacoes" que descreve o que o modo entende
        self.assertNotIn("de", radar.CAMPOS_POR_VISTA["renovacoes"])
        self.assertNotIn("ate", radar.CAMPOS_POR_VISTA["renovacoes"])

    def test_os_dois_modos_estao_nas_abas_e_nao_tambem_na_barra(self):
        """A 16/09/2026 (fase 5) as sub-vistas do Mercado saíram da barra.

        «Contratos» e «Renovações» na barra eram os **mesmos** dois modos
        que as abas da página já ofereciam como «Por celebração» e «Por
        fim estimado» — a mesma escolha duas vezes, a 40px de distância e
        com nomes diferentes, o que a fazia ler como quatro opções quando
        são duas. E as sub-vistas só apareciam depois de se entrar no
        Mercado, que é onde as abas também estão: não eram atalho de
        lado nenhum.

        A distinção que fica: uma sub-vista na barra é uma **forma
        diferente de olhar** (o Calendário dos Concursos, uma grelha de
        dias); dois modos da mesma tabela são abas.
        """
        mercado = next(n for n in radar.NAV if n[0] == "mercado")
        # O que se guarda é a REGRA, e não o tuplo vazio: a 17/09/2026 o
        # Mercado ganhou a vista **Entidades** (fase 2 do
        # `docs/historico/CICLOS.md`), que passa nesta distinção — é
        # olhar para o mesmo mercado por quem, e não por contrato. Pregar
        # o `()` fazia este teste falhar por uma vista que ele devia
        # deixar passar.
        self.assertNotIn("renovacoes", [v[0] for v in mercado[3]])
        self.assertNotIn("contratos", [v[0] for v in mercado[3]])
        # o Calendário continua a ser vista de barra, que é o caso oposto
        concursos = next(n for n in radar.NAV if n[0] == "anuncios")
        self.assertEqual([v[0] for v in concursos[3]], ["calendario"])
        # e os dois modos continuam alcançáveis, pelas abas da página
        corpo = radar.app.test_client().get("/contratos").get_data(as_text=True)
        self.assertIn("ver=fim", corpo)
        self.assertIn("Por fim estimado", corpo)
        self.assertIn("Por celebração", corpo)

    def test_a_pagina_do_mercado_continua_a_acender_o_item_da_barra(self):
        """O `ITEM_DA_PAGINA` derivava das sub-vistas: tirá-las deixou a
        barra sem acender e as migalhas a dizer «Radar». A barra é
        hierarquia por cima das páginas, não um nome novo para elas."""
        self.assertEqual(radar.ITEM_DA_PAGINA["contratos"], "mercado")
        self.assertEqual(radar.ITEM_DA_PAGINA["renovacoes"], "mercado")
        self.assertIn("Mercado", radar.migalhas_de("contratos"))
        self.assertIn("Mercado", radar.migalhas_de("renovacoes"))
        # e uma folha continua a pendurar-se por baixo
        self.assertIn("procurar", radar.migalhas_de("contratos", "procurar"))


class TestVoltaComModo(unittest.TestCase):
    """O «volta» de guardar um filtro no modo fim é «/contratos?ver=fim»
    — juntar a consulta com um segundo «?» partia a URL e o modo
    perdia-se ao gravar."""

    def test_rota_com_query_junta_com_e_comercial(self):
        destino = radar.volta_para("/contratos?ver=fim",
                                   consulta="q=software").headers["Location"]
        self.assertEqual(destino, "/contratos?ver=fim&q=software")
        self.assertEqual(destino.count("?"), 1)

    def test_rota_simples_continua_igual(self):
        destino = radar.volta_para("/contratos",
                                   consulta="q=x").headers["Location"]
        self.assertEqual(destino, "/contratos?q=x")


class TestBlocosPartilhados(unittest.TestCase):
    """Decisões 6.3-A e 6.4-A: a faixa do CPV activo e o selector de
    procedimento passaram a UM bloco cada. Eram três/quatro cópias «com
    pequenas diferenças» — o principal gerador de bugs do projecto."""

    def test_faixa_vazia_sem_cpv(self):
        self.assertEqual(radar.faixa_cpv_activo({}, "/x"), "")
        self.assertEqual(radar.faixa_cpv_activo({"cpv": "  "}, "/x"), "")

    def test_faixa_diz_o_cpv_e_escapa(self):
        saiu = radar.faixa_cpv_activo({"cpv": "72<b>"}, "/contratos?a=1")
        self.assertIn("72&lt;b&gt;", saiu)
        self.assertIn("tirar", saiu)
        self.assertIn("/contratos?a=1", saiu)

    def test_selector_marca_o_actual_e_escapa(self):
        saiu = radar.selector_procedimento(
            ["Concurso público", "Ajuste <directo>"], "Concurso público")
        self.assertIn("selected", saiu)
        self.assertIn("Ajuste &lt;directo&gt;", saiu)
        self.assertNotIn("Ajuste <directo>", saiu)

    def test_selector_com_rotulo_proprio(self):
        saiu = radar.selector_procedimento([], "", "procedimento: todos")
        self.assertIn("procedimento: todos", saiu)


class TestSerieDeErros(BaseTemporaria):
    """C3: as marcas *_ultimo_erro são sobrescritas — um dia mau apagava
    a história toda. marca_erro() guarda a marca (o ecrã lê-a) E uma
    linha na tabela `erros`; a poda do iniciar_db() guarda os últimos
    ~200 por tipo, e tem de guardar os RECENTES, não os primeiros."""

    def test_marca_e_serie_ao_mesmo_tempo(self):
        radar.marca_erro("x_ultimo_erro", "ensaio", "primeiro")
        radar.marca_erro("x_ultimo_erro", "ensaio", "segundo")
        self.assertEqual(radar.le_marca("x_ultimo_erro"), "segundo")
        with radar.liga() as c:
            serie = [r["texto"] for r in c.execute(
                "SELECT texto FROM erros WHERE tipo='ensaio' ORDER BY id")]
        self.assertEqual(serie, ["primeiro", "segundo"])

    def test_a_poda_e_por_tipo_e_guarda_os_recentes(self):
        with radar.liga() as c:
            c.executemany(
                "INSERT INTO erros (quando,tipo,texto) VALUES (?,?,?)",
                [("2026-01-01", "a", str(i)) for i in range(250)]
                + [("2026-01-01", "b", "único")])
        radar.iniciar_db()          # a poda corre sempre, idempotente
        with radar.liga() as c:
            na = c.execute("SELECT COUNT(*) n FROM erros "
                           "WHERE tipo='a'").fetchone()["n"]
            nb = c.execute("SELECT COUNT(*) n FROM erros "
                           "WHERE tipo='b'").fetchone()["n"]
            menor = c.execute("SELECT MIN(CAST(texto AS INT)) m FROM erros "
                              "WHERE tipo='a'").fetchone()["m"]
        self.assertEqual(na, 200)
        self.assertEqual(nb, 1)     # um tipo raro não é podado pelo cheio
        self.assertEqual(menor, 50)  # caíram os 50 mais ANTIGOS


class TestExpiracaoDoToken(BaseTemporaria):
    """E4: a frequência de expiração do token nunca foi reconstruível —
    marcas sobrescritas, token opaco. O registo guarda quando expirou e
    de quando era a captura; é o instrumento de medida que faltava."""

    def _com_pasta_temporaria(self, criar_captura):
        with unittest.mock.patch.object(radar, "BASE_DIR", self.pasta):
            if criar_captura:
                with open(os.path.join(self.pasta, "curl_DR.txt"),
                          "w", encoding="utf-8") as f:
                    f.write("curl 'https://exemplo'")
            radar.registar_expiracao_token("curl_DR", "sem JSON")

    def test_regista_com_a_idade_da_captura(self):
        self._com_pasta_temporaria(criar_captura=True)
        valor = radar.le_marca("token_ultimo_erro")
        self.assertIn("sem JSON", valor)
        self.assertIn("captura de", valor)
        self.assertIn("dias", valor)
        with radar.liga() as c:
            n = c.execute("SELECT COUNT(*) n FROM erros "
                          "WHERE tipo='token'").fetchone()["n"]
        self.assertEqual(n, 1)

    def test_sem_captura_regista_na_mesma(self):
        # a captura pode ter sido apagada: o registo do evento nao pode
        # depender do ficheiro existir
        self._com_pasta_temporaria(criar_captura=False)
        self.assertEqual(radar.le_marca("token_ultimo_erro"), "sem JSON")


class TestPecasDoDR(BaseTemporaria):
    """02/09/2026: o "token" das capturas era tratado como coisa de
    sessão que expira e obriga a refazer a captura no DevTools. Medido
    contra o portal (medir_captura.py): é o AnonymousCSRFToken publicado
    no OutSystems.js, a moduleVersion não tranca, e a única tranca é a
    apiVersion, que vive no script do ecrã listado no moduleinfo. Três
    GETs renovam tudo. O erro que se trava: voltar a ler estas peças da
    captura, ou registar "expirou" sem antes tentar renovar."""

    URL = radar.ACAO
    MODULEINFO = {"manifest": {"versionToken": "Y0NBIj4uVIBdNjR3KejkaA",
                               "urlVersions": {
                                   "/dr/scripts/OutSystems.js": "?EU4N",
                                   "/dr/scripts/dr.Pesquisas.PesquisaResultado.mvc.js": "?DQoe"}}}
    OUTSYSTEMS = ('e.CSRFHeader="X-CSRFToken",e.AnonymousCSRFToken='
                  '"T6C+9iB49TLra4jEsMeSckDMNhQ=",e.getCSRFToken=function')
    SCRIPT = ('return controller.callDataAction("DataActionGetPesquisas", '
              '"screenservices/dr/Pesquisas/PesquisaResultado/'
              'DataActionGetPesquisas", "PRsQKjEXDVBC3ZSqkS8k6A", '
              'function (b) {')
    PEDIDO = {"url": URL, "headers": {"Cookie": "nr2Users=crf%3dvelho",
                                      "x-csrftoken": "velho",
                                      "Content-Type": "application/json"},
              "body": ""}
    MOLDE = {"versionInfo": {"moduleVersion": "9DeZ", "apiVersion": "PRsQ"},
             "screenData": {"variables": {"StartIndex": 0}}}

    def setUp(self):
        super().setUp()
        self._limpar()

    def tearDown(self):
        self._limpar()
        super().tearDown()

    def _limpar(self):
        radar._PECAS_DR["quando"] = 0.0
        radar._PECAS_DR["token"] = radar._PECAS_DR["modulo"] = ""
        radar._PECAS_DR["api"].clear()

    def _buscar(self, urls, rebenta=False, script=None):
        teste = self

        def buscar(url, **kw):
            urls.append(url)
            if rebenta:
                raise radar.requests.RequestException("sem rede")

            class R:
                text = ""

                def json(self):
                    return teste.MODULEINFO
            r = R()
            if "OutSystems.js" in url:
                r.text = teste.OUTSYSTEMS
            elif ".mvc.js" in url:
                r.text = teste.SCRIPT if script is None else script
            return r
        return buscar

    def test_script_do_ecra_segue_a_convencao_do_outsystems(self):
        self.assertEqual(
            radar.script_do_ecra(self.URL),
            ("/dr/scripts/dr.Pesquisas.PesquisaResultado.mvc.js",
             "DataActionGetPesquisas"))
        self.assertEqual(
            radar.script_do_ecra("https://diariodarepublica.pt/dr/screenservices/"
                                 "dr/Legislacao_Conteudos/Conteudo_Detalhe/"
                                 "DataActionGetAllConteudoDetalheData"),
            ("/dr/scripts/dr.Legislacao_Conteudos.Conteudo_Detalhe.mvc.js",
             "DataActionGetAllConteudoDetalheData"))
        self.assertEqual(radar.script_do_ecra("https://x/y"), ("", ""))

    def test_api_version_le_se_do_script_real(self):
        # o pedaco e o que o portal devolveu a 02/09/2026, tal e qual
        self.assertEqual(radar.api_version_do_script(
            self.SCRIPT, "DataActionGetPesquisas"), "PRsQKjEXDVBC3ZSqkS8k6A")
        self.assertEqual(radar.api_version_do_script(self.SCRIPT, "Outra"), "")

    def test_tres_gets_renovam_as_tres_pecas(self):
        urls = []
        pecas = radar.renovar_pecas_dr([self.URL], buscar=self._buscar(urls))
        self.assertEqual(pecas["token"], "T6C+9iB49TLra4jEsMeSckDMNhQ=")
        self.assertEqual(pecas["modulo"], "Y0NBIj4uVIBdNjR3KejkaA")
        self.assertEqual(pecas["api"][self.URL], "PRsQKjEXDVBC3ZSqkS8k6A")
        self.assertEqual(len(urls), 3)
        # os scripts pedem-se com a versao do manifesto, senao vem a cache
        self.assertTrue(urls[1].endswith("/dr/scripts/OutSystems.js?EU4N"))
        self.assertTrue(urls[2].endswith("PesquisaResultado.mvc.js?DQoe"))

    def test_a_cache_poupa_os_gets_e_forcar_ignora_a(self):
        urls = []
        radar.renovar_pecas_dr([self.URL], buscar=self._buscar(urls))
        radar.renovar_pecas_dr([self.URL], buscar=self._buscar(urls))
        self.assertEqual(len(urls), 3)
        radar.renovar_pecas_dr([self.URL], forcar=True,
                               buscar=self._buscar(urls))
        self.assertEqual(len(urls), 6)

    def test_sem_rede_da_none_e_fica_na_saude(self):
        pecas = radar.renovar_pecas_dr([self.URL],
                                       buscar=self._buscar([], rebenta=True))
        self.assertIsNone(pecas)
        marca = radar.le_marca("pecas_dr_ultimo_erro", "")
        self.assertIn("sem rede", marca)
        linhas = radar.linhas_de_ultimos_erros(pecas_dr=marca)
        self.assertEqual(len(linhas), 1)
        self.assertIn("peças do DR", linhas[0][0])

    def test_script_sem_a_accao_e_erro_e_nao_peca_vazia(self):
        pecas = radar.renovar_pecas_dr(
            [self.URL], buscar=self._buscar([], script="var x = 1;"))
        self.assertIsNone(pecas)
        self.assertIn("apiVersion", radar.le_marca("pecas_dr_ultimo_erro", ""))

    def test_pedido_renovado_tira_o_cookie_e_poe_as_pecas(self):
        pecas = {"token": "NOVO", "modulo": "M2", "api": {self.URL: "A2"}}
        cabecalhos, corpo = radar.pedido_renovado(self.PEDIDO, self.MOLDE, pecas)
        self.assertNotIn("Cookie", cabecalhos)
        self.assertNotIn("x-csrftoken", cabecalhos)
        self.assertEqual(cabecalhos["X-CSRFToken"], "NOVO")
        self.assertEqual(cabecalhos["Content-Type"], "application/json")
        self.assertEqual(corpo["versionInfo"],
                         {"moduleVersion": "M2", "apiVersion": "A2"})
        # o molde de quem chama nao muda: e reutilizado pagina a pagina
        self.assertEqual(self.MOLDE["versionInfo"]["apiVersion"], "PRsQ")
        self.assertEqual(corpo["screenData"], self.MOLDE["screenData"])

    def test_sem_pecas_o_pedido_e_a_captura_tal_como_esta(self):
        cabecalhos, corpo = radar.pedido_renovado(self.PEDIDO, self.MOLDE, None)
        self.assertIs(cabecalhos, self.PEDIDO["headers"])
        self.assertIs(corpo, self.MOLDE)

    def _resposta(self, tipo, dados=None, texto=""):
        class R:
            status_code = 200
            headers = {"Content-Type": tipo}
            text = texto

            def json(self):
                if dados is None:
                    raise ValueError("nada")
                return dados
        return R()

    def _renovar(self, registo):
        def renovar(urls, forcar=False):
            registo.append(forcar)
            return {"token": "T", "modulo": "M", "api": {self.URL: "A"}}
        return renovar

    def test_hasapiversionchanged_renova_a_forca_e_repete_uma_vez(self):
        respostas = [self._resposta("application/json",
                                    {"versionInfo": {"hasApiVersionChanged": True},
                                     "data": {}}),
                     self._resposta("application/json", {"data": {"ok": 1}})]
        enviados, forcados = [], []

        def enviar(url, headers=None, data=None, timeout=None):
            enviados.append((headers, json.loads(data)))
            return respostas.pop(0)
        dados, erro = radar.perguntar_ao_dr(self.PEDIDO, self.MOLDE, enviar,
                                            self._renovar(forcados))
        self.assertEqual(erro, "")
        self.assertEqual(dados, {"data": {"ok": 1}})
        self.assertEqual(forcados, [False, True])
        self.assertEqual(len(enviados), 2)
        for cabecalhos, corpo in enviados:
            self.assertNotIn("Cookie", cabecalhos)
            self.assertEqual(cabecalhos["X-CSRFToken"], "T")
            self.assertEqual(corpo["versionInfo"]["apiVersion"], "A")

    def test_a_casca_duas_vezes_e_so_ai_e_expiracao(self):
        antigo = radar.AMOSTRAS
        radar.AMOSTRAS = os.path.join(self.pasta, "amostras")
        try:
            enviados = []

            def enviar(url, headers=None, data=None, timeout=None):
                enviados.append(1)
                return self._resposta("text/html", texto="<html>casca</html>")
            dados, erro = radar.perguntar_ao_dr(self.PEDIDO, self.MOLDE, enviar,
                                                self._renovar([]))
            self.assertIsNone(dados)
            self.assertEqual(erro, "casca")
            self.assertEqual(len(enviados), 2)
            with open(os.path.join(radar.AMOSTRAS, "resposta_inesperada.txt"),
                      encoding="utf-8") as f:
                self.assertIn("casca", f.read())
        finally:
            radar.AMOSTRAS = antigo

    def test_sem_renovacao_manda_a_captura_e_nao_grita(self):
        # sem rede para os GETs (ou o DR mudou de forma) o pedido segue
        # com a captura tal como esta: e o comportamento de sempre
        enviados = []

        def enviar(url, headers=None, data=None, timeout=None):
            enviados.append(headers)
            return self._resposta("application/json", {"data": {"ok": 1}})
        dados, erro = radar.perguntar_ao_dr(self.PEDIDO, self.MOLDE, enviar,
                                            lambda urls, forcar=False: None)
        self.assertEqual(erro, "")
        self.assertEqual(enviados[0]["x-csrftoken"], "velho")
        self.assertIn("Cookie", enviados[0])

    def test_sem_rede_no_post_e_rede_e_nao_expiracao(self):
        def enviar(url, headers=None, data=None, timeout=None):
            raise radar.requests.RequestException("timeout")
        dados, erro = radar.perguntar_ao_dr(self.PEDIDO, self.MOLDE, enviar,
                                            self._renovar([]))
        self.assertIsNone(dados)
        self.assertTrue(erro.startswith("rede: timeout"))

    def test_os_quatro_pedidos_ao_dr_passam_pela_porta_unica(self):
        # e a unica forma de a renovacao valer para todos: um POST solto
        # ao DR volta a ler o token da captura
        for nome in ("recolher", "ler_detalhe_de", "ler_detalhes",
                     "reler_marcados"):
            fonte = inspect.getsource(getattr(radar, nome))
            self.assertIn("perguntar_ao_dr(", fonte, nome)
            self.assertNotIn("requests.post(", fonte, nome)


class TestExportacaoDaTriagem(BaseTemporaria):
    """B15: a triagem é o único dado irrecuperável e vivia só no disco.
    A exportação é determinística (é o que faz o git diff mostrar o que
    mudou hoje), o restauro é idempotente, e um ref que ainda não
    exista na base NÃO se inventa — fica no relatório, senão o restauro
    parecia completo e não era."""

    def _semear(self):
        with radar.liga() as c:
            for ref, titulo in (("1/2026", "Um"), ("2/2026", "Dois"),
                                ("3/2026", "Por ver — não entra")):
                c.execute("INSERT INTO anuncios (ref, titulo) VALUES (?,?)",
                          (ref, titulo))
        # a decisão da empresa mora na proposta desde 15/09/2026, e é ela a
        # parte irrecuperável: o DR não devolve o preço que se propôs
        um = radar.criar_proposta("1/2026", estado="submetido")
        radar.gravar_campos_da_proposta(um, ["responsavel", "valor_proposta"],
                                        ["Afonso", "118.500,00 EUR"])
        radar.criar_proposta("2/2026", estado="nao_fomos")
        with radar.liga() as c:
            c.execute("INSERT INTO etiquetas (id, nome, cor) "
                      "VALUES (7, 'urgente', '#c0392b')")
            c.execute("INSERT INTO anuncio_etiquetas (ref, etiqueta_id) "
                      "VALUES ('1/2026', 7)")
            c.execute("INSERT INTO historico (ref, quem, accao, detalhe, "
                      "quando) VALUES ('1/2026', 'Afonso', 'interessa', "
                      "'', '2026-08-31 10:00')")
            c.execute("INSERT INTO filtros_guardados (id, nome, consulta, "
                      "alerta, quem, criado_em) VALUES "
                      "(3, 'CPV IT', 'cpv=72&estado=novo', 1, 'Afonso', "
                      "'2026-08-30 10:00')")
            c.execute("INSERT INTO alertas_vistos (filtro_id, ref, "
                      "visto_em, enviado_em) VALUES (3, '1/2026', "
                      "'2026-08-31', 'acervo')")

    def test_exporta_deterministico_e_so_o_que_conta(self):
        self._semear()
        caminho = os.path.join(self.pasta, "triagem.jsonl")
        n, _ = radar.exportar_triagem(caminho)
        with open(caminho, encoding="utf-8") as f:
            primeira = f.read()
        # o por ver sem proposta não entra: refaz-se do DR
        self.assertNotIn("3/2026", primeira)
        self.assertIn("1/2026", primeira)
        self.assertIn("Afonso", primeira)
        # determinístico: exportar duas vezes dá o MESMO ficheiro
        radar.exportar_triagem(caminho)
        with open(caminho, encoding="utf-8") as f:
            segunda = f.read()
        self.assertEqual(primeira, segunda)
        self.assertGreater(n, 0)

    def test_restauro_repoe_e_diz_o_que_ficou_por_repor(self):
        self._semear()
        caminho = os.path.join(self.pasta, "triagem.jsonl")
        radar.exportar_triagem(caminho)
        # a "base refeita pela recolha": só um dos anúncios voltou
        with radar.liga() as c:
            c.execute("DELETE FROM anuncios")
            c.execute("DELETE FROM propostas")
            c.execute("DELETE FROM etiquetas")
            c.execute("DELETE FROM anuncio_etiquetas")
            c.execute("DELETE FROM historico")
            c.execute("DELETE FROM filtros_guardados")
            c.execute("DELETE FROM alertas_vistos")
            c.execute("INSERT INTO anuncios (ref, titulo) VALUES "
                      "('1/2026', 'Um, voltado do DR')")
        escritas, por_repor = radar.repor_triagem(caminho)
        self.assertGreater(escritas, 0)
        # o 2/2026 ainda não voltou do DR: fica no relatório, não se
        # inventa
        self.assertIn("2/2026", por_repor.get("propostas", []))
        p = radar.propostas_de("1/2026")[0]
        self.assertEqual((p["estado"], p["responsavel"], p["valor_proposta"]),
                         ("submetido", "Afonso", "118.500,00 EUR"))
        with radar.liga() as c:
            self.assertEqual(c.execute(
                "SELECT COUNT(*) n FROM anuncio_etiquetas").fetchone()["n"],
                1)
            f = c.execute("SELECT id, alerta FROM filtros_guardados "
                          "WHERE nome='CPV IT'").fetchone()
            self.assertEqual((f["id"], f["alerta"]), (3, 1))
            # a marca de já-avisado voltou: o primeiro resumo não traz
            # o acervo outra vez
            self.assertEqual(c.execute(
                "SELECT COUNT(*) n FROM alertas_vistos").fetchone()["n"], 1)

    def test_restauro_e_idempotente(self):
        self._semear()
        caminho = os.path.join(self.pasta, "triagem.jsonl")
        radar.exportar_triagem(caminho)
        with radar.liga() as c:
            antes = c.execute("SELECT COUNT(*) n FROM historico").fetchone()["n"]
        radar.repor_triagem(caminho)
        radar.repor_triagem(caminho)     # segunda volta: nada duplica
        with radar.liga() as c:
            # o histórico compara-se com o que havia, e não com um número
            # escrito à mão: pôr um concurso na escada já escreve lá
            self.assertEqual(c.execute(
                "SELECT COUNT(*) n FROM historico").fetchone()["n"], antes)
            self.assertEqual(c.execute(
                "SELECT COUNT(*) n FROM anuncio_etiquetas").fetchone()["n"],
                1)
            # e as propostas não se duplicam: o índice único por
            # (ref, lote) é o que trava isso
            self.assertEqual(c.execute(
                "SELECT COUNT(*) n FROM propostas").fetchone()["n"], 2)

    def test_sem_ficheiro_diz_o_e_nao_rebenta(self):
        escritas, por_repor = radar.repor_triagem(
            os.path.join(self.pasta, "nao-existe.jsonl"))
        self.assertEqual(escritas, 0)
        self.assertIn("ficheiro", por_repor)


class TestEscadaDaEmpresa(unittest.TestCase):
    """O vocabulário da empresa (D1 do docs/historico/CRM.md, 15/09/2026):
    oito palavras, e duas ranhuras nas pontas que não são estados. Nada
    aqui toca na base — é tudo vocabulário."""

    def test_as_oito_palavras_sao_as_que_ele_disse(self):
        # a lista dele, por estas palavras e por esta ordem
        self.assertEqual(
            [r for _, r in radar.ESTADOS_DA_EMPRESA],
            ["Por analisar", "A preparar proposta", "Submetido",
             "Relatório preliminar", "Ganho", "Perdido", "Não fomos",
             "Cancelado"])

    def test_as_chaves_das_seis_primeiras_sao_as_do_quadro_antigo(self):
        """De propósito: as seis primeiras chaves são as que `fases.papel`
        usava, para a passagem dos cartões do quadro ser por igualdade e
        não por um mapa a adivinhar. A tabela `fases` saiu no mesmo dia,
        mas as chaves ficam -- são o que um `triagem.jsonl` de antes traz
        escrito, e mudá-las agora era partir o restauro em silêncio."""
        self.assertEqual(
            list(radar.CHAVES_DA_EMPRESA[:6]),
            ["analisar", "proposta", "submetido", "relatorio", "ganho",
             "perdido"])

    def test_a_escada_tem_a_entrada_e_o_cemiterio_nas_pontas(self):
        """E nenhum dos dois é estado da empresa: não há proposta nenhuma
        neles. Sem a entrada, os 1 263 por ver caíam em «Por analisar» e
        o funil deixava de dizer o que diz; sem o cemitério, 198 305
        anúncios que ninguém olhou contavam como decisão da empresa."""
        self.assertEqual(radar.ESCADA[0], ("porver", "Por ver"))
        self.assertEqual(radar.ESCADA[-1], ("expirou", "Expirou sem ver"))
        self.assertEqual(len(radar.ESCADA), 10)
        self.assertNotIn("porver", radar.CHAVES_DA_EMPRESA)
        self.assertNotIn("expirou", radar.CHAVES_DA_EMPRESA)

    def test_fechados_e_abertos_cobrem_as_oito_sem_sobrar(self):
        self.assertEqual(sorted(radar.ESTADOS_FECHADOS + radar.ESTADOS_ABERTOS),
                         sorted(radar.CHAVES_DA_EMPRESA))
        self.assertEqual(set(radar.ESTADOS_FECHADOS),
                         {"ganho", "perdido", "nao_fomos", "cancelado"})

    def test_estado_invalido_devolve_vazio_em_vez_de_rebentar(self):
        """É por aqui que se valida o que vem de um formulário: devolver
        "" deixa a rota responder com aviso, e rebentar dava um 500."""
        self.assertEqual(radar.estado_da_empresa("inventado"), "")
        self.assertEqual(radar.estado_da_empresa(""), "")
        self.assertEqual(radar.estado_da_empresa(None), "")
        self.assertEqual(radar.estado_da_empresa("ganho"), "Ganho")

    def test_cada_pedido_e_cada_motivo_e_de_um_estado_que_existe(self):
        """As duas listas andam ao lado da escada e é fácil deixar lá uma
        chave velha depois de renomear um estado — ela cala-se e o campo
        nunca mais aparece."""
        for chave in list(radar.PEDIDO_DO_ESTADO) + list(radar.MOTIVOS_DO_ESTADO):
            self.assertIn(chave, radar.CHAVES_DA_EMPRESA, chave)
        for chave in radar.ESTADOS_COM_PROPOSTO:
            self.assertIn(chave, radar.CHAVES_DA_EMPRESA, chave)


class TestPropostas(BaseTemporaria):
    """A tabela `propostas` (etapa 1 do CRM, 15/09/2026): o que a empresa
    está a fazer, que não é o estado de um anúncio. Existe por causa dos
    lotes (D3) e das propostas sem anúncio do DR (D2)."""

    def _anuncio(self, ref="60/2026", **campos):
        valores = {"titulo": "Aquisição de software",
                   "entidade": "Câmara de Lisboa",
                   "preco_base": "118.500,00 EUR", "data_pub": "2026-09-01"}
        valores.update(campos)
        with radar.liga() as c:
            c.execute("INSERT INTO anuncios (ref,%s) VALUES (?%s)"
                      % (",".join(valores), ",?" * len(valores)),
                      [ref] + list(valores.values()))
        return ref

    def _tarefas(self):
        with radar.liga() as c:
            return c.execute("SELECT COUNT(*) n FROM tarefas").fetchone()["n"]

    def test_apagar_uma_proposta_leva_as_tarefas_dela(self):
        """As `tarefas` não têm chave estrangeira com ON DELETE CASCADE, e
        até 16/09/2026 os **três** sítios que apagam propostas deixavam
        as tarefas automáticas atrás.

        Apanhado a desfazer duas propostas criadas por engano na base
        dele: as propostas foram-se e duas tarefas ficaram a apontar para
        um `proposta_id` que já não existe. Não é só lixo — a página de
        abertura lê esta tabela, e uma tarefa órfã aparecia lá como
        trabalho de uma proposta que não há.
        """
        ref = self._anuncio(prazo="2026-10-20")
        id_ = radar.criar_proposta(ref, estado="analisar")
        radar.sincronizar_tarefas(id_)
        self.assertGreater(self._tarefas(), 0, "a sincronização não criou nada")
        with radar.liga() as c:
            radar.apagar_propostas(c, "id=?", (id_,))
        self.assertEqual(self._tarefas(), 0)

    def test_o_voltar_a_por_ver_nao_deixa_tarefas_atras(self):
        """O caminho por onde o erro apareceu: o selector da linha em
        «tirar da escada»."""
        ref = self._anuncio(prazo="2026-10-20")
        id_ = radar.criar_proposta(ref, estado="analisar")
        radar.sincronizar_tarefas(id_)
        self.assertGreater(self._tarefas(), 0)
        r = radar.app.test_client().post("/escada/" + ref,
                                         data={"estado": "porver"})
        self.assertIn(r.status_code, (302, 303))
        self.assertEqual(self._tarefas(), 0)

    def test_o_arranque_limpa_as_orfas_que_ja_existiam(self):
        """A base dele já as tinha. A limpeza é no `iniciar_db()`, é
        idempotente, e **não** toca nas tarefas escritas à mão sem
        proposta (`proposta_id` NULL), que não são órfãs."""
        with radar.liga() as c:
            c.execute("INSERT INTO tarefas (proposta_id, ref, o_que, quando) "
                      "VALUES (999, '1/2026', 'órfã', '2026-10-01')")
            c.execute("INSERT INTO tarefas (proposta_id, ref, o_que, quando) "
                      "VALUES (NULL, '1/2026', 'à mão', '2026-10-01')")
        self.assertEqual(self._tarefas(), 2)
        radar.iniciar_db()
        with radar.liga() as c:
            ficaram = [r["o_que"] for r in c.execute("SELECT o_que FROM tarefas")]
        self.assertEqual(ficaram, ["à mão"])

    def test_criar_copia_do_anuncio_o_que_a_proposta_tem_de_ter_por_si(self):
        """Uma proposta sem `ref` tem de trazer entidade e título, e uma
        com `ref` não pode depender de um JOIN para se mostrar numa lista
        de mil linhas."""
        self._anuncio()
        p = radar.proposta(radar.criar_proposta("60/2026"))
        self.assertEqual(p["entidade"], "Câmara de Lisboa")
        self.assertEqual(p["titulo"], "Aquisição de software")
        self.assertEqual(p["preco_base"], "118.500,00 EUR")
        self.assertEqual(p["estado"], "analisar")

    def test_criar_duas_vezes_o_mesmo_da_a_mesma_proposta(self):
        """Um duplo clique no «preparar proposta» punha o mesmo negócio
        duas vezes no funil, e a soma da coluna passava a mentir."""
        self._anuncio()
        um = radar.criar_proposta("60/2026")
        dois = radar.criar_proposta("60/2026")
        self.assertEqual(um, dois)
        with radar.liga() as c:
            self.assertEqual(c.execute(
                "SELECT COUNT(*) n FROM propostas").fetchone()["n"], 1)

    def test_lotes_diferentes_do_mesmo_anuncio_sao_propostas_diferentes(self):
        """D3: um concurso de três lotes pode acabar com o L1 ganho e o
        L2 perdido. Um anúncio, uma linha e um estado não cabem dois
        resultados."""
        self._anuncio()
        l1 = radar.criar_proposta("60/2026", lote=1)
        l2 = radar.criar_proposta("60/2026", lote=2)
        self.assertNotEqual(l1, l2)
        # o preco proposto e o motivo viajam no mesmo pedido: a ranhura
        # exige-os (D4 do docs/historico/CICLOS.md)
        radar.mover_proposta(l1, "ganho", campos={"valor_proposta": "118.500,00 EUR"})
        radar.mover_proposta(l2, "perdido",
                             campos={"valor_proposta": "118.500,00 EUR",
                                     "motivo": radar.MOTIVOS_PERDA[0]})
        estados = {p["lote"]: p["estado"] for p in radar.propostas_de("60/2026")}
        self.assertEqual(estados, {1: "ganho", 2: "perdido"})

    def test_duas_propostas_sem_anuncio_nao_colidem(self):
        """D2: duas consultas prévias distintas não são a mesma coisa só
        por nenhuma ter anúncio. Em UNIQUE, dois NULL não são iguais — e
        é disso que isto depende."""
        uma = radar.criar_proposta(entidade="IPL", titulo="Consulta prévia A",
                                   porque_sem_ref="consulta prévia")
        outra = radar.criar_proposta(entidade="IPL", titulo="Consulta prévia B",
                                     porque_sem_ref="consulta prévia")
        self.assertNotEqual(uma, outra)
        with radar.liga() as c:
            self.assertEqual(c.execute(
                "SELECT COUNT(*) n FROM propostas").fetchone()["n"], 2)

    def test_a_proposta_de_um_lote_leva_o_preco_do_lote(self):
        """Visto no ecrã a 15/09/2026: a proposta do lote 2 mostrava os
        212 400 EUR do procedimento inteiro — o número do anúncio numa
        linha que representa uma parte dele. É a mentira mais cara que
        esta tabela pode contar: é deste número que sai o desvio face ao
        proposto, e é com ele que a etapa 4 há-de comparar o que o
        Portal BASE adjudicou, que também é por lote."""
        self._anuncio()
        with radar.liga() as c:
            c.execute("UPDATE anuncios SET lotes=? WHERE ref='60/2026'",
                      (json.dumps([{"n": 1, "descricao": "Norte",
                                    "preco_base": "70.000,00 EUR"},
                                   {"n": 2, "descricao": "Sul",
                                    "preco_base": "48.500,00 EUR"}]),))
        l1 = radar.proposta(radar.criar_proposta("60/2026", lote=1))
        l2 = radar.proposta(radar.criar_proposta("60/2026", lote=2))
        self.assertEqual(l1["preco_base"], "70.000,00 EUR")
        self.assertEqual(l2["preco_base"], "48.500,00 EUR")

    def test_sem_preco_do_lote_lido_fica_vazio_e_nao_o_do_todo(self):
        """Um campo em branco pergunta-se; um número errado acredita-se."""
        self._anuncio()
        with radar.liga() as c:
            c.execute("UPDATE anuncios SET lotes=? WHERE ref='60/2026'",
                      (json.dumps([{"n": 1, "descricao": "Único"}]),))
        p = radar.proposta(radar.criar_proposta("60/2026", lote=1))
        self.assertEqual(p["preco_base"], "")

    def test_o_conjunto_e_o_anuncio_sem_lotes_levam_o_preco_do_todo(self):
        self._anuncio()
        conjunto = radar.proposta(radar.criar_proposta("60/2026", lote=0))
        self.assertEqual(conjunto["preco_base"], "118.500,00 EUR")

    def test_fechar_carimba_e_reabrir_limpa(self):
        """O `fechada_em` é o que faz o funil esvaziar. E um «Perdido»
        que se reabre por impugnação não pode continuar a contar como
        fechado no trimestre em que se fechou."""
        self._anuncio()
        p = radar.criar_proposta("60/2026")
        radar.mover_proposta(p, "perdido",
                             campos={"valor_proposta": "118.500,00 EUR",
                                     "motivo": radar.MOTIVOS_PERDA[0]})
        self.assertTrue(radar.proposta(p)["fechada_em"])
        radar.mover_proposta(p, "submetido")
        self.assertIsNone(radar.proposta(p)["fechada_em"])

    def test_estado_inventado_recusa_se_com_recado(self):
        self._anuncio()
        p = radar.criar_proposta("60/2026")
        ok, recado = radar.mover_proposta(p, "quase_ganho")
        self.assertFalse(ok)
        self.assertIn("quase_ganho", recado)
        self.assertEqual(radar.proposta(p)["estado"], "analisar")

    def test_mover_uma_proposta_que_nao_existe_nao_rebenta(self):
        ok, recado = radar.mover_proposta(9999, "ganho")
        self.assertFalse(ok)
        self.assertTrue(recado)

    def test_o_historico_fica_com_o_percurso(self):
        """«submetido a 118 500 EUR» vale mais, três meses depois, do que
        a coluna onde o cartão parou."""
        self._anuncio()
        p = radar.criar_proposta("60/2026")
        radar.mover_proposta(p, "submetido", quem="Afonso", campos={"valor_proposta": "118.500,00 EUR"})
        with radar.liga() as c:
            accoes = [r["accao"] for r in c.execute(
                "SELECT accao FROM historico WHERE ref='60/2026' ORDER BY id")]
        # o `valor_proposta` no meio é a condicionante da escada (D4):
        # os campos que a ranhura exige gravam-se ANTES de ela mudar, e
        # ficam no histórico como o que são — trabalho escrito
        self.assertEqual(accoes,
                         ["proposta criada", "valor_proposta", "estado"])


class TestColunasVelhasFicamMasNinguemAsLe(BaseTemporaria):
    """As doze colunas de CRM do `anuncios` ficam nas bases que já as
    têm, e a garantia passa a ser esta classe.

    A etapa 2 largava-as com `ALTER TABLE ... DROP COLUMN`. Medido a
    15/09/2026 na base dele — 209 894 anúncios, 1,2 GB, com o
    `anuncios.texto` a valer 843 MB desses: o SQLite reescreve a tabela
    inteira uma vez por coluna, e ao fim de 45 s a primeira ainda não
    tinha acabado com o WAL já acima do tamanho da própria base. Num
    arranque do `radar-painel.service` isso lê-se como o painel
    pendurado, e uma migração que fique sem disco a meio deixa a base num
    estado que ninguém planeou. O que se ganhava era cosmética.

    O que interessa não é a coluna não existir: é ninguém a escrever nem
    a ler. É isso que aqui se mede.
    """

    def test_uma_base_nova_nao_as_cria(self):
        with radar.liga() as c:
            colunas = {r["name"] for r in c.execute("PRAGMA table_info(anuncios)")}
        for nome in radar.COLUNAS_QUE_SAIRAM:
            self.assertNotIn(nome, colunas, nome)

    def test_uma_base_que_as_tenha_arranca_e_funciona(self):
        """O caso da instalação dele: a base tem-nas, e o arranque não
        pode nem rebentar nem ficar minutos a reescrever a tabela."""
        with radar.liga() as c:
            for nome in radar.COLUNAS_QUE_SAIRAM:
                c.execute("ALTER TABLE anuncios ADD COLUMN %s TEXT" % nome)
            c.execute("INSERT INTO anuncios (ref, titulo, estado, data_pub) "
                      "VALUES ('7/2026', 'Velho', 'novo', '2026-09-01')")
        radar.iniciar_db()          # a migração, outra vez
        with radar.liga() as c:
            colunas = {r["name"] for r in c.execute("PRAGMA table_info(anuncios)")}
        # ficaram, e não estorvam
        self.assertIn("fase_id", colunas)
        id_ = radar.criar_proposta("7/2026", estado="submetido")
        self.assertEqual(radar.proposta(id_)["estado"], "submetido")
        r = radar.app.test_client().get(radar.LISTA + "?estado=submetido")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Velho", r.get_data(as_text=True))

    def test_nenhuma_e_lida_ou_escrita_no_codigo(self):
        """A guarda a sério. Uma coluna que ficou na base é um sítio onde
        se pode voltar a escrever por distracção -- e aí ficam DOIS
        registos do mesmo facto, que é o risco B do plano.

        Procura-se o nome da coluna em SQL que fale de `anuncios`; os
        nomes que a `propostas` também usa (motivo, notas, coe, lugar…)
        têm de passar, e por isso mede-se a linha e não o ficheiro."""
        suspeitas = []
        for numero, linha in enumerate(radar_fonte().split("\n"), 1):
            nu = linha.strip()
            if nu.startswith("#") or "COLUNAS_QUE_SAIRAM" in nu:
                continue
            if "anuncios" not in nu.lower():
                continue
            for nome in radar.COLUNAS_QUE_SAIRAM:
                # `a["fase_id"]`, `SET fase_id=`, `SELECT fase_id`
                for forma in ('"%s"' % nome, "'%s'" % nome, " %s=" % nome,
                              ",%s" % nome, " %s," % nome, " %s " % nome):
                    if forma in nu:
                        suspeitas.append("%d: %s" % (numero, nu[:90]))
                        break
        self.assertEqual(suspeitas, [], "o `anuncios` voltou a ser escrito:\n"
                         + "\n".join(suspeitas))

    def test_a_tabela_das_fases_sai_mesmo(self):
        """Essa é seis linhas e sai num instante -- e tem de sair, e não
        só de deixar de se criar: enquanto existisse, um restauro de um
        `triagem.jsonl` antigo voltava a enchê-la e ficava um vocabulário
        de fases ao lado do da empresa, sem nada a dizer qual manda."""
        with radar.liga() as c:
            c.execute("CREATE TABLE IF NOT EXISTS fases (id INTEGER, nome TEXT)")
            c.execute("INSERT INTO fases VALUES (1, 'Por analisar')")
        radar.iniciar_db()
        with radar.liga() as c:
            self.assertIsNone(c.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND "
                "name='fases'").fetchone())


class TestPropostasNoB15(BaseTemporaria):
    """As propostas no `triagem.jsonl` — a parte MAIS irrecuperável de
    todas, porque o DR não devolve o preço que se propôs. Até 15/09/2026
    as doze colunas de CRM que viviam em `anuncios` nunca tinham sido
    acrescentadas à exportação, e o BACKLOG dava o R2 por fechado."""

    def _semear(self):
        with radar.liga() as c:
            c.execute("INSERT INTO anuncios (ref, titulo) VALUES (?,?)",
                      ("1/2026", "Um"))
        com_ref = radar.criar_proposta("1/2026", lote=2)
        sem_ref = radar.criar_proposta(entidade="IPL", titulo="Consulta prévia",
                                       porque_sem_ref="consulta prévia")
        with radar.liga() as c:
            c.execute("UPDATE propostas SET valor_proposta=?, lugar=?, "
                      "top3=?, notas=?, coe=?, tipologia=? WHERE id=?",
                      ("118.500,00 EUR", 2, "1º X · 2º nós", "pedir CVs",
                       "Data", "turnkey", com_ref))
            c.execute("INSERT INTO tarefas (proposta_id, ref, o_que, quando, "
                      "quem, origem) VALUES (?,?,?,?,?,?)",
                      (com_ref, "1/2026", "pedir esclarecimentos",
                       "2026-09-22", "Afonso", "esclarecimentos"))
        return com_ref, sem_ref

    def test_exporta_as_colunas_todas_da_proposta(self):
        """Quem acrescentar uma coluna a `propostas` acrescenta-a à lista
        — ou ela deixa de sair do computador, em silêncio."""
        self._semear()
        caminho = os.path.join(self.pasta, "triagem.jsonl")
        radar.exportar_triagem(caminho)
        with open(caminho, encoding="utf-8") as f:
            linhas = [json.loads(l) for l in f if l.strip()]
        propostas = [l for l in linhas if l["tabela"] == "propostas"]
        self.assertEqual(len(propostas), 2)
        self.assertEqual(sorted(propostas[0]),
                         sorted(("tabela",) + radar.COLUNAS_DA_PROPOSTA))
        self.assertTrue(any(p["valor_proposta"] == "118.500,00 EUR"
                            for p in propostas))
        self.assertTrue(any(l["tabela"] == "tarefas" for l in linhas))

    def test_as_colunas_da_proposta_sao_as_da_tabela(self):
        """A lista é escrita à mão de propósito (uma coluna nova tem de
        passar por uma decisão), e é por isso que pode ficar para trás.
        Este teste é o que a obriga a acompanhar."""
        with radar.liga() as c:
            na_tabela = {r["name"] for r in c.execute("PRAGMA table_info(propostas)")}
            nas_tarefas = {r["name"] for r in c.execute("PRAGMA table_info(tarefas)")}
        self.assertEqual(na_tabela, set(radar.COLUNAS_DA_PROPOSTA))
        self.assertEqual(nas_tarefas, set(radar.COLUNAS_DA_TAREFA))

    def test_a_proposta_sem_anuncio_repoe_se(self):
        """Não é um órfão: é a consulta prévia, o ajuste directo, o
        convite. Se levasse a regra das outras tabelas («o ref não está
        na base, fica por repor»), perdia-se no restauro exactamente a
        parte do pipeline que não vem do DR — e o relatório final dizia
        «reposto» na mesma, porque essas linhas nem ref têm para listar."""
        self._semear()
        caminho = os.path.join(self.pasta, "triagem.jsonl")
        radar.exportar_triagem(caminho)
        with radar.liga() as c:      # a base refeita: nada voltou ainda
            c.execute("DELETE FROM propostas")
            c.execute("DELETE FROM tarefas")
            c.execute("DELETE FROM anuncios")
        _, por_repor = radar.repor_triagem(caminho)
        with radar.liga() as c:
            vivas = c.execute("SELECT ref, titulo FROM propostas").fetchall()
        self.assertEqual([v["titulo"] for v in vivas], ["Consulta prévia"])
        self.assertIn("1/2026", por_repor.get("propostas", []))

    def test_restauro_repoe_o_que_se_escreveu_a_mao(self):
        self._semear()
        caminho = os.path.join(self.pasta, "triagem.jsonl")
        radar.exportar_triagem(caminho)
        with radar.liga() as c:
            c.execute("DELETE FROM propostas")
            c.execute("DELETE FROM tarefas")
        radar.repor_triagem(caminho)
        radar.repor_triagem(caminho)      # segunda volta: nada duplica
        with radar.liga() as c:
            p = c.execute("SELECT * FROM propostas WHERE ref='1/2026'").fetchone()
            n = c.execute("SELECT COUNT(*) n FROM propostas").fetchone()["n"]
            t = c.execute("SELECT COUNT(*) n FROM tarefas").fetchone()["n"]
        self.assertEqual(p["valor_proposta"], "118.500,00 EUR")
        self.assertEqual((p["lugar"], p["lote"], p["coe"]), (2, 2, "Data"))
        self.assertEqual((n, t), (2, 1))


class TestCaminhoDeVoltaDaFicha(BaseTemporaria):
    """A queixa dele, a 16/09/2026: «eu vejo a folha de concurso e se eu
    carregar na seta para trás vou para o Hoje».

    Não era um 404 nem um erro — `/` responde 200 —, era o botão do
    caminho de volta a levar a outro sítio depois de a abertura ter
    tomado o `/` na fase 4. É a avaria que se usa duas vezes e depois
    não se usa mais, e por isso não aparece em teste nenhum de estado."""

    def setUp(self):
        super().setUp()
        self.cliente = radar.app.test_client()
        self.enterContext(unittest.mock.patch.object(
            radar, "pedir_documentos", lambda ref: None))
        with radar.liga() as c:
            c.execute("INSERT INTO anuncios (ref, titulo, entidade, data_pub,"
                      " prazo, estado, detalhe_lido, texto, url) VALUES "
                      "(?,?,?,?,?,?,?,?,?)",
                      ("70/2026", "Aquisição de consultoria", "IPL",
                       "2026-09-01", "2099-12-30", "novo", 1, "1 - Objecto",
                       "https://exemplo/70"))

    def _volta(self, referrer):
        with radar.app.test_request_context(
                "/anuncio/70%2F2026",
                headers={"Referer": referrer} if referrer else {}):
            return radar.volta_a_lista()

    def test_sem_referrer_volta_a_lista_e_nao_a_abertura(self):
        self.assertEqual(self._volta(None), radar.LISTA)

    def test_o_referrer_da_lista_traz_o_filtro_e_a_pagina(self):
        self.assertEqual(
            self._volta("http://localhost/concursos?estado=ganho&pag=3"),
            radar.LISTA + "?estado=ganho&pag=3")

    def test_o_calendario_tambem_e_lista_de_onde_se_veio(self):
        self.assertEqual(self._volta("http://localhost/calendario"), "/calendario")

    def test_vindo_da_abertura_a_seta_leva_a_lista(self):
        """O Hoje não é uma lista: quem lá clicou numa tarefa e carrega
        na seta quer os concursos, não voltar ao sítio de onde veio —
        para isso há o botão do browser."""
        self.assertEqual(self._volta("http://localhost/"), radar.LISTA)

    def test_a_seta_da_ficha_aponta_mesmo_para_ali(self):
        html_ = self.cliente.get("/anuncio/70%2F2026").get_data(as_text=True)
        self.assertIn("<a class='volta' href='%s'>" % radar.LISTA, html_)

    def test_procurar_dentro_de_uma_ranhura_encontra_por_pedaco(self):
        """O `para_like()` só ESCAPA os caracteres especiais — os
        coringas põe-nos quem procura, e os outros quatro sítios que o
        chamam põem-nos. Aqui faltavam, e por isso esta procura só
        encontrava um título escrito por inteiro, letra por letra:
        procurar «consult» numa ranhura com o título «Aquisição de
        consultoria» dava zero, e o ecrã dizia «Nada em Ganho» por baixo
        de uma aba a dizer 1."""
        radar.criar_proposta(ref="70/2026", estado="ganho")
        html_ = self.cliente.get(
            radar.LISTA + "?estado=ganho&q=consult").get_data(as_text=True)
        self.assertIn("1 proposta", html_)
        self.assertIn("Aquisição de consultoria", html_)
        # e pelo cliente também, que é o outro campo que a caixa promete
        html_ = self.cliente.get(
            radar.LISTA + "?estado=ganho&q=IP").get_data(as_text=True)
        self.assertIn("Aquisição de consultoria", html_)

    def test_procurar_sem_acentos_encontra_o_que_os_tem(self):
        """O LIKE do SQLite só baixa maiúsculas ASCII: para ele «Ç» e «ç»
        são letras diferentes. A lista dos anúncios procura há muito na
        coluna normalizada; esta procurava no título cru, e «aquisicao»
        não encontrava «Aquisição». A `propostas` não ganha coluna
        normalizada para isto — são dezenas de linhas, e o `simplifica()`
        está registado como função da ligação."""
        radar.criar_proposta(ref="70/2026", estado="ganho")
        for termo in ("aquisicao", "AQUISIÇÃO", "Aquisição", "consultoria"):
            html_ = self.cliente.get(
                radar.LISTA + "?estado=ganho&q=" + termo).get_data(as_text=True)
            self.assertIn("Aquisição de consultoria", html_, termo)

    def test_procura_sem_resultados_nao_diz_que_a_ranhura_esta_vazia(self):
        """A ranhura pode estar cheia: o que está vazio é a RESPOSTA.
        «Nada em Ganho» por baixo de uma aba a dizer 13 é o ecrã a
        discordar de si próprio a dois centímetros de distância."""
        radar.criar_proposta(ref="70/2026", estado="ganho")
        html_ = self.cliente.get(
            radar.LISTA + "?estado=ganho&q=zzzz").get_data(as_text=True)
        self.assertIn("zzzz", html_)
        self.assertIn("Ver as 1", html_)
        self.assertNotIn("Põe um concurso aqui a partir da ficha dele", html_)

    def test_procurar_numa_ranhura_nao_salta_para_a_abertura(self):
        """O `action` do formulário da procura ficou em `/` na mudança de
        endereço: escrever no campo e carregar em «procurar» dava na
        abertura, com a pergunta na barra de endereço e nenhuma resposta
        no ecrã. Um `action` não é um `href` e por isso escapou à
        varredura das nove ligações."""
        radar.criar_proposta(ref="70/2026", estado="submetido")
        html_ = self.cliente.get(
            radar.LISTA + "?estado=submetido").get_data(as_text=True)
        self.assertIn("<form class='pf' method='get' action='%s'>" % radar.LISTA,
                      html_)
        self.assertNotIn("<form class='pf' method='get' action='/'>", html_)


class TestNenhumEcraDa500(BaseTemporaria):
    """Abre TODAS as páginas sem parâmetros e exige que nenhuma dê 500.

    Existe por causa da armadilha do `%`: `"a" + LISTA + "b %s" % x`
    aplica a formatação só ao último pedaço, e a linha parte-se em
    tempo de execução — não de importação. Está escrita nas armadilhas
    desde a fase 4 e foi cometida **outra vez** a 16/09/2026, a corrigir
    as ligações que apontavam para a abertura: o
    `/configuracoes/interesse` passou a dar 500 e as 968 provas passaram
    todas, porque nenhuma abria essa secção com o interesse ligado.

    Não fixa a lista de rotas: percorre o `app.url_map`, e por isso uma
    página nova entra aqui sozinha."""

    def setUp(self):
        super().setUp()
        self.cliente = radar.app.test_client()
        # com o interesse LIGADO: era essa a metade que faltava, e a
        # secção só monta a frase do «em vigor» quando ele existe
        radar.gravar_config({"interesse_cpv": "72000000|48000000",
                             "interesse_ligado": True})

    # A única que fica de fora, e com o nome à vista para não se
    # esquecer: o `/contratos/resumo` agrega o corpus inteiro do Portal
    # BASE (2 milhões de contratos, 2,5 GB) e leva 92 s a frio — sozinha
    # valia mais do que a bateria toda. É também a única página da
    # aplicação que demora isso, e isso é um problema dela e não deste
    # teste; está apontado no BACKLOG.
    LENTAS = ("/contratos/resumo",)

    def test_nenhuma_pagina_sem_parametros_da_500(self):
        caminhos = sorted({r.rule for r in radar.app.url_map.iter_rules()
                           if "GET" in (r.methods or ())
                           and "<" not in r.rule
                           and r.rule not in self.LENTAS})
        maus = []
        for caminho in caminhos:
            resposta = self.cliente.get(caminho)
            if resposta.status_code >= 500:
                maus.append((caminho, resposta.status_code))
        self.assertEqual(maus, [])
        # e o passeio é mesmo um passeio: se um dia a app ficar sem
        # rotas, isto não pode passar por vazio
        self.assertGreater(len(caminhos), 20)


class TestCasaPassouAEmpresa(BaseTemporaria):
    """«a "casa" deve ser na verdade "empresa"» — ele, a 16/09/2026.

    As cadeias do ecrã mudaram nesse dia; o vocabulário do código a
    seguir, a pedido dele. O que isso arrasta são **duas migrações**,
    porque duas das coisas com esse nome estão gravadas: as chaves do
    `config.json` e uma tabela do `radar.db`. Nenhuma das duas pode
    perder o que lá estava — a do config leva o NIF com que o
    cruzamento do Portal BASE diz se a adjudicação foi nossa."""

    def test_a_tabela_muda_de_nome_sem_perder_as_linhas(self):
        with radar.liga() as c:
            c.execute("DROP TABLE IF EXISTS empresa")
            c.execute("CREATE TABLE casa (id INTEGER PRIMARY KEY, nome TEXT, "
                      "ref TEXT, folha TEXT, importado_em TEXT)")
            c.execute("CREATE INDEX ix_casa_ref ON casa(ref)")
            c.execute("INSERT INTO casa (nome, ref, folha) "
                      "VALUES ('Concurso velho','60/2026','modelo')")
            empresa.iniciar_tabelas(c)
            tabelas = {r["name"] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertIn("empresa", tabelas)
            self.assertNotIn("casa", tabelas)
            linhas = c.execute("SELECT nome FROM empresa").fetchall()
        self.assertEqual([l["nome"] for l in linhas], ["Concurso velho"])

    def test_renomear_a_tabela_corre_antes_do_create(self):
        """A ordem é o ponto todo: um `CREATE TABLE IF NOT EXISTS` feito
        primeiro criava uma `empresa` vazia ao lado da `casa` cheia, e o
        registo desaparecia **sem uma palavra** — a tabela existia, só
        não tinha lá nada."""
        with radar.liga() as c:
            c.execute("DROP TABLE IF EXISTS empresa")
            c.execute("CREATE TABLE casa (id INTEGER PRIMARY KEY, nome TEXT, "
                      "ref TEXT, folha TEXT)")
            c.execute("INSERT INTO casa (nome) VALUES ('uma linha')")
            empresa.iniciar_tabelas(c)
            empresa.iniciar_tabelas(c)      # idempotente
            n = c.execute("SELECT COUNT(*) n FROM empresa").fetchone()["n"]
        self.assertEqual(n, 1)

    def test_as_chaves_do_config_levam_o_valor(self):
        radar.gravar_config({"nome_da_casa": "LATD DIGITAL ENABLERS, LDA",
                             "nif_da_casa": "516241362"})
        levadas = radar.renomear_chaves_do_config()
        self.assertEqual(levadas, {"nome_da_casa": "nome_da_empresa",
                                   "nif_da_casa": "nif_da_empresa"})
        cfg = radar.ler_config()
        self.assertEqual(cfg["nome_da_empresa"], "LATD DIGITAL ENABLERS, LDA")
        self.assertEqual(cfg["nif_da_empresa"], "516241362")
        # e a velha sai mesmo do ficheiro, senão ficava resíduo a
        # confundir quem lá fosse ver
        with open(radar.CONFIG, encoding="utf-8") as f:
            self.assertNotIn("nome_da_casa", json.load(f))
        # idempotente: correr outra vez não tem o que levar
        self.assertEqual(radar.renomear_chaves_do_config(), {})

    def test_a_chave_nova_manda_quando_as_duas_existem(self):
        """Quer dizer que já se gravou pelo painel depois da mudança: o
        que está no ecrã é o que vale, e a velha é o que ficou para
        trás."""
        radar.gravar_config({"nome_da_casa": "Nome velho",
                             "nome_da_empresa": "Nome novo"})
        radar.renomear_chaves_do_config()
        self.assertEqual(radar.ler_config()["nome_da_empresa"], "Nome novo")

    def test_o_vocabulario_do_codigo_nao_tem_casa(self):
        """Nenhum nome nem nenhuma cadeia diz «casa» — fora dos
        COMENTÁRIOS, onde dizer o nome velho é o que explica a migração
        a quem a encontrar daqui a um ano.

        Mede-se com o `tokenize` e não por linha: é a única forma de
        separar o que corre do que se lê ao lado. O que fica com «casa»
        na língua — «casar», «casamento», as «casas» de um código CPV —
        vive todo em comentários e docstrings, e por isso não entra."""
        import tokenize
        for ficheiro in (radar.__file__, empresa.__file__):
            soltas = []
            with tokenize.open(ficheiro) as f:
                for tok in tokenize.generate_tokens(f.readline):
                    if tok.type in (tokenize.COMMENT, tokenize.STRING):
                        continue    # comentário e docstring são prosa
                    if re.search(r"(?i)\bcasas?\b", tok.string):
                        soltas.append("%s:%d %s"
                                      % (ficheiro, tok.start[0], tok.string))
            self.assertEqual(soltas, [], ficheiro)
        self.assertTrue(hasattr(radar, "ESTADOS_DA_EMPRESA"))
        self.assertFalse(hasattr(radar, "ESTADOS_DA_CASA"))
        # e o que se LÊ também não: aí nem comentário há para explicar
        legendas = " ".join(l for _, _, l, _, _ in radar.SECCOES_CONFIG)
        self.assertIn("a nossa empresa", legendas)
        self.assertNotIn("casa", legendas)
        self.assertNotIn("casa", " ".join(
            r for _, r in radar.ESTADOS_DA_EMPRESA))


class TestMercadoDepressa(BaseTemporaria):
    """Os gráficos do Mercado levavam 92 s a frio e 14,8 s quentes, numa
    página que faz seis agregações sobre o corpus (2 000 340 contratos).
    16/09/2026, a pedido dele. Duas causas, e as duas mediram-se:

    1. **O recorte por CPV varria a tabela inteira.** O `LIKE 'x%'` do
       SQLite é insensível a maiúsculas e por isso NÃO usa o índice; o
       `GLOB 'x*'` é sensível e o planeador traduz o prefixo numa gama.
       2,83 s → 0,03 s, mesmo resultado.
    2. **O «Quem ganha» ia buscar a `chave` à tabela**, uma vez por cada
       um dos 95 680 contratos do recorte: o `ux_adj` começa por
       `contrato_id` mas não cobre a `chave`. Com um índice que a cobre,
       6,19 s → 1,02 s.

    Estes testes não medem tempo — um teste cronometrado num portátil é
    um teste instável. Medem as duas propriedades de que o tempo depende.
    """

    def test_o_recorte_por_cpv_e_glob_e_nao_like(self):
        frag, vals = radar.prefixos_em_cpv8(["72", "48"])
        self.assertEqual(frag, "cpv8 GLOB ? OR cpv8 GLOB ?")
        self.assertEqual(vals, ["72*", "48*"])
        self.assertNotIn("LIKE", frag)

    def test_o_glob_da_o_mesmo_que_o_like_em_codigos_cpv(self):
        """A troca só é segura porque os prefixos vêm do `prefixo_cpv()`,
        que devolve DÍGITOS: as duas diferenças do GLOB — ser sensível a
        maiúsculas, e tratar `*`, `?` e `[` como coringas — não tocam num
        código CPV. Isto prova-o contra o SQLite, e não por leitura."""
        c = sqlite3.connect(":memory:")
        c.execute("CREATE TABLE t (cpv8 TEXT)")
        c.executemany("INSERT INTO t VALUES (?)",
                      [("72000000",), ("72267100",), ("48190000",),
                       ("30000000",), ("7200",), ("",)])
        frag, vals = radar.prefixos_em_cpv8(["72", "48"])
        por_glob = {r[0] for r in c.execute(
            "SELECT cpv8 FROM t WHERE " + frag, vals)}
        por_like = {r[0] for r in c.execute(
            "SELECT cpv8 FROM t WHERE cpv8 LIKE ? OR cpv8 LIKE ?",
            ["72%", "48%"])}
        self.assertEqual(por_glob, por_like)
        self.assertEqual(por_glob, {"72000000", "72267100", "48190000", "7200"})

    def test_os_sitios_todos_perguntam_pelo_mesmo_sitio(self):
        """A regra vive numa função só. Sete sítios copiavam o mesmo
        `" OR ".join("cpv8 LIKE ?" ...)`, e o primeiro a mudar deixava os
        outros seis a varrer a tabela em silêncio — sem erro nenhum, só
        mais lento."""
        with open(radar.__file__, encoding="utf-8") as f:
            fonte = f.read()
        self.assertNotIn("cpv8 LIKE", fonte)
        self.assertGreaterEqual(fonte.count("prefixos_em_cpv8("), 7)

    def test_o_corpus_leva_o_indice_que_cobre_a_chave(self):
        radar.iniciar_corpus()
        with radar.liga_corpus() as c:
            linha = c.execute("SELECT sql FROM sqlite_master WHERE type='index'"
                              " AND name='ix_adj_ctr_chave'").fetchone()
        self.assertIsNotNone(linha, "falta o índice de cobertura do «Quem ganha»")
        # a ordem é o que o faz cobrir: procura-se por contrato_id e
        # lê-se a chave sem ir à tabela
        self.assertIn("(contrato_id, chave)", linha["sql"])


class TestClienteOuConcorrente(unittest.TestCase):
    """«a "empresa" deve ser na verdade "empresa" todas as outras são
    concorrentes. ou clientes. deves fazer a diferenciação entre
    clientes e concorrentes através da quantidade de compra e de venda»
    — ele, a 16/09/2026.

    O Portal BASE não tem campo nenhum a dizer o que uma entidade é: tem
    os contratos dos dois lados, e é do peso de cada lado que o papel
    sai. A função é pura de propósito — dois números entram, um papel
    sai — para se poder provar sem corpus."""

    def test_quem_compra_e_cliente(self):
        # o Município de Lagos, medido na base dele: 263,9 M€ comprados
        # contra 824 € ganhos
        self.assertEqual(radar.papel_da_entidade(263_900_000, 824)[0],
                         "cliente")

    def test_quem_vende_e_concorrente(self):
        self.assertEqual(radar.papel_da_entidade(0, 1_200_000)[0],
                         "concorrente")

    def test_quem_faz_as_duas_coisas_nao_leva_lado(self):
        """Uma ULS compra informática e ganha candidaturas. Dizer só um
        dos lados era escolher qual mentir."""
        self.assertEqual(radar.papel_da_entidade(1_000_000, 900_000)[0],
                         "ambos")

    def test_a_fronteira_e_a_folga_e_nao_o_maior(self):
        folga = radar.FOLGA_DO_PAPEL
        self.assertEqual(radar.papel_da_entidade(100 * folga, 100)[0],
                         "cliente")
        self.assertEqual(radar.papel_da_entidade(100 * folga - 1, 100)[0],
                         "ambos")

    def test_sem_contratos_nenhuns_nao_se_inventa_papel(self):
        self.assertEqual(radar.papel_da_entidade(0, 0), ("", "", ""))
        self.assertEqual(radar.papel_da_entidade(None, None)[0], "")


class TestEscadaNaLista(BaseTemporaria):
    """A escada no ecrã (etapa 2 do CRM, 15/09/2026). A pergunta do
    Afonso era que o «Em curso» e a aba «interessados» mostravam o
    mesmo: mostravam, porque eram a mesma consulta. Estas provas são de
    que deixaram de ser."""

    def setUp(self):
        super().setUp()
        self.cliente = radar.app.test_client()
        self.enterContext(unittest.mock.patch.object(
            radar, "pedir_documentos", lambda ref: None))
        with radar.liga() as c:
            c.execute("INSERT INTO anuncios (ref, titulo, entidade, preco_base,"
                      " data_pub, prazo, estado, detalhe_lido) VALUES "
                      "(?,?,?,?,?,?,?,?)",
                      ("60/2026", "Aquisição de software", "Câmara de Lisboa",
                       "118.500,00 EUR", "2026-09-01", "2099-12-30", "novo", 1))
            c.execute("INSERT INTO anuncios (ref, titulo, data_pub, prazo,"
                      " estado) VALUES (?,?,?,?,?)",
                      ("9/2020", "Velho e expirado", "2020-01-01",
                       "2020-02-01", "novo"))

    def _html(self, url=None):
        return self.cliente.get(url or radar.LISTA).get_data(as_text=True)

    def test_o_todos_diz_o_mesmo_nas_duas_listas(self):
        """15/09/2026, visto no ecrã: o «Todos» dizia **209 894** na
        lista das propostas e **199 631** na dos anúncios -- o mesmo
        botão com dois números, que é exactamente o que a regra da empresa
        proíbe («um número que um ecrã mostra tem de dar exactamente a
        lista que a ligação dele abre»).

        A causa: sem filtro nenhum, a `contar_a_escada()` partia de uma
        base VAZIA, e a base certa é a do motor com `estado=""` -- que
        tira as republicações, porque «todos» são todos os
        PROCEDIMENTOS e uma alteração é o mesmo concurso outra vez.
        """
        with radar.liga() as c:
            for ref, estado in (("1/2026", "novo"), ("2/2026", "novo"),
                                ("3/2026", "alteracao")):
                c.execute("INSERT INTO anuncios (ref, titulo, data_pub,"
                          " estado) VALUES (?,?,?,?)",
                          (ref, "T", "2026-09-01", estado))
        radar.criar_proposta("1/2026", estado="submetido")
        with radar.app.test_request_context("/"):
            sem_base = radar.contar_a_escada()
            com_base = radar.contar_a_escada(
                *radar.condicoes({"estado": ""}))
        self.assertEqual(sem_base, com_base)
        # e a alteração não conta: os dois do setUp mais os dois novos
        with radar.liga() as c:
            todos = c.execute("SELECT COUNT(*) n FROM anuncios").fetchone()["n"]
        self.assertEqual(todos, 5)
        self.assertEqual(sem_base[""], 4)

    def test_a_barra_tem_as_dez_ranhuras_e_o_todos(self):
        html_ = self._html()
        for _, rotulo in radar.ESCADA:
            self.assertIn(">%s <i>" % rotulo, html_, rotulo)
        self.assertIn(">Todos <i>", html_)

    def test_a_entrada_e_o_cemiterio_apartam_se(self):
        self.assertIn("Aquisição de software", self._html())
        self.assertNotIn("Velho e expirado", self._html())
        cemiterio = self._html(radar.LISTA + "?estado=expirou")
        self.assertIn("Velho e expirado", cemiterio)
        self.assertNotIn("Aquisição de software", cemiterio)

    def test_decidir_tira_o_anuncio_da_entrada(self):
        """Um anúncio que se pôs na escada não pode continuar em «Por
        ver» a pedir triagem — antes da escada isto vinha de graça,
        porque o estado era do anúncio."""
        self.cliente.post("/estado/60%2F2026/analisar")
        self.assertNotIn("Aquisição de software", self._html())
        self.assertIn("Aquisição de software", self._html(radar.LISTA + "?estado=analisar"))

    def test_as_duas_listas_deixaram_de_ser_a_mesma_consulta(self):
        """A pergunta que deu origem a tudo isto. A lista dos anúncios
        mostra o que o DR publicou; a das ranhuras da empresa mostra
        propostas — e uma delas nem anúncio tem."""
        # o preço vai no mesmo pedido: «Submetido» exige-o (D4)
        self.cliente.post("/estado/60%2F2026/submetido",
                          data={"valor_proposta": "1.000,00 EUR"})
        radar.criar_proposta(entidade="IPL", titulo="Consulta prévia de formação",
                             porque_sem_ref="consulta prévia", estado="submetido")
        html_ = self._html(radar.LISTA + "?estado=submetido")
        self.assertIn("Aquisição de software", html_)
        self.assertIn("Consulta prévia de formação", html_)
        # e a entrada não mostra nem uma nem outra
        entrada = self._html()
        self.assertNotIn("Aquisição de software", entrada)
        self.assertNotIn("Consulta prévia de formação", entrada)

    def test_a_aba_conta_exactamente_a_lista_que_abre(self):
        """A aba contava ANÚNCIOS com proposta e a lista mostra
        PROPOSTAS. Discordavam por três razões de uma vez — as propostas
        feitas sobre uma republicação do DR (que a base do motor tira),
        as que caem fora do interesse por CPV, e as que nem anúncio têm.
        Visto no ecrã a 16/09/2026: «Por analisar 7» por cima de uma
        lista de 11. A regra da empresa é que um número abre exactamente
        a lista que o confirma."""
        radar.criar_proposta(entidade="IPL", titulo="Consulta prévia",
                             porque_sem_ref="consulta prévia")
        html_ = self._html(radar.LISTA + "?estado=analisar")
        # a lista continua a dizer quais não vêm do DR: é um facto sobre
        # ela, e não um desconto no número
        self.assertIn("sem anúncio do DR", html_)
        self.assertNotIn("a aba conta só as que têm", html_)
        with radar.liga() as c:
            quantas = c.execute("SELECT COUNT(*) n FROM propostas "
                                "WHERE estado='analisar'").fetchone()["n"]
        with radar.app.test_request_context(radar.LISTA):
            self.assertEqual(radar.contar_a_escada()["analisar"], quantas)
        # e o número da aba é o número que a lista escreve no topo
        self.assertIn("%d proposta%s" % (quantas, "" if quantas == 1 else "s"),
                      html_)

    def test_uma_proposta_sem_anuncio_tem_ficha_propria(self):
        """Sem esta porta, a decisão D2 ficava escrita no plano e sem
        sítio no ecrã: uma consulta prévia não tem ficha do DR para
        abrir."""
        r = self.cliente.post("/proposta/nova",
                              data={"entidade": "IPL", "titulo": "Formação",
                                    "porque_sem_ref": "consulta prévia"})
        self.assertEqual(r.status_code, 302)
        html_ = self.cliente.get(r.headers["Location"]).get_data(as_text=True)
        self.assertIn("Formação", html_)
        self.assertIn("consulta prévia", html_)

    def test_uma_proposta_sem_cliente_nem_titulo_recusa_se(self):
        """Uma linha sem nenhum dos dois não se encontra depois."""
        r = self.cliente.post("/proposta/nova", data={"entidade": "", "titulo": ""})
        self.assertIn("aviso", r.headers["Location"])
        with radar.liga() as c:
            self.assertEqual(c.execute(
                "SELECT COUNT(*) n FROM propostas").fetchone()["n"], 0)

    def test_a_ficha_de_uma_proposta_com_anuncio_leva_a_ficha_do_anuncio(self):
        """O procedimento tem uma ficha só, e é a do anúncio: é lá que
        estão as peças, o CPV e o histórico do cliente."""
        id_ = radar.criar_proposta("60/2026")
        r = self.cliente.get("/proposta/%d" % id_)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/anuncio/60", r.headers["Location"])


class TestFiltrosGuardadosFalamAEscada(BaseTemporaria):
    """Um filtro (ou um alerta) guardado antes de 15/09/2026 tem
    "estado=novo" escrito. Sem a tradução partiam-se duas coisas, as
    duas em silêncio: o filtro em uso nunca mais se reconhecia a si
    próprio, e um alerta com "estado=interessa" procurava um valor que a
    coluna já não tem — sem encontrar nada e sem nada no ecrã a dizê-lo.
    """

    def _guardar(self, consulta):
        with radar.liga() as c:
            c.execute("INSERT INTO filtros_guardados (nome, consulta, alerta,"
                      " quem, criado_em) VALUES (?,?,?,?,?)",
                      ("CPV IT", consulta, 1, "Afonso", "2026-08-30 10:00"))

    def _consulta(self):
        with radar.liga() as c:
            return c.execute("SELECT consulta FROM filtros_guardados"
                             ).fetchone()["consulta"]

    def test_a_migracao_traduz_e_e_idempotente(self):
        self._guardar("cpv=72&estado=novo")
        with radar.liga() as c:
            radar.traduzir_filtros_guardados(c)
        self.assertEqual(self._consulta(), "cpv=72&estado=porver")
        with radar.liga() as c:
            radar.traduzir_filtros_guardados(c)     # segunda volta
        self.assertEqual(self._consulta(), "cpv=72&estado=porver")

    def test_nao_mexe_no_que_ja_esta_certo_nem_no_todos(self):
        self._guardar("cpv=72&estado=")
        with radar.liga() as c:
            radar.traduzir_filtros_guardados(c)
        self.assertEqual(self._consulta(), "cpv=72&estado=")

    def test_um_alerta_pelo_vocabulario_antigo_continua_a_ver(self):
        """`estado=interessa` já não é valor nenhum da coluna. Deixar cair
        no `estado = ?` fazia o alerta não encontrar nada; traduz-se para
        a proposta, que é onde esse estado passou a viver."""
        onde, valores = radar.condicoes({"estado": "interessa"})
        self.assertIn("EXISTS", onde)
        self.assertIn("propostas", onde)
        self.assertEqual(valores, ["analisar"])


class TestFecharOCicloComOBase(BaseTemporaria):
    """Etapa 4 do CRM (15/09/2026): submetemos uma proposta, e meses
    depois o Estado publica em quem caiu o procedimento e por quanto.

    **A ligação é por chave e não por semelhança.** Medido nesse dia na
    base dele: o `contratos.n_anuncio` do dump do IMPIC vem no mesmo
    formato do `ref` do radar («17161/2026»), e 69,4% dos anúncios de
    2024 já têm contrato celebrado (contra 5,3% dos de 2026, que é o
    ciclo a demorar meses). O plano previa o maquinário de semelhança do
    `empresa.py`; não é preciso nenhum — ou é o mesmo procedimento ou não é
    nada.

    E **propõe, nunca decide**: palavra dele, «isto avança-se sempre com
    a confirmação de um humano para fechar o resultado».
    """

    def setUp(self):
        super().setUp()
        self.cliente = radar.app.test_client()
        self.enterContext(unittest.mock.patch.object(
            radar, "CORPUS", os.path.join(self.pasta, "contratos.db")))
        self.enterContext(unittest.mock.patch.object(
            radar, "CONFIG", os.path.join(self.pasta, "config.json")))
        radar.iniciar_corpus()
        with radar.liga() as c:
            c.execute("INSERT INTO anuncios (ref, titulo, entidade, data_pub,"
                      " tipo, url, estado, preco_base) VALUES "
                      "(?,?,?,?,?,?,'novo',?)",
                      ("17161/2026", "Aquisição de testes", "ULS Santo António",
                       "2026-03-01", "Anúncio de procedimento", "https://dr/1",
                       "200.000,00 EUR"))
        self.id_ = radar.criar_proposta("17161/2026", estado="submetido")
        radar.gravar_campos_da_proposta(self.id_, ["valor_proposta"],
                                        ["180.000,00 EUR"])

    def _contrato(self, ref="17161/2026", quem="ROCHE", nif="504282921",
                  valor=171543.0):
        with radar.liga_corpus() as c:
            cur = c.execute(
                "INSERT INTO contratos (ano, n_anuncio, tipo_procedimento,"
                " objecto, adjudicante, data_celebracao, preco_contratual,"
                " preco_base) VALUES (2026,?,?,?,?,?,?,?)",
                (ref, "Concurso público", "Testes", "ULS Santo António",
                 "2026-08-27", valor, 200000.0))
            c.execute("INSERT INTO contrato_adjudicatario (contrato_id, nif,"
                      " nome, chave) VALUES (?,?,?,?)",
                      (cur.lastrowid, nif, quem, nif))

    def test_a_ligacao_e_por_chave_e_nao_por_semelhanca(self):
        self._contrato()
        linhas = radar.desfecho_do_anuncio("17161/2026")
        self.assertEqual(len(linhas), 1)
        self.assertIn("ROCHE", linhas[0]["ganhou"])
        # e um ref parecido não empresa: ou é o mesmo procedimento ou não é
        self.assertEqual(radar.desfecho_do_anuncio("17162/2026"), [])

    def test_uma_proposta_parada_com_contrato_aparece_por_fechar(self):
        """São as que ficam meses em «Submetido» à espera de alguém se
        lembrar de as fechar -- e o Estado já publicou o desfecho."""
        self.assertEqual(radar.propostas_por_fechar(), [])
        self._contrato()
        por_fechar = radar.propostas_por_fechar()
        self.assertEqual([p["id"] for p, _ in por_fechar], [self.id_])

    def test_uma_proposta_ja_fechada_nao_volta_a_aparecer(self):
        self._contrato()
        radar.mover_proposta(self.id_, "perdido",
                             campos={"valor_proposta": "118.500,00 EUR",
                                     "motivo": radar.MOTIVOS_PERDA[0]})
        self.assertEqual(radar.propostas_por_fechar(), [])

    def test_sem_o_nif_da_empresa_nao_se_afirma_que_nao_fomos_nos(self):
        """Três respostas e não duas, de propósito: um «não fomos» de
        quem não sabe é uma afirmação falsa -- e era com base nela que a
        proposta ia fechar."""
        self._contrato()
        linhas = radar.desfecho_do_anuncio("17161/2026")
        self.assertIsNone(radar.fomos_nos(linhas))
        radar.gravar_config({"nif_da_empresa": "111111111"})
        self.assertIs(radar.fomos_nos(linhas), False)
        radar.gravar_config({"nif_da_empresa": "504282921"})
        self.assertIs(radar.fomos_nos(linhas), True)

    def test_o_nome_da_empresa_tambem_serve_mas_o_nif_e_que_e_certo(self):
        self._contrato(quem="ROCHE SISTEMAS DE DIAGNOSTICO, LDA")
        linhas = radar.desfecho_do_anuncio("17161/2026")
        radar.gravar_config({"nome_da_empresa": "Roche Sistemas"})
        self.assertIs(radar.fomos_nos(linhas), True)

    def test_o_desvio_compara_o_nosso_preco_com_o_adjudicado(self):
        """«perdeste para a X por 5% abaixo do teu preço» -- o número
        que esta etapa existe para dar."""
        self._contrato(valor=171000.0)
        linhas = radar.desfecho_do_anuncio("17161/2026")
        desvio, ganhou = radar.desvio_do_proposto("180.000,00 EUR", linhas)
        self.assertEqual(ganhou, 171000.0)
        self.assertAlmostEqual(desvio, 0.05, places=3)

    def test_com_lotes_soma_antes_de_dividir(self):
        """A mesma regra do `desconto_do_desfecho()`: o procedimento é a
        unidade. Por linha, cada lote comparava-se com a nossa proposta
        inteira e dava um número que mente com ar de certo."""
        self._contrato(valor=90000.0)
        self._contrato(valor=81000.0, quem="OUTRA", nif="500000000")
        linhas = radar.desfecho_do_anuncio("17161/2026")
        desvio, ganhou = radar.desvio_do_proposto("180.000,00 EUR", linhas)
        self.assertEqual(ganhou, 171000.0)
        self.assertAlmostEqual(desvio, 0.05, places=3)

    def test_sem_proposto_nao_se_inventa_desvio(self):
        self._contrato()
        linhas = radar.desfecho_do_anuncio("17161/2026")
        self.assertEqual(radar.desvio_do_proposto(None, linhas), (None, None))
        self.assertEqual(radar.desvio_do_proposto("180.000,00 EUR", []),
                         (None, None))

    def test_a_ficha_propoe_e_nao_decide(self):
        """O facto fica ao lado dos dois botões, e o estado não muda
        sozinho: palavra dele, «isto avança-se sempre com a confirmação
        de um humano para fechar o resultado»."""
        self._contrato()
        html_ = self.cliente.get("/anuncio/17161%2F2026").get_data(as_text=True)
        self.assertIn("ROCHE", html_)
        self.assertIn("Ganhámos", html_)
        self.assertIn("Perdemos", html_)
        self.assertIn("falta o NIF da empresa", html_)
        # e a proposta continua onde estava
        self.assertEqual(radar.proposta(self.id_)["estado"], "submetido")

    def test_o_botao_fecha_a_proposta(self):
        self._contrato()
        r = self.cliente.post("/proposta/%d/escada" % self.id_,
                              data={"estado": "perdido", "motivo": "Preço"})
        self.assertEqual(r.status_code, 302)
        p = radar.proposta(self.id_)
        self.assertEqual((p["estado"], p["motivo"]), ("perdido", "Preço"))
        self.assertTrue(p["fechada_em"])

    def test_a_faixa_cala_se_quando_a_proposta_ja_esta_fechada(self):
        self._contrato()
        radar.mover_proposta(self.id_, "ganho")
        linhas = radar.desfecho_do_anuncio("17161/2026")
        self.assertEqual(
            radar.faixa_do_desfecho(radar.proposta(self.id_), linhas), "")

    def test_sem_corpus_nao_rebenta_nem_promete_nada(self):
        with unittest.mock.patch.object(radar, "ha_corpus", lambda: False):
            self.assertEqual(radar.propostas_por_fechar(), [])
            self.assertEqual(radar.desfecho_do_anuncio("17161/2026"), [])


class TestIndicadoresComerciais(BaseTemporaria):
    """Etapa 5 do CRM (15/09/2026). Os indicadores mediam o funil da
    TRIAGEM -- quanto entra, quanto se olha, quanto vinga. Faltava o do
    NEGÓCIO: quanto está em jogo, quanto se ganha, e porque se perde.

    A regra que esta classe guarda, e que é a da empresa: **o que não se
    pode saber diz-se**. Uma taxa de vitória sobre três concursos é
    ruído com ar de facto, e as decisões que se tomam com ela custam
    dinheiro.
    """

    def _p(self, ref, estado, base=None, proposto=None, motivo=None, **k):
        with radar.liga() as c:
            c.execute("INSERT OR IGNORE INTO anuncios (ref, titulo, entidade,"
                      " data_pub, estado, preco_base, cpv) VALUES "
                      "(?,?,?,?,'novo',?,?)",
                      (ref, "T " + ref, k.get("entidade", "Câmara"),
                       "2026-01-01", base or "", k.get("cpv", "72000000")))
        id_ = radar.criar_proposta(ref, estado=estado)
        campos, valores = [], []
        if proposto:
            campos.append("valor_proposta")
            valores.append(proposto)
        for nome in ("tipologia", "coe"):
            if nome in k:
                campos.append(nome)
                valores.append(k[nome])
        if campos:
            radar.gravar_campos_da_proposta(id_, campos, valores)
        if motivo:
            radar.gravar_motivo(id_, motivo)
        return id_

    def test_o_pipeline_soma_base_ate_ao_submetido_e_proposto_dai_em_diante(self):
        """Um pipeline somado a preços base é o tecto das entidades e
        não o que está em jogo, com o mesmo ar de número certo."""
        self._p("1/2026", "analisar", base="100.000,00 EUR")
        self._p("2/2026", "submetido", base="200.000,00 EUR",
                proposto="150.000,00 EUR")
        p = radar.pipeline_em_euros()
        self.assertEqual(p["analisar"]["euros"], 100000.0)
        self.assertEqual(p["submetido"]["euros"], 150000.0)

    def test_sem_proposto_lido_o_base_serve_e_diz_se(self):
        self._p("3/2026", "submetido", base="200.000,00 EUR")
        p = radar.pipeline_em_euros()
        self.assertEqual(p["submetido"]["euros"], 200000.0)
        self.assertEqual(p["submetido"]["sem_preco"], 1)

    def test_as_ranhuras_fechadas_nao_contam_para_o_pipeline(self):
        self._p("4/2026", "ganho", base="500.000,00 EUR")
        self.assertNotIn("ganho", radar.pipeline_em_euros())

    def test_o_nao_fomos_nao_entra_no_denominador_da_taxa(self):
        """Um «Não fomos» é uma decisão nossa de não concorrer. Metê-lo
        no denominador fazia a taxa cair por se ter sido selectivo, que
        é o contrário do que ela devia dizer."""
        for i in range(3):
            self._p("g%d/2026" % i, "ganho")
        for i in range(3):
            self._p("p%d/2026" % i, "perdido")
        for i in range(10):
            self._p("n%d/2026" % i, "nao_fomos")
        self._p("c/2026", "cancelado")
        nome, ganhos, decididos, taxa = radar.taxa_de_vitoria()[0]
        self.assertEqual((ganhos, decididos), (3, 6))
        self.assertAlmostEqual(taxa, 0.5)

    def test_abaixo_do_minimo_a_taxa_e_None_e_nao_zero(self):
        """None é «ainda não sei»; um número seria uma afirmação."""
        self._p("1/2026", "ganho")
        self._p("2/2026", "perdido")
        _, ganhos, decididos, taxa = radar.taxa_de_vitoria()[0]
        self.assertEqual((ganhos, decididos), (1, 2))
        self.assertIsNone(taxa)

    def test_a_taxa_por_dimensao_agrupa_e_ordena_pelos_decididos(self):
        for i in range(6):
            self._p("t%d/2026" % i, "ganho" if i < 4 else "perdido",
                    tipologia="turnkey")
        self._p("c1/2026", "perdido", tipologia="consulting")
        linhas = radar.taxa_de_vitoria("tipologia")
        self.assertEqual(linhas[0][0], "turnkey")
        self.assertEqual((linhas[0][1], linhas[0][2]), (4, 6))
        self.assertAlmostEqual(linhas[0][3], 4 / 6.0)
        self.assertIsNone(linhas[1][3])     # consulting: um só

    def test_uma_coluna_inventada_nao_entra_em_SQL(self):
        """O `por` vem de um sítio só do código, mas uma lista branca é
        o que separa isto de interpolar um nome de coluna."""
        self._p("1/2026", "ganho")
        # uma coluna que não está na lista branca cai no total, e não em
        # SQL: é isso que separa isto de interpolar um nome vindo de fora
        self.assertEqual(radar.taxa_de_vitoria("; DROP TABLE propostas"),
                         radar.taxa_de_vitoria())
        self.assertEqual(radar.taxa_de_vitoria()[0][0], "total")
        with radar.liga() as c:
            self.assertEqual(c.execute(
                "SELECT COUNT(*) n FROM propostas").fetchone()["n"], 1)

    def test_a_taxa_por_cpv_junta_as_duas_tabelas_e_deixa_de_fora_quem_nao_tem(self):
        """Uma proposta sem anúncio (D2) não tem CPV, e ficar de fora é
        diferente de contar como zero."""
        for i in range(5):
            self._p("x%d/2026" % i, "ganho" if i < 2 else "perdido",
                    cpv="72000000")
        radar.criar_proposta(entidade="IPL", titulo="Consulta prévia",
                             estado="ganho")
        linhas = radar.taxa_por_divisao_cpv()
        self.assertEqual(linhas[0][0], "72")
        self.assertEqual((linhas[0][1], linhas[0][2]), (2, 5))

    def test_os_motivos_agregam_se_porque_sao_vocabulario_fechado(self):
        self._p("1/2026", "perdido", motivo="Preço")
        self._p("2/2026", "perdido", motivo="Preço")
        self._p("3/2026", "perdido", motivo="CV's")
        self._p("4/2026", "perdido")
        linhas = radar.porque_se_perde()
        self.assertEqual([(l["m"], l["n"]) for l in linhas][:2],
                         [("Preço", 2), ("CV's", 1)])
        self.assertIn(("(por dizer)", 1), [(l["m"], l["n"]) for l in linhas])

    def test_os_dois_motivos_nao_se_misturam(self):
        """«Preço base baixo» é porque não se foi; «Preço» é porque se
        perdeu. Somá-los numa tabela só dava duas coisas com o mesmo
        nome e nenhuma conta."""
        self._p("1/2026", "perdido", motivo="Preço")
        self._p("2/2026", "nao_fomos", motivo="Preço base baixo")
        self.assertEqual([l["m"] for l in radar.porque_se_perde()], ["Preço"])
        self.assertEqual([l["m"] for l in radar.porque_nao_se_vai()],
                         ["Preço base baixo"])

    def test_o_desconto_medio_so_conta_quem_tem_os_dois_precos(self):
        self._p("1/2026", "ganho", base="100.000,00 EUR",
                proposto="90.000,00 EUR")
        self._p("2/2026", "ganho", base="200.000,00 EUR")     # sem proposto
        desconto, sobre = radar.desconto_medio_dos_ganhos()
        self.assertAlmostEqual(desconto, 0.10)
        self.assertEqual(sobre, 1)

    def test_sem_ganhos_o_desconto_e_None_e_nao_zero(self):
        self._p("1/2026", "perdido", base="100.000,00 EUR",
                proposto="90.000,00 EUR")
        self.assertEqual(radar.desconto_medio_dos_ganhos(), (None, 0))

    def test_o_parado_mede_se_pela_ultima_mexida_e_nao_pela_criacao(self):
        """Uma proposta que se mexeu ontem não está parada, por muito
        antiga que seja."""
        self._p("1/2026", "submetido")
        with radar.liga() as c:
            c.execute("UPDATE propostas SET criada_em='2026-01-01 09:00'")
            c.execute("UPDATE historico SET quando='2026-01-01 09:00'")
        primeiro = radar.dias_parados()[0]
        self.assertGreater(primeiro[1], 100)
        radar.registar("1/2026", "nota", "mexeu hoje")
        self.assertEqual(radar.dias_parados()[0][1], 0)

    def test_o_ecra_abre_e_cada_numero_leva_a_lista(self):
        self._p("1/2026", "submetido", base="200.000,00 EUR",
                proposto="150.000,00 EUR")
        # Os números do negócio mudaram-se para a ABERTURA a 16/09/2026,
        # por decisão dele: «põe os indicadores no hoje, à excepção dos
        # indicadores da curl, plataformas, BASE, DR». Em Configurações
        # ficou a saúde da máquina. A 17/09/2026 saíram da abertura para
        # o **Ponto de situação**, página própria: são a segunda
        # pergunta de quem chega, não a primeira, e a abertura ficava
        # com duas páginas empilhadas.
        html_ = radar.app.test_client().get("/situacao").get_data(as_text=True)
        self.assertIn("O negócio", html_)
        self.assertIn("em jogo", html_)
        sistema = radar.app.test_client().get(
            "/configuracoes/indicadores").get_data(as_text=True)
        self.assertNotIn("O negócio", sistema)
        self.assertIn("Estado da recolha", sistema)
        # a regra da empresa: o número abre a lista que o confirma
        # o endereço da lista: até 16/09/2026 este teste pedia
        # "href='/?estado=submetido'", que é a abertura e não a lista --
        # e assim pregava a ligação errada no lugar
        self.assertIn("href='/concursos?estado=submetido'", html_)


class TestContactos(BaseTemporaria):
    """Etapa 6 do CRM (15/09/2026): quem é a pessoa do lado de lá.

    Foi a última etapa do plano de propósito -- é do que se sente falta
    mais tarde, quando já há concursos que se repetem com o mesmo
    cliente. E é por isso que os contactos são da **entidade** e não do
    concurso: a pessoa que responde aos esclarecimentos do IPL responde
    aos do ano que vem também.
    """

    def setUp(self):
        super().setUp()
        self.cliente = radar.app.test_client()
        with radar.liga() as c:
            for ref, nif in (("1/2026", "506000000"), ("2/2027", "506000000")):
                c.execute("INSERT INTO anuncios (ref, titulo, entidade, nif,"
                          " data_pub, tipo, url, estado, texto, detalhe_lido)"
                          " VALUES (?,?,?,?,?,?,?,'novo','x',1)",
                          (ref, "Concurso " + ref, "Instituto Politécnico de Leiria",
                           nif, "2026-01-01", "Anúncio de procedimento",
                           "https://dr/" + ref))

    def _a(self, ref):
        with radar.liga() as c:
            return c.execute("SELECT * FROM anuncios WHERE ref=?", (ref,)).fetchone()

    def test_a_chave_e_o_nif_quando_o_ha(self):
        self.assertEqual(radar.chave_da_entidade(self._a("1/2026")), "506000000")

    def test_sem_nif_a_chave_e_o_nome_normalizado(self):
        """93,7% das entidades do radar acham-se assim (medido; ver
        `norma_entidade()`), e sem isto os contactos de uma entidade
        cujo NIF o DR não publica não tinham onde viver.

        **Com o prefixo `n:` desde 17/09/2026** (fase 2 do
        `docs/historico/CICLOS.md`): é a mesma chave do corpus
        (`chave_entidade()`). Este teste pregava a escrita antiga, sem
        prefixo, e eram duas escritas do mesmo facto — a ficha da
        entidade não achava os contactos dela.
        """
        with radar.liga() as c:
            c.execute("UPDATE anuncios SET nif='' WHERE ref='1/2026'")
        chave = radar.chave_da_entidade(self._a("1/2026"))
        self.assertTrue(chave)
        self.assertNotEqual(chave, "506000000")
        self.assertEqual(chave, "n:" + radar.norma_entidade(
            "Instituto Politécnico de Leiria"))
        self.assertEqual(chave, radar.chave_entidade(
            "", "Instituto Politécnico de Leiria"))

    def test_o_contacto_aparece_nos_OUTROS_concursos_da_mesma_entidade(self):
        """É o ponto todo da etapa: o contacto é da entidade."""
        radar.criar_contacto("506000000", "Maria Silva", "Júri",
                             "maria@ipl.pt", entidade="IPL")
        for ref in ("1/2026", "2/2027"):
            html_ = self.cliente.get("/anuncio/%s" % quote(ref, safe="")
                                     ).get_data(as_text=True)
            self.assertIn("Maria Silva", html_, ref)
            self.assertIn("maria@ipl.pt", html_, ref)

    def test_um_contacto_sem_nome_nao_se_cria(self):
        """Não se encontra depois, que é o mesmo que não existir."""
        self.assertIsNone(radar.criar_contacto("506000000", "  "))
        self.assertIsNone(radar.criar_contacto("", "Maria"))
        self.assertEqual(radar.contactos_de("506000000"), [])

    def test_criar_e_apagar_pela_ficha(self):
        r = self.cliente.post("/contacto/nova", data={
            "chave": "506000000", "entidade": "IPL", "volta": "1/2026",
            "nome": "João Costa", "papel": "Compras",
            "telefone": "244 000 000"})
        self.assertEqual(r.status_code, 302)
        linhas = radar.contactos_de("506000000")
        self.assertEqual([l["nome"] for l in linhas], ["João Costa"])
        self.assertEqual(linhas[0]["telefone"], "244 000 000")
        r = self.cliente.post("/contacto/%d/apagar" % linhas[0]["id"])
        self.assertEqual(r.status_code, 302)
        self.assertEqual(radar.contactos_de("506000000"), [])

    def test_os_contactos_vao_no_triagem_jsonl(self):
        """Um nome e um telefone que alguém escreveu, e que fonte
        nenhuma refaz -- a mesma razão das propostas."""
        radar.criar_contacto("506000000", "Maria Silva", "Júri",
                             "maria@ipl.pt", entidade="IPL")
        caminho = os.path.join(self.pasta, "triagem.jsonl")
        radar.exportar_triagem(caminho)
        with open(caminho, encoding="utf-8") as f:
            linhas = [json.loads(l) for l in f if l.strip()]
        contactos = [l for l in linhas if l["tabela"] == "contactos"]
        self.assertEqual(len(contactos), 1)
        self.assertEqual(sorted(contactos[0]),
                         sorted(("tabela",) + radar.COLUNAS_DO_CONTACTO))
        # e voltam no restauro
        with radar.liga() as c:
            c.execute("DELETE FROM contactos")
        radar.repor_triagem(caminho)
        self.assertEqual([l["nome"] for l in radar.contactos_de("506000000")],
                         ["Maria Silva"])

    def test_as_colunas_do_contacto_sao_as_da_tabela(self):
        with radar.liga() as c:
            na_tabela = {r["name"] for r in c.execute(
                "PRAGMA table_info(contactos)")}
        self.assertEqual(na_tabela, set(radar.COLUNAS_DO_CONTACTO))


class TestPorqueDoGit(unittest.TestCase):
    """01/09/2026: um push recusado ficava gravado como "git push: To
    https://github.com/afonsonp/radarconcursos.git" — o endereço comia
    os 80 caracteres da linha dos indicadores e a razão nunca se via.
    Foi o que aconteceu a um "cannot lock ref" de 31/08: ficou um dia
    inteiro na base sem ninguém poder saber o que dizia."""

    class Falso:
        def __init__(self, err=b"", out=b""):
            self.stderr, self.stdout = err, out

    def test_tira_o_endereco_e_o_error_final(self):
        saida = (b"To https://github.com/afonsonp/radarconcursos.git\n"
                 b" ! [remote rejected] master -> master (cannot lock ref "
                 b"'refs/heads/master': is at 95919b5 but expected 3b53318)\n"
                 b"error: failed to push some refs to 'https://github.com/"
                 b"afonsonp/radarconcursos.git'\n")
        porque = radar.porque_do_git(self.Falso(saida))
        self.assertTrue(porque.startswith("! [remote rejected]"))
        self.assertIn("cannot lock ref", porque)
        self.assertNotIn("github.com", porque)

    def test_fica_numa_linha_so(self):
        porque = radar.porque_do_git(self.Falso(b"uma\nduas\ntres\n"))
        self.assertEqual(porque, "uma duas tres")

    def test_usa_o_stdout_quando_nao_ha_stderr(self):
        self.assertEqual(radar.porque_do_git(self.Falso(b"", b"so no out")),
                         "so no out")

    def test_se_so_houver_cabecalho_mostra_o_cabecalho(self):
        # nunca devolver vazio: uma marca de erro em branco é pior que
        # uma marca com pouco
        porque = radar.porque_do_git(self.Falso(b"To https://exemplo/r.git\n"))
        self.assertIn("exemplo", porque)

    def test_respeita_o_tecto(self):
        self.assertEqual(len(radar.porque_do_git(self.Falso(b"x" * 400))), 150)

    def test_sem_saida_nenhuma_da_vazio(self):
        self.assertEqual(radar.porque_do_git(self.Falso()), "")


class TestEmpurrarTriagem(BaseTemporaria):
    """B15, sub-decisão fechada a 31/08/2026: commit+push automáticos
    do triagem.jsonl em cada verificação. O erro que se trava: um push
    falhado com o commit já feito deixava o diff limpo, e um gatilho só
    por diff nunca mais tentava o push — a cópia externa ficava para
    trás em silêncio. Tudo com repositórios temporários, sem rede."""

    def _git(self, pasta, *args):
        import subprocess
        return subprocess.run(["git"] + list(args), cwd=pasta,
                              capture_output=True)

    def _repo(self, com_remoto):
        os.makedirs(os.path.join(self.pasta, "trabalho"))
        trabalho = os.path.join(self.pasta, "trabalho")
        self._git(trabalho, "init", "-q", "-b", "master")
        self._git(trabalho, "config", "user.email", "t@t")
        self._git(trabalho, "config", "user.name", "t")
        with open(os.path.join(trabalho, "triagem.jsonl"), "w") as f:
            f.write("{}\n")
        self._git(trabalho, "add", "triagem.jsonl")
        self._git(trabalho, "commit", "-q", "-m", "inicial")
        if com_remoto:
            bare = os.path.join(self.pasta, "remoto.git")
            self._git(self.pasta, "init", "-q", "--bare", "-b", "master",
                      "remoto.git")
            self._git(trabalho, "remote", "add", "origin", bare)
            self._git(trabalho, "push", "-q", "-u", "origin", "master")
        return trabalho

    def _mexe(self, trabalho):
        with open(os.path.join(trabalho, "triagem.jsonl"), "a",
                  encoding="utf-8") as f:
            f.write('{"tabela": "ensaio"}\n')

    def test_fluxo_feliz_e_sem_mudancas(self):
        trabalho = self._repo(com_remoto=True)
        bem, porque = radar.empurrar_triagem(trabalho)
        self.assertTrue(bem)
        self.assertIn("sem mudanças", porque)
        self._mexe(trabalho)
        bem, porque = radar.empurrar_triagem(trabalho)
        self.assertTrue(bem)
        self.assertIn("empurrada", porque)
        # o remoto tem mesmo o commit da triagem
        bare = os.path.join(self.pasta, "remoto.git")
        log = self._git(bare, "log", "--oneline").stdout.decode()
        self.assertIn("triagem:", log)

    def test_push_falhado_retoma_na_volta_seguinte(self):
        # commit à frente do origin SEM mudança no ficheiro: um gatilho
        # só por diff dizia "nada a fazer" e o remoto ficava para trás
        trabalho = self._repo(com_remoto=True)
        self._mexe(trabalho)
        self._git(trabalho, "commit", "-q", "-m", "triagem: preso",
                  "--", "triagem.jsonl")
        bem, porque = radar.empurrar_triagem(trabalho)
        self.assertTrue(bem)
        self.assertIn("empurrada", porque)

    def test_sem_remoto_o_commit_fica_e_o_erro_regista_se(self):
        trabalho = self._repo(com_remoto=False)
        self._mexe(trabalho)
        bem, _ = radar.empurrar_triagem(trabalho)
        self.assertFalse(bem)
        # o commit local ficou — a exportação não se perdeu, só a cópia
        # externa é que espera pela próxima volta
        log = self._git(trabalho, "log", "--oneline").stdout.decode()
        self.assertIn("triagem:", log)
        self.assertTrue(radar.le_marca("ultimo_erro_triagem_git"))

    def test_o_push_bem_sucedido_apaga_a_marca_do_erro(self):
        # 04/09/2026: o painel mostrava um push recusado a 31/08 depois
        # de dezenas de pushes bons. A marca escrevia-se na falha e não
        # se apagava nunca — mandava procurar uma avaria que já não
        # havia. A série na tabela `erros` é que guarda a história.
        trabalho = self._repo(com_remoto=False)
        self._mexe(trabalho)
        radar.empurrar_triagem(trabalho)            # falha: sem remoto
        self.assertTrue(radar.le_marca("ultimo_erro_triagem_git"))
        bare = os.path.join(self.pasta, "remoto.git")
        self._git(self.pasta, "init", "-q", "--bare", "-b", "master",
                  "remoto.git")
        self._git(trabalho, "remote", "add", "origin", bare)
        self._git(trabalho, "push", "-q", "-u", "origin", "master")
        bem, _ = radar.empurrar_triagem(trabalho)
        self.assertTrue(bem)
        self.assertEqual(radar.le_marca("ultimo_erro_triagem_git"), "")
        # a história não se perde: continua na série
        with radar.liga() as c:
            self.assertEqual(c.execute(
                "SELECT COUNT(*) n FROM erros WHERE tipo='triagem-git'"
            ).fetchone()["n"], 1)

    def test_sem_nada_por_empurrar_tambem_apaga(self):
        # o caso comum: a falha foi de rede, e na volta seguinte já não
        # há nada para empurrar. Se só o push limpasse, a marca ficava
        # até à próxima vez que a triagem mudasse — dias.
        trabalho = self._repo(com_remoto=True)
        radar.marca_erro("ultimo_erro_triagem_git", "triagem-git", "de ontem")
        bem, porque = radar.empurrar_triagem(trabalho)
        self.assertTrue(bem)
        self.assertIn("sem mudanças", porque)
        self.assertEqual(radar.le_marca("ultimo_erro_triagem_git"), "")


class TestFaltaDePecasNaoEErroDeLeitura(unittest.TestCase):
    """04/09/2026: os três «Último erro da leitura pelo modelo» que o
    painel mostrava não eram do modelo. Um era uma consulta preliminar
    (PT1.NTC.3785562), que não TEM Caderno de Encargos; outro um anúncio
    cujo `link_pecas` é a página de entrada da Vortal, sem código de
    procedimento; o terceiro tinha sido lido com sucesso 1h25 depois do
    erro que continuava no ecrã.

    A acusação era do sítio errado: culpava o modelo de uma coisa que é
    das peças. O que este teste segura é a decisão — as duas razões de
    «não há o que ler» são reconhecidas, e uma falha a sério continua a
    ser falha."""

    def test_as_duas_razoes_de_nao_haver_nada(self):
        for porque in radar.SEM_NADA_PARA_LER:
            self.assertTrue(radar.e_falta_de_pecas(porque), porque)

    def test_a_razao_que_analisar_pecas_devolve_mesmo(self):
        # o texto está escrito em dois sítios; se um mudar sem o outro,
        # a falta de peças volta a contar como erro do modelo em silêncio
        self.assertIn("ainda não há Caderno de Encargos nem Programa em "
                      "disco", radar.SEM_NADA_PARA_LER)
        self.assertIn("os documentos deste concurso são digitalizações, "
                      "sem texto que se possa ler", radar.SEM_NADA_PARA_LER)

    def test_uma_falha_a_serio_continua_a_ser_falha(self):
        self.assertFalse(radar.e_falta_de_pecas(
            "groq: 429 Too Many Requests"))
        self.assertFalse(radar.e_falta_de_pecas(
            "falta a chave da API: põe-na em chave_api.txt, na pasta do radar"))
        self.assertFalse(radar.e_falta_de_pecas(""))
        self.assertFalse(radar.e_falta_de_pecas(None))


class TestLimpaErro(BaseTemporaria):
    """A marca diz «está avariado agora?», a série diz «o que já correu
    mal». Antes de 04/09/2026 a marca só sabia dizer que sim."""

    def test_apaga_a_marca_e_guarda_a_serie(self):
        radar.marca_erro("docs_ultimo_erro", "pecas", "rebentou")
        self.assertTrue(radar.le_marca("docs_ultimo_erro"))
        radar.limpa_erro("docs_ultimo_erro")
        self.assertEqual(radar.le_marca("docs_ultimo_erro"), "")
        with radar.liga() as c:
            self.assertEqual(c.execute(
                "SELECT COUNT(*) n FROM erros WHERE tipo='pecas'"
            ).fetchone()["n"], 1)

    def test_limpar_o_que_nao_existe_nao_rebenta(self):
        radar.limpa_erro("marca_que_nunca_existiu")

    def test_a_linha_do_ecra_desaparece_com_a_marca(self):
        # o que o Afonso vê: sem marca não há linha nenhuma no bloco
        self.assertEqual(radar.linhas_de_ultimos_erros(triagem=""), [])
        self.assertEqual(len(radar.linhas_de_ultimos_erros(
            triagem="2026-08-31 17:00: git push: recusado")), 1)


class TestConsultasPreliminares(BaseTemporaria):
    """B14 (decisão do Afonso a 31/08/2026): a segunda fonte traz SÓ o
    que a parte L não publica — consultas preliminares da pesquisa
    pública da Vortal. O que se trava: duplicar anúncios do DR, o
    rótulo do tipo mudar com o idioma da sessão, e as releituras do DR
    tentarem ler uma consulta que lá não existe."""

    ITEM = {"uniqueIdentifier": "PT1.NTC.999", "reference": "2026/1",
            "description": "CONSULTA PRELIMINAR –  luvas de nitrilo ",
            "authorityName": "ULS de Ensaio, E. P. E.", "country": "PT",
            "publishDate": "2026-08-31T08:05:52.133Z",
            "deadline": "2026-09-04T22:59:00Z",
            "procedureTypeLabel": "GovPT - Consulta Preliminar",
            "basePrice": 478500.0}

    def test_entra_com_fonte_propria_e_sem_detalhe_do_dr(self):
        self.assertEqual(radar._guardar_preliminar(dict(self.ITEM)), 1)
        with radar.liga() as c:
            a = c.execute("SELECT * FROM anuncios "
                          "WHERE ref='PT1.NTC.999'").fetchone()
        self.assertEqual(a["fonte"], "vortal")
        # por ler: a pesquisa não traz CPV nem NIPC — quem os vai
        # buscar é ler_preliminares(). Marcar como lido aqui dizia que
        # o anúncio estava completo sem o campo por que todos filtram
        self.assertEqual(a["detalhe_lido"], 0)
        self.assertEqual(a["data_pub"], "2026-08-31")
        # 22:59Z é 23:59 em Lisboa, do MESMO dia — a conversão não pode
        # empurrar o prazo para o dia seguinte
        self.assertEqual(a["prazo"], "2026-09-04")
        self.assertEqual(a["preco_base"], "478.500,00 EUR")
        self.assertEqual(a["plataforma"], "vortal")
        self.assertEqual(a["tipo"], "Consulta preliminar")
        # normalizado: é por aqui que a pesquisa e os alertas procuram
        self.assertIn("consulta preliminar", a["titulo_norm"])
        self.assertIn("PT1.NTC.999", a["url"])

    def test_rever_a_mesma_consulta_nao_mexe_na_triagem(self):
        radar._guardar_preliminar(dict(self.ITEM))
        with radar.liga() as c:
            c.execute("UPDATE anuncios SET estado='interessa' "
                      "WHERE ref='PT1.NTC.999'")
        # a verificação seguinte volta a vê-la na listagem: OR IGNORE
        self.assertEqual(radar._guardar_preliminar(dict(self.ITEM)), 0)
        with radar.liga() as c:
            a = c.execute("SELECT estado FROM anuncios "
                          "WHERE ref='PT1.NTC.999'").fetchone()
        self.assertEqual(a["estado"], "interessa")

    def test_os_dois_rotulos_do_tipo(self):
        # "GovPT - Consulta Preliminar" (sessão pt) e "Quick Tender
        # GovPT" (sessão en) são o MESMO tipo — verificado item a item;
        # filtrar só por um deles perdia metade consoante o idioma
        for rotulo in ("GovPT - Consulta Preliminar", "Quick Tender GovPT"):
            self.assertIn(rotulo.strip().lower(), radar.TIPOS_PRELIMINAR)
        self.assertNotIn("concurso público", radar.TIPOS_PRELIMINAR)

    def test_preco_da_api_sai_em_formato_portugues(self):
        self.assertEqual(radar._texto_do_preco(478500), "478.500,00 EUR")
        self.assertEqual(radar._texto_do_preco(1234567.5),
                         "1.234.567,50 EUR")
        self.assertEqual(radar._texto_do_preco(None), "")
        # e o resto da aplicação lê de volta o que se escreveu
        self.assertEqual(radar.euros_do_texto("478.500,00 EUR"), 478500.0)

    def test_as_releituras_do_dr_ignoram_a_fonte_vortal(self):
        import inspect
        # o contrato: reler_marcados só toca na fonte do DR — uma
        # consulta preliminar não tem página de detalhe no DR
        self.assertIn("COALESCE(fonte,'dr')='dr'",
                      inspect.getsource(radar.reler_marcados))

    def test_o_link_com_ntc_salta_o_primeiro_salto_da_cadeia(self):
        # o link público das consultas já traz o PT1.NTC.x às claras:
        # a cadeia das peças vai directa aos documentos
        class Sessao:
            def __init__(self):
                self.urls = []

            def get(self, url, **kw):
                self.urls.append(url)

                class R:
                    def json(self):
                        return []
                return R()
        s = Sessao()
        radar._pecas_vortal(
            s, "https://community.vortal.biz/Public/"
               "contract-notice-view/PT1.NTC.42/")
        self.assertEqual(len(s.urls), 1)
        self.assertIn("GetContractNoticeDocuments", s.urls[0])


class TestDetalheDaPreliminar(BaseTemporaria):
    """01/09/2026, apanhado pelo Afonso: as consultas preliminares
    entravam **sem se ler o que está lá dentro**. A pesquisa da Vortal
    (SearchTenders) tem 16 campos — título, entidade, datas, estado,
    tipo — e nenhum deles é CPV nem NIPC. Consequência medida: as 24
    consultas na base tinham CPV vazio, o que as tornava invisíveis a
    todo o filtro por CPV, ao recorte do interesse e aos alertas por
    código; e sem NIPC não havia por onde cruzar a entidade com o
    corpus de contratos.

    O detalhe (GetRegionConfigurationByContractNoticeUId) responde ao
    PT1.NTC às claras, sem sessão iniciada, e nas 24 medidas trouxe CPV
    em 100%, NIPC em 100% e peças em 75%."""

    REGIAO = {"regionConfiguration": [
        {"name": "AA1_ManagingAuthorityCN_BusinessCard",
         "value": {"name": "ULS de Ensaio, E. P. E.", "nif": "508080142",
                   "location": "PORTUGAL, Lisboa"}},
        {"name": "AE2_RequestInfoCN_RequestReference", "value": "2026/665"},
        {"name": "AE9_RequestInfoCN_ProcedureType",
         "value": "GovPT - Consulta Preliminar"},
        {"name": "AG1_CPVClassificationCN_MainVocabulary",
         "value": "33140000-3 - Material médico de consumo (CPV)"},
        {"name": "AI1_ObjectOfContractCN_TypeOfContract",
         "value": "Aquisição de Bens Móveis\n"},
        {"name": "AJ7_SchedulingCN_DueDateForReceivingReplies",
         "value": {"dateValue": "2026-09-03T22:59:00Z"}},
        {"name": "CB1_SummaryCN_QuestionnaireHTML",
         "value": "https://exemplo/questionario"},
        {"name": "EA2_AvailableDocumentssCN_ContractDocuments",
         "value": [{"name": "Consulta Preliminar 2026.pdf",
                    "downloadUrl": "https://exemplo/doc"}]},
    ]}

    QUESTIONARIO = ("<html><head><style>#q * { font-family: sans-serif; "
                    "color: rgba(0,0,0,0.65); }</style></head><body>"
                    "<table><thead><th>Item</th><th>Descri&#231;&#227;o</th>"
                    "<th>Qt</th></thead><tbody>"
                    "<tr><td></td><td>1</td><td>Luvas de nitrilo</td>"
                    "<td>1500,00</td><td>UNID</td></tr>"
                    "</tbody></table></body></html>")

    def _sessao(self, regiao=None, questionario=None, rebenta=False):
        teste = self

        class Sessao:
            def __init__(self):
                self.urls = []
                self.headers = {}

            def get(self, url, **kw):
                self.urls.append(url)
                if rebenta:
                    raise radar.requests.RequestException("sem rede")
                corpo = (teste.QUESTIONARIO if questionario is None
                         else questionario)
                dados = teste.REGIAO if regiao is None else regiao

                class R:
                    text = corpo

                    def json(self):
                        return dados
                return R()
        return Sessao()

    def test_o_cpv_sai_nos_oito_digitos_que_a_coluna_usa(self):
        # a coluna guarda "33140000", sem o dígito de controlo e sem a
        # descrição: é o formato que prefixo_cpv() e a árvore já leem.
        # A Vortal escreve "33140000-3 - Material médico de consumo (CPV)"
        campos, aviso = radar.detalhe_da_preliminar(self._sessao(),
                                                    "PT1.NTC.42")
        self.assertEqual(aviso, "")
        self.assertEqual(campos["cpv"], "33140000")
        self.assertEqual(campos["nif"], "508080142")
        self.assertEqual(campos["entidade"], "ULS de Ensaio, E. P. E.")

    def test_varios_cpv_saem_separados_e_sem_repetidos(self):
        regiao = {"regionConfiguration": [
            {"name": "AG1_CPVClassificationCN_MainVocabulary",
             "value": "33140000-3 - Material, 33100000-1 - Equipamento, "
                      "33140000-3 - Material"}]}
        campos, _ = radar.detalhe_da_preliminar(self._sessao(regiao=regiao),
                                                "PT1.NTC.42")
        self.assertEqual(campos["cpv"], "33140000, 33100000")

    def test_a_hora_do_prazo_e_a_de_lisboa_e_nao_a_utc(self):
        # a API dá UTC e a própria Vortal mostra 23:59: no Verão Lisboa
        # é UTC+1. Escrever 22:59 na ficha punha o prazo uma hora mais
        # cedo do que a plataforma diz — e um prazo é a informação pela
        # qual se perde uma proposta
        self.assertEqual(radar.hora_de_lisboa("2026-09-03T22:59:00Z"),
                         "2026-09-03 23:59")
        # em Janeiro não há hora de Verão: UTC e Lisboa coincidem
        self.assertEqual(radar.hora_de_lisboa("2026-01-15T09:30:00Z"),
                         "2026-01-15 09:30")
        # as fronteiras da regra da UE: último domingo de Março (29/03
        # em 2026) e de Outubro (25/10), às 01:00 UTC
        self.assertEqual(radar.hora_de_lisboa("2026-03-29T00:59:00Z"),
                         "2026-03-29 00:59")
        self.assertEqual(radar.hora_de_lisboa("2026-03-29T01:00:00Z"),
                         "2026-03-29 02:00")
        self.assertEqual(radar.hora_de_lisboa("2026-10-25T00:59:00Z"),
                         "2026-10-25 01:59")
        self.assertEqual(radar.hora_de_lisboa("2026-10-25T01:00:00Z"),
                         "2026-10-25 01:00")
        # o que não for data volta como veio, sem rebentar
        self.assertEqual(radar.hora_de_lisboa(""), "")
        self.assertEqual(radar.hora_de_lisboa("nunca"), "nunca")

    def test_o_texto_leva_as_seccoes_e_o_dicionario_nao(self):
        campos, _ = radar.detalhe_da_preliminar(self._sessao(), "PT1.NTC.42")
        texto = campos["texto"]
        self.assertIn("1 - ENTIDADE ADJUDICANTE", texto)
        self.assertIn("NIPC: 508080142", texto)
        self.assertIn("3 - CLASSIFICAÇÃO CPV", texto)
        self.assertIn("Referência da consulta: 2026/665", texto)
        # a data sai formatada e em hora de Lisboa, não o dict cru
        self.assertIn("03/09/2026 23:59", texto)
        self.assertNotIn("dateValue", texto)
        # e o cartão da entidade também não sai como dicionário
        self.assertNotIn("{", texto)

    def test_o_questionario_perde_o_css_e_guarda_os_artigos(self):
        # numa consulta preliminar a lista de artigos É o conteúdo: é a
        # única parte que diz mais do que o título. Vem com 6 KB de CSS
        # inline, que tem de sair ANTES de se despirem as etiquetas —
        # senão a folha de estilos entrava na ficha como se fosse texto
        campos, _ = radar.detalhe_da_preliminar(self._sessao(), "PT1.NTC.42")
        texto = campos["texto"]
        self.assertIn("6 - ARTIGOS SOLICITADOS", texto)
        self.assertIn("Luvas de nitrilo", texto)
        self.assertIn("1500,00", texto)
        self.assertNotIn("font-family", texto)
        self.assertNotIn("rgba(", texto)
        # as entidades HTML desescapam-se: "Descri&#231;&#227;o"
        self.assertIn("Descrição", texto)

    def test_um_questionario_que_falha_nao_derruba_o_detalhe(self):
        teste = self

        class Sessao:
            headers = {}

            def get(self, url, **kw):
                if "questionario" in url:
                    raise radar.requests.RequestException("sem rede")

                class R:
                    text = ""

                    def json(self):
                        return teste.REGIAO
                return R()
        campos, aviso = radar.detalhe_da_preliminar(Sessao(), "PT1.NTC.42")
        self.assertEqual(aviso, "")
        self.assertIn("33140000", campos["cpv"])
        self.assertNotIn("6 - ARTIGOS SOLICITADOS", campos["texto"])

    def test_uma_resposta_vazia_nao_passa_por_detalhe_lido(self):
        campos, aviso = radar.detalhe_da_preliminar(
            self._sessao(regiao={}), "PT1.NTC.42")
        self.assertEqual(campos, {})
        self.assertIn("vazio", aviso)
        campos, aviso = radar.detalhe_da_preliminar(
            self._sessao(rebenta=True), "PT1.NTC.42")
        self.assertEqual(campos, {})
        self.assertIn("falhou", aviso)

    def test_ler_preliminares_enche_e_marca_como_lido(self):
        radar._guardar_preliminar(
            dict(TestConsultasPreliminares.ITEM))
        # entra por ler, sem CPV
        with radar.liga() as c:
            a = c.execute("SELECT detalhe_lido, cpv FROM anuncios "
                          "WHERE ref='PT1.NTC.999'").fetchone()
        self.assertEqual(a["detalhe_lido"], 0)
        sessao = self._sessao()
        antigo = radar.requests.Session
        radar.requests.Session = lambda: sessao
        try:
            lidas, aviso = radar.ler_preliminares()
        finally:
            radar.requests.Session = antigo
        self.assertEqual((lidas, aviso), (1, ""))
        with radar.liga() as c:
            a = c.execute("SELECT * FROM anuncios "
                          "WHERE ref='PT1.NTC.999'").fetchone()
        self.assertEqual(a["detalhe_lido"], 1)
        self.assertEqual(a["cpv"], "33140000")
        self.assertEqual(a["nif"], "508080142")
        self.assertIn("NIPC: 508080142", a["texto"])
        # a entidade normalizada acompanha o nome novo: é por ela que a
        # pesquisa procura
        self.assertIn("uls de ensaio", a["entidade_norm"])
        # e não se relê o que já está lido
        self.assertEqual(radar.ler_preliminares()[0], 0)

    def test_um_detalhe_que_falha_fica_por_ler_para_a_proxima(self):
        radar._guardar_preliminar(dict(TestConsultasPreliminares.ITEM))
        sessao = self._sessao(rebenta=True)
        antigo = radar.requests.Session
        radar.requests.Session = lambda: sessao
        try:
            lidas, aviso = radar.ler_preliminares()
        finally:
            radar.requests.Session = antigo
        self.assertEqual(lidas, 0)
        self.assertIn("falhou", aviso)
        with radar.liga() as c:
            a = c.execute("SELECT detalhe_lido FROM anuncios "
                          "WHERE ref='PT1.NTC.999'").fetchone()
        # continua por ler: marcar como lido um detalhe que não chegou
        # dizia que o anúncio estava completo sem CPV nenhum
        self.assertEqual(a["detalhe_lido"], 0)

    def test_a_entidade_vazia_nao_apaga_a_que_ja_la_estava(self):
        radar._guardar_preliminar(dict(TestConsultasPreliminares.ITEM))
        regiao = {"regionConfiguration": [
            {"name": "AG1_CPVClassificationCN_MainVocabulary",
             "value": "33140000-3 - Material"}]}
        sessao = self._sessao(regiao=regiao)
        antigo = radar.requests.Session
        radar.requests.Session = lambda: sessao
        try:
            radar.ler_preliminares()
        finally:
            radar.requests.Session = antigo
        with radar.liga() as c:
            a = c.execute("SELECT entidade, entidade_norm FROM anuncios "
                          "WHERE ref='PT1.NTC.999'").fetchone()
        # a pesquisa já tinha posto um nome bom: trocá-lo por vazio era
        # perder informação por causa de um campo em falta no detalhe
        self.assertEqual(a["entidade"], "ULS de Ensaio, E. P. E.")
        self.assertIn("uls de ensaio", a["entidade_norm"])

    def test_a_fila_do_dr_nao_pesca_uma_consulta_preliminar(self):
        import inspect
        # as duas passam por detalhe_lido=0, mas o detalhe da Vortal é
        # outro endpoint. Sem este filtro, ler_detalhes() mandava um
        # "PT1.NTC.42" ao portal do DR como se fosse chave dele — e a
        # resposta sem JSON acabava a marcar o token como expirado. Um
        # falso alarme de captura expirada é pior que não ler nada
        fonte = inspect.getsource(radar.ler_detalhes)
        self.assertIn("COALESCE(fonte,'dr')='dr'", fonte)

    def test_a_recolha_le_o_detalhe_do_que_acabou_de_guardar(self):
        import inspect
        # a pesquisa dá a linha; o CPV vem do detalhe. Guardar sem ler
        # era o erro que esta classe regista
        self.assertIn("ler_preliminares",
                      inspect.getsource(radar.recolher_vortal))


class TestVisualizadorDePecas(unittest.TestCase):
    """O <embed> ficava à mercê da definição do browser: com «transferir
    PDFs em vez de abrir» ligada, o Chrome mostrava um cartão «Abrir»
    que só descarregava (aconteceu ao Afonso a 31/08/2026). O
    visualizador próprio desenha as páginas no servidor com o PyMuPDF,
    que vive em libs/ — e sem ele o código degrada para o embed em vez
    de rebentar."""

    @classmethod
    def setUpClass(cls):
        # o Python da pasta vê o libs/ sozinho; o do sistema, que corre
        # os testes, precisa do caminho
        libs = os.path.join(
            os.path.dirname(os.path.abspath(radar.__file__)), "libs")
        if os.path.isdir(libs) and libs not in sys.path:
            sys.path.append(libs)
        try:
            import pymupdf                    # noqa: F401
            cls.tem_pymupdf = True
        except ImportError:
            cls.tem_pymupdf = False

    def test_ficheiro_que_nao_abre_nao_rebenta(self):
        # sem PyMuPDF ou com um caminho inválido, a resposta é a mesma:
        # 0 páginas / None, e a página cai para o embed
        self.assertEqual(radar.paginas_do_pdf_imagem("nao-existe.pdf"), 0)
        self.assertIsNone(radar.imagem_da_pagina("nao-existe.pdf", 1))

    def _pdf_de_ensaio(self, pasta):
        import pymupdf
        caminho = os.path.join(pasta, "ensaio.pdf")
        doc = pymupdf.open()
        doc.new_page().insert_text((72, 72), "ensaio do visualizador")
        doc.new_page().insert_text((72, 72), "segunda pagina, com ensaio "
                                             "escrito duas vezes: ensaio")
        doc.save(caminho)
        doc.close()
        return caminho

    def test_desenha_a_pagina_como_png(self):
        if not self.tem_pymupdf:
            self.skipTest("sem pymupdf no Python dos testes")
        with tempfile.TemporaryDirectory() as pasta:
            caminho = self._pdf_de_ensaio(pasta)
            self.assertEqual(radar.paginas_do_pdf_imagem(caminho), 2)
            png = radar.imagem_da_pagina(caminho, 1)
            self.assertTrue(png.startswith(b"\x89PNG"))
            # fora do intervalo é None, não uma excepção
            self.assertIsNone(radar.imagem_da_pagina(caminho, 3))
            self.assertIsNone(radar.imagem_da_pagina(caminho, 0))

    def test_a_pesquisa_diz_as_paginas_e_conta_as_vezes(self):
        # a pesquisa que o Afonso pediu a 31/08/2026: no DOCUMENTO, não
        # no bloco de texto — a mesma search_for desenha os destaques
        if not self.tem_pymupdf:
            self.skipTest("sem pymupdf no Python dos testes")
        with tempfile.TemporaryDirectory() as pasta:
            caminho = self._pdf_de_ensaio(pasta)
            self.assertEqual(radar.paginas_com_termo(caminho, "ensaio"),
                             [(1, 1), (2, 2)])
            self.assertEqual(radar.paginas_com_termo(caminho, "ENSAIO"),
                             [(1, 1), (2, 2)])   # sem caso
            self.assertEqual(radar.paginas_com_termo(caminho, "nabo"), [])
            self.assertEqual(radar.paginas_com_termo(caminho, "  "), [])
            # o destaque não parte o desenho da página
            png = radar.imagem_da_pagina(caminho, 2, procurar="ensaio")
            self.assertTrue(png.startswith(b"\x89PNG"))

    def test_pesquisa_em_ficheiro_que_nao_abre_da_vazio(self):
        self.assertEqual(radar.paginas_com_termo("nao-existe.pdf", "x"), [])


class TestDesenhaValor(unittest.TestCase):
    """Os campos longos do essencial ganham a forma que o texto já tem.

    O diagnóstico da fase de desenho (31/08/2026): a "Equipa" do anúncio
    do INFARMED são 3 200 caracteres em 146 linhas, e saíam como um
    bloco corrido no mesmo corpo e peso do resto do essencial -- 80% do
    rolo da ficha a ler-se ao mesmo nível. O texto não muda; ganha
    degraus. Estes testes seguram as três formas e, sobretudo, o que
    NÃO deve virar forma nenhuma.
    """

    def test_perfis_com_pares_viram_cartoes(self):
        valor = ("Gestor de Projeto\n"
                 "Formação: —\n"
                 "Experiência geral: 8 anos\n"
                 "\n"
                 "Product Owner\n"
                 "Formação: Agile/scrum\n"
                 "Experiência geral: 8 anos")
        saida = radar.desenha_valor(valor)
        self.assertEqual(saida.count("class='perfil'"), 2)
        self.assertIn("<b>Gestor de Projeto</b>", saida)
        self.assertIn("<dt>Formação</dt>", saida)
        self.assertIn("<dd>Agile/scrum</dd>", saida)

    def test_travessoes_viram_lista(self):
        valor = ("- Assegurar a boa execução do contrato.\n"
                 "- Entregar os entregáveis em formato eletrónico.\n"
                 "- Destinar os profissionais indicados.")
        saida = radar.desenha_valor(valor)
        self.assertIn("<ul class='pontos'>", saida)
        self.assertEqual(saida.count("<li>"), 3)
        # o travessão desenha-o o CSS; não fica no texto
        self.assertNotIn("- Assegurar", saida)

    def test_numerados_separam_nome_do_detalhe(self):
        valor = ("1. DEUCP\n"
                 "Condições especiais: modelo pré-preenchido em XML\n"
                 "2. Modelo da Proposta (Anexo II)\n"
                 "Condições especiais: conforme o Anexo II")
        saida = radar.desenha_valor(valor)
        self.assertIn("<ol class='numerados'>", saida)
        self.assertIn("<b>DEUCP</b>", saida)
        self.assertIn("modelo pré-preenchido em XML", saida)

    def test_texto_corrido_fica_como_estava(self):
        # uma frase com dois pontos a meio NÃO é um par de perfil: sem
        # esta guarda, "Local: Lisboa, Av. do Brasil" virava tabela
        valor = "Presencial, nas instalações do Parque de Saúde de Lisboa"
        self.assertEqual(radar.desenha_valor(valor), radar.html.escape(valor))

    def test_um_bloco_so_nao_e_grelha_de_perfis(self):
        # dois blocos é o mínimo: um bloco com pares é um campo normal
        valor = "Prazo\nDuração: 10 meses"
        self.assertNotIn("perfis", radar.desenha_valor(valor))

    def test_escapa_sempre(self):
        valor = "- <script>alert(1)</script>\n- outro & mais"
        saida = radar.desenha_valor(valor)
        self.assertNotIn("<script>", saida)
        self.assertIn("&lt;script&gt;", saida)
        self.assertIn("&amp;", saida)

    def test_vazio_da_vazio(self):
        self.assertEqual(radar.desenha_valor(""), "")
        self.assertEqual(radar.desenha_valor(None), "")
        self.assertEqual(radar.desenha_valor("   \n  "), "")


class TestBrowserEsperaPelaPorta(unittest.TestCase):
    """01/09/2026: o main() chamava webbrowser.open() ANTES do app.run().
    Medido, o browser recebia o endereço aos 0,98 s e a porta só
    respondia aos 1,91 s — com o browser já aberto, que é o caso normal,
    o separador novo apanhava a porta fechada e ficava num erro que só
    um F5 tirava. Lia-se como "o radar demora a arrancar"."""

    def setUp(self):
        self.aberto = []
        self.open_antigo = radar.webbrowser.open
        radar.webbrowser.open = lambda url: self.aberto.append(
            (url, time.time()))

    def tearDown(self):
        radar.webbrowser.open = self.open_antigo

    def porta_livre(self):
        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    def test_porta_atende_ve_quem_esta_a_ouvir(self):
        import socket
        with socket.socket() as servidor:
            servidor.bind(("127.0.0.1", 0))
            servidor.listen(1)
            porta = servidor.getsockname()[1]
            self.assertTrue(radar.porta_atende(porta))
        self.assertFalse(radar.porta_atende(self.porta_livre()))

    def test_abre_quando_a_porta_atende(self):
        import socket
        with socket.socket() as servidor:
            servidor.bind(("127.0.0.1", 0))
            servidor.listen(1)
            porta = servidor.getsockname()[1]
            self.assertTrue(radar.abrir_no_browser(porta, espera=5))
        self.assertEqual(len(self.aberto), 1)
        self.assertIn(":%d/" % porta, self.aberto[0][0])

    def test_nao_abre_nada_se_ninguem_atender(self):
        # antes abria à mesma, e o browser mostrava o erro de ligação
        self.assertFalse(radar.abrir_no_browser(self.porta_livre(),
                                                espera=0.4))
        self.assertEqual(self.aberto, [])

    def test_espera_pela_porta_em_vez_de_adivinhar(self):
        # É ISTO a regressão: o servidor só nasce ao fim de umas voltas,
        # e o open() tem de vir depois. A sonda é falsa de propósito —
        # a primeira versão deste teste punha um servidor a nascer meio
        # segundo depois e era intermitente, porque no Windows uma
        # ligação a uma porta com bind e sem listen não é recusada,
        # bloqueia até ao timeout. Um teste de relógio a medir o
        # escalonador não prova nada sobre esta função.
        respostas = [False, False, True]
        sondadas = []
        antigo = radar.porta_atende

        def sonda_falsa(porta, espera=0.5):
            sondadas.append(porta)
            # a última resposta fica a valer, se alguma vez lá chegar
            return respostas[min(len(sondadas) - 1, len(respostas) - 1)]

        radar.porta_atende = sonda_falsa
        try:
            self.assertTrue(radar.abrir_no_browser(4321, espera=5))
        finally:
            radar.porta_atende = antigo
        self.assertEqual(sondadas, [4321, 4321, 4321])
        self.assertEqual(len(self.aberto), 1)
        self.assertIn(":4321/", self.aberto[0][0])

    def test_desiste_sem_abrir_se_a_porta_nunca_atender(self):
        antigo = radar.porta_atende
        radar.porta_atende = lambda porta, espera=0.5: False
        try:
            self.assertFalse(radar.abrir_no_browser(4321, espera=0.3))
        finally:
            radar.porta_atende = antigo
        self.assertEqual(self.aberto, [])


class TestRelogioPassaPeloTrinco(BaseTemporaria):
    """01/09/2026: o relogio() chamava verificar() directamente, por fora
    do trinco e do `passo`. Duas consequências: um slot falhado disparava
    a verificação inteira no arranque do painel — cópia de 93 MB, push da
    triagem, recolha toda — sem nada no ecrã a dizer porquê, e podia
    apanhar um "Verificar agora" a meio, com duas verificações na mesma
    base."""

    def setUp(self):
        super().setUp()
        self.verificacao_antes = dict(radar._VERIFICACAO)
        self.enterContext(unittest.mock.patch.object(
            radar, "ler_config",
            lambda: {"horas_verificacao": ["00:01"],
                     "recuperar_slot_falhado": True}))
        # cada teste troca o verificar(); o patch so garante que volta
        self.enterContext(unittest.mock.patch.object(
            radar, "verificar", radar.verificar))
        radar._VERIFICACAO["a_correr"] = False
        radar._VERIFICACAO["passo"] = ""

    def tearDown(self):
        radar._VERIFICACAO.clear()
        radar._VERIFICACAO.update(self.verificacao_antes)
        super().tearDown()

    def uma_volta_do_relogio(self):
        """Corre uma passagem do ciclo e sai. O time.sleep(60) está fora
        do try/except, por isso um BaseException lá rebenta o while sem
        ser engolido pelo `except Exception` do relógio.

        O `time` do radar troca-se por um sósia, e não se mexe no módulo
        global: o sleep de qualquer outra thread não tem nada a ver com
        isto."""
        class Sosia:
            def __init__(self, real):
                self._real = real

            def __getattr__(self, nome):
                return getattr(self._real, nome)

            def sleep(self, _):
                raise SystemExit

        antigo = radar.time
        radar.time = Sosia(antigo)
        try:
            with self.assertRaises(SystemExit):
                radar.relogio()
        finally:
            radar.time = antigo

    def test_o_slot_falhado_passa_pelo_comecar_verificacao(self):
        pedidos = []
        antigo = radar.comecar_verificacao
        radar.comecar_verificacao = lambda slot=None: (
            pedidos.append(slot), (True, ""))[1]
        try:
            self.uma_volta_do_relogio()
        finally:
            radar.comecar_verificacao = antigo
        hoje = datetime.datetime.now().strftime("%Y-%m-%d")
        self.assertEqual(pedidos, [(hoje, "00:01")])

    def test_o_trinco_recusa_e_o_slot_fica_por_correr(self):
        # com uma verificação a decorrer, a hora NÃO se marca como
        # corrida: senão o slot dava-se por feito sem ninguém o fazer
        radar._VERIFICACAO["a_correr"] = True
        radar._VERIFICACAO["passo"] = "a ler o detalhe"
        self.uma_volta_do_relogio()
        hoje = datetime.datetime.now().strftime("%Y-%m-%d")
        self.assertFalse(radar.slot_corrido(hoje, "00:01"))

    def test_o_slot_marca_se_no_fim_e_com_os_novos(self):
        radar.verificar = lambda cfg=None, passo=None: ("ok", 7)
        radar._VERIFICACAO["a_correr"] = False
        arrancou, _ = radar.comecar_verificacao(slot=("2026-09-01", "09:00"))
        self.assertTrue(arrancou)
        for _ in range(100):                    # a thread é curta
            if radar.slot_corrido("2026-09-01", "09:00"):
                break
            time.sleep(0.02)
        with radar.liga() as c:
            linha = c.execute("SELECT novos FROM slots WHERE dia=? AND "
                              "hora=?", ("2026-09-01", "09:00")).fetchone()
        self.assertIsNotNone(linha)
        self.assertEqual(linha["novos"], 7)

    def test_o_botao_a_mao_nao_marca_slot_nenhum(self):
        # um clique não é um slot: marcá-lo faria a verificação das 17h
        # dar-se por feita porque alguém carregou no botão às 15h
        radar.verificar = lambda cfg=None, passo=None: ("ok", 0)
        radar._VERIFICACAO["a_correr"] = False
        radar.comecar_verificacao()
        time.sleep(0.3)
        with radar.liga() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) n FROM slots")
                             .fetchone()["n"], 0)


class CorpusTemporario(unittest.TestCase):
    """Como a BaseTemporaria, mas para o contratos.db: um corpus
    TEMPORÁRIO — nunca o verdadeiro —, criado e deitado fora por teste."""

    def setUp(self):
        self.pasta = tempfile.mkdtemp()
        # mesma ordem da BaseTemporaria: repoe o CORPUS, o gc.collect()
        # fecha ligacoes penduradas, e so entao a pasta vai fora
        self.addCleanup(shutil.rmtree, self.pasta, ignore_errors=True)
        self.addCleanup(gc.collect)
        self.enterContext(unittest.mock.patch.object(
            radar, "CORPUS", os.path.join(self.pasta, "ensaio-contratos.db")))

    def poe_contrato(self, cid, ganhadores=0, n_adj=None):
        with radar.liga_corpus() as c:
            c.execute("INSERT INTO contratos (id, objecto, data_celebracao, "
                      "prazo_execucao, n_adj) VALUES (?,?,?,?,?)",
                      (cid, "Aquisição de serviços", "2026-01-05", 30, n_adj))
            c.executemany("INSERT INTO contrato_adjudicatario "
                          "(contrato_id, nif, nome) VALUES (?,?,?)",
                          [(cid, str(i), "Empresa %d" % i)
                           for i in range(ganhadores)])

    def n_adj_de(self, cid):
        with radar.liga_corpus() as c:
            return c.execute("SELECT n_adj FROM contratos WHERE id=?",
                             (cid,)).fetchone()[0]

    def esquece_a_marca(self):
        """Põe o corpus como estava antes da coluna existir."""
        with radar.liga_corpus() as c:
            c.execute("DELETE FROM corpus_estado WHERE chave='n_adj_cheio'")


class TestNAdjEnchePorMarca(CorpusTemporario):
    """01/09/2026: o iniciar_corpus() corria o "UPDATE contratos SET n_adj
    ... WHERE n_adj IS NULL" em TODOS os arranques. É a única das quatro
    migrações desta função cujo IS NULL não tem índice que o sirva, por
    isso varria o corpus inteiro — 1,6 GB, 38,9 s a frio na pen — para
    encontrar zero linhas. Era o arranque do painel inteiro. Passou a
    marca no corpus_estado, como o html_desescapado.

    O que estes testes seguram: que a migração continua a encher o corpus
    antigo, e que na segunda vez não faz nada."""

    def test_enche_o_corpus_antigo(self):
        radar.iniciar_corpus()
        self.esquece_a_marca()
        self.poe_contrato(7, ganhadores=3)
        radar.iniciar_corpus()
        self.assertEqual(self.n_adj_de(7), 3)

    def test_sem_adjudicatarios_vale_um(self):
        # nunca zero: é divisor no gráfico de quem ganha
        radar.iniciar_corpus()
        self.esquece_a_marca()
        self.poe_contrato(8, ganhadores=0)
        radar.iniciar_corpus()
        self.assertEqual(self.n_adj_de(8), 1)

    def test_nao_mexe_no_que_ja_tem_valor(self):
        radar.iniciar_corpus()
        self.esquece_a_marca()
        self.poe_contrato(9, ganhadores=3, n_adj=1)
        radar.iniciar_corpus()
        self.assertEqual(self.n_adj_de(9), 1)

    def test_deixa_a_marca(self):
        radar.iniciar_corpus()
        with radar.liga_corpus() as c:
            self.assertTrue(c.execute(
                "SELECT 1 FROM corpus_estado WHERE chave='n_adj_cheio'"
            ).fetchone())

    def test_segunda_vez_nao_varre(self):
        # É ISTO o arranque de 39 segundos. Com a marca posta, a linha
        # deixada a NULL de propósito tem de continuar a NULL: se voltar
        # a 2, o UPDATE correu outra vez — e num corpus a sério isso são
        # 1,6 GB varridos a cada arranque do painel.
        radar.iniciar_corpus()
        self.poe_contrato(10, ganhadores=2)
        radar.iniciar_corpus()
        self.assertIsNone(self.n_adj_de(10))

    def test_o_importador_e_que_enche_a_coluna(self):
        # A marca só é segura porque nenhuma linha nova chega com o
        # n_adj a NULL: o importador escreve-o sempre, por estar no
        # COLS_CONTRATO (com max(1, len(ganhadores))). Tirá-lo de lá
        # reabre o buraco em silêncio.
        self.assertIn("n_adj", radar.COLS_CONTRATO)


class TestPrimeiroAnoDoCorpus(CorpusTemporario):
    """03/09/2026: a página "procurar entidade" dizia "o corpus só conhece
    quem já assinou contratos desde 2020" — com o 2020 escrito à mão no
    código. No dia em que o corpus passou a começar em 2015, a frase
    ficou a mentir ao Afonso sobre cinco anos que ele tinha em disco.

    Um número que um ecrã mostra tem de sair dos dados. O que estes
    testes seguram: que sai do MIN(ano), e que os dois casos em que não
    há nada para ler não rebentam a página."""

    def poe_ano(self, cid, ano):
        with radar.liga_corpus() as c:
            c.execute("INSERT INTO contratos (id, ano) VALUES (?,?)",
                      (cid, ano))

    def test_le_o_ano_mais_antigo(self):
        radar.iniciar_corpus()
        self.poe_ano(1, 2019)
        self.poe_ano(2, 2015)
        self.poe_ano(3, 2026)
        self.assertEqual(radar.primeiro_ano_corpus(), 2015)

    def test_sem_ficheiro_da_a_omissao(self):
        # antes de o corpus ser importado não há ficheiro nenhum
        self.assertEqual(radar.primeiro_ano_corpus(), 2015)

    def test_corpus_vazio_da_a_omissao(self):
        # o MIN de zero linhas é NULL, e um NULL no %d rebentava a página
        radar.iniciar_corpus()
        self.assertEqual(radar.primeiro_ano_corpus(), 2015)


class TestPecasDaVortalNasDuasFormas(unittest.TestCase):
    """A Vortal deixou de trazer peças e ninguém deu por isso.

    Medido a 01/09/2026 no 22005/2026: a resposta do primeiro salto
    (GetPublicTenderInformation) vem de DUAS formas -- com
    `contractNoticeUrl` e `documentList` vazia (o caminho de sempre), ou
    com `documentList` cheia e sem `contractNoticeUrl`. O radar só sabia
    ler a primeira e, na segunda, devolvia lista vazia **sem erro
    nenhum**: trazia o anúncio e mais nada.
    """

    class FalsaSessao:
        """Devolve JSON por endereço. Sem rede, como todos os outros."""

        def __init__(self, por_url, ficheiros=None):
            self.por_url = por_url
            self.ficheiros = ficheiros or {}
            self.pedidos = []

        class R:
            def __init__(self, dados):
                self._dados = dados

            def json(self):
                return self._dados

        def get(self, url, **k):
            self.pedidos.append(url)
            return self.R(self.por_url[url])

    def _sessao(self, info, docs=None):
        return self.FalsaSessao({radar.VORTAL_INFO: info,
                                 radar.VORTAL_DOCS: docs or []})

    @contextlib.contextmanager
    def sem_descarregar(self, falso):
        """Troca _descarregar e **repoe-o**. Um `del` deixava o modulo
        sem a funcao para os testes seguintes -- tres deles passaram a
        rebentar com AttributeError, e o culpado nao era nenhum deles."""
        antigo = radar._descarregar
        radar._descarregar = falso
        try:
            yield
        finally:
            radar._descarregar = antigo

    def test_documentos_no_primeiro_salto_sao_lidos(self):
        # a forma que dava zero peças em silêncio
        s = self._sessao({"documentList": [
            {"documentName": "Peças.pdf", "downloadUrl": "http://x/1"}],
            "downloadAllUrl": "http://x/tudo"})
        baixados = []
        with self.sem_descarregar(lambda ses, url, **k: (
                baixados.append(url) or ("Peças.pdf", b"%PDF"))):
            saida, grandes = radar._pecas_vortal(s, "http://v/abc")
        self.assertEqual([n for n, _ in saida], ["Peças.pdf"])
        self.assertEqual(baixados, ["http://x/1"])
        # e não se foi ao segundo salto: não há PT1.NTC nenhum a pedir
        self.assertNotIn(radar.VORTAL_DOCS, s.pedidos)

    def test_sem_documentos_desce_ao_segundo_salto(self):
        # a forma antiga tem de continuar a funcionar
        s = self._sessao(
            {"documentList": [],
             "contractNoticeUrl": "https://community.vortal.biz/Public/"
                                  "contract-notice-view/PT1.NTC.42/"},
            [{"name": "CE.pdf", "downloadUrl": "http://x/2"}])
        with self.sem_descarregar(lambda ses, url, **k: ("CE.pdf", b"%PDF")):
            saida, _ = radar._pecas_vortal(s, "http://v/abc")
        self.assertEqual([n for n, _ in saida], ["CE.pdf"])
        self.assertIn(radar.VORTAL_DOCS, s.pedidos)

    def test_link_com_pt1ntc_salta_o_primeiro_pedido(self):
        # as consultas preliminares (B14) já trazem o PT1.NTC às claras
        s = self._sessao({}, [{"name": "A.pdf", "downloadUrl": "http://x/3"}])
        with self.sem_descarregar(lambda ses, url, **k: ("A.pdf", b"%PDF")):
            saida, _ = radar._pecas_vortal(
                s, "https://community.vortal.biz/Public/"
                   "contract-notice-view/PT1.NTC.9/")
        self.assertEqual(len(saida), 1)
        self.assertNotIn(radar.VORTAL_INFO, s.pedidos)


class TestLinkDoProcedimento(unittest.TestCase):
    """"Abrir plataforma" abria o link das PEÇAS.

    Na acingov isso descarrega um ZIP, na Vortal dá na lista dos
    ficheiros e na anogov idem: nenhum dos três é o procedimento. O
    botão passou a ter destino por plataforma -- e onde não há página
    pública (acingov, verificado a 01/09/2026: "para aceder a este
    procedimento inicie sessão") diz o que abre em vez de prometer.
    """

    @staticmethod
    def _a(plat, link, proc=None, ref="1/2026"):
        return {"ref": ref, "plataforma": plat, "link_pecas": link,
                "link_proc": proc}

    def test_vortal_com_pt1ntc_no_proprio_link(self):
        destino, rotulo, _ = radar.link_do_procedimento(
            self._a("vortal", "https://community.vortal.biz/Public/"
                              "contract-notice-view/PT1.NTC.7/"))
        self.assertIn("contract-notice-view/PT1.NTC.7", destino)
        self.assertIn("Vortal", rotulo)

    def test_vortal_cifrado_passa_pela_rota_que_resolve(self):
        destino, _, _ = radar.link_do_procedimento(
            self._a("vortal", "https://community.vortal.biz/Public/"
                              "public-tender-documents/AbC"))
        self.assertEqual(destino, "/plataforma/1%2F2026")

    def test_vortal_ja_resolvido_nao_volta_a_rota(self):
        destino, _, _ = radar.link_do_procedimento(
            self._a("vortal", "https://community.vortal.biz/Public/"
                              "public-tender-documents/AbC",
                    proc="https://community.vortal.biz/Public/"
                         "contract-notice-view/PT1.NTC.8/"))
        self.assertIn("PT1.NTC.8", destino)

    def test_acingov_nao_promete_o_que_nao_ha(self):
        destino, rotulo, dica = radar.link_do_procedimento(
            self._a("acingov", "https://www.acingov.pt/.../"
                               "donwloadProcedurePiece/MTEz"))
        # nunca o link do ZIP: era isso que o botão fazia
        self.assertNotIn("donwloadProcedurePiece", destino)
        self.assertEqual(destino, radar.ACINGOV_PESQUISA)
        self.assertIn("Procurar", rotulo)
        self.assertIn("sessão iniciada", dica)

    def test_anogov_o_acessodocs_e_a_pagina_do_procedimento(self):
        link = ("https://www.anogov.com/x/faces/app/acessoDocs.jsp"
                "?codigoAcesso=ABC")
        destino, rotulo, _ = radar.link_do_procedimento(
            self._a("anogov", link))
        self.assertEqual(destino, link)
        self.assertIn("anogov", rotulo)

    def test_sem_link_nenhum_nao_ha_botao(self):
        destino, _, _ = radar.link_do_procedimento(self._a("", ""))
        self.assertIsNone(destino)


class TestInteresse(unittest.TestCase):
    """O interesse limita a lista de anúncios e NÃO entra em condicoes().

    O motor serve também os alertas e os filtros guardados: um recorte
    lá dentro fazia um alerta deixar de ver, em silêncio, o que vê hoje.
    """

    def test_desligado_nao_recorta(self):
        frag, vals = radar.condicao_do_interesse(
            args={}, cfg={"interesse_activo": False,
                          "interesse_cpv": "72000000"})
        self.assertEqual((frag, vals), ("", []))

    def test_ligado_sem_cpv_nao_esvazia_o_ecra(self):
        # ligado e por definir: um ecrã em branco lê-se como avaria
        frag, _ = radar.condicao_do_interesse(
            args={}, cfg={"interesse_activo": True, "interesse_cpv": ""})
        self.assertEqual(frag, "")

    def test_ligado_recorta_pelo_cpv(self):
        frag, vals = radar.condicao_do_interesse(
            args={}, cfg={"interesse_activo": True,
                          "interesse_cpv": "72000000"})
        self.assertIn("cpv LIKE ?", frag)
        self.assertEqual(vals, ["72%", "%, 72%"])

    def test_o_que_se_tira_entra_como_NOT(self):
        frag, vals = radar.condicao_do_interesse(
            args={}, cfg={"interesse_activo": True,
                          "interesse_cpv": "72000000",
                          "interesse_cpv_excl": "72212000"})
        self.assertIn("NOT (", frag)
        # o COALESCE não é decorativo: um anúncio ainda sem CPV lido não
        # é "CPV 72212", e o NOT (NULL LIKE x) é NULL
        self.assertIn("COALESCE(cpv,'')", frag)
        self.assertEqual(vals, ["72%", "%, 72%", "72212%", "%, 72212%"])

    def test_interesse_nao_na_url_levanta_o_recorte(self):
        frag, _ = radar.condicao_do_interesse(
            args={"interesse": "nao"},
            cfg={"interesse_activo": True, "interesse_cpv": "72000000"})
        self.assertEqual(frag, "")

    def test_o_motor_dos_filtros_nao_sabe_do_interesse(self):
        # a guarda que interessa: condicoes() serve os alertas
        onde, _ = radar.condicoes({"estado": ""})
        self.assertNotIn("cpv LIKE", onde)
        self.assertNotIn("interesse", onde)


class TestRecorteDaLista(unittest.TestCase):
    """A aba e o interesse são UM recorte só.

    Aplicado em quatro consultas da mesma página (lista, contagem de
    cada aba, selector das plataformas, total do filtro): um número que
    conte com outro recorte abre uma lista diferente da que promete.
    """

    def _com(self, cfg):
        antigo = radar.ler_config
        radar.ler_config = lambda: dict(radar.CONFIG_INICIAL, **cfg)
        try:
            with radar.app.test_request_context("/?estado=porver"):
                return radar.recorte_da_lista("submetido")
        finally:
            radar.ler_config = antigo

    def test_sem_interesse_e_so_a_aba(self):
        frag, vals = self._com({"interesse_activo": False})
        self.assertIn("EXISTS", frag)
        self.assertEqual(vals, ["submetido"])

    def test_com_interesse_junta_os_dois_com_E(self):
        frag, vals = self._com({"interesse_activo": True,
                                "interesse_cpv": "72000000"})
        self.assertIn("EXISTS", frag)
        self.assertIn("cpv LIKE ?", frag)
        self.assertIn(") AND (", frag)
        # a ordem dos valores tem de seguir a dos ? -- aba primeiro
        self.assertEqual(vals, ["submetido", "72%", "%, 72%"])


class TestMotivoDoAbandono(unittest.TestCase):
    """Abandonar sem dizer porquê deixa a aba dos abandonados inútil.

    Decisão do Afonso a 01/09/2026: âmbito fechado. O `required` do
    selector é conveniência do browser -- a guarda é no servidor.
    """

    def setUp(self):
        self.cliente = radar.app.test_client()

    def test_sem_motivo_o_servidor_recusa(self):
        r = self.cliente.post("/estado/1%2F2026/descartado", data={})
        self.assertEqual(r.status_code, 302)
        self.assertIn("aviso=", r.headers["Location"])
        self.assertIn("motivo", r.headers["Location"])

    def test_motivo_inventado_tambem_e_recusado(self):
        r = self.cliente.post("/estado/1%2F2026/descartado",
                              data={"motivo": "porque sim"})
        self.assertIn("aviso=", r.headers["Location"])

    def test_o_botao_nao_pergunta_nada_na_linha(self):
        # Decisão do Afonso a 01/09/2026: o motivo é pop-up e não um
        # selector ao lado do botão -- vinte linhas na lista eram vinte
        # perguntas antes de alguém as fazer.
        html_ = radar.forma_abandonar("1/2026", titulo="Um anúncio")
        self.assertNotIn("<select", html_)
        self.assertNotIn("<option", html_)
        self.assertIn("abandonar-js", html_)
        self.assertIn("action='/estado/1/2026/nao_fomos'", html_)
        self.assertIn("Um anúncio", html_)

    def test_sem_JS_o_pedido_segue_e_o_servidor_e_que_recusa(self):
        # o botão continua a ser submit de um <form> que faz POST: sem
        # JS o pedido segue e a recusa explica-se, em vez de o botão
        # ficar morto
        html_ = radar.forma_abandonar("1/2026")
        self.assertIn("<form", html_)
        self.assertIn("method='post'", html_)
        self.assertIn("type='submit'", html_)

    def test_a_caixa_traz_os_motivos_todos_e_nenhum_por_omissao(self):
        html_ = radar.caixa_do_motivo()
        for m in radar.MOTIVOS_ABANDONO:
            # escapado, que e como chega ao browser: "CV's" leva
            # apostrofo e o atributo e delimitado por ele
            self.assertIn(html.escape(m), html_)
        # nenhum vem escolhido e o campo é required: não se abandona a
        # carregar duas vezes sem olhar. Só a marcação -- o `checked` do
        # JS é o que LIMPA a escolha anterior, e um `assertNotIn` sobre
        # o texto todo apanhava-o e acusava o contrário do que se quer.
        marcacao = html_.split("<script")[0]
        self.assertNotIn("checked", marcacao)
        self.assertIn("<dialog", marcacao)
        # o `required` passou a ser posto pelo JS, e nao na marcação
        # (15/09/2026): a caixa serve os DOIS estados com motivo, e um
        # grupo escondido com radios `required` travava a submissão do
        # grupo visível sem nada no ecrã a dizer porquê. Quem recusa sem
        # motivo continua a ser o servidor -- e isso tem teste próprio
        # em TestSelectorDaRanhura.
        self.assertIn("r.required = meu", html_)
        self.assertIn("data-para='perdido'", marcacao)
        self.assertIn("data-para='nao_fomos'", marcacao)

    def test_interessa_continua_a_nao_pedir_motivo(self):
        # a exigência é só de quem abandona
        self.assertNotIn("motivo", radar.accao("/estado/1/interessa", "x"))


class TestContrasteNosFundosReais(unittest.TestCase):
    """`--papel` não é o pior fundo.

    A regra da empresa dizia que os --t* passavam AA sobre --papel, "que é
    o pior fundo". As colunas do quadro são --linha2, mais escuro, e os
    três «pede o preço proposto» de 01/09/2026 estavam a 4,35:1 (medido
    na UX-Auditoria.md de 02/09/2026). O teste calcula os contrastes a
    partir do próprio CSS, para a próxima cor nova não passar sem ser
    medida.
    """

    def _cores(self):
        return dict(re.findall(r"(--[a-z0-9-]+):(#[0-9a-fA-F]{6})", radar.CSS))

    @staticmethod
    def _contraste(a, b):
        def lum(h):
            r, g, b_ = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
            f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
            return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b_)
        la, lb = lum(a), lum(b)
        return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)

    def _regra(self, selector):
        m = re.search(re.escape(selector) + r"\{([^}]*)\}", radar.CSS)
        self.assertIsNotNone(m, selector)
        return m.group(1)

    def test_o_pede_da_coluna_saiu_com_a_coluna(self):
        """A coluna do quadro saiu a 15/09/2026, e o `.coluna-pede` com
        ela. O que a regra guardava -- um texto de 10,5 px tem de passar
        AA sobre o fundo em que vive -- continua nas outras regras desta
        classe."""
        self.assertNotIn(".coluna-pede", radar.CSS)

    def _morto_o_pede_da_coluna(self):
        cores = self._cores()
        token = re.search(r"color:var\((--t\d)\)", self._regra(".coluna-pede")).group(1)
        fundo = re.search(r"background:var\((--[a-z0-9]+)\)", self._regra(".coluna")).group(1)
        self.assertGreaterEqual(self._contraste(cores[token], cores[fundo]), 4.5)

    def test_t1_a_t4_passam_sobre_todos_os_fundos_claros(self):
        cores = self._cores()
        for token in ("--t1", "--t2", "--t3", "--t4"):
            for fundo in ("--papel", "--linha2", "--creme"):
                self.assertGreaterEqual(
                    self._contraste(cores[token], cores[fundo]), 4.5,
                    "%s sobre %s" % (token, fundo))

    def test_t5_e_t6_so_servem_sobre_branco_e_creme(self):
        # e por isso que nao podem ir para a coluna do quadro nem para
        # o papel: a regra do CLAUDE.md diz onde cada escala pode escrever
        cores = self._cores()
        for token in ("--t5", "--t6"):
            self.assertGreaterEqual(self._contraste(cores[token], "#ffffff"), 4.5)
            self.assertGreaterEqual(self._contraste(cores[token], cores["--creme"]), 4.5)
            self.assertLess(self._contraste(cores[token], cores["--linha2"]), 4.5)


class TestAlvosDeTextoA24px(unittest.TestCase):
    """A área de clique era o próprio texto de 11 px.

    «voltar a por ver» 85×11, «no calendário» 75×11, «Pôr por ver»
    63×12, «Ver no DR» 57×12, «mudar» 34×13 (UX-Auditoria.md,
    02/09/2026). O padrão era o mesmo em todos: background:none,
    border:0, padding:0. A regra da cor mediu-se a 31/08; a área nunca.
    O mínimo é 24 px (WCAG 2.5.8); a letra fica como está.
    """

    # 15/09/2026: os alvos do cartão do quadro saíram com ele, e
    # entraram os do selector de ranhura e os da lista de tarefas --
    # que são os controlos novos que se carregam vinte vezes seguidas.
    ALVOS = ("button.tirar", ".ranhura select", "button.tq", ".bt-leve",
             ".sou button", "button.etq-x", ".alerta .apagar")

    def test_cada_alvo_de_texto_tem_24px_de_altura(self):
        for selector in self.ALVOS:
            m = re.search(re.escape(selector) + r"\{([^}]*)\}", radar.CSS)
            self.assertIsNotNone(m, selector)
            self.assertIn("min-height:24px", m.group(1), selector)
            self.assertIn("box-sizing:border-box", m.group(1), selector)


class TestPaginaSemNadaDeFora(unittest.TestCase):
    """A folha do Google Fonts era um <link rel=stylesheet> normal, que
    bloqueia a pintura até chegar ou falhar: 12,6 s de página branca
    neste ambiente sem saída para o domínio, com o servidor a responder
    em 16 ms. Primeiro passou a carregar sem bloquear; a 14/09/2026
    saiu de vez (auditoria ponytail): o painel não pede nada a nenhum
    domínio de fora, e o CSP diz o mesmo.
    """

    def test_o_esqueleto_nao_liga_a_dominio_nenhum(self):
        self.assertNotIn("https://", radar.BASE.split("<body>")[0])
        self.assertNotIn("fonts.googleapis", radar.CSS)

    def test_o_csp_nao_abre_excepcao_para_fora(self):
        csp = radar.CABECALHOS_DE_SEGURANCA["Content-Security-Policy"]
        self.assertNotIn("https://", csp)
        self.assertIn("font-src 'self'", csp)


class TestPeleNova(unittest.TestCase):
    """A camada de aspecto de 16/09/2026 (`docs/design.md`).

    Três coisas, e cada uma tem uma avaria por trás:

    - **O contraste mede-se sobre TODOS os fundos.** A escala antiga
      tinha dois patamares e isso já partiu duas vezes: as seis falhas
      entre 4,1 e 4,43 de 31/08, e os `.coluna-pede` a 4,35 de 02/09,
      que passaram porque só se tinha medido sobre `--papel`. A escala
      nova tem um patamar só -- tudo passa AA sobre tudo --, e é isso
      que este teste fixa. Um `--t*` novo que não chegue lá falha aqui.
    - **As fontes são servidas da aplicação e de mais lado nenhum.** A
      regra é que o painel não pede nada a nenhum domínio de fora, e o
      CSP diz `font-src 'self'`.
    - **`/tipo/<nome>` é uma lista branca.** Serve ficheiros do disco a
      quem ainda não fez login (a página de entrar precisa da letra),
      e por isso o que lá entra tem de ser exactamente um dos quatro
      nomes.
    """

    _contraste = staticmethod(TestContrasteNosFundosReais._contraste)

    def _cores(self):
        """Os tokens do bloco [data-pele=novo], que são os que contam --
        o CSS antigo continua a declarar os seus, e apanhar os dois
        misturava duas paletas."""
        m = re.search(r"\[data-pele=novo\]\{(.*?)\}", radar.CSS_NOVO, re.S)
        self.assertIsNotNone(m, "o bloco [data-pele=novo] desapareceu")
        return dict(re.findall(r"(--[a-z0-9-]+):\s*(#[0-9a-fA-F]{6})",
                               m.group(1)))

    # todos os fundos que existem: os três níveis de superfície e os
    # quatro fundos de nota. É a lista que faltava em agosto e setembro.
    FUNDOS = ("--fundo", "--sup", "--sup2", "--azul-fundo", "--verde-fundo",
              "--laranja-fundo", "--verm-fundo")
    TINTAS = ("--t1", "--t2", "--t3", "--t4", "--t5",
              "--azul", "--verde", "--verm", "--laranja")

    def test_toda_a_escala_passa_aa_sobre_todos_os_fundos(self):
        cores = self._cores()
        for token in self.TINTAS:
            for fundo in self.FUNDOS:
                c = self._contraste(cores[token], cores[fundo])
                self.assertGreaterEqual(
                    c, 4.5, "%s sobre %s dá %.2f" % (token, fundo, c))

    def test_a_escala_de_texto_tem_um_patamar_so(self):
        """O `--t6` aponta para o mesmo valor do `--t5`: um sexto
        cinzento que só funciona em metade dos fundos é uma armadilha,
        não um degrau, e foi o que partiu as `.coluna-pede`."""
        cores = self._cores()
        self.assertEqual(cores["--t6"], cores["--t5"])

    def test_tudo_o_que_pinta_esta_dentro_do_ambito(self):
        """Uma regra do CSS_NOVO fora de [data-pele=novo] / [data-tipo=*]
        pinta mesmo com os atributos tirados do <html>, e isso tira o
        caminho de volta: a fase 1 tem de se desfazer apagando dois
        atributos, e mais nada."""
        for regra in re.findall(r"^([^@\s/][^{]*)\{", radar.CSS_NOVO, re.M):
            self.assertTrue(
                "[data-pele=novo]" in regra or "[data-tipo=" in regra,
                "regra fora do âmbito da pele: %r" % regra.strip())

    def test_os_tres_moldes_carimbam_a_pele_e_a_letra(self):
        """Fase 1 (16/09/2026). São três e não um: a página de entrar e
        as de erro vivem fora do BASE de propósito -- o BASE lê a sessão
        e monta a barra, e um 500 a meio disso dava outro 500 em cima do
        primeiro. Carimbar só o BASE deixava o login e os erros com o
        aspecto antigo, que é o género de coisa que ninguém vê até ao
        dia em que vê."""
        for molde in (radar.BASE, radar.PAGINA_ERRO, radar.PAGINA_ENTRAR):
            self.assertIn('data-pele="novo"', molde)
            self.assertIn('data-tipo="plex"', molde)
            # e a folha que carimbam tem de ser a que traz a pele
            self.assertIn("%(css)s", molde)
        # A ORDEM é o que importa, e não por onde começa: o que é nosso
        # vem depois do que é de terceiros (para nos podermos sobrepor às
        # curvas do Open Props), e a pele vem por último de todas (para
        # ganhar ao CSS de base). A 17/09/2026 isto pregava
        # `startswith(CSS)` e passou a falhar quando os `estilo/*.css`
        # entraram à frente — que é exactamente onde têm de estar.
        self.assertTrue(radar.CSS_TUDO.endswith(radar.CSS_NOVO))
        self.assertIn(radar.CSS, radar.CSS_TUDO)
        self.assertLess(radar.CSS_TUDO.index(radar.CSS),
                        radar.CSS_TUDO.index(radar.CSS_NOVO))

    def test_as_fontes_vem_da_propria_aplicacao(self):
        self.assertNotIn("https://", radar.CSS_NOVO)
        for nome in radar.TIPOS:
            self.assertIn("/tipo/" + nome, radar.CSS_NOVO)

    def test_tipo_serve_a_lista_branca_e_recusa_o_resto(self):
        cliente = radar.app.test_client()
        for nome in radar.TIPOS:
            r = cliente.get("/tipo/" + nome)
            self.assertEqual(r.status_code, 200, nome)
            self.assertEqual(r.headers["Content-Type"], "font/woff2")
            r.close()   # o send_file deixa o ficheiro aberto senão
        for fora in ("radar.py", "..%2Fradar.py", "config.json",
                     "inter.woff2.bak", "inter.WOFF2"):
            self.assertEqual(cliente.get("/tipo/" + fora).status_code, 404,
                             fora)

    def test_a_amostra_desenha_se(self):
        cliente = radar.app.test_client()
        for pedido in ("/amostra", "/amostra?tipo=plex",
                       "/amostra?tipo=sistema&pele=velho",
                       "/amostra?tipo=inventado"):
            r = cliente.get(pedido)
            self.assertEqual(r.status_code, 200, pedido)
            corpo = r.get_data(as_text=True)
            self.assertIn("Amostra do desenho", corpo)
            self.assertNotIn("https://", corpo)
        # o `tipo` inventado cai no de omissão em vez de ir para o HTML
        self.assertIn('data-tipo="plex"',
                      cliente.get("/amostra?tipo=inventado").get_data(
                          as_text=True))

    def test_o_mini_deixou_de_ficar_vermelho_em_tudo(self):
        """O `.mini` é o botão DA LINHA, e ficava vermelho ao passar por
        cima -- em todos: no «ir» do selector, no «desfazer», no «X
        lotes». A cor de alarme a sair em coisas que não alarmam nada é
        o ponto (c) do diagnóstico, e faz o vermelho não querer dizer
        nada onde devia."""
        m = re.search(r"\[data-pele=novo\] \.mini:hover\{([^}]*)\}",
                      radar.CSS_NOVO)
        self.assertIsNotNone(m, "o .mini:hover da pele nova desapareceu")
        self.assertNotIn("--verm", m.group(1))

    def test_quem_apaga_uma_conta_leva_a_classe_do_perigo(self):
        """Estava em `.mini` simples e **só parecia certo** porque o
        `.mini` ficava vermelho ao passar -- em tudo. Tirado esse
        vermelho sem querer, o botão que apaga uma conta ficava igual ao
        «desfazer». O que o marca agora é a classe, não um acidente."""
        self.assertIn('"tirar", "mini perigo"',
                      inspect.getsource(radar._bloco_utilizadores))

    def test_abandonar_e_laranja_e_nao_vermelho(self):
        """Abandonar **não apaga nada** -- a própria aplicação o diz no
        pop-up do motivo, e repõe-se numa linha. Pintar de vermelho uma
        coisa reversível gasta o vermelho, e depois não sobra cor para o
        que apaga mesmo (design.md §5)."""
        # o botao da linha, pela omissao do forma_abandonar()
        self.assertIn('classe="mini cuidado"',
                      inspect.getsource(radar.forma_abandonar))
        # e o botao grande da ficha, que passa a classe a mao
        self.assertIn('"bt cuidado"', inspect.getsource(radar.ficha))

    def test_os_cinco_botoes_existem_e_os_perigosos_comecam_em_contorno(self):
        """A regra do design.md §5: um botão vermelho cheio numa lista de
        vinte linhas é um alvo. Os dois que saem do fluxo começam em
        contorno sobre a superfície e só se enchem ao passar ou ao
        receber o foco."""
        for classe in (".bt.forte", ".bt.ok", ".bt.cuidado", ".bt.perigo"):
            self.assertIn("[data-pele=novo] " + classe, radar.CSS_NOVO, classe)
        for classe in ("cuidado", "perigo"):
            repouso = re.search(
                r"\[data-pele=novo\] \.bt\.%s\{([^}]*)\}" % classe,
                radar.CSS_NOVO).group(1)
            self.assertIn("background:var(--sup)", repouso, classe)
            self.assertIn(
                "[data-pele=novo] .bt.%s:hover,"
                "[data-pele=novo] .bt.%s:focus-visible" % (classe, classe),
                radar.CSS_NOVO.replace("\n", ""), classe)


class TestTriarAvisaEDeixaDesfazer(BaseTemporaria):
    """Marcar «interessa» ou «abandonar» fazia o POST e o cartão
    desaparecia da aba sem uma palavra.

    Medido na UX-Auditoria.md (02/09/2026): zero avisos depois das duas
    acções, e o caminho de volta era ir à outra aba procurar o anúncio.
    Enganar-se no cartão de baixo em vez do de cima é o erro mais fácil
    numa lista de vinte com dois botões por linha.
    """

    def setUp(self):
        super().setUp()
        self.cliente = radar.app.test_client()
        # marcar interessa poe as pecas na fila, e a fila e uma thread
        # que vai a rede e abre a base -- a base do teste SEGUINTE, que
        # aparecia "locked" sem razao visivel. Aqui nao ha pecas.
        self.enterContext(unittest.mock.patch.object(
            radar, "pedir_documentos", lambda ref: None))
        with radar.liga() as c:
            c.execute("INSERT INTO anuncios (ref, titulo, entidade, data_pub, tipo,"
                      " url, estado) VALUES (?,?,?,?,?,?,?)",
                      ("2/2026", "Aquisição de serviços de consultoria",
                       "IFAP", "2026-08-01", "Anúncio de procedimento",
                       "https://dr/2", "novo"))

    def _params(self, r):
        return dict(parse_qsl(urlparse(r.headers["Location"]).query))

    def test_por_na_escada_avisa_e_oferece_desfazer(self):
        r = self.cliente.post(
            "/estado/2/2026/interessa",      # o nome antigo ainda serve
            headers={"Referer": "http://localhost:8765/?estado=porver"})
        self.assertEqual(r.status_code, 302)
        p = self._params(r)
        self.assertIn("Por analisar", p["aviso"])
        self.assertIn("Aquisição de serviços de consultoria", p["aviso"])
        self.assertEqual(p["desfazer"], "/estado/2/2026/porver")
        self.assertEqual(p["estado"], "porver")     # o filtro da pagina fica

    def test_nao_fomos_avisa_com_o_motivo_e_o_desfazer_repoe(self):
        r = self.cliente.post("/estado/2/2026/nao_fomos",
                              data={"motivo": radar.MOTIVOS_ABANDONO[0]})
        p = self._params(r)
        self.assertIn("Não fomos (%s)" % radar.MOTIVOS_ABANDONO[0], p["aviso"])
        self.assertEqual(p["desfazer"], "/estado/2/2026/porver")
        r = self.cliente.post(p["desfazer"])
        self.assertIn("reposto em por ver", self._params(r)["aviso"])
        # sair da escada tira a proposta, e o anuncio fica como o DR o
        # deixou -- a decisao da empresa nao mora no anuncio desde 15/09/2026
        self.assertEqual(radar.propostas_de("2/2026"), [])
        with radar.liga() as c:
            a = c.execute("SELECT estado FROM anuncios WHERE ref='2/2026'").fetchone()
        self.assertEqual(a["estado"], "novo")

    def test_o_desfazer_de_um_nao_fomos_leva_o_motivo(self):
        # sem o motivo na accao, o servidor recusava a reposicao
        self.cliente.post("/estado/2/2026/nao_fomos",
                          data={"motivo": radar.MOTIVOS_ABANDONO[1]})
        r = self.cliente.post("/estado/2/2026/analisar")
        p = self._params(r)
        self.assertTrue(p["desfazer"].startswith("/estado/2/2026/nao_fomos?motivo="))
        r = self.cliente.post(p["desfazer"])
        self.assertEqual(r.status_code, 302)
        viva = radar.propostas_de("2/2026")[0]
        self.assertEqual((viva["estado"], viva["motivo"]),
                         ("nao_fomos", radar.MOTIVOS_ABANDONO[1]))

    def test_repetir_o_mesmo_estado_avisa_mas_nao_oferece_desfazer(self):
        self.cliente.post("/estado/2/2026/analisar")
        p = self._params(self.cliente.post("/estado/2/2026/analisar"))
        self.assertIn("Por analisar", p["aviso"])
        self.assertNotIn("desfazer", p)

    def test_repor_nao_deita_fora_trabalho_escrito(self):
        """15/09/2026, etapa 2: «voltar ao por ver» apaga a proposta — e
        apagar uma com preço proposto ou notas lá dentro era perder
        trabalho com um clique, sem confirmação e sem desfazer. Essa
        volta a «Por analisar», e o aviso diz porquê: sem uma palavra, o
        gesto parecia não ter funcionado."""
        self.cliente.post("/estado/2/2026/submetido",
                          data={"valor_proposta": "1.000,00 EUR"})
        id_ = radar.propostas_de("2/2026")[0]["id"]
        radar.gravar_campos_da_proposta(id_, ["valor_proposta"],
                                        ["118.500,00 EUR"])
        p = self._params(self.cliente.post("/estado/2/2026/porver"))
        self.assertIn("não se deita fora", p["aviso"])
        viva = radar.propostas_de("2/2026")
        self.assertEqual(len(viva), 1)
        self.assertEqual(viva[0]["estado"], "analisar")
        self.assertEqual(viva[0]["valor_proposta"], "118.500,00 EUR")

    def test_o_motivo_nao_sobrevive_a_mudanca_de_ranhura(self):
        """A prova de fumo da etapa 2 apanhou isto: reabrir um «Não
        fomos» em «Submetido» deixava lá o «Preço base baixo» pendurado.
        Um motivo numa proposta que mudou de ranhura é uma mentira à
        espera de ser lida — a mesma regra que já valia para o abandono
        do anúncio, agora no sítio que sabe que o estado mudou."""
        self.cliente.post("/estado/2/2026/nao_fomos",
                          data={"motivo": radar.MOTIVOS_ABANDONO[0]})
        self.cliente.post("/estado/2/2026/submetido",
                          data={"valor_proposta": "1.000,00 EUR"})
        self.assertIsNone(radar.propostas_de("2/2026")[0]["motivo"])

class TestARanhuraDizOQuePede(unittest.TestCase):
    """O campo só aparece quando há um cartão lá dentro.

    Com o quadro todo em "Por analisar" -- que é o caso normal -- não
    havia nada no ecrã a dizer que o "Submetido" pede o preço proposto,
    e a funcionalidade parecia não existir. Foi o que o Afonso viu.

    (Era TestAColunaDizOQuePede, sobre `fases.papel`. As fases saíram a
    15/09/2026 -- o vocabulário passou a ser as oito palavras escritas no
    código --, e o acordo que esta classe guarda vale na mesma: quem pede
    no cartão e quem o diz no cabeçalho têm de ser a mesma lista.)
    """

    def test_so_os_dois_estados_com_motivo_tem_rotulo(self):
        """O `PEDIDO_DO_ESTADO` era a lista do que cada coluna do quadro
        anunciava no cabeçalho. Com o quadro fora (15/09/2026) não há
        cabeçalho nenhum, e o que resta é o rótulo do campo do motivo --
        que só os dois estados com motivo têm. Um rótulo que ninguém
        mostra é uma promessa que se esquece de cumprir."""
        self.assertEqual(sorted(radar.PEDIDO_DO_ESTADO),
                         sorted(radar.MOTIVOS_DO_ESTADO))
        for estado, rotulo in radar.PEDIDO_DO_ESTADO.items():
            self.assertIn(estado, radar.CHAVES_DA_EMPRESA, estado)
            self.assertTrue(rotulo.strip(), estado)

    def test_o_rotulo_aparece_mesmo_no_campo(self):
        for estado, rotulo in radar.PEDIDO_DO_ESTADO.items():
            p = {"id": 1, "ref": "1/2026", "estado": estado,
                 "valor_proposta": None, "lugar": None, "top3": None,
                 "motivo": None}
            self.assertIn(html.escape(rotulo),
                          radar._campos_que_a_ranhura_pede(p), estado)


class TestAsOitoPalavrasSaoDoCodigo(unittest.TestCase):
    """15/09/2026: a tabela `fases` saiu, e com ela o renomear.

    Aqui viviam quatro classes -- TestPapeisDasFases, TestAtribuirPapeis,
    TestSemeadoraDeFases e TestFasesNaoSeCriamNemSeApagam -- sobre uma
    tabela de fases renomeáveis, os papéis que lhes davam significado e o
    semeador que as punha numa base por estrear. Guardavam um erro real:
    o cartão mudava com o NOME da coluna, e renomeá-la calava o campo que
    ela pedia.

    A decisão D1 mata esse erro na origem, e é isso que estes testes
    passam a guardar: as oito palavras são vocabulário do código, o nome
    não manda em nada, e não há forma de os renomear. O que ficou para
    trás está no histórico do git.
    """

    def test_nao_ha_rotas_de_fases(self):
        rotas = [r.rule for r in radar.app.url_map.iter_rules()]
        for morta in ("/quadro/fase/nova", "/quadro/fase/9/apagar"):
            self.assertNotIn(morta, rotas)
        self.assertFalse([r for r in rotas if "/fase/" in r],
                         "sobrou uma rota de fases")

    def test_renomear_saiu_com_elas(self):
        """Renomear uma coluna fazia o quadro dizer uma palavra e as abas
        outra, para o mesmo estado -- não havia como isso ficar certo com
        uma escada só."""
        pontos = [r.endpoint for r in radar.app.url_map.iter_rules()]
        self.assertNotIn("fase_renomear", pontos)
        # o JS do quadro saiu com ele a 15/09/2026
        self.assertNotIn("QUADRO_JS", radar_fonte())
        self.assertNotIn("renomearFase", radar_fonte())

    def test_a_tabela_das_fases_nao_se_cria(self):
        self.assertNotIn("CREATE TABLE IF NOT EXISTS fases", radar_fonte())

    def test_o_vocabulario_nao_se_edita_por_dados(self):
        """As oito vêm de uma constante, e é isso que faz o quadro, as
        abas, o calendário e os indicadores falarem a mesma língua."""
        self.assertIsInstance(radar.ESTADOS_DA_EMPRESA, tuple)
        self.assertEqual(len(radar.ESTADOS_DA_EMPRESA), 8)


class TestCamposPorRanhura(BaseTemporaria):
    """Cada ranhura pede o que lhe falta, e só ela.

    "Por analisar" e "A preparar proposta" não têm nada a apontar
    (palavras do Afonso); o "Submetido" pede o preço proposto, o
    relatório preliminar o lugar e os três primeiros, e o "Perdido" e o
    "Não fomos" o porquê, de âmbito fechado.

    (15/09/2026, segunda arrumação do dia: o quadro saiu e estes campos
    mudaram de empresa — do cartão para o bloco «A nossa proposta» da
    ficha. O âmbito é o mesmo, e é isso que aqui se mede.)
    """

    def _p(self, estado, **k):
        base = {"id": 7, "ref": "1/2026", "estado": estado,
                "valor_proposta": None, "lugar": None, "top3": None,
                "motivo": None}
        base.update(k)
        return base

    def test_ranhuras_sem_nada_a_apontar_nao_mostram_campos(self):
        for estado in ("analisar", "proposta"):
            self.assertEqual(
                radar._campos_que_a_ranhura_pede(self._p(estado)), "", estado)

    def test_submetido_pede_o_preco_proposto(self):
        html_ = radar._campos_que_a_ranhura_pede(self._p("submetido"))
        self.assertIn("name='valor_proposta'", html_)
        self.assertNotIn("name='motivo'", html_)

    def test_relatorio_pede_lugar_e_os_tres_primeiros(self):
        html_ = radar._campos_que_a_ranhura_pede(
            self._p("relatorio", lugar=2, top3="A · B · C"))
        self.assertIn("name='lugar'", html_)
        self.assertIn("value='2'", html_)
        self.assertIn("A · B · C", html_)

    def test_perdido_e_nao_fomos_tem_ambito_fechado_e_cada_um_o_seu(self):
        """As duas listas não são a mesma: «Preço base baixo» é porque
        não se foi, e não é resposta a «porque se perdeu»."""
        perdido = radar._campos_que_a_ranhura_pede(
            self._p("perdido", motivo="Preço"))
        for m in radar.MOTIVOS_PERDA:
            self.assertIn(html.escape(m), perdido)
        self.assertIn("selected", perdido)     # o que lá está vem escolhido
        nao_fomos = radar._campos_que_a_ranhura_pede(self._p("nao_fomos"))
        for m in radar.MOTIVOS_ABANDONO:
            self.assertIn(html.escape(m), nao_fomos)
        self.assertNotIn("Preço base baixo", perdido)
        self.assertNotIn("Proposta técnica", nao_fomos)

    def test_o_ganho_ainda_pergunta_o_lugar(self):
        """Ganhar é ficar em primeiro, mas o lugar e os três primeiros
        são o que se sabe da concorrência — e é disso que a etapa 4 vive.
        Perdê-los ao mover para «Ganho» era deitar fora o que custou a
        saber."""
        html_ = radar._campos_que_a_ranhura_pede(self._p("ganho", lugar=1))
        self.assertIn("name='lugar'", html_)
        self.assertIn("name='top3'", html_)


class TestSelectorDaRanhura(BaseTemporaria):
    """O quadro saiu a 15/09/2026 e a escada passou a mudar-se na linha.

    Palavra dele: «o quadro deixa de ser preciso tal como a lista. na
    verdade eu devo conseguir passar entre estados aqui». Oito colunas e
    oito abas eram a mesma coisa duas vezes, e a diferença era o
    arrastar — que só compensa quando se vê tudo ao mesmo tempo.

    O que esta classe guarda, e que o arrasto guardava antes: mudar de
    ranhura a partir da lista tem de funcionar, tem de exigir o motivo
    onde ele é devido, e tem de funcionar **sem JavaScript** — o que
    degrada mal é um controlo que não faz nada com o JS desligado.
    """

    def setUp(self):
        super().setUp()
        self.cliente = radar.app.test_client()
        self.enterContext(unittest.mock.patch.object(
            radar, "pedir_documentos", lambda ref: None))
        with radar.liga() as c:
            c.execute("INSERT INTO anuncios (ref, titulo, entidade, data_pub,"
                      " tipo, url, estado) VALUES (?,?,?,?,?,?,'novo')",
                      ("60/2026", "Aquisição de software", "IPL",
                       "2026-09-01", "Anúncio de procedimento", "https://dr/60"))

    def test_o_selector_aparece_para_quem_ja_esta_na_escada(self):
        """Por decidir são os dois botões; na escada é o selector."""
        # no CORPO da lista e não na página: o JS da caixa do motivo
        # fala do `escada-js` para lhe apanhar o `change`, e está em
        # todas as páginas que tenham a caixa
        def corpo(url):
            """A página SEM os <script>: o JS da caixa do motivo fala do
            `escada-js` para lhe apanhar o `change`, e está em todas as
            páginas que tenham a caixa."""
            h = self.cliente.get(url).get_data(as_text=True)
            return re.sub(r"(?s)<script.*?</script>", "", h)

        self.assertNotIn("escada-js", corpo(radar.LISTA))
        self.cliente.post("/estado/60%2F2026/analisar")
        # na lista dos ANÚNCIOS (a aba «Todos») o selector aponta ao ref
        self.assertIn("action='/escada/60%2F2026'",
                      corpo(radar.LISTA + "?estado="))
        # na das PROPOSTAS aponta à proposta, que é mais preciso: com
        # lotes há uma por lote, e mover «a do ref» movia a primeira
        html_ = self.cliente.get(radar.LISTA + "?estado=analisar").get_data(as_text=True)
        id_ = radar.propostas_de("60/2026")[0]["id"]
        self.assertIn("action='/proposta/%d/escada'" % id_, html_)
        for _, rotulo in radar.ESTADOS_DA_EMPRESA:
            self.assertIn(">%s</option>" % html.escape(rotulo), html_)
        self.assertIn("<option value='porver'>tirar da escada</option>", html_)

    def test_muda_de_ranhura_pelo_corpo_e_nao_pelo_caminho(self):
        """Um `<select>` não sabe escrever um URL. Se o estado fosse no
        caminho, o selector precisava de JS para funcionar de todo."""
        r = self.cliente.post("/escada/60%2F2026",
                              data={"estado": "submetido",
                                    "valor_proposta": "1.000,00 EUR"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(radar.propostas_de("60/2026")[0]["estado"], "submetido")

    def test_sem_motivo_a_ranhura_que_o_pede_recusa_e_diz_porque(self):
        r = self.cliente.post("/escada/60%2F2026", data={"estado": "perdido"})
        self.assertIn("aviso", r.headers["Location"])
        self.assertEqual(radar.propostas_de("60/2026"), [])

    def test_com_motivo_grava_os_dois(self):
        self.cliente.post("/escada/60%2F2026",
                          data={"estado": "perdido", "motivo": "Preço",
                                "valor_proposta": "1.000,00 EUR"})
        p = radar.propostas_de("60/2026")[0]
        self.assertEqual((p["estado"], p["motivo"]), ("perdido", "Preço"))

    def test_o_botao_ir_existe_para_quem_nao_tem_javascript(self):
        """O JS marca o <html> com `com-js` e a folha esconde o botão. Ao
        contrário — esconder por omissão e mostrar por JS — quem não
        tivesse JS ficava com um selector que não fazia nada."""
        self.cliente.post("/estado/60%2F2026/analisar")
        html_ = self.cliente.get(radar.LISTA + "?estado=analisar").get_data(as_text=True)
        self.assertIn("<button type='submit' class='mini'>ir</button>", html_)
        self.assertIn(".com-js .ranhura button{display:none}", radar.CSS)
        self.assertIn("classList.add('com-js')", radar.caixa_do_motivo())

    def test_uma_proposta_sem_anuncio_move_se_pelo_id(self):
        """Essas não têm `ref` por onde lhes pegar (D2)."""
        id_ = radar.criar_proposta(entidade="IPL", titulo="Consulta prévia")
        r = self.cliente.post("/proposta/%d/escada" % id_,
                              data={"estado": "submetido",
                                    "valor_proposta": "9.000,00 EUR"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(radar.proposta(id_)["estado"], "submetido")

    def test_o_quadro_deixou_de_existir(self):
        rotas = [r.rule for r in radar.app.url_map.iter_rules()]
        self.assertFalse([r for r in rotas if r.startswith("/quadro")], rotas)
        self.assertEqual(self.cliente.get("/quadro").status_code, 404)
        self.assertNotIn("quadro", [v[0] for n in radar.NAV for v in n[3]])


class TestPrecoDaProposta(unittest.TestCase):
    """A partir do "Submetido" o número que conta é o proposto.

    E enquanto o proposto não estiver preenchido mostra-se o base
    **dito como base**: mostrá-lo calado é dar o tecto da entidade por
    proposta nossa. A regra vivia no cartão do quadro; com ele fora,
    vive na linha da lista das propostas.
    """

    @staticmethod
    def _p(estado="analisar", **k):
        base = {"id": 3, "ref": "1/2026", "titulo": "T", "entidade": "E",
                "lote": None, "estado": estado, "motivo": None,
                "porque_sem_ref": None,
                "preco_base": "175.000,00 EUR", "valor_proposta": None,
                "lugar": None, "top3": None, "responsavel": ""}
        base.update(k)
        return base

    def _linha(self, p):
        with radar.app.test_request_context("/"):
            return radar.linha_da_pipeline(p, 10, {})

    def test_antes_do_submetido_o_proposto_esta_vazio(self):
        html_ = self._linha(self._p("analisar"))
        self.assertIn("175.000,00 EUR", html_)     # o base, na coluna dele

    def test_no_submetido_com_proposto_mostra_o_proposto(self):
        html_ = self._linha(
            self._p("submetido", valor_proposta="118.500,00 EUR"))
        self.assertIn("118.500,00 EUR", html_)

    def test_o_proposto_guarda_se_no_formato_que_se_sabe_ler(self):
        # euros() põe espaço nos milhares e euros_do_texto() lê "118" de
        # "118 500 €": a soma dava 118 em vez de 118 500
        texto = radar._texto_do_preco(radar.euros_do_texto("118500"))
        self.assertEqual(texto, "118.500,00 EUR")
        self.assertEqual(radar.euros_do_texto(texto), 118500.0)


class TestPrazoNeutroDepoisDeSubmetido(unittest.TestCase):
    """O quadro pintava «prazo expirado» a vermelho em 4 dos 9 cartões,
    todos em fases pós-submissão, onde o prazo ter passado é o estado
    normal (UX-Auditoria.md, 02/09/2026). O vermelho é a cor de alarme
    da lista e puxava o olho para uma coisa que não pede acção nenhuma.

    O cartão saiu com o quadro; a regra ficou, na lista das propostas.
    """

    def _linha(self, estado, prazo="2026-08-03"):
        p = {"id": 9, "ref": "9/2026", "titulo": "T", "entidade": "E",
             "lote": None, "estado": estado, "motivo": None,
             "porque_sem_ref": None, "preco_base": "175.000,00 EUR",
             "valor_proposta": "", "lugar": None, "top3": "",
             "responsavel": ""}
        with radar.app.test_request_context("/"):
            return radar.linha_da_pipeline(p, 8, {"9/2026": prazo})

    def test_antes_do_submetido_o_prazo_e_alarme(self):
        for estado in ("analisar", "proposta"):
            self.assertIn("prazo expirado", self._linha(estado))
            self.assertIn("tag mau", self._linha(estado))

    def test_a_partir_do_submetido_diz_entregue_e_nao_alarme(self):
        for estado in radar.ESTADOS_COM_PROPOSTO:
            linha = self._linha(estado)
            self.assertNotIn("prazo expirado", linha)
            self.assertNotIn("tag mau", linha)
            self.assertIn("entregue", linha)

    def test_sem_prazo_nao_ha_pilula(self):
        self.assertIn("&mdash;", self._linha("submetido", ""))


class TestCalendarioLigaAEscada(unittest.TestCase):
    """Atalho da §5 do esqueleto: o calendário e a lista são vistas do
    mesmo conjunto, e há sempre por onde passar de uma à outra.

    Apontou para o quadro; com ele fora (15/09/2026) passou a apontar
    para a ranhura em que a proposta está. A 16/09/2026, com o dia a ser
    a unidade da grade, a ligação **subiu de nível**: uma linha passou a
    ser uma linha dentro de uma célula de 119px e não há lá sítio para
    um segundo destino, por isso o par mantém-se na legenda da página —
    e aponta para a ranhura que está a ser vista. Uma ligação para uma
    página que já não existe é pior do que nenhuma; nenhuma ligação é
    pior do que uma que esteja no sítio certo.
    """

    def test_a_volta_do_calendario_e_para_a_ranhura(self):
        fonte = inspect.getsource(radar.calendario)
        self.assertNotIn("/quadro", fonte)
        # o endereço da lista, e não o "/" que passou a ser a abertura:
        # este teste estava a PREGAR a ligação errada no lugar, e foi
        # por isso que as nove partidas passaram 952 testes (16/09/2026)
        self.assertIn('LISTA + "?estado=" + estado', fonte)

    def test_o_calendario_nao_promete_uma_lista_que_nao_abre(self):
        """O «+N» de um dia cheio **não** liga a `/?de=X&ate=X`: esses
        dois filtros são por `data_pub` e não por `prazo`, e a lista que
        abriam não era a que o número prometia. Abre no sítio, com um
        `<details>`."""
        fonte = inspect.getsource(radar.calendario)
        self.assertIn("cal-mais", fonte)
        self.assertNotIn("&ate=", fonte)
        self.assertNotIn("ate=%s", fonte)

    def test_nada_no_painel_liga_ao_quadro(self):
        for pedaco in ("/quadro#", "href='/quadro'", 'href="/quadro"'):
            self.assertNotIn(pedaco, radar_fonte(), pedaco)


class TestColunasSeguemARanhura(BaseTemporaria):
    """A lista das propostas mostrava as **oito colunas nas oito
    ranhuras** (fase 5, 16/09/2026).

    A regra já existia e é do próprio CRM — um campo pertence a um estado
    e a mais nenhum (`_campos_que_a_ranhura_pede()`, que a ficha segue) —
    e a lista não a seguia.

    O caso que importa é o **«Proposto» antes do Submetido**: não está
    vazio por falta de preenchimento, é **impossível**. O
    `ESTADOS_COM_PROPOSTO` diz que o preço proposto só existe a partir do
    Submetido, e o `docs/historico/CRM.md` escreve que «perguntar o preço
    proposto antes de haver proposta é perguntar por adivinhas». Uma
    coluna de travessões que nunca poderá ter nada é uma pergunta sem
    resposta possível, repetida em cada linha.
    """

    def _proposta(self, estado):
        # o mesmo anúncio serve as várias ranhuras, uma de cada vez: o
        # `ref` é único, e sem o OR IGNORE a segunda chamada rebentava
        with radar.liga() as c:
            c.execute("DELETE FROM propostas")
            c.execute("INSERT OR IGNORE INTO anuncios (ref, titulo, entidade,"
                      " estado, data_pub, prazo, preco_base) VALUES "
                      "('60/2026','Soft','CML','novo','2026-09-01',"
                      "'2026-12-01','118.500,00 EUR')")
        return radar.criar_proposta("60/2026", estado=estado)

    def _colunas(self, estado):
        corpo = radar.app.test_client().get(
            radar.LISTA + "?estado=" + estado).get_data(as_text=True)
        cabeca = corpo.split("<thead><tr>")[1].split("</tr>")[0]
        return re.findall(r"<th>([^<]*)</th>", cabeca), corpo

    def test_o_proposto_so_aparece_de_submetido_para_a_frente(self):
        for estado in ("analisar", "proposta"):
            self._proposta(estado)
            colunas, _ = self._colunas(estado)
            self.assertNotIn("Proposto", colunas, estado)
        for estado in radar.ESTADOS_COM_PROPOSTO:
            self._proposta(estado)
            colunas, _ = self._colunas(estado)
            self.assertIn("Proposto", colunas, estado)

    def test_as_celulas_batem_com_os_cabecalhos(self):
        """Uma coluna que sai do cabeçalho e não da linha desalinha a
        tabela toda, e isso não dá erro nenhum — vê-se, e mal."""
        for estado in ("analisar", "submetido"):
            self._proposta(estado)
            colunas, corpo = self._colunas(estado)
            linha = corpo.split("<tbody>")[1].split("</tbody>")[0]
            self.assertEqual(linha.count("<td"), len(colunas),
                             "%s: %d cabeçalhos, %d células"
                             % (estado, len(colunas), linha.count("<td")))

    def test_o_lote_e_o_responsavel_nao_se_escondem(self):
        """Estão vazios por não estarem **preenchidos**, e isso é outra
        coisa: podem ter valor, e esconder a coluna tirava o sítio onde
        se vê que faltam."""
        self._proposta("analisar")
        colunas, _ = self._colunas("analisar")
        self.assertIn("Lote", colunas)
        self.assertIn("Responsável", colunas)


class TestIndiceDaFichaCobreAPagina(BaseTemporaria):
    """O índice da ficha prometia seis destinos e a página tinha oito
    blocos com âncora (fase 5, 16/09/2026).

    Faltavam o **`#proposta`** — que é onde vive o trabalho da empresa, o
    bloco mais importante da ficha — e o `#contactos`. Um índice que
    salta por cima de um bloco é a mesma mentira de um número que abre
    outra lista: promete o mapa da página e não o é.

    O teste não fixa a lista de entradas (essa muda), fixa a
    **propriedade**: toda a âncora que a página tem está no índice.
    """

    # os blocos que o índice tem de cobrir quando existem na página
    BLOCOS = ("proposta", "lotes", "pecas", "mercado", "contactos",
              "historico", "desfecho")

    def _ficha(self):
        with radar.liga() as c:
            # o `texto` tem de vir preenchido: sem ele a ficha vai à
            # rede buscar o detalhe, e os testes correm sem rede
            c.execute("INSERT INTO anuncios (ref, titulo, entidade, estado, "
                      "data_pub, prazo, preco_base, cpv, texto) VALUES "
                      "('60/2026','Software','CML','novo','2026-09-01',"
                      "'2026-12-01','118.500,00 EUR','72000000',"
                      "'6 - OBJETO DO CONTRATO')")
        r = radar.app.test_client().get("/anuncio/60%2F2026")
        self.assertEqual(r.status_code, 200)
        return r.get_data(as_text=True)

    def test_toda_a_ancora_da_pagina_esta_no_indice(self):
        corpo = self._ficha()
        indice = corpo.split("<div class='ficha-indice'>")[1].split("</div>")[0]
        for bloco in self.BLOCOS:
            if "id='%s'" % bloco not in corpo:
                continue                      # esse bloco não está nesta ficha
            self.assertIn("href='#%s'" % bloco, indice,
                          "o bloco «%s» existe na página e não no índice"
                          % bloco)

    def test_um_anuncio_sem_url_nao_derruba_a_ficha(self):
        """Apanhado por este teste, a 16/09/2026: o `html.escape(None)`
        do «Ver no DR» dava 500 na ficha inteira.

        Na base dele todos os anúncios têm `url`, e por isso nunca se
        viu — mas um NULL numa coluna que ninguém garante não pode
        derrubar a página toda. Sem `url` não há ligação, e o resto da
        ficha desenha-se."""
        corpo = self._ficha()          # o fixture não põe `url`
        self.assertIn("id='proposta'", corpo)
        self.assertNotIn(">Ver no DR<", corpo)

    def test_o_bloco_da_proposta_esta_no_indice(self):
        """O que se perdeu antes, nomeado: é o bloco onde ele trabalha."""
        corpo = self._ficha()
        self.assertIn("id='proposta'", corpo)
        self.assertIn("href='#proposta'", corpo)

    def test_o_indice_nao_promete_um_bloco_que_nao_existe(self):
        """A recíproca, que já estava certa e tem de continuar: o
        «Desfecho» e os «Lotes» só entram quando há bloco. Um chip que
        salta para um bloco que não existe é a mesma mentira ao
        contrário."""
        corpo = self._ficha()
        indice = corpo.split("<div class='ficha-indice'>")[1].split("</div>")[0]
        for bloco in self.BLOCOS:
            if "href='#%s'" % bloco in indice:
                self.assertIn("id='%s'" % bloco, corpo, bloco)


class TestBlocoComPorque(unittest.TestCase):
    """O «?» de bloco, dentro da ficha (fase 5, 16/09/2026).

    O critério é o do `docs/design.md` §9 e **não** «tirar tudo»: fica no
    ecrã o que diz de onde vem um número ou o que ele não inclui; vai
    para o «?» o que diz o que o bloco É; apaga-se o que descreve o que
    já se vê.
    """

    def test_sem_explicacao_nao_ha_controlo_nenhum(self):
        """Um «?» que abre nada é um controlo morto — a mesma regra do
        título da página."""
        self.assertEqual(radar.rot_com_porque("Histórico"),
                         "<div class='rot'>Histórico</div>")
        self.assertNotIn("<details", radar.rot_com_porque("Histórico"))

    def test_com_explicacao_o_rotulo_vira_summary(self):
        saida = radar.rot_com_porque("Lotes", "vêm do anúncio")
        self.assertIn("<details class='porque porque-bloco'>", saida)
        self.assertIn("<span class='rot'>Lotes</span>", saida)
        self.assertIn("vêm do anúncio", saida)

    def test_o_facto_fica_no_corpo_e_a_explicacao_dentro_do_porque(self):
        """A prova de que a triagem foi feita e não uma limpeza cega.

        Mede-se sobre o que sai: o `<details>` fecha antes do corpo do
        bloco, por isso o que está **dentro** dele é o que só se vê ao
        abrir o «?», e o que vem depois é o que se lê sempre.
        """
        saida = (radar.rot_com_porque("Procedimentos homólogos",
                                      "as edições anteriores")
                 + "<div class='nota'>Parecido = tem em comum isto.</div>")
        dentro, fora = saida.split("</details>")
        self.assertIn("as edições anteriores", dentro)
        self.assertNotIn("Parecido", dentro)
        self.assertIn("Parecido", fora)


class TestAberturaEOEstadoDoNegocio(BaseTemporaria):
    """A abertura deixou de ser a lista (fase 4 do `docs/design.md`,
    16/09/2026): «hoje a abertura é a lista dos concursos; eu quero
    chegar e ver o estado do negócio e o que tenho de fazer».

    Ressuscita o que o `/hoje` fazia antes de sair a 15/09, e responde ao
    que ficou por responder nessa noite: «o que tenho de fazer hoje, em
    todos os concursos ao mesmo tempo».
    """

    def setUp(self):
        super().setUp()
        self.cliente = radar.app.test_client()

    def _proposta_com_tarefas(self, dias):
        with radar.liga() as c:
            c.execute("INSERT INTO anuncios (ref, titulo, entidade, estado, "
                      "data_pub, prazo) VALUES ('60/2026','Software','CML',"
                      "'novo','2026-09-01','2026-12-01')")
        id_ = radar.criar_proposta("60/2026", estado="proposta")
        hoje = datetime.date.today()
        with radar.liga() as c:
            c.execute("DELETE FROM tarefas")
            for n, d in enumerate(dias):
                quando = ("" if d is None
                          else (hoje + datetime.timedelta(days=d)).isoformat())
                c.execute("INSERT INTO tarefas (proposta_id, ref, o_que, "
                          "quando) VALUES (?,?,?,?)",
                          (id_, "60/2026", "tarefa %d" % n, quando))
        return id_

    def test_a_abertura_e_o_negocio_e_a_lista_mudou_de_endereco(self):
        r = self.cliente.get("/")
        self.assertEqual(r.status_code, 200)
        corpo = r.get_data(as_text=True)
        # «Para fazer» desde o redesenho de 17/09/2026 -- era «O que
        # tenho de fazer», e o cabeçalho passou a ter as pílulas de
        # pessoa ao lado, onde a frase comprida não cabia.
        self.assertIn("Para fazer", corpo)
        # E NAO é a lista. Mede-se a MARCAÇÃO e não o texto: o CSS vai
        # embutido em todas as páginas e cita os próprios selectores
        # (`.abas-escada{...}`), por isso um `assertNotIn("abas-escada")`
        # dava sempre falso positivo. É a mesma armadilha que o
        # test_o_indice_e_o_verificar_agora_seguem_o_papel já anotava.
        self.assertNotIn("<div class='abas abas-escada'>", corpo)
        self.assertNotIn("<details class='painel-filtros'", corpo)
        # a lista continua a existir, noutro endereço
        self.assertIn("<div class='abas abas-escada'>",
                      self.cliente.get(radar.LISTA).get_data(as_text=True))

    def test_nenhuma_ligacao_manda_para_a_lista_pelo_endereco_antigo(self):
        """O teste que faltava na fase 4, e que só se descobriu a fazer
        outra coisa (16/09/2026).

        A lista mudou de `/` para `LISTA`, e ficaram **nove** ligações a
        apontar para `/?estado=…` — nas barras dos indicadores, no
        «limpar» do filtro, no «procurar em todos» da ficha inexistente,
        no «ver em lista» do calendário, nos alertas. **Nenhuma dava
        erro**: `/` responde 200, e por isso os 952 testes passaram. Uma
        ligação que abre a página **errada** é silenciosa — abre a
        abertura com um `?estado=` que ela ignora, e quem clicou não
        percebe porque não chegou à lista.

        O que se guarda é a propriedade, não a lista dos nove sítios:
        **nada no código escreve uma ligação para `/` com query string.**
        """
        # Onde o endereço entra num molde de formatação vai como
        # LITERAL e não como `LISTA`: o `%` tem precedência sobre o `+`,
        # e `"a" + LISTA + "b %d" % x` lê-se como
        # `"a" + LISTA + ("b %d" % x)` — a formatação do resto da cadeia
        # parte-se. (O ficheiro já avisava disto no `negocio_cx()`, e eu
        # cometi-o de novo ao corrigir estas nove ligações.) É este
        # `assertEqual` que impede o literal e a constante de divergirem.
        self.assertEqual(radar.LISTA, "/concursos")
        fonte = radar_fonte()
        # A propriedade é sobre `?estado=`, e não sobre qualquer query
        # string: desde o redesenho de 17/09/2026 a abertura tem
        # parâmetros SEUS (`?dia=`, `?quem=`, `?feitas=`) e escreve-os
        # nas suas próprias ligações. O que continua proibido -- e é o
        # que custou as nove ligações silenciosas -- é mandar alguém
        # para a LISTA pelo endereço da abertura.
        for forma in ("href='/?estado=", 'href="/?estado=',
                      '"/?estado=', "'/?estado="):
            self.assertNotIn(forma, fonte, forma)
        # e o mesmo no HTML que sai, que é onde o utilizador clica
        for pagina in ("/", radar.LISTA, "/calendario",
                       "/configuracoes/indicadores"):
            corpo = self.cliente.get(pagina).get_data(as_text=True)
            self.assertNotIn("href='/?estado=", corpo, pagina)

    def test_as_rotas_antigas_da_lista_apontam_para_o_endereco_novo(self):
        for antiga in ("/anuncios", "/lista"):
            r = self.cliente.get(antiga)
            self.assertIn(r.status_code, (301, 302, 303), antiga)
            self.assertIn(radar.LISTA, r.headers["Location"], antiga)

    def test_o_para_fazer_conta_exactamente_as_linhas_que_mostra(self):
        """A regra da empresa: um número que um ecrã mostra tem de dar
        exactamente o que a ligação dele abre.

        Esteve errado: contava só as dos próximos dias (6 de 8) e ligava
        ao `/calendario`, que mostra **prazos** e não tarefas. Duas
        avarias numa: o número não era o das linhas, e o destino era
        outra população. É a mesma que se apanhou no «+N» do calendário,
        no mesmo dia.
        """
        self._proposta_com_tarefas([-6, -1, 0, 3, 40, None])
        corpo = self.cliente.get("/").get_data(as_text=True)
        # o facto diz 6, que são as seis linhas desenhadas (os quatro
        # cartões `.kpi` deram lugar à linha de factos a 17/09/2026)
        self.assertIn("6 para fazer", corpo)
        self.assertEqual(corpo.count("class='hj-row"), 6)
        # e o destino é a própria lista, aqui em baixo -- e NÃO o
        # calendário, que mostra prazos e não tarefas
        self.assertIn("href='#fazer'", corpo)
        self.assertIn("id='fazer'", corpo)
        # «para fazer» aparece antes disto no title do logótipo -- é o
        # facto que se quer, e por isso procura-se o número junto dele
        facto = corpo[corpo.index("6 para fazer") - 400:
                      corpo.index("6 para fazer")]
        self.assertIn("href='#fazer'", facto)
        self.assertNotIn("/calendario", facto)

    def test_as_atrasadas_sao_outra_categoria_e_nao_um_dia_pior(self):
        """Um «o que tenho de fazer» ordenado só por data põe o atrasado
        de ontem a seguir ao de hoje, o que é verdade e não ajuda."""
        self._proposta_com_tarefas([-6, 0, 3, 40])
        corpo = self.cliente.get("/").get_data(as_text=True)
        # Os rótulos mudaram no redesenho de 17/09/2026: o balde do meio
        # é o DIA ESCOLHIDO na fita (por omissão, hoje) e o «Nos
        # próximos N dias» passou a «Resto da semana». Estes três são os
        # que não dependem do dia da semana em que o teste corre.
        for rotulo in ("Atrasadas", "Hoje &middot;", "Mais para a frente"):
            self.assertIn(rotulo, corpo, rotulo)
        # e as atrasadas vêm primeiro, seja qual for a data
        self.assertLess(corpo.index("Atrasadas"),
                        corpo.index("Hoje &middot;"))

    def test_uma_tarefa_sem_data_nao_parte_a_ordenacao(self):
        self._proposta_com_tarefas([None])
        corpo = self.cliente.get("/").get_data(as_text=True)
        self.assertIn("sem data", corpo)
        self.assertEqual(corpo.count("class='hj-row"), 1)

    def test_sem_nada_por_fazer_o_ecra_diz_por_onde_se_comeca(self):
        """O estado vazio da abertura é o que ele vê no primeiro dia, e
        um «0» não diz nada. Diz de onde nascem as tarefas e tem saída."""
        corpo = self.cliente.get("/").get_data(as_text=True)
        self.assertIn("Nada por fazer", corpo)
        self.assertIn(radar.LISTA + "?estado=porver", corpo)

    def test_a_mensagem_da_verificacao_nao_leva_entidades_html(self):
        """A `ultima_mensagem` é uma marca na base, e quem a mostra
        escapa-a: uma entidade HTML lá dentro **sai escrita**.

        Estava assim desde a entrada da Vortal — «1108 anúncios lidos
        &middot; 6 consultas preliminares» — e só se viu quando a
        mensagem passou para a abertura, que é a página onde ele aterra
        (16/09/2026). É a mesma armadilha que a barra lateral já tinha
        tido e que o `docs/armadilhas.md` já documentava: guarda-se o
        **carácter**, não a entidade.
        """
        # Sem os comentários: os que explicam esta armadilha citam a
        # entidade de propósito, e são três na mesma função -- o ponto
        # das peças novas e o dos alertas já estavam certos, e o da
        # Vortal foi o que escapou.
        codigo = "\n".join(l for l in inspect.getsource(radar.verificar)
                           .splitlines() if not l.strip().startswith("#"))
        self.assertNotIn("&middot;", codigo)
        # e o que sai no ecrã não tem a entidade escrita
        radar.marca("ultima_mensagem", "ok, 3 lidos · 1 da Vortal")
        radar.marca("ultima_verificacao", "2026-09-16 17:04")
        corpo = self.cliente.get("/").get_data(as_text=True)
        self.assertIn("1 da Vortal", corpo)
        self.assertNotIn("&amp;middot;", corpo)

    def test_o_titulo_e_a_data_e_nao_uma_saudacao(self):
        """A saudação saiu no redesenho de 17/09/2026: é a DATA que
        titula a abertura.

        O teste que estava aqui guardava «Bom dia às 14h está errado, e
        um título errado metade do dia é pior do que nenhum» — e a
        resposta a isso deixou de ser acertar a hora: «Bom dia» não diz
        nada que o relógio do computador não diga melhor, e o dia da
        semana é metade da pergunta que esta página responde.

        Fica a mesma propriedade, invertida: o título **não muda com a
        hora**, e muda com o dia.
        """
        vistos = set()
        for hora in (9, 15, 22):
            falso = datetime.datetime(2026, 9, 16, hora, 0)
            with unittest.mock.patch.object(radar, "datetime") as dt:
                dt.now.return_value = falso
                dt.strptime = datetime.datetime.strptime
                corpo = self.cliente.get("/").get_data(as_text=True)
            self.assertIn("Quarta, 16 de setembro", corpo, "%dh" % hora)
            for saudacao in ("Bom dia", "Boa tarde", "Boa noite"):
                self.assertNotIn(saudacao, corpo, saudacao)
            vistos.add(corpo[corpo.index("<h1 class='tit'>"):][:60])
        self.assertEqual(len(vistos), 1, "o título mudou com a hora")


class TestCalendarioEPorDiaENaoUmGantt(BaseTemporaria):
    """O calendário era uma grade de «uma linha por concurso × uma coluna
    por dia» — a forma de um Gantt, que serve para **intervalos**.

    Um prazo não é um intervalo, é um dia. Medido na base verdadeira, em
    `?estado=porver`: **48 870 células desenhadas para mostrar 1 086
    factos** (2,2% cheias), 2,0 MB de HTML e 86 915 px de altura. E a
    pílula dizia «prazo» as 1 086 vezes, porque a única informação da
    célula era a POSIÇÃO — que já estava no cabeçalho da coluna.

    O que este teste fixa é a inversão: **as células são sempre 42**,
    venham dez linhas ou dez mil. É essa a propriedade que impede a
    forma antiga de voltar por distracção.
    """

    def _por_ver(self, quantos, dia):
        with radar.liga() as c:
            for n in range(quantos):
                c.execute("INSERT INTO anuncios (ref, titulo, entidade, "
                          "estado, data_pub, prazo) VALUES (?,?,?,?,?,?)",
                          ("%d/2026" % n, "Anúncio %d" % n, "Município %d" % n,
                           "novo", dia.isoformat(), dia.isoformat()))

    def _grade(self):
        r = radar.app.test_client().get("/calendario?estado=porver")
        self.assertEqual(r.status_code, 200)
        return r.get_data(as_text=True)

    def test_as_celulas_sao_sempre_42_venham_dez_ou_dez_mil(self):
        hoje = datetime.date.today()
        dia = hoje + datetime.timedelta(days=3)
        for quantos in (0, 1, 200):
            with radar.liga() as c:
                c.execute("DELETE FROM anuncios")
            self._por_ver(quantos, dia)
            self.assertEqual(self._grade().count("class='cal-dia"), 42,
                             "com %d anúncios" % quantos)

    def test_a_grade_comeca_sempre_a_uma_segunda(self):
        """Uma grade de semanas que comece a uma quarta não se lê como um
        calendário. E é por isso que a janela é um número inteiro de
        semanas e não «45 dias a partir de hoje»."""
        hoje = datetime.date.today()
        self._por_ver(1, hoje + datetime.timedelta(days=2))
        corpo = self._grade()
        principio = hoje - datetime.timedelta(days=hoje.weekday())
        self.assertEqual(principio.weekday(), 0)
        self.assertIn(radar.data_pt(principio.isoformat()), corpo)

    def test_nenhum_se_perde_no_mais_n(self):
        """O que não cabe na célula vai para o `<details>`, e **está lá**.
        Um «+86» que esconda oitenta e seis para sempre é pior do que não
        os mostrar."""
        dia = datetime.date.today() + datetime.timedelta(days=2)
        self._por_ver(radar.CABEM_NO_DIA + 5, dia)
        corpo = self._grade()
        self.assertIn("+5", corpo)
        for n in range(radar.CABEM_NO_DIA + 5):
            self.assertIn("Anúncio %d<" % n, corpo)

    def test_um_dia_sem_nada_e_um_dia_e_nao_um_erro(self):
        """Sem `?estado=` o calendário mostra as propostas em aberto, que
        numa empresa que ainda não abriu nenhuma são zero. A grade desenha-se
        na mesma, e as abas por cima são a saída — antes era um beco, em
        que a única forma de ver outra coisa era escrever `?estado=` na
        barra de endereços."""
        r = radar.app.test_client().get("/calendario")
        corpo = r.get_data(as_text=True)
        self.assertEqual(corpo.count("class='cal-dia"), 42)
        self.assertIn("abas-escada", corpo)

    def test_o_que_fica_fora_da_janela_diz_se(self):
        hoje = datetime.date.today()
        self._por_ver(1, hoje + datetime.timedelta(days=120))
        corpo = self._grade()
        self.assertIn("fora destas seis semanas", corpo)


class TestAlteracoesDoDR(BaseTemporaria):
    """O DR não emenda um anúncio: publica outro, com ref novo, cujo
    texto começa por «Alteração do Anúncio de procedimento n.º X». Até
    01/09/2026 cada republicação entrava como anúncio novo — o mesmo
    concurso três vezes no por ver, e 511 descartes repetidos do Afonso
    sobre procedimentos que já tinha descartado. A regra: o ORIGINAL é a
    ficha do procedimento e fica com o prazo e o preço em vigor; a
    alteração fica na base, fora das listas ('alteracao'). Medido: 763
    das 5 661 lidas, 103 em cadeia (citam a alteração anterior)."""

    CORPO = ("\n1 - IDENTIFICAÇÃO E CONTACTOS DA ENTIDADE ADJUDICANTE\n"
             "Designação da entidade adjudicante: Município de Exemplo\n"
             "NIPC: 501234567\n\n6 - OBJETO DO CONTRATO\n"
             "Vocabulário Principal: 72268000 - Serviços de software\n"
             "Preço base s/IVA: %s\n\n13 - CONDIÇÕES DE APRESENTAÇÃO\n"
             "Plataforma eletrónica utilizada pela entidade adjudicante: ACIN\n"
             "Prazo para apresentação das propostas: %s 23:59\n")

    def _texto(self, prazo="13-08-2026", preco="900.000,00 EUR", altera=""):
        cabeca = ("Alteração do Anúncio de procedimento n.º %s, de 2026-07-17, "
                  "com o ID 419967433 " % altera) if altera else ""
        return cabeca + self.CORPO % (preco, prazo)

    def _poe(self, ref, data_pub, texto=None, estado="novo", **campos):
        with radar.liga() as c:
            c.execute("INSERT INTO anuncios (ref, titulo, entidade, data_pub, "
                      "tipo, url, estado) VALUES (?,?,?,?,?,?,?)",
                      (ref, "Software", "Município de Exemplo", data_pub,
                       "Anúncio de procedimento", "https://dr/" + ref, estado))
            if texto is not None:
                lidos = radar.campos_do_detalhe(texto)
                c.execute("UPDATE anuncios SET texto=?, prazo=?, preco_base=?, "
                          "altera=?, detalhe_lido=1 WHERE ref=?",
                          (texto, lidos["prazo"], lidos["preco_base"],
                           lidos["altera"], ref))
            for k, v in campos.items():
                c.execute("UPDATE anuncios SET %s=? WHERE ref=?" % k, (v, ref))

    def _le(self, ref):
        with radar.liga() as c:
            return c.execute("SELECT * FROM anuncios WHERE ref=?", (ref,)).fetchone()

    def _chega(self, ref, texto):
        """A leitura do detalhe, como o DR a devolve."""
        radar._guardar_detalhe(
            ref, {"data": {"DetalheConteudo": {"Texto": texto, "URL_PDF": ""}}})

    def _historico(self, ref, accao=None):
        with radar.liga() as c:
            return [dict(p) for p in c.execute(
                "SELECT accao, detalhe FROM historico WHERE ref=?" +
                (" AND accao=?" if accao else ""),
                (ref, accao) if accao else (ref,))]

    def test_reconhece_o_cabecalho_da_alteracao(self):
        self.assertEqual(radar.anuncio_alterado(
            "Alteração do Anúncio de procedimento n.º 18372/2026, de "
            "2026-07-17, com o ID 419967433 1 - IDENTIFICAÇÃO"), "18372/2026")
        self.assertEqual(radar.anuncio_alterado(
            " alteração do anúncio de procedimento n. º 5 / 2025 ..."), "5/2025")
        self.assertEqual(radar.anuncio_alterado(
            "Alteração do Anúncio de concurso urgente n.º 7/2026"), "7/2026")
        self.assertEqual(radar.anuncio_alterado(self.CORPO % ("1", "2")), "")
        self.assertEqual(radar.anuncio_alterado(""), "")
        # a citacao a meio do texto nao conta: so o cabecalho
        self.assertEqual(radar.anuncio_alterado(
            self.CORPO % ("1", "2") +
            "Alteração do Anúncio de procedimento n.º 1/2026"), "")

    def test_campos_do_detalhe_traz_o_altera(self):
        self.assertEqual(radar.campos_do_detalhe(
            self._texto(altera="100/2026"))["altera"], "100/2026")
        self.assertEqual(radar.campos_do_detalhe(self._texto())["altera"], "")

    def test_a_alteracao_esconde_se_e_o_original_fica_com_o_prazo_novo(self):
        self._poe("100/2026", "2026-07-17", self._texto())
        self._poe("200/2026", "2026-08-14")
        self._chega("200/2026", self._texto(prazo="11-09-2026",
                                            altera="100/2026"))
        alt, orig = self._le("200/2026"), self._le("100/2026")
        self.assertEqual(alt["estado"], "alteracao")
        self.assertEqual(alt["altera"], "100/2026")
        self.assertEqual(orig["estado"], "novo")
        self.assertEqual(orig["prazo"], "2026-09-11")
        self.assertEqual(orig["alterado_por"], "200/2026")
        alterou = self._historico("100/2026", "alterou")
        self.assertEqual(len(alterou), 1)
        self.assertIn("13/08/2026 → 11/09/2026", alterou[0]["detalhe"])
        # nao marcado: o historico conta, a fila do resumo nao
        with radar.liga() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) n FROM alteracoes")
                             .fetchone()["n"], 0)

    def test_um_marcado_alterado_vai_para_a_fila_do_resumo(self):
        self._poe("100/2026", "2026-07-17", self._texto(), estado="interessa")
        self._poe("200/2026", "2026-08-14")
        self._chega("200/2026", self._texto(prazo="11-09-2026",
                                            preco="950.000,00 EUR",
                                            altera="100/2026"))
        with radar.liga() as c:
            fila = c.execute("SELECT ref, campo, antes, depois FROM alteracoes "
                             "ORDER BY campo").fetchall()
        self.assertEqual([(f["ref"], f["campo"]) for f in fila],
                         [("100/2026", "prazo"), ("100/2026", "preco_base")])
        self.assertEqual(fila[1]["depois"], "950.000,00 EUR")

    def test_o_nao_fomos_fica_e_a_lista_nao_repete(self):
        self._poe("100/2026", "2026-07-17", self._texto())
        p = radar.criar_proposta("100/2026", estado="nao_fomos")
        radar.gravar_motivo(p, "Preço base baixo")
        self._poe("200/2026", "2026-08-14")
        self._chega("200/2026", self._texto(prazo="11-09-2026",
                                            altera="100/2026"))
        viva = radar.propostas_de("100/2026")[0]
        self.assertEqual((viva["estado"], viva["motivo"]),
                         ("nao_fomos", "Preço base baixo"))
        # "todos" sao todos os procedimentos: a alteracao nao entra
        onde, valores = radar.condicoes({"estado": ""})
        with radar.liga() as c:
            refs = [r["ref"] for r in c.execute(
                "SELECT ref FROM anuncios" + onde, valores)]
        self.assertEqual(refs, ["100/2026"])

    def test_a_triagem_feita_na_alteracao_passa_para_o_original(self):
        """513 vezes antes disto: o Afonso decidiu na republicação.

        O que passa é a PROPOSTA inteira (15/09/2026) e não um punhado
        de colunas -- com o preço proposto, o lugar e o motivo, que é o
        que custa mais a reescrever."""
        self._poe("100/2026", "2026-07-17", self._texto())
        self._poe("200/2026", "2026-08-14",
                  self._texto(prazo="11-09-2026", altera="100/2026"))
        p = radar.criar_proposta("200/2026", estado="nao_fomos")
        radar.gravar_motivo(p, "Falta de CV's")
        with radar.liga() as c:
            c.execute("UPDATE anuncios SET altera=NULL")   # texto por reler
        self.assertEqual(radar.agrupar_alteracoes(), (2, 1))
        viva = radar.propostas_de("100/2026")
        self.assertEqual([(x["estado"], x["motivo"]) for x in viva],
                         [("nao_fomos", "Falta de CV's")])
        self.assertEqual(radar.propostas_de("200/2026"), [])
        self.assertEqual(self._le("200/2026")["estado"], "alteracao")
        self.assertTrue(any("decidido na alteração" in p["detalhe"]
                            for p in self._historico("100/2026", "estado")))
        # segunda passagem: nada a fazer
        self.assertEqual(radar.agrupar_alteracoes(), (0, 0))

    def test_a_decisao_na_alteracao_ganha_ao_descarte_antigo_do_original(self):
        # aconteceu na migracao de 01/09/2026: um «interessa» do Afonso na
        # republicacao ficou por baixo de um descarte antigo do original,
        # e o item sumiu-se dos Interessados
        self._poe("100/2026", "2026-07-17", self._texto())
        velha = radar.criar_proposta("100/2026", estado="nao_fomos")
        radar.gravar_motivo(velha, "Preço base baixo")
        self._poe("200/2026", "2026-08-14",
                  self._texto(prazo="11-09-2026", altera="100/2026"))
        radar.criar_proposta("200/2026", estado="proposta")
        radar.aplicar_alteracao("200/2026")
        viva = radar.propostas_de("100/2026")
        # uma só, e é a da alteração: duas davam dois cartões do mesmo
        # procedimento no quadro
        self.assertEqual([(x["estado"], x["motivo"]) for x in viva],
                         [("proposta", None)])
        self.assertTrue(any("era «Não fomos»" in p["detalhe"]
                            for p in self._historico("100/2026", "estado")))
        # mas uma alteração SEM proposta não é decisão nenhuma, e não
        # pode desfazer o "Não fomos" do original: uma republicação que
        # ninguém triou é o DR a falar, não a empresa
        self._poe("400/2026", "2026-07-01", self._texto())
        antigo = radar.criar_proposta("400/2026", estado="nao_fomos")
        radar.gravar_motivo(antigo, "Falta de CV's")
        self._poe("500/2026", "2026-08-02",
                  self._texto(prazo="20-09-2026", altera="400/2026"))
        radar.aplicar_alteracao("500/2026")
        fica = radar.propostas_de("400/2026")
        self.assertEqual([(x["estado"], x["motivo"]) for x in fica],
                         [("nao_fomos", "Falta de CV's")])

    def test_a_cadeia_segue_ate_a_raiz_e_o_mais_recente_manda(self):
        self._poe("100/2026", "2026-07-17", self._texto())
        self._poe("200/2026", "2026-08-14")
        self._poe("300/2026", "2026-08-25")
        self._chega("200/2026", self._texto(prazo="21-08-2026", altera="100/2026"))
        self._chega("300/2026", self._texto(prazo="11-09-2026", altera="200/2026"))
        orig = self._le("100/2026")
        self.assertEqual(orig["alterado_por"], "300/2026")
        self.assertEqual(orig["prazo"], "2026-09-11")
        self.assertEqual(self._le("200/2026")["estado"], "alteracao")
        self.assertEqual(self._le("300/2026")["estado"], "alteracao")

    def test_a_ordem_de_leitura_invertida_da_o_mesmo(self):
        # ler_detalhes() le do mais recente para o mais antigo
        self._poe("100/2026", "2026-07-17", self._texto())
        self._poe("200/2026", "2026-08-14")
        self._poe("300/2026", "2026-08-25")
        self._chega("300/2026", self._texto(prazo="11-09-2026", altera="200/2026"))
        self._chega("200/2026", self._texto(prazo="21-08-2026", altera="100/2026"))
        orig = self._le("100/2026")
        self.assertEqual((orig["alterado_por"], orig["prazo"], orig["estado"]),
                         ("300/2026", "2026-09-11", "novo"))
        self.assertEqual(self._le("200/2026")["estado"], "alteracao")
        self.assertEqual(self._le("300/2026")["estado"], "alteracao")

    def test_sem_o_original_na_base_a_alteracao_fica_como_anuncio(self):
        self._poe("200/2026", "2026-08-14")
        self._chega("200/2026", self._texto(altera="999/2020"))
        alt = self._le("200/2026")
        self.assertEqual((alt["estado"], alt["altera"]), ("novo", "999/2020"))

    def test_reler_o_original_nao_repoe_o_prazo_antigo(self):
        # a pagina do original no DR nunca muda; rele-la escrevia o prazo
        # velho por cima do novo e registava uma alteracao falsa
        self._poe("100/2026", "2026-07-17", self._texto())
        self._poe("200/2026", "2026-08-14")
        self._chega("200/2026", self._texto(prazo="11-09-2026", altera="100/2026"))
        self._chega("100/2026", self._texto())
        self.assertEqual(self._le("100/2026")["prazo"], "2026-09-11")
        self.assertEqual(len(self._historico("100/2026", "alterou")), 1)
        # e o --reler tambem nao
        radar.reparsear()
        self.assertEqual(self._le("100/2026")["prazo"], "2026-09-11")
        self.assertEqual(self._le("100/2026")["altera"], "")

    def test_reler_marcados_le_a_pagina_da_alteracao_em_vigor(self):
        fonte = inspect.getsource(radar.reler_marcados)
        self.assertIn("COALESCE(a.alterado_por, a.ref)", fonte)
        self.assertIn("x.ref=a.alterado_por", fonte)

    def test_a_alteracao_nao_se_tria(self):
        self._poe("100/2026", "2026-07-17", self._texto())
        self._poe("200/2026", "2026-08-14")
        self._chega("200/2026", self._texto(prazo="11-09-2026", altera="100/2026"))
        r = radar.app.test_client().post("/estado/200%2F2026/interessa")
        self.assertEqual(r.status_code, 302)
        self.assertIn("aviso=", r.headers["Location"])
        self.assertIn("100%2F2026", r.headers["Location"])
        self.assertEqual(self._le("200/2026")["estado"], "alteracao")
        self.assertEqual(self._le("100/2026")["estado"], "novo")

    def test_a_migracao_corre_uma_vez_por_marca(self):
        self._poe("100/2026", "2026-07-17", self._texto())
        self._poe("200/2026", "2026-08-14",
                  self._texto(prazo="11-09-2026", altera="100/2026"))
        with radar.liga() as c:
            c.execute("UPDATE anuncios SET altera=NULL")
            c.execute("DELETE FROM estado WHERE chave='alteracoes_agrupadas'")
        radar.iniciar_db()
        self.assertEqual(self._le("200/2026")["estado"], "alteracao")
        n = len(self._historico("100/2026"))
        radar.iniciar_db()              # segunda vez: marca posta, nada muda
        self.assertEqual(len(self._historico("100/2026")), n)
        self.assertEqual(radar.le_marca("alteracoes_agrupadas"), "1")

    def test_o_nome_do_estado_e_por_extenso(self):
        self.assertEqual(radar._NOMES_ESTADO["alteracao"], "alteração")

    def test_os_alertas_por_enviar_saltam_as_alteracoes(self):
        self.assertIn("a.estado != 'alteracao'",
                      inspect.getsource(radar.alertas_por_enviar))


class TestEstadoEfectivoDaEmpresa(BaseTemporaria):
    """O que o registo da empresa DIZ sobre um concurso, e como isso se
    traduz numa das oito palavras da escada (02-04/09/2026, com as
    decisões dele depois de ver os números).

    Era o `TestRegistoDaEmpresa`, 638 linhas: o leitor do Excel antigo
    (`.xlsm` do SharePoint, ligado por semelhança de título) saiu a
    15/09/2026 e levou 17 testes com ele. Estes seis não eram dele --
    são da regra do Zoho, da guarda dos lotes, dos lotes no texto do DR
    e da porta que ficou fechada no front. O teste do
    `desaplicar_da_copia()` mudou-se para o `TestModeloDaEmpresa`, que é
    por onde uma importação passa hoje."""

    def test_o_zoho_manda_no_estado_menos_no_nao_fomos(self):
        # A regra dele, 03/09/2026, depois de ver os numeros: "o que
        # esta no Excel como nao fomos, esse estado prevalece ao estado
        # do Zoho, mas e o unico". A excepcao existe porque em 46 das 92
        # linhas que cruzam o Excel diz "Nao fomos" e o Zoho diz "Lost":
        # sem ela, metade do cruzamento perdia a distincao.
        efec = empresa.estado_efectivo
        self.assertEqual(efec({"status": "Não fomos", "zoho_fase": "Lost"}),
                         "Não fomos")
        self.assertEqual(efec({"status": "Não fomos", "zoho_fase": "Won"}),
                         "Não fomos")
        # em tudo o resto ganha o Zoho
        self.assertEqual(efec({"status": "Submetido", "zoho_fase": "Lost"}),
                         "Perdido")
        self.assertEqual(efec({"status": "Submetido", "zoho_fase": "Won"}), "Ganho")
        self.assertEqual(efec({"status": "TBD", "zoho_fase": "Cancel"}), "Cancelado")
        # o "2.3 - Negotiation" tem de casar mesmo: o _norma() guarda os
        # pontos e os hifens, e uma chave escrita "2 3 negotiation" nao
        # casava nada e caia em silencio para o estado do Excel
        self.assertEqual(efec({"status": "Submetido",
                               "zoho_fase": "2.3 - Negotiation"}), "Submetido")
        self.assertIn("2.3 - negotiation", empresa.TRADUCAO_ZOHO)
        # sem Zoho, ou com uma fase que nao se traduz, manda o Excel
        self.assertEqual(efec({"status": "Ganho", "zoho_fase": None}), "Ganho")
        self.assertEqual(efec({"status": "Ganho"}), "Ganho")
        self.assertEqual(efec({"status": "Submetido", "zoho_fase": "Fase Nova"}),
                         "Submetido")
        # e a triagem segue a regra, nao o status cru
        estado, _ = empresa.estado_pretendido(
            {"status": "Submetido", "zoho_fase": "Lost"})
        self.assertEqual(estado, "perdido")        # perdido, nao submetido
        self.assertEqual(empresa.estado_pretendido(
            {"status": "Não fomos", "zoho_fase": "Won", "razao": ""}),
            ("nao_fomos", {"motivo": None}))        # o Zoho nao o resgata

    def test_o_zoho_nao_decide_uma_linha_que_e_um_lote(self):
        # 04/09/2026, dele: "o #14 e lotes e nos ganhamos um deles". As
        # duas fontes contam coisas diferentes -- o Excel uma linha por
        # lote, o Zoho um negocio por procedimento -- e um "Won" do Zoho
        # quer dizer "ganhamos pelo menos um lote", nao "ganhamos este".
        # O caso real: 1947/2026, tres lotes, tres linhas (#14 o L1
        # perdido, #97 o L2 ganho, #98 o L3 perdido) e um so negocio no
        # Zoho, "Won" com 169 344 contra os 109 065,60 do L1. Sem esta
        # guarda o #14 passava de Perdido a Ganho.
        efec = empresa.estado_efectivo
        l1 = {"status": "Perdido", "zoho_fase": "Won", "lote": 1,
              "preco_base": 109065.6, "zoho_montante": 169344.0}
        self.assertEqual(efec(l1), "Perdido")
        # e nao e so o "Won": nenhuma fase do Zoho decide um lote
        self.assertEqual(efec({"status": "Submetido", "zoho_fase": "Lost",
                               "lote": 2}), "Submetido")
        # o conjunto (lote 0) NAO e um lote, e aceita o Zoho
        self.assertEqual(efec({"status": "Submetido", "zoho_fase": "Lost",
                               "lote": 0}), "Perdido")
        # e um anuncio sem lotes tambem
        self.assertEqual(efec({"status": "Submetido", "zoho_fase": "Lost",
                               "lote": None}), "Perdido")
        # a excepcao do "Nao fomos" continua a valer por cima de tudo
        self.assertEqual(efec({"status": "Não fomos", "zoho_fase": "Won",
                               "lote": 1}), "Não fomos")
        # e a triagem segue-a
        estado, _ = empresa.estado_pretendido(dict(l1, lugar=3))
        self.assertEqual(estado, "perdido")        # perdido, nao ganho

    def test_estado_pretendido_traduz_o_excel(self):
        """Desde 15/09/2026 devolve uma das oito palavras da empresa, e não
        um par estado+fase: o vocabulário passou a ser um só, e
        "interessa" com uma fase ao lado era o mesmo estado dito duas
        vezes."""
        self.assertEqual(empresa.estado_pretendido(
            {"status": "Não fomos", "razao": "Prazo de Entrega curto"}),
            ("nao_fomos", {"motivo": "Prazo curto"}))
        self.assertEqual(empresa.estado_pretendido(
            {"status": "Não fomos", "razao": ""}),
            ("nao_fomos", {"motivo": None}))
        estado, campos = empresa.estado_pretendido(
            {"status": "Ganho", "valor_proposta": 78987, "lugar": None,
             "concorrentes": [{"lugar": 1, "nome": "LATD", "valor": 78987}]})
        self.assertEqual((estado, campos["lugar"], campos["valor_proposta"]),
                         ("ganho", 1, "78.987,00 EUR"))
        self.assertIn("1.º LATD 78.987,00 EUR", campos["top3"])
        # as oito palavras, e mais nenhuma
        self.assertIn(estado, radar.CHAVES_DA_EMPRESA)
        self.assertIsNone(empresa.estado_pretendido({"status": "Cancelado"}))
        self.assertIsNone(empresa.estado_pretendido({"status": "TBD"}))

    def test_o_front_nao_mudou(self):
        # decisao do Afonso a 02/09/2026: nenhuma alteracao no front antes
        # de o registo estar consolidado -- a pagina /empresa e o bloco da
        # ficha que chegaram a existir sairam, e nao voltam sem ele dizer
        self.assertNotIn("empresa", radar.ITEM_DA_PAGINA)
        self.assertNotIn("/empresa", [r.rule for r in radar.app.url_map.iter_rules()])
        self.assertFalse(hasattr(radar, "empresa_cx"))
        # quatro desde 13/09/2026: "Nao faz parte da oferta" entrou a
        # pedido dele ("Mudancas na plataforma RADAR"); os dois do Excel
        # continuam de fora ate o registo se aplicar
        self.assertEqual(len(radar.MOTIVOS_ABANDONO), 4)
        self.assertIn("Não faz parte da oferta", radar.MOTIVOS_ABANDONO)

    LOTES = ("\n1 - IDENTIFICAÇÃO\nDesignação da entidade adjudicante: SPMS\n"
             "Procedimento com lotes? Sim\nNº Máx. de Lotes Autorizado: 3\n\n"
             "6 - OBJETO DO CONTRATO\nDesignação do contrato: Biblioteca\n"
             "Preço base s/IVA: 735.889,84 EUR\nLotes: \n"
             "Nº: LOT-0001\nDescrição do Lote: Lote 1 - Levantamento de requisitos\n"
             "Preço base s/IVA: 53.667,20 EUR\nVocabulário Principal: 72500000\n"
             "Nº: LOT-0002\nDescrição do Lote: Lote 2 - Front-end e back-end\n"
             "Preço base s/IVA: 268.336,00 EUR\n"
             "Nº: LOT-0003\nDescrição do Lote: Lote 3 - Testes\n"
             "Valor Estimado do Lote: 26.833,60 EUR\n\n"
             "7 - PRAZO\nPrazo para apresentação das propostas: 23-08-2026 23:59\n")

    def test_le_os_lotes_do_anuncio(self):
        lotes = radar.lotes_do_texto(self.LOTES)
        self.assertEqual([l["n"] for l in lotes], [1, 2, 3])
        self.assertEqual(lotes[0]["descricao"], "Lote 1 - Levantamento de requisitos")
        self.assertEqual(lotes[1]["preco_base"], "268.336,00 EUR")
        self.assertEqual(lotes[2]["preco_base"], "26.833,60 EUR")   # valor estimado
        self.assertEqual(radar.lotes_do_texto(
            self.LOTES.replace("lotes? Sim", "lotes? Não")), [])
        self.assertEqual(radar.lotes_do_texto(""), [])
        campos = radar.campos_do_detalhe(self.LOTES)
        self.assertEqual(json.loads(campos["lotes"])[0]["n"], 1)
        self.assertEqual(campos["preco_base"], "735.889,84 EUR")  # o do procedimento
        self.assertEqual(radar.campos_do_detalhe("sem lotes")["lotes"], "")

    def test_as_razoes_do_excel_mapeiam_para_motivos(self):
        # os dois que ainda nao estao em MOTIVOS_ABANDONO entram la quando a
        # triagem do registo passar a aplicar-se (ver CLAUDE.md)
        self.assertEqual(set(empresa.MAPA_RAZAO.values()) - set(radar.MOTIVOS_ABANDONO),
                         {"Fora do âmbito", "Prazo curto"})


class TestPaginasNaoVarremATabelaLarga(BaseTemporaria):
    """A tabela `anuncios` é LARGA: a 05/09/2026, o `texto` do anúncio
    sozinho são 843 MB, porque o acervo passou a onze anos e os 209 177
    anúncios têm todos detalhe lido. Um `SCAN anuncios` não é "ler
    duzentas mil linhas": é arrastar 843 MB do disco — e o disco é uma
    pen a ~42 MB/s a frio. Os números deste docstring dobraram numa
    tarde; a regra não.

    Enquanto só 9% tinham texto isto não se via; no dia em que passaram a
    ter todos, a página inicial fazia nove varrimentos por pedido e
    levava 1,6 s a quente. Os índices `ix_anuncios_lista`,
    `_triagem`, `_detalhe`, `_plataforma` e `_estado_cpv` existem para
    cobrir essas consultas.

    O teste não olha para o texto do SQL — olha para o PLANO de cada
    consulta que a rota dispara de facto. Uma consulta nova que não caiba
    nos índices, ou um índice apagado, aparecem aqui como um `SCAN`."""

    def _planos(self, rota):
        """Corre a rota e devolve (sql, plano) de tudo o que ela pediu."""
        import sqlite3 as s3
        apanhado = []

        class Cursor(s3.Cursor):
            def execute(self, sql, *a, **k):
                apanhado.append((sql, a[0] if a else ()))
                return super().execute(sql, *a, **k)

        class Ligacao(s3.Connection):
            def cursor(self, factory=Cursor):
                return super().cursor(factory)

            def execute(self, sql, *a, **k):
                return self.cursor().execute(sql, *a, **k)

        antes = s3.connect
        s3.connect = lambda *a, **k: antes(*a, factory=Ligacao,
                                           **{x: y for x, y in k.items()
                                              if x != "factory"})
        try:
            radar.app.test_client().get(rota)
        finally:
            s3.connect = antes
        planos = []
        with radar.liga() as c:
            for sql, par in apanhado:
                if not sql.lstrip().upper().startswith("SELECT"):
                    continue
                if "anuncios" not in sql:
                    continue
                try:
                    passos = [r[-1] for r in c.execute(
                        "EXPLAIN QUERY PLAN " + sql, par)]
                except s3.Error:
                    continue        # consulta do outro ficheiro (corpus)
                planos.append((sql, passos))
        return planos

    def _sem_varrimento(self, rota):
        planos = self._planos(rota)
        self.assertTrue(planos, "a rota %s não consultou os anúncios" % rota)
        # `SCAN anuncios USING COVERING INDEX x` é o que se quer: varre o
        # índice, e o índice não tem o `texto` lá dentro. O que se recusa
        # é o `SCAN anuncios` seco — esse arrasta as linhas todas — e o
        # `SCAN ... USING INDEX` sem COVERING, que vai à tabela buscar
        # cada linha que o índice aponta e é ainda pior.
        maus = [(" ".join(sql.split())[:120], p)
                for sql, passos in planos for p in passos
                if p.startswith("SCAN anuncios") and "COVERING INDEX" not in p]
        self.assertEqual(maus, [], "%s varre a tabela larga: %s" % (rota, maus))

    def test_a_lista_nao_varre(self):
        self._sem_varrimento("/")

    def test_os_indicadores_nao_varrem(self):
        self._sem_varrimento("/configuracoes/indicadores")

    def test_os_alertas_nao_varrem(self):
        self._sem_varrimento("/configuracoes/alertas")

    def test_a_ficha_da_entidade_nao_varre(self):
        """17/09/2026, e apanhado por ele a usar a aplicação: «parece-me
        que está muito lenta».

        A fase 2 pôs o lado da empresa na ficha da entidade, e o número
        dos anúncios dela sai do filtro `nif` do `condicoes()` —
        `nif = ? OR entidade IN (SELECT DISTINCT entidade WHERE nif=?)`.
        **Nenhuma das duas metades tinha índice**, e por isso a página
        fazia dois `SCAN anuncios`: 0,33 s na v1.6.0 contra 1,63 s na
        v1.7.0, medido lado a lado sobre a mesma base.
        """
        with radar.liga() as c:
            c.execute("INSERT INTO anuncios (ref, titulo, entidade, nif, "
                      "estado, data_pub, prazo, titulo_norm, entidade_norm) "
                      "VALUES ('90/2026','Software','CML','506000000','novo',"
                      "'2026-09-01','2026-12-01','software','cml')")
        self._sem_varrimento("/entidade/506000000")

    def test_os_dois_indices_da_entidade_sao_precisos_juntos(self):
        """A regra que o `_sem_varrimento()` não consegue dizer: qual dos
        dois índices é que faltava. Só com o do `nif`, o SQLite não usa a
        optimização MULTI-INDEX OR e varre na mesma — 1,36 s sem nenhum,
        0,66 s só com o do `nif`, 0,01 s com os dois (medido). É o erro
        fácil de cometer a limpar índices «que ninguém usa»."""
        with radar.liga() as c:
            tem = {r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='index'")}
        self.assertIn("ix_anuncios_nif", tem)
        self.assertIn("ix_anuncios_entidade", tem)
        onde, vals = radar.condicoes({"nif": "506000000", "estado": ""})
        with radar.liga() as c:
            passos = [r[-1] for r in c.execute(
                "EXPLAIN QUERY PLAN SELECT COUNT(*) FROM anuncios" + onde,
                vals)]
        self.assertTrue(any("MULTI-INDEX OR" in p for p in passos), passos)

    def test_os_indices_existem_e_repor_e_idempotente(self):
        # o mesmo que as migrações: correr duas vezes não muda nada
        radar.iniciar_db()
        with radar.liga() as c:
            tem = {r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='index'")}
        for nome in ("ix_anuncios_lista", "ix_anuncios_triagem",
                     "ix_anuncios_detalhe", "ix_anuncios_plataforma",
                     "ix_anuncios_estado_cpv", "ix_anuncios_acervo"):
            self.assertIn(nome, tem)

    def test_o_mapa_das_plataformas_sai_de_um_indice_de_cobertura(self):
        """05/09/2026: o mapa das plataformas da lista custava 0,45 s.

        O `ix_anuncios_detalhe(detalhe_lido, plataforma)` foi feito para
        esta consulta quando ela nao filtrava por estado; passou a
        filtrar (`estado != 'alteracao'`, mais o recorte), e faltando
        colunas ao indice o SQLite ia a tabela buscar **cada linha**.
        Com 66 mil anuncios nem se via; com 209 177 e a `anuncios` em
        843 MB eram 0,45 s. Com o `ix_anuncios_acervo`, 0,037 s.

        O `_sem_varrimento()` nao apanha isto: recusa `SCAN anuncios`
        sem cobertura, e este plano e um **SEARCH**. Um SEARCH que
        acerta em duzentas mil linhas custa o mesmo que um SCAN, e a
        unica diferenca no plano e a palavra. Por isso este teste nao
        olha para a rota: olha para a consulta, e exige a palavra
        COVERING.
        """
        radar.iniciar_db()
        sql = ("SELECT COALESCE(NULLIF(plataforma,''),'(nenhuma)') p,"
               " COUNT(*) n FROM anuncios"
               " WHERE estado != 'alteracao' AND detalhe_lido=1 GROUP BY p")
        with radar.liga() as c:
            passos = [r[-1] for r in c.execute("EXPLAIN QUERY PLAN " + sql)]
        usa = [p for p in passos if "anuncios" in p]
        self.assertTrue(usa, "a consulta nem sequer toca na tabela")
        self.assertTrue(
            all("COVERING INDEX" in p for p in usa),
            "o mapa das plataformas vai a tabela buscar as linhas: %s" % usa)

    def test_o_corpus_conta_se_uma_vez_por_pedido(self):
        """`ha_corpus()` contava 1,99 milhões de linhas quatro ou cinco
        vezes na mesma página — a barra, a árvore e o corpo. Dentro de um
        pedido conta-se uma vez; fora dele conta sempre."""
        vezes = []
        antes = radar.liga_corpus

        def espia():
            vezes.append(1)
            return antes()

        radar.liga_corpus = espia
        try:
            if not os.path.exists(radar.CORPUS):
                self.skipTest("sem corpus nesta máquina")
            radar.app.test_client().get("/quadro")
            self.assertLessEqual(vezes.count(1), 1,
                                 "o corpus contou-se %d vezes num pedido"
                                 % len(vezes))
            vezes.clear()
            radar.ha_corpus()
            radar.ha_corpus()
            self.assertEqual(len(vezes), 2)     # fora do pedido, sem cache
        finally:
            radar.liga_corpus = antes


class TestTiposDeProcedimentoGuardados(CorpusTemporario):
    """`tipos_de_procedimento()` agrupava 1,99 milhões de linhas em cada
    pedido de /contratos e de /alertas — 0,17 s por página, e a mesma
    consulta escrita duas vezes. Guarda-se em memória, com a identidade
    do ficheiro do corpus como chave: a lista muda quando a importação
    semanal corre, e só aí.

    O que o teste separa é a CONDIÇÃO da espera: conta quantas vezes se
    foi ao corpus, e verifica as duas coisas — que a resposta está certa
    e que a segunda chamada não perguntou outra vez."""

    def setUp(self):
        super().setUp()
        radar._TIPOS_DO_CORPUS = (None, [])
        radar.iniciar_corpus()
        self.idas = []
        self.liga_verdadeira = radar.liga_corpus

        def espia():
            self.idas.append(1)
            return self.liga_verdadeira()

        self.enterContext(unittest.mock.patch.object(radar, "liga_corpus", espia))

    def tearDown(self):
        radar._TIPOS_DO_CORPUS = (None, [])
        super().tearDown()

    _proximo = 1000

    def _poe(self, tipos):
        with self.liga_verdadeira() as c:
            for t in tipos:
                TestTiposDeProcedimentoGuardados._proximo += 1
                c.execute("INSERT INTO contratos (id, objecto, "
                          "tipo_procedimento) VALUES (?,?,?)",
                          (self._proximo, "x", t))

    def test_ordena_pelo_mais_comum_e_ignora_o_vazio(self):
        self._poe(["Ajuste direto", "Concurso público", "Ajuste direto",
                   "Ajuste direto", "", "Concurso público"])
        self.assertEqual(radar.tipos_de_procedimento(),
                         ["Ajuste direto", "Concurso público"])

    def test_a_segunda_chamada_nao_vai_ao_corpus(self):
        self._poe(["Ajuste direto"])
        radar.tipos_de_procedimento()
        antes = len(self.idas)
        radar.tipos_de_procedimento()
        radar.tipos_de_procedimento()
        self.assertEqual(len(self.idas), antes,
                         "foi ao corpus outra vez com o ficheiro na mesma")

    def test_o_corpus_a_mudar_desfaz_a_cache(self):
        self._poe(["Ajuste direto"])
        self.assertEqual(radar.tipos_de_procedimento(), ["Ajuste direto"])
        self._poe(["Concurso público", "Concurso público",
                   "Concurso público"])
        # o ficheiro mudou: o resultado tem de ser o novo, não o guardado
        self.assertEqual(radar.tipos_de_procedimento(),
                         ["Concurso público", "Ajuste direto"])

    def test_sem_corpus_devolve_lista_vazia_e_nao_rebenta(self):
        import os as _os
        radar.CORPUS = _os.path.join(self.pasta, "nao-existe.db")
        self.assertEqual(radar.tipos_de_procedimento(), [])


class TestDescontoDoDesfecho(unittest.TestCase):
    """O desfecho na ficha refaz a conta do B04, e por isso podia
    refazer o erro do B04: **num procedimento com lotes, cada linha
    traz o preço base do procedimento inteiro**, e dividir linha a
    linha compara um lote pequeno com a base toda — a média ingénua
    dava -18,9% no corpus. A regra é somar antes de dividir, e é o
    primeiro teste daqui.

    Os outros guardam as exclusões: sem base, base a variar entre
    lotes (aí a base é por lote e a semântica é outra) e soma acima da
    base. Nesses o número não se mostra, em vez de se mostrar errado.
    """

    def linha(self, base, contratual):
        return {"preco_base": base, "preco_contratual": contratual}

    def test_os_lotes_somam_antes_de_dividir(self):
        # tres lotes de 30 000 contra a base de 100 000 do procedimento:
        # 10% abaixo. Linha a linha dava 70%, tres vezes.
        lotes = [self.linha(100000.0, 30000.0) for _ in range(3)]
        desconto, base, fonte = radar.desconto_do_desfecho(lotes)
        self.assertAlmostEqual(desconto, 0.10)
        self.assertEqual(base, 100000.0)
        self.assertEqual(fonte, "corpus")

    def test_base_a_variar_entre_lotes_nao_da_desconto(self):
        # base por lote e nao do procedimento: outra semantica, e o
        # MAX() das bases nao e o tecto de nada
        desconto, _, _ = radar.desconto_do_desfecho(
            [self.linha(100000.0, 30000.0), self.linha(50000.0, 20000.0)])
        self.assertIsNone(desconto)

    def test_soma_acima_da_base_nao_da_desconto(self):
        # ruido do dump: 4 275 grupos assim no corpus inteiro
        desconto, _, _ = radar.desconto_do_desfecho(
            [self.linha(100000.0, 130000.0)])
        self.assertIsNone(desconto)

    def test_sem_base_no_dump_cai_para_a_do_anuncio_e_diz_que_caiu(self):
        # 5295/2014 e companhia: preco_base a zero no IMPIC. O anuncio
        # tem-no, e serve -- mas o ecra tem de dizer que a fonte e outra
        desconto, base, fonte = radar.desconto_do_desfecho(
            [self.linha(0.0, 90000.0)], base_do_anuncio=100000.0)
        self.assertAlmostEqual(desconto, 0.10)
        self.assertEqual(base, 100000.0)
        self.assertEqual(fonte, "anuncio")

    def test_sem_base_nenhuma_nao_inventa(self):
        desconto, base, _ = radar.desconto_do_desfecho(
            [self.linha(0.0, 90000.0)])
        self.assertIsNone(desconto)
        self.assertEqual(base, 0.0)

    def test_sem_linhas_nao_rebenta(self):
        self.assertEqual(radar.desconto_do_desfecho([]), (None, 0.0, "anuncio"))


class TestJanelasDeDatas(unittest.TestCase):
    """O varrimento histórico faz-se por janelas porque o `recolher()`
    só grava no fim de uma janela e porque a ordem do DR se desfaz nas
    páginas fundas (medido a 04/09/2026: com a janela 2015-2026,
    StartIndex 60 000 devolve 2019 e 120 000 devolve 2022).

    O que estes testes seguram é a cobertura: **os dois limites do
    filtro do DR são inclusivos**, por isso a janela seguinte tem de
    começar no dia a seguir. Um `-1` a mais e perde-se um dia por
    janela — 118 dias numa recolha de dez anos, silenciosamente.
    """

    def dias_cobertos(self, janelas):
        dias = set()
        for de, ate in janelas:
            d = datetime.datetime.strptime(de, "%Y-%m-%d").date()
            a = datetime.datetime.strptime(ate, "%Y-%m-%d").date()
            while d <= a:
                dias.add(d)
                d += datetime.timedelta(days=1)
        return dias

    def test_cobre_todos_os_dias_sem_buracos(self):
        janelas = radar.janelas_de_datas("2019-01-01", "2019-03-31", passo=30)
        cobertos = self.dias_cobertos(janelas)
        self.assertEqual(len(cobertos), 90)
        self.assertIn(datetime.date(2019, 1, 1), cobertos)
        self.assertIn(datetime.date(2019, 3, 31), cobertos)

    def test_as_janelas_nao_se_sobrepoem(self):
        janelas = radar.janelas_de_datas("2019-01-01", "2019-03-31", passo=30)
        soma = sum((datetime.datetime.strptime(a, "%Y-%m-%d")
                    - datetime.datetime.strptime(d, "%Y-%m-%d")).days + 1
                   for d, a in janelas)
        self.assertEqual(soma, len(self.dias_cobertos(janelas)))

    def test_do_mais_recente_para_o_mais_antigo(self):
        janelas = radar.janelas_de_datas("2019-01-01", "2019-03-31", passo=30)
        self.assertEqual(janelas[0][1], "2019-03-31")
        self.assertEqual(janelas[-1][0], "2019-01-01")

    def test_um_dia_so_da_uma_janela(self):
        self.assertEqual(radar.janelas_de_datas("2019-01-01", "2019-01-01"),
                         [("2019-01-01", "2019-01-01")])

    def test_passo_maior_do_que_o_intervalo_nao_o_parte(self):
        self.assertEqual(
            radar.janelas_de_datas("2019-01-01", "2019-01-10", passo=90),
            [("2019-01-01", "2019-01-10")])

    def test_dez_anos_dao_janelas_a_conta(self):
        janelas = radar.janelas_de_datas("2015-01-01", "2024-08-27", passo=30)
        self.assertEqual(len(self.dias_cobertos(janelas)), 3527)


class TestRecolherIntervalo(unittest.TestCase):
    """Numa recolha de horas, uma janela falhada não pode deitar fora o
    resto — e o que ficou por trazer tem de sair **nomeado**, porque a
    resposta a uma falha é voltar a correr o comando com essas datas.

    Separa-se a condição da espera, como manda a empresa: a `recolha`
    injecta-se, e verifica-se que cada janela foi pedida uma vez e que
    as falhadas voltam identificadas.
    """

    def test_pede_cada_janela_uma_vez_e_soma_os_novos(self):
        pedidas = []

        def recolha(cfg):
            pedidas.append((cfg["data_de"], cfg["data_ate"]))
            return True, "ok", 10

        novos, falhadas = radar.recolher_intervalo(
            {}, "2019-01-01", "2019-03-31", passo=30,
            avisar=lambda *_: None, recolha=recolha)
        self.assertEqual(pedidas,
                         radar.janelas_de_datas("2019-01-01", "2019-03-31", 30))
        self.assertEqual(len(pedidas), len(set(pedidas)))
        self.assertEqual(novos, 10 * len(pedidas))
        self.assertEqual(falhadas, [])

    def test_uma_janela_falhada_nao_para_as_outras_e_volta_nomeada(self):
        janelas = radar.janelas_de_datas("2019-01-01", "2019-03-31", 31)
        parte = janelas[1][0]            # a do meio, seja qual for

        def recolha(cfg):
            if cfg["data_de"] == parte:
                return False, "sem ligação ao DR: timeout", 0
            return True, "ok", 5

        novos, falhadas = radar.recolher_intervalo(
            {}, "2019-01-01", "2019-03-31", passo=31,
            avisar=lambda *_: None, recolha=recolha)
        self.assertEqual(len(falhadas), 1)
        self.assertEqual(falhadas[0][0], parte)
        self.assertIn("timeout", falhadas[0][2])
        self.assertEqual(novos, 5 * (len(janelas) - 1))   # as outras trouxeram

    def test_a_configuracao_da_empresa_nao_e_mexida(self):
        # o dict(cfg, ...) e uma copia: um data_de pendurado no cfg
        # verdadeiro estragava a recolha seguinte, que e a diaria
        cfg = {"dias_catchup": 15}
        radar.recolher_intervalo(cfg, "2019-01-01", "2019-01-10", passo=30,
                                 avisar=lambda *_: None,
                                 recolha=lambda c: (True, "ok", 0))
        self.assertEqual(cfg, {"dias_catchup": 15})


class TestGanhadoresDaLinha(unittest.TestCase):
    """04/09/2026: os três sítios que mostram «quem ganhou» faziam cada
    um o seu `zip(nomes, chaves)` sobre dois `group_concat`s. O das
    chaves vem **NULL** quando nenhum adjudicatário daquele contrato
    tem chave — e aí `"".split("|")` dá uma lista de UM, o zip trunca
    pelo mais curto, e um agrupamento de cinco aparecia com um nome só.
    Sem erro e sem aviso: só um ecrã com menos gente do que a verdade.

    No corpus verdadeiro as chaves estão cheias, por isso isto nunca
    apareceu — foi um teste do desfecho contra um corpus sem a migração
    que o expôs. É a regra da empresa: onde a documentação disser «em
    último recurso faz X», escreve-se o teste que força esse recurso.
    """

    def test_sem_chave_nenhuma_nao_perde_ninguem(self):
        linha = {"ganhou": "A|B|C|D|E", "ganhou_ch": None}
        self.assertEqual([n for _, n in radar.ganhadores_da_linha(linha)],
                         ["A", "B", "C", "D", "E"])
        self.assertEqual({ch for ch, _ in radar.ganhadores_da_linha(linha)},
                         {""})

    def test_com_chaves_emparelha_pela_ordem(self):
        linha = {"ganhou": "A|B", "ganhou_ch": "500|n:b"}
        self.assertEqual(radar.ganhadores_da_linha(linha),
                         [("500", "A"), ("n:b", "B")])

    def test_menos_chaves_do_que_nomes_nao_trunca(self):
        linha = {"ganhou": "A|B|C", "ganhou_ch": "500"}
        self.assertEqual(radar.ganhadores_da_linha(linha),
                         [("500", "A"), ("", "B"), ("", "C")])

    def test_sem_ganhadores_da_lista_vazia(self):
        self.assertEqual(
            radar.ganhadores_da_linha({"ganhou": None, "ganhou_ch": None}), [])


class TestDesfechoNaFicha(BaseTemporaria):
    """A ligação anúncio → contrato é por CHAVE (`n_anuncio` do dump do
    IMPIC = `ref` do radar), ao contrário dos homólogos, que são um
    palpite por termos do título. O que estes testes seguram:

    - que só vêm os contratos DESTE anúncio (um `LIKE` ou um prefixo
      trariam o 1/2026 ao pedir o 1/202, e o corpus tem 245 931 linhas
      com número de anúncio);
    - a regra do silêncio: um anúncio recente sem contrato não mostra
      caixa nenhuma, um antigo mostra — e é a mesma condição que decide
      a entrada «Desfecho» no índice da ficha. **Um chip do índice que
      salta para um bloco inexistente é a mesma mentira de um número
      que abre outra lista.**
    """

    def setUp(self):
        BaseTemporaria.setUp(self)
        self.enterContext(unittest.mock.patch.object(
            radar, "CORPUS", os.path.join(self.pasta, "ensaio-contratos.db")))
        radar.iniciar_corpus()

    def poe_anuncio(self, ref, data_pub, preco_base=""):
        with radar.liga() as c:
            c.execute("INSERT INTO anuncios (ref, titulo, url, data_pub, "
                      "preco_base) VALUES (?,?,?,?,?)",
                      (ref, "Aquisição de serviços", "https://x/" + ref,
                       data_pub, preco_base))
        with radar.liga() as c:
            return c.execute("SELECT * FROM anuncios WHERE ref=?",
                             (ref,)).fetchone()

    def poe_contrato(self, cid, n_anuncio, base, contratual, quem="Empresa"):
        with radar.liga_corpus() as c:
            c.execute("INSERT INTO contratos (id, ano, n_anuncio, objecto, "
                      "tipo_procedimento, data_celebracao, preco_base, "
                      "preco_contratual, prazo_execucao) "
                      "VALUES (?,?,?,?,?,?,?,?,?)",
                      (cid, 2026, n_anuncio, "Aquisição de serviços",
                       "Concurso público", "2026-02-10", base, contratual, 30))
            c.execute("INSERT INTO contrato_adjudicatario "
                      "(contrato_id, nif, nome) VALUES (?,?,?)",
                      (cid, "500000000", quem))

    def test_traz_so_os_contratos_deste_anuncio(self):
        self.poe_contrato(1, "1/2026", 100000.0, 90000.0)
        self.poe_contrato(2, "10/2026", 100000.0, 90000.0)
        self.poe_contrato(3, "", 100000.0, 90000.0)
        linhas = radar.desfecho_do_anuncio("1/2026")
        self.assertEqual([l["id"] for l in linhas], [1])

    def test_sem_corpus_nao_rebenta(self):
        radar.CORPUS = os.path.join(self.pasta, "nao-existe.db")
        self.assertEqual(radar.desfecho_do_anuncio("1/2026"), [])

    def test_anuncio_recente_sem_contrato_nao_desenha_caixa(self):
        self.poe_contrato(9, "99/2026", 100000.0, 90000.0)   # corpus nao vazio
        hoje = datetime.date.today().isoformat()
        a = self.poe_anuncio("1/2026", hoje)
        self.assertEqual(radar.desfecho_cx(a), "")

    def test_anuncio_antigo_sem_contrato_diz_que_nao_ha(self):
        self.poe_contrato(9, "99/2026", 100000.0, 90000.0)   # corpus nao vazio
        velho = (datetime.date.today()
                 - datetime.timedelta(days=radar.DIAS_ATE_CONTRATO + 1))
        a = self.poe_anuncio("1/2026", velho.isoformat())
        saiu = radar.desfecho_cx(a)
        self.assertIn("ainda sem contrato celebrado", saiu)
        self.assertIn("id='desfecho'", saiu)

    def test_o_indice_so_tem_desfecho_quando_a_caixa_existe(self):
        # a ancora e o bloco saem da MESMA condicao: se um dia se
        # separarem, o chip do indice salta para lado nenhum
        self.poe_contrato(9, "99/2026", 100000.0, 90000.0)   # corpus nao vazio
        hoje = datetime.date.today().isoformat()
        recente = self.poe_anuncio("1/2026", hoje)
        velho = self.poe_anuncio(
            "2/2026", (datetime.date.today()
                       - datetime.timedelta(days=radar.DIAS_ATE_CONTRATO + 1)
                       ).isoformat())
        cliente = radar.app.test_client()
        for a, tem in ((recente, False), (velho, True)):
            pagina = cliente.get("/anuncio/%s" % a["ref"].replace("/", "%2F"))
            saiu = pagina.data.decode("utf-8")
            self.assertEqual("href='#desfecho'" in saiu, tem, a["ref"])
            self.assertEqual("id='desfecho'" in saiu, tem, a["ref"])

    def test_um_contrato_nao_desenha_a_tabela_dos_lotes(self):
        # repetia os mesmos numeros do somario noutra forma
        self.poe_contrato(1, "1/2026", 100000.0, 90000.0)
        a = self.poe_anuncio("1/2026", "2026-01-05")
        saiu = radar.desfecho_cx(a)
        self.assertIn(radar.euros(90000.0), saiu)
        self.assertIn("10,0%", saiu)
        self.assertNotIn("tab-mercado", saiu)

    def test_varios_lotes_desenham_a_tabela_e_nao_repetem_quem_ganhou(self):
        for i in (1, 2, 3):
            self.poe_contrato(i, "1/2026", 100000.0, 30000.0, quem="Empresa")
        a = self.poe_anuncio("1/2026", "2026-01-05")
        saiu = radar.desfecho_cx(a)
        self.assertIn("tab-mercado", saiu)
        self.assertIn("Os 3 contratos", saiu)
        self.assertIn("10,0%", saiu)     # somados, nao 70% tres vezes
        # o mesmo adjudicatario ganhou os tres lotes: no somario aparece
        # uma vez, e nao "Empresa + Empresa + Empresa"
        somario = saiu.split("desfecho-som")[1].split("</div></div>")[0]
        self.assertEqual(somario.count(">Empresa<"), 1)

    def test_muitos_vencedores_contam_se_em_vez_de_se_listarem(self):
        # o 10011/2026 tem dez lotes e dez vencedores: a lista de nomes
        # no cartao era um paragrafo que empurrava os numeros para fora
        # do olho. Os nomes ficam na tabela, que aqui existe.
        for i in range(1, 6):
            self.poe_contrato(i, "1/2026", 100000.0, 10000.0,
                              quem="Empresa %d" % i)
        a = self.poe_anuncio("1/2026", "2026-01-05")
        saiu = radar.desfecho_cx(a)
        somario = saiu.split("desfecho-som")[1].split("</div></div>")[0]
        self.assertIn("5 adjudicatários", somario)
        self.assertNotIn("Empresa 1", somario)
        self.assertIn("Empresa 1", saiu)          # na tabela, sim

    def test_agrupamento_num_contrato_so_escreve_se_por_extenso(self):
        # sem tabela por baixo nao ha outro sitio onde os nomes apareçam:
        # contar aqui era esconder o unico facto que a caixa tinha
        self.poe_contrato(1, "1/2026", 100000.0, 90000.0)
        with radar.liga_corpus() as c:
            c.executemany("INSERT INTO contrato_adjudicatario "
                          "(contrato_id, nif, nome) VALUES (?,?,?)",
                          [(1, "60000000%d" % i, "Consorciada %d" % i)
                           for i in range(1, 5)])
        a = self.poe_anuncio("1/2026", "2026-01-05")
        saiu = radar.desfecho_cx(a)
        self.assertNotIn("adjudicatários", saiu)
        self.assertIn("Consorciada 4", saiu)


class TestTarefasEmFalta(unittest.TestCase):
    """O aviso vermelho «o radar não está a verificar sozinho». Até
    8/09/2026, fora do Windows `tarefas_em_falta()` devolvia vazio --
    «não há o que avisar» -- e era exactamente o modo de falha que o
    aviso existe para apanhar: parecer vivo sem recolher nada. Em Linux
    lê os temporizadores do systemd que o agendar.sh cria. A listagem é
    injectável: nada disto chama o systemctl. (O ramo do schtasks do
    Windows saiu a 14/09/2026, com o resto do Windows.)"""

    SYSTEMD = (
        "Tue 2026-09-08 17:00:00 WEST 4h left Tue 2026-09-08 09:00:12 WEST "
        "3h ago radar-17h.timer radar-verificar.service\n"
        "Wed 2026-09-09 09:00:00 WEST 20h left Tue 2026-09-08 09:00:12 WEST "
        "3h ago radar-09h.timer radar-verificar.service\n"
        "Mon 2026-09-14 08:00:00 WEST 5 days left - - "
        "radar-contratos.timer radar-contratos.service\n")
    def setUp(self):
        radar._TAREFAS_VISTAS = None
        self.chamadas = []

    def lista(self, saida):
        def listar(comando):
            self.chamadas.append(comando)
            return saida
        return listar

    def test_linux_com_os_dois_timers_nao_avisa(self):
        self.assertEqual(
            radar.tarefas_em_falta(self.lista(self.SYSTEMD), "linux"), [])
        self.assertEqual(self.chamadas[0][:2], ["systemctl", "--user"])

    def test_linux_sem_um_timer_diz_qual(self):
        so_um = self.SYSTEMD.replace("radar-17h.timer", "outro.timer")
        self.assertEqual(
            radar.tarefas_em_falta(self.lista(so_um), "linux"),
            ["radar-17h.timer"])

    def test_sistema_sem_agendador_conhecido_nao_inventa_aviso(self):
        self.assertEqual(
            radar.tarefas_em_falta(self.lista(""), "darwin"), [])
        self.assertEqual(self.chamadas, [])

    def test_comando_que_falha_nao_inventa_aviso(self):
        def rebenta(comando):
            raise OSError("sem systemctl")
        self.assertEqual(radar.tarefas_em_falta(rebenta, "linux"), [])

    def test_a_resposta_guarda_se_um_minuto(self):
        radar.tarefas_em_falta(self.lista(""), "linux")
        radar.tarefas_em_falta(self.lista(""), "linux")
        self.assertEqual(len(self.chamadas), 1)

    def test_o_aviso_do_painel_manda_correr_o_agendar_sh(self):
        onde, guiao = radar.como_agendar()
        self.assertEqual(guiao, "agendar.sh")
        self.assertIn("systemd", onde)


class TestAvisoDasTarefasNoPainel(BaseTemporaria):
    """O aviso chega mesmo ao HTML, com o nome da tarefa em falta e o
    guião certo -- e a lista de tarefas é a deste sistema, não a do
    Windows por defeito."""

    def test_pagina_mostra_o_aviso(self):
        with unittest.mock.patch.object(radar, "tarefas_em_falta",
                                        lambda: ["radar-17h.timer"]), \
                unittest.mock.patch.object(radar, "como_agendar",
                                           lambda: ("nos temporizadores do systemd",
                                                    "agendar.sh")):
            html_ = radar.app.test_client().get(radar.LISTA).get_data(as_text=True)
        self.assertIn("não está a verificar", html_)
        self.assertIn("radar-17h.timer", html_)
        self.assertIn("agendar.sh", html_)
        self.assertNotIn("Windows", html_.split("não está a verificar")[1][:300])


class TestContas(BaseTemporaria):
    """A porta do painel (docs/historico/ONLINE.md, etapa 1, 8/09/2026).

    Antes disto o painel atendia em 127.0.0.1 sem palavra-passe e o
    `tunel.sh` punha-o na internet tal como estava. E a armadilha que
    estes testes guardam: o cloudflared liga-se ao painel A PARTIR de
    127.0.0.1 -- so pelo IP, todos os visitantes do tunel eram locais e
    entravam pelo acesso livre.
    """
    FORA = {"REMOTE_ADDR": "203.0.113.7"}

    def setUp(self):
        super().setUp()
        import contas
        self.contas = contas
        # o config.json verdadeiro fica fora do alcance: um POST que grave
        # configuracao escreve num ficheiro da pasta temporaria
        self.enterContext(unittest.mock.patch.object(
            radar, "CONFIG", os.path.join(self.pasta, "config.json")))
        self.cfg = dict(radar.CONFIG_INICIAL, acesso_livre_local=True)
        self.enterContext(unittest.mock.patch.object(
            radar, "ler_config", lambda: dict(self.cfg)))
        self.cliente = radar.app.test_client()
        with radar.liga() as c:
            self.contas.criar_utilizador(c, "afonso@exemplo.pt",
                                         "senha-comprida", "Afonso")

    def entrar(self, cliente=None, **ambiente):
        cliente = cliente or radar.app.test_client()
        r = cliente.post("/entrar", data={"email": "afonso@exemplo.pt",
                                         "senha": "senha-comprida"},
                         environ_base=ambiente or self.FORA)
        return cliente, r

    def token_da_pagina(self, cliente):
        html_ = cliente.get("/", environ_base=self.FORA).get_data(as_text=True)
        m = re.search(r"<meta name=\"csrf\" content=\"([0-9a-f]+)\"", html_)
        return m.group(1) if m else ""

    # -- a criptografia

    def test_hash_verifica_e_nao_e_reversivel(self):
        h = self.contas.hash_senha("segredo-1")
        self.assertTrue(h.startswith("scrypt$"))
        self.assertNotIn("segredo", h)
        self.assertTrue(self.contas.verifica_senha("segredo-1", h))
        self.assertFalse(self.contas.verifica_senha("segredo-2", h))
        self.assertFalse(self.contas.verifica_senha("segredo-1", "lixo"))
        self.assertFalse(self.contas.verifica_senha("segredo-1", None))
        # dois hashes da mesma senha diferem (sal novo de cada vez)
        self.assertNotEqual(h, self.contas.hash_senha("segredo-1"))

    def test_senha_curta_e_recusada(self):
        with radar.liga() as c:
            with self.assertRaises(ValueError):
                self.contas.criar_utilizador(c, "x@y.pt", "curta")
            with self.assertRaises(ValueError):
                self.contas.criar_utilizador(c, "com espaco", "senha-comprida")
            # um nome simples serve: o Afonso quer "admin", nao um e-mail
            self.assertTrue(self.contas.criar_utilizador(c, "admin", "senha-comprida"))

    # -- sessoes

    def test_sessao_expira_e_desliza(self):
        t0 = datetime.datetime(2026, 9, 8, 10, 0, 0)
        with radar.liga() as c:
            token, u = self.contas.entrar(c, "afonso@exemplo.pt",
                                          "senha-comprida", agora=t0)
            self.assertTrue(token)
            self.assertEqual(u["nome"], "Afonso")
            # ao dia 29 ainda vale, e o uso empurra o fim para a frente
            dia29 = t0 + datetime.timedelta(days=29)
            self.assertTrue(self.contas.utilizador_da_sessao(c, token, dia29))
            dia58 = dia29 + datetime.timedelta(days=29)
            self.assertTrue(self.contas.utilizador_da_sessao(c, token, dia58))
            dia89 = dia58 + datetime.timedelta(days=31)
            self.assertIsNone(self.contas.utilizador_da_sessao(c, token, dia89))
            # e a linha expirada foi apagada ao ser encontrada
            self.assertEqual(self.contas.sessoes_de(c, u["id"]), [])

    def test_senha_errada_nao_abre_sessao_e_diz_o_mesmo_que_email_errado(self):
        with radar.liga() as c:
            t1, p1 = self.contas.entrar(c, "afonso@exemplo.pt", "errada-x")
            t2, p2 = self.contas.entrar(c, "ninguem@exemplo.pt", "senha-comprida")
        self.assertIsNone(t1)
        self.assertIsNone(t2)
        self.assertEqual(p1, p2)

    def test_trinco_ao_quinto_erro(self):
        t0 = datetime.datetime(2026, 9, 8, 10, 0, 0)
        with radar.liga() as c:
            for i in range(5):
                token, porque = self.contas.entrar(
                    c, "afonso@exemplo.pt", "errada", ip="1.2.3.4",
                    agora=t0 + datetime.timedelta(seconds=i))
                self.assertIsNone(token)
            self.assertNotIn("espera", porque)      # a quinta ainda responde
            # a sexta, com a senha CERTA, espera -- e diz quanto
            token, porque = self.contas.entrar(
                c, "afonso@exemplo.pt", "senha-comprida", ip="9.9.9.9",
                agora=t0 + datetime.timedelta(seconds=10))
            self.assertIsNone(token)
            self.assertIn("espera", porque)
            # por IP tambem: outro e-mail do mesmo IP fica preso
            token, porque = self.contas.entrar(
                c, "outro@exemplo.pt", "x", ip="1.2.3.4",
                agora=t0 + datetime.timedelta(seconds=10))
            self.assertIn("espera", porque)
            # passados os quinze minutos abre
            token, _ = self.contas.entrar(
                c, "afonso@exemplo.pt", "senha-comprida", ip="1.2.3.4",
                agora=t0 + datetime.timedelta(minutes=15, seconds=1))
            self.assertTrue(token)

    # -- a porta

    def test_de_fora_sem_sessao_vai_para_entrar(self):
        r = self.cliente.get(radar.LISTA + "?estado=novo", environ_base=self.FORA)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].startswith("/entrar?para="))
        self.assertIn("estado%3Dnovo", r.headers["Location"])
        # um POST de fora sem sessao e recusado, nao redireccionado
        r = self.cliente.post("/estado/1/novo", environ_base=self.FORA)
        self.assertEqual(r.status_code, 403)

    def test_acesso_livre_so_de_127001_e_sem_tunel_a_meio(self):
        local = {"REMOTE_ADDR": "127.0.0.1"}
        self.assertEqual(self.cliente.get("/", environ_base=local).status_code, 200)
        # o cloudflared liga-se de 127.0.0.1 -- mas traz o Host publico
        # e os cabecalhos de proxy, e qualquer um deles chega
        r = self.cliente.get("/", environ_base=local,
                             headers={"Host": "abc.trycloudflare.com"})
        self.assertEqual(r.status_code, 302)
        r = self.cliente.get("/", environ_base=local,
                             headers={"Cf-Connecting-Ip": "203.0.113.7"})
        self.assertEqual(r.status_code, 302)
        # X-Forwarded-For: o ProxyFix troca o IP e o pedido deixa de ser local
        r = self.cliente.get("/", environ_base=local,
                             headers={"X-Forwarded-For": "203.0.113.7"})
        self.assertEqual(r.status_code, 302)
        # e com o interruptor desligado nem o local entra
        self.cfg["acesso_livre_local"] = False
        self.assertEqual(self.cliente.get("/", environ_base=local).status_code, 302)

    def test_acesso_livre_e_o_unico_utilizador(self):
        with radar.app.test_request_context("/", environ_base={"REMOTE_ADDR": "127.0.0.1"}):
            radar.porta_de_entrada()
            self.assertEqual(radar.quem_sou(), "Afonso")
        # com mais utilizadores o acesso livre e o primeiro admin
        # (14/09/2026: a primeira conta de tester deixou o computador do
        # Afonso "sem conta ainda"); um segundo admin nao o destrona
        with radar.liga() as c:
            self.contas.criar_utilizador(c, "tester", "senha-comprida", papel="tester")
            self.contas.criar_utilizador(c, "outro@exemplo.pt", "senha-comprida")
        with radar.app.test_request_context("/", environ_base={"REMOTE_ADDR": "127.0.0.1"}):
            radar.porta_de_entrada()
            self.assertEqual(radar.quem_sou(), "Afonso")
            self.assertTrue(radar.sou_admin())
        # varias contas e nenhum admin: nao ha ninguem (uma so conta,
        # seja qual for, continua a ser "o unico")
        with radar.liga() as c:
            self.contas.criar_utilizador(c, "tester2", "senha-comprida", papel="tester")
            c.execute("UPDATE utilizadores SET papel='tester' WHERE papel='admin'")
        with radar.app.test_request_context("/", environ_base={"REMOTE_ADDR": "127.0.0.1"}):
            radar.porta_de_entrada()
            self.assertEqual(radar.quem_sou(), "")

    def test_entrar_abre_sessao_e_o_cookie_e_httponly(self):
        cliente, r = self.entrar()
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers["Location"], "/")
        cookie = r.headers.get("Set-Cookie", "")
        self.assertIn("sessao=", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        # com a sessao, o pedido de fora passa e a pagina diz quem e
        html_ = cliente.get("/", environ_base=self.FORA).get_data(as_text=True)
        self.assertIn("Afonso", html_)
        self.assertIn("action='/sair'", html_)

    def test_para_so_aceita_caminhos_da_aplicacao(self):
        for para, esperado in (("/quadro", "/quadro"), ("//mal.pt/x", "/"),
                               ("https://mal.pt", "/"), ("", "/")):
            with self.subTest(para=para):
                cliente = radar.app.test_client()
                r = cliente.post("/entrar", data={"email": "afonso@exemplo.pt",
                                                 "senha": "senha-comprida",
                                                 "para": para},
                                 environ_base=self.FORA)
                self.assertEqual(r.headers["Location"], esperado)

    def test_senha_errada_no_ecra_fica_no_ecra(self):
        r = self.cliente.post("/entrar", data={"email": "afonso@exemplo.pt",
                                              "senha": "errada-mesmo"},
                              environ_base=self.FORA)
        self.assertEqual(r.status_code, 200)
        html_ = r.get_data(as_text=True)
        self.assertIn("errados", html_)
        self.assertIn("afonso@exemplo.pt", html_)     # o e-mail volta preenchido
        self.assertNotIn("Set-Cookie", r.headers)

    def test_sem_conta_o_ecra_diz_o_comando(self):
        with radar.liga() as c:
            c.execute("DELETE FROM utilizadores")
        html_ = self.cliente.get("/entrar", environ_base=self.FORA).get_data(as_text=True)
        self.assertIn("--criar-utilizador", html_)

    def test_sair_de_todos_mata_a_outra_sessao(self):
        a, _ = self.entrar()
        b, _ = self.entrar()
        self.assertEqual(b.get("/", environ_base=self.FORA).status_code, 200)
        r = a.post("/sair-de-todos", data={"csrf": self.token_da_pagina(a)},
                   environ_base=self.FORA)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(b.get("/", environ_base=self.FORA).status_code, 302)
        self.assertEqual(a.get("/", environ_base=self.FORA).status_code, 302)

    def test_sair_invalida_de_imediato(self):
        a, _ = self.entrar()
        a.post("/sair", data={"csrf": self.token_da_pagina(a)}, environ_base=self.FORA)
        self.assertEqual(a.get("/", environ_base=self.FORA).status_code, 302)

    # -- csrf

    def test_todas_as_rotas_post_recusam_sem_token(self):
        """Percorre o app.url_map: uma rota POST nova nao escapa."""
        cliente, _ = self.entrar()
        rotas = sorted(r.rule for r in radar.app.url_map.iter_rules()
                       if "POST" in r.methods and r.rule not in ("/entrar",))
        self.assertGreater(len(rotas), 15)
        for regra in rotas:
            caminho = re.sub(r"<[^>]*>", "1", regra)
            with self.subTest(rota=regra):
                r = cliente.post(caminho, data={"x": "1"}, environ_base=self.FORA)
                self.assertEqual(r.status_code, 403)
        # A outra metade -- com o token passa -- so em rotas inofensivas.
        # A primeira versao percorria todas com o token: o /alertas/email
        # gravou o config.json VERDADEIRO com os valores de origem, e o
        # /verificar foi a rede. Uma rota com efeitos so se testa isolada.
        for caminho in ("/estado/1/novo", "/responsavel/1"):
            r = cliente.post(caminho, data={"csrf": self.token_da_pagina(cliente)},
                             environ_base=self.FORA)
            self.assertNotEqual(r.status_code, 403, caminho)

    def test_os_formularios_da_pagina_levam_o_token(self):
        cliente, _ = self.entrar()
        html_ = cliente.get("/", environ_base=self.FORA).get_data(as_text=True)
        token = self.token_da_pagina(cliente)
        self.assertTrue(token)
        formas = re.findall(r"<form\b[^>]*method=['\"]post['\"][^>]*>", html_, re.I)
        self.assertGreater(len(formas), 0)
        for f in formas:
            self.assertIn("name='csrf' value='%s'" % token,
                          html_[html_.index(f):html_.index(f) + len(f) + 120])
        # no acesso livre nao ha token, e os formularios seguem sem ele
        html_ = self.cliente.get("/", environ_base={"REMOTE_ADDR": "127.0.0.1"}).get_data(as_text=True)
        self.assertNotIn("name='csrf'", html_)

    def test_o_token_e_o_da_sessao_e_o_json_do_quadro_leva_o_cabecalho(self):
        a, _ = self.entrar()
        b, _ = self.entrar()
        token_de_a = self.token_da_pagina(a)
        self.assertNotEqual(token_de_a, self.token_da_pagina(b))
        r = b.post("/quadro/mover", json={"ref": "x", "fase_id": "1"},
                   headers={"X-CSRF": token_de_a}, environ_base=self.FORA)
        self.assertEqual(r.status_code, 403)
        r = b.post("/quadro/mover", json={"ref": "x", "fase_id": "1"},
                   headers={"X-CSRF": self.token_da_pagina(b)}, environ_base=self.FORA)
        self.assertNotEqual(r.status_code, 403)

    def test_no_acesso_livre_um_post_de_outro_sitio_e_recusado(self):
        local = {"REMOTE_ADDR": "127.0.0.1"}
        r = self.cliente.post("/estado/1/novo", environ_base=local,
                              headers={"Origin": "https://mal.pt"})
        self.assertEqual(r.status_code, 403)
        # o Referer com 127.0.0.1 e o Host com localhost sao a mesma empresa
        r = self.cliente.post("/estado/1/novo", environ_base=local,
                              headers={"Referer": "http://127.0.0.1:8765/?estado=novo"})
        self.assertNotEqual(r.status_code, 403)

    # -- o arranque

    def test_arranque_recusa_porta_aberta_com_acesso_livre(self):
        pode, porque = radar.arranque_permitido({"acesso_livre_local": True}, "0.0.0.0")
        self.assertFalse(pode)
        self.assertIn("acesso_livre_local", porque)
        self.assertTrue(radar.arranque_permitido({"acesso_livre_local": True}, "127.0.0.1")[0])
        self.assertTrue(radar.arranque_permitido({"acesso_livre_local": False}, "0.0.0.0")[0])

    def test_o_cookie_quem_e_a_rota_sou_deixaram_de_existir(self):
        self.assertEqual(self.cliente.post("/sou", data={"nome": "X"},
                                           environ_base={"REMOTE_ADDR": "127.0.0.1"}).status_code, 404)
        html_ = self.cliente.get("/", environ_base={"REMOTE_ADDR": "127.0.0.1"}).get_data(as_text=True)
        self.assertNotIn("quem está a trabalhar?", html_)


class TestEnderecoPublico(unittest.TestCase):
    """Os links do e-mail diziam 127.0.0.1:8765 mesmo com o painel em
    radargov.pt: so abriam neste computador."""

    def test_vazio_e_o_local(self):
        self.assertEqual(radar.endereco_do_painel({}), radar.LOCAL)
        self.assertEqual(radar.endereco_do_painel({"endereco_publico": "  "}), radar.LOCAL)

    def test_publico_sem_barra_no_fim_e_com_https_por_omissao(self):
        self.assertEqual(radar.endereco_do_painel({"endereco_publico": "https://radargov.pt/"}),
                         "https://radargov.pt")
        self.assertEqual(radar.endereco_do_painel({"endereco_publico": "radargov.pt"}),
                         "https://radargov.pt")

    def test_a_ligacao_do_email_usa_o_publico(self):
        antigo = radar.ler_config
        radar.ler_config = lambda: dict(radar.CONFIG_INICIAL, endereco_publico="https://radargov.pt")
        try:
            self.assertEqual(radar._em_ligacao("1/2026"), "https://radargov.pt/anuncio/1%2F2026")
        finally:
            radar.ler_config = antigo



class TestListaRecolhidaETeclado(BaseTemporaria):
    """UX-Auditoria (2/09/2026), decididos pelo Afonso a 8/09/2026: a
    lista abria com 60% do ecrã em filtros, e não havia teclado.

    Sobre uma base temporária (14/09/2026): pediam a página à base
    verdadeira, e num computador sem radar.db davam 500."""

    def setUp(self):
        super().setUp()
        self.cliente = radar.app.test_client()

    def test_o_painel_dos_filtros_nao_se_lembra_de_ter_ficado_aberto(self):
        """A memória em `localStorage` desfazia o recolhimento (16/09/2026,
        fase 5).

        Lembrava-se para sempre e em todas as abas: bastava filtrar uma
        vez, num dia qualquer, para a lista abrir com o painel aberto
        todos os dias a partir daí. **Medido na instalação dele: com a
        marca posta o primeiro cartão começava aos 409px, e sem ela aos
        284** — 125px, mais do que um cartão inteiro, por uma marca que
        ninguém sabia que tinha.

        O sinal certo é o do servidor, e está no teste a seguir: o painel
        abre quando HÁ filtro aplicado. Uma memória por cima disso nunca
        ajuda — só desfaz o recolhimento que a UX-Auditoria pediu, que
        existia precisamente porque a lista abria com 60% do ecrã em
        filtros. É a mesma razão por que o «?» do título também não tem
        memória (fase 2).
        """
        self.assertNotIn("radar-filtros-abertos", radar.LISTA_JS)
        self.assertNotIn("getElementById('painel-filtros')", radar.LISTA_JS)

    def test_filtros_recolhidos_sem_filtro_e_abertos_com_filtro(self):
        html_ = self.cliente.get(radar.LISTA).get_data(as_text=True)
        self.assertIn("<details class='painel-filtros' id='painel-filtros'>", html_)
        html_ = self.cliente.get(radar.LISTA + "?cpv=72000000").get_data(as_text=True)
        self.assertIn("<details class='painel-filtros' id='painel-filtros' open>", html_)
        # O resumo do filtro fica na linha, para se saber o que está
        # posto. Recorta-se o <summary> DOS FILTROS e não o primeiro da
        # página: desde 16/09/2026 há o «?» do título antes dele
        # (fase 2 do docs/design.md), e um split pelo primeiro
        # "</summary>" passou a medir o título.
        dos_filtros = html_.split("id='painel-filtros' open>")[1]
        self.assertIn("CPV 72000000", dos_filtros.split("</summary>")[0])

    def test_os_blocos_continuam_la_dentro_e_os_guardados_sairam(self):
        html_ = self.cliente.get(radar.LISTA).get_data(as_text=True)
        dentro = html_.split("<details class='painel-filtros'")[1].split("</details>\n")[0]
        self.assertIn("class='cx filtros'", dentro)
        # 13/09/2026: a caixa "Filtros guardados" saiu das listas; o que
        # era guardar um filtro passou a ser o Interesse e os alertas
        self.assertNotIn("Filtros guardados", html_)
        self.assertNotIn("/filtros/guardar", html_)

    def test_o_teclado_esta_na_lista_e_diz_se(self):
        html_ = self.cliente.get(radar.LISTA).get_data(as_text=True)
        self.assertIn("class='teclas'", html_)
        self.assertIn("keydown", radar.LISTA_JS)
        for tecla in ("'j'", "'k'", "'i'", "'a'", "'Enter'"):
            self.assertIn("e.key === " + tecla, radar.LISTA_JS)
        # com o foco num campo de texto as teclas escrevem, não triam
        self.assertIn("t.tagName === 'INPUT'", radar.LISTA_JS)
        self.assertIn(".item.foco{", radar.CSS)


class TestEssencialNumaFrase(unittest.TestCase):
    """O «essencial» de um por ver sem peças tinha 8 linhas em 12 a
    dizer «só consta das peças»: saem para uma frase, agrupadas pela
    razão, para continuar a dizer ONDE cada campo está."""

    def test_agrupa_por_razao_e_mantem_a_ordem(self):
        saiu = radar.frase_dos_campos_em_falta([
            ("só consta do Programa de Concurso", "Preço anormalmente baixo"),
            ("o anúncio não indica", "Duração do contrato"),
            ("só consta do Caderno de Encargos", "Equipa"),
            ("só consta do Programa de Concurso", "Documentos que constituem a proposta"),
        ])
        self.assertIn("4 campos sem valor aqui", saiu)
        self.assertIn("<b>só consta do Programa de Concurso</b>: Preço anormalmente baixo, "
                      "Documentos que constituem a proposta", saiu)
        self.assertLess(saiu.index("Programa"), saiu.index("não indica"))
        self.assertLess(saiu.index("não indica"), saiu.index("Caderno"))
        self.assertIn("href='#pecas'", saiu)

    def test_singular_e_vazio(self):
        self.assertIn("1 campo sem valor", radar.frase_dos_campos_em_falta([("x", "Equipa")]))
        self.assertEqual(radar.frase_dos_campos_em_falta([]), "")

    def test_escapa(self):
        saiu = radar.frase_dos_campos_em_falta([("<b>", "A & B")])
        self.assertIn("&lt;b&gt;", saiu)
        self.assertIn("A &amp; B", saiu)



class TestConfiguracoes(BaseTemporaria):
    """O menu de configurações (docs/historico/ONLINE.md, etapa 2,
    8/09/2026): o que estava no separador Alertas, no config.json à mão
    e em cinco ficheiros de texto passa a sete secções, cada uma um
    formulário que grava uma coisa."""

    def setUp(self):
        super().setUp()
        self.enterContext(unittest.mock.patch.object(
            radar, "CONFIG", os.path.join(self.pasta, "config.json")))
        # as chaves e as capturas escrevem-se em BASE_DIR: aponta-se para
        # a pasta temporaria, senao o teste gravava ficheiros na pasta real
        self.enterContext(unittest.mock.patch.object(radar, "BASE_DIR", self.pasta))
        self.cliente = radar.app.test_client()

    def test_as_nove_seccoes_abrem_e_as_rotas_antigas_redireccionam(self):
        # nove desde 13/09/2026 (Indicadores entrou), pela ordem do
        # documento do Afonso: o que e de quem usa primeiro, o do sistema
        # depois, marcado como so de admin
        self.assertEqual([c for c, _, _, _, _ in radar.SECCOES_CONFIG],
                         ["conta", "interesse", "alertas", "importar",
                          "indicadores", "capturas", "recolha", "leitura", "copias"])
        self.assertEqual([c for c, _, _, so_admin, _ in radar.SECCOES_CONFIG
                          if so_admin],
                         ["indicadores", "capturas", "recolha", "leitura", "copias"])
        # A quinta coluna diz se a seccao GRAVA alguma coisa (16/09/2026,
        # fase 5). Os Indicadores nao gravam nada -- zero campos, nove
        # blocos de numeros -- e estavam debaixo de um subtitulo que
        # prometia "cada seccao grava so o que mostra". O subtitulo
        # perdeu essa metade, que era falsa para eles.
        self.assertEqual([c for c, _, _, _, grava in radar.SECCOES_CONFIG
                          if not grava], ["indicadores"])
        for seccao, _, _, _, _ in radar.SECCOES_CONFIG:
            with self.subTest(seccao=seccao):
                r = self.cliente.get("/configuracoes/" + seccao)
                self.assertEqual(r.status_code, 200)
                self.assertIn("class='conf-indice'", r.get_data(as_text=True))
        r = self.cliente.get("/alertas?aviso=x")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers["Location"], "/configuracoes/alertas?aviso=x")
        r = self.cliente.get("/alertas/interesse")
        self.assertEqual(r.headers["Location"], "/configuracoes/interesse")
        self.assertEqual(self.cliente.get("/configuracoes").headers["Location"],
                         "/configuracoes/conta")
        self.assertEqual(self.cliente.get("/indicadores").headers["Location"],
                         "/configuracoes/indicadores")

    def test_a_seccao_que_so_le_esta_apartada_e_o_subtitulo_nao_mente(self):
        """Os **Indicadores não gravam nada** — zero campos de formulário,
        nove blocos de números — e estavam debaixo de um subtítulo que
        prometia «cada secção grava só o que mostra».

        Uma página de leitura num menu de afinação, com o ecrã a dizer o
        contrário do que ela faz. Vieram da barra a 13/09 e o sítio
        serve; o que estava errado era chamar-lhes configuração. Ficam
        apartadas por um risco, no fim do menu, e o subtítulo perdeu a
        metade falsa.
        """
        corpo = self.cliente.get("/configuracoes/conta").get_data(as_text=True)
        indice = corpo.split("class='conf-indice'")[1].split("</nav>")[0]
        self.assertIn("so-le", indice)
        # e é a última do menu, não uma do meio
        self.assertTrue(indice.rstrip().endswith("</a>"))
        self.assertLess(indice.index("conta"), indice.index("so-le"))
        # o subtítulo perdeu a metade que era falsa
        self.assertNotIn("grava só o que mostra", corpo)
        self.assertIn("Dizer ao radar como quero que ele trabalhe", corpo)

    def test_as_notas_dos_campos_ficam_onde_estao(self):
        """O critério da §9 do `docs/design.md` **não** se aplica aqui do
        mesmo modo: numa página de configuração o texto está ao lado do
        controlo que governa, e é no momento de mexer no controlo que ele
        faz falta. Não é a página a descrever-se — é o campo a dizer o
        que faz, e uma avisa de uma coisa que não se adivinha.
        """
        corpo = self.cliente.get("/configuracoes/alertas").get_data(as_text=True)
        # não é a página a descrever-se: é o campo a avisar de uma coisa
        # que não se adivinha antes de o preencher
        self.assertIn("não avisam de nada", corpo)
        self.assertIn("Um por dia, a partir da hora marcada", corpo)

    def test_recolha_grava_e_rele_sem_perder_o_resto(self):
        radar.gravar_config({"interesse_cpv": "72000000", "email": {"para": "x@y.pt"}})
        r = self.cliente.post("/configuracoes/recolha", data={
            "horas": "08:30, 18:00", "dias_catchup": "10", "detalhe_dias": "90",
            "detalhes_por_volta": "50", "relidos_por_volta": "5",
            "vortal_preliminares": "1"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("guardada", r.headers["Location"])
        cfg = radar.ler_config()
        self.assertEqual(cfg["horas_verificacao"], ["08:30", "18:00"])
        self.assertEqual(cfg["detalhe_dias"], 90)
        self.assertTrue(cfg["vortal_preliminares"])
        self.assertFalse(cfg["recuperar_slot_falhado"])     # a caixa nao veio
        # o que a seccao nao mostra fica como estava
        self.assertEqual(cfg["interesse_cpv"], "72000000")
        self.assertEqual(cfg["email"]["para"], "x@y.pt")
        # e o formulario rele o que gravou
        html_ = self.cliente.get("/configuracoes/recolha").get_data(as_text=True)
        self.assertIn("value='08:30, 18:00'", html_)
        # e fica no historico, com o antes e o depois
        with radar.liga() as c:
            regs = [r_["detalhe"] for r_ in c.execute(
                "SELECT detalhe FROM historico WHERE accao='configuração'")]
        self.assertTrue(any(d.startswith("detalhe_dias: 60 → 90") for d in regs), regs)

    def test_validacao_recusa_e_nao_grava(self):
        antes = radar.ler_config()["detalhe_dias"]
        for dados, frase in (
                ({"horas": "25:00"}, "não é uma hora"),
                ({"horas": "09:00", "dias_catchup": "x"}, "não é um número"),
                ({"horas": "09:00", "dias_catchup": "1", "detalhe_dias": "0"}, "vai de 1"),
                ({"horas": ""}, "pelo menos uma hora")):
            with self.subTest(dados=dados):
                base = {"dias_catchup": "15", "detalhe_dias": "60",
                        "detalhes_por_volta": "40", "relidos_por_volta": "25"}
                base.update(dados)
                r = self.cliente.post("/configuracoes/recolha", data=base)
                self.assertEqual(r.status_code, 302)
                self.assertIn(frase, unquote_plus(r.headers["Location"]))
        self.assertEqual(radar.ler_config()["detalhe_dias"], antes)

    def test_um_segredo_nunca_vai_para_o_config(self):
        with self.assertRaises(ValueError):
            radar.gravar_config_registado({"groq_api_key": "abc"})
        with self.assertRaises(ValueError):
            radar.gravar_config_registado({"email_senha": "abc"})
        self.assertNotIn("groq_api_key", open(radar.CONFIG, encoding="utf-8").read()
                         if os.path.exists(radar.CONFIG) else "")

    def test_a_chave_grava_no_ficheiro_e_por_variavel_nao_se_edita(self):
        r = self.cliente.post("/configuracoes/leitura", data={
            "fornecedor_pecas": "nvidia", "modelo_groq": "", "modelo_nvidia": "m-x",
            "chave_nvidia": "nv-123"})
        self.assertEqual(r.status_code, 302)
        cfg = radar.ler_config()
        self.assertEqual(cfg["fornecedor_pecas"], "nvidia")
        self.assertEqual(cfg["modelos_pecas"]["nvidia"], "m-x")
        with open(os.path.join(self.pasta, "nvidia_API_KEY.txt"), encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "nv-123")
        self.assertNotIn("nv-123", open(radar.CONFIG, encoding="utf-8").read())
        # por variavel de ambiente: o ecra di-lo e nao ha campo
        with unittest.mock.patch.dict(os.environ, {"NVIDIA_API_KEY": "por-variavel"}):
            html_ = self.cliente.get("/configuracoes/leitura").get_data(as_text=True)
            self.assertIn("definida pela variável NVIDIA_API_KEY", html_)
            self.assertNotIn("name='chave_nvidia'", html_)
            self.cliente.post("/configuracoes/leitura", data={"chave_nvidia": "outra"})
        with open(os.path.join(self.pasta, "nvidia_API_KEY.txt"), encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "nv-123")     # nao escreveu por cima
        # fornecedor desconhecido e recusado
        r = self.cliente.post("/configuracoes/leitura", data={"fornecedor_pecas": "xpto"})
        self.assertIn("desconhecido", unquote_plus(r.headers["Location"]))

    def test_uma_captura_invalida_nao_toca_no_ficheiro(self):
        caminho = os.path.join(self.pasta, "curl_DR.txt")
        with open(caminho, "w", encoding="utf-8") as f:
            f.write("curl 'https://x' -H 'a: b' --data-raw 'c'\n")
        r = self.cliente.post("/configuracoes/capturas",
                              data={"qual": "curl_DR", "texto": "isto nao e um curl"})
        self.assertIn("gravei", unquote_plus(r.headers["Location"]))
        with open(caminho, encoding="utf-8") as f:
            self.assertIn("--data-raw 'c'", f.read())
        # a da pesquisa sem corpo tambem nao
        r = self.cliente.post("/configuracoes/capturas",
                              data={"qual": "curl_DR", "texto": "curl 'https://x' -H 'a: b'"})
        self.assertIn("corpo", unquote_plus(r.headers["Location"]))
        # uma valida grava
        r = self.cliente.post("/configuracoes/capturas", data={
            "qual": "curl_detalhe", "texto": "curl 'https://y' -H 'k: v'"})
        self.assertIn("gravada", unquote_plus(r.headers["Location"]))
        with open(os.path.join(self.pasta, "curl_detalhe.txt"), encoding="utf-8") as f:
            self.assertIn("https://y", f.read())

    def test_copias_grava_e_lista(self):
        r = self.cliente.post("/configuracoes/copias", data={
            "copia_de_seguranca": "1", "copias_a_guardar": "3"})
        self.assertEqual(r.status_code, 302)
        cfg = radar.ler_config()
        self.assertEqual(cfg["copias_a_guardar"], 3)
        self.assertFalse(cfg["triagem_no_git"])
        r = self.cliente.post("/configuracoes/copias", data={"copias_a_guardar": "0"})
        self.assertIn("vai de 1", unquote_plus(r.headers["Location"]))

    def test_remetente_grava_a_senha_no_ficheiro_e_nao_no_config(self):
        r = self.cliente.post("/alertas/remetente", data={
            "de": "radar@gmail.com", "servidor": "smtp.gmail.com", "porta": "587",
            "senha": "segredo-do-email"})
        self.assertEqual(r.headers["Location"], "/configuracoes/alertas?aviso=Conta+que+envia+guardada.")
        cfg = radar.ler_config()
        self.assertEqual(cfg["email"]["de"], "radar@gmail.com")
        self.assertEqual(cfg["email"]["porta"], 587)
        self.assertNotIn("segredo", open(radar.CONFIG, encoding="utf-8").read())
        with open(os.path.join(self.pasta, "email_senha.txt"), encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "segredo-do-email")
        # sem senha no formulario o ficheiro fica como esta
        self.cliente.post("/alertas/remetente", data={
            "de": "radar@gmail.com", "servidor": "smtp.gmail.com", "porta": "465"})
        with open(os.path.join(self.pasta, "email_senha.txt"), encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "segredo-do-email")

    def test_conta_muda_a_palavra_passe_com_a_actual(self):
        # 13/09/2026: o "nome a mostrar" e a nota da consola sairam do
        # ecra; o formulario e so a palavra-passe
        import contas
        with radar.liga() as c:
            contas.criar_utilizador(c, "admin", "senha-comprida", "Afonso")
        html_ = self.cliente.get("/configuracoes/conta").get_data(as_text=True)
        self.assertNotIn("Nome a mostrar", html_)
        self.assertNotIn("--criar-utilizador", html_)
        # pelo acesso livre local o utilizador e o unico
        r = self.cliente.post("/configuracoes/conta", data={
            "actual": "errada", "nova": "nova-senha-1", "outra": "nova-senha-1"})
        self.assertIn("actual", unquote_plus(r.headers["Location"]))
        r = self.cliente.post("/configuracoes/conta", data={
            "actual": "senha-comprida", "nova": "nova-senha-1", "outra": "nova-senha-2"})
        self.assertIn("iguais", unquote_plus(r.headers["Location"]))
        r = self.cliente.post("/configuracoes/conta", data={
            "actual": "senha-comprida", "nova": "nova-senha-1", "outra": "nova-senha-1"})
        self.assertIn("mudada", r.headers["Location"])
        with radar.liga() as c:
            token, _ = contas.entrar(c, "admin", "nova-senha-1")
        self.assertTrue(token)



class TestResumoDosLotes(unittest.TestCase):
    """Os lotes, desenhados a 8/09/2026 (decisão do Afonso a 2/09: um
    cartão por anúncio, mas a dizer a que lotes fomos; no fim separam-se).
    O caso real é o 1947/2026: três lotes, L1 perdido, L2 ganho, L3
    perdido, e um só negócio «Won» no Zoho que não decide lote nenhum."""
    LOTES = [{"n": 1, "id": "L1", "descricao": "Pilar 4 - L1", "preco_base": "109.065,60 EUR"},
             {"n": 2, "id": "L2", "descricao": "Pilar 4 - L2", "preco_base": "436.262,40 EUR"},
             {"n": 3, "id": "L3", "descricao": "Pilar 4 - L3", "preco_base": "54.532,80 EUR"}]
    EMPRESA = [{"lote": 1, "status": "Perdido", "zoho_fase": "Won", "valor_proposta": 54432.0, "lugar": 3},
            {"lote": 2, "status": "Ganho", "zoho_fase": None, "valor_proposta": 169344.0, "lugar": 1},
            {"lote": 3, "status": "Perdido", "zoho_fase": None, "valor_proposta": 46368.0, "lugar": 2}]

    def test_o_caso_real_lote_a_lote(self):
        r = radar.resumo_dos_lotes(self.LOTES, self.EMPRESA)
        self.assertEqual([l["estado"] for l in r["lotes"]], ["perdido", "ganho", "perdido"])
        self.assertEqual(r["fomos"], [1, 2, 3])
        self.assertEqual(r["por_estado"], {"perdido": [1, 3], "ganho": [2]})
        self.assertIsNone(r["conjunto"])
        # o Zoho «Won» no L1 não o faz ganho: é o Excel que manda num lote
        self.assertEqual(r["lotes"][0]["lugar"], 3)
        self.assertEqual(radar.frase_dos_lotes(r), "fomos a todos os 3 lotes")

    def test_a_alguns_e_a_nenhum(self):
        r = radar.resumo_dos_lotes(self.LOTES, self.EMPRESA[1:2])
        self.assertEqual(r["fomos"], [2])
        self.assertEqual(radar.frase_dos_lotes(r), "fomos a 1 dos 3 lotes")
        # (as etiquetas por lote, `chips_dos_lotes()`, saíram a
        # 15/09/2026 com o cartão do quadro; o que a ficha mostra hoje é
        # a tabela dos lotes, e isso tem teste próprio em
        # TestLotesNaEscadaENaFicha)
        self.assertEqual(r["por_estado"], {"ganho": [2]})
        r = radar.resumo_dos_lotes(self.LOTES, [])
        self.assertEqual(r["fomos"], [])
        self.assertEqual(radar.frase_dos_lotes(r), "3 lotes; sem registo de a que fomos")

    def test_o_conjunto_nao_e_um_lote(self):
        # #23 e #26 (3/09/2026): o preço da linha é a soma — empresa.lote = 0
        r = radar.resumo_dos_lotes(self.LOTES[:2], [{"lote": 0, "status": "Perdido",
                                                    "zoho_fase": "Lost"}])
        self.assertEqual(r["fomos"], [])
        self.assertTrue(r["conjunto"])
        self.assertEqual(radar.frase_dos_lotes(r), "fomos ao conjunto dos 2 lotes")
        self.assertEqual(empresa.estado_do_lote(r["conjunto"]), "perdido")

    def test_sem_lotes_e_none(self):
        self.assertIsNone(radar.resumo_dos_lotes([], self.EMPRESA))
        self.assertEqual(radar.frase_dos_lotes(None), "")
        self.assertEqual(radar.lotes_de({"lotes": "não é json"}), [])


class TestLotesNaEscadaENaFicha(BaseTemporaria):
    """A separação no fim, que era um truque e passou a ser o modelo.

    O pedido dele, a 02/09/2026: «um cartão por anúncio, mas os cartões
    que têm lotes devem identificar a que lotes fomos e se fomos a
    todos, e no final, perdido ou ganho, separam-se os cartões». Até
    15/09/2026 isso fazia-se com um **cartão separado** montado a partir
    do registo do Excel -- não se arrastava, não tinha formulários, e a
    granularidade vinha toda de fora do painel.

    Com uma proposta por lote (D3), a separação deixa de precisar de
    truque: cada lote é a sua proposta, com o seu estado, e cai sozinho
    na coluna dele -- arrastável e editável como qualquer outro cartão.
    O bloco dos lotes na ficha continua a vir do registo da empresa, que é
    quem sabe o preço e o lugar de cada um.
    """

    def setUp(self):
        super().setUp()
        self.cliente = radar.app.test_client()
        with radar.liga() as c:
            # com texto e detalhe lido: sem texto a ficha ia ao DR buscar o
            # detalhe (e a captura verdadeira existe na pasta), e o que
            # voltava escrevia por cima dos lotes de ensaio
            c.execute("INSERT INTO anuncios (ref, titulo, entidade, data_pub, tipo, url, "
                      "estado, lotes, texto, detalhe_lido) "
                      "VALUES (?,?,?,?,?,?,?,?,?,1)",
                      ("1947/2026", "Servidor de terminologias", "SPMS", "2026-02-01",
                       "Anúncio de procedimento", "https://dr/1947", "novo",
                       json.dumps(TestResumoDosLotes.LOTES),
                       "1 - IDENTIFICAÇÃO E CONTACTOS DA ENTIDADE ADJUDICANTE\n"
                       "Designação da entidade adjudicante: SPMS\n"
                       "Procedimento com lotes? Sim\n"))
            for i, l in enumerate(TestResumoDosLotes.EMPRESA, 1):
                c.execute("INSERT INTO empresa (id, nome, ref, lote, status, zoho_fase, "
                          "valor_proposta, lugar, resultado) VALUES (?,?,?,?,?,?,?,?,?)",
                          (i, "Pilar 4 - L%d" % l["lote"], "1947/2026", l["lote"], l["status"],
                           l["zoho_fase"], l["valor_proposta"], l["lugar"], "guardado"))
        # uma proposta por lote, com o resultado de cada um
        self.por_lote = {}
        for n, estado in ((1, "perdido"), (2, "ganho"), (3, "perdido")):
            self.por_lote[n] = radar.criar_proposta("1947/2026", lote=n,
                                                    estado=estado)

    def test_cada_lote_cai_na_sua_ranhura_sem_truque_nenhum(self):
        """Com uma proposta por lote, a separação deixa de precisar de
        truque: o L2 está na aba do Ganho e os outros dois na do
        Perdido, sem nada montado à mão."""
        ganho = self.cliente.get(radar.LISTA + "?estado=ganho").get_data(as_text=True)
        perdido = self.cliente.get(radar.LISTA + "?estado=perdido").get_data(as_text=True)
        self.assertIn("L2", ganho)
        self.assertIn("/proposta/%d/escada" % self.por_lote[2], ganho)
        self.assertNotIn("/proposta/%d/escada" % self.por_lote[1], ganho)
        for n in (1, 3):
            self.assertIn("/proposta/%d/escada" % self.por_lote[n], perdido)
        self.assertNotIn("/proposta/%d/escada" % self.por_lote[2], perdido)

    def test_cada_lote_move_se_por_si(self):
        """O cartão separado de antes não se arrastava nem tinha
        formulário: o que mandava era o Excel, e não havia forma de
        corrigir no painel o que ele dissesse. Agora cada lote tem o seu
        selector, e move-se sem levar os outros."""
        r = self.cliente.post("/proposta/%d/escada" % self.por_lote[1],
                              data={"estado": "submetido",
                                    "valor_proposta": "118.500,00 EUR"})
        self.assertEqual(r.status_code, 302)
        estados = {p["lote"]: p["estado"]
                   for p in radar.propostas_de("1947/2026")}
        self.assertEqual(estados, {1: "submetido", 2: "ganho", 3: "perdido"})

    def test_a_ficha_tem_um_bloco_de_proposta_por_lote(self):
        """«a página do anúncio é sempre a mesma» -- e com lotes há uma
        decisão por lote, por isso há um bloco por cada."""
        html_ = self.cliente.get("/anuncio/1947%2F2026").get_data(as_text=True)
        bloco = html_.split("id='proposta'")[1].split("id='pecas'")[0]
        for n in (1, 2, 3):
            self.assertIn("Lote %d" % n, bloco)
            self.assertIn("/proposta/%d/ficha" % self.por_lote[n], bloco)

    def test_a_ficha_tem_o_bloco_e_o_indice(self):
        html_ = self.cliente.get("/anuncio/1947%2F2026").get_data(as_text=True)
        self.assertIn("id='lotes'", html_)
        self.assertIn("<a href='#lotes'>Lotes</a>", html_)
        bloco = html_.split("id='lotes'")[1].split("</table>")[0]
        self.assertIn("Fomos a todos os 3 lotes", bloco)
        self.assertIn("436.262,40 EUR", bloco)
        self.assertIn("ganho", bloco)
        self.assertIn("1º lugar", bloco)
        self.assertIn("proposta", bloco)

    def test_sem_registo_da_empresa_a_ficha_diz_o(self):
        with radar.liga() as c:
            c.execute("DELETE FROM empresa")
        html_ = self.cliente.get("/anuncio/1947%2F2026").get_data(as_text=True)
        self.assertIn("sem registo de a que fomos", html_)
        self.assertNotIn("<th>A empresa</th>", html_)

    def test_sem_lotes_nao_ha_bloco(self):
        with radar.liga() as c:
            c.execute("UPDATE anuncios SET lotes='' WHERE ref='1947/2026'")
        html_ = self.cliente.get("/anuncio/1947%2F2026").get_data(as_text=True)
        self.assertNotIn("id='lotes'", html_)
        self.assertNotIn("href='#lotes'", html_)


class TestModeloDaEmpresa(BaseTemporaria):
    """O registo da empresa pelo modelo (8/09/2026): o radar dita o Excel, o
    utilizador preenche, e a importação passa por um ensaio no painel.
    O Excel antigo deixou de contar para a aplicação."""

    def setUp(self):
        super().setUp()
        import io
        self.io = io
        self.cliente = radar.app.test_client()
        self.enterContext(unittest.mock.patch.object(
            radar, "IMPORTACOES", os.path.join(self.pasta, "importacoes")))
        with radar.liga() as c:
            for ref, titulo, lotes in (("1947/2026", "Servidor de terminologias",
                                        json.dumps(TestResumoDosLotes.LOTES)),
                                       ("22285/2026", "Backups INFARMED", ""),
                                       ("100/2026", "Republicação", "")):
                c.execute("INSERT INTO anuncios (ref, titulo, entidade, data_pub, tipo, url, "
                          "estado, lotes, texto, detalhe_lido) VALUES (?,?,?,?,?,?,?,?,?,1)",
                          (ref, titulo, "SPMS", "2026-02-01", "Anúncio", "https://dr/x",
                           "alteracao" if ref == "100/2026" else "novo", lotes, "texto"))

    def preenchido(self, linhas):
        """Um .xlsx a partir do modelo, com as linhas dadas (listas por coluna)."""
        from openpyxl import load_workbook
        caminho = os.path.join(self.pasta, "m.xlsx")
        empresa.escrever_modelo(caminho)
        wb = load_workbook(caminho)
        ws = wb[empresa.FOLHA_MODELO]
        for l in linhas:
            ws.append(l)
        wb.save(caminho)
        return caminho

    def test_o_modelo_tem_as_colunas_e_as_listas(self):
        from openpyxl import load_workbook
        caminho = empresa.escrever_modelo(os.path.join(self.pasta, "modelo.xlsx"))
        wb = load_workbook(caminho)
        ws = wb[empresa.FOLHA_MODELO]
        self.assertEqual([c.value for c in ws[1]], [t for t, _ in empresa.COLUNAS_MODELO])
        validacoes = [dv.formula1 for dv in ws.data_validations.dataValidation]
        self.assertTrue(any("Não fomos" in f and "Ganho" in f for f in validacoes))
        self.assertTrue(any("Preço base baixo" in f for f in validacoes))
        self.assertIn("Instruções", wb.sheetnames)
        # sem linhas de dados: o modelo importado em branco nao entra nada
        self.assertEqual(empresa.ler_modelo(caminho), [])

    def test_ler_normaliza_e_aponta_erros_de_forma(self):
        caminho = self.preenchido([
            ["1947-2026", 2, "ganho", None, "169.344,00", 1, "Nós; Empresa B ; Empresa C", "Afonso", "ok"],
            [" 22285 / 2026 ", None, "Não fomos", "preco base demasiado baixo", None, None, None, None, None],
            ["lixo", "x", "Talvez", None, None, "primeiro", None, None, None],
        ])
        linhas = empresa.ler_modelo(caminho)
        self.assertEqual(len(linhas), 3)
        a, b, c_ = linhas
        self.assertEqual((a["ref"], a["lote"], a["status"], a["valor_proposta"], a["lugar"]),
                         ("1947/2026", 2, "Ganho", 169344.0, 1))
        self.assertEqual([x["nome"] for x in a["concorrentes"]], ["Nós", "Empresa B", "Empresa C"])
        self.assertEqual(a["responsavel"], "Afonso")
        self.assertEqual((b["ref"], b["lote"], b["status"], b["razao"]),
                         ("22285/2026", None, "Não fomos", "Preço base baixo"))
        self.assertEqual(a["erros"], [])
        self.assertTrue(any("ilegível" in e for e in c_["erros"]))
        self.assertTrue(any("lote" in e for e in c_["erros"]))
        self.assertTrue(any("estado" in e for e in c_["erros"]))
        self.assertTrue(any("lugar" in e for e in c_["erros"]))

    def test_o_ensaio_cruza_com_a_base(self):
        caminho = self.preenchido([
            ["1947/2026", 2, "Ganho", None, 169344, 1, None, None, None],
            ["1947/2026", 7, "Perdido", None, None, None, None, None, None],     # lote a mais
            ["1947/2026", 2, "Perdido", None, None, None, None, None, None],     # repetida
            ["22285/2026", 1, "Submetido", None, None, None, None, None, None],  # sem lotes
            ["22285/2026", None, "Não fomos", None, 5, None, None, None, None],
            ["9999/2026", None, "Ganho", None, None, None, None, None, None],    # sem anuncio
            ["100/2026", None, "Ganho", None, None, None, None, None, None],     # republicacao
        ])
        with radar.liga() as c:
            linhas, contagens = empresa.ensaio_modelo(c, empresa.ler_modelo(caminho))
        problemas = ["; ".join(l["problemas"]) for l in linhas]
        self.assertEqual(linhas[0]["problemas"], [])
        self.assertEqual(linhas[0]["titulo"], "Servidor de terminologias")
        self.assertIn("não tem o lote 7", problemas[1])
        self.assertIn("repete a linha 2", problemas[2])
        self.assertIn("não declara lotes", problemas[3])
        self.assertEqual(linhas[4]["problemas"], [])
        self.assertTrue(any("não contam" in a for a in linhas[4]["avisos"]))
        self.assertIn("não há anúncio 9999/2026", problemas[5])
        self.assertIn("republicação", problemas[6])
        self.assertEqual((contagens["total"], contagens["ok"], contagens["com_erro"],
                          contagens["anuncios"]), (7, 2, 5, 2))

    def test_aplicar_grava_o_registo_e_a_triagem(self):
        caminho = self.preenchido([
            ["1947/2026", 1, "Perdido", None, 54432, 3, "A; B; Nós", None, None],
            ["1947/2026", 2, "Ganho", None, 169344, 1, "Nós; B; C", "Afonso", None],
            ["22285/2026", None, "Não fomos", "Falta de CV's", None, None, None, None, "sem equipa"],
        ])
        with radar.liga() as c:
            linhas, _ = empresa.ensaio_modelo(c, empresa.ler_modelo(caminho))
            r = empresa.aplicar_modelo(c, linhas, quem="teste")
        self.assertEqual((r["gravadas"], r["anuncios"], r["aplicadas"]), (3, 2, 2))
        with radar.liga() as c:
            # ganhamos um lote: desde 15/09/2026 o cartao E do lote, e nao
            # do anuncio -- o L2 fica no Ganho com a proposta desse lote,
            # e o L1 perdido tem cartao proprio na outra coluna
            a = c.execute("SELECT * FROM propostas WHERE ref='1947/2026' "
                          "AND lote=2").fetchone()
            self.assertEqual((a["estado"], a["lugar"], a["responsavel"]),
                             ("ganho", 1, "Afonso"))
            self.assertIn("169.344", a["valor_proposta"])
            b = c.execute("SELECT estado, motivo FROM propostas "
                          "WHERE ref='22285/2026'").fetchone()
            self.assertEqual((b["estado"], b["motivo"]),
                             ("nao_fomos", "Falta de CV's"))
            self.assertEqual(c.execute("SELECT COUNT(*) FROM empresa WHERE folha='modelo'").fetchone()[0], 3)
            self.assertEqual(c.execute("SELECT lote FROM empresa WHERE ref='22285/2026'").fetchone()[0], 0)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM pessoas WHERE nome='Afonso'").fetchone()[0], 1)
            # e a ficha dos lotes ve o registo
            linhas_empresa = empresa.linhas_de_lotes(c, ["1947/2026"])["1947/2026"]
        resumo = radar.resumo_dos_lotes(TestResumoDosLotes.LOTES, linhas_empresa)
        self.assertEqual(resumo["por_estado"], {"perdido": [1], "ganho": [2]})
        # importar outra vez a mesma linha substitui, nao duplica
        with radar.liga() as c:
            linhas, _ = empresa.ensaio_modelo(c, empresa.ler_modelo(caminho))
            empresa.aplicar_modelo(c, linhas, quem="teste")
            self.assertEqual(c.execute("SELECT COUNT(*) FROM empresa").fetchone()[0], 3)

    def test_desaplicar_repoe_as_propostas_da_copia(self):
        """O `--empresa-desfazer`: desfaz uma importação repondo as propostas
        tal como estão numa cópia de antes dela.

        Repor também sabe APAGAR (15/09/2026): uma proposta que a
        importação criou do nada não estava na cópia, e deixá-la lá era a
        importação ficar meia desfeita. E o histórico repõe-se pela
        cópia, não por `quem='Excel'` -- essa condição deixou de apanhar
        nada no dia em que o leitor do Excel antigo saiu."""
        ja_estava = radar.criar_proposta("22285/2026", estado="nao_fomos")
        radar.gravar_motivo(ja_estava, "Falta de CV's")
        copia = os.path.join(self.pasta, "antes.db")
        with radar.liga() as c:
            c.execute("VACUUM INTO ?", (copia,))
        caminho = self.preenchido([
            ["1947/2026", 2, "Ganho", None, 169344, 1, None, "Afonso", None],
            ["22285/2026", None, "Perdido", None, None, 3, None, None, None],
        ])
        with radar.liga() as c:
            linhas, _ = empresa.ensaio_modelo(c, empresa.ler_modelo(caminho))
            empresa.aplicar_modelo(c, linhas, quem="Afonso")
        # a do lote nasceu da importação; a outra é um conflito com a
        # decisão humana, e o conflito escreve uma linha no histórico
        self.assertEqual(radar.propostas_de("1947/2026")[0]["estado"], "ganho")
        with radar.liga() as c:
            self.assertGreater(c.execute(
                "SELECT COUNT(*) FROM historico WHERE ref='1947/2026'"
                ).fetchone()[0], 0)

        repostos, apagadas = empresa.desaplicar_da_copia(copia)
        self.assertEqual(repostos, 2)
        self.assertGreater(apagadas, 0)
        # a que a importação criou do nada desaparece
        self.assertEqual(radar.propostas_de("1947/2026"), [])
        # o que já lá estava antes da importação volta tal e qual
        volta = radar.propostas_de("22285/2026")
        self.assertEqual([(p["estado"], p["motivo"]) for p in volta],
                         [("nao_fomos", "Falta de CV's")])
        with radar.liga() as c:
            self.assertEqual(c.execute(
                "SELECT COUNT(*) FROM historico WHERE ref='1947/2026'"
                ).fetchone()[0], 0)
            # o registo fica: é o que a importação trouxe, e não se perde
            self.assertEqual(c.execute(
                "SELECT resultado FROM empresa WHERE ref='1947/2026'"
                ).fetchone()[0], "guardado")

    def test_o_fluxo_no_painel_ensaio_e_confirmar(self):
        r = self.cliente.get("/configuracoes/importar")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Descarregar o modelo", r.get_data(as_text=True))
        r = self.cliente.get("/configuracoes/importar/modelo.xlsx")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data[:2] == b"PK")          # e um zip: um .xlsx
        caminho = self.preenchido([
            ["1947/2026", 2, "Ganho", None, 169344, 1, None, None, None],
            ["9999/2026", None, "Ganho", None, None, None, None, None, None],
        ])
        with open(caminho, "rb") as f:
            r = self.cliente.post("/configuracoes/importar",
                                  data={"ficheiro": (self.io.BytesIO(f.read()), "registo.xlsx")},
                                  content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200)
        html_ = r.get_data(as_text=True)
        self.assertIn("<b>1 liga</b>", html_)
        self.assertIn("<b>1 com erro</b>", html_)
        self.assertIn("não há anúncio 9999/2026", html_)
        self.assertIn("Nada foi gravado ainda", html_)
        m = re.search(r"name='ficheiro' value='([^']+)'", html_)
        self.assertTrue(m)
        # nada gravado ate confirmar
        with radar.liga() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM empresa").fetchone()[0], 0)
        r = self.cliente.post("/configuracoes/importar/confirmar", data={"ficheiro": m.group(1)})
        self.assertEqual(r.status_code, 302)
        self.assertIn("Importado", unquote_plus(r.headers["Location"]))
        with radar.liga() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM empresa").fetchone()[0], 1)
        # a decisão mora na proposta desde 15/09/2026
        self.assertEqual(radar.propostas_de("1947/2026")[0]["estado"], "ganho")
        # um nome com caminho nao passa
        r = self.cliente.post("/configuracoes/importar/confirmar", data={"ficheiro": "../radar.db"})
        self.assertIn("carrega-o outra vez", unquote_plus(r.headers["Location"]))
        # e um ficheiro que nao e .xlsx e recusado sem ler
        r = self.cliente.post("/configuracoes/importar",
                              data={"ficheiro": (self.io.BytesIO(b"x"), "lista.csv")},
                              content_type="multipart/form-data")
        self.assertIn("Só .xlsx", unquote_plus(r.headers["Location"]))


class TestEstadoZero(BaseTemporaria):
    """--estado-zero (8/09/2026): a aplicação como acabada de instalar,
    sem perder o acervo nem as republicações."""

    def setUp(self):
        super().setUp()
        self.enterContext(unittest.mock.patch.object(
            radar, "CONFIG", os.path.join(self.pasta, "config.json")))
        radar.gravar_config({"interesse_activo": True, "interesse_cpv": "72000000",
                             "email": {"para": "x@y.pt", "de": "r@g.com"}})
        with radar.liga() as c:
            for ref, estado in (("1/2026", "novo"), ("2/2026", "novo"),
                                ("3/2026", "alteracao"), ("4/2026", "novo")):
                c.execute("INSERT INTO anuncios (ref, titulo, entidade, "
                          "data_pub, tipo, url, estado) VALUES (?,?,?,?,?,?,?)",
                          (ref, "t", "e", "2026-01-01", "a", "u", estado))
        # a decisão da empresa mora na escada desde 15/09/2026
        ganho = radar.criar_proposta("1/2026", estado="ganho")
        radar.gravar_campos_da_proposta(ganho, ["responsavel"], ["Afonso"])
        nao_fomos = radar.criar_proposta("2/2026", estado="nao_fomos")
        radar.gravar_motivo(nao_fomos, "Fora do âmbito")
        with radar.liga() as c:
            c.execute("INSERT INTO tarefas (ref, o_que, quando) "
                      "VALUES ('1/2026', 'pedir CVs', '2026-02-01')")
            c.execute("DELETE FROM historico")     # o que interessa é o de baixo
            c.execute("INSERT INTO etiquetas (nome, cor) VALUES ('x', '#000')")
            c.execute("INSERT INTO historico (ref, quem, accao, detalhe, quando) VALUES ('1/2026','a','b','c','d')")
            c.execute("INSERT INTO filtros_guardados (nome, consulta) VALUES ('f', 'q=x')")
            c.execute("INSERT INTO empresa (nome, ref) VALUES ('linha', '1/2026')")
            c.execute("INSERT INTO pessoas (nome) VALUES ('Afonso')")

    def test_apaga_o_que_e_do_utilizador_e_guarda_o_acervo(self):
        n = radar.repor_estado_zero()
        self.assertEqual(n["propostas"], 2)
        self.assertEqual(n["tarefas"], 1)
        self.assertEqual(n["empresa"], 1)
        with radar.liga() as c:
            estados = dict(c.execute("SELECT ref, estado FROM anuncios"))
            # o acervo fica, e as republicações continuam escondidas
            self.assertEqual(estados, {"1/2026": "novo", "2/2026": "novo",
                                       "3/2026": "alteracao", "4/2026": "novo"})
            for tabela in ("propostas", "tarefas", "etiquetas", "historico",
                           "filtros_guardados", "empresa", "pessoas"):
                self.assertEqual(c.execute("SELECT COUNT(*) FROM %s" % tabela).fetchone()[0], 0, tabela)
        cfg = radar.ler_config()
        self.assertFalse(cfg["interesse_activo"])
        self.assertEqual(cfg["interesse_cpv"], "")
        self.assertEqual(cfg["email"]["para"], "")
        self.assertEqual(cfg["email"]["de"], "r@g.com")      # quem envia fica


class TestEcraEstreito(unittest.TestCase):
    """O painel no telemóvel (8/09/2026, «quero que o frontend seja
    responsive»). Medido antes a 375 px: a barra de 140 px comia um terço
    do ecrã, a linha da lista transbordava, o título da ficha vinha com
    22 px numa coluna de 230. Isto guarda as regras que o desfazem."""

    def bloco(self):
        return radar.CSS.split("@media (max-width:900px){", 1)[1]

    def test_ha_um_ponto_de_corte_a_900_e_a_barra_e_uma_linha_em_cima(self):
        # 13/09/2026: a barra passou a horizontal em TODOS os tamanhos
        # ("Mudancas na plataforma RADAR"); o que era o bloco do telemovel
        # e agora a regra, e o bloco so trata do que e estreito
        self.assertIn("@media (max-width:900px){", radar.CSS)
        base = radar.CSS.split("@media (max-width:900px){", 1)[0]
        self.assertIn(".app{display:flex;flex-direction:column;min-height:100vh}", base)
        self.assertIn(".barra{display:flex;flex-direction:row;flex-wrap:wrap", base)
        self.assertIn(".barra nav{display:flex;flex-direction:row;flex-wrap:nowrap", base)
        self.assertNotIn("aside", base)
        b = self.bloco()
        # no estreito a navegacao vai para uma linha propria, a rolar de lado
        self.assertIn(".barra nav{order:10;flex-basis:100%", b)

    def test_as_grelhas_de_duas_colunas_passam_a_uma(self):
        b = self.bloco()
        self.assertIn(".item{grid-template-columns:minmax(0,1fr)}", b)
        self.assertIn(".essencial .par{grid-template-columns:minmax(0,1fr)", b)
        self.assertIn(".kpis{grid-template-columns:repeat(2,minmax(0,1fr))}", b)

    def test_o_que_e_largo_rola_dentro_de_si_e_nao_na_pagina(self):
        b = self.bloco()
        for regra in (".abas{overflow-x:auto", ".ficha-indice{gap:14px;overflow-x:auto",
                      ".escada{flex-wrap:wrap}", ".barras .col{min-width:0}"):
            self.assertIn(regra, b, regra)
        # o viewport esta declarado, senao o browser do telemovel finge 980px
        self.assertIn('<meta name="viewport" content="width=device-width, initial-scale=1">', radar.BASE)



class TestLigacaoFechaAoSair(BaseTemporaria):
    """8/09/2026, à noite: o painel a servir radargov.pt esgotou os 1024
    descritores do processo em quatro horas — 501 ligações ao radar.db
    abertas, porque o `with` do sqlite3 só faz commit e a ligação
    ficava à espera do garbage collector. O accept() a falhar em ciclo
    pôs o processo a 100% de CPU sem atender ninguém."""

    def test_a_ligacao_fecha_no_fim_do_with(self):
        with radar.liga() as c:
            self.assertEqual(c.execute("SELECT 1").fetchone()[0], 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            c.execute("SELECT 1")

    def test_e_commit_continua_a_acontecer(self):
        with radar.liga() as c:
            c.execute("INSERT INTO estado VALUES ('teste-fecho', '1')")
        with radar.liga() as c:
            self.assertEqual(c.execute("SELECT valor FROM estado WHERE chave='teste-fecho'")
                             .fetchone()[0], "1")

    def test_o_corpus_tambem(self):
        self.assertIs(type(radar.liga()), radar.Ligacao)
        corpus_antigo = radar.CORPUS
        radar.CORPUS = os.path.join(self.pasta, "corpus.db")
        try:
            with radar.liga_corpus() as c:
                pass
            with self.assertRaises(sqlite3.ProgrammingError):
                c.execute("SELECT 1")
        finally:
            radar.CORPUS = corpus_antigo

    def test_cem_pedidos_nao_deixam_ligacoes_abertas(self):
        cliente = radar.app.test_client()
        gc.collect()
        antes = len([o for o in gc.get_objects() if isinstance(o, sqlite3.Connection)])
        for _ in range(30):
            cliente.get(radar.LISTA)
        depois = len([o for o in gc.get_objects() if isinstance(o, sqlite3.Connection)])
        # fechadas ou nao, o que conta e que nao se acumulam por pedido
        self.assertLessEqual(depois - antes, 3)


class TestPecaNaoSaiDaPasta(BaseTemporaria):
    """8/09/2026, à noite: o painel estava na internet havia um dia e as
    quatro rotas que servem ficheiros deixavam sair de `documentos/`.
    A ref passava por `re.sub(r"[^0-9A-Za-z._-]", "-", ref)`, que troca
    a barra por hífen mas deixa `..` inteiro — e as rotas recebem-na
    como `<path:ref>`. Um GET a /peca/../radar.db dava a base (hashes
    das palavras-passe, sessões, triagem toda); /documento/../curl_DR.txt
    dava os cookies do portal do DR. A guarda que lá estava comparava o
    caminho com a pasta, mas a pasta era escolhida pelo mesmo pedido.
    Pelo caminho, o 404 dessas rotas devolvia a ref crua dentro do HTML."""

    def refs_que_escapam(self):
        return ["..", "%2e%2e", "../..", "a/../..", "."]

    def test_a_ref_nunca_e_ponto_nem_ponto_ponto(self):
        for ref in ("..", ".", "...", " .. ", "../..", "./."):
            nome = radar.ref_de_pasta(ref)
            self.assertNotIn(nome, (".", "..", ""),
                             "ref %r virou a pasta %r" % (ref, nome))

    def test_uma_ref_verdadeira_nao_muda(self):
        self.assertEqual(radar.ref_de_pasta("12345/2026"), "12345-2026")

    def test_o_caminho_fica_dentro_de_documentos(self):
        for ref in self.refs_que_escapam():
            for nome in ("radar.db", "config.json", "curl_DR.txt", "radar.py"):
                self.assertIsNone(radar.caminho_na_pasta(ref, nome),
                                  "/%s/%s saiu da pasta" % (ref, nome))

    def test_as_rotas_recusam(self):
        cliente = radar.app.test_client()
        for ref in self.refs_que_escapam():
            for nome in ("radar.db", "curl_DR.txt"):
                for rota in ("/documento/%s/%s", "/peca/%s/%s",
                             "/peca-pagina/%s/%s/1.png"):
                    r = cliente.get(rota % (ref, nome))
                    self.assertEqual(r.status_code, 404,
                                     "%s serviu %s" % (rota % (ref, nome),
                                                       r.status_code))
                    self.assertNotIn(b"SQLite format", r.data)

    def test_o_404_escapa_a_ref(self):
        cliente = radar.app.test_client()
        r = cliente.get("/documento/%3Cscript%3Ex/naoexiste")
        self.assertNotIn(b"<script>", r.data)


class TestExportacaoNaoChocaComOutroProcesso(BaseTemporaria):
    """8/09/2026, às 17:00: `ultima_exportacao_triagem` guardou
    «[Errno 2] ... triagem.jsonl.tmp -> triagem.jsonl». Correram duas
    verificações ao mesmo tempo — o temporizador do systemd (17:00:37)
    e o relógio de dentro do painel, que não se vêem um ao outro porque
    a guarda de «uma verificação de cada vez» é uma variável na memória
    de um processo. Os dois escreviam para o MESMO rascunho: o primeiro
    mudava-lhe o nome, o segundo já não o encontrava. E como o
    FileNotFoundError é um OSError, apanhava-o o try que no verificar()
    envolve a exportação E o empurrar_triagem() — o envio dessa volta
    nem chegava a ser tentado."""

    def rascunhos_com_pid(self, pid):
        """Os rascunhos por onde a exportacao passa, fingindo ser o
        processo `pid`. Espia o os.replace em vez de correr dois
        processos a serio: o que ha a garantir e que o NOME depende do
        pid, e isso mede-se sem concorrencia nenhuma."""
        alvo = os.path.join(self.pasta, "triagem.jsonl")
        vistos = []
        replace_verdadeiro = os.replace

        def espia(origem, destino):
            vistos.append(os.path.basename(origem))
            return replace_verdadeiro(origem, destino)

        with unittest.mock.patch.object(radar.os, "getpid", lambda: pid), \
                unittest.mock.patch.object(radar.os, "replace", espia):
            radar.exportar_triagem(alvo)
        return vistos

    def test_o_rascunho_tem_o_numero_do_processo(self):
        vistos = self.rascunhos_com_pid(4242)
        self.assertTrue(vistos, "não passou por nenhum rascunho")
        self.assertIn("4242", vistos[0],
                      "o rascunho %r não tem o número do processo" % vistos[0])

    def test_dois_processos_nao_partilham_o_rascunho(self):
        # e o caso das 17:00: dois processos, um rascunho so
        self.assertNotEqual(self.rascunhos_com_pid(111),
                            self.rascunhos_com_pid(222))

    def test_o_ficheiro_final_fica_com_o_nome_pedido(self):
        alvo = os.path.join(self.pasta, "triagem.jsonl")
        n, caminho = radar.exportar_triagem(alvo)
        self.assertEqual(caminho, alvo)
        self.assertTrue(os.path.exists(alvo))
        self.assertFalse([f for f in os.listdir(self.pasta)
                          if f.endswith(".tmp")], "ficou rascunho para trás")

    def test_uma_exportacao_boa_limpa_a_marca_de_erro(self):
        # a marca das 17:00 so se escrevia; ficava no painel para sempre
        #
        # O TRIAGEM_EXPORT tem de ir para a pasta temporaria: o
        # verificar() exporta para o caminho de origem, que e o
        # `triagem.jsonl` VERDADEIRO da pasta do radar -- correr os
        # testes reescrevia-o, e o git mostrava-o alterado sem ninguem
        # lhe ter tocado. Apanhado a 15/09/2026, a olhar para um
        # `git status` que tinha uma linha a mais.
        self.enterContext(unittest.mock.patch.object(
            radar, "TRIAGEM_EXPORT",
            os.path.join(self.pasta, "triagem.jsonl")))
        radar.marca_erro("ultima_exportacao_triagem", "exportacao",
                         "erro de antes")
        with radar.liga() as c:
            self.assertTrue(c.execute(
                "SELECT valor FROM estado WHERE chave=?",
                ("ultima_exportacao_triagem",)).fetchone())
        with unittest.mock.patch.object(radar, "recolher",
                                        lambda *a, **k: (False, "sem rede", 0)), \
                unittest.mock.patch.object(radar, "copia_com_marca",
                                           lambda *a, **k: None), \
                unittest.mock.patch.object(radar, "empurrar_triagem",
                                           lambda *a, **k: (True, "")):
            radar.verificar({"copia_de_seguranca": False})
        with radar.liga() as c:
            self.assertIsNone(c.execute(
                "SELECT valor FROM estado WHERE chave=?",
                ("ultima_exportacao_triagem",)).fetchone(),
                "a marca de erro sobreviveu a uma exportação boa")



class TestMudancasDeSetembro(BaseTemporaria):
    """«Mudanças na plataforma RADAR» (13/09/2026), o documento do Afonso:
    dois tipos de utilizador, a barra em cima, o menu de configurações
    reordenado com os Indicadores lá dentro, a Conta sem nome nem nota,
    o Interesse só com a árvore, os Alertas sem interesse nem filtros
    guardados, e o e-mail só com destino e hora para quem não é admin."""
    FORA = {"REMOTE_ADDR": "203.0.113.7"}

    def setUp(self):
        super().setUp()
        import contas
        self.contas = contas
        self.enterContext(unittest.mock.patch.object(
            radar, "CONFIG", os.path.join(self.pasta, "config.json")))
        self.cfg = dict(radar.CONFIG_INICIAL, acesso_livre_local=True)
        self.enterContext(unittest.mock.patch.object(
            radar, "ler_config", lambda: dict(self.cfg)))
        with radar.liga() as c:
            self.contas.criar_utilizador(c, "admin", "senha-comprida")
            self.contas.criar_utilizador(c, "teste", "senha-comprida", papel="tester")

    def entrar(self, quem):
        cliente = radar.app.test_client()
        r = cliente.post("/entrar", data={"email": quem, "senha": "senha-comprida"},
                         environ_base=self.FORA)
        self.assertEqual(r.status_code, 302)
        return cliente

    def token(self, cliente):
        html_ = cliente.get("/", environ_base=self.FORA).get_data(as_text=True)
        m = re.search(r"<meta name=\"csrf\" content=\"([0-9a-f]+)\"", html_)
        return m.group(1) if m else ""

    # -- os papeis

    def test_quem_ja_existia_e_admin_e_a_coluna_entra_por_migracao(self):
        with radar.liga() as c:
            c.execute("DROP TABLE utilizadores")
            c.execute("CREATE TABLE utilizadores (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                      "email TEXT UNIQUE NOT NULL, nome TEXT NOT NULL DEFAULT '', "
                      "hash TEXT NOT NULL, criado_em TEXT, ultimo_acesso TEXT)")
            c.execute("INSERT INTO utilizadores (email, hash) VALUES ('afonso', 'x')")
            self.contas.iniciar_tabelas(c)
            self.assertEqual(self.contas.utilizadores(c)[0]["papel"], "admin")
            # uma conta nova sem papel dito e admin; com papel, o que se disse
            self.assertEqual(self.contas.utilizadores(c)[0]["papel"], "admin")
            with self.assertRaises(ValueError):
                self.contas.criar_utilizador(c, "z", "senha-comprida", papel="chefe")
            # trocar a palavra-passe nao despromove
            self.contas.criar_utilizador(c, "teste", "senha-comprida", papel="tester")
            self.contas.criar_utilizador(c, "teste", "outra-senha-1")
            papel = c.execute("SELECT papel FROM utilizadores WHERE email='teste'").fetchone()[0]
            self.assertEqual(papel, "tester")
            self.assertTrue(self.contas.e_admin({"papel": "admin"}))
            self.assertFalse(self.contas.e_admin({"papel": "tester"}))

    def test_o_ultimo_admin_nao_se_tira(self):
        with radar.liga() as c:
            admin = [u for u in self.contas.utilizadores(c) if u["email"] == "admin"][0]
            tester = [u for u in self.contas.utilizadores(c) if u["email"] == "teste"][0]
            with self.assertRaises(ValueError):
                self.contas.apagar_utilizador(c, admin["id"])
            self.assertTrue(self.contas.apagar_utilizador(c, tester["id"]))
            self.assertFalse(self.contas.apagar_utilizador(c, tester["id"]))

    def test_a_sessao_traz_o_papel(self):
        with radar.liga() as c:
            token, u = self.contas.entrar(c, "teste", "senha-comprida")
            self.assertEqual(u["papel"], "tester")
            self.assertEqual(self.contas.utilizador_da_sessao(c, token)["papel"], "tester")

    def test_o_tester_nao_abre_o_que_e_do_sistema(self):
        tester = self.entrar("teste")
        admin = self.entrar("admin")
        for rota in ("/configuracoes/recolha", "/configuracoes/leitura",
                     "/configuracoes/capturas", "/configuracoes/copias",
                     "/configuracoes/indicadores", "/indicadores"):
            with self.subTest(rota=rota):
                self.assertEqual(tester.get(rota, environ_base=self.FORA).status_code, 403)
                self.assertIn(admin.get(rota, environ_base=self.FORA).status_code, (200, 302))
        # os POST tambem: o "Verificar agora" e quem envia o e-mail
        for rota in ("/verificar", "/alertas/remetente", "/configuracoes/conta/utilizadores"):
            with self.subTest(rota=rota):
                r = tester.post(rota, data={"csrf": self.token(tester)}, environ_base=self.FORA)
                self.assertEqual(r.status_code, 403)
        # e o que e dele continua a abrir
        for rota in ("/", "/calendario", "/contratos", "/configuracoes/conta",
                     "/configuracoes/interesse", "/configuracoes/alertas",
                     "/configuracoes/importar"):
            with self.subTest(rota=rota):
                self.assertEqual(tester.get(rota, environ_base=self.FORA).status_code, 200)

    def test_o_indice_e_o_verificar_agora_seguem_o_papel(self):
        tester = self.entrar("teste")
        admin = self.entrar("admin")
        html_t = tester.get("/configuracoes/conta", environ_base=self.FORA).get_data(as_text=True)
        html_a = admin.get("/configuracoes/conta", environ_base=self.FORA).get_data(as_text=True)
        for seccao in ("recolha", "leitura", "capturas", "copias", "indicadores"):
            self.assertNotIn("href='/configuracoes/%s'" % seccao, html_t)
            self.assertIn("href='/configuracoes/%s'" % seccao, html_a)
        for seccao in ("conta", "interesse", "alertas", "importar"):
            self.assertIn("href='/configuracoes/%s'" % seccao, html_t)
        # o bloco dos utilizadores so ao admin
        self.assertIn("Criar utilizador", html_a)
        self.assertNotIn("Criar utilizador", html_t)
        lista_t = tester.get(radar.LISTA,
                             environ_base=self.FORA).get_data(as_text=True)
        lista_a = admin.get(radar.LISTA,
                            environ_base=self.FORA).get_data(as_text=True)
        # (pelo formulario, nao pelo texto: o CSS da pagina cita o botao)
        self.assertNotIn("action='/verificar'", lista_t)
        self.assertIn("action='/verificar'", lista_a)
        # o e-mail: o tester so ve destino e hora
        alertas_t = tester.get("/configuracoes/alertas", environ_base=self.FORA).get_data(as_text=True)
        alertas_a = admin.get("/configuracoes/alertas", environ_base=self.FORA).get_data(as_text=True)
        self.assertIn("name='hora_resumo'", alertas_t)
        self.assertNotIn("Quem envia", alertas_t)
        self.assertIn("Quem envia", alertas_a)

    def test_o_admin_cria_e_tira_contas_pelo_painel(self):
        admin = self.entrar("admin")
        r = admin.post("/configuracoes/conta/utilizadores",
                       data={"csrf": self.token(admin), "email": "novo",
                             "senha": "senha-do-novo", "papel": "tester"},
                       environ_base=self.FORA)
        self.assertIn("criado", unquote_plus(r.headers["Location"]))
        with radar.liga() as c:
            novo = [u for u in self.contas.utilizadores(c) if u["email"] == "novo"][0]
            self.assertEqual(novo["papel"], "tester")
            eu = [u for u in self.contas.utilizadores(c) if u["email"] == "admin"][0]
        # repetido: recusa; curta: recusa
        r = admin.post("/configuracoes/conta/utilizadores",
                       data={"csrf": self.token(admin), "email": "novo",
                             "senha": "senha-do-novo", "papel": "tester"},
                       environ_base=self.FORA)
        self.assertIn("existe", unquote_plus(r.headers["Location"]))
        r = admin.post("/configuracoes/conta/utilizadores",
                       data={"csrf": self.token(admin), "email": "outro",
                             "senha": "curta", "papel": "admin"},
                       environ_base=self.FORA)
        self.assertIn("8 caracteres", unquote_plus(r.headers["Location"]))
        # a propria conta nao se tira daqui; a do novo sim
        r = admin.post("/configuracoes/conta/utilizadores/%d/apagar" % eu["id"],
                       data={"csrf": self.token(admin)}, environ_base=self.FORA)
        self.assertIn("própria", unquote_plus(r.headers["Location"]))
        r = admin.post("/configuracoes/conta/utilizadores/%d/apagar" % novo["id"],
                       data={"csrf": self.token(admin)}, environ_base=self.FORA)
        self.assertIn("tirada", unquote_plus(r.headers["Location"]))
        with radar.liga() as c:
            self.assertNotIn("novo", [u["email"] for u in self.contas.utilizadores(c)])

    def test_as_sessoes_dizem_o_aparelho_e_nao_o_agente(self):
        self.assertEqual(radar.aparelho_do_agente(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605"), "iPhone")
        self.assertEqual(radar.aparelho_do_agente(
            "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36"), "Android")
        self.assertEqual(radar.aparelho_do_agente(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"), "Windows")
        self.assertEqual(radar.aparelho_do_agente(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605"), "Mac")
        self.assertEqual(radar.aparelho_do_agente("curl/8.5"), "outro aparelho")
        self.assertEqual(radar.aparelho_do_agente(None), "outro aparelho")
        cliente = radar.app.test_client()
        cliente.post("/entrar", data={"email": "admin", "senha": "senha-comprida"},
                     environ_base=dict(self.FORA, HTTP_USER_AGENT=
                                       "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X)"))
        html_ = cliente.get("/configuracoes/conta", environ_base=self.FORA).get_data(as_text=True)
        self.assertIn("iPhone (esta)", html_)
        self.assertNotIn("Mozilla", html_)

    # -- a barra

    def test_a_barra_e_um_header_sem_contagens_nem_ultima_verificacao(self):
        self.assertIn('<header class="barra">', radar.BASE)
        self.assertNotIn("<aside", radar.BASE)
        for texto in ("Verificação automática", "127.0.0.1:", "%(fontes)s",
                      "%(acervo)s", "%(ultima)s", "%(horas)s"):
            self.assertNotIn(texto, radar.BASE)
        html_ = radar.app.test_client().get(radar.LISTA).get_data(as_text=True)
        self.assertNotIn("Anúncios do DR", html_)
        self.assertNotIn("anúncios<br>", html_)
        self.assertIn('href="/configuracoes"', html_)
        # a ultima verificacao foi para os indicadores
        rotulo, _, _ = radar.linha_da_ultima_verificacao()
        self.assertEqual(rotulo, "Última verificação")
        html_ = radar.app.test_client().get("/configuracoes/indicadores").get_data(as_text=True)
        self.assertIn("Última verificação", html_)
        self.assertIn("Verificação automática", html_)
        self.assertIn("class='conf-indice'", html_)

    # -- o interesse

    def test_o_interesse_e_so_a_arvore_aberta_e_grava_pelo_botao_dela(self):
        html_ = radar.app.test_client().get("/configuracoes/interesse").get_data(as_text=True)
        self.assertIn("<details class='arvore' data-de='anuncios' open>", html_)
        self.assertIn("Guardar o interesse", html_)
        self.assertNotIn("data-submeter", html_)         # o botao da arvore submete
        self.assertNotIn("Marcar uma divisão apanha", html_)
        self.assertNotIn("name='activo'", html_)
        self.assertNotIn("Aplicar seleccionados", html_)
        self.assertIn("<input type='hidden' id='filtro-cpv' name='cpv'", html_)
        # a arvore ja aberta carrega-se logo, sem depender do toggle
        self.assertIn("if (ARV_DET.open) arvoreCarregar();", radar.ARVORE_JS)
        # com CPV fica ligado; vazio fica desligado -- nao ha caixa
        r = radar.app.test_client().post("/alertas/interesse", data={"cpv": "72000000"})
        self.assertIn("passa a mostrar", unquote_plus(r.headers["Location"]))
        cfg = json.load(open(radar.CONFIG, encoding="utf-8"))
        self.assertTrue(cfg["interesse_activo"])
        self.assertEqual(cfg["interesse_cpv"], "72000000")
        radar.app.test_client().post("/alertas/interesse", data={"cpv": ""})
        cfg = json.load(open(radar.CONFIG, encoding="utf-8"))
        self.assertFalse(cfg["interesse_activo"])

    def test_com_interesse_a_lista_fica_so_com_o_filtro_de_texto(self):
        html_ = radar.app.test_client().get(radar.LISTA).get_data(as_text=True)
        self.assertIn("details class='arvore'", html_)
        self.cfg.update(interesse_activo=True, interesse_cpv="72000000")
        html_ = radar.app.test_client().get(radar.LISTA).get_data(as_text=True)
        self.assertNotIn("details class='arvore'", html_)
        self.assertIn("name='q'", html_)
        # e o JS da arvore nao vai: ligava um listener a null
        self.assertNotIn("arvoreCarregar", html_)
        self.assertIn("if (ARV_DET) {", radar.ARVORE_JS)

    # -- os alertas

    def test_os_alertas_sem_interesse_e_criar_alerta_nasce_ligado(self):
        cliente = radar.app.test_client()
        html_ = cliente.get("/configuracoes/alertas").get_data(as_text=True)
        self.assertNotIn("Definir o interesse", html_)
        self.assertNotIn("<div class='rot'>Interesse</div>", html_)
        self.assertIn("Filtro de alertas", html_)
        self.assertIn("Criar alerta", html_)
        self.assertNotIn("Novo filtro", html_)
        self.assertNotIn("Criar filtro", html_)
        r = cliente.post("/alertas/criar", data={"nome": "IT", "cpv": "72000000", "estado": "novo"})
        self.assertIn("Alerta criado", unquote_plus(r.headers["Location"]))
        with radar.liga() as c:
            self.assertEqual(c.execute("SELECT alerta FROM filtros_guardados WHERE nome='IT'")
                             .fetchone()[0], 1)

    def test_o_formulario_do_alerta_tem_os_campos_da_lista_e_a_arvore_em_cima(self):
        # 14/09/2026: os mesmos campos da lista (nome ou objecto, entidade,
        # plataforma, datas), mais o nome; a arvore por cima; sem o grupo
        # dos contratos, que nao avisava de nada
        html_ = radar.app.test_client().get("/configuracoes/alertas").get_data(as_text=True)
        caixa = html_.split("<div class='rot'>Filtro de alertas</div>")[1].split("</form>")[0]
        self.assertLess(caixa.index("details class='arvore'"), caixa.index("action='/alertas/criar'"))
        form = caixa.split("action='/alertas/criar'")[1]
        for campo in ("name='nome'", "name='q'", "name='cpv'", "name='ent'",
                      "name='plat'", "name='de'", "name='ate'"):
            self.assertIn(campo, form)
        for campo in ("name='q_excl'", "name='op'", "name='estado'", "name='prazo'",
                      "name='adj'", "name='ganhou'", "name='proc'", "name='min'"):
            self.assertNotIn(campo, form)
        self.assertIn("type='hidden' id='filtro-cpv-excl'", form)
        self.assertNotIn("Só contratos", html_)
        self.assertIn("data-sugere='anuncios'", form)

    def test_os_filtros_guardados_deixaram_de_existir(self):
        regras = [r.rule for r in radar.app.url_map.iter_rules()]
        self.assertNotIn("/filtros/guardar", regras)
        self.assertFalse(hasattr(radar, "caixa_de_filtros"))
        self.assertFalse(hasattr(radar, "GUARDAR_JS"))
        for rota in ("/", "/contratos"):
            html_ = radar.app.test_client().get(rota).get_data(as_text=True)
            self.assertNotIn("Filtros guardados", html_)
            self.assertNotIn("Guardar filtro", html_)

    def test_os_filtros_sem_alerta_apagam_se_uma_vez_e_so_uma(self):
        with radar.liga() as c:
            c.execute("INSERT INTO filtros_guardados (nome, consulta, alerta) VALUES "
                      "('velho', 'q=x', 0), ('vivo', 'q=y', 1)")
            c.execute("DELETE FROM estado WHERE chave='filtros_sem_alerta_apagados'")
        radar.iniciar_db()
        with radar.liga() as c:
            nomes = [r[0] for r in c.execute("SELECT nome FROM filtros_guardados ORDER BY nome")]
        self.assertEqual(nomes, ["vivo"])
        # um alerta desligado DEPOIS da migracao fica: a marca ja esta posta
        with radar.liga() as c:
            c.execute("UPDATE filtros_guardados SET alerta=0 WHERE nome='vivo'")
        radar.iniciar_db()
        with radar.liga() as c:
            nomes = [r[0] for r in c.execute("SELECT nome FROM filtros_guardados")]
        self.assertEqual(nomes, ["vivo"])


class TestTrincoEntreProcessos(BaseTemporaria):
    """O P0 de 8/09/2026: às 17:00 o temporizador do systemd (um processo
    `--uma-vez`) e o relógio de dentro do painel correram os dois, sobre
    a mesma base, porque a guarda era um dicionário na memória de um só
    processo. O trinco passou a viver na tabela `estado`, com pid e hora.
    A condição («o outro está vivo e dentro do prazo») é injectável,
    para não depender de arrancar processos a sério."""

    def test_o_segundo_processo_desiste_enquanto_o_primeiro_vive(self):
        agora = datetime.datetime(2026, 9, 8, 17, 0, 0)
        tomou, _ = radar.tomar_trinco(agora=agora, pid=111, vivo=lambda p: True)
        self.assertTrue(tomou)
        tomou, porque = radar.tomar_trinco(agora=agora + datetime.timedelta(seconds=37),
                                           pid=222, vivo=lambda p: True)
        self.assertFalse(tomou)
        self.assertIn("pid 111", porque)
        self.assertIn("17:00", porque)
        # o dono volta a tomar o seu sem se bloquear a si proprio
        self.assertTrue(radar.tomar_trinco(agora=agora, pid=111, vivo=lambda p: True)[0])

    def test_um_trinco_de_processo_morto_ou_velho_nao_prende(self):
        agora = datetime.datetime(2026, 9, 8, 17, 0, 0)
        radar.tomar_trinco(agora=agora, pid=111, vivo=lambda p: True)
        # morto: o pid ja nao existe
        self.assertTrue(radar.tomar_trinco(agora=agora, pid=222,
                                           vivo=lambda p: False)[0])
        # velho: vivo mas ha mais de HORAS_DE_TRINCO (um processo preso)
        radar.tomar_trinco(agora=agora, pid=111, vivo=lambda p: True)
        tarde = agora + datetime.timedelta(hours=radar.HORAS_DE_TRINCO, minutes=1)
        self.assertTrue(radar.tomar_trinco(agora=tarde, pid=333,
                                           vivo=lambda p: True)[0])

    def test_so_o_dono_larga(self):
        agora = datetime.datetime(2026, 9, 8, 17, 0, 0)
        radar.tomar_trinco(agora=agora, pid=111, vivo=lambda p: True)
        radar.largar_trinco(pid=222)
        self.assertFalse(radar.tomar_trinco(agora=agora, pid=222,
                                            vivo=lambda p: True)[0])
        radar.largar_trinco(pid=111)
        self.assertTrue(radar.tomar_trinco(agora=agora, pid=222,
                                           vivo=lambda p: True)[0])
        radar.largar_trinco(pid=222)

    def test_o_painel_diz_que_e_noutro_processo(self):
        agora = datetime.datetime(2026, 9, 8, 17, 0, 0)
        self.assertEqual(radar.verificacao_noutro_processo(agora=agora), "")
        radar.tomar_trinco(agora=agora, pid=os.getpid() + 100000, vivo=lambda p: True)
        self.assertEqual(radar.verificacao_noutro_processo(
            agora=agora + datetime.timedelta(minutes=2), vivo=lambda p: True), "17:00")
        # o meu proprio trinco nao e "outro processo"
        radar.tomar_trinco(agora=agora, vivo=lambda p: True)
        self.assertEqual(radar.verificacao_noutro_processo(agora=agora), "")
        radar.largar_trinco()

    def test_comecar_verificacao_toma_e_larga_o_trinco(self):
        # a condicao verdadeira contra o recurso verdadeiro, uma vez: o
        # relogio do painel com o trinco de "outro processo" na base
        agora = datetime.datetime.now()
        radar.tomar_trinco(agora=agora, pid=os.getpid() + 100000, vivo=lambda p: True)
        antigo = radar.processo_vivo
        radar.processo_vivo = lambda p: True
        try:
            arrancou, porque = radar.comecar_verificacao()
            self.assertFalse(arrancou)
            self.assertIn("noutro processo", porque)
            self.assertFalse(radar._VERIFICACAO["a_correr"])
            self.assertIn("noutro processo", radar.verificacao_a_correr())
        finally:
            radar.processo_vivo = antigo
            radar.largar_trinco(pid=os.getpid() + 100000)

    def test_um_pid_que_nao_existe_esta_morto(self):
        self.assertTrue(radar.processo_vivo(os.getpid()))
        self.assertFalse(radar.processo_vivo(2 ** 22 - 1))



class TestVigilanciaDasPecas(BaseTemporaria):
    """03/09/2026: o reler_marcados() vigia o prazo e o preço base na
    página do DR, mas um esclarecimento ou uma errata não passam pelo DR —
    aparecem na lista de documentos da plataforma, e só se dava por eles
    abrindo a plataforma à mão.

    Os erros que estes testes travam, todos com custo real:

    - vigiar pela via do obter_documentos(), que apaga as linhas do
      anúncio: levava atrás o texto já extraído e os veredictos do OCR, e
      mandava as ~7 s por página de cada digitalização outra vez;
    - avisar a mesma peça a cada verificação — duas vezes por dia, para
      sempre — quando ela não se conseguiu trazer;
    - tomar uma lista vazia por «as peças desapareceram», que é a
      plataforma em baixo e não uma novidade (a mesma regra do
      diferencas_do_detalhe(): só se avisa o que tem valor dos dois lados);
    - contar o «Anúncio DR.pdf», que é o radar que o acrescenta e a
      plataforma não tem, como peça nova a cada volta."""

    def _anuncio(self, ref="30/2026", **campos):
        """Um anúncio JÁ na escada, que é o que a vigilância olha. Desde
        15/09/2026 isso é ter uma proposta e não `estado='interessa'`;
        passar `estado='novo'` deixa-o de fora, como antes."""
        valores = {"estado": "interessa", "docs_estado": "ok",
                   "link_pecas": "https://www.acingov.pt/x/donwloadProcedurePiece/A",
                   "plataforma": "acingov", "url": "https://x/anuncio-procedimento/k-30",
                   # com texto: senao a ficha vai ao DR reler o detalhe
                   # e escreve por cima do link das pecas
                   "texto": "Anúncio de procedimento", "detalhe_lido": 1,
                   "data_pub": datetime.date.today().isoformat(),
                   "prazo": (datetime.date.today() + datetime.timedelta(days=10)).isoformat(),
                   "titulo": "Aquisição de serviços", "entidade": "Câmara"}
        valores.update(campos)
        na_escada = valores.pop("estado") == "interessa"
        valores["estado"] = "novo"
        colunas = ",".join(valores)
        with radar.liga() as c:
            c.execute("INSERT INTO anuncios (ref,%s) VALUES (?%s)"
                      % (colunas, ",?" * len(valores)),
                      [ref] + list(valores.values()))
        if na_escada:
            radar.criar_proposta(ref)
        return ref

    def _peca(self, ref, nome, texto="texto da peça", estado="ok"):
        with radar.liga() as c:
            c.execute("INSERT INTO documentos (ref,nome,ficheiro,tamanho,"
                      "origem,obtido_em,texto,texto_estado)"
                      " VALUES (?,?,?,?,?,?,?,?)",
                      (ref, nome, nome, 10, "acingov", "2026-09-01 09:00",
                       texto, estado))

    def _disponiveis(self, *nomes):
        """A lista que a plataforma daria: o conteúdo só chega se pedido.

        Os bytes de propósito não são um PDF: assim o extrair_textos()
        diz «não é PDF» e cala-se, em vez de o pypdf gritar por um EOF
        que não existe — um teste que imprime avisos ensina a ignorá-los.
        """
        return [(n, (lambda n=n: b"conteudo de " + n.encode()))
                for n in nomes]

    def _alteracoes(self, ref):
        with radar.liga() as c:
            return [(r["campo"], r["depois"]) for r in c.execute(
                "SELECT campo, depois FROM alteracoes WHERE ref=?", (ref,))]

    def _docs(self, ref):
        with radar.liga() as c:
            return {r["nome"]: (r["texto_estado"], r["texto"]) for r in c.execute(
                "SELECT nome, texto_estado, texto FROM documentos WHERE ref=?",
                (ref,))}

    def test_peca_nova_avisa_e_nao_mexe_nas_que_ja_ca_estavam(self):
        ref = self._anuncio()
        self._peca(ref, "Caderno de Encargos.pdf", "texto por OCR", "ocr")
        self._peca(ref, "Anúncio DR.pdf")
        quantas = radar._guardar_pecas_novas(
            ref, "acingov",
            self._disponiveis("Caderno de Encargos.pdf", "Esclarecimento 1.pdf"))
        self.assertEqual(quantas, 1)
        self.assertEqual(self._alteracoes(ref),
                         [(radar.CAMPO_PECA_NOVA, "Esclarecimento 1.pdf")])
        docs = self._docs(ref)
        # o veredicto do OCR e o texto dele sobrevivem — que é
        # exactamente o que a via do obter_documentos() não faria
        self.assertEqual(docs["Caderno de Encargos.pdf"], ("ocr", "texto por OCR"))
        self.assertIn("Esclarecimento 1.pdf", docs)
        with radar.liga() as c:
            h = c.execute("SELECT detalhe FROM historico WHERE ref=?",
                          (ref,)).fetchall()
        self.assertTrue(any("Esclarecimento 1.pdf" in x["detalhe"] for x in h), h)

    def test_a_segunda_volta_nao_volta_a_avisar(self):
        ref = self._anuncio()
        self._peca(ref, "Caderno de Encargos.pdf")
        pecas = self._disponiveis("Caderno de Encargos.pdf", "Errata.pdf")
        self.assertEqual(radar._guardar_pecas_novas(ref, "acingov", pecas), 1)
        self.assertEqual(radar._guardar_pecas_novas(ref, "acingov", pecas), 0)
        self.assertEqual(len(self._alteracoes(ref)), 1)

    def test_peca_que_nao_se_consegue_trazer_avisa_uma_vez_so(self):
        # ficheiro acima do tecto: o buscar() devolve None. Avisar é
        # preciso — ela existe; repetir o aviso duas vezes por dia para
        # sempre é que não.
        ref = self._anuncio()
        pecas = [("Anexo enorme.zip", lambda: None)]
        self.assertEqual(radar._guardar_pecas_novas(ref, "acingov", pecas), 1)
        self.assertEqual(self._alteracoes(ref),
                         [(radar.CAMPO_PECA_NOVA, "Anexo enorme.zip")])
        self.assertEqual(self._docs(ref), {})
        self.assertEqual(radar._guardar_pecas_novas(ref, "acingov", pecas), 0)

    def test_o_anuncio_dr_nao_conta_como_peca_nova(self):
        ref = self._anuncio()
        self.assertEqual(radar._guardar_pecas_novas(
            ref, "acingov", self._disponiveis("Anúncio DR.pdf")), 0)
        self.assertEqual(self._alteracoes(ref), [])

    def test_lista_vazia_nao_e_novidade_nem_desaparecimento(self):
        ref = self._anuncio()
        self._peca(ref, "Caderno de Encargos.pdf")
        antigo = radar.pecas_disponiveis
        radar.pecas_disponiveis = lambda sessao, link: ([], "")
        try:
            novas, aviso = radar.vigiar_pecas()
        finally:
            radar.pecas_disponiveis = antigo
        self.assertEqual((novas, aviso), (0, ""))
        self.assertEqual(self._alteracoes(ref), [])
        self.assertEqual(list(self._docs(ref)), ["Caderno de Encargos.pdf"])

    def test_so_os_marcados_com_prazo_aberto_pecas_trazidas_e_uma_razao(self):
        ontem = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        # todos publicados ha 20 dias com prazo a 10: a data de
        # esclarecimentos (primeiro terco, 10 dias) ja passou
        pub = (datetime.date.today() - datetime.timedelta(days=20)).isoformat()
        self._anuncio("31/2026", estado="novo", data_pub=pub)           # por ver
        self._anuncio("32/2026", prazo=ontem, data_pub=pub)             # prazo fechado
        self._anuncio("33/2026", docs_estado="", data_pub=pub)          # sem base de comparação
        self._anuncio("34/2026", link_pecas="", data_pub=pub)           # sem link
        self._anuncio("35/2026", data_pub=pub)                          # só este conta
        self._anuncio("36/2026", data_pub=pub,                          # ja visto depois
                      pecas_vigiadas_em=datetime.date.today().isoformat() + " 09:00")
        escolhidos = radar.anuncios_a_vigiar()
        self.assertEqual([a["ref"] for a, _ in escolhidos], ["35/2026"])
        self.assertIn("esclarecimentos", escolhidos[0][1])
        vistos = []
        antigo = radar.pecas_disponiveis

        def espia(sessao, link):
            vistos.append(link)
            return [], ""
        radar.pecas_disponiveis = espia
        try:
            radar.vigiar_pecas()
        finally:
            radar.pecas_disponiveis = antigo
        self.assertEqual(len(vistos), 1, vistos)

    def test_a_razao_e_a_data_de_esclarecimentos_ou_uma_alteracao(self):
        hoje = datetime.date(2026, 9, 14)
        a = {"ref": "40/2026", "data_pub": "2026-09-01", "prazo": "2026-09-30",
             "pecas_vigiadas_em": ""}
        nunca = lambda ref, desde: False
        # esclarecimentos a 10/09 (primeiro terco de 29 dias): passou
        self.assertIn("esclarecimentos", radar.razao_para_vigiar(a, hoje, nunca))
        # ainda nao passou: sem razao
        self.assertEqual(radar.razao_para_vigiar(a, datetime.date(2026, 9, 5), nunca), "")
        # ja se olhou depois da data: sem razao
        visto = dict(a, pecas_vigiadas_em="2026-09-12 09:00")
        self.assertEqual(radar.razao_para_vigiar(visto, hoje, nunca), "")
        # mas uma alteracao desde entao volta a dar razao
        self.assertIn("mudaram", radar.razao_para_vigiar(
            visto, hoje, lambda ref, desde: desde == "2026-09-12 09:00"))
        # olhou-se no proprio dia da data: conta como antes dela
        no_dia = dict(a, pecas_vigiadas_em="2026-09-10 17:00")
        self.assertIn("esclarecimentos", radar.razao_para_vigiar(no_dia, hoje, nunca))
        # sem datas nao ha regra do primeiro terco
        self.assertEqual(radar.razao_para_vigiar(dict(a, prazo=""), hoje, nunca), "")

    def test_uma_alteracao_do_prazo_manda_ver_as_pecas(self):
        ref = self._anuncio(data_pub=datetime.date.today().isoformat())
        self.assertEqual(radar.anuncios_a_vigiar(), [])
        with radar.liga() as c:
            c.execute("UPDATE anuncios SET pecas_vigiadas_em='2026-09-01 09:00' WHERE ref=?",
                      (ref,))
        radar.registar_alteracoes(ref, [("prazo", "2026-09-20", "2026-09-30")])
        escolhidos = radar.anuncios_a_vigiar()
        self.assertEqual([a["ref"] for a, _ in escolhidos], [ref])
        self.assertIn("mudaram", escolhidos[0][1])

    def test_vigiar_um_anuncio_marca_quando_a_plataforma_responde(self):
        ref = self._anuncio()
        self._peca(ref, "Caderno de Encargos.pdf")
        with radar.liga() as c:
            a = c.execute("SELECT * FROM anuncios WHERE ref=?", (ref,)).fetchone()
        antigo = radar.pecas_disponiveis
        try:
            radar.pecas_disponiveis = lambda s, l: ([], "")     # a plataforma falhou
            self.assertEqual(radar.vigiar_anuncio(a)[0], 0)
            with radar.liga() as c:
                self.assertIsNone(c.execute("SELECT pecas_vigiadas_em FROM anuncios "
                                            "WHERE ref=?", (ref,)).fetchone()[0])
            radar.pecas_disponiveis = lambda s, l: (
                self._disponiveis("Caderno de Encargos.pdf", "Errata.pdf"), "")
            self.assertEqual(radar.vigiar_anuncio(a), (1, ""))
            with radar.liga() as c:
                self.assertTrue(c.execute("SELECT pecas_vigiadas_em FROM anuncios "
                                          "WHERE ref=?", (ref,)).fetchone()[0])
        finally:
            radar.pecas_disponiveis = antigo

    def test_com_peca_nova_rele_se_pelo_modelo_e_sem_ela_nao(self):
        ref = self._anuncio()
        self._peca(ref, "Caderno de Encargos.pdf")
        with radar.liga() as c:
            a = c.execute("SELECT * FROM anuncios WHERE ref=?", (ref,)).fetchone()
        relidos = []
        antigo = radar.pecas_disponiveis
        try:
            radar.pecas_disponiveis = lambda s, l: (
                self._disponiveis("Caderno de Encargos.pdf"), "")
            radar.vigiar_anuncio(a, reler=relidos.append)
            self.assertEqual(relidos, [])
            radar.pecas_disponiveis = lambda s, l: (
                self._disponiveis("Caderno de Encargos.pdf", "CE revisto.pdf"), "")
            radar.vigiar_anuncio(a, reler=relidos.append)
            self.assertEqual(relidos, [ref])
        finally:
            radar.pecas_disponiveis = antigo

    def test_a_verificacao_rele_em_linha_e_o_botao_pela_fila(self):
        # no --uma-vez a fila e uma thread daemon que morre com o
        # processo: a verificacao tem de ler em linha
        ref = self._anuncio()
        self._peca(ref, "Caderno de Encargos.pdf")
        lidos, na_fila = [], []
        antigos = (radar.pecas_disponiveis, radar.ler_pecas_e_registar,
                   radar.pedir_analise)
        try:
            radar.pecas_disponiveis = lambda s, l: (
                self._disponiveis("Caderno de Encargos.pdf", "Errata.pdf"), "")
            radar.ler_pecas_e_registar = lambda r, quem="": lidos.append((r, quem))
            radar.pedir_analise = lambda r, quem="": na_fila.append((r, quem))
            with radar.liga() as c:
                c.execute("UPDATE anuncios SET pecas_vigiadas_em='2026-09-01 09:00' "
                          "WHERE ref=?", (ref,))
            radar.registar_alteracoes(ref, [("prazo", "2026-09-20", "2026-09-30")])
            self.assertEqual(radar.vigiar_pecas()[0], 1)
            self.assertEqual(lidos, [(ref, "plataforma")])
            self.assertEqual(na_fila, [])
            radar.pecas_disponiveis = lambda s, l: (
                self._disponiveis("Caderno de Encargos.pdf", "Errata.pdf",
                                  "Esclarecimento 3.pdf"), "")
            r = radar.app.test_client().post("/pecas-novas/" + ref)
            self.assertIn("A reler pelo modelo", unquote_plus(r.headers["Location"]))
            self.assertEqual(len(na_fila), 1)
            self.assertEqual(na_fila[0][0], ref)
        finally:
            (radar.pecas_disponiveis, radar.ler_pecas_e_registar,
             radar.pedir_analise) = antigos

    def test_o_botao_da_ficha_diz_o_que_encontrou(self):
        ref = self._anuncio()
        self._peca(ref, "Caderno de Encargos.pdf")
        cliente = radar.app.test_client()
        html_ = cliente.get("/anuncio/" + ref).get_data(as_text=True)
        self.assertIn("Ver se há peças novas", html_)
        self.assertIn("action='/pecas-novas/%s'" % ref, html_)
        antigo = radar.pecas_disponiveis
        try:
            radar.pecas_disponiveis = lambda s, l: (
                self._disponiveis("Caderno de Encargos.pdf", "Esclarecimento 2.pdf"), "")
            r = cliente.post("/pecas-novas/" + ref)
            self.assertIn("1 peça nova: Esclarecimento 2.pdf", unquote_plus(r.headers["Location"]))
            r = cliente.post("/pecas-novas/" + ref)
            self.assertIn("Nenhuma peça nova", unquote_plus(r.headers["Location"]))
            radar.pecas_disponiveis = lambda s, l: ([], "o ZIP das peças não veio")
            r = cliente.post("/pecas-novas/" + ref)
            self.assertIn("o ZIP das peças não veio", unquote_plus(r.headers["Location"]))
        finally:
            radar.pecas_disponiveis = antigo
        # sem pecas trazidas nao ha com que comparar
        outro = self._anuncio("50/2026", docs_estado="")
        r = cliente.post("/pecas-novas/" + outro)
        self.assertIn("Traz primeiro", unquote_plus(r.headers["Location"]))

    def test_o_aviso_da_peca_nova_le_se_no_resumo_e_no_html(self):
        # o `antes` é vazio: sem caso próprio saía " -> Errata 2.pdf"
        linha = {"ref": "30/2026", "campo": radar.CAMPO_PECA_NOVA, "antes": "",
                 "depois": "Errata 2.pdf", "titulo": "Aquisição de serviços",
                 "entidade": "Câmara", "id": 1}
        texto = radar.texto_do_resumo([], [linha])
        htm = radar.html_do_resumo([], [linha])
        self.assertIn("peça nova na plataforma: Errata 2.pdf", texto)
        self.assertIn("peça nova na plataforma: <b>Errata 2.pdf</b>", htm)
        self.assertNotIn("-> Errata 2.pdf", texto)



class TestNomeRadarGov(unittest.TestCase):
    """14/09/2026: «a aplicação diz RadarDR mas tem de dizer RadarGov e
    Gov tem de ser a azul». O nome esta em dois sitios (a barra e o ecra
    de entrar) e o azul da barra e um claro proprio: o --azul da paleta
    sobre a barra escura dava 2,3:1."""

    def test_o_nome_e_radargov_nos_dois_sitios_e_o_gov_e_azul(self):
        # o logotipo ganhou a classe do estado aceso e o title a
        # 16/09/2026, quando passou a ser o caminho para o Hoje
        self.assertIn('Radar<span>Gov</span></a>', radar.BASE)
        self.assertIn('class="logo %(inicio_on)s" href="/"', radar.BASE)
        self.assertIn('<div class="logo">Radar<span>Gov</span></div>', radar.PAGINA_ENTRAR)
        self.assertIn("RadarGov", radar.PAGINA_ENTRAR)
        self.assertNotIn("Radar<span>DR", radar.BASE + radar.PAGINA_ENTRAR)
        self.assertIn(".marca .logo span{color:var(--azul-claro)}", radar.CSS)
        self.assertIn(".entrar .logo span{color:var(--azul)}", radar.CSS)
        # o claro le-se sobre a barra: AA para texto grande e mais
        contraste = TestContrasteNosFundosReais._contraste("#7cbcf0", "#14181e")
        self.assertGreater(contraste, 7)


class TestAuditoriaDeSeguranca(BaseTemporaria):
    """A auditoria de 14/09/2026, a pedido do Afonso. O que ela apanhou e
    aqui se trava: nenhum cabeçalho de segurança; um pedido sem tecto de
    tamanho; as peças das plataformas servidas em linha fosse qual fosse
    o tipo (um .html corria no domínio do painel, com a sessão); o CSV
    a deixar passar fórmulas; redireccionamentos crus pelo Referer; e os
    ficheiros com segredos a 644/755."""

    def setUp(self):
        super().setUp()
        self.cliente = radar.app.test_client()

    def test_os_cabecalhos_vao_em_todas_as_respostas(self):
        for rota in ("/", "/entrar", "/quadro", "/configuracoes/conta"):
            with self.subTest(rota=rota):
                r = self.cliente.get(rota)
                self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(r.headers["X-Frame-Options"], "SAMEORIGIN")
                self.assertEqual(r.headers["Referrer-Policy"], "same-origin")
                csp = r.headers["Content-Security-Policy"]
                self.assertIn("frame-ancestors 'self'", csp)
                self.assertIn("form-action 'self'", csp)
                self.assertIn("object-src 'self'", csp)          # o <embed> das peças
                self.assertNotIn("https://", csp)    # nada de fora
                self.assertNotIn("Strict-Transport-Security", r.headers)   # http local
        r = self.cliente.get("/", base_url="https://localhost")
        self.assertIn("max-age=", r.headers.get("Strict-Transport-Security", ""))

    def test_um_pedido_tem_tecto(self):
        import io
        self.assertEqual(radar.app.config["MAX_CONTENT_LENGTH"], 20 * 1024 * 1024)
        r = self.cliente.post("/configuracoes/importar",
                              data={"ficheiro": (io.BytesIO(b"x" * (21 * 1024 * 1024)),
                                                 "modelo.xlsx")},
                              content_type="multipart/form-data")
        self.assertEqual(r.status_code, 413)

    def test_so_pdf_imagens_e_texto_abrem_no_browser(self):
        ref = "70/2026"
        with radar.liga() as c:
            c.execute("INSERT INTO anuncios (ref, titulo, url, texto, detalhe_lido) "
                      "VALUES (?,?,?,?,1)", (ref, "t", "https://x/anuncio-procedimento/k", "x"))
        pasta = radar.pasta_do_anuncio(ref)
        os.makedirs(pasta)
        for nome, conteudo in (("ce.pdf", b"%PDF-1.4 x"), ("nota.txt", b"ola"),
                               ("Caderno de Encargos", b"%PDF-1.4 sem extensao"),
                               ("pagina.html", b"<script>alert(1)</script>"),
                               ("desenho.svg", b"<svg onload=alert(1)/>"),
                               ("macro.xlsm", b"PK")):
            with open(os.path.join(pasta, nome), "wb") as f:
                f.write(conteudo)
        for nome in ("ce.pdf", "nota.txt", "Caderno de Encargos"):
            r = self.cliente.get("/documento/%s/%s" % (quote(ref, safe=""), nome))
            self.assertEqual(r.status_code, 200)
            self.assertNotIn("attachment", r.headers.get("Content-Disposition", ""))
            self.assertNotEqual(r.headers.get("Content-Security-Policy"), "sandbox")
            self.assertNotEqual(r.mimetype, "application/octet-stream")
        r = self.cliente.get("/documento/%s/%s" % (quote(ref, safe=""), "Caderno de Encargos"))
        self.assertEqual(r.mimetype, "application/pdf")
        for nome in ("pagina.html", "desenho.svg", "macro.xlsm"):
            with self.subTest(nome=nome):
                r = self.cliente.get("/documento/%s/%s" % (quote(ref, safe=""), nome))
                self.assertEqual(r.status_code, 200)
                self.assertIn("attachment", r.headers["Content-Disposition"])
                self.assertEqual(r.mimetype, "application/octet-stream")
                self.assertEqual(r.headers["Content-Security-Policy"], "sandbox")
                self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")

    def test_o_csv_nao_deixa_passar_formulas(self):
        self.assertEqual(radar.celula_csv("=1+1"), "'=1+1")
        self.assertEqual(radar.celula_csv("+351"), "'+351")
        self.assertEqual(radar.celula_csv("-x"), "'-x")
        self.assertEqual(radar.celula_csv("@a"), "'@a")
        self.assertEqual(radar.celula_csv("Aquisição"), "Aquisição")
        self.assertEqual(radar.celula_csv(12.5), 12.5)
        self.assertEqual(radar.celula_csv(None), None)
        with radar.liga() as c:
            c.execute("INSERT INTO anuncios (ref, titulo, entidade, url, data_pub, estado) "
                      "VALUES (?,?,?,?,?,?)",
                      ("71/2026", "=HYPERLINK(\"http://mau\")", "Câmara",
                       "https://x/anuncio-procedimento/k", "2026-09-01", "novo"))
        csv_ = self.cliente.get("/csv?estado=").get_data(as_text=True)
        self.assertIn("'=HYPERLINK", csv_)
        # e nao ha writerow a saltar a guarda
        self.assertEqual(radar_fonte().count("escritor.writerow("), 1)

    def test_o_referer_so_volta_para_esta_aplicacao(self):
        with radar.app.test_request_context("/", headers={"Referer": "https://mau.site/x"}):
            self.assertEqual(radar.volta_ao_referer("/quadro").headers["Location"], "/quadro")
        with radar.app.test_request_context("/", headers={"Referer": "http://localhost/lista?a=1"}):
            self.assertEqual(radar.volta_ao_referer("/quadro").headers["Location"], "/lista?a=1")
        with radar.app.test_request_context("/"):
            self.assertEqual(radar.volta_ao_referer("/quadro").headers["Location"], "/quadro")
        self.assertNotIn("redirect(request.referrer", radar_fonte())

    def test_os_ficheiros_com_segredos_ficam_so_do_dono(self):
        caminho = os.path.join(self.pasta, "segredo.txt")
        with open(caminho, "w") as f:
            f.write("x")
        os.chmod(caminho, 0o644)
        radar.so_o_dono(caminho)
        self.assertEqual(os.stat(caminho).st_mode & 0o777, 0o600)
        # a base fica assim ao ligar (uma vez por processo)
        radar._BASE_PROTEGIDA.discard(radar.DB)
        os.chmod(radar.DB, 0o644)
        with radar.liga() as c:
            c.execute("SELECT 1")
        self.assertEqual(os.stat(radar.DB).st_mode & 0o777, 0o600)


def radar_fonte():
    with open(radar.__file__, encoding="utf-8") as f:
        return f.read()


class TestInteresseNoMercado(BaseTemporaria):
    """14/09/2026: «no mercado, após definir o interesse, deve também só
    aparecer o CPV marcado, tal como nos anúncios». O recorte entra por
    filtros_dos_contratos() — a lista, o CSV e os gráficos filtram os
    três por lá — e nunca por condicoes_contratos(), que serve os
    alertas e a ficha da entidade."""

    def setUp(self):
        super().setUp()
        self.cfg = dict(radar.CONFIG_INICIAL, interesse_activo=True,
                        interesse_cpv="72000000", interesse_cpv_excl="")
        self.enterContext(unittest.mock.patch.object(
            radar, "ler_config", lambda: dict(self.cfg)))

    def test_prefixos_do_cpv_le_codigos_e_palavras(self):
        self.assertEqual(radar.prefixos_do_cpv("72000000|48700000"), ["72", "487"])
        self.assertEqual(radar.prefixos_do_cpv(""), [])
        self.assertEqual(radar.prefixos_do_cpv("72267100-0"), ["722671"])

    def test_a_condicao_usa_a_tabela_dos_cpv_e_o_nao_levanta(self):
        frag, vals = radar.condicao_do_interesse_contratos(args={}, cfg=self.cfg)
        self.assertIn("contrato_cpv", frag)
        self.assertIn("cpv8 GLOB ?", frag)
        self.assertEqual(vals, ["72*"])
        frag, vals = radar.condicao_do_interesse_contratos(
            args={}, cfg=dict(self.cfg, interesse_cpv_excl="72212000"))
        self.assertIn("NOT IN", frag)
        self.assertEqual(vals, ["72*", "72212*"])
        self.assertEqual(radar.condicao_do_interesse_contratos(
            args={"interesse": "nao"}, cfg=self.cfg), ("", []))
        self.assertEqual(radar.condicao_do_interesse_contratos(
            args={}, cfg=dict(self.cfg, interesse_activo=False)), ("", []))
        self.assertEqual(radar.condicao_do_interesse_contratos(
            args={}, cfg=dict(self.cfg, interesse_cpv="")), ("", []))

    def test_o_interesse_e_uma_pergunta(self):
        # 14/09/2026: «abre-se e nao se ve contrato nenhum» -- com
        # interesse definido o Mercado abre logo com os CPV da empresa
        from werkzeug.datastructures import MultiDict
        self.assertTrue(radar.pergunta_feita(MultiDict(), "contratos", self.cfg))
        self.assertTrue(radar.pergunta_feita(MultiDict({"ver": "fim"}), "renovacoes", self.cfg))
        # levantado, ou sem interesse, volta a ser preciso um filtro
        self.assertFalse(radar.pergunta_feita(MultiDict({"interesse": "nao"}), "contratos", self.cfg))
        self.assertFalse(radar.pergunta_feita(MultiDict(), "contratos",
                                              dict(self.cfg, interesse_activo=False)))
        self.assertTrue(radar.pergunta_feita(MultiDict({"q": "x"}), "contratos",
                                             dict(self.cfg, interesse_activo=False)))
        # o `op` sozinho nao e pergunta
        self.assertFalse(radar.pergunta_feita(MultiDict({"op": "ou"}), "contratos",
                                              dict(self.cfg, interesse_activo=False)))

    def test_entra_pelos_filtros_da_pagina_e_nao_pelo_motor(self):
        from werkzeug.datastructures import MultiDict
        args = MultiDict({"q": "software"})
        onde, vals = radar.filtros_dos_contratos(args, cfg=self.cfg)
        self.assertIn("contrato_cpv", onde)
        self.assertEqual(vals[-1], "72*")
        onde_livre, vals_livre = radar.filtros_dos_contratos(args, com_interesse=False,
                                                              cfg=self.cfg)
        self.assertNotIn("contrato_cpv", onde_livre)
        # o motor dos alertas e da ficha da entidade nao leva o interesse
        onde_motor, _ = radar.condicoes_contratos(args)
        self.assertNotIn("contrato_cpv", onde_motor)
        # e o ?interesse=nao levanta-o tambem aqui
        onde, _ = radar.filtros_dos_contratos(MultiDict({"q": "x", "interesse": "nao"}),
                                              cfg=self.cfg)
        self.assertNotIn("contrato_cpv", onde)


class TestPlataformasQueJaNaoExistem(BaseTemporaria):
    """14/09/2026: «as plataformas que hoje já não tens acesso é porque
    já não existem — juntamos todas como outras». Saphety, compraspublicas,
    gatewit, bizgov e construlink ficam na base, mas nos selectores são
    um balde só; o filtro por nome continua a aceitar qualquer uma."""

    def setUp(self):
        super().setUp()
        # sem o interesse do config.json verdadeiro: recortava a lista
        self.enterContext(unittest.mock.patch.object(
            radar, "ler_config", lambda: dict(radar.CONFIG_INICIAL)))

    def test_agrupa_as_mortas_e_deixa_as_activas_e_as_especiais(self):
        grupos = radar.agrupar_plataformas({
            "vortal": 50, "acingov": 40, "saphety": 9, "gatewit": 3,
            "anogov": 20, radar.SEM_PLATAFORMA: 7})
        self.assertEqual(grupos, [("vortal", 50), ("acingov", 40), ("anogov", 20),
                                  (radar.OUTRAS_PLATAFORMAS, 12),
                                  (radar.SEM_PLATAFORMA, 7)])
        # sem mortas nao ha balde
        self.assertEqual(radar.agrupar_plataformas({"vortal": 1}), [("vortal", 1)])
        self.assertEqual(radar.rotulo_da_plataforma(radar.OUTRAS_PLATAFORMAS),
                         "outras (já não existem)")
        for p in radar.PLATAFORMAS_ACTIVAS:
            self.assertIn(p, radar.PLATAFORMAS)

    def test_o_filtro_outras_apanha_o_que_nao_e_activo_nem_vazio(self):
        for ref, plat, lido in (("80/2026", "saphety", 1), ("81/2026", "vortal", 1),
                                ("82/2026", "", 1), ("83/2026", "gatewit", 1),
                                ("84/2026", "bizgov", 0)):
            with radar.liga() as c:
                c.execute("INSERT INTO anuncios (ref, titulo, url, plataforma, detalhe_lido,"
                          " estado, data_pub) VALUES (?,?,?,?,?,'novo','2026-09-01')",
                          (ref, "t", "https://x/anuncio-procedimento/" + ref, plat, lido))
        onde, vals = radar.condicoes({"plat": radar.OUTRAS_PLATAFORMAS, "estado": ""})
        with radar.liga() as c:
            refs = sorted(r["ref"] for r in c.execute("SELECT ref FROM anuncios" + onde, vals))
        self.assertEqual(refs, ["80/2026", "83/2026"])
        # e por nome continua a servir (um alerta antigo com plat=saphety)
        onde, vals = radar.condicoes({"plat": "saphety", "estado": ""})
        with radar.liga() as c:
            self.assertEqual([r["ref"] for r in c.execute("SELECT ref FROM anuncios" + onde, vals)],
                             ["80/2026"])
        # os dois selectores mostram "outras" e nao as mortas
        cliente = radar.app.test_client()
        lista = cliente.get(radar.LISTA + "?estado=").get_data(as_text=True)
        alertas = cliente.get("/configuracoes/alertas").get_data(as_text=True)
        for html_ in (lista, alertas):
            self.assertIn("value='(outras)'", html_)
            self.assertIn("outras (já não existem)", html_)
            self.assertNotIn("value='saphety'", html_)
            self.assertNotIn("value='gatewit'", html_)
            self.assertIn("value='vortal'", html_)
        self.assertIn("outras (já não existem) (2)", lista)


class TestFiltrosSimples(BaseTemporaria):
    """14/09/2026: «no campo de filtros dos anúncios só quero nome do
    anúncio ou objecto; entidade; filtro de plataformas, e data x a data
    y», a árvore de CPV por cima, e a entidade a sugerir-se enquanto se
    escreve («se estou a escrever SP… ele deve sugerir as SP»)."""

    def setUp(self):
        super().setUp()
        self.enterContext(unittest.mock.patch.object(
            radar, "ler_config", lambda: dict(radar.CONFIG_INICIAL)))
        with radar.liga() as c:
            for i, ent in enumerate(("SPMS — Serviços Partilhados do Ministério da Saúde",
                                     "SPMS — Serviços Partilhados do Ministério da Saúde",
                                     "Sociedade Portuguesa de Inovação", "Câmara Municipal de Espinho",
                                     "Hospital de Espinho")):
                c.execute("INSERT INTO anuncios (ref,titulo,url,entidade,entidade_norm,estado,"
                          "data_pub,detalhe_lido) VALUES (?,?,?,?,?,'novo','2026-09-01',1)",
                          ("9%d/2026" % i, "t", "https://x/anuncio-procedimento/%d" % i,
                           ent, radar.simplifica(ent)))

    def test_a_lista_tem_so_os_quatro_campos_e_a_arvore_em_cima(self):
        html_ = radar.app.test_client().get(radar.LISTA).get_data(as_text=True)
        painel = html_.split("<details class='painel-filtros'")[1].split("</details>\n")[0]
        self.assertLess(painel.index("details class='arvore'"), painel.index("class='cx filtros'"))
        form = painel.split("class='cx filtros'")[1].split("</form>")[0]
        for campo in ("name='q'", "name='ent'", "name='plat'", "name='de'", "name='ate'"):
            self.assertIn(campo, form)
        for campo in ("name='q_excl'", "name='op'", "name='prazo'"):
            self.assertNotIn(campo, form)
        self.assertIn("type='hidden' id='filtro-cpv-excl'", form)
        self.assertIn("type='hidden' id='filtro-cpv'", form)
        # o que vier pela URL passa escondido, para nao se perder
        html_ = radar.app.test_client().get(radar.LISTA + "?prazo=urgente&op=ou").get_data(as_text=True)
        self.assertIn("<input type='hidden' name='prazo' value='urgente'>", html_)
        self.assertIn("<input type='hidden' name='op' value='ou'>", html_)
        self.assertEqual(radar.campos_escondidos({"prazo": " "}, ("prazo",)), "")

    def test_as_entidades_sugerem_se_pelo_inicio_primeiro_e_agrupadas_por_nif(self):
        nomes = [e["nome"] for e in radar.sugestoes_de_entidade("sp")]
        self.assertEqual(nomes[0], "SPMS — Serviços Partilhados do Ministério da Saúde")
        self.assertIn("Hospital de Espinho", nomes)                  # "sp" no meio
        self.assertNotIn("Sociedade Portuguesa de Inovação", nomes)   # "s p" com espaco nao e "sp"
        self.assertEqual(radar.sugestoes_de_entidade("s"), [])         # menos de duas letras
        self.assertEqual(sorted(e["nome"] for e in radar.sugestoes_de_entidade("espinho")),
                         ["Câmara Municipal de Espinho", "Hospital de Espinho"])
        # sem acentos e sem maiusculas, como o filtro
        self.assertEqual(radar.sugestoes_de_entidade("SAÚDE")[0]["nome"],
                         "SPMS — Serviços Partilhados do Ministério da Saúde")
        # 14/09/2026: «as entidades nao estao agrupadas por NIF?» -- uma
        # linha por NIF, a grafia mais frequente, a soma de todas
        with radar.liga() as c:
            c.execute("UPDATE anuncios SET nif='509540716' WHERE entidade LIKE 'SPMS%'")
            for i, ent in enumerate(("Serviços Partilhados do Ministério da Saúde, EPE",
                                     "SPMS - Servicos Partilhados, E. P. E.")):
                c.execute("INSERT INTO anuncios (ref,titulo,url,entidade,entidade_norm,nif,"
                          "estado,data_pub,detalhe_lido) VALUES (?,?,?,?,?,?,'novo','2026-09-01',1)",
                          ("8%d/2026" % i, "t", "https://x/anuncio-procedimento/8%d" % i,
                           ent, radar.simplifica(ent), "509540716"))
        # e a mesma grafia sem NIF (a base veio assim em 24%) dobra-se no
        # grupo do NIF, em vez de sair uma segunda vez com o mesmo nome
        with radar.liga() as c:
            c.execute("INSERT INTO anuncios (ref,titulo,url,entidade,entidade_norm,nif,"
                      "estado,data_pub,detalhe_lido) VALUES (?,?,?,?,?,'','novo','2026-09-01',1)",
                      ("82/2026", "t", "https://x/anuncio-procedimento/82",
                       "SPMS — Serviços Partilhados do Ministério da Saúde",
                       radar.simplifica("SPMS — Serviços Partilhados do Ministério da Saúde")))
        sugeridas = radar.sugestoes_de_entidade("partilhados")
        spms = [e for e in sugeridas if e["nif"] == "509540716"]
        self.assertEqual(len(spms), 1)
        self.assertEqual(spms[0]["nome"], "SPMS — Serviços Partilhados do Ministério da Saúde")
        self.assertEqual(spms[0]["n"], 5)
        self.assertEqual(len([e for e in sugeridas if "SPMS" in e["nome"]]), 1)
        r = radar.app.test_client().get("/entidades.json?q=esp")
        self.assertEqual(r.mimetype, "application/json")
        self.assertEqual(sorted(e["nome"] for e in r.get_json()),
                         ["Câmara Municipal de Espinho", "Hospital de Espinho"])
        self.assertIn("data-sugere='anuncios'", radar.app.test_client().get(radar.LISTA).get_data(as_text=True))
        self.assertIn("/entidades.json", radar.ENTIDADES_JS)
        self.assertIn("dataset.chaveEm", radar.ENTIDADES_JS)

    def test_o_filtro_pelo_nif_apanha_todas_as_grafias_e_as_sem_nif(self):
        with radar.liga() as c:
            # a SPMS: duas com NIF, uma grafia sem NIF (24% da base veio assim)
            c.execute("UPDATE anuncios SET nif='509540716' WHERE ref='90/2026'")
            c.execute("INSERT INTO anuncios (ref,titulo,url,entidade,entidade_norm,nif,estado,"
                      "data_pub,detalhe_lido) VALUES (?,?,?,?,?,?,'novo','2026-09-01',1)",
                      ("85/2026", "t", "https://x/anuncio-procedimento/85",
                       "Serviços Partilhados do Ministério da Saúde, EPE",
                       radar.simplifica("Serviços Partilhados do Ministério da Saúde, EPE"),
                       "509540716"))
        onde, vals = radar.condicoes({"nif": "509540716", "ent": "SPMS — Serviços Partilhados",
                                      "estado": ""})
        with radar.liga() as c:
            refs = sorted(r["ref"] for r in c.execute("SELECT ref FROM anuncios" + onde, vals))
        # 90 e 85 pelo NIF; 91 tem a mesma grafia de 90 e nao tem NIF: entra
        self.assertEqual(refs, ["85/2026", "90/2026", "91/2026"])
        self.assertNotIn("entidade_norm LIKE", onde)     # o nome nao prende a uma grafia
        # sem NIF, o texto continua a filtrar como sempre
        onde, vals = radar.condicoes({"ent": "espinho", "estado": ""})
        self.assertIn("entidade_norm LIKE", onde)
        # e o NIF entra no resumo do filtro e nos formularios
        self.assertIn("NIF 509540716", radar.resumo_filtro("nif=509540716"))
        html_ = radar.app.test_client().get(radar.LISTA + "?nif=509540716").get_data(as_text=True)
        self.assertIn("<input type='hidden' name='nif' value='509540716'>", html_)
        html_ = radar.app.test_client().get("/configuracoes/alertas").get_data(as_text=True)
        self.assertIn("name='nif'", html_.split("action='/alertas/criar'")[1].split("</form>")[0])


class TestEntidadesNoMercado(BaseTemporaria):
    """14/09/2026: «nos contratos isto não está a aparecer, só aparece nos
    anúncios» — as sugestões de entidade também no Mercado, do corpus,
    e por chave (o NIF): escolhida a sugestão, a chave vai em
    entid/vencid e o texto deixa de prender a uma grafia. E o «excluir
    palavras» e o E/OU saem também do formulário dos contratos."""

    def setUp(self):
        super().setUp()
        self.enterContext(unittest.mock.patch.object(
            radar, "CORPUS", os.path.join(self.pasta, "contratos.db")))
        radar.iniciar_corpus()                      # o esquema do corpus, vazio
        with radar.liga_corpus() as c:
            # com as colunas nomeadas: um VALUES sem elas parte-se
            # quando a tabela ganha uma coluna, e foi o que aconteceu com
            # a `compra`/`ganha` do papel (16/09/2026)
            for chave, nome, variantes in (
                    ("509540716", "SPMS - Serviços Partilhados do Ministério "
                                  "da Saúde, E. P. E.", 15),
                    ("500000001", "Sport Lisboa e Benfica", 2),
                    ("500000002", "Hospital de Espinho", 1)):
                c.execute("INSERT INTO entidades (chave, nif, nome, variantes)"
                          " VALUES (?,?,?,?)", (chave, chave, nome, variantes))
            for norm, chave in (("spms", "509540716"),
                                ("servicos partilhados do ministerio da saude epe", "509540716"),
                                ("sport lisboa e benfica", "500000001"),
                                ("hospital de espinho", "500000002")):
                c.execute("INSERT INTO entidade_nomes VALUES (?,?)", (norm, chave))
        self.enterContext(unittest.mock.patch.object(radar, "ha_corpus", lambda: 1))

    def test_sugere_do_corpus_uma_por_chave_e_pelo_inicio_primeiro(self):
        nomes = radar.sugestoes_de_entidade_do_corpus("sp")
        self.assertEqual([e["nif"] for e in nomes][:1], ["509540716"])     # "spms" comeca por sp
        self.assertEqual(nomes[0]["nome"], "SPMS - Serviços Partilhados do Ministério da Saúde, E. P. E.")
        self.assertIn("Sport Lisboa e Benfica", [e["nome"] for e in nomes])
        self.assertIn("Hospital de Espinho", [e["nome"] for e in nomes])      # "espinho" tem "sp"
        # por qualquer dos nomes por que ja apareceu, nao so o canonico
        self.assertEqual([e["nif"] for e in radar.sugestoes_de_entidade_do_corpus("partilhados")],
                         ["509540716"])
        self.assertEqual(radar.sugestoes_de_entidade_do_corpus("s"), [])
        r = radar.app.test_client().get("/entidades.json?de=contratos&q=benfica")
        self.assertEqual([e["nif"] for e in r.get_json()], ["500000001"])

    def test_com_a_chave_o_texto_nao_prende_e_sem_ela_filtra(self):
        from werkzeug.datastructures import MultiDict
        onde, vals = radar.condicoes_contratos(MultiDict({"adj": "SPMS", "entid": "509540716"}))
        self.assertIn("c.adjudicante_chave = ?", onde)
        self.assertNotIn("adjudicante_norm", onde)
        onde, vals = radar.condicoes_contratos(MultiDict({"adj": "SPMS"}))
        self.assertIn("adjudicante_norm", onde)
        onde, vals = radar.condicoes_contratos(MultiDict({"ganhou": "MEO", "vencid": "500000009"}))
        self.assertIn("WHERE chave=?", onde)
        self.assertNotIn("nome_norm LIKE", onde)
        onde, vals = radar.condicoes_contratos(MultiDict({"ganhou": "MEO"}))
        self.assertIn("nome_norm LIKE", onde)

    def test_o_formulario_dos_contratos_sugere_e_perdeu_as_exclusoes(self):
        html_ = radar.app.test_client().get("/contratos").get_data(as_text=True)
        form = html_.split("action='/contratos'")[1].split("</form>")[0]
        self.assertIn("data-sugere='contratos' data-chave-em='entid'", form)
        self.assertIn("data-sugere='contratos' data-chave-em='vencid'", form)
        self.assertIn("name='entid'", form)
        self.assertIn("name='vencid'", form)
        for campo in ("name='q_excl'", "name='op'"):
            self.assertNotIn(campo, form)
        self.assertIn("type='hidden' id='filtro-cpv-excl'", form)
        self.assertIn("datalist id='entidades-contratos'", html_)
        self.assertIn("/entidades.json", html_)
        # o que vier na URL passa escondido
        html_ = radar.app.test_client().get("/contratos?q=x&op=ou").get_data(as_text=True)
        self.assertIn("<input type='hidden' name='op' value='ou'>", html_)


class TestPaginasDeErro(BaseTemporaria):
    """15/09/2026: um 404 dava a página nua do Werkzeug e um 500 dava
    «Internal Server Error» sem ficar registado em lado nenhum. Passam
    a ter a página da empresa, e o 500 fica na marca `painel_ultimo_erro`
    e na série `erros`, que a saúde dos Indicadores mostra."""

    def setUp(self):
        super().setUp()
        self.cliente = radar.app.test_client()

    def test_404_tem_a_pagina_da_empresa(self):
        r = self.cliente.get("/isto-nao-existe")
        self.assertEqual(r.status_code, 404)
        html_ = r.get_data(as_text=True)
        self.assertIn("Não há nada aqui", html_)
        self.assertIn("href=\"/\"", html_)
        self.assertNotIn("Werkzeug", html_)

    def test_500_fica_registado_e_tem_pagina(self):
        # a vista da lista a rebentar, só durante este pedido: o Flask
        # não deixa juntar rotas depois do primeiro pedido, e a lista é
        # a página que mais se abre
        regra = "/"
        endpoint = next(x.endpoint for x in radar.app.url_map.iter_rules()
                        if x.rule == regra and "GET" in x.methods)

        def rebenta(*a, **kw):
            raise ZeroDivisionError("de propósito")
        with unittest.mock.patch.dict(radar.app.view_functions, {endpoint: rebenta}), \
                unittest.mock.patch.dict(radar.app.config, {"PROPAGATE_EXCEPTIONS": False}):
            r = self.cliente.get(regra)
        self.assertEqual(r.status_code, 500)
        html_ = r.get_data(as_text=True)
        self.assertIn("Correu mal", html_)
        self.assertNotIn("Internal Server Error", html_)
        valor = radar.le_marca("painel_ultimo_erro")
        self.assertIn("ZeroDivisionError", valor)
        self.assertIn("GET /", valor)
        with radar.liga() as c:
            n = c.execute("SELECT COUNT(*) FROM erros WHERE tipo='painel'").fetchone()[0]
        self.assertEqual(n, 1)

    def test_a_saude_dos_indicadores_mostra_o_erro(self):
        radar.marca_erro("painel_ultimo_erro", "painel", "2026-09-15 10:00 em GET /x: KeyError")
        html_ = self.cliente.get("/configuracoes/indicadores").get_data(as_text=True)
        self.assertIn("Último erro do painel", html_)
        self.assertIn("KeyError", html_)


class TestRotaDeSaude(BaseTemporaria):
    """15/09/2026: não havia nada que alguém de fora pudesse vigiar. O
    `/saude` responde «ok» sem sessão (senão o monitor caía no /entrar,
    que dá sempre 200, e nunca via o painel cair), e 503 quando a base
    não responde. Não diz nada de dentro."""
    FORA = {"REMOTE_ADDR": "203.0.113.7"}

    def setUp(self):
        super().setUp()
        self.enterContext(unittest.mock.patch.object(
            radar, "CONFIG", os.path.join(self.pasta, "config.json")))
        self.cliente = radar.app.test_client()

    def test_responde_ok_sem_sessao_e_de_fora(self):
        r = self.cliente.get("/saude", environ_base=self.FORA)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_data(as_text=True), "ok")
        self.assertEqual(r.headers.get("Cache-Control"), "no-store")
        self.assertIn("/saude", radar.ROTAS_ABERTAS)

    def test_nao_diz_nada_de_dentro(self):
        radar.marca("ultima_verificacao", "2026-09-15 09:00")
        texto = self.cliente.get("/saude", environ_base=self.FORA).get_data(as_text=True)
        self.assertNotIn("2026", texto)
        self.assertNotIn("anúncios", texto)

    def test_503_quando_a_base_nao_responde(self):
        def liga_partida():
            raise sqlite3.OperationalError("disco fora")
        with unittest.mock.patch.object(radar, "liga", liga_partida):
            r = self.cliente.get("/saude", environ_base=self.FORA)
        self.assertEqual(r.status_code, 503)


class TestEnsaioDeRestauro(BaseTemporaria):
    """15/09/2026: a cópia diária fazia-se há semanas e ninguém tinha
    provado que se restaurava. `--ensaiar-copia` abre a última cópia só
    de leitura, passa-lhe o integrity_check e conta contra a base viva;
    a marca `ultimo_ensaio_copia` fica na saúde dos Indicadores e na
    secção Cópias. Uma cópia vazia ou corrompida diz «FALHOU»."""

    def setUp(self):
        super().setUp()
        self.copias = os.path.join(self.pasta, "copias")
        self.enterContext(unittest.mock.patch.object(radar, "COPIAS", self.copias))
        with radar.liga() as c:
            for i in range(3):
                c.execute("INSERT INTO anuncios (ref, titulo, estado) VALUES (?,?,?)",
                          ("R%d" % i, "t%d" % i, "interessa" if i == 0 else "novo"))

    def test_sem_copia_nenhuma_diz_isso(self):
        with self.assertRaises(FileNotFoundError):
            radar.ensaiar_copia()

    def test_a_ultima_copia_serve_e_conta_contra_a_viva(self):
        os.makedirs(self.copias)
        velha = os.path.join(self.copias, "radar-2026-09-01.db")
        open(velha, "wb").close()          # a mais velha nunca é escolhida
        destino = radar.copia_de_seguranca(guardar=0)
        self.assertEqual(radar.ultima_copia(), destino)
        r = radar.ensaiar_copia()
        self.assertTrue(r["serve"])
        self.assertEqual(r["integridade"], "ok")
        self.assertEqual(r["contagens"]["anuncios"], (3, 3))
        self.assertEqual(r["contagens"]["triagem"], (1, 1))
        self.assertTrue(radar.le_marca("ultimo_ensaio_copia").startswith("ok: "))
        # nunca escreve na cópia: nem um -journal ao lado
        self.assertFalse(os.path.exists(destino + "-journal"))
        html_ = radar.app.test_client().get("/configuracoes/copias").get_data(as_text=True)
        self.assertIn("Ensaio de restauro: ok:", html_)
        html_ = radar.app.test_client().get("/configuracoes/indicadores").get_data(as_text=True)
        self.assertIn("Ensaio de restauro", html_)

    def test_uma_copia_vazia_nao_serve(self):
        os.makedirs(self.copias)
        vazia = os.path.join(self.copias, "radar-2026-09-10.db")
        c = sqlite3.connect(vazia)
        c.execute("CREATE TABLE anuncios (ref TEXT, estado TEXT)")
        c.execute("CREATE TABLE estado (chave TEXT, valor TEXT)")
        c.commit()
        c.close()
        r = radar.ensaiar_copia(vazia)
        self.assertFalse(r["serve"])
        self.assertEqual(r["contagens"]["anuncios"], (0, 3))
        self.assertTrue(radar.le_marca("ultimo_ensaio_copia").startswith("FALHOU"))

class CicloDasTarefas(BaseTemporaria):
    """Esqueleto das seis classes da fase 1 do `docs/historico/CICLOS.md`
    (17/09/2026): um anúncio, uma proposta, e as datas do DR a virarem
    tarefas."""

    def setUp(self):
        super().setUp()
        self.cliente = radar.app.test_client()
        self.hoje = datetime.date.today()

    def _dia(self, delta):
        return (self.hoje + datetime.timedelta(days=delta)).isoformat()

    def _anuncio(self, ref="60/2026", pub=-30, prazo=30, entidade="CML"):
        with radar.liga() as c:
            c.execute("INSERT INTO anuncios (ref, titulo, entidade, estado, "
                      "data_pub, prazo) VALUES (?,?,?,?,?,?)",
                      (ref, "Software de gestão", entidade, "novo",
                       self._dia(pub), self._dia(prazo)))
        return ref

    def _tarefas(self, ref="60/2026"):
        with radar.liga() as c:
            return c.execute("SELECT * FROM tarefas WHERE ref=? ORDER BY id",
                             (ref,)).fetchall()


class TestAutomaticaHerdaOResponsavel(CicloDasTarefas):
    """As 36 tarefas automáticas da base de 16/09/2026 tinham **zero**
    responsáveis, mesmo quando a proposta tinha um: o INSERT do
    `sincronizar_tarefas()` não escrevia a coluna `quem`. Uma lista de
    «o que há para fazer» onde nada diz de quem é não distribui trabalho
    nenhum.

    E a outra metade da regra (D-b): uma tarefa a que alguém já pôs nome
    **não se reescreve**. Se herdasse sempre, mudar o responsável da
    proposta apagava em silêncio a atribuição feita à mão.
    """

    def test_nasce_com_o_responsavel_da_proposta(self):
        ref = self._anuncio()
        id_ = radar.criar_proposta(ref, estado="analisar")
        radar.gravar_campos_da_proposta(id_, ["responsavel"], ["Ana"])
        radar.sincronizar_tarefas(ref)
        self.assertTrue(self._tarefas())
        for t in self._tarefas():
            self.assertEqual(t["quem"], "Ana", t["o_que"])

    def test_uma_tarefa_com_nome_nao_se_reescreve(self):
        ref = self._anuncio()
        id_ = radar.criar_proposta(ref, estado="analisar")
        primeira = self._tarefas()[0]["id"]
        radar.gravar_tarefa(primeira, quem="Maria")
        radar.gravar_campos_da_proposta(id_, ["responsavel"], ["Ana"])
        radar.sincronizar_tarefas(ref)
        donos = {t["id"]: t["quem"] for t in self._tarefas()}
        self.assertEqual(donos[primeira], "Maria")
        self.assertEqual(set(donos.values()), {"Maria", "Ana"})

    def test_continua_idempotente(self):
        """Herdar o dono não pode fazer a sincronização deixar de ser
        idempotente: a segunda volta tem de dar (0, 0, 0)."""
        ref = self._anuncio()
        id_ = radar.criar_proposta(ref, estado="analisar")
        radar.gravar_campos_da_proposta(id_, ["responsavel"], ["Ana"])
        radar.sincronizar_tarefas(ref)
        self.assertEqual(radar.sincronizar_tarefas(ref), (0, 0, 0))


class TestPrazoPassadoNaoMexeEmNada(CicloDasTarefas):
    """A prova da D2 do `CICLOS.md`, palavra dele: «tenho receio com essas
    tarefas assim automáticas; posso não ter passado para submetido por
    esquecimento e ele vai passar para não fomos».

    Uma automática cujo prazo já passou, numa proposta que continua na
    escada, **não se apaga, não se fecha e não move a proposta**. Só o
    Hoje a mostra num balde próprio, e quem decide é a pessoa.
    """

    def test_nada_se_move_nem_se_apaga(self):
        ref = self._anuncio(pub=-60, prazo=-3)
        id_ = radar.criar_proposta(ref, estado="analisar")
        antes = self._tarefas()
        self.assertTrue(antes)
        self.assertEqual(radar.sincronizar_tarefas(ref), (0, 0, 0))
        depois = self._tarefas()
        self.assertEqual([t["id"] for t in depois], [t["id"] for t in antes])
        for t in depois:
            self.assertIsNone(t["feita_em"], t["o_que"])
        self.assertEqual(radar.proposta(id_)["estado"], "analisar")
        self.assertIsNone(radar.proposta(id_)["fechada_em"])

    def test_a_consulta_encontra_a_proposta_e_nao_lhe_toca(self):
        ref = self._anuncio(pub=-60, prazo=-3)
        id_ = radar.criar_proposta(ref, estado="analisar")
        paradas = radar.propostas_sem_decisao(self.hoje)
        self.assertEqual([p["id"] for p in paradas], [id_])
        # uma já decidida não aparece, mesmo com o prazo passado
        radar.mover_proposta(id_, "submetido", campos={"valor_proposta": "118.500,00 EUR"})
        self.assertEqual(radar.propostas_sem_decisao(self.hoje), [])


class TestAberturaRedesenhada(CicloDasTarefas):
    """O redesenho de 17/09/2026 («Radar Gov UI redesign», §1).

    Cada teste desta classe é um erro que o desenho antigo tinha e que
    este veio resolver -- ou uma armadilha que o novo desenho abriu e
    que se apanhou a escrevê-lo.
    """

    def _uma(self, quando=0, quem="", o_que="pedir os CVs"):
        ref = self._anuncio(entidade="Câmara de Leiria")
        id_ = radar.criar_proposta(ref, estado="proposta")
        with radar.liga() as c:
            c.execute("DELETE FROM tarefas")
        t = radar.criar_tarefa(o_que, self._dia(quando),
                               proposta_id=id_, ref=ref)
        if quem:
            radar.gravar_tarefa(t, quem=quem)
        return ref, id_, t

    def test_riscar_uma_tarefa_volta_a_linha_e_nao_ao_topo(self):
        """**A queixa principal** dele sobre a abertura: «concluo a
        tarefa e volto para o início da página».

        Numa lista de cinquenta tarefas, reencontrar onde se ia custa
        mais do que o gesto que se fez. A resposta é a âncora `#t<id>`
        no redireccionamento -- e vale para o «feita» e para o
        «desfazer», que é o mesmo gesto ao contrário.
        """
        _, _, t = self._uma()
        for caminho in ("feita", "por-fazer"):
            r = self.cliente.post("/tarefa/%d/%s" % (t, caminho),
                                  headers={"Referer": "http://localhost/"})
            self.assertIn(r.status_code, (301, 302, 303), caminho)
            self.assertTrue(r.headers["Location"].endswith("#t%d" % t),
                            "%s: %s" % (caminho, r.headers["Location"]))

    def test_a_linha_feita_fica_no_sitio_riscada_e_com_desfazer(self):
        """Antes, marcar uma tarefa fazia-a desaparecer: o gesto ficava
        sem confirmação e sem volta, que é o erro mais fácil de cometer
        numa lista grande."""
        _, _, t = self._uma()
        radar.marcar_tarefa(t, True)
        corpo = self.cliente.get("/").get_data(as_text=True)
        self.assertIn("class='hj-row feita' id='t%d'" % t, corpo)
        self.assertIn("/tarefa/%d/por-fazer" % t, corpo)
        # e com «esconder as feitas» sai do ecrã, sem deixar de existir
        escondido = self.cliente.get(
            "/?feitas=esconder").get_data(as_text=True)
        self.assertNotIn("id='t%d'" % t, escondido)

    def test_o_dia_escolhido_na_fita_muda_o_balde_do_meio(self):
        """A fita veio comprar exactamente isto: ver a quinta-feira sem
        sair da página nem ir ao calendário."""
        ref, id_, hoje_t = self._uma(quando=0, o_que="a de hoje")
        t = radar.criar_tarefa("a de daqui a dois dias", self._dia(2),
                               proposta_id=id_, ref=ref)
        # hoje, a tarefa de daqui a dois dias não está no balde do meio
        hoje = self.cliente.get("/").get_data(as_text=True)
        self.assertIn("Hoje &middot;", hoje)
        meio = hoje[hoje.index("Hoje &middot;"):]
        meio = meio[:meio.index("</div>", meio.index("id='t"))]
        self.assertIn("id='t%d'" % hoje_t, meio)
        self.assertNotIn("id='t%d'" % t, meio)
        # escolhendo o dia dela, o balde do meio passa a ser esse dia
        escolhido = self.cliente.get(
            "/?dia=" + self._dia(2)).get_data(as_text=True)
        self.assertIn(radar.dia_por_extenso(
            self.hoje + datetime.timedelta(days=2)), escolhido)
        self.assertIn("id='t%d'" % t, escolhido)

    def test_a_fita_conta_o_mesmo_que_o_balde_das_atrasadas(self):
        """A regra da empresa, apanhada a olhar para a página real: a
        célula de hoje dizia «19 atrasadas arrastam» ao lado de um balde
        «Atrasadas 14».

        A fita contava a lista de onde os baldes saem, e os baldes
        escondem as automáticas das propostas sem decisão (D2) — duas
        populações, dois números do mesmo facto no mesmo ecrã.
        """
        ref = self._anuncio(entidade="Câmara de Leiria")
        with radar.liga() as c:
            c.execute("UPDATE anuncios SET prazo=? WHERE ref=?",
                      (self._dia(-5), ref))
            c.execute("DELETE FROM tarefas")
        id_ = radar.criar_proposta(ref, estado="proposta")
        # uma automática de uma proposta cujo prazo já passou: não se
        # desenha em balde nenhum, e por isso não pode contar na fita
        automatica = radar.criar_tarefa("entregar a proposta", self._dia(-5),
                                        proposta_id=id_, ref=ref)
        with radar.liga() as c:
            c.execute("UPDATE tarefas SET origem='entrega' WHERE id=?",
                      (automatica,))
        # e uma escrita à mão, que se desenha nas atrasadas
        radar.criar_tarefa("ligar ao Dr. X", self._dia(-1),
                           proposta_id=id_, ref=ref)
        corpo = self.cliente.get("/").get_data(as_text=True)
        self.assertIn("Prazo passou sem decisão", corpo)
        self.assertEqual(corpo.count("class='hj-row"), 1)
        self.assertIn("1 atrasada arrasta", corpo)
        self.assertNotIn("2 atrasadas arrastam", corpo)

    def test_um_dia_estragado_volta_a_hoje_em_vez_de_rebentar(self):
        """Um `?dia=` que não é uma data chega por um link colado ou por
        um dedo enganado, e não é erro: a página é do dia de hoje."""
        for mau in ("ontem", "2026-13-45", "", "0000"):
            r = self.cliente.get("/?dia=" + mau)
            self.assertEqual(r.status_code, 200, mau)
            self.assertIn(radar.dia_por_extenso(self.hoje),
                          r.get_data(as_text=True), mau)

    def test_o_filtro_por_pessoa_distingue_todos_de_sem_dono(self):
        """São três respostas e não duas: ausente = todos, `?quem=` =
        sem dono, `?quem=X` = do X. Um `or ""` a meio disto fazia o «sem
        dono» mostrar tudo."""
        ref = self._anuncio(entidade="Câmara de Leiria")
        id_ = radar.criar_proposta(ref, estado="proposta")
        with radar.liga() as c:
            c.execute("DELETE FROM tarefas")
        da_ana = radar.criar_tarefa("com dono", self._dia(0),
                                    proposta_id=id_, ref=ref)
        radar.gravar_tarefa(da_ana, quem="Ana")
        sozinha = radar.criar_tarefa("sem dono", self._dia(0),
                                     proposta_id=id_, ref=ref)

        todos = self.cliente.get("/").get_data(as_text=True)
        self.assertIn("id='t%d'" % da_ana, todos)
        self.assertIn("id='t%d'" % sozinha, todos)

        so_ana = self.cliente.get("/?quem=Ana").get_data(as_text=True)
        self.assertIn("id='t%d'" % da_ana, so_ana)
        self.assertNotIn("id='t%d'" % sozinha, so_ana)

        vagas = self.cliente.get("/?quem=").get_data(as_text=True)
        self.assertNotIn("id='t%d'" % da_ana, vagas)
        self.assertIn("id='t%d'" % sozinha, vagas)

    def test_mudar_de_dia_nao_perde_o_filtro_da_pessoa(self):
        """Os dois controlos reescrevem o MESMO endereço, e cada um só
        mexe no seu parâmetro: sem isso, escolher um dia deitava fora o
        filtro da pessoa e ninguém percebia porquê."""
        self._uma(quem="Ana")
        corpo = self.cliente.get("/?quem=Ana").get_data(as_text=True)
        self.assertIn("quem=Ana", corpo)
        # a fita reescreve só o `dia=` e leva o `quem=` que já lá estava
        self.assertIn("/?quem=Ana&amp;dia=%s" % self._dia(0), corpo)
        # e o «esconder as feitas» faz o mesmo com o seu
        self.assertIn("/?quem=Ana&amp;feitas=esconder", corpo)

    def test_a_dica_do_concurso_nao_leva_entidades_escritas(self):
        """Apanhado a escrever isto: o `&middot;` da coluna ia para o
        `title=` já escapado, e a dica dizia «60/2026 &amp;middot;
        Câmara». É a mesma armadilha do `ultima_mensagem` -- guarda-se o
        carácter, não a entidade."""
        self._uma()
        corpo = self.cliente.get("/").get_data(as_text=True)
        self.assertNotIn("&amp;middot;", corpo)
        self.assertIn("title='60/2026 · Câmara de Leiria'", corpo)

    def test_adiar_todas_pergunta_antes_e_so_mexe_nas_atrasadas(self):
        """Doze linhas vermelhas de ontem, cada uma com o seu
        formulário, eram doze viagens para dizer a mesma coisa. Mas não
        há desfazer -- cada tarefa tinha a sua data --, e por isso
        pergunta-se."""
        ref = self._anuncio(entidade="Câmara de Leiria")
        id_ = radar.criar_proposta(ref, estado="proposta")
        with radar.liga() as c:
            c.execute("DELETE FROM tarefas")
        velha = radar.criar_tarefa("de ontem", self._dia(-1),
                                   proposta_id=id_, ref=ref)
        futura = radar.criar_tarefa("da semana que vem", self._dia(7),
                                    proposta_id=id_, ref=ref)
        pergunta = self.cliente.get("/tarefas/adiar").get_data(as_text=True)
        self.assertIn("Não há desfazer", pergunta)
        self.cliente.post("/tarefas/adiar")
        with radar.liga() as c:
            datas = {r["id"]: r["quando"] for r in
                     c.execute("SELECT id, quando FROM tarefas")}
        self.assertEqual(datas[velha], self._dia(0))
        self.assertEqual(datas[futura], self._dia(7))

    def test_o_periodo_do_ponto_de_situacao_recorta_mesmo(self):
        """Um período que não recorta nada é um selector decorativo: a
        taxa contava tudo desde sempre em qualquer das quatro opções."""
        ref = self._anuncio()
        id_ = radar.criar_proposta(ref, estado="ganho")
        with radar.liga() as c:
            c.execute("UPDATE propostas SET fechada_em='2020-01-15 09:00' "
                      "WHERE id=?", (id_,))
        # sem janela conta; numa janela recente, não
        self.assertEqual(radar.taxa_de_vitoria()[0][2], 1)
        janela, _, _ = radar.janelas_do_periodo("mes", self.hoje)
        self.assertEqual(radar.taxa_de_vitoria(janela=janela), [])
        self.assertEqual(radar.ganho_no_periodo(janela)[1], 0)
        # e "tudo" não tem janela nenhuma, por desenho
        self.assertEqual(radar.janelas_do_periodo("tudo", self.hoje)[0], None)

    def test_o_periodo_anterior_tem_o_mesmo_tamanho(self):
        """Comparar um trimestre com o ano todo daria um «▼» garantido e
        sem significado."""
        hoje = datetime.date(2026, 9, 17)
        janela, antes, _ = radar.janelas_do_periodo("mes", hoje)
        self.assertEqual(janela, ("2026-09-01", "2026-09-17"))
        self.assertEqual(antes, ("2026-08-01", "2026-08-31"))
        janela, antes, _ = radar.janelas_do_periodo("trimestre", hoje)
        self.assertEqual(janela, ("2026-07-01", "2026-09-17"))
        self.assertEqual(antes, ("2026-04-01", "2026-06-30"))

    def test_a_data_e_o_dia_dizem_se_em_portugues(self):
        """O `strftime("%A")` responde na língua do SISTEMA -- num
        servidor em inglês saía «Wednesday» no meio de uma aplicação
        inteira em português, que é a mesma avaria do `<input
        type=date>` corrigida a 15/09/2026."""
        d = datetime.date(2026, 9, 16)
        self.assertEqual(radar.dia_por_extenso(d), "Quarta, 16 de setembro")
        self.assertEqual(radar.data_curta(d), "16 set")
        self.assertEqual(radar.data_curta("2026-12-01"), "1 dez")
        self.assertEqual(radar.data_curta("nada", vazio="—"), "nada")
        self.assertEqual(radar.iniciais("Afonso Pinto"), "AP")
        self.assertEqual(radar.iniciais("Ana"), "AN")
        self.assertEqual(radar.iniciais(""), "")


class TestHojeAgrupaSemDecisao(CicloDasTarefas):
    """O balde «prazo passou sem decisão» (fase 1). Sem ele, as dezasseis
    automáticas de Julho e Agosto apareciam nas «atrasadas» a dizer
    «entregar a proposta» um mês depois do prazo -- trabalho que já não
    existe a tapar o que existe.

    As escritas à mão dessas propostas continuam onde a data as põe:
    «ligar ao Dr. X» não deixa de fazer sentido por o prazo ter passado.
    """

    def test_a_automatica_nao_aparece_duas_vezes(self):
        ref = self._anuncio(pub=-60, prazo=-3)
        id_ = radar.criar_proposta(ref, estado="analisar")
        a_mao = radar.criar_tarefa("ligar ao Dr. X", self._dia(-1),
                                   proposta_id=id_, ref=ref)
        tarefas = radar._tarefas_por_fazer()
        paradas = radar.propostas_sem_decisao(self.hoje)
        _, grupos = radar._grupos_das_tarefas(tarefas, self.hoje, paradas)
        self.assertEqual([p["id"] for p, _ in grupos["sem_decisao"]], [id_])
        # nas atrasadas fica SÓ a escrita à mão. O balde deixou de
        # agrupar por proposta a 17/09/2026 -- o concurso passou a ser
        # uma COLUNA da linha, e um cabeçalho de grupo por cima de uma
        # linha só era mais altura do que informação.
        atrasadas = [t["id"] for t, _ in grupos["atrasadas"]]
        self.assertEqual(atrasadas, [a_mao])

    def test_o_balde_desenha_se_com_o_selector_da_ranhura(self):
        ref = self._anuncio(pub=-60, prazo=-3)
        id_ = radar.criar_proposta(ref, estado="analisar")
        corpo = self.cliente.get("/").get_data(as_text=True)
        self.assertIn("Prazo passou sem decisão", corpo)
        # a ranhura muda-se ali, sem ir à ficha
        self.assertIn("/proposta/%d/escada" % id_, corpo)

    def test_o_numero_do_kpi_conta_as_linhas_que_se_desenham(self):
        """A regra da empresa. Com as automáticas escondidas, um KPI que
        continuasse a contar `len(tarefas)` prometia mais linhas do que
        as que a âncora abre."""
        ref = self._anuncio(pub=-60, prazo=-3)
        id_ = radar.criar_proposta(ref, estado="analisar")
        radar.criar_tarefa("ligar ao Dr. X", self._dia(-1),
                           proposta_id=id_, ref=ref)
        corpo = self.cliente.get("/").get_data(as_text=True)
        self.assertEqual(corpo.count("class='hj-row"), 1)
        self.assertIn("1 para fazer", corpo)


class TestLinhaDaTarefaDizOConcurso(CicloDasTarefas):
    """«Tenho lá 30 tarefas, mal consigo perceber o concurso que cada uma
    delas é» (16/09/2026). A linha mostrava a data, o texto e o título,
    e mais nada -- nem a referência, nem a ranhura, nem a entidade, nem
    quem.

    E agrupam-se por proposta (D-c): 55 tarefas são ~25 concursos, e o
    cabeçalho do grupo é o concurso.
    """

    def test_a_linha_traz_ref_ranhura_entidade_e_quem(self):
        ref = self._anuncio(entidade="Câmara de Leiria")
        id_ = radar.criar_proposta(ref, estado="proposta")
        radar.gravar_campos_da_proposta(id_, ["responsavel"], ["Ana"])
        radar.sincronizar_tarefas(ref)
        corpo = self.cliente.get("/").get_data(as_text=True)
        # A ranhura saiu da linha no redesenho de 17/09/2026 (era do
        # cabeçalho do grupo, que deixou de existir): o que a queixa
        # pedia -- «mal consigo perceber o concurso que cada uma delas
        # é» -- é a ref e a entidade, e essas estão na própria linha,
        # mais o avatar de quem.
        for pedaco in ("60/2026", "Câmara de Leiria", "AN"):
            self.assertIn(pedaco, corpo, pedaco)
        self.assertIn("title='Ana'", corpo)

    def test_cada_linha_diz_o_concurso_sem_cabecalho_de_grupo(self):
        """O agrupamento por proposta deu lugar a uma COLUNA do concurso
        em cada linha (redesenho de 17/09/2026).

        A queixa que o agrupamento resolvia -- «mal consigo perceber o
        concurso que cada uma delas é» -- continua resolvida, e sem o
        cabeçalho: três tarefas do mesmo concurso eram quatro linhas de
        altura para três de trabalho.
        """
        ref = self._anuncio(entidade="Câmara de Leiria")
        id_ = radar.criar_proposta(ref, estado="proposta")
        with radar.liga() as c:
            c.execute("DELETE FROM tarefas")
        for n in range(3):
            radar.criar_tarefa("tarefa %d" % n, self._dia(2),
                               proposta_id=id_, ref=ref)
        corpo = self.cliente.get("/").get_data(as_text=True)
        self.assertEqual(corpo.count("class='hj-row"), 3)
        # o cabeçalho de grupo já não existe
        self.assertNotIn("class='hj-p'", corpo)
        # e as três linhas dizem, cada uma, de que concurso são
        self.assertEqual(corpo.count("60/2026 &middot; Câmara de Leiria"), 3)
        for n in range(3):
            self.assertIn("tarefa %d" % n, corpo)


class TestTarefaResolveSeDeQualquerPagina(CicloDasTarefas):
    """Concluir uma tarefa só existia na ficha do anúncio, e o «desfazer»
    do `/tarefa/<id>/feita` **nunca apareceu**: o `envolver()` só
    desenhava o botão para caminhos que começassem por `/estado/`.

    Adiar e atribuir não existiam de todo.
    """

    def _uma(self):
        ref = self._anuncio()
        id_ = radar.criar_proposta(ref, estado="proposta")
        return radar.criar_tarefa("escrever o esclarecimento", self._dia(2),
                                  proposta_id=id_, ref=ref)

    def test_feita_a_partir_da_abertura_volta_com_o_desfazer(self):
        t = self._uma()
        r = self.cliente.post("/tarefa/%d/feita" % t,
                              headers={"Referer": "http://localhost/"})
        self.assertIn(r.status_code, (301, 302, 303))
        destino = r.headers["Location"]
        self.assertIn("desfazer=%2Ftarefa%2F", destino)
        corpo = self.cliente.get(destino).get_data(as_text=True)
        self.assertIn("/tarefa/%d/por-fazer" % t, corpo)
        self.assertIn(">desfazer<", corpo)

    def test_adiar_e_atribuir_sao_a_mesma_rota(self):
        t = self._uma()
        self.cliente.post("/tarefa/%d/gravar" % t,
                          data={"quando": "31/12/2026"},
                          headers={"Referer": "http://localhost/"})
        self.cliente.post("/tarefa/%d/gravar" % t, data={"quem": "Ana"},
                          headers={"Referer": "http://localhost/"})
        with radar.liga() as c:
            linha = c.execute("SELECT * FROM tarefas WHERE id=?",
                              (t,)).fetchone()
        self.assertEqual(linha["quando"], "2026-12-31")
        self.assertEqual(linha["quem"], "Ana")

    def test_data_ilegivel_recusa_e_nao_apaga_o_prazo(self):
        t = self._uma()
        antes = self._tarefas()[-1]["quando"]
        ok, recado = radar.gravar_tarefa(t, quando="amanhã")
        self.assertFalse(ok)
        self.assertIn("não é uma data", recado)
        with radar.liga() as c:
            linha = c.execute("SELECT quando FROM tarefas WHERE id=?",
                              (t,)).fetchone()
        self.assertEqual(linha["quando"], antes)

    def test_um_campo_vazio_no_formulario_nao_apaga_nada(self):
        """O formulário da linha tem sempre os dois campos desenhados, e
        manda-os vazios quando não se escreve neles."""
        t = self._uma()
        antes = self._tarefas()[-1]["quando"]
        self.cliente.post("/tarefa/%d/gravar" % t,
                          data={"quando": "", "quem": ""},
                          headers={"Referer": "http://localhost/"})
        with radar.liga() as c:
            linha = c.execute("SELECT quando FROM tarefas WHERE id=?",
                              (t,)).fetchone()
        self.assertEqual(linha["quando"], antes)

    def test_a_garantia_e_da_funcao_e_nao_do_chamador(self):
        """Apanhado pelo `code-reviewer` a 17/09/2026: a rota filtrava os
        campos vazios, mas `gravar_tarefa(id_, quando="")` gravava NULL —
        apagava o prazo em silêncio, que é exactamente o que o docstring
        dela diz que não faz. Um chamador novo (outra rota, um script de
        manutenção) herdava a avaria."""
        t = self._uma()
        antes = self._tarefas()[-1]
        self.assertTrue(antes["quando"])
        ok, _ = radar.gravar_tarefa(t, quando="", quem="   ")
        self.assertTrue(ok)
        with radar.liga() as c:
            linha = c.execute("SELECT quando, quem FROM tarefas WHERE id=?",
                              (t,)).fetchone()
        self.assertEqual(linha["quando"], antes["quando"])
        self.assertEqual(linha["quem"], antes["quem"])


class TestPropostaSemAnuncioTemTarefas(CicloDasTarefas):
    """Uma tarefa de uma proposta sem anúncio não tinha onde se riscar: o
    `/proposta/<id>` não chamava o `_tarefas_da_ficha()`, e o atalho da
    ficha do anúncio não existe para quem não tem `ref`."""

    def test_a_ficha_mostra_a_tarefa_e_o_botao_de_feita(self):
        id_ = radar.criar_proposta(entidade="IPLeiria", titulo="Consulta",
                                   porque_sem_ref="consulta prévia")
        t = radar.criar_tarefa("preparar a consulta", self._dia(3),
                               proposta_id=id_)
        corpo = self.cliente.get("/proposta/%d" % id_).get_data(as_text=True)
        self.assertIn("preparar a consulta", corpo)
        self.assertIn("/tarefa/%d/feita" % t, corpo)
        self.assertIn("/tarefa/%d/gravar" % t, corpo)


class CicloDaEntidade(BaseTemporaria):
    """Esqueleto das classes da fase 2 do `docs/historico/CICLOS.md`
    (17/09/2026): a ficha da entidade deixa de ser só do Portal BASE."""

    def setUp(self):
        super().setUp()
        self.cliente = radar.app.test_client()
        # **Sem corpus, de propósito.** A `BaseTemporaria` não aponta o
        # `CORPUS` para a pasta temporária, e por isso o `ha_corpus()`
        # lia o `contratos.db` verdadeiro dele (2,5 GB) — o resultado
        # destes testes passava a depender do que lá está. É a mesma
        # armadilha do `config.json`, apanhada a 16/09/2026.
        self.enterContext(unittest.mock.patch.object(
            radar, "ha_corpus", lambda: 0))

    def _anuncio(self, ref, nif="506000000", entidade="IPLeiria",
                 titulo="Software"):
        with radar.liga() as c:
            c.execute("INSERT INTO anuncios (ref, titulo, entidade, nif, "
                      "estado, data_pub, prazo, titulo_norm, entidade_norm) "
                      "VALUES (?,?,?,?,?,?,?,?,?)",
                      (ref, titulo, entidade, nif, "novo", "2026-09-01",
                       "2026-12-01", radar.simplifica(titulo),
                       radar.simplifica(entidade)))
        return ref


class TestEntidadeSemCorpusTemFicha(CicloDaEntidade):
    """Uma entidade sem contrato celebrado no corpus dava **404**, mesmo
    com dezenas de anúncios no Diário da República — e é a mais provável
    de interessar, porque o concurso ainda não foi adjudicado. O
    `entidade()` começava por `ha_corpus()` e nunca chegava a olhar para
    a base do radar.

    D3 do plano, palavra dele: «todas as entidades e empresas devem ter
    ficha».
    """

    def test_a_ficha_existe_so_com_anuncios(self):
        self._anuncio("60/2026")
        r = self.cliente.get("/entidade/506000000")
        self.assertEqual(r.status_code, 200)
        corpo = r.get_data(as_text=True)
        self.assertIn("IPLeiria", corpo)
        self.assertIn("O Portal BASE não conhece esta entidade", corpo)

    def test_uma_chave_que_nao_existe_em_lado_nenhum_da_404(self):
        self.assertEqual(
            self.cliente.get("/entidade/999999999").status_code, 404)

    def test_o_nome_do_anuncio_leva_sempre_a_ficha(self):
        """Sem corpus o nome saía como texto, e não havia caminho
        nenhum para a entidade."""
        self._anuncio("60/2026")
        corpo = self.cliente.get("/anuncio/60%2F2026").get_data(as_text=True)
        self.assertIn("/entidade/506000000", corpo)


class TestFichaDaEntidadeDizOLadoDaEmpresa(CicloDaEntidade):
    """A ficha não mostrava os anúncios do DR dessa entidade, nem as
    nossas propostas com ela, nem os contactos — que são «da entidade»
    por desenho e só se viam dentro de um anúncio."""

    def test_as_propostas_aparecem_e_a_taxa_diz_de_quantos_e(self):
        self._anuncio("60/2026")
        self._anuncio("61/2026", titulo="Manutenção")
        radar.mover_proposta(radar.criar_proposta("60/2026"), "ganho",
                             campos={"valor_proposta": "10.000,00 EUR"})
        radar.mover_proposta(radar.criar_proposta("61/2026"), "perdido",
                             campos={"valor_proposta": "9.000,00 EUR",
                                     "motivo": radar.MOTIVOS_PERDA[0]})
        corpo = self.cliente.get("/entidade/506000000").get_data(as_text=True)
        self.assertIn("As nossas propostas", corpo)
        self.assertIn("Software", corpo)
        self.assertIn("Manutenção", corpo)
        # dois decididos não chegam para uma taxa, e o ecrã di-lo
        self.assertIn("a taxa diz-se a partir de %d"
                      % radar.MINIMO_COM_ENTIDADE, corpo)

    def test_com_decididos_que_cheguem_a_taxa_aparece(self):
        for n in range(radar.MINIMO_COM_ENTIDADE):
            ref = self._anuncio("%d/2026" % (70 + n))
            radar.mover_proposta(
                radar.criar_proposta(ref), "ganho" if n else "perdido",
                campos={"valor_proposta": "10.000,00 EUR",
                        "motivo": radar.MOTIVOS_PERDA[0]})
        d = radar.lado_da_empresa("506000000", "IPLeiria")
        self.assertEqual(d["decididos"], radar.MINIMO_COM_ENTIDADE)
        self.assertIsNotNone(d["taxa"])

    def test_o_numero_dos_anuncios_abre_exactamente_essa_lista(self):
        """A regra da empresa: o número e a ligação têm de dar a mesma
        população. Aqui é por construção — o filtro é o mesmo objecto
        nos dois sítios (`filtro_dos_anuncios_da_entidade()`)."""
        self._anuncio("60/2026")
        self._anuncio("61/2026")
        self._anuncio("62/2026", nif="500000001", entidade="Outra")
        d = radar.lado_da_empresa("506000000", "IPLeiria")
        self.assertEqual(d["anuncios"], 2)
        corpo = self.cliente.get("/entidade/506000000").get_data(as_text=True)
        self.assertIn("<b>2</b> anúncios", corpo)
        # e a lista que a ligação abre tem exactamente esses dois
        lista = self.cliente.get(
            radar.LISTA + "?" + urlencode(dict(d["filtro"], estado=""))
        ).get_data(as_text=True)
        self.assertIn("60/2026", lista)
        self.assertIn("61/2026", lista)
        self.assertNotIn("62/2026", lista)


class TestContactoNasceNaEntidade(CicloDaEntidade):
    """Os contactos são da ENTIDADE por desenho, e até 17/09/2026 só se
    viam e criavam dentro de um anúncio dela."""

    def test_criado_na_ficha_da_entidade_aparece_no_anuncio(self):
        self._anuncio("60/2026")
        r = self.cliente.post("/contacto/nova",
                              data={"chave": "506000000", "nome": "Maria",
                                    "email": "maria@ipl.pt",
                                    "entidade": "IPLeiria"},
                              headers={"Referer": "http://localhost/"})
        self.assertIn(r.status_code, (301, 302, 303))
        for pagina in ("/entidade/506000000", "/anuncio/60%2F2026"):
            corpo = self.cliente.get(pagina).get_data(as_text=True)
            self.assertIn("Maria", corpo, pagina)

    def test_a_chave_de_um_contacto_sem_nif_e_a_mesma_do_corpus(self):
        """Eram duas escritas do mesmo facto: o corpus guardava
        `n:<nome>` e os contactos guardavam o nome sem prefixo. A ficha
        da entidade não achava os contactos dela, e um NIF que chegasse
        mais tarde partia a ligação em silêncio."""
        a = {"nif": "", "entidade": "Junta de Freguesia de Anos"}
        self.assertEqual(radar.chave_da_entidade(a),
                         radar.chave_entidade("", a["entidade"]))
        self.assertTrue(radar.chave_da_entidade(a).startswith("n:"))
        # e quem PROCURA tenta as duas: o NIF e o nome
        com_nif = {"nif": "506000000", "entidade": "IPLeiria"}
        self.assertEqual(radar.chaves_da_entidade(com_nif),
                         ["506000000", "n:" + radar.norma_entidade("IPLeiria")])

    def test_a_migracao_poe_o_prefixo_e_e_idempotente(self):
        with radar.liga() as c:
            c.execute("INSERT INTO contactos (entidade_chave, entidade, nome) "
                      "VALUES (?,?,?)", ("junta de freguesia de anos",
                                         "Junta de Anos", "Rui"))
            c.execute("INSERT INTO contactos (entidade_chave, entidade, nome) "
                      "VALUES (?,?,?)", ("506000000", "IPLeiria", "Ana"))
        for _ in range(2):
            radar.iniciar_db()
        with radar.liga() as c:
            chaves = sorted(r["entidade_chave"] for r in
                            c.execute("SELECT entidade_chave FROM contactos"))
        self.assertEqual(chaves, ["506000000", "n:junta de freguesia de anos"])


class TestListaDeEntidades(CicloDaEntidade):
    """Não havia lista de entidades. À ficha de uma só se chegava por três
    caminhos, e o formulário «Ficha de entidade» não era `href` de lado
    nenhum."""

    def test_a_lista_existe_e_mostra_com_quem_trabalhamos(self):
        self._anuncio("60/2026")
        radar.criar_proposta("60/2026")
        r = self.cliente.get("/entidades")
        self.assertEqual(r.status_code, 200)
        corpo = r.get_data(as_text=True)
        self.assertIn("Com quem trabalhamos", corpo)
        self.assertIn("IPLeiria", corpo)
        self.assertIn("/entidade/506000000", corpo)
        self.assertIn("1 proposta", corpo)

    def test_e_uma_vista_do_mercado_na_barra(self):
        mercado = next(n for n in radar.NAV if n[0] == "mercado")
        self.assertIn("entidades", [v[0] for v in mercado[3]])
        self.assertEqual(radar.ITEM_DA_PAGINA["entidades"], "mercado")

    def test_a_procura_sem_termo_vai_para_a_lista(self):
        r = self.cliente.get("/entidade/procurar")
        self.assertIn(r.status_code, (301, 302, 303))
        self.assertIn("/entidades", r.headers["Location"])

    def test_sem_corpus_a_procura_acha_o_nosso_lado(self):
        self._anuncio("60/2026")
        radar.criar_proposta("60/2026")
        r = self.cliente.get("/entidade/procurar?q=IPLeiria")
        self.assertIn(r.status_code, (301, 302, 303))
        self.assertIn("/entidade/506000000", r.headers["Location"])


class TestEntidadesRedesenhadas(CicloDaEntidade):
    """O redesenho de 17/09/2026, §3 e §4 («Radar Gov UI redesign»).

    Eram quatro blocos empilhados de nomes soltos, e comparar duas
    entidades obrigava a abrir duas fichas em separadores. Estas classes
    correm **sem corpus** (ver `CicloDaEntidade`): é o caso em que mais
    fácil era a página parecer avariada, e é o que o §5 cobre.
    """

    def _com_propostas(self, estados):
        """Propostas em estados escolhidos, escritos à mão na base.

        Não pelo `mover_proposta()`: a condicionante da informação em
        falta (D4) exige campos para entrar em «Ganho» e «Perdido», e o
        que estes testes medem é o que a lista DESENHA, não a escada."""
        self._anuncio("60/2026")
        for n, estado in enumerate(estados):
            id_ = radar.criar_proposta("60/2026", lote=n + 1)
            with radar.liga() as c:
                c.execute("UPDATE propostas SET estado=? WHERE id=?",
                          (estado, id_))
        return "506000000"

    def test_as_cinco_abas_existem_e_a_ver_escolhe(self):
        self._anuncio("60/2026")
        radar.criar_proposta("60/2026")
        corpo = self.cliente.get("/entidades").get_data(as_text=True)
        for _, rotulo in radar.ABAS_DAS_ENTIDADES:
            self.assertIn(rotulo, corpo, rotulo)
        # a aba pedida acende, e uma inventada volta à primeira
        seguidas = self.cliente.get(
            "/entidades?ver=seguidas").get_data(as_text=True)
        self.assertIn("class='on' href='/entidades?ver=seguidas'", seguidas)
        self.assertIn("Não segues nenhuma entidade", seguidas)
        inventada = self.cliente.get("/entidades?ver=xpto")
        self.assertEqual(inventada.status_code, 200)
        self.assertIn("class='on' href='/entidades?ver=nossas'",
                      inventada.get_data(as_text=True))

    def test_a_fita_tem_um_quadrado_por_proposta_e_a_cor_do_desfecho(self):
        """«6 propostas» não diz se correram bem; seis quadrados dizem-no
        antes de se ler a taxa."""
        self._com_propostas(["ganho", "perdido", "submetido"])
        corpo = self.cliente.get("/entidades").get_data(as_text=True)
        fita = corpo[corpo.index("ent-fita"):]
        fita = fita[:fita.index("</span>")]
        self.assertEqual(fita.count("<i style="), 3)
        self.assertIn("var(--verde)", fita)
        self.assertIn("var(--verm)", fita)
        self.assertIn("3 propostas", corpo)
        self.assertIn("1 em curso", corpo)

    def test_a_taxa_connosco_cala_se_abaixo_do_minimo(self):
        """Uma taxa sobre dois concursos é ruído com ar de facto -- a
        mesma regra do `MINIMO_COM_ENTIDADE` na ficha."""
        self._com_propostas(["ganho", "perdido"])
        corpo = self.cliente.get("/entidades").get_data(as_text=True)
        self.assertIn("1 de 2 — poucos", corpo)
        self.assertNotIn("50%", corpo)

    def test_sem_corpus_diz_sem_base_e_o_caminho_para_o_trazer(self):
        """Um «0» nas colunas do mercado é uma afirmação sobre o mercado;
        a afirmação verdadeira é «não sei» (redesenho §5)."""
        self._anuncio("60/2026")
        radar.criar_proposta("60/2026")
        corpo = self.cliente.get("/entidades").get_data(as_text=True)
        self.assertIn("sem BASE", corpo)
        self.assertIn("Actualizar contratos", corpo)
        self.assertIn("/configuracoes/indicadores", corpo)
        self.assertEqual(radar.a_acabar_por_entidade(), {})

    def test_comparar_precisa_de_duas_marcadas(self):
        """A comparação é entre DUAS: com uma só, ou com três, não se
        desenha nada -- um painel de comparação com uma coluna é um
        controlo que mente sobre o que faz."""
        self._anuncio("60/2026")
        radar.criar_proposta("60/2026")
        self._anuncio("61/2026", nif="500000002", entidade="Hospital")
        radar.criar_proposta("61/2026")
        uma = self.cliente.get(
            "/entidades?vs=506000000").get_data(as_text=True)
        self.assertNotIn("A comparar", uma)
        duas = self.cliente.get(
            "/entidades?vs=506000000&vs=500000002").get_data(as_text=True)
        self.assertIn("A comparar", duas)
        self.assertIn("A quem compra", duas)
        self.assertIn("deixar de comparar", duas)

    def test_a_ficha_abre_com_seis_factos(self):
        """Eram dois cartões, «Compra» e «Ganha», e os dois diziam o
        acervo inteiro. A pergunta comercial é sobre a janela recente,
        sobre o nosso CPV e sobre o que já fizemos com ela."""
        self._com_propostas(["ganho", "perdido"])
        corpo = self.cliente.get(
            "/entidade/506000000").get_data(as_text=True)
        for rotulo in ("Compra · 24 m", "No nosso CPV", "Fecha a",
                       "Connosco", "Taxa connosco", "A acabar · 90 d"):
            self.assertIn(rotulo, corpo, rotulo)
        # seis células, e não o `sit-numeros` que as embrulha -- o
        # `count("sit-n")` apanhava as duas coisas e dava sete
        self.assertEqual(corpo.count("<span class='r'>"), 6)
        # sem corpus, os três do mercado dizem-no
        self.assertIn("sem BASE", corpo)
        # e a taxa não se inventa
        self.assertIn("a taxa diz-se a partir de %d" % radar.MINIMO_COM_ENTIDADE,
                      corpo)


class TestPropostaGuardaAChaveDaEntidade(CicloDaEntidade):
    """É o que liga uma proposta à ficha da entidade e aos contactos dela
    sem comparar nomes — e uma proposta sem anúncio (D2) não tem `ref`
    por onde lá chegar."""

    def test_criar_proposta_preenche_a_chave(self):
        self._anuncio("60/2026")
        p = radar.proposta(radar.criar_proposta("60/2026"))
        self.assertEqual(p["entidade_chave"], "506000000")

    def test_uma_proposta_sem_anuncio_tira_a_chave_do_nome(self):
        p = radar.proposta(radar.criar_proposta(entidade="Junta de Anos",
                                                titulo="Consulta"))
        self.assertEqual(p["entidade_chave"],
                         radar.chave_entidade("", "Junta de Anos"))

    def test_a_migracao_enche_as_antigas_e_e_idempotente(self):
        self._anuncio("60/2026")
        id_ = radar.criar_proposta("60/2026")
        with radar.liga() as c:
            c.execute("UPDATE propostas SET entidade_chave=NULL")
        for _ in range(2):
            radar.iniciar_db()
        self.assertEqual(radar.proposta(id_)["entidade_chave"], "506000000")

    def test_a_coluna_entra_na_exportacao_da_triagem(self):
        """O B15 exporta as propostas coluna a coluna; uma coluna nova
        que fique de fora perde-se num restauro."""
        with radar.liga() as c:
            nas_propostas = {r["name"] for r in
                             c.execute("PRAGMA table_info(propostas)")}
        self.assertEqual(nas_propostas, set(radar.COLUNAS_DA_PROPOSTA))


class TestEscadaExigeOQueARanhuraPede(CicloDaEntidade):
    """A condicionante da informação em falta (D4 do
    `docs/historico/CICLOS.md`), palavra dele a 16/09/2026: «eu não posso
    passar um por analisar directo para ganho porque há informação que
    não foi preenchida».

    Qualquer par de ranhuras continua permitido — não há percurso
    obrigatório, e voltar atrás é reabrir. O que trava é o campo que faz
    a ranhura ser verdade.
    """

    def _p(self):
        self._anuncio("60/2026")
        return radar.criar_proposta("60/2026")

    def test_sem_o_preco_o_ganho_recusa_e_diz_o_que_falta(self):
        p = self._p()
        ok, recado = radar.mover_proposta(p, "ganho")
        self.assertFalse(ok)
        self.assertIn("preço proposto", recado)
        self.assertEqual(radar.proposta(p)["estado"], "analisar")

    def test_com_o_campo_no_mesmo_pedido_passa(self):
        p = self._p()
        ok, recado = radar.mover_proposta(
            p, "ganho", campos={"valor_proposta": "118.500,00 EUR"})
        self.assertTrue(ok, recado)
        self.assertEqual(radar.proposta(p)["estado"], "ganho")
        self.assertEqual(radar.proposta(p)["valor_proposta"],
                         "118.500,00 EUR")

    def test_reabrir_nao_pede_nada(self):
        """Voltar a uma ranhura aberta é reabrir, e reabrir não é
        afirmar coisa nenhuma."""
        p = self._p()
        radar.mover_proposta(p, "ganho",
                             campos={"valor_proposta": "118.500,00 EUR"})
        ok, _ = radar.mover_proposta(p, "analisar")
        self.assertTrue(ok)
        self.assertEqual(radar.proposta(p)["estado"], "analisar")
        self.assertIsNone(radar.proposta(p)["fechada_em"])

    def test_o_relatorio_pede_dois_e_o_recado_di_lo(self):
        p = self._p()
        ok, recado = radar.mover_proposta(p, "relatorio")
        self.assertFalse(ok)
        self.assertIn("preço proposto", recado)
        self.assertIn("lugar", recado)
        # com um só continua a faltar o outro
        ok, recado = radar.mover_proposta(
            p, "relatorio", campos={"valor_proposta": "1.000,00 EUR"})
        self.assertFalse(ok)
        self.assertIn("lugar", recado)
        ok, _ = radar.mover_proposta(p, "relatorio", campos={"lugar": 2})
        self.assertTrue(ok)

    def test_um_motivo_da_outra_ranhura_nao_serve(self):
        """As duas listas não são a mesma: «Preço base baixo» é porque
        não se foi, e não é resposta a «porque se perdeu»."""
        p = self._p()
        radar.gravar_motivo(p, radar.MOTIVOS_ABANDONO[0])
        ok, recado = radar.mover_proposta(
            p, "perdido", campos={"valor_proposta": "1.000,00 EUR"})
        self.assertFalse(ok)
        self.assertIn("motivo", recado)
        ok, _ = radar.mover_proposta(
            p, "perdido", campos={"motivo": radar.MOTIVOS_PERDA[0]})
        self.assertTrue(ok)

    def test_qualquer_par_de_ranhuras_e_permitido(self):
        """A escada é livre: não há percurso obrigatório. O que trava é
        a informação, e não a ordem."""
        p = self._p()
        ok, _ = radar.mover_proposta(
            p, "ganho", campos={"valor_proposta": "1.000,00 EUR"})
        self.assertTrue(ok)          # analisar -> ganho, sem passar pelo meio
        ok, _ = radar.mover_proposta(
            p, "nao_fomos", campos={"motivo": radar.MOTIVOS_ABANDONO[0]})
        self.assertTrue(ok)          # e de ganho para não fomos

    def test_entrar_na_escada_de_uma_vez_tambem_passa_pela_regra(self):
        """Apanhado pela revisão de código a 17/09/2026: sem proposta
        prévia, o `mudar_estado()` criava-a já na ranhura pedida e nunca
        passava pelo `mover_proposta()`. Um `POST /estado/<ref>/ganho`
        num anúncio por ver punha um «Ganho» sem preço proposto,
        contornando em silêncio a regra que esta fase introduziu.

        E a recusa **não deixa a proposta criada**: uma linha a mais por
        um gesto que não passou é pior do que a recusa."""
        self._anuncio("60/2026")
        r = self.cliente.post("/estado/60%2F2026/ganho",
                              headers={"Referer": "http://localhost/"})
        self.assertIn("aviso", r.headers["Location"])
        self.assertEqual(radar.propostas_de("60/2026"), [])
        # com o campo, passa — e o campo fica gravado
        self.cliente.post("/estado/60%2F2026/ganho",
                          data={"valor_proposta": "118.500,00 EUR"},
                          headers={"Referer": "http://localhost/"})
        p = radar.propostas_de("60/2026")[0]
        self.assertEqual((p["estado"], p["valor_proposta"]),
                         ("ganho", "118.500,00 EUR"))

    def test_uma_aspa_no_titulo_nao_sai_do_atributo_do_confirm(self):
        """Também da revisão: o `confirmar` do `accao()` era interpolado
        cru dentro de `onsubmit="return confirm('…')"`, com os chamadores
        a trocarem só a plica. Uma aspa dupla num nome escrito pelo
        utilizador — o título de uma proposta, o nome de um contacto —
        fechava o atributo."""
        mau = 'Consulta " onmouseover=alert(1) x="'
        p = radar.criar_proposta(entidade="IPL", titulo=mau)
        corpo = self.cliente.get("/proposta/%d" % p).get_data(as_text=True)
        # o texto aparece — escapado. O que não pode aparecer é a aspa
        # CRUA a fechar um atributo antes dele.
        self.assertIn("onmouseover", corpo)
        self.assertNotIn('" onmouseover=alert(1)', corpo)
        self.assertNotIn("' onmouseover=alert(1)", corpo)
        # e a função em si: nada de aspas nem de plicas por escapar
        saida = radar.accao("/x", "ok", confirmar="a\"b'c")
        self.assertNotIn('"a"b', saida)
        self.assertIn("&quot;", saida)

    def test_o_selector_da_linha_pode_trazer_os_campos(self):
        p = self._p()
        r = self.cliente.post("/proposta/%d/escada" % p,
                              data={"estado": "submetido",
                                    "valor_proposta": "118.500,00 EUR"},
                              headers={"Referer": "http://localhost/"})
        self.assertIn(r.status_code, (301, 302, 303))
        self.assertEqual(radar.proposta(p)["estado"], "submetido")


class TestPropostaSemAnuncioTemPaginaInteira(CicloDaEntidade):
    """A página de uma proposta sem anúncio era só o formulário que o
    `/proposta/<id>/gravar` recebe: sem tarefas, sem contactos, sem
    histórico. E o `/proposta/<id>/apagar` existia sem que HTML nenhum o
    desenhasse."""

    def _p(self):
        return radar.criar_proposta(entidade="IPLeiria", titulo="Consulta",
                                    porque_sem_ref="consulta prévia")

    def test_a_pagina_tem_o_bloco_inteiro(self):
        p = self._p()
        radar.criar_tarefa("preparar a consulta", "2026-12-01", proposta_id=p)
        radar.criar_contacto(radar.chave_entidade("", "IPLeiria"), "Maria",
                             entidade="IPLeiria")
        corpo = self.cliente.get("/proposta/%d" % p).get_data(as_text=True)
        self.assertIn("A nossa proposta", corpo)
        self.assertIn("/proposta/%d/escada" % p, corpo)   # selector da ranhura
        self.assertIn("preparar a consulta", corpo)       # tarefas
        self.assertIn("Maria", corpo)                     # contactos
        self.assertIn("Cronologia", corpo)                # histórico
        self.assertIn("/proposta/%d/apagar" % p, corpo)   # o apagar existe

    def test_o_apagar_volta_a_ranhura_de_onde_veio(self):
        p = self._p()
        estado = radar.proposta(p)["estado"]
        r = self.cliente.post("/proposta/%d/apagar" % p,
                              headers={"Referer": "http://localhost/"})
        self.assertIn(r.status_code, (301, 302, 303))
        destino = r.headers["Location"]
        self.assertIn(radar.LISTA, destino)
        self.assertIn("estado=" + estado, destino)
        self.assertIsNone(radar.proposta(p))

    def test_a_ligacao_para_a_ficha_da_entidade(self):
        p = self._p()
        corpo = self.cliente.get("/proposta/%d" % p).get_data(as_text=True)
        self.assertIn("/entidade/" + quote(
            radar.chave_entidade("", "IPLeiria"), safe=""), corpo)


class TestHistoricoDaPropostaSemRef(CicloDaEntidade):
    """O `historico` de uma proposta sem `ref` gravava-se com `ref=""` e
    perdia-se: nada o voltava a encontrar, e a cronologia dela estava a
    ser escrita para o vazio."""

    def test_a_mudanca_de_ranhura_fica_com_proposta_id(self):
        p = radar.criar_proposta(entidade="IPLeiria", titulo="Consulta")
        radar.mover_proposta(p, "submetido",
                             campos={"valor_proposta": "1.000,00 EUR"})
        with radar.liga() as c:
            linhas = c.execute("SELECT * FROM historico WHERE proposta_id=? "
                               "ORDER BY id", (p,)).fetchall()
        self.assertIn("estado", [l["accao"] for l in linhas])
        self.assertIn("proposta criada", [l["accao"] for l in linhas])
        corpo = self.cliente.get("/proposta/%d" % p).get_data(as_text=True)
        self.assertIn("Cronologia", corpo)
        self.assertIn("Submetido", corpo)

    def test_a_migracao_da_coluna_e_idempotente(self):
        for _ in range(2):
            radar.iniciar_db()
        with radar.liga() as c:
            colunas = {r["name"] for r in
                       c.execute("PRAGMA table_info(historico)")}
        self.assertIn("proposta_id", colunas)


class TestLeituraIncompletaVoltaATentar(BaseTemporaria):
    """O terceiro beco sem saída das peças (fase 4 do
    `docs/historico/CICLOS.md`): «o tecto do dia bateu» gravava a leitura
    parcial em `analise` e **ninguém voltava a tentar**. O `--ler-pecas`
    só escolhia quem não tem linha nenhuma em `analise` (`a.ref IS
    NULL`), e a verificação nunca relia. Uma leitura que apanhou o
    objecto e perdeu a equipa ficava assim para sempre.

    E a condição separa-se da espera, como o `CLAUDE.md` manda: o
    fornecedor é um duplo que conta chamadas, e a asserção é sobre
    **quantas vezes** se chamou — não sobre um `sleep` aterrar a tempo.
    """

    def setUp(self):
        super().setUp()
        with radar.liga() as c:
            c.execute("INSERT INTO anuncios (ref, titulo, estado) "
                      "VALUES ('60/2026','Software','novo')")
            c.execute("INSERT INTO anuncios (ref, titulo, estado) "
                      "VALUES ('61/2026','Manutenção','novo')")
            # uma a meio, na escada; uma completa, na escada
            c.execute("INSERT INTO analise (ref, objecto, equipa, "
                      "documentos_proposta, quando) VALUES "
                      "('60/2026','o objecto','', 'os documentos','2026-09-10')")
            c.execute("INSERT INTO analise (ref, objecto, equipa, "
                      "documentos_proposta, quando) VALUES "
                      "('61/2026','o objecto','a equipa','os docs','2026-09-10')")
        radar.criar_proposta("60/2026")
        radar.criar_proposta("61/2026")

    def test_a_incompleta_e_escolhida_e_a_completa_nao(self):
        self.assertEqual(radar.refs_com_leitura_incompleta(), ["60/2026"])
        with radar.liga() as c:
            linhas = {r["ref"]: r for r in c.execute("SELECT * FROM analise")}
        self.assertTrue(radar.analise_incompleta(linhas["60/2026"]))
        self.assertFalse(radar.analise_incompleta(linhas["61/2026"]))

    def test_so_o_que_esta_na_escada_gasta_orcamento(self):
        """Reler um concurso que ninguém olhou é tirar o orçamento do dia
        a um que se vai entregar."""
        with radar.liga() as c:
            c.execute("DELETE FROM propostas WHERE ref='60/2026'")
        self.assertEqual(radar.refs_com_leitura_incompleta(), [])
        # à mão (`--ler-pecas`) não há esse recorte: quem corre o comando
        # está a pedir que se leia o que falta
        self.assertEqual(
            radar.refs_com_leitura_incompleta(so_na_escada=False), ["60/2026"])

    def test_com_a_cadeia_esgotada_nao_se_chama_o_modelo(self):
        vezes = []

        def falso(ref):
            vezes.append(ref)
            return True, ""

        with unittest.mock.patch.object(radar, "analisar_pecas", falso), \
             unittest.mock.patch.object(radar, "cadeia_de_fornecedores",
                                        lambda: [("groq", "k", "m")]), \
             unittest.mock.patch.object(radar, "cadeia_esgotada",
                                        lambda cadeia: True):
            feitas, aviso = radar.reler_incompletas()
        self.assertEqual(vezes, [])
        self.assertEqual(feitas, 0)
        self.assertEqual(aviso, radar.SEM_ORCAMENTO_HOJE)

    def test_com_orcamento_rele_e_para_ao_primeiro_sem_orcamento(self):
        """Três incompletas, e a segunda responde «sem orçamento»: a
        terceira não se chega a pedir."""
        with radar.liga() as c:
            for n in (62, 63):
                c.execute("INSERT INTO anuncios (ref, titulo, estado) "
                          "VALUES (?,?,'novo')", ("%d/2026" % n, "t"))
                c.execute("INSERT INTO analise (ref, objecto, equipa, "
                          "documentos_proposta, quando) VALUES (?,?,?,?,?)",
                          ("%d/2026" % n, "", "", "", "2026-09-09"))
        # fora do `with`: o `criar_proposta()` abre a sua própria ligação,
        # e a base fica trancada contra si mesma
        for n in (62, 63):
            radar.criar_proposta("%d/2026" % n)
        vezes = []

        def falso(ref):
            vezes.append(ref)
            return (False, radar.SEM_ORCAMENTO_HOJE) if len(vezes) == 2 \
                else (True, "")

        with unittest.mock.patch.object(radar, "analisar_pecas", falso), \
             unittest.mock.patch.object(radar, "cadeia_de_fornecedores",
                                        lambda: [("groq", "k", "m")]), \
             unittest.mock.patch.object(radar, "cadeia_esgotada",
                                        lambda cadeia: False):
            feitas, aviso = radar.reler_incompletas()
        self.assertEqual(len(vezes), 2)
        self.assertEqual(feitas, 1)
        self.assertEqual(aviso, radar.SEM_ORCAMENTO_HOJE)

    def test_a_condicao_verdadeira_contra_o_recurso_verdadeiro(self):
        """O teste pequeno que exercita o `cadeia_esgotada()` a sério,
        para a condição ficar coberta e não só o duplo dela."""
        radar._ESGOTADOS.clear()
        self.addCleanup(radar._ESGOTADOS.clear)
        cadeia = [("groq", "k", "m")]
        self.assertFalse(radar.cadeia_esgotada(cadeia))
        radar.marcar_esgotado("groq")
        self.assertTrue(radar.cadeia_esgotada(cadeia))


class TestOFunilContaPropostasENaoOEstadoDoAnuncio(BaseTemporaria):
    """17/09/2026, encontrado a medir porque é que a abertura demorava.

    O funil da triagem contava `anuncios.estado IN ('interessa',
    'descartado')` — e essas palavras **saíram do `anuncios` a
    15/09/2026**, quando a decisão da empresa passou para a tabela
    `propostas`. A coluna só tem `novo` e `alteracao`.

    Resultado: «Triados 0 · Interessa 0» na abertura, todos os dias, e o
    bloco por CPV vazio. **Zeros são plausíveis**, e foi por isso que
    ninguém viu durante dois dias. E custava 0,22 s por carregamento —
    86% da página — a varrer 210 mil anúncios para devolver zeros.

    O que cada lado responde: os anúncios dizem o que é do DR (quantos
    entraram, quantos ninguém tocou); as propostas dizem o que é decisão
    nossa. É a mesma divisão do `contar_a_escada()`.
    """

    def setUp(self):
        super().setUp()
        hoje = datetime.date.today()
        with radar.liga() as c:
            for n in range(4):
                c.execute(
                    "INSERT INTO anuncios (ref, titulo, entidade, estado, "
                    "data_pub, prazo, cpv, titulo_norm, entidade_norm) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    ("%d/2026" % (60 + n), "Software", "CML", "novo",
                     hoje.isoformat(),
                     (hoje + datetime.timedelta(days=30)).isoformat(),
                     "72000000", "software", "cml"))
        # duas na escada aberta, uma «não fomos», uma por ver
        radar.mover_proposta(radar.criar_proposta("60/2026"), "submetido",
                             campos={"valor_proposta": "1.000,00 EUR"})
        radar.criar_proposta("61/2026")
        radar.mover_proposta(radar.criar_proposta("62/2026"), "nao_fomos",
                             campos={"motivo": radar.MOTIVOS_ABANDONO[0]})

    def _funil(self):
        with radar.app.test_request_context("/"):
            return radar.funil_anuncios()

    def test_os_triados_sao_os_que_tem_proposta(self):
        f = self._funil()
        self.assertEqual(f["triados"], 3)          # 60, 61 e 62
        self.assertEqual(f["entrados"], 4)         # o DR publicou quatro
        self.assertEqual(f["porver_30"], 1)        # só o 63 ficou por ver

    def test_interessa_e_estar_numa_ranhura_aberta(self):
        f = self._funil()
        self.assertEqual(f["interessa"], 2)        # submetido e por analisar
        self.assertEqual(f["descartados"], 1)      # o «não fomos»

    def test_o_bloco_por_cpv_deixa_de_vir_vazio(self):
        """Era `WHERE estado NOT IN ('novo','alteracao')` sobre o
        `anuncios` — uma condição que nenhuma linha satisfaz."""
        f = self._funil()
        self.assertEqual([dict(r) for r in f["por_divisao"]],
                         [{"div": "72", "sim": 2, "nao": 1, "tudo": 3}])

    def test_nenhuma_consulta_do_funil_procura_o_vocabulario_antigo(self):
        """A garantia contra a reincidência: o `anuncios.estado` só tem
        `novo` e `alteracao`, e qualquer comparação com as palavras da
        empresa nesta função é um zero à espera de acontecer."""
        fonte = inspect.getsource(radar.funil_anuncios)
        codigo = "\n".join(l for l in fonte.splitlines()
                           if not l.strip().startswith("#"))
        for palavra in ("'interessa'", "'descartado'"):
            self.assertNotIn(palavra, codigo, palavra)

    def test_a_abertura_mostra_os_numeros_e_nao_zeros(self):
        # O funil da triagem é a aba «Triagem» do Ponto de situação
        # desde 17/09/2026; até aí vivia no fim da abertura.
        corpo = radar.app.test_client().get(
            "/situacao?ver=triagem").get_data(as_text=True)
        bloco = corpo[corpo.index("Entrados"):]
        bloco = bloco[:bloco.index("</div></div>") + 12]
        self.assertIn("Triados", bloco)
        # o valor do «Triados» é o 3, e não um 0
        self.assertNotIn("<span class='v'>0</span>", bloco)


class TestAFolhaDeEstiloNaoViajaEmCadaClique(BaseTemporaria):
    """17/09/2026: o CSS estava embutido num `<style>` em **todas** as
    páginas — 85 KB, 58% de cada resposta, e o browser não o podia
    guardar. Localmente não se notava; pelo túnel do `radargov.pt`, cada
    navegação voltava a arrastá-lo.

    Passou a `/estilo/<etiqueta>.css`, com a etiqueta a ser o resumo do
    próprio conteúdo: o browser guarda-o para sempre, e mudar uma linha
    de CSS muda o endereço — não há cache velha possível.
    """

    FORA = {"REMOTE_ADDR": "203.0.113.7"}

    def setUp(self):
        super().setUp()
        self.cliente = radar.app.test_client()

    def test_a_pagina_deixou_de_levar_o_css_dentro(self):
        corpo = self.cliente.get("/").get_data(as_text=True)
        self.assertIn(radar.FOLHA_CSS, corpo)
        self.assertNotIn("<style>", corpo)
        # a folha inteira não pode estar lá dentro: procura-se uma regra
        # que só existe no CSS, não a marcação
        self.assertNotIn(".hj-l{display:grid", corpo)

    def test_a_folha_serve_se_com_cache_para_sempre(self):
        r = self.cliente.get(radar.FOLHA_CSS)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.headers["Content-Type"].startswith("text/css"))
        self.assertIn("immutable", r.headers["Cache-Control"])
        self.assertEqual(r.get_data(as_text=True), radar.CSS_TUDO)

    def test_uma_etiqueta_velha_da_404_e_nao_o_css_novo(self):
        """Senão um endereço guardado apontava para conteúdo mudado, que
        é exactamente o que o resumo no nome existe para impedir."""
        self.assertEqual(
            self.cliente.get("/estilo/aaaaaaaaaaaa.css").status_code, 404)

    def test_a_etiqueta_muda_quando_o_css_muda(self):
        outra = radar.hashlib.sha256(
            (radar.CSS_TUDO + "\n.x{color:red}").encode("utf-8")
        ).hexdigest()[:12]
        self.assertNotEqual(outra, radar.ETIQUETA_CSS)

    def test_o_movimento_vem_da_pasta_e_nao_de_um_dominio_de_fora(self):
        """As curvas e os keyframes são do Open Props, alojados em
        `estilo/`. Um `@import` de CDN morria à chegada: o painel envia
        `default-src 'self'`."""
        self.assertIn("--ease-3:", radar.CSS_TUDO)
        self.assertIn("@keyframes fade-in", radar.CSS_TUDO)
        self.assertNotIn("@import", radar.CSS_TUDO)
        self.assertNotIn("https://", radar.CSS_TUDO)

    def test_quem_pede_menos_movimento_nao_recebe_nenhum(self):
        """O bloco está DENTRO do `prefers-reduced-motion:
        no-preference`, e não desligado a seguir: assim quem pediu menos
        movimento nunca chega a receber um fotograma."""
        marca = "@media (prefers-reduced-motion: no-preference)"
        self.assertIn(marca, radar.CSS_TUDO)
        # o `rindex` e não o `index`: o comentário que explica a regra
        # cita-a acima dela, e um `split()[1]` ingénuo apanhava o
        # comentário em vez do bloco (foi o que aconteceu ao escrever
        # isto). O bloco é o ÚLTIMO, que é o que o browser lê.
        depois = radar.CSS_TUDO[radar.CSS_TUDO.rindex(marca):]
        bloco = depois[:depois.index("\n}")]
        for regra in (".flash{animation:", "dialog.modal[open]{animation:"):
            self.assertIn(regra, bloco, regra)
        # e nenhuma delas pode existir FORA do bloco
        self.assertEqual(radar.CSS_TUDO.count(".flash{animation:"), 1)

    def test_sem_a_pasta_o_painel_serve_na_mesma(self):
        """Perde-se a suavidade, não a página: os `estilo/*.css` são um
        acrescento, e o `BASE_DIR` dos testes é uma pasta temporária que
        não os tem — é esse o caso que isto exercita."""
        self.assertEqual(radar.carregar_estilos_de_terceiros(), "")
        self.assertEqual(self.cliente.get("/").status_code, 200)

    def test_a_folha_abre_sem_sessao(self):
        """O ecrã de entrar precisa dela **antes** de haver sessão. Sem
        isto aparecia em branco e sem letra — e é o primeiro ecrã de
        quem abre o radargov.pt de fora."""
        import contas
        with radar.liga() as c:
            contas.criar_utilizador(c, "afonso", "palavra-passe-comprida",
                                    "admin")
        anonimo = radar.app.test_client()
        r = anonimo.get(radar.FOLHA_CSS, environ_base=self.FORA)
        self.assertEqual(r.status_code, 200)
        # e o ecrã de entrar aponta-lhe
        entrar = anonimo.get("/entrar", environ_base=self.FORA)
        self.assertIn(radar.FOLHA_CSS, entrar.get_data(as_text=True))


class TestAsPecasMudamDePastaSozinhas(unittest.TestCase):
    """19/09/2026: `documentos/` passou a `pecas/`, por queixa dele —
    «temos uma pasta que é docs outra que é documentos».

    Sem a migração, o `actualizar.sh` traz o código novo e as peças de
    42 concursos desaparecem do painel **sem nada o dizer**: ficam no
    disco, com o nome que o código já não procura. É o mesmo silêncio
    do painel a servir código velho, que custou dezassete horas nesse
    mesmo dia.
    """

    def setUp(self):
        self.pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.pasta, ignore_errors=True)
        self.nova = os.path.join(self.pasta, "pecas")
        self.velha = os.path.join(self.pasta, "documentos")
        self.enterContext(unittest.mock.patch.object(radar, "DOCS", self.nova))
        self.enterContext(unittest.mock.patch.object(
            radar, "DOCS_ANTIGO", self.velha))

    def _peca(self, raiz, texto="conteudo"):
        os.makedirs(os.path.join(raiz, "21296-2026"), exist_ok=True)
        with open(os.path.join(raiz, "21296-2026", "CE.pdf"), "w") as f:
            f.write(texto)

    def test_a_pasta_antiga_passa_a_nova_com_o_que_tem_dentro(self):
        self._peca(self.velha)
        radar.arrumar_pecas()
        self.assertFalse(os.path.exists(self.velha))
        with open(os.path.join(self.nova, "21296-2026", "CE.pdf")) as f:
            self.assertEqual(f.read(), "conteudo")

    def test_correr_outra_vez_nao_faz_nada(self):
        """Corre a cada arranque: tem de ser idempotente."""
        self._peca(self.velha)
        radar.arrumar_pecas()
        radar.arrumar_pecas()
        with open(os.path.join(self.nova, "21296-2026", "CE.pdf")) as f:
            self.assertEqual(f.read(), "conteudo")

    def test_sem_pasta_antiga_nao_inventa_nada(self):
        radar.arrumar_pecas()
        self.assertFalse(os.path.exists(self.nova))

    def test_com_as_duas_nao_se_adivinha_qual_vale(self):
        """A nova manda, e a antiga fica à espera de uma mão — apagá-la
        ou fundi-la é decisão de quem olha, não de um arranque."""
        self._peca(self.velha, "a antiga")
        self._peca(self.nova, "a nova")
        radar.arrumar_pecas()
        self.assertTrue(os.path.isdir(self.velha))
        with open(os.path.join(self.nova, "21296-2026", "CE.pdf")) as f:
            self.assertEqual(f.read(), "a nova")


class TestOActualizarReiniciaSempreOPainel(unittest.TestCase):
    """19/09/2026: o painel esteve dezassete horas a servir código velho.

    O `actualizar.sh` saía com `exit 0` no «já está na última release»,
    **antes** da linha que reinicia o serviço. Nesta pasta é o caso
    normal — programa-se aqui, por isso nunca há nada a trazer — e o
    reinício nunca acontecia. O serviço tinha arrancado a 18/09 às
    07:53 e o `radar.py` fora gravado a 19/09 à 01:09.

    É a armadilha que o CLAUDE.md já mandava verificar («compara a hora
    de arranque do processo com a da última gravação do radar.py»), e
    que um guião ajudava a esconder ao dizer «já está na última
    release».
    """

    GUIAO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "actualizar.sh")

    def setUp(self):
        with open(self.GUIAO, encoding="utf-8") as f:
            self.linhas = f.read().splitlines()

    def _linha_de(self, agulha):
        for i, l in enumerate(self.linhas):
            if agulha in l and not l.strip().startswith("#"):
                return i
        self.fail("não encontrei %r no actualizar.sh" % agulha)

    def test_nenhuma_saida_boa_salta_o_reinicio(self):
        """A regra, e não o texto: todo o `exit 0` — se algum voltar —
        tem de vir **depois** do reinício. É isto que falhava."""
        reinicio = self._linha_de("try-restart radar-painel.service")
        for i, l in enumerate(self.linhas):
            if l.strip() == "exit 0":
                self.assertGreater(
                    i, reinicio,
                    "linha %d: um `exit 0` antes do reinício deixa o "
                    "painel a servir código velho" % (i + 1))

    def test_o_caminho_sem_nada_a_trazer_chega_ao_reinicio(self):
        """O ramo «já está na última release» não pode terminar o
        guião: é o ramo que corre todos os dias nesta pasta."""
        ja_esta = self._linha_de("Já está na última release")
        reinicio = self._linha_de("try-restart radar-painel.service")
        self.assertLess(ja_esta, reinicio)
        seguintes = self.linhas[ja_esta + 1:reinicio]
        self.assertNotIn("exit 0", [l.strip() for l in seguintes])

    def test_diz_a_verdade_quando_a_pasta_esta_a_frente(self):
        """Dizia «a pasta está agora na release vX.Y.Z» quando estava à
        frente dela — o `git merge --ff-only` para um antepassado
        devolve «Already up to date» e sai bem."""
        self._linha_de("merge-base --is-ancestor")
        junto = "\n".join(self.linhas)
        self.assertIn("à frente da release", junto)


if __name__ == "__main__":

    unittest.main(verbosity=2)
