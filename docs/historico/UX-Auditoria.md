# UX-Auditoria.md

> **Instantâneo de 02/09/2026.** Descreve o que se planeou ou mediu
> nesse dia. O que mudou depois está no `ESTADO.md` e no
> `docs/diario/`. Não se edita.

Auditoria das regras de interface do radar, passadas pela lente das
vinte «leis de UX» (Hick, Fitts, Jakob, Miller, Doherty, Von Restorff,
Postel, Peak-End, Zeigarnik, Prägnanz, Tesler, Goal-Gradient e as
restantes). Feita a **02/09/2026**, a pedido do Afonso, depois de ele
levantar a dúvida certa: «as regras que implementámos podem estar
erradas».

O ponto de partida foi este: as leis não substituem as regras da casa,
que são específicas e nasceram de erros reais. Servem de lente. Cada
regra passa por elas e sai com um veredicto: **manter**, **afinar**
ou **dívida** (um remendo técnico que ficou escrito como se fosse
decisão de desenho). E onde as leis apanharam coisas que nenhuma regra
cobria, ficam registadas como achados novos.

A passagem de medição não alterou código. Na mesma tarde, à ordem
dele, aplicaram-se o P0 e os cinco P1 sem decisão (ver «O que já se
fez», no fim); o resto espera a palavra dele.

## Como se mediu

- **Base de ensaio**, não a base verdadeira: 40 anúncios fictícios com
  os casos que interessam (por ver com prazo folgado, urgente e
  expirado; sem detalhe lido; um interessado em cada uma das seis
  fases; descartados com e sem motivo; uma consulta preliminar da
  Vortal; um original com a sua alteração). Sem corpus de contratos.
- **Browser sem cabeça** (Chromium por Playwright) a 1366×768 e a
  1920×1080, sobre as 16 páginas: as quatro abas da lista, a lista
  filtrada, três fichas (densa, preliminar, por ver), quadro,
  calendário, contratos nos dois modos, alertas, interesse,
  indicadores, ficha de entidade.
- **Por página**, um script no browser contou os alvos interactivos e
  os que ficam abaixo de 24×24 px (o mínimo da WCAG 2.5.8) e de 32 px;
  os pares de alvos a menos de 8 px um do outro; os elementos com texto
  abaixo de 12 px; o contraste de cada elemento com texto contra o
  primeiro fundo opaco acima dele (AA: 4,5:1, ou 3:1 em texto grande);
  os botões com fundo cheio na primeira dobra; os campos de formulário
  visíveis; e o tempo do servidor e até ao DOMContentLoaded.
- **Fluxos**: abandonar a partir da lista (gestos até ficar feito),
  marcar interessa, arrastar no quadro (por leitura do JS), filtro com
  data inválida, pesquisa sem resultados, ficha inexistente, contratos
  sem corpus.
- **Não se mediu**: o tempo real das páginas sobre os 66 mil anúncios
  (o ESTADO.md tem essas medidas), o arrasto com rato verdadeiro, a
  leitura de peças, e o ecrã do Afonso. Este ambiente é Linux sem
  saída para o Google Fonts, e isso deixou uma medida própria (ver
  «Doherty»).

Os números abaixo são os de 1366×768, salvo indicação. A 1920 as
contagens são as mesmas; só a dobra muda.

## Parte 1: as regras da casa, uma a uma

| Regra (CLAUDE.md) | Lei que a testa | Medido | Veredicto |
|---|---|---|---|
| Arrastar no quadro recarrega a página | Doherty (400 ms), optimistic updates | O `drop` move o cartão, faz o POST e no sucesso chama `location.reload()`; o próprio comentário diz que o servidor é que sabe o que cada fase pede | **Dívida.** A lei tem razão. A regra existe porque o servidor não devolve o cartão redesenhado. Proposta em P1 |
| Abandonar pergunta o motivo num pop-up | Parkinson (menos passos), Hick, Postel (recuperável) | 3 gestos: clicar «abandonar», escolher um de 3 rádios, clicar «Abandonar». O pop-up diz que não apaga e que se pode repor. Os rótulos dos rádios são alvos de 390×36 px | **Manter, afinar.** Não é uma confirmação, é recolha de um dado. Mas cabe em 2 gestos: os três motivos como botões que fecham a caixa. Proposta em P2 |
| Painel denso, texto pequeno | Fitts (alvos), Miller (blocos), legibilidade | Na lista, 104 dos ~220 elementos com texto estão abaixo de 12 px; no quadro 65; no calendário 107 (90 a 9 px). Botões de texto com 11 px de altura: «voltar a por ver» 85×11, «no calendário» 75×11 (quadro), «Pôr por ver» 63×12, «Ver no DR» 57×12 (ficha), «mudar» 34×13 (barra lateral). 31 pares de alvos a menos de 8 px na lista | **Parcialmente errada.** Denso está certo para uma ferramenta de uso diário; o que está errado é a área de clique ser o próprio texto de 11 px. Rótulos secundários podem ficar; alvos não. Proposta em P1 |
| Os `--t*` passam AA sobre `--papel`, «que é o pior fundo» | Contraste medido, não estimado (regra da própria casa) | **3 falhas a 4,35:1** no quadro: `.coluna-pede` («pede o preço proposto» e os outros dois) usa `--t5` sobre a coluna, que é `--linha2` (#eceff2), mais escura que `--papel` (#eef1f4). Todas as outras páginas: pior caso 4,66 a 5,12 | **Regra incompleta.** O pior fundo não é `--papel`: é a coluna do quadro. O texto entrou a 01/09/2026 sem se medir. Correcção em P0 |
| O número que um ecrã mostra abre exactamente a lista que promete | Fitts (acção ao lado do conteúdo) | Nos indicadores, 2 dos 4 KPI ligam a uma lista («1 com prazo a menos de 8 dias», «6 por ver…»); «Anúncios na base 40» e «Sem detalhe lido 6» não ligam a nada; as quatro barras do funil não ligam; a página inteira tem 3 ligações | **Certa, mal cumprida.** A regra garante que a ligação, quando existe, bate certo. Não garante que exista. Proposta em P2 |
| Uma acção primária por bloco («Filtrar», «Trazer peças», «Criar filtro») | Von Restorff | Lista: 2 botões cheios na dobra (Filtrar, Verificar agora); ficha: 1 (Trazer peças); quadro e calendário: 0; alertas: 2. O «interessa» é contorno verde e o «abandonar» contorno cinzento | **Manter.** Medido e consistente |
| «Verificar agora» só na lista dos anúncios | Jakob, Hick | Está no canto superior direito da lista e da ficha (a ficha vive em Anúncios); ausente do resto | **Manter** |
| Sem JS o POST segue | Postel | Todos os botões de acção são `<form method=post>`; o pop-up intercepta o submit e, sem `<dialog>`, deixa passar; a recusa do servidor explica-se por `?aviso=` | **Manter** |
| Toda a truncagem passa por `corta()` / `text-overflow:ellipsis` | Prägnanz, Postel | Lista e ficha: sim. Calendário: a pílula de uma fase numa célula de 52 px mostra «A pr…» (5 caracteres) | **Manter, com um caso a rever.** Reticências em 5 caracteres já não são informação. Ver calendário em P2 |
| Contadores das abas contam dentro do filtro | Prägnanz, Postel | Com «zzzzqqq»: Por ver 0 · Interessados 0 · Abandonados 0 · Todos 0, e «Nada corresponde a este filtro. limpar» | **Manter.** Estado vazio com saída |
| Data inválida avisa em vez de esvaziar | Postel | `?de=lixo`: «data “lixo” não se percebe e foi ignorada», e a lista continua | **Manter** |
| A ficha de um anúncio inexistente é uma página da aplicação | Postel, Jakob | 404 com barra lateral, migalhas e duas saídas («Voltar à lista», «procurar em todos») | **Manter** |
| Prazo: janela única (`dias_urgente()`), etiqueta pela mesma conta | Consistência (Similarity) | 26 dias verde, 3 dias laranja, expirado vermelho, com a janela a 8; o cartão dos indicadores diz «menos de 8 dias» e abre a lista com o mesmo recorte | **Manter** |
| Dossier de uma coluna na ficha, cabeçalho e índice presos | Miller, Zeigarnik | Sticky no `aside` e no `.topo`; ficha densa com 1 492 px de altura; secções Essencial / Anúncio completo / Peças / Mercado / Histórico | **Manter**, com o achado do «essencial» abaixo |
| O interesse limita a lista e a lista di-lo | Postel (nada cai em silêncio) | Não activo na base de ensaio; a página de alertas diz «Ainda não está definido: a lista de anúncios mostra tudo» | **Manter** (não exercido) |

## Parte 2: achados novos, por lei

O que as leis apanharam e nenhuma regra da casa cobria. Cada um com a
medida, a proposta e o esforço (1 ≈ até 2 h · 2 ≈ meio dia a 1 dia ·
3 ≈ 2 a 3 dias, a escala do BACKLOG.md).

### Hick e Tesler: a lista abre com 60% do ecrã em filtros

Na lista dos anúncios a 1366×768, o primeiro cartão começa aos ~460 px:
título, abas, três blocos (11 campos de filtro, árvore de CPV, filtros
guardados) antes de haver um anúncio. São 42 alvos na primeira dobra. A
triagem, que é o trabalho de todos os dias, é «ler o cartão, decidir»,
e os filtros são o caso excepcional.

Proposta: os três blocos recolhidos por omissão num `<details>` com o
resumo do filtro activo na linha («pesquisa: outsourcing · CPV 72 ·
2 filtros guardados»), abertos quando há filtro aplicado ou quando se
abriram da última vez (`localStorage`). Esforço 1 a 2. **Decisão dele:
muda o primeiro ecrã.**

### Peak-End e Postel: triar não confirma nem deixa desfazer

Marcar «interessa» ou «abandonar» faz o POST, redirecciona para a
mesma página e o cartão desaparece da aba. Zero confirmação, zero
caminho de volta no sítio (o caminho é ir à aba dos interessados ou dos
abandonados e carregar em «repor por ver»). Medido: 0 elementos de
aviso depois de cada uma das duas acções. Enganar-se no cartão de
baixo em vez do de cima é um erro comum numa lista de 20 com dois botões
por linha, e hoje só se dá por ele à procura.

Proposta: reutilizar o `?aviso=` que já existe (o `.flash`) com o
título e um «desfazer» que faz o POST de volta: «AQUISIÇÃO DE
SERVIÇOS… marcado interessa · desfazer». Esforço 1. Sem decisão nova a
pedir: é o mesmo mecanismo do «Verificar agora».

### Von Restorff e Prägnanz: «prazo expirado» a vermelho onde é normal

No quadro, 4 dos 9 cartões mostram a pílula vermelha «prazo expirado»,
e os 4 estão em Submetido, Relatório preliminar, Ganho ou Perdido. A
partir do Submetido o prazo ter passado é o estado esperado (a proposta
foi entregue); o vermelho, que é a cor de alarme na lista, puxa o olho
para uma coisa que não pede acção nenhuma, e rouba força ao «3 dias»
laranja do cartão que ainda está a preparar proposta.

Proposta: em `cartao()`, a partir de `FASES_COM_PROPOSTO` a etiqueta
passa a neutra («prazo 03/08»); antes disso fica como está. Esforço 1.

### Fitts: alvos de 11 px de altura

Listados na Parte 1. O padrão é o mesmo em todos: `background:none;
border:0; padding:0` num `<button>` ou num `<a>` com letra de 10,5 a
11,5 px, o que faz da área de clique o próprio texto. A regra de
contraste apanhou o caso da cor a 31/08; ninguém mediu a área.

Proposta: um `padding` vertical mínimo que leve todos os alvos de texto
a 24 px sem mudar o tamanho da letra (`padding:6px 4px; margin:-6px
-4px` mantém o encaixe visual), e um teste que percorra as classes
`.tirar`, `.mini`, `.etq-x` e os `<a>` de acção da ficha a medir a
altura resultante no CSS. Esforço 1.

### Doherty: a folha de estilos do Google Fonts bloqueia a primeira pintura

O `BASE` carrega `fonts.googleapis.com/css2?…` como `<link
rel="stylesheet">`, que é render-blocking. Neste ambiente sem saída
para esse domínio, as páginas que o browser tentou pela primeira vez
levaram **12,6 s até ao DOMContentLoaded** com o servidor a responder
em 5 a 16 ms; as páginas seguintes, com a falha em cache do browser,
19 a 23 ms. No PC dele, sem rede ou com a rede lenta, é o mesmo
mecanismo: o painel fica branco até o pedido ao Google falhar ou
chegar. O ESTADO.md regista «se a máquina estiver sem rede a aplicação
continua legível, só muda de letra», e isso é verdade depois do
timeout, não antes.

Proposta: carregar a folha das fontes sem bloquear (`media="print"
onload="this.media='all'"`, o truque corrente) ou guardar os dois
ficheiros de fonte na pasta `libs/` e servi-los do próprio radar, que
é o que a pen já faz com os módulos. Esforço 1.

### Miller e Prägnanz: o «essencial» da ficha diz sobretudo o que falta

Na ficha de um anúncio sem peças lidas (que é a ficha de todos os por
ver, o momento da decisão), a tabela do essencial tem 12 linhas: 4
com valor e **8 a dizer «o anúncio não indica» ou «só consta do
Programa de Concurso / Caderno de Encargos»**. O bloco que devia ser o
mais rápido de ler é o que tem mais linhas sem conteúdo.

Proposta: as linhas sem valor saem para uma única frase por baixo
(«8 campos só constam das peças: critério, duração, local… Trazer
peças»), com o botão que já existe. Depois de as peças serem lidas as
linhas voltam a aparecer com valor. Esforço 1 a 2. **Decisão dele: é
ele quem lê a ficha.**

### Fitts e Prägnanz: a pílula do calendário não cabe na célula

Cada dia tem 52 px de largura e a pílula de uma fase leva o nome da
fase: «A pr…». 90 elementos a 9 px (os cabeçalhos dos dias). A grelha
de 45 dias é a razão de ser da página e o dia é a unidade certa; o
que não cabe lá é texto.

Proposta: a pílula passa a ponto colorido com a fase no `title`, e o
nome da fase vai para a coluna da esquerda, ao lado do «no quadro»,
onde há 227 px. Esforço 1.

### Parkinson: não há teclado

Nenhum `keydown`, `accesskey` ou atalho na aplicação. Triar 20 cartões
é 20 vezes mover o rato até dois botões de 25 px no canto direito de
cada cartão. Uma ferramenta que a mesma pessoa usa todos os dias ganha
mais com `j`/`k` (cartão seguinte/anterior), `i` (interessa), `a`
(abandonar, abre o pop-up) e `Enter` (abrir a ficha) do que com
qualquer rearranjo visual.

Proposta: um bloco de JS na lista, com o cartão focado marcado a
contorno e uma linha de ajuda na cabeça da lista («j k i a Enter»).
Esforço 2. **Decisão dele: é hábito novo.**

### Zeigarnik e Goal-Gradient: o quadro não mostra o que falta a cada cartão

O cabeçalho da coluna diz o que a fase pede («pede o preço proposto»),
e isso está bem. Mas o cartão no Submetido sem preço proposto e o do
Relatório sem lugar não se distinguem dos que já têm tudo, a não ser
pelo campo vazio. Um sinal por cartão («falta o proposto», a laranja,
do lado das etiquetas) mostraria o trabalho por acabar sem ter de ler
cada formulário. Esforço 1. Não é urgente: com 9 cartões vê-se; com 30
já não.

## Parte 3: o que as leis dizem e aqui não se aplica

Para não voltar a discutir o que já está decidido:

- **«Optimistic updates» na triagem da lista.** O POST com redirect
  demora dezenas de ms em local; um cartão a desaparecer sem esperar
  pelo servidor ganharia nada e perdia a garantia de que a base diz o
  mesmo que o ecrã. O que falta não é rapidez, é confirmação (Parte 2).
- **Alvos de 44 px (o mínimo do toque).** Nenhum ecrã é para
  telemóvel, por decisão registada (E3 do BACKLOG). 24 px é o mínimo
  certo aqui; 44 desfazia a densidade que ele quer.
- **Ligações de texto corrido abaixo de 24 px.** Os títulos dos
  cartões (924×20) e as ligações dentro de frases contam nas medições
  mas a WCAG exclui-as, e bem: uma ligação em linha tem a altura da
  linha. As 24 «abaixo de 24» da lista são quase todas estas.
- **«Remover confirmações desnecessárias» aplicado ao pop-up do
  motivo.** Não é uma confirmação: o motivo é a razão de ser do
  pop-up, e a alternativa (selector em cada linha) foi medida pior.
- **«Uma decisão por ecrã» aplicado à página de alertas.** 19 campos
  no «Novo filtro» é muito, mas é a página avançada, aberta de
  propósito, com os campos na mesma ordem em toda a aplicação. Mudar
  aqui é mexer no vocabulário partilhado por um ganho pequeno.

## Parte 4: ordem proposta

| Prioridade | Item | Esforço | Precisa de decisão |
|---|---|---|---|
| P0 | Contraste dos `.coluna-pede` (regra própria violada, 3 elementos) | 1 | Não |
| P1 | Alvos de texto a 24 px sem mudar a letra, com teste | 1 | Não |
| P1 | Confirmação com «desfazer» depois de triar | 1 | Não |
| P1 | «Prazo expirado» neutro a partir do Submetido | 1 | Não |
| P1 | Fontes sem bloquear a primeira pintura | 1 | Não |
| P1 | O quadro sem `location.reload()`: o servidor devolve o cartão e os cabeçalhos | 2 | Não (a dívida já estava assumida) |
| P2 | Filtros da lista recolhidos por omissão | 1 a 2 | **Sim** |
| P2 | Linhas sem valor do essencial numa frase só | 1 a 2 | **Sim** |
| P2 | Motivos de abandono em 2 gestos | 1 | Não |
| P2 | KPI e funil dos indicadores a ligar às listas | 1 | Não |
| P2 | Pílula do calendário como ponto, nome na coluna da esquerda | 1 | Não |
| P3 | Teclado na lista | 2 | **Sim** |
| P3 | Sinal de «falta X» por cartão do quadro | 1 | Não |

Os P0 e P1 sem decisão são meia jornada juntos, e nenhum muda o que o
Afonso vê de forma que precise de habituação. Os que precisam de
decisão mudam o primeiro ecrã ou a ficha, e por isso esperam por ele.

## O que já se fez (02/09/2026, à tarde)

À ordem do Afonso («avança com P0 e P1»), na mesma sessão:

| Item | O que mudou | Teste |
|---|---|---|
| P0 contraste | `.coluna-pede` passou de `--t5` para `--t4` (5,12:1 sobre `--linha2`) | `TestContrasteNosFundosReais`, que calcula os contrastes a partir do próprio CSS e fixa os dois patamares da escala |
| P1 alvos | `button.tirar`, `.carta-pe a`, `.bt-leve`, `.sou button`, `button.etq-x`, `.alerta .apagar` com `min-height:24px` por padding e margem negativa vertical, letra igual | `TestAlvosDeTextoA24px` |
| P1 desfazer | `mudar_estado()` volta com aviso («título» marcado como interessa / abandonado (motivo) / reposto em por ver) e um botão «desfazer» que faz o POST inverso, com o motivo antigo quando o estado anterior era um abandono | `TestTriarAvisaEDeixaDesfazer` (7 testes) |
| P1 prazo neutro | A partir do Submetido o cartão diz «prazo 03/08/2026» sem cor; antes continua a etiqueta de alarme | `TestPrazoNeutroDepoisDeSubmetido` |
| P1 fontes | Folha do Google Fonts com `media="print" onload`, cópia em `<noscript>` | `TestFontesNaoBloqueiamAPrimeiraPintura` |
| P1 quadro | `/quadro/mover` devolve `{carta, contas}`; o `drop` troca o cartão e as duas contagens; `reload()` só nos erros | `TestArrastarRedesenhaOCartao` reescrita (4 testes, com cliente Flask sobre base temporária) |

A medição do browser não se repetiu depois destas alterações: fica
para a próxima passagem, junto com o que está abaixo.

## O que fica para a próxima passagem

- Repetir a medição do contraste **em todos os fundos que existem**
  (papel, branco, `--linha2` das colunas, os fundos das pílulas, a
  barra escura), não só sobre `--papel`. O script desta auditoria
  (`auditoria.py`, na pasta de rascunho da sessão; a receita está na
  secção «Como se mediu») faz isso por elemento e cabe em `teste_radar`
  como teste de CSS estático para os pares cor/fundo declarados.
- Medir a lista sobre a base verdadeira com o filtro por omissão, a
  frio, na pen: o servidor aqui respondeu em 16 ms sobre 40 linhas e
  isso não diz nada sobre 66 mil.
- Ver o arrasto com rato verdadeiro depois de tirar o `reload()`.
