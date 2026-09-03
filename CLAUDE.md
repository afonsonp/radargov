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

Substitui a Armilar (produto Vortal, 200 €/mês).

### Onde está a documentação

Arrumada a 3/09/2026, porque eram 10 819 linhas em nove ficheiros à raiz
e este ficheiro sozinho tinha 968. **Não leias tudo: lê o que a tarefa
pede.**

| Ficheiro | O que é | Quando se lê |
|---|---|---|
| **este** | As regras de trabalho e a arquitectura | Sempre. É o único que se carrega inteiro |
| `ESTADO.md` | O estado de hoje, com os números | Ao começar. São 150 linhas |
| `docs/armadilhas.md` | O que não é óbvio, em 14 áreas | **A área que vais tocar**, antes de tocar |
| `docs/referencia.md` | Como cada parte foi feita, e porquê assim | Quando a armadilha não chega |
| `docs/diario/2026-08.md`<br>`docs/diario/2026-09.md` | O diário: o que se mediu e decidiu, dia a dia | Para perceber uma decisão antiga |
| `docs/historico/` | Auditorias e propostas com data fechada: `AUDITORIA`, `SANEAMENTO`, `ESQUELETO`, `UX-Auditoria`, `CONCORRENTES` | Raramente. São instantâneos, não se mantêm |
| `BACKLOG.md` | O que falta, com prioridade | Ao escolher trabalho |
| `LEIA-ME.md` | O manual do Afonso | Ao mexer no que ele opera |

Duas destas merecem nome: o `docs/historico/CONCORRENTES.md` guarda o que
se observou nos produtos pagos deste mercado, com data — **um produto
muda, e o que lá está vale para o dia em que foi visto**. O
`docs/historico/UX-Auditoria.md` (2/09/2026) passa as regras de interface
da casa pelas «leis de UX», uma a uma, com medidas e veredicto (manter,
afinar, dívida): lê-o antes de mexer no painel.

**A documentação corrige-se na mesma sessão que muda o comportamento.**
Antes do commit de qualquer trabalho que mude comportamento, números ou
decisões, procura no `ESTADO.md`, no `docs/armadilhas.md`, no
`LEIA-ME.md` e neste ficheiro as afirmações que o trabalho tornou falsas
— contagens (testes, anúncios, linhas), funcionalidades descritas como
inexistentes ou ao contrário, limites e janelas — e corrige-as **no mesmo
commit**.

Três paragens obrigatórias quando o trabalho mudou números ou
comportamento: o **«Como está a correr» do `ESTADO.md`**, a **área
tocada do `docs/armadilhas.md`**, e a **lista de comandos** aqui em
baixo. Um commit que muda o `radar.py` sem tocar em nenhum `.md` é sinal
para verificar, não prova de que está tudo bem.

O **diário é acrescento, não correcção**: uma sessão nova escreve uma
secção nova em `docs/diario/2026-MM.md`, e o que ela tornou falso
corrige-se nos três sítios acima. Uma secção do diário que descreva algo
depois revertido fica lá, com uma citação no topo a dizê-lo — foi assim
que o OCR e a vigilância das peças ficaram registados a 3/09/2026.

(A auditoria de 30/08/2026 encontrou o ESTADO.md a abrir com números 13×
errados e o LEIA-ME.md a negar funcionalidades que já existiam — esta
regra existe para isso não voltar. E a 3/09/2026 o mesmo parágrafo
estava outra vez com números de dois dias antes, que foi o que motivou a
arrumação.)

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
python radar.py --importar-excel F [--ensaio] [--sem-rede] [--com-triagem] # o Excel da casa (casa.py); sem --com-triagem só guarda e liga
python radar.py --casa-ligar ID REF  # liga à mão uma linha do Excel a um anúncio
python radar.py --casa-desfazer COPIA # repõe a triagem tal como está numa cópia de antes
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

Quase tudo em **`radar.py`** (~13 mil linhas), dividido por bandas com
cabeçalho `# ---`; o registo da casa está em **`casa.py`** (ver abaixo).
A ordem do ficheiro é a ordem do fluxo:

1. **base** — `liga()`, `iniciar_db()`, `ler_config()`. SQLite, tabelas
   `anuncios`, `documentos`, `analise`, `fases`, `etiquetas`, `historico`,
   `cpv_dict`, `slots`, `estado`, `filtros_guardados`, `erros` (C3: a
   série dos erros que as marcas sobrescrevem; poda a 200 por tipo).
2. **comum** — as utilidades puras: `simplifica()`, `data_pt()`,
   `data_hora_pt()`, `mil_pt()`, `euros_do_texto()`, `conta_dias()`,
   `dias_restantes()`, `dias_urgente()`, `janela_urgente()`,
   `etiqueta_prazo()`, `para_like()`, `prefixo_cpv()`,
   `data_de_filtro()`, e as duas primitivas do filtro de texto
   (`frag_de_texto()` / `frag_de_exclusao()`, que as duas
   `condicoes*()` partilham). Não tocam na
   base, não escrevem HTML e não dependem de nada à frente. **Um
   formatador novo entra aqui**, não na banda que por acaso o precisou
   primeiro — ver a regra no `docs/armadilhas.md`.
3. **captura** — `carregar_curl()` / `parse_curl()` lêem `curl_DR.txt` e
   `curl_detalhe.txt`, capturas cURL feitas à mão no DevTools.
4. **leitura** — `recolher()` pagina a pesquisa do portal;
   `ler_detalhes()` vai à página de cada anúncio buscar CPV, prazo e preço
   base; `campos_do_detalhe()` faz o parsing por secções numeradas.
5. **documentos** — `obter_documentos()` puxa as peças do procedimento das
   plataformas que o permitem (`PLATAFORMAS_COM_PECAS`: acingov, vortal,
   compraspt, anogov), por fila e thread de fundo. Ficam em `documentos/`
   no disco, **não na base** — para o `radar.db` ficar pequeno.
6. **leitura das peças por modelo** — `analisar_pecas()` recorta as zonas
   relevantes do CE/PC e faz três pedidos (um por campo), gravando em
   `analise`. Cada pedido desce a cadeia `FORNECEDORES` (Groq → NVIDIA →
   OpenRouter) até alguém responder. **Medido: nenhuma das reservas
   aguenta um recorte de tamanho real em rajada** — ver o
   `docs/referencia.md` antes de contar com elas.
7. **contratos celebrados (BASE)** — `importar_contratos()` traz o dump
   semanal do IMPIC do dados.gov para o **`contratos.db`**, ficheiro
   próprio. `historico_entidade()` responde ao bloco da ficha do
   anúncio, `ficha_entidade()` à página `/entidade/<chave>`.
8. **painel** — rotas Flask, HTML gerado por concatenação de strings
   (`CSS`, `BASE`, `NAV`). Navegação por quatro intenções: Anúncios
   (`/`, a lista única com as abas por ver / interessados /
   abandonados / todos; `/anuncios` redirecciona), Em curso (quadro
   `/quadro` + calendário `/calendario`), Mercado (contratos
   `/contratos`, com o modo `?ver=fim` das antigas renovações;
   `/renovacoes` redirecciona), Alertas (`/alertas`, com o interesse
   em `/alertas/interesse`). Indicadores
   (`/indicadores`) fora da barra, pelo ponto da zona de estado. Ficha
   em `/anuncio/<ref>`, em composição de dossier: uma coluna, com o
   cabeçalho fino e o índice presos ao rolar. Uma peça abre **dentro
   da ficha** (`?peca=<nome>`), por baixo da lista das peças; a rota
   própria `/peca/<ref>/<nome>` mantém-se para ligações directas, e as
   duas partilham `visualizador_de_peca()`.
9. **agendamento** — `relogio()`, thread daemon que dispara os slots.

### O que não é óbvio está em `docs/armadilhas.md`

São 78 pontos, cada um de um erro que existiu mesmo, em **14 áreas**:
a recolha e as fontes · as peças e as plataformas · o modelo que lê as
peças · o motor de filtros · datas, números e texto · a árvore de CPV ·
contratos e entidades · alertas e interesse · triagem, quadro e ficha ·
o registo da casa · a base, as migrações e o disco · trabalhos de fundo
e arranque · a interface · convenções.

**Lê a área antes de lhe mexer.** Estavam aqui até 3/09/2026 e
carregavam-se inteiros em todas as sessões, incluindo as que só tocavam
num sítio. Três que valem sempre, seja qual for a área:

- **Não se filtra nada à entrada.** Entra tudo o que a parte L publicar,
  e a triagem faz-se no painel. Não reintroduzas filtros em
  `recolher()`.
- **Nenhum recorte entra em `condicoes()`.** Esse motor serve também os
  alertas e os filtros guardados; um recorte lá dentro cega-os em
  silêncio. As abas e o interesse aplicam-se por cima, com
  `com_recorte()`.
- **Um número que um ecrã mostra tem de dar exactamente a lista que a
  ligação dele abre** — e a cor de uma etiqueta é um desses números.

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

**Separa a condição da espera.** Quando o contrato de uma função é «espera
até X e só então faz Y», torna o X injectável e escreve-o: `False`, `False`,
`True`, e verifica as duas coisas — que o Y aconteceu e quantas vezes se
perguntou. Guarda um teste pequeno que exercite o X verdadeiro contra o
recurso verdadeiro, para a condição ficar coberta, mas não faças a asserção
da ordem depender de concorrência real. Um teste cujo sucesso depende de um
`sleep` numa thread aterrar antes de um prazo noutra é um teste instável que
ainda não falhou: passou duas vezes isolado, falhou à terceira e outra vez
dentro da bateria completa, e o que estava a medir era o escalonador do
sistema. (Pelo caminho apareceu um facto do Windows que piora muito as
contas: ligar a uma porta que está reservada mas ainda não à escuta não é
recusado — bloqueia o tempo todo do timeout.)

### Armadilhas já pagas

Custaram horas uma vez. O registo longo está no `docs/diario/`; estas quatro
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
  **Falso positivo conhecido:** o hook procura o padrao no texto do comando
  e nao distingue texto que executa de texto que descreve execucao, por
  isso dispara num `git commit` cuja *mensagem* cita o SQL que foi
  alterado. O efeito pratico nao e neutro -- obriga a escrever a mensagem
  de commit de forma mais vaga sobre exactamente aquilo que o hook protege.
  Estreitar o padrao (so o argumento de um cliente de base de dados, um
  `-c`/`-e`, um redireccionamento para o stdin dele) ou isentar os comandos
  estruturalmente incapazes de o executar (`git commit`, `git tag`) e
  mudanca a uma guarda de seguranca: decisao do Afonso, nao se faz de
  passagem.
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

**Há remoto**, ao contrário do que este ficheiro afirmou até 01/09/2026:
`origin` é `https://github.com/afonsonp/radarconcursos.git` e o `master`
segue o `origin/master`. Isto não é detalhe de arrumação — é o que decide
se um commit **sai da pen**, e escrito ao contrário levava a tratar o
histórico como se nunca saísse daqui. O repositório é privado (medido a
31/08/2026: um pedido anónimo dá 404 — ver o `docs/diario/2026-08.md`,
«O código saiu do PC»), mas privado não é o mesmo que interno: o `.gitignore` largo
continua a ser a guarda, e é ele que mantém capturas, bases, chaves e
peças de fora.

Commit no fim de cada trabalho acabado, sem esperar autorização. Numa
sessão local (na pen), **push não**: quem empurra é o Afonso, ou o
próprio radar pelo B15 — e o B15 empurra mais do que o nome diz:
`empurrar_triagem()` faz **commit** só do `triagem.jsonl`, mas o **push
é do ramo inteiro** e a decisão de empurrar é `git rev-list --count
origin/master..master`, não o diff do ficheiro. Ou seja, qualquer commit
que fique no `master` da pen sai sozinho na verificação seguinte (09:00
ou 17:00), tenha a triagem mudado ou não. Um push falhado retoma na
volta seguinte (desliga-se com `"triagem_no_git": false`). Escrito ao
contrário — «push só do triagem.jsonl» — levava a contar com um push à
mão que já não é preciso, e a não perceber que um commit por acabar
deixado no `master` sai para o GitHub sem mais ninguém o mandar.
Numa sessão remota (claude.ai/code), o trabalho vai para um ramo
`claude/*` e o merge para o `master` **é o Claude que o faz**, por
decisão dele a 02/09/2026 («tens de começar a ser tu a fazer»): validar
no PC primeiro, fazer o merge do PR, e dizer-lhe os dois comandos para a
pen apanhar o `master` (`git checkout master`, `git pull origin master`).

Trabalha-se no `master`, e a 03/09/2026 é o único ramo que existe: os
`claude/*` de sessões anteriores foram apagados a pedido dele, depois de
se confirmar que nenhum tinha commits exclusivos (`git log
origin/master..origin/<ramo>` vazio nos dois). O worktree que houve em
`.claude/worktrees/` também já não existe. Um ramo `claude/*` que volte
a aparecer é de uma sessão remota, e **não se apaga sem uma palavra
dele** — nem depois do merge.
