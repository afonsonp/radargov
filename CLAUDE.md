# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Este projecto é escrito e comentado em português. Escreve em português de
Portugal — código, comentários, mensagens de commit e respostas.

## O que é

Aplicação local em Python que vigia os anúncios de contratação pública da
**parte L da série II do Diário da República**, guarda-os em SQLite e
mostra-os num painel Flask em `http://127.0.0.1:8765`. Corre no PC do
Afonso, verifica sozinha às 09:00 e às 17:00 por temporizadores do
systemd, e não depende de nada da empresa.

Substitui a Armilar (produto Vortal, 200 €/mês).

### Onde está a documentação

Arrumada a 3/09/2026, porque eram 10 819 linhas em nove ficheiros à raiz
e este ficheiro sozinho tinha 968. **Não leias tudo: lê o que a tarefa
pede.**

| Ficheiro | O que é | Quando se lê |
|---|---|---|
| **este** | As regras de trabalho e a arquitectura | Sempre. É o único que se carrega inteiro |
| `ESTADO.md` | O estado de hoje, com os números | Ao começar. São 150 linhas |
| `docs/armadilhas.md` | O que não é óbvio, em 15 áreas | **A área que vais tocar**, antes de tocar |
| `docs/design.md` | O caminho do aspecto: a direcção, a letra, a cor, os botões, a escala | **Antes de mexer em cor, letra, botões ou no calendário**. O que ele vê está em `/amostra` |
| `docs/referencia.md` | Como cada parte foi feita, e porquê assim | Quando a armadilha não chega |
| `docs/seguranca.md` | As seis coisas a rever, por ordem de gravidade | Antes de mexer na porta, nas rotas, ou no que serve ficheiros. São 73 linhas |
| `docs/diario/2026-08.md`<br>`docs/diario/2026-09.md` | O diário: o que se mediu e decidiu, dia a dia | Para perceber uma decisão antiga |
| `docs/historico/` | Auditorias e propostas com data fechada: `AUDITORIA`, `SANEAMENTO`, `ESQUELETO`, `UX-Auditoria`, `CONCORRENTES`, `ONLINE`, `CRM` | Raramente. São instantâneos, não se mantêm |
| `docs/arquitectura.html`<br>`docs/processo-*.html` | Seis diagramas interactivos (16/09/2026, pela skill `archify`): a arquitectura, e por dentro da recolha, das peças, da porta, da escada e do corpus | Para ver a forma de uma coisa antes de lhe mexer. **São instantâneos: mudar o código não os muda** |
| `BACKLOG.md` | O que falta, com prioridade | Ao escolher trabalho |
| `LEIA-ME.md` | O manual do Afonso | Ao mexer no que ele opera |

Quatro destas merecem nome. O `docs/historico/ONLINE.md` (3/09/2026) é o
plano para o radar sair do PC: login de um utilizador, um menu de
configurações que absorve o separador Alertas, e o servidor — **lê-o
antes de tocar em contas, sessões, no `config.json` pelo painel ou na
barra de navegação**. O `docs/historico/CONCORRENTES.md` guarda o que
se observou nos produtos pagos deste mercado, com data — **um produto
muda, e o que lá está vale para o dia em que foi visto**. O
`docs/historico/UX-Auditoria.md` (2/09/2026) passa as regras de interface
da empresa pelas «leis de UX», uma a uma, com medidas e veredicto (manter,
afinar, dívida): lê-o antes de mexer no painel. O
`docs/historico/CRM.md` (15/09/2026, reescrito nesse dia com as
respostas dele) é o plano para o «Em curso» deixar de ser a mesma
consulta dos interessados. O desenho é do Afonso: **uma escada só** —
dez ranhuras, a entrada (*por ver*), as oito palavras da empresa (*por
analisar · a preparar proposta · submetido · relatório preliminar ·
ganho · perdido · não fomos · cancelado*) e o cemitério dos expirados —
com o calendário como única outra vista, e a navegação num
«Concursos». Por baixo, uma tabela `propostas` que o estado do anúncio
não consegue ser (lotes, e propostas sem anúncio). **O quadro saiu ao
fim do dia**, por decisão dele: oito colunas e oito abas eram a mesma
coisa duas vezes, a ranhura muda-se no selector de cada linha, e tudo o
que o cartão fazia vive no bloco «A nossa proposta» da ficha. **Lê-o
antes de tocar no calendário, nas abas dos anúncios, no bloco da
proposta ou nas colunas de CRM do `anuncios`.** As sete decisões do §2
estão respondidas; nenhuma se reabre de passagem.

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
python radar.py --exportar-triagem # B15: triagem.jsonl (a verificacao exporta E faz commit+push sozinha)
python radar.py --repor-triagem [F] # repoe a triagem numa base refeita; idempotente
python radar.py --empresa-desfazer COPIA # repõe a triagem tal como está numa cópia de antes
python radar.py --ensaiar-copia [F]   # prova que a última cópia (ou F) se restaura: integrity_check e contagens; sai com 1 se não servir
python radar.py --estado-zero [--sim]  # a aplicação como acabada de instalar, sem perder o acervo; faz cópia antes
python radar.py --criar-utilizador NOME  # a conta do painel ("admin" serve); pergunta o tipo (admin/tester) e a palavra-passe por getpass
python radar.py --palavra-passe NOME     # troca-a (é o "esqueci-me": por consola, não por e-mail)
```

As tarefas agendadas são três (`agendar.sh`): as duas verificações
diárias e a do corpus, à segunda. **Se faltarem, o radar só recolhe com
o painel aberto** — e o relógio interno recupera os slots falhados, o
que faz a tabela `slots` parecer certa. O painel avisa a vermelho.
Desde 8/09/2026 o radar corre em **Ubuntu**, em `~/Desktop/radar`, e
as tarefas são temporizadores do systemd na sessão do utilizador
(`radar-09h.timer`, `radar-17h.timer`, `radar-contratos.timer`), mais
o painel como serviço sempre a correr (`radar-painel.service`, que
arranca o `radar.py --sem-browser`). O aviso vermelho lê `systemctl
--user list-timers` e procura esses dois nomes — mudar um nome no
`agendar.sh` sem mudar `TAREFAS_LINUX` cega o aviso. **O ramo do
Windows saiu a 14/09/2026** (a aplicação está alojada em Linux, atrás
do túnel da Cloudflare, e o Afonso decidiu que nada do Windows fica):
o `schtasks`, o `agendar.bat`, os `creationflags`, o `python.exe` do
hook e os testes disso. Está tudo no histórico do git.

Testes — sem rede e sem tocar na base verdadeira; correm em poucos
segundos (os do B15 criam repositórios git temporários):

```bash
python teste_radar.py                                    # todos
python teste_radar.py TestPrefixoCPV                     # uma classe
python teste_radar.py TestPrefixoCPV.test_divisao_normal # um teste
```

Em Ubuntu, `python` nestes comandos é o `.venv/bin/python` que o
`instalar.sh` cria: o `python3` do sistema não tem o flask nem o
pymupdf. O hook dos testes já escolhe o `.venv` sozinho.

Os `.sh` são atalhos para o Afonso, não para desenvolvimento:
`instalar.sh` (cria o `.venv` e instala o `requirements.txt`),
`iniciar.sh` (painel; recusa-se a abrir um segundo se o serviço já
estiver a correr), `verificar.sh` (`--uma-vez`), `agendar.sh` (cria os
temporizadores e o serviço do painel), `desinstalar.sh` (tira-os),
`reler.sh` (`--reler`), `contratos.sh` (o que a tarefa semanal corre),
`detalhes.sh` (`--detalhes tudo`, ~3 h), `ensaio.sh`
(ensaio-de-leitura), `historico.sh` (gitk), `medir.sh`
(`medir_captura.py`, a medição do token das capturas),
`actualizar.sh` (traz a última release do GitHub e reinicia o serviço
— ver a secção Git), `publicar_dados.sh` / `trazer_dados.sh` (levam o
`radar.db` de um computador para outro pela release "dados" — ver a
secção Git), `tunel.sh` (um endereço público temporário para o
painel) e `tunel_fixo.sh` (o endereço fixo, `https://radargov.pt`,
como serviço — ver «Acesso de fora», em baixo). Todos passam pelo
`_python.sh`, que escolhe o `.venv` se existir. Um `.sh` novo entra
com o exec bit no git (`git update-index --chmod=+x`), porque o
`core.filemode` esteve a `false` no disco NTFS de onde isto veio.

**Os `.bat` do Windows saíram a 8/09/2026** (commit «Saem os .bat»):
a pen do Windows deixou de ser onde o radar corre, e dezanove atalhos
mortos à raiz eram só ruído. Estão no histórico do git se o Windows
voltar; a 14/09/2026 saiu também o que restava dele no `radar.py`, nos
hooks e nos testes (ver «Comandos», em cima).

### Acesso de fora

O painel atende só em `127.0.0.1`, e **desde 8/09/2026 tem login**
(etapa 1 do `docs/historico/ONLINE.md`, feita nesse dia): o
`contas.py` guarda utilizadores e sessões, e a «porta» do `radar.py`
(`porta_de_entrada()`, logo a seguir ao `app`) exige sessão em tudo o
que não seja `/entrar`. Um pedido **deste computador, sem túnel a
meio**, entra sem login como o único utilizador (ou o primeiro
admin, quando há mais contas) — é o
`acesso_livre_local` do `config.json`, o que mantém o desenvolvimento
e os testes sem fazerem login a cada pedido. **Desde 13/09/2026 há
dois papéis** (`utilizadores.papel`: `admin` ou `tester`): o admin vê
tudo e cria contas em Configurações › Conta; o tester leva 403 no que
é do sistema (`ROTAS_SO_ADMIN`: Indicadores, Capturas, Recolha,
Leitura das peças, Cópias, o «Verificar agora» e quem envia o e-mail).
`sou_admin()` é a pergunta; no acesso livre sem conta nenhuma a
resposta é sim. Lê a área «Contas e a
porta» do `docs/armadilhas.md` antes de tocar nisto: a armadilha
principal é que o túnel liga-se ao painel **a partir de 127.0.0.1**.

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

Quase tudo em **`radar.py`** (~19 mil linhas), dividido por bandas com
cabeçalho `# ---`; o registo da empresa está em **`empresa.py`** e as contas
em **`contas.py`** (ver abaixo).
A ordem do ficheiro é a ordem do fluxo:

1. **base** — `liga()`, `iniciar_db()`, `ler_config()`. SQLite, tabelas
   `anuncios`, `documentos`, `analise`, `fases`, `etiquetas`, `historico`,
   `cpv_dict`, `slots`, `estado`, `filtros_guardados`, `erros` (C3: a
   série dos erros que as marcas sobrescrevem; poda a 200 por tipo),
   `propostas`, `tarefas` e `contactos` (o CRM, 15/09/2026). São 23
   tabelas.
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
   `gravar_campos_da_proposta()` / `contar_propostas()`, as tarefas
   (`sincronizar_tarefas()` — as automáticas seguem as datas do DR, as
   escritas à mão nunca se tocam), o cruzamento com o Portal BASE
   (`propostas_por_fechar()`, `fomos_nos()`, `desvio_do_proposto()` —
   **propõe, nunca decide**), os indicadores comerciais
   (`pipeline_em_euros()`, `taxa_de_vitoria()`) e os contactos, que são
   da **entidade** e não do concurso. **A escada é o estado da proposta,
   não do anúncio** — não voltes a pendurar estado da empresa no
   `anuncios`, que é de onde as doze colunas saíram.
3. **captura** — `carregar_curl()` / `parse_curl()` lêem `curl_DR.txt` e
   `curl_detalhe.txt`, capturas cURL feitas à mão no DevTools.
4. **leitura** — `recolher()` pagina a pesquisa do portal;
   `ler_detalhes()` vai à página de cada anúncio buscar CPV, prazo e preço
   base; `campos_do_detalhe()` faz o parsing por secções numeradas.
5. **documentos** — `obter_documentos()` puxa as peças do procedimento das
   plataformas que o permitem (`PLATAFORMAS_COM_PECAS`: acingov, vortal,
   compraspt, anogov), por fila e thread de fundo. Ficam em `documentos/`
   no disco, **não na base** — para o `radar.db` ficar pequeno.
6. **leitura das peças por modelo** — `analisar_pecas()` recorta as zonas
   relevantes do CE/PC e faz três pedidos (um por campo), gravando em
   `analise`. Cada pedido desce a cadeia `FORNECEDORES` (Groq → NVIDIA →
   OpenRouter) até alguém responder. **Medido: nenhuma das reservas
   aguenta um recorte de tamanho real em rajada** — ver o
   `docs/referencia.md` antes de contar com elas.
7. **contratos celebrados (BASE)** — `importar_contratos()` traz o dump
   semanal do IMPIC do dados.gov para o **`contratos.db`**, ficheiro
   próprio. `historico_entidade()` responde ao bloco da ficha do
   anúncio, `ficha_entidade()` à página `/entidade/<chave>`.
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
   renovações; `/renovacoes` redirecciona). Por baixo das abas há
   **duas listas**: as pontas mostram anúncios, as oito ranhuras da
   empresa mostram propostas. **O quadro saiu no mesmo dia**, por decisão
   dele: a ranhura muda-se no selector de cada linha (`/escada/<ref>`),
   e tudo o que o cartão fazia vive no bloco «A nossa proposta» da
   ficha (`proposta_cx()`) — os campos que a ranhura pede, o que a empresa
   decide, as etiquetas e o que falta fazer. A barra é **horizontal, em cima**
   (13/09/2026; `<header class="barra">`), só com a marca, os itens,
   **Configurações** e quem está. Configurações
   (`/configuracoes/<seccao>`, etapa 2 do `ONLINE.md`, 8/09/2026):
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
   em `/anuncio/<ref>`, em composição de dossier: uma coluna, com o
   cabeçalho fino e o índice presos ao rolar. Uma peça abre **dentro
   da ficha** (`?peca=<nome>`), por baixo da lista das peças; a rota
   própria `/peca/<ref>/<nome>` mantém-se para ligações directas, e as
   duas partilham `visualizador_de_peca()`.
8a. **a abertura** — `/` (16/09/2026, fase 4 do `docs/design.md`): o
   estado do negócio e o que há para fazer. Lê só a tabela `tarefas`;
   os prazos dos anúncios não se somam por cima, que as automáticas já
   os trazem.
8b. **a amostra do desenho** — `/amostra` (16/09/2026, fase 0 do
   `docs/design.md`): os componentes todos num sítio, com um selector
   de letra e de pele, para ele ver e decidir antes de um ecrã mudar.
   É a **única** página que não passa pelo `envolver()`, porque é a
   única que precisa de carimbar `data-pele` e `data-tipo` no `<html>`.
   O `CSS_NOVO` está todo dentro desse âmbito e as fontes servem-se de
   `/tipo/<nome>`, por lista branca (`TIPOS`).
9. **agendamento** — `relogio()`, thread daemon que dispara os slots.

### O que não é óbvio está em `docs/armadilhas.md`

São 195 pontos, cada um de um erro que existiu mesmo, em **15 áreas**:
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
  `com_recorte()`.
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

Tres hooks, em `.claude/settings.json`. Os tres olham para o `file_path` das
ferramentas de escrita **e para o texto dos comandos** do Bash e do
PowerShell -- so pelo `file_path` eram uma porta com a parede ao lado:

- **`proteger_dados.py`** (PreToolUse) recusa escritas em `curl_*.txt` e
  `radar.db*` -- capturas e base nao se editam a maos. Nos comandos, recusa
  a escrita e deixa passar a leitura: um `sqlite3 radar.db "SELECT ..."` e
  rotina, e travar leituras so ensinava a desligar o hook.
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

Fora do projecto, mas activa aqui: a skill global **`task-observer`**
(«One Skill to Rule Them All»). **Invoca-a no início de qualquer sessão
de trabalho** — qualquer interacção em que vais usar ferramentas e produzir
trabalho — antes de começar. É ela que apanha, durante o trabalho, o que
vale a pena guardar sobre as próprias skills e métodos, e escreve-o em
`~/.claude/projects/D--radar/skill-observations/log.md`. A descrição da
skill sozinha não chega para a disparar — é esta instrução que a torna
fiável, e é por ela que a skill volta depois de o contexto ser comprimido.

E ao carregar qualquer skill, vê nesse registo se há entradas **OPEN**
dessa skill e aplica o que dizem ao trabalho a decorrer, mesmo que o
ficheiro da skill ainda não tenha sido actualizado.

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
histórico). Cortar uma release é decisão do Afonso, feita depois de
validar o merge: `git tag -a vX.Y.Z -m "..."`, `git push origin
vX.Y.Z`, `gh release create vX.Y.Z`. A primeira do repositório actual
é a `v1.1.0`: a `v1.0.0` e a `v1.0.1` de 7/09/2026 nunca chegaram ao
remoto e as tags locais saíram a 15/09/2026, porque uma tag que só
existe num disco confunde o `actualizar.sh` e o `gh release create`
(foi o que travou a republicação da release `dados` nesse dia).

Isto **não muda o B15**: `empurrar_triagem()` continua a fazer commit
só do `triagem.jsonl` e a decidir empurrar por `git rev-list --count
origin/master..master` (não pelo diff do ficheiro) — o push é do ramo
inteiro, na verificação seguinte (09:00 ou 17:00), tenha a triagem
mudado ou não. Um push falhado retoma sozinho (desliga-se com
`"triagem_no_git": false`). Isso é sincronização de **dados**, não
programação: continua automático e sem tocar em `radar.py`. A única
coisa que passou a ser manual é a instalação **trazer código novo** —
isso só acontece quando o Afonso corre `actualizar.sh`.

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
dá 1 GB/mês, insuficiente para uma base que cresce duas vezes por dia.
Para levar o `radar.db` de um computador para outro usa-se uma release
à parte, **`dados`** (fora da numeração `vX.Y.Z` do código, para o
`actualizar.sh` não a confundir com uma versão): `publicar_dados.sh`
sobe o `radar.db` como anexo dessa release (`gh release upload dados
--clobber`), `trazer_dados.sh` descarrega-o no computador novo. É
manual e pontual — nunca corre nas verificações agendadas, que só
mexem no `triagem.jsonl`. **O `contratos.db` não viaja**: com 2,5 GB
excede mesmo o limite de anexo do GitHub (2 GB), e refaz-se em minutos
com `python radar.py --contratos` a partir do dump público do IMPIC —
não há razão para transportar o ficheiro.

**Fins de linha:** o `.gitattributes` (8/09/2026) fixa LF em tudo (e
CRLF nos `.bat`, que já não existem). Antes dele, a pasta escrita pelo Windows com
`autocrlf` aparecia em Ubuntu com 27 ficheiros «alterados» sem uma
letra mudada. Se o `git status` mostrar o ficheiro inteiro a mudar,
compara com `git diff --ignore-cr-at-eol` antes de acreditar.

Commit no fim de cada trabalho acabado, sem esperar autorização.
`master` é o único ramo persistente; um ramo `claude/*` é sempre de uma
sessão remota em curso e **não se apaga sem uma palavra dele** — nem
depois do merge.
