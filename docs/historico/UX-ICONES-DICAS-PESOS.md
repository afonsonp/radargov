# Auditoria de interface — ícones, dicas e pesos da letra

30/09/2026 · só leitura: nenhum ficheiro do repositório mudou, o painel não correu, nada foi à rede.

**Material e método.** O `ecrans.html` (34 ecrãs, o HTML verdadeiro de cada rota) foi partido por ecrã e contado com Python; os pesos e tamanhos **calculados** mediram-se abrindo uma cópia local dele no Chrome headless que já está no disco (`~/.cache/ms-playwright`), com um guião que lê o `getComputedStyle` de cada elemento com texto. Tudo o resto é `grep` ao `radar.py`, ao `icones.py`, ao `estilo/` e ao `site/`. As linhas citadas são do `master` em `2206786`.

**Um aviso sobre o material, antes de tudo** (vale para quem voltar a julgar os ecrãs pela colagem): o `ferramentas/ecrans.py:164-165` põe `html,body{font:400 13px/1.5 'Plex Sans'…}`. Na colagem, tudo o que se mede em `rem` (os `--text-*` da nossa folha) sai a **81 %** do tamanho real — o título de página aparece a 22,75 px em vez de 28 —, enquanto o que o sistema escreve em px fica igual; e os elementos sem letra própria aparecem em **Plex Sans**, que saiu a 21/09 (medidos: 116 rótulos da barra de baixo, 81 botões dos filtros, 29 «Saltar para o conteúdo»). **A colagem mostra uma hierarquia que a aplicação não tem.** Os números da parte C foram medidos com a raiz reposta a 16 px e Source Sans 3, como no `BASE`.

Gravidade: **Alta** (esconde informação de que a pessoa precisa, ou contradiz o que o ecrã diz) · **Média** (inconsistência que se vê ou barreira para um grupo) · **Baixa** (arrumação). «Cabe» = antes de 5/10/2026, menos de meia hora e sem risco.

---

## A. Os ícones

### A.0 A conta

| | Número |
|---|---|
| Ícones no `icones.py` | 49 |
| Nomes distintos usados no `radar.py` (`icone("…")` + `ICONES_DE_BAIXO`) | **18** — ajuda, anterior, apagar, calendario, configuracoes, descarregar, documento, euro, externo, lista, mais, menu, mercado, sair, seguinte, utilizador, ver, verificar |
| **Nunca usados** | **31** — alerta, arquivar, aviso, baixo, carregar, cima, copiar, direita, editar, email, entidade, equipa, esquerda, etiqueta, excluido, fechar, feito, filtrar, historico, imprimir, info, interessa, ligacao, local, lote, menos, ok, peca, pesquisar, prazo, relogio |
| `<svg class="mg-icon">` desenhados nos 34 ecrãs | 273 |
| … dos quais nas duas barras (9 por página × 29 páginas com barra) | 261 (96 %) |
| … no conteúdo das páginas | **12**: descarregar 5, externo 2, mais 2, anterior 1, seguinte 1, apagar 1 |
| Símbolos em texto nos 34 ecrãs | `&rarr;` 35 · `&#10003;` ✓ 26 · `&#10005;` ✕ 25 · `&larr;` 8 · `&rsaquo;` 4 · ↕ 2 · ⏎ 2 · ☐ 2 · ⚠ 1 · ◷ 1 · × 1 (mais o ⚠/◷ que o CSS põe em cada `.mg-tag--danger/--warning`) |
| Emojis | **0** no `radar.py`, 0 no `site/` |
| SVG escritos à mão | `_olho()` (`radar.py:16539`), `_olho_do_site()` (`radar.py:32912`, a mesma geometria com as cores escritas), os 8 de `marca/` (a mesma amêndoa `M1 30A64…` em todos — consistentes), e 4 vistos no `site/index.html:594-597` |

Fora da aplicação: o e-mail do alerta abre com um ponto laranja `#e08b2c` em vez do olho (`radar.py:10455`) — cor fora da paleta, mas num e-mail o SVG não é fiável; fica só registado (Baixa, não mexer agora).

### A.1 O mesmo conceito com desenhos diferentes

| Conceito | Desenhos em uso | Prova | Gravidade | Correcção numa frase | Cabe? |
|---|---|---|---|---|---|
| **«Feito / sim»** | **quatro**: o carácter ✓ (`SINAL_SIM` `radar.py:16577`, aviso de sucesso `:17188`, o JS `:17544`, a caixa da tarefa na ficha `:30375`); o visto desenhado com bordas em CSS (`.chk.on::after`, `radar.py:15721` e `miragov-radar.css:702`, a caixa do Hoje); 4 SVG à mão com traço 2,2 no site; e os Lucide `ok` e `feito`, **por usar** | e8: 20 «✓ Interessa»; `/`: `.chk` | Baixa | Deixar o ✓ onde vive em texto e CSS, e não acrescentar um quinto: a coerência que vale é a das **duas caixas de tarefa** (linha seguinte) | — |
| **A caixa de «marcar como feita»** | Hoje: `<button class='chk'>` vazio com visto em CSS, 16→24 px (`radar.py:34969`); ficha: `<button class='tq'>` com «✓» transparente até ao hover (`radar.py:30375`, CSS `:15125-15129`) | as duas com `aria-label` | Média | Pôr a ficha a usar a mesma `.chk` do Hoje (é a mesma acção, a mesma rota `/tarefa/<id>/feita`) | Não (dois CSS, e a caixa da ficha tem a nota G94 do hover; medir) |
| **Apagar / tirar / fechar** | `icone("apagar", 16)` no alerta (`:21037`); `&times;` no **apagar** do contacto (`:30132`) — que é destruir, como o alerta; `&times;` no tirar a etiqueta (`:30446`) e no fechar do aviso (`:17178`); Lucide `fechar` por usar | e25 tem o caixote; a ficha tem o × | Baixa | Regra de uma linha: **destruir** = `apagar`, **tirar de um conjunto / fechar** = `fechar`; só o contacto está do lado errado | Sim (1 linha, `:30132`) |
| **Anterior / seguinte** | ícones `anterior`/`seguinte` no calendário (`:31445`); `&larr; anterior` / `seguinte &rarr;` na paginação (`:18456`, `:18472`); `&larr; 7 dias antes` / `7 dias depois &rarr;` na fita do Hoje | e12 vs e8/e16/e17 vs e1 | Baixa | Passar a paginação e a fita para `icone("anterior")`/`icone("seguinte")` | Sim |
| **«O que é isto?»** | Barra: `icone("ajuda", 20)` (`:17125`). Página e bloco: um `<i>?</i>` com círculo feito no nosso CSS (`:17217`, `:26874`, `:28382`; CSS `:14316-14330`). O **sistema tem este componente**: `.mg-disc__q` (`miragov-componentes.css:210-213`, 20 px, e **enche-se de azul quando aberto**) — **0 usos** no `radar.py` | 16 «?» nos ecrãs (e4-e7, e13, e15, e19-e21) | Média | Trocar o `<i>` por `<span class='mg-disc__q' aria-hidden='true'>?</span>` nos três sítios e apagar as regras `details.porque > summary > i` — fidelidade ao sistema e o estado aberto passa a ver-se | Sim (3 strings + apagar CSS; o teste `:11981` só olha para a classe do `<details>`) |
| **Aviso / perigo** | ⚠ em texto (`:17184`, calendário `:31332`, `::before` do `.mg-tag--danger` `miragov-radar.css:668`); Lucide `aviso` por usar | — | Baixa | Manter: o `::before` não recebe SVG inline e o sinal já é o mesmo carácter em todo o lado | — |
| **Prazo a chegar** | ◷ em texto (`:31335`, `miragov-radar.css:669`); Lucide `prazo` e `relogio` por usar | e12 | Baixa | Manter, pela mesma razão | — |
| **Abrir / fechar uma secção** | ▸/▾ por CSS em 5 sítios (`radar.py:14744`, `:14770`, `:14814`, `:14929`, `:15682`); o «?» nos `porque`; no site, uma seta de bordas (`site/index.html:287`) | — | Baixa | Manter; se um dia se tocar, `direita`/`baixo` | Não |
| **Migalhas** | TOPO: `<a>…</a><s>&rsaquo;</s><em>…</em>` (`:16392-16396`) — o `<s>` é «texto riscado» e o › não é `aria-hidden`; ficha: `<ol class='mg-crumbs'>` do sistema, com o › no `::before` (`:26935`) | e15, e19-e21 | Baixa | Pôr `aria-hidden='true'` no `<s>` (ou trocar por `<span aria-hidden>`) | Sim |
| **Um ícone, dois destinos** | `documento` é «Propostas» na barra de baixo (`:17007`) e cada peça na ficha (`:29003`) — e o `peca` do sistema está por usar; `configuracoes` é «Configurações» e «Administração da plataforma» no menu do dono (`:14110`) | — | Baixa | Nas peças, `peca` | Sim (1 palavra) |

### A.2 Tamanho e traço

- Quatro tamanhos: **16** (3 chamadas: `:21037`, `:29039`, `:29078`), **18** (a omissão, a maioria), **20** (a Ajuda, `:17125`), **22** (barra de baixo, `:17035`, `:17065`).
- O `stroke-width` é sempre 1,75 no `viewBox` 24 (`icones.py:57-60`), por isso o traço desenhado vai de **1,17 px (16) a 1,60 px (22)**. Os 4 SVG do site têm 2,2 num `viewBox` 16 — **2,2 px, quase o dobro** do ícone de 16 da aplicação. Baixa; o do site troca-se por `icone("ok", 16)` pelo mesmo `_do_site()` que já troca o `<!--OLHO-->` (Sim, mas só se se mexer no site).
- Posição: o ícone vai **antes** da palavra em todas as acções, e **depois** só no `externo` («Ver no DR ↗», `:28775`) — é a convenção certa.

### A.3 Botões só com ícone e o nome acessível

**Zero falhas.** Nos 34 ecrãs, os controlos sem texto visível são 55 e **todos** têm `aria-label`: a Ajuda da barra (29), as barras do funil (24), o interruptor e o «Remover» do alerta (1+1). No código, os botões de × e ✓ passam pelo `rotulo=` do `accao()` (`:30132`, `:30375`, `:30446`, `:34971`) e o fechar do aviso tem o seu (`:17178`).

Um resto: o cabeçalho da coluna das caixas nas Entidades é o carácter `☐` (`radar.py:25570`; e20, e21) — um cabeçalho de tabela cujo texto é um desenho. **Baixa**; `<th><span class='so-leitor'>Comparar</span></th>`. **Cabe.**

### A.4 Onde um ícone ajudava, e onde seria ruído

**Ajudava (por ordem):**
1. **A falha da verificação** no «O que mudou» do Hoje (ver B.1): hoje é só cor. Um `icone("aviso")` antes do texto é o sinal além da cor que a WCAG 1.4.1 pede — faz parte da correcção B.1.
2. **O campo Pesquisar** (e8, e11) com `pesquisar`, e **«Mais filtros»** com `filtrar`: são os dois gestos de toda a lista, e os únicos ícones do sistema feitos para eles estão parados. Cabe (2 strings), mas é gosto: propor, não decidir.
3. **As peças** com `peca` (acima).

**Seria ruído:** nos itens de texto da barra de cima (a de baixo já os tem, e a de cima tem espaço para as palavras); nas abas; em cada linha das tabelas (o «✓ Interessa / ✕ Abandonar» já aparece 20 vezes por página no e8); nos títulos dos cartões. Os 31 que não se usam **não são dívida**: vêm do sistema, e apagá-los tirava o `icones.py` do que o sistema publica.

---

## B. As dicas ao passar o rato (`title=`)

### B.0 A conta

- `radar.py`: **48** linhas com `title=` e **48** com `aria-label=`.
- 34 ecrãs: **482** `title=` e **404** `aria-label=`.
- Onde estão os 482: selo do papel da entidade **198** (122 «cli», 72 «conc», 4 «c+c») · a barra, repetida em cada página, **116** (logótipo, Configurações, Ajuda, empresa: 29 × 4) · nomes cortados no resumo 28 · títulos cortados na lista 24 · barras do funil 24 · barras do resumo 24 · índice das Configurações 21 · «?» 16 · «sem NIF» 10 · e 21 soltos.
- **O `title` não aparece no toque nem ao teclado** (e um `title` num `<span>` também não é lido de forma fiável pelo leitor de ecrã). É problema **quando é o único sítio** da informação. A lista seguinte são esses.

### B.1 Onde a informação só existe no `title`

| # | O quê | Prova (rota) | Quem fica sem ela | Gravidade | Correcção numa frase | Cabe? |
|---|---|---|---|---|---|---|
| 1 | **A verificação falhou.** A meta do «O que mudou» diz «desde a última verificação, 20:00» a vermelho; a razão («o DR não aceitou a pesquisa (apiVersion)… refaz a captura») está **só** no `title` (`radar.py:34718`, `dica_verif` em `:34616`). E o subtítulo da mesma página diz «Última verificação às 20:00: 4 anúncios novos» — **nada diz, em palavras, que falhou**; o único sinal é a cor | `/` (e1, e2, e3, e33) | toda a gente no telemóvel e ao teclado; o daltónico nem vê a cor | **Alta** | Escrever «a última verificação **falhou** às 20:00» com `icone("aviso")` quando `not verif_ok`, e deixar o pormenor técnico no `title` | **Sim** |
| 2 | **cli / conc / c+c.** A palavra está no `.so-leitor` desde 29/09 (G74), e por isso o leitor de ecrã ouve «Cliente»; **quem vê e toca** só lê «CLI» (em maiúsculas por CSS), e a explicação «compra muito mais do que vende…» só existe no `title` (`radar.py:24576-24585`, `PAPEL_ABREVIADO` `:24534`). Não há legenda no ecrã e o glossário da Ajuda (`GLOSSARIO`, `:23827`) não tem «Cliente» nem «Concorrente» | e13, e16, e17, e20, e21: **198** selos | quem usa o telemóvel ou só o teclado | **Média** | Uma frase na nota por baixo das duas tabelas («CLI cliente · CONC concorrente · C+C os dois») e as duas palavras no glossário | **Sim** |
| 3 | **O valor de 11 das 24 barras** do resumo do mercado: acima de 6 barras (`MAX_ROTULOS_BARRAS`, `:24910`) só o máximo e o último levam o número; os outros ficam no `title` de um `<div>` sem foco (`:24952`) | `/contratos/resumo` (e18) | telemóvel, teclado, leitor | Média | Pôr os valores numa tabela `.so-leitor` por baixo de cada gráfico, e para o toque um `<details>` «ver os números» | Não (desenho) |
| 4 | **As fatias da concentração** e os **quadradinhos do «connosco»**: nome e valor de cada fatia, e o desfecho de cada proposta, só no `title` de um `<i>` vazio (`:24828`, `:24834`, `:25328`) | resumo; ficha da entidade | idem | Média | Os mesmos números numa lista à vista ou `.so-leitor` | Não |
| 5 | **Quem é o responsável.** A coluna mostra as iniciais («AF»); o nome está no `title` (`:19458` na lista das propostas; `_avatar_html()` `:34231` no Hoje). A tarefa **sem dono** é um `<span class='av vago' title='sem dono'>` **vazio** (`:34230`): para o leitor de ecrã, não existe | Propostas; `/` | toque, teclado; leitor no «sem dono» | Média | `<span class='so-leitor'>` com o nome inteiro (e «sem dono») dentro do avatar | **Sim** (a parte do leitor); o toque fica como está |
| 6 | **A sintaxe da pesquisa** («vírgula para qualquer uma; entre aspas, a frase exacta», `:19070`) e **a do CPV** («separados por \|; os zeros à direita alargam ao grupo», `:26223`) só no `title` do campo | e8, e11; e16, e17 | toque e teclado — **o `title` de um campo nem aparece ao focar** | Média | Um `mg-field__hint` à vista — no painel «Mais filtros», onde há espaço | Não (a barra compacta tem de ser medida a 320 px) |
| 7 | **Os atalhos do teclado** «j k i a ⏎»: a explicação está no `title` e no `.so-leitor` (`:19279-19282`). O leitor de ecrã está servido; **a pessoa que usa o teclado e vê** — a única que precisa disto — lê cinco letras soltas, porque o `title` não aparece com o foco | e8, e11 | teclado com visão | Baixa | Um `<details>` «atalhos» com a frase à vista | Sim |
| 8 | **«automática»** (a origem da tarefa, `:30382`, `:35043`), **«sem anúncio»** (`:19452`), **«sem data da adjudicação»** (`:32162`) e **«sem NIF»** (`:25027`, 10 no e13/e16/e17): etiquetas de estado cuja razão só está no `title` | ficha, propostas, contratos | toque, teclado | Baixa | Pôr o porquê no glossário e ligar a etiqueta ao termo (`/ajuda#…`) | Não |
| 9 | **O índice das Configurações**: a descrição de cada secção só no `title` (`:21507`; 21 nos ecrãs) | e23-e31 | toque, teclado | Baixa | Mostrar a descrição por baixo do nome na coluna do índice (em ecrã largo) | Não |
| 10 | **Os nomes cortados** (28 no resumo, `:24865`; 24 títulos na lista, `:17440`, `line-clamp:2`) | e18, e8 | toque | Baixa | Nada: a ligação abre a ficha, onde está inteiro | — |

### B.2 Onde o `title` sobra ou está bem

- **Redundantes mas inofensivos:** o `title` do «Configurações», da empresa («A trabalhar em: LATD») e da Ajuda (este com `aria-label='Ajuda'`, que é o que conta). O «Ordenar pelo prazo mais perto» (`:19125`) repete o que a seta ↕ sugere; o nome acessível da ligação é só «Prazo» — acrescentar «, ordenar» em `.so-leitor` (Baixa, Sim).
- **O logótipo = Hoje** (`:15994`): o nome acessível da ligação é «Mira Gov» (o `role=img` do logótipo) e «Hoje» só está no `title`; quem ouve não sabe que vai para o Hoje. Baixa; `aria-label='Hoje — Mira Gov'` na ligação. Sim.
- **O «?»** tem `title` num `<i aria-hidden>` — está certo: o que se toca é o `<summary>` inteiro.
- **Modo de suporte** (`:17293`): o JS põe `title='Só leitura…'` em botões **desactivados**, que o teclado não alcança; a faixa do topo já o diz. Só o dono o vê. Baixa.
- **Um número no `title` sai sem formatador:** «< 20 k€: 39 562, **39562** contratos» (`:24952`, `l["k"]` cru). Baixa; `mil_pt(l["k"])`. Sim.

### B.3 A declaração de acessibilidade

O pedido dizia que a declaração ainda admite as siglas das entidades explicadas só no `title`. **Já não admite**: o ponto «Papel de uma entidade («CLI», «CONC»)…» entrou a 26/09 (`d3fddf3`) e saiu a 29/09 (`f5e97cf`, lote 6), quando o `.so-leitor` resolveu o leitor de ecrã. Hoje a declaração lista só duas não conformidades (a grelha do calendário e o «+N»). O que ficou por resolver — **quem vê e toca não tem a explicação** (B.1 #2) — não é uma falha AA (as abreviaturas são o 3.1.4, AAA), por isso a declaração está certa; a correcção é de usabilidade.

---

## C. A hierarquia dos pesos da letra

### C.0 A escala

- **O sistema usa três pesos**: `miragov-componentes.css` tem 400 ×23, 500 ×11, 600 ×19 — **nenhum 700**. A Zilla Slab carrega-se só a 500 e 600 (`miragov-tokens.css:5-6`) e **mede-se sempre a 600**: não há negrito sintetizado. ✓
- **O radar acrescenta**: `miragov-radar.css` 700 ×3; `CSS` 700 ×15 e 620 ×1; `CSS_NOVO` 700 ×1, 620 ×1, 680 ×1.
- **Medido nos 34 ecrãs** (elementos com texto): 400 ×2096 · 500 ×959 · 600 ×888 · **700 ×58**. Tamanhos: **12 px ×2182 (55 %)** · 14 ×1384 · 16 ×262 · 18 ×41 · 22 ×19 · 24 ×6 · 26 ×58 · 28 ×46 · 34 ×1 · 40 ×2.
- A escala de tamanhos é da nossa folha (`--text-xs … --text-3xl`, `miragov-radar.css:16-17`), e o G93 já mapeou os tamanhos do sistema para ela (`miragov-radar.css:1240-1254`).
- `style=` com letra no HTML da aplicação: **só o tamanho do logótipo** (`:16568`); as outras 18 ocorrências estão nos e-mails, onde têm de ser inline.

### C.1 A tabela, por nível (medido, raiz a 16 px)

| Nível | Elemento | Peso | Tamanho | Letra | Onde |
|---|---|---|---|---|---|
| **Título de página** | `h1.mg-pagehead__title` | 600 | **28** (22 a ≤600 px) | Zilla | 29 ecrãs, todos iguais ✓ |
| | `h1.mg-empty__title` | 600 | 22 | Zilla | 404 (e14, e22, e34) |
| **Título de cartão** | `h2.mg-card__title` | 600 | 18 | Sans (22) / **Zilla** nos `--band` (9) | a maioria |
| | `div.mg-field__label` **como título** | **500** | **14** | Sans | 7 cartões do resumo do mercado (e18); 9 blocos da Situação (e4-e7) |
| | `h3` sem classe | **700** | 18 | Sans | «As propostas», Perfil da empresa (e24) |
| | `legend` | 600 | 16 | Sans | e23, e24 |
| | `.perfil > b` | **700** | 12 | Sans | leitura das peças (`radar.py:26810`, CSS `:14951`) |
| **Cabeçalho de tabela** | `th` (`.mg-table`) | 600 | **12** | Sans | Concursos (e8, e11) |
| | `th` (`.tab-contratos`, `.tab-mercado`) | 600 | **14** | Sans | ficha, Contratos, Entidades, Alertas (e13, e16, e17, e20, e21, e25) |
| | `th.p` na **mesma linha** | 600 | **12** | Sans | idem |
| **Rótulo** | `.mg-field__label` | 500 | 14 | Sans | 111 |
| | `dt` (factos da ficha) | 600 | 12 | Sans | 18 (e13) |
| | `.mg-stat__label` | 600 | 12 | Sans | 26 |
| | `label` pequeno, `.rot-t` | 500 | 12 | Sans | e13, e24, e25 |
| **Texto** | `td` da lista dos Concursos (`.mg-num`, plataforma) | 400 | **14** | Mono / Sans | e8, e11 |
| | `a.item-titulo` (o objecto) | 600 | 14 | Sans | e8, e11 |
| | `td` dos contratos (`.tab-contratos`) | 400 | **12** | Sans; `td.p` Mono (408) | e13, e16, e17, e20, e21 |
| | `td.o` (o objecto) | **600** | 12 | Sans | e16, e17 |
| | `dd` (factos da ficha) | 400 | 16 | Sans | e13 |
| | `.mg-card__meta` | 400 | 14 | Sans | 26 |
| **Nota** | `.nota` | 400 | 12 | Sans | ~300 |
| | `.ficha-nota`, `.mg-field__hint`, `.mg-empty__text` | 400 | 14 | Sans | |
| | `.mg-pagehead__sub` | 400 | 16 | Sans | 24 |
| **Número em destaque** | `.mg-stat__value` | 600 | **28** | Mono | Hoje, Situação |
| | `.ficha-prazo b` («8 dias») | 600 | **28** | Mono | ficha |
| | `.mudou-n b` | 600 | 22 | Mono | Hoje |
| | `.conc-n` («17 %») | **700** | **34** | Mono | resumo do mercado |
| | `.v` das barras | 600 | 12 | Mono | 76 |
| **Ênfase** | `<b>` sem classe | **700** (o do browser) | herdado | — | **36** medidos; `radar.py` tem 115 `<b>` e 0 `<strong>` |

### C.2 Os achados

| # | Achado | Prova | Gravidade | Correcção numa frase | Cabe? |
|---|---|---|---|---|---|
| 1 | **O `<b>` sai a 700 e a escala acaba em 600.** 36 ocorrências nos ecrãs: 20 datas a negrito no «por fim estimado» (e17, `td.d b`), 16 dentro de notas (e4, e7, e17, e18, e20-e25). Numa nota de 12 px, o 700 é o peso mais alto do ecrã | e17; `<b>` em 115 sítios do `radar.py` | Média | Uma regra na nossa folha: `main.mg :is(b,strong){font-weight:600}` | **Sim** |
| 2 | **O `h3` é mais pesado do que o `h2` por cima**: «As propostas» a 700/18 debaixo de «Perfil da empresa» a 600/18 — a nossa folha deu-lhe o tamanho (`miragov-radar.css:1255`) e deixou o peso do browser | `/configuracoes/interesse` (e24); `radar.py:20877` | Média | Acrescentar `font-weight:600` à regra `main.mg h3:not([class])` | **Sim** |
| 3 | **Os cabeçalhos das tabelas têm dois tamanhos, e trocam com o corpo entre ecrãs.** Nos Concursos: `th` 12, corpo 14. Nos Contratos, Entidades e ficha: `th` **14**, corpo **12** — o cabeçalho é maior do que o que encabeça — e na **mesma linha** o `th.p` («Preço») fica a 12. A causa é uma regra antiga do `CSS_NOVO` que põe `--text-sm` nos `th` das duas tabelas (`radar.py:15527-15532`, especificidade 0,2,1) e perde só contra o `main.mg table th.p` (0,2,3, `miragov-radar.css:286`) | e13, e16, e17, e20, e21, e25 vs e8 | Média | Tirar `.tab-contratos th` e `.tab-mercado th` dessa lista do `CSS_NOVO`: todos os `th` voltam aos 12 do sistema | **Sim** (uma linha; ver os três ecrãs depois) |
| 4 | **O corpo das tabelas dos contratos está a 12 px** (`radar.py:14639-14640`): 408 valores `td.p` e todos os objectos, entidades e datas. Nos Concursos o corpo é 14. É o maior bloco dos 55 % de texto a 12 px | e16, e17, e20, e21 | Média | Subir `.tab-contratos td` para `--text-sm` | Não (a tabela tem `min-width:900px` e larguras medidas; ver a 320 e a 1280) |
| 5 | **O título de cartão tem cinco tratamentos**: `h2` 600/18 (Sans ou Zilla), `div.mg-field__label` 500/14 (16 cartões e blocos — **sem elemento de título**, por isso o leitor de ecrã não os encontra por títulos), `h3` 700/18, `legend` 600/16, `.perfil > b` 700/12 | e18, e4-e7, e24, `:26810` | Média | Nos gráficos e na Situação, `<h2 class='mg-card__title'>` em vez do rótulo | Não (são 16 blocos em duas funções; e muda a navegação por títulos — testar com o leitor) |
| 6 | **Os estados vazios têm três formas**: `mg-empty__title` (2 sítios), um `<b>` como título a 700/16 (`radar.py:25585`, `:26348`, `:26362`; e19) e texto solto (~20 `mg-empty` sem título) | e19 vs e27-e31 | Baixa | Os três `<b>` passam a `<h2 class='mg-empty__title'>` | Sim (3 strings). É por isto que o `<b>` sai a 700: a regra que o devia pintar, `.vazio.comecar b` (`CSS`, `:14656`, 600), procura `.vazio` e o HTML tem `mg-empty` — já está morta |
| 7 | **No telemóvel, os números passam o título.** A ≤600 px o `h1` desce para 22 (`miragov-radar.css:617`) e o `.mg-stat__value` e o `.ficha-prazo b` ficam a 28. No computador empatam os três a 28: o G93 baixou o título do sistema de 30 para 28 (`:1247`) e deixou o número do sistema nos 28 | `/` e a ficha, a 390 px | Baixa | Na mesma `@media`, `.mg-stat__value,.ficha-prazo b{font-size:var(--text-xl)}` | Sim (mas é gosto: um painel pode querer o número acima do título — perguntar) |
| 8 | **O `.conc-n` é o texto mais pesado e maior da aplicação**: 700/34 px mono, acima do `h1` (600/28) da página onde aparece, num cartão cujo título é um rótulo 500/14 | e18; `radar.py:14597` | Baixa | 600 e `--text-2xl` | Sim |
| 9 | **Pesos soltos (700, 620, 680) no nosso CSS.** Vivos a 700: `.bb-item` aceso e `.bb-menu` aceso (`miragov-radar.css:853`, `:862`), `.ficha-lista li.aberta a` (`:376`), `.fita .hoje .d` (`radar.py:15640`), `.cal-dia.hoje .cal-n` (`:15225`), `.conc-n`, `.prop-nome`, `.perfil>b`, `.achados b`, `.chip-prazo`, `.pf-tit`. **Em classes que o `radar.py` já não gera** (grep sem ocorrência de `class='tit'`, `kpi`, `cx hoje`, `rot`, `abas`, `item-prazo`): `h1.tit` 700 e 680, `.kpi .v` 700, `.cx.hoje > h2` 620, `.rot` 700, `.abas a.on` 700, `.item-prazo` 700. O `[data-pele=novo] .item-titulo` 620 existe mas perde para o 600 da nossa folha | ver linhas | Baixa | Os três da nossa folha a 600 já; os mortos saem numa limpeza com os ecrãs à frente | Os 3 da nossa folha **sim**; a limpeza **não** |
| 10 | **O corpo tão pesado como o título**: nos contratos o objecto (`td.o`) é 600 como o `th` — **é de propósito** (o comentário `radar.py:14643-14646`: «invertido pelo peso»), e o `th` distingue-se pela cor. Fica | e16, e17 | — | — | — |
| 11 | **O site**: o «sobre» por cima de cada `h2` está a **700** (`site/index.html:176`, `:190`) e o `h2` em serifa a 600; o `<strong>` do ecrã de exemplo (700, `:371-381`) é mais pesado do que o título real da lista (600) | `/` sem sessão | Baixa | `.sobre{font-weight:600}` | Sim |

### C.3 Diferenças entre ecrãs, em resumo

A mesma coisa com pesos ou tamanhos diferentes consoante a página: o cabeçalho de tabela (12 nos Concursos, 14 no Mercado — C.2 #3); o corpo de tabela (14 / 12 — #4); o título de cartão (#5); o estado vazio (#6); a caixa de tarefa (A.1). O título de página é o único nível **igual em todos os 29 ecrãs** que o têm.

---

## As correcções por ordem de valor

| # | Correcção | Parte | Gravidade | Onde | Cabe antes de 5/10? |
|---|---|---|---|---|---|
| 1 | A falha da verificação dita em palavras («falhou»), com `icone("aviso")`, e o pormenor no `title` | B.1 #1 | Alta | `radar.py:34718` | **Sim** |
| 2 | Legenda «CLI cliente · CONC concorrente · C+C os dois» por baixo das tabelas das entidades e dos contratos, e as duas palavras no `GLOSSARIO` | B.1 #2 | Média | `:25580`, a nota dos contratos, `:23827` | **Sim** |
| 3 | `main.mg :is(b,strong){font-weight:600}` e `font-weight:600` no `h3` sem classe | C.2 #1, #2 | Média | `miragov-radar.css:1255` | **Sim** |
| 4 | Tirar `.tab-contratos th` e `.tab-mercado th` da lista do `CSS_NOVO`: um só tamanho de cabeçalho de tabela | C.2 #3 | Média | `radar.py:15529` | **Sim** |
| 5 | O «?» passa ao `.mg-disc__q` do sistema (e vê-se aberto) | A.1 | Média | `:17217`, `:26874`, `:28382` + CSS `:14316-14330` | **Sim** |
| 6 | O nome inteiro do responsável e o «sem dono» em `.so-leitor` | B.1 #5 | Média | `:19458`, `:34230-34231` | **Sim** |
| 7 | O `ferramentas/ecrans.py` a pôr a letra da colagem só no que é dela, e a raiz a 16 px | nota inicial | Média (engana quem julga os ecrãs) | `ferramentas/ecrans.py:164-165` | **Sim** |
| 8 | Os 700 da nossa folha a 600 (barra de baixo, menu, peça aberta) e o `.conc-n` a 600 / `--text-2xl` | C.2 #8, #9 | Baixa | `miragov-radar.css:376`, `:853`, `:862`; `radar.py:14597` | **Sim** |
| 9 | Pequenos de uma linha: o contacto apaga com `apagar` (`:30132`); as peças com `peca` (`:29003`); `aria-hidden` no › das migalhas (`:16392`); `so-leitor` no `☐` (`:25570`); `mil_pt` no `title` das barras (`:24952`); `aria-label` «Hoje — Mira Gov» no logótipo; «ordenar» no «Prazo» | A.1, A.3, B.2 | Baixa | ver linhas | **Sim** |
| 10 | Paginação e fita com `icone("anterior")`/`icone("seguinte")` | A.1 | Baixa | `:18456`, `:18472`, a fita | Sim |
| 11 | Os estados vazios com `<b>` passam a `mg-empty__title` | C.2 #6 | Baixa | `:25585`, `:26348`, `:26362` | Sim |
| 12 | Os atalhos «j k i a ⏎» explicados à vista | B.1 #7 | Baixa | `:19279` | Sim |
| 13 | Os valores dos gráficos (barras, fatias, quadradinhos) fora do `title` | B.1 #3, #4 | Média | `:24952`, `:24828`, `:25328` | Não |
| 14 | A sintaxe da pesquisa e do CPV à vista, no painel «Mais filtros» | B.1 #6 | Média | `:19070`, `:26223` | Não |
| 15 | Títulos de cartão como `h2` nos gráficos e na Situação | C.2 #5 | Média | resumo e `/situacao` | Não |
| 16 | O corpo das tabelas dos contratos a 14 px | C.2 #4 | Média | `radar.py:14639` | Não |
| 17 | Uma caixa de tarefa só (a `.chk` do Hoje também na ficha) | A.1 | Média | `:30375` | Não |
| 18 | Limpar o CSS morto com os pesos 620/680/700 | C.2 #9 | Baixa | `radar.py:14333`, `:14342`, `:14380`, `:14857`, `:15260`, `:15352`, `:15519`, `:15520` | Não |

Tudo o que está acima respeita a decisão do dono: **nenhuma correcção toca no `miragov-componentes.css`**; o CSS vai para o `miragov-radar.css`, e as restantes são strings do `radar.py`. E, pela regra da casa, nenhuma se faz sem o sim dele — isto é a proposta.
