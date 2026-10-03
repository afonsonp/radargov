# Auditoria de UX depois do dia 1/10 — as sete leis em todos os ecrãs

3/10/2026 (capturas de 1/10/2026, e as nove páginas que o #204 e o #205 tocaram refeitas a 3/10 sobre o `master` em `a8f48a4`). Só leitura: nenhum ficheiro do código mudou; isto é o relatório.

Repete as três auditorias de 30/09 (`UX-7-LEIS.md`, `UX-ICONES-DICAS-PESOS.md`, `UX-ECRAS-EM-FALTA-E-ESCURO.md`) depois das correcções de 1/10 (#180, #183, #184, #185, #187) e do que entrou no mesmo dia: os ecrãs dos concorrentes (L5, #186, #198, #204), as condições de pagamento (L4, #203), os planos Solo, Duo e Corporate (#190, #191, #201), a pesquisa geral (#187) e a revisão dos termos (#205). O pedido dele: «as 7 leis têm de funcionar em todo».

## Material e método

- **As bases**: uma cópia do `radar.db` (1,5 GB) e do `contratos.db` (3,4 GB), feita com a API de cópia do SQLite com a origem em `mode=ro`. O `/tmp` desta máquina é um tmpfs de 3,6 GB e não as levava; ficaram em `~/radar-trabalho/bases-auditoria-1-10/`, fora do git, e foram apagadas no fim. A produção não foi tocada.
- **A empresa de teste**, criada **na cópia** pelas funções do radar (`criar_empresa()`, `contas.criar_utilizador()`, `gravar_config()`, `criar_proposta()`, `mover_proposta()`, `gravar_campos_da_proposta()`, `criar_tarefa()`, `gravar_nota()`, `criar_contacto()`, e a rota `/configuracoes/documentos`): «Obras e Serviços Tejo, Lda», perfil CPV 45 + 71 + 90, Lisboa e Setúbal, desde 20 000 €; uma gestora e um utilizador; 7 propostas (Por analisar, A preparar ×2, Submetida, Relatório preliminar, Ganha, Perdida), **uma sem anúncio** (consulta prévia, com prazo de entrega); 12 tarefas (uma atrasada, uma sem dono, duas do cofre); 2 contactos; 2 documentos no cofre.
- **O browser**: o painel do worktree a servir a cópia em `127.0.0.1:8799`, com JavaScript, letras e folhas verdadeiras; o Chromium sem janela de `~/.cache/ms-playwright/chromium_headless_shell-1243`, conduzido pelo playwright do Python (`uv run --with playwright`). **50 rotas** (33 da empresa como gestora, 1 como utilizador, 9 da plataforma como dono, 7 sem sessão: o site, termos, privacidade, acessibilidade, entrar, esqueci-me e um 404), cada uma em claro e em escuro, a 1280 × 900 e a 390 × 844 (com `isMobile` e `hasTouch`, que liga o `pointer:coarse`): **200 capturas de página inteira** e 2 recortes de foco, em `~/radar-capturas/auditoria-1-10/`.
- **O que se mediu em cada página** (guião no browser): botões, ligações, campos, opções, primários, etiquetas e alertas por cor, texto pintado com `--warning`/`--danger`/`--success`, pesos e tamanhos calculados de cada texto (5 796 textos no claro a 1280, 5 812 no escuro), contraste de cada texto contra o fundo efectivo, alvos com `getBoundingClientRect` (abaixo de 24 e de 44 px), rolagem horizontal; e no computador **45 `Tab` por página**, com o contorno do foco e a razão contra o fundo: 2 155 paragens por tema.
- **O código**: `grep` ao `radar.py`, ao `estilo/` e ao `site/` para o que um ecrã com estes dados não mostra.

**O que não se viu**: os e-mails (resumo e convite), o 2.º factor, o convite e o repor; uma falha da verificação (na cópia a recolha estava verde, por isso o V6/B.1 #1 lê-se no código); os «docs 3/7» das Propostas (nenhuma proposta da cópia tem o Programa lido); o tema contraste; estados que pedem gesto (menus abertos, o diálogo do motivo, a lista da pesquisa geral aberta). O dia das capturas mudou de 1/10 para 3/10 nas nove refeitas: as datas relativas («amanhã», «1 atrasada» → «4 atrasadas») diferem entre elas, e isso não é achado.

Legenda: ✓ cumpre · ⚠ cumpre em parte · ✗ falha · — não se aplica. Gravidade: **Alta** (esconde, parte ou contradiz), **Média** (inconsistência que se vê, ou barreira para um grupo), **Baixa** (arrumação). «Cabe» = antes de 5/10, menos de meia hora e sem risco — e, pela regra da casa, nada se faz sem o sim dele.

---

## 1. Tabela-resumo

| Ecrã | Fitts | Hick | Zeigarnik | Jakob | Goal gradient | Von Restorff | Miller |
|---|---|---|---|---|---|---|---|
| Hoje `/` | ⚠ | ✓ | ✓ | ✓ | ✓ | ⚠ | ✓ |
| Situação (3 abas) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Concursos | ⚠ | ✓ | ✓ | ✓ | ✓ | ⚠ | ✓ |
| Propostas | ⚠ | ⚠ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Calendário | ✓ | ✓ | ✓ | ⚠ | — | ✓ | ✓ |
| Ficha do anúncio por ver | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ⚠ |
| Ficha do anúncio com proposta | ⚠ | ✗ | ✓ | ⚠ | ✓ | ✗ | ⚠ |
| Proposta sem anúncio | ⚠ | ⚠ | ✓ | ⚠ | ✓ | ⚠ | ✓ |
| Nova proposta | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ |
| Mercado › contratos e fim estimado | ✓ | ✓ | — | ⚠ | — | ⚠ | ✓ |
| Mercado › resumo | ✗ | ✗ | — | ✗ | — | ✗ | ✗ |
| Mercado › Concorrentes (novo) | ✓ | ✓ | — | ⚠ | — | ✓ | ⚠ |
| Entidades (5 abas) | ✓ | ⚠ | ⚠ | ✗ | ⚠ | ⚠ | ✓ |
| Ficha da entidade | ⚠ | ✓ | — | ✓ | — | ✓ | ✓ |
| Pesquisa geral (nova) | ✓ | ✓ | — | ✓ | — | ✓ | ✓ |
| Configurações › Conta | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| Configurações › Perfil | ⚠ | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| Configurações › Alertas | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| Configurações › Importar | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Configurações › Documentos | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| Ajuda | ✓ | ✓ | — | ✓ | — | ✓ | ✓ |
| Barra de cima e barra de baixo | ⚠ | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| Entrar e «esqueci-me» | ✓ | ✓ | — | ✓ | — | ✓ | ✓ |
| Plataforma `/plataforma` | ⚠ | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| Plataforma › empresa e erros | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| Pedidos de acesso | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Configurações do sistema (5) | ✓ | ✓ | — | ✓ | — | ⚠ | ✓ |
| Site `/` | ✓ | ✓ | — | ✓ | ✓ | ⚠ | ✓ |
| Termos, privacidade, acessibilidade | ✓ | ✓ | — | ✓ | — | ✓ | ⚠ |
| Erros 403 e 404 | ✓ | ✓ | — | ✓ | — | ✓ | ✓ |

Totais das 30 linhas (210 células): **8 ✗ · 30 ⚠ · 142 ✓ · 30 —**.

A 30/09 eram 25 linhas (175 células): 12 ✗ · 45 ⚠ · 97 ✓ · 21 —. Dos 8 ✗ de hoje, **5 são de uma página só**, o resumo do Mercado, que deixou de abrir (N1); os outros 3 são as Entidades/Jakob (o J2, que **voltou**) e a ficha com proposta (Hick e Von Restorff; a 30/09 tinha o ✗ de Von Restorff na auditoria dos ecrãs em falta). Sem o resumo, os ✗ passam de 12 a 3.

| Lei | ✗ | ⚠ | Onde estão os ✗ |
|---|---|---|---|
| Von Restorff | 2 | 7 | resumo; ficha com proposta (5 primários) |
| Jakob | 2 | 5 | resumo; Entidades (as abas do Mercado tapadas) |
| Hick | 2 | 3 | resumo; ficha com proposta (12 controlos nas tarefas) |
| Fitts | 1 | 9 | resumo |
| Miller | 1 | 4 | resumo |
| Goal gradient | 0 | 1 | — |
| Zeigarnik | 0 | 1 | — |

**Contraste e foco, os dois temas, em números:**

| | Claro | Escuro |
|---|---|---|
| Páginas medidas (× 2 larguras) | 50 | 50 |
| Textos abaixo do limiar | 2 por página no Hoje (as iniciais «MR»/«JC» da pílula «as minhas», **1,68:1**), 0 nas outras | os mesmos 2, a **1,30:1** |
| O texto mais baixo que passa, fora do Hoje | 4,74:1 | 4,69:1 |
| Páginas com rolagem horizontal | 0 de 100 | 0 de 100 |
| Paragens de `Tab` medidas | 2 155 | 2 155 |
| Sem contorno nem anel | 1 (o campo da hora dos Alertas: o browser desenha o foco dentro) | 1 (o mesmo) |
| Contorno abaixo de 3:1 | 53 no site, termos, privacidade, acessibilidade e entrar (magenta a **2,36:1** na barra azul) + 74 na pesquisa da barra (contorno `--brand` sobre a barra `--brand`, **1:1**, mas com um anel claro de 4 px que se vê: passa pelo anel) | os mesmos 53; a pesquisa passa (o `--brand` do escuro é claro) |

---

## 2. Os achados das auditorias de 30/09: ficou resolvido ou voltou?

**Conta:** dos 30/09 conferiram-se **81 achados** (os que duas auditorias repetiam contam uma vez). **59 resolvidos** · **8 em parte** · **2 voltaram** · **9 ficaram** (não estavam entre os pedidos, ou dependiam de decisão) · **3 não vistos**.

### Os que voltaram (2)

| Achado de 30/09 | O que se mediu agora | Prova |
|---|---|---|
| **J2** — a aba Entidades fazia desaparecer as abas do Mercado | As quatro abas do Mercado **estão no HTML** de `/entidades` (o `abas_do_mercado()` desenha-as), mas a barra das cinco vistas das entidades **fica por cima delas**: `nav[aria-label='Vistas do Mercado']` em y = 248,9 px e `nav[aria-label='Vistas das entidades']` em y = 252,9 px, as duas com 1 212 × 40. Nas capturas a 1280 e a 390 só se vê a segunda. Quem lá chega continua sem caminho de volta ao «Por celebração» e aos «Concorrentes» a não ser pela barra de cima — que era o achado | `estilo/miragov-radar.css:442`, `.topo>.abas-mercado+.mg-tabs{grid-row:4}`: o seletor procura um `.topo` que o cabeçalho destas páginas já não tem; `entidades-acabar-claro-1280.png`, `-390.png` |
| **B.2 dos pesos** («`mil_pt` no `title` das barras») | A correcção partiu o **resumo do Mercado**: ver N1 | `radar.py:26388` |

### Os que ficaram em parte (8)

| Achado | Resolvido | O que falta, medido |
|---|---|---|
| **F1/E10** alvos de 44 px no toque | a triagem dos Concursos, as abas, a paginação, o selector e o «Mudar» das linhas das Propostas, a caixa ✓ (24 + `::before` de 11 px) | Hoje a 390: «Dispensar», «Esconder as feitas» e «adiar todas para hoje» a **32 px**; as pílulas «Todos/as minhas/João/sem dono» a **27–30 px**. Proposta sem anúncio: «Mudar» **32**, selector **36**. Ficha: o índice em pílulas a 26 |
| **E8/V-E2** um primário por ecrã | ficha da entidade 4 → **0**; Conta 5 → 1; Alertas 4 → 1; Perfil 2 → 1; Propostas 2 → 1 | ficha com proposta **7 → 5** (o «Guardar» da nota e um «Guardar» por tarefa); proposta sem anúncio **3 → 3**. O «Guardar» da tarefa ficou `mg-btn--primary` (`radar.py:32393`) |
| **C.2 #1/#9** nenhum peso a 700 | dentro do `main.mg` o `<b>` é 600 (`miragov-radar.css:1350`); 98 regras mortas saíram (`2cdf4fa`) | **7 elementos a 700** na aplicação: o dia de hoje da fita (`.fita .hoje .d`, `radar.py:16496`), o dia de hoje e o mês novo do Calendário (`:16159`, `:16162`, 5 no ecrã), o nome da fase na caixa da proposta (`.prop-nome`, `:16041`). Fora do `main.mg`: 13 `<b>` nos termos, 8 na privacidade, 7 na acessibilidade, e 5 no site (o preço dos planos e um `strong`) |
| **J3** dois moldes de cabeçalho | nenhum título dentro de um `<summary>` (0 em 50 rotas) | Concorrentes e Entidades abrem com migalhas «Mercado › …» e o título da aba; Por celebração e Fim estimado abrem com «Mercado» e sem migalhas — quatro abas da mesma barra, dois cabeçalhos |
| **J4** ordenar | Concursos (Prazo, Preço base) e Propostas | Mercado, Entidades e **Concorrentes** (uma classificação, 442 fornecedores) não ordenam |
| **B4.1** o foco na banda azul | na aplicação, a barra, a barra de baixo e a banda do cartão focam a amarelo | o topo do **site**, dos termos, da privacidade, da acessibilidade e do **entrar** foca a magenta, **2,36:1**, nos dois temas (53 paragens). Não estava na auditoria do escuro (só viu 14 páginas da aplicação) |
| **V1/V-E1** o «Abandonar» | neutro (0 `mg-btn--warning` nos Concursos); o prazo folgado neutro | os 20 «Interessa» continuam de contorno verde: no escuro o `--success` é a cor mais forte da linha (fica, era a parte que pedia decisão) |
| **E5** nomes de coluna no ecrã | «preço base alterado» (0 «preco_base») | voltou noutra coluna: a cronologia da proposta sem anúncio diz **«prazo_entrega — 10/10/2026»** (N4) |

### Os que ficaram (9) — não estavam entre os pedidos ou dependiam de decisão

F5 («Verificar agora» no fim do `/plataforma`, `radar.py:23193`) · F6 (recusar um pedido escreve na célula) · Z3/G2 («Marque duas» sem contador) · J5 (o Calendário anda uma semana numa vista de seis) · M7 (a ficha com 9 entradas no índice) · M8 (as páginas legais sem índice — os termos têm agora **20 `h2`** e 5 815 px no computador; eram 10 secções) · B.1 #8 a #10 (etiquetas cuja razão só está no `title`).

### Não vistos (3)

Z4 e M6 (o e-mail do resumo) e B.1 #4 (as fatias da concentração, que vivem no resumo, que não abre).

### Resolvidos (59), por auditoria

- **UX-7-LEIS**: F2, F3, F4, H1, H2, H3, H4, H5, H6, H7, Z1 (no código: a empresa de teste tem propostas), Z2 (o `<title>` diz «(4) Hoje — Mira Gov»), J1, J6, J7, J8 (no código), G1 (no código), V2, V3, V4, V5, V6 (no código), V7, V8, M1, M2, M3, M4, M5.
- **UX-ICONES-DICAS-PESOS**: o «?» do sistema (8 `mg-disc__q`, 0 `<i>?</i>`), o caixote no apagar do contacto, os ícones na paginação, o `›` das migalhas, o `☐`, B.1 #1, #2 (a legenda «Papel: CLI cliente · CONC concorrente · C+C os dois» à vista), #5, #6, #7, C.2 #2 a #7.
- **UX-ECRAS-EM-FALTA-E-ESCURO**: E1, E2 (a opção «voltar a Por ver» já não aparece na proposta sem anúncio), E3, E6 (prazo e os quatro passos na proposta sem anúncio), E7, E9, E11, E12, E13, E14, E15, a seta `↕`, o fundo do diálogo no escuro, a etiqueta âmbar `#a0640a`.

---

## 3. Os achados novos

**N1. O resumo do Mercado não abre: 500 em todos os pedidos** — `/contratos/resumo`, e por isso o fundo de `/contratos` e de `/contratos?ver=fim`, que o carregam por baixo da tabela. Gravidade **Alta**. Lei: todas (✗ na linha inteira).
- **O que se vê**: por baixo da tabela dos contratos, um cartão «Correu mal — O painel deu um erro, e ficou registado» com um segundo botão cheio «Voltar ao Hoje» (`contratos-claro-1280.png`). No lugar estavam os 7 gráficos do resumo.
- **Prova**: `ValueError: invalid literal for int() with base 10: '14\xa0931'` em `mil_pt()`. O `desconto_html()` monta as barras com `"k": mil_pt(k)` (`radar.py:26221`), e o `barras_v()` passou a pôr `mil_pt(l["k"])` no `title` (`radar.py:26388`, commit `13eb234`, a correcção do B.2 de 30/09): o número entra já formatado e rebenta à segunda volta. Só rebenta quando um escalão do desconto tem 1 000 procedimentos ou mais — que é o caso com o corpus verdadeiro e não com os dados dos testes, e por isso a bateria passou.
- **Afecta a produção**: o mesmo código está na instalação desde a v2.0.36.
- **Correcção**: no `desconto_html()`, `"k": k` (o número cru, como os outros dois chamadores do `barras_v()`), e um teste com um escalão de 1 000.
- **Cabe?** **Sim** (uma palavra e um teste).

**N2. As abas do Mercado tapadas nas Entidades** — é o J2 que voltou (secção 2). Gravidade **Alta** (a correcção diz que as desenha; o ecrã não as mostra). Correcção: o seletor da `miragov-radar.css:442` para o contentor que o cabeçalho tem hoje, de modo que a segunda barra fique na linha seguinte; ver a 390. **Cabe: sim** (CSS).

**N3. A ficha com proposta: cada tarefa traz o seu formulário aberto** — `/anuncio/<ref>` com proposta e `/proposta/<id>`. Gravidade **Média**. Hick, Von Restorff e Jakob.
- **Medido**: com 4 tarefas, a coluna da direita tem **12 controlos só para adiar e atribuir** (4 × «Adiar para», «Quem faz», «Guardar»), mais 5 botões cheios, todos «Guardar». No Hoje, o mesmo gesto está fechado atrás de «adiar · quem». A 390 a ficha tem 5 659 px; a proposta sem anúncio, com 2 tarefas, abre os mesmos campos a toda a largura.
- **Correcção**: o formulário de cada tarefa dentro de um `<details>` «adiar · quem», como no Hoje, e o «Guardar» dele secundário (`radar.py:32386-32393`).
- **Cabe?** **Sim** (a classe do botão já; o `<details>` é meia hora com o teste).

**N4. «prazo_entrega» na cronologia** — proposta sem anúncio. Gravidade **Média** (Jakob; a classe do E5). A coluna nova do E6 não entrou no `_NOMES_ACCAO` (`radar.py:20876-20885`). Correcção: `"prazo_entrega": "prazo de entrega"`. **Cabe: sim** (uma linha).

**N5. As setas de ordenar têm 16 px de altura** — Concursos e Propostas. Gravidade **Média** (Fitts; WCAG 2.5.8). `a.ordenar` «Preço base» 66 × 16 e «Prazo» 39 × 16, nas duas larguras: entraram com o J4 de 1/10 e o `TestAlvosDeTextoA24px` não os vê. Na mesma lista, a Ref.ª «—» da proposta sem anúncio é uma ligação de **8 × 18 px** (o título ao lado leva ao mesmo sítio). Correcção: `th a.ordenar{display:inline-flex;align-items:center;min-height:24px}`, e o «—» sem ligação. **Cabe: sim**.

**N6. O foco magenta a 2,36:1 no topo do site e das páginas sem sessão** — ver B4.1 na secção 2. Gravidade **Média** (WCAG 1.4.11; o teclado é a primeira coisa que um visitante cego ou motor usa no site). Correcção: no `site/moldura.css`, `.topo :focus-visible{outline-color:var(--focus-on-header,#ffd84d)}`, como a aplicação. **Cabe: sim**.

**N7. Concorrentes: dois âmbitos na mesma linha** — `/concorrentes`. Gravidade **Média** (Miller e clareza). A primeira linha diz «Concorreu 12 · Ganhou **0** · Taxa 0 % · Desconto quando ganha **40 % em 71**»: as três primeiras são do perfil nos últimos 2 anos, a última é «de sempre», e só a nota do pé o diz. 2 das 20 linhas da primeira página têm 0 vitórias e um desconto. Sem ordenar (J4). Correcção: o cabeçalho «Desconto quando ganha (de sempre)». **Cabe: sim** (texto); ordenar não.

**N8. Entidades: a procura ocupa um cartão inteiro, com botão cheio** — `/entidades`. Gravidade **Baixa** (Von Restorff, Hick). «Nome ou NIF» + «Abrir a ficha» (primário) num cartão de 1 212 px com a metade esquerda vazia, nas duas larguras; é o único primário de uma página de listas. Correcção: secundário, e o campo à esquerda. **Cabe: sim** (a classe).

**N9. As Entidades não dizem que não seguem o perfil** — Gravidade **Baixa** (Jakob, consistência). «Por celebração» e «Concorrentes» abrem com a faixa «Limitado ao perfil da empresa»; as Entidades, na mesma barra, não a têm e mostram hospitais a uma empresa de obras («Contratos a acabar · 2 663»). Correcção: uma frase a dizer que as entidades são todas. **Cabe: sim** (texto); recortar pelo perfil pede decisão.

**N10. As iniciais da pílula «as minhas» não se lêem** — Hoje. Gravidade **Baixa**. «MR» a 1,68:1 no claro e 1,30:1 no escuro (o nome está no `.so-leitor`, por isso o leitor de ecrã está servido). Correcção: a cor do `.periodos .av.eu` igual à do `.av.eu` fora da pílula. **Cabe: sim**.

**N11. A tarefa do cofre repete o tipo** — Hoje e Calendário: «renovar Certidão da AT **Certidão AT** (válido até 11/10/2026)». Gravidade **Baixa**. Correcção: a descrição só quando acrescenta ao tipo. **Cabe: sim**.

**N12. O site tem quatro botões cheios com três nomes** — `/` sem sessão. Gravidade **Baixa** (Von Restorff). «Pedir um lugar de fundador» ×2, «Pedir o Duo», «Pedir acesso»: levam todos ao mesmo formulário (`#acesso`, com `data-plano`). A 30/09 era «um só CTA, repetido». Correcção: decisão dele (o plano escolhido pode ir no formulário e o botão ser um só). **Cabe: não** sem decisão.

**N13. Os 7 pesos 700 que ficaram** — secção 2, C.2 #1/#9. Gravidade **Baixa**. Correcção: as quatro regras do `CSS` a 600, e `.legal :is(b,strong){font-weight:600}` no `moldura.css`. **Cabe: sim**.

### O que está bem, e é novo

- **A pesquisa geral**: na barra de todas as páginas, com «Procurar (Ctrl+K)» escrito no próprio campo, e uma página de resultados por grupos (Propostas, Concursos, Entidades) para quem carrega em Enter.
- **O Calendário com propostas**: «As nossas 12» com as tarefas na grelha, o ⚠ e o ◷ com legenda, e «3 com prazo depois destas seis semanas — ver em lista».
- **A Situação**: uma tabela por bloco («Por submeter», «Em jogo», «Decididas este trimestre»), cada uma a somar o que o indicador de cima diz (6,5 M€, 82,6 k€, 177,4 k€).
- **As Propostas**: «→ A preparar» / «→ Submetida» na linha; a etiqueta vermelha «atrasada · 29 set» é a única cor da coluna «Falta»; a proposta sem anúncio diz «sem anúncio» e tem prazo.
- **Os Concursos**: três campos à vista (eram oito) e o «Mais filtros»; os atalhos «j k i a ⏎» explicados num `<details>`; 0 elementos laranja nos botões.
- **Zero rolagem horizontal** em 200 vistas; o `<title>` conta as atrasadas.

---

## 4. As correcções que cabem antes de 5/10, por ordem

| # | Correcção | Achado | Gravidade | Onde |
|---|---|---|---|---|
| 1 | O resumo do Mercado volta a abrir: `"k": k` no `desconto_html()`, e um teste com um escalão de 1 000 | N1 | Alta | `radar.py:26221` |
| 2 | As abas do Mercado à vista nas Entidades | N2 (J2) | Alta | `miragov-radar.css:442` |
| 3 | O foco amarelo no topo do site, legais e entrar | N6 (B4.1) | Média | `site/moldura.css` |
| 4 | A tarefa da ficha num `<details>` «adiar · quem», com o «Guardar» secundário (ficha 5 → 1 primário, proposta sem anúncio 3 → 1) | N3, E8 | Média | `radar.py:32386-32393` |
| 5 | «prazo de entrega» na cronologia | N4 | Média | `radar.py:20876` |
| 6 | As setas de ordenar a 24 px, e o «—» sem ligação | N5 | Média | `miragov-radar.css`, a lista das Propostas |
| 7 | 44 px no toque para os três `mg-btn--sm` do Hoje, as pílulas e o «Mudar» fora da lista | F1 em parte | Média | `@media (pointer:coarse)` |
| 8 | «Desconto quando ganha (de sempre)» | N7 | Média | `concorrentes()` |
| 9 | Os pequenos: «Abrir a ficha» secundário (N8), a frase do perfil nas Entidades (N9), as iniciais da pílula (N10), a tarefa do cofre sem o tipo repetido (N11), os 700 que ficaram (N13) | — | Baixa | ver os achados |

**Não antes de 5/10**: o botão único do site (N12, decisão dele), ordenar no Mercado, Entidades e Concorrentes (J4), o cabeçalho único das quatro abas do Mercado (J3), recortar as Entidades pelo perfil (N9), e os que ficaram na secção 2.
