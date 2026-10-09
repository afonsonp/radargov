"""O portão da igualdade (D1, fase 0, 9/10/2026): prova que o HTML que o
painel serve não mudou numa letra.

O D1 tira o HTML do `radar.py` para moldes, e a regra dele é que nada
muda ao que o browser recebe. Isto mede-o em vez de o prometer: pede
todas as rotas GET, com quatro perfis, sobre a empresa inventada do
`ferramentas/demo.py` (base temporária; nada sai das bases verdadeiras),
grava cada resposta, e compara duas gravações -- a do `master` contra a
do ramo.

    python ferramentas/igual.py --gravar PASTA [--codigo DIR]
    python ferramentas/igual.py --comparar PASTA_A PASTA_B

`--codigo` é a pasta do código a medir (por omissão, a deste ficheiro):
é assim que se grava o `master` com este script, que ele ainda não tem.
Sai com 1 se houver diferenças, e mostra-as.

O teto: só vê os estados que a empresa inventada tem. O ensaio sobre a
cópia das bases verdadeiras é o outro portão.
"""
import hashlib
import itertools
import os
import re
import sys
from datetime import date

# Os perfis: quem pede. O «sem sessão» vem de fora (o cabeçalho do
# túnel), senão o pedido era local e entrava como o dono.
PERFIS = ("fora", "dono", "gestor", "membro")

# As rotas com parâmetros não se adivinham: um exemplo para cada uma. A
# que não tiver exemplo é dita no fim, e não saltada em silêncio.
# `{...}` preenche-se com o que a base inventada tem.
EXEMPLOS = {
    "/anuncio/<path:ref>": ["/anuncio/9104/2026", "/anuncio/9101/2026",
                            "/anuncio/9104/2026?peca=Caderno de Encargos.pdf"],
    "/convite/<codigo>": ["/convite/nao-existe"],
    "/demo/<int:n>": [],          # gerado pelo demo.py, fora do git
    "/documento/<path:ref>/<nome>": ["/documento/9104/2026/nao-existe.pdf"],
    "/entidade/<path:chave>": ["/entidade/{pombal}",
                               "/entidade/{pombal}?aba=contratos"],
    "/estilo/<etiqueta>.css": ["/estilo/{etiqueta}.css"],
    "/peca-pagina/<path:ref>/<nome>/<int:n>.png":
        ["/peca-pagina/9104/2026/Caderno de Encargos.pdf/1.png"],
    "/peca/<path:ref>/<nome>": ["/peca/9104/2026/Caderno de Encargos.pdf"],
    "/pecas-zip/<path:ref>": [],          # o zip leva as horas de agora
    "/pedido/<codigo>": ["/pedido/nao-existe"],
    "/pedidos-de-acesso/<int:id_>/aceitar": ["/pedidos-de-acesso/1/aceitar"],
    "/plataforma/empresa/<int:id_>": ["/plataforma/empresa/{empresa}"],
    "/plataforma/empresa/<int:id_>/actividade":
        ["/plataforma/empresa/{empresa}/actividade"],
    "/plataforma/sugestoes/<int:id_>/captura":
        ["/plataforma/sugestoes/1/captura"],
    "/procedimento/<path:ref>": ["/procedimento/9104/2026"],
    "/proposta/<int:id_>": ["/proposta/{proposta}"],
    "/repor/<codigo>": ["/repor/nao-existe"],
    "/static/<path:filename>": [],        # o Flask serve-o, não o radar
    "/tipo/<nome>": ["/tipo/{tipo}"],
}

# As vistas que a mesma rota tem pela pergunta (as do `ecrans.py`, e as
# abas que mudam o ecrã).
VARIANTES = [
    "/?dia=", "/?quem=", "/?feitas=esconder",
    "/situacao?ver=triagem", "/situacao?ver=cpv", "/situacao?periodo=mes",
    "/situacao?periodo=tudo",
    "/concursos?estado=porver&q=climatização", "/concursos?estado=urgente",
    "/propostas?estado=analisar", "/propostas?estado=proposta",
    "/propostas?estado=submetido", "/propostas?estado=ganho",
    "/propostas?ver=tabela", "/propostas?ver=calendario",
    "/contratos?ver=fim", "/entidades?ver=acabar", "/entidades?ver=clientes",
    "/pesquisa?q=climatização",
]

# O que muda de pedido para pedido sem ser o HTML: o token do CSRF (vem
# de uma chave nova em cada base temporária) e o identificador de envio
# (G1, aleatório em cada formulário). Mais nada se normaliza sem uma
# razão escrita aqui -- cada linha a mais é um sítio onde uma diferença
# verdadeira se esconde.
NORMALIZAR = [
    (re.compile(r"(name=['\"]csrf['\"] value=['\"])[^'\"]*"), r"\1·"),
    (re.compile(r"(<meta name=['\"]csrf['\"] content=['\"])[^'\"]*"), r"\1·"),
    (re.compile(r"(name=['\"]envio['\"] value=['\"])[0-9a-f]*"), r"\1·"),
    # o identificador da visita do beacon do site (`registar_visita()`)
    (re.compile(r'(\{var V=")[0-9a-f]*'), r"\1·"),
    # a impressão digital da proposta (`versao_da_proposta()`): leva as
    # horas de criação, que são as do minuto em que a base se montou
    (re.compile(r"(name=['\"]versao['\"] value=['\"])[0-9a-f]*"), r"\1·"),
    # as horas de hoje (o que a base inventada registou ao montar-se:
    # a actividade, as entradas). Só as de HOJE: uma data fixa da base
    # que mude é uma diferença verdadeira
    (re.compile(re.escape(date.today().strftime("%d/%m/%Y")) + r" \d\d:\d\d"),
     "HOJE hh:mm"),
    # o sitemap dá a data dos ficheiros do site, que é a do disco
    (re.compile(r"<lastmod>[^<]*</lastmod>"), "<lastmod>·</lastmod>"),
]

# Os formatos que trazem a hora de agora dentro (um zip guarda a data de
# cada ficheiro; o xlsx é um zip): o resumo muda a cada gravação, e não
# são HTML. Grava-se o código e o tipo, não o conteúdo.
NAO_SE_COMPARA = ("application/zip",
                  "application/vnd.openxmlformats-officedocument")


def normalizar(texto):
    for padrao, troca in NORMALIZAR:
        texto = padrao.sub(troca, texto)
    return texto


def nome_do_ficheiro(caminho):
    """O pedido como nome de ficheiro: legível e sem colisões."""
    limpo = re.sub(r"[^A-Za-z0-9._=-]+", "_", caminho).strip("_") or "raiz"
    return limpo[:80] + "-" + hashlib.sha1(caminho.encode()).hexdigest()[:8]


# --- gravar -----------------------------------------------------------------

def preparar(codigo):
    """Importa o código a medir e monta a base inventada do `demo.py`
    dele. Devolve o módulo `radar` e os valores para os `EXEMPLOS`."""
    sys.path.insert(0, os.path.join(codigo, "ferramentas"))
    import demo                                   # monta a base temporária
    radar = demo.radar
    with radar.com_empresa(demo.EMPRESA):
        with radar.liga() as c:
            r = c.execute("SELECT id FROM propostas WHERE COALESCE(ref,'')=''"
                          " ORDER BY id LIMIT 1").fetchone()
    valores = {"pombal": demo.POMBAL, "empresa": demo.EMPRESA,
               "proposta": r[0] if r else 0,
               "etiqueta": radar.ETIQUETA_CSS, "tipo": sorted(radar.TIPOS)[0]}
    # As contas existem mesmo na base: há ecrãs (a Conta) que as relêem
    # pelo id. A sessão é que não se grava: o token é o nome do perfil.
    senha = "Igualdade-do-HTML-2026"
    contas = {}
    with radar.liga() as c:
        for perfil, email, nome, papel, empresa in (
                ("dono", "dono@miragov.pt", "Dono", "admin", None),
                ("gestor", "ana@climatermica.pt", "Ana Costa", "admin",
                 demo.EMPRESA),
                ("membro", "rui@climatermica.pt", "Rui Matos", "tester",
                 demo.EMPRESA)):
            id_ = radar.contas.criar_utilizador(
                c, email, senha, nome=nome, papel=papel, empresa_id=empresa,
                pela_consola=perfil == "dono")
            linha = c.execute("SELECT id, email, nome, papel, empresa_id,"
                              " dono FROM utilizadores WHERE id=?",
                              (id_,)).fetchone()
            contas[perfil] = dict(linha, aspecto="claro", ver_como=None)
    radar.contas.utilizador_da_sessao = (
        lambda c, token, agora=None: dict(contas[token])
        if token in contas else None)
    return radar, valores


def pedidos(radar, valores):
    """Todos os GET do painel, com os exemplos e as variantes."""
    lista, sem_exemplo = [], []
    for regra in sorted(radar.app.url_map.iter_rules(), key=lambda r: r.rule):
        if "GET" not in regra.methods:
            continue
        if not regra.arguments:
            lista.append(regra.rule)
        elif regra.rule in EXEMPLOS:
            lista += [e.format(**valores) for e in EXEMPLOS[regra.rule]]
        else:
            sem_exemplo.append(regra.rule)
    return lista + VARIANTES, sem_exemplo


def cliente_de(radar, perfil):
    cliente = radar.app.test_client()
    if perfil == "fora":
        cliente.environ_base["HTTP_CF_CONNECTING_IP"] = "203.0.113.7"
    else:
        cliente.set_cookie("sessao", perfil)
    return cliente


def gravar(pasta, codigo):
    radar, valores = preparar(codigo)
    lista, sem_exemplo = pedidos(radar, valores)
    for perfil in PERFIS:
        cliente = cliente_de(radar, perfil)
        destino = os.path.join(pasta, perfil)
        os.makedirs(destino, exist_ok=True)
        for caminho in lista:
            r = cliente.get(caminho)
            corpo = r.get_data()
            tipo = r.headers.get("Content-Type", "")
            if tipo.startswith(("text/", "application/json", "application/xml")):
                conteudo = corpo.decode("utf-8", "replace")
            elif tipo.startswith(NAO_SE_COMPARA):
                conteudo = "(não se compara: leva a hora de agora)"
            else:   # o binário compara-se pelo resumo
                conteudo = "sha256 %s" % hashlib.sha256(corpo).hexdigest()
            cabeca = "%s %d %s %s\n" % (caminho, r.status_code, tipo,
                                        r.headers.get("Location", ""))
            with open(os.path.join(destino, nome_do_ficheiro(caminho)),
                      "w", encoding="utf-8") as f:
                f.write(cabeca + conteudo)
    print("Gravados %d pedidos x %d perfis em %s"
          % (len(lista), len(PERFIS), pasta))
    for regra in sem_exemplo:
        print("  SEM EXEMPLO (não medida): %s" % regra)


# --- comparar ---------------------------------------------------------------

def trecho(linha_a, linha_b, largura=60):
    """O sítio onde duas linhas se separam: as linhas do painel têm
    milhares de caracteres, e um diff da linha inteira não mostra nada."""
    i = len(os.path.commonprefix([linha_a, linha_b]))
    inicio = max(0, i - largura)
    return (linha_a[inicio:i + largura], linha_b[inicio:i + largura])


def comparar(a, b, mostrar=3):
    """As diferenças entre duas gravações, depois de normalizadas.
    Devolve a lista de (ficheiro, [(n.º da linha, trecho A, trecho B)]),
    com as primeiras `mostrar` linhas diferentes de cada ficheiro."""
    diferencas = []
    ficheiros = set()
    for raiz in (a, b):
        for perfil in os.listdir(raiz):
            for nome in os.listdir(os.path.join(raiz, perfil)):
                ficheiros.add(os.path.join(perfil, nome))
    for rel in sorted(ficheiros):
        lados = []
        for raiz in (a, b):
            try:
                with open(os.path.join(raiz, rel), encoding="utf-8") as f:
                    lados.append(normalizar(f.read()).splitlines())
            except FileNotFoundError:
                lados.append(["(não existe deste lado)"])
        if lados[0] == lados[1]:
            continue
        linhas = []
        for n, (la, lb) in enumerate(itertools.zip_longest(
                *lados, fillvalue="(acabou)"), 1):
            if la != lb:
                linhas.append((n,) + trecho(la, lb))
                if len(linhas) == mostrar:
                    break
        diferencas.append((rel, linhas))
    return diferencas


def main(argv):
    if argv[:1] == ["--gravar"] and len(argv) >= 2:
        codigo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if "--codigo" in argv:
            codigo = os.path.abspath(argv[argv.index("--codigo") + 1])
        gravar(os.path.abspath(argv[1]), codigo)
        return 0
    if argv[:1] == ["--comparar"] and len(argv) == 3:
        diferencas = comparar(argv[1], argv[2])
        for rel, linhas in diferencas:
            print("=== %s" % rel)
            for n, antes, depois in linhas:
                print("  linha %d\n    A: %r\n    B: %r" % (n, antes, depois))
        print("%d ficheiros diferentes." % len(diferencas) if diferencas
              else "Iguais.")
        return 1 if diferencas else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
