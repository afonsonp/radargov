# Migração do radar.py para o sistema de desenho

> **Instantâneo de 21/09/2026.** É o plano tal como chegou no pacote
> `radargov-migracao.zip`, com o mapa de variáveis, o mapa de classes e
> as três fases. Descreve o que se **pediu**; o que ficou feito está no
> `ESTADO.md` e no `docs/diario/`. **Não se edita.**
>
> **Duas coisas dele não se seguiram, e foram medidas** (ver o diário de
> 21/09/2026 e a área «A interface» das armadilhas):
>
> 1. A **ordem** do `CSS_TUDO`. O plano manda `tokens + pontes + CSS +
>    CSS_NOVO`; com essa ordem **nada muda de cor**, porque o `CSS_NOVO`
>    redefine as mesmas variáveis com a mesma especificidade e vem
>    depois. O que define variáveis foi todo para o fim.
> 2. `--ink: var(--ink)` nas pontes é **circular**: as 79 regras que
>    usam `var(--ink)` ficavam sem valor, e a barra de topo ficava
>    transparente. A ponte saiu, e a barra passou a `--surface-header`.


O radar.py serve três moldes (`BASE`, `PAGINA_ENTRAR`, `PAGINA_ERRO`), uma folha única `CSS_TUDO = terceiros + CSS + CSS_NOVO` em `/estilo/<etiqueta>.css` (etiqueta = resumo do conteúdo, cache imutável), as fontes em `/tipo/<nome>` com lista branca `TIPOS`, e um CSP com `font-src 'self'`. A pele nova está em `[data-pele=novo]` no `<html>`. Nada disto muda: a migração é acrescentar três ficheiros à folha, quatro fontes à pasta, e trocar classes ecrã a ecrã.

## As três fases

**Fase 1 · Tokens e fontes (um dia, sem tocar em ecrãs).** Copia `tipo/ZillaSlab-SemiBold.woff2`, `ZillaSlab-Medium.woff2`, `SourceSans3-Variable.woff2` e `SourceCodePro-Variable.woff2` para `tipo/` e acrescenta os quatro nomes a `TIPOS`. Copia `estilo/radargov-tokens.css`, `radargov-pontes.css` e `radargov-componentes.css` para `estilo/` e muda `CSS_TUDO` para `terceiros + tokens + pontes + CSS + CSS_NOVO + componentes`, por esta ordem (as pontes têm de vir depois dos tokens e antes do CSS antigo). Troca `data-tipo="plex"` por nada e põe `data-theme="claro"` nos três moldes. Resultado: a aplicação inteira passa a pintar com a paleta e as letras novas, porque as pontes apontam `--papel`, `--t1`, `--azul` e as outras 41 variáveis antigas aos tokens novos. Os testes de contraste antigos (`TestContrasteNosFundosReais`) passam a medir a paleta nova; os que fixam valores hexadecimais têm de ser actualizados para lerem os tokens.

**Fase 2 · Barra, marca e moldes (um dia).** `.barra` passa a `.rg-topbar`; `.marca .logo` passa ao lockup (o markup está em `Logo`: `Radar G<svg>v`, com o disco inline) e o favicon a `radargov-favicon.svg`. `PAGINA_ENTRAR` refaz-se com o ecrã `EcraEntrar`; `PAGINA_ERRO` com `EmptyState`. O `envolver()` põe `.rg` no `<main>` para os componentes herdarem a letra e o foco.

**Fase 3 · Classes, ecrã a ecrã (a ordem da §11 do design.md).** Ficha do anúncio, lista dos concursos, Hoje, Propostas, Mercado, Calendário, Configurações. Cada ecrã troca as classes pela tabela abaixo, apaga do `CSS`/`CSS_NOVO` as regras que ficaram sem uso, e só se dá por feito depois de correr na instalação real com os 209 895 anúncios, como manda o `CLAUDE.md`. No fim, apaga-se `radargov-pontes.css` e o que restar do `CSS_NOVO`.

## Mapa de variáveis

| Antiga | Nova | Nota |
|---|---|---|
| `--papel`, `--fundo` | `--surface` | |
| `--creme`, `--sup` | `--surface-raised` | |
| `--linha2`, `--sup2` | `--surface-sunken` | |
| `--linha` | `--line` | |
| `--traco` | `--line-strong` | agora é a borda de campo (2px) |
| `--ink`, `--t1` | `--ink` | |
| `--t2`, `--t3` | `--ink-secondary` | seis tons passam a três |
| `--t4`, `--t5`, `--t6` | `--ink-muted` | |
| `--azul`, `--azul-fundo`, `--azul-borda` | `--brand`, `--brand-soft`, `--brand-soft` | |
| `--verde`, `--verde-fundo` | `--success`, `--success-soft` | |
| `--laranja`, `--laranja-fundo` | `--warning`, `--warning-soft` | |
| `--verm`, `--verm-fundo` | `--danger`, `--danger-soft` | |
| `--coral` | `--seal` | o ocre, só para o oficial e o destacado |
| `--azul-claro`, `--barra-t1`, `--barra-t2`, `--barra-t3` | `--on-header-muted`, `--on-header`, `--on-header-muted`, `--on-header-muted` | |
| `--ok-claro`, `--mau-claro` | `--success`, `--danger` | |
| `--sans`, `--mono` | `--font-sans`, `--font-mono` | `--font-serif` é novo: só títulos |
| `--f1` … `--f6` | classes `.label`, `.small`, `.ui`, `.body`, `.h3`, `.h1` | a escala deixa de ser variável e passa a estilo |
| `--r`, `--sombra` | `--radius-lg`, `--shadow-sm` | |

## Mapa de classes

| Antiga | Nova | Nota |
|---|---|---|
| `.bt` | `.rg-btn.rg-btn--secondary` | contorno azul a 2px |
| `.bt.forte` | `.rg-btn.rg-btn--primary` | um por bloco |
| `.bt.ok`, `.bt.verde` | `.rg-btn.rg-btn--success` | contorno, enche ao passar |
| `.bt.cuidado` | `.rg-btn.rg-btn--warning` | |
| `.bt.perigo` | `.rg-btn.rg-btn--danger` | |
| `.mini` (e `.mini.ok/.cuidado/.perigo`) | `.rg-btn.rg-btn--sm` + a variante | o botão da linha |
| `.tag`, `.tag.mono` | `.rg-tag`, `.rg-tag.rg-tag--mono` | pílula |
| `.tag.ok`, `.tag.avisa`, `.tag.mau`, `.tag.info` | `.rg-tag--success`, `--warning`, `--danger`, `--brand` | `.rg-tag--seal` é novo (PRR, adjudicação nossa) |
| `.cx`, `.item`, `.sec`, `.conf-cx`, `.prop` | `.rg-card` (`__head`, `__title`, `__meta`, `__body`, `__foot`) | um cartão por coisa; o principal com `.rg-card--band` |
| `.rot`, `.kpi .r`, `.facto .k`, `th` | `.rg-field__label` / `th` do `.rg-table` | caixa normal, sem maiúsculas espaçadas |
| `.nota` | `.rg-card__foot` ou `.rg-field__hint` | proveniência no rodapé; ajuda ao lado do campo |
| `.vazio` | `.rg-empty` (`__title`, `__text`, `__action`) | o facto e o próximo passo |
| `.flash`, `.flash.mau` | `.rg-alert.rg-alert--info`, `--danger` | com `__bar`, `__body`, `__title`, `__text`, `__action` |
| `.abas a`, `.abas a.on`, `.abas a i` | `.rg-tabs` › `.rg-tab[aria-selected]`, `.rg-tab__count` | segmento em pílula |
| `.abas-escada` | `.rg-tabs` | uma escada, não duas |
| `.kpis`, `.kpi .v` | `.rg-stats` › `.rg-stat` (`__label`, `__value`, `__delta`, `__note`) | `.rg-stat--seal` no número principal |
| `.delta.sobe/.desce/.igual` | `.rg-stat__delta--up/--down/--flat` | |
| `.sit-numeros`, `.sit-n` | `.rg-stats`, `.rg-stat` | |
| `.tab-lista`, `.tab-contratos`, `.tab-mercado`, `.tab-ensaio` | `.rg-table` com `.rg-num` nas colunas de dinheiro e datas e `.rg-code` nas referências | |
| `.barra`, `.marca .logo`, `.barra nav a.on`, `.sou .av` | `.rg-topbar`, `.rg-topbar__brand` (+ `Logo`), `.rg-topbar__link[aria-current]`, `.rg-avatar` | |
| `.caixa a.conf`, `.conf-indice` | `.rg-secnav` | a que só lê apartada no fim |
| `.topo`, `h1.tit`, `p.subtit`, `.migalhas` | `.rg-pagehead`, `__title`, `__sub`, `.rg-crumbs` | |
| `details.porque`, `.porque-bloco` | `.rg-disc` (`__q`, `__body`) | sem memória |
| `.painel-filtros`, `.filtros`, `.conf-campo`, `.prop-campos label` | `.rg-field` (`__label`, `__input`, `__hint`, `__error`), `.rg-select` | 40px, borda 2px |
| `.interruptor`, `.chk`, `.escolhas` | `.rg-choice--switch`, `--checkbox`, `--radio` em `.rg-choices` | |
| `.modal`, `.modal-pe` | `.rg-dialog` (`__title`, `__body`, `__actions`) sobre `.rg-dialog-backdrop` | o motivo do abandono vive aqui |
| `.sou-menu` | `.rg-menu` (`__item`, `__sep`, `__head`) | |
| `.paginas`, `.ir-pagina` | `.rg-pager` | |
| `.fita`, `.fita a.hoje`, `.fita .e/.m` | fica como está (é específico do Hoje), só com os tokens novos | ver `EcraHoje` |
| `.hj-row`, `.hj-g`, `.chk`, `.av` | fica como está, com `.rg-choice` na caixa e `.rg-avatar` no dono | ver `EcraHoje` |
| `.cal-dia`, `.cal-it`, `.cal-mais`, `.cal-n` | fica como está, com os tokens novos e `.rg-tag` nos itens nossos | ver `EcraCalendario` |
| `.graf`, `.barras`, `.corpus-barra` | fica como está, cor das barras em `--brand` e `--seal` nas nossas | ver `EcraMercado` |
| `.entrar` | `EcraEntrar` | fora do molde |
| `.a-correr` | `.rg-tag--warning` com `dot` | o único que pisca |

O que **não** tem correspondência e se decide na fase 3: `.arvore`, `.leitor`, `.doc`, `.saude`, `.guardados`, `.ensaio`. São ecrãs de máquina (indicadores, leitura de peças, ensaio) e ficam com o CSS antigo sobre os tokens novos até se decidir se se desenham.

## Ícones

O `Icon` do bundle é React; no radar.py, que gera HTML em Python, os ícones entram inline: um dicionário `ICONES = {nome: '<svg …>'}` gerado a partir de `assets/Ícones` (troca `stroke="#2b363c"` por `stroke="currentColor"`) e uma função `icone(nome, tamanho=18)` que devolve o `<svg class="rg-icon">`. Num botão: `f'<button class="rg-btn rg-btn--primary">{icone("verificar")} Verificar agora</button>'`.

## Testes a mexer

`TestPeleNova` passa a exigir `data-theme` nos três moldes. `TestContrasteNosFundosReais` lê os tokens dos três temas e mede 4.5:1 (claro e escuro) e 7:1 (contraste). `TestPaginaSemNadaDeFora` continua a valer: as quatro fontes novas vêm de `/tipo/`, o CSP não muda. `TestAlvosDeTextoA24px` ganha os `.rg-btn--sm` (28px) e os `.rg-tab` (32px). `TestEcraEstreito` ganha `.rg-table` (rola dentro de si) e `.rg-stats` (uma coluna abaixo de 480px).
