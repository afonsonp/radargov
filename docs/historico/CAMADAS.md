# A documentação medida contra o ICM — 19/09/2026

> **Instantâneo.** Descreve o dia em que foi escrito. O que vale hoje
> está no `CLAUDE.md`, no `docs/FUNCIONAL.md` e nas armadilhas.

Auditoria da documentação do radar contra o **Interpretable Context
Methodology** (Van Clief & McDermott, arXiv:2603.16021v2, 18/03/2026),
que foi o documento que deu início a esta arrumação.

O que se fez a 19/09 de manhã — dar dono a cada facto — respondeu à
pergunta **«onde está escrito?»**. Esta auditoria responde à outra, que
o paper faz e nós não tínhamos feito: **«quanto é que isto pesa, e que
camada é cada coisa?»**

---

## 1. O modelo do paper, em cinco camadas

| Camada | Pergunta | Alvo do paper |
|---|---|---|
| **0** `CLAUDE.md` | «Onde estou?» | **~800 tokens** |
| **1** routing | «Para onde vou?» | ~300 tokens |
| **2** contrato da fase | «O que faço?» | 200–500 tokens |
| **3** referência — *a receita* | «Que regras se aplicam?» | 500–2 000 tokens |
| **4** artefactos — *os ingredientes* | «Com que material trabalho?» | varia |

Duas distinções que o paper insiste que são estruturais, não de estilo:

- **Camadas 0–2 juntas: 1 300 a 1 600 tokens.** Total por fase: 2 000 a
  8 000. Um prompt **monolítico** — tudo carregado de uma vez — chega
  aos 30–50 mil, «a maior parte irrelevante para a tarefa em curso».
- **Camada 3 é a receita** (estável entre execuções, «internaliza-se
  como restrição»); **camada 4 são os ingredientes** (muda a cada
  execução, «processa-se como entrada»). Misturá-las «obriga o modelo a
  separá-las sozinho».

A defesa do paper não é comprimir, é **não carregar**: «isto é
prevenção, não compressão».

---

## 2. O que medimos

Estimativa a 3,6 caracteres por token — português acentuado tokeniza
pior que inglês. É estimativa, não medição com tokenizador.

| Ficheiro | Linhas | ~tokens | Camada |
|---|---|---|---|
| `CLAUDE.md` | 644 | **11 018** | 0 + 1 + 3 |
| `ESTADO.md` | 142 | 2 054 | 4 |
| `BACKLOG.md` | 531 | 11 446 | 4 |
| `LEIA-ME.md` | 1 143 | 15 122 | 3 (humano) |
| `docs/FUNCIONAL.md` | 826 | 10 331 | 3 |
| `docs/armadilhas.md` | 2 668 | **43 078** | 3 |
| `docs/design.md` | 819 | 10 384 | 3 |
| `docs/referencia.md` | 1 511 | 21 526 | 3 |
| `docs/seguranca.md` | 73 | 984 | 3 |
| `docs/diario/` (2 ficheiros) | 9 245 | **133 678** | 4 |
| `docs/historico/` (10 ficheiros) | — | 82 371 | 4 |
| **Total** | | **342 000** | |

---

## 3. Os três achados

### 3.1 A camada 0 está 14× acima do alvo

O `CLAUDE.md` é a camada 0 — e **declara-se a si mesmo** «o único que
se carrega inteiro». São ~11 000 tokens contra os ~800 do paper.

Sozinho, o nosso ficheiro de identidade é quase um terço do prompt
monolítico que a Figura 3 do paper usa como exemplo do que **não** se
deve fazer.

E não é só tamanho: **são três camadas num ficheiro.**

| O que lá está | Camada a que pertence | ~tokens |
|---|---|---|
| o que a aplicação é | 0 | ~150 |
| a tabela «onde está a documentação» (20 linhas) | **1** | ~2 500 |
| as regras de trabalho | 3 | ~2 000 |
| o mapa da arquitectura, banda a banda | 3 | ~3 500 |
| hooks, skills, Git, releases | 3 | ~2 800 |

A tabela de routing sozinha é **oito vezes** o alvo da camada 1.

### 3.2 A receita e os ingredientes estão na mesma pasta

`docs/` tem **86 000 tokens de camada 3** (a receita: funcional,
armadilhas, design, referência, segurança) e **216 000 de camada 4**
(os ingredientes gastos: diário e histórico), sem fronteira nenhuma
entre eles.

**O arquivo é 2,5× a documentação viva.** O `docs/diario/2026-09.md`
sozinho — 7 018 linhas, ~104 000 tokens — é maior do que toda a
documentação viva junta, e cresceu nisto em dezanove dias, porque a
regra da casa é «o diário é acrescento, não correcção».

É exactamente o que o paper descreve: artefactos de execuções passadas
guardados como se fossem regras permanentes.

### 3.3 O `BACKLOG.md` é camada 4 a fingir-se de camada 3

São 11 446 tokens, **32 linhas de tabela das quais 21 riscadas como
feitas** — e as seis primeiras, as que se lêem primeiro, são todas
trabalho terminado.

Foi a primeira queixa do Afonso a 19/09: *«o Backlog começa por coisas
que já estão terminadas»*. O paper dá-lhe o nome: é estado de execução,
não referência, e ler-se-ia melhor invertido, com o que está por fazer
primeiro e o que está feito no arquivo.

---

## 4. O que isto não é

**Não é um argumento para escrever menos.** A arrumação da manhã de
19/09 *acrescentou* 242 linhas, porque cinco dos nove assuntos não
estavam espalhados — estavam em falta. O paper também não pede menos
texto: pede que cada camada carregue só o que é dela.

**Não é um argumento para adoptar o ICM.** O radar não é um pipeline de
fases com portões de revisão; é uma aplicação. O que se aproveita é o
diagnóstico — as camadas e os alvos —, não a estrutura de pastas
`01_/02_/03_`.

**E a medição é estimativa.** 3,6 caracteres por token é um valor
observado, não medido com tokenizador. As ordens de grandeza aguentam;
os números exactos não se citam.

---

## 5. O que se propõe, por ordem de proveito

Nada disto está feito. Fica aqui para decidir.

| # | O quê | Proveito | Custo |
|---|---|---|---|
| **C1** | Partir o `CLAUDE.md`: a tabela de routing sai para um `MAPA.md` e fica um ponteiro | a camada 0 cai de ~11 000 para ~8 500, e o routing passa a ser carregável à parte | baixo — é mover uma tabela |
| **C2** | Separar o arquivo: `docs/arquivo/` com o `diario/` e o `historico/` lá dentro | a fronteira camada 3 / camada 4 passa a existir no disco | médio — 108 referências a `docs/` em `.md`, 66 em comentários de código |
| **C3** | Inverter o `BACKLOG`: aberto primeiro, feito no fim ou no arquivo | quem o abre vê trabalho, não história | baixo |
| **C4** | O mapa da arquitectura (banda a banda) sai do `CLAUDE.md` para o `docs/FUNCIONAL.md` ou para um `ARQUITECTURA.md` | mais ~3 500 tokens fora da camada 0 | médio — é o coração do ficheiro, decide-se antes de mexer |
| **C5** | Fechar o `docs/diario/2026-09.md` e abrir `2026-09-b.md` | o ficheiro de 104 000 tokens deixa de crescer | trivial |
| — | Renomear `documentos/` (são as peças, não documentação) | tira a confusão que ele apontou primeiro | **toca no código**: a constante `DOCS` no `radar.py` |

**C1, C3 e C5 são baratos e independentes.** C2 e C4 mudam o mapa
mental de quem trabalha aqui, e não se fazem de passagem.

---

## 6. A pergunta que fica em aberto

O paper admite-a no §5.4: *«à medida que as janelas de contexto crescem,
a carga selectiva torna-se menos importante? Se um modelo atende com
fiabilidade a 200 000 tokens sem degradação, o argumento de engenharia
enfraquece — embora os argumentos de interacção humana
(observabilidade, editabilidade, portões de revisão) permaneçam.»*

Para o radar isto é a pergunta certa. Os 342 000 tokens nunca se
carregam de uma vez; carrega-se o `CLAUDE.md` (11 000) mais a área das
armadilhas que a tarefa pedir. **O custo real não é o modelo não
aguentar — é o humano não achar.** E é aí que os três achados doem:
onze afirmações falsas encontradas nesse mesmo dia, todas em ficheiros
que alguém tinha lido e dado por certos.
