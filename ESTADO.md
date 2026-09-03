# Estado do projecto, para quem pegar nisto a seguir

Última actualização: 3 de setembro de 2026 (a retirada do OCR e da vigilância das peças).

## O que isto é

Aplicação local em Python que vigia os anúncios de contratação pública
publicados no Diário da República, série II, parte L. Guarda tudo numa
base SQLite e mostra num painel web local, em `http://localhost:8765`.
Verifica sozinha às 09:00 e às 17:00, por tarefas do Windows.

Substitui a Armilar, produto da Vortal que a empresa paga a 200 euros
por mês, com má experiência de uso e falhas de ingestão. Corre no PC do
Afonso e não depende de nada da empresa.

Princípio de desenho, decidido depois de uma primeira versão que
filtrava por pontuação: **não se filtra nada à entrada**. Entra tudo o
que a parte L publicar, ordenado da data mais recente para a mais
antiga, e a triagem faz-se no painel, por CPV, palavras, datas e estado.

## Como está a correr

Funciona. A base tem **66 387 anúncios, dois anos deles**
(28/08/2024–03/09/2026) — **65 511 procedimentos**, porque 876 são
republicações («Alteração do Anúncio de procedimento n.º …») ligadas
ao original desde 01/09/2026 e fora de todas as listas: o grosso trazido pelo `--historico 730` a
28/08/2026, mais a rotina diária — que desde 31/08 inclui as
**consultas preliminares da Vortal** (17 na primeira recolha, **32 até
agora**, `fonte='vortal'`), o tipo que a parte L não publica — **todas
com CPV e NIPC desde 01/09/2026**, que é quando se passou a ler o
detalhe delas e não só a linha da pesquisa.
**Só 9,3% têm detalhe lido** (6 172): a rotina lê o detalhe apenas dos
publicados na janela `detalhe_dias` (60 dias), e os antigos lêem-se
quando se abre a ficha. Consequência a ter presente: um filtro por CPV
só apanha quem tem detalhe lido — o histórico é acervo por consultar,
não estatística, enquanto os detalhes não forem forçados (~17 horas de
pedidos a um por segundo). **Decisão do Afonso a 03/09/2026: fica
assim.** «Passado é passado, e nesses anúncios já não conseguimos fazer
nada» — os 60 215 sem detalhe não se vão forçar.

A base já esteve cortada aos 60 dias por decisão do Afonso (~5 100
anúncios, todos com detalhe lido); o `--historico 730` reverteu isso na
prática. A limpeza não é automática: o que envelhece acumula.

Desde 31/08/2026 os anuncios sao **uma pagina so** (`/`), e o que
aparta o acervo sao as quatro abas: **por ver 1 181** (por decidir e
ainda respondivel), **interessados 6** (todos, expirados incluidos --
um interessa expirado e trabalho em curso), **abandonados 64 324** (os
3 728 descartados a mao mais os por ver que ja nao dao para responder)
e **todos 65 511**. O Excel da casa (187 concursos, 149 ligados a
anuncios) esta na base desde 02/09/2026 mas **nao toca em nenhum
destes numeros nem se ve no painel**, por decisao dele -- ver a
seccao do registo da casa. A particao e exacta sobre os
procedimentos, e e recorte de leitura: a base nao muda -- la dentro ha
61 777 com estado `novo`, e as 876 alteracoes (`estado='alteracao'`)
nao entram em aba nenhuma, nem na de todos. A **Triagem e a
Pesquisa separadas duraram um dia**: `/anuncios` redirecciona com o
filtro atras, e o interruptor do arquivo caiu. **O esqueleto esta
implementado** (os quatro andamentos, todos a 31/08/2026): navegacao
por **quatro** intencoes -- Anuncios, Em curso, Mercado, Alertas --,
com os Indicadores fora da barra, pelo ponto da zona de estado;
vocabulario e atalhos; renovacoes como modo dos contratos; e o Fluxo B
verificado a espera so do primeiro envio (E2). **E o desenho visual
esta aplicado** (01/09/2026): paleta "ardosia e ambar", barra lateral a
140px, ficha em dossier com o leitor de pecas la dentro, e a largura a
adaptar-se ao ecra.

Por cima das abas ha, desde 01/09/2026, um recorte a mais: o
**interesse** (Alertas › Interesse), os CPV que a casa trabalha. Com
ele ligado a lista so mostra o que corresponde -- nas quatro abas --,
e di-lo por cima de si mesma com a porta de saida (`?interesse=nao`).
**Nasce desligado**, e desligado nada muda. No mesmo dia: **abandonar
passou a exigir motivo** de ambito fechado, e o **quadro passou a ser
o funil da casa** -- seis fases fixas, cada uma com o seu papel e com
o campo que pede. As entradas de diario do fim contam os numeros
todos.

*(Numeros de 01/09/2026, lidos da base e das abas do proprio painel.
Este paragrafo ja mentiu duas vezes: dizia "~5 100, todos com detalhe
lido" por cima de uma base de 66 mil a 8%, e descrevia a Triagem e a
Pesquisa como as duas paginas dos anuncios um dia depois de elas terem
sido fundidas -- as duas vezes porque as sessoes seguintes
acrescentavam seccoes sem corrigir o topo. Quem mudar os numeros ou as
paginas corrige-o na mesma sessao; a regra esta no CLAUDE.md.)*

## A ficha do anúncio e as peças do procedimento

Mudança de rumo pedida pelo Afonso: clicar num anúncio deixou de abrir
o portal do DR e passa a abrir **`/anuncio/<ref>`, dentro da app**, com
o anúncio inteiro e os documentos do procedimento.

**O texto completo já vinha e era deitado fora.** A resposta de detalhe
traz `data.DetalheConteudo.Texto` com o anúncio todo — 28 secções
numeradas, com linhas `Chave: Valor`. O código antigo corria 4 regexes
sobre ele e descartava o resto. Agora guarda-se em `anuncios.texto`.
Consequência prática: **reanalisar deixou de precisar de rede**. O
comando `python radar.py --reler` chama `reparsear()`, que recalcula os
campos a partir do texto guardado — 5125 anúncios em ~6 segundos, zero
pedidos ao portal, em vez das ~18 horas que demorava a voltar a pedir
tudo. **É isto que se corre depois de mexer em `campos_do_detalhe()`**;
foi assim que a ComprasPT foi reconhecida em 39 anúncios já guardados.

Esteve algum tempo como botão "Reler detalhes" no topo do painel, ao
lado do "Verificar agora". Saiu de lá por decisão do Afonso: é
manutenção, não uso diário, e os dois lado a lado com o mesmo peso
sugeriam que eram alternativas equivalentes — quando um se usa todos os
dias e o outro só depois de o código mudar.

Saiu a heurística `maior_texto()` ("escolher a maior string da
resposta"), substituída pelos caminhos exactos, agora conhecidos:
`data.DetalheConteudo.Texto` e `data.DetalheConteudo.URL_PDF`.

`seccoes_do_texto()` parte o anúncio em secções e pares chave/valor;
`campos_do_detalhe()` passou a ler desses pares em vez de procurar
etiquetas soltas no texto todo. Validado contra 12 anúncios reais:
**12/12 iguais** ao parser antigo, mais o link das peças que o antigo
não capturava. Aceita chaves repetidas, porque procedimentos com lotes
repetem as mesmas chaves.

### Quando é que o detalhe é lido

O detalhe é o passo caro: **um pedido por anúncio**, com pausa de um
segundo. Para os 65 mil da base isso são ~18 horas. Fazia-se em massa;
passou a ser sob procura, como os documentos:

- **Ao abrir a ficha**, se o anúncio ainda não tiver texto, é lido na
  hora (`ler_detalhe_de`). Medido: **0,6 s** para um anúncio de 2024.
  Funciona para qualquer anúncio, por mais antigo que seja.
- **Em rotina**, `ler_detalhes(dias=...)` só trata dos publicados na
  janela `detalhe_dias` (60 por omissão, no `config.json`; 0 = tudo).

Porquê 60 dias, e não tudo: **entre a publicação e o prazo vão ~18 dias
em média** (medido sobre a base). Um anúncio com mais de dois meses já
fechou — não dá para concorrer, e o CPV dele só interessa como
histórico. Isto reduz o trabalho de rotina de 65 mil para ~4400 de uma
vez (~75 min), e depois ~80 por dia, que é ~80 segundos.

**A razão de não ser tudo sob procura:** o CPV **não vem na pesquisa**,
só no detalhe — verificado, o `_source` da pesquisa tem `numero`,
`emissor`, `sumario`, `dataPublicacao`, `dbId`, `tipo` e mais uns
quantos, e nenhum campo de CPV, vocabulário ou classificação. Se o
detalhe fosse lido apenas ao abrir, o filtro de CPV e a árvore ficavam
vazios para tudo o que ainda não tivesse sido aberto — e era preciso o
CPV justamente para decidir o que abrir. Daí a janela: cobre tudo o que
é concorrível, sem pagar as 18 horas.

### Onde estão as peças, e o que se consegue de cada plataforma

A secção 15 do anúncio tem sempre *"Link para acesso às peças do
concurso (URL)"* (18/18 numa amostra). O que esse link dá depende da
plataforma — e **nenhum destes caminhos precisa de browser, sessão ou
credenciais**:

| Plataforma | % da base | Como |
|---|---|---|
| acingov | ~48% | GET no link devolve um ZIP com tudo lá dentro |
| vortal | ~42% | três saltos de API pública, ver abaixo |
| anogov | ~8% | a página lista os documentos; cada um sai de um `decryptservlet` |
| compraspt | ~1% | igual à anogov — é a mesma aplicação |

**ComprasPT esteve por reconhecer durante algum tempo** e caía num balde
chamado "(nenhuma)" que o ecrã de indicadores pintava de vermelho com a
legenda "sem acesso" — duplamente errado, porque é uma plataforma real,
nomeada no anúncio, e as peças até se obtêm. Faltava simplesmente na
lista `PLATAFORMAS`. Repara na ordem dessa constante: `compraspt` tem de
vir antes de `compraspublicas`, senão um endereço `compraspt.com` nunca
chega a ser testado contra o primeiro.

A ComprasPT e a anogov são a **mesma aplicação JSF** do mesmo
fornecedor, e um só obtentor serve as duas (`_pecas_jsf`): a página
responde a um GET com o código de acesso, lista os documentos em HTML,
e cada ficheiro sai de um `decryptservlet` no mesmo servidor. Sem
sessão iniciada.

`PLATAFORMAS_COM_PECAS` diz quais é que dão as peças; é o que decide a
cor da etiqueta na lista e o "sem acesso" nos indicadores. Ao acrescentar
uma plataforma nova, acrescenta-a nos dois sítios.

O `(nenhuma)` sobrante (~1%) são anúncios em que o próprio DR não indica
plataforma. Aparece agora com legenda neutra, não como avaria.

**A cadeia da vortal**, que custou a encontrar porque o link abre uma
SPA de 686 bytes que não diz nada sem JavaScript:

1. do link tira-se o último segmento, o identificador cifrado;
2. `GET /public/api/PublicTenderDocuments/GetPublicTenderInformation
   ?uniqueIdentifierEncrypted=<id>&languageCode=pt` → devolve
   `contractNoticeUrl`, de onde se extrai um `PT1.NTC.<numero>`;
3. `GET /public/api/ContractNoticeDetail/GetContractNoticeDocuments
   ?contractNoticeUId=PT1.NTC.<numero>` → JSON com `name` e
   `downloadUrl` de cada documento;
4. cada `downloadUrl` descarrega o ficheiro directamente.

O nome do endpoint do passo 3 foi encontrado a procurar
`ContractNoticeDetail` no bundle `index-*.js` da vortal (7,5 MB) — não
aparece no tráfego que o browser faz ao carregar a página das peças.
Atenção ao nome do parâmetro: é `contractNoticeUId`;
`contractNoticeUniqueIdentifier` devolve **400**, embora seja esse o
nome usado noutro endpoint da mesma API.

**Esteve escrito aqui que "a anogov não dá".** Era falso, e a causa
merece ficar registada porque se repetiu: eu tinha imprimido os links
truncados a 78 caracteres e testei o código de acesso **cortado**. Os
códigos da anogov têm ~50 caracteres; um código truncado faz a página
responder "não foi encontrado nenhum documento para o código de acesso
introduzido" — que se lê como "esta plataforma não dá acesso".

Com o código inteiro, a anogov devolve a lista completa: Programa do
Procedimento, Cláusulas Gerais e Especiais, anexos técnicos.

**O mesmo erro tinha acontecido antes com a vortal**, também por
truncar a URL ao imprimi-la. Duas vezes o mesmo engano custou ~53% de
cobertura declarada como impossível. A lição: nunca testar um endereço
que passou por um `[:n]` ou por um `print` truncado.

**Ficheiros grandes.** A Infraestruturas de Portugal publica anexos
técnicos enormes — um anúncio real trouxe 551 MB num único ZIP, mais
69 MB noutro, e o código juntava tudo em memória antes de decidir.
Há agora `MAX_FICHEIRO` (60 MB) e `_descarregar()`, que lê por pedaços
e desiste a meio; o que fica de fora é nomeado no aviso, e o anúncio
fica com `docs_estado='parcial'`.

O **PDF oficial do anúncio** (`URL_PDF`) descarrega para 100% dos
casos, sem autenticação, e é sempre trazido.

### Onde ficam os ficheiros

Em `documentos/<ref>/`, no disco — **não** dentro do SQLite. Blobs na
base fariam-na crescer para dezenas de GB e tornavam lento tudo o resto;
em ficheiro, o `radar.db` fica pequeno e a pasta migra bem para um
servidor ou para armazenamento de objectos, se isto sair deste PC (que
é uma intenção declarada, para partilhar trabalho com outra pessoa).
A tabela `documentos` guarda só o índice (ref, nome, tamanho, origem).

`servir_documento()` confirma com `os.path.abspath` que o caminho final
fica dentro da pasta do anúncio, para um nome de ficheiro vindo de um
ZIP não conseguir escrever nem ler fora dela. Testado: `..%2F..%2F` dá
404.

**Quando é que os documentos vêm:** ao carregar em "Trazer peças" na
ficha, e automaticamente (em fundo, para o clique não esperar) ao
marcar **interessa**. Não se descarrega tudo: 65 mil anúncios a ~3 MB
seriam ~200 GB e semanas de download. Assim tens sempre as peças
daquilo em que realmente trabalhas.

## A leitura das peças por um modelo

Quatro dos doze campos do essencial não existem no anúncio do DR: o
**objecto** decomposto, a **equipa** exigida, os **documentos que
constituem a proposta** e o **preço anormalmente baixo**. Vivem no
Caderno de Encargos e no Programa. Um modelo lê-os e a tabela fica
completa; tudo o resto sai do texto do anúncio ou de cálculo, e não
passa por modelo nenhum.

**Só vão documentos públicos.** Cadernos de Encargos e Programas, que as
entidades publicam para quem os quiser. Propostas, CVs e trabalho
próprio não passam por aqui — foi condição desde o início.

A chave fica em `groq_API_KEY.txt` (ou `chave_api.txt`) na pasta, fora
do git: o `.gitignore` apanha-a por três padrões diferentes, incluindo
maiúsculas/minúsculas. Confirma-se com `git check-ignore -v`.

### Os limites da conta, medidos

Não são os do modelo. Medido a 2026-08-26, com a chave dele:

| modelo | contexto | tokens/minuto |
|---|---|---|
| `openai/gpt-oss-120b` | 131 mil | **8 mil** |
| `openai/gpt-oss-20b` | 131 mil | 8 mil |
| `qwen/qwen3.6-27b`, `qwen3.8-27b` | 131 mil | 8 mil |
| `groq/compound`, `compound-mini` | 131 mil | 70 mil *(ver abaixo)* |

O contexto de 131 mil tokens é irrelevante: quem manda é o tecto de
**8000 tokens por minuto**, e um pedido acima disso leva 413, não 429.

**E há um segundo tecto que não aparece em cabeçalho nenhum: 200 mil
tokens por DIA.** Só se descobre pela mensagem de erro do 429
(`on tokens per day (TPD): Limit 200000`). Custou uma hora a perceber:
uma releitura do acervo ficou a moer, porque cada pedido esperava dois
minutos antes de desistir de um limite que só passa no dia seguinte.
`orcamento_do_dia_esgotado()` distingue os dois — o do minuto espera-se,
o do dia pára tudo de imediato.

Em números: uma leitura completa de um concurso são ~6 mil tokens (três
pedidos de ~2 mil). O dia dá para uns **30 concursos**, que é muito mais
do que o uso normal — mas só para **2 releituras do acervo inteiro**.
Reler tudo é uma operação cara; usar `--ler-pecas` sem `tudo` sempre que
chegue.

Os 70 mil do `groq/compound` são ilusórios — por dentro encaminha para
`meta-llama/llama-4-scout-17b-16e-instruct`, que tem tecto próprio e
mais baixo. Devolve 429 a falar de um modelo que não se pediu. Não
serve para isto.

Para saber o que a conta permite hoje, sem adivinhar:

    GET https://api.groq.com/openai/v1/models
    e ler o cabeçalho x-ratelimit-limit-tokens de um pedido pequeno

O modelo está no `config.json` (`modelo_pecas`), porque estas listas
mudam.

### A cadeia de reserva, quando o dia da Groq acaba

*27 de agosto de 2026.* O tecto diário acima é o problema: 200 mil
tokens dão 2 releituras do acervo, e a partir daí a fila fica parada até
ao dia seguinte. `FORNECEDORES` é agora uma lista, e `_perguntar()`
desce-a até alguém responder:

| ordem | fornecedor | modelo por omissão | chave |
|---|---|---|---|
| 1 | `groq` | `openai/gpt-oss-120b` | `groq_API_KEY.txt` |
| 2 | `nvidia` | `openai/gpt-oss-120b` | `nvidia_API_KEY.txt` |
| 3 | `openrouter` | `z-ai/glm-5.2:free` | `openrouter_API_KEY.txt` |

O NVIDIA fica em segundo por servir **o mesmo modelo** que a Groq: é a
reserva que não muda a qualidade da leitura. O OpenRouter, que lê com
outro modelo e é o único que já recusou por falta de vaga, fica em
último.

Todos falam o dialecto da OpenAI (`/chat/completions`, `Bearer`,
`response_format`), por isso a cadeia é uma lista de endereços e não
três clientes. O NVIDIA serve **o mesmo modelo** que a Groq — é a
reserva que não muda a qualidade da leitura.

Três decisões que valem a pena guardar:

- **Só entra quem tem chave.** Um fornecedor por configurar custava uma
  volta e um 401 em cada uma das três perguntas de cada concurso.
  Consequência prática: **sem chaves novas, o comportamento é exactamente
  o de antes** — a cadeia tem só a Groq.
- **O esgotamento fica em memória** (`_ESGOTADOS`, por dia). Sem isso,
  cada pergunta voltava a bater na porta fechada — a hora deitada fora
  que o `SEM_ORCAMENTO_HOJE` veio evitar, de volta multiplicada por três.
- **A mensagem do tecto diário só aparece quando a cadeia inteira
  esgota** (`cadeia_esgotada()`). Com "algum esgotado", bastava a Groq
  acabar para o painel dar o dia por perdido com o OpenRouter a
  responder ao lado.

`analise.modelo` passou a guardar **quem respondeu** (`groq:openai/gpt-oss-120b`),
e não o modelo configurado. Uma leitura da Groq e uma leitura de um
modelo gratuito não valem o mesmo, e a ficha tem de o dizer. Isso trouxe
de volta o problema que o `juntar_fontes()` já tinha pago nas fontes:
sendo agora variável, uma releitura parcial apagava o registo do modelo
que leu os outros campos. Reutiliza-se o mesmo `juntar_fontes()`.

No `config.json`: `modelos_pecas` escolhe o modelo por fornecedor,
`fornecedor_pecas` prende a leitura a um só — serve para comparar
leituras com o `ensaio-de-leitura`. O `modelo_pecas` antigo continua a
valer, e **só para a Groq**: aplicado à cadeia toda, pedia um nome de
modelo da Groq ao OpenRouter, onde não existe.

### Medido com chaves verdadeiras, e o resultado é mau

*27 de agosto de 2026, com as três chaves postas.* Num recorte curto
(3770 caracteres do CE do 21507/2026) os três respondem e todos honram
o `response_format`:

| fornecedor | tempo | resposta |
|---|---|---|
| groq | 1,2 s | a referência |
| nvidia | 168 s → **3,5 s** com `reasoning_effort=low` | igual à da Groq |
| openrouter | 15,6 s | mais curta, cortou o início da frase |

Os 168 segundos do NVIDIA não cabiam no `timeout=180` e faziam estourar
dois dos três pedidos de cada concurso. É o mesmo `gpt-oss-120b` da
Groq, mas aqui vem com o raciocínio ligado — e o raciocínio não serve
para nada nisto, que é extracção de texto que está à vista. Daí o campo
de extras por fornecedor no `FORNECEDORES`. **O `reasoning_effort` não
vai para os outros**: nem todos o aceitam, e um 400 por um parâmetro a
mais tirava o fornecedor da cadeia.

**Mas num recorte de tamanho real (7070 caracteres) nenhum dos dois de
reserva aguenta:**

- **OpenRouter**: 429 sistemático — `z-ai/glm-5.2:free is temporarily
  rate-limited upstream`, `limit_source: upstream_provider_shared_pool`.
  O *pool* gratuito é partilhado por toda a gente e está contendido. A
  própria mensagem sugere trazer chave própria de um fornecedor (BYOK).
  Não é utilizável como reserva.
- **NVIDIA**: `ReadTimeout` aos 240 s, mesmo com `reasoning_effort=low`,
  depois de uma série de pedidos seguidos. O escalão gratuito parece pôr
  em fila em vez de devolver 429, o que é pior: não se distingue de uma
  avaria e ocupa o *timeout* todo.

**Conclusão honesta: a cadeia está bem feita e não custa nada, mas
nenhuma das duas reservas resolve mesmo uma paragem da Groq.** Ao ritmo
normal — meia dúzia de concursos por dia — o NVIDIA provavelmente
chega, porque a 3,5 s por pedido é perfeitamente utilizável; foi o
disparo em rajada dos testes que o pôs em fila. O que a cadeia não faz é
salvar uma releitura do acervo inteiro. Para isso o caminho é o que a
própria mensagem de erro da Groq diz: **Dev Tier**.

Efeito colateral de medir isto: os testes gastaram o orçamento diário
da Groq (`Used 197803` de 200000). Repõe-se sozinho.

Se a lentidão do NVIDIA se confirmar em uso normal, o passo seguinte é
um *timeout* por fornecedor (ou pôr de lado quem estoirar, como se faz
com quem esgota) — não está feito, de propósito, para não se optimizar
contra uma medição feita em rajada.

### O que falta verificar na cadeia

**Correcção, 30 de agosto de 2026.** Esteve aqui escrito que «a cadeia
nunca correu pelo caminho normal do radar». A base desmente: a coluna
`analise.modelo` — que só o `analisar_pecas()` escreve — tem
`nvidia:openai/gpt-oss-120b` em duas análises, uma delas com os dois
rótulos juntos («groq:…, nvidia:…»), que é o `juntar_fontes()` a fazer
pela coluna `modelo` o que já fazia pelas fontes. Ou seja: a cadeia
desceu até ao NVIDIA **em produção**, pelo caminho normal, pelo menos
duas vezes, e os pontos 1 a 3 da lista que aqui estava (descer em
produção, o rótulo na coluna, os dois rótulos juntos) estão cumpridos
sem ninguém ter dado por isso.

O que falta mesmo verificar:

1. Confirmar que o ritmo normal (meia dúzia de concursos por dia) não
   põe o NVIDIA em fila como a rajada dos testes pôs — os 240 s de
   `ReadTimeout` mediram-se em rajada, não em uso corrente.

A cadeia está exercitada em produção; o que não está medido é o
comportamento do NVIDIA em uso corrente.

Os nomes dos ficheiros de chave já estão cobertos pelo `.gitignore`
(`*[Aa][Pp][Ii]_[Kk][Ee][Yy]*`), de propósito largo — confirmado com
`git check-ignore -v`.

### Porque é que não se envia o documento todo

O Caderno de Encargos deste concurso tem 52 mil caracteres e o Programa
40 mil: juntos, ~26 mil tokens, mais do triplo do que cabe num minuto.

Mas o problema também não é só de orçamento. **A parte que interessa do
Caderno de Encargos são os últimos 11 mil caracteres** — o anexo com
"Objeto da Solução Tecnológica", "Requisitos" e "Equipa". Os 41 mil
anteriores são cláusulas de rotina: força maior, subcontratação,
penalidades, sigilo. Enviar tudo gasta o orçamento em ruído.

`recorte_relevante()` marca janelas de 3500 caracteres à volta dos
títulos que casam com as âncoras, junta-as e corta ao tecto.

### Uma leitura por campo, e não uma por concurso

Ao princípio era um pedido só, com o Caderno e o Programa recortados
juntos. Parecia bem e não era.

O Caderno de Encargos do INFARMED (21295/2026) tem **167 mil
caracteres** e a tabela de perfis — a coisa que interessa mesmo, com
preço/hora, anos mínimos e certificação de cada um — está na posição
**136 mil**. As âncoras do objecto (`objeto`, `solução`, `âmbito`,
`requisitos`) casavam com 16 títulos, quase todos antes disso, e
gastavam o orçamento muito antes de lá chegar. O modelo, sem a tabela,
respondia *"conforme o Anexo I do Caderno de Encargos"* — que é verdade
e não serve absolutamente para nada.

A correcção foi separar: cada campo tem as suas âncoras, o seu recorte
de 7000 caracteres e o seu pedido (`LEITURAS`). Medido no mesmo
documento: as âncoras da equipa disputam **5 títulos em vez de 21**, e
quatro deles são a zona certa. Passou a devolver os 20 perfis todos com
os valores da tabela — e aplicou o requisito de português C1 só aos
perfis que o documento nomeia, que é o que lá está.

São três pedidos de ~2 mil tokens cada, o que cabe folgadamente nos
8000 por minuto — mais rápido e mais barato do que o pedido único de
antes.

### Duas armadilhas que já custaram

**Título não é frase.** À primeira, as âncoras casavam com qualquer
linha — e "2. As rejeições de serviços são objeto de notificação ao
adjudicatário." gastava 3500 caracteres do orçamento. O anexo do fim,
que era o que valia a pena, ficava de fora. `e_titulo()` distingue:
um título não acaba em `.,;:` e começa por maiúscula ou por marcador
(`Cláusula 1ª`, `3. Equipa`, `Artigo 9.º`). Está testado.

**`Resolução` contém `solucao`.** Sem fronteira de palavra na âncora,
"Cláusula 24ª - Resolução do contrato" e "Cláusula 35ª - Resolução de
litígios" davam anzol, e comiam o orçamento antes de se chegar a
"1. Objeto da Solução Tecnológica". Daí o `\bsolucao`.

### O `\n` que aparecia à letra

O modelo escreve `\\n` dentro das cadeias do JSON, e o `json.loads`
só desfaz uma camada — as listas apareciam numa linha só, com os `\n`
visíveis. `limpa_campo()` desfaz a segunda camada e tira linhas vazias.
O CSS de `.essencial dd` já tem `white-space:pre-line`, por isso as
mudanças de linha bastam para a lista se ver como lista.

### As peças que chegaram antes disto existir

Ficaram em disco sem texto extraído (`texto_estado` a NULL), e a leitura
não tinha o que ler — a ficha mostrava "só consta do Caderno de
Encargos" com o Caderno de Encargos ali ao lado, o que parece um erro de
leitura e não é. `analisar_pecas()` extrai o texto na hora quando falta,
sem voltar à rede, e `python radar.py --ler-pecas` percorre os que
faltam (6 de 7 recuperados; o outro é digitalização, fica para o OCR).

Sintoma parecido, causa diferente: **o painel a correr código antigo.**
Aconteceu — duas instâncias de ontem agarradas à porta 8765 (é o
problema do `SO_REUSEADDR` descrito mais abaixo, e as respostas vinham
ora de uma ora de outra). Antes de diagnosticar seja o que for,
confirmar a hora de arranque do processo:

    Get-NetTCPConnection -LocalPort 8765 -State Listen

e ver o `StartTime` do PID. Se for anterior à alteração, é isso.

### As plataformas JSF reconhecem-se pela aplicação, não pelo domínio

A anogov, a ComprasPT e a **plataforma da ESPAP**
(`plataforma-sncp.espap.gov.pt`) são a mesma aplicação, do mesmo
fornecedor. Estava a reconhecer-se pelo domínio, e os concursos da
ESPAP ficavam de fora — vinham marcados como `anogov` no DR (a
plataforma estava bem identificada!) mas com o link noutro host, e a
ficha dizia *"não sei trazer as peças da plataforma anogov"*. São 14 na
base, e são concursos grandes.

Passou a reconhecer-se pela assinatura da aplicação,
`ASSINATURA_JSF = "/faces/app/acessoDocs.jsp"`, e o `RX_DOC_JSF` deixou
de exigir o domínio. Como a página é conteúdo vindo de fora,
`docs_jsf_da_pagina()` só segue endereços **do mesmo servidor** da
página — uma página não manda o radar buscar ficheiros a outro lado.

Cobertura depois disto: 30 anúncios em 5244 (0,6%) ficam sem obtentor, e
são casos que não têm mesmo solução — links para a página inicial de uma
câmara, `www.anogov.pt` sem mais nada, um `dashboard.jsp` sem código de
acesso.

### Quando é que corre

Dentro do trabalhador que traz as peças, a seguir a `extrair_textos()`
e **antes** de marcar `docs_estado`. Assim a ficha só deixa de dizer
"a trazer as peças…" quando já lá está tudo, incluindo o objecto e a
equipa. Se ficasse depois, a página recarregava a meio e mostrava a
tabela por preencher. São ~5 segundos, ao lado de uma descarga que
demora muito mais; e se falhar, as peças ficam na mesma e há o botão
"Ler peças" à mão.

Um 429 não desiste à primeira: `espera_pedida()` lê o `retry-after` (ou
a mensagem, que diz "try again in 12.4s"), espera e tenta outra vez.
Marcar três concursos seguidos bate no tecto, e isto corre em fundo,
sem ninguém a ver.

### O que se verificou da qualidade

No 21508/2026 (AIMA), conferiram-se ~25 afirmações do modelo contra o
texto enviado: todas constam. Atenção a uma coisa na verificação — o
PDF parte números ("1 2 meses"), por isso um `grep` por "12 meses"
falha e faz **parecer** que o modelo inventou. Normalizar os espaços
entre dígitos antes de comparar.

**O erro que valeu a pena caçar:** o Caderno deste concurso exige que
os quatro perfis, *"em conjunto"*, detenham sete certificações Oracle.
À primeira, o modelo distribuiu-as por perfil — o que muda o sentido
por completo para quem concorre: sete certificações numa pessoa não é
o mesmo que sete espalhadas por quatro. As `INSTRUCOES` passaram a
mandar reparar nisso e a escrever uma linha "Em conjunto, a equipa deve
deter: …". Corrigido e confirmado contra o documento. É o género de
coisa a verificar quando se mexer no prompt.

O `preço anormalmente baixo` sai "não consta" quase sempre, e está
certo: dos 6 Programas lidos, só 1 fala do tema, e mesmo esse fala dele
como documento a juntar, não como limiar. Por isso a tabela diz "o
Programa de Concurso não fixa nenhum" depois de o ter lido, em vez de
"só consta do Programa de Concurso" — que mandava procurar o que lá não
está.

## O que descobrimos sobre o portal, para não se repetir o trabalho

O DR não tem API pública, nem RSS. Todos os endereços do género
`/dr/rss`, `/dr/feeds`, `/dr/ultimos` devolvem a mesma casca HTML de
2346 bytes. Ter conta no DR não ajuda: a pesquisa corre sempre como
`lid=Anonymous`.

O portal é uma aplicação OutSystems. O que funciona é chamar directamente
os `screenservices` que o browser chama, com os cabeçalhos de uma
captura feita no DevTools. Dois pedidos interessam:

**Pesquisa.** `POST /dr/screenservices/dr/Pesquisas/PesquisaResultado/DataActionGetPesquisas`

- Aceita pesquisa com termo vazio, o que devolve a parte L inteira por
  data. Confirmado: 205 anúncios em três dias.
- A resposta **não** traz o JSON dos anúncios aberto. Traz-os dentro de
  `data.Resultado`, que é **texto** contendo o JSON do Elasticsearch,
  com os campos em minúsculas: `hits.hits[]._source.numero`, `emissor`,
  `sumario`, `dataPublicacao`, `dbId`, `tipo`. Foi o que custou mais a
  descobrir. O código trata disto abrindo qualquer string que pareça JSON.
- O corpo do pedido tem 86 variáveis de ecrã. Não vale a pena construí-lo
  à mão: tentou-se, e o servidor responde com a casca HTML em vez de
  JSON. Usa-se o corpo da captura, esvaziando os resultados que traz
  colados e substituindo datas, termo, página e ordenação.

**Detalhe.** `POST /dr/screenservices/dr/Legislacao_Conteudos/Conteudo_Detalhe/DataActionGetAllConteudoDetalheData`

- Identifica o anúncio por `screenData.variables.Key`, no formato
  `21171-2026-1160416962`, que é `numero-com-traço` mais `dbId`. É a
  mesma chave do endereço público do anúncio, que o radar já constrói.
- `screenData.variables.Tipo` vale `"anuncio-procedimento"`.
- A página pública do anúncio **não** serve para raspar: um GET devolve
  só a casca da aplicação, 2346 bytes. O conteúdo vem por esta chamada.

**Diagnóstico de erros.** Se o pedido chegar ao serviço mas o corpo
estiver mal formado, a resposta é 400 com JSON do OutSystems, do género
`Failed to parse JSON request content`. Se o token não for aceite, a
resposta é 200 com a casca HTML. Distinguir os dois casos poupa tempo.

## As duas capturas

`curl_DR.txt` e `curl_detalhe.txt`, na pasta. São `Copy as cURL` do
DevTools, sobre os dois pedidos acima. O radar aproveita delas os
cabeçalhos e a forma do corpo; o `x-csrftoken` e a `versionInfo` vêm
do portal desde 02/09/2026 (ver «O token não expira», mais abaixo).

Usar sempre **Copy as cURL (bash)**. O formato `cmd` escapa cada
caractere com `^` e **come os acentos**: o filtro `parte` chegava ao
servidor como `L - Contratos p blicos` e o DR devolvia zero sem se
queixar. Há código a repor esse valor (`VALORES_FIXOS`), mas é remendo.

**Esteve aqui escrito que o token vinha da sessão do browser, que
havia de expirar e que não havia forma de o evitar sem API.** As três
afirmações eram falsas, medidas a 02/09/2026 — ver a secção «O token
não expira» no fim. O painel continua a avisar se o DR não aceitar o
pedido, mas só depois de tentar renovar as peças sozinho.

## O problema do CPV, resolvido — e um diagnóstico errado que aqui esteve

Estava documentado como "1 em 80, problema em aberto". A causa real era
banal: **os dados na base estavam velhos**. O código de extracção já
estava correcto; faltava mandar reler os anúncios já guardados. Feito
isso, 498 de 500 ficaram com CPV.

**Aviso a quem ler este ficheiro:** durante um tempo esteve aqui escrito
que a causa era o DR mandar caracteres corrompidos (U+FFFD), do género
`Vocabul�rio Principal`. **Isso é falso** e foi verificado: o texto do
DR tem **zero** U+FFFD, é UTF-8 impecável (`\xc3\x87` = "Ç", `\xe1` =
"á"), e `simplifica()` converte `"Vocabulário"` em `"vocabulario"` sem
problema. Os `�` que se viam eram a **consola do Windows** (cp1252) a
não conseguir imprimir acentos — um artefacto do terminal, nunca dos
dados. Se voltares a ver `�` ao correr Python no terminal, é isto;
escreve para ficheiro com `encoding="utf-8"` e confirma antes de tirar
conclusões sobre a fonte.

## CPV por código ou por palavra

O campo de CPV aceita duas coisas, à mistura e separadas por `|`, tal
como a caixa de palavras:

- **código**: `72`, `72267100-0`.
- **palavra da descrição oficial do CPV**: `software`, `manutenção`.

Para código, só os primeiros 8 dígitos contam (o dígito de controlo a
seguir ao traço é ignorado — havia um bug aqui: `72267100-0` virava
`722671000`, nove dígitos sem traço, que nunca batia certo com o valor
guardado, que mantém o traço; ficava sempre a zero, sem se notar que
era um bug e não "não há dados"). Os zeros à direita desses 8 dígitos
são tirados antes de se usar como prefixo — no CPV, zero à direita é
sempre estrutura, nunca faz parte do número em si — por isso `72000000`
vira prefixo `72` e apanha tudo o que está por baixo da divisão
(`72267100` incluído). É esta linha que faz a árvore, a seguir,
funcionar como selecção de grupo sem precisar de nenhuma lógica extra
no SQL.

Isto é possível porque a base tem uma tabela `cpv_dict` (código de 8
dígitos, descrição, versão sem acentos para pesquisa), importada de um
ficheiro `cpv-2024.json` (formato `[{"codigo":"...","descricao":"..."}]`,
9454 códigos) que o Afonso arranjou. A importação corre-se com
`python radar.py --importar-cpv caminho\para\ficheiro.json` e é
para se correr uma vez; depois disso o `radar.db` já não depende do
ficheiro. Repete-se só se aparecer uma versão mais recente do
vocabulário CPV.

`condicoes()` traduz um termo não-numérico numa lista de códigos de 8
dígitos via `cpv_por_termo()` (LIKE sobre a descrição simplificada), e
constrói o OR de prefixos como já fazia para código directo. Um termo
que não bate com nada devolve lista vazia, e a condição fica `1=0` —
mostra "nada corresponde", em vez de, por engano, mostrar tudo.

Chegaram a existir atalhos fixos no `config.json` — primeiro só
`atalhos_cpv`, depois o Afonso pediu para tirar também os `atalhos` de
palavra (TI, Bolsa de horas, Meus clientes) que já vinham do início do
projecto. Motivo: quer escolher tudo na hora, a partir da app, não
editar um ficheiro de configuração com listas fixas. Os dois já não
existem em lado nenhum — nem em `CONFIG_INICIAL`, nem no `config.json`,
nem na `PAGINA`. A caixa de palavras (`q`) continua livre, escreve-se
o que se quiser directamente; para CPV há a árvore, a seguir.

A caixa de texto do CPV (`#filtro-cpv`) tornou-se um `<input
type="hidden">` — deixou de estar visível, só a árvore a preenche. Por
troca, quando há um filtro de CPV activo aparece uma linha por cima da
árvore, "Filtro CPV activo: X, tirar", com um link que o remove sem
mexer nos outros filtros (`estado`, datas, palavras).

## Árvore de CPV no painel

Abaixo da caixa de filtros, um `<details>` "Escolher CPV na árvore"
que, ao abrir, pede `/cpv.json` (rota nova) e constrói a árvore no
browser em JavaScript simples, sem framework:

- `cpv.json` devolve os 9454 códigos do `cpv_dict` mais a contagem
  própria de cada um (quantos anúncios guardados têm exactamente aquele
  código de 8 dígitos, via `SELECT cpv FROM anuncios`, partido por
  vírgula porque um anúncio pode ter mais que um CPV).
- No browser, `nivelSignificativo()` conta os zeros à direita do código
  para saber a que nível da hierarquia pertence (72000000 tem 6 zeros
  = divisão; 72212761 tem 0 = código final). `arvoreConstruir()` liga
  cada código ao pai mais próximo que exista no dicionário com menos
  dígitos significativos — funciona porque o CPV inclui como entradas
  próprias todos os níveis intermédios, não só as folhas.
- As contagens mostradas são acumuladas (a de 72000000 soma a dela mais
  a de todos os descendentes), calculadas com uma passagem bottom-up
  depois de montada a árvore.
- Caixa de busca dentro da árvore filtra por texto (código ou
  descrição), abre os ramos onde bate certo, esconde o resto.
- Marcar a caixa de um grupo marca visualmente tudo o que está por
  baixo (`arvoreDescendentes()`, percorre `ARV_FILHOS`) — só para se
  ver na hora o que ficou incluído. O que realmente vai para o filtro
  é só o código do próprio grupo (`ARV_SEL`, guarda só o que foi
  clicado directamente); os zeros à direita tratam do resto no
  servidor, como descrito acima. Marcar `.checked` por script não
  dispara `change`, por isso os descendentes marcados por cascata não
  entram em `ARV_SEL` por engano.
- "Aplicar" escreve `Array.from(ARV_SEL).join('|')` no campo escondido
  e submete o formulário — reaproveita a `condicoes()` que já existia,
  nenhuma rota nova para aplicar o filtro.
- `arvoreSemear()` enche o `ARV_SEL` a partir do campo `filtro-cpv` ao
  carregar a página, e `arvoreMarcarSemeados()` põe as caixas em dia
  quando a árvore se constrói (abrindo os antepassados, senão o que
  está marcado fica dentro de um `<details>` fechado e parece não estar
  lá). **Sem isto a árvore abria em branco por cima de um filtro cheio
  de CPV, e como "Aplicar" escreve o que a árvore tem, aplicar limpava
  o filtro.** Passou despercebido enquanto o filtro de CPV se punha
  sempre pela árvore na mesma visita; deu de caras com os filtros
  guardados, onde o CPV chega de uma visita anterior. O semear guarda
  também os pedaços que não são código (o filtro aceita palavras), para
  "Aplicar" não deitar fora o que a árvore não sabe desenhar.

Sem framework, sem build step: tudo dentro do `<script>` no fim do
`PAGINA`. Testado ao vivo (browser tool, mais chamadas directas ao JS
quando o click do automatismo não acertava no botão certo depois da
árvore mudar o layout da página — 9454 nós é bastante DOM, o
`read_page` do próprio browser tool chegou a fazer timeout em cima
disto): árvore constrói, busca filtra, cascata marca 252 caixas ao
marcar a divisão 72, aplicar submete `/?cpv=72000000` e mostra 308
resultados dessa divisão inteira.

## Mensagem de estado sem quantidades

O Afonso pediu para a barra de baixo do painel ("ok, N anuncios lidos e
M novos...") deixar de mostrar quantidades — ficava confuso ver "500
anuncios lidos" depois de a base já ter dezenas de milhares. `recolher()`
devolve só `"ok"` no sucesso; `verificar()` já não lhe apend a
`", N detalhes lidos"`. Erros e avisos (token expirado, sem ligação)
continuam com texto completo, esses importam. Quem quiser números tem
os contadores "Por ver / Interessa / Descartados / Todos" na barra de
cima, que já eram ao vivo.

## A aparência, e o esqueleto partilhado

A interface veio de um desenho feito pelo Afonso no Claude Design
("Alertas de Concursos Públicos",
`Concursos.dc.html`), importado com a ferramenta DesignSync. O desenho
é um protótipo com dados fictícios; o que se implementou foi a
linguagem visual, ligada aos dados reais.

**O que mudou na estrutura, e é o mais importante:** havia quatro
documentos HTML completos (`PAGINA`, `QUADRO_PAGINA`, `FICHA_PAGINA`,
`CALENDARIO_PAGINA`), cada um com a sua folha de estilo, que já tinham
divergido entre si. Agora há **um** `CSS` e **um** `BASE`, e cada ecrã
só produz o seu conteúdo e chama `envolver(...)`. A barra lateral, o
cabeçalho, o selector de pessoa e as fontes existem uma vez só.

**Pormenor que evita muita dor:** o `CSS` vive numa constante própria e
entra por **substituição** (`BASE % {"css": CSS, ...}`), não escrito no
texto do molde. Como o `%`-formatting só interpreta a *string de
formato* e não os valores substituídos, as percentagens do CSS
(`50%`, `100vh`, `flex:1 1 30%`, `width:46%`) **não precisam de ser
escapadas como `%%`**. Se um dia alguém colar CSS directamente dentro
do `BASE`, tem de dobrar todos os `%` — não o faças, põe-no no `CSS`.

Tipografia: Archivo e JetBrains Mono, do Google Fonts, com `system-ui`
e `ui-monospace` como reserva — se a máquina estiver sem rede a
aplicação continua legível, só muda de letra.

**Armadilha encontrada:** entidades HTML (`&mdash;`) dentro de uma
string que depois passa por `html.escape()` saem escritas tal e qual,
porque o `&` é escapado para `&amp;`. Nos títulos das secções da ficha
usa-se o carácter literal `—`, que atravessa o `escape()` intacto. A
regra: a entidade fica **fora** do `html.escape()`, ou usa-se o
carácter.

Ecrã novo, **`/indicadores`**, que vinha no desenho marcado como
proposta. Tudo o que mostra sai de SQL sobre o `radar.db`: contagens
por estado, prazos a menos de 7 dias, distribuição por fase do quadro,
percentagem de peças obtidas por plataforma, tamanho e modo da base.
Sem serviços externos.

A contagem da lista distingue agora o que o filtro apanhou do que está
guardado ("a mostrar 500 dos 598 que correspondem · 65 869 na base").
Antes dizia "500 de 65 869 guardados" mesmo com filtro activo, o que
fazia um filtro que funcionava parecer avariado.

## Lista principal em cartões

Pedido do Afonso ("como melhoramos o UX/UI?"), começando pela lista
principal a seu pedido. A `<table>` densa virou uma lista de cartões
(`.item`, uma `<div>` por anúncio, `linha()` continua a gerar cada um —
nome mantido para não mexer no resto). Cada cartão: dia/mês em
destaque à esquerda, título e entidade, etiquetas (CPV, tipo, dias até
ao prazo a verde ou "prazo expirado" a vermelho, e o próprio estado
quando não é "novo"), preço e os botões de acção à direita.

`dias_restantes()`, que já existia para o quadro e o calendário, passou
a ser usada aqui também — antes a lista principal nem mostrava contagem
de prazo, só a data em bruto.

Aproveitou-se para dar uma passagem geral: sombra suave e cantos
arredondados em `.filtros`, `.aviso` e nos cartões, consistente com o
que já existia no quadro. Sem framework CSS, sem novas dependências —
só CSS a mais no mesmo `<style>`.

Verificado por computed style no browser (a screenshot não estava a
funcionar nesta sessão, o painel do browser não compunha frames):
fundo branco, `border-radius:6px`, sombra `rgba(0,0,0,.06) 0 1px 2px`,
título a azul `#1f4e79` a negrito, etiqueta de prazo com fundo verde
claro — confere com o CSS escrito.

## Lista paginada, 20 por página

Pedido do Afonso. A lista mostrava as primeiras 500 linhas e escondia
o resto: com 5 390 anúncios a corresponder ao filtro por omissão,
ficavam 4 890 sem forma de lá chegar sem apertar o filtro. `POR_PAGINA
= 20` substitui o `LIMITE_LISTA = 500`, com `LIMIT ... OFFSET` na
consulta. *(A constante chama-se hoje `POR_PAGINA_LISTA`: o nome antigo
colidia com o `por_pagina` do config, que é da recolha — saneamento de
30/08/2026.)*

O que mudou de decisão, e porquê:

- **A contagem deixou de ser condicional.** Havia um truque para a
  evitar (pedir uma linha a mais que o limite e ver se ela vinha), que
  poupava uma passagem pelas 65 mil linhas quando o filtro cabia todo
  em 500. Com páginas de 20 esse caso quase nunca acontece — e agora
  é a contagem que diz quantas páginas há, por isso corre sempre.
- **Corre antes da consulta das linhas**, para se segurar a página
  pedida dentro do que existe: pedir a página 999 de 270 devolvia uma
  lista vazia sem explicação. Agora dá a última. `?pag=abc` dá a
  primeira.
- **Mexer num filtro ou trocar de aba volta à página 1**
  (`args_da_lista()` deixa cair o `pag`): a página 7 do filtro anterior
  não existe no filtro novo.
- O paginador mostra uma janela de duas páginas para cada lado, com a
  primeira e a última sempre presentes — 270 números não cabem na
  linha.
- O CSV continua a exportar tudo o que o filtro apanha; o `pag` na URL
  é ignorado por `condicoes()`.

## Filtros guardados

Pedido do Afonso: "seleciono um conjunto de CPV e tenho um botão que
diz guardar filtro, e sempre que seleciono ele volta onde estava".

Tabela `filtros_guardados` (`nome` UNIQUE, `consulta`, `quem`,
`criado_em`). **O que se guarda é a query string da lista, não as
condições SQL** — assim um filtro guardado é uma ligação, aplicá-lo é
seguir um `<a href>` (leitura, sem rota nova), e o que a lista aprender
a filtrar amanhã funciona nos filtros de ontem sem migração nenhuma.

`filtro_actual()` produz a forma canónica dessa query string, e é ela
que faz o resto funcionar:

- **Ordem fixa dos campos** (`CAMPOS_FILTRO`). Sem ela, os mesmos
  filtros davam consultas diferentes conforme a ordem da URL, e o chip
  do filtro em uso nunca se reconhecia como activo.
- **O `estado` entra sempre, mesmo vazio.** É o mesmo critério da
  `condicoes()`: ausente é "por ver", presente e vazio é "todos". São
  vistas diferentes e a diferença tem de sobreviver à ida à base —
  deixar cair o campo por ser vazio trocava "Todos" por "Por ver".
- **O `pag` e o `aviso` ficam de fora** (`CAMPOS_DA_VEZ`). Guardar na
  página 3 gravava a página 3 e o filtro abria sempre a meio; o aviso
  colava-se ao filtro e reaparecia a cada visita.

Gravar por cima do mesmo nome actualiza (`ON CONFLICT ... DO UPDATE`),
e o campo do nome vem pré-preenchido com o filtro em uso — é assim que
se afina um filtro sem ficar com dois quase iguais sem saber qual é
qual. Apagar só apaga o filtro e fica-se onde se estava; os anúncios
não se mexem.

Armadilha apanhada nesta sessão: a **árvore de CPV não sabia o que já
estava no filtro** — ver a secção da árvore. Era um erro que já existia,
mas que só os filtros guardados tornavam visível.

Verificado ao vivo num browser (a screenshot continua a não funcionar,
o painel não compõe frames — verificou-se por DOM): guardar, o chip
marcar-se activo só no seu próprio filtro, sair para outro filtro e
voltar pelo chip (repõe CPV, aba e os 350 resultados), gravar por cima
actualizar em vez de duplicar, e apagar. Mais o ciclo completo por
`test_client` sobre uma **cópia** da base.

## Portal BASE: corpus de contratos celebrados

Segunda fonte, para inteligência de mercado. Vive num ficheiro próprio,
`contratos.db`, e não no `radar.db` — pelo mesmo motivo que as peças
vivem em `documentos/`: a base de trabalho tem 5 mil anúncios e tem de
continuar pequena; dois anos de contratos são 405 mil linhas e 334 MB.
Cruzam-se por `ATTACH` (`com_corpus()`).

### O que se descobriu antes de escrever código, e mudou o plano

O plano de partida tinha duas premissas. Uma caiu, a outra ficou.

- **O dump "OCDS" do dados.gov não existe na prática.** A página está lá
  desde 2019, mas tem **zero ficheiros** e a última actualização é de
  **Outubro de 2022**. Não se conta com ele. O que está vivo é o dump
  normal do IMPIC, no mesmo portal: `anuncios<ano>.json` e
  `contratos<ano>.zip`, **semanal**, domínio público (melhor licença que
  a do OCDS, que é cc-by), 15 anos disponíveis (2012–2026).
- **Os "anúncios" do BASE são o mesmo universo do DR**, não uma fonte
  nova. Medido: `nAnuncio` tem exactamente o formato do `ref` do radar, e
  **4 917 dos 5 391** refs do radar estão lá directamente; o campo `url`
  aponta para `files.diariodarepublica.pt` e há um `IdIncm` ao lado. Só
  aparecem `Concurso público`, `Concurso limitado` e afins — nenhum
  procedimento abaixo dos limiares, porque **abaixo dos limiares não há
  anúncio nenhum** (ver a secção "O que fica de fora").
- **As datas batem certo a 100%**: nos 4 917 comuns, zero dias de
  diferença. Mas o dump é semanal e anda atrás: em 27/08 o radar tinha
  anúncios de hoje e o dump parava em 21/08. Para anúncios, **o radar já
  está na melhor fonte** e não há frescura a ganhar no BASE, por
  construção — o BASE é a jusante do DR.

Conclusão, decidida com o Afonso: **os anúncios do BASE ignoram-se por
completo**. Não se acrescentou coluna `fonte` nem se mexeu na
deduplicação, porque não há segunda fonte de anúncios para deduplicar.
O que entra é só o corpus de contratos.

### Como se traz

```bash
python radar.py --contratos              # ano corrente e anterior
python radar.py --contratos 2019-2026    # intervalo
python radar.py --contratos 2024 2026    # anos soltos
```

Medido: 2025 e 2026 juntos são 91 MB descarregados, 405 798 contratos,
**2 minutos** e 334 MB de base. Os 15 anos ficam na ordem dos 2 GB — daí
o valor de origem serem dois anos e não tudo.

Três coisas que não são óbvias:

- **O endereço do ficheiro muda todas as semanas.** Traz a data da
  actualização no meio do caminho. Resolve-se sempre pela API do
  dados.gov (`recursos_contratos()`) e nunca se guarda — um endereço
  guardado deixa de servir na semana seguinte.
- **O identificador do conjunto diz "2012-a-2025" e já vai em 2026.** O
  nome ficou congelado quando o conjunto foi criado e é por ele que a
  API responde. Não o "corrijas".
- **Lê-se objecto a objecto** (`objectos_do_array()`). Um ano são 268 MB
  de JSON e um `json.loads` disso constrói a lista toda em memória.

### O erro dos filhos duplicados

Há contratos que aparecem no ficheiro de **dois anos** (e até duas vezes
no mesmo). O pai era substituído pela chave primária, mas
`contrato_cpv` e `contrato_adjudicatario` iam a `INSERT` simples e
**acumulavam**: medido, 917 CPV e 971 adjudicatários a dobrar em dois
anos, o que inflacionava qualquer contagem por CPV. A correcção não foi
mais código de limpeza no importador — foi um **índice único** em cada
tabela filha mais `INSERT OR IGNORE`, que torna o problema impossível em
vez de o remediar. A migração limpa o que já lá estava, uma vez só
(guardada por `sqlite_master`, para não varrer 400 mil linhas a cada
arranque).

## Um filtro só, para toda a aplicação

Pedido do Afonso, e obrigou a apagar o que estava: **os filtros deixaram
de pertencer a um separador**. Antes havia filtros de anúncios e filtros
de contratos, em espaços separados, e um filtro por CPV — que serve as
duas listas — tinha de ser guardado duas vezes.

Agora um filtro é um **conjunto de campos**, e cada página aplica os que
entende:

| campos | anúncios | contratos | ficha de entidade |
|---|---|---|---|
| objecto, CPV, datas | sim | sim | sim |
| estado, plataforma, entidade (texto) | sim | — | — |
| quem ganhou, procedimento, valor mínimo | — | sim | procedimento e valor |

**O que não pode acontecer é um campo cair em silêncio.**
`filtro_para(consulta, vista)` devolve a parte aplicável **e os campos
que ficaram de fora**. Onde ficam campos de fora, o chip aparece
tracejado com a legenda "parcial" e a dica diz quais. Aplicar "ganho por
MEO" aos anúncios, onde não há vencedor, seria alargar o filtro sem
avisar — e num alerta isso significava e-mails com tudo.

O mesmo cuidado no `registar_alertas()`: passava o filtro inteiro à
`condicoes()`, que ignora campos que não conhece. Um alerta "CPV 72 +
ganho por MEO" passaria a avisar de **todos** os anúncios de CPV 72.
Agora usa só a parte dos anúncios, salta os filtros que não têm nada de
anúncios, e o separador diz "avisa só por..." quando é parcial.

### O separador dos alertas é onde se gerem os filtros

`/alertas` passou a ser o centro: lista todos os filtros, liga e desliga
o alerta de cada um, apaga, e **cria filtros ali mesmo** — com a árvore
de CPV, sem ter de ir primeiro a uma lista. Cada filtro mostra onde se
aplica, com ligações directas para os anúncios e para os contratos.

### A árvore de CPV serve dois sitios com necessidades opostas

Defeito apanhado pelo Afonso: no formulário de criar um filtro, escolher
CPV não dava nada. A causa é que o `arvoreAplicar()` **submetia o
formulário** — o que numa lista é exactamente o que se quer (aplicar e
pesquisar), mas ali mandava o formulário antes de o nome estar escrito,
e a resposta era "o filtro precisa de nome". O `form.submit()` por
script salta a validação do `required`, por isso nem havia aviso do
browser.

`arvore_html(..., submeter=False)` põe um `data-submeter='nao'` no
elemento e o JS lê-o: preenche o campo, fecha a árvore, e fica na
página. E ali o campo do CPV passa a ver-se (só de leitura, escrito pela
árvore) — nas listas há a lista por baixo a mostrar o resultado, aqui
não havia nada que dissesse o que tinha sido escolhido.

### O e-mail configura-se no ecrã

Deixou de ser preciso abrir o `config.json` — onde uma vírgula a mais
deixa a aplicação sem configuração nenhuma. O formulário grava por
`gravar_config()`, que junta ao que lá está em vez de reescrever tudo.

**Só o destino e a hora.** A conta que **envia** não se configura no
painel, por decisão do Afonso e com razão: quem envia são três coisas
que andam juntas — endereço, servidor e porta — e a quarta, a
palavra-passe, nunca poderia estar ali. Ter metade no ecrã e metade num
ficheiro convidava a preencher o ecrã e a achar que estava feito. Fica
tudo do lado de fora (`config.json` e `email_senha.txt`), e o painel
**mostra** o que já está posto, a verde ou a amarelo.

## Ronda de manutenção, 28 de agosto de 2026

Correctivas e evolutivas, da mais barata para a mais cara. As
correctivas saíram todas de medições, não de suspeitas.

### A verificação automática não estava a acontecer

**A mais grave, e passou semanas despercebida.** As tarefas do Windows
nunca tinham sido criadas — procurei nas 257 tarefas da máquina e não
havia nenhuma do radar.

O que corria era o `relogio()`, que vive dentro do painel e só enquanto
ele está aberto. E como recupera slots falhados, a tabela `slots` ficava
preenchida e parecia que tinha corrido a horas. As horas denunciavam:

| slot | correu às |
|---|---|
| 23/08 09:00 | **16:27** — 500 anúncios de uma vez |
| 24/08 09:00 | 13:15 |
| 26/08 17:00 | 20:53 |
| 27/08 09:00 | 12:22 |

Nem um bateu certo: o radar recolhia quando o Afonso abria o painel.
O `agendar.bat` foi corrido e as três tarefas existem. E o painel passa
a **avisar a vermelho quando faltam** — `tarefas_em_falta()` pergunta ao
`schtasks` e guarda a resposta. Era isso que faltava para não voltar a
acontecer em silêncio.

### Cópia de segurança do radar.db

Não havia nenhuma. O `contratos.db` refaz-se com `--contratos` e a pasta
`documentos/` volta a descarregar-se, mas a **triagem, as fases do
quadro, os responsáveis e o histórico não se recuperam de lado nenhum**
— não estão no git, por serem uma base.

`VACUUM INTO` e não copiar o ficheiro: o SQLite fá-lo a quente, com a
base aberta e em WAL, e o que sai é uma base consistente e já
compactada; copiar o `.db` com o `.wal` ao lado dava uma cópia truncada.
**Uma por dia**, sete guardadas: medido, o VACUUM de 44 MB leva 37 s, e
a cada verificação era tempo a mais.

### O NIPC é a ligação certa entre o anúncio e o corpus

Fui ver se o DR publicava o número fiscal da entidade. **Publica, em
100% dos anúncios com texto guardado** — e é o mesmo número por que o
BASE a identifica, portanto é a chave directa, sem comparação de nomes
pelo meio.

Coluna `nif` em `anuncios`, lida em `campos_do_detalhe()`, e um
`--reler` encheu-a em 20 segundos **sem um único pedido à rede** — o
texto já estava guardado. 99,3% dos anúncios com detalhe lido ficaram
com NIPC.

| como se resolve a entidade | acerta |
|---|---|
| pelo nome normalizado | 96,2% |
| **pelo NIPC, com o nome de reserva** | **98,2%** |

Os 16 que faltam são entidades que nunca adjudicaram nada nos anos
importados: não há ali nada a corrigir.

### Avisos por filtro guardado

Já havia filtros guardados e já havia recolha automática; faltava cruzar
as duas coisas, e **é isso que faz o radar deixar de precisar de ser
aberto**.

A verificação corre os filtros **depois de ler os detalhes** — um filtro
por CPV só apanha o anúncio depois do CPV estar lido — e escreve o
`AVISOS.txt`. Ficheiro e não e-mail nem notificação: não há servidor de
correio configurado e uma notificação desaparece se ninguém estiver a
olhar; um ficheiro fica lá até ser lido. Aplica os filtros com a mesma
`condicoes()` da lista, para não haver um segundo motor de filtros a
divergir do primeiro.

### Preço base contra o mercado

O anúncio traz o preço base e o corpus traz o que se pagou de facto.
Postos lado a lado dizem se este concurso é generoso ou apertado para o
que aquela entidade costuma pagar naquele CPV — a pergunta que se faz
antes de decidir a proposta, e que nenhum portal responde.

Só aparece com três contratos ou mais: com dois não há padrão. Dos 20
anúncios mais recentes com preço base e CPV, 3 tinham histórico que
chegasse — e um deles trazia preço base de 30 000 € numa entidade cuja
mediana naquele CPV é 200 100 €.

**Cuidado que valeu a pena:** o DR escreve `175.000,00 EUR`, com o ponto
nos milhares e a vírgula nos cêntimos, ao contrário do que o `float()`
de Python lê. Ingenuamente dava 175,0 em vez de 175 000, e a comparação
dizia o contrário do que devia. Tem testes.

### Dois anos de anúncios

O `--historico 730` correu até ao fim: **66 009 anúncios, de 28/08/2024 a
28/08/2026**, contra os 5 391 de 60 dias que estavam. Levou algumas
horas, como previsto (uma página por segundo, para não castigar o
portal).

**60 589 ficam sem detalhe lido**, e é assim de propósito: o
`detalhe_dias` limita a rotina aos últimos 60 dias, e os mais antigos
lem-se quando se abre a ficha. Consequência a ter em conta: **um filtro
por CPV só apanha os que têm detalhe lido**, porque é de lá que o CPV
vem. Para o histórico servir de base a estatística, era preciso forçar a
leitura dos detalhes — são 60 mil pedidos a um por segundo, ou seja
umas 17 horas.

Com 66 mil linhas o painel continua rápido: a lista filtrada abaixo de
200 ms, a página 500 em 184 ms, os indicadores em 303 ms.

### Indicadores do funil

Os indicadores contavam estados parados. Passam a mostrar o movimento —
entrados, por ver, triados, interessa — mais a taxa de conversão e as
divisões de CPV onde a triagem tem dito que sim.

Dois números que nenhum ecrã mostrava e que valem por si: **694
anúncios por ver com prazo a menos de 10 dias, e 3 982 por ver já com o
prazo passado.** É a fila que custa dinheiro, e estava invisível.

Uma armadilha: a leitura da taxa traz um `%` e, concatenada no template,
o `%` de baixo tentava interpretá-la como conversão. O bloco passa a ser
montado à parte e entregue como argumento.

### O histórico da ficha restringe-se ao CPV do anúncio

Pedido do Afonso a olhar para o bloco: mostrava os 25 contratos mais
recentes da entidade com os do CPV à frente, e o resto por baixo. Com
uma entidade de 5 493 contratos, as linhas enchiam-se de limpeza e de
refeições que nada diziam sobre o concurso em mãos.

O CPV passa a **restringir**, não só a ordenar. E acrescentou-se a
coluna do **objecto**, que era o que faltava para se perceber o que a
entidade comprou de facto — "Concurso público, 358 623 €" não diz o
que é que se comprou.

São quatro estados, e cada um diz o que sabe:

| situação | o que aparece |
|---|---|
| há contratos no CPV | a tabela, com quantos são e de quantos ao todo |
| a entidade compra, mas nunca isto | "nenhum no CPV X — é a primeira vez que compra isto" |
| o anúncio ainda não tem CPV lido | diz isso, e dá a ficha da entidade |
| a entidade não está no corpus | diz isso, e porquê |

O terceiro e o quarto já existiam; o segundo é novo e só aparece por o
CPV passar a restringir. Vale por si: "esta entidade nunca comprou isto"
é informação, e antes ficava escondida no meio de 25 linhas de outra
coisa.

### Datas e árvore, iguais em todo o lado

Três arrumações pedidas pelo Afonso, todas do mesmo feitio — o que é
igual tem de parecer igual:

- **As datas mostram-se sempre DD/MM/AAAA.** Guardam-se em ISO porque
  ordenam como texto, e essa decisão mantém-se; o que mudou foi a
  camada de apresentação. Havia tabelas a mostrar `2026-08-21` e outras
  `21/08/2026`. Tudo passa por `data_pt()`, que devolve o texto como
  está se não for uma data — o DR já escreveu datas que não são datas,
  e mais vale mostrar o que lá está do que deitar a página abaixo.
- **A árvore de CPV vem sempre antes dos filtros guardados**, nas três
  páginas. A ordem é filtros → faixa do CPV activo → árvore → filtros
  guardados: escolhe-se o CPV na árvore, e só depois se guarda a
  escolha.
- **Onde se pode procurar por CPV, pode-se escolher na árvore.** A ficha
  da entidade tinha uma caixa de texto solta, onde só dava para escrever
  um código à mão. Passou a ter a mesma árvore, com o campo escondido e
  a faixa do filtro activo — e o "Aplicar" fica na ficha, não salta
  para a lista.

### Passagem de coerência a toda a aplicação

Depois de o BASE entrar, metade do painel ainda falava como se só
houvesse o DR. Correcções, todas pequenas e todas do mesmo tipo — o que
está escrito tem de ser verdade:

- **As migalhas punham tudo dentro dos anúncios.** Todas as páginas
  começavam por `Anúncios ›`, incluindo os contratos, o quadro e os
  indicadores, que são separadores irmãos. `migalhas_de(vista, folha)`
  parte agora do separador em que a página vive; só as fichas penduram
  uma folha por baixo.
- **"Verificar agora" aparecia em todo o lado.** Vai ao DR buscar
  anúncios — nos contratos aparecia ao lado do "Actualizar contratos" a
  dizer outra coisa parecida, e nos indicadores não dizia nada. Fica só
  nos anúncios, no quadro e no calendário.
- **O cabeçalho dizia "DR II série · parte L" no separador dos
  contratos**, o que é falso: aqueles dados vêm do BASE. Passa a
  "Anúncios do DR · contratos do BASE", com os dois acervos contados.
- **Os indicadores não sabiam que o corpus existia** — diziam que estava
  tudo bem sem olhar para metade da aplicação. Têm agora um bloco
  próprio: contratos, anos cobertos, entidades identificadas, idade da
  importação (a amarelo passados 14 dias, que é mais do que a cadência
  semanal do dump) e tamanho do ficheiro.
- **A rota deixou de aparecer ao lado do nome na navegação.** Era ruído
  de programador num painel que é para trabalhar.
- **Os contratos não exportavam CSV** e os anúncios sim — e são os
  contratos que dão trabalho de análise a sério. Tecto de 50 mil linhas,
  e sem filtro não exporta: o corpus inteiro seriam 1,36 milhões de
  linhas que ninguém queria pedir.
- **O separador de milhares era espaço normal em quase todo o lado e
  inquebrável no cabeçalho.** Com espaço normal o browser parte
  "1 363 300" ao fim da linha. Os três formatadores (`mil_pt`, `euros`,
  `euros_curto`) usam agora U+00A0, e há um teste que os obriga a
  concordar.
- Um `objeto` em vez de `objecto` no marcador de uma caixa de pesquisa.

### Pesquisar dentro da ficha da entidade

A ficha mostrava tudo o que a entidade já fez, sem forma de perguntar
mais nada: com 2038 contratos, era preciso sair para a lista. Passa a
ter caixa de pesquisa própria (objecto, CPV, datas, valor) que se soma à
entidade **em todos os blocos** — KPI, gráficos e contratos recentes.

Mais atalhos de período: **12 meses, 3 anos, e os últimos quatro anos
civis**. Carregar num aplica-o, carregar outra vez tira-o. É a pergunta
que se faz logo a seguir a abrir a ficha, e obrigar a escrever duas
datas para isso era atrito.

Duas consequências:

- Os atalhos para a lista levam o filtro da ficha, senão a lista
  mostrava outra coisa daquela que se estava a ver.
- Um filtro que não apanha nada diz isso e oferece "ver tudo". Antes a
  página ficava aparentemente na mesma, só com os números a zero.

### O eixo do tempo passou a adaptar-se

Com sete anos, o gráfico de evolução tinha 27 barras e os rótulos
deixavam de se ler. Acima de `MAX_BARRAS_TEMPO` (16) passa a agrupar por
ano, e a legenda diz qual das duas unidades está a usar — um gráfico que
muda de unidade sem avisar é pior do que um gráfico apertado.

### Sete anos, e a pergunta antes da lista

O corpus passou a ir de **2020 a 2026: 1 363 300 contratos, 1,2 GB**. E
a escala partiu a página: `/contratos` sem filtro levava **48 segundos**.
Três correcções, e a primeira foi de desenho.

**A pergunta vem primeiro.** Decisão do Afonso, e é a certa: sem filtro
não se mostra lista nenhuma, só o convite a filtrar. Um milhão e meio de
contratos ordenados por data não é resposta a nada — ao contrário dos
anúncios, onde a lista inteira é o acervo por triar e faz sentido vê-la.
Os gráficos também só aparecem com filtro. Isto sozinho levou a página
de 48 s para **248 ms**.

Depois, duas de desempenho, ambas medidas:

- **Índice em `contratos(data_celebracao, id)`.** Sem ele, mostrar as
  primeiras 20 de 1,36 milhões obrigava a ordenar tudo: 6 s só nessa
  consulta. E a paginação faz-se dentro de um CTE, com o `LEFT JOIN
  entidades` e as subconsultas dos nomes **depois do `LIMIT`** — a
  correrem antes, eram 45 s.
- **`IN` e não `EXISTS` nas tabelas filhas.** As duas dão o mesmo e
  nenhuma repete linhas (que era o problema do `JOIN`), mas o `EXISTS`
  obriga a passar por todos os contratos a perguntar por cada um; com o
  `IN`, a tabela filha varre-se uma vez e sai o conjunto de ids. Medido:
  **183 ms contra 517**, e `?ganhou=MEO` foi de 5 s para 605 ms.

Como está agora, com sete anos: `/contratos` vazio 248 ms, por CPV
1,5 s, por adjudicatário 605 ms, ficha de entidade 266 ms, os seis
gráficos 1,9 s (e só ao abrir).

### Actualizar o corpus a partir do painel

Faltava: o corpus só se trazia pela linha de comando, e não havia forma
de saber quando tinha sido. Agora há uma barra no topo dos contratos com
**quantos contratos, de que anos, e quando foram trazidos**, mais um
botão **Actualizar contratos**.

Corre **numa thread**, não no pedido: um ano são ~60 s e um pedido HTTP
parado esse tempo parece o painel pendurado. O estado fica no
`corpus_estado` e a página volta a pedir-se sozinha de 4 em 4 segundos
enquanto corre — a thread põe sempre um estado terminal (`ok`/`falhou`),
por isso isto pára. Um `Lock` não-bloqueante impede duas actualizações
ao mesmo tempo.

**A marca na base não é a verdade sobre se está a correr — o trinco é.**
Descobriu-se ao matar o processo do painel a meio de uma actualização,
a testar: a marca fica gravada como `a correr`, mas a thread que a limpa
morreu com o processo, e o botão nunca mais voltava. `actualizacao_a_correr()`
pergunta ao `_ACTUALIZAR`, que é do processo; a marca só serve para
mostrar o passo em que ia. Quando a marca diz "a correr" e o trinco está
livre, a página diz que ficou a meio e devolve o botão. Nada se perde:
reimportar substitui o ano inteiro.

**O botão só traz o ano corrente e o anterior.** É onde entram contratos
novos; anos fechados não mudam, e voltar a descarregar sete anos de cada
vez seriam 10 minutos por nada. Para anos mais antigos há a linha de
comando, e a barra diz isso.

Reimportar um ano substitui-o, por isso carregar no botão é seguro de
repetir. O dump do IMPIC é semanal — a barra diz isso também, para não
se estranhar que um contrato de ontem não apareça.

### Filtros guardados também nos contratos

A tabela `filtros_guardados` ganhou uma coluna `vista`, e a unicidade
passou de `nome` para **`(vista, nome)`**: "Software" quer dizer coisas
diferentes em cada lista e tem de poder existir nas duas. Isso não se faz
com `ALTER TABLE` — a migração recria a tabela uma vez, guardando o que
lá estava como filtro de anúncios, que é o que era. Testada sobre uma
cópia antes de tocar na base verdadeira, incluindo correr três vezes
seguidas.

`CAMPOS_FILTRO_CONTRATOS` é lista própria, porque os campos são outros
(quem ganhou, preço mínimo, tipo de procedimento). O `VISTAS` junta
campos e rota por separador, e é o que deixa `filtro_actual()`,
`resumo_filtro()` e a caixa servirem os dois sem duas cópias do código.

**Os parâmetros de entidade dos contratos chamam-se `entid`/`vencid`,
não `ent`/`venc`.** Nos anúncios o `ent` é a caixa de texto da entidade;
dois campos com o mesmo nome e sentidos diferentes eram um erro à espera
de acontecer. Há um teste que segura isso.

### O INSERT posicional partiu outra vez

Ao acrescentar a coluna `chave` às tabelas filhas, o importador rebentou
a meio da importação de sete anos: `table contrato_adjudicatario has 5
columns but 4 values were supplied`. **Era o mesmo erro que já tinha
acontecido com a `contratos`** e que se tinha corrigido só nessa tabela.

A correcção desta vez não foi nomear as colunas à mão outra vez, foi
tirar a duplicação: `COLS_CONTRATO`, `COLS_CPV` e `COLS_ADJ` são a única
fonte da verdade, e `_inserir()` constrói o SQL e as interrogações a
partir delas. Acrescentar uma coluna que ninguém enche passa a dar erro
no teste, e não a meio de uma importação de dez minutos.

### O nome não é a identidade — o NIF é

O Afonso reparou: "entidades que são as mesmas têm variações nos nomes".
Foi medir, e é pior do que parecia:

| | nomes | NIFs |
|---|---|---|
| adjudicantes | 8 247 | **5 948** |
| adjudicatários | 95 567 | **40 351** |

A **Universidade do Porto assina com 87 nomes** (faculdades, serviços,
institutos), o IEFP com 65 (os centros regionais), a **MEO com 81**, a
Bricantel com 50 — todos com o mesmo NIF. Agrupar por nome partia uma
entidade em dezenas, e nenhuma das partes chegava ao topo. Depois de
corrigir, a MEO entra no top 3 de TI, onde antes não aparecia de todo, e
a Petrogal passa de 304 M€ para 474 M€.

A correcção é uma **chave de entidade**: o NIF quando existe, o nome
normalizado com prefixo `n:` quando não. Sem NIF ficam as pessoas
singulares, que o BASE não identifica — 11% das linhas de adjudicatário,
mas só **5% do valor**. O prefixo evita que alguém chamado "123456789"
colida com esse NIF.

Duas tabelas novas:

- **`entidades`** — o nome canónico de cada chave. É **o mais usado**,
  com o mais curto a desempatar. Medido: dá "Universidade do Porto"
  (1 137 vezes) e não uma das 87 faculdades. O critério "mais curto"
  sozinho dava "Serviços Centrais" para o IEFP e "CP" para os comboios.
- **`entidade_nomes`** — todos os nomes por que uma entidade já apareceu,
  normalizados, a apontar para a chave. É por aqui que o nome que o DR
  escreve num anúncio chega à entidade do corpus, que pode ter assinado
  com outro dos seus 87 nomes. Subiu a resolução de 93,7% para 94,3%, e
  mais importante, passou a apanhar **todos** os contratos da entidade:
  o EMGFA foi de 2 342 para 2 628, e de 18 para 27 no CPV da ficha.

Também se corrigiu o parser: quando o NIF não é público o BASE escreve
um traço no lugar dele (`- - Filomena Ferreira`), e o nome ficava com o
`- - ` colado.

**O `+` do `GROUP BY` ficou ainda mais importante.** Com a chave
indexada, `GROUP BY a.chave` levava **17 segundos** num filtro por CPV;
com `+a.chave`, 1,5 s. E o `LEFT JOIN entidades` mudou-se para **depois
do `LIMIT`**: juntar antes eram 68 mil buscas ao índice para mostrar 10
linhas.

### Ficha da entidade

Pedido do Afonso: carregar num nome e ver um resumo. Rota
`/entidade/<chave>`, com **os dois papéis na mesma página** — a mesma
entidade compra e ganha (a Universidade do Porto compra 105,3 M€ e ganha
3,4 M€), e ter uma página de compradores e outra de fornecedores partia
isso ao meio.

Traz: identificação com o NIF e quantos nomes usa (aberto num `<details>`
— é o que explica porque é que somar "a olho" pelo nome dava outro
número); dois KPI, compra e ganha; a quem compra / a quem vende, o que
compra / o que ganha por CPV, como compra, e a evolução trimestral do
que ganha; e os 12 contratos mais recentes.

Chega-se lá de todo o lado: dos gráficos, da tabela de contratos, e do
bloco de histórico na ficha do anúncio. Os nomes são ligações.

**Os atalhos filtram por entidade, não por nome.** `/contratos?ent=` e
`?venc=` filtram pela chave, e a lista mostra uma faixa a dizer de quem
é. Sem isso o atalho prometia 1 871 contratos e mostrava menos, porque
o número da ficha estava contado por NIF e o filtro era por nome.

### Ligar uma entidade do radar às adjudicações dela

É a peça de que depende o ganho todo, e não era garantida: o radar
guarda o nome da entidade como o DR o escreve, o BASE guarda
`NIF - nome`. Medido sobre as 898 entidades distintas do radar:

| normalização | resolve | ambíguos |
|---|---|---|
| acentos, maiúsculas, pontuação (1 ano de corpus) | 818/898 = 91,1% | 0 |
| a mesma, com 2 anos de corpus | 841/898 = **93,7%** | 1 |
| + tirar EPE/SA/IP, unificar Município com Câmara Municipal | 843/898 = 93,8% | — |

Duas leituras, ambas no código:

- **Mais anos, melhor cobertura.** Os que falham não são erros de
  escrita — são entidades que ainda não adjudicaram nada nos anos
  importados. De 1 para 2 anos ganharam-se 23.
- **A normalização agressiva não compensa.** Dois casos em 898, e
  arrisca juntar entidades diferentes. `norma_entidade()` fica no
  básico, e há um teste que segura essa decisão.

Os 6% que sobram são diferenças reais, não tipográficas: sub-unidades
("Centro de Emprego de Entre Douro e Vouga" contra o IEFP que assina o
anúncio), "Município de X" contra "Câmara Municipal de X", e "EPE"
contra "E. P. E.".

### Separador próprio, e a lista passa a chamar-se Anúncios

Pedido do Afonso, e é a arrumação certa: **são coisas diferentes**. Um
anúncio é uma oportunidade a que se pode concorrer; um contrato já está
assinado e o que dele se quer saber é quem ganhou e por quanto. Até os
filtros são outros — um anúncio não tem vencedor nem valor final, por
isso "quem ganhou" e "desde € X" só existem no separador dos contratos.

A navegação passa a `Anúncios · Contratos · Quadro · Calendário ·
Indicadores`, e a chave interna da vista da lista passou de `"lista"`
para `"anuncios"` (as migalhas também). O `/contratos` tem lista
própria, `condicoes_contratos()` própria e paginação a 20, como os
anúncios — o `paginador()` ganhou um argumento `base` para servir as
duas rotas em vez de estar preso a `/`.

Filtros: objecto, entidade adjudicante, quem ganhou, CPV **com a mesma
árvore dos anúncios**, tipo de procedimento (lista dos que existem no
corpus, por frequência), datas de celebração e preço mínimo. A linha de
contagem soma **o valor do filtro todo**, não o da página: é o número
que diz quanto vale aquele mercado.

### A árvore de CPV serve os dois separadores

Uma árvore só, `arvore_html(n_cpv, de)`, e um JS só. O que muda é **de
onde vêm as contagens**, e isso viaja num `data-de` no próprio
`<details>` — é dali que o `arvoreCarregar()` lê a rota a pedir. Duas
cópias do JS divergiam ao primeiro arranjo.

`/cpv.json` passou a aceitar `?de=anuncios` (por omissão) ou
`?de=contratos`, com uma função de contagem por fonte (`FONTES_CPV`).
**Isto não é cosmético:** as contagens são outras e mostrar as erradas
diria que uma divisão está vazia quando tem milhares de contratos.
Medido — 1 548 códigos têm anúncios e o mais carregado tem 175; **5 657
códigos têm contratos** e o mais carregado tem 49 979.

A cache (`_CPV_CACHE`) deixou de ser uma variável e passou a dicionário
com uma entrada por fonte: com uma só, alternar de separador deitava
fora a cache do outro a cada visita, e são ~770 KB a serializar de cada
vez. A chave de frescura é o que muda a contagem — anúncios com detalhe
lido, ou contratos no corpus.

O campo do CPV tem o mesmo `id='filtro-cpv'` nos dois separadores, que é
por onde o `arvoreSemear()` lê e o `arvoreAplicar()` escreve. Nos
anúncios é escondido, nos contratos é uma caixa de texto à vista — o que
até ajuda, vê-se o que a árvore lá pôs. Verificado ao vivo: marcar as
divisões 33 e 72 e aplicar leva a `/contratos?cpv=33600000|72000000`,
73 958 contratos, 6,85 mil M€, e a árvore volta a abrir com as duas
marcadas.

**`EXISTS` e não `JOIN`**, nas duas tabelas filhas. Com `JOIN`, um
contrato ganho por um agrupamento aparecia uma vez por adjudicatário —
e há um com 35 — e um contrato com vários CPV da mesma divisão aparecia
uma vez por CPV. Verificado sobre os 404 954: zero ids repetidos.

### Gráficos, e porque respondem ao filtro

Pedido do Afonso: "só ter os dados não ajuda em nada". Três gráficos num
`<details>` por cima da tabela, e o essencial do desenho é que correm
sobre **o mesmo `WHERE` da lista**. O filtro é a pergunta ("CPV 72,
últimos 12 meses") e os gráficos são a resposta; fixos, seriam a
resposta a uma pergunta que ninguém fez.

1. **Quem ganha** — top 10 por valor adjudicado. O valor **reparte-se
   pelos adjudicatários** (`n_adj`): um contrato ganho por um agrupamento
   de três não vale três vezes o mercado, e há um com 35.
2. **Como se compra** — por tipo de procedimento. É o mais subestimado
   e o que mais muda uma decisão, porque diz **quanto daquele mercado é
   sequer concorrível**. Medido nos três CPV que interessam à empresa:

   | divisão | o que domina |
   |---|---|
   | 72 (TI) | Concurso público 568 M€ > ajuste directo 254 M€ |
   | 45 (obras) | Concurso público 8,8 mM€, folgado |
   | 33 (saúde) | **Acordo-quadro 4,0 mM€** > ajuste directo 1,6 mM€ |

   Na saúde o concurso público nem entra nos dois primeiros: compra-se
   por acordo-quadro, e quem não está no acordo não concorre. Isso não
   se vê numa tabela de contratos.
3. **Quem compra** — top 10 entidades adjudicantes por valor.
4. **Concentração** — que fatia levam os cinco maiores, entre todas as
   empresas que ganharam alguma coisa. Diz se vale a pena entrar: um
   mercado onde cinco levam quatro quintos joga-se de outra maneira, ou
   não se joga. Medido: no corpus todo os cinco maiores levam **9%**
   (entre 95 567 empresas); em TI 10%; na saúde 13%.
5. **Tamanho dos contratos** — quantos há de cada escalão, com o escalão
   da mediana realçado a verde. Responde a "há aqui contratos do meu
   tamanho?". Na saúde, **64 313 dos ~126 mil ficam abaixo de 5 k€** —
   é um mercado de compras miudinhas com alguns contratos grandes.
6. **Evolução** — valor celebrado por trimestre.

Três decisões de construção:

- **Desenha-se em Python, com `<div>`s dimensionados**, como o
  `/indicadores` já fazia (`.barras`). Sem biblioteca, sem SVG, sem CDN
  — continua a funcionar offline e sem build step. Barras horizontais em
  1 e 2 porque os nomes das empresas são longos e não cabem por baixo.
- **Pedidos só ao abrir**, como a árvore. São ~800 ms de consultas sem
  filtro; a correr a cada visita punham a lista lenta para quem só quer
  a tabela. A rota `/contratos/resumo` devolve **HTML e não JSON**, de
  propósito: desenhar continua em Python e o JS só tem de o pendurar.
- **`n_adj` é coluna, não subconsulta.** Contar os adjudicatários por
  linha levava **2,1 s** no corpus todo; em coluna, 407 ms. Enche-se na
  importação e há migração para o que já lá estava. Foi aqui que se
  descobriu que o `INSERT` posicional partia em silêncio ao acrescentar
  uma coluna — passou a nomear as colunas.

Três medições que decidiram o resto, e que não se adivinhavam:

- **"Quem ganha" e "Concentração" saem da mesma passagem.** As duas
  agregam por adjudicatário; com `SUM(v) OVER ()` e `COUNT(*) OVER ()`
  vem o total e o número de empresas sem uma segunda varredura. Duas
  consultas eram 889 ms, uma é 514.
- **O índice tornava o "quem compra" 3× mais lento.** `GROUP BY
  c.adjudicante_norm` levava 1 443 ms: o SQLite varria o índice e ia
  buscar cada linha ao acaso. Com o `+` à frente (`GROUP BY
  +c.adjudicante_norm`), que desliga o índice de propósito, são 477 ms
  com o mesmo resultado. **Não tires o `+`.** Agrupa-se pelo nome
  normalizado e não pelo nome em bruto porque junta 636 variantes em
  8 247 nomes — a mesma entidade escrita de duas maneiras.
- **Escalões em vez de mediana exacta.** Ordenar 400 mil preços para
  tirar o do meio levava 953 ms; os escalões custam 222 e respondem
  melhor à pergunta. A mediana sai do escalão onde a contagem acumulada
  passa metade, e vai realçada.

Os seis juntos são ~1,7 s sem filtro, e só correm ao abrir o painel.

**O trimestre a decorrer vai às riscas.** Sem isso, o trimestre corrente
aparecia como uma queda a pique (668 M€ contra 1,2 mM€ no anterior) e a
conclusão que se tirava dali — "este mercado secou" — era falsa; é só
não ter acabado. Tem legenda, tracejado próprio e a dica diz "trimestre
a decorrer".

### O que aparece na ficha

Bloco "Histórico de adjudicações", na coluna esquerda: os contratos já
celebrados por aquela entidade, **os do mesmo CPV primeiro e
destacados**, e dentro de cada grupo os mais recentes. Data, tipo de
procedimento, quem ganhou, preço. Exemplo real (Município de Oeiras,
CPV 48100000): 1 433 contratos da entidade, 6 no mesmo CPV.

O CPV compara-se com `prefixo_cpv()`, que saiu de dentro da
`condicoes()` para as duas coisas procurarem com o mesmo critério —
duas cópias daquela regra divergiam, e a de "nunca abaixo de dois
dígitos" já custou 4592 anúncios em vez de 440 uma vez.

Degrada bem, e está verificado: sem corpus importado diz como o trazer;
com corpus mas sem esta entidade diz que não há e porquê. Nunca finge
que não há histórico quando o que falta é a importação.

### Porque é que o `contratos.db` não está protegido pelo hook

O `proteger_dados.py` cobre o `radar.db` porque lá está a triagem, que
não se recupera. O corpus é **dado derivado**: refaz-se em dois minutos
a partir de um dump público. Protegê-lo só travava a própria
importação. Está no `.gitignore`, isso sim — são centenas de MB.

## Quadro (kanban)

Pedido do Afonso depois de mostrar o SpotGov (concorrente comercial,
200€/mês) como referência: queria o género do "Saved Tenders" de lá —
colunas configuráveis, cartões arrastáveis, etiquetas, contagem de
prazo. Decidiu-se conscientemente **não** replicar a pesquisa "Search
with AI" do SpotGov, para o radar continuar 100% local sem depender de
nenhum serviço externo.

**As fases de origem** vêm do desenho: *Por analisar, A preparar
proposta, Em revisão, Submetido, Resultado*. Estão em `FASES_INICIAIS`
e são semeadas por `semear_fases()`, chamada de `iniciar_db()`.

Essa função tem de ser cuidadosa, porque corre a cada arranque: só
actua se o quadro estiver **vazio**, ou se tiver **apenas** a coluna
`Guardados` que as primeiras versões criavam sozinha — nesse caso
reaproveita-lhe o `id` e renomeia-a para a primeira fase, para não
desgarrar os cartões que já lhe estivessem atribuídos. Se encontrar
qualquer outra coisa, não toca em nada: as fases são do utilizador,
que as renomeia, acrescenta e apaga no próprio quadro. Verificado nos
três casos (base nova, base só com `Guardados`, base já personalizada).

Tabelas novas: `fases` (id, nome, ordem — as colunas do quadro),
`etiquetas` (id, nome, cor), `anuncio_etiquetas` (ref, etiqueta_id,
tabela de ligação). Coluna nova em `anuncios`: `fase_id`, adicionada
por `ALTER TABLE` em `iniciar_db()` se ainda não existir (migração
idempotente, corre sempre, não faz nada se a coluna já lá estiver).

Marcar um anúncio como `interessa` (no botão da lista principal)
atribui-lhe a primeira fase automaticamente
(`fase_id=COALESCE(fase_id, primeira_fase())`, em `mudar_estado()`) —
só entra no quadro quem já está marcado como interessante, o quadro não
é uma vista diferente da lista toda.

Rota `/quadro` monta o board a partir de `anuncios WHERE estado='interessa'`,
agrupado por `fase_id`. `/quadro/mover` (POST, JSON) é a única rota
chamada por `fetch`, para o arrastar-largar não recarregar a página; o
resto (nova fase, renomear, apagar, etiquetas) é formulário + redirect,
ao estilo do resto da app — mais simples e mais robusto que gerir tudo
em JS.

Arrastar e largar é `dragstart`/`dragover`/`drop` nativos do HTML5, sem
biblioteca. Testado com eventos disparados por JavaScript em vez de
arrastar a sério com o rato (o browser tool desta sessão não simula
arrasto físico de forma fiável) — dataTransfer mockado à mão com
`setData`/`getData`, confirmado que persiste (`fase_id` mudou na base)
depois do "drop".

Apagar uma fase só é permitido se sobrar mais que uma (`fase_apagar()`);
os cartões que lá estavam vão para a fase seguinte por `ordem`. Etiquetas
são globais (por nome, `COLLATE NOCASE` para não duplicar "Urgente" e
"urgente"), com cor atribuída por rotação sobre `CORES_ETIQUETA` — sem
selector de cor, para manter simples.

Armadilha encontrada a testar: `curl -d "nome=Em revisão"` pelo Git Bash
do Windows não manda UTF-8 correcto (o `ã` fica em bytes que o Flask não
consegue interpretar, e a fase não chega a ser criada, sem erro visível).
`requests.post` do Python não tem este problema. Não é bug da app, é do
terminal — mas vale a nota para não se perder tempo outra vez a pensar
que a rota está avariada.

## Correcções vindas de uma revisão ao código

Uma passagem de revisão encontrou 15 problemas, todos corrigidos. Os que
vale a pena conhecer, porque voltariam a acontecer:

**O filtro de CPV por divisão apanhava dez vezes de mais.** Tirar os
zeros à direita de `30000000` deixa `"3"` — e `LIKE '3%'` apanha as
divisões 31, 33, 34, 35, 37, 38 e 39. Medido: 4592 anúncios em vez de
440. Agora o prefixo nunca desce abaixo de dois dígitos, que é a largura
da divisão no CPV. Escapou porque as divisões do Afonso (48 e 72) têm um
segundo dígito diferente de zero e por isso funcionavam.

**O sucesso era decidido por `"ok" in mensagem`.** A mensagem de falha de
rede é `"sem ligação ao DR: Connection broken..."` — e *br**ok**en*
contém "ok". Uma falha de rede passava por sucesso: o painel pintava o
ponto de verde e o programa seguia para ler detalhes. `recolher()`
devolve agora `(correu_bem, mensagem, novos)` e o estado fica em
`ultima_ok`. **Nunca decidir estado por substring de texto para humanos.**

**Tudo o que altera dados era um link GET** — incluindo o então `/reler`,
que reprocessa a base inteira. Um prefetch do browser ou qualquer coisa
que siga links disparava-os. Há agora `accao()`, que desenha um `<form
method="post">` com aspecto de botão, e as rotas exigem POST. (O
`/reler` acabou por sair do painel de vez — passou a `--reler`.)

**O `/quadro/mover` aceitava qualquer `fase_id`.** Um id inexistente
punha o cartão numa coluna que não é desenhada: desaparecia do quadro
sem voltar à lista, porque continuava `interessa`. Agora valida a fase e
o anúncio, devolve 404, e o JavaScript recarrega quando o servidor
recusa — antes o ecrã ficava a mostrar uma mudança que não foi gravada.

**Sucesso parcial nos documentos parecia sucesso.** O PDF do anúncio vem
sempre; se as peças falhassem, `docs_estado` ficava `ok` e o aviso era
deitado fora. Há agora o estado `parcial`, dito na ficha.

**O `config.json` estragado era substituído em silêncio** pelos valores
de origem — e `ler_config()` corre a cada página, por isso perdia-se na
página seguinte. Agora guarda-se `config.json.estragado` primeiro.

Outros: `LIKE` passou a escapar `%` e `_` (procurar "50%" devolvia tudo
o que tem "50"); o escape usa `!` e não a barra invertida, que teria de
sobreviver ao literal de Python e ao de SQL ao mesmo tempo. As descargas
de documentos passaram a uma fila com um trabalhador, em vez de uma
thread por clique. O `relogio()` grava o erro em `ultimo_erro_relogio`
em vez de o engolir. `guardar()` usa `INSERT OR IGNORE`. A lista pede
uma linha a mais em vez de correr a consulta filtrada outra vez só para
contar. `descricoes_cpv()` faz uma consulta e não uma por código.
`cpv.json` é guardado em memória, invalidado pela contagem de detalhes
lidos.

### Segunda revisão, à leitura das peças

Quatro correcções, todas nascidas de uma revisão ao código escrito na
mesma noite.

**O tecto diário do modelo deitava fora o que já tinha sido lido.** São
três pedidos por concurso; quando os dois primeiros respondiam e o
terceiro apanhava o "tokens per day", a função saía *antes* do INSERT —
o objecto e a equipa tinham sido lidos, pagos, e eram deitados fora. E
como devolvia `True`, o `obter_documentos()` não marcava erro nenhum (só
o faz quando isto devolve `False`) e a ficha ainda dizia "peças lidas
pelo modelo". Simulado sobre uma cópia da base: antes, nenhuma linha na
`analise`; agora ficam os dois campos, e a mensagem do tecto continua a
chegar inteira ao `--ler-pecas`.

**As fontes não acompanhavam os campos.** O `juntar_leituras()` guarda o
que se leu antes quando um pedido falha, mas o `fontes` era substituído
pelas peças desta vez — e a nota da ficha, que passara a nomeá-las,
dizia "objecto lido de Programa.pdf" a texto vindo do Caderno de
Encargos. O `juntar_fontes()` é o companheiro que faltava: numa leitura
parcial, junta as de antes.

**O `e_pdf()` a ler 1 KB dava um ZIP por PDF.** Com o PDF lá dentro por
comprimir — que é como o `zipfile` grava por omissão — o `%PDF` fica no
byte 46. Como o `extrair_textos()` pergunta ao `e_pdf()` antes de ir ao
`texto_do_zip()`, o pacote ia ao pypdf e nunca chegava a ser aberto.
Nenhum dos sete ZIPs em disco é assim (são todos deflate), por isso
ainda não tinha mordido. Rejeita-se agora o magic `PK\x03\x04`.

**A caixa das peças mentia enquanto a fila trabalhava.** O botão
"Actualizar peças" passou a pôr na fila em vez de esperar, mas o ramo
"há documentos" vinha antes do "pendente": a lista antiga aparecia como
se estivesse pronta, e o `obter_documentos()` apaga-a e volta a inserir.
Falhar a actualização com peças velhas em disco também não se via em
lado nenhum. O aviso na ligação saiu de vez: o recarregar é um
`location.reload()` e levava a query string atrás, por isso o "a trazer
as peças…" ficava colado à página depois de a descarga ter acabado.

Ficou de fora, de propósito, a regra dos anexos a exigir a palavra por
extenso: um `CE_e_Anexos.pdf` perderia o papel, mas não há nenhum nome
assim no acervo e não se mexe em regras de classificação por suposição.

## Contagem de dias, e os dias da semana no calendário

`conta_dias()` e `etiqueta_prazo()` tratam a contagem toda num sítio só,
porque estava errada em três pontos ao mesmo tempo:

- um prazo que acaba **hoje** dava `0 dias` (agora "termina hoje", a
  vermelho, porque é hoje que se perde);
- o dia seguinte dava `1 dias`, sem concordância (agora "amanhã");
- a ficha dizia "faltam 0 dias" pela mesma razão.

`dias_restantes()` continua a devolver o número cru; quem escreve texto
passa por `conta_dias()`. Se acrescentares outro sítio que mostre
prazos, usa a mesma função em vez de formatar `%d dias` à mão.

O **calendário ganhou os dias da semana**. Sem eles a grade era uma
tira de 45 números onde não se distinguia um sábado de uma terça, e um
prazo ao fim-de-semana muda o que se faz na sexta. Agora cada coluna
traz `seg/ter/qua/...`, os fins-de-semana ficam sombreados
(`.cel-dia.fds`) e o primeiro dia de cada mês leva uma linha mais
grossa (`.mes-novo`). As iniciais soltas não servem em português:
segunda/sexta/sábado e quarta/quinta repetem-se, daí as abreviaturas
de três letras.

Verificado contra as datas reais: as 45 células batem certo com o dia
da semana e o dia do mês, e as pílulas caem exactamente na coluna do
respectivo prazo (medido em pixels contra o cabeçalho, não só no HTML).

## Calendário

Vista nova, só de leitura, rota `/calendario`. Uma grade CSS
(`grid-template-columns:260px repeat(45,74px)`, uma linha por
`<div class='linha-grade'>`) com uma coluna fixa à esquerda (título e
entidade, `position:sticky;left:0`) e 45 colunas de dias a partir de
hoje. Cada anúncio interessado com prazo fica numa linha, com uma
pílula na coluna do dia certo, mostrando o nome da fase actual no
quadro. Testado ao vivo: o prazo `2026-09-05` caiu exactamente na
coluna com esse cabeçalho.

Decisão: quem tem prazo fora da janela de 45 dias (já passado, ou muito
à frente) não entra na grade — só conta numa nota de texto por baixo.
A alternativa (mostrar a linha inteira vazia, sem pílula visível) só
ocupava espaço sem dizer nada.

Não há paginação nem scroll infinito para trás/à frente no tempo — se
um dia isso fizer falta (portefólio com muitos prazos a mais de 45 dias),
é só mudar `DIAS_CALENDARIO`.

## Tarefas agendadas

Criadas nesta sessão via `schtasks`, equivalente ao que o `agendar.bat`
faz (o próprio `.bat` não se corre bem sem consola interactiva, por
causa do `pause` no fim): "Radar DR 09h" e "Radar DR 17h", diárias,
a chamar `verificar.bat`. Confirmado com `schtasks /Query`.

## Painel a correr

Deixado a correr em fundo (`python radar.py`, sem `--uma-vez`) nesta
sessão, depois de tudo testado — porta 8765, um único processo (o
problema do duplo-bind do Werkzeug, descrito mais abaixo, não voltou a
acontecer desta vez).

## Pessoas, e o caminho para isto ser partilhado

O Afonso perguntou como levar isto para a cloud, para trabalhar com
mais alguém. Decisão tomada: **fica local por agora**, mas com o
terreno preparado.

**Feito já, porque é risco presente e não futuro:**

- **`journal_mode=WAL`** no `liga()`, mais `busy_timeout=30000`. Havia
  (e há, enquanto a recolha corre) dois processos a escrever na mesma
  base — o painel e a recolha em fundo. Com o modo `delete` que estava,
  isso dá `database is locked` mais cedo ou mais tarde. WAL deixa ler
  enquanto outro escreve. A definição é persistente na base, mas repete-se
  na ligação porque é barato e cobre bases novas.
- **Identidade sem autenticação.** Tabela `pessoas`, tabela `historico`
  (ref, quem, acção, detalhe, quando) e `anuncios.responsavel`. Quem
  está a usar a app diz o nome no cabeçalho, fica num cookie de um ano,
  e passa a ser gravado em cada mudança de estado, de fase e de
  responsável. **Não há palavra-passe de propósito**: hoje isto corre
  no PC de uma pessoa, e um ecrã de login seria atrito puro. O modelo de
  dados é que fica pronto — histórico não se inventa depois.

**O que falta mesmo para pôr isto num servidor partilhado**, por ordem:

1. **As capturas são o verdadeiro obstáculo, não o alojamento.** O
   `curl_DR.txt` e o `curl_detalhe.txt` levam o token da sessão do
   browser e expiram. Local, refaz-se em dois minutos. Num servidor,
   alguém tem de refazer a captura no browser **e enviá-la para lá** —
   é preciso um ecrã para colar a captura, em vez de trocar ficheiros
   na pasta. Isto não desaparece com a cloud; é o preço de o DR não ter
   API pública.
2. **Servidor a sério** (waitress no Windows, gunicorn no Linux). O
   `app.run()` é o servidor de desenvolvimento do Flask e ele próprio
   avisa que não serve para produção.
3. **Autenticação**, porque na internet pública qualquer um apagaria
   fases e mudaria estados. O sítio para a pôr é o bloco "pessoas".
4. **Separar o agendador do processo web.** O `relogio()` corre numa
   thread dentro da app; com vários trabalhadores passavam a existir
   verificações duplicadas. Vai para um processo próprio (ou uma tarefa
   do sistema, como já existe no Windows).
5. **Disco persistente** para `documentos/`. Em plataformas de sistema
   de ficheiros efémero (Cloud Run, Heroku) os ficheiros desaparecem a
   cada arranque.

Para 2-3 pessoas **SQLite com WAL chega bem** — não é preciso Postgres,
e trocar de base de dados agora seria complicar sem ganho. Dimensões
medidas: `radar.db` a 32 MB, projectado ~400 MB com todo o texto;
`documentos/` cresce com o uso.

Alojamento recomendado quando for a altura: um VPS pequeno (Hetzner,
DigitalOcean, ~5-10€/mês), que dá disco persistente e controlo, em vez
de plataformas geridas que complicam o armazenamento dos documentos.

## Histórico e paginação

Dois limites artificiais, ambos hoje corrigidos:

- `dias_catchup` (15 dias) é a janela da verificação de **rotina**
  (09h/17h) — continua pequena de propósito, não vale a pena pedir mais
  duas vezes por dia. Para trazer mais história de uma vez, sem alterar
  esse valor, há `python radar.py --historico N` (N em dias, 730 por
  omissão), que faz uma chamada a `recolher()` isolada com um `cfg`
  modificado só na memória.
- `paginas` estava a 20 (=500 resultados a 25/página) e cortava a meio
  de qualquer pesquisa que tivesse mais que isso — foi o que aconteceu
  com os 500. O ciclo em `recolher()` já parava sozinho quando o portal
  devolvia menos que uma página cheia (fim real dos resultados); o `20`
  não era esse sinal, era um tecto que se atingia primeiro. Subido para
  5000, que na prática nunca se atinge — fica só como rede de segurança
  contra um ciclo infinito se o portal se comportar mal.

Consequência a ter em conta: com uma janela grande, `recolher()` só
grava no fim (`guardar(colhidos)` corre uma vez, depois do `for` todo).
Não há sinal de progresso a meio — só o log e a base de dados depois de
terminar. Para 2 anos, a listagem sozinha leva uns 20-40 minutos
(segundo a estimativa; o portal ronda as 60-70 publicações por dia na
parte L, e há um segundo de pausa entre páginas). Os detalhes de cada
anúncio novo (CPV, prazo, preço) são um pedido à parte, também com um
segundo de pausa, e só correm 40 de cada vez por verificação
(`detalhes_por_volta`) — para um backlog grande, ler tudo pode levar
várias voltas ou, se se forçar em ciclo como se fez na correcção do CPV,
horas seguidas. Nessa altura vale a pena confirmar que o token de
`curl_detalhe.txt` não expira a meio (ver secção das capturas).

Índices novos em `anuncios(data_pub)`, `anuncios(cpv)` e
`anuncios(estado)`, para a base não abrandar à medida que cresce para
lá dos 500.

## Testes, controlo de versões e automatismos

**`teste_radar.py`** — 655 testes a 03/09/2026 (eram 118 quando esta
secção foi escrita), correm em poucos segundos, sem rede nem a base
verdadeira (as migrações ensaiam-se numa base temporária). Não são
exaustivos de propósito: cada um corresponde a um erro que existiu
**mesmo**, e o comentário diz qual, para ninguém "simplificar" de volta
para o erro.

Verificado que apanham regressões: reintroduzindo o bug do CPV
(`curto or digitos` em vez do mínimo de dois dígitos), três testes falham
com a mensagem certa (`['3'] != ['30']`).

**Git** — o repositório começa aqui, com um `.gitignore` que deixa de
fora o que nunca deve entrar em histórico: `curl_*.txt` (levam o token da
sessão do browser), `radar.db*`, `documentos/` (Cadernos de Encargos e
propostas) e `amostras/`.

**Hooks**, em `.claude/hooks/` — dentro do `radar/`, e não na pasta-mãe,
onde estiveram e onde estavam inertes: as definições de projecto lêem-se
da raiz, que é aqui, e o `$CLAUDE_PROJECT_DIR` do comando apontava para
um caminho que não existia. Medido, não suposto: escrever um ficheiro
chamado `curl_ensaio_do_hook.txt` — nome que casa com o padrão protegido
— passou sem uma palavra.

- `verificar_sintaxe.py` (PostToolUse) — compila o ficheiro Python
  acabado de escrever, com `-W error::SyntaxWarning`. Existe porque os
  erros que passaram foram todos de sintaxe e de escapes; este apanha o
  `"\%"` que aqui mordeu duas vezes.
- `proteger_dados.py` (PreToolUse) — recusa escritas em `curl_*.txt` e
  `radar.db*`. Sai com código 2 para travar a ferramenta.
- `testes_antes_do_commit.py` (PreToolUse) — trava o `git commit` com
  testes a falhar. Só o commit; o resto do git passa.

Os três olham para o `file_path` das ferramentas de escrita **e para o
texto dos comandos** do Bash e do PowerShell. Só pelo `file_path` eram
uma porta com a parede ao lado: um `rm radar.db` ou um `sed -i` numa
captura passavam. No `proteger_dados.py`, recusa-se a escrita e deixa-se
passar a leitura — um `sqlite3 radar.db "SELECT ..."` é rotina, e travar
leituras só ensinava a desligar o hook. Fica um buraco assumido: um
`python -c` que abra a base sem dizer "radar.db" no comando passa; contra
isso vale o hábito de apontar o `radar.DB` a uma cópia, que é o que o
comando tem de fazer para ser deixado passar quando traz SQL de escrita.

As mensagens dos três saem em UTF-8 explícito: a consola do Windows é
cp1252 e o português acentuado chegava estropiado do outro lado.

**Skill `/estado-radar`** — o resumo que se pedia à mão várias vezes por
sessão: quantos por ler, triagem, fases, validade das capturas, painel e
tarefas. Lê a base em modo só-leitura e não importa o `radar.py`, por
isso funciona mesmo com o programa a meio de uma alteração que não
compila.

**Skill `/ensaio-de-leitura <ref>`** — a ferramenta do ponto que falta
para a v1. Põe cada linha da resposta do modelo ao lado do pedaço do
documento que a sustenta, e marca-a: literal, reescrita (as palavras
todas lá, mas não seguidas), ou sem apoio. A comparação é feita sobre
texto comprimido — sem acentos, espaços nem pontuação — porque o
extractor parte números ("1 2 meses") e um grep ingénuo produz uma
acusação falsa de invenção. A janela mostrada é escolhida pelo sítio
onde mais termos da linha se juntam: pela primeira ocorrência, as 20
linhas da tabela de perfis do INFARMED apontavam todas para uma cláusula
de acompanhamento a meio do Caderno. A fonte passa pelo `sem_indice()`,
como no caminho que leva o texto ao modelo. Sem `--sem-modelo`, relê
sobre uma **cópia** da base.

Medido nos dois concursos vistos a fundo: INFARMED 21295/2026 dá 8
literais, 25 reescritos, 0 sem apoio; AIMA 21508/2026 dá 6 "sem apoio"
que são todos nominalizações do modelo ("Automatizar" → "Automatização",
"Reduzir" → "Redução"), visíveis num relance na janela ao lado. O que o
guião **não** sabe é se o que saiu chega para decidir — essa continua a
ser a pergunta do Afonso.

**Subagente `explorador-de-plataforma`** — investiga se as peças de uma
plataforma sem obtentor se alcançam sem sessão iniciada, e devolve
receita ou um "não há" fundamentado. São 30 anúncios em 5 244 com link e
sem obtentor (anogov.com 5, miisy 2, source360.ren.pt 2, comprasnasaude
2, e depois avulsos). Leva no briefing a armadilha do `[:n]`.

## Estrutura do código

Ficheiro único, `radar.py`, com quatro dependências: `flask`,
`requests`, `pypdf` e `cryptography` (cresceu passado das 600 linhas
originais, mas continua um ficheiro só). Blocos, por ordem no ficheiro:

- configuração e base de dados, `CONFIG_INICIAL`, `iniciar_db`
- leitura das capturas, `carregar_curl`, `parse_curl`, que entende os
  formatos bash e cmd
- reparação de filtros e limpeza do corpo, `repara_filtros`,
  `limpa_resultados`
- leitura da resposta, `campo`, `anuncios_da_resposta`
- detalhe, `seccoes_do_texto`, `valor_de`, `campos_do_detalhe`,
  `ler_detalhes` (com rede), `reparsear` (sem rede)
- documentos, `obter_documentos` e os `_pecas_*` por plataforma
- recolha e gravação, `recolher`, `guardar`, `verificar`
- dicionário de CPV, `importar_cpv_dict`, `cpv_por_termo`
- agendamento, `relogio`, com recuperação de horário falhado
- painel Flask, `condicoes` traduz os filtros em SQL; rota `/cpv.json`
  alimenta a árvore de CPV, a árvore em si é montada em JS no browser,
  dentro do `<script>` no fim do `PAGINA`
- quadro (kanban), `QUADRO_PAGINA`, `cartao`, rotas `/quadro*`

Tabela `anuncios`: `ref` é chave primária e é o número do anúncio, o que
serve de deduplicação. Campos `cpv`, `prazo`, `preco_base`, `plataforma`,
`detalhe_lido`, mais `texto` (o anúncio inteiro), `pdf_url`,
`link_pecas`, `docs_estado` e `fase_id`. Estados: `novo`, `interessa`,
`descartado`. Tabelas `fases`, `etiquetas`, `anuncio_etiquetas` para o
quadro, e `documentos` para o índice dos ficheiros em disco.

As migrações de esquema estão em `iniciar_db()`, com `PRAGMA
table_info` + `ALTER TABLE` só se a coluna faltar. Correm sempre, não
fazem nada se já estiver tudo lá — é seguro chamar a qualquer momento.

O enriquecimento corre a seguir a cada verificação, 40 anúncios de cada
vez, com um segundo de pausa entre pedidos. Configurável em
`detalhes_por_volta`.

## Coisas a saber antes de mexer

A pasta está no ambiente de trabalho, dentro do OneDrive. A sincronização
pode bloquear o `radar.db` durante a escrita. Se aparecerem erros de base
bloqueada, é isto, e resolve-se movendo a pasta para fora do OneDrive.

O painel pagina a lista a 20 por página (`POR_PAGINA_LISTA`; já esteve
limitado às primeiras 500 linhas). A base não tem limite.

Python 3.14 instalado pela Microsoft Store. O `flask.exe` fica fora do
PATH, o que é indiferente porque o arranque é por `python radar.py`.

O servidor de desenvolvimento do Flask, no Windows, às vezes deixa duas
instâncias ligarem-se à mesma porta 8765 sem se queixar (`SO_REUSEADDR`),
e as respostas passam a vir ora de uma ora de outra, de forma imprevisível
— sintoma: mudas o código, reinicias, e o painel continua a comportar-se
como a versão antiga. Se isto acontecer, `Get-NetTCPConnection -LocalPort
8765` mostra os PIDs a ligar; mata-se os dois e arranca-se de novo, um
de cada vez.

## O que fica de fora, e porquê

**Correcção, 27 de agosto de 2026.** Esta secção dizia que o pedido de
acesso à API do BASE ao IMPIC "está por submeter". Está errado: o Afonso
**submeteu-o pelo helpdesk e nunca obteve resposta**. Fica registado, e
fica também que **deixou de ser caminho crítico** — o dump semanal do
dados.gov dá os mesmos dados sem chave, sem sessão e sem depender de
ninguém responder. Ver a secção do corpus de contratos.

O que aqui se dizia sobre cobertura estava certo na conclusão e errado
na premissa. A premissa era que abaixo dos limiares há anúncios que só
o BASE publica. **Não há.** Abaixo dos limiares não existe anúncio
nenhum: ajuste directo e consulta prévia são por convite, e o
procedimento só se torna público como **contrato celebrado**, depois de
estar tudo decidido. Medido no dump de 2026: 84,6% dos contratos
(134 242 de 158 725) nunca tiveram anúncio, e valem 49% dos 13,98 mil
M€ do ano. Não são oportunidades a que se possa concorrer — são o
retrato de quem ganha o quê.

O TED foi implementado e depois retirado, por decisão do Afonso: o que
vai ao TED de entidades portuguesas sai também no DR. Fica a nota de que
o TED é a única fonte para Espanha, mercado onde a empresa está a
qualificar-se, e que a API v3 do TED é pública e sem chave.

O radar já traz as peças do procedimento (Programa de Concurso, Caderno
de Encargos, anexos) em ~90% dos casos — ver "A ficha do anúncio e as
peças do procedimento" — nas quatro plataformas que aparecem na base
(acingov, vortal, anogov, compraspt), o que cobre ~99% dos anúncios que
indicam plataforma.

A sonda (`sonda.py`, `sonda.bat`, `sonda.txt`, `sonda_detalhe.html`) foi
apagada: respondia a duas perguntas — se a pesquisa aceitava termo vazio
e de onde vinha o CPV — ambas respondidas há muito e documentadas aqui.

A pen como «hub» (Python, Node, git e chaves partilhados em `D:\comum`)
foi planeada e fechada a 1 de setembro de 2026 sem se construir: das
três vantagens, duas já existiam. Ver a secção própria no fim.

## Olhar para a concorrência — Tendios, 29 de agosto de 2026

O Afonso tem conta na **Tendios Bid** (`bid.tendios.com`, plano
gratuito) e mandou ver o produto por dentro. O registo completo, com
números e provas, está em **`CONCORRENTES.md`** — aqui fica só o que
muda decisões deste projecto.

**O que se confirmou.** Fomos ao mesmo concurso nas duas casas: o
"Fornecimento de sensores para medição de oximetria para a ULS de São
José", publicado a 28/08/2026. Está no radar como `21792/2026` e lá como
`12025626`. **No que é parte L, há paridade** — não se está a perder
anúncios para eles. E o radar corre às 09:00, contra as 10:00 a que eles
revêem o DR.

**A premissa que mudou.** O separador *Fontes* da ficha deles nomeia a
origem: `EU_TED`, `PT_DDR_CPO`, `PT_BG_CPO` e `GLOBAL_VORTAL`. Ou seja,
vão à **plataforma**, não só ao jornal. Daí virem coisas que a parte L
não publica: consultas preliminares de mercado (na base do radar,
`titulo LIKE '%Consulta preliminar%'` dá **zero**) e contratos menores.
Continua verdade que o BASE não traz anúncios novos — isso está medido e
não muda. O que deixa de ser verdade é a frase "não há segunda fonte":
**há, e são as plataformas de onde o `obter_documentos()` já traz
peças**. Fica registado como premissa, não como plano; implementar é
decisão do Afonso, e custa uma recolha nova por plataforma.

**Onde eles se partem, e porque isso interessa.** Três defeitos
encadeados, todos com a mesma raiz:

1. O concurso de cima está lá **duas vezes**, em fichas separadas. A que
   vem da Vortal tem as peças (Programa e CE, Anexo I, ESPD); a que vem
   do DR/TED só tem os anúncios. Quem abre a segunda não vê as peças.
2. A razão: no directório de organismos, "Unidade Local de Saúde de São
   José, **E. P. E.**" e "Unidade Local de Saúde de São José, **EPE**"
   são duas entidades — **com o mesmo NIF, 508080142**, e com 6 137 e
   1 831 adjudicações cada.
3. E propaga-se: no top-5 de adjudicatários de telecomunicações, a MEO
   aparece **duas vezes** (52 e 19, com um nome em maiúsculas e prefixo
   "1 - "). Juntas seriam 71.

Isto é o cenário exacto contra o qual o `chave_entidade()` foi escrito, a
acontecer num produto pago. **A regra de agrupar sempre pelo NIF, nunca
pelo nome, passa a ter um preço medido.** Não se mexe nela.

**A IA deles não lê as peças.** Duas perguntas à "Vera", na ficha, com o
contexto do concurso carregado e ~90 s de espera cada: os critérios de
adjudicação e o prazo de entrega. Nas duas respondeu que *"não foi
possível extrair automaticamente… a partir dos documentos indexados"* e
mandou ler o PDF; na segunda ainda inferiu do título ("pelo título, o
fornecimento decorre durante 2026"). Não é acaso: no painel de segmento,
o gráfico "Evolução dos critérios de adjudicação" diz **"Sem dados
disponíveis"**. Com a ressalva de que a conta é gratuita e "Análise" está
bloqueada — mas a Vera respondeu, logo tem acesso.

**É isto que o `analisar_pecas()` faz e eles não.** É a vantagem mais
defensável que o radar tem, e a razão para não a deixar apodrecer.

**Preços, para dimensionar.** 5 / 37 / 168 / 345 / 589 €/mês, e o
**histórico é vendido a peso**: 3 meses no plano de 5 €, 4 anos só no de
345 € — 4 140 €/ano. O radar tem 66 009 anúncios de dois anos e 1,36
milhões de contratos desde 2020 em disco. Alertas: 5 é o tecto do plano
de 589 €; cá não há tecto.

**Portugal está encaixado à força no produto deles**, e isso é espaço a
ocupar: taxonomia de procedimentos espanhola (*Aberto simplificado
sumário*, *Contrato Menor*, *Instrução interna* — nada de ajuste directo
nem consulta prévia), geografia sem distritos ("Lisboa" devolve uma
entrada do tipo "Cidade"), **pesquisa que não ignora acentos** (`Sao
Jose` → zero resultados; `São José` → 24), tradução automática com fugas
("Avaliações" por adjudicações, "leilões", "Oporto", um modal em
castelhano) e encoding partido nos títulos portugueses.

### O que daqui sai para fazer

Por ordem de valor, com o detalhe em `CONCORRENTES.md`:

1. **Exclusões nos filtros, e escolher como se combinam.** Eles têm
   *Incluídos* e *Excludentes* para palavras-chave e para CPV, mais duas
   opções em português claro — "OU: pesquisa mais ampla" e "E: pesquisa
   mais restrita". Cá é AND implícito, sem exclusões e sem explicação.
   As exclusões são o que corta ruído sem perder cobertura.
2. **Desconto médio por segmento.** Eles mostram, sobre o filtro da
   lista, mín/média/máx do desconto (0,82 / 20,58 / 45,35 %). Sai já do
   que cá há: `anuncios.preco_base` contra o valor adjudicado no
   `contratos.db`. É o que passa o radar de "o que existe" para "vale a
   pena ir". **Depende de ter detalhe lido** — hoje 5 420 de 66 009
   (8,2%), pela decisão já registada acima; sem levantar isso, a métrica
   corre só sobre a janela dos 60 dias. O número de concorrentes por
   concurso, que eles também mostram, **não sai**: o dump do IMPIC não o
   traz. Não prometer.
3. **Taxa de acerto por alerta.** A ficha de alerta deles mostra *em
   curso · guardadas · descartadas · taxa de acerto*. Um alerta com 200
   avisos e zero guardados está mal afinado, e nada cá diz isso. Os dados
   já existem.
4. **Modificações no resumo diário.** O e-mail deles inclui alterações a
   concursos já conhecidos, não só novos — uma prorrogação de prazo vale
   tanto como um anúncio. Toca no `enviar_resumo()`.
5. **Perguntas às peças como configuração.** A automação deles corre
   perguntas editáveis pelo utilizador sobre as peças ("Quais são os
   requisitos técnicos e económicos?", "Que documentos devem ser
   apresentados?") e escreve o resultado em campos do quadro. É a
   arquitectura do `analisar_pecas()` com as perguntas fora do código.

E um punhado de detalhes pequenos que valem meia hora cada — ordenar por
"última alteração significativa", filtrar por data de actualização do
registo, "sugerir uma mudança" na ficha para reportar campo mal extraído,
e desactivar com explicação os campos que não se aplicam à vista (o que
o `filtro_para()` resolve à saída, eles resolvem à entrada, e fica
melhor).

## Vistoria de utilização, 29 de agosto de 2026

Passagem pela aplicação inteira do ponto de vista de quem depende dela
todos os dias, com a base real e o painel a correr: lista, ficha,
alertas, contratos, quadro, calendário, indicadores, árvore de CPV e as
duas exportações. Saíram 31 problemas, e estão todos resolvidos. O
registo fica aqui porque quase todos eram do mesmo tipo — **o ecrã dizia
um número e entregava outro** — e é o tipo de defeito que volta.

### Os quatro que enganavam

**A pesquisa perdia 11% dos resultados por causa dos acentos.** O `LIKE`
do SQLite só baixa maiúsculas de letras ASCII: para ele `Ç` e `ç` são
letras diferentes. Escrever `aquisição` devolvia 25 868 dos 29 058
anúncios que contêm mesmo a palavra, porque 9 383 títulos (14% da base)
estão escritos todos em maiúsculas. Não havia nada no ecrã a dizê-lo.

A correcção segue o caminho que o projecto já tinha para o NIPC: duas
colunas novas, `titulo_norm` e `entidade_norm`, cheias por uma migração
idempotente no `iniciar_db()` com a função `simplifica()` registada na
ligação (`c.create_function`), e a `condicoes()` a procurar aí com o
termo normalizado do mesmo modo. Passou a devolver 29 094.

**Os índices não são opcionais.** As colunas normalizadas ficaram no fim
da linha, depois do `texto` do anúncio inteiro, e chegar lá obrigava o
SQLite a desserializar alguns KB por registo: a pesquisa passou de 0,4 s
para 4,7 s. Com `ix_anuncios_titulo_norm` e `ix_anuncios_entidade_norm`
a consulta varre o índice em vez da tabela (`SCAN USING COVERING INDEX`)
e voltou aos 0,4 s. Um `LIKE` com `%` à frente nunca salta linhas — o
índice aqui serve para **varrer menos bytes**, não para procurar melhor.

**O selector de plataformas dizia `(nenhuma) (56)` e devolvia 60 645.**
Os números do selector contam os anúncios com detalhe lido; o filtro
apanhava todos os que não tinham plataforma, incluindo os 60 589 que
ninguém tinha lido — e sem detalhe lido ainda não há plataforma nenhuma.
São dois baldes: o `SEM_PLATAFORMA` passou a exigir `detalhe_lido=1`, e
o balde que faltava ganhou nome (`POR_LER`) e uma opção no selector.
Qualquer escolha ali filtrava 8% da base e apresentava o resultado como
se fosse a base toda.

**Os contadores dos separadores ignoravam o filtro.** Com CPV 72 posto
diziam "Por ver 66 007 · Todos 66 009" por cima de uma lista de 234 — e
as ligações dos separadores *levavam* o filtro, portanto o número e o
destino do mesmo botão discordavam. Contam-se agora com a mesma
`condicoes()` da lista, sem a parte do estado.

**A árvore de CPV guardava selecções invisíveis.** Marcar um código,
marcar a divisão por cima e desmarcar a divisão deixava a árvore em
branco com o chip a dizer "1 seleccionado" — e o "Aplicar" filtrava por
um código que não estava marcado em lado nenhum. Ao desmarcar tiram-se
agora os descendentes do conjunto. E ao contrário: com uma divisão
marcada, desmarcar um filho lá dentro mexia a caixa e não mudava nada,
porque o filtro não sabe excluir. Essas caixas ficam **trancadas com
explicação** — uma caixa que se mexe à toa é pior do que uma que não se
mexe.

### O ciclo de triagem

**"Voltar à lista" voltava sempre ao princípio.** Estava preso a `/`:
filtrar por CPV, ir à página 7, abrir um anúncio e carregar ali devolvia
"Por ver, página 1, sem filtro". Passou a usar o `referrer`, validado
pelo `volta_a_lista()` — só aceita caminhos desta aplicação que sejam
mesmo listas.

**Cada "interessa" ou "descartar" atirava para o topo.** É POST com
redireccionamento, e a posição perdia-se; no décimo oitavo item isso é
descer tudo outra vez, e como o anúncio triado desaparece do separador
"Por ver", os de baixo sobem uma posição e o clique seguinte cai no
anúncio errado. O `LISTA_JS` guarda o `scrollY` no `sessionStorage` ao
submeter e repõe-no ao carregar.

**Não havia como desfazer um descarte.** Os botões de cada linha eram
sempre os mesmos dois, independentemente do estado: em Descartados o
único caminho de volta era promover a "interessa" e depois "tirar do
quadro". Agora dependem do estado, e a rota `/estado/<ref>/novo` já
existia. No mesmo sítio: clicar "interessa" em quem já estava interessa
voltava a pôr o anúncio na fila das peças e a descarregar tudo outra vez
— o `mudar_estado()` compara com o estado anterior antes de pedir.

### Três trabalhos longos, três comportamentos

"Verificar agora" corria **dentro do pedido**: recolhe páginas com
pausas, lê até 40 detalhes a um segundo cada e ainda passa os alertas —
minutos com a página em branco, sem sinal de que tinha arrancado e sem
nada a impedir um segundo clique de começar tudo de novo. Ao lado, no
mesmo painel, "Actualizar contratos" já corria em thread com o estado à
vista e "Trazer peças" numa fila.

Passou a thread com trinco (`comecar_verificacao()`), com o `verificar()`
a receber um `passo` opcional que diz em que fase vai. A barra lateral
mostra o passo e recarrega-se sozinha; o botão do topo dá lugar a "a
verificar…". O POST responde em 0,2 s. E volta à página de onde se
carregou, em vez de atirar sempre para `/`.

A leitura das peças pelo modelo tinha o mesmo defeito com um comentário
a dizer o contrário ("demora poucos segundos"): são três perguntas e
cada uma espera até 70 s quando bate no tecto por minuto. Foi para uma
fila igual à dos documentos (`pedir_analise()`), e a caixa das peças diz
em que pé vai. O `registar()` ganhou um `quem` explícito porque fora de
um pedido não há cookie para ler e o `quem_sou()` rebentava.

### Números que não batiam certo

- **O funil misturava janelas.** "Entrados (30 dias) 2 476" seguido de
  "Por ver 66 007" de sempre: a segunda barra maior do que a primeira,
  o que num funil é impossível. As quatro barras passaram para a mesma
  janela de 30 dias.
- **Uma percentagem sobre dois casos.** "De tudo o que já triaste, 100%
  ficou como interessa" com n=2. Abaixo de `MINIMO_PARA_TAXA` (20) diz-se
  quantos são e não se calcula taxa.
- **Números sem saída.** "703 por ver com prazo a menos de 10 dias" e
  "3 982 já com o prazo passado" eram texto corrido. São ligações para a
  lista já filtrada, o que obrigou a um filtro por prazo (ver abaixo).
- **Denominadores diferentes lado a lado.** As percentagens das
  plataformas são sobre os 5 492 com detalhe lido e ficavam encostadas a
  um cartão a dizer "Sem detalhe lido 60 589": a única leitura possível
  era a errada. Ganharam uma linha de legenda a dizer sobre o que contam.
- **"Entidades identificadas 137 904"** prometia uma identificação que
  45% delas não tem: 10% dos adjudicatários do dump do IMPIC vêm sem NIF
  e agrupam-se por uma chave feita do nome. Passaram a duas linhas, com
  NIF e só com nome. É também a razão de a Inetum aparecer duas vezes no
  "quem ganha" — uma pelo NIF com 31 contratos, outra pelo nome com um.
  São dados do IMPIC e não há como juntá-los, mas o `liga_entidade()`
  marca as chaves `n:` com **sem NIF**, e uma linha explicada deixa de
  parecer um erro de contagem.

### Filtro por prazo

Depois de entrarem os dois anos de histórico, 4 059 dos "por ver" já
tinham o prazo passado — arquivo, não triagem — misturados com os de
hoje e sem forma de os apartar. A etiqueta vermelha já existia na linha;
faltava poder pedir a lista sem eles. O campo `prazo` aceita `aberto`,
`urgente` e `expirado`, e o `urgente` usa o mesmo `DIAS_URGENTE` que os
indicadores anunciam — **o número mostrado tem de dar exactamente a
lista que a ligação abre**.

### As duas exportações não concordavam uma com a outra

Nos anúncios o preço saía "1.326.675,00 EUR", que o Excel lê como texto
e não soma; nos contratos saía "7546.5", que num Excel português dá
setenta e cinco mil. As datas iam em ISO nos dois — e a regra da casa é
ISO na base e DD/MM à vista, sendo que um CSV é para ver. Há agora um
`numero_csv()` e um `nome_csv()` partilhados: vírgula decimal, sem
símbolo, sem separador de milhares, e o ficheiro com data no nome, que
`concursos.csv`, `concursos(1).csv` e `concursos(2).csv` não distinguem
nada. E a ligação diz quantas linhas é que saem — encostada ao "1–20 de
66 007", exportava as 66 mil sem avisar.

### O filtro único cumpria metade da promessa

A página de alertas diz que "os filtros são os mesmos em toda a
aplicação" e o formulário de criação oferecia **seis dos treze campos**:
não dava para criar ali um filtro por plataforma, por estado, por tipo
de procedimento nem por valor, coisas que se punham nas outras páginas e
se guardavam de lá. Tem-nos agora todos. O `alerta_criar()` deixa passar
o `estado` vazio, pela mesma razão que a `condicoes()` — ausente é "por
ver", vazio é "todos", e sem a excepção escolher "todos" gravava um
filtro sem estado, que é o contrário do que se pediu.

**Duas caixas com o mesmo rótulo que não falavam uma com a outra.**
`ent` (anúncios) e `adj` (contratos) mostravam ambas "Entidade
adjudicante", e o aviso do parcial saía literalmente "entidade Município
de Lisboa — aqui não se aplica: entidade". São agora "Entidade que
publica" e "Entidade que comprou", nas caixas e no `_NOMES_FILTRO`.

**O aviso do parcial vivia num `title`.** A regra é boa — um filtro
nunca se aplica a meio em silêncio — mas o que se via era a palavra
"parcial" em itálico e a lista dos campos só aparecia a quem deixasse o
rato quieto em cima. O filtro em uso mostra agora, por escrito, o que
esta página não aplica.

**Gravar por cima não perguntava nada.** O campo do nome vem
pré-preenchido com o filtro em uso, de propósito, para se afinar; mas
por isso mesmo era fácil afinar, mudar de ideias e substituir outro
filtro sem aviso e sem forma de voltar atrás. Confirma-se, como já se
confirmava apagar uma fase do quadro.

### Detalhes que custavam meio segundo cada

- **Truncagem sem reticências.** Corte a 190 caracteres em 5 418
  anúncios (8%), e o mesmo nos contratos, nos avisos e nas descrições de
  CPV. "…as Base de Dado" lia-se como dado estragado. Há um `corta()`.
- **As contagens das colunas do quadro** eram desenhadas no servidor e
  ficavam como estavam depois de arrastar: duas colunas passavam a dizer
  o contrário do que se via dentro delas.
- **"Tirar do quadro" repunha o estado em "por ver"** — quem lê isso
  espera perder a fase, não a triagem. Chama-se "voltar a por ver" e
  confirma.
- **Renomear a fase submetia no `onblur` mesmo sem alterações**, e o
  nome vazio era ignorado em silêncio no servidor: a página voltava com
  o nome antigo, o que se lê como avaria.
- **O aviso das tarefas do Windows ficava em cache até reiniciar.**
  Correr o `agendar.bat` com o painel aberto deixava o aviso vermelho no
  ecrã, e apagar uma tarefa nunca chegava a ser notado — sendo que é o
  aviso que impede o pior modo de falha desta aplicação. Vale um minuto.
- **A etiqueta "por ver" aparecia em todas as linhas do separador "Por
  ver"**, onde é sempre verdade e portanto não diz nada.
- **A ficha repetia-se:** "Propostas até" na grelha e outra vez na caixa
  preta da direita, o estado no chip e outra vez na grelha. E o subtítulo
  mostrava `/anuncio/21804/2026`, que é para a barra do browser.
- **O critério de adjudicação somava 200%.** O DR põe os subfactores a
  seguir ao factor, depois de um `Subfatores:` sem valor, e iam todos na
  mesma linha com o mesmo peso visual: "Preço 45% · Início 10% ·
  Qualidade 45% · Plano de Trabalhos 70% · Memória Descritiva 30%". Os
  dois últimos são subfactores da Qualidade e passaram para dentro de
  parênteses. É o campo que decide se vale a pena concorrer.
- **3 301 páginas e só se andava de página em página.** Há uma caixa
  para saltar, no paginador partilhado.
- **O 404 de um anúncio era uma linha de texto solta** — o único ecrã da
  aplicação que não parecia a aplicação.
- **O rodapé repetia a barra lateral.** A hora da última verificação e as
  horas marcadas apareciam nas duas; o ponto verde/vermelho foi para a
  barra e o rodapé saiu. A caixa "Sou", num produto de um utilizador só,
  ocupava permanentemente o canto para uma escolha que se faz uma vez —
  é um `<details>` fechado.

### O que se decidiu não mexer

A página de contratos continua a não mostrar lista nenhuma sem filtro; os
gráficos continuam a correr sobre o filtro e não sobre o corpus; as
legendas por baixo dos números ficam; o agrupamento por NIF fica; as
ressalvas dos campos calculados ("calculado pela regra supletiva do art.
50.º; confirmar no Programa de Concurso") ficam. São as decisões que
fazem a diferença entre uma ferramenta e uma adivinha, e são exactamente
as que uma arrumação apressada deitaria fora.

Os testes passaram de 264 para 307. Cada classe nova corresponde a um
destes defeitos, com o comentário a dizer qual.

## Segunda vistoria, 29 de agosto de 2026 — catorze problemas, todos resolvidos

Segunda passagem completa pela aplicação, à procura do que a primeira
não apanhou. O padrão novo que saiu dela: **defeito corrigido numa
vista, vivo na vista irmã**. Os três achados mais graves eram todos
reincidências de correcções da primeira vistoria noutro sítio do ecrã.
Estão todos corrigidos, com os testes a passarem de 307 para 340.

### Os dois do corpus, que custavam dinheiro

**A pesquisa dos contratos perdia 11,8%.** O mesmo defeito dos acentos
já corrigido nos anúncios, vivo no separador onde se estuda a
concorrência: `LIKE` cru sobre `objecto`, `adjudicante` e o `nome` dos
adjudicatários. Medido: "aquisição" achava 511 723 de 580 986 contratos
— 69 263 invisíveis, porque o IMPIC escreve muito em maiúsculas e o
`LIKE` do SQLite não baixa o `Ç`. A correcção segue o caminho dos
anúncios: coluna `objecto_norm` cheia por migração idempotente no
`iniciar_corpus()` (com `simplifica()` registada em `liga_corpus()`),
índice para não desserializar a linha inteira, e as caixas de entidade a
procurar nas colunas `*_norm` que já existiam — com o termo normalizado
pela **mesma** norma da coluna (`norma_entidade`, que troca `&` por
" e "). A migração corre no arranque do `main()`, não só na importação:
um corpus já em disco levava a coluna só quando se carregasse em
"Actualizar contratos". A primeira passagem custa ~8 minutos, uma vez.

**O dump do IMPIC vem escapado para HTML — às vezes duas vezes.** 5 998
entidades tinham literalmente `&amp;` no nome ("Ramos &amp; Filhos"), o
painel escapava outra vez ao desenhar ("Ernst &amp;amp; Young" no ecrã)
e procurar "Ramos & Filhos" não encontrava **nada** — o segmento inteiro
das empresas familiares impesquisável. Pior: as chaves `n:` derivadas do
nome sujo levavam um "amp" lá dentro. O `_des_html()` desescapa à
entrada do importador, e uma migração por marca (`html_desescapado` no
`corpus_estado`) repara o corpus existente: texto, colunas normalizadas,
chaves, e `resolver_entidades()` no fim. **Desescapa até estabilizar**:
1 413 adjudicatários vinham escapados duas vezes e uma passagem única
tirava uma capa e deixava a outra — foi preciso a segunda passagem para
o descobrir. Depois da reparação: "ramos & filhos" passou de 0 para 300
contratos.

### A ficha deixou de mentir sobre a leitura

O modelo respondia "não consta" à equipa e a ficha continuava a dizer
"só consta do Caderno de Encargos" — mandava abrir um documento que a
leitura já tinha visto não dizer nada, e parecia avariada exactamente
quando funcionou. "Lido e não consta" e "ainda não lido" são respostas
diferentes; o campo do preço anormalmente baixo já as distinguia e os
outros três (objecto, equipa, documentos) e a nota do local passaram a
fazer o mesmo. A subtileza que o teste antigo apanhou logo à primeira:
uma linha de análise gravada **antes de o campo existir** não o leu, e
"foi lido e não fixa" aí seria mentira ao contrário — daí o
`foi_lido()`, que distingue o campo a NULL (nunca perguntado) do campo
com resposta.

### Números e regras da casa

- **"2 com prazo a menos de 7 dias"** no cartão Interessa, com o
  `DIAS_URGENTE` a 10 e sem ligação nenhuma: um limiar escrito à mão que
  nenhuma lista confirmava. Há agora `janela_urgente()`, usada pelo
  filtro e pelo cartão, e o número abre `/?estado=interessa&prazo=urgente`.
- **O selector de plataformas era o único controlo fora do filtro**:
  com a lista em 118 oferecia "acingov (2 637)". A lista das plataformas
  continua a vir da base toda (para se poder mudar), os números contam
  dentro do filtro sem a parte da plataforma, como os separadores.
- **Datas ISO em três sítios**: o histórico da ficha, a barra do corpus
  e a "última" da barra lateral. Há um `data_hora_pt()` ao lado do
  `data_pt()`; texto livre ("nunca") passa como está.
- **O CSV escrevia `novo`** na coluna Estado — chave interna que nenhum
  ecrã mostra. Sai "por ver", pelo `_NOMES_ESTADO` — o mesmo dicionário
  dos separadores.
- **"Criar filtro" era GET** — escrevia na base contra a regra da casa,
  com um comentário a justificar a excepção — e quando a validação
  recusava, o redirect deitava fora os treze campos, nome incluído. É
  POST, e a recusa leva os campos na query string; o formulário volta
  preenchido (prefill por `request.args`).
- **A régua de quartis com n=3** repetia o mesmo contrato em "mais
  barato" e "25%". `MINIMO_PARA_ESCADA = 8`; a comparação com a mediana
  e a tabela ficam, e dizem sobre quantos contam.
- **"Novos hoje 0 · ~60-70/dia" ao sábado** lia-se como recolha
  avariada; o cartão diz "fim-de-semana: a parte L não publica".

### Silêncios e atritos

- **"limpar" apontava sempre para `/`**: limpar a pesquisa nos
  Descartados atirava para "Por ver". `href_limpar()` mantém o estado —
  o separador é onde se está, não parte do filtro.
- **`de=lixo` esvaziava a lista em silêncio** (texto comparado com
  datas) enquanto o € mínimo com lixo era ignorado — dois silêncios com
  efeitos opostos. `data_de_filtro()` só aceita ISO e as três páginas
  (anúncios, contratos, ficha da entidade) avisam por palavras
  (`avisos_de_datas`): data ignorada, e intervalo invertido — que
  continua a devolver vazio, trocar as datas às escondidas seria outro
  silêncio, mas agora diz porquê.
- **A truncagem crua tinha sobrevivido num sítio**: a tabela da ficha da
  entidade cortava o objecto com `[:130]` a seco ("…CENTRADA NO
  CONHECIME"). É o `corta()`, como no resto.
- **A árvore de CPV enterrava os ramos úteis**: filtrar por "software"
  nos anúncios mostrava dezenas de códigos "(0)" no meio dos que têm.
  Ficam esbatidos (classe `zero` no JS, ao aplicar as contagens) — não
  escondidos, porque a mesma árvore conta contratos no outro separador.

### O que se aprendeu

A lista de defeitos já corrigidos é o melhor gerador de hipóteses para
defeitos vivos: cada correcção da primeira vistoria devia ter sido
procurada em todas as vistas irmãs na altura. E uma reparação de dados
verifica-se **contando o que resta**, não confiando no que se escreveu —
foi a contagem pós-reparação que denunciou o escape duplo.

## Os dois P0 do backlog, 30 de agosto de 2026 — exclusões e homólogos

Primeiro trabalho saído do `BACKLOG.md`: os dois itens P0 da análise
competitiva, feitos e medidos no mesmo dia.

### B01 — exclusões nos filtros (`q_excl` e `cpv_excl`)

Três dos quatro concorrentes observados deixam dizer "sem isto"
(Tendios, SpotGov, Armilar); o radar não deixava, e um filtro largo
obrigava a descartar o mesmo ruído à mão todas as semanas. Agora há
duas caixas novas — "Excluir palavras…" e "Excluir CPV…" — nos quatro
formulários: anúncios, contratos, ficha da entidade e o "novo filtro"
dos alertas. Ambas aceitam vários termos separados por `|`.

Decisões que valem a pena registar:

- **O NOT sobre NULL é NULL.** A exclusão usa
  `NOT (COALESCE(coluna,'') LIKE …)`: sem o COALESCE, excluir "obras"
  escondia também os anúncios ainda sem título normalizado, e excluir o
  CPV 72 escondia os anúncios ainda sem CPV lido — que não são "CPV 72",
  são desconhecidos. Há teste.
- **A exclusão vazia é um não-filtro**, ao contrário do positivo. Um
  `cpv=-` dá `1=0` (mostrar tudo seria fingir que o filtro pegou); um
  `cpv_excl=-` não exclui nada — excluir nada é não excluir. Há teste.
- **O `cpv_excl` é caixa de texto, não árvore.** O modo excluir na
  árvore exigia tri-estado no JS partilhado pelos quatro sítios e
  destrancava os descendentes (`arvoreTrancarFilhos` existe exactamente
  porque "o filtro não sabe excluir" — agora sabe, mas a interacção é
  trabalho a sério). Ficou registado no BACKLOG como reabrível.
- **Herança de graça, confirmada:** filtros guardados, legenda
  ("objecto manutencao · sem elevador · sem CPV 724"), alertas e os
  dois CSV apanharam as exclusões sem uma linha a mais, porque tudo
  passa por `condicoes()`/`condicoes_contratos()` e por
  `CAMPOS_FILTRO`. As três vistas entendem os campos novos — nenhum
  fica "parcial".

Medido na base real: `q=manutenção` 3 781 → 3 616 com
`q_excl=elevador|avac`; `cpv=72` 235 → 225 com `cpv_excl=72400000`;
nos contratos, limpeza (909100) 12 156 → 11 892 sem "escolas" no
objecto. Tempos na casa das dezenas de ms.

### B02 — procedimentos homólogos na ficha do anúncio

A pergunta que a Armilar responde e o radar não respondia: "quanto é
que isto custou da última vez, e quem ganhou?". O histórico por CPV
(`mercado()`) responde ao segmento; a caixa nova "Procedimentos
homólogos" responde ao concurso — contratos da mesma entidade (pela
`chave`, como sempre) cujo `objecto_norm` partilha termos do título.

- `termos_do_titulo()` tira o vocabulário burocrático (`_PALAVRAS_OCAS`:
  aquisição, fornecimento, empreitada, obra, lote…), as palavras com
  menos de 4 letras e os números soltos, e fica com até 6 termos na
  norma do corpus (`simplifica`).
- Com 2+ termos exigem-se **pelo menos 2 em comum**: um só
  ("manutenção") arrastava a manutenção toda da entidade. Ordena por
  termos em comum e depois por data; o próprio anúncio fica de fora
  pelo `n_anuncio`, que é o `ref` do radar.
- A caixa só aparece quando há resultados — o estado do corpus já é
  dito pela caixa do histórico logo abaixo — e diz os termos que usou,
  para se saber porque é que cada contrato lá está. Quando o
  `n_anuncio` de um homólogo existe na base do radar, a ficha dele fica
  a um clique.

Confirmado o caso que motivou o item: "Fornecimento de refeições e
Serviço de bar" (21819/2026) mostra as edições de 2025, 2023 e 2020 —
64 975 €, 65 840 €, 70 730 € — com o vencedor de cada uma, em ~20 ms.
Nas obras municipais os termos de lugar ("negrelos", "roriz") fazem o
trabalho de distinguir a estrada certa.

De caminho, o `[:140]` cru na tabela do `mercado()` passou a `corta()`,
que é a regra da casa.

Testes: `TestExclusoesNoFiltro` e `TestTermosDoTitulo`, 353 no total,
todos verdes.

## Os três P1 do backlog, 30 de agosto de 2026 — renovações, desconto, alterações

No mesmo dia dos P0, os três P1 da análise competitiva. Cada um com o
seu commit, os seus testes e a sua medição.

### B03 — vista "Renovações" (`/renovacoes`)

A pergunta "o que vai renovar no meu mercado?" — o que a Armilar vende
como "Previsão de Contratos" e a SpotGov como "Pipeline Radar". É um
separador novo, entre os contratos e o quadro: contratos do corpus com
o fim estimado numa janela de 3/6/12/24 meses, do mais próximo para o
mais distante, com quem o detém e por quanto.

- **`fim_estimado` é coluna, não expressão**: celebração + prazo de
  execução em dias, enchida pelo importador (`fim_estimado()`, função
  pura com teste) e por migração idempotente no `iniciar_corpus()` (349 s
  uma vez, para 1,36 M de linhas), com índice `(fim_estimado, id)`.
  O dump traz prazos absurdos (um de 365 milhões de dias): esses ficam
  "" em vez de rebentar o calendário.
- **A pergunta vem primeiro**, como nos contratos: 81 827 contratos
  terminam nos próximos 6 meses, e sem CPV ou entidade a lista não
  responde a nada.
- **A janela vai por whitelist** (`MESES_RENOVACOES`), porque entra numa
  expressão de data do SQL. Fora da lista, volta aos 6 meses.
- A vista `renovacoes` entra em `CAMPOS_POR_VISTA` **sem `de`/`ate`**:
  a página já tem um eixo do tempo (a janela) e dois confundiam. Um
  filtro guardado com datas entra na mesma, marcado como parcial.
- A página diz, por extenso, que o fim é **estimado** e que prorrogações
  e cessações antecipadas não constam do dump.

### B04 — desconto sobre o preço base

A validação veio primeiro, como o backlog exigia, e confirmou o risco
anotado: **a média ingénua por linha dá -18,9%** — num procedimento com
lotes, cada linha compara o seu lote com o preço base do procedimento
inteiro. As regras que ficaram, validadas contra 20 casos à mão:

- **Agrega-se por `n_anuncio`** (soma dos contratuais ÷ base) e nunca
  por linha.
- **Ficam de fora**: grupos com a base a variar entre lotes (5 388 — aí
  a base é por lote e a semântica é outra) e grupos com a soma acima da
  base (4 275, ruído). Sobra o conjunto limpo: **97 130 procedimentos**.
- O 7º gráfico do resumo dos contratos mostra a distribuição por
  escalões e a mediana (global 8,7%; CPV 72: 3,4%; limpeza 909100:
  10,5%), e diz quantos procedimentos contam e porquê. Com o índice
  parcial `ix_ctr_desconto`, a consulta caiu de 1,0 s para 0,07 s.
- Na ficha do anúncio, ao pé da régua de preços: desconto mediano da
  entidade neste CPV, só com 5 ou mais procedimentos.

De caminho descobriu-se que o "~800 ms sem filtro" do resumo é número
de outro corpus: com os 7 anos actuais, as cinco consultas antigas
somam ~7 s (ganha 2,1 s, proc 1,7 s, compra e trim 1,1 s cada, escal
0,8 s). O desconto novo custa 65 ms — a lentidão é herdada, não deste
trabalho, e fica aqui anotada como melhoria possível.

### B05 — avisos de alterações

O DR republica anúncios alterados — há um em base com "Descrição das
Alterações: Modificação do prazo para a apresentação de propostas" — e
o radar não olhava duas vezes. Agora olha, com juízo sobre o custo:

- **Só se releem os marcados** (interessa ou com fase no quadro) com
  prazo aberto, até 25 por verificação (`reler_marcados()`,
  `relidos_por_volta` no config). A base toda eram 85 minutos por
  verificação a vigiar o que ninguém quer.
- **A comparação é de valor para valor** (`diferencas_do_detalhe()`):
  prazo e preço base, e só quando há valor dos dois lados. Um campo que
  passa a vazio é o parser a tropeçar num texto reformatado — avisar
  isso era o rapaz que gritava lobo.
- **Reconhecer e enviar separados**, como nos alertas: a fila
  `alteracoes` guarda o que ainda não foi avisado; o histórico da ficha
  mostra "DR · alterou · prazo de propostas: 05/09/2026 → 19/09/2026";
  o resumo diário ganha a secção "Alterados desde a última leitura", e
  o assunto do e-mail diz "· N alterados".
- Ensaiado sobre **cópia** da base (o padrão do ensaio-de-leitura) com
  uma prorrogação simulada de 14 dias: detecta, regista uma vez, e
  reler o mesmo texto não avisa segunda vez.
- **Anulações ficaram de fora**: o formato com que o DR as republica
  está por confirmar — era a metade de confiança média do item, e
  prometê-la sem a ter visto era prometer em falso.

Testes novos: `TestFimEstimado`, `TestEscaloesDeDesconto`,
`TestDiferencasDoDetalhe`, `TestResumoComAlterados` — 376 no total,
todos verdes.

## A coluna do fim, as rectificações e os cinco P2, 30 de agosto de 2026

A seguir aos P1, três pedidos do Afonso e o resto do backlog.

### A tabela dos contratos ganhou o "Fim estimado"

A pedido: a lista `/contratos` mostrava só a celebração. A coluna nova
vem logo a seguir, com travessão quando o dump não traz prazo — um
contrato em curso lê-se pelo fim, não só pelo princípio.

### Anulações e rectificações — a investigação

Sobre 66 081 anúncios (2 anos):

- **Anulações não têm formato.** 3 títulos em texto livre ("ANULAÇÃO DO
  CONCURSO PÚBLICO PARA…"), publicados como anúncio de procedimento
  normal, sem referência mecânica ao original. Não há nada fiável para
  detectar — e um alerta por CPV/palavras já as traz como anúncio novo.
  Fica registado como premissa reaberta se o DR algum dia estruturar.
  (Cuidado com o grep: "CÂNULAS" e "Granulado" contêm "anula" — a
  primeira contagem era falsa; a norma certa é `titulo_norm LIKE
  '%anulacao%'`.)
- **Rectificações são anúncios novos com o original citado no título**
  ("Retificação ao Anúncio de procedimento n.º 19900/2026"): 6 em dois
  anos, 4 com o ref extraível. `ligar_retificacoes()`
  (`PADRAO_RETIFICACAO`, com teste) liga-as ao original: histórico da
  ficha sempre, fila do resumo só quando o original está marcado.
  Idempotente pelo próprio histórico; corre na verificação, ao lado da
  releitura dos marcados.

### B06 — taxa de acerto por alerta

Cada alerta em `/alertas` diz em que estados acabou o que marcou e o
acerto sobre os triados (interessa ÷ triados). Os por ver não contam
para a taxa — ainda não são opinião.

### B07 — E/OU entre palavras e CPV

O selector `op` traduz a booleana para humano, como a Tendios: "palavras
E CPV — mais restrito" / "palavras OU CPV — mais amplo". Por baixo,
`condicoes()` e `condicoes_contratos()` passaram a montar o lado das
palavras e o do CPV como fragmentos (fragmento, valores) e só depois os
juntam — era a única forma de os unir por OR **sem baralhar a ordem dos
placeholders**, e há um teste que conta os `?` contra os valores. No
modo OU, um CPV que não corresponde a nada não acrescenta nada (em vez
do `1=0` do modo E, que continua). O `op` sozinho não conta como
pergunta em /contratos nem como filtro nos alertas — é um modo, não um
filtro. Medido: manutenção E CPV 72 = 46 anúncios; OU = 3 970.

### B08 — leituras das peças configuráveis

`leituras_activas()` põe o `config.json` por cima das `LEITURAS` de
origem — `quais`, `ancoras` (`[[prioridade, regex], …]`) e `instrucao`,
campo a campo, com validação à entrada: um regex que não compila ou um
`quais` desconhecido deixam ficar o de origem. **Uma entrada estragada
nunca desliga uma leitura em silêncio.** O 4.º campo definido pelo
utilizador ficou de fora com registo no BACKLOG: a tabela `analise` tem
colunas fixas e o caso de uso ainda não apareceu.

### B09 — pesquisa nas peças (FTS5)

Índice FTS5 **de conteúdo externo** sobre `documentos.texto` — só o
índice, o texto já vivia na base. Triggers em INSERT/UPDATE/DELETE
mantêm-no em dia; a população inicial é `rebuild` com marca no `estado`
(`fts_povoado`). **Armadilha paga**: num FTS de conteúdo externo, um
SELECT sem MATCH lê a tabela de conteúdo — o teste "está vazio?" via
linhas e saltava a população, e todas as pesquisas davam zero.

No painel é o campo "Procurar nas peças…" (`q_pecas`, só anúncios). O
input entra no MATCH sempre entre aspas: NEAR, AND e * escritos pelo
utilizador são texto, não operadores. E a faixa diz a verdade: a
pesquisa só olha para os anúncios com peças trazidas e com texto (17
hoje) — parecer que pesquisa a base toda seria mentir com uma caixa de
texto. Bónus do tokenizador (unicode61 + remove_diacritics): acentos e
maiúsculas certos sem o defeito do LIKE. "penalidades" acha 13,
"alvará" 2, a 0 ms.

### B10 — seguir entidades

Botão "Seguir esta entidade" na ficha; os anúncios novos das seguidas
entram no resumo diário numa secção própria, com o mesmo
reconhecer/enviar dos alertas e o acervo marcado ao começar a seguir —
com âmbito só dessa entidade, senão engolia as novidades por enviar das
outras. O casamento é pelo NIPC (`anuncios.nif` = chave do corpus), sem
comparação de nomes. Entidades sem NIF (`n:`) seguem-se… não: a ficha
nem oferece o botão, porque não haveria aviso nenhum — oferecê-lo era
prometer em falso. Gestão visível em `/alertas`. Contratos novos das
seguidas ficaram de fora (o corpus é semanal e a ficha já os mostra),
registado no BACKLOG.

Testes: 402, todos verdes. O backlog da análise competitiva está
fechado de P0 a P2; sobram os P3 (cosméticos) e o «Não fazer».

## Os três P3, 30 de agosto de 2026 — o backlog fecha

Com estes três, a análise competitiva de 30/08 está toda implementada
(P0 a P3) ou registada em «Não fazer».

### B11 — o valor de cada fase do quadro

O cabeçalho da coluna diz "2 · 123,4 k€": soma dos preços base lidos,
com o title a dizer sobre quantos anúncios é (`soma_precos_base()`).
Os sem preço lido não contam e di-lo — somar uns e calar os outros
parecia o valor da fase inteira. De caminho pagou-se (outra vez) a
armadilha da precedência do `%`: um `+ valor +` no meio de literais
adjacentes cola o formatador só ao último pedaço — o valor entra sempre
como parâmetro `%s`, nunca por concatenação.

### B12 — fontes com página nas leituras

A premissa por confirmar confirmou-se: o `texto_do_pdf()` já lia página
a página, e passou a juntá-las com `\f` **em linha própria** (colado à
linha seguinte, o `sem_indice()` levava a marca junto com uma linha de
sumário). A parte comum do recorte saiu para `_janelas_do_recorte()`:
o texto que vai ao modelo e as páginas que a ficha declara saem DAS
MESMAS janelas — de outro sítio, a fonte mentia. As fontes da análise
dizem agora "Caderno_Encargos_signed.pdf (pág. 1–5)", por leitura
(objecto e equipa lêem zonas diferentes do mesmo CE, e é isso que se
quer declarar).

Os textos antigos não tinham marcas: reextracção única por marca
(`texto_com_paginas`, 49 s, 56 peças), só dos ficheiros que ainda
existem em disco — apagar um texto bom por já não ter o ficheiro seria
trocar a leitura pela cosmética. Limites assumidos: PDFs de uma página
não têm marca (nem precisam de ponteiro); num ZIP com vários PDFs a
página é do texto extraído, não de cada ficheiro. As páginas aparecem
nas fichas à medida que as leituras forem refeitas pelo modelo.

### B13 — a janela do "urgente" no painel

`dias_urgente()` lê o `config.json` por cima da omissão (10), e lixo,
zero ou negativo voltam à omissão — uma janela de 0 dias esvaziava o
filtro em silêncio. Continua a ser UMA janela: o filtro, os rótulos dos
selectores, a legenda dos filtros guardados, o cartão dos indicadores e
a linha da saúde leem todos daqui (o `_NOMES_PRAZO` deixou de ter o
número cozido a quente do arranque). Edita-se em `/alertas` ("Janela do
urgente", 1–90 dias, validação à vista), e mudar lá muda em todo o
lado. Verificado ponta a ponta: gravar 7 muda o cartão dos indicadores
para "menos de 7 dias"; repor 10 repõe.

Testes: 410, todos verdes.

## A pesquisa nas peças mudou-se para a ficha, 30 de agosto de 2026

Correcção pedida pelo Afonso no próprio dia: o campo "Procurar nas
peças…" não pertencia à lista dos anúncios — lá cobria os 17 anúncios
com peças trazidas contra 66 mil da base, e uma caixa que parece
pesquisar tudo mas pesquisa 0,03% engana por muito que a faixa avise.
O sítio certo é a **ficha do anúncio**, depois de as peças virem:
"procura nas peças DESTE concurso" é uma promessa que se cumpre.

- A caixa vive dentro de "Peças do procedimento", só quando há peças
  com texto; devolve um excerto por documento, com o termo a negrito,
  por ordem de relevância do FTS.
- O `q_pecas` saiu de `condicoes()`, do `CAMPOS_FILTRO` e do
  formulário, com um teste a impedir o regresso — um q_pecas numa URL
  guardada não pode voltar a filtrar em silêncio.
- O excerto é calculado em Python (`excerto_de()`) sobre o texto **sem
  as linhas de índice** e com a procura sem acentos, porque o
  `snippet()` do FTS escolhia a linha do sumário ("Penalidades .......
  7") em vez do corpo. O FTS continua a dizer *que* documentos
  respondem; o excerto diz *onde*.
- Nota assumida no código: o corte do excerto é por posição no texto
  normalizado, e um PDF com ligaturas pode desviá-lo umas letras — é um
  excerto, não uma citação ao carácter.

Testes: 413, todos verdes.

## A pesquisa nas peças foi retirada, 30 de agosto de 2026

O Afonso experimentou a caixa na ficha e decidiu retirar a função, e o
argumento é melhor do que a função era: **as peças só existem depois de
marcar "interessa" ou de as pedir à mão** — ou seja, quando há peças
para pesquisar, a decisão que a pesquisa ajudaria a tomar já foi
tomada. Nem na lista (onde cobria 17 anúncios em 66 mil) nem na ficha a
função pagava o ecrã que ocupava. Saiu tudo: a caixa, o motor
(`pesquisa_nas_pecas`, `excerto_de`, `termos_fts`, `ha_fts`) e o índice
FTS da base (o `iniciar_db()` faz a limpeza, idempotente). Há um teste
a impedir o regresso acidental de meio motor esquecido.

O que se aproveita do trabalho: as marcas de página do B12 no extractor
(eram partilhadas e continuam a servir as fontes com página) e o
registo, no BACKLOG, da versão que o Afonso disse que valeria a pena —
**ver o próprio PDF dentro da aplicação, com pesquisa lá dentro** — com
a decisão explícita de não avançar já. Quando for pedida, o caminho
barato é servir o PDF de `documentos/` num visualizador embebido, que o
do browser já traz o Ctrl+F.

Nota para a próxima vez: entre implementar e retirar passaram-se umas
horas. O custo pequeno confirma a regra de construir fino primeiro —
mas a lição verdadeira é que o B09 tinha o aviso no próprio backlog
("cobertura parcial que exige comunicação honesta") e o que a cobertura
parcial pedia não era comunicação, era outra pergunta: "para que serve
pesquisar no que só existe depois de decidir?". Testes: 405, verdes.

## Saneamento pós-auditoria, 30 de agosto de 2026

A `AUDITORIA.md` do mesmo dia apontou problemas de estado dos dados, de
documentação e de visibilidade de erros; esta sessão corrigiu-os todos
— o registo item a item, com o que ficou por fazer e porquê, está em
**`SANEAMENTO.md`**, incluindo o bloco de decisões que são do Afonso
(cópia externa/remoto git, canal de e-mail, links do resumo, registo da
expiração do token). O essencial:

- **Dados destravados, por migração idempotente com marca** (nunca SQL
  à mão): os 30 documentos presos em `erro: cryptography...` voltaram à
  fila e extraíram todos (`ok` passou de 56 para 86 — a dependência já
  estava instalada); as 12 análises com `modelo` sem fornecedor levaram
  o prefixo `groq:` (antes da cadeia só a Groq escrevia, por isso a
  atribuição não é adivinhada); as chaves `ultimo_aviso*` do esquema
  antigo saíram do `estado`; os índices legados `ix_cpv_c`/`ix_adj_c`
  caíram do corpus.
- **Erro de extracção deixou de ser terminal**: `extrair_textos()`
  retenta tudo o que esteja em `erro:...` sempre que corre — é local,
  sem rede e sem orçamento. "scan" e "não é PDF" são veredictos sobre o
  conteúdo e esses ficam.
- **Os erros invisíveis passaram a ver-se**: `ultimo_erro_relogio`,
  `docs_ultimo_erro` e `analise_ultimo_erro` (agora com data na marca)
  aparecem na saúde dos indicadores, a amarelo; a cópia de segurança
  grava `ultima_copia` (ok/falhou) em vez de um print para consola
  nenhuma, e a linha é vermelha quando a última tentativa falhou.
- **Documentação posta a dizer a verdade**: o topo deste ficheiro, a
  secção da cadeia (que JÁ correu em produção — a base prova-o), o
  LEIA-ME (§14 reescrito: o radar lê as peças e traz o corpus do BASE;
  §12 com a contagem certa de testes; §5 com os filtros todos), e a
  regra nova no CLAUDE.md: quem muda comportamento corrige os números
  da documentação no mesmo commit.
- **Arrumação**: `painel.log`, `__pycache__/` e 4 worktrees antigas
  apagados (o `.gitignore` cobre a reincidência); `radar_chave()`
  deixou de duplicar `simplifica().strip()`; o `if "acin" in alvo`
  passou a `SINONIMOS_PLATAFORMA`, com teste a garantir que um sinónimo
  aponta sempre para uma plataforma da lista; `POR_PAGINA` (lista)
  renomeada para `POR_PAGINA_LISTA`, que colidia com o `por_pagina` do
  config (recolha). A chave `leituras` (B08) entrou no `CONFIG_INICIAL`
  e no LEIA-ME, com exemplo.
- **Um achado de caminho**: o «último recurso do texto todo» da
  detecção de plataforma está morto desde sempre (join de pistas vazias
  é truthy). Ficou no BACKLOG, medido antes de mexido.

Verificado sobre a base real: `--reler` (21,5 s) aplicou as migrações e
as contagens de plataforma ficaram exactamente iguais antes e depois.
Testes: 424, verdes, em ~0,8 s.

## O esqueleto de informação, 30 de agosto de 2026

A seguir ao saneamento, desenhou-se em **`ESQUELETO.md`** a estrutura
de informação que consolida o radar — só estrutura e navegação, sem
código e sem decisões visuais (essas são da fase seguinte, por outra
pessoa, a partir desse documento). O essencial: a navegação passa a
cinco intenções (Triagem, Em curso, Pesquisa, Mercado, Alertas), a
Triagem separa-se do arquivo de dois anos (era a aba de 61 981), os
Indicadores entram pela zona de estado, e das 35 rotas 31 mantêm-se
tal como estão — o problema era a hierarquia, não as rotas.

**As decisões estão todas tomadas** (Afonso, no mesmo dia), e o
documento está reescrito segundo elas — a secção 0 do ESQUELETO
regista quem decidiu o quê. As que mudam mais coisas: as **renovações
fundem-se** nos contratos como modo «ver por: fim estimado» (6.1-A); a
**Triagem mostra a janela de `detalhe_dias`** (11.2-A), o que significa
que esse valor de configuração passa a governar também o que se vê de
manhã, e não só o trabalho de fundo; a **Pesquisa abre em 12 meses**
com interruptor para o arquivo (11.5-B); o **«Verificar agora» fica só
na Triagem** (11.8-A), ao contrário de hoje; e a faixa do CPV e o
selector de procedimento passam a blocos partilhados no andamento 3
(6.3-A, 6.4-A), que é onde se paga a dívida do HTML por concatenação.
Ficam por decidir só os dois motores de filtro, que se mantêm como
estão de propósito (6.2-B).

**Quando isto se escreveu, nada estava implementado** — era proposta
fechada, não código. O **andamento 1 foi implementado a 31/08/2026**
(ver a entrada de diário no fim); os andamentos 2 a 4 continuam por
fazer. O Fluxo B continua dependente da decisão E2 do SANEAMENTO.md, e
a procura directa de entidade ficou no BACKLOG a pedido dele, como
possibilidade registada e não feita.

## O código saiu do PC, 31 de agosto de 2026

Meio dia de decisões do Afonso, sem uma linha de código novo — a
implementação fica para quando ele der luz verde.

- **Há remoto.** `github.com/afonsonp/radarconcursos`, privado
  (confirmado: pedido anónimo dá 404), com os 72 commits empurrados.
  Verificado antes do push que os 46 ficheiros versionados não levam
  capturas, bases, chaves nem peças — o `.gitignore` largo fez o
  trabalho. **Isto fecha metade do R2: o código.**
- **A triagem ainda não saiu do PC**, e ele não tem disco externo. A
  saída decidida é o tamanho: a parte irrecuperável são **8 330
  linhas**, que cabem num ficheiro de texto a viajar no próprio
  repositório. Especificado no BACKLOG como **B15**, por implementar.
  Até lá, o R2 continua vivo para a triagem, que é justamente o que não
  se recupera.
- **O e-mail passou a autenticar** (31/08, 00:38–01:00). A primeira
  tentativa levava a palavra-passe normal da conta e a Google recusava-a
  (535 BadCredentials); o Afonso ligou a validação em dois passos, gerou
  a palavra-passe de aplicação e agora o login SMTP passa. Nota para
  quem repetir: ela funciona **com os espaços dos quatro grupos**, que
  a Google ignora. **Falta o primeiro envio verdadeiro**, que só se faz
  com ordem dele — aí sai mesmo um e-mail.
- **A triagem actual é de teste, e isso muda a urgência.** Aviso dele a
  31/08: os 3 «interessa», os 4 097 descartados e as 4 150 linhas de
  histórico não são trabalho real. O risco estrutural do R2 mantém-se —
  a triagem continua a ser o único dado irrecuperável — mas o custo de a
  perder **hoje** é zero. O B15 fica especificado e sem urgência, com o
  gatilho declarado: a primeira semana de triagem a sério.
- **A frequência de expiração do token não é reconstruível.** Procurada
  a 31/08 a pedido dele, em três sítios: o `resposta_inesperada.txt`
  **nunca existiu** (logo, nunca houve expiração desde que o mecanismo
  existe), as marcas de estado são sobrescritas, e o token é **opaco** —
  não é JWT, não traz validade lá dentro. O que se afirma, medido: as
  capturas são de 23/08 16:26 e ainda funcionavam a 31/08, portanto o
  token dura **pelo menos 8 dias**. É um piso, não uma frequência; o
  número real só aparece com o E4 posto, e é para isso que ele serve.
- **E3 decidido: fica como está.** Os links do resumo continuam em
  `localhost`; o e-mail vale como aviso, e o trabalho faz-se no PC. Sem
  VPN, sem expor o painel.
- **E4 decidido: implementar** o registo da expiração do token. Por
  fazer.
- **Segunda fonte de anúncios aprovada, com âmbito** (BACKLOG **B14**):
  Vortal e acingov, **só para procedimentos que o DR não publica**.
  Fica escrito o que a decisão não apaga: o caminho que hoje existe
  parte sempre de um link vindo de um anúncio do DR — é buscar peças de
  algo já conhecido, não descobrir — e **não se sabe se existe listagem
  anónima** em qualquer das duas plataformas. A primeira tarefa é medir
  isso, não escrever ingestão. Os avisos [LEGAL] [RISCO] mantêm-se.

## Andamento 1 do esqueleto implementado, 31 de agosto de 2026

O primeiro trabalho de código sobre o `ESQUELETO.md`: a navegação por
intenções e a separação da Triagem do arquivo. Zero rotas removidas,
zero fusões, o motor de filtros intacto — como a §10 do esqueleto
manda. Verificado a correr no painel, não só nos testes.

**A navegação passou a cinco itens** (§2): Triagem `/` · Em curso ·
Pesquisa `/anuncios` · Mercado · Alertas. "Em curso" agrupa o quadro e
o calendário (11.4; o quadro abre por omissão), "Mercado" agrupa
contratos e renovações (só na navegação — a fusão em modo é do
andamento 3). As duas vistas de um item só aparecem na barra com o
item aberto, e as migalhas dizem "Em curso › Quadro", "Mercado ›
Contratos". Os **Indicadores saíram da barra** (11.6-A): o ponto
verde/vermelho da última verificação, na barra lateral, é agora a
ligação para `/indicadores` — sem atalho secundário. O **"Verificar
agora" ficou só na Triagem** (11.8-A): a constante
`PAGINAS_COM_VERIFICAR` guarda a decisão, com teste.

**A Triagem abre na janela de `detalhe_dias`** (11.2-A), aplicada POR
CIMA de `condicoes()` — nunca lá dentro, porque o motor serve os
alertas e os filtros guardados (`com_ambito()` / `ambito_da_vista()`;
há teste a guardar a armadilha). Medido a 31/08: **"Por ver" passou de
61 981 para 1 374**; as abas contam dentro do âmbito e do filtro
(interessa 3 · descartados 3 618 · todos 4 995). A página declara a
janela por extenso e leva o filtro em uso para a Pesquisa pela ligação
"ver no acervo completo". Com `detalhe_dias` a 0 a janela desliga-se,
como na rotina — um conceito, não dois.

**Nasceu a Pesquisa** (`/anuncios`, rota nova, decisão 11.5-B): a
lista de sempre, sem o âmbito da Triagem, aberta em 12 meses (32 451
anúncios, 28 351 por ver) com o interruptor **"incluir arquivo"** que
alarga aos 66 081. O interruptor é o campo `arquivo` e entrou em
`CAMPOS_FILTRO` de propósito: um filtro guardado com o arquivo
incluído que o perdesse ao reabrir mostrava menos do que quando foi
guardado. Triagem e Pesquisa partilham a vista `"anuncios"` de
`CAMPOS_POR_VISTA` (uma chave nova partia os filtros guardados) e a
mesma função `_lista_de_anuncios()` — duas cópias divergiam ao
primeiro arranjo. O `/csv` recebe um `ambito` (campo "da vez", não do
filtro) para exportar exactamente o que a lista mostra: "exportar as
1 374 linhas" exporta 1 374; sem `ambito`, as ligações antigas
continuam a exportar o filtro tal e qual.

**Consequências espalhadas, todas com o mesmo motivo** (o número abre
a lista que o confirma, FR-33): os cartões dos indicadores que contam
sobre a base toda (urgentes, expirados por ver) passaram a abrir a
Pesquisa com `arquivo=1` — abri-los na Triagem mostrava menos do que o
número dizia; a ligação "anúncios" dos alertas e a rota genérica da
vista (`ROTA_DA_VISTA`) apontam para a Pesquisa; a ficha do anúncio
pendura-se nas migalhas da Pesquisa e o `volta_a_lista()` aceita
`/anuncios` como lista de volta.

Testes: **446** (424 + 22 novos, um por armadilha verificável), verdes
em ~0,8 s. Verificado no painel a correr: números das abas iguais aos
da base lida à mão, filtro a viajar da Triagem para a Pesquisa, CSV
com âmbito a bater com a contagem da ligação.

## Andamento 2 do esqueleto implementado, 31 de agosto de 2026

Estado, vocabulário e atalhos (§4, §7 e §5 do ESQUELETO), na mesma
sessão do andamento 1.

**Estado (§4): auditado, já conforme.** O saneamento C1/C2 tinha feito
o grosso: a barra lateral só tem o que bloqueia (ponto, "a verificar",
tarefas em falta), os Indicadores têm a saúde completa e o diagnóstico
datado, e não se encontrou estado de item na barra nem estado de
sistema repetido nas fichas. Sem código novo — a auditoria é o
resultado.

**Vocabulário (§7), o que mudou de facto** — muito já estava certo
(o CSV já saía `anuncios-<data>.csv`, "peças" já era o nome na ficha):

- O placeholder da lista dizia "Nome do concurso" — passa a **"Nome do
  anúncio ou objecto…"** (anúncio é o único nome do item).
- Indicadores: "Documentos guardados" → **"Peças guardadas"** — no
  ecrã, "documentos" é só os da proposta.
- "análise" deixou de aparecer no ecrã: o histórico da ficha regista
  **"leitura"** daqui em diante e os registos antigos traduzem-se ao
  mostrar (`_NOMES_ACCAO`), sem reescrever a base.
- A coluna do CSV dos anúncios passou de "Estado" a **"Triagem"**, e o
  selector do formulário de alertas diz "triagem: só os por ver" — o
  nome "estado" reserva-se para sistema e itens.

**Atalhos (§5)** — o Triagem→Pesquisa ficara no andamento 1; agora:

- **Ficha → Pesquisa por CPV**: "ver anúncios deste CPV na Pesquisa"
  no facto do CPV, com todos os estados — fecha o "que mais há disto?".
- **Quadro ⇄ Calendário**: cada cartão e cada linha têm âncora
  (`c-<ref>`) e apontam para o seu par na outra vista. O cartão só
  promete a âncora quando o prazo cabe na janela dos 45 dias — fora
  dela a grade não tem a linha, e havia teste a garantir isso desde o
  primeiro dia.
- **Linha de contrato → ficha do anúncio** (o inverso do B02):
  `refs_com_anuncio()` cruza os `n_anuncio` da página com a base e só
  liga os que existem — sem o crivo, ~474 dos 5 391 comuns davam 404.
- De caminho: o último `[:70]` cru visível (título no calendário)
  passou por `corta()`, como a regra da casa manda.

Testes: **453** (446 + 7). Os atalhos do modo dos contratos e da ficha
da entidade dependem da fusão 6.1-A e ficam com o andamento 3.

## Andamento 3 do esqueleto implementado, 31 de agosto de 2026

As fusões decididas na §6 do ESQUELETO, na mesma sessão dos andamentos
1 e 2. Verificado no painel a correr, com o corpus real.

**As renovações fundiram-se nos contratos** (6.1-A): `/contratos` tem
agora dois modos — **por celebração** (o que já se comprou) e **por
fim estimado** (`?ver=fim`, o que vai acabar). A troca é um par de
abas que leva o filtro inteiro; o modo diz-se **por extenso no título
da tabela** ("Contratos por fim estimado — o que vai acabar até
31/08/2027"), que era a defesa contra o ecrã bifacetado que o custo da
opção A previa. No modo fim: janela 3/6/12/24 meses (whitelist
`meses_pedidos()`, como sempre), ordem do fim mais próximo, colunas
próprias ("Quem tem o contrato"), nota do estimado, e **`de`/`ate`
desactivados com explicação** — vindos de um filtro guardado ficam
postos de lado e uma faixa di-lo, nunca em silêncio (B03/P3).
`/renovacoes` ficou como **redireccionamento** com o filtro atrás:
nenhum filtro guardado nem ligação antiga se parte. A vista de campos
continua a ser `"renovacoes"` — é ela que descreve o que o modo
entende.

**Uma conta só para lista, CSV e gráficos**: `filtros_dos_contratos()`
junta `condicoes_contratos()` ao fragmento do modo
(`condicao_do_modo()`), e é por lá que os três passam — medido no
painel: lista 6 229 contratos CPV 72 a acabar em 12 meses, CSV 6 229
registos (a primeira contagem à bruta deu 6 514 por quebras de linha
DENTRO dos objectos — CSV válido, contagem ingénua), gráficos sobre o
mesmo conjunto. O CSV dos contratos ganhou a coluna **Fim estimado**
nos dois modos.

**Blocos partilhados** (6.3-A/6.4-A): a faixa "Filtro CPV activo" é
uma função (`faixa_cpv_activo()`, servia 4 páginas com 4 cópias) e o
selector de procedimento é outra (`selector_procedimento()`, 3 cópias
→ 1). `caixa_de_filtros()` ganhou o `extra` da vista ("ver=fim") para
os chips não trocarem de modo, e `volta_para()` aprendeu rotas que já
têm `?` — gravar um filtro no modo fim voltava com a URL partida.

**Os dois atalhos que faltavam da §5**: modo ⇄ modo com o filtro
intacto (as abas), e ficha da entidade → "o que está a acabar (fim
estimado)" com a chave dela. A dívida do HTML pagou-se onde a fusão a
amortizava: o formulário, as faixas, a barra do corpus e a paginação
dos contratos passaram a existir **uma vez**; não se fez extracção
além disso.

Testes: **467** (453 + 14), verdes em ~2 s (os novos com base
temporária). Verificado a correr: redirect com filtro, troca de modo,
datas postas de lado declaradas, ligação "anúncio" nas linhas com
`n_anuncio`, atalho da entidade.

## Andamento 4 verificado: o Fluxo B está armado, 31 de agosto de 2026

O andamento 4 revelou-se **verificação, não código**: o Fluxo B já
estava inteiro. Confirmado de ponta a ponta no painel a correr e na
base (só leitura):

- **O canal está pronto.** Conta que envia e destino postos, servidor
  `smtp.gmail.com:587`, palavra-passe de aplicação lida de
  `email_senha.txt` (o login SMTP passa desde as 00:38 de 31/08). O
  ecrã de Alertas mostra a saúde do envio e o botão "Enviar o resumo
  agora" está armado.
- **A entrega automática está desenhada e ligada**: os alertas
  reconhecem na verificação, o relógio envia o resumo uma vez por dia
  a partir das 17:00 (`hora_resumo`), o corpo vai por e-mail E fica em
  `AVISOS.txt`, os links ficam em `localhost` (E3, decidido). Falha a
  sério não marca como entregue — volta a tentar.
- **As três filas estão a zero** (alertas por enviar 0, alterações 0,
  seguidas 0) e nunca saiu resumo nenhum (`ultimo_resumo` sem marca).
  Disparar o envio agora devolveria "nada de novo para avisar" e não
  sairia e-mail — o mecanismo é honesto: só envia com novidade.

**O que falta é só o E2, e é do Afonso**: o primeiro envio verdadeiro.
Sai sozinho na primeira verificação que apanhar um anúncio do alerta
"CPV IT", uma alteração ou uma seguida (a partir da hora do resumo) —
ou à ordem, pelo botão, no dia em que houver conteúdo. Nenhum e-mail
foi enviado nesta sessão.

## Pendências da casa resolvidas: C3, E4 e o fallback, 31 de agosto de 2026

Com o esqueleto fechado, resolveram-se as três pendências pequenas do
registo, por ordem de dependência:

- **C3 — a série dos erros.** Tabela `erros (quando, tipo, texto)` no
  `radar.db`, migração idempotente. `marca_erro()` grava a marca de
  sempre — o ecrã continua a lê-la — MAIS uma linha na série, nos
  cinco caminhos de erro (relógio, peças, leitura, cópia, token). A
  poda no `iniciar_db()` guarda os últimos **200 por tipo**, e há
  teste a garantir que guarda os recentes e que um tipo raro não é
  podado por um tipo falador. Leitura por SQL, como o BACKLOG
  propunha; ecrã fica para quando fizer falta.
- **E4 — registar quando o token expira.** Nos quatro pontos onde a
  expiração se detecta (pesquisa sem JSON, detalhe sem JSON — na
  rotina, na releitura e na leitura ao abrir a ficha),
  `registar_expiracao_token()` grava o momento **e a idade da captura**
  (mtime do `curl_*.txt`) na série do C3 e na marca
  `token_ultimo_erro`, que os indicadores mostram como "Última
  expiração do token". O piso «≥ 8 dias» passa a ter instrumento para
  virar frequência — a série é que a há-de dizer.
- **O fallback morto da plataforma — medido, e depois corrigido.**
  Medição só de leitura sobre a base: dos 56 anúncios com detalhe e sem
  plataforma, 18 têm pistas reais (URLs que não batem em nada — o
  strip() não lhes toca) e **28 diziam a plataforma por extenso no
  corpo do anúncio** ("apresentados através da plataforma eletrónica
  acinGov"), todos acingov, nenhuma menção de passagem. Aplicado o
  `strip()` e corrido `--reler` (5 493 reanalisados em 8,2 s):
  **56 → 28 sem plataforma**. A protecção contra menções de passagem
  continua de pé — pistas reais que não batem em plataforma nenhuma
  continuam a não cair para o texto, com teste.

Testes: **473** (467 + 6).

## B15 implementado: a triagem viaja no repositório, 31 de agosto de 2026

A pendência maior do registo, feita como a especificação mandava:

- **`triagem.jsonl`** — a parte irrecuperável da base num ficheiro de
  texto versionado: das `anuncios` só ref/estado/fase/responsável/
  visto_em das linhas triadas ou com fase/responsável, o `historico`
  inteiro, fases, etiquetas e pares, filtros guardados (com id — o
  `filtro_id` dos avisos aponta para ele), seguidas, e as marcas de
  já-avisado (sem elas o primeiro resumo pós-restauro trazia o acervo
  todo). **Primeiro export: 8 330 registos — exactamente a medição de
  31/08.** Um registo por linha, chaves ordenadas, ordem
  determinística (testada: exportar duas vezes dá o mesmo byte a
  byte) — é o que faz o `git diff` mostrar o que mudou hoje. Escrita
  por temporário + `os.replace`: um export interrompido não fica a
  fazer de cópia.
- **Corre sozinho** a seguir à cópia diária, dentro do `verificar()`
  (uma falha ali regista-se na série de erros e não trava a recolha),
  e à mão por `--exportar-triagem`.
- **`--repor-triagem`** é o caminho de volta, para depois de a base
  ser refeita pela recolha: idempotente (testado — segunda volta não
  duplica histórico nem etiquetas), e um ref que ainda não voltou do
  DR **não se inventa**: fica no relatório final, para se repor outra
  vez mais tarde.
- **A sub-decisão do push fica aberta, como a especificação queria**:
  por agora é manual — cada commit leva o `triagem.jsonl` — e a
  alternativa (tarefa semanal com commit+push automático) é a que
  fecha mesmo o R2. Palavra do Afonso.

Testes: **477** (473 + 4).

## B14 medido: as duas plataformas têm listagem anónima, 31 de agosto de 2026

A investigação que o B14 pedia antes de qualquer código — «existe
listagem anónima? paginada? com data? que campos traz?» — foi feita à
mão, no browser, sem sessão em nenhuma das duas. **Deu «dá» nas
duas**; as receitas completas ficaram na secção B14 do BACKLOG.md. O
essencial:

- **acingov**: zona pública com 598 procedimentos a decorrer, paginada
  a 8 por página, com filtros e um botão «Descarregar Peças» em cada
  linha — mas sem data nem prazo na listagem.
- **Vortal**: pesquisa pública de consultas activas com tudo — datas,
  prazo com contagem, preço base, tipo — e o «Detalhe» entrega
  directamente o `PT1.NTC.x` que a cadeia das peças já usa. **As
  «GovPT - Consulta Preliminar» apareceram logo na primeira página**:
  a premissa do B14 (as plataformas publicam o que a parte L não
  publica) confirmou-se à vista.

**Não se escreveu uma linha de ingestão** — o B14 é explícito: primeiro
a medição, depois uma decisão informada do Afonso, plataforma a
plataforma. O que fica por medir (duplicação com o DR pelo `ref`,
estabilidade dos endpoints, ritmo aceitável) está anotado no BACKLOG.
*(A decisão chegou nessa mesma noite — ver a entrada seguinte.)*

## O registo ficou limpo: E2 disparado, B15 automático, B14 em produção, 31 de agosto de 2026

A ordem do Afonso fechou tudo o que estava aberto, de uma vez.

**E2 — o primeiro resumo saiu mesmo.** «Devemos ter algo agora para
enviar» — e havia: a verificação da manhã tinha posto **1 anúncio** na
fila do alerta CPV IT (o concurso do novo website do INFARMED, SPMS,
400 930 €, prazo 07/09). Disparado pelo botão do painel: **«Resumo
enviado para [e-mail retirado]»**, marcas postas
(`ultimo_resumo` 2026-08-31), `AVISOS.txt` igual ao corpo. Daqui em
diante sai sozinho, uma vez por dia com novidade, a partir das 17:00.

**B15 — o push passou a automático**, como ele mandou («grava logo lá
consoante o uso»): `empurrar_triagem()` corre a seguir à exportação em
cada verificação — commit SÓ do `triagem.jsonl` com mensagem
padronizada («triagem: AAAA-MM-DD HH:MM») e push. O gatilho do push
não é o diff mas os commits à frente do origin: **um push falhado (sem
rede) retoma na verificação seguinte** em vez de ficar para trás em
silêncio — há teste exactamente para isso, com repositórios git
temporários. Sem janela de consola (as tarefas correm em pythonw);
desliga-se com `triagem_no_git: false`. **Isto fecha o R2 por
inteiro.**

**B14 — em produção, com o âmbito estrito dele** («só consultas
preliminares ou algo que não seja publicado no DR; não quero
duplicação»). `recolher_vortal()` corre em cada verificação: pesquisa
pública da Vortal (`SearchTenders`, o endpoint JSON descoberto ao
interceptar a própria página — o corpo é
`{"contractNoticeActive":true,"pageNumber":N,"pageSize":50}`), filtro
país PT + tipo preliminar. **O rótulo do tipo muda com o idioma da
sessão** — «GovPT - Consulta Preliminar» em pt é «Quick Tender GovPT»
em en, verificado item a item — e `TIPOS_PRELIMINAR` aceita os dois.
Cada consulta entra com `fonte='vortal'` (coluna nova, migração
idempotente com DEFAULT 'dr'), ref natural `PT1.NTC.x`,
`detalhe_lido=1`; o INSERT OR IGNORE garante que rever a mesma não
mexe na triagem dela. *(o `detalhe_lido=1` durou um dia: ver «O
detalhe das consultas preliminares», 01/09/2026 — entravam sem CPV
nem NIPC, invisíveis a todo o filtro por código.)* As releituras do DR filtram por fonte; a ficha
diz o que a consulta é e liga à plataforma («Ver na Vortal»); a cadeia
das peças aceita o link público (o PT1.NTC vem às claras — salta-se o
primeiro salto). **Primeira recolha real: 17 consultas** (ULS de Santo
António ×7, Tâmega e Sousa, São José, Coimbra, Lezíria, Cova da Beira,
Litoral Alentejano, municípios de Elvas e Amadora), prazos de 2 a 7
dias, na Triagem no minuto seguinte — pesquisável por «preliminar». A
**acingov ficou de fora**: a listagem pública não distingue tipos sem
abrir os detalhes; alargar é decisão nova.

**11.7-B — a procura de entidade, reaberta e feita**: caixa «Ficha de
entidade» em Mercado + `/entidade/procurar`. NIF vai directo (é a
chave); nome resolve por `entidade_nomes` com `norma_entidade()` —
única abre a ficha («municipio de lisboa» foi directo, verificado),
várias dão escolha, nenhuma di-lo com contexto.

**O visualizador de PDF saiu do «Não fazer»**, a pedido dele: os PDF
das peças abrem em `/peca/<ref>/<nome>`, dentro do painel, com o
Ctrl+F do visualizador do browser a pesquisar lá dentro — o caminho
barato que o BACKLOG guardava. O resto (ZIPs, etc.) descarrega como
antes. *Afinado duas vezes na mesma noite:* no browser do Afonso o
`<embed>` mostrava um cartão «Abrir» que só descarregava — os
cabeçalhos do servidor estavam certos (`application/pdf`, `inline`;
medido), a causa é a definição do Chrome «transferir PDFs em vez de
abrir», que recusa renderizar em embeds. Primeiro a página ganhou o
**texto extraído por páginas** (pesquisável com Ctrl+F, funcione o
visualizador ou não); depois, porque ele quer que **abra sempre**, o
radar ganhou um **visualizador próprio**: as páginas desenham-se no
servidor com o **PyMuPDF** (novo em `libs/` e no `requirements.txt`) e
servem-se como imagens (`/peca-pagina/<ref>/<nome>/<n>.png`, escala
2×, cache de um dia, carregamento preguiçoso). Sem PyMuPDF o código
degrada para o embed com o aviso — nunca rebenta. Verificado sobre o
Caderno de Encargos real do INFARMED: 68 páginas desenhadas, PNG
válido, fora do intervalo dá 404.

*(nota: nesta entrada "Triagem" e "Pesquisa" são as páginas de então —
fundiram-se numa lista só nessa mesma noite, ver a última entrada)*

*E o terceiro afinamento, logo a seguir:* com o visualizador próprio,
o Ctrl+F levava ao bloco de texto e o Afonso queria o resultado **no
PDF**. A página ganhou a caixa **"Procurar no documento"**: a mesma
`search_for` do PyMuPDF que sabe onde o termo está desenha os
**destaques a amarelo nas páginas** (anotação em memória, nada se
grava no ficheiro) e a faixa de resultados lista as páginas com salto
por âncora. Medido na peça do INFARMED: «vigência» → 8 páginas, 10
ocorrências, página com destaque comprovadamente diferente da sem. A
procura é literal como está no documento (acentos contam) e a faixa
di-lo quando não encontra. Testes: **490** (486 + 4, a correr nos dois
Pythons — o da pasta e o do sistema).

Verificado a correr: resumo enviado e filas a zero; consulta
preliminar aberta na ficha (chip «Consulta», «Ver na Vortal», vazio
explicado, e os homólogos da entidade a funcionar por cima); Caderno
de Encargos aberto no visualizador; procura de entidade directa à
ficha. Base a **66 145** (47 do DR de hoje + 17 da Vortal); a Triagem
abre com 1 438 por ver. Testes: **486** (480 + 6; a bateria passou de
<1 s para ~3-4 s por causa dos repositórios git temporários do B15 —
continua sem rede e sem tocar na base verdadeira).

## A lista é uma só: Triagem e Pesquisa fundidas, 31 de agosto de 2026

O Afonso, depois de um dia a usar o esqueleto: «a triagem e a pesquisa
não fazem sentido estarem separados. ambas são a mesma coisa. em cima
devem [estar] por ver, interessado, abandonado, todos. todos os
anúncios que já não é possível responder devem estar nos abandonado.»
É ele a rever as suas decisões 11.2-A e 11.5-B com o critério que só o
uso dá — as duas páginas separadas duraram exactamente um dia.

**O que ficou:** a lista vive em `/` com o item **Anúncios** na barra
(quatro itens agora); `/anuncios` redirecciona com o filtro atrás. As
quatro abas fazem o trabalho que as duas páginas faziam, com o recorte
em `condicao_da_aba()` aplicado POR CIMA do motor (`com_recorte()` —
a armadilha de sempre mantém-se: nada disto entra em `condicoes()`,
que serve os alertas):

- **Por ver** = novo E ainda respondível — prazo aberto, ou, sem prazo
  lido, publicado dentro de `detalhe_dias`. A antiga janela da Triagem
  virou parte da definição da aba.
- **Interessados** = todos os interessa. Um interessa com prazo
  passado é trabalho em curso (proposta entregue, à espera) e não se
  esconde — a regra antiga do `--descartar-expirados` sobrevive aqui.
- **Abandonados** = abandonados à mão + os por ver que já não são
  respondíveis. **É recorte de leitura, a base não muda**: um
  expirado rectificado com prazo novo volta sozinho ao por ver, e não
  há fila nenhuma a limpar (o alerta «expirados por ver» dos
  indicadores morreu por definição da aba).
- **Todos** = sem recorte.

Medido na base real — a partição é exacta: **1 392 por ver + 4
interessados + 64 749 abandonados = 66 145**. O CSV com `ambito` põe o
mesmo recorte da aba (o por ver exporta 1 392, não os expirados); o
interruptor do arquivo caiu (deixou de haver janela para desligar —
um filtro guardado que o tenha fica marcado parcial, declarado); o
vocabulário passou a «abandonar/abandonado» nos botões, etiquetas,
abas, CSV e alertas. O rótulo do grupo continua a ser «triagem» (§7).

Testes: **485** (as classes das decisões da manhã foram substituídas
pelas da lista única, com o porquê nos comentários — reescrever testes
quando a decisão muda é o custo certo; «simplificá-los» de volta é que
não).

## Desenho visual: direccao "ardosia e ambar", 31 de agosto de 2026

Fase de desenho puro, a seguir ao esqueleto: cor, tipografia,
espacamento, densidade e composicao das paginas. **Zero mudancas de
estrutura de informacao, rotas ou comportamento** -- a estrutura fechou
nesse mesmo dia e nao se reabriu aqui.

**As duas escolhas do Afonso**, por reaccao a arranjos postos lado a
lado num canvas (o metodo dele: nao articula o que quer, escolhe entre
opcoes contrastantes):

- **Composicao da ficha: C, "dossier com indice"** -- uma coluna so,
  tudo aberto por ordem de leitura, com um cabecalho fino (titulo,
  prazo, interessa/abandonar) e um indice presos ao rolar. As
  alternativas eram A ("mesa de decisao": faixa no topo e mercado
  fechado) e B ("coluna do processo": duas colunas com a direita fixa).
  Sacrificio assumido: nada fica lado a lado, a pagina e comprida e
  ganha-se pelo indice. **Com uma afinacao dele: o leitor de PDF abre
  dentro da ficha, por baixo do bloco das pecas** -- a rota
  `/peca/<ref>/<nome>` mantem-se para ligacoes directas.
- **Direccao visual: 1, "o actual afinado", com a paleta 3 "ardosia e
  ambar"**. Nao muda a identidade (barra escura, Archivo + JetBrains
  Mono) -- muda a leitura. As outras direccoes eram "imprensa" (serifa
  Newsreader, reguas em vez de caixas) e "instrumento" (IBM Plex,
  denso). Das quatro paletas propostas sobre a direccao 1 escolheu a
  fria: barra ardosia azulada, papel cinzento-claro, ambar na marca e
  nos prazos que apertam.

**O diagnostico que isto corrige** (fase A0, `design:design-critique`
sobre screenshots de todas as paginas):

- os cinzentos `--t5`/`--t6` davam **2,5:1 a 2,9:1** sobre branco --
  abaixo de AA, e justamente nos textos de 10-11px (contagens, notas,
  datas). A escala nova nao desce abaixo de 4,5:1 **sobre `--papel`**,
  que e o pior fundo;
- a escala tipografica vivia toda entre 10 e 13,5px e a hierarquia
  fazia-se so por peso e cor: numa pagina densa lia-se tudo ao mesmo
  nivel;
- tudo era caixa branca com a mesma borda e a mesma sombra -- um
  filtro, um aviso e o conteudo tinham o mesmo peso visual.

**Regra nova que a paleta traz:** o que e texto usa `--t1`..`--t6`, o
que e decoracao (setas das migalhas, molduras tracejadas, separadores)
usa `--traco` ou `--linha`. Foi a confusao entre os dois que fez
nascer os cinzentos ilegiveis -- um `--t6` escolhido para desenhar uma
seta acabou a escrever contagens.

### A barra lateral passou de 236px para 140px

Pedido dele, e nao e so uma largura: **encolher sem refazer o
espacamento e o que a partia**. Ele proprio a puxou para 121px no
canvas e com o padding antigo (22px de cada lado) sobravam 77px de
conteudo. A 140 com padding de 12 sobram 116, e tudo dentro tem
medidas proprias: a marca numa linha, as contagens do acervo **uma por
linha** (`acervo` passou a separa-las com `<br>` -- numa linha so, "66
205 anuncios · 1 363 300 contratos" partia em qualquer sitio menos nos
que interessam), a caixa da verificacao sem fundo proprio e o "quem
esta a trabalhar" reduzido a inicial mais nome. A zona principal ganha
96px de largura util.

Os pontos verde/vermelho da ultima verificacao deixaram de ser cores
fixas no Python: sobre a barra escura o contraste conta ao contrario,
e o verde da paleta clara desaparecia la. Passaram a `--ok-claro` e
`--mau-claro`, que so existem para esse fundo.

### Pagina a pagina, o que mudou

Um commit por pagina ou bloco coerente, com os testes verdes e uma
passagem pelo browser antes de cada um -- sempre com os dois anuncios
reais: o **21925/2026** (INFARMED, o mais denso que ha) e a consulta
**PT1.NTC.3784180**, que quase nao tem nada. A composicao tinha de
aguentar os dois extremos.

- **Anuncios.** O "interessa" passou a contorno verde: cheio, vinte
  deles puxavam o olho todo para a coluna das accoes e os titulos --
  o que se le para decidir -- ficavam atras. O prazo saiu das
  etiquetas e subiu a numero forte por cima do preco. A coluna da
  data saiu: repetia "31 AGO" vinte vezes com peso de titulo, e a
  publicacao passou a nota ao lado da entidade. As tres caixas do
  filtro continuam tres, mas as duas de baixo baixaram de nivel.
- **Ficha.** Ver a seccao acima -- e o trabalho maior desta fase.
- **Peca.** O visualizador passou a funcao partilhada
  (`visualizador_de_peca`), usada pela rota `/peca/<ref>/<nome>` e
  pelo bloco dentro da ficha. **Armadilha paga:** o formulario da
  procura e um GET, e um GET substitui a query string INTEIRA pelos
  campos do formulario -- procurar dentro da ficha devolvia a pagina
  com o leitor fechado, porque o `peca=` desaparecia. Os campos que
  tem de sobreviver a procura viajam como `<input type=hidden>`.
- **Em curso.** As colunas do quadro eram `--linha2` sobre `--papel`,
  dois cinzentos a um passo um do outro: o quadro lia-se como cartoes
  soltos, e a coluna E a informacao. O cabecalho da coluna passou a
  duas linhas (o nome partilhava 282px com a contagem, a soma e o
  apagar, e saia "A preparar pr"). No calendario, o dia -- o eixo da
  pagina -- estava em `--t4`; e as pilulas cortavam sem reticencias,
  "Por analis", que e dado estragado e nao texto cortado.
- **Mercado.** Na tabela dos contratos o objecto era a coluna mais
  apagada, com os nomes de entidade (ligacoes azuis) a puxar o olho
  primeiro: invertido pelo peso, sem tirar o azul. Nos graficos o nome
  levava 1.4fr contra 2fr da barra e saia "Capgemin…" em quase todas
  as linhas. E no modo "por fim estimado" os campos `de`/`ate`
  desactivam-se com a explicacao no `title`, mas eram desenhados como
  os outros: so quem tentasse escrever la e que descobria.
- **Indicadores.** A linha do ultimo erro **transbordava da caixa** --
  frases de 80 caracteres em mono com `flex:none` no valor -- e o
  rotulo partia palavra a palavra a tentar dar-lhe espaco. O funil e as
  fases do quadro passaram de cinco cores sem sistema a um degrade de
  azul: sao passos de um caminho, nao categorias, e duas das cores
  antigas vinham das cores de estado (a coluna "Submetido" a laranja
  parecia um aviso).
- **Alertas.** Os treze campos do filtro novo ganharam um degrau de
  largura e leem-se em linhas de tres. Os campos sao os mesmos e pela
  mesma ordem.

### Acessibilidade, medida e nao estimada

A verificacao correu como script no browser sobre as **nove paginas**:
para cada elemento com texto, a cor calculada contra o primeiro fundo
opaco acima dele, com o limite de AA (4,5:1, ou 3:1 em texto grande).

Antes: os `--t5`/`--t6` davam **2,5:1 a 2,9:1**. Depois da primeira
passagem sobravam **seis** falhas, todas entre 4,1 e 4,43 -- e todas
onde a intuicao nao chega: a pilula do calendario sobre o proprio
fundo, o rotulo da mediana sobre azul-claro, o "x" de apagar fase, o
"…" do corte da paginacao. **Hoje o pior caso das nove paginas e
4,66:1.** A licao e o metodo: um contraste marginal nao se ve, mede-se
-- e mede-se sobre o fundo real, nao sobre branco.

O foco de teclado passou a ser um so em toda a aplicacao
(`:focus-visible`, contorno de 2px; ambar sobre a barra escura, azul
no resto). Havia **quatro** campos a desligar o contorno para pôr uma
pista propria -- a pista fica, o contorno volta, e so para quem navega
por teclado.

### O que se verificou a funcionar, e nao so a parecer bem

Arrastar um cartao entre fases (move e as contagens acompanham ao
vivo), o rolo horizontal do calendario (2 600px de conteudo em 829),
as tabelas largas a rolarem dentro da caixa sem a pagina rolar de
lado, o leitor da peca a abrir dentro da ficha, e a procura
"vigencia" a devolver 8 paginas com o destaque amarelo desenhado no
sitio certo.

**Nao entrou nesta fase, de proposito:** `etiqueta_prazo()` usa um `7`
escrito a mao para a cor amarela, enquanto a janela do "urgente" e
`dias_urgente()` (10 por omissao, editavel em /alertas) -- um anuncio
a 9 dias aparece verde na lista e conta como urgente nos filtros e nos
indicadores. E a armadilha registada no CLAUDE.md, esta viva, e e
correccao de comportamento: fica para trabalho proprio.

### E o que a composicao em dossier obrigava a resolver

Com tudo aberto por ordem de leitura, os campos longos lidos das pecas
deixam de ter onde se esconder -- e eram eles o achado central do
diagnostico: **a "Equipa" deste anuncio do INFARMED sao 3 200
caracteres em 146 linhas**, e saiam como um bloco corrido no mesmo
corpo e peso do resto do essencial. Oitenta por cento do rolo da ficha
lia-se ao mesmo nivel.

`desenha_valor()` da a cada valor a forma que o texto **ja tem**, sem
lhe mudar uma palavra: blocos separados por linha em branco com pares
"Chave: valor" viram um cartao por perfil (21 neste anuncio, em tres
colunas); linhas comecadas por travessao viram lista; "1. Nome"
seguido de detalhe vira lista numerada. O que nao tiver forma nenhuma
sai como sempre saiu.

A guarda que interessa e a ultima: **uma frase com dois pontos a meio
nao e um par**. Sem ela, "Presencial, nas instalacoes do Parque de
Saude de Lisboa" virava uma linha de tabela. O `RX_PAR_PERFIL` exige
uma chave curta (2 a 40 caracteres, sem dois-pontos la dentro) e ha
teste a segurar cada uma das tres formas e o texto corrido
(`TestDesenhaValor`, 7 testes). A ficha do INFARMED encurtou 12%.

**Armadilha paga outra vez, a mesma do costume:** a pagina nao mostrava
nada de novo depois de tudo estar escrito e testado. Nao era o codigo
-- eram **duas instancias na porta 8765**, a responder a vez, com a
mais velha a servir o CSS de antes (SO_REUSEADDR no Windows, ja
registado aqui). Matar "o processo que esta na porta" nao chega:
mata-se **por caminho** -- todos os python que corram da pasta do
radar -- e confirma-se que a contagem ficou em **uma** antes de
acreditar no que o ecra mostra. E compara-se a hora de arranque do
processo com a da ultima gravacao do `radar.py`: foi essa comparacao
que denunciou isto, com o processo a arrancar quatro minutos ANTES do
ficheiro que devia estar a servir.

*(nota de metodo, tambem ja registada e tambem repetida: os heredocs
do Bash comem um nivel de escape neste ambiente. A classe de testes
nova saiu com as quebras de linha por expandir a primeira vez, e este
paragrafo saiu com um caminho do Windows estropiado -- ambos por
escrever codigo com contrabarras dentro de um heredoc. Para isso
usam-se as ferramentas de escrita, como o CLAUDE.md ja dizia.)*

### A aplicacao passou a usar o ecra que tem, 1 de setembro de 2026

Pergunta do Afonso: «e possivel fazermos com que a aplicacao se adapte
ao ecra onde esta?». Medido antes de mexer, em nove paginas e sete
larguras (768 a 2560), e o resultado dividiu-se em dois:

- **o ecra pequeno ja estava resolvido**: nada rolava de lado, nem a
  768px -- as tabelas largas ja rolavam dentro da propria caixa e as
  grelhas ja quebravam;
- **o ecra grande e que estava por usar**: com o `.larg` preso em
  1240px, sobravam **530px vazios num monitor de 1920 e 1170 num de
  2560** -- quase metade do ecra. A tabela dos contratos ficava a 1240
  com a coluna do preco fora da vista, num ecra onde cabiam as sete
  colunas a folgar.

O principio da correccao: **a largura a mais da mais informacao, nao
linhas de texto mais compridas.** Uma linha de 1500px nao se le, por
isso o que cresce sao as grelhas e as tabelas, e o texto corrido guarda
a sua medida.

- `.larg` sobe de 1240 para 1560, e a folga lateral do corpo passa a
  `clamp(20px, 2.4vw, 44px)` -- acompanha o ecra em vez de ser sempre 34;
- os KPI dos indicadores e os graficos dos contratos deixam de ter um
  numero fixo de colunas (`repeat(auto-fit, minmax(...))`): os KPI
  passam de 2 colunas a 768 para 4 esticados a 1920; os graficos de 1
  para 3. Os perfis da ficha, que ja eram `auto-fill`, vao de 2 a 768
  ate 6 a 1920;
- o texto corrido ganha tecto proprio em `ch` (86 no essencial, 88 nas
  listas). **Medido: fica em 643px de 1366 a 2560**, enquanto a tabela
  do mercado na mesma ficha vai de 1112 para 1522. E exactamente a
  divisao que se queria;
- saiu uma regra morta: o `@media (max-width:1100px)` ainda continha
  `.ficha`, classe que deixou de existir quando a composicao passou a
  dossier.

Verificado depois: **nenhuma das nove paginas rola de lado nem
transborda, em nenhuma das seis larguras** de 768 a 2560. O tecto de
1560 e deliberado -- num monitor de 2560 sobram 850px de margem, que e
o que uma aplicacao de trabalho centrada deve fazer; o que nao devia
fazer era desperdica-los a 1920, onde agora sobram 210.

## O arranque de 39 segundos: uma migração sem índice, 1 de setembro de 2026

Pergunta do Afonso: «o iniciar.bat está a demorar muito a arrancar
porquê?». A resposta estava numa linha de SQL — e no disco onde isto
vive.

**A causa.** O `iniciar_corpus()` corre a cada arranque do painel e
tinha quatro migrações do género «enche o que falta». Três delas têm
índice que responde ao `IS NULL` e custam zero:

| verificação | plano | custo |
|---|---|---|
| `objecto_norm IS NULL` | COVERING INDEX `ix_ctr_objecto_norm` | 0,00 s |
| `fim_estimado IS NULL` | COVERING INDEX `ix_ctr_fim` | 0,00 s |
| `adjudicante_chave IS NULL` | COVERING INDEX `ix_ctr_chave` | 0,00 s |
| **`n_adj IS NULL`** | **SCAN contratos** | **38,92 s** |

O `n_adj` era o único sem índice. Resultado: 1 363 300 linhas, 421 949
páginas, **1,65 GB varridos a cada arranque** — para encontrar **zero
linhas por encher**. A migração só servia corpora anteriores à coluna;
o importador enche-a sempre, por estar no `COLS_CONTRATO` com
`max(1, len(ganhadores))`.

**A correcção** é a que o ficheiro já usava noutro sítio: marca no
`corpus_estado` (`n_adj_cheio`), como o `html_desescapado`. Medido no
corpus verdadeiro: `iniciar_corpus()` passou de **18,66 s** (o
arranque que ainda paga o varrimento e põe a marca) para **0,02 s** e
depois 0,00 s. A frio eram 38,9.

Preferiu-se a marca ao índice parcial porque o índice ainda obrigava a
uma varredura para o construir, e a coluna nunca mais volta a ficar a
NULL.

### Porque é que a medição a quente escondia isto

A primeira medição do mesmo varrimento deu **1,14 s** — suficiente para
o descartar e ir procurar noutro lado (threads de fundo, instâncias a
mais na porta, corrida do browser). Era uma medição a quente: uma
consulta exploratória minutos antes tinha posto a tabela na cache do
Windows. Mais tarde, com a cache já despejada, a consulta idêntica
sobre os mesmos dados deu **38,92 s**.

A lição, que vale para qualquer queixa de «o primeiro arranque é
lento»: **um tempo medido depois da nossa própria exploração não é
prova** — fomos nós que aquecemos exactamente aquilo por que o
utilizador espera. Ou se mede a grandeza independente da cache (bytes
movidos: `GetProcessIoCounters`), ou se mede o dispositivo por baixo
(`FILE_FLAG_NO_BUFFERING`), ou se repete a medição mais tarde.

### E o disco por baixo: isto corre de uma pen

O `D:` não é o SSD interno. É um **Samsung Flash Drive, BusType USB**.
Medido com leitura sem cache:

- **408 MB/s** em sequencial puro;
- **~42 MB/s efectivos** numa varredura de páginas de 4 KB, que é o que
  o SQLite faz — daí 1,65 GB darem 39 s e não 4;
- **8,7 ms para abrir um ficheiro pequeno a frio.** Dos 459 módulos que
  o `radar.py` carrega, **216 vêm de `libs/` como ficheiros soltos** (a
  stdlib está zipada no `python314.zip`, essa é barata). São segundos
  de arranque só em abrir ficheiros.

Sem saber isto, todos os números seguintes eram interpretados na escala
errada. Passou a regra do CLAUDE.md: confirma em que disco o código
está antes de o culpar.

### Os outros dois custos do arranque, medidos e não corrigidos

Ficam registados; nenhum foi mexido nesta sessão.

1. **O browser abre antes de o Flask atender.** O `main()` chama
   `webbrowser.open()` e só depois `app.run()`. Medido: browser aos
   0,98 s, porta a responder aos 1,91 s. Se o browser já estiver
   aberto, apanha a porta fechada e é preciso recarregar à mão. A
   correcção é abrir o browser de um `threading.Timer` depois do
   `app.run()` ter arrancado.
2. **Um slot falhado dispara a verificação inteira no arranque.** O
   `relogio()` corre o ciclo à cabeça: se um slot do dia não correu,
   chama `verificar()` logo — cópia `VACUUM INTO` de 93 MB para a pen,
   `git push` da triagem (que está a falhar, `ultimo_erro_triagem_git`
   = `remote rejected`), e a recolha toda. Os slots de 31/08 levaram
   ~5 minutos cada.

Arranque a quente, sem nada disto: **2,5 s** do duplo-clique à
primeira página (`import radar` 0,24 s, `iniciar_db` 0,00 s,
`iniciar_corpus` agora 0,00 s, Flask de pé a 1,91 s, primeira página
servida em 0,41 s).

**Testes:** `TestNAdjEnchePorMarca`, seis, sobre um `CorpusTemporario`
novo (o irmão da `BaseTemporaria`, para o `contratos.db`). O que
seguram: que a migração continua a encher o corpus antigo, que sem
adjudicatários vale 1 e não 0 — é divisor no gráfico de quem ganha —,
que **na segunda vez não faz nada** (é este o arranque de 39 s), e que
o `n_adj` continua no `COLS_CONTRATO`, que é o que torna a marca
segura. Os testes passaram de 492 para 498.

## Os outros dois custos do arranque, e os erros que ninguém via, 1 de setembro de 2026

Continuação directa da entrada anterior. A varredura de 1,65 GB era o
custo grande; ficavam dois mais pequenos, medidos e registados nessa
sessão mas não corrigidos. E a diagnosticar um deles apareceu um
terceiro problema, que não era de arranque nenhum.

### O browser abria antes de haver servidor

O `main()` chamava `webbrowser.open()` e só depois `app.run()`. Medido:
o browser recebia o endereço aos **0,98 s** e a porta só respondia aos
**1,91 s**. Com o browser já aberto — que é o caso normal — o separador
novo apanhava a porta fechada e ficava num erro de ligação que só um F5
tirava. Lia-se exactamente como «o radar demora a arrancar».

Passa a `abrir_no_browser()`, em thread, a esperar pela porta
(`porta_atende()`) em vez de adivinhar um tempo — o arranque varia com
o disco, e este corre de uma pen. Se ninguém atender dentro de 15 s não
abre nada: o endereço já foi impresso na consola, e uma janela de erro
não ajuda ninguém.

**A armadilha do Windows, que custou um teste intermitente.** Ligar a
uma porta onde ninguém fez `bind` é recusado logo. Ligar a uma porta
com `bind` feito e **sem `listen`** — que é exactamente o instante em
que o Flask está a arrancar — não devolve recusa nenhuma: bloqueia até
ao timeout e devolve WSAEWOULDBLOCK (10035). O primeiro teste que
escrevi punha um servidor a nascer meio segundo depois e comparava
carimbos de tempo; passou duas vezes seguidas e falhou à terceira.
Um teste de relógio a medir o escalonador não prova nada sobre esta
função: a sonda passou a ser injectável, e o teste responde False,
False, True e conta as sondagens. Cinco corridas seguidas, estável.

### Um slot falhado disparava a verificação inteira, e em silêncio

O `relogio()` chamava `verificar()` **directamente**, por fora das duas
coisas que o botão "Verificar agora" tem: o trinco e o `passo`.

Consequências, as duas reais:

1. Um slot falhado dispara a verificação no **arranque** do painel —
   cópia `VACUUM INTO` de 93 MB para a pen, push da triagem, recolha
   toda, ~5 minutos (os slots de 31/08 levaram 09:00→09:05 e
   17:00→17:04) — e não havia nada no ecrã a explicar a lentidão.
2. O relógio podia apanhar um clique no botão a meio e pôr **duas
   verificações na mesma base**.

Passa por `comecar_verificacao(slot=(dia, hora))`, a mesma porta do
botão. O `slot` é novo e é o que marca a hora como corrida — no fim, e
só se correu bem; se o trinco recusar, o slot fica por correr e
tenta-se no minuto seguinte. **O botão à mão não passa slot nenhum**:
um clique às 15h não pode fazer a verificação das 17h dar-se por feita.

### O push da triagem não estava a falhar — e ninguém podia saber

A marca dizia `ultimo_erro_triagem_git = 2026-08-31 17:00: git push: To
https://github.com/afonsonp/radarconcursos.git ! [remote rejected]…`.
Duas coisas, ambas diferentes do que parecia.

**Primeira: já tinha passado.** A razão completa era `cannot lock ref
'refs/heads/master': is at 95919b5…` — uma corrida entre dois pushes,
transitória. O reflog do `origin/master` mostra `update by push`
sucessivos desde então, o último às 03:02 de 01/09. O mecanismo
recuperou exactamente como o `empurrar_triagem()` diz que recupera: o
commit local fica, e a volta seguinte vê os commits à frente do origin
e volta a empurrar.

**Segunda, e a que interessa: essa marca não aparecia em ecrã nenhum.**
O `linhas_de_ultimos_erros()` — que nasceu no C1 do saneamento
justamente para acabar com os erros que só se viam por SQL — lia quatro
marcas. O B14 e o B15 acrescentaram `vortal_ultimo_erro` e
`ultimo_erro_triagem_git` **depois** desse saneamento e não as ligaram
lá. O C1 tinha-se desfeito por acréscimo: um "remote rejected" esteve
um dia inteiro na base a não existir para ninguém. Passam a seis, e
fica a regra no CLAUDE.md — quem acrescenta um `marca_erro()` acrescenta
o rótulo aqui.

E a razão passou a caber na linha. O git escreve `To <url>` primeiro e
a razão só na segunda linha; com os 80 caracteres da linha dos
indicadores, o endereço do repositório comia a mensagem inteira e
lia-se «git push: To https://github.com/…» — que é precisamente não
dizer nada. O `porque_do_git()` tira a linha do endereço e o `error:
failed to push` final, e junta o resto numa linha só. Nunca devolve
vazio: se só houver cabeçalho, mostra o cabeçalho.

### O parágrafo do topo, outra vez

O «Como está a correr» descrevia a Triagem e a Pesquisa como páginas
separadas — durante o dia inteiro em que já eram uma só. É a segunda
vez que este parágrafo mente, e pela mesma razão de sempre: as sessões
acrescentam secções ao fim e não tocam no topo. Corrigido com números
lidos da base e abas lidas do próprio painel: 66 205 anúncios, 8,5% com
detalhe lido (5 617), 22 consultas da Vortal, e as abas a 1 319 / 7 /
64 879 / 66 205. E quatro intenções na navegação, não cinco.

**Testes:** 498 → 516. `TestBrowserEsperaPelaPorta` (5),
`TestRelogioPassaPeloTrinco` (4, com uma volta só do ciclo — o
`time.sleep(60)` está fora do try/except, por isso um `SystemExit` de
um sósia do módulo `time` rebenta o `while` sem ser engolido pelo
`except Exception`), `TestPorqueDoGit` (6) e mais dois na
`TestUltimosErrosNoEcra`, um deles a exigir que os `/indicadores` leiam
as seis marcas — o rótulo e a marca que o alimenta têm de andar juntos.

## A etiqueta de prazo tinha um 7 escrito à mão, 31 de agosto de 2026

Correcção de comportamento, deliberadamente à parte da fase de desenho
visual que corre em paralelo: aqui não se mexeu numa cor, mexeu-se em
**quem decide a cor**.

`etiqueta_prazo()` decidia o amarelo com `dias <= 7`, um limiar cozido
no código. A janela do "urgente" da aplicação é `dias_urgente()` — lê o
`config.json`, omissão 10, editável em `/alertas`. Resultado: um anúncio
com prazo a **9 dias** aparecia **verde ("folgado")** na lista, no
quadro, no calendário e na ficha, e ao mesmo tempo contava como urgente
no filtro `prazo=urgente`, no cartão dos indicadores e nos avisos por
filtro. Com a janela a 10 de origem, a discordância apanhava os prazos
a 8, 9 e 10 dias — e piorava com qualquer valor que o Afonso pusesse em
`/alertas`: a 20 dias, doze dias de anúncios diziam "folgado" a abrir
uma lista de urgentes.

É a mesma armadilha do cartão que dizia "2 com prazo a menos de 7 dias"
com o filtro a 10, e que deu origem a `janela_urgente()`. Da primeira
vez corrigiu-se o rótulo e esqueceu-se a cor — **a cor também é um
número que o ecrã mostra**, e tem de dar a mesma lista.

`etiqueta_prazo(prazo, urgente=None)` passa a ler `dias_urgente()`
quando não lhe dão a janela. Quem desenha em ciclo passa-a: a lista
(`linha(a, vista, urgente)`), o quadro (`cartao(a, etiquetas, urgente)`)
e o calendário lêem-na **uma vez por pedido**. O custo é a razão: a
etiqueta é chamada uma vez por anúncio e `dias_urgente()` abre e
desserializa o `config.json` a cada chamada — sem isto era uma abertura
de ficheiro por linha da lista. Na lista a mesma leitura serve também o
rótulo do selector ("só os que acabam em N dias"), que já lá estava a
chamar `dias_urgente()` à parte.

A ficha ficou com a omissão: renderiza-se uma vez, não em ciclo.

Testes: **490** (485 + 5 em `TestEtiquetaPrazoSegueAJanela`). Um põe a
janela a 10 e a 7 e exige que a classe de um prazo a 9 dias mude de
`avisa` para `ok`; outro confirma a fronteira **contra
`janela_urgente()`** — o último dia que o filtro apanha tem de sair
`avisa`, e o dia seguinte `ok`; outro garante que a janela passada como
argumento manda mesmo, substituindo `ler_config` por algo que rebenta.
O expirado e o "termina hoje" continuam vermelhos independentemente da
janela.

Documentação corrigida no mesmo commit: a regra do `prazo` no
`CLAUDE.md` passou a incluir a etiqueta ("a cor da etiqueta é um desses
números"), e o `LEIA-ME.md` deixou de descrever o cartão dos
indicadores como "prazo a menos de uma semana" — dizia sete com o
filtro a dez, exactamente o erro que esta sessão foi corrigir.


### O topo deste ficheiro estava a descrever páginas que já não existem

Encontrado ao procurar o que a correcção da etiqueta tornava falso, e
corrigido no mesmo dia porque é o mesmo tipo de erro: o parágrafo **«Como
está a correr»** descrevia a página inicial como a **Triagem** e mandava
o acervo para a **Pesquisa** (`/anuncios`, «12 meses por omissão, com
interruptor para o arquivo») — as duas páginas foram fundidas numa só a
31/08/2026, no mesmo dia, e o interruptor caiu. Dizia também «navegação
por cinco intenções» quando `NAV` tem quatro, com os Indicadores fora da
barra.

Os números foram remedidos na base, não copiados de outra secção:
**66 205** anúncios (dizia 66 145), **5 617 com detalhe lido = 8,5%**
(dizia 5 493 e 8,3%), **22** consultas da Vortal, e as abas a **1 449
por ver + 7 interessados + 64 749 abandonados**, que somam exactamente
os 66 205 — a partição continua a fechar. As ~17 horas para forçar os
detalhes que faltam continuam certas (60 588 a um por segundo).

**As entradas de diário datadas não se tocaram**, incluindo as que falam
da Triagem e da Pesquisa como páginas de então: são registo do que era
verdade nessa altura, e uma delas já traz a nota a dizê-lo. O que se
corrige é o que está escrito no presente — o topo, e três frases do
`LEIA-ME.md` que ainda mandavam marcar «interessa» «na Triagem ou na
Pesquisa» e diziam que o cartão do quadro é verde ou vermelho, sem o
âmbar que esta sessão acabou de pôr a acompanhar a janela do urgente.


## Seis correcções pedidas pelo Afonso, 1 de setembro de 2026

Lista de correcções vinda do uso, não de auditoria. Todas
implementadas; a primeira, a segunda e a terceira obrigaram a medir
antes de escrever código.

### 1. A Vortal deixou de trazer as peças — e não era avaria nenhuma

O Afonso reparou no **22005/2026**: o radar trazia o anúncio e mais
nada. Antes de abrir o `radar.py`, replicou-se o pedido real com o
identificador daquele anúncio. A resposta trazia as peças — **num
campo que o código não lê**.

`GetPublicTenderInformation`, o primeiro salto a partir do link
cifrado que o DR publica, responde de **duas formas** ao mesmo pedido:

- com `contractNoticeUrl` e a `documentList` vazia — o procedimento
  está publicado na comunidade e as peças saem do segundo salto
  (`GetContractNoticeDocuments`). É o caminho de sempre.
- com a `documentList` já cheia (cada documento com o seu
  `downloadUrl`) e **sem** `contractNoticeUrl`.

O código só sabia ler a primeira. Na segunda o caminho acabava em
`return [], []` — lista vazia, sem excepção, sem erro registado.
Medido em quatro anúncios reais: **duas de cada forma**. Não foi uma
mudança recente que partiu tudo; é uma forma que coexiste com a outra
e que ninguém tinha visto.

`_info_vortal()` passou a ler as duas e a devolver também o endereço
do anúncio, que é de onde sai o link do procedimento (ver o ponto 2).
Os nomes dos ficheiros também não se chamam o mesmo nas duas respostas
— `name` numa, `documentName` na outra — e aceitam-se os dois.

Provado contra a rede, nos três anúncios: 22005/2026 passou de 0 para
2 peças, 22000/2026 traz 7 e 21991/2026 traz 5. E em produção: as peças
do 22005/2026 estão na base, "Peças do procedimento CP 2298_26_Signed.pdf",
446 KB.

**Lição, escrita no CLAUDE.md:** um caminho que devolve "vazio" tanto
para "não há" como para "não percebi a resposta" transforma uma
mudança de formato numa avaria silenciosa. E ao mexer nesta cadeia,
medem-se as **duas** formas, não uma.

### 2. O botão da plataforma abria as peças, não o procedimento

Queixa: "Abrir plataforma" devia levar ao procedimento; a acingov traz
sempre um zip, a Vortal leva aos documentos e a anogov também.

Foi preciso medir o que existe, plataforma a plataforma, porque **o DR
nunca publica o endereço da página do procedimento**: os dois URL que
traz são a raiz da plataforma ("URL para Apresentação", que dá sempre
na porta de entrada) e o das peças.

- **Vortal** — há página pública: `Public/contract-notice-view/PT1.NTC.x`.
  Resolve-se pela API a partir do link cifrado.
- **anogov / ComprasPT / ESPAP** — o `acessoDocs.jsp` **é** a página do
  procedimento: traz referência interna, objecto e tipo por cima da
  lista dos documentos. Não há outra; o resto da aplicação é JSF por
  POST, sem endereço próprio (sondados sete nomes de `.jsp` prováveis,
  todos 404).
- **acingov — não há.** A lista pública tem um ícone "consultar
  procedimento" que é um `href` vazio com JS: abre um modal a dizer
  "para que possa aceder a este procedimento por favor inicie sessão".
  O identificador do link das peças é só o id em base64 (`MTEzNTk5OA`
  = `1135998`) e nenhuma rota o aceita fora da descarga.

Então: `link_do_procedimento()` decide por plataforma, e a ficha passou
a ter **dois botões** — "Abrir na (plataforma)" e "Peças na
plataforma". A Vortal resolve-se pela rota `/plataforma/<ref>` e o
resultado guarda-se em `anuncios.link_proc` (a ficha não pode ir à rede
a cada abertura). Na acingov o botão diz **"Procurar na acingov"** e
abre a pesquisa pública, com o title a explicar porquê — em vez de
prometer o que não existe. Onde a Vortal não publica página do
procedimento (é o caso do 22005/2026), a rota volta à ficha a dizê-lo.

### 3. A árvore de CPV passou a deixar tirar de dentro

O pedido, com o raciocínio já feito: escolher o 72000000 e poder tirar
um ou outro que não faça sentido — porque podem vir anúncios que tenham
apenas o 72, e se a regra for que só entram os sub-códigos escolhidos
um a um, perdem-se oportunidades.

Está certo, e o número confirma-o: com CPV 72 posto, o primeiro anúncio
da lista é um da IMPIC com o CPV `72000000` e mais nada. Marcar os
sub-códigos um a um perdia-o.

O motor já sabia excluir — o campo `cpv_excl` existe desde 30/08. O que
faltava era a árvore escrever nele: as caixas dos descendentes de uma
divisão marcada estavam **desactivadas de propósito**, com o comentário
"o filtro não sabe excluir". Sabia.

O estado da árvore passou a ser dois conjuntos (`ARV_SEL` e `ARV_EXC`)
e as caixas passaram a ser um **desenho** desse estado (`arvorePintar()`,
decidido por `arvoreEstado()`), nunca o contrário — com o estado
espalhado pelas caixas, um descendente marcado "só para se ver" acabava
dentro do filtro. Quem manda num código é o antepassado mais próximo
(ou o próprio) que apareça numa das duas listas. Voltar a marcar dentro
de um ramo excluído **empurra a exclusão para baixo**
(`arvoreDesexcluir()` exclui os irmãos do caminho), porque o par
(cpv, cpv_excl) sabe somar e subtrair uma vez mas não sabe alternar.

Verificado no browser: marcar `72000000` e desmarcar `72200000` deixa o
pai marcado, risca o filho com a marca "tirado", o chip diz "1
seleccionado · 1 tirado", e "Aplicar" escreve `cpv=72000000` e
`cpv_excl=72200000` — a lista passa de 64 para 33 e o anúncio de CPV
`72000000` continua lá.

### 4. O interesse: os CPV que a casa trabalha

Pedido: criar o interesse dentro dos alertas, para limitar a página de
anúncios sempre aos interesses definidos, com base em CPV.

É um recorte, não um filtro, e por isso entra por `com_recorte()` como
as abas e **nunca por `condicoes()`** — o motor serve os alertas e os
filtros guardados, e o interesse lá dentro cegava-os em silêncio. Vive
em `recorte_da_lista()`, que junta a aba e o interesse num sítio só,
porque o recorte é aplicado em quatro consultas da mesma página (a
lista, a contagem de cada aba, o selector das plataformas e o total do
filtro) e no CSV: um número que conte com outro recorte abre uma lista
diferente da que promete. Verificado: com `72000000` posto, as abas
passam de 1 353 / 1 / 64 879 / 66 233 para 64 / 0 / 181 / 245, e a
lista bate com o número da aba.

Três guardas, todas por a alternativa ser silêncio:

- ligado **sem CPV escolhido não esconde nada** — um ecrã em branco por
  não se ter escolhido código nenhum lê-se como avaria;
- a lista **diz** que está limitada, por cima de si mesma, com os CPV,
  o que foi tirado e quantos ficam de fora;
- `?interesse=nao` levanta-o para a vista em que se está, e a faixa
  passa a oferecer o caminho de volta.

O vazio da lista também mudou de texto: "nada por decidir, o que entrou
está triado" era uma afirmação falsa com 1 290 anúncios escondidos por
cima da faixa que diz o contrário.

O ecrã é próprio (`/alertas/interesse`, migalhas "Alertas › Interesse")
por uma razão prática: a árvore é **uma por página** — o JS fala com um
`details.arvore` e um `#filtro-cpv` — e `/alertas` já gasta a sua no
"Novo filtro". Pôr duas obrigava a mexer no JS que serve quatro
páginas. Em `/alertas` fica a caixa com o resumo e a porta.

Nasce desligado. Desligado, nada muda.

### 5. Abandonar passou a exigir motivo

Âmbito fechado, ditado pelo Afonso: *Preço base baixo*, *Falta de
certificações*, *Falta de CV's*. Sem texto livre — ao fim de um mês dá
cinquenta maneiras de escrever "preço" e nenhuma conta que se possa
fazer.

O selector vai colado ao botão, na lista e na ficha, com `required`; e
o `mudar_estado()` recusa na mesma o que não estiver na lista, porque
um `required` é conveniência do browser e não uma guarda. Sair de
abandonado limpa o motivo — um motivo pendurado num anúncio que voltou
ao por ver é uma mentira à espera de ser lida. Os que caem nos
abandonados por o prazo ter passado não têm motivo, e não se lhes
inventa um.

O motivo aparece na etiqueta da linha, no cabeçalho da ficha, no
histórico ("descartado (Preço base baixo)") e numa **coluna nova do
CSV**.

### 6. O quadro passou a ser o funil da casa

A criação de novas fases desaparece: já não é precisa. São seis, e são
estas — *Por analisar, A preparar proposta, Submetido, Relatório
preliminar, Ganho, Perdido*. Renomear fica; criar e apagar saiu, UI e
rotas. Apagar saiu junto porque, sem criar, apagar uma das seis era
irreversível e levava consigo o campo que ela pede.

**O que manda é o papel, não o nome** (`fases.papel`, `FASES_DE_ORIGEM`):
renomear uma coluna não pode calar o campo que ela pergunta. A migração
`atribuir_papeis()` corre a cada arranque, reconhece por pedaço de nome
(`PISTAS_DE_PAPEL`) e cria o que faltar, uma vez só. Na base do Afonso
apanhou as seis à primeira, "Relatorio Preleminar" incluído.

Cada fase pede o que lhe falta, no próprio cartão:

| Fase | O que pede |
|---|---|
| Por analisar | nada |
| A preparar proposta | nada |
| Submetido | o preço proposto |
| Relatório preliminar | o lugar e os três primeiros |
| Ganho | nada |
| Perdido | porquê — *Preço, CV's, Proposta técnica, Certificações* |

A partir do "Submetido" o preço do cartão **e a soma da coluna** passam
a ser o proposto: somar preços base numa coluna de submetidos dá o
tecto da entidade e não o que está em jogo, com o mesmo ar de número
certo. Enquanto o proposto não estiver preenchido mostra-se o base
**escrito como "base"** — mostrá-lo calado era dar o tecto da entidade
por proposta nossa. O que se grava fica também no histórico da ficha:
"submetido a 118.500,00 EUR" vale mais, três meses depois, do que a
coluna onde o cartão parou.

Uma armadilha pequena e cara: o proposto grava-se pelo
`_texto_do_preco()` ("118.500,00 EUR") e **não pelo `euros()`** — esse
põe espaço nos milhares, e o `euros_do_texto()` lê "118" de "118 500 €".
A soma da coluna dava 118 em vez de 118 500. Há teste a guardá-lo.

### Testes e verificação

**561 testes** (eram 521), todos a passar. As classes novas guardam: as
duas formas da resposta da Vortal e o salto que se poupa quando o
PT1.NTC vem no próprio link; o destino do botão por plataforma,
incluindo o "não há" da acingov; o reconhecimento dos papéis das fases
com o erro de escrita real da base; a idempotência do
`atribuir_papeis()`; o interesse ligado, desligado, vazio, levantado e
**fora do `condicoes()`**; a recusa de abandonar sem motivo e com
motivo inventado; os campos por fase; e a troca do preço base pelo
proposto, com o formato de gravação.

Dois testes antigos falhavam **antes desta sessão** e não por causa
dela: comparavam a janela do urgente com `radar.DIAS_URGENTE` (a
omissão, 10) enquanto o config.json está a 8 — exactamente o limiar à
mão que a regra da casa proíbe. Passaram a ler `dias_urgente()`.

Verificação a correr: as páginas todas servidas, o interesse ligado e
desligado com as abas a acompanhar, a árvore exercitada no browser, e o
quadro com as seis fases cheias num painel de ensaio sobre base
temporária (porta 8766, nunca a 8765).

Pelo caminho, a armadilha do costume: o painel da porta 8765 tinha
arrancado às 12:37 e o `radar.py` foi gravado às 12:39 — **estava a
servir código velho**. Comparar a hora de arranque do processo com a da
última gravação do ficheiro continua a ser o primeiro passo antes de
dizer "a correcção não funcionou".

### O que ficou por decidir

Na acingov não há página pública do procedimento, e por isso o botão
leva à pesquisa pública em vez de ao procedimento — é o melhor que se
consegue sem sessão iniciada, e a acingov é ~45% dos anúncios com
peças. Se o Afonso quiser mais do que isto, é decisão nova: implicaria
credenciais, e a regra da casa é que o radar não depende de nada da
empresa.

## O detalhe das consultas preliminares, 1 de setembro de 2026

O Afonso, ao ver a segunda fonte a funcionar: «tu não estás a fazer a
leitura do que está dentro das consultas preliminares da Vortal — por
exemplo a consulta preliminar vem sem CPV».

Vinha mesmo. **24 em 24, com o CPV vazio.** E não era um caso de
borda: a pesquisa pública da Vortal (`SearchTenders`) devolve
dezasseis campos — identificador, referência, descrição, entidade,
país, local, datas, estado, tipo, moeda, preço base — e **nenhum deles
é CPV nem NIPC**. O B14 tomou a linha da pesquisa por anúncio inteiro
e guardou-a com `detalhe_lido=1`, ou seja, a dizer que não havia mais
nada para ler.

O custo disto não se via em lado nenhum. A contagem subia, os erros
estavam a zero, a consulta abria na ficha. Mas sem CPV uma consulta
preliminar é **invisível a tudo o que filtra por código**: o filtro da
lista, a árvore de CPV, os alertas por código e — a pior — o recorte
do interesse, que é permanente. Com o interesse ligado, as 24
desapareciam da lista sem uma palavra. E sem NIPC não havia por onde
cruzar a entidade com o corpus de contratos, que é a chave (o nome
não é a identidade de uma entidade: o NIF é).

### Onde estava o que faltava

Duas tentativas de adivinhar deram três HTTP 500: o
`GetPublicTenderInformation`, que é o primeiro salto das peças, **só
aceita o identificador cifrado que o DR publica** e recusa o
`PT1.NTC` às claras. O que resolveu foi abrir a página pública de uma
consulta no browser e ler os pedidos dela — a página **mostra** o CPV,
logo alguma chamada o traz. Trazia:

    /public/api/ContractNoticeDetail/
        GetRegionConfigurationByContractNoticeUId
        ?contractNoticeUId=PT1.NTC.x&langCode=pt

Sem sessão, com o `PT1.NTC` às claras, e com tudo o que faltava:
CPV, NIPC, nome canónico da entidade, referência interna, tipo de
contrato, morada completa da execução, prazos e a lista de documentos.
Medido nas 24 que já estavam na base: **CPV em 100%, NIPC em 100%,
local em 100%, peças em 75%, zero falhas.**

E mais uma coisa que não se esperava: o campo
`CB1_SummaryCN_QuestionnaireHTML` aponta para o **questionário
público**, que é a lista dos artigos que a entidade quer comprar, com
quantidade e unidade. Numa consulta preliminar isso *é* o conteúdo —
uma consulta intitulada «150 discos 2.5" SSD de 240GB» explica-se no
título, mas a de Coimbra, intitulada «Aquisição de um computador com
características especiais», traz onze linhas de artigos com marca e
modelo. Entra na ficha como secção 6.

### O que ficou feito

`detalhe_da_preliminar()` faz o pedido e monta o texto por secções
numeradas, como o do DR — a ficha lê-se igual, venha de onde vier.
`ler_preliminares()` corre sobre `detalhe_lido=0`, grava e só então
marca como lido; um detalhe que não chega deixa a consulta por ler
para a verificação seguinte, porque marcar como lido o que não se leu
era repetir o erro de origem. `recolher_vortal()` chama-a a seguir à
pesquisa: a pesquisa dá a linha, o detalhe dá o conteúdo.

Três coisas que a implementação obrigou a arrumar:

**O `ler_detalhes()` passou a filtrar a fonte.** As duas fontes usam
agora o mesmo `detalhe_lido=0`, e sem o filtro a fila do DR pescava um
`PT1.NTC.3785462`, mandava-o ao portal do DR como se fosse chave dele
e — porque a resposta não vinha em JSON — **acabava a marcar o token
como expirado**. Um falso alarme de captura expirada é pior do que não
ler nada: manda o Afonso refazer capturas que estão boas.

**O prazo passou a ser em hora de Lisboa.** A API dá tudo em UTC
(`2026-09-03T22:59:00Z`) e a própria Vortal mostra 23:59, porque no
Verão Lisboa é UTC+1. Escrever o UTC na ficha punha o prazo uma hora
mais cedo do que a plataforma diz — e um prazo é a informação pela
qual se perde uma proposta. `hora_de_lisboa()` faz a conta pela regra
da UE (último domingo de Março às 01:00 UTC ao último domingo de
Outubro), à mão, porque o `zoneinfo` depende de dados de fusos que
este Windows não garante. Há teste nas quatro fronteiras.

**O questionário perde o CSS antes de perder as etiquetas.** São 6 KB
de estilos inline para 500 caracteres de tabela; despir as etiquetas
primeiro punha a folha de estilos na ficha como se fosse texto. E o
cabeçalho da tabela vem em `<th>` soltos dentro do `<thead>`, **sem
`<tr>` nenhum** — sem o tratar à parte, a linha saía «1 | Luvas |
1500,00 | UNID» sem dizer qual dos números era a quantidade.

As 24 que já estavam na base encheram-se por migração com marca
(`preliminares_com_detalhe`), que as põe a `detalhe_lido=0` uma vez.
Marca e não `WHERE cpv=''`: uma consulta pode mesmo não ter CPV, e
essa não se retenta para sempre.

Verificado a correr contra a Vortal verdadeira: **24 em 24 com CPV,
NIPC e texto; zero por ler.** Treze códigos CPV distintos, com o
33140000 (material médico de consumo) em nove — o que é de esperar de
uma população que é quase toda de unidades locais de saúde. Testes:
**573** (561 + 12).

### O que isto ensina para a próxima fonte

Uma fonte não está integrada quando responde e as linhas aparecem.
Está integrada quando **todas as colunas por que a aplicação filtra**
estão cheias ou declaradas indisponíveis. O B14 passou por revisão,
testes e documentação com uma coluna 100% vazia, porque contagens a
subir e erros a zero não distinguem «este campo não veio» de «este
anúncio não tem esse campo». A verificação que apanha isto é uma
consulta de uma linha — quantos é que têm a coluna vazia — e não se
fez.


## Duas correcções às correcções, 1 de setembro de 2026

Devolvidas pelo Afonso depois de usar o que a sessão anterior entregou.

### O motivo do abandono é um pop-up, não um selector na linha

«O motivo do abandonar deve ser um pop-up e não um botão.» Tem razão, e
a razão é de leitura: a lista tem vinte linhas por página, e um selector
colado a cada botão punha **vinte perguntas no ecrã antes de alguém as
fazer**. A lista é para ler anúncios; a pergunta é do momento em que se
decide, não de antes.

Agora: carregar em "abandonar" abre uma caixa (`<dialog>` nativo, sem
biblioteca) com o nome do anúncio, a nota de que não apaga nada, e as
três hipóteses em rádios. A caixa é **uma por página**
(`caixa_de_abandono()`), partilhada por todos os botões — vinte cópias
do mesmo diálogo seriam o mesmo erro dos vinte selectores, com mais
HTML.

O botão continua a ser `submit` de um `<form>` que faz POST, e o JS
intercepta o submit para abrir a caixa. **Sem JS o pedido segue** e o
servidor recusa por falta de motivo, com o aviso a dizer porquê — a
degradação diz o que se passa, em vez de deixar um botão morto. A guarda
continua a ser o `mudar_estado()`: o `required` dos rádios é
conveniência do browser.

Verificado no painel a correr: o clique abre a caixa com o título certo
("Aquisição de mantas térmicas c/ cedência de equipamento") e a acção
apontada ao anúncio certo; "Cancelar" fecha sem gravar; e a lista ficou
limpa — nenhum selector nas linhas.

### «Já testei e não vi isso a acontecer» — os campos por fase

Fui ver a base antes de responder. Os três cartões dele estão todos em
**`fase_id=1`, "Por analisar"** — a fase que, por especificação dele
próprio, *não pede nada*. Os papéis estão todos bem atribuídos
(`analisar, proposta, submetido, relatorio, ganho, perdido`, com o
"Relatorio Preleminar" reconhecido apesar do erro de escrita), e o
mecanismo funciona: num painel de ensaio com cartões nas seis colunas,
o "Submetido" mostra o campo do preço proposto, o "Relatório
preliminar" o lugar e os três primeiros, e o "Perdido" o motivo.

Mas isto não é uma boa resposta: **o campo só existe quando lá está um
cartão**, e com tudo em "Por analisar" — que é o estado normal de quem
acabou de triar — não havia nada no ecrã a dizer que a coluna
"Submetido" pede o preço proposto. Uma funcionalidade que só se
descobre por acidente é uma funcionalidade que não existe.

Correcção: **o cabeçalho de cada coluna diz o que ela pede**
(`PEDIDO_DA_FASE`) — "pede o preço proposto", "pede o lugar e os três
primeiros", "pede porque se perdeu". As três que não pedem nada
continuam a não dizer nada. Há teste a obrigar as duas listas a
concordar: uma coluna que anuncia um campo e não o mostra é pior do que
não o anunciar.

578 testes.

### E outra vez o painel a servir código velho

Segunda vez no mesmo dia: o processo na 8765 tinha arrancado às 13:33 e
o `radar.py` foi gravado às 13:40. É a armadilha que está escrita no
CLAUDE.md, e continua a valer a pena repeti-la: **antes de dizer "não
funciona", compara a hora de arranque do processo com a da última
gravação do ficheiro.**


## «Já tenho um no Submetido e não aconteceu nada», 1 de setembro de 2026

Era verdade, e o diagnóstico da sessão anterior estava incompleto: eu
tinha dito que os cartões dele estavam todos em "Por analisar" e
acrescentado o aviso no cabeçalho da coluna. Ele moveu um para o
Submetido, e continuou a não acontecer nada.

**O servidor estava a mandar o campo.** Medido no HTML servido: a coluna
diz "pede o preço proposto", o cartão do 21993/2026 traz
`base 213.830,00 EUR` e o formulário com `name='preco_proposto'`. E
numa página carregada de fresco o campo está lá, visível.

O que falhava era o arrastar. O cartão que se arrasta é o **mesmo nó do
DOM**, com o HTML que o servidor lhe deu na coluna de onde veio; o
`drop` faz `corpo.appendChild(carta)` e um POST ao `/quadro/mover`, e
mais nada. Quem decide o que um cartão mostra é o servidor, pela fase —
por isso largar no "Submetido" mudava a coluna e não fazia aparecer o
campo, não trocava o preço base pelo proposto, e deixava a soma no
cabeçalho das duas colunas errada. Só recarregando à mão.

Correcção: o caminho do **sucesso** também recarrega (o do erro já
recarregava), guardando o rolar horizontal em `sessionStorage` — sem
isso, arrastar para a última coluna atirava a vista para a primeira, o
que se lê como "perdi o cartão".

Verificado a sério, num painel de ensaio sobre base temporária, com um
`drop` disparado a sério (`DataTransfer` + `DragEvent`): antes do
largar, o cartão está em "Por analisar", sem campo, a mostrar
`175.000,00 EUR`; depois, está em "Submetido", com o campo
`preco_proposto`, a mostrar `base 175.000,00 EUR` **e o cabeçalho da
coluna já em `3 · 118,5 k€`**.

**A lição, e é a que interessa:** eu tinha verificado o servidor (o HTML
sai certo) e tinha verificado o ecrã depois de um carregamento normal.
Não tinha verificado **a transição** — o caminho por que o utilizador
lá chega. Um render correcto e uma interacção que não o volta a pedir
dão exactamente o sintoma de "não funciona", e nenhum dos dois testes
que eu tinha o apanhava.

580 testes. Os dois novos guardam a decisão no próprio JS: que o ramo do
sucesso recarrega, e que guarda o rolar antes de o fazer.

### A skill do estado abria a PowerShell velha

À margem, mas da mesma queixa dele ("tenho a versão mais recente do
PowerShell e abre sempre a mais antiga"): o radar não abre PowerShell
nenhuma — os `.bat` correm em `cmd.exe` e chamam o Python directamente.
A única coisa deste repositório que a abria era a skill `estado-radar`,
que pedia `powershell` (o 5.1) para ver se a porta 8765 está a atender.
Passou a tentar o `pwsh` (7) primeiro e a cair no `powershell` se ele
não existir — o 7 nem sempre está instalado, o 5.1 está sempre.

(O que faz aparecer a antiga ao abrir um terminal é outra coisa e fica
fora do projecto: o perfil por omissão do Windows Terminal, que está em
"Windows PowerShell" — decisão dele, não se mexeu.)

## A pen como «hub», 1 de setembro de 2026 — planeado, e fechado antes de se construir

O Afonso quis que a pen deixasse de ser uma pasta com um projecto
dentro e passasse a ser um hub: um Python, um Node e um git partilhados
em `D:\comum`, as chaves numa pasta comum, e as skills, plugins e MCPs
do Claude a valerem para todas as aplicações que viesse a construir,
sem ter de escolher quais pôr em qual. Falou também em modelos de IA
locais pequenos e em ferramentas que viu na net (claude-mem,
OmniRoute).

Já tinha havido uma primeira tentativa, na sessão anterior: construiu-se
tudo de uma vez (motor movido, chaves movidas, configuração do Claude
copiada, hooks reescritos, commit e push), ele viu o resultado só no
fim, não ficou confiante, e repôs-se tudo — `git reset`, force push,
pasta apagada. Desta vez fez-se a planta primeiro, e a planta chegou
a esta conclusão antes de mover um ficheiro.

### Porque se fechou

Das três vantagens que o hub prometia, duas já existem e a terceira
ainda não tem para quem servir:

- **«A pen tem de funcionar em qualquer computador.»** Já funciona: o
  Python está dentro de `radar\python`, e o painel abre em qualquer
  Windows. O que falta na pen é o git, que só faz falta ao trabalhar
  com o Claude Code — e esse tem de estar instalado nesse computador
  de qualquer maneira (decisão dele: o Claude Code não vai para a pen).
- **«Skills e plugins a valerem em todas as aplicações sem escolher.»**
  Já é assim: as três skills dele e os seis plugins estão instalados
  ao nível do utilizador (`~/.claude`), e por isso aplicam-se a
  qualquer projecto que abra. Era o que queria, e já tinha.
- **Poupar ~100 MB e um passo de instalação por aplicação nova.** Só
  conta quando houver uma segunda aplicação. Há uma. E o passo é o
  Claude que o faz.

No dia-a-dia, o hub não mudava nada na forma de trabalhar — a
complexidade ficava toda na montagem e na documentação. Trabalho e
risco agora, para uma vantagem que hoje não existe. **Decisão dele:
não se faz.** Quando aparecer a segunda aplicação, copia-se a receita
do radar (uma pasta com o Python embutido dentro), que leva minutos.
Se um dia forem quatro ou cinco aplicações e o desperdício incomodar,
volta-se à planta abaixo.

### O que a primeira tentativa mediu, e continua verdade

Fica aqui para não se voltar a descobrir:

- O Python embutido corre em `safe_path`: não acrescenta sozinho ao
  `sys.path` a pasta do programa. Dentro da aplicação resolve-se com
  um `..` no `python314._pth`; partilhado, é preciso um
  `sitecustomize.py`.
- O `PYTHONPATH` é ignorado quando existe um `._pth`.
- O `sys.path` traz a pasta de pacotes do utilizador **da máquina onde
  a pen está espetada**. É o que faz a pen correr num computador e não
  noutro; um hub teria de a retirar.
- `CLAUDE_CONFIG_DIR` governa tudo (`settings.json`, skills, plugins e
  o `.claude.json` dos MCPs), mas o Claude guarda **caminhos
  absolutos**: copiada de `C:\Users\...`, os plugins vinham apontados
  ao disco da máquina — abre sem se queixar e sem os plugins. Uma
  pasta nova pede `/login`. Nunca se mediu se a aplicação de
  secretária respeita a variável.
- O hook `testes_antes_do_commit.py` procura o Python em
  `<projecto>\python\python.exe`: mover o motor parte-o, e foi um bug
  que a própria primeira tentativa criou.
- A letra da unidade não é fixa: a pen já apareceu como `E:` (há
  registos em `.claude.json`). Qualquer atalho tem de a encontrar por
  `%~d0`.
- A pen é rápida em ficheiros grandes e lenta em muitos pequenos
  (42 MB/s a 4 KB): um modelo de IA carrega bem, o Node e o Claude
  Code arrancam mal.

### A planta, para se voltar a ela

`D:\CLAUDE.md` (regras comuns; o Claude Code lê os CLAUDE.md de todas
as pastas acima do projecto) e `D:\comum\` com `python\` (motor +
`sitecustomize.py`), `libs\` (pacotes comuns, com a `libs\` de cada
aplicação a ganhar-lhe), `node\`, `git\`, `chaves\` e `ferramentas\`
(`ambiente.bat`, `_python.bat` modelo). O `_python.bat` de cada
aplicação reencaminha para `%~d0\comum\python`. Fases pequenas, o
antigo só se apaga depois de os testes passarem com o novo, teste com
a pen montada noutra letra por `subst`. A configuração do Claude fica
no computador (decisão dele); o que a pen partilharia entre projectos
é o `CLAUDE.md` da raiz e os hooks.

### Sobre o que ele viu na net

- **Modelos locais**: o computador tem 16 GB e gráfica integrada. Um
  modelo de 3–8 mil milhões corre no processador a poucas palavras
  por segundo — serve para lote (classificar de madrugada) ou como
  reserva quando a cadeia `FORNECEDORES` esgota o dia; não substitui
  o `gpt-oss-120b`. Ferramenta: `llama.cpp` (pasta solta) ou Ollama em
  zip, com os modelos na pen. **Fica para depois**, decisão dele.
- **claude-mem** (memória entre sessões): seria a quarta memória, ao
  lado da automática, do ESTADO.md e do registo das skills — e a
  auditoria de 30/08 já apanhou o ESTADO.md a mentir por omissão.
  Não agora.
- **OmniRoute** (porta única de IA com reservas entre fornecedores): o
  radar já o faz em `_perguntar()`. Só vale quando uma segunda
  aplicação precisar da mesma cadeia — e aí é peça de hub.

### O que fica em aberto, e não é código

- **BitLocker To Go** na pen, pelos passos que lhe foram dados. A
  chave de recuperação **em ficheiro fora da pen e impressa**, não
  «na conta Microsoft»: a sessão dele é uma conta de empresa, e a
  chave iria para o Entra ID da empresa. Desbloqueio automático no
  computador dele, senão as tarefas das 09:00 e das 17:00 encontram a
  pen fechada.
- **Uma cópia do `radar.db` fora da pen.** As sete cópias diárias de
  `copias/` vivem na mesma pen; se ela morrer, perde-se a triagem e
  as peças, que são o único conteúdo que não se refaz. Pequeno de
  montar, quando ele pedir.

## O mesmo concurso três vezes: as alterações do DR, 1 de setembro de 2026

Apareceu a medir outra coisa. Ao cruzar o Excel de análise de concursos
do Afonso (187 concursos, exportados de uma lista do SharePoint) com a
base, 94 das 180 linhas de 2025–2026 davam «vários anúncios com a mesma
pontuação» — e eram sempre o mesmo procedimento publicado duas e três
vezes: o BIA da Infraestruturas de Portugal a 4 de Fevereiro, 10 de
Março e 18 de Março, com título igual e `ref` diferente. Em 2026 a base
tinha 22 053 anúncios para 18 894 procedimentos distintos. Ele decidiu:
**resolve-se isto antes de importar seja o que for.**

### O que se mediu antes de desenhar

- **O DR não emenda um anúncio: publica outro.** O texto da
  republicação começa por «Alteração do Anúncio de procedimento n.º
  18372/2026, de 2026-07-17, com o ID 419967433». Dos 5 661 textos
  lidos, **763 (13,5%) começam assim** — e é a única forma que existe:
  os 763 prefixos são «alteração do». É uma chave exacta, não uma
  heurística.
- **Título igual na mesma entidade não serve de chave.** Dos pares com
  título igual e detalhe lido, 58 não citam anúncio nenhum: são
  procedimentos diferentes (a Universidade do Algarve repete o mesmo
  título todos os anos). Se se tivesse agrupado por título, tinham-se
  fundido concursos distintos.
- **103 das 763 citam a alteração anterior e não o original** (21505 →
  20771 → 18372). Segue-se a cadeia.
- **O que muda é o prazo**: nos 495 grupos todos lidos, 461 têm prazo
  diferente entre membros e 458 têm o mesmo preço base. É a prorrogação
  a sair como anúncio novo.
- **O custo humano estava medido na base**: 511 das 763 alterações
  estavam «descartado» — o Afonso descartou 511 vezes procedimentos que
  já tinha descartado no original. E 217 dos 1 404 «por ver» eram
  republicações de algo que já lá estava.

### A decisão de desenho

**O original é a ficha do procedimento.** A triagem, o quadro, as peças
e a leitura ficam nele; a alteração fica na base com o próprio texto,
em `estado='alteracao'`, fora de todas as listas (o `condicoes()`
exclui-a quando `estado=""`; os outros estados nunca a apanham), e
passa ao original o que está em vigor: prazo, preço base, CPV,
plataforma e link das peças — **do membro mais recente da cadeia**,
seja qual for o que acabou de ser lido, porque o `ler_detalhes()` lê do
mais recente para o mais antigo e a ordem de chegada não pode importar.
O original guarda `alterado_por`; a alteração guarda `altera`.

A alternativa era passar a triagem para o anúncio mais recente. Mudava
o `ref` de tudo o que já estava feito a cada republicação — peças em
`documentos/<ref>/`, análise, cartão do quadro, histórico — e foi
rejeitada por isso.

Três guardas que não são decorativas, e cada uma tem teste:

- **Reler um original já alterado não pode escrever-lhe os campos da
  página dele.** A página do original no DR nunca muda; relê-la repunha
  o prazo velho por cima do novo e registava uma «alteração» falsa.
  `_guardar_detalhe()` e `reparsear()` só lhe guardam o texto.
- **`reler_marcados()` relê pela página da alteração em vigor**, não
  pela do original.
- **`mudar_estado()` recusa triar uma alteração** e diz onde se decide.

A ficha da alteração aponta para o original; a do original diz
«Alterado pelo anúncio X» e mostra o texto da versão em vigor (o dela
fica na base). O histórico do original conta o que mudou («prazo de
propostas 13/08/2026 → 11/09/2026»). Quando o original está marcado
(interessa ou com fase), a mudança vai também para a fila
`alteracoes`, a do resumo diário — o mesmo critério do
`reler_marcados()`: uma prorrogação num anúncio que ninguém quer não é
notícia.

**Se foi na alteração que alguém decidiu, a decisão passa para o
original.** 145 heranças na migração (a maioria descartes), incluindo
o «interessa» do 21993/2026 para o 21488/2026.

### A migração, e o erro que ela apanhou

Correu por marca (`alteracoes_agrupadas`) no arranque, sobre uma cópia
com nome próprio feita antes (`copias/radar-antes-alteracoes-2026-09-01.db`,
fora da rotação das sete). Dois minutos. Resultado: 763 alterações
ligadas, 660 originais com `alterado_por`, 626 com campos alterados
registados no histórico, fila do resumo a zero (a migração não avisa).
O 18372/2026 ficou como devia: descartado, com o prazo 11/09 que veio
do 21505.

**A primeira regra de fusão estava errada num caso.** Quando a
alteração e o original estavam ambos decididos e diferentes,
mantinha-se o original. Aconteceu 6 vezes; em 5 a alteração era um
«por ver» com fase (não é decisão), mas na sexta era o **«interessa»
que o Afonso pôs no 21924/2026 às 12:59 de hoje**, por baixo de um
descarte automático do original 19127/2026 de 30/08 («prazo passado»).
O item dele sumiu-se dos Interessados. A regra passou a ser: uma
decisão a sério (interessa/descartado) na alteração ganha, porque a
alteração é a publicação mais recente e foi sobre ela que se decidiu
por último; um «por ver» com fase continua a não ser decisão. A
reparação fez-se pelo caminho sanccionado — `--repor-triagem` com um
ficheiro de uma linha (a do 21924 exportada às 17:00) e `--reler` —
depois de o hook ter recusado, e bem, um UPDATE por script à base de
trabalho. O 19127/2026 está «interessa», fase 1, e o histórico dele
guarda as três linhas: o descarte, a regra errada e a correcção.

### Números depois

| | antes | depois |
|---|---|---|
| Anúncios na base | 66 286 | 66 286 (65 523 procedimentos + 763 alterações) |
| Por ver | 1 404 | 1 221 |
| Interessados | 3 (2 eram alterações) | 3 (os originais) |
| Abandonados | 64 879 | 64 299 |
| Todos | 66 233 | 65 523 |
| Descartados à mão | 4 097 | 3 728 (511 eram descartes repetidos em alterações) |

Dos 1 221 por ver, 70 são originais cujo prazo foi prorrogado e que
por isso **voltaram** ao por ver — o comportamento que o LEIA-ME já
prometia («um anúncio rectificado com prazo novo volta sozinho») e que
até hoje só acontecia por acaso, quando a republicação entrava como
anúncio novo.

### O que fica por fazer, e o que isto abre

- **Uma etiqueta «alterado a DD/MM» na linha da lista.** A ficha e o
  histórico dizem-no; a lista ainda não. Pequeno.
- **A importação do Excel e do Zoho** era o objectivo e fica para a
  próxima sessão, agora com a chave certa: uma linha do Excel liga-se
  ao procedimento (o original), e os 94 «ambíguos» do cruzamento
  deixam de o ser. O Zoho lê-se pelo browser (ele não consegue exportar
  CSV); é a fonte mais actual do estado. Entidades espanholas não
  entram. E o vocabulário dos estados («Não fomos», «passou sem
  decisão», «cancelado») e se o radar passa a ser onde se escreve são
  decisões dele, ainda por dar.
- **`--reler` demora ~2 minutos na primeira vez** por causa da
  migração dentro do `iniciar_db()`; depois disso, 5 segundos. O
  arranque do painel paga a mesma migração uma vez, por marca.

## O registo da casa: o Excel entrou no radar, 2 de setembro de 2026

«Avança com a importação do Excel», disse ele, depois de os
duplicados estarem resolvidos. O ficheiro é o
`Analise_Concursos_Publicos.xlsm`: 187 concursos exportados de uma
lista do SharePoint (nome, entidade, preço base, modelo, estado) e
completados numa folha por concurso, com macros VBA a consolidar as
tabelas planas. Antes de escrever uma linha de código leu-se o VBA
todo — o ficheiro é uma pequena base de dados feita em Excel, com as
folhas `C_` como registos, um ID estável na coluna K (e em Z1 da
folha), sincronização nos dois sentidos e quatro consolidadores.
**Decisão:** lê-se pelas mesmas âncoras que as macros usam e nunca
pelas tabelas planas, que só estão certas depois do último
`AtualizarTudo`.

### O primeiro módulo fora do `radar.py`

`casa.py`, 700 linhas. Importa o radar dentro das funções (o radar
importa-o no topo para as rotas), e o `radar.py` ganhou só o que tinha
de ser dele: a linha do CLI (`--importar-excel`), a página `/casa`, o
bloco «Registo da casa» na ficha e uma entrada no `Em curso`. É a
regra para os módulos seguintes, em vez de partir o ficheiro grande
antes de haver um segundo módulo para ver onde as fronteiras estão.

### Ligar uma linha do Excel a um anúncio

Três sinais, por ordem, e a medida de cada um:

1. **O nome no título, por contenção.** O nome do Excel é uma
   abreviatura do título do DR («Plataforma Central de Deteção
   Precoce» para «(DAG) Aquisição de serviços para evolução da
   Plataforma Central de Deteção Precoce no âmbito…»). Com Jaccard
   ficavam 105 linhas ambíguas; com 70% de contenção e 30% de Jaccard
   ficaram 84. A entidade conta 0,35 e resolve-se pelo corpus (o nome
   «SPMS» dá a chave 509540716 e o nome canónico, que é o que o DR
   escreve por extenso); um preço base igual conta 0,5.
2. **O contrato celebrado.** O valor do 1.º lugar da tabela C é o
   `preco_contratual` no BASE, e o BASE guarda o `n_anuncio`, que é o
   ref. Exige-se a entidade certa ou parentesco no título — o mesmo
   valor aparece em suturas e em software. Ligou 5 que mais nada
   ligava, o «GPEARI» da eSPAP incluído.
3. **Ler o detalhe dos candidatos ambíguos ao DR.** Traz o preço base
   para desempatar e, sobretudo, **revela as republicações**: a maior
   parte da ambiguidade eram alterações por ler (o BIA aparecia como
   2596, 5777 e 6734 porque as duas últimas ainda não tinham detalhe).
   354 leituras no ensaio, ~1 s cada; passou de 97 para 149 ligadas, e
   a base ganhou 104 alterações identificadas pelo caminho (763 → 867).

Resultado: **149 das 187 ligadas** (144 pela pontuação, 5 pelo BASE),
32 ambíguas e 5 sem nada (títulos internos como «2026_P093» ou
«ADENE_CPr_019_2026_DITE», e dois de 2023 anteriores à base), 1 fora do
país (Astúrias, por decisão dele). As 25 ligações de pontuação mais
baixa foram vistas uma a uma antes de gravar: todas certas.

### O que se escreveu nos anúncios

Só quando o estado do Excel é inequívoco: *Não fomos* → descartado com
o motivo mapeado (9 tinham razão; os outros 60 ficam sem motivo, como
os expirados); *Submetido*, *Perdido* e *Ganho* → interessa na fase
com esse papel, com preço proposto, lugar e três primeiros.
*Cancelado* e *TBD* ficam só no registo. 146 aplicadas: o quadro tem
agora 18 submetidos, 12 ganhos e 42 perdidos vindos do Excel, e a soma
das colunas Ganho/Perdido é a das propostas da casa. Os dois motivos
novos — «Fora do âmbito», «Prazo curto» — vieram das razões dele.

**Uma decisão humana no radar nunca é esmagada.** Houve um conflito, e
é um caso de lotes: o 1947/2026 da SPMS (servidor de terminologias)
tem três linhas no Excel — dois lotes perdidos e um ganho — e o radar
tem um estado por anúncio. Ficou «perdido» (a primeira linha) e o
histórico diz que o Excel também diz «Ganho». Lotes com resultados
diferentes no mesmo anúncio são uma limitação conhecida, não um erro.

### O erro que só a importação a sério apanhou

O ensaio correu duas vezes sem problema; a importação a sério rebentou
com `database is locked` ao fim de 30 segundos. A importação escrevia a
primeira linha da casa e ficava com a transacção aberta enquanto o
`ler_detalhe_de()` gravava pela ligação dele. O ensaio não escrevia,
por isso nunca esperou por nada. Passou a duas passagens — a primeira
só lê (e vai ao DR), a segunda escreve — e há teste que simula a
leitura com uma escrita por outra ligação. A base ficou intacta: a
transacção foi abortada e as leituras de detalhe são idempotentes.
Cópia com nome antes de gravar: `copias/radar-antes-excel-2026-09-02.db`.

### E logo a seguir: tudo isto saiu do ecrã, por decisão dele

Ao ver o resultado, o Afonso decidiu de outra maneira, e é a decisão
que manda daqui para a frente: **«não quero ver alterações nenhumas
no front antes de termos tudo consolidado»**. Primeiro guarda-se a
informação e garante-se que está correcta — as ligações validadas à
mão, os lotes resolvidos —, só depois o Zoho, e só depois disso se
decide como o registo entra no esqueleto da aplicação.

O que se desfez, na mesma sessão:

- A página `/casa`, a entrada «Registo da casa» no *Em curso*, o bloco
  da ficha e a entrada do índice **saíram do `radar.py`**. Há teste a
  guardar que não voltam sem ele dizer (`test_o_front_nao_mudou`).
- **A triagem aplicada aos 146 anúncios foi reposta** tal como estava
  na cópia feita antes da importação (`--casa-desfazer
  copias/radar-antes-excel-2026-09-02.db`): estado, fase, motivo,
  preço proposto, lugar e três primeiros; as 213 linhas de histórico
  escritas pelo Excel foram apagadas. O quadro voltou aos cartões de
  antes (4: os 3 que já lá estavam mais o 22102/2026, que ele marcou
  às 09:58 desta manhã, com o painel dele aberto), os motivos novos a
  zero. As leituras de detalhe e as 104 alterações identificadas pelo
  caminho ficam — são factos do DR, não triagem. Entretanto a
  verificação das 09:00 correu: 47 anúncios publicados hoje e mais 4
  alterações ligadas sozinhas ao original, com o prazo novo — a regra
  de ontem a trabalhar sem ninguém olhar.
- Os dois motivos de abandono novos saíram de `MOTIVOS_ABANDONO` (o
  pop-up volta a ter três); ficam em `casa.MAPA_RAZAO` para o dia em
  que a triagem se aplicar.
- O importador passou a **não aplicar triagem por omissão**
  (`triagem=False`; `--com-triagem` para quando for altura). Ligar à
  mão faz-se por comando, `--casa-ligar ID REF`, sem página.

O que ficou na base: a tabela `casa` com as 187 linhas e as 149
ligações, os 311 preços por perfil e os 156 perfis exigidos. Nada
disto se vê no painel, e é assim de propósito.

### O que fica

- **As 37 linhas por ligar ficaram em 3.** Ele respondeu à lista na
  mesma manhã: 24 referências (todas existem e batem com o nome do
  Excel, conferidas uma a uma antes de gravar), 5 que **não têm
  anúncio no DR** — consultas prévias, ajustes directos e consultas
  preliminares, que a parte L não publica —, 3 «não sei» (#102, #128,
  #134) e os de 2023 e 2024, que «não interessam». Os «nenhum» ficam
  ditos em `porque_sem_ref` e a importação seguinte não os volta a
  procurar. O registo está agora em 173 ligados, 10 sem anúncio, 3 por
  saber e 1 fora do país.
- **Os lotes: decididos e lidos, ainda não desenhados.** A decisão
  dele (02/09/2026): «nos anúncios diz se tem lotes, podes identificar
  por aí; um cartão por anúncio, mas os cartões que têm lotes devem
  identificar a que lotes fomos e se fomos a todos, e no final,
  perdido ou ganho, separam-se os cartões». Medido no DR: o anúncio
  declara «Procedimento com lotes? Sim», o máximo autorizado e um bloco
  «Lotes:» com número, descrição e preço base de cada um — **1 423 dos
  6 140 anúncios lidos (23%) têm lotes**. `lotes_do_texto()` lê-os para
  `anuncios.lotes`, e o `--reler` encheu o acervo em 7 segundos. E o
  Excel tem o preço base **do lote** em cada linha: foi assim que 8 das
  12 linhas em anúncios com lotes ficaram com o lote certo
  (`casa.lote`), sem adivinhar — #95 e #96 da «biblioteca de
  artefactos» são os lotes 4 e 5, não os 2 e 3 que o nome sugeria. Das
  outras 4: #23 e #26 trazem o preço base do procedimento inteiro
  (foi-se a todos os lotes, ou a linha é o conjunto); #129 e #147 têm
  um preço base que não bate com lote nenhum — ele que diga. O #93 era
  um duplicado do #31 (sem proposta, sem perfis, e o «preço base» dele
  é a proposta do #31): ficou marcado como tal. O quadro continua a ter
  um cartão por anúncio sem saber de lotes; a separação em Ganho e
  Perdido faz-se quando o registo chegar ao ecrã.
- **Depois do Zoho** (a fonte mais actual do estado, lido pelo browser
  porque ele não consegue exportar CSV) e da validação, decide-se
  **como isto se monta no esqueleto** — a página, o bloco da ficha, o
  vocabulário dos estados («Não fomos», «passou sem decisão»,
  «cancelado») e se o radar passa a ser onde se escreve.

## O e-mail de alerta ficou «bonito», 2 de setembro de 2026

O Afonso mostrou o resumo tal como chegava à caixa de correio — texto
corrido, títulos cortados aos 88 caracteres («…Software-as-a-Service
(SaaS» a meio), as ligações a azul do cliente — e pediu que ficasse
bonito. Foi feito nesta sessão, sem mexer no que se avisa nem em quando.

- **`html_do_resumo()`** produz o mesmo resumo em HTML: cabeçalho em
  ardósia com a contagem e a hora, um bloco branco por secção (cada
  alerta, os alterados, as seguidas), e um cartão por anúncio com o
  título inteiro a ligar à ficha, a entidade, e a linha do ref, prazo e
  preço base. O prazo leva a pílula da lista — verde folgado, laranja
  dentro da janela do urgente, vermelho expirado ou a acabar hoje —
  pela mesma `etiqueta_prazo()` e a mesma `dias_urgente()`, para o
  e-mail nunca dizer uma cor diferente da do painel. Nos alterados o
  valor antigo vai riscado e o novo a negrito.
- **A mensagem vai em `multipart/alternative`**: o texto de sempre
  primeiro, o HTML depois (`enviar_email(..., html_corpo=)`). O
  `AVISOS.txt` continua a ser o texto; quem lê sem HTML vê o que via.
- **Tudo em estilos em linha e tabelas**, sem `<style>`, fontes
  externas nem flex — é o que os clientes de e-mail percebem. As cores
  da paleta «ardósia e âmbar» estão copiadas à mão nas constantes
  `_EM_*`, porque o e-mail não lê o `CSS` do painel. Tudo o que vem da
  base passa por `html.escape`.
- **Onze testes novos** (`TestResumoEmHtml`, `TestEnvioComHtml`): o
  documento, as ligações em `href`, o escape, o título inteiro, os
  três estados do prazo, a cor da janela do urgente, os alterados, as
  seguidas, a estrutura de duas partes da mensagem (com um SMTP falso)
  — e um que segura os dois formatos juntos, comparando as ligações do
  texto e do HTML na mesma ordem. 621 testes, todos a passar (634 no
  fim do dia, com os das peças do DR).

Verificado com dados de exemplo num browser a 760px, a partir de um
ficheiro gerado pela função; **nenhum e-mail foi enviado nesta sessão**.
A primeira leitura a sério é no Gmail, quando o próximo resumo sair —
se o Gmail lhe torcer alguma coisa (costuma ser o `font` abreviado ou
o `border-radius`), é aí que se afina.

## Sete repositórios do Instagram, e o que daí sai para o radar, 2 de setembro de 2026

Um carrossel do @sebastianhardy_ («sell these 7 free repos») posto à
prova contra o que o radar já faz. Ficam as decisões, para não se
voltar a avaliar o mesmo:

- **trycompai/crm — não.** É um CRM de vendas B2B (pessoas, contas,
  deals, agente de pesquisa). O quadro do radar é o próprio anúncio do
  DR com prazo, CPV, alterações e peças; as fases pedem dados; o
  interesse é um recorte por CPV sobre 66 mil anúncios. Nada disso cabe
  num deal genérico. Onde um CRM faria sentido é na relação com as
  pessoas das entidades, e isso é decisão da CONKORD, não do radar.
- **PaddleOCR — sim, pelo RapidOCR.** Dos 12 CE/PC medidos, 2 são
  digitalizações (`texto_estado='scan'`) e a leitura pelo modelo nem
  arranca. O caminho já existe: `imagem_da_pagina()` renderiza a
  página, falta OCR e a marca `\f` entre páginas. O RapidOCR corre os
  mesmos modelos do PaddleOCR em ONNX (~50 MB, `pip install`); o
  PaddleOCR inteiro são centenas de MB numa pen a 42 MB/s. Só se passa
  ao PaddleOCR completo se o RapidOCR ler mal ou se as tabelas dos
  perfis exigirem o PP-Structure. Por fazer.
- **changedetection.io — a ideia sim, o programa não.** Para o DR o
  `reler_marcados()` já vigia prazo e preço base dos marcados, e as
  republicações ligam-se ao original. Faltava vigiar a **lista de
  documentos** na plataforma (esclarecimentos, erratas) dos anúncios
  marcados, com os obtentores que já existem e a fila `alteracoes` —
  **feito a 03/09/2026** (`vigiar_pecas()`, ver a secção do fim). Do
  changedetection não havia código a aproveitar: é uma aplicação
  inteira (Flask, datastore em JSON, fetchers, notificações por
  apprise) e o diff é `difflib`.
- **Scrapling — não.** O parser adaptativo serve HTML que muda, e o
  radar quase não parseia HTML (o DR responde JSON, a Vortal é API, a
  acingov dá um ZIP; só as páginas JSF, 9%). O único ângulo com valor
  seria o browser sem cabeça a renovar o token das capturas, e a
  medição abaixo provou que não é preciso browser nenhum.

## O token não expira: as peças do DR renovam-se sozinhas, 2 de setembro de 2026

Três voltas do `medir_captura.py` (corrido no PC pelo Afonso; o DR não
responde do ambiente remoto), contra o portal verdadeiro, com o
`curl_DR.txt` de 23/08 como controlo. O que se mediu, por ordem:

1. **Só o `x-csrftoken` tranca.** Sem ele, a casca HTML de 2346 bytes.
   Sem cookie nenhum, passa. Com a `moduleVersion` errada, passa. O DR
   já tinha republicado a aplicação desde a captura
   (`hasModuleVersionChanged: true` em todas as respostas) e respondia
   na mesma.
2. **O token não é de sessão: é uma constante pública.** Está escrito
   em `/dr/scripts/OutSystems.js` como
   `AnonymousCSRFToken="T6C+9iB49TLra4jEsMeSckDMNhQ="`, e é exactamente
   o da captura (o `crf=` do cookie `nr2Users` é o mesmo valor, com o
   `+` escrito `%2b`). Com cookie, o DR verifica o cabeçalho contra o
   `crf` do cookie e um token inventado cai; **sem cookie aceita até um
   inventado**. Foi por isto que a captura de 23/08 servia a 02/09: o
   token só muda quando o DR actualiza a plataforma OutSystems.
3. **A `apiVersion` é a única tranca real.** Errada, o DR responde JSON
   com `data: {}` e `versionInfo.hasApiVersionChanged: true`. Vive no
   script compilado do ecrã (`dr.Pesquisas.PesquisaResultado.mvc.js`,
   `callDataAction("DataActionGetPesquisas", "screenservices/…",
   "PRsQKjEXDVBC3ZSqkS8k6A", …)`), e esse script está listado com a
   versão em `manifest.urlVersions` do `/dr/moduleservices/moduleinfo`,
   que responde a um GET sem sessão (176 KB; o `versionToken` já era
   `Y0NBIj4uVIBdNjR3KejkaA` contra `9DeZ4j9NYEpfCiXfe3gDLw` da captura).
   O detalhe é igual: `dr.Legislacao_Conteudos.Conteudo_Detalhe.mvc.js`.
4. **A prova:** pesquisa e detalhe feitos com cabeçalhos mínimos
   (User-Agent, Accept, Content-Type, Origin, Referer, X-CSRFToken) e
   as três peças vindas dos GETs, sem nada da captura a não ser o corpo
   — 25 anúncios e 1 detalhe. A `apiVersion` errada de propósito, na
   mesma volta: zero.

**O que mudou no `radar.py`:** uma banda nova, «as peças do DR
renovam-se sozinhas». `renovar_pecas_dr()` faz os três GETs
(moduleinfo → OutSystems.js → script do ecrã), com cache por processo
(6 h) e `forcar`; `pedido_renovado()` tira o Cookie e põe o token, a
`moduleVersion` e a `apiVersion` por cima da captura; e
`perguntar_ao_dr()` é a **porta única** dos quatro POST ao portal
(`recolher`, `ler_detalhe_de`, `ler_detalhes`, `reler_marcados`): se
vier a casca ou `hasApiVersionChanged`, renova à força e repete uma
vez; só se falhar as duas é que `registar_expiracao_token()` grava,
com a razão (`casca`/`apiVersion`). Sem rede para os GETs (ou se o DR
mudar de forma) o pedido segue com a captura tal como está — o
comportamento de sempre —, e a falha da renovação fica em
`pecas_dr_ultimo_erro`, ligada aos indicadores. A captura fica a servir
pela **forma do corpo** (as variáveis do ecrã), que não expira.
Treze testes (`TestPecasDoDR`), incluindo um que recusa um
`requests.post` solto nas quatro funções. 634 testes.

**O que já se sabia e ficava por explicar:** a captura de 23/08 nunca
tinha expirado em 10 dias, e o E4 (registo da expiração) nunca disparou.
Agora sabe-se porquê. O `medir_captura.py` e o `medir.bat` ficam como
instrumento: se o DR mudar, é por aí que se volta a medir.

## Auditoria UX pelas «leis», 2 de setembro de 2026

Pedido do Afonso, a partir de uma lista genérica de vinte «leis de UX»
que perguntou se se aproveitava. A resposta foi que sim, mas como lente
e não como regras: as da casa são mais específicas e nasceram de erros
reais. Ele levantou a dúvida certa («as regras que implementámos podem
estar erradas») e a auditoria é a resposta: `UX-Auditoria.md`, com
cada regra de interface do CLAUDE.md passada pelas leis e um veredicto
(manter, afinar, dívida), mais os achados que nenhuma regra cobria.

Feita sobre uma **base de ensaio** de 40 anúncios fictícios (nunca a
verdadeira), num Chromium sem cabeça a 1366 e 1920, sobre 16 páginas,
com um script a medir alvos, texto pequeno, contraste por elemento
contra o fundo real e os fluxos de triar. **Nada mudou no código.**

O que a medição apanhou e vale registar aqui:

- **A regra do contraste estava incompleta.** `--papel` não é o pior
  fundo: as colunas do quadro são `--linha2`, mais escuro, e os três
  «pede o preço proposto» de 01/09/2026 estão a **4,35:1**. Todas as
  outras páginas ficam entre 4,66 e 5,12. Corrigido no CLAUDE.md; a
  cor fica para o P0 do BACKLOG.
- **Alvos de 11 px de altura**: «voltar a por ver» (85×11), «no
  calendário» (75×11), «Pôr por ver» (63×12), «Ver no DR» (57×12),
  «mudar» (34×13). A regra da cor mediu-se a 31/08; a área nunca.
- **Triar não confirma nem deixa desfazer**: zero avisos depois de
  «interessa» e de «abandonar», e o caminho de volta é ir à outra aba.
- **A lista abre com 60% do ecrã em filtros** a 1366×768 (o primeiro
  cartão aos ~460 px, 11 campos, 42 alvos na dobra).
- **O quadro pinta «prazo expirado» a vermelho** em 4 dos 9 cartões, e
  os 4 estão em fases pós-submissão, onde é o estado normal.
- **A folha do Google Fonts é render-blocking**: 12,6 s até ao DOM
  neste ambiente sem saída para o domínio, com o servidor a responder
  em 5 a 16 ms. «Sem rede continua legível» é verdade depois do
  timeout, não antes.
- **O «essencial» da ficha de um por ver tem 8 linhas em 12 a dizer
  que o valor só consta das peças.**
- **Os indicadores têm 3 ligações**: 2 dos 4 KPI ligam a listas, o
  funil não liga a nada.
- O que se confirmou a funcionar como escrito: estado vazio com
  «limpar», data inválida avisa, 404 dentro da aplicação, contadores
  das abas dentro do filtro, uma acção primária por bloco, sem JS o
  POST segue, janela do urgente única.

O arrasto do quadro sai da lista das «regras» e passa a **dívida
assumida**: a lei do feedback tem razão, e o remendo (recarregar) só
existe porque o servidor não devolve o cartão redesenhado. As
propostas e a ordem estão na Parte 4 do `UX-Auditoria.md`; cinco delas
pedem decisão dele (filtros recolhidos, essencial encurtado, teclado)
e o resto é meia jornada sem mudar hábitos.

## As digitalizações lêem-se por OCR, 2 de setembro de 2026

> **Revertido a 03/09/2026** — ver «O OCR e a vigilância das peças
> saíram», no fim deste ficheiro. O que está aqui é o registo do que se
> fez e mediu, e vale para quem o quiser repor; não descreve o radar de
> hoje.

O buraco medido em Agosto: dos 12 Cadernos de Encargos e Programas
reais, 2 são digitalizações sem camada de texto, ficavam em
`texto_estado='scan'` e a leitura pelo modelo nem arrancava («os
documentos deste concurso são digitalizações»). Um em seis, e são os
das entidades mais pequenas.

**O que se mediu antes de escrever**, num PDF sintético de duas páginas
A4 a 150 dpi com texto português (cláusula, cedilhas, «175.000,00
EUR»), aqui, em CPU:

- **`rapidocr_onnxruntime` 1.4** (16 MB, modelos chineses/ingleses):
  lê tudo mas perde os acentos («Clausula», «execucäo») e leu
  **«175.oo0,00»**, que o `euros_do_texto()` não come. A 2× não
  melhora. Não serve.
- **`rapidocr` 3.9** (27 MB): o modelo que a própria roda traz
  (`PP-OCRv6_rec_small`, dicionário de 18 708 caracteres com ç, ã, é,
  õ) lê as 10 linhas em 10, acentos inteiros e o preço certo, com
  confiança ≥ 0,98. **Não descarrega nada** — importa porque os
  espelhos dele (ModelScope, Hugging Face, GitHub releases) estão
  bloqueados deste ambiente, e na pen seria uma dependência da rede no
  primeiro uso. 0,4 s a arrancar, **~5 s por página**: uma peça de 27
  páginas são uns dois minutos, em thread de fundo.
- O PaddleOCR inteiro nem se instalou: são os mesmos modelos, com
  centenas de MB de framework por cima. Só se voltará a olhar para ele
  se as tabelas dos perfis pedirem o PP-Structure.

**O que mudou no `radar.py`**, banda «OCR das peças digitalizadas»:

- `motor_ocr()` carrega o RapidOCR uma vez por processo, e só quando há
  mesmo o que ler; se não estiver instalado ou não arrancar, a razão
  fica em `ocr_ultimo_erro` (indicadores) e não se volta a tentar nesse
  processo.
- `texto_por_ocr()` desenha cada página com o PyMuPDF (o mesmo do
  visualizador, a 2×), passa-a ao motor como imagem BGR e junta as
  linhas com a marca `\f` de sempre — a ficha e a análise não sabem
  que veio do OCR, excepto onde se diz de propósito.
- **Os estados**: `ok` (pypdf), `ocr` (texto pelo OCR), `scan` (sem
  camada de texto e **ainda sem OCR tentado**), `imagem` (o OCR correu
  e não achou texto). `extrair_textos()` ganhou uma segunda passagem:
  os `scan` com ficheiro em disco vão ao OCR quando há motor, uma vez
  por documento; um `scan` sem ficheiro ou sem motor fica como está.
  Os ZIPs com PDF digitalizado lá dentro também. Quem consome texto
  (`documentos_com_texto()`) pergunta por `IN ('ok','ocr')`.
- A ficha diz «Texto extraído da peça (por OCR)» e avisa que pode ter
  erros; a análise, quando não há texto, distingue «OCR por instalar»
  de «o OCR não encontrou texto»; a saúde dos indicadores tem a linha
  «OCR das digitalizações». `"ocr": false` no config.json desliga.
- `requirements.txt` ganhou `rapidocr` e `onnxruntime` (o rapidocr não
  declara o onnxruntime). Uma armadilha: o `omegaconf` que ele puxa
  compila o `antlr4` 4.9 do código fonte, e neste ambiente (setuptools
  do Debian) a compilação falha; instalou-se à mão. Na pen é para
  medir; se falhar, `--no-build-isolation`.
- **Onze testes** (`TestOcrDasPecas`) com um motor falso: as páginas
  pela marca, a imagem a cores, sem motor fica `scan`, sem texto dá
  `imagem`, a segunda passagem só com ficheiro, o `scan` novo lê-se
  na mesma chamada, desligado no config não faz nada, o ZIP, o que
  conta para a análise, o que a ficha diz, a marca na saúde. **646
  testes.** O motor verdadeiro mediu-se à parte, sobre o PDF sintético,
  de ponta a ponta pela mesma `texto_por_ocr()`: 2 páginas, 9 s, texto
  certo.

**`--ocr [ref] [tudo]`** lê pelo OCR os `scan` que já estavam na base
(a segunda passagem só corre quando alguém pede as peças DESSE
anúncio, e os antigos ficavam à espera de uma ficha aberta), e diz o
tempo de cada documento: é o instrumento para medir o custo por página
no PC. Com `tudo` relê também as que já estão em `ocr` e as `imagem` —
é o que faz uma escala nova chegar ao acervo (03/09/2026, ver a secção
do fim). `ocr_pendentes()`, com teste.

**Instalar na pen** (medido a 02/09/2026): o Python embutido não tem
pip e o `._pth` ignora o `PYTHONPATH`, por isso o ambiente isolado de
compilação do pip não vê o `setuptools` e o `antlr4` (a única
dependência sem roda pronta) não compila. A receita que funcionou, com
o pip como ficheiro único e a instalar para `libs\`, como o resto:

    curl -o pip.pyz https://bootstrap.pypa.io/pip/pip.pyz
    python\python.exe pip.pyz install --target libs setuptools wheel
    python\python.exe pip.pyz install --target libs --no-build-isolation --upgrade rapidocr onnxruntime

Instalou o rapidocr 3.9.2, o onnxruntime 1.29 e o opencv 5.0 (uns
100 MB em `libs\`) e o `import rapidocr, onnxruntime` respondeu «ok».
**Medido no PC, 02/09/2026, com o `--ocr`**: os três `scan` da base
leram-se todos. O CE do 20968/2026 (20 páginas, 30 365 caracteres) e o
Programa do mesmo anúncio (12 páginas, 24 036) levaram 896 s na mesma
passagem, e o `[CA]_20260817_DAG-UAP_N_0696.pdf` do 21295/2026 (6
páginas, 10 482) levou 168 s: **~28 s por página no PC**, contra 5 s
no ambiente remoto. Um CE de 20 páginas são 10 minutos, em fundo. É
caro mas é raro (2 em 12), e o alternativa era não ler. O aviso «text
detection result is empty» é uma página em branco, e é inofensivo.

**Estes 28 s por página não se reproduzem** (03/09/2026, no mesmo PC).
Com o mesmo `--ocr` e numa escala *mais alta* (2,5), um Programa de 24
páginas levou 199 s — **8,3 s por página**; isolado, só render e
reconhecimento com o motor já carregado, são 6,0 s por página. Não sei
o que deu os 28 s: nada no código faz trabalho a mais (o
`extrair_textos()` só toca nos `scan`, sem reprocessar as outras peças
do anúncio), e as causas que sobram — plano de energia, outra coisa a
correr ao mesmo tempo, o motor a vir frio da pen — já não se
distinguem depois do facto. Fica escrito que o número medido é 8 s por
página pelo `--ocr` e 6 s isolado, e que o de 02/09 não se explicou.
Um CE de 20 páginas são 2 a 3 minutos, não 10. A escolha da escala
deixa de ter o tempo como argumento — ver a secção seguinte.

## P0 e P1 da auditoria UX aplicados, 2 de setembro de 2026

À ordem do Afonso («avança com P0 e P1»), na mesma sessão da auditoria.
Seis alterações no `radar.py`, todas pequenas e nenhuma a mudar hábitos:

- **Contraste (P0).** `.coluna-pede` de `--t5` para `--t4`: 5,12:1
  sobre a coluna do quadro. E a regra ficou escrita como é: a escala do
  texto tem dois patamares, `--t1`..`--t4` para qualquer fundo claro,
  `--t5`/`--t6` só para branco e `--creme`. Um teste calcula os
  contrastes a partir do próprio `CSS`.
- **Alvos de texto a 24px.** Seis selectores com `padding` até aos 24px
  e margem negativa vertical, letra igual. Teste por selector.
- **Triar avisa e deixa desfazer.** O `.flash` que já servia o
  «Verificar agora» passa a dizer «título» marcado como interessa /
  abandonado (motivo) / reposto em por ver, com um botão «desfazer» que
  faz o POST inverso. Se o estado anterior era um abandono, o motivo
  vai na acção; `mudar_estado()` lê `request.values` por isso.
  `_volta_com_aviso()` limpa o aviso anterior da query string.
- **Prazo neutro a partir do Submetido.** «prazo 03/08/2026» sem cor
  nas `FASES_COM_PROPOSTO`; antes disso, a etiqueta de sempre.
- **Fontes sem bloquear.** `media="print" onload="this.media='all'"`
  na folha do Google Fonts, com a normal em `<noscript>`.
- **O quadro deixou de recarregar.** `/quadro/mover` devolve o cartão
  redesenhado (`cartao()`) e a `conta_da_coluna()` das duas colunas; o
  `drop` troca só isso e volta a ligar o arrasto ao nó novo. O
  guardar/repor do rolar horizontal saiu com o `reload()` que servia.
  A classe de testes do arrasto foi reescrita: era a regressão do
  comportamento antigo e o comportamento mudou de propósito.

**652 testes, todos a passar** (621 antes; 13 vieram com o merge do
master, 18 são destes). Uma armadilha paga a meio: um teste que marca
«interessa» pelo cliente Flask põe as peças na fila, e a fila é uma
thread que abre a base — a base do teste **seguinte**, que aparecia
«locked» sem razão visível. O teste substitui `pedir_documentos` por
nada; um teste que passe sozinho e falhe na bateria é sinal disto.

Não se repetiu a medição do browser depois das alterações. O que
espera decisão dele continua no BACKLOG (filtros recolhidos, essencial
encurtado, teclado).

## A escala do OCR mede-se pelos valores, 3 de setembro de 2026

> **Revertido a 03/09/2026** — ver «O OCR e a vigilância das peças
> saíram», no fim deste ficheiro. O que está aqui é o registo do que se
> fez e mediu, e vale para quem o quiser repor; não descreve o radar de
> hoje.

Ficou o ponto A: olhar para a qualidade do texto lido pelo OCR e
decidir se o `OCR_ESCALA` fica em 2,0 ou desce para 1,5 (o argumento
para descer era o tempo). **A resposta é nenhuma das duas: subiu para
2,5.** E o caminho até lá é mais útil que o número.

**A qualidade a 2,0 não era uniforme.** No CE do 20968/2026 (20
páginas), 21 de 596 linhas saíam desfeitas em letras soltas — 3,5% —, e
no Programa do mesmo anúncio 20 de 426. Não é ruído espalhado: são
linhas inteiras que se perdem, com o texto ao lado perfeito, acentos
incluídos. Uma delas era a **cláusula 4, «Preço Base»**, que saiu
`a      s          d   al / em vigor.`; outra o título da cláusula 3
(«Ints o nas a no n so o nados»); e o cabeçalho da entidade, certo em
17 páginas, saiu «SERS  A S ZS TO» em três.

**A varredura, de 1,0 a 4,0, sobre o documento inteiro.** A métrica
começou por ser «linhas desfeitas» (proporção de palavras de uma letra
só), contada sobre as 20 páginas e reprodutível ao caractere — a
releitura a 2,0 deu exactamente as mesmas 20 linhas que já estavam
guardadas na base:

    escala   s/pág   linhas desfeitas   chars   preço base   tabela «≥170 cv»
    1,0       3,9         8 (1,4%)      30 159      ok            «110»
    1,25      4,2        13 (2,2%)      30 214      ok            «110»
    1,5       3,6        11 (1,9%)      30 071      ok             «10»
    1,75      4,9        22 (3,7%)      29 543      ok       «170» (sem o ≥)
    2,0       5,1        20 (3,4%)      29 731   PERDIDO           ok
    2,5       6,0        22 (3,7%)      29 741      ok             ok
    3,0       5,5        24 (4,0%)      29 409      ok             ok
    4,0       6,0        23 (3,9%)      28 781      ok             ok

Pela métrica, descer a escala melhorava tudo ao mesmo tempo: um terço
das linhas desfeitas, mais caracteres lidos e 30% mais rápido. **A
métrica estava a premiar o erro.** Abaixo de 2,0 o modelo não desfaz a
linha — adivinha-a: onde a página 14 diz «Potência mínima | cv |
≥170», o 1,0 e o 1,25 leram **110** e o 1,5 leu **10**. Confirmado a
olho, desenhando a página a 3× e lendo-a (é a única forma de ter
verdade num PDF sem camada de texto), e o preço base cruzado com o
`anuncios.preco_base` do DR: 150.000,00 EUR, e o 1,5 leu «€150 000
(cento e cinquenta mil euros)» certo. Uma linha desfeita vê-se; um
«10 cv» lê-se como dado, passa pelo `euros_do_texto()` e pelo modelo
sem levantar nada. **A regra que fica: a escala decide-se pelo valor
confirmado na página, nunca pelo aspecto do texto** — uma métrica que
conta a falha visível classifica melhor a configuração que a converte
em erro silencioso, porque o erro silencioso não aparece nela.

**Segundo documento, para o número não descansar em três linhas de um
só.** O `[CA]_20260817_DAG-UAP_N_0696.pdf` do 21295/2026 (6 páginas)
aponta ao mesmo: 2,5 empata ou ganha em tudo (2 linhas desfeitas, 10
441 caracteres contra 10 257 do 2,0), e a data da assinatura digital
sai **2026**.08.06 14.39.17 a 2,5 e **2036**.08.06 a 2,0 — outro
número plausível e errado, e o nome do ficheiro diz 2026.

**Porque 2,5.** É a escala mais baixa onde os dois documentos lêem
certo todos os valores que se confirmaram; o 2,0 anterior perde a
cláusula do preço base inteira, o «artigo 332.º do CCP» e o cabeçalho
de uma página; acima de 2,5 não se ganha nada e começam a perder-se
caracteres (28 781 a 4,0). Custa 6,0 s por página isolado, contra
5,1 s do 2,0: **uns 18% mais caro**, num trabalho que corre em thread
de fundo e acontece em 2 de 12 peças. Os 664 testes de então passam —
o teste do OCR usa um motor falso, e a escala é argumento por omissão
do `texto_por_ocr()`.

**Duas digitalizações novas apareceram na base** e leram-se agora, à
escala nova: o Programa do 22001/2026 (24 páginas, 60 966 caracteres,
199 s → 8,3 s/página) e o `2_programa_de_concurso_I.pdf` do 22102/2026
(14 páginas, 23 045 caracteres, 107 s → 7,6 s/página). São as duas
medidas do `--ocr` a 2,5 que sustentam os «8 s por página» acima.

**`--ocr tudo`, para a escala nova chegar ao acervo.** Uma escala nova
não vale nada se as peças já lidas ficarem com o texto da antiga, e o
`--ocr` sozinho só apanha os `scan` — quem está em `ocr` nunca mais é
relido. Com `tudo` entram também os `ocr` e os `imagem`, e cada
documento volta a `scan` **imediatamente antes** de ser relido, um a
um: assim a releitura passa pelo caminho de sempre (a segunda passagem
do `extrair_textos()`) em vez de ter um seu, e uma interrupção a meio
deixa o resto como estava. O teste
(`test_ocr_tudo_rele_as_que_ja_estavam_lidas`) trava precisamente o
erro que isto pode ter: o `tudo` devolver um documento a `scan` e
deixá-lo lá sem texto, que é pior do que o texto velho.

Correu sobre os 8 documentos do acervo digitalizado (94 páginas, 688 s
→ **7,3 s/página**, a confirmar os 8 s). Verificado na base depois da
releitura: o CE do 20968/2026 tem agora o «€150 000», o «artigo
332.º», o «Veículo Tipo Pick-Up», o «≥170» e o cabeçalho da entidade
nas 16 páginas onde ele existe; o `[CA]` do 21295/2026 tem
«2026.08.06» e já não tem «2036». O que a 2,0 se perdia está lá.

## As peças novas na plataforma avisam-se, 3 de setembro de 2026

> **Revertido a 03/09/2026** — ver «O OCR e a vigilância das peças
> saíram», no fim deste ficheiro. O que está aqui é o registo do que se
> fez e mediu, e vale para quem o quiser repor; não descreve o radar de
> hoje.

O `reler_marcados()` vigia o prazo e o preço base na página do DR. Mas
**um esclarecimento ou uma errata não passam pelo DR**: aparecem na
lista de documentos do procedimento, na plataforma, e só se dava por
eles abrindo a plataforma à mão. `vigiar_pecas()` faz do lado das
plataformas o que o `reler_marcados()` faz do lado do DR.

**Encontrou trabalho à primeira passagem, e não era um caso de
laboratório.** O **21830/2026** — «Subscrição de licenças de software
Microsoft (modelo CSP)», Metropolitano de Lisboa, base 158 300 €, no
quadro em «Por analisar», **prazo 03/09/2026, ou seja o próprio dia** —
tinha três peças na plataforma que não estavam na base:
`Caderno de encargos - P049_2026_REV.pdf`,
`Anexo III - Programa - P049_2026_REV.xlsx` e
`Resposta a pedido de esclarecimentos - P049_2026.pdf`. E a resposta
tem conteúdo: o CE indicava a referência Microsoft
`CFQ7TTC0LF8Q:0001`, que é **Office 365 E1**; a entidade confirma que
o que quer é **Office 365 E3 (com Teams)**, diz que a referência era um
lapso e que foi eliminada nas peças revistas. Quem orçamentasse pelo CE
original orçamentava o produto errado.

**O `obter_documentos()` não serve para vigiar, e é a primeira coisa a
saber.** Faz `DELETE FROM documentos WHERE ref=?` e volta a trazer
tudo: usá-lo para comparar apagava o texto já extraído e os veredictos
do OCR, e mandava as ~7 s por página de cada digitalização outra vez.
Vigiar é **ler a lista e trazer só o que falta**, e por isso há
`pecas_disponiveis()`, que devolve `[(nome, buscar)]` — o `buscar` é
uma função que só se chama para as peças novas. Cada plataforma dá o
que dá:

- **vortal** — os nomes vêm na resposta JSON (`documentList` do
  primeiro salto, ou o `GetContractNoticeDocuments` do segundo), sem
  descarregar nada;
- **acingov** — a lista **é** o ZIP: não há endereço de listagem (a
  página do procedimento exige sessão, medido a 01/09/2026), por isso
  o ZIP vem para memória e lê-se o `infolist()` dele. É a plataforma
  cara de vigiar, e não há alternativa sem sessão iniciada;
- **anogov/ComprasPT/ESPAP** — os endereços estão na página, mas o
  nome só vem no `Content-Disposition` de cada descarga:
  `_nome_sem_corpo()` abre o pedido em stream e fecha-o depois dos
  cabeçalhos, sem ler o corpo.

**O recorte é o mesmo do `reler_marcados()`** — «interessa» ou com fase
no quadro, prazo aberto — e por cima disso **só os que já têm peças
trazidas** (`docs_estado` em ok/parcial). Esta última condição não é
arrumação: os dois refs que o Afonso deu para ensaiar (20666/2026 na
acingov, 19127/2026 na Vortal) têm `docs_estado` a NULL, e sem a
guarda as 12 peças deles contariam todas como novidade no primeiro
resumo. Uma lista vazia **não** é «as peças desapareceram» — é a
plataforma em baixo, e não avisa nada (a mesma regra do
`diferencas_do_detalhe()`: só se avisa o que tem valor dos dois lados).

**Uma peça avisada não se avisa duas vezes.** A guarda óbvia é a peça
passar a estar na tabela `documentos`, e é o que acontece quando se
consegue trazer. Mas um ficheiro acima do tecto (`MAX_FICHEIRO`) não se
traz — e sem uma segunda guarda o mesmo anexo saía no resumo a cada
verificação, duas vezes por dia, para sempre. Por isso o
`_guardar_pecas_novas()` também olha para as linhas que já estão na
fila `alteracoes` com `campo='peca_nova'`. Há teste para o caso do
ficheiro que não se consegue trazer, precisamente porque é o que
repetiria.

No resumo, `peca_nova` tem caso próprio no texto **e** no HTML, como o
`retificacao` já tinha: o `antes` é vazio e « → Errata.pdf» não se lê.

**Medido na base a 03/09/2026**: dos 11 marcados que passam o recorte,
**10 dão zero peças novas** — a comparação por nome bate exactamente, e
a base tem sempre uma peça a mais que a plataforma, que é o
`Anúncio DR.pdf` que o radar acrescenta e a plataforma não tem
(`PECAS_DO_RADAR`, excluído; sem isso contava como novidade a cada
volta). O 11.º é o 21830/2026 acima. Segunda passagem: 0 novas, fila
com as mesmas 3 linhas.

Corre na verificação, depois do `reler_marcados()` e **antes** dos
alertas — para as peças novas entrarem no resumo do mesmo dia —, com
falha isolada: uma plataforma em baixo não dá a verificação por
falhada. Quantos por volta em `pecas_vigiadas_por_volta` (10 por
omissão). Os erros vão para a marca `docs_ultimo_erro`, que os
indicadores já mostram como «Último erro ao trazer peças» — não se
criou marca nova sem ecrã que a leia. Sete testes
(`TestVigilanciaDasPecas`), 672 no total.

**O que fica em aberto**, e é decisão dele: a leitura pelo modelo
**não** se repete quando chega um CE revisto — o `objecto`, a `equipa`
e a `proposta` continuam a ser os que se leram do CE antigo, e no
21830/2026 o CE antigo tinha a referência errada. E há três anúncios
`descartado` com fase no quadro, que o `reler_marcados()` já vigia
hoje: «abandonado mas no quadro» é uma contradição que ninguém decidiu.


## O OCR e a vigilância das peças saíram, 3 de setembro de 2026

Decisão do Afonso, no dia a seguir a as duas terem ficado prontas.
A pergunta que ele fez foi «acredito que não houve uma mais-valia para
a aplicação», e a base deu-lhe razão em números:

| | |
|---|---|
| Documentos em disco | 182 |
| Lidos pelo OCR | **8** |
| Anúncios que a vigilância vigiava | **6** (os `interessa`) |
| Anúncios na base | 66 387 |
| **Sem detalhe lido** | **60 215 (91%)** |

Nenhuma das duas estava mal feita. O OCR lia português com acentos à
escala 2,5 e tinha as medidas todas escritas; a vigilância comparava a
lista das plataformas com a tabela `documentos` e tinha sete testes. O
problema é onde estavam: **na ponta mais estreita de um funil que
recebe 80 detalhes por dia e tem 60 mil por ler.** Só se chega ao OCR
depois de trazer as peças, e só se trazem peças depois de marcar
«interessa» — e havia seis.

**O que saiu do `radar.py`** (13 863 linhas, eram 14 307):

- a banda «OCR das peças digitalizadas» inteira — `motor_ocr()`,
  `texto_por_ocr()`, `ocr_ligado()`, `ocr_instalado()`, `OCR_ESCALA`;
- `ocr_pendentes()` e o comando `--ocr`;
- a segunda passagem do `extrair_textos()` e o `motor` do
  `texto_do_zip()`;
- a banda «vigiar a lista das peças» — `vigiar_pecas()`,
  `_guardar_pecas_novas()`, `CAMPO_PECA_NOVA`, `PECAS_DO_RADAR` — e os
  ajudantes que só ela usava: `pecas_disponiveis()`,
  `_nome_sem_corpo()`, `_buscar_do_endereco()`, `_buscar_do_zip()`;
- a volta que a `verificar()` dava à vigilância, o caso `peca_nova` nos
  dois resumos, a linha do OCR na saúde dos indicadores e a marca
  `ocr_ultimo_erro`;
- a chave `"ocr"` do config e o `rapidocr`/`onnxruntime` do
  `requirements.txt`.

**O que ficou de propósito.** O visualizador de peças —
`paginas_do_pdf_imagem()`, `imagem_da_pagina()`, `paginas_com_termo()`
— vivia debaixo do cabeçalho do OCR sem ser dele, e ganhou cabeçalho
próprio: é o que desenha a página no servidor e o que procura dentro
do PDF. E o `texto_estado='ocr'` continua a ser aceite por
`documentos_com_texto()`: os 8 documentos que o OCR leu têm texto a
sério, e apagá-lo seria perder dados por arrumação. `imagem` lê-se
como `scan`. Não se produz mais nenhum dos dois.

**Testes: 655, todos verdes em 18 s** (eram 673 com 13 saltados — os
saltados eram os do OCR). Saíram `TestOcrDasPecas` e
`TestVigilanciaDasPecas`; `test_os_indicadores_leem_as_oito_marcas`
passou a `…as_sete_marcas`.

**As dependências continuam instaladas em `libs/`** — o `onnxruntime`
são 45 MB e o `rapidocr` 32 MB, mais o opencv, o numpy e o shapely que
vieram com eles. Não se apagaram: é decisão dele, e recupera-se o
espaço com `python\python.exe pip.pyz uninstall rapidocr onnxruntime
opencv-python-headless shapely omegaconf --target libs`.

**A lição, para quando alguma destas voltar:** o que as fazia não valer
a pena não era o código — era não haver anúncios marcados que
chegassem. Estão no git, com as medidas: `git show 8963251` (OCR),
`01e13bb` (a escala), `31fd388` (vigilância).
