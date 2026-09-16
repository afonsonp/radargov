# design.md

O caminho para o aspecto da aplicação. Escrito a **16/09/2026**, a
pedido do Afonso: «a aplicação tem aspecto de 2002 e eu quero 2026 —
dá-me um caminho, não uma opinião por ecrã».

Este ficheiro é a decisão. O que se vê está em **`/amostra`**, que
mostra os componentes todos num sítio e deixa trocar o lettering e a
pele para comparar. **Nenhum ecrã muda enquanto ele não disser qual
serve.**

As medidas de interface anteriores estão em
`docs/historico/UX-Auditoria.md` (2/09/2026) e as regras que já
existem em `docs/armadilhas.md`, área «A interface». Este documento
não as revoga: acrescenta a camada que faltava, que é a de aspecto.
Onde colidem, diz-se aqui e diz-se porquê.

---

## 1. O diagnóstico, medido

Não é «feio» em abstracto. São seis coisas concretas, e cinco delas
medem-se.

**a) Não há sistema tipográfico.** A letra é a do sistema
(`system-ui`), que no Ubuntu dele é outra coisa que no telemóvel e
outra no browser de um cliente. E os tamanhos declarados no CSS são
**dezanove valores diferentes entre 9 e 34px**, sem escala: 10,
10.5, 11, 11.5, 11.8, 12, 12.5, 13, 13.5, 14… Degraus de meio pixel
não são hierarquia, são ruído. Quem olha não consegue ordenar o que
vê porque a diferença entre um rótulo e um valor é 0,5px e um tom de
cinzento.

**b) Não há superfícies, há riscos.** Tudo é `#fff` sobre `--papel`
com uma moldura de `1px solid var(--linha)`. Uma página densa fica um
campo de rectângulos do mesmo tom separados por fios cinzentos — que é
literalmente o aspecto de uma tabela de 2002. Não há nada que diga
«isto está por cima daquilo».

**c) A cor não quer dizer nada de fixo.** Há `.bt`, `.bt.forte` (azul)
e `.bt.verde`, e é tudo. «Interessa» e «Abandonar» são os dois
contornos cinzentos numa lista onde essa é a decisão do dia. Não há
maneira de ver, sem ler, o que confirma e o que desfaz.

**d) Rótulos em maiúsculas espaçadas, por todo o lado.** «PUBLICADO»,
«PREÇO BASE», «A NOSSA PROPOSTA», «PROCEDIMENTOS HOMÓLOGOS»,
«HISTÓRICO DE ADJUDICAÇÕES». Foi o maneirismo dos painéis de 2012 e
hoje data a página à distância. Além disso obriga a letra a descer aos
9–10px para caber, o que foi a origem de metade dos problemas de
contraste que a auditoria de 31/08 apanhou.

**e) O ecrã explica-se a si próprio.** Dezassete páginas abrem com um
parágrafo `p.subtit` a dizer o que a página é, e há mais **68 blocos
`.nota`** dentro delas. Para quem chega uma vez é útil. Para quem abre
isto duas vezes por dia é uma linha a menos de trabalho no ecrã, todos
os dias, para sempre.

**f) O calendário está construído ao contrário.** Medido no browser,
na base verdadeira, em `/calendario?estado=porver`:

| | |
|---|---|
| Linhas | 1 086 |
| Células de dia desenhadas | **48 870** |
| Células com alguma coisa lá dentro | 1 086 — **2,2%** |
| HTML da página | **2,0 MB** |
| Altura da página | **86 915 px** |
| Palavras diferentes nas pílulas | **uma** («prazo», 1 086 vezes) |

Ver a §8.

---

## 2. A direcção: «instrumento»

O radar é uma ferramenta de trabalho diário sobre 209 895 anúncios,
não um sítio para visitar. A direcção não é «mais bonito», é **mais
legível com a mesma densidade**. Seis regras. Tudo o resto sai delas.

**1. A hierarquia é tipográfica, não cromática.** Seis degraus de
tamanho com razão entre eles, três pesos, cinco tons de texto. Quem
olha ordena o ecrã pelo tamanho e pelo peso, antes de ler.

**2. Uma cor só entra quando quer dizer alguma coisa.** Cinzento é o
estado normal do mundo. Azul é «podes fazer isto». Verde, laranja e
vermelho são estados do negócio. Nada é colorido para ficar bonito.

**3. As superfícies separam-se por tom, não por risco.** Três níveis —
fundo, superfície, encaixe. O fio de `1px` fica só onde separa *dados*
(linhas de tabela, colunas), não para desenhar caixas.

**4. Os números alinham por algarismo.** Dinheiro, prazos, datas,
referências e CPV são metade do que este ecrã mostra. Algarismos
tabulares em toda a aplicação, e a coluna do dinheiro alinhada à
direita. É a diferença entre uma tabela que se compara de relance e
uma que se lê linha a linha.

**5. O ecrã não se explica.** O texto que ensina existe, é bom, e vive
**num sítio só**: atrás de um «?» no título, dobrado por omissão. Ver
a §9.

**6. A densidade não se toca.** 2026 não é mais espaço em branco. Com
1 269 anúncios por ver, dar 8px de respiro a cada linha custa-lhe um
ecrã inteiro de rolagem por cada dez anúncios. O ganho vem da letra,
do contraste e da cor com significado — não de afastar as coisas.

---

## 3. O lettering

### O que ele escolheu

**IBM Plex Sans** para a interface, **IBM Plex Mono** para números,
referências e códigos — **decisão dele a 16/09/2026**, depois de ver as
três na amostra («prefiro a segunda, a do IBM»). As duas de licença
aberta (OFL), servidas **da própria aplicação** — a regra «o painel não
pede nada a nenhum domínio de fora» (armadilha de 14/09/2026, com o CSP
a dizer `font-src 'self'`) mantém-se intacta: os ficheiros vivem em
`tipo/` e são 124 KB ao todo.

A proposta escrita aqui tinha sido a Inter, e a escolha dele é melhor
do que o argumento que eu tinha usado contra ela — que estava
**errado**. Medido no browser, com as duas fontes mesmo carregadas (a
primeira medição comparou a Plex com uma substituta, porque
`document.fonts.ready` não descarrega uma família que a página não usa
— é preciso `document.fonts.load()`):

| a 13px, a mesma frase | largura | altura-de-x |
|---|---|---|
| Inter | 637,3 px | 54 |
| **IBM Plex Sans** | **602,6 px** | 52 |
| Sistema | 593,8 px | 52 |

A Plex **não é mais larga: é 5,4% mais estreita** do que a Inter. O que
ela tem a menos é altura-de-x, e por isso lê-se 3,8% mais pequena ao
mesmo tamanho. Corrigido isso — Plex a 13,5px contra Inter a 13px, o
mesmo tamanho óptico — dá 625,7 contra 637,3: **continua 1,8% mais
estreita**. Das três, é a que cabe mais texto por linha ao mesmo
tamanho aparente, que na regra 6 (a densidade não se toca) é o
argumento que conta.

O resto do que a recomenda:

- **Uma família só** cobre o texto e os números. A Plex Mono é a irmã
  desenhada da Plex Sans, e a referência (`23012/2026`), o CPV e o
  preço deixam de ser de outra casa.
- **Tem voz, e é a voz certa.** Ligeiramente institucional, de
  engenharia — assenta num radar de contratação pública melhor do que
  a neutralidade da Inter.
- **É variável**: 46 KB cobrem todos os pesos, o que deixa usar 550 ou
  620 onde hoje se usa 600 porque só há 600.

A consequência prática está na §6: **a escala sobe meio pixel**, porque
a escala tinha sido desenhada para a altura-de-x da Inter.

A frase de prova da amostra leva os diacríticos todos do português —
`ã õ ç á é í ó ú à â ê ô` — porque o subconjunto «latin» de uma fonte
web não é sempre o que promete, e uma cedilha em falta só se vê no dia
em que aparece um «Direcção-Geral».

A `/amostra` mantém as três opções, para se poder voltar a comparar; a
escolhida é a que abre.

---

## 4. A cor

A paleta antiga chamava-se «ardósia e âmbar» (31/08/2026). Os tons não
estavam errados; o que estava errado era haver **dois patamares** —
`--t1..--t4` passavam AA em todos os fundos e `--t5`/`--t6` só nalguns.
Isso já causou três falhas de contraste documentadas (as
`.coluna-pede`, a 2/09) porque quem escreve um `--t5` novo não sabe
sobre que fundo ele vai cair.

**A escala nova tem cinco degraus e todos passam AA sobre todos os
fundos que existem na aplicação.** Medido, não estimado — sobre fundo,
superfície, encaixe e os quatro fundos de nota:

```
              fundo   sup     sup2    azul-f  verde-f lar-f   verm-f
--t1 #111418  17,08   18,47   16,19   16,11   16,00   16,33   15,93
--t2 #343a42  10,61   11,48   10,06   10,01    9,94   10,15    9,90
--t3 #4a515b   7,41    8,02    7,03    6,99    6,94    7,09    6,91
--t4 #5a626d   5,71    6,17    5,41    5,38    5,35    5,46    5,32
--t5 #646d7a   4,84    5,24    4,59    4,57    4,54    4,63    4,52

--azul    #1b5fc1   pior caso 5,24
--verde   #12704a   pior caso 5,26
--verm    #b3261e   pior caso 5,64
--laranja #9a4a06   pior caso 5,40
```

Pior caso de toda a paleta: **4,52**. O `--t6` desaparece: um sexto tom
de cinzento que só funciona em metade dos fundos é uma armadilha, não
um degrau.

As superfícies:

| Token | Valor | Onde |
|---|---|---|
| `--fundo` | `#f5f6f8` | o fundo da página |
| `--sup` | `#ffffff` | cartões, linhas, a ficha |
| `--sup2` | `#eef0f4` | encaixes: cabeçalho de tabela, campo em repouso, coluna |
| `--linha` | `#e3e6eb` | fio entre dados |
| `--traco` | `#c3c9d2` | decoração: setas, molduras tracejadas |

A regra antiga mantém-se e fica mais fácil de cumprir: **cor de texto
e cor de decoração são escalas diferentes.** Um `--t*` nunca desenha um
risco; um `--traco` nunca escreve uma palavra.

### O que cada cor quer dizer

| Cor | Significado | Exemplos |
|---|---|---|
| **Azul** `--azul` | Podes fazer isto. Acção, ligação, o que está seleccionado | Filtrar, Gravar, Entrar, os links |
| **Verde** `--verde` | Correu bem, ou avança no negócio | Interessa, Submetido, Ganho, «adjudicação nossa» |
| **Laranja** `--laranja` | Atenção, sem ser um erro. Sai do fluxo sem apagar | Prazo a chegar, Abandonar, Descartar, «falta o proposto» |
| **Vermelho** `--verm` | Perdeu-se, ou destrói | Prazo expirado, Perdido, Apagar, Estado zero |
| **Cinzento** | Tudo o resto | O estado normal de uma linha |

Isto é uma regra, não uma sugestão: **uma cor nova precisa de um
significado novo.** Se o significado já existe, usa-se a cor que já o
diz.

---

## 5. Os botões

Cinco classes. Um botão diz o que faz **pela cor e pelo preenchimento**,
antes de se ler a palavra.

| Classe | Aspecto | Função | Exemplos |
|---|---|---|---|
| `.bt.forte` | azul cheio | **A acção principal do bloco.** Uma por bloco | Filtrar · Gravar · Entrar · Trazer peças |
| `.bt.ok` | verde cheio | **Confirma e avança no negócio** | Interessa · Marcar ganho · Submeter |
| `.bt` | contorno neutro | **Secundário.** Cancelar, voltar, alternativas | Limpar · Voltar · Ver no DR |
| `.bt.cuidado` | contorno laranja → laranja cheio ao passar | **Sai do fluxo, mas não apaga nada** | Abandonar · Descartar · Pôr por ver |
| `.bt.perigo` | contorno vermelho → vermelho cheio ao passar | **Irreversível. Destrói dados** | Apagar contacto · Apagar alerta · Estado zero |

Duas decisões dentro disto, e ambas têm razão de ser:

**Os dois perigosos começam em contorno e só se enchem ao passar por
cima.** Um botão vermelho cheio numa lista de vinte linhas é um alvo —
puxa o olho e convida ao clique errado, que é exactamente o contrário
do que uma acção irreversível quer. Contorno vermelho lê-se como
«vermelho» à mesma, sem gritar. Enche ao passar e ao receber o foco,
que é quando a pessoa já está a decidir.

**`.bt.cuidado` é laranja e não vermelho** porque abandonar **não
apaga nada** — a própria aplicação já o diz no pop-up do motivo, e
repõe-se numa linha. Pintar de vermelho uma coisa reversível gasta o
vermelho, e depois não sobra cor para o que apaga mesmo.

Uma regra que já existia e passa a ter dentes: **uma acção principal
por bloco** (Von Restorff, medido na UX-Auditoria). Com cinco classes é
mais fácil quebrá-la por distracção, por isso: `.bt.forte` e `.bt.ok`
são os únicos cheios, e **num bloco só pode haver um cheio**.

---

## 6. A escala tipográfica

Dezanove tamanhos passam a **seis**, com razão entre degraus.

| Degrau | Tamanho | Peso | Onde |
|---|---|---|---|
| `--f6` | 25 | 680 | O título da página |
| `--f5` | 17.5 | 620 | Título de anúncio, título de bloco |
| `--f4` | 15 | 400 | Texto corrido, valores da ficha |
| `--f3` | 13.5 | 500 | O texto da interface: botões, abas, linhas de lista |
| `--f2` | 12.5 | 500 | Metadados: entidade, data, plataforma |
| `--f1` | 11.5 | 550 | Etiquetas, contadores, pílulas |

**Os valores são os da Plex, não os da Inter.** A primeira versão desta
escala era 11 / 12 / 13 / 14.5 / 17 / 24, desenhada para a altura-de-x
da Inter (54). A Plex tem 52, e ao mesmo tamanho lê-se 3,8% mais
pequena — a 11px uma etiqueta perdia legibilidade onde ela é mais
apertada. Subir meio pixel repõe o tamanho óptico e **não custa
densidade**: a §3 mede que a Plex a 13,5px é 1,8% mais estreita do que
a Inter a 13px.

Meio pixel dentro de uma escala de seis valores não é o «ruído de meio
pixel» do diagnóstico (§1a). Lá eram dezanove valores sem relação
nenhuma entre si; aqui são seis degraus com razão, deslocados todos
pela mesma razão e por um motivo medido.

**As maiúsculas espaçadas saem.** Um rótulo de bloco passa a ser `--f2`
em `--t4`, caixa normal, com peso 600. Lê-se melhor, ocupa menos, e
deixa de obrigar a letra a descer para caber.

O que **não muda**: um alvo de texto continua a ter 24px de altura
(`TestAlvosDeTextoA24px`), com a letra que tiver. A escala nova não
mexe nisso.

---

## 7. O que se mantém, e não se discute outra vez

A auditoria de 2/09/2026 já decidiu estas, e continuam certas:

- **Alvos de 24px, não 44.** Nenhum ecrã é para toque (E3 do BACKLOG).
- **Nada de «optimistic updates» na triagem.** O que falta é
  confirmação, e já existe (o `.flash` com «desfazer»).
- **O pop-up do motivo do abandono fica.** Não é uma confirmação, é
  recolha de um dado.
- **A página de alertas pode ter 19 campos.** É a página avançada.
- **Abaixo de 900px a barra é uma linha e o que é largo rola dentro de
  si, nunca a página.** A medida é `scrollWidth == 375`.
- **Toda a truncagem passa por `corta()`** ou por `text-overflow`.
- **Nada vem de fora.** Agora inclui as fontes, que são servidas de
  `tipo/`.

---

## 8. O calendário

### O que lhe está errado

**Está a usar a forma de um Gantt para desenhar pontos.** Uma grelha
de «uma linha por coisa × uma coluna por dia» serve para mostrar
**intervalos** — quando uma coisa começa e acaba, e como se sobrepõem.
Um prazo de concurso não é um intervalo: é um dia. Desenhar um ponto
numa grelha de 45 colunas gasta 44 células para não dizer nada.

Os números estão na §1f. O que eles significam, na prática:

- **A página é 98% vazia** e pesa 2 MB. Desenha 48 870 divisões para
  mostrar 1 086 factos.
- **Tem 87 000 px de altura.** Para ver o que fecha daqui a três
  semanas, ele rola verticalmente por mil linhas *e* horizontalmente
  por 45 colunas. A informação que ele quer — «o que fecha a 3 de
  Outubro» — está espalhada por uma coluna de mil pixéis de altura com
  um ponto de 20px algures lá dentro.
- **A pílula diz sempre a mesma palavra.** Nos anúncios o rótulo é
  `"prazo"`, fixo, 1 086 vezes. A única informação da célula é a
  *posição*, e a posição já está no cabeçalho da coluna.
- **Não responde à pergunta de um calendário.** Está ordenado por
  prazo, uma linha por concurso: isso é uma **lista ordenada por data**
  com 48 000 células desenhadas à volta. A pergunta que um calendário
  responde é a inversa — «que dia é que está carregado?», «há dois a
  fechar na mesma manhã?». Essa lê-se por dia, e o ecrã não tem o dia
  como unidade.
- **E o ecrã por omissão está vazio.** Sem `?estado=`, mostra as
  propostas em aberto — que hoje são zero. O calendário que ele abre
  diz «Nada com prazo em o que a casa tem em aberto» (com o «em o»
  incluído).

### O que o substitui

**A unidade passa a ser o dia, não o concurso.** Uma grelha de semanas
— seis semanas, `Seg` a `Dom` — em que cada célula é um dia e dentro
dele estão as coisas que fecham nesse dia, por ordem. O choque de
datas, que é a razão de ser da página, passa a ver-se por a célula ter
três coisas em vez de uma.

O que isso resolve, ponto por ponto:

| Hoje | Depois |
|---|---|
| 48 870 células, 2,2% cheias | 42 células, e só se desenha o que existe |
| 87 000 px, rola nos dois eixos | cabe num ecrã, sem rolagem lateral |
| A pílula diz «prazo» | a célula diz o título e a entidade |
| Ordenado por data = uma lista | o dia é a unidade, e a carga do dia vê-se |
| Vazio por omissão | um dia sem nada é um dia, não um erro |

Um dia com mais coisas do que cabem mostra as três primeiras e «+4»,
que abre o dia. E mantém-se o que já estava certo: sábados e domingos
distinguem-se, hoje marca-se, e cada linha liga à ficha.

**Isto é um ecrã, e por isso espera pela ordem dele** — está aqui
escrito para ele decidir, como ele pediu («diz-me o que lhe está
errado antes de o refazeres»).

---

## 9. Os descritivos

Saem do ecrã e **não se apagam**. O texto é bom e um utilizador novo
— um tester, quando isto for multi-empresa — precisa dele.

A mecânica é uma só, aplicada no `envolver()`, que serve as 17
páginas: o `p.subtit` passa a viver dentro de um `<details
class='porque'>` cujo resumo é um **«?»** ao lado do título. Fechado
por omissão; o browser lembra-se por página (`localStorage`), como já
faz com os filtros.

Os 68 blocos `.nota` dentro das páginas tratam-se um a um, na passagem
ecrã a ecrã (§11), com este critério:

- **Fica** o que diz de onde vem um número ou o que ele não inclui
  («3 contratos desta entidade neste CPV — de 3 983 ao todo»). Isso é
  um dado, não uma explicação.
- **Vai para o «?»** o que diz o que a página é ou para que serve.
- **Apaga-se** o que descreve o que já se vê («Cada secção grava só o
  que mostra»).

---

## 10. A página de abertura

Hoje `/` é a lista dos concursos. Passa a ser **o estado do negócio
mais o que há para fazer**, que é o que ele pediu (ponto 6) e o que o
`/hoje` fazia antes de sair.

Isto mexe em mais coisas do que parece — `NAV`, `ITEM_DA_PAGINA`,
`PAGINAS_COM_VERIFICAR`, as migalhas, e os redireccionamentos de
`/anuncios` e `/lista` que apontam para `/`. Por isso é uma fase
própria (§11, fase 4) e não um efeito lateral do aspecto.

O desenho proposto, para ele ver antes:

1. **Quatro números do negócio**, que são os que já existem em
   Indicadores: em jogo (€), taxa de vitória, por decidir, a fechar
   esta semana. Cada um liga à lista que o produz — a regra da casa.
2. **O que tenho de fazer**, que é o `agenda()` que está no histórico
   do git: as tarefas das propostas mais os prazos a chegar, num só
   sítio, por dia. Atrasadas primeiro.
3. **O que entrou desde a última vez** — uma linha, com a ligação para
   o por ver.

A lista dos concursos passa a ter endereço próprio e continua a ser o
primeiro item da barra.

---

## 11. A ordem de trabalho

| Fase | O que é | Muda ecrãs? |
|---|---|---|
| **0** | `docs/design.md` e `/amostra` — as fontes, a paleta, os botões, a escala | **Não** |
| **1** | Aplicar a camada: fontes, tokens, escala, botões. Uma bandeira que se liga de uma vez | Todos, ao mesmo tempo |
| **2** | Os descritivos para trás do «?» (§9) | Todos, uma linha no `envolver()` |
| **3** | O calendário (§8) | Um |
| **4** | A abertura (§10) | Um novo, e a navegação |
| **5** | Passagem ecrã a ecrã, um de cada vez, com antes e depois | Um de cada vez |

A fase 0 é o que está feito. **Cada fase corre na instalação dele
antes de se dizer que está feita** — com os 209 895 anúncios, não com
três linhas de ensaio.

---

## 12. Os testes que isto obriga a mexer

Quatro, e todos por boas razões:

- **`TestContrasteNosFundosReais`** — deixa de ter dois patamares e
  passa a ter um: **tudo passa AA sobre tudo**. O teste fica mais
  simples e mais apertado.
- **`TestPaginaSemNadaDeFora`** — continua a valer, e passa a ter mais
  uma coisa a guardar: as fontes são servidas de `tipo/`, e o CSP
  continua a dizer `font-src 'self'`.
- **`TestAlvosDeTextoA24px`** — não muda. A lista de selectores cresce
  se entrar um botão de texto novo.
- **`TestEcraEstreito`** — a grelha nova do calendário é um
  `display:grid` com colunas de largura fixa, que é exactamente o
  padrão que já apanhou a escada de preços e as barras do funil. Entra
  na lista.
