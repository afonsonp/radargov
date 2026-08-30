# SpotGov — demo interactiva Navattic (30/08/2026)

Percorrida depois de o Afonso desbloquear o gate de email. **É o caminho feliz
escolhido por eles** — capturas de ecrã interactivas (Navattic), não a
aplicação viva: tempos de resposta e correcção do conteúdo IA não são
verificáveis aqui. Interface em **inglês**, com títulos dos concursos
portugueses **traduzidos automaticamente** ("Acquisition of Arthroscopy Tower
for PRR"); dados de fundo reais de Portugal (IP, EPAL, ULS, municípios).

## Estrutura da aplicação (vista no tour de 11 passos)

Sidebar: DETECTION AND ANALYSIS (Active Tenders, Tender Radar) · MANAGEMENT
(Saved Tenders, Notifications) · MARKET INTELLIGENCE (Market Intelligence,
Past Tenders, Pipeline Radar) · APPLICATION (Proposal Revision).

- **Active Tenders**: pesquisa em linguagem natural ("Search with AI") +
  Advanced Options: Include/Exclude Keywords, **Search in Documents**
  (full-text nas peças), Search with CPVs, Entities, Base Price, Publication,
  Location, país (Portugal). Pesquisas anteriores guardadas com badge AI/KW.
- **Tender Radar**: pesquisas guardadas como tabela monitorizada — filtros
  Searches/CPV/Entities/Interest/Country/**Platform**/Base Price, colunas
  configuráveis (**Add column**), **Export**, coluna "Visto" (toggle) e
  Interest (Save), dias restantes.
- **Saved Tenders**: **kanban** (Phases/Table/Timeline) com colunas
  personalizadas; cada coluna mostra **nº de contratos e soma do valor**
  (ex.: "11 contracts · 11 424 735,87€"); etiquetas (Low Priority, Urgent),
  **atribuição a utilizadores**, dias restantes/deadline expired por cartão,
  Export, filtro por Label/User/Country.
- **Market Intelligence**: "Competitors Activity" — empresas monitorizadas
  (watchlist), tabela com Winner, **Competitors (nº)** e Price por contrato;
  pesquisa de qualquer empresa ou entidade.
- **Past Tenders**: histórico com Include/Exclude, Search in Documents, CPVs,
  Entities, Base Price, Publication, Location, **Has announcement**,
  **Competitors**, **Winners**, Type.
- **Pipeline Radar**: "Contracts in execution approaching renewal date" —
  gráfico de renovações por mês (total mostrado: 112 910 contratos, 33,6
  mM€), filtros incl. Renewal date/Winner/Competitor/CPV, ordenação "Nearest
  renewal", abas Contracts/Top Entities/Top Winners, **Watchlist** por
  contrato, Export. (Mesmo conceito da "Previsão de Contratos" da Armilar.)

## AI Analysis (percurso dedicado)

Ficha do concurso (exemplo real: "BIA — AI Bot for Public Procurement" da
Infraestruturas de Portugal, ref 10021989) com: Analyze with AI; tabela de
análise por categorias (Contractual Object detalhado — objecto, âmbito,
local, prazos); "Default Docs / **Uploaded Docs**" (o utilizador pode juntar
documentos); Export; **Award Criteria com pesos** (Preço 40%...); Useful
Links para o **Diário da República e AnoGov**; Execution Deadline; Renewable
(sim/não); entidade com **NIPC**, morada, email, telefone.

Vista "Analysis": PDF das peças à esquerda (selector de documento "Terms of
Reference"), **chatbot** à direita ("Clarify your doubts..."). A pergunta
guiada da demo ("delivery deadlines + DPIA") devolve resposta estruturada com
datas concretas (13/06, 30/07, 30/08, 26/10/2026, execução 6 meses, DPIA
obrigatório, RGPD) — **resposta pré-gravada da demo, não medida ao vivo**.

## Proposal Revision (percurso dedicado)

Organizado pelas fases do kanban (Saved/Under Review/Reviewer/Submitted/
Lost). Cartão por revisão com: ficheiros carregados, **Total Checks** (ex.:
1 958), repartidos **Compliant / Pending / Non-Compliant** (ex.: 240 / 0 /
1 718), "% Resolved Comments", View Revision / View Contract. Fluxo "Start
Revision" por contrato guardado. (Declarado no site: também analisa propostas
de concorrentes para contestação.)

## Leitura para o radar

O SpotGov é o concorrente **funcionalmente mais próximo do topo**: cobre o
funil inteiro (deteção→análise→proposta→gestão) com IA transversal. O que a
demo NÃO mostra: preços (sob consulta), tempos reais da IA, qualidade da
extracção em documentos difíceis, comportamento com contas reais.
