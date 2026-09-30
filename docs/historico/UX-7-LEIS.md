# Auditoria das sete leis — o Mira Gov inteiro

30/09/2026. Só leitura: não se mexeu em nenhum ficheiro do repositório, não se correu o painel e não se fez nenhum pedido à rede.

**Material usado**
- `ecrans.html`: 34 ecrãs vistos como gestor da empresa 2 (LATD). Separados um a um e contados com um script (botões, ligações, campos, opções, etiquetas, botões primários).
- O código, para o que não está na captura: `_lista_de_propostas()`, `linha_da_pipeline()`, `selector_de_ranhura()`, `barra_de_baixo()`, `administracao_da_plataforma()`, `plataforma_empresa()`, `pedidos_de_acesso()`, `_formulario_do_aceitar()`, `convite()`, `repor()`, `pagina_do_codigo()`, `html_do_resumo()`, `texto_e_html_do_convite()` e a linha de tarefa do Hoje.
- Os ficheiros `site/*.html`, `site/moldura.css`, `estilo/miragov-*.css` e o CSS que está dentro do `radar.py`.

**O que não se viu**
- A ficha da entidade, a ficha de uma proposta sem anúncio e a `/amostra`: deram 404 na captura (a primeira por falta de dados, a última porque saiu).
- As cinco secções do sistema: dão 403 ao gestor.
- A `/ajuda`, as `/configuracoes/documentos` e a `/plataforma/erros`.
- O Hoje com tarefas e as Propostas com linhas: a empresa 2 não tem nenhuma, por isso isto lê-se no código.
- Os tamanhos de alvo foram **calculados a partir do CSS, não medidos num browser**.
- O tema escuro.

Legenda: ✓ cumpre · ⚠ cumpre em parte · ✗ falha · — não se aplica.

## Tabela-resumo

| Ecrã | Fitts | Hick | Zeigarnik | Jakob | Goal gradient | Von Restorff | Miller |
|---|---|---|---|---|---|---|---|
| Hoje `/` | ⚠ | ✓ | ✓ | ✓ | ✓ | ⚠ | ✓ |
| Situação `/situacao` (3 abas) | ✓ | ✓ | ✓ | ⚠ | ✓ | ✓ | ✗ |
| Concursos `/concursos` | ⚠ | ✗ | ✓ | ⚠ | ✓ | ✗ | ✓ |
| Propostas `/propostas` (código) | ⚠ | ⚠ | ✓ | ⚠ | ⚠ | ✗ | ⚠ |
| Calendário | ✓ | ✓ | ✗ | ⚠ | — | ✓ | ✓ |
| Ficha do anúncio | ⚠ | ⚠ | ✓ | ✓ | ✓ | ✗ | ⚠ |
| Nova proposta | ✓ | ✓ | — | ⚠ | ✓ | ✓ | ✓ |
| Mercado (contratos, fim, resumo) | ✓ | ⚠ | — | ✗ | — | ✗ | ✓ |
| Entidades (5 abas) | ⚠ | ⚠ | ⚠ | ⚠ | ⚠ | ⚠ | ⚠ |
| Configurações › Conta | ✓ | ⚠ | ✓ | ⚠ | — | ✗ | ✗ |
| Configurações › Perfil | ✓ | ⚠ | ✓ | ✓ | — | ⚠ | ✗ |
| Configurações › Alertas | ✓ | ⚠ | ✓ | ✓ | — | ✗ | ⚠ |
| Configurações › Importar | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Barra de cima e barra de baixo | ⚠ | ⚠ | ⚠ | ✓ | — | ✓ | ✓ |
| Entrar | ✓ | ✓ | — | ⚠ | — | ✓ | ✓ |
| Código do segundo factor | ✓ | ✓ | — | ✓ | — | ✓ | ✓ |
| Convite e repor | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ |
| Plataforma `/plataforma` | ⚠ | ✓ | ✓ | ⚠ | — | ⚠ | ✓ |
| Plataforma › empresa | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| Pedidos de acesso e aceitar | ⚠ | ✓ | ✓ | ⚠ | ✓ | ⚠ | ⚠ |
| Site `site/index.html` | ⚠ | ✓ | — | ✓ | ✓ | ✓ | ✓ |
| Site: termos, privacidade, acessibilidade | ✓ | ✓ | — | ✓ | — | ✓ | ⚠ |
| E-mail do resumo diário | ⚠ | ✓ | ⚠ | ✓ | — | ✓ | ⚠ |
| E-mail do convite | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Erros 403 e 404 | ✓ | ✓ | — | ✓ | — | ✓ | ✓ |

Totais das 25 linhas (175 células): **12 ✗ · 45 ⚠ · 97 ✓ · 21 —**. Cinco leis têm pelo menos um ✗:

| Lei | ✗ | ⚠ |
|---|---|---|
| Von Restorff | 6 | 5 |
| Miller | 3 | 7 |
| Hick | 1 | 8 |
| Zeigarnik | 1 | 3 |
| Jakob | 1 | 10 |
| Fitts | 0 | 10 (quase todos no telemóvel) |
| Goal gradient | 0 | 2 |

---

## 1. Fitts — a acção principal é grande, perto e visivelmente principal; 24 px no rato, 44 px no dedo

**F1. A triagem no telemóvel fica nos 32 px** — Concursos, Propostas, e a caixa ✓ do Hoje. Gravidade **alta**.
- **O que acontece:** a acção de todos os dias (Interessa / Abandonar) é um `mg-btn--sm`, e no toque só sobe para 32 px. Há 20 linhas × 2 botões.
- **Prova:** `estilo/miragov-radar.css:713-715`, dentro de `@media (pointer:coarse)`: `.mg-btn{min-height:44px}` e `.mg-btn--sm{min-height:32px}`. No `/concursos` há `<button ... class='mg-btn mg-btn--sm mg-btn--success'>✓ Interessa</button>`.
- **Os outros alvos abaixo de 44 px no toque:**
  - a caixa ✓ da tarefa (`.chk`, 24×24, `miragov-radar.css:701`): o comentário do mesmo ficheiro cita «risquei a de baixo por engano»;
  - a paginação (32 px, `:693`);
  - o «×» do aviso (32 px);
  - o «Mudar» do selector da ranhura (`mg-btn--sm`);
  - as abas `.mg-tab`: padding de 6 px e letra de 13 a 14 px dão cerca de 32 px (estimado).
- **Correcção:** no `@media (pointer:coarse)`, levar aos 44 px o `.col-acc .mg-btn--sm`, o `.mg-tab`, o `.mg-pager>*` e o `.chk`.
- **Cabe antes de 5/10?** Sim: é CSS; a linha da tabela fica mais alta no telemóvel.

**F2. Na ficha, o botão cheio é o secundário** — `/anuncio/<ref>` de um concurso por ver. Gravidade **média**.
- **O que acontece:** a decisão (Interessa / Abandonar) está no cabeçalho, perto do título, e isso está bem; mas os botões são de contorno. O único botão cheio visível é «Trazer peças», no terceiro cartão, depois de duas tabelas do Mercado. E a própria ficha diz «[as peças] vêm sozinhas ao marcar interessa».
- **Prova:** `<button type='submit' class='mg-btn mg-btn--sm mg-btn--primary'>[svg] Trazer peças</button>`, com `<p class='ficha-nota'>Ainda não foram trazidas. Vêm sozinhas ao marcar «interessa».</p>` por baixo.
- **Correcção:** «Trazer peças» passa a `mg-btn--secondary` enquanto o anúncio não tem proposta.
- **Cabe antes de 5/10?** Sim.

**F3. «comparar as marcadas» só existe depois da 60.ª linha** — Entidades › Contratos a acabar. Gravidade **média**.
- **O que acontece:** 60 linhas com caixa de marcar; o botão, e a instrução «Marque duas», só aparecem no fim da tabela.
- **Prova:** `/entidades?ver=acabar`, 61 `<tr>`; `<div class='tab-pe'><button ...>comparar as marcadas</button><span class='nota'>Marque duas. …`.
- **Correcção:** o mesmo botão e a mesma instrução também por cima da tabela.
- **Cabe antes de 5/10?** Sim, é HTML (o contador «1 de 2» fica para depois, porque pede JS).

**F4. No site, os dois alvos do topo são pequenos no telemóvel** — `site/index.html`. Gravidade **baixa**.
- **O que acontece:** abaixo de 860 px o `.ligacao` esconde-se e ficam «Entrar» e «Pedir acesso».
- **Prova, calculada a partir do CSS e não medida:**
  - «Entrar»: `padding:6px 2px`, letra de 0,95 rem, cerca de 30 a 34 px (`moldura.css:48`);
  - «Pedir acesso»: `.btn-pequeno` com `padding:8px 14px`, cerca de 35 px (`moldura.css:39`).
- **Correcção:** `min-height:44px` nos dois dentro de `@media (max-width:860px)`.
- **Cabe antes de 5/10?** Sim.

**F5. «Verificar agora» está no fim da página do dono** — `/plataforma`. Gravidade **baixa**.
- **O que acontece:** é o único gesto de reparação que o semáforo «Recolha» pede, e está no fundo da página, num `bt-leve`.
- **Prova:** `radar.py`, `administracao_da_plataforma()`: `accao("/verificar", … "bt-leve", …)` dentro do cartão «Recolha», o penúltimo bloco.
- **Correcção:** quando o semáforo da Recolha está «mau», o botão sobe para dentro do bloco «A tratar hoje».
- **Cabe antes de 5/10?** Não, não é urgente.

**F6. Recusar um pedido obriga a escrever dentro da célula** — `/pedidos-de-acesso`. Gravidade **baixa**.
- **O que acontece:** o campo «motivo» e o «recusar» estão na célula «Decisão», ao lado de «aceitar…».
- **Prova:** `pedidos_de_acesso()`, a função `decisao()`.
- **Correcção:** «recusar…» abre o mesmo passo que o «aceitar…».
- **Cabe antes de 5/10?** Não.

**O que está bem:**
- A barra de baixo tem alvos de 60 px e o menu «Mais» tem itens de 48 px (`:846`, `:860`).
- No toque, o `mg-btn` tem 44 px.
- A etiqueta «Pedir acesso» repete-se cinco vezes no site, sempre a mesma acção.
- O e-mail do convite tem um botão único de cerca de 39 px («Criar a conta»).
- A regra dos 24 px no rato (`TestAlvosDeTextoA24px`) continua de pé. A auditoria de 02/09 disse que os 44 px não se aplicavam «porque nenhum ecrã é para telemóvel»; **isso deixou de ser verdade com a D9** (a barra de baixo), por isso os 44 px contam agora.

## 2. Hick — quantas escolhas de cada vez

**H1. Concursos: a triagem tem por cima um formulário de 8 campos** — `/concursos`. Gravidade **alta**.
- **O que está à vista no computador, antes da primeira linha:**
  - 3 abas;
  - 8 campos: Pesquisar, Entidade, Plataforma (7 opções), duas datas, Distrito (21 opções), dois preços;
  - Filtrar e Limpar;
  - Exportar CSV.
- **Na página inteira:** 53 botões, 68 ligações, 10 campos e 2 selects com 28 opções.
- **Prova:** `<form class='mg-card filtros' id='filtros-lista'>` com 8 `mg-field`. O «Mais filtros» existe, mas só se vê abaixo de 600 px (`miragov-radar.css:1200-1203`).
- **O que já se decidiu:** a UX-Auditoria de 02/09 propôs recolher os filtros (P2), recolheram-se de 8/09 a 24/09, e **voltaram a estar à vista a 24/09 com o `EcraConcursos`** (armadilhas, «A árvore dos CPV da lista»). Voltou por decisão, não por descuido.
- **Correcção:** no computador, à vista só a Pesquisa, a Entidade e o «Mais filtros»; o resto abre com ele (o mecanismo do telemóvel já existe), e abre sozinho quando há filtro aplicado.
- **Cabe antes de 5/10?** **Não**: contraria o `EcraConcursos` e pede a palavra dele.

**H2. Configurações › Conta: seis assuntos e dois caminhos para a mesma coisa** — `/configuracoes/conta`. Gravidade **média**.
- **O que tem:** 6 formulários, 13 campos, 7 botões.
- **Dois caminhos para acrescentar um colega:**
  - «Criar convite» (e-mail + papel);
  - «Ou criar a conta já, com a palavra-passe» (utilizador + palavra-passe + papel).
- **Correcção:** o segundo caminho fica recolhido num `<details>` «criar sem convite»; o convite fica como o caminho.
- **Cabe antes de 5/10?** Sim.

**H3. Há três sítios para ir parar à ficha de uma entidade** — Mercado. Gravidade **média**.
- **Os três:**
  - o campo «Entidade que comprou» do filtro;
  - o formulário «Ficha de uma entidade: [Nome ou NIF] Abrir», no pé do mesmo cartão;
  - a aba Entidades, que abre outro campo «Nome ou NIF» com o botão primário «Abrir a ficha».
- **Prova:** `/contratos`, `<form class='procura-entidade' … action='/entidade/procurar'>`; `/entidades`, `<form class='mg-card filtros' … action='/entidade/procurar'>`.
- **Correcção:** o formulário do pé do cartão sai do Mercado; fica a aba Entidades.
- **Cabe antes de 5/10?** Sim.

**H4. Nas Propostas, cada linha tem um selector de 9 opções** — `/propostas`. Gravidade **baixa**.
- **O que acontece:** o selector traz as 8 ranhuras e «voltar a Por ver», com o botão «Mudar». As 8 abas são decisão dele e ficam.
- **Prova:** `selector_de_ranhura()`: 8 `<option>` de `ESTADOS_DA_EMPRESA` mais uma.
- **Correcção:** um botão «→ A preparar» (a ranhura seguinte) ao lado do selector, porque é o gesto de quase sempre.
- **Cabe antes de 5/10?** Não, pede decisão.

**H5. O «Mais» do telemóvel tem duas entradas para o mesmo endereço** — barra de baixo. Gravidade **baixa**.
- **O que acontece:** «Configurações» e «A conta» abrem os dois `/configuracoes/conta`. São 6 escolhas quando bastavam 5.
- **Prova:** `barra_de_baixo()`: `do_menu("/configuracoes/conta", "Configurações", …)` e, logo abaixo, `do_menu("/configuracoes/conta", "A conta", "utilizador")`.
- **Correcção:** tirar «A conta» do «Mais».
- **Cabe antes de 5/10?** Sim.

**H6. Entidades: duas ligações por linha para o mesmo sítio** — `/entidades`. Gravidade **baixa**.
- **O que acontece:** o nome da entidade e o «abrir» levam os dois a `/entidade/<chave>`. São 60 linhas, 142 ligações.
- **Correcção:** tirar a coluna «abrir».
- **Cabe antes de 5/10?** Sim.

**H7. Perfil e Alertas: a árvore dos CPV (9 454 códigos) abre-se sozinha** — Configurações › Perfil. Gravidade **baixa**.
- **Prova:** `<details class='arvore' … open>` no Perfil; nos Alertas vem fechada.
- **Correcção:** no Perfil, abre fechada quando o perfil já tem CPV («Em vigor: 72000000»).
- **Cabe antes de 5/10?** Sim.

**O que está bem:**
- O Hoje tem 4 indicadores e uma fita de 7 dias.
- A Situação tem 3 abas e 4 períodos.
- O Calendário tem 3 filtros (eram 11 abas).
- Nas perguntas do site, as 9 respostas vêm fechadas em `<details>`.
- O formulário do site tem 5 campos e o sector 5 opções.
- O diálogo do motivo tem 4 ou 5 botões que gravam num clique.

## 3. Zeigarnik — o que está por acabar vê-se e puxa a acabar

**Z1. O Calendário de uma empresa nova abre vazio** — `/calendario`. Gravidade **média**.
- **O que acontece:** o filtro por omissão é «As nossas», que tem 0. A grelha de 42 dias abre vazia e não diz nada, com «Por ver 49» na aba ao lado.
- **Prova:** `<a class='mg-tab' aria-current='page' href='/calendario'>As nossas <span class='mg-tab__count'>0</span>`; não há nenhum `mg-empty` no ecrã.
- **Correcção:** quando «As nossas» dá 0, uma linha na `cal-legenda`: «Nada vosso nestas seis semanas. Há 49 por ver com prazo aqui →».
- **Cabe antes de 5/10?** Sim.

**Z2. Fora do Hoje nada lembra as tarefas atrasadas** — barra de cima e de baixo. Gravidade **média**.
- **O que acontece:** a marca é o Hoje (decisão dele) e não tem contador; nas Propostas, no Mercado ou no Calendário, as atrasadas não se vêem.
- **Correcção:** o número de atrasadas no `<title>` da página («(2) Concursos · Mira Gov»), que é a convenção do Gmail e não mexe na marca.
- **Cabe antes de 5/10?** Não: pede uma consulta em cada página.

**Z3. «Marque duas», sem dizer quantas faltam** — Entidades. Gravidade **baixa**.
- **Correcção:** um contador «1 de 2 marcadas» ao lado do botão.
- **Cabe antes de 5/10?** Não (JS).

**Z4. O resumo diário não diz o que fica por decidir no painel** — e-mail. Gravidade **baixa**.
- **O que acontece:** lista o que entrou nos alertas, mas não quantos concursos continuam por ver.
- **Prova:** `html_do_resumo()`: o cabeçalho é «N anúncios novos nos seus alertas · …».
- **Correcção:** uma linha «e N por decidir no Mira Gov», com a ligação.
- **Cabe antes de 5/10?** Não, não é urgente.

**O que está bem:**
- No Hoje:
  - o cartão «Pôr a empresa a trabalhar» diz «3 de 4 feitos; falta 1» (`<p class='mg-card__meta'>3 de 4 feitos; falta 1</p>`);
  - os baldes têm contadores, e as atrasadas contam-se;
  - «Paradas há mais tempo».
- Nas Propostas, a coluna «Falta» mostra a tarefa seguinte.
- Na ficha:
  - «Falta decidir.»;
  - «Documentos da proposta — X de Y prontos» (`_documentos_da_proposta_html()`).
- Todas as abas têm contagem.
- Nos Alertas, «0 por avisar · 19 avisados».
- Na página do dono, o bloco «A tratar hoje».

## 4. Jakob — as convenções dos outros produtos

**J1. Não há pesquisa geral nem Ctrl+K, e a pesquisa dos Concursos fica presa à aba** — todo o painel. Gravidade **média**.
- **O que acontece:**
  - não há pesquisa na barra de cima nem nenhum atalho global;
  - a caixa «Pesquisar» dos Concursos leva `<input type='hidden' name='estado' value='porver'>`: procurar a referência de um concurso já triado a partir do «Por ver» dá 0. As contagens das abas dentro do filtro atenuam isto.
- **Prova:** no `radar.py`, o único `ctrlKey` é a guarda do `j k i a` (`:17713`).
- **Correcção:** uma caixa de pesquisa na barra de cima que procura em «Todos» e nas Propostas, com «/» ou Ctrl+K para a focar.
- **Cabe antes de 5/10?** Não.

**J2. A aba Entidades faz desaparecer a barra de abas de onde se veio** — Mercado. Gravidade **média**.
- **O que acontece:**
  - nos Concursos e nas Propostas as abas estão por cima do filtro; no Mercado as 3 abas («Por celebração · Por fim estimado · Entidades») estão **por baixo** do cartão do filtro e da linha da contagem;
  - carregar em «Entidades» leva a uma página sem essas 3 abas, com outro cabeçalho e outras 5 abas. Uma aba que tira a própria barra de abas não se comporta como uma aba.
- **Prova:** `/contratos`: `<nav class='mg-tabs' aria-label='Vistas do Mercado'>` depois de `<div class='mercado-resumo'>`. O `/entidades` não tem esse `nav`.
- **Correcção:**
  - as 3 abas do Mercado sobem para logo a seguir ao cabeçalho, como nos Concursos;
  - o `/entidades` desenha-as por cima das suas 5.
- **Cabe antes de 5/10?** Não (três páginas).

**J3. Há dois moldes de cabeçalho, e num deles o título está dentro de um `<summary>`** — Situação ×3, Nova proposta, Entidades ×3, Plataforma, 403. Gravidade **média**.
- **O que acontece:**
  - 14 dos 31 ecrãs com resposta usam `cabecalho_de_pagina()` (`mg-pagehead`);
  - 8 usam o `TOPO` antigo (`mg-crumbs migalhas` e `<details class='mg-disc porque'><summary><h1>…`): carregar no título abre um texto. Mais 5 (os 403) usam as mesmas migalhas sem o `<details>`.
- **Prova:** contagem por ficheiro dos dois moldes; `/situacao`: `<details class='mg-disc porque'><summary><h1 class='mg-pagehead__title'>Ponto de situação</h1><i aria-hidden='true' title='O que é esta página'>?</i>`.
- **Correcção:** passar a Situação, as Entidades, a Nova proposta e a Plataforma para `cabecalho_de_pagina()`, com o texto como `sub`.
- **Cabe antes de 5/10?** Não (4 rotas, mais os testes que procuram a marcação).

**J4. Só se ordena por uma coluna, e só nos Concursos** — Mercado, Entidades, Propostas, Plataforma. Gravidade **média**.
- **O que acontece:** há `th a.ordenar` só no «Prazo» dos Concursos (30/09). O Mercado (Preço, Celebrado), as Entidades (Compra, Ganha, A acabar) e as Propostas (Prazo, Preço) não ordenam.
- **Correcção:** o mesmo `?ordem=` nos cabeçalhos numéricos dessas tabelas.
- **Cabe antes de 5/10?** Não.

**J5. O Calendário mostra 6 semanas e anda de 1 em 1** — `/calendario`. Gravidade **baixa**.
- **O que acontece:** os botões «‹ Semana» e «Semana ›» andam uma semana, numa vista de seis. A convenção do Google e do Outlook é andar o tamanho da vista.
- **Correcção:** ou «‹ 6 semanas», ou ficar como está e dizê-lo no rótulo.
- **Cabe antes de 5/10?** Não, não é urgente.

**J6. As datas são texto dd/mm/aaaa, sem calendário para escolher** — filtros, adiar a tarefa, o motivo, os alertas. Gravidade **baixa**.
- **O que se sabe:** há `inputmode='numeric'` e um padrão que o valida, o que já é uma escolha da casa.
- **Correcção:** `type=date` nos filtros, deixando o texto como está onde o formato se escreve à mão.
- **Cabe antes de 5/10?** Não.

**J7. Não há «Esqueci-me da palavra-passe» por conta própria** — `/entrar`. Gravidade **baixa**.
- **O que acontece:** o ecrã diz «Peça ao gestor da sua empresa uma ligação» (D17, decisão dele).
- **Correcção:** fica como está até haver correio fiável; depois, uma ligação que manda a reposição por e-mail.
- **Cabe antes de 5/10?** Não.

**J8. A ligação do convite aceite não tem botão «Copiar»** — aceitar pedido, e o convite nas Configurações. Gravidade **baixa**.
- **Prova:** `aceitar_pedido()`: `<p><code>%s</code></p>`.
- **Correcção:** um botão «Copiar» com `navigator.clipboard`.
- **Cabe antes de 5/10?** Sim.

**O que está bem:**
- O menu da conta está no canto (avatar) e tem «Sair».
- Há migalhas na ficha.
- O código do segundo factor tem `autocomplete="one-time-code"` e `inputmode="numeric"`.
- O «Hoje» do Calendário existe.
- O site tem «Entrar» no topo.
- A tecla Esc fecha os menus.
- Os e-mails dizem porque se recebem e têm «Mudar os alertas».

## 5. Goal gradient — sentir quanto falta

**G1. Na lista das Propostas não se vê quanto falta a cada uma** — `/propostas`. Gravidade **média**.
- **O que acontece:** a ficha tem o stepper de 4 passos e «Documentos da proposta — X de Y prontos». A lista só mostra a tarefa seguinte; o «3 de 7 prontos» fica dentro da ficha.
- **Prova:** `linha_da_pipeline()`: a célula «Falta» é só `falta["o_que"]`.
- **Correcção:** na coluna «Falta», juntar «docs 3/7» quando o Programa já foi lido.
- **Cabe antes de 5/10?** Não (uma consulta por lista).

**G2. Entidades: comparar precisa de duas marcadas e o ecrã não conta** — ver Z3. Gravidade **baixa**.

**O que está bem:**
- O arranque «3 de 4» encurta para só o que falta.
- A ficha tem o stepper de 4 fases (`mg-stepper ficha-escada`).
- Os documentos da proposta dizem «X de Y».
- O Importar tem os passos «1. O modelo» e «2. O ficheiro preenchido».
- O e-mail do convite tem «O que vem a seguir», numerado.
- O site tem «Três passos, e o primeiro é o único que dá trabalho», e o formulário, depois de enviado, diz o que vem a seguir.
- A taxa da Situação diz quantas decididas faltam para aparecer.
- A aba «Por ver» desce um a cada triagem, sem recarregar.

## 6. Von Restorff — só se destaca o que importa

**V1. Concursos: 59 elementos com cor em 20 linhas, e o «Abandonar» tem a cor da urgência** — `/concursos`. Gravidade **alta**.
- **O que se contou:**
  - 20 botões «Interessa» `mg-btn--success`, de contorno verde;
  - 20 botões «Abandonar» `mg-btn--warning`, de contorno laranja;
  - 11 etiquetas verdes («14 dias», e as outras de prazo folgado);
  - 8 etiquetas laranja («5 dias», e as outras urgentes).
- **O que isso faz:** as 8 etiquetas que pedem atenção têm **o mesmo laranja** que os 20 botões «Abandonar».
- **Isto voltou:** a 02/09 o «abandonar» tinha «contorno cinzento» (UX-Auditoria, Parte 1).
- **Prova:** contagem no `/concursos`: `mg-btn--success` 20, `mg-btn--warning` 20, `mg-tag--success` 11, `mg-tag--warning` 8.
- **Correcção:** o «Abandonar» volta a neutro (`mg-btn--secondary`; o «✕» diz o que é).
- **Cabe antes de 5/10?** Sim: é uma palavra no molde da linha (e o do cabeçalho da ficha).
- **Fica por decidir:** as etiquetas verdes do prazo folgado ficaram «manter» a 02/09; torná-las neutras é decisão dele.

**V2. Várias acções principais no mesmo ecrã.** Gravidade **média**. Correcção: um primário por ecrã e o resto `secondary`. Cabe antes de 5/10: sim, em cada caso.

| Ecrã | Botões `mg-btn--primary` à vista | Quais | Qual fica primário |
|---|---|---|---|
| Configurações › Conta | 5 | Guardar · Guardar o aspecto · Guardar · Criar convite · Criar utilizador | «Criar convite» (é para ele que o arranque aponta, `#convidar`) |
| Configurações › Alertas | 4 (mais 1 dentro de um `<details>`) | Criar o alerta do perfil · Criar alerta · Guardar · Guardar | «Criar alerta» |
| Propostas | 2 | Nova proposta · Filtrar | «Nova proposta» |
| Perfil | 2 | Guardar o perfil · Guardar as listas | «Guardar o perfil» |

**V3. A ficha diz o prazo três vezes a laranja** — ficha do anúncio. Gravidade **média**.
- **As três vezes:**
  - a etiqueta «Faltam 8 dias» por baixo do título;
  - «Faltam 8 dias» nos factos;
  - o cartão «Prazo», com «8 dias» e mais uma etiqueta de aviso.
- **Mais laranja no mesmo ecrã:** o alerta «Falta decidir.» (`mg-alert--warning`) e o «Abandonar». São 5 elementos laranja para dois factos.
- **Correcção:** tirar a etiqueta do cartão «Prazo» (que já é o número grande), e o «Falta decidir» passa a `mg-alert--info`.
- **Cabe antes de 5/10?** Sim.

**V4. Mercado: «Concorrente» está pintado como aviso** — Mercado e o bloco Mercado da ficha. Gravidade **média**.
- **O que acontece:** `/contratos` tem 45 etiquetas `ent-papel` em 20 linhas: «cli» a verde, «conc» a laranja. O laranja é o tom do aviso, e ser concorrente não é um aviso.
- **Prova:** `radar.py:14534-14535`: `.ent-papel.cliente{color:var(--success)…}`, `.ent-papel.concorrente{color:var(--warning)…}`.
- **Correcção:** as duas neutras (`--ink-muted`, com contorno). O texto já diz qual é qual.
- **Cabe antes de 5/10?** Sim.

**V5. A coluna «Falta» das Propostas é toda laranja** — `/propostas`. Gravidade **média**.
- **O que acontece:** o texto de todas as linhas sai a laranja, e a atrasada, que já leva a etiqueta vermelha «atrasada · data», perde o destaque.
- **Prova:** `radar.py`, no CSS: `.tab-lista td.falta{color:var(--warning);…}`.
- **Correcção:** `color:var(--ink)`, e a cor fica só para a etiqueta da atrasada.
- **Cabe antes de 5/10?** Sim.

**V6. Hoje: vermelho sem razão à vista, com um texto técnico por trás** — `/`. Gravidade **média**.
- **O que acontece:**
  - «desde a última verificação, 20:00» sai a vermelho;
  - a razão só aparece ao passar o rato, e é para o dono («o DR não aceitou a pesquisa (apiVersion) … ver amostras/resposta_inesperada.txt e refaz a captura»);
  - quem vê isto é o gestor de uma empresa cliente, que não pode fazer nada;
  - por cima, o subtítulo diz «Última verificação às 20:00: 4 anúncios novos», em tom normal;
  - o feed tem 4 etiquetas laranja «prazo alterado».
- **Prova:** `<span title='30/09/2026 20:00 — o DR não aceitou a pesquisa …' class='mau'>`; `radar.py:34718`.
- **Correcção:** o vermelho e a dica técnica só para o dono (`sou_dono()`); para os outros, em tom neutro.
- **Cabe antes de 5/10?** Sim.

**V7. Mercado › Por fim estimado: 20 datas iguais a negrito** — `/contratos?ver=fim`. Gravidade **baixa**.
- **Prova:** 20 `<b>30/09/2026</b>` com «hoje» por baixo; na página há 25 negritos.
- **Correcção:** tirar o `<b>` da data.
- **Cabe antes de 5/10?** Sim.

**V8. Uma etiqueta verde «activa» por empresa, e um «aceitar…» primário por pedido** — Plataforma e pedidos de acesso. Gravidade **baixa**.
- **Correcção:**
  - «activa» neutra, e só a «suspensa» com cor;
  - «aceitar…» secundário, com os pendentes agrupados no topo (ver M5).
- **Cabe antes de 5/10?** Sim.

**O que está bem:**
- No Hoje, com dados vazios, só há um botão cheio à vista («ver os 57 por decidir»).
- No Calendário, a urgência vai num ícone e não só na cor.
- Nos Concursos, o «Filtrar» é o único primário à vista.
- As etiquetas de perigo e de aviso levam sinal além da cor.
- O site tem um só CTA, repetido.

## 7. Miller — agrupar, fatiar, uma decisão de cada vez

**M1. A Situação mostra a mesma coisa duas e três vezes** — `/situacao`. Gravidade **alta**.
- **O que se repete na aba Negócio:**
  - «Por submeter» e «Em jogo» aparecem 3 vezes: como indicador, como cartão (`#em-analise`, `#entregues`) e como barra;
  - as 4 fases abertas aparecem em **dois** gráficos de barras na mesma página: «Abertas, por fase», com 4 barras, e «Propostas por fase», com 8 barras que incluem as mesmas 4.
- **O total:** 5 indicadores, 4 cartões e 6 subtítulos (a `mg-field__label`).
- **Prova:** `/situacao`: `<div class='mg-field__label' id='em-jogo' …>Abertas, por fase</div>` e, mais abaixo, `<div class='mg-field__label' …>Propostas por fase</div>`, os dois com `href='/propostas?estado=analisar'`.
- **Correcção:** tirar o gráfico «Abertas, por fase», porque o de 8 barras já o contém.
- **Cabe antes de 5/10?** Não sem a palavra dele. Técnicamente cabe (é apagar um bloco), mas é a página do negócio e o `id='em-jogo'` tem de se confirmar.

**M2. Configurações › Conta: seis assuntos num cartão só** — `/configuracoes/conta`. Gravidade **média**.
- **Os seis:** a palavra-passe, as sessões, o aspecto, a nossa empresa (nome e NIF), os utilizadores com o convite, e os acessos do suporte.
- **O índice ao lado** diz «palavra-passe, sessões, a nossa empresa, utilizadores»: os dados da empresa e a equipa vivem dentro da «Conta» pessoal.
- **Correcção:** partir em três cartões — «A minha conta», «A empresa e a equipa», «Registo do suporte».
- **Cabe antes de 5/10?** Não.

**M3. Perfil da empresa: 20 distritos soltos** — Configurações › Perfil, e o aceitar pedido. Gravidade **média**.
- **O que acontece:** 20 caixas de marcar seguidas, sem grupo. Nos Alertas estão dentro de um `<details>`, o que está bem.
- **Correcção:** agrupar pelas 7 NUTS II (Norte, Centro, Lisboa, Alentejo, Algarve, Açores, Madeira), cada grupo com «todos».
- **Cabe antes de 5/10?** Não.

**M4. Tabelas de 9 colunas sem paginação** — Entidades e Propostas. Gravidade **média**.
- **Entidades › Contratos a acabar:** 60 linhas de uma vez, 9 colunas (caixa, entidade, papel, compra, ganha, connosco, taxa, a acabar, abrir).
- **Propostas:** até 9 colunas (Ref.ª, Objecto, Lote, Resp., Preço base, Proposto, Prazo, Estado, Falta).
- **Correcção:**
  - nas Entidades, paginar a 20 como o Mercado, e tirar «abrir» (H6);
  - nas Propostas, «Lote» só aparece quando alguma linha o tem.
- **Cabe antes de 5/10?** Não.

**M5. Pedidos de acesso: os pendentes misturados com os decididos** — `/pedidos-de-acesso`. Gravidade **baixa**.
- **Prova:** `ORDER BY id DESC LIMIT 500`, numa tabela de 8 colunas.
- **Correcção:** os pendentes num cartão em cima, e os decididos por baixo.
- **Cabe antes de 5/10?** Sim.

**M6. O resumo por e-mail não tem tecto** — e-mail. Gravidade **baixa**.
- **Prova:** `html_do_resumo()` põe todos os anúncios de cada alerta, sem limite.
- **Correcção:** mostrar os primeiros 10 por alerta e «mais N no Mira Gov», com a ligação.
- **Cabe antes de 5/10?** Não, não é urgente.

**M7. Ficha: 9 entradas no índice e 6 de 8 factos vazios** — `/anuncio/<ref>`. Gravidade **baixa**.
- **O que acontece:**
  - 9 entradas no índice e 9 cartões;
  - num concurso por ver, 6 dos 8 factos dizem «o anúncio não indica» ou «consta do Programa do Concurso».
- **Isto já se decidiu:** o achado «o essencial diz sobretudo o que falta» (02/09) voltou em parte. É atenuado pela classe `apagado`, e a ficha nova de 28/09 fê-lo de propósito (armadilhas, «Os filtros da lista…»).
- **Correcção:** nenhuma antes de 5/10; ver com ele.

**M8. As páginas legais não têm índice** — termos. Gravidade **baixa**.
- **O que acontece:** 10 secções `<h2>` nos termos e 9 na privacidade, sem índice. Lê-se bem na mesma.
- **Correcção:** nenhuma antes de 5/10.

**O que está bem:**
- O Hoje tem baldes com tecto e «mais N».
- Os filtros estão agrupados num cartão.
- O «Anúncio completo (8 secções)» vem fechado.
- O resumo do mercado tem 7 gráficos, cada um no seu cartão.
- A barra de baixo tem 4 entradas e um «Mais».
- A página do dono segue a ordem da manhã (semáforos → a tratar → empresas → sistema).

---

## As 10 correcções que mais valem, por ordem

Todas cabem em menos de meia hora, e todas esperam o sim dele antes de se tocar no código.

1. **O «Abandonar» volta a neutro** (V1). Tira 20 laranjas do ecrã de todos os dias, e o laranja volta a querer dizer urgência. Era cinzento a 02/09.
2. **Alvos de 44 px no toque** (F1): os botões da triagem, as abas, a paginação e a caixa ✓ das tarefas, num `@media (pointer:coarse)`.
3. **Um só primário por ecrã** (V2, F2): Conta 5→1, Alertas 4→1, Propostas 2→1, Perfil 2→1, e o «Trazer peças» passa a secundário na ficha por ver.
4. **O Calendário vazio diz porquê e aponta os 49 por ver** (Z1). É o primeiro contacto de uma empresa nova.
5. **O vermelho do «O que mudou» só para o dono** (V6). Para o gestor o texto sai neutro, sem a dica técnica.
6. **As etiquetas cli/conc passam a neutras** (V4). Tira 45 cores por página do Mercado.
7. **A coluna «Falta» das Propostas sem laranja**, fora a atrasada (V5).
8. **A ficha diz o prazo a laranja uma vez**, e o «Falta decidir» passa a info (V3).
9. **«comparar as marcadas» também por cima da tabela das Entidades** (F3).
10. **Sai o «A conta» do «Mais»** (H5), **sai o formulário repetido de ficha de entidade do Mercado** (H3), e **sai o negrito das 20 datas iguais** (V7).

## O que NÃO se deve fazer antes de 5/10

- **Recolher os filtros dos Concursos no computador** (H1). Contraria o `EcraConcursos` de 24/09 e muda o primeiro ecrã: pede decisão.
- **Tornar neutras as etiquetas verdes de prazo folgado** (V1, segunda parte): foi «manter» a 02/09.
- **Pesquisa geral e Ctrl+K** (J1), **cabeçalhos ordenáveis no Mercado, Entidades e Propostas** (J4), **datas com calendário** (J6).
- **Unificar os dois moldes de cabeçalho** (J3) e **arrumar as abas do Mercado e das Entidades** (J2). Mexe em várias rotas e em testes que procuram a marcação.
- **Tirar o gráfico repetido da Situação** (M1), **partir Configurações › Conta em três cartões** (M2), **agrupar os distritos** (M3), **paginar as Entidades** (M4).
- **Botão «→ ranhura seguinte» nas Propostas** (H4) e **«docs 3/7» na lista** (G1): mudam o gesto da escada.
- **Contador de atrasadas no `<title>`** (Z2): uma consulta em todas as páginas.
- **Repor a palavra-passe por conta própria** (J7): depende do correio e da D17.
- **Mexer nas decisões dele:** o Hoje como marca, os seis itens mais «?», as oito ranhuras, o sistema de desenho, e não se filtrar nada à entrada. Nenhuma correcção acima lhes toca.
