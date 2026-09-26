# Estado do projecto

Última actualização: **26 de setembro de 2026**.

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

O **Mira Gov** (era Radar Gov até 24/09/2026). Aplicação local em Python que vigia os anúncios de contratação pública
publicados no Diário da República, série II, **parte L**. Guarda tudo
numa base SQLite e mostra num painel Flask. Verifica sozinha de hora a
hora, das 08:00 às 20:00, por um temporizador do systemd, corre em Ubuntu em
`~/Desktop/radar`, e responde em `http://127.0.0.1:8765` e, por um túnel
com nome da Cloudflare, em **`https://miragov.pt`** (o `miragov.com` e o
`radargov.pt` vão lá ter). Tem login e três
níveis: o dono da plataforma, e o `admin` e o `tester` de cada empresa.
**É multi-empresa desde 23/09/2026, e hoje não tem nenhuma**: a LATD
saiu a pedido dele, para voltar a entrar pelo pedido de acesso do site.

Substitui a Armilar, produto da Vortal que a empresa pagava a 200 euros
por mês. Princípio de desenho, decidido depois de uma primeira versão
que filtrava por pontuação: **não se filtra nada à entrada** — entra
tudo o que a parte L publicar, e a triagem faz-se no painel.

## Como está a correr

Funciona. Os números da plataforma são de **22/09/2026**, lidos das
duas bases; os das empresas, de **24/09/2026**.

| O quê | Quanto |
|---|---|
| Anúncios | 210 379 (**199 925 procedimentos**; a diferença são republicações ligadas ao original) |
| Com o texto integral | 185 454. O `detalhe_lido` está a **100%**: não há fila por ler |
| Empresas | **1** — a LATD, empresa 2 desde 24/09 (a empresa 1 foi apagada a 23/09 com `--apagar-empresa`) |
| Propostas, tarefas, contactos | 4 · 8 · 0 — da LATD (25/09/2026) |
| Peças em disco | 274 documentos, de 50 concursos (em `pecas/`, 277 MB) |
| Leituras pelo modelo | 44, das quais **7 incompletas** (voltam a tentar-se sozinhas) |
| Corpus do Portal BASE | 2 004 511 contratos, 180 090 entidades |
| Alertas ligados · entidades seguidas | 0 · 0 — são de cada empresa |
| Contas | 2: a do dono, **sem empresa** (abre a `/plataforma` e lê os Concursos e o Mercado), e a admin da LATD |
| Rotas Flask | 98 |
| Tabelas em `radar.db` | 16, as da plataforma (com os `eventos`, F2, os `convites`, F5, as `leituras_pedidas`, F7, e as `reposicoes`, D17 a 26/09). As 14 da empresa vivem em `empresas/<id>/empresa.db` desde 23/09 (F1); hoje só a da LATD, a empresa 2 |
| Índices em `anuncios` | 14, dos quais dois novos a 17/09 para o filtro por entidade (+22 MB) |
| Testes | **1 271**, em ~118 s, sem rede e sem tocar na base verdadeira |
| Código | `radar.py` 27 239 linhas · `teste_radar.py` 17 160 · `empresa.py` 802 · `contas.py` 607 · `icones.py` 62 |
| As duas bases | `radar.db` **1,32 GB** (o `anuncios.texto` sozinho vale ~840 MB) · `contratos.db` **2,67 GB**, fora do git |

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

## O que espera pelo Afonso

Escrito a 24/09/2026, para fechar nas próximas conversas. Por ordem:

1. ~~Entregar o design system novo~~ — **feito a 24/09/2026**: o
   pacote Mira Gov entrou em onze PR (#50 a #61): o prefixo `mg-`, a
   marca do olho, o nome, a barra de cinco itens, os oito ecrãs fiéis à
   referência, e a limpeza das variáveis antigas e das pontes. Chegou
   à instalação pelas releases `v2.0.1` e `v2.0.2`.
2. ~~Pôr os domínios do MiraGov na Cloudflare~~ — **feito a
   25/09/2026**: o túnel responde por `miragov.pt`, `miragov.com` e
   `radargov.pt`, e o painel manda os outros para o `miragov.pt`. O
   monitor do UptimeRobot passou para `https://miragov.pt/saude` no
   mesmo dia.
3. ~~Confirmar as cópias fora do PC~~ — **feito a 25/09/2026**: a
   linha «Fora deste PC» diz «ok: 2026-09-25 08:00», e o bucket do B2
   tem as cópias da empresa 2 e das contas. Fecha o R2 do `BACKLOG.md`.
4. ~~Criar a primeira empresa~~ — **feito a 24/09/2026**: a LATD
   voltou pelo pedido de acesso, como empresa 2.
5. **Pedir ao suporte do GitHub** que limpe os `refs/pull` dos PR
   antigos (support.github.com, repositório `afonsonp/radargov`: «purge
   cached refs/pull after history rewrite»). Guardam commits de antes da
   reescrita, com o `config.json` e a triagem.
6. **Antes de cobrar o primeiro cliente:** falar com um contabilista
   sobre abrir uma sociedade. O NIPC dela entra no `operador` do
   `config.json` no lugar do teu nome, e os termos passam a ser dela.

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

- **Os dois temporizadores do systemd** (`radar-hora.timer` e
  `radar-contratos.timer`, do `agendar.sh`) são o que faz o
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
- **Nada sai deste computador sozinho.** Desde 23/09/2026 a
  verificação não faz commit nem push: o `triagem.jsonl` exporta-se por
  empresa para `empresas/<id>/triagem.jsonl`, só no disco, e o
  `config.json` também saiu do git. As cópias ficam em `copias/`, no
  mesmo disco, e **desde 24/09/2026 também fora dele**: a primeira
  verificação do dia manda a de cada empresa e a das contas, cifradas,
  para o Backblaze B2 (bucket na UE, `eu-central-003`; ensaio de ida e
  volta feito nesse dia). A palavra-passe da cifra está com o Afonso,
  fora do PC.
- **A instalação só traz código novo quando o Afonso corre
  `actualizar.sh`**, e só até à última tag publicada como GitHub Release
  — nunca segue o `master` a cada merge. A última é a **`v2.0.7`**, de
  26/09/2026 — **uma correcção de segurança**: as páginas e os
  ficheiros das peças ficavam na cache da Cloudflare e chegavam a quem
  não tinha sessão; tudo o que não é público sai agora com `private`
  (purgar a cache da Cloudflare depois). A `v2.0.6`, de
  25/09/2026, foi **o que o teste com dez perfis pediu de novo**: o
  convite pelo admin, o «Como funciona» com o glossário, o alerta que
  avisa logo, o filtro por distrito e por preço base (uma migração lê o
  distrito de ~150 mil anúncios na primeira arrancada), a lista por
  prazo, as peças num ZIP e a comparação de preço lote a lote. A
  `v2.0.5`, do mesmo dia, foi **o resto do teste com dez perfis de utilizador**: cada
  número abre a lista que o confirma, os erros que enganavam (o aviso
  assinado, as peças, os títulos com controlos do Windows-1252), o
  telemóvel e a acessibilidade, e as tarefas que já nasceriam atrasadas.
  A `v2.0.4`, do mesmo dia, foram **três erros que estragavam dados** (o
  preço com espaços, dois separadores, o «ver tudo»). A `v2.0.3`, do mesmo dia, foi **o miragov.pt**: o painel passa ao endereço novo, e o
  miragov.com e o radargov.pt vão lá ter. A `v2.0.2`, do mesmo dia, foi
  **a varredura**: os ícones nos botões, e as correcções
  das duas voltas (a página já não foge de lado no telemóvel, a escada
  pede no acto o que falta, o alerta pergunta antes de apagar, uma porta
  por gesto na ficha, o NIF confere, seguir entidades sem NIF, o Mercado
  por texto e a ficha mais depressa, e a acessibilidade que o axe
  apontava). A `v2.0.1`, de 24/09, trouxe o **Mira Gov**: o nome, a
  marca do olho, a barra de cinco itens e os ecrãs do sistema de
  desenho. **Reinicia sempre o painel**, mesmo quando não há
  nada a trazer: o painel só lê o `radar.py` ao arrancar.
- **As últimas migrações correram a 23/09/2026**: a F1 passou as
  tabelas da empresa para `empresas/1/empresa.db` (`separar_empresa()`,
  com cópia antes e as contagens comparadas antes de apagar; 13 s no
  primeiro arranque, quase tudo a cópia), a F2 levou 397 linhas do
  histórico para os `eventos`, e a F3 partiu o `config.json`
  (`separar_config_da_empresa()`). (As
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
pedaço do documento que a sustenta) e há 44 leituras feitas, 7 delas
incompletas. Falta passá-las a pente.
