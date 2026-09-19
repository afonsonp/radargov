"""Junta todos os ecrãs do painel num ficheiro HTML só, para se verem
lado a lado.

Não é um screenshot: é o HTML verdadeiro de cada rota, com o CSS e as
fontes embutidos uma vez. Abre-se offline, e o que se vê é o que o
painel serve.
"""
import base64
import os
import re
import sys
from datetime import datetime

# A raiz do projecto e o pai desta pasta: o script corre de qualquer
# sitio, e o `radar` importa-se de la.
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)
import radar  # noqa: E402

SAIDA = sys.argv[1] if len(sys.argv) > 1 else "ecrans-radargov.html"

c = radar.app.test_client()


def uma(sql, omissao=""):
    with radar.liga() as lig:
        r = lig.execute(sql).fetchone()
    return (r[0] if r else omissao)


REF = uma("SELECT ref FROM propostas WHERE ref IS NOT NULL "
          "ORDER BY id DESC LIMIT 1") or uma(
    "SELECT ref FROM anuncios ORDER BY rowid DESC LIMIT 1")
PROP = uma("SELECT id FROM propostas ORDER BY id DESC LIMIT 1", 0)
ENT = uma("SELECT entidade_chave FROM propostas "
          "WHERE COALESCE(entidade_chave,'')!='' ORDER BY id DESC LIMIT 1")

ECRAS = [
    ("A abertura", [
        ("Hoje", "/", "o estado do negócio e o que há para fazer"),
        ("Hoje · um dia escolhido na fita", "/?dia=", "a lista muda para esse dia"),
        ("Hoje · filtrado por pessoa", "/?quem=", "aqui, as que não têm dono"),
    ]),
    ("O negócio", [
        ("Ponto de situação · Negócio", "/situacao", "com período e comparação"),
        ("Ponto de situação · Triagem", "/situacao?ver=triagem", "o funil"),
        ("Ponto de situação · Por área CPV", "/situacao?ver=cpv", "taxa por divisão"),
        ("Ponto de situação · este mês", "/situacao?periodo=mes", "outro período"),
    ]),
    ("Concursos", [
        ("Lista · Por ver", "/concursos", "a entrada da escada — anúncios"),
        ("Lista · Por analisar", "/concursos?estado=analisar", "uma ranhura da empresa — propostas"),
        ("Lista · Ganho", "/concursos?estado=ganho", ""),
        ("Lista · com filtro", "/concursos?estado=porver&q=software", "o painel de filtros"),
        ("Calendário", "/calendario", "os prazos por dia, seis semanas"),
    ]),
    ("As fichas", [
        ("Ficha do anúncio", "/anuncio/%s" % REF, "em composição de dossier"),
        ("Ficha da proposta", "/proposta/%s" % PROP,
         "uma proposta COM anúncio vai para a ficha do anúncio; a ficha "
         "própria serve as que não têm — e hoje não há nenhuma"),
        ("Proposta nova", "/proposta/nova", "consulta prévia, ajuste directo, convite"),
    ]),
    ("Mercado", [
        ("Contratos", "/contratos", "o corpus do Portal BASE"),
        ("Contratos · por fim estimado", "/contratos?ver=fim", "o que está a acabar"),
        ("Resumo do mercado", "/contratos/resumo", "seis agregações"),
    ]),
    ("Entidades", [
        ("Entidades · com quem trabalhamos", "/entidades", "cinco abas, uma tabela"),
        ("Entidades · clientes que mais compram", "/entidades?ver=clientes", ""),
        ("Entidades · contratos a acabar", "/entidades?ver=acabar", "90 dias"),
        ("Ficha da entidade", "/entidade/%s" % ENT, "seis factos, duas colunas"),
    ]),
    ("Configurações", [
        ("Configurações · Conta", "/configuracoes",
         "nove secções; a raiz abre na primeira"),
        ("· Interesse", "/configuracoes/interesse", "os CPV que a empresa trabalha"),
        ("· Alertas", "/configuracoes/alertas", "filtros, entidades, o resumo"),
        ("· Importar", "/configuracoes/importar", "o registo da empresa, pelo Excel"),
        ("· Indicadores", "/configuracoes/indicadores", "a saúde da máquina"),
        ("· Capturas", "/configuracoes/capturas", "os dois pedidos cURL ao DR"),
        ("· Recolha", "/configuracoes/recolha", "horas, janelas, a Vortal"),
        ("· Leitura das peças", "/configuracoes/leitura", "fornecedor, modelo, chaves"),
        ("· Cópias", "/configuracoes/copias", "a cópia diária e a triagem no git"),
    ]),
    ("Fora da barra", [
        ("Entrar", "/entrar", "a porta"),
        ("Adiar as atrasadas", "/tarefas/adiar", "pergunta antes: não há desfazer"),
        ("Amostra do desenho", "/amostra", "os componentes todos num sítio"),
    ]),
]

# --- as fontes, embutidas uma vez -------------------------------------
fontes = []
for nome, peso in (("plex-sans.woff2", "100 700"),
                   ("plex-mono-400.woff2", "400"),
                   ("plex-mono-600.woff2", "600")):
    caminho = os.path.join("tipo", nome)
    if not os.path.exists(caminho):
        continue
    with open(caminho, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    familia = "Plex Sans" if "sans" in nome else "Plex Mono"
    fontes.append("@font-face{font-family:'%s';src:url(data:font/woff2;"
                  "base64,%s) format('woff2');font-weight:%s;"
                  "font-display:swap}" % (familia, b64, peso))

# O CSS da aplicação, sem os @font-face dele (que apontam para /tipo/).
css = re.sub(r"@font-face\{[^}]*\}", "", radar.CSS_TUDO)

CORPO = re.compile(r"<body[^>]*>(.*)</body>", re.S | re.I)
SCRIPTS = re.compile(r"<script\b.*?</script>", re.S | re.I)


def corpo_de(caminho):
    # `follow_redirects`: duas rotas desta lista redireccionam de
    # propósito -- o `/configuracoes` para a primeira secção, e o
    # `/proposta/<id>` de uma proposta COM anúncio para a ficha do
    # anúncio (a ficha própria serve as que não têm). Mostra-se o que
    # elas mostram, e o rótulo diz para onde foram.
    r = c.get(caminho, follow_redirects=True)
    html = r.get_data(as_text=True)
    m = CORPO.search(html)
    dentro = m.group(1) if m else html
    # Os <script> saem: correriam trinta e quatro vezes na mesma página,
    # e procuram elementos por id que aqui deixam de ser únicos.
    #
    # Os **id ficam**. São duplicados entre ecrãs, o que é HTML inválido
    # -- mas o CSS da aplicação tem quatro selectores por id
    # (`#arvore-corpo`, `#arvore-contagem`, `#filtro-cpv-excl`,
    # `#mercado`), e tirá-los deixava a árvore de CPV por pintar. Um
    # `#id` em CSS casa com TODOS os elementos que o tenham, e sem JS
    # não há mais nada a depender de serem únicos: o que se perde é uma
    # âncora saltar para o primeiro ecrã em vez do seu, e isto é para
    # ver, não para navegar.
    dentro = SCRIPTS.sub("", dentro)
    return r.status_code, dentro


partes, indice, n = [], [], 0
for grupo, ecras in ECRAS:
    indice.append("<li class='g'>%s</li>" % grupo)
    partes.append("<h2 class='grupo'>%s</h2>" % grupo)
    for titulo, caminho, nota in ecras:
        n += 1
        codigo, dentro = corpo_de(caminho)
        marca = "e%d" % n
        indice.append("<li><a href='#%s'>%s</a></li>" % (marca, titulo))
        partes.append(
            "<section class='ecra' id='%s'>"
            "<div class='cab'><b>%s</b><code>%s</code>"
            "<span class='nota'>%s</span>"
            "<span class='cod %s'>%d</span></div>"
            "<div class='janela'><div class='pagina'>%s</div></div>"
            "</section>"
            % (marca, titulo, caminho or "/", nota,
               "ok" if codigo == 200 else "mau", codigo, dentro))
        print("  %-42s %s" % (caminho, codigo))

FOLHA = """
:root{color-scheme:light}
html,body{margin:0;background:#e9ebef;
 font:400 13px/1.5 'Plex Sans',system-ui,sans-serif;color:#111418}
.topo-doc{position:sticky;top:0;z-index:50;background:#111418;color:#fff;
 padding:14px 26px;display:flex;gap:18px;align-items:baseline;flex-wrap:wrap}
.topo-doc h1{margin:0;font:680 19px/1.2 'Plex Sans',sans-serif;
 letter-spacing:-.4px}
.topo-doc span{font-size:12px;color:#9aa3b0}
.corpo-doc{display:grid;grid-template-columns:230px minmax(0,1fr);
 align-items:start}
.indice{position:sticky;top:52px;max-height:calc(100vh - 52px);
 overflow:auto;padding:18px 14px 40px;background:#f5f6f8;
 border-right:1px solid #d7dbe1}
.indice ul{list-style:none;margin:0;padding:0}
.indice li{margin:0 0 3px}
.indice li.g{margin:16px 0 6px;font:600 11px/1 'Plex Sans',sans-serif;
 text-transform:uppercase;letter-spacing:.06em;color:#5a626d}
.indice a{color:#343a42;text-decoration:none;font-size:12.5px;
 display:block;padding:3px 6px;border-radius:5px}
.indice a:hover{background:#e3e6eb;color:#1b5fc1}
/* `display:block` à força: o CSS da aplicação tem `main{display:flex;
   flex-direction:column}`, e a folha é um <main>. */
.folha{display:block;padding:22px 26px 80px;min-width:0}
h2.grupo{margin:34px 0 12px;font:600 15px/1 'Plex Sans',sans-serif;
 letter-spacing:.02em;color:#4a515b;text-transform:uppercase;
 border-bottom:1px solid #d7dbe1;padding-bottom:8px}
h2.grupo:first-child{margin-top:0}
.ecra{margin:0 0 26px;background:#fff;border:1px solid #d7dbe1;
 border-radius:10px;overflow:hidden;
 box-shadow:0 1px 3px rgba(17,20,24,.06)}
.ecra .cab{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;
 padding:10px 14px;background:#f5f6f8;border-bottom:1px solid #e3e6eb}
.ecra .cab b{font:600 13.5px/1 'Plex Sans',sans-serif}
.ecra .cab code{font:500 11.5px/1 'Plex Mono',monospace;color:#1b5fc1;
 background:#e8f0fd;padding:3px 6px;border-radius:4px}
.ecra .cab .nota{font-size:11.5px;color:#5a626d}
.ecra .cab .cod{margin-left:auto;font:600 11px/1 'Plex Mono',monospace;
 padding:3px 7px;border-radius:4px;background:#e4f2ea;color:#12704a}
.ecra .cab .cod.mau{background:#fdeae8;color:#b3261e}
/* A janela: cada ecrã rola dentro de si, para a página inteira não
   ficar com trinta metros de altura. */
.janela{height:620px;overflow:auto;background:#f5f6f8;
 border-top:1px solid #eef0f4;resize:vertical}
.pagina{min-height:100%}
/* O `.app` da aplicação assume o ecrã inteiro; aqui assume a janela, e
   o que é `sticky` deixa de o ser -- dois níveis de `sticky` dentro de
   uma caixa que rola tapam-se um ao outro. */
.janela .app{min-height:0}
.janela .barra,.janela .topo,.janela .am-topo{position:static}
@media (max-width:900px){
 .corpo-doc{grid-template-columns:minmax(0,1fr)}
 .indice{position:static;max-height:none;border-right:0;
  border-bottom:1px solid #d7dbe1}
}
"""

doc = ("<!doctype html><html lang='pt' data-pele='novo' data-tipo='plex'>"
       "<head><meta charset='utf-8'>"
       "<meta name='viewport' content='width=device-width,initial-scale=1'>"
       "<title>RadarGov &mdash; todos os ecrãs</title>"
       "<style>%s</style><style>%s</style><style>%s</style></head><body>"
       "<div class='topo-doc'><h1>RadarGov &mdash; todos os ecrãs</h1>"
       "<span>%d ecrãs &middot; v1.8.0 &middot; %s &middot; o HTML "
       "verdadeiro de cada rota, com o CSS e as fontes embutidos. "
       "Cada janela rola, e arrasta-se pelo canto para crescer.</span></div>"
       "<div class='corpo-doc'><nav class='indice'><ul>%s</ul></nav>"
       "<main class='folha'>%s</main></div></body></html>"
       % ("".join(fontes), css, FOLHA, n,
          datetime.now().strftime("%d/%m/%Y"),
          "".join(indice), "".join(partes)))

with open(SAIDA, "w", encoding="utf-8") as f:
    f.write(doc)
print("\n%s ecrãs · %.1f MB · %s" % (n, os.path.getsize(SAIDA) / 1e6, SAIDA))
