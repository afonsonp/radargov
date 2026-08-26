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

    def test_reconhece_os_dois_hosts(self):
        for host in ("anogov.com", "compraspt.com"):
            with self.subTest(host=host):
                alvo = ('href="https://www.%s/x/decryptservlet?'
                        'papId=1&amp;fichId=2"' % host)
                achados = radar.RX_DOC_JSF.findall(alvo)
                self.assertEqual(len(achados), 1)

    def test_ignora_outros_enderecos(self):
        self.assertEqual(
            radar.RX_DOC_JSF.findall('href="https://exemplo.pt/decryptservlet"'),
            [])

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
               "preco_base": "150.000,00 EUR", "prazo": "2026-09-01"}

    def tabela(self, texto=None, anuncio=None):
        return radar.essencial_do_anuncio(
            anuncio or self.ANUNCIO,
            radar.seccoes_do_texto(texto if texto is not None else self.TEXTO))

    def test_tem_os_doze_campos(self):
        self.assertEqual(len(self.tabela()), 12)

    def test_preenche_o_que_vem_do_anuncio(self):
        d = {r: v for r, v, _ in self.tabela()}
        self.assertEqual(d["Nome do projeto"], "Aquisição de X")
        self.assertEqual(d["Entidade adjudicante"], "Município Y")
        self.assertEqual(d["Preço base"], "150.000,00 EUR")
        self.assertEqual(d["Data de submissão da proposta"], "2026-09-01")
        self.assertEqual(d["Duração do contrato"], "36 MESES")
        self.assertEqual(d["Critério de adjudicação"], "Preço")

    def test_local_junta_concelho_e_distrito(self):
        d = {r: v for r, v, _ in self.tabela()}
        self.assertEqual(d["Local de prestação de serviços"], "Montijo, Setúbal")

    def test_local_nao_se_repete_quando_sao_iguais(self):
        t = "9 - LOCAL DA EXECUÇÃO DO CONTRATO\nConcelho: Lisboa\nDistrito: Lisboa\n"
        d = {r: v for r, v, _ in self.tabela(t)}
        self.assertEqual(d["Local de prestação de serviços"], "Lisboa")

    def test_renovacoes_aparecem_na_duracao(self):
        t = ("10 - PRAZO DE EXECUÇÃO DO CONTRATO\n"
             "Prazo de execução do contrato: 12 MESES\n"
             "Previsão de renovações: Sim\n")
        d = {r: v for r, v, _ in self.tabela(t)}
        self.assertIn("renovações", d["Duração do contrato"])

    def test_os_cinco_que_faltam_estao_assinalados(self):
        # nao se omitem: se nao aparecessem, parecia que nao existiam
        faltam = {r for r, _, f in self.tabela() if f}
        self.assertEqual(faltam, {
            "Preço anormalmente baixo", "Data de esclarecimentos",
            "Objeto, âmbito e características", "Equipa",
            "Documentos que constituem a proposta"})

    def test_diz_em_que_documento_esta_o_que_falta(self):
        for _, _, falta in self.tabela():
            if falta:
                self.assertTrue("Caderno de Encargos" in falta
                                or "Programa de Concurso" in falta)


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
