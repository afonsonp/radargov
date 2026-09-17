# Plano: o radar online, com login e um menu de configurações

> **Instantâneo de 03/09/2026.** Descreve o que se planeou ou mediu
> nesse dia. O que mudou depois está no `ESTADO.md` e no
> `docs/diario/`. Não se edita.

Escrito a **3 de setembro de 2026**, à tarde, a pedido do Afonso. A
primeira versão deste ficheiro, da mesma tarde, planeava empresas,
utilizadores por empresa e um super-admin; **ele pôs isso de lado
horas depois**: «eu quero eu, Afonso Pinto, usar a plataforma num
formato online. Mas quero ter login para não ser aberto ao mundo. Para
além disso os alertas e os interesses, entre outras configurações, devem
estar num menu de configurações». Essa primeira versão fica em
`ONLINE-empresas.md`, ao lado, para o dia em que uma segunda empresa
aparecer; o que
aqui se planeia não lhe fecha a porta — a tabela de utilizadores é uma
tabela, não uma linha no `config.json` — mas não paga nada dela hoje.

É um plano, não trabalho feito. Quando cada etapa se fizer, corrige-se o
`ESTADO.md`, o `docs/armadilhas.md`, o `LEIA-ME.md` e o `CLAUDE.md` no
mesmo commit; este ficheiro fica como instantâneo.

---

## 0. O que o âmbito novo tira do caminho

Um utilizador só muda o plano mais do que parece. Com uma empresa, **a
triagem fica onde está** — nas colunas de `anuncios` — e não há
`empresa_id` em tabela nenhuma. Era a etapa de 4 a 6 dias e a mais
arriscada (98 sítios do `radar.py` a tocar, um JOIN esquecido e uma
empresa via a triagem da outra). Desaparece inteira.

O que sobra são três coisas, e as três são pequenas:

1. **Login**, para a porta não ficar aberta. Um utilizador, uma
   palavra-passe, sessão, e a protecção dos formulários que a internet
   pública obriga.
2. **Configurações num sítio**, em vez de espalhadas pelo separador
   Alertas, pelo `config.json` editado à mão e por cinco ficheiros de
   texto na pasta.
3. **Servir online**, o que já estava desenhado no `docs/referencia.md`
   («Pessoas, e o caminho para isto ser partilhado») e só precisa de
   uma decisão sobre onde.

O que **já existe** e se aproveita, medido a 3/09/2026:

- A banda `pessoas` do `radar.py`: `quem_sou()` lê o cookie `quem`,
  `registar()` grava quem fez o quê em `historico`. O comentário lá diz
  que «quando isto for para um servidor partilhado, é aqui que entra a
  autenticação» — é aqui, e é menos do que o comentário temia.
- `gravar_config(mudancas)` já existe e já é o que o e-mail e a janela
  do urgente usam para não se editar o JSON à mão. O menu de
  configurações é, em grande parte, **formulários por cima dela**.
- `ler_chave()` já lê as chaves dos ficheiros `.txt` **ou** de variáveis
  de ambiente. No servidor usam-se as variáveis, sem mudar código.
- SQLite em WAL, `busy_timeout`, cópias diárias em `copias/`, o B15 a
  empurrar o `triagem.jsonl` para o GitHub. Tudo isto serve tal como
  está, com um papel ligeiramente diferente (secção 3).

## 1. Login (1 a 2 dias)

**Módulo novo `contas.py`**, ao molde do `casa.py`: as suas tabelas, o
seu `iniciar_tabelas(c)` chamado de `iniciar_db()`, os seus testes.

```sql
utilizadores (id, email UNIQUE, nome, hash, criado_em, ultimo_acesso)
sessoes      (token PRIMARY KEY, utilizador_id, criada_em, expira, ip,
              agente)
```

Uma linha em `utilizadores`. É tabela e não chave do `config.json`
porque um segundo utilizador há-de ser uma linha, não uma reescrita — e
porque a palavra-passe não pode viver num ficheiro «que se abre sem
pensar», como o `gravar_config()` já diz.

Decisões técnicas, para não as discutir duas vezes:

- **Palavra-passe com `hashlib.scrypt`** (biblioteca padrão, sem
  dependência nova; `n=2**14, r=8, p=1`, sal de 16 bytes; guardado como
  `scrypt$sal$hash`; verificação com `hmac.compare_digest`).
- **Sessões no servidor**, não no cookie assinado do Flask: «sair» e
  «sair de todos os aparelhos» invalidam de imediato, e não há
  `secret_key` a gerir. Cookie `sessao`, `HttpOnly`, `SameSite=Lax`,
  `Secure` quando o pedido vier por HTTPS (o `ProxyFix` da etapa 3 é o
  que faz o Flask saber isso atrás do Caddy). Trinta dias deslizantes.
- **Trinco ao login**: cinco falhas em 15 minutos, por e-mail ou por
  IP, e a resposta passa a esperar. As falhas vão para a série de
  `erros` (C3), que já tem poda — é assim que se vê se alguém anda a
  bater à porta.
- **CSRF**: um token por sessão, escrito num campo escondido por um
  helper único, `campo_csrf()`, que **todos os formulários passam a
  incluir**; um `before_request` recusa qualquer `POST` sem ele. São
  cerca de 25 formulários; é trabalho de procurar `<form` e acrescentar
  o campo. `envolver()` passa o token à página uma vez, como já passa a
  lista de pessoas.
- **`quem_sou()` passa a ler a sessão** e devolve o nome do utilizador.
  O cookie `quem` e a rota `/sou` **desaparecem**. A tabela `pessoas`
  fica como está: é a lista de nomes para o «responsável», que pode ser
  um colega sem conta na plataforma.
- **A pen continua a funcionar como hoje** com um interruptor só:
  `"acesso_livre_local": true` no `config.json` liga um pedido vindo de
  `127.0.0.1` ao único utilizador, sem login. É o que mantém o
  desenvolvimento e os 669 testes sem fazerem login em cada pedido.
  **Não são dois caminhos de código**: a única coisa que muda é como a
  sessão se resolve. No servidor a chave fica a `false`, e o arranque
  recusa-se a ouvir fora de `127.0.0.1` com ela a `true` — é a guarda
  contra pôr o servidor de pé com a porta aberta por engano.
- **Recuperar a palavra-passe é pela linha de comandos**, não por
  e-mail: `python radar.py --palavra-passe EMAIL` pede a nova por
  `getpass` e grava. Para um utilizador com acesso SSH ao servidor é o
  suficiente, e é um fluxo a menos exposto à internet. Se um dia
  houver mais gente, é aí que entra a recuperação por e-mail.
- **Trabalho de fundo** (`relogio()`, fila das peças, alertas) não tem
  pedido nem sessão: `registar()` já aceita `quem=` explícito por isso
  mesmo. Nada muda aí.

Rotas: `GET/POST /entrar` (e-mail, palavra-passe, «Entrar»; nada mais
— um ecrã, uma tarefa), `POST /sair`, `POST /sair-de-todos`. O
`before_request` exige sessão em tudo o que não seja `/entrar` e as
imagens das peças pedidas de dentro de uma página com sessão. A conta
(nome, e-mail, palavra-passe, sessões activas) vive no menu de
configurações, secção 2.

Arranque: `python radar.py --criar-utilizador EMAIL` cria o utilizador
e pede a palavra-passe. Sem utilizador, o painel só tem a página de
entrada e diz que comando correr.

Testes (`TestContas`): hash e verificação; sessão expira; trinco ao
quinto erro; `POST` sem CSRF recusado em **todas** as rotas `POST` do
`app.url_map` (o teste percorre o mapa, para uma rota nova não escapar);
`acesso_livre_local` só de `127.0.0.1`; «sair de todos» mata a outra
sessão no pedido seguinte; arranque recusado com `acesso_livre_local`
ligado e `host` fora do localhost.

## 2. O menu de configurações (2 a 3 dias)

### A decisão que se reverte

O esqueleto de 30/08/2026 (`docs/historico/ESQUELETO.md`, §2, decisão
11.6-A) decidiu **não criar página «Definições»**: «seria uma entidade
técnica, não uma intenção», e as definições ficaram distribuídas de
propósito — e-mail e urgente em Alertas, identidade no cabeçalho,
horas e leituras no `config.json`. O Afonso reverte-a a 3/09/2026, e a
razão é boa: o que era «afinar o que o radar vigia sozinho» (Alertas)
mais «o que se edita à mão no JSON» mais «cinco ficheiros de chaves na
pasta» **deixa de caber em três sítios quando a pasta está num
servidor** onde não se abre o Bloco de Notas. A página passa a ser uma
intenção: *dizer ao radar como quero que ele trabalhe*.

A consequência na barra: **Alertas sai do primeiro nível.** Ficam
Anúncios, Em curso, Mercado — e Configurações entra em baixo, ao lado
da zona de estado, como os Indicadores: não é uma intenção diária, é
onde se vai de vez em quando. `/alertas` e `/alertas/interesse`
redireccionam para as secções novas, e o «guardar filtro» das listas
aponta para lá. A `docs/historico/UX-Auditoria.md` lê-se antes de
desenhar isto; as regras dela (alvos a 24 px, contraste, desfazer)
valem aqui como em qualquer ecrã.

### As secções

Uma rota por secção, `/configuracoes/<seccao>`, cada uma **um
formulário que grava uma coisa** e volta a dizer o que ficou. Não é um
formulário único com tudo: quem grava o e-mail não quer arriscar as
horas da recolha pelo caminho. A página tem o índice das secções à
esquerda, preso ao rolar, como a ficha do anúncio tem o dela.

| Secção | O que lá está | De onde vem hoje |
|---|---|---|
| **Interesse** | o interruptor e os CPV que a casa trabalha, com a árvore; quantos anúncios ficam dentro e fora | `/alertas/interesse` (muda de sítio, não de código) |
| **Alertas** | os filtros guardados com o interruptor de alerta e a taxa de acerto; entidades seguidas; destino e hora do resumo; janela do urgente; «enviar já»; o histórico do que saiu | `/alertas` inteiro |
| **Recolha** | horas da verificação; janela de recuperação (`dias_catchup`); janela do detalhe (`detalhe_dias`) e quantos por volta; Vortal ligada/desligada; recuperar slots falhados | `config.json` à mão |
| **Leitura das peças** | fornecedor e modelo em uso; as perguntas configuráveis (B08, `leituras`); estado de cada chave (está/não está, e desde quando) e um campo para colar uma nova | `config.json` + `*_API_KEY.txt` |
| **Capturas** | idade de cada captura e a última vez que funcionou; um campo para colar a nova, validado por `parse_curl()` antes de gravar | ficheiros `curl_*.txt` trocados na pasta (LEIA-ME §3) |
| **Cópias** | cópia diária ligada/desligada e quantas guardar; `triagem_no_git`; a lista das cópias que existem | `config.json` |
| **Conta** | nome, e-mail, mudar a palavra-passe; sessões activas com aparelho e data, e «sair de todos» | `/sou` (identidade sem palavra-passe) |

O que **fica no `config.json` de propósito**, sem formulário: os termos
de pesquisa e de reserva, `paginas`, `por_pagina`, `abrir_browser_ao_
encontrar`. São afinação de quem mexe no código, e um campo para cada
um seria ruído no ecrã sem uso previsto. Continuam documentados no
`LEIA-ME.md` como hoje.

### Regras para o fazer

- **Cada gravação passa por `gravar_config()`**, que já sabe juntar sem
  apagar o resto. As chaves e a palavra-passe do e-mail **nunca** vão
  ao `config.json`: continuam nos ficheiros de hoje (o campo do ecrã
  escreve o ficheiro), ou nas variáveis de ambiente no servidor — e aí
  o ecrã mostra «definida por variável» e não deixa editar.
- **Validar antes de gravar**: horas em `HH:MM`, inteiros com limites
  (uma janela de detalhe de 0 dias cala a recolha em silêncio), CPV
  pela árvore. O formulário volta preenchido com o erro ao lado, como o
  de criar filtro já faz.
- **Cada gravação regista-se** em `historico` com `ref=''`, a chave e
  os valores antes e depois. A pergunta «desde quando é que isto está
  assim?» tem de ter resposta.
- **A colagem de uma captura grava o ficheiro pela aplicação**, o que
  não conflitua com o hook `proteger_dados.py`: esse protege as edições
  feitas pelo Claude, não as da aplicação.
- **O interesse e os alertas não mudam de comportamento**, só de
  morada. As armadilhas deles mantêm-se: o interesse entra por
  `com_recorte()`, nunca por `condicoes()`; um número num ecrã dá a
  lista que abre. As funções das rotas actuais reutilizam-se; o que
  muda é o `envolver()` (título, item da barra) e o caminho.

Testes: cada secção grava e relê (o que se gravou é o que se lê);
`gravar_config()` não perde chaves que a secção não mostra; validação
recusa e devolve o formulário; `/alertas` e `/alertas/interesse`
redireccionam; a colagem de uma captura inválida não toca no ficheiro;
uma chave posta por variável de ambiente não é editável.

## 3. Servir online (1 a 2 dias, mais o alojamento)

A escolha primeiro, porque o resto depende dela:

- **A. Um VPS pequeno em Linux** (Hetzner ou DigitalOcean, 5 a 10 €/mês,
  40 GB de disco pelo `contratos.db` e pelas peças). Está de pé 24 h, vê-se
  do telemóvel, e a recolha corre lá sem o PC ligado. É o que o
  `docs/referencia.md` recomenda.
- **B. O PC de casa, exposto por um túnel** (Tailscale, que só tu vês,
  ou Cloudflare Tunnel, com domínio). Custa zero, não muda nada na
  forma como a recolha corre hoje, e o login continua a ser obrigatório.
  A desvantagem é a de sempre: quando o PC está desligado, o radar não
  está.

O plano assume **A**. Se for B, a etapa 3 reduz-se ao túnel e ao
`acesso_livre_local: false`, e o resto do plano não muda.

Com o VPS:

1. **gunicorn** com 2 trabalhadores atrás do **Caddy** (HTTPS automático
   com Let's Encrypt; menos configuração que nginx + certbot). `ProxyFix`
   no Flask para ler `X-Forwarded-Proto` e pôr o cookie `Secure`.
2. **O agendador sai do processo web**: `python radar.py --uma-vez` por
   `systemd` timer às 09:00 e 17:00, e o `--contratos` à segunda —
   exactamente o que as tarefas do Windows fazem hoje. O `relogio()`
   passa a arrancar só com `"relogio_interno": true`; com dois
   trabalhadores gunicorn, cada um dispararia o slot.
3. **Segredos por variáveis de ambiente** no ficheiro de ambiente do
   `systemd`: `RADAR_EMAIL_SENHA`, `GROQ_API_KEY`, e as outras que
   `ler_chave()` já conhece. Os `.txt` não vão para o servidor.
4. **`documentos/`, `radar.db` e `contratos.db` no disco do VPS.**
   Levam-se uma vez por `rsync`/`scp`; o corpus, se for mais simples,
   refaz-se lá com `--contratos`.
5. **Cópias para fora da máquina**: `copias/` continua a fazer a diária;
   um `rclone` ou `scp` de manhã leva a última para o PC ou para um
   bucket. O `contratos.db` não se copia — refaz-se.
6. **`endereco_publico`** no `config.json`, para os links do e-mail de
   alerta deixarem de apontar para `localhost`.
7. **Quem recolhe passa a ser o servidor.** Duas instâncias a recolher e
   a triar (a pen e o VPS) divergem na triagem em dias. A pen passa a ser
   desenvolvimento e testes; a triagem chega-lhe pelo `triagem.jsonl`
   que o B15 empurra do servidor (`--repor-triagem`), e a base pela
   cópia. As tarefas do Windows tiram-se com o `desinstalar.bat`.

## 4. Ordem, e porquê

**1 → 2 → 3.** O login é pequeno e é o que autoriza tudo o resto; as
configurações fazem-se e testam-se em local, e é lá que nasce o ecrã
das capturas de que o servidor precisa; servir online é o último passo
porque é o único que se faz melhor de uma vez só do que aos bocados.
Total: **4 a 7 dias** de trabalho, mais o dia de pôr o VPS de pé.

## 5. Os riscos, e onde cada um se apanha

| Risco | Onde se apanha |
|---|---|
| Servidor de pé com `acesso_livre_local` ligado | O arranque recusa-se; teste que o prova |
| Um `POST` novo sem CSRF | O teste percorre `app.url_map` e faz `POST` sem token a cada rota |
| A palavra-passe ou uma chave acaba no `config.json` | `gravar_config()` recusa as chaves proibidas; teste |
| Dois trabalhadores, duas verificações às 09:00 | `relogio_interno` desligado no servidor; `slots` já é único por (dia, hora) |
| Uma secção grava e apaga o que outra tinha posto | `gravar_config()` junta; teste que grava A, grava B, relê A |
| A pen e o servidor a triar em paralelo | Decisão 3.7: só o servidor recolhe; a pen repõe pelo `triagem.jsonl` |
| Ficar sem palavra-passe | `--palavra-passe EMAIL` por SSH, documentado no `LEIA-ME.md` |

## 6. O que é do Afonso decidir antes de começar

1. **VPS ou túnel do PC** (secção 3, A ou B). O plano assume o VPS.
2. **Alertas sai da barra** e passa a secção de Configurações — é o que o
   pedido implica, e reverte o esqueleto. Fica escrito aqui porque a
   barra é o que ele vê todos os dias.
3. **Recuperar a palavra-passe pela linha de comandos** chega, ou
   quer-se por e-mail desde já?
4. **A pen deixa de recolher** quando o servidor recolher (3.7)?
5. **Nome e domínio** para o `endereco_publico`.

## 7. O que a documentação terá de dizer no fim

- `ESTADO.md` — «O que está implementado» ganha login e configurações;
  «O que não corre sozinho» passa a falar do `systemd` e não das
  tarefas do Windows quando o servidor for a instância que recolhe.
- `docs/armadilhas.md` — área nova **«Contas e servidor»** (o CSRF nos
  formulários, o `acesso_livre_local`, o `relogio_interno`, as chaves
  fora do `config.json`), e «A interface» ganha a reversão do 11.6-A.
- `CLAUDE.md` — `contas.py` ao lado do `casa.py`; a banda `pessoas`
  reescrita; os comandos `--criar-utilizador` e `--palavra-passe`; a
  barra com três intenções e Configurações; `/sou` e o cookie `quem`
  deixam de existir.
- `LEIA-ME.md` — secção nova para o servidor (variáveis, `systemd`,
  Caddy, colar capturas no ecrã em vez de trocar ficheiros, cópias); a
  secção 3 das capturas e a 7 «Quem está a trabalhar» reescritas.
- `docs/historico/ESQUELETO.md` — não se edita (é instantâneo); a
  reversão do 11.6-A fica registada no diário e nas armadilhas.
- `BACKLOG.md` — «Multi-utilizador a sério» volta ao «não fazer», com a
  nota de que o login de uma pessoa está feito.
