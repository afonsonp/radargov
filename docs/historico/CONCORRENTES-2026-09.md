# Concorrentes, segunda passagem — 29 de setembro de 2026

A primeira análise é o `docs/historico/CONCORRENTES.md` (29–30/08/2026):
quatro produtos, vistos com as contas do Afonso. Esta é a segunda,
**um mês depois**, e faz três coisas que a primeira não fez: procura
**os que faltavam** (encontrou nove com relevância para Portugal), lê o
**contexto** — o mercado, a lei que muda a 1/10/2026 e a que vem da
Europa — e fecha com a **SWOT do Mira Gov** e os pontos onde ele pode
partir o mercado.

Como todo o `docs/historico/`, é um instantâneo: **descreve este dia e
não se edita**. Cada facto traz a fonte; a lista está no fim.

**O que este documento não fez, e a primeira fez:** entrar nas contas.
A passagem de Agosto mediu paridade ao vivo (3 anúncios nossos
procurados em cada produto); esta é feita de páginas públicas, notícias,
LinkedIn e do relatório anual do IMPIC. Onde digo «declarado» é o
produto a falar de si; onde digo «medido» é a nossa base, só leitura,
na noite de 29/09/2026. **Os testes de paridade de Agosto não foram
repetidos** — repeti-los é o primeiro passo se alguma decisão daqui
depender de cobertura.

---

## 0. Em seis linhas

1. **O mercado mudou de forma em Fevereiro e em Setembro**: a Vortal
   saiu da Hubexo para uma empresa nova (Simplifae, 350 pessoas,
   «AI-first a três anos») e **perdeu o CEO em Setembro** (Miguel Sobral,
   25 anos de Vortal, foi para a Mercell; sucessor por anunciar).
2. **A SpotGov não é o que Agosto registou**: 12 pessoas, 600 k€ de
   ARR, lucrativa e sem ronda (a «seed de 50 M€» é da Augusta Labs, outra
   empresa). Mas declarou em Julho que **vem para as PME** — o nosso
   segmento.
3. **Havia mais concorrentes do que os quatro**: a **TRINTA** (Lisboa)
   faz exactamente o que o Mira Gov faz — DR + peças lidas com fonte +
   escada — a 2 000–4 000 €/mês; a **Adjudica** promete o mesmo «a partir
   de 50 €/mês» e não tem empresa visível; a **Alerta Concursos Públicos**
   vende o DR por 8 €/mês. O tecto e o chão do mercado estão marcados;
   **o meio — IA e escada a preço de PME — está vazio em Portugal**.
4. **A lei muda a 1/10/2026** e muda contra a nossa fonte: os limiares
   sobem e **28% dos anúncios de 2025 (54% nas obras) ficam na banda que
   deixa de obrigar a concurso público** — medido na nossa base. É a
   maior ameaça externa, e ao mesmo tempo a maior oportunidade, porque
   o mercado que sai do DR entra no Portal BASE, que só nós temos inteiro
   em disco.
5. **O Mira Gov ganha onde é auditável**: cobertura total da parte L de
   hora a hora, dez anos de anúncios e dois milhões de contratos por
   NIF, leitura das peças por família de contrato com a página, e a
   escada com o vocabulário do CCP. **Perde onde é uma pessoa e um PC**:
   sem preço, sem sociedade, um cliente (a própria empresa), e a leitura
   ainda por anunciar.
6. **A rotura possível não é um ecrã**: é ser o único que **diz em que
   regime está cada concurso**, que **publica a sua régua de leitura**, e
   que transforma o mercado invisível (consultas prévias, convites) em
   «quem convida quem» a partir do BASE.

---

## 1. Os quatro de Agosto — o que mudou

### 1.1 Armilar / Vortal → Simplifae

| | Agosto | Setembro |
|---|---|---|
| Dono | Vortal (Hubexo, ex-Byggfakta) | **Simplifae**, empresa autónoma desde 24–27/02/2026: Vortal, Armilar, eZam, Marketplanet, OnePlace, Plyca; 350 pessoas, PT+ES+PL |
| CEO | Miguel Sobral | **Saiu ≈16/09/2026** para CEO da Mercell (Oslo, 5 000 entidades públicas). Sucessor: **não anunciado** — o site ainda o lista |
| Preços | sob consulta (~200 €/mês pago pela empresa) | Igual; a página de planos não muda desde 18/05/2026 |
| IA | resumo com fontes e Q&R testados ao vivo | Página «Armilar AI» (30/07/2026) junta **probabilidade de renovação** (alta/média/baixa por CPV, tipo, histórico do comprador) e **CPV por algoritmo** nos anúncios sem CPV. Declarado: «−50% do tempo», «2× oportunidades» |
| Eventos | — | Último webinar a 30/10/2025; nenhum anunciado |

**Leitura.** A incumbente está em transição de dono e de direcção no
mesmo ano, com uma promessa pública de IA a três anos. Isso torna-a ao
mesmo tempo **mais lenta** (uma empresa a reorganizar-se e sem CEO não
corta preço nem lança produto em Outubro) e **mais motivada** (a
promessa foi feita ao mercado e a um accionista). Um facto de Agosto
continua a valer e é o mais importante: **a Armilar lê mesmo as peças**,
com fontes e página. O argumento «eles não lêem» não existe — o nosso é
outro, e está no §7.

**O que é nosso e eles têm o dado para fazer:** a probabilidade de
renovação. O Mira Gov tem o `fim_estimado` e a lista (B03, 30/08); não
tem a probabilidade. A `docs/FUNCIONAL.md` §7.2 já descreve como se
mede («costuma voltar ao DR 2–4 meses antes do fim»).

### 1.2 GovGo (VIPA)

Nada mudou: 50 €+IVA/semestre, 90 €+IVA/ano, «app brevemente nas
stores» há mais de um ano (o `vipa.pt` diz «disponível»; o Google Play
e a App Store não a têm a 29/09/2026), zero notícias em 2026, as mesmas
seis funcionalidades. A lacuna de cobertura medida em Agosto (0/3, o
dia 28/08 com 8 procedimentos contra os nossos 99) **não foi
reverificada** e não há razão para pensar que fechou.

**Leitura.** É o produto que define o «barato e simples» em Portugal,
e está parado. Não é ameaça; é a referência de preço que um cliente
pequeno vai citar («a GovGo custa 7,5 €/mês»).

### 1.3 SpotGov — corrigir Agosto

O registo de Agosto misturava duas empresas. O que se confirmou:

| | O que Agosto dizia | O que é (verificado) |
|---|---|---|
| Empresa | Augusta Labs (Rodrigo Fernandes, João Cerejeira) | **SpotGov é empresa própria, fundada em 2025**; Alves foi *entrepreneur in residence* na Augusta Labs antes |
| CEO | «João Alves, discrepância não resolvida» | **João Ramalho Alves**, co-fundador e CEO (IST, ex-BCG) |
| Ronda | «seed a 50 M€ de avaliação, jun/2026» | **É da Augusta Labs** (Expresso, 2/06/2026). A SpotGov diz: 600 k€ de ARR no 1.º ano (abr/2025–abr/2026), **lucrativa, sem investimento externo**, «a avaliar opções» |
| Equipa | «40+ pessoas» | **≈12** (entrevista de 25/06/2026), «20 daqui a seis meses»; vaga de *Applied AI Engineer* a ≈23/09 |
| Clientes | enterprise | Declarado: **>100 clientes em 13 sectores**, ≈1,5 mil M€ em concursos (~10% do volume nacional); nomeado só a Palex |
| Preço | sob consulta | Igual: Standard e Plus, 6 ou 12 meses; `/pricing` dá 404 |

**O que é novo e importa:**

- **Declarou (9/07/2026) descer de enterprise para mid-market e PME.**
  É o nosso segmento, dito em público.
- Expansão a **Espanha e Reino Unido**, «sem calendário fixo».
- No site: «Personalização Setorial — brevemente» (o nosso Q3, feito
  a 28–29/09 pelo `familia_do_contrato()`) e «processos adjacentes».
- A métrica de marketing passou de «≈25 h/utilizador/semana» para
  «125 h/semana por cliente». Sem fonte independente, como antes.
- Patrocinador principal do **Public Law Summit** (23/10/2026, Porto),
  com o CEO como orador. Estão a comprar a conversa com os juristas.

**Leitura.** Uma empresa de 12 pessoas com 100 clientes e sem capital
externo não cobre tudo ao mesmo tempo: enterprise, PME, Espanha, Reino
Unido, personalização sectorial, geração de propostas. **É o
concorrente mais parecido em ambição e o mais exposto em foco.** O que
eles fazem e nós decidimos não fazer (gerar e rever propostas por IA)
continua a ser a fronteira — ver §6 e §7.

### 1.4 Tendios

**A tabela de preços mudou** (lida no código da página a 29/09/2026):

| | Pro | Business | Advanced | Enterprise |
|---|---|---|---|---|
| €/mês | 37 | 168 | 345 | «consultar» (589 no código) |
| €/ano | 372 | 1 692 | 3 480 | «consultar» (5 940) |
| Histórico | 6 meses | 2 anos | 4 anos | personalizado |
| **Créditos de IA/mês** | 25 | 500 | 1 000 | 10 000 |
| Países | 1 | 1 | 1 | personalizado |

O que saiu e entrou: **o Lite de 5 € desapareceu**; o Enterprise deixou
de ter preço público; a IA passou a vender-se **em créditos** por plano;
a «pré-selecção automática pela Vera» é só Enterprise; e há serviços
humanos novos — **600 € por concurso (ou 1% do preço base)** e 80 €/hora.
Lançaram a 18/09/2026 o «Tendios Local» para autarquias espanholas
pequenas. Ronda de 2 M€ em Maio/2025 (Easo, Ona, Archipelago, Lukkap);
Barcelona, 2023, co-CEOs Xavier Creus e Albert Riera.

**Portugal continua a não ser prioridade**: um país por plano, site só
em castelhano, o único conteúdo português é um guia para empresas
espanholas venderem cá, e fala do BASE — não do DR nem das plataformas.
Os defeitos de Agosto (13 entidades num NIF, fichas em duplicado,
encoding partido) **não foram reverificados**.

**Leitura.** A Tendios está a subir de preço e a vender IA ao crédito:
é o que faz um produto com ronda e custos de modelo reais. O nosso
custo marginal de leitura é próximo de zero (reservas gratuitas, leitura
partilhada entre empresas) — isso é uma vantagem de preço, e é também
uma fragilidade (§6).

---

## 2. Os que faltavam

A primeira análise partiu dos produtos que o Afonso conhecia. Esta
procurou o mercado inteiro: portugueses, espanhóis, europeus,
internacionais, e os serviços oficiais. Só os que **cobrem Portugal ou
podem vir a cobrir** ficam aqui; os outros (Stotles, Tussell, Tracker,
DeepStream, Vultron, Govly, Loopio, Responsive, AutogenAI…) confirmaram-se
como UK/US sem fontes portuguesas — não são concorrentes de uma PME
portuguesa e não voltam a este documento.

### 2.1 Os dois que interessam mesmo

**TRINTA** (`trinta.ai`, Lisboa) — *«o Mira Gov a 24–48 k€/ano»*

- Fontes declaradas: DR, BASE, Vortal, acinGov, anoGov, ComprasPT, TED,
  «lidas diariamente»; «10 fontes portuguesas mapeadas, 8 com conector».
- **Case Files**: lê as peças e extrai o prazo real («dos documentos,
  não do resumo do portal»), preço base e lotes, pesos dos critérios,
  ISO, cauções, visitas, esclarecimentos — **e cita o documento de
  origem**. É a nossa leitura com fonte.
- **Pipeline**: 12 estados (Encontrado → … → Ganho/Perdido), rascunho
  da proposta estruturado nos critérios, partilha por WhatsApp.
- Dois módulos que não temos: **Signals** (intenção do comprador antes
  do anúncio) e **Forensics** (impugnação de adjudicação).
- Preço público: **Radar 2 000–2 500 €/mês** (1 mercado, 3 lugares, 100
  documentos/mês); **Pipeline 4 000 €/mês**; piloto pago de 2 000 €.
  Público declarado: exportadores e industriais com ≥10 M€ de contratos
  decididos por ano.
- Nasceu **dentro de uma empresa** (Ultra Controlo, gases medicinais) —
  a mesma origem que a nossa. Fundação e capital: não encontrados.
- A página `trinta.ai/plataformas-de-concursos` publica uma contagem
  útil: 17 634 anúncios de abertura entre 2/01 e 7/08/2026, com
  **Vortal 48,4% + acinGov 42,8% = 91,2%** das peças.

**Leitura.** É o produto **mais parecido com o Mira Gov que existe em
Portugal**, feito pela mesma razão. Não disputa a PME de 100–200 €/mês —
mas prova que o pacote se vende, e a que preço. Se descerem de escalão
são o concorrente directo; enquanto não descem, são **a referência de
preço por cima**.

**Adjudica** (`adjudica.biz`) — *«o Mira Gov a 50 €/mês, sem empresa»*

- «Portugal · Germany · Spain»; fontes PT declaradas: **Portal
  BASE/IMPIC** — **não cita o DR**. Mostra concursos portugueses
  abertos com CPV e preço base; «27 950 concursos abertos».
- Avaliação *go/no-go* «que cita a página do documento», «quando falta
  um facto o agente pergunta em vez de inventar», dossiês de proposta,
  pontuação contra os critérios antes de submeter.
- «Free to start… monthly plans start at €50».
- **Sem entidade jurídica, morada, fundadores, data, imprensa.** Sem
  `/pt`, sem `/pricing`, sem `/privacy`.

**Leitura.** Mesmo público, mesmo preço, mesma promessa — e invisível.
Duas hipóteses: um produto a sério em lançamento silencioso, ou uma
página de captura de leads. **Vale uma conta e um teste de paridade
contra a nossa base** (é o gesto de Agosto, e leva uma hora). O que lhes
falta face a nós, pelo que declaram: a parte L como fonte, e o
vocabulário da escada.

### 2.2 Os alertas baratos — o chão do mercado

| Produto | Preço | Fonte | O que não tem |
|---|---|---|---|
| **Alerta Concursos Públicos** (NoOperation, Lda., V. N. da Barquinha) | 10 €/mês · 96 €/ano | DR | IA, peças, CRM, contratos |
| **Helpdesk Público** | 24,99 €/mês (5 CPV) · 16,67 €/mês anual (20 CPV) | plataformas + DR, por CPV | idem |
| **anoGov — Alertas** (ANO Software) | 180 €/ano, ou nos packs 677 / 1 620 / 3 989 €/ano | «todas as plataformas» | idem; é um e-mail acoplado à plataforma |
| **ComprasPT — +Concursos** | 180 €/ano | «todas as plataformas» | idem |
| **acinGov — Standard/Gold/Premium** | 615 €/ano · 115 €/mês · 155 €/mês | Standard só acinGov; Gold/Premium «todas» | idem; a IA da ACIN é para compradores |
| **Tender Radar** (`tenderradar.io`, sede não declarada) | 79 €/mês (3 portais) · 149 €/mês (10 portais, resumos por IA) | «acinGov e Diário da República (Portugal)» + NL/FR/DE/ES/FI/IT/TED | CRM |

**Leitura.** É aqui que uma PME que hoje «abre o DR de manhã» vai
primeiro: 8 a 25 €/mês para não o abrir. Nenhum destes lê peças,
nenhum tem escada, nenhum cruza com o BASE. **O Mira Gov não compete
com eles em preço — compete em «e depois do alerta?»**. Mas define o
chão: um preço acima de ~100 €/mês tem de justificar o salto com o que
eles não fazem.

### 2.3 Os serviços oficiais e gratuitos

- **Diário da República**: subscrição gratuita do **índice** diário das
  1.ª e 2.ª séries por e-mail, e RSS. Não filtra por CPV, entidade nem
  preço. Os alertas por «chaves de pesquisa» do antigo dre.pt **não se
  confirmam** na página nova.
- **Portal BASE**: **sem alertas** por e-mail. Novidades de 2026 são só
  do Base4 actual (pesquisa da área pública a 10/07, anúncios de
  adjudicação ao JOUE a 30/07, consultas preliminares a 19/01, PNFE).
- **Novo portal do IMPIC**: 1,5 M€, anunciado a 4/02/2025 com «IA» e
  «notificação de utilizadores individualmente ou em grupo por
  parâmetros dinâmicos»; produção prevista para **Abril de 2026**.
  **A 29/09/2026 não há rasto de lançamento**, nem data. É a ameaça
  oficial a médio prazo: um alerta gratuito por CPV, do Estado.
- **TED**: conta gratuita, 25 pesquisas guardadas, 25 alertas por
  e-mail, RSS — **só acima dos limiares europeus** (140 k€ / 216 k€ /
  5,404 M€). Não vê a parte L.
- **dados.gov**: o dump do BASE **continua**, última actualização
  27/09/2026 (o nosso corpus é de 28/09). OCDS desde 2019. Sem API nova.

### 2.4 Espanha — os que podem atravessar a fronteira

Todos verificados como **só Espanha** a 29/09/2026, mas com o nosso
pacote funcional (alertas + IA sobre pliegos + kanban) e preços de PME:

| | Preço | O que tem |
|---|---|---|
| **LICAI** (Eivor Systems) | grátis (5) · 29 · 79 · 199 €/mês | pipeline de 9 fases, RAG, agentes que geram memória técnica em DOCX |
| **Gobierto Contratación** | 150 · 300 · 475 · 1 490 €/mês | redactor IA, kanban, todas as plataformas ES |
| **Tenderyou** (Gijón, Lanzadera) | grátis · 149 €/mês | análise de pliegos; «não redige propostas» (a nossa posição) |
| Licitar y Ganar IA | 49 · 120 · 249 €/mês | probabilidade, análise, preenchimento de anexos |

**Leitura.** A SpotGov vai para Espanha; o movimento inverso é
plausível, e Agosto mostrou o custo de o fazer mal (Tendios: taxonomia
espanhola, «Oporto», encoding partido). Um espanhol que entre cá com o
DR bem lido a 29–79 €/mês é o cenário que mais nos aperta. A vigiar de
seis em seis meses; não a temer hoje.

### 2.5 Vencer.ai

Indexado pelo Google como «IA para Concursos Públicos em Portugal»
(monitorização em todas as plataformas, análise de documentos, chat,
pontuação, kanban; blog de 2025). **A 29/09/2026 o site devolve 404 em
todas as páginas** (erro do Railway). Ou morreu, ou está entre versões.
Preço, empresa, fundadores: não encontrados.

### 2.6 O que não existe, para não voltar a procurar

Gatewit (licença cancelada pelo IMPIC em 2016/17); SaphetyGov (vendida à
Vortal a 16/04/2020 — não consta das quatro licenças de hoje: VortalGOV,
acinGov, ComprasPT, anoGov); Konvix, iConcursos, Licitações.pt, Aviso.pt
(não existem como produto). Granter é fundos europeus, não concursos.

---

## 3. O contexto — o mercado e a lei

### 3.1 O mercado, pelos números do IMPIC (relatório de 2025, 15/07/2026)

- **254 685 contratos, 24,77 mil M€** em 2025: +14% em número, **+33% em
  valor**, «os números mais altos dos últimos 5 anos». Obras +52% em valor.
- **218 828 procedimentos**; ajuste directo + consulta prévia = **70%
  do número**; concurso público = **16% do número e 53% do valor**.
- **5 517 entidades adjudicantes**; **≈50 700 adjudicatários distintos**,
  95% sediados em Portugal.
- Concorrência fraca: na consulta prévia a moda é **1 proposta (51%)**;
  nos contratos do TED, **38% têm um só concorrente** (UE: 28%). A SpotGov
  declara que 23% das candidaturas são excluídas por erros
  administrativos.
- **PME**: o IMPIC não desagrega. O Scoreboard europeu (só TED, 2024)
  dá **79% dos contratos a PME** (UE: 71%).
- Anúncios da parte L por ano: sem contagem oficial. **Medido na nossa
  base: 29 285 anúncios de procedimento em 2025** (excluídas as
  republicações e a Vortal). A TRINTA contou 17 634 entre Janeiro e
  Agosto de 2026 — bate com o nosso ritmo.
- Só 43,7% dos procedimentos (87% do valor) correm em plataforma
  electrónica; o indicador **caiu** 3,6 p.p. em 2025.

### 3.2 O DL 177/2026 — a 1 de Outubro, quinta-feira

O que o `docs/ccp.md` já guarda vale aqui; o que importa à
concorrência é o efeito na **fonte**:

| Limiar | Antes | Desde 1/10/2026 |
|---|---|---|
| Ajuste directo, bens/serviços | 20 000 € | **75 000 €** |
| Consulta prévia, bens/serviços | 75 000 € | **130 000 €** |
| Ajuste directo, empreitadas | 30 000 € | **150 000 €** |
| Consulta prévia, empreitadas | 150 000 € | **1 000 000 €** |

Mais: **consulta prévia especial** (mínimo 5 convidados, **sem
publicidade**, até 2 M€ em fundos europeus, habitação, digital, saúde,
apoio social); **concurso público flexível** abaixo dos limiares
europeus com pronúncia e impugnação em 3 dias; **preço base
facultativo** e «valor estimado» a comandar (mexe no campo que
extraímos); habilitação «só uma vez»; e o **art. 1.º-C**, que manda as
entidades usar sistemas digitais «incluindo IA» com supervisão humana e
explicabilidade.

**O que sai do DR — medido na nossa base, noite de 29/09/2026.** Dos
29 285 anúncios de 2025, 28 839 têm o tipo de contrato na secção 6:

| Família | Anúncios em 2025 | Na banda que deixa de obrigar a concurso público | % |
|---|---|---|---|
| Bens (75–130 k€) | 12 316 | 2 274 | 18% |
| Serviços (75–130 k€) | 9 278 | 1 830 | 20% |
| **Obras (150 k€–1 M€)** | 7 245 | **3 936** | **54%** |
| **Total** | 28 839 | **8 040** | **28%** |

Dois cuidados na leitura. É um **tecto**, não uma previsão: em 2025
havia 4 116 anúncios de bens **abaixo** dos 75 k€ que já não eram
obrigados a concurso e foram a concurso na mesma — as entidades
publicam por hábito, por regulamento interno ou por fundos. E é
**por preço base**, que a lei nova torna facultativo. Mas a ordem de
grandeza é esta: **entre um quinto e um quarto do que hoje entra na
parte L pode deixar de entrar, e nas obras mais de metade.** Quem vive
só do DR (GovGo, Alerta Concursos, Tender Radar) encolhe; quem tem o
BASE (nós, Armilar, TRINTA, Adjudica) vê o mercado mudar de sítio, não
desaparecer.

A crítica pública (Transparência Internacional; três juristas no ECO
a 17/04/2026) é sobre concorrência e corrupção — «impossível separar
o aumento do poder discricionário de riscos de corrupção» —, e um dos
juristas avisa que **a revisão europeia vai obrigar a rever outra vez**.

### 3.3 O que vem a seguir

- **Regulamento europeu de contratação pública** — proposta da Comissão
  a **9/09/2026** (COM(2026) 590): **revoga as três directivas de 2014**
  e substitui-as por um regulamento de aplicação directa; negociação
  como regra, **peso mínimo de qualidade de 30%** (50% em serviços
  intensivos em mão-de-obra), preferência europeia opcional, «once-only»,
  espaços de dados. Negociações até Q4 2027, transição de 2 anos →
  aplicação plausível 2029–30 (derivado). O CCP vai mudar outra vez.
- **Tribunal de Contas**: proposta de 9/04/2026 sobe o visto prévio de
  750 k€ para **10 M€** («90% dos contratos» deixam de passar por lá);
  por aprovar na AR.
- **AI Act**: o Digital Omnibus (em vigor 27/07/2026) adiou o alto risco
  para 2/12/2027; **a transparência do art. 50 vale desde 2/08/2026**.
  ANACOM é a autoridade. Uma ferramenta que **lê e mapeia** para o
  fornecedor não é alto risco; passa a ter obrigações se **gerar** texto
  entregue a terceiros. A AdC vai aplicar ML aos dados do BASE em 2026
  para apanhar propostas coordenadas — texto «igual» gerado por
  ferramentas partilhadas passa a ser um risco para quem o entrega.
- **Financiamento no segmento, na Europa**: Stotles 13 M USD (05/2025),
  Tendium 2 M USD (03/2026), Mercell consolidada pela Thoma Bravo desde
  2022 — e com o ex-CEO da Vortal desde Setembro. Nenhum cobre Portugal
  em profundidade.

---

## 4. Matriz comparativa — 29/09/2026

✅ tem e funciona · ⚠️ parcial, ou declarado sem prova · ❌ não tem ·
— não se sabe. A coluna do Mira Gov é o estado de hoje (`ESTADO.md`);
as outras, o que se viu em Agosto mais o que mudou (§1) e as páginas
públicas (§2). **Os asteriscos marcam o que só se viu em demo ou
declaração.**

| Capacidade | Mira Gov | Armilar | SpotGov* | TRINTA* | Adjudica* | Tendios | GovGo | Alerta CP |
|---|---|---|---|---|---|---|---|---|
| Parte L do DR, tudo, auditável | ✅ hora a hora | ⚠️ 2/3 em Agosto | ✅ declarado | ✅ declarado | ❌ não cita o DR | ✅ 3/3 em Agosto | ❌ 0/3 | ✅ declarado |
| Consultas preliminares / mercado sem DR | ✅ Vortal | ✅ | ✅ decl. | ⚠️ «Signals» | — | ✅ | ❌ | ❌ |
| Peças na ficha, descarregadas sozinhas | ✅ 4 plataformas | ✅ | ✅ | ✅ | — | ⚠️ só fonte Vortal | ❌ | ❌ |
| Leitura das peças com **página** | ✅ 12 campos, por família | ✅ | ⚠️ demo | ✅ decl. | ✅ decl. | ❌ (Agosto) / créditos | ❌ | ❌ |
| Leitura **por tipo de contrato** | ✅ 5 famílias (28–29/09) | ❌ | ⚠️ «brevemente» | — | — | ❌ | ❌ | ❌ |
| Chat livre sobre as peças | ❌ decisão | ✅ <20 s | ✅ | — | ⚠️ «pergunta» | ⚠️ Vera | ❌ | ❌ |
| Identidade por NIF, em todo o lado | ✅ | ✅ | ⚠️ | — | — | ❌ 13/NIF | ⚠️ | — |
| Contratos celebrados, locais e completos | ✅ 2,0 M, 2012→ | ✅ ≥2014 | ✅ decl. | ✅ decl. | ✅ BASE | ⚠️ a peso | ⚠️ parado 01/2025 | ❌ |
| Desconto por entidade/CPV, homólogos | ✅ ficha + comparação | ✅ + nº licitadores | ✅ demo | — | — | ⚠️ | ❌ | ❌ |
| Renovações (contratos a acabar) | ✅ lista | ✅ + probabilidade | ✅ | — | — | ❌ | ❌ | ❌ |
| Escada / CRM de propostas | ✅ 10 ranhuras, CCP | ⚠️ tarefas | ✅ kanban | ✅ 12 estados | ✅ decl. | ✅ | ❌ | ❌ |
| Tarefas, donos, calendário, iCal | ✅ (iCal por fazer) | ⚠️ | ✅ | ⚠️ WhatsApp | — | ✅ | ❌ | ⚠️ prazo |
| Contactos da entidade, notas, cofre de documentos | ✅ | ❌ | ✅ CRM | — | — | ✅ CRM | ❌ | ❌ |
| Exclusões e E/OU nos filtros | ✅ | ⚠️ | ✅ | — | — | ✅ | ❌ | ⚠️ |
| Alerta de alterações/anulações | ✅ no resumo | ❌ | ⚠️ | — | — | ✅ | ✅ favoritos | ❌ |
| Alerta imediato | ✅ «avisar logo» | ⚠️ 3 momentos | — | — | — | ✅ | ❌ diário | ❌ diário |
| Pesquisa no texto integral dos anúncios | ❌ (existe em disco) | ⚠️ | ✅ | — | — | ⚠️ | ❌ | ❌ |
| Geração / revisão de propostas por IA | ❌ **decisão** | ❌ | ✅ BETA | ✅ rascunho | ✅ dossiê | ✅ Advanced | ❌ | ❌ |
| Previsão do preço vencedor | ❌ decisão | ⚠️ desconto estimado | ✅ BETA | — | — | ❌ | ❌ | ❌ |
| Regime legal do concurso (antes/depois de 1/10) | ❌ **por fazer, dado existe** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Multi-empresa, papéis, 2FA, cópias cifradas fora | ✅ | ✅ | ✅ | ✅ | — | ✅ | ⚠️ | ⚠️ |
| API / integrações CRM-ERP | ❌ | ⚠️ Lusha | ✅ decl. | ✅ Pipeline | — | ✅ Enterprise | ❌ | ❌ |
| Português de Portugal, taxonomia do CCP | ✅ | ✅ | ⚠️ EN traduzido | ⚠️ EN | ⚠️ EN | ❌ ES | ✅ | ✅ |
| Preço público | ❌ **por definir** (beta grátis) | ❌ (~200 €/m) | ❌ | ✅ 2 000–4 000 €/m | ✅ «desde 50 €» | ✅ 37–345 €/m | ✅ 7,5 €/m | ✅ 8–10 €/m |
| Prova social (clientes nomeados) | ❌ 1 (a LATD) | ✅ | ⚠️ 1 nomeado, «100+» | ⚠️ 1 (a casa-mãe) | ❌ | ⚠️ «5 000» | — | — |

### 4.1 O mapa de preços, por mês e sem IVA

```
   8 €   Alerta Concursos Públicos ── só DR, só alerta
   7,5 € GovGo ───────────────────── só DR, lacunas
  25 €   Helpdesk Público ────────── por CPV
  37 €   Tendios Pro ─────────────── ES, 25 créditos de IA, 6 meses
  50 €   Adjudica (declarado) ────── IA + dossiê, sem empresa visível
  79 €   Tender Radar ────────────── 3 portais, sem CRM
 115 €   acinGov Gold ────────────── alerta acoplado à plataforma
 149 €   Tender Radar Pro ────────── resumos por IA
 168 €   Tendios Business ────────── 500 créditos, 2 anos
~200 €   Armilar (o que a LATD pagava) ─ IA que lê, PT+ES, sob consulta
 345 €   Tendios Advanced ────────── 4 anos, gerador 5/mês
   ?     SpotGov ─────────────────── sob consulta; «vem para as PME»
2 000 €  TRINTA Radar ────────────── o nosso pacote, 3 lugares
4 000 €  TRINTA Pipeline ─────────── + API, TED, 10 lugares

   ?     Mira Gov ────────────────── beta fechada, gratuita
```

**O que o mapa diz:** entre os 50 € declarados por um produto invisível
e os 200 € da Armilar **não há em Portugal nenhum produto verificado que
junte DR completo + peças lidas com fonte + escada**. A TRINTA prova
que o pacote vale 2 000 €; os alertas provam que o gesto de «não abrir
o DR» vale 8 €. O Mira Gov cabe no meio, e o meio está vazio.

---

## 5. Onde o Mira Gov está hoje, medido

Para a SWOT não se apoiar em impressões (`ESTADO.md`, 29/09/2026):

- **210 811 anúncios** (200 291 procedimentos), dez anos (2015→), 185 886
  com o texto integral; verificação de hora a hora, das 08:00 às 20:00.
- **2 009 640 contratos** e 180 507 entidades do BASE, em disco, por NIF.
- 436 peças em disco de 79 concursos; **70 leituras**, a régua a **103 de
  113 passagens** depois de duas rondas a 29/09; a leitura marcada como
  rascunho na ficha e **ainda não anunciada** («falta reler com a
  pergunta de agora e voltar a julgar»).
- Multi-empresa desde 23/09, com **uma** empresa (a LATD); **zero
  alertas ligados, zero entidades seguidas**; site com beta fechada
  gratuita; **preço por definir**; sociedade por abrir.
- 27 releases em Setembro (v2.0.1 → v2.0.27); 1 701 testes; `radar.py`
  com 35 380 linhas, HTML por concatenação.
- Uma pessoa a programar, um PC a servir (túnel da Cloudflare), cópias
  cifradas no B2 (UE) desde 24/09, 2FA na conta do dono desde 28/09.
- Leitura pelo modelo em **reservas gratuitas** (Groq, Cerebras, NVIDIA,
  OpenRouter), com tectos por dia e sem contrato.

---

## 6. SWOT do Mira Gov

### Forças (internas, medidas)

1. **A fonte, inteira e auditável.** Entra tudo o que a parte L publica,
   de hora a hora, sem filtro à entrada; qualquer cliente pode confirmar
   um anúncio no DR pelo link. Em Agosto a Armilar falhou 1 em 3 e a GovGo
   3 em 3. Ninguém mais publica a sua cobertura de forma verificável.
2. **Dez anos de anúncios e dois milhões de contratos, no disco, por
   NIF.** A Tendios vende quatro anos de histórico por 3 480 €/ano; a
   GovGo está parada em Janeiro de 2025. O Mira Gov refaz o corpus do
   dump público em minutos, e a chave é o NIF em toda a aplicação
   (`chave_entidade()`), que é o defeito que partia os painéis da Tendios.
3. **A leitura das peças, com a página, por família de contrato, e
   marcada como rascunho.** Doze campos, o campo 11 a variar com o tipo
   (equipa · equipa técnica e alvará · artigos · postos e horários ·
   nível de serviço), cada linha com a página, o que não está nas
   páginas lidas marcado «para confirmar», e uma régua com 113 passagens
   que se corre antes de mudar a pergunta. A SpotGov anuncia a
   personalização sectorial como «brevemente». A Armilar tem a página;
   não tem a família nem a régua.
4. **A escada fala CCP.** Dez ranhuras com o vocabulário da lei
   (audiência prévia, relatório preliminar, os motivos de perda
   fechados), campos que a ranhura exige, o preço acima da base recusado
   à entrada, e o `docs/ccp.md` conferido no texto oficial com o
   DL 177/2026 já lido. A TRINTA tem 12 estados em inglês; a Tendios a
   taxonomia espanhola.
5. **Custo marginal próximo de zero.** A leitura é da plataforma e
   partilhada entre empresas; o modelo corre em reservas gratuitas; o
   DR e o BASE são públicos. O Mira Gov pode fixar preço onde os outros
   não conseguem (a Tendios vende IA ao crédito por isto).
6. **Nasceu dentro de uma empresa que concorre, e itera à velocidade
   de um dia.** 27 releases num mês, duas rondas de teste com 10 e 20
   perfis, a segunda ronda da leitura no mesmo dia da terceira ronda de
   testes. É a mesma origem da TRINTA — com um ciclo dez vezes mais
   curto do que qualquer incumbente.
7. **Nada da empresa passa pelo modelo, e nada sai do país.** As
   propostas, os CV e os documentos da empresa não vão ao modelo (decisão
   de princípio); os dados estão num disco em Portugal com cópia cifrada
   na UE. Com o art. 50 do AI Act e a AdC a vigiar propostas «iguais»,
   isto passou de escolha a argumento.
8. **Português de Portugal, sem tradução.** Contra a interface em inglês
   da SpotGov, da TRINTA e da Adjudica, e o castelhano com fugas da
   Tendios.

### Fraquezas (internas, medidas)

1. **Uma pessoa, um PC.** Bus factor 1; o painel serve de um computador
   pessoal por um túnel; se o PC morre, o serviço pára até se restaurar
   noutro (as cópias existem; o tempo de restauro nunca se mediu com
   clientes a olhar).
2. **Sem preço, sem sociedade, sem prova social.** O site diz «gratuito
   na beta» e «preço por anunciar»; a única empresa é a do Afonso; não há
   um cliente nomeado nem um testemunho. A SpotGov diz «100+»; a TRINTA
   nomeia a casa-mãe.
3. **A leitura ainda não se anuncia.** A régua está em 103/113, mas as
   70 leituras estão por reler com a pergunta de agora e por julgar. Até
   lá, a força 3 é uma promessa interna.
4. **As duas fontes dependem de acessos que não são nossos.** O DR por
   capturas cURL feitas à mão; as peças por acesso anónimo à Vortal e à
   acinGov (91% dos anúncios). O IMPIC tem um portal novo atrasado e sem
   data; a INCM mudou o sistema de submissão em Janeiro. Uma mudança de
   forma pára a recolha até alguém refazer a captura.
5. **O modelo em reservas gratuitas.** Tectos por dia, sem SLA, a NVIDIA
   esteve morta de 3/09 a 28/09 sem ninguém dar por isso. Um cliente que
   pague não pode ouvir «a reserva está esgotada».
6. **O que decidimos não ter, o mercado vende**: chat livre sobre as
   peças (Armilar, SpotGov, Tendios), geração e revisão de propostas
   (SpotGov, TRINTA, Tendios, Adjudica, LICAI), previsão de preço
   (SpotGov), API e integrações (TRINTA, Tendios, SpotGov). São
   decisões, não faltas — mas cada uma vai aparecer numa demo perdida.
7. **Pesquisa no texto integral por fazer**, com 185 mil textos em
   disco (o `contratos_fts` já mostrou o caminho a 29/09).
8. **Dívida estrutural**: 35 mil linhas num ficheiro, HTML por
   concatenação; cada ecrã novo custa mais do que o anterior. Não se vê
   de fora; vê-se no ritmo daqui a seis meses.
9. **Sem marketing, sem canal de venda.** O site existe desde 23/09; o
   pedido de acesso responde-se à mão em dois dias úteis; ninguém está a
   vender.

### Oportunidades (externas, com fonte)

1. **O mercado está em máximo histórico**: 24,77 mil M€ (+33%), 254 685
   contratos, ≈50 700 fornecedores — e o Governo quer subir de 8% para
   15% do PIB. Mais empresas a precisar de vigiar mais concursos.
2. **O DL 177/2026 desloca o mercado do DR para o BASE — e nós temos o
   BASE inteiro.** 28% dos anúncios (54% nas obras) podem passar a
   consulta prévia sem publicidade. Os alertas do DR encolhem; **o valor
   passa para quem sabe que entidades convidam quem, em que CPV** — e
   isso está nos 2 milhões de contratos (`docs/FUNCIONAL.md` §7.2,
   «contratos sem anúncio»).
3. **Quem explicar o regime novo no dia 1 ganha.** A 1/10 há dois regimes
   ao mesmo tempo (decisão de contratar antes ou depois), o preço base
   passa a facultativo, o concurso flexível tem 3 dias de pronúncia. O
   `docs/ccp.md` já sabe isto; nenhum concorrente português anunciou o
   que vai mostrar.
4. **O art. 1.º-C legitima a IA com supervisão humana e explicabilidade.**
   É a nossa postura — «mapear, não decidir», com a página — escrita na
   lei. Serve de argumento de venda e de defesa regulatória.
5. **A incumbente está em transição** (Simplifae desde Fevereiro, sem CEO
   desde Setembro), **o portal oficial está atrasado** e a **SpotGov tem
   12 pessoas para cinco frentes**. É uma janela de meses, não de anos.
6. **Concorrência fraca nos concursos**: 51% das consultas prévias com
   uma proposta, 38% dos contratos do TED com um concorrente, 23% de
   exclusões administrativas (declarado). Uma ferramenta que chega a
   tempo e lista o que falta tem valor mensurável — e o «o que as peças
   pedem» já é isso.
7. **O meio do mapa de preços está vazio** (§4.1): entre 50 € e 200 €
   não há em Portugal DR completo + leitura com fonte + escada,
   verificado. A TRINTA prova que o pacote vale 2 000 €.
8. **Os dados abertos continuam e melhoram**: o dump do BASE a 27/09,
   eForms desde Maio de 2025, o Regulamento europeu com «once-only» e
   espaços de dados. Mais dados estruturados, mais baratos de ler.
9. **A Tendios subiu de preço e a IA passou a créditos**; a GovGo parou.
   O chão barato com IA ficou livre.

### Ameaças (externas, com fonte)

1. **Menos anúncios na parte L a partir de 1/10/2026** — 28% em risco,
   54% nas obras (medido). A fonte principal encolhe; a promessa
   «nenhum concurso da sua área fica por ver» tem de passar a contar com
   o que **não** é anunciado.
2. **A Armilar já faz o que o site do Mira Gov promete** — resumo com
   fontes, chat, renovações com probabilidade, CPV automático — e o dono
   dela prometeu «AI-first» a três anos. Se a Simplifae resolver a
   sucessão e cortar preço, é um produto de 350 pessoas contra um de uma.
3. **A SpotGov vem para as PME** com 100 clientes, geração de propostas e
   um patrocínio ao evento dos juristas em Outubro. **A Adjudica promete o
   mesmo a 50 €** sem cara. Um espanhol (LICAI a 29 €, Gobierto a 150 €)
   pode atravessar a fronteira com o pacote inteiro.
4. **O Estado pode oferecer o alerta de graça**: o novo portal do IMPIC
   promete «notificação por parâmetros dinâmicos». Quando sair, o alerta
   deixa de ser produto — o que sobra é o que fazemos depois dele.
5. **Fontes que mudam de forma sem aviso**: o portal novo do BASE, a
   INCM, a Vortal ou a acinGov a fechar as peças a quem não tem sessão
   (91% dos anúncios entre as duas). O R4/R5 das armadilhas multiplicado
   por clientes que pagam.
6. **A lei vai mudar outra vez**: Regulamento europeu (negociações até
   Q4 2027, +2 anos), Tribunal de Contas, limiares europeus de dois em
   dois anos. Tudo o que cita um artigo tem prazo de validade; o
   `docs/ccp.md` é trabalho permanente.
7. **AI Act e AdC**: a transparência do art. 50 desde Agosto, coimas até
   7%, a AdC com ML sobre o BASE para apanhar propostas coordenadas. Risco
   baixo enquanto lemos; sobe no dia em que gerarmos texto que uma
   empresa entrega.
8. **Barreira de entrada baixa**: dezenas de «AI tender tools» europeus
   em 2026, feitos com os mesmos modelos que nós usamos. O que não é
   copiável em três meses é o acervo, o NIF, a régua e o CCP — não a
   leitura em si.

---

## 7. Diferenciadores e pontos de rotura

Separo as duas coisas. **Diferenciador** é o que já temos e os outros
não, ou não verificadamente. **Rotura** é o que ninguém faz e o mercado
vai precisar — onde uma ferramenta de uma pessoa pode mudar a conversa
em vez de correr atrás.

### 7.1 O que já nos distingue (para dizer no site e numa demo)

| # | Diferenciador | Prova | Quem mais o tem |
|---|---|---|---|
| D1 | **Cobertura total e verificável da parte L, de hora a hora** | «entra tudo»; link ao DR em cada anúncio; paridade 3/3 em Agosto | Tendios (ES-first); os outros falharam ou não se verifica |
| D2 | **Dez anos de anúncios + 2 M de contratos, por NIF, sem histórico a peso** | 210 811 / 2 009 640; `chave_entidade()` | Armilar (a 200 €); a Tendios cobra o histórico |
| D3 | **Leitura por família de contrato, com a página e a régua** | 5 famílias, 12 campos, 103/113 | Ninguém — a SpotGov diz «brevemente» |
| D4 | **A escada em CCP** — ranhuras, motivos, audiência prévia, o preço acima da base recusado | `docs/FUNCIONAL.md` §3.1 | Ninguém com o vocabulário da lei |
| D5 | **Nada da empresa passa pelo modelo; dados em Portugal** | decisão de princípio; cópias cifradas na UE | Tenderyou declara o mesmo (ES); os outros geram propostas |
| D6 | **Custo marginal ~0 → preço de PME para o pacote de 2 000 €** | leitura partilhada, reservas, fontes públicas | Só a Adjudica declara (sem prova) |
| D7 | **Consultas preliminares sem duplicar o DR** | `recolher_vortal()`, só o que a parte L não publica | Armilar e Tendios trazem-nas — misturadas |
| D8 | **Português de Portugal e a taxonomia do CCP** | — | GovGo, Alerta CP (sem IA) |

### 7.2 Os pontos de rotura — o que ninguém faz

**R1. O regime legal de cada concurso, na ficha.** A 1/10/2026 há dois
Códigos em vigor ao mesmo tempo, e o que decide é a **data da decisão
de contratar**, que o anúncio não traz — o Programa diz. O `docs/ccp.md`
já tem a regra; o dado (data de envio do anúncio, tipo, preço base ou
valor estimado) já está na base. Uma etiqueta «regime de 2017» / «regime
de 2026» com **o artigo certo dos prazos e da pronúncia** (3 dias no
flexível!) é uma coisa que nenhum dos treze produtos deste documento
mostra, e que em Outubro toda a gente vai precisar. **É o mais barato
dos cinco e o mais urgente**: tem data.

**R2. Publicar a régua.** Todos vendem «a IA lê as peças»: «Encaje 92%»,
«IC 80%», «125 h/semana». Ninguém publica **quantas passagens acerta, em
que documentos, e o que marca como «não consta»**. Nós temos 113
passagens, duas rondas, quatro perfis de juízes, e a leitura marcada
como rascunho. Publicar isso — a régua, a percentagem, os casos falhados
— vira a honestidade em produto e torna a comparação impossível para
quem não a tenha. **Pré-requisito: reler as 70 e julgar** (o ponto que
falta para a v1). A rotura é depois.

**R3. O mercado que não passa pelo DR: «quem convida quem».** Os
2 milhões de contratos incluem os ajustes directos e as consultas
prévias — 70% dos procedimentos, e a partir de 1/10 uma fatia maior. Por
entidade e CPV, o corpus diz **a quem cada entidade compra sem concurso**,
com que frequência, a que preço. Para uma PME, «entrar na lista dos 5
convidados da ULS X» passa a ser o jogo — e a lista de quem já lá está é
pública, só ninguém a mostra. A `docs/FUNCIONAL.md` §7.2 já o descreve
(«contratos sem anúncio»); a lei nova dá-lhe a razão de existir. É a
resposta à ameaça 1 **com o dado que só nós temos inteiro em disco**.

**R4. O custo de oportunidade, medido.** Os que caíram no perfil,
ficaram «por ver» e expiraram: quantos, de quem, de que valor. É o
número que vende a ferramenta ao gerente («deixámos passar 1,2 M€ no
trimestre») e nenhum produto o mostra — todos mostram o que
apanharam, nunca o que o cliente ignorou. Já está descrito no §7.1 do
funcional; falta o ecrã.

**R5. A antecipação das renovações, medida e não estimada.** A Armilar
dá uma probabilidade; a SpotGov um radar. Nós temos o dado para dizer
**«esta entidade republica este CPV em média N meses antes do fim do
contrato»** — cruzando o `fim_estimado` com a `data_pub` do anúncio
seguinte da mesma entidade — e mostrar a regra com os casos, em vez de
uma percentagem opaca. É o mesmo princípio da régua: mostrar a conta.

### 7.3 O que **não** é rotura, e continua a não se fazer

Para não voltar atrás por pressão de uma demo perdida (é a lista do
`BACKLOG.md` «Não fazer», confirmada por esta passagem):

- **Gerar e rever propostas por IA** — quatro concorrentes fazem-no;
  é precisamente o que o art. 50 do AI Act e a AdC vão apertar, e o que
  contradiz o D5. A TRINTA e a SpotGov que carreguem esse risco.
- **Chat livre sobre as peças** — custo imprevisível nas reservas; as
  leituras estruturadas por família cobrem o caso. Reavaliar com contrato
  de modelo, não antes.
- **Previsão do preço vencedor** — sem o número de licitadores não há
  fonte; o desconto histórico por entidade é a versão honesta.
- **Multi-país** — a Tendios mostra o custo.

---

## 8. O que isto pede — decisões do Afonso

Nada aqui se constrói sem palavra dele. Por ordem do que o calendário
impõe:

1. **A 1/10 é quinta-feira.** O R1 (regime na ficha) é a única coisa
   deste documento com data. Cabe numa sessão: uma etiqueta e o artigo.
   *Decisão: fazer antes ou depois de anunciar a leitura?*
2. **Um preço.** O mapa (§4.1) diz onde há espaço: acima dos alertas
   (25 €), abaixo da Armilar (200 €), com o pacote da TRINTA (2 000 €).
   O site promete «preço anunciado antes do fim da beta». *Decisão: a
   ordem de grandeza, e se há um degrau «só alertas + BASE» por baixo.*
3. **Testar a Adjudica** com uma conta e os três anúncios de Agosto —
   é uma hora, e diz se o «50 €» tem produto atrás.
4. **Reler as 70 e julgar** (o ponto da v1) — é o pré-requisito do R2 e
   do «anunciar a leitura».
5. **O R3 (quem convida quem)** — é a resposta estratégica ao DL 177 e
   vive no `/contratos` e nas fichas das entidades. *Decisão: entra no
   backlog com que prioridade?*
6. **Contrato de modelo** (Dev Tier ou equivalente) antes do primeiro
   cliente pago — a fraqueza 5 não se resolve com código.
7. **Repetir esta análise** de seis em seis meses, com paridade ao vivo
   — e a próxima deve testar TRINTA, Adjudica e Tender Radar com conta,
   como se fez em Agosto com as quatro.

---

## Fontes

Lidas a 29/09/2026 salvo indicação. **[V]** verificado na página ·
**[D]** declarado pelo próprio · **[M]** medido na nossa base.

**Armilar / Simplifae / Mercell** — armilar.biz/pt-pt/plans (mod.
18/05/2026) [V] · armilar.biz/pt-pt/armilar-ai/ (mod. 30/07/2026) [D] ·
tek.sapo.pt, «Vortal integra nova Simplifae…» (24/02/2026) [V] ·
supplychainmagazine.pt (27/02/2026) [V] · info.mercell.com/en/blog/
introducing-miguel-sobral-as-our-new-ceo/ (LinkedIn ≈16/09/2026) [V] ·
simplifae.com/about-us (mod. 19/02/2026) [V].

**GovGo** — govgo.pt, govgo.pt/about, vipa.pt/products/govgo, Google
Play «govgo concursos» [V].

**SpotGov** — spotgov.com [V] · expresso.pt, «Augusta Labs angaria mais
de 5 milhões» (2/06/2026) [V] · business-it.pt, entrevista (1/07/2026)
[D] · jornaleconomico.sapo.pt (6/07/2026) [D] · portugalstartupnews.com
(9/07/2026) [D] · eco.sapo.pt, Public Law Summit (7/08/2026) [V] ·
pmemagazine.sapo.pt (11/08/2026) [D] · linkedin.com/company/spotgov
(excerto) [V].

**Tendios** — tendios.com/bidders/pricing e /bidders (JSON-LD e estado
Nuxt) [V] · tendios.com/about-us [V] · blog «contratacion-publica-
portugal-guia-completa-del-ccp» (21/04/2026) [V] · okdiario.com e
computing.es, «Tendios Local» (18/09/2026) [V] · comparasoft.es
(21/09/2026) [V].

**Os outros** — trinta.ai (/pricing, /product/pipeline,
/product/case-files, /government-tenders/portugal,
/plataformas-de-concursos, /customers/ultra-controlo) [D] ·
adjudica.biz [D] · vencer.ai (404) [V] · alertaconcursospublicos.pt/precos
(página de 30/05/2024) [V] · helpdeskpublico.pt/alerta-concursos-publicos
[V] · anogov.com (packs e alertas) [V] · compraspt.com (+Concursos) [V] ·
acingov.pt, condições dos serviços avançados (PDF de 26/01/2026) [V] ·
tenderradar.io/pricing [V] · contratos.gobierto.es/empresas/planes [V] ·
licai.es [V] · tenderyou.com [V] · licitaryganaria.es [V] ·
impic.pt, plataformas licenciadas [V] · dinheirovivo.dn.pt, SaphetyGov →
Vortal (16/04/2020) [V].

**Oficiais** — diariodarepublica.pt/dr/geral/notificacoes/email [V] ·
base.gov.pt/Base4/pt/noticias/2026/ [V] · eco.sapo.pt, novo portal
(10/02/2025) [V] · apdc.pt, novo portal com IA (4/02/2025) [V] ·
ted.europa.eu/en/help/ted-account [V] · dados.gov.pt, dataset BASE
(act. 27/09/2026) [V].

**Mercado e lei** — IMPIC, Relatório Anual da Contratação Pública 2025
(15/07/2026, PDF de 91 páginas) [V] · single-market-scoreboard.ec.europa.eu/
countries/portugal_en (dados 2024) [V] · diariodarepublica.pt, DL
177/2026 [V] · helpdeskpublico.pt/alteracoes-ccp-decreto-lei-177-2026
[V] · mlgts.pt, legal alert [V] · eco.sapo.pt (16/04 e 17/04/2026) [V] ·
observador.pt (25/06/2026) [V] · transparencia.pt, comunicado (site com
erro 500; citado por excerto) [D] · publico.pt, Tribunal de Contas
(9/04/2026) [V] · cuatrecasas.com e legal500.com, proposta de
Regulamento COM(2026) 590 (9/09/2026) [V] · data.consilium.europa.eu,
ST-12969-2026 (10/09/2026) [V] · digital.gov.pt, AI Act [V] ·
gibsondunn.com e cloudsecurityalliance.org, Digital Omnibus (07/2026)
[V] · eco.sapo.pt, AdC e IA no BASE (26/12/2025) [V] ·
stotles.com/resource/blog, Series A (05/2025) [V] · tracxn.com, Tendium
(03/2026) [D].

**Medido na nossa base** (só leitura, 29/09/2026) — 29 285 anúncios de
procedimento de 2025 sem republicações nem Vortal; 28 839 com o tipo de
contrato na secção 6; a banda do DL 177 por família: bens 2 274 de
12 316, serviços 1 830 de 9 278, obras 3 936 de 7 245 [M].

---

## Adenda, à noite do mesmo dia — a Adjudica, medida

Decisão dele à noite: «testa a adjudica». Feito **sem criar conta**, às
23h de 29/09/2026. Corrige o que está acima: onde o §2.1 e a matriz
dizem «declarado» e «sem empresa visível», leia-se isto.

**É um produto a sério, em lançamento silencioso.** A API
(`api.adjudica.biz`, documentação aberta) tem **317 rotas**: radar,
dossiês de propostas, fundos europeus e candidaturas, consórcios,
facturação por Stripe com créditos e planos, ingestão com «políticas de
scraping» e níveis de modelo por fase, geração de posts de marketing.
Login por Keycloak; base de dados a responder; sete dias de uptime. Há
um `people.adjudica.biz` gratuito (despesa pública) e um observatório
por sector com dados do BASE.

**Quem está por trás: ninguém encontrável.** Domínio registado a
**11/07/2026** (Namecheap, registante oculto); sem NIF, morada, termos,
privacidade, LinkedIn, imprensa, Product Hunt. A única captura antiga do
domínio (2010) é de uma consultora de compras com o mesmo nome. Preço:
«grátis para começar, planos a partir de 50 €», sem página de preços.

**Cobertura, medida contra a nossa base** — a lista pública deles, sem
conta, 960 concursos únicos (847 do DR + 113 do TED; a paginação repete
e não deixa ver os 1 486 que anunciam):

| | |
|---|---|
| Refs do DR que existem na nossa base, com a mesma `data_pub` | **847 de 847** |
| Atraso | a ref mais alta deles: **24059/2026**; a nossa às 23h: **24148** — 102 anúncios de hoje e 74 de ontem ainda não lá estão. Consistente com ingerir pelo BASE, que republica o DR com atraso |
| Os nossos três de hoje acima de 100 k€ (24074, 24135, 24114) | **ausentes** |
| Fonte declarada | «Portal BASE / IMPIC» — mas o número que expõem é o da parte L, e as peças apontam para as mesmas plataformas que nós |

**Erros de dados nos cinco da página inicial:** dois prazos
**antecipados** (Almodôvar 24090/2026: eles 29/09, o DR diz **06/10**;
23414/2026: 30/09 contra 02/10 — quem confiar neles julga ter uma
semana a menos), duas entidades trocadas (a FCUP e a UP aparecem como
«Faculdade de Medicina»), e o preço da GNR (22093/2026) é o do lote 1
em vez do total. Em 8 dos 847 o prazo deles é mais cedo do que o do DR.

**O que muda no que está escrito acima:**

1. **É o concorrente directo** — mesmo segmento, mesmo pacote, mais
   fundos e consórcios — com dois meses e meio de vida.
2. **Onde ganhamos, com prova**: a frescura (hora a hora contra um dia)
   e **os dados certos** — o prazo antecipado é o erro que faz perder
   concursos. É um argumento de venda mensurável, e repete o padrão da
   Tendios em Agosto: quem ingere de segunda mão parte a identidade e as
   datas.
3. **Aperta o preço** (§8, decisão 2): com eles a «desde 50 €», a
   diferença tem de estar à vista — frescura, prazos do DR, leitura por
   família, escada em CCP, uma empresa com cara e termos.
4. **Falta ver a leitura das peças e o dossiê**, que é onde dizem
   «citamos a página». Só com conta.

A pesquisa inversa dos três anúncios de Agosto não se fez: já tinham
o prazo expirado e a lista pública só mostra abertos; a pesquisa por
texto exige sessão.
