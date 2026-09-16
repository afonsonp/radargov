# design.md

O caminho para o aspecto da aplicação. Escrito a **16/09/2026**, a
pedido do Afonso: «a aplicação tem aspecto de 2002 e eu quero 2026 —
dá-me um caminho, não uma opinião por ecrã».

Este ficheiro é a decisão. O que se vê está em **`/amostra`**, que
mostra os componentes todos num sítio e deixa trocar o lettering e a
pele para comparar.

**As seis fases estão feitas** (16/09/2026): ele viu a amostra,
escolheu a letra («prefiro a segunda, a do IBM») e disse «avança». A
camada está aplicada aos ecrãs todos. O diagnóstico da §1 descreve o
que **estava** antes disso — é o registo do que se mediu, não o estado
de hoje. A ordem do que falta está na §11.

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
  preço deixam de ser de outra empresa.
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

### O `.mini` é o botão da linha, e tem as mesmas cinco classes

`.bt` é o botão **da página**; `.mini` é o botão **da linha**. A
diferença não é só o tamanho: numa lista de vinte linhas com dois
botões cada, encher quarenta botões de cor faz quarenta alvos e
hierarquia nenhuma. Por isso **no `.mini` a regra dos perigosos vale
para todos**: contorno com a cor do significado, e enche ao passar por
cima ou ao receber o foco. Cheio só o `.bt.forte` e o `.bt.ok`, que são
um por bloco.

E o `.mini` **deixou de ficar vermelho ao passar por cima**. Ficava, em
todos — no «ir» do selector de ranhura, no «desfazer», no «X lotes» —,
que é o ponto (c) do diagnóstico em estado puro: a cor de alarme a sair
em coisas que não alarmam nada, e por isso a não querer dizer nada onde
devia.

Isso destapou um erro escondido. O botão que **apaga uma conta** em
Configurações › Conta era um `.mini` simples, e só *parecia* certo
porque o `.mini` ficava vermelho em tudo. Tirado esse vermelho, ficava
igual ao «desfazer». Leva agora `.mini.perigo`, e o que o marca é a
classe e não um acidente — com teste
(`test_quem_apaga_uma_conta_leva_a_classe_do_perigo`).

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
  diz «Nada com prazo em o que a empresa tem em aberto» (com o «em o»
  incluído).

### O que o substitui

**A unidade passa a ser o dia, não o concurso.** Uma grelha de semanas
— seis semanas, `Seg` a `Dom` — em que cada célula é um dia e dentro
dele estão as coisas que fecham nesse dia, por ordem. O choque de
datas, que é a razão de ser da página, passa a ver-se por a célula ter
três coisas em vez de uma.

O que isso resolve, ponto por ponto:

**Feito a 16/09/2026** (fase 3). Medido na mesma base, na mesma
página, antes e depois:

| | Antes | Depois |
|---|---|---|
| Células desenhadas | 48 870 | **42** |
| Cheias | 2,2% | **88%** (37 dos 42 dias) |
| HTML | 2,0 MB | **380 KB** |
| Altura | 86 915 px | **1 254 px** |
| Rolagem | vertical **e** horizontal | cabe num ecrã |
| A célula diz | «prazo», 1 086 vezes | o título e a entidade |
| Servidor | — | 66 ms |

**As células são sempre 42**, venham dez linhas ou dez mil — é essa a
propriedade que impede a forma antiga de voltar por distracção, e é o
que `TestCalendarioEPorDiaENaoUmGantt` fixa.

Quatro decisões que se tomaram a fazê-lo:

- **A grade começa na segunda-feira desta semana**, não em «hoje». Uma
  grade de semanas que comece a uma quarta não se lê como um
  calendário. Os dias já passados desta semana ficam lá, apagados: um
  prazo de terça que hoje é quinta ainda explica o que aconteceu.
- **A urgência é do dia e não de cada linha.** No mesmo dia todas as
  linhas são igualmente urgentes, e por isso a cor está no número do
  dia e não em vinte e seis pílulas iguais. A conta é a mesma do resto
  da aplicação (`dias_urgente()`, janela única), para a cor aqui e a
  etiqueta da lista nunca discordarem sobre o mesmo prazo.
- **O «+N» abre no sítio, com um `<details>`, e não liga à lista.**
  A tentação era `/?de=<dia>&ate=<dia>` — mas esses dois filtros são
  por **`data_pub`** e não por `prazo`: a lista que abriam não era a
  que o número prometia, que é exactamente a avaria que a regra da empresa
  proíbe. Nada se perde: o que não cabe está no `<details>`, e há teste.
- **As abas da escada entraram**, sem números. Sem elas, o calendário
  por omissão mostra as propostas em aberto — que hoje são zero — e a
  única saída era escrever `?estado=` na barra de endereços. Sem
  números porque o número que faria sentido aqui não é o total da
  ranhura mas quantos têm prazo dentro das seis semanas: outra conta,
  onze vezes por pedido. Entre um número que abre outra coisa e nenhum
  número, a regra da empresa escolhe o segundo.

E abaixo de 900px **a grade rola dentro de si** (`min-width:840px`,
120px por coluna). Sete colunas em 375px dão 49px e o título sai
«Ex…» — a mesma avaria do calendário antigo, que mostrava «A pr…» numa
célula de 52px. Medido: a página fica em 375, a célula em 119.

---

## 9. Os descritivos

Saem do ecrã e **não se apagam**. O texto é bom e um utilizador novo
— um tester, quando isto for multi-empresa — precisa dele.

**Feito a 16/09/2026** (fase 2). A mecânica é uma só, aplicada no
`envolver()`, que serve as 17 páginas: o `<h1>` vai **dentro** do
`<summary>` — que o HTML permite, porque o modelo de conteúdo do
`summary` aceita um elemento de cabeçalho — e leva um «?» ao lado. A
linha inteira do título alterna, e o texto aparece por baixo. Nativo,
sem JS.

Duas decisões dentro disto:

- **Sem memória.** A ideia escrita aqui era lembrar por página, como os
  filtros fazem. Está errada: um «?» que se lembra de estar aberto
  volta a pôr o parágrafo no ecrã todos os dias, que é exactamente o
  que isto vem tirar. Fechado por omissão, sempre.
- **Sem subtítulo não há «?».** Algumas páginas passam `""` — a ficha
  do anúncio, por exemplo. Um `<details>` que abre nada é um controlo
  morto, e a empresa não põe controlos mortos no ecrã.

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

**Feita a 16/09/2026** (fase 4). `/` é a abertura, a lista vive em
`LISTA` (`/concursos`) e a barra ganhou um primeiro item, **Hoje** —
que é a primeira intenção: chegar e ver como está.

1. **Quatro números**: em jogo (€), taxa de vitória, por decidir, para
   fazer.
2. **O que tenho de fazer**, em **quatro baldes** e não por data:
   atrasadas · hoje · nos próximos 7 dias · mais para a frente. Uma
   lista ordenada só por data põe o atrasado de ontem a seguir ao de
   hoje, o que é verdade e não ajuda — o que está atrasado é outra
   categoria, não um dia pior.
3. **O que entrou desde a última vez** — uma linha, com a última
   verificação.

Três decisões que se tomaram a fazê-la:

- **Só a tabela `tarefas`, e não os prazos dos anúncios por cima.** As
  tarefas automáticas já trazem os prazos do DR
  (`sincronizar_tarefas()`), por isso somá-los aqui era contá-los duas
  vezes — e juntar os mil «por ver» afogava as dez que são mesmo
  trabalho. A pressão do «por ver» está no KPI que lhe é próprio.
- **O «Para fazer» conta as linhas que mostra, e o destino é elas.**
  Esteve a contar só as dos próximos dias (6 de 8) e a ligar ao
  `/calendario`, que mostra **prazos** e não tarefas: duas avarias
  numa, e a mesma que se apanhou no «+N» do calendário no mesmo dia. O
  destino passou a ser uma âncora para a lista que está na própria
  página.
- **A saudação acompanha a hora.** «Bom dia» às 14h está errado, e um
  título errado metade do dia é pior do que nenhum.

O «Em jogo» aponta aos Indicadores e não a uma lista: é a soma de
quatro ranhuras e não há lista única que o dê. Apontar a uma parecida
seria pior — a regra é apontar ao ecrã que o **decompõe**, e a nota
di-lo.

A lista dos concursos continua a ser o item a seguir ao Hoje, e
`/anuncios` e `/lista` redireccionam para o endereço novo. O endereço
entrou como **constante** `LISTA` e não como literal: eram 56 sítios a
escrever `"/"` e nem todos queriam dizer a lista — uns queriam dizer
«volta ao princípio», que agora é outra página.

---

## 11. A ordem de trabalho

| Fase | O que é | Muda ecrãs? | Estado |
|---|---|---|---|
| **0** | `docs/design.md` e `/amostra` — as fontes, a paleta, os botões, a escala | **Não** | **feita** 16/09 |
| **1** | Aplicar a camada: fontes, tokens, escala, botões | Todos, ao mesmo tempo | **feita** 16/09 |
| **2** | Os descritivos para trás do «?» (§9) | Todos, uma linha no `envolver()` | **feita** 16/09 |
| **3** | O calendário (§8) | Um | **feita** 16/09 |
| **4** | A abertura (§10) | Um novo, e a navegação | **feita** 16/09 |
| **5** | Passagem ecrã a ecrã, um de cada vez, com antes e depois | Um de cada vez | **feita** 16/09 |

### Fase 5 · os ecrãs, um a um

| Ecrã | Quando | O que mudou |
|---|---|---|
| **Ficha do anúncio** | 16/09 | O índice passou a cobrir a página; cinco blocos ganharam «?» |
| **Lista dos concursos** | 16/09 | Saiu a memória do painel de filtros (−125px); a definição da aba saiu da linha do resumo |
| **Mercado** | 16/09 | Saiu a duplicação barra/abas; a pergunta dobra-se quando já foi feita (−182px) |
| **Configurações** | 16/09 | Os Indicadores deixaram de ser tratados como afinação; o subtítulo era falso |
| **Lista das propostas** | 16/09 | As colunas seguem a ranhura; os testes deixaram de ler o `config.json` dele |

**Cada fase corre na instalação dele antes de se dizer que está
feita** — com os 209 895 anúncios, não com três linhas de ensaio.

A **fase 1** foi três linhas de código e não uma: os moldes são
**três**, não um. O `BASE` monta a barra e lê a sessão, mas a página de
entrar (`PAGINA_ENTRAR`) e as de erro (`PAGINA_ERRO`) vivem fora dele
de propósito — um 500 a meio do `BASE` dava outro 500 em cima do
primeiro. Carimbar só o `BASE` deixava o login e os erros com o aspecto
antigo, que é o género de coisa que ninguém vê até ao dia em que vê.
`TestPeleNova` passou a exigir os três.

E a fase 1 desfaz-se apagando dois atributos: é por isso que o `CSS`
antigo fica como estava, com os testes que o medem intactos, e que
nenhuma regra do `CSS_NOVO` pode ficar fora do âmbito.

---

## 11b. A ficha do anúncio (fase 5, primeiro ecrã)

**O índice não cobria a página.** Prometia seis destinos e a ficha tinha
oito blocos com âncora. Faltavam o **`#proposta`** — que é onde vive o
trabalho da empresa, o bloco mais importante do ecrã — e o `#contactos`. Um
índice que salta por cima de um bloco é a mesma mentira de um número que
abre outra lista: promete o mapa da página e não o é. O teste não fixa a
lista de entradas, fixa a **propriedade**: toda a âncora que a página tem
está no índice, e o índice não promete nenhuma que não exista.

**Onze notas a explicar cada bloco**, e a triagem foi a da §9, não uma
limpeza cega. Cinco blocos ganharam «?» — Lotes, Peças, Procedimentos
homólogos, Histórico de adjudicações, Contactos — e três não, por não
terem explicação a esconder. O que **ficou no ecrã**:

- «2 lotes; sem registo de a que fomos» — é um facto.
- «Parecido = tem em comum estes termos do título: …» — diz **como** a
  lista foi feita; sem ele o bloco é uma tabela sem critério.
- «3 contratos desta entidade no CPV X · de 3 983 ao todo» — de onde vem.
- «O preço contratual é o de partida, não o valor final» — o que o
  número **não** inclui.
- «Guardadas em documentos/…» — de onde vem.

O que foi para o «?» diz o que o bloco **é**: «as edições anteriores, com
quem ganhou e por quanto», «não são oportunidades — servem para saber com
quem se concorre», «de <entidade>, e não deste concurso», «o radar vai à
plataforma ver se há peças novas…». Nada se apagou — a primeira versão
desta passagem **apagou** a nota da vigilância das peças, que explica um
comportamento que não se vê em mais lado nenhum; foi reposta no «?».

**E um erro latente saiu com o teste**: um anúncio sem `url` derrubava a
ficha inteira com um 500 (`html.escape(None)` no «Ver no DR»). Na base
dele todos têm `url` e por isso nunca se viu, mas um NULL numa coluna que
ninguém garante não pode derrubar a página toda.

## 11c. A lista dos concursos (fase 5, segundo ecrã)

**O maior ganho deste ecrã foi apagar código.** O painel de filtros
lembrava-se, em `localStorage`, de ter ficado aberto — para sempre e em
todas as abas. Bastava filtrar uma vez, num dia qualquer, para a lista
abrir com o painel aberto todos os dias a partir daí. Medido na
instalação dele:

| | Com a marca | Sem ela |
|---|---|---|
| O primeiro cartão começa aos | **409 px** | **284 px** |
| Alvos na primeira dobra | 47 | 50¹ |
| Cartões por ecrã (1440×950) | 9,2 | 9,2 |

¹ sobem porque entram mais cartões no ecrã — cada um traz dois botões.

São **125 px, mais do que um cartão inteiro**, por uma marca que ninguém
sabia que tinha. E o recolhimento existia precisamente porque a
UX-Auditoria mediu «a lista abre com 60% do ecrã em filtros».

O sinal certo já existia e é do servidor: o painel abre quando **há
filtro aplicado**. Uma memória por cima disso nunca ajuda — é a mesma
razão por que o «?» do título também não tem memória (§9). Verificado
nos dois sentidos: com `?cpv=` abre, sem filtro fecha, e não fica marca
nenhuma guardada.

**E a definição da aba saiu da linha do resumo.** Dizia «só o que ainda
dá para responder, e por decidir», que é quase palavra por palavra o que
o «?» do título diz. O que o P4 da UX-Auditoria pedia — que o `1 268`
não pareça o acervo todo — continua cumprido pelo «209 903 na base» que
vem imediatamente antes: era a definição que estava a mais, não o
denominador. A linha ficou só com factos: ordem, intervalo, página,
denominador.

**Duas coisas que verifiquei e não mexi**, por a medição as ter
desmentido:

- **As etiquetas do cartão não são ruído.** Parecia que «Anúncio de
  procedimento» estava em todos; medido, são 12 de 20, e as outras 8 são
  «Consulta preliminar». A plataforma varia do mesmo modo (14 de 20). As
  três dizem alguma coisa.
- **O teclado (`j k i a Enter`) não se partiu** com a mudança de
  endereço da lista — confirmado no browser, dois `j` movem o foco dois
  cartões.

## 11d. O Mercado (fase 5, terceiro ecrã)

**A mesma escolha estava no ecrã duas vezes, a 40px de distância e com
nomes diferentes.** A barra dizia `Mercado › Contratos · Renovações` e
as abas da página diziam `Por celebração · Por fim estimado` — são os
**mesmos dois modos**, e com rótulos distintos liam-se como quatro
opções quando são duas. E as sub-vistas da barra só aparecem depois de
se entrar no Mercado, que é exactamente onde as abas também estão: não
eram atalho de lado nenhum.

Saíram da barra. A distinção que fica, e que é coerente:

- uma **sub-vista na barra** é uma *forma diferente de olhar* — o
  Calendário dos Concursos, que é uma grelha de dias;
- **dois modos da mesma tabela** são abas.

Tirá-las destapou que o `ITEM_DA_PAGINA` e as migalhas eram derivados
das sub-vistas: a barra deixou de acender e as migalhas passaram a dizer
«Radar». A barra é hierarquia **por cima** das páginas, não um nome novo
para elas, e agora há um recuo para as páginas que vivem num item sem
serem vista dele.

**E a pergunta dobra-se quando já foi feita** — o **inverso** da lista
dos anúncios, e não a mesma regra aplicada duas vezes:

| | Lista dos anúncios | Mercado |
|---|---|---|
| Sem filtro | 1 268 anúncios para triar → filtros **fechados** | não mostra nada → campos **abertos** |
| Com filtro | os filtros continuam fechados; abre-os quem quer | a resposta é o que interessa → campos **dobrados** |

Medido na instalação dele, com `?cpv=71318100`:

| | Antes | Depois |
|---|---|---|
| O primeiro contrato começa aos | **700 px** | **518 px** |
| (a lista dos anúncios, para comparar) | — | 284 px |

São **182 px** de nove campos e uma caixa de pesquisa já respondidos,
com o CPV activo declarado na sua própria banda logo abaixo. O resumo
fica no `<summary>`: «Perguntar outra coisa · CPV 71318100».

Verificado nos dois modos e a 375px.

## 11e. As Configurações (fase 5, quarto ecrã)

Medidas as nove secções antes de olhar para alguma, e o que saltou não
foi o aspecto: **uma das nove não é uma configuração.**

| Secção | Campos | Letras |
|---|---|---|
| Alertas | 17 | 1 786 |
| **Indicadores** | **0** | 1 981 |
| Conta | 9 | 721 |
| Recolha · Leitura | 7 · 7 | 603 · 622 |
| Cópias | 3 | 901 |
| Capturas | 4 | 364 |
| Interesse | 3 | 236 |
| Importar | 1 | 480 |

Os **Indicadores não têm um único campo de formulário** — são nove
blocos de números — e estavam debaixo de um subtítulo que prometia «cada
secção grava só o que mostra». Uma página de **leitura** num menu de
afinação, com o ecrã a dizer o contrário do que ela faz. Vieram da barra
a 13/09 e o sítio serve; o que estava errado era chamar-lhes
configuração.

Duas correcções, as duas pequenas:

- **O subtítulo perdeu a metade falsa.** «Cada secção grava só o que
  mostra» descrevia o que já se vê (§9) e, pior, era **mentira** para
  uma das nove.
- **O `SECCOES_CONFIG` ganhou uma quinta coluna**, «grava alguma
  coisa», e a que só lê fica apartada no fim do menu, por um risco. Um
  menu que as pinte iguais diz que os Indicadores são uma coisa que se
  afina.

**E aqui parei de aplicar o critério da §9**, de propósito. As notas por
baixo de cada campo — «um por dia, a partir da hora marcada», «os campos
dos contratos não avisam de nada», «enquanto estiver vazio, a ficha
pergunta» — **ficam todas**. Numa página de configuração o texto está ao
lado do controlo que governa, e é no momento de mexer nele que faz
falta: não é a página a descrever-se, é o campo a dizer o que faz, e
algumas avisam de coisas que não se adivinham. A §9 é sobre páginas e
blocos que se explicam, não sobre rótulos de campo.

**Decidido por ele no mesmo dia** («põe os indicadores no hoje, à
excepção dos indicadores da curl, plataformas, BASE, DR»). A divisão é
essa, e é boa:

| Vai para **Hoje** | Fica em **Configurações** |
|---|---|
| O negócio (em jogo, taxa, desconto) | Estado da recolha (as duas capturas cURL, a última verificação, as horas) |
| Em jogo, por ranhura | As plataformas, em percentagem do que tem detalhe lido |
| Porque se perde · Porque não se vai | Corpus de contratos (Portal BASE) |
| Há mais tempo sem se mexerem | Os quatro números do acervo |
| Funil da triagem | |
| Propostas por ranhura | |

O critério: **como vai o negócio** vive onde ele chega; **se a máquina
está boa** fica onde se vai de vez em quando.

Três consequências:

- O KPI «Em jogo» **deixou de sair da página**: apontava aos
  Indicadores para se decompor, e o bloco que o decompõe está agora na
  mesma página (`#negocio`). Um número que manda o leitor para outro
  ecrã para se explicar é um número que o manda embora.
- O `numeros_do_negocio()` é **função própria com as suas consultas**, e
  não metade de uma que calcula as duas: a abertura é a página em que
  ele aterra duas vezes por dia, e fazer-lhe as contas do estado das
  plataformas para não as mostrar era pagar o que não se usa.
- A etiqueta «Interessados por fase do **quadro**» passou a «Propostas
  por ranhura» — o quadro saiu a 15/09, e não são interessados.

## 11f. A lista das propostas (fase 5, quinto ecrã)

**As mesmas oito colunas nas oito ranhuras**, e a regra que faltava era
do próprio CRM: um campo pertence a um estado e a mais nenhum
(`_campos_que_a_ranhura_pede()`, que a ficha já seguia).

O caso que importa é o **«Proposto» antes do Submetido**. Não está vazio
por falta de preenchimento — é **impossível**: o `ESTADOS_COM_PROPOSTO`
diz que o preço proposto só existe a partir do Submetido, e o
`docs/historico/CRM.md` escreve que «perguntar o preço proposto antes de
haver proposta é perguntar por adivinhas». Uma coluna de travessões que
nunca poderá ter nada é uma pergunta sem resposta possível, repetida em
cada linha. Passa a aparecer só de Submetido para a frente.

O que **não** se esconde: «Lote» e «Responsável» estão vazios por não
estarem *preenchidos*, e isso é outra coisa — podem ter valor, e
esconder a coluna tirava o sítio onde se vê que faltam.

### E um defeito na bateria, que apareceu por acidente

A meio deste ecrã três testes da escada começaram a falhar, e o diff não
os podia ter tocado. A causa: **os testes liam o `config.json`
verdadeiro dele**. Ele estava a usar o painel ao mesmo tempo — ligou o
Interesse — e o recorte por CPV passou a esconder os anúncios dos
fixtures, que não têm CPV nenhum. Três testes a contar 0 em vez de 4.

Não é um teste frágil, é pior: o hook `testes_antes_do_commit.py` trava
o commit com testes a falhar, e a causa está num ficheiro que ninguém
associa aos testes. **O uso normal da aplicação podia bloquear o
trabalho no código.**

O `BaseTemporaria` passou a apontar o `CONFIG` e o `BASE_DIR` para a
pasta temporária, como a `TestConfiguracoes` já fazia por si. Agora é de
todos, e nenhum teste depende dos dados dele.

### E a armadilha do processo velho, outra vez

A primeira verificação no ecrã mostrou a coluna «Proposto» ainda lá, em
«Não fomos». A tentação era procurar o erro no código. O `CLAUDE.md`
manda outra coisa: **comparar a hora de arranque do processo com a da
última gravação do ficheiro.** Processo às 16:09, ficheiro às 16:50 — eu
não tinha reiniciado o painel. Reiniciado, correcto.

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
