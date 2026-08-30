# Estado do projecto, para quem pegar nisto a seguir

Última actualização: 30 de agosto de 2026.

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

Funciona. A base tem ~5100 anúncios, **todos com detalhe lido**, a
cobrir os últimos 60 dias.

Chegou a ter 65 819 (dois anos de histórico) e o Afonso mandou apagar o
que fosse mais antigo que 60 dias — decisão informada, com os números à
frente: saíam 92% das linhas, mas nenhum anúncio triado, nenhum
documento e nenhum histórico, porque nada disso existia fora da janela.
Ficou sem cópia, por escolha dele. Para voltar a ter histórico é
`python radar.py --historico 730`, e conta horas.

A janela é a mesma que a rotina usa (`detalhe_dias`, 60), e a razão é a
mesma: entre a publicação e o prazo vão ~18 dias em média, por isso mais
atrás que isso já fechou. O que ficar mais velho volta a acumular — a
limpeza não é automática.

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

Fica aqui porque **ainda não foi feito**, e é fácil dar por assente que
foi: tudo o que está acima mediu-se chamando os fornecedores
directamente. **A cadeia nunca correu pelo caminho normal do radar** —
`analisar_pecas()` a escrever na base, com o painel a mostrar o
resultado. O que falta confirmar, e como:

1. Com a Groq esgotada (ou com `"fornecedor_pecas": "nvidia"` no
   `config.json`), correr `python radar.py --ler-pecas` num concurso.
2. Abrir a ficha e confirmar que o campo do modelo diz **`nvidia:openai/gpt-oss-120b`**
   e não `groq:...`. É o sinal de que o `_perguntar()` desceu a cadeia e
   de que o `usado` chega mesmo à coluna `analise.modelo`.
3. Numa releitura em que só um fornecedor responda, confirmar que a
   coluna guarda **os dois** rótulos, separados por vírgula — é o
   `juntar_fontes()` a fazer pela coluna `modelo` o que já fazia pelas
   fontes. Está nos testes, mas nunca se viu na base verdadeira.
4. Confirmar que o ritmo normal (meia dúzia de concursos) não põe o
   NVIDIA em fila como a rajada dos testes pôs.

Enquanto isto não estiver feito, tratar a cadeia como **implementada e
testada em unidade, mas não exercitada em produção**.

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
cabeçalhos, o `x-csrftoken` e a forma do corpo.

Usar sempre **Copy as cURL (bash)**. O formato `cmd` escapa cada
caractere com `^` e **come os acentos**: o filtro `parte` chegava ao
servidor como `L - Contratos p blicos` e o DR devolvia zero sem se
queixar. Há código a repor esse valor (`VALORES_FIXOS`), mas é remendo.

O token vem da sessão do browser e há-de expirar. Quando isso acontecer,
o painel avisa em vez de mostrar lista vazia. A recaptura leva dois
minutos. Não há forma de evitar isto sem API.

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
consulta.

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

**`teste_radar.py`** — 118 testes, correm em milissegundos, sem rede nem
base de dados. Não são exaustivos de propósito: cada um corresponde a um
erro que existiu **mesmo**, e o comentário diz qual, para ninguém
"simplificar" de volta para o erro. Cobrem o prefixo de CPV, o escape do
LIKE, as duas caixas de pesquisa, a contagem de dias, `nome_seguro()`, o
parser de secções e a semeadora de fases.

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

Ficheiro único, `radar.py`, sem dependências além de `flask` e
`requests` (cresceu passado das 600 linhas originais com o dicionário
de CPV e a árvore no painel, mas continua um ficheiro só). Blocos, por
ordem no ficheiro:

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

O painel limita a tabela a 500 linhas por questão de apresentação. A base
não tem limite.

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
