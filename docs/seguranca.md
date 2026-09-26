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

## As seis, por ordem de gravidade

1. **Caminhos de ficheiro montados a partir do URL.** As rotas que
   servem ficheiros recebem `<path:ref>`, que aceita barras. Qualquer
   caminho tem de passar por `caminho_na_pasta()`; uma guarda que
   compare o caminho final com uma pasta que o próprio pedido
   escolheu não é guarda. Foi assim que `/peca/../radar.db` serviu a
   base a 8/09/2026.

2. **Texto que vem do pedido e entra no HTML sem `html.escape()`.**
   O painel gera HTML por concatenação de strings, não por templates
   com escape automático: cada `%s` numa página é um sítio a
   verificar. Inclui as mensagens de erro e os 404.

3. **Rotas que escapam à porta.** As abertas estão em `ROTAS_ABERTAS`
   (por igualdade) e `PREFIXOS_ABERTOS` (por prefixo), e cada uma que
   aceita um POST traz a guarda **dentro de si**: o `/pedir-acesso`
   (origem, armadilha, tectos), o `/convite/<código>` e, desde
   26/09/2026, o `/repor/<código>` (o código de 32 bytes guardado só em
   resumo, a origem, o prazo, o uso único e um trinco por IP). Uma rota
   nova que não passe pelo `before_request`, ou um POST sem verificação
   de CSRF quando há sessão, é uma falha. O `/saude` entrou a 15/09/2026
   e responde «ok» ou 503 sem dizer nada de dentro: é assim que uma rota
   aberta se escreve. **Uma ligação de repor vale uma palavra-passe**:
   só a gera quem pode (`contas.pode_repor()` — o dono para qualquer
   conta, o admin para as da empresa dele e nunca para a do dono), só
   se mostra na resposta do POST, e usá-la fecha todas as sessões da
   conta.

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

## O que não vale a pena rever aqui

Com um utilizador, atrás de um túnel autenticado pela Cloudflare:
dependências desactualizadas, e limite de pedidos fora do login — no
login existe, e é o trinco por conta e IP do `contas.py`, que faz a
resposta esperar N segundos ao fim de demasiadas tentativas.

**A lista original também mandava ignorar a falta de cabeçalhos de
segurança HTTP e a ausência de tecto no tamanho de um pedido. Isso
mudou a 14/09/2026:** os cabeçalhos passaram a existir
(`CABECALHOS_DE_SEGURANCA`, com o CSP que o painel aguenta) e o
`MAX_CONTENT_LENGTH` ficou nos 20 MB. Deixaram de ser coisas a
ignorar e passaram a ser coisas a não estragar.
