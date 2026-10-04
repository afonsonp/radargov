# Documento funcional — Mira Gov

> **Última revisão: 3 de outubro de 2026**, sobre a `v2.0.43`. Este
> ficheiro **não é instantâneo**: descreve a aplicação como ela é, e
> corrige-se quando o comportamento muda. Os números são medidos, não
> estimados — a data em cima diz de quando.

Serve duas leituras:

- **§1 a §6** — o que a aplicação **é e faz hoje**. É o que tens de
  respeitar ao desenhar: os conceitos, os ecrãs, as acções e as regras.
- **§7 a §9** — o que **ainda se pode fazer** com os dados que já estão
  na base, o que precisaria de dados novos, e o que está construído e
  não se usa.

Ao desenhar um ecrã novo, o §2 (os dados) e o §6 (as regras) são os
dois que decidem se ele é possível como está desenhado.

> **Este ficheiro é o DONO de «o que a aplicação é e faz».** Decidido a
> 19/09/2026, depois de se medir que os nove assuntos da aplicação
> estavam contados nos **oito** ficheiros vivos ao mesmo tempo — a
> escada 140 vezes, as entidades 236. Não era desleixo: os ficheiros
> estavam divididos por **género** (as regras, o manual, as armadilhas,
> o porquê), e uma divisão por género obriga a contar cada assunto uma
> vez por género. Corrigir um facto passava por seis sítios, e a 17/09 o
> manual ainda descrevia um quadro que tinha saído dois dias antes.
>
> A regra que fica: **um facto tem um dono, e os outros apontam.**
>
> | Dono de | Ficheiro |
> |---|---|
> | o que a aplicação **é e faz** | **este** |
> | como se **opera** (instalar, correr, refazer capturas) | `LEIA-ME.md` |
> | as **armadilhas**, por área | `docs/armadilhas.md` |
> | as **regras de trabalho** e o mapa do código | `CLAUDE.md` |
> | os **números medidos** de hoje | `ESTADO.md` |
> | o que está **em aberto** | `BACKLOG.md` |
> | o que a **lei** diz (o CCP), as mudanças e as datas | `docs/ccp.md` |
> | o **porquê**, com data | `docs/referencia.md`, `docs/historico/` |
>
> Se estás a escrever aqui uma coisa que é de outro dono, ela vai para
> lá e fica aqui uma ligação. E ao contrário.

---

## 1. O que a aplicação é

Uma aplicação local em Python (Flask + SQLite) que **vigia os anúncios
de contratação pública da parte L da série II do Diário da República**,
guarda-os, e serve-os num painel.

Corre em Ubuntu, em `~/Desktop/radar`. Verifica sozinha **de hora a
hora, das 08:00 às 20:00** (um temporizador do systemd), e responde em
`http://127.0.0.1:8765` e, por um túnel da Cloudflare, em
**`https://miragov.pt`**, com login (desde 25/09/2026; o `miragov.com` e o
`radargov.pt` de antes, com e sem `www`, mandam para lá, com o caminho).

Substitui a Armilar (produto Vortal, 200 €/mês).

**O princípio de desenho, decidido depois de uma primeira versão que
filtrava por pontuação: não se filtra nada à entrada.** Entra tudo o que
a parte L publicar; a triagem faz-se no painel. Isto é a razão de haver
210 mil anúncios e não mil — e é o que dá valor ao §7.

A aplicação faz três coisas que se sobrepõem:

1. **Vigiar** — recolher, ler o detalhe, trazer as peças, detectar
   alterações, avisar.
2. **Decidir** — a escada: por ver → analisar → propor → ganhar ou
   perder, com tarefas e prazos.
3. **Conhecer o mercado** — o corpus de 2 milhões de contratos
   celebrados do Portal BASE, e o que ele diz sobre entidades,
   concorrentes e preços.

---

## 2. Os dados que existem

É a matéria-prima. **Nada se pode desenhar que não saia daqui.**

### 2.1 `radar.db` — a plataforma (1,32 GB, 19 tabelas)

**A base muda-se sozinha, a cada arranque.** Não há ficheiros de
migração nem números de versão: é o `iniciar_db()`, e cada passo é
idempotente — `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT
EXISTS`, um `ALTER TABLE ADD COLUMN` apanhado pela `OperationalError`,
ou um `UPDATE` cuja própria pergunta o torna irrepetível. Consequência
para quem desenha: **acrescentar uma coluna é barato e imediato**
(menos de 0,1 s sobre 210 mil anúncios); reescrever uma tabela não é, e
o `DROP COLUMN` do SQLite reescreve-a inteira. As regras de quando
fazer cópia e quando ensaiar estão no `CLAUDE.md`, banda 1.

**O trabalho de cada empresa não está aqui** desde a fase F1 do plano
multi-empresa (23/09/2026): mora no ficheiro dela, §2.1a. Aqui fica o
que é da **plataforma** — o que é de todas e poupa custos por o ser: os
anúncios, as peças e o que o modelo leu delas, o CPV, as alterações do
DR, as verificações, os erros, as contas e os pedidos de acesso.

**Duas colunas de números, e a diferença importa.** As tabelas que
crescem **sozinhas** — a verificação corre de hora a hora — não levam contagem
exacta: levava-se um número que fica velho antes de o commit chegar ao
GitHub. Aconteceu a 22/09/2026: alguém fez um commit **só** para mudar
o `historico` de 622 para 623, e nessa manhã ele já ia em 625. As que
mexem ao ritmo de uma pessoa, e as que estão a zero, levam o número —
porque aí **o número é o que interessa**. O portão da release confere
as exactas e salta as outras.

| Tabela | Linhas | O que é |
|---|---|---|
| `anuncios` | ~210 mil | Um por anúncio do DR (mais ~110 da Vortal). Desde **2015**. Cresce ~40/dia |
| `documentos` | algumas centenas | As peças em disco. Crescem quando se traz um concurso, e com a vigilância |
| `analise` | uma por concurso lido | O que o modelo leu das peças |
| `alteracoes` | uma por alteração | O que o DR mudou num anúncio já lido. **Leva tudo** desde a F2 (23/09/2026): cada empresa recebe só as dos concursos que tem na escada, e marca-as na `alteracoes_avisadas` dela (a coluna `avisado_em` ficou, por usar) |
| `eventos` | uma por evento | O que a plataforma viu acontecer a um anúncio — o DR mudou-o ou rectificou-o, apareceu uma peça, o modelo leu-as (`ACCOES_DA_PLATAFORMA`). Saiu do `historico` da empresa na F2; a ficha mostra os dois juntos (`passos_do_anuncio()`) |
| `cpv_dict` | **9 454** | O vocabulário CPV, com descrição. Importado uma vez |
| `slots` | uma por verificação | Cada verificação que correu, e quantos trouxe (13/dia, das 08:00 às 20:00) |
| `erros` | a série, por tipo, com o `visto_em` que o dono põe em `/plataforma/erros` | Poda a 200 por tipo — a contagem não quer dizer nada |
| `utilizadores` | **1** | Quem entra. As 19 contas da segunda ronda de testes com utilizadores já saíram. O `contacto` (1/10/2026) é o e-mail para onde vai o «esqueci-me» quando o utilizador não é um e-mail; vem do convite (§4.9) |
| `sessoes` | as abertas agora | Caducam aos 30 dias, e o «sair de todos» esvazia-as. `ver_como`: a empresa que o dono está a ver, só para ler, nessa sessão (26/09/2026) |
| `estado` | 22 | Marcas do sistema (última verificação, migrações feitas) |
| `entradas_falhadas` | 1 | Tentativas de login falhadas |
| `leituras_pedidas` | **0** | As leituras das peças que cada empresa pediu, para o tecto por dia (F7) |
| `convites` | **0** | Os convites de quem teve o pedido de acesso aceite (F5): o resumo do código, a empresa, o prazo, se já se usou e se foi anulado (`anulado_em`, 26/09/2026) |
| `reposicoes` | **4** | As ligações para repor a palavra-passe (D17, 26/09/2026): o resumo do código, a conta, quem a gerou, o prazo e se já se usou (§4.9) |
| `segundo_factor` | dez por conta que o liga, mais os pendentes e os aparelhos | O segundo factor (28/09/2026): o pedido de entrada à espera do código, os aparelhos de confiança e os códigos de recuperação, pelo `tipo`, todos só em resumo (§4.9). A chave da app está no `utilizadores` (`totp_segredo`) |
| `pedidos_acesso` | **6** | Os pedidos do formulário do site público (§4.9), desde a `v1.12.0`; `estado` aceite ou recusado, com `motivo` e `decidido_em` desde 26/09/2026; o `nif` da empresa e o `plano` que interessa (`PLANOS_DO_PEDIDO`) de 30/09 a 4/10/2026, quando o formulário passou a pedir o `telefone` em vez deles |
| `planos` | uma por empresa com plano | O plano de cada empresa (L2.1, 1/10/2026): o nome, mensal ou anual, se é fundador, e os utilizadores acordados no Corporate. É da plataforma, como as contas (`contas.py`) |
| `sessoes_fechadas` | as que uma entrada noutro aparelho fechou | A sessão única do plano de uma pessoa: guarda o token fechado, para quem o tinha ver porque saiu |

**As colunas de `anuncios` que interessam, e quanto estão preenchidas:**

| Coluna | Cheia | Nota |
|---|---|---|
| `ref` | 100% | «21296/2026» — é a chave, e é a mesma do Portal BASE |
| `titulo`, `entidade`, `data_pub` | 100% | |
| `texto` | **88,1%** | **O anúncio inteiro em texto.** ~840 MB. Nunca foi explorado |
| `cpv` | 87,1% | |
| `plataforma` | 87,0% | vortal 80 k · acingov 68 k · anogov 15 k · saphety 13 k · … |
| `nif` | 76,1% | O NIF da entidade que publica — liga ao corpus |
| `preco_base` | 53,5% | O tecto que exclui propostas (art. 70.º do CCP) |
| `preco_estimado` | ~0,2% | Desde 1/10/2026: o valor estimado do contrato (art. 17.º), que **não exclui** — a linha nova do DR, o «Valor estimado» do objecto e o máximo de um acordo-quadro. Medido nesse dia: 401 anúncios da base sem preço base o têm. Ver `docs/ccp.md` §3-A |
| `prazo` | 38,2% | Data-limite de entrega |
| `link_pecas` | 39,2% | |
| `distrito` | ~70% | Desde 25/09/2026: os distritos do **local de execução** (secção 9 do texto), «\|Porto\|Lisboa\|»; `*` num concurso nacional. Medido na leitura: 148 579 dos 185 886 com texto |
| `lotes` | 10,3% | |
| `altera` | 5,0% | Republicações ligadas ao original |
| `detalhe_lido` | **100%** | Não há fila por ler |

**Onze colunas de `anuncios` estão a 0%**: `responsavel`, `tipologia`,
`cv`, `proposta_tecnica`, `coe`, `notas`, `motivo`, `preco_proposto`,
`posicao`, `top3`, `motivo_perda`. São as colunas de CRM que saíram para
`propostas` a 15/09/2026 — **não as uses: estão mortas.**

**O índice da pesquisa geral** (1/10/2026) não conta nas tabelas de
cima: é derivado, como um índice. São a `pesquisa_fts` (FTS5 `trigram`,
sem o texto — só os trigramas do título, da entidade, da referência e
do NIF de cada anúncio, ~111 MB) e a `pesquisa_refs`, que dá a cada
`ref` um número que um VACUUM não muda (~4 MB). Constroem-se em fundo
no primeiro arranque do painel com este código (~30 a 60 s), e daí em
diante os gatilhos dos `anuncios` mantêm-nas em todas as escritas.

### 2.1a `empresas/<id>/empresa.db` — o trabalho de uma empresa (16 tabelas)

**Um ficheiro por empresa** (fase F1, 23/09/2026; hoje só há a empresa
2, a LATD). O `liga()` junta-o ao `radar.db` com o nome `emp`, e o SQL não
mudou: um nome de tabela que não exista no `radar.db` resolve-se sozinho
aqui. **Sem este ficheiro a `propostas` nem existe** — o erro fecha, em
vez de mostrar o trabalho de outra empresa. As tabelas que são daqui
estão em `TABELAS_DA_EMPRESA`, e o esquema é o `iniciar_empresa()`; a
primeira base que ainda as tinha dentro do `radar.db` passou-as para
cá no arranque (`separar_empresa()`), com cópia antes e as contagens
comparadas antes de apagar.

| Tabela | Linhas | O que é |
|---|---|---|
| `propostas` | **4** — da LATD, que voltou como empresa 2 a 24/09/2026 (eram 81 antes de 23/09) | O que a **empresa** está a fazer — a escada |
| `tarefas` | dezenas | O que falta fazer, por proposta — e, desde 26/09/2026, por documento do cofre (`documento_id`). A verificação sincroniza-as |
| `notas_da_proposta` | **0** (a LATD não tinha notas quando a coluna passou, a 26/09/2026) | As notas datadas e assinadas: texto, quem, quando. Nenhuma apaga a anterior; quem a escreveu corrige-a ou apaga-a (§3.1) |
| `documentos_da_empresa` | **0** | O cofre (D5, 26/09/2026): tipo, número ou descrição, validade. Sem ficheiros (§4.8) |
| `contactos` | **0** (eram 26 na LATD antes de 23/09) | As pessoas do lado de lá, **por entidade** |
| `historico` | uma por movimento | Quem, o quê, quando — o que a **empresa** fez. Cresce a **cada acção** no painel; o que o DR e as peças fizeram está nos `eventos` |
| `pessoas` | 0 | Os nomes que a lista de «responsável» sugere |
| `etiquetas` · `anuncio_etiquetas` | **0** · **0** | Etiquetas livres — construído, **por usar** |
| `filtros_guardados` | **1** | Hoje só os alertas lá vivem (§3.8) |
| `entidades_seguidas` · `seguidas_vistos` | **0** | Construído, por usar |
| `alertas_vistos` | **9 879** | A memória do que já foi avisado (§3.8) |
| `empresa` | **0** | Resto do importador de Excel, já corrido |
| `marcas_da_empresa` | 4 | As marcas do resumo diário (`MARCAS_DA_EMPRESA`), a da migração das alterações avisadas e, desde 26/09/2026, a do cartão do arranque dispensado (`MARCA_DO_ARRANQUE`) |
| `alteracoes_avisadas` | uma por alteração recebida | O que esta empresa já recebeu da fila `alteracoes`, que é da plataforma (F2) |

**As colunas de `propostas`, e quantas das 78 estão preenchidas:**

| Coluna | Cheias | Nota |
|---|---|---|
| `ref`, `entidade`, `titulo`, `preco_base`, `entidade_chave` | 78 | |
| `responsavel` | 72 | Quem a tem |
| `tipologia` | 72 | **Nenhum ecrã a mostra agrupada** |
| `coe` | 58 | idem |
| `cv`, `proposta_tecnica` | 49 | **Saíram do ecrã a 28/09/2026**: o que a proposta leva é o que o Programa pede, e isso é a `documentos_prontos`. As colunas ficam |
| `documentos_prontos` | 0 | Os documentos do campo 12 que a empresa marcou como prontos, em JSON (28/09/2026) |
| `valor_proposta`, `ebitda` | 42 | **O `ebitda` não aparece em ecrã nenhum** |
| `fechada_em` | 48 | O dia em que se marcou como decidida — o período do `/situacao` usa-a só quando falta a `data_adjudicacao` |
| `data_adjudicacao` | 0 | A data da adjudicação (26/09/2026): é por ela que o `/situacao` conta o período |
| `audiencia_em` | 0 | A data da notificação do relatório preliminar: abre a tarefa da audiência prévia (§3.5) |
| `valor_adjudicado` | 0 | O que o «Ganho» soma; vazio, o proposto (26/09/2026). A Situação diz quantas ganhas somam cada um, e a tabela das decididas tem a coluna «Conta» |
| `notas` | 0 | **Vazia desde 26/09/2026**: as notas passaram à `notas_da_proposta`, e a coluna fica (largar uma coluna reescreve a tabela) |
| `lugar`, `top3` | 34 | Em que posição ficámos, e quem ficou à frente |
| `motivo` | 31 | Vocabulário fechado (4+4 palavras) |
| `lote` | 0 | Existe, ainda não se usou |
| `porque_sem_ref` | 0 | Propostas sem anúncio: existe, ainda não se usou |
| `prazo_entrega` | 0 | O prazo de entrega de uma proposta **sem anúncio** (1/10/2026): dá o «até …» dos quatro passos, a coluna «Prazo» da lista e a tarefa automática «entregar a proposta». Com anúncio fica vazia — o prazo é o do DR |

### 2.2 `contratos.db` — o mercado (2,66 GB, 6 tabelas)

O dump semanal do IMPIC, do dados.gov. **Refaz-se em minutos e não
viaja**: não está no git.

| Tabela | Linhas | O que é |
|---|---|---|
| `contratos` | **2 009 640** | Cada contrato celebrado. Desde 2015 |
| `contrato_adjudicatario` | 2 041 974 | Quem ganhou (um contrato pode ter vários) |
| `contrato_cpv` | 2 042 820 | Os CPV de cada contrato |
| `entidades` | **180 507** | Identidade: chave, NIF, nome, nº de grafias, quanto compra, quanto ganha |
| `entidade_nomes` | 256 875 | Todas as grafias por que uma entidade já apareceu |

E, desde o lote 10 (29/09/2026), o **índice de texto** dos objectos,
`contratos_fts` (FTS5 `trigram`, de conteúdo externo: só os trigramas,
~609 MB, mais as tabelas-sombra do FTS5), por onde a pesquisa do
Mercado vai. Constrói-se sozinho em fundo (~5 minutos) e mantém-se por
gatilhos; a marca `indice_de_texto` do `corpus_estado` diz quando está
pronto.

Colunas de `contratos` que interessam: `n_anuncio` (**é o `ref` do
radar** — é por aqui que se fecha o ciclo), `adjudicante_chave`,
`objecto`, `cpv`, `preco_base`, `preco_contratual`, `data_celebracao`,
`prazo_execucao`, `fim_estimado`, `tipo_procedimento`, `local_execucao`,
`fundamentacao`, `n_adj`.

**`fim_estimado`** = celebração + prazo declarado. É **estimado**:
prorrogações e cessações antecipadas não constam do dump. Trata-se como
sinal para olhar, nunca como facto.

**Ao lado do corpus, o `contratos-concorrentes.db`** (desde 1/10/2026,
L5 do plano de Outubro): o detalhe de cada contrato dos últimos dois
anos pedido ao Portal BASE, um a um, pela thread de fundo do painel
(`vigiar_os_concorrentes()`). Quatro tabelas: `detalhe` (um por contrato
lido; `n_concorrentes` a NULL quando o BASE não traz lista — «sem lista»
não é «zero»), `concorrente` (o NIF, o nome e a chave, que é **o NIF e
nunca o nome**: `chave_do_concorrente()`), `corte` (cada corte da
firewall do BASE, com quantos pedidos passaram antes e quando voltou) e
`estado`. A fila vai pelos concursos públicos, depois as consultas
prévias, e os ajustes directos no fim. **Enche-se devagar e durante
semanas**; o progresso está na página da plataforma, no cartão Recolha.

### 2.3 O que a aplicação sabe sem pedir nada a ninguém

- **Dez anos de anúncios** (2015→), todos com detalhe lido.
- **O texto integral** de 185 mil deles.
- **Dez anos de contratos celebrados**, ligáveis ao anúncio pela `ref`.
- **Quem compra o quê, a quem, a que preço** — 180 mil entidades.
- **O que a empresa fez**, com preços propostos, desfechos e motivos.

### 2.4 O que **não** existe (não desenhes isto)

- **Não há histórico do pipeline.** Não se sabe o que estava em jogo no
  trimestre passado — só o que está agora. Por isso o «em jogo» não leva
  comparação.
- **Não há preços dos concorrentes antes da adjudicação.** Só depois, e
  só o vencedor: o BASE não publica as propostas perdedoras.
- **Não há quem concorreu e perdeu.** O `top3` da proposta é escrito à
  mão por nós, quando se sabe.
- **Não há datas de esclarecimentos fiáveis** — são derivadas do prazo
  pelo prazo supletivo do CCP, não lidas do anúncio.
- **Não há notificações em tempo real.** A recolha é 2× por dia.
- **Não há mais do que 2 papéis.** Não há equipas, nem permissões por
  concurso.
- **O corpus não tem o texto das peças** — só o objecto do contrato.

---

## 3. Os conceitos

Cinco ideias explicam todos os ecrãs.

### 3.1 A escada — dez ranhuras

Desenho do Afonso (15/09/2026). **Uma escada só**, não um quadro:

```
Por ver → Por analisar → A preparar → Submetida
        → Relatório preliminar → Ganha | Perdida | Não fomos | Cancelada
                                                    (+ Expirou sem ver)
```

- **As duas pontas** (`Por ver`, `Expirou sem ver`) são **anúncios**.
  O `Expirou sem ver` de uma empresa conta **desde que ela chegou**
  (`empresa_desde`, gravado ao criá-la; 26/09/2026): o que expirou
  antes não foi ela que o deixou passar, e fica só em «Todos». Sem essa
  data (as empresas anteriores a ela) conta tudo.
- **As oito do meio** são **propostas** — o que a empresa decidiu fazer.
- **Qualquer salto é permitido**, e voltar atrás é reabrir. **O salto
  pede o que pedem as ranhuras que implica** (D3 da 3.ª ronda,
  29/09/2026, decisão dele: «não vejo problema em meter diretamente no
  ganho desde que dê toda a informação que é pedida até lá»):
  «Relatório preliminar», «Ganha» e «Perdida» implicam «Submetida»
  (`RANHURAS_IMPLICADAS`, `exigidos_da_ranhura()`). «Não fomos» e
  «Cancelada» não implicam nenhuma: a escada da ficha nunca as mostra
  com «Submetida ✓», e a lista nunca diz «entregue» nem conta dias
  (G22).
- **Entrar numa ranhura exige o que a faz ser verdade**:

| Ranhura | Exige |
|---|---|
| Submetida | valor proposto |
| Relatório preliminar | valor proposto + lugar |
| Ganho | valor proposto |
| Perdido | valor proposto + motivo |
| Não fomos | motivo |

O selector **não grava ao mudar** (26/09/2026): escolhe-se a ranhura e
grava-se com o botão «Mudar» (ou o Enter). Antes gravava a cada seta do
teclado. «Tirar da escada» pergunta antes. Na linha das **Propostas**,
por baixo dele, há o botão da **fase seguinte** (`FASE_SEGUINTE`,
1/10/2026, H4 da `docs/historico/UX-7-LEIS.md`): «→ A preparar» em
«Por analisar», «→ Submetida» em «A preparar», «→ Relatório
preliminar» em «Submetida»; do relatório em diante não há uma seguinte
só, e não há botão. Vai pelo mesmo caminho do selector, com o `de`, e
pela mesma caixa quando a fase seguinte exige o que falta.

O que falta **pede-se no gesto que escolhe a ranhura** (25/09/2026):
escolhida no selector e carregado o «Mudar», abre-se uma caixa com o que esta proposta ainda
não tem — o preço, o lugar, o motivo — e grava-se tudo de uma vez. Sem
isto, o «Submetida» a partir de «A preparar» era um beco. O
campo do preço proposto está no bloco **desde «A preparar»**
(26/09/2026), e em qualquer ranhura quando já tem valor — senão uma
proposta reposta em «Por analisar» ficava com o preço escondido e presa.
A caixa recusa lá dentro o que não é preço, e fala português.

O preço proposto **tem de se ler como preço** — «118 500,00»,
«118.500,00 €» ou «118500» —, e grava-se sempre como «118.500,00 EUR».
O que não se lê recusa-se com um aviso, e numa ranhura que o exige não
pode ficar vazio. E a proposta **não se grava por cima de uma versão
mais nova**: aberta em dois separadores, ou por dois colegas, o segundo
a gravar é recusado e vê o que está agora (25/09/2026).

**Um proposto acima do preço base recusa-se** (D2, decisão dele a
26/09/2026; até aí só avisava): pelo art. 70.º do CCP a proposta é
excluída — o n.º 2, al. d), e o n.º 3, al. d) nos procedimentos
iniciados a partir de 1/10/2026 (`docs/ccp.md`). Vale em todos os caminhos que gravam o preço — a
ficha, o selector e a caixa dele, a proposta sem anúncio e a importação
— e é **o preço base do lote** numa proposta a um lote (a coluna
`lotes` do anúncio), o total numa proposta ao conjunto. **Sem preço base
conhecido não se recusa.** O browser recusa antes de enviar, e o
servidor recusa na mesma (`recusa_do_preco()`). **O valor adjudicado
tem o mesmo tecto** (ronda em PC, 26/09/2026): acima do preço base
recusa-se, no diálogo e no servidor. Um «Relatório
preliminar» ou «Ganho» **antes do fim do prazo de entrega** continua a
gravar-se com o aviso a vermelho (`aviso_do_ccp()`), e a **data da
adjudicação** escrita no campo também, quando é anterior ao fim do
prazo; **no futuro recusa-se** (3.ª ronda, G23: um dígito trocado tirava
a Ganha do trimestre). Uma **Ganha sem lugar fica em 1.º**, e uma
proposta decidida **não conta dias** na ficha; as listas das decididas
trocam o «Falta» pelo **Desfecho** — o adjudicado da Ganha, o motivo da
Perdida e do Não fomos (G28).

**A fase que a página mostrava vai com o gesto** (ronda em PC): o
selector manda o `de`, e se a proposta já está noutra fase — mudada
noutro separador, ou por um colega — nada muda e o aviso diz em que
fase está (`recado_da_fase_mudada()`). O **desfazer** leva também a
fase em que deixou a proposta, e recusa se um colega a mudou depois; e
pedir a fase em que a proposta já está não é conflito — é o segundo
toque no «Mudar» (3.ª ronda, 29/09/2026). **Uma nota nova grava-se
mesmo quando a ficha mudou entretanto, ou quando outro campo é
recusado** (um preço apagado sem querer): acrescenta, não substitui; os
outros campos do bloco é que não se gravam — e só há conflito se o
pedido muda algum campo. A **tarefa** (`versao_da_tarefa()`) e o
**responsável** (o `de`) têm a mesma guarda: quem grava sobre uma página
antiga não passa por cima do colega, e o aviso diz o que está agora.

**Gravar uma vez** (3.ª ronda, G1): cada formulário leva um `envio`
aleatório, e um segundo pedido com o mesmo — o duplo toque, o «voltar»
e «Guardar» outra vez — recebe a resposta do primeiro sem gravar outra
vez (`envio_repetido()`). No browser, o botão diz «A gravar…» e
desliga-se até a página mudar.

**O desfecho tem datas e valor** (D3 e D10, 26/09/2026): o «Ganho» e o
«Perdido» pedem, na mesma caixa e sem obrigar, a **data da
adjudicação** — é por ela que a Situação conta o período — e o «Ganho»
o **valor adjudicado** (vazio, é o proposto). A partir do «Relatório
preliminar» o bloco tem a **data da notificação** do relatório, que abre
a tarefa da audiência prévia (§3.5).

**As notas são datadas e assinadas** (D3): cada nota nova fica com
quem e quando, e nenhuma apaga a anterior. **Quem escreveu uma nota
corrige-a ou apaga-a, sempre** (D6 da 3.ª ronda, 29/09/2026), e o
histórico guarda o que ela dizia («nota corrigida», «nota apagada»);
as dos outros não se tocam. A nota única que cada
proposta tinha passou a ser a primeira, «antes das notas datadas».
Uma proposta **fechada com tarefas por fazer** di-lo no bloco, com um
«fechar as N tarefas». O histórico guarda **o antes e o depois** do
preço e da fase («Submetida → Relatório preliminar»), e a ficha
mostra as 12 entradas mais recentes com um «ver as N».

Os motivos são **vocabulário fechado** (é o que os faz dar contas):
perda — *Preço · Qualidade técnica · Prazo · Habilitação e
certificações · Proposta excluída*, **genéricos para todas as
empresas** desde 28/09/2026 (eram os da LATD: «CV's», «Proposta
técnica», «Certificações», que passaram aos novos no
`iniciar_empresa()`, pelo `MOTIVOS_QUE_MUDARAM`); não fomos —
*Preço base baixo · Falta de certificações · Falta de equipa ou
capacidade · Não faz parte da oferta* (era «Falta de CV's» até
28/09/2026; passa no `iniciar_empresa()` e no modelo Excel).

### 3.2 Anúncio ≠ proposta

Tabelas separadas, por duas razões que o estado do anúncio não consegue
ser:

- **Lotes** — um concurso de três lotes pode acabar com o L1 ganho e o
  L2 perdido. Uma linha não cabe dois resultados.
- **Propostas sem anúncio** — consulta prévia, ajuste directo, convite.
  `ref` a NULL é legítimo; o `porque_sem_ref` diz porquê.

### 3.3 O perfil da empresa (o interesse)

**Chama-se «Perfil da empresa» em tudo o que o utilizador lê** desde
26/09/2026 (decisão dele, na segunda ronda de testes: «Interesse»
colidia com o botão «Interessa», que é outra coisa). No código, nas
chaves do `config.json` (`interesse_*`), no `?interesse=nao` e na rota
`/configuracoes/interesse` continua a chamar-se **interesse** — são
endereços guardados e configurações gravadas. Este documento usa as
duas palavras para a mesma coisa.

Uma lista de CPV que a empresa trabalha (e outra de exclusões), em
Configurações › Perfil da empresa, com uma dica por cima da árvore
(`DICA_DO_PERFIL`, 30/09/2026): marcar as áreas em que um comprador o
publicaria, duas a quatro. Recorta **a lista, o Hoje, o
Calendário, o Mercado e a ficha da entidade**. Levanta-se com
`?interesse=nao`.

Desde 25/09/2026 leva também **os distritos** do local de execução e
**um preço base mínimo** (`interesse_distritos`, `interesse_pbmin`).
Esses dois recortam só os **anúncios** — os contratos do Mercado não os
têm na mesma forma, e a faixa do Mercado diz isso mesmo em vez de
prometer o perfil inteiro (26/09/2026). Um concurso nacional entra em qualquer distrito; um
anúncio sem distrito lido, ou sem preço base, fica de fora quando se
pede um ou outro. Os mesmos dois campos existem no filtro dos Concursos
e no do alerta (`dist`, `pbmin`, `pbmax`, no `condicoes()`). **Desde
1/10/2026 o valor é o preço base e, só quando não há, o preço estimado**
(`SQL_PRECO_DO_ANUNCIO`): o DL 177/2026 tornou o base facultativo, e sem
isto um anúncio só com o estimado ficava fora de todos os filtros e
alertas por valor. Um anúncio sem nenhum dos dois continua de fora.

**Não recorta os alertas, e é de propósito.** O interesse é recorte de
**página** (entra por `com_recorte()`), não de motor — um interesse
dentro do `condicoes()` cegava os alertas e os filtros guardados em
silêncio: um alerta deixaria de ver o que vê hoje sem ninguém lhe ter
tocado. **O interesse esconde, o alerta avisa** (§3.8); são coisas
diferentes e não se recortam uma à outra.

### 3.4 A entidade, e a chave

**A chave é uma só**: o NIF quando existe, `n:` + nome normalizado
quando não. O nome **não** é a identidade — a Universidade do Porto
aparece com 84 nomes, a MEO com 81, todos com o mesmo NIF.

**Toda a entidade tem ficha**, tenha ou não contratos no corpus.

### 3.5 As tarefas

Duas origens:

- **Automáticas** (`esclarecimentos`, `entrega`) — nascem das datas do
  DR quando um concurso entra na escada, e **acompanham-nas**.
  **Uma que já nasceria atrasada não se cria** (25/09/2026, decisão
  dele): entrar na escada depois de os esclarecimentos fecharem não põe
  uma tarefa a vermelho no mesmo clique.
- **A audiência prévia** (26/09/2026) — nasce da data da notificação do
  relatório preliminar que alguém escreve na proposta: **5 dias úteis**
  depois, o mínimo do art. 147.º do CCP (contado pelo art. 87.º do CPA,
  art. 470.º do CCP). O júri fixa o prazo na notificação e pode dar
  mais: a tarefa diz para o confirmar, **adia-se e a sincronização
  respeita** (ao contrário das do DR). Conta sábados e domingos e não os
  feriados, por isso sai igual ou mais cedo do que o verdadeiro. Outra
  data de notificação refaz-a; a proposta fechada tira-a.
- **A validade de um documento do cofre** (26/09/2026) — **15 dias
  antes** de cada validade (§4.8), **ou hoje**, se isso já passou (um
  alvará registado a dez dias de caducar é trabalho para hoje, não
  «atrasado»); é **de quem registou** o documento. Mudar a validade
  troca-a pela da data nova, mesmo que a velha já estivesse feita;
  tirar o documento leva-a.
- **Escritas à mão** — nunca se tocam.

**Vivem no Hoje e no Calendário** (este desde 26/09/2026, D12): as por
fazer aparecem no dia delas, no filtro «As nossas» e no «Tudo».

**O dono de uma tarefa, e o responsável de uma proposta, são contas da
empresa** (D4 da 3.ª ronda, 29/09/2026, decisão dele). Escolhem-se numa
lista com as contas, uma vez cada, e gravam-se pela **chave da conta**
(o nome de utilizador); o ecrã mostra o nome (`contas_da_empresa()`,
`pessoa_de()`). Um nome que não é conta recusa-se. **O que já estava em
texto livre mostra-se como está** e não se perde ao gravar outro campo;
o texto antigo que é o nome ou o utilizador de uma conta conta como
essa conta — no Hoje é um só chip, e o `?quem=` apanha as duas
grafias. Adiar para uma data que já passou grava, e avisa que a tarefa
fica atrasada.

**O histórico diz o que era e o que ficou**: quem cria uma tarefa é o
autor, e o dono vai ao lado («… (para Rui)»); mudar a data ou o dono
escreve «quando 30/09 → 02/10 · quem A → B»; na proposta, as datas, o
responsável e os documentos prontos («6 de 8 → 8 de 8») também. Uma
mudança que não muda nada à vista não se regista.

**Nada se move sozinho.** Um prazo que passa não muda ranhura nenhuma:
aparece no balde «prazo passou sem decisão» e quem escolhe é a pessoa.

### 3.6 As peças, e o que o modelo lê

**Os ZIP abrem-se por dentro** (23/09/2026): todos, até três níveis de ZIP dentro de ZIP, com os PDF, os `.docx` e (desde 28/09/2026) o **Excel** lidos; de um ZIP, o modelo recebe só os ficheiros de dentro que são o Caderno de Encargos, o Programa ou um anexo técnico. Os `.7z` também (`py7zr`), lidos quando se pedem as peças ou a leitura do concurso.

**O Excel lê-se** (28/09/2026): os `.xlsx` e `.xlsm`, pelo `openpyxl` (`texto_do_xlsx()`), uma linha por linha da folha e uma «página» por folha. É lá que estão os mapas de quantidades, os cadastros dos equipamentos e as listas de preços unitários. O `.xls` antigo **não** — pedia outra biblioteca, e eram 2 em 24.

**A leitura é da plataforma, e partilhada** (F7, 23/09/2026; decisão
dele: o que poupa custos e não é de uma empresa é de todas). Uma leitura
completa serve todas as empresas e **não se refaz a pedido** — o botão
«Reler pelo modelo» só o dono o vê; quem a refaz é a vigilância das
peças, quando aparece uma peça nova. Uma leitura a meio, ou por fazer,
pede-se da ficha, até ao tecto diário de cada empresa
(`leituras_por_empresa_por_dia`, 10 de origem, na tabela
`leituras_pedidas`); o que a plataforma lê sozinha não conta, e o dono
não tem tecto (`pode_pedir_leitura()`).

Os documentos do procedimento — Caderno de Encargos, Programa de
Concurso, anexos. Vêm em duas metades, e convém não as confundir.

**Trazer.** Só das plataformas que o permitem sem sessão iniciada:
`acingov`, `vortal`, `compraspt`, `anogov` (`PLATAFORMAS_COM_PECAS`).
Dispara ao pôr um concurso em «Por analisar» — é esse o sinal de que se
vai trabalhar nele. **Os ficheiros ficam em disco (`pecas/`), não
na base**, para o `radar.db` não crescer com PDF.

**Ler.** Um modelo lê o CE (com os **anexos técnicos**, desde
28/09/2026) e o PC e preenche **três campos**:
`objecto`, `equipa`, `documentos_proposta` (`CAMPOS_LIDOS_PELO_MODELO`).

**O campo 11 muda com o tipo de contrato** (28/09/2026, o
`docs/historico/MAPA.md`). O tipo sai do anúncio e do CPV, sem modelo
(`familia_do_contrato()`), e cada um tem a sua pergunta, as suas âncoras
e o seu rótulo na ficha (`CAMPO_11`):

| Tipo | Na ficha | O que se pede |
|---|---|---|
| Serviços de TI, projectos, consultoria, formação | Equipa | Os perfis, com as horas e o valor/hora quando o CE os fixa, e o nível de serviço (tempos de resposta, horário, disponibilidade) desde 29/09/2026 |
| Obras | Equipa técnica e alvará | Equipa técnica (com a remissão para a lei da qualificação), equipamento a montar, mapa de quantidades, condicionantes. O alvará sai do anúncio, e não desta pergunta, desde 29/09/2026 — ao lado dele, o que o Programa diz (`analise.habilitacao`, em baixo) |
| Bens — e, desde 29/09/2026, as licenças e o suporte de fabricante com CPV de TI (`RX_LICENCAS`, pela designação do contrato) | Artigos e especificações | Artigos, quantidades, características, marcas e «ou equivalente», entrega, garantia |
| Mão-de-obra (limpeza, vigilância, refeições) | Postos e horários | Postos × horário × dias, habilitações, equipamentos, regime dos trabalhadores |
| Outros serviços | Nível de serviço | Âmbito, tempos de resposta, qualificações, volume |

Sem tipo nem CPV fica «Equipa», a pergunta de antes. A resposta vai
sempre para a coluna `analise.equipa`; a afinação do `config.json` para
a `equipa` vale só para a família «equipa».

**A versão da pergunta** (D8 da 3.ª ronda, 29/09/2026, decisão dele).
Cada leitura guarda a versão das perguntas com que se fez
(`analise.pergunta`, `VERSAO_DA_PERGUNTA`, que sai do próprio texto das
`INSTRUCOES_*`: mudar uma pergunta muda a versão sem ninguém se
lembrar). **As leituras das propostas abertas** — Por analisar, A
preparar, Submetida, Relatório preliminar — lidas com uma versão
anterior **relêem-se sozinhas**, pela fila das incompletas
(`refs_com_leitura_incompleta()`), depois delas e com o mesmo tecto por
volta: sem rajada, que as reservas não aguentam. As outras ficam como
estão, e a ficha diz «lida a dd/mm/aaaa com uma versão anterior da
pergunta» (`leitura_desactualizada()`).

**Nas obras muda também o objecto** (29/09/2026, `OBJECTO_DA_FAMILIA`):
o que se constrói está na memória descritiva e no projecto, e não no
Caderno de Encargos, que remete para eles. A leitura do objecto de uma
empreitada lê os anexos técnicos à frente do CE e pergunta a obra, os
trabalhos principais e o local da obra (morada, troço, quilómetros).
Sem memória descritiva, os trabalhos saem dos **capítulos do mapa de
quantidades** (`capitulos_do_mapa()`) ou da «Descrição da obra» do plano
de segurança ou de resíduos (29/09/2026).

**O local**, nos outros tipos, é o que uma cláusula nomeia — as
instalações, a morada, o local de entrega —, com o regime (presencial,
remoto, híbrido) só quando o documento o fixa. Até 29/09/2026 a
pergunta só aceitava o regime, e respondia «não consta» a uma cláusula
«Local da prestação» com a morada. **Quando a leitura não traz local
nenhum, a ficha mostra o do anúncio** — a localidade, a freguesia, o
concelho e o distrito da secção 9 (`local_do_anuncio()`) — e diz que é
do anúncio (29/09/2026).

**Os anexos técnicos** reconhecem-se pelo nome (`RX_PECA_TECNICA`):
especificação, anexo técnico, memória descritiva, mapa de quantidades,
cadastro, lista de preços unitários. Ficam de fora os formulários da
proposta, o DEUCP, as garantias e as respostas a esclarecimentos
(`RX_NAO_TECNICA`). O `Lista.pdf` decide-se pelo cabeçalho (29/09/2026):
é anexo técnico quando é a «Lista de artigos» ou a «Lista de todas as
espécies de trabalhos» da plataforma, que eram os 14 da base.

**O que chega ao modelo** (28/09/2026, `docs/historico/LEITURA-VALIDADA.md`).
Cada peça dá um recorte de até `TECTO_RECORTE` caracteres, feito das
zonas onde as âncoras se juntam: os títulos, e as frases do corpo que
dizem a resposta («…pelos seguintes documentos:»), escolhidas pela
**densidade** e cortadas no orçamento — menos metade, que fica guardada
para as frases do corpo, e onde cada uma (o local, o objecto, a lista,
o limiar do preço anormalmente baixo) tem a sua parte (29/09/2026). A
janela de uma dessas frases vai até ao fim do artigo dela. O título que
se repete (o sumário) cede ao do corpo; o mesmo documento duas vezes
conta uma; o último documento escolhe as zonas dentro do que ainda cabe
no pedido. A leitura do Caderno abre também o Programa, e a do Programa
o Caderno, mas só pelo que as âncoras apanharem
(`SECUNDARIAS_DA_LEITURA`); sem a peça da leitura, a outra faz as vezes
dela. Medido com as passagens que se provou estarem nas peças: a
28/09/2026 chegavam 20 de 55, e passaram a 44; a 29/09, com 88
passagens, de 52 para 82; e à tarde, com 113, de 89 para 103 (as 88 de
antes voltaram a 82, depois de o lote 4 as ter posto em 79).

**A página em cada linha** (29/09/2026, 3.ª ronda: «um resumo em que se
pode confiar, sempre com a leitura das peças associada»). O recorte leva
«[pág. N]» onde cada página começa — quando o texto sabe páginas: um
`.docx` ou um Excel não sabem, e não se inventam —, e as perguntas pedem
que cada linha da resposta acabe com a página de onde veio, «(pág. 12)»,
ou «(Programa, pág. 5)» quando o pedido leva mais de uma peça. A ficha
mostra-a em cada linha.

**E a página abre a peça** (30/09/2026, L1 do plano de Outubro): a
citação é uma ligação (`citacao_com_ligacao()`) que abre a peça dentro
da ficha, nessa página, com o excerto por cima — uns 240 caracteres à
volta das palavras da linha (`excerto_da_pagina()`), a dizer «pág. N de
M» e, quando a linha não se acha tal qual na página, que fica o início
dela. **Qual é a peça decide-o a ficha** (`peca_da_citacao()`): a que a
citação nomeia, quando nomeia; senão, entre os PDF que a leitura leu, o
que tem mais palavras da linha nessa página — a leitura não guarda de
que peça veio cada campo, e a maior parte das linhas diz só «(pág. 2)».
Uma peça dentro de um ZIP não abre na página: a lista das peças só tem
o ZIP.

**A página é posta pelo código** (30/09/2026, 4.ª ronda): o modelo
acertava em 76 a 85 % das linhas. Depois da resposta, cada linha
procura-se no texto que foi enviado, por janelas de palavras, sem
acentos, espaços nem pontuação (`paginas_pelo_codigo()`); onde se acha,
a página — e a peça, quando o pedido leva mais de uma — é a desse sítio,
e substitui a que o modelo escreveu. Uma linha que passa a quebra de
página leva o intervalo, «(pág. 6–7)». Onde não se acha (um resumo, uma
reformulação), fica a do modelo **só** se for uma das páginas enviadas.
Num texto sem marcas (`.docx`) não há página, e as linhas «não consta» e
«—» também não a têm. Uma leitura guardada antes disto fica com a página
do modelo até ser relida.

**Nenhum número que não esteja nas peças** (29/09/2026). Depois da
resposta, sem modelo, cada número de cada linha tem de estar no texto
que foi ao modelo, comparado como o `ensaio-de-leitura` compara — sem
espaços nem pontuação, porque o PDF parte «1 2 meses», e também com os
espaços como separador, porque «4 1920» junto não tem o 1920 lá dentro
(`numeros_por_confirmar()`). A linha que falha fica, e **não passa por
facto**: leva «[confirmar: o número 1200 não está nas páginas lidas]».
Os algarismos colados a letras («m3/h», «ePM1»), a página citada e o
número da própria lista não se conferem. Desde 30/09/2026: os milhares
com qualquer espaço («18 000» com o espaço estreito é «18.000»)
conferem-se como um número, **inteiro** — o «7» e o «000» soltos não
sustentam um «7 000» —, e as horas são uma forma só («09:00» = «09.00h»
= «9h00»). Não se convertem unidades: «36 meses» contra «3 anos» fica
marcado, porque a regra é copiar das peças. No mesmo passo saem do objecto
as cláusulas que todos os contratos têm — cumprir a lei, o sigilo,
comunicar alterações — quando sobra alguma coisa (`sem_clausulas_tipo()`).

**Nem uma palavra com peso que não esteja nas peças** (4/10/2026). Os
números não chegam: o modelo escreveu «Ministério da Justiça» num
concurso do Metropolitano de Lisboa, «dessalinizadores» por
descalcificadores, e «1 licença» onde a tabela diz 16 (o 1 é o número
da linha). Do mesmo modo, sem modelo: as palavras com peso de cada
linha — os nomes próprios, as siglas, os códigos, os substantivos
técnicos compridos — têm de estar no texto que foi ao modelo, e a linha
que falha leva «[confirmar: «Justiça» não está nas páginas lidas]»
(`palavras_por_confirmar()`); e uma quantidade com a unidade («16
licenças», «9 recursos», «120 horas») confere-se **junto do artigo**, e
não sozinha: «[confirmar: «1 licença» não está junto de «Architecture
Engineering Construction» nas páginas lidas]» (`quantidade_sem_apoio()`).
O plural, a grafia de antes do Acordo e a palavra partida pelo PDF
valem; as palavras da própria pergunta e o IVA não se conferem. O que
falha é quase sempre o modelo a abreviar o que leu («ULS», «IA») — uma
marca a mais, e nunca uma a menos. E saem os restos do molde da
pergunta (`sem_o_molde()`): as linhas que repetem os cabeçalhos, e o
«(firme)» ou o «(estimada)» que as peças não dizem. A pergunta não
mudou, e as leituras não voltaram à fila por isto: as guardas valem
para as leituras novas.

**Na ficha, a leitura é um rascunho.** Cada linha lida diz de que peças
e páginas veio e «é um rascunho: confirmar no documento antes de
decidir». «A leitura não encontrou» quer dizer que não encontrou nas
zonas que leu; e quando a peça nem estava entre as descarregadas, a
ficha di-lo em vez de dizer que a leu. **Três faltas que não se
confundem** (3.ª ronda, G36-G38): «não encontrado nas páginas lidas»
(a peça foi lida), «o Programa do Concurso não foi lido» (a peça de
onde o campo sai não está entre as fontes, `PECAS_DO_CAMPO`), e o
mesmo «não encontrado» com «lida com uma versão anterior da pergunta».
No campo 11, o «—» é só o que as peças dizem expressamente que não há;
o que a leitura não achou diz «não encontrado» (`sem_negativos_por_saber()`).
As peças que não entraram na leitura — o ZIP do projecto, um 7z, um
Excel — listam-se por nome, «Não lido» (`pecas_nao_lidas()`).
**A caução e o alvará do Programa** (`analise.caucao`,
`analise.habilitacao`) vão ao lado do que o anúncio diz, cada um com a
fonte: quando se contradizem, vêem-se as duas versões, e o Mira Gov não
escolhe.
**As condições de pagamento** (`analise.pagamentos`, L4 do plano de
Outubro, 1/10/2026) perguntam-se no pedido do objecto, que é o do Caderno
de Encargos: a periodicidade, o prazo depois da fatura, o adiantamento,
as retenções e a fatura eletrónica, copiados como estão e com os números
conferidos como os outros. A ficha mostra-as na linha «Pagamento» de «O
que as peças pedem»; uma leitura de antes da pergunta diz que é de
antes, e não «não encontrado». **A âncora tem peso 1**, decisão dele:
com o peso 0 chegavam ao modelo 4 das 5 passagens de pagamento medidas,
mas a localização saía de 2 Cadernos; com o peso 1 não sai nada a
ninguém, e o pagamento só entra quando sobra recorte (medido nesse dia:
0 das 5).
São **três pedidos, um por campo** — não um pedido grande —, porque o
tecto da conta é por minuto e manda no tamanho do recorte
(`TECTO_RECORTE`). Cada pedido desce a cadeia `FORNECEDORES` até
alguém responder: a Groq (`gpt-oss-120b`), o Cerebras (o mesmo modelo,
com 1 milhão de tokens por dia; só entra com chave), a NVIDIA
(`nemotron-3-ultra`, com o raciocínio desligado), o OpenRouter (um
modelo gratuito, quase sempre cheio), o Gemini da Google (desde
30/09/2026, com a chave de um projecto só para a leitura; atrás dos
outros até as leituras dele serem julgadas; desde 4/10/2026 o
`gemini-3.5-flash-lite`, com 15 pedidos por minuto e ~500 por dia,
contra os 20 por dia do `gemini-3.6-flash`) e, no fim, a reserva na própria
Groq (`gpt-oss-20b`) — no fim desde 29/09/2026, por ter sido o único a
errar números nas leituras julgadas nesse dia. Todos gratuitos; a conta de 28/09/2026 dava ~20 concursos por
dia em cada modelo da Groq, ~55 no Cerebras, e a NVIDIA sem limite
publicado. Venha de quem vier, a resposta passa pelas mesmas guardas
(`conferir_a_resposta()`): o campo que chega como lista junta-se em texto
(`em_texto()`) e a página escrita a meio da linha sai — a página é a
do código.

**O campo 11 desce outra cadeia, com outro recorte** (1/10/2026,
decisão dele): a NVIDIA primeiro, depois o Cerebras, depois o resto pela
ordem de cima (`PRIMEIROS_NO_CAMPO_11`, `cadeia_do_campo_11()`). E o
recorte depende de quem lê (`TECTO_DO_FORNECEDOR`): a NVIDIA e o
Cerebras levam o dobro do `TECTO_RECORTE` por peça (e 1,5 × isso no
total, como sempre); quando o pedido cai na Groq, ou noutro de limite
apertado, vai o recorte de sempre, que o dobro dava 413. O recorte
monta-se outra vez só quando o tecto muda ao descer a cadeia
(`_perguntar_com_o_recorte_de_cada_um()`), e as páginas e os números
por confirmar conferem-se contra o recorte de quem respondeu. O objecto
e a proposta ficam com a cadeia e o recorte de cima. Medido nesse dia
sobre as frases-prova que faltavam ao campo 11 (`docs/diario/2026-10.md`).

Três regras que decidem o que se vê:

- **Uma leitura que ficou a meio volta a tentar-se sozinha.** Incompleta
  = algum dos três campos vazio. A verificação relê, mas só com
  orçamento e só sobre o que está na escada.
- **Dois becos ficam por fechar, e são das fontes e não do radar**: sem
  plataforma conhecida, as peças trazem-se à mão; sem texto extraível
  (uma digitalização), não há nada a ler. A ficha di-lo em vez de
  fingir.
- **Só documentos públicos passam pelo modelo** — Cadernos de Encargos e
  Programas. Propostas, CV e trabalho próprio nunca.

O que sai vem marcado com o nome do modelo e um aviso para confirmar no
documento: **é para decidir se vale a pena abrir os PDF, não para
assinar por baixo.**


### 3.7 De onde vêm os anúncios

Duas fontes, e nenhuma tem API pública.

**O Diário da República, parte L** é a fonte principal. O radar faz os
mesmos dois pedidos que o browser faria: a pesquisa, e o detalhe de cada
anúncio. Para os saber fazer precisa de duas **capturas** cURL, tiradas à
mão uma vez no DevTools — o gesto está no `LEIA-ME.md` §3. Sem a do
detalhe recolhe na mesma, mas fica sem CPV, sem prazo e sem preço base.

**A Vortal** dá só as **consultas preliminares** de mercado, que o DR não
publica (`recolher_vortal()`, desde 31/08/2026). É pesquisa pública: não
leva captura nenhuma. Entram no «Por ver» como qualquer anúncio, com a
etiqueta `vortal`, e **só esse tipo entra** (`TIPOS_PRELIMINAR`) — os
concursos públicos da Vortal já vêm pelo DR, e trazê-los outra vez era
mentir nas contagens.

Três coisas que mudam o que se pode desenhar:

- **O que a captura ainda dá é a forma do pedido, não a credencial.**
  Desde 2/09/2026 o token e a `apiVersion` vêm do próprio portal a cada
  verificação — o `perguntar_ao_dr()` renova-os à força e repete uma vez
  antes de declarar expiração. Uma captura «expirada» é hoje uma captura
  cujo **corpo** deixou de servir: refaz-se, não se renova.
- **Não se filtra nada à entrada, e isso é uma escolha.** O termo de
  pesquisa existe no pedido e está **vazio** (`termos_de_pesquisa: [""]`);
  a janela são os últimos 15 dias (`dias_catchup`); a triagem faz-se toda
  no painel. Há `termos_de_reserva` para o caso de a pesquisa sem termo
  devolver zero — nunca disparou.
- **Entra tudo o que a parte L publicar.** É por isso que há 210 mil
  anúncios e não os mil que interessam: o recorte é do ecrã, nunca da
  recolha.

---

### 3.8 Os alertas, e o resumo que sai

A contrapartida de não se filtrar à entrada: se entra tudo, alguém tem
de avisar. **O interesse esconde, o alerta avisa** — são coisas
diferentes (§3.3).

**Reconhecer não é enviar, e essa separação é o desenho.** A
verificação corre de hora a hora e o resumo sai 1×/dia; se fossem o mesmo
passo, saíam dois e-mails com metade das coisas cada um.

**O alerta do perfil** (D13, 26/09/2026): em Configurações › Alertas,
um botão cria — ou actualiza, pelo nome «Perfil da empresa» — o alerta
com os CPV, as exclusões, os distritos e o valor mínimo do perfil
(`consulta_do_perfil()`), nos mesmos campos do filtro. O alerta escrito
à mão também leva **vários distritos** (caixas, como no Perfil; ronda em
PC), e um valor que não se lê — uma data, um preço — recusa-o a
vermelho, sem gravar.

1. **Reconhecer** (`registar_alertas()`, `registar_seguidas()`, a cada
   verificação): anota na `alertas_vistos` que anúncios caem em que
   alerta. A tabela é a memória — **um anúncio nunca é avisado duas
   vezes**, nem que a verificação corra dez.
2. **Enviar** (`enviar_resumo()`, a partir da `hora_resumo`): junta o
   que está reconhecido e ainda não saiu, manda um e-mail e só então
   marca como enviado.
3. **Avisar logo** (`enviar_imediatos()`, a cada verificação, antes do
   resumo; 25/09/2026, do teste com utilizadores): um alerta com
   `imediato=1` («avisar logo», na lista dos alertas) manda o que lhe
   caiu no e-mail dessa verificação, e marca-o enviado — o resumo do dia
   já não o repete. Os outros alertas continuam só no resumo.

**Corre depois de `ler_detalhes()`, e isso não é arrumação:** um alerta
por CPV só apanha o anúncio depois de o CPV estar lido.

**Três coisas entram no resumo**, e só a primeira precisa de um alerta:

| | De onde vem |
|---|---|
| os anúncios que caíram nos teus alertas | `filtros_guardados` com `alerta=1` |
| os anúncios **alterados** | a tabela `alteracoes`, da releitura dos marcados |
| as novidades das **entidades seguidas** | casadas pelo **NIPC**, nunca por nome |

Quatro comportamentos que decidem o que chega:

- **Só a parte do filtro que os anúncios entendem é que alerta.** Um
  filtro que mistura campos de contratos passa por `filtro_para(…,
  "anuncios")`; sem isso, um alerta «CPV 72 + ganho pela concorrência»
  avisava de **todos** os anúncios de CPV 72.
- **O estado não entra.** Procuram-se anúncios que correspondem; a
  triagem deles é outra conversa.
- **Um alerta não se grava com o que o filtro não lê** (26/09/2026):
  uma data impossível ou um valor que não é valor recusam-no, com a
  razão. Na lista, o mesmo erro ignora-se e avisa-se; um alerta avisa
  quando ninguém está a olhar, e ia apanhar a base inteira. O destino
  do resumo também se valida no servidor.
- **A página dos alertas diz quando o e-mail não sai**, e porquê
  (`porque_o_email_nao_sai()`: falta a conta que envia, falta a
  palavra-passe, ou falta o endereço). «Sem destino» e «por configurar»
  são duas frases desde 26/09/2026.
- **Sem e-mail configurado, o ficheiro é a entrega.** O resumo escreve-se
  sempre no `AVISOS.txt`, e nesse caso dá-se por avisado — senão o painel
  dizia «153 por avisar» para sempre e reescrevia o mesmo resumo a cada
  volta. Uma falha a sério (senha recusada, rede em baixo) **não** marca,
  para voltar a tentar.
- **Cada envio fica registado, e por onde saiu** (30/09/2026, L7 do
  plano de Outubro). Um envio é um alerta e o minuto em que se marcou
  (`marcar_alertas_enviados()`), e a coluna `canal` da `alertas_vistos`
  diz se foi «por e-mail» ou «só no AVISOS.txt» — o caso de cima, que
  conta como enviado. `envios_dos_alertas()` lê-os, e aparecem em três
  sítios: nas Configurações › Alertas (um envio por linha, com os
  anúncios a abrir por baixo do número), na ficha do anúncio («avisado
  a … pelo alerta …», no Histórico) e na página da empresa na
  plataforma, para o dono. Os envios de antes da coluna ficam sem canal
  («—»). O acervo, o que já lá estava quando o alerta nasceu, não é
  envio.
- **Uma entidade que se começa a seguir entra com o acervo marcado como
  já visto**, senão o primeiro resumo trazia dez anos de uma vez.
- **Qualquer entidade se segue, com ou sem NIF** (25/09/2026). Com NIF,
  os anúncios casam pelo NIPC; sem ele (as consultas da Vortal, uma
  entidade só com nome), pelo nome normalizado, e só com anúncios que
  também não tragam NIF.

**A maquinaria está construída e por estrear**: o canal funciona, mas
nunca se criou um alerta, e por isso o resumo leva só alterações. As
contagens estão no §7.6, e o gesto que falta — ligar um alerta, seguir
uma entidade, ver o que chega — está no `BACKLOG.md`.

---

## 4. O que já está feito, ecrã a ecrã

**140 rotas.** A barra tem **o logótipo, seis itens e a Ajuda** desde
26/09/2026 (D11 da segunda ronda: a Situação entrou, a Ajuda é um «?»
com nome depois das Configurações, e as Entidades são aba do Mercado).
Eram cinco itens desde 24/09/2026
(a do Mira Gov, por ordem de uso diário):

- **Mira Gov** (o logótipo) = **Hoje**, `/` — a marca é a abertura
- **Concursos** → `/concursos`: as pontas da escada (Por ver, Expirou
  sem ver, Todos), que são anúncios
- **Propostas** → `/propostas`: as oito ranhuras da empresa. O endereço
  antigo, `/concursos?estado=<ranhura da empresa>`, serve a mesma página
- **Situação** → `/situacao` (26/09/2026; até aí só se chegava pelo
  «Em jogo» do Hoje)
- **Mercado** → `/contratos` · aba **Entidades** `/entidades`, ao lado
  dos dois modos da tabela (26/09/2026; era vista na barra)
- **Calendário** → `/calendario`, com três filtros (§4.3)
- **Configurações** → `/configuracoes` (9 secções)

**No telemóvel (abaixo de 600 px) a navegação vai para baixo** (D9 da
segunda ronda, 26/09/2026, decisão dele): uma barra fixa em baixo com
**Concursos, Propostas, Situação, Calendário e «Mais»** — o «Mais» abre
o Mercado, as Configurações, a Ajuda e o sair (a «conta» saiu a
30/09/2026: as Configurações abrem-na) —, cada destino
com ícone e nome, alvos de 60 px de altura, o `aria-current` no aceso (e
o «Mais» aceso quando a página vive lá dentro), e a área segura do
iPhone respeitada. Em cima fica a marca (o Hoje) e quem está. O
conteúdo e o `scroll-padding-bottom` guardam a altura dela, para nada
nem o foco ficarem tapados (WCAG 2.4.11). O dono sem empresa tem em
baixo os Concursos e o Mercado, e a Plataforma no «Mais». Em ecrã largo
a barra de cima fica como está (`barra_de_baixo()`).

**O título da aba do browser conta as tarefas atrasadas** — «(2)
Concursos — Mira Gov» (1/10/2026, Z2 da `docs/historico/UX-7-LEIS.md`):
é o número do balde «Atrasadas» do Hoje, de toda a gente
(`quantas_atrasadas()`), em todas as páginas de uma empresa. A marca
continua sem contador. E o **cabeçalho de todas as páginas é um só**:
o título e, por baixo, o subtítulo à vista (J3; até aí, em oito ecrãs,
o título vivia dentro do `<summary>` de um «?»).

À direita, o menu da conta: o nome de quem entrou e, **por baixo, o da
empresa em que está a trabalhar** (D7 da segunda ronda, 26/09/2026,
decisão dele; `nome_da_empresa_activa()`) — «Empresa N» enquanto ela
não tiver nome, e nada para o dono sem empresa. Com várias empresas na
plataforma, é o que impede de triar na errada sem dar por isso. Uma
conta continua a ser de **uma** empresa só. O menu é o mesmo `mg-menu` do «Mais» da barra de baixo
(«A conta», «Sair», «Sair de todos os aparelhos»), e fecha com o Esc, com
o Tab para fora ou com um clique fora (3.ª ronda, G71).

**A pesquisa geral** (J1 da auditoria das sete leis, 2R-D8; 1/10/2026):
entre a navegação e o menu da conta há uma caixa só, «Procurar
(Ctrl+K)», que acha **concursos** (pelo título, pela entidade, pela
referência e pelo NIF, por pedaço de palavra, com todas as palavras
lá — os mais recentes primeiro, sem as republicações), as **propostas
da empresa** de quem procura (nunca as de outra: vivem no ficheiro
dela) e as **entidades do Portal BASE** (por todas as grafias do nome,
ou pelo NIF). **Ctrl+K** (ou Cmd+K) em qualquer sítio, e **«/»** fora de
um campo, levam lá; a lista cai por baixo 200 ms depois da última
tecla, a partir de três letras, e as setas andam por ela. Enter abre a
página `/pesquisa?q=…`, que também serve quem não tem JavaScript, com
as ligações «Ver todos na lista dos Concursos» e «Procurar mais
entidades». O dono sem empresa também procura (está na
`LEITURA_DO_DONO`), e as propostas dele são nenhumas. Os concursos vão
por um índice de texto (§2.1); as respostas medidas numa cópia das
bases ficaram entre 0,02 e 0,09 s a quente.

### 4.1 Hoje — `/`

Responde a quatro perguntas em três segundos: *o que tenho de fazer
hoje · o que fecha esta semana · o que mudou · o que está parado.*

0. **Pôr a empresa a trabalhar** (D13 da segunda ronda, 26/09/2026,
   decisão dele) — só ao admin, por cima de tudo, enquanto faltar
   algum dos quatro passos: **Perfil da empresa** → **nome e NIF** →
   **um alerta** → **convidar a equipa**. Cada passo é a ligação para
   onde se faz, e **risca-se pelos dados** e não por um clique
   (`passos_do_arranque()`): o perfil com alguma coisa, o nome **e** o
   NIF, um alerta ligado, e mais uma conta na empresa ou um convite
   feito pelo admin (o do pedido de acesso não conta). Um passo desfeito
   volta a aparecer. Sai quando os quatro estão feitos, ou com
   **Dispensar** (`/arranque/dispensar`, só admin), que vale para a
   empresa (`MARCA_DO_ARRANQUE`). **Com metade feita, encurta** (ronda
   em PC): só os passos que faltam, uma linha cada.

1. **Título** = a data por extenso («Sexta, 18 de setembro»), e não a
   saudação do `EcraHoje` (decisão dele de 17/09/2026, mantida a
   24/09). Por baixo, o que a última verificação trouxe («Última
   verificação às 14:10: 41 anúncios novos, 3 peças novas»); à direita,
   **Verificar agora** (só o dono). Desde 24/09/2026 o «Para fazer» é o
   cartão principal, com faixa, e os blocos da direita são cartões com
   título e meta.
2. **Quatro indicadores** (o `Stat` do sistema de desenho, desde
   22/09/2026) — em jogo · taxa de vitória · por decidir · para fazer,
   com as atrasadas na nota. **Cada um abre exactamente a lista que o
   produz** — o **em jogo** é só o que já se entregou, «Submetida» e
   «Relatório preliminar» (D12 da 3.ª ronda, 29/09/2026: o por submeter
   é o trabalho do Hoje, não dinheiro em jogo), e abre o mesmo número
   na Situação (`#entregues`); a taxa abre as decididas de sempre
   (`#decididas`), ganhas e perdidas, que é o que ela divide, e diz-se
   «2 ganhas em 4 decididas — a taxa aparece às 5» (`frase_da_taxa()`);
   o «por decidir» é a aba «Por ver» (os que ainda têm prazo).
3. **Fita da semana** — sete células, **de ontem em diante** (`_inicio_da_fita()`; até
   29/09/2026 era seg→dom). Cada uma: nº de tarefas,
   nº de feitas, e as entregas **em duas** (D12): as **por entregar**
   (laranja; «Por analisar» e «A preparar», `ESTADOS_POR_ENTREGAR`) e as
   **já entregues**; a de hoje diz também quantas atrasadas arrasta
   (vermelho). **Clicar num dia muda o balde do meio**, e o balde do
   dia mostra também as entregas desse dia (3.ª ronda, G20). Setas
   de 7 dias para trás e para a frente; o «mais para a frente» é o número
   do balde do fim.
4. **Para fazer** (coluna esquerda), em cinco baldes:
   - **Prazo passou sem decisão** — propostas abertas cujo prazo do DR
     passou, com o selector de ranhura ao lado. Não dobra.
   - **Atrasadas** — com «adiar todas p/ hoje» só quando há atrasadas
     por fazer (pergunta antes; não há desfazer). Não dobra.
   - **O dia escolhido** na fita (por omissão, hoje). Não dobra.
   - **Próximos N dias** (até ao fim da fita, e sempre pelo menos
     até daqui a sete dias, `_limite_da_semana()`, para uma entrega da
     segunda seguinte não ficar dobrada — G32) · **Mais para a frente e
     sem data** — dobram. As tarefas sem data vivem no último, e o
     aviso de as criar di-lo (G33).

   Os que não dobram mostram as primeiras linhas (`CABEM_NO_BALDE`;
   `CABEM_SEM_DECISAO` no primeiro) e o resto num **«mais N»** que se
   abre ali; o número do cabeçalho conta todas (22/09/2026).

   **A linha de tarefa**: caixa de ✓ · texto (a origem automática vai na
   dica do texto, não numa etiqueta) ·
   dia · **de que concurso é** (ref · entidade), que **liga à tarefa
   dentro do bloco da proposta** (`_alvo_da_tarefa()`) · avatar de quem
   (tracejado = sem dono) · entrega, ou «fecha hoje», ou a fase de uma
   proposta já decidida (G28) · **«adiar · quem»**, dobrado, com a
   mesma rota da ficha (`/tarefa/<id>/gravar`; D5 da 3.ª ronda).

   **Risca-se no sítio**: a linha fica, riscada, com «desfazer» — e a
   página volta à linha (`#t<id>`), não ao topo. **Só as feitas de
   hoje** ficam; as de outros dias saem do ecrã (22/09/2026).

   No cabeçalho: **pílulas de pessoa** (Todos · **as minhas** · cada
   dono, pelo nome e uma vez por pessoa · sem dono) e
   **esconder as feitas**. Tudo vive no endereço (`?dia=`, `?quem=`,
   `?feitas=`); nada se guarda no browser.
5. **Coluna direita**, três caixas:
   - **O que mudou** — três números (anúncios novos · no perfil, ou
     «sem perfil: contam todos» · peças novas hoje) e um feed: os novos que caem no perfil, peças
     novas, **prazos alterados por republicação** (só os do perfil), e
     as propostas que o Portal BASE **já diz adjudicadas** e nós não
     fechámos. Os anúncios novos não contam as republicações, e o
     subtítulo da página conta o mesmo (`novos_de_hoje()`); as peças
     trazidas depois da verificação contam-se à parte no subtítulo («e
     N trazidas depois»). Quando a última verificação falhou, **só o
     dono** o lê na meta, em palavras e com o sinal («a última
     verificação falhou às 20:00», a vermelho, a razão na dica); o
     gestor e o utilizador vêem a hora, em tom normal (30/09/2026).
   - **Prazos a chegar · 7 dias** — todas as entregas das propostas
     abertas, **por entregar** primeiro e **já entregues** à parte; o
     que passa das cinco dobra num «mais N» (G19, D12).
   - **Paradas há mais tempo** — dias desde o último movimento (laranja
     acima de 30). Só a partir de uma semana parada
     (`DIAS_PARA_ESTAR_PARADA`); sem nenhuma, a caixa não aparece.

### 4.2 Ponto de situação — `/situacao`

Como vai o negócio. **Três abas** (Negócio · Triagem · Por área CPV) e
um **período** (este mês · este trimestre · 12 meses · tudo), com
comparação com o período anterior **do mesmo tamanho**.

- **Cinco números**: por submeter · em jogo · taxa de vitória ·
  ganho (€ e nº) · desconto médio nos ganhos. **Cada um diz, por baixo,
  o que soma** (26/09/2026): o «em jogo» partiu-se em dois (D10) — **por
  submeter** é o preço base das propostas em «Por analisar» e «A
  preparar», **em jogo** o proposto das que estão em «Submetida» e
  «Relatório preliminar» (o base, quando falta), e é o mesmo número do
  «Em jogo» do Hoje (D12 e G25 da 3.ª ronda, 29/09/2026); o ganho
  é a soma do **adjudicado** das ganhas (o proposto quando falta, o
  base quando faltam os dois); a taxa é ganhas ÷ (ganhas + perdidas),
  sem os «Não fomos» nem os cancelados; o desconto é a média simples,
  com a pesada pelo valor ao lado. **E cada um é uma ligação**: os dois
  do «em jogo» à sua lista, com o total (`tabela_em_jogo()`), os outros
  três à tabela **«Decididas»** do período — as ganhas e as perdidas,
  com a data, os três preços e o total.
- **Negócio**: aviso das propostas por fechar · porque se perde ·
  porque não se vai · onde se ganha por área CPV · há mais tempo sem se
  mexerem · propostas por fase (as oito). O gráfico «Abertas, por fase»
  saiu a 1/10/2026 (UX-7-LEIS M1): eram as quatro primeiras barras do
  das oito, na mesma página. Cada cartão tem o seu título `h2`, e os
  subtítulos são `h3`.
- **Quem nos ganha** (no Negócio, desde 1/10/2026, L5): os fornecedores
  que mais vezes ganharam contratos em que a empresa **constou da lista
  de concorrentes** e não ganhou (`quem_nos_ganha_cx()`), com a frase «a
  empresa consta da lista de N contratos lidos, e ganhou M». Lê os
  contratos dos últimos dois anos que a recolha do Portal BASE já leu, e
  procura a empresa pelo **NIF** (Configurações › Conta). Sem NIF, sem
  corpus, sem nada lido, ou sem a empresa em lista nenhuma, o cartão diz
  qual das quatro — nunca uma tabela vazia.
- **Triagem**: o funil — entrados · sem decisão · triados · interessa.
  O segundo chama-se «sem decisão» e não «por ver» (G26): conta também
  os que já expiraram, e a aba «Por ver» só os que ainda têm prazo.
- **Por área CPV**: taxa de vitória por divisão.

O período conta pela **data da adjudicação** (26/09/2026, D3) e, sem
ela, pela **`fechada_em`** — o dia em que a proposta se marcou como
decidida no Mira Gov; a tabela marca essas com «(marcada)», e o ecrã
di-lo. Uma taxa só se diz a partir de
**5 decididos**; abaixo disso diz-se por extenso quantos faltam.

### 4.3 Concursos — `/concursos` (a lista única)

**As dez ranhuras da escada nas abas.** As duas pontas mostram
**anúncios**; as oito do meio mostram **propostas**.

Por omissão a lista vem **pela publicação**, a mais recente primeiro; o
**cabeçalho «Prazo»** troca para **o prazo mais perto primeiro**, como
numa folha de cálculo (seta ▲ e `aria-sort` quando está activo; um
segundo clique volta atrás; 30/09/2026), com os sem prazo no fim
(`?ordem=prazo`, `ordem_da_lista()`; 25/09/2026), e o do **«Preço
base»** para **o maior primeiro** (`?ordem=preco`, seta ▼; 1/10/2026,
J4) — pelo mesmo valor do filtro: o base, ou o estimado sem ele. Na
coluna, um estimado escreve-se com «(estimado)» atrás
(`preco_do_anuncio()`), e o mesmo nos alertas e nos lotes da ficha. As **Propostas** ordenam-se da mesma maneira pelo «Prazo» e pelo
«Preço base» (`cabecalho_que_ordena()`); a omissão continua a ser a
mais recente primeiro. Nos cartões do
telemóvel, onde o cabeçalho se esconde, a troca é uma ligação ao lado da
contagem. A ordem não é um filtro: não se guarda num alerta.

A caixa **Pesquisar** procura **todas as palavras**, por qualquer ordem
(26/09/2026: «limpeza manutenção» dava 0, porque se procurava a frase);
a vírgula ou a barra separam alternativas, e entre aspas procura-se a
frase exacta. Vale igual para os alertas, que usam o mesmo motor. **A
regra está escrita por baixo dos filtros** desde 1/10/2026 (fora do
«Mais filtros»: vê-se com ele fechado), e a do CPV por baixo dos do Mercado: estavam
só no `title` do campo, que não aparece no toque nem ao focar. Sem
resultados dentro do perfil da empresa, a lista diz quantos há fora dele.

Filtros: à vista só a **Pesquisa**, a **Entidade** e o **«Mais
filtros»**, que recolhe a plataforma, as datas, o distrito e os preços
(1/10/2026, H1; até aí só no telemóvel). O botão diz quantos desses
estão postos («Mais filtros · 2») e o bloco abre sozinho quando há
algum. As datas são texto `dd/mm/aaaa` com um botão ao lado que abre o
**calendário do browser** e escreve nele (J6). O CPV escolhe-se na
árvore de 9 454 códigos, por baixo; o motor entende ainda o E/OU, as
exclusões e o prazo vindos no endereço. O filtro compõe-se com o perfil
da empresa.

A **etiqueta do prazo** só tem cor quando pede atenção: laranja dentro
da janela do urgente, vermelha expirado ou a acabar hoje; o prazo
folgado é **neutro** (1/10/2026, V1; era verde), nos Concursos e nas
Propostas (`pilula_do_prazo()`).

Por linha: triar («interessa» / «abandonar», que pergunta o motivo),
**mudar de ranhura no selector**, abrir a ficha. Exporta para CSV.

**Triar sem recarregar** (D1-bis da segunda ronda, 26/09/2026, decisão
dele). No **Por ver**, o «Interessa» e o motivo do «Abandonar» gravam
por `fetch`, na **mesma rota** (`/estado/<ref>/<ranhura>`) e com o
mesmo CSRF: o servidor responde JSON a quem o pede pelo `Accept`
(`pede_json()` no `_volta_com_aviso()`), com o mesmo aviso e o mesmo
desfazer do redireccionamento. A linha sai no sítio, o aviso fixo em
baixo diz o que se fez e traz o **desfazer** (que devolve a linha ao
lugar dela), o foco passa à linha seguinte, e **o número da aba e o
«N que correspondem» descem um** — o que o ecrã mostra continua a ser
o que a ligação abre. O diálogo do «Abandonar» tem os **motivos como
botões que gravam** (um clique; o «Guardar» só aparece quando não há
motivo a escolher, como no preço do «Submetido»). Nas outras abas, e
sem JavaScript, é o POST de sempre, com a página inteira.

**Vista Calendário** — `/calendario`: o que fecha em cada dia, seis
semanas a partir de segunda-feira, a andar de semana em semana. Desde
26/09/2026 (D12 da segunda ronda, decisão dele) tem **três filtros** em
vez das onze abas da escada (`FILTROS_DO_CALENDARIO`):

- **As nossas** (a omissão): os prazos das propostas em aberto e as
  **tarefas por fazer, no dia delas**. A proposta não se desenha outra
  vez por baixo da sua «entregar a proposta», que cai no mesmo dia;
- **Por ver**: os concursos por decidir, com o perfil da empresa e a
  faixa da lista, com o «ver tudo»;
- **Tudo**: as nossas e os concursos todos (com o perfil).

O número de cada filtro é o que ele desenha nestas seis semanas, e o
«ver em lista» abre as Propostas (as nossas) ou os Concursos na aba que
diz o mesmo. Um endereço antigo com `?estado=` redirecciona para o
filtro equivalente (as ranhuras da empresa → as nossas; o por ver → o
por ver; o resto → tudo). **No telemóvel é uma agenda**: dia a dia, só
os dias que têm alguma coisa, em vez da grelha de sete colunas. Com
«As nossas» vazio nas seis semanas, a legenda di-lo e aponta os por ver
que fecham nelas (30/09/2026: uma empresa nova abria numa grelha vazia,
sem uma palavra).

### 4.4 Ficha do anúncio — `/anuncio/<ref>`

**Quem costuma concorrer** (desde 1/10/2026, L5 do plano de Outubro):
um cartão a seguir a «O mercado», com os concorrentes dos contratos desta
entidade neste CPV nos últimos dois anos, lidos do Portal BASE contrato a
contrato (`concorrentes_cx()`, `concorrentes_da_entidade()`): quantos
lidos de quantos, a média de concorrentes por contrato (só com 3 ou mais
com lista) e os fornecedores que mais aparecem, com quantas vezes
concorreram, quantas ganharam e o **desconto mediano sobre o preço base
quando ganham** neste CPV, em todas as entidades. Sem nada lido, o cartão
diz que a recolha ainda lá não chegou; os concorrentes sem NIF não
entram na tabela.

As peças descarregam-se **todas num ZIP** (`/pecas-zip/<ref>`,
25/09/2026), além de uma a uma; cada uma mostra o tamanho, e o botão do
ZIP o total (30/09/2026). Com lotes, a comparação com o que a
entidade costuma pagar faz-se **lote a lote** (`comparacao_de_preco()`),
e não pelo total.

Em **duas colunas** desde 23/09/2026 (o `EcraFicha` do sistema de
desenho), numa só abaixo de 1100px. **Desde 28/09/2026 (a ficha nova,
da maquete que ele aprovou)** a coluna da esquerda é, por esta ordem:
**Os factos do anúncio** (`para_decidir_cx()`; chamava-se «Para
decidir» até à 3.ª ronda, G49, e o bloco só tem factos: oito numa
grelha, pela ordem de `factos_para_decidir()` — preço base (ou, sem
ele, «Preço estimado», com a nota «sem preço base: não exclui
propostas»; 1/10/2026), esclarecimentos até, propostas até, duração, critério, local,
habilitação, caução; o que o anúncio não traz fica na célula, apagado,
a dizer onde está; a caução e o alvará levam ao lado o que o Programa
diz, quando foi lido), os lotes
e o desfecho quando os há, **O que as peças pedem**
(`pecas_pedem_cx()`: a leitura, marcada «Rascunho» uma vez, com as
peças e as páginas lidas; a equipa em tabela, `perfis_da_equipa()` e
`resumo_da_equipa()`, o objecto fechado na primeira linha,
`resumo_do_objecto()`), **O mercado** (`mercado_cx()`: a mediana do que
a entidade paga com a régua dos quartis, o desconto habitual, quem
costuma ganhar, e as tabelas dos homólogos e do CPV fechadas), as
peças, e o **anúncio completo**, fechado no fim (`?modo=completo`
abre-o). À direita, presa ao rolar no computador: o prazo, a nossa
proposta, o responsável, os contactos e o histórico. Abaixo de 1100px
o prazo e a nossa proposta sobem para logo a seguir ao cabeçalho, antes
dos factos do anúncio (só CSS); o resto da coluna da direita fica no fim.

**O prazo de uma republicação é o da cadeia** (`cadeia_do_anuncio()`):
cada alteração guarda o seu prazo e o original guarda o que está em
vigor; a ficha de qualquer anúncio da cadeia mostra o em vigor, quantas
vezes foi prorrogado, e de que anúncio vem. Sem leitura das peças no
próprio anúncio, a ficha mostra a mais recente da cadeia e diz de onde
veio; sem peças, aponta para o anúncio da cadeia que as tem. Desde 24/09/2026 abre com o **cabeçalho da página** (migalhas,
o título inteiro com as acções à direita, a entidade por baixo), a
**escada em quatro passos** (Interessa · Em preparação · Submetida ·
Decidida) e o **índice em pílulas**; nada disto fica preso ao rolar. Tem:

- Os factos do DR (entidade, CPV, preço base, prazo, plataforma, lotes),
  com a **habilitação** (o alvará, §12 do anúncio) e a **caução** (§14),
  desde 28/09/2026
- O **texto** do anúncio, fechado no fim
- As **peças** do procedimento, que **abrem dentro da ficha** (PDF, com
  pesquisa)
- A **leitura pelo modelo**: objecto · equipa exigida · documentos da
  proposta (+ preço anormalmente baixo, localização)
- O **histórico do cliente** — contratos dela no mesmo CPV, do corpus
- Os **contactos** da entidade
- O **desfecho** do Portal BASE, quando existe: quem ganhou, por quanto,
  e o desvio face ao nosso preço
- O bloco **«A nossa proposta»** — a ranhura, os campos que ela exige,
  as etiquetas, e **o que falta fazer** (as tarefas, com adiar e
  atribuir)

**Uma porta por gesto** (25/09/2026). Fora da escada, entra-se por
«Interessa» ou sai-se por «Abandonar», no cabeçalho, e o bloco da
proposta só diz que falta decidir; o cartão **«Responsável»** só existe
com proposta, e é o único sítio da ficha onde o responsável se escreve.
Os dois botões do desfecho («Ganhámos», «Perdemos») **propõem e não
decidem**: abrem a caixa da escada quando falta o preço proposto, e o
«Perdemos» pergunta o motivo em vez de o escolher.

### 4.5 Ficha da proposta — `/proposta/<id>`

Para as propostas **sem anúncio** (consulta prévia, ajuste directo,
convite) e para qualquer proposta. Tem os quatro passos da escada, o
bloco inteiro, os contactos, a cronologia e o apagar. `/proposta/nova`
cria uma. **Sem anúncio, o prazo de entrega escreve-se no bloco**
(1/10/2026, E6 do `docs/historico/UX-ECRAS-EM-FALTA-E-ESCURO.md`): é ele
que dá o «até …» do passo «Submetida», a coluna «Prazo» das Propostas e
a tarefa automática «entregar a proposta», que acompanha a data como as
do DR. Não chega ainda ao cartão «Prazos a chegar» do Hoje nem ao
Calendário, que lêem os prazos dos anúncios.

**Quando o Portal BASE fecha o contrato** (a faixa do desfecho, aqui e
na ficha do anúncio; `faixa_do_desfecho()`): diz a quem foi adjudicado,
por quanto, e oferece «Ganhámos» e «Perdemos». **Desde 1/10/2026 (L5)**,
se o NIF da empresa consta da lista de concorrentes de um contrato
desse procedimento e o adjudicatário é outro (`consta_da_lista()`), diz
«A sua empresa consta da lista de concorrentes; o contrato foi para X»
e **propõe** a ranhura Perdida: o «Perdemos» passa a botão primário. A
ranhura não muda sozinha. Sem a lista lida, a faixa fica como era.

### 4.6 Mercado — `/contratos`

O corpus do Portal BASE. Lista com filtros (objecto, CPV, entidade que
comprou, quem ganhou, procedimento, datas, preço), CSV, e **modo «por
fim estimado»** — o que está a acabar, que é o que volta a concurso.
**O CPV é um campo à vista** (26/09/2026): um ou mais códigos, com
sugestões pelo número ou pelo nome, e é o mesmo que a árvore enche —
a árvore só aparece sem perfil definido, o campo aparece sempre. A
tabela tem cinco colunas: celebrado (com o fim estimado por baixo) ·
objecto (com o procedimento por baixo) · entidade · quem ganhou ·
preço, com o corpo a 14 px como o dos Concursos (1/10/2026). Os
gráficos vão por baixo da tabela, em grelha, e só passam a coluna à
direita dela em ecrãs com mais de 1600px. **As três vistas** (por
celebração · por fim estimado · Entidades · Concorrentes) estão logo
por baixo do cabeçalho, por cima do filtro, e são as mesmas nas
Entidades e nos Concorrentes (J2, 1/10/2026).

**Concorrentes** (`/concorrentes`, desde 1/10/2026, L5): os fornecedores
que concorreram nos contratos do perfil da empresa (o CPV do interesse;
sem perfil, ou com «ver tudo», todos) nos últimos dois anos, a partir
das listas que a recolha já leu (`concorrencia_no_perfil()`). Uma frase
no topo diz **quantos contratos foram lidos de quantos**, e quantos
traziam lista. Tabela: fornecedor (abre a ficha) · concorreu · ganhou
(contratos lidos) · taxa (ganhou ÷ concorreu) · desconto mediano sobre o
preço base quando ganha (no perfil, de sempre, só com 5 procedimentos
ou mais). Pagina a 20, e o «N fornecedores» é o total da lista. **Os
ajustes directos ficam fora de todas as contas da concorrência** (a aba,
a ficha do fornecedor, o «Quem nos ganha»; decisão dele, 1/10/2026,
`SEM_AJUSTE_DIRECTO`): neles o BASE só lista o adjudicatário, e cada um
contava como uma vitória. A frase do topo e a nota dizem-no. Sem
nada lido, diz que a recolha ainda não chegou — sem tabela nem zeros. A
lista guarda-se pelo número de lidos (`lembrado_do_corpus()`).

`/contratos/resumo`: sete gráficos — quem ganha, quem compra, como se
compra, concentração, tamanho dos contratos, desconto, evolução —, cada
um com o título em `h2`. Um gráfico de barras que esconde valores (mais
de seis barras) e a concentração levam um «ver os números» com a tabela
deles (1/10/2026): estavam só no `title`.

A ficha de uma entidade abre-se pelo nome em qualquer linha, ou pela aba
**Entidades**; o formulário «Ficha de uma entidade» do pé do cartão do
filtro saiu a 30/09/2026 (era o terceiro caminho para o mesmo sítio).

O perfil da empresa recorta o Mercado **só pelo CPV**, e a faixa diz
que os distritos e o valor mínimo ficam para os concursos. O CSV leva
até 50 000 linhas (`TECTO_CSV`); acima disso o botão diz quantas leva
de quantas.

### 4.7 Entidades — `/entidades` e `/entidade/<chave>`

**Cinco abas**: com quem trabalhamos · seguidas · clientes que mais
compram · concorrentes que mais ganham · **contratos a acabar · 3
meses** — por baixo das três vistas do Mercado. **Pagina-se a 20**,
como o Mercado (M4, 1/10/2026), e o número de cada aba é o total da
lista paginada: o «a acabar» cortava nas 60 com a aba a contar todas.

Tabela: entidade (nome + NIF) · papel (cliente / concorrente / ambos) ·
compra · ganha (as duas **de sempre**, e o cabeçalho di-lo) · **fita do «connosco»** (um quadrado por proposta, com a
cor do desfecho, e por baixo, em palavras, quantas de cada desfecho) ·
taxa connosco · a acabar. O nome leva à ficha (a
coluna «abrir», o mesmo destino, saiu a 30/09/2026). O papel é uma
abreviatura neutra (CLI, CONC, C+C), explicada por baixo desta tabela e
da dos contratos e no glossário. **Marcando duas linhas, comparam-se
lado a lado** — o «comparar as marcadas» está por cima e por baixo da
tabela.

**A ficha** abre com **seis factos** — compra a 24 meses · quanto disso
cai no nosso CPV · a que desconto fecha · quantas propostas lhe fizemos
· a taxa com ela · o que lhe acaba em 3 meses — e tem duas colunas: o
**nosso lado** à esquerda (anúncios dela, propostas, taxa, contactos,
seguir) e o **Portal BASE** à direita (o que compra, a quem, como, ao
longo do tempo). **Sem corpus diz «sem BASE», não zero.** O filtro da
ficha (CPV, datas, valor…) aplica-se aos três factos do Portal BASE e
às listas; as listas são do acervo todo, ou das datas do filtro, e o
título de cada uma di-lo («· sempre»). **O filtro vem depois dos
números e do nosso lado** (E11, 1/10/2026): vive no topo da coluna do
Portal BASE, recolhido em «Filtrar os contratos», e abre quando está em
uso. A tabela do fim chama-se «Os últimos contratos que ganhou».

**A concorrência de um fornecedor** (desde 1/10/2026, L5): no topo da
coluna do Portal BASE, o cartão «Concorrência» (`concorrencia_cx()`)
diz «Concorreu a N contratos lidos, ganhou M» e **quem lhe ganha** — os
que mais vezes ganharam um contrato em que ele constou da lista e não
ganhou. Só aparece a quem consta de alguma lista lida. **Quem só
concorreu e nunca ganhou** não está nas entidades do corpus, e a ficha
existe na mesma: o nome vem da lista do BASE, e o cartão é o que tem.

### 4.8 Configurações — `/configuracoes/…`

Dez secções, por esta ordem. **As cinco últimas são do sistema**, e só o
dono da plataforma as abre; os **documentos** só o admin da empresa.

| Secção | O que faz |
|---|---|
| **conta** | três cartões desde 1/10/2026 (M2): **a minha conta** — palavra-passe, e-mail de contacto (o do «esqueci-me»), sessões, o **aspecto** (normal, escuro, como o sistema ou alto contraste, por pessoa — D14, 26/09/2026; D1, 29/09/2026); **a empresa e a equipa** — a nossa empresa (nome + NIF), utilizadores, convites; e o **registo do suporte**, quando o há. Os dois últimos só o gestor |
| **perfil da empresa** (`interesse`) | os CPV que a empresa trabalha, e as exclusões; os distritos (agrupados por região, cada uma com o seu «todos» — M3, 1/10/2026; grava-se o mesmo de sempre) e o preço base mínimo |
| **alertas** | filtros de alerta, entidades seguidas, o resumo por e-mail; o utilizador vê-os e só o gestor os muda (4/10/2026) |
| **importar** | o registo da empresa, pelo modelo Excel: um ensaio antes de gravar (o que entra, o que é novo, o que altera uma proposta que existe e o quê, o que o Portal BASE contradiz, as colunas que não são do modelo), a «Data da decisão» (sem ela, o prazo do anúncio), e **cada importação desfaz-se** enquanto ninguém mexer nas propostas que tocou (26/09/2026) |
| **documentos** | o cofre dos documentos da empresa (26/09/2026, D5): o alvará, as certidões da AT e da Segurança Social, as ISO 9001, 14001 e 45001, os seguros de responsabilidade civil e de acidentes de trabalho, outro — com o número e a validade, **sem os ficheiros**. Cada validade dá uma tarefa 15 dias antes (§3.5) |
| indicadores | as capturas, a recolha, o corpus — a saúde da máquina |
| capturas | os dois pedidos cURL ao DR |
| recolha | horas, janelas, a Vortal |
| leitura | fornecedor, modelo e chaves do modelo que lê as peças |
| cópias | a cópia diária (plataforma e empresa) e o ensaio de restauro |

**Como funciona** — `/ajuda` (25/09/2026, do teste com utilizadores),
o «?» da barra desde 26/09/2026 (era no menu da conta): um índice das
seis secções no topo (30/09/2026), o caminho de todos os dias num
parágrafo, e o glossário (`GLOSSARIO`) das palavras da aplicação. Cada termo tem âncora (`/ajuda#em-jogo`), e o «?» de um
bloco ou de uma página cujo nome é um termo liga à definição («Mais na
ajuda», `mais_na_ajuda()`). **As definições de lá
seguem as deste documento**: uma regra que mude aqui muda lá. No fim,
a ligação para a declaração de acessibilidade.

**O aspecto** (D14, 26/09/2026, decisão dele; o escuro e o «como o
sistema» desde a D1 da 3.ª ronda, 29/09/2026): em Configurações › Conta,
«Normal», «Escuro», «Como o sistema» ou «Alto contraste». Guarda-se
**na conta** (`utilizadores.aspecto`, `contas.gravar_aspecto()`), e não
no browser — vale em todos os aparelhos —, e o molde carimba-o no
`data-theme` (`tema_da_pessoa()`): `claro`, `escuro`, `sistema` ou
`contraste`. O `sistema` troca-o o `TEMA_DO_SISTEMA_JS`, no `<head>`,
pelo claro ou pelo escuro do computador. O ecrã de entrar, o do convite
e os de erro seguem o computador (não há a quem perguntar).

### 4.9 A porta

**Os planos** (desde 1/10/2026, L2.1 do plano de Outubro, com os planos
desse dia): cada empresa tem um — **Solo** (1 utilizador, uma sessão de
cada vez), **Duo** (2; substituiu no mesmo dia o Equipa, de 5) ou
**Corporate** (o número acordado) —, na
tabela `planos` do `radar.db`, que é da plataforma como as contas. Quem o
põe é o dono: ao aceitar um pedido escolhe-o no ecrã do aceitar (desde
4/10/2026; a oferta de fundador, que vem escolhida, é o Duo, marcado
como fundador), numa empresa criada sem pedido na `/plataforma`
(`plataforma_criar_empresa()`, 4/10/2026) escolhe-o na página dela, e
muda-se no cartão «Plano» da página da empresa
(`plataforma_gravar_plano()`). **O limite conta as contas e os convites
por usar** (`contas.lugares_livres()`): o `criar_convite()` recusa com a
frase do plano, e o `usar_convite()` volta a conferir, porque o plano
pode ter descido entretanto. **No Solo, a última entrada ganha**: o
`_abrir_sessao()` fecha as outras sessões da conta e guarda-as na
`sessoes_fechadas`, e quem as tinha vê, no pedido seguinte, «a sua sessão
foi fechada porque entrou noutro aparelho». **Os três planos têm as
mesmas funcionalidades** — a leitura das peças por IA, as tarefas
atribuídas, o Hoje por pessoa, as notas partilhadas e o cofre —: o plano
só conta pessoas (o cofre fechava no Solo até o Duo chegar). **Uma
empresa sem plano não tem limites**, e o cartão avisa.

Tudo passa por um só sítio antes de qualquer rota: o
`porta_de_entrada()`, logo a seguir ao `app`. As tabelas e a
criptografia estão no **`contas.py`**, que não importa o radar.

**Quem entra.** Três estados, por esta ordem:

1. **Com sessão** — o cookie `sessao`, válido 30 dias
   (`DIAS_DE_SESSAO`). A senha guarda-se em `scrypt`, nunca em claro.
2. **Acesso livre local** — um pedido deste computador **que não passou
   por um túnel** entra como o único utilizador, ou como o primeiro
   admin quando há mais contas (`acesso_livre_local`, a `true`). É o que
   mantém o desenvolvimento e os testes sem login a cada pedido.
3. **Nem um nem outro** — um GET é reencaminhado para `/entrar?para=…`,
   um POST leva 403. **A excepção é a raiz**: um GET a `/` sem sessão
   recebe o **site público** (`site/index.html`, desde 23/09/2026), que
   é um ficheiro estático sem dados. Desde 30/09/2026 tem os três planos
   (Solo, Duo e Corporate desde 1/10/2026, com as mesmas
   funcionalidades, o preço + IVA e só o número de pessoas a mudar) e a
   oferta de fundador,
   e o formulário pede só o nome, a empresa, o e-mail, o telemóvel e a
   área (4/10/2026; de 30/09 a 4/10 pedia também o NIF e o plano). Com `?dia=` ou outro parâmetro é a
   mesma raiz, e é o site; todos os outros caminhos **que são rotas** vão
   ao login. Um caminho que não é rota nenhuma dá o **404** do painel,
   com «Voltar ao início» (3.ª ronda, G100: era o `/entrar` com 200, um
   «soft 404» para os motores de busca).

**O que fica aberto sem sessão** não é só o `/entrar`: também o
`/saude`, o `/favicon.svg`, o **`/pedir-acesso`** (o formulário do site,
com a guarda dentro da própria rota: origem, campo-armadilha, campos
validados e cortados — o telemóvel por `telefone_valido()` —, e tectos de `PEDIDOS_POR_IP_POR_HORA` e
`PEDIDOS_POR_DIA`), e por prefixo as fontes `/tipo/<nome>` (lista branca `TIPOS`)
e a folha `/estilo/<etiqueta>.css`. Sem estes dois últimos o próprio
ecrã de entrar aparecia sem letra e sem cor. Nenhum tem dados lá dentro.
A **`/acessibilidade`** (D15, 26/09/2026): a declaração de
acessibilidade, com a estrutura do modelo do DL 83/2018 — o estado
(parcialmente conforme com a WCAG 2.1 AA), o que não está conforme, a
data e o método da avaliação, e o contacto, que é o formulário do site.
É um ficheiro do `site/`, servido **sempre** (não depende do operador),
e liga-se do rodapé do site e da Ajuda. **Quando a acessibilidade mudar,
muda-se lá** — a lista do que não está conforme é um facto com data.
Os números do site não se escrevem à mão (3.ª ronda, G101): o dos
concursos é o do `/entrar` (`concursos_na_base()`), arredondado para
baixo ao milhar (`numero_do_site()`), e o ritmo da verificação sai do
`horas_verificacao` (`ritmo_da_verificacao()`). O site e as páginas
legais levam os **tokens da aplicação** e o tema «como o sistema»
(D11), e as legais o topo e o rodapé do site; tudo entra pelas marcas
que o `_do_site()` preenche, e a moldura partilhada é o `site/moldura.css`.
Abertos, por igualdade, também o **`/robots.txt`**, o **`/sitemap.xml`**
(as páginas públicas, `paginas_publicas()`, com o `<lastmod>` da data do
ficheiro; as legais só quando existem), a **`/partilha.png`** (a imagem
do Open Graph, `site/partilha.png`) e o **`/llms.txt`** (o resumo do
site para os agentes de IA, `site/llms.txt`; 29/09/2026). Desde esse
dia o robots é uma **lista branca**: abre as páginas do mapa, o que elas
pedem para se desenharem e o `/entrar` (`ABERTOS_AO_ROBOT`), e fecha o
resto — o `/entrar` abre-se para o motor ler o `noindex` que leva. Cada
página do site tem o seu título, descrição, `canonical` e JSON-LD do
Schema.org: a inicial um `@graph` com `WebSite`, `Organization` e
`SoftwareApplication` (a oferta a 0 € da beta), mais o `FAQPage`, que
**não se escreve à mão** — o `faq_em_json_ld()` tira-o dos `<details>`
que a página mostra; as legais uma `WebPage` com o caminho de migalhas.
O `http://` passa a `https://` na Cloudflare («Always Use HTTPS»), e não
no painel, que só vê o túnel.
Desde a auditoria de 30/09/2026, as **datas dos ecrãs de exemplo** do site
contam-se a partir de hoje (`datas_do_exemplo()`: os prazos, o título e a
fita do Hoje de exemplo, que começa ontem como a da aplicação); o site
diz **quem está por trás** (o nome dele e a fotografia, a
**`/afonso-pinto.jpg`**, aberta por igualdade; sem o ficheiro, as
iniciais, `rosto_do_site()`), e nunca o nome da empresa onde trabalhou; e
o site está **no Acordo Ortográfico** («objeto», «setor», os meses em
minúscula), ao contrário da aplicação.
E, desde a F8 (23/09/2026), o **`/termos`** e a **`/privacidade`**: páginas do site (desde 30/09/2026 com o texto dos planos pagos, o `docs/historico/TERMOS-2026-10.md`: os planos, os preços sem IVA, a fatura, o pré-pago, a renovação e o preço de fundador), que só se servem com o `operador` preenchido (`operador_completo()`) — até lá dão 404 e o site não as mostra, porque uma política de privacidade sem responsável não se publica. O fim de cada verificação bate no vigia externo (`vigia_url`, `avisar_o_vigia()`), com o sufixo «fail» quando corre mal; quem avisa que o radar parou é o vigia, pela falta das batidas. E o próprio `/saude` dá 503 quando a recolha parou (`recolha_atrasada()`: a última hora marcada passou há mais de `FOLGA_DA_RECOLHA` sem verificação), para um só monitor de fora apanhar as duas avarias.
E, por prefixo, o **`/convite/<código>`** (F5, 23/09/2026): quem o abre
ainda não tem conta, e a guarda está na própria rota — o código (32
bytes aleatórios, que na base só existe em resumo), a origem do POST e
o uso único com prazo (`DIAS_DE_CONVITE`, sete). O ecrã diz **para que
empresa e com que papel** é o convite, e liga aos termos e à privacidade
quando existem (`_de_quem_e_o_convite()`, G55 da 3.ª ronda); um convite
que não serve diz «peça outro ao gestor da sua empresa».

**Do pedido de acesso à empresa a trabalhar** (F5). Em «pedidos de
acesso do site», o dono carrega em **aceitar…**, que desde 26/09/2026
(D13 da segunda ronda) abre primeiro **o perfil da empresa nova**: os
CPV que o sector diz sem dúvida (`CPV_DO_SECTOR`) mais os códigos
escritos na mensagem, e os distritos que ela nomeia
(`perfil_do_pedido()`; também o «CPV 909» escrito à mão, completado a
oito algarismos, G56 da 3.ª ronda — e quando nada se sugere o ecrã
di-lo, em vez de «vem do sector e da mensagem»), para o dono afinar
antes de aceitar — é o
«configuramos o perfil consigo» que o site promete. Só se aceitam
códigos CPV (`_perfil_do_formulario()`); vazio, a empresa define-o
depois. Ao aceitar nasce a empresa
(`criar_empresa()`), com o NIF do pedido como o NIF da empresa quando o
pedido o trouxe (de 30/09 a 4/10/2026; é o da fatura), e o ecrã diz «Empresa n.º N criada» com a ligação
para a página dela; o resumo vai para quem pediu, e um convite de
gestor dela (`contas.criar_convite()`), que vai por e-mail para
o endereço do pedido e aparece também no ecrã — o e-mail pode não sair.
O e-mail do convite (`texto_e_html_do_convite()`, 29/09/2026) tem um
botão «Criar a conta», o dia até quando a ligação vale e os passos a
seguir, que são outros para o gestor e para o utilizador.
Quem abre a ligação escolhe o utilizador e a palavra-passe e entra já,
na empresa nova (`contas.usar_convite()`). Um pedido aceite não se
aceita duas vezes.

**Os números das empresas nunca se reutilizam** (D10 da 3.ª ronda,
29/09/2026, decisão dele): a seguinte é a maior que alguma vez existiu
mais um, contando as que se apagaram — a marca `maior_empresa` da
tabela `estado` (`MARCA_DA_MAIOR_EMPRESA`) e as pastas
`copias/empresa-N-apagada-…` (`empresas_apagadas()`). Até aí era o maior
dos que existiam, e a empresa nova herdava o número da última apagada.
Nos pedidos, um «aceite: empresa N» cuja empresa já não existe — ou que
lá está mas chegou **depois** da decisão (o `decidido_em`, que o aceite
passou a gravar; nos antigos, a data do pedido e o nome) — diz
«(apagada a dd/mm/aaaa)» e não abre a outra (G57).

**O admin de uma empresa também convida** (25/09/2026, do teste com
utilizadores): em Configurações › Conta, «Criar convite» dá uma
ligação para a empresa dele, de utilizador ou de gestor, que vale sete dias
e uma vez, e se mostra **só nessa página** (`conta_convidar()`); com o
e-mail do colega, que é opcional, segue também por e-mail (29/09/2026),
como o convite que o dono cria com endereço e o que gera de novo. Criar
a conta com a palavra-passe continua a existir, por baixo.

**Cada conta é de uma empresa** (`utilizadores.empresa_id`, desde a F4
de 23/09/2026), e a porta põe a empresa dela no pedido: o `liga()`
junta o ficheiro dessa empresa, e só esse. Nada da empresa de outro se
vê em página nenhuma — é o que o `TestNenhumaEmpresaVeAOutra` percorre,
rota a rota. Na cronologia de um anúncio, uma leitura pedida por
alguém de outra empresa aparece como «Mira Gov», sem o nome.

**Três níveis.** O **dono da plataforma** (`utilizadores.dono`; o
primeiro admin, que é o Afonso) é o único que abre o que é do sistema
(`ROTAS_SO_DONO`: Indicadores, Capturas, Recolha, Leitura das peças,
Cópias, o «Verificar agora», quem envia o e-mail e os pedidos de
acesso do site); `sou_dono()` é a pergunta. O **admin** de uma empresa
cria e tira as contas **dela** — nunca a do dono, que só o dono tira, e o
último dono nunca sai (26/09/2026) — e diz quem ela é (`ROTAS_SO_ADMIN`:
`/configuracoes/conta/utilizadores`, `/configuracoes/conta/empresa` e
`/arranque/dispensar`, o cartão do Hoje, e desde 29/09/2026 o **gravar
do Perfil da empresa**, `/alertas/interesse` e `/configuracoes/propostas`
— D7 da 3.ª ronda: o perfil recorta os concursos de toda a equipa; e
desde 4/10/2026, decisão dele, **os alertas** — criar, ligar, apagar,
o destino do resumo, o «avisar logo» e a janela do urgente — e **apagar
uma proposta**: `RX_SO_ADMIN` apanha os caminhos com um número no
meio);
`sou_admin()` é a pergunta. Quem abre uma destas sem ser admin vê uma
página **dentro do molde** que diz o nome do admin da empresa, a quem
pedir (`recado_so_do_admin()`, 3.ª ronda, G17). O **tester** trabalha, e
vê o Perfil da empresa e os Alertas só para ler (os campos desligados e
a linha «só o gestor o muda»). **No ecrã os papéis chamam-se «gestor» (o admin) e
«utilizador» (o tester)** desde 29/09/2026 (D7, decisão dele: «as
expressões admin e tester devem sair»): nos ecrãs, nos e-mails, nos
convites, nas recusas e nos termos (`PAPEL_NO_ECRA`). Na base e no
código continuam `admin` e `tester`, e a conta que se chama `admin` é
um nome de conta. **As duas
administrações não se misturam** (23/09/2026, pedido dele): as
Configurações mostram só as quatro secções da empresa, a toda a gente —
também ao dono —, e as do sistema vivem na **administração da
plataforma** (`/plataforma`, pelo menu da conta), com as empresas, os
pedidos de acesso e o «Verificar agora» (`seccoes_visiveis()` /
`seccoes_da_plataforma()`). O dono **não vê** os
dados das empresas clientes, e **não é de empresa nenhuma** (23/09/2026,
decisão dele): o `apagar_empresa()` deixa-o com `empresa_id` 0
(`SEM_EMPRESA`, `contas.sem_empresa()`). Desde 24/09/2026 (pedido dele:
«na página de dono não consigo ver concursos nem o mercado») a porta
abre-lhe, **só para ler**, o que é da plataforma: os Concursos (as
pontas), a ficha do anúncio e as peças, o Mercado, as Entidades e o
CSV (`LEITURA_DO_DONO`, `dono_le()`). A barra dele tem os Concursos, o
Mercado e a Plataforma (`NAV_DO_DONO`). Os Concursos saíram a 29/09/2026
(G61 da 3.ª ronda: sem empresa nada foi visto, e as abas contavam
199 178 «sem ver») e voltaram no mesmo dia, a pedido dele («deixei de
ter acesso a concursos»). O que saiu foram as abas de uma empresa: o
dono vê só «Todos» (`ABAS_DO_DONO`), e é essa a aba que abre. A ficha
não tem os botões da escada nem a coluna
do trabalho. O `liga()` junta-lhe uma empresa **vazia e só de leitura**
(`_empresa_vazia()`), para as perguntas pelas propostas darem zero em
vez de rebentarem. O resto — as Propostas, o Hoje, o Calendário, as
Configurações da empresa — continua a redireccionar para `/plataforma`,
e um POST dá 403. Para trabalhar numa
empresa usa outra conta, dela. No acesso livre **sem conta nenhuma** as duas respostas são sim,
senão não se chegava a Conta para criar a primeira.

**Duas guardas diferentes para um POST**, e confundi-las é o erro que os
diagramas ainda têm:

- **Com sessão**, o token CSRF, derivado da sessão por HMAC e não
  guardado em lado nenhum (`csrf_bate()`) — um cookie roubado sem o
  token não serve para um POST de outro sítio.
- **Sem sessão** (acesso livre), o `origem_e_nossa()`: se o browser
  disser de onde vem, tem de ser daqui. Um pedido sem `Origin` nem
  `Referer` passa — é o caso dos testes e do `curl`, e não há sessão
  para roubar.

**O túnel é a razão de «local» não ser o IP.** O `cloudflared` liga-se
ao painel a partir de `127.0.0.1`: só pelo endereço, todos os visitantes
do endereço público eram locais. O `pedido_e_local()` conta também os
cabeçalhos de proxy e o `Host` público — qualquer um deles chega para o
pedido deixar de ser local.

**O trinco é da conta** (D2 da 3.ª ronda, 29/09/2026): cinco falhas em
quinze minutos fecham-na (`FALHAS_ATE_TRINCO`, `MINUTOS_DE_TRINCO`), e o
IP tem um tecto **muito mais alto** (`FALHAS_ATE_TRINCO_DO_IP`, 30) —
um escritório é um IP, e um colega que erre não fecha os outros. Até
aí eram cinco por e-mail **ou** por IP. A recusa diz a **hora** a que se
pode tentar («pode tentar de novo às 22:04», `contas.recado_do_trinco()`),
e não «espera 674 s». O **dono levanta o trinco** na página dos erros
(`/plataforma/erros`, cartão «Trincos fechados», `POST
/plataforma/trinco/levantar`, `contas.trincos_fechados()` /
`contas.levantar_trinco()`), e o «A tratar hoje» conta os fechados.

**A palavra-passe** (D16, 26/09/2026) tem oito caracteres ou mais, além
dos espaços; não pode ser das mais usadas (`SENHAS_COMUNS`, também com
números ou sinais à volta), um só carácter repetido, um pedaço repetido
ou uma sequência do teclado ou do alfabeto; nem ter lá dentro o nome de
utilizador ou o e-mail. Vale em todas as portas — a conta, o convite, a
consola e a ligação de repor —, porque todas passam pelo
`contas.criar_utilizador()`; a recusa diz qual das regras falhou
(`contas.problema_da_senha()`).

**Repor a palavra-passe** (D17, 26/09/2026). Há dois caminhos para a
mesma ligação. O **«esqueci-me» por e-mail** (J7, 1/10/2026): o `/entrar`
leva ao **`/esqueci-me`**, onde a pessoa escreve o e-mail da conta e, se
houver conta, recebe lá a ligação (`esqueci_me()`, rota aberta por
igualdade, com a guarda dentro). A resposta é **a mesma** exista ou não
a conta — e procurar a conta, criar a ligação e mandar o e-mail
acontece em fundo (`_repor_por_email()`), para o tempo de resposta
também não o dizer; a ligação vale **uma hora**
(`HORAS_DE_REPOSICAO_POR_EMAIL`) e uma vez; há tecto de cinco pedidos
em quinze minutos **por IP e pelo endereço escrito**, contados exista
ou não a conta e fora do trinco do `/entrar`
(`contas.contar_pedido_de_reposicao()`); a **conta do dono nunca** se
repõe por aqui (`contas.reposicao_por_email()`; fica nos eventos que
alguém pediu); e só sai com o correio da plataforma configurado — uma
falha do envio fica nos eventos. **Procura pelo utilizador ou pelo e-mail
de contacto** (`utilizadores.contacto`, desde 1/10/2026), e a ligação vai
para o endereço escrito: o convite vai para um e-mail, a pessoa escolhe
outro utilizador, e o e-mail do convite fica na conta
(`contas.usar_convite()`) — vale para o convite do pedido aceite e para o
do colega que o gestor convida. Cada pessoa vê o contacto em
Configurações › Conta e muda-o com a palavra-passe actual. Um endereço é
**de uma conta só**: o que já é utilizador ou contacto de outra recusa-se
(`contas.problema_do_contacto()`), e se ainda assim casar com duas, não
vai nada. Quem não tem contacto nem entra com um e-mail continua a pedir
ao gestor.
O outro caminho é o de antes: o **admin** gera, em Configurações › Conta, uma ligação para uma conta
da empresa dele — nunca a do dono —, e o **dono** gera-a para qualquer
conta, na `/plataforma` (`contas.pode_repor()`). A ligação mostra-se
**uma vez**, nessa página, e nunca vai no endereço nem no histórico;
vale `HORAS_DE_REPOSICAO` (24) e uma vez, e gerar outra anula a
anterior. O **`/repor/<código>`** é rota aberta, por prefixo, com a
guarda dentro (`repor()`): o código (32 bytes, na base só o resumo, na
tabela `reposicoes`), a origem do POST, o prazo, o uso único e um
trinco **só por IP e só dele** (os códigos que **não existem** contam
como entradas falhadas com a chave `repor:<ip>`, e não contam no trinco
do `/entrar` — 3.ª ronda, G50: cinco aberturas de uma ligação velha
fechavam a entrada ao escritório; uma ligação já usada ou fora do prazo
não conta nada). Ao guardar, **fecham-se todas as sessões da conta** e abre-se
uma nova para quem repôs. Pela consola continua o `--palavra-passe
NOME`. **Com o segundo factor ligado, a ligação não abre sessão**: leva
ao ecrã do código (ver a seguir).

**O segundo factor da conta do dono** (28/09/2026, decisão dele). A
conta do dono abre a plataforma inteira; com o segundo factor ligado,
a palavra-passe já não chega. É **opcional e só do dono**
(`contas.pode_ter_segundo_factor()`: a regra é por conta, e estendê-la
aos admins é mudar essa linha). O TOTP é o da RFC 6238 (HMAC-SHA1,
30 s, seis dígitos, `contas.codigo_totp()`), feito com a biblioteca
padrão; aceita o passo de agora e um de cada lado (`JANELA_TOTP`), e
**nunca o mesmo passo duas vezes**: a conta guarda o último aceite
(`utilizadores.totp_passo`).

- **Ligar**, em Configurações › Conta, **com a palavra-passe actual**
  (sem ela não se gera nada, e a errada conta no trinco): «Ligar o
  segundo factor» gera a chave (160 bits, `contas.segredo_novo()`) e mostra-a em grupos de
  quatro e como ligação `otpauth://`, que no telemóvel abre a app. Não
  há QR. **Só fica ligado com o primeiro código certo**
  (`contas.confirmar_segundo_factor()`); nesse momento saem **dez
  códigos de recuperação** de uso único, mostrados uma vez pelo
  `mostrar_uma_vez()` e guardados só em resumo.
- **Entrar**: com ele ligado, a palavra-passe certa no `/entrar` não
  cria a sessão — o `contas.entrar()` devolve um **pendente** (cookie
  `pendente`, cinco minutos, `MINUTOS_DO_PENDENTE`; na base só o
  resumo) e o **`/entrar/codigo`** pede o código da app ou um de
  recuperação (só o último pendente da conta vale). É rota aberta,
  **com a guarda dentro**
  (`entrar_codigo()`): o pendente, cinco tentativas
  (`TENTATIVAS_DO_PENDENTE`), o trinco da conta e do IP (cada código
  errado conta como uma entrada falhada) e a origem do POST.
- **Confiar neste aparelho** (a caixa no ecrã do código): um cookie
  `aparelho`, `HttpOnly`, `SameSite=Lax`, `Secure` quando o pedido
  vem pelo endereço público, válido `DIAS_DE_APARELHO` (30) e ligado
  à conta; com ele, a palavra-passe chega. O «sair de todos», a
  ligação de repor e o desligar **apagam os aparelhos de confiança**.
- **Nada dá a volta**: a guarda está no `contas.entrar()`, por onde
  passam também a ligação de repor (que muda a palavra-passe e leva ao
  ecrã do código, sem sessão) e o convite (que nunca serve a uma conta
  que já existe). O acesso livre local continua como está: é a consola
  do próprio computador.
- **Desligar**: na Conta, com a palavra-passe actual e um código
  válido (da app ou de recuperação), com trinco
  (`contas.desligar_com_codigo()`); ou pela consola, `--desligar-segundo-factor NOME`,
  para quando o telemóvel se perde. Leva a chave, os códigos de
  recuperação e os aparelhos.

Ligar, desligar, os códigos errados e cada código de recuperação usado
ficam nos `eventos` da plataforma. As tabelas: três colunas no
`utilizadores` (`totp_segredo`, `totp_ligado_em`, `totp_passo`) e a
tabela `segundo_factor`, com o `tipo` pendente, aparelho ou
recuperação.

**Só a consola cria um dono** (F2 da segunda ronda, 26/09/2026): o
primeiro admin criado pelo `--criar-utilizador` numa base sem dono é o
dono; do painel, de um convite ou de uma reposição nunca nasce um.

**A página do dono** (26/09/2026, a §7 da segunda ronda). A
`/plataforma` abre com **os semáforos** — Recolha, Capturas, Cópias (e a
de fora), Erros em 24 h, Temporizadores e E-mail —, cada um a levar ao
detalhe; por baixo, **«a tratar hoje»**, só quando há alguma coisa: os
pedidos por decidir, os convites por usar que acabam em dois dias
(`DIAS_ATE_O_CONVITE_ACABAR`), as empresas onde ninguém entra há
`DIAS_SEM_ENTRAR` (14) dias, a empresa que chegou ao tecto das leituras
de hoje, e os erros. Depois **as empresas** (estado, contas, última
entrada, propostas em curso, leituras do mês e de hoje contra o tecto),
as secções do sistema e, no fim, a **Recolha** com o «Verificar agora»
(pede confirmação) e o **Correio**, que se usam uma vez (G60 da 3.ª
ronda: estavam a meio, e os semáforos passaram a encher a linha).

- **Os erros das últimas 24 horas** (`/plataforma/erros`, ronda em PC):
  a lista inteira — quando, onde, o texto todo — e o «dar por vistos»;
  por cima, os **trincos fechados**, cada um com «Levantar o trinco».
  O semáforo e «a tratar hoje» contam só os que ninguém deu por vistos
  (`erros.visto_em`); um que chegue depois de a página abrir não se dá
  por visto.
- **As ligações de uso único** (o convite e o repor) mostram-se numa
  página própria, `/configuracoes/conta/ligacao`, com o botão
  «Copiar»: o gesto redirecciona para lá, e recarregar já não a mostra
  nem cria outra; o «Voltar» leva à empresa de onde se veio, também
  depois de recarregar (G61).

- **O Correio da plataforma**: a conta que envia (a mesma do resumo das
  empresas) e o endereço dos **avisos da plataforma** (`email.avisos`,
  chave da plataforma). É para ele que vai o aviso de cada pedido de
  acesso novo e o «e-mail de teste» — nunca para o resumo de uma
  empresa cliente (`config_do_correio()`).
- **A página de cada empresa** (`/plataforma/empresa/<n>`, a que cada
  linha da tabela leva): as contas, com o papel, a última entrada, as
  sessões abertas e o «repor palavra-passe»; os **convites por usar**,
  com «gerar de novo» (anula o antigo e mostra a ligação nova, uma vez)
  e «anular», e um «criar convite», com o endereço opcional (G61); os alertas ligados e se o e-mail
  sai; o perfil; as propostas em curso e as leituras. **O trabalho da
  empresa não aparece** — para isso é o «ver como».
- **Ver como a empresa, só leitura** — o suporte. O dono carrega no
  botão da página da empresa, e a sessão dele passa a ver a aplicação
  dessa empresa (`sessoes.ver_como`): a porta recusa **todos** os POST
  (só o sair passa, `PODE_A_VER_COMO`; o «sair de todos» não, desde a
  3.ª ronda — dava 500 e fechava as sessões do dono, G52) — a um `fetch`, como a triagem,
  em JSON: «Só leitura: nada se grava» —, os botões que gravam aparecem
  desligados, o «Verificar agora» não aparece, o ficheiro dela junta-se
  **só de leitura**, e uma faixa presa à barra diz «A ver a empresa X, só
  leitura» com o botão de sair. O que é **do dono** não aparece lá
  dentro (G54): a Conta mostra só os blocos da empresa, como o gestor
  os vê — sem a palavra-passe, as sessões, o aspecto e o segundo
  factor dele —, e os Alertas não mostram «Quem envia». Cada entrada e saída fica no histórico
  da empresa — o admin vê-as em Configurações › Conta, «Acessos do
  suporte» — e nos eventos da plataforma.
- **Apagar a empresa** (26/09/2026, pedido dele: «eu como dono não
  consigo apagar empresas»): um cartão de perigo no fim da página da
  empresa diz o que sai, com os números — as propostas, as tarefas, os
  contactos, as linhas do histórico, a configuração, a triagem, as
  contas e os convites por usar — e o que fica (a pasta dela em
  `copias/`, com as linhas que saem do `radar.db` num `plataforma.json`). Confirma-se **escrevendo o nome** da
  empresa (sem contar maiúsculas nem espaços a mais); um nome errado
  não apaga nada. É o mesmo `apagar_empresa()` do `--apagar-empresa`
  (`plataforma_apagar_empresa()`, `POST /plataforma/empresa/<n>/apagar`),
  e corre no próprio pedido. Desde 4/10/2026 não copia a base inteira
  (era 1,4 GB e todas as empresas, ~1 minuto com as escritas das outras à
  espera, visto na 4.ª ronda): guarda só as contas, os convites, o plano e
  as leituras da empresa (`_guardar_linhas_da_plataforma()`). Tira também a empresa da lista das suspensas e o «ver
  como» de qualquer sessão que a estivesse a ver, e deixa um evento
  da plataforma. No modo de suporte não se apaga (a porta recusa).
- **Suspender** uma empresa (e reactivar): a confirmação diz quantas
  contas deixam de entrar; nada se apaga. **As sessões abertas não se
  apagam** (G53 da 3.ª ronda, 29/09/2026: apagadas, quem estava dentro
  caía no site público sem uma palavra): a porta recusa-as a partir do
  pedido seguinte com a página «Acesso suspenso», a mesma de quem tenta
  entrar, com o contacto e um só botão, «Sair»
  (`_empresa_suspensa()`), e a verificação salta-a — sem alertas nem
  resumo (`empresas_a_trabalhar()`). A lista é `empresas_suspensas` no
  config.json da plataforma.
- **Os pedidos de acesso** recusam-se com o motivo, sem se apagar
  (`recusar_pedido()`); um recusado não se aceita. Os por decidir vêm
  num bloco em cima e os decididos por baixo (30/09/2026). No telemóvel
  a lista são cartões, com o «aceitar» à vista. O pedido aceite mostra a
  ligação do convite com o botão «Copiar», como o convite da Conta.
- **O admin da empresa** vê e anula os convites por usar da empresa dele
  em Configurações › Conta (um de outra empresa dá 404).

**O dono tem conta** (26/09/2026): sem empresa, abre na mesma a Conta —
a palavra-passe, as sessões, o aspecto — e a Ajuda (`CONTA_DO_DONO`).

**As sessões de cada conta** (G58 da 3.ª ronda, 29/09/2026) dizem o
aparelho, quando foram **usadas** pela última vez (o fim desliza trinta
dias a cada pedido, e por isso é o fim menos esses dias) e até quando
valem, e cada uma, menos a desta, tem **«terminar»**
(`POST /configuracoes/conta/sessoes/terminar`, `contas.terminar_sessao()`,
só as da própria conta). O «Sair de todos os aparelhos» e o «recusar»
de um pedido de acesso pedem confirmação.

**Um GET numa rota que só grava** (G59) dá a página da casa, «Este
endereço só grava», e não o 405 cru do servidor; o `/pedir-acesso` e o
`/configuracoes/propostas` voltam ao formulário deles (`VOLTA_DO_GET`).
Até aí as duas mandavam-no de volta para a `/plataforma`.

### 4.10 O que corre sozinho

- **Recolha** de hora a hora, das 08:00 às 20:00 (desde 23/09/2026; o
  `radar-hora.timer` dispara a todas as horas e só as de
  `horas_verificacao` contam; o relógio do painel recupera só a última
  hora falhada): pagina a pesquisa do DR, lê o
  detalhe de cada anúncio novo, traz as **consultas preliminares** da
  Vortal (as duas fontes estão no §3.7), detecta **republicações** e o
  que mudou, traz as peças das plataformas que o permitem (acingov,
  vortal, compraspt, anogov), **relê as leituras que ficaram a meio**,
  dispara alertas e o resumo diário.
- **Corpus** à segunda-feira: traz o dump do IMPIC.
- **O corpus quente** (lote 10, 29/09/2026): enquanto o painel está no
  ar, uma thread de fundo faz, com o perfil de cada empresa, as contas
  que a primeira visita ao Mercado e às Entidades pediria, e refá-las
  quando o corpus, o dia ou um perfil mudam. Ficam em memória e no
  `contratos-memoria.db`, ao lado do corpus: um reinício encontra-as
  feitas. A mesma thread constrói, uma vez, o índice de texto dos
  objectos (~5 minutos), por onde a pesquisa do Mercado passa a ir.
- **O índice da pesquisa geral** (1/10/2026): outra thread, no
  arranque do painel, constrói-o uma vez se falta (~30 a 60 s, aos
  lotes, sem prender a base); até lá, a caixa da barra procura pelo
  `LIKE`, mais devagar.
- **Cópia de segurança** diária, por `VACUUM INTO` (a quente, com a
  base em WAL), sete guardadas de cada: `radar-<data>.db` (a
  plataforma) e `empresa-<id>-<data>.db` por empresa (`VACUUM emp
  INTO`). O `contratos.db` refaz-se com `--contratos` e as peças
  voltam a descarregar-se, mas a triagem, os responsáveis, a escada e
  o histórico de cada empresa **não se recuperam de mais lado
  nenhum** — e nenhum dado vai para o git. Uma cópia que nunca se
  ensaiou não conta: `--ensaiar-copia` prova que se restaura (abre as
  duas).
- **Cópia fora do PC** (F6, 23/09/2026): a primeira verificação do dia
  manda as cópias das empresas e a das contas (`contas-<data>.db`, as
  `TABELAS_DAS_CONTAS`) para o destino `copia_fora` do rclone, cifrado,
  onde ficam `DIAS_DAS_COPIAS_FORA` dias (`mandar_para_fora()`); sem
  destino configurado (o `copias_fora.sh` faz isso), ficam só no PC, e
  a secção Cópias di-lo.
- **Exportação da triagem**: `empresas/<id>/triagem.jsonl`, por
  empresa, só local (desde 23/09/2026 não vai ao GitHub).
- **Leitura das peças pelo modelo**: três pedidos por concurso, a descer
  a cadeia de fornecedores (a Groq, o Cerebras, a NVIDIA, o OpenRouter,
  o Gemini e a reserva na Groq) até alguém responder.

---

## 5. As acções — tudo o que muda dados

Todas por **POST**, todas com CSRF, e todas **voltam à página de onde
vieram** — menos a triagem do «Por ver» com JavaScript, que grava pela
mesma rota sem sair da página (§4.3).

| Acção | Onde |
|---|---|
| Triar um anúncio (interessa / abandonar + motivo) | lista, ficha |
| Mudar de ranhura (+ os campos que ela exige) | lista, Hoje, ficha |
| Gravar campos da proposta · escrever uma nota nova · corrigir ou apagar a própria nota | ficha, ficha da proposta |
| Acrescentar · mudar · remover um documento do cofre | Configurações › Documentos da empresa (admin) |
| Criar / apagar proposta | ficha, `/proposta/nova` |
| Criar tarefa · marcar feita · desfazer · adiar · atribuir | Hoje, ficha |
| Adiar todas as atrasadas | Hoje |
| Criar / apagar contacto | ficha, ficha da entidade |
| Seguir / deixar de seguir entidade | ficha da entidade |
| Etiquetar / desetiquetar um anúncio | ficha |
| Trazer as peças · verificar peças novas | ficha |
| Criar / ligar / apagar alerta · enviar resumo | Configurações |
| Criar o alerta a partir do perfil (`/alertas/do-perfil`) | Configurações › Alertas |
| Dispensar o cartão «Pôr a empresa a trabalhar» | Hoje (admin) |
| Aceitar um pedido de acesso, com o perfil da empresa nova | `/pedidos-de-acesso` (dono) |
| Verificar agora · actualizar contratos | Configurações |
| Gravar qualquer configuração | Configurações |
| Criar / apagar utilizador · trocar palavra-passe · sair de todos | Configurações |
| Gerar a ligação de repor a palavra-passe | Configurações › Conta (admin), página da empresa na `/plataforma` (dono) |
| Pedir a ligação de repor por e-mail | `/esqueci-me`, a partir do `/entrar` (sem sessão; nunca a conta do dono) |
| Recusar um pedido de acesso, com o motivo | `/pedidos-de-acesso` (dono) |
| Criar · anular · gerar de novo um convite | página da empresa (dono); anular também em Configurações › Conta (admin) |
| Suspender · reactivar uma empresa | página da empresa (dono) |
| Entrar e sair do «ver como a empresa, só leitura» | página da empresa, faixa (dono) |
| Gravar o correio da plataforma · mandar um e-mail de teste | `/plataforma` › Correio (dono) |
| Importar o modelo · desfazer uma importação | Configurações › Importar |
| Fechar as tarefas de uma proposta fechada | ficha |

---

## 6. As regras que qualquer ecrã novo tem de respeitar

Não são gosto: cada uma é um erro que já aconteceu.

1. **Um número que um ecrã mostra tem de dar exactamente a lista que a
   ligação dele abre.** Inclui a cor de uma etiqueta. (Falhou 3×.)
2. **Não se filtra nada à entrada.** A triagem é no painel.
3. **Nenhum recorte novo entra no motor de filtros** — ele serve também
   os alertas; um recorte lá cega-os em silêncio.
4. **Sem número não se põe um travessão**: escreve-se a frase que diz o
   que falta para ele existir.
5. **Uma taxa só a partir de 5 decididos.** Abaixo disso diz-se
   «N de M — poucos».
6. **Zero ≠ «não sei».** Sem corpus diz-se «sem BASE».
7. **Nada se move sozinho.** Um prazo que passa não muda ranhura.
8. **O que está no ecrã está no endereço.** Nada se guarda no browser.
9. **Uma acção de linha volta à âncora dessa linha.**
10. **Tudo o que muda dados é POST**, e tem desfazer quando é fácil
    errar. O aviso do que se fez fica fixo em baixo, com o «desfazer» à
    mão, e nenhum selector grava ao mudar (26/09/2026).
11. **Alvos ≥ 24 px**, contraste AA sobre **todos** os fundos, e cor só
    com significado: azul = acção / em curso · verde = ganho / feito ·
    laranja = a chegar, atenção · vermelho = atrasado, perdido. **A cor
    nunca está sozinha**: ⚠ no vermelho, ◷ no laranja, ✓/✕ nos botões
    da triagem (26/09/2026). O «Abandonar» é neutro, e o laranja fica
    para a urgência; **um só botão cheio por ecrã** (30/09/2026). No
    toque, os alvos de todos os dias — a triagem, o «Mudar», as abas, a
    paginação, a caixa ✓ — têm 44 px.
12. **Nada de fora**: CSP `default-src 'self'`. Sem CDN, sem fontes
    externas, sem analytics.

---

## 7. O que ainda se pode fazer com os dados que existem

Nada aqui precisa de uma fonte nova. Ordenado por **o que os dados já
suportam**, não por prioridade.

### 7.1 Com os 210 mil anúncios

- **Sazonalidade.** Dez anos de `data_pub` × `cpv` × `preco_base`:
  *quando é que o teu mercado publica?* Um calendário anual diria
  «Setembro e Março são 40% do ano» — e isso muda quando se contrata
  equipa.
- **Preços-base de referência por CPV.** 112 mil anúncios com preço
  base: a distribuição por divisão de CPV e por entidade. *«Este
  concurso a 80 k€ está no percentil 20 do que o IPL costuma pôr.»*
- **Quem publica onde.** 87% têm plataforma: que entidades usam que
  plataforma, e o que isso implica em esforço de submissão.
- **Pesquisa no texto integral.** 185 mil anúncios com o corpo todo, e
  ninguém lá procura. Uma pesquisa por expressão sobre o texto (não só
  sobre o título) acha exigências que o CPV não classifica — «ISO
  27001», «OutSystems», «bolsa de horas».
- **Um perfil do que a empresa deixa passar.** Os que caem no interesse
  e ficam «por ver» até expirar: quantos, de quem, e de que valor. É o
  custo de oportunidade, e hoje não se mede.
- **Republicações como sinal.** 10 417 anúncios com `altera`: que
  procedimentos se republicam mais, e que entidades o fazem —
  republicar muito é sinal de peças mal feitas e de prazos que
  escorregam.

### 7.2 Com os 2 milhões de contratos

- **Um radar de renovações a sério.** O `fim_estimado` já dá a lista;
  falta a **antecipação**. «Costuma voltar ao DR 2–4 meses antes do fim»
  é uma regra que se pode **medir**: cruzar o `fim_estimado` de um
  contrato com a `data_pub` do anúncio seguinte da mesma entidade no
  mesmo CPV. Dá um alerta com meses de antecedência.
- **Quem é que nos ganha, e onde.** Por CPV e por entidade: os
  concorrentes que aparecem nos procedimentos em que também estamos.
  Hoje só se vê quem ganhou um contrato de cada vez.
- **A que desconto se fecha, por entidade e por CPV.** Já existe na
  ficha (−39,4% na SPMS); falta o **comparativo** — o desconto médio do
  mercado nesse CPV, para se saber se o nosso preço é agressivo ou
  ingénuo.
- **Fornecedores como pistas de parceria.** Quem mais recebe de uma
  entidade em CPV vizinhos do nosso é candidato a consórcio.
- **Concentração de mercado.** Por CPV: quantos fornecedores dividem 80%
  do valor. Um CPV com dois donos não vale o esforço.
- **Contratos sem anúncio.** Ajustes directos e consultas prévias no
  corpus cujo `n_anuncio` é vazio: é o mercado que **nunca** passa pelo
  DR, e por isso é invisível ao radar — mas está todo aqui.

### 7.3 Com as 78 propostas (os campos que ninguém mostra)

É a gaveta mais rica em relação ao esforço.

- **`ebitda`** (42 preenchidos) — **não aparece em ecrã nenhum.** Margem
  por concurso, por tipologia, por cliente. «Ganhámos 2,8 M€» sem margem
  não diz se foi bom negócio.
- **`lugar` e `top3`** (34) — *quão perto se perde.* Perder em 2.º por
  2% é outra coisa que perder em 7.º. Um gráfico de posições diz se o
  problema é preço ou proposta.
- **`tipologia`** (72) e **`coe`** (58) — taxa de vitória e margem por
  tipologia. O motor existe (`taxa_de_vitoria(por=…)`), **falta o
  ecrã**.
- **`cv` e `proposta_tecnica`** (49) — saíram do ecrã a 28/09/2026; os
  valores antigos ficam na base.
- **Ciclo de decisão.** `criada_em` → `fechada_em`: quanto tempo leva
  cada ranhura, e onde é que as propostas encalham.
- **Preço proposto vs. preço base vs. adjudicado** — as três pontas
  existem para 42 propostas. Dá a curva «a que desconto se ganha».

### 7.4 Com as tarefas e o histórico

- **Carga por pessoa ao longo do tempo** — o `historico` tem 539
  movimentos com `quem` e `quando`.
- **Tarefas que se adiam sempre.** Uma tarefa adiada quatro vezes é uma
  tarefa que ninguém vai fazer; hoje nada o diz.
- **Tempo de resposta.** Entre a publicação e a primeira triagem: o
  radar recolhe de hora a hora, desde as 08:00, e o que interessa é quanto tempo fica parado
  depois disso.

### 7.5 Com as peças e o modelo

- **Só 44 leituras, de 274 documentos.** O maior ganho aqui não é ecrã
  novo — é **julgar se as leituras prestam** (a skill
  `ensaio-de-leitura` existe para isso e nunca correu a sério).
- **Campos novos, sem mudar a mecânica:** a leitura já extrai objecto,
  equipa e documentos; podia extrair **critérios de adjudicação e
  pesos**, **visitas obrigatórias**, **garantias**, **penalidades** — o
  texto já está em disco e o modelo já é chamado três vezes.
- **Um «o que este concurso exige de nós»** cruzando a equipa exigida
  com os CV que a empresa tem.

### 7.6 Construído e por usar

Estas já têm código, tabela e ecrã — falta **usá-las**:

| O quê | Estado |
|---|---|
| **Alertas** | 0 ligados. O e-mail funciona — o último resumo saiu a 17/09 —, mas leva só alterações (§3.8) |
| **Entidades seguidas** | 0. O botão está na ficha |
| **Etiquetas** | 0. Tabela e ecrã existem |
| **Filtros guardados** | Tabela existe; hoje só os alertas lá vivem |
| **Lotes** | Coluna existe; nenhuma proposta a usa |
| **Propostas sem anúncio** | Rota e ficha existem; nenhuma criada |

---

## 8. O que precisaria de dados novos

Para não desenhares o que não se pode fazer:

- **Quem mais concorreu** (não só quem ganhou) — **não está no dump**
  semanal do IMPIC, que é o que o corpus tem. **Está no detalhe de cada
  contrato do Portal BASE** (medido a 30/09/2026: o pedido
  `type=detail_contratos` devolve `contestants`, a lista dos concorrentes
  com NIF, e ainda `invitees`, `closeDate`, `causesDeadlineChange`,
  `causesPriceChange`, o PDF do contrato e o link das peças). É um pedido
  por contrato, não uma coluna. **Desde 1/10/2026 recolhe-se** (o
  `contratos-concorrentes.db`, §2.2), devagar, por causa da firewall do
  BASE. Mostram-no, desde o mesmo dia, o «Quem costuma concorrer» da
  ficha do anúncio, a aba Concorrentes do Mercado (§4.6), a ficha do
  fornecedor (§4.7), a faixa do desfecho da proposta (§4.5) e o «Quem
  nos ganha» da Situação (§4.2).
- **Preços das propostas perdedoras** — não estão em lado nenhum público.
- **Relatórios preliminares e finais** — só chegam a quem concorre, pela
  plataforma, com sessão iniciada.
- **Impugnações, a vida do contrato e as não celebrações** — não
  constam do dump, mas **estão na pesquisa do Portal BASE** (medido a
  30/09/2026, `docs/diario/2026-10.md`, L0): as impugnações que as
  entidades comunicam (`search_impugnacoes`), as modificações
  contratuais — adendas e o preço novo, com o `contractId`
  (`search_incrementos`) — e os procedimentos que acabaram sem contrato,
  com o motivo (`search_cnccs`). O BASE publica também as consultas
  preliminares (`search_consultapreliminar`). Nada disto foi
  construído; é inventário para o L5 e os planos seguintes.
- **Notificação imediata** — exigiria interrogar o DR de minuto a
  minuto.
- **Peças de saphety, compraspublicas e gatewit** — ~17 mil anúncios sem
  peças, por não haver receita de descarga sem sessão iniciada.

---

## 9. Vocabulário

| Palavra | Quer dizer |
|---|---|
| **anúncio** | Uma publicação da parte L do DR. Tem `ref` («21296/2026») |
| **proposta** | O que a empresa decidiu fazer sobre um anúncio (ou sem ele) |
| **fase** | O ponto em que a proposta está. No ecrã diz-se «fase» desde 26/09/2026; no código continua a ser «ranhura» |
| **escada** | As fases, por ordem, da entrada ao desfecho. No ecrã só na Ajuda |
| **Por analisar · A preparar · Submetida · Relatório preliminar · Ganha · Perdida · Não fomos · Cancelada** | As oito fases da proposta, no feminino porque o sujeito é a proposta (26/09/2026; eram «Submetido», «Ganho»…). As chaves gravadas não mudaram |
| **Administrador / Utilizador** | Os papéis de uma conta no ecrã. No código, `admin` e `tester` |
| **perfil da empresa** | Os CPV que a empresa trabalha (e os distritos e o valor mínimo). No código, `interesse` |
| **contratos do Portal BASE** | O `contratos.db`. No código e nestes documentos, «corpus»; no ecrã, nunca (26/09/2026) |
| **entidade** | Quem publica, ou quem ganha. Identificada por chave |
| **peças** | Os documentos do procedimento (caderno de encargos, programa) |
| **empresa** | Nós. (Era «casa» até 16/09/2026) |
| **triagem** | Decidir se um anúncio interessa |

---

## Onde está o resto

| Ficheiro | O que é |
|---|---|
| `CLAUDE.md` | As regras de trabalho e a arquitectura do código |
| `ESTADO.md` | O estado de hoje, com os números |
| `docs/armadilhas.md` | O que não é óbvio, em 16 áreas — **lê a área antes de lhe mexer** |
| `docs/design.md` | O caminho do aspecto: letra, cor, botões, escala |
| `docs/historico/REDESENHO.md` | O pacote de desenho de 17/09/2026, ecrã a ecrã |
| `docs/historico/CRM.md` | Porque é que a escada é assim |
| `BACKLOG.md` | O que falta, com prioridade e com quem decide |
| `LEIA-ME.md` | O manual de quem opera |
