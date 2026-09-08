# Estado do projecto

Última actualização: **8 de setembro de 2026**.

Este ficheiro diz **como está o radar hoje**. O histórico saiu daqui no
mesmo dia: era um ficheiro de 5 297 linhas onde o topo envelhecia a cada
sessão que só acrescentava no fim. Onde está o resto:

| Onde | O quê |
|---|---|
| `LEIA-ME.md` | O manual: instalar, correr, refazer as capturas |
| `CLAUDE.md` | As regras da casa, para quem trabalha no código |
| `docs/armadilhas.md` | O que não é óbvio, por área — **lê a área antes de lhe mexer** |
| `docs/referencia.md` | Como cada parte foi feita, e porquê assim |
| `docs/diario/2026-08.md` | As sessões de 28 a 31 de agosto |
| `docs/diario/2026-09.md` | As sessões de setembro |
| `docs/historico/` | Auditorias e propostas com data fechada |
| `BACKLOG.md` | O que falta, com prioridade |

---

## O que isto é

Aplicação local em Python que vigia os anúncios de contratação pública
publicados no Diário da República, série II, **parte L**. Guarda tudo
numa base SQLite e mostra num painel web local, em
`http://127.0.0.1:8765`. Verifica sozinha às 09:00 e às 17:00, por
tarefas do Windows — ou, em Linux, por temporizadores do systemd.

**Desde 8/09/2026 corre também em Ubuntu**, em
`/home/afonso/Desktop/radar` no disco interno (esteve umas horas no
disco «Matriz», NTFS, que só é montado ao entrar na sessão gráfica —
mudou-se nesse mesmo dia por isso): um `.venv`
criado pelo `instalar.sh` faz de `python/` + `libs/`, cada `.bat` tem
o seu `.sh` (e a 8/09/2026 os `.bat` saíram do repositório: a pen do
Windows deixou de existir), e o `agendar.sh` cria os três temporizadores e o painel
como serviço do utilizador. É o passo antes de este computador servir
o radar para fora — o plano disso é o `docs/historico/ONLINE.md`.
**A etapa 1, o login, ficou feita a 8/09/2026** (`contas.py`; a
conta cria-se com `--criar-utilizador`): tudo exige sessão, excepto
um pedido vindo deste computador sem túnel a meio, que entra sem
login (`acesso_livre_local`). **E a etapa 3, o endereço fixo, também
ficou feita nesse dia: o painel está em `https://radargov.pt`**, por
um túnel com nome da Cloudflare a correr como serviço
(`radar-tunel.service`, do `tunel_fixo.sh`); o painel continua a
atender só em `127.0.0.1`, e quem abre o domínio cai no `/entrar`.
Os links do e-mail já dizem `radargov.pt` (`endereco_publico` no
`config.json`). **E a etapa 2 também, ao fim da tarde**: o menu de
Configurações em `/configuracoes/<seccao>`, sete secções (interesse,
alertas, recolha, leitura das peças, capturas, cópias, conta), com
Alertas a sair da barra para lá. O plano `ONLINE.md` está feito por
inteiro, pela via B (o PC de casa exposto por túnel). A bateria de
testes — 802 — passa inteira no Python 3.14 do Ubuntu. **E desde a
tarde de 8/09/2026 o painel serve no telemóvel**: abaixo de 900 px a
barra passa para cima, as grelhas de duas colunas passam a uma, e o
que é largo (quadro, tabelas, abas, índice da ficha) rola dentro de
si; medido a 375 px em oito páginas, nenhuma alarga a página.

Substitui a Armilar, produto da Vortal que a empresa paga a 200 euros por
mês, com má experiência de uso e falhas de ingestão. Corre no PC do
Afonso, de uma pen, e não depende de nada da empresa.

Princípio de desenho, decidido depois de uma primeira versão que filtrava
por pontuação: **não se filtra nada à entrada**. Entra tudo o que a parte
L publicar, e a triagem faz-se no painel.

## Como está a correr

Funciona. Os números são de **4/09/2026**, lidos das duas bases.

**O acervo.** **209 177 anúncios, onze anos deles** (06/01/2015 a
04/09/2026) — **199 080 procedimentos**, porque 10 097 são republicações
(«Alteração do Anúncio de procedimento n.º …») ligadas ao original e
fora de todas as listas. Eram 66 498 na manhã de 4/09/2026: o
`--historico 2015-01-01 2024-08-19` trouxe **142 063 num varrimento de
3h09**, 118 janelas de 30 dias, **zero falhadas**. A partir daqui a
rotina diária traz ~65 por dia útil, mais as **consultas preliminares
da Vortal** (36 até agora, `fonte='vortal'`), o tipo que a parte L não
publica.

**A cobertura está verificada, e conta-se por referência.** Nove meses
espalhados por 2015, 2016, 2018, 2019, 2020, 2021, 2023 e 2024: as
refs que o DR devolve para cada mês estão **todas** na base, 100% nos
nove. Não se afere isto comparando totais por data — ver a armadilha
no `docs/armadilhas.md`, que custou um falso alarme de 4 390 anúncios
«em falta» que estavam todos lá.

**O funil, e onde ele aperta.**

| Passo | Quantos | |
|---|---|---|
| Na base | 209 177 | |
| Procedimentos distintos | 199 080 | 10 097 são alterações |
| **Com detalhe lido** | **209 177** | **100%** — não falta nenhum |
| Por ver, ainda respondíveis | 1 185 | a aba de entrada |
| Descartados à mão | 3 728 | com motivo |
| **Marcados «interessa»** | **7** | |
| Peças em disco | 187 | 206 MB |
| Lidas pelo modelo | 30 | |

**O que liga aos contratos: 135 945 anúncios, 65%.** É o que o
varrimento serviu. Do outro lado, 240 500 contratos do Portal BASE têm
agora ficha de anúncio a que ligar — eram 65 731. A taxa é estável nos
**65-70% em onze anos** (66,3% em 2015, 68,3% em 2022, 69,2% em 2024),
o que confirma o patamar que dois anos de dados já sugeriam; os 40,1%
de 2026 são só o tempo de celebração a decorrer.

O aperto de cima fechou de manhã a 4/09/2026 (66 498 de 66 498),
**voltou a abrir à tarde** com os 142 063 do varrimento, e **fechou
outra vez de madrugada**: 209 177 de 209 177, zero por ler. Três
passagens do `--detalhes tudo` — 81 585 em 3h11, 22 800 em 1h09 e
38 208 em 1h17. A do meio **parou-se a si própria** por três voltas
seguidas sem ler nada (falha de rede às 23h15, passageira: quinze
minutos depois o portal respondia a 40 detalhes em 4 s). A guarda
funcionou como devia e não deixou nada a meio.

O que o detalhe custa em disco, agora medido em escala grande: o
`anuncios.texto` são **843 MB** e o `radar.db` passou de 558 MB para
**1,23 GB** em doze horas. Foi o crescimento desta coluna que tornou o
painel lento a 4/09 de manhã, e voltou a fazê-lo a 5/09: o mapa das
plataformas da lista custava **0,45 s**, porque o índice que o servia
tinha sido feito para uma versão da consulta que ainda não filtrava por
estado. O `ix_anuncios_acervo` põe-no em **0,037 s** e a página
`/?estado=` em 0,49 s; nenhuma página do painel passa de 0,55 s, tirando
uma ficha com dez lotes a 1,0 s (ver o `docs/diario/2026-09.md`).

- **Os 60 215 sem detalhe vão ser lidos.** A rotina lê o detalhe apenas
  dos publicados na janela `detalhe_dias` (60 dias) e os antigos lêem-se
  ao abrir a ficha, o que deixava 60 215 anúncios **mudos para o filtro
  por CPV, para a árvore, para o preço e para os indicadores** — contam
  na base e não aparecem em nada disso. A decisão de manhã a 3/09/2026
  foi deixá-los («passado é passado, e nesses anúncios já não
  conseguimos fazer nada»); **ele reverteu-a à tarde**, e a razão é a
  segunda metade da frase: não se responde a um concurso de 2024, mas o
  CPV e o preço base dele são o corpus que diz onde é que esta casa
  ganha. Existe desde então o `--detalhes [N|tudo]`. Três versões no
  mesmo dia, cada uma medida contra o portal antes de ficar: sequencial
  a 1s (~24h) → sequencial a 0,3s (~11h) → 0,1s testado e **revertido**
  por ter dado mais lento, não mais rápido, sem erro nenhum → paralelo,
  8 pedidos ao portal ao mesmo tempo (**`ler_detalhes_paralelo()`**),
  ensaiado em graus 1/2/4/8 sem nenhum erro nem sinal de abrandamento,
  e é o que ficou: **0,19 s por anúncio** medido com o comando real a
  correr (632 em 120s) — **~3,2 horas** para o total, não as 24
  iniciais. Retomável por construção — o `detalhe_lido=1` grava-se
  anúncio a anúncio, um Ctrl-C ou um corte de rede não perdem nada, e
  o comando repetido continua de onde ia. Não gasta modelo nenhum: é
  HTTP mais parsing (quem gasta é `--ler-pecas`). Ver
  `docs/diario/2026-09.md` para a história completa e o que o ensaio
  de concorrência mediu.
- **Seis anúncios marcados é pouco para sustentar trabalho a jusante.**
  Foi o que fez cair o OCR e a vigilância das peças a 3/09/2026: estavam
  bem feitos e no sítio errado do funil. Ver `docs/diario/2026-09.md`.

**A lista.** Desde 31/08/2026 os anúncios são **uma página só** (`/`), e
o que aparta o acervo são quatro abas: **por ver 1 185** (por decidir e
ainda respondível), **interessados 7** (todos, expirados incluídos — um
interessa expirado é trabalho em curso), **abandonados 197 888** (os
3 728 descartados à mão mais os por ver que já não dão para responder) e
**todos 199 080**. É recorte de leitura: a base não muda — lá dentro há
195 345 com estado `novo`.

Por cima das abas há o **interesse** (Alertas › Interesse), os CPV que a
casa trabalha. **Está desligado** (`interesse_activo: false`), e
desligado nada muda.

**O que está implementado.** O esqueleto de informação (quatro
intenções: Anúncios, Em curso, Mercado, Alertas, com os Indicadores fora
da barra), o desenho visual «ardósia e âmbar», a ficha em dossier com o
leitor de peças lá dentro, o quadro de seis fases, o calendário, os
alertas por e-mail em texto e HTML, o corpus de contratos do Portal BASE
com os sete gráficos, a exportação da triagem para o git, a segunda fonte
(Vortal), e o registo da casa — desde 8/09/2026 pelo **modelo Excel
do radar**, em Configurações › Importar dados, com ensaio.

**O funil fecha: a ficha diz como o anúncio acabou** (04/09/2026). O dump
do IMPIC traz o número do anúncio do DR em `n_anuncio`, no mesmo formato
do `ref` do radar, e é uma ligação por **chave** — ao contrário dos
homólogos, que são um palpite por termos do título. **135 945 dos
209 177 anúncios têm contrato celebrado no corpus**, 65%; a caixa
«Desfecho» mostra o contratado, quem ganhou, o preço base e quanto
abaixo dele se fechou, com uma linha por lote quando há lotes.

Os 35% que faltam não são falha: **do anúncio à celebração são 68 dias de
mediana** (p25 45, p75 98, p90 139), medido sobre os 38 666 pares que
havia quando isto se mediu. Por isso a taxa é de 66,3% em 2015, 68,3%
em 2022 e 69,2% em 2024, mas só **40,1% em 2026** — e por isso a caixa
só diz «ainda sem contrato» passados 180 dias (`DIAS_ATE_CONTRATO`);
antes disso o silêncio é o normal. **O patamar dos ~65-70% aguenta onze
anos**, o que era hipótese com dois anos de dados e passou a facto com
onze: o resto são procedimentos desertos, anulados, abaixo do limiar de
publicação, ou linhas do dump sem `nAnuncio`.

**A 8/09/2026 a aplicação foi posta a zero, e o registo da casa
mudou de fonte.** Decisão do Afonso: o Excel antigo
(`Analise_Concursos_Publicos.xlsm`) deixa de contar para a aplicação —
fica nos documentos, e o leitor dele fica no `casa.py` sem comando que
o chame. Em vez disso **o radar dita o modelo**: um `.xlsx` gerado em
Configurações › Importar dados (referência do anúncio, lote, estado,
razão, proposta, lugar, concorrentes, responsável, notas, com listas
de escolha), que se preenche, se carrega, se vê em ensaio e só depois
se confirma; a confirmação escreve o registo (`casa.folha='modelo'`)
**e a triagem** (`casa.aplicar()`, o anúncio fica no melhor estado dos
seus lotes). O `--estado-zero` apagou a triagem (3 744 anúncios de
volta a «por ver»), o quadro, as etiquetas, o histórico (24 443
linhas), os filtros e alertas, as entidades seguidas, o interesse, o
destino do resumo e as 187 linhas do Excel/Zoho; ficaram o acervo, as
republicações, as peças, a conta, a recolha e quem envia o e-mail. A
cópia de antes está em `copias/radar-antes-estado-zero-2026-09-08.db`.
Os parágrafos que se seguem sobre o Excel e o Zoho são **história**:
descrevem o que se aprendeu com a fonte antiga, e a regra do
`estado_efectivo()` (o Zoho não decide um lote) continua a valer para
o que o modelo traz.

**O Zoho já está lido, e em coluna própria.** A 03/09/2026 leram-se
pelo browser, na sessão dele, as **148 oportunidades** da vista dos
Negócios (`Potentials`, org `conkord`) — o Zoho não exporta CSV. **92
cruzam** com o registo da casa (68 por preço e nome, 24 só por nome);
sobram 95 linhas da casa sem par e 56 negócios sem par, estes últimos
sobretudo entidades espanholas (que o Excel não inclui de propósito) e
pedidos de perfil, que não são concursos. O que o Zoho diz ficou em
`casa.zoho_fase` / `zoho_montante` / `zoho_como` / `zoho_em`, e o
`status` do Excel **não foi tocado**: em 46 das 92 o Excel diz «Não
fomos» e o Zoho diz «Lost», porque o Zoho não tem palavra para «não
concorremos». Escrever por cima apagava a distinção.

**E a regra de quem manda já está dada** (04/09/2026): **o «Não fomos»
do Excel prevalece, e é o único**; em tudo o resto ganha o Zoho —
**excepto numa linha que é um lote**, onde manda sempre o Excel. As duas
fontes contam coisas diferentes: o Excel tem uma linha por lote, o Zoho
um negócio por procedimento, e um «Won» do Zoho quer dizer «ganhámos
pelo menos um lote», que não diz nada sobre este. Vive em
`casa.estado_efectivo()`, **derivada** — nenhuma das duas colunas se
reescreve. Sobre as 187 linhas: **15 mudam de estado** (9 Submetido →
Perdido, 2 Submetido → Cancelado, 2 TBD → Perdido, 1 Cancelado →
Perdido, 1 Submetido → Ganho) e **47 ficam protegidas** pela excepção do
«Não fomos». O retrato efectivo passa a ser 88 Não fomos · 70 Perdido ·
19 Ganho · 7 Submetido · 2 Cancelado · 1 vazio. O `estado_pretendido()`
já lê por aí, portanto quando o `--com-triagem` correr é este o estado
que chega aos anúncios.

**Os lotes estão desenhados desde 8/09/2026** (decisão de 2/09): a
ficha tem o bloco «Lotes» (os que o anúncio declara, com o preço base
de cada um e, quando o registo da casa os conhece, a que fomos, com
que proposta, em que lugar e como acabou), o cartão do quadro diz a
que lotes fomos («fomos a 2 dos 3 lotes», com uma etiqueta por lote),
e no fim separam-se: um anúncio no Ganho com lotes perdidos ganha um
cartão de lotes, não arrastável, na coluna Perdido — e vice-versa.
Só a partir do registo da casa; o quadro não adivinha resultados.

**Os lotes já têm solução, tirando dois casos.** A 03/09/2026 ele
respondeu às quatro linhas que faltavam. As #23 e #26 traziam a **soma**
dos lotes — é o total do anúncio, não está dividido por lotes: passaram
a `casa.lote = 0`, «o conjunto», e a regra ficou no `lote_da_linha()`
para valer nas importações seguintes. As #129 e #147 trazem um número
que não bate com lote nenhum, nem com a soma, nem com o preço base de
qualquer anúncio da base — é, provavelmente, o valor da nossa proposta;
ficam por identificar até ele dizer o lote à mão. São 12 as linhas
ligadas a anúncios com lotes: 8 com o lote, 2 o conjunto, 2 por
identificar — e as 2 que faltam são exactamente essas.

**Código e testes.** `radar.py` com 14 643 linhas, `casa.py` com 990,
`teste_radar.py` com 728 testes que correm em 30 segundos, sem rede e sem
tocar na base verdadeira. **Mais de metade do `radar.py` é painel**
(7 569 linhas, 54% — da banda `# --- painel` à `# --- arranque`).

**As duas bases.** `radar.db` (era 100 MB em Agosto e 558 MB na manhã
de 04/09/2026; ao fim dessa tarde, com os onze anos dentro, são
**1,23 GB**, com os onze anos e os detalhes todos lidos — o
`anuncios.texto` sozinho são **843 MB**; 19 tabelas, no git só a triagem,
cópia diária em `copias/`) e
`contratos.db` (2,36 GB, 1 987 798 contratos de 2015 a 2026, 178 978
entidades, **fora do git**, refaz-se com `--contratos`). **O tamanho da
`anuncios` é um número de desempenho, não de arrumação**: cada
varrimento dela arrasta esses 843 MB do disco, e é por isso que as
contagens do painel têm de ir por índice de cobertura — ver a
`docs/armadilhas.md`, «A base, as migrações e o disco». **Não se cruzam em SQL**: cada uma tem a sua ligação
(`liga()` e `liga_corpus()`) e quem junta os resultados é o Python.

## O que não corre sozinho, e é preciso saber

- **Os três temporizadores do systemd** (`agendar.sh`; no Windows
  eram tarefas do Agendador) são o que faz o radar
  verificar sem ninguém. Se faltarem, só recolhe com o painel aberto — e
  o relógio interno recupera os slots falhados, o que faz a tabela
  `slots` parecer certa. O painel avisa a vermelho nos dois sistemas
  (até 8/09/2026 só no Windows: fora dele devolvia «nada em falta»).
- **Em Linux, o painel corre como serviço** (`radar-painel.service`)
  e o `iniciar.sh` não abre um segundo. Sem `loginctl enable-linger`,
  o serviço e os temporizadores morrem com o logout — o `agendar.sh`
  tenta ligá-lo e diz se não conseguiu (a 8/09/2026 está ligado). A
  pasta está no disco interno de propósito: num disco externo montado
  pelo ambiente de trabalho, a pasta não estava lá quando o systemd a
  procurava sem sessão gráfica.
- **As capturas `curl_*.txt`** são a forma do pedido ao DR. O token não
  expira (medido a 2/09/2026), mas se o portal mudar de forma é por elas
  que se refaz — secção 3 do `LEIA-ME.md`. Não se editam à mão; um hook
  bloqueia-o.
- **O push é do ramo inteiro.** A verificação das 09:00 e das 17:00 faz
  commit do `triagem.jsonl` e depois `git push origin master` — o ramo
  todo. Qualquer commit deixado no `master` da pen sai sozinho para o
  GitHub na volta seguinte, tenha a triagem mudado ou não. Desliga-se com
  `"triagem_no_git": false`.
- **O repositório mudou a 07/09/2026**: agora é `afonsonp/Radar` (o
  `afonsonp/radarconcursos` foi apagado). A programação passou a
  fazer-se nas sessões remotas do Claude Code; a instalação só traz
  código novo quando o Afonso corre `actualizar.sh`, e só até à última tag
  publicada como GitHub Release (`v1.0.1` agora) — nunca segue o
  `master` a cada merge. Ver a secção Git do `CLAUDE.md`.

## O que fica de fora, e porquê

- **O Portal BASE não traz anúncios novos.** Medido: os «anúncios» do
  BASE são o mesmo universo do DR, e o dump é semanal, portanto mais
  atrasado. Abaixo dos limiares não existe anúncio nenhum — esses
  procedimentos só se vêem como contrato celebrado.
- **A pesquisa no acervo das peças** foi implementada e retirada no mesmo
  dia (30/08/2026): as peças só existem depois de marcar «interessa», por
  isso a pesquisa chegava sempre tarde para ajudar a decidir. A procura
  **dentro** de um documento, no visualizador, existe e é outra coisa.
- **O OCR das digitalizações e a vigilância das peças** saíram a
  3/09/2026. Ver `docs/diario/2026-09.md`.
- **Criar e apagar fases do quadro** saiu a 1/09/2026: o quadro é o funil
  da casa, não um kanban em branco. Renomear ficou.
- **Só passam pelo modelo documentos públicos** — Cadernos de Encargos e
  Programas de Concurso. Propostas, CVs e trabalho próprio não.

## O ponto que falta para a v1

Julgar se a leitura das peças pelo modelo presta. A ferramenta existe
(`ensaio-de-leitura <ref>`, que põe cada linha da resposta ao lado do
pedaço do documento que a sustenta) e há 29 leituras feitas. Falta
passá-las a pente.
