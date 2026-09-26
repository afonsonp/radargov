# A leitura e a proposta à medida do setor — investigação

**27/09/2026.** É a sessão de investigação que o Q3 do `BACKLOG.md`
pedia antes de se construir alguma coisa, com a D6 da segunda ronda
(o semáforo «Podemos concorrer?») lá dentro. **Não se construiu nada:
o desenho é decisão do Afonso** (§6). Como todo o `docs/historico/`, é
um instantâneo — descreve este dia e não se edita.

Duas fontes, e nunca misturadas:

- **Medido**: as nossas bases, só leitura, na manhã de 27/09/2026 — os
  32 050 anúncios de procedimento de 27/09/2025 a 26/09/2026, as 70
  leituras pelo modelo e o texto das 436 peças em disco (79 concursos).
- **Investigado**: a lei (o CCP e os diplomas de cada setor) e a prática
  de mercado, por um agente na web, com as fontes em §5. **Prática não é
  lei**, e as tabelas dizem qual é qual.

## 1. O que já está no anúncio, e o radar não mostra

O anúncio do DR não é texto livre: é um formulário por secções
numeradas, e o `campos_do_detalhe()` já as parte. Medido nos 32 050:

| Secção | Presente | O que traz |
|---|---|---|
| §6 «Tipo de Contrato Principal» | 99% | Bens 13 600 · Serviços 10 680 · Empreitada 6 638 · Locação 624 · Concessões 185 |
| §12 Documentos de habilitação | 99% | «Habilitação para a actividade profissional: Sim» em **7 788**; o tipo: Alvará 5 550, Outros 1 806, Certificado 264, Ordem Profissional 176 |
| §14 Prestação de caução | 99% | «Sim» em **8 929**, e a percentagem vem sempre: 5% em 7 569, 2% em 864, 10% em 109 |
| §21 Critério de adjudicação | 99% | Multifator em **9 519** — **todos** com as ponderações em %; monofator (preço) em 22 264 |
| §26 Contrato adequado para PME | 99% | Sim em 25 018 |
| §5 Procedimento com lotes | 99% | Sim em 8 971 |

E por tipo de contrato:

| Tipo | Pede habilitação | Pede caução | Multifator |
|---|---|---|---|
| Empreitada de obras públicas | **81%** | **68%** | 30% |
| Aquisição de serviços | 14% | 21% | 28% |
| Aquisição de bens móveis | 6% | 14% | 32% |

**Dos 5 574 que pedem alvará, 3 833 (69%) escrevem a categoria ou a
classe na descrição da §12** — texto livre («Alvará de construção com a
1.ª subcategoria da 1.ª categoria, classe 2…»), mas está lá.

**O que a ficha faz hoje com isto:** o critério aparece no essencial,
com as ponderações (`criterio_de_adjudicacao()`, em
`essencial_do_anuncio()`). **A caução e a habilitação não** — só no
anúncio completo, em bruto, e com as secções fechadas. A metade da D6
que dizia «mostrar na ficha os requisitos que o DR já traz» é, afinal,
**leitura de campos que já temos, sem modelo e sem custo**.

## 2. O setor reconhece-se sem modelo

A dúvida do Q3 era «como se reconhece o setor — pelo CPV?». Medido: **o
tipo de contrato e a divisão do CPV concordam quase sempre.**

- 6 637 das 6 638 empreitadas têm CPV 45; dos 6 662 com CPV 45, 6 637
  são empreitadas.
- Divisão 72 (TI): 1 374 de 1 376 são aquisição de serviços. 33
  (equipamento médico): 5 291 de 5 314 são bens. 90, 71, 79, 50, 85,
  60: acima de 99% serviços.
- A excepção que se vê: a 55 (restauração) é concessão em 72 de 459.

O tipo de contrato separa obras, bens e serviços; a divisão (e às
vezes o grupo) do CPV separa os serviços entre si. Com cinco famílias:

| Família | Regra | Anúncios | % |
|---|---|---|---|
| **Bens** | Aquisição ou locação de bens | 14 224 | **44%** |
| **Obras** | Empreitada ou concessão de obras | 6 663 | **21%** |
| **Serviços com equipa** | CPV 72, 71, 73, 80, 794 (TI, projectos, consultoria, formação) | 3 062 | **10%** |
| **Mão-de-obra** | CPV 9091 (limpeza), 7971 (segurança), 55 (refeições) | 1 287 | 4% |
| Outros serviços | O resto (manutenção 50, seguros 66, transportes 60, saúde 85…) | 6 814 | 21% |

Os limites da regra, pela investigação: há CPV genéricos (79000000,
50000000) e mal escolhidos (software em 48 ou em 72, manutenção em 50 ou
em 45). Os «outros serviços» são o saco onde isso cai — 21% é o preço
de não afinar mais. **Afinar é acrescentar prefixos, não modelo.**

## 3. A leitura de hoje foi desenhada para 10% dos anúncios

A leitura pelo modelo faz três pedidos, e os três pensam em serviços
de TI: o `INSTRUCOES_OBJECTO` pede o regime **presencial, remoto ou
híbrido**; o `INSTRUCOES_EQUIPA` pede os **perfis** com formação,
experiência e certificações; e a proposta tem `TIPOLOGIAS` =
`consulting` / `turnkey`, e os campos `cv` e `proposta_tecnica`.

Medido nas 70 leituras, pelo tipo de contrato do anúncio:

| Tipo | Leituras | «Equipa» encontrada | «Local» encontrado |
|---|---|---|---|
| Aquisição de serviços | 45 | 19 | 12 |
| Empreitada | 17 | **0** (16 «não consta», 1 vazia) | 0 |
| Aquisição de bens | 6 | **0** | 0 |

**E as peças dessas empreitadas têm equipa.** Procurado no texto das
peças em disco, por concurso:

| Nas peças de… | director de obra | alvará | categoria/classe | técnico de segurança | plano de trabalhos | amostras | fichas técnicas |
|---|---|---|---|---|---|---|---|
| 19 empreitadas | **19** | **19** | **18** | 14 | 19 | 15 | 11 |
| 54 aquisições (bens e serviços) | 0 | 3 | 2 | 1 | 2 | 13 | 6 |

Numa empreitada, a «equipa» é o director de obra e o técnico de
segurança, com o alvará da empresa; o modelo, perguntado por **perfis
com formação e anos de experiência**, responde «não consta» — e a ficha
diz «a leitura não encontrou requisitos de equipa», que é falso. É o
mesmo erro que o teste de 25/09 apanhou («não fixa requisitos de
equipa»), agora com a causa: **a pergunta, não o modelo.**

A contagem é por expressão regular sobre o texto das peças; diz que a
palavra lá está, não que é um requisito de exclusão. Serve para medir o
desencontro, não para decidir por ninguém.

## 4. O que decide um go/no-go, por família

### Comum a todos (lei)

| O quê | Artigo do CCP | Onde está |
|---|---|---|
| Critério e ponderações | 74.º, 139.º | Anúncio §21; o modelo de avaliação (escalas, fórmula do preço) no PP |
| Preço base | 47.º; acima dele exclui (70.º, n.º 2, d)) | Anúncio |
| Preço anormalmente baixo | 71.º — a lei não fixa percentagem; o PP pode | PP (já se lê) |
| Caução | 88.º–91.º — até 5% (10% se o preço for anormalmente baixo) | Anúncio §14, com a % |
| Habilitação profissional | 81.º; Portaria 372/2017 | Anúncio §12; a lista no PP |
| Requisitos mínimos de capacidade | 164.º–165.º (concurso limitado) | PP |
| Esclarecimentos | 50.º — primeiro terço do prazo | PP (a ficha já calcula a regra supletiva) |
| Lotes | 46.º-A | Anúncio §5 |
| Visita ao local | **não é lei**: é o PP que a prevê, às vezes como condição | PP |

### Por família

| Família | O que decide | Lei ou prática |
|---|---|---|
| **Obras** | Alvará do IMPIC com a categoria e subcategoria da obra principal **numa classe que cubra o valor** (Lei 41/2015); director de obra e técnico de segurança; prazo de execução; plano de trabalhos; lista de preços unitários; erros e omissões | O alvará e a classe são **lei**; a equipa técnica é quase sempre exigida no PP |
| **Bens** | Prazo e local de entrega; quantidades; fichas técnicas e amostras; marcação CE; garantia e assistência. **Não há equipa nem CV** | Marcação CE e dispositivos médicos (INFARMED, Reg. 2017/745) são **lei**; o resto é do CE |
| **Serviços com equipa** | Perfis, CVs, anos de experiência, certificações (ISO 27001, de fabricante), referências — quase sempre como **subfactor** e raramente como exclusão. Projectos e fiscalização: inscrição na OA/OE (Lei 31/2009) | A inscrição é **lei**; os perfis são prática |
| **Mão-de-obra** | Custo laboral pelo CCT do setor contra o preço base — é aqui que o **preço anormalmente baixo** decide (71.º); **transmissão de trabalhadores** (art. 285.º do Código do Trabalho); segurança privada: **alvará da PSP** (Lei 34/2013); refeições: HACCP | Alvará da PSP e HACCP são **lei**; o custo laboral é o que exclui na prática |
| Outros serviços | O comum, e o que o CE disser | — |

### A lei muda daqui a quatro dias

O **DL n.º 177/2026, de 4/09** (17.ª alteração ao CCP) entra em vigor a
**1/10/2026** e aplica-se aos procedimentos **iniciados a partir dessa
data** — durante meses o radar vai ver anúncios dos dois regimes.
Confirmado na síntese da Procurai; o PDF do DR não se leu. O que toca
no Mira Gov, pela mesma síntese:

- **O preço base passa a facultativo** (47.º), e sem ele não há exclusão
  por preço. O `recusa_do_preco()` já não recusa sem base conhecida —
  está certo para os dois regimes.
- A **dispensa de caução** sobe de 500 000 € para 1 000 000 €; o
  **limiar dos lotes** em bens e serviços de 135 000 € para 250 000 €.
- O ajuste directo e a consulta prévia sobem para **75 000 € e
  130 000 €** em bens e serviços e **150 000 € e 1 000 000 €** em
  empreitadas. **Isto pode tirar anúncios à parte L** — o que passa a
  ser consulta prévia não se publica lá. Vale medir o volume de
  outubro contra o de outubro de 2025.
- As declarações-tipo dos anexos I, II e V da habilitação são
  revogadas, e a entidade passa a obter os documentos ela própria.
- O PP passa a trazer a **lista dos trabalhadores transmissíveis** —
  exactamente o que a família mão-de-obra precisa de ler.

## 5. Fontes

- DL 177/2026 (síntese artigo a artigo): https://procurai.pt/ccp/revisao-2026
  — o PDF oficial: https://files.diariodarepublica.pt/1s/2026/09/17200/0000200283.pdf
- CCP, artigos: https://procurai.pt/ccp/artigo-74-criterio-de-adjudicacao,
  https://procurai.pt/ccp/artigo-71-preco-ou-custo-anormalmente-baixo,
  https://procurai.pt/ccp/artigo-88-funcao-da-caucao,
  https://procurai.pt/ccp/artigo-46-a-adjudicacao-por-lotes
- Portaria 371/2017 (os modelos de anúncio):
  https://diariodarepublica.pt/dr/detalhe/portaria/371-2017-114350956
- Lei 41/2015 (alvarás): https://diariodarepublica.pt/dr/detalhe/lei/41-2015-67377968

**Ficou por confirmar:** os valores das classes do alvará para 2026 (a
classe 1 era 200 000 € e cada uma dobra, com actualização por
portaria); os prazos mínimos dos arts. 135.º-136.º; os diplomas dos
transportes; e o que os concorrentes (a Vortal, a BidPortugal, a
Tenderbase) fazem de pré-qualificação. A SpotGov anuncia a verificação
dos documentos exigidos — ver o `CONCORRENTES.md`, que é de outro dia.

## 6. Proposta — em três degraus, por ordem de custo

Cada degrau vale sozinho, e o de baixo não espera pelo de cima.

**Degrau 1 — o que o anúncio já diz, na ficha (sem modelo).**
Três linhas novas no essencial, ao lado do critério: **Habilitação**
(o tipo e a descrição da §12 — onde a classe já vem em 69% dos
alvarás), **Caução** (sim/não e a %), e **Família** (§2). E o semáforo
«Podemos concorrer?» contra o cofre, só no que se compara sem
interpretar: o anúncio pede alvará e o cofre tem um válido → verde;
não tem, ou caducou → vermelho. **A classe não se compara hoje**: o
cofre guarda o tipo, a descrição e a validade, não a categoria nem a
classe. *É uma sessão.*

**Degrau 2 — a leitura pergunta conforme a família.**
O `INSTRUCOES_EQUIPA` passa a ter uma versão por família: nas obras,
o director de obra, o técnico de segurança e as categorias do alvará;
nos bens, em vez de equipa, prazos de entrega, amostras, fichas
técnicas e garantia; na mão-de-obra, os postos, as horas e a
transmissão de trabalhadores. O pedido do Programa ganha a
**habilitação e os requisitos mínimos** (alvará, seguros,
certificações, volume de negócios, referências), para todas.
O custo é o de hoje: continua a ser um pedido por campo. *Uma sessão, e
uma segunda para julgar as releituras com o `ensaio-de-leitura`.*

**Degrau 3 — a proposta pede conforme a família.**
O `cv` e a `proposta_tecnica` só nos serviços com equipa; a
`TIPOLOGIAS` (`consulting` / `turnkey`) só nas TI. *Depois do
degrau 2, para se ver primeiro o que as leituras trazem.*

### O que é preciso decidir

1. **As cinco famílias servem?** Ou os «outros serviços» (21%) partem-se
   já — a manutenção (50) e os transportes (60) são os maiores.
2. **O cofre ganha a categoria e a classe do alvará?** Sem isso, o
   semáforo das obras diz «tem alvará», nunca «tem a classe que chega».
3. **O semáforo é da empresa ou do anúncio?** Um cliente que só faz TI
   não precisa de ver «não tem alvará» em cada obra: o interesse já o
   recorta, mas a ficha de uma obra aberta por engano diria vermelho.
4. **Reler as 17 empreitadas e os 6 bens** depois do degrau 2 (gasta
   orçamento do modelo) ou só as que entrarem na escada.
