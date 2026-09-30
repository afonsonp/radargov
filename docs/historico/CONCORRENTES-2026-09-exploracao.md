# Concorrentes, segunda passagem — a exploração por dentro (30/09/2026)

> Relatório escrito pelo agente que navegou nas contas do Afonso, no Chrome dele, na manhã de 30/09/2026. É a prova da adenda 2 do `CONCORRENTES-2026-09.md`; como todo o `docs/historico/`, não se edita. O texto abaixo é o dele, tal como veio (a numeração e a tabela são as originais).

# Relatório de exploração — plataformas de concursos públicos

**Data:** 30/09/2026 (manhã) · **Método:** navegação real nas contas abertas no Chrome (Armilar, Tendios Bid, Adjudica, SpotGov demo Navattic, TRINTA site) · **Regra seguida:** só leitura; nada criado ou alterado, exceto o que se indica em "Notas de auditoria" no fim.

**Contas usadas:** Armilar (conta "Public Sector / Conkord PT"; a plataforma marca "Readiness IT, Systems Integration, SA" como "a sua empresa"), Tendios Bid (plano Freemium, empresa Noptis, Sistemas de Comunicações, Lda), Adjudica (conta nova, onboarding por concluir), SpotGov (demo pública Navattic, sem conta), TRINTA (só site de marketing; não há conta nem demo interativa).

---

## 1. ARMILAR (business.armilar.biz)

### 1.1 Estrutura
Menu "Meus Serviços" (topo): Previsão de Contratos · Previsão de Projectos · Gestor de Oportunidades · Informação de mercado (benchmarker) · Mais Oportunidades (redireciona para login em community.vortal.biz) · Preços de mercado · Consultor Dedicado (landing de suporte premium) · Dashboard.

Dashboard: três cartões com toggle 6/12 meses — Previsão de Contratos (nº contratos a terminar; volume acumulado; ambos "0" e a carregar durante mais de um minuto), Gestor de Oportunidades (548 oportunidades disponíveis, 806 688 300 €), Informação de mercado (adjudicações).

Gestor de Oportunidades (menu lateral): Visão Geral · Meus Interesses · Alerta de Negócios · As minhas oportunidades · Gestor de tarefas · Notificações.
- Visão Geral: Alerta de Negócios 451 ativas / 467 573 280 €; Minhas oportunidades 229 no total, 2 em curso, 0 adjudicadas; Tarefas: 0 em curso, 35 atrasadas, 78 concluídas.
- Meus Interesses: tabs Tudo/Em curso/Expiradas/Adjudicadas; pesquisa por referência/descrição; "Incluir todas as palavras"; "Incluir documentos PDF da oportunidade na pesquisa" (pesquisa full-text nas peças); vista tabela/cartões; exportar CSV. Estava vazio.
- Alerta de Negócios (=motor de pesquisa): 11 490 400 oportunidades na base. **Sem filtro de país, a lista abre com Espanha** (Aena, ayuntamientos) — para uma PME portuguesa a primeira página é inútil.
- Cartão de resultado: estado (Publicado / Adjudicado / Formalizado), título, REF, comprador, local de execução, categoria CPV, data de publicação, data limite (com hora), preço base; ou data e preço de adjudicação. Ícone clip = tem documentos. **Ícone de aviso com tooltip "Atenção: esta oportunidade sofreu modificações na fonte desde que foi originalmente publicada"** — deteta alterações. Ações: favorito, marcar como lido, "Adicionar às minhas oportunidades", Detalhe.

### 1.2 Ficha de um concurso (op. 19004043 — "Anúncio de procedimento n.º 24122/2026", APS Sines, ref. FAP.PR.26.005)
Campos, por ordem no ecrã:
- Cabeçalho: nº do anúncio DR; estado (Publicado); "Tem Lotes: Não" (com contagem).
- Entidade Gestora (nome + NIF) · Entidade Contratante (nome + NIF).
- Descrição (com "Ver mais").
- Ações: favorito, copiar link, marcar não lido, **"Link da fonte"** com 3 URLs: documentos públicos Vortal, **diariodarepublica.pt/dr/detalhe/anuncio-procedimento/24122-2026-…**, contract-notice-view Vortal.
- Informações do Procedimento: Referência do Procedimento · Tipo de Procedimento (Concurso Público) · Tipo de Contrato (Leasing de Bens) · Preço Base (190 000,00 €) · Data de Publicação (29/09/2026) · Última atualização da fonte (29/09/2026) · Prazo de apresentação de propostas "(No seu Fuso Horário)" (14/10/2026 22:59) · Duração Prevista do Contrato (1461 dias) · Renovações Permitidas (Não) · Financiado pela UE (Não) · Adequado a PME (Sim) · Local de Execução (Sines) · Categorias CPV (34115200-8 + descrição).
- Critérios de Adjudicação: Adjudicação Multifator (Não) · Fator (Preço) · Ponderação (100%).
- Insights (demorou ~30 s; mensagem "A tentar obter Insights com um intervalo geográfico maior…"): % Desconto estimado (8,11%) · Nº potencial de participantes (9) · Participações próprias semelhantes 12M (0) · Adjudicações próprias 12M (0) · tabela POTENCIAIS CONCORRENTES (nome com link para ficha, NIF, Desconto Médio, Taxa de sucesso média, Adjudicações com a Entidade, Última Atividade): KINTO 15,73% / 17% / 21-09-2026; HR Aluguer 0,89% / 26%; Onda Predileta 11,24% / 16%; Toyota Caetano 4,26% / 28%; Readiness IT ("A sua empresa") 0 / — / N/D. Botão "Insights detalhados".
- Documentos: "Gerar resumo da oportunidade" + tabela (Nome do Ficheiro, Data de Publicação, Tipo): CE.Cláusulas Gerais.pdf, Programa.Procedimento.pdf, CE.Cláusulas Técnicas.pdf, FAP.26.005.Anuncio.DRE.pdf, 419974145.pdf; "Descarregar Todos".

**Ligação ao DR: sim (URL direto). Peças: sim, descarregáveis, com o anúncio DR em PDF.**

### 1.3 Leitura por IA ("Gerar Resumo")
- Clique ~06:49; mensagem "A geração do Resumo pode levar alguns minutos. Avisá-lo-emos assim que estiver disponível"; resumo gerado às 06:50 → **≈1–2 minutos**. Depois aparece "Ver resumo gerado".
- Página do resumo: "Versão 1 - 30/09/2026 06:50" (versionado), cabeçalho com entidade, publicado em, prazo, preço base, "Documento(s): CE.Cl_usulas Gerais.pdf" (lista só 1 dos 5 ficheiros).
- Secções: VISÃO GERAL · DATAS IMPORTANTES · CRITÉRIOS DE AVALIAÇÃO E DE ADJUDICAÇÃO · GARANTIAS E PENALIDADES · PLANOS DE PAGAMENTO · "Q&R com IA — Deve verificar as informações antes de as enviar."
- **Cita documento e PÁGINA:** cada secção termina com "Fonte:" + ficheiro + números de página (ex.: `4b6b5594…(...).pdf 3, 7, 8, 9, 10 (+3)`; `affaf964…(...).pdf 1, 3, 4, 5, 6`; `3f50efa3…(...).pdf 1, 2, 3`). **Mas o nome do ficheiro é um hash**, não "Programa.Procedimento.pdf" — o utilizador não sabe qual é qual.

Texto tal como aparece (excertos literais):
> **VISÃO GERAL** — "O projeto consiste na locação de seis viaturas em regime de aluguer operacional de viaturas (AOV), conforme especificações técnicas indicadas no Caderno de Encargos do processo administrativo FAP PR26.005, assegurando o cumprimento das obrigações legais relativas à proteção de dados, segurança da informação e normas de segurança, ambiente e proteção estabelecidas nas cláusulas contratuais aplicáveis. - O número identificador do procedimento é PR26.005 (…) - A entidade que pretende contratar (…) é a APS - Administração dos Portos de Sines e do Algarve, S.A., localizada na Rua do Porto Industrial, em Sines. Os contactos (…) telefone (+351) 269 860 600, o fax (+351) 269 860 690 e o endereço eletrónico geral@apsinesalgarve.pt. As peças do procedimento estão disponíveis na plataforma eletrónica Vortal (…) - O local de execução do projeto é em Portugal, na NUT III PT1C1 - Alentejo Litoral, especificamente na Freguesia de Sines, Concelho de Sines, Distrito de Setúbal. - O preço base do projeto é 190.000 euros, sem IVA (cfr. página 1). - O CPV associado ao projeto é **34115200 - Veículos a motor para o transporte de menos de dez pessoas** (…) - O tipo de contrato é "Locação de Bens Móveis" (…) seguro com cobertura de danos próprios com franquia de 2% e capital de ocupantes de 30.000 €, com pagamentos mensais durante 48 meses (…)"
>
> **DATAS IMPORTANTES** — "- Com base nas informações fornecidas, a decisão de contratar foi tomada no dia **29-09-2026**, conforme indicado no anúncio de procedimento n.º 24122/2026. - O prazo para os esclarecimentos é até ao fim do segundo terço do prazo fixado para a apresentação das propostas. - O prazo para a submissão das propostas é até às 23:59 horas do dia 14 de outubro de 2026. - (…) não é mencionada explicitamente a data de abertura dos envelopes. Contudo, é indicado que o prazo para apresentação das propostas é até às 23:59 horas do 15.º dia a contar da data de envio do anúncio (…) - (…) a duração total do contrato é de 48 meses (4 anos), a contar da data de entrega das viaturas (…) - O concorrente é obrigado a manter a proposta pelo prazo de 66 dias (…) Além disso, é também obrigado a manter a proposta pelo prazo de conservação do procedimento de concurso, que é de quatro anos a contar da data de celebração do contrato. - O anúncio foi publicado no dia **29 de setembro de 2026**. - A informação fornecida não especifica diretamente o prazo após a assinatura do contrato para a atribuição do trabalho. Recomenda-se consultar (…) - - Entrega das viaturas: prazo de 60 dias. - Início das intervenções de manutenção periódica: no dia da entrega da viatura na oficina. - Início das intervenções de manutenção corretiva: prazo máximo de 48 horas (…) - Disponibilização de viatura de substituição: prazo máximo de 2 horas (…) - Conclusão do processo de legalização dos veículos: na data de entrega. - Entrega da documentação para gestão do IUC (…)"
>
> **CRITÉRIOS** — "As propostas serão avaliadas com base no critério da proposta economicamente mais vantajosa, determinado unicamente pela avaliação do preço, conforme a alínea b) do n.º 1 do artigo 74.º do Código dos Contratos Públicos (CCP). Não são admitidas propostas variantes. Em caso de empate entre as propostas mais vantajosas, a adjudicação será decidida por sorteio realizado pelo Júri, na presença de um representante de cada concorrente que deseje estar presente. O sorteio ocorrerá nas instalações da Entidade Adjudicante, em local, data e hora a designar com uma antecedência mínima de 2 dias. Não são mencionados sistemas de pontuação, fórmulas ou pesos adicionais no contexto fornecido." Fonte: affaf…pdf 8; 3f50…pdf 3; 4b6b…pdf 7.
>
> **GARANTIAS E PENALIDADES** — "(…) Nos termos da Cláusula 17.ª, se houver responsabilidade do adjudicatário, o montante correspondente será deduzido das quantias devidas (…) conforme indicado na Cláusula 15.ª, não há lugar à prestação de cauções. (…) seguros obrigatórios (Cláusula 4.9.2), proteção de dados (Cláusula 23.ª) e segurança da informação (Cláusula 24.ª) (…) 1. **Penas pecuniárias por incumprimento**: A APS pode exigir ao locador o pagamento de até 2% do valor global do contrato por cada dia útil de incumprimento, com um limite máximo de 20% do valor contratual. 2. Critérios para avaliação da gravidade (…) 3. Compensação de pagamentos (…) 4. Indemnização por danos excedentes (…) 5. Substituição de viaturas em caso de perda ou destruição total: (…) prazo máximo de 30 dias (…) 6. **Seguro de recondicionamento**: Em caso de danos na devolução das viaturas, aplica-se um custo de reparação no valor de €500,00 por veículo. Estas penalidades estão em conformidade com o CCP (…)" Fonte: 4b6b…pdf 10, 11, 12, 14, 15; affaf…pdf 1, 8; 2ba21…pdf 9, 10.
>
> **PLANOS DE PAGAMENTO** — "Os pagamentos do projeto são mensais, totalizando 48 prestações, efetuadas no prazo máximo de 30 dias após a receção da fatura eletrónica. O valor total do contrato não pode exceder €190.000,00 (acrescido de IVA), correspondendo a €31.666,67 por viatura para um período de 48 meses e 80.000 km. (…) Não há lugar a adiantamentos, e em caso de atraso no pagamento, serão aplicados juros de mora à taxa legal." + dois bullets que repetem o mesmo parágrafo.

Avaliação (sem acesso aos PDFs; comparação apenas com a ficha e com a lógica):
- **Coerente com a ficha:** preço 100%, 190 000 €, 48 meses, publicação 29/09.
- **Incoerências internas:** o resumo diz prazo "até às 23:59 do dia 14 de outubro"; a ficha da própria Armilar diz "14/10/2026 22:59 (no seu fuso horário)". Um bullet diz "acrescido de IVA", outro "incluindo IVA".
- **Suspeitas de invenção/má leitura:** "a decisão de contratar foi tomada no dia 29-09-2026" (é a data do anúncio, não há evidência da data da decisão); "obrigado a manter a proposta pelo prazo de conservação do procedimento… quatro anos" (mistura manutenção da proposta com conservação de documentos); "Estas penalidades estão em conformidade com o CCP" (juízo jurídico não pedido).
- **Qualidade de escrita:** repetitivo (o objeto é repetido 3 vezes; pagamentos 3 vezes), bullets "- -" duplicados, sem separação clara entre o que está nas peças e o que é inferido ("Com base nas informações fornecidas…" aparece 4 vezes).

### 1.4 Alertas e filtros
Pesquisa avançada (que se guarda com "Guardar como filtro" e aparece em "Meus filtros"): texto (referência/descrição) + "todas as palavras" + "incluir PDFs" · Compradores (modal com **pesquisa por Nome ou por NIF**, árvore por região) · Localizações (árvore: ESPANHA, PORTUGAL expansíveis, depois todos os países) · Tipo de Procedimento · Estado da Oportunidade · Data de Publicação de/até · Data Limite de/até · Preço Base de/até · Tipo de contrato · Categorias (CPV). **Não vi campo de exclusões de palavras nem de entidades a excluir.** Frequência: não configurável no ecrã que vi; a plataforma diz "Informação atualizada diariamente". Alterações: **sim** — a lista e a ficha assinalam "sofreu modificações na fonte" e a ficha tem "Última atualização da fonte". Notificações: a página /opportunities/notifications mostrou só o título "Detalhes da Oportunidade" (vazia/bug).

### 1.5 CRM / Pipeline ("As minhas oportunidades" + "Gestor de tarefas")
- Fases (tabs): Tudo · Em análise · Em curso · Proposta Submetida · Em negociação · Inativas. (Na Visão Geral aparecem também "Em curso (ativo)" e "Adjudicadas".)
- Lista: Descrição · Comprador · Localização · Fase · Data Limite · Detalhe. "Criar oportunidade" (manual).
- Campos do formulário "Editar oportunidade": Origem · Assign user (responsável; etiqueta em inglês) · Tipo de procedimento · Data do Contrato · Data da adjudicação · Fase · Referência/Nome · Preço Base · Comprador · Data de publicação · Prazo de apresentação de propostas · Descrição · Categorias · Localizações · Carregar documentos.
- Espaço de trabalho da oportunidade: tabs "Visão geral" (mesma ficha do concurso) e **"Lista de atividades"** com grupos de tarefas pré-definidos: Proposta · Reuniões e validações internas · Documentos de económicos e financeiros (sic) · Documentos Técnicos · Documentos Legais e Administrativos · Avaliação de oportunidade — cada um "0 de 0 tarefas concluídas".
- Gestor de tarefas (global): filtros Minhas/Ativa; colunas Nome · Referência de oportunidade · Responsável · Estado · Prazo limite · Detalhe. Exemplos reais na conta: "Fechar PO", "Fechar Documentação", "Fechar CVs", "Fechar Proposta", "Fechar FO" com prazos de fevereiro de 2026 ainda "Ativa" (35 atrasadas).
- Notas: não vi campo de notas livre. Documentos: "Carregar documentos" na oportunidade.

### 1.6 Mercado ("Informação de mercado" / benchmarker)
- Menu: Visão Geral · Detalhe da Minha Empresa · Análise de Mercado · Empresas seguidas · Minha posição no mercado.
- Visão Geral: Últimos 30 dias 28 697 adjudicações / 3 327 139 220 €; 12 meses 1 023 244 / 104 906 742 512 €; 5 anos 6 601 260 / 401 462 339 770 € (base ES+PT). "Principais Adjudicadores" e "Principais Concorrentes" — "Nenhuma informação encontrada" para esta conta.
- **Ficha de empresa (KINTO PORTUGAL, NIF 502584866):** botão Seguir; tabs Resumo / Contratos Relacionados / Relações; "Pesquisar nos Meus Interesses"; Últimos 12 meses: Nº Contratos Adjudicados 68 · Valor 13 013 184 € · **Desconto Médio 20,35%** · **Média de Participantes 5** · Nº de Ofertas Enviadas 557 · Taxa de Sucesso 12,21%; 24 meses: 96 / 16 195 411 € / 15,73% / 5 / 569 / 16,87%; "Principais Parceiros Comerciais" (INEM 2 adjudicações 2 817 556,83 €; AdP 2 adj. 1 908 049,92 €; …).
- **Previsão de Contratos:** filtro 6/12 meses; "Concorrentes Analisados"; "Próximos a Terminar" com colunas **Probabilidade** · Nome do contrato · Comprador · Fornecedor · Montante · Data estimada de conclusão. Nesta conta: "Dado não mapeado", 0,00 €. Aviso legal: "Nenhuma relação directa é feita em qualquer momento entre um comprador, fornecedor, um produto e um preço."

### 1.7 Planos e preços
Dentro da conta não há tabela; o link "Visite a nossa Loja Online" vai para armilar.biz/pt-pt/plans:
| Plano | Inclui | Módulos |
|---|---|---|
| INTELLIGENCE (* o mais escolhido) | Mercado de Contratação Pública; Regiões de Portugal e Espanha; Resumo de Oportunidades por IA; Consultor Dedicado | Alerta de Negócios; Previsão de Contratos; Informação de Mercado |
| CONSTRUÇÃO + | + Mercado Privado da Construção | + Previsão de Projetos; Informação de Projetos |
| SAÚDE + | foco em preços de princípios ativos | + Preços de Mercado |
"Preços sob consulta" — formulário (Nome, Empresa, Email, Telefone, NIF). Sem limites de utilizadores/créditos visíveis.

### 1.8 Três testes
- **a) NIF 508080142** (modal Compradores → "Pesquisa por NIF"): **1 entidade — "UNIDADE LOCAL DE SAÚDE DE SÃO JOSÉ, E.P.E. (508080142)"**. (O rádio "por NIF" só mudou ao clicar no elemento; o clique por coordenada falhou.)
- **b) Anúncio 24090/2026 (Almodôvar, 4 viaturas):** **não encontrado.** Pesquisa "24090/2026" → 0; "Almodôvar viaturas" (todas as palavras) → 0; "Almodôvar" → 1057 resultados, mas a maioria "Almodóvar del Campo" (Espanha), e os portugueses são adjudicações antigas. Comprador "Câmara Municipal de Almodôvar (506816184)" existe no diretório. Conclusão: a 30/09 de manhã o anúncio de 06/10 não estava indexado.
- **c) Mais recente:** anúncio DR **24122/2026**, publicado 29/09/2026 (APS Sines). Havia várias publicações de 29/09/2026 em Espanha e Portugal; nada de 30/09 às 08h.

### 1.9 Faz bem / faz mal
**Bem (copiar):**
- Link direto ao DR e às peças na ficha; peças descarregáveis em bloco.
- Resumo IA com **secções fixas** (datas, critérios, garantias/penalidades, pagamentos) e **fonte com páginas**; versionado.
- Insights por concurso: desconto estimado, nº de participantes esperado, concorrentes prováveis com taxa de sucesso e último contrato.
- Ficha de empresa com desconto médio, média de participantes, taxa de sucesso, principais clientes.
- Deteta e assinala alterações na fonte ("sofreu modificações").
- Pesquisa full-text opcional dentro dos PDFs.
- Lista de atividades por oportunidade com grupos de tarefas pré-definidos.

**Mal:**
- **Lentidão:** o separador do Chrome congelou 4 vezes (screenshots expiraram após 30 s); Insights ~30 s; resumo 1–2 min; dashboard com spinners >1 min.
- **Espanha por defeito:** sem filtro de país, tudo é ES. O filtro de localização perdeu-se ao mudar o texto da pesquisa.
- **Pesquisa fuzzy sem acentos** ("Almodôvar" = "Almodóvar del Campo").
- **Idioma instável:** ao navegar por URL a UI passou para inglês (Overview / My Interests / Opportunities Finder / Task Manager / "Assign user") e depois voltou.
- Resumo IA: fontes como hash, repetições, inferências apresentadas como factos (decisão de contratar, conservação 4 anos), hora do prazo incoerente com a ficha (23:59 vs 22:59).
- Ficha "Última atualização da fonte: 01/01/0001" numa oportunidade do INFARMED (data nula não tratada).
- Tarefas de fevereiro ainda "Ativa" sem alerta de atraso na lista.
- Página de Notificações vazia.

---

## 2. TENDIOS BID (bid.tendios.com) — plano Freemium

### 2.1 Estrutura
Barra lateral: Início · Vera (Beta) · Tarefas (cadeado) · Ferramentas · **Descobrir:** Buscar, Alertas · **Gestão comercial:** Oportunidades (kanban), Organizações, Contactos · **Estudo de mercado:** Listas · **Diretórios:** Empresas, Organismos, CPVs · **Ajuda e formação:** Academy, help.tendios.com. Checklist de onboarding "Primeros pasos en Tendios" **em espanhol**. Widget Lusha embebido.

Painel de Controle: caixa de pergunta à Vera; atalhos; KPIs "Total de Licitações 13.763.226 (+2879 nas últimas 24h)", "Avaliações 9.852.973 (+5339)" (=adjudicações), "Contratos Menores 4.579.211 (+409)" — **base ES+PT misturada**; gráfico 30 dias (246 733 publicadas / 80 558 adjudicadas); Taxa de sucesso; Pipeline por estado com valor; "Insights da Vera"; "Resumo da semana GERADO POR VERA AI".

Pesquisador: caixa "Buscar licitações"; banner "Foi aplicada a pesquisa personalizada criada para você" (setor). Filtros: Publicadas últimas 24h · Atualizadas últimas 24h · Excluir salvas/descartadas · CPV (0/5 — máximo 5 no free) · Órgão de Contratação (cadeado) · Localização · Estados (cadeado) · Montantes · Datas · Tipo de contrato · Contratos menores · Classificação empresarial · "Filtros inteligentes: O que você está procurando? — Desbloquear". Tabs: Todas (cadeado) · Em Dia · Avaliações (cadeado) · Vencimentos (cadeado). Colunas: Expediente · Nome · Estado · Orçamento · Prazo final · Organismo (link) · Localização; "Editar colunas"; ordenar; lista/tabela; por linha: guardar como oportunidade, descartar, ver detalhes (drawer), Vera. Pesquisas salvas (2).

### 2.2 Ficha de um concurso (27/2026, Município de Aveiro — viaturas)
Cabeçalho: Expediente · título · organismo (link) · país · estado; botões Descartar · Guardar · Vera. Tabs: **Resumo · Lotes (2) · Documentos (5) · Fontes (3) · Atividade (cadeado) · Análise (cadeado)**.
- Resumo: Cronograma (Publicação 28 set 2026 00:00 · Fim da apresentação 13 out 2026 17:00 · Adjudicação —; "Step 1 of 3" em inglês) · CPVs (34130000 + descrição) · Objeto do contrato · Descrição do procedimento · Informação Geral: Estado, Resultado, Tipo de procedimento (Aberto), **Tipo de contrato ("Não definido")**, Lotes · Datas: Duração do contrato (1 ano), Fim da apresentação, Prorrogação · Montantes: Orçamento, Valor estimado, Valor anual, **Valor mensal (14.671,23 € — calculado, sem sentido para uma compra)**, Garantia provisória, Garantia definitiva · Órgão de Contratação: Organismo, Responsável, Endereço, Email, Atividade da organização ("Servicios públicos generales" — espanhol), Horário, Telefone, Web.
- Drawer rápido (olho): "Faltam 13 dias e 9 horas" e, mais abaixo, "faltam 14 dias" — inconsistente.
- Lotes: LOTE-1 "Viatura ligeira de mercadorias elétrica - tipo furgão"; LOTE-2 "Viatura pesada de mercadorias com caixa aberta tribasculante"; **orçamento por lote "--"** (a Vera sabe: 130 000 € e 48 500 €).
- Documentos: "FORNECIMENTO DAS PEÇAS DO CONCURSO" (ARCHIVE, AcinGov) · **Anúncio 23871/2026.pdf (Diário da República)** · Minuta do anúncio.pdf · 1_Caderno_Encargos.pdf · 2_Programa_Procedimento.pdf. **"O download não está disponível no seu plano atual"** (há botão "Ver").
- Fontes: PT_DDR_CPO (revisto 28/09 10:01) · PT_ACINGOV (28/09 10:01) · PT_BG_CPO (28/09 13:04) — códigos internos, **sem link clicável para o DR**; "Links adicionais: não existem".

**Ligação ao DR: só o nome do PDF do anúncio; sem URL. Peças: listadas, bloqueadas no free.**

### 2.3 Leitura por IA (Vera)
- O botão "Vera" na ficha abre paywall ("Plano Pro"). Na página /vera a conversa funciona no free.
- 1.ª mensagem (com nome do concurso) → **~25 s**, devolveu um cartão "Pesquisa de licitações — 1 resultados" e "Por favor, seleciona o concurso no ecrã". Após "Selecionar" → "Quero ver os detalhes desta licitação": *"Entidade Adjudicante: Município de Aveiro · Preço Base: 178.500,00 € (sem IVA), dividido em 2 lotes (Lote 1: 130.000,00 €; Lote 2: 48.500,00 €) · Estado: Publicada · Prazo limite para apresentação de propostas: 13/10/2026 às 16:00"* — **a ficha diz 17:00**.
- **"Quais são os critérios de adjudicação?"** (~30–40 s; mostra "A pensar…" e um cartão "Documentação da licitação"):
  > "Critério Principal / O critério de adjudicação é o da proposta economicamente mais vantajosa por Lote [1]. / Aplica-se a modalidade Monofator, sendo o único fator de avaliação o Preço [2]. / A adjudicação é feita à proposta que apresentar o mais baixo preço contratual [1]. / O critério não é diferenciado por lote [2]. / Critérios de Desempate / 1º Critério: Em caso de empate, vence a proposta com o menor prazo de execução proposto para o respetivo Lote [1]. / 2º Critério: Se o empate persistir, o desempate será feito por sorteio realizado pelo Júri do Procedimento, de forma isenta e transparente (com recurso a boletins em urna ou saco opaco) [1]. / Analisei as peças do procedimento relativamente aos critérios de adjudicação."
- **"Qual é o prazo de execução?"** (~30 s):
  > "O prazo de execução estabelecido nos documentos do procedimento apresenta as seguintes características: / O prazo de execução base do contrato (abrangendo o LOT-0001 e LOT-0002) é de 365 Dias [1]. / Não existe previsão de renovações para este contrato [1]. / O prazo de execução específico de cada Lote será aquele que constar na proposta adjudicada [2]. / A contagem do prazo inicia-se no dia seguinte ao da outorga do contrato [2]. / Analisei as peças do procedimento relativamente ao prazo de execução."
- **Citações:** os números [1]/[2] são botões. Ao clicar em [1] abre um visualizador com título **"Cláusula 12ª - Critério de adjudicação"**, excerto literal ("Após análise das propostas por Lote, a adjudicação é feita à proposta não excluída que apresentar o mais baixo preço contratual para a execução do objeto do Lote…") e o PDF do Programa de Procedimento (Câmara Municipal de Aveiro, CP n.º 27/26) **aberto na página 1 (índice)** — cita **documento e cláusula, não a página**, e não salta para ela.
- Invenções: não detetei; o texto é consistente com o excerto citado. Não pude ler o PDF inteiro (download bloqueado). Disclaimer permanente "Vera não substitui a revisão técnica ou jurídica".

### 2.4 Alertas
Um alerta auto-criado "Novas licitações do meu setor" ("Configurado automaticamente por Tendios"). Lista: Nome · Frequência (S, T, Q, Q, S) · Última notificação (Ontem 08:36) · Utilizadores. Ficha do alerta com tabs Resultados · Parâmetros · Notificações · Atividade (cadeado) · Expedições · Integrações (cadeado).
- **Parâmetros:** Tipo de resultados — "Seguir status da licitação": Por publicação / Por adjudicação / Por vencimento; Licitações / Contratos menores. Conceitos de pesquisa — **Palavras-chave incluídas** (7: serviços postais, telecomunicações, serviços de correio, +4) e **Excludentes** ("Sem palavras-chave excluídas"); **Setores (CPV) incluídos** (64000000) e **Excludentes**; lógica **OU** (mais ampla) / **E** (mais restrita). (Ecrã continua com mais filtros que não consegui ler: presumo localização, montantes, órgãos, porque a tab Resultados tem esses filtros mais "Proponentes (0/5)".)
- **Notificações:** por e-mail; Destinatários (adicionar); **Frequência: Diária · Hora 09:00 · Fuso "Europa/Madrid"** (não Lisboa) · Dias da semana Seg–Dom; **"Enviar resumo mesmo que não haja novidades (novas licitações e modificações)"** → o alerta cobre **modificações**; Conteúdo: formato dos cartões (Cartão completo).
- **Expedições:** histórico real de envios (29 set 08:36 — 4 licitações; 28 set — 1; 25 set — 1; 24 set — 1; 23 set — 2; 22 set — 3; 21 set — 5; …; 21 envios).
- Bug: abrir a tab por URL (?tab=params) mostra painel vazio; só por clique.

### 2.5 CRM / Pipeline
- Kanban "As minhas oportunidades guardadas": colunas **Em revisão · Candidata · Em andamento · Submetida · Ganha · Perdida** (contagem + valor €); "Automação: Ativa"; responsável; "Equipas"; "Nova Oportunidade"; ordenação "Personalizado". Tarefas: cadeado. "Organizações" e "Contactos" = mini-CRM próprio (vazio). Não vi campos por proposta nem notas (bloqueado/vazio no free).

### 2.6 Mercado
- KPIs de adjudicações no painel; **Diretório de Organismos** (311 870; cartões com sigla, país, NIF, nº "Em dia", nº "Avaliações", nº "Fornecedores"; topo da lista = agregados espanhóis "ENTIDADES LOCALES", "Andalucía"…). **Ficha de entidade** (Município de Aveiro): NIF 505931192; tabs Detalhes/Expedientes; endereço, código postal, "**População: Aveiro**" (tradução errada de "Población"), telefone, fax, e-mail, idioma. Sem histórico de contratos/fornecedores no free. Vera oferece "Analisar candidatos". Não há "contratos a terminar"/renovações visível.

### 2.7 Planos (modal na conta)
| Plano | Preço | Inclui |
|---|---|---|
| Freemium (atual) | 0 € | pesquisador limitado (5 CPV, filtros com cadeado), 1 alerta auto, Vera na página própria, sem download de peças, sem Atividade/Análise/Tarefas |
| **Pro** | **"De 37€/mês" — 0 € durante 7 dias** | Utilizadores: 2 · Alertas: 2 · Pesquisador · Inteligência Artificial · Transferência de dados · CRM de licitações · Suporte prioritário · "Cancele quando quiser" |
"Ver mais planos" abre janela fora do grupo; /plans dá 404.

### 2.8 Três testes
- **a) NIF 508080142:** caixa "Pesquisar órgãos por nome ou NIF" no diretório — Enter não filtrou (lista ficou nos 311 870). **Inconclusivo** (provável bug ou pesquisa só por clique).
- **b) 24090/2026 / Almodôvar:** "Almodôvar" e "Almodovar" → **0 leilões** (com a pesquisa personalizada do setor ativa; "viaturas" no mesmo contexto deu 40, logo o texto sobrepõe-se ao setor). **Não existe.**
- **c) Mais recente:** filtro "Publicadas últimas 24h" (após reload): 2 licitações de 29–30/09 no perfil: **CP/1/2026 – Escola Básica Integrada Canto da Maia** (refeições; "Orçamento 0 €"; limite 08/10/2026 22:59) e "SalesianosdeManique:ViagemPRAGA" (limite "6 de outubro de 2027" — provável erro de dados). O concurso de Aveiro tem anúncio DR 23871/2026 (28/09).

### 2.9 Faz bem / faz mal
**Bem:**
- **Citações clicáveis** que abrem o PDF com a cláusula e o excerto literal.
- Alerta com **incluídos/excluídos** para palavras e CPV, lógica OU/E, **por publicação / adjudicação / vencimento**, e histórico de expedições.
- Alerta e pesquisa personalizada criados automaticamente a partir do setor da empresa.
- Fontes com carimbo de "revisto em" (hora da última leitura).
- Guardar/descartar direto da lista; kanban com valor por coluna.
- Resposta da Vera com estrutura (critério principal / desempate).

**Mal:**
- **Tradução PT-BR/ES:** "Painel de Controle", "leilões encontrados", "Buscar", "você", "Servicios públicos generales", "População: Aveiro", checklist em espanhol, "Step 1 of 3", fuso "Europa/Madrid".
- **Dados:** "Tipo de contrato: Não definido"; "Orçamento 0 €" quando desconhecido; orçamento por lote "--"; hora do prazo 17:00 (ficha) vs 16:00 (Vera); "faltam 13 dias e 9 horas" vs "14 dias"; prazo 2027 num concurso.
- Free muito castrado: sem download de peças, sem link ao DR, Vera na ficha atrás de paywall, CPV máx. 5, Estados/Órgão com cadeado.
- Checkbox "Publicadas últimas 24h" só atua após recarregar; tabs do alerta vazias por URL; "Ver mais planos" abre janela solta; separador congelou 2 vezes.
- Base ES+PT misturada nos números do painel e no diretório.

---

## 3. ADJUDICA (adjudica.biz) — conta nova

### 3.1 Estrutura
Onboarding em 2 passos: (1) País de operação (Portugal), produto (Concursos públicos / Fundos europeus / Ambos), "Tem 10 € em créditos de boas-vindas"; (2) "Foco" do agente — texto livre com sugestões (TI e software · Construção e obras · Facilities e manutenção · Consultoria e formação · Saúde e social · Fornecimentos e equipamento). Conclusão: "Score 92% — Está tudo pronto" e 4 promessas: Radar sempre a postos · Análise que decide (Go ou No-Go) · Proposta a sério · Fale com o agente.

Menu: **Concursos** (Radar) · **Fundos** · Radar · **Projetos** ("Perseguições") · **Acompanhamento** ("Depois da submissão") · **Créditos** · Atividade ("0 a processar") · **Explorar** · Definições.
- Radar: "FOCO DO AGENTE: Desenvolvimento de software à medida, integração de sistemas de informação, cloud e cibersegurança. Atualizado 30/09, 08:18" · "Última pesquisa: 30/09, 08:18 · **1 pesquisa falhou** · Ainda sem concursos no radar" · **"Créditos de boas-vindas esgotados — o trabalho dos agentes está em pausa. Subscreva um plano."**
- Explorar: pesquisas pontuais em linguagem natural ("Cada pesquisa demora alguns minutos — os resultados aparecem aqui automaticamente").
- Projetos: "Cada concurso que decidiu perseguir, com a fase atual e o que aguarda a sua decisão" (vazio).
- Acompanhamento: pede **NIF da empresa** para cruzar com a lista de concorrentes publicada em cada contrato e dizer se ganhou/perdeu; "Já concorri a um concurso".
- Definições: Aparência (tema, idioma) · Notificações por e-mail (Análise profunda concluída · Análise rápida pedida por si concluída · Proposta concluída · Pesquisa "Explorar" concluída · …) · Empresa (NIF, nome, site) · **"Leitura automática da empresa"** (lê o site e documentos, preenche perfil, sugere competências e foco; consome créditos) · Perfil (Nome, Setor, Dimensão, Região, Certificações, Diferenciadores) · Competências · "Modelos por fase".

### 3.2 Ficha de concurso, 3.3 IA go/no-go, 3.4 alertas, 3.5 CRM, 3.6 mercado
**Não testável:** o saldo estava a **0 cr** ("Créditos de boas-vindas esgotados", "Consumo total 0 cr / 0 pedidos / 0 tokens") logo após o onboarding, com "1 pesquisa falhou". O radar não devolveu nenhum concurso, não há ficha, não há avaliação go/no-go, não há alertas configuráveis (o "alerta" é o foco do agente + e-mails de conclusão), o pipeline ("Projetos") está vazio e não há módulo de mercado (o "Acompanhamento" só olha para os contratos onde a empresa concorreu).

### 3.7 Planos e preços (página /plans dentro da conta)
| Plano | Créditos/mês | Preço |
|---|---|---|
| Start | 50 000 cr | 50,00 €/mês — "Para começar e testar o fluxo com volume ligeiro" |
| Grow | 100 000 cr | 100,00 €/mês |
| Scale | 195 000 cr | 195,00 €/mês — "equipas com vários concursos em simultâneo" |
| Pro | 290 000 cr | 290,00 €/mês — "modelos premium no dia a dia" |
| Max | 500 000 cr | 500,00 €/mês |
"Os créditos renovam a cada ciclo e não transitam." Upgrade imediato com proporcional; ao cancelar mantém créditos até ao fim do período. Modelos económicos "correm no nosso próprio hardware"; modelos premium (propostas, análise profunda) consomem créditos comprados; "cada modelo consome créditos a ritmos diferentes". Sem indicação de utilizadores/limites.

### 3.8 Testes
Nenhum dos três é possível (não há pesquisa por entidade, por referência nem lista de anúncios; só o radar por foco e "Explorar", ambos parados sem créditos).

### 3.9 Faz bem / faz mal
**Bem:** onboarding claro, em bom português; conceito "foco" em linguagem natural com dicas úteis ("use as palavras com que um comprador o publicaria; duas a quatro áreas"); Acompanhamento por NIF para saber ganho/perdido automaticamente; leitura automática do site da empresa; e-mails por evento; consumo por fase/projeto na carteira.
**Mal:** os 10 € de boas-vindas desapareceram numa pesquisa que falhou — o produto fica inutilizável antes de mostrar um único concurso; sem pesquisa manual, sem diretório, sem ficha sem créditos; "1 pesquisa falhou" sem explicação; rotas /app, /dashboard, /tenders, /billing dão 404 (o onboarding é a única porta).

---

## 4. SPOTGOV (demo interativa Navattic — capturas do produto, em inglês)

### 4.1 Estrutura
Menu: **DETECTION AND ANALYSIS:** Active Tenders · Tender Radar · **MANAGEMENT:** Saved Tenders · Notifications · **MARKET INTELLIGENCE:** Market Intelligence · Past Tenders · Pipeline Radar · **APPLICATION:** Proposal Revision.
- Active Tenders ("New Search"): "Search with AI…" (linguagem natural) + país (Portugal) + Advanced Options: Include Keywords · Exclude Keywords · "Search in Documents" · Search with CPVs · Entities · Base Price · Publication · Location · "Active tenders"; "Previous Searches (83)" com contagem de resultados e etiqueta "AI".
- Tender Radar: tabela com filtros Searches · CPV · Entities · Interest · Country · Platform · Publication Date · Base Price · Most recent; colunas Title (entidade + Ref) · Interest (Save) · Visto · Base Price · Publication Date · Submission Deadline · Time left; "Add column", "Export".
- Saved Tenders: kanban por Phases / Table / Timeline; colunas "Saved Tenders (3 contracts · 2 590 283,37 €)", "Saved Tenders (2)", "Under Review", "Reviewer"…; cartão com entidade, valor, Ref, **labels** (Low Priority, Urgent), **utilizador atribuído**, "X days left"/"Deadline expired"; filtros Label · User · Country; Export.
- Market Intelligence: "Search for any company or public entity in Portugal"; "Competitors Activity — Total contracts: 2317"; filtros Monitored companies (2) · Publication Date · Winner · CPV; tabela Publication Date · Description (+ entidade) · Winner · **Competitors (nº)** · Price (adjudicado vs base).
- Past Tenders: pesquisa histórica com Include/Exclude keywords, CPVs, Entities, Base Price, Publication, Location, "Has announcement", **Competitors · Winners · Type**.
- **Pipeline Radar:** "Contracts in execution approaching renewal date"; filtros Entity · Location · Value · Renewal date · Winner · Competitor · CPV · Nearest renewal; gráfico "Number of Renewals" por mês (ano/mês/semana/dia); "Total: 112 910 · Volume: 33,6 mM €"; tabs Contracts / Top Entities / Top Winners; Watchlist; Export. **Sem probabilidade** — data de renovação = fim de contrato.
- Proposal Revision: escolher contrato guardado (por fase) → revisão da proposta; "Existing Revisions".

### 4.2 Ficha (exemplo "BIA - AI Bot for Public Procurement", Infraestruturas de Portugal, Ref 10021989)
Cabeçalho: título, entidade, "1 day left", Ref, "Updated", partilha; botões **"Analyze with AI"** e Save; Base Price 1 000 000 € · Location (Almada, Setúbal) · Publication Date 18/03/2026 · Submission Deadline 23/03/2026. Painel lateral "Additional Information": Contract Object · **Useful Links: Diário da República · AnoGov** · Execution Deadline (6 MESES) · Renewable (No) · Award Criteria (Preço 40% · Outros 30% · Qualidade 30%) · Contracting Entity (morada, **NIPC 503933813**, site) · General Information (e-mail, telefone) · Administrative Appeals Body · Files (Default / Uploaded / Upload Documents): Terms of Reference (0,6 MB), Tender Program (0,8 MB), espd-request.pdf/.xml, 2026-OJS024-…-pt-ts.pdf (TED), README.txt, Anúncio, Anexo III, Anexo IV Critério Adjudicação, Caderno Encargos Cláusulas Especiais, xades.xml. Tabela "Regulamentação": Publication Date · Description (25/07/2025 — Regulamento de IA).

**Ligação ao DR e peças: sim (links e ficheiros com tamanho).**

### 4.3 Leitura por IA ("AI Analysis" do exemplo)
Tabela Category / Details com 7 categorias e tamanho do texto: Contractual Object (5 562 caracteres) · Technical Specifications (5 776) · Place of Execution and Supply Conditions (5 030) · Deadlines (1 011) · Price (1 796) · Other Award Criteria (1 421) · Required Documents (2 940). Toggle "Default Docs / Uploaded Docs"; "Export"; "Deepen Analysis".
Excertos literais:
> **Deadlines:** "Deadline for proposals submission: 09-03-2026 at 17:00. Note: proposals must be delivered through the electronic platform https://www.anogov.com/infraestruturasdeportugal-ip/… Period during which proposals must be kept: 120 days from the end of the proposals submission deadline (i.e., from 09-03-2026). Proposal signing: must be carried out with a qualified certificate (e.g.: Citizen Card, Digital Sign, Multicert) under Article 13. Deadline for submission of eligibility documents by the awardee: 10 days from the adjudication notification (Article 20). Deadline for providing the bid security: 10 days from the notification provided in paragraph 2 of Article 77 of the CCP (Article 19). Contract execution period: 6 MONTHS. Note: it is anticipated that there will be no renewals…"
>
> **Other Award Criteria:** "Award Criteria (hierarchized with respective coefficients) Price (K1) — 40%. Partial scoring formula: K1 = 100 – 100 × (Pc / Pb)^3 … Technical merit of the proposal (K2) — 30%. Discrete value evaluation system: 1, 33, 66 and 100 … Comprises seven subfactors, with internal weightings: K2.1 – Architecture and Design — 30%; K2.2 – Technical Quality — 20%; K2.3 – Governance and Transparency — 15%; K2.4 – Performance and SLA — 10%; K2.5 – Security and Data Protection — 10%; K2.6 – Team Competence — 10%; K2.7 – Sustainability and Knowledge Transfer (note: the text of the subfactor is truncated in the excerpt provided). Proof of Concept (K3) — 30%…"
>
> **Price:** "Maximum price that the IP is willing to pay: € 1,000,000.00 — excluding VAT … Payment terms: 50% of the contractual price after 3 months from the start of the project (end of implementation); 50% at the end of the project. Electronic invoicing … EDI … Invoice payment term: up to 60 days…"

Chatbot ("Clarify your doubts…", com o PDF ao lado): pergunta do exemplo "What are the delivery deadlines for the solution and what data protection laws (DPIA) are required?" → resposta em bullets: "Interim demonstration of the solution: 13/06/2026 · Delivery of the Operational Solution: 30/07/2026 · Provisional acceptance: 30/08/2026 · Final acceptance: 26/10/2026 · Maximum contract execution period: 6 months from date of contract signature · A DPIA is mandatory prior to production…"; no cabeçalho aparece um ícone de citação "1/1" e um ícone de tabela — **cita o documento (1 fonte), sem número de página visível**.

Tempo: não medível (demo estática). Invenções/erros visíveis **na própria demo**: a IA diz prazo de entrega **09-03-2026 às 17:00** mas o cabeçalho da ficha diz **Submission Deadline 23/03/2026** e Publication Date 18/03/2026 (prazo antes da publicação); a IA escreve "the text of the subfactor is truncated in the excerpt provided" (assume que o excerto está truncado em vez de ler o documento); os critérios no painel lateral são "Preço 40 / Outros 30 / Qualidade 30" e na IA "K1 40 / K2 30 / K3 30" — coerentes, mas com nomes diferentes. Toda a análise está **em inglês** para um concurso português.

### 4.4 Alertas: "Notifications" no menu e "Saved searches" com etiqueta AI; a demo não mostra o formulário de alerta. Filtros da pesquisa: palavras a incluir, palavras a excluir, "search in documents", CPV, entidades, preço base, publicação, localização, país, plataforma.
### 4.5 CRM: kanban por fases (Saved Tenders · Under Review · Reviewer · Submitted · Lost…), labels (Urgent, Low Priority), utilizador atribuído, contagem/valor por coluna, timeline, export; "Proposal Revision" (IA revê a proposta contra as peças).
### 4.6 Mercado: Market Intelligence (empresas monitorizadas, nº de concorrentes por contrato, preço adjudicado vs base); Past Tenders (histórico com winners/competitors); **Pipeline Radar** (contratos a terminar por mês, watchlist; sem probabilidade); ficha de entidade com NIPC.
### 4.7 Planos: não visíveis na demo ("Book a Demo").
### 4.8 Testes: não aplicáveis (demo com dados fixos; "Search for any company or public entity in Portugal" existe mas não é executável).

### 4.9 Faz bem / faz mal
**Bem:** pesquisa em linguagem natural + palavras a excluir + "search in documents"; análise IA em tabela por categoria com fórmulas e ponderações completas; chatbot lado a lado com o PDF; **Pipeline Radar** (renovações por mês, watchlist); Market Intelligence com nº de concorrentes por contrato; kanban com labels e responsável; ficheiros com tamanho; links DR/AnoGov.
**Mal:** interface e análise em inglês; a demo expõe um prazo errado (09/03 vs 23/03) sem qualquer alerta de incoerência; a IA reconhece "excerto truncado" (lê chunks, não o documento inteiro); sem página nas citações; separador da demo congelou 2 vezes.

---

## 5. TRINTA (trinta.ai) — só site de marketing

### 5.1 Estrutura (declarada, não vista a funcionar)
Sete módulos: 01 Radar (varrimento diário, cada aviso 0–100) · 02 Sinais (pré-informação, acordos-quadro a expirar) · 03 Dossiês (peças lidas: prazo real, valor, critérios, certificações, garantias, "peças em falta") · 04 Pipeline ("escada de doze estados", rascunho IA) · 05 Parceiros (bolsa por país) · 06 Resultados (vitórias, derrotas, ROI) · 07 Forensics (dissecar adjudicações perdidas, "citação literal e norma", prazo de reação em dias úteis). Fontes PT: Diário da República, BASE.gov, Vortal, acinGov, anoGov, ComprasPT, TED; "varrimento 05:12", "várias vezes por dia, incluindo fim de semana". Promessas relevantes: prorrogações e retificações aplicadas ao prazo; janelas de esclarecimentos e de erros e omissões contadas; "**fecha às 17:00, não às 23:59 — a hora vem da plataforma**"; acordos-quadro/SNCP; histórico do adjudicante por NIF.
### 5.2–5.6 Ficha, IA, alertas, CRM, mercado: sem acesso. O site tem um widget "Escreva o NIF → Ver o registo" (dados BASE via IMPIC, "sem registo e sem email"); testei com 508080142 duas vezes (botão e submit) e **não apareceu resultado** no ecrã. Há também "Experimente já com o seu site" (radar em ~20–30 s, sem registo) — não testado por não ter o site da empresa.
### 5.7 Preços (página /pricing, sem IVA)
| Âmbito | Critério | Preço |
|---|---|---|
| Radar | até 10 M€ decididos/ano no seu mercado | 2 000–2 500 €/mês (24 000–30 000 €/ano); 1 mercado; 3 lugares; 100 documentos/mês; apoio por e-mail |
| Pipeline ("a escolha da maioria") | 10–50 M€ | 4 000 €/mês (48 000 €/ano); + região + TED; Radar Signals; vários perfis; parceiros; API, webhooks, Slack, Teams; ROI; 10 lugares; gestor dedicado |
| Command | > 50 M€ | personalizado, plurianual; geografia ilimitada; lugares ilimitados; auditoria; camada de proposta; briefings |
Piloto pago de 30 dias: 2 000 €, creditado no 1.º ano. Contratos desde ago-2026 com indexação IPC + 2% (mín. 4%).
### 5.8 Testes: não aplicáveis.
### 5.9 Bem/mal: **Bem** — o discurso lista exatamente as dores certas (hora exata do prazo, prorrogações/retificações, erros e omissões, dias úteis, peças > portal, "peças em falta assinaladas em vez de adivinhadas"). **Mal** — nada é verificável sem demo com o fundador; preço 20–50× o da Tendios; widget de NIF não devolveu nada.

---

## 6. Tabela comparativa (o que vi, não o que dizem)

| Critério | Armilar | Tendios (free) | Adjudica | SpotGov (demo) | TRINTA (site) |
|---|---|---|---|---|---|
| Base PT separada de ES | Não (ES por defeito) | Não (misturada) | Só PT | Só PT | Só PT |
| Link ao DR na ficha | **Sim (URL)** | Só nome do PDF | — | Sim (link) | (promete) |
| Peças descarregáveis | **Sim** | Bloqueado no free | — | Sim | (promete) |
| Anúncio 24090/2026 | Não | Não | — | — | — |
| Entidade por NIF 508080142 | **1 (ULS São José)** | Inconclusivo | — | — | Sem resultado |
| Anúncio mais recente | 24122/2026 (29/09) | CP/1/2026 Canto da Maia (29/09) | — | — | — |
| IA: resumo estruturado | Sim, 5 secções | Só Q&A | (não correu) | Sim, 7 categorias | (promete) |
| IA: cita documento | Hash do ficheiro | **Sim (cláusula + excerto + PDF)** | — | Sim ("1/1") | (promete) |
| IA: cita página | **Sim (números)** | Não (abre no índice) | — | Não | — |
| IA: tempo | 1–2 min | 25–40 s/pergunta | — | n/a | — |
| IA: erros vistos | Inferências como factos; hora 23:59 vs 22:59; repetições | Hora 16:00 vs 17:00 | — | Prazo 09/03 vs 23/03 na demo | — |
| Deteta alterações | **Sim (ícone + data)** | Sim (alerta cobre "modificações") | — | "Updated" na ficha | (promete) |
| Alerta: CPV / palavras / exclusões | CPV, palavras; sem exclusões vistas | **CPV ± e palavras ±, OU/E** | Foco em texto livre | Include/Exclude | — |
| Alerta: frequência | Diária (não configurável) | **Diária, hora, dias, fuso** | E-mail por evento | ? | Manhã |
| Pipeline / estados | 5 fases + tarefas por grupo | 6 colunas kanban | "Projetos" (vazio) | Kanban + labels + user | 12 estados |
| Mercado: ficha empresa | **Desconto médio, nº participantes, taxa sucesso, clientes** | NIF + morada | — | Nº concorrentes, preço adj. | Por NIF |
| Contratos a acabar | Sim, com **Probabilidade** (vazio nesta conta) | Não | Não | **Sim (Pipeline Radar, sem prob.)** | Sinais |
| Preço | Sob consulta | 0 € / Pro 37 €/mês | 50–500 €/mês em créditos | Sob demo | 2 000–4 000 €/mês |
| Estabilidade/UX | Lento, congelou 4×, idioma instável | PT-BR/ES, bugs de filtro | 404s, créditos esgotados | Congelou 2× (demo) | n/a |

---

## 7. Ideias a roubar (ordenadas pelo valor para uma PME portuguesa que concorre todas as semanas)

1. **Hora exata do prazo, vinda da plataforma, com fuso explícito** (TRINTA promete; Armilar mostra "no seu fuso horário"; Tendios e Armilar falharam por 1 h). Mostrar sempre "17:00 Lisboa (fonte: acinGov)".
2. **Detetar e assinalar alterações ao concurso** (Armilar: ícone + "Última atualização da fonte"; Tendios: alerta cobre modificações). Guardar diff: prazo prorrogado, retificação, esclarecimentos, cancelamento.
3. **Citações que abrem o PDF na cláusula, com excerto literal** (Tendios) **e número de página** (Armilar). Fazer as duas coisas com o nome real do ficheiro, não hash.
4. **Resumo IA com secções fixas** — Datas · Critérios com ponderações e fórmula · Habilitação/documentos exigidos · Cauções/garantias · Penalidades · Pagamentos (Armilar + SpotGov). Marcar cada linha como "extraído" vs "inferido".
5. **Alerta com incluídos e excluídos** (palavras e CPV), lógica OU/E, e três gatilhos: publicação, adjudicação, vencimento (Tendios). Frequência/hora/dias configuráveis, fuso Lisboa.
6. **Insights por concurso:** desconto estimado, nº esperado de participantes, concorrentes prováveis com taxa de sucesso e último contrato com a entidade (Armilar). É o que decide "vale a pena?" em 10 s.
7. **Ficha de empresa** com desconto médio, média de participantes, taxa de sucesso e principais clientes (Armilar); nº de concorrentes por contrato e preço adjudicado vs base (SpotGov).
8. **Contratos a terminar** por mês, com watchlist (SpotGov Pipeline Radar) e probabilidade (Armilar). Para uma PME é a única forma de chegar antes do anúncio.
9. **Link direto ao DR e peças em bloco, com tamanho** (Armilar, SpotGov) — e "peças em falta" assinaladas (TRINTA).
10. **Filtro de país por defeito = Portugal** e base ES separada (todas as ES-first falham aqui).
11. **Guardar/descartar da lista + kanban com valor por coluna, labels e responsável** (Tendios, SpotGov); lista de tarefas pré-definida por oportunidade (Armilar: proposta, documentos económicos/técnicos/legais, validações).
12. **Histórico de expedições do alerta** ("29 set 08:36 — 4 licitações") para o utilizador confiar que o alerta corre (Tendios).
13. **Acompanhamento ganho/perdido por NIF** cruzado com a lista de concorrentes do contrato (Adjudica).
14. **Pesquisa full-text opcional dentro dos PDFs** (Armilar "incluir documentos PDF").
15. **Onboarding com "foco" em linguagem natural e dicas** ("use as palavras com que um comprador o publicaria") (Adjudica) — e alerta auto-criado a partir do setor (Tendios).
16. **Versionar o resumo IA** ("Versão 1 – data") e mostrar quando as peças mudaram (Armilar).

**Erros a não repetir:** base ES misturada; traduções PT-BR/ES; "Orçamento 0 €" e "Tipo de contrato: Não definido"; datas nulas "01/01/0001"; horas de prazo divergentes entre ecrãs; créditos que se esgotam antes do primeiro resultado; IA que apresenta inferências ("decisão de contratar em 29-09") como factos; páginas que congelam o browser.

---

## Notas de auditoria (o que foi tocado)
- **Armilar:** cliquei "Gerar Resumo" numa oportunidade (gerou 1 resumo, consome o que a conta tiver de quota de resumos). Nada guardado/favoritado.
- **Tendios:** 3 perguntas à Vera (chat; free); filtros alterados na pesquisa (não guardados); fechei o checklist de onboarding. Nada guardado.
- **Adjudica:** para entrar na app tive de concluir o onboarding: país Portugal, produto "Concursos públicos", foco "TI e software" (editável em Radar → Editar foco). Recusei cookies. Os créditos já estavam a 0 quando entrei no Radar ("1 pesquisa falhou").
- **SpotGov:** demo pública, nada tocado na conta. **TRINTA:** submeti o NIF 508080142 no widget público (o site diz que não guarda nada).
- Não visitei GovGo nem Tender Radar (fora do pedido).
