# Documento funcional — RadarGov

> **Última revisão: 23 de setembro de 2026**, sobre a `v1.12.0`. Este
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
> | o **porquê**, com data | `docs/referencia.md`, `docs/historico/` |
>
> Se estás a escrever aqui uma coisa que é de outro dono, ela vai para
> lá e fica aqui uma ligação. E ao contrário.

---

## 1. O que a aplicação é

Uma aplicação local em Python (Flask + SQLite) que **vigia os anúncios
de contratação pública da parte L da série II do Diário da República**,
guarda-os, e serve-os num painel.

Corre em Ubuntu, em `~/Desktop/radar`. Verifica sozinha às **09:00 e às
17:00** (temporizadores do systemd), e responde em
`http://127.0.0.1:8765` e, por um túnel da Cloudflare, em
**`https://radargov.pt`**, com login.

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

### 2.1 `radar.db` — o trabalho (1,32 GB, 24 tabelas)

**A base muda-se sozinha, a cada arranque.** Não há ficheiros de
migração nem números de versão: é o `iniciar_db()`, e cada passo é
idempotente — `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT
EXISTS`, um `ALTER TABLE ADD COLUMN` apanhado pela `OperationalError`,
ou um `UPDATE` cuja própria pergunta o torna irrepetível. Consequência
para quem desenha: **acrescentar uma coluna é barato e imediato**
(menos de 0,1 s sobre 210 mil anúncios); reescrever uma tabela não é, e
o `DROP COLUMN` do SQLite reescreve-a inteira. As regras de quando
fazer cópia e quando ensaiar estão no `CLAUDE.md`, banda 1.

**Duas colunas de números, e a diferença importa.** As tabelas que
crescem **sozinhas** — a verificação corre 2×/dia — não levam contagem
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
| `propostas` | **80** | O que a **empresa** está a fazer — a escada |
| `tarefas` | dezenas | O que falta fazer, por proposta. A verificação sincroniza-as |
| `contactos` | **26** | As pessoas do lado de lá, **por entidade** |
| `historico` | uma por movimento | Quem, o quê, quando. Cresce a **cada acção** no painel |
| `alteracoes` | uma por alteração | O que o DR mudou num anúncio já lido |
| `cpv_dict` | **9 454** | O vocabulário CPV, com descrição. Importado uma vez |
| `slots` | uma por verificação | Cada verificação que correu, e quantos trouxe (2/dia) |
| `erros` | a série, por tipo | Poda a 200 por tipo — a contagem não quer dizer nada |
| `utilizadores` | **2** | Quem entra |
| `sessoes` | as abertas agora | Caducam aos 30 dias, e o «sair de todos» esvazia-as |
| `pessoas` | 4 | Os nomes que a lista de «responsável» sugere |
| `estado` | 18 | Marcas do sistema (última verificação, migrações feitas) |
| `etiquetas` · `anuncio_etiquetas` | **0** · **0** | Etiquetas livres — construído, **por usar** |
| `filtros_guardados` | **0** | Hoje só os alertas lá vivem (§3.8) |
| `entidades_seguidas` · `seguidas_vistos` | **0** | Construído, por usar |
| `alertas_vistos` | **0** | A memória do que já foi avisado (§3.8) |
| `empresa` | **0** | Resto do importador de Excel, já corrido |
| `entradas_falhadas` | 1 | Tentativas de login falhadas |
| `pedidos_acesso` | **0** | Os pedidos do formulário do site público (§4.9), desde a `v1.12.0` |

**As colunas de `anuncios` que interessam, e quanto estão preenchidas:**

| Coluna | Cheia | Nota |
|---|---|---|
| `ref` | 100% | «21296/2026» — é a chave, e é a mesma do Portal BASE |
| `titulo`, `entidade`, `data_pub` | 100% | |
| `texto` | **88,1%** | **O anúncio inteiro em texto.** ~840 MB. Nunca foi explorado |
| `cpv` | 87,1% | |
| `plataforma` | 87,0% | vortal 80 k · acingov 68 k · anogov 15 k · saphety 13 k · … |
| `nif` | 76,1% | O NIF da entidade que publica — liga ao corpus |
| `preco_base` | 53,5% | |
| `prazo` | 38,2% | Data-limite de entrega |
| `link_pecas` | 39,2% | |
| `lotes` | 10,3% | |
| `altera` | 5,0% | Republicações ligadas ao original |
| `detalhe_lido` | **100%** | Não há fila por ler |

**Onze colunas de `anuncios` estão a 0%**: `responsavel`, `tipologia`,
`cv`, `proposta_tecnica`, `coe`, `notas`, `motivo`, `preco_proposto`,
`posicao`, `top3`, `motivo_perda`. São as colunas de CRM que saíram para
`propostas` a 15/09/2026 — **não as uses: estão mortas.**

**As colunas de `propostas`, e quantas das 78 estão preenchidas:**

| Coluna | Cheias | Nota |
|---|---|---|
| `ref`, `entidade`, `titulo`, `preco_base`, `entidade_chave` | 78 | |
| `responsavel` | 72 | Quem a tem |
| `tipologia` | 72 | **Nenhum ecrã a mostra agrupada** |
| `coe` | 58 | idem |
| `cv`, `proposta_tecnica` | 49 | Quem entrou na proposta |
| `valor_proposta`, `ebitda` | 42 | **O `ebitda` não aparece em ecrã nenhum** |
| `fechada_em` | 48 | A data da decisão — é o que o período do `/situacao` usa |
| `notas` | 38 | |
| `lugar`, `top3` | 34 | Em que posição ficámos, e quem ficou à frente |
| `motivo` | 31 | Vocabulário fechado (4+4 palavras) |
| `lote` | 0 | Existe, ainda não se usou |
| `porque_sem_ref` | 0 | Propostas sem anúncio: existe, ainda não se usou |

### 2.2 `contratos.db` — o mercado (2,66 GB, 6 tabelas)

O dump semanal do IMPIC, do dados.gov. **Refaz-se em minutos e não
viaja**: não está no git.

| Tabela | Linhas | O que é |
|---|---|---|
| `contratos` | **2 004 511** | Cada contrato celebrado. Desde 2015 |
| `contrato_adjudicatario` | 2 036 810 | Quem ganhou (um contrato pode ter vários) |
| `contrato_cpv` | 2 037 647 | Os CPV de cada contrato |
| `entidades` | **180 090** | Identidade: chave, NIF, nome, nº de grafias, quanto compra, quanto ganha |
| `entidade_nomes` | 256 340 | Todas as grafias por que uma entidade já apareceu |

Colunas de `contratos` que interessam: `n_anuncio` (**é o `ref` do
radar** — é por aqui que se fecha o ciclo), `adjudicante_chave`,
`objecto`, `cpv`, `preco_base`, `preco_contratual`, `data_celebracao`,
`prazo_execucao`, `fim_estimado`, `tipo_procedimento`, `local_execucao`,
`fundamentacao`, `n_adj`.

**`fim_estimado`** = celebração + prazo declarado. É **estimado**:
prorrogações e cessações antecipadas não constam do dump. Trata-se como
sinal para olhar, nunca como facto.

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
Por ver → Por analisar → A preparar proposta → Submetido
        → Relatório preliminar → Ganho | Perdido | Não fomos | Cancelado
                                                    (+ Expirou sem ver)
```

- **As duas pontas** (`Por ver`, `Expirou sem ver`) são **anúncios**.
- **As oito do meio** são **propostas** — o que a empresa decidiu fazer.
- **Qualquer salto é permitido**, e voltar atrás é reabrir.
- **Entrar numa ranhura exige o que a faz ser verdade**:

| Ranhura | Exige |
|---|---|
| Submetido | valor proposto |
| Relatório preliminar | valor proposto + lugar |
| Ganho | valor proposto |
| Perdido | valor proposto + motivo |
| Não fomos | motivo |

Os motivos são **vocabulário fechado** (é o que os faz dar contas):
perda — *Preço · CV's · Proposta técnica · Certificações*; não fomos —
*Preço base baixo · Falta de certificações · Falta de CV's · Não faz
parte da oferta*.

### 3.2 Anúncio ≠ proposta

Tabelas separadas, por duas razões que o estado do anúncio não consegue
ser:

- **Lotes** — um concurso de três lotes pode acabar com o L1 ganho e o
  L2 perdido. Uma linha não cabe dois resultados.
- **Propostas sem anúncio** — consulta prévia, ajuste directo, convite.
  `ref` a NULL é legítimo; o `porque_sem_ref` diz porquê.

### 3.3 O interesse

Uma lista de CPV que a empresa trabalha (e outra de exclusões), em
Configurações. Recorta **a lista, o Hoje, o Mercado e a ficha da
entidade**. Levanta-se com `?interesse=nao`.

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
- **Escritas à mão** — nunca se tocam.

**Nada se move sozinho.** Um prazo que passa não muda ranhura nenhuma:
aparece no balde «prazo passou sem decisão» e quem escolhe é a pessoa.

### 3.6 As peças, e o que o modelo lê

Os documentos do procedimento — Caderno de Encargos, Programa de
Concurso, anexos. Vêm em duas metades, e convém não as confundir.

**Trazer.** Só das plataformas que o permitem sem sessão iniciada:
`acingov`, `vortal`, `compraspt`, `anogov` (`PLATAFORMAS_COM_PECAS`).
Dispara ao pôr um concurso em «Por analisar» — é esse o sinal de que se
vai trabalhar nele. **Os ficheiros ficam em disco (`pecas/`), não
na base**, para o `radar.db` não crescer com PDF.

**Ler.** Um modelo lê o CE e o PC e preenche **três campos**:
`objecto`, `equipa`, `documentos_proposta` (`CAMPOS_LIDOS_PELO_MODELO`).
São **três pedidos, um por campo** — não um pedido grande —, porque o
tecto da conta é por minuto e manda no tamanho do recorte
(`TECTO_RECORTE`). Cada pedido desce a cadeia `FORNECEDORES` (Groq →
NVIDIA → OpenRouter) até alguém responder.

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
verificação corre 2×/dia e o resumo sai 1×/dia; se fossem o mesmo
passo, saíam dois e-mails com metade das coisas cada um.

1. **Reconhecer** (`registar_alertas()`, `registar_seguidas()`, a cada
   verificação): anota na `alertas_vistos` que anúncios caem em que
   alerta. A tabela é a memória — **um anúncio nunca é avisado duas
   vezes**, nem que a verificação corra dez.
2. **Enviar** (`enviar_resumo()`, a partir da `hora_resumo`): junta o
   que está reconhecido e ainda não saiu, manda um e-mail e só então
   marca como enviado.

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
- **Sem e-mail configurado, o ficheiro é a entrega.** O resumo escreve-se
  sempre no `AVISOS.txt`, e nesse caso dá-se por avisado — senão o painel
  dizia «153 por avisar» para sempre e reescrevia o mesmo resumo a cada
  volta. Uma falha a sério (senha recusada, rede em baixo) **não** marca,
  para voltar a tentar.
- **Uma entidade que se começa a seguir entra com o acervo marcado como
  já visto**, senão o primeiro resumo trazia dez anos de uma vez.

**A maquinaria está construída e por estrear**: o canal funciona, mas
nunca se criou um alerta, e por isso o resumo leva só alterações. As
contagens estão no §7.6, e o gesto que falta — ligar um alerta, seguir
uma entidade, ver o que chega — está no `BACKLOG.md`.

---

## 4. O que já está feito, ecrã a ecrã

**84 rotas.** A navegação tem **duas intenções mais o logótipo**:

- **RadarGov** (o logótipo) = **Hoje**, `/` — a marca é a abertura
- **Concursos** → `/concursos` · vista **Calendário** `/calendario`
- **Mercado** → `/contratos` · vista **Entidades** `/entidades`
- **Configurações** → `/configuracoes` (9 secções)

### 4.1 Hoje — `/`

Responde a quatro perguntas em três segundos: *o que tenho de fazer
hoje · o que fecha esta semana · o que mudou · o que está parado.*

1. **Título** = a data por extenso («Sexta, 18 de setembro»).
2. **Quatro indicadores** (o `Stat` do sistema de desenho, desde
   22/09/2026) — em jogo (com a saída para o Ponto de situação) · taxa
   de vitória · por decidir · para fazer, com as atrasadas na nota.
   **Cada um abre exactamente a lista que o produz.**
3. **Fita da semana** — sete células, seg→dom. Cada uma: nº de tarefas,
   nº de feitas, entregas (laranja); a de hoje diz também quantas
   atrasadas arrasta (vermelho). **Clicar num dia muda o balde do
   meio.** Setas para a semana anterior e seguinte.
4. **Para fazer** (coluna esquerda), em cinco baldes:
   - **Prazo passou sem decisão** — propostas abertas cujo prazo do DR
     passou, com o selector de ranhura ao lado. Não dobra.
   - **Atrasadas** — com «adiar todas p/ hoje» (pergunta antes; não há
     desfazer). Não dobra.
   - **O dia escolhido** na fita (por omissão, hoje). Não dobra.
   - **Resto da semana** · **Mais para a frente** — dobram.

   Os que não dobram mostram as primeiras linhas (`CABEM_NO_BALDE`;
   `CABEM_SEM_DECISAO` no primeiro) e o resto num **«mais N»** que se
   abre ali; o número do cabeçalho conta todas (22/09/2026).

   **A linha de tarefa**: caixa de ✓ · texto (a origem automática vai na
   dica do texto, não numa etiqueta) ·
   dia · **de que concurso é** (ref · entidade) · avatar de quem
   (tracejado = sem dono) · entrega, ou «fecha hoje».

   **Risca-se no sítio**: a linha fica, riscada, com «desfazer» — e a
   página volta à linha (`#t<id>`), não ao topo. **Só as feitas de
   hoje** ficam; as de outros dias saem do ecrã (22/09/2026).

   No cabeçalho: **pílulas de pessoa** (Todos · cada dono · sem dono) e
   **esconder as feitas**. Tudo vive no endereço (`?dia=`, `?quem=`,
   `?feitas=`); nada se guarda no browser.
5. **Coluna direita**, três caixas:
   - **O que mudou** — três números (anúncios novos · no interesse ·
     peças novas) e um feed: os novos que caem no interesse, peças
     novas, **prazos alterados por republicação**, e as propostas que o
     Portal BASE **já diz adjudicadas** e nós não fechámos.
   - **Prazos a chegar · 7 dias**
   - **Paradas há mais tempo** — dias desde o último movimento (laranja
     acima de 30).

### 4.2 Ponto de situação — `/situacao`

Como vai o negócio. **Três abas** (Negócio · Triagem · Por área CPV) e
um **período** (este mês · este trimestre · 12 meses · tudo), com
comparação com o período anterior **do mesmo tamanho**.

- **Quatro números**: em jogo · taxa de vitória · ganho (€ e nº) ·
  desconto médio nos ganhos.
- **Negócio**: aviso das propostas por fechar · em jogo por ranhura ·
  porque se perde · porque não se vai · onde se ganha por área CPV · há
  mais tempo sem se mexerem · propostas por ranhura.
- **Triagem**: o funil — entrados · por ver · triados · interessa.
- **Por área CPV**: taxa de vitória por divisão.

O período conta pela **`fechada_em`**. Uma taxa só se diz a partir de
**5 decididos**; abaixo disso diz-se por extenso quantos faltam.

### 4.3 Concursos — `/concursos` (a lista única)

**As dez ranhuras da escada nas abas.** As duas pontas mostram
**anúncios**; as oito do meio mostram **propostas**.

Filtros (painel recolhível): objecto (com E/OU e exclusões) · CPV (com
árvore de 9 454 códigos e exclusões) · entidade que publica · NIF ·
plataforma · prazo · datas · preço mínimo. O filtro compõe-se com o
interesse.

Por linha: triar («interessa» / «abandonar», que pergunta o motivo),
**mudar de ranhura no selector**, abrir a ficha. Exporta para CSV.

**Vista Calendário** — `/calendario`: os prazos por dia, seis semanas,
para qualquer ranhura.

### 4.4 Ficha do anúncio — `/anuncio/<ref>`

Em **duas colunas** desde 23/09/2026 (o `EcraFicha` do sistema de
desenho): à esquerda o anúncio (identidade, essencial, lotes, peças,
desfecho, homólogos e mercado), à direita o trabalho (a nossa proposta,
contactos, histórico, responsável); numa só abaixo de 1100px. O
cabeçalho fino e o índice ficam presos ao rolar. Tem:

- Os factos do DR (entidade, CPV, preço base, prazo, plataforma, lotes)
- O **texto** do anúncio
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

### 4.5 Ficha da proposta — `/proposta/<id>`

Para as propostas **sem anúncio** (consulta prévia, ajuste directo,
convite) e para qualquer proposta. Tem o bloco inteiro, os contactos, a
cronologia e o apagar. `/proposta/nova` cria uma.

### 4.6 Mercado — `/contratos`

O corpus do Portal BASE. Lista com filtros (objecto, CPV, entidade que
comprou, quem ganhou, procedimento, datas, preço), CSV, e **modo «por
fim estimado»** — o que está a acabar, que é o que volta a concurso.

`/contratos/resumo`: seis agregações — quem compra, quem ganha, por CPV,
por procedimento, descontos, evolução.

### 4.7 Entidades — `/entidades` e `/entidade/<chave>`

**Cinco abas**: com quem trabalhamos · seguidas · clientes que mais
compram · concorrentes que mais ganham · **contratos a acabar · 90
dias**.

Tabela: entidade (nome + NIF) · papel (cliente / concorrente / ambos) ·
compra · ganha · **fita do «connosco»** (um quadrado por proposta, com a
cor do desfecho) · taxa connosco · a acabar · abrir. **Marcando duas
linhas, comparam-se lado a lado.**

**A ficha** abre com **seis factos** — compra a 24 meses · quanto disso
cai no nosso CPV · a que desconto fecha · quantas propostas lhe fizemos
· a taxa com ela · o que lhe acaba em 90 dias — e tem duas colunas: o
**nosso lado** à esquerda (anúncios dela, propostas, taxa, contactos,
seguir) e o **Portal BASE** à direita (o que compra, a quem, como, ao
longo do tempo). **Sem corpus diz «sem BASE», não zero.**

### 4.8 Configurações — `/configuracoes/…`

Nove secções, por esta ordem. **As cinco últimas só ao admin.**

| Secção | O que faz |
|---|---|
| **conta** | palavra-passe, sessões, a nossa empresa (nome + NIF), utilizadores |
| **interesse** | os CPV que a empresa trabalha, e as exclusões |
| **alertas** | filtros de alerta, entidades seguidas, o resumo por e-mail |
| **importar** | o registo da empresa, pelo modelo Excel |
| indicadores | as capturas, a recolha, o corpus — a saúde da máquina |
| capturas | os dois pedidos cURL ao DR |
| recolha | horas, janelas, a Vortal |
| leitura | fornecedor, modelo e chaves do modelo que lê as peças |
| cópias | a cópia diária e a triagem no git |

### 4.9 A porta

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
   é um ficheiro estático sem dados. Com `?dia=` ou outro parâmetro é a
   mesma raiz, e é o site; todos os outros caminhos vão ao login.

**O que fica aberto sem sessão** não é só o `/entrar`: também o
`/saude`, o `/favicon.svg`, o **`/pedir-acesso`** (o formulário do site,
com a guarda dentro da própria rota: origem, campo-armadilha, campos
validados e cortados, e tectos de `PEDIDOS_POR_IP_POR_HORA` e
`PEDIDOS_POR_DIA`), e por prefixo as fontes `/tipo/<nome>` (lista branca `TIPOS`)
e a folha `/estilo/<etiqueta>.css`. Sem estes dois últimos o próprio
ecrã de entrar aparecia sem letra e sem cor. Nenhum tem dados lá dentro.

**Dois papéis** (`utilizadores.papel`). O **admin** vê tudo e cria
contas; o **tester** leva 403 nas dez rotas do sistema
(`ROTAS_SO_ADMIN`: Indicadores, Capturas, Recolha, Leitura das peças,
Cópias, a gestão de utilizadores, o «Verificar agora», quem envia o
e-mail e os pedidos de acesso do site). `sou_admin()` é a pergunta — e no acesso livre **sem conta
nenhuma** a resposta é sim, senão não se chegava a Conta para criar a
primeira.

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
de `radargov.pt` eram locais. O `pedido_e_local()` conta também os
cabeçalhos de proxy e o `Host` público — qualquer um deles chega para o
pedido deixar de ser local.

**Cinco falhas em quinze minutos fecham o trinco**, por e-mail **ou** por
IP (`FALHAS_ATE_TRINCO`, `MINUTOS_DE_TRINCO`). Não há recuperação por
e-mail: a senha troca-se por consola, com `--palavra-passe NOME`.

### 4.10 O que corre sozinho

- **Recolha** 2×/dia (09:00, 17:00): pagina a pesquisa do DR, lê o
  detalhe de cada anúncio novo, traz as **consultas preliminares** da
  Vortal (as duas fontes estão no §3.7), detecta **republicações** e o
  que mudou, traz as peças das plataformas que o permitem (acingov,
  vortal, compraspt, anogov), **relê as leituras que ficaram a meio**,
  dispara alertas e o resumo diário.
- **Corpus** à segunda-feira: traz o dump do IMPIC.
- **Cópia de segurança** diária do `radar.db`, por `VACUUM INTO` (a
  quente, com a base em WAL), sete guardadas. **Só o `radar.db`**: o
  `contratos.db` refaz-se com `--contratos` e as peças voltam a
  descarregar-se, mas a triagem, os responsáveis, a escada e o
  histórico **não se recuperam de mais lado nenhum** — não estão no
  git, por serem uma base. Uma cópia que nunca se ensaiou não conta:
  `--ensaiar-copia` prova que se restaura.
- **Triagem no git**: `triagem.jsonl`, commit + push automáticos.
- **Leitura das peças pelo modelo**: três pedidos por concurso, a descer
  a cadeia Groq → NVIDIA → OpenRouter até alguém responder.

---

## 5. As acções — tudo o que muda dados

Todas por **POST**, todas com CSRF, e todas **voltam à página de onde
vieram**.

| Acção | Onde |
|---|---|
| Triar um anúncio (interessa / abandonar + motivo) | lista, ficha |
| Mudar de ranhura (+ os campos que ela exige) | lista, Hoje, ficha |
| Gravar campos da proposta | ficha, ficha da proposta |
| Criar / apagar proposta | ficha, `/proposta/nova` |
| Criar tarefa · marcar feita · desfazer · adiar · atribuir | Hoje, ficha |
| Adiar todas as atrasadas | Hoje |
| Criar / apagar contacto | ficha, ficha da entidade |
| Seguir / deixar de seguir entidade | ficha da entidade |
| Etiquetar / desetiquetar um anúncio | ficha |
| Trazer as peças · verificar peças novas | ficha |
| Criar / ligar / apagar alerta · enviar resumo | Configurações |
| Verificar agora · actualizar contratos | Configurações |
| Gravar qualquer configuração | Configurações |
| Criar / apagar utilizador · trocar palavra-passe · sair de todos | Configurações |

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
    errar.
11. **Alvos ≥ 24 px**, contraste AA sobre **todos** os fundos, e cor só
    com significado: azul = acção / em curso · verde = ganho / feito ·
    laranja = a chegar, atenção · vermelho = atrasado, perdido.
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
- **`cv` e `proposta_tecnica`** (49) — quem entra nas propostas que se
  ganham. Carga por pessoa, e que perfis fazem falta.
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
  radar recolhe às 09:00, e o que interessa é quanto tempo fica parado
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

- **Quem mais concorreu** (não só quem ganhou) — não está em lado nenhum
  público.
- **Preços das propostas perdedoras** — idem.
- **Relatórios preliminares e finais** — só chegam a quem concorre, pela
  plataforma, com sessão iniciada.
- **Impugnações e recursos** — não constam do dump.
- **Execução do contrato** (prorrogações, adendas, rescisões) — o BASE
  publica a celebração, não a vida do contrato.
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
| **ranhura** | Um degrau da escada |
| **escada** | As dez ranhuras, da entrada ao desfecho |
| **interesse** | Os CPV que a empresa trabalha |
| **corpus** | O `contratos.db` — os contratos celebrados do Portal BASE |
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
