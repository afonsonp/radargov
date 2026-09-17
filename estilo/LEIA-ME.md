# `estilo/` — o que aqui está, e de onde veio

Ficheiros de terceiros, alojados aqui de propósito: o painel envia
`default-src 'self'` e **não pede nada a nenhum domínio de fora**. Um
`@import` de um CDN morria à chegada, e é essa a regra que os mantém
neste sítio.

| Ficheiro | O que é | Origem |
|---|---|---|
| `easings.min.css` | ~30 curvas de aceleração (`--ease-*`) | [Open Props](https://open-props.style), MIT |
| `animations.min.css` | 23 `@keyframes` e os `--animation-*` que lhes chamam | Open Props, MIT |
| `open-props-LICENSE.txt` | A licença MIT do Open Props | — |

**Porquê só estes dois, e não o Open Props inteiro** (28,9 KB): o resto
são cores, gradientes, sombras e escalas tipográficas, e disso o radar
já tem o seu — escolhido, medido e escrito no `docs/design.md`. Trazer
as cores dele era pôr duas paletas a discutir. O que faltava era
**movimento**, e é só isso que estes dois dão.

Entram no `CSS_TUDO` no arranque (`carregar_estilos_de_terceiros()`),
por isso viajam dentro da folha em cache e não custam um pedido a mais.
**Se sumirem, o painel continua a servir**: as regras que os usam caem
para os valores de omissão do browser, e a única coisa que se perde é a
suavidade.

Actualizar é descarregar por cima e correr os testes — o resumo no nome
da folha (`/estilo/<etiqueta>.css`) muda sozinho e invalida a cache.
