# Radar de Concursos, Diário da República

Vigia a parte L da série II do Diário da República, filtra os anúncios
que interessam ao teu portefólio e mostra-os num painel local.
Verifica sozinho às 09:00 e às 17:00.

Duas fontes: o serviço de pesquisa do próprio portal do DR (os
anúncios) e o dump semanal do Portal BASE (os contratos celebrados, no
separador Contratos — ver a secção 15).

---

## 1. Onde pôr a pasta

No ambiente de trabalho, como tinhas. Guarda tudo na mesma pasta:
o programa, a captura, a configuração e a base de dados.

Nota: se a pasta ficar dentro do OneDrive, a sincronização pode
bloquear o ficheiro `radar.db` no momento em que ele está a escrever.
Se um dia vires erros de base de dados bloqueada, é isto, e resolve-se
movendo a pasta para fora do OneDrive.

**Em Ubuntu** a mesma pasta serve, também num disco NTFS. Duas coisas
a saber: o Windows deixa pastas e ficheiros marcados «só de leitura»
que o Linux respeita à letra — se a instalação disser *Permission
denied*, corre `chmod -R u+w .` dentro da pasta uma vez; e um disco
externo só é montado quando entras no ambiente de trabalho, por isso
um computador que arranque sem ninguém entrar não encontra a pasta.
Para servir o radar a sério, o sítio é o disco interno.

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
  **cada verificação de rotina** (as das 09h/17h). Serve também de rede
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

A verificação de rotina (09h/17h) só olha para os últimos `dias_catchup`
dias — não vale a pena pedir mais que isso duas vezes por dia. Para
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

A barra de cima tem três entradas, por ordem de uso:
**Anúncios** (a página inicial — a lista toda, triagem e acervo num
sítio só), **Em curso** (o quadro e o calendário dos "interessa"),
**Mercado** (os contratos e as renovações). À direita, **Configurações**
e o teu nome. Os Indicadores estão dentro das Configurações (§8).

Em cima da lista estão as quatro abas que fazem o trabalho todo:

- **Por ver** — o que está por decidir **e ainda dá para responder**:
  prazo aberto, ou, quando o prazo ainda não foi lido, publicado nos
  últimos 60 dias (a janela `detalhe_dias`). É a aba em que a página
  abre, e anda na ordem do milhar, não dos 60 mil.
- **Interessados** — os teus "interessa", todos: um interessa com o
  prazo já passado é trabalho em curso (proposta entregue, à espera de
  decisão) e não desaparece daqui.
- **Abandonados** — os que abandonaste à mão **mais tudo o que já não
  é possível responder** (prazo passado, ou publicado há tanto tempo
  que o prazo já lá vai). Passa para cá sozinho, sem mexer em nada: se
  um anúncio for rectificado com prazo novo, volta sozinho ao Por ver.
- **Todos** — a base inteira, sem recorte.

A lista vem sempre do mais recente para o mais antigo.

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

**O interesse recorta as quatro abas.** Em *Configurações › Interesse*
escolhes, na árvore, os CPV que a casa trabalha; ligado, a lista passa
a mostrar só o que corresponde — nas quatro abas, sem teres de pôr
filtro nenhum. Não é um alerta: um alerta avisa-te, o interesse esconde
o resto. A lista diz sempre que está limitada, quantos ficam de fora, e
tem um **ver tudo** que o levanta para a vista em que estás. Nasce
desligado; desligado, nada muda. Os alertas, os contratos e os filtros
guardados não são tocados — o interesse é recorte de leitura da lista,
não um filtro.

A barra de filtros trabalha sobre o que já está guardado, sem apagar
nada. **Está recolhida por omissão** (desde 8/09/2026): a lista abre
logo nos anúncios, e a linha «Filtros» diz o que está posto; carrega
nela para abrir a árvore de CPV, em cima, e os campos por baixo (a
árvore só aparece enquanto não tiveres interesse definido — com ele,
o CPV já está decidido). Abre sozinha quando há um filtro aplicado, e
lembra-se se a deixaste aberta. Desde 14/09/2026 são quatro campos:

- **nome do concurso ou objecto**. Várias palavras separadas por `|`
  valem como "qualquer uma destas" (`outsystems|.net|java`).
- **entidade que publica**. Enquanto escreves, o campo sugere as
  entidades que existem na base — escreve «sp» e aparecem as que
  começam por SP e depois as que o têm no nome, uma por NIF, com a
  grafia mais frequente e quantos anúncios tem. O DR escreve o mesmo
  nome de várias maneiras («SPMS - Serviços Partilhados…, E. P. E.» e
  «Serviços Partilhados…, EPE» são a mesma casa, NIF 509540716);
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

Um filtro que valha a pena repetir guarda-se com nome (botão "guardar
filtro") e volta-se a ele com um clique; em **Configurações › Alertas** liga-se a
qualquer filtro guardado um aviso no resumo diário, define-se o
**interesse** (os CPV que recortam a lista, ver §5), e configura-se o
e-mail e a janela do "urgente". O resumo chega formatado — um cartão
por anúncio, com o prazo colorido como na lista — e o mesmo conteúdo
fica em texto no `AVISOS.txt`. Em **Mercado** vivem os **Contratos**
(o que já foi adjudicado, com gráficos sobre o filtro), com dois modos
no mesmo ecrã: **por celebração** e **por fim estimado** — as antigas
Renovações, agora uma aba que mantém o filtro e mostra o que está a
chegar ao fim (o modo diz-se no título da tabela, e as datas de
celebração desactivam-se aí, com explicação). De lá chega-se à **ficha
de cada entidade** (o que compra e o que ganha), com uma ligação
directa a "o que está a acabar" dela — e há uma caixa **"Ficha de
entidade"** no topo que aceita nome ou NIF e abre a ficha
directamente, cobrindo todas as grafias com que a entidade já assinou.

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

Clicar no título de um anúncio — na lista, no quadro ou no calendário —
abre a ficha **dentro da aplicação**, já não o site do DR. Lá tens:

- os factos de topo: prazo com contagem de dias, preço base, plataforma,
  e o CPV já com a descrição por extenso — com uma ligação **ver
  anúncios deste CPV na Pesquisa**, para responder ao "que mais há
  disto?";
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
registo da casa (§11) tiver linhas deste concurso lote a lote, a
coluna «A casa» diz, por lote, se fomos e como acabou — ganho,
perdido, submetido, não fomos — com a nossa proposta e o lugar. Se
a linha da casa for do **conjunto** (o preço é a soma dos lotes), a
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

Assim que as peças chegam, um modelo lê o Caderno de Encargos e o
Programa e preenche os quatro campos que faltavam. Leva cerca de cinco
segundos, corre em fundo, e a ficha só deixa de dizer "a trazer as
peças…" quando já lá está tudo. Se preferires accionar à mão, ou se
falhar, há o botão **Ler peças**.

O que sai vem marcado com o nome do modelo e um aviso para confirmares
no documento. Não é para assinar por baixo: é para saberes, em cinco
segundos, se vale a pena abrir os PDF.

Quando o Programa não fixa limiar de preço anormalmente baixo — o que é
o caso na maioria — a tabela di-lo em vez de te mandar procurar.

**Precisa de uma chave.** Um ficheiro `groq_API_KEY.txt` na pasta do
radar, com a chave lá dentro e mais nada. Sem ele os quatro campos
ficam simplesmente assinalados como antes, e o resto funciona na mesma.
O ficheiro está fora do controlo de versões, de propósito.

Só saem daqui documentos que já são públicos — Cadernos de Encargos e
Programas. Propostas, CVs e trabalho teu não passam por lá.

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
sem aparecer no ecrã). As contas seguintes criam-se no painel, em
**Configurações › Conta**, por um admin.

**Há dois tipos de utilizador** (desde 13/09/2026). O **admin** vê
tudo e cria contas. O **tester** vê os anúncios, o que está em curso e
o mercado, e nas configurações só a Conta, o Interesse, os Alertas e o
Importar dados — não vê os Indicadores, as Capturas, a Recolha, a
Leitura das peças nem as Cópias, não tem o botão «Verificar agora», e
no resumo por e-mail só escolhe para quem e a que hora.

**Neste computador não vês o login.** Um pedido vindo daqui entra
como tu, sem palavra-passe — é o `"acesso_livre_local": true` do
`config.json`. Quem vem de fora (pelo `tunel.sh`, secção 15) cai no
ecrã de entrar, e a sessão dura 30 dias em cada aparelho. No canto
direito da barra de cima está o teu nome; ao abrir há «a conta»,
«sair» e «sair de todos os aparelhos», que fecha todas as sessões de
uma vez — se perderes o telemóvel, é isso.

Mudar a palavra-passe faz-se em **Configurações › Conta** (pede a
actual), e é lá que se vêem as sessões abertas, cada uma pelo aparelho
(«iPhone até 10/10/2026 14:35»). Se te
esqueceres da palavra-passe, não há «esqueci-me» por e-mail: é no
terminal deste computador, e grava a nova por cima:

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
leitura das peças ficar com a versão nova. E na ficha há o botão
**«Ver se há peças novas»**
para quando queres olhar já: responde na hora com o que encontrou.
Não confundir com «Actualizar peças», que apaga e volta a trazer tudo.

A ligação **Configurações** está à direita na barra de cima (desde
8/09/2026; o separador Alertas passou para aqui, e a 13/09/2026 os
Indicadores também). É onde dizes ao radar como queres que ele
trabalhe, em nove secções, cada uma com o seu botão «Guardar» — gravar
uma não toca nas outras, e cada gravação fica no histórico com o
valor de antes e o de depois. As quatro primeiras são de toda a gente;
as outras cinco só um admin as vê:

- **Conta** — a palavra-passe (pede a actual), as sessões abertas,
  «sair de todos os aparelhos» e, para o admin, os utilizadores: quem
  existe, de que tipo, criar outro (utilizador, palavra-passe, tipo) e
  tirar um — a tua própria conta e o último admin não se tiram.
- **Interesse** — só a árvore de CPV, já aberta, com o que está
  guardado marcado. Marca e desmarca e carrega em «Guardar o
  interesse»: com CPV fica ligado, sem nenhum fica desligado. Uma linha
  por cima diz o que está em vigor e quantos anúncios apanha.
- **Alertas** — os alertas com o interruptor e a taxa de acerto, as
  entidades seguidas, o «Filtro de alertas» em três grupos — o que é
  comum, o que é só dos anúncios (é por esses que o alerta avisa) e o
  que é só dos contratos (serve para aplicar o filtro ao Mercado) — com
  o botão «Criar alerta», que o cria já ligado, o resumo por e-mail (para quem e a que hora; e,
  só para o admin, **quem envia**: conta, servidor, porta e
  palavra-passe — esta grava-se no `email_senha.txt`, nunca no
  `config.json`, e o campo fica sempre vazio), a janela do urgente,
  «enviar já» e os últimos avisos. Os «filtros guardados» de antes
  deixaram de existir: o que era guardar um filtro para o reaplicar é
  o Interesse; o que era guardá-lo para avisar é criar um alerta.
- **Importar dados** — o registo da casa, pelo modelo Excel (§13).
- **Indicadores** — a saúde do sistema e os números (§8), com a
  verificação automática e a última verificação que estavam na barra.
- **Recolha** — as horas da verificação (o relógio interno; os
  temporizadores do sistema mudam com o `agendar.sh`), a janela de
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
- **Cópias** — a cópia diária ligada ou não, quantas guardar, a
  triagem no git, e a lista do que existe em `copias/`.

O que fica no `config.json` à mão, de propósito: os termos de pesquisa
e de reserva, `paginas`, `por_pagina`, `abrir_browser_ao_encontrar`,
`acesso_livre_local` e `endereco_publico` — afinação de quem mexe no
código.

## 8. Indicadores

Estão em **Configurações › Indicadores**, só para o admin — é
consulta ocasional, não trabalho diário. A verificação automática
(as horas) e a última verificação, com o ponto verde/vermelho, estão
lá em cima, no «Estado da recolha». Números sobre o teu próprio radar:
quantos anúncios tens, quantos entraram hoje, quantos marcaste como
interessa (e destes, quantos estão dentro da janela do "urgente" — os
mesmos N dias do filtro e da etiqueta cor de âmbar, editáveis em
Configurações › Alertas), quantos ainda estão sem detalhe lido, como estão distribuídos
pelas fases do quadro, e o estado da recolha — se as capturas ainda são
válidas e que percentagem de peças se consegue por plataforma. Na saúde
aparecem também a última cópia, o último ensaio de restauro
(`--ensaiar-copia`, secção 13) e, se houver, o último erro que o painel
deu (uma página a dizer «Correu mal» fica aqui registada).

É tudo lido da tua base, não sai nada para fora.

## 9. O quadro

Item **Em curso**, na barra da esquerda — o quadro é a vista que abre
por omissão (o calendário é a segunda, §10). Mostra os anúncios
marcados **interessa** organizados em colunas (fases), ao estilo
Trello/kanban. O botão "Verificar agora" não está aqui: vive só na
lista dos **Anúncios**, que é onde os novos aterram — na aba "por ver".

São **seis fases, e são estas** — *Por analisar, A preparar proposta,
Submetido, Relatório preliminar, Ganho, Perdido*: o funil da casa. Podes
mudar-lhes o nome; criar e apagar colunas já não, porque cada coluna tem
um papel e é o papel que decide o que o cartão pergunta.

**Um cartão por anúncio, mesmo com lotes** — foi assim que decidiste
a 2/09/2026. O cartão de um anúncio com lotes diz a que lotes fomos
(«fomos a 2 dos 3 lotes», com uma etiqueta por lote: L1 perdido, L2
ganho…) ou que não há registo. E **no fim separam-se**: um anúncio
cujo cartão está no Ganho com lotes perdidos tem também um cartão de
lotes na coluna Perdido, a tracejado, que não se arrasta e liga ao
bloco dos lotes na ficha; e ao contrário. Isso vem do registo da
casa, lote a lote — o quadro não inventa resultados.

**Cada fase pede o que lhe falta**, no próprio cartão — e o cabeçalho
da coluna diz o quê, para se ver sem ser preciso lá pôr um cartão
primeiro:

| Fase | O que o cartão pede |
|---|---|
| Por analisar | nada |
| A preparar proposta | nada |
| Submetido | o **preço proposto** — e passa a ser esse o preço que o cartão e a soma da coluna mostram, em vez do preço base |
| Relatório preliminar | em que **lugar** ficaste e quem são os **três primeiros** |
| Ganho | nada |
| Perdido | **porquê**, à escolha de quatro: *Preço, CV's, Proposta técnica, Certificações* |

Enquanto o preço proposto não estiver preenchido, o cartão mostra o preço
base **escrito como "base"** — para não passar o tecto da entidade por
proposta tua. Tudo o que gravas nestes campos fica também no histórico da
ficha.

- **Arrastar um cartão** para outra coluna move-o de fase.
- O nome de cada coluna é editável, clica e escreve.
- **+ etiqueta**, em cada cartão, cria ou aplica uma etiqueta (com cor
  automática). O `×` ao lado da etiqueta tira-a desse cartão.
- Cada cartão mostra os dias até ao prazo de propostas: a verde se há
  folga, cor de âmbar dentro da janela do "urgente" (a mesma do filtro,
  editável em Configurações › Alertas) e a vermelho se termina hoje ou já expirou.
- **no calendário**, no pé do cartão, salta para a linha deste anúncio
  na grade (só aparece quando o prazo cabe nos 45 dias dela).
- **Voltar a por ver** devolve o anúncio a "por ver" — sai do quadro sem
  apagar nada da base.

Marcar **interessa** num anúncio, em qualquer aba da lista dos
**Anúncios**, põe-no automaticamente na primeira coluna do quadro.

## 10. O calendário

A segunda vista do **Em curso** — os mesmos "interessa" postos no
tempo. Uma grade só de leitura, uma linha por anúncio interessado com prazo,
uma coluna por dia (45 dias a partir de hoje). Cada coluna mostra o dia
da semana, o dia do mês e o mês; os fins-de-semana aparecem sombreados
e o início de cada mês tem uma linha mais marcada.

A pílula na linha, na coluna certa, mostra a fase actual desse anúncio
no quadro — clica para abrir a ficha. Cada linha tem também um **no
quadro** que salta para o cartão correspondente. Quem tem prazo já
passado ou para lá dos 45 dias não aparece na grade (fica contado numa
nota por baixo), mas continua no quadro.

## 10-A. A lista

A terceira vista do **Em curso** (desde 14/09/2026): os mesmos
interessados numa tabela, uma linha por anúncio, ordenada pelo prazo.
As colunas são as da tua folha: título, cliente, preço base,
esclarecimentos (a data-limite pela regra do primeiro terço, com
«passou» quando já foi), entrega (o prazo), tipologia (consulting ou
turnkey), estado da proposta (a fase em que o cartão está no quadro),
CV (sim/não), proposta técnica (sim/não), notas, plataforma, CoE e
responsável.

O que vem da base lê-se; o que a casa decide — tipologia, CV, proposta
técnica, notas, CoE e o responsável — escreve-se na própria linha e
grava-se com o «guardar» dela. Cada mudança fica no histórico da ficha
do anúncio, como as do quadro.

## 11. O registo da casa

O «registo da casa» é o que a empresa fez com cada concurso: se foi,
com que proposta, em que lugar ficou, quem eram os concorrentes. Desde
8/09/2026 entra **pelo modelo do radar**, em **Configurações › Importar
dados**, em três passos:

1. **Descarregar o modelo.** Um Excel vazio com as colunas que o radar
   precisa: referência do anúncio no DR (ex. `1947/2026`, tal como a
   ficha a mostra — é o que liga a linha ao anúncio, sem adivinhar),
   lote (só quando o concurso tem lotes e a linha é de um), estado (Não
   fomos, Submetido, Ganho, Perdido — lista de escolha), razão de não
   participação, valor da proposta, lugar, concorrentes (separados por
   `;`), responsável e notas. A folha «Instruções» explica cada coluna
   e tem um exemplo. Uma linha por concurso, ou por lote.
2. **Carregar o ficheiro preenchido.** O radar mostra um **ensaio**:
   linha a linha, a que anúncio liga, e o que não liga e porquê —
   referência que não existe, republicação em vez do anúncio original,
   lote que o anúncio não tem, estado fora da lista, linha repetida.
   Nada é gravado nesta altura.
3. **Confirmar.** As linhas sem erro entram no registo e **escrevem a
   triagem**: «Não fomos» abandona o anúncio com a razão como motivo;
   Submetido, Ganho e Perdido marcam interessa e põem o cartão na fase
   certa, com a proposta e o lugar. Um concurso com lotes fica no
   melhor estado dos seus lotes (ganhámos um, o cartão está no Ganho) e
   a separação faz-se no fim do quadro (§9). O responsável fica no
   anúncio. Uma linha repetida (mesma referência e lote) substitui a
   anterior, por isso corrigir é preencher outra vez e voltar a
   carregar.

Os ficheiros carregados ficam em `importacoes/`, fora do git.

O Excel antigo de análise de concursos (`Analise_Concursos_Publicos.xlsm`)
**deixou de contar para a aplicação**, por decisão tua a 8/09/2026:
fica nos documentos, e o que o radar tinha lido dele saiu com o estado
zero desse dia. Para repor a aplicação como acabada de instalar — sem
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
tua sessão), a base de dados e a pasta `documentos/`.

Na linha de comandos, se preferires:

```bash
git log --oneline
```

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
systemctl --user stop radar-painel.service radar-09h.timer radar-17h.timer
.venv/bin/python radar.py --ensaiar-copia copias/radar-AAAA-MM-DD.db
cp radar.db radar-estragada.db          # guarda a que lá está, por via das dúvidas
rm -f radar.db-wal radar.db-shm         # o resto da base antiga; sem isto misturam-se
cp copias/radar-AAAA-MM-DD.db radar.db
systemctl --user start radar-painel.service radar-09h.timer radar-17h.timer
```

Perde-se o que entrou depois dessa cópia: a recolha seguinte traz os
anúncios outra vez, mas a triagem desses dias não volta (a do
`triagem.jsonl` no git repõe-se com `--repor-triagem`).

```bash
python radar.py --exportar-triagem
```
Escreve o `triagem.jsonl` — a parte irrecuperável da base (a tua
triagem, fases, etiquetas, histórico, filtros, seguidas) num ficheiro
de texto que viaja no repositório do git. **Não precisas de fazer
nada**: cada verificação exporta E faz commit+push sozinha quando o
ficheiro muda (um push falhado retenta na verificação seguinte); à mão
serve só para forçar antes de um commit teu. Desliga-se com
`"triagem_no_git": false` no `config.json`.

**Atenção (15/09/2026):** o que o quadro e a lista do «Em curso» pedem
— preço proposto, lugar no relatório, os três primeiros, motivo da
perda, tipologia, CV, proposta técnica, notas, CoE — **ainda não vai
neste ficheiro**, e é escrito à mão. Até isso ficar feito (B15-b no
`BACKLOG.md`), o que te protege esses campos são as cópias em
`copias/`, não o git.

```bash
python radar.py --repor-triagem
```
O caminho inverso, para depois de um desastre: com a base refeita pela
recolha (`--historico 730`), repõe as decisões do `triagem.jsonl`.
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
| `casa.py` | o registo da casa: lê o Excel e liga-o aos anúncios, sem tocar no painel (secção 11) |
| `curl_DR.txt` / `curl_detalhe.txt` | as tuas capturas, secção 3 |
| `config.json` | configuração e horários, criado no primeiro arranque |
| `radar.db` | os anúncios, a triagem e o histórico |
| `contratos.db` | o corpus de contratos do BASE (refaz-se com `--contratos`) |
| `copias/` | cópia diária do `radar.db`, sete guardadas |
| `amostras/` | a última colheita e, se houver, a resposta que correu mal |
| `documentos/` | as peças dos concursos que foste buscar |
| `AVISOS.txt` | o último resumo dos alertas em texto, quando há (o e-mail leva o mesmo, formatado) |
| `instalar.sh` | cria o `.venv/` e instala as dependências |
| `iniciar.sh` | abre o painel (ou diz que o serviço já o tem aberto) |
| `agendar.sh` | cria os três temporizadores e o serviço do painel |
| `verificar.sh` | o que os temporizadores das 09h/17h correm |
| `desinstalar.sh` | remove temporizadores e serviço |
| `historico.sh` | abre o histórico de alterações |
| `tunel_fixo.sh` | monta o `https://radargov.pt` (túnel com nome, como serviço); correu uma vez |
| `tunel.sh` | dá um endereço público temporário ao painel, sem domínio |
| `.venv/` | o Python e os pacotes do radar |
| `teste_radar.py` | os testes |

## 15. O painel fora deste computador: radargov.pt

**O painel está em https://radargov.pt** (e `www.radargov.pt`), de
qualquer computador ou telemóvel, sem instalar nada. No telemóvel a
barra passa para cima e as listas ficam a uma coluna; o quadro e as
tabelas largas arrastam-se de lado. Quem abre cai no
ecrã de entrar (secção 7) e entra com o teu utilizador e a tua
palavra-passe. Os links do e-mail de alerta apontam para lá.

Como funciona, para saberes o que pode falhar: o painel continua a
atender só neste computador; um programa da Cloudflare, o
`cloudflared`, corre aqui como serviço (`radar-tunel.service`) e faz a
ponte entre o teu domínio e o painel. Por isso, **se este computador
estiver desligado, o `radargov.pt` não abre** — e se estiver ligado,
o serviço arranca sozinho, como o do painel. Para ver se está de pé:

```bash
systemctl --user status radar-tunel.service
```

E para não teres de ser tu a reparar que caiu: **`https://radargov.pt/saude`**
responde «ok» sem login quando o painel e a base estão de pé (e 503
quando a base não responde). Serve para pôr um vigilante gratuito a
bater lá de cinco em cinco minutos e a mandar-te e-mail quando falha:
o UptimeRobot (uptimerobot.com, plano Free) ou equivalente, um monitor
do tipo HTTP com esse endereço. Ligaste-o a 15/09/2026, na tua conta
do UptimeRobot: não está na pasta do radar, e se mudares de e-mail é
lá que se muda.

Foi montado uma vez com o `tunel_fixo.sh`, depois de o domínio estar
na tua conta da Cloudflare e de autorizares este computador no
browser. Não é preciso voltar a corrê-lo; se um dia o radar mudar de
computador, é `.venv/bin/cloudflared tunnel login` (abre a página de
autorização) e depois `./tunel_fixo.sh` outra vez.

O que continua fora: o **`tunel.sh`**, que dá um endereço
`trycloudflare.com` aleatório e temporário, sem domínio. Serve para
uma demonstração se o `radargov.pt` estiver em baixo por alguma razão;
Ctrl+C fecha-o.

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
