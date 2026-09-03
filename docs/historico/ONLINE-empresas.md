# Plano posto de lado: o radar online com empresas e utilizadores

Escrito a **3 de setembro de 2026**, de manhã para a tarde, a pedido do
Afonso: «criação de user e pass e gestão dos mesmos por empresas; a
conta ADMIN Pinto LDA é criada e a partir daí cria-se a gestão dos user
e dos interesses; e um menu inicial onde se faz login». **Posto de lado
na mesma tarde**, por ele: «vamos pensar de outra forma — quero eu,
Afonso Pinto, usar a plataforma num formato online, com login para não
ser aberto ao mundo». O plano que vale é o `ONLINE.md` ao lado. Este
fica para o dia em que uma segunda empresa aparecer: o que aqui está é
o trabalho a mais que esse dia custa.

---

## 0. De onde se partia (medido a 3/09/2026)

| Hoje | O que implicava |
|---|---|
| A triagem são **colunas de `anuncios`** (`estado`, `motivo`, `fase_id`, `responsavel`, `preco_proposto`, `posicao`, `top3`, `motivo_perda`, `docs_estado`, `visto_em`) | Duas empresas não podem ter opiniões diferentes sobre o mesmo anúncio. Era a mudança estrutural. `CAMPOS_DA_TRIAGEM` já nomeia o conjunto; 98 ocorrências de `fase_id`/`responsavel`/`motivo` no `radar.py` |
| O interesse vive no `config.json` | Passava a tabela, uma linha por empresa |
| `fases`, `etiquetas`, `filtros_guardados`, `alertas_vistos`, `entidades_seguidas`, `seguidas_vistos`, `historico`, `casa` são globais | Ganhavam `empresa_id`; o que existe passava para a empresa 1 |
| O destinatário do e-mail está no `config.json` | Passava para a empresa; a conta que envia ficava global |
| O B15 faz commit+push do `triagem.jsonl` | Num servidor com N empresas é cópia de segurança do operador, não sincronização |

Ficava **partilhado por desenho**: anúncios (a recolha corre uma vez),
peças em `documentos/` (a peça é pública), a leitura pelo modelo em
`analise` (lê-se o documento, não a empresa; o orçamento da Groq é um
só), `cpv_dict` e `contratos.db`. Era isso que tornava uma instância só
mais barata do que uma por empresa.

## 1. O modelo

```
empresa (Pinto, Lda)
 ├─ utilizadores: admin / membro
 ├─ triagem   — a opinião DESTA empresa sobre cada anúncio
 ├─ interesse — os CPV que ESTA empresa trabalha
 ├─ fases, etiquetas, filtros guardados, alertas, entidades seguidas
 ├─ registo da casa (casa.py)
 └─ histórico

comum: anuncios, documentos, analise, cpv_dict, contratos.db,
       alteracoes, erros, slots
```

Três papéis: **super-admin** (o Afonso; cria e suspende empresas, cola
capturas; `empresa_id` nulo), **admin** da empresa (convida e desactiva
utilizadores, edita interesse, e-mail e fases), **membro** (tria, move
no quadro, atribui). Sem registo público: uma empresa nasce pela mão do
super-admin. Sem «leitor» na v1.

## 2. As etapas

### Etapa 1 — Contas e login (2 a 3 dias)

Módulo `contas.py` ao molde do `casa.py`. Tabelas:

```sql
empresas     (id, nome, nif, email_para, activa, criada_em)
utilizadores (id, empresa_id, email UNIQUE, nome, hash, papel,
              activo, criado_em, ultimo_acesso)
sessoes      (token PRIMARY KEY, utilizador_id, criada_em, expira, ip)
convites     (token PRIMARY KEY, empresa_id, email, papel, expira, usado_em)
```

`hashlib.scrypt` (sem dependência nova); sessões no servidor; cookie
`HttpOnly`/`SameSite=Lax`/`Secure`; trinco ao login (5 falhas em 15
min); CSRF por `campo_csrf()` em todos os ~25 formulários; `quem_sou()`
lê a sessão e `/sou` desaparece; `acesso_livre_local` para a pen e os
testes; trabalho de fundo recebe a empresa explícita. Rotas `/entrar`,
`/sair`, `/conta`, `/recuperar` (token por e-mail, 1 h),
`/convite/<token>`. Arranque por `--criar-empresa NOME --admin EMAIL` e
`--super EMAIL`.

### Etapa 2 — Separar os dados por empresa (4 a 6 dias, o grosso)

```sql
triagem (empresa_id, ref, estado, motivo, fase_id, responsavel_id,
         visto_em, preco_proposto, posicao, top3, motivo_perda,
         docs_estado, PRIMARY KEY (empresa_id, ref))
```

Um anúncio sem linha está `novo` (não se criam 65 mil linhas por
empresa). `condicoes()` passa a `LEFT JOIN triagem … AND t.empresa_id=?`
com `COALESCE(t.estado,'novo')` — o `empresa_id` não é recorte, é a
identidade da consulta, e é onde uma empresa vê a da outra se o JOIN
ficar sem a segunda condição. `estado='alteracao'` fica em `anuncios`
(é facto do DR); `aplicar_alteracao()` move a triagem de todas as
empresas para a raiz. Quadro, calendário, indicadores, ficha, CSV e
alertas ganham `empresa_id`. `casa.py` escreve na `triagem`. O B15
exporta a tabela inteira com `empresa_id`. «Interessa» pede peças e
leitura **se ainda não existem**. O interesse passa a tabela
`interesse (empresa_id, activo, cpv, cpv_excl)`, lida uma vez por pedido
em `before_request`. `filtros_guardados.nome` passa a `UNIQUE(empresa_id,
nome)`. Os alertas correm por empresa.

Teste central: `TestDuasEmpresas` — A marca «interessa», B continua a
vê-lo em «por ver»; contagens, quadro, alerta e `--repor-triagem`
isolados.

### Etapa 3 — Gestão pelo admin (1 a 2 dias)

`/empresa` (admin): nome, NIF, e-mail, utilizadores, convidar,
desactivar, repor palavra-passe. `/admin` (super): criar empresa com o
primeiro admin, suspender, ver recolha e capturas. `--apagar-empresa
ID` por linha de comandos, nunca por botão. O último admin não se
desactiva.

### Etapa 4 — Ecrã de entrada e cabeçalho (1 dia)

`/entrar` faz uma coisa; o cabeçalho troca «sou …» por `empresa · nome
▾` com Conta, Empresa, Admin, Sair; `endereco_publico` nos e-mails; um
super-admin a olhar para uma empresa vê um aviso fixo a dizer qual.

### Etapa 5 — Servir online (2 a 3 dias)

Igual ao `ONLINE.md`, secção 3, com N empresas numa instância.

## 3. Os riscos

Uma empresa a ver a triagem da outra por um JOIN sem `empresa_id`
(`TestDuasEmpresas` em cada ecrã); contagem de aba a não bater com a
lista; `POST` sem CSRF (teste que percorre `app.url_map`); agendador em
dobro com dois trabalhadores; `acesso_livre_local` aberto num servidor;
a migração da triagem a perder os 3 728 descartes (exportar antes,
contar antes e depois); peças pedidas duas vezes.

## 4. As decisões que eram dele

Uma instância ou uma por empresa; super-admin à parte ou o admin da
Pinto com mais poderes; convite por e-mail ou palavra-passe temporária;
o `triagem.jsonl` a ir para o GitHub a partir do servidor; o modo local
a continuar na pen; nome e domínio.
