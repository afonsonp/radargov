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

| ID | Item | Origem | Valor | Esforço | Confiança | Prioridade — a conta | Onde toca | Dependências | Risco |
|---|---|---|---|---|---|---|---|---|---|
| B03 | Vista "Renovações": contratos do corpus com fim estimado (`data_celebracao + prazo_execucao`) nos próximos N meses, filtráveis por CPV/entidade — a pergunta "o que vai renovar no meu mercado?" | Armilar "Previsão de Contratos" (módulo de 1ª linha), SpotGov "Pipeline Radar" | 5 | 3 (~2 dias: consulta + vista com árvore CPV reutilizada + índice) | Alta — **verificado**: 96,6% dos 1,36 M contratos têm prazo_execucao>0; 81 827 terminam nos próximos 6 meses | **P1**: valor 5, ≤3 dias, confiança alta; não é P0 porque uma vista nova a sério passa das 8h | rota nova (ou secção em `/contratos`), `com_corpus()`, `arvore_html()` (fonte contratos), índice novo em contratos(fim estimado) ou coluna calculada na importação | — | [PRAZO] o fim estimado é estimativa: prorrogações não constam do dump |
| B04 | Desconto por segmento e na ficha: preço base vs preço contratual, ligado por `n_anuncio = ref` e agregado por procedimento (não por linha — os lotes contaminam) | Tendios "Visão geral" (desconto méd 20,58%), Armilar Insights (0,47% estimado por concurso) | 4 | 3 (~2–3 dias) | **Média** — a ligação existe (187 489 pares com ambos os preços) mas a média ingénua dá 50%: multi-lote e multi-adjudicatário exigem agregação por procedimento antes de dividir | **P1 fronteira com P2**: valor 4 e ≤3 dias, mas a confiança é média — fica P1 porque o passo de validação está identificado (agregar por `n_anuncio` e comparar amostras à mão) e o resto é o padrão já usado nos gráficos dos contratos | `/contratos/resumo` (7º gráfico), ficha do anúncio (desconto médio do CPV), `com_corpus()` | B02 ajuda (mesma ligação) | [RISCO] se a agregação não limpar os lotes, o número mente — validar contra 20 casos à mão antes de mostrar |
| B05 | Avisar de alterações: na releitura de detalhe da janela, comparar prazo/preço/texto com o guardado; mudanças em anúncios marcados (interessa/fases) entram no resumo diário como "alterados" | Tendios ("incluir modificações"), GovGo ("alteração ou anulação de procedimentos dos favoritos") — 2 de 4 têm | 4 | 3 (~2–3 dias: coluna de hash/versão + diff de campos + secção no e-mail) | Alta para prazo/preço (campos já parseados); a detecção de anulações depende de o DR republicar — por confirmar o formato | **P1**: valor 4, ≤3 dias, confiança alta no núcleo (prorrogações de prazo, que é o caso que importa) | `ler_detalhes()`/`reparsear()`, tabela `historico` (já existe para triagem — acrescentar eventos de fonte), `enviar_resumo()`, `registar_alertas()` | rotina diária a reler a janela (já corre) | [PRAZO] uma prorrogação perdida é pior que nenhuma promessa — só anunciar quando o diff estiver testado |

## P2

| ID | Item | Origem | Valor | Esforço | Confiança | Prioridade — a conta | Onde toca | Dependências | Risco |
|---|---|---|---|---|---|---|---|---|---|
| B06 | Taxa de acerto por alerta: em `/alertas`, por cada alerta, quantos anúncios marcou e em que estados acabaram (interessa/descartado/por ver) | Tendios (ficha do alerta: em curso · guardadas · descartadas · taxa) | 3 | 2 (~5h) | Alta — `registar_alertas()` já anota o que corresponde; falta cruzar com `estado` e mostrar | **P2**: esforço baixo mas valor 3 (há poucos alertas e um utilizador — o sinal de "alerta mal afinado" vale menos que numa equipa); não cumpre o valor 4–5 de P1 | `/alertas`, consulta sobre a tabela de correspondências + `anuncios.estado` | alertas em uso há tempo suficiente para haver números | |
| B07 | Escolha E/OU entre palavras e CPV no filtro, com a redacção "pesquisa mais ampla / mais restrita" | Tendios (a melhor tradução de booleana para humano vista) | 3 | 2 (~4h) | Alta | **P2**: valor 3 — o AND implícito serve na maioria dos dias; ganha valor se B01 entrar (exclusões + OU compõem) | `condicoes()`, `CAMPOS_FILTRO`, formulário | B01 primeiro (partilham UI) | |
| B08 | Perguntas às peças configuráveis: mover as `LEITURAS` (âncoras+prompt por campo) para o `config.json`, editáveis sem mexer no código; opcionalmente um 4º campo definido pelo utilizador ("que alvará exige?") | Tendios (acções editáveis + "Regras para a IA"), Armilar (Q&R livre), SpotGov (chat + uploaded docs) | 3 | 2 (~1 dia) | Alta na mecânica; média no valor — o Afonso mexe no radar.py sem medo, o ganho é para o "outro utilizador" futuro | **P2**: valor 3 e o caso de uso concreto ainda não apareceu (nenhum campo novo foi pedido desde a v1 da leitura) | `LEITURAS`, `ler_config()`, `analisar_pecas()`; validação de âncoras à entrada | orçamento do modelo aguenta um 4º campo (ver ESTADO.md: ~8 mil tokens/min) | |
| B09 | Pesquisa full-text nas peças descarregadas: FTS5 sobre os textos extraídos (`texto_estado='ok'`), como opção "procurar nas peças" na lista | Armilar ("Incluir documentos PDF da oportunidade na pesquisa"), SpotGov ("Search in Documents") | 4 | 4 (~1 semana: tabela FTS, indexação incremental no worker das peças, UI, e o caso "só tem peças quem foi marcado") | Média — só há texto das peças descarregadas (as do interessa + pedidos manuais), logo a pesquisa cobre uma fracção pequena da base e pode enganar | **P2**: valor alto mas esforço grande E cobertura parcial que exige comunicação honesta na UI | tabela FTS nova no radar.db (ou anexa), `extrair_textos()`, `condicoes()` ou pesquisa própria | peças descarregadas em quantidade útil | [RISCO] parecer que pesquisa "tudo" quando só pesquisa o que foi trazido |
| B10 | Seguir entidades: marca "seguir" na `/entidade/<chave>` e secção no painel/resumo com novos anúncios e contratos das seguidas | Armilar ("Empresas seguidas"), SpotGov (monitored companies) | 3 | 3 (~2 dias) | Alta na mecânica; média no valor (o filtro por `ent` guardado já faz 80% disto) | **P2**: sobreposição grande com filtros guardados+alertas que já existem — só vale se a sobreposição incomodar na prática | tabela nova (entidades_seguidas), `/entidade/`, `enviar_resumo()` | — | |

## P3

| ID | Item | Origem | Valor | Esforço | Confiança | Prioridade — a conta | Onde toca | Dependências | Risco |
|---|---|---|---|---|---|---|---|---|---|
| B11 | Soma do preço base por coluna do quadro (cabeçalho da fase: "4 anúncios · 1,2 M€") | SpotGov (kanban com valor por fase) | 2 | 1 (~2h) | Alta | **P3**: agradável, não muda decisões — cosmético por definição do critério | `quadro()` (rota `/quadro`), `euros_curto()` | — | |
| B12 | Fontes com página nas leituras do modelo: guardar em `analise` a página/offset do recorte que sustentou cada campo, e mostrar na ficha | Armilar (resumo com números de página clicáveis ao lado do PDF) | 2 | 3 | Média — o recorte atravessa páginas; mapear offset→página do PDF não é directo com o extractor actual | **P3**: premissa técnica por confirmar + valor 2 (o `ensaio-de-leitura` já cobre a auditoria a quem desenvolve) | `recorte_relevante()`, extracção de texto (guardar quebras de página), `analise`, ficha | — | |
| B13 | Prazo do "urgente" configurável no painel (hoje `janela_urgente()` fixa) | GovGo (prazo "A findar" editável: 5 dias) | 2 | 1 (~2h) | Alta | **P3**: cosmético; a janela única já é regra do projecto, só ganharia um campo no config | `janela_urgente()`, `config.json`, cartão dos indicadores | — | |

## Feito

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

## Não fazer, e porquê

Decisões registadas com a observação que as sustenta. Reabrem-se se a
premissa mudar — com data e números novos.

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
