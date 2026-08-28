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
        self.assertIn("titulo LIKE", onde)
        self.assertNotIn("entidade LIKE", onde)

    def test_entidade_procura_so_na_entidade(self):
        onde, _ = radar.condicoes({"ent": "Camara", "estado": ""})
        self.assertIn("entidade LIKE", onde)
        self.assertNotIn("titulo LIKE", onde)

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


if __name__ == "__main__":

    unittest.main(verbosity=2)
