# D1 — o HTML sai do `radar.py` · plano

> Para quem executar: um lote por sessão, num worktree (`git worktree add
> ../radar-d1 -b claude/d1-<lote> origin/master`, com o `.venv` ligado por
> atalho). **Nada entra no `master` sem passar os dois portões do §2.**

**Objectivo:** o HTML do painel passa de strings concatenadas no `radar.py`
para moldes Jinja em ficheiros, **sem mudar uma letra do que o browser
recebe**.

**Porquê Jinja:** já vem com o Flask (zero dependências novas), e escapa
sozinho. Hoje o escape é à mão (`html.escape(...)` em cada valor). Um
esquecido é uma falha de segurança, e com a concatenação nada o apanha.

**O que NÃO se faz (fica para depois, se fizer falta):**
- partir o `radar.py` em módulos. É outra dívida: os testes fazem 263
  `patch` sobre `radar.<nome>`, e mudar funções de sítio parte-os todos;
- mudar o aspecto, os textos ou o comportamento de um ecrã. Uma
  diferença no HTML é um defeito, mesmo que «fique melhor»;
- o inglês (EN). Vem a seguir a isto, e é por isto que fica barato.

## 1. Os números de partida (9/10/2026)

| | |
|---|---|
| `radar.py` | 41 745 linhas; a banda do painel vai da linha 14 765 ao fim (~27 mil) |
| rotas | 154 decoradores; 79 rotas GET |
| CSS dentro do Python | `CSS` (16 060–17 733, ~1 670 linhas) e `CSS_NOVO` |
| moldes de página em string | `BASE`, `PAGINA_ENTRAR`, `PAGINA_ERRO` |
| peças partilhadas | `envolver()`, `cartao()`, `cabecalho_de_pagina()`, `barra_das_abas()`, `NAV` |
| testes | 378 classes; 566 asserções sobre o HTML devolvido; 114 referências a `radar.CSS*`, `BASE`, `NAV` e `PAGINA_*` |

## 2. Os dois portões: «funciona como dantes» medido, não prometido

**Portão A — igualdade automática** (`ferramentas/igual.py`, feito na fase 0)

1. Monta a empresa inventada do `ferramentas/demo.py` numa base
   temporária, com três contas a sério (dono, gestor, membro).
2. Pede **todas as rotas GET** (79, mais as variantes da pergunta: 98
   pedidos) pelo `test_client` do Flask, com quatro perfis: de fora sem
   sessão, dono, gestor e membro. Leva ~4 segundos.
3. Grava cada resposta num ficheiro (`<pasta>/<perfil>/<pedido>`), com o
   código HTTP, o tipo e o `Location`.
4. **Compara duas gravações** e mostra o trecho onde cada linha se separa.
   Só normaliza o que está no `NORMALIZAR`, cada um com a razão escrita
   (o CSRF, o identificador de envio, o da visita, a `versao` da proposta,
   as horas **de hoje** e o `lastmod` do sitemap). Tudo o resto tem de ser
   **igual ao byte**.

Como se usa, num lote:

```bash
python ferramentas/igual.py --gravar /tmp/antes --codigo ~/Desktop/radar   # o master
python ferramentas/igual.py --gravar /tmp/depois                           # o ramo
python ferramentas/igual.py --comparar /tmp/antes /tmp/depois              # sai 1 se mudou
```

(O `--codigo` deve ser um worktree no `master`; a instalação serve
enquanto estiver no mesmo commit que o `origin/master`.)

Provado a 9/10/2026: o ramo contra si mesmo, com um minuto de intervalo,
e contra a instalação, dá «Iguais». Um espaço a mais numa frase das
Configurações é acusado em todos os ecrãs onde aparece.

Os tectos conhecidos: só vê os estados que a empresa inventada tem, e os
e-mails ainda não estão (entram no lote 3.11). É por isso que existe o
portão B.

**Portão B — o ensaio sobre as bases verdadeiras** (como na 4.ª ronda)

1. Cópia das bases para `~/Desktop/radar-ensaio-d1/` e painel na porta
   **8799**, sem correio, sem recolha e sem modelo.
2. O `igual.py` corre também contra essa cópia: o `master` e o ramo, os
   mesmos ecrãs com os dados reais.
3. **Tu abres o ensaio de fora**, por um *quick tunnel* da Cloudflare
   (`cloudflared tunnel --url http://127.0.0.1:8799`, o mesmo binário do
   `tunel.sh`): um endereço `https://….trycloudflare.com` que só existe
   enquanto o ensaio corre. Entras com a tua conta de sempre (é uma cópia
   da base). O `ao_endereco_certo()` não o manda para o `miragov.pt`,
   porque esse nome não está nos `DOMINIOS_DO_PAINEL`. Na cópia, o
   `endereco_publico` fica vazio, para nenhum link apontar para a
   produção. Percorres a lista dos ecrãs do lote (dou-ta em cada lote),
   no telemóvel e no computador. Só com o teu «está igual» é que o lote
   vai para o `master`.

**A regra de cada lote:**
`ensaio → portão A limpo → portão B limpo → o teu ok → PR → merge no master`.

**Lote a lote** (decisão dele, 9/10/2026): cada lote entra no `master`
logo que passa os dois portões, sem esperar pelos outros. O merge **não**
corta release: a release continua a ser decisão dele.

## 3. As fases

### Fase 0 — o portão (feita a 9/10/2026)
- `ferramentas/igual.py`, com os modos `--gravar PASTA [--codigo DIR]` e
  `--comparar A B`.
- `TestOPortaoDaIgualdade`: o que muda de pedido para pedido não conta;
  um espaço a mais acusa; uma data que não é de hoje não se normaliza; um
  pedido que só existe de um lado acusa; e nenhuma rota com parâmetros
  fica sem exemplo.
- Não muda nenhum ecrã, por isso não pede o portão B.

### Fase 1 — o que já é ficheiro de alma (1 sessão)
- `CSS` e `CSS_NOVO` saem para `estilo/radar-antigo.css` e
  `estilo/radar-novo.css`, lidos pelo `ler_estilo()` que já existe. O
  `CSS_TUDO` tem de dar **o mesmo hash** (`ETIQUETA_CSS` igual = prova).
- `BASE`, `PAGINA_ENTRAR` e `PAGINA_ERRO` saem para `moldes/*.html`,
  ainda com os `%(nome)s` de hoje. Mudar de ficheiro não muda a mecânica.
- Os nomes `radar.CSS`, `radar.BASE`, etc. **continuam a existir**
  (passam a ser lidos do ficheiro). Assim os 114 usos nos testes não
  mudam.
- Ganho: ~2 000 linhas fora do `radar.py`, com risco quase nulo.

### Fase 2 — a mecânica Jinja (feita a 9/10/2026)
- `MOLDES_JINJA` (escape automático ligado, `StrictUndefined`,
  `keep_trailing_newline`, `trim_blocks` e `lstrip_blocks`) e o
  `desenhar(molde, valores)`.
- Os três moldes de página passaram de `%(nome)s` a `{{ nome }}`, e as
  onze formatações com `%` a `desenhar(...)`, reescritas pela árvore
  sintáctica.
- **Por agora todos os valores entram como HTML já feito** (`Markup`):
  era o que o `%` fazia. Cada lote da fase 3 passa a texto o que é texto,
  e aí é o Jinja que escapa.
- **As macros das peças partilhadas (`cartao`, `cabecalho_de_pagina`,
  `barra_das_abas`, as barras) não se fizeram aqui, de propósito:** são
  funções de uma linha que recebem HTML pronto, e uma macro só ganha
  alguma coisa quando um ecrã em molde a chama. **Cada macro nasce no
  primeiro lote da fase 3 que a precisar**, e as funções Python ficam com
  o mesmo nome enquanto houver ecrãs em Python a chamá-las.

### Fase 3 — os ecrãs, um lote de cada vez (~10 sessões)
Do mais pequeno e isolado para o maior. Cada lote tem o seu plano curto
quando lá chegarmos. **Como se faz um lote** (aprendido no 3.1):
1. grava-se a saída das funções do ecrã no `master`, com combinações dos
   argumentos e texto com `'`, `"`, `<` e `&` (um script no scratchpad,
   que importa o `demo.py` e chama as funções dentro de um
   `test_request_context`) — apanha o que o portão A não visita (os
   erros depois de um POST, os ecrãs que pedem um cookie);
2. escreve-se o molde, e o Python passa ao `ecra()`, com o texto como
   texto e o HTML feito como `Markup`;
3. compara-se: as combinações e o portão A têm de dar «Iguais».


| Lote | Ecrãs | Porquê nesta ordem |
|---|---|---|
| 3.1 | entrar, convite, repor, esqueci-me, segundo factor — **feito a 9/10/2026** (o erro ficou com o `desenhar()`: os seus onze sítios passam com os ecrãs que os chamam) | sem sessão, poucos dados, testam a mecânica |
| 3.2a | o esqueleto das Configurações (o índice e a secção) e as quatro secções do sistema (recolha, leitura, capturas, cópias) — **feito a 9/10/2026**; as macros `campo` e `interruptor` nasceram aqui | só o dono as vê |
| 3.2b | a Conta — **feito a 9/10/2026**: sete moldes `conta_*.html`; as funções `_bloco_*` ficam com o nome e desenham o seu molde; nasce a macro `accao` | a maior das secções da empresa |
| 3.2c-i | o Interesse — **feito a 9/10/2026** (`interesse.html`, `interesse_listas.html`); a árvore dos CPV entra feita (`arvore_html()`, partilhada com os Concursos: passa no 3.8) | o mais pequeno dos dois |
| 3.2c-ii | os Alertas — **feito a 9/10/2026** (`alertas.html`; saem o `_linha_filtro`, o `_caixa_email`, o `_caixa_urgente` e o `_caixa_alerta_do_perfil`; nasce a macro `rotulado`, com `{% call %}`). Entram feitos o `arvore_html()`, o `campos_do_local_e_valor()` e o `envios_html()`, partilhados | 177 linhas e quatro auxiliares de ~90 |
| 3.2d-i | os Documentos — **feito a 9/10/2026** (`documentos.html`) | o mais pequeno dos três |
| 3.2d-ii | o Importar — **feito a 9/10/2026** (`importar.html`, `importar_ensaio.html`; o `_tabela_do_ensaio()` passa a `_linha_do_ensaio()`, que só prepara os dados) | o assistente de três passos |
| 3.2d-iii | os Indicadores — **feito a 10/10/2026** (`indicadores.html`, só o esqueleto: as linhas de saúde e os números são o `linhas_de_saude()` e o `kpi()`, partilhados por muitos ecrãs, e passam a macros no lote que for dono deles). **Com este, as Configurações estão todas em moldes** | 197 linhas |
| 3.3a | Plataforma: os Erros, as Sugestões e as Visitas — **feito a 10/10/2026** (`plataforma_erros.html`, `plataforma_sugestoes.html`, `plataforma_visitas.html`, `visitas_tabela.html`; nasce a macro `celula`) | só o dono os vê |
| 3.3b | a página principal da Plataforma — **feito a 10/10/2026** (`plataforma.html`; saem o `_html_dos_semaforos`, o `_bloco_do_correio` e o `_contas_encontradas`, que passa a `_contas_da_procura`, só dados; nasce a macro `cartao`, sem o «?» do bloco) | |
| 3.3c | a página de cada empresa — **feito a 10/10/2026** (`plataforma_empresa.html`, e a tabela da actividade em `actividade_tabela.html`, que serve também as duas `/actividade`; saem o `_gestos_do_suporte`, o `_cartao_do_plano`, o `_cartao_de_apagar`, o `_cartao_do_uso`, o `_cartao_da_nota` e o `_cartao_da_actividade`; o `_cartao_do_pedido` passa a `_pedidos_da_empresa`, só dados) | 141 linhas |
| 3.3d | os pedidos de acesso — **feito a 10/10/2026** (`pedidos_de_acesso.html`; as etiquetas dos repetidos passam a dados, e a decisão de cada pedido a campos da linha.) | 185 linhas |
| 3.4 | Alertas e sugestões — **feito a 10/10/2026**: os Alertas já tinham passado no 3.2c-ii, e ficou o «Enviar uma sugestão» (`sugestoes.html`), com a recusa do POST, que traz o texto e o tipo de volta | |
| 3.5 | Calendário e indicadores — **feito a 10/10/2026**: os indicadores já tinham passado no 3.2d-iii; o Calendário é o `calendario.html`, e os dois pedaços (a agenda do telemóvel e o «+N» de um dia) o `calendario_pedaco.html`, com as peças comuns em `_calendario.html` | |
| 3.6 | Situação (`/situacao`) | |
| 3.7 | Mercado: contratos, entidades, ficha da entidade | |
| 3.8 | Concursos e Propostas: listas, fases, tabela | os mais vistos |
| 3.9 | A ficha do anúncio e da proposta | o maior (~5 000 linhas) |
| 3.10 | O Hoje (`/`) e a pesquisa | |
| 3.11 | Os e-mails | têm o CSS inline: o portão compara-os à parte |

### Fase 4 — fechar (1 sessão)
- Um teste-catraca: o número de `"<div"`, `"<td"`, `"<a "`… dentro do
  `radar.py` **só pode descer**. Isto impede que o HTML volte a entrar
  por um ecrã novo.
- Documentação no mesmo commit: a arquitectura do `CLAUDE.md` (a banda do
  painel), as armadilhas («A interface»), o `ESTADO.md` (linhas), e o D1
  riscado no `BACKLOG.md`.

## Achados pelo caminho (não se corrigem dentro do D1)

O D1 não muda comportamento: o que se encontra de errado fica aqui, e
corrige-se num trabalho à parte, com o seu teste.

- **A confirmação do «Remover» da Conta escapa o e-mail duas vezes**
  (lote 3.2b): o texto da confirmação leva o e-mail já escapado, e o
  `accao` escapa-o outra vez — um e-mail com `&` aparece no diálogo
  como `&amp;`. O molde reproduz o defeito de propósito (`u.email|e`);
  corrige-se tirando esse `|e`.

- **Um disco temporário cheio parece uma diferença**: no lote 3.2c-ii o
  `/tmp` (memória, 3,6 GB, partilhado com as outras sessões) encheu, e um
  teste caiu com `Disk quota exceeded`; com espaço, passou. Antes de
  procurar a diferença no código, `df -h /tmp`; e as gravações dos lotes
  já fundidos apagam-se. **O PDF da demo com outro tamanho não era do
  disco** (corrigido no 3.2d-ii): o `demo.py` gera os PDF na hora, com a
  data dentro, e o tamanho varia um byte de gravação para gravação. O
  portão normaliza os tamanhos em bytes.

## 4. Riscos e como se tratam

| Risco | O que se faz |
|---|---|
| O Jinja muda espaços e quebras de linha | `trim_blocks` e `lstrip_blocks`; o portão A compara ao byte e acusa |
| Um valor fica escapado duas vezes (`&amp;amp;`) ou deixa de ser escapado | o portão A acusa as duas coisas; a regra do `\|safe` na armadilha |
| Testes que lêem o código-fonte (`inspect.getsource`) deixam de encontrar o HTML | ajustam-se no lote que os parte, com a razão escrita |
| O `valida_docs.py` acusa nomes que saíram | corrige-se a documentação no mesmo lote |
| Conflitos com outro trabalho no `master` enquanto um lote está aberto | lotes curtos (uma sessão), e o merge no mesmo dia em que tu dás o ok |
| Desempenho (o Jinja compila os moldes uma vez e guarda-os) | mede-se o Hoje e a ficha antes e depois, no ensaio |

## 5. Calendário

- Código congelado até **11/10/2026**. Isto começa na segunda, 12/10.
- ~14 sessões ao todo. Se fizermos uma por dia útil, são três semanas.
- O EN só começa depois da Fase 4.
