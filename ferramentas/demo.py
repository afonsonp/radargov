"""Gera os ecrãs do `/demo` (`site/demo/<n>.html`): a visita guiada ao Mira Gov, para quem ainda
não tem conta (5/10/2026, pedido dele: «um walkthrough completo da app,
que não permite utilizar mesmo, para o cliente ver sozinho e pedir a
demo»).

Cada passo é o HTML VERDADEIRO de uma rota, como o `ferramentas/ecrans.py`
o tira -- mas sobre uma base TEMPORÁRIA, com uma empresa inventada
(«Climatérmica», AVAC). Nada sai das bases verdadeiras: nem um anúncio,
nem uma proposta, nem um contrato. Os scripts saem, os formulários e as
ligações ficam mortos. As legendas estão no `site/demo.html`.

    python ferramentas/demo.py [PASTA]

Não vão para o git: o `actualizar.sh` (e o `instalar.sh`) gera-os de
cada vez, e assim a visita mostra sempre os ecrãs do código instalado.
A PASTA é para os testes; por omissão é `site/demo/`.
"""
import os
import re
import sys
import tempfile
from datetime import date, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)
import fitz  # noqa: E402
import radar  # noqa: E402

# --- a base inventada ----------------------------------------------------
# Tudo aponta para uma pasta temporária ANTES de qualquer ligação: é o que
# a `BaseTemporaria` dos testes faz, pela mesma razão.
PASTA = tempfile.mkdtemp(prefix="miragov-demo-")
for nome, ficheiro in (("DB", "radar.db"), ("CORPUS", "contratos.db"),
                       ("CONFIG", "config.json"), ("DOCS", "documentos"),
                       ("COPIAS", "copias")):
    setattr(radar, nome, os.path.join(PASTA, ficheiro))
radar.BASE_DIR = PASTA

HOJE = date.today()


def dia(n):
    return (HOJE + timedelta(days=n)).isoformat()


radar.iniciar_db()
radar.iniciar_corpus()
EMPRESA = radar.criar_empresa("Climatérmica, Lda.")

# (ref, título, entidade, nif, publicado há, prazo daqui a, preço, cpv, plataforma)
ANUNCIOS = [
    ("9101/2026", "Manutenção preventiva e corretiva dos equipamentos de climatização dos edifícios municipais",
     "Município de Leiria", "505181266", 1, 18, "184652.00", "50730000", "acinGov"),
    ("9102/2026", "Assistência técnica a sistemas de AVAC do bloco operatório",
     "Hospital Distrital de Santarém, E.P.E.", "506361616", 2, 12, "96000.00", "50720000", "Vortal"),
    ("9103/2026", "Substituição de chillers no pavilhão municipal",
     "Município de Viseu", "506697320", 3, 25, "238500.00", "45331000", "anoGov"),
    ("9104/2026", "Fornecimento e instalação de bombas de calor na escola básica",
     "Município de Pombal", "506334562", 0, 30, "142300.00", "45331000", "acinGov"),
    ("9105/2026", "Manutenção das unidades de tratamento de ar do centro de saúde",
     "ULS da Região de Leiria", "510445152", 4, 9, "58900.00", "50730000", "Vortal"),
    ("9106/2026", "Remodelação da rede de ventilação do arquivo distrital",
     "Direção-Geral do Património Cultural", "600084779", 5, 21, "312000.00", "45331210", "ComprasPT"),
    ("9107/2026", "Aquisição de serviços de limpeza de condutas de ar",
     "Município de Ourém", "501280740", 1, 15, "27500.00", "90915000", "acinGov"),
    ("9108/2026", "Eficiência energética: instalação de sistemas solares térmicos",
     "Município da Batalha", "506631729", 2, 40, "410000.00", "45331100", "anoGov"),
    ("9109/2026", "Manutenção de equipamentos de frio industrial",
     "Mercado Abastecedor da Região de Lisboa", "504986107", 6, 5, "73400.00", "50730000", "Vortal"),
    ("9110/2026", "Empreitada de climatização do auditório municipal",
     "Município de Alcobaça", "506811913", 7, 33, "268700.00", "45331000", "acinGov"),
]

TEXTO = ("1 - Entidade adjudicante: %s. 2 - Objeto do contrato: %s. "
         "3 - Preço base do procedimento: %s. 4 - Prazo para apresentação "
         "das propostas: até às 17:00 do dia %s. 5 - Critério de "
         "adjudicação: proposta economicamente mais vantajosa, na modalidade "
         "de avaliação do preço. (Texto de exemplo.)")
PECAS = ("Programa do Procedimento", "Caderno de Encargos",
         "Anexo I - Declaração")


def preco_pt(valor):
    """184652.00 -> «184 652,00 €», como o DR o escreve."""
    inteiro, dec = ("%.2f" % float(valor)).split(".")
    return "{:,}".format(int(inteiro)).replace(",", " ") + "," + dec + " €"


with radar.liga() as c:
    for (ref, tit, ent, nif, pub, prazo, preco, cpv, plat) in ANUNCIOS:
        c.execute("INSERT INTO anuncios (ref, titulo, entidade, data_pub, tipo,"
                  " url, cpv, prazo, preco_base, plataforma, detalhe_lido,"
                  " estado, nif, texto, distrito, docs_estado) VALUES"
                  " (?,?,?,?,?,?,?,?,?,?,1,'novo',?,?,'Leiria','ok')",
                  (ref, tit, ent, dia(-pub), "Anúncio de procedimento",
                   "https://diariodarepublica.pt/", cpv, dia(prazo),
                   preco_pt(preco), plat, nif,
                   TEXTO % (ent, tit, preco_pt(preco), dia(prazo))))
        # as peças: PDF de uma página, que a ficha lista
        pasta = radar.pasta_do_anuncio(ref)
        os.makedirs(pasta, exist_ok=True)
        for peca in PECAS:
            doc = fitz.open()
            doc.new_page().insert_text((72, 72), "%s (exemplo)" % peca)
            doc.save(os.path.join(pasta, peca + ".pdf"))
    # uma verificação de hoje, para o Hoje não dizer «ainda não houve»
    c.execute("INSERT OR REPLACE INTO slots VALUES (?,?,?,?)",
              (dia(0), "09:00", dia(0) + " 09:02", len(ANUNCIOS)))
    # A leitura das peças da primeira: o que o modelo devolve, com a página
    c.execute(
        "INSERT INTO analise (ref, objecto, equipa, documentos_proposta,"
        " preco_anormalmente_baixo, localizacao, caucao, habilitacao,"
        " pagamentos, modelo, quando, pergunta) VALUES"
        " (?,?,?,?,?,?,?,?,?,?,?,?)",
        ("9101/2026",
         "Manutenção preventiva trimestral e corretiva, com resposta em 4 horas, "
         "de 212 equipamentos de climatização em 18 edifícios (CE, p. 3)",
         "Um técnico responsável com 5 anos de experiência em AVAC e certificação "
         "de técnico de climatização (PC, p. 6)",
         "Proposta de preço; lista de preços unitários; plano de manutenção; "
         "declaração do anexo I (PC, p. 8)",
         "Abaixo de 20% do preço base (PC, p. 9)",
         "Concelho de Leiria, 18 edifícios listados no anexo II (CE, p. 14)",
         "5% do preço contratual (PC, p. 11)",
         "Alvará de construção da 4.ª subcategoria da 4.ª categoria (PC, p. 12)",
         "Mensal, a 60 dias da fatura (CE, p. 19)",
         "demo", dia(0), radar.VERSAO_DA_PERGUNTA))

# Os contratos do Portal BASE: quem ganha, a que preço, quando acaba
CONCORRENTES = [("509876543", "Frio Centro, Lda."),
                ("508123456", "Climatérmica, Lda."),
                ("507654321", "Ar Puro Engenharia, S.A."),
                ("510111222", "TermoLis, Unipessoal, Lda.")]
with radar.liga_corpus() as c:
    cid = 0
    for (ref, tit, ent, nif, _pub, _prazo, preco, cpv, _p) in ANUNCIOS:
        for ano, k in ((2023, 0), (2024, 1), (2025, 2)):
            cid += 1
            nif_g, nome_g = CONCORRENTES[(cid + k) % len(CONCORRENTES)]
            base = float(preco) * (0.85 + 0.05 * k)
            c.execute(
                "INSERT INTO contratos (id, ano, n_anuncio, tipo_procedimento,"
                " objecto, adjudicante_nif, adjudicante, adjudicante_norm,"
                " adjudicante_chave, data_publicacao, data_celebracao,"
                " preco_contratual, preco_base, prazo_execucao,"
                " local_execucao, cpv, n_adj) VALUES"
                " (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)",
                (cid, ano, "", "Concurso público", tit, nif, ent,
                 radar.simplifica(ent), radar.chave_entidade(nif, ent),
                 "%d-03-01" % ano, "%d-04-15" % ano, round(base * 0.91, 2),
                 round(base, 2), 365, "Portugal", cpv))
            c.execute("INSERT INTO contrato_adjudicatario (contrato_id, nif,"
                      " nome, nome_norm, chave) VALUES (?,?,?,?,?)",
                      (cid, nif_g, nome_g, radar.simplifica(nome_g),
                       radar.chave_entidade(nif_g, nome_g)))
            c.execute("INSERT INTO contrato_cpv VALUES (?,?)", (cid, cpv))
    radar.resolver_entidades(c)
radar.marca_corpus("ultima_importacao", dia(-2))
radar.marca("ultima_verificacao", dia(0) + " 09:02")

# O perfil da empresa e o trabalho dela
with radar.com_empresa(EMPRESA):
    radar.gravar_config({"interesse_activo": True,
                         "interesse_cpv": "45330000|50720000|50730000|90910000",
                         "nif_da_empresa": "508123456"})
    def poe(ref, estado, titulo="", entidade="", **campos):
        """Uma proposta na ranhura, pelo caminho da aplicação: a escada
        pede o que cada ranhura exige, e o `mover_proposta()` confere-o."""
        id_ = radar.criar_proposta(ref, titulo=titulo, entidade=entidade,
                                   porque_sem_ref="" if ref else "consulta prévia")
        if estado != "analisar":
            ok, recado = radar.mover_proposta(id_, estado, campos=campos)
            if not ok:
                sys.exit("a proposta %s não entrou em %s: %s"
                         % (ref or titulo, estado, recado))

    poe("9101/2026", "proposta")
    poe("9102/2026", "analisar")
    poe("9103/2026", "analisar")
    poe("9106/2026", "submetido", valor_proposta="289 500,00")
    poe("9107/2026", "submetido", valor_proposta="24 900,00")
    # as já decididas, para a taxa de vitória ter de onde contar (só
    # aparece com cinco): consultas prévias, que não vêm do DR
    for titulo, entidade, desfecho, preco, motivo in (
            ("Manutenção do AVAC da biblioteca municipal", "Município de Leiria",
             "ganho", "18 400,00", ""),
            ("Reparação de unidades de climatização", "Município de Ourém",
             "ganho", "9 750,00", ""),
            ("Manutenção de chillers do pavilhão", "Município de Pombal",
             "perdido", "42 300,00", "Preço"),
            ("Ventilação da piscina municipal", "Município da Batalha",
             "ganho", "61 200,00", ""),
            ("Climatização do centro escolar", "Município de Alcobaça",
             "perdido", "88 000,00", "Prazo")):
        extra = {"motivo": motivo} if motivo else {}
        poe(None, desfecho, titulo, entidade, valor_proposta=preco, **extra)
    radar.sincronizar_tarefas()
    radar.marca_da_empresa(radar.MARCA_DO_ARRANQUE, dia(0))

# --- quem vê: o gestor inventado, sem sessão gravada ----------------------
GESTOR = {"id": 1, "email": "ana", "nome": "Ana Costa", "papel": "admin",
          "empresa_id": EMPRESA, "dono": 0, "aspecto": "claro", "ver_como": None}
radar.contas.utilizador_da_sessao = (
    lambda c, token, agora=None: dict(GESTOR) if token == "ana" else None)
cliente = radar.app.test_client()
cliente.set_cookie("sessao", "ana")

# --- os ecrãs -------------------------------------------------------------
# A ordem é a dos passos do `site/demo.html`, que leva as legendas: o
# passo n mostra o `site/demo/<n>.html`.
ECRAS = ["/", "/concursos", "/anuncio/9101/2026", "/propostas",
         "/calendario", "/contratos", "/entidades", "/situacao"]

SCRIPTS = re.compile(r"<script\b.*?</script>", re.S | re.I)


def ecra(caminho):
    """A página inteira, morta: sem scripts, sem ligações, sem envios.
    A folha de estilo fica com a etiqueta de hoje, e o `/demo/<n>` troca-a
    pela de quando for servido."""
    r = cliente.get(caminho, follow_redirects=True)
    if r.status_code != 200:
        sys.exit("%s deu %d" % (caminho, r.status_code))
    texto = SCRIPTS.sub("", r.get_data(as_text=True))
    # o que a página pede por fetch ao abrir (os gráficos do Mercado) vem
    # já dentro, que os scripts saíram
    if "id='graf-corpo'" in texto:
        resumo = cliente.get("/contratos/resumo").get_data(as_text=True)
        texto = re.sub(r"(<div id='graf-corpo'[^>]*>).*?</div>",
                       lambda m: m.group(1) + resumo + "</div>", texto,
                       count=1, flags=re.S)
    texto = re.sub(r"<form\b", "<form inert", texto, flags=re.I)
    texto = re.sub(r"""\shref=(["'])(?!/estilo/|/tipo/|/favicon)[^"']*\1""",
                   ' tabindex="-1"', texto)
    return texto.replace("<head>", '<head><meta name="robots" content="noindex">', 1)


def gerar(pasta=os.path.join(RAIZ, "site", "demo")):
    os.makedirs(pasta, exist_ok=True)
    for n, caminho in enumerate(ECRAS, 1):
        with open(os.path.join(pasta, "%d.html" % n), "w", encoding="utf-8") as f:
            f.write(ecra(caminho))
        print("  %d  %-24s ok" % (n, caminho))


if __name__ == "__main__":
    gerar(*sys.argv[1:2])
