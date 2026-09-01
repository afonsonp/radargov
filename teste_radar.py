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

import datetime
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radar


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

    def test_tira_caracteres_proibidos_no_windows(self):
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
        import tempfile
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
        import tempfile, zipfile
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
        # dizer "scan" a um PDF cifrado manda a pessoa buscar o OCR
        # quando o que falta é um pacote de Python
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
        self.fornecedores, self.ler_chave = radar.FORNECEDORES, radar.ler_chave
        radar.FORNECEDORES = self.FALSOS

    def tearDown(self):
        radar.FORNECEDORES = self.fornecedores
        radar.ler_chave = self.ler_chave

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
        self.um_pedido = radar._um_pedido
        self.chamados = []

    def tearDown(self):
        radar._um_pedido = self.um_pedido
        radar._ESGOTADOS.clear()

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
        # anunciam: o número mostrado tem de dar a lista que o link abre
        ini = datetime.date.fromisoformat(valores[0])
        fim = datetime.date.fromisoformat(valores[1])
        self.assertEqual((fim - ini).days, radar.DIAS_URGENTE)

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
        self.assertEqual(fim, (hoje + datetime.timedelta(
            days=radar.DIAS_URGENTE)).isoformat())

    def test_o_filtro_urgente_usa_a_mesma_janela(self):
        _, valores = radar.condicoes({"prazo": "urgente", "estado": ""})
        inicio, fim = radar.janela_urgente(datetime.date.today())
        self.assertIn(inicio, valores)
        self.assertIn(fim, valores)


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
        import tempfile
        self.pasta = tempfile.mkdtemp()
        self.db_antigo = radar.DB
        self.docs_antigo = radar.DOCS
        radar.DB = os.path.join(self.pasta, "ensaio.db")
        radar.DOCS = os.path.join(self.pasta, "documentos")
        radar.iniciar_db()          # cria o esquema e põe as marcas

    def tearDown(self):
        import gc
        import shutil
        radar.DB = self.db_antigo
        radar.DOCS = self.docs_antigo
        gc.collect()                # fecha ligações penduradas do liga()
        shutil.rmtree(self.pasta, ignore_errors=True)


class TestMigracoesDoSaneamento(BaseTemporaria):
    """Saneamento de 30/08/2026 (A1/A2/A3): cada migração tem de poder
    correr duas vezes sem efeito na segunda. Foi a falta delas que
    deixou 30 documentos presos num erro obsoleto, 12 análises no
    formato antigo e duas chaves mortas na tabela estado."""

    def test_erro_cryptography_volta_a_fila_e_uma_vez_so(self):
        with radar.liga() as c:
            c.execute("DELETE FROM estado WHERE chave='erros_extraccao_limpos'")
            c.executemany(
                "INSERT INTO documentos (ref,nome,texto,texto_estado) "
                "VALUES (?,?,?,?)",
                [("1/2026", "CE.pdf", "",
                  "erro: cryptography>=3.1 is required for AES algorithm"),
                 ("1/2026", "PC.pdf", "t", "ok"),
                 ("1/2026", "digit.pdf", "", "scan")])
        radar.iniciar_db()
        with radar.liga() as c:
            estados = dict(c.execute("SELECT nome, texto_estado "
                                     "FROM documentos"))
        self.assertIsNone(estados["CE.pdf"])     # voltou à fila
        self.assertEqual(estados["PC.pdf"], "ok")
        self.assertEqual(estados["digit.pdf"], "scan")
        # segunda passagem: a marca segura, e um erro novo com a mesma
        # cara já não é desta migração — é do caminho de retentativa
        with radar.liga() as c:
            c.execute("UPDATE documentos SET texto_estado="
                      "'erro: cryptography outra vez' WHERE nome='digit.pdf'")
        radar.iniciar_db()
        with radar.liga() as c:
            fica = c.execute("SELECT texto_estado FROM documentos "
                             "WHERE nome='digit.pdf'").fetchone()[0]
        self.assertEqual(fica, "erro: cryptography outra vez")

    def test_modelo_antigo_converte_e_duas_passagens_dao_o_mesmo(self):
        with radar.liga() as c:
            c.execute("DELETE FROM estado WHERE chave='modelo_com_fornecedor'")
            c.executemany("INSERT INTO analise (ref, modelo) VALUES (?,?)",
                          [("1/2026", "openai/gpt-oss-120b"),
                           ("2/2026", "groq:openai/gpt-oss-120b"),
                           ("3/2026",
                            "nvidia:openai/gpt-oss-120b, openai/gpt-oss-120b")])
        radar.iniciar_db()
        with radar.liga() as c:
            saiu = dict(c.execute("SELECT ref, modelo FROM analise"))
        self.assertEqual(saiu["1/2026"], "groq:openai/gpt-oss-120b")
        self.assertEqual(saiu["2/2026"], "groq:openai/gpt-oss-120b")
        self.assertEqual(saiu["3/2026"],
                         "nvidia:openai/gpt-oss-120b, groq:openai/gpt-oss-120b")
        radar.iniciar_db()          # segunda vez: nada muda
        with radar.liga() as c:
            outra = dict(c.execute("SELECT ref, modelo FROM analise"))
        self.assertEqual(saiu, outra)

    def test_chaves_legadas_do_estado_saem(self):
        with radar.liga() as c:
            c.execute("INSERT OR REPLACE INTO estado VALUES ('ultimo_aviso','x')")
            c.execute("INSERT OR REPLACE INTO estado "
                      "VALUES ('ultimo_aviso_texto','y')")
        radar.iniciar_db()
        with radar.liga() as c:
            n = c.execute("SELECT COUNT(*) FROM estado "
                          "WHERE chave LIKE 'ultimo_aviso%'").fetchone()[0]
        self.assertEqual(n, 0)


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


class TestNavegacaoPorIntencoes(unittest.TestCase):
    """A navegação por intenções (31/08/2026): primeiro cinco itens, e
    na mesma noite quatro — o Afonso, depois de usar, fundiu a Triagem
    e a Pesquisa numa lista só ("ambas são a mesma coisa"). O que isto
    trava: repor os Indicadores na barra (saíram por decisão 11.6-A) ou
    voltar a separar a lista em duas páginas."""

    def test_quatro_itens_por_ordem_de_uso(self):
        self.assertEqual([n[0] for n in radar.NAV],
                         ["anuncios", "emcurso", "mercado", "alertas"])

    def test_indicadores_fora_da_navegacao(self):
        chaves = {n[0] for n in radar.NAV}
        chaves.update(v[0] for n in radar.NAV for v in n[3])
        self.assertNotIn("indicadores", chaves)
        # mas a página existe e as migalhas sabem o nome dela
        self.assertIn("Indicadores", radar.migalhas_de("indicadores"))

    def test_quadro_e_calendario_vivem_sob_em_curso(self):
        self.assertEqual(radar.ITEM_DA_PAGINA["quadro"], "emcurso")
        self.assertEqual(radar.ITEM_DA_PAGINA["calendario"], "emcurso")

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
        antigo = radar.BASE_DIR
        radar.BASE_DIR = self.pasta
        try:
            if criar_captura:
                with open(os.path.join(self.pasta, "curl_DR.txt"),
                          "w", encoding="utf-8") as f:
                    f.write("curl 'https://exemplo'")
            radar.registar_expiracao_token("curl_DR", "sem JSON")
        finally:
            radar.BASE_DIR = antigo

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
        self.assertEqual(a["detalhe_lido"], 1)   # nada para ler no DR
        self.assertEqual(a["data_pub"], "2026-08-31")
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
        import tempfile
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
        import tempfile
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


class CorpusTemporario(unittest.TestCase):
    """Como a BaseTemporaria, mas para o contratos.db: um corpus
    TEMPORÁRIO — nunca o verdadeiro —, criado e deitado fora por teste."""

    def setUp(self):
        import tempfile
        self.pasta = tempfile.mkdtemp()
        self.corpus_antigo = radar.CORPUS
        radar.CORPUS = os.path.join(self.pasta, "ensaio-contratos.db")

    def tearDown(self):
        import gc
        import shutil
        radar.CORPUS = self.corpus_antigo
        gc.collect()                # fecha ligações penduradas
        shutil.rmtree(self.pasta, ignore_errors=True)

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


if __name__ == "__main__":

    unittest.main(verbosity=2)
