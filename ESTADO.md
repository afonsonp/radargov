# Estado do projecto, para quem pegar nisto a seguir

Última actualização: 25 de agosto de 2026.

## O que isto é

Aplicação local em Python que vigia os anúncios de contratação pública
publicados no Diário da República, série II, parte L. Guarda tudo numa
base SQLite e mostra num painel web local, em `http://localhost:8765`.
Verifica sozinha às 09:00 e às 17:00, por tarefas do Windows.

Substitui a Armilar, produto da Vortal que a empresa paga a 200 euros
por mês, com má experiência de uso e falhas de ingestão. Corre no PC do
Afonso e não depende de nada da empresa.

Princípio de desenho, decidido depois de uma primeira versão que
filtrava por pontuação: **não se filtra nada à entrada**. Entra tudo o
que a parte L publicar, ordenado da data mais recente para a mais
antiga, e a triagem faz-se no painel, por CPV, palavras, datas e estado.

## Como está a correr

Funciona. A base tem ~5100 anúncios, **todos com detalhe lido**, a
cobrir os últimos 60 dias.

Chegou a ter 65 819 (dois anos de histórico) e o Afonso mandou apagar o
que fosse mais antigo que 60 dias — decisão informada, com os números à
frente: saíam 92% das linhas, mas nenhum anúncio triado, nenhum
documento e nenhum histórico, porque nada disso existia fora da janela.
Ficou sem cópia, por escolha dele. Para voltar a ter histórico é
`python radar.py --historico 730`, e conta horas.

A janela é a mesma que a rotina usa (`detalhe_dias`, 60), e a razão é a
mesma: entre a publicação e o prazo vão ~18 dias em média, por isso mais
atrás que isso já fechou. O que ficar mais velho volta a acumular — a
limpeza não é automática.

## A ficha do anúncio e as peças do procedimento

Mudança de rumo pedida pelo Afonso: clicar num anúncio deixou de abrir
o portal do DR e passa a abrir **`/anuncio/<ref>`, dentro da app**, com
o anúncio inteiro e os documentos do procedimento.

**O texto completo já vinha e era deitado fora.** A resposta de detalhe
traz `data.DetalheConteudo.Texto` com o anúncio todo — 28 secções
numeradas, com linhas `Chave: Valor`. O código antigo corria 4 regexes
sobre ele e descartava o resto. Agora guarda-se em `anuncios.texto`.
Consequência prática: **reanalisar deixou de precisar de rede**. O
comando `python radar.py --reler` chama `reparsear()`, que recalcula os
campos a partir do texto guardado — 5125 anúncios em ~6 segundos, zero
pedidos ao portal, em vez das ~18 horas que demorava a voltar a pedir
tudo. **É isto que se corre depois de mexer em `campos_do_detalhe()`**;
foi assim que a ComprasPT foi reconhecida em 39 anúncios já guardados.

Esteve algum tempo como botão "Reler detalhes" no topo do painel, ao
lado do "Verificar agora". Saiu de lá por decisão do Afonso: é
manutenção, não uso diário, e os dois lado a lado com o mesmo peso
sugeriam que eram alternativas equivalentes — quando um se usa todos os
dias e o outro só depois de o código mudar.

Saiu a heurística `maior_texto()` ("escolher a maior string da
resposta"), substituída pelos caminhos exactos, agora conhecidos:
`data.DetalheConteudo.Texto` e `data.DetalheConteudo.URL_PDF`.

`seccoes_do_texto()` parte o anúncio em secções e pares chave/valor;
`campos_do_detalhe()` passou a ler desses pares em vez de procurar
etiquetas soltas no texto todo. Validado contra 12 anúncios reais:
**12/12 iguais** ao parser antigo, mais o link das peças que o antigo
não capturava. Aceita chaves repetidas, porque procedimentos com lotes
repetem as mesmas chaves.

### Quando é que o detalhe é lido

O detalhe é o passo caro: **um pedido por anúncio**, com pausa de um
segundo. Para os 65 mil da base isso são ~18 horas. Fazia-se em massa;
passou a ser sob procura, como os documentos:

- **Ao abrir a ficha**, se o anúncio ainda não tiver texto, é lido na
  hora (`ler_detalhe_de`). Medido: **0,6 s** para um anúncio de 2024.
  Funciona para qualquer anúncio, por mais antigo que seja.
- **Em rotina**, `ler_detalhes(dias=...)` só trata dos publicados na
  janela `detalhe_dias` (60 por omissão, no `config.json`; 0 = tudo).

Porquê 60 dias, e não tudo: **entre a publicação e o prazo vão ~18 dias
em média** (medido sobre a base). Um anúncio com mais de dois meses já
fechou — não dá para concorrer, e o CPV dele só interessa como
histórico. Isto reduz o trabalho de rotina de 65 mil para ~4400 de uma
vez (~75 min), e depois ~80 por dia, que é ~80 segundos.

**A razão de não ser tudo sob procura:** o CPV **não vem na pesquisa**,
só no detalhe — verificado, o `_source` da pesquisa tem `numero`,
`emissor`, `sumario`, `dataPublicacao`, `dbId`, `tipo` e mais uns
quantos, e nenhum campo de CPV, vocabulário ou classificação. Se o
detalhe fosse lido apenas ao abrir, o filtro de CPV e a árvore ficavam
vazios para tudo o que ainda não tivesse sido aberto — e era preciso o
CPV justamente para decidir o que abrir. Daí a janela: cobre tudo o que
é concorrível, sem pagar as 18 horas.

### Onde estão as peças, e o que se consegue de cada plataforma

A secção 15 do anúncio tem sempre *"Link para acesso às peças do
concurso (URL)"* (18/18 numa amostra). O que esse link dá depende da
plataforma — e **nenhum destes caminhos precisa de browser, sessão ou
credenciais**:

| Plataforma | % da base | Como |
|---|---|---|
| acingov | ~48% | GET no link devolve um ZIP com tudo lá dentro |
| vortal | ~42% | três saltos de API pública, ver abaixo |
| anogov | ~8% | a página lista os documentos; cada um sai de um `decryptservlet` |
| compraspt | ~1% | igual à anogov — é a mesma aplicação |

**ComprasPT esteve por reconhecer durante algum tempo** e caía num balde
chamado "(nenhuma)" que o ecrã de indicadores pintava de vermelho com a
legenda "sem acesso" — duplamente errado, porque é uma plataforma real,
nomeada no anúncio, e as peças até se obtêm. Faltava simplesmente na
lista `PLATAFORMAS`. Repara na ordem dessa constante: `compraspt` tem de
vir antes de `compraspublicas`, senão um endereço `compraspt.com` nunca
chega a ser testado contra o primeiro.

A ComprasPT e a anogov são a **mesma aplicação JSF** do mesmo
fornecedor, e um só obtentor serve as duas (`_pecas_jsf`): a página
responde a um GET com o código de acesso, lista os documentos em HTML,
e cada ficheiro sai de um `decryptservlet` no mesmo servidor. Sem
sessão iniciada.

`PLATAFORMAS_COM_PECAS` diz quais é que dão as peças; é o que decide a
cor da etiqueta na lista e o "sem acesso" nos indicadores. Ao acrescentar
uma plataforma nova, acrescenta-a nos dois sítios.

O `(nenhuma)` sobrante (~1%) são anúncios em que o próprio DR não indica
plataforma. Aparece agora com legenda neutra, não como avaria.

**A cadeia da vortal**, que custou a encontrar porque o link abre uma
SPA de 686 bytes que não diz nada sem JavaScript:

1. do link tira-se o último segmento, o identificador cifrado;
2. `GET /public/api/PublicTenderDocuments/GetPublicTenderInformation
   ?uniqueIdentifierEncrypted=<id>&languageCode=pt` → devolve
   `contractNoticeUrl`, de onde se extrai um `PT1.NTC.<numero>`;
3. `GET /public/api/ContractNoticeDetail/GetContractNoticeDocuments
   ?contractNoticeUId=PT1.NTC.<numero>` → JSON com `name` e
   `downloadUrl` de cada documento;
4. cada `downloadUrl` descarrega o ficheiro directamente.

O nome do endpoint do passo 3 foi encontrado a procurar
`ContractNoticeDetail` no bundle `index-*.js` da vortal (7,5 MB) — não
aparece no tráfego que o browser faz ao carregar a página das peças.
Atenção ao nome do parâmetro: é `contractNoticeUId`;
`contractNoticeUniqueIdentifier` devolve **400**, embora seja esse o
nome usado noutro endpoint da mesma API.

**Esteve escrito aqui que "a anogov não dá".** Era falso, e a causa
merece ficar registada porque se repetiu: eu tinha imprimido os links
truncados a 78 caracteres e testei o código de acesso **cortado**. Os
códigos da anogov têm ~50 caracteres; um código truncado faz a página
responder "não foi encontrado nenhum documento para o código de acesso
introduzido" — que se lê como "esta plataforma não dá acesso".

Com o código inteiro, a anogov devolve a lista completa: Programa do
Procedimento, Cláusulas Gerais e Especiais, anexos técnicos.

**O mesmo erro tinha acontecido antes com a vortal**, também por
truncar a URL ao imprimi-la. Duas vezes o mesmo engano custou ~53% de
cobertura declarada como impossível. A lição: nunca testar um endereço
que passou por um `[:n]` ou por um `print` truncado.

**Ficheiros grandes.** A Infraestruturas de Portugal publica anexos
técnicos enormes — um anúncio real trouxe 551 MB num único ZIP, mais
69 MB noutro, e o código juntava tudo em memória antes de decidir.
Há agora `MAX_FICHEIRO` (60 MB) e `_descarregar()`, que lê por pedaços
e desiste a meio; o que fica de fora é nomeado no aviso, e o anúncio
fica com `docs_estado='parcial'`.

O **PDF oficial do anúncio** (`URL_PDF`) descarrega para 100% dos
casos, sem autenticação, e é sempre trazido.

### Onde ficam os ficheiros

Em `documentos/<ref>/`, no disco — **não** dentro do SQLite. Blobs na
base fariam-na crescer para dezenas de GB e tornavam lento tudo o resto;
em ficheiro, o `radar.db` fica pequeno e a pasta migra bem para um
servidor ou para armazenamento de objectos, se isto sair deste PC (que
é uma intenção declarada, para partilhar trabalho com outra pessoa).
A tabela `documentos` guarda só o índice (ref, nome, tamanho, origem).

`servir_documento()` confirma com `os.path.abspath` que o caminho final
fica dentro da pasta do anúncio, para um nome de ficheiro vindo de um
ZIP não conseguir escrever nem ler fora dela. Testado: `..%2F..%2F` dá
404.

**Quando é que os documentos vêm:** ao carregar em "Trazer peças" na
ficha, e automaticamente (em fundo, para o clique não esperar) ao
marcar **interessa**. Não se descarrega tudo: 65 mil anúncios a ~3 MB
seriam ~200 GB e semanas de download. Assim tens sempre as peças
daquilo em que realmente trabalhas.

## O que descobrimos sobre o portal, para não se repetir o trabalho

O DR não tem API pública, nem RSS. Todos os endereços do género
`/dr/rss`, `/dr/feeds`, `/dr/ultimos` devolvem a mesma casca HTML de
2346 bytes. Ter conta no DR não ajuda: a pesquisa corre sempre como
`lid=Anonymous`.

O portal é uma aplicação OutSystems. O que funciona é chamar directamente
os `screenservices` que o browser chama, com os cabeçalhos de uma
captura feita no DevTools. Dois pedidos interessam:

**Pesquisa.** `POST /dr/screenservices/dr/Pesquisas/PesquisaResultado/DataActionGetPesquisas`

- Aceita pesquisa com termo vazio, o que devolve a parte L inteira por
  data. Confirmado: 205 anúncios em três dias.
- A resposta **não** traz o JSON dos anúncios aberto. Traz-os dentro de
  `data.Resultado`, que é **texto** contendo o JSON do Elasticsearch,
  com os campos em minúsculas: `hits.hits[]._source.numero`, `emissor`,
  `sumario`, `dataPublicacao`, `dbId`, `tipo`. Foi o que custou mais a
  descobrir. O código trata disto abrindo qualquer string que pareça JSON.
- O corpo do pedido tem 86 variáveis de ecrã. Não vale a pena construí-lo
  à mão: tentou-se, e o servidor responde com a casca HTML em vez de
  JSON. Usa-se o corpo da captura, esvaziando os resultados que traz
  colados e substituindo datas, termo, página e ordenação.

**Detalhe.** `POST /dr/screenservices/dr/Legislacao_Conteudos/Conteudo_Detalhe/DataActionGetAllConteudoDetalheData`

- Identifica o anúncio por `screenData.variables.Key`, no formato
  `21171-2026-1160416962`, que é `numero-com-traço` mais `dbId`. É a
  mesma chave do endereço público do anúncio, que o radar já constrói.
- `screenData.variables.Tipo` vale `"anuncio-procedimento"`.
- A página pública do anúncio **não** serve para raspar: um GET devolve
  só a casca da aplicação, 2346 bytes. O conteúdo vem por esta chamada.

**Diagnóstico de erros.** Se o pedido chegar ao serviço mas o corpo
estiver mal formado, a resposta é 400 com JSON do OutSystems, do género
`Failed to parse JSON request content`. Se o token não for aceite, a
resposta é 200 com a casca HTML. Distinguir os dois casos poupa tempo.

## As duas capturas

`curl_DR.txt` e `curl_detalhe.txt`, na pasta. São `Copy as cURL` do
DevTools, sobre os dois pedidos acima. O radar aproveita delas os
cabeçalhos, o `x-csrftoken` e a forma do corpo.

Usar sempre **Copy as cURL (bash)**. O formato `cmd` escapa cada
caractere com `^` e **come os acentos**: o filtro `parte` chegava ao
servidor como `L - Contratos p blicos` e o DR devolvia zero sem se
queixar. Há código a repor esse valor (`VALORES_FIXOS`), mas é remendo.

O token vem da sessão do browser e há-de expirar. Quando isso acontecer,
o painel avisa em vez de mostrar lista vazia. A recaptura leva dois
minutos. Não há forma de evitar isto sem API.

## O problema do CPV, resolvido — e um diagnóstico errado que aqui esteve

Estava documentado como "1 em 80, problema em aberto". A causa real era
banal: **os dados na base estavam velhos**. O código de extracção já
estava correcto; faltava mandar reler os anúncios já guardados. Feito
isso, 498 de 500 ficaram com CPV.

**Aviso a quem ler este ficheiro:** durante um tempo esteve aqui escrito
que a causa era o DR mandar caracteres corrompidos (U+FFFD), do género
`Vocabul�rio Principal`. **Isso é falso** e foi verificado: o texto do
DR tem **zero** U+FFFD, é UTF-8 impecável (`\xc3\x87` = "Ç", `\xe1` =
"á"), e `simplifica()` converte `"Vocabulário"` em `"vocabulario"` sem
problema. Os `�` que se viam eram a **consola do Windows** (cp1252) a
não conseguir imprimir acentos — um artefacto do terminal, nunca dos
dados. Se voltares a ver `�` ao correr Python no terminal, é isto;
escreve para ficheiro com `encoding="utf-8"` e confirma antes de tirar
conclusões sobre a fonte.

## CPV por código ou por palavra

O campo de CPV aceita duas coisas, à mistura e separadas por `|`, tal
como a caixa de palavras:

- **código**: `72`, `72267100-0`.
- **palavra da descrição oficial do CPV**: `software`, `manutenção`.

Para código, só os primeiros 8 dígitos contam (o dígito de controlo a
seguir ao traço é ignorado — havia um bug aqui: `72267100-0` virava
`722671000`, nove dígitos sem traço, que nunca batia certo com o valor
guardado, que mantém o traço; ficava sempre a zero, sem se notar que
era um bug e não "não há dados"). Os zeros à direita desses 8 dígitos
são tirados antes de se usar como prefixo — no CPV, zero à direita é
sempre estrutura, nunca faz parte do número em si — por isso `72000000`
vira prefixo `72` e apanha tudo o que está por baixo da divisão
(`72267100` incluído). É esta linha que faz a árvore, a seguir,
funcionar como selecção de grupo sem precisar de nenhuma lógica extra
no SQL.

Isto é possível porque a base tem uma tabela `cpv_dict` (código de 8
dígitos, descrição, versão sem acentos para pesquisa), importada de um
ficheiro `cpv-2024.json` (formato `[{"codigo":"...","descricao":"..."}]`,
9454 códigos) que o Afonso arranjou. A importação corre-se com
`python radar.py --importar-cpv caminho\para\ficheiro.json` e é
para se correr uma vez; depois disso o `radar.db` já não depende do
ficheiro. Repete-se só se aparecer uma versão mais recente do
vocabulário CPV.

`condicoes()` traduz um termo não-numérico numa lista de códigos de 8
dígitos via `cpv_por_termo()` (LIKE sobre a descrição simplificada), e
constrói o OR de prefixos como já fazia para código directo. Um termo
que não bate com nada devolve lista vazia, e a condição fica `1=0` —
mostra "nada corresponde", em vez de, por engano, mostrar tudo.

Chegaram a existir atalhos fixos no `config.json` — primeiro só
`atalhos_cpv`, depois o Afonso pediu para tirar também os `atalhos` de
palavra (TI, Bolsa de horas, Meus clientes) que já vinham do início do
projecto. Motivo: quer escolher tudo na hora, a partir da app, não
editar um ficheiro de configuração com listas fixas. Os dois já não
existem em lado nenhum — nem em `CONFIG_INICIAL`, nem no `config.json`,
nem na `PAGINA`. A caixa de palavras (`q`) continua livre, escreve-se
o que se quiser directamente; para CPV há a árvore, a seguir.

A caixa de texto do CPV (`#filtro-cpv`) tornou-se um `<input
type="hidden">` — deixou de estar visível, só a árvore a preenche. Por
troca, quando há um filtro de CPV activo aparece uma linha por cima da
árvore, "Filtro CPV activo: X, tirar", com um link que o remove sem
mexer nos outros filtros (`estado`, datas, palavras).

## Árvore de CPV no painel

Abaixo da caixa de filtros, um `<details>` "Escolher CPV na árvore"
que, ao abrir, pede `/cpv.json` (rota nova) e constrói a árvore no
browser em JavaScript simples, sem framework:

- `cpv.json` devolve os 9454 códigos do `cpv_dict` mais a contagem
  própria de cada um (quantos anúncios guardados têm exactamente aquele
  código de 8 dígitos, via `SELECT cpv FROM anuncios`, partido por
  vírgula porque um anúncio pode ter mais que um CPV).
- No browser, `nivelSignificativo()` conta os zeros à direita do código
  para saber a que nível da hierarquia pertence (72000000 tem 6 zeros
  = divisão; 72212761 tem 0 = código final). `arvoreConstruir()` liga
  cada código ao pai mais próximo que exista no dicionário com menos
  dígitos significativos — funciona porque o CPV inclui como entradas
  próprias todos os níveis intermédios, não só as folhas.
- As contagens mostradas são acumuladas (a de 72000000 soma a dela mais
  a de todos os descendentes), calculadas com uma passagem bottom-up
  depois de montada a árvore.
- Caixa de busca dentro da árvore filtra por texto (código ou
  descrição), abre os ramos onde bate certo, esconde o resto.
- Marcar a caixa de um grupo marca visualmente tudo o que está por
  baixo (`arvoreDescendentes()`, percorre `ARV_FILHOS`) — só para se
  ver na hora o que ficou incluído. O que realmente vai para o filtro
  é só o código do próprio grupo (`ARV_SEL`, guarda só o que foi
  clicado directamente); os zeros à direita tratam do resto no
  servidor, como descrito acima. Marcar `.checked` por script não
  dispara `change`, por isso os descendentes marcados por cascata não
  entram em `ARV_SEL` por engano.
- "Aplicar" escreve `Array.from(ARV_SEL).join('|')` no campo escondido
  e submete o formulário — reaproveita a `condicoes()` que já existia,
  nenhuma rota nova para aplicar o filtro.

Sem framework, sem build step: tudo dentro do `<script>` no fim do
`PAGINA`. Testado ao vivo (browser tool, mais chamadas directas ao JS
quando o click do automatismo não acertava no botão certo depois da
árvore mudar o layout da página — 9454 nós é bastante DOM, o
`read_page` do próprio browser tool chegou a fazer timeout em cima
disto): árvore constrói, busca filtra, cascata marca 252 caixas ao
marcar a divisão 72, aplicar submete `/?cpv=72000000` e mostra 308
resultados dessa divisão inteira.

## Mensagem de estado sem quantidades

O Afonso pediu para a barra de baixo do painel ("ok, N anuncios lidos e
M novos...") deixar de mostrar quantidades — ficava confuso ver "500
anuncios lidos" depois de a base já ter dezenas de milhares. `recolher()`
devolve só `"ok"` no sucesso; `verificar()` já não lhe apend a
`", N detalhes lidos"`. Erros e avisos (token expirado, sem ligação)
continuam com texto completo, esses importam. Quem quiser números tem
os contadores "Por ver / Interessa / Descartados / Todos" na barra de
cima, que já eram ao vivo.

## A aparência, e o esqueleto partilhado

A interface veio de um desenho feito pelo Afonso no Claude Design
("Alertas de Concursos Públicos",
`Concursos.dc.html`), importado com a ferramenta DesignSync. O desenho
é um protótipo com dados fictícios; o que se implementou foi a
linguagem visual, ligada aos dados reais.

**O que mudou na estrutura, e é o mais importante:** havia quatro
documentos HTML completos (`PAGINA`, `QUADRO_PAGINA`, `FICHA_PAGINA`,
`CALENDARIO_PAGINA`), cada um com a sua folha de estilo, que já tinham
divergido entre si. Agora há **um** `CSS` e **um** `BASE`, e cada ecrã
só produz o seu conteúdo e chama `envolver(...)`. A barra lateral, o
cabeçalho, o selector de pessoa e as fontes existem uma vez só.

**Pormenor que evita muita dor:** o `CSS` vive numa constante própria e
entra por **substituição** (`BASE % {"css": CSS, ...}`), não escrito no
texto do molde. Como o `%`-formatting só interpreta a *string de
formato* e não os valores substituídos, as percentagens do CSS
(`50%`, `100vh`, `flex:1 1 30%`, `width:46%`) **não precisam de ser
escapadas como `%%`**. Se um dia alguém colar CSS directamente dentro
do `BASE`, tem de dobrar todos os `%` — não o faças, põe-no no `CSS`.

Tipografia: Archivo e JetBrains Mono, do Google Fonts, com `system-ui`
e `ui-monospace` como reserva — se a máquina estiver sem rede a
aplicação continua legível, só muda de letra.

**Armadilha encontrada:** entidades HTML (`&mdash;`) dentro de uma
string que depois passa por `html.escape()` saem escritas tal e qual,
porque o `&` é escapado para `&amp;`. Nos títulos das secções da ficha
usa-se o carácter literal `—`, que atravessa o `escape()` intacto. A
regra: a entidade fica **fora** do `html.escape()`, ou usa-se o
carácter.

Ecrã novo, **`/indicadores`**, que vinha no desenho marcado como
proposta. Tudo o que mostra sai de SQL sobre o `radar.db`: contagens
por estado, prazos a menos de 7 dias, distribuição por fase do quadro,
percentagem de peças obtidas por plataforma, tamanho e modo da base.
Sem serviços externos.

A contagem da lista distingue agora o que o filtro apanhou do que está
guardado ("a mostrar 500 dos 598 que correspondem · 65 869 na base").
Antes dizia "500 de 65 869 guardados" mesmo com filtro activo, o que
fazia um filtro que funcionava parecer avariado.

## Lista principal em cartões

Pedido do Afonso ("como melhoramos o UX/UI?"), começando pela lista
principal a seu pedido. A `<table>` densa virou uma lista de cartões
(`.item`, uma `<div>` por anúncio, `linha()` continua a gerar cada um —
nome mantido para não mexer no resto). Cada cartão: dia/mês em
destaque à esquerda, título e entidade, etiquetas (CPV, tipo, dias até
ao prazo a verde ou "prazo expirado" a vermelho, e o próprio estado
quando não é "novo"), preço e os botões de acção à direita.

`dias_restantes()`, que já existia para o quadro e o calendário, passou
a ser usada aqui também — antes a lista principal nem mostrava contagem
de prazo, só a data em bruto.

Aproveitou-se para dar uma passagem geral: sombra suave e cantos
arredondados em `.filtros`, `.aviso` e nos cartões, consistente com o
que já existia no quadro. Sem framework CSS, sem novas dependências —
só CSS a mais no mesmo `<style>`.

Verificado por computed style no browser (a screenshot não estava a
funcionar nesta sessão, o painel do browser não compunha frames):
fundo branco, `border-radius:6px`, sombra `rgba(0,0,0,.06) 0 1px 2px`,
título a azul `#1f4e79` a negrito, etiqueta de prazo com fundo verde
claro — confere com o CSS escrito.

## Quadro (kanban)

Pedido do Afonso depois de mostrar o SpotGov (concorrente comercial,
200€/mês) como referência: queria o género do "Saved Tenders" de lá —
colunas configuráveis, cartões arrastáveis, etiquetas, contagem de
prazo. Decidiu-se conscientemente **não** replicar a pesquisa "Search
with AI" do SpotGov, para o radar continuar 100% local sem depender de
nenhum serviço externo.

**As fases de origem** vêm do desenho: *Por analisar, A preparar
proposta, Em revisão, Submetido, Resultado*. Estão em `FASES_INICIAIS`
e são semeadas por `semear_fases()`, chamada de `iniciar_db()`.

Essa função tem de ser cuidadosa, porque corre a cada arranque: só
actua se o quadro estiver **vazio**, ou se tiver **apenas** a coluna
`Guardados` que as primeiras versões criavam sozinha — nesse caso
reaproveita-lhe o `id` e renomeia-a para a primeira fase, para não
desgarrar os cartões que já lhe estivessem atribuídos. Se encontrar
qualquer outra coisa, não toca em nada: as fases são do utilizador,
que as renomeia, acrescenta e apaga no próprio quadro. Verificado nos
três casos (base nova, base só com `Guardados`, base já personalizada).

Tabelas novas: `fases` (id, nome, ordem — as colunas do quadro),
`etiquetas` (id, nome, cor), `anuncio_etiquetas` (ref, etiqueta_id,
tabela de ligação). Coluna nova em `anuncios`: `fase_id`, adicionada
por `ALTER TABLE` em `iniciar_db()` se ainda não existir (migração
idempotente, corre sempre, não faz nada se a coluna já lá estiver).

Marcar um anúncio como `interessa` (no botão da lista principal)
atribui-lhe a primeira fase automaticamente
(`fase_id=COALESCE(fase_id, primeira_fase())`, em `mudar_estado()`) —
só entra no quadro quem já está marcado como interessante, o quadro não
é uma vista diferente da lista toda.

Rota `/quadro` monta o board a partir de `anuncios WHERE estado='interessa'`,
agrupado por `fase_id`. `/quadro/mover` (POST, JSON) é a única rota
chamada por `fetch`, para o arrastar-largar não recarregar a página; o
resto (nova fase, renomear, apagar, etiquetas) é formulário + redirect,
ao estilo do resto da app — mais simples e mais robusto que gerir tudo
em JS.

Arrastar e largar é `dragstart`/`dragover`/`drop` nativos do HTML5, sem
biblioteca. Testado com eventos disparados por JavaScript em vez de
arrastar a sério com o rato (o browser tool desta sessão não simula
arrasto físico de forma fiável) — dataTransfer mockado à mão com
`setData`/`getData`, confirmado que persiste (`fase_id` mudou na base)
depois do "drop".

Apagar uma fase só é permitido se sobrar mais que uma (`fase_apagar()`);
os cartões que lá estavam vão para a fase seguinte por `ordem`. Etiquetas
são globais (por nome, `COLLATE NOCASE` para não duplicar "Urgente" e
"urgente"), com cor atribuída por rotação sobre `CORES_ETIQUETA` — sem
selector de cor, para manter simples.

Armadilha encontrada a testar: `curl -d "nome=Em revisão"` pelo Git Bash
do Windows não manda UTF-8 correcto (o `ã` fica em bytes que o Flask não
consegue interpretar, e a fase não chega a ser criada, sem erro visível).
`requests.post` do Python não tem este problema. Não é bug da app, é do
terminal — mas vale a nota para não se perder tempo outra vez a pensar
que a rota está avariada.

## Correcções vindas de uma revisão ao código

Uma passagem de revisão encontrou 15 problemas, todos corrigidos. Os que
vale a pena conhecer, porque voltariam a acontecer:

**O filtro de CPV por divisão apanhava dez vezes de mais.** Tirar os
zeros à direita de `30000000` deixa `"3"` — e `LIKE '3%'` apanha as
divisões 31, 33, 34, 35, 37, 38 e 39. Medido: 4592 anúncios em vez de
440. Agora o prefixo nunca desce abaixo de dois dígitos, que é a largura
da divisão no CPV. Escapou porque as divisões do Afonso (48 e 72) têm um
segundo dígito diferente de zero e por isso funcionavam.

**O sucesso era decidido por `"ok" in mensagem`.** A mensagem de falha de
rede é `"sem ligação ao DR: Connection broken..."` — e *br**ok**en*
contém "ok". Uma falha de rede passava por sucesso: o painel pintava o
ponto de verde e o programa seguia para ler detalhes. `recolher()`
devolve agora `(correu_bem, mensagem, novos)` e o estado fica em
`ultima_ok`. **Nunca decidir estado por substring de texto para humanos.**

**Tudo o que altera dados era um link GET** — incluindo o então `/reler`,
que reprocessa a base inteira. Um prefetch do browser ou qualquer coisa
que siga links disparava-os. Há agora `accao()`, que desenha um `<form
method="post">` com aspecto de botão, e as rotas exigem POST. (O
`/reler` acabou por sair do painel de vez — passou a `--reler`.)

**O `/quadro/mover` aceitava qualquer `fase_id`.** Um id inexistente
punha o cartão numa coluna que não é desenhada: desaparecia do quadro
sem voltar à lista, porque continuava `interessa`. Agora valida a fase e
o anúncio, devolve 404, e o JavaScript recarrega quando o servidor
recusa — antes o ecrã ficava a mostrar uma mudança que não foi gravada.

**Sucesso parcial nos documentos parecia sucesso.** O PDF do anúncio vem
sempre; se as peças falhassem, `docs_estado` ficava `ok` e o aviso era
deitado fora. Há agora o estado `parcial`, dito na ficha.

**O `config.json` estragado era substituído em silêncio** pelos valores
de origem — e `ler_config()` corre a cada página, por isso perdia-se na
página seguinte. Agora guarda-se `config.json.estragado` primeiro.

Outros: `LIKE` passou a escapar `%` e `_` (procurar "50%" devolvia tudo
o que tem "50"); o escape usa `!` e não a barra invertida, que teria de
sobreviver ao literal de Python e ao de SQL ao mesmo tempo. As descargas
de documentos passaram a uma fila com um trabalhador, em vez de uma
thread por clique. O `relogio()` grava o erro em `ultimo_erro_relogio`
em vez de o engolir. `guardar()` usa `INSERT OR IGNORE`. A lista pede
uma linha a mais em vez de correr a consulta filtrada outra vez só para
contar. `descricoes_cpv()` faz uma consulta e não uma por código.
`cpv.json` é guardado em memória, invalidado pela contagem de detalhes
lidos.

## Contagem de dias, e os dias da semana no calendário

`conta_dias()` e `etiqueta_prazo()` tratam a contagem toda num sítio só,
porque estava errada em três pontos ao mesmo tempo:

- um prazo que acaba **hoje** dava `0 dias` (agora "termina hoje", a
  vermelho, porque é hoje que se perde);
- o dia seguinte dava `1 dias`, sem concordância (agora "amanhã");
- a ficha dizia "faltam 0 dias" pela mesma razão.

`dias_restantes()` continua a devolver o número cru; quem escreve texto
passa por `conta_dias()`. Se acrescentares outro sítio que mostre
prazos, usa a mesma função em vez de formatar `%d dias` à mão.

O **calendário ganhou os dias da semana**. Sem eles a grade era uma
tira de 45 números onde não se distinguia um sábado de uma terça, e um
prazo ao fim-de-semana muda o que se faz na sexta. Agora cada coluna
traz `seg/ter/qua/...`, os fins-de-semana ficam sombreados
(`.cel-dia.fds`) e o primeiro dia de cada mês leva uma linha mais
grossa (`.mes-novo`). As iniciais soltas não servem em português:
segunda/sexta/sábado e quarta/quinta repetem-se, daí as abreviaturas
de três letras.

Verificado contra as datas reais: as 45 células batem certo com o dia
da semana e o dia do mês, e as pílulas caem exactamente na coluna do
respectivo prazo (medido em pixels contra o cabeçalho, não só no HTML).

## Calendário

Vista nova, só de leitura, rota `/calendario`. Uma grade CSS
(`grid-template-columns:260px repeat(45,74px)`, uma linha por
`<div class='linha-grade'>`) com uma coluna fixa à esquerda (título e
entidade, `position:sticky;left:0`) e 45 colunas de dias a partir de
hoje. Cada anúncio interessado com prazo fica numa linha, com uma
pílula na coluna do dia certo, mostrando o nome da fase actual no
quadro. Testado ao vivo: o prazo `2026-09-05` caiu exactamente na
coluna com esse cabeçalho.

Decisão: quem tem prazo fora da janela de 45 dias (já passado, ou muito
à frente) não entra na grade — só conta numa nota de texto por baixo.
A alternativa (mostrar a linha inteira vazia, sem pílula visível) só
ocupava espaço sem dizer nada.

Não há paginação nem scroll infinito para trás/à frente no tempo — se
um dia isso fizer falta (portefólio com muitos prazos a mais de 45 dias),
é só mudar `DIAS_CALENDARIO`.

## Tarefas agendadas

Criadas nesta sessão via `schtasks`, equivalente ao que o `agendar.bat`
faz (o próprio `.bat` não se corre bem sem consola interactiva, por
causa do `pause` no fim): "Radar DR 09h" e "Radar DR 17h", diárias,
a chamar `verificar.bat`. Confirmado com `schtasks /Query`.

## Painel a correr

Deixado a correr em fundo (`python radar.py`, sem `--uma-vez`) nesta
sessão, depois de tudo testado — porta 8765, um único processo (o
problema do duplo-bind do Werkzeug, descrito mais abaixo, não voltou a
acontecer desta vez).

## Pessoas, e o caminho para isto ser partilhado

O Afonso perguntou como levar isto para a cloud, para trabalhar com
mais alguém. Decisão tomada: **fica local por agora**, mas com o
terreno preparado.

**Feito já, porque é risco presente e não futuro:**

- **`journal_mode=WAL`** no `liga()`, mais `busy_timeout=30000`. Havia
  (e há, enquanto a recolha corre) dois processos a escrever na mesma
  base — o painel e a recolha em fundo. Com o modo `delete` que estava,
  isso dá `database is locked` mais cedo ou mais tarde. WAL deixa ler
  enquanto outro escreve. A definição é persistente na base, mas repete-se
  na ligação porque é barato e cobre bases novas.
- **Identidade sem autenticação.** Tabela `pessoas`, tabela `historico`
  (ref, quem, acção, detalhe, quando) e `anuncios.responsavel`. Quem
  está a usar a app diz o nome no cabeçalho, fica num cookie de um ano,
  e passa a ser gravado em cada mudança de estado, de fase e de
  responsável. **Não há palavra-passe de propósito**: hoje isto corre
  no PC de uma pessoa, e um ecrã de login seria atrito puro. O modelo de
  dados é que fica pronto — histórico não se inventa depois.

**O que falta mesmo para pôr isto num servidor partilhado**, por ordem:

1. **As capturas são o verdadeiro obstáculo, não o alojamento.** O
   `curl_DR.txt` e o `curl_detalhe.txt` levam o token da sessão do
   browser e expiram. Local, refaz-se em dois minutos. Num servidor,
   alguém tem de refazer a captura no browser **e enviá-la para lá** —
   é preciso um ecrã para colar a captura, em vez de trocar ficheiros
   na pasta. Isto não desaparece com a cloud; é o preço de o DR não ter
   API pública.
2. **Servidor a sério** (waitress no Windows, gunicorn no Linux). O
   `app.run()` é o servidor de desenvolvimento do Flask e ele próprio
   avisa que não serve para produção.
3. **Autenticação**, porque na internet pública qualquer um apagaria
   fases e mudaria estados. O sítio para a pôr é o bloco "pessoas".
4. **Separar o agendador do processo web.** O `relogio()` corre numa
   thread dentro da app; com vários trabalhadores passavam a existir
   verificações duplicadas. Vai para um processo próprio (ou uma tarefa
   do sistema, como já existe no Windows).
5. **Disco persistente** para `documentos/`. Em plataformas de sistema
   de ficheiros efémero (Cloud Run, Heroku) os ficheiros desaparecem a
   cada arranque.

Para 2-3 pessoas **SQLite com WAL chega bem** — não é preciso Postgres,
e trocar de base de dados agora seria complicar sem ganho. Dimensões
medidas: `radar.db` a 32 MB, projectado ~400 MB com todo o texto;
`documentos/` cresce com o uso.

Alojamento recomendado quando for a altura: um VPS pequeno (Hetzner,
DigitalOcean, ~5-10€/mês), que dá disco persistente e controlo, em vez
de plataformas geridas que complicam o armazenamento dos documentos.

## Histórico e paginação

Dois limites artificiais, ambos hoje corrigidos:

- `dias_catchup` (15 dias) é a janela da verificação de **rotina**
  (09h/17h) — continua pequena de propósito, não vale a pena pedir mais
  duas vezes por dia. Para trazer mais história de uma vez, sem alterar
  esse valor, há `python radar.py --historico N` (N em dias, 730 por
  omissão), que faz uma chamada a `recolher()` isolada com um `cfg`
  modificado só na memória.
- `paginas` estava a 20 (=500 resultados a 25/página) e cortava a meio
  de qualquer pesquisa que tivesse mais que isso — foi o que aconteceu
  com os 500. O ciclo em `recolher()` já parava sozinho quando o portal
  devolvia menos que uma página cheia (fim real dos resultados); o `20`
  não era esse sinal, era um tecto que se atingia primeiro. Subido para
  5000, que na prática nunca se atinge — fica só como rede de segurança
  contra um ciclo infinito se o portal se comportar mal.

Consequência a ter em conta: com uma janela grande, `recolher()` só
grava no fim (`guardar(colhidos)` corre uma vez, depois do `for` todo).
Não há sinal de progresso a meio — só o log e a base de dados depois de
terminar. Para 2 anos, a listagem sozinha leva uns 20-40 minutos
(segundo a estimativa; o portal ronda as 60-70 publicações por dia na
parte L, e há um segundo de pausa entre páginas). Os detalhes de cada
anúncio novo (CPV, prazo, preço) são um pedido à parte, também com um
segundo de pausa, e só correm 40 de cada vez por verificação
(`detalhes_por_volta`) — para um backlog grande, ler tudo pode levar
várias voltas ou, se se forçar em ciclo como se fez na correcção do CPV,
horas seguidas. Nessa altura vale a pena confirmar que o token de
`curl_detalhe.txt` não expira a meio (ver secção das capturas).

Índices novos em `anuncios(data_pub)`, `anuncios(cpv)` e
`anuncios(estado)`, para a base não abrandar à medida que cresce para
lá dos 500.

## Testes, controlo de versões e automatismos

**`teste_radar.py`** — 31 testes, correm em milissegundos, sem rede nem
base de dados. Não são exaustivos de propósito: cada um corresponde a um
erro que existiu **mesmo**, e o comentário diz qual, para ninguém
"simplificar" de volta para o erro. Cobrem o prefixo de CPV, o escape do
LIKE, as duas caixas de pesquisa, a contagem de dias, `nome_seguro()`, o
parser de secções e a semeadora de fases.

Verificado que apanham regressões: reintroduzindo o bug do CPV
(`curto or digitos` em vez do mínimo de dois dígitos), três testes falham
com a mensagem certa (`['3'] != ['30']`).

**Git** — o repositório começa aqui, com um `.gitignore` que deixa de
fora o que nunca deve entrar em histórico: `curl_*.txt` (levam o token da
sessão do browser), `radar.db*`, `documentos/` (Cadernos de Encargos e
propostas) e `amostras/`.

**Hooks**, em `../.claude/hooks/`:

- `verificar_sintaxe.py` (PostToolUse) — compila o ficheiro Python
  acabado de escrever, com `-W error::SyntaxWarning`. Existe porque os
  erros que passaram foram todos de sintaxe e de escapes; este apanha o
  `"\%"` que aqui mordeu duas vezes.
- `proteger_dados.py` (PreToolUse) — recusa escritas em `curl_*.txt` e
  `radar.db*`. Sai com código 2 para travar a ferramenta.

**Skill `/estado-radar`** — o resumo que se pedia à mão várias vezes por
sessão: quantos por ler, triagem, fases, validade das capturas, painel e
tarefas. Lê a base em modo só-leitura e não importa o `radar.py`, por
isso funciona mesmo com o programa a meio de uma alteração que não
compila.

## Estrutura do código

Ficheiro único, `radar.py`, sem dependências além de `flask` e
`requests` (cresceu passado das 600 linhas originais com o dicionário
de CPV e a árvore no painel, mas continua um ficheiro só). Blocos, por
ordem no ficheiro:

- configuração e base de dados, `CONFIG_INICIAL`, `iniciar_db`
- leitura das capturas, `carregar_curl`, `parse_curl`, que entende os
  formatos bash e cmd
- reparação de filtros e limpeza do corpo, `repara_filtros`,
  `limpa_resultados`
- leitura da resposta, `campo`, `anuncios_da_resposta`
- detalhe, `seccoes_do_texto`, `valor_de`, `campos_do_detalhe`,
  `ler_detalhes` (com rede), `reparsear` (sem rede)
- documentos, `obter_documentos` e os `_pecas_*` por plataforma
- recolha e gravação, `recolher`, `guardar`, `verificar`
- dicionário de CPV, `importar_cpv_dict`, `cpv_por_termo`
- agendamento, `relogio`, com recuperação de horário falhado
- painel Flask, `condicoes` traduz os filtros em SQL; rota `/cpv.json`
  alimenta a árvore de CPV, a árvore em si é montada em JS no browser,
  dentro do `<script>` no fim do `PAGINA`
- quadro (kanban), `QUADRO_PAGINA`, `cartao`, rotas `/quadro*`

Tabela `anuncios`: `ref` é chave primária e é o número do anúncio, o que
serve de deduplicação. Campos `cpv`, `prazo`, `preco_base`, `plataforma`,
`detalhe_lido`, mais `texto` (o anúncio inteiro), `pdf_url`,
`link_pecas`, `docs_estado` e `fase_id`. Estados: `novo`, `interessa`,
`descartado`. Tabelas `fases`, `etiquetas`, `anuncio_etiquetas` para o
quadro, e `documentos` para o índice dos ficheiros em disco.

As migrações de esquema estão em `iniciar_db()`, com `PRAGMA
table_info` + `ALTER TABLE` só se a coluna faltar. Correm sempre, não
fazem nada se já estiver tudo lá — é seguro chamar a qualquer momento.

O enriquecimento corre a seguir a cada verificação, 40 anúncios de cada
vez, com um segundo de pausa entre pedidos. Configurável em
`detalhes_por_volta`.

## Coisas a saber antes de mexer

A pasta está no ambiente de trabalho, dentro do OneDrive. A sincronização
pode bloquear o `radar.db` durante a escrita. Se aparecerem erros de base
bloqueada, é isto, e resolve-se movendo a pasta para fora do OneDrive.

O painel limita a tabela a 500 linhas por questão de apresentação. A base
não tem limite.

Python 3.14 instalado pela Microsoft Store. O `flask.exe` fica fora do
PATH, o que é indiferente porque o arranque é por `python radar.py`.

O servidor de desenvolvimento do Flask, no Windows, às vezes deixa duas
instâncias ligarem-se à mesma porta 8765 sem se queixar (`SO_REUSEADDR`),
e as respostas passam a vir ora de uma ora de outra, de forma imprevisível
— sintoma: mudas o código, reinicias, e o painel continua a comportar-se
como a versão antiga. Se isto acontecer, `Get-NetTCPConnection -LocalPort
8765` mostra os PIDs a ligar; mata-se os dois e arranca-se de novo, um
de cada vez.

## O que fica de fora, e porquê

Abaixo dos limiares de publicação obrigatória, os procedimentos não
aparecem no DR, aparecem no Portal BASE. O acesso à API do BASE exige
pedido e autorização ao IMPIC, feito pelo helpdesk, e está por submeter.
É a peça que falta para cobertura completa e para deixar de depender de
capturas de browser.

O TED foi implementado e depois retirado, por decisão do Afonso: o que
vai ao TED de entidades portuguesas sai também no DR. Fica a nota de que
o TED é a única fonte para Espanha, mercado onde a empresa está a
qualificar-se, e que a API v3 do TED é pública e sem chave.

O radar já traz as peças do procedimento (Programa de Concurso, Caderno
de Encargos, anexos) em ~90% dos casos — ver "A ficha do anúncio e as
peças do procedimento" — nas quatro plataformas que aparecem na base
(acingov, vortal, anogov, compraspt), o que cobre ~99% dos anúncios que
indicam plataforma.

A sonda (`sonda.py`, `sonda.bat`, `sonda.txt`, `sonda_detalhe.html`) foi
apagada: respondia a duas perguntas — se a pesquisa aceitava termo vazio
e de onde vinha o CPV — ambas respondidas há muito e documentadas aqui.
