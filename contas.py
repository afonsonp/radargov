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

# Os dois papeis (13/09/2026, "Mudancas na plataforma RADAR"): o admin
# ve tudo e cria contas; o tester ve o trabalho (anuncios, em curso,
# mercado) e as configuracoes que sao dele (conta, interesse, alertas,
# importar dados). O que e do sistema -- indicadores, capturas, recolha,
# leitura das pecas, copias, o "Verificar agora" -- e so do admin.
PAPEIS = ("admin", "tester")

# Desde a F4 do plano multi-empresa (23/09/2026) cada conta e de UMA
# empresa (`empresa_id`), e o papel e dentro dela: o admin gere as contas
# da empresa dele, o tester trabalha. O que e do SISTEMA -- a recolha,
# as capturas, a leitura das pecas, as copias, os indicadores, os
# pedidos de acesso -- passou a ser do DONO da plataforma (`dono`), que
# e uma marca e nao um papel: o dono e tambem admin da empresa dele.


def iniciar_tabelas(c):
    c.execute("""CREATE TABLE IF NOT EXISTS utilizadores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL, nome TEXT NOT NULL DEFAULT '',
        hash TEXT NOT NULL, criado_em TEXT, ultimo_acesso TEXT,
        papel TEXT NOT NULL DEFAULT 'admin')""")
    # A coluna do papel entrou a 13/09/2026. Quem ja existia e admin:
    # ate aqui so havia uma conta, e era a do Afonso.
    cols = [r[1] for r in c.execute("PRAGMA table_info(utilizadores)")]
    if "papel" not in cols:
        c.execute("ALTER TABLE utilizadores ADD COLUMN papel TEXT "
                  "NOT NULL DEFAULT 'admin'")
    # A empresa de cada conta e a marca de dono (F4, 23/09/2026). Quem ja
    # existia e da empresa 1, que era a unica; e o dono e o primeiro
    # admin, que era o Afonso -- uma vez, quando a coluna nasce.
    if "empresa_id" not in cols:
        c.execute("ALTER TABLE utilizadores ADD COLUMN empresa_id INTEGER "
                  "NOT NULL DEFAULT 1")
    if "dono" not in cols:
        c.execute("ALTER TABLE utilizadores ADD COLUMN dono INTEGER "
                  "NOT NULL DEFAULT 0")
        c.execute("UPDATE utilizadores SET dono=1 WHERE id=(SELECT MIN(id) "
                  "FROM utilizadores WHERE papel='admin')")
    c.execute("""CREATE TABLE IF NOT EXISTS sessoes (
        token TEXT PRIMARY KEY, utilizador_id INTEGER NOT NULL,
        criada_em TEXT, expira TEXT, ip TEXT, agente TEXT)""")
    c.execute("CREATE INDEX IF NOT EXISTS ix_sessoes_util "
              "ON sessoes(utilizador_id)")
    # As falhas de login, para o trinco. Poda-se ao registar: so
    # interessam as dos ultimos quinze minutos.
    c.execute("""CREATE TABLE IF NOT EXISTS entradas_falhadas (
        quando TEXT, email TEXT, ip TEXT)""")
    # Os convites (F5, 23/09/2026): o que o dono manda a quem pediu
    # acesso. Guarda-se o RESUMO do codigo, nunca o codigo: quem lesse a
    # base nao podia usar um convite por usar.
    c.execute("""CREATE TABLE IF NOT EXISTS convites (
        resumo TEXT PRIMARY KEY, empresa_id INTEGER NOT NULL,
        email TEXT, papel TEXT NOT NULL DEFAULT 'admin', pedido_id INTEGER,
        criado_em TEXT, expira TEXT, usado_em TEXT)""")


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

def criar_utilizador(c, email, senha, nome="", papel=None, empresa_id=None):
    """Cria ou substitui a palavra-passe se o e-mail ja existir: e o
    mesmo comando que serve para recuperar o acesso pela linha de
    comandos. Devolve o id.

    O `papel` a None mantem o que ja la esta (ou 'admin' numa conta
    nova): trocar a palavra-passe nao despromove ninguem. A `empresa_id`
    a None, o mesmo -- trocar a palavra-passe nao muda ninguem de
    empresa --, e 1 numa conta nova.
    """
    email = email_limpo(email)
    if papel is not None and papel not in PAPEIS:
        raise ValueError("o tipo de utilizador tem de ser admin ou tester")
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
        c.execute("UPDATE utilizadores SET hash=?, nome=COALESCE(NULLIF(?,''), nome), "
                  "papel=COALESCE(?, papel), empresa_id=COALESCE(?, empresa_id) "
                  "WHERE id=?",
                  (hash_senha(senha), (nome or "").strip(), papel, empresa_id,
                   linha[0]))
        return linha[0]
    # O primeiro admin e o dono da plataforma, tambem numa instalacao
    # nova -- a mesma regra da migracao, que so corre quando a coluna
    # nasce e numa base vazia nao encontra ninguem.
    sem_dono = not c.execute("SELECT 1 FROM utilizadores WHERE dono=1").fetchone()
    cur = c.execute("INSERT INTO utilizadores (email, nome, hash, criado_em, papel, "
                    "empresa_id, dono) VALUES (?,?,?,?,?,?,?)",
                    (email, (nome or "").strip() or email.split("@")[0],
                     hash_senha(senha), _agora(), papel or "admin",
                     empresa_id or 1,
                     1 if sem_dono and (papel or "admin") == "admin" else 0))
    return cur.lastrowid


def utilizadores(c, empresa_id=None):
    """As contas, ou so as de uma empresa: o admin de uma empresa nao ve
    as contas das outras (F4)."""
    onde, args = ("WHERE empresa_id=?", (empresa_id,)) if empresa_id else ("", ())
    return [dict(r) for r in c.execute(
        "SELECT id, email, nome, papel, criado_em, ultimo_acesso, empresa_id, dono "
        "FROM utilizadores %s ORDER BY id" % onde, args)]


def apagar_utilizador(c, utilizador_id, empresa_id=None):
    """Tira a conta e as sessoes dela. Recusa-se a tirar o ultimo admin
    da empresa: sem admin ninguem volta a criar contas nela pelo painel.
    Com `empresa_id`, uma conta de OUTRA empresa e como se nao existisse
    -- e o que impede um admin de tirar contas alheias pelo id."""
    linha = c.execute("SELECT papel, empresa_id FROM utilizadores WHERE id=?",
                      (utilizador_id,)).fetchone()
    if not linha or (empresa_id and linha["empresa_id"] != empresa_id):
        return False
    if linha["papel"] == "admin" and c.execute(
            "SELECT COUNT(*) FROM utilizadores WHERE papel='admin' "
            "AND empresa_id=?", (linha["empresa_id"],)).fetchone()[0] <= 1:
        raise ValueError("é o único admin; cria outro antes de o tirar")
    c.execute("DELETE FROM sessoes WHERE utilizador_id=?", (utilizador_id,))
    c.execute("DELETE FROM utilizadores WHERE id=?", (utilizador_id,))
    return True


def e_admin(utilizador):
    return bool(utilizador) and utilizador.get("papel", "admin") == "admin"


def sem_empresa(utilizador):
    """O dono da plataforma sem empresa (23/09/2026): `empresa_id` 0.
    So o dono pode estar assim -- e o `apagar_empresa()` do radar que o
    deixa."""
    return bool(utilizador) and e_dono(utilizador) \
        and not utilizador.get("empresa_id")


def e_dono(utilizador):
    """O dono da plataforma: ve o que e do sistema (F4)."""
    return bool(utilizador) and bool(utilizador.get("dono"))


def unico_utilizador(c):
    """Quem e o acesso livre local: o unico utilizador se so ha um, senao
    o primeiro admin. None so sem contas.

    Ate 14/09/2026 devolvia None com mais de um utilizador ("o unico e
    mentira") -- e no dia em que o Afonso criou a primeira conta de
    tester, o painel no computador dele passou a dizer "sem conta
    ainda" e a registar tudo como "(sem nome)". O acesso livre e o
    computador dele; com varias contas, e o admin."""
    colunas = "id, email, nome, papel, empresa_id, dono"
    linhas = c.execute("SELECT %s FROM utilizadores ORDER BY id LIMIT 2"
                       % colunas).fetchall()
    if len(linhas) == 1:
        return dict(linhas[0])
    # o dono primeiro: o acesso livre e o computador dele
    admin = c.execute("SELECT %s FROM utilizadores WHERE papel='admin' "
                      "ORDER BY dono DESC, id LIMIT 1" % colunas).fetchone()
    return dict(admin) if admin else None


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


# ------------------------------------------------------------------ convites
#
# Do pedido de acesso a empresa a trabalhar (F5): o dono aceita, o radar
# cria a empresa e um convite, e a ligacao vai por e-mail. Quem a abre
# escolhe o utilizador e a palavra-passe e entra ja. Uso unico e com
# validade: uma ligacao que ficou numa caixa de correio velha nao pode
# abrir uma conta daqui a um ano.

DIAS_DE_CONVITE = 7


def _resumo(codigo):
    return hashlib.sha256((codigo or "").encode("utf-8")).hexdigest()


def criar_convite(c, empresa_id, email="", papel="admin", pedido_id=None,
                  agora=None):
    """Um convite novo. Devolve o CODIGO, que so existe aqui: na base
    fica o resumo."""
    if papel not in PAPEIS:
        raise ValueError("o tipo de utilizador tem de ser admin ou tester")
    agora = agora or datetime.now()
    codigo = secrets.token_urlsafe(32)
    c.execute("INSERT INTO convites (resumo, empresa_id, email, papel, pedido_id, "
              "criado_em, expira) VALUES (?,?,?,?,?,?,?)",
              (_resumo(codigo), empresa_id, email_limpo(email), papel, pedido_id,
               agora.strftime("%Y-%m-%d %H:%M:%S"),
               (agora + timedelta(days=DIAS_DE_CONVITE)).strftime(
                   "%Y-%m-%d %H:%M:%S")))
    return codigo


def convite_valido(c, codigo, agora=None):
    """(convite, None) se serve, ou (None, porque). O porque distingue o
    que nao existe do que ja foi usado ou passou do prazo -- a quem tem
    a ligacao certa, dizer-lhe porque e que ja nao serve."""
    agora = agora or datetime.now()
    linha = c.execute("SELECT * FROM convites WHERE resumo=?",
                      (_resumo(codigo),)).fetchone()
    if not linha:
        return None, "este convite não existe"
    if linha["usado_em"]:
        return None, "este convite já foi usado"
    if linha["expira"] <= agora.strftime("%Y-%m-%d %H:%M:%S"):
        return None, "este convite passou do prazo"
    return dict(linha), None


def usar_convite(c, codigo, utilizador, senha, ip="", agente="", agora=None):
    """Cria a conta do convite e entra. Devolve (token de sessao, None)
    ou (None, porque). Tudo na mesma ligacao: ou fica a conta, o convite
    gasto e a sessao, ou nao fica nada."""
    agora = agora or datetime.now()
    convite, porque = convite_valido(c, codigo, agora)
    if not convite:
        return None, porque
    if c.execute("SELECT 1 FROM utilizadores WHERE email=?",
                 (email_limpo(utilizador),)).fetchone():
        return None, "já existe um utilizador com esse nome; escolhe outro"
    criar_utilizador(c, utilizador, senha, papel=convite["papel"],
                     empresa_id=convite["empresa_id"])
    c.execute("UPDATE convites SET usado_em=? WHERE resumo=?",
              (agora.strftime("%Y-%m-%d %H:%M:%S"), convite["resumo"]))
    token, _ = entrar(c, utilizador, senha, ip, agente, agora)
    return token, None


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
    linha = c.execute("SELECT id, email, nome, papel, hash, empresa_id, dono "
                      "FROM utilizadores WHERE email=?", (email,)).fetchone()
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
                   "nome": linha["nome"], "papel": linha["papel"],
                   "empresa_id": linha["empresa_id"], "dono": linha["dono"]}


def utilizador_da_sessao(c, token, agora=None):
    """O utilizador de uma sessao valida, ou None. Uma sessao valida
    desliza: o fim passa a ser daqui a DIAS_DE_SESSAO. Uma expirada
    apaga-se ao ser encontrada, para a tabela nao crescer."""
    if not token:
        return None
    agora = agora or datetime.now()
    linha = c.execute(
        "SELECT s.expira, u.id, u.email, u.nome, u.papel, u.empresa_id, "
        "u.dono FROM sessoes s "
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
            "nome": linha["nome"], "papel": linha["papel"],
            "empresa_id": linha["empresa_id"], "dono": linha["dono"]}


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
