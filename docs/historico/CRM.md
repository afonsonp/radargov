# Plano: o «Em curso» como CRM a sério

Escrito a **15 de setembro de 2026**, a pedido do Afonso: «precisamos de
fazer algo melhor o separador em curso. aquilo não está um verdadeiro
CRM de gestão de leads e de propostas e é estranho porque na página de
anúncios já tenho o que classifiquei como interesse.»

**Segunda versão, do mesmo dia**, depois das respostas dele. A primeira
propunha o modelo e deixava quatro decisões em aberto; ele respondeu às
quatro e acrescentou o desenho que dá nome a este ficheiro — **uma
escada só**, que é o que resolve a duplicação por construção em vez de
por filtro. O que aqui está já não tem perguntas por responder.

É um plano, não trabalho feito. Quando cada etapa se fizer, corrige-se o
`ESTADO.md`, o `docs/armadilhas.md`, o `LEIA-ME.md` e o `CLAUDE.md` no
mesmo commit; este ficheiro fica como instantâneo.

---

## 0. O que se mediu antes de propor

Base a 15/09/2026, no estado zero: **209 826 anúncios** (199 568 `novo`,
10 258 `alteracao`), **zero `interessa`**, **zero `descartado`**, zero
cartões em qualquer fase, zero linhas em `casa`.

Dois números que mandam no desenho:

- as abas de hoje dizem **Por ver 1 263 · Abandonados 198 305 · Todos
  199 568**. Os «abandonados» são **todos** anúncios que expiraram sem
  ninguém olhar — não há uma única decisão de descarte na base. São
  ruído acumulado, não história comercial;
- a plataforma **não está em uso**, é teste. Não há dados de produção a
  proteger, e é por isso que este plano pode ser radical sem ser
  arriscado (§6, risco A).

## 1. O que está errado

### 1.1 «Em curso» e «interessados» são a mesma consulta

O `/lista` faz `SELECT * FROM anuncios WHERE estado='interessa'`
(`lista_em_curso()`). A aba «interessados» faz `estado = 'interessa'`
(`condicao_da_aba()`). O `/quadro` e o `/calendario` partem do mesmo
conjunto. **São o mesmo conjunto, sempre.**

A causa não é a interface: é haver **duas escadas paralelas** para o
mesmo percurso. A da triagem (`anuncios.estado`: novo / interessa /
descartado) e a do funil (`fases`: seis colunas). Um concurso sobe as
duas ao mesmo tempo, e o topo de uma é o fundo da outra. Daí os dois
separadores mostrarem a mesma população — e nenhum desenho de ecrã
resolver isso.

### 1.2 O funil nunca esvazia

`condicao_da_aba()` diz, por escrito: «interessados: TODOS os
`interessa`». Está certo para a triagem e errado para o funil: um
concurso **Ganho** ou **Perdido** fica `interessa` para sempre. As
colunas Ganho e Perdido acumulam desde o primeiro dia, e a aba
«interessados» conta negócios fechados como se estivessem por decidir.

### 1.3 O CRM são colunas penduradas na tabela dos anúncios

Doze, em `anuncios`: `fase_id`, `responsavel`, `motivo`,
`preco_proposto`, `posicao`, `top3`, `motivo_perda`, `tipologia`, `cv`,
`proposta_tecnica`, `notas`, `coe`. Isso impõe **um anúncio = um
negócio**, e daí saem três limitações:

- **Os lotes não cabem.** Um concurso de 3 lotes pode acabar com o L1
  ganho e o L2 perdido; um anúncio, uma linha, um estado — e dois
  resultados. A decisão dele de 2/09/2026 («no final, perdido ou ganho,
  separam-se os cartões») não tem onde ser cumprida.
- **Não há negócio sem anúncio do DR.** Consulta prévia, ajuste directo,
  convite, o anterior a 2025.
- **Não há histórico por cliente.** O mesmo concurso no ano seguinte é
  outra `ref`, e nada se acumula.

### 1.4 A tabela que falta já existe

`casa` (`casa.py`) tem a granularidade do lote, a linha sem `ref`, o
resultado, o concorrente e a margem. É só-leitura, alimentada do Excel,
e mostra-se num bloco da ficha. O painel escreve nas outras doze
colunas. Dois registos do mesmo facto, que não se falam.

### 1.5 Faltam tarefas, pessoas e cronologia

Um CRM responde a «o que tenho de fazer hoje»; o quadro responde a «onde
é que as coisas estão». Não há tarefa, dono nem data. Não há o contacto
na entidade. A cronologia quase existe — o `historico` por `ref` já
grava quem fez o quê — e falta desenhá-la.

---

## 2. As decisões, respondidas

Todas do Afonso, a 15/09/2026.

**D1 — o vocabulário da casa são estas oito palavras:** *Por analisar ·
A preparar proposta · Submetido · Relatório preliminar · Ganho ·
Perdido · Não fomos · Cancelado.* O Excel e o Zoho traduzem-se para
esta lista; nenhum outro vocabulário manda.

Duas notas sobre o que isto encaixa no que já existe:

- **«Não fomos» é o «Abandonado» de hoje**, com nome novo. Já tem
  motivos de lista fechada (`MOTIVOS_ABANDONO`). É renomear, não
  construir.
- **Faltam duas ranhuras nas pontas**, e não são estados da casa — são
  o antes e o fora (§3.1).

**D2 — uma proposta sem anúncio do DR entra no painel.** Consulta
prévia, ajuste directo, convite. O «Em curso» passa a ser o pipeline
todo, e não só o que vem da parte L.

**D3 — a granularidade é o lote.** Uma proposta por lote; um cartão que
os agrupa enquanto não divergem, e que se parte quando divergirem.

**D4 — o painel manda.** O Excel serve **apenas** para importar
concursos passados a que se respondeu, e o resultado deles. Deixa de ser
sincronização; passa a ser arranque, uma vez.

**D5 — o «Cancelado» marca-se sozinho quando o DR o disser**, e o DR
quase nunca o diz. Medido a 15/09/2026: não existe tipo de anúncio para
cancelamento (os tipos são cinco: *Anúncio de procedimento* 190 291,
*Aviso de prorrogação* 14 931, *Declaração de retificação* 2 725,
*Concurso urgente* 1 791, *Consulta preliminar* 84). Quando aparece, é
texto livre e em três formas: uma retificação cujo título abre com «SEM
EFEITO ->» (**1** em 209 mil), um anúncio cujo título diz «Revogação da
Decisão de Contratar» (**4**), e o resto no corpo.

**Regra, então: só o caso explícito e inequívoco se marca sozinho, e
avisa.** Procurar por texto é traiçoeiro — `%anula%` dá 601 resultados
que são quase todos **cânulas** e «anulações de ramais». O resto é botão.

**D6 — os expirados sem ver saem da escada.** Aba discreta, fora da
escada, que não conta para lado nenhum. Não são decisão de ninguém.

**D7 — uma escada só, e três vistas.** É o desenho dele: as abas da
lista de anúncios passam a ser os estados. Consequência aceite por ele:
«vamos revolucionar a forma como o em curso aparece, inclusive o quadro,
o calendário e as listas».

---

## 3. O desenho

### 3.1 A escada

Dez ranhuras: as oito palavras da casa, e duas nas pontas que não são
estados da casa nenhum — a entrada e o cemitério.

| | Aba | O que é | A 15/09/2026 |
|---|---|---|---|
| 📥 | **Por ver** | a entrada; ainda ninguém olhou | 1 263 |
| 1 | **Por analisar** | interessa, ainda não se decidiu se se vai | 0 |
| 2 | **A preparar proposta** | vai-se, está a fazer-se | 0 |
| 3 | **Submetido** | entregue, à espera | 0 |
| 4 | **Relatório preliminar** | sabe-se o lugar, não é final | 0 |
| 5 | **Ganho** | | 0 |
| 6 | **Perdido** | com motivo (`MOTIVOS_PERDA`) | 0 |
| 7 | **Não fomos** | decidiu-se não ir, com motivo (`MOTIVOS_ABANDONO`) | 0 |
| 8 | **Cancelado** | a entidade cancelou (D5) | 0 |
| 🗑 | **Expirou sem ver** | o prazo passou e nunca foi olhado (D6) | 198 305 |

**Porque é que as duas pontas não podem ser ranhuras da escada:** sem a
entrada, os 1 263 vivos e os ~60 que chegam por dia iam parar a «Por
analisar», e o funil deixava de querer dizer o que diz. Sem o cemitério,
198 305 anúncios que ninguém olhou contavam como decisão da casa.

### 3.2 Três vistas sobre a mesma escada

| Vista | Serve | Nota |
|---|---|---|
| **Lista** | tudo, incluindo a entrada e o cemitério | é a única que aguenta 199 mil linhas, e a única onde se editam dez linhas seguidas |
| **Quadro** | as ranhuras 1 a 8 | um kanban não aguenta 198 305 cartões: a entrada e o cemitério não têm coluna |
| **Calendário** | qualquer aba que se esteja a ver | hoje só mostra interessados; os *por ver* com prazo a chegar são a fila que custa dinheiro |

O separador **Lista** do «Em curso» desaparece; a **vista** lista não —
funde-se na lista dos anúncios.

### 3.3 A navegação

Com uma escada só, «Anúncios» e «Em curso» deixam de ter razão para ser
dois sítios:

```
Concursos   ← lista · quadro · calendário, com as abas da escada
Mercado     ← contratos (como está)
```

### 3.4 O que é uma linha

A escada é o estado **do que a casa está a fazer**, não do anúncio. Na
maior parte dos casos é um para um e não se dá por isso. As excepções
são as duas que as decisões D2 e D3 obrigam:

- uma **consulta prévia** é um caso sem anúncio por trás;
- um concurso de **três lotes** parte-se em três quando os resultados
  divergirem.

Daí a tabela nova. Não é abstracção: é a resposta a «onde ponho o estado
quando ele não é um por anúncio». E a etapa 4 precisa dela — **o Portal
BASE adjudica por lote**; sem a granularidade do lote não há comparação
para fazer.

### 3.5 As tabelas

```
propostas
  id             INTEGER PRIMARY KEY
  ref            TEXT      -- o anúncio; NULL numa consulta prévia (D2)
  porque_sem_ref TEXT      -- só quando ref é NULL
  lote           INTEGER   -- >=1 um lote, 0 o conjunto, NULL sem lotes (D3)
  entidade       TEXT      -- uma proposta sem ref tem de a trazer
  titulo         TEXT
  estado         TEXT      -- uma das oito palavras de D1
  motivo         TEXT      -- porque não se foi / porque se perdeu
  responsavel    TEXT
  tipologia      TEXT      -- consulting / turnkey
  coe            TEXT
  preco_base     REAL
  valor_proposta REAL
  ebitda         REAL
  lugar          INTEGER
  top3           TEXT
  cv             TEXT      -- sim/não
  proposta_tecnica TEXT    -- sim/não
  notas          TEXT
  criada_em      TEXT
  fechada_em     TEXT      -- entrada em Ganho/Perdido/Não fomos/Cancelado

tarefas
  id INTEGER PRIMARY KEY
  proposta_id INTEGER
  ref TEXT            -- tarefa de um anúncio ainda sem proposta
  o_que TEXT
  quando TEXT
  quem TEXT
  feita_em TEXT
  origem TEXT         -- 'mão' | 'prazo' | 'esclarecimentos'

contactos             -- etapa 6
  id, entidade_chave, nome, papel, email, telefone, notas
```

O `anuncios.estado` fica com **três** valores e mais nenhum: `novo`,
`alteracao`, e `expirado` é recorte de leitura como hoje. O `interessa`
e o `descartado` deixam de existir — quem os substitui é a proposta.

`casa` fica como está: é o registo importado do Excel, com a
proveniência e a auditoria da ligação. Por D4, a importação passa a
**criar propostas** e a correr uma vez.

---

## 4. As etapas

Esforço na escala do BACKLOG (1 ≈ ≤2 h · 2 ≈ meio dia a 1 dia ·
3 ≈ 2–3 dias · 4 ≈ 1 semana).

**A etapa 0 da primeira versão saiu.** Era exportar as doze colunas do
CRM no `triagem.jsonl`, que não lá estavam (R2 reaberto em parte). Com o
modelo novo essas colunas desaparecem: exportar-se-ia trabalho para o
deitar fora a seguir. A exportação escreve-se **uma vez**, já sobre as
tabelas novas, dentro da etapa 1. O item **B15-b** do BACKLOG fecha-se
assim.

### Etapa 1 — as tabelas e o modelo (esforço 3)

`propostas` e `tarefas`, com `iniciar_tabelas()` idempotente. As funções
que criam, movem e fecham uma proposta, e o `estado_da_escada()` que dá
a ranhura de cada linha. `_TABELAS_TRIAGEM` e `--repor-triagem` passam a
levá-las.

Por **D4** e pelo §0 (base sem dados), **as doze colunas do `anuncios`
saem**, sem espelho nem período de convivência. Sai com elas a menção
delas em `CAMPOS_DA_TRIAGEM`, que é o que passa a triagem de uma
alteração para o original.

### Etapa 2 — a escada, e as três vistas (esforço 3)

A lista de anúncios ganha as dez abas. O quadro passa a ter as oito
colunas e a ler propostas. O calendário deixa de ser só dos
interessados. A navegação funde-se («Concursos»). O gesto que cria uma
proposta a partir de um anúncio, e o que cria uma proposta do nada (D2).
O arquivo: as ranhuras fechadas mostram o trimestre corrente por
omissão.

### Etapa 3 — tarefas e cronologia (esforço 2)

A tabela em uso: tarefas automáticas a partir do prazo de
esclarecimentos e da data de entrega, uma coluna «o que falta fazer» no
cartão, e uma vista **hoje**. A cronologia na ficha, a partir do
`historico`.

### Etapa 4 — fechar o ciclo com o Portal BASE (esforço 3)

O `contratos.db` diz quem ganhou o procedimento e por quanto. Cruza-se
por entidade + objecto + data **e por lote**, com o maquinário de
semelhança do `casa.py` (`LIMIAR`, `FOLGA`, `MAX_CANDIDATOS`) e a mesma
exigência de a ligação ser auditável.

O que dá, sem ninguém escrever nada — e é o que o Afonso aprovou por
estas palavras:

- propostas paradas em «Submetido» há meses fecham-se sozinhas, **com
  confirmação dele**;
- «perdeste para a X por 18% abaixo do teu preço» — o desvio real;
- uma tabela de concorrentes por cliente e por área, da observação.

**O cruzamento propõe, nunca decide** (D-C do §6, e palavra dele:
«isto avança-se sempre com a confirmação de um humano para fechar o
resultado»).

### Etapa 5 — indicadores comerciais (esforço 2)

O `/indicadores` mede o funil da **triagem** (`funil_anuncios()`). Falta
o do **negócio**: pipeline em euros por ranhura e ponderado pela taxa de
vitória; taxa de vitória por CPV, entidade, tipologia e CoE; desconto
médio face ao preço base; motivos de perda agregados; tempo por ranhura
e dias parado.

Vale a regra da casa: **um número que um ecrã mostra tem de dar
exactamente a lista que a ligação dele abre.**

### Etapa 6 — contactos (esforço 2)

`contactos` ligada à entidade. Por último, porque é do que se sente
falta mais tarde.

---

## 5. O que este plano **não** faz

- **Não toca na recolha nem nos alertas.** Entra tudo o que a parte L
  publicar; nenhum recorte novo entra em `condicoes()` — as abas da
  escada aplicam-se por cima, com `com_recorte()`, como as de hoje.
- **Não devolve as fases configuráveis.** As oito ranhuras são as oito
  (D1), e o que manda continua a ser o papel e não o nome.
- **Não abre texto livre** onde há vocabulário fechado.
- **Não deixa o Portal BASE fechar nada sozinho** (D5, e §4 etapa 4).
- **Não promete detectar cancelamentos que o DR não publica** (D5).

## 6. Riscos

| | O quê | Estado |
|---|---|---|
| **A** | A mudança perder trabalho escrito à mão | **Morto.** A plataforma é teste, a base está no estado zero: não há trabalho feito. É o que permite tirar as doze colunas sem espelho |
| **B** | Dois registos do mesmo facto (Excel e painel) | **Resolvido por D4**: o painel manda, o Excel só importa o passado e o resultado |
| **C** | O cruzamento com o BASE ligar o contrato errado | Propõe e não decide; a ficha diz por que regra casou. Palavra dele: confirmação humana, sempre |
| **D** | O painel pedir campos que ninguém preenche | Cada campo pertence a uma ranhura só, como já hoje (`_campos_da_fase()`) |

## 7. A ordem

**1 → 2** (o modelo e a escada: é aqui que os dois separadores deixam
de ser o mesmo) → **4** (o ciclo com o BASE, o que distingue este
produto dos pagos) → 3, 5, 6.
