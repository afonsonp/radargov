# O que este projecto quer que a revisão procure

O Radar é uma aplicação Flask que serve o painel em `radargov.pt`
através de um túnel da Cloudflare, com login próprio (`contas.py` e a
`porta_de_entrada()` do `radar.py`). Corre no computador pessoal do
Afonso, na mesma pasta onde estão o `radar.db`, o `config.json` e as
capturas `curl_*.txt` — ficheiros que **nunca** podem ser servidos.

Dá prioridade a:

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
3. **Rotas que escapam à porta.** Só `/entrar` está em
   `ROTAS_ABERTAS`. Uma rota nova que não passe pelo
   `before_request`, ou um POST sem verificação de CSRF quando há
   sessão, é uma falha.
4. **`pedido_e_local()` e o acesso livre.** `acesso_livre_local` dá
   entrada sem palavra-passe a pedidos de `127.0.0.1`. O cloudflared
   liga-se ao painel a partir de `127.0.0.1` — qualquer mudança que
   torne mais fácil um visitante do túnel parecer local é grave.
5. **Segredos.** Chaves de modelos, cookies das capturas e o conteúdo
   do `config.json` não podem aparecer em páginas, em registos, em
   mensagens de erro nem em ficheiros que entrem no git.
6. **SQL construído por concatenação** com valores vindos do pedido
   (o motor de filtros monta condições).

Ignora: falta de cabeçalhos de segurança HTTP, ausência de limite de
pedidos fora do login, e dependências desactualizadas — o painel tem
um utilizador e está atrás de um túnel autenticado por Cloudflare.
