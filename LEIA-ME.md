# Radar de Concursos, Diário da República

Vigia a parte L da série II do Diário da República, filtra os anúncios
que interessam ao teu portefólio e mostra-os num painel local.
Verifica sozinho às 09:00 e às 17:00.

Duas fontes: o serviço de pesquisa do próprio portal do DR (os
anúncios) e o dump semanal do Portal BASE (os contratos celebrados, no
separador Contratos — ver a secção 14).

---

## 1. Onde pôr a pasta

No ambiente de trabalho, como tinhas. Guarda tudo na mesma pasta:
o programa, a captura, a configuração e a base de dados.

Nota: se a pasta ficar dentro do OneDrive, a sincronização pode
bloquear o ficheiro `radar.db` no momento em que ele está a escrever.
Se um dia vires erros de base de dados bloqueada, é isto, e resolve-se
movendo a pasta para fora do OneDrive.

## 2. Primeira instalação

1. Duplo clique em `instalar.bat`. Instala as dependências (flask,
   requests, pypdf, cryptography, pymupdf).
2. Faz a captura da secção 3.
3. Duplo clique em `iniciar.bat`. Abre o painel em `http://localhost:8765`.
4. Duplo clique em `agendar.bat`, uma vez só. Cria as três tarefas: as
   verificações das 09h e 17h e a actualização semanal dos contratos,
   à segunda de manhã.

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

Os cabeçalhos, o token de segurança e a forma do pedido. As datas, o
termo de pesquisa e a página são substituídos a cada verificação. Na
captura do detalhe, o que muda é a chave do anúncio.

Quando o token expirar, o painel fica com o aviso a vermelho a dizer que
a captura pode ter expirado. Repete esta secção, leva dois minutos.

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
portal recusar a pesquisa vazia.

## Histórico

A verificação de rotina (09h/17h) só olha para os últimos `dias_catchup`
dias — não vale a pena pedir mais que isso duas vezes por dia. Para
trazer um período maior de uma vez, corre:

```
python radar.py --historico 730
```

O número são os dias a recuar (730 ≈ 2 anos; omitido, usa 730). Isto
não mexe no `dias_catchup` da configuração, só faz uma recolha extra,
maior, uma vez. Para um período grande demora — uma página por segundo,
para não sobrecarregar o portal — e depois os detalhes (CPV, prazo,
preço) continuam a ser lidos aos poucos nas verificações seguintes, 40
de cada vez (`detalhes_por_volta`), até não sobrar nada por ler.

## 5. O painel

A barra da esquerda tem quatro entradas, por ordem de uso:
**Anúncios** (a página inicial — a lista toda, triagem e acervo num
sítio só), **Em curso** (o quadro e o calendário dos "interessa"),
**Mercado** (os contratos e as renovações) e **Alertas**. Os
Indicadores não estão na barra: chegam-se pelo ponto verde/vermelho
da última verificação, em baixo à esquerda (§8).

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

**O interesse recorta as quatro abas.** Em *Alertas › Interesse*
escolhes, na árvore, os CPV que a casa trabalha; ligado, a lista passa
a mostrar só o que corresponde — nas quatro abas, sem teres de pôr
filtro nenhum. Não é um alerta: um alerta avisa-te, o interesse esconde
o resto. A lista diz sempre que está limitada, quantos ficam de fora, e
tem um **ver tudo** que o levanta para a vista em que estás. Nasce
desligado; desligado, nada muda. Os alertas, os contratos e os filtros
guardados não são tocados — o interesse é recorte de leitura da lista,
não um filtro.

A barra de filtros trabalha sobre o que já está guardado, sem apagar
nada. Podes filtrar por:

- **nome do concurso ou objecto** e, em caixa separada, **entidade
  adjudicante**. Dentro de cada caixa, várias palavras separadas por `|`
  valem como "qualquer uma destas" (`outsystems|.net|java`); entre as
  duas caixas é "e", por isso podes pedir software *da* Autoridade
  Tributária sem apanhar tudo o que diz Tributária.

  Nota: procura pelo nome por extenso, não pela sigla. O DR escreve
  "Serviços Partilhados do Ministério da Saúde", nunca "SPMS".
- **CPV**, por início do código (`72` apanha todos os serviços de TI) ou
  por palavra da descrição oficial do CPV (`software`, `manutenção`).
  Tal como nas palavras, várias opções separadas por `|` valem como
  "qualquer uma": `72|manutenção de software`.
- **plataforma electrónica**: acingov, vortal, anogov, compraspt, ou os
  que não a indicam. Serve sobretudo para isolares aquelas de que o
  radar consegue trazer as peças sozinho.
- **intervalo de datas** de publicação.
- **estado**: as mesmas quatro abas, para os filtros guardados.
- **prazo**: abertos, urgentes (a menos de N dias — a janela edita-se
  em Alertas) ou expirados. Serve para apartar o arquivo da triagem do
  dia.
- **exclusões**: "Excluir palavras…" e "Excluir CPV…" tiram ruído sem
  apertar o resto do filtro (`manutenção` sem `elevador|avac`).
- **E/OU entre palavras e CPV**: "mais restrito" exige as duas coisas,
  "mais amplo" basta uma.

Um filtro que valha a pena repetir guarda-se com nome (botão "guardar
filtro") e volta-se a ele com um clique; em **Alertas** liga-se a
qualquer filtro guardado um aviso no resumo diário, define-se o
**interesse** (os CPV que recortam a lista, ver §5), e configura-se o
e-mail e a janela do "urgente". Em **Mercado** vivem os **Contratos**
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
O botão **Anúncio completo** abre as 28 secções em bruto.

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

## 7. Quem está a trabalhar

No canto do cabeçalho escreves o teu nome. A partir daí fica registado
quem marcou interessa, quem moveu de fase e quem ficou responsável por
cada concurso — vês esse registo na ficha do anúncio, em baixo.

Na ficha podes também atribuir o concurso a uma pessoa.

Não há palavra-passe: isto corre no teu PC e é identificação, não
segurança. No dia em que isto for para um servidor partilhado, é aí que
entra o login a sério.

## 8. Indicadores

Chega-se lá pelo **ponto verde/vermelho da última verificação**, em
baixo na barra da esquerda — é a única porta, de propósito: é consulta
ocasional, não trabalho diário. Números sobre o teu próprio radar:
quantos anúncios tens, quantos entraram hoje, quantos marcaste como
interessa (e destes, quantos estão dentro da janela do "urgente" — os
mesmos N dias do filtro e da etiqueta cor de âmbar, editáveis em
Alertas), quantos ainda estão sem detalhe lido, como estão distribuídos
pelas fases do quadro, e o estado da recolha — se as capturas ainda são
válidas e que percentagem de peças se consegue por plataforma.

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
  editável em Alertas) e a vermelho se termina hoje ou já expirou.
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

## 11. Histórico de alterações

Duplo clique em `historico.bat`. Abre uma janela com todas as
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

## 12. Comandos, se precisares

O uso normal é o painel. Estes são para casos pontuais:

```bash
python radar.py --historico 730
```
Puxa 730 dias (2 anos) de anúncios de uma vez. Demora horas — é um
pedido por página, e depois um por anúncio para os detalhes.

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
python radar.py --exportar-triagem
```
Escreve o `triagem.jsonl` — a parte irrecuperável da base (a tua
triagem, fases, etiquetas, histórico, filtros, seguidas) num ficheiro
de texto que viaja no repositório do git. **Não precisas de fazer
nada**: cada verificação exporta E faz commit+push sozinha quando o
ficheiro muda (um push falhado retenta na verificação seguinte); à mão
serve só para forçar antes de um commit teu. Desliga-se com
`"triagem_no_git": false` no `config.json`.

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
Corre os testes — 580 verificações em poucos segundos, sem tocar
na rede nem na base verdadeira. Vale a pena corrê-los depois de
qualquer alteração ao `radar.py`. Se o DR mudar o formato dos
anúncios, é o teste do parser que avisa primeiro.

## 13. Ficheiros

| Ficheiro | Para que serve |
|---|---|
| `radar.py` | o programa |
| `curl_DR.txt` / `curl_detalhe.txt` | as tuas capturas, secção 3 |
| `config.json` | configuração e horários, criado no primeiro arranque |
| `radar.db` | os anúncios, a triagem e o histórico |
| `contratos.db` | o corpus de contratos do BASE (refaz-se com `--contratos`) |
| `copias/` | cópia diária do `radar.db`, sete guardadas |
| `amostras/` | a última colheita e, se houver, a resposta que correu mal |
| `documentos/` | as peças dos concursos que foste buscar |
| `AVISOS.txt` | o último resumo dos alertas, quando há |
| `instalar.bat` | instala as dependências |
| `iniciar.bat` | abre o painel |
| `agendar.bat` | cria as três tarefas agendadas |
| `verificar.bat` | o que as tarefas das 09h/17h correm |
| `desinstalar.bat` | remove tarefas e pacotes |
| `historico.bat` | abre o histórico de alterações |
| `teste_radar.py` | os testes |

## 14. Limites, para não haver surpresas

O DR publica anúncios acima de certos valores. Abaixo dos limiares
(ajustes directos, consultas prévias) **não existe anúncio nenhum** —
esses procedimentos são por convite e só se tornam públicos como
**contrato celebrado**. O radar traz esses contratos: o separador
Contratos carrega o dump semanal do IMPIC (dados.gov, sem chave e sem
sessão — a API que nunca respondeu deixou de fazer falta), com mais de
um milhão de contratos desde 2020. Não são oportunidades: quando lá
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
