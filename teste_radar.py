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
from urllib.parse import parse_qsl, quote, unquote, unquote_plus, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radar
import casa


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
    """O sumário casa com todas as âncoras e não diz nada."""

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


class TestSemeadoraDeFases(unittest.TestCase):
    """As fases sao do utilizador: so se semeiam num quadro por estrear."""

    class FalsoCursor:
        def __init__(self, linhas):
            self._linhas = linhas

        def fetchall(self):
            return self._linhas

    class FalsaLigacao:
        """O minimo que semear_fases() usa: execute() e fetchall()."""

        def __init__(self, fases):
            self.fases = list(fases)
            self.escritas = []

        def execute(self, sql, args=()):
            if sql.lstrip().upper().startswith("SELECT"):
                return TestSemeadoraDeFases.FalsoCursor(
                    [{"id": i + 1, "nome": n}
                     for i, n in enumerate(self.fases)])
            self.escritas.append((sql, args))
            return TestSemeadoraDeFases.FalsoCursor([])

    def test_quadro_vazio_recebe_as_de_origem(self):
        c = self.FalsaLigacao([])
        radar.semear_fases(c)
        self.assertEqual(len(c.escritas), len(radar.FASES_INICIAIS))

    def test_quadro_do_utilizador_fica_intacto(self):
        c = self.FalsaLigacao(["As minhas", "Outra"])
        radar.semear_fases(c)
        self.assertEqual(c.escritas, [])

    def test_guardados_antigo_e_aproveitado_e_nao_duplicado(self):
        # renomeia a coluna que as primeiras versoes criavam, para nao
        # desgarrar os cartoes que ja lhe estivessem atribuidos
        c = self.FalsaLigacao(["Guardados"])
        radar.semear_fases(c)
        self.assertTrue(c.escritas[0][0].startswith("UPDATE"))
        self.assertEqual(len(c.escritas), len(radar.FASES_INICIAIS))


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

    def casa(self, linha, ancoras):
        import re
        curta = radar.simplifica(linha)
        return any(re.search(padrao, curta) for _, padrao in ancoras)

    def test_resolucao_nao_e_solucao(self):
        # "Clausula 24a - Resolucao do contrato" casava com "solucao" por
        # nao haver fronteira de palavra, e comia o orcamento todo
        self.assertFalse(self.casa("Cláusula 24ª - Resolução do contrato",
                                   radar.ANCORAS_OBJECTO))
        self.assertFalse(self.casa("Cláusula 35ª - Resolução de litígios",
                                   radar.ANCORAS_OBJECTO))
        self.assertTrue(self.casa("1. Objeto da Solução Tecnológica",
                                  radar.ANCORAS_OBJECTO))

    def test_o_que_interessa_casa(self):
        self.assertTrue(self.casa("3. Equipa", radar.ANCORAS_EQUIPA))
        self.assertTrue(self.casa("Cláusula 39ª Profissionais",
                                  radar.ANCORAS_EQUIPA))
        self.assertTrue(self.casa("Artigo 9.º - Documentos da proposta",
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
        # condicoes() trata a falta de estado como "novo"; se a consulta
        # guardada nao dissesse isso, o filtro voltava como "todos"
        self.assertEqual(radar.filtro_actual({}), "estado=novo")

    def test_estado_vazio_e_todos_e_nao_se_perde(self):
        # vazio nao e a mesma coisa que ausente, e nao se pode deixar cair
        # por ser vazio: e a aba "Todos"
        self.assertEqual(radar.filtro_actual({"estado": ""}), "estado=")

    def test_ordem_fixa_seja_qual_for_a_ordem_da_url(self):
        um = radar.filtro_actual({"estado": "novo", "q": "software"})
        outro = radar.filtro_actual({"q": "software", "estado": "novo"})
        self.assertEqual(um, outro)
        self.assertEqual(um, "q=software&estado=novo")

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
                         "estado=novo")


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
        self.assertIn("72%", valores)

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
        self.assertIn("90%", valores)
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
        self.assertIn("9091%", valores)   # zeros à direita: código -> grupo

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
        # a regra da casa: nunca uma data ISO num texto para ler
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


class TestSomaPrecosBase(unittest.TestCase):
    """B11: o cabeçalho da coluna do quadro soma os preços base lidos e
    diz sobre quantos é — somar uns e calar os outros parecia o valor da
    fase inteira."""

    def test_soma_e_conta_so_os_lidos(self):
        itens = [{"preco_base": "175.000,00 EUR"},
                 {"preco_base": ""},
                 {"preco_base": "25.000,00 EUR"}]
        soma, com_preco = radar.soma_precos_base(itens)
        self.assertEqual(soma, 200000.0)
        self.assertEqual(com_preco, 2)

    def test_sem_precos_nao_ha_soma(self):
        self.assertEqual(radar.soma_precos_base([{"preco_base": ""}]), (0, 0))
        self.assertEqual(radar.soma_precos_base([]), (0, 0))


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
        # Desde a fusão de 31/08/2026, a lista dos anúncios é uma só e
        # vive em "/" (a /anuncios redirecciona para lá).
        self.assertEqual(radar.ROTA_DA_VISTA["anuncios"], "/")
        self.assertEqual(radar.ROTA_DA_VISTA["contratos"], "/contratos")
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
                         "q=software&estado=novo")

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
        # mão que a regra da casa proíbe.
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
    """

    def anuncio(self, estado):
        return {"ref": "1/2026", "titulo": "T", "entidade": "E",
                "data_pub": "2026-08-01", "tipo": "", "cpv": "",
                "plataforma": "", "prazo": "", "preco_base": "",
                "estado": estado}

    def test_por_ver_oferece_os_dois_caminhos(self):
        h = radar.linha(self.anuncio("novo"))
        self.assertIn("/estado/1/2026/interessa", h)
        self.assertIn("/estado/1/2026/descartado", h)
        self.assertNotIn("/estado/1/2026/novo", h)

    def test_descartado_pode_repor_se(self):
        h = radar.linha(self.anuncio("descartado"))
        self.assertIn("/estado/1/2026/novo", h)
        self.assertNotIn("/estado/1/2026/descartado", h)

    def test_interessa_nao_repete_o_botao_interessa(self):
        h = radar.linha(self.anuncio("interessa"))
        self.assertNotIn("/estado/1/2026/interessa", h)

    def test_a_etiqueta_do_estado_some_na_vista_desse_estado(self):
        # no separador "Por ver" a etiqueta "por ver" é sempre verdade,
        # portanto não diz nada e só disputa espaço com o CPV e o prazo
        self.assertNotIn(">por ver<", radar.linha(self.anuncio("novo"), "novo"))
        self.assertIn(">por ver<", radar.linha(self.anuncio("novo"), ""))


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
        self.assertEqual(radar.data_de_filtro("01/08/2026"), "")
        self.assertEqual(radar.data_de_filtro(None), "")

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
    da casa de ISO na base e DD/MM no ecrã."""

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
        self.assertEqual(radar.href_limpar("/", "novo"), "/")

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

    E o formulário era GET -- escrevia na base contra a regra da casa de
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


class TestModeloComFornecedor(unittest.TestCase):
    """A2 do saneamento de 30/08/2026: 12 das 18 análises tinham o
    modelo no formato de antes da cadeia ("openai/gpt-oss-120b", sem
    fornecedor), e nenhuma migração o convertia. A regra: um segmento
    sem ":" é de antes da cadeia, e antes da cadeia só a Groq escrevia
    — os outros fornecedores nasceram já com o prefixo posto."""

    def test_sem_prefixo_ganha_groq(self):
        self.assertEqual(radar._modelo_com_fornecedor("openai/gpt-oss-120b"),
                         "groq:openai/gpt-oss-120b")

    def test_prefixado_fica_como_esta(self):
        self.assertEqual(
            radar._modelo_com_fornecedor("nvidia:openai/gpt-oss-120b"),
            "nvidia:openai/gpt-oss-120b")

    def test_misto_converte_so_a_parte_nua(self):
        # havia uma linha assim mesmo na base: a parte prefixada veio da
        # cadeia, a nua ficara da leitura antiga (juntar_fontes preserva)
        self.assertEqual(
            radar._modelo_com_fornecedor(
                "nvidia:openai/gpt-oss-120b, openai/gpt-oss-120b"),
            "nvidia:openai/gpt-oss-120b, groq:openai/gpt-oss-120b")

    def test_aplicar_duas_vezes_da_o_mesmo(self):
        uma = radar._modelo_com_fornecedor("openai/gpt-oss-120b, nvidia:x")
        self.assertEqual(radar._modelo_com_fornecedor(uma), uma)

    def test_vazio_e_none_ficam_vazios(self):
        self.assertEqual(radar._modelo_com_fornecedor(""), "")
        self.assertEqual(radar._modelo_com_fornecedor(None), "")

    def test_modelo_com_dois_pontos_no_nome_nao_ganha_prefixo(self):
        # "z-ai/glm-5.2:free" leva ":" no proprio nome; um prefixo em
        # cima era estragar um valor que nunca foi escrito sem fornecedor
        self.assertEqual(radar._modelo_com_fornecedor("z-ai/glm-5.2:free"),
                         "z-ai/glm-5.2:free")


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

    def test_tres_itens_por_ordem_de_uso(self):
        # a 8/09/2026 Alertas saiu do primeiro nivel: passou a seccao de
        # Configuracoes, que vive em baixo ao lado da zona de estado
        self.assertEqual([n[0] for n in radar.NAV],
                         ["anuncios", "emcurso", "mercado"])
        html_ = radar.app.test_client().get("/").get_data(as_text=True)
        self.assertIn('href="/configuracoes"', html_)

    def test_indicadores_fora_da_navegacao(self):
        chaves = {n[0] for n in radar.NAV}
        chaves.update(v[0] for n in radar.NAV for v in n[3])
        self.assertNotIn("indicadores", chaves)
        # desde 13/09/2026 sao uma seccao de Configuracoes (so do admin)
        self.assertIn("indicadores", [c for c, _, _, _ in radar.SECCOES_CONFIG])
        self.assertIn("Configurações", radar.migalhas_de("configuracoes"))

    def test_quadro_e_calendario_vivem_sob_em_curso(self):
        self.assertEqual(radar.ITEM_DA_PAGINA["quadro"], "emcurso")
        self.assertEqual(radar.ITEM_DA_PAGINA["calendario"], "emcurso")
        # e a lista, desde 14/09/2026
        self.assertEqual(radar.ITEM_DA_PAGINA["lista"], "emcurso")
        self.assertIn("Em curso", radar.migalhas_de("lista"))

    def test_contratos_e_renovacoes_vivem_sob_mercado(self):
        self.assertEqual(radar.ITEM_DA_PAGINA["contratos"], "mercado")
        self.assertEqual(radar.ITEM_DA_PAGINA["renovacoes"], "mercado")

    def test_migalhas_das_vistas_agrupadas(self):
        # deixaram de ser separadores irmãos: são duas vistas de um item
        self.assertIn("Em curso", radar.migalhas_de("quadro"))
        self.assertIn("<em>Quadro</em>", radar.migalhas_de("quadro"))
        self.assertIn("Em curso", radar.migalhas_de("calendario"))
        self.assertIn("Mercado", radar.migalhas_de("contratos"))

    def test_migalhas_da_lista_unica(self):
        self.assertEqual(radar.migalhas_de("anuncios"),
                         "<em>Anúncios</em>")

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
        frag, valores = self._aba("novo")
        self.assertIn("estado = 'novo'", frag)
        self.assertIn("prazo >= ?", frag)          # com prazo lido
        self.assertIn("data_pub >= ?", frag)       # sem prazo: publicação
        self.assertEqual(valores, ["2026-08-31", "2026-07-02"])
        self.assertEqual(frag.count("?"), len(valores))

    def test_abandonados_juntam_descartados_e_expirados(self):
        frag, valores = self._aba("descartado")
        self.assertIn("estado = 'descartado'", frag)
        self.assertIn("estado = 'novo' AND NOT", frag)
        self.assertEqual(frag.count("?"), len(valores))

    def test_interessa_mostra_tudo_mesmo_expirado(self):
        # um interessa com prazo passado é trabalho em curso (proposta
        # entregue, a aguardar decisão) — não se esconde por expirar
        frag, valores = self._aba("interessa")
        self.assertEqual((frag, valores), ("estado = ?", ["interessa"]))

    def test_todos_nao_recorta_nada(self):
        self.assertEqual(self._aba(""), ("", []))

    def test_o_recorte_aplica_se_por_cima_do_motor(self):
        onde, valores = radar.com_recorte(
            *radar.condicoes({"q": "software", "estado": ""}),
            *self._aba("novo"))
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


class TestQuadroECalendarioLigados(unittest.TestCase):
    """Atalho da §5 do esqueleto: quadro e calendário são duas vistas do
    mesmo conjunto, e cada cartão/linha aponta para o seu par por
    âncora. O erro que isto trava: a ligação do cartão prometer uma
    âncora que a grade não tem (prazo fora da janela de 45 dias)."""

    def _carta(self, prazo):
        a = {"ref": "111/2026", "prazo": prazo, "preco_base": "",
             "titulo": "Ensaio", "entidade": "Ent", "responsavel": ""}
        return radar.cartao(a, {})

    def test_cartao_com_prazo_na_janela_aponta_para_a_grade(self):
        prazo = (datetime.date.today()
                 + datetime.timedelta(days=5)).isoformat()
        html_carta = self._carta(prazo)
        self.assertIn("id='c-111-2026'", html_carta)
        self.assertIn("/calendario#c-111-2026", html_carta)

    def test_prazo_fora_da_janela_nao_promete_ancora(self):
        longe = (datetime.date.today()
                 + datetime.timedelta(days=radar.DIAS_CALENDARIO + 10)
                 ).isoformat()
        self.assertNotIn("/calendario#", self._carta(longe))

    def test_prazo_passado_ou_vazio_nao_promete_ancora(self):
        ontem = (datetime.date.today()
                 - datetime.timedelta(days=1)).isoformat()
        self.assertNotIn("/calendario#", self._carta(ontem))
        self.assertNotIn("/calendario#", self._carta(""))


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

    def test_a_navegacao_aponta_para_o_modo(self):
        mercado = next(n for n in radar.NAV if n[0] == "mercado")
        destinos = {v[0]: v[2] for v in mercado[3]}
        self.assertEqual(destinos["renovacoes"], "/contratos?ver=fim")


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
            c.execute("INSERT INTO anuncios (ref, titulo, estado, "
                      "responsavel) VALUES (?,?,?,?)",
                      ("1/2026", "Um", "interessa", "Afonso"))
            c.execute("INSERT INTO anuncios (ref, titulo, estado) "
                      "VALUES (?,?,?)", ("2/2026", "Dois", "descartado"))
            c.execute("INSERT INTO anuncios (ref, titulo) VALUES (?,?)",
                      ("3/2026", "Por ver — não entra"))
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
        # o por ver sem fase nem responsável não entra: refaz-se do DR
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
        self.assertIn("2/2026", por_repor.get("anuncios", []))
        with radar.liga() as c:
            a = c.execute("SELECT estado, responsavel FROM anuncios "
                          "WHERE ref='1/2026'").fetchone()
            self.assertEqual(a["estado"], "interessa")
            self.assertEqual(a["responsavel"], "Afonso")
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
        radar.repor_triagem(caminho)
        radar.repor_triagem(caminho)     # segunda volta: nada duplica
        with radar.liga() as c:
            self.assertEqual(c.execute(
                "SELECT COUNT(*) n FROM historico").fetchone()["n"], 1)
            self.assertEqual(c.execute(
                "SELECT COUNT(*) n FROM anuncio_etiquetas").fetchone()["n"],
                1)

    def test_sem_ficheiro_diz_o_e_nao_rebenta(self):
        escritas, por_repor = radar.repor_triagem(
            os.path.join(self.pasta, "nao-existe.jsonl"))
        self.assertEqual(escritas, 0)
        self.assertIn("ficheiro", por_repor)


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


class TestPapeisDasFases(unittest.TestCase):
    """O cartão muda com a coluna -- e é pelo PAPEL, não pelo nome.

    A base do Afonso tem "Relatorio Preleminar" escrito assim; e
    renomear uma coluna não pode calar o campo que ela pede.
    """

    def test_reconhece_os_nomes_em_uso_erro_de_escrita_incluido(self):
        self.assertEqual(radar.papel_pelo_nome("Relatorio Preleminar"),
                         "relatorio")
        self.assertEqual(radar.papel_pelo_nome("Relatório preliminar"),
                         "relatorio")
        self.assertEqual(radar.papel_pelo_nome("A preparar proposta"),
                         "proposta")
        self.assertEqual(radar.papel_pelo_nome("Submetido"), "submetido")
        self.assertEqual(radar.papel_pelo_nome("Perdido"), "perdido")
        self.assertEqual(radar.papel_pelo_nome("Ganho"), "ganho")
        self.assertEqual(radar.papel_pelo_nome("Por analisar"), "analisar")

    def test_nome_do_utilizador_sem_pista_nao_ganha_papel(self):
        self.assertEqual(radar.papel_pelo_nome("As minhas coisas"), "")

    def test_as_seis_de_origem_tem_papel_e_sao_reconheciveis(self):
        # se o nome de origem de uma fase deixar de dar o papel dela, a
        # base nova nasce com duas colunas para o mesmo papel
        for papel, nome in radar.FASES_DE_ORIGEM:
            self.assertEqual(radar.papel_pelo_nome(nome), papel)


class TestAtribuirPapeis(BaseTemporaria):
    """A migração dos papéis corre a cada arranque e não pode duplicar."""

    def _fases(self):
        with radar.liga() as c:
            return [(f["nome"], f["papel"]) for f in c.execute(
                "SELECT nome, papel FROM fases ORDER BY ordem, id")]

    def test_base_nova_tem_as_seis_com_papel(self):
        self.assertEqual([p for _, p in self._fases()],
                         [p for p, _ in radar.FASES_DE_ORIGEM])

    def test_segunda_passagem_nao_acrescenta_nada(self):
        antes = self._fases()
        radar.atribuir_papeis_no_ficheiro = None   # só para não confundir
        with radar.liga() as c:
            radar.atribuir_papeis(c)
        self.assertEqual(self._fases(), antes)

    def test_nomes_antigos_ganham_papel_sem_coluna_nova(self):
        with radar.liga() as c:
            c.execute("UPDATE fases SET papel=NULL")
            c.execute("UPDATE fases SET nome='Relatorio Preleminar' "
                      "WHERE papel IS NULL AND nome LIKE 'Relat%'")
            radar.atribuir_papeis(c)
        papeis = [p for _, p in self._fases()]
        self.assertEqual(len(papeis), len(radar.FASES_DE_ORIGEM))
        self.assertIn("relatorio", papeis)

    def test_papel_em_falta_e_criado_uma_vez_so(self):
        with radar.liga() as c:
            c.execute("DELETE FROM fases WHERE papel='perdido'")
            radar.atribuir_papeis(c)
            radar.atribuir_papeis(c)
        papeis = [p for _, p in self._fases()]
        self.assertEqual(papeis.count("perdido"), 1)


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
            with radar.app.test_request_context("/?estado=novo"):
                return radar.recorte_da_lista("interessa")
        finally:
            radar.ler_config = antigo

    def test_sem_interesse_e_so_a_aba(self):
        frag, vals = self._com({"interesse_activo": False})
        self.assertEqual(frag, "estado = ?")
        self.assertEqual(vals, ["interessa"])

    def test_com_interesse_junta_os_dois_com_E(self):
        frag, vals = self._com({"interesse_activo": True,
                                "interesse_cpv": "72000000"})
        self.assertIn("estado = ?", frag)
        self.assertIn("cpv LIKE ?", frag)
        self.assertIn(") AND (", frag)
        # a ordem dos valores tem de seguir a dos ? -- aba primeiro
        self.assertEqual(vals, ["interessa", "72%", "%, 72%"])


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
        self.assertIn("action='/estado/1/2026/descartado'", html_)
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
        html_ = radar.caixa_de_abandono()
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
        self.assertIn("required", marcacao)
        self.assertIn("<dialog", marcacao)

    def test_interessa_continua_a_nao_pedir_motivo(self):
        # a exigência é só de quem abandona
        self.assertNotIn("motivo", radar.accao("/estado/1/interessa", "x"))


class TestArrastarRedesenhaOCartao(BaseTemporaria):
    """Arrastar movia o cartão no ecrã e não o redesenhava.

    O cartão que se arrasta é o MESMO nó do DOM, com o HTML da coluna de
    onde veio -- e quem decide o que um cartão mostra é o servidor, pela
    fase. Largá-lo no "Submetido" mudava a coluna e mais nada: o campo
    do preço proposto não aparecia, o preço continuava a ser o base, e a
    soma no cabeçalho das duas colunas ficava errada. O Afonso arrastou
    um cartão para o Submetido e "não aconteceu nada".

    A primeira resposta (01/09/2026) foi recarregar a página depois de
    cada arrasto. A UX-Auditoria.md de 02/09/2026 classificou-a como
    dívida: o servidor passa a devolver o cartão redesenhado e as
    contagens das duas colunas, e o cliente troca só isso.
    """

    def setUp(self):
        super().setUp()
        self.cliente = radar.app.test_client()
        with radar.liga() as c:
            self.fases = {r["papel"]: r["id"] for r in
                          c.execute("SELECT id, papel FROM fases")}
            c.execute("INSERT INTO anuncios (ref, titulo, entidade, data_pub, tipo,"
                      " url, estado, fase_id, preco_base, preco_proposto) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?)",
                      ("1/2026", "Bolsa de horas", "Município X", "2026-08-01",
                       "Anúncio de procedimento", "https://dr/1", "interessa",
                       self.fases["analisar"], "175.000,00 EUR", "118.500,00 EUR"))

    def _mover(self, papel):
        return self.cliente.post("/quadro/mover", json={
            "ref": "1/2026", "fase_id": self.fases[papel]})

    def test_o_servidor_devolve_o_cartao_redesenhado_na_fase_nova(self):
        r = self._mover("submetido")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["ok"])
        # o cartao vem desenhado para o Submetido: pede o proposto e o
        # preco que se le e o proposto, nao o base
        self.assertIn("name='preco_proposto'", d["carta"])
        self.assertIn("118.500,00 EUR", d["carta"])
        self.assertIn("class='carta'", d["carta"])
        self.assertIn("data-ref='1/2026'", d["carta"])
        with radar.liga() as c:
            self.assertEqual(c.execute("SELECT fase_id FROM anuncios WHERE ref='1/2026'")
                             .fetchone()["fase_id"], self.fases["submetido"])

    def test_devolve_as_contagens_das_duas_colunas_tocadas(self):
        d = self._mover("submetido").get_json()
        contas = d["contas"]
        self.assertEqual(set(contas), {str(self.fases["analisar"]),
                                       str(self.fases["submetido"])})
        # a coluna de onde saiu ficou a zero; a de destino conta um e
        # soma o PROPOSTO (e o que esta em jogo a partir do Submetido)
        self.assertIn("<span class='coluna-conta'>0</span>",
                      contas[str(self.fases["analisar"])])
        destino = contas[str(self.fases["submetido"])]
        self.assertIn("<span class='coluna-conta'>1", destino)
        self.assertIn("propostos", destino)

    def test_fase_inexistente_e_anuncio_fora_do_quadro_continuam_a_recusar(self):
        r = self.cliente.post("/quadro/mover", json={"ref": "1/2026", "fase_id": 999})
        self.assertEqual(r.status_code, 404)
        r = self.cliente.post("/quadro/mover", json={"ref": "nao/existe",
                                                     "fase_id": self.fases["ganho"]})
        self.assertEqual(r.status_code, 404)

    def test_o_js_troca_o_cartao_e_as_contagens_em_vez_de_recarregar(self):
        js = radar.QUADRO_JS
        sucesso = js[js.index("return r.json();"):js.index(".catch(")]
        self.assertNotIn("location.reload", sucesso)
        self.assertIn("carta.replaceWith(nova)", sucesso)
        self.assertIn("ligarCarta(nova)", sucesso)      # senao o cartao novo nao arrasta
        self.assertIn("d.contas", sucesso)
        # os ramos do erro continuam a repor o ecra pelo que a base diz
        self.assertEqual(js.count("location.reload()"), 2)


class TestContrasteNosFundosReais(unittest.TestCase):
    """`--papel` não é o pior fundo.

    A regra da casa dizia que os --t* passavam AA sobre --papel, "que é
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

    def test_o_pede_da_coluna_passa_aa_sobre_a_coluna(self):
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

    ALVOS = ("button.tirar", ".carta-pe a", ".bt-leve", ".sou button",
             "button.etq-x", ".alerta .apagar")

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

    def test_interessa_avisa_e_oferece_desfazer(self):
        r = self.cliente.post("/estado/2/2026/interessa",
                              headers={"Referer": "http://localhost:8765/?estado=novo"})
        self.assertEqual(r.status_code, 302)
        p = self._params(r)
        self.assertIn("marcado como interessa", p["aviso"])
        self.assertIn("Aquisição de serviços de consultoria", p["aviso"])
        self.assertEqual(p["desfazer"], "/estado/2/2026/novo")
        self.assertEqual(p["estado"], "novo")     # o filtro da pagina fica

    def test_abandonar_avisa_com_o_motivo_e_o_desfazer_repoe(self):
        r = self.cliente.post("/estado/2/2026/descartado",
                              data={"motivo": radar.MOTIVOS_ABANDONO[0]})
        p = self._params(r)
        self.assertIn("abandonado (%s)" % radar.MOTIVOS_ABANDONO[0], p["aviso"])
        self.assertEqual(p["desfazer"], "/estado/2/2026/novo")
        r = self.cliente.post(p["desfazer"])
        self.assertIn("reposto em por ver", self._params(r)["aviso"])
        with radar.liga() as c:
            a = c.execute("SELECT estado, motivo FROM anuncios WHERE ref='2/2026'").fetchone()
        self.assertEqual((a["estado"], a["motivo"]), ("novo", None))

    def test_desfazer_um_interessa_sobre_um_abandonado_leva_o_motivo(self):
        # sem o motivo na accao, o servidor recusava a reposicao
        self.cliente.post("/estado/2/2026/descartado",
                          data={"motivo": radar.MOTIVOS_ABANDONO[1]})
        r = self.cliente.post("/estado/2/2026/interessa")
        p = self._params(r)
        self.assertTrue(p["desfazer"].startswith("/estado/2/2026/descartado?motivo="))
        r = self.cliente.post(p["desfazer"])
        self.assertEqual(r.status_code, 302)
        with radar.liga() as c:
            a = c.execute("SELECT estado, motivo FROM anuncios WHERE ref='2/2026'").fetchone()
        self.assertEqual((a["estado"], a["motivo"]), ("descartado", radar.MOTIVOS_ABANDONO[1]))

    def test_repetir_o_mesmo_estado_avisa_mas_nao_oferece_desfazer(self):
        self.cliente.post("/estado/2/2026/interessa")
        p = self._params(self.cliente.post("/estado/2/2026/interessa"))
        self.assertIn("marcado como interessa", p["aviso"])
        self.assertNotIn("desfazer", p)

    def test_o_aviso_anterior_sai_da_query_string(self):
        r = self.cliente.post("/estado/2/2026/interessa", headers={
            "Referer": "http://localhost:8765/?aviso=velho&desfazer=/estado/x/novo&estado="})
        q = parse_qsl(urlparse(r.headers["Location"]).query, keep_blank_values=True)
        self.assertEqual([k for k, _ in q].count("aviso"), 1)
        self.assertEqual([k for k, _ in q].count("desfazer"), 1)
        self.assertIn(("estado", ""), q)

    def test_envolver_desenha_o_desfazer_como_botao_post(self):
        with radar.app.test_request_context(
                "/?aviso=feito&desfazer=/estado/2/2026/novo"):
            pagina = radar.envolver("anuncios", "T", "S", "")
        self.assertIn("<form class='accao desfazer' method='post' "
                      "action='/estado/2/2026/novo'>", pagina)
        self.assertIn(">desfazer</button>", pagina)

    def test_so_aceita_caminhos_de_estado_no_desfazer(self):
        with radar.app.test_request_context(
                "/?aviso=feito&desfazer=https://exemplo.pt/x"):
            pagina = radar.envolver("anuncios", "T", "S", "")
        self.assertNotIn("class='accao desfazer'", pagina)
        self.assertIn("feito", pagina)


class TestPrazoNeutroDepoisDeSubmetido(unittest.TestCase):
    """O quadro pintava «prazo expirado» a vermelho em 4 dos 9 cartões,
    todos em fases pós-submissão, onde o prazo ter passado é o estado
    normal (UX-Auditoria.md, 02/09/2026). O vermelho é a cor de alarme
    da lista e puxava o olho para uma coisa que não pede acção nenhuma.
    """

    def _carta(self, papel, prazo="2026-08-03"):
        a = {"ref": "9/2026", "titulo": "T", "entidade": "E", "prazo": prazo,
             "preco_base": "175.000,00 EUR", "preco_proposto": "", "responsavel": "",
             "posicao": None, "top3": "", "motivo_perda": ""}
        return radar.cartao(a, {}, urgente=8, papel=papel)

    def test_antes_do_submetido_o_prazo_e_alarme(self):
        for papel in ("analisar", "proposta"):
            self.assertIn("prazo expirado", self._carta(papel))
            self.assertIn("class='tag mau'", self._carta(papel))

    def test_a_partir_do_submetido_e_uma_data_neutra(self):
        for papel in radar.FASES_COM_PROPOSTO:
            carta = self._carta(papel)
            self.assertNotIn("prazo expirado", carta)
            self.assertNotIn("tag mau", carta)
            self.assertIn("prazo 03/08/2026", carta)

    def test_um_prazo_ainda_aberto_tambem_e_neutro_depois_de_submeter(self):
        # a proposta ja foi entregue: contar os dias que faltam e ruido
        futuro = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
        carta = self._carta("submetido", futuro)
        self.assertNotIn("dias", carta)
        self.assertIn("prazo " + radar.data_pt(futuro), carta)

    def test_sem_prazo_nao_ha_pilula(self):
        self.assertNotIn("prazo", self._carta("submetido", "").split("carta-meta")[1].split("</div>")[0])


class TestAColunaDizOQuePede(unittest.TestCase):
    """O campo só aparece quando há um cartão lá dentro.

    Com o quadro todo em "Por analisar" -- que é o caso normal -- não
    havia nada no ecrã a dizer que o "Submetido" pede o preço proposto,
    e a funcionalidade parecia não existir. Foi o que o Afonso viu.
    """

    def test_as_fases_que_pedem_dizem_o_que_pedem(self):
        for papel in ("submetido", "relatorio", "perdido"):
            self.assertIn(papel, radar.PEDIDO_DA_FASE)
            self.assertTrue(radar.PEDIDO_DA_FASE[papel].strip())

    def test_as_que_nao_pedem_nada_nao_dizem_nada(self):
        for papel in ("analisar", "proposta", "ganho"):
            self.assertNotIn(papel, radar.PEDIDO_DA_FASE)

    def test_quem_pede_no_cartao_e_quem_o_diz_no_cabecalho(self):
        # as duas listas têm de concordar: uma coluna que anuncia um
        # campo e não o mostra é pior do que não o anunciar
        a = {"ref": "1/2026", "preco_proposto": None, "posicao": None,
             "top3": None, "motivo_perda": None}
        for papel in ("analisar", "proposta", "submetido", "relatorio",
                      "ganho", "perdido"):
            tem_campo = bool(radar._campos_da_fase(a, papel))
            self.assertEqual(tem_campo, papel in radar.PEDIDO_DA_FASE,
                             "desacordo na fase %s" % papel)


class TestCamposPorFase(unittest.TestCase):
    """Cada fase pede o que lhe falta, e só ela.

    "Por analisar" e "A preparar proposta" não têm nada a apontar
    (palavras do Afonso); o "Submetido" pede o preço proposto, o
    relatório preliminar o lugar e os três primeiros, e o "Perdido" o
    porquê, de âmbito fechado.
    """

    @staticmethod
    def _a(**k):
        base = {"ref": "1/2026", "preco_proposto": None, "posicao": None,
                "top3": None, "motivo_perda": None}
        base.update(k)
        return base

    def test_fases_sem_nada_a_apontar_nao_mostram_formulario(self):
        for papel in ("analisar", "proposta", "ganho"):
            self.assertEqual(radar._campos_da_fase(self._a(), papel), "")

    def test_submetido_pede_o_preco_proposto(self):
        html_ = radar._campos_da_fase(self._a(), "submetido")
        self.assertIn("name='preco_proposto'", html_)
        self.assertNotIn("motivo_perda", html_)

    def test_relatorio_pede_lugar_e_os_tres_primeiros(self):
        html_ = radar._campos_da_fase(self._a(posicao=2, top3="A · B · C"),
                                      "relatorio")
        self.assertIn("name='posicao'", html_)
        self.assertIn("value='2'", html_)
        self.assertIn("name='top3'", html_)
        self.assertIn("A · B · C", html_)

    def test_perdido_tem_ambito_fechado(self):
        html_ = radar._campos_da_fase(self._a(motivo_perda="Preço"),
                                      "perdido")
        for m in radar.MOTIVOS_PERDA:
            self.assertIn(html.escape(m), html_)
        self.assertIn("required", html_)
        # o que já lá está vem escolhido, senão gravar outra vez apagava
        self.assertIn("selected", html_)


class TestPrecoDoCartao(unittest.TestCase):
    """A partir do "Submetido" o número que conta é o proposto.

    E enquanto o proposto não estiver preenchido mostra-se o base
    **dito como base**: mostrá-lo calado é dar o tecto da entidade por
    proposta nossa.
    """

    @staticmethod
    def _a(**k):
        base = {"ref": "1/2026", "titulo": "T", "entidade": "E", "prazo": "",
                "preco_base": "175.000,00 EUR", "preco_proposto": None,
                "posicao": None, "top3": None, "motivo_perda": None,
                "responsavel": ""}
        base.update(k)
        return base

    def test_antes_do_submetido_e_o_preco_base(self):
        html_ = radar.cartao(self._a(), {}, 10, "analisar")
        self.assertIn("175.000,00 EUR", html_)
        self.assertIn("preço base", html_)

    def test_no_submetido_com_proposto_mostra_o_proposto(self):
        html_ = radar.cartao(self._a(preco_proposto="118.500,00 EUR"),
                             {}, 10, "submetido")
        self.assertIn("118.500,00 EUR", html_)
        self.assertNotIn("175.000,00 EUR", html_)
        self.assertIn("preço proposto", html_)

    def test_no_submetido_sem_proposto_o_base_vai_dito_como_base(self):
        html_ = radar.cartao(self._a(), {}, 10, "submetido")
        self.assertIn("base 175.000,00 EUR", html_)

    def test_a_soma_da_coluna_segue_a_mesma_regra(self):
        itens = [self._a(preco_proposto="100.000,00 EUR"),
                 self._a(preco_proposto=None)]
        soma, quantos = radar.soma_precos_base(itens, "preco_proposto")
        self.assertEqual((soma, quantos), (100000.0, 1))
        soma, quantos = radar.soma_precos_base(itens, "preco_base")
        self.assertEqual((soma, quantos), (350000.0, 2))

    def test_o_proposto_guarda_se_no_formato_que_se_sabe_ler(self):
        # euros() põe espaço nos milhares e euros_do_texto() lê "118" de
        # "118 500 €": a soma da coluna dava 118 em vez de 118 500
        texto = radar._texto_do_preco(radar.euros_do_texto("118500"))
        self.assertEqual(texto, "118.500,00 EUR")
        self.assertEqual(radar.euros_do_texto(texto), 118500.0)


class TestFasesNaoSeCriamNemSeApagam(unittest.TestCase):
    """Decisão do Afonso a 01/09/2026: o quadro é o funil da casa.

    Criar uma sétima coluna não teria papel nenhum, e apagar uma das
    seis levava consigo o campo que ela pede -- sem forma de a repor.
    """

    def setUp(self):
        self.cliente = radar.app.test_client()

    def test_a_rota_de_criar_fase_deixou_de_existir(self):
        r = self.cliente.post("/quadro/fase/nova", data={"nome": "X"})
        self.assertEqual(r.status_code, 404)

    def test_a_rota_de_apagar_fase_deixou_de_existir(self):
        r = self.cliente.post("/quadro/fase/9/apagar")
        self.assertEqual(r.status_code, 404)

    def test_renomear_continua_a_existir(self):
        self.assertIn("fase_renomear",
                      [r.endpoint for r in radar.app.url_map.iter_rules()])


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

    def test_o_descartado_fica_descartado_e_a_lista_nao_repete(self):
        self._poe("100/2026", "2026-07-17", self._texto(), estado="descartado",
                  motivo="Preço base baixo")
        self._poe("200/2026", "2026-08-14")
        self._chega("200/2026", self._texto(prazo="11-09-2026",
                                            altera="100/2026"))
        self.assertEqual(self._le("100/2026")["estado"], "descartado")
        self.assertEqual(self._le("100/2026")["motivo"], "Preço base baixo")
        # "todos" sao todos os procedimentos: a alteracao nao entra
        onde, valores = radar.condicoes({"estado": ""})
        with radar.liga() as c:
            refs = [r["ref"] for r in c.execute(
                "SELECT ref FROM anuncios" + onde, valores)]
        self.assertEqual(refs, ["100/2026"])

    def test_a_triagem_feita_na_alteracao_passa_para_o_original(self):
        # 513 vezes antes disto: o Afonso decidiu na republicacao
        self._poe("100/2026", "2026-07-17", self._texto())
        self._poe("200/2026", "2026-08-14",
                  self._texto(prazo="11-09-2026", altera="100/2026"),
                  estado="descartado", motivo="Falta de CV's")
        with radar.liga() as c:
            c.execute("UPDATE anuncios SET altera=NULL")   # texto por reler
        self.assertEqual(radar.agrupar_alteracoes(), (2, 1))
        orig = self._le("100/2026")
        self.assertEqual((orig["estado"], orig["motivo"]),
                         ("descartado", "Falta de CV's"))
        self.assertEqual(self._le("200/2026")["estado"], "alteracao")
        self.assertTrue(any("decidido na alteração" in p["detalhe"]
                            for p in self._historico("100/2026", "estado")))
        # segunda passagem: nada a fazer
        self.assertEqual(radar.agrupar_alteracoes(), (0, 0))

    def test_a_decisao_na_alteracao_ganha_ao_descarte_antigo_do_original(self):
        # aconteceu na migracao de 01/09/2026: um «interessa» do Afonso na
        # republicacao ficou por baixo de um descarte antigo do original,
        # e o item sumiu-se dos Interessados
        self._poe("100/2026", "2026-07-17", self._texto(), estado="descartado",
                  motivo="Preço base baixo")
        self._poe("200/2026", "2026-08-14",
                  self._texto(prazo="11-09-2026", altera="100/2026"),
                  estado="interessa", fase_id=1)
        radar.aplicar_alteracao("200/2026")
        orig = self._le("100/2026")
        self.assertEqual((orig["estado"], orig["fase_id"], orig["motivo"]),
                         ("interessa", 1, None))
        self.assertTrue(any("era «abandonado»" in p["detalhe"]
                            for p in self._historico("100/2026", "estado")))
        # mas um 'novo' com fase nao e decisao: nao desfaz um descarte
        self._poe("300/2026", "2026-08-20",
                  self._texto(prazo="20-09-2026", altera="100/2026"),
                  fase_id=1)
        self._poe("400/2026", "2026-07-01", self._texto(), estado="descartado",
                  motivo="Falta de CV's")
        self._poe("500/2026", "2026-08-02",
                  self._texto(prazo="20-09-2026", altera="400/2026"), fase_id=1)
        radar.aplicar_alteracao("500/2026")
        self.assertEqual(self._le("400/2026")["estado"], "descartado")

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


class TestRegistoDaCasa(BaseTemporaria):
    """O Excel de análise de concursos da casa (02/09/2026): 187 concursos
    exportados do SharePoint e completados numa folha por concurso, com
    macros a consolidar. Lê-se pelas MESMAS âncoras das macros, liga-se
    cada linha ao procedimento do radar (nunca a uma alteração) e só se
    escreve triagem quando o estado do Excel é inequívoco. Uma decisão
    humana feita no radar nunca é esmagada pela importação."""

    CAB = ["NOME DO CONCURSO", "ENTIDADE", "MODELO", "PRAZO EXECUÇÃO (MESES)",
           "PREÇO BASE (€)", "CRITERIO DE ADJUDICAÇÃO", "PLATAFORMA", "ANO",
           "STATUS", "FOLHA", "ID"]

    def _excel(self, indice, folhas):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "ÍNDICE"
        ws.append(self.CAB)
        for l in indice:
            ws.append(l)
        for ide, d in folhas.items():
            w = wb.create_sheet("C_%04d" % ide)
            w["A1"], w["B1"], w["C1"] = d["entidade"], d["nome"], ide
            w["Z1"], w["Z2"] = ide, "ID_CONCURSO"
            w["A2"] = "← Voltar ao ÍNDICE"
            w["A3"] = "TABELA A — DEFINIÇÃO DO CONCURSO"
            for i, (rot, chave) in enumerate((
                    ("Modelo", "modelo"), ("Prazo de execução (meses)", "prazo"),
                    ("Preço base (€)", "preco"), ("Critério de adjudicação", "criterio"),
                    ("Plataforma", "plataforma"), ("Ano", "ano"), ("Status", "status"))):
                w.cell(4 + i, 1, rot)
                w.cell(4 + i, 2, d.get(chave))
            w["A11"] = "SUBTABELA A.1 — PERFIS EXIGIDOS NO CONCURSO"
            w.append([])
            w.append(["PERFIL", "TECNOLOGIAS / FERRAMENTAS", "ANOS EXP.",
                      "Nº RECURSOS", "HORAS EST.", "CERTIFICAÇÕES"])
            for p in d.get("perfis", []):
                w.append(list(p))
            w.append([])
            w.append(["TABELA B — PROPOSTA CONKORD"])
            for rot, chave in (("Valor total da proposta (€)", "valor"),
                               ("Lugar obtido", "lugar"), ("EBITDA (%)", "ebitda"),
                               ("Gap para o Preço base (€)", None),
                               ("Gap para o Preço base (%)", None),
                               ("Gap para o 1º lugar (€)", None),
                               ("Gap para o 1º lugar (%)", None),
                               ("Razão de não participação", "razao"),
                               ("Notas", "notas")):
                w.append([rot, d.get(chave) if chave else None])
            w.append(["TABELA C — PREÇOS DOS CONCORRENTES"])
            conc = d.get("concorrentes", [])
            for lugar in range(1, 6):
                w.append(["%dº Lugar" % lugar])
                nome, valor = conc[lugar - 1] if lugar <= len(conc) else ("", None)
                w.append(["Nome do concorrente", nome])
                w.append(["Valor total da proposta (€)", valor])
            w.append(["SUBTABELA C.1 — PREÇO POR PERFIL (POR CONCORRENTE)"])
            w.append(["CONCORRENTE", "PERFIL", "TECNOLOGIAS", "ANOS EXP.",
                      "VALOR PERFIL (€)", "HORAS", "€/HORA"])
            for p in d.get("precos", []):
                w.append(list(p))
        caminho = os.path.join(self.pasta, "casa.xlsx")
        wb.save(caminho)
        return caminho

    INDICE = [
        ["Plataforma Central de Deteção Precoce", "SPMS", "Turn Key", 5, 716846.64,
         "Preço", "Vortal", 2026, "Perdido", "Abrir folha", 1],
        ["Serviços especializados OutSystems", "IFAP", None, None, 188000,
         None, "AnoGov", 2026, "Não fomos", "Abrir folha", 2],
        ["Infraestructuras análisis y diseño", "Principado de Asturias", None, None,
         50000, None, "Vortal", 2026, "Não fomos", None, 3],
        ["Bolsa de horas de desenvolvimento", "OSAE", "Consulting", 12, 99000,
         None, "AcinGov", 2026, "Submetido", None, 4],
    ]
    FOLHAS = {
        1: {"entidade": "SPMS", "nome": "Plataforma Central de Deteção Precoce",
            "modelo": "Turn Key", "prazo": 5, "preco": 716846.64, "criterio": "Preço",
            "plataforma": "Vortal", "ano": 2026, "status": "Perdido",
            "perfis": [("Desenvolvedor Fullstack", "Java", 5, 2, 1600, "PMP")],
            "valor": 399632, "lugar": 4, "ebitda": 0.3047,
            "concorrentes": [("Axians", 265233), ("Glintt", 300000), ("LATD", 399632)],
            "precos": [("LATD", "Desenvolvedor Fullstack", "Java", 5, 156600, 5400, 29)]},
        2: {"entidade": "IFAP", "nome": "Serviços especializados OutSystems",
            "modelo": "Consulting", "prazo": 12, "preco": 188000, "criterio": "Preço",
            "plataforma": "AnoGov", "ano": 2026, "status": "Não fomos",
            "razao": "Fora do nosso âmbito"},
    }

    def _anuncio(self, ref, titulo, entidade, data_pub, preco="", **campos):
        with radar.liga() as c:
            c.execute("INSERT INTO anuncios (ref, titulo, entidade, data_pub, tipo, url,"
                      " estado, preco_base, titulo_norm, entidade_norm) "
                      "VALUES (?,?,?,?,?,?,?,?,simplifica(?),simplifica(?))",
                      (ref, titulo, entidade, data_pub, "Anúncio de procedimento",
                       "https://dr/" + ref, "novo", preco, titulo, entidade))
            for k, v in campos.items():
                c.execute("UPDATE anuncios SET %s=? WHERE ref=?" % k, (v, ref))

    def _le(self, ref):
        with radar.liga() as c:
            return c.execute("SELECT * FROM anuncios WHERE ref=?", (ref,)).fetchone()

    def _historico(self, ref, accao=None):
        with radar.liga() as c:
            return [dict(p) for p in c.execute(
                "SELECT accao, detalhe, quem FROM historico WHERE ref=?" +
                (" AND accao=?" if accao else ""),
                (ref, accao) if accao else (ref,))]

    def _base_normal(self):
        self._anuncio("5491/2026", "(DAG) Aquisição de serviços para evolução da "
                      "Plataforma Central de Deteção Precoce",
                      "Serviços Partilhados do Ministério da Saúde, EPE", "2026-03-06",
                      "716.846,64 EUR")
        self._anuncio("100/2026", "Aquisição de serviços especializados OutSystems",
                      "IFAP - Instituto de Financiamento da Agricultura e Pescas, I.P.",
                      "2026-05-02", "188.000,00 EUR")
        self._anuncio("7/2026", "Fornecimento de refeições escolares",
                      "Município de Exemplo", "2026-01-10")
        # dois candidatos com o mesmo titulo e entidade, anos seguidos, sem
        # preco base lido: ambiguo ate se ler o detalhe
        self._anuncio("300/2025", "Aquisição de bolsa de horas de desenvolvimento",
                      "Ordem dos Solicitadores e dos Agentes de Execução", "2025-11-03")
        self._anuncio("301/2026", "Aquisição de bolsa de horas de desenvolvimento",
                      "Ordem dos Solicitadores e dos Agentes de Execução", "2026-04-03")

    def test_le_o_indice_e_a_folha_pelas_ancoras_das_macros(self):
        linhas = casa.ler_excel(self._excel(self.INDICE, self.FOLHAS))
        self.assertEqual([l["id"] for l in linhas], [1, 2, 3, 4])
        um = linhas[0]
        self.assertEqual((um["status"], um["valor_proposta"], um["lugar"],
                          um["folha"]), ("Perdido", 399632.0, 4.0, "C_0001"))
        self.assertEqual([c["nome"] for c in um["concorrentes"]],
                         ["Axians", "Glintt", "LATD"])
        self.assertEqual(um["perfis"][0]["perfil"], "Desenvolvedor Fullstack")
        self.assertEqual(um["precos_perfis"][0]["hora"], 29.0)
        dois = linhas[1]
        # a folha completa o que o INDICE nao tem
        self.assertEqual((dois["modelo"], dois["razao"]),
                         ("Consulting", "Fora do nosso âmbito"))
        self.assertEqual(linhas[3]["concorrentes"], [])      # sem folha
        self.assertTrue(casa.fora_do_pais(linhas[2]))
        self.assertFalse(casa.fora_do_pais(linhas[0]))

    def test_o_que_o_zoho_diz_fica_em_coluna_propria_e_sobrevive_a_reimportacao(self):
        # 03/09/2026: o Zoho e a fonte mais actual do estado, mas nao tem
        # palavra para "nao fomos" -- das 92 linhas que cruzavam, 46
        # diziam "Nao fomos" no Excel e "Lost" no Zoho. Escrever por
        # cima do `status` apagava a distincao, por isso o Zoho tem
        # coluna propria. E o `_guardar_linha()` usa ON CONFLICT DO
        # UPDATE com colunas nomeadas, nao um REPLACE da linha inteira:
        # e isso que faz o zoho_* (e o lote, e o porque_sem_ref)
        # sobreviver a uma reimportacao do Excel. Um REPLACE apagava-os
        # em silencio.
        self._base_normal()
        indice = [list(self.INDICE[0])]
        casa.importar(self._excel(indice, {}), ler=False)
        with radar.liga() as c:
            colunas = [r["name"] for r in c.execute("PRAGMA table_info(casa)")]
            for k in ("zoho_fase", "zoho_montante", "zoho_como", "zoho_em"):
                self.assertIn(k, colunas)
            c.execute("UPDATE casa SET zoho_fase='Lost', zoho_montante=1234.5, "
                      "zoho_como='preço+nome', zoho_em='2026-09-03 18:14' WHERE id=1")
            antes = dict(c.execute("SELECT status, zoho_fase FROM casa "
                                   "WHERE id=1").fetchone())
        self.assertNotEqual(antes["status"], "Lost")     # o Excel manda no seu
        casa.importar(self._excel(indice, {}), ler=False)
        with radar.liga() as c:
            r = dict(c.execute("SELECT status, zoho_fase, zoho_montante, zoho_como "
                               "FROM casa WHERE id=1").fetchone())
        self.assertEqual(r["zoho_fase"], "Lost")         # nao foi apagado
        self.assertEqual(r["zoho_montante"], 1234.5)
        self.assertEqual(r["zoho_como"], "preço+nome")
        self.assertEqual(r["status"], antes["status"])   # nem um esmagou o outro

    def test_o_zoho_manda_no_estado_menos_no_nao_fomos(self):
        # A regra dele, 03/09/2026, depois de ver os numeros: "o que
        # esta no Excel como nao fomos, esse estado prevalece ao estado
        # do Zoho, mas e o unico". A excepcao existe porque em 46 das 92
        # linhas que cruzam o Excel diz "Nao fomos" e o Zoho diz "Lost":
        # sem ela, metade do cruzamento perdia a distincao.
        efec = casa.estado_efectivo
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
        self.assertIn("2.3 - negotiation", casa.TRADUCAO_ZOHO)
        # sem Zoho, ou com uma fase que nao se traduz, manda o Excel
        self.assertEqual(efec({"status": "Ganho", "zoho_fase": None}), "Ganho")
        self.assertEqual(efec({"status": "Ganho"}), "Ganho")
        self.assertEqual(efec({"status": "Submetido", "zoho_fase": "Fase Nova"}),
                         "Submetido")
        # e a triagem segue a regra, nao o status cru
        papeis = {"submetido": 3, "perdido": 6, "ganho": 5}
        e, f, _ = casa.estado_pretendido(
            {"status": "Submetido", "zoho_fase": "Lost"}, papeis)
        self.assertEqual((e, f), ("interessa", 6))          # perdido, nao submetido
        self.assertEqual(casa.estado_pretendido(
            {"status": "Não fomos", "zoho_fase": "Won", "razao": ""}, papeis),
            ("descartado", None, {"motivo": None}))          # o Zoho nao o resgata

    def test_o_zoho_nao_decide_uma_linha_que_e_um_lote(self):
        # 04/09/2026, dele: "o #14 e lotes e nos ganhamos um deles". As
        # duas fontes contam coisas diferentes -- o Excel uma linha por
        # lote, o Zoho um negocio por procedimento -- e um "Won" do Zoho
        # quer dizer "ganhamos pelo menos um lote", nao "ganhamos este".
        # O caso real: 1947/2026, tres lotes, tres linhas (#14 o L1
        # perdido, #97 o L2 ganho, #98 o L3 perdido) e um so negocio no
        # Zoho, "Won" com 169 344 contra os 109 065,60 do L1. Sem esta
        # guarda o #14 passava de Perdido a Ganho.
        efec = casa.estado_efectivo
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
        papeis = {"submetido": 3, "perdido": 6, "ganho": 5}
        e, f, _ = casa.estado_pretendido(dict(l1, lugar=3), papeis)
        self.assertEqual((e, f), ("interessa", 6))          # perdido, nao ganho

    def test_a_reimportacao_leva_o_lote_e_nao_so_a_fase_do_zoho(self):
        # O lote e o que TRAVA o Zoho, por isso tem de chegar ao
        # estado_efectivo() no caminho da importacao tal como o
        # zoho_fase. Sem ele, um --com-triagem numa reimportacao dava
        # Ganho a uma linha de lote que o Excel diz Perdido.
        self._base_normal()
        lotes = radar.lotes_do_texto(self.LOTES)
        with radar.liga() as c:
            c.execute("UPDATE anuncios SET lotes=? WHERE ref='5491/2026'",
                      (json.dumps(lotes),))
        indice = [list(self.INDICE[0])]
        indice[0][4] = 53667.2          # o preco do lote 1
        indice[0][9] = "Perdido"
        casa.importar(self._excel(indice, {}), ler=False)
        with radar.liga() as c:
            c.execute("UPDATE casa SET zoho_fase='Won' WHERE id=1")
            self.assertEqual(
                c.execute("SELECT lote FROM casa WHERE id=1").fetchone()[0], 1)
        vistos = []
        real = casa.estado_pretendido
        casa.estado_pretendido = lambda linha, papeis: (
            vistos.append(casa.estado_efectivo(linha)) or real(linha, papeis))
        try:
            casa.importar(self._excel(indice, {}), ler=False, triagem=True,
                          ensaio=True)
        finally:
            casa.estado_pretendido = real
        self.assertEqual(vistos, ["Perdido"])   # e nao "Ganho"

    def test_a_reimportacao_do_excel_nao_desfaz_a_regra_do_zoho(self):
        # A linha vem do Excel e nao traz o zoho_fase. Sem o ir buscar a
        # base, um --importar-excel --com-triagem aplicava o estado do
        # Excel e desfazia a regra em silencio -- justamente no caminho
        # em que a triagem se escreve nos anuncios.
        self._base_normal()
        indice = [list(self.INDICE[0])]
        indice[0][9] = "Submetido"
        casa.importar(self._excel(indice, {}), ler=False)
        with radar.liga() as c:
            c.execute("UPDATE casa SET zoho_fase='Lost' WHERE id=1")
        vistos = []
        real = casa.estado_pretendido
        casa.estado_pretendido = lambda linha, papeis: (
            vistos.append(casa.estado_efectivo(linha)) or real(linha, papeis))
        try:
            casa.importar(self._excel(indice, {}), ler=False, triagem=True,
                          ensaio=True)
        finally:
            casa.estado_pretendido = real
        self.assertEqual(vistos, ["Perdido"])   # e nao "Submetido"

    def test_estado_pretendido_traduz_o_excel(self):
        papeis = {"submetido": 3, "perdido": 6, "ganho": 5}
        self.assertEqual(casa.estado_pretendido(
            {"status": "Não fomos", "razao": "Prazo de Entrega curto"}, papeis),
            ("descartado", None, {"motivo": "Prazo curto"}))
        self.assertEqual(casa.estado_pretendido(
            {"status": "Não fomos", "razao": ""}, papeis),
            ("descartado", None, {"motivo": None}))
        e, f, campos = casa.estado_pretendido(
            {"status": "Ganho", "valor_proposta": 78987, "lugar": None,
             "concorrentes": [{"lugar": 1, "nome": "LATD", "valor": 78987}]}, papeis)
        self.assertEqual((e, f, campos["posicao"], campos["preco_proposto"]),
                         ("interessa", 5, 1, "78.987,00 EUR"))
        self.assertIn("1.º LATD 78.987,00 EUR", campos["top3"])
        self.assertIsNone(casa.estado_pretendido({"status": "Cancelado"}, papeis))
        self.assertIsNone(casa.estado_pretendido({"status": "TBD"}, papeis))

    def test_por_omissao_so_guarda_e_nao_toca_na_triagem(self):
        # decisao do Afonso a 02/09/2026: nada se aplica antes de o registo
        # estar validado -- o importador liga e guarda, e mais nada
        self._base_normal()
        rel = casa.importar(self._excel(self.INDICE, self.FOLHAS), ler=False)
        self.assertEqual(rel["ligadas"], 2)
        self.assertEqual(rel["aplicadas"], {"guardado": 2})
        self.assertEqual(self._le("5491/2026")["estado"], "novo")
        self.assertEqual(self._le("100/2026")["estado"], "novo")
        self.assertEqual(self._historico("5491/2026"), [])
        with radar.liga() as c:
            self.assertEqual(c.execute("SELECT resultado FROM casa WHERE id=1"
                                       ).fetchone()["resultado"], "guardado")
        self.assertIn("não se aplica", casa.texto_do_relatorio(rel))

    def test_desaplicar_repoe_a_triagem_da_copia(self):
        self._base_normal()
        with radar.liga() as c:
            c.execute("UPDATE anuncios SET estado='descartado', motivo='Falta de CV''s' "
                      "WHERE ref='100/2026'")
        copia = os.path.join(self.pasta, "antes.db")
        with radar.liga() as c:
            c.execute("VACUUM INTO ?", (copia,))
        casa.importar(self._excel(self.INDICE, self.FOLHAS), ler=False, triagem=True)
        self.assertEqual(self._le("5491/2026")["estado"], "interessa")
        repostos, apagadas = casa.desaplicar_da_copia(copia)
        self.assertEqual(repostos, 2)
        self.assertGreater(apagadas, 0)
        self.assertEqual(self._le("5491/2026")["estado"], "novo")
        self.assertIsNone(self._le("5491/2026")["preco_proposto"])
        # o que ja la estava antes da importacao volta tal e qual
        self.assertEqual((self._le("100/2026")["estado"], self._le("100/2026")["motivo"]),
                         ("descartado", "Falta de CV's"))
        self.assertEqual(self._historico("5491/2026"), [])
        with radar.liga() as c:
            self.assertEqual(c.execute("SELECT ref, resultado FROM casa WHERE id=1"
                                       ).fetchone()[:], ("5491/2026", "guardado"))

    def test_liga_e_aplica_a_triagem(self):
        self._base_normal()
        rel = casa.importar(self._excel(self.INDICE, self.FOLHAS), ler=False,
                            triagem=True)
        self.assertEqual(rel["fora"], ["Infraestructuras análisis y diseño"])
        self.assertEqual(rel["ligadas"], 2)
        self.assertEqual([a[1] for a in rel["ambiguas"]],
                         ["Bolsa de horas de desenvolvimento"])
        self.assertEqual(rel["sem"], [])
        perdido = self._le("5491/2026")
        with radar.liga() as c:
            fase_perdido = c.execute("SELECT id FROM fases WHERE papel='perdido'"
                                     ).fetchone()["id"]
        self.assertEqual((perdido["estado"], perdido["fase_id"], perdido["posicao"],
                          perdido["preco_proposto"]),
                         ("interessa", fase_perdido, 4, "399.632,00 EUR"))
        self.assertIn("1.º Axians 265.233,00 EUR", perdido["top3"])
        nao_fomos = self._le("100/2026")
        self.assertEqual((nao_fomos["estado"], nao_fomos["motivo"]),
                         ("descartado", "Fora do âmbito"))
        self.assertTrue(all(p["quem"] == "Excel" for p in self._historico("100/2026")))
        with radar.liga() as c:
            reg = casa.registo_de(c, "5491/2026")
            self.assertEqual((reg["id"], reg["ligacao"], reg["resultado"]),
                             (1, "auto", "aplicado"))
            ambiguo = c.execute("SELECT ref, candidatos FROM casa WHERE id=4").fetchone()
        self.assertIsNone(ambiguo["ref"])
        self.assertEqual(sorted(json.loads(ambiguo["candidatos"])),
                         ["300/2025", "301/2026"])
        self.assertEqual(radar.le_marca("excel_casa_em")[:4], "2026")

    def test_o_preco_base_desempata_quando_esta_lido(self):
        self._base_normal()
        with radar.liga() as c:
            c.execute("UPDATE anuncios SET preco_base='99.000,00 EUR' WHERE ref='301/2026'")
        rel = casa.importar(self._excel(self.INDICE, self.FOLHAS), ler=False,
                            triagem=True)
        self.assertEqual(rel["ambiguas"], [])
        with radar.liga() as c:
            self.assertEqual(c.execute("SELECT ref FROM casa WHERE id=4").fetchone()["ref"],
                             "301/2026")
        sub = self._le("301/2026")
        self.assertEqual(sub["estado"], "interessa")

    def test_ler_o_detalhe_a_meio_da_importacao_nao_tranca_a_base(self):
        # a importacao a serio rebentou com "database is locked": escrevia
        # a primeira linha da casa e ficava com a transaccao aberta
        # enquanto o ler_detalhe_de() gravava pela ligacao dele. Simula-se
        # a leitura com uma escrita por outra ligacao, como a verdadeira.
        self._base_normal()
        antigo = radar.ler_detalhe_de

        def falso_detalhe(ref):
            with radar.liga() as c:
                c.execute("UPDATE anuncios SET preco_base=?, detalhe_lido=1 WHERE ref=?",
                          ("99.000,00 EUR" if ref == "301/2026" else "1,00 EUR", ref))
            return True, ""
        radar.ler_detalhe_de = falso_detalhe
        try:
            rel = casa.importar(self._excel(self.INDICE, self.FOLHAS), ler=True)
        finally:
            radar.ler_detalhe_de = antigo
        self.assertEqual(rel["ambiguas"], [])
        self.assertGreaterEqual(rel["lidos"], 1)
        with radar.liga() as c:
            self.assertEqual(c.execute("SELECT ref FROM casa WHERE id=4").fetchone()["ref"],
                             "301/2026")
            self.assertEqual(c.execute("SELECT COUNT(*) n FROM casa").fetchone()["n"], 4)

    def test_o_ensaio_nao_grava_nada(self):
        self._base_normal()
        rel = casa.importar(self._excel(self.INDICE, self.FOLHAS), ensaio=True, ler=False,
                            triagem=True)
        self.assertTrue(rel["ensaio"])
        self.assertEqual(rel["ligadas"], 2)
        self.assertEqual(rel["aplicadas"], {"aplicado": 2})
        self.assertEqual(self._le("5491/2026")["estado"], "novo")
        with radar.liga() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) n FROM casa").fetchone()["n"], 0)

    def test_e_idempotente_e_nao_esmaga_decisao_humana(self):
        self._base_normal()
        # o Afonso marcou interessa no radar; o Excel diz "Não fomos"
        with radar.liga() as c:
            c.execute("UPDATE anuncios SET estado='interessa', fase_id=1 WHERE ref='100/2026'")
        caminho = self._excel(self.INDICE, self.FOLHAS)
        rel = casa.importar(caminho, ler=False, triagem=True)
        self.assertEqual(rel["aplicadas"], {"aplicado": 1, "conflito": 1})
        self.assertEqual(self._le("100/2026")["estado"], "interessa")
        rel2 = casa.importar(caminho, ler=False, triagem=True)
        self.assertEqual(rel2["aplicadas"], {"igual": 1, "conflito": 1})
        self.assertEqual(rel2["novas"], 0)
        # uma linha de conflito, e uma so, por muitas vezes que se importe
        conflitos = [p for p in self._historico("100/2026", "estado")
                     if "registo da casa diz" in p["detalhe"]]
        self.assertEqual(len(conflitos), 1)
        self.assertEqual(len(self._historico("5491/2026", "estado")), 1)

    def test_ligar_a_mao_resolve_a_alteracao_para_o_original(self):
        self._base_normal()
        casa.importar(self._excel(self.INDICE, self.FOLHAS), ler=False)
        # 301/2026 passa a ser uma alteracao de 300/2025
        with radar.liga() as c:
            c.execute("UPDATE anuncios SET estado='alteracao', altera='300/2025' "
                      "WHERE ref='301/2026'")
            ok, msg = casa.ligar_a_mao(c, 4, "301/2026", quem="Teste")
            self.assertTrue(ok, msg)
            self.assertEqual(c.execute("SELECT ref, ligacao, resultado FROM casa WHERE id=4"
                                       ).fetchone()[:], ("300/2025", "manual", "guardado"))
        self.assertEqual(self._le("300/2025")["estado"], "novo")   # sem triagem
        with radar.liga() as c:
            casa.ligar_a_mao(c, 4, "301/2026", quem="Teste", triagem=True)
        self.assertEqual(self._le("300/2025")["estado"], "interessa")
        # uma ligacao manual sobrevive a importacao seguinte
        rel = casa.importar(self._excel(self.INDICE, self.FOLHAS), ler=False)
        self.assertEqual(rel["manuais"], 1)
        with radar.liga() as c:
            self.assertEqual(c.execute("SELECT ref FROM casa WHERE id=4").fetchone()["ref"],
                             "300/2025")
            ok, msg = casa.ligar_a_mao(c, 4, "nada/2026")
        self.assertFalse(ok)

    def test_o_front_nao_mudou(self):
        # decisao do Afonso a 02/09/2026: nenhuma alteracao no front antes
        # de o registo estar consolidado -- a pagina /casa e o bloco da
        # ficha que chegaram a existir sairam, e nao voltam sem ele dizer
        self.assertNotIn("casa", radar.ITEM_DA_PAGINA)
        self.assertNotIn("/casa", [r.rule for r in radar.app.url_map.iter_rules()])
        self.assertFalse(hasattr(radar, "casa_cx"))
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

    def test_a_linha_do_excel_liga_se_ao_lote(self):
        lotes = radar.lotes_do_texto(self.LOTES)
        # pelo preco base do lote
        self.assertEqual(casa.lote_da_linha({"nome": "Biblioteca", "preco_base": 26833.6},
                                            lotes), 3)
        # pelo nome, quando o preco nao bate
        self.assertEqual(casa.lote_da_linha({"nome": "Bolsa de Horas - L2",
                                             "preco_base": 1.0}, lotes), 2)
        self.assertIsNone(casa.lote_da_linha({"nome": "Bolsa - L9", "preco_base": None},
                                             lotes))
        self.assertIsNone(casa.lote_da_linha({"nome": "x", "preco_base": 5.0}, []))
        # na importacao e no ligar a mao
        self._base_normal()
        with radar.liga() as c:
            c.execute("UPDATE anuncios SET lotes=? WHERE ref='5491/2026'",
                      (json.dumps(lotes),))
        indice = [list(self.INDICE[0])]
        indice[0][4] = 53667.2                       # o preco base do lote 1
        rel = casa.importar(self._excel(indice, {}), ler=False)
        self.assertEqual((rel["em_lotes"], rel["com_lote"]), (1, 1))
        with radar.liga() as c:
            self.assertEqual(c.execute("SELECT lote FROM casa WHERE id=1").fetchone()[0], 1)
            ok, msg = casa.ligar_a_mao(c, 1, "5491/2026")
        self.assertIn("lote 1 de 3", msg)

    def test_o_preco_que_e_a_soma_dos_lotes_e_o_conjunto_nao_um_lote(self):
        # As #23 e #26 do Excel traziam a soma exacta dos dois lotes e
        # ficavam com lote=NULL, indistinguiveis das que estao mesmo por
        # identificar -- foi o que obrigou a perguntar. A resposta dele
        # (03/09/2026): "o preco que la esta e o total do anuncio, nao
        # esta dividido por lotes". Zero e o conjunto; NULL continua a
        # ser "por identificar", e a #129 (valor da nossa proposta, que
        # nao bate com nada) tem de continuar NULL.
        lotes = radar.lotes_do_texto(self.LOTES)
        soma = 53667.20 + 268336.00 + 26833.60
        self.assertEqual(casa.lote_da_linha({"nome": "Biblioteca",
                                             "preco_base": soma}, lotes), 0)
        # e nao se conta como lote identificado
        self.assertFalse(casa.lote_da_linha({"nome": "Biblioteca",
                                             "preco_base": soma}, lotes))
        # um preco que nao bate com lote nenhum nem com a soma fica por identificar
        self.assertIsNone(casa.lote_da_linha({"nome": "Biblioteca",
                                              "preco_base": soma - 1000}, lotes))
        # o nome ganha a soma: um "Lote 2" explicito nao vira conjunto
        self.assertEqual(casa.lote_da_linha({"nome": "Biblioteca L2",
                                             "preco_base": soma}, lotes), 2)
        self._base_normal()
        with radar.liga() as c:
            c.execute("UPDATE anuncios SET lotes=? WHERE ref='5491/2026'",
                      (json.dumps(lotes),))
        indice = [list(self.INDICE[0])]
        indice[0][4] = soma
        rel = casa.importar(self._excel(indice, {}), ler=False)
        self.assertEqual((rel["em_lotes"], rel["com_lote"], rel["conjunto"]), (1, 0, 1))
        self.assertIn("pelo conjunto: 1", casa.texto_do_relatorio(rel))
        with radar.liga() as c:
            self.assertEqual(c.execute("SELECT lote FROM casa WHERE id=1").fetchone()[0], 0)
            ok, msg = casa.ligar_a_mao(c, 1, "5491/2026")
        self.assertIn("o preço é o conjunto", msg)

    def test_sem_anuncio_no_dr_fica_dito_e_nao_se_volta_a_procurar(self):
        # as respostas dele (02/09/2026): consultas previas, ajustes
        # directos e consultas preliminares nao tem anuncio no DR
        self._base_normal()
        caminho = self._excel(self.INDICE, self.FOLHAS)
        casa.importar(caminho, ler=False)
        with radar.liga() as c:
            ok, msg = casa.ligar_a_mao(c, 4, "nenhum", porque="consulta prévia")
            self.assertTrue(ok)
            ok, _ = casa.ligar_a_mao(c, 1, "?", porque="não sei")
            self.assertTrue(ok)
            ok, _ = casa.ligar_a_mao(c, 99, "nenhum")
            self.assertFalse(ok)
        rel = casa.importar(caminho, ler=False)
        self.assertEqual(rel["sem_dr"], 1)
        self.assertEqual(rel["ambiguas"], [])
        with radar.liga() as c:
            l4 = c.execute("SELECT ref, ligacao, porque_sem_ref FROM casa WHERE id=4"
                           ).fetchone()
            self.assertEqual(l4[:], (None, "nenhum", "consulta prévia"))
            # a nota "nao sei" sobrevive a importacao seguinte; a ligacao
            # automatica de #1 mantem-se
            l1 = c.execute("SELECT ref, porque_sem_ref FROM casa WHERE id=1").fetchone()
            self.assertEqual(l1[:], ("5491/2026", "não sei"))
        self.assertIn("sem anúncio no DR: 1", casa.texto_do_relatorio(rel))

    def test_a_pontuacao_e_por_contencao_do_nome_no_titulo(self):
        # o nome do Excel e uma abreviatura do titulo do DR: o que conta e
        # quantas palavras do Excel la estao, nao o tamanho do titulo
        self._base_normal()
        with radar.liga() as c:
            acervo = casa.Acervo(c, {2026})
        linha = {"nome": "Plataforma Central de Deteção Precoce", "entidade": "SPMS",
                 "ano": 2026, "preco_base": None}
        pontos = casa.pontuar(linha, acervo)
        self.assertEqual(pontos[0][1], "5491/2026")
        self.assertGreaterEqual(pontos[0][0], casa.LIMIAR)
        # uma palavra em comum nao chega
        linha = {"nome": "Plataforma de gestão documental", "entidade": "Outra",
                 "ano": 2026, "preco_base": None}
        pontos = casa.pontuar(linha, acervo)
        self.assertTrue(not pontos or pontos[0][0] < casa.LIMIAR)
        self.assertEqual(casa.decidir(pontos)[0], "")

    def test_sem_corpus_o_base_nao_liga_nada(self):
        self._base_normal()
        antigo = radar.ha_corpus
        radar.ha_corpus = lambda: False
        try:
            with radar.liga() as c:
                acervo = casa.Acervo(c, {2026})
                self.assertEqual(casa.ref_pelo_base(
                    c, {"status": "Perdido", "entidade": "SPMS", "ano": 2026,
                        "concorrentes": [{"lugar": 1, "nome": "X", "valor": 265233}]},
                    acervo), "")
        finally:
            radar.ha_corpus = antigo

    def test_as_razoes_do_excel_mapeiam_para_motivos(self):
        # os dois que ainda nao estao em MOTIVOS_ABANDONO entram la quando a
        # triagem do registo passar a aplicar-se (ver CLAUDE.md)
        self.assertEqual(set(casa.MAPA_RAZAO.values()) - set(radar.MOTIVOS_ABANDONO),
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

    Separa-se a condição da espera, como manda a casa: a `recolha`
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

    def test_a_configuracao_da_casa_nao_e_mexida(self):
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
    que o expôs. É a regra da casa: onde a documentação disser «em
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
            html_ = radar.app.test_client().get("/").get_data(as_text=True)
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
        r = self.cliente.get("/?estado=novo", environ_base=self.FORA)
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
        # o Referer com 127.0.0.1 e o Host com localhost sao a mesma casa
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

    def test_filtros_recolhidos_sem_filtro_e_abertos_com_filtro(self):
        html_ = self.cliente.get("/").get_data(as_text=True)
        self.assertIn("<details class='painel-filtros' id='painel-filtros'>", html_)
        html_ = self.cliente.get("/?cpv=72000000").get_data(as_text=True)
        self.assertIn("<details class='painel-filtros' id='painel-filtros' open>", html_)
        # o resumo do filtro fica na linha, para se saber o que está posto
        self.assertIn("CPV 72000000", html_.split("</summary>")[0])

    def test_os_blocos_continuam_la_dentro_e_os_guardados_sairam(self):
        html_ = self.cliente.get("/").get_data(as_text=True)
        dentro = html_.split("<details class='painel-filtros'")[1].split("</details>\n")[0]
        self.assertIn("class='cx filtros'", dentro)
        # 13/09/2026: a caixa "Filtros guardados" saiu das listas; o que
        # era guardar um filtro passou a ser o Interesse e os alertas
        self.assertNotIn("Filtros guardados", html_)
        self.assertNotIn("/filtros/guardar", html_)

    def test_o_teclado_esta_na_lista_e_diz_se(self):
        html_ = self.cliente.get("/").get_data(as_text=True)
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
        self.assertEqual([c for c, _, _, _ in radar.SECCOES_CONFIG],
                         ["conta", "interesse", "alertas", "importar",
                          "indicadores", "capturas", "recolha", "leitura", "copias"])
        self.assertEqual([c for c, _, _, so_admin in radar.SECCOES_CONFIG if so_admin],
                         ["indicadores", "capturas", "recolha", "leitura", "copias"])
        for seccao, _, _, _ in radar.SECCOES_CONFIG:
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
    CASA = [{"lote": 1, "status": "Perdido", "zoho_fase": "Won", "valor_proposta": 54432.0, "lugar": 3},
            {"lote": 2, "status": "Ganho", "zoho_fase": None, "valor_proposta": 169344.0, "lugar": 1},
            {"lote": 3, "status": "Perdido", "zoho_fase": None, "valor_proposta": 46368.0, "lugar": 2}]

    def test_o_caso_real_lote_a_lote(self):
        r = radar.resumo_dos_lotes(self.LOTES, self.CASA)
        self.assertEqual([l["estado"] for l in r["lotes"]], ["perdido", "ganho", "perdido"])
        self.assertEqual(r["fomos"], [1, 2, 3])
        self.assertEqual(r["por_estado"], {"perdido": [1, 3], "ganho": [2]})
        self.assertIsNone(r["conjunto"])
        # o Zoho «Won» no L1 não o faz ganho: é o Excel que manda num lote
        self.assertEqual(r["lotes"][0]["lugar"], 3)
        self.assertEqual(radar.frase_dos_lotes(r), "fomos a todos os 3 lotes")

    def test_a_alguns_e_a_nenhum(self):
        r = radar.resumo_dos_lotes(self.LOTES, self.CASA[1:2])
        self.assertEqual(r["fomos"], [2])
        self.assertEqual(radar.frase_dos_lotes(r), "fomos a 1 dos 3 lotes")
        chips = radar.chips_dos_lotes(r)
        self.assertIn("L2 ganho", chips)
        self.assertIn("lote-fora", chips)            # L1 e L3, a que não fomos
        self.assertEqual(radar.chips_dos_lotes(r, so_estado="perdido"), "")
        r = radar.resumo_dos_lotes(self.LOTES, [])
        self.assertEqual(r["fomos"], [])
        self.assertEqual(radar.frase_dos_lotes(r), "3 lotes; sem registo de a que fomos")

    def test_o_conjunto_nao_e_um_lote(self):
        # #23 e #26 (3/09/2026): o preço da linha é a soma — casa.lote = 0
        r = radar.resumo_dos_lotes(self.LOTES[:2], [{"lote": 0, "status": "Perdido",
                                                    "zoho_fase": "Lost"}])
        self.assertEqual(r["fomos"], [])
        self.assertTrue(r["conjunto"])
        self.assertEqual(radar.frase_dos_lotes(r), "fomos ao conjunto dos 2 lotes")
        self.assertEqual(casa.estado_do_lote(r["conjunto"]), "perdido")

    def test_sem_lotes_e_none(self):
        self.assertIsNone(radar.resumo_dos_lotes([], self.CASA))
        self.assertEqual(radar.frase_dos_lotes(None), "")
        self.assertEqual(radar.lotes_de({"lotes": "não é json"}), [])


class TestLotesNoQuadroENaFicha(BaseTemporaria):
    """A separação no fim: o cartão está no Ganho, os lotes perdidos
    aparecem como cartão separado no Perdido. E a ficha tem o bloco."""

    def setUp(self):
        super().setUp()
        self.cliente = radar.app.test_client()
        fases = {(radar._valor(f, "papel") or ""): f["id"] for f in radar.listar_fases()}
        self.ganho, self.perdido = fases["ganho"], fases["perdido"]
        with radar.liga() as c:
            # com texto e detalhe lido: sem texto a ficha ia ao DR buscar o
            # detalhe (e a captura verdadeira existe na pasta), e o que
            # voltava escrevia por cima dos lotes de ensaio
            c.execute("INSERT INTO anuncios (ref, titulo, entidade, data_pub, tipo, url, "
                      "estado, fase_id, lotes, texto, detalhe_lido) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?,1)",
                      ("1947/2026", "Servidor de terminologias", "SPMS", "2026-02-01",
                       "Anúncio de procedimento", "https://dr/1947", "interessa", self.ganho,
                       json.dumps(TestResumoDosLotes.LOTES),
                       "1 - IDENTIFICAÇÃO E CONTACTOS DA ENTIDADE ADJUDICANTE\n"
                       "Designação da entidade adjudicante: SPMS\n"
                       "Procedimento com lotes? Sim\n"))
            for i, l in enumerate(TestResumoDosLotes.CASA, 1):
                c.execute("INSERT INTO casa (id, nome, ref, lote, status, zoho_fase, "
                          "valor_proposta, lugar, resultado) VALUES (?,?,?,?,?,?,?,?,?)",
                          (i, "Pilar 4 - L%d" % l["lote"], "1947/2026", l["lote"], l["status"],
                           l["zoho_fase"], l["valor_proposta"], l["lugar"], "guardado"))

    def coluna(self, html_, fase_id):
        return html_.split("data-fase='%d'>" % fase_id)[1].split("</div></div>")[0]

    def test_o_cartao_diz_a_que_lotes_fomos_e_o_fim_separa(self):
        html_ = self.cliente.get("/quadro").get_data(as_text=True)
        ganho = self.coluna(html_, self.ganho)
        self.assertIn("id='c-1947-2026'", ganho)
        self.assertIn("fomos a todos os 3 lotes", ganho)
        self.assertIn("L2 ganho", ganho)
        self.assertIn("L1 perdido", ganho)          # o cartão principal diz tudo
        perdido = self.coluna(html_, self.perdido)
        self.assertIn("id='c-1947-2026-perdido'", perdido)
        self.assertIn("2 lotes perdidos", perdido)
        self.assertIn("L1 perdido", perdido)
        self.assertIn("L3 perdido", perdido)
        self.assertNotIn("L2 ganho", perdido)
        self.assertIn("draggable='false'", perdido)
        # e no Ganho não há cartão separado (não há lote ganho fora dele)
        self.assertNotIn("id='c-1947-2026-ganho'", ganho)

    def test_o_redesenho_depois_de_arrastar_leva_os_lotes(self):
        carta, _ = radar.carta_e_contas("1947/2026", {self.ganho})
        self.assertIn("carta-lotes", carta)
        self.assertIn("L2 ganho", carta)

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

    def test_sem_registo_da_casa_a_ficha_diz_o(self):
        with radar.liga() as c:
            c.execute("DELETE FROM casa")
        html_ = self.cliente.get("/anuncio/1947%2F2026").get_data(as_text=True)
        self.assertIn("sem registo de a que fomos", html_)
        self.assertNotIn("<th>A casa</th>", html_)
        # e no quadro nao ha separacao nenhuma
        q = self.cliente.get("/quadro").get_data(as_text=True)
        self.assertNotIn("c-1947-2026-perdido", q)
        self.assertIn("3 lotes; sem registo", q)

    def test_sem_lotes_nao_ha_bloco(self):
        with radar.liga() as c:
            c.execute("UPDATE anuncios SET lotes='' WHERE ref='1947/2026'")
        html_ = self.cliente.get("/anuncio/1947%2F2026").get_data(as_text=True)
        self.assertNotIn("id='lotes'", html_)
        self.assertNotIn("href='#lotes'", html_)


class TestModeloDaCasa(BaseTemporaria):
    """O registo da casa pelo modelo (8/09/2026): o radar dita o Excel, o
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
        casa.escrever_modelo(caminho)
        wb = load_workbook(caminho)
        ws = wb[casa.FOLHA_MODELO]
        for l in linhas:
            ws.append(l)
        wb.save(caminho)
        return caminho

    def test_o_modelo_tem_as_colunas_e_as_listas(self):
        from openpyxl import load_workbook
        caminho = casa.escrever_modelo(os.path.join(self.pasta, "modelo.xlsx"))
        wb = load_workbook(caminho)
        ws = wb[casa.FOLHA_MODELO]
        self.assertEqual([c.value for c in ws[1]], [t for t, _ in casa.COLUNAS_MODELO])
        validacoes = [dv.formula1 for dv in ws.data_validations.dataValidation]
        self.assertTrue(any("Não fomos" in f and "Ganho" in f for f in validacoes))
        self.assertTrue(any("Preço base baixo" in f for f in validacoes))
        self.assertIn("Instruções", wb.sheetnames)
        # sem linhas de dados: o modelo importado em branco nao entra nada
        self.assertEqual(casa.ler_modelo(caminho), [])

    def test_ler_normaliza_e_aponta_erros_de_forma(self):
        caminho = self.preenchido([
            ["1947-2026", 2, "ganho", None, "169.344,00", 1, "Nós; Empresa B ; Empresa C", "Afonso", "ok"],
            [" 22285 / 2026 ", None, "Não fomos", "preco base demasiado baixo", None, None, None, None, None],
            ["lixo", "x", "Talvez", None, None, "primeiro", None, None, None],
        ])
        linhas = casa.ler_modelo(caminho)
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
            linhas, contagens = casa.ensaio_modelo(c, casa.ler_modelo(caminho))
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
            linhas, _ = casa.ensaio_modelo(c, casa.ler_modelo(caminho))
            r = casa.aplicar_modelo(c, linhas, quem="teste")
        self.assertEqual((r["gravadas"], r["anuncios"], r["aplicadas"]), (3, 2, 2))
        with radar.liga() as c:
            fases = {radar._valor(f, "papel"): f["id"] for f in radar.listar_fases()}
            a = c.execute("SELECT estado, fase_id, preco_proposto, posicao, responsavel "
                          "FROM anuncios WHERE ref='1947/2026'").fetchone()
            # ganhamos um lote: o cartao fica no Ganho, com a proposta desse lote
            self.assertEqual((a["estado"], a["fase_id"], a["posicao"], a["responsavel"]),
                             ("interessa", fases["ganho"], 1, "Afonso"))
            self.assertIn("169.344", a["preco_proposto"])
            b = c.execute("SELECT estado, motivo FROM anuncios WHERE ref='22285/2026'").fetchone()
            self.assertEqual((b["estado"], b["motivo"]), ("descartado", "Falta de CV's"))
            self.assertEqual(c.execute("SELECT COUNT(*) FROM casa WHERE folha='modelo'").fetchone()[0], 3)
            self.assertEqual(c.execute("SELECT lote FROM casa WHERE ref='22285/2026'").fetchone()[0], 0)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM pessoas WHERE nome='Afonso'").fetchone()[0], 1)
            # e a ficha dos lotes ve o registo
            linhas_casa = casa.linhas_de_lotes(c, ["1947/2026"])["1947/2026"]
        resumo = radar.resumo_dos_lotes(TestResumoDosLotes.LOTES, linhas_casa)
        self.assertEqual(resumo["por_estado"], {"perdido": [1], "ganho": [2]})
        # importar outra vez a mesma linha substitui, nao duplica
        with radar.liga() as c:
            linhas, _ = casa.ensaio_modelo(c, casa.ler_modelo(caminho))
            casa.aplicar_modelo(c, linhas, quem="teste")
            self.assertEqual(c.execute("SELECT COUNT(*) FROM casa").fetchone()[0], 3)

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
            self.assertEqual(c.execute("SELECT COUNT(*) FROM casa").fetchone()[0], 0)
        r = self.cliente.post("/configuracoes/importar/confirmar", data={"ficheiro": m.group(1)})
        self.assertEqual(r.status_code, 302)
        self.assertIn("Importado", unquote_plus(r.headers["Location"]))
        with radar.liga() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM casa").fetchone()[0], 1)
            self.assertEqual(c.execute("SELECT estado FROM anuncios WHERE ref='1947/2026'").fetchone()[0],
                             "interessa")
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
            fases = {radar._valor(f, "papel"): f["id"] for f in radar.listar_fases()}
            for ref, estado, fase in (("1/2026", "interessa", fases["ganho"]),
                                      ("2/2026", "descartado", None),
                                      ("3/2026", "alteracao", None),
                                      ("4/2026", "novo", None)):
                c.execute("INSERT INTO anuncios (ref, titulo, entidade, data_pub, tipo, url, "
                          "estado, fase_id, responsavel, motivo) VALUES (?,?,?,?,?,?,?,?,?,?)",
                          (ref, "t", "e", "2026-01-01", "a", "u", estado, fase,
                           "Afonso" if estado == "interessa" else None,
                           "Fora do âmbito" if estado == "descartado" else None))
            c.execute("INSERT INTO etiquetas (nome, cor) VALUES ('x', '#000')")
            c.execute("INSERT INTO historico (ref, quem, accao, detalhe, quando) VALUES ('1/2026','a','b','c','d')")
            c.execute("INSERT INTO filtros_guardados (nome, consulta) VALUES ('f', 'q=x')")
            c.execute("INSERT INTO casa (nome, ref) VALUES ('linha', '1/2026')")
            c.execute("INSERT INTO pessoas (nome) VALUES ('Afonso')")

    def test_apaga_o_que_e_do_utilizador_e_guarda_o_acervo(self):
        n = radar.repor_estado_zero()
        self.assertEqual(n["triagem reposta"], 2)
        self.assertEqual(n["casa"], 1)
        with radar.liga() as c:
            estados = dict(c.execute("SELECT ref, estado FROM anuncios"))
            self.assertEqual(estados, {"1/2026": "novo", "2/2026": "novo",
                                       "3/2026": "alteracao", "4/2026": "novo"})
            self.assertEqual(c.execute("SELECT COUNT(*) FROM anuncios WHERE fase_id IS NOT NULL "
                                       "OR responsavel IS NOT NULL OR motivo IS NOT NULL").fetchone()[0], 0)
            for tabela in ("etiquetas", "historico", "filtros_guardados", "casa", "pessoas"):
                self.assertEqual(c.execute("SELECT COUNT(*) FROM %s" % tabela).fetchone()[0], 0, tabela)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM fases").fetchone()[0], 6)
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
            cliente.get("/")
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
        for rota in ("/", "/quadro", "/contratos", "/configuracoes/conta",
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
        lista_t = tester.get("/", environ_base=self.FORA).get_data(as_text=True)
        lista_a = admin.get("/", environ_base=self.FORA).get_data(as_text=True)
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
        html_ = radar.app.test_client().get("/").get_data(as_text=True)
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
        html_ = radar.app.test_client().get("/").get_data(as_text=True)
        self.assertIn("details class='arvore'", html_)
        self.cfg.update(interesse_activo=True, interesse_cpv="72000000")
        html_ = radar.app.test_client().get("/").get_data(as_text=True)
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
        colunas = ",".join(valores)
        with radar.liga() as c:
            c.execute("INSERT INTO anuncios (ref,%s) VALUES (?%s)"
                      % (colunas, ",?" * len(valores)),
                      [ref] + list(valores.values()))
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



class TestListaEmCurso(BaseTemporaria):
    """A tabela do «Em curso» (14/09/2026), com as colunas que o Afonso
    mandou: título, cliente, preço, esclarecimentos, entrega, tipologia,
    estado da proposta, CV, proposta técnica, notas, plataforma, CoE,
    responsável. O que a casa decide grava-se linha a linha."""

    def _anuncio(self, ref="60/2026", **campos):
        valores = {"estado": "interessa", "titulo": "Aquisição de software",
                   "entidade": "Câmara de Lisboa", "preco_base": "118.500,00 EUR",
                   "plataforma": "acingov", "data_pub": "2026-09-01",
                   "prazo": "2026-09-30", "texto": "x", "detalhe_lido": 1,
                   "url": "https://x/anuncio-procedimento/k-60"}
        valores.update(campos)
        with radar.liga() as c:
            c.execute("INSERT INTO anuncios (ref,%s) VALUES (?%s)"
                      % (",".join(valores), ",?" * len(valores)),
                      [ref] + list(valores.values()))
        return ref

    def test_as_colunas_e_os_valores_da_base(self):
        fase = radar.listar_fases()[1]          # a segunda fase da base nova
        ref = self._anuncio(fase_id=fase["id"], responsavel="Afonso", tipologia="turnkey",
                            cv="sim", notas="pedir CVs ao João", coe="Data")
        html_ = radar.app.test_client().get("/lista").get_data(as_text=True)
        for coluna in ("Título", "Cliente", "Preço", "Esclarecimentos", "Entrega",
                       "Tipologia", "Estado da proposta", "CV", "Proposta técnica",
                       "Notas", "Plataforma", "CoE", "Responsável"):
            self.assertIn("<th>%s</th>" % coluna, html_)
        self.assertIn("Aquisição de software", html_)
        self.assertIn("Câmara de Lisboa", html_)
        self.assertIn("118.500,00 EUR", html_)
        self.assertIn(html.escape(fase["nome"]), html_)     # a fase e o estado
        self.assertIn("10/09/2026", html_)                   # o primeiro terço de 29 dias
        self.assertIn("value='turnkey' selected", html_)
        self.assertIn("value='sim' selected", html_)
        self.assertIn("value='pedir CVs ao João'", html_)
        self.assertIn("value='Data'", html_)
        self.assertIn("value='Afonso'", html_)
        self.assertIn("action='/lista/%s'" % quote(ref, safe=""), html_)
        # so os interessados: um por ver nao entra
        self._anuncio("61/2026", estado="novo", titulo="Fora da lista")
        html_ = radar.app.test_client().get("/lista").get_data(as_text=True)
        self.assertNotIn("Fora da lista", html_)

    def test_gravar_uma_linha_muda_so_o_que_veio_e_regista_so_o_que_mudou(self):
        ref = self._anuncio(coe="Data")
        cliente = radar.app.test_client()
        r = cliente.post("/lista/" + ref, data={
            "tipologia": "consulting", "cv": "não", "proposta_tecnica": "sim",
            "notas": "  ver  os  lotes ", "coe": "Data", "responsavel": "Rita"})
        self.assertIn("guardada", unquote_plus(r.headers["Location"]))
        with radar.liga() as c:
            a = c.execute("SELECT * FROM anuncios WHERE ref=?", (ref,)).fetchone()
            registos = [r_["accao"] for r_ in c.execute(
                "SELECT accao FROM historico WHERE ref=? ORDER BY id", (ref,))]
        self.assertEqual((a["tipologia"], a["cv"], a["proposta_tecnica"], a["notas"],
                          a["coe"], a["responsavel"]),
                         ("consulting", "não", "sim", "ver os lotes", "Data", "Rita"))
        # o CoE nao mudou: nao ha registo dele
        self.assertEqual(registos, ["tipologia", "CV", "proposta técnica", "notas",
                                    "responsável"])
        self.assertIn("Rita", radar.listar_pessoas())
        # um valor fora da lista e recusado, com aviso
        r = cliente.post("/lista/" + ref, data={"tipologia": "outra"})
        self.assertIn("não é um valor", unquote_plus(r.headers["Location"]))
        with radar.liga() as c:
            self.assertEqual(c.execute("SELECT tipologia FROM anuncios WHERE ref=?",
                                       (ref,)).fetchone()[0], "consulting")

    def test_a_lista_esta_na_navegacao_do_em_curso(self):
        vistas = [v for n in radar.NAV if n[0] == "emcurso" for v in n[3]]
        self.assertEqual([v[0] for v in vistas], ["quadro", "calendario", "lista"])
        html_ = radar.app.test_client().get("/lista").get_data(as_text=True)
        self.assertIn("Sem anúncios interessados", html_)


class TestNomeRadarGov(unittest.TestCase):
    """14/09/2026: «a aplicação diz RadarDR mas tem de dizer RadarGov e
    Gov tem de ser a azul». O nome esta em dois sitios (a barra e o ecra
    de entrar) e o azul da barra e um claro proprio: o --azul da paleta
    sobre a barra escura dava 2,3:1."""

    def test_o_nome_e_radargov_nos_dois_sitios_e_o_gov_e_azul(self):
        self.assertIn('<a class="logo" href="/">Radar<span>Gov</span></a>', radar.BASE)
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
        self.assertIn("cpv8 LIKE ?", frag)
        self.assertEqual(vals, ["72%"])
        frag, vals = radar.condicao_do_interesse_contratos(
            args={}, cfg=dict(self.cfg, interesse_cpv_excl="72212000"))
        self.assertIn("NOT IN", frag)
        self.assertEqual(vals, ["72%", "72212%"])
        self.assertEqual(radar.condicao_do_interesse_contratos(
            args={"interesse": "nao"}, cfg=self.cfg), ("", []))
        self.assertEqual(radar.condicao_do_interesse_contratos(
            args={}, cfg=dict(self.cfg, interesse_activo=False)), ("", []))
        self.assertEqual(radar.condicao_do_interesse_contratos(
            args={}, cfg=dict(self.cfg, interesse_cpv="")), ("", []))

    def test_o_interesse_e_uma_pergunta(self):
        # 14/09/2026: «abre-se e nao se ve contrato nenhum» -- com
        # interesse definido o Mercado abre logo com os CPV da casa
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
        self.assertEqual(vals[-1], "72%")
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
        lista = cliente.get("/?estado=").get_data(as_text=True)
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
        html_ = radar.app.test_client().get("/").get_data(as_text=True)
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
        html_ = radar.app.test_client().get("/?prazo=urgente&op=ou").get_data(as_text=True)
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
        self.assertIn("data-sugere='anuncios'", radar.app.test_client().get("/").get_data(as_text=True))
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
        html_ = radar.app.test_client().get("/?nif=509540716").get_data(as_text=True)
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
            c.execute("INSERT INTO entidades VALUES ('509540716','509540716',"
                      "'SPMS - Serviços Partilhados do Ministério da Saúde, E. P. E.', 15)")
            c.execute("INSERT INTO entidades VALUES ('500000001','500000001','Sport Lisboa e Benfica', 2)")
            c.execute("INSERT INTO entidades VALUES ('500000002','500000002','Hospital de Espinho', 1)")
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


if __name__ == "__main__":

    unittest.main(verbosity=2)
