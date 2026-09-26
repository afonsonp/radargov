# -*- coding: utf-8 -*-
"""O registo da empresa: o que a empresa fez com cada concurso.

Entra pelo **modelo** -- a folha que o radar escreve (`escrever_modelo()`)
e o Afonso preenche, uma linha por concurso respondido, com a ref do DR
escrita por ele. Le-se com `ler_modelo()`, ensaia-se com
`ensaio_modelo()` e aplica-se com `aplicar_modelo()`, que cria ou move a
proposta na escada. O que o registo sabe e o radar nao (concorrentes,
precos por perfil, EBITDA, perfis exigidos) fica na tabela `empresa` e
mostra-se na ficha.

**O leitor do Excel antigo saiu a 15/09/2026**, por decisao dele. Era o
`.xlsm` de analise de concursos exportado do SharePoint, lido com a
logica dos consolidadores VBA de dentro dele, e ligado aos anuncios por
semelhanca de titulo e entidade (`Acervo`, `pontuar`, `ref_pelo_base`,
`decidir`, `importar`, `ligar_a_mao`): 603 linhas que nenhum comando e
nenhuma rota chamavam desde que a D4 do `docs/historico/CRM.md` decidiu
que o Excel so importa o passado pelo modelo. O `.xlsm` ja tinha sido
importado. Esta no historico do git.

E o primeiro modulo fora do radar.py (decisao de 01/09/2026): importa o
radar de dentro das funcoes, porque o radar importa este para as rotas.
"""
import json
import re
from datetime import datetime

# Os estados do Excel que se traduzem em triagem do radar. "Cancelado" e
# "TBD" ficam so no registo: nao ha estado do radar que os diga sem mentir.
ESTADOS_COM_TRIAGEM = ("nao fomos", "submetido", "perdido", "ganho")

# As fases do Zoho, no vocabulario da empresa. "2.3 - Negotiation" e
# "Ready for Proposal" nao sao um fim: a primeira ja concorremos, a
# segunda ainda nem propusemos -- e o Excel so tem "Submetido" para o
# meio do caminho, por isso e ai que ambas caem. Uma fase que nao esteja
# aqui nao traduz, e a linha fica com o que o Excel diz.
# As chaves sao o que o `_norma()` devolve -- que guarda os pontos e os
# hifens, e por isso "2.3 - negotiation" fica assim mesmo. Ha teste.
TRADUCAO_ZOHO = {"lost": "Perdido", "won": "Ganho", "cancel": "Cancelado",
                 "2.3 - negotiation": "Submetido",
                 "ready for proposal": "Submetido"}

# As razoes de nao participacao do Excel, no vocabulario dos motivos de
# abandono (MOTIVOS_ABANDONO). Chaves ja simplificadas.
MAPA_RAZAO = {"preco base demasiado baixo": "Preço base baixo",
              "preco base baixo": "Preço base baixo",
              "falta de certificacoes": "Falta de certificações",
              "falta de cv s": "Falta de CV's",
              "falta de cvs": "Falta de CV's",
              "fora do nosso ambito": "Fora do âmbito",
              "fora do ambito": "Fora do âmbito",
              "prazo de entrega curto": "Prazo curto",
              "prazo curto": "Prazo curto"}


def _num(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        import radar
        return radar.euros_do_texto(str(v)) or None
    except Exception:
        return None


def _norma(texto):
    import radar
    return radar.simplifica(texto or "")


# ------------------------------------------------------- a aplicacao

def _texto_top3(concorrentes):
    import radar
    partes = []
    for cc in sorted(concorrentes or [], key=lambda x: x.get("lugar") or 9)[:3]:
        v = cc.get("valor")
        partes.append("%d.º %s%s" % (cc.get("lugar") or 0, cc.get("nome") or "",
                                     " " + radar._texto_do_preco(v) if v else ""))
    return " · ".join(partes)[:300]


def estado_efectivo(linha):
    """O estado que vale, entre o que o Excel diz e o que o Zoho diz.

    A regra e dele, dada a 03/09/2026 depois de ver os numeros: **o
    "Nao fomos" do Excel prevalece, e e o unico**; em tudo o resto ganha
    o Zoho, que e a fonte mais actual. A excepcao existe porque o Zoho
    nao tem palavra para "nao concorremos" -- em 46 das 92 linhas que
    cruzam, o Excel diz "Nao fomos" e o Zoho diz "Lost". Sem a excepcao,
    metade do cruzamento perdia a distincao.

    **E o Zoho tambem nao decide uma linha que e UM LOTE.** As duas
    fontes contam coisas diferentes: o Excel tem uma linha por lote, o
    Zoho um negocio por procedimento. Um "Won" do Zoho quer dizer
    "ganhamos pelo menos um lote" e nao diz nada sobre este. Medido no
    1947/2026 (04/09/2026, e a razao desta regra existir): tres lotes,
    tres linhas -- #14 o L1 perdido, #97 o L2 ganho, #98 o L3 perdido --
    e no Zoho um so negocio, "Won". Sem esta guarda, o #14 passava de
    Perdido a Ganho. Uma linha de lote fica com o que o Excel diz, que e
    a fonte fina para lotes; o `lote = 0` (o conjunto) nao e um lote e
    aceita o Zoho como qualquer outra.

    Nao le a base e nao escreve nada: e derivada, de proposito. O
    `status` continua a ser o do Excel e o `zoho_fase` o do Zoho, cada
    um intacto na sua coluna -- assim uma reimportacao do Excel nao
    desfaz a regra, e mudar a regra nao obriga a reescrever dados.
    """
    st = linha.get("status")
    if _norma(st) == "nao fomos":
        return st
    if linha.get("lote"):           # >= 1: o zero e o conjunto, e nao conta
        return st
    return TRADUCAO_ZOHO.get(_norma(linha.get("zoho_fase")), st)


def estado_pretendido(linha):
    """(estado da escada, campos) que o registo da empresa pede, ou None
    quando o estado do Excel nao se traduz em nada.

    O estado vem do `estado_efectivo()`, nao do `status` cru: quem manda
    e o Zoho, tirando o "Nao fomos". Desde 15/09/2026 devolve uma das
    oito palavras da empresa (radar.ESTADOS_DA_EMPRESA) em vez de um par
    estado+fase: o vocabulario passou a ser um so, e "interessa" com uma
    fase ao lado era o mesmo estado dito duas vezes.
    """
    import radar
    st = _norma(estado_efectivo(linha))
    if st not in ESTADOS_COM_TRIAGEM:
        return None
    if st == "nao fomos":
        # a razao ja canonica (vem do modelo, ou e uma das do radar) fica
        # como esta; o mapa e para as variantes do Excel antigo
        razao = (linha.get("razao") or "").strip()
        motivo = MAPA_RAZAO.get(_norma(razao)) or razao or None
        # Uma razao fora da lista fechada entra na mesma (o `MAPA_RAZAO`
        # tem duas que esperam por uma decisao dele), mas o ensaio avisa
        # que a ficha e as contas nao a conhecem (segunda ronda,
        # 26/09/2026: entrava em silencio).
        campos = {"motivo": motivo}
        if linha.get("notas"):
            campos["notas"] = linha["notas"][:500]
        return ("nao_fomos", campos)
    campos = {}
    if linha.get("valor_proposta"):
        campos["valor_proposta"] = radar._texto_do_preco(linha["valor_proposta"])
    # As notas do modelo nao entravam em lado nenhum (segunda ronda,
    # 26/09/2026: «escrevi notas em todas as linhas e nao ficou nenhuma»).
    if linha.get("notas"):
        campos["notas"] = linha["notas"][:500]
    if st == "submetido":
        return ("submetido", campos)
    campos["lugar"] = (int(linha["lugar"]) if linha.get("lugar")
                       else (1 if st == "ganho" else None))
    campos["top3"] = _texto_top3(linha.get("concorrentes")) or None
    return (st, campos)


def aplicar(c, linha, ref, quem="registo da empresa"):
    """Escreve o que o registo da empresa sabe na PROPOSTA do anuncio ligado.
    Devolve 'aplicado', 'igual', 'sem estado', 'conflito' ou 'sem anúncio'.

    Ate 15/09/2026 escrevia no `anuncios` (estado, fase_id e as colunas do
    quadro). Agora cria ou move uma proposta -- e por decisao dele nesse
    dia (D4 do docs/historico/CRM.md) o Excel deixou de ser fonte
    permanente: serve para trazer os concursos passados e o resultado
    deles. **Nao passa por cima de uma decisao humana feita no radar**:
    uma proposta que ja esteja noutra ranhura fica como esta, e o
    conflito e registado uma vez no historico.

    O LOTE vem da linha do Excel: o Excel tem uma linha por lote e a
    escada tem uma proposta por lote, o que finalmente e a mesma coisa.
    """
    import radar
    if not c.execute("SELECT 1 FROM anuncios WHERE ref=?", (ref,)).fetchone():
        return "sem anúncio"
    pedido = estado_pretendido(linha)
    if not pedido:
        return "sem estado"
    estado, campos = pedido
    lote = linha.get("lote")
    p = c.execute("SELECT * FROM propostas WHERE ref=? AND "
                  "COALESCE(lote,-1)=COALESCE(?,-1)", (ref, lote)).fetchone()
    if p:
        igual = (p["estado"] == estado
                 and all((p[k] or None) == (v or None)
                         for k, v in campos.items() if k in p.keys()))
        if igual:
            return "igual"
        if p["estado"] != estado:
            aviso = ("o registo da empresa diz «%s»; mantém-se a decisão do Mira Gov"
                     % (linha.get("status") or ""))
            if not c.execute("SELECT 1 FROM historico WHERE ref=? AND detalhe=?",
                             (ref, aviso)).fetchone():
                _registar(c, ref, "estado", aviso, quem)
            return "conflito"
        id_ = p["id"]
    else:
        # Criada aqui e nao pelo radar.criar_proposta(): esta funcao corre
        # DENTRO da transaccao da importacao, com a ligacao `c` aberta, e
        # abrir uma segunda ligacao a meio trancava a base -- e um erro
        # que este modulo ja pagou uma vez.
        a = c.execute("SELECT titulo, entidade, preco_base, lotes FROM anuncios "
                      "WHERE ref=?", (ref,)).fetchone()
        cur = c.execute(
            "INSERT INTO propostas (ref, lote, entidade, titulo, estado, "
            "preco_base, criada_em) VALUES (?,?,?,?,?,?,?)",
            (ref, lote, a["entidade"] or "", a["titulo"] or "", estado,
             radar.preco_base_do_lote(a, lote),
             datetime.now().strftime("%Y-%m-%d %H:%M")))
        id_ = cur.lastrowid
    sets, vals = ["estado=?"], [estado]
    # O carimbo que faz o funil esvaziar, e a mesma regra do radar: so as
    # ranhuras fechadas o levam, e sair delas limpa-o.
    sets.append("fechada_em=?")
    vals.append(data_da_decisao(c, linha, ref)
                if estado in radar.ESTADOS_FECHADOS else None)
    if "motivo" not in campos:
        sets.append("motivo=NULL")
    for k, v in campos.items():
        sets.append("%s=?" % k)
        vals.append(v)
    c.execute("UPDATE propostas SET %s WHERE id=?" % ", ".join(sets), vals + [id_])
    detalhe = ("%s%s, do registo da empresa"
               % (radar.estado_da_empresa(estado),
                  " (%s)" % campos["motivo"] if campos.get("motivo") else ""))
    _registar(c, ref, "estado", detalhe, quem)
    if campos.get("valor_proposta"):
        _registar(c, ref, "preço proposto", campos["valor_proposta"], quem)
    if campos.get("lugar") or campos.get("top3"):
        _registar(c, ref, "relatório preliminar",
                  "%s%s" % ("%dº lugar" % campos["lugar"] if campos.get("lugar")
                            else "sem lugar",
                            " — " + campos["top3"] if campos.get("top3") else ""),
                  quem)
    return "aplicado"


def data_da_decisao(c, linha, ref):
    """O `fechada_em` de uma linha importada (segunda ronda, 26/09/2026):
    a «Data da decisão» do modelo; sem ela, o prazo do anuncio; e so sem
    os dois, agora. Ate aqui era sempre agora -- tres anos de historico
    caiam em «este trimestre», e a Situacao dizia que se ganhara tudo
    nele."""
    if linha.get("data_decisao"):
        return linha["data_decisao"] + " 00:00"
    a = c.execute("SELECT prazo FROM anuncios WHERE ref=?", (ref,)).fetchone()
    if a and re.fullmatch(r"\d{4}-\d{2}-\d{2}", a["prazo"] or ""):
        return a["prazo"] + " 00:00"
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _registar(c, ref, accao, detalhe, quem):
    c.execute("INSERT INTO historico (ref, quem, accao, detalhe, quando) "
              "VALUES (?,?,?,?,?)",
              (ref, quem, accao, detalhe, datetime.now().strftime("%Y-%m-%d %H:%M")))


# --------------------------------------------------------- a tabela

def iniciar_tabelas(c):
    # A tabela chamou-se `casa` ate 16/09/2026, quando o vocabulario
    # passou a «empresa». Renomear ANTES do CREATE, senao o CREATE IF
    # NOT EXISTS fazia uma `empresa` vazia ao lado da `casa` cheia e o
    # registo desaparecia sem uma palavra. Idempotente: a condicao e a
    # propria pergunta -- ha uma `casa` e ainda nao ha `empresa`.
    tabelas = {r["name"] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if "casa" in tabelas and "empresa" not in tabelas:
        c.execute("DROP INDEX IF EXISTS ix_casa_ref")
        c.execute("ALTER TABLE casa RENAME TO empresa")
    c.execute("""CREATE TABLE IF NOT EXISTS empresa (
        id INTEGER PRIMARY KEY, nome TEXT, entidade TEXT, modelo TEXT,
        prazo_meses REAL, preco_base REAL, criterio TEXT, plataforma TEXT,
        ano INTEGER, status TEXT, razao TEXT, valor_proposta REAL,
        lugar INTEGER, ebitda REAL, notas TEXT, folha TEXT,
        perfis TEXT, concorrentes TEXT, precos_perfis TEXT,
        ref TEXT, ligacao TEXT DEFAULT '', candidatos TEXT DEFAULT '[]',
        fora INTEGER DEFAULT 0, resultado TEXT DEFAULT '',
        importado_em TEXT, aplicado_em TEXT)""")
    c.execute("CREATE INDEX IF NOT EXISTS ix_empresa_ref ON empresa(ref)")
    # Porque e que uma linha nao tem anuncio: "consulta previa", "antes de
    # 2025", "nao sei". Vem das respostas do Afonso (02/09/2026) e e o
    # que distingue "por ligar" de "nao ha nada para ligar".
    colunas = [r["name"] for r in c.execute("PRAGMA table_info(empresa)")]
    if "porque_sem_ref" not in colunas:
        c.execute("ALTER TABLE empresa ADD COLUMN porque_sem_ref TEXT")
    # A que lote do anuncio esta linha corresponde (o Excel tem uma linha
    # por lote; o DR um anuncio para todos). NULL = anuncio sem lotes, ou
    # lote por identificar. ZERO = o conjunto: a linha e do procedimento
    # inteiro, nao de um lote (resposta do Afonso a 03/09/2026 sobre as
    # linhas #23 e #26, cujo preco e o total do anuncio).
    if "lote" not in colunas:
        c.execute("ALTER TABLE empresa ADD COLUMN lote INTEGER")
    # O que o Zoho diz do mesmo concurso, em coluna PROPRIA -- nao por
    # cima do `status`, e de proposito. Medido a 03/09/2026 no
    # cruzamento das 148 oportunidades da vista dos Negocios: em 46 das
    # 92 linhas que cruzam, o Excel diz "Nao fomos" e o Zoho diz "Lost".
    # O Zoho nao tem palavra para "nao concorremos", e escrever por cima
    # apagava a distincao. Fica cada um com a sua coluna, e quem manda
    # decide-se quando o vocabulario dos estados estiver decidido.
    # `zoho_como` guarda por que regra a linha casou, para a ligacao ser
    # auditavel: um cruzamento por semelhanca de nome nao e uma certeza.
    for coluna, tipo in (("zoho_fase", "TEXT"), ("zoho_montante", "REAL"),
                         ("zoho_como", "TEXT"), ("zoho_em", "TEXT")):
        if coluna not in colunas:
            c.execute("ALTER TABLE empresa ADD COLUMN %s %s" % (coluna, tipo))


RX_LOTE_NO_NOME = re.compile(r"\bL(?:ote)?\s*\.?\s*(\d{1,2})\b", re.I)


ESTADOS_DE_LOTE = ("ganho", "perdido", "submetido", "nao fomos")


def estado_do_lote(linha):
    """O estado de UMA linha da empresa, como chave: 'ganho', 'perdido',
    'submetido', 'nao fomos' ou '' quando o Excel nao diz nada de util
    ("Cancelado", "TBD"). E o estado_efectivo() normalizado -- por isso
    uma linha de lote fica com o que o Excel diz, e o conjunto (lote 0)
    aceita o Zoho."""
    st = _norma(estado_efectivo(linha))
    return st if st in ESTADOS_DE_LOTE else ""


def linhas_de_lotes(c, refs):
    """{ref: [linhas da empresa com `lote` preenchido]} para varios anuncios
    de uma vez -- o quadro pede pelas suas cartas todas, nao uma a uma."""
    refs = [r for r in refs if r]
    if not refs:
        return {}
    saida = {}
    for i in range(0, len(refs), 400):
        pedaco = refs[i:i + 400]
        for r in c.execute(
                "SELECT id, ref, lote, status, zoho_fase, valor_proposta, lugar, "
                "nome, razao FROM empresa WHERE lote IS NOT NULL AND ref IN (%s) "
                "ORDER BY lote, id" % ",".join("?" * len(pedaco)), pedaco):
            saida.setdefault(r["ref"], []).append(dict(r))
    return saida


def lotes_do_anuncio(c, ref):
    r = c.execute("SELECT lotes FROM anuncios WHERE ref=?", (ref,)).fetchone()
    try:
        return json.loads(r["lotes"]) if r and r["lotes"] else []
    except ValueError:
        return []


CAMPOS_EXCEL = ("nome", "entidade", "modelo", "prazo_meses", "preco_base",
                "criterio", "plataforma", "ano", "status", "razao",
                "valor_proposta", "lugar", "ebitda", "notas", "folha")


# ------------------------------------------------------ para o painel


def desaplicar_da_copia(copia):
    """Desfaz o que uma importacao escreveu, repondo as PROPOSTAS tal
    como estao numa COPIA da base feita antes dela, e apaga do historico
    o que a importacao la escreveu. O registo (tabela empresa) fica; as
    ligacoes ficam. Devolve (propostas repostas, linhas de historico
    apagadas).

    Existe porque a 02/09/2026 se importou e aplicou, e o Afonso decidiu
    a seguir que nada se aplica antes de o registo estar validado.

    Desde 15/09/2026 repoe propostas e nao colunas do anuncio -- e por
    isso repor tambem sabe APAGAR: uma proposta que a importacao criou
    do nada nao estava na copia, e deixa-la la era a importacao ficar
    meia desfeita. Uma copia de ANTES da escada nao tem a tabela, e ai
    nao se desfaz nada: di-lo devolvendo zero, em vez de apagar tudo o
    que encontrar."""
    import radar
    import sqlite3
    antes = sqlite3.connect("file:%s?mode=ro" % copia.replace("\\", "/"), uri=True)
    antes.row_factory = sqlite3.Row
    repostos = apagadas = 0
    with radar.liga() as c:
        refs = [r["ref"] for r in c.execute(
            "SELECT DISTINCT ref FROM empresa WHERE ref IS NOT NULL "
            "AND resultado IN ('aplicado', 'conflito', 'igual')")]
        try:
            antes.execute("SELECT 1 FROM propostas LIMIT 1")
        except sqlite3.OperationalError:
            refs = []
        for ref in refs:
            velhas = antes.execute(
                "SELECT %s FROM propostas WHERE ref=?"
                % ", ".join(radar.COLUNAS_DA_PROPOSTA), (ref,)).fetchall()
            c.execute("DELETE FROM propostas WHERE ref=?", (ref,))
            for v in velhas:
                c.execute("INSERT INTO propostas (%s) VALUES (%s)"
                          % (", ".join(radar.COLUNAS_DA_PROPOSTA),
                             ", ".join("?" * len(radar.COLUNAS_DA_PROPOSTA))),
                          [v[k] for k in radar.COLUNAS_DA_PROPOSTA])
            # O historico repoe-se pela COPIA e nao por `quem`: ate
            # 15/09/2026 apagava-se `WHERE quem='Excel'`, e isso deixou de
            # apanhar nada no dia em que o leitor do Excel antigo saiu --
            # a importacao pelo modelo escreve o nome de quem a fez. A
            # copia sabe exactamente que linhas la estavam.
            ja_estavam = {r["id"] for r in antes.execute(
                "SELECT id FROM historico WHERE ref=?", (ref,))}
            novas = [r["id"] for r in c.execute(
                "SELECT id FROM historico WHERE ref=?", (ref,))
                if r["id"] not in ja_estavam]
            for ide in novas:
                c.execute("DELETE FROM historico WHERE id=?", (ide,))
            apagadas += len(novas)
            repostos += 1
        c.execute("UPDATE empresa SET resultado='guardado', aplicado_em=NULL "
                  "WHERE ref IS NOT NULL AND resultado != 'fora'")
    antes.close()
    return repostos, apagadas


# ------------------------------------------ o modelo da empresa (8/09/2026)
#
# Decisao do Afonso a 8/09/2026: em vez de o radar tentar perceber o
# Excel antigo (Analise_Concursos_Publicos.xlsm, feito para outra coisa,
# com folhas C_ e consolidadores VBA), **o radar dita o modelo**: um
# .xlsx gerado aqui, com as colunas que a aplicacao precisa e listas de
# escolha onde ha vocabulario, que o utilizador preenche e carrega em
# Configuracoes > Importar dados, com ensaio antes de gravar. **O leitor
# do Excel antigo saiu a 15/09/2026**, por decisao dele: ficou uma
# semana sem comando que o chamasse e o .xsm ja tinha sido importado.
# Esta no historico do git.
#
# A chave e a REFERENCIA DO ANUNCIO no DR ("1947/2026"), que a ficha
# mostra: liga sem adivinhar, e uma linha sem anuncio e um erro que se
# ve no ensaio, nao um palpite.

COLUNAS_MODELO = (
    ("Referência do anúncio", "ref"),
    ("Lote", "lote"),
    ("Estado", "status"),
    ("Razão de não participação", "razao"),
    ("Valor da proposta (€)", "valor_proposta"),
    ("Lugar", "lugar"),
    ("Concorrentes (separados por ;)", "concorrentes"),
    ("Responsável", "responsavel"),
    ("Notas", "notas"),
    # A data em que se decidiu (segunda ronda, 26/09/2026): sem ela, tudo
    # o que se importava contava como decidido no dia da importacao.
    ("Data da decisão", "data_decisao"),
)
ESTADOS_MODELO = ("Não fomos", "Submetido", "Ganho", "Perdido")
FOLHA_MODELO = "Registo"
PASTA_IMPORTACOES = "importacoes"
RX_REF = re.compile(r"^\s*(\d{1,6})\s*[/\-\s]\s*(\d{4})\s*$")
# A referencia escrita a maneira do Excel: «Anúncio n.º 8023/2026»,
# «8023/26». Procura-se o numero/ano dentro do texto, e diz-se o que se
# leu (segunda ronda, 26/09/2026: davam «ilegível» e mostravam «—»).
RX_REF_NO_TEXTO = re.compile(r"(?<!\d)(\d{1,6})\s*/\s*(\d{4}|\d{2})(?!\d)")


def escrever_modelo(caminho):
    """Gera o .xlsx vazio: a folha Registo com os cabecalhos e as listas
    de escolha (Estado, Razao) ate a linha 500, e uma folha de
    instrucoes com um exemplo. Devolve o caminho."""
    import radar
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
    wb = Workbook()
    ws = wb.active
    ws.title = FOLHA_MODELO
    larguras = (22, 8, 14, 28, 20, 8, 44, 18, 40, 14)
    for i, ((titulo, _), largura) in enumerate(zip(COLUNAS_MODELO, larguras), 1):
        c = ws.cell(row=1, column=i, value=titulo)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="17557F")
        c.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = largura
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"
    dv_estado = DataValidation(type="list", formula1='"%s"' % ",".join(ESTADOS_MODELO),
                               allow_blank=True, showErrorMessage=True,
                               errorTitle="Estado", error="Escolha um da lista.")
    dv_razao = DataValidation(type="list",
                              formula1='"%s"' % ",".join(radar.MOTIVOS_ABANDONO),
                              allow_blank=True, showErrorMessage=False)
    ws.add_data_validation(dv_estado)
    ws.add_data_validation(dv_razao)
    dv_estado.add("C2:C500")
    dv_razao.add("D2:D500")
    inst = wb.create_sheet("Instruções")
    inst.column_dimensions["A"].width = 110
    linhas = [
        "Como preencher a folha «Registo» — uma linha por concurso, ou por lote quando o concurso tem lotes.",
        "",
        "Referência do anúncio: a referência do DR tal como a ficha do Mira Gov a mostra, ex. 1947/2026. É obrigatória e é o que liga a linha ao anúncio.",
        "Lote: o número do lote (1, 2, 3…) quando o concurso tem lotes e a linha é de um lote. Vazio quando não há lotes ou quando se foi ao conjunto.",
        "Estado: um da lista — Não fomos, Submetido, Ganho, Perdido.",
        "Razão de não participação: só quando o estado é «Não fomos» — uma da lista: %s. Outra razão entra, mas a ficha e as contas só conhecem as da lista." % ", ".join(radar.MOTIVOS_ABANDONO),
        "Valor da proposta (€): o que propusemos, em número (ex. 54432 ou 54432,50). Vazio se não fomos.",
        "Lugar: a posição no relatório preliminar (1, 2, 3…). Vazio se ainda não há relatório.",
        "Concorrentes: os nomes separados por ponto e vírgula, por ordem de classificação, ex. Empresa A; Empresa B; Empresa C.",
        "Responsável: quem da empresa acompanha este concurso (nome).",
        "Notas: texto livre.",
        "Data da decisão: quando se decidiu (dd/mm/aaaa) — a entrega da proposta, a adjudicação ou o «não vamos». Conta para o período do Ponto de situação; vazia, conta o prazo do anúncio.",
        "",
        "Exemplo:  1947/2026 | 2 | Ganho |  | 169344 | 1 | Nós; Empresa B; Empresa C | Afonso | contrato de 24 meses | 15/03/2026",
        "",
        "Depois de preencher, carrega o ficheiro em Configurações › Importar dados. O Mira Gov mostra um ensaio (o que liga a que anúncio, o que é novo e o que muda, o que não liga e porquê) e só grava quando confirmares. Uma importação desfaz-se lá, enquanto ninguém mexer nas propostas que ela tocou.",
        "No mesmo ficheiro, uma linha repetida (mesma referência e mesmo lote) é um erro: fica a primeira. Voltar a importar uma referência que já entrou substitui o que ela tinha no registo. Linhas com erro não entram; as outras entram.",
    ]
    for i, t in enumerate(linhas, 1):
        inst.cell(row=i, column=1, value=t).alignment = Alignment(wrap_text=True, vertical="top")
    inst.cell(row=1, column=1).font = Font(bold=True)
    wb.save(caminho)
    return caminho


def ref_limpa(texto):
    """"1947/2026", "1947-2026", " 1947 / 2026 " -> "1947/2026"; senao ''."""
    m = RX_REF.match(str(texto or ""))
    return "%s/%s" % (int(m.group(1)), m.group(2)) if m else ""


def _celula(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _ref_da_celula(texto):
    """(referência, aviso do que se leu) de uma célula. A escrita limpa
    não leva aviso; a que se tirou de dentro do texto, ou com o ano em
    dois dígitos, diz como se leu, para se poder conferir."""
    ref = ref_limpa(texto)
    if ref or not texto:
        return ref, ""
    m = RX_REF_NO_TEXTO.search(texto)
    if not m:
        return "", ""
    ano = m.group(2) if len(m.group(2)) == 4 else "20" + m.group(2)
    ref = "%d/%s" % (int(m.group(1)), ano)
    return ref, "li «%s» como %s" % (texto[:60], ref)


def _data_da_celula(v):
    """A data de uma célula em ISO, ou "": o Excel dá-a como data, e à
    mão escreve-se dd/mm/aaaa."""
    import radar
    if v is None or v == "":
        return ""
    if hasattr(v, "date") and callable(v.date):
        return v.date().isoformat()
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return radar.data_de_filtro(_celula(v))


def colunas_ignoradas(caminho):
    """[(letra, título)] das colunas com cabeçalho que não são do modelo:
    liam-se em silêncio como se não existissem (segunda ronda,
    26/09/2026)."""
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter
    wb = load_workbook(caminho, read_only=True, data_only=True)
    ws = wb[FOLHA_MODELO] if FOLHA_MODELO in wb.sheetnames else wb.active
    cabeca = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ()) or ()
    wb.close()
    return [(get_column_letter(i), _celula(v))
            for i, v in enumerate(cabeca, 1)
            if i > len(COLUNAS_MODELO) and _celula(v)]


def ler_modelo(caminho):
    """Le o .xlsx preenchido: [{linha, ref, lote, status, razao,
    valor_proposta, lugar, concorrentes, responsavel, notas, erros}].

    Nao decide nada sobre a base -- isso e o ensaio_modelo(). Aqui so
    se normaliza e se apontam os erros de forma: referencia ilegivel,
    estado fora da lista, lote ou lugar que nao sao numeros."""
    import radar
    from openpyxl import load_workbook
    wb = load_workbook(caminho, read_only=True, data_only=True)
    ws = wb[FOLHA_MODELO] if FOLHA_MODELO in wb.sheetnames else wb.active
    chaves = [c for _, c in COLUNAS_MODELO]
    saida = []
    for n, valores in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
        valores = list(valores or ())[:len(chaves)]
        valores += [None] * (len(chaves) - len(valores))
        bruto = dict(zip(chaves, valores))
        if not any(_celula(v) for v in valores):
            continue
        erros = []
        avisos = []
        linha = {"linha": n, "erros": erros, "avisos": avisos}
        linha["ref_escrita"] = _celula(bruto["ref"])
        linha["ref"], lida = _ref_da_celula(linha["ref_escrita"])
        if lida:
            avisos.append(lida)
        if not linha["ref_escrita"]:
            erros.append("sem referência: o modelo só importa concursos do DR; "
                         "as propostas sem anúncio fazem-se em Propostas › "
                         "Nova proposta")
        elif not linha["ref"]:
            erros.append("referência «%s» ilegível (ex.: 1947/2026)"
                         % linha["ref_escrita"][:60])
        lote_txt = _celula(bruto["lote"])
        try:
            linha["lote"] = int(float(lote_txt.replace(",", "."))) if lote_txt else None
            if linha["lote"] is not None and linha["lote"] < 1:
                erros.append("o lote tem de ser 1 ou mais")
        except ValueError:
            linha["lote"] = None
            erros.append("lote «%s» não é um número" % lote_txt)
        estado = _celula(bruto["status"])
        por_norma = {_norma(e): e for e in ESTADOS_MODELO}
        linha["status"] = por_norma.get(_norma(estado), "")
        if not linha["status"]:
            erros.append("estado «%s» não está na lista (%s)"
                         % (estado, ", ".join(ESTADOS_MODELO)))
        razao = _celula(bruto["razao"])
        linha["razao"] = MAPA_RAZAO.get(_norma(razao), razao) if razao else ""
        if razao and linha["status"] and _norma(linha["status"]) != "nao fomos":
            avisos.append("a razão só conta em «Não fomos»; nesta linha fica "
                          "de fora")
        elif linha["razao"] and linha["razao"] not in radar.MOTIVOS_ABANDONO:
            avisos.append("a razão «%s» não é uma da lista: entra, mas a ficha "
                          "e o «Porque não se vai» só conhecem as da lista (%s)"
                          % (linha["razao"][:60], ", ".join(radar.MOTIVOS_ABANDONO)))
        linha["valor_proposta"] = _num(bruto["valor_proposta"])
        valor_txt = _celula(bruto["valor_proposta"])
        if valor_txt and linha["valor_proposta"] is None \
                and radar.euros_do_texto(valor_txt) is None:
            # «cento e vinte mil» passava a «—» e a linha dizia «liga»
            erros.append("valor «%s» não é um número (ex. 54432,50)"
                         % valor_txt[:40])
        linha["data_decisao"] = _data_da_celula(bruto["data_decisao"])
        if bruto["data_decisao"] not in (None, "") and not linha["data_decisao"]:
            erros.append("data da decisão «%s» não é uma data (dd/mm/aaaa)"
                         % _celula(bruto["data_decisao"])[:20])
        lugar_txt = _celula(bruto["lugar"])
        try:
            linha["lugar"] = int(float(lugar_txt.replace(",", "."))) if lugar_txt else None
        except ValueError:
            linha["lugar"] = None
            erros.append("lugar «%s» não é um número" % lugar_txt)
        nomes = [p.strip() for p in re.split(r"[;\n]", _celula(bruto["concorrentes"])) if p.strip()]
        linha["concorrentes"] = [{"lugar": i, "nome": nome} for i, nome in enumerate(nomes, 1)]
        linha["responsavel"] = _celula(bruto["responsavel"])[:60]
        linha["notas"] = _celula(bruto["notas"])[:2000]
        linha["nome"] = ""
        saida.append(linha)
    wb.close()
    return saida


def ensaio_modelo(c, linhas):
    """Cruza as linhas lidas com a base, sem gravar: poe em cada uma o
    titulo do anuncio, a lista de problemas e `ok`. Devolve (linhas,
    contagens)."""
    vistas = {}
    for l in linhas:
        problemas = list(l["erros"])
        l["titulo"] = ""
        a = None
        if l["ref"]:
            a = c.execute("SELECT ref, titulo, estado, lotes FROM anuncios WHERE ref=?",
                          (l["ref"],)).fetchone()
            if not a:
                problemas.append("não há anúncio %s na base" % l["ref"])
            else:
                l["titulo"] = a["titulo"] or ""
                if a["estado"] == "alteracao":
                    problemas.append("%s é uma republicação; usa a referência do anúncio original" % l["ref"])
                lotes = lotes_do_anuncio(c, l["ref"])
                if l["lote"] is not None and not lotes:
                    problemas.append("o anúncio não declara lotes; deixa o lote vazio")
                elif l["lote"] is not None and l["lote"] not in [x["n"] for x in lotes]:
                    problemas.append("o anúncio tem %d lotes e não tem o lote %d"
                                     % (len(lotes), l["lote"]))
                elif l["lote"] is None and lotes:
                    l.setdefault("avisos", []).append(
                        "o anúncio tem %d lotes; sem lote, a linha conta como o conjunto" % len(lotes))
        chave = (l["ref"], l["lote"])
        if l["ref"] and chave in vistas:
            problemas.append("repete a linha %d (mesma referência e lote)" % vistas[chave])
        elif l["ref"]:
            vistas[chave] = l["linha"]
        if _norma(l.get("status")) == "nao fomos" and (l.get("valor_proposta") or l.get("lugar")):
            l.setdefault("avisos", []).append("«Não fomos» com proposta ou lugar: ficam guardados, mas não contam")
        l["problemas"] = problemas
        l["ok"] = not problemas
    _efeitos(c, linhas)
    contagens = {"total": len(linhas), "ok": sum(1 for l in linhas if l["ok"]),
                 "com_erro": sum(1 for l in linhas if not l["ok"]),
                 "anuncios": len({l["ref"] for l in linhas if l["ok"]}),
                 "alteram": sum(1 for l in linhas if l.get("efeito", "")
                                .startswith("altera")),
                 "mantem": sum(1 for l in linhas if l.get("efeito", "")
                               .startswith("mantém"))}
    return linhas, contagens


_ROTULOS_DO_EFEITO = {"valor_proposta": "preço", "lugar": "lugar",
                      "top3": "os três primeiros", "motivo": "motivo",
                      "notas": "notas"}


def _efeitos(c, linhas):
    """O que a importação vai fazer a cada linha boa, sem gravar (E17 da
    segunda ronda, 26/09/2026): «nova», «altera: preço 362 000,00 € →
    1 000,00 €», «igual», ou «mantém-se» quando a proposta já está
    noutra ranhura -- o `aplicar()` não passa por cima de uma decisão
    feita no Mira Gov. Só a MELHOR linha de cada anúncio mexe na
    proposta (`aplicar_modelo()`); as outras ficam só no registo."""
    import radar
    por_ref = {}
    for l in linhas:
        if l.get("ok"):
            por_ref.setdefault(l["ref"], []).append(l)
    for ref, grupo in por_ref.items():
        melhor = sorted(grupo, key=lambda x: _PRIORIDADE.get(_norma(x["status"]), 9))[0]
        for l in grupo:
            if l is not melhor:
                l["efeito"] = ("fica só no registo: o anúncio segue a linha %d"
                               % melhor["linha"])
        pedido = estado_pretendido(melhor)
        if not pedido:
            continue
        estado, campos = pedido
        p = c.execute("SELECT * FROM propostas WHERE ref=? AND "
                      "COALESCE(lote,-1)=COALESCE(?,-1)",
                      (ref, melhor["lote"])).fetchone()
        if not p:
            melhor["efeito"] = "nova"
        elif p["estado"] != estado:
            melhor["efeito"] = ("mantém-se em «%s»: a importação não substitui "
                                "uma decisão feita no Mira Gov"
                                % radar.estado_da_empresa(p["estado"]))
        else:
            mudancas = []
            for k, v in campos.items():
                if (p[k] or None) == (v or None):
                    continue
                if k == "valor_proposta":
                    mudancas.append("preço %s → %s" % (radar.preco_pt(p[k]),
                                                        radar.preco_pt(v)))
                else:
                    mudancas.append("%s «%s» → «%s»"
                                    % (_ROTULOS_DO_EFEITO.get(k, k),
                                       radar.corta(str(p[k] or "—"), 30),
                                       radar.corta(str(v or "—"), 30)))
            melhor["efeito"] = ("altera: " + "; ".join(mudancas)
                                if mudancas else "igual")


# A prioridade quando um anuncio tem varias linhas (lotes) com estados
# diferentes: o anuncio fica no melhor deles -- ganhamos um lote, o
# cartao esta no Ganho, e a separacao no fim mostra os perdidos.
_PRIORIDADE = {"ganho": 0, "submetido": 1, "perdido": 2, "nao fomos": 3}


def aplicar_modelo(c, linhas, quem="modelo"):
    """Grava as linhas `ok` na tabela empresa (folha='modelo') e escreve a
    triagem nos anuncios. Devolve {"gravadas", "aplicadas", "anuncios",
    "resultados": {ref: resultado de aplicar()}}."""
    import radar
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    por_ref = {}
    gravadas = 0
    for l in linhas:
        if not l.get("ok"):
            continue
        c.execute("DELETE FROM empresa WHERE ref=? AND folha='modelo' AND "
                  "COALESCE(lote,0)=COALESCE(?,0)", (l["ref"], l["lote"] if l["lote"] is not None else 0))
        c.execute(
            "INSERT INTO empresa (nome, status, razao, valor_proposta, lugar, notas, folha, "
            "concorrentes, ref, ligacao, candidatos, fora, resultado, importado_em, "
            "aplicado_em, lote) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (l.get("titulo") or "", l["status"], l["razao"] or None, l["valor_proposta"],
             l["lugar"], l["notas"] or None, "modelo",
             json.dumps(l["concorrentes"], ensure_ascii=False), l["ref"], "ref", "[]",
             0, "aplicado", agora, agora, l["lote"] if l["lote"] is not None else 0))
        gravadas += 1
        por_ref.setdefault(l["ref"], []).append(l)
    resultados = {}
    for ref, grupo in por_ref.items():
        melhor = sorted(grupo, key=lambda l: _PRIORIDADE.get(_norma(l["status"]), 9))[0]
        resultados[ref] = aplicar(c, melhor, ref, quem=quem)
        responsavel = next((l["responsavel"] for l in grupo if l.get("responsavel")), "")
        if responsavel:
            c.execute("INSERT OR IGNORE INTO pessoas (nome) VALUES (?)", (responsavel,))
            # Na PROPOSTA, e nao no anuncio (15/09/2026): quem trata de um
            # concurso e quem trata da proposta, e um anuncio por ver nao
            # tem dono porque ainda nao ha nada para tratar.
            c.execute("UPDATE propostas SET responsavel=? WHERE ref=?",
                      (responsavel, ref))
    return {"gravadas": gravadas, "anuncios": len(por_ref),
            "aplicadas": sum(1 for r in resultados.values() if r == "aplicado"),
            "resultados": resultados}
