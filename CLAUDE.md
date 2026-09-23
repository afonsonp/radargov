# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Este projecto é escrito e comentado em português. Escreve em português de
Portugal — código, comentários, mensagens de commit e respostas.

## O que é

Aplicação local em Python que vigia os anúncios de contratação pública da
**parte L da série II do Diário da República**, guarda-os em SQLite e
mostra-os num painel Flask em `http://127.0.0.1:8765`. Corre no PC do
Afonso, verifica sozinha **de hora a hora** (das 08:00 às 20:00, desde
23/09/2026; eram só as 09:00 e as 17:00) por um temporizador do
systemd, e não depende de nada da empresa.

Substitui a Armilar (produto Vortal, 200 €/mês).

### Onde está a documentação

Arrumada a 3/09/2026, porque eram 10 819 linhas em nove ficheiros à raiz
e este ficheiro sozinho tinha 968. **Não leias tudo: lê o que a tarefa
pede.**

| Ficheiro | O que é | Quando se lê |
|---|---|---|
| **este** | As regras de trabalho e a arquitectura | Sempre. É o único que se carrega inteiro |
| `ESTADO.md` | O estado de hoje, com os números | Ao começar. São ~156 linhas, e **é para isso que serve o formato**: sempre que voltar a crescer para diário, o que ele contava vai inteiro para o `docs/diario/` e este volta ao formato (já aconteceu a 3/09 e a 17/09/2026) |
| `docs/FUNCIONAL.md` | **O documento funcional**: os dados que existem (tabela a tabela, com o que está cheio e o que está vazio), os conceitos, os ecrãs, as acções, as regras — e o que ainda se pode fazer com os dados que há. **Não é instantâneo: corrige-se quando o comportamento muda** | Ao desenhar ou propor um ecrã novo; ao explicar a aplicação a alguém |
| `docs/armadilhas.md` | O que não é óbvio, em 16 áreas | **A área que vais tocar**, antes de tocar |
| `docs/design.md` | O caminho do aspecto **até 20/09/2026**: a direcção, a letra, a cor, os botões, a escala. A paleta e a letra que ele descreve (Plex, ardósia) **saíram a 21/09** — o que vale hoje é o sistema de desenho | Para perceber uma decisão de aspecto antiga |
| `docs/referencia.md` | Como cada parte foi feita, e porquê assim | Quando a armadilha não chega |
| `docs/seguranca.md` | As seis coisas a rever, por ordem de gravidade | Antes de mexer na porta, nas rotas, ou no que serve ficheiros. São 73 linhas |
| `docs/diario/2026-08.md`<br>`docs/diario/2026-09.md` | O diário: o que se mediu e decidiu, dia a dia | Para perceber uma decisão antiga |
| `docs/historico/` | **O arquivo**: oito instantâneos com data fechada — `CRM`, `ONLINE`, `ONLINE-empresas`, `UX-Auditoria`, `CONCORRENTES`, `REDESENHO`, `MIGRACAO`, `CICLOS`, `CAMADAS`. **Descrevem o dia em que foram escritos e não se editam** | **Nunca antes de mexer em código** — para isso é o dono vivo. Só para perceber **porquê**, e em que dia |
| `BACKLOG.md` | O que falta, com prioridade | Ao escolher trabalho |
| `LEIA-ME.md` | O manual do Afonso | Ao mexer no que ele opera |

**Nenhum destes é leitura obrigatória, e isso mudou a 19/09/2026.**
Quatro deles diziam «lê-o antes de tocar em X» — mas a regra da casa é
que um instantâneo **não se edita**, e um ficheiro que é obrigatório e
não se corrige é uma contradição. Provou-se nesse dia: o `CICLOS.md`
tinha seis referências a diagramas apagados uma hora antes, e não
podia ser corrigido.

**O que é preciso antes de tocar no código está nos donos vivos.** O
histórico responde a outra pergunta — **porquê, e em que dia**:

| Para saber… | Lê |
|---|---|
| o que a escada é, e o que cada ranhura exige | `docs/FUNCIONAL.md` §3.1 |
| como a porta funciona | `docs/FUNCIONAL.md` §4.9 |
| a abertura, o `/situacao`, as entidades | `docs/FUNCIONAL.md` §4.1, §4.2, §4.7 |
| o aspecto: cor, letra, botões, e o que falta migrar | `docs/historico/MIGRACAO.md` (o plano) e `docs/design.md` (o que veio antes) |
| o que não é óbvio na área que vais tocar | `docs/armadilhas.md` |
| **porque é que ficou assim, e quando** | `docs/historico/` |

Dois avisos sobre o arquivo. O `CONCORRENTES.md` guarda o que se
observou nos produtos pagos deste mercado — **um produto muda, e o que
lá está vale para o dia em que foi visto**. E o `REDESENHO.md` descreve
o que se **pediu**, não o que ficou: para saber o que ficou, é o
`FUNCIONAL`.

**Um facto tem um DONO, e os outros apontam** (19/09/2026). **A tabela
dos donos, e o que se mediu para chegar a ela, estão no
`docs/FUNCIONAL.md`, logo a seguir ao cabeçalho.** A regra de trabalho
que daí sai, e que é o que este ficheiro guarda: antes de escreveres
aqui o que uma ranhura exige, ou no manual o que a aplicação faz,
pergunta **de quem é o facto** — se não é deste ficheiro, escreve-se lá
e aqui fica uma ligação.

E o critério que separa as duas metades de um assunto: **o facto
responde a «o que é?», a regra responde a «o que faço antes de
gravar?»**. Um assunto com as duas parte-se; não se escolhe um dono
para o conjunto.

(O caso que fundou a regra: a 17/09 escrevi a condicionante da escada no
`LEIA-ME` §5, e a 19/09 escrevi-a outra vez no §9 **sem apagar a
primeira**. Duas secções do mesmo ficheiro a dizer a mesma coisa, com
dois dias de intervalo e a mesma mão.)

**A documentação corrige-se na mesma sessão que muda o comportamento.**
Antes do commit de qualquer trabalho que mude comportamento, números ou
decisões, procura no `ESTADO.md`, no `docs/armadilhas.md`, no
`LEIA-ME.md` e neste ficheiro as afirmações que o trabalho tornou falsas
— contagens (testes, anúncios, linhas), funcionalidades descritas como
inexistentes ou ao contrário, limites e janelas — e corrige-as **no mesmo
commit**.

Três paragens obrigatórias quando o trabalho mudou números ou
comportamento: o **«Como está a correr» do `ESTADO.md`**, a **área
tocada do `docs/armadilhas.md`**, e a **lista de comandos** aqui em
baixo. Um commit que muda o `radar.py` sem tocar em nenhum `.md` é sinal
para verificar, não prova de que está tudo bem.

### Duas partes disto já não dependem de ninguém se lembrar

**Um `.md` não falha — ninguém o corre.** Foi assim que uma instrução
para invocar uma skill inexistente sobreviveu a duas mudanças de
sistema, no ficheiro que se carrega inteiro em todas as sessões. Desde
19/09/2026 há duas ferramentas, e a primeira corre na bateria de
testes:

| Ferramenta | A pergunta | Onde corre |
|---|---|---|
| `ferramentas/valida_docs.py` | o que está escrito **existe**? e as contagens deriváveis **batem**? | na bateria (`TestADocumentacaoNaoApontaParaOVazio`) — **trava o commit** |
| `ferramentas/repetido.py` | está escrito **duas vezes**? | à mão; a duplicação precisa de julgamento humano |

**O que elas cobrem:** funções, constantes, bandeiras, rotas,
ficheiros, pastas e secções citadas; e as contagens que se derivam do
código ou da base (rotas, tabelas, áreas e pontos das armadilhas,
secções de configurações).

**O que elas NÃO cobrem, e continua a ser teu:**

- **Se a frase é verdadeira.** «O interesse recorta os alertas» tinha
  todos os nomes certos e estava ao contrário. Isso mediu-se a ler o
  código, e é a regra de sempre: **confirma antes de escrever**.
- **Os números medidos** — anúncios, MB, tempos. Não se derivam;
  medem-se, e vivem no `ESTADO.md` com a data ao lado.
- **A duplicação**, que tem ferramenta mas não teste: duas afirmações
  do mesmo facto para públicos diferentes são legítimas, e isso um
  programa não sabe.

Quando o teste falhar há dois caminhos, e só um é o certo: ou a
documentação envelheceu e corrige-se, ou a referência é legítima — algo
que saiu, um exemplo de ataque, um caminho externo — e entra no
`ISENTOS` **com a razão escrita**. Uma isenção sem razão é o princípio
de um saco onde se esconde o que incomoda.

E a lição que custou duas vezes ao escrever a ferramenta: **quando ela
discorda da realidade, confere-se a ferramenta primeiro.** Acusou o
`--sem-modelo` (é bandeira de uma skill) e dez nomes em maiúsculas (são
variáveis JavaScript e palavras em comentários). «Corrigir» a
documentação nesses casos era estragar texto certo, com um relatório a
dar razão.

O **diário é acrescento, não correcção**: uma sessão nova escreve uma
secção nova em `docs/diario/2026-MM.md`, e o que ela tornou falso
corrige-se nos três sítios acima. Uma secção do diário que descreva algo
depois revertido fica lá, com uma citação no topo a dizê-lo — foi assim
que o OCR e a vigilância das peças ficaram registados a 3/09/2026.

(A auditoria de 30/08/2026 encontrou o ESTADO.md a abrir com números 13×
errados e o LEIA-ME.md a negar funcionalidades que já existiam — esta
regra existe para isso não voltar. E a 3/09/2026 o mesmo parágrafo
estava outra vez com números de dois dias antes, que foi o que motivou a
arrumação.)

## Comandos

```bash
python radar.py                    # painel em http://127.0.0.1:8765
python radar.py --uma-vez          # verifica e sai (é o que as tarefas correm)
python radar.py --historico 730    # recolha extra de N dias; conta horas
python radar.py --historico DE ATE # varre um intervalo por janelas de 30 dias;
                                   # grava cada janela, idempotente, retomavel
python radar.py --detalhes [N|tudo] # le o detalhe do que falta (~0,19s cada, 8 em paralelo); retomavel
python radar.py --reler            # reanalisa o texto já guardado, sem rede
python radar.py --ler-pecas [tudo] # manda as peças ao modelo; "tudo" refaz as já lidas
python radar.py --importar-cpv F   # carrega o vocabulário CPV (uma vez)
python radar.py --contratos [anos] # corpus de contratos do Portal BASE
python radar.py --descartar-expirados # descarta os "por ver" com prazo passado
python radar.py --exportar-triagem # empresas/<id>/triagem.jsonl, só local (a verificação exporta-o sozinha; não vai para o git)
python radar.py --repor-triagem [F] # repõe a triagem numa base refeita, a partir do empresas/<id>/triagem.jsonl (ou F); idempotente
python radar.py --empresa-desfazer COPIA # repõe a triagem tal como está numa cópia de antes
                                   # (a da EMPRESA: copias/empresa-1-….db)
python radar.py --ensaiar-copia [F]   # prova que a última cópia (ou F) se restaura: integrity_check e contagens; sai com 1 se não servir
python radar.py --estado-zero [--sim]  # a aplicação como acabada de instalar, sem perder o acervo; faz cópia antes
python radar.py --criar-utilizador NOME [--empresa N]  # a conta do painel ("admin" serve); pergunta o tipo (admin/tester) e a palavra-passe por getpass; sem --empresa é da 1
python radar.py --criar-empresa "NOME"   # F4: uma empresa nova, com o ficheiro dela vazio; diz o número
python radar.py --apagar-empresa N [--sim] # tira a empresa inteira (cópia antes; a pasta vai para copias/); o dono fica sem empresa
python ferramentas/ecrans.py       # todos os ecrãs num HTML só, para os ver
                                   # lado a lado: o HTML verdadeiro de cada
                                   # rota, com o CSS e as fontes embutidos.
                                   # Gerado e ignorado pelo git; refaz-se
python ferramentas/valida_docs.py  # o que a documentação cita existe? e as
                                   # contagens deriváveis batem? (também corre
                                   # na bateria de testes, e trava o commit)
python ferramentas/repetido.py     # o que está escrito duas vezes, com
                                   # ficheiro e linha dos dois lados
python ferramentas/antes_da_release.py vX.Y.Z   # o portão antes de cortar
                                   # uma release: árvore, testes, documentação
                                   # e os números medidos do ESTADO.md
python radar.py --palavra-passe NOME     # troca-a (é o "esqueci-me": por consola, não por e-mail)
```

As tarefas agendadas são duas (`agendar.sh`): a verificação, de hora a
hora, e a do corpus, à segunda — mais o painel como serviço. **Se faltarem, o radar só recolhe com
o painel aberto** — e o relógio interno recupera os slots falhados, o
que faz a tabela `slots` parecer certa. O painel avisa a vermelho.
Desde 8/09/2026 o radar corre em **Ubuntu**, em `~/Desktop/radar`, e
as tarefas são temporizadores do systemd na sessão do utilizador
(`radar-hora.timer`, que dispara a todas as horas e corre o
`verificar.sh --agendada` — **quem decide que horas contam é o radar**,
pela lista `horas_verificacao` do `config.json`, em Configurações ›
Recolha —, e `radar-contratos.timer`), mais
o painel como serviço sempre a correr (`radar-painel.service`, que
arranca o `radar.py --sem-browser`). O aviso vermelho lê `systemctl
--user list-timers` e procura esse nome — mudar um nome no
`agendar.sh` sem mudar `TAREFAS_LINUX` cega o aviso. **O ramo do
Windows saiu a 14/09/2026** (a aplicação está alojada em Linux, atrás
do túnel da Cloudflare, e o Afonso decidiu que nada do Windows fica):
o `schtasks`, o `agendar.bat`, os `creationflags`, o `python.exe` do
hook e os testes disso. Está tudo no histórico do git.

Testes — sem rede e sem tocar na base verdadeira; correm em poucos
segundos:

```bash
python teste_radar.py                                    # todos
python teste_radar.py TestPrefixoCPV                     # uma classe
python teste_radar.py TestPrefixoCPV.test_divisao_normal # um teste
```

Em Ubuntu, `python` nestes comandos é o `.venv/bin/python` que o
`instalar.sh` cria: o `python3` do sistema não tem o flask nem o
pymupdf. O hook dos testes já escolhe o `.venv` sozinho.

**Os `.sh` são atalhos para o Afonso, não para desenvolvimento.** São
quinze, e **o que cada um faz está no `LEIA-ME.md` §14** — é o
manual dele, e um script que exista sem lá estar é um script que ele
não sabe que tem (aconteceu ao `actualizar.sh`, que é o gesto mais
importante que ele faz e faltava no manual até 19/09/2026). Dois que
tocam neste ficheiro: `actualizar.sh` (a secção Git, em baixo) e
`tunel_fixo.sh` («Acesso de fora», em cima).

Duas regras: todos passam pelo **`_python.sh`**, que escolhe o `.venv`
se existir — um `.sh` novo que chame o `python` directamente parte-se
em Ubuntu. E um `.sh` novo **entra com o exec bit no git**
(`git update-index --chmod=+x`), porque o `core.filemode` esteve a
`false` no disco NTFS de onde isto veio.

**Os `.bat` do Windows saíram a 8/09/2026** (commit «Saem os .bat»):
a pen do Windows deixou de ser onde o radar corre, e dezanove atalhos
mortos à raiz eram só ruído. Estão no histórico do git se o Windows
voltar; a 14/09/2026 saiu também o que restava dele no `radar.py`, nos
hooks e nos testes (ver «Comandos», em cima).

### Acesso de fora

O painel atende só em `127.0.0.1`, e **desde 8/09/2026 tem login**
(etapa 1 do `docs/historico/ONLINE.md`), com **três níveis** desde 23/09/2026 (o dono da plataforma, o admin e o tester de cada empresa; eram dois papéis desde
13/09/2026).

**O que a porta É — os três estados, o que fica aberto sem sessão, as
duas guardas do POST e o trinco — está no `docs/FUNCIONAL.md` §4.9.**
Aqui ficam os nomes no código: `porta_de_entrada()` (um
`before_request`, logo a seguir ao `app`), `pedido_e_local()`,
`origem_e_nossa()`, `sou_dono()` / `so_dono()`, `ROTAS_SO_DONO`,
`sou_admin()` / `so_admin()`, `ROTAS_SO_ADMIN`, `largar_a_empresa()`
(o `teardown_request` que repõe a empresa do pedido), `aceitar_pedido()`
e `convite()` (F5; a rota aberta do convite tem a guarda dentro), `pagina_legal()` / `operador_completo()` e `avisar_o_vigia()` (F8),
`administracao_da_plataforma()` (`/plataforma`, com
`seccoes_da_plataforma()`: as secções do sistema saíram do índice das
Configurações a 23/09/2026),
`ROTAS_ABERTAS` / `PREFIXOS_ABERTOS`, `com_csrf()`, e o **`contas.py`**
inteiro (tabelas `utilizadores`, `sessoes`, `entradas_falhadas`;
`scrypt`; `token_csrf()` / `csrf_bate()`), que **não importa o radar**.

Duas regras de trabalho que não estão em mais lado nenhum: um POST
protege-se **por sessão ou por origem, nunca por nenhuma das duas** —
se acrescentares um caminho que dispensa a porta, diz qual é a guarda;
e **`ROTAS_ABERTAS` é por igualdade, `PREFIXOS_ABERTOS` por prefixo**,
porque quem fecha a porta nas fontes e na folha é a lista branca
`TIPOS` e a conferência da etiqueta, não a linha da porta. Lê a área
«Contas e a porta» do `docs/armadilhas.md` antes de tocar nisto.

**Sem sessão, a raiz de radargov.pt é o site público** (23/09/2026):
`site/index.html`, servido pela `porta_de_entrada()` só em `/`, e o
formulário `/pedir-acesso`, que é rota aberta com a guarda dentro de
si (`pedir_acesso()`). O que isso quer dizer está no
`docs/FUNCIONAL.md` §4.9 e nas armadilhas, «Contas e a porta».

**O endereço público é `https://radargov.pt`** (8/09/2026, etapa 3
do plano, feita pela via B — o PC de empresa exposto por um túnel, não
um VPS): um túnel com nome da Cloudflare, `radar`, a correr como
serviço do utilizador (`radar-tunel.service`, criado pelo
**`tunel_fixo.sh`**), que se liga ao painel em `127.0.0.1:8765` e
responde por `radargov.pt` e `www.radargov.pt`. O domínio está na
conta da Cloudflare do Afonso (plano Free; os nameservers do
registador apontam para lá), a autorização deste computador é o
`~/.cloudflared/cert.pem` (feita uma vez com `cloudflared tunnel
login`, no browser dele), e as credenciais do túnel são o
`~/.cloudflared/<id>.json` — **nada disto está na pasta do radar nem
no git**. O `tunel_fixo.sh` é idempotente: cria o que falta e salta o
que já está; se o Afonso mudar de computador, é correr o `login` e
depois o script. O painel continua a atender só em `127.0.0.1` e
`acesso_livre_local` continua a `true`: é o `Host` público e os
cabeçalhos do túnel que fazem um pedido de fora não ser local. O
`config.json` leva `endereco_publico`, e `endereco_do_painel()` é o
que os links do e-mail usam (`LOCAL` quando está vazio).

Para uma demonstração sem o domínio há também o **`tunel.sh`**: um
*quick tunnel* da Cloudflare, endereço `https://….trycloudflare.com`
aleatório, válido só enquanto o script corre, sem conta. Foi o
primeiro passo, no mesmo dia; o `cloudflared` que ele descarrega para
`.venv/bin/` é o mesmo que o serviço usa.

## Arquitectura

Quase tudo em **`radar.py`** (~23,2 mil linhas), dividido por bandas com
cabeçalho `# ---`; o registo da empresa está em **`empresa.py`** e as contas
em **`contas.py`** (ver abaixo).
A ordem do ficheiro é a ordem do fluxo:

1. **base** — `liga()`, `iniciar_db()`, `ler_config()`. **O trabalho
   de cada empresa é outro ficheiro** desde 23/09/2026 (F1 do plano
   multi-empresa): `empresas/<id>/empresa.db`, que o `liga()` junta por
   ATTACH como `emp` (`db_da_empresa()`, `TABELAS_DA_EMPRESA`,
   `EMPRESA_ACTIVA`); o esquema dele é o `iniciar_empresa()`, e o
   `separar_empresa()` passou-lhe as tabelas no primeiro arranque. A
   regra: **uma tabela da empresa nunca nasce no `radar.db`** — a razão
   está nas armadilhas, «A base, as migrações e o disco». Desde a **F2**
   (mesmo dia) a empresa activa é do fio de execução (`empresa_activa()`,
   `com_empresa()`), e a verificação faz a recolha uma vez e o
   `trabalho_da_empresa()` em cada uma; o que o DR e as peças fazem vai
   para os `eventos` da plataforma (`registar_evento()`), e o
   `registar()` fica para o que a empresa faz. Desde a **F3** o
   `config.json` também se parte: o que é da empresa
   (`CONFIG_DA_EMPRESA`, `EMAIL_DA_EMPRESA`) vive em
   `empresas/<id>/config.json` (`config_da_empresa()`), e o
   `ler_config()` / `gravar_config()` juntam e separam sozinhos. **As tabelas,
   com o que cada uma tem lá dentro e quantas linhas, estão no
   `docs/FUNCIONAL.md` §2.1**; os números medidos de hoje no
   `ESTADO.md`.

   **Como as migrações funcionam — o `iniciar_db()` a correr a cada
   arranque, sem ficheiros nem versões — está no `docs/FUNCIONAL.md`
   §2.1.** Daí saem quatro regras de trabalho, que são o que este
   ficheiro guarda:

   - **A ordem dentro do `iniciar_db()` é contrato, não arrumação.** Um
     passo que leia uma coluna tem de vir depois do `ALTER` que a cria.
     Aconteceu a 17/09/2026: o enchimento do `propostas.entidade_chave`
     estava antes dos `ALTER` do `anuncios` e rebentava numa base antiga
     com `no such column: a.nif`.
   - **Um índice entra depois da migração que cria a coluna dele** — o
     `ix_ctr_chave_fim` é o caso, e está nas armadilhas.
   - **Uma release que traga migrações pede cópia antes.** O
     `iniciar_db()` **não** faz cópia nenhuma; a rotina diária faz, mas
     pode ser de ontem. Quando a migração for maior do que acrescentar
     uma coluna, **ensaia-a numa cópia** antes de a deixar chegar à base
     de 1,3 GB.
   - **Uma cópia que nunca se ensaiou não é uma cópia.** É o que o
     `--ensaiar-copia` faz: `integrity_check` mais as contagens da cópia
     contra a base viva, e sai com 1 se não servir.
2. **comum** — as utilidades puras: `simplifica()`, `data_pt()`,
   `data_hora_pt()`, `mil_pt()`, `euros_do_texto()`, `conta_dias()`,
   `dias_restantes()`, `dias_urgente()`, `janela_urgente()`,
   `etiqueta_prazo()`, `para_like()`, `prefixo_cpv()`,
   `data_de_filtro()`, e as duas primitivas do filtro de texto
   (`frag_de_texto()` / `frag_de_exclusao()`, que as duas
   `condicoes*()` partilham). Não tocam na
   base, não escrevem HTML e não dependem de nada à frente. **Um
   formatador novo entra aqui**, não na banda que por acaso o precisou
   primeiro — ver a regra no `docs/armadilhas.md`.
2b. **propostas** — o CRM inteiro (`docs/historico/CRM.md`,
   15/09/2026): o vocabulário da escada (`ESCADA`, `ESTADOS_DA_EMPRESA`),
   `criar_proposta()` / `mover_proposta()` /
   `gravar_campos_da_proposta()` / `_propostas_por_estado()`, as tarefas
   (`sincronizar_tarefas()`; as duas origens estão no
   `docs/FUNCIONAL.md` §3.5), o cruzamento com o Portal BASE
   (`propostas_por_fechar()`, `fomos_nos()`, `desvio_do_proposto()` —
   **propõe, nunca decide**), os indicadores comerciais
   (`pipeline_em_euros()`, `taxa_de_vitoria()`) e os contactos, que são
   da **entidade** e não do concurso. A condicionante da escada vive em
   `CAMPOS_QUE_A_RANHURA_EXIGE` / `falta_para_a_ranhura()` /
   `recado_do_que_falta()`; o histórico de uma proposta sem `ref` em
   `historico.proposta_id` (`cronologia_da_proposta()` lê pelas duas); e
   a página `/proposta/<id>` monta-se com `_bloco_de_uma_proposta()`, o
   mesmo bloco da ficha do anúncio.
   **O que a escada É lê-se no `docs/FUNCIONAL.md` §3.1** — as dez
   ranhuras, o que cada uma exige, o vocabulário fechado dos motivos.
   Aqui ficam só os nomes no código.
   A regra de trabalho que este mapa guarda, e que não está em mais
   lado nenhum: **a escada é o estado da proposta, não do anúncio** —
   não voltes a pendurar estado da empresa no `anuncios`, que é de onde
   as doze colunas saíram.
3. **captura** — `carregar_curl()` / `parse_curl()` lêem `curl_DR.txt` e
   `curl_detalhe.txt`, capturas cURL feitas à mão no DevTools.
   **De onde vêm os anúncios, e o que a captura ainda dá, está no
   `docs/FUNCIONAL.md` §3.7.**
4. **leitura** — `recolher()` pagina a pesquisa do portal;
   `ler_detalhes()` vai à página de cada anúncio buscar CPV, prazo e preço
   base; `campos_do_detalhe()` faz o parsing por secções numeradas.
   A segunda fonte é a Vortal (`recolher_vortal()`), só consultas
   preliminares, sem captura.
5. **documentos** — `obter_documentos()` puxa as peças do procedimento das
   plataformas que o permitem (`PLATAFORMAS_COM_PECAS`: acingov, vortal,
   compraspt, anogov), por fila e thread de fundo. Ficam em `pecas/`
   no disco, **não na base** — para o `radar.db` ficar pequeno.
6. **leitura das peças por modelo** — o que se lê e porque são três
   pedidos está no `docs/FUNCIONAL.md` §3.6. Aqui: `analisar_pecas()`
   recorta as zonas relevantes do CE/PC e grava em `analise`;
   `analise_incompleta()` / `refs_com_leitura_incompleta()` /
   `reler_incompletas()` são a releitura, que corre na verificação
   **depois** de `vigiar_pecas()` (as peças novas podem ser o que
   faltava) e **antes** dos alertas (para o que se ler entrar no resumo
   do mesmo dia). **Medido: nenhuma das reservas aguenta um recorte de
   tamanho real em rajada** — ver o `docs/referencia.md` antes de
   contar com elas.
7. **contratos celebrados (BASE)** — `importar_contratos()` traz o dump
   semanal do IMPIC do dados.gov para o **`contratos.db`**, ficheiro
   próprio. `historico_entidade()` responde ao bloco da ficha do
   anúncio, `ficha_entidade()` à página `/entidade/<chave>`.
   **O que as entidades SÃO** — a chave única, os dois lados da ficha,
   as cinco abas, os seis factos — está no `docs/FUNCIONAL.md` §3.4 e
   §4.7. Os nomes no código: `chave_entidade()` / `chave_da_entidade()`
   / `chaves_da_entidade()` (grava-se uma, procura-se pelas duas),
   `nome_da_entidade()`, `lado_da_empresa()` e `nosso_lado_cx()`,
   `factos_da_entidade()`, `ABAS_DAS_ENTIDADES` e `_linhas_da_aba()`,
   `_fita_connosco()`, `a_acabar_por_entidade()`,
   `_bloco_de_comparacao()`, `filtro_dos_anuncios_da_entidade()`,
   `MINIMO_COM_ENTIDADE`. A `propostas` tem a coluna `entidade_chave`.
   As três armadilhas desta área — a chave com prefixo, o índice
   `ix_ctr_chave_fim` que entra **depois** da migração que cria a
   coluna, e o filtro que não acrescenta recorte ao `condicoes()` —
   estão no `docs/armadilhas.md`, «Contratos e entidades».
8. **painel** — rotas Flask, HTML gerado por concatenação de strings
   (`CSS`, `BASE`, `NAV`). Abre com **a porta** (`porta_de_entrada()`,
   `/entrar`, `/sair`, `/sair-de-todos`, `com_csrf()`), que exige
   sessão em tudo; as tabelas e a criptografia dessa porta estão no
   **`contas.py`**, que não importa o radar. A banda `pessoas`, antes
   disto, é só a lista de nomes do «responsável» e o `quem_sou()`, que
   lê da porta. Navegação por DUAS intenções mais
   o logótipo, desde 16/09/2026. O **Hoje** (`/`, a abertura — o estado
   do negócio e o que há para fazer) **não é um separador: é a marca**
   («não quero um separador de hoje, quero que esse hoje esteja no
   radargov, no logo» — ele, no mesmo dia em que a abertura nasceu). Os
   dois itens são **Concursos** (**`LISTA`** = `/concursos`, que é
   constante e não literal, a lista única com as dez ranhuras da
   escada nas abas, mais a vista calendário `/calendario`; `/anuncios`
   e `/lista` redireccionam e `/quadro` já não existe) e **Mercado**
   (contratos `/contratos`, com o modo `?ver=fim` das antigas
   renovações e a vista **Entidades**, `/entidades`, desde 17/09/2026;
   `/renovacoes` redirecciona). Por baixo das abas há
   **duas listas**: as pontas mostram anúncios, as oito ranhuras da
   empresa mostram propostas. **O quadro saiu no mesmo dia**, por decisão
   dele: a ranhura muda-se no selector de cada linha (`/escada/<ref>`),
   e tudo o que o cartão fazia vive no bloco «A nossa proposta» da
   ficha (`proposta_cx()`) — os campos que a ranhura pede, o que a empresa
   decide, as etiquetas e o que falta fazer. A barra é **horizontal, em cima**
   (13/09/2026; `<header class="barra">`), só com a marca, os itens,
   **Configurações** e quem está. Configurações
   (`/configuracoes/…`, etapa 2 do `ONLINE.md`, 8/09/2026 — **nove
   rotas literais**, não um `<seccao>`: procura-se pelo nome de cada
   uma):
   nove secções por esta ordem — conta, interesse, alertas, importar,
   indicadores, capturas, recolha, leitura das peças, cópias
   (`SECCOES_CONFIG`, com a bandeira de só-admin nas cinco últimas) —
   cada uma um formulário que grava uma coisa por
   `gravar_config_registado()` (junta sem apagar, recusa chaves que
   pareçam segredos, e deixa o antes/depois no `historico`). Alertas
   saiu da barra para lá, e os Indicadores também (13/09/2026);
   `/alertas`, `/alertas/interesse` e `/indicadores` redireccionam.
   **Os filtros guardados deixaram de existir** nesse dia: a tabela
   `filtros_guardados` fica, mas só os alertas lá vivem. Ficha
   em `/anuncio/<ref>`, em **duas colunas** desde 23/09/2026 (o
   `EcraFicha`: o anúncio à esquerda, a proposta, os contactos e o
   histórico à direita), com o cabeçalho fino e o índice presos ao rolar. Uma peça abre **dentro
   da ficha** (`?peca=<nome>`), por baixo da lista das peças; a rota
   própria `/peca/<ref>/<nome>` mantém-se para ligações directas, e as
   duas partilham `visualizador_de_peca()`.
8a. **a abertura** — `/` (16/09/2026, fase 4 do `docs/design.md`).
   **O que o ecrã mostra está no `docs/FUNCIONAL.md` §4.1**, e as
   tarefas no §3.5. Aqui: lê a tabela `tarefas` e os prazos dos anúncios
   **não se somam por cima** — as automáticas já os trazem, e somá-los
   contava duas vezes o que está na escada e afogava as dez que são
   mesmo trabalho nos mil «por ver». Os nomes:
   `_tarefas_por_fazer()`, `_grupos_das_tarefas()`,
   `propostas_sem_decisao()`, `_quantas()`, `sincronizar_tarefas()`,
   `gravar_tarefa()`.
   **Redesenhada a 17/09/2026** (`docs/historico/REDESENHO.md` §1):
   o título é a **data** (`dia_por_extenso()`) e não uma saudação; os
   quatro cartões `.kpi` deram lugar a uma linha de factos na
   ranhura das abas (que a 22/09/2026 voltou a quatro indicadores, o
   `Stat` do sistema de desenho, por baixo do título); entrou a **fita da semana** (`_fita_da_semana()`,
   sete células — clicar num dia muda o balde do meio, `?dia=`); e o
   corpo passou a **duas colunas**, com «O que mudou», «Prazos a chegar»
   e «Paradas há mais tempo» à direita. O agrupamento por proposta
   **saiu**: o concurso é uma coluna de cada `.hj-row`. A linha tem
   caixa de ✓, dono e entrega, e **risca-se no sítio** — o
   `_volta_com_aviso(..., ancora="t<id>")` traz de volta à linha, que
   era a queixa dele («concluo a tarefa e volto para o início da
   página»). Filtra-se por pessoa (`?quem=`; **ausente = todos, vazio =
   sem dono**) e escondem-se as feitas (`?feitas=esconder`); nada disto
   se guarda em lado nenhum — o que está no ecrã está no endereço. O
   número do facto conta as **linhas desenhadas**, e não `len(tarefas)`.
8b. **o ponto de situação** — `/situacao` (17/09/2026, §2 do
   redesenho): como vai o negócio. É o bloco `#negocio` que vivia no fim
   da abertura, agora com casa própria, três abas (Negócio · Triagem ·
   Por área CPV) e um **período** (`janelas_do_periodo()`: este mês ·
   este trimestre, que é a omissão · 12 meses · tudo), com a comparação
   com o período anterior **do mesmo tamanho**. O período conta pela
   `fechada_em` — a data em que a proposta se **decidiu**; o «em jogo» é
   uma fotografia de agora e **não leva seta**, porque a base não guarda
   o pipeline de ontem.
8c. **a amostra do desenho** — `/amostra` (16/09/2026, fase 0 do
   `docs/design.md`): os componentes todos num sítio, com um selector
   de letra e de pele, para ele ver e decidir antes de um ecrã mudar.
   É a **única** página que não passa pelo `envolver()`, porque é a
   única que precisa de carimbar `data-pele` e `data-tipo` no `<html>`.
   O `CSS_NOVO` está todo dentro desse âmbito e as fontes servem-se de
   `/tipo/<nome>`, por lista branca (`TIPOS`).
8d. **o sistema de desenho** — quatro folhas em `estilo/`, do pacote
   `radargov-migracao` (**fases 1 e 2 feitas a 21-22/09/2026**;
   `docs/historico/MIGRACAO.md`): `radargov-tokens.css` (24 variáveis,
   três temas — claro, escuro, contraste), `radargov-pontes.css` (as 44
   variáveis **antigas** apontadas às novas, para o CSS de 23 mil linhas
   mudar de paleta sem se tocar numa regra) e
   `radargov-componentes.css` (as classes `.rg-*`, **inertes** até à
   fase 2: está tudo dentro de `.rg`, e nenhum molde carimba essa classe
   ainda). Entram por `ler_estilo()`, e **se faltarem o painel serve na
   mesma**.
   **A ordem do `CSS_TUDO` não é a que o plano diz, e a razão está
   medida**: `terceiros + CSS + CSS_NOVO + tokens + pontes +
   componentes` — o que **define** variáveis vai todo para o fim, senão
   o bloco `[data-pele=novo]{--azul:…}` do `CSS_NOVO` ganha-lhes e nada
   muda de cor. Os três moldes carimbam `data-theme="claro"` (o
   `data-tipo` saiu). A quarta folha é **nossa**:
   `radargov-radar.css`, o pouco que o radar precisa e o sistema ainda
   não tem (as vistas da barra, a barra a dobrar, o menu da conta, os
   dois ecrãs fora do molde). **É o único sítio onde se escreve CSS de
   componente que não venha do design system** — assim o
   `radargov-componentes.css` fica igual ao que o sistema publica.
   Da **fase 2**: a barra é `.rg-topbar`, o aceso é `aria-current` e
   não uma classe, a marca é o lockup (`logotipo()`, com o disco da
   bandeira no lugar do ó), o `<main>` leva `.rg`, e o `PAGINA_ENTRAR`
   e o `PAGINA_ERRO` passaram aos componentes. Os 49 ícones estão em
   **`icones.py`** e servem-se por `icone(nome)`; **se o módulo faltar,
   o painel serve na mesma**. Ver a área «A interface» das armadilhas
   antes de mexer nisto.
9. **agendamento** — `relogio()`, thread daemon que dispara os slots.

### O que não é óbvio está em `docs/armadilhas.md`

São **245 pontos** (contados a 23/09/2026), cada um de um erro que
existiu mesmo, em **16 áreas**:
a recolha e as fontes · as peças e as plataformas · o modelo que lê as
peças · o motor de filtros · datas, números e texto · a árvore de CPV ·
contratos e entidades · alertas e interesse · triagem, quadro e ficha ·
o registo da empresa · a base, as migrações e o disco · trabalhos de fundo
e arranque · contas e a porta · a interface · convenções.

**Lê a área antes de lhe mexer.** Estavam aqui até 3/09/2026 e
carregavam-se inteiros em todas as sessões, incluindo as que só tocavam
num sítio. Três que valem sempre, seja qual for a área:

- **Não se filtra nada à entrada.** Entra tudo o que a parte L publicar,
  e a triagem faz-se no painel. Não reintroduzas filtros em
  `recolher()`.
- **Nenhum recorte entra em `condicoes()`.** Esse motor serve também os
  alertas e os filtros guardados; um recorte lá dentro cega-os em
  silêncio. As abas e o interesse aplicam-se por cima, com
  `com_recorte()`. E no sentido inverso: **um filtro que vá virar
  alerta passa primeiro por `filtro_para(…, "anuncios")`** — sem isso,
  os campos de contratos caem em silêncio e o alerta avisa de muito
  mais do que prometeu (o que o alerta É está no `docs/FUNCIONAL.md`
  §3.8).
- **Um número que um ecrã mostra tem de dar exactamente a lista que a
  ligação dele abre** — e a cor de uma etiqueta é um desses números.

### Os testes são regressões

Cada classe de `teste_radar.py` corresponde a um erro que existiu mesmo, e
o comentário diz qual — "simplificar" um teste é normalmente voltar ao erro.
Correm em poucos segundos: corre-os antes de gravar.

E onde a documentação disser «em último recurso faz X», escreve o teste que
força esse último recurso. A leitura do código confirma a intenção, não o
disparo: foi um teste novo que descobriu que `" ".join(("","",""))` dá `"  "`
— que é verdadeiro — e que o `or` de último recurso dos sinónimos de
plataforma nunca chegava a correr. Uma auditoria por leitura integral tinha
passado por cima dele no dia anterior.

**Separa a condição da espera.** Quando o contrato de uma função é «espera
até X e só então faz Y», torna o X injectável e escreve-o: `False`, `False`,
`True`, e verifica as duas coisas — que o Y aconteceu e quantas vezes se
perguntou. Guarda um teste pequeno que exercite o X verdadeiro contra o
recurso verdadeiro, para a condição ficar coberta, mas não faças a asserção
da ordem depender de concorrência real. Um teste cujo sucesso depende de um
`sleep` numa thread aterrar antes de um prazo noutra é um teste instável que
ainda não falhou: passou duas vezes isolado, falhou à terceira e outra vez
dentro da bateria completa, e o que estava a medir era o escalonador do
sistema. (Pelo caminho apareceu um facto do Windows que piora muito as
contas: ligar a uma porta que está reservada mas ainda não à escuta não é
recusado — bloqueia o tempo todo do timeout.)

### Armadilhas já pagas

Custaram horas uma vez. O registo longo está no `docs/diario/`; estas quatro
valem sempre:

- **Nunca testes um endereço que passou por um `[:n]`.** Dois "isto é
  impossível" falsos vieram de códigos de acesso truncados na impressão —
  juntos, tinham declarado ~53% da cobertura das plataformas impossível.
- **Antes de dizer "a correcção não funcionou", confirma a hora de arranque
  do processo na porta 8765.** Já houve cinco instâncias em simultâneo
  (SO_REUSEADDR no Windows), a responder à vez e com código velho.
  Aconteceu outra vez a 31/08/2026, com duas. Duas consequências
  práticas: **matar por caminho** (todos os python que corram da pasta
  do radar), não só "o que está na porta" — e depois **confirmar que
  ficou um**; e comparar a hora de arranque do processo com a da
  última gravação do `radar.py`. Foi essa comparação que denunciou o
  caso: o processo tinha arrancado quatro minutos ANTES do ficheiro
  que devia estar a servir.
- **Para ver se o modelo inventou um facto, normaliza a fonte como o
  extractor a normaliza.** O PDF parte números ("1 2 meses") e um grep
  ingénuo produz uma acusação falsa. É o que o `ensaio-de-leitura` faz.
- **Os heredocs do Bash comem um nível de escape neste ambiente.** O
  gatilho é o carácter, não o tipo de conteúdo: se o que vais escrever
  tem uma contrabarra — um `\n`, um caminho do Windows, uma expressão
  regular — usa as ferramentas de escrita, sem parar para julgar se é
  "código" ou "só um bloco de texto". A regra já estava aqui escrita e
  falhou duas vezes na mesma hora, nas duas por o conteúdo parecer
  inofensivo.

## Hooks, skills e subagente

Tres hooks, em `.claude/settings.json`. **Porque e que olham tambem
para o texto dos comandos, e o buraco que fica assumido, estao no
`docs/referencia.md`.** Aqui: o que cada um recusa, e o que isso te
obriga a fazer.

- **`proteger_dados.py`** (PreToolUse) recusa escritas em `curl_*.txt` e
  `radar.db*` -- capturas e base nao se editam a maos. Nos comandos, recusa
  a escrita e deixa passar a leitura.
  **Falso positivo conhecido:** o hook procura o padrao no texto do comando
  e nao distingue texto que executa de texto que descreve execucao, por
  isso dispara num `git commit` cuja *mensagem* cita o SQL que foi
  alterado. O efeito pratico nao e neutro -- obriga a escrever a mensagem
  de commit de forma mais vaga sobre exactamente aquilo que o hook protege.
  Estreitar o padrao (so o argumento de um cliente de base de dados, um
  `-c`/`-e`, um redireccionamento para o stdin dele) ou isentar os comandos
  estruturalmente incapazes de o executar (`git commit`, `git tag`) e
  mudanca a uma guarda de seguranca: decisao do Afonso, nao se faz de
  passagem.
- **`testes_antes_do_commit.py`** (PreToolUse) trava o `git commit` com
  testes a falhar. So o commit; o resto do git passa.
- **`verificar_sintaxe.py`** (PostToolUse) compila o Python escrito com
  `-W error::SyntaxWarning`, porque os erros que passaram despercebidos
  neste projecto foram todos de sintaxe e de escapes. Escrito por comando
  (`sed -i`, heredoc), compila os `.py` nomeados no comando.

Atencao: estes hooks so actuam quando o **`radar/` e a pasta de trabalho**
da sessao. A trabalhar a partir da pasta-mae, nao disparam -- corre entao
`python teste_radar.py` a mao antes de gravar.

O `settings.json` chama os hooks por `python3` (8/09/2026: em Ubuntu
não há `python`, e as sessões remotas também são Linux), e o
`testes_antes_do_commit.py` corre os testes no `.venv/bin/python` se
existir, senão no interpretador do hook — sem isto, em Ubuntu travava
todos os commits por ImportError.

Duas skills e um subagente:

- **`estado-radar`** lê a base em modo só-leitura e diz quantos anúncios há,
  quantos faltam ler e se as capturas ainda são válidas — funciona mesmo com
  o `radar.py` a meio de uma alteração que não compila.
- **`ensaio-de-leitura <ref>`** põe cada linha da resposta do modelo ao lado
  do pedaço do documento que a sustenta, para julgar se a leitura das peças
  presta. Com `--sem-modelo` não gasta orçamento; sem ele, relê sobre uma
  **cópia** da base. É a ferramenta do ponto que falta para a v1.
- **`explorador-de-plataforma`** (subagente) investiga se as peças de uma
  plataforma que o radar ainda não sabe descarregar se alcançam sem sessão
  iniciada, e devolve receita ou um "não há" fundamentado.

**Saiu a 19/09/2026 a instrução da skill `task-observer`**, que mandava
invocá-la no início de todas as sessões. Três coisas mortas na mesma
instrução, verificadas nesse dia: a skill **não existe** (nem em
`~/.claude/skills/`, nem em plugin nenhum), o registo que ela escreveria
**não existe**, e o caminho que a instrução citava —
`~/.claude/projects/D--radar/…` — era **do Windows**, do tempo da pen.
O radar mudou-se para `~/Desktop/radar` a 8/09 e o ramo do Windows saiu
a 14/09.

É o pior sítio possível para uma instrução morta: este ficheiro
carrega-se inteiro em todas as sessões, e a instrução mandava começar
por uma ferramenta que não há.

## Git

**Repositório novo a 07/09/2026**: o `afonsonp/radarconcursos` foi
apagado pelo Afonso e substituído por `origin` =
`https://github.com/afonsonp/radargov.git`, histórico limpo (verificado
antes do push: nenhum ficheiro de senha, chave ou token alguma vez
entrou nos objectos git — só o `.gitignore` largo, que continua a ser a
guarda de capturas, bases, chaves e peças). Privado, como antes.

**A programação faz-se nas sessões remotas do Claude Code
(claude.ai/code)**, decisão do Afonso a 07/09/2026: um ramo `claude/*`,
PR, e o merge para o `master` **é o Claude que o faz** — validar
primeiro, fazer o merge do PR. A pen deixou de ser onde se escreve
`radar.py`; sessões locais (como esta) servem para operar o radar,
mexer em dados (`config.json`, a triagem), e para trabalho de
infra-estrutura pontual como este.

**A instalação actualiza-se por release, não por commit.** Nunca segue o
`master` a cada merge — só avança quando há uma tag `vX.Y.Z` publicada
como GitHub Release, correndo **`actualizar.sh`**, que faz `git fetch
--tags` e um `git merge --ff-only` até à tag mais recente (recusa-se a
avançar se isso não for uma simples fast-forward, para nunca misturar
histórico). Antes de avançar põe de lado o `config.json` e o
`triagem.jsonl`, que já não estão no git, e repõe-nos depois — já não
se recusa por o painel ter mexido na configuração. Cortar uma release é decisão do Afonso, feita depois de
validar o merge.

**Antes de cortar, corre o portão** (19/09/2026):

```bash
python ferramentas/antes_da_release.py vX.Y.Z
```

Confere sete coisas e **diz o que falta**, não só que falta: a árvore
limpa, a tag por publicar, os testes, o validador da documentação, os
**números medidos** do `ESTADO.md`, a data, e as **contagens do
`docs/FUNCIONAL.md`** §2.1 e §2.2 contra as bases — cada secção contra
a sua. **É automático**: o `.githooks/pre-push` corre-o ao empurrar
uma tag `vX.Y.Z`, e recusa o push. Num push de `master` não faz nada:
o portão é da release, e o commit já tem o seu (os testes e o
validador da documentação). (Até 23/09/2026 era também obrigatório: o
`empurrar_triagem()` empurrava sozinho, e uma falha aqui travava a
triagem.) Só depois é que
`git tag -a vX.Y.Z -m "..."`, `git push origin vX.Y.Z`,
`gh release create vX.Y.Z`.

**Porque é que existe:** a bateria já trava um commit com uma
referência morta ou uma contagem derivável errada. Mas os **números
medidos** — quantos testes há, quantas linhas tem o `radar.py`, qual é
a última release — só se sabem correndo, e por isso ficam fora dela.
Medido no dia em que se escreveu isto, **com cinco releases cortadas
nesse mesmo dia**: o `radar.py` dizia 23 165 linhas e tinha 23 197, e
a linha da última release dizia `v1.8.1` — **quatro releases seguidas
sem ninguém reparar**. A mesma linha já estivera errada a 18/09
(dizia `v1.7.0` quando era a `v1.8.0`).

A primeira do repositório actual
é a `v1.1.0`: a `v1.0.0` e a `v1.0.1` de 7/09/2026 nunca chegaram ao
remoto e as tags locais saíram a 15/09/2026, porque uma tag que só
existe num disco confunde o `actualizar.sh` e o `gh release create`
(foi o que travou a republicação da release `dados` nesse dia).

**O B15 deixou de ir ao GitHub a 23/09/2026** (decisão dele: «no
GitHub só código»). O `empurrar_triagem()` e a chave `triagem_no_git`
saíram, e o `config.json` e o `triagem.jsonl` saíram do git. A triagem
continua a exportar-se em cada verificação, mas por empresa e só no
disco (`empresas/<id>/triagem.jsonl`). Nada do que a verificação faz
toca no git: a instalação só muda quando o Afonso corre
`actualizar.sh`.

**O leitor do Excel antigo saiu a 15/09/2026**, por decisão dele
(«corta, fica no git»): as 603 linhas do `empresa.py` que sabiam ler o
`Analise_Concursos_Publicos.xlsm` do SharePoint e ligá-lo aos anúncios
por semelhança de título (`ler_excel`, `Acervo`, `pontuar`,
`ref_pelo_base`, `decidir`, `importar`, `ligar_a_mao`), mais as 638
linhas do `TestRegistoDaEmpresa`. Uma decisão anterior tinha-o guardado
como história; a D4 do `docs/historico/CRM.md` — o Excel serve só para
importar o passado, **pelo modelo** — tornou-a obsoleta, e o `.xlsm` já
tinha sido importado. O que ficou do `empresa.py` é o modelo
(`escrever_modelo` › `ler_modelo` › `ensaio_modelo` › `aplicar_modelo`),
a tradução do estado (`estado_efectivo`, `estado_pretendido`, que ainda
guardam a regra do Zoho e a guarda dos lotes, com testes em
`TestEstadoEfectivoDaEmpresa`) e o `desaplicar_da_copia()` do
`--empresa-desfazer`.

**As bases de dados não entram no histórico do git** — `radar.db` (1,3
GB) e `contratos.db` (2,5 GB) excedem de longe o limite de 100 MB por
ficheiro que o GitHub recusa num push normal, e o Git LFS gratuito só
dá 1 GB/mês, insuficiente para uma base que cresce de hora a hora.
**E desde 23/09/2026 nenhum dado vai para o GitHub, por nenhum
caminho** — decisão dele: «no github devemos apenas guardar código».
Nesse dia saiu a release `dados`, que levava o `radar.db` como anexo
para o mudar de computador, com os dois scripts que a faziam; mudar de
computador faz-se por uma pen ou pela rede (`LEIA-ME.md` §15-A). Com
empresas clientes, uma base num repositório de código deixava de ser
um atalho e passava a ser uma fuga. **O `contratos.db` não viaja**:
refaz-se em minutos com `python radar.py --contratos` a partir do dump
público do IMPIC.

**Fins de linha:** o `.gitattributes` (8/09/2026) fixa LF em tudo (e
CRLF nos `.bat`, que já não existem). Antes dele, a pasta escrita pelo Windows com
`autocrlf` aparecia em Ubuntu com 27 ficheiros «alterados» sem uma
letra mudada. Se o `git status` mostrar o ficheiro inteiro a mudar,
compara com `git diff --ignore-cr-at-eol` antes de acreditar.

Commit no fim de cada trabalho acabado, sem esperar autorização.
`master` é o único ramo persistente; um ramo `claude/*` é sempre de uma
sessão remota em curso e **não se apaga sem uma palavra dele** — nem
depois do merge.
