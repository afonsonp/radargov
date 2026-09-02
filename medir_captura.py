"""Mede de onde vem o token das capturas do DR, e se se renova sem browser.

Pergunta: o x-csrftoken e a versionInfo que o radar copia do curl_DR.txt
nascem de uma sessao iniciada no browser, ou de pedidos simples que o
requests faz? Se for o segundo caso, a recaptura no DevTools deixa de
ser precisa e nao ha razao para trazer um browser (Scrapling,
Playwright) para a pen.

O DR e uma aplicacao OutSystems. A primeira volta (02/09/2026) mediu:

- o x-csrftoken E o `crf=` do cookie nr2Users (o `+` vem como %2b);
- so o x-csrftoken tranca: sem cookie passa, com a moduleVersion errada
  passa (o DR ja republicou desde a captura, `hasModuleVersionChanged`,
  e continua a responder);
- a apiVersion e a segunda tranca: errada, vem JSON com zero anuncios;
- a home e a casca de 2346 bytes, sem cookies: o cookie e o moduleinfo
  nascem dos pedidos que o JavaScript faz a seguir.

A segunda volta segue essa pista: que pedido poe o cookie, se um token
inventado passa (se passar, nao ha token nenhum a renovar), e de onde
se tira a apiVersion sem browser (o manifesto do moduleinfo lista os
scripts de cada ecra, e a apiVersion esta dentro do script do ecra).

Corre no PC (o DR nao responde de fora), le as capturas e NUNCA as
escreve. Escreve o relatorio em amostras/medicao_captura.txt, e guarda
em amostras/ a casca da home e o moduleinfo, para se lerem depois.

    python medir_captura.py        (ou medir.bat, que abre o relatorio)
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta
from urllib.parse import unquote, urljoin

import requests

import radar

RAIZ = "https://diariodarepublica.pt"
HOME = RAIZ + "/dr/home"
MODULEINFO = RAIZ + "/dr/moduleservices/moduleinfo"
RELATORIO = os.path.join(radar.AMOSTRAS, "medicao_captura.txt")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")

linhas = []


def diz(texto=""):
    print(texto)
    linhas.append(texto)


def guardar(nome, conteudo):
    os.makedirs(radar.AMOSTRAS, exist_ok=True)
    with open(os.path.join(radar.AMOSTRAS, nome), "w", encoding="utf-8") as f:
        f.write(conteudo)


def crf_do_cookie(cookie):
    """O token dentro do nr2Users: 'crf%3dXXXX%3b...' ou ja descodificado.

    O valor leva '+' e '/' (e base64), e o browser manda-os como %2b e
    %2f: descodifica-se o pedaco inteiro ate ao ';' (ou %3b)."""
    if not cookie:
        return ""
    m = re.search(r"crf(?:=|%3[Dd])(.*?)(?:;|%3[Bb]|$)", cookie)
    return unquote(m.group(1)) if m else ""


def cabecalho(pedido, nome):
    for chave, valor in pedido["headers"].items():
        if chave.lower() == nome.lower():
            return valor
    return ""


def sem_cabecalho(headers, nome):
    return {k: v for k, v in headers.items() if k.lower() != nome.lower()}


def com_token(headers, token):
    h = sem_cabecalho(headers, "x-csrftoken")
    h["X-CSRFToken"] = token
    return h


def corpo_pequeno(molde):
    """O molde da captura com uma janela de 3 dias e uma pagina."""
    m = json.loads(json.dumps(molde))
    variaveis = m["screenData"]["variables"]
    radar.limpa_resultados(variaveis)
    filtros = variaveis["FiltrosDePesquisa"]
    radar.repara_filtros(filtros)
    fim = datetime.now()
    inicio = fim - timedelta(days=3)
    filtros["dataPublicacaoDe"] = inicio.strftime("%Y-%m-%d")
    filtros["dataPublicacaoAte"] = fim.strftime("%Y-%m-%d")
    variaveis["DataDe"] = filtros["dataPublicacaoDe"]
    variaveis["DataAte"] = filtros["dataPublicacaoAte"]
    variaveis["StartIndex"] = 0
    return m


def disparar(rotulo, url, headers, molde, sessao=None):
    """POST e veredicto: JSON com anuncios, JSON sem anuncios, ou casca."""
    quem = sessao or requests
    corpo = json.dumps(molde, ensure_ascii=False).encode("utf-8")
    try:
        r = quem.post(url, headers=headers, data=corpo, timeout=60)
    except requests.RequestException as erro:
        diz("  %-34s rede: %s" % (rotulo, str(erro)[:70]))
        return "rede"
    tipo = r.headers.get("Content-Type", "")
    if "json" not in tipo:
        diz("  %-34s HTTP %d, %s, %d bytes: NAO aceite (casca HTML)"
            % (rotulo, r.status_code, tipo.split(";")[0] or "?", len(r.content)))
        return "casca"
    try:
        dados = r.json()
    except ValueError:
        diz("  %-34s HTTP %d com JSON ilegivel" % (rotulo, r.status_code))
        return "ilegivel"
    n = len(radar.anuncios_da_resposta(dados))
    excepcao = ""
    if isinstance(dados, dict):
        exc = dados.get("exception") or {}
        if isinstance(exc, dict):
            excepcao = exc.get("message") or exc.get("name") or ""
        vi = dados.get("versionInfo") or {}
        if isinstance(vi, dict) and vi.get("hasModuleVersionChanged"):
            excepcao = (excepcao + " | hasModuleVersionChanged").strip(" |")
    if n == 0 and isinstance(dados, dict):
        # Com a apiVersion errada vem JSON sem anuncios: o que mais diz?
        guardar("medicao_resposta_vazia.json", json.dumps(dados, indent=1)[:20000])
    diz("  %-34s HTTP %d, JSON, %d anuncios%s"
        % (rotulo, r.status_code, n,
           (", excepcao: " + excepcao[:80]) if excepcao else ""))
    return "ok" if n else "vazio"


def cookies_de(r):
    return [c.split("=", 1)[0].strip()
            for c in r.headers.get("Set-Cookie", "").split(",") if "=" in c]


def pedir(s, rotulo, url):
    """GET numa sessao, com o relatorio a dizer o que veio e que cookies pos."""
    try:
        r = s.get(url, timeout=60)
    except requests.RequestException as erro:
        diz("  %-34s rede: %s" % (rotulo, str(erro)[:70]))
        return None
    postos = cookies_de(r)
    diz("  %-34s HTTP %d, %s, %d bytes%s"
        % (rotulo, r.status_code,
           r.headers.get("Content-Type", "?").split(";")[0], len(r.content),
           (", poe cookies: " + ", ".join(postos)) if postos else ""))
    return r


def urls_da_casca(html_home):
    """Os scripts e folhas que a casca carrega, absolutos."""
    achados = re.findall(r'(?:src|href)="([^"]+\.(?:js|json)[^"]*)"', html_home)
    return [urljoin(HOME, u) for u in achados]


def procurar(texto, padrao, largura=90):
    """Os pedacos do texto a volta de cada ocorrencia do padrao."""
    fora = []
    for m in re.finditer(padrao, texto):
        a, b = max(0, m.start() - largura), min(len(texto), m.end() + largura)
        fora.append(texto[a:b].replace("\n", " "))
        if len(fora) >= 3:
            break
    return fora


def main():
    diz("Medicao do token do DR, %s (2.a volta)"
        % datetime.now().strftime("%d/%m/%Y %H:%M"))
    diz()

    comando = radar.carregar_curl("curl_DR")
    if not comando:
        diz("falta o curl_DR.txt: sem captura nao ha com que comparar")
        return 2
    pedido = radar.parse_curl(comando)
    try:
        molde = json.loads(pedido["body"])
        molde["screenData"]["variables"]["FiltrosDePesquisa"]
    except (ValueError, KeyError, TypeError):
        diz("o curl_DR.txt nao tem um corpo legivel")
        return 2

    # 1. O que a captura traz
    diz("1. A captura")
    token_capt = cabecalho(pedido, "x-csrftoken")
    cookie_capt = cabecalho(pedido, "cookie")
    crf_capt = crf_do_cookie(cookie_capt)
    versao_capt = molde.get("versionInfo") or {}
    diz("  x-csrftoken:            %s" % (token_capt[:12] + "..." if token_capt else "(nao ha)"))
    diz("  crf= no cookie nr2Users: %s" % (crf_capt[:12] + "..." if crf_capt else "(nao ha)"))
    diz("  os dois sao iguais:     %s" % ("SIM" if token_capt and token_capt == crf_capt else "nao"))
    diz("  moduleVersion:          %s" % versao_capt.get("moduleVersion", "(nao ha)"))
    diz("  apiVersion:             %s" % versao_capt.get("apiVersion", "(nao ha)"))
    diz()

    # 2. Controlo: a captura tal como esta
    diz("2. Controlo, a captura tal como esta")
    pequeno = corpo_pequeno(molde)
    controlo = disparar("captura intacta", pedido["url"], pedido["headers"], pequeno)
    if controlo == "rede":
        diz("  sem rede para o DR; nada mais se mede")
        return 1
    diz()

    # 3. O token e verificado, ou basta haver um?
    diz("3. O token: verificado, ou basta haver um?")
    if controlo in ("ok", "vazio"):
        h = pedido["headers"]
        disparar("token inventado, com cookie", pedido["url"],
                 com_token(h, "abcdefghijklmnopqrstuv"), pequeno)
        disparar("token inventado, sem cookie", pedido["url"],
                 com_token(sem_cabecalho(h, "cookie"), "abcdefghijklmnopqrstuv"),
                 pequeno)
        disparar("token vazio", pedido["url"], com_token(h, ""), pequeno)
        if token_capt:
            disparar("token com um caracter trocado", pedido["url"],
                     com_token(h, token_capt[:-1] + ("A" if token_capt[-1] != "A" else "B")),
                     pequeno)
    else:
        diz("  (saltado: a captura ja nao e aceite)")
    diz()

    # 4. Que pedido poe o cookie, sem browser
    diz("4. Sessao nova, a seguir o caminho que o JavaScript faz")
    s = requests.Session()
    s.headers["User-Agent"] = cabecalho(pedido, "user-agent") or UA
    r = pedir(s, "GET home", HOME)
    if r is None:
        return 1
    html_home = r.text
    guardar("medicao_casca_home.html", html_home)
    urls = urls_da_casca(html_home)
    diz("  a casca carrega %d ficheiros:" % len(urls))
    for u in urls[:12]:
        diz("    " + u.replace(RAIZ, "")[:100])

    # os scripts da casca: onde falam de moduleinfo e do cookie?
    for u in urls:
        if not u.endswith((".js",)) and ".js?" not in u:
            continue
        try:
            js = s.get(u, timeout=60).text
        except requests.RequestException:
            continue
        for padrao in (r"moduleinfo", r"nr2Users", r"X-CSRFToken", r"csrf"):
            pedacos = procurar(js, padrao, 70)
            if pedacos:
                diz("  %s fala de %s:" % (u.rsplit("/", 1)[-1][:40], padrao))
                for p in pedacos[:2]:
                    diz("      ..." + p[:150] + "...")
        postos = [c.name for c in s.cookies]
        if postos:
            diz("  depois de %s a sessao tem cookies: %s"
                % (u.rsplit("/", 1)[-1][:40], ", ".join(postos)))
            break

    # o moduleinfo, com a versao da captura e sem versao
    mi_json = None
    for rotulo, url in (("GET moduleinfo?<moduleVersion capt>",
                         MODULEINFO + "?" + versao_capt.get("moduleVersion", "")),
                        ("GET moduleinfo sem versao", MODULEINFO)):
        r = pedir(s, rotulo, url)
        if r is not None and "json" in r.headers.get("Content-Type", ""):
            try:
                mi_json = r.json()
                guardar("medicao_moduleinfo.json", json.dumps(mi_json, indent=1)[:200000])
                break
            except ValueError:
                pass
    versao_nova = ""
    if isinstance(mi_json, dict):
        versao_nova = str(mi_json.get("versionToken", ""))
        diz("  moduleinfo: chaves %s" % ", ".join(list(mi_json)[:10]))
        diz("  versionToken:           %s (captura: %s)"
            % (versao_nova or "(nao ha)", versao_capt.get("moduleVersion", "?")))
        # o manifesto lista os scripts de cada ecra: o da pesquisa traz a apiVersion
        texto_mi = json.dumps(mi_json)
        candidatos = sorted(set(re.findall(r'"([^"]*Pesquisa[^"]*\.js[^"]*)"', texto_mi)))
        diz("  scripts com 'Pesquisa' no manifesto: %d" % len(candidatos))
        api_capt = versao_capt.get("apiVersion", "")
        for c in candidatos[:8]:
            url_js = urljoin(HOME, c) if not c.startswith("http") else c
            try:
                js = s.get(url_js, timeout=60).text
            except requests.RequestException:
                continue
            tem = api_capt and api_capt in js
            outras = re.findall(r'apiVersion["\']?\s*[:=]\s*["\']([A-Za-z0-9_\-]{10,})', js)
            diz("    %-60s %s%s"
                % (c.rsplit("/", 1)[-1][:60],
                   "TEM a apiVersion da captura" if tem else "nao tem a da captura",
                   (", traz %d apiVersion" % len(set(outras))) if outras else ""))
            if "GetPesquisas" in js:
                for p in procurar(js, r"GetPesquisas", 120)[:1]:
                    diz("      ..." + p[:240] + "...")

    cookies_sessao = {c.name: c.value for c in s.cookies}
    diz("  cookies na sessao no fim: %s" % (", ".join(sorted(cookies_sessao)) or "(nenhum)"))
    crf_novo = crf_do_cookie(cookies_sessao.get("nr2Users", ""))
    diz("  crf= no nr2Users novo:  %s" % (crf_novo[:12] + "..." if crf_novo else "(nao ha)"))
    diz()

    # 5. Um pedido da sessao nova
    diz("5. O pedido da captura com o que a sessao nova deu")
    h = sem_cabecalho(pedido["headers"], "cookie")
    renovado = json.loads(json.dumps(pequeno))
    if versao_nova:
        renovado.setdefault("versionInfo", {})["moduleVersion"] = versao_nova
    if crf_novo:
        disparar("sessao nova, crf novo", pedido["url"], com_token(h, crf_novo),
                 renovado, sessao=s)
    else:
        diz("  sem crf novo; o que se testa e a sessao nova com o token da captura")
        disparar("sessao nova, token da captura", pedido["url"], h, renovado, sessao=s)
    diz()

    diz("Conclusao: ler os pontos 3 e 4. Se um token inventado passa, nao ha "
        "token a renovar e so a apiVersion importa; se nao passa, o pedido "
        "que poe o nr2Users esta no ponto 4 (ou nao esta, e o caminho e o "
        "browser).")

    guardar("medicao_captura.txt", "\n".join(linhas) + "\n")
    diz()
    diz("relatorio em %s; a casca, o moduleinfo e a resposta vazia ficaram "
        "em amostras/" % os.path.relpath(RELATORIO, radar.BASE_DIR))
    return 0


if __name__ == "__main__":
    sys.exit(main())
