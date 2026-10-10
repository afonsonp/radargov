# O que rever neste projecto, e por que ordem

Estas seis prioridades foram escritas a 8/09/2026 para a revisão
automática do GitHub (`.github/seguranca-radar.md`), que lhe dizia o
que procurar. **A revisão saiu a 15/09/2026** — nunca chegou a correr
uma única vez, faltava-lhe sempre a chave, e mantê-la custava uma
chamada paga por cada push num projecto privado de um utilizador; o
caso todo está no `docs/diario/2026-09.md` desse dia. A lista
sobreviveu-lhe porque o valor dela nunca esteve na ferramenta: é o que
uma pessoa deve ler com atenção antes de gravar, e o que uma sessão
deve reler antes de mexer na porta, nas rotas ou no que serve
ficheiros.

Cada ponto vem de uma falha real ou de uma quase-falha deste
repositório, e não de uma lista genérica.

## O terreno

O Radar é uma aplicação Flask que serve o painel em `radargov.pt`
através de um túnel da Cloudflare, com login próprio (`contas.py` e a
`porta_de_entrada()` do `radar.py`). Corre no computador pessoal do
Afonso, na mesma pasta onde estão o `radar.db`, o `config.json`, a pasta
`empresas/` (a base, a configuração e a triagem de cada empresa) e as
capturas `curl_*.txt` — ficheiros que **nunca** podem ser servidos.

## As sete, por ordem de gravidade

1. **Caminhos de ficheiro montados a partir do URL.** As rotas que
   servem ficheiros recebem `<path:ref>`, que aceita barras. Qualquer
   caminho tem de passar por `caminho_na_pasta()`; uma guarda que
   compare o caminho final com uma pasta que o próprio pedido
   escolheu não é guarda. Foi assim que `/peca/../radar.db` serviu a
   base a 8/09/2026. **E a pasta tem de ser da empresa do pedido**:
   até 26/09/2026 a `importacoes/` era de todas, e a confirmação de
   uma importação aceitava o nome (data e hora) de um ficheiro que
   outra empresa carregara. Um nome que vem do pedido resolve-se
   dentro de `empresas/<id>/`, e recusa-se se trouxer `/`, `\` ou
   `..` — não se «limpa».

2. **Texto que vem do pedido e entra no HTML sem `html.escape()`.**
   O painel gera HTML por concatenação de strings, não por templates
   com escape automático: cada `%s` numa página é um sítio a
   verificar. Inclui as mensagens de erro e os 404.

3. **Rotas que escapam à porta.** As abertas estão em `ROTAS_ABERTAS`
   (por igualdade) e `PREFIXOS_ABERTOS` (por prefixo), e cada uma que
   aceita um POST traz a guarda **dentro de si**: o `/pedir-acesso`
   (origem, armadilha, tectos), o `/convite/<código>` e, desde
   26/09/2026, o `/repor/<código>` (o código de 32 bytes guardado só em
   resumo, a origem, o prazo, o uso único e um trinco por IP, só dele —
   não conta no do `/entrar`), desde 1/10/2026 o `/esqueci-me` (a
   origem, o tecto por IP e pelo endereço escrito, a mesma resposta
   exista ou não a conta — com a procura e o envio em fundo, para o
   tempo não o dizer —, a ligação a uma hora, o endereço do config e
   não o `Host` do pedido, e nunca a conta do dono; desde o mesmo dia
   procura também pelo `contacto` da conta, que é de uma conta só, se
   muda com a palavra-passe actual, e com duas contas no mesmo endereço
   não manda nada) e, desde
   28/09/2026, o `/entrar/codigo` do segundo factor (o pendente, só em
   resumo, cinco minutos e cinco tentativas, o trinco e a origem). E,
   desde 5/10/2026, o `/pedido/<código>`, a página de estado do pedido
   de acesso: só GET, o código de 18 bytes vai só para quem pediu e na
   base fica o resumo, um código errado dá 404 sem mais nada, a página
   diz o estado e o e-mail do próprio pedido e nada da plataforma, e
   leva `Cache-Control: no-store` para a borda não a guardar.
   **Uma porta que abra sessões passa pelo `contas.entrar()`**, que é
   onde está a guarda do segundo factor: a ligação de repor da conta do
   dono leva ao ecrã do código, e não a uma sessão. Uma rota
   nova que não passe pelo `before_request`, ou um POST sem verificação
   de CSRF quando há sessão, é uma falha. O `/saude` entrou a 15/09/2026
   e responde «ok» ou 503 sem dizer nada de dentro: é assim que uma rota
   aberta se escreve. **Uma ligação de repor vale uma palavra-passe**:
   só a gera quem pode (`contas.pode_repor()` — o dono para qualquer
   conta, o admin para as da empresa dele e nunca para a do dono), só
   se mostra na resposta do POST, e usá-la fecha todas as sessões da
   conta. **Um 500 não guarda o código**: o `rebentou()` corta o
   caminho do `/repor/…` e do `/convite/…` antes de o escrever nos
   erros. **E o mesmo vale para tirar uma conta**: até 26/09/2026 o
   admin da empresa onde o dono tem conta tirava-o, e numa base sem
   dono o admin seguinte nascia dono. Toda a acção de um admin sobre
   uma conta pergunta se é da empresa dele **e** se é o dono
   (`contas.apagar_utilizador(…, quem=)`; o último dono nunca sai).
   **E um dono só nasce pela consola** (F2, 26/09/2026): o
   `criar_utilizador()` só marca dono com `pela_consola=True`, que só o
   `--criar-utilizador` passa — do painel, de um convite ou de uma
   reposição, nunca. **O «ver como a empresa» do dono é só de leitura
   em dois sítios** (26/09/2026): a porta recusa todos os POST dessa
   sessão menos o sair (`PODE_A_VER_COMO`), e o `liga()` junta o ficheiro
   da empresa com `mode=ro`. A marca é da sessão e só vale numa conta de
   dono; cada entrada e saída fica no histórico da empresa. Uma rota nova
   do dono entra em `ROTAS_SO_DONO` (todas as da `/plataforma/…` já
   entram pelo prefixo) — e uma rota que **não** seja do dono não pode
   começar por `/plataforma/`: o «Abrir na Vortal» deu 403 às empresas
   até 26/09/2026 por isso.

4. **`pedido_e_local()` e o acesso livre.** `acesso_livre_local` dá
   entrada sem palavra-passe a pedidos de `127.0.0.1`. O cloudflared
   liga-se ao painel a partir de `127.0.0.1` — qualquer mudança que
   torne mais fácil um visitante do túnel parecer local é grave. É o
   `ProxyFix` com um salto de confiança que separa os dois casos.

5. **Segredos.** Chaves de modelos, cookies das capturas e o conteúdo
   do `config.json` não podem aparecer em páginas, em registos, em
   mensagens de erro nem em ficheiros que entrem no git. O
   `gravar_config_registado()` recusa chaves que pareçam segredos, e o
   `.gitignore` largo é a outra metade da guarda — e desde 23/09/2026
   o `config.json` e o `triagem.jsonl` também estão lá.

6. **SQL construído por concatenação** com valores vindos do pedido
   (o motor de filtros monta condições).

7. **O conector MCP** (10/10/2026): a segunda porta para os dados de
   uma empresa, aberta a servidores de fora. Quatro coisas a rever em
   cada mudança: **a empresa vem só do token** — relido a cada chamada
   contra a conta (`contas.conta_do_token_mcp()`), posto pelo
   `com_empresa()` da rota, e nenhuma ferramenta recebe o número da
   empresa; **a credencial é só o bearer** — nunca o cookie do painel
   nem o acesso livre local, que a porta já leu antes de a rota correr;
   **nada escreve** — as ferramentas só lêem, e correm em
   `so_de_leitura()` (`PRAGMA query_only`); e **o que sai é a lista
   fechada** — sem contactos, notas nem documentos do cofre, com o
   texto de terceiros limpo e cortado (`mcp_servidor.limpo()`), porque
   um anúncio pode trazer instruções para o modelo de quem pergunta. O
   OAuth guarda só resumos, aceita só o redirect do Claude
   (`REDIRECTS_DO_MCP`), exige o PKCE `S256`, e revoga a família de um
   código ou de um refresh usado duas vezes. **E nada sem tecto** (revisão
   de 10/10/2026): o registo dinâmico até 5 redirects e 8 KB, com os
   clientes sem tokens a sair aos 30 dias; as listas até 40 páginas; cada
   ligação das ferramentas com 10 s de prazo (`_com_prazo()`), recusado
   por palavras e fora dos erros; números NaN ou infinitos recusados; o
   histórico por lista branca (`ACCOES_QUE_SAEM`); e o dicionário das
   falhas do `/oauth/token` podado. Os testes que provam o
   isolamento (`TestConectorMCP`) falham quando se força a empresa
   errada — se um deixar de falhar, é o teste que está estragado.

## O que não vale a pena rever aqui

Com um utilizador, atrás de um túnel autenticado pela Cloudflare:
dependências desactualizadas, e limite de pedidos fora do login — no
login existe, e é o trinco do `contas.py` — por conta, com um tecto
muito mais alto por IP desde 29/09/2026 (D2) —, que faz a
resposta esperar N segundos ao fim de demasiadas tentativas.

**A lista original também mandava ignorar a falta de cabeçalhos de
segurança HTTP e a ausência de tecto no tamanho de um pedido. Isso
mudou a 14/09/2026:** os cabeçalhos passaram a existir
(`CABECALHOS_DE_SEGURANCA`, com o CSP que o painel aguenta) e o
`MAX_CONTENT_LENGTH` ficou nos 20 MB. Deixaram de ser coisas a
ignorar e passaram a ser coisas a não estragar.
