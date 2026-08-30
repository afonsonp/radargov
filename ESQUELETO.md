# Esqueleto de informação do Radar — 30 de agosto de 2026

Proposta de estrutura de informação e navegação, a partir da
`AUDITORIA.md` (30/08) corrigida pelo `SANEAMENTO.md` (30/08, que
prevalece onde divergem), do `ESTADO.md` e do `BACKLOG.md`. Sem
código, sem decisões visuais: o desenho visual é fase seguinte e
parte deste documento.

## Resumo executivo

Sim, isto resolve o sentimento de aplicação espalhada — porque o
espalhado é sobretudo **hierarquia, âmbito e vocabulário**, não falta
nem excesso de funcionalidade: das 35 rotas, 31 mantêm-se tal como
estão, 3 mudam de lugar na navegação e 1 funde-se (pendente de escolha
do Afonso). O que muda mais: (1) a entrada deixa de misturar o dia com
dois anos de arquivo — a Triagem mostra o decidível e o acervo passa a
uma Pesquisa própria; (2) a navegação passa de oito entradas planas a
**cinco intenções** ordenadas pelo uso real (Triagem, Em curso,
Pesquisa, Mercado, Alertas), com os Indicadores a entrar pela zona de
estado; (3) quadro e calendário declaram-se como duas vistas da mesma
população; (4) um vocabulário único (anúncio, peças, leitura, triagem)
acaba com os três sentidos de "documentos" e os dois de "estado".
Fica por resolver mesmo depois disto: o Fluxo B continua dependente da
decisão E2 (canal de e-mail), a dívida do HTML por concatenação
paga-se no andamento 3 e não aqui, os riscos R1 (token) e R11 (volume)
continuam vivos com as mitigações actuais, e quatro fusões de vistas
irmãs ficam apresentadas para o Afonso escolher, não decididas.

---

## 1. Princípios

**P1 — O que pede decisão hoje nunca partilha ecrã com o arquivo.**
Derivado da aba "Por ver" a mostrar 61 981 itens porque os dois anos de
histórico sem detalhe vivem no mesmo balde da triagem do dia
(auditoria §4, Fluxo A, passo 3). Triagem e acervo são intenções
diferentes e passam a superfícies diferentes.

**P2 — Uma população de dados tem um lugar; perguntas diferentes são
vistas declaradas desse lugar, não páginas irmãs decalcadas.**
Derivado de: quadro e calendário são ambos "os interessa" (auditoria
§1.8); renovações são "contratos vistos pelo fim" (§1.8); e o padrão
"defeito corrigido numa vista, vivo na vista irmã" é o principal
gerador de bugs do projecto (auditoria §3.2, citando a 2.ª vistoria do
ESTADO).

**P3 — Há um só motor de filtros, e o filtro é contexto que viaja:
nunca se perde ao mudar de página e nunca se aplica a meio em
silêncio.** Derivado de FR-15/FR-35 (auditoria §6.1), da regra "nunca
escrevas um segundo motor de filtros" (CLAUDE.md; os avisos usam a
`condicoes()` da lista) e do chip "parcial" com os campos de fora
declarados (ESTADO, «Um filtro só»).

**P4 — Todo o número mostrado abre exactamente a lista que o
confirma.** Derivado de FR-33 e da vistoria de 29/08 («o número e o
destino do mesmo botão discordavam», ESTADO). Já é regra da casa nos
indicadores; a consolidação estende-a a qualquer contador da
navegação.

**P5 — O estado do sistema tem três alcances: o que bloqueia o radar
vê-se sem procurar; a saúde completa está a um clique; o diagnóstico
tem data e não grita.** Derivado do saneamento C1/C2 (marcas com data;
a distinção entre diagnóstico e accionável-agora ficou lá feita) e da
auditoria §3.3 (diagnóstico espalhado e invisível — já parcialmente
corrigido).

**P6 — Os 4-5 estados de cada item não são excepção a esconder, são o
conteúdo a desenhar.** Derivado de: `docs_estado` com 5 estados,
`texto_estado` com 5, `foi_lido` a distinguir "lido e não consta" de
"ainda não lido", corpus "interrompida" explicada (auditoria
§1.4–1.7, §2.3) — e de ser aí que a aplicação se sente inacabada
(enunciado). Cada página abaixo declara vazio / a carregar / erro /
parcial.

---

## 2. Navegação principal

Cinco itens de primeiro nível, por frequência real de uso. Cada um é
uma intenção, não uma tabela.

| # | Nome | A pessoa vem cá… | Frequência | Nasce do fluxo |
|---|------|------------------|------------|----------------|
| 1 | **Triagem** | decidir o que entrou: interessa, descarta, deixa para ver — só o decidível (P1) | diária (2×, após as recolhas das 09h/17h) | A |
| 2 | **Em curso** | trabalhar o que já disse "interessa": fases, etiquetas, prazos no tempo | diária | A (o desaguar do interessa) e C |
| 3 | **Pesquisa** | procurar no acervo completo (66 081, dois anos), filtrar, exportar | semanal | A (arquivo) e D |
| 4 | **Mercado** | perguntar ao corpus: quem compra, quem ganha, por quanto, o que vai acabar | semanal | C e D |
| 5 | **Alertas** | afinar o que o radar vigia sozinho: filtros, alertas, seguidas, resumo | ocasional | B |

**O que fica fora do primeiro nível, e onde passa a viver:**

- **Indicadores e saúde do sistema** — fora da navegação; entram pela
  **zona de estado da barra lateral** (o ponto verde/vermelho da
  última verificação passa a ligação para `/indicadores`). Ver §4.
  Fundamento: é consulta ocasional-a-rara, e a barra já é a superfície
  de estado permanente (auditoria §1.1, painel).
- **Definições** — continuam distribuídas *por decisão já tomada*, não
  por acidente: e-mail e janela do "urgente" em Alertas (ESTADO, «O
  e-mail configura-se no ecrã»; B13), identidade no cabeçalho
  (`/sou`), afinação das leituras e horas no `config.json` (ESTADO,
  B08; a conta que envia fica fora do ecrã de propósito). Não se cria
  página "Definições": seria uma entidade técnica, não uma intenção.
- **Gestão do corpus** — na barra do topo de Mercado·Contratos
  (contagens, anos, idade, botão Actualizar — já existe, auditoria
  §1.7) e na linha de idade dos Indicadores. Nunca item de navegação.
- **Exportações (Fluxo D)** — acções dentro das listas (Pesquisa,
  Contratos), com o número de linhas anunciado (FR-34/ESTADO). Nunca
  item de navegação.
- **Fluxo E (token expirado)** — não nasce em item nenhum: vive na
  zona de estado como aviso de sistema (R1), com a recaptura manual
  documentada no LEIA-ME §3. É operação, não navegação.

---

## 3. Inventário de páginas

### 3.0 Elementos transversais (não são páginas)

- **Barra lateral / cabeçalho**: navegação, migalhas
  (`migalhas_de`), contagem do acervo, identidade (`/sou`, POST),
  zona de estado (§4). As migalhas continuam a partir do separador em
  que a página vive — os separadores são irmãos (CLAUDE.md).
- **Sistema de filtros**: caixa de campos por vista
  (`CAMPOS_POR_VISTA`), árvore de CPV (uma só, contagens por fonte via
  `/cpv.json?de=`), faixa do filtro activo, filtros guardados
  (`/filtros/guardar`), chip "parcial" com os campos de fora ditos por
  escrito. Serve Triagem, Pesquisa, Mercado e ficha de entidade com o
  mesmo motor (P3). Rotas que vivem aqui: `/cpv.json`,
  `/filtros/guardar`.

### 3.1 Triagem — `/`

- **Propósito:** decidir o que entrou e é decidível — o Fluxo A sem o
  arquivo no caminho (P1).
- **Quem chega, vindo de onde:** o Afonso, ao abrir a aplicação (é a
  página inicial); da zona de estado após uma verificação; das
  ligações do resumo diário (dependência E3 para fora do PC).
- **Informação primária:** a lista de anúncios do âmbito por omissão
  — por ver, dentro da janela de decisão (a janela dos 60 dias de
  `detalhe_dias` e/ou prazo aberto; a escolha exacta é a pergunta
  11.2). Ordem: mais recentes primeiro. Na ordem dos poucos milhares,
  não 61 981 (a janela de 60 dias continha ~4 400 publicações quando
  foi medida — ESTADO, «Quando é que o detalhe é lido»; número actual
  não determinável pelos documentos).
- **Informação secundária:** abas de triagem (por ver / interessa /
  descartados / todos) contando **dentro do âmbito e do filtro**
  (regra existente — auditoria §1.8, contadores); etiqueta de
  plataforma (assinalando de qual se trazem as peças
  automaticamente — comportamento existente); dias até ao prazo.
- **Sai daqui:** o arquivo — os ~60 mil sem detalhe e fora da janela —
  para a Pesquisa (P1). A contagem assustadora sai com ele. Uma
  ligação "ver no acervo completo" leva o filtro em uso (P3).
- **Acções:** interessa [primária], descartar [primária], voltar a
  por ver [secundária], Verificar agora [secundária], guardar filtro
  [secundária], exportar CSV do filtro [secundária].
- **Estados:**
  - *Vazio:* "não entrou nada decidível" — ao fim-de-semana diz
    "a parte L não publica" (regra existente, ESTADO 2.ª vistoria);
    oferece a Pesquisa.
  - *A carregar:* verificação em curso — o passo na zona de estado e a
    página a recarregar-se sozinha (mecanismo existente, auditoria
    §1.1); a lista existente continua visível.
  - *Erro:* captura expirada / última verificação falhou — o aviso é
    da zona de estado (aviso de sistema, R1), a lista mostra o que há;
    nunca lista vazia sem explicação.
  - *Parcial:* anúncios do âmbito ainda sem detalhe lido dizem-no na
    linha ("ainda sem detalhe"); um filtro por CPV não os apanha e a
    página di-lo (facto: o CPV só existe após detalhe — ESTADO).
- **Saídas:** ficha do anúncio; Pesquisa com o mesmo filtro; Em curso
  (após marcar interessa); a plataforma externa (etiqueta cinzenta).
- **Funcionalidades/rotas:** §1.1 (recolha: botão e aviso), §1.2
  (transparente), parte de §1.8; rotas `/`, `/verificar`,
  `/estado/<ref>/<novo>`, `/csv` (partilhada com a Pesquisa).

### 3.2 Pesquisa — `/anuncios` (nova rota; a função é a lista actual)

- **Propósito:** o acervo completo de anúncios, para procurar,
  filtrar e exportar — a memória de dois anos, sem prazo de decisão.
- **Quem chega, vindo de onde:** da Triagem ("ver no acervo"); da
  navegação; de um filtro guardado; da ficha ("outros anúncios deste
  CPV", §5).
- **Informação primária:** a lista paginada (20/página,
  `POR_PAGINA_LISTA`) sobre os 66 081, com o conjunto completo de
  filtros: q, exclusões, entidade, CPV+árvore, op E/OU, plataforma
  (com os baldes `(nenhuma)`/`(por ler)` distintos — auditoria §1.8),
  prazo, datas, estado.
- **Informação secundária:** contagem "a mostrar X dos Y que
  correspondem · Z na base" (existente); filtros guardados.
- **Sai daqui:** nada — é página nova que recebe o que sai da Triagem.
- **Acções:** os mesmos interessa/descartar/repor [secundárias aqui —
  a decisão em massa é da Triagem], guardar filtro [primária],
  exportar CSV [primária].
- **Estados:**
  - *Vazio:* "nada corresponde ao filtro" — com o CPV sem
    correspondência a dar vazio declarado, nunca tudo (regra `1=0`
    existente, ESTADO); datas inválidas avisadas (`avisos_de_datas`).
  - *A carregar:* não determinável pelos documentos que precise de
    estado próprio (consultas <200 ms medidas, ESTADO); assume-se
    resposta imediata e declara-se que não se desenha estado próprio.
  - *Erro:* filtro parcial vindo de outra vista — chip tracejado com
    os campos de fora por escrito (existente, FR-15); não há erro de
    rede possível (é tudo local).
  - *Parcial:* 91,7% da base sem detalhe lido — a página declara que
    filtros por CPV/prazo/plataforma só vêem quem tem detalhe
    (auditoria §1.2: 5 493 de 66 081).
- **Saídas:** ficha do anúncio; Triagem (voltar ao âmbito de decisão);
  CSV.
- **Funcionalidades/rotas:** §1.2, parte de §1.8, Fluxo D dos
  anúncios; rotas `/anuncios` (nova), `/csv`, `/estado/<ref>/<novo>`,
  `/filtros/guardar`.

### 3.3 Ficha do anúncio — `/anuncio/<ref>` (mantém-se; Fluxo C, o mais bem servido — auditoria §4-C)

- **Propósito:** tudo o que se sabe de um concurso num sítio só, para
  decidir se se concorre.
- **Quem chega, vindo de onde:** Triagem, Pesquisa, Em curso
  (quadro/calendário), homólogos de outra ficha, resumo diário.
- **Informação primária:** o essencial (12 campos, com os quatro
  lidos das peças pelo modelo e as fontes com páginas); as peças do
  procedimento com os seus estados; prazo com contagem.
- **Informação secundária:** anúncio completo (28 secções, atrás de um
  comando); histórico da ficha (quem fez o quê, alterações do DR,
  rectificações ligadas); homólogos (B02); histórico de adjudicações
  da entidade no CPV + referência de preço + desconto (B04);
  responsável.
- **Sai daqui:** nada — a auditoria dá este fluxo como o mais bem
  servido; mantém-se e segue (regra do enunciado). Densidade é
  problema de layout, não de IA (fase seguinte).
- **Acções:** trazer/actualizar peças [primária], ler peças pelo
  modelo [primária], interessa/descartar [primária], atribuir
  responsável [secundária], abrir plataforma [secundária], abrir PDF
  oficial [secundária], voltar à lista com contexto [secundária].
- **Estados:** (o catálogo mais rico da aplicação — P6)
  - *Vazio:* anúncio sem detalhe lido → lê na hora (~0,6 s, mecanismo
    existente); 404 com página completa da aplicação (existente).
  - *A carregar:* "a trazer as peças…" com auto-recarga até estado
    terminal; leitura pelo modelo na fila com o pé em que vai
    (existente, auditoria §1.4/§1.6).
  - *Erro:* peças `falhou` com o motivo e botão de repetir/abrir
    plataforma; extracção `erro:` retenta-se sozinha na próxima
    passagem (saneamento A1 — **não** desenhar botão de retentativa,
    já não é preciso); `scan` diz "digitalização, fica para OCR
    futuro"; cadeia de modelo esgotada diz o dia por perdido só quando
    toda a cadeia esgota (existente).
  - *Parcial:* `docs_estado='parcial'` com os ficheiros >60 MB
    nomeados; leitura parcial preserva campos anteriores e o
    `foi_lido` distingue "lido e não consta" de "ainda não lido"
    (existente — os quatro estados por campo do essencial mantêm-se).
- **Saídas:** ficha da entidade; ficha de anúncio homólogo; Pesquisa
  por CPV (§5, novo); plataforma externa; PDF oficial.
- **Funcionalidades/rotas:** §1.2 (leitura na hora), §1.3 (histórico
  de alterações e rectificações — a superfície de leitura é esta),
  §1.4, §1.5, §1.6, B02/B04; rotas `/anuncio/<ref>`,
  `/documento/<ref>/<nome>`, `/documentos/<ref>`, `/analisar/<ref>`,
  `/responsavel/<ref>`, `/estado/<ref>/<novo>`.

### 3.4 Em curso · Quadro — `/quadro` (muda de lugar na navegação, não de caminho)

- **Propósito:** conduzir os "interessa" pelas fases até à proposta —
  a vista de trabalho do Em curso.
- **Quem chega, vindo de onde:** navegação (item Em curso, vista por
  omissão — pergunta 11.4); da Triagem após marcar interessa.
- **Informação primária:** colunas = fases editáveis; cartões com
  prazo contado; soma do preço base por coluna com o "sobre quantos"
  declarado (B11).
- **Informação secundária:** etiquetas; contagens por coluna (ao vivo
  após arrastar — regra existente).
- **Sai daqui:** nada.
- **Acções:** arrastar cartão [primária], nova fase / renomear /
  apagar (com migração de cartões) [secundárias], etiquetar
  [secundária], Verificar agora [secundária, pergunta 11.8], tirar do
  quadro = "voltar a por ver", com confirmação [secundária].
- **Estados:**
  - *Vazio:* sem interessa nenhum — explica que o quadro se enche a
    partir da Triagem, com ligação para lá.
  - *A carregar:* o arrastar é o único fetch (existente); falha de
    gravação recarrega em vez de mentir (regra existente, ESTADO).
  - *Erro:* fase inexistente devolve 404 e o ecrã repõe-se
    (existente).
  - *Parcial:* cartões sem preço base não entram na soma da coluna e a
    soma di-lo (B11); cartões sem prazo não têm contagem.
- **Saídas:** ficha do anúncio; vista Calendário do mesmo conjunto
  (§5).
- **Funcionalidades/rotas:** §1.8 (quadro), B11; rotas `/quadro`,
  `/quadro/mover`, `/quadro/fase/nova`, `/quadro/fase/<id>/renomear`,
  `/quadro/fase/<id>/apagar`, `/quadro/etiqueta/<ref>/nova`,
  `/quadro/etiqueta/<ref>/tirar/<id>`.

### 3.5 Em curso · Calendário — `/calendario` (muda de lugar na navegação, não de caminho)

- **Propósito:** os mesmos "interessa" postos no tempo — 45 dias de
  prazos, a segunda vista do Em curso (P2).
- **Quem chega, vindo de onde:** o item Em curso, alternando com o
  quadro.
- **Informação primária:** grade de 45 dias, uma linha por anúncio com
  prazo, pílula na coluna do dia com a fase actual.
- **Informação secundária:** fins-de-semana e fronteiras de mês
  marcados; nota com quem ficou fora da janela.
- **Sai daqui:** nada.
- **Acções:** abrir a ficha pela pílula [primária], Verificar agora
  [secundária, pergunta 11.8]. Só leitura no resto (deliberado).
- **Estados:**
  - *Vazio:* sem interessa com prazo na janela — di-lo e aponta o
    quadro e a nota dos fora-da-janela.
  - *A carregar:* não aplicável (leitura local imediata); declara-se
    que não se desenha estado próprio.
  - *Erro:* não aplicável (sem escrita); herda os avisos da zona de
    estado.
  - *Parcial:* prazos passados ou a mais de 45 dias fora da grade,
    contados na nota (existente — a nota é o estado parcial declarado).
- **Saídas:** ficha do anúncio; vista Quadro.
- **Funcionalidades/rotas:** §1.8 (calendário); rota `/calendario`.

### 3.6 Mercado · Contratos — `/contratos` (mantém-se)

- **Propósito:** perguntar ao corpus quem comprou o quê, a quem e por
  quanto — a pergunta vem primeiro, por decisão e por custo (48 s sem
  filtro antes da regra; auditoria §1.8, ESTADO).
- **Quem chega, vindo de onde:** navegação (Mercado); ficha de
  entidade (atalhos com filtro); ficha do anúncio (histórico/homólogos
  apontam para cá); Alertas (ligações do filtro).
- **Informação primária:** com filtro: a tabela (celebração, fim
  estimado, objecto, quem, valor) e a linha de contagem com o valor do
  mercado filtrado. Sem filtro: o convite a perguntar — **que é o
  estado vazio de propósito, não uma falta** (P6; ver Estados).
- **Informação secundária:** os 7 gráficos sob o filtro, pedidos só ao
  abrir (`/contratos/resumo`); a barra do corpus (contagens, anos,
  idade, botão Actualizar).
- **Sai daqui:** nada de conteúdo; a duplicação com Renovações é a
  decisão 6.1.
- **Acções:** filtrar/perguntar [primária], abrir os gráficos
  [secundária], exportar CSV (exige filtro, tecto 50 000, linhas
  anunciadas) [secundária], Actualizar contratos [secundária], guardar
  filtro [secundária].
- **Estados:**
  - *Vazio:* sem filtro = o convite (deliberado); com filtro sem
    resultados = "nada corresponde", com avisos de datas.
  - *A carregar:* actualização do corpus em thread, estado na base,
    página a recarregar-se; "interrompida" explicada quando o trinco
    está livre e a marca diz "a correr" (existente, auditoria §1.7).
  - *Erro:* corpus por importar — a barra diz como o trazer; nunca
    finge que não há dados (regra existente).
  - *Parcial:* entidades sem NIF marcadas "sem NIF" (chaves `n:`);
    dump semanal — a barra diz a idade e assinala-a passados 14 dias
    (regra existente); o trimestre corrente declarado como "a
    decorrer" nos gráficos (existente).
- **Saídas:** ficha de entidade (nomes são ligações); Renovações com o
  mesmo filtro (§5); ficha do anúncio quando `n_anuncio` existe na
  base (§5, novo); CSV.
- **Funcionalidades/rotas:** §1.7 (corpus), Fluxo D dos contratos;
  rotas `/contratos`, `/contratos/resumo`, `/contratos/csv`,
  `/contratos/actualizar`.

### 3.7 Mercado · Renovações — `/renovacoes` (pendente da decisão 6.1)

- **Propósito:** os contratos vistos pelo fim estimado — "o que vai
  acabar no meu mercado, e quem o tem" (B03).
- **Quem chega, vindo de onde:** Mercado; ficha de entidade ("o que
  desta entidade está a acabar", §5 novo).
- **Informação primária:** com filtro: contratos com fim na janela
  (3/6/12/24 meses, whitelist), do mais próximo ao mais distante, com
  detentor e valor. Sem filtro: o mesmo convite dos contratos.
- **Informação secundária:** a declaração de que o fim é **estimado**
  e que prorrogações não constam do dump (existente e obrigatória).
- **Sai daqui (se ficar página):** o formulário/faixas decalcados dos
  contratos passam a bloco partilhado (decisão 6.3/6.4); os campos
  `de`/`ate` continuam fora desta vista (decisão registada — dois
  eixos de tempo confundiam, ESTADO B03).
- **Acções:** filtrar [primária], mudar a janela [primária], guardar
  filtro [secundária]. Exportação: não determinável pelos documentos
  se existe CSV próprio das renovações; não se promete aqui.
- **Estados:**
  - *Vazio:* sem filtro = convite (81 827 contratos a acabar em 6
    meses não respondem a nada — B03); com filtro = "nada acaba nesta
    janela".
  - *A carregar:* herda o da actualização do corpus (barra).
  - *Erro:* corpus por importar — como nos contratos.
  - *Parcial:* contratos sem prazo de execução não têm fim estimado e
    ficam fora — a página deve dizê-lo (a auditoria não regista se o
    diz hoje: não determinável; fica como requisito).
- **Saídas:** ficha de entidade; Contratos com o mesmo filtro.
- **Funcionalidades/rotas:** §1.8 (renovações), B03; rota
  `/renovacoes`.

### 3.8 Ficha da entidade — `/entidade/<chave>` (mantém-se)

- **Propósito:** uma entidade nos dois papéis — o que compra e o que
  ganha — com filtro próprio (Fluxo C; mantém-se, funciona).
- **Quem chega, vindo de onde:** ficha do anúncio (histórico/NIPC),
  gráficos e tabelas dos contratos, Alertas (seguidas).
- **Informação primária:** identificação (NIF, quantos nomes usa), os
  dois KPI (compra / ganha), gráficos por papel, contratos recentes.
- **Informação secundária:** filtro próprio somado à entidade em todos
  os blocos; períodos rápidos; botão seguir.
- **Sai daqui:** nada.
- **Acções:** filtrar dentro da ficha [primária], seguir / deixar de
  seguir [secundária], saltar para Contratos com o filtro da ficha
  [secundária].
- **Estados:**
  - *Vazio:* filtro que não apanha nada di-lo e oferece "ver tudo"
    (existente); entidade sem contratos no corpus explica porquê.
  - *A carregar:* não aplicável além do corpus (herda a barra).
  - *Erro:* corpus por importar — diz como trazer (existente).
  - *Parcial:* entidade `n:` (sem NIF) marcada, **sem botão de
    seguir** — não haveria aviso nenhum e oferecê-lo era prometer em
    falso (decisão B10, mantém-se).
- **Saídas:** Contratos filtrados por `entid`/`vencid` com faixa;
  Renovações da entidade (§5, novo); fichas de anúncios recentes dela
  — não determinável pelos documentos se essa ligação existe hoje;
  proposta em §5.
- **Funcionalidades/rotas:** §1.8 (ficha de entidade), B10; rotas
  `/entidade/<chave>`, `/entidade/<chave>/seguir`.

### 3.9 Alertas — `/alertas` (mantém-se)

- **Propósito:** o centro do que o radar vigia sozinho: filtros
  guardados, alertas, entidades seguidas, e-mail e janela do urgente.
- **Quem chega, vindo de onde:** navegação; da faixa de filtros de
  qualquer lista ("guardar filtro" aponta a gestão para cá).
- **Informação primária:** a lista de filtros com o interruptor de
  alerta, a taxa de acerto (B06) e as ligações para as listas que cada
  filtro abre; as entidades seguidas.
- **Informação secundária:** configuração do destino e hora do resumo
  (o ecrã mostra o que está posto e o que falta — comportamento
  existente; a conta que envia fica fora do ecrã, por decisão); janela
  do urgente (B13); histórico de avisos.
- **Sai daqui:** nada — é o centro de gestão por decisão tomada
  (ESTADO, «O separador dos alertas é onde se gerem os filtros»).
- **Acções:** criar filtro (com árvore) [primária], ligar/desligar
  alerta [primária], apagar filtro [secundária, confirmado], enviar
  resumo já [secundária, dependente E2], gravar destino/hora
  [secundária, dependente E2], mudar janela do urgente [secundária].
- **Estados:**
  - *Vazio:* sem filtros guardados — explica que se criam aqui ou de
    qualquer lista.
  - *A carregar:* não aplicável; declara-se sem estado próprio.
  - *Erro:* envio falhado distingue "por configurar" de "falha a
    sério" e a autenticação recusada tem mensagem própria (existente,
    §1.9); validação da criação devolve o formulário preenchido
    (existente).
  - *Parcial:* alerta cujo filtro tem campos que os anúncios não
    entendem avisa "avisa só por…" (existente, FR-15/§1.9); acervo
    marcado ao ligar, para o primeiro resumo não trazer tudo.
- **Saídas:** listas de anúncios/contratos de cada filtro; fichas de
  entidades seguidas.
- **Funcionalidades/rotas:** §1.9, B06, B10 (gestão), B13; rotas
  `/alertas`, `/alertas/criar`, `/alertas/email`,
  `/alertas/<id>/trocar`, `/alertas/enviar`, `/alertas/urgente`,
  `/filtros/<id>/apagar`.

### 3.10 Indicadores — `/indicadores` (mantém-se; sai da navegação, entra pela zona de estado)

- **Propósito:** os números sobre o próprio radar e a saúde
  consolidada do sistema — a superfície que o saneamento C1/C2 já
  reforçou; não se inventa página nova (§4).
- **Quem chega, vindo de onde:** a zona de estado da barra lateral (o
  ponto passa a ligação); quem quer saber "isto está a funcionar?".
- **Informação primária:** KPI (base, novos hoje, interessa, sem
  detalhe), funil de 30 dias, fases; saúde: capturas, peças por
  plataforma com denominador declarado, base, corpus, cópia de
  segurança.
- **Informação secundária:** o bloco de diagnóstico — últimos erros
  com data (relógio, peças, leitura), como diagnóstico
  (saneamento C1).
- **Sai daqui:** nada; entra o acesso pela zona de estado.
- **Acções:** cada número com limiar abre exactamente a lista que o
  confirma [primária] (FR-33, P4). Sem outras acções — é leitura.
- **Estados:**
  - *Vazio:* base nova sem fases/anúncios — cada bloco di-lo ("ainda
    não há fases no quadro", existente).
  - *A carregar:* não aplicável; herda o "a verificar" da zona de
    estado.
  - *Erro:* é a página que os mostra: capturas em falta e cópia
    falhada como estado presente accionável; últimos erros como
    diagnóstico datado (P5) — na convenção de severidade que já
    existe (saneamento C1/C2).
  - *Parcial:* percentagens de plataformas com o denominador escrito
    (existente); entidades com/sem NIF em linhas separadas
    (existente); corpus com idade >14 dias assinalado (existente).
- **Saídas:** as listas confirmatórias; Mercado (bloco do corpus).
- **Funcionalidades/rotas:** §1.10 (estado da cópia), saúde de
  §1.1/§1.4/§1.6/§1.7, saneamento C1/C2; rota `/indicadores`.

### 3.11 Fica fora desta consolidação, com motivo

- **CLI de manutenção** (`--historico`, `--reler`, `--ler-pecas`,
  `--importar-cpv`, `--contratos <anos antigos>`,
  `--descartar-expirados`): sem ecrã **por decisão** — o botão "Reler
  detalhes" saiu do painel porque manutenção não é uso diário (ESTADO).
  Continuam documentados no LEIA-ME §12/CLAUDE.md.
- **Fluxo E (recaptura do token):** manual por natureza — não há API
  do DR (auditoria §2.4); o ecrã avisa (zona de estado) e o LEIA-ME §3
  ensina. O registo da frequência de expiração é a proposta E4,
  pendente no SANEAMENTO.md.
- **Releitura dos marcados e rectificações (§1.3):** correm dentro da
  verificação, sem superfície própria além do histórico da ficha e da
  secção "Alterados" do resumo — vigilância, não página (CLAUDE.md).
- **Cópia de segurança (§1.10):** automática; a sua superfície é a
  linha de saúde (saneamento C2), não uma página.
- **`amostras/`, `AVISOS.txt` em disco:** artefactos de diagnóstico e
  entrega, sem ecrã; o AVISOS.txt é a entrega de reserva do Fluxo B
  (ver §8, E2).

**Verificação de cobertura da secção 1 da auditoria:** 1.1 → Triagem +
zona de estado; 1.2 → Triagem/Pesquisa/Ficha; 1.3 → Ficha (leitura) +
resumo (entrega) + exclusões (motor); 1.4/1.5/1.6 → Ficha do anúncio;
1.7 → Mercado·Contratos + Indicadores; 1.8 → §3.1–3.10; 1.9 → Alertas
(+ Triagem no cenário sem e-mail, §8); 1.10 → exclusões com motivo +
linha de saúde da cópia. Zero órfãs.

---

## 4. Superfícies de estado e saúde

Hoje o estado vive em três sítios (barra lateral, Indicadores, ficha);
mantêm-se os três, mas com papéis declarados e sem duplicação — a
regra que já tirou o rodapé repetido (ESTADO, vistoria):

**Nível 1 — sem procurar (barra lateral, todas as páginas).** Só o que
bloqueia a promessa central ou está a acontecer agora: ponto
verde/vermelho da última verificação com a mensagem; "a verificar
agora" com o passo; o aviso de captura expirada (R1) e o de
tarefas do Windows em falta (R13). Nada mais entra aqui — um aviso
permanente deixa de ser aviso.

**Nível 2 — a um clique (Indicadores, via o ponto da barra).** A saúde
completa: capturas, peças por plataforma, base, corpus (idade, anos,
tamanho), cópia de segurança (ok/falhou — saneamento C2). A severidade
segue a regra existente: estado presente accionável distinto do
"quando der jeito" (corpus velho — auditoria §1.7/Indicadores).

**Nível 3 — diagnóstico (bloco próprio dos Indicadores).** Os últimos
erros com data (relógio, peças, leitura — saneamento C1), marcados
como diagnóstico porque a marca é sobrescrita e pode ser antiga; e,
quando existir, o histórico de erros proposto no BACKLOG (C3) — este
esqueleto **não** o assume, só lhe reserva o lugar.

**Estado do item ≠ estado do sistema (P6).** `docs_estado`,
`texto_estado`, `foi_lido`, "a trazer as peças" vivem na ficha do
anúncio; "interrompida" do corpus vive na barra do corpus em Mercado.
Nenhum estado de item sobe à barra lateral; nenhum estado de sistema
se repete nas fichas.

---

## 5. Navegação transversal

O Fluxo C mantém-se como está — a auditoria dá-o como o mais bem
servido. O contexto que viaja é sempre a query string canónica do
filtro (FR-15), a chave da entidade, o CPV ou o período; o que uma
vista não entende declara-se parcial, nunca cai em silêncio (P3).

**Atalhos que existem (mantêm-se):**

| De | Para | Contexto que viaja |
|----|------|--------------------|
| Ficha do anúncio | Ficha da entidade | chave (NIPC), CPV do anúncio |
| Ficha do anúncio | Ficha de homólogo | `n_anuncio` (B02) |
| Ficha da entidade | Contratos | `entid`/`vencid` + filtro da ficha |
| Indicadores | Listas confirmatórias | o filtro exacto do número (FR-33) |
| Alertas | Anúncios / Contratos do filtro | a consulta guardada |
| Lista → ficha → lista | (volta) | filtro, página e posição de scroll (FR-35) |
| Gráficos dos contratos | Ficha da entidade | chave |
| Quadro / Calendário | Ficha do anúncio | ref |

**Atalhos que deviam existir (propostos):**

| De | Para | Contexto que viaja | Fundamento |
|----|------|--------------------|------------|
| Triagem | Pesquisa | o filtro em uso, completo | P1: sair do âmbito sem perder a pergunta |
| Ficha do anúncio | Pesquisa por CPV | o(s) CPV do anúncio | "que mais há disto?" fecha o ciclo A→C |
| Contratos ⇄ Renovações (se separadas) | a vista irmã | o filtro, menos `de`/`ate` (declarado parcial) | mesma população, pergunta vizinha (P2) |
| Ficha da entidade | Renovações | `entid` + janela | "o que desta entidade está a acabar" é a pergunta comercial da ficha |
| Linha de contrato com `n_anuncio` na base | Ficha do anúncio | ref | o inverso do B02; só quando o ref existe (4 917 dos 5 391 comuns — ESTADO) |
| Quadro ⇄ Calendário | a mesma linha/cartão | ref | duas vistas do mesmo conjunto (P2) |

---

## 6. Duplicações e vistas irmãs

Apresentado para o Afonso escolher; nada aqui é definitivo.

### 6.1 `/contratos` vs `/renovacoes`

- **A — fundir:** os contratos ganham um eixo declarado "ver por:
  celebração | fim estimado"; no modo fim aparece a janela (3/6/12/24)
  e a nota do estimado, e `de`/`ate` desactivam-se com explicação.
  Uma página, um formulário, uma tabela.
- **B — manter:** páginas irmãs como hoje, com os blocos comuns
  partilhados (6.3/6.4).
- **Custo de A:** um ecrã bifacetado — o utilizador tem de saber
  sempre em que modo está; o argumento original contra ("dois eixos do
  tempo na mesma página confundiam", ESTADO B03) era sobre eixos
  simultâneos, mas um selector mal sinalizado recria a confusão.
- **Custo de B:** ~80% decalcado, "qualquer correcção numa tem de ser
  lembrada na outra" — o principal gerador de bugs do projecto
  (auditoria §3.2).
- **Recomendação: A** — o custo de B já está medido e pago duas vezes;
  o de A resolve-se com o modo dito por extenso no título da tabela.

### 6.2 `condicoes()` vs `condicoes_contratos()`

- **A — fundir** num motor único com esquema de campos por vista.
- **B — manter** as irmãs deliberadas (campos genuinamente diferentes:
  um anúncio não tem vencedor — auditoria §3.2 chama-lhes
  "deliberadamente irmãs", com testes).
- **Custo de A:** refactor de fundo fora do âmbito deste documento;
  risco de mexer no que os 424 testes seguram.
- **Custo de B:** `frag_texto`/`procura`/`exclui` e o bloco OU escritos
  duas vezes — um bug de escape corrige-se em dois sítios (§3.2).
- **Recomendação: B por agora** — é dívida de código, não de IA;
  reavaliar no andamento 3, junto da dívida do HTML.

### 6.3 Blocos de faixa "CPV activo" repetidos em 4 páginas

- **A — declarar bloco único partilhado** (a faixa do filtro activo é
  um só conceito em todas as páginas com filtro).
- **B — manter cópias.**
- **Custo de A:** trabalho do andamento 3 (é onde o HTML partilhado se
  extrai); **de B:** quatro sítios a divergir "com pequenas
  diferenças" (auditoria §3.2).
- **Recomendação: A**, no andamento 3 — é exactamente o tipo de bloco
  que a extracção do esqueleto comum paga sozinha.

### 6.4 Selectores de procedimento montados 3 vezes

Igual a 6.3: **A** (um só selector partilhado, no andamento 3) contra
**B** (três cópias, §3.2). **Recomendação: A**, pela mesma linha.

---

## 7. Vocabulário

Um conceito, um nome, em todo o lado. A coluna do código não muda
(fica como documentação da correspondência); muda o que o ecrã diz.

| Termo no código | No ecrã hoje | Proposto |
|---|---|---|
| `anuncios` | "Anúncios" / "concurso" à mistura | **anúncio** — o item publicado no DR; único nome do item em listas, fichas e contagens |
| — | "concurso" (textos, `concursos.csv`) | **concurso** só como linguagem de topo (Radar de Concursos); o CSV passa a `anuncios-<data>.csv` |
| `tipo_procedimento`, `n_anuncio` | "tipo de procedimento", "desconto por procedimento" | **procedimento** — o processo de contratação; usado em tipos e agregações, nunca como sinónimo de anúncio |
| `documentos` (tabela), `DOCS` | "Peças do procedimento" / "Trazer peças" / "Documentos guardados" | **peças** — os ficheiros trazidos; a linha dos Indicadores passa a "Peças guardadas" |
| `documentos_proposta` | "documentos que constituem a proposta" | **documentos da proposta** — conceito distinto (o que o concorrente entrega); mantém-se, e é o único uso de "documentos" no ecrã |
| `analise`, `analisar_pecas` | "Ler peças", "peças lidas pelo modelo" | **leitura (das peças)** — a acção e o resultado; "análise" não aparece no ecrã |
| `essencial_do_anuncio` | "Essencial" | **essencial** — mantém: a tabela dos 12 campos da ficha |
| `filtros_guardados` | "filtro", "filtros guardados" | **filtro** — o conjunto de campos; "guardado" quando tem nome |
| `alerta` | "alerta" | **alerta** — um filtro com a marca de avisar (FR-19); nunca "notificação" |
| `entidades`, `chave` | "Entidade que publica" / "Entidade que comprou" | **entidade** — pessoa colectiva identificada pelo NIF; os rótulos por papel mantêm-se |
| `adjudicatario`, `vencid` | "quem ganhou" | **quem ganhou** no ecrã; *adjudicatário* só em texto técnico/CSV |
| `estado` (anuncios.estado) | "por ver / interessa / descartados" | **triagem** — o rótulo do grupo e da coluna do CSV; os três valores mantêm-se |
| `estado` (tabela de marcas), `docs_estado`, `texto_estado` | invisível / vário | **estado** reserva-se para sistema e itens (peças, leitura) — nunca para a triagem |
| `novo` (chave interna) | "por ver" | **por ver** — mantém; a chave interna nunca aparece (o CSV já traduz) |
| `detalhe_lido` | "ainda sem detalhe lido" | **detalhe** — mantém |
| `fases` | "fase" | **fase** — coluna do quadro Em curso; mantém |
| `entidades_seguidas` | "Seguir esta entidade" | **seguida** — mantém |

(A confusão `por_pagina`/`POR_PAGINA` foi resolvida no saneamento D4 —
não é problema aberto.)

---

## 8. Dependências e pré-requisitos

- **E2 (canal de aviso, por decidir).** O Fluxo B está desenhado assim:
  os alertas reconhecem na verificação, o resumo entrega uma vez por
  dia por e-mail e sempre para `AVISOS.txt` (§1.9). **Tudo o que em
  §3.9 diz "dependente E2"** (destino, hora, enviar já) só ganha vida
  com a decisão do SANEAMENTO.md. **Se o Afonso decidir não ligar o
  e-mail de todo**, a estrutura muda num ponto: a entrega passa para
  dentro da aplicação — um bloco "novidades por ver" na Triagem,
  alimentado pelas filas que já existem (`alertas_vistos`,
  `alteracoes`, `seguidas_vistos` com `enviado_em` vazio — auditoria
  §2.6), em que "entregue" passa a significar "mostrado e confirmado
  no ecrã". É mudança de semântica da entrega e vai como pergunta 11.3;
  não usa dados que não existam.
- **E3 (links do resumo em localhost).** Nenhuma página deste
  esqueleto é desenhada para consulta fora do PC. O único artefacto
  que sai do PC é o e-mail do resumo — os links dele dependem da
  decisão E3 (SANEAMENTO.md) e este documento não a antecipa.
- **R1 (token) — vivo.** A zona de estado (nível 1 de §4) é a
  mitigação de ecrã; o Fluxo E continua manual e fora da navegação
  (§3.11). O registo da frequência é E4, pendente.
- **R11 (volume) — vivo.** As listas aguentam por paginação e índices;
  o ponto sensível é `/contratos/resumo`: **~7 s sem filtro** no
  corpus de 7 anos, a caminho de ~14 s se duplicar (auditoria §3.6).
  Consequência directa na entrada de Mercado·Contratos: o estado vazio
  é o convite a filtrar, os gráficos só se pedem **com filtro e ao
  abrir** — este esqueleto proíbe qualquer "painel de mercado" na
  entrada que dispare o resumo sem filtro.
- **R4/R5/R7 — vivos.** Plataformas que mudem degradam ficha a ficha
  (`docs_estado='falhou'` com botão manual — estados de §3.3); o R7
  (DR mudar o formato) degrada em silêncio e não tem superfície nova
  aqui — a defesa continua a ser o texto guardado + `--reler`
  (auditoria §5). Sem monitorização agregada de plataformas: fica
  como está, não se desenha sem dados novos.
- **R13/R15 — vivos**, com as superfícies existentes (aviso na zona
  de estado;
  diagnóstico documentado).
- **C3 (histórico de erros)** está proposto no BACKLOG e **não é
  assumido** por nenhuma página; §4 nível 3 apenas lhe reserva o
  lugar.

---

## 9. Mapa de migração

Tipos: **mantém-se** (mesma função, mesmo lugar), **muda de sítio**
(mesma função, novo lugar na navegação — o caminho pode não mudar),
**funde** (passa a modo/vista de outra página), **desaparece**,
**nova**.

| # | Rota actual | Página nova | Tipo |
|---|---|---|---|
| 1 | `GET /` | Triagem (âmbito por omissão novo; a lista completa passa à Pesquisa) | mantém-se |
| 2 | `GET /cpv.json` | serviço da árvore CPV (transversal, §3.0) | mantém-se |
| 3 | `GET /csv` | acção de Triagem e Pesquisa | mantém-se |
| 4 | `GET /alertas` | Alertas | mantém-se |
| 5 | `GET /contratos` | Mercado · Contratos | mantém-se |
| 6 | `GET /contratos/resumo` | serviço dos gráficos (só sob filtro) | mantém-se |
| 7 | `GET /contratos/csv` | acção de Mercado · Contratos | mantém-se |
| 8 | `GET /renovacoes` | modo "fim estimado" dos Contratos (proposta 6.1-A) | funde* |
| 9 | `GET /entidade/<chave>` | Ficha da entidade | mantém-se |
| 10 | `GET /anuncio/<ref>` | Ficha do anúncio | mantém-se |
| 11 | `GET /documento/<ref>/<nome>` | serviço das peças (ficha) | mantém-se |
| 12 | `GET /quadro` | Em curso · Quadro | muda de sítio |
| 13 | `GET /calendario` | Em curso · Calendário | muda de sítio |
| 14 | `GET /indicadores` | Indicadores, via zona de estado | muda de sítio |
| 15 | `POST /verificar` | Triagem / Em curso | mantém-se |
| 16 | `POST /estado/<ref>/<novo>` | Triagem / Pesquisa / Ficha | mantém-se |
| 17 | `POST /sou` | cabeçalho (transversal) | mantém-se |
| 18 | `POST /responsavel/<ref>` | Ficha do anúncio | mantém-se |
| 19 | `POST /filtros/guardar` | transversal (todas as listas) | mantém-se |
| 20 | `POST /filtros/<id>/apagar` | Alertas | mantém-se |
| 21 | `POST /alertas/criar` | Alertas | mantém-se |
| 22 | `POST /alertas/email` | Alertas [dep. E2] | mantém-se |
| 23 | `POST /alertas/<id>/trocar` | Alertas | mantém-se |
| 24 | `POST /alertas/enviar` | Alertas [dep. E2] | mantém-se |
| 25 | `POST /alertas/urgente` | Alertas | mantém-se |
| 26 | `POST /entidade/<chave>/seguir` | Ficha da entidade | mantém-se |
| 27 | `POST /contratos/actualizar` | barra do corpus (Mercado) | mantém-se |
| 28 | `POST /documentos/<ref>` | Ficha do anúncio | mantém-se |
| 29 | `POST /analisar/<ref>` | Ficha do anúncio | mantém-se |
| 30 | `POST /quadro/mover` | Em curso · Quadro | mantém-se |
| 31 | `POST /quadro/fase/nova` | Em curso · Quadro | mantém-se |
| 32 | `POST /quadro/fase/<id>/renomear` | Em curso · Quadro | mantém-se |
| 33 | `POST /quadro/fase/<id>/apagar` | Em curso · Quadro | mantém-se |
| 34 | `POST /quadro/etiqueta/<ref>/nova` | Em curso · Quadro | mantém-se |
| 35 | `POST /quadro/etiqueta/<ref>/tirar/<id>` | Em curso · Quadro | mantém-se |
| — | `GET /anuncios` | Pesquisa (o acervo completo) | **nova** |

*\* pendente da decisão 6.1; na opção B fica "mantém-se".*

**Contagem:** mantém-se **31** · muda de sítio **3** · funde **1**
(pendente; na opção B: mantém-se 32, funde 0) · desaparece **0** ·
novas **1**. A leitura desta contagem é o argumento central do
documento: o problema não são as rotas, é a hierarquia por cima delas.

---

## 10. Sequência de implementação

**Andamento 1 — navegação e âmbito (o alívio maior, o esforço menor).**
Muda: a navegação passa aos cinco itens de §2; `/` abre no âmbito da
Triagem; nasce `/anuncios` (Pesquisa); os Indicadores saem da
navegação para a zona de estado; quadro e calendário agrupam-se sob Em
curso. Zero rotas removidas, zero fusões, o motor de filtros intacto
(P3). Desbloqueia: o fim do 61 981 na cara todas as manhãs (P1) e uma
primeira navegação por intenção. Continua na mesma: todas as páginas
por dentro, o vocabulário, as vistas irmãs. **Parar aqui deixa a
aplicação coerente.**

**Andamento 2 — estado, vocabulário e atalhos.** Muda: os três níveis
de estado de §4 arrumados (nada de item na barra, nada de sistema nas
fichas); a tabela de vocabulário de §7 aplicada aos ecrãs e CSV; os
seis atalhos propostos de §5 (cada um é uma ligação com a query
canónica — baratos por construção, FR-15). Desbloqueia: a sensação de
"uma aplicação" no dia-a-dia. Continua na mesma: duplicações.

**Andamento 3 — fusões escolhidas e a dívida do HTML.** Muda: o que o
Afonso decidir em §6 (renovações como modo; faixa CPV e selector de
procedimento partilhados). **É aqui que faz sentido pagar a dívida do
HTML por concatenação (auditoria §3.9)** — fundir vistas sem extrair o
esqueleto comum era duplicar strings outra vez; a fusão é a ocasião
que amortiza a extracção. (Como pagar, não é deste documento.)
Desbloqueia: o fim do "corrigido numa vista, vivo na irmã" (§3.2).

**Andamento 4 — o Fluxo B inteiro (dependente E2/E3).** Muda: a
entrega das novidades — e-mail ligado (E2) com os links resolvidos
(E3), ou o bloco "novidades por ver" na Triagem se a decisão for sem
e-mail (§8). Desbloqueia: a promessa central ("deixar de precisar de
abrir o radar") pela primeira vez com conteúdo real. Continua na
mesma: tudo o resto — este andamento é independente dos anteriores e
pode trocar de ordem com o 3 se a decisão E2 chegar primeiro.

---

## 11. Perguntas em aberto

Por impacto na estrutura. As decisões E1–E4 já esperam no
SANEAMENTO.md e não se reformulam aqui.

1. **Renovações: fundir ou manter?** (§6.1) A: uma página com eixo
   declarado — menos manutenção, um ecrã bifacetado. B: duas páginas —
   mais claras uma a uma, custo de manutenção medido (§3.2). A escolha
   define a linha 8 do mapa de migração.
2. **Âmbito por omissão da Triagem:** (a) janela dos 60 dias de
   `detalhe_dias` — alinha com o que a rotina lê e com "o que é
   concorrível" (ESTADO); (b) prazo aberto, incluindo antigos com
   prazo lido — mais completo, mistura idades; (c) "desde a última
   visita" — o mais radical, exige definir "visita". Consequência: é o
   número que a aba mostra todas as manhãs.
3. **Sem e-mail (se E2 ficar em não): onde vivem as novidades?**
   (a) bloco "novidades por ver" na Triagem — a entrega passa a ser o
   ecrã, e "entregue" muda de sentido (§8); (b) secção em Alertas —
   mais arrumado, menos visto; (c) fica só o `AVISOS.txt` — o Fluxo B
   continua morto na prática (auditoria §4-B). Só se decide depois do
   E2.
4. **Em curso: confirma quadro+calendário como vistas do mesmo item?**
   E qual abre por omissão — o quadro (trabalho) ou o calendário
   (prazos)? E o nome do item: "Em curso" ou simplesmente "Quadro"?
   Consequência: define §3.4/3.5 e as linhas 12–13 da migração.
5. **Pesquisa por omissão: a base toda ou os últimos N?** (a) tudo —
   honesto, com 91,7% sem detalhe declarado; (b) uma janela com
   interruptor "incluir arquivo" — listas mais úteis, mais um conceito
   de âmbito para além do da Triagem. Consequência: o que "Pesquisa"
   promete.
6. **Indicadores só pela zona de estado chega?** (a) sim — navegação
   limpa, um clique a mais para os KPI; (b) manter também um atalho
   visível secundário. Consequência: se (b), a navegação tem 5+1
   itens.
7. **Entidades precisam de porta própria?** Hoje chega-se à ficha só
   por ligações; uma pesquisa de entidade (nome/NIF) seria
   funcionalidade nova — não determinável pelos documentos se existe
   procura directa. (a) só ligações, como hoje; (b) caixa de procura
   de entidade em Mercado. Consequência: (b) acrescenta uma
   funcionalidade ao andamento 2, fora do "consolidar sem acrescentar".
8. **"Verificar agora" onde?** (a) só na Triagem — é lá que os novos
   aterram; (b) Triagem + Em curso, como hoje (auditoria §1.1).
   Consequência: quantos sítios mostram o estado "a verificar…".
