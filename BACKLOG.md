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

- **Ingerir as plataformas (Vortal e afins) como segunda fonte de anúncios**
  — consultas preliminares e contratos menores. É a maior lacuna real face a
  Tendios/Armilar/SpotGov, confirmada em duas passagens. **Não se faz sem o
  Afonso decidir** (regra registada no CLAUDE.md): implica scraping de
  plataformas comerciais fora do caminho anónimo actual das peças, com
  fragilidade e possível atrito de termos de utilização. [LEGAL] [RISCO]
  Se um dia se decidir, o caminho já conhecido é a API pública da Vortal
  (a cadeia de 3 saltos do `obter_documentos()`).
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
