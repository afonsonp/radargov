# Backlog — melhorias saídas da análise competitiva de 30/08/2026

Origem: `docs/historico/CONCORRENTES.md` (passagens de 29 e 30/08/2026) e a prova em
`concorrentes/`. Os cinco itens identificados na Tendios a 29/08 estão cá
dentro, reavaliados à luz da Armilar, GovGo e SpotGov.

**Critério de prioridade** (aplicado item a item, com a conta à vista):
- **P0** — fecha uma desvantagem competitiva já medida, esforço ≤ 8h
- **P1** — valor 4–5, esforço ≤ 3 dias, confiança alta
- **P2** — valor alto mas esforço grande, ou confiança média
- **P3** — cosmético, ou premissa por confirmar

Esforço: 1 ≈ ≤2h · 2 ≈ meio dia a 1 dia · 3 ≈ 2–3 dias · 4 ≈ 1 semana ·
5 ≈ mais que isso.

## Registo de pendências — fechado a 31/08/2026

Tudo o que está em aberto, com **quem** decide ou age e **o que o
dispara**. Nada aqui está a meio: ou espera uma palavra do Afonso, ou
espera um gatilho declarado. O que não está nesta tabela está decidido
ou feito.

| # | O que falta | Estado | Espera por |
|---|---|---|---|
| — | ~~Reler as peças pelo modelo quando chega um CE revisto~~ | **Feito a 14/09/2026**: a vigilância das peças voltou, por razão (data de esclarecimentos passada, prorrogação ou preço base novo) e por botão na ficha, avisa no resumo, e **com peça nova relê logo pelo modelo** (em linha na verificação, pela fila no botão) | — |
| UX | Auditoria pelas «leis de UX» (`docs/historico/UX-Auditoria.md`, 02/09/2026) | **P0 e os cinco P1 feitos a 02/09/2026** (contraste da coluna, alvos a 24 px, «desfazer» depois de triar, prazo neutro pós-submissão, fontes sem bloquear, quadro sem `reload()`). Falta repetir a medição do browser sobre o resultado | **Afonso** nos P2/P3 que mudam o primeiro ecrã: filtros recolhidos por omissão, essencial da ficha encurtado, teclado na lista; motivos em 2 gestos, KPI e funil ligados, pílula do calendário não precisam de decisão e ficam para a próxima sessão |
| E2 | ~~O primeiro envio do resumo diário~~ | **Feito a 31/08/2026, à ordem dele**: «Resumo enviado para afonso.pinto95@hotmail.com», com 1 anúncio do alerta CPV IT (INFARMED, 400 930 €). Daqui em diante sai sozinho, uma vez por dia com novidade | — |
| E4 | ~~Registar quando o token expira~~ | **Feito a 31/08/2026**: cada expiração grava o momento e a idade da captura na série de erros (C3) e na marca dos indicadores | — |
| — | ~~Andamentos do esqueleto~~ | **Feitos a 31/08/2026** (1: navegação e âmbitos · 2: vocabulário e atalhos · 3: renovações fundidas em modo · 4: Fluxo B verificado e, com o E2, disparado — ver `docs/diario/2026-08.md`) | — |
| B15 | ~~Exportar a triagem~~ | **Feito a 31/08/2026**, e a sub-decisão do push também: **automático** («grava logo lá consoante o uso») — `empurrar_triagem()` faz commit+push só do `triagem.jsonl` em cada verificação em que mude; push falhado retoma na volta seguinte. **Isto fecha o R2 por inteiro** | — |
| B14 | ~~Vortal como segunda fonte~~ | **Em produção desde 31/08/2026, com o âmbito dele**: só «GovPT - Consulta Preliminar», país PT, fonte='vortal' — zero duplicação com o DR. Primeira recolha: **17 consultas** (ver a secção B14). A acingov fica de fora: a listagem dela não distingue tipos sem abrir detalhes | Alargar a outros tipos não-DR ou à acingov: palavra dele, com medição antes |
| C3 | ~~Histórico de erros~~ | **Feito a 31/08/2026**: tabela `erros` com poda a 200 por tipo; as marcas continuam a servir o ecrã | — |
| — | ~~Fallback morto na detecção de plataforma~~ | **Medido e corrigido a 31/08/2026**: +28 anúncios com plataforma (todos acingov, dita por extenso no corpo); 56 → 28 sem plataforma | — |
| 11.7-B | ~~Procura directa de entidade~~ | **Feito a 31/08/2026, a pedido dele**: caixa «Ficha de entidade» em Mercado + `/entidade/procurar` — NIF vai directo, nome resolve por `entidade_nomes` (única → ficha; várias → escolha; nenhuma → di-lo) | — |
| — | ~~Visualizador de PDF na ficha~~ | **Feito a 31/08/2026, a pedido dele** (sai do «Não fazer»): os PDF das peças abrem em `/peca/<ref>/<nome>`, dentro da aplicação, com a pesquisa do próprio visualizador (Ctrl+F) — o caminho barato que estava anotado | — |
| CRM | ~~O «Em curso» não é um CRM: é a mesma consulta dos interessados~~ | **Plano escrito a 15/09/2026** e **reescrito no mesmo dia com as decisões dele**: `docs/historico/CRM.md`. Seis etapas. O desenho é dele — **uma escada só** (dez ranhuras: a entrada, as oito palavras da casa, o cemitério dos expirados), com lista, quadro e calendário como três vistas dessa escada | **Feito a 15/09/2026, as seis etapas**: as tabelas, a escada nas abas, a triagem a criar propostas, o quadro (que saiu no mesmo dia, por decisão dele: a ranhura muda-se no selector da linha), o calendário para qualquer ranhura, a navegação em Concursos · Calendário · Mercado, as tarefas que seguem as datas do DR, o ciclo fechado com o Portal BASE (por chave: o `n_anuncio` é o `ref`), os indicadores comerciais e os contactos. Falta o NIF da casa, em Configurações › Conta, para o cruzamento adiantar se a adjudicação foi nossa |
| B15-b | ~~Os campos do CRM não saem no `triagem.jsonl`~~ | **Fechado a 15/09/2026, sem trabalho próprio**: as colunas em falta são exactamente as que a etapa 1 do CRM apaga — exportá-las era escrever para deitar fora a seguir. A exportação faz-se uma vez, já sobre `propostas` e `tarefas`, dentro dessa etapa | — |

**O registo está limpo: não há pendências abertas.** O que se abrir a
seguir entra aqui com quem decide e o que dispara, como sempre.

**Dependências, e o estado de cada uma:**

- **E2 → Fluxo B:** fechada a 31/08/2026 — o primeiro resumo saiu por
  e-mail à ordem do Afonso. O cenário «sem e-mail» (11.3-B) fica
  escrito só como registo histórico.
- **E3 → ecrãs fora do PC:** fechada, e a 8/09/2026 virada ao
  contrário: o painel está em `radargov.pt`, os links do resumo já
  apontam para lá, e o CSS passou a ter um ponto de corte a 900 px
  para o telemóvel (barra em cima, grelhas a uma coluna).
- **R1 (token) → recolha:** viva, mitigada pelo aviso no painel. O E4
  (feito a 31/08) não a reduz — mede-a: a série na tabela `erros` é que
  há-de dizer a frequência real.
- **R11 (volume) → `/contratos/resumo`:** viva. É a razão de a entrada
  de Mercado ser «a pergunta primeiro», e o esqueleto proíbe qualquer
  painel que dispare o resumo sem filtro.
- **R2 (perda do PC):** dada como fechada a 31/08/2026 — o código pelo
  remoto do GitHub, e a triagem pelo B15 com o push automático em cada
  verificação. **Reaberta a 15/09/2026, em parte** (B15-b, em cima): as
  colunas de CRM que entraram no `anuncios` depois dessa data
  (14/09/2026: `tipologia`, `cv`, `proposta_tecnica`, `notas`, `coe`; e
  antes delas `preco_proposto`, `posicao`, `top3`, `motivo_perda`,
  `motivo`) nunca foram acrescentadas ao `_TABELAS_TRIAGEM`, e a tabela
  `casa` também não lá está. **Fechada no mesmo dia, com o CRM**: essas
  colunas deixaram de existir e o que as substituiu — `propostas`,
  `tarefas` e `contactos` — vai inteiro no `triagem.jsonl`. É a parte
  mais irrecuperável de todas, porque o DR não devolve o preço que se
  propôs. Fora isso, o que fica em risco no disco é só o que se refaz
  (base, corpus, peças).
- **6.2-B (dois motores de filtro):** decidido mantê-los. Não é
  pendência, é decisão — reavaliável no andamento 3.

## P0

- ~~**A guarda de «uma verificação de cada vez» não atravessa
  processos.**~~ **Feito a 14/09/2026**: `tomar_trinco()` /
  `largar_trinco()` na tabela `estado`, com pid, hora e prazo de
  `HORAS_DE_TRINCO`; o `--uma-vez` e o `comecar_verificacao()` passam
  os dois por lá, e o painel diz «noutro processo» enquanto o
  temporizador corre. O que se segue é a descrição de quando estava
  aberto. Aberto a 8/09/2026. `comecar_verificacao()` protege-se
  com `_VERIFICACAO`, um dicionário na memória com um trinco de
  threads: vale dentro de **um** processo. O temporizador do systemd
  arranca um processo à parte, que não vê o relógio de dentro do
  painel — e a 8/09, às 17:00, correram os dois (o timer às 17:00:37,
  o relógio às 17:00). Duas verificações inteiras sobre a mesma base
  ao mesmo tempo. O sintoma que apareceu foi pequeno — o rascunho da
  exportação partilhado, já corrigido com o pid no nome — mas a causa
  não é: por baixo estão duas recolhas, duas leituras de detalhe e
  dois `empurrar_triagem()` a competir. Precisa de um trinco que os
  dois processos vejam (ficheiro com `O_EXCL`, ou uma linha na tabela
  `estado` com o pid e a hora, com prazo para o caso de o processo
  morrer a meio). **Esforço 1.** Enquanto não for feito, a tabela
  `slots` continua a parecer certa, como já acontecia quando faltavam
  as tarefas.

## P1

Vazio — B03, B04 e B05 feitos a 30/08/2026; ver «Feito», no fim.

## P2

- ~~**«Em curso» em modo lista**~~ (13/09/2026, do documento «Mudanças
  na plataforma RADAR»). **Feito a 14/09/2026** com as colunas que ele
  mandou: título, cliente, preço, esclarecimentos, entrega, tipologia
  (consulting/turnkey), estado da proposta (a fase), CV (sim/não),
  proposta técnica (sim/não), notas, plataforma, CoE, responsável.
  Em `/lista`, terceira vista do Em curso; as cinco colunas da casa são
  novas na base e gravam-se linha a linha.

Vazio — B06 a B10 feitos a 30/08/2026; ver «Feito», no fim.

### Da auditoria ponytail (14/09/2026), por decidir pelo Afonso

O relatório inteiro está no diário desse dia. O que se aplicou está lá;
estes quatro ficaram investigados e por decidir:

- **Fundir `_pecas_acingov/_vortal/_jsf` em `pecas_disponiveis()`**
  (-50 a -55 linhas, três cópias da lógica de plataforma numa só).
  Aplicável, mas com quatro perdas assumidas: na Vortal e no JSF um
  `None` deixa de distinguir «acima do tecto» de «rede»; um documento
  da Vortal sem rótulo no JSON passa a chamar-se «documento»; o texto
  dos avisos muda; no JSF paga-se um pedido extra por peça (o nome vem
  de um HEAD à parte). Plano concreto no diário.
- **`pypdf` e `cryptography` → `pymupdf`** (-2 dependências). Só depois
  de medir sobre as peças reais em `documentos/`: no ensaio sintético o
  `pymupdf` parte as linhas das tabelas em uma célula por linha, que é
  exactamente a tabela de perfis do campo «equipa». Guião de medida no
  diário; se for favorável, reextrair o acervo por marca e refazer as
  análises com `--ler-pecas tudo`.
- **Não aplicar, e porquê:** as duas filas de fundo por
  `ThreadPoolExecutor(1)`. O executor não é daemon (o `--uma-vez` do
  temporizador ficaria à espera de descargas e leituras no `atexit`),
  não deduplica (a fila da análise deduplica por `_A_ANALISAR`) e um
  arranque falhado fica `BrokenThreadPool` para sempre. As filas não
  são gémeas; o que se repete são três linhas de arranque. Fica.

## P3

Vazio — B11, B12 e B13 feitos a 30/08/2026; ver «Feito», no fim.
**O backlog da análise competitiva está fechado de P0 a P3.**

## Feito

- **B03 — vista "Renovações"** (30/08/2026). Separador novo `/renovacoes`:
  contratos do corpus com fim estimado (coluna `fim_estimado` =
  celebração + prazo em dias, com migração idempotente e índice) numa
  janela de 3/6/12/24 meses, filtráveis como os contratos (a vista
  `renovacoes` partilha os campos, menos `de`/`ate` — a página já tem um
  eixo do tempo). A pergunta vem primeiro, como em `/contratos`. A
  página diz que o fim é estimado e que prorrogações não constam do
  dump. Medido: 81 827 contratos terminam nos próximos 6 meses (bate
  com a conta da análise); limpeza 6 meses ~350 ms.
- **B04 — desconto sobre o preço base** (30/08/2026). Validado como o
  backlog exigia: a média ingénua por linha dá **-18,9%** (cada lote
  compara com a base do procedimento inteiro); agregado por `n_anuncio`
  com base constante dá descontos plausíveis. Ficam de fora os grupos
  com a base a variar entre lotes (5 388 — aí a base é por lote,
  semântica ambígua) e a soma acima da base (4 275, ruído): sobra o
  conjunto limpo de 97 130 procedimentos. 7º gráfico no resumo dos
  contratos (mediana global 8,7%; CPV 72: 3,4%; limpeza: 10,5%) com
  índice parcial (1,0 s → 0,07 s), e desconto mediano da entidade+CPV
  na ficha do anúncio (mínimo 5 procedimentos).
- **B05 — avisos de alterações** (30/08/2026). `reler_marcados()` relê
  por verificação até 25 anúncios interessa/quadro com prazo aberto;
  `_guardar_detalhe()` compara prazo e preço base com o guardado
  (`diferencas_do_detalhe()`: só valor→valor diferente — campo que
  desaparece é o parser a tropeçar, não se grita lobo). As mudanças vão
  para a fila `alteracoes` (reconhecer/enviar separados, como os
  alertas) e para o histórico da ficha ("DR · alterou · prazo de
  propostas: 05/09/2026 → 19/09/2026"); o resumo diário ganha a secção
  "Alterados desde a última leitura". Ensaiado sobre cópia da base com
  uma prorrogação simulada de 14 dias; reler o mesmo texto não avisa
  duas vezes. Anulações ficaram de fora (o formato de republicação do
  DR está por confirmar — era a parte de confiança média do item).

- **B01 — exclusões nos filtros** (30/08/2026). `q_excl` e `cpv_excl`
  em `condicoes()` e `condicoes_contratos()`, nos quatro formulários
  (anúncios, contratos, ficha da entidade, novo filtro dos alertas) e
  em `CAMPOS_FILTRO`/`CAMPOS_POR_VISTA` — filtros guardados, alertas e
  CSV herdaram de graça, como previsto. O `cpv_excl` é caixa de texto
  (códigos ou palavras, separados por `|`): o modo excluir na árvore
  ficou de fora — exigia tri-estado no JS partilhado e destrancava os
  descendentes (`arvoreTrancarFilhos`), que é trabalho a sério; se o
  campo à mão incomodar, reabre-se como item próprio. **Reaberto e
  feito a 01/09/2026, a pedido do Afonso**: a árvore escreve nos dois
  campos, os descendentes deixaram de estar trancados e desmarcar um
  código dentro de uma divisão marcada tira só esse ramo (`ARV_EXC`,
  `arvorePintar()`, `arvoreDesexcluir()`) — a razão dele é que marcar
  os sub-códigos um a um perde os anúncios que trazem apenas o código
  da divisão. Ver o `docs/diario/2026-09.md`, entrada de 01/09/2026. Medido: `q=
  manutenção` 3 781 → 3 616 sem `elevador|avac`; `cpv=72` 235 → 225 sem
  `724`; nos contratos, limpeza (909100) 12 156 → 11 892 sem "escolas".
- **B02 — procedimentos homólogos na ficha** (30/08/2026).
  `homologos_do_anuncio()` procura contratos da mesma `chave` com
  termos do título (`termos_do_titulo()`, sem o vocabulário burocrático)
  no `objecto_norm`; com 2+ termos exigem-se 2 em comum, senão um só
  "manutenção" arrastava a manutenção toda da entidade. Caixa
  "Procedimentos homólogos" antes do histórico por CPV, só quando há
  resultados, com os termos usados à vista. Confirmado o caso Armilar:
  "Fornecimento de refeições e Serviço de bar" mostra as edições de
  2025/2023/2020 (64 975 € / 65 840 € / 70 730 €), em ~20-60 ms.

- **B06 — taxa de acerto por alerta** (30/08/2026). Cada alerta em
  `/alertas` diz agora em que estados acabou o que marcou (interessa ·
  descartados · por ver) e o acerto sobre os triados — o sinal de
  alerta mal afinado.
- **B07 — E/OU entre palavras e CPV** (30/08/2026). Selector `op` nos
  formulários ("mais restrito / mais amplo"); `condicoes()` e
  `condicoes_contratos()` montam os dois lados como fragmentos para os
  juntar por OR sem baralhar a ordem dos placeholders. No modo OU, um
  CPV sem correspondência não esvazia o lado das palavras. Medido:
  manutenção E CPV72 = 46; OU = 3 970.
- **B08 — leituras configuráveis** (30/08/2026). `leituras_activas()`
  põe o `config.json` por cima das `LEITURAS` (quais/âncoras/instrução,
  campo a campo), com validação — um regex estragado deixa ficar o de
  origem, nunca cala uma leitura. **O 4.º campo do utilizador ficou de
  fora**: a tabela `analise` tem colunas fixas e o caso de uso ainda
  não apareceu; reabre-se quando aparecer.
- **B09 — pesquisa nas peças: implementado e RETIRADO** (30/08/2026,
  tudo no mesmo dia). Três versões no dia: campo na lista (cobria 17
  anúncios em 66 mil — enganava), caixa na ficha com excertos (tirava
  a linha do sumário; corrigido com `excerto_de()`), e por fim a
  decisão do Afonso de retirar: **as peças só existem depois de marcar
  "interessa"**, por isso a pesquisa chegava sempre tarde demais para
  ajudar a decidir — não se estava a ganhar nada. O índice FTS saiu da
  base (migração de limpeza no `iniciar_db`) e há teste a impedir o
  regresso acidental. O que ficou de útil: as marcas de página do B12
  no extractor, que eram partilhadas. **A versão que valeria a pena**,
  palavras dele: ver o próprio PDF dentro da aplicação, com pesquisa lá
  dentro — está em baixo, no «Não fazer (por agora)».
- **B10 — seguir entidades** (30/08/2026). Botão na ficha da entidade;
  os anúncios novos das seguidas entram no resumo diário em secção
  própria (reconhecer/enviar como os alertas, acervo ao começar a
  seguir, com âmbito só dessa entidade). Casamento pelo NIPC
  (`anuncios.nif` = chave); entidades `n:` (sem NIF) não têm aviso e a
  ficha não oferece o botão. **Contratos novos das seguidas ficaram de
  fora**: o corpus chega semanal e a ficha da entidade já os mostra;
  reabre-se se fizer falta na prática.

- **B11 — soma do preço base por coluna do quadro** (30/08/2026). O
  cabeçalho da fase diz "2 · 123,4 k€", com o title a dizer sobre
  quantos anúncios com preço lido é a soma (`soma_precos_base()`) —
  somar uns e calar os outros parecia o valor da fase inteira.
- **B12 — fontes com página** (30/08/2026). A premissa confirmou-se: o
  extractor lê página a página, e passou a juntá-las com `\f` em linha
  própria. `paginas_do_recorte()` sai das MESMAS janelas do recorte
  (`_janelas_do_recorte()` partilhado) e as fontes da análise dizem
  "CE.pdf (pág. 1–5)" — por leitura, que objecto e equipa lêem zonas
  diferentes. Textos antigos reextraíram-se uma vez por marca
  (`texto_com_paginas`, 49 s); os sem ficheiro em disco ficaram como
  estavam. Num ZIP com vários PDFs a página é do texto extraído, e a
  nota di-lo.
- **B13 — janela do "urgente" configurável** (30/08/2026).
  `dias_urgente()` lê o `config.json` (lixo/zero voltam a 10) e TODOS os
  sítios leem dela — filtro, rótulos, cartão dos indicadores, saúde.
  Edita-se no painel, em `/alertas` ("Janela do urgente"), com validação
  1–90 à vista.

## Anotado no esqueleto de informação de 30/08/2026

- ~~Procura directa de entidade (nome ou NIF)~~ — **reaberta e feita a
  31/08/2026, a pedido dele**: caixa «Ficha de entidade» em Mercado e
  rota `/entidade/procurar`, exactamente como aqui estava desenhado —
  NIF vai directo (é a chave do corpus), nome resolve por
  `entidade_nomes` com `norma_entidade()`; resolução única abre a
  ficha, várias dão lista de escolha, nenhuma di-lo. Tinha ficado de
  fora do esqueleto por decisão dele (11.7-A), com a possibilidade
  registada — o registo serviu.

## Anotado no saneamento de 30/08/2026 — FEITO a 31/08/2026

- **Reter histórico de erros (C3 da auditoria) — feito.** Tabela
  `erros (quando, tipo, texto)` no `radar.db`; `marca_erro()` grava a
  marca de sempre (o ecrã lê-a) MAIS uma linha na série, e a poda no
  `iniciar_db()` guarda os últimos 200 por tipo — os recentes, com
  teste a garantir que não são os primeiros. Tipos: relogio, pecas,
  leitura, copia, token. Leitura por SQL, como proposto; o ecrã fica
  para quando fizer falta.
- **E4 — registar quando o token expira — feito.** Nos quatro pontos
  onde a expiração se detecta (pesquisa e detalhe), o registo grava o
  momento E a idade da captura (`registar_expiracao_token()`, mtime do
  `curl_*.txt`), na série do C3 e na marca `token_ultimo_erro` — que
  aparece nos indicadores como "Última expiração do token". É o
  instrumento que faltava para o piso «≥ 8 dias» virar frequência.
- **O «último recurso do texto todo» na detecção de plataforma — medido
  e corrigido.** Medição a 31/08 (só leitura, sobre a base): dos 56 com
  detalhe e sem plataforma, 18 tinham pistas reais (o strip() não lhes
  toca) e **28 diziam a plataforma por extenso no corpo** — todos
  acingov, referência directa ("apresentados através da plataforma
  eletrónica acinGov"), nenhuma menção de passagem. Aplicado o
  `strip()`, `--reler` (8,2 s): 56 → 28 sem plataforma, e a protecção
  contra menções de passagem continua de pé (pistas reais que não batem
  em nada continuam a NÃO cair para o texto — testado).

## Aprovado pelo Afonso a 30/08/2026

- **B15 — exportação da triagem — FEITO a 31/08/2026.** Implementado
  como especificado abaixo: `exportar_triagem()` corre a seguir à cópia
  diária dentro do `verificar()` (e à mão por `--exportar-triagem`),
  escreve o **`triagem.jsonl`** — 8 330 registos no primeiro export,
  exactamente a medição de 31/08 — com um registo por linha, chaves
  ordenadas e ordem determinística; `--repor-triagem` é o restauro
  idempotente com o relatório dos refs por repor. A escrita é por
  ficheiro temporário + `os.replace`, para um export interrompido não
  fazer de cópia. **A sub-decisão do push continua aberta** (manual ou
  tarefa semanal): por agora é manual — cada commit da sessão leva o
  ficheiro — e só a tarefa semanal fecha mesmo o R2. A especificação
  original fica abaixo, como registo.
  Luz verde do Afonso a 31/08/2026, **e sem urgência**: ele avisou no
  mesmo dia que todo o histórico de actividade actual é **de teste**,
  portanto perder a triagem hoje não custa nada. O risco estrutural
  mantém-se e a especificação fica pronta; **o gatilho é a primeira
  semana de triagem a sério**, e convém não deixar passar disso. O problema: o remoto do GitHub já
  põe o **código** fora do PC, mas a **triagem** — o único dado
  declaradamente irrecuperável — continua só no disco `D:`, porque a
  base de trabalho está no `.gitignore` e ele não tem disco externo. A
  saída é o tamanho: das dezenas de MB da base, a parte irrecuperável
  são **8 330 linhas** (medido a 31/08). Isso cabe num ficheiro de texto
  que viaja no repositório que já existe, e cada push passa a ser uma
  cópia da triagem fora do PC, sem comprar nada.

  **O que entra** (e nada mais — o resto refaz-se): de `anuncios`, só
  `ref`, `estado`, `fase_id`, `responsavel` e `visto_em`, e só das
  linhas triadas, com fase ou com responsável (4 107); `historico`
  inteiro (4 150); `fases` (5); `etiquetas` e `anuncio_etiquetas`;
  `filtros_guardados`; `entidades_seguidas`; e as marcas de já-avisado
  (`alertas_vistos`, `seguidas_vistos`, 66) — sem elas, o primeiro
  resumo depois de um restauro traz tudo outra vez.

  **Formato, e a razão:** um registo por linha, chaves ordenadas, ordem
  determinística. Não é estética — é o que faz o `git diff` mostrar *o
  que mudou hoje* em vez de um ficheiro inteiro reescrito, e é isso que
  torna o histórico do repositório uma máquina do tempo da triagem em
  vez de um monte de versões opacas.

  **Quando corre:** a seguir à cópia diária, dentro do `verificar()` —
  são milhares de linhas, custa nada, e assim está sempre fresco.
  **Como sai do PC:** o export torna o dado pequeno; sair daqui exige um
  push. Ou o Afonso faz commit quando calha, ou uma tarefa semanal faz
  commit+push se o ficheiro mudou. A segunda é a que fecha mesmo o R2,
  com o custo de meter commits de dados no histórico do código — com
  mensagem padronizada, é ruído tolerável. **Decisão dele, quando isto
  se fizer.**

  **Restauro:** um comando próprio, idempotente, para correr **depois**
  de a base ser refeita pela recolha — o ficheiro guarda decisões, não
  anúncios, e os anúncios voltam do DR. Um `ref` que ainda não exista na
  base não se inventa: fica num relatório no fim, para se saber o que
  ficou por repor. Sem isto o restauro parecia completo e não era.

  **O que o ficheiro leva de pessoal:** as decisões dele e o histórico
  com o nome de quem agiu. Repositório privado, dados dele — mas fica
  dito, porque passa a estar fora do PC.


- **B14 — segunda fonte de anúncios — EM PRODUÇÃO desde 31/08/2026,
  com o âmbito estrito dele** («sim quero avançar mas só com consultas
  preliminares ou com algo que não seja publicado no DR. não quero
  duplicação de anuncios»). O que ficou a correr: `recolher_vortal()`
  dentro de cada verificação (desliga-se com `vortal_preliminares:
  false`), a bater no `SearchTenders` da pesquisa pública
  (POST JSON `{"contractNoticeActive":true,"pageNumber":N,
  "pageSize":50}`), a filtrar **país PT + tipo preliminar** — o rótulo
  muda com o idioma da sessão («GovPT - Consulta Preliminar» /
  «Quick Tender GovPT», verificado item a item — aceitam-se os dois —
  e concursos públicos NUNCA entram, porque esses o DR publica. Cada
  consulta entra como anúncio com `fonte='vortal'`, ref natural
  `PT1.NTC.x` (nunca colide com refs do DR), `detalhe_lido=1` (não há
  detalhe DR), prazo/preço/datas da API; as releituras do DR filtram
  por fonte e não lhe tocam; a cadeia das peças aceita o link público
  (o PT1.NTC vem às claras e salta-se o primeiro salto). **Primeira
  recolha real: 17 consultas** — ULS de Santo António, São José,
  Tâmega e Sousa, municípios — com prazos de 2 a 7 dias, na Triagem no
  minuto seguinte. A **acingov fica de fora**: a listagem pública dela
  não mostra tipo nem datas, e sem isso não se garante «não publicado
  no DR» sem abrir os detalhes um a um — alargar é decisão nova, com
  medição antes.

  Decisão original dele, a 30/08/2026, sobre o item que estava em «Não
  fazer» à espera precisamente disto: «podemos avançar com a ligação à
  vortal e acingov se der, apenas para procedimentos que não sejam
  publicados em DR». É a maior lacuna medida face à Tendios/Armilar/SpotGov
  (consultas preliminares e contratos menores — `titulo LIKE '%Consulta
  preliminar%'` dava **zero** na base do radar; hoje dá as da Vortal).

  **O âmbito, que é o que torna isto seguro de desenhar:** só entra o que
  a parte L não publicou. Nada de duplicar o universo do DR — a regra de
  deduplicação é a de sempre, o `ref`, e o que vier das plataformas com
  anúncio no DR ignora-se. Isso mantém a promessa «o DR é a fonte dos
  anúncios» intacta e faz da segunda fonte um acrescento, não um
  concorrente.

  **O «se der» era a primeira tarefa — e foi medido a 31/08/2026:
  existe listagem anónima nas DUAS plataformas.** O que se viu, sem
  sessão iniciada e à mão (medição, não ingestão):

  - **acingov**: zona pública em
    `https://www.acingov.pt/acingovprod/2/zonaPublica/zona_publica_c/indexProcedimentos`
    (POST `procedure_search`; é o formulário da própria homepage).
    Paginada por `zona_publica_c/getProcedimentos/true/<offset>`, 8
    por página; no momento da medição dizia **598 procedimentos a
    decorrer**. Campos por linha: nº de procedimento, tipo, objecto,
    entidade, estado — **sem data de publicação nem prazo na listagem**
    (a confirmar no detalhe). Filtros: texto, sector de actividade,
    concelho. Cada linha traz um botão «Descarregar Peças» com um
    `data-id` cifrado — as peças alcançam-se da própria listagem, sem
    passar pelo link do DR.
  - **Vortal**: pesquisa pública «Consultas Ativas» em
    `https://community.vortal.biz/PRODPublic/Tendering/ContractNoticeManagement/Index`
    (ligada da página de login da vision). Campos ricos: referência,
    comprador, tipo de consulta, preço base, estado, fase, **data de
    publicação e data limite** com contagem de dias; filtros por texto,
    comprador, país (também lista ES — filtrar PT), datas e estado;
    ~108 páginas no momento. O «Detalhe» de cada linha é
    `https://community.vortal.biz/Public/contract-notice-view/PT1.NTC.<id>/`
    — **entrega directamente o `PT1.NTC.x`**, a peça central da cadeia
    de 3 saltos que `obter_documentos()` já usa; a ingestão encaixaria
    no código existente sem o salto de descodificação do link do DR.
  - **A premissa do âmbito confirmou-se à primeira página**: a
    listagem da Vortal mostrava três **«GovPT - Consulta Preliminar»**
    nas primeiras sete linhas — exactamente o tipo que a parte L não
    publica (`titulo LIKE '%Consulta preliminar%'` dá zero na base).

  O que a medição NÃO responde e fica para a fase de ingestão: quanto
  do universo das listagens duplica o DR (o cruzamento é pelo `ref`,
  que a listagem da acingov não mostra — pode obrigar a abrir o
  detalhe), a estabilidade dos endpoints (R4/R5), e o ritmo de
  varrimento aceitável. **Nada disto se escreve sem decisão informada
  do Afonso, plataforma a plataforma.**

  **Os avisos do item antigo mantêm-se, porque a decisão não os apaga**
  [LEGAL] [RISCO]: são plataformas comerciais, o caminho sai do que hoje é
  acesso anónimo a peças públicas, há atrito possível com termos de
  utilização, e a fragilidade é a do R4/R5 multiplicada (uma mudança de
  layout passa a parar recolha, não só peças). Recomendação de execução:
  primeiro a medição, depois uma decisão informada sobre cada plataforma —
  pode dar «a Vortal dá e a acingov não», e isso é resultado, não falhanço.

## Não fazer, e porquê

Decisões registadas com a observação que as sustenta. Reabrem-se se a
premissa mudar — com data e números novos.

- ~~Visualizador de PDF dentro da aplicação~~ — **saiu do «Não fazer»
  a 31/08/2026, a pedido dele, e está feito**: os PDF das peças abrem
  em `/peca/<ref>/<nome>`, dentro do painel, exactamente pelo caminho
  barato aqui anotado (um `<embed>` do ficheiro de `documentos/`; a
  pesquisa é o Ctrl+F do visualizador do browser). A caixa de pesquisa
  solta (B09) continua retirada — isto é a versão que ele queria.

- **Número de licitadores por concurso** — Armilar e SpotGov mostram-no;
  **não há fonte pública**: o dump do IMPIC não o traz (medido a 29/08) e o
  da Armilar vem presumivelmente dos dados internos da própria plataforma.
  Prometê-lo seria inventá-lo.
- **Previsão do preço vencedor por ML** (SpotGov, BETA deles) — sem o nº de
  licitadores nem dados de propostas, o radar só teria o desconto histórico
  (B04), que é a versão honesta da mesma pergunta. A versão "intervalo de
  confiança de 80%" é marketing não verificável — não perseguir.
- **Geração e revisão de propostas por IA** (SpotGov Plus, Tendios
  Advanced) — viola a condição de princípio do projecto: **propostas, CVs e
  trabalho próprio não passam pelo modelo** (registada desde o início no
  docs/diario/). Não é falta de capacidade, é decisão de âmbito.
- **Chat livre sobre as peças** (Armilar Q&R) — o orçamento de modelo do
  radar é medido ao token (8 mil/min, 200 mil/dia na Groq) e um chat torna o
  consumo imprevisível; as três leituras estruturadas + B08 (perguntas
  configuráveis) cobrem o caso de uso com custo previsível. Reavaliar se
  houver Dev Tier.
- **Pesquisa em linguagem natural** ("Search with AI" da SpotGov) — para um
  utilizador que conhece o CPV e o mercado, a árvore com contagens + palavras
  + exclusões (B01) responde mais depressa e sem gastar orçamento.
- **Multi-país (Espanha)** — a observação da Tendios e da Armilar mostra o
  custo de o fazer mal (taxonomia trocada, traduções com fugas, ruído
  catalão na lista). O radar é bom precisamente por ser só parte L, bem.
- **Multi-utilizador a sério** (permissões, comentários, atribuição além do
  `responsavel`) — o radar é 1–2 pessoas; SpotGov e Tendios vendem equipas.
  Reabrir quando houver equipa. **A 3/09/2026 ficou decidido que não é
  isto que se faz**: o Afonso quer o radar online **para ele**, com
  login para fechar a porta e as configurações num menu — o plano está
  em `docs/historico/ONLINE.md`. Empresas e utilizadores por empresa
  foram pensados na mesma tarde e postos de lado
  (`docs/historico/ONLINE-empresas.md`). **A 8/09/2026 o radar passou
  a correr em Ubuntu** (`.sh`, `.venv`, temporizadores do systemd,
  painel como serviço) — é o degrau antes da etapa 3 do plano, servir
  para fora. **As três etapas ficaram feitas no mesmo dia**: o
  login (`contas.py`, `/entrar`, sessões, CSRF, trinco), o endereço
  fixo `https://radargov.pt` (túnel com nome, `tunel_fixo.sh`) e o
  menu de Configurações (`/configuracoes/<seccao>`, sete secções;
  Alertas saiu da barra). A pasta já está no disco interno
  (`~/Desktop/radar`), com o `linger` ligado. O painel no telemóvel,
  que ele tinha adiado de manhã («vai ser utilizada maioritariamente no
  PC»), pediu-o à tarde: feito no mesmo dia, um ponto de corte a 900 px.
- **App móvel / push** — o e-mail diário chega ao telemóvel; um push a mais
  não muda nenhuma decisão de dia útil.
- **Contagem decrescente ao segundo, mapas nas fichas** (GovGo, Armilar) —
  ornamento; os dias restantes calculados (`dias_restantes()`) dizem o mesmo.
- **Exportação Excel nativa** (Armilar CSV+Excel, Tendios 4 formatos) — o
  CSV do radar já sai com vírgula decimal e data no nome para o Excel
  português (`numero_csv()`/`nome_csv()`); um .xlsx a sério só acrescentaria
  dependências. Reavaliar se o Afonso alguma vez tropeçar no CSV.
