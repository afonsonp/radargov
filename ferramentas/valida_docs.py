#!/usr/bin/env python3
"""Confere se o que a documentação afirma existe mesmo.

    python ferramentas/valida_docs.py            # o relatório
    python ferramentas/valida_docs.py --curto    # só a contagem

Nasceu a 19/09/2026, do pedido dele: «valida toda a documentação». E
nasceu de uma falha concreta do mesmo dia — o `CLAUDE.md` mandava
invocar, no início de **todas** as sessões, uma skill `task-observer`
que **não existia**, e escrever num caminho `~/.claude/projects/D--radar/`
que era do Windows, de antes da mudança de 8/09. Sobreviveu a duas
mudanças de sistema porque **um `.md` não falha**: ninguém o corre.

O `repetido.py` pergunta «isto está escrito duas vezes?». Este pergunta
outra coisa, e é a que faltava: **«isto que aqui está escrito existe?»**

Confere nove famílias de referência, e só as que têm resposta
mecânica:

  `funcao()`     está definida no nosso código?
  `CONSTANTE`    aparece em ficheiro de código nenhum?
  `--bandeira`   o programa, uma skill ou uma ferramenta aceita-a?
  `/rota`        está registada no Flask?
  `ficheiro.ext` existe no disco?
  `pasta/`       existe no disco?
  `§N.N`         a secção existe no ficheiro apontado?
  a skill X      existe em .claude/skills, .claude/agents ou no perfil?
  `~/caminho`    existe?

E as contagens deriváveis (`valida_numeros()`): rotas, tabelas, áreas
e pontos das armadilhas, secções das configurações.

**As duas últimas famílias entraram depois, e é a parte que interessa.**
A 19/09/2026 parti o `CLAUDE.md` de propósito, com quatro mentiras do
mesmo feitio das do `task-observer`: uma função, uma rota, uma skill e
um caminho `~/`. A ferramenta apanhou **duas** — e as duas que
escaparam eram exactamente as do `task-observer`. **A ferramenta que
nasceu dele não o teria apanhado.** Só depois de as acrescentar é que
a prova deu quatro em quatro.

Se acrescentares uma família, parte a documentação de propósito e vê
se ela cai. Um verificador que nunca falhou não está provado — está
por experimentar.

**O que NÃO confere: se a frase é verdadeira.** «O prazo é 15 dias»
tem um número que este programa não sabe ler. Para esses vale a regra
da casa — confirmar no código antes de escrever.

E **nem toda a ausência é erro**: a documentação fala de propósito de
coisas que saíram (os `.bat` do Windows, o `casa.py`), e de ficheiros
que só existem em uso (`AVISOS.txt`, as capturas). Por isso há uma
lista de isenções, cada uma com a razão escrita.
"""
import ast
import io
import os
import re
import sys
from collections import defaultdict

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# O `docs/referencia.md` **não** está aqui, e é decisão de
# 19/09/2026. Ele próprio se declara «contexto histórico» no
# cabeçalho, escreve no passado («havia quatro documentos HTML») e a
# tabela dos donos põe-no ao lado do `docs/historico/` — é o «porquê,
# com data». Conferi-lo contra o código de hoje dava ~15 falsos
# positivos permanentes, e uma ferramenta que acusa sempre o mesmo
# deixa de se ler.
VIVOS = ["CLAUDE.md", "ESTADO.md", "BACKLOG.md", "LEIA-ME.md",
         "docs/FUNCIONAL.md", "docs/armadilhas.md", "docs/design.md",
         "docs/seguranca.md"]

MODULOS = ["radar.py", "contas.py", "empresa.py"]

# Referências que a documentação faz de propósito a coisas que não
# existem — porque saíram, ou porque só nascem em uso. Cada uma leva a
# razão: sem ela, isto vira um saco onde se esconde o que incomoda.
ISENTOS = {
    "agendar.bat": "os .bat saíram a 8/09/2026",
    "actualizar.bat": "os .bat saíram a 8/09/2026",
    "iniciar.bat": "os .bat saíram a 8/09/2026",
    "publicar_dados.bat": "os .bat saíram a 8/09/2026",
    "trazer_dados.bat": "os .bat saíram a 8/09/2026",
    "reler.bat": "os .bat saíram a 8/09/2026",
    "contratos.bat": "os .bat saíram a 8/09/2026",
    "detalhes.bat": "os .bat saíram a 8/09/2026",
    "casa.py": "renomeado para empresa.py a 16/09/2026",
    "Analise_Concursos_Publicos.xlsm": "o Excel legado, já importado",
    "AVISOS.txt": "escrito pelo primeiro resumo",
    "curl_DR.txt": "captura do Afonso; não entra no git",
    "curl_detalhe.txt": "captura do Afonso; não entra no git",
    "radar.db": "a base; não entra no git",
    "contratos.db": "o corpus; não entra no git",
    "empresas/1/empresa.db": "o trabalho da empresa (F1); não entra no git",
    "empresa.db": "o ficheiro de cada empresa (F1); não entra no git",
    "empresas/": "a pasta das empresas (F1); não entra no git",
    "radar-AAAA-MM-DD.db": "o molde do nome da cópia diária",
    "empresa-1-AAAA-MM-DD.db": "o molde do nome da cópia diária da empresa",
    "triagem.jsonl": "exportado pela verificação",
    "email_senha.txt": "segredo; nunca no git",
    "config.json": "criado no primeiro arranque",
    "ecrans-radargov.html": "gerado pelo ferramentas/ecrans.py",
    "painel.log": "gerado em uso",
    "documentos/": "o nome antigo de pecas/, até 19/09/2026",
    # bandeiras que a prosa declara mortas ou por nascer, e diz qual é
    "--importar-excel": "saiu a 15/09/2026, com o leitor do Excel",
    "--empresa-ligar": "saiu a 15/09/2026, com o leitor do Excel",
    "--com-triagem": "por implementar; a prosa diz «quando se aplicar»",
    "--ensaio": "idem, do mesmo plano por implementar",
    # saíram com o leitor do Excel a 15/09/2026; as armadilhas
    # descrevem-nas como história, e o aviso está à cabeça da área
    # «Triagem, quadro e ficha»
    "importar()": "saiu com o leitor do Excel a 15/09/2026",
    "_guardar_linha()": "saiu com o leitor do Excel a 15/09/2026",
    "lote_da_linha()": "saiu com o leitor do Excel a 15/09/2026",
    "carta_de_lotes()": "saiu com o leitor do Excel a 15/09/2026",
    "com_corpus()": "nunca foi chamada; saiu a 03/09/2026",
    # saíram com o quadro, no mesmo dia
    "cartao()": "saiu com o quadro a 15/09/2026",
    "FASES_COM_PROPOSTO": "saiu com o quadro a 15/09/2026",
    "caixa_de_filtros()": "saiu com os filtros guardados a 13/09/2026",
    "GUARDAR_JS": "idem",
    "/filtros/guardar": "idem",
    "/quadro": "o quadro saiu a 15/09/2026",
    "/quadro/mover": "o quadro saiu a 15/09/2026",
    "/empresa": "saiu a 15/09/2026, com o registo da empresa",
    "FORA_DO_PAIS": "do plano por implementar, como o --com-triagem",
    # propostas do BACKLOG: nomes de código que ainda não existe
    "excerto_de()": "proposta do BACKLOG, por implementar",
    "soma_precos_base()": "proposta do BACKLOG, por implementar",
    # exemplos de ataque na área da segurança, não rotas
    "/documento": "exemplo de travessia de caminho",
    "/documento/../curl_DR.txt": "exemplo de travessia de caminho",
    "/peca": "exemplo de travessia de caminho",
    "/peca-pagina": "exemplo de travessia de caminho",
    "/peca/../radar.db": "exemplo de travessia de caminho",
    # caminhos que não são rotas nossas
    "/proc/PID/limits": "caminho do Linux",
    "/chat/completions": "endpoint do dialecto OpenAI, nos fornecedores",
    "/dr/feeds": "caminho do portal do DR, investigado",
    "/dr/rss": "caminho do portal do DR, investigado",
    "/dr/ultimos": "caminho do portal do DR, investigado",
    "/estado/": "abreviatura de /estado/<ref>/<estado>",
    "/estado-radar": "o nome da skill, não uma rota",
    "/hoje": "a abertura é `/`; o /hoje nunca existiu como rota",
    "/reler": "abreviatura; a rota é /reler-pecas",
    # ficheiros que o código procura mas podem não estar cá
    "chave_api.txt": "um dos NOMES_CHAVE que o código aceita",
    "docs/diario/2026-MM.md": "molde: MM é o mês",
    "settings.json": "é o .claude/settings.json",
    ".github/seguranca-radar.md": "a revisão saiu a 15/09/2026",
    "sonda.py": "sonda de investigação, não versionada",
    "sonda.bat": "idem",
    "sonda.txt": "idem",
    "sonda_detalhe.html": "idem",
    "Concursos.dc.html": "o protótipo do DesignSync, não versionado",
    "cpv.json": "vocabulário CPV, importado uma vez",
    "cpv-2024.json": "idem",
    "curl_ensaio_do_hook.txt": "ficheiro de ensaio do hook, apagado",
    "verificar.bat": "os .bat saíram a 8/09/2026",
    "radar/": "«a pasta do radar», genérico",
    # a skill que nunca existiu: o CLAUDE.md fala dela para dizer
    # que saiu, e é dela que esta ferramenta nasceu
    "task-observer": "saiu a 19/09/2026; nunca existiu",
}


# MAIÚSCULAS que não são constantes nossas: SQL, HTTP, o sistema
# operativo, variáveis de ambiente, e os nomes dos ficheiros do
# histórico escritos sem a extensão. Apanhá-las era ruído que
# escondia as três que importavam.
NAO_SAO_CONSTANTES = {
    # SQL
    "ALTER", "ATTACH", "DELETE", "EXISTS", "GLOB", "INSERT", "JOIN",
    "LIKE", "LIMIT", "NULL", "PRAGMA", "REPLACE", "SEARCH", "SELECT",
    "UPDATE", "VACUUM", "WAL", "GROUP", "ORDER", "WHERE", "INDEX",
    # HTTP e web
    "GET", "POST", "CSRF", "HTML", "CSS", "JSON", "URL", "API", "HTTP",
    # sistema e ambiente
    "SO_REUSEADDR", "O_EXCL", "GROQ_API_KEY", "NVIDIA_API_KEY",
    "OPENROUTER_API_KEY",
    # abreviaturas da interface
    "CLI", "CONC", "CPV", "NIF", "NIPC", "IVA", "PDF", "CE", "PC",
    # ficheiros do histórico, citados sem extensão
    "AUDITORIA", "SANEAMENTO", "ESQUELETO", "UX-Auditoria", "CAMADAS",
    "CICLOS", "CONCORRENTES", "CRM", "ONLINE", "REDESENHO", "FUNCIONAL",
    "BACKLOG", "ESTADO",
}

# Embutidas do Python e metodos de JS que a documentacao cita a
# proposito ("um `int()` que rebenta", "o `escape()` da barra"). Nao
# sao funcoes nossas e nao ha nada para conferir.
NAO_SAO_NOSSAS = {
    "int", "float", "str", "len", "print", "open", "range", "sorted",
    "escape", "strip", "split", "join", "accept", "reload", "replace",
    "format", "get", "set", "append", "items", "keys", "values",
}


# --------------------------------------------------------- os números
#
# A segunda família de apodrecimento, e a mais silenciosa: uma contagem
# que era verdade no dia em que se escreveu. Aqui ficam só as que se
# **derivam** — o resto (quantos anúncios, quantos MB) mede-se e vai
# para o `ESTADO.md` com data, que é o dono desses.
#
# Medido a 19/09/2026, ao escrever isto: três estavam erradas. As
# «80 rotas» eram 81, as «15 áreas» eram 16 em dois ficheiros, e os
# «223 pontos» eram 222 — este último **estragado nesse mesmo dia**,
# por eu ter fundido duas armadilhas numa e não ter recontado.
#
# Cada entrada é (rótulo, ficheiro, expressão com UM grupo, como se
# sabe a verdade).
def _conta_no_ficheiro(caminho, padrao):
    return len(re.findall(padrao, io.open(
        os.path.join(RAIZ, caminho), encoding="utf-8").read(), re.M))


def NUMEROS():
    import sqlite3
    sys.path.insert(0, RAIZ)
    import radar

    def tabelas():
        base = os.path.join(RAIZ, "radar.db")
        if not os.path.exists(base):
            return None                      # sem base, não se julga
        c = sqlite3.connect("file:%s?mode=ro" % base, uri=True)
        try:
            # As da empresa nao contam, estejam onde estiverem: a F1
            # (23/09/2026) leva-as para o ficheiro dela no primeiro
            # arranque, e ate la ainda moram aqui.
            return len({r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
                " AND name NOT LIKE 'sqlite_%'")} - set(radar.TABELAS_DA_EMPRESA))
        finally:
            c.close()

    return [
        ("tabelas em radar.db", "docs/FUNCIONAL.md",
         r"(\d+) tabelas\)", tabelas),
        ("rotas registadas", "docs/FUNCIONAL.md",
         r"\*\*(\d+) rotas\.?\*\*",
         lambda: len(list(radar.app.url_map.iter_rules()))),
        ("áreas nas armadilhas", "CLAUDE.md",
         r"em \*\*(\d+) áreas\*\*",
         lambda: _conta_no_ficheiro("docs/armadilhas.md", r"^## ")),
        ("pontos nas armadilhas", "CLAUDE.md",
         r"São \*\*(\d+) pontos\*\*",
         lambda: _conta_no_ficheiro("docs/armadilhas.md", r"^- \*\*")),
        ("secções de configurações", "CLAUDE.md",
         r"(\w+) secções por esta ordem",
         lambda: len(radar.SECCOES_CONFIG)),
    ]


PALAVRA_NUMERO = {"uma": 1, "duas": 2, "três": 3, "quatro": 4, "cinco": 5,
                  "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10,
                  "onze": 11, "doze": 12, "treze": 13, "catorze": 14,
                  "quinze": 15, "dezasseis": 16}


def valida_numeros():
    """[(rótulo, ficheiro, o que diz, o que é)] das que não batem."""
    maus = []
    for rotulo, ficheiro, padrao, verdade in NUMEROS():
        p = os.path.join(RAIZ, ficheiro)
        if not os.path.exists(p):
            continue
        m = re.search(padrao, io.open(p, encoding="utf-8").read())
        if not m:
            maus.append((rotulo, ficheiro, "não encontrado", "—"))
            continue
        bruto = m.group(1).replace(" ", "").replace(" ", "")
        diz = (int(bruto) if bruto.isdigit()
               else PALAVRA_NUMERO.get(bruto.lower()))
        real = verdade()
        if real is None or diz is None:
            continue
        if diz != real:
            maus.append((rotulo, ficheiro, diz, real))
    return maus


def sem_codigo(t):
    return re.sub(r"```.*?```", "", t, flags=re.S)


def refs_dos_docs():
    """{tipo: {token: [(ficheiro, linha)]}}"""
    achados = defaultdict(lambda: defaultdict(list))
    for f in VIVOS:
        p = os.path.join(RAIZ, f)
        if not os.path.exists(p):
            continue
        for n, linha in enumerate(sem_codigo(
                io.open(p, encoding="utf-8").read()).splitlines(), 1):
            for tok in re.findall(r"`([^`\n]{1,80})`", linha):
                s = tok.strip()
                if re.fullmatch(r"[a-z_][a-z0-9_]*\(\)", s):
                    k = "funcao"
                elif re.fullmatch(r"[A-Z][A-Z0-9_]{2,}", s):
                    if s in NAO_SAO_CONSTANTES:
                        continue
                    k = "constante"
                elif re.fullmatch(r"--[a-z0-9-]+", s):
                    # `--x` é bandeira do programa OU variável de CSS, e
                    # a documentação fala das duas. Distinguem-se pelo
                    # que existe: desde 21/09/2026 a documentação cita
                    # `--ink`, `--azul`, `--surface` e companhia a
                    # propósito da migração, e o validador acusava-as de
                    # serem bandeiras que o programa não aceita.
                    k = "variavel" if s in variaveis_css() else "bandeira"
                elif re.fullmatch(r"/[\w/<>:.-]*", s) and len(s) > 1:
                    k = "rota"
                elif re.fullmatch(
                        r"[\w./-]+\.(md|py|sh|json|txt|db|html|jsonl|xlsm|bat)", s):
                    k = "ficheiro"
                elif re.fullmatch(r"[\w/-]+/", s):
                    k = "pasta"
                elif re.fullmatch(r"~/[\w./-]+", s):
                    k = "caminho_de_casa"
                else:
                    continue
                achados[k][s].append((f, n))
            for sec in re.findall(
                    r"`([\w./-]+\.md)`[^`\n]{0,40}?§(\d+(?:\.\d+)?)", linha):
                achados["seccao"]["%s§%s" % sec].append((f, n))
            # **A família que faltava**, e é a que fundou a ferramenta:
            # a instrução do `task-observer` dizia «a skill global
            # `task-observer`» e escrevia em `~/.claude/projects/…`.
            # A primeira versão disto não conferia nem uma coisa nem
            # outra — apanhava a função e a rota inventadas, e deixava
            # passar exactamente o erro que a motivou. Provado a
            # 19/09/2026 partindo o `CLAUDE.md` de propósito.
            for m in re.finditer(
                    r"(?:skill|subagente|agente)s?\s+(?:global\s+)?"
                    r"\*{0,2}`([\w-]+)`", linha, re.I):
                achados["skill"][m.group(1)].append((f, n))
    return achados


def _fontes():
    """Todos os `.py` nossos: os módulos, as skills e as ferramentas."""
    fontes = [os.path.join(RAIZ, m) for m in MODULOS]
    for pasta in (".claude/skills", ".claude/hooks", "ferramentas"):
        for raiz, _, ficheiros in os.walk(os.path.join(RAIZ, pasta)):
            if "__pycache__" in raiz:
                continue
            fontes += [os.path.join(raiz, f) for f in ficheiros
                       if f.endswith(".py")]
    return [p for p in fontes if os.path.exists(p)]


_VARIAVEIS_CSS = None


def variaveis_css():
    """Todas as variáveis CSS que o painel **define**, venham do
    `radar.py` ou das folhas de `estilo/`.

    Uma definição vem sempre a seguir a um `{` ou a um `;`; sem essa
    âncora, um `.rg-btn--danger:hover` lia-se como a definição de
    `--danger`. (A mesma armadilha apanhou o teste irmão, no
    `TestPeleNova`.)
    """
    global _VARIAVEIS_CSS
    if _VARIAVEIS_CSS is None:
        textos = []
        for nome in ("radar.py",):
            caminho = os.path.join(RAIZ, nome)
            if os.path.exists(caminho):
                textos.append(io.open(caminho, encoding="utf-8").read())
        pasta = os.path.join(RAIZ, "estilo")
        if os.path.isdir(pasta):
            for f in sorted(os.listdir(pasta)):
                if f.endswith(".css"):
                    textos.append(io.open(os.path.join(pasta, f),
                                          encoding="utf-8").read())
        junto = re.sub(r"/\*.*?\*/", " ", "\n".join(textos), flags=re.S)
        _VARIAVEIS_CSS = set(re.findall(r"[{;]\s*(--[a-z0-9-]+)\s*:", junto))
    return _VARIAVEIS_CSS


def o_que_o_codigo_tem():
    """Funções e nomes atribuídos, **em qualquer nível**.

    À primeira versão só contei atribuições ao nível do módulo, e o
    relatório acusou dez nomes que existiam — `ARV_SEL`, `PAGINA`,
    `LIMIAR` e companhia, atribuídos dentro de funções. Mesma lição
    das bandeiras: confere-se a ferramenta antes de acusar o texto.
    """
    funcoes, constantes = set(), set()
    for p in _fontes():
        try:
            arv = ast.parse(io.open(p, encoding="utf-8").read(), filename=p)
        except SyntaxError:
            continue
        for no in ast.walk(arv):
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcoes.add(no.name)
            elif isinstance(no, ast.Assign):
                for a in no.targets:
                    if isinstance(a, ast.Name):
                        constantes.add(a.id)
            elif isinstance(no, ast.AnnAssign) and isinstance(no.target,
                                                              ast.Name):
                constantes.add(no.target.id)
    return funcoes, constantes


def skill_existe(nome):
    """Uma skill ou subagente com este nome, aqui ou no perfil global.

    Procura nos três sítios de onde o Claude Code as carrega. Foi a
    ausência desta pergunta que deixou o `task-observer` — que não
    existia em nenhum deles — a mandar em todas as sessões durante
    semanas.
    """
    for pasta in (os.path.join(RAIZ, ".claude", "skills"),
                  os.path.join(RAIZ, ".claude", "agents"),
                  os.path.expanduser("~/.claude/skills"),
                  os.path.expanduser("~/.claude/agents")):
        if not os.path.isdir(pasta):
            continue
        for entrada in os.listdir(pasta):
            if entrada == nome or entrada == nome + ".md":
                return True
    return False


def o_que_o_flask_tem():
    sys.path.insert(0, RAIZ)
    import radar
    return {r.rule for r in radar.app.url_map.iter_rules()}, radar


def bandeiras_do_programa():
    """As do `radar.py` E as das skills e ferramentas.

    À primeira versão só olhei para o radar.py, e o relatório acusou o
    `--sem-modelo` de não existir. Existe — é do `ensaio-de-leitura`.
    **Quando a ferramenta discorda da realidade, é a ferramenta que se
    confere primeiro.**
    """
    bandeiras = set()
    fontes = [os.path.join(RAIZ, "radar.py")]
    for pasta in (".claude/skills", "ferramentas", ".claude/hooks"):
        for raiz, _, ficheiros in os.walk(os.path.join(RAIZ, pasta)):
            fontes += [os.path.join(raiz, f) for f in ficheiros
                       if f.endswith(".py")]
    for p in fontes:
        if not os.path.exists(p):
            continue
        t = io.open(p, encoding="utf-8", errors="ignore").read()
        bandeiras |= set(re.findall(r'"(--[a-z-]+)"', t))
        bandeiras |= set(re.findall(r"'(--[a-z-]+)'", t))
        bandeiras |= set(re.findall(r"\[(--[a-z-]+)\]", t))
    return bandeiras


def seccoes_de(caminho):
    if not os.path.exists(caminho):
        return set()
    return {m.group(1) for m in re.finditer(
        r"^#{2,4}\s+(\d+(?:\.\d+)?)[.\s]",
        io.open(caminho, encoding="utf-8").read(), re.M)}


def valida():
    refs = refs_dos_docs()
    funcoes, constantes = o_que_o_codigo_tem()
    rotas, radar = o_que_o_flask_tem()
    bandeiras = bandeiras_do_programa()
    faltam = []

    def erro(tipo, tok, onde, porque):
        if tok in ISENTOS:
            return
        faltam.append((tipo, tok, onde, porque))

    for tok, onde in refs["funcao"].items():
        if tok[:-2] in NAO_SAO_NOSSAS:
            continue
        if tok[:-2] not in funcoes:
            erro("função", tok, onde, "não está definida em nenhum módulo")
    # O AST não chega para os nomes em MAIÚSCULAS: `ARV_SEL` e
    # `GUARDAR_JS` são variáveis **JavaScript** dentro das strings do
    # painel, e `LIMIAR` ou `FOLGA` são palavras portuguesas escritas
    # em capitais dentro de um comentário. Nenhuma delas é uma
    # atribuição Python, e todas são referências legítimas. Por isso a
    # pergunta é a mais larga que serve: **este nome aparece em algum
    # ficheiro de código?** Se não aparece em lado nenhum, é fantasma.
    texto_do_codigo = "\n".join(
        io.open(p, encoding="utf-8", errors="ignore").read()
        for p in _fontes())
    for tok, onde in refs["constante"].items():
        if (tok in constantes or hasattr(radar, tok)
                or re.search(r"\b%s\b" % re.escape(tok), texto_do_codigo)):
            continue
        erro("constante", tok, onde, "não aparece em ficheiro de código nenhum")
    for tok, onde in refs["bandeira"].items():
        if tok not in bandeiras:
            erro("bandeira", tok, onde, "o programa não a aceita")
    # As variáveis de CSS já foram separadas das bandeiras por EXISTIREM
    # (ver `variaveis_css()`), e por isso esta volta nunca acusa nada.
    # Fica escrita à mesma: sem ela, um `refs["variavel"]` que deixasse
    # de ser preenchido passava despercebido, e é exactamente assim que
    # uma verificação morre em silêncio.
    for tok, onde in refs["variavel"].items():
        if tok not in variaveis_css():
            erro("variavel", tok, onde, "nenhuma folha a define")
    for tok, onde in refs["rota"].items():
        base = tok.split("?")[0].rstrip("/") or "/"
        if base in rotas or tok in rotas:
            continue
        molde = re.sub(r"<[^>]+>", "<X>", base)
        if any(re.sub(r"<[^>]+>", "<X>", r.rstrip("/") or "/") == molde
               for r in rotas):
            continue
        erro("rota", tok, onde, "não está registada no Flask")
    for tok, onde in refs["ficheiro"].items():
        if not any(os.path.exists(os.path.join(RAIZ, d, tok))
                   for d in ("", "docs", "ferramentas", ".claude/hooks",
                             "docs/historico", "docs/diario")):
            erro("ficheiro", tok, onde, "não existe no disco")
    for tok, onde in refs["pasta"].items():
        if not os.path.isdir(os.path.join(RAIZ, tok.rstrip("/"))):
            erro("pasta", tok, onde, "não existe no disco")
    for tok, onde in refs["skill"].items():
        if not skill_existe(tok):
            erro("skill", tok, onde,
                 "não existe em .claude/skills, .claude/agents nem "
                 "~/.claude/skills")
    for tok, onde in refs["caminho_de_casa"].items():
        if not os.path.exists(os.path.expanduser(tok)):
            erro("caminho", tok, onde, "não existe")
    for tok, onde in refs["seccao"].items():
        alvo, sec = tok.split("§")
        for base in ("", "docs"):
            caminho = os.path.join(RAIZ, base, alvo)
            if os.path.exists(caminho):
                if sec not in seccoes_de(caminho):
                    erro("secção", tok, onde, "%s não tem §%s" % (alvo, sec))
                break
    return faltam, refs


def main():
    faltam, refs = valida()
    total = sum(len(v) for v in refs.values())
    if "--curto" in sys.argv:
        print("%d referências distintas, %d por resolver"
              % (total, len(faltam)))
        return 1 if faltam else 0
    print("=" * 74)
    print("O QUE A DOCUMENTAÇÃO AFIRMA E NÃO EXISTE")
    print("=" * 74)
    if not faltam:
        print("\nnada. %d referências distintas, todas conferidas." % total)
    for tipo, tok, onde, porque in sorted(faltam):
        print("\n%-10s `%s` — %s" % (tipo, tok, porque))
        for f, n in onde[:6]:
            print("            %s:%d" % (f, n))
        if len(onde) > 6:
            print("            (+%d)" % (len(onde) - 6))
    print("\n%d referências distintas conferidas, %d por resolver."
          % (total, len(faltam)))
    return 1 if faltam else 0


if __name__ == "__main__":
    sys.exit(main())
