# A multidão e o dono simulado — o ensaio do lançamento de 5/10/2026

30/09/2026. **Instantâneo: descreve o dia em que foi escrito e não se edita.**
O que daqui se decidir vai para os donos vivos (`BACKLOG.md`, o site, o
`docs/FUNCIONAL.md`).

## Porque existe

O Afonso fixou o anúncio público do Mira Gov para **5/10/2026** (feriado),
com a oferta de fundador. Viu um reel sobre o MiroFish (simular uma multidão
de clientes antes de lançar) e pediu: «não limites o uso a 10 ou 20, deixa
vir a multidão», e «cria um agente para simular a minha função de dono a
autorizar os pedidos».

## O método

**A multidão (500 pessoas).** 450 são fornecedores **reais** do Estado,
tirados do corpus do Portal BASE (`contratos.db`), **sem nomes**: dos 35 820
fornecedores com pelo menos um concurso público ou consulta prévia desde
2024, 90 por quintil de tamanho (número de contratos), cada um com a divisão
CPV principal, o distrito, a forma jurídica, os contratos por tipo de
procedimento e o valor. As outras 50 são quem também chega a um anúncio
público: consultores, técnicos de entidades públicas, concorrentes,
jornalistas, robôs de spam, uma empresa estrangeira, e assim por diante.

Dez agentes (Sonnet), cinquenta pessoas cada, leram o texto do site tal como
está e a oferta de lançamento tirada das decisões de 30/09 (`PLANO-2026-10.md`,
§L2: Vigia 39 €, VigIA+ 99 € ou 999 €/ano, Corporate sob consulta, fundador a
55 € com testemunho, tudo +IVA). Cada pessoa decidiu sozinha, com a instrução
de que ninguém está a ser simpático e sem taxa-alvo, e deixou uma linha JSON:
o que a trava, o que pensa de cada preço, se pede acesso, e o formulário que
preencheria.

**O dono.** Um agente com o papel dele (`.claude/agents/dono-dos-pedidos.md`)
recebeu só o que o formulário do site traz (nome, empresa, e-mail, sector,
mensagem), pela ordem de chegada, e decidiu cada pedido como o ecrã deixa:
aceitar com o perfil, recusar com motivo, ou perguntar. As regras que ele já
tomou estão na definição; o que não está decidido, o agente **marca** em vez
de inventar. Só depois de aceitar é que viu a resposta ao e-mail do
fundador, para escolher os dez.

**O MiroFish** (o do reel) corre à parte, instalado em `~/mirofish`, com o
Gemini gratuito do Google AI Studio e o Zep Cloud gratuito, sobre uma semente
com as mesmas 500 pessoas (só os factos, não as reacções). Simula o anúncio a
circular numa rede social. O resultado dele entra no diário quando acabar.

**Onde estão os dados:** em `~/radar-capturas/lancamento-2026-09-30/`, fora
do git (regra de 23/09: no GitHub só código). As sementes, as 500 respostas,
os 177 pedidos, as 177 decisões e o resumo do dono.

## O aviso antes dos números

A taxa de quem pede acesso variou entre **12% e 50% de grupo para grupo**,
com pessoas sorteadas da mesma população. Parte disso é o modelo, que em cada
corrida é mais ou menos exigente. **Valem as direcções** — quem se interessa,
e porquê —, não as percentagens.

## A multidão

| | |
|---|---|
| Pessoas | 500 (450 fornecedores + 50 outras) |
| Pediram acesso | 177 (média dos grupos 35%; mínimo 12%, máximo 50%) |
| Querem o fundador a 55 € | 88 (para 10 lugares) |
| Dos que pedem, pagam em janeiro | 49 sim · 112 talvez · 8 não |
| Confiança média | 2,9 em 5 |
| Entendem o que é | 3,6 em 5 |

**O que decide é o peso do ajuste directo**, que não sai no Diário da
República e o Mira Gov não mostra:

| Parte do negócio em ajuste directo | Pedem acesso |
|---|---|
| < 25% | 34% |
| 25–50% | 69% |
| 50–75% | 20% |
| > 75% | 3% |

**E o tamanho:** quintis 1–2 pedem 14–19%; quintis 3–5, 41–49%.
**Por divisão CPV** (≥ 10 pessoas): obras (45) 59% e transportes (60) 64% no
topo; formação (80) 11% e hotelaria (55) 8% em baixo.

**O que trava** (pessoas que o citam):

| Objecção | Pessoas |
|---|---|
| O negócio com o Estado é pequeno de mais para uma mensalidade | 152 |
| É uma pessoa em nome individual: e se ele parar? | 142 |
| Vivem de ajuste directo, que o Mira Gov não mostra | 100 |
| Já têm ferramenta ou rotina | 73 |
| Não confiam na leitura das peças pelo modelo | 65 |
| Os dados ficam no servidor de um particular | 48 |
| O preço final por decidir | 37 |
| Pedir acesso e esperar | 31 |
| Não se sabe quem já usa | 27 |

**Os preços, nos fornecedores:** o Vigia a 39 € divide-se quase por igual
(justo 133 · caro 126 · não me serve 105 · barato 86). O **VigIA+ a 99 € não
pega**: 216 em 450 dizem que não lhes serve. Dos que pedem acesso, o plano
provável é o Vigia (89) antes do VigIA+ (55) e do Corporate (17).

**O que o site contradiz** (visto por pessoas diferentes em grupos
diferentes): a pergunta «Quanto vai custar depois da beta?» responde que
ainda não está decidido; o site não diz que cada empresa tem a sua própria
base; não diz o que acontece aos dados se o vendedor parar; e não diz, à
cabeça, que os ajustes directos não aparecem.

## O dono

| Decisão | Pedidos |
|---|---|
| Aceitar | 126 |
| Perguntar primeiro | 47 |
| Recusar | 4 |

**O dia não cabe no tempo dele.** Cerca de 20 h 20 min para decidir, e mais
~4 h para as respostas e as demonstrações; com o feriado e duas noites há 10
a 12 h.

**Os dez fundadores** que o agente escolheu são de dez sectores diferentes,
todos com testemunho com nome e pagamento em janeiro. Três ficaram à porta
por pouco — um deles porque quer a equipa toda e o VigIA+ tem 2 utilizadores.

**O que lhe fez perder tempo:** o formulário não pede o NIF, o que a empresa
vende nem os distritos, e o sector engana (três engenharias escolheram
«Tecnologias de informação»); não há aviso de pedidos repetidos (18 com a
mesma mensagem-modelo, 8 com a mesma pessoa em várias empresas); o convite
não tem onde pôr uma nota (52 precisaram de um segundo e-mail); o
`perfil_do_pedido()` não apanha «Algarve», «Alentejo», «Norte» nem «Centro»;
recusar não avisa a pessoa; não há onde marcar o fundador; o tecto de 200
pedidos por dia é um só para o site inteiro; e o site contradiz-se em três
sítios («no próprio dia» e «dois dias úteis»; o preço; «contas para toda a
equipa» contra 1 ou 2 utilizadores).

**As regras que faltam**, perguntas ao Afonso, pela ordem de quantos pedidos
tocaram: quando se pede o NIF (126); quantas empresas consegue acompanhar por
semana, e se aceita por vagas (126); se quem vive de consultas prévias entra
igual (25); uma pessoa com várias empresas — uma conta por cliente ou uma só
(24); o preço do Corporate (15); se há compromisso de serviço e de
continuidade (8); parceiros com comissão (5); demonstrações (3).
