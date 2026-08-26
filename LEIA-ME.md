# Radar de Concursos, Diário da República

Vigia a parte L da série II do Diário da República, filtra os anúncios
que interessam ao teu portefólio e mostra-os num painel local.
Verifica sozinho às 09:00 e às 17:00.

Fonte única: o serviço de pesquisa do próprio portal do DR.

---

## 1. Onde pôr a pasta

No ambiente de trabalho, como tinhas. Guarda tudo na mesma pasta:
o programa, a captura, a configuração e a base de dados.

Nota: se a pasta ficar dentro do OneDrive, a sincronização pode
bloquear o ficheiro `radar.db` no momento em que ele está a escrever.
Se um dia vires erros de base de dados bloqueada, é isto, e resolve-se
movendo a pasta para fora do OneDrive.

## 2. Primeira instalação

1. Duplo clique em `instalar.bat`. Instala o flask e o requests.
2. Faz a captura da secção 3.
3. Duplo clique em `iniciar.bat`. Abre o painel em `http://localhost:8765`.
4. Duplo clique em `agendar.bat`, uma vez só. Cria as tarefas das 09h e 17h.

## 3. As capturas

O DR não tem API pública. O radar faz as mesmas perguntas que o teu
browser faz, e para isso precisa de duas capturas, feitas uma vez.

### `curl_DR.txt`, a pesquisa

1. Vai a `diariodarepublica.pt`, escolhe **Anúncios, parte L** e pesquisa
   por `aquisição`, com datas dos últimos dias.
2. **F12**, separador **Rede**, filtro **Fetch/XHR**.
3. Carrega em **Filtrar** no site. Aparece na lista o `DataActionGetPesquisas`.
4. Botão direito nele, **Copy**, **Copy as cURL (bash)**.
   O formato `cmd` também serve, mas o `bash` preserva os acentos.
5. Abre o Bloco de Notas, Ctrl+V, e grava na pasta do radar com o nome
   `curl_DR.txt`. Em Tipo, escolhe **Todos os ficheiros**.

### `curl_detalhe.txt`, os campos de cada anúncio

O CPV, o prazo e o preço base não vêm na pesquisa, vêm da página de cada
anúncio. Para os obter falta uma segunda captura.

1. Abre um anúncio qualquer, por exemplo pelo link de um da lista.
2. **F12**, **Rede**, filtro **Fetch/XHR**, e depois **F5** para recarregar.
3. Procura o pedido `DataActionGetAllConteudoDetalheData`.
4. Botão direito, **Copy**, **Copy as cURL (bash)**.
5. Grava como `curl_detalhe.txt` na pasta do radar.

Sem esta segunda captura o radar funciona na mesma, apenas fica sem CPV,
sem prazo e sem preço base, e o filtro de CPV não devolve nada.

### O que é aproveitado

Os cabeçalhos, o token de segurança e a forma do pedido. As datas, o
termo de pesquisa e a página são substituídos a cada verificação. Na
captura do detalhe, o que muda é a chave do anúncio.

Quando o token expirar, o painel fica com o aviso a vermelho a dizer que
a captura pode ter expirado. Repete esta secção, leva dois minutos.

## 4. O que entra

Tudo. Todos os anúncios da parte L que o portal devolver na janela de
datas entram na base, sem juízo prévio. A triagem é tua, no painel.

No `config.json`, a única coisa que costuma valer a pena mexer é:

- `dias_catchup`: 15 dias. É a janela que o radar pede ao portal em
  **cada verificação de rotina** (as das 09h/17h). Serve também de rede
  se o PC estiver dias desligado. Não é o limite do que fica na base —
  ver "Histórico", abaixo.
- `detalhe_dias`: 60 dias. O radar só vai buscar os detalhes (CPV,
  prazo, preço) dos anúncios publicados nos últimos 60 dias, porque
  entre a publicação e o prazo vão ~18 dias em média e mais atrás do
  que isso já fechou. Os mais antigos são lidos quando abres a ficha.
  Põe a `0` se quiseres mesmo que ele leia tudo — demora horas.

Não há atalhos pré-definidos no ficheiro de configuração (nem de
palavra, nem de CPV) — tudo se escolhe na hora, no painel: a caixa de
palavras aceita o que escreveres directamente, e a árvore de CPV cobre
o que os atalhos faziam antes, sem precisar de editar ficheiros.

`paginas` é um tecto de segurança (5000), não um alvo: o radar pede
páginas ao portal até ele devolver menos que uma página cheia, e só
pára aí por engano se algo estiver mesmo a repetir para sempre.

Os `termos_de_pesquisa` estão a `[""]`, que quer dizer pesquisa sem
termo, ou seja, tudo. Os `termos_de_reserva` só entram em acção se o
portal recusar a pesquisa vazia.

## Histórico

A verificação de rotina (09h/17h) só olha para os últimos `dias_catchup`
dias — não vale a pena pedir mais que isso duas vezes por dia. Para
trazer um período maior de uma vez, corre:

```
python radar.py --historico 730
```

O número são os dias a recuar (730 ≈ 2 anos; omitido, usa 730). Isto
não mexe no `dias_catchup` da configuração, só faz uma recolha extra,
maior, uma vez. Para um período grande demora — uma página por segundo,
para não sobrecarregar o portal — e depois os detalhes (CPV, prazo,
preço) continuam a ser lidos aos poucos nas verificações seguintes, 40
de cada vez (`detalhes_por_volta`), até não sobrar nada por ler.

## 5. O painel

A lista vem sempre do mais recente para o mais antigo.

A barra de filtros trabalha sobre o que já está guardado, sem apagar
nada. Podes filtrar por:

- **nome do concurso ou objecto** e, em caixa separada, **entidade
  adjudicante**. Dentro de cada caixa, várias palavras separadas por `|`
  valem como "qualquer uma destas" (`outsystems|.net|java`); entre as
  duas caixas é "e", por isso podes pedir software *da* Autoridade
  Tributária sem apanhar tudo o que diz Tributária.

  Nota: procura pelo nome por extenso, não pela sigla. O DR escreve
  "Serviços Partilhados do Ministério da Saúde", nunca "SPMS".
- **CPV**, por início do código (`72` apanha todos os serviços de TI) ou
  por palavra da descrição oficial do CPV (`software`, `manutenção`).
  Tal como nas palavras, várias opções separadas por `|` valem como
  "qualquer uma": `72|manutenção de software`.
- **plataforma electrónica**: acingov, vortal, anogov, compraspt, ou os
  que não a indicam. Serve sobretudo para isolares aquelas de que o
  radar consegue trazer as peças sozinho.
- **intervalo de datas** de publicação.
- **estado**: por ver, interessa, descartados, ou todos.

Na lista, cada anúncio mostra a plataforma numa etiqueta: **a verde**
quando as peças se conseguem automaticamente, a cinzento quando tens de
ir ao site da plataforma buscá-las.

Os botões **interessa** e **descartar** servem para ires limpando a
lista. Descartar não apaga, arquiva, e podes sempre voltar a vê-los.

O **Exportar CSV** exporta exactamente o que o filtro está a mostrar,
não a base inteira.

Nota sobre o CPV e o prazo: esses campos não vêm da pesquisa, vêm da
página de detalhe de cada anúncio. Enquanto não estiverem preenchidos
(a coluna "Faltam ler os detalhes de N" no painel indica isso), o
filtro de CPV não devolve nada para esses anúncios em concreto.

O filtro de CPV percebe tanto código como palavra da descrição oficial,
porque a base traz embutido o vocabulário CPV completo (tabela
`cpv_dict`, importada uma vez de um ficheiro de referência). Se um dia
precisares de o actualizar para uma versão mais recente do vocabulário,
corre `python radar.py --importar-cpv caminho\para\ficheiro.json`, com
um ficheiro no formato `[{"codigo":"...", "descricao":"..."}]`.

Abaixo da caixa de filtro há **"Escolher CPV na árvore"**, com o
vocabulário CPV inteiro em hierarquia (divisão, grupo, classe...), cada
nó com a contagem de anúncios guardados nesse ramo. Escreve na caixa de
busca da árvore para filtrar por palavra (ela abre os ramos onde bate
certo), marca as caixas que interessam, e carrega em **"Aplicar
seleccionados ao filtro"** — isso escreve os códigos escolhidos, juntos
por `|`, e submete o formulário. Marcar um código grande (uma divisão
ou grupo) apanha automaticamente tudo o que está por baixo dele — não
é preciso marcar um a um.

A caixa de CPV em si já não aparece — é a árvore que a preenche por
baixo dos panos. Quando há um filtro de CPV a valer, aparece uma linha
"Filtro CPV activo: ..." com um link para o tirar sem mexer no resto.

## 6. A ficha do anúncio

Clicar no título de um anúncio — na lista, no quadro ou no calendário —
abre a ficha **dentro da aplicação**, já não o site do DR. Lá tens:

- os factos de topo: prazo com contagem de dias, preço base, plataforma,
  e o CPV já com a descrição por extenso;
- **as peças do procedimento** (Programa de Concurso, Caderno de
  Encargos, anexos), para abrir sem sair da aplicação;
- o **anúncio completo**, com contactos, critério de
  adjudicação, prazo de execução, tudo o que o DR publica.

**Essencial** mostra uma tabela com o que interessa para decidir: nome,
entidade, critério de adjudicação, preço base, duração, local, data de
submissão. O botão **Anúncio completo** abre as 28 secções em bruto.

Cinco campos aparecem assinalados como em falta — preço anormalmente
baixo, data de esclarecimentos, objecto detalhado, equipa e documentos
da proposta. Não estão no anúncio do DR: vivem no Programa de Concurso
e no Caderno de Encargos. Aparecem na tabela de propósito, para veres o
que falta em vez de parecer que não existe.

Se abrires um anúncio que o radar ainda não tinha lido — um antigo, por
exemplo — ele lê-o na altura, demora cerca de um segundo, e fica
guardado. Não precisas de esperar por verificação nenhuma.

Sobre as peças: o botão **Trazer peças** vai buscá-las à plataforma
indicada no anúncio. Também vêm sozinhas quando marcas **interessa** —
nesse caso a ficha mostra "a trazer as peças…" e actualiza-se sozinha
quando elas chegam, o que leva alguns segundos.

Funciona nas quatro plataformas que aparecem na base — acingov, vortal,
anogov e ComprasPT — o que cobre quase todos os anúncios que indicam
plataforma. O PDF oficial do anúncio vem sempre, seja qual for.

**Ficheiros muito grandes ficam de fora.** Alguns anúncios (sobretudo da
Infraestruturas de Portugal) trazem anexos técnicos de centenas de MB.
Acima de 60 MB o radar não os traz, diz-te quais são pelo nome, e marca
o anúncio como parcial — vais buscá-los pelo botão **Abrir plataforma**.

Não se descarrega tudo de uma vez de propósito: seriam centenas de GB.
Assim ficas com as peças daquilo em que trabalhas mesmo.

## 7. Quem está a trabalhar

No canto do cabeçalho escreves o teu nome. A partir daí fica registado
quem marcou interessa, quem moveu de fase e quem ficou responsável por
cada concurso — vês esse registo na ficha do anúncio, em baixo.

Na ficha podes também atribuir o concurso a uma pessoa.

Não há palavra-passe: isto corre no teu PC e é identificação, não
segurança. No dia em que isto for para um servidor partilhado, é aí que
entra o login a sério.

## 8. Indicadores

Botão **Indicadores**, na barra da esquerda. Números sobre o teu próprio
radar: quantos anúncios tens, quantos entraram hoje, quantos marcaste
como interessa (e destes, quantos têm prazo a menos de uma semana),
quantos ainda estão sem detalhe lido, como estão distribuídos pelas
fases do quadro, e o estado da recolha — se as capturas ainda são
válidas e que percentagem de peças se consegue por plataforma.

É tudo lido da tua base, não sai nada para fora.

## 9. O quadro

Botão **Quadro**, na barra da esquerda. Mostra os anúncios marcados
**interessa** organizados em colunas (fases), ao estilo Trello/kanban.

Começa com cinco fases — *Por analisar, A preparar proposta, Em
revisão, Submetido, Resultado* — mas são só um ponto de partida: muda
os nomes, acrescenta e apaga à vontade. Depois de mexeres nelas o
programa não volta a tocar-lhes.

- **Arrastar um cartão** para outra coluna move-o de fase.
- **+ Nova fase** cria uma coluna. O nome de cada coluna é editável, clica
  e escreve. O `×` no canto apaga a coluna — os cartões lá dentro voltam
  para a primeira coluna, não se perdem.
- **+ etiqueta**, em cada cartão, cria ou aplica uma etiqueta (com cor
  automática). O `×` ao lado da etiqueta tira-a desse cartão.
- Cada cartão mostra os dias até ao prazo de propostas, a verde, ou
  "prazo expirado", a vermelho.
- **Tirar do quadro** devolve o anúncio a "por ver" — sai do quadro sem
  apagar nada da base.

Marcar **interessa** num anúncio, na lista principal, põe-no
automaticamente na primeira coluna do quadro.

## 10. O calendário

Uma grade só de leitura, uma linha por anúncio interessado com prazo,
uma coluna por dia (45 dias a partir de hoje). Cada coluna mostra o dia
da semana, o dia do mês e o mês; os fins-de-semana aparecem sombreados
e o início de cada mês tem uma linha mais marcada.

A pílula na linha, na coluna certa, mostra a fase actual desse anúncio
no quadro — clica para abrir a ficha. Quem tem prazo já passado ou para
lá dos 45 dias não aparece na grade (fica contado numa nota por baixo),
mas continua no quadro.

## 11. Histórico de alterações

Duplo clique em `historico.bat`. Abre uma janela com todas as
alterações ao programa: à esquerda a lista, e ao clicar numa vês
exactamente que linhas mudaram, a verde e a vermelho.

Fica tudo **no teu PC**, dentro da pasta `.git`. Não há nada online e
não sai nada para lado nenhum.

Ficam de fora do histórico, de propósito: as capturas (levam o token da
tua sessão), a base de dados e a pasta `documentos/`.

Na linha de comandos, se preferires:

```bash
git log --oneline
```

## 12. Comandos, se precisares

O uso normal é o painel. Estes são para casos pontuais:

```bash
python radar.py --historico 730
```
Puxa 730 dias (2 anos) de anúncios de uma vez. Demora horas — é um
pedido por página, e depois um por anúncio para os detalhes.

```bash
python radar.py --reler
```
Reanalisa o texto que já está guardado, sem ir ao DR: recalcula CPV,
prazo, preço e plataforma. Segundos para a base toda. Só faz diferença
depois de o programa ser melhorado a ler os anúncios — não traz nada
de novo.

```bash
python radar.py --importar-cpv ficheiro.json
```
Carrega uma versão nova do vocabulário CPV.

```bash
python teste_radar.py
```
Corre os testes — 31 verificações em menos de um segundo, sem tocar na
rede nem na base. Vale a pena corrê-los depois de qualquer alteração ao
`radar.py`. Se o DR mudar o formato dos anúncios, é o teste do parser
que avisa primeiro.

## 13. Ficheiros

| Ficheiro | Para que serve |
|---|---|
| `radar.py` | o programa |
| `curl_DR.txt` | a tua captura, secção 3 |
| `config.json` | filtros e horários, criado no primeiro arranque |
| `radar.db` | os anúncios e os estados |
| `amostras/` | a última colheita e, se houver, a resposta que correu mal |
| `documentos/` | as peças dos concursos que foste buscar |
| `instalar.bat` | instala as dependências |
| `iniciar.bat` | abre o painel |
| `agendar.bat` | cria as tarefas das 09h e 17h |
| `verificar.bat` | o que as tarefas correm |
| `desinstalar.bat` | remove tarefas e pacotes |
| `historico.bat` | abre o histórico de alterações |
| `teste_radar.py` | os testes |

## 14. Limites, para não haver surpresas

O DR publica anúncios acima de certos valores. Ajustes directos e
consultas prévias abaixo dos limiares não passam por aqui: aparecem no
Portal BASE. Enquanto o IMPIC não te der acesso à API, essa parte fica
de fora.

O radar lê o anúncio, não as peças do procedimento. Para o caderno de
encargos continuas a ir à plataforma electrónica indicada no anúncio.
