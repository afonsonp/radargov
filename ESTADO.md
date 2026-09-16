# Estado do projecto

Última actualização: **14 de setembro de 2026**.

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
temporizadores do systemd.

**Desde 8/09/2026 corre também em Ubuntu**, em
`/home/afonso/Desktop/radar` no disco interno (esteve umas horas no
disco «Matriz», NTFS, que só é montado ao entrar na sessão gráfica —
mudou-se nesse mesmo dia por isso): um `.venv`
criado pelo `instalar.sh` traz as dependências, os `.sh` são os
atalhos (a 8/09/2026 os `.bat` saíram do repositório, e a 14/09/2026
saiu o que restava do Windows no código: a pen deixou de existir), e o
`agendar.sh` cria os três temporizadores e o painel
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
Configurações em `/configuracoes/<seccao>`, com Alertas a sair da
barra para lá. O plano `ONLINE.md` está feito por inteiro, pela via B
(o PC de casa exposto por túnel). **E desde a tarde de 8/09/2026 o
painel serve no telemóvel**: as grelhas de duas colunas passam a uma
abaixo de 900 px, e o que é largo (quadro, tabelas, abas, índice da
ficha) rola dentro de si; medido a 375 px em oito páginas, nenhuma
alarga a página.

**A 13/09/2026 entraram as «Mudanças na plataforma RADAR»**, o
documento do Afonso (ramo `claude/mudancas-radar`): há **dois tipos
de utilizador** — `admin` vê tudo e cria contas em Configurações ›
Conta; `tester` vê os anúncios, o que está em curso, o mercado, e nas
configurações só Conta, Interesse, Alertas e Importar dados (a porta
dá 403 ao resto, `ROTAS_SO_ADMIN`, e o «Verificar agora» é só do
admin). **A barra passou a horizontal, em cima, em todos os
tamanhos**, só com a marca, os três itens, Configurações e quem está —
as fontes, as contagens, o endereço e a última verificação saíram (a
última verificação está nos Indicadores). As Configurações são **nove
secções** por esta ordem: Conta, Interesse, Alertas, Importar dados,
Indicadores, Capturas, Recolha, Leitura das peças, Cópias — as cinco
últimas só ao admin. A Conta perdeu o «nome a mostrar» e a nota da
consola, e as sessões dizem o aparelho («iPhone até 10/10/2026 14:35»).
O Interesse é só a árvore, já aberta, e o botão dela «Guardar o
interesse» grava: com CPV fica ligado, vazio fica desligado; com
interesse definido a lista de anúncios deixa de ter árvore e «excluir
CPV». Os Alertas perderam o bloco do interesse, o formulário chama-se
«Filtro de alertas» e «Criar alerta» nasce ligado; **os filtros
guardados deixaram de existir** (a caixa saiu das três listas, a rota
`/filtros/guardar` também, e os que estavam sem alerta apagaram-se
uma vez por migração — a tabela fica, é onde os alertas vivem). O
resumo por e-mail mostra ao tester só o destino e a hora. Entrou o
motivo de abandono «Não faz parte da oferta». A bateria — **819** —
passa inteira. Ficou para o backlog o modo lista do «Em curso».
**A 14/09/2026 fechou-se o P0**: a verificação tem um trinco entre
processos na tabela `estado` (pid, hora, prazo de 3 h), e o
temporizador e o relógio do painel já não correm os dois à mesma hora.
**E no mesmo dia voltou a vigilância das peças**, com o desenho que
ele pediu: o radar vai à plataforma ver a lista das peças de um
anúncio marcado quando passou a data de esclarecimentos, ou quando o
prazo ou o preço base mudaram, e há o botão «Ver se há peças novas»
na ficha; as novas entram no resumo por e-mail, **e com peça nova o
anúncio é relido logo pelo modelo**. **E entrou a lista do «Em
curso»** (`/lista`), a tabela que ele mandou: título, cliente, preço,
esclarecimentos, entrega, tipologia, estado da proposta, CV, proposta
técnica, notas, plataforma, CoE, responsável — as cinco da casa são
colunas novas, gravadas linha a linha. E a aplicação chama-se
**RadarGov** na barra e no ecrã de entrar, com o «Gov» a azul. **E
passou por uma auditoria de segurança** (14/09/2026, a pedido dele):
cabeçalhos em todas as respostas (CSP, `nosniff`, moldura, Referer,
HSTS por HTTPS), tecto de 20 MB por pedido, as peças das plataformas
só abrem em linha se forem PDF, imagem ou texto (o resto descarrega-se
em caixa fechada), o CSV sem fórmulas, os redireccionamentos pelo
Referer só para o próprio anfitrião, e os ficheiros com segredos a
0600. **E o Mercado recorta-se pelo interesse** como os anúncios
(14/09/2026): com interesse definido, os contratos, o CSV e os
gráficos mostram só os CPV marcados, com a mesma faixa e o mesmo «ver
tudo». **Com interesse definido o Mercado abre logo com os contratos
dos CPV da casa** — o interesse conta como pergunta, nos dois modos e
no CSV (14/09/2026, «abre-se e não se vê contrato nenhum»); sem
interesse continua a pedir um filtro, e o ecrã vazio diz-o. O
formulário do alerta ficou em três grupos — em comum, só anúncios, só
contratos. E as plataformas que já não existem (saphety, compraspublicas,
gatewit, bizgov, construlink) são «outras» nos dois selectores. **Os
filtros ficaram em quatro campos** — objecto, entidade, plataforma,
datas — com a árvore de CPV por cima, na lista e no alerta (o grupo dos
contratos do alerta saiu), e **a entidade sugere-se enquanto se
escreve**, uma por NIF, e escolhida a sugestão o filtro é pelo NIF,
que apanha todas as grafias — no Mercado também, do corpus e pela
chave da entidade. O «excluir palavras» e o E/OU saíram dos três
formulários. A bateria vai em **861**.

Substitui a Armilar, produto da Vortal que a empresa paga a 200 euros por
mês, com má experiência de uso e falhas de ingestão. Corre no PC do
Afonso, de uma pen, e não depende de nada da empresa.

Princípio de desenho, decidido depois de uma primeira versão que filtrava
por pontuação: **não se filtra nada à entrada**. Entra tudo o que a parte
L publicar, e a triagem faz-se no painel.

## Como está a correr

Funciona. Os números são de **4/09/2026**, lidos das duas bases.

**A 15/09/2026, à tarde, começou o trabalho do CRM** — a pergunta dele
foi que o «Em curso» não é um CRM e que é estranho, porque a página dos
anúncios já tem o que ele classificou como interesse. Tinha razão, e a
causa é de raiz: o `/lista`, o `/quadro` e o `/calendario` partem todos
de `estado='interessa'`, que é exactamente o que a aba «interessados»
mostra. São o mesmo conjunto, sempre, porque há **duas escadas
paralelas** para o mesmo percurso (a triagem e o funil) e um concurso
sobe as duas ao mesmo tempo. O plano está em `docs/historico/CRM.md`,
com as sete decisões dele respondidas, e o desenho é dele: **uma escada
só**, dez ranhuras — a entrada (*por ver*), as oito palavras da casa
(*por analisar · a preparar proposta · submetido · relatório preliminar
· ganho · perdido · não fomos · cancelado*) e o cemitério dos expirados
—, com lista, quadro e calendário como três vistas dela. **As etapas 1 e 2
estão feitas**, no mesmo dia. A 1: as tabelas `propostas` e `tarefas`, o
vocabulário, e as duas no `triagem.jsonl` — que é o que fecha o buraco
do R2 que ninguém tinha visto (as doze colunas de CRM em `anuncios`
nunca tinham sido exportadas). A 2: as dez ranhuras nas abas, a triagem
a criar propostas em vez de escrever no anúncio, o quadro nas oito
colunas a ler propostas, o calendário para qualquer ranhura, e a
navegação fundida num **Concursos** com lista · quadro · calendário.

**As doze colunas de CRM deixaram de se criar** e a tabela `fases` saiu,
com o renomear das colunas — as oito palavras são vocabulário do
código, e uma tabela renomeável por cima disso fazia o quadro dizer uma
palavra e as abas outra para o mesmo estado. Numa base que já as tenha, as colunas **ficam**: apagá-las
custava doze reescritas de uma tabela de 1,2 GB, medido nesse dia a
correr contra uma cópia da base dele — ao fim de 45 s a primeira ainda
não tinha acabado, com o WAL já maior do que a base. São doze colunas a
NULL que código nenhum lê, e a garantia passou a ser um teste em vez de
uma migração.

**Ensaiado com os dados dele nesse dia**, numa cópia da base (1,2 GB, 209
894 anúncios) e na porta 8799, com o painel de produção de pé em 8765:
arranca de imediato, as abas dizem **Por ver 1 325 · Expirou sem ver
198 305 · Todos 199 631**, e as contas fecham — pôr um concurso na
escada tirou-o do «Por ver» e pô-lo no «Por analisar», com a proposta
na tabela e o prazo a horas.

**E no mesmo dia, à noite, uma segunda arrumação, também dele, a olhar
para o ecrã:** «o quadro deixa de ser preciso tal como a lista. na
verdade eu devo conseguir passar entre estados aqui. e a pagina do
anuncio e sempre a mesma». **O quadro saiu por inteiro.** Oito colunas e
oito abas eram a mesma coisa duas vezes, e a diferença era o arrastar —
que só compensa quando se vê tudo ao mesmo tempo. A ranhura muda-se
agora pelo **selector de cada linha** (grava ao escolher, com desfazer;
o «Perdido» e o «Não fomos» abrem a caixa do motivo), e tudo o que o
cartão fazia mora no bloco **«A nossa proposta»** da ficha: os campos
que a ranhura pede, a tipologia, o CV, a proposta técnica, o CoE, as
notas, as etiquetas e o que falta fazer. A barra ficou em **Concursos ·
Calendário · Mercado**.

**As tarefas entraram com isso** (etapa 3, encolhida): o prazo de
esclarecimentos e o de entrega viram tarefas sozinhas quando um
concurso entra na escada, acompanham uma prorrogação do DR e
desaparecem quando a proposta fecha. As escritas à mão nunca são
tocadas pela sincronização. **A vista «Hoje» não ficou** — ele escolheu
que só o calendário sobrevive como vista —, e com ela fica por responder
«o que tenho de fazer hoje, em todos os concursos ao mesmo tempo».

**Os lotes deixaram de precisar de truque.** O pedido dele de 2/09
(«no final, perdido ou ganho, separam-se os cartões») fazia-se com um
cartão montado a partir do registo do Excel, que não se arrastava nem
se editava. Com uma proposta por lote, cada um cai sozinho na coluna
dele e é um cartão como os outros.

**As etapas 4, 5 e 6 entraram nessa noite, e o CRM ficou completo.**

**O ciclo com o Portal BASE fecha-se por chave e não por palpite**, que
foi a surpresa da medição: o `contratos.n_anuncio` do dump do IMPIC vem
no mesmo formato do `ref` do radar («17161/2026»), e **69,4% dos
anúncios de 2024 já têm contrato celebrado** (5,3% nos de 2026 — o ciclo
demora meses). O plano previa o maquinário de semelhança do `casa.py`;
não é preciso nenhum. A ficha de uma proposta ainda aberta cujo
procedimento já foi adjudicado mostra a quem foi, por quanto, e **quanto
a nossa proposta estava acima ou abaixo** — com dois botões, «Ganhámos»
e «Perdemos». **Propõe, nunca decide.** Falta-lhe uma coisa para
adiantar a resposta: o NIF da casa, em Configurações › Conta (enquanto
estiver vazio, pergunta em vez de adivinhar).

**Os indicadores ganharam o bloco «O negócio»**: o que está em jogo por
ranhura (preço base até ao Submetido, proposto daí para a frente), a
taxa de vitória — que **só aparece com 5 decididos ou mais**, e onde o
«Não fomos» não entra no denominador, porque é uma decisão de não
concorrer e não uma derrota —, o desconto médio nos ganhos, porque se
perde e porque não se vai, e o que há mais tempo não se mexe. Cada
número abre a lista que o confirma.

**E os contactos**, que são da **entidade** e não do concurso: a pessoa
que responde aos esclarecimentos do IPL responde aos do ano que vem
também, e por isso aparecem em todos os concursos dela.

**A 15/09/2026 entraram as três coisas que faltavam de uma lista de
«20 coisas a proteger antes de um site ir para o público»** (as outras
dezassete já existiam ou não se aplicam): páginas de erro da casa
(404, 403 e 500, e o 500 fica na marca `painel_ultimo_erro` e na série
`erros`, visível nos últimos erros dos Indicadores); a rota **`/saude`**,
sem sessão, que responde «ok» ou 503 para um vigilante de fora bater
(o UptimeRobot, ligado pelo Afonso nesse dia, na conta dele, a bater
de 5 em 5 minutos e a avisar por e-mail); e o
**`--ensaiar-copia`**, que prova que a última cópia se restaura sem a
restaurar (integrity_check e contagens contra a base viva; marca
`ultimo_ensaio_copia`). **Correu na instalação a 15/09/2026, depois
da v1.3.0: «Serve.»**, integridade ok, 209 793 anúncios na cópia contra
209 826 na base viva (os 33 da verificação das 09:00, feita depois da
cópia). A release **v1.3.0** é desse dia: os PR #8 a #20, e a
**v1.3.1** logo a seguir, na mesma manhã: a saída da revisão de
segurança automática do GitHub (as seis prioridades ficam em
`docs/seguranca.md`) e os comentários da cópia diária sem números do
Windows — medido nesse dia em Ubuntu, com a base nos 1,23 GB, o
`VACUUM INTO` leva 3,4 s e 16 MB de RSS, e a razão de ser uma cópia
por dia passou a ser o disco, não o tempo. A instalação está na
v1.4.0 — **a release do CRM**, cortada ao fim desse mesmo dia, com o
PR #25: a escada só, as `propostas`, o ciclo fechado com o Portal BASE,
os indicadores comerciais, a limpeza do código morto e a saída do leitor
do Excel antigo. Fez-se cópia da base antes de a instalação arrancar com
o código novo (`copias/radar-antes-da-escada-2026-09-15.db`), o
`actualizar.sh` avançou por fast-forward, e o painel e o `radargov.pt`
responderam a seguir. Nesse dia republicou-se também a release **`dados`** com o
`radar.db` (1,29 GB): tinha desaparecido do GitHub com o
repositório antigo, e as tags locais `v1.0.0`, `v1.0.1` e `dados`,
que o remoto já não tinha, foram apagadas.

**A 16/09/2026 começou o trabalho do aspecto** («a aplicação tem
aspecto de 2002 e eu quero 2026»). O caminho está escrito em
**`docs/design.md`** e o que se vê está em **`/amostra`**, uma página
que mostra os componentes todos num sítio — a letra, a paleta, a
escala, os cinco botões, as etiquetas, a tabela, os formulários, os
avisos e o selector da ranhura — com um selector para trocar entre
**três letras** e entre a pele nova e a de hoje. **A letra está
escolhida: IBM Plex Sans + IBM Plex Mono**, decisão dele nesse dia
depois de ver as três. A proposta escrita tinha sido a Inter, e o
argumento que eu usei contra a Plex — «mais larga, perde-se
densidade» — **estava errado**: medida com as duas fontes mesmo
carregadas, a mesma frase a 13px dá 637,3px em Inter contra 602,6px em
Plex, e mesmo ao mesmo tamanho óptico (a Plex tem altura-de-x 52
contra 54) a Plex continua 1,8% mais estreita. Das três é a que cabe
mais texto por linha. A consequência é a escala subir meio pixel —
11,5 / 12,5 / 13,5 / 15 / 17,5 / 25 — para repor o tamanho aparente.
**A fase 1 entrou no mesmo dia** («avança», palavra dele): os **três**
moldes — `BASE`, `PAGINA_ENTRAR` e `PAGINA_ERRO` — carimbam
`data-pele="novo" data-tipo="plex"` no `<html>`, e mais nada mudou. Os
tokens antigos (`--papel`, `--creme`, `--linha2`) apontam para os
valores novos, e por isso as 1196 linhas de CSS herdaram a paleta
inteira sem se tocar numa regra; apagar os dois atributos repõe o
aspecto de antes, e `TestPeleNova` falha se alguma regra da pele
escapar desse âmbito. **Os botões passaram a ter significado**: cinco
classes (`forte` azul, `ok` verde, neutro, `cuidado` laranja, `perigo`
vermelho), e o `.mini` da linha deixou de ficar vermelho ao passar por
cima — ficava, em todos, o que destapou um erro escondido: o botão que
**apaga uma conta** era um `.mini` simples e só parecia certo por
acidente. As fontes são servidas da própria aplicação (`tipo/`, 124 KB,
rota `/tipo/<nome>` com lista branca) — a regra de não pedir nada a
domínio nenhum de fora mantém-se. Dois números do diagnóstico, medidos
no browser sobre a base verdadeira: o CSS declara **dezanove tamanhos
de letra** entre 9 e 34px sem escala nenhuma, e o `/calendario` desenha
**48 870 células para mostrar 1 086 factos** — 2 MB de HTML e 87 000 px
de altura, 98% vazios. A paleta nova está medida sobre **todos** os
fundos que existem, não só sobre o papel: pior caso **4,52**, e a
escala de texto passou a ter um patamar só em vez de dois, que era a
armadilha que já partiu o contraste duas vezes.

**E a fase 3, o calendário, no mesmo dia.** Era uma grade de «uma
linha por concurso × uma coluna por dia» — a forma de um Gantt, que
serve para intervalos; um prazo é um dia. A unidade passou a ser o
**dia**: seis semanas, sete colunas, e dentro de cada dia o que fecha
nesse dia. Medido na mesma página e na mesma base, antes e depois:
**48 870 células → 42**, 2,2% cheias → 88% (37 dos 42 dias), **2,0 MB
→ 380 KB**, **86 915 px → 1 254 px**, e deixou de rolar nos dois eixos
para caber num ecrã (66 ms no servidor). A célula diz o título e a
entidade, e não «prazo» 1 086 vezes. Entraram as **abas da escada**,
sem números — sem elas o calendário por omissão mostra as propostas em
aberto, que hoje são zero, e a única saída era escrever `?estado=` na
barra de endereços. Abaixo de 900px a grade rola dentro de si.

**E a fase 2, os descritivos.** Eram 17 páginas a abrir com um
parágrafo a dizer o que a página é. O `<h1>` passou a ir **dentro** do
`<summary>` de um `<details>`, com um «?» ao lado: a linha do título
alterna e o texto aparece por baixo, nativo e sem JS. **Fechado por
omissão e sem memória** — um «?» que se lembra de estar aberto volta a
pôr o parágrafo no ecrã todos os dias, que é o que isto vem tirar.

**Um erro do CRM apanhado pelo caminho**: as `tarefas` não têm chave
estrangeira com `ON DELETE CASCADE`, e os **três** sítios que apagam
propostas deixavam as tarefas automáticas atrás. Passaram a ir pelo
`apagar_propostas()`, e o `iniciar_db()` limpa as que já existiam (sem
tocar nas escritas à mão). Importa porque a página de abertura lê essa
tabela: uma tarefa órfã aparecia lá como trabalho de uma proposta que
não existe. Saiu também um `volta_ao_referer("/quadro")` que apontava
para a página que desapareceu a 15/09.

**E a fase 4, a abertura.** «Hoje a abertura é a lista dos concursos;
eu quero chegar e ver o estado do negócio e o que tenho de fazer.» O
`/` passou a ser essa página e a lista mudou para **`/concursos`**; a
barra ganhou um primeiro item, **Hoje**. Quatro números (em jogo, taxa
de vitória, por decidir, para fazer), o que há para fazer em **quatro
baldes** — atrasadas · hoje · próximos 7 dias · mais para a frente, que
não é o mesmo que ordenar por data — e uma linha com o que entrou hoje
e a última verificação. A saudação acompanha a hora. Ressuscita o que o
`/hoje` fazia antes de sair a 15/09, e fecha o «o que tenho de fazer
hoje, em todos os concursos ao mesmo tempo» que tinha ficado por
responder. **Ensaiado numa cópia da base** (1,26 GB, porta 8801) com
seis propostas e oito tarefas espalhadas pelos quatro baldes, que é a
única forma de ver o ecrã com conteúdo sem mexer na base a sério. São
**945 testes**.

**E começou a fase 5, a passagem ecrã a ecrã: o primeiro foi a ficha
do anúncio.** O índice prometia seis destinos e a página tinha oito
blocos com âncora — faltavam o **«A nossa proposta»**, que é onde o
trabalho vive, e os «Contactos». Cinco blocos passaram a ter o «?» com
o que eles são, e o que ficou no ecrã foi o que é facto: «2 lotes; sem
registo de a que fomos», «Parecido = tem em comum estes termos», «de
3 983 ao todo», «o preço contratual é o de partida». Saiu também um
erro latente que o teste destapou: um anúncio sem `url` derrubava a
ficha inteira com um 500.

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

Por cima das abas há o **interesse** (Configurações › Interesse), os
CPV que a casa trabalha: está ligado quando há CPV guardado, e com ele
definido a lista não tem árvore nem «excluir CPV».

**O que está implementado.** O esqueleto de informação (três
intenções na barra de cima: Anúncios, Em curso, Mercado, com Alertas e
os Indicadores dentro das Configurações), o desenho visual «ardósia e
âmbar», a ficha em dossier com o
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
o chame (**e saiu de vez a 15/09/2026**, por decisão dele: 603 linhas de
código e 638 de testes; está no histórico do git). Em vez disso **o radar dita o modelo**: um `.xlsx` gerado em
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

**Código e testes.** `radar.py` com 18 971 linhas, `casa.py` com **630**
(eram 1 307: saiu o leitor do Excel antigo),
`teste_radar.py` com **911** testes que correm em ~66 segundos, sem rede e sem
tocar na base verdadeira (contados a 15/09/2026, ao fim do CRM e da limpeza do
código morto; a 14/09 a auditoria ponytail tinha tirado ~160 linhas líquidas ao
conjunto e ~360 ao radar.py). **Mais de metade do `radar.py` é painel**
(10 588 linhas, 55% — da banda `# --- painel` à `# --- arranque`).

**A limpeza do código morto** (15/09/2026, a pedido dele): saíram oito
funções que só os próprios testes chamavam (`estado_aberto`,
`_modelo_com_fornecedor`, `chips_dos_lotes`, `soma_precos_base`,
`contar_propostas`, `CAMPOS_DA_TRIAGEM`, `_EM_AZUL`, `ROTA_DA_VISTA`) e
três classes de CSS de 240 (`.modos`, `.tag.lote-fora`, `.carta-meta`) —
contadas por busca literal com asserções nos limites do bloco, depois de
três detectores por expressão regular darem 30, 104 e 81 falsos
positivos. Duas funções das etapas 4 e 5 **não estavam mortas, estavam
por ligar** e ligaram-se: `propostas_por_fechar()` é agora o aviso no
topo de «O negócio», e `taxa_por_divisao_cpv()` a lista «Onde se ganha,
por área». **O leitor do Excel antigo saiu** ao fim do dia, quando ele
disse «corta, fica no git»: 603 linhas do `casa.py` e 638 do
`TestRegistoDaCasa`, que encolheu para as seis provas de código vivo
(`TestEstadoEfectivoDaCasa`). O corte destapou um erro que nenhum teste
apanhava: o `--casa-desfazer` apagava o histórico por `quem='Excel'`, e
já só a importação pelo modelo escreve ali — agora repõe-se pela cópia.

**As duas bases.** `radar.db` (era 100 MB em Agosto e 558 MB na manhã
de 04/09/2026; ao fim dessa tarde, com os onze anos dentro, são
**1,23 GB**, com os onze anos e os detalhes todos lidos — o
`anuncios.texto` sozinho são **843 MB**; 23 tabelas, no git só a triagem, as propostas, as tarefas e os contactos,
cópia diária em `copias/`) e
`contratos.db` (2,36 GB, 1 987 798 contratos de 2015 a 2026, 178 978
entidades, **fora do git**, refaz-se com `--contratos`). **O tamanho da
`anuncios` é um número de desempenho, não de arrumação**: cada
varrimento dela arrasta esses 843 MB do disco, e é por isso que as
contagens do painel têm de ir por índice de cobertura — ver a
`docs/armadilhas.md`, «A base, as migrações e o disco». **Não se cruzam em SQL**: cada uma tem a sua ligação
(`liga()` e `liga_corpus()`) e quem junta os resultados é o Python.

## O que não corre sozinho, e é preciso saber

- **Os três temporizadores do systemd** (`agendar.sh`) são o que faz o radar
  verificar sem ninguém. Se faltarem, só recolhe com o painel aberto — e
  o relógio interno recupera os slots falhados, o que faz a tabela
  `slots` parecer certa. O painel avisa a vermelho (até 8/09/2026 só
  no Windows: fora dele devolvia «nada em falta»; o ramo do Windows
  saiu a 14/09/2026).
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
- **O repositório mudou a 07/09/2026**: agora é `afonsonp/radargov` (o
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
