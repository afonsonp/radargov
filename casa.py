# -*- coding: utf-8 -*-
"""O registo da casa: o que a empresa fez com cada concurso.

Primeira fonte: o Excel de analise de concursos do Afonso
(Analise_Concursos_Publicos.xlsm), exportado de uma lista do SharePoint
e completado a mao numa folha por concurso. Le-se com a MESMA logica dos
consolidadores VBA que ele tem la dentro -- as folhas C_ sao os registos,
as tabelas planas sao derivadas e podem estar desactualizadas.

Cada linha liga-se ao PROCEDIMENTO do radar (o anuncio original, nunca
uma alteracao) e, quando o estado e inequivoco, escreve-se a triagem e o
quadro nesse anuncio. O que o Excel sabe e o radar nao (concorrentes,
precos por perfil, EBITDA, perfis exigidos) fica na tabela `casa` e
mostra-se na ficha.

E o primeiro modulo fora do radar.py (decisao de 01/09/2026): importa o
radar de dentro das funcoes, porque o radar importa este para as rotas.
"""
import json
import re
import time
from datetime import datetime

# Entidades que nao entram (decisao do Afonso a 01/09/2026): as espanholas.
# O universo do radar e a parte L do DR, por isso nada disto se ligaria
# de qualquer maneira; a regra existe para nao ficarem "por ligar" para
# sempre a pedir atencao.
FORA_DO_PAIS = ("asturias", "principado de", "xunta de", "junta de andalucia",
                "generalitat", "ayuntamiento", "gobierno de", "ministerio de",
                "comunidad de", "diputacion")

# Os estados do Excel que se traduzem em triagem do radar. "Cancelado" e
# "TBD" ficam so no registo: nao ha estado do radar que os diga sem mentir.
ESTADOS_COM_TRIAGEM = ("nao fomos", "submetido", "perdido", "ganho")

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

STOP = set("de da do das dos e a o as os em para com no na nos nas por um uma "
           "ao aos servicos servico aquisicao contratacao prestacao fornecimento "
           "projeto projecto desenvolvimento".split())

# Nomes curtos que o Excel usa e que o corpus nao resolve sozinho.
ALIAS = {"ipl": "instituto politecnico de leiria",
         "tml": "transportes metropolitanos de lisboa",
         "osae": "ordem dos solicitadores",
         "act": "autoridade para as condicoes do trabalho",
         "icnf": "conservacao da natureza",
         "igefe": "gestao financeira e equipamentos",
         "igfej": "gestao financeira e equipamentos da justica",
         "adene": "agencia para a energia",
         "ifap": "financiamento da agricultura",
         "impic": "mercados publicos do imobiliario",
         "aicep": "aicep",
         "ipdj": "portugues do desporto e juventude",
         "dgpj": "direcao geral da politica de justica",
         "ipca": "instituto politecnico do cavado",
         "ama": "modernizacao administrativa",
         "ansr": "seguranca rodoviaria",
         "inem": "emergencia medica",
         "lneg": "energia e geologia",
         "dgt": "direcao geral do territorio",
         "u porto": "universidade do porto",
         "emrp": "emrp"}

LIMIAR = 0.6           # abaixo disto nao ha ligacao
FOLGA = 0.15           # o segundo tem de ficar a esta distancia do primeiro
MAX_CANDIDATOS = 5


# ------------------------------------------------------------ o Excel

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


def _txt(v):
    return " ".join(str(v).split()) if v is not None else ""


def _celulas(ws):
    """A folha como lista de linhas (listas), sem depender de dimensions."""
    return [list(r) for r in ws.iter_rows(values_only=True)]


def _procura(linhas, texto, coluna=0, a_partir=0):
    """Indice da primeira linha cuja coluna comeca por `texto` (maiusc.)."""
    alvo = texto.upper()
    for i in range(a_partir, len(linhas)):
        cel = linhas[i][coluna] if coluna < len(linhas[i]) else None
        if cel is not None and _txt(cel).upper().startswith(alvo):
            return i
    return -1


def _valor_em(linhas, i, coluna=1):
    if 0 <= i < len(linhas) and coluna < len(linhas[i]):
        return linhas[i][coluna]
    return None


def ler_folha_concurso(ws):
    """Uma folha C_: as tabelas A, A.1, B, C e C.1, pelas mesmas ancoras
    que as macros usam ("TABELA B", "TABELA C", cabecalhos PERFIL e
    CONCORRENTE)."""
    L = _celulas(ws)
    if not L:
        return None
    fora = {"entidade": _txt(_valor_em(L, 0, 0)),
            "nome": _txt(_valor_em(L, 0, 1)),
            "id": None, "perfis": [], "concorrentes": [], "precos_perfis": []}
    # o id estavel fica em Z1 (coluna 26, indice 25) com a marca em Z2
    z1 = _valor_em(L, 0, 25)
    if isinstance(z1, (int, float)):
        fora["id"] = int(z1)
    else:
        try:
            fora["id"] = int(_txt(_valor_em(L, 0, 2)) or 0) or None
        except ValueError:
            pass
    # Tabela A: rotulo na coluna A, valor na B
    ia = _procura(L, "TABELA A")
    rotulos = {"modelo": "modelo", "prazo de execu": "prazo_meses",
               "preço base": "preco_base", "preco base": "preco_base",
               "critério": "criterio", "criterio": "criterio",
               "plataforma": "plataforma", "ano": "ano", "status": "status"}
    if ia >= 0:
        for i in range(ia + 1, min(ia + 12, len(L))):
            rot = _txt(_valor_em(L, i, 0)).lower()
            for chave, campo in rotulos.items():
                if rot.startswith(chave):
                    fora[campo] = _valor_em(L, i, 1)
    # A.1: perfis exigidos, ate a linha vazia ou a TABELA B
    ip = _procura(L, "PERFIL", 0, ia if ia >= 0 else 0)
    if ip >= 0:
        for i in range(ip + 1, len(L)):
            p = _txt(_valor_em(L, i, 0))
            if not p or p.upper().startswith("TABELA"):
                break
            fora["perfis"].append({
                "perfil": p, "tecnologias": _txt(_valor_em(L, i, 1)),
                "anos": _num(_valor_em(L, i, 2)), "n": _num(_valor_em(L, i, 3)),
                "horas": _num(_valor_em(L, i, 4)),
                "certificacoes": _txt(_valor_em(L, i, 5))})
    # Tabela B: nove valores na coluna B, pela ordem do modelo
    ib = _procura(L, "TABELA B")
    if ib >= 0:
        fora["valor_proposta"] = _num(_valor_em(L, ib + 1))
        fora["lugar"] = _num(_valor_em(L, ib + 2))
        fora["ebitda"] = _num(_valor_em(L, ib + 3))
        fora["gap_base"] = _num(_valor_em(L, ib + 4))
        fora["gap_base_pct"] = _num(_valor_em(L, ib + 5))
        fora["gap_primeiro"] = _num(_valor_em(L, ib + 6))
        fora["gap_primeiro_pct"] = _num(_valor_em(L, ib + 7))
        fora["razao"] = _txt(_valor_em(L, ib + 8))
        fora["notas"] = _txt(_valor_em(L, ib + 9))
    # Tabela C: cinco lugares, tres linhas cada (titulo, nome, valor)
    ic = _procura(L, "TABELA C")
    if ic >= 0:
        for lugar in range(1, 6):
            base = ic + 1 + (lugar - 1) * 3
            nome = _txt(_valor_em(L, base + 1))
            if nome:
                fora["concorrentes"].append(
                    {"lugar": lugar, "nome": nome,
                     "valor": _num(_valor_em(L, base + 2))})
    # C.1: preco por perfil por concorrente
    icc = _procura(L, "CONCORRENTE", 0, ic if ic >= 0 else 0)
    if icc >= 0:
        for i in range(icc + 1, len(L)):
            conc = _txt(_valor_em(L, i, 0))
            if not conc or conc.upper().startswith("LEGENDA"):
                break
            fora["precos_perfis"].append({
                "concorrente": conc, "perfil": _txt(_valor_em(L, i, 1)),
                "tecnologias": _txt(_valor_em(L, i, 2)),
                "anos": _num(_valor_em(L, i, 3)), "valor": _num(_valor_em(L, i, 4)),
                "horas": _num(_valor_em(L, i, 5)), "hora": _num(_valor_em(L, i, 6))})
    return fora


def ler_excel(caminho):
    """As linhas do INDICE, completadas pela folha de cada concurso quando
    existe. Devolve uma lista de dicionarios, um por concurso, com `id`
    (a coluna K do INDICE, estavel) e `folha` (o nome da folha ou '')."""
    import openpyxl
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    if "ÍNDICE" not in wb.sheetnames:
        raise ValueError("o ficheiro não tem a folha ÍNDICE")
    L = _celulas(wb["ÍNDICE"])
    cab = [_txt(c).upper() for c in (L[0] if L else [])]
    def col(nome, omissao):
        for i, c in enumerate(cab):
            if c.startswith(nome):
                return i
        return omissao
    ci = {"nome": col("NOME", 0), "entidade": col("ENTIDADE", 1),
          "modelo": col("MODELO", 2), "prazo": col("PRAZO", 3),
          "preco": col("PRE", 4), "criterio": col("CRIT", 5),
          "plataforma": col("PLATAFORMA", 6), "ano": col("ANO", 7),
          "status": col("STATUS", 8), "id": col("ID", 10)}
    folhas = {}
    for nome in wb.sheetnames:
        if nome.startswith("C_"):
            f = ler_folha_concurso(wb[nome])
            if f and f["id"]:
                f["folha"] = nome
                folhas[f["id"]] = f
    linhas = []
    for r in L[1:]:
        if not r or not _txt(r[ci["nome"]] if ci["nome"] < len(r) else None):
            continue
        def g(k):
            i = ci[k]
            return r[i] if i < len(r) else None
        try:
            ide = int(g("id")) if g("id") not in (None, "") else None
        except (TypeError, ValueError):
            ide = None
        linha = {"id": ide, "nome": _txt(g("nome")), "entidade": _txt(g("entidade")),
                 "modelo": _txt(g("modelo")), "prazo_meses": _num(g("prazo")),
                 "preco_base": _num(g("preco")), "criterio": _txt(g("criterio")),
                 "plataforma": _txt(g("plataforma")),
                 "ano": int(_num(g("ano")) or 0) or None,
                 "status": _txt(g("status")), "folha": "",
                 "razao": "", "valor_proposta": None, "lugar": None,
                 "ebitda": None, "notas": "", "perfis": [], "concorrentes": [],
                 "precos_perfis": []}
        f = folhas.get(ide) if ide else None
        if f:
            for k in ("razao", "valor_proposta", "lugar", "ebitda", "notas",
                      "perfis", "concorrentes", "precos_perfis", "folha"):
                if f.get(k) not in (None, "", []):
                    linha[k] = f[k]
            # a folha e a versao mais completa da Tabela A: se o INDICE
            # estiver vazio num campo e a folha nao, vale a folha
            for k in ("modelo", "criterio", "plataforma", "status"):
                if not linha[k] and _txt(f.get(k)):
                    linha[k] = _txt(f.get(k))
            if linha["preco_base"] is None and _num(f.get("preco_base")):
                linha["preco_base"] = _num(f.get("preco_base"))
        linhas.append(linha)
    wb.close()
    return linhas


def fora_do_pais(linha):
    import radar
    texto = radar.simplifica(" ".join((linha.get("entidade") or "",
                                       linha.get("notas") or "")))
    return any(p in texto for p in FORA_DO_PAIS)


# --------------------------------------------------------- a ligacao

def _toks(texto):
    import radar
    return {w for w in radar.simplifica(texto or "").split()
            if w not in STOP and len(w) > 2}


def _norma(texto):
    import radar
    return radar.simplifica(texto or "")


class Acervo(object):
    """Os anuncios candidatos, lidos UMA vez por importacao: so os
    originais (nunca alteracoes), so o DR, dentro dos anos pedidos."""

    def __init__(self, c, anos):
        anos = sorted(a for a in anos if a)
        if not anos:
            anos = [datetime.now().year]
        de, ate = "%d-01-01" % (min(anos) - 1), "%d-12-31" % max(anos)
        self.linhas = []
        for r in c.execute(
                "SELECT ref, titulo_norm, entidade_norm, nif, preco_base, "
                "data_pub, estado FROM anuncios WHERE data_pub BETWEEN ? AND ? "
                "AND estado != 'alteracao' AND COALESCE(fonte,'dr')='dr'",
                (de, ate)):
            self.linhas.append((r["ref"],
                                {w for w in (r["titulo_norm"] or "").split()
                                 if w not in STOP and len(w) > 2},
                                r["entidade_norm"] or "", r["nif"] or "",
                                _num(r["preco_base"]), r["data_pub"] or ""))
        self.por_ref = {l[0]: l for l in self.linhas}

    def actualiza(self, c, ref):
        """Depois de se ler o detalhe de um candidato: o preco base passa
        a contar, e se o detalhe o revelou como alteracao de outro (o
        _guardar_detalhe ja o ligou ao original) sai da lista -- era a
        razao de muitas ambiguidades: republicacoes por ler."""
        r = c.execute("SELECT ref, titulo_norm, entidade_norm, nif, preco_base, "
                      "data_pub, estado FROM anuncios WHERE ref=?", (ref,)).fetchone()
        if not r or r["estado"] == "alteracao":
            self.por_ref.pop(ref, None)
            self.linhas = [l for l in self.linhas if l[0] != ref]
            return
        nova = (r["ref"], {w for w in (r["titulo_norm"] or "").split()
                           if w not in STOP and len(w) > 2},
                r["entidade_norm"] or "", r["nif"] or "",
                _num(r["preco_base"]), r["data_pub"] or "")
        self.por_ref[ref] = nova
        self.linhas = [nova if l[0] == ref else l for l in self.linhas]


# Palavras de nome de entidade que nao distinguem ninguem.
STOP_ENT = set("servicos instituto municipio direcao geral regional portugal "
               "nacional autoridade agencia unidade local saude entidade publica "
               "administracao camara municipal secretaria ministerio".split())

_ENTIDADES = {}      # nome no Excel -> (chave no corpus, nome canonico norm., nome norm.)


def _entidade(nome):
    """(chave, canonico, norma) da entidade como o Excel a escreve. A chave
    e o NIF no corpus (quando o nome la esta: SPMS, eSPap, INCM...); o
    canonico e o nome mais usado por essa chave, que e o que os anuncios
    do DR escrevem por extenso. Sem corpus fica so o nome, com alias."""
    import radar
    if nome in _ENTIDADES:
        return _ENTIDADES[nome]
    norma = _norma(nome)
    norma = ALIAS.get(norma, norma)
    chave, canon = "", ""
    try:
        chave = radar.entidade_do_anuncio("", nome or "")
        if chave and radar.ha_corpus():
            with radar.liga_corpus() as k:
                r = k.execute("SELECT nome FROM entidades WHERE chave=?",
                              (chave,)).fetchone()
            canon = radar.simplifica(r["nome"]) if r else ""
    except Exception:           # sem corpus (contratos.db) nao ha chave; fica o nome
        chave, canon = "", ""
    _ENTIDADES[nome] = (chave, canon, norma)
    return _ENTIDADES[nome]


def pontuar(linha, acervo):
    """[(pontuacao, ref)] por ordem decrescente, para uma linha do Excel.

    O nome no Excel e uma abreviatura do titulo do DR ("Plataforma
    Central de Deteção Precoce" para "(DAG) Aquisição de serviços para
    evolução da Plataforma Central de Deteção Precoce no âmbito..."):
    conta sobretudo a CONTENCAO -- que fraccao das palavras do Excel esta
    no titulo --, e o Jaccard so desempata. Medido a 02/09/2026: com o
    Jaccard sozinho ficavam 105 das 187 linhas ambiguas."""
    T = _toks(linha["nome"])
    if not T:
        return []
    chave, canon, ent = _entidade(linha["entidade"])
    palavras = [w for w in (canon or ent).split() if len(w) > 4 and w not in STOP_ENT]
    ano = str(linha["ano"]) if linha["ano"] else ""
    anos = {ano, str(linha["ano"] - 1)} if ano else None
    fora = []
    for ref, TT, EE, nif, pb, dp in acervo.linhas:
        if anos and dp[:4] not in anos:
            continue
        inter = len(T & TT)
        if not inter:
            continue
        sc = 0.7 * inter / float(len(T)) + 0.3 * inter / float(len(T | TT))
        if ano and dp[:4] == ano:
            sc += 0.05          # o ano do Excel e o da decisao; quase sempre o do DR
        ent_ok = ((chave and nif and chave == nif)
                  or (canon and (canon in EE or (EE and EE in canon)))
                  or (ent and ent in EE)
                  or (palavras and sum(w in EE for w in palavras)
                      >= max(1, len(palavras) // 2)))
        if ent_ok:
            sc += 0.35
        if linha["preco_base"] and pb and abs(pb - linha["preco_base"]) < 0.5:
            sc += 0.5
        fora.append((round(sc, 3), ref))
    fora.sort(reverse=True)
    return fora


def ref_pelo_base(c, linha, acervo, pontos=()):
    """O anuncio pelo contrato celebrado. O valor do 1.º lugar da tabela C
    (ou a proposta da casa, quando ganhou) e o preco contratual no BASE, e
    o BASE guarda o `n_anuncio`, que e o ref do DR. Medido a 01/09/2026:
    23 dos 29 primeiros lugares com valor acham-se assim. Um valor
    sozinho engana (o mesmo numero em suturas e em software): exige-se
    a entidade certa ou, sem chave, algum parentesco no titulo."""
    import radar
    if not radar.ha_corpus():
        return ""
    st = _norma(linha.get("status"))
    valores = [cc["valor"] for cc in linha.get("concorrentes") or []
               if cc.get("lugar") == 1 and cc.get("valor")]
    if st == "ganho" and linha.get("valor_proposta"):
        valores.append(linha["valor_proposta"])
    if not valores:
        return ""
    chave, _, _ = _entidade(linha["entidade"])
    ano = linha.get("ano") or datetime.now().year
    achados = {}
    with radar.liga_corpus() as k:
        for v in valores:
            for r in k.execute(
                    "SELECT n_anuncio, adjudicante_chave FROM contratos "
                    "WHERE preco_contratual BETWEEN ? AND ? AND data_celebracao >= ? "
                    "AND n_anuncio != ''", (v - 1, v + 1, "%d-01-01" % (ano - 1))):
                achados[r["n_anuncio"]] = r["adjudicante_chave"] or ""
    score = dict((r, s) for s, r in pontos)
    refs = set()
    for n, adj in achados.items():
        if chave and adj and adj != chave:
            continue
        ref = n
        if n not in acervo.por_ref:
            a = c.execute("SELECT estado, altera FROM anuncios WHERE ref=?",
                          (n,)).fetchone()
            if not a:
                continue
            if a["estado"] == "alteracao":
                ref = radar.raiz_da_alteracao(c, n, a["altera"] or "") or ""
            if ref not in acervo.por_ref:
                continue
        if (chave and adj == chave) or score.get(ref, 0) >= 0.3:
            refs.add(ref)
    return refs.pop() if len(refs) == 1 else ""


def decidir(pontos):
    """(ref, candidatos): a ligacao unica, ou '' e a lista dos candidatos."""
    if not pontos or pontos[0][0] < LIMIAR:
        return "", [r for s, r in pontos[:MAX_CANDIDATOS] if s >= 0.3]
    if len(pontos) > 1 and pontos[1][0] >= LIMIAR and pontos[1][0] > pontos[0][0] - FOLGA:
        return "", [r for s, r in pontos[:MAX_CANDIDATOS] if s >= 0.3]
    return pontos[0][1], []


# ------------------------------------------------------- a aplicacao

def _texto_top3(concorrentes):
    import radar
    partes = []
    for cc in sorted(concorrentes or [], key=lambda x: x.get("lugar") or 9)[:3]:
        v = cc.get("valor")
        partes.append("%d.º %s%s" % (cc.get("lugar") or 0, cc.get("nome") or "",
                                     " " + radar._texto_do_preco(v) if v else ""))
    return " · ".join(partes)[:300]


def estado_pretendido(linha, papeis):
    """(estado, fase_id, campos) que o registo da casa pede para o anuncio,
    ou None quando o estado do Excel nao se traduz em triagem."""
    import radar
    st = _norma(linha.get("status"))
    if st not in ESTADOS_COM_TRIAGEM:
        return None
    if st == "nao fomos":
        motivo = MAPA_RAZAO.get(_norma(linha.get("razao")))
        return ("descartado", None, {"motivo": motivo})
    campos = {}
    if linha.get("valor_proposta"):
        campos["preco_proposto"] = radar._texto_do_preco(linha["valor_proposta"])
    if st == "submetido":
        return ("interessa", papeis.get("submetido"), campos)
    lugar = int(linha["lugar"]) if linha.get("lugar") else (1 if st == "ganho" else None)
    campos["posicao"] = lugar
    campos["top3"] = _texto_top3(linha.get("concorrentes")) or None
    return ("interessa", papeis.get(st), campos)


def aplicar(c, linha, ref, quem="Excel"):
    """Escreve a triagem do registo no anuncio ligado. Devolve 'aplicado',
    'igual', 'sem estado' ou 'conflito'.

    Nao passa por cima de uma decisao humana feita no radar: um
    'interessa', um descartado com motivo ou um cartao com fase que
    discordem do Excel ficam como estao, e o conflito e registado uma
    vez no historico -- e o Zoho que decide isso, e ainda nao esta cá."""
    import radar
    a = c.execute("SELECT estado, fase_id, motivo, preco_proposto, posicao, top3 "
                  "FROM anuncios WHERE ref=?", (ref,)).fetchone()
    if not a:
        return "sem anúncio"
    papeis = {r["papel"]: r["id"] for r in c.execute(
        "SELECT id, papel FROM fases WHERE papel IS NOT NULL")}
    pedido = estado_pretendido(linha, papeis)
    if not pedido:
        return "sem estado"
    estado, fase_id, campos = pedido
    humano = (a["estado"] == "interessa"
              or (a["estado"] == "descartado" and a["motivo"])
              or a["fase_id"] is not None)
    igual = (a["estado"] == estado
             and (fase_id is None or a["fase_id"] == fase_id)
             and all((a[k] or None) == (v or None) for k, v in campos.items()
                     if k in a.keys()))
    if igual:
        return "igual"
    if humano and (a["estado"] != estado
                   or (fase_id is not None and a["fase_id"] != fase_id)):
        aviso = ("o registo da casa diz «%s»; mantém-se a decisão do radar"
                 % (linha.get("status") or ""))
        if not c.execute("SELECT 1 FROM historico WHERE ref=? AND detalhe=?",
                         (ref, aviso)).fetchone():
            _registar(c, ref, "estado", aviso, quem)
        return "conflito"
    sets, vals = ["estado=?"], [estado]
    if estado == "interessa":
        sets.append("fase_id=?"); vals.append(fase_id)
        sets.append("motivo=NULL")
    else:
        sets.append("fase_id=NULL")
    for k, v in campos.items():
        sets.append("%s=?" % k); vals.append(v)
    c.execute("UPDATE anuncios SET %s WHERE ref=?" % ", ".join(sets), vals + [ref])
    nome_fase = ""
    if fase_id:
        f = c.execute("SELECT nome FROM fases WHERE id=?", (fase_id,)).fetchone()
        nome_fase = f["nome"] if f else ""
    detalhe = ("%s%s%s, do registo da casa"
               % (radar._NOMES_ESTADO.get(estado, estado),
                  " (%s)" % campos["motivo"] if campos.get("motivo") else "",
                  " › %s" % nome_fase if nome_fase else ""))
    _registar(c, ref, "estado", detalhe, quem)
    if campos.get("preco_proposto"):
        _registar(c, ref, "preço proposto", campos["preco_proposto"], quem)
    if campos.get("posicao") or campos.get("top3"):
        _registar(c, ref, "relatório preliminar",
                  "%s%s" % ("%dº lugar" % campos["posicao"] if campos.get("posicao")
                            else "sem lugar",
                            " — " + campos["top3"] if campos.get("top3") else ""),
                  quem)
    return "aplicado"


def _registar(c, ref, accao, detalhe, quem):
    c.execute("INSERT INTO historico (ref, quem, accao, detalhe, quando) "
              "VALUES (?,?,?,?,?)",
              (ref, quem, accao, detalhe, datetime.now().strftime("%Y-%m-%d %H:%M")))


# --------------------------------------------------------- a tabela

def iniciar_tabelas(c):
    c.execute("""CREATE TABLE IF NOT EXISTS casa (
        id INTEGER PRIMARY KEY, nome TEXT, entidade TEXT, modelo TEXT,
        prazo_meses REAL, preco_base REAL, criterio TEXT, plataforma TEXT,
        ano INTEGER, status TEXT, razao TEXT, valor_proposta REAL,
        lugar INTEGER, ebitda REAL, notas TEXT, folha TEXT,
        perfis TEXT, concorrentes TEXT, precos_perfis TEXT,
        ref TEXT, ligacao TEXT DEFAULT '', candidatos TEXT DEFAULT '[]',
        fora INTEGER DEFAULT 0, resultado TEXT DEFAULT '',
        importado_em TEXT, aplicado_em TEXT)""")
    c.execute("CREATE INDEX IF NOT EXISTS ix_casa_ref ON casa(ref)")


CAMPOS_EXCEL = ("nome", "entidade", "modelo", "prazo_meses", "preco_base",
                "criterio", "plataforma", "ano", "status", "razao",
                "valor_proposta", "lugar", "ebitda", "notas", "folha")


def _guardar_linha(c, linha, ref, ligacao, candidatos, fora, resultado, agora):
    vals = [linha.get(k) for k in CAMPOS_EXCEL]
    vals = [(None if v == "" else v) for v in vals]
    c.execute(
        "INSERT INTO casa (id, %s, perfis, concorrentes, precos_perfis, ref, "
        "ligacao, candidatos, fora, resultado, importado_em, aplicado_em) "
        "VALUES (?, %s, ?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET %s, "
        "perfis=excluded.perfis, concorrentes=excluded.concorrentes, "
        "precos_perfis=excluded.precos_perfis, ref=excluded.ref, "
        "ligacao=excluded.ligacao, candidatos=excluded.candidatos, "
        "fora=excluded.fora, resultado=excluded.resultado, "
        "importado_em=excluded.importado_em, aplicado_em=excluded.aplicado_em"
        % (", ".join(CAMPOS_EXCEL), ", ".join("?" * len(CAMPOS_EXCEL)),
           ", ".join("%s=excluded.%s" % (k, k) for k in CAMPOS_EXCEL)),
        [linha["id"]] + vals + [
            json.dumps(linha.get("perfis") or [], ensure_ascii=False),
            json.dumps(linha.get("concorrentes") or [], ensure_ascii=False),
            json.dumps(linha.get("precos_perfis") or [], ensure_ascii=False),
            ref or None, ligacao, json.dumps(candidatos), int(bool(fora)),
            resultado, agora, agora if resultado == "aplicado" else None])


def importar(caminho, ensaio=False, ler=True, quem="Excel", relatar=None,
             triagem=False):
    """Le o Excel, liga cada linha ao procedimento e guarda o registo.

    `ensaio` calcula tudo e nao grava nada. `ler` autoriza ir ao DR
    buscar o detalhe dos candidatos de uma linha ambigua (um pedido por
    candidato, ~1 s) para o preco base desempatar. `triagem` escreve
    tambem a triagem nos anuncios ligados -- DESLIGADO por omissao,
    decisao do Afonso a 02/09/2026: enquanto as ligacoes nao estiverem
    validadas e os lotes (varias linhas do Excel no mesmo anuncio) nao
    tiverem solucao, guarda-se a informacao e mais nada. Devolve o
    relatorio: contagens e as listas do que ficou por ligar."""
    import radar
    diz = relatar or (lambda _: None)
    linhas = ler_excel(caminho)
    linhas = [l for l in linhas if l["id"]]
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    rel = {"total": len(linhas), "fora": [], "ligadas": 0, "novas": 0,
           "manuais": 0, "pelo_base": 0, "ambiguas": [], "sem": [],
           "aplicadas": {}, "conflitos": [], "lidos": 0, "ensaio": ensaio}
    _ENTIDADES.clear()
    # Duas passagens, de proposito. A primeira so LE (e vai ao DR pelos
    # candidatos ambiguos); a segunda escreve. Com uma so, a ligacao que
    # ja tinha escrito a primeira linha da casa segurava a base numa
    # transaccao, e o ler_detalhe_de(), que grava pela ligacao dele,
    # ficava a espera ate rebentar com "database is locked" -- so na
    # importacao a serio, porque o ensaio nao escrevia nada.
    decisoes = []
    with radar.liga() as c:
        iniciar_tabelas(c)
    with radar.liga() as c:
        acervo = Acervo(c, {l["ano"] for l in linhas})
        existentes = {r["id"]: dict(r) for r in c.execute(
            "SELECT id, ref, ligacao FROM casa")}
        for linha in linhas:
            antes = existentes.get(linha["id"]) or {}
            if fora_do_pais(linha):
                rel["fora"].append(linha["nome"])
                decisoes.append((linha, "", "", [], True))
                continue
            ref, ligacao, candidatos = "", "", []
            if antes.get("ref") and antes.get("ligacao") == "manual":
                ref, ligacao = antes["ref"], "manual"
                rel["manuais"] += 1
            else:
                pontos = pontuar(linha, acervo)
                ref, candidatos = decidir(pontos)
                if not ref:
                    # o contrato celebrado sabe o ref: pelo valor do 1.º lugar
                    ref = ref_pelo_base(c, linha, acervo, pontos)
                    if ref:
                        ligacao, candidatos = "base", []
                        rel["pelo_base"] += 1
                if not ref and candidatos and ler:
                    # desempate pela leitura do detalhe dos candidatos que
                    # ainda nao o tem: traz o preco base, e revela as
                    # republicacoes (que saem da lista). Um pedido por
                    # candidato, ~1 s, sem castigar o portal.
                    for cand in candidatos:
                        if acervo.por_ref.get(cand) and acervo.por_ref[cand][4] is None:
                            ok, _ = radar.ler_detalhe_de(cand)
                            rel["lidos"] += 1
                            time.sleep(0.7)
                            if not ok:
                                break
                            acervo.actualiza(c, cand)
                    ref, candidatos = decidir(pontuar(linha, acervo))
                if ref:
                    ligacao = ligacao or "auto"
                    if antes.get("ref") != ref:
                        rel["novas"] += 1
            decisoes.append((linha, ref, ligacao, candidatos, False))
    with radar.liga() as c:
        papeis = {r["papel"]: r["id"] for r in c.execute(
            "SELECT id, papel FROM fases WHERE papel IS NOT NULL")}
        for linha, ref, ligacao, candidatos, fora in decisoes:
            resultado = ""
            if fora:
                resultado = "fora"
            elif ref:
                rel["ligadas"] += 1
                if not triagem:
                    resultado = "guardado"
                elif ensaio:
                    # o que se faria, sem escrever: le-se o estado actual
                    pedido = estado_pretendido(linha, papeis)
                    a = c.execute("SELECT estado FROM anuncios WHERE ref=?",
                                  (ref,)).fetchone()
                    resultado = ("sem estado" if not pedido else
                                 "igual" if a and a["estado"] == pedido[0] else
                                 "aplicado")
                else:
                    resultado = aplicar(c, linha, ref, quem)
                rel["aplicadas"][resultado] = rel["aplicadas"].get(resultado, 0) + 1
                if resultado == "conflito":
                    rel["conflitos"].append((linha["nome"], ref, linha["status"]))
            elif candidatos:
                rel["ambiguas"].append((linha["id"], linha["nome"], linha["entidade"],
                                        linha["ano"], candidatos))
            else:
                rel["sem"].append((linha["id"], linha["nome"], linha["entidade"],
                                   linha["ano"]))
            if not ensaio:
                _guardar_linha(c, linha, ref, ligacao, candidatos, fora,
                               resultado, agora)
        if not ensaio:
            c.execute("INSERT OR REPLACE INTO estado VALUES ('excel_casa', ?)",
                      (caminho,))
            c.execute("INSERT OR REPLACE INTO estado VALUES ('excel_casa_em', ?)",
                      (agora,))
    return rel


def texto_do_relatorio(rel):
    linhas = ["%d concursos no Excel%s" % (rel["total"],
                                            " (ENSAIO: nada foi gravado)" if rel["ensaio"] else "")]
    linhas.append("  ligados ao radar: %d (%d novos, %d à mão, %d pelo contrato no BASE)"
                  % (rel["ligadas"], rel["novas"], rel["manuais"], rel["pelo_base"]))
    if rel["aplicadas"]:
        linhas.append("  triagem: " + ", ".join(
            "%s %d" % (k, v) for k, v in sorted(rel["aplicadas"].items())))
        if list(rel["aplicadas"]) == ["guardado"]:
            linhas[-1] += " (só o registo; a triagem não se aplica sem --com-triagem)"
    if rel["lidos"]:
        linhas.append("  detalhes lidos ao DR para desempatar: %d" % rel["lidos"])
    linhas.append("  ambíguos: %d | sem correspondência: %d | fora do país: %d"
                  % (len(rel["ambiguas"]), len(rel["sem"]), len(rel["fora"])))
    for ide, nome, ent, ano, cands in rel["ambiguas"]:
        linhas.append("    ? #%s %s — %s (%s): %s" % (ide, nome[:50], ent, ano,
                                                     ", ".join(cands)))
    for ide, nome, ent, ano in rel["sem"]:
        linhas.append("    - #%s %s — %s (%s)" % (ide, nome[:50], ent, ano))
    for nome, ref, st in rel["conflitos"]:
        linhas.append("    ! %s: o Excel diz %s, o radar decidiu outra coisa (%s)"
                      % (nome[:50], st, ref))
    return "\n".join(linhas)


# ------------------------------------------------------ para o painel

def registo_de(c, ref):
    """A linha da casa ligada a este anuncio, ou None."""
    r = c.execute("SELECT * FROM casa WHERE ref=? ORDER BY id LIMIT 1",
                  (ref,)).fetchone()
    return dict(r) if r else None


def ligar_a_mao(c, ide, ref, quem="Afonso", triagem=False):
    """Liga uma linha do registo a um anuncio, resolvendo uma alteracao
    para o original. So escreve triagem com `triagem`. Devolve (ok,
    mensagem)."""
    import radar
    a = c.execute("SELECT ref, estado, altera FROM anuncios WHERE ref=?",
                  (ref,)).fetchone()
    if not a:
        return False, "não há nenhum anúncio %s" % ref
    if a["estado"] == "alteracao":
        raiz = radar.raiz_da_alteracao(c, ref, a["altera"] or "")
        if raiz:
            ref = raiz
    linha = c.execute("SELECT * FROM casa WHERE id=?", (ide,)).fetchone()
    if not linha:
        return False, "não há nenhum registo #%s" % ide
    d = dict(linha)
    for k in ("perfis", "concorrentes", "precos_perfis"):
        try:
            d[k] = json.loads(d.get(k) or "[]")
        except ValueError:
            d[k] = []
    resultado = aplicar(c, d, ref, quem) if triagem else "guardado"
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    c.execute("UPDATE casa SET ref=?, ligacao='manual', candidatos='[]', "
              "resultado=?, aplicado_em=? WHERE id=?",
              (ref, resultado, agora if resultado == "aplicado" else None, ide))
    return True, "#%s ligado ao anúncio %s (%s)" % (ide, ref, resultado)


def desligar(c, ide):
    c.execute("UPDATE casa SET ref=NULL, ligacao='', resultado='', "
              "aplicado_em=NULL WHERE id=?", (ide,))


def desaplicar_da_copia(copia):
    """Desfaz a triagem que uma importacao escreveu nos anuncios, repondo
    os campos de triagem tal como estao numa COPIA da base feita antes
    dela, e apaga do historico o que a importacao la escreveu. O registo
    (tabela casa) fica; as ligacoes ficam. Devolve (anuncios repostos,
    linhas de historico apagadas).

    Existe porque a 02/09/2026 se importou e aplicou, e o Afonso decidiu
    a seguir que nada se aplica antes de o registo estar validado."""
    import radar
    import sqlite3
    antes = sqlite3.connect("file:%s?mode=ro" % copia.replace("\\", "/"), uri=True)
    antes.row_factory = sqlite3.Row
    repostos = apagadas = 0
    with radar.liga() as c:
        refs = [r["ref"] for r in c.execute(
            "SELECT DISTINCT ref FROM casa WHERE ref IS NOT NULL "
            "AND resultado IN ('aplicado', 'conflito', 'igual')")]
        for ref in refs:
            a = antes.execute("SELECT %s FROM anuncios WHERE ref=?"
                              % ", ".join(radar.CAMPOS_DA_TRIAGEM), (ref,)).fetchone()
            if not a:
                continue
            c.execute("UPDATE anuncios SET %s WHERE ref=?"
                      % ", ".join("%s=?" % k for k in radar.CAMPOS_DA_TRIAGEM),
                      [a[k] for k in radar.CAMPOS_DA_TRIAGEM] + [ref])
            repostos += 1
        apagadas = c.execute("DELETE FROM historico WHERE quem='Excel'").rowcount
        c.execute("UPDATE casa SET resultado='guardado', aplicado_em=NULL "
                  "WHERE ref IS NOT NULL AND resultado != 'fora'")
    antes.close()
    return repostos, apagadas
