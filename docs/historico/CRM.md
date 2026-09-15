# Plano: o «Em curso» como CRM a sério

Escrito a **15 de setembro de 2026**, a pedido do Afonso: «precisamos de
fazer algo melhor o separador em curso. aquilo não está um verdadeiro
CRM de gestão de leads e de propostas e é estranho porque na página de
anúncios já tenho o que classifiquei como interesse.»

A segunda metade da frase é o diagnóstico inteiro. Este ficheiro mostra
porquê, com o código à vista, e propõe o caminho.

É um plano, não trabalho feito. Quando cada etapa se fizer, corrige-se o
`ESTADO.md`, o `docs/armadilhas.md`, o `LEIA-ME.md` e o `CLAUDE.md` no
mesmo commit; este ficheiro fica como instantâneo.

---

## 0. O que se mediu antes de propor

Base no estado zero, a 15/09/2026: 209 826 anúncios (199 568 `novo`,
10 258 `alteracao`), **zero `interessa`**, zero cartões em qualquer das
seis fases, zero linhas em `casa`. Não há dados de produção a proteger —
é o melhor momento possível para mexer no modelo, e o pior para adiar.

## 1. O que está errado

### 1.1 «Em curso» e «interessados» são a mesma consulta

O `/lista` faz `SELECT * FROM anuncios WHERE estado='interessa'`
(`lista_em_curso()`). A aba «interessados» da lista de anúncios faz
`estado = ?` com `"interessa"` (`condicao_da_aba()`). O `/quadro` e o
`/calendario` partem do mesmo conjunto. **São o mesmo conjunto, sempre.**

A causa não é a interface: é o campo. `anuncios.estado='interessa'` faz
dois trabalhos ao mesmo tempo —

- *«isto merece ser olhado»* — a saída da triagem;
- *«isto é um negócio nosso»* — a entrada do funil.

Num CRM são objectos distintos: **lead** e **oportunidade**. Enquanto
forem a mesma coluna, os dois separadores mostram a mesma coisa, e
nenhum desenho de ecrã resolve isso.

### 1.2 O funil nunca esvazia

`condicao_da_aba()` diz, por escrito: «interessados: TODOS os
`interessa`. Um `interessa` com prazo passado é trabalho em curso». A
regra está certa para a triagem e errada para o funil: um concurso
**Ganho** ou **Perdido** continua com `estado='interessa'` para sempre.
Consequências, as duas visíveis no ecrã:

- as colunas Ganho e Perdido do quadro acumulam desde o primeiro dia,
  sem janela nem arquivo — ao fim de um ano são a maior parte do quadro;
- a aba «interessados» dos anúncios conta negócios fechados como se
  estivessem por decidir.

### 1.3 O CRM são colunas penduradas na tabela dos anúncios

Doze, hoje, em `anuncios`: `fase_id`, `responsavel`, `motivo`,
`preco_proposto`, `posicao`, `top3`, `motivo_perda`, `tipologia`, `cv`,
`proposta_tecnica`, `notas`, `coe`. Isso impõe **um anúncio = uma
oportunidade**, e daí saem três limitações que já se sentem:

- **Os lotes não cabem.** A decisão do Afonso (2/09/2026) é «um cartão
  por anúncio, mas os cartões que têm lotes devem identificar a que
  lotes fomos e se fomos a todos, e no final, perdido ou ganho,
  separam-se os cartões». A segunda metade não está feita, e a primeira
  só se consegue porque o `resumo_dos_lotes()` vai buscar a granularidade
  à tabela `casa` — que é lida do Excel, não editável no painel. Um
  concurso com L1 ganho e L2 perdido não tem onde ser dito.
- **Não há oportunidade sem anúncio do DR.** Consulta prévia, ajuste
  directo, convite, o que veio de antes de 2025. O `casa.porque_sem_ref`
  existe exactamente porque isso é comum no registo dele.
- **Não há histórico por cliente.** O mesmo concurso no ano seguinte é
  outra `ref`, e nada se acumula.

### 1.4 A tabela que falta já existe, e está a ser desperdiçada

`casa` (`casa.py`, `iniciar_tabelas()`): `nome, entidade, modelo,
prazo_meses, preco_base, criterio, plataforma, ano, status, razao,
valor_proposta, lugar, ebitda, notas, perfis, concorrentes,
precos_perfis, ref, lote, porque_sem_ref, zoho_fase, zoho_montante…`

Isto **é** o objecto CRM — tem a granularidade do lote, tem a
oportunidade sem `ref`, tem o resultado, o concorrente e a margem. Só que
hoje é só-leitura, alimentado por importação do Excel, e mostra-se num
bloco da ficha. O painel escreve noutro sítio (as 12 colunas), e os dois
registos do mesmo facto não se falam.

### 1.5 Faltam as três coisas que fazem um CRM ser um CRM

- **Próxima acção.** Um CRM responde a «o que tenho de fazer hoje». O
  quadro responde a «onde é que as coisas estão». Não há tarefa, dono,
  nem data.
- **Pessoas.** Não há o contacto na entidade adjudicante, nem quem cá
  faz o quê para além de um `responsavel` por cartão.
- **Cronologia.** Esta quase existe: o `historico` por `ref` já grava
  quem fez o quê e quando, e o `/quadro/campos` já lá escreve «submetido
  a 118 500 EUR». Falta desenhá-lo como cronologia na ficha.

### 1.6 Achado à parte, e não é de desenho: os campos do CRM não saem do PC

`_TABELAS_TRIAGEM` (B15) exporta do `anuncios` apenas `ref, estado,
fase_id, responsavel, visto_em`. Ficam **fora** do `triagem.jsonl`:
`motivo`, `preco_proposto`, `posicao`, `top3`, `motivo_perda`,
`tipologia`, `cv`, `proposta_tecnica`, `notas`, `coe` — e a tabela
`casa` inteira. Tudo isto é escrito à mão e não se refaz a partir de
fonte nenhuma.

O BACKLOG dá o **R2 (perda do PC)** como «fechada por inteiro a
31/08/2026». Não está: o preço proposto, o lugar no relatório e o motivo
da perda são precisamente «a parte irrecuperável da base» que o B15 diz
guardar. As colunas de 14/09/2026 entraram sem passar por ali.

**Isto corrige-se já, independentemente deste plano** — é acrescentar
colunas ao `_TABELAS_TRIAGEM` e ao `--repor-triagem`, com teste. Esforço
1. Não se espera pelo CRM.

---

## 2. As decisões que são dele

Nada do que está abaixo se faz sem estas quatro respostas.

1. **O vocabulário dos estados.** Há três a coexistir: o do radar
   (`novo/interessa/descartado`, mais as seis fases), o do Excel
   (`Não fomos / Submetido / Perdido / Ganho / Cancelado / TBD`) e o do
   Zoho (`Lost / Won / 2.3 - Negotiation / Ready for Proposal…`). O
   `casa.py` guarda o do Zoho em coluna própria de propósito, com o
   comentário a dizer «quem manda decide-se quando o vocabulário dos
   estados estiver decidido». É agora. Um CRM com três vocabulários não
   dá contas.
2. **A oportunidade sem anúncio entra no painel?** Se sim, o «Em curso»
   deixa de ser uma vista dos anúncios e passa a ter criação própria
   (consulta prévia, ajuste directo). Se não, o Excel continua a ser o
   sítio dessas — e o CRM fica parcial por decisão, não por omissão.
3. **A granularidade é o lote ou o procedimento?** A resposta desenha a
   tabela. A recomendação abaixo é: uma proposta por lote quando há
   lotes, com um cartão agregador — que é o que ele descreveu a
   2/09/2026.
4. **O Excel continua a ser fonte, ou o painel passa a ser o sítio?**
   Enquanto forem os dois a escrever a mesma coisa, há dois registos do
   mesmo facto. O importador do `casa.py` pode passar a ser
   *arranque* (uma vez, para trazer o acervo) em vez de
   *sincronização* (sempre).

---

## 3. O modelo proposto

### 3.1 Uma tabela `propostas`

Uma linha por **proposta**: por lote quando há lotes, por procedimento
quando não há.

```
propostas
  id            INTEGER PRIMARY KEY
  ref           TEXT     -- o anúncio do DR; NULL numa consulta prévia
  porque_sem_ref TEXT    -- só quando ref é NULL (herdado do casa)
  lote          INTEGER  -- >=1 um lote, 0 o conjunto, NULL sem lotes
  entidade      TEXT     -- copiada à criação: uma proposta sem ref tem de a ter
  titulo        TEXT
  fase_id       INTEGER  -- as seis fases, como hoje
  responsavel   TEXT
  tipologia     TEXT     -- consulting / turnkey
  coe           TEXT
  preco_base    REAL
  valor_proposta REAL
  ebitda        REAL
  lugar         INTEGER
  top3          TEXT
  motivo_perda  TEXT
  cv            TEXT     -- sim/não
  proposta_tecnica TEXT  -- sim/não
  notas         TEXT
  fechada_em    TEXT     -- data em que entrou em Ganho/Perdido/Não fomos
  criada_em     TEXT
```

`casa` fica como está — é o registo importado do Excel, com a proveniência
e a auditoria da ligação (`ligacao`, `candidatos`, `zoho_como`). A
`propostas` é o que o painel escreve. A importação passa a **criar
propostas** em vez de ficar num bloco à parte da ficha.

### 3.2 Uma tabela `tarefas`

```
tarefas
  id INTEGER PRIMARY KEY
  proposta_id INTEGER   -- ou ref, para tarefas de um anúncio ainda sem proposta
  o_que TEXT
  quando TEXT           -- data
  quem TEXT
  feita_em TEXT
  origem TEXT           -- 'mão' ou 'automática' (prazo de esclarecimentos, entrega)
```

Os prazos que já se calculam — `prazo_de_esclarecimentos()` e o `prazo`
das propostas — geram tarefas automáticas. Uma tarefa automática cuja
data mude com uma rectificação do DR acompanha-a; uma tarefa à mão não.

### 3.3 Uma tabela `contactos` (etapa tardia, ver §4)

Pessoa, entidade (pela chave das entidades, que já existe no
`contratos.db`), papel, e-mail, telefone, notas. O CRM vive sem isto
durante as primeiras etapas; não vive sem isto ao fim de um ano.

### 3.4 O que acontece ao `estado='interessa'`

Volta a significar **uma coisa só**: a triagem disse que sim. É o lead.

A proposta cria-se por um **gesto explícito** — um botão «preparar
proposta» na ficha e na lista — e é isso que põe o cartão no quadro. Os
dois separadores deixam de mostrar o mesmo conjunto sem se inventar
recorte nenhum:

| | Anúncios | Em curso |
|---|---|---|
| O que mostra | os `anuncios` | as `propostas` |
| Aba «interessados» | leads por converter e convertidos | — |
| Fechados | não se escondem (são anúncios) | saem do funil para o arquivo |

E a aba «interessados» ganha o que lhe falta: distinguir, com uma
etiqueta, o lead que já virou proposta do que ainda está a marinar.

---

## 4. As etapas, por ordem

Esforço na escala do BACKLOG (1 ≈ ≤2 h · 2 ≈ meio dia a 1 dia ·
3 ≈ 2–3 dias · 4 ≈ 1 semana).

### Etapa 0 — o B15 leva as colunas do CRM (esforço 1)

Independente de tudo o resto, e a fazer primeiro. Fecha o §1.6.

### Etapa 1 — a tabela `propostas` e a migração (esforço 3)

Tabela nova, `iniciar_tabelas()` idempotente, migração que lê as 12
colunas do `anuncios` e cria uma proposta por cada anúncio que tenha
`fase_id` ou qualquer campo do CRM preenchido. **As colunas antigas
ficam** durante uma versão, escritas em espelho, para o restauro de uma
cópia anterior não perder nada; saem quando uma release passar.

O `_TABELAS_TRIAGEM` passa a exportar `propostas` inteira, e o
`--repor-triagem` a repô-la. Teste de ida e volta.

### Etapa 2 — o «Em curso» passa a ler propostas (esforço 3)

Quadro, calendário e lista mudam de fonte. O `/quadro/mover` e o
`/quadro/campos` passam a escrever na `propostas`. O gesto «preparar
proposta» nasce aqui, e com ele o cartão por lote.

O **arquivo**: as fases Ganho/Perdido mostram por omissão o trimestre
corrente, com um selector de período. O funil volta a caber num ecrã.

### Etapa 3 — próxima acção e cronologia (esforço 2)

A tabela `tarefas`, as tarefas automáticas a partir dos prazos, uma
coluna «o que falta fazer» no cartão, e uma vista «hoje» — que é a
primeira coisa que um comercial abre de manhã. A cronologia na ficha, a
partir do `historico`, que já lá está.

### Etapa 4 — fechar o ciclo com o Portal BASE (esforço 3)

**Isto é o que nenhum concorrente tem, e o radar já tem metade feito.**
Submetemos uma proposta; meses depois o `contratos.db` diz quem ganhou o
procedimento e por quanto. Cruza-se por entidade + objecto + data, com
o mesmo maquinário de semelhança que o `casa.py` já usa para ligar as
linhas do Excel (`LIMIAR`, `FOLGA`, `MAX_CANDIDATOS`, e a mesma exigência
de a ligação ser auditável).

O que isso dá, sem ninguém escrever nada:

- propostas paradas em «Submetido» há meses fecham-se sozinhas, com
  proposta de resultado a confirmar por um clique;
- «perdeste para a X por 18% abaixo do teu preço» — o desvio real, não a
  impressão;
- uma tabela de concorrentes por CPV e por entidade, construída da
  observação e não da memória.

**Regra:** o cruzamento **propõe**, nunca decide. Um contrato ligado por
semelhança é um candidato, e a ficha diz por que regra casou — a
armadilha do `zoho_como` foi escrita para exactamente este erro.

### Etapa 5 — indicadores comerciais (esforço 2)

O `/indicadores` de hoje mede o funil da **triagem** (`funil_anuncios()`:
quanto entra, quanto se olha, quanto vinga). Falta o do **negócio**:

- pipeline em euros por fase, e ponderado pela taxa de vitória histórica;
- taxa de vitória por CPV, por entidade, por tipologia, por CoE;
- desconto médio face ao preço base, nos ganhos e nos perdidos;
- motivos de perda agregados — já são vocabulário fechado
  (`MOTIVOS_PERDA`), logo já dão contas;
- tempo médio por fase, e quantos dias um cartão está parado.

Vale a regra da casa: **um número que um ecrã mostra tem de dar
exactamente a lista que a ligação dele abre.**

### Etapa 6 — contactos (esforço 2)

A tabela `contactos`, ligada à entidade. Depois de tudo o resto, porque
é a parte de que se sente falta mais tarde.

### Arrumação de interface, a fazer com a etapa 2

Quadro, Calendário e Lista são três recortes do mesmo conjunto e ocupam
três entradas de navegação. Passam a ser um botão de vista dentro do «Em
curso» — como as renovações passaram a `?ver=fim` dos contratos
(decisão 6.1-A). A ficha do anúncio passa a ser a página do negócio:
cronologia, peças, proposta, concorrentes.

---

## 5. O que este plano **não** faz

- **Não mexe na recolha, nem na triagem, nem nos alertas.** Nenhum
  recorte novo entra em `condicoes()`.
- **Não reintroduz fases configuráveis.** As seis são as seis, e o que
  manda é o `papel` (decisão de 1/09/2026).
- **Não abre texto livre onde há vocabulário fechado.** Motivos de
  abandono e de perda continuam listas.
- **Não põe o `contratos.db` a decidir nada.** Propõe; a confirmação é
  de quem usa.

## 6. Riscos

| | O quê | Mitigação |
|---|---|---|
| R-A | A migração perde trabalho escrito à mão | Etapa 0 primeiro; colunas antigas em espelho durante uma versão; teste de ida e volta pelo `triagem.jsonl` |
| R-B | Dois registos do mesmo facto (`casa` e `propostas`) | Decisão 2.4 antes da etapa 1: o Excel é arranque ou é fonte |
| R-C | O cruzamento com o BASE liga o contrato errado | Propõe e não decide; a ficha diz a regra que casou; limiar e folga como no `casa.py` |
| R-D | O «Em curso» fica a pedir dados que ninguém preenche | Cada campo pertence a uma fase e a mais nenhuma, como já é hoje (`_campos_da_fase()`) |

## 7. A ordem curta, se houver pouco tempo

**Etapa 0** (o B15, 2 h) → **etapas 1 e 2** (o modelo e o funil a sério,
~1 semana) → **etapa 4** (o ciclo com o BASE, o que distingue este
produto). As etapas 3, 5 e 6 melhoram; as primeiras três resolvem a
pergunta que deu origem a este ficheiro.
