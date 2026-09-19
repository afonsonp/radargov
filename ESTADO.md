# Estado do projecto

Última actualização: **19 de setembro de 2026**.

Este ficheiro diz **como está o radar hoje**, e só isso. O histórico
está no diário: sempre que este ficheiro volta a crescer para diário —
já aconteceu duas vezes — o que ele contava vai inteiro para lá e este
volta ao formato. Onde está o resto:

| Onde | O quê |
|---|---|
| `LEIA-ME.md` | O manual: instalar, correr, refazer as capturas |
| `CLAUDE.md` | As regras da empresa, para quem trabalha no código |
| `docs/FUNCIONAL.md` | **O documento funcional**: os dados, os conceitos, os ecrãs, as regras, e o que ainda se pode fazer com o que há |
| `docs/armadilhas.md` | O que não é óbvio, por área — **lê a área antes de lhe mexer** |
| `docs/design.md` | O caminho do aspecto: a direcção, a letra, a cor, os botões |
| `docs/referencia.md` | Como cada parte foi feita, e porquê assim |
| `docs/seguranca.md` | As seis coisas a rever, por ordem de gravidade |
| `docs/diario/2026-08.md` | As sessões de 28 a 31 de agosto |
| `docs/diario/2026-09.md` | As sessões de setembro |
| `docs/historico/` | Auditorias e propostas com data fechada — instantâneos |
| `BACKLOG.md` | O que falta, com prioridade |

---

## O que isto é

Aplicação local em Python que vigia os anúncios de contratação pública
publicados no Diário da República, série II, **parte L**. Guarda tudo
numa base SQLite e mostra num painel Flask. Verifica sozinha às 09:00 e
às 17:00 por temporizadores do systemd, corre em Ubuntu em
`~/Desktop/radar`, e responde em `http://127.0.0.1:8765` e, por um túnel
com nome da Cloudflare, em **`https://radargov.pt`**. Tem login e dois
papéis (`admin` e `tester`).

Substitui a Armilar, produto da Vortal que a empresa pagava a 200 euros
por mês. Princípio de desenho, decidido depois de uma primeira versão
que filtrava por pontuação: **não se filtra nada à entrada** — entra
tudo o que a parte L publicar, e a triagem faz-se no painel.

## Como está a correr

Funciona. Os números são de **17/09/2026**, lidos das duas bases —
salvo os testes e as linhas de código, remedidos a 19/09.

| O quê | Quanto |
|---|---|
| Anúncios | 210 004 (**199 731 procedimentos**; a diferença são republicações ligadas ao original) |
| Com detalhe lido | 185 079 |
| Propostas na escada | **77** — perdido 16 · não fomos 14 · ganho 13 · por analisar 10 · submetido 8 · a preparar 7 · relatório 5 · cancelado 4 |
| Tarefas por fazer | 52 |
| Contactos | 26 |
| Peças em disco | 265 documentos, de 42 concursos |
| Leituras pelo modelo | 42, das quais **8 incompletas** (voltam a tentar-se sozinhas) |
| Corpus do Portal BASE | 2 000 340 contratos, 179 823 entidades |
| Alertas ligados · entidades seguidas | 0 · 0 — o `email.para` tem destino desde 16/09, falta ligar um alerta |
| Contas | 2 |
| Rotas Flask | 80 |
| Tabelas em `radar.db` | 23 |
| Índices em `anuncios` | 14, dos quais dois novos a 17/09 para o filtro por entidade (+22 MB) |
| Testes | **1 074**, em ~105 s, sem rede e sem tocar na base verdadeira |
| Código | `radar.py` 23 165 linhas · `teste_radar.py` 13 728 · `empresa.py` 641 · `contas.py` 302 |
| As duas bases | `radar.db` **1,29 GB** (o `anuncios.texto` sozinho vale ~840 MB) · `contratos.db` **2,6 GB**, fora do git |

**O CSS não viaja em cada clique** desde 17/09/2026: está em
`/estilo/<etiqueta>.css`, guardado para sempre pelo browser, e a
etiqueta é o resumo do conteúdo — mudar uma linha muda o endereço. A
abertura passou de 144 KB para 60 KB, e cinco ecrãs de ~590 KB para
179 KB. O movimento (curvas e `@keyframes`) vem do Open Props alojado
em `estilo/`, e desliga-se inteiro com `prefers-reduced-motion`.

**As duas bases não se cruzam em SQL**: cada uma tem a sua ligação
(`liga()` e `liga_corpus()`) e quem junta os resultados é o Python. O
tamanho da `anuncios` é um número de **desempenho**, não de arrumação:
cada varrimento arrasta os 840 MB de texto do disco, e é por isso que as
contagens do painel vão por índice de cobertura.

## O que está implementado

**Está no `docs/FUNCIONAL.md`, ecrã a ecrã (§4), e só lá.** Esta secção
era uma segunda contagem da mesma coisa — treze pontos que repetiam as
dez subsecções de lá —, e foi por repetições assim que o manual chegou
a descrever um quadro que já tinha saído. Este ficheiro guarda os
**números medidos**; o que a aplicação faz tem dono.

Em duas linhas, para não teres de abrir: **Hoje** (`/`) · **Ponto de
situação** (`/situacao`) · **Concursos** (`/concursos`, as dez ranhuras
e o calendário) · **Mercado** (`/contratos`) e **Entidades**
(`/entidades`) · as fichas do anúncio, da entidade e da proposta ·
**Configurações** em nove secções · alertas e resumo diário · as peças
lidas pelo modelo · a Vortal como segunda fonte · cópia diária com
ensaio de restauro.

## O que não corre sozinho, e é preciso saber

- **Os três temporizadores do systemd** (`agendar.sh`) são o que faz o
  radar verificar sem ninguém. Se faltarem, só recolhe com o painel
  aberto — e o relógio interno recupera os slots falhados, o que faz a
  tabela `slots` parecer certa. O painel avisa a vermelho.
- **Em Linux o painel corre como serviço** (`radar-painel.service`).
  Sem `loginctl enable-linger`, o serviço e os temporizadores morrem com
  o logout. A pasta está no disco interno de propósito.
- **As capturas `curl_*.txt`** são a forma do pedido ao DR. O token não
  expira (medido a 2/09/2026), mas se o portal mudar de forma é por elas
  que se refaz — secção 3 do `LEIA-ME.md`. Não se editam à mão; um hook
  bloqueia-o.
- **O push é do ramo inteiro.** A verificação faz commit do
  `triagem.jsonl` e depois `git push origin master`. Qualquer commit
  deixado no `master` sai sozinho na volta seguinte. Desliga-se com
  `"triagem_no_git": false`.
- **A instalação só traz código novo quando o Afonso corre
  `actualizar.sh`**, e só até à última tag publicada como GitHub Release
  — nunca segue o `master` a cada merge. A última é a **`v1.8.1`**,
  de 19/09/2026. **Reinicia sempre o painel**, mesmo quando não há
  nada a trazer: o painel só lê o `radar.py` ao arrancar.
- **As últimas migrações correram a 17/09/2026** — as colunas novas da
  `propostas` e do `historico` — e demoraram **menos de 0,1 s** sobre
  210 mil anúncios, porque nenhuma toca na tabela `anuncios`. (As
  regras de quando fazer cópia e quando ensaiar estão no `CLAUDE.md`,
  banda 1.)

## O que fica de fora, e porquê

- **O Portal BASE não traz anúncios novos.** Medido: os «anúncios» do
  BASE são o mesmo universo do DR, e o dump é semanal, portanto mais
  atrasado. Abaixo dos limiares não existe anúncio nenhum.
- **A pesquisa no acervo das peças** foi implementada e retirada no
  mesmo dia (30/08/2026): as peças só existem depois de se marcar
  interesse, por isso chegava sempre tarde para ajudar a decidir. A
  procura **dentro** de um documento existe e é outra coisa.
- **O OCR das digitalizações** saiu a 3/09/2026.
- **Dois becos das peças ficam, e só passam pelo modelo documentos
  públicos** — as duas regras estão no `docs/FUNCIONAL.md` §3.6. Ficam
  nesta lista porque são **limites de âmbito**, e é isso que esta
  secção inventaria; o que elas dizem lê-se lá.

## O ponto que falta para a v1

Julgar se a leitura das peças pelo modelo presta. A ferramenta existe
(`ensaio-de-leitura <ref>`, que põe cada linha da resposta ao lado do
pedaço do documento que a sustenta) e há 42 leituras feitas, 8 delas
incompletas. Falta passá-las a pente.
