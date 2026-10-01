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
import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from datetime import datetime, timedelta

# scrypt da biblioteca padrao: sem dependencia nova. n=2**14 e o que o
# OWASP recomenda para 2024+; demora ~50 ms por verificacao neste PC,
# o suficiente para um ataque de forca bruta ser caro e um login nao.
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1

# Trinta dias deslizantes: cada pedido com sessao valida empurra o fim
# para a frente. Quem usa o painel todos os dias nunca ve o login; quem
# o deixa um mes ve-o uma vez.
DIAS_DE_SESSAO = 30

# O trinco ao login (D2 da 3.ª ronda, 29/09/2026): cinco falhas em
# quinze minutos POR CONTA, e um tecto muito mais alto POR IP. Era cinco
# por conta OU por IP, e um escritorio e um IP so: um colega que errasse
# cinco vezes (ou cinco ligacoes de repor velhas) fechava a porta a
# todos. O tecto do IP fica para quem experimenta contas ao calhas.
FALHAS_ATE_TRINCO = 5
FALHAS_ATE_TRINCO_DO_IP = 30
MINUTOS_DE_TRINCO = 15
# As ligacoes de repor com codigo errado tem trinco proprio, com esta
# chave e o IP (`repor:<ip>`), e NAO contam no tecto do IP do login
# (G50): cinco aberturas de uma ligacao expirada fechavam a entrada ao
# escritorio inteiro.
PREFIXO_DO_REPOR = "repor:"

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
    # O segundo factor (28/09/2026): o segredo da app de autenticacao, o
    # dia em que ficou ligado (NULL = preparado mas por confirmar, ou
    # desligado) e o ultimo passo de tempo aceite, para o mesmo codigo
    # nao servir duas vezes. O segredo vive em claro -- o TOTP precisa
    # dele para calcular, nao ha resumo que sirva --, como os tokens das
    # sessoes: quem le a base ja esta do lado de dentro.
    cols = [r[1] for r in c.execute("PRAGMA table_info(utilizadores)")]
    for coluna, tipo in (("totp_segredo", "TEXT"), ("totp_ligado_em", "TEXT"),
                         ("totp_passo", "INTEGER NOT NULL DEFAULT 0")):
        if coluna not in cols:
            c.execute("ALTER TABLE utilizadores ADD COLUMN %s %s" % (coluna, tipo))
    # E o que o segundo factor da, numa tabela so, pelo `tipo`: o pedido
    # PENDENTE (a palavra-passe esta certa, falta o codigo), o APARELHO de
    # confianca, e os codigos de RECUPERACAO. Os tres sao o molde dos
    # convites: so o resumo, prazo, uso unico.
    c.execute("""CREATE TABLE IF NOT EXISTS segundo_factor (
        resumo TEXT PRIMARY KEY, utilizador_id INTEGER NOT NULL,
        tipo TEXT NOT NULL, criado_em TEXT, expira TEXT, usado_em TEXT,
        tentativas INTEGER NOT NULL DEFAULT 0)""")
    c.execute("CREATE INDEX IF NOT EXISTS ix_segundo_factor_util "
              "ON segundo_factor(utilizador_id, tipo)")
    # O plano de cada empresa (L2.1 do plano de Outubro, com os planos de
    # 1/10/2026: Solo, Duo e Corporate). E da plataforma, como as
    # contas: vive aqui e nao no ficheiro da empresa. Sem linha, a empresa
    # nao tem plano e nao tem limites -- a pagina do dono avisa.
    c.execute("""CREATE TABLE IF NOT EXISTS planos (
        empresa_id INTEGER PRIMARY KEY, plano TEXT NOT NULL,
        periodo TEXT NOT NULL DEFAULT 'mensal', fundador INTEGER NOT NULL DEFAULT 0,
        utilizadores INTEGER, desde TEXT)""")
    # O Equipa (ate 5) deu lugar ao Duo (2) no mesmo dia em que nasceu
    # (1/10/2026, decisao dele). A tabela estava vazia; uma linha que o
    # tenha gravado passa a Duo. Idempotente: sem 'equipa', nao faz nada.
    c.execute("UPDATE planos SET plano='duo', utilizadores=2 WHERE plano='equipa'")
    # As sessoes que uma entrada noutro aparelho fechou (a sessao unica do
    # Solo), para quem as tinha ver porque, e nao so o ecra de entrar.
    c.execute("""CREATE TABLE IF NOT EXISTS sessoes_fechadas (
        token TEXT PRIMARY KEY, quando TEXT)""")


# ------------------------------------------------------------------- planos
#
# Os planos de 1/10/2026 (decisao dele): o nome, e quantos utilizadores
# leva -- e so isso: «todos os planos tem exactamente a mesma coisa, so
# muda o numero de pessoas». O Corporate e pelo numero acordado, que se
# grava na linha da empresa; sem numero, nao tem limite.
PLANOS = {"solo": ("Solo", 1), "duo": ("Duo", 2), "corporate": ("Corporate", None)}
PERIODOS = ("mensal", "anual")


def plano_da_empresa(c, empresa_id):
    """A linha do plano da empresa, ou None quando nao tem plano."""
    if not empresa_id:
        return None
    linha = c.execute("SELECT * FROM planos WHERE empresa_id=?", (empresa_id,)).fetchone()
    return dict(linha) if linha else None


def gravar_plano(c, empresa_id, plano, periodo="mensal", fundador=False,
                 utilizadores=None, agora=None):
    """Poe (ou muda) o plano de uma empresa. O limite do Solo e do Duo
    e o do plano; o do Corporate e o que se der. ValueError com a frase
    para o ecra se o plano ou o periodo nao existem."""
    if plano not in PLANOS:
        raise ValueError("o plano tem de ser Solo, Duo ou Corporate")
    if periodo not in PERIODOS:
        raise ValueError("o período tem de ser mensal ou anual")
    limite = PLANOS[plano][1] if plano != "corporate" else utilizadores
    c.execute("INSERT OR REPLACE INTO planos (empresa_id, plano, periodo, fundador, "
              "utilizadores, desde) VALUES (?,?,?,?,?,?)",
              (empresa_id, plano, periodo, 1 if fundador else 0, limite,
               (agora or datetime.now()).strftime("%Y-%m-%d")))


def lugares_livres(c, empresa_id, agora=None, contar_convites=True):
    """Quantas contas mais a empresa pode ter, ou None sem limite. Conta
    as contas dela e, com `contar_convites`, os convites ainda validos --
    um convite e um lugar guardado, senao davam-se dez convites num Solo
    e o limite so se sentia ao usa-los."""
    p = plano_da_empresa(c, empresa_id)
    if not p or not p["utilizadores"]:
        return None
    contas_ = c.execute("SELECT COUNT(*) FROM utilizadores WHERE empresa_id=? "
                        "AND COALESCE(dono,0)=0", (empresa_id,)).fetchone()[0]
    convites_ = 0
    if contar_convites:
        convites_ = c.execute(
            "SELECT COUNT(*) FROM convites WHERE empresa_id=? AND usado_em IS NULL "
            "AND anulado_em IS NULL AND expira > ?",
            (empresa_id, (agora or datetime.now()).strftime("%Y-%m-%d %H:%M:%S"))
        ).fetchone()[0]
    return max(0, p["utilizadores"] - contas_ - convites_)


def frase_do_limite(c, empresa_id):
    """A frase de quando nao ha lugar: o que o plano da e como se muda."""
    p = plano_da_empresa(c, empresa_id) or {}
    nome = PLANOS.get(p.get("plano"), ("", 0))[0]
    return ("O plano %s da empresa tem %s, e já estão todos ocupados ou "
            "convidados. Para mais, fale connosco." % (
                nome, "1 utilizador" if p.get("utilizadores") == 1
                else "%s utilizadores" % p.get("utilizadores")))


def foi_fechada_por_outra(c, token):
    """Se esta sessao foi fechada por uma entrada noutro aparelho (a
    sessao unica do Solo). Responde uma vez: a linha sai ao ser lida."""
    if not token:
        return False
    linha = c.execute("SELECT 1 FROM sessoes_fechadas WHERE token=?", (token,)).fetchone()
    if linha:
        c.execute("DELETE FROM sessoes_fechadas WHERE token=?", (token,))
    return bool(linha)


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
        raise ValueError("o papel tem de ser gestor ou utilizador")
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
        raise ValueError("só o gestor da empresa tira contas")
    if linha["papel"] == "admin" and c.execute(
            "SELECT COUNT(*) FROM utilizadores WHERE papel='admin' "
            "AND empresa_id=?", (linha["empresa_id"],)).fetchone()[0] <= 1:
        raise ValueError("é o único gestor; crie outro antes de o tirar")
    c.execute("DELETE FROM sessoes WHERE utilizador_id=?", (utilizador_id,))
    c.execute("DELETE FROM reposicoes WHERE utilizador_id=?", (utilizador_id,))
    c.execute("DELETE FROM segundo_factor WHERE utilizador_id=?", (utilizador_id,))
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
# O "sistema" nao e um tema: o guiao do <head> (TEMA_DO_SISTEMA_JS, no
# radar) troca-o pelo claro ou pelo escuro do computador (3.a ronda, D1).
ASPECTOS = {"normal": "claro", "escuro": "escuro", "sistema": "sistema",
            "contraste": "contraste"}


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

def _espera(linhas, tecto, agora):
    """Segundos ate a falha que faz a `tecto`-esima a contar do fim sair
    da janela; 0 se nao chegam ao tecto."""
    if len(linhas) < tecto:
        return 0
    primeira = datetime.strptime(linhas[-tecto][0], "%Y-%m-%d %H:%M:%S")
    abre = primeira + timedelta(minutes=MINUTOS_DE_TRINCO)
    return max(1, int((abre - agora).total_seconds()))


def segundos_de_trinco(c, email, ip, agora=None):
    """Quantos segundos faltam para o trinco abrir: 0 se nao ha trinco.

    Conta as falhas dos ultimos MINUTOS_DE_TRINCO da conta (FALHAS_ATE_
    TRINCO) e as do IP (FALHAS_ATE_TRINCO_DO_IP, sem as do repor); o
    trinco fecha pelo que chegar primeiro ao seu tecto. `email=None` so
    olha para o IP.
    """
    agora = agora or datetime.now()
    limite = (agora - timedelta(minutes=MINUTOS_DE_TRINCO)).strftime(
        "%Y-%m-%d %H:%M:%S")
    da_conta = c.execute(
        "SELECT quando FROM entradas_falhadas WHERE quando > ? AND email=? "
        "ORDER BY quando", (limite, email_limpo(email))).fetchall() \
        if email is not None else []
    do_ip = c.execute(
        "SELECT quando FROM entradas_falhadas WHERE quando > ? AND ip=? "
        "AND substr(email, 1, ?) != ? ORDER BY quando",
        (limite, ip, len(PREFIXO_DO_REPOR), PREFIXO_DO_REPOR)).fetchall() if ip else []
    return max(_espera(da_conta, FALHAS_ATE_TRINCO, agora),
               _espera(do_ip, FALHAS_ATE_TRINCO_DO_IP, agora))


def recado_do_trinco(espera, agora=None):
    """A frase do trinco para o ecra (G50): a hora a que se pode tentar,
    e nao «espera 674 s» -- que tratava por tu e obrigava a fazer contas."""
    abre = (agora or datetime.now()) + timedelta(seconds=espera + 59)
    return "demasiadas tentativas; pode tentar de novo às %s" % abre.strftime("%H:%M")


def levantar_trinco(c, email="", ip=""):
    """Tira as falhas da conta e/ou do IP (D2: o dono levanta o trinco
    nas paginas dele). Devolve quantas linhas sairam."""
    n = 0
    if email:
        n += c.execute("DELETE FROM entradas_falhadas WHERE email=?",
                       (email_limpo(email),)).rowcount
    if ip:
        n += c.execute("DELETE FROM entradas_falhadas WHERE ip=?", (ip,)).rowcount
    return n


def trincos_fechados(c, agora=None):
    """[(chave, tipo, segundos)] das contas e IP com o trinco fechado
    agora -- o que a pagina dos erros oferece para levantar."""
    agora = agora or datetime.now()
    limite = (agora - timedelta(minutes=MINUTOS_DE_TRINCO)).strftime(
        "%Y-%m-%d %H:%M:%S")
    fechados = []
    for coluna, tipo in (("email", "conta"), ("ip", "ip")):
        for (chave,) in c.execute(
                "SELECT DISTINCT %s FROM entradas_falhadas WHERE quando > ? "
                "AND COALESCE(%s, '') != ''" % (coluna, coluna), (limite,)).fetchall():
            espera = (segundos_de_trinco(c, chave, "", agora) if tipo == "conta"
                      else segundos_de_trinco(c, None, chave, agora))
            if espera:
                fechados.append((chave, tipo, espera))
    return fechados


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
        raise ValueError("o papel tem de ser gestor ou utilizador")
    agora = agora or datetime.now()
    # o limite do plano (L2.1): um convite guarda um lugar
    if lugares_livres(c, empresa_id, agora) == 0:
        raise ValueError(frase_do_limite(c, empresa_id))
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
    # o plano pode ter descido depois do convite: so as contas contam aqui
    if lugares_livres(c, convite["empresa_id"], agora, contar_convites=False) == 0:
        return None, frase_do_limite(c, convite["empresa_id"])
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
# resumo na base, prazo e uso unico. Desde 1/10/2026 (J7) a propria
# pessoa pode pedi-la por e-mail (`reposicao_por_email()`), com uma hora
# de prazo e o tecto do `contar_pedido_de_reposicao()`.

HORAS_DE_REPOSICAO = 24
# A que vai por e-mail (J7, 1/10/2026) vale uma hora, e nao um dia: a de
# cima entrega-a uma pessoa a outra, e esta fica numa caixa de correio
# que pode ser lida por quem nao devia.
HORAS_DE_REPOSICAO_POR_EMAIL = 1


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


def criar_reposicao(c, utilizador_id, criado_por=None, agora=None,
                    horas=HORAS_DE_REPOSICAO):
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
               (agora + timedelta(hours=horas)).strftime(
                   "%Y-%m-%d %H:%M:%S")))
    return codigo


def contar_pedido_de_reposicao(c, email, ip, agora=None):
    """O tecto do «esqueci-me» por e-mail (J7): segundos de espera, ou 0
    e o pedido fica contado. Conta TODOS os pedidos, exista a conta ou
    nao -- um tecto que so contasse as que existem dizia quais existem
    --, pelo IP e pelo endereco escrito: o do IP trava quem experimenta
    enderecos, o do endereco trava quem enche a caixa de alguem a partir
    de muitos IP. As chaves levam o PREFIXO_DO_REPOR, e por isso nada
    disto conta no trinco do /entrar (G50)."""
    chaves = (PREFIXO_DO_REPOR + "pedido:" + (ip or ""),
              PREFIXO_DO_REPOR + "conta:" + email_limpo(email))
    espera = max(segundos_de_trinco(c, chave, "", agora) for chave in chaves)
    if not espera:
        for chave in chaves:
            registar_falha(c, chave, ip, agora)
    return espera


def reposicao_por_email(c, email, agora=None):
    """(codigo, conta) da ligacao que vai por e-mail, ou (None, conta ou
    None) quando nao vai. Nunca para o dono: tem o segundo factor, e
    repoe-se pela consola (`--palavra-passe`) -- uma ligacao por e-mail
    para a conta mais poderosa era a porta do lado. Quem chama decide o
    que dizer, e diz o mesmo nos tres casos."""
    linha = c.execute("SELECT id, email, nome, dono FROM utilizadores "
                      "WHERE email=?", (email_limpo(email),)).fetchone()
    if not linha or e_dono(dict(linha)):
        return None, (dict(linha) if linha else None)
    return (criar_reposicao(c, linha["id"], None, agora,
                            horas=HORAS_DE_REPOSICAO_POR_EMAIL), dict(linha))


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
    # Com o segundo factor ligado nao ha sessao (28/09/2026): a ligacao
    # vale uma palavra-passe, nao as duas coisas. O `entrar()` devolve o
    # pendente, e quem repos ainda tem de dar o codigo.
    token, resultado = entrar(c, reposicao["email"], senha, ip, agente, agora)
    return token, (None if token else resultado)


# ------------------------------------------------------------ segundo factor
#
# O TOTP da RFC 6238 (28/09/2026): HMAC-SHA1, passos de 30 s, seis
# digitos -- o que todas as apps de autenticacao fazem por omissao, e
# por isso nada a configurar do lado de quem liga. Sem dependencia nova:
# e um HMAC e um corte, com a biblioteca padrao.

PASSO_TOTP = 30
DIGITOS_TOTP = 6
# O passo de agora e um de cada lado: o relogio de um telemovel anda
# uns segundos fora, e quem escreve o codigo no ultimo segundo do passo
# nao pode ser recusado.
JANELA_TOTP = 1
# O pedido pendente (a palavra-passe certa, falta o codigo): cinco
# minutos e cinco tentativas. Com seis digitos, cinco tentativas sao uma
# hipotese em 200 000; o trinco da conta apanha quem insistir.
MINUTOS_DO_PENDENTE = 5
TENTATIVAS_DO_PENDENTE = 5
DIAS_DE_APARELHO = 30
CODIGOS_DE_RECUPERACAO = 10
_LETRAS_DA_RECUPERACAO = "abcdefghijklmnopqrstuvwxyz234567"


def _instante():
    """O relogio do TOTP, a parte para os testes o poderem parar."""
    return time.time()


def _quando(momento):
    return momento.strftime("%Y-%m-%d %H:%M:%S")


def pode_ter_segundo_factor(utilizador):
    """Quem pode ligar o segundo factor. So o dono, por agora (decisao
    dele, 28/09/2026); estender aos admins e mudar esta linha -- o resto
    ja e por conta, e nao por papel."""
    return e_dono(utilizador)


def segredo_novo():
    """160 bits em base32, sem o '=' do fim: e o que as apps esperam."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii")


def codigo_totp(segredo, instante, digitos=DIGITOS_TOTP):
    """O codigo do passo de `instante` (segundos desde 1970)."""
    return _codigo_do_passo(segredo, int(instante) // PASSO_TOTP, digitos)


def _codigo_do_passo(segredo, passo, digitos=DIGITOS_TOTP):
    chave = base64.b32decode(segredo.upper() + "=" * (-len(segredo) % 8))
    mac = hmac.new(chave, struct.pack(">Q", passo), hashlib.sha1).digest()
    corte = mac[-1] & 0x0F
    numero = struct.unpack(">I", mac[corte:corte + 4])[0] & 0x7FFFFFFF
    return str(numero % 10 ** digitos).zfill(digitos)


def _passo_do_codigo(segredo, codigo, ultimo):
    """O passo em que `codigo` bate, dentro da janela e DEPOIS do
    `ultimo` aceite; None se nenhum. E o «depois» que faz a
    anti-repeticao: um codigo visto por cima do ombro ja nao serve."""
    agora = int(_instante()) // PASSO_TOTP
    for passo in range(agora - JANELA_TOTP, agora + JANELA_TOTP + 1):
        if passo > ultimo and hmac.compare_digest(
                _codigo_do_passo(segredo, passo), codigo):
            return passo
    return None


def segundo_factor_ligado(c, utilizador_id):
    linha = c.execute("SELECT totp_ligado_em FROM utilizadores WHERE id=?",
                      (utilizador_id,)).fetchone()
    return bool(linha and linha[0])


def _senha_actual(c, utilizador_id, senha, ip, agora):
    """None se `senha` e a palavra-passe actual da conta e o trinco esta
    aberto; senao o porque. A errada conta no trinco da conta e do IP."""
    linha = c.execute("SELECT email, hash FROM utilizadores WHERE id=?",
                      (utilizador_id,)).fetchone()
    if not linha:
        return "a conta não existe"
    espera = segundos_de_trinco(c, linha["email"], ip, agora)
    if espera:
        return recado_do_trinco(espera, agora)
    if not verifica_senha(senha or "", linha["hash"]):
        registar_falha(c, linha["email"], ip, agora)
        return "a palavra-passe actual não está certa"
    return None


def preparar_segundo_factor(c, utilizador_id, senha, ip="", agora=None):
    """O segredo novo, por confirmar: fica guardado, mas o segundo factor
    so se liga quando a app devolver um codigo certo
    (`confirmar_segundo_factor()`). Preparar outra vez deita o anterior
    fora. Devolve (segredo, None) ou (None, porque).

    Pede a palavra-passe ACTUAL (revisao de seguranca do PR #123,
    28/09/2026): sem ela, quem tivesse roubado o cookie da sessao ligava
    o segundo factor com a app DELE e trancava o dono fora da conta. A
    errada conta no trinco. Ja ligado, recusa: para mudar de telemovel,
    desliga-se primeiro."""
    agora = agora or datetime.now()
    porque = _senha_actual(c, utilizador_id, senha, ip, agora)
    if porque:
        return None, porque
    if segundo_factor_ligado(c, utilizador_id):
        return None, "o segundo factor já está ligado"
    segredo = segredo_novo()
    c.execute("UPDATE utilizadores SET totp_segredo=?, totp_ligado_em=NULL, "
              "totp_passo=0 WHERE id=?", (segredo, utilizador_id))
    return segredo, None


def segredo_por_confirmar(c, utilizador_id):
    linha = c.execute("SELECT totp_segredo FROM utilizadores WHERE id=? "
                      "AND totp_ligado_em IS NULL", (utilizador_id,)).fetchone()
    return linha[0] if linha and linha[0] else None


def _so_digitos(codigo):
    return "".join((codigo or "").split())


def confirmar_segundo_factor(c, utilizador_id, codigo, agora=None):
    """Liga o segundo factor se o `codigo` bater com o segredo preparado.
    Devolve os codigos de recuperacao -- que so existem aqui: na base
    fica o resumo --, ou None."""
    segredo = segredo_por_confirmar(c, utilizador_id)
    if not segredo:
        return None
    passo = _passo_do_codigo(segredo, _so_digitos(codigo), 0)
    if passo is None:
        return None
    agora = agora or datetime.now()
    c.execute("UPDATE utilizadores SET totp_ligado_em=?, totp_passo=? WHERE id=?",
              (_quando(agora), passo, utilizador_id))
    return _codigos_de_recuperacao_novos(c, utilizador_id, agora)


def _recuperacao_limpa(codigo):
    """Como se escreve a mao: maiusculas, espacos, com ou sem o traco."""
    return "".join((codigo or "").lower().replace("-", " ").split())


def _codigos_de_recuperacao_novos(c, utilizador_id, agora):
    """Dez codigos de uso unico, `xxxxx-xxxxx` (50 bits cada), e os
    anteriores deixam de servir."""
    c.execute("DELETE FROM segundo_factor WHERE utilizador_id=? AND tipo='recuperacao'",
              (utilizador_id,))
    codigos = []
    while len(codigos) < CODIGOS_DE_RECUPERACAO:
        letras = "".join(secrets.choice(_LETRAS_DA_RECUPERACAO) for _ in range(10))
        if letras in codigos:
            continue
        codigos.append(letras)
        c.execute("INSERT INTO segundo_factor (resumo, utilizador_id, tipo, criado_em) "
                  "VALUES (?,?,'recuperacao',?)",
                  (_resumo(letras), utilizador_id, _quando(agora)))
    return ["%s-%s" % (l[:5], l[5:]) for l in codigos]


def verificar_codigo(c, utilizador_id, codigo, agora=None):
    """'totp' ou 'recuperacao' se o codigo serve, e gasta-o; None se nao.
    Seis digitos sao da app, o resto e um codigo de recuperacao."""
    linha = c.execute("SELECT totp_segredo, totp_ligado_em, totp_passo "
                      "FROM utilizadores WHERE id=?", (utilizador_id,)).fetchone()
    if not linha or not linha["totp_ligado_em"]:
        return None
    digitos = _so_digitos(codigo)
    if digitos.isdigit() and len(digitos) == DIGITOS_TOTP:
        passo = _passo_do_codigo(linha["totp_segredo"], digitos, linha["totp_passo"])
        # o `totp_passo < ?` no UPDATE: dois pedidos com o mesmo codigo
        # ao mesmo tempo, e so um o gasta
        if passo is None or not c.execute(
                "UPDATE utilizadores SET totp_passo=? WHERE id=? AND totp_passo < ?",
                (passo, utilizador_id, passo)).rowcount:
            return None
        return "totp"
    gasto = c.execute(
        "UPDATE segundo_factor SET usado_em=? WHERE resumo=? AND utilizador_id=? "
        "AND tipo='recuperacao' AND usado_em IS NULL",
        (_quando(agora or datetime.now()), _resumo(_recuperacao_limpa(codigo)),
         utilizador_id)).rowcount
    return "recuperacao" if gasto else None


def codigos_por_usar(c, utilizador_id):
    return c.execute("SELECT COUNT(*) FROM segundo_factor WHERE utilizador_id=? "
                     "AND tipo='recuperacao' AND usado_em IS NULL",
                     (utilizador_id,)).fetchone()[0]


def desligar_com_codigo(c, utilizador_id, senha, codigo, ip="", agora=None):
    """O desligar da Conta: a palavra-passe actual e um codigo valido (da
    app ou de recuperacao). Devolve ('totp' ou 'recuperacao', None) se
    desligou, ou (None, porque).

    Com trinco (revisao do PR #123, 28/09/2026): cada palavra-passe ou
    codigo errado conta no trinco da conta e do IP, e com ele fechado nem
    o certo passa -- sem isto, uma sessao roubada tentava codigos sem
    limite ate desligar o segundo factor."""
    agora = agora or datetime.now()
    porque = _senha_actual(c, utilizador_id, senha, ip, agora)
    if porque:
        return None, porque
    usado = verificar_codigo(c, utilizador_id, codigo, agora)
    if not usado:
        email = c.execute("SELECT email FROM utilizadores WHERE id=?",
                          (utilizador_id,)).fetchone()[0]
        registar_falha(c, email, ip, agora)
        return None, "o código não está certo"
    desligar_segundo_factor(c, utilizador_id)
    return usado, None


def desligar_segundo_factor(c, utilizador_id):
    """Tira o segredo, os codigos de recuperacao, os pendentes e os
    aparelhos de confianca. Devolve se estava ligado. Sem guarda nenhuma:
    e o que a consola chama; a Conta passa pelo `desligar_com_codigo()`."""
    estava = segundo_factor_ligado(c, utilizador_id)
    c.execute("UPDATE utilizadores SET totp_segredo=NULL, totp_ligado_em=NULL, "
              "totp_passo=0 WHERE id=?", (utilizador_id,))
    c.execute("DELETE FROM segundo_factor WHERE utilizador_id=?", (utilizador_id,))
    return estava


def criar_pendente(c, utilizador_id, agora=None):
    """O pedido de entrada a meio: a palavra-passe estava certa, falta o
    codigo. Devolve o CODIGO do pendente (vai num cookie); na base fica o
    resumo. Poda os pendentes e os aparelhos fora do prazo.

    E so o ultimo da conta vale (revisao do PR #123): cada pendente traz
    cinco tentativas, e quem soubesse a palavra-passe abria quantos
    quisesse. O trinco ja o apanhava; o pendente e que nao pode ser o
    atalho."""
    agora = agora or datetime.now()
    c.execute("DELETE FROM segundo_factor WHERE (tipo IN ('pendente', 'aparelho') "
              "AND expira <= ?) OR (tipo='pendente' AND utilizador_id=?)",
              (_quando(agora), utilizador_id))
    codigo = secrets.token_urlsafe(32)
    c.execute("INSERT INTO segundo_factor (resumo, utilizador_id, tipo, criado_em, "
              "expira) VALUES (?,?,'pendente',?,?)",
              (_resumo(codigo), utilizador_id, _quando(agora),
               _quando(agora + timedelta(minutes=MINUTOS_DO_PENDENTE))))
    return codigo


def pendente_valido(c, codigo, agora=None):
    """O pendente (com o `email` da conta) se ainda serve, ou None."""
    if not codigo:
        return None
    linha = c.execute(
        "SELECT p.utilizador_id, p.tentativas, u.email FROM segundo_factor p "
        "JOIN utilizadores u ON u.id = p.utilizador_id WHERE p.resumo=? "
        "AND p.tipo='pendente' AND p.expira > ?",
        (_resumo(codigo), _quando(agora or datetime.now()))).fetchone()
    return dict(linha) if linha else None


def usar_pendente(c, codigo, codigo_2f, ip="", agente="", agora=None):
    """Da o codigo ao pendente. (token, utilizador) se serve -- com o
    `codigo_usado`, 'totp' ou 'recuperacao' --, ou (None, porque).

    As falhas contam no trinco da conta e do IP (o mesmo da palavra-
    passe), e ao fim de TENTATIVAS_DO_PENDENTE o pendente gasta-se: e
    preciso voltar a dar a palavra-passe."""
    agora = agora or datetime.now()
    pendente = pendente_valido(c, codigo, agora)
    if not pendente:
        return None, "o pedido de entrada passou do prazo; entre outra vez"
    espera = segundos_de_trinco(c, pendente["email"], ip, agora)
    if espera:
        return None, recado_do_trinco(espera, agora)
    usado = verificar_codigo(c, pendente["utilizador_id"], codigo_2f, agora)
    if not usado:
        registar_falha(c, pendente["email"], ip, agora)
        if pendente["tentativas"] + 1 >= TENTATIVAS_DO_PENDENTE:
            c.execute("DELETE FROM segundo_factor WHERE resumo=?", (_resumo(codigo),))
            return None, "código errado demasiadas vezes; entre outra vez"
        c.execute("UPDATE segundo_factor SET tentativas=tentativas+1 WHERE resumo=?",
                  (_resumo(codigo),))
        return None, "código errado"
    c.execute("DELETE FROM segundo_factor WHERE resumo=?", (_resumo(codigo),))
    token, utilizador = _abrir_sessao(c, pendente["utilizador_id"], ip, agente, agora)
    return token, dict(utilizador, codigo_usado=usado)


def confiar_no_aparelho(c, utilizador_id, agora=None):
    """Um token de aparelho de confianca, para DIAS_DE_APARELHO: com ele,
    a palavra-passe chega. Devolve o TOKEN (vai num cookie HttpOnly);
    na base fica o resumo, ligado a conta."""
    agora = agora or datetime.now()
    token = secrets.token_urlsafe(32)
    c.execute("INSERT INTO segundo_factor (resumo, utilizador_id, tipo, criado_em, "
              "expira) VALUES (?,?,'aparelho',?,?)",
              (_resumo(token), utilizador_id, _quando(agora),
               _quando(agora + timedelta(days=DIAS_DE_APARELHO))))
    return token


def aparelho_de_confianca(c, utilizador_id, token, agora=None):
    """Se `token` e um aparelho de confianca DESTA conta, dentro do prazo."""
    if not token:
        return False
    return bool(c.execute(
        "SELECT 1 FROM segundo_factor WHERE resumo=? AND utilizador_id=? "
        "AND tipo='aparelho' AND expira > ?",
        (_resumo(token), utilizador_id, _quando(agora or datetime.now()))).fetchone())


# ------------------------------------------------------------------- sessoes

def entrar(c, email, senha, ip="", agente="", agora=None, aparelho=""):
    """Tenta entrar. Devolve (token, utilizador) ou (None, porque).

    O `porque` e texto para o ecra: 'espera N s' quando o trinco esta
    fechado, 'utilizador ou palavra-passe errados' no resto -- a mesma
    frase para os dois casos, para nao dizer a quem tenta quais os
    e-mails que existem.

    Com o segundo factor ligado (28/09/2026) a palavra-passe certa NAO
    abre sessao: o `porque` e um dict `{"pendente": codigo}`, e a sessao
    so nasce no `usar_pendente()`. E aqui, e nao na rota, porque o
    convite e a ligacao de repor tambem entram por esta funcao -- uma
    guarda na rota do /entrar deixava-as abertas. So o `aparelho` de
    confianca da conta dispensa o codigo.
    """
    agora = agora or datetime.now()
    email = email_limpo(email)
    espera = segundos_de_trinco(c, email, ip, agora)
    if espera:
        return None, recado_do_trinco(espera, agora)
    linha = c.execute("SELECT id, hash FROM utilizadores WHERE email=?",
                      (email,)).fetchone()
    if not linha or not verifica_senha(senha or "", linha["hash"]):
        registar_falha(c, email, ip, agora)
        return None, "utilizador ou palavra-passe errados"
    if segundo_factor_ligado(c, linha["id"]) \
            and not aparelho_de_confianca(c, linha["id"], aparelho, agora):
        return None, {"pendente": criar_pendente(c, linha["id"], agora)}
    return _abrir_sessao(c, linha["id"], ip, agente, agora)


def _abrir_sessao(c, utilizador_id, ip, agente, agora):
    """A sessao nova, depois de a porta ter dito que sim. (token, utilizador)."""
    linha = c.execute("SELECT id, email, nome, papel, empresa_id, dono, aspecto "
                      "FROM utilizadores WHERE id=?", (utilizador_id,)).fetchone()
    token = secrets.token_urlsafe(32)
    c.execute("INSERT INTO sessoes (token, utilizador_id, criada_em, expira, ip, agente) "
              "VALUES (?,?,?,?,?,?)",
              (token, linha["id"], agora.strftime("%Y-%m-%d %H:%M:%S"),
               (agora + timedelta(days=DIAS_DE_SESSAO)).strftime(
                   "%Y-%m-%d %H:%M:%S"), ip or "", (agente or "")[:200]))
    c.execute("UPDATE utilizadores SET ultimo_acesso=? WHERE id=?",
              (agora.strftime("%Y-%m-%d %H:%M:%S"), linha["id"]))
    # A sessao unica do Solo (L2.1, decisao dele a 1/10/2026): a ultima
    # entrada ganha, e as outras fecham-se, ficando registadas para quem
    # as tinha saber porque. E aqui, e nao na rota do /entrar, porque o
    # convite, o repor e o segundo factor tambem abrem sessoes por aqui.
    p = plano_da_empresa(c, linha["empresa_id"]) if not linha["dono"] else None
    if p and p["plano"] == "solo":
        outras = [r[0] for r in c.execute(
            "SELECT token FROM sessoes WHERE utilizador_id=? AND token != ?",
            (linha["id"], token))]
        c.executemany("INSERT OR REPLACE INTO sessoes_fechadas VALUES (?,?)",
                      [(o, agora.strftime("%Y-%m-%d %H:%M:%S")) for o in outras])
        c.executemany("DELETE FROM sessoes WHERE token=?", [(o,) for o in outras])
        c.execute("DELETE FROM sessoes_fechadas WHERE quando < ?",
                  ((agora - timedelta(days=DIAS_DE_SESSAO)).strftime("%Y-%m-%d %H:%M:%S"),))
    return token, dict(linha)


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
    """Fecha todas as sessoes do utilizador. Devolve quantas eram.

    E esquece os aparelhos de confianca (28/09/2026): o «sair de todos»
    e o gesto de quem perdeu o telemovel, e um aparelho que ainda
    dispensasse o codigo era meia porta aberta. A ligacao de repor
    passa por aqui, e leva-os tambem."""
    n = c.execute("SELECT COUNT(*) FROM sessoes WHERE utilizador_id=?",
                  (utilizador_id,)).fetchone()[0]
    c.execute("DELETE FROM sessoes WHERE utilizador_id=?", (utilizador_id,))
    c.execute("DELETE FROM segundo_factor WHERE utilizador_id=? AND tipo='aparelho'",
              (utilizador_id,))
    return n


def sessoes_de(c, utilizador_id):
    """As sessoes da conta, com o `n` (o rowid, que vai para o ecra -- o
    token nunca) e o `usada_em`: o fim desliza DIAS_DE_SESSAO a cada
    pedido, e por isso o ultimo uso e o fim menos esses dias (G58)."""
    linhas = [dict(r) for r in c.execute(
        "SELECT rowid AS n, token, criada_em, expira, ip, agente FROM sessoes "
        "WHERE utilizador_id=? ORDER BY expira DESC", (utilizador_id,))]
    for l in linhas:
        l["usada_em"] = (datetime.strptime(l["expira"], "%Y-%m-%d %H:%M:%S")
                         - timedelta(days=DIAS_DE_SESSAO)).strftime("%Y-%m-%d %H:%M:%S")
    return linhas


def terminar_sessao(c, utilizador_id, n):
    """Fecha UMA sessao da conta, pelo `n` do `sessoes_de()`. So as da
    propria conta: um `n` de outra nao fecha nada. True se fechou."""
    return bool(c.execute("DELETE FROM sessoes WHERE rowid=? AND utilizador_id=?",
                          (n, utilizador_id)).rowcount)


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
