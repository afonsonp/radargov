"""Mede de onde vem o token das capturas do DR, e se se renova sem browser.

Pergunta: o x-csrftoken e a versionInfo que o radar copia do curl_DR.txt
nascem de uma sessao iniciada no browser, ou de pedidos simples que o
requests faz? Se for o segundo caso, a recaptura no DevTools deixa de
ser precisa e nao ha razao para trazer um browser para a pen.

O DR e uma aplicacao OutSystems. Duas voltas (02/09/2026) mediram:

- o x-csrftoken e o `crf=` do cookie nr2Users, E e uma CONSTANTE
  publicada no /dr/scripts/OutSystems.js (`AnonymousCSRFToken="..."`):
  nao vem de sessao nenhuma, so muda quando o DR actualiza a plataforma;
- so o token tranca: sem cookie passa; com cookie, um token inventado
  nao passa; sem cookie, ate um token inventado passa;
- a moduleVersion nao tranca (o DR ja republicou desde a captura,
  `hasModuleVersionChanged`, e responde na mesma);
- a apiVersion tranca: errada, vem JSON com zero anuncios. Vive no
  script do ecra (dr.Pesquisas.PesquisaResultado.mvc.js), cujo endereco
  com versao esta em `manifest.urlVersions` do moduleinfo;
- a home e a casca de 2346 bytes, sem cookies, e o moduleinfo responde
  a um GET sem sessao.

A terceira volta faz a renovacao de ponta a ponta -- token do
OutSystems.js, versionToken e script do moduleinfo, apiVersion do
script -- e prova-a com um pedido de pesquisa e um de detalhe feitos
so com isso e a forma do corpo da captura. Provou (02/09/2026, 25
anuncios e 1 detalhe com cabecalhos minimos), e a receita passou para
o radar.py: renovar_pecas_dr() e perguntar_ao_dr(). Isto fica como o
instrumento de medida, para quando o DR mudar.

Corre no PC (o DR nao responde de fora), le as capturas e NUNCA as
escreve. Relatorio em amostras/medicao_captura.txt; guarda tambem em
amostras/ o pedaco do script onde a apiVersion aparece.

    python medir_captura.py        (ou medir.bat, que abre o relatorio)
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta
from urllib.parse import unquote, urlparse

import requests

import radar

RAIZ = "https://diariodarepublica.pt"
MODULEINFO = RAIZ + "/dr/moduleservices/moduleinfo"
OUTSYSTEMS_JS = "/dr/scripts/OutSystems.js"
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
    """O molde da pesquisa com uma janela de 3 dias e uma pagina."""
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


def com_versoes(molde, module_version=None, api_version=None):
    m = json.loads(json.dumps(molde))
    vi = m.setdefault("versionInfo", {})
    if module_version:
        vi["moduleVersion"] = module_version
    if api_version:
        vi["apiVersion"] = api_version
    return m


def veredicto_json(dados, contar):
    """('ok'|'vazio', descricao). `contar` diz quantos anuncios traz."""
    n = contar(dados)
    excepcao = ""
    if isinstance(dados, dict):
        exc = dados.get("exception") or {}
        if isinstance(exc, dict):
            excepcao = exc.get("message") or exc.get("name") or ""
        vi = dados.get("versionInfo") or {}
        if isinstance(vi, dict) and vi.get("hasModuleVersionChanged"):
            excepcao = (excepcao + " | hasModuleVersionChanged").strip(" |")
    return ("ok" if n else "vazio"), ("%d resultados%s" % (
        n, (", excepcao: " + excepcao[:80]) if excepcao else ""))


def contar_pesquisa(dados):
    return len(radar.anuncios_da_resposta(dados))


def contar_detalhe(dados):
    """O detalhe traz o texto do anuncio em 'data'; conta 1 se vier."""
    texto = json.dumps(dados.get("data", "")) if isinstance(dados, dict) else ""
    return 1 if len(texto) > 500 else 0


def disparar(rotulo, url, headers, molde, contar=contar_pesquisa, sessao=None):
    """POST e veredicto: JSON com resultados, JSON sem eles, ou casca."""
    quem = sessao or requests
    corpo = json.dumps(molde, ensure_ascii=False).encode("utf-8")
    try:
        r = quem.post(url, headers=headers, data=corpo, timeout=60)
    except requests.RequestException as erro:
        diz("  %-38s rede: %s" % (rotulo, str(erro)[:70]))
        return "rede"
    tipo = r.headers.get("Content-Type", "")
    if "json" not in tipo:
        diz("  %-38s HTTP %d, %s, %d bytes: NAO aceite (casca HTML)"
            % (rotulo, r.status_code, tipo.split(";")[0] or "?", len(r.content)))
        return "casca"
    try:
        dados = r.json()
    except ValueError:
        diz("  %-38s HTTP %d com JSON ilegivel" % (rotulo, r.status_code))
        return "ilegivel"
    estado, descricao = veredicto_json(dados, contar)
    if estado == "vazio":
        guardar("medicao_resposta_vazia.json", json.dumps(dados, indent=1)[:20000])
    diz("  %-38s HTTP %d, JSON, %s" % (rotulo, r.status_code, descricao))
    return estado


def buscar(s, rotulo, url):
    try:
        r = s.get(url, timeout=60)
    except requests.RequestException as erro:
        diz("  %-38s rede: %s" % (rotulo, str(erro)[:70]))
        return None
    diz("  %-38s HTTP %d, %s, %d bytes"
        % (rotulo, r.status_code,
           r.headers.get("Content-Type", "?").split(";")[0], len(r.content)))
    return r


def script_do_ecra(url_accao):
    """De .../screenservices/dr/Pesquisas/PesquisaResultado/DataActionX
    para ('/dr/scripts/dr.Pesquisas.PesquisaResultado.mvc.js', 'DataActionX')."""
    partes = urlparse(url_accao).path.split("/screenservices/", 1)
    if len(partes) != 2:
        return "", ""
    pedacos = partes[1].strip("/").split("/")
    if len(pedacos) < 2:
        return "", ""
    accao = pedacos[-1]
    return "/dr/scripts/" + ".".join(pedacos[:-1]) + ".mvc.js", accao


def api_version_do_script(js, accao, conhecida=""):
    """A apiVersion da accao dentro do script compilado do ecra.

    Devolve (valor, pedaco) -- o pedaco e o texto a volta da accao, para
    se ver como o OutSystems a escreve e afinar o padrao. Primeiro a
    conhecida, se la estiver (prova que se le do sitio certo); senao,
    o primeiro token de 22 caracteres a seguir ao nome da accao."""
    i = js.find(accao)
    if i < 0:
        return "", ""
    pedaco = js[max(0, i - 200):i + 600]
    if conhecida and conhecida in pedaco:
        return conhecida, pedaco
    m = re.search(re.escape(accao) + r'.{0,400}?["\']([A-Za-z0-9_+\-]{22})["\']',
                  js[i:i + 1200], re.S)
    return (m.group(1) if m else ""), pedaco


def cabecalhos_minimos(token, referer):
    """O que um pedido feito de raiz leva, sem nada da captura."""
    return {"User-Agent": UA,
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
            "Origin": RAIZ,
            "Referer": referer,
            "X-CSRFToken": token}


def main():
    diz("Medicao do token do DR, %s (3.a volta: renovar de ponta a ponta)"
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
    token_capt = cabecalho(pedido, "x-csrftoken")
    versao_capt = molde.get("versionInfo") or {}
    pequeno = corpo_pequeno(molde)

    par, _ = radar._molde_detalhe()
    pedido_det, molde_det = par if par else (None, None)

    # 1. Controlo
    diz("1. Controlo, as capturas tal como estao")
    controlo = disparar("pesquisa, captura intacta", pedido["url"],
                        pedido["headers"], pequeno)
    if controlo == "rede":
        diz("  sem rede para o DR; nada mais se mede")
        return 1
    if pedido_det:
        disparar("detalhe, captura intacta", pedido_det["url"],
                 pedido_det["headers"], molde_det, contar_detalhe)
    else:
        diz("  (sem curl_detalhe.txt legivel: o detalhe fica de fora)")
    diz()

    # 2. As tres pecas, sem browser e sem captura
    diz("2. As tres pecas, so com GETs")
    s = requests.Session()
    s.headers["User-Agent"] = UA
    r = buscar(s, "GET moduleinfo", MODULEINFO)
    if r is None:
        return 1
    try:
        manifesto = r.json()["manifest"]
        versao_nova = str(manifesto["versionToken"])
        url_versions = manifesto["urlVersions"]
    except (ValueError, KeyError, TypeError):
        diz("  o moduleinfo nao tem manifest.versionToken/urlVersions")
        return 1
    diz("  versionToken:           %s (captura: %s)"
        % (versao_nova, versao_capt.get("moduleVersion", "?")))

    r = buscar(s, "GET OutSystems.js",
               RAIZ + OUTSYSTEMS_JS + url_versions.get(OUTSYSTEMS_JS, ""))
    if r is None:
        return 1
    m = re.search(r'AnonymousCSRFToken\s*=\s*"([^"]+)"', r.text)
    token_novo = m.group(1) if m else ""
    diz("  AnonymousCSRFToken:     %s" % (token_novo[:12] + "..." if token_novo else "(nao ha)"))
    diz("  igual ao da captura:    %s" % ("SIM" if token_novo and token_novo == token_capt else "nao"))

    caminho_js, accao = script_do_ecra(pedido["url"])
    diz("  script da pesquisa:     %s%s" % (caminho_js, url_versions.get(caminho_js, " (NAO esta no manifesto)")))
    api_nova = ""
    if caminho_js in url_versions:
        r = buscar(s, "GET script da pesquisa", RAIZ + caminho_js + url_versions[caminho_js])
        if r is not None:
            api_nova, pedaco = api_version_do_script(r.text, accao, versao_capt.get("apiVersion", ""))
            guardar("medicao_script_pesquisa.txt", pedaco)
            diz("  apiVersion da pesquisa: %s (captura: %s)"
                % (api_nova or "(nao encontrada)", versao_capt.get("apiVersion", "?")))
            diz("  pedaco do script:       ..." + pedaco[max(0, pedaco.find(accao) - 60):][:220].replace("\n", " ") + "...")

    api_det = ""
    if pedido_det:
        caminho_det, accao_det = script_do_ecra(pedido_det["url"])
        diz("  script do detalhe:      %s%s" % (caminho_det, url_versions.get(caminho_det, " (NAO esta no manifesto)")))
        if caminho_det in url_versions:
            r = buscar(s, "GET script do detalhe", RAIZ + caminho_det + url_versions[caminho_det])
            if r is not None:
                api_det, pedaco = api_version_do_script(
                    r.text, accao_det, (molde_det.get("versionInfo") or {}).get("apiVersion", ""))
                guardar("medicao_script_detalhe.txt", pedaco)
                diz("  apiVersion do detalhe:  %s (captura: %s)"
                    % (api_det or "(nao encontrada)",
                       (molde_det.get("versionInfo") or {}).get("apiVersion", "?")))
    diz()

    # 3. A prova: pedidos feitos so com as pecas renovadas
    diz("3. A prova, sem nada da captura a nao ser a forma do corpo")
    if not (token_novo and api_nova):
        diz("  faltam pecas (token %s, apiVersion %s): a prova nao se faz"
            % ("sim" if token_novo else "NAO", "sim" if api_nova else "NAO"))
    else:
        renovado = com_versoes(pequeno, versao_nova, api_nova)
        disparar("pesquisa, cabecalhos minimos", pedido["url"],
                 cabecalhos_minimos(token_novo, RAIZ + "/dr/home"), renovado)
        disparar("pesquisa, cabecalhos da captura", pedido["url"],
                 com_token(sem_cabecalho(pedido["headers"], "cookie"), token_novo),
                 renovado)
        # e a apiVersion errada de proposito, para confirmar que e ela que tranca
        disparar("pesquisa, apiVersion errada", pedido["url"],
                 cabecalhos_minimos(token_novo, RAIZ + "/dr/home"),
                 com_versoes(pequeno, versao_nova, "0" * 22))
    if pedido_det and token_novo and api_det:
        renovado_det = com_versoes(molde_det, versao_nova, api_det)
        disparar("detalhe, cabecalhos minimos", pedido_det["url"],
                 cabecalhos_minimos(token_novo, RAIZ + "/dr/home"), renovado_det,
                 contar_detalhe)
    diz()

    diz("Conclusao: se as linhas 'cabecalhos minimos' do ponto 3 trazem "
        "resultados, o radar renova as tres pecas sozinho com tres GETs e "
        "as capturas so servem pela forma do corpo. Se so a 'apiVersion "
        "errada' falha, esta provado que e ela a tranca.")

    guardar("medicao_captura.txt", "\n".join(linhas) + "\n")
    diz()
    diz("relatorio em %s" % os.path.relpath(RELATORIO, radar.BASE_DIR))
    return 0


if __name__ == "__main__":
    sys.exit(main())
