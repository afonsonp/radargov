"""Mede de onde vem o token das capturas do DR, e se se renova sem browser.

Pergunta: o x-csrftoken e a versionInfo que o radar copia do curl_DR.txt
nascem de uma sessao iniciada no browser, ou de um simples GET a pagina?
Se for o segundo caso, a recaptura no DevTools deixa de ser precisa e
nao ha razao para trazer um browser (Scrapling, Playwright) para a pen.

O DR e uma aplicacao OutSystems. O que se sabe de aplicacoes desse tipo,
e que aqui se confirma ou desmente contra o portal verdadeiro:

- o primeiro GET poe um cookie `nr2Users` com `crf=<token>` la dentro,
  e o cabecalho x-csrftoken de cada pedido e esse mesmo valor;
- o corpo de cada pedido leva `versionInfo.moduleVersion`, que e o
  `versionToken` do `moduleservices/moduleinfo`, e muda quando o DR
  republica a aplicacao;
- `versionInfo.apiVersion` vem do JS compilado do ecra, e so muda com a
  republicacao.

Corre no PC (o DR nao responde de fora), le as capturas e NUNCA as
escreve. Escreve o relatorio em amostras/medicao_captura.txt e no ecra.

    python medir_captura.py
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta
from urllib.parse import unquote

import requests

import radar

HOME = "https://diariodarepublica.pt/dr/home"
RELATORIO = os.path.join(radar.AMOSTRAS, "medicao_captura.txt")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")

linhas = []


def diz(texto=""):
    print(texto)
    linhas.append(texto)


def crf_do_cookie(cookie):
    """O token dentro do nr2Users: 'crf%3dXXXX%3b...' ou ja descodificado."""
    if not cookie:
        return ""
    m = re.search(r"crf(?:=|%3[Dd])([^;%\s]+)", cookie)
    return unquote(m.group(1)) if m else ""


def cabecalho(pedido, nome):
    for chave, valor in pedido["headers"].items():
        if chave.lower() == nome.lower():
            return valor
    return ""


def sem_cabecalho(pedido, nome):
    return {k: v for k, v in pedido["headers"].items()
            if k.lower() != nome.lower()}


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
    diz("  %-34s HTTP %d, JSON, %d anuncios%s"
        % (rotulo, r.status_code, n,
           (", excepcao: " + excepcao[:80]) if excepcao else ""))
    return "ok" if n else "vazio"


def main():
    diz("Medicao do token do DR, %s" % datetime.now().strftime("%d/%m/%Y %H:%M"))
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
    nomes_cookies = sorted(set(re.findall(r"(?:^|;\s*)([^=;\s]+)=", cookie_capt)))
    diz("  cookies na captura:     %s" % (", ".join(nomes_cookies) or "(nenhum)"))
    diz()

    # 2. Controlo: a captura tal como esta
    diz("2. Controlo, a captura tal como esta")
    pequeno = corpo_pequeno(molde)
    controlo = disparar("captura intacta", pedido["url"], pedido["headers"], pequeno)
    if controlo == "rede":
        diz("  sem rede para o DR; nada mais se mede")
        return 1
    diz()

    # 3. O que cada peca tranca (so faz sentido se o controlo passou)
    if controlo in ("ok", "vazio"):
        diz("3. Tirar uma peca de cada vez a captura")
        disparar("sem x-csrftoken", pedido["url"],
                 sem_cabecalho(pedido, "x-csrftoken"), pequeno)
        disparar("sem cookie", pedido["url"],
                 sem_cabecalho(pedido, "cookie"), pequeno)
        trocado = json.loads(json.dumps(pequeno))
        trocado.setdefault("versionInfo", {})["moduleVersion"] = "0" * 32
        disparar("moduleVersion errada", pedido["url"], pedido["headers"], trocado)
        trocado = json.loads(json.dumps(pequeno))
        trocado.setdefault("versionInfo", {})["apiVersion"] = "0" * 32
        disparar("apiVersion errada", pedido["url"], pedido["headers"], trocado)
        diz()
    else:
        diz("3. (saltado: a captura ja nao e aceite, e o que se mede a seguir "
            "e se uma sessao nova a substitui)")
        diz()

    # 4. Sessao nova, sem browser
    diz("4. Sessao nova por GET, sem browser")
    s = requests.Session()
    s.headers["User-Agent"] = cabecalho(pedido, "user-agent") or UA
    try:
        r = s.get(HOME, timeout=60)
    except requests.RequestException as erro:
        diz("  GET %s: %s" % (HOME, str(erro)[:70]))
        return 1
    html_home = r.text
    diz("  GET home: HTTP %d, %d bytes" % (r.status_code, len(r.content)))
    novos = {c.name: c.value for c in s.cookies}
    diz("  cookies recebidos:      %s" % (", ".join(sorted(novos)) or "(nenhum)"))
    crf_novo = crf_do_cookie(novos.get("nr2Users", ""))
    diz("  crf= no nr2Users novo:  %s" % (crf_novo[:12] + "..." if crf_novo else "(nao ha)"))

    m = re.search(r"moduleservices/moduleinfo\?[0-9A-Za-z]+", html_home)
    versao_nova = ""
    if m:
        url_mi = "https://diariodarepublica.pt/dr/" + m.group(0)
        try:
            mi = s.get(url_mi, timeout=60).json()
            versao_nova = str(mi.get("versionToken", ""))
        except (requests.RequestException, ValueError) as erro:
            diz("  moduleinfo: %s" % str(erro)[:70])
        diz("  moduleinfo versionToken: %s" % (versao_nova or "(nao veio)"))
        diz("  igual ao da captura:    %s"
            % ("SIM" if versao_nova and versao_nova == versao_capt.get("moduleVersion") else "nao"))
    else:
        diz("  a home nao referencia moduleinfo (a aplicacao mudou de forma?)")

    api_capt = versao_capt.get("apiVersion", "")
    if api_capt:
        scripts = re.findall(r'src="([^"]*Pesquisa[^"]*\.js[^"]*)"', html_home)
        achado = False
        for src in scripts[:6]:
            url_js = src if src.startswith("http") else "https://diariodarepublica.pt" + (
                src if src.startswith("/") else "/dr/" + src)
            try:
                js = s.get(url_js, timeout=60).text
            except requests.RequestException:
                continue
            if api_capt in js:
                achado = True
                diz("  apiVersion da captura ainda esta no JS: %s" % url_js.rsplit("/", 1)[-1][:60])
                break
        if not achado:
            diz("  apiVersion da captura NAO encontrada em %d scripts de Pesquisa"
                " (republicado, ou o script vem por outro nome)" % len(scripts))
    diz()

    # 5. O pedido da captura, com as pecas novas
    diz("5. O pedido da captura com o token e a versao da sessao nova")
    if not crf_novo:
        diz("  sem crf novo nao ha o que testar: o token nao nasce do GET")
    else:
        headers = sem_cabecalho(pedido, "cookie")
        headers = {k: v for k, v in headers.items() if k.lower() != "x-csrftoken"}
        headers["X-CSRFToken"] = crf_novo
        renovado = json.loads(json.dumps(pequeno))
        if versao_nova:
            renovado.setdefault("versionInfo", {})["moduleVersion"] = versao_nova
        veredicto = disparar("sessao nova", pedido["url"], headers, renovado, sessao=s)
        diz()
        diz("Conclusao:")
        if veredicto in ("ok", "vazio"):
            diz("  O token renova-se com um GET e um POST, sem browser. As capturas "
                "so fazem falta pela forma do corpo, e essa nao expira. "
                "Scrapling nao acrescenta nada aqui.")
        elif veredicto == "casca":
            diz("  Um GET nao chega: ou o token exige um passo que o browser faz "
                "(JS, segundo pedido), ou a apiVersion esta desactualizada. "
                "Ver os pontos 3 e 4 para saber qual. So neste caso um browser "
                "sem cabeca vale a pena medir.")
        else:
            diz("  Resultado inconclusivo (%s): ver as linhas acima." % veredicto)

    os.makedirs(radar.AMOSTRAS, exist_ok=True)
    with open(RELATORIO, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
    diz()
    diz("relatorio em %s" % os.path.relpath(RELATORIO, radar.BASE_DIR))
    return 0


if __name__ == "__main__":
    sys.exit(main())
