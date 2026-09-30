"""Junta todos os ecrãs do painel num ficheiro HTML só, para se verem
lado a lado.

Não é um screenshot: é o HTML verdadeiro de cada rota, com o CSS e as
fontes embutidos uma vez. Abre-se offline, e o que se vê é o que o
painel serve.

    python ferramentas/ecrans.py [SAIDA] [--empresa N]

Os ecrãs da empresa vêem-se como o GESTOR dela (a primeira empresa, ou
a `--empresa N`); os da plataforma, como o dono. Desde o multi-empresa
(23/09/2026) o acesso local entra como o dono, que não tem empresa, e o
script rebentava com «no such table: propostas» (FERR-E, 30/09/2026).
Nenhuma sessão se grava: a conta de cada pedido vem do
`utilizador_da_sessao()` deste script, e não da tabela `sessoes`.
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

argumentos = [a for a in sys.argv[1:] if not a.startswith("--empresa")]
SAIDA = argumentos[0] if argumentos else "ecrans-radargov.html"
pedida = next((a.split("=", 1)[1] for a in sys.argv[1:]
               if a.startswith("--empresa=")), "")
if "--empresa" in sys.argv[1:-1]:
    pedida = sys.argv[sys.argv.index("--empresa") + 1]

EMPRESAS = radar.empresas_existentes()
if not EMPRESAS:
    sys.exit("Não há empresas: os ecrãs de uma empresa precisam de uma.")
EMPRESA = int(pedida) if pedida else EMPRESAS[0]
if EMPRESA not in EMPRESAS:
    sys.exit("A empresa %s não existe; há %s." % (EMPRESA, EMPRESAS))


def uma(sql, omissao="", corpus=False):
    """O primeiro valor de uma consulta, lida na empresa escolhida."""
    try:
        with radar.com_empresa(EMPRESA):
            ligar = radar.liga_corpus if corpus else radar.liga
            with ligar() as lig:
                r = lig.execute(sql).fetchone()
    except Exception:           # sem corpus, ou uma base mais antiga
        return omissao
    return (r[0] if r else omissao) or omissao


def conta(onde, omissao):
    """A conta de quem vê: a verdadeira, lida só, ou uma inventada."""
    with radar.liga() as lig:
        r = lig.execute("SELECT id, email, nome, papel, empresa_id, dono, "
                        "aspecto FROM utilizadores WHERE " + onde
                        + " ORDER BY id LIMIT 1").fetchone()
    base = dict(omissao, ver_como=None)
    return dict(base, **{k: r[k] for k in r.keys()}) if r else base


GESTOR = conta("papel='admin' AND empresa_id=%d AND COALESCE(dono,0)=0"
               % EMPRESA,
               {"id": 0, "email": "gestor", "nome": "Gestor", "papel": "admin",
                "empresa_id": EMPRESA, "dono": 0, "aspecto": "claro"})
DONO = conta("dono=1", {"id": 0, "email": "dono", "nome": "Dono",
                        "papel": "admin", "empresa_id": None, "dono": 1,
                        "aspecto": "claro"})
# O tema claro, seja qual for o da pessoa: a colagem é uma folha só.
GESTOR["aspecto"] = DONO["aspecto"] = "claro"
radar.contas.utilizador_da_sessao = (
    lambda c, token, agora=None: dict({"gestor": GESTOR, "dono": DONO}[token])
    if token in ("gestor", "dono") else None)

c = radar.app.test_client()
REF = uma("SELECT ref FROM propostas WHERE COALESCE(ref,'')!='' "
          "ORDER BY id DESC LIMIT 1") or uma(
    "SELECT ref FROM anuncios ORDER BY rowid DESC LIMIT 1")
# A ficha própria é a das propostas SEM anúncio: uma com anúncio
# redirecciona para a ficha dele, que já está na lista.
PROP = uma("SELECT id FROM propostas WHERE COALESCE(ref,'')='' "
           "ORDER BY id DESC LIMIT 1", 0)
# A entidade: uma das propostas da empresa, e senão a que mais compra no
# corpus (na LATD não havia nenhuma, e a ficha dava 404).
ENT = uma("SELECT entidade_chave FROM propostas "
          "WHERE COALESCE(entidade_chave,'')!='' ORDER BY id DESC LIMIT 1") or uma(
    "SELECT chave FROM entidades ORDER BY compra DESC LIMIT 1", corpus=True)

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
        ("Lista · Por ver", "/concursos", "a entrada — anúncios"),
        ("Lista · com filtro", "/concursos?estado=porver&q=software", "o painel de filtros"),
        ("Calendário", "/calendario", "os prazos por dia, seis semanas"),
    ]),
    ("Propostas", [
        ("Propostas · Por analisar", "/propostas?estado=analisar", "as oito fases da empresa"),
        ("Propostas · Ganho", "/propostas?estado=ganho", ""),
        ("Proposta nova", "/proposta/nova", "consulta prévia, ajuste directo, convite"),
    ]),
    ("As fichas", [
        ("Ficha do anúncio", "/anuncio/%s" % REF, "o anúncio e a proposta"),
    ] + ([("Ficha da proposta sem anúncio", "/proposta/%s" % PROP,
           "a das propostas que não vêm do DR")] if PROP else [])),
    ("Mercado", [
        ("Contratos", "/contratos", "o corpus do Portal BASE"),
        ("Contratos · por fim estimado", "/contratos?ver=fim", "o que está a acabar"),
        ("Resumo do mercado", "/contratos/resumo", "as agregações"),
    ]),
    ("Entidades", [
        ("Entidades · com quem trabalhamos", "/entidades", "cinco abas, uma tabela"),
        ("Entidades · clientes que mais compram", "/entidades?ver=clientes", ""),
        ("Entidades · contratos a acabar", "/entidades?ver=acabar", "90 dias"),
    ] + ([("Ficha da entidade", "/entidade/%s" % ENT, "seis factos, duas colunas")]
         if ENT else [])),
    ("Configurações", [
        ("Configurações · Conta", "/configuracoes",
         "dez secções; a raiz abre na primeira"),
        ("· Perfil da empresa", "/configuracoes/interesse",
         "os CPV, os distritos e o valor que a empresa trabalha"),
        ("· Alertas", "/configuracoes/alertas", "filtros, entidades, o resumo"),
        ("· Importar", "/configuracoes/importar", "o registo da empresa, pelo Excel"),
        ("· Documentos da empresa", "/configuracoes/documentos",
         "o alvará, as certidões, com a validade"),
    ]),
    ("Fora da barra", [
        ("Ajuda", "/ajuda", "como funciona, e o glossário"),
        ("Entrar", "/entrar", "a porta"),
        ("Adiar as atrasadas", "/tarefas/adiar", "pergunta antes: não há desfazer"),
    ]),
    ("A plataforma (o dono)", [
        ("Plataforma", "/plataforma", "semáforos, a tratar hoje, empresas"),
        ("Pedidos de acesso", "/pedidos-de-acesso", "os por decidir primeiro"),
        ("· Indicadores", "/configuracoes/indicadores", "a saúde da máquina"),
        ("· Capturas", "/configuracoes/capturas", "os dois pedidos cURL ao DR"),
        ("· Recolha", "/configuracoes/recolha", "horas, janelas, a Vortal"),
        ("· Leitura das peças", "/configuracoes/leitura", "fornecedor, modelo, chaves"),
        ("· Cópias", "/configuracoes/copias", "a cópia diária"),
    ]),
]
DO_DONO = {"A plataforma (o dono)"}
SEM_SESSAO = {"/entrar"}

# --- as fontes da aplicação, embutidas uma vez ------------------------
# As `@font-face` do CSS apontam para /tipo/<nome>; aqui cada uma leva o
# ficheiro dentro. Eram as Plex, que saíram da aplicação a 21/09/2026.


def embutida(m):
    caminho = os.path.join("tipo", m.group(1))
    if not os.path.exists(caminho):
        return m.group(0)
    with open(caminho, "rb") as f:
        return ("url(data:font/woff2;base64,%s)"
                % base64.b64encode(f.read()).decode("ascii"))


css = re.sub(r'url\("?/tipo/([\w.-]+)"?\)', embutida, radar.CSS_TUDO)

CORPO = re.compile(r"<body[^>]*>(.*)</body>", re.S | re.I)
SCRIPTS = re.compile(r"<script\b.*?</script>", re.S | re.I)


def corpo_de(caminho, quem):
    # `follow_redirects`: o `/configuracoes` vai para a primeira secção.
    # Mostra-se o que a rota mostra, e o rótulo diz para onde foi.
    if quem:
        c.set_cookie("sessao", quem)
    else:
        c.delete_cookie("sessao")
    r = c.get(caminho, follow_redirects=True)
    html = r.get_data(as_text=True)
    m = CORPO.search(html)
    dentro = m.group(1) if m else html
    # Os <script> saem: correriam dezenas de vezes na mesma página, e
    # procuram elementos por id que aqui deixam de ser únicos.
    #
    # Os **id ficam**. São duplicados entre ecrãs, o que é HTML inválido
    # -- mas o CSS da aplicação tem selectores por id (`#arvore-corpo`,
    # `#filtro-cpv-excl`, `#mercado`), e tirá-los deixava a árvore de CPV
    # por pintar. Sem JS não há mais nada a depender de serem únicos: o
    # que se perde é uma âncora saltar para o primeiro ecrã em vez do seu.
    dentro = SCRIPTS.sub("", dentro)
    return r.status_code, dentro


partes, indice, n = [], [], 0
for grupo, ecras in ECRAS:
    indice.append("<li class='g'>%s</li>" % grupo)
    partes.append("<h2 class='grupo'>%s</h2>" % grupo)
    for titulo, caminho, nota in ecras:
        n += 1
        quem = ("" if caminho in SEM_SESSAO else
                "dono" if grupo in DO_DONO else "gestor")
        codigo, dentro = corpo_de(caminho, quem)
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

# A letra da colagem vai SÓ no que é dela (a barra do topo, o índice e os
# cabeçalhos): no `html` punha a raiz a 13 px, e tudo o que a aplicação
# mede em `rem` saía a 81 % -- uma hierarquia que a aplicação não tem
# (UX-ICONES-DICAS-PESOS, nota inicial). A raiz fica nos 16 px do browser.
FOLHA = """
:root{color-scheme:light}
html,body{margin:0;background:#e9ebef}
.topo-doc,.indice,h2.grupo,.ecra .cab{font:400 13px/1.5 system-ui,sans-serif;color:#111418}
.topo-doc{position:sticky;top:0;z-index:50;background:#111418;color:#fff;
 padding:14px 26px;display:flex;gap:18px;align-items:baseline;flex-wrap:wrap}
.topo-doc h1{margin:0;font:600 19px/1.2 system-ui,sans-serif}
.topo-doc span{font-size:12px;color:#9aa3b0}
.corpo-doc{display:grid;grid-template-columns:230px minmax(0,1fr);
 align-items:start}
.indice{position:sticky;top:52px;max-height:calc(100vh - 52px);
 overflow:auto;padding:18px 14px 40px;background:#f5f6f8;
 border-right:1px solid #d7dbe1}
.indice ul{list-style:none;margin:0;padding:0}
.indice li{margin:0 0 3px}
.indice li.g{margin:16px 0 6px;font:600 11px/1 system-ui,sans-serif;
 text-transform:uppercase;letter-spacing:.06em;color:#5a626d}
.indice a{color:#343a42;text-decoration:none;font-size:12.5px;
 display:block;padding:3px 6px;border-radius:5px}
.indice a:hover{background:#e3e6eb;color:#004682}
/* `display:block` à força: o CSS da aplicação tem `main{display:flex;
   flex-direction:column}`, e a folha é um <main>. */
.folha{display:block;padding:22px 26px 80px;min-width:0}
h2.grupo{margin:34px 0 12px;font:600 15px/1 system-ui,sans-serif;
 letter-spacing:.02em;color:#4a515b;text-transform:uppercase;
 border-bottom:1px solid #d7dbe1;padding-bottom:8px}
h2.grupo:first-child{margin-top:0}
.ecra{margin:0 0 26px;background:#fff;border:1px solid #d7dbe1;
 border-radius:10px;overflow:hidden;
 box-shadow:0 1px 3px rgba(17,20,24,.06)}
.ecra .cab{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;
 padding:10px 14px;background:#f5f6f8;border-bottom:1px solid #e3e6eb}
.ecra .cab b{font:600 13.5px/1 system-ui,sans-serif}
.ecra .cab code{font:500 11.5px/1 ui-monospace,monospace;color:#004682;
 background:#e1ecf6;padding:3px 6px;border-radius:4px}
.ecra .cab .nota{font-size:11.5px;color:#5a626d}
.ecra .cab .cod{margin-left:auto;font:600 11px/1 ui-monospace,monospace;
 padding:3px 7px;border-radius:4px;background:#e4f2ea;color:#12704a}
.ecra .cab .cod.mau{background:#fdeae8;color:#b3261e}
/* A janela: cada ecrã rola dentro de si, para a página inteira não
   ficar com trinta metros de altura. A letra dela é a do corpo da
   aplicação (o `body` do BASE), que aqui não chega. */
.janela{height:620px;overflow:auto;background:var(--surface);
 border-top:1px solid #eef0f4;resize:vertical;
 font:400 1rem/1.5 var(--font-sans);color:var(--ink)}
.pagina{min-height:100%}
/* O que é `sticky` ou fixo na aplicação deixa de o ser: dois níveis de
   `sticky` dentro de uma caixa que rola tapam-se um ao outro. */
.janela .mg-topbar,.janela .topo,.janela .barra-baixo{position:static}
@media (max-width:900px){
 .corpo-doc{grid-template-columns:minmax(0,1fr)}
 .indice{position:static;max-height:none;border-right:0;
  border-bottom:1px solid #d7dbe1}
}
"""

doc = ("<!doctype html><html lang='pt' data-pele='novo' data-theme='claro'>"
       "<head><meta charset='utf-8'>"
       "<meta name='viewport' content='width=device-width,initial-scale=1'>"
       "<title>Mira Gov &mdash; todos os ecrãs</title>"
       "<style>%s</style><style>%s</style></head><body>"
       "<div class='topo-doc'><h1>Mira Gov &mdash; todos os ecrãs</h1>"
       "<span>%d ecrãs &middot; empresa %d, vista pelo gestor &middot; %s "
       "&middot; o HTML verdadeiro de cada rota, com o CSS e as fontes "
       "embutidos. Cada janela rola, e arrasta-se pelo canto para "
       "crescer.</span></div>"
       "<div class='corpo-doc'><nav class='indice'><ul>%s</ul></nav>"
       "<main class='folha'>%s</main></div></body></html>"
       % (css, FOLHA, n, EMPRESA, datetime.now().strftime("%d/%m/%Y"),
          "".join(indice), "".join(partes)))

with open(SAIDA, "w", encoding="utf-8") as f:
    f.write(doc)
print("\n%s ecrãs · %.1f MB · %s" % (n, os.path.getsize(SAIDA) / 1e6, SAIDA))
