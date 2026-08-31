# Backlog — melhorias saídas da análise competitiva de 30/08/2026

Origem: `CONCORRENTES.md` (passagens de 29 e 30/08/2026) e a prova em
`concorrentes/`. Os cinco itens identificados na Tendios a 29/08 estão cá
dentro, reavaliados à luz da Armilar, GovGo e SpotGov.

**Critério de prioridade** (aplicado item a item, com a conta à vista):
- **P0** — fecha uma desvantagem competitiva já medida, esforço ≤ 8h
- **P1** — valor 4–5, esforço ≤ 3 dias, confiança alta
- **P2** — valor alto mas esforço grande, ou confiança média
- **P3** — cosmético, ou premissa por confirmar

Esforço: 1 ≈ ≤2h · 2 ≈ meio dia a 1 dia · 3 ≈ 2–3 dias · 4 ≈ 1 semana ·
5 ≈ mais que isso.

## Registo de pendências — fechado a 31/08/2026

Tudo o que está em aberto, com **quem** decide ou age e **o que o
dispara**. Nada aqui está a meio: ou espera uma palavra do Afonso, ou
espera um gatilho declarado. O que não está nesta tabela está decidido
ou feito.

| # | O que falta | Estado | Espera por |
|---|---|---|---|
| E2 | O **primeiro envio** do resumo diário | Canal autentica desde 31/08; nunca saiu um e-mail com conteúdo | Uma ordem do Afonso — sai mesmo um e-mail, por isso não se dispara sozinho |
| E4 | ~~Registar quando o token expira~~ | **Feito a 31/08/2026**: cada expiração grava o momento e a idade da captura na série de erros (C3) e na marca dos indicadores | — |
| — | ~~Andamentos do esqueleto~~ | **Feitos a 31/08/2026** (1: navegação e âmbitos · 2: vocabulário e atalhos · 3: renovações fundidas em modo · 4: verificado, o Fluxo B já estava inteiro — ver ESTADO.md). O que sobra do 4 é exactamente o E2 acima | — |
| B15 | ~~Exportar a triagem~~ | **Feito a 31/08/2026**: `triagem.jsonl` (8 330 registos) escrito em cada verificação e reposto por `--repor-triagem`; ver a secção abaixo | A sub-decisão que sobra: o **push** é manual (o de agora) ou passa a tarefa semanal? Só a semanal fecha mesmo o R2 — palavra do Afonso |
| B14 | **Vortal e acingov** como segunda fonte | **A investigação está feita (31/08/2026) e deu «dá» nas duas** — listagem anónima confirmada, receitas anotadas na secção B14. A ingestão é que continua por decidir e por escrever | Decisão informada do Afonso sobre cada plataforma, com os achados à frente. Os avisos [LEGAL] [RISCO] mantêm-se |
| C3 | ~~Histórico de erros~~ | **Feito a 31/08/2026**: tabela `erros` com poda a 200 por tipo; as marcas continuam a servir o ecrã | — |
| — | ~~Fallback morto na detecção de plataforma~~ | **Medido e corrigido a 31/08/2026**: +28 anúncios com plataforma (todos acingov, dita por extenso no corpo); 56 → 28 sem plataforma | — |
| 11.7-B | **Procura directa de entidade** (nome/NIF) | Fora do esqueleto por decisão dele, registada como reabrível | O sinal: dar por si a abrir um contrato só para chegar à ficha de uma entidade |
| — | **Visualizador de PDF na ficha**, com pesquisa lá dentro | Em «Não fazer», por decisão dele ao retirar o B09 | Ele pedir |

**Dependências, e o estado de cada uma:**

- **E2 → Fluxo B:** deixou de bloquear. O canal autentica; falta só
  disparar o primeiro resumo. O cenário «sem e-mail» (secção de
  novidades em Alertas, decisão 11.3-B) fica escrito mas deixou de ser
  o provável.
- **E3 → ecrãs fora do PC:** fechada. Os links do resumo ficam em
  `localhost` por decisão; nenhum ecrã é desenhado para o telemóvel.
- **R1 (token) → recolha:** viva, mitigada pelo aviso no painel. O E4
  (feito a 31/08) não a reduz — mede-a: a série na tabela `erros` é que
  há-de dizer a frequência real.
- **R11 (volume) → `/contratos/resumo`:** viva. É a razão de a entrada
  de Mercado ser «a pergunta primeiro», e o esqueleto proíbe qualquer
  painel que dispare o resumo sem filtro.
- **R2 (perda do PC) → código:** fechada a 31/08 com o remoto do
  GitHub. **Para a triagem continua aberta**, e só o B15 a fecha.
- **6.2-B (dois motores de filtro):** decidido mantê-los. Não é
  pendência, é decisão — reavaliável no andamento 3.

## P0

Vazio — B01 e B02 feitos a 30/08/2026; ver «Feito», no fim.

## P1

Vazio — B03, B04 e B05 feitos a 30/08/2026; ver «Feito», no fim.

## P2

Vazio — B06 a B10 feitos a 30/08/2026; ver «Feito», no fim.

## P3

Vazio — B11, B12 e B13 feitos a 30/08/2026; ver «Feito», no fim.
**O backlog da análise competitiva está fechado de P0 a P3.**

## Feito

- **B03 — vista "Renovações"** (30/08/2026). Separador novo `/renovacoes`:
  contratos do corpus com fim estimado (coluna `fim_estimado` =
  celebração + prazo em dias, com migração idempotente e índice) numa
  janela de 3/6/12/24 meses, filtráveis como os contratos (a vista
  `renovacoes` partilha os campos, menos `de`/`ate` — a página já tem um
  eixo do tempo). A pergunta vem primeiro, como em `/contratos`. A
  página diz que o fim é estimado e que prorrogações não constam do
  dump. Medido: 81 827 contratos terminam nos próximos 6 meses (bate
  com a conta da análise); limpeza 6 meses ~350 ms.
- **B04 — desconto sobre o preço base** (30/08/2026). Validado como o
  backlog exigia: a média ingénua por linha dá **-18,9%** (cada lote
  compara com a base do procedimento inteiro); agregado por `n_anuncio`
  com base constante dá descontos plausíveis. Ficam de fora os grupos
  com a base a variar entre lotes (5 388 — aí a base é por lote,
  semântica ambígua) e a soma acima da base (4 275, ruído): sobra o
  conjunto limpo de 97 130 procedimentos. 7º gráfico no resumo dos
  contratos (mediana global 8,7%; CPV 72: 3,4%; limpeza: 10,5%) com
  índice parcial (1,0 s → 0,07 s), e desconto mediano da entidade+CPV
  na ficha do anúncio (mínimo 5 procedimentos).
- **B05 — avisos de alterações** (30/08/2026). `reler_marcados()` relê
  por verificação até 25 anúncios interessa/quadro com prazo aberto;
  `_guardar_detalhe()` compara prazo e preço base com o guardado
  (`diferencas_do_detalhe()`: só valor→valor diferente — campo que
  desaparece é o parser a tropeçar, não se grita lobo). As mudanças vão
  para a fila `alteracoes` (reconhecer/enviar separados, como os
  alertas) e para o histórico da ficha ("DR · alterou · prazo de
  propostas: 05/09/2026 → 19/09/2026"); o resumo diário ganha a secção
  "Alterados desde a última leitura". Ensaiado sobre cópia da base com
  uma prorrogação simulada de 14 dias; reler o mesmo texto não avisa
  duas vezes. Anulações ficaram de fora (o formato de republicação do
  DR está por confirmar — era a parte de confiança média do item).

- **B01 — exclusões nos filtros** (30/08/2026). `q_excl` e `cpv_excl`
  em `condicoes()` e `condicoes_contratos()`, nos quatro formulários
  (anúncios, contratos, ficha da entidade, novo filtro dos alertas) e
  em `CAMPOS_FILTRO`/`CAMPOS_POR_VISTA` — filtros guardados, alertas e
  CSV herdaram de graça, como previsto. O `cpv_excl` é caixa de texto
  (códigos ou palavras, separados por `|`): o modo excluir na árvore
  ficou de fora — exigia tri-estado no JS partilhado e destrancava os
  descendentes (`arvoreTrancarFilhos`), que é trabalho a sério; se o
  campo à mão incomodar, reabre-se como item próprio. Medido: `q=
  manutenção` 3 781 → 3 616 sem `elevador|avac`; `cpv=72` 235 → 225 sem
  `724`; nos contratos, limpeza (909100) 12 156 → 11 892 sem "escolas".
- **B02 — procedimentos homólogos na ficha** (30/08/2026).
  `homologos_do_anuncio()` procura contratos da mesma `chave` com
  termos do título (`termos_do_titulo()`, sem o vocabulário burocrático)
  no `objecto_norm`; com 2+ termos exigem-se 2 em comum, senão um só
  "manutenção" arrastava a manutenção toda da entidade. Caixa
  "Procedimentos homólogos" antes do histórico por CPV, só quando há
  resultados, com os termos usados à vista. Confirmado o caso Armilar:
  "Fornecimento de refeições e Serviço de bar" mostra as edições de
  2025/2023/2020 (64 975 € / 65 840 € / 70 730 €), em ~20-60 ms.

- **B06 — taxa de acerto por alerta** (30/08/2026). Cada alerta em
  `/alertas` diz agora em que estados acabou o que marcou (interessa ·
  descartados · por ver) e o acerto sobre os triados — o sinal de
  alerta mal afinado.
- **B07 — E/OU entre palavras e CPV** (30/08/2026). Selector `op` nos
  formulários ("mais restrito / mais amplo"); `condicoes()` e
  `condicoes_contratos()` montam os dois lados como fragmentos para os
  juntar por OR sem baralhar a ordem dos placeholders. No modo OU, um
  CPV sem correspondência não esvazia o lado das palavras. Medido:
  manutenção E CPV72 = 46; OU = 3 970.
- **B08 — leituras configuráveis** (30/08/2026). `leituras_activas()`
  põe o `config.json` por cima das `LEITURAS` (quais/âncoras/instrução,
  campo a campo), com validação — um regex estragado deixa ficar o de
  origem, nunca cala uma leitura. **O 4.º campo do utilizador ficou de
  fora**: a tabela `analise` tem colunas fixas e o caso de uso ainda
  não apareceu; reabre-se quando aparecer.
- **B09 — pesquisa nas peças: implementado e RETIRADO** (30/08/2026,
  tudo no mesmo dia). Três versões no dia: campo na lista (cobria 17
  anúncios em 66 mil — enganava), caixa na ficha com excertos (tirava
  a linha do sumário; corrigido com `excerto_de()`), e por fim a
  decisão do Afonso de retirar: **as peças só existem depois de marcar
  "interessa"**, por isso a pesquisa chegava sempre tarde demais para
  ajudar a decidir — não se estava a ganhar nada. O índice FTS saiu da
  base (migração de limpeza no `iniciar_db`) e há teste a impedir o
  regresso acidental. O que ficou de útil: as marcas de página do B12
  no extractor, que eram partilhadas. **A versão que valeria a pena**,
  palavras dele: ver o próprio PDF dentro da aplicação, com pesquisa lá
  dentro — está em baixo, no «Não fazer (por agora)».
- **B10 — seguir entidades** (30/08/2026). Botão na ficha da entidade;
  os anúncios novos das seguidas entram no resumo diário em secção
  própria (reconhecer/enviar como os alertas, acervo ao começar a
  seguir, com âmbito só dessa entidade). Casamento pelo NIPC
  (`anuncios.nif` = chave); entidades `n:` (sem NIF) não têm aviso e a
  ficha não oferece o botão. **Contratos novos das seguidas ficaram de
  fora**: o corpus chega semanal e a ficha da entidade já os mostra;
  reabre-se se fizer falta na prática.

- **B11 — soma do preço base por coluna do quadro** (30/08/2026). O
  cabeçalho da fase diz "2 · 123,4 k€", com o title a dizer sobre
  quantos anúncios com preço lido é a soma (`soma_precos_base()`) —
  somar uns e calar os outros parecia o valor da fase inteira.
- **B12 — fontes com página** (30/08/2026). A premissa confirmou-se: o
  extractor lê página a página, e passou a juntá-las com `\f` em linha
  própria. `paginas_do_recorte()` sai das MESMAS janelas do recorte
  (`_janelas_do_recorte()` partilhado) e as fontes da análise dizem
  "CE.pdf (pág. 1–5)" — por leitura, que objecto e equipa lêem zonas
  diferentes. Textos antigos reextraíram-se uma vez por marca
  (`texto_com_paginas`, 49 s); os sem ficheiro em disco ficaram como
  estavam. Num ZIP com vários PDFs a página é do texto extraído, e a
  nota di-lo.
- **B13 — janela do "urgente" configurável** (30/08/2026).
  `dias_urgente()` lê o `config.json` (lixo/zero voltam a 10) e TODOS os
  sítios leem dela — filtro, rótulos, cartão dos indicadores, saúde.
  Edita-se no painel, em `/alertas` ("Janela do urgente"), com validação
  1–90 à vista.

## Anotado no esqueleto de informação de 30/08/2026

- **Procura directa de entidade (nome ou NIF).** Ficou de fora do
  esqueleto por decisão do Afonso (pergunta 11.7, opção A: chega-se à
  ficha da entidade só por ligações — consolidar não é acrescentar),
  **com a possibilidade registada a pedido dele**. Quando se fizer: uma
  caixa "procurar entidade" em Mercado, a resolver por
  `entidade_nomes` (que já mapeia qualquer grafia à chave) e a levar a
  `/entidade/<chave>`. Os dados já existem; o custo é só de ecrã.
  Esforço 1. O sinal de que faz falta: abrir um contrato qualquer só
  para chegar à ficha de uma entidade.

## Anotado no saneamento de 30/08/2026 — FEITO a 31/08/2026

- **Reter histórico de erros (C3 da auditoria) — feito.** Tabela
  `erros (quando, tipo, texto)` no `radar.db`; `marca_erro()` grava a
  marca de sempre (o ecrã lê-a) MAIS uma linha na série, e a poda no
  `iniciar_db()` guarda os últimos 200 por tipo — os recentes, com
  teste a garantir que não são os primeiros. Tipos: relogio, pecas,
  leitura, copia, token. Leitura por SQL, como proposto; o ecrã fica
  para quando fizer falta.
- **E4 — registar quando o token expira — feito.** Nos quatro pontos
  onde a expiração se detecta (pesquisa e detalhe), o registo grava o
  momento E a idade da captura (`registar_expiracao_token()`, mtime do
  `curl_*.txt`), na série do C3 e na marca `token_ultimo_erro` — que
  aparece nos indicadores como "Última expiração do token". É o
  instrumento que faltava para o piso «≥ 8 dias» virar frequência.
- **O «último recurso do texto todo» na detecção de plataforma — medido
  e corrigido.** Medição a 31/08 (só leitura, sobre a base): dos 56 com
  detalhe e sem plataforma, 18 tinham pistas reais (o strip() não lhes
  toca) e **28 diziam a plataforma por extenso no corpo** — todos
  acingov, referência directa ("apresentados através da plataforma
  eletrónica acinGov"), nenhuma menção de passagem. Aplicado o
  `strip()`, `--reler` (8,2 s): 56 → 28 sem plataforma, e a protecção
  contra menções de passagem continua de pé (pistas reais que não batem
  em nada continuam a NÃO cair para o texto — testado).

## Aprovado pelo Afonso a 30/08/2026

- **B15 — exportação da triagem — FEITO a 31/08/2026.** Implementado
  como especificado abaixo: `exportar_triagem()` corre a seguir à cópia
  diária dentro do `verificar()` (e à mão por `--exportar-triagem`),
  escreve o **`triagem.jsonl`** — 8 330 registos no primeiro export,
  exactamente a medição de 31/08 — com um registo por linha, chaves
  ordenadas e ordem determinística; `--repor-triagem` é o restauro
  idempotente com o relatório dos refs por repor. A escrita é por
  ficheiro temporário + `os.replace`, para um export interrompido não
  fazer de cópia. **A sub-decisão do push continua aberta** (manual ou
  tarefa semanal): por agora é manual — cada commit da sessão leva o
  ficheiro — e só a tarefa semanal fecha mesmo o R2. A especificação
  original fica abaixo, como registo.
  Luz verde do Afonso a 31/08/2026, **e sem urgência**: ele avisou no
  mesmo dia que todo o histórico de actividade actual é **de teste**,
  portanto perder a triagem hoje não custa nada. O risco estrutural
  mantém-se e a especificação fica pronta; **o gatilho é a primeira
  semana de triagem a sério**, e convém não deixar passar disso. O problema: o remoto do GitHub já
  põe o **código** fora do PC, mas a **triagem** — o único dado
  declaradamente irrecuperável — continua só no disco `D:`, porque a
  base de trabalho está no `.gitignore` e ele não tem disco externo. A
  saída é o tamanho: das dezenas de MB da base, a parte irrecuperável
  são **8 330 linhas** (medido a 31/08). Isso cabe num ficheiro de texto
  que viaja no repositório que já existe, e cada push passa a ser uma
  cópia da triagem fora do PC, sem comprar nada.

  **O que entra** (e nada mais — o resto refaz-se): de `anuncios`, só
  `ref`, `estado`, `fase_id`, `responsavel` e `visto_em`, e só das
  linhas triadas, com fase ou com responsável (4 107); `historico`
  inteiro (4 150); `fases` (5); `etiquetas` e `anuncio_etiquetas`;
  `filtros_guardados`; `entidades_seguidas`; e as marcas de já-avisado
  (`alertas_vistos`, `seguidas_vistos`, 66) — sem elas, o primeiro
  resumo depois de um restauro traz tudo outra vez.

  **Formato, e a razão:** um registo por linha, chaves ordenadas, ordem
  determinística. Não é estética — é o que faz o `git diff` mostrar *o
  que mudou hoje* em vez de um ficheiro inteiro reescrito, e é isso que
  torna o histórico do repositório uma máquina do tempo da triagem em
  vez de um monte de versões opacas.

  **Quando corre:** a seguir à cópia diária, dentro do `verificar()` —
  são milhares de linhas, custa nada, e assim está sempre fresco.
  **Como sai do PC:** o export torna o dado pequeno; sair daqui exige um
  push. Ou o Afonso faz commit quando calha, ou uma tarefa semanal faz
  commit+push se o ficheiro mudou. A segunda é a que fecha mesmo o R2,
  com o custo de meter commits de dados no histórico do código — com
  mensagem padronizada, é ruído tolerável. **Decisão dele, quando isto
  se fizer.**

  **Restauro:** um comando próprio, idempotente, para correr **depois**
  de a base ser refeita pela recolha — o ficheiro guarda decisões, não
  anúncios, e os anúncios voltam do DR. Um `ref` que ainda não exista na
  base não se inventa: fica num relatório no fim, para se saber o que
  ficou por repor. Sem isto o restauro parecia completo e não era.

  **O que o ficheiro leva de pessoal:** as decisões dele e o histórico
  com o nome de quem agiu. Repositório privado, dados dele — mas fica
  dito, porque passa a estar fora do PC.


- **B14 — segunda fonte de anúncios: Vortal e acingov, só o que o DR não
  publica.** *(Sequência confirmada a 31/08/2026: fica para a frente,
  como **trabalho de investigação**; só depois de saber o que dá é que
  se tenta a implementação. Não é o próximo trabalho.)* Decisão dele,
  a 30/08/2026, sobre o item que estava em «Não
  fazer» à espera precisamente disto: «podemos avançar com a ligação à
  vortal e acingov se der, apenas para procedimentos que não sejam
  publicados em DR». É a maior lacuna medida face à Tendios/Armilar/SpotGov
  (consultas preliminares e contratos menores — `titulo LIKE '%Consulta
  preliminar%'` dá **zero** na base do radar).

  **O âmbito, que é o que torna isto seguro de desenhar:** só entra o que
  a parte L não publicou. Nada de duplicar o universo do DR — a regra de
  deduplicação é a de sempre, o `ref`, e o que vier das plataformas com
  anúncio no DR ignora-se. Isso mantém a promessa «o DR é a fonte dos
  anúncios» intacta e faz da segunda fonte um acrescento, não um
  concorrente.

  **O «se der» era a primeira tarefa — e foi medido a 31/08/2026:
  existe listagem anónima nas DUAS plataformas.** O que se viu, sem
  sessão iniciada e à mão (medição, não ingestão):

  - **acingov**: zona pública em
    `https://www.acingov.pt/acingovprod/2/zonaPublica/zona_publica_c/indexProcedimentos`
    (POST `procedure_search`; é o formulário da própria homepage).
    Paginada por `zona_publica_c/getProcedimentos/true/<offset>`, 8
    por página; no momento da medição dizia **598 procedimentos a
    decorrer**. Campos por linha: nº de procedimento, tipo, objecto,
    entidade, estado — **sem data de publicação nem prazo na listagem**
    (a confirmar no detalhe). Filtros: texto, sector de actividade,
    concelho. Cada linha traz um botão «Descarregar Peças» com um
    `data-id` cifrado — as peças alcançam-se da própria listagem, sem
    passar pelo link do DR.
  - **Vortal**: pesquisa pública «Consultas Ativas» em
    `https://community.vortal.biz/PRODPublic/Tendering/ContractNoticeManagement/Index`
    (ligada da página de login da vision). Campos ricos: referência,
    comprador, tipo de consulta, preço base, estado, fase, **data de
    publicação e data limite** com contagem de dias; filtros por texto,
    comprador, país (também lista ES — filtrar PT), datas e estado;
    ~108 páginas no momento. O «Detalhe» de cada linha é
    `https://community.vortal.biz/Public/contract-notice-view/PT1.NTC.<id>/`
    — **entrega directamente o `PT1.NTC.x`**, a peça central da cadeia
    de 3 saltos que `obter_documentos()` já usa; a ingestão encaixaria
    no código existente sem o salto de descodificação do link do DR.
  - **A premissa do âmbito confirmou-se à primeira página**: a
    listagem da Vortal mostrava três **«GovPT - Consulta Preliminar»**
    nas primeiras sete linhas — exactamente o tipo que a parte L não
    publica (`titulo LIKE '%Consulta preliminar%'` dá zero na base).

  O que a medição NÃO responde e fica para a fase de ingestão: quanto
  do universo das listagens duplica o DR (o cruzamento é pelo `ref`,
  que a listagem da acingov não mostra — pode obrigar a abrir o
  detalhe), a estabilidade dos endpoints (R4/R5), e o ritmo de
  varrimento aceitável. **Nada disto se escreve sem decisão informada
  do Afonso, plataforma a plataforma.**

  **Os avisos do item antigo mantêm-se, porque a decisão não os apaga**
  [LEGAL] [RISCO]: são plataformas comerciais, o caminho sai do que hoje é
  acesso anónimo a peças públicas, há atrito possível com termos de
  utilização, e a fragilidade é a do R4/R5 multiplicada (uma mudança de
  layout passa a parar recolha, não só peças). Recomendação de execução:
  primeiro a medição, depois uma decisão informada sobre cada plataforma —
  pode dar «a Vortal dá e a acingov não», e isso é resultado, não falhanço.

## Não fazer, e porquê

Decisões registadas com a observação que as sustenta. Reabrem-se se a
premissa mudar — com data e números novos.

- **Visualizador de PDF dentro da aplicação, com pesquisa lá dentro**
  — a ideia do Afonso a 30/08/2026, ao retirar o B09: em vez de uma
  caixa de pesquisa solta, abrir a própria peça na ficha e procurar
  dentro dela. É a versão da pesquisa nas peças que valeria a pena,
  e ele decidiu explicitamente **não avançar já** ("para já diria que
  não estamos a ganhar nada com esta função"). Não se faz sem ele
  pedir. Quando se fizer, o caminho barato é servir o PDF que já está
  em `documentos/` num `<iframe>`/`<embed>` (o visualizador do browser
  já pesquisa com Ctrl+F); as marcas de página do B12 continuam no
  extractor para o que for preciso.

- **Número de licitadores por concurso** — Armilar e SpotGov mostram-no;
  **não há fonte pública**: o dump do IMPIC não o traz (medido a 29/08) e o
  da Armilar vem presumivelmente dos dados internos da própria plataforma.
  Prometê-lo seria inventá-lo.
- **Previsão do preço vencedor por ML** (SpotGov, BETA deles) — sem o nº de
  licitadores nem dados de propostas, o radar só teria o desconto histórico
  (B04), que é a versão honesta da mesma pergunta. A versão "intervalo de
  confiança de 80%" é marketing não verificável — não perseguir.
- **Geração e revisão de propostas por IA** (SpotGov Plus, Tendios
  Advanced) — viola a condição de princípio do projecto: **propostas, CVs e
  trabalho próprio não passam pelo modelo** (registada desde o início no
  ESTADO.md). Não é falta de capacidade, é decisão de âmbito.
- **Chat livre sobre as peças** (Armilar Q&R) — o orçamento de modelo do
  radar é medido ao token (8 mil/min, 200 mil/dia na Groq) e um chat torna o
  consumo imprevisível; as três leituras estruturadas + B08 (perguntas
  configuráveis) cobrem o caso de uso com custo previsível. Reavaliar se
  houver Dev Tier.
- **Pesquisa em linguagem natural** ("Search with AI" da SpotGov) — para um
  utilizador que conhece o CPV e o mercado, a árvore com contagens + palavras
  + exclusões (B01) responde mais depressa e sem gastar orçamento.
- **Multi-país (Espanha)** — a observação da Tendios e da Armilar mostra o
  custo de o fazer mal (taxonomia trocada, traduções com fugas, ruído
  catalão na lista). O radar é bom precisamente por ser só parte L, bem.
- **Multi-utilizador a sério** (permissões, comentários, atribuição além do
  `responsavel`) — o radar é 1–2 pessoas; SpotGov e Tendios vendem equipas.
  Reabrir quando houver equipa.
- **App móvel / push** — o e-mail diário chega ao telemóvel; um push a mais
  não muda nenhuma decisão de dia útil.
- **Contagem decrescente ao segundo, mapas nas fichas** (GovGo, Armilar) —
  ornamento; os dias restantes calculados (`dias_restantes()`) dizem o mesmo.
- **Exportação Excel nativa** (Armilar CSV+Excel, Tendios 4 formatos) — o
  CSV do radar já sai com vírgula decimal e data no nome para o Excel
  português (`numero_csv()`/`nome_csv()`); um .xlsx a sério só acrescentaria
  dependências. Reavaliar se o Afonso alguma vez tropeçar no CSV.
