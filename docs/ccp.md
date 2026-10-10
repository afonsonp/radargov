# O Código dos Contratos Públicos, para o Mira Gov

**É o dono do que a lei diz.** O código e os outros documentos citam o
CCP; o que o artigo diz, em que versão, e desde quando, vive aqui. Não
é instantâneo: **corrige-se quando a lei muda**, e a data de cada
secção diz quando foi conferida contra o texto oficial.

Pedido dele a 27/09/2026: «quero que tenhas o CCP bem estudado e que te
mantenhas atualizado sobre as mudanças que vão acontecer e quando».

## 1. A versão em vigor, e a que vem

*Conferido no texto oficial a 27/09/2026.*

A linha do tempo, tirada da 1.ª série do DR (pesquisa pelo sumário
«Código dos Contratos Públicos», de 2008 a hoje). Só as alterações que
ainda pesam no Código de hoje:

| Publicado | Diploma | O que fez | Estado |
|---|---|---|---|
| 29/01/2008 | DL 18/2008 | Aprova o CCP | — |
| 31/08/2017 | **DL 111-B/2017** | A grande revisão: transpõe as directivas de 2014 | Em vigor; é a base do Código de hoje |
| 21/05/2021 | **Lei 30/2021** | Medidas especiais (procedimentos simplificados) e alterações ao CCP | Os arts. 2.º a 16.º **saem a 1/10/2026** (revogados pelo DL 177/2026) |
| 7/11/2022 | DL 78/2022 | Altera a Lei 30/2021 e o CCP | Idem, na parte da Lei 30/2021 |
| 10/04/2025 | DL 66/2025 | Art. 318.º, n.º 4: o contrato pode exigir que prestações críticas sejam executadas pelo próprio cocontratante, sem subcontratar | Em vigor |
| 23/10/2025 | DL 112/2025 | Habitação pública ou de custos controlados: concurso, consulta prévia (até 1 000 000 €) e ajuste directo simplificados **até 31/12/2026**; conceção-construção mais larga (art. 43.º) | Lido na página do DR por extracção automática, não no PDF. **Esse regime vive no art. 3.º da Lei 30/2021, que o DL 177/2026 revoga a 1/10** — para procedimentos novos, acaba três meses antes do anunciado |
| 4/09/2026 | **DL 177/2026** | 17.ª alteração, **republica o Código inteiro** — §3 | **Entra em vigor a 1/10/2026** |

O PDF oficial do DL 177/2026: DR, 1.ª série, n.º 172,
https://files.diariodarepublica.pt/1s/2026/09/17200/0000200283.pdf

O que o preâmbulo do DL 177/2026 diz que muda, pelos temas dele:
princípios novos (economicidade, qualidade, «menor custo»); uso de
sistemas digitais **incluindo inteligência artificial** pelas entidades;
o princípio «só uma vez» na habilitação; o **valor estimado** redefinido
como «preço estimado a pagar»; limiares da consulta prévia e do ajuste
directo mais altos; não adjudicar por falta de «propostas
satisfatórias»; o **concurso público flexível** abaixo dos limiares
europeus (arts. 161.º-A a 161.º-E); o dever de planear as necessidades
antes de contratar; **mais peso à qualidade** na avaliação; iniciativas
espontâneas dos privados; testes gratuitos de soluções de TI; contratos
reservados a startups; as causas de exclusão todas no art. 70.º; o
concurso limitado revisto; a modificação dos contratos; a consulta
prévia **especial** (vinda da Lei 30/2021); e a arbitragem voluntária.

**A regra da transição** (art. 10.º do DL, «Aplicação no tempo»): as
alterações valem para os procedimentos **iniciados depois de
1/10/2026** e para os contratos que deles saírem. Duas matérias valem
também para os que estão em curso: a **modificação objectiva do
contrato** e a **resolução alternativa de litígios**.

**Quando é que um procedimento se inicia** (art. 36.º, n.º 1): com a
**decisão de contratar**, não com o anúncio. O Mira Gov só vê o anúncio
(«Data de Envio do Anúncio», §3), que é sempre **depois** da decisão.
Daí:

- anúncio enviado **antes** de 1/10/2026 → regime antigo, com certeza;
- anúncio enviado **depois** → quase sempre regime novo, **mas não
  garantidamente**: uma decisão de setembro pode ter anúncio em
  outubro. O Programa do Procedimento diz em que redacção se baseia.

**Consequência para o código:** durante meses o Mira Gov vê os dois
regimes e não sabe de qual é cada procedimento. **Nenhuma mensagem deve
citar um número ou alínea que mudou entre os dois** — cita-se o artigo.

## 2. Os artigos que o Mira Gov usa

*Conferido a 27/09/2026 contra a republicação.* «Alterado» quer dizer
que o DL 177/2026 lhe mexe; não quer dizer que mexe na parte que usamos.

| Artigo | O que usamos | Alterado? | No código |
|---|---|---|---|
| **50.º** | Esclarecimentos no primeiro terço do prazo das propostas (regra supletiva) | Não | `prazo_de_esclarecimentos()` |
| **135.º, n.º 1** / **136.º, n.º 1** | O prazo das propostas conta-se **da data do envio do anúncio** para publicação (no DR; com o JOUE, do envio ao Serviço das Publicações). É daí que se conta o terço do art. 50.º — a «Data de Envio do Anúncio» do §3 do DR, não a publicação. *Conferido a 10/10/2026*: no regime novo, na republicação do DL 177/2026 (PDF do DR, pág. 152); no anterior, no texto consolidado da PGDL, que dá o art. 135.º alterado só pelo DL 111-B/2017 | Não (o 136.º, n.º 4 é revogado; não é o que usamos) | `prazo_de_esclarecimentos()`, `SQL_DO_ENVIO` |
| **70.º** | A proposta acima do preço base é excluída | **Sim — mudou de sítio**: era o n.º 2, al. d); passa a **n.º 3, al. d)**. O n.º 2, al. d) novo é «não constituídas por todos os documentos exigidos» | `recusa_do_preco()` e os dois avisos do preço, que desde 27/09/2026 citam só «art. 70.º» |
| **71.º** | Preço anormalmente baixo: a entidade *pode* fixar o limiar no PP; sem ele, pode considerá-lo na mesma, fundamentando; o concorrente é sempre ouvido antes | Sim — não se conferiu em que parte | A pergunta ao modelo sobre o Programa |
| **147.º** | Audiência prévia: prazo fixado pelo júri, não inferior a cinco dias | Não | `DIAS_DE_PRONUNCIA`, `prazo_de_pronuncia()` |
| **470.º** | Os prazos contam-se pelo art. 87.º do CPA (dias úteis) | Não | idem |
| **47.º** | Preço base | **Sim: passa a facultativo** («pode fixar»); os n.os 3 a 6 são revogados | `recusa_do_preco()` não recusa sem base — certo nos dois regimes |
| **17.º** | Valor estimado do contrato = «preço estimado a pagar»; indica-se no convite ou no programa (§3-A) | **Sim** | `preco_estimado` (`campos_do_detalhe()`), que nunca vai para o `preco_base` |
| **74.º** | Critério de adjudicação (multifator / monofator) | Sim | `criterio_de_adjudicacao()` lê o anúncio, não a lei |
| **88.º** | Caução: dispensável quando o preço contratual for inferior a **1 000 000 €** (regime novo, n.º 2, al. a)) | Sim | Ainda não se mostra (`docs/historico/SETORES.md` §6) |

## 3. O que muda a 1/10/2026 e toca o produto

*Cada linha conferida no texto oficial a 27/09/2026, com o artigo
republicado.* Os valores **antigos** não se conferiram — o DL só traz os
novos.

| O quê | Regime novo | Artigo |
|---|---|---|
| Preço base | Facultativo | 47.º, n.º 1 |
| Ajuste directo / consulta prévia — bens e serviços | abaixo de **75 000 €** / **130 000 €** | 20.º, n.º 1, als. c) e d) |
| Ajuste directo / consulta prévia — empreitadas | abaixo de **150 000 €** / **1 000 000 €** | 19.º, als. c) e d) |
| Caução dispensável | preço contratual abaixo de **1 000 000 €** | 88.º, n.º 2, a) |
| Não dividir em lotes tem de se fundamentar | acima de **250 000 €** (bens e serviços) e **500 000 €** (obras) | 46.º-A, n.º 2 |
| Exclusão acima do preço base | passa ao n.º 3, al. d) | 70.º |
| Anexos I, II, V e XIII do CCP | **revogados** | 8.º do DL, al. a) |
| Lei 30/2021 (medidas especiais) | os arts. 2.º a 16.º revogados | 8.º do DL, al. b) |
| Portaria 372/2017 (habilitação) | **continua em vigor** até sair a portaria nova do art. 81.º, n.º 2 | 7.º do DL, n.º 1 |
| Concurso público **flexível** (abaixo dos limiares europeus) | A entidade pode tirar ou pôr formalidades: requisitos mínimos de capacidade técnica e financeira verificados na análise das propostas, avaliação faseada, leilão, negociação | 161.º-A |
| Audiência prévia no concurso flexível | O prazo de pronúncia pode descer a **três dias** | 161.º-B, n.º 1, b) |

### 3-A. O preço estimado

*Conferido no texto oficial (PDF do DR, republicação) a 1/10/2026.*

- **Art. 17.º, n.º 1:** «O valor estimado do contrato corresponde ao
  preço estimado a pagar pela entidade adjudicante e por terceiros»,
  mais as contraprestações e vantagens do adjudicatário. É o mesmo
  conceito com outro nome: o preâmbulo diz que substitui o «valor do
  contrato» (o «valor máximo do benefício económico»). **Não há um campo
  «preço estimado» à parte do valor estimado.**
- **Art. 17.º, n.º 2:** o valor estimado «deve ser indicado no convite
  ou no programa do procedimento». É aqui que a lei o torna obrigatório
  — nas peças, não no anúncio. Os n.os 3 a 6, 8 e 9 são revogados (art.
  8.º, al. a), do DL).
- **Art. 17.º-A, n.º 2** (novo): num acordo-quadro, o valor estimado é o
  máximo de todos os contratos previstos durante a vigência.
- **Arts. 115.º, n.º 1, al. d) (convite), 132.º, n.º 1, al. e)
  (programa do concurso público) e 164.º, n.º 1, al. e) (programa do
  concurso limitado):** devem indicar «o valor estimado do contrato ou,
  se for o caso, o preço base». Lido à letra, o programa pode dar um ou
  o outro — não diz que dá os dois.
- **Art. 47.º, n.º 1:** a entidade «pode fixar» o preço base, «o
  montante máximo que esta entidade se dispõe a pagar». **Art. 70.º, n.º
  3, al. d):** exclui-se a proposta cujo preço contratual seria superior
  ao preço base. Sobre o estimado não há causa de exclusão: **o estimado
  não é tecto.**
- **O anúncio:** o art. 130.º, n.º 1 (não alterado) remete o conteúdo
  do anúncio do concurso público para um «modelo aprovado por portaria»
  (e o mesmo para os outros procedimentos). **O DL 177/2026 não aprova
  modelo novo nem fala da portaria dos anúncios** — a norma transitória
  (art. 7.º) só mantém a Portaria 372/2017, a da habilitação. Qual é a
  portaria dos modelos em vigor, e se saiu uma nova, **não se conferiu**
  no DR.

**O que os anúncios já trazem (medido a 1/10/2026, os 71 desse dia):**
o formulário do DR mudou nesse dia. A secção 5 ganhou «Regime de
flexibilização do concurso público» e **«Valor do preço estimado do
procedimento»** (56 dos 71); em **55 vem «0,00 EUR»** e só em um
(24414/2026) vem um valor, igual ao preço base. Três dos 71 dizem
«Preço base do procedimento: Não»: um acordo-quadro com o máximo
estimado de 13 M€ (24394/2026) e duas actualizações de sistemas de
qualificação sem valor nenhum. Os de 30/09 ainda têm a forma antiga.
A lei não obriga o estimado no anúncio, e o formulário deixa-o a zero:
**o sítio certo para o procurar continua a ser o Programa.**

**O que a §3 obrigou a rever no código (feito a 4/10/2026, decisão
dele):** o `DIAS_DE_PRONUNCIA` = 5 é o mínimo do art. 147.º, e num
concurso flexível o mínimo passa a três. Quando o anúncio diz
«Regime de flexibilização do concurso público: Sim» (`e_flexivel()`), a
tarefa da audiência conta `DIAS_DE_PRONUNCIA_NO_FLEXIVEL` = 3 e diz
porquê, e a ficha avisa na célula «Propostas até». Continua a mandar
confirmar o prazo na notificação.

**O que isto pode fazer ao volume da parte L:** com os limiares da
consulta prévia muito mais altos, o que passar a consulta prévia não
se publica em anúncio. **Medir** os anúncios de outubro e novembro de
2026 contra os mesmos meses de 2025 antes de concluir — é hipótese, não
facto.

## 4. O que está marcado para depois

| Quando | O quê |
|---|---|
| **1/10/2026** | DL 177/2026 (§3); saem os arts. 2.º a 16.º da Lei 30/2021 |
| **31/12/2026** | Fim anunciado do regime simplificado da habitação do DL 112/2025 — mas ver a §1: nos procedimentos novos já acaba a 1/10 |
| **1/01/2028** | Próxima revisão bienal dos limiares europeus (art. 474.º) — data pelo ciclo da Comissão, não por diploma publicado |
| Sem data | O resto da tabela abaixo |

| O quê | Porque importa | Como se sabe que saiu |
|---|---|---|
| A **portaria nova do art. 81.º, n.º 2** (os documentos de habilitação) | Substitui a 372/2017; muda o que a empresa entrega depois de ganhar, e o cofre dos documentos | DR, 1.ª série: «Portaria» + «artigo 81.º do Código dos Contratos Públicos» |
| A **revisão dos limiares europeus** (art. 474.º) | Decide o que vai ao JOUE. A Comissão revê-os de dois em dois anos, por regulamento delegado, com efeito a 1 de janeiro. **O texto republicado ainda reproduz os montantes com a redacção dos regulamentos de 2019** (obras 5 404 000 €; bens e serviços do Estado 139 000 €) — confirmar contra o regulamento em vigor antes de citar | JOUE, «Regulamento Delegado» + «limiares» |
| Os **valores das classes do alvará** (Lei 41/2015) | O semáforo das obras, se o cofre um dia guardar a classe | Portaria anual do IMPIC |
| Uma **18.ª alteração** ao CCP | — | DR, 1.ª série: «Código dos Contratos Públicos» |

## 5. Como me mantenho actualizado

Uma sessão não se lembra da anterior: o que eu sei do CCP é o que está
**aqui**. Por isso:

1. **Uma verificação periódica** procura no DR e no JOUE o que a tabela
   da §4 diz para procurar, e alterações novas ao CCP. Quando encontra,
   corrige este ficheiro por PR — com o artigo conferido no texto
   oficial, não numa síntese.
2. **Antes de escrever uma frase que cite o CCP** em código ou em
   documentação, confere-se aqui; se o artigo não estiver na §2,
   lê-se no texto oficial e acrescenta-se.
3. **Uma síntese não é fonte.** A Procurai (https://procurai.pt/ccp)
   serve para achar; o que se escreve aqui leu-se no DR.
