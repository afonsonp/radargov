# Estado do projecto

Última actualização: **3 de setembro de 2026**.

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
`http://localhost:8765`. Verifica sozinha às 09:00 e às 17:00, por
tarefas do Windows.

Substitui a Armilar, produto da Vortal que a empresa paga a 200 euros por
mês, com má experiência de uso e falhas de ingestão. Corre no PC do
Afonso, de uma pen, e não depende de nada da empresa.

Princípio de desenho, decidido depois de uma primeira versão que filtrava
por pontuação: **não se filtra nada à entrada**. Entra tudo o que a parte
L publicar, e a triagem faz-se no painel.

## Como está a correr

Funciona. Os números são de **3/09/2026**, lidos das duas bases.

**O acervo.** 66 387 anúncios, dois anos deles (28/08/2024 a
03/09/2026) — **65 511 procedimentos**, porque 876 são republicações
(«Alteração do Anúncio de procedimento n.º …») ligadas ao original e
fora de todas as listas. O grosso veio do `--historico 730` a
28/08/2026; a rotina diária traz ~65 por dia útil, mais as **consultas
preliminares da Vortal** (32 até agora, `fonte='vortal'`), o tipo que a
parte L não publica.

**O funil, e onde ele aperta.**

| Passo | Quantos | |
|---|---|---|
| Na base | 66 387 | |
| Procedimentos distintos | 65 511 | 876 são alterações |
| **Com detalhe lido** | **6 172** | **9,3%** |
| Por ver, ainda respondíveis | 1 181 | a aba de entrada |
| Descartados à mão | 3 728 | com motivo |
| **Marcados «interessa»** | **6** | |
| Peças em disco | 182 | 32 anúncios, 206 MB |
| Lidas pelo modelo | 29 | |

Os dois apertos são conhecidos e um deles é decisão tomada:

- **Os 60 215 sem detalhe lido ficam assim.** A rotina lê o detalhe
  apenas dos publicados na janela `detalhe_dias` (60 dias); os antigos
  lêem-se quando se abre a ficha. Forçá-los seria ~17 horas de pedidos a
  um por segundo. Decisão do Afonso a 3/09/2026: «passado é passado, e
  nesses anúncios já não conseguimos fazer nada». Consequência a ter
  presente: **um filtro por CPV só apanha quem tem detalhe lido** — o
  histórico é acervo por consultar, não estatística.
- **Seis anúncios marcados é pouco para sustentar trabalho a jusante.**
  Foi o que fez cair o OCR e a vigilância das peças a 3/09/2026: estavam
  bem feitos e no sítio errado do funil. Ver `docs/diario/2026-09.md`.

**A lista.** Desde 31/08/2026 os anúncios são **uma página só** (`/`), e
o que aparta o acervo são quatro abas: **por ver 1 181** (por decidir e
ainda respondível), **interessados 6** (todos, expirados incluídos — um
interessa expirado é trabalho em curso), **abandonados 64 324** (os 3 728
descartados à mão mais os por ver que já não dão para responder) e
**todos 65 511**. É recorte de leitura: a base não muda — lá dentro há
61 777 com estado `novo`.

Por cima das abas há o **interesse** (Alertas › Interesse), os CPV que a
casa trabalha. **Está desligado** (`interesse_activo: false`), e
desligado nada muda.

**O que está implementado.** O esqueleto de informação (quatro
intenções: Anúncios, Em curso, Mercado, Alertas, com os Indicadores fora
da barra), o desenho visual «ardósia e âmbar», a ficha em dossier com o
leitor de peças lá dentro, o quadro de seis fases, o calendário, os
alertas por e-mail em texto e HTML, o corpus de contratos do Portal BASE
com os sete gráficos, a exportação da triagem para o git, a segunda fonte
(Vortal), e o registo da casa (o Excel de 187 concursos, 172 ligados).

**O registo da casa não toca em nada.** Está na base desde 02/09/2026
mas não se vê no painel nem mexe em nenhum destes números, por decisão
dele: nada muda no front antes de o registo estar validado. Há um
teste a guardá-lo (`test_o_front_nao_mudou`).

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

**Código e testes.** `radar.py` com 13 863 linhas, `casa.py` com 918,
`teste_radar.py` com 656 testes que correm em 26 segundos, sem rede e sem
tocar na base verdadeira. **Mais de metade do `radar.py` é painel**
(7 747 linhas, 56%).

**As duas bases.** `radar.db` (100 MB, 19 tabelas, no git só a triagem,
cópia diária em `copias/`) e `contratos.db` (1,65 GB, 1 363 300
contratos, 137 898 entidades, **fora do git**, refaz-se com
`--contratos`). **Não se cruzam em SQL**: cada uma tem a sua ligação
(`liga()` e `liga_corpus()`) e quem junta os resultados é o Python.

## O que não corre sozinho, e é preciso saber

- **As três tarefas do Windows** (`agendar.bat`) são o que faz o radar
  verificar sem ninguém. Se faltarem, só recolhe com o painel aberto — e
  o relógio interno recupera os slots falhados, o que faz a tabela
  `slots` parecer certa. O painel avisa a vermelho.
- **As capturas `curl_*.txt`** são a forma do pedido ao DR. O token não
  expira (medido a 2/09/2026), mas se o portal mudar de forma é por elas
  que se refaz — secção 3 do `LEIA-ME.md`. Não se editam à mão; um hook
  bloqueia-o.
- **O push é do ramo inteiro.** A verificação das 09:00 e das 17:00 faz
  commit do `triagem.jsonl` e depois `git push origin master` — o ramo
  todo. Qualquer commit deixado no `master` da pen sai sozinho para o
  GitHub na volta seguinte, tenha a triagem mudado ou não. Desliga-se com
  `"triagem_no_git": false`.

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
