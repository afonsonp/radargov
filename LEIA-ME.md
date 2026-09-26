# Mira Gov, Diário da República

O produto chama-se **Mira Gov** desde 24/09/2026 (era Radar Gov). Neste
manual, «o radar» é o programa que corre no PC (o `radar.py`, a pasta, os
serviços); o nome do produto, que os clientes lêem, é Mira Gov.

Vigia a parte L da série II do Diário da República, filtra os anúncios
que interessam ao teu portefólio e mostra-os num painel local.
Verifica sozinho de hora a hora, das 08:00 às 20:00 (as horas mudam-se
em Configurações › Recolha).

Duas fontes: o serviço de pesquisa do próprio portal do DR (os
anúncios) e o dump semanal do Portal BASE (os contratos celebrados, no
separador Contratos — ver a secção 15).

---

## 1. Onde pôr a pasta

No ambiente de trabalho, como tinhas. Guarda tudo na mesma pasta:
o programa, a captura, a configuração e a base de dados.

**Hoje está em `~/Desktop/radar`, no disco interno, em Ubuntu** — e é
esse o sítio certo. Duas razões, as duas pagas: um disco externo só é
montado quando entras no ambiente de trabalho, por isso um computador
que arranque sem ninguém entrar não encontra a pasta (e os
temporizadores falham em silêncio); e uma pasta dentro do OneDrive tem
a sincronização a bloquear o `radar.db` a meio de uma escrita.

Se algum dia voltares a pôr isto num disco vindo do Windows: o Windows
deixa pastas e ficheiros marcados «só de leitura» que o Linux respeita à
letra — se a instalação disser *Permission denied*, corre
`chmod -R u+w .` dentro da pasta uma vez.

## 2. Primeira instalação

Num terminal aberto na pasta:

```bash
./instalar.sh
```
Cria um ambiente Python dentro da pasta (`.venv`) e instala lá as
dependências. Se disser que falta o `python3-venv`, é
`sudo apt install python3-venv` e voltar a correr. Faz a captura da
secção 3. Depois:

```bash
./iniciar.sh
```
abre o painel, e

```bash
./agendar.sh
```
cria as tarefas — e, ao contrário do Windows, deixa também o painel a
correr como serviço, para não ser preciso abri-lo de manhã. A partir
daí o `iniciar.sh` só diz «já está a correr». Para ver as tarefas:
`systemctl --user list-timers`; para o registo de uma verificação:
`journalctl --user -u radar-verificar.service`. Para parar tudo:
`./desinstalar.sh`. Para os comandos da secção 13, o `python` é o da
pasta: `.venv/bin/python radar.py ...`.

## 3. As capturas

O DR não tem API pública. O radar faz as mesmas perguntas que o teu
browser faz, e para isso precisa de duas capturas, feitas uma vez.

### `curl_DR.txt`, a pesquisa

1. Vai a `diariodarepublica.pt`, escolhe **Anúncios, parte L** e pesquisa
   por `aquisição`, com datas dos últimos dias.
2. **F12**, separador **Rede**, filtro **Fetch/XHR**.
3. Carrega em **Filtrar** no site. Aparece na lista o `DataActionGetPesquisas`.
4. Botão direito nele, **Copy**, **Copy as cURL (bash)**.
   O formato `cmd` também serve, mas o `bash` preserva os acentos.
5. Abre o Bloco de Notas, Ctrl+V, e grava na pasta do radar com o nome
   `curl_DR.txt`. Em Tipo, escolhe **Todos os ficheiros**.

### `curl_detalhe.txt`, os campos de cada anúncio

O CPV, o prazo e o preço base não vêm na pesquisa, vêm da página de cada
anúncio. Para os obter falta uma segunda captura.

1. Abre um anúncio qualquer, por exemplo pelo link de um da lista.
2. **F12**, **Rede**, filtro **Fetch/XHR**, e depois **F5** para recarregar.
3. Procura o pedido `DataActionGetAllConteudoDetalheData`.
4. Botão direito, **Copy**, **Copy as cURL (bash)**.
5. Grava como `curl_detalhe.txt` na pasta do radar.

Sem esta segunda captura o radar funciona na mesma, apenas fica sem CPV,
sem prazo e sem preço base, e o filtro de CPV não devolve nada.

### O que é aproveitado

Os cabeçalhos e a forma do pedido. As datas, o termo de pesquisa e a
página são substituídos a cada verificação. Na captura do detalhe, o
que muda é a chave do anúncio.

O token de segurança e as versões que o pedido leva **já não vêm da
captura**: desde 02/09/2026 o radar vai buscá-los ao próprio portal a
cada verificação, com três pedidos simples, e por isso a captura não
expira por causa deles (mediu-se que o token é público e que só a
versão do ecrã mudava). Se um dia o DR mudar a forma do pedido, o
painel avisa a vermelho a dizer que não aceitou a pesquisa nem depois
de renovar as peças. Só aí é que se repete esta secção; leva dois
minutos.

## 4. O que entra

Tudo. Todos os anúncios da parte L que o portal devolver na janela de
datas entram na base, sem juízo prévio. A triagem é tua, no painel.

E, desde 31/08/2026, também as **consultas preliminares da Vortal** —
o tipo de procedimento que a parte L não publica de todo. Vêm da
pesquisa pública da plataforma (sem sessão), entram no Por ver como
qualquer anúncio (com a etiqueta `vortal` e o tipo "Consulta
preliminar") e **só esse tipo entra**: concursos públicos da Vortal já
vêm pelo DR, e duplicá-los era mentir nas contagens. A ficha destas
consultas é como a de qualquer outro anúncio: entidade e NIPC, CPV,
tipo de contrato, local de execução, prazos — **e a lista dos artigos
que a entidade quer comprar**, item a item, que numa consulta
preliminar é a parte que diz mais do que o título. As peças trazem-se
com o mesmo botão de sempre. Desliga-se com `"vortal_preliminares":
false` no `config.json`.

No `config.json`, a única coisa que costuma valer a pena mexer é:

- `dias_catchup`: 15 dias. É a janela que o radar pede ao portal em
  **cada verificação de rotina** (as de hora a hora). Serve também de rede
  se o PC estiver dias desligado. Não é o limite do que fica na base —
  ver "Histórico", abaixo.
- `detalhe_dias`: 60 dias. O radar só vai buscar os detalhes (CPV,
  prazo, preço) dos anúncios publicados nos últimos 60 dias, porque
  entre a publicação e o prazo vão ~18 dias em média e mais atrás do
  que isso já fechou. Os mais antigos são lidos quando abres a ficha.
  Põe a `0` se quiseres mesmo que ele leia tudo — demora horas.
- `leituras`: afina, campo a campo, o que o modelo lê das peças
  (secção 6): em que documento procura (`quais`: `"encargos"` ou
  `"programa"`), à volta de que títulos recorta (`ancoras`, pares
  `[prioridade, expressão]` — prioridade mais baixa ganha) e o que se
  lhe pede (`instrucao`). Os campos são `objecto`, `equipa` e
  `proposta`; só se substitui o que escreveres, o resto fica o de
  origem, e uma entrada inválida (expressão que não compila, `quais`
  desconhecido) é ignorada em vez de calar a leitura. Exemplo, para
  mandar a leitura da equipa procurar também em "recursos humanos":

  ```json
  "leituras": {
    "equipa": {
      "ancoras": [[1, "perfis"], [2, "equipa"], [3, "recursos humanos"]]
    }
  }
  ```

Não há atalhos pré-definidos no ficheiro de configuração (nem de
palavra, nem de CPV) — tudo se escolhe na hora, no painel: a caixa de
palavras aceita o que escreveres directamente, e a árvore de CPV cobre
o que os atalhos faziam antes, sem precisar de editar ficheiros.

`paginas` é um tecto de segurança (5000), não um alvo: o radar pede
páginas ao portal até ele devolver menos que uma página cheia, e só
pára aí por engano se algo estiver mesmo a repetir para sempre.

Os `termos_de_pesquisa` estão a `[""]`, que quer dizer pesquisa sem
termo, ou seja, tudo. Os `termos_de_reserva` só entram em acção se o
portal responder à pesquisa vazia sem um único anúncio (não num corte
de rede, que é avaria e pára logo); quando isso acontece, a mensagem
da verificação diz «pelos termos de reserva». Nunca se viu disparar.

## Histórico

A verificação de rotina (de hora a hora) só olha para os últimos
`dias_catchup` dias — não vale a pena pedir mais que isso a cada hora. Para
trazer um período maior de uma vez, corre:

```
python radar.py --historico 730
```

O número são os dias a recuar (730 ≈ 2 anos; omitido, usa 730). Isto
não mexe no `dias_catchup` da configuração, só faz uma recolha extra,
maior, uma vez.

Para trazer **anos**, dá-lhe duas datas em vez de um número:

```
python radar.py --historico 2015-01-01 2024-08-19
```

Aí o radar parte o intervalo em janelas de 30 dias e **grava cada uma
assim que a traz**, dizendo em que vai e quanto falta. Podes parar com
Ctrl-C sem perder nada, e voltar a correr o mesmo comando: as janelas
que já vieram não trazem nada de novo. Se alguma falhar (rede em baixo,
por exemplo), as outras continuam e no fim ele escreve o comando exacto
para repetir só as que faltam. Para um período grande demora — uma página por segundo,
para não sobrecarregar o portal — e depois os detalhes (CPV, prazo,
preço) continuam a ser lidos aos poucos nas verificações seguintes, 40
de cada vez (`detalhes_por_volta`), até não sobrar nada por ler.

## 5. O painel

### A abertura: o que há para fazer

O endereço `/` é o **Hoje** — o logótipo leva-lhe de volta. O título é a
data. Logo por baixo, numa linha, **quatro números** (em jogo, taxa de
vitória, por decidir, para fazer), e cada um abre exactamente a lista
que o produz; ao fim da linha, a saída para o **Ponto de situação**.

A seguir vem a **fita da semana**: sete células, segunda a domingo. Cada
uma diz quantas tarefas tem nesse dia, quantas já estão feitas e quantas
entregas fecham; o dia de hoje diz também quantas atrasadas arrasta.
**Clica num dia** para o veres — a lista por baixo muda para esse dia, e
as setas andam de semana em semana.

Por baixo, duas colunas.

**À esquerda, o que há para fazer**, em cinco baldes — a lista deles e
o que cada linha mostra estão no `docs/FUNCIONAL.md` §4.1. Três coisas
que só se sabem a usar:

- **O primeiro balde não é trabalho teu: é decisão tua.** São os
  concursos em «Por analisar» ou «A preparar proposta» cujo prazo já
  passou. **O radar não mexe em nenhum** — mostra-os com o selector da
  ranhura ao lado, e quem escolhe és tu. Foi pedido teu: «posso não ter
  passado para submetido por esquecimento».
- **O «adiar todas p/ hoje» das atrasadas pergunta antes, e não tem
  desfazer** — cada tarefa tinha a sua data, e depois de as juntar num
  dia não há como as devolver.
- **Um concurso cujas automáticas estão no primeiro balde não as repete
  nas atrasadas.** Se procuras uma tarefa e não a vês, é aí que ela
  está.

**A tarefa risca-se ali e a página fica onde está** — a linha não
desaparece: fica riscada, com o **desfazer** ao lado, até ao fim do
dia; no dia seguinte já não aparece. Um balde comprido mostra as
primeiras linhas e tem um **«mais N»** para ver o resto. Em cima podes
**filtrar por pessoa** e **esconder as feitas**. Para adiar ou atribuir,
abre a ficha do concurso: o bloco «A nossa proposta» tem os campos.

**À direita**, três caixas: **O que mudou** desde a última verificação
(anúncios novos, quantos caem no perfil da empresa, peças novas, prazos
alterados e as propostas que o Portal BASE já diz adjudicadas),
**Prazos a chegar · 7 dias** e **Paradas há mais tempo**.

As tarefas de uma proposta sem anúncio (consulta prévia, ajuste
directo) riscam-se na página dela, `/proposta/<n>`.

### O Ponto de situação: como vai o negócio

O endereço `/situacao`, a partir da linha de números do Hoje. É o que
antes estava no fim da abertura, agora com casa própria e três abas —
**Negócio**, **Triagem** e **Por área CPV**.

Em cima escolhe-se o **período**: este mês, este trimestre (o que abre
por omissão), 12 meses ou tudo. Cada número traz a comparação com o
período anterior do mesmo tamanho. O período conta pela data em que a
proposta se **decidiu**; o «em jogo» é o que está aberto **agora**, e
por isso não tem comparação — o radar não guarda o que estava em jogo no
trimestre passado.

### A ficha de uma entidade

> **O que a lista e a ficha mostram** — as cinco abas, as colunas da
> tabela, os seis factos do topo — está no `docs/FUNCIONAL.md` §3.4 e
> §4.7, e só lá. Aqui fica o que tu fazes.

**Toda a entidade tem ficha**, tenha ou não contratos no Portal BASE.
Chega-se por dois caminhos: **clica no nome da entidade** em qualquer
anúncio, ou vai a **Mercado › Entidades**.

Na lista, três gestos:

- **procura** por nome ou NIF — apanha todas as grafias com que a
  entidade já assinou, por isso não tens de acertar no nome;
- **as abas** mudam a pergunta, não o filtro: com quem trabalhamos,
  quem segues, quem mais compra, quem mais ganha, e a quem acaba um
  contrato em breve;
- **marca duas linhas e carrega em «comparar as marcadas»** para as ver
  lado a lado.

Na ficha, o teu lado está à esquerda e o do mercado à direita. Duas
coisas que vale a pena saber ao usar:

- **os contactos criam-se ali**, e passam a aparecer em todos os
  concursos dessa entidade — são dela, não do concurso;
- **a taxa com ela só aparece a partir de cinco decididos**; abaixo
  disso o ecrã diz de quantos precisa, em vez de inventar uma
  percentagem sobre dois casos.

**Sem o corpus do Portal BASE** as colunas do mercado dizem «sem BASE»
e não zero — zero era uma afirmação sobre o mercado, e a verdadeira é
«não sei». O ecrã diz-te onde o trazer.

### Mudar de ranhura

O gesto está no **§9**, e o que cada ranhura exige no
`docs/FUNCIONAL.md` §3.1. (Esta secção repetia os dois, palavra por
palavra — saiu a 19/09/2026.)

### As propostas sem anúncio

Uma consulta prévia, um ajuste directo ou um convite não saem no Diário
da República. Criam-se em **Nova proposta**, e a página delas
(`/proposta/<n>`) tem tudo o que a ficha de um anúncio tem do nosso
lado: a ranhura, os campos que ela pede, as etiquetas, o que falta
fazer, os contactos do cliente, a cronologia — e o **apagar**, dobrado
dentro de «Apagar esta proposta» porque não tem volta. Uma proposta que
tenha vindo do DR não se apaga aí: tira-se da escada, e o anúncio volta
à lista.

### A barra

A barra é **horizontal, em cima**, e tem a marca à esquerda — o
**Mira Gov** é o Hoje, e é por ele que se volta à abertura — e **cinco
itens** (desde 24/09/2026): **Concursos** (o que o DR publicou: por
ver, expirou sem ver, todos), **Propostas** (as oito ranhuras da
empresa, de «Por analisar» a «Cancelado»), **Mercado** (os contratos,
com a vista **Entidades**), **Calendário** e **Configurações**. À
direita, o teu nome. Os Indicadores estão dentro das Configurações (§8).

As **dez ranhuras da escada** repartem-se desde 24/09/2026 por dois itens: as duas pontas (e o «Todos») estão nos **Concursos**, e as oito da empresa nas **Propostas**. Por ordem:

- **Por ver** — o que está por decidir **e ainda dá para responder**:
  prazo aberto, ou, quando o prazo ainda não foi lido, publicado nos
  últimos 60 dias (a janela `detalhe_dias`). É a aba em que a página
  abre, e anda na ordem do milhar, não dos 200 mil.
- As **oito palavras da empresa**, por ordem (estão no
  `docs/FUNCIONAL.md` §3.1). Estas oito mostram **propostas**, não
  anúncios: com lotes há uma proposta por lote, e há propostas que nem
  anúncio têm.
- **Expirou sem ver** — o que já não é possível responder e ninguém
  chegou a olhar. Passa para cá sozinho: se um anúncio for rectificado
  com prazo novo, volta ao Por ver.

As duas pontas mostram **anúncios**; as oito do meio, propostas. A lista
vem sempre do mais recente para o mais antigo.

**O quadro saiu a 15/09/2026**, por decisão tua: oito colunas e oito
abas eram a mesma coisa duas vezes. A ranhura muda-se no selector de
cada linha, e tudo o que o cartão fazia vive no bloco «A nossa proposta»
da ficha.

**Um concurso aparece uma vez, mesmo que o DR o publique três.** O DR
não corrige um anúncio: publica outro, com número novo, cujo texto
começa por «Alteração do Anúncio de procedimento n.º …» — é assim que
um prazo se prorroga ou um preço base muda. O radar reconhece essas
republicações, passa o prazo e o preço novos para o anúncio original e
tira-as da lista. A ficha do original diz «Alterado pelo anúncio X» e o
histórico conta o que mudou; a ficha da alteração aponta para o
original, que é onde se decide — um anúncio que abandonaste continua
abandonado quando é republicado, e um por ver a que estenderam o prazo
volta a aparecer com o prazo novo, sem mexeres em nada.

**O perfil da empresa recorta a lista inteira** (chamava-se
«Interesse» até 26/09/2026). Em *Configurações › Perfil da empresa*
escolhes, na árvore, os CPV que a empresa trabalha; ligado, a lista passa
a mostrar só o que corresponde — em todas as abas, sem teres de pôr
filtro nenhum. Não é um alerta: um alerta avisa-te, o perfil esconde
o resto. No Mercado só recorta pelo CPV (os contratos não têm distrito
nem preço base na mesma forma), e a faixa di-lo. A lista diz sempre que está limitada, quantos ficam de fora, e
tem um **ver tudo** que o levanta para a vista em que estás. Nasce
desligado; desligado, nada muda.

Recorta também o **Hoje**, o **Mercado** e a ficha da entidade. **Não
recorta os alertas nem os filtros guardados**, e isso é de propósito:
pô-lo lá dentro fazia um alerta deixar de te avisar do que te avisa
hoje, sem tu lhe teres tocado.

A barra de filtros trabalha sobre o que já está guardado, sem apagar
nada. **Os campos estão sempre à vista** (desde 24/09/2026, como no
desenho do Mira Gov; de 8/09 a 24/09 estavam recolhidos): uma linha,
por baixo das abas. A **árvore de CPV** fica por baixo deles, recolhida
na linha «Escolher por CPV», e abre sozinha quando há um CPV escolhido
(só aparece enquanto não tiveres interesse definido — com ele, o CPV
já está decidido). Desde 14/09/2026 são quatro campos:

- **nome do concurso ou objecto**. Várias palavras separadas por `|`
  valem como "qualquer uma destas" (`outsystems|.net|java`).
- **entidade que publica**. Enquanto escreves, o campo sugere as
  entidades que existem na base — escreve «sp» e aparecem as que
  começam por SP e depois as que o têm no nome, uma por NIF, com a
  grafia mais frequente e quantos anúncios tem. O DR escreve o mesmo
  nome de várias maneiras («SPMS - Serviços Partilhados…, E. P. E.» e
  «Serviços Partilhados…, EPE» são a mesma empresa, NIF 509540716);
  escolhida a sugestão, o filtro é pelo NIF e apanha todas as grafias,
  mais os anúncios antigos dessa entidade que vieram sem NIF. Se
  escreveres à mão sem escolher, filtra pelo texto, como sempre. Entre
  este campo e o do objecto é "e".
- **plataforma electrónica**: acingov, vortal, anogov, compraspt,
  «outras» (as que já não existem — saphety, compraspublicas, gatewit,
  bizgov, construlink — num balde só) ou os que não a indicam.
- **intervalo de datas** de publicação.

No **Mercado** os campos são os mesmos por feitio: objecto, entidade
que comprou e quem ganhou (as duas sugerem-se do corpus, uma por NIF,
por qualquer dos nomes com que a entidade já assinou; escolhida a
sugestão, o filtro é pela entidade e não pela grafia), procedimento,
datas e valor mínimo. O «excluir palavras» e o E/OU saíram de lá
também.

O **CPV** escolhe-se na árvore, por cima: marca uma divisão e apanha
tudo o que está por baixo; desmarca um código lá dentro e só esse sai.
O que saiu do ecrã continua a funcionar pela ligação — o prazo dos
cartões dos indicadores («urgentes»), um alerta antigo com exclusões —
e passa em campos escondidos quando voltas a filtrar.

**Pelo teclado** (desde 8/09/2026): `j` e `k` passam ao anúncio
seguinte e anterior (o focado fica com contorno azul), `i` marca
interessa, `a` abre a caixa do motivo de abandono, e Enter abre a
ficha. Não fazem nada com o cursor num campo de texto. A pista «j k i
a ⏎» na linha da contagem é isto.

**Os filtros guardados deixaram de existir a 13/09/2026**: o que há é
**Criar alerta**, em cima do filtro em uso. Em **Configurações ›
Alertas** gerem-se os alertas e configura-se o e-mail e a janela do
«urgente»; o **interesse** (os CPV que recortam a lista, ver §5) tem
secção própria. O resumo chega formatado — um cartão
por anúncio, com o prazo colorido como na lista — e o mesmo conteúdo
fica em texto no `AVISOS.txt`. Em **Mercado** vivem os **Contratos**
(o que já foi adjudicado, com **quem ganha** e **quem compra** numa
coluna ao lado da tabela, sobre o mesmo filtro), com dois modos no
mesmo ecrã: **por celebração** e **por fim estimado** — as antigas
Renovações, agora uma aba que mantém o filtro e mostra o que está a
chegar ao fim (o modo diz-se na frase por baixo do título e na aba
acesa, e as datas de celebração desactivam-se aí, com explicação). De lá chega-se à **ficha
de cada entidade**, com uma ligação directa a «o que está a acabar»
dela — e há a vista **Entidades** na barra, descrita no §5, «A ficha de
uma entidade». (Estava aqui a lista das abas outra vez, e ainda dizia
«quatro atalhos» quando já são cinco desde 18/09 — saiu a 19/09/2026.)

Na lista, cada anúncio mostra a plataforma numa etiqueta: **a verde**
quando as peças se conseguem automaticamente, a cinzento quando tens de
ir ao site da plataforma buscá-las.

Os botões **interessa** e **abandonar** servem para ires limpando a
lista. Abandonar não apaga, arquiva — fica na aba Abandonados, e
podes sempre repor. **Abandonar pede o motivo**: carregas no botão e
abre uma caixa com o nome do anúncio e três hipóteses — *Preço base
baixo*, *Falta de certificações*, *Falta de CV's* —, sem caixa de texto
livre. Sem motivo escolhido não abandona. O
motivo fica na etiqueta da linha, no cabeçalho da ficha, no histórico e
numa coluna própria do CSV; assim, daqui a um mês, a aba Abandonados
ainda diz porque é que cada um ficou de fora. (Os que caem lá sozinhos
por o prazo ter passado não têm motivo — não se lhes inventa um.)

O **Exportar CSV** exporta exactamente o que o filtro está a mostrar,
não a base inteira.

Nota sobre o CPV e o prazo: esses campos não vêm da pesquisa, vêm da
página de detalhe de cada anúncio. Enquanto não estiverem preenchidos
(o cartão "Sem detalhe lido" dos Indicadores diz quantos faltam), o
filtro de CPV não devolve nada para esses anúncios em concreto.

O filtro de CPV percebe tanto código como palavra da descrição oficial,
porque a base traz embutido o vocabulário CPV completo (tabela
`cpv_dict`, importada uma vez de um ficheiro de referência). Se um dia
precisares de o actualizar para uma versão mais recente do vocabulário,
corre `python radar.py --importar-cpv caminho\para\ficheiro.json`, com
um ficheiro no formato `[{"codigo":"...", "descricao":"..."}]`.

Abaixo da caixa de filtro há **"Escolher CPV na árvore"**, com o
vocabulário CPV inteiro em hierarquia (divisão, grupo, classe...), cada
nó com a contagem de anúncios guardados nesse ramo. Escreve na caixa de
busca da árvore para filtrar por palavra (ela abre os ramos onde bate
certo), marca as caixas que interessam, e carrega em **"Aplicar
seleccionados ao filtro"** — isso escreve os códigos escolhidos, juntos
por `|`, e submete o formulário. Marcar um código grande (uma divisão
ou grupo) apanha automaticamente tudo o que está por baixo dele — não
é preciso marcar um a um.

E **podes tirar de dentro**: com uma divisão marcada, desmarcar um
código lá dentro tira só esse ramo e deixa a divisão a valer. O que
tiraste fica riscado na árvore, com a marca "tirado", e vai parar ao
campo **Excluir CPV** — que é o mesmo que podes escrever à mão. Isto
importa: marcar o 72 e ficar só com os sub-códigos escolhidos perderia
os anúncios que trazem apenas `72000000`, e esses são oportunidades a
sério. Com a divisão marcada e dois ramos tirados, esses continuam a
entrar.

A caixa de CPV em si já não aparece — é a árvore que a preenche por
baixo dos panos. Quando há um filtro de CPV a valer, aparece uma linha
"Filtro CPV activo: ..." com um link para o tirar sem mexer no resto.

## 6. A ficha do anúncio

Clicar no título de um anúncio — na lista, no Hoje ou no calendário —
abre a ficha **dentro da aplicação**, já não o site do DR. Lá tens:

- os factos de topo: prazo com contagem de dias, preço base, plataforma,
  e o CPV já com a descrição por extenso — com uma ligação **ver
  anúncios deste CPV**, que abre a lista já filtrada — para responder ao
  «que mais há disto?»;
- **as peças do procedimento** (Programa de Concurso, Caderno de
  Encargos, anexos) — os PDF abrem **dentro da aplicação**, numa página
  própria onde é o próprio radar que desenha o documento, página a
  página, em qualquer browser. A **caixa "Procurar no documento"**
  marca as ocorrências **a amarelo nas próprias páginas** e diz onde
  estão ("aparece em 8 páginas, 10 vezes"), com salto directo para
  cada uma. A procura é tal e qual está escrito no documento (acentos
  contam). O que não for PDF descarrega-se como antes;
- o **anúncio completo**, com contactos, critério de
  adjudicação, prazo de execução, tudo o que o DR publica;
- dois botões para sair daqui, que são coisas diferentes: **Abrir na
  \<plataforma\>** leva à página do procedimento, e **Peças na
  plataforma** ao endereço das peças que o anúncio indica. Na acingov
  não há página pública do procedimento (só se vê com sessão iniciada),
  por isso o botão diz **Procurar na acingov** e abre a pesquisa
  pública — em vez de prometer o que não existe.

**Essencial** mostra uma tabela com os doze campos que interessam para
decidir: nome, entidade, critério de adjudicação, preço base, preço
anormalmente baixo, duração, local, data de esclarecimentos, data de
submissão, objecto, equipa e documentos que constituem a proposta.
Os que não têm valor **não ocupam linha**: ficam numa frase por baixo
da tabela, agrupados pela razão («só consta do Programa de Concurso:
…; só consta do Caderno de Encargos: …»), com a ligação para as peças.
Depois de as peças serem lidas, os campos que a leitura trouxer voltam
à tabela. O botão **Anúncio completo** abre as 28 secções em bruto.

A **data de esclarecimentos** é calculada, não lida: é o primeiro terço
do prazo das propostas, que é a regra supletiva do artigo 50.º do CCP.
Vem marcada como tal, para confirmares no Programa de Concurso — alguns
fixam prazo próprio. É um prazo que se perde em silêncio, porque fecha
muito antes do prazo das propostas e ninguém avisa.

Quatro desses campos não estão no anúncio do DR — preço anormalmente
baixo, objecto detalhado, equipa e documentos da proposta. Vivem no
Programa de Concurso e no Caderno de Encargos, e é um modelo que os lê
de lá quando as peças chegam (ver o ponto seguinte). Enquanto as peças
não vierem, aparecem assinalados na tabela de propósito, para veres o
que falta em vez de parecer que não existe.

Se abrires um anúncio que o radar ainda não tinha lido — um antigo, por
exemplo — ele lê-o na altura, demora cerca de um segundo, e fica
guardado. Não precisas de esperar por verificação nenhuma.

### Lotes

Quando o anúncio diz «Procedimento com lotes? Sim» (23% dos que têm
detalhe lido), a ficha tem um bloco **Lotes**, com entrada no índice:
cada lote com a descrição e o preço base que o DR publica. Se o
registo da empresa (§11) tiver linhas deste concurso lote a lote, a
coluna «A empresa» diz, por lote, se fomos e como acabou — ganho,
perdido, submetido, não fomos — com a nossa proposta e o lugar. Se
a linha da empresa for do **conjunto** (o preço é a soma dos lotes), a
ficha di-lo por baixo em vez de o pôr num lote. Sem registo, a ficha
diz que os lotes são os do anúncio e que a que fomos ainda não se
sabe.

### Desfecho: como o concurso acabou

Mais abaixo na ficha há a caixa **Desfecho**, quando já há contrato
assinado: quanto foi contratado, **quem ganhou**, o preço base e
**quanto abaixo dele** se fechou. Quando o concurso tinha lotes, uma
linha por lote, e a percentagem é a do procedimento inteiro — os lotes
somam-se antes de dividir, senão o número mentia.

Vem do Portal BASE e liga-se pelo **número deste anúncio**, não por
parecença: ou é este concurso ou não aparece. Não confundir com os
**Procedimentos homólogos**, logo a seguir, que são as edições
anteriores parecidas — esses são um palpite pelo título.

Contratos demoram: **metade dos concursos só assina 68 dias depois** do
anúncio, e um em cada dez passa dos 139. Por isso num anúncio recente a
caixa nem aparece — não há nada a dizer ainda. Só passados seis meses é
que ela diz «ainda sem contrato celebrado», e aí já quer dizer alguma
coisa: ficou deserto, foi anulado, ou nunca chegou ao Portal BASE.

Sobre as peças: o botão **Trazer peças** vai buscá-las à plataforma
indicada no anúncio. Também vêm sozinhas quando marcas **interessa** —
nesse caso a ficha mostra "a trazer as peças…" e actualiza-se sozinha
quando elas chegam, o que leva alguns segundos.

### As peças lidas

> **O que o modelo lê, e porquê em três pedidos**, está no
> `docs/FUNCIONAL.md` §3.6. Aqui fica o que tu fazes e o que te pode
> surpreender.

Assim que as peças chegam, o modelo lê e preenche sozinho. Leva cerca
de cinco segundos, corre em fundo, e a ficha só deixa de dizer «a
trazer as peças…» quando já lá está tudo. Se preferires accionar à mão,
ou se falhar, há o botão **Ler peças**.

O que sai vem marcado com o nome do modelo e um aviso para confirmares
no documento. **Não é para assinar por baixo**: é para saberes, em cinco
segundos, se vale a pena abrir os PDF.

Quando o Programa não fixa limiar de preço anormalmente baixo — o que é
o caso na maioria — a tabela di-lo em vez de te mandar procurar.

**Uma leitura que fique a meio volta a tentar-se sozinha**, cinco por
verificação, e só às dos concursos que estão na escada: gastar o tecto
do dia num que ninguém olhou é tirá-lo a um que se vai entregar. À mão,
`python radar.py --ler-pecas` também as apanha, e sem esse limite.

**Precisa de uma chave.** Um ficheiro `groq_API_KEY.txt` na pasta do
radar, com a chave lá dentro e mais nada. Sem ele os campos
ficam simplesmente por preencher, e o resto funciona na mesma.
O ficheiro está fora do controlo de versões, de propósito.

Funciona nas plataformas que aparecem na base — acingov, vortal,
anogov, ComprasPT e a plataforma da ESPAP — o que cobre 99% dos
anúncios que indicam plataforma. Os que faltam apontam para a página
inicial de uma câmara ou para um painel sem código de acesso, e não há
lá nada para ir buscar automaticamente. O PDF oficial do anúncio vem sempre, seja qual for.

**Ficheiros muito grandes ficam de fora.** Alguns anúncios (sobretudo da
Infraestruturas de Portugal) trazem anexos técnicos de centenas de MB.
Acima de 60 MB o radar não os traz, diz-te quais são pelo nome, e marca
o anúncio como parcial — vais buscá-los pelo botão **Peças na
plataforma**, na ficha.

Não se descarrega tudo de uma vez de propósito: seriam centenas de GB.
Assim ficas com as peças daquilo em que trabalhas mesmo.

## 7. A conta, e quem está a trabalhar

Desde 8/09/2026 o painel tem login. A conta cria-se uma vez, num
terminal aberto na pasta:

```bash
.venv/bin/python radar.py --criar-utilizador admin
```

O nome de utilizador é o que quiseres, sem espaços — `admin` serve,
não precisa de ser um e-mail. Pergunta o tipo (admin ou tester; Enter
é admin) e a palavra-passe (8 caracteres ou mais, escrita duas vezes,
sem aparecer no ecrã). Desde 26/09/2026 recusa as fáceis — as mais
usadas, `aaaaaaaa`, `12345678`, sequências do teclado, e as que têm o
nome de utilizador lá dentro —, e diz qual foi o problema; vale igual
no painel e no convite. As contas seguintes criam-se no painel, em
**Configurações › Conta**, por um admin.

**Cada conta é de uma empresa** (desde 23/09/2026), e só vê o trabalho
dela — **menos a tua**: a conta do dono da plataforma não é de empresa
nenhuma, e só abre a administração da plataforma. Para trabalhar numa
empresa usa outra conta, dela. Uma empresa nova nasce de um pedido de
acesso aceite (o convite), ou num terminal, com a primeira conta dela a
seguir:

```bash
.venv/bin/python radar.py --criar-empresa "NOME DA EMPRESA"
.venv/bin/python radar.py --criar-utilizador NOME --empresa 2
```

Dentro de uma empresa, o admin dela convida os colegas sem ti: em
Configurações › Conta, **Criar convite** dá uma ligação que ele manda
ao colega, e é o colega que escolhe o nome e a palavra-passe.

Para tirar uma empresa inteira — propostas, tarefas, contactos,
histórico, configuração, triagem e contas —:

```bash
.venv/bin/python radar.py --apagar-empresa N
```

Pede que escrevas APAGAR, faz uma cópia antes, e a pasta da empresa
não desaparece: vai para `copias/empresa-N-apagada-…`, e apagas-a tu
quando tiveres a certeza.

**Há três níveis.** **Tu és o dono da plataforma**: só tu vês os
Indicadores, as Capturas, a Recolha, a Leitura das peças e as Cópias,
o botão «Verificar agora», a conta que envia o e-mail e os pedidos de
acesso do site — tudo na **administração da plataforma**, no menu da
tua conta. Não vês o trabalho de nenhuma empresa: a tua conta não é
de nenhuma, e tudo o que não é da plataforma leva-te de volta a ela. O
**admin** de uma empresa cria e tira as contas **dela** e diz quem ela é
(nome e NIF). O **tester** vê os anúncios, o que está em curso e o
mercado, e nas configurações só a Conta, o Perfil da empresa, os Alertas e o
Importar dados; no resumo por e-mail só escolhe para quem e a que hora.

**Neste computador não vês o login.** Um pedido vindo daqui entra
como tu, sem palavra-passe — é o `"acesso_livre_local": true` do
`config.json`. Quem vem de fora (pelo `tunel.sh`, secção 15) cai no
ecrã de entrar, e a sessão dura 30 dias em cada aparelho. No canto
direito da barra de cima está o teu nome; ao abrir há «a conta»,
«sair» e «sair de todos os aparelhos», que fecha todas as sessões de
uma vez — se perderes o telemóvel, é isso.

Mudar a palavra-passe faz-se em **Configurações › Conta** (pede a
actual), e é lá que se vêem as sessões abertas, cada uma pelo aparelho
(«iPhone até 10/10/2026 14:35»).

**Quando alguém se esquece da palavra-passe** (desde 26/09/2026) não há
e-mail de recuperação — o ecrã de entrar diz para pedir ao
administrador da empresa. Quem repõe:

- o **admin da empresa**, para as contas dela: em Configurações ›
  Conta, na lista dos utilizadores, **repor palavra-passe**;
- **tu**, para qualquer conta de qualquer empresa (e para a tua): na
  administração da plataforma, na lista **Contas**, **repor
  palavra-passe**.

Sai uma ligação, que só se vê nessa página — copia-a e manda-a à
pessoa por onde falares com ela. Vale 24 horas e uma vez; se gerares
outra, a primeira deixa de servir. Quem a abre escolhe a palavra-passe
nova, entra, e **todas as sessões que essa conta tinha abertas
fecham-se** (se alguém a estava a usar sem autorização, deixa de
estar). O admin de uma empresa não repõe a tua conta.

E continua a dar pelo terminal deste computador, que grava a nova por
cima:

```bash
.venv/bin/python radar.py --palavra-passe admin
```

Cinco tentativas erradas em quinze minutos, pelo mesmo utilizador ou pelo
mesmo IP, e a porta espera; as falhas ficam nos Indicadores, na série
dos erros, que é como se vê se alguém anda a bater à porta.

A partir de estares identificado fica registado quem marcou
interessa, quem moveu de fase e quem ficou responsável por cada
concurso — vês esse registo na ficha do anúncio, em baixo. Na ficha
podes também atribuir o concurso a uma pessoa, e essa lista de nomes
é livre: um colega sem conta pode ser responsável.

## 7-A. Configurações

**As peças novas na plataforma.** Um esclarecimento ou uma errata
não passam pelo DR: aparecem só na lista de documentos da plataforma.
Desde 14/09/2026 o radar vai lá ver sozinho, nos anúncios marcados
com peças já trazidas, em duas alturas: depois de passar a data de
esclarecimentos (o primeiro terço do prazo, a regra supletiva do CCP)
e sempre que o prazo ou o preço base mudam. O que aparecer de novo
fica guardado ao lado das outras peças, no histórico da ficha e no
resumo por e-mail — e o anúncio é logo relido pelo modelo, para a
leitura das peças ficar com a versão nova. **A leitura é a mesma para
todas as empresas** (desde 23/09/2026): uma vez completa, só tu a podes
mandar reler; e cada empresa pode pedir até 10 leituras por dia (o
número muda-se no `config.json`, `leituras_por_empresa_por_dia`). E na
ficha há o botão
**«Ver se há peças novas»**
para quando queres olhar já: responde na hora com o que encontrou.
Não confundir com «Actualizar peças», que apaga e volta a trazer tudo.

A ligação **Configurações** está à direita na barra de cima (desde
8/09/2026; o separador Alertas passou para aqui, e a 13/09/2026 os
Indicadores também). É onde dizes ao Mira Gov como queres que ele
trabalhe, em nove secções, cada uma com o seu botão «Guardar» — gravar
uma não toca nas outras, e cada gravação fica no histórico com o
valor de antes e o de depois. As quatro primeiras são de toda a gente;
as outras cinco só um admin as vê:

- **Conta** — a palavra-passe (pede a actual), as sessões abertas,
  «sair de todos os aparelhos» e, para o admin, os utilizadores: quem
  existe, de que tipo, criar outro (utilizador, palavra-passe, tipo) e
  tirar um — a tua própria conta e o último admin não se tiram.
- **Perfil da empresa** — a árvore de CPV, já aberta, com o que está
  guardado marcado, e por baixo os **distritos** do local de execução e
  o **preço base mínimo**. Marca e carrega em «Guardar o perfil» (ou
  em «Guardar», para os distritos e o valor): com alguma coisa escolhida
  fica ligado, sem nada fica desligado. Uma linha por cima diz o que
  está em vigor e quantos anúncios apanha. O distrito e o preço base
  também se escolhem no filtro dos Concursos e nos alertas.
- **Alertas** — os alertas com o interruptor e a taxa de acerto, as
  entidades seguidas, o «Filtro de alertas» em três grupos — o que é
  comum, o que é só dos anúncios (é por esses que o alerta avisa) e o
  que é só dos contratos (serve para aplicar o filtro ao Mercado) — com
  o botão «Criar alerta», que o cria já ligado, e em cada alerta o
  «avisar logo» — um e-mail a cada verificação em vez de esperar pelo
  resumo —, o resumo por e-mail (para quem e a que hora; e,
  só para o admin, **quem envia**: conta, servidor, porta e
  palavra-passe — esta grava-se no `email_senha.txt`, nunca no
  `config.json`, e o campo fica sempre vazio), a janela do urgente,
  «enviar já» e os últimos avisos. Os «filtros guardados» de antes
  deixaram de existir: o que era guardar um filtro para o reaplicar é
  o Perfil da empresa; o que era guardá-lo para avisar é criar um alerta.
  Um alerta com uma data ou um valor que não se lê **não se grava**, e
  a página diz quando o e-mail ainda não sai, e porquê.
- **Importar dados** — o registo da empresa, pelo modelo Excel (§13).
- **Indicadores** — a saúde do sistema e os números (§8), com a
  verificação automática e a última verificação que estavam na barra.
- **Recolha** — as horas da verificação (o temporizador dispara a
  todas as horas e é esta lista que decide quais contam; mudá-la já
  não pede o `agendar.sh`), a janela de
  recuperação, a janela e o ritmo do detalhe, a Vortal ligada ou não.
  Com limites: um zero na janela do detalhe calava a recolha em
  silêncio, por isso agora recusa.
- **Leitura das peças** — o fornecedor em uso e o modelo de cada um,
  e o estado de cada chave (em que ficheiro está e desde quando), com
  um campo para colar uma nova. Uma chave posta por variável de
  ambiente aparece como tal e não se edita.
- **Capturas** — o estado das duas capturas (`curl_DR.txt` e
  `curl_detalhe.txt`) e uma caixa para colar a nova; valida antes de
  gravar, e uma colagem errada não toca no ficheiro que lá está.
- **Cópias** — a cópia diária ligada ou não, quantas guardar, o
  último ensaio, e a lista do que existe em `copias/`.

O que fica no `config.json` à mão, de propósito: os termos de pesquisa
e de reserva, `paginas`, `por_pagina`, `abrir_browser_ao_encontrar`,
`acesso_livre_local` e `endereco_publico` — afinação de quem mexe no
código.

**Desde 23/09/2026 a configuração está em dois ficheiros.** O que é
**da empresa** — o nome e o NIF, o interesse, os alertas ligados ou
não, para quem vai o resumo e a que hora, a janela do urgente — vive em
`empresas/1/config.json`, ao lado do trabalho dela. O resto — as horas
da recolha, a conta que **envia** o e-mail, a leitura das peças, as
cópias — continua no `config.json` da pasta, que é da plataforma. O
painel grava cada coisa no sítio certo sozinho; só precisas de saber
isto se fores abrir os ficheiros à mão.

## 8. Indicadores

Estão em **Configurações › Indicadores**, só para o admin — é
consulta ocasional, não trabalho diário. A verificação automática
(as horas) e a última verificação, com o ponto verde/vermelho, estão
lá em cima, no «Estado da recolha». Números sobre o teu próprio radar:
quantos anúncios tens, quantos entraram hoje, quantos marcaste como
interessa (e destes, quantos estão dentro da janela do "urgente" — os
mesmos N dias do filtro e da etiqueta cor de âmbar, editáveis em
Configurações › Alertas), quantos ainda estão sem detalhe lido, e o estado da recolha — se as capturas ainda são
válidas e que percentagem de peças se consegue por plataforma. Na saúde
aparecem também a última cópia, o último ensaio de restauro
(`--ensaiar-copia`, secção 13) e, se houver, o último erro que o painel
deu (uma página a dizer «Correu mal» fica aqui registada).

É tudo lido da tua base, não sai nada para fora.

## 9. A escada, e o bloco «A nossa proposta»

> **O que a escada é** — as dez ranhuras, o que cada uma exige para se
> entrar nela, e as listas fechadas de motivos — está no
> `docs/FUNCIONAL.md` §3.1, e só lá. Aqui fica o que tu fazes com ela.

**A ranhura muda-se na linha.** Em qualquer lista — a dos Concursos, a
do Hoje — cada linha tem um selector com as oito palavras mais «tirar
da escada». Escolhe e carrega em «ir».

Duas coisas podem travar-te, e as duas dizem porquê:

- se a ranhura pedir **motivo** («Perdido», «Não fomos»), abre-se uma
  caixa a perguntar, com a lista à escolha;
- se faltar um **campo** que ela exige — o preço proposto, o lugar —, o
  gesto é recusado e o aviso diz exactamente o que falta. Preenche no
  bloco «A nossa proposta» e escolhe outra vez.

**Tudo o resto vive no bloco «A nossa proposta»**, na ficha do anúncio —
e há um bloco por lote, quando há lotes. Lá dentro: a ranhura, os campos
que ela pede, o que a empresa decide (tipologia, CV, proposta técnica),
o CoE, as notas, as etiquetas, o que falta fazer, e o desfecho do Portal
BASE quando já há contrato celebrado. O responsável escreve-se no cartão
«Responsável», ao lado, que aparece quando o concurso já está na escada.

**Marcar interessa** num anúncio põe-no em «Por analisar» — e é o sinal
que manda o radar ir buscar as peças. **Voltar a por ver** tira-o da
escada; se a proposta já tiver trabalho escrito (preço, notas, lugar,
CoE), volta a «Por analisar» em vez de se apagar, e o aviso diz porquê.

## 10. O calendário

A segunda vista dos **Concursos** — os prazos postos no tempo, **por
dia** e não numa grade de colunas. Seis semanas a partir de hoje, um
quadrado por dia, e dentro de cada um os concursos cujo prazo cai nele.
Um «+N» quando não cabem todos, que abre exactamente esses N.

Vale para **qualquer ranhura**, e não só para os interessados: o que o
calendário mostra é o recorte que estiver escolhido.

## 10-A. A lista

Já não é uma vista à parte. **É a própria lista dos Concursos**: as
oito ranhuras da empresa mostram propostas em vez de anúncios, com as
colunas da tua folha — título, cliente, preço, esclarecimentos,
entrega, tipologia, estado, lote, responsável. O `/lista` redirecciona
para lá.

O que a empresa decide já não se escreve na linha: escreve-se no bloco
«A nossa proposta» da ficha, que é onde vive tudo o que é da proposta.
A coluna «Proposto» só aparece de «Submetido» para a frente — antes
disso não está por preencher, é impossível, e uma coluna de travessões
que nunca poderá ter nada é uma pergunta sem resposta.

## 11. O registo da empresa

O «registo da empresa» é o que a empresa fez com cada concurso: se foi,
com que proposta, em que lugar ficou, quem eram os concorrentes. Desde
8/09/2026 entra **pelo modelo do radar**, em **Configurações › Importar
dados**, em três passos:

1. **Descarregar o modelo.** Um Excel vazio com as colunas que o Mira Gov
   precisa: referência do anúncio no DR (ex. `1947/2026`, tal como a
   ficha a mostra — é o que liga a linha ao anúncio, sem adivinhar),
   lote (só quando o concurso tem lotes e a linha é de um), estado (Não
   fomos, Submetido, Ganho, Perdido — lista de escolha), razão de não
   participação, valor da proposta, lugar, concorrentes (separados por
   `;`), responsável, notas e **data da decisão** (dd/mm/aaaa: é ela que
   diz em que período do Ponto de situação a proposta conta; vazia, conta
   o prazo do anúncio). A folha «Instruções» explica cada coluna e tem
   um exemplo. Uma linha por concurso, ou por lote. Uma referência
   escrita à mão («Anúncio n.º 8023/2026», «8023/26») lê-se, e o ensaio
   diz como a leu.
2. **Carregar o ficheiro preenchido.** O radar mostra um **ensaio**:
   linha a linha, se **entra** ou **não entra**, a que anúncio liga, e o
   que não liga e porquê — referência que não existe, republicação em
   vez do anúncio original, lote que o anúncio não tem, estado fora da
   lista, valor ou data que não se lêem, linha repetida. Diz também o que
   cada linha faz ao que já existe: **nova**, **altera** (e o quê — «preço
   362 000,00 € → 1 000,00 €»), **igual**, ou **mantém-se**, quando a
   proposta já está noutra fase no Mira Gov (essa não se substitui); o
   que o Portal BASE diz de um Ganho ou Perdido («não bate» quando o dá
   a outro); e as colunas do ficheiro que não são do modelo. Nada é
   gravado nesta altura.
3. **Confirmar.** As linhas sem erro entram no registo e **escrevem a
   triagem**: «Não fomos» abandona o anúncio com a razão como motivo;
   Submetido, Ganho e Perdido marcam interessa e põem o cartão na fase
   certa, com a proposta e o lugar. Cada lote é uma proposta sua, com a
   sua ranhura: um concurso com três lotes tem três blocos «A nossa
   proposta» na ficha, e cada um move-se sozinho. O responsável é da
   proposta. No mesmo ficheiro, uma linha repetida (mesma referência e
   lote) é um erro e fica a primeira; voltar a importar uma referência
   que já entrou substitui o que ela tinha, por isso corrigir é
   preencher outra vez e voltar a carregar. As notas entram no campo
   Notas da proposta.

**Desfazer uma importação** (desde 26/09/2026): em «O que já está», cada
importação tem o seu **desfazer**. As propostas que ela tocou voltam a
como estavam antes — as que ela criou saem, as que já existiam voltam
ao que eram, com as tarefas. Se alguém mexeu numa delas depois de
importar, essa fica como está, e o aviso diz qual.

Os ficheiros carregados ficam em `importacoes/`, fora do git.

O Excel antigo de análise de concursos (`Analise_Concursos_Publicos.xlsm`)
**deixou de contar para a aplicação**, por decisão tua a 8/09/2026:
fica nos documentos, e o que o radar tinha lido dele saiu com o estado
zero desse dia. A 15/09/2026 **saiu também o leitor** — o radar já não
sabe abrir esse ficheiro, e não precisa: o que ele tinha foi importado e
o registo novo entra pelo modelo. Está no histórico do git, se algum dia
voltar a ser preciso. Para repor a aplicação como acabada de instalar — sem
perder os anúncios — há o comando, que faz cópia antes e pede
confirmação:

```bash
.venv/bin/python radar.py --estado-zero
```

## 12. Histórico de alterações

Corre `./historico.sh`. Abre uma janela com todas as
alterações ao programa: à esquerda a lista, e ao clicar numa vês
exactamente que linhas mudaram, a verde e a vermelho.

Fica tudo **no teu PC**, dentro da pasta `.git`. Não há nada online e
não sai nada para lado nenhum.

Ficam de fora do histórico, de propósito: as capturas (levam o token da
tua sessão), a base de dados e a pasta `pecas/`.

Na linha de comandos, se preferires:

```bash
git log --oneline
```

## 12-A. Trazer uma versão nova

O radar **não se actualiza sozinho**. Fica na versão que tem até tu
correres, na pasta:

```bash
./actualizar.sh
```

Traz a última versão publicada, instala o que for preciso e **reinicia
sempre o painel** — mesmo quando não havia nada a trazer, porque o
painel só lê o código ao arrancar. Demora segundos. Três coisas a
saber:

- **Nunca traz trabalho a meio.** Só avança até uma versão *publicada*
  (uma «release»), nunca até ao último remendo que alguém gravou.
- **Não mexe na tua configuração nem na tua triagem.** O `config.json`
  e o `triagem.jsonl` já não estão no git: o guião põe-nos de lado
  antes de actualizar e repõe-nos depois. Recusa-se só se houver
  alterações por gravar no código, e diz-te qual é.
- **Recusa-se se não puder avançar em linha recta.** Se isso acontecer
  não mexeu em nada — é caso para me dizeres, não para forçares.

Para saber em que versão estás, a ligação no canto da barra; ou, na
pasta, `git describe --tags`.

> **Corrigido a 19/09/2026, e vale a pena saber porquê.** O guião saía
> no «já está na última release» **antes** de reiniciar o painel — e
> nesta pasta esse é o caso de todos os dias, porque o código escreve-se
> aqui e não há nada para trazer. Resultado: o painel esteve dezassete
> horas a servir código antigo sem nada o dizer. Agora o reinício é
> sempre, e a linha final distingue «está na release» de «está à frente
> dela».

## 13. Comandos, se precisares

O uso normal é o painel. Estes são para casos pontuais:

```bash
python radar.py --historico 730
```
Puxa 730 dias (2 anos) de anúncios de uma vez. Demora horas — é um
pedido por página, e depois um por anúncio para os detalhes.

```bash
python radar.py --historico 2015-01-01 2024-08-19
```
O mesmo, mas para um intervalo de datas, em janelas de 30 dias que vão
sendo gravadas à medida que chegam. É esta a forma de trazer anos: dá
para parar a meio, e repetir não duplica nada.

```bash
python radar.py --detalhes tudo
```
(ou `./detalhes.sh`, que é o mesmo com as instruções
escritas na janela.) Vai buscar o detalhe — CPV, prazo, preço base, plataforma, texto — de
todos os anúncios que ainda não o têm. Faz falta porque a rotina diária
só lê o detalhe dos últimos 60 dias, e sem detalhe um anúncio **não
aparece num filtro por CPV, nem na árvore, nem nos indicadores**: está
na base e é como se não estivesse. A 3/09/2026 eram 60 190 anúncios.

Isto **demora cerca de 3 horas** — 8 pedidos ao portal do DR ao
mesmo tempo, em vez de um a seguir ao outro. O Afonso decidiu isto a
3/09/2026 depois de medir: um ensaio de 150 pedidos em graus de 1 a 8
não mostrou nenhum erro nem sinal de o portal reagir mal. Não gasta
tokens nem dinheiro nenhum: é só ir buscar páginas (o que gasta modelo
é o `--ler-pecas`). Ver `docs/diario/2026-09.md` para a história
completa.

Deixa correr numa janela e esquece. Podes parar com Ctrl-C, fechar o
computador, ir dormir: **não perdes nada** — cada anúncio fica gravado
assim que é lido, e o mesmo comando outra vez continua de onde ia. Se a
rede falhar, ele espera 30 segundos e tenta outra vez, três vezes,
antes de desistir. Vai dizendo quantos já leu e quanto falta.

Para experimentar primeiro, põe um número em vez do `tudo`:
`python radar.py --detalhes 20` lê vinte e sai (meio minuto).

```bash
python radar.py --reler
```
Reanalisa o texto que já está guardado, sem ir ao DR: recalcula CPV,
prazo, preço e plataforma. Segundos para a base toda. Só faz diferença
depois de o programa ser melhorado a ler os anúncios — não traz nada
de novo.

```bash
python radar.py --ler-pecas
```
Lê pelo modelo os concursos que já têm peças mas ainda não têm análise
— serve para recuperar os que trouxeste antes de isto existir. Diz-te
o que leu e o que falhou. Acrescenta `tudo` ao fim para reler também os
que já têm análise.

```bash
python radar.py --importar-cpv ficheiro.json
```
Carrega uma versão nova do vocabulário CPV.

```bash
python radar.py --contratos
```
Actualiza o corpus de contratos do Portal BASE (o ano corrente e o
anterior). A tarefa semanal de segunda já o faz; à mão serve para anos
mais antigos (`--contratos 2019-2026`) ou para não esperar pela
segunda. Também há o botão "Actualizar contratos" no painel.

```bash
python radar.py --descartar-expirados
```
Descarta os "por ver" cujo prazo já passou — arquivo, não triagem.

```bash
.venv/bin/python radar.py --ensaiar-copia
```
Prova que a última cópia de `copias/` se restaura, sem a restaurar:
abre-a só de leitura, verifica a integridade e conta os anúncios, a
triagem, o histórico e as contas contra a base viva. Diz «Serve.» ou
«NÃO SERVE». Corre-o uma vez por mês; o resultado fica na secção
Cópias e nos Indicadores. Podes indicar outra cópia a seguir ao
comando.

**Se um dia for preciso restaurar de verdade** (a base corrompeu-se,
uma importação estragou a triagem), é isto, por esta ordem, na pasta
do radar:

```bash
systemctl --user stop radar-painel.service radar-hora.timer
.venv/bin/python radar.py --ensaiar-copia copias/radar-AAAA-MM-DD.db
cp radar.db radar-estragada.db          # guarda a que lá está, por via das dúvidas
rm -f radar.db-wal radar.db-shm         # o resto da base antiga; sem isto misturam-se
cp copias/radar-AAAA-MM-DD.db radar.db
# e o trabalho da empresa, que desde 23/09/2026 é um ficheiro à parte
rm -f empresas/1/empresa.db-wal empresas/1/empresa.db-shm
cp copias/empresa-1-AAAA-MM-DD.db empresas/1/empresa.db
systemctl --user start radar-painel.service radar-hora.timer
```

**Cópias fora deste PC** (desde 23/09/2026). As cópias acima estão no
mesmo disco que a base: se o PC se perder, perdem-se com ele. Para isso
há o **`./copias_fora.sh`**, que corres **uma vez**: descarrega o
programa que as envia (o `rclone`) e pede-te os três dados de uma conta
gratuita do **Backblaze B2** (10 GB, sem cartão — as cópias das empresas
têm centenas de KB): o keyID, a applicationKey e o nome do bucket. O
resto faz sozinho, e no fim mostra-te a palavra-passe da cifra. A partir daí, a primeira verificação de cada dia manda
para lá, **cifradas antes de sair daqui**, a cópia de cada empresa e a
das contas (`contas-AAAA-MM-DD.db`: quem entra, os convites, os pedidos
do site). Lá ficam 90 dias. O estado vê-se em Configurações › Cópias,
na linha «Fora deste PC». **Guarda a palavra-passe da cifra fora deste
PC** (num gestor de palavras-passe, ou em papel): sem ela, as cópias lá
fora não se lêem — nem por ti. Para trazer uma de volta, o
`./copias_fora.sh` diz o comando.

**As cópias são duas por dia desde 23/09/2026**: `radar-AAAA-MM-DD.db`
(os anúncios, as peças lidas, as contas) e `empresa-1-AAAA-MM-DD.db`
(as propostas, as tarefas, os contactos, o histórico — o trabalho da
empresa, que é o que não se recupera de lado nenhum). O ensaio abre as
duas. Restaura-se o par da mesma data; só o da empresa, se foi só o
trabalho que se estragou.

Perde-se o que entrou depois dessa cópia: a recolha seguinte traz os
anúncios outra vez, mas a triagem desses dias não volta (a do
`empresas/1/triagem.jsonl`, se for mais recente do que a cópia,
repõe-se com `--repor-triagem`).

```bash
python radar.py --exportar-triagem
```
Escreve o `empresas/1/triagem.jsonl` — a parte irrecuperável do
trabalho da empresa (a tua triagem, fases, etiquetas, histórico,
filtros, seguidas) num ficheiro de texto, **só neste computador**.
**Não precisas de fazer nada**: cada verificação o reescreve. Desde
23/09/2026 não vai para o GitHub (lá só entra código), por isso não te
salva se perderes o disco — para isso, leva `copias/` para fora de vez
em quando.

**Desde 15/09/2026 leva também as propostas e as tarefas** — o preço
proposto, o lugar no relatório, os três primeiros, o motivo, a
tipologia, o CV, a proposta técnica, as notas e o CoE. É a parte mais
irrecuperável de todas, porque o Diário da República não te devolve o
preço que propuseste; até esse dia não ia no ficheiro e ninguém tinha
dado por isso.

```bash
python radar.py --repor-triagem
```
O caminho inverso, para depois de um desastre: com a base refeita pela
recolha (`--historico 730`), repõe as decisões do `empresas/1/triagem.jsonl`.
Idempotente; os anúncios que ainda não voltaram do DR ficam listados
para se repor outra vez mais tarde.

```bash
python teste_radar.py
```
Corre os testes — mais de 850 verificações em poucos segundos, sem tocar
na rede nem na base verdadeira. Vale a pena corrê-los depois de
qualquer alteração ao `radar.py`. Se o DR mudar o formato dos
anúncios, é o teste do parser que avisa primeiro.

## 14. Ficheiros

| Ficheiro | Para que serve |
|---|---|
| `radar.py` | o programa |
| `empresa.py` | o modelo Excel do registo da empresa (secção 11): escreve-o, lê-o e aplica-o |
| `curl_DR.txt` / `curl_detalhe.txt` | as tuas capturas, secção 3 |
| `config.json` | a configuração da plataforma (recolha, horas, e-mail que envia, leitura das peças, cópias); fora do git, criado no primeiro arranque |
| `empresas/1/config.json` · `empresas/1/triagem.jsonl` | a configuração da empresa (interesse, alertas, resumo) e a exportação da triagem dela |
| `radar.db` | os anúncios, as peças lidas, as contas — o que é da plataforma |
| `empresas/1/empresa.db` | o trabalho da empresa: propostas, tarefas, contactos, histórico (desde 23/09/2026) |
| `contratos.db` | o corpus de contratos do BASE (refaz-se com `--contratos`) |
| `copias/` | cópia diária do `radar.db` e do `empresa.db`, sete de cada guardadas |
| `amostras/` | a última colheita e, se houver, a resposta que correu mal |
| `pecas/` | as peças dos concursos que foste buscar |
| `AVISOS.txt` | o último resumo dos alertas em texto, quando há (o e-mail leva o mesmo, formatado) |
| `instalar.sh` | cria o `.venv/` e instala as dependências |
| `iniciar.sh` | abre o painel (ou diz que o serviço já o tem aberto) |
| `agendar.sh` | cria os dois temporizadores (a verificação de hora a hora e a do corpus) e o serviço do painel |
| `verificar.sh` | o que o temporizador de hora a hora corre |
| `actualizar.sh` | traz a última versão publicada, secção 12-A |
| `desinstalar.sh` | remove temporizadores e serviço |
| `historico.sh` | abre o histórico de alterações |
| `contratos.sh` | o que o temporizador de segunda corre: refaz o corpus do BASE |
| `detalhes.sh` | vai buscar o detalhe de tudo o que ainda não o tem (~3 h), secção 13 |
| `reler.sh` | manda o modelo reler as peças já guardadas, sem ir à rede |
| `ensaio.sh` | o ensaio de leitura de um concurso: põe o que o modelo escreveu ao lado do texto do documento, sem gastar orçamento |
| `medir.sh` | mede de onde vem o token das capturas do DR (só lê as capturas) e abre o resultado |
| `tunel_fixo.sh` | monta o `https://miragov.pt` (túnel com nome, como serviço, que responde também pelo miragov.com e pelo radargov.pt); diz que registos DNS faltam |
| `copias_fora.sh` | liga as cópias a um destino fora deste PC (Backblaze B2, cifrado); corre-se uma vez, secção 13 |
| `tunel.sh` | dá um endereço público temporário ao painel, sem domínio |
| `.venv/` | o Python e os pacotes do radar |
| `teste_radar.py` | os testes |

## 15. O painel fora deste computador: miragov.pt

**O painel está em https://miragov.pt**, de qualquer computador ou
telemóvel, sem instalar nada. Desde 25/09/2026; antes era o
`radargov.pt`. O `miragov.com`, o `radargov.pt` e os `www` levam lá ter,
na mesma página em que estavas, por isso as ligações antigas continuam a
servir. Da primeira vez tens de voltar a entrar: a sessão é de cada
endereço. No telemóvel as
listas ficam a uma coluna e as tabelas largas arrastam-se de lado (a
barra já é em cima em todos os tamanhos, desde 13/09/2026). **Quem abre
sem sessão vê o site de apresentação** (desde 23/09/2026), com um
«Entrar» no canto que leva ao ecrã de entrar (secção 7); quem já entrou
vê o Hoje, como sempre. Os links do e-mail de alerta apontam para lá.

**O site** é o ficheiro `site/index.html`: muda-se o texto aí, e a
mudança vê-se sem reiniciar o painel. O formulário «Pedir acesso»
guarda cada pedido e manda-te um e-mail para o endereço dos alertas
(se o correio estiver configurado, em Configurações › Alertas). Os
pedidos vêem-se sempre no menu da tua conta, em **«pedidos de acesso do
site»** — e é aí que os vês se o e-mail não tiver chegado.

**Para dar acesso a quem pediu**, carrega em **«aceitar»** na linha do
pedido. O radar cria a empresa, com o resumo diário a ir para o e-mail
de quem pediu, e manda-lhe um convite. A pessoa abre a ligação, escolhe
o utilizador e a palavra-passe, e entra já como administradora da
empresa dela — e cria a seguir as contas dos colegas. A ligação serve
uma vez e dura sete dias. **Se o e-mail não sair**, o ecrã mostra-te a
ligação: copia-a e manda-a tu.

Como funciona, para saberes o que pode falhar: o painel continua a
atender só neste computador; um programa da Cloudflare, o
`cloudflared`, corre aqui como serviço (`radar-tunel.service`) e faz a
ponte entre o teu domínio e o painel. Por isso, **se este computador
estiver desligado, o `miragov.pt` não abre** — e se estiver ligado,
o serviço arranca sozinho, como o do painel. Para ver se está de pé:

```bash
systemctl --user status radar-tunel.service
```

E para não teres de ser tu a reparar que caiu: **`https://miragov.pt/saude`**
responde «ok» sem login quando o painel e a base estão de pé (e 503
quando a base não responde). Serve para pôr um vigilante gratuito a
bater lá de cinco em cinco minutos e a mandar-te e-mail quando falha:
o UptimeRobot (uptimerobot.com, plano Free) ou equivalente, um monitor
do tipo HTTP com esse endereço. Ligaste-o a 15/09/2026, na tua conta
do UptimeRobot: não está na pasta do radar, e se mudares de e-mail é
lá que se muda. Passou do `radargov.pt/saude` para o `miragov.pt/saude`
a 25/09/2026. O `/saude` não se reencaminha, e responde nos dois.

Foi montado uma vez com o `tunel_fixo.sh`, depois de o domínio estar
na tua conta da Cloudflare e de autorizares este computador no
browser. Não é preciso voltar a corrê-lo; se um dia o radar mudar de
computador, é `.venv/bin/cloudflared tunnel login` (abre a página de
autorização) e depois `./tunel_fixo.sh` outra vez. Os domínios que não
são o do login precisam dos seus registos DNS feitos à mão no painel da
Cloudflare, e o script diz quais faltam e o que lá pôr. Foi assim com
o miragov, a 25/09/2026.

O que continua fora: o **`tunel.sh`**, que dá um endereço
`trycloudflare.com` aleatório e temporário, sem domínio. Serve para
uma demonstração se o `miragov.pt` estiver em baixo por alguma razão;
Ctrl+C fecha-o.

## 15-B. Abrir a beta: o que preencher

Três coisas, que o radar já sabe usar e só precisam de ti (desde
23/09/2026):

1. **Quem opera o Mira Gov**, para os Termos e a Política de
   privacidade do site. No `config.json` da pasta:

   ```json
   "operador": {"nome": "O TEU NOME", "morada": "MORADA"}
   ```

   O `"nif"` é opcional: em nome individual não o pões na internet
   (23/09/2026); quando houver sociedade, entra o NIPC dela. Enquanto
   faltar o nome ou a morada, as duas páginas não aparecem. Os textos
   estão em `site/termos.html` e `site/privacidade.html` — **são um
   rascunho: lê-os, e dá-os a rever a quem responda por isto na
   empresa, antes do primeiro cliente**. Mudam-se lá, sem reiniciar.
2. **Um vigia externo**, que te avisa por e-mail se o radar parar (o
   radar parado não o pode dizer): uma conta gratuita no **UptimeRobot**
   a vigiar `https://miragov.pt/saude`, de cinco em cinco minutos.
   Chega para as duas avarias: o `/saude` dá erro com o site em baixo
   **e** quando a recolha parou (a última hora marcada passou há mais de
   40 minutos sem verificação). Se um dia quiseres também o aviso por
   «batida», há a chave `vigia_url` (healthchecks.io), opcional.
3. **As cópias fora do PC**, se ainda não as ligaste: secção 13.

## 15-A. Mudar o radar de computador

**Para o usares noutro sítio não precisas disto** — o
`https://miragov.pt` responde de qualquer lado, e é sempre a mesma
base. Isto é para o dia em que o radar passar a **correr** noutro
computador.

Cinco passos, nesta ordem:

1. **Neste**, parar o serviço
   (`systemctl --user stop radar-painel.service radar-hora.timer`) e
   levar numa pen, ou pela rede, o `radar.db`, o `config.json` e a
   pasta `empresas/`
   inteira — ou as cópias de hoje de `copias/`. **Nunca pelo GitHub**:
   desde 23/09/2026 lá só entra código, e a pasta `empresas/` é o
   trabalho das empresas.
2. **No novo**, trazer a pasta do GitHub e correr `./instalar.sh`.
3. Pôr o `radar.db`, o `config.json` e a pasta `empresas/` na pasta do radar, para não
   teres de recolher onze anos outra vez.
4. `python radar.py --contratos` (ou `./contratos.sh`) — o corpus do
   BASE **não viaja**: são 2,5 GB e refaz-se em minutos.
5. `./agendar.sh`, e as capturas da secção 3, que são deste browser.

O túnel é à parte, e está na secção 15: `cloudflared tunnel login` e
depois `./tunel_fixo.sh`.

**As peças que já descarregaste não vão** — voltam a descarregar-se
quando forem precisas.

## 16. Limites, para não haver surpresas

O DR publica anúncios acima de certos valores. Abaixo dos limiares
(ajustes directos, consultas prévias) **não existe anúncio nenhum** —
esses procedimentos são por convite e só se tornam públicos como
**contrato celebrado**. O radar traz esses contratos: o separador
Contratos carrega o dump semanal do IMPIC (dados.gov, sem chave e sem
sessão — a API que nunca respondeu deixou de fazer falta), com quase
dois milhões de contratos desde 2015. Não são oportunidades: quando lá
aparecem, já está tudo decidido. Servem para comparar preços, ver quem
ganha o quê e antecipar renovações.

As peças do procedimento (Programa de Concurso, Caderno de Encargos,
anexos) o radar também as traz — ver a secção 6 — nas plataformas que
o permitem sem sessão (acingov, vortal, anogov/ComprasPT/ESPAP), e um
modelo lê delas os campos que o anúncio não tem. Fica de fora o que a
secção 6 diz: anexos acima de 60 MB e as raras plataformas sem acesso
anónimo — para esses há o botão "Peças na plataforma" da ficha.

O que continua a não haver: número de concorrentes por concurso (não é
público em fonte nenhuma) e o que as plataformas publicam sem passar
pela parte L (consultas preliminares, contratos menores).
