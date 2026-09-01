# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Este projecto é escrito e comentado em português. Escreve em português de
Portugal — código, comentários, mensagens de commit e respostas.

## O que é

Aplicação local em Python que vigia os anúncios de contratação pública da
**parte L da série II do Diário da República**, guarda-os em SQLite e
mostra-os num painel Flask em `http://localhost:8765`. Corre no PC do
Afonso, verifica sozinha às 09:00 e às 17:00 por tarefas do Windows, e não
depende de nada da empresa.

Substitui a Armilar (produto Vortal, 200 €/mês). O `ESTADO.md` é o diário
do projecto — **lê-o antes de mexer** e actualiza-o no fim de trabalho que
mude decisões ou números. O `CONCORRENTES.md` guarda o que se observou nos
produtos pagos deste mercado, com data: o que fazem melhor, onde se partem,
e o que daí se aproveita.

**A documentação corrige-se na mesma sessão que muda o comportamento.**
Antes do commit de qualquer trabalho que mude comportamento, números ou
decisões, procura no `ESTADO.md`, no `LEIA-ME.md` e neste ficheiro as
afirmações que o trabalho tornou falsas — contagens (testes, anúncios,
linhas), funcionalidades descritas como inexistentes ou ao contrário,
limites e janelas — e corrige-as **no mesmo commit**. Em particular: o
parágrafo «Como está a correr» do ESTADO.md é o primeiro sítio onde se
mente por omissão, porque as sessões acrescentam secções novas sem
tocar no topo; se o teu trabalho mudou números, esse parágrafo é
paragem obrigatória. Um commit que muda o `radar.py` sem tocar em
nenhum `.md` é sinal para verificar, não prova de que está tudo bem.
(A auditoria de 30/08/2026 encontrou o ESTADO.md a abrir com números
13× errados e o LEIA-ME.md a negar funcionalidades que já existiam —
esta regra existe para isso não voltar.)

## Comandos

```bash
python radar.py                    # painel em http://localhost:8765
python radar.py --uma-vez          # verifica e sai (é o que as tarefas correm)
python radar.py --historico 730    # recolha extra de N dias; conta horas
python radar.py --reler            # reanalisa o texto já guardado, sem rede
python radar.py --ler-pecas [tudo] # manda as peças ao modelo; "tudo" refaz as já lidas
python radar.py --importar-cpv F   # carrega o vocabulário CPV (uma vez)
python radar.py --contratos [anos] # corpus de contratos do Portal BASE
python radar.py --descartar-expirados # descarta os "por ver" com prazo passado
python radar.py --exportar-triagem # B15: triagem.jsonl (a verificacao exporta E faz commit+push sozinha)
python radar.py --repor-triagem [F] # repoe a triagem numa base refeita; idempotente
```

As tarefas do Windows são três (`agendar.bat`): as duas verificações
diárias e a do corpus, à segunda. **Se faltarem, o radar só recolhe com
o painel aberto** — e o relógio interno recupera os slots falhados, o
que faz a tabela `slots` parecer certa. O painel avisa a vermelho.

Testes — sem rede e sem tocar na base verdadeira; correm em poucos
segundos (os do B15 criam repositórios git temporários):

```bash
python teste_radar.py                                    # todos
python teste_radar.py TestPrefixoCPV                     # uma classe
python teste_radar.py TestPrefixoCPV.test_divisao_normal # um teste
```

Os `.bat` são atalhos para o Afonso, não para desenvolvimento:
`instalar.bat` (pip), `iniciar.bat` (painel), `verificar.bat` (`--uma-vez`),
`agendar.bat` (cria as três tarefas), `reler.bat` (`--reler`),
`contratos.bat` (o que a tarefa semanal corre), `ensaio.bat`
(ensaio-de-leitura), `historico.bat` (gitk), `desinstalar.bat` (tira as
tarefas agendadas). Todos passam pelo `_python.bat`, que escolhe o
Python da pasta se existir.

## Arquitectura

Tudo em **`radar.py`** (~10 mil linhas), dividido por bandas com cabeçalho
`# ---`. A ordem do ficheiro é a ordem do fluxo:

1. **base** — `liga()`, `iniciar_db()`, `ler_config()`. SQLite, tabelas
   `anuncios`, `documentos`, `analise`, `fases`, `etiquetas`, `historico`,
   `cpv_dict`, `slots`, `estado`, `filtros_guardados`, `erros` (C3: a
   série dos erros que as marcas sobrescrevem; poda a 200 por tipo).
2. **captura** — `carregar_curl()` / `parse_curl()` lêem `curl_DR.txt` e
   `curl_detalhe.txt`, capturas cURL feitas à mão no DevTools.
3. **leitura** — `recolher()` pagina a pesquisa do portal;
   `ler_detalhes()` vai à página de cada anúncio buscar CPV, prazo e preço
   base; `campos_do_detalhe()` faz o parsing por secções numeradas.
4. **documentos** — `obter_documentos()` puxa as peças do procedimento das
   plataformas que o permitem (`PLATAFORMAS_COM_PECAS`: acingov, vortal,
   compraspt, anogov), por fila e thread de fundo. Ficam em `documentos/`
   no disco, **não na base** — para o `radar.db` ficar pequeno.
5. **leitura das peças por modelo** — `analisar_pecas()` recorta as zonas
   relevantes do CE/PC e faz três pedidos (um por campo), gravando em
   `analise`. Cada pedido desce a cadeia `FORNECEDORES` (Groq → NVIDIA →
   OpenRouter) até alguém responder. **Medido: nenhuma das reservas
   aguenta um recorte de tamanho real em rajada** — ver o ESTADO.md antes
   de contar com elas.
6. **contratos celebrados (BASE)** — `importar_contratos()` traz o dump
   semanal do IMPIC do dados.gov para o **`contratos.db`**, ficheiro
   próprio. `historico_entidade()` responde ao bloco da ficha do
   anúncio, `ficha_entidade()` à página `/entidade/<chave>`.
7. **painel** — rotas Flask, HTML gerado por concatenação de strings
   (`CSS`, `BASE`, `NAV`). Navegação por quatro intenções: Anúncios
   (`/`, a lista única com as abas por ver / interessados /
   abandonados / todos; `/anuncios` redirecciona), Em curso (quadro
   `/quadro` + calendário `/calendario`), Mercado (contratos
   `/contratos`, com o modo `?ver=fim` das antigas renovações;
   `/renovacoes` redirecciona), Alertas (`/alertas`). Indicadores
   (`/indicadores`) fora da barra, pelo ponto da zona de estado. Ficha
   em `/anuncio/<ref>`, em composição de dossier: uma coluna, com o
   cabeçalho fino e o índice presos ao rolar. Uma peça abre **dentro
   da ficha** (`?peca=<nome>`), por baixo da lista das peças; a rota
   própria `/peca/<ref>/<nome>` mantém-se para ligações directas, e as
   duas partilham `visualizador_de_peca()`.
8. **agendamento** — `relogio()`, thread daemon que dispara os slots.

### O que não é óbvio

- **Não se filtra nada à entrada.** Decisão tomada depois de uma primeira
  versão que filtrava por pontuação: entra tudo o que a parte L publicar, e
  a triagem faz-se no painel. Não reintroduzas filtros em `recolher()`.
- **O BASE não traz anúncios novos.** Medido, e a decisão já foi tomada:
  os "anúncios" do Portal BASE são o mesmo universo do DR (`nAnuncio` é o
  `ref` do radar, o `url` aponta para o diariodarepublica.pt), e o dump é
  semanal, portanto mais atrasado que o radar. **Abaixo dos limiares não
  existe anúncio nenhum** — esses procedimentos só se vêem como contrato
  celebrado. Não acrescentes coluna `fonte` nem mexas na deduplicação à
  espera de uma segunda fonte de anúncios **vinda do BASE**: não há. E o
  conjunto "OCDS" do dados.gov está vazio desde 2022; o que se usa é o
  dump normal do IMPIC. **A ressalva vale só para o BASE**: as
  plataformas publicam procedimentos que a parte L não publica, e essa
  segunda fonte EXISTE desde 31/08/2026 (decisão do Afonso) — ver o
  ponto seguinte.
- **A segunda fonte é a Vortal, e só consultas preliminares.** O âmbito
  é decisão dele (31/08/2026): «só consultas preliminares ou algo que
  não seja publicado no DR — não quero duplicação». `recolher_vortal()`
  corre em cada verificação (`vortal_preliminares` no config) contra a
  pesquisa pública (`SearchTenders`), filtra país PT e tipo preliminar
  — o rótulo muda com o idioma da sessão (`TIPOS_PRELIMINAR` aceita
  «GovPT - Consulta Preliminar» E «Quick Tender GovPT», que são o mesmo
  tipo) — e guarda com `fonte='vortal'`, ref `PT1.NTC.x` e
  `detalhe_lido=1`. **Nunca alargues os tipos**: concursos públicos da
  Vortal estão no DR e duplicavam. As releituras do DR filtram por
  `COALESCE(fonte,'dr')='dr'`; a ficha destas consultas não tem texto
  por desenho (o vazio explica-o); a cadeia das peças aceita o link
  público porque o PT1.NTC vem às claras. A acingov ficou de fora: a
  listagem pública dela não distingue tipos — alargar é decisão nova.
- **Anúncios e contratos são populações diferentes, de propósito.** Um
  anúncio é uma oportunidade, um contrato já está assinado; os filtros
  nem coincidem (um anúncio não tem vencedor nem valor final). A lista
  de anúncios é **UMA página** (`/`, fusão de 31/08/2026 — a Triagem e
  a Pesquisa separadas duraram um dia; `/anuncios` redirecciona) com
  quatro abas cujo recorte vive em `condicao_da_aba()`, aplicado POR
  CIMA do motor com `com_recorte()`: **por ver** = novo e ainda
  respondível (prazo aberto; sem prazo lido vale a publicação dentro
  de `detalhe_dias`), **interessados** = todos (um interessa expirado
  é trabalho em curso), **abandonados** = descartados à mão MAIS os
  por ver já não respondíveis — é recorte de leitura, a base não muda.
  O `estado` da aba tira-se dos args antes de chamar `condicoes()`
  (a aba dos abandonados é uma união que um `estado=?` não diz), mas
  continua na consulta canónica dos filtros guardados. **Nenhum
  recorte entra em `condicoes()`** — o motor serve os alertas e os
  filtros guardados, e o recorte lá dentro cegava-os em silêncio. Os
  contratos vivem em `/contratos`, com `condicoes_contratos()` própria.
  Nas tabelas filhas usa-se **`IN (SELECT ...)`, nunca `JOIN`**: com
  JOIN, um contrato ganho por um agrupamento repetia-se uma vez por
  adjudicatário. `IN` e não `EXISTS` por velocidade — o EXISTS passa por
  todos os contratos a perguntar por cada um (517 ms contra 183).
- **Sem filtro, `/contratos` não mostra lista nenhuma.** São 1,36 milhões
  de contratos e por data não dizem nada; a página levava 48 s a montar.
  A pergunta vem primeiro — ao contrário dos anúncios, onde a lista
  inteira é o acervo por triar. A paginação corre num CTE com o `LEFT
  JOIN entidades` e as subconsultas dos nomes **depois do `LIMIT`**, e há
  índice em `contratos(data_celebracao, id)`: sem ele, ordenar 1,36
  milhões para mostrar 20 levava 6 s.
- **Os gráficos dos contratos correm sobre o filtro da lista**, não sobre
  o corpus todo: o filtro é a pergunta. Pedidos só ao abrir o `<details>`
  (`/contratos/resumo`; sem filtro são ~7 s no corpus de 7 anos — o
  "~800 ms" antigo era doutro corpus, e a lentidão vem das cinco
  consultas de sempre, medida a 30/08/2026 no ESTADO.md), e a rota
  devolve **HTML e não JSON** — desenhar continua em Python, com
  `<div>`s dimensionados, sem biblioteca. No "quem ganha", o valor
  reparte-se pelos adjudicatários (`contratos.n_adj`): um agrupamento de
  três não vale três vezes o mercado. O trimestre a decorrer vai às
  riscas, senão parece uma queda a pique. São sete: quem ganha, quem
  compra, como se compra, concentração, tamanho dos contratos, desconto
  sobre o preço base, evolução. **O desconto agrega por `n_anuncio` e
  nunca por linha** — a média por linha dá -18,9%, porque cada lote
  compara com a base do procedimento inteiro; as exclusões estão em
  `descontos_por_procedimento()`.
- **As renovações são um MODO dos contratos** (fundidas a 31/08/2026,
  decisão 6.1-A): `/contratos?ver=fim` filtra pela coluna
  `fim_estimado` (celebração + prazo em dias; coluna e não expressão,
  com índice próprio), janela por whitelist (`MESES_RENOVACOES`/
  `meses_pedidos()`) porque entra numa expressão de data do SQL. A
  lista, o CSV e os gráficos filtram todos por
  `filtros_dos_contratos()` — uma conta só. A vista de campos
  continua a chamar-se `"renovacoes"` e exclui **`de`/`ate`** — dois
  eixos do tempo na mesma página confundiam; no modo fim esses campos
  desactivam-se com explicação, nunca caem em silêncio. O fim é
  estimado e o modo di-lo: prorrogações não constam do dump.
  `/renovacoes` redirecciona com o filtro atrás — não a removas, é o
  que segura filtros guardados e ligações antigas.
- **A pesquisa nas peças (B09) foi implementada e retirada no mesmo
  dia** (30/08/2026), por decisão do Afonso: as peças só existem depois
  de marcar "interessa", por isso a pesquisa chegava sempre tarde
  demais para ajudar a decidir. Não a reintroduzas — nem `q_pecas` em
  `condicoes()` nem caixa na ficha; há teste a guardá-lo
  (`TestPesquisaNasPecasRetirada`). O `iniciar_db()` limpa o índice
  FTS de quem chegou a ter a versão retirada. **A versão que ele
  queria já existe e é outra coisa**: procurar DENTRO de um documento,
  no visualizador (`visualizador_de_peca()`, com os destaques a
  amarelo). Essa é por peça, não pelo acervo — não confundir as duas,
  nem tomar uma como caminho para a outra.
- **O `op` (E/OU entre palavras e CPV) é um modo, não um filtro**:
  sozinho não conta como pergunta em /contratos nem valida um alerta.
  Em `condicoes()`/`condicoes_contratos()`, os lados q e cpv montam-se
  como fragmentos (sql, valores) e só se juntam no fim — é o que mantém
  a ordem dos placeholders igual à dos valores; há um teste que conta
  os `?`. No modo OU, um CPV sem correspondência não acrescenta nada
  (o `1=0` é só do modo E).
- **As leituras das peças afinam-se no config.json** (`leituras`:
  quais/âncoras/instrução por campo, via `leituras_activas()`), com
  validação: o inválido deixa ficar o de origem, nunca cala uma leitura
  em silêncio. Campos novos não entram por aí — a `analise` tem colunas
  fixas.
- **A releitura dos marcados é vigilância, não recolha.**
  `reler_marcados()` relê por verificação até 25 anúncios
  interessa/quadro com prazo aberto; `_guardar_detalhe()` compara prazo
  e preço base com o guardado e grava as mudanças na fila `alteracoes`
  (reconhecer/enviar separados, como os alertas) e no histórico. Só se
  avisa valor→valor diferente: um campo que passa a vazio é o parser a
  tropeçar, não uma alteração — não grites lobo.
- **O nome não é a identidade de uma entidade: o NIF é.** A Universidade
  do Porto assina com 87 nomes e a MEO com 81, todos com o mesmo NIF.
  Agrupa-se sempre por `chave` (`chave_entidade()`: o NIF, ou `n:` mais o
  nome normalizado quando não há). `entidades` guarda o nome canónico —
  o mais usado — e `entidade_nomes` mapeia qualquer variante à chave, que
  é como o nome que o DR escreve chega ao corpus. Nunca agrupes nem
  filtres por `adjudicante` ou `a.nome`.
- **O `+` de `GROUP BY +a.chave` não se tira.** Desliga o índice de
  propósito: com ele o SQLite varre o índice e vai buscar cada linha ao
  acaso — **17 segundos** contra 1,5 num filtro por CPV. Pela mesma
  razão, o `LEFT JOIN entidades` vai **depois do `LIMIT`**: antes eram
  68 mil buscas ao índice para mostrar 10 linhas.
- **As migalhas são `migalhas_de(vista, folha)`.** Cada página parte do
  item da navegação em que vive (`NAV`/`ITEM_DA_PAGINA`); as vistas
  agrupadas dizem o caminho inteiro ("Em curso › Quadro", "Mercado ›
  Contratos") e as fichas penduram uma folha por baixo — a do anúncio
  em Anúncios. E o "Verificar agora" aparece **só na lista dos
  anúncios** (`PAGINAS_COM_VERIFICAR`, decisão 11.8-A): os novos
  aterram no por ver.
- **A entidade de um anúncio resolve-se pelo NIPC.** O DR publica-o em
  100% dos anúncios e é a chave do corpus — `entidade_do_anuncio(nif,
  nome)`, com o nome de reserva para os antigos. 98,2% contra 96,2% só
  pelo nome. A coluna `anuncios.nif` enche-se com `--reler`, sem rede.
- **Há cópia diária da base de trabalho** em `copias/`, sete guardadas,
  feita antes da recolha com `VACUUM INTO` (a quente, e sai compactada).
  Copiar o ficheiro com o `.wal` ao lado dava uma cópia truncada. Só a
  de trabalho: o corpus e os documentos refazem-se, a triagem não.
- **Os avisos por filtro correm depois de `ler_detalhes()`** — um filtro
  por CPV só apanha o anúncio depois do CPV estar lido — e usam a
  `condicoes()` da lista. Nunca escrevas um segundo motor de filtros.
- **`175.000,00 EUR` é formato português**: ponto nos milhares, vírgula
  nos cêntimos. Usa `euros_do_texto()`; um `float()` ingénuo dá 175,0.
- **As datas guardam-se ISO e mostram-se DD/MM/AAAA.** ISO porque ordena
  como texto; a apresentação passa por `data_pt()` e, quando leva hora,
  por `data_hora_pt()` (histórico da ficha, barra do corpus, barra
  lateral). Nunca ponhas uma data em ISO no HTML **nem no CSV** — um CSV
  também é para ver. E o CSV escreve o estado pelo `_NOMES_ESTADO`
  ("por ver"), não pela chave interna ("novo").
- **Datas de filtro validam-se com `data_de_filtro()`** — só ISO; lixo
  ignora-se e a página avisa (`avisos_de_datas`), incluindo o intervalo
  invertido. Um `de=lixo` comparado com datas esvaziava a lista em
  silêncio.
- **A pesquisa procura em `titulo_norm` e `entidade_norm`, nunca nas
  colunas originais.** O `LIKE` do SQLite só baixa maiúsculas de letras
  ASCII: para ele `Ç` e `ç` são letras diferentes, e escrever
  "aquisição" perdia os 14% de títulos escritos todos em maiúsculas —
  11% de cada pesquisa, sem aviso nenhum. As colunas enchem-se numa
  migração idempotente do `iniciar_db()`, com `simplifica()` registada na
  ligação (`c.create_function`), e o termo procurado normaliza-se do
  mesmo modo. Os índices `ix_anuncios_titulo_norm` e
  `ix_anuncios_entidade_norm` **não são decorativos**: as colunas ficaram
  depois do `texto` do anúncio inteiro, e sem eles o SQLite desserializa
  alguns KB por linha — 4,7 s contra 0,4.
- **Nos contratos, a mesma regra, com a norma certa por coluna.** O
  objecto procura-se em `objecto_norm` (termo por `simplifica()`); os
  nomes de entidade em `adjudicante_norm`/`nome_norm`, com o termo por
  `norma_entidade()` — é ela que enche essas colunas e que troca `&`
  por " e ". Procurar com a norma errada volta a perder 11,8%.
- **O dump do IMPIC vem escapado para HTML, às vezes duas vezes.** Tudo
  o que é texto passa por `_des_html()` à entrada do importador
  (desescapa até estabilizar), senão "Ramos &amp; Filhos" fica
  impesquisável e o painel mostra `&amp;` — 5 998 entidades estavam
  assim. O corpus antigo foi reparado por uma migração com marca
  (`html_desescapado`).
- **`(nenhuma)` e `(por ler)` são baldes diferentes.** `SEM_PLATAFORMA`
  é "detalhe lido, sem plataforma indicada" e exige `detalhe_lido=1`;
  `POR_LER` é "ainda sem detalhe lido", que é 92% da base. Sem a
  distinção, o selector dizia "(nenhuma) (56)" e a lista devolvia 60 645.
  Os números do selector contam sempre sobre os que têm detalhe lido, e
  o cabeçalho di-lo.
- **Os contadores dos separadores contam dentro do filtro**, com a mesma
  `condicoes()` da lista e sem a parte do estado. Contavam a base
  inteira: com um CPV posto diziam "Todos 66 009" por cima de uma lista
  de 234, e as ligações levavam o filtro atrás — o número e o destino do
  mesmo botão discordavam.
- **O `prazo` é um filtro dos anúncios** (`aberto`, `urgente`,
  `expirado`), e a janela do `urgente` é UMA — `janela_urgente()`, usada
  pelo filtro e pelo cartão dos indicadores. Já houve um "7" escrito à
  mão no cartão com o filtro a 10. O número que um ecrã mostra tem de
  dar exactamente a lista que a ligação dele abre. O número vem de
  `dias_urgente()` (config.json, editável em `/alertas`); nunca uses
  `DIAS_URGENTE` directamente num rótulo — é só a omissão.
- **O texto extraído das peças leva `\f` em linha própria** entre
  páginas: é por ele que as fontes da análise dizem "(pág. 1–5)". O
  recorte e as páginas saem das mesmas janelas (`_janelas_do_recorte`);
  um texto sem marcas não declara páginas — não se inventam.
- **Os três trabalhos longos correm todos fora do pedido.** "Verificar
  agora" é thread com trinco (`comecar_verificacao()`, com um `passo`
  que a barra lateral mostra), "Actualizar contratos" é thread com
  estado na base, e as peças e a leitura pelo modelo são filas
  (`pedir_documentos()`, `pedir_analise()`). Nenhum deles espera dentro
  do pedido do browser: já esteve assim e eram minutos de página em
  branco. Em fundo não há cookie para ler — passa o `quem` ao
  `registar()` em vez de contar com o `quem_sou()`.
- **O `relogio()` entra pela mesma porta do botão.** Um slot falhado
  chama `comecar_verificacao(slot=(dia, hora))`, não o `verificar()`
  directo — só assim há trinco (senão o relógio apanhava um clique a
  meio e punha duas verificações na mesma base) e há `passo` (senão o
  arranque do painel ficava ~5 minutos lento, com a cópia, o push da
  triagem e a recolha toda, sem nada no ecrã a dizer porquê). O slot
  só se marca como corrido no fim e se correu bem; se o trinco
  recusar, tenta-se no minuto seguinte. E o botão à mão **não** marca
  slot: um clique às 15h não faz a verificação das 17h por feita.
- **Um `marca_erro()` novo tem de aparecer em `linhas_de_ultimos_erros()`.**
  É a única lista que o ecrã lê (na saúde dos `/indicadores`). O B14 e
  o B15 acrescentaram marcas e não as ligaram lá: um "remote rejected"
  esteve um dia inteiro na base sem existir para ninguém. E a razão de
  um comando git passa por `porque_do_git()` — o "To &lt;url&gt;" que o
  git escreve primeiro comia os 80 caracteres da linha e a razão nunca
  chegava a ver-se.
- **O browser abre-se depois de a porta atender**
  (`abrir_no_browser()`, em thread, com `porta_atende()`). O
  `webbrowser.open()` era chamado antes do `app.run()` e chegava lá
  ~1 s antes de haver servidor. Atenção ao medir isto no Windows: uma
  ligação a uma porta com bind e **sem** listen não é recusada, bloqueia
  até ao timeout — um teste que ponha um servidor a nascer a meio é
  intermitente, e por isso a sonda troca-se por uma falsa nos testes.
- **Toda a truncagem visível passa por `corta()`**, que põe reticências.
  Um `[:190]` cru corta a meio de palavra e lê-se como dado estragado.
  Onde quem corta é o CSS (uma pílula do calendário, um nome num
  gráfico), a regra é a mesma: `text-overflow:ellipsis` e não
  `overflow:hidden` sozinho — "Por analis" também se lê como avaria.
- **Os campos longos do essencial ganham forma, não texto novo.**
  `desenha_valor()` reconhece o que o valor já é — blocos com pares
  «Chave: valor» viram cartões de perfil, linhas com travessão viram
  lista, «1. Nome» + detalhe vira lista numerada — e o resto sai como
  sempre saiu. **A guarda que interessa é a última:** uma frase com
  dois pontos a meio não é um par (senão «Presencial, nas instalações
  do Parque de Saúde de Lisboa» virava tabela); por isso o
  `RX_PAR_PERFIL` exige chave curta. Há teste por forma
  (`TestDesenhaValor`).
- **A largura a mais dá mais informação, não linhas mais compridas.**
  O `.larg` tem tecto (1560px) e a folga lateral acompanha o ecrã
  (`clamp`); as grelhas ganham colunas com `auto-fit`/`auto-fill` em vez
  de terem um número fixo; e o texto corrido tem tecto próprio em `ch`
  — medido, fica em 643px de 1366 a 2560, enquanto as tabelas da mesma
  página vão de 1112 a 1522. Antes disto, um monitor de 1920 tinha 530px
  vazios e um de 2560 tinha 1170.
- **Cor de texto e cor de decoração são escalas diferentes.** O texto
  usa `--t1`..`--t6`, medidos para passar AA (4,5:1) **sobre
  `--papel`**, que é o pior fundo — não sobre branco. Setas, molduras
  tracejadas e separadores usam `--traco` ou `--linha`, e nunca um
  `--t*`. Foi a confusão entre os dois que fez a escala antiga descer a
  2,5:1 em texto de 10px. E um contraste marginal **não se vê,
  mede-se**: a passagem de 31/08/2026 deixou seis falhas entre 4,1 e
  4,43 que nenhuma revisão a olho tinha apanhado — a medição corre como
  script no browser, elemento a elemento contra o primeiro fundo opaco
  acima dele.
- **Os dois CSV escrevem números com `numero_csv()` e chamam-se pelo
  `nome_csv()`.** Vírgula decimal, sem símbolo e sem separador de
  milhares, que é o que o Excel português come; e data no nome, porque
  três `concursos.csv` na pasta das descargas não se distinguem.
- **`ent` é "Entidade que publica" e `adj` é "Entidade que comprou".**
  Os rótulos das caixas e o `_NOMES_FILTRO` dizem o mesmo. Com os dois a
  chamarem-se "entidade", o aviso do parcial saía "entidade Município de
  Lisboa — aqui não se aplica: entidade".
- **A árvore de CPV vem antes dos filtros guardados** e está em todas as
  páginas onde se procura por CPV — anúncios, contratos e ficha da
  entidade. Onde houver campo `cpv`, tem de haver árvore: a caixa de
  texto solta só deixava escolher um código.
- **Os números levam espaço inquebrável** (U+00A0) nos milhares, nos
  três formatadores (`mil_pt`, `euros`, `euros_curto`). Com espaço
  normal o browser parte "1 363 300" ao fim da linha. Há um teste que
  os obriga a concordar.
- **A árvore de CPV é uma só, com duas fontes de contagem.** `arvore_html()`
  põe um `data-de` no `<details>` e o JS lê dali a rota
  (`/cpv.json?de=anuncios|contratos`); `FONTES_CPV` diz de onde se conta.
  Não copies o JS para o segundo separador, e não reutilizes as contagens
  dos anúncios nos contratos — são outras (1 548 códigos têm anúncios,
  5 657 têm contratos). O campo tem `id='filtro-cpv'` nos dois, que é por
  onde a árvore lê e escreve. O `_CPV_CACHE` é um dicionário por fonte.
- **O corpus de contratos é ficheiro à parte** (`contratos.db`), e não
  entra no funil: são contratos assinados, não oportunidades. Cruza-se
  com `ATTACH` (`com_corpus()`). Está no `.gitignore` — 2020-2026 são
  1,36 milhões de contratos e 1,65 GB — e refaz-se com `--contratos`. O
  endereço do dump muda todas as semanas: resolve-se sempre pela API do
  dados.gov, nunca se guarda.
- **Uma migração do corpus sem índice que a sirva é o arranque do
  painel.** O `iniciar_corpus()` corre a cada arranque, e um
  `WHERE <coluna> IS NULL` sem índice varre os 1,65 GB todos — mesmo
  para encontrar zero linhas. Foi o que o `n_adj` fez até 01/09/2026:
  **38,9 s a frio** contra 0,00 s das outras três migrações da mesma
  função, que têm índice. Regra: uma migração idempotente ou tem índice
  que responda ao `IS NULL`, ou tem **marca no `corpus_estado`** (como
  o `html_desescapado` e agora o `n_adj_cheio`) — e a marca só é segura
  quando o importador enche sempre a coluna, o que se garante pelo
  `COLS_CONTRATO`. E **mede-se a frio**: a quente o mesmo varrimento
  dava 0,8 s, que foi o que escondeu isto durante meses.
- **Isto corre de uma pen, e a pen manda nos números.** O `D:` é um
  Samsung Flash Drive por USB, não o SSD interno: 8,7 ms para abrir um
  ficheiro pequeno a frio, e ~42 MB/s efectivos numa varredura de
  páginas de 4 KB (408 MB/s em sequencial puro). Daí os 216 dos 459
  módulos que vêm de `libs/` como ficheiros soltos custarem segundos
  no arranque, e daí uma varredura de 1,65 GB não ser um encolher de
  ombros. Antes de culpar o código por lentidão, confirma em que
  disco ele está (`Get-Partition -DriveLetter D | Get-Disk`).
- **Um filtro guardado é uma query string, não SQL, e não pertence a
  separador nenhum.** Guarda os campos que tiver (`CAMPOS_FILTRO`, ordem
  fixa — é ela que deixa reconhecer o filtro em uso por igualdade de
  texto), e cada página aplica os que entende (`CAMPOS_POR_VISTA`).
  `filtro_para(consulta, vista)` devolve a parte aplicável **e os campos
  que ficaram de fora**: esses nunca caem em silêncio — o chip fica
  marcado como parcial e um alerta com eles avisa só pela parte que
  serve, e diz que o faz. Aplicar "ganho por MEO" aos anúncios, onde não
  há vencedor, seria alargar o filtro sem avisar.
- **O `estado` entra sempre no filtro dos anúncios, mesmo vazio** —
  ausente é "por ver", vazio é "todos", como em `condicoes()`.
- **Um alerta é um filtro com a marca posta.** Geridos em `/alertas`, que
  é também onde se criam e onde se configura o e-mail. `registar_alertas()`
  anota o que corresponde e `enviar_resumo()` manda uma vez por dia — o
  reconhecer e o enviar são separados de propósito, porque a verificação
  corre duas vezes. Ao ligar um alerta, o acervo que já lá está fica
  marcado como `ACERVO`, senão o primeiro resumo trazia tudo.
- **Os campos de entidade dos contratos são `entid`/`vencid`.** Nos
  anúncios `ent` é a caixa de texto da entidade — nomes iguais com
  sentidos diferentes já estiveram a um passo de se cruzar.
- **As colunas do importador saem de `COLS_CONTRATO`/`COLS_CPV`/
  `COLS_ADJ`**, e `_inserir()` constrói o SQL a partir delas. Nunca
  escrevas `VALUES (?,?,…)` à mão: acrescentar uma coluna com o INSERT
  posicional já partiu o importador duas vezes, a segunda a meio de uma
  importação de sete anos.
- **O botão "Actualizar contratos" corre numa thread**, com o estado em
  `corpus_estado` e a página a recarregar-se enquanto isso — um ano são
  ~60 s e um pedido HTTP parado esse tempo parece o painel pendurado. Só
  traz o ano corrente e o anterior: anos fechados não mudam.
- **O DR não tem API pública.** O radar faz-se passar pelo browser com os
  cabeçalhos e o token das capturas `curl_*.txt`. **O token expira** — o
  painel avisa a vermelho e o Afonso refaz a captura no DevTools (instruções
  na secção 3 do `LEIA-ME.md`). Nunca edites estas capturas: um hook
  bloqueia-o.
- **Orçamento do modelo, não contexto.** O tecto da conta Groq são 8000
  tokens/minuto, e é ele que manda no tamanho do pedido — daí
  `TECTO_RECORTE = 7000` caracteres e três pedidos separados em vez de um.
  Juntos, as âncoras do objecto gastavam o orçamento antes de chegar à
  tabela de perfis. Há também um tecto diário: `SEM_ORCAMENTO_HOJE`.
- **Cadeia de reserva, não um fornecedor.** O tecto diário da Groq (200
  mil tokens) acaba a meio de uma releitura do acervo. `_perguntar()`
  desce `FORNECEDORES` até alguém responder, e `_ESGOTADOS` guarda quem
  já bateu no tecto **nesse dia** — sem isso, cada pergunta voltava a
  bater na porta fechada. A mensagem do tecto diário só aparece quando
  **toda** a cadeia esgota (`cadeia_esgotada()`). Só entra quem tem
  chave: sem chaves novas, o comportamento é o de sempre.
- **`analise.modelo` diz quem respondeu**, não o modelo configurado
  (`groq:openai/gpt-oss-120b`). Por ser variável, passa pelo
  `juntar_fontes()` como as fontes — uma releitura parcial apagava o
  registo do modelo que leu os outros campos.
- **As chaves da API** lêem-se de `<fornecedor>_API_KEY.txt` na pasta
  (`groq_API_KEY.txt`, `chave_api.txt`, `openrouter_API_KEY.txt`,
  `nvidia_API_KEY.txt`) ou das variáveis `GROQ_API_KEY`,
  `OPENROUTER_API_KEY`, `NVIDIA_API_KEY`. O `.gitignore` é
  deliberadamente largo (`*api_key*`, `*token*`, `*secret*`) porque a
  chave já apareceu com nomes diferentes — e é ele que já cobre os
  nomes novos.
- **Só passam pelo modelo documentos públicos** (Cadernos de Encargos e
  Programas de Concurso). Propostas, CVs e trabalho próprio não.
- **Migrações idempotentes.** Colunas novas acrescentam-se ao ciclo de
  `ALTER TABLE` em `iniciar_db()`, que corre sempre e não faz nada se já
  existirem. Não escrevas migrações que corram uma vez só.
- **Convenção de acentos:** comentários e docstrings do `radar.py` em ASCII,
  sem acentos; texto visível ao utilizador (HTML, prints, prompts) com
  acentos. Segue o que já lá está.
- **OneDrive.** A pasta está dentro do OneDrive; a sincronização pode
  bloquear o `radar.db` a meio de uma escrita. Se aparecerem erros de base
  bloqueada, é isso.

### Os testes são regressões

Cada classe de `teste_radar.py` corresponde a um erro que existiu mesmo, e
o comentário diz qual — "simplificar" um teste é normalmente voltar ao erro.
Correm em poucos segundos: corre-os antes de gravar.

E onde a documentação disser «em último recurso faz X», escreve o teste que
força esse último recurso. A leitura do código confirma a intenção, não o
disparo: foi um teste novo que descobriu que `" ".join(("","",""))` dá `"  "`
— que é verdadeiro — e que o `or` de último recurso dos sinónimos de
plataforma nunca chegava a correr. Uma auditoria por leitura integral tinha
passado por cima dele no dia anterior.

### Armadilhas já pagas

Custaram horas uma vez. O registo longo está no `ESTADO.md`; estas quatro
valem sempre:

- **Nunca testes um endereço que passou por um `[:n]`.** Dois "isto é
  impossível" falsos vieram de códigos de acesso truncados na impressão —
  juntos, tinham declarado ~53% da cobertura das plataformas impossível.
- **Antes de dizer "a correcção não funcionou", confirma a hora de arranque
  do processo na porta 8765.** Já houve cinco instâncias em simultâneo
  (SO_REUSEADDR no Windows), a responder à vez e com código velho.
  Aconteceu outra vez a 31/08/2026, com duas. Duas consequências
  práticas: **matar por caminho** (todos os python que corram da pasta
  do radar), não só "o que está na porta" — e depois **confirmar que
  ficou um**; e comparar a hora de arranque do processo com a da
  última gravação do `radar.py`. Foi essa comparação que denunciou o
  caso: o processo tinha arrancado quatro minutos ANTES do ficheiro
  que devia estar a servir.
- **Para ver se o modelo inventou um facto, normaliza a fonte como o
  extractor a normaliza.** O PDF parte números ("1 2 meses") e um grep
  ingénuo produz uma acusação falsa. É o que o `ensaio-de-leitura` faz.
- **Os heredocs do Bash comem um nível de escape neste ambiente.** O
  gatilho é o carácter, não o tipo de conteúdo: se o que vais escrever
  tem uma contrabarra — um `\n`, um caminho do Windows, uma expressão
  regular — usa as ferramentas de escrita, sem parar para julgar se é
  "código" ou "só um bloco de texto". A regra já estava aqui escrita e
  falhou duas vezes na mesma hora, nas duas por o conteúdo parecer
  inofensivo.

## Hooks, skills e subagente

Tres hooks, em `.claude/settings.json`. Os tres olham para o `file_path` das
ferramentas de escrita **e para o texto dos comandos** do Bash e do
PowerShell -- so pelo `file_path` eram uma porta com a parede ao lado:

- **`proteger_dados.py`** (PreToolUse) recusa escritas em `curl_*.txt` e
  `radar.db*` -- capturas e base nao se editam a maos. Nos comandos, recusa
  a escrita e deixa passar a leitura: um `sqlite3 radar.db "SELECT ..."` e
  rotina, e travar leituras so ensinava a desligar o hook.
- **`testes_antes_do_commit.py`** (PreToolUse) trava o `git commit` com
  testes a falhar. So o commit; o resto do git passa.
- **`verificar_sintaxe.py`** (PostToolUse) compila o Python escrito com
  `-W error::SyntaxWarning`, porque os erros que passaram despercebidos
  neste projecto foram todos de sintaxe e de escapes. Escrito por comando
  (`sed -i`, heredoc), compila os `.py` nomeados no comando.

Atencao: estes hooks so actuam quando o **`radar/` e a pasta de trabalho**
da sessao. A trabalhar a partir da pasta-mae, nao disparam -- corre entao
`python teste_radar.py` a mao antes de gravar.

Duas skills e um subagente:

- **`estado-radar`** lê a base em modo só-leitura e diz quantos anúncios há,
  quantos faltam ler e se as capturas ainda são válidas — funciona mesmo com
  o `radar.py` a meio de uma alteração que não compila.
- **`ensaio-de-leitura <ref>`** põe cada linha da resposta do modelo ao lado
  do pedaço do documento que a sustenta, para julgar se a leitura das peças
  presta. Com `--sem-modelo` não gasta orçamento; sem ele, relê sobre uma
  **cópia** da base. É a ferramenta do ponto que falta para a v1.
- **`explorador-de-plataforma`** (subagente) investiga se as peças de uma
  plataforma que o radar ainda não sabe descarregar se alcançam sem sessão
  iniciada, e devolve receita ou um "não há" fundamentado.

Fora do projecto, mas activa aqui: a skill global **`task-observer`**
(«One Skill to Rule Them All»). **Invoca-a no início de qualquer sessão
de trabalho** — qualquer interacção em que vais usar ferramentas e produzir
trabalho — antes de começar. É ela que apanha, durante o trabalho, o que
vale a pena guardar sobre as próprias skills e métodos, e escreve-o em
`~/.claude/projects/D--radar/skill-observations/log.md`. A descrição da
skill sozinha não chega para a disparar — é esta instrução que a torna
fiável, e é por ela que a skill volta depois de o contexto ser comprimido.

E ao carregar qualquer skill, vê nesse registo se há entradas **OPEN**
dessa skill e aplica o que dizem ao trabalho a decorrer, mesmo que o
ficheiro da skill ainda não tenha sido actualizado.

## Git

Repositório local, sem remoto. Commit no fim de cada trabalho acabado, sem
esperar autorização.
