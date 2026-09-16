# Plano: fechar os ciclos da plataforma, e arrumar a documentação

Escrito a **16 de setembro de 2026**, à noite, a pedido do Afonso: «a
aplicação está a ganhar funcionalidades mas parece-me que os caminhos
não estão fechados. Para abrir a folha de uma entidade tenho de procurar
por um contrato para encontrar a ficha dela. O Hoje foi uma boa adição,
mas agora tenho lá 30 tarefas, mal consigo perceber o concurso que cada
uma delas é, e para as concluir tenho de ir uma a uma à ficha do
anúncio.» E: «só backend e lógica; UX e UI ficam para depois.»

É um plano, não trabalho feito. Está escrito para ser executado por
**outra sessão**, que não esteve nesta conversa: cada fase diz o que
muda, em que funções, com que regras, que testes a provam e que
documentos se corrigem no mesmo commit. Quando cada fase se fizer,
corrige-se o `ESTADO.md`, o `docs/armadilhas.md`, o `LEIA-ME.md` e o
`CLAUDE.md` nesse commit, e acrescenta-se aqui uma linha no §9; este
ficheiro fica como instantâneo.

Os números de linha do `radar.py` citados abaixo são os de 16/09/2026
(20 505 linhas) e vão andar; os nomes das funções é que valem.

---

## 0. O que se mediu antes de propor

Base a 16/09/2026, à noite, com os três meses de uso a fingir que se
povoaram nesse dia (73 propostas, 70 tarefas, 26 contactos):

| O quê | Quanto |
|---|---|
| Tarefas por fazer | **55** (não 30: o Hoje mostra-as em quatro baldes) |
| Das quais automáticas | **36** (18 «esclarecimentos», 18 «entrega») |
| Automáticas com data já passada, presas a propostas ainda em «por analisar» ou «a preparar» | **16**, de Julho e Agosto |
| Automáticas com responsável | **0** |
| Propostas por ranhura | analisar 11 · proposta 7 · submetido 8 · relatorio 5 · ganho 13 · perdido 16 · nao_fomos 14 · cancelado 4 |
| Propostas sem anúncio (D2 do CRM) | 0 |
| Anúncios com NIF da entidade | 159 848 de 209 999, em **3 342** NIF distintos |
| Entidades no corpus do Portal BASE | 179 823 |
| `email.para` | vazio até esta noite; alertas ligados: **0**; entidades seguidas: **0** |
| Interesse | ligado (CPV 72 e 48) |
| Rotas Flask | 74 |
| Documentação | 19 257 linhas em 19 ficheiros `.md`, mais seis diagramas de ~800 KB |
| Testes | 982, em ~118 s |

Quatro agentes leram tudo nesse dia: um mapeou o grafo de navegação do
painel (todas as rotas, e para onde cada página liga), outro varreu os
dois diários, as armadilhas e a referência à procura de trabalho a meio
e de contradições (211 itens), outro verificou cada documento do
`docs/historico/` e o `LEIA-ME.md` contra o código, e o quarto extraiu
os nós e as arestas dos seis diagramas. O que se segue é o que ficou de
pé depois de confirmar as afirmações deles no código e na base.

---

## 1. O que não fecha

### 1.1 O ciclo do trabalho: o Hoje mostra tarefas e não deixa resolvê-las

| Facto | Onde está no código |
|---|---|
| A linha da tarefa no Hoje mostra a data, o texto e o título da proposta. Não mostra a ranhura, a entidade, o responsável, a origem nem os dias que faltam | `linha_da_tarefa()` dentro de `inicio()`; `_tarefas_por_fazer()` lê `p.estado` e nunca o usa |
| O texto das automáticas é o mesmo em 36 linhas | `TEXTO_AUTOMATICO`, duas frases |
| Concluir só existe na ficha do anúncio; no Hoje a tarefa é só uma ligação | o botão `/tarefa/<id>/feita` está desenhado num único sítio, `_tarefas_da_ficha()` |
| O «desfazer» de uma tarefa concluída nunca aparece | `envolver()` só monta o botão quando o caminho começa por `/estado/` |
| Não há adiar, não há atribuir, não há lista de tarefas | nenhuma rota |
| Uma tarefa de proposta sem anúncio não tem onde se riscar | `/proposta/<id>` (`ficha_da_proposta()`) não chama `_tarefas_da_ficha()` |
| «Entregar a proposta» nasce em «por analisar», antes de se decidir ir | `ESTADOS_COM_TAREFAS = ("analisar", "proposta")` |
| Uma automática cujo prazo passou fica atrasada para sempre | `sincronizar_tarefas()` só apaga quando a proposta fecha ou o anúncio perde a data |
| As automáticas nascem sem responsável, mesmo quando a proposta o tem | o `INSERT` em `sincronizar_tarefas()` não escreve `quem` |

### 1.2 O ciclo da entidade: a ficha é do Portal BASE, não da empresa

- Só se chega a `/entidade/<chave>` por três caminhos: o nome na ficha de
  um anúncio, e só quando o corpus conhece a entidade (`entidade_do_anuncio()`);
  uma célula de uma tabela do Mercado (`liga_entidade()`); e o formulário
  «Ficha de entidade» dentro de `/contratos` (`/entidade/procurar`, que
  não é um `href` em lado nenhum). **Não há lista de entidades.**
- Uma entidade sem contrato no corpus dá **404**, mesmo com dezenas de
  anúncios no DR (`entidade()` começa por `ficha_entidade()` e devolve
  «não encontrada no corpus»).
- A ficha não mostra os anúncios do DR dessa entidade, nem as nossas
  propostas com ela, nem os contactos. Os contactos são «da entidade»
  por desenho (`contactos.entidade_chave`, e o próprio comentário de
  `contactos_cx()` di-lo) e só se vêem e criam dentro de um anúncio.

### 1.3 O ciclo da proposta sem anúncio

A decisão D2 do `CRM.md` criou-a; a página dela (`/proposta/<id>`,
`ficha_da_proposta()`) é só o formulário que `/proposta/<id>/gravar`
recebe. Sem tarefas, sem contactos, sem histórico. O `/proposta/<id>/apagar`
existe e nenhum HTML o desenha; e devolve `redirect("/?estado=…")`, que o
Hoje ignora desde que `/` deixou de ser a lista. O `historico` de uma
proposta sem `ref` escreve-se com `ref=""` (`mover_proposta()` faz
`registar(antes["ref"] or "", …)`), portanto perde-se.

E a escada aceita qualquer transição: `mover_proposta()` só verifica
que o destino é uma das oito palavras. O diagrama `processo-escada.html`
desenha Ganho, Não fomos e Cancelado como terminais. Nenhum dos dois diz
qual é a regra.

### 1.4 O ciclo do aviso

`email.para` estava vazio desde o estado zero de 8/09/2026, há zero
alertas ligados e zero entidades seguidas: o resumo diário não saía para
ninguém. O `BACKLOG.md` dava o E2 («o primeiro envio do resumo») como
feito a 31/08. O SMTP autentica; faltava o destino. **Posto nesta noite**
(§2, decisão 5).

### 1.5 As peças

Três becos sem saída, os mesmos no código e no diagrama `processo-pecas.html`:
sem plataforma conhecida é manual; sem texto extraível não há nada; e
«o tecto do dia bateu» grava a leitura parcial em `analise` e **ninguém
volta a tentar**: o `--ler-pecas` só escolhe quem não tem linha em
`analise`, e a verificação não relê incompletas. O ponto que falta para
a v1, julgar as leituras com o `ensaio-de-leitura`, continua por fazer
desde 3/09.

### 1.6 A documentação

**Vivos e errados** (verificado linha a linha; a lista completa está no §4):

- `LEIA-ME.md` (991 linhas): descreve a barra com três entradas, quatro
  abas, filtros guardados, o quadro de seis fases e o calendário de 45
  colunas. Tudo saiu entre 13 e 16/09.
- `docs/referencia.md` (1 441): diz que corre de uma pen com OneDrive e
  Windows, sem login, com 655 testes e quatro dependências, com quadro e
  calendário em grade.
- `docs/armadilhas.md` (2 383): a pen, o OneDrive, «lotes ainda não no
  quadro», e o `--empresa-ligar` fora e dentro ao mesmo tempo. O índice
  diz um número de pontos e as áreas têm outro (211 entradas contadas
  a 16/09).
- `ESTADO.md` (789): a arrumação de 3/09 fixou-o em 150 linhas de estado;
  voltou a ser um diário, e o «O que está implementado» fala de três
  intenções e do quadro. O «Como está a correr» diz que os números são de
  4/09.
- `BACKLOG.md` (514): o «registo de pendências fechado a 31/08» tem
  linhas erradas (o E2, o NIF da empresa já posto) e não tem o que este
  plano abre.
- `CLAUDE.md`: 19 mil linhas são 20 505, 23 tabelas são 24, e a tabela
  dos documentos não conhecia este ficheiro.
- `docs/design.md` (814): diz que o Hoje ganhou um item na barra (saiu
  no mesmo dia) e que o `--t6` desapareceu (foi aliasado).

**Instantâneos sem aviso:** `ESQUELETO`, `AUDITORIA`, `SANEAMENTO`,
`UX-Auditoria`, `ONLINE`, `ONLINE-empresas`, `CRM`. Só o `CONCORRENTES`
abre com o aviso certo. O `proximo-prompt.md` era um prompt já
consumido: **apagado nesta noite** (decisão 8).

**Diagramas:** cinco contradições com o código. A escada desenha oito
ranhuras em vez de dez e nenhuma seta de retorno; a arquitectura diz que
o DR é «a única fonte» quando há Vortal e BASE, «quatro plataformas» quando
são três descarregadores, e 23 tabelas; a recolha não tem o passo da
Vortal; a porta atribui ao CSRF a recusa que é de `origem_e_nossa()`.

---

## 2. As decisões, respondidas

Todas do Afonso, a 16/09/2026, à noite. Onde a resposta dele deixou
margem, a leitura que se fez está escrita, para se poder contestar.

**D1. A automática em «por analisar» fica como hoje**: «entregar a
proposta» nasce quando o concurso entra na escada, com a data do prazo.
(Resposta: «tal e qual». Lê-se como «como está»; a alternativa proposta,
«decidir se vamos» em «por analisar» e «entregar» só em «a preparar»,
fica registada e não se faz.)

**D2. Nada muda de ranhura sozinho.** Palavra dele: «tenho receio com
essas tarefas assim automáticas; posso não ter passado para submetido
por esquecimento e ele vai passar para não fomos.» Logo: uma automática
cujo prazo passou **não fecha, não se apaga e não move a proposta**. O
Hoje agrupa essas propostas num balde próprio, «prazo passou sem
decisão», e é a pessoa que escolhe a ranhura. É a regra do CRM outra vez:
**propõe, nunca decide.**

**D3. Todas as entidades têm ficha**: as do corpus do BASE e as que só
existem no DR, adjudicantes e adjudicatárias. «Clientes de clientes,
concorrentes de concorrentes»: de qualquer ficha chega-se às entidades
com que ela se relaciona, e daí às seguintes. A lista de entidades é uma
procura mais atalhos, não uma tabela de 180 mil linhas.

**D4. As transições da escada são livres, com a condicionante da
informação em falta.** Palavra dele: «eu não posso passar um por
analisar directo para ganho porque há informação que não foi
preenchida.» Logo: qualquer par de ranhuras é permitido, mas entrar
numa ranhura exige os campos que ela pede; se faltam, o movimento é
recusado com a lista do que falta, e o mesmo pedido pode trazê-los.

**D5. O e-mail**: `email.para = afonso.pinto95@hotmail.com`. Posto no
`config.json` nesta noite, por edição directa do ficheiro (não pelo
painel, portanto sem linha no `historico`). Os alertas e as entidades
seguidas continuam a zero: ligar um alerta ao interesse é gesto dele em
Configurações › Alertas.

**D6. O `ESTADO.md` volta ao formato de 3/09**: só o estado e os
números, ~150 linhas; a narrativa de 15 e 16/09 vai para o diário. Com
a condição dele: «vê com conflitos com o ECC» (§7).

**D7. Os diagramas regeneram-se** sobre o código final, pela skill
`archify`, e não só se marcam como instantâneos.

**D8. O `proximo-prompt.md` apaga-se.** Feito.

**D9. O plano fica em `docs/historico/CICLOS.md`**, pela convenção do
projecto (`CRM.md`, `ONLINE.md`), e não na pasta que a skill de
brainstorming sugeria.

**E o caminho é o A: fechar por objecto**, um ciclo de cada vez, cada um
um PR, a documentação numa passagem própria no fim.

Três decisões pequenas ficaram minhas, por omissão, e escrevem-se aqui
para se poderem desfazer:

- **D-a.** Os campos que cada ranhura **exige** (D4) são um subconjunto
  dos que ela **pede** (`_campos_que_a_ranhura_pede()`): §3.3.
- **D-b.** A automática herda o `responsavel` da proposta quando nasce e
  quando está vazia; não se reescreve uma tarefa a que alguém já pôs
  nome.
- **D-c.** As tarefas do Hoje agrupam-se **por proposta**, e não por
  data dentro do balde: 55 tarefas são ~25 concursos.

---

## 3. O desenho, fase a fase

Esforço na escala do `BACKLOG.md` (1 ≈ ≤2 h · 2 ≈ meio dia a 1 dia ·
3 ≈ 2–3 dias). Cada fase é **um PR** de uma sessão remota, com os
testes primeiro (a bateria é de regressões: cada classe nova diz que
erro deste §1 impede), o `code-reviewer` antes do commit, e os quatro
documentos vivos corrigidos no mesmo commit.

### Fase 1 — As tarefas (esforço 2)

**O que muda.** O Hoje passa a dizer de que concurso é cada tarefa e a
deixar resolvê-la ali. As automáticas ganham dono e deixam de mentir
quando o prazo passou.

**Regras.**

1. `sincronizar_tarefas()` escreve `quem = propostas.responsavel` nas
   automáticas que cria, e preenche-o nas que já existem com `quem`
   vazio (D-b). Uma tarefa com nome não se toca.
2. Uma automática cuja data já passou e cuja proposta continua numa
   ranhura de `ESTADOS_COM_TAREFAS` **fica como está** (D2). Não se
   apaga, não se marca feita, não se move nada.
3. O Hoje ganha um quinto balde, **«prazo passou sem decisão»**, antes
   das «atrasadas»: as propostas em `analisar` ou `proposta` cujo
   `anuncios.prazo` é anterior a hoje. Cada linha é a proposta (não a
   tarefa), com o selector de ranhura que a lista já tem
   (`/proposta/<id>/escada`). As automáticas dessas propostas **não**
   aparecem também nas «atrasadas»: seria a mesma coisa duas vezes. As
   tarefas escritas à mão dessas propostas continuam onde a data as põe.
4. A linha da tarefa leva: a data e os dias que faltam (`conta_dias()`
   da banda comum), o texto, a **referência**, a **ranhura**
   (`estado_da_empresa()`), a **entidade** (de `anuncios.entidade` pela
   `ref`, ou `propostas.entidade` quando não há anúncio), **quem**, e a
   origem (automática ou à mão). E agrupa-se por proposta dentro de cada
   balde (D-c): o cabeçalho do grupo é o concurso, as linhas são as
   tarefas dele.
5. As acções valem de qualquer página: **feita**, **desfazer**,
   **adiar** e **atribuir**. O Hoje desenha-as por linha.
6. A ficha de uma proposta sem anúncio mostra as tarefas dela, com as
   mesmas acções.

**Código.**

- `sincronizar_tarefas()` (~1820): o `INSERT` leva `quem`; um `UPDATE`
  para as existentes com `quem IS NULL`. O `SELECT` das propostas passa
  a trazer `p.responsavel`.
- `_tarefas_por_fazer()` (~19953): o `SELECT` junta `anuncios` pela
  `ref` para trazer `a.entidade` e `a.prazo`, e devolve também
  `p.responsavel`. Uma função nova na banda **propostas**,
  `propostas_sem_decisao(hoje)`, devolve as propostas abertas com prazo
  passado; `_grupos_das_tarefas()` recebe o conjunto dos `proposta_id`
  dessas e não põe as automáticas delas em balde nenhum.
- `_grupos_das_tarefas()` (~19969): balde novo `("sem_decisao", "Prazo
  passou sem decisão", "mau")` em primeiro; e cada balde devolve
  `[(proposta, [tarefas])]` em vez de `[(tarefa, dia)]`.
- Uma rota nova, `POST /tarefa/<id>/gravar`, com os campos opcionais
  `quando` (dd/mm/aaaa, lido por `data_de_filtro()`), `quem` e `o_que`;
  uma função `gravar_tarefa(id_, **campos)` ao lado de `marcar_tarefa()`.
  Adiar e atribuir são esta rota. Uma rota só, e não duas: o formulário
  da linha manda o que mudou.
- `envolver()` (~10600): o `desfazer` aceita caminhos que comecem por
  `/estado/` **ou** `/tarefa/`. É a única razão de o desfazer da tarefa
  nunca ter aparecido.
- `ficha_da_proposta()` (~18516): chama `_tarefas_da_ficha(p)`.
- Os botões da linha do Hoje: `accao()` para feita, um `<form>` de uma
  linha com data e nome para adiar e atribuir. É o mínimo de HTML que
  torna a fase usável; o aspecto fica para a passagem de desenho.

**Testes** (`teste_radar.py`, classes novas, cada uma com o comentário
do erro que impede):

- `TestAutomaticaHerdaOResponsavel`: proposta com responsável cria
  tarefa com `quem`; tarefa já nomeada não muda ao sincronizar.
- `TestPrazoPassadoNaoMexeEmNada`: proposta em `analisar` com prazo de
  ontem: sincronizar dá `(0,0,0)`, a tarefa continua aberta, a proposta
  continua em `analisar`. É a prova da D2.
- `TestHojeAgrupaSemDecisao`: essa proposta aparece no balde
  `sem_decisao` e a automática dela **não** aparece em `atrasadas`; uma
  tarefa à mão dela aparece onde a data manda.
- `TestLinhaDaTarefaDizOConcurso`: a linha traz `ref`, ranhura,
  entidade e quem; e as tarefas do mesmo `proposta_id` vêm juntas.
- `TestTarefaResolveSeDeQualquerPagina`: `POST /tarefa/<id>/feita` a
  partir de `/` volta a `/` com o desfazer no flash; `POST
  /tarefa/<id>/gravar` com `quando` adia e com `quem` atribui; data
  inválida recusa e não grava.
- `TestPropostaSemAnuncioTemTarefas`: `/proposta/<id>` mostra a tarefa
  e o botão de feita.

**Documentação no mesmo commit.** `ESTADO.md` (o Hoje: cinco baldes,
acções por linha), `docs/armadilhas.md` (a área do CRM: «uma automática
com prazo passado não se toca, é o balde do Hoje que a mostra»),
`LEIA-ME.md` (a secção do Hoje), `CLAUDE.md` (a banda 8a).

### Fase 2 — A entidade (esforço 3)

**O que muda.** Qualquer entidade tem ficha, a ficha mostra o lado da
empresa, e há um sítio para as encontrar.

**Regras.**

1. **A chave é uma só**: `chave_entidade(nif, nome)` (banda contratos),
   a mesma do corpus (`nif` de nove dígitos, ou `n:<nome normalizado>`).
   Um anúncio do DR resolve-se por `entidade_do_anuncio()`; quando o
   corpus não a conhece, a chave é a mesma regra aplicada ao `nif` e ao
   `entidade` do anúncio, e a ficha existe na mesma.
2. A ficha de uma entidade tem **dois lados**: o do Portal BASE (o que já
   está: compra, ganha, a quem, o quê, evolução, recentes, seguir) e o
   da empresa, novo: os **anúncios do DR** dela (contagem por ranhura,
   com a ligação para `/concursos?entid=<chave>` que dá exactamente
   essa lista), as **nossas propostas** com ela (por ranhura, com o
   resultado e o desvio de preço quando há), a **taxa de vitória com
   esta entidade** (só com 5 decididos ou mais, a mesma regra de
   `taxa_de_vitoria()`), e os **contactos**, com o formulário de criar
   contacto ali (a rota `/contacto/nova` já existe; só precisa de
   receber a `entidade_chave` sem passar por um anúncio).
3. Sem corpus, ou sem contrato no corpus, a ficha mostra só o lado da
   empresa e diz que o Portal BASE não a conhece. Nunca 404 para uma
   chave que exista em `anuncios`, em `propostas` ou em `contactos`.
4. **A lista de entidades** é `/entidades`: uma procura por nome ou NIF
   (a de `/entidade/procurar`, que passa a viver aqui), e por baixo
   quatro atalhos, cada um uma lista: **com quem trabalhamos** (as que
   têm proposta nossa), **seguidas**, **clientes que mais compram** e
   **concorrentes que mais ganham** (os totais já vivem em
   `entidades.compra` e `entidades.ganha`). O item **Mercado** da barra
   liga-lhe; a ficha do anúncio continua a ligar ao nome.
5. **Clientes de clientes, concorrentes de concorrentes** (D3): os blocos
   «A quem compra» e «A quem vende» já ligam por `liga_entidade()`;
   passam a ligar também no lado da empresa (a entidade de cada proposta
   é uma ligação) e o papel Cliente/Concorrente aparece em todas.
6. O filtro `entid=<chave>` da lista de concursos: `condicoes()` já
   filtra por entidade e por NIF (14/09); confirmar que a chave `n:`
   também resolve, e que **nenhum recorte novo entra em `condicoes()`**
   (regra da casa).

**Código.**

- Banda **contratos e entidades**: `chave_da_entidade_do_anuncio(a)` que
  devolve a chave com ou sem corpus (hoje `entidade_do_anuncio()` devolve
  `""` sem corpus); `lado_da_empresa(chave)` que devolve os anúncios por
  ranhura, as propostas, a taxa e os contactos; `entidades_com_proposta()`,
  `entidades_top(papel, n)`.
- `entidade()` (~15151): deixa de começar por `ha_corpus()`; monta o
  lado do BASE se houver e o da empresa sempre.
- Rota nova `GET /entidades`; `/entidade/procurar` passa a redireccionar
  para lá quando não há termo. O `NAV`: Mercado ganha a sub-vista
  Entidades pelo mesmo mecanismo do Calendário em Concursos (o
  `envolver()` só desenha sub-vistas do item aceso).
- `propostas` ganha a coluna `entidade_chave` (migração idempotente em
  `iniciar_db()`, preenchida a partir de `anuncios` pela `ref`, e no
  `criar_proposta()` daí em diante; nas propostas sem anúncio vem do
  formulário `/proposta/nova`, que já tem o `datalist` de
  `/entidades.json` a devolver NIF). É o que liga a proposta aos
  contactos e à ficha sem comparar nomes.
- `contacto_novo()` (~18190): aceita `entidade_chave` directa, com o
  `volta_ao_referer()` a levar de volta à ficha da entidade.

**Testes.**

- `TestEntidadeSemCorpusTemFicha`: base temporária sem `contratos.db`;
  um anúncio com NIF; `/entidade/<nif>` dá 200 com o anúncio na lista.
- `TestFichaDaEntidadeDizOLadoDaEmpresa`: duas propostas com essa
  entidade, uma ganha e uma perdida; a ficha diz «2 propostas», e a
  ligação abre exactamente as duas (a regra do número que abre a lista).
- `TestContactoNasceNaEntidade`: `POST /contacto/nova` com
  `entidade_chave` e sem `ref`; aparece na ficha da entidade **e** na
  ficha de um anúncio dela.
- `TestListaDeEntidades`: `/entidades` dá 200; os quatro atalhos dão as
  contagens certas; a procura por NIF vai directa à ficha.
- `TestPropostaGuardaAChaveDaEntidade`: `criar_proposta(ref)` preenche
  `entidade_chave`; a migração preenche as antigas e é idempotente.
- `TestNenhumEcraDa500` já existe e apanha a rota nova sozinho.

**Documentação no mesmo commit.** `ESTADO.md`, `docs/armadilhas.md`
(área «contratos e entidades»: a chave é uma só e a ficha existe sem
corpus), `LEIA-ME.md` (o Mercado e a ficha da entidade), `CLAUDE.md`
(banda 7 e a navegação).

### Fase 3 — A proposta sem anúncio, e a regra da escada (esforço 2)

**O que muda.** A página da proposta sem anúncio fica completa, e a
escada passa a ter a regra que o Afonso deu (D4), escrita e testada.

**Regras.**

1. `/proposta/<id>` mostra o bloco «A nossa proposta» inteiro (o mesmo
   `proposta_cx()` da ficha do anúncio, com os campos da ranhura, as
   etiquetas, as tarefas, os contactos da entidade e a cronologia), e
   o botão **apagar** (perigo, com confirmação por `<details>` como o
   apagar de conta). O `proposta_apagar()` volta à ranhura de onde veio:
   `redirect(LISTA + "?estado=…")`, não `/`.
2. O `historico` de uma proposta sem `ref` grava-se com `proposta_id`
   (coluna nova, migração idempotente), e a cronologia lê por `ref` **ou**
   por `proposta_id`. `registar()` ganha o parâmetro.
3. **A condicionante da escada (D4).** Uma tabela `CAMPOS_QUE_A_RANHURA_EXIGE`
   na banda propostas, ao lado de `MOTIVOS_DO_ESTADO`, com o mínimo que
   cada ranhura precisa para ser verdade (D-a):

   | Ranhura | Exige |
   |---|---|
   | analisar, proposta | nada |
   | submetido | `valor_proposta` |
   | relatorio | `valor_proposta`, `lugar` |
   | ganho | `valor_proposta` |
   | perdido | `valor_proposta`, `motivo` de `MOTIVOS_PERDA` |
   | nao_fomos | `motivo` de `MOTIVOS_ABANDONO` |
   | cancelado | nada |

   `mover_proposta()` recebe os campos que vierem no mesmo pedido,
   grava-os **antes** de verificar, e recusa com «falta: preço proposto,
   lugar» quando ainda faltam. Qualquer par de ranhuras continua
   permitido. O selector da linha e o da ficha já mandam o `motivo` no
   mesmo POST; passam a poder mandar os outros campos. (O ecrã que pede
   os campos em falta ao escolher a ranhura é desenho, fica para depois;
   até lá a recusa diz o que falta e o bloco «A nossa proposta» é onde se
   preenche.)
4. Voltar a uma ranhura aberta continua a limpar `fechada_em`
   (`mover_proposta()` já o faz) e regista-se no histórico como hoje.

**Código.** `ficha_da_proposta()` (~18516) reusa `proposta_cx()` com
uma proposta em vez de um anúncio (a função recebe hoje `a`, o anúncio;
passa a aceitar a proposta directamente, que é o que ela realmente usa).
`proposta_apagar()` (~19616). `registar()` e a migração de `historico`.
`mover_proposta()` (~1630) e `escada_da_proposta()` / `escada_do_anuncio()`
(~17899–17909), que passam os campos do formulário.

**Testes.**

- `TestEscadaExigeOQueARanhuraPede`: `analisar → ganho` sem
  `valor_proposta` recusa e diz o que falta; com o valor no mesmo pedido
  passa; `ganho → analisar` passa sem nada (é reabrir).
- `TestPropostaSemAnuncioTemPaginaInteira`: tarefas, contactos da
  entidade, histórico com a mudança de ranhura, e o apagar volta à lista
  da ranhura.
- `TestHistoricoDaPropostaSemRef`: `mover_proposta()` numa proposta sem
  `ref` deixa linha com `proposta_id` e a cronologia mostra-a.

**Documentação no mesmo commit.** `ESTADO.md`, `docs/armadilhas.md`
(área do CRM: a condicionante, e «a escada é livre, o que trava é o
campo em falta»), `LEIA-ME.md`, `CLAUDE.md` (banda 2b), e o
`docs/historico/CRM.md` **não** se edita (é instantâneo): a regra nova
fica aqui e nas armadilhas.

### Fase 4 — As peças que ficaram a meio (esforço 1)

**O que muda.** Uma leitura que parou por o tecto do dia bater volta a
tentar sozinha. Os outros dois becos (sem plataforma, sem texto) ficam
como estão: são limites das fontes, não do radar.

**Regras.** Uma linha de `analise` é **incompleta** quando algum dos
três campos lidos (`objecto`, `equipa`, `documentos_proposta`) está a
NULL. A verificação, depois de `vigiar_pecas()` e antes dos alertas,
chama `reler_incompletas(limite=5)`: só quando `cadeia_esgotada()` é
falso, só anúncios na escada, e pára ao primeiro «sem orçamento». O
`--ler-pecas` sem `tudo` passa a escolher também as incompletas.

**Código.** `analise_incompleta(linha)` e `reler_incompletas()` na banda
da leitura das peças; a chamada em `verificar()` (~6801); o `SELECT` do
`--ler-pecas` (~20361).

**Testes.** `TestLeituraIncompletaVoltaATentar`: uma linha com `equipa`
a NULL é escolhida; uma completa não; com a cadeia esgotada não se
chama o modelo (o fornecedor é um duplo que conta chamadas: é a regra
«separa a condição da espera» do `CLAUDE.md`).

**Documentação.** `docs/armadilhas.md` (área «o modelo que lê as
peças»), `ESTADO.md` (o funil), o diagrama `processo-pecas.html`
regenera-se na fase 5.

### Fase 5 — A documentação (esforço 2)

Detalhada no §4. Faz-se **depois** das fases 1 a 4, sobre o código
final, e é um PR só. A única excepção é o que cada fase corrige no seu
próprio commit, que é obrigatório e não espera.

---

## 4. A documentação, ficheiro a ficheiro

Os números de linha são os de 16/09/2026 e servem para encontrar o
sítio, não para editar às cegas: **verifica cada afirmação contra o
código do dia** antes de a mudar, como os agentes fizeram.

### 4.1 `ESTADO.md` → ~150 linhas (D6)

Fica: o cabeçalho com a tabela «onde está o resto»; «O que isto é» em
dois parágrafos; «Como está a correr» com **uma tabela de números
medidos no dia** (anúncios, procedimentos, com detalhe, por ver, na
escada por ranhura, tarefas por fazer, peças, leituras, testes, linhas
do `radar.py`, tamanho das duas bases) e a data da medição; «O que está
implementado» reescrito ao que existe hoje (Hoje · Concursos com as dez
ranhuras e o calendário · Mercado com contratos e entidades · Configurações
com nove secções · ficha do anúncio · ficha da entidade · ficha da
proposta · alertas e resumo · Portal BASE · Vortal · login e papéis ·
radargov.pt); «O que não corre sozinho»; «O que fica de fora, e porquê»;
«O ponto que falta para a v1».

Sai: toda a narrativa de 13 a 16/09 (as linhas ~58–119 e ~133–505 do
ficheiro de 16/09), que vai **inteira** para o `docs/diario/2026-09.md`
numa secção nova «16/09/2026 — o que o `ESTADO.md` contava até hoje»,
com a nota de que é o texto tal como estava. O diário é acrescento;
nada se reescreve lá.

Também sai o que já está falso: «corre no PC do Afonso, de uma pen»
(~122), «os números são de 4/09» (~131), a lista com quatro abas
(~589–599), «o quadro de seis fases» e «três intenções» (~601–609),
«`v1.0.1` agora» (~764).

### 4.2 `BACKLOG.md`

A tabela «Registo de pendências» reescreve-se com o que está aberto
**hoje**, com quem decide e o que dispara, como manda o próprio
ficheiro:

- as fases deste plano que ainda não estão feitas (cada uma uma linha);
- ligar um alerta ao interesse e seguir entidades (Afonso; o e-mail já
  tem destino);
- julgar as 29 leituras com o `ensaio-de-leitura` (o ponto da v1);
- as três da auditoria ponytail de 14/09 que continuam por decidir
  (fundir `_pecas_*`, `pypdf`→`pymupdf`, e a que se decidiu não fazer);
- repetir a medição do browser da UX-Auditoria (está lá desde 2/09);
- a dívida do HTML por concatenação (AUDITORIA §3.9, 20 505 linhas): não
  é deste plano, mas é a maior pendência estrutural e não estava escrita
  em lado nenhum vivo.

Corrigem-se as linhas do E2 («feito a 31/08» → «o destino esteve vazio
de 8/09 a 16/09») e do CRM («falta o NIF» → posto a 16/09). O resto do
ficheiro (P0–P3, «Feito», «Não fazer») fica: é história com data.

### 4.3 `LEIA-ME.md`

Reescrever as secções que descrevem o que saiu: §5 «O painel» (linhas
~198–218: barra com dois itens, as dez ranhuras, o Hoje), ~248 (a
memória do painel de filtros saiu a 16/09), ~193–194 (`detalhes_por_volta`
é 100 e `relidos_por_volta` 50), ~286–291 (os filtros guardados
acabaram; o que há é «Criar alerta»), ~358 e ~363–364 (não há quadro nem
Pesquisa), ~607–608 («propostas por ranhura»), **§9 «O quadro» inteira**
(~617–670: substitui-se por «A escada e o bloco A nossa proposta»),
**§10 «O calendário»** (~672–684: seis semanas por dia), **§10-A «A
lista»** (~686–700: `/lista` redirecciona; os campos editam-se na
proposta), ~900 (982 testes em ~118 s), ~910 (o `empresa.py` já não lê
o Excel), ~19–21 (não há OneDrive). E as secções novas que as fases 1 a
3 criam: o Hoje com as acções, a ficha da entidade com o lado da
empresa, `/entidades`, a página da proposta sem anúncio, a condicionante
da escada.

### 4.4 `docs/referencia.md`

Purgar ou reescrever: ~1164 (tarefas por `schtasks`), ~1394–1397
(Python da Microsoft Store, duas instâncias no Windows), ~1386
(OneDrive), ~1196–1202 («não há palavra-passe de propósito»; «é preciso
um ecrã para colar a captura», que existe), ~964–1016 (o quadro
inteiro), ~1144–1160 (o calendário em grade de 45 colunas), ~1268 (655
testes), ~1349 (ficheiro único com quatro dependências: são três
módulos e mais dependências), ~1370 (estados `novo/interessa/descartado`
e `fase_id`), ~783 (filtros guardados), ~898 («um filtro só… o separador
dos alertas é onde se gerem os filtros»), ~717 («prazos a menos de 7
dias»: é `dias_urgente()`), ~671 («a barra de baixo»), ~420 («fica para
o OCR», que saiu), ~641 (`ARV_SEL` só: hoje há `ARV_EXC`). As correcções
anteriores que o ficheiro guarda como «esteve aqui escrito que…» ficam:
é a regra da casa.

### 4.5 `docs/armadilhas.md`

Corrigir: ~1463 («isto corre de uma pen»), ~1533 (OneDrive), ~988
(«ainda não está implementado no quadro»: os lotes foram desenhados a
8/09 e o quadro saiu a 15/09), ~1364 contra ~1407 (`--empresa-ligar`
saiu; a segunda menção está a mais), ~359 (`texto_estado` legado: dizer
se ainda existe algum na base). Acrescentar as armadilhas que as fases
1 a 4 deixam (cada fase escreve a sua no seu commit). **Refazer o índice
no fim** e contar as entradas: o comentário das linhas ~28–32 conta duas
vezes em que o índice mentiu.

### 4.6 `CLAUDE.md`

Os números (20 505 linhas do `radar.py`; 24 tabelas com `contactos`,
`propostas`, `tarefas`… confirmar a lista; 982 testes; o número de
armadilhas depois do índice refeito); a banda 8a (o Hoje com o balde
«sem decisão» e as acções); a banda 7 (a ficha da entidade com o lado da
empresa e `/entidades`); a banda 2b (a condicionante da escada). E a
lista de comandos, se alguma fase acrescentar um. A linha deste ficheiro
na tabela dos documentos já lá está desde 16/09.

### 4.7 `docs/design.md`

~480–481 (o Hoje **não** ficou na barra: é o logótipo, decisão dele no
mesmo dia) e ~197–200 (o `--t6` foi aliasado a `--t5`, não removido).

### 4.8 Os instantâneos

Cada ficheiro de `docs/historico/` abre com o mesmo aviso, três linhas,
logo abaixo do título:

> **Instantâneo de DD/MM/AAAA.** Descreve o que se planeou ou mediu
> nesse dia. O que mudou depois está no `ESTADO.md` e no
> `docs/diario/`. Não se edita.

Nos sete que não o têm (`ESQUELETO`, `AUDITORIA`, `SANEAMENTO`,
`UX-Auditoria`, `ONLINE`, `ONLINE-empresas`, `CRM`), e neste quando a
fase 5 fechar. O `CONCORRENTES` já tem o seu e fica. É a **única**
edição que se faz a um instantâneo.

### 4.9 Os diagramas (D7)

Regenerar com a skill `archify`, sobre o código do fim da fase 4, os
cinco que estão errados ou que as fases mudam: `arquitectura.html`
(Vortal e BASE como fontes; três descarregadores; 24 tabelas),
`processo-recolha.html` (o passo `recolher_vortal()` e o
`reler_incompletas()`), `processo-escada.html` (as **dez** ranhuras, as
setas de retorno, a condicionante, e o disparo de `pedir_documentos()`
ao entrar em «por analisar»), `processo-porta.html` (`origem_e_nossa()`
separado do CSRF; o 403 de POST sem sessão), `processo-pecas.html` (a
seta de retorno do «sem orçamento»). O `processo-corpus.html` está certo
e fica. Um diagrama novo, `processo-tarefas.html`, se a fase 1 justificar
(o ciclo de uma tarefa: nasce, muda com o DR, resolve-se, não se toca
quando o prazo passa).

### 4.10 O diário

Uma secção por sessão, como sempre. A desta noite regista o diagnóstico
e as nove decisões; a de cada fase regista o que se mediu e o que mudou
face a este plano.

---

## 5. O que este plano não faz

- **Não desenha ecrãs.** O HTML que as fases acrescentam é o mínimo que
  torna a lógica alcançável (um botão, um formulário de uma linha, uma
  lista). O aspecto é a passagem seguinte do `docs/design.md`.
- **Não move nada sozinho na escada** (D2). Nem por prazo, nem pelo
  Portal BASE (que já só propõe), nem pelo DR (o «Cancelado» automático
  de D5 do `CRM.md` continua a ser só o caso explícito, que é um).
- **Não toca na recolha, nos alertas nem em `condicoes()`.** As listas
  novas (anúncios de uma entidade, propostas de uma entidade) recortam
  por cima, com `com_recorte()`.
- **Não funde os `_pecas_*`, não troca o `pypdf`, não parte o
  `radar.py`.** São as pendências do ponytail e da auditoria; ficam no
  BACKLOG com quem decide.
- **Não resolve «sem plataforma» nem «sem texto».** O primeiro é o
  subagente `explorador-de-plataforma`, caso a caso; o segundo era o
  OCR, que saiu a 3/09 por decisão.
- **Não reabre nenhuma das sete decisões do CRM.**

## 6. Riscos

| | O quê | Guarda |
|---|---|---|
| **A** | A fase 1 mexer no `sincronizar_tarefas()` e apagar ou fechar uma automática por o prazo ter passado | `TestPrazoPassadoNaoMexeEmNada`. É o receio dele por escrito |
| **B** | Uma lista da ficha da entidade não bater com o número que a abre | a regra da casa, e um teste por número (fase 2) |
| **C** | A chave `n:` de uma entidade sem NIF juntar duas entidades diferentes com o mesmo nome | é a limitação do corpus, já documentada em `liga_entidade()`; a ficha di-lo com «sem NIF público» |
| **D** | A condicionante da escada (D4) recusar um movimento que hoje passa, e o selector da linha não ter onde pedir o campo | a recusa diz o que falta; o bloco «A nossa proposta» é onde se preenche; o ecrã que pede no acto é da passagem de desenho. Testado com o POST a trazer os campos |
| **E** | A migração de `propostas.entidade_chave` e de `historico.proposta_id` correr sobre a base de 1,3 GB | são `ALTER TABLE ADD COLUMN`, instantâneos no SQLite; o preenchimento é sobre 73 propostas e 474 linhas de histórico. Ensaiar numa cópia antes de actualizar a instalação, como no CRM |
| **F** | A fase 5 reescrever o `ESTADO.md` e perder algo que só lá estava | a narrativa vai inteira para o diário antes de sair |
| **G** | Os diagramas regenerados ficarem outra vez desactualizados | são instantâneos por definição (`CLAUDE.md`): o que fica é a data no título de cada um |

## 7. Conflitos com o ECC (D6)

O ECC são as regras globais em `~/.claude/rules/ecc/` (as `common/` e
as `python/`), carregadas em todas as sessões. O que este plano faz que
as contraria, e o que manda:

| Regra do ECC | O que o projecto faz | Quem manda |
|---|---|---|
| `python/testing.md`: **pytest**, `--cov`, marcas `@pytest.mark` | `unittest` num ficheiro só, `python teste_radar.py`, sem cobertura medida; o hook `testes_antes_do_commit.py` corre-o | **O projecto.** O `CLAUDE.md` é explícito e o hook depende disso. Não se converte a bateria; as classes novas seguem o molde das 982 |
| `common/testing.md`: 80% de cobertura, três tipos de teste | Cada classe é uma regressão de um erro real; não há E2E | O projecto: «os testes são regressões». Não se instala `coverage` de passagem |
| `common/coding-style.md`: ficheiros até 800 linhas | `radar.py` tem 20 505 | Conhecido desde a AUDITORIA §3.9; **não é deste plano**, e a fase 5 põe-no no BACKLOG como dívida |
| `common/git-workflow.md`: `type: description` | Commits em português, uns com prefixo (`docs:`, `fix:`, `perf+fix:`) e outros sem | Usar o prefixo **e** o português: `feat: as tarefas resolvem-se de qualquer página`. Sem trailer de atribuição |
| `common/agents.md` e `code-review.md`: `planner`, `tdd-guide`, `code-reviewer` antes do commit | Os testes primeiro é já regra da casa | Compatível: cada fase passa pelo `code-reviewer` antes do PR |
| `common/development-workflow.md` §0: procurar no GitHub e em registos antes de escrever | Este plano é todo sobre código que já existe aqui | Sem objecto |
| Agente `doc-updater` e skill `update-docs`: geram `docs/CODEMAPS/*` | O mapa do código é a secção «Arquitectura» do `CLAUDE.md` | **O projecto.** Não se criam CODEMAPS; a fase 5 não usa o `update-docs` |
| Hooks de sessão do ECC (`gateguard`, `governance-capture`) | Os três hooks do projecto em `.claude/settings.json` | Convivem; o do projecto que trava commits com testes a falhar é o que conta |

Nenhum destes conflitos pede mudança ao ECC: são as regras do
`CLAUDE.md` a prevalecer, como o próprio ECC diz (as instruções do
utilizador e do projecto ficam acima das skills).

## 8. Como se executa, para quem não esteve nesta conversa

1. **Lê primeiro** o `CLAUDE.md` inteiro, o `ESTADO.md`, este ficheiro,
   e a área do `docs/armadilhas.md` da fase que vais fazer. O
   `docs/historico/CRM.md` explica a escada, que as três primeiras fases
   tocam.
2. **Uma fase, um ramo `claude/*`, um PR.** Merge para `master` depois
   de validar; a release corta-se depois de o Afonso ver a fase a correr
   na instalação dele (`actualizar.sh`), como no CRM: **cópia da base
   antes** de arrancar com o código novo.
3. **Testes primeiro.** As classes deste plano têm nome; escreve-as a
   falhar, depois o código. `python teste_radar.py NomeDaClasse` corre
   uma; a bateria inteira antes do commit (o hook trava-o se falhar).
4. **Ensaia numa cópia da base**, na porta 8799 ou 8801, com o painel
   de produção de pé em 8765: `copias/` tem uma por dia. É a única
   forma de ver o Hoje com 55 tarefas ou a ficha de uma entidade com
   contratos a sério. Confirma a hora de arranque do processo contra a
   hora do ficheiro (armadilha do processo velho, três vezes paga).
5. **Os quatro documentos vivos no mesmo commit** (`ESTADO.md`,
   `docs/armadilhas.md`, `LEIA-ME.md`, `CLAUDE.md`), e uma secção nova
   no `docs/diario/2026-09.md`. Um commit que muda o `radar.py` sem
   tocar num `.md` é sinal para verificar.
6. **Acrescenta uma linha no §9** deste ficheiro quando a fase fechar: a
   data, o que saiu diferente do plano, e porquê. É a única edição que
   se faz aqui.
7. As decisões do §2 **não se reabrem de passagem**. Se uma fase
   mostrar que uma está errada, escreve-se no diário e pergunta-se.

## 9. O que se fez, e o que o fazer mudou

- **16/09/2026, à noite:** o plano; `email.para` posto; o
  `proximo-prompt.md` apagado; a linha deste ficheiro no `CLAUDE.md` e
  no `BACKLOG.md`. Nenhuma fase começada.
