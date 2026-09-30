# Auditoria dos ecrãs que faltavam, e do tema escuro

30/09/2026 · só leitura: nenhum ficheiro do repositório mudou, o painel não correu, nada foi à rede. Completa o `UX-7-LEIS.md` e o `UX-ICONES-DICAS-PESOS.md` do mesmo dia. Os achados que já lá estão não se repetem: quando um ecrã novo os confirma, cita-se o número de lá (V1, F1, B.1 #3…).

## Material e método

- **As páginas**: 14 rotas × 2 temas = 28 ficheiros HTML verdadeiros, gerados pelo `ecrans_extra.py` a partir de uma **cópia** da base da empresa 2 (LATD), com duas propostas criadas para o efeito (uma com anúncio, uma sem), vistas como gestor. O código que as gerou é o do `master` em `2206786`; o `radar.py` e o `estilo/` são iguais neste ramo (`git diff --stat 2206786 HEAD -- radar.py estilo icones.py` vazio), por isso as linhas citadas valem nos dois.
- **O browser**: o Chromium headless que está em `~/.cache/ms-playwright/chromium-1243`, conduzido pelo `playwright-core` que está na cache do `npx`. As fontes foram apontadas para `tipo/` no disco (Source Sans 3, Zilla Slab e Source Code Pro carregaram).
- **Capturas**: 112 — cada página a 1280 × 900 e a 390 × 844 (esta com `isMobile` e `hasTouch`, o que liga o `@media (pointer:coarse)`), no primeiro ecrã e inteira. Nenhuma das 28 tem rolagem horizontal da página.
- **Contraste** (medido no browser, não calculado à mão): em cada elemento com texto próprio e visível, a cor calculada contra o fundo efectivo (subindo pelos antepassados e compondo as camadas transparentes e a opacidade). 1 543 textos por tema. Limiar 4,5:1, ou 3:1 a partir de 24 px (18,66 px a 700).
- **Componentes**: 216 controlos por tema (campos, selects, botões, abas, caixas); contorno e fundo contra o que está à volta, limiar 3:1.
- **Foco**: 45 `Tab` por página a partir do topo = 620 paragens por tema; em cada uma, o `outline` calculado e a razão contra o fundo por trás do elemento.
- **Pesos e alvos**: `getComputedStyle` e `getBoundingClientRect` nas sete páginas da parte A.
- **O código**: `grep` por cores escritas à mão (`#hex`, `rgb`, `white`, `black`) no `radar.py` e nas quatro folhas, e por `style=` com cor nas 14 páginas escuras.

### O que não se viu

- **Estados que precisam de gesto**: o hover, o menu da conta aberto, o «Mais» da barra de baixo aberto, os avisos depois de gravar, e o diálogo do motivo **cheio** (abriu-se vazio com `showModal()`: os motivos entram por JS no clique).
- **A árvore dos CPV**: no Perfil e nos Alertas diz «falhou a carregar», porque é um `fetch` e as páginas estão fora do servidor.
- **As peças**: a cópia não as tem, por isso nem o visualizador nem as imagens das páginas dos PDF (que são brancas por natureza) foram vistos.
- **As ranhuras que pedem campos**: o guião pediu `estado="preparar"`, que não é chave da escada (é `proposta`), e as duas propostas ficaram em «Por analisar». Não se viu a caixa da escada com preço, lugar ou motivo, nem uma proposta decidida.
- **A cronologia da proposta sem anúncio diz «(sem nome)»**: a proposta nasceu fora de um pedido. Numa proposta verdadeira ali está o nome de quem a criou; não é achado.
- O tema **contraste**, o leitor de ecrã, um telemóvel verdadeiro e os e-mails em clientes com tema escuro.
- A ordem do foco foi seguida só até à 45.ª paragem de cada página. O fundo das páginas longas ficou por percorrer.

Legenda: ✓ cumpre · ⚠ cumpre em parte · ✗ falha · — não se aplica. Gravidade: **Alta** (esconde ou contradiz informação), **Média** (inconsistência que se vê, ou barreira para um grupo), **Baixa** (arrumação). «Cabe» = antes de 5/10/2026, menos de meia hora e sem risco.

---

## Parte A — os ecrãs que faltavam

### A.0 A conta dos sete ecrãs (claro, `<main>` só)

| Ecrã | Botões | Ligações | Campos + selects | Primários | `title=` | Ícones SVG | `<b>` | `h2` |
|---|---|---|---|---|---|---|---|---|
| Hoje, com 2 tarefas | 5 | 36 | 2 + 2 | 2 (dentro do «adiar · quem», fechados) | 10 | 0 | 6 | 4 |
| Propostas, com 2 linhas | 3 | 13 | 1 + 2 (18 opções) | 2 | 5 | 1 | 0 | 0 |
| Proposta sem anúncio | 5 | 2 | 7 + 3 | 3 | 1 | 0 | 1 | 1 |
| Ficha da entidade | 5 | 41 | 11 + 0 | 4 | 67 | 0 | 2 | **1** |
| Ajuda | 0 | 2 | 0 | 0 | 1 | 0 | 7 | 6 |
| Documentos da empresa | 1 | 5 | 2 + 1 (9 opções) | 1 | 5 | 0 | 0 | 1 |
| Ficha do anúncio **com proposta** (onde a `/proposta/<id>` com anúncio redirecciona) | 11 | 53 | 10 + 5 | **7** | 36 | 3 | 6 | 10 |

### A.1 Tabela-resumo das sete leis

| Ecrã | Fitts | Hick | Zeigarnik | Jakob | Goal gradient | Von Restorff | Miller |
|---|---|---|---|---|---|---|---|
| Hoje, com tarefas | ⚠ | ✓ | ✓ | ⚠ | ✓ | ⚠ | ✓ |
| Propostas, com linhas | ⚠ | ✗ | ✓ | ⚠ | ⚠ | ✗ | ⚠ |
| Proposta sem anúncio | ⚠ | ✓ | ⚠ | ⚠ | ✗ | ⚠ | ✓ |
| Ficha da entidade | ⚠ | ⚠ | — | ⚠ | — | ⚠ | ⚠ |
| Ajuda | ✓ | ✓ | — | ⚠ | — | ✓ | ⚠ |
| Documentos da empresa | ✓ | ✓ | ⚠ | ⚠ | — | ✓ | ✓ |
| Ficha do anúncio com proposta | ⚠ | ⚠ | ✓ | ⚠ | ✓ | ✗ | ⚠ |

Totais das 7 linhas (49 células): **4 ✗ · 22 ⚠ · 16 ✓ · 7 —**.

### A.2 Os achados

**E1. A Situação diz «0» em cima de «Por analisar», e «2» vinte centímetros abaixo** — `/situacao`, aba Negócio. Gravidade **Alta**.
- **O que se vê**: o gráfico «Abertas, por fase» põe **0** por cima da barra «Por analisar»; o gráfico «Propostas por fase», na mesma página, põe **2**. As duas propostas não têm preço, e o primeiro gráfico mostra **euros sem a unidade** — o número parece uma contagem.
- **Prova**: `radar.py:31892-31893`, `euros_curto(pipeline[ch]["euros"]) if pipeline[ch]["euros"] else "0"`; o `aria-label` da mesma barra diz «Por analisar: 2 proposta(s)», por isso o leitor de ecrã ouve 2 e o olho lê 0. Quebra a regra da casa: o número tem de dar a lista que a ligação abre (a ligação abre as 2).
- **Correcção**: escrever a contagem e os euros («2 · 0 €»), ou pelo menos «0 €».
- **Cabe?** **Sim** (uma cadeia de formato). O M1 da outra auditoria (tirar este gráfico) resolve-o também, mas pede decisão.

**E2. «voltar a Por ver» numa proposta que não tem anúncio** — Propostas, proposta sem anúncio. Gravidade **Média**.
- **O que acontece**: o selector de cada linha tem 9 opções, e a 9.ª é «voltar a «Por ver»». Numa proposta sem anúncio não há «Por ver» para onde voltar: o `mover_proposta()` recusa com ««porver» não é um estado da empresa.» — o nome interno da ranhura, no ecrã.
- **Prova**: `selector_de_ranhura()` acrescenta a opção sempre (`radar.py:16654-16655`); `escada_da_proposta()` (`radar.py:29840`) manda as sem `ref` para o `mover_proposta()`, cuja primeira guarda devolve essa frase. Nas Propostas, a segunda linha tem-na.
- **Correcção**: não pôr a opção quando a proposta não tem `ref`.
- **Cabe?** **Sim** (uma condição). *Deduzido do código; o POST não se correu.*

**E3. Na ficha da entidade, a fase das nossas propostas fica escondida à direita** — `/entidade/<chave>`, bloco «O nosso lado». Gravidade **Média**.
- **O que se vê**: «As nossas propostas 1» mostra só o título do concurso, cortado no bordo do cartão. A fase («Por analisar») e o preço estão lá, mas fora da vista: a tabela tem `min-width:900px` dentro de uma coluna de ~360 px, e rola de lado sem a dica «A tabela continua para o lado» (que só se põe em `.cal-rolo`, `.tab-cx` e `.mercado-tab`, `radar.py:16166`).
- **Prova**: `radar.py:14635` (`.tab-contratos{…min-width:900px}`), `miragov-radar.css:60` (`.ent-nossas{overflow-x:auto}`); captura a 1280.
- **Correcção**: `.ent-nossas .tab-contratos{min-width:0}` na nossa folha.
- **Cabe?** **Sim**.

**E4. «3 189anúncios»** — ficha da entidade. Gravidade **Baixa**.
- **Prova**: o HTML tem o espaço (`<b>3 189</b> anúncios`, `radar.py:25174`), mas o `.ent-num` é `inline-flex` (`miragov-radar.css:741`) e o flex come o espaço entre o `<b>` e o texto.
- **Correcção**: `gap:.25em` no `.ent-num`.
- **Cabe?** **Sim**.

**E5. «preco_base alterado»: o nome da coluna da base, no Hoje** — `/`, «O que mudou». Gravidade **Média** (Jakob; e soma ao V6).
- **Prova**: `radar.py:34670`, `"%s alterado" % m["campo"]`; na captura, 1 «preco_base alterado» e 4 «prazo alterado», todas `mg-tag--warning`.
- **Correcção**: um dicionário de duas entradas (`preco_base` → «preço base»).
- **Cabe?** **Sim**.

**E6. A proposta sem anúncio não tem prazo, nem os quatro passos** — `/proposta/<id>`. Gravidade **Média**.
- **Zeigarnik**: a tabela `propostas` não tem coluna de prazo (`radar.py:806`); uma consulta prévia por convite tem data de entrega, mas nunca entra em «Prazos a chegar», no Calendário, nem nas tarefas automáticas. O ecrã diz «Nada por fazer.» Hoje só se contorna escrevendo uma tarefa com «Até quando».
- **Goal gradient**: a ficha do anúncio abre com os 4 passos (`passos_da_escada()`, `radar.py:26955`; 1 `mg-stepper`); a proposta sem anúncio tem 0. A fase só se lê no selector.
- **Correcção**: um campo de prazo na proposta sem anúncio, e o mesmo stepper.
- **Cabe?** **Não** (migração; o `passos_da_escada()` recebe um anúncio).

**E7. A coluna da direita da ficha, com proposta, rola por dentro 56 % do que tem** — ficha do anúncio com proposta. Gravidade **Média**.
- **Prova**: medido a 1280 × 900, `.ficha-lado` tem 1 874 px de conteúdo numa caixa de 820 px (`miragov-radar.css:1127-1129`, `max-height:calc(100vh - …)`, `overflow-y:auto`). A página inteira tem 1 528 px: a parte de baixo da coluna («O que falta fazer», contactos, histórico) só se alcança rolando **dentro** dela. Na captura inteira, o cartão «A nossa proposta» acaba cortado a meio de uma tarefa.
- **O que já se decidiu**: o comentário diz porquê («senão o fim dela só se via no fim da página»). Sem proposta a coluna cabia; com proposta deixa de caber.
- **Correcção**: tirar o `max-height` quando a coluna leva a proposta, ou só a partir de 1 100 px de altura de janela.
- **Cabe?** **Não** (pede a palavra dele e ver a 1366 × 768).

**E8. Um primário por ecrã — os que faltavam** (o V2 da outra auditoria). Gravidade **Média**.

| Ecrã | Primários à vista | Quais | Qual fica |
|---|---|---|---|
| Ficha do anúncio com proposta | **7** | Trazer peças · Guardar (nota) · Guardar · Guardar · Adicionar (tarefa) · Guardar · Adicionar (contacto) | o «Guardar» da nota; «Trazer peças» já era o F2 |
| Ficha da entidade | 4 | Filtrar · Aplicar seleccionados ao filtro · Seguir esta entidade · Adicionar | «Filtrar» |
| Proposta sem anúncio | 3 | Guardar · Adicionar · Adicionar | «Guardar» |
| Propostas | 2 | Nova proposta · Filtrar | «Nova proposta» (confirma o V2) |

Mais: **quatro botões «Guardar» e dois «Adicionar» sem nome que os distinga** na ficha (nenhum com `aria-label`), e o diálogo do motivo diz **«Gravar»** para o mesmo gesto. Correcção: `secondary` em todos menos um, e o verbo único «Guardar». **Cabe: sim.**

**E9. Propostas: 3 das 8 colunas de dados vazias nas duas linhas** — `/propostas`. Gravidade **Média** (Miller; confirma o M4).
- **O que se vê**: «Lote», «Resp.» e «Preço base» dizem «—» nas duas linhas. A 390 px as linhas passam a cartões e esses travessões ficam **sem rótulo**: «PT1.NTC.3809959 — —» e «— 08/10/2026».
- **Mais duas coisas da mesma lista**: a coluna «Falta» corta a tarefa a meio («pedir esclarecimentos (prazo supletivo d…»), numa coluna de ~130 px que dobra em 4 linhas; e o «sem dono» é «—» na lista e um círculo tracejado vazio no Hoje (B.1 #5).
- **Correcção**: esconder uma coluna quando está vazia em todas as linhas (o «Lote» primeiro).
- **Cabe?** **Não** (mexe no molde da tabela e na versão cartão).

**E10. Os alvos no toque — confirmado nas linhas verdadeiras** (F1). Medido a 390 px com `pointer:coarse`, sem contar ligações dentro de texto:

| Ecrã | Alvos | Abaixo de 24 px | Abaixo de 44 px de altura | Os que mais contam |
|---|---|---|---|---|
| Hoje | 49 | 6 | 26 | a caixa ✓ `.chk` 24 × 24; o «adiar · quem» 24; «Todos» e «sem dono» 27 |
| Propostas | 19 | 3 | 17 | o selector da fase **30**; «Mudar» 32; as 8 abas 32; a ref.ª 18 |
| Proposta sem anúncio | 19 | 0 | 15 | «Mudar» 32; «Apagar esta proposta» 24 (é bom que seja pequeno e longe) |
| Ficha da entidade | 61 | 1 | 45 | os 6 períodos 26; os 3 atalhos «ver os…» 32 |

A correcção é a do F1 (um bloco no `@media (pointer:coarse)`), mais `main.mg td select` a 44 px. **Cabe: sim.**

**E11. A ficha da entidade abre com o filtro, e os números só aparecem no segundo ecrã do telemóvel** — Hick e Fitts. Gravidade **Média**.
- **Medido**: antes dos 6 números há o nome **duas vezes** (o `h1` e o cabeçalho do cartão, com a etiqueta «Cliente»), 6 campos de filtro, 6 períodos e a árvore. O primeiro número está a 573 px no computador e a **1 063 px a 390**; o «O nosso lado» a 869 e **1 665 px**.
- **Correcção**: os 6 números e o «O nosso lado» antes do filtro; o filtro recolhido em «Filtrar os contratos», como o «Mais filtros».
- **Cabe?** **Não** (muda a ordem de uma página inteira).

**E12. A ficha da entidade tem 8 títulos que não são títulos** — pesos e Jakob. Gravidade **Média** (confirma o C.2 #5, agora num ecrã novo).
- **Medido**: 1 `h2` na página («Contactos»); os 7 gráficos têm por título um `div.mg-field__label` a 500/14; a tabela do fim (12 contratos que a entidade ganhou) **não tem título nenhum**.
- **Dicas**: os valores de **22 barras** («Quanto adjudicou» 12, «Quanto ganhou» 10) só estão no `title` de um `div` sem foco (`radar.py:24952`) — é o B.1 #3, agora também aqui.
- **Correcção**: `<h2 class='mg-card__title'>` nos 7, e um título «Contratos que ganhou» na tabela.
- **Cabe?** Não (o mesmo que o C.2 #5).

**E13. A proposta sem anúncio tem três tratamentos de título, e a linha da cronologia pesa mais do que o título dela** — pesos. Gravidade **Baixa**.
- **Medido**: «A nossa proposta» 500/14 (rótulo); «Contactos» 600/18 (`h2`); «Cronologia» 500/14 (rótulo) — e a linha por baixo dele sai a **700/16** na data e 400/16 no resto, porque o `<div class='hist'>` da proposta (`radar.py:30946`) põe o texto solto, sem o `.t` e o `.q` que o `.hist` do resto da aplicação tem a 12 px.
- **Correcção**: a mesma marcação `.hist` com `.t`/`.q` que a ficha usa.
- **Cabe?** **Sim**.

**E14. Documentos da empresa: o subtítulo repete o parágrafo, e duas palavras sem explicação** — `/configuracoes/documentos`. Gravidade **Baixa**.
- **O que se vê**: o subtítulo da banda diz «alvará, certidões, ISO e seguros, com a validade» (`radar.py:21407`) e a primeira frase do cartão diz o mesmo. «Ainda não há documentos no **cofre**» (`radar.py:23631`): «cofre» não está no glossário. O botão diz «**Juntar**» (`:23635`), e nada se junta — não há ficheiro. Os rótulos saem a 500/12, quando os dos outros formulários são 500/14.
- **Zeigarnik**: o estado vazio não diz o que costuma ser pedido; o select tem 9 tipos.
- **Correcção**: tirar a primeira frase, «cofre» → «lista», «Juntar» → «Acrescentar».
- **Cabe?** **Sim**.

**E15. A Ajuda: 29 termos em 3 587 px, sem índice** — `/ajuda`. Gravidade **Baixa**.
- **Medido**: 6 cartões, 29 `<dt>`, cada um com âncora própria (e o `ligacao_ao_termo()` já liga para elas); o primeiro cartão tem 10 termos. Não há índice das 6 secções, e os cartões não têm `id`.
- **Mais duas**: a própria Ajuda tem o «?» de «O que é esta página»; e a abertura tem 7 `<b>` a 700 (o C.2 #1).
- **Correcção**: uma linha de 6 ligações no topo, e tirar o «?» da página da Ajuda.
- **Cabe?** **Sim**.

**E16. Os ícones nos sete ecrãs** — Baixa, sem correcção. O conteúdo tem 4 ícones SVG ao todo («+ Nova proposta», «Exportar CSV», os dois «Abrir… ↗» da ficha). Não falta nenhum e não sobra nenhum, pela régua do A.4 da outra auditoria. O «Cliente» da ficha da entidade é uma `mg-tag--success`, verde: é o V4.

**O que está bem nestes ecrãs**
- **Hoje**:
  - os baldes contam («Próximos 7 dias 1», «Mais para a frente e sem data 1»);
  - a fita diz «sex 2 · 1 tarefa»;
  - o «Pôr a empresa a trabalhar» diz «1 de 4 feitos» e risca o que está feito.
- **Calendário** (o Z1): com duas propostas, «As nossas 2» mostra as duas datas na grelha.
- **Proposta sem anúncio**: o «Apagar» está no fundo, fechado num `<details>`, com a consequência escrita e uma confirmação.
- **Propostas**: a coluna «Falta» existe e tem data.
- **Ajuda**: tem uma âncora por termo.
- **Documentos**: a validade diz «vazio se não caduca».

---

## Parte B — o tema escuro

### B.1 O contraste do texto: passa

| | Escuro | Claro |
|---|---|---|
| Textos medidos (14 páginas) | 1 543 | 1 543 |
| Abaixo do limiar | **3** | 3 |
| … que são o `✓` transparente do `.tq` na ficha (G94, de propósito: só aparece no hover) | 2 | 2 |
| … que é a seta `↕` «fraca» do «Prazo» ordenável nos Concursos | 1 (2,26:1) | 1 (1,83:1) |
| O texto mais baixo que passa | **4,69:1** | 4,74:1 |
| Textos entre 4,5 e 5,0 | 1 | 71 |

**O escuro tem mais folga do que o claro.** Os pares de tokens do escuro, calculados de `miragov-tokens.css:28-54`:

| Par | Razão | Par | Razão |
|---|---|---|---|
| `--ink` sobre `--surface-raised` | 14,06 | `--ink-muted` sobre `--surface-raised` | 5,68 |
| `--brand` (ligações) sobre `--surface` | 8,12 | `--ink-muted` sobre `--brand-soft` (o pior) | **4,69** |
| `--warning` sobre `--warning-soft` | 7,23 | `--danger` sobre `--danger-soft` | 6,62 |
| `--success` sobre `--success-soft` | 7,72 | `--on-brand` sobre `--brand` (botão cheio) | 7,92 |
| `--line-strong` (contorno dos campos) sobre `--surface-raised` | 5,29 | `--on-header-muted` sobre a barra | 5,87 |

A seta `↕` é o único sinal gráfico de que a coluna se ordena, e está abaixo de 3:1 nos dois temas. Gravidade **Baixa**; a correcção é `--ink-muted` na `.seta.fraca`, e **cabe**.

### B.2 Os componentes (3:1)

- **216 controlos por tema.** Os contornos dos campos e dos botões de contorno ficam a 5,29:1. A caixa de marcar nativa sai com contorno `#858585` sobre `#1c2027`, cerca de 4,7:1: o `color-scheme:dark` está posto (`miragov-radar.css:1211`). ✓
- **As abas** (`.mg-tab`): a aba activa distingue-se das outras por um fundo a **1,16:1** (1,19:1 no claro) e pela cor da letra. É igual nos dois temas e vem do sistema. Baixa, **não mexer**.
- **O diálogo** (o motivo do «Abandonar»): o fundo por trás é `rgba(22,27,38,.45)`, escrito à mão (`radar.py:14872`; `miragov-componentes.css:199`).
  - No claro escurece a página. **No escuro, a página passa de `#14171c` a `#151920`: 1,02:1**, e o próprio diálogo (`--surface-raised`) fica a 1,10:1 da página. Separa-se pela sombra e pelos cantos.
  - Na captura (`showModal()`, vazio) lê-se, mas o «a página ficou para trás» quase não existe.
  - Gravidade **Baixa**. A correcção é `[data-theme=escuro] dialog.mg-dialog::backdrop{background:rgba(0,0,0,.6)}` na nossa folha. **Cabe.**

### B.3 As cores que ficaram presas ao claro

**O que se procurou:**
- 0 `style=` com cor escrita nas 14 páginas escuras. Há 10 com cor, e todos usam `var(--…)`.
- 0 `<img>` nas 14 páginas.
- No `radar.py`, fora dos e-mails e do site, 9 cores escritas à mão. Nas folhas, 7 no `miragov-radar.css` e 7 no `miragov-componentes.css`.

**O que se encontrou:**

| # | O quê | Prova | O que faz no escuro | Gravidade | Correcção | Cabe? |
|---|---|---|---|---|---|---|
| 1 | **As etiquetas** da proposta: letra `#fff` sobre 6 cores fixas | `CORES_ETIQUETA`, `radar.py:2889`; `.etq`, `:15052-15053` | O `#d68910` com letra branca dá **2,82:1 nos dois temas** (falha AA, a 12 px/600). No escuro, `#1f4e79` e `#6c3483` ficam a 1,9:1 do cartão: a pastilha quase desaparece, mas a letra lê-se | Média (a falha é dos dois temas) | `#d68910` → `#a0640a` (4,86:1 com branco; 3,36:1 contra o cartão escuro). As etiquetas já gravadas guardam a cor antiga | **Sim**, para as novas |
| 2 | O «×» de tirar a etiqueta: `#fff` a `opacity:.6` | `radar.py:15055` | Sobre o `#d68910` fica a 1,91:1; sobre o `#1e8449`, a 2,72:1 | Baixa | `opacity:.85` | Sim |
| 3 | O fundo por trás do diálogo | acima, B.2 | 1,02:1 | Baixa | acima | Sim |
| 4 | O `<embed>` do PDF com `background:#fff` | `radar.py:29528` | Uma folha branca: é um documento, e é de propósito | — | nada | — |
| 5 | A pupila do olho (`#006432`, `#e61e1e`) e o amarelo do foco nas barras (`#ffd84d`) | `miragov-componentes.css:275-276`; `miragov-radar.css:516` | Vivem sempre sobre a barra azul, que é igual nos três temas | — | nada | — |
| 6 | `--ink:#14181e` no `CSS` e `--ink:#111418` no `CSS_NOVO` | `radar.py:14162`, `:15486` | Perdem para os tokens pela ordem do `CSS_TUDO`. Se o `miragov-tokens.css` faltar (o painel «serve na mesma»), o escuro não existe: fica tudo claro | Baixa | nada agora; tirá-las na limpeza do CSS morto (C.2 #9) | Não |

### B.4 O foco visível

| | Escuro | Claro |
|---|---|---|
| Paragens de `Tab` medidas | 620 | 619 |
| Com contorno | 619 | 618 |
| Sem contorno | 1 (o campo de hora, cujo foco o browser desenha **dentro** dele: o ícone do relógio fica com moldura) | 1 |
| Abaixo de 3:1 | **1** | **1** |
| As mais baixas a seguir | 3,19 (os indicadores do Hoje, sobre `#2c323b`) e 3,33 (as linhas dos Concursos sobre `--brand-soft`) | 3,18 · 3,38 |

**B4.1 «Esconder as feitas» — o foco magenta sobre a banda azul, a 2,36:1** — Hoje, cartão «Para fazer», nos dois temas. Gravidade **Média** (WCAG 1.4.11).
- **O que acontece**: a regra que troca o `--focus` pelo amarelo nas superfícies azul-marinho (`miragov-radar.css:516-518`) cobre a `.mg-topbar` e a `.barra-baixo`, e deixou de fora a `.mg-card--band`, cujo cabeçalho é o mesmo `--surface-header` (`:575`).
- **Onde calha**: é o único alvo focável dentro de uma banda nas 14 páginas. As outras 4 bandas (Alertas, Documentos, Perfil, ficha) não têm nada focável no cabeçalho.
- **Correcção**: acrescentar `.mg-card--band .mg-card__head :focus-visible` ao seletor da linha 517.
- **Cabe?** **Sim**.

Nota, sem correcção: os campos focam a `--brand` (7,39:1 no escuro) e tudo o resto a magenta (4,0 a 4,7:1). São dois desenhos de foco, e vêm do sistema.

### B.5 O que muda de destaque quando o fundo escurece (Von Restorff)

Contraste de cada cor contra o cartão (`--surface-raised`), por ordem:

| Claro | | Escuro | |
|---|---|---|---|
| `--brand` (ligações, primário) | **9,55** | `--seal` (o avatar da barra) | **10,17** |
| `--success` | 7,32 | `--success` | 8,58 |
| `--seal` | 6,92 | **`--warning`** | **8,56** (saturação 1,00) |
| **`--warning`** | 6,56 | `--brand` | 7,39 |
| `--danger` | 5,83 | `--danger` | 6,84 |

**V-E1. No escuro, o laranja passa à frente do azul.**
- **O que muda**: no claro, a cor mais forte do ecrã é a das acções (`--brand`). No escuro, o `--warning` e o `--success` passam-lhe à frente, e o laranja é o único tom com saturação 1,00.
- **O que isso faz nos Concursos**: as 20 molduras «Abandonar» `#ffaa00` são o elemento mais visível da lista; as 20 «Interessa» vêm logo a seguir; e as ligações das referências e dos títulos ficam atrás das duas.
- **Gravidade**: **Alta**. O V1 da outra auditoria é pior no escuro.
- **Correcção**: a mesma do V1 («Abandonar» neutro). **Cabe.**

**V-E2. O primário cheio vira o bloco mais claro do cartão.** No escuro o botão cheio é `#7fb3e6` com letra escura, e é a maior mancha clara de cada cartão. Com os 7 primários da ficha com proposta (E8), e o «Guardar» da nota a toda a largura da coluna, a coluna da direita tem mais peso visual do que o prazo. Gravidade **Média**; a correcção é a do E8.

**V-E3. O vermelho lê-se mais baixo do que o texto normal.**
- **Os números**: `--danger` a 6,84 contra 14,06 do `--ink`, com 2,06:1 entre os dois.
- **O que perde**: o «desde a última verificação, 20:00» (V6) e as etiquetas «atrasada». Destacam-se pelo tom e não pela luz; num ecrã com o brilho baixo ou sob a luz do dia, a falha lê-se menos do que o texto à volta.
- **Gravidade**: Baixa, porque o B.1 #1 da outra auditoria (escrever «falhou» e pôr o ícone) já o resolve.

**V-E4. O avatar da barra passa de castanho a amarelo `#ffc24d`**, e é a coisa mais clara da barra. Baixa; fica (é o `--seal` do sistema).

**O que não muda**: a banda azul do «Para fazer» e a barra de cima são `#004682` nos dois temas. Contra a página escura ficam a 1,88:1: continuam a ser as duas maiores manchas de cor, como no claro.

---

## As correcções por ordem de valor

| # | Correcção | Achado | Gravidade | Onde | Cabe antes de 5/10? |
|---|---|---|---|---|---|
| 1 | O «0» da Situação passa a «2 · 0 €» (ou «0 €») | E1 | Alta | `radar.py:31892` | **Sim** |
| 2 | «Abandonar» neutro — agora com a medida do escuro | V-E1, V1 | Alta | molde da linha e da ficha | **Sim** |
| 3 | O foco amarelo também na banda azul | B4.1 | Média | `miragov-radar.css:517` | **Sim** |
| 4 | Sem «voltar a Por ver» nas propostas sem anúncio | E2 | Média | `radar.py:16654` | **Sim** |
| 5 | A fase das nossas propostas à vista na ficha da entidade (`min-width:0`) | E3 | Média | `miragov-radar.css:60` | **Sim** |
| 6 | «preco_base» → «preço base» | E5 | Média | `radar.py:34670` | **Sim** |
| 7 | Um primário por ecrã: ficha com proposta 7→1, entidade 4→1, proposta sem anúncio 3→1; e um verbo só («Guardar», não «Gravar») | E8, V-E2 | Média | os moldes dos blocos | **Sim** |
| 8 | A etiqueta laranja `#d68910` → `#a0640a`, e o «×» a `.85` | B.3 #1, #2 | Média | `radar.py:2889`, `:15055` | **Sim** (as novas) |
| 9 | Alvos de 44 px no toque, incluindo o select da fase | E10, F1 | Média | `miragov-radar.css`, `@media (pointer:coarse)` | **Sim** |
| 10 | Pequenos de uma linha: o espaço de «3 189 anúncios» (E4); a seta `↕` a `--ink-muted` (B.1); o fundo do diálogo no escuro (B.2); a cronologia da proposta com a marcação `.hist` (E13); Documentos sem a frase repetida, «cofre» e «Juntar» (E14); o índice da Ajuda e o seu «?» (E15) | — | Baixa | ver achados | **Sim** |
| 11 | Os números e «O nosso lado» antes do filtro, na ficha da entidade | E11 | Média | `ficha_entidade()` | Não |
| 12 | Títulos `h2` nos 7 gráficos da entidade, título na tabela do fim, e os 22 valores fora do `title` | E12 | Média | `radar.py:24952` e o bloco | Não |
| 13 | Prazo e stepper na proposta sem anúncio | E6 | Média | esquema `propostas`, `passos_da_escada()` | Não |
| 14 | Esconder a coluna vazia nas Propostas (o «Lote» primeiro) | E9 | Média | a lista | Não |
| 15 | A coluna da direita da ficha sem rolagem própria quando leva a proposta | E7 | Média | `miragov-radar.css:1127` | Não (pede a palavra dele) |

As correcções respeitam o que ele decidiu e o que o sistema de desenho publica:
- nenhuma toca no `miragov-componentes.css`: o CSS vai para o `miragov-radar.css`, e o resto são cadeias do `radar.py`;
- pela regra da casa, nenhuma se faz sem o sim dele. Isto é a proposta.
