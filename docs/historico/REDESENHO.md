# Redesenho: Hoje, Ponto de situação, Entidades

> **Instantâneo de 17/09/2026.** É o pacote de desenho «Radar Gov UI
> redesign» tal como chegou — `Hoje.dc.html`, `Radar - Mockups.dc.html`,
> `radar.css` e este documento. Descreve o que se pediu nesse dia; o que
> ficou feito está no `ESTADO.md` e no `docs/diario/`, e o que ficou por
> fazer no `BACKLOG.md`. **Não se edita.**


## Overview
Redesenho de três ecrãs do painel Flask do radar (`radar.py`): a abertura **Hoje** (`/`), uma página nova **Ponto de situação** (o bloco `#negocio` que hoje vive no fim do Hoje passa a página própria) e a vista **Entidades** (`/entidades`), mais a **ficha da entidade** (`/entidade/<chave>`) e os estados vazios dos três.

Direcção escolhida pelo Afonso: **o sistema do próprio radar** (`docs/design.md` — IBM Plex Sans/Mono, paleta ardósia, cinco degraus de cinzento, cor só com significado). As variantes Industry (2c, 2e, 2g) ficaram de fora.

## About the Design Files
Os ficheiros deste pacote são **referências de desenho em HTML** — protótipos que mostram o aspecto e o comportamento pretendidos, não código para copiar. O trabalho é **recriar estes ecrãs no `radar.py`** com o padrão da casa: HTML por concatenação em Python, `envolver()`, o `CSS` + `CSS_NOVO` servidos em `/estilo/<etiqueta>.css`, sem nada de fora (CSP `default-src 'self'`). As regras do `docs/design.md` §2–§6 e do `docs/armadilhas.md` (área «A interface») continuam a valer; onde este desenho as quebra de propósito está dito em baixo.

## Fidelity
**Alta fidelidade** para cor, letra, escala e espaçamento — usa os tokens que já existem (`--f1..--f6`, `--t1..--t5`, `--azul/--verde/--laranja/--verm`, `--sup/--sup2/--linha/--traco`). Os dados são inventados a partir do `ESTADO.md` de 17/09/2026.

## Screens / Views

### 1. Hoje (`/`) — `Hoje.dc.html` (interactivo) e `Radar - Mockups.dc.html` #2a/#2b
**Objectivo:** responder em 3 segundos a «o que tenho de fazer hoje, o que fecha esta semana, o que mudou desde a última verificação, o que está parado».

**Layout** (1366 de referência; reflui):
1. **Linha de factos** em vez dos quatro cartões `.kpi`: `h1.tit` («Quarta, 17 de setembro» — a data, não a saudação) à esquerda; à direita, inline, quatro factos `--f4` mono + legenda `--f2` `--t4`: *1,42 M€ em jogo · 30 abertas* · *45% de vitória · 13 de 29* · *1 269 por decidir* (laranja) · *9 atrasadas · 52 para fazer* (vermelho) · ligação «Ponto de situação →». Cada facto abre a lista que o produz (regra da empresa).
2. **Fita da semana**: grelha de 7 células (`repeat(7,minmax(0,1fr))`, `gap:1px` sobre `--linha`, raio 9px, `--sombra`), seg→dom da semana corrente. Cada célula: `seg 15` em mono `--f2` 600; «N tarefas · M feitas» `--f1`; entregas a laranja; «X atrasadas arrastam»/«1 prazo passou» a vermelho. Dias passados `opacity:.7` fundo `--creme`; fim-de-semana `--linha2`; **hoje** fundo `--azul-fundo` e número azul 700; **dia escolhido** `outline:2px solid --azul` interior. Clicar escolhe o dia (o balde do meio muda). Por baixo, linha `--f2` `--t4`: «← semana passada · próxima semana · 17 tarefas · 3 entregas → · mais para a frente: 22».
3. **Duas colunas** `minmax(0,1fr) minmax(300px,360px)`, gap 18. Abaixo de 760px passa a uma.

**Coluna esquerda — `.cx#fazer` «Para fazer»**
- Cabeçalho (12×16, `border-bottom --linha`): `.rot` «Para fazer»; **pílulas de pessoa** (`.periodos` — Todos 52 · AF Afonso 23 · RM Rita 14 · JC João 9 · sem dono 6), a activa a azul cheio; à direita, «esconder as feitas» com caixa de 14px.
- Balde **Prazo passou sem decisão** (sempre aberto, vermelho): título + contagem + «o radar não mexe — escolhe a ranhura». Linha: título 600 `--f3`, sub-linha `.hj-c` «ref · entidade · prazo a dd mmm (vermelho) · [ranhura]», selector de ranhura à direita (`selector_de_ranhura()`).
- Baldes **Atrasadas** (vermelho, com «adiar todas p/ hoje» `.mini`), **Hoje · qua 17** (laranja) ou o dia escolhido, **Resto da semana** (`--t3`). Título é `.hj-t` clicável com seta ▾/▸ e conta as **por fazer**; «· N feitas» a `--t5`. Cada balde dobra.
- **Linha de tarefa** `.hj-row`: grelha `20px minmax(0,1fr) 64px minmax(120px,220px) 20px 96px`, gap 10, padding 6×8, raio 6, `border-left:2px` com a cor do balde, hover `--sup2`. Colunas: caixa ✓ (16px, raio 4, `--traco`; feita = fundo `--verde`), texto `.hj-o` (+ `.tag` «automática»), quando `.hj-q` mono (cor do balde), concurso `.hj-c` «ref · entidade» truncado, avatar 20px (AF azul cheio = eu; iniciais `--sup2`; sem dono = círculo tracejado), última coluna: «entrega 24 set» `--t4`, ou `.chip-prazo.avisa` «fecha hoje», ou o botão **desfazer** quando feita.
- **Feita**: a linha **fica no sítio**, texto riscado `--t5`, fundo `--sup2`, «desfazer» `.mini`. Com «esconder as feitas» ligado, as feitas de antes não aparecem; as riscadas nesta sessão ficam.
- Abaixo de 1180px a linha passa a `flex-wrap`: 1.ª linha caixa + texto + avatar + acção; 2.ª linha quando + concurso (recuo 26px).
- Rodapé: «Mais para a frente 22 · ✓ risca no sítio · desfazer na linha · a página fica onde está».

**Coluna direita** (três `.cx` 14×18):
- **O que mudou** — três números `22px` mono (38 anúncios novos · 12 no interesse (azul) · 2 peças novas) e um **feed** por hora (`grid 44px 1fr`, `.hj-q` à esquerda): novos no interesse como `.cal-it.empresa` (título 600 `--f1`, sub `--t5`); `.tag.info` «peça nova»; `.tag.avisa` «prazo alterado» com «19 set → 26 set, pela republicação …»; `.tag` «BASE» «adjudicado a X — a nossa está em Submetido — fecha-a»; movimentos de colegas com avatar.
- **Prazos a chegar · 7 dias** — `grid 44px 1fr auto`: quando (mono; hoje a laranja), concurso 500, `.tag` ranhura; «calendário →».
- **Paradas há mais tempo** — `.saude` com «41 dias» (laranja acima de 30).

**Telemóvel** (390): uma coluna; fita só com dia e contagem; linhas de tarefa em duas linhas. Em `Hoje.dc.html`, Tweaks › Ecrã = telemóvel.

**Quebras deliberadas do design.md:** os KPI deixam de ser cartões (§10 punha «quatro números» — mantêm-se, mudam de forma); a linha de tarefa tem mais de 24px de altura em telemóvel (duas linhas), o alvo continua ≥24px.

### 2. Ponto de situação (página própria, ex-`#negocio`) — Mockups #2d
Rota sugerida `/situacao`; item do Hoje («Ponto de situação →») e migalhas «Hoje › Ponto de situação». Abas: Negócio · Triagem · Por área CPV. **Período** com `.periodos`: este mês · 3.º trimestre (omissão) · 12 meses · tudo — e **comparação com o período anterior** em cada número.
- **Quatro números** numa grelha de 4 células `gap:1px` (não cartões): `.rot` + valor `28px` mono + delta mono `--f2` (▲ verde / ▼ vermelho / = `--t5`) + nota `--f1` «30 propostas abertas · 4 sem preço lido · era 1,20 M€ no 2.º T». Em jogo · Taxa de vitória (pp) · Ganho (€ e n.º) · Desconto médio nos ganhos.
- `.flash` «2 propostas ainda em aberto cujo procedimento o Portal BASE já diz adjudicado» com as ligações.
- Duas colunas. Esquerda: **Em jogo por ranhura** como **faixa horizontal** (segmentos com flex = €, cores `#c3ced9 #9db1c4 #5c809f #17557f`) e quatro legendas com `border-left:3px` da cor; **Taxa de vitória mês a mês** (6 barras, meses fora do período a `--traco`, mês com <3 decididos tracejado e sem taxa); **Funil da triagem** em barras horizontais com a conversão entre passos (17%, 14%).
- Direita: **Porque se perde** (`.barras-h` azul) e **Porque não se vai** (`--traco`) com a leitura «perde-se ao preço e recusa-se pelo preço base»; **Onde se ganha, por área** (verde; «poucos» a `--traco`); **Propostas por ranhura** como faixa de 8 segmentos + legenda inline (ganho verde, perdido vermelho).
- Regras: uma taxa só a partir de `MINIMO_PARA_TAXA`; sem número, frase por extenso.

### 3. Entidades (`/entidades`) — Mockups #2f
- Cabeçalho: título + «179 823 no Portal BASE · 4 106 no DR · 26 com quem já trabalhámos». **Abas** substituem as quatro listas: Com quem trabalhamos 26 · Seguidas 4 · Clientes que mais compram · Concorrentes que mais ganham · **Contratos a acabar · 90 dias 31**.
- `.cx.filtros`: procura por nome/NIF (cobre as grafias), selector CPV («o nosso interesse (72, 48)» / todos), período (24 m / 12 m).
- **Tabela** `.tab-contratos`: ☐ comparar · Entidade (nome 600 + NIF e n.º de grafias) · Papel (`.ent-papel.curto` C / K / C·K) · Compra 24 m · Ganha 24 m · **Connosco** (fita de quadrados 8px: verde ganho, vermelho perdido, azul em curso, `--traco` não fomos; + «6 propostas · 2 em curso») · Taxa connosco (mono; «de 3 — poucos» quando < `MINIMO_COM_ENTIDADE`) · A acabar 90 d (n.º · €) · Último anúncio · seguir/`.tag.ok` seguida. Legenda no rodapé.
- **Comparar**: com duas linhas marcadas, painel `.cx` com `border-color --azul-borda` e cabeçalho `--azul-fundo`; grelha `180px 1fr 1fr`: o que compra · a quem compra (com «nós N%») · desconto a que fecha · **relação connosco** (linha do tempo 2024–2026 com pontos coloridos + frase) · a acabar 90 dias.

### 4. Ficha da entidade (`/entidade/<chave>`) — Mockups #3a
- `.topo` com migalhas «Mercado › Entidades › SPMS», acções «seguir · comparar com… · ver os 214 anúncios» (`.bt.forte`), `h1.tit` + `.ent-papel`, linha de metadados (NIF mono, grafias, local, contactos, último anúncio) e **seis factos** em grelha `gap:1px`: Compra 24 m · No nosso CPV · Fecha a (−17,4%) · Connosco · Taxa connosco («2 de 3 — a taxa diz-se a partir de 5») · A acabar 90 d (laranja).
- Duas colunas. Esquerda **O nosso lado**: linha do tempo, tabela das propostas (Proposta/ref · Ranhura · Proposto · Desfecho — «−19% da base», «Glintt · 171 200 €», motivo do não fomos) e **Contactos** com formulário inline. Direita **Portal BASE**: o que compra por divisão CPV, a quem compra (concorrentes a laranja, **nós** a verde), nota de origem; **Contratos a acabar · 90 dias** (objecto · quem tem · valor · fim, o mais próximo a laranja) e a nota «costuma voltar ao DR 2–4 meses antes».

### 5. Estados vazios — Mockups #3b
- Hoje, primeiro dia: «Nada por fazer ainda» + explicação de onde nascem as tarefas + `.bt.forte` «ver os 1 269 por decidir» + «cria uma proposta sem anúncio». O que mudou: «A primeira verificação corre às 17:00 · verifica agora».
- Ponto de situação sem decididos: em jogo com o que há; taxa por extenso; faixa com ranhuras vazias tracejadas; motivos e comparação dizem o que falta para existirem.
- Entidades sem corpus: a aba «Com quem trabalhamos» funciona; «sem BASE» nas colunas do BASE; `.flash` com «Actualizar contratos».

## Interactions & Behavior
- **Riscar**: POST `/tarefa/<id>/feita` por fetch; a linha muda no sítio (classe feita + «desfazer»); sem JS, o formulário continua a funcionar e `volta_ao_referer()` deve voltar **à âncora da linha** (`#t<id>`), não ao topo — é a queixa principal («concluo a tarefa e volto para o início da página»).
- **Desfazer**: POST `/tarefa/<id>/por-fazer`, mesma linha.
- **Filtro por pessoa**: query `?quem=AF` (e «sem dono» = `?quem=`), contagens recalculadas; lembrar em `localStorage` **não** — segue-se a regra do §9 (sem memória); a omissão pode ser «as minhas» se `g.utilizador` existir.
- **Dobrar baldes**: `<details>` nativo; aberto por omissão excepto «Mais para a frente».
- **Escolher dia** na fita: `?dia=2026-09-19` muda o balde do meio; hoje é a omissão.
- **Adiar todas p/ hoje**: um POST por tarefa ou rota nova `/tarefas/adiar?para=hoje&quem=…`, com desfazer no `.flash`.
- Transições: as três regras já existentes (`.12s var(--ease-3)` em fundo/cor; `prefers-reduced-motion` desliga).
- Alvos ≥ 24px; foco `:focus-visible` azul como o resto.

## State Management (para o protótipo; no Flask é tudo servidor)
`pessoa`, `dia`, `esconderFeitas`, `dobrados{}`, `feitas{}`, `recentes{}` (feitas nesta sessão, que ficam visíveis), `datas{}` (adiamentos). Ver a classe `Component` em `Hoje.dc.html`.

## Design Tokens (os do `CSS_NOVO`, sem alterações)
- Fundos `--fundo #f5f6f8` · `--sup #fff` · `--sup2 #eef0f4` · `--linha #e3e6eb` · `--traco #c3c9d2`
- Texto `--t1 #111418` · `--t2 #343a42` · `--t3 #4a515b` · `--t4 #5a626d` · `--t5 #646d7a`
- Cor com significado: `--azul #1b5fc1` (acção/selecção/em curso) · `--verde #12704a` (ganho/feito) · `--laranja #9a4a06` (a chegar, atenção) · `--verm #b3261e` (atrasado, perdido)
- Fundos de nota `--azul-fundo #e8f0fd` · `--verde-fundo #e4f2ea` · `--laranja-fundo #fcefe1` · `--verm-fundo #fdeae8`
- Escala `--f1 11.5` · `--f2 12.5` · `--f3 13.5` · `--f4 15` · `--f5 17.5` · `--f6 25`; números 22–30px mono só nos factos.
- Letra `'Plex Sans'` / `'Plex Mono'` (em `tipo/`), `font-variant-numeric:tabular-nums`.
- Raio 8 (`.cx`), 6 (linhas, botões), 4 (tags, caixas); sombra `--sombra`.
- Barras das ranhuras `#c3ced9 #9db1c4 #7994ae #5c809f #17557f`; funil `#b9c6d2 #8ba3ba #5c809f --azul`.

## Classes novas a acrescentar ao CSS (sugestão de nomes)
`.factos-linha` (linha de KPI), `.fita`/`.fita-dia` (semana), `.hj-row` (linha de tarefa nova — pode substituir `.hj-l`), `.pill.on`, `.chk`, `.av`, `.feed` (o que mudou), `.faixa` (barras empilhadas horizontais), `.ent-fita` (quadrados connosco), `.comparar`.

## Assets
- `tipo/plex-sans.woff2`, `tipo/plex-mono-400.woff2`, `tipo/plex-mono-600.woff2` — os da pasta `tipo/` do radar.
- Sem ícones novos; ✓ e setas são caracteres.

## Files
- `Hoje.dc.html` — o Hoje fundido, interactivo (abre no browser; `support.js` ao lado).
- `Radar - Mockups.dc.html` — turno 3 (ficha da entidade 3a, estados vazios 3b), turno 2 (opções; escolhidas 2a, 2b, 2d, 2f), turno 1 (recriação do actual).
- `radar.css` — cópia reduzida e limitada a `.rg` do `CSS` + `CSS_NOVO` do `radar.py`, para os protótipos.
