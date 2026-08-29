# Concorrentes

O que os produtos pagos deste mercado fazem, o que fazem mal, e o que
daí se aproveita para o radar. Escrito a olhar para eles com a conta do
Afonso, não a partir de material de marketing.

Cada secção tem a data da observação. **Um produto muda; o que aqui está
vale para o dia em que foi visto.** Antes de citar um número destes numa
decisão, confirma se ainda é verdade.

---

## Tendios Bid — `bid.tendios.com`

**Observado a 29 de agosto de 2026**, com a conta do Afonso (Noptis),
**plano gratuito**. Empresa espanhola; `tendios.com` é o site público.

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
4 140 €/ano. O radar tem 66 009 anúncios de dois anos e 1,36 milhões de
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

---

## O que se aprende com eles

Por ordem de valor para o radar. Cada ponto diz o que eles fazem e o que
falta cá.

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
concorrentes. Não prometer o que não há.

**Pré-requisito:** o desconto precisa de preço base, que vem do detalhe.
Hoje só 5 420 dos 66 009 anúncios têm detalhe lido (8,2%) — decisão já
registada no ESTADO.md, com o custo de a levantar (~17 horas de pedidos).
Sem isso, a métrica corre só sobre a janela dos 60 dias.

### 3. Taxa de acerto por alerta

A ficha de cada alerta mostra quatro números: *Licitações em curso ·
Guardadas · Descartadas · **Taxa de acerto***.

Um alerta que produz 200 avisos e zero guardados está mal afinado, e
nada no radar diz isso hoje. Os dados já lá estão — `anuncios.estado`
cruzado com o alerta que marcou cada um.

### 4. As perguntas às peças como configuração, não como código

O motor de automações tem um passo "Análise de oportunidade" com quatro
acções **editáveis pelo utilizador**:

- *Resumo da licitação* — "gera um resumo das folhas e documentação"
- *Quais são os requisitos técnicos e económicos?*
- *Que documentos devem ser apresentados?*
- *Data limite de apresentação* — "adiciona campos personalizados à
  oportunidade"

É a arquitectura do `analisar_pecas()` — um pedido por campo, para não
estourar o tecto de tokens — mas com as perguntas na configuração e o
resultado a cair em campos do quadro. Hoje, para extrair "que classe de
alvará exige", era preciso mexer no `radar.py`.

Há ainda uma página **"Regras para a IA"** — instruções de sistema por
conta, aplicadas a todas as funcionalidades com IA. Um CLAUDE.md do
cliente.

### 5. "Incluir modificações" no resumo diário

O e-mail deles inclui **alterações a concursos já conhecidos**, não só
novos. Uma prorrogação de prazo vale tanto como um anúncio novo. Há
também um toggle *"Enviar resumo mesmo que não haja novidades"* —
desligado por omissão, boa escolha.

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
- **Âmbito de países como preferência da conta**, não como filtro
  ("O âmbito de localização está limitado a PT. Vá para Definições →
  Preferências → Pesquisa para adicionar mais países").

### 7. O que confirma decisões já tomadas

Não é para copiar — é para não voltar atrás:

- **Um só motor de filtros.** A ficha da empresa reutiliza a página de
  pesquisa com `?bidders=<ids>` pré-aplicado e um chip "Proponentes 16"
  com "Limpar tudo". Igual à regra do CLAUDE.md.
- **Um filtro guardado é uma query, e pode ter mais que um papel.** As
  "Pesquisas salvas" deles mostram um resumo em texto (`PT · 1 CPV`) e
  uma marca *"Lista"* quando a mesma pesquisa alimenta uma lista dinâmica.
- **Agrupar por NIF, sempre.** Ver o defeito 2 — e o preço de o não fazer.
- **Anúncios e contratos são coisas diferentes.** Eles misturam-nos no
  mesmo separador com um chip de estado, e daí vem metade da confusão de
  vocabulário ("Avaliações" a ser adjudicações).

---

## Armilar (Vortal) — 200 €/mês

O produto que o radar substitui. Está descrito no ESTADO.md, na secção
de abertura: má experiência de uso e falhas de ingestão. Não foi
reobservado.
