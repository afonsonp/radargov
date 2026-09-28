# A leitura das peças, validada — 28/09/2026

*Instantâneo: descreve o dia em que foi escrito e não se edita. O que a
leitura faz hoje está no `docs/FUNCIONAL.md` §3.6; o que não é óbvio,
nas armadilhas, «O modelo que lê as peças».*

## A pergunta

«Presta a leitura das peças pelo modelo?» — o ponto que faltava para a
v1 desde 3/09/2026. Respondeu-se antes de anunciar o Mira Gov, a pedido
do Afonso: «valida a leitura das peças, usa vários agentes com
diferentes perfis».

## Como se fez

Quatro agentes, cada um com o perfil de quem decide naquele tipo de
concurso, correram o `ensaio-de-leitura --sem-modelo` nas **70 leituras
guardadas** e conferiram cada campo no texto das peças (os ZIP também,
que o guião não abre):

| Perfil | Concursos | Confiáveis sem abrir as peças |
|---|---|---|
| Bid manager de TI | 18 | 1 (mais 7 com uma vista de olhos ao título) |
| Director de equipa de TI | 18 | 1 completa; 4 servem para decidir a capacidade |
| Director técnico de obras | 17 | 1 |
| Jurista de contratação pública (serviços e bens) | 17 | 2 (mais 7 com lacunas menores) |

As leituras julgadas foram feitas com instruções de datas diferentes,
várias anteriores às de 28/09 (o campo 11 conforme o tipo de contrato).

## O que se encontrou

**O defeito é a omissão, não a invenção.** Factos errados houve poucos:
um técnico de helpdesk em vez de oito (21724), os «perfis» que eram os
departamentos da entidade que vão usar o sistema (23804), licenças para
50 utilizadores quando eram 10 (22036), o Anexo II no lugar do III
(23610, 23612). O grande é o **«não consta» falso**: a leitura diz que
não há equipa, lista de documentos ou limiar de preço, e há — só não
leu essa parte. O jurista: **em 7 de 17, uma empresa que preparasse a
proposta só pela ficha entregava uma proposta a excluir** (art. 146.º,
n.º 2, d)). Quando lê a parte certa, lê bem: as listas de documentos
lidas são quase sempre fiéis.

As causas, medidas:

1. **Só os títulos ancoravam.** «2. A proposta deve ser constituída, sob
   pena de exclusão, pelos seguintes documentos:» acaba em dois pontos —
   não é título, e a lista ficava fora do recorte.
2. **O sumário sem pontinhos** («7. DOCUMENTOS DA PROPOSTA 5») vinha
   primeiro e levava a janela do artigo.
3. **O orçamento cortava por posição.** As janelas escolhiam-se por
   prioridade, mas o texto saía pela ordem do documento e um `[:tecto]`
   no fim deitava fora a última — muitas vezes a tabela dos perfis, no
   último anexo.
4. **Documentos que não se reconheciam pelo nome**: «Anexo.1-CdE»,
   «CADE», «Pograma», o «Convite» das consultas.
5. **A equipa só se procurava no Caderno**, e estava no Programa (nos
   requisitos mínimos ou nos critérios: ISO 27001, CISM, PMP, ITIL).
6. **O mesmo documento duas vezes** (o PDF e o que vem no ZIP) gastava
   metade do recorte.
7. **Nas obras faltavam o alvará e a caução** — e estão no anúncio do
   DR (§12 e §14), sem modelo.
8. **A ficha afirmava uma leitura que não houve**: com o Programa ausente
   das peças, dizia «o Programa foi lido e a leitura não encontrou».

## A régua

Para medir sem gastar orçamento de modelo: **59 passagens** que os
agentes provaram estar nas peças, e a pergunta «esta passagem chega ao
modelo?» (está no recorte que a leitura manda). Quatro saíram por serem
injustas — só estão no anúncio, numa folha de preços ou no índice das
peças, que por desenho não se lêem. Ficaram 55.

| | Chegam ao modelo |
|---|---|
| O código de 28/09, antes | 20 de 55 (36%) |
| Depois das correcções | **46 de 55 (84%)** |

As nove que faltam: a morada que vem numa cláusula de notificações e não
na do local; a lista de uma obra de 190 mil caracteres; o limiar de
preço anormalmente baixo escrito dentro do critério; um Programa
digitalizado com OCR estragado; e a equipa de dois concursos de
serviços, onde as âncoras da família ainda não apanham a zona.

## O que mudou no código

As oito causas, uma a uma: as âncoras de **peso 0** (frases do corpo),
o sumário repetido que cede ao corpo, a **escolha das janelas pela
densidade** das âncoras com o orçamento cortado na escolha, os nomes das
peças, o Programa aberto por acrescento na leitura da equipa (e o
Caderno na do Programa, só pelo que as âncoras apanharem), os
documentos repetidos, a habilitação e a caução do anúncio no essencial
da ficha, e o `None` para «não lido». As perguntas ao modelo passaram a
pedir a quantidade de cada perfil, os anos junto da tecnologia, o que
se contrata na primeira linha do objecto sem as cláusulas de rotina, e
os documentos de habilitação fora da lista da proposta. A ficha passou a
dizer, em cada linha lida, «é um rascunho: confirmar no documento antes
de decidir».

## O que fica para depois

Reler as 70 com o código novo e voltar a pôr os quatro perfis a julgar
— a régua mede se a resposta chega ao modelo, não se o modelo a
escreve bem.
