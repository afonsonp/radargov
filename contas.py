# -*- coding: utf-8 -*-
"""As contas: quem pode entrar no painel, e as sessoes de quem entrou.

Etapa 1 do docs/historico/ONLINE.md (8/09/2026). Um utilizador, uma
palavra-passe, sessoes no servidor. E tabela e nao chave do config.json
porque um segundo utilizador ha-de ser uma linha, nao uma reescrita --
e porque a palavra-passe nao pode viver num ficheiro que se abre sem
pensar.

Segundo modulo fora do radar.py, ao molde do casa.py: as suas tabelas,
o seu `iniciar_tabelas(c)` chamado de `iniciar_db()`, os seus testes.
Nao importa o radar: tudo o que precisa e uma ligacao aberta, que quem
chama lhe passa. Assim os testes correm sobre uma base em memoria.

O que aqui NAO esta, de proposito: o que e do pedido HTTP (cookies,
redireccionamentos, o `before_request`) vive no radar.py, na banda
`pessoas`. Este modulo so sabe de tabelas e de criptografia.
"""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta

# scrypt da biblioteca padrao: sem dependencia nova. n=2**14 e o que o
# OWASP recomenda para 2024+; demora ~50 ms por verificacao neste PC,
# o suficiente para um ataque de forca bruta ser caro e um login nao.
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1

# Trinta dias deslizantes: cada pedido com sessao valida empurra o fim
# para a frente. Quem usa o painel todos os dias nunca ve o login; quem
# o deixa um mes ve-o uma vez.
DIAS_DE_SESSAO = 30

# O trinco ao login: cinco falhas em quinze minutos, por e-mail ou por
# IP, e a resposta passa a esperar.
FALHAS_ATE_TRINCO = 5
MINUTOS_DE_TRINCO = 15


def iniciar_tabelas(c):
    c.execute("""CREATE TABLE IF NOT EXISTS utilizadores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL, nome TEXT NOT NULL DEFAULT '',
        hash TEXT NOT NULL, criado_em TEXT, ultimo_acesso TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS sessoes (
        token TEXT PRIMARY KEY, utilizador_id INTEGER NOT NULL,
        criada_em TEXT, expira TEXT, ip TEXT, agente TEXT)""")
    c.execute("CREATE INDEX IF NOT EXISTS ix_sessoes_util "
              "ON sessoes(utilizador_id)")
    # As falhas de login, para o trinco. Poda-se ao registar: so
    # interessam as dos ultimos quinze minutos.
    c.execute("""CREATE TABLE IF NOT EXISTS entradas_falhadas (
        quando TEXT, email TEXT, ip TEXT)""")


# ------------------------------------------------------------ palavra-passe

def hash_senha(senha):
    """`scrypt$sal$hash`, tudo em hexadecimal. O sal e novo de cada vez."""
    sal = os.urandom(16)
    digest = hashlib.scrypt(senha.encode("utf-8"), salt=sal,
                            n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return "scrypt$%s$%s" % (sal.hex(), digest.hex())


def verifica_senha(senha, guardado):
    """True se a senha bate com o que esta guardado. Nunca levanta:
    um registo estragado e uma senha errada, nao um erro 500."""
    try:
        esquema, sal, digest = (guardado or "").split("$")
        if esquema != "scrypt":
            return False
        calculado = hashlib.scrypt(senha.encode("utf-8"),
                                   salt=bytes.fromhex(sal),
                                   n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
        return hmac.compare_digest(calculado, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False


def _agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def email_limpo(email):
    return (email or "").strip().lower()


# --------------------------------------------------------------- utilizadores

def criar_utilizador(c, email, senha, nome=""):
    """Cria ou substitui a palavra-passe se o e-mail ja existir: e o
    mesmo comando que serve para recuperar o acesso pela linha de
    comandos. Devolve o id."""
    email = email_limpo(email)
    # Um nome de utilizador chega ("admin"): o Afonso nao quer e-mail
    # (8/09/2026). A coluna continua a chamar-se `email` -- e o que
    # identifica a conta, seja um e-mail ou nao.
    if not email or " " in email or len(email) < 2:
        raise ValueError("utilizador em falta, com espacos ou curto demais")
    if len(senha or "") < 8:
        raise ValueError("a palavra-passe tem de ter pelo menos 8 caracteres")
    linha = c.execute("SELECT id FROM utilizadores WHERE email=?",
                      (email,)).fetchone()
    if linha:
        c.execute("UPDATE utilizadores SET hash=?, nome=COALESCE(NULLIF(?,''), nome) "
                  "WHERE id=?", (hash_senha(senha), (nome or "").strip(), linha[0]))
        return linha[0]
    cur = c.execute("INSERT INTO utilizadores (email, nome, hash, criado_em) "
                    "VALUES (?,?,?,?)",
                    (email, (nome or "").strip() or email.split("@")[0],
                     hash_senha(senha), _agora()))
    return cur.lastrowid


def utilizadores(c):
    return [dict(r) for r in c.execute(
        "SELECT id, email, nome, criado_em, ultimo_acesso "
        "FROM utilizadores ORDER BY id")]


def unico_utilizador(c):
    """O unico utilizador, para o acesso livre local. None se nao houver
    nenhum -- ou se houver mais do que um, porque ai 'o unico' e mentira
    e o acesso livre deixa de saber quem e."""
    linhas = c.execute("SELECT id, email, nome FROM utilizadores "
                       "LIMIT 2").fetchall()
    return dict(linhas[0]) if len(linhas) == 1 else None


# -------------------------------------------------------------------- trinco

def segundos_de_trinco(c, email, ip, agora=None):
    """Quantos segundos faltam para o trinco abrir: 0 se nao ha trinco.

    Conta as falhas dos ultimos MINUTOS_DE_TRINCO por e-mail OU por IP;
    a partir de FALHAS_ATE_TRINCO a porta fecha ate a falha mais antiga
    da janela sair dela.
    """
    agora = agora or datetime.now()
    limite = (agora - timedelta(minutes=MINUTOS_DE_TRINCO)).strftime(
        "%Y-%m-%d %H:%M:%S")
    linhas = c.execute(
        "SELECT quando FROM entradas_falhadas WHERE quando > ? "
        "AND (email=? OR ip=?) ORDER BY quando",
        (limite, email_limpo(email), ip or "")).fetchall()
    if len(linhas) < FALHAS_ATE_TRINCO:
        return 0
    # a janela abre quando a falha que faz a quinta a contar do fim sair
    # dos quinze minutos
    primeira = datetime.strptime(linhas[-FALHAS_ATE_TRINCO][0],
                                 "%Y-%m-%d %H:%M:%S")
    abre = primeira + timedelta(minutes=MINUTOS_DE_TRINCO)
    return max(1, int((abre - agora).total_seconds()))


def registar_falha(c, email, ip, agora=None):
    agora = agora or datetime.now()
    c.execute("INSERT INTO entradas_falhadas VALUES (?,?,?)",
              (agora.strftime("%Y-%m-%d %H:%M:%S"), email_limpo(email),
               ip or ""))
    poda = (agora - timedelta(minutes=MINUTOS_DE_TRINCO * 4)).strftime(
        "%Y-%m-%d %H:%M:%S")
    c.execute("DELETE FROM entradas_falhadas WHERE quando < ?", (poda,))


# ------------------------------------------------------------------- sessoes

def entrar(c, email, senha, ip="", agente="", agora=None):
    """Tenta entrar. Devolve (token, utilizador) ou (None, porque).

    O `porque` e texto para o ecra: 'espera N s' quando o trinco esta
    fechado, 'utilizador ou palavra-passe errados' no resto -- a mesma
    frase para os dois casos, para nao dizer a quem tenta quais os
    e-mails que existem.
    """
    agora = agora or datetime.now()
    email = email_limpo(email)
    espera = segundos_de_trinco(c, email, ip, agora)
    if espera:
        return None, "demasiadas tentativas; espera %d s" % espera
    linha = c.execute("SELECT id, email, nome, hash FROM utilizadores "
                      "WHERE email=?", (email,)).fetchone()
    if not linha or not verifica_senha(senha or "", linha["hash"]):
        registar_falha(c, email, ip, agora)
        return None, "utilizador ou palavra-passe errados"
    token = secrets.token_urlsafe(32)
    c.execute("INSERT INTO sessoes VALUES (?,?,?,?,?,?)",
              (token, linha["id"], agora.strftime("%Y-%m-%d %H:%M:%S"),
               (agora + timedelta(days=DIAS_DE_SESSAO)).strftime(
                   "%Y-%m-%d %H:%M:%S"), ip or "", (agente or "")[:200]))
    c.execute("UPDATE utilizadores SET ultimo_acesso=? WHERE id=?",
              (agora.strftime("%Y-%m-%d %H:%M:%S"), linha["id"]))
    return token, {"id": linha["id"], "email": linha["email"],
                   "nome": linha["nome"]}


def utilizador_da_sessao(c, token, agora=None):
    """O utilizador de uma sessao valida, ou None. Uma sessao valida
    desliza: o fim passa a ser daqui a DIAS_DE_SESSAO. Uma expirada
    apaga-se ao ser encontrada, para a tabela nao crescer."""
    if not token:
        return None
    agora = agora or datetime.now()
    linha = c.execute(
        "SELECT s.expira, u.id, u.email, u.nome FROM sessoes s "
        "JOIN utilizadores u ON u.id = s.utilizador_id WHERE s.token=?",
        (token,)).fetchone()
    if not linha:
        return None
    if linha["expira"] <= agora.strftime("%Y-%m-%d %H:%M:%S"):
        c.execute("DELETE FROM sessoes WHERE token=?", (token,))
        return None
    c.execute("UPDATE sessoes SET expira=? WHERE token=?",
              ((agora + timedelta(days=DIAS_DE_SESSAO)).strftime(
                  "%Y-%m-%d %H:%M:%S"), token))
    return {"id": linha["id"], "email": linha["email"],
            "nome": linha["nome"]}


def sair(c, token):
    c.execute("DELETE FROM sessoes WHERE token=?", (token or "",))


def sair_de_todos(c, utilizador_id):
    """Fecha todas as sessoes do utilizador. Devolve quantas eram."""
    n = c.execute("SELECT COUNT(*) FROM sessoes WHERE utilizador_id=?",
                  (utilizador_id,)).fetchone()[0]
    c.execute("DELETE FROM sessoes WHERE utilizador_id=?", (utilizador_id,))
    return n


def sessoes_de(c, utilizador_id):
    return [dict(r) for r in c.execute(
        "SELECT token, criada_em, expira, ip, agente FROM sessoes "
        "WHERE utilizador_id=? ORDER BY criada_em DESC", (utilizador_id,))]


# ---------------------------------------------------------------------- csrf

def token_csrf(token_sessao):
    """O token contra pedidos forjados, derivado da sessao: nao se guarda
    nada, e um cookie roubado sem o token continua a nao servir para um
    POST feito de outro sitio."""
    return hmac.new(b"csrf:" + (token_sessao or "").encode("utf-8"),
                    b"radar", hashlib.sha256).hexdigest()


def csrf_bate(token_sessao, apresentado):
    return bool(apresentado) and hmac.compare_digest(
        token_csrf(token_sessao), str(apresentado))
