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
        self.assertEqual(d["Data de submissão da proposta"], "2026-09-01")
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
        self.assertIn("2026-08-22", valor)   # prazo 2026-09-01
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

    def test_tira_linhas_vazias_e_espacos(self):
        self.assertEqual(radar.limpa_campo("  a  \\n\\n  b "),
                         "a" + chr(10) + "b")

    def test_aguenta_vazio(self):
        self.assertEqual(radar.limpa_campo(None), "")


if __name__ == "__main__":

    unittest.main(verbosity=2)
