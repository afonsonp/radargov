# Concorrentes

O que os produtos pagos deste mercado fazem, o que fazem mal, e o que
daí se aproveita para o radar. Escrito a olhar para eles com a conta do
Afonso, não a partir de material de marketing.

Cada secção tem a data da observação. **Um produto muda; o que aqui está
vale para o dia em que foi visto.** Antes de citar um número destes numa
decisão, confirma se ainda é verdade.

## Passagem de 30 de agosto de 2026 — as quatro plataformas

Segunda passagem, agora completa: **Armilar** (conta paga da empresa),
**GovGo** (trial, sessão do Afonso), **SpotGov/Augusta Labs** (demo guiada
Navattic + site público) e **Tendios** (reverificação da análise de 29/08).
A prova detalhada, com extractos datados das páginas, está em
`concorrentes/<plataforma>/*.md` — as capturas de ecrã não puderam ser
gravadas em ficheiro (limitação da ferramenta de browser desta sessão), por
isso a evidência são extractos de texto com URL e data.

O que mudou face a 29/08:

- O defeito de identidade da Tendios é **pior** do que estava registado: o
  NIF 508080142 devolve **13 órgãos**, não 2.
- O duplicado de fichas da Tendios foi **reproduzido num anúncio nosso**
  (21825/2026, duas fichas com horas-limite diferentes).
- Teste de paridade corrido nas quatro (3 anúncios de 28/08 do radar):
  Tendios 3/3 · Armilar 2/3 · GovGo **0/3** · SpotGov não testável (demo).
- A "segunda fonte de anúncios vinda das plataformas" (registada a 29/08 como
  premissa que mudou) confirma-se na Armilar: consultas preliminares e
  micro-compras à vista. Continua a ser decisão por tomar, não tomada.

---

## Armilar (Vortal) — o que a empresa paga a ~200 €/mês

**Observado a 30 de agosto de 2026**, conta da empresa ("Public Sector /
Conkord PT"), business.armilar.biz. É o produto que o radar substitui.

### A. Entrada e posicionamento

- Preços públicos: **não existem** — armilar.biz/pt-pt/plans diz "preços sob
  consulta". 3 planos: INTELLIGENCE ("o mais escolhido"), CONSTRUÇÃO+ (junta
  mercado privado da construção), SAÚDE+ (preços de princípios activos).
  Todos PT+ES, com "Resumo de Oportunidades por IA" e "Consultor Dedicado".
  O que a empresa paga (~200 €/mês) é conhecimento interno, não tabela.
- Onboarding: não verificado (conta já existente). O perfil da conta tem
  33 categorias e 27 localizações configuradas.

### B. Fontes e cobertura

- Universo total pesquisável: **11 378 004 oportunidades** (PT+ES), incluindo
  **micro-despesas adjudicadas** — almoços protocolares de 18 €, reservas de
  hotel de 87 € da Universitat de Girona. Cobertura enorme, ruído idem.
- "Informação atualizada diariamente" (declarado no topo das listas).
- Distinguem anúncio de contrato? Meio: um selector de Estado
  (Publicado/Adjudicado/Formalizado) na mesma lista — como a Tendios, tudo no
  mesmo separador.
- **Teste de paridade (3 anúncios do radar de 28/08):**
  - 21811/2026 UMinho → **encontrado** (CCP USSIC-22-2026), mesmo dia,
    preço/prazo iguais, peças completas na ficha.
  - 21825/2026 ULS Sto António → **encontrado**, mesmo dia.
  - 21809/2026 Sto Tirso (E.M. 644, 872 k€, plataforma vortal!) → **não
    encontrado**: duas pesquisas AND com palavras do título devolvem obras
    antigas de Santo Tirso mas não esta, 2 dias depois de publicada. As
    "falhas de ingestão" que motivaram o radar, medidas num caso concreto.
  - Inverso: 3 itens deles → 3/3 no radar, mesmas datas.
- Consultas preliminares: sim, no universo (registado a 29/08 na Tendios via
  fonte GLOBAL_VORTAL; a Armilar É a Vortal).

### C. Dados e modelo

- Ficha da oportunidade: entidade gestora e contratante separadas **com
  NIF**, mapa do local de execução, tipo de procedimento e de contrato,
  duração prevista do contrato, prazo com fuso horário, CPV com descrição,
  documentos (peças) com data.
- **Identidade por NIF, correcta**: o selector de compradores pesquisa "por
  Nome ou por NIF"; "São José" devolve 14 entidades cada uma com o seu NIF e
  a ULS de São José aparece **uma vez** (508080142). Sem o defeito da
  Tendios.
- Histórico: contratos desde pelo menos 2014 vistos em pesquisa.
- **Bloco "Insights" na ficha** — a mecânica exposta pela query string do
  botão "Insights detalhados": desconto estimado, nº potencial de
  participantes e **potenciais concorrentes com NIF, desconto médio e taxa
  de sucesso**, calculados como "quem ganhou contratos da mesma categoria e
  localização com valor entre 50% e 150% do preço base nos últimos 2 anos".
- A Análise de Mercado tem colunas **Desconto e Número de licitadores** por
  contrato — o nº de licitadores não existe no dump do IMPIC; origem deles
  não declarada (plausível: dados internos da plataforma Vortal).

### D. Filtros, alertas e triagem

- Pesquisa simples: **OR de palavras soltas ordenado por data** — "equipamento
  de produção e distribuição de vapor" devolve 9 942 resultados com almoços
  catalães no topo. Com "Incluir todas as Palavras" (AND) fica utilizável,
  mas a frase completa deu 0 mesmo estando no título. Sem aviso de nada.
- Pesquisa avançada: compradores, localizações, tipo de procedimento, estado,
  datas, preço base min/max, tipo de contrato, categorias. E uma opção
  notável: **"Incluir documentos PDF da oportunidade na pesquisa"** —
  full-text nas peças.
- **"Meus Interesses" é uma armadilha**: lista filtrada pelo perfil da conta
  (33 categorias/27 localizações) sem o dizer — o 21825/2026 não aparecia lá
  de todo, e 9 das 10 primeiras entradas eram de Espanha/Catalunha porque a
  conta tem um filtro chamado "ESPANHA" activo.
- Alertas: por filtro, frequência Nunca/Diário/Semanal, momento do dia
  configurável (início/almoço/fim, ou dois momentos). Sem taxa de acerto.
- Triagem: favoritos (coração), "As minhas oportunidades", "Gestor de
  tarefas" (não explorado a fundo).

### E. IA e leitura de peças — testada, e funciona

- **"Gerar resumo da oportunidade"**: 1–3 minutos, abre página própria com
  **versionamento** ("Versão 1 - 30/08/2026"), PDF das peças ao lado, e
  secções (visão geral, datas, critérios, garantias/penalidades, pagamentos)
  **cada uma com fonte: o PDF e os números de página clicáveis**. A secção de
  garantias cita cláusulas exactas ("Cláusula 3ª, n.º 1 e 2", "R.4, R.10").
- **Q&R com IA** (chat sobre o concurso): "Que documentos devem constituir a
  proposta?" → resposta em <20 s citando a Cláusula 8ª do Programa, com os
  anexos certos e o modo de submissão. "Fixa um limiar de preço anormalmente
  baixo?" → "não menciona explicitamente um limiar fixo" — **não inventou**.
  Com "Ver Fonte". As perguntas são livres.
- Defeitos: markdown por renderizar (`**`, `###` à letra) em todo o lado;
  secção de pagamentos repete a mesma informação 3×; o painel do chat nasce
  colapsado fora do ecrã numa janela grande (foi preciso JavaScript para o
  abrir).
- Ao contrário da Vera/Tendios (conta gratuita), **a IA da Armilar lê mesmo
  as peças**. É o único dos quatro onde isso foi verificado ao vivo.

### F. Dashboards e visualização

- Dashboard: previsão de contratos (8 328 a terminar, 1 243 M€), oportunidades
  (650/6 meses), 263 632 adjudicações, janela 6/12 meses.
- **Previsão de Contratos**: lista "Próximos a Terminar" com probabilidade e
  data estimada de conclusão — contratos existentes transformados em
  oportunidades de renovação. (O radar consegue calcular isto do
  contratos.db: celebração + prazo de execução.)
- Análise de Mercado: abas Contratos / Principais Adjudicadores / Principais
  Concorrentes, gráfico barras+linha, tudo a responder ao filtro. "Guardar
  como filtro" igual ao conceito do radar.
- "Minha posição no mercado": funil próprio (oportunidades/propostas/
  adjudicações) — vazio nesta conta, não verificado com dados.

### G. Conectores e saída

- Exportar: **CSV e Excel** (não descarregado). Botão "Open Lusha"
  (integração de contactos B2B). API pública: nada visto; não verificado.

### H. UX, UI e execução técnica

- SPA Angular/Material com skin Vortal; "Mais Oportunidades" salta para
  community.vortal.biz com login separado — o produto é uma federação de
  módulos, nota-se.
- Taxonomia de procedimentos portuguesa correcta no universo global ("Ajuste
  Directo / Consulta Prévia", "Concurso Limitado sem Publicação").
- Pesquisa por texto lenta a aplicar-se (segundos com a contagem antiga no
  ecrã). O chat de IA fora do ecrã (acima). De resto competente.

### I. Presença no mercado

No contratos.db (SQL em `concorrentes/presenca-mercado.md`): a Vortal como
**fornecedora do Estado** tem 471 contratos, 4,66 M€ (2020–2026), ~630 k€/ano
estável, clientes sobretudo saúde (SPMS, hospitais/ULS) e municípios, CPV
72xxx. A ACIN (acinGov) no mesmo período: 622 contratos, 13,95 M€, pico 2025
(EMEL, 4,07 M€). Curiosidade do dump: há um "adjudicatário" chamado
"https://community.vortal.biz/sts/Login" — lixo de dados do IMPIC.

---

## GovGo (VIPA) — 50 €/semestre

**Observado a 30 de agosto de 2026**, trial do Afonso (14 dias restantes),
www.govgo.pt. Produto da VIPA (Madeira, 2019, CEO Pedro Paixão), lançado em
2023.

### A. Entrada e posicionamento

- "Todos os anúncios de concursos públicos numa única plataforma" — **só
  Portugal**. Persona: PME que quer olhar para os concursos sem pagar caro.
- **Preços públicos**: 15 dias grátis; **Semestral 50 €+IVA; Anual 90 €+IVA**
  — ~7,5 €/mês, duas ordens de grandeza abaixo da Armilar. Sem escalões: um
  plano com tudo (alertas "ilimitados").
- App móvel "brevemente disponível nas stores" (declarado).

### B. Fontes e cobertura — o ponto fraco, medido

- Fonte é claramente o DR (a ficha é o anúncio do DR, ver C). Frequência
  declarada: "tempo real"; observada: **o dia 28/08 tem 8 procedimentos na
  lista deles; o radar tem 99 anúncios de procedimento desse dia.**
- **Teste de paridade: 0/3** — nem o 21811 (UMinho), nem o 21825 (ULS Sto
  António), nem o 21809 (Sto Tirso) aparecem, com a pesquisa a funcionar
  (validada com "oximetria": 15 resultados 2020–2026). Critério de selecção
  deles: desconhecido. Inverso: 3 itens deles → 3/3 no radar, mesmas datas.
- Contratos: 574 115 desde jan/2020 — **o radar tem 1,36 M no mesmo
  período**. E na ordenação por omissão o contrato mais recente é de
  **23/01/2025**, ~19 meses atrás.
- **Reverificado ~24h depois** (a pedido do Afonso, para excluir atraso de
  ingestão): as três pesquisas continuam a zero, o dia 28/08 continua com as
  mesmas 8 entradas, e os totais (141 011 procedimentos, 574 115 contratos,
  topo 23/01/2025) não mexeram. Não é atraso — é lacuna, com critério de
  selecção desconhecido.
- Total de procedimentos: 141 011 desde jan/2020 (o radar apanhou 65 819 só
  em 2 anos de parte L; os números deles não batem com cobertura completa).

### C. Dados e modelo

- **A ficha do procedimento é o anúncio do DR tal e qual**: as 17 secções
  numeradas em acordeão — a mesma estrutura que o radar guarda em
  `anuncios.texto`. Entidade com NIF e email; cronologia Publicação →
  Clarificações → Propostas → Fim com **contagem decrescente ao segundo**;
  "Plataforma de acesso" como link; tipo de contrato.
- **"Documentos" é só o PDF do anúncio do DR.** Não trazem peças.
- Entidades: texto, não ficha — sem página de entidade, sem agrupamento
  visível. Não verificado se por NIF ou nome.
- CPV: não existe como filtro na lista; no "Meu govgo" há "áreas de
  trabalho/CPV" que são ~40 ícones de sector (taxonomia própria).

### D. Filtros, alertas e triagem

- Filtros: localização, estado (Aberto / A Findar / Fechado), valor, data de
  publicação, adjudicante, data limite; caixa "Procurar" de texto livre.
- Até **6 filtros de pesquisa personalizados** guardados.
- Alertas por email com 3 toggles: novos anúncios da área; **alteração ou
  anulação de procedimentos dos favoritos**; aproximação da data final.
  Prazo "A findar" configurável (5 dias por omissão).
- Triagem: favoritos (estrela). Sem estados, sem kanban, sem notas.

### E. IA

Comunicados de 2024 dizem que integraram IA; **no painel não se encontrou
nenhuma funcionalidade de IA**. Não verificado onde vive.

### F–H. Dashboards, saída, UX

- Dashboard: números de 7 dias, mapa/radar por região, calendário, favoritos,
  últimos alertas. Simples e legível.
- Exportações: não encontradas. API: não vista.
- Português correcto, datas DD/MM/AAAA, interface rápida. O melhor UX dos
  quatro em simplicidade; o pior em profundidade.

### I. Presença no mercado

VIPA: **zero contratos** como fornecedora do Estado no corpus. Financiamento
não conhecido; notícias de lançamento em 2023 (ECO, Jornal Económico).

---

## SpotGov (Augusta Labs) — a ameaça a prazo

**Observado a 30 de agosto de 2026**: site público spotgov.com + demo guiada
Navattic (desbloqueada pelo Afonso). **A demo é o caminho feliz deles em
capturas interactivas — nada do que envolve IA foi medido ao vivo.**

### A. Entrada e posicionamento

- "A Solução de IA para Contratação Pública — ganhe mais concursos em menos
  tempo", processo inteiro: deteção → análise → proposta → gestão. Alvo
  claramente enterprise ("as empresas com maior faturação pública nacional",
  logos por sector quase todos ENTERPRISE; testemunho da Palex).
- Números declarados (deles): clientes faturaram €1,5B+ no último ano;
  ~25 h/utilizador/semana poupadas; 99% retenção; ROI >10×.
- **Preços sob consulta**, subscrição 6/12 meses, planos Standard e Plus
  (Plus junta revisão + contestação de propostas).
- Empresa: Augusta Labs, fundada jan/2024 (Rodrigo Fernandes, João
  Cerejeira), **seed a avaliação de 50 M€ em jun/2026**, investidores dos
  unicórnios PT (Bento/Sword, Mónica/Anchorage, Rosado/OutSystems,
  Sebastião/Feedzai). 40+ pessoas. O site apresenta "João Alves, CEO" —
  discrepância com as notícias, não resolvida.

### B. Fontes e cobertura (declaradas + demo)

- FAQ: "assim que a publicação é realizada no DR este fica automaticamente
  disponível, assim como o site onde a publicação se encontra (Vortal,
  AcinGov, AnoGov, etc.)" — **o mesmo desenho de fontes do radar**.
- Declaram cobertura de ajustes directos e consultas prévias, PT+ES+"qualquer
  país sob pedido". A demo tem filtro por **Platform**.
- Paridade: **não testável** — a demo é estática.

### C. Dados e modelo (demo)

- Ficha com critérios de adjudicação **com pesos** (Preço 40%...), prazo de
  execução, renovável s/n, links para DR e AnoGov, entidade com NIPC e
  contactos. Dados de fundo reais (IP, EPAL, ULS).
- Market Intelligence com **Winner, nº de Competitors e Price por contrato**;
  Past Tenders com filtros Has announcement / Competitors / Winners.
- **Pipeline Radar**: renovações previstas (contratos em execução a
  aproximar-se do fim), gráfico mensal, watchlist — igual em conceito à
  Previsão de Contratos da Armilar.

### D. Filtros e triagem (demo)

- Include/Exclude keywords, **Search in Documents**, CPVs, entidades, preço,
  localização, pesquisa em linguagem natural ("Search with AI").
- **Kanban** (Phases/Table/Timeline) com **soma de valor por coluna**,
  etiquetas, **atribuição a utilizadores**, dias restantes por cartão.
- Tender Radar: pesquisas guardadas monitorizadas, colunas configuráveis,
  Export, coluna "Visto".

### E. IA (demo + declarado)

- Análise por categorias + **chatbot sobre as peças** com selector de
  documento e "Uploaded Docs" (juntar documentos próprios). Resposta da demo
  com datas concretas e DPIA — pré-gravada, não verificável.
- Declarado: **previsão do preço vencedor (BETA)** com intervalo de confiança
  de 80%; geração de rascunho de proposta (BETA) a partir de vencedoras
  anteriores; **revisão de propostas de concorrentes para contestação**.
- **Proposal Revision** (demo): checks automáticos de conformidade da
  proposta contra o CE — cartões com 1 958 checks, Compliant/Pending/
  Non-Compliant, % comentários resolvidos.

### G–H. Saída e UX

- Export nas listas; declarado: sincronização com CRM/ERPs ("sincronize
  qualquer workflow"). Interface em **inglês** com títulos PT traduzidos
  automaticamente — para um utilizador português é um passo atrás.

### I. Presença no mercado

Zero contratos como fornecedor do Estado no corpus. A ronda e os investidores
(acima) são a notícia relevante: é o único dos quatro com capital para
contratar depressa.

---

## Tendios Bid — `bid.tendios.com`

**Observado a 29 de agosto de 2026**, com a conta do Afonso (Noptis),
**plano gratuito**. Empresa espanhola; `tendios.com` é o site público.
**Reverificado a 30/08** — confirmações e agravamentos no fim da secção.

### O que é, em números

| | |
|---|---|
| Licitações indexadas | 13 491 905 |
| Adjudicações | 9 764 471 |
| Contratos menores | 4 563 996 |
| Entrada diária | +8 048 concursos / +6 049 adjudicações em 24h |
| Directório de empresas | 1 525 679 |
| Directório de organismos | 295 025 |
| Directório de CPVs | 9 454 |

Multi-país, com Espanha à cabeça — o topo dos organismos é todo
espanhol (Entidades Locales, Andalucía, Ayuntamientos). Portugal é
mercado secundário, e nota-se.

### Preços

| | Lite | Pro | Business | Advanced | Enterprise |
|---|---|---|---|---|---|
| €/mês | 5 | 37 | 168 | 345 | 589 |
| Utilizadores | 1 | 2 | 3 | 4 | 7 |
| Alertas | 1 | 2 | 3 | 4 | 5 |
| **Histórico** | **3 meses** | **6 meses** | **2 anos** | **4 anos** | personalizado |
| IA | — | sim | sim | sim | sim |
| Análise | — | — | básica | avançada | avançada |
| Automações / Integrações | — | — | — | — | sim |
| Gerador de proposta | — | — | — | 5/mês | ilimitado |

**O histórico é vendido a peso.** Quatro anos custam 345 €/mês, ou
4 140 €/ano. O radar tem o acervo de dois anos re-obtível e 1,36 milhões de
contratos desde 2020 em disco, sem mensalidade. E cinco alertas é o
tecto do plano de 589 €; os do radar não têm tecto.

Para referência: a Armilar que isto substitui custa 200 €/mês.

### A fonte deles não é o jornal oficial — são quatro fontes

O separador *Fontes* de cada ficha nomeia a origem e a hora da última
revisão. Em Portugal:

| Fonte | O que é | Revista a |
|---|---|---|
| `EU_TED` | Jornal Oficial da UE | 02:12 |
| `PT_DDR_CPO` | Diário da República | 10:00 |
| `PT_BG_CPO` | Portal BASE | 11:01 |
| `GLOBAL_VORTAL` | plataforma Vortal | 14:48 |

O radar corre às 09:00 — apanha o DR **antes** deles.

**O que a Vortal traz e o DR não:** consultas preliminares de mercado e
contratos menores. Na primeira página da pesquisa apareciam duas
"Consulta preliminar" da ULS de Santo António; `titulo LIKE '%Consulta
preliminar%'` na base do radar dá **zero**. São o sinal mais precoce que
existe — meses antes de haver concurso.

Isto **não contradiz** o que o CLAUDE.md diz sobre o BASE: continua a ser
verdade que o dump do IMPIC não traz anúncios novos, e eles também não o
usam para isso. O que muda é a frase "não há segunda fonte de anúncios":
**há, e são as plataformas** — as mesmas de onde o `obter_documentos()`
já descarrega peças. Não é decisão tomada; é premissa que mudou.

### Onde se partem — três defeitos encadeados, com prova

**1. O mesmo concurso está lá duas vezes.** Ordenando a pesquisa por data
de publicação, apareceram lado a lado:

| | ficha A | ficha B |
|---|---|---|
| Referência | `12025626` | `21792/2026` |
| Título | Fornecimento de sensores para medição de oximetria… | o mesmo |
| Orçamento | 56 013,2 € | 56 013,2 € |
| Fontes | Vortal | TED + DR + BASE |
| Documentos | **Programa e CE, Anexo I, ESPD** | anúncio do DR + 3 ficheiros TED |

UUIDs diferentes, dois registos. **Quem abrir a ficha B não vê as peças.**

**2. A causa está na identidade da entidade.** No directório de
organismos, "São José":

| Nome | NIF | Em dia | Adjudicações |
|---|---|---|---|
| Unidade Local de Saúde de São José, **E. P. E.** | 508080142 | 3 | 6 137 |
| Unidade Local de Saúde de São José, **EPE** | 508080142 | 9 | 1 831 |

**Mesmo NIF, duas entidades.** Uns pontos no "E.P.E." partem a entidade,
e com ela partem-se os concursos, os filtros e as estatísticas. A ficha
da Vortal ligou-se a uma, a do DR à outra.

**3. E propaga-se aos painéis.** Top-5 adjudicatários do segmento de
telecomunicações: MEO 52, Vodafone 42, NOS 40, **"1 - MEO - SERVIÇOS DE
COMUNICAÇÕES E MULTIMÉDIA, S.A." 19**, CTT 15. A MEO ocupa dois lugares
do top-5; juntas seriam 71 e a leitura do mercado é outra.

O mais curioso é que eles **têm** a solução: o directório de empresas
agrupa por NIF em "grupos de organizações" (a Medtronic Portugal aparece
com "16 empresas do grupo", cada uma com o seu NIF). Mas os painéis
agrupam por nome. É incoerência interna deles.

> Isto valida directamente a regra do CLAUDE.md — *"O nome não é a
> identidade de uma entidade: o NIF é"*, `chave_entidade()`, nunca
> agrupar por `adjudicante` nem `a.nome`. Aqui está o custo de fazer ao
> contrário, medido num produto pago.

### A IA deles não lê as peças

A Vera é o assistente. Abre em painel lateral **com o contexto da ficha
carregado** (chip removível "Contexto: 12025626 · Fornecimento de
sens…"), com abas *Chat* e *Conhecimento* e sugestões contextuais.
Duas perguntas, ambas com ~90 s de espera:

**"Quais são os critérios de adjudicação?"**
> "De momento, não foi possível extrair automaticamente o detalhe dos
> critérios de adjudicação a partir das peças do procedimento… Recomenda-se
> a consulta direta do documento **Programa e CE 12025626.pdf**."

**"Qual é o prazo de entrega previsto no caderno de encargos?"**
> "Não é possível extrair automaticamente o prazo exato… **a partir dos
> documentos indexados do procedimento**. Pelo título da licitação, o
> fornecimento está previsto decorrer durante 2026…"

A segunda é pior do que nada: **inferiu do título**. A expressão
"documentos indexados" explica a coisa — o PDF está listado na ficha mas
não entra no índice de leitura.

Não é acidente daquele concurso: na *Visão geral* de um segmento, o
gráfico **"Evolução dos critérios de adjudicação" diz "Sem dados
disponíveis"**. O campo existe no modelo deles e está vazio para Portugal.

**Ressalva honesta:** conta gratuita, com "Análise" bloqueada. Pela
tabela de preços a IA começa no Pro (37 €). A Vera respondeu — logo tem
acesso — mas não se pode garantir que a indexação de peças não seja de um
plano acima. Seguro é: nesta conta não lê o caderno de encargos, e o
gráfico de critérios está vazio por falta de dados de base.

**O `analisar_pecas()` do radar faz exactamente isto, e faz.** É a
vantagem mais defensável que o radar tem.

### Portugal encaixado à força

Sinais de que o modelo é espanhol e Portugal foi acrescentado:

- **Taxonomia de procedimentos espanhola**: *Aberto simplificado
  sumário*, *Contrato Menor*, *Instrução interna de contratação*,
  *Licitação pública*. Não há *ajuste directo* nem *consulta prévia* do
  CCP.
- **Tipos de contrato idem**: *Administrativo especial*, *Gestão de
  Serviços Públicos*, *Patrimonial* — categorias da LCSP.
- **Geografia pobre**: o selector fala de "comunidades, províncias,
  regiões ou municípios"; para Portugal, "Lisboa" devolve **uma** entrada
  do tipo "Cidade". Sem distritos.
- **A pesquisa não ignora acentos**: `Sao Jose` → *nenhum órgão
  encontrado*; `São José` → 24.
- **Tradução automática com fugas**: "Avaliações" onde se quer dizer
  adjudicações, "leilões" por concursos, "Oporto, Portugal", CPVs em
  castelhano nos painéis, e um modal que abre com *"¿Queres que a Vera
  te ajude…"*.
- **Encoding partido** nos títulos portugueses: "Aquisi├¦├úo de
  servi├¦os de manuten├¦├úo".

É aqui que uma ferramenta portuguesa dedicada ganha, e sem esforço.

### Onde o radar já está à frente

- **Contagens na árvore de CPV.** A árvore deles é um modal com
  checkboxes e **sem número nenhum** ao lado dos códigos. A do radar diz
  quantos anúncios e quantos contratos há por código, com fonte separada.
- **O "Diretório de CPVs" deles é uma tabela morta** — as linhas não são
  links (confirmado na árvore de acessibilidade) e são os 9 454 códigos
  do vocabulário, exactamente os que o `cpv_dict` já tem.
- **Uma ficha por concurso, com as peças lá dentro.** Ver o defeito 1.
- **Identidade por NIF, coerente em toda a aplicação.** Ver o defeito 2.

### Reverificação a 30/08/2026

- Contadores cresceram ~4 000 num dia (13 495 889) — entrada diária
  plausível face ao declarado.
- **Defeito 2, agravado**: pesquisa pelo NIF 508080142 no directório de
  órgãos → **13 entidades**, incluindo ~9 variantes do Centro Hospitalar
  (Universitário) de Lisboa Central e uma entidade "CHULC + CHULC". A
  caixa até diz "Pesquisar por nome ou NIF" — o NIF está indexado, só não
  agrupa.
- **Defeito 1, reproduzido num anúncio nosso**: "vapor distribuição" → o
  21825/2026 em **duas fichas** ("CP/471/2026" da ULS "E. P. E." com
  limite 16/09 23:59; "21792/2026"-style "21825/2026" da ULS "EPE" com
  limite 16/09 **00:00**). Quem confie na segunda julga ter um dia a menos.
- **Paridade 3/3**: os três anúncios de 28/08 estão lá, com a referência
  do DR como expediente e a data certa — incluindo o 21809 que a Armilar
  não devolve. Na cobertura pura do DR, a Tendios bateu a Armilar.
- Encoding partido visto ao vivo na lista ("Assistência tãđcnica",
  "P.A.N.š169/2026"); onboarding em castelhano ("Primeros pasos en
  Tendios"); "Filtros inteligentes" bloqueados no gratuito.

---

## O que se aprende com eles

Por ordem de valor para o radar. Cada ponto diz o que eles fazem e o que
falta cá. (Itens 1–7 de 29/08, mantidos; a passagem de 30/08 confirmou-os
e acrescentou os seguintes — tudo convertido em itens no `BACKLOG.md`.)

### 1. Incluir e excluir, e escolher como se combina

Na configuração do alerta, **palavras-chave** e **CPVs** têm cada um duas
listas — *Incluídos* e *Excludentes* — em chips. E por baixo, a escolha
de como se combinam, em português claro:

> **OU: Pesquisa mais ampla** — resultados que incluam pelo menos uma das
> palavras-chave ou CPVs
> **E: Pesquisa mais restrita** — resultados que incluam pelo menos uma
> combinação de palavra-chave e CPV

O radar tem `q` e `cpv` em AND implícito, sem exclusões e sem explicação.
As exclusões são o que corta ruído sem perder cobertura — "telecomunicações
mas não obras de instalação". E o par ampla/restrita é a melhor tradução
de lógica booleana para linguagem humana que apareceu nesta observação.
*(30/08: a SpotGov tem Include/Exclude Keywords à cabeça da pesquisa; a
Armilar tem o AND como opção. Três em quatro têm exclusões; o radar não.)*

Onde mexe: `condicoes()`, `CAMPOS_FILTRO`, e o formulário de filtro.

### 2. A "Visão geral" de um segmento

Sobre o filtro de uma lista, com selector de período e de critério de
data, um painel de métricas. As que o radar não tem e que decidem se vale
a pena concorrer:

| Métrica | Exemplo visto | Para que serve |
|---|---|---|
| **Desconto (%)** | mín 0,82 · **méd 20,58** · máx 45,35 | quanto é preciso baixar para ganhar |
| **Número de ofertas** | 1 · **1,59** · 3 | quantos concorrentes há |
| Tempo de resolução | 25 dias · 43 dias · 2 meses | quanto tempo até saber |
| Licitações desertas | 0 | concursos sem propostas = oportunidade |
| Lotes / Licitação | 1,57 | |
| Prazo de submissão | 10 dias | |

**O desconto sai já com o que o radar tem:** `anuncios.preco_base` de um
lado, valor adjudicado no `contratos.db` do outro. É a métrica que passa
o radar de "o que existe" para "vale a pena ir".

O nº de ofertas não sai — o dump do IMPIC não traz o número de
concorrentes. Não prometer o que não há. *(30/08: a Armilar tem-no por
contrato e a SpotGov mostra-o na demo — ambos com dados que o radar não
tem como obter. Mantém-se: não prometer.)*

**Pré-requisito:** o desconto precisa de preço base, que vem do detalhe.
*(30/08: a ligação anúncio→contrato existe no corpus — `n_anuncio` é o
`ref` do radar.)*

### 3. Taxa de acerto por alerta

A ficha de cada alerta mostra quatro números: *Licitações em curso ·
Guardadas · Descartadas · **Taxa de acerto***.

Um alerta que produz 200 avisos e zero guardados está mal afinado, e
nada no radar diz isso hoje. Os dados já lá estão — `anuncios.estado`
cruzado com o alerta que marcou cada um.

### 4. As perguntas às peças como configuração, não como código

O motor de automações tem um passo "Análise de oportunidade" com quatro
acções **editáveis pelo utilizador**. É a arquitectura do
`analisar_pecas()` — um pedido por campo — mas com as perguntas na
configuração e o resultado a cair em campos do quadro. Há ainda uma página
**"Regras para a IA"** — instruções de sistema por conta.
*(30/08: a Armilar resolve o mesmo problema com um chat livre sobre as
peças, e a SpotGov idem + upload de documentos próprios. Duas formas:
campos configuráveis ou chat. O radar não tem nenhuma.)*

### 5. "Incluir modificações" no resumo diário

O e-mail deles inclui **alterações a concursos já conhecidos**, não só
novos. Uma prorrogação de prazo vale tanto como um anúncio novo. Há
também um toggle *"Enviar resumo mesmo que não haja novidades"* —
desligado por omissão, boa escolha. *(30/08: a GovGo — o produto mais
simples dos quatro — também notifica "alteração ou anulação de
procedimentos dos favoritos". Dois em quatro; o radar não.)*

Onde mexe: `enviar_resumo()`.

### 6. Detalhes que valem meia hora cada

- **Ordenar por "Última alteração significativa"** — distinguem alteração
  real de toque no registo.
- **Filtro por data de última actualização**, além de publicação, prazo e
  adjudicação.
- **"Sugerir uma mudança"** no menu da ficha — o utilizador reporta um
  campo mal extraído. Num produto de dados, é a via de correcção mais
  barata que há.
- **Campos não aplicáveis desactivados com explicação** — "Selecione 'Por
  adjudicação' ou 'Por vencimento' para ativar este filtro". É a mesma
  preocupação do `filtro_para()`, resolvida **à entrada** em vez de à
  saída, e fica melhor: avisa antes de o utilizador construir o filtro.
- **Pesquisa na árvore de CPV mantém a hierarquia** — filtra e expande só
  os ramos com resultados, em vez de virar lista plana.
- **Histórico de envios por alerta** ("Expedições") — auditoria do que foi
  enviado e quando.
- **Anexos do resumo configuráveis** — CSV / PDF / JSONL / XLSX, com
  escolha de colunas (53 de 60 disponíveis).
- **Dois campos de valor distintos** no filtro: *orçamento base (sem
  impostos)* e *valor estimado do contrato*. O radar só tem `preco_base`.
- **Âmbito de países como preferência da conta**, não como filtro.

### 7. O que confirma decisões já tomadas

Não é para copiar — é para não voltar atrás:

- **Um só motor de filtros.** A ficha da empresa reutiliza a página de
  pesquisa com `?bidders=<ids>` pré-aplicado. Igual à regra do CLAUDE.md.
- **Um filtro guardado é uma query, e pode ter mais que um papel.**
- **Agrupar por NIF, sempre.** Ver o defeito 2 da Tendios — e agora a
  Armilar a fazê-lo bem: pesquisa por NIF, uma entidade por NIF.
- **Anúncios e contratos são coisas diferentes.** Eles misturam-nos no
  mesmo separador com um chip de estado, e daí vem metade da confusão de
  vocabulário. A Armilar mistura também. A GovGo separa — e é o produto
  mais legível dos quatro.
- **As peças na ficha importam.** Armilar e Tendios(fonte Vortal) têm-nas;
  GovGo não tem e sente-se logo. O `obter_documentos()` do radar está no
  sítio certo.
- **A ficha = o texto do DR completo** (GovGo): a decisão do radar de
  guardar `anuncios.texto` e derivar tudo dele é a mesma que eles tomaram.

### Novo a 30/08 — o que só se viu nas outras três

- **8. Contratos a terminar = oportunidades de renovação** (Armilar
  "Previsão de Contratos", SpotGov "Pipeline Radar"). Os dois produtos
  mais caros têm-no como módulo de primeira linha. O radar tem a
  matéria-prima no `contratos.db`: `data_celebracao + prazo_execucao` dá o
  fim estimado; filtrar por CPV dá "o que vai renovar no teu mercado".
- **9. Histórico do procedimento anterior à distância de uma pesquisa**:
  na Armilar, a pesquisa do concurso da ULS devolveu ao lado o CP/1025/2024
  da mesma entidade com o mesmo objecto — o valor de 2024 (30 381 €) ao pé
  do de 2026 (122 040 €) conta uma história que decide propostas. A SpotGov
  chama-lhe "analise edições passadas".
- **10. Fontes com número de página** na leitura por IA (Armilar): cada
  secção do resumo aponta para o PDF e a página. O radar guarda fontes por
  campo mas sem página.
- **11. Soma de valor por coluna do kanban** (SpotGov): o quadro diz
  quanto dinheiro está em cada fase do funil.
- **12. Pesquisa full-text nas peças** (Armilar "Incluir documentos PDF na
  pesquisa"; SpotGov "Search in Documents"): o radar extrai o texto das
  peças e depois só o usa para a leitura por modelo — não se pesquisa nele.

---

## Matriz comparativa (30/08/2026)

✅ tem e funciona · ⚠️ parcial/limitado · ❌ não tem/não visto

| Capacidade | Armilar | GovGo | SpotGov* | Tendios | Radar |
|---|---|---|---|---|---|
| Cobertura DR (paridade 28/08) | ⚠️ 2/3 | ❌ 0/3 | — n/testável | ✅ 3/3 | ✅ é a fonte |
| Frescura face ao DR | ⚠️ diária, falhas | ❌ lacunas grandes | — | ✅ mesmo dia (10:00) | ✅ 09:00/17:00 |
| Consultas preliminares/menores | ✅ via Vortal | ❌ | ✅ declarado | ✅ via Vortal | ❌ parte L não tem |
| Peças do procedimento na ficha | ✅ | ❌ só PDF do anúncio | ✅ demo | ⚠️ só ficha "fonte Vortal" | ✅ 4 plataformas |
| IA lê as peças de facto | ✅ testado | ❌ invisível | ⚠️ demo, não medido | ❌ nesta conta não | ✅ 3 campos + fontes |
| Perguntas livres às peças | ✅ Q&R <20 s | ❌ | ⚠️ demo | ⚠️ Vera responde mas não lê | ❌ perguntas fixas no código |
| Identidade de entidade por NIF | ✅ | ⚠️ NIF mostrado, sem ficha | ⚠️ NIPC na ficha | ❌ 13 entidades/1 NIF | ✅ chave_entidade() |
| Contratos celebrados (corpus) | ✅ desde ≥2014 | ⚠️ 574 k, parado em 01/2025 | ✅ desde 2014 declarado | ✅ 9,7 M multi-país | ✅ 1,36 M 2020–26 |
| Desconto / nº licitadores | ✅ ambos | ❌ | ✅ demo | ⚠️ desconto por segmento | ❌ desconto calculável; licitadores sem fonte |
| Contratos a terminar (renovações) | ✅ módulo próprio | ❌ | ✅ Pipeline Radar | ❌ | ❌ calculável do corpus |
| Exclusões na pesquisa | ⚠️ AND opcional | ❌ | ✅ include/exclude | ✅ chips incl/excl | ❌ |
| Pesquisa full-text nas peças | ✅ opção | ❌ | ✅ demo | ⚠️ nos docs indexados | ❌ texto existe, não se pesquisa |
| Alertas — canais e afinação | ⚠️ 3 momentos/dia | ⚠️ email, 3 tipos | ⚠️ demo | ✅ mais completo | ⚠️ email 1×/dia |
| Notifica alterações/anulações | ❌ não visto | ✅ dos favoritos | ⚠️ declarado | ✅ no resumo | ❌ |
| Kanban / triagem | ⚠️ tarefas | ❌ só favoritos | ✅ fases+valor+pessoas | ✅ | ✅ quadro+estados+etiquetas |
| Árvore CPV com contagens | ❌ modal simples | ❌ sem CPV real | ⚠️ campo CPV | ❌ tabela morta | ✅ com 2 fontes |
| Exportações | ✅ CSV+Excel | ❌ não vistas | ✅ demo | ✅ configuráveis | ✅ 2 CSV |
| Preço | sob consulta (~200 €/m) | 50 €+IVA/sem | sob consulta | 5–589 €/m | 0 € |
| Português correcto | ✅ | ✅ | ❌ interface EN | ❌ ES com fugas | ✅ |

\* SpotGov avaliado por demo guiada + declarações; nada de IA foi medido ao
vivo.

## Onde o Radar ganha hoje

- **Cobertura e frescura do DR.** É a fonte primária às 09:00: 3/3 no teste
  inverso contra qualquer um deles; a Armilar falhou 1 em 3, a GovGo os
  três. Nenhum dos quatro é auditável quanto ao que lhes falta — o radar é
  (entra tudo, sem filtro à entrada).
- **A leitura das peças por modelo, com fontes.** Só a Armilar faz
  comparável — a 200 €/mês, e sem os campos estruturados na ficha (equipa,
  documentos da proposta, PAB por extenso). A Tendios não lê; a GovGo não
  tem; a SpotGov não é verificável sem comprar.
- **Identidade por NIF em todo o lado** — a Tendios mostra o custo de não o
  fazer (13 entidades num NIF), e nos painéis dela a MEO conta duas vezes.
- **O corpus de contratos completo e local**: 1,36 M contratos 2020–2026,
  refeito quando se quiser, com SQL à mão. A GovGo tem menos de metade e
  parada em jan/2025; a Tendios vende 4 anos por 4 140 €/ano.
- **Árvore de CPV com contagens por fonte** — nenhum dos quatro tem.
- **Custo e controlo.** 0 €/mês, dados no disco, sem tecto de alertas, sem
  histórico a peso, sem dependência de conta.
- **Português de Portugal e taxonomia do CCP** — contra ES-com-fugas
  (Tendios) e interface EN (SpotGov).

## Onde o Radar perde hoje

- **Sinal precoce**: consultas preliminares e contratos menores das
  plataformas não passam pela parte L — Tendios/Armilar/SpotGov vêem-nos,
  o radar não. (Premissa registada; implementação é decisão do Afonso.)
- **Inteligência de adjudicação por concurso**: a Armilar mostra desconto
  estimado, potenciais concorrentes com taxa de sucesso e o procedimento
  homólogo anterior na própria ficha. O radar tem os dados para metade
  disto (desconto, homólogos) e não o calcula.
- **Renovações**: dois dos quatro tratam "contratos a terminar" como
  módulo de primeira linha; o radar tem o corpus e não responde à pergunta
  "o que vai renovar no meu CPV?".
- **Exclusões e combinação E/OU nos filtros** — três dos quatro têm; o
  radar só faz AND implícito sem exclusão.
- **Alterações a concursos conhecidos**: prorrogações e rectificações não
  geram aviso nenhum no radar; Tendios e GovGo avisam.
- **Perguntas livres às peças**: o Q&R da Armilar responde a qualquer
  pergunta em <20 s; no radar, uma pergunta nova é uma alteração ao
  `radar.py`.
- **Pesquisa dentro das peças**: o texto extraído existe em disco e não é
  pesquisável.
- **Multi-utilizador a sério** (atribuição, permissões, comentários) — o
  radar tem `responsavel` e pouco mais; SpotGov e Tendios têm equipas.
  (Relevância baixa enquanto isto for de 1–2 pessoas.)
