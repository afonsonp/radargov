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
    # O aspecto de cada pessoa (D14 da segunda ronda, 26/09/2026): o tema
    # de alto contraste, escolhido na conta e nao no browser -- quem o
    # precisa leva-o para todos os aparelhos. So «normal» e «contraste»:
    # o escuro nao se oferece enquanto o subtitulo tiver 1,4:1 nele.
    if "aspecto" not in cols:
        c.execute("ALTER TABLE utilizadores ADD COLUMN aspecto TEXT "
                  "NOT NULL DEFAULT 'normal'")
    c.execute("""CREATE TABLE IF NOT EXISTS sessoes (
        token TEXT PRIMARY KEY, utilizador_id INTEGER NOT NULL,
        criada_em TEXT, expira TEXT, ip TEXT, agente TEXT)""")
    # A empresa que o dono esta a ver, so para ler (a pagina do dono,
    # 26/09/2026): e da SESSAO e nao da conta -- o suporte num aparelho
    # nao muda o que o dono ve no outro, e sair fecha-o.
    if "ver_como" not in [r[1] for r in c.execute("PRAGMA table_info(sessoes)")]:
        c.execute("ALTER TABLE sessoes ADD COLUMN ver_como INTEGER")
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
    # Anular um convite (a pagina do dono, 26/09/2026): um convite que
    # foi para o endereco errado tinha de esperar sete dias. Fica a linha,
    # com a data, e o codigo deixa de servir.
    if "anulado_em" not in [r[1] for r in c.execute("PRAGMA table_info(convites)")]:
        c.execute("ALTER TABLE convites ADD COLUMN anulado_em TEXT")
    # As ligacoes para repor a palavra-passe (D17, 26/09/2026): o mesmo
    # molde dos convites -- so o resumo, prazo, uso unico --, mas para
    # uma conta que ja existe. Tabela a parte, e nao uma coluna nos
    # convites: um convite cria contas, e a rota dele nao pode nunca
    # aceitar um codigo que troca a palavra-passe de alguem.
    c.execute("""CREATE TABLE IF NOT EXISTS reposicoes (
        resumo TEXT PRIMARY KEY, utilizador_id INTEGER NOT NULL,
        criado_por INTEGER, criado_em TEXT, expira TEXT, usado_em TEXT)""")


# ------------------------------------------------------------ palavra-passe

# D16 (26/09/2026, o 19 da segunda ronda criou contas com `aaaaaaaa`,
# `12345678` e o proprio nome): as mais comuns. Nao sao as dez mil --
# sao as que aparecem no topo de todas as listas publicas, mais as
# portuguesas. O resto apanha-se pelos padroes (`_padrao_fraco()`): uma
# lista embutida de dez mil entradas era um ficheiro de 80 KB para
# apanhar sobretudo variacoes que os padroes ja apanham.
SENHAS_COMUNS = frozenset("""
password passw0rd password1 password12 password123 p@ssw0rd p@ssword
qwerty qwertyuiop qwerty123 qwerty1234 azerty azertyuiop asdfghjkl
asdfasdf zxcvbnm 1q2w3e4r 1q2w3e4r5t 1qaz2wsx qazwsxedc zaq12wsx
iloveyou letmein welcome welcome1 monkey dragon football baseball
sunshine princess master superman batman trustno1 starwars whatever
shadow michael jennifer computer internet abc12345 abcd1234 changeme
admin admin123 admin1234 administrator root toor secret secret123
senha senha123 senha1234 palavra palavrapasse palavra-passe
portugal portugal1 benfica benfica1 sporting porto fcporto slbenfica
lisboa coimbra braga amor amoreterno saudade cristiano ronaldo
bemvindo benvindo entrar mudar mudar123 alterar teste teste123
teste1234 testes utilizador utilizador1 mira miragov radar radargov
concursos concurso empresa empresa1 geral contabilidade
""".split())

# O que se escreve correndo os dedos: as filas do teclado e o alfabeto,
# nos dois sentidos. Uma palavra-passe que caiba inteira dentro de uma
# destas e uma sequencia.
_SEQUENCIAS = ("01234567890123456789", "abcdefghijklmnopqrstuvwxyz",
               "qwertyuiopasdfghjklzxcvbnm", "azertyuiopqsdfghjklmwxcvbn",
               "1qaz2wsx3edc4rfv5tgb6yhn", "qazwsxedcrfvtgbyhnujmikolp")


def _padrao_fraco(minusculas):
    """Porque e que a palavra-passe e um padrao, ou ''."""
    if len(set(minusculas)) == 1:
        return "é um só carácter repetido"
    for passo in range(2, 5):
        pedaco = minusculas[:passo]
        if (pedaco * (len(minusculas) // passo + 1))[:len(minusculas)] == minusculas:
            return "é um pedaço repetido («%s»)" % pedaco
    for seq in _SEQUENCIAS:
        if minusculas in seq or minusculas in seq[::-1]:
            return "é uma sequência do teclado ou do alfabeto"
    return ""


def problema_da_senha(senha, utilizador=""):
    """Porque e que esta palavra-passe nao serve, ou '' se serve (D16).

    Oito caracteres ou mais, e nao so espacos; nao uma das mais comuns,
    nem com numeros ou sinais a volta ("Benfica2026!"); nao um padrao;
    e sem o nome do utilizador nem o e-mail dentro. A frase vai para o
    ecra: quem a le tem de saber o que mudar."""
    senha = senha or ""
    if len(senha) < 8:
        return "a palavra-passe tem de ter pelo menos 8 caracteres"
    # Oito espacos eram oito caracteres (teste com utilizadores,
    # 25/09/2026). Os espacos continuam a contar numa frase-passe: o que
    # se recusa e a que nao tem mais nada.
    if len(senha.strip()) < 8:
        return ("a palavra-passe tem de ter pelo menos 8 caracteres "
                "além dos espaços")
    minusculas = senha.lower()
    miolo = minusculas.strip("0123456789!?.,;:-_@#$%&*+=/ ")
    if minusculas in SENHAS_COMUNS or miolo in SENHAS_COMUNS:
        return ("essa palavra-passe está entre as mais usadas, e é das "
                "primeiras que se tentam; escolhe outra")
    padrao = _padrao_fraco(minusculas) or (
        _padrao_fraco(miolo) if len(miolo) >= 4 else "")
    if padrao or not miolo:
        return ("a palavra-passe %s, e adivinha-se depressa; escolhe outra"
                % (padrao or "é só números e sinais"))
    utilizador = email_limpo(utilizador)
    partes = {utilizador, utilizador.split("@")[0]}
    if any(len(p) >= 3 and p in minusculas for p in partes):
        return ("a palavra-passe não pode ter o nome de utilizador (nem o "
                "e-mail) lá dentro")
    return ""


def verificar_senha_nova(senha, utilizador=""):
    """`problema_da_senha()` como ValueError, para quem grava."""
    problema = problema_da_senha(senha, utilizador)
    if problema:
        raise ValueError(problema)

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

def criar_utilizador(c, email, senha, nome="", papel=None, empresa_id=None,
                     pela_consola=False):
    """Cria ou substitui a palavra-passe se o e-mail ja existir: e o
    mesmo comando que serve para recuperar o acesso pela linha de
    comandos. Devolve o id.

    O `papel` a None mantem o que ja la esta (ou 'admin' numa conta
    nova): trocar a palavra-passe nao despromove ninguem. A `empresa_id`
    a None, o mesmo -- trocar a palavra-passe nao muda ninguem de
    empresa --, e 1 numa conta nova.

    `pela_consola`: so o `--criar-utilizador` o passa. E so assim nasce
    um dono (F2 da segunda ronda, 26/09/2026, decisao dele): o primeiro
    admin de uma base sem dono era dono viesse de onde viesse -- e um
    admin de empresa que conseguisse deixar a base sem dono ficava com
    a plataforma ao criar a conta seguinte, pelo painel ou por convite.
    """
    email = email_limpo(email)
    if papel is not None and papel not in PAPEIS:
        raise ValueError("o tipo de utilizador tem de ser admin ou tester")
    # Um nome de utilizador chega ("admin"): o Afonso nao quer e-mail
    # (8/09/2026). A coluna continua a chamar-se `email` -- e o que
    # identifica a conta, seja um e-mail ou nao.
    # Uma causa de cada vez (segunda ronda, 26/09/2026): «em falta, com
    # espacos ou curto demais» deixava a pessoa a adivinhar qual.
    if not email:
        raise ValueError("o nome de utilizador está em falta")
    if " " in email:
        raise ValueError("o nome de utilizador não pode ter espaços")
    if len(email) < 2:
        raise ValueError("o nome de utilizador é curto demais (2 caracteres "
                         "ou mais)")
    # A politica inteira (D16) vive num sitio so, e todas passam aqui: a
    # conta, o convite, a consola e a ligacao de repor.
    verificar_senha_nova(senha, email)
    linha = c.execute("SELECT id FROM utilizadores WHERE email=?",
                      (email,)).fetchone()
    if linha:
        c.execute("UPDATE utilizadores SET hash=?, nome=COALESCE(NULLIF(?,''), nome), "
                  "papel=COALESCE(?, papel), empresa_id=COALESCE(?, empresa_id) "
                  "WHERE id=?",
                  (hash_senha(senha), (nome or "").strip(), papel, empresa_id,
                   linha[0]))
        return linha[0]
    # O primeiro admin criado PELA CONSOLA numa base sem dono e o dono da
    # plataforma -- a regra da migracao, que so corre quando a coluna
    # nasce e numa base vazia nao encontra ninguem. Do painel, de um
    # convite ou de uma reposicao nunca nasce um dono.
    sem_dono = pela_consola and not c.execute(
        "SELECT 1 FROM utilizadores WHERE dono=1").fetchone()
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


def apagar_utilizador(c, utilizador_id, empresa_id=None, quem=None):
    """Tira a conta e as sessoes dela. Recusa-se a tirar o ultimo admin
    da empresa: sem admin ninguem volta a criar contas nela pelo painel.
    Com `empresa_id`, uma conta de OUTRA empresa e como se nao existisse
    -- e o que impede um admin de tirar contas alheias pelo id.

    A conta do dono da plataforma so a tira o dono, e o ultimo dono
    nunca (26/09/2026): ate ai, o admin de uma empresa onde o dono tinha
    a conta tirava-o pelo botao «tirar» -- e o proximo admin criado
    numa base sem dono nascia dono (`criar_utilizador()`). Sem `quem`
    (a consola, os testes) vale o mesmo: a conta do dono nao sai. Com
    `quem`, e a regra do `pode_repor()`: o dono tira qualquer uma, o
    admin so as da empresa dele, o tester nenhuma."""
    linha = c.execute("SELECT papel, empresa_id, dono FROM utilizadores WHERE id=?",
                      (utilizador_id,)).fetchone()
    if not linha or (empresa_id and linha["empresa_id"] != empresa_id):
        return False
    if linha["dono"] and not e_dono(quem):
        raise ValueError("a conta do dono da plataforma só o dono a tira")
    if linha["dono"] and c.execute(
            "SELECT COUNT(*) FROM utilizadores WHERE dono=1").fetchone()[0] <= 1:
        raise ValueError("é o único dono da plataforma; não se tira")
    if quem is not None and not pode_repor(quem, dict(linha)):
        raise ValueError("só o admin da empresa tira contas")
    if linha["papel"] == "admin" and c.execute(
            "SELECT COUNT(*) FROM utilizadores WHERE papel='admin' "
            "AND empresa_id=?", (linha["empresa_id"],)).fetchone()[0] <= 1:
        raise ValueError("é o único admin; cria outro antes de o tirar")
    c.execute("DELETE FROM sessoes WHERE utilizador_id=?", (utilizador_id,))
    c.execute("DELETE FROM reposicoes WHERE utilizador_id=?", (utilizador_id,))
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


# Os aspectos que a conta oferece, e o `data-theme` que cada um carimba.
ASPECTOS = {"normal": "claro", "contraste": "contraste"}


def gravar_aspecto(c, utilizador_id, aspecto):
    """Grava o aspecto de uma conta. Recusa o que nao esta em ASPECTOS:
    o valor vai parar a um atributo do HTML."""
    if aspecto not in ASPECTOS:
        raise ValueError("aspecto desconhecido")
    c.execute("UPDATE utilizadores SET aspecto=? WHERE id=?",
              (aspecto, utilizador_id))


def unico_utilizador(c):
    """Quem e o acesso livre local: o unico utilizador se so ha um, senao
    o primeiro admin. None so sem contas.

    Ate 14/09/2026 devolvia None com mais de um utilizador ("o unico e
    mentira") -- e no dia em que o Afonso criou a primeira conta de
    tester, o painel no computador dele passou a dizer "sem conta
    ainda" e a registar tudo como "(sem nome)". O acesso livre e o
    computador dele; com varias contas, e o admin."""
    colunas = "id, email, nome, papel, empresa_id, dono, aspecto"
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
    if linha["anulado_em"]:
        return None, "este convite foi anulado; peça outro a quem o mandou"
    if linha["expira"] <= agora.strftime("%Y-%m-%d %H:%M:%S"):
        return None, "este convite passou do prazo"
    return dict(linha), None


def convites_por_usar(c, empresa_id=None):
    """Os convites que ninguem usou nem anulou -- tambem os que passaram
    do prazo, que se mostram como tal: e o que o dono quer ver para
    gerar outro. O `id` e o rowid da linha: o resumo nunca vai para um
    formulario."""
    onde, args = ("AND empresa_id=?", (empresa_id,)) if empresa_id else ("", ())
    return [dict(r) for r in c.execute(
        "SELECT rowid AS id, empresa_id, email, papel, pedido_id, criado_em, "
        "expira FROM convites WHERE usado_em IS NULL AND anulado_em IS NULL "
        "%s ORDER BY criado_em DESC" % onde, args)]


def _convite_por_id(c, id_, empresa_id=None):
    linha = c.execute("SELECT rowid AS id, * FROM convites WHERE rowid=? "
                      "AND usado_em IS NULL AND anulado_em IS NULL",
                      (id_,)).fetchone()
    if not linha or (empresa_id and linha["empresa_id"] != empresa_id):
        return None
    return dict(linha)


def anular_convite(c, id_, empresa_id=None, agora=None):
    """Anula um convite por usar. Com `empresa_id`, um convite de OUTRA
    empresa e como se nao existisse (o admin so anula os da dele).
    Devolve o convite anulado, ou None."""
    convite = _convite_por_id(c, id_, empresa_id)
    if not convite:
        return None
    c.execute("UPDATE convites SET anulado_em=? WHERE rowid=?",
              ((agora or datetime.now()).strftime("%Y-%m-%d %H:%M:%S"), id_))
    return convite


def renovar_convite(c, id_, empresa_id=None, agora=None):
    """Anula o convite e cria outro igual (empresa, e-mail, tipo e
    pedido), com prazo novo. Devolve o CODIGO novo, ou None. E o
    «gerar de novo»: a ligacao antiga nao se volta a ver -- so o resumo
    ficou --, e reenviar e mandar esta."""
    convite = anular_convite(c, id_, empresa_id, agora)
    if not convite:
        return None
    return criar_convite(c, convite["empresa_id"], convite["email"] or "",
                         convite["papel"], convite["pedido_id"], agora)


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


# ---------------------------------------------------------------- reposicoes
#
# O "esqueci-me" (D17, 26/09/2026). Sem correio ligado nao ha e-mail de
# recuperacao: quem repoe e uma pessoa -- o admin da empresa, para as
# contas dela, ou o dono da plataforma, para qualquer uma --, que gera
# uma ligacao e a entrega a mao. O molde e o do convite: 32 bytes, so o
# resumo na base, prazo e uso unico.

HORAS_DE_REPOSICAO = 24


def pode_repor(quem, alvo):
    """Se `quem` pode gerar a ligacao de repor para a conta `alvo` (os
    dois como dicts com `empresa_id`, `papel` e `dono`). O dono repoe
    qualquer uma; o admin so as da empresa dele, e nunca a do dono; o
    tester nenhuma."""
    if not quem or not alvo:
        return False
    if e_dono(quem):
        return True
    # A conta do dono nunca, mesmo sendo da empresa do admin: repor-lha
    # era entrar como dono da plataforma inteira.
    if e_dono(alvo):
        return False
    return e_admin(quem) and bool(quem.get("empresa_id")) \
        and quem.get("empresa_id") == alvo.get("empresa_id")


def criar_reposicao(c, utilizador_id, criado_por=None, agora=None):
    """Uma ligacao nova para repor a palavra-passe da conta. Devolve o
    CODIGO, que so existe aqui. As ligacoes anteriores da mesma conta
    que ainda nao se usaram deixam de servir: so a ultima vale."""
    agora = agora or datetime.now()
    codigo = secrets.token_urlsafe(32)
    c.execute("DELETE FROM reposicoes WHERE utilizador_id=? AND usado_em IS NULL",
              (utilizador_id,))
    c.execute("INSERT INTO reposicoes (resumo, utilizador_id, criado_por, "
              "criado_em, expira) VALUES (?,?,?,?,?)",
              (_resumo(codigo), utilizador_id, criado_por,
               agora.strftime("%Y-%m-%d %H:%M:%S"),
               (agora + timedelta(hours=HORAS_DE_REPOSICAO)).strftime(
                   "%Y-%m-%d %H:%M:%S")))
    return codigo


def reposicao_valida(c, codigo, agora=None):
    """(reposicao com o `email` da conta, None) se serve, ou (None,
    porque). Uma conta que entretanto saiu faz a ligacao nao existir."""
    agora = agora or datetime.now()
    linha = c.execute(
        "SELECT r.*, u.email FROM reposicoes r JOIN utilizadores u "
        "ON u.id = r.utilizador_id WHERE r.resumo=?",
        (_resumo(codigo),)).fetchone()
    if not linha:
        return None, "esta ligação não existe"
    if linha["usado_em"]:
        return None, "esta ligação já foi usada"
    if linha["expira"] <= agora.strftime("%Y-%m-%d %H:%M:%S"):
        return None, "esta ligação passou do prazo"
    return dict(linha), None


def usar_reposicao(c, codigo, senha, ip="", agente="", agora=None):
    """Troca a palavra-passe, fecha TODAS as sessoes da conta (quem a
    tinha roubado deixa de a ter) e abre uma nova para quem repos.
    Devolve (token, None) ou (None, porque); a politica da palavra-passe
    levanta ValueError, como no `criar_utilizador()`."""
    agora = agora or datetime.now()
    reposicao, porque = reposicao_valida(c, codigo, agora)
    if not reposicao:
        return None, porque
    criar_utilizador(c, reposicao["email"], senha)
    c.execute("UPDATE reposicoes SET usado_em=? WHERE resumo=?",
              (agora.strftime("%Y-%m-%d %H:%M:%S"), reposicao["resumo"]))
    sair_de_todos(c, reposicao["utilizador_id"])
    token, _ = entrar(c, reposicao["email"], senha, ip, agente, agora)
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
    linha = c.execute("SELECT id, email, nome, papel, hash, empresa_id, dono, "
                      "aspecto FROM utilizadores WHERE email=?",
                      (email,)).fetchone()
    if not linha or not verifica_senha(senha or "", linha["hash"]):
        registar_falha(c, email, ip, agora)
        return None, "utilizador ou palavra-passe errados"
    token = secrets.token_urlsafe(32)
    c.execute("INSERT INTO sessoes (token, utilizador_id, criada_em, expira, ip, agente) "
              "VALUES (?,?,?,?,?,?)",
              (token, linha["id"], agora.strftime("%Y-%m-%d %H:%M:%S"),
               (agora + timedelta(days=DIAS_DE_SESSAO)).strftime(
                   "%Y-%m-%d %H:%M:%S"), ip or "", (agente or "")[:200]))
    c.execute("UPDATE utilizadores SET ultimo_acesso=? WHERE id=?",
              (agora.strftime("%Y-%m-%d %H:%M:%S"), linha["id"]))
    return token, {"id": linha["id"], "email": linha["email"],
                   "nome": linha["nome"], "papel": linha["papel"],
                   "empresa_id": linha["empresa_id"], "dono": linha["dono"],
                   "aspecto": linha["aspecto"]}


def utilizador_da_sessao(c, token, agora=None):
    """O utilizador de uma sessao valida, ou None. Uma sessao valida
    desliza: o fim passa a ser daqui a DIAS_DE_SESSAO. Uma expirada
    apaga-se ao ser encontrada, para a tabela nao crescer."""
    if not token:
        return None
    agora = agora or datetime.now()
    linha = c.execute(
        "SELECT s.expira, u.id, u.email, u.nome, u.papel, u.empresa_id, "
        "u.dono, u.aspecto, s.ver_como FROM sessoes s "
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
            "empresa_id": linha["empresa_id"], "dono": linha["dono"],
            "aspecto": linha["aspecto"],
            # so o dono ve como outra empresa: numa conta que deixou de
            # ser dono, uma marca que ficou na sessao nao vale nada
            "ver_como": linha["ver_como"] if linha["dono"] else None}


def marcar_ver_como(c, token, empresa_id):
    """Poe (ou tira, com None) a empresa que o dono esta a ver nesta
    sessao, so para ler. Quem pode e decide o radar; isto so grava."""
    c.execute("UPDATE sessoes SET ver_como=? WHERE token=?",
              (empresa_id, token or ""))


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
