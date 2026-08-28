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
mude decisões ou números.

## Comandos

```bash
python radar.py                    # painel em http://localhost:8765
python radar.py --uma-vez          # verifica e sai (é o que as tarefas correm)
python radar.py --historico 730    # recolha extra de N dias; conta horas
python radar.py --reler            # reanalisa o texto já guardado, sem rede
python radar.py --ler-pecas [tudo] # manda as peças ao modelo; "tudo" refaz as já lidas
python radar.py --importar-cpv F   # carrega o vocabulário CPV (uma vez)
python radar.py --contratos [anos] # corpus de contratos do Portal BASE
```

Testes — sem rede, sem base, correm em menos de um segundo:

```bash
python teste_radar.py                                    # todos
python teste_radar.py TestPrefixoCPV                     # uma classe
python teste_radar.py TestPrefixoCPV.test_divisao_normal # um teste
```

Os `.bat` são atalhos para o Afonso, não para desenvolvimento:
`instalar.bat` (pip), `iniciar.bat` (painel), `verificar.bat` (`--uma-vez`),
`agendar.bat` (cria as tarefas 09h/17h), `historico.bat` (gitk).

## Arquitectura

Tudo em **`radar.py`** (~3900 linhas), dividido por bandas com cabeçalho
`# ---`. A ordem do ficheiro é a ordem do fluxo:

1. **base** — `liga()`, `iniciar_db()`, `ler_config()`. SQLite, tabelas
   `anuncios`, `documentos`, `analise`, `fases`, `etiquetas`, `historico`,
   `cpv_dict`, `slots`, `estado`, `filtros_guardados`.
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
   (`CSS`, `BASE`, `NAV`). Vistas: anúncios (`/`), contratos
   (`/contratos`), ficha (`/anuncio/<ref>`), quadro kanban, calendário,
   indicadores.
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
  espera de uma segunda fonte de anúncios: não há. E o conjunto "OCDS" do
  dados.gov está vazio desde 2022; o que se usa é o dump normal do IMPIC.
- **Anúncios e contratos são separadores diferentes, de propósito.** Um
  anúncio é uma oportunidade, um contrato já está assinado; os filtros
  nem coincidem (um anúncio não tem vencedor nem valor final). A lista
  `/` chama-se **Anúncios** e a chave interna é `"anuncios"`; os
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
  (`/contratos/resumo`, ~800 ms sem filtro), e a rota devolve **HTML e
  não JSON** — desenhar continua em Python, com `<div>`s dimensionados,
  sem biblioteca. No "quem ganha", o valor reparte-se pelos
  adjudicatários (`contratos.n_adj`): um agrupamento de três não vale
  três vezes o mercado. O trimestre a decorrer vai às riscas, senão
  parece uma queda a pique. São seis: quem ganha, quem compra, como se
  compra, concentração, tamanho dos contratos, evolução.
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
  1,36 milhões de contratos e 1,2 GB — e refaz-se com `--contratos`. O
  endereço do dump muda todas as semanas: resolve-se sempre pela API do
  dados.gov, nunca se guarda.
- **Um filtro guardado é uma query string, não SQL.** A tabela
  `filtros_guardados` guarda o que `filtro_actual()` produz, e aplicá-lo
  é seguir uma ligação. Duas coisas seguram isto e não se mexem: a ordem
  dos campos é fixa (é ela que deixa reconhecer o filtro em uso por
  igualdade de texto) e o `estado` entra **sempre**, mesmo vazio —
  ausente é "por ver", vazio é "todos", como em `condicoes()`. Cada
  separador tem a sua lista em `VISTAS` (campos + rota), e a unicidade é
  por `(vista, nome)`. Campo novo? Acrescenta-o à lista da vista; se for
  da vez e não do filtro, a `CAMPOS_DA_VEZ`.
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
Correm em menos de um segundo: corre-os antes de gravar.

### Armadilhas já pagas

Custaram horas uma vez. O registo longo está no `ESTADO.md`; estas quatro
valem sempre:

- **Nunca testes um endereço que passou por um `[:n]`.** Dois "isto é
  impossível" falsos vieram de códigos de acesso truncados na impressão —
  juntos, tinham declarado ~53% da cobertura das plataformas impossível.
- **Antes de dizer "a correcção não funcionou", confirma a hora de arranque
  do processo na porta 8765.** Já houve cinco instâncias em simultâneo
  (SO_REUSEADDR no Windows), a responder à vez e com código velho.
- **Para ver se o modelo inventou um facto, normaliza a fonte como o
  extractor a normaliza.** O PDF parte números ("1 2 meses") e um grep
  ingénuo produz uma acusação falsa. É o que o `ensaio-de-leitura` faz.
- **Os heredocs do Bash comem um nível de escape neste ambiente.** Para
  código com barras invertidas, usa as ferramentas de escrita.

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

## Git

Repositório local, sem remoto. Commit no fim de cada trabalho acabado, sem
esperar autorização.
