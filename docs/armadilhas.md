# Armadilhas: o que não é óbvio, por área

Cada ponto aqui custou tempo uma vez. **Lê a área antes de lhe mexer** —
não o ficheiro todo. Saíram do `CLAUDE.md` a 3/09/2026, sem uma palavra
mudada, porque lá carregavam-se inteiros em todas as sessões.

O contexto por trás de cada um está no `docs/referencia.md` e no
`docs/diario/`. As regras de trabalho continuam no `CLAUDE.md`.

## Índice

- [A recolha, e as fontes](#a-recolha-e-as-fontes) &middot; 14
- [As peças e as plataformas](#as-pecas-e-as-plataformas) &middot; 9
- [O modelo que lê as peças](#o-modelo-que-le-as-pecas) &middot; 5
- [O motor de filtros](#o-motor-de-filtros) &middot; 9
- [Datas, números e texto](#datas-numeros-e-texto) &middot; 7
- [A árvore de CPV](#a-arvore-de-cpv) &middot; 3
- [Contratos e entidades](#contratos-e-entidades) &middot; 13
- [Alertas e interesse](#alertas-e-interesse) &middot; 4
- [Triagem, quadro e ficha](#triagem-quadro-e-ficha) &middot; 10
- [O registo da casa](#o-registo-da-casa) &middot; 2
- [A base, as migrações e o disco](#a-base-as-migracoes-e-o-disco) &middot; 8
- [Trabalhos de fundo e arranque](#trabalhos-de-fundo-e-arranque) &middot; 6
- [Contas e a porta](#contas-e-a-porta) &middot; 5
- [A interface](#a-interface) &middot; 12
- [Convenções](#convencoes) &middot; 2

São 109 ao todo. Contam-se com `grep -c '^- \*\*'` por secção — e o
índice volta a ter de se recontar sempre que se acrescenta um ponto:
somava 78 a 3/09/2026 e 88 a 4/09/2026, as duas vezes abaixo do que as
áreas tinham.

---

## A recolha, e as fontes

O DR, a Vortal, e como um anúncio entra na base.

- **Não se filtra nada à entrada.** Decisão tomada depois de uma primeira
  versão que filtrava por pontuação: entra tudo o que a parte L publicar, e
  a triagem faz-se no painel. Não reintroduzas filtros em `recolher()`.

- **Uma recolha grande faz-se por JANELAS de datas, nunca numa janela
  só.** Duas razões, medidas contra o portal a 04/09/2026. A primeira: o
  `recolher()` acumula tudo em memória e **só chama o `guardar()` no
  fim** — de 2015 a 2024 são ~6 800 páginas e horas de corrida, e um
  corte de rede a meio não gravava nada. A segunda é pior porque é
  silenciosa: **a ordem do DR deixa de ser cronológica nas páginas
  fundas.** Com a janela 2015-2026 ordenada por data, StartIndex 20 000
  devolve 2024, mas 60 000 devolve 2019 e 120 000 e 200 000 devolvem
  2022 — repetível (três voltas, sempre o mesmo), portanto estável, mas
  não é por data; é o que um Elasticsearch faz em profundidade sem
  desempate. **Não há tecto de profundidade** (200 000 responde), por
  isso o que obriga às janelas não é um limite: é a ordem e a gravação.
  `janelas_de_datas()` parte o intervalo e `recolher_intervalo()` grava
  cada uma. Os dois limites do filtro do DR são **inclusivos** — a
  janela seguinte começa no dia a seguir, e um `-1` a mais perdia um dia
  por janela, 118 dias numa recolha de dez anos, sem dar erro. Medida a
  cobertura numa janela real: 547 anúncios pedidos, 547 na base.

- **A cobertura conta-se por REFERÊNCIA, nunca por data.** O DR devolve
  **o mesmo anúncio com datas diferentes conforme a janela que se
  pede**: o `1205/2023` vem com `2023-01-27` quando se pede Janeiro e
  com `2023-06-01` quando se pede Junho, e como o `guardar()` é INSERT
  OR IGNORE, fica com a data da primeira janela que o viu. Comparar o
  total do DR num mês contra um `GROUP BY substr(data_pub,1,7)` da base
  parece uma verificação e é uma armadilha: a 04/09/2026 acusou 4 390
  anúncios «em falta» em 2023 que estavam todos lá, guardados noutros
  meses. A verificação certa é pedir as **referências** da janela e ver
  quantas existem na base — foi assim que se confirmou 100%.

  E **`hits.total.value` não é o número de anúncios distintos**: é a
  contagem de hits do Elasticsearch, e a listagem devolve menos refs
  distintas do que ele diz (1 387 para 1 692 em Janeiro de 2023, 1 909
  para 1 940 em Fevereiro). Serve para ordem de grandeza, não para
  aferir cobertura.

- **O BASE não traz anúncios novos.** Medido, e a decisão já foi tomada:
  os "anúncios" do Portal BASE são o mesmo universo do DR (`nAnuncio` é o
  `ref` do radar, o `url` aponta para o diariodarepublica.pt), e o dump é
  semanal, portanto mais atrasado que o radar. **Abaixo dos limiares não
  existe anúncio nenhum** — esses procedimentos só se vêem como contrato
  celebrado. Não acrescentes coluna `fonte` nem mexas na deduplicação à
  espera de uma segunda fonte de anúncios **vinda do BASE**: não há. E o
  conjunto "OCDS" do dados.gov está vazio desde 2022; o que se usa é o
  dump normal do IMPIC. **A ressalva vale só para o BASE**: as
  plataformas publicam procedimentos que a parte L não publica, e essa
  segunda fonte EXISTE desde 31/08/2026 (decisão do Afonso) — ver o
  ponto seguinte.

- **A segunda fonte é a Vortal, e só consultas preliminares.** O âmbito
  é decisão dele (31/08/2026): «só consultas preliminares ou algo que
  não seja publicado no DR — não quero duplicação». `recolher_vortal()`
  corre em cada verificação (`vortal_preliminares` no config) contra a
  pesquisa pública (`SearchTenders`), filtra país PT e tipo preliminar
  — o rótulo muda com o idioma da sessão (`TIPOS_PRELIMINAR` aceita
  «GovPT - Consulta Preliminar» E «Quick Tender GovPT», que são o mesmo
  tipo) — e guarda com `fonte='vortal'` e ref `PT1.NTC.x`. **Nunca
  alargues os tipos**: concursos públicos da Vortal estão no DR e
  duplicavam. As releituras do DR filtram por
  `COALESCE(fonte,'dr')='dr'`; a cadeia das peças aceita o link
  público porque o PT1.NTC vem às claras. A acingov ficou de fora: a
  listagem pública dela não distingue tipos — alargar é decisão nova.

- **O DR não emenda um anúncio: publica outro.** O texto da
  republicação começa por «Alteração do Anúncio de procedimento n.º
  18372/2026, de …» e é a única forma que existe (medido a 01/09/2026:
  763 dos 5 661 textos lidos, 13,5%, todos com esse prefixo; 103 citam a
  alteração anterior e não o original). Até aí cada uma entrava como
  anúncio novo — o mesmo concurso três vezes no por ver, e 511 descartes
  do Afonso sobre procedimentos que já tinha descartado. A regra: **o
  original é a ficha do procedimento** (triagem, quadro, peças e leitura
  ficam nele) e a alteração fica na base, com o próprio texto, em
  `estado='alteracao'` e fora de todas as listas (`condicoes()` exclui-a
  quando `estado=""`; os outros estados nunca a apanham). `campos_do_
  detalhe()` lê o `altera`; `aplicar_alteracao()` segue a cadeia até à
  raiz (`raiz_da_alteracao`), passa ao original o que está em vigor —
  prazo, preço base, CPV, plataforma, link das peças — **do membro mais
  recente da cadeia**, seja qual for o que acabou de ser lido (o
  `ler_detalhes()` vai do mais recente para o mais antigo), e grava
  `alterado_por` no original. Se foi na alteração que alguém decidiu, a
  decisão passa para o original. **Título igual na mesma entidade NÃO é
  chave**: 58 pares assim sem citação são procedimentos diferentes. Três
  guardas que não são decorativas: a releitura de um original já
  alterado não pode escrever-lhe os campos da página dele (é a versão
  antiga, e repunha o prazo velho — `_guardar_detalhe()` e `reparsear()`
  só lhe guardam o texto), o `reler_marcados()` relê pela página da
  alteração em vigor, e `mudar_estado()` recusa triar uma alteração. Os
  763 que já estavam na base ligaram-se por marca (`alteracoes_agrupadas`)
  no arranque; `--reler` volta a passar por tudo.

- **A pesquisa da Vortal dá a linha; o CPV e o NIPC vêm do detalhe.**
  Os 16 campos do `SearchTenders` são título, entidade, datas, estado
  e tipo — **nenhum é CPV nem NIPC**. Até 01/09/2026 guardava-se a
  linha com `detalhe_lido=1` e as 24 consultas na base tinham o CPV
  vazio: invisíveis ao filtro por código, à árvore, aos alertas por
  CPV e ao recorte do interesse, que é permanente e as escondia todas
  sem uma palavra. `detalhe_da_preliminar()` chama
  `GetRegionConfigurationByContractNoticeUId` (o `VORTAL_REGIAO`), que
  responde ao `PT1.NTC` às claras e sem sessão — 100% de CPV e de NIPC
  nas 24 medidas — e `ler_preliminares()` grava e só então marca
  `detalhe_lido=1`. **Não confundas com o `GetPublicTenderInformation`**:
  esse é o primeiro salto das peças, só aceita o identificador cifrado
  do DR e responde 500 ao PT1.NTC. Por causa disto o `ler_detalhes()`
  filtra a fonte: as duas passam por `detalhe_lido=0`, e sem o filtro
  a fila do DR mandava um `PT1.NTC` ao portal e a resposta sem JSON
  acabava a **marcar o token como expirado** — um falso alarme de
  captura expirada é pior que não ler nada. O questionário público
  (`CB1_SummaryCN_QuestionnaireHTML`) é a lista dos artigos pedidos, e
  numa consulta preliminar é o conteúdo: tira-se o `<style>` **antes**
  de despir as etiquetas, e o cabeçalho vem em `<th>` soltos no
  `<thead>`, sem `<tr>`.

- **As datas da Vortal vêm em UTC e mostram-se em hora de Lisboa.**
  A API dá `2026-09-03T22:59:00Z` e a plataforma mostra 23:59 — no
  Verão Lisboa é UTC+1. `hora_de_lisboa()` faz a conta pela regra da
  UE (último domingo de Março às 01:00 UTC ao último domingo de
  Outubro), à mão porque o `zoneinfo` depende de dados de fusos que
  este Windows não garante. Escrever o UTC punha o prazo uma hora mais
  cedo do que a plataforma diz. Só a Vortal precisa disto: o DR
  publica datas já locais.

- **A API da Vortal responde de DUAS formas ao mesmo pedido.**
  `GetPublicTenderInformation` (o primeiro salto, a partir do link
  cifrado do DR) devolve ou `contractNoticeUrl` com a `documentList`
  vazia — e as peças saem do segundo salto,
  `GetContractNoticeDocuments` —, ou a `documentList` já cheia e
  **sem** `contractNoticeUrl`. `_info_vortal()` lê as duas; o código
  só lia a primeira e, na segunda, devolvia lista vazia sem erro
  nenhum: metade dos anúncios da Vortal trazia o anúncio e mais nada,
  em silêncio (o Afonso deu por isso no 22005/2026). Os nomes dos
  ficheiros também não se chamam o mesmo — `name` numa resposta,
  `documentName` na outra. Ao mexer aqui, **mede as duas formas contra
  anúncios reais**, não uma.

- **`ler_detalhes()` desiste em SILÊNCIO, e numa corrida de horas isso
  importa.** Um pedido que falhe de rede ou traga JSON ilegível faz
  `break` no ciclo e a função devolve `(feitos, "")` — menos do que o
  lote e **aviso vazio**. Na verificação diária não se nota: a volta
  seguinte é dentro de oito horas. Mas o `--detalhes`, que enche a base
  toda a ~1,45 s por anúncio (~24 h para os 60 mil), parava a primeira e
  perdia a noite por causa de um segundo. `detalhes_em_lote()` tolera
  `VOLTAS_VAZIAS` (3) seguidas com 30 s de intervalo, e o que distingue
  «acabou» de «falhou a rede» é o **contador** — sem ele, o fim normal
  da fila gastava as três voltas e 60 segundos a olhar para uma fila
  vazia. Um aviso verdadeiro (captura recusada) para logo: bater outra
  vez na mesma porta não a abre. A espera, a leitura e a escrita são
  injectáveis, e o último recurso das três voltas tem teste próprio —
  um teste que dependesse de sleeps verdadeiros mediria o escalonador.

- **Um anúncio antigo que já não exista não entala a fila.** O
  `detalhe_lido=1` grava-se mesmo quando o DR responde sem texto, por
  isso a fila anda sempre para a frente. É por isso que o `--detalhes`
  pode ser retomável de forma trivial — e é uma propriedade a não
  perder: fazer o `detalhe_lido` depender de o texto vir preenchido
  punha um anúncio morto a ser pedido para sempre, e a corrida de 24
  horas nunca acabava.

- **`ler_detalhes()` e `ler_detalhes_paralelo()` têm ritmos separados,
  de propósito.** A rotina diária (09h/17h) chama sempre
  `ler_detalhes()` sequencial, 1s de intervalo — nunca mudou. O
  `--detalhes` — que pode correr horas seguidas — usa
  `ler_detalhes_paralelo()`, `CONCORRENCIA_DETALHES` (8) pedidos ao
  mesmo tempo, decisão do Afonso a 3/09/2026 depois de lhe dizer que
  **o risco de bloqueio de IP por rajada não está medido nem
  confirmado nem afastado** (o DR não tem rate-limit conhecido, mas
  ninguém testou o que acontece com muitos pedidos seguidos ou em
  paralelo). Ao mexer no ritmo de qualquer um dos dois, não presumas
  que o outro segue: são decisões separadas, com riscos diferentes (a
  rotina é 40 pedidos espaçados por 8 horas; o `--detalhes` é dezenas
  de milhares seguidos, agora em paralelo).

- **Um ensaio isolado subestima o custo do comando real.** Duas vezes
  no mesmo dia (3/09/2026): (1) descer o intervalo sequencial de 0,3s
  para 0,1s deu **mais lento** medido (0,78-0,82s por anúncio, contra
  0,68s), sem erro nenhum — sinal de que o tempo total não depende só
  do nosso `sleep`, também da resposta do portal, que pode reagir a
  carga sustentada abrandando em vez de recusar; revertido por não
  haver benefício. (2) Já com a concorrência integrada,
  `ler_detalhes_paralelo()` isolado (um lote, uma `ThreadPoolExecutor`)
  mediu 0,118s/anúncio, mas o `--detalhes` completo a correr mediu
  0,19s — a diferença é a sobrecarga de `detalhes_em_lote()` abrir uma
  pool de threads NOVA a cada volta de `lote` (40) e reler o
  `curl_detalhe.txt` do disco a cada volta, custo que um ensaio de um
  lote só nunca paga. **Não presumas que o número de um ensaio pequeno
  vale para a corrida inteira: mede com o comando real, durante
  minutos, não com uma amostra de segundos.**

- **O DR não tem API pública.** O radar faz-se passar pelo browser com os
  cabeçalhos e a forma do corpo das capturas `curl_*.txt`. **O token NÃO
  expira, e não é de sessão** (medido a 02/09/2026 com `medir_captura.py`,
  três voltas contra o portal): é o `AnonymousCSRFToken` publicado no
  `OutSystems.js`, sem cookie o DR nem o verifica, a `moduleVersion` não
  tranca, e a única tranca é a `apiVersion` do ecrã, que vive no script
  listado no `moduleinfo`. `renovar_pecas_dr()` vai buscar as três por
  GET e `perguntar_ao_dr()` é a **porta única** dos quatro pedidos ao
  portal (recolha, detalhe, ficha, releitura): se o DR responder a casca
  ou `hasApiVersionChanged`, renova à força e repete uma vez, e só depois
  disso regista expiração. Nunca escrevas um `requests.post` solto ao DR
  — há teste a guardá-lo. O que resta à captura é a forma do corpo, e é
  só por essa que um dia se refaz (secção 3 do `LEIA-ME.md`). Nunca
  edites estas capturas: um hook bloqueia-o.


---

## As peças e as plataformas

Trazer os documentos do procedimento, e o que se faz com o texto deles.

- **"Abrir plataforma" não é o link das peças.** O DR nunca publica o
  endereço da página do procedimento: traz a raiz da plataforma e o
  link das peças, e o botão abria o segundo — na acingov isso
  descarrega um ZIP. `link_do_procedimento()` decide por plataforma:
  na Vortal é `contract-notice-view/PT1.NTC.x`, resolvido pela rota
  `/plataforma/<ref>` e **guardado em `anuncios.link_proc`** (a ficha
  não pode ir à rede a cada abertura); na anogov/ComprasPT/ESPAP o
  próprio `acessoDocs.jsp` é a página do procedimento (traz referência
  interna, objecto e tipo — não há outra, o resto da aplicação é JSF
  por POST); **na acingov não existe** — medido a 01/09/2026, o botão
  "consultar procedimento" da lista pública só abre "para aceder a
  este procedimento inicie sessão" —, por isso o botão diz "Procurar
  na acingov" e abre a pesquisa pública. Não inventes um endereço de
  procedimento para a acingov sem voltar a medir.

- **A pesquisa nas peças (B09) foi implementada e retirada no mesmo
  dia** (30/08/2026), por decisão do Afonso: as peças só existem depois
  de marcar "interessa", por isso a pesquisa chegava sempre tarde
  demais para ajudar a decidir. Não a reintroduzas — nem `q_pecas` em
  `condicoes()` nem caixa na ficha; há teste a guardá-lo
  (`TestPesquisaNasPecasRetirada`). O `iniciar_db()` limpa o índice
  FTS de quem chegou a ter a versão retirada. **A versão que ele
  queria já existe e é outra coisa**: procurar DENTRO de um documento,
  no visualizador (`visualizador_de_peca()`, com os destaques a
  amarelo). Essa é por peça, não pelo acervo — não confundir as duas,
  nem tomar uma como caminho para a outra.

- **As leituras das peças afinam-se no config.json** (`leituras`:
  quais/âncoras/instrução por campo, via `leituras_activas()`), com
  validação: o inválido deixa ficar o de origem, nunca cala uma leitura
  em silêncio. Campos novos não entram por aí — a `analise` tem colunas
  fixas.

- **A vigilância das peças foi retirada a 03/09/2026**, no dia a
  seguir a ter sido feita, por decisão do Afonso. Não porque estivesse
  errada — funcionava e tinha sete testes — mas porque **vigiava seis
  anúncios**: só olhava para os «interessa», e só havia seis na base.
  Foi construída na ponta mais estreita de um funil que tem 60 217
  anúncios por ler à entrada. Saíram com ela `vigiar_pecas()`,
  `pecas_disponiveis()`, `_nome_sem_corpo()`, o campo `peca_nova` do
  resumo e a volta que a verificação lhe dava. **Se voltar**, volta com
  a lição escrita: o que a fazia valer a pena não era o código, era
  haver anúncios marcados que chegassem. Está em `git show 31fd388`.

- **A releitura dos marcados é vigilância, não recolha.**
  `reler_marcados()` relê por verificação até 25 anúncios
  interessa/quadro com prazo aberto; `_guardar_detalhe()` compara prazo
  e preço base com o guardado e grava as mudanças na fila `alteracoes`
  (reconhecer/enviar separados, como os alertas) e no histórico. Só se
  avisa valor→valor diferente: um campo que passa a vazio é o parser a
  tropeçar, não uma alteração — não grites lobo.

- **O texto extraído das peças leva `\f` em linha própria** entre
  páginas: é por ele que as fontes da análise dizem "(pág. 1–5)". O
  recorte e as páginas saem das mesmas janelas (`_janelas_do_recorte`);
  um texto sem marcas não declara páginas — não se inventam.

- **Só passam pelo modelo documentos públicos** (Cadernos de Encargos e
  Programas de Concurso). Propostas, CVs e trabalho próprio não.

- **O OCR foi retirado a 03/09/2026**, por decisão do Afonso, um dia
  depois de entrar. Funcionava — RapidOCR, modelos PP-OCR em ONNX, à
  escala 2,5 — mas tinha lido **8 documentos de 182**: os CE/PC sem
  camada de texto são 2 em 12, e há 182 peças em disco porque só há
  seis anúncios marcados. 77 MB de dependências e uma banda inteira do
  `radar.py` por 8 documentos. Está em `git show 8963251` e `01e13bb`,
  com as medidas todas, e o que lá está escrito sobre a escala vale
  para quem o reponha: **abaixo de 2,0 o modelo não desfaz a linha,
  adivinha-a** (leu «110» onde a página diz «≥170 cv», «2036» onde
  estava «2026»), e por isso uma escala só se aprova a ler os valores
  desenhados, nunca pelo aspecto do texto.

- **`texto_estado` tem quatro valores, e dois são legado.** `ok` (o
  pypdf leu), `scan` (PDF sem camada de texto — é um veredicto sobre o
  conteúdo e fica), `erro: …` (falha da ferramenta, retenta-se), «não
  é PDF». Os `ocr` e `imagem` que estão na base vieram do OCR que
  saiu: o texto dos `ocr` é texto a sério e continua a servir
  (`documentos_com_texto()` pergunta por `IN ('ok','ocr')`), e
  `imagem` lê-se como `scan`. Não se produzem mais nenhum dos dois.


---

## O modelo que lê as peças

Orçamento, cadeia de reserva, chaves.

- **Orçamento do modelo, não contexto.** O tecto da conta Groq são 8000
  tokens/minuto, e é ele que manda no tamanho do pedido — daí
  `TECTO_RECORTE = 7000` caracteres e três pedidos separados em vez de um.
  Juntos, as âncoras do objecto gastavam o orçamento antes de chegar à
  tabela de perfis. Há também um tecto diário: `SEM_ORCAMENTO_HOJE`.

- **Cadeia de reserva, não um fornecedor.** O tecto diário da Groq (200
  mil tokens) acaba a meio de uma releitura do acervo. `_perguntar()`
  desce `FORNECEDORES` até alguém responder, e `_ESGOTADOS` guarda quem
  já bateu no tecto **nesse dia** — sem isso, cada pergunta voltava a
  bater na porta fechada. A mensagem do tecto diário só aparece quando
  **toda** a cadeia esgota (`cadeia_esgotada()`). Só entra quem tem
  chave: sem chaves novas, o comportamento é o de sempre.

- **«Não há peças para ler» não é erro do modelo.** `analisar_pecas()`
  devolve `(False, razão)` em dois casos que não são falha nenhuma: não
  há Caderno de Encargos nem Programa em disco, e os documentos são
  digitalizações sem texto. Estão em `SEM_NADA_PARA_LER`, e quem chama
  filtra-os com `e_falta_de_pecas()` antes de escrever a marca. Até
  4/09/2026 iam todos para «Último erro da leitura pelo modelo»: dos
  três que lá estavam nesse dia, um era uma **consulta preliminar**
  (que não tem Caderno de Encargos), outro um anúncio cujo `link_pecas`
  é a página de entrada da Vortal sem código de procedimento, e o
  terceiro tinha sido lido com sucesso 1h25 depois. Acusavam o modelo
  de uma coisa que é das peças. Continuam no histórico da ficha, que é
  onde interessam.

- **`analise.modelo` diz quem respondeu**, não o modelo configurado
  (`groq:openai/gpt-oss-120b`). Por ser variável, passa pelo
  `juntar_fontes()` como as fontes — uma releitura parcial apagava o
  registo do modelo que leu os outros campos.

- **As chaves da API** lêem-se de `<fornecedor>_API_KEY.txt` na pasta
  (`groq_API_KEY.txt`, `chave_api.txt`, `openrouter_API_KEY.txt`,
  `nvidia_API_KEY.txt`) ou das variáveis `GROQ_API_KEY`,
  `OPENROUTER_API_KEY`, `NVIDIA_API_KEY`. O `.gitignore` é
  deliberadamente largo (`*api_key*`, `*token*`, `*secret*`) porque a
  chave já apareceu com nomes diferentes — e é ele que já cobre os
  nomes novos.


---

## O motor de filtros

- **A tradução de «texto com `|`» para SQL está num só sítio**
  (`frag_de_texto()` e `frag_de_exclusao()`, banda `comum`, desde
  03/09/2026). Estava escrita quatro vezes — duas em cada
  `condicoes*()` — e a regra que ela contém já se pagou **duas vezes**:
  procurar na coluna crua em vez da normalizada custou ~11% dos
  resultados nos anúncios e 11,8% nos contratos, das duas em silêncio.
  A `norma` é argumento porque não é a mesma nas duas populações
  (`simplifica` para títulos e objectos, `norma_entidade` para nomes).
  **Isto não funde os dois motores** — continuam a ser dois, de
  propósito; partilham a tradução, não as perguntas. E continuam a
  devolver `(fragmento, valores)` sem tocar no `onde`: é o que deixa o
  `op=ou` juntar o lado das palavras ao do CPV sem baralhar a ordem dos
  placeholders.

`condicoes()` serve a lista, os alertas e os filtros guardados. Nada de recortes lá dentro.

- **Anúncios e contratos são populações diferentes, de propósito.** Um
  anúncio é uma oportunidade, um contrato já está assinado; os filtros
  nem coincidem (um anúncio não tem vencedor nem valor final). A lista
  de anúncios é **UMA página** (`/`, fusão de 31/08/2026 — a Triagem e
  a Pesquisa separadas duraram um dia; `/anuncios` redirecciona) com
  quatro abas cujo recorte vive em `condicao_da_aba()`, aplicado POR
  CIMA do motor com `com_recorte()` (e junto ao do interesse em
  `recorte_da_lista()`, que é o que a página chama): **por ver** = novo e ainda
  respondível (prazo aberto; sem prazo lido vale a publicação dentro
  de `detalhe_dias`), **interessados** = todos (um interessa expirado
  é trabalho em curso), **abandonados** = descartados à mão MAIS os
  por ver já não respondíveis — é recorte de leitura, a base não muda.
  O `estado` da aba tira-se dos args antes de chamar `condicoes()`
  (a aba dos abandonados é uma união que um `estado=?` não diz), mas
  continua na consulta canónica dos filtros guardados. **Nenhum
  recorte entra em `condicoes()`** — o motor serve os alertas e os
  filtros guardados, e o recorte lá dentro cegava-os em silêncio. Os
  contratos vivem em `/contratos`, com `condicoes_contratos()` própria.
  Nas tabelas filhas usa-se **`IN (SELECT ...)`, nunca `JOIN`**: com
  JOIN, um contrato ganho por um agrupamento repetia-se uma vez por
  adjudicatário. `IN` e não `EXISTS` por velocidade — o EXISTS passa por
  todos os contratos a perguntar por cada um (517 ms contra 183).

- **O `op` (E/OU entre palavras e CPV) é um modo, não um filtro**:
  sozinho não conta como pergunta em /contratos nem valida um alerta.
  Em `condicoes()`/`condicoes_contratos()`, os lados q e cpv montam-se
  como fragmentos (sql, valores) e só se juntam no fim — é o que mantém
  a ordem dos placeholders igual à dos valores; há um teste que conta
  os `?`. No modo OU, um CPV sem correspondência não acrescenta nada
  (o `1=0` é só do modo E).

- **Os avisos por filtro correm depois de `ler_detalhes()`** — um filtro
  por CPV só apanha o anúncio depois do CPV estar lido — e usam a
  `condicoes()` da lista. Nunca escrevas um segundo motor de filtros.

- **`(nenhuma)` e `(por ler)` são baldes diferentes.** `SEM_PLATAFORMA`
  é "detalhe lido, sem plataforma indicada" e exige `detalhe_lido=1`;
  `POR_LER` é "ainda sem detalhe lido", que é 92% da base. Sem a
  distinção, o selector dizia "(nenhuma) (56)" e a lista devolvia 60 645.
  Os números do selector contam sempre sobre os que têm detalhe lido, e
  o cabeçalho di-lo.

- **Os contadores dos separadores contam dentro do filtro**, com a mesma
  `condicoes()` da lista e sem a parte do estado. Contavam a base
  inteira: com um CPV posto diziam "Todos 66 009" por cima de uma lista
  de 234, e as ligações levavam o filtro atrás — o número e o destino do
  mesmo botão discordavam.

- **O `prazo` é um filtro dos anúncios** (`aberto`, `urgente`,
  `expirado`), e a janela do `urgente` é UMA — `janela_urgente()`, usada
  pelo filtro e pelo cartão dos indicadores. Já houve um "7" escrito à
  mão no cartão com o filtro a 10, e outro dentro de `etiqueta_prazo()`:
  um prazo a 9 dias saía verde ("folgado") na lista e contava como
  urgente no filtro. O número que um ecrã mostra tem de dar exactamente
  a lista que a ligação dele abre — **a cor da etiqueta é um desses
  números**. Tudo vem de `dias_urgente()` (config.json, editável em
  `/alertas`); nunca uses `DIAS_URGENTE` directamente num rótulo nem um
  limiar à mão num teste de cor — é só a omissão. Quem desenha em ciclo
  (lista, quadro, calendário) lê a janela uma vez por pedido e passa-a a
  `etiqueta_prazo(prazo, urgente)`: `dias_urgente()` abre o config.json a
  cada chamada.

- **Um filtro guardado é uma query string, não SQL, e não pertence a
  separador nenhum.** Guarda os campos que tiver (`CAMPOS_FILTRO`, ordem
  fixa — é ela que deixa reconhecer o filtro em uso por igualdade de
  texto), e cada página aplica os que entende (`CAMPOS_POR_VISTA`).
  `filtro_para(consulta, vista)` devolve a parte aplicável **e os campos
  que ficaram de fora**: esses nunca caem em silêncio — o chip fica
  marcado como parcial e um alerta com eles avisa só pela parte que
  serve, e diz que o faz. Aplicar "ganho por MEO" aos anúncios, onde não
  há vencedor, seria alargar o filtro sem avisar.

- **O `estado` entra sempre no filtro dos anúncios, mesmo vazio** —
  ausente é "por ver", vazio é "todos", como em `condicoes()`.


---

## Datas, números e texto

Formatos portugueses, normalização e o que o SQLite não sabe fazer.

- **`175.000,00 EUR` é formato português**: ponto nos milhares, vírgula
  nos cêntimos. Usa `euros_do_texto()`; um `float()` ingénuo dá 175,0.

- **As datas guardam-se ISO e mostram-se DD/MM/AAAA.** ISO porque ordena
  como texto; a apresentação passa por `data_pt()` e, quando leva hora,
  por `data_hora_pt()` (histórico da ficha, barra do corpus, barra
  lateral). Nunca ponhas uma data em ISO no HTML **nem no CSV** — um CSV
  também é para ver. E o CSV escreve o estado pelo `_NOMES_ESTADO`
  ("por ver"), não pela chave interna ("novo").

- **Datas de filtro validam-se com `data_de_filtro()`** — só ISO; lixo
  ignora-se e a página avisa (`avisos_de_datas`), incluindo o intervalo
  invertido. Um `de=lixo` comparado com datas esvaziava a lista em
  silêncio.

- **A pesquisa procura em `titulo_norm` e `entidade_norm`, nunca nas
  colunas originais.** O `LIKE` do SQLite só baixa maiúsculas de letras
  ASCII: para ele `Ç` e `ç` são letras diferentes, e escrever
  "aquisição" perdia os 14% de títulos escritos todos em maiúsculas —
  11% de cada pesquisa, sem aviso nenhum. As colunas enchem-se numa
  migração idempotente do `iniciar_db()`, com `simplifica()` registada na
  ligação (`c.create_function`), e o termo procurado normaliza-se do
  mesmo modo. Os índices `ix_anuncios_titulo_norm` e
  `ix_anuncios_entidade_norm` **não são decorativos**: as colunas ficaram
  depois do `texto` do anúncio inteiro, e sem eles o SQLite desserializa
  alguns KB por linha — 4,7 s contra 0,4.

- **Nos contratos, a mesma regra, com a norma certa por coluna.** O
  objecto procura-se em `objecto_norm` (termo por `simplifica()`); os
  nomes de entidade em `adjudicante_norm`/`nome_norm`, com o termo por
  `norma_entidade()` — é ela que enche essas colunas e que troca `&`
  por " e ". Procurar com a norma errada volta a perder 11,8%.

- **O dump do IMPIC vem escapado para HTML, às vezes duas vezes.** Tudo
  o que é texto passa por `_des_html()` à entrada do importador
  (desescapa até estabilizar), senão "Ramos &amp; Filhos" fica
  impesquisável e o painel mostra `&amp;` — 5 998 entidades estavam
  assim. O corpus antigo foi reparado por uma migração com marca
  (`html_desescapado`).

- **Os números levam espaço inquebrável** (U+00A0) nos milhares, nos
  três formatadores (`mil_pt`, `euros`, `euros_curto`). Com espaço
  normal o browser parte "1 363 300" ao fim da linha. Há um teste que
  os obriga a concordar.


---

## A árvore de CPV

Uma árvore, duas fontes de contagem, dois campos.

- **A árvore de CPV vem antes dos filtros guardados** e está em todas as
  páginas onde se procura por CPV — anúncios, contratos e ficha da
  entidade. Onde houver campo `cpv`, tem de haver árvore: a caixa de
  texto solta só deixava escolher um código.

- **A árvore de CPV é uma só, com duas fontes de contagem.** `arvore_html()`
  põe um `data-de` no `<details>` e o JS lê dali a rota
  (`/cpv.json?de=anuncios|contratos`); `FONTES_CPV` diz de onde se conta.
  Não copies o JS para o segundo separador, e não reutilizes as contagens
  dos anúncios nos contratos — são outras (1 548 códigos têm anúncios,
  5 657 têm contratos). O campo tem `id='filtro-cpv'` nos dois, que é por
  onde a árvore lê e escreve. O `_CPV_CACHE` é um dicionário por fonte.

- **A árvore escreve em DOIS campos, e por isso os filhos não se
  trancam.** Marcar uma divisão inclui tudo o que está por baixo;
  desmarcar um código lá dentro **tira só esse ramo** e escreve-o no
  `cpv_excl` (`id='filtro-cpv-excl'`, presente nas quatro páginas com
  árvore). As caixas estiveram desactivadas de propósito porque o
  filtro "não sabia excluir" — sabe, e a decisão do Afonso a
  01/09/2026 é que tem de dar: marcar só os sub-códigos em vez da
  divisão **perde os anúncios que trazem apenas o código da divisão**,
  e esses são oportunidades. O estado vive em `ARV_SEL`/`ARV_EXC` e as
  caixas são um desenho dele (`arvorePintar()`, decidido por
  `arvoreEstado()`) — nunca o contrário; com o estado espalhado pelas
  caixas, um descendente marcado "só para se ver" acabava dentro do
  filtro. Voltar a marcar dentro de um ramo excluído **empurra a
  exclusão para baixo** (`arvoreDesexcluir()`, exclui os irmãos do
  caminho): o par (cpv, cpv_excl) sabe somar e subtrair uma vez, não
  sabe alternar.


---

## Contratos e entidades

O corpus do Portal BASE — 1,99 milhões de linhas (2015 a 2026, desde
03/09/2026), e por isso a velocidade conta.

- **Sem filtro, `/contratos` não mostra lista nenhuma.** São 1,99 milhões
  de contratos e por data não dizem nada; a página levava 48 s a montar.
  A pergunta vem primeiro — ao contrário dos anúncios, onde a lista
  inteira é o acervo por triar. A paginação corre num CTE com o `LEFT
  JOIN entidades` e as subconsultas dos nomes **depois do `LIMIT`**, e há
  índice em `contratos(data_celebracao, id)`: sem ele, ordenar 1,36
  milhões para mostrar 20 levava 6 s — e o corpus cresceu 46% desde
  essa medição.

- **Os gráficos dos contratos correm sobre o filtro da lista**, não sobre
  o corpus todo: o filtro é a pergunta. Pedidos só ao abrir o `<details>`
  (`/contratos/resumo`; sem filtro eram ~7 s no corpus de 7 anos, e o
  corpus são 12 desde 03/09/2026 — o
  "~800 ms" antigo era doutro corpus, e a lentidão vem das cinco
  consultas de sempre, medida a 30/08/2026 no `docs/diario/`), e a rota
  devolve **HTML e não JSON** — desenhar continua em Python, com
  `<div>`s dimensionados, sem biblioteca. No "quem ganha", o valor
  reparte-se pelos adjudicatários (`contratos.n_adj`): um agrupamento de
  três não vale três vezes o mercado. O trimestre a decorrer vai às
  riscas, senão parece uma queda a pique. São sete: quem ganha, quem
  compra, como se compra, concentração, tamanho dos contratos, desconto
  sobre o preço base, evolução. **O desconto agrega por `n_anuncio` e
  nunca por linha** — a média por linha dá -18,9%, porque cada lote
  compara com a base do procedimento inteiro; as exclusões estão em
  `descontos_por_procedimento()`.

- **As renovações são um MODO dos contratos** (fundidas a 31/08/2026,
  decisão 6.1-A): `/contratos?ver=fim` filtra pela coluna
  `fim_estimado` (celebração + prazo em dias; coluna e não expressão,
  com índice próprio), janela por whitelist (`MESES_RENOVACOES`/
  `meses_pedidos()`) porque entra numa expressão de data do SQL. A
  lista, o CSV e os gráficos filtram todos por
  `filtros_dos_contratos()` — uma conta só. A vista de campos
  continua a chamar-se `"renovacoes"` e exclui **`de`/`ate`** — dois
  eixos do tempo na mesma página confundiam; no modo fim esses campos
  desactivam-se com explicação, nunca caem em silêncio. O fim é
  estimado e o modo di-lo: prorrogações não constam do dump.
  `/renovacoes` redirecciona com o filtro atrás — não a removas, é o
  que segura filtros guardados e ligações antigas.

- **O nome não é a identidade de uma entidade: o NIF é.** A Universidade
  do Porto assina com 87 nomes e a MEO com 81, todos com o mesmo NIF.
  Agrupa-se sempre por `chave` (`chave_entidade()`: o NIF, ou `n:` mais o
  nome normalizado quando não há). `entidades` guarda o nome canónico —
  o mais usado — e `entidade_nomes` mapeia qualquer variante à chave, que
  é como o nome que o DR escreve chega ao corpus. Nunca agrupes nem
  filtres por `adjudicante` ou `a.nome`.

- **O `+` de `GROUP BY +a.chave` não se tira.** Desliga o índice de
  propósito: com ele o SQLite varre o índice e vai buscar cada linha ao
  acaso — **17 segundos** contra 1,5 num filtro por CPV. Pela mesma
  razão, o `LEFT JOIN entidades` vai **depois do `LIMIT`**: antes eram
  68 mil buscas ao índice para mostrar 10 linhas.

- **A entidade de um anúncio resolve-se pelo NIPC.** O DR publica-o em
  100% dos anúncios e é a chave do corpus — `entidade_do_anuncio(nif,
  nome)`, com o nome de reserva para os antigos. 98,2% contra 96,2% só
  pelo nome. A coluna `anuncios.nif` enche-se com `--reler`, sem rede.

- **O corpus de contratos é ficheiro à parte** (`contratos.db`), e não
  entra no funil: são contratos assinados, não oportunidades. Cruza-se
  em Python, **não em SQL**: cada base tem a sua ligação (`liga()` e
  `liga_corpus()`) e os resultados juntam-se depois. Havia uma
  `com_corpus()` com um `ATTACH`, descrita aqui como se fosse o
  mecanismo — nunca foi chamada, e saiu a 03/09/2026. Está no
  `.gitignore` — 2015-2026 são
  1 987 798 contratos e 2,47 GB — e refaz-se com `--contratos`. O
  endereço do dump muda todas as semanas: resolve-se sempre pela API do
  dados.gov, nunca se guarda.

- **Do anúncio ao contrato liga-se por CHAVE, e o silêncio tem prazo.**
  O dump do IMPIC traz o número do anúncio do DR em `n_anuncio`, no
  mesmo formato do `ref` do radar (`13108/2026`), com índice
  (`ix_ctr_anuncio`): ou é este procedimento ou não aparece. Não
  confundir com os **homólogos** da mesma ficha, que são um palpite por
  termos do título — os dois blocos estão lado a lado e respondem a
  perguntas diferentes. A caixa «Desfecho» (`desfecho_cx()`) só diz
  «ainda sem contrato» passados `DIAS_ATE_CONTRATO` (180): medido a
  04/09/2026, do anúncio à celebração vão 68 dias de mediana e 139 no
  p90, portanto num anúncio de há um mês a ausência não significa nada
  e a caixa em todos eles era ruído. **O desconto agrega por
  procedimento** (`desconto_do_desfecho()`), com as mesmas exclusões do
  gráfico do corpus — é o B04 outra vez, e por linha voltava a mentir.

- **`group_concat` das chaves vem NULL, e o `zip` truncava em
  silêncio.** Os adjudicatários chegam em duas listas paralelas
  separadas por `|` (`ganhou`/`ganhou_ch`), e quando NENHUM tem chave a
  segunda vem `NULL` — `"".split("|")` dá uma lista de **um**, o `zip`
  trunca pelo mais curto, e um agrupamento de cinco aparecia com um
  nome só, sem erro nenhum. Os três sítios que mostram «quem ganhou»
  (`/contratos`, os homólogos e o desfecho) passam desde 04/09/2026 por
  `ganhadores_da_linha()`. No corpus verdadeiro as chaves estão cheias,
  por isso isto **nunca se viu no ecrã** — quem o apanhou foi um teste
  contra um corpus sem a migração, e é por nunca se ver que tinha de
  deixar de depender dela.

- **Os campos de entidade dos contratos são `entid`/`vencid`.** Nos
  anúncios `ent` é a caixa de texto da entidade — nomes iguais com
  sentidos diferentes já estiveram a um passo de se cruzar.

- **As colunas do importador saem de `COLS_CONTRATO`/`COLS_CPV`/
  `COLS_ADJ`**, e `_inserir()` constrói o SQL a partir delas. Nunca
  escrevas `VALUES (?,?,…)` à mão: acrescentar uma coluna com o INSERT
  posicional já partiu o importador duas vezes, a segunda a meio de uma
  importação de sete anos.

- **O intervalo de anos do corpus nunca se escreve à mão.** A página
  "procurar entidade" dizia "só conhece quem já assinou contratos desde
  2020", com o 2020 no código; a 03/09/2026 o corpus passou a começar
  em 2015 e a frase mentiu no mesmo dia. Sai de
  `primeiro_ano_corpus()` (MIN(ano), imediato por `ix_ctr_ano`), como a
  barra do corpus já fazia com o `DISTINCT ano`. E **os zips de 2012,
  2013 e 2014 do dados.gov vêm vazios** — o conjunto anuncia-os, o
  `Content-Length` é zero e o importador traz "0 contratos em 0 s".
  2015 é o mais antigo que existe, e não é preciso voltar a pedi-los.

- **O botão "Actualizar contratos" corre numa thread**, com o estado em
  `corpus_estado` e a página a recarregar-se enquanto isso — um ano são
  ~60 s e um pedido HTTP parado esse tempo parece o painel pendurado. Só
  traz o ano corrente e o anterior: anos fechados não mudam.


---

## Alertas e interesse

Um alerta é um filtro com a marca posta; o interesse é outra coisa.

- **Um `marca_erro()` novo tem de aparecer em `linhas_de_ultimos_erros()`.**
  É a única lista que o ecrã lê (na saúde dos `/indicadores`). O B14 e
  o B15 acrescentaram marcas e não as ligaram lá: um "remote rejected"
  esteve um dia inteiro na base sem existir para ninguém. E a razão de
  um comando git passa por `porque_do_git()` — o "To &lt;url&gt;" que o
  git escreve primeiro comia os 80 caracteres da linha e a razão nunca
  chegava a ver-se.

- **Uma marca de erro tem de se apagar quando a coisa volta a correr
  bem** (`limpa_erro()`, no sucesso). A marca responde a «está avariado
  agora?»; a história fica na série da tabela `erros` (C3), que é para
  isso que existe. Sem isto a marca só crescia: a 4/09/2026 o painel
  mostrava um push recusado a 31/08 depois de dezenas de pushes bons —
  e, por ser anterior ao `porque_do_git()`, ainda no formato velho, com
  o endereço a tapar a razão. Dava a impressão de uma avaria a durar
  uma semana. **Duas não se limpam, de propósito**: a do relógio, que
  passa a cada 60 s e apagaria a marca um minuto depois da avaria, e a
  expiração do token, que não é um erro mas uma data.

- **Um alerta é um filtro com a marca posta.** Geridos em `/alertas`, que
  é também onde se criam e onde se configura o e-mail. `registar_alertas()`
  anota o que corresponde e `enviar_resumo()` manda uma vez por dia — o
  reconhecer e o enviar são separados de propósito, porque a verificação
  corre duas vezes. Ao ligar um alerta, o acervo que já lá está fica
  marcado como `ACERVO`, senão o primeiro resumo trazia tudo. **O
  e-mail vai em duas partes** (02/09/2026): o texto de
  `texto_do_resumo()`, que é também o `AVISOS.txt`, e o HTML de
  `html_do_resumo()` — estilos em linha e tabelas, porque um cliente
  de e-mail não lê o `CSS` do painel; as cores da paleta estão
  copiadas à mão em `_EM_*`. Os dois dizem o mesmo, e há um teste que
  compara as ligações de um e do outro (`TestResumoEmHtml`): dois
  formatos que divergem ao primeiro arranjo foi a razão de haver um só
  até aqui. A pílula do prazo vem de `etiqueta_prazo()` com a janela
  de `dias_urgente()`, como a lista.

- **O interesse não é um alerta nem um filtro: é o recorte permanente
  da lista.** Os CPV que a casa trabalha (`interesse_activo`,
  `interesse_cpv`, `interesse_cpv_excl` no config.json, editados em
  `/alertas/interesse`). Entra por `com_recorte()` como as abas — **e
  nunca por `condicoes()`**, pela mesma razão de sempre: o motor serve
  os alertas e os filtros guardados, e o interesse lá dentro cegava-os
  em silêncio. Quem o aplica é `recorte_da_lista()`, chamado nas
  QUATRO consultas da página (lista, contagem de cada aba, selector
  das plataformas, total do filtro) e no CSV com `ambito` — um número
  que conte com outro recorte abre uma lista diferente da que promete.
  Ligado sem CPV escolhido **não esconde nada** (um ecrã em branco por
  não se ter escolhido código nenhum lê-se como avaria), a lista diz
  sempre que está limitada e quantos ficam de fora, e `?interesse=nao`
  levanta-o. O ecrã é próprio porque a árvore é uma por página (um
  `details.arvore`, um `#filtro-cpv`) e `/alertas` já gasta a sua no
  "Novo filtro".


---

## Triagem, quadro e ficha

O funil da casa, do «por ver» ao «ganho».

- **Os lotes vêm de dois sítios e o quadro não adivinha o terceiro.**
  O anúncio declara os lotes (`anuncios.lotes`, JSON de
  `lotes_do_texto()`); a que fomos e como acabou só o registo da casa
  sabe (`casa.lote` ≥ 1, lote a lote; 0 é o conjunto; NULL é por
  identificar), e `resumo_dos_lotes()` junta os dois, puro, com
  `casa.estado_do_lote()` — que é o `estado_efectivo()`: o Zoho
  **não** decide um lote. A separação no fim (`carta_de_lotes()`) só
  acontece nas colunas de papel `ganho`/`perdido` e só com lotes do
  outro estado no registo; o cartão separado não se arrasta e não tem
  formulários. **Um teste de ficha precisa de um anúncio com `texto`**:
  sem texto a ficha chama `ler_detalhe_de()`, a captura verdadeira
  existe na pasta, o pedido vai ao DR e o que volta escreve por cima
  dos lotes de ensaio — foi assim que o primeiro teste dos lotes
  «não encontrou» o bloco que estava lá.

- **O Zoho é mais actual do que o Excel e menos preciso: tem coluna
  própria, não escreve por cima do `status`.** Medido a 03/09/2026 nas
  148 oportunidades da vista dos Negócios: das 92 que cruzam com o
  registo, **46 dizem «Não fomos» no Excel e «Lost» no Zoho**. O Zoho
  não tem palavra para «não concorremos» — perdeu-se o concurso e nunca
  se foi a ele caem os dois no mesmo sítio. Por isso o que ele diz vive
  em `casa.zoho_fase` / `zoho_montante` / `zoho_como` / `zoho_em`.
  **Uma fonte mais recente não é automaticamente a fonte melhor:
  compara-se campo a campo antes de a deixar mandar.** O
  `zoho_como` guarda a regra que casou a linha porque o cruzamento é por
  semelhança de nome e preço, não por chave — não é uma certeza, e uma
  ligação errada escreve um estado errado. E o que salva estas colunas
  de uma reimportação do Excel é o `_guardar_linha()` usar `ON CONFLICT
  DO UPDATE SET` com as colunas do Excel nomeadas, e não um `REPLACE` da
  linha inteira: um `REPLACE` apagava-as, e ao `lote` e ao
  `porque_sem_ref` também. Há teste
  (`test_o_que_o_zoho_diz_fica_em_coluna_propria_e_sobrevive_a_reimportacao`).
  **Lê-se pelo browser, na sessão dele** — o Zoho não exporta CSV — e a
  aplicação é uma SPA que **não arranca com o separador escondido**:
  fica em «A carregar» para sempre e nem chega a pedir os registos.
  Confirma-se com `document.visibilityState`.

- **O estado que vale é o `estado_efectivo()`, nunca o `casa.status`
  cru.** A regra é dele, 04/09/2026: **o «Não fomos» do Excel prevalece,
  e é o único**; em tudo o resto ganha o Zoho — **excepto numa linha que
  é um lote**, onde manda sempre o Excel. Esta segunda guarda não é um
  detalhe: **as duas fontes contam coisas diferentes.** O Excel tem uma
  linha por lote, o Zoho um negócio por procedimento, e um «Won» do Zoho
  quer dizer «ganhámos pelo menos um lote» — não diz nada sobre este.
  Medido no 1947/2026: três lotes, três linhas (#14 o L1 perdido, #97 o
  L2 ganho, #98 o L3 perdido) e um só negócio no Zoho, «Won» com
  169 344 € contra os 109 065,60 do L1. Sem a guarda, o #14 passava de
  Perdido a Ganho. O `lote = 0` (o conjunto) **não é um lote** e aceita o
  Zoho como qualquer outra linha. **Antes de deixar uma fonte decidir um
  campo, verifica se as duas contam a mesma unidade** — aqui uma contava
  procedimentos e a outra lotes, e o cruzamento por nome não o revela.
  É **derivada**, não
  gravada — o `status` continua a ser o do Excel e o `zoho_fase` o do
  Zoho, cada um intacto, e por isso uma reimportação não desfaz a regra
  e mudar a regra não obriga a reescrever dados. Sobre as 187 linhas,
  16 mudam de estado e 47 ficam protegidas pela excepção. **Quem lê o
  estado do registo chama esta função**; o `estado_pretendido()` já o
  faz, e é por aí que a triagem sai certa. Duas armadilhas medidas ao
  escrevê-la: as chaves do `TRADUCAO_ZOHO` são o que o `_norma()`
  devolve, que **guarda os pontos e os hifens** — escrever
  `"2 3 negotiation"` em vez de `"2.3 - negotiation"` não casa nada e
  cai em silêncio para o estado do Excel; e a linha que vem do Excel
  **não traz nem o `zoho_fase` nem o `lote`**, que têm de ser idos
  buscar à base dentro do `importar()`, senão um `--com-triagem` desfaz
  a regra exactamente no caminho em que a triagem se escreve — e o
  `lote` faz falta lá justamente por ser ele que **trava** o Zoho. Há
  teste para as três.

- **Os lotes lêem-se do anúncio, e a decisão sobre eles já está
  tomada.** O DR escreve «Procedimento com lotes? Sim», «Nº Máx. de
  Lotes Autorizado: N» e um bloco «Lotes:» com «Nº: LOT-000k»,
  descrição e preço base por lote (`lotes_do_texto()`, guardado em
  `anuncios.lotes` como JSON, em vigor pela alteração mais recente como
  os outros campos). O Excel da casa tem uma linha por lote, e o preço
  base dessa linha é o **do lote**: é assim que `casa.lote` se
  atribui (`lote_da_linha()`: preço base igual, senão «L1»/«Lote 2» no
  nome). **Nem sempre — e o valor de `casa.lote` distingue os três
  casos.** Quando o preço da linha é a **soma** de todos os lotes, o
  número do Excel é o total do anúncio e a linha não está dividida por
  lotes: `lote = 0`, «o conjunto» (resposta dele a 03/09/2026 sobre as
  #23 e #26). `NULL` fica a significar só «por identificar», que é o
  que era preciso: as duas coisas eram ambas `NULL` e ficavam
  indistinguíveis, e foi isso que obrigou a perguntar. **Zero é falso
  em Python, de propósito** — quem contava «linhas com lote» com um
  `bool(lote)` continua a não as contar; para as contar usa-se
  `lote == 0`. E há um quarto caso que nenhuma regra apanha: uma linha
  cujo preço não bate com lote nenhum, nem com a soma, nem com o preço
  base de qualquer anúncio da base (as #129 e #147) — aí o número do
  Excel é, provavelmente, o **valor da nossa proposta** e não um preço
  base, e a linha fica `NULL` até ele dizer o lote à mão. Não se move o
  número para `valor_proposta` com base num «provavelmente». Decisão do
  Afonso a 02/09/2026 para quando o registo chegar
  ao ecrã: **um cartão por anúncio**; um anúncio com lotes diz a que
  lotes se foi e se se foi a todos; e no fim, em Ganho ou Perdido, **os
  cartões separam-se por lote**, cada um com o seu resultado. Ainda não
  está implementado no quadro — nada muda no front antes de o registo
  estar validado.

- **Arrastar no quadro NÃO recarrega: o servidor devolve o cartão.**
  O cartão que se arrasta é o MESMO nó do DOM, e quem decide o que ele
  mostra é o servidor, pela fase: largá-lo no "Submetido" mudava-o de
  coluna e mais nada — sem o campo do preço proposto, com o preço base
  onde já devia estar o proposto, e com a soma no cabeçalho das duas
  colunas errada. A primeira resposta (01/09/2026) foi um
  `location.reload()` no caminho do sucesso; a `docs/historico/UX-Auditoria.md`
  (02/09/2026) classificou-a como dívida, e no mesmo dia `/quadro/mover`
  passou a devolver `{carta, contas}` — o HTML do cartão redesenhado
  (`cartao()`) e a `conta_da_coluna()` das duas colunas tocadas — e o
  `drop` troca só isso (`carta.replaceWith`, `ligarCarta` no nó novo,
  `outerHTML` das contagens). O `reload()` fica só nos ramos do erro,
  para repor o ecrã pelo que a base diz. Se acrescentares ao cartão
  algo que dependa da fase, é em `cartao()` que entra, e a resposta do
  mover já o traz.

- **Triar avisa e deixa desfazer.** `mudar_estado()` volta com
  `?aviso=«título» marcado como interessa.&desfazer=/estado/<ref>/<estado
  anterior>` e `envolver()` desenha o `desfazer` como botão POST dentro
  do `.flash` — só caminhos `/estado/`, nunca um endereço vindo da query
  string. Se o estado anterior era um abandono com motivo, o motivo vai
  em `?motivo=` na acção do desfazer (por isso `mudar_estado()` lê
  `request.values` e não `request.form`); um abandono antigo sem motivo
  não oferece desfazer, porque o servidor o recusaria.
  `_volta_com_aviso()` tira o `aviso`/`desfazer` anteriores da query
  string antes de pôr os novos. Repetir o mesmo estado avisa sem
  desfazer.

- **A partir do "Submetido" o prazo é uma data, não um alarme.** Em
  `cartao()`, nas `FASES_COM_PROPOSTO` a pílula é `prazo DD/MM/AAAA`
  sem cor: a proposta foi entregue, e o vermelho de «prazo expirado»
  estava em 4 dos 9 cartões do quadro a puxar o olho para nada. Antes do
  Submetido continua a ser `etiqueta_prazo()`.

- **Abandonar exige motivo, de âmbito fechado** (`MOTIVOS_ABANDONO`,
  decisão do Afonso a 01/09/2026), e pergunta-se **num pop-up**, não
  num selector ao lado do botão (decisão dele no mesmo dia): vinte
  linhas na lista eram vinte perguntas antes de alguém as fazer. A
  caixa é UMA por página (`caixa_de_abandono()`, um `<dialog>`
  partilhado); o botão continua a ser submit de um `<form>` e o JS
  intercepta — **sem JS o POST segue** e a recusa do servidor explica
  porquê, em vez de o botão ficar morto. O `required` dos rádios é
  conveniência do browser; a guarda é o `mudar_estado()`, que recusa o
  que não estiver na lista. Sair de abandonado limpa o `motivo` — um
  motivo pendurado num anúncio que voltou ao por ver é uma mentira à
  espera de ser lida. Os que caem nos abandonados por terem expirado
  não têm motivo, e não se lhes inventa um. Texto livre não: ao fim de
  um mês dá cinquenta maneiras de escrever "preço" e nenhuma conta.

- **As fases do quadro são SEIS e fixas, e o que manda é o `papel`.**
  Decisão do Afonso a 01/09/2026: o quadro é o funil da casa, não um
  kanban em branco — criar e apagar fases saiu (UI e rotas). Renomear
  fica. **O cabeçalho da coluna diz o que ela pede** (`PEDIDO_DA_FASE`,
  e há teste a obrigar as duas listas a concordar): o campo só aparece
  quando há lá um cartão, e com tudo em "Por analisar" — o caso normal
  — não havia nada no ecrã a dizer que o "Submetido" pede o preço
  proposto; a funcionalidade parecia não existir, e foi o que o Afonso
  viu. Cada fase tem `fases.papel` (`FASES_DE_ORIGEM`), e é por ele —
  **nunca pelo nome** — que o cartão decide o que pede
  (`_campos_da_fase()`): renomear a coluna não pode calar o campo. A
  migração `atribuir_papeis()` corre a cada arranque, reconhece os
  nomes que já existem por pedaço (`PISTAS_DE_PAPEL`: a base do Afonso
  tem "Relatorio Preleminar" escrito assim) e cria os que faltarem, uma
  vez só.

- **A partir do "Submetido" o preço é o proposto** (`FASES_COM_PROPOSTO`),
  no cartão e na soma da coluna: somar preços base numa coluna de
  submetidos dá o tecto da entidade e não o que está em jogo, com o
  mesmo ar de número certo. Sem proposto preenchido mostra-se o base
  **escrito como "base"**. E o proposto grava-se pelo `_texto_do_preco()`
  ("118.500,00 EUR"), **não pelo `euros()`**: esse põe espaço nos
  milhares e o `euros_do_texto()` lê "118" de "118 500 €".


---

## O registo da casa

O registo da casa, em `casa.py`: desde 8/09/2026 pelo modelo do radar;
o leitor do Excel antigo fica lá, sem comando.

- **O modelo é do radar, e a chave é a referência do DR.** Decisão do
  Afonso a 8/09/2026: em vez de adivinhar a que anúncio pertence uma
  linha do Excel antigo (nome, entidade, preço, um pedido ao DR para
  desempatar), o `.xlsx` sai de `casa.escrever_modelo()` com a coluna
  «Referência do anúncio», e uma linha sem anúncio é um **erro do
  ensaio**, não um palpite. `ler_modelo()` só normaliza (`ref_limpa()`
  aceita `1947/2026`, `1947-2026`, com espaços); `ensaio_modelo()` cruza
  com a base sem gravar; `aplicar_modelo()` grava em `casa` com
  `folha='modelo'` e chama o `aplicar()` de sempre com a **melhor** linha
  do anúncio (ganho › submetido › perdido › não fomos) — um lote ganho
  põe o cartão no Ganho e a separação do fim mostra os perdidos. O
  ficheiro carregado guarda-se em `importacoes/` e a confirmação lê-o
  outra vez pelo nome, **só o nome** (`_nome_de_importacao()` recusa
  caminhos): um `ficheiro=../radar.db` não passa. Uma razão já canónica
  («Falta de CV's») fica como está no `estado_pretendido()`: o
  `MAPA_RAZAO` é para as variantes do Excel antigo, e a primeira versão
  perdia o motivo por o passar pelo mapa. `--importar-excel` e
  `--casa-ligar` saíram; `--casa-desfazer` (repor a triagem de uma
  cópia) ficou, porque serve para qualquer importação.

- **O registo da casa vive em `casa.py`** — o primeiro módulo fora do
  `radar.py` (02/09/2026), e a regra para os próximos: o módulo novo
  nasce em ficheiro próprio, importa o radar **dentro das funções**
  (o radar importa-o no topo, para as rotas), e o `radar.py` só ganha
  as rotas, o bloco da ficha e a linha do CLI. É o Excel de análise de
  concursos do Afonso (`Analise_Concursos_Publicos.xlsm`: 187
  concursos vindos de uma lista do SharePoint, completados numa folha
  por concurso e consolidados por macros VBA). Lê-se **pelas mesmas
  âncoras que as macros usam** («TABELA B», «TABELA C», cabeçalhos
  PERFIL e CONCORRENTE): as folhas `C_` são os registos, as tabelas
  planas são derivadas e podem estar desactualizadas — nunca se lêem
  essas. O id estável é a coluna K do ÍNDICE (Z1 da folha). Cada linha
  liga-se ao **procedimento** (o anúncio original; uma alteração
  resolve-se para a raiz) por três sinais, por esta ordem: pontuação
  do nome no título (**contenção**, não Jaccard — o nome do Excel é
  uma abreviatura do título do DR), o valor do 1.º lugar cruzado com o
  `preco_contratual` do BASE (que traz o `n_anuncio`, isto é, o ref),
  e a leitura do detalhe dos candidatos ambíguos para o preço base
  desempatar e as republicações caírem. **Por agora só se guarda e
  liga: a triagem NÃO se aplica** (decisão dele a 02/09/2026 — nada
  muda no front antes de o registo estar validado, e os lotes, várias
  linhas do Excel no mesmo anúncio, ainda não têm solução). A página
  `/casa` e o bloco da ficha que chegaram a existir saíram nesse dia;
  há teste a guardá-lo (`test_o_front_nao_mudou`). Quando se aplicar
  (`--com-triagem`, `triagem=True`): só com estado inequívoco (Não
  fomos → descartado com o motivo mapeado; Submetido/Perdido/Ganho →
  interessa na fase com esse papel, com preço proposto, lugar e três
  primeiros), «Cancelado» e «TBD» ficam só no registo, **uma decisão
  humana feita no radar nunca é esmagada** (conflito registado uma vez
  no histórico), e os motivos «Fora do âmbito» e «Prazo curto» entram
  então em `MOTIVOS_ABANDONO` (hoje só em `casa.MAPA_RAZAO`).
  Entidades espanholas não entram (`FORA_DO_PAIS`, decisão dele).
  `--ensaio` calcula e não grava; `--casa-ligar ID REF` liga à mão
  (`ID nenhum "razão"` diz que não há anúncio no DR — consultas
  prévias, ajustes directos, consultas preliminares, anteriores à base
  —, `ID ? "razão"` só anota), e uma ligação ou um «nenhum» manual
  sobrevivem às importações seguintes;
  `--casa-desfazer CÓPIA` repõe a triagem de uma cópia anterior (foi o
  que desfez a aplicação de 02/09/2026).


---

## A base, as migrações e o disco

SQLite, cópias, e a pen que manda nos números.

- **Há cópia diária da base de trabalho** em `copias/`, sete guardadas,
  feita antes da recolha com `VACUUM INTO` (a quente, e sai compactada).
  Copiar o ficheiro com o `.wal` ao lado dava uma cópia truncada. Só a
  de trabalho: o corpus e os documentos refazem-se, a triagem não.

- **Uma migração do corpus sem índice que a sirva é o arranque do
  painel.** O `iniciar_corpus()` corre a cada arranque, e um
  `WHERE <coluna> IS NULL` sem índice varre o corpus todo — 1,65 GB
  quando isto se mediu, 2,47 GB desde 03/09/2026 — mesmo para
  encontrar zero linhas. Foi o que o `n_adj` fez até 01/09/2026:
  **38,9 s a frio** contra 0,00 s das outras três migrações da mesma
  função, que têm índice. Regra: uma migração idempotente ou tem índice
  que responda ao `IS NULL`, ou tem **marca no `corpus_estado`** (como
  o `html_desescapado` e agora o `n_adj_cheio`) — e a marca só é segura
  quando o importador enche sempre a coluna, o que se garante pelo
  `COLS_CONTRATO`. E **mede-se a frio**: a quente o mesmo varrimento
  dava 0,8 s, que foi o que escondeu isto durante meses.

- **Isto corre de uma pen, e a pen manda nos números.** O `D:` é um
  Samsung Flash Drive por USB, não o SSD interno: 8,7 ms para abrir um
  ficheiro pequeno a frio, e ~42 MB/s efectivos numa varredura de
  páginas de 4 KB (408 MB/s em sequencial puro). Daí os 216 dos 459
  módulos que vêm de `libs/` como ficheiros soltos custarem segundos
  no arranque, e daí uma varredura do corpus (2,47 GB) não ser um
  encolher de ombros. Antes de culpar o código por lentidão, confirma em que
  disco ele está (`Get-Partition -DriveLetter D | Get-Disk`).

- **A tabela `anuncios` é LARGA, e um varrimento dela não custa
  linhas — custa megabytes.** A 4/09/2026 são 438 MB, dos quais o
  `texto` do anúncio sozinho são 377. Um `SCAN anuncios` seco arrasta
  isso tudo do disco para responder a um `COUNT(*)`. Enquanto só 9%
  tinham detalhe lido não se via; no dia em que o `--detalhes tudo`
  acabou (66 498 de 66 498), a página inicial passou a fazer **nove
  varrimentos por pedido** e foi de ~0,2 s para **1,57 s a quente** —
  na pen a frio, muito pior. Regra: **uma consulta de contagem ou de
  agrupamento sobre os anúncios tem de ter um índice que a COBRE.**
  Existem para isso o `ix_anuncios_lista` (estado + a ordem da
  primeira página), o `ix_anuncios_triagem` (as cinco colunas das
  abas), o `ix_anuncios_detalhe`, o `ix_anuncios_plataforma`, o
  `ix_anuncios_estado_cpv` e o `ix_anuncios_acervo`. Uma coluna que
  falte ao índice tira-lhe o «COVERING» e volta tudo atrás, em
  silêncio: o `TestPaginasNaoVarremATabelaLarga` corre o
  `EXPLAIN QUERY PLAN` das consultas que as rotas disparam de facto e
  recusa qualquer `SCAN anuncios` que não seja por índice de cobertura.

  **E aconteceu outra vez a 05/09/2026, de duas maneiras que valem por
  si.** O mapa das plataformas da lista era servido pelo
  `ix_anuncios_detalhe(detalhe_lido, plataforma)`, e o comentário dele
  dizia «não filtram por estado nenhum» — mas a consulta passou a
  filtrar por `estado != 'alteracao'` e pelo recorte, e o índice deixou
  de a cobrir. Com 66 mil anúncios não se via; com 209 177 e a
  `anuncios` em 843 MB eram **0,45 s numa página**. O
  `ix_anuncios_acervo(detalhe_lido, estado, plataforma, cpv)` põe-nos
  em **0,037 s**, constrói-se em 1 s e não acrescenta nada de medível
  ao ficheiro. **Um comentário que descreve a consulta que o índice
  serve é uma afirmação que envelhece**: quando alguém acrescenta uma
  coluna ao WHERE, o comentário passa a mentir e o índice a não cobrir,
  os dois em silêncio.

  A segunda: **o teste não apanhou isto, e o plano dizia porquê.** Ele
  recusa `SCAN anuncios` sem cobertura, e este plano era um
  **`SEARCH`** — `SEARCH anuncios USING INDEX ix_anuncios_detalhe`. Um
  SEARCH que acerta em duzentas mil linhas custa o mesmo que um SCAN, e
  a única diferença no plano é a palavra. Não se pode recusar todo o
  SEARCH sem cobertura (o `WHERE ref=?` é um e é o correcto), por isso
  o que se acrescentou foi um teste **à consulta**, não à rota, a exigir
  a palavra COVERING —
  `test_o_mapa_das_plataformas_sai_de_um_indice_de_cobertura`. Os índices
  criam-se no `iniciar_db()` e custam **~1 minuto no primeiro
  arranque** depois de os acrescentar — é o preço de os construir na
  pen, uma vez.

- **O mesmo vale para o corpus, mas por CPU e não por disco.** O
  `GROUP BY tipo_procedimento` sobre 1,99 milhões custa 0,17 s **mesmo
  com o índice a cobri-lo** — agrupar texto é trabalho que o índice
  não evita, só encurta. Uma lista que só muda quando a importação
  semanal corre guarda-se em memória, com a **identidade do ficheiro**
  (data e tamanho, do `.db` e do `-wal`) como chave, não com um prazo
  de validade: um prazo mostrava números velhos exactamente depois de
  uma importação, que é a única coisa que os muda. É o que o
  `tipos_de_procedimento()` faz. E o `ha_corpus()` guarda-se **por
  pedido**, no `g` do Flask: a barra, a árvore e o corpo chamavam-no
  quatro ou cinco vezes na mesma página.

- **Migrações idempotentes.** Colunas novas acrescentam-se ao ciclo de
  `ALTER TABLE` em `iniciar_db()`, que corre sempre e não faz nada se já
  existirem. Não escrevas migrações que corram uma vez só.

- **OneDrive.** A pasta está dentro do OneDrive; a sincronização pode
  bloquear o `radar.db` a meio de uma escrita. Se aparecerem erros de base
  bloqueada, é isso.


- **O Windows deixa a pasta «só de leitura», e o Linux acredita.** A
  8/09/2026 a mesma pasta NTFS, aberta em Ubuntu, tinha 138 pastas e
  450 ficheiros sem o bit de escrita — o `.git` incluído — e o `python3
  -m venv` morria com *Permission denied* sem dizer em quê. É o atributo
  «read-only» do NTFS a passar por modo POSIX. Resolve-se com `chmod -R
  u+w .` uma vez; e o `core.filemode` fica a `false`, por isso o exec
  bit dos `.sh` só entra no git com `git update-index --chmod=+x`.
  Também por isso existe o `.gitattributes`: o mesmo disco visto do
  Windows tinha CRLF e o git em Linux via 27 ficheiros alterados sem
  uma letra mudada — `git diff --ignore-cr-at-eol` antes de acreditar.

---

## Trabalhos de fundo e arranque

Nada espera dentro do pedido do browser.

- **`with liga() as c` fecha a ligação; sem isso o painel morre em
  silêncio ao fim de umas horas.** (8/09/2026, à noite.) O `with` do
  `sqlite3` de origem só faz commit: a ligação fica aberta até o
  garbage collector a apanhar, e com ciclos (cursores, Rows) não a
  apanha. Medido no painel a servir `radargov.pt`: 501 ligações ao
  `radar.db` abertas, 1024 descritores — o limite do processo —, o
  `accept()` a falhar em ciclo e o processo a 100% de CPU sem atender
  ninguém durante quase quatro horas, sem uma linha no journal. Os
  sinais: `ss -ltnp` com a fila de espera cheia na 8765, `ls
  /proc/PID/fd | wc -l` a bater no `Max open files` do
  `/proc/PID/limits`, e a thread principal a gastar o CPU. A cura é a
  classe `Ligacao` (`__exit__` fecha), usada por `liga()` e
  `liga_corpus()`; quem usar a ligação depois do bloco tem um
  `ProgrammingError`, alto. O `radar-painel.service` leva
  `LimitNOFILE=16384` por cima. `TestLigacaoFechaAoSair` guarda-o, e
  a medida a fazer depois de qualquer mudança nas ligações é a dos
  descritores: `ls /proc/PID/fd | wc -l` antes e depois de cem pedidos
  tem de dar o mesmo (deu 4 e 4).

- **Os três trabalhos longos correm todos fora do pedido.** "Verificar
  agora" é thread com trinco (`comecar_verificacao()`, com um `passo`
  que a barra lateral mostra), "Actualizar contratos" é thread com
  estado na base, e as peças e a leitura pelo modelo são filas
  (`pedir_documentos()`, `pedir_analise()`). Nenhum deles espera dentro
  do pedido do browser: já esteve assim e eram minutos de página em
  branco. Em fundo não há cookie para ler — passa o `quem` ao
  `registar()` em vez de contar com o `quem_sou()`.

- **O `relogio()` entra pela mesma porta do botão.** Um slot falhado
  chama `comecar_verificacao(slot=(dia, hora))`, não o `verificar()`
  directo — só assim há trinco (senão o relógio apanhava um clique a
  meio e punha duas verificações na mesma base) e há `passo` (senão o
  arranque do painel ficava ~5 minutos lento, com a cópia, o push da
  triagem e a recolha toda, sem nada no ecrã a dizer porquê). O slot
  só se marca como corrido no fim e se correu bem; se o trinco
  recusar, tenta-se no minuto seguinte. E o botão à mão **não** marca
  slot: um clique às 15h não faz a verificação das 17h por feita.

- **O browser abre-se depois de a porta atender**
  (`abrir_no_browser()`, em thread, com `porta_atende()`). O
  `webbrowser.open()` era chamado antes do `app.run()` e chegava lá
  ~1 s antes de haver servidor. Atenção ao medir isto no Windows: uma
  ligação a uma porta com bind e **sem** listen não é recusada, bloqueia
  até ao timeout — um teste que ponha um servidor a nascer a meio é
  intermitente, e por isso a sonda troca-se por uma falsa nos testes.

- **O endereço é `127.0.0.1:8765`, nunca `localhost:8765`** — e é a
  mesma armadilha do Windows, do lado do cliente. O `localhost` aqui
  resolve para **`::1` antes** de `127.0.0.1`, o painel só atende em
  IPv4, e a ligação ao IPv6 não é recusada: bloqueia. Medido a
  04/09/2026, no browser, a mesma página: **208 ms por pedido por
  `localhost` contra 37 ms por `127.0.0.1`** — e por curl, 0,22 s só
  para abrir a ligação, contra 0,0008 s. É um imposto fixo em cada
  clique, e não se vê num perfil do servidor, porque é gasto antes de
  o pedido lá chegar. O `radar.LOCAL` é a constante que escreve o
  endereço em todo o lado (o arranque, o browser que se abre, os
  links dos e-mails, o rodapé), e há um teste que recusa a palavra
  `localhost` no e-mail. **Quem tiver `localhost:8765` nos favoritos
  continua a pagar** — troque-se o favorito. A alternativa era pôr um
  segundo servidor a atender em `::1`; não se fez, para não ter dois
  servidores no mesmo processo por causa de um endereço.

- **Fora do Windows, o aviso das tarefas em falta dizia «nada em
  falta».** `tarefas_em_falta()` devolvia vazio em qualquer sistema
  que não fosse `nt` — «não há o que avisar» — e era exactamente o modo
  de falha que o aviso existe para apanhar: parecer vivo sem recolher.
  Desde 8/09/2026 em Linux lê `systemctl --user list-timers --all` e
  procura os nomes de `TAREFAS_LINUX` (`radar-09h.timer`,
  `radar-17h.timer`); o `agendar.sh` é quem os cria, e **os nomes têm
  de bater nos dois sítios**. A listagem é injectável
  (`tarefas_em_falta(listar, sistema)`) e os testes cobrem os dois
  sistemas, o sistema desconhecido (devolve vazio sem chamar nada) e o
  comando a rebentar (vazio: não se inventa aviso). O painel como
  serviço arranca com `--sem-browser`, senão cada reinício abria um
  separador na sessão gráfica — e arranca o `radar.py` directamente,
  não o `iniciar.sh`: este pergunta ao systemd se o serviço está
  activo, e de dentro do serviço a resposta é sim; saía em 44 ms com
  «já está a correr» e o painel nunca subia.


---

## Contas e a porta

O login de 8/09/2026 (etapa 1 do `docs/historico/ONLINE.md`): o
`contas.py` tem as tabelas e a criptografia, a «porta» do `radar.py`
(`porta_de_entrada()`, logo a seguir ao `app`) tem o que é do pedido.
`TestContas` cobre tudo isto.

- **O túnel liga-se ao painel a partir de 127.0.0.1.** O `cloudflared`
  corre neste computador e fala com o Flask por loopback: só pelo IP,
  **todos os visitantes do túnel eram locais** e entravam pelo
  `acesso_livre_local` sem login. `pedido_e_local()` conta também o
  que o túnel acrescenta — o `Host` público e os cabeçalhos de proxy
  (`X-Forwarded-For`, `Cf-Connecting-Ip`, `X-Real-Ip`) — e qualquer um
  chega para o pedido deixar de ser local. O `ProxyFix` (um salto) faz
  o `remote_addr` ser o IP verdadeiro e o cookie levar `Secure` por
  trás de HTTPS. Um proxy novo à frente do painel que não ponha nenhum
  destes cabeçalhos reabre o buraco: o teste
  `test_acesso_livre_so_de_127001_e_sem_tunel_a_meio` é o que o apanha.

- **O CSRF entra pelo `com_csrf()`, não formulário a formulário.** São
  26 `<form method=post>` e há-de haver mais; um helper a chamar em
  cada um era um formulário novo esquecido e uma acção a dar 403. O
  `envolver()` passa a página inteira por uma substituição que mete o
  campo escondido em todos, e o `test_todas_as_rotas_post_recusam_sem_
  token` percorre o `app.url_map` para a outra metade. O que não passa
  pelo `envolver()` tem de tratar de si: o `fetch` do `/quadro/mover`
  manda o token no cabeçalho `X-CSRF`, lido da `<meta name="csrf">`.
  **No acesso livre local não há token** (não há sessão de que o
  derivar): a guarda é o `Origin`/`Referer`, e `localhost`, `127.0.0.1`
  e `::1` contam como a mesma casa — o browser pode ter um nos
  favoritos e mandar o outro no Referer.

- **Um teste que varre as rotas POST com o token válido executa-as.**
  A primeira versão do teste do CSRF chamava todas as rotas com token
  para provar que passavam: o `/alertas/email` gravou o **`config.json`
  verdadeiro** com os valores de origem (e-mail apagado, interesse
  desligado, `triagem_no_git` ligado), e o `/verificar` foi à rede. A
  metade «com token passa» só se testa em rotas inofensivas, e o
  `TestContas` aponta `radar.CONFIG` para a pasta temporária. Um
  teste que usa o cliente Flask com uma base temporária **não está
  isolado da configuração** só por isso.

- **A porta corre em todos os pedidos e fecha a ligação à mão.** O
  `with liga() as c` do SQLite só faz commit, não fecha; na porta era
  uma ligação por pedido à espera do garbage collector, e a bateria
  passou de 327 para 719 avisos de «unclosed database». Um `before_
  request` novo que abra a base fecha-a num `finally`. E tolera uma
  base sem as tabelas das contas (`sqlite3.OperationalError`): os
  testes que usam o cliente sem base própria batem no `radar.db`
  verdadeiro tal como está, e isso é «sem sessão», não um 500 em
  todas as páginas.

- **`acesso_livre_local` a `true` com o painel a ouvir fora do
  loopback é a porta aberta ao mundo.** `arranque_permitido()`
  recusa-se a arrancar nessa combinação; hoje `ENDERECO` é uma
  constante em `127.0.0.1` e a guarda parece supérflua — é para o dia
  em que deixar de ser. Recuperar a palavra-passe é por consola
  (`--palavra-passe EMAIL`, o mesmo `criar_utilizador()` que troca o
  hash se o e-mail existir), não por e-mail, de propósito: é um fluxo
  a menos exposto.

## A interface

As regras de desenho da casa. As medidas estão em `docs/historico/UX-Auditoria.md`.

- **As migalhas são `migalhas_de(vista, folha)`.** Cada página parte do
  item da navegação em que vive (`NAV`/`ITEM_DA_PAGINA`); as vistas
  agrupadas dizem o caminho inteiro ("Em curso › Quadro", "Mercado ›
  Contratos") e as fichas penduram uma folha por baixo — a do anúncio
  em Anúncios. E o "Verificar agora" aparece **só na lista dos
  anúncios** (`PAGINAS_COM_VERIFICAR`, decisão 11.8-A): os novos
  aterram no por ver.

- **Abaixo de 900 px a barra é uma linha em cima, e o que é largo rola
  dentro de si — nunca a página.** (8/09/2026.) O bloco `@media
  (max-width:900px)` no fim do `CSS` é o único sítio: `.app` em coluna,
  `aside` em linha com a navegação numa segunda linha inteira a rolar
  de lado (espremida ao lado da marca, empilhava-se em coluna),
  `.item` e `.essencial .par` a uma coluna, `.abas` e `.ficha-indice`
  com `overflow-x:auto`. A medida que apanha o resto é
  `document.documentElement.scrollWidth` a 375 px: tem de ser 375 em
  todas as páginas. Foi assim que apareceram a escada de preços da
  ficha (`.escada`, cinco caixas com `flex:1` sem `min-width:0`) e as
  barras do funil dos indicadores (`.barras .col`), que ninguém via no
  ecrã porque o corte era de 27 e 2 px. Um bloco novo com `display:flex`
  e filhos de largura fixa entra nessa lista; `TestEcraEstreito` guarda
  as regras que existem, não a medida — a medida faz-se no browser.

- **Configurações é uma página, e Alertas deixou de ser um item da
  barra** (8/09/2026, etapa 2 do `ONLINE.md`; reverte a decisão 11.6-A
  do esqueleto). `NAV` tem três itens; `/alertas` e
  `/alertas/interesse` redireccionam com a query string atrás, e os
  `POST` antigos (`/alertas/criar`, `/alertas/email`, …) continuam a
  existir e voltam para `/configuracoes/alertas` — mudar-lhes o
  destino sem mudar o `redirect` deixa o aviso a aparecer numa página
  vazia. Cada secção grava por `gravar_config_registado()`, que
  **recusa chaves que pareçam segredos** (`senha`, `api_key`, `token`,
  …): as chaves e a palavra-passe do e-mail escrevem-se nos ficheiros
  de sempre, os que `ler_chave()` lê, e o campo do ecrã fica vazio de
  propósito. Por variável de ambiente, o ecrã di-lo e não deixa
  editar. A validação é por limites e não só `int()`: um zero na
  janela do detalhe calava a recolha em silêncio. E `registar()` fora
  do `with liga()` de quem grava: lá dentro a transacção está aberta e
  a segunda ligação fica presa («database is locked», apanhado pelo
  teste da conta). `TestConfiguracoes` aponta `radar.BASE_DIR` e
  `radar.CONFIG` para a pasta temporária — as chaves e as capturas
  escrevem-se em `BASE_DIR`, e sem isso o teste gravava na pasta real.

- **Os três blocos de filtro da lista vivem dentro de um `<details
  class='painel-filtros'>`, recolhido por omissão** (8/09/2026, os
  P2/P3 da UX-Auditoria que o Afonso aprovou). Abre sozinho com filtro
  aplicado (`filtro_em_uso != "estado=" + aba`) e o JS lembra o
  estado em `localStorage`. O JS da árvore continua a procurar
  `details.arvore` no documento inteiro, por isso aninhá-la não a
  parte — mas um `id` novo lá dentro tem de continuar único na página.
  Na mesma sessão entraram o **teclado da lista** (`j k i a Enter`,
  no `LISTA_JS`: `requestSubmit()` nos formulários da linha focada,
  para o pop-up do abandono e a memória da posição do scroll
  continuarem a disparar; nada dispara com o foco num campo) e a
  **frase dos campos em falta** do essencial
  (`frase_dos_campos_em_falta()`, agrupada pela razão). A mensagem da
  última verificação passou a levar o ponto como carácter: era
  `&middot;` e a barra lateral escapa-a — saía escrito.

- **Um alvo de texto tem 24px de altura, com a letra que tiver.**
  «voltar a por ver» tinha 85×11, «Pôr por ver» 63×12, «mudar» 34×13:
  `background:none;border:0;padding:0` num botão de 11px faz da área
  de clique o próprio texto. O padrão é `padding` até aos 24px com
  margem negativa vertical (a linha não cresce) e `min-height:24px;
  box-sizing:border-box`; `TestAlvosDeTextoA24px` percorre os
  selectores (`button.tirar`, `.carta-pe a`, `.bt-leve`, `.sou button`,
  `button.etq-x`, `.alerta .apagar`) — um botão de texto novo entra
  nessa lista. Ligações dentro de frases não contam: têm a altura da
  linha, e a WCAG exclui-as.

- **A folha do Google Fonts carrega sem bloquear a pintura**
  (`media="print" onload="this.media='all'"`, com a cópia normal em
  `<noscript>`). Como `<link rel=stylesheet>` simples era render-blocking:
  12,6 s de página branca sem saída para o domínio, com o servidor a
  responder em 16 ms. Sem rede, a aplicação fica legível **antes** do
  timeout, com a letra de reserva.

- **Toda a truncagem visível passa por `corta()`**, que põe reticências.
  Um `[:190]` cru corta a meio de palavra e lê-se como dado estragado.
  Onde quem corta é o CSS (uma pílula do calendário, um nome num
  gráfico), a regra é a mesma: `text-overflow:ellipsis` e não
  `overflow:hidden` sozinho — "Por analis" também se lê como avaria.

- **Os campos longos do essencial ganham forma, não texto novo.**
  `desenha_valor()` reconhece o que o valor já é — blocos com pares
  «Chave: valor» viram cartões de perfil, linhas com travessão viram
  lista, «1. Nome» + detalhe vira lista numerada — e o resto sai como
  sempre saiu. **A guarda que interessa é a última:** uma frase com
  dois pontos a meio não é um par (senão «Presencial, nas instalações
  do Parque de Saúde de Lisboa» virava tabela); por isso o
  `RX_PAR_PERFIL` exige chave curta. Há teste por forma
  (`TestDesenhaValor`).

- **A largura a mais dá mais informação, não linhas mais compridas.**
  O `.larg` tem tecto (1560px) e a folga lateral acompanha o ecrã
  (`clamp`); as grelhas ganham colunas com `auto-fit`/`auto-fill` em vez
  de terem um número fixo; e o texto corrido tem tecto próprio em `ch`
  — medido, fica em 643px de 1366 a 2560, enquanto as tabelas da mesma
  página vão de 1112 a 1522. Antes disto, um monitor de 1920 tinha 530px
  vazios e um de 2560 tinha 1170.

- **Cor de texto e cor de decoração são escalas diferentes.** O texto
  usa `--t1`..`--t6`; setas, molduras tracejadas e separadores usam
  `--traco` ou `--linha`, e nunca um `--t*`. Foi a confusão entre os
  dois que fez a escala antiga descer a 2,5:1 em texto de 10px. **E a
  escala do texto tem dois patamares, medidos pelo próprio CSS**
  (`TestContrasteNosFundosReais`, 02/09/2026): `--t1`..`--t4` passam AA
  (4,5:1) sobre `--papel`, `--linha2` e `--creme`; `--t5` e `--t6` só
  passam sobre branco e `--creme` — sobre `--papel` dão 4,43 e 4,30, e
  sobre `--linha2`, que é o fundo das colunas do quadro, 4,35 e 4,22.
  Os `.coluna-pede` estiveram em `--t5` um dia por isso. Um contraste
  marginal **não se vê, mede-se**: a passagem de 31/08/2026 deixou seis
  falhas entre 4,1 e 4,43 que nenhuma revisão a olho tinha apanhado, e
  a de 02/09/2026 apanhou três dentro da coluna do quadro porque só se
  tinha medido sobre o papel. Mede sobre todos os fundos que existem.

- **Os dois CSV escrevem números com `numero_csv()` e chamam-se pelo
  `nome_csv()`.** Vírgula decimal, sem símbolo e sem separador de
  milhares, que é o que o Excel português come; e data no nome, porque
  três `concursos.csv` na pasta das descargas não se distinguem.

- **`ent` é "Entidade que publica" e `adj` é "Entidade que comprou".**
  Os rótulos das caixas e o `_NOMES_FILTRO` dizem o mesmo. Com os dois a
  chamarem-se "entidade", o aviso do parcial saía "entidade Município de
  Lisboa — aqui não se aplica: entidade".


---

## Convenções

- **Uma utilidade pura vive na banda `comum`, não onde foi precisa
  primeiro.** Formatar, validar e contar — nada que toque na base ou
  escreva HTML. A 03/09/2026 o `data_pt()` vivia na banda da ficha do
  anúncio e era chamado por seis funções de quatro bandas; o
  `dias_restantes()` vivia no quadro e era usado pelo resumo por
  e-mail; o `dias_urgente()` vivia na banda do procedimento na
  plataforma. Medido no grafo de chamadas: **era isto que prendia as
  fontes, o mercado e a rotina ao painel** — três dos seis ciclos entre
  as fatias do ficheiro eram formatadores, não painel. Mudaram-se doze
  para `comum` e os três ciclos caíram. Escrever um formatador na banda
  em que se estava a trabalhar é como isto volta.

- **Convenção de acentos:** comentários e docstrings do `radar.py` em ASCII,
  sem acentos; texto visível ao utilizador (HTML, prints, prompts) com
  acentos. Segue o que já lá está.

