# Estado do projecto

Última actualização: **4 de outubro de 2026**.

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
| `docs/diario/2026-10.md` | As sessões de outubro, a começar pelo L0 do plano de Outubro (as medições de 30/09) |
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

Funciona — **com a recolha do DR parada de 30/09/2026 às 08:00 até
chegar a release com o PR da apiVersion** (o DR mudou o script do ecrã e
o radar lia mal a versão; ver o diário de outubro). Os 30/09 e 1/10
entram sozinhos na primeira verificação depois dela, pela janela de 15
dias. Os números dos anúncios, das peças, das leituras e das
empresas são de **26/09/2026**; os do corpus, de **22/09/2026**.

| O quê | Quanto |
|---|---|
| Anúncios | 210 811 (**200 291 procedimentos**; a diferença são republicações ligadas ao original) |
| Com o texto integral | 185 886. O `detalhe_lido` está a **100%**: não há fila por ler |
| Empresas | **0** — a LATD, a empresa 2, que era de teste, saiu a 1/10/2026 a pedido dele (`--apagar-empresa`; a cópia de antes e a pasta dela estão em `copias/`). As empresas entram pelo pedido de acesso do site, já com o plano |
| Propostas, tarefas, contactos | 0 · 0 · 0 — são de cada empresa |
| Peças em disco | 436 documentos, de 79 concursos (em `pecas/`, 556 MB) |
| Leituras pelo modelo | 70, das quais **11 incompletas** (voltam a tentar-se sozinhas; desde a 3.ª ronda, também as das propostas abertas lidas com uma versão anterior da pergunta) |
| Corpus do Portal BASE | 2 009 640 contratos, 180 507 entidades (28/09/2026) |
| Alertas ligados · entidades seguidas | 0 · 0 — são de cada empresa |
| Contas | 2: a do dono, **sem empresa** (abre a `/plataforma`, a Conta dele e a Ajuda, e lê os Concursos e o Mercado), e mais nenhuma desde que a LATD saiu (1/10/2026) |
| Rotas Flask | 144 |
| Tabelas em `radar.db` | 20, as da plataforma (com as `sugestoes`, 4/10, os `eventos`, F2, os `convites`, F5, as `leituras_pedidas`, F7, as `reposicoes`, D17 a 26/09, o `segundo_factor`, 28/09, e os `planos` e as `sessoes_fechadas`, L2.1 a 1/10). As 16 da empresa (com as `notas_da_proposta` e os `documentos_da_empresa`, 26/09) vivem em `empresas/<id>/empresa.db` desde 23/09 (F1); hoje nenhuma, desde que a LATD saiu |
| Índices em `anuncios` | 16: dois a 17/09 para o filtro por entidade (+22 MB), o `ix_anuncios_cobre` a 26/09 para as abas com o perfil (+36 MB), e o `ix_anuncios_altera` a 29/09 (0,6 s a criar, no arranque). No corpus, o `ix_cpv_cobre` e o `ix_ctr_chave_cobre` (26/09, +144 MB), o `ix_nomes_chave` (29/09, 0,4 s a criar), e o índice de texto `contratos_fts` (29/09, lote 10: ~5 min a construir **em fundo** no primeiro arranque do painel, +609 MB). E o índice da **pesquisa geral** (1/10/2026): `pesquisa_fts` + `pesquisa_refs` no `radar.db`, ~115 MB, 30 a 60 s **em fundo** no primeiro arranque com esse código, numa cópia |
| Testes | **1 969**, em ~200 s, sem rede e sem tocar em nenhuma das duas bases verdadeiras (o corpus só desde 26/09) |
| Código | `radar.py` 39 599 linhas · `teste_radar.py` 28 723 · `empresa.py` 868 · `contas.py` 1 387 · `icones.py` 62 |
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

**O tempo das páginas lentas** (lote 4, 26/09/2026, medido numa cópia
das duas bases com o código de antes e o de depois, a quente, empresa
de ensaio com o perfil «45 ou 507 · 4 distritos · desde 20 000 €»):
Concursos 1,1–2,6 s → **0,6–1,3 s**; Propostas 0,75 → 0,20 s; Mercado
2,0 s → **0,65 s** (e 0,3 s num CPV); ficha do Município de Lisboa
1,05 → **0,33 s**. Todas as respostas levam `Server-Timing` (`base` e
`total`), que é por onde se mede a seguir. O pormenor está no diário.
**E na 3.ª ronda** (lote 7, 29/09/2026, a mesma medição, perfil «45,
50, 71 ou 909», TTFB a quente): o resumo do Mercado 8,6 s → **0,04 s**
(3,2 s na primeira visita da semana, guardado até o corpus mudar); o
Mercado 1,37 → 0,53 s; a pesquisa sem resultados 15–17 s → **0,29 s**;
a lista com `?ent=` 27–29 s → 0,38 s; a ficha de uma entidade sem NIF
5,0 → 0,12 s, e a de Lisboa 0,69 → 0,18 s; o Calendário 0,31 → 0,13 s.
**E no lote 10, «Nada lento»** (29/09/2026; as 200 rotas GET das
secções B e C do inventário, numa cópia das bases, empresas de ensaio
com os perfis «72 ou 48» e «45, 50, 71 ou 909», a 1.ª visita num
processo acabado de arrancar): antes, 19 rotas passavam de 1 s na
primeira visita e 12 de 0,5 s a quente; depois, **nenhuma passa de
0,5 s a quente** e só a primeira procura de um nome no «Entidade que
comprou» passa de 1 s. A primeira visita ao Mercado 1,6–19 s → **0,04
s**, ao resumo 1,1–16 s → 0,03 s, às Entidades 2,8–34 s → 0,15 s (as
contas vivem também no `contratos-memoria.db`, e uma thread aquece-as em
fundo: 15–31 s na primeira vez, 0 s depois de um reinício); a primeira
pesquisa de texto no Mercado 1,6–34 s → 0,2–0,6 s, e a quente 0,3–15 s
→ 0,07–0,22 s (índice FTS5); o distrito 0,65–0,75 → 0,4–0,46 s; a ficha
do anúncio −0,25 s em cada uma (um índice na `altera`); o Calendário
«Tudo» 383 → 63 KB de HTML. A tabela inteira está no PR do lote 10.

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
7. ~~**As três decisões que o L0 do plano de Outubro deixou**~~ —
   **respondidas a 1/10/2026** (`docs/diario/2026-10.md`): o lote da
   hora da plataforma **não vale a pena**; o **L6 sai do plano**; e o
   **L5 avança** devagar, com todos os contratos dos últimos dois anos e o
   inventário do BASE, depois de ele ver o ecrã.

## O que está implementado

**Está no `docs/FUNCIONAL.md`, ecrã a ecrã (§4), e só lá.** Esta secção
era uma segunda contagem da mesma coisa — treze pontos que repetiam as
dez subsecções de lá —, e foi por repetições assim que o manual chegou
a descrever um quadro que já tinha saído. Este ficheiro guarda os
**números medidos**; o que a aplicação faz tem dono.

Em duas linhas, para não teres de abrir: **Hoje** (`/`) · **Ponto de
situação** (`/situacao`) · **Concursos** (`/concursos`) e **Propostas**
(`/propostas`) · **Calendário** (`/calendario`, três filtros) · **Mercado** (`/contratos`) e **Entidades**
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
  — nunca segue o `master` a cada merge. A última é a **`v2.0.52`**, de
  4/10/2026 — **o anual com um mês grátis** (429 / 825 / 605 €) **e a
  segunda leva da 5.ª ronda**. Antes dela, a `v2.0.51`, de
  4/10/2026 — **o espaço das sugestões** (`/sugestoes`, com captura de ecrã,
  e o resumo por dia ao dono) e **os campos fechados só aceitam o que se
  pede** (o NIF com letras, os preços «20 mil», as datas impossíveis).
  **Traz migração (pequena): cópia antes.** A `v2.0.50`, de
  4/10/2026 — **os acabamentos da 5.ª ronda e a frase da fatura nos
  termos** (sete dias antes no mensal, trinta no anual). Antes dela, a
  `v2.0.49`, de
  4/10/2026 — **o concurso público flexível**: quando o anúncio o diz, a
  tarefa da audiência prévia conta 3 dias úteis em vez de 5, e a ficha
  avisa ao pé do prazo. Sem migração. A `v2.0.48`, do mesmo dia — **o preço estimado na ficha ao lado do preço base** («estimado:
  o anúncio não indica» enquanto o DR o der a 0,00 EUR), a ferramenta que
  mede o DL 177/2026 (`ferramentas/mede_dl177.py`), e os Concursos por NIF
  e por palavras pelos índices, com o CSV mais rápido. Sem migração. A
  `v2.0.47`, do mesmo dia — **a 4.ª e a 5.ª rondas de testes e as decisões dele**:
  criar empresas na plataforma, o pedido de acesso com cinco campos, o
  site sem o vocabulário da aplicação, só o gestor muda os alertas,
  apagar uma empresa sem copiar a base, o menu do site no telemóvel e o
  primeiro do dia mais rápido. Antes dela, a `v2.0.46`, de 4/10/2026 —
  **as correcções da auditoria de 1/10** antes do anúncio: as
  abas do Mercado à vista nas Entidades, o foco a âmbar no topo azul do
  site e do entrar, as tarefas da ficha atrás de «adiar · quem», 44 px no
  toque, e o perfil do pedido com todos os CPV curtos da mensagem
  (`docs/diario/2026-10.md`). Sem migração. A `v2.0.45`, do mesmo dia —
  **a leitura das peças confere as palavras e as
  quantidades** (um nome, uma sigla ou uma quantidade que não esteja nas
  peças fica «[confirmar]»; saem os restos do molde da pergunta) e **o
  Gemini Flash-Lite entra na cadeia** no lugar do 3.6-flash. A `v2.0.44`,
  de 3/10/2026: **a conta guarda o e-mail do convite**, e o «esqueci-me da
  palavra-passe» encontra-a por ele (o ensaio do percurso de 1/10 provou que
  falhava a quem escolhesse um utilizador diferente do e-mail); e o apagar
  de uma empresa tira também o plano dela. **Traz migração (pequena).** A
  `v2.0.43`, do mesmo dia — **o resumo do Mercado volta a abrir** (dava 500 desde 2/10)
  e **o preço estimado do DL 177/2026** numa coluna própria, que nunca
  se confunde com o preço base (e o «Valor Estimado do Lote» deixou de
  ser lido como preço base do lote); leva também a leitura das condições
  de pagamento (L4), a taxa de vitória sem os ajustes directos e os termos
  corrigidos nos três pontos graves. **Traz migração: cópia antes.** A
  `v2.0.42`, de 1/10/2026 — **os planos Solo, Duo e Corporate**: o Equipa deu lugar ao
  Duo, de duas pessoas, e os três planos têm exactamente o mesmo — só muda
  o número de pessoas (o cofre abre também no Solo). A `v2.0.41`, do mesmo
  dia — **o campo 11 da leitura vai primeiro ao nemotron, com o
  dobro do recorte** (as frases-prova do grupo «o modelo ignorou»
  passam de 11 para 19 de 31, as do «faltava espaço» de 0 para 9 de 15,
  sem números inventados), e o fim do dia do Gemini reconhecido. A
  `v2.0.40`, do mesmo dia: **a recolha do Diário da República volta a funcionar**: o
  portal foi republicado na noite de 29 para 30/09 e o script de onde o
  radar lê a apiVersion ganhou mais um argumento; a leitura passou a
  ancorar-se no caminho da acção, e o `/saude` dá 503 à terceira
  verificação seguida que falha. A `v2.0.39`, do mesmo dia — **os planos no código (L2.1)**: o plano de cada empresa, o
  limite de utilizadores, a sessão única do Solo e o cofre fechado no
  Solo; e a LATD, de teste, saiu. A `v2.0.38`, do mesmo dia — **os planos novos: Solo, Equipa e Corporate**, com a leitura
  das peças por IA em todos, o Solo com uma sessão de cada vez e o plano
  anual pago de uma vez (Solo 429 €, Equipa 825 €, fundador 605 €). A
  `v2.0.37`, do mesmo dia — **a recolha dos concorrentes do Portal BASE** (L5): o painel
  lê-os em fundo, contrato a contrato, e a ficha do concurso mostra «Quem
  costuma concorrer», com o desconto de cada um; e a pesquisa geral na
  barra (Ctrl+K), o «esqueci-me» por e-mail, e os achados de UX que
  ficavam para depois de 5/10 nos Concursos, nas Propostas, nas fichas,
  no Mercado, nas Entidades, na Situação e na Conta. A `v2.0.36`, de
  30/09/2026 — **o início do plano de Outubro**: o site com os três
  planos e a oferta de fundador, os termos e a privacidade dos planos
  pagos, o pedido de acesso com o NIF e o plano, a citação da leitura
  que abre a peça na página, o registo dos envios dos alertas, as
  medições do L0, a promessa de continuidade no site e nos termos, o
  Gemini da Google na cadeia da leitura das peças, antes da reserva, e as
  correções de UX das três auditorias de 30/09. A `v2.0.35`, do mesmo dia — **a plataforma na lista é
  texto**, e não uma etiqueta verde que todas tinham. A `v2.0.34`, do mesmo dia — **a página e os números da leitura das peças passam a
  ser do código**: cada linha do resumo leva a página onde está de facto
  no texto enviado (e não a que o modelo escreveu), e a conferência dos
  números deixou os falsos alarmes (24 marcas, 17 falsas → 9, 1 falsa).
  A `v2.0.33`, do mesmo dia, **a lista ordena-se no cabeçalho do Prazo**, como numa
  folha de cálculo. A `v2.0.32`, do mesmo dia — **o cartão das listas da proposta com os campos do
  sistema**, em duas colunas, e o aspecto a dizer só «Como o sistema». A
  `v2.0.31`, do mesmo dia — **o site fala da procura plataforma a plataforma**, e não
  de abrir o Diário da República. A `v2.0.30`, do mesmo dia — **a fotografia no «Quem está por trás» do site**. A
  `v2.0.29`, do mesmo dia — **a página inicial depois da auditoria** (os números
  verdadeiros, as datas do exemplo a contar de hoje, quem está por trás,
  quatro perguntas novas, o site no Acordo Ortográfico). A `v2.0.28`, de
  29/09/2026 — **as descrições da inicial e dos termos à medida do
  Google** (a da inicial tinha 166 caracteres). A `v2.0.27`, do mesmo
  dia — **o site pronto para os motores de busca e os agentes de
  IA** (o robots em lista branca, o `<lastmod>` no mapa, o JSON-LD em
  todas as páginas, o `/llms.txt`, o `noindex` no `/entrar`) e **todos
  os e-mails saem bonitos, e o convite segue por e-mail**. A `v2.0.26`,
  do mesmo dia — **a fita do Hoje começa ontem**, e não à segunda-feira
  (as setas andam 7 dias; o balde passa a «Próximos N dias»). A
  `v2.0.25`, do mesmo dia — **o Mercado sem perfil também aquece em
  fundo** (o «ver tudo», e o que o dono vê: 33 s na primeira visita com
  a v2.0.24). A
  `v2.0.24`, do mesmo dia — **o lote 10 da 3.ª ronda, «Nada lento»**: as contas do
  Mercado guardam-se no `contratos-memoria.db` e aquecem-se em fundo (a
  primeira visita ao Mercado, que chegava a 25 s, passa a ~0,1 s), a
  pesquisa de texto vai por um índice FTS5 (construído em fundo no
  primeiro arranque, ~5 min e +609 MB) e o Calendário «Tudo» passa de
  383 para 63 KB. A `v2.0.20`, do mesmo dia: **os lotes 2 a 7 da 3.ª ronda** (pessoas e autoria;
  números, Hoje e escada; a leitura que diz que não há; a porta e o
  suporte; acessibilidade e telemóvel; o desempenho do Mercado, das
  listas e das fichas) e **61 procedimentos que estavam escondidos
  como alteração voltam às listas** (24 de prazo aberto); na acingov o
  botão abre a página do procedimento. A `v2.0.19`, do mesmo dia:
  **a segunda ronda da leitura das peças** (a régua passa
  de 52 para 82 de 88 passagens: o local, a lista inteira até ao fim do
  artigo, o objecto das obras pela memória descritiva, o SLA, a
  dimensão da equipa, o limiar do preço anormalmente baixo) e **o lote 1
  da 3.ª ronda** (gravar uma vez e dizer a verdade: um POST repetido não
  grava duas vezes). A `v2.0.18`, de 28/09/2026: **a ficha do concurso nova**: «Para decidir» com os
  oito factos, «O que as peças pedem» marcado uma vez como rascunho e
  com a equipa numa tabela, o mercado em três números, e o prazo da
  cadeia nas republicações. A `v2.0.17`, do mesmo dia: **as reservas gratuitas voltam a ler**: o Cerebras
  (o mesmo gpt-oss-120b, 1 milhão de tokens por dia, com chave), a
  NVIDIA com o nemotron-3-ultra e o raciocínio desligado, e um modelo
  gratuito no OpenRouter. A `v2.0.16`, do mesmo dia: **a leitura cabe no limite da Groq, e a reserva volta
  a ler** (a Groq com o gpt-oss-20b; a NVIDIA estava morta desde 3/09).
  A `v2.0.15`, do mesmo dia, trouxe **o segundo factor da conta do dono** (a app de
  autenticação, com códigos de recuperação e aparelhos de confiança;
  pede a palavra-passe para ligar e desligar) e **a leitura das peças
  validada e corrigida** (chegam ao modelo 46 de 55 passagens em vez de
  20; a habilitação e a caução do anúncio no essencial; a leitura
  marcada como rascunho). A `v2.0.14`, do mesmo dia, trouxe **a página de entrar volta ao início** (o logótipo liga
  ao site, e há um «Voltar ao início» por cima do título) e **os campos
  do site sem o magenta**. A `v2.0.13`, do mesmo dia, pôs **data e
  identificador nos e-mails do radar** (`Date` e `Message-ID`; saíam
  sem eles, e há servidores que os tomam por spam). A `v2.0.12` trouxe **o `contacto@miragov.pt`** no site, na privacidade e na
  acessibilidade (o correio do domínio passou a existir nesse dia, na
  caixa do alojamento do domínios.pt), e **a proposta de cada empresa**:
  a tipologia e a unidade de negócio passam a listas do Perfil da
  empresa, os documentos que o Programa pede (campo 12) substituem o CV
  e a proposta técnica sim/não, os motivos de perda passam a genéricos,
  e a leitura das peças pede o campo 11 conforme o tipo de contrato. A
  `v2.0.11`, de 26/09/2026, foi **o dono apaga uma empresa no painel** (com o nome
  escrito para confirmar e a cópia antes) e o aviso sem o anel magenta.
  A `v2.0.10`, do mesmo dia, foi **a ronda em PC**: o layout dos ecrãs grandes, o
  Mercado e os gráficos (PC-A), as mensagens que enganavam, a página
  dos erros, o convite sem duplicar, a suspensão com confirmação e as
  regressões da segunda ronda (PC-B). A `v2.0.9`, do mesmo dia, foi
  **o lote 5 e as decisões do dono sobre a segunda ronda**:
  texto e desenho, a Situação e a Ajuda na barra, a empresa na barra, o
  arranque guiado, a triagem sem recarregar, as regras e datas da
  proposta, o cofre de documentos, o Calendário novo, a barra em baixo
  no telemóvel, o alto contraste, a declaração de acessibilidade e a
  página do dono (uma por empresa, «ver como», saúde, correio). A
  `v2.0.8`, do mesmo dia, foi **os quatro primeiros lotes da segunda ronda de testes com
  20 perfis**: cada número abre a sua lista e o «Perfil da empresa»; as
  regras dos dados, a importação que se desfaz, as palavras-passe e o repor
  por ligação; o telemóvel e a acessibilidade; e o desempenho (2 a 4×
  mais rápido nas listas e no Mercado). A `v2.0.7`, do mesmo dia, foi **uma correcção de segurança**: as páginas e os
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

Julgar se a leitura das peças pelo modelo presta. **Julgado a
28/09/2026** (`docs/historico/LEITURA-VALIDADA.md`): quatro agentes com
perfis diferentes passaram as 70 leituras a pente, e **não prestava
para decidir sem abrir as peças** — o defeito era o «não consta» falso,
porque a resposta não chegava ao modelo (20 de 55 passagens). As
correcções desse dia põem 44 de 55 a chegar (com pedidos que cabem no
limite da Groq), e a ficha passou a marcar
a leitura como rascunho. Relidas e julgadas outra vez a 29/09/2026, duas
rondas no mesmo dia: a régua vai em 103 de 113 passagens, cada linha da
leitura cita a página, e um número que não está nas páginas lidas fica
marcado para confirmar (`docs/diario/2026-09.md`). Desde 4/10/2026
conferem-se também as palavras com peso e as quantidades junto do
artigo, e saem os restos do molde (`docs/diario/2026-10.md`: nas 77
leituras de 3/10, 18 linhas marcadas pelas palavras, 11 verdadeiras).
**Falta reler com o código de agora e voltar a julgar**; até lá, a
leitura não se anuncia.
