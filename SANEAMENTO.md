# Saneamento pós-auditoria — 30 de agosto de 2026

Sessão de correcção dos problemas de estado dos dados, operação e
documentação apontados pela `AUDITORIA.md` do mesmo dia. Sem
reestruturação, sem decisões visuais, sem refactor de fundo; toda a
correcção de dados foi feita como migração idempotente dentro de
`iniciar_db()`/`iniciar_corpus()`, guardada por marca, no padrão das
que já lá estavam. Nada foi escrito à mão nas bases nem tocado nas
capturas.

**Estado final: 424 testes verdes em ~0,8 s** (eram 405). As migrações
foram aplicadas à base real pelo caminho normal (`--reler`, 21,5 s, e
`iniciar_corpus()` no arranque), com verificação antes/depois.

---

## A. Dados presos

### A1 — 30 documentos presos em «erro: cryptography…»

- **O que estava:** `texto_estado = "erro: cryptography>=3.1 is
  required for AES algorithm"` em 30 documentos, com a dependência já
  instalada (cryptography 50.0.1); `extrair_textos()` só processava
  `texto_estado IS NULL`, portanto nunca seriam retentados.
- **O que se fez:** (i) migração por marca (`erros_extraccao_limpos`)
  que limpa para NULL os estados `erro:%cryptography%` — só os
  obsoletos, cuja causa desapareceu; (ii) **caminho geral de
  retentativa**: `extrair_textos()` passou a processar também
  `texto_estado LIKE 'erro:%'`. A escolha foi **retentar
  automaticamente na passagem seguinte**, não por botão: a extracção é
  local, sem rede e sem orçamento de modelo, e só corre quando alguém
  já pediu as peças ou a leitura desse anúncio — tentar outra vez não
  custa nada, e um botão seria interface nova para uma acção gratuita.
  «scan» e «não é PDF» são veredictos sobre o conteúdo, não falhas, e
  esses não se repetem.
- **Resultado na base real:** os 30 voltaram à fila e **extraíram
  todos** — `ok` passou de 56 para 86; zero `erro:` restantes.
- **Testes:** `TestMigracoesDoSaneamento.test_erro_cryptography_volta_a_fila_e_uma_vez_so`
  (efeito + idempotência: a segunda passagem não toca num erro novo com
  a mesma cara) e `TestRetentativaDeExtraccao` (erro retenta-se,
  veredictos ficam).
- **Por fazer:** nada.

### A2 — 12 análises com `modelo` no formato antigo

- **O que estava:** 12 das 18 linhas de `analise` com
  `openai/gpt-oss-120b` sem prefixo de fornecedor, e uma linha mista
  (`nvidia:…, openai/gpt-oss-120b`).
- **O que se fez:** migração por marca (`modelo_com_fornecedor`) que
  converte segmento a segmento com `_modelo_com_fornecedor()`. **A
  regra e porquê:** um segmento sem `:` só pode ter sido escrito antes
  da cadeia de fornecedores (27/08/2026), quando `_perguntar()` só
  falava com a Groq — os outros fornecedores nasceram já com o prefixo
  posto. O prefixo atribuído é portanto `groq:`, determinável, não
  adivinhado. Segmentos com `:` (prefixados, ou nomes de modelo com `:`
  no próprio nome, como `z-ai/glm-5.2:free`) ficam intactos.
- **Resultado na base real:** 16×`groq:…` e 2 mistas, todas
  prefixadas; nenhum valor sem fornecedor.
- **Testes:** `TestModeloComFornecedor` (6 casos, incluindo o misto
  real da base e a idempotência da função) e
  `TestMigracoesDoSaneamento.test_modelo_antigo_converte_e_duas_passagens_dao_o_mesmo`.
- **Por fazer:** nada.

### A3 — chaves e índices legados

- **O que estava:** `ultimo_aviso` e `ultimo_aviso_texto` na tabela
  `estado` (esquema de avisos anterior ao par reconhecer/enviar de
  `alertas_vistos`); `ix_cpv_c` e `ix_adj_c` no `contratos.db`, não
  recriáveis pelo código actual.
- **Decisão e porquê:** **remover os quatro.** As chaves não são lidas
  nem escritas por código nenhum — recriá-las era ressuscitar um
  esquema morto. Os índices são cobertos pelos únicos
  `ux_cpv`/`ux_adj`, que começam por `contrato_id` e servem os mesmos
  acessos; um corpus refeito de raiz não os teria, portanto apagá-los
  põe o corpus existente igual ao que o código produz e poupa a
  manutenção deles na importação semanal.
- **O que se fez:** `DELETE`/`DROP INDEX IF EXISTS` idempotentes nos
  dois `iniciar_*()` (o mesmo padrão da limpeza do FTS retirado).
  Verificado na base real: chaves a zero, índices ausentes.
- **Testes:** `TestMigracoesDoSaneamento.test_chaves_legadas_do_estado_saem`.
  A queda dos índices não tem teste próprio: é um `DROP IF EXISTS`
  literal, idempotente por construção, e um teste ao corpus obrigava a
  montar um `contratos.db` temporário só para confirmar que o SQLite
  faz o que o SQLite faz — anotado como assumido.
- **Por fazer:** nada.

## B. Documentação a mentir

### B1 — topo do ESTADO.md com números 13× errados

Corrigido o parágrafo «Como está a correr»: 66 081 anúncios de dois
anos, 8,3 % com detalhe lido (5 493), com a consequência prática (um
filtro por CPV só vê quem tem detalhe) e a nota de que a decisão dos
60 dias foi revertida na prática pelo `--historico 730`. Ficou lá
escrito porque é que o parágrafo mentia (camadas de datas sem corrigir
o topo) e a remissão para a regra nova do CLAUDE.md (B7).

### B2 — «a cadeia nunca correu pelo caminho normal»

Corrigido: a coluna `analise.modelo` — que só `analisar_pecas()`
escreve — prova que a cadeia desceu até ao NVIDIA em produção pelo
menos duas vezes, uma delas com os dois rótulos juntos (o
`juntar_fontes()` a funcionar na coluna `modelo`). Os pontos 1–3 da
lista «o que falta verificar» saíram como cumpridos; ficou só o que
falta mesmo: medir o NVIDIA em ritmo corrente (os 240 s mediram-se em
rajada).

### B3 — LEIA-ME §14: «o radar lê o anúncio, não as peças»

Secção reescrita: abaixo dos limiares não há anúncio nenhum e o radar
traz esses procedimentos como contratos celebrados (dump semanal do
IMPIC, sem chave — a API que nunca respondeu deixou de fazer falta); as
peças são trazidas e lidas por modelo (remissão para §6); o que
continua de fora está dito (nº de concorrentes, publicações
só-de-plataforma).

### B4 — LEIA-ME §12: «82 verificações»

Corrigido para 424, a contagem no fim desta sessão (a auditoria contou
405; os 19 novos são desta sessão). O número voltará a envelhecer — a
regra B7 é o que o mantém honesto daqui em diante.

### B5 — varrimento dos três ficheiros

Encontrado e corrigido, para lá do que a auditoria já listava:

| Onde | Dizia | Está agora |
|---|---|---|
| ESTADO «Coisas a saber» | «o painel limita a tabela a 500 linhas» | pagina a 20 (`POR_PAGINA_LISTA`) |
| ESTADO «Testes…» | «118 testes, em milissegundos» | 415 à data, <1 s, com nota de que as migrações usam base temporária |
| ESTADO «Estrutura do código» | «sem dependências além de flask e requests» | quatro: flask, requests, pypdf, cryptography |
| ESTADO «Lista paginada» | `POR_PAGINA = 20` | nota do rename para `POR_PAGINA_LISTA` (D4) |
| LEIA-ME intro | «Fonte única: … o portal do DR» | duas fontes: DR e Portal BASE |
| LEIA-ME §2 | «instala o flask e o requests»; «tarefas das 09h e 17h» | as quatro dependências; as três tarefas (inclui corpus à segunda) |
| LEIA-ME §5 | faltavam exclusões, E/OU, prazo, filtros guardados, Contratos/Renovações/Alertas | acrescentados |
| LEIA-ME §5 | «a coluna "Faltam ler os detalhes de N"» (não existe) | o cartão «Sem detalhe lido» dos Indicadores |
| LEIA-ME §12 | faltavam `--contratos` e `--descartar-expirados` | acrescentados |
| LEIA-ME §13 | tabela sem `curl_detalhe.txt`, `contratos.db`, `copias/`, `AVISOS.txt` | completa |
| CLAUDE.md | «~8200 linhas»; lista de `.bat` sem `contratos.bat` | «~10 mil»; lista completa |
| hook `testes_antes_do_commit.py` | «São 118 testes» | sem número exacto (envelhecem todos) |

Deixado como está, de propósito: as secções datadas do ESTADO.md que
narram o passado com os números do passado («5125 anúncios em ~6 s»,
medições antigas) — são diário, não descrição do presente.

### B6 — a chave `leituras` invisível

Acrescentada ao `CONFIG_INICIAL` (`"leituras": {}`, neutro — um exemplo
a sério lá dentro mudava o comportamento de quem nunca a afinou) com o
exemplo funcional em comentário, e ao LEIA-ME §4 com exemplo JSON
pronto a copiar. Teste que a guarda: os `TestLeiturasConfiguraveis`
já cobriam a semântica; a presença no config de origem fica coberta
pelo arranque normal (o `ler_config()` funde `CONFIG_INICIAL`).

### B7 — regra anti-reincidência no CLAUDE.md

Acrescentada como procedimento, não como intenção: antes do commit de
trabalho que mude comportamento/números/decisões, procurar nos três
`.md` as afirmações que o trabalho tornou falsas e corrigi-las **no
mesmo commit**; o parágrafo «Como está a correr» é paragem
obrigatória quando os números mudam; um commit que muda `radar.py` sem
tocar em nenhum `.md` é sinal para verificar.

## C. Visibilidade de erros

### C1 — `ultimo_erro_relogio` e `docs_ultimo_erro` só por SQL

Passam a linhas na **saúde dos Indicadores** (superfície que já
existia; nenhuma página nova), a amarelo — a marca é sobrescrita e pode
ser antiga, por isso é diagnóstico e não alarme. Incluiu-se também
`analise_ultimo_erro`, que estava na mesma situação e é da mesma
família. As três marcas passaram a levar **data** no valor, para se
saber de quando é o erro que se está a ver. Só aparece linha quando há
erro gravado — uma linha verde «sem erros» era ruído.
**Teste:** `TestLinhasDeUltimosErros` (nada→nada, só o que existe,
escape de HTML, truncagem por `corta()`).

### C2 — a cópia de segurança falhava para uma consola que ninguém vê

`copia_com_marca()` embrulha a cópia e grava `ultima_copia`
(`ok: radar-….db` / `falhou a <data>: <erro>`), no padrão das marcas
existentes; `verificar()` passou a usá-la, e a linha «Cópia de
segurança» aparece na saúde dos Indicadores — vermelha quando a última
tentativa falhou, que é estado presente e accionável.
**Teste:** `TestCopiaComMarca` (falha grava marca com data; sucesso
grava o nome do ficheiro).

### C3 — marcas sobrescritas apagam a história

Não implementado, como pedido. Proposta registada no BACKLOG.md
(«Anotado no saneamento»): tabela `erros (quando, tipo, texto)` com o
`marca()` dos erros a duplicar para lá e poda aos últimos ~200 por
tipo no `iniciar_db()` — leitura por SQL chega para começar. Esforço 1.

## D. Lixo e resíduos

### D1 — lixo em disco

`painel.log` (morto desde 27/08), `__pycache__/` e as 4 worktrees
vazias de `.claude/worktrees/` apagados. O `.gitignore` já cobria
`painel.log` e `__pycache__/`; acrescentou-se `.claude/worktrees/`
para a reincidência.

### D2 — `radar_chave()` duplicava `simplifica().strip()`

Função removida; a única chamada (parser do critério de adjudicação)
faz `simplifica(chave).strip()` no sítio. Sem teste próprio — é remoção
de um sinónimo, e os testes do critério de adjudicação continuam
verdes.

### D3 — `if "acin" in alvo` solto

Passou a `SINONIMOS_PLATAFORMA = {"acin": "acingov"}`, declarado ao
lado de `PLATAFORMAS`, com a regra escrita: um sinónimo aponta sempre
para uma plataforma da lista, nunca inventa uma nova.
**Teste:** `TestSinonimosDePlataforma` (todo o sinónimo aponta para a
lista; «acin» continua a dar acingov pelo caminho real das pistas; o
nome por extenso ganha). Verificado na base real: as contagens de
plataforma ficaram exactamente iguais antes e depois do `--reler`.
**Achado de caminho:** o «último recurso do texto todo» desta detecção
está morto desde sempre (o join de pistas vazias dá `"  "`, truthy).
Fora de âmbito mexer no parser sem medir — registado no BACKLOG.

### D4 — `por_pagina` (config, recolha) vs `POR_PAGINA` (código, lista)

Renomeada a constante do código para **`POR_PAGINA_LISTA`** (12
ocorrências) — o lado do config não se mexeu porque `por_pagina` vive
no `config.json` dos utilizadores e renomeá-lo exigia migração de
configuração para ganho nenhum. O comentário do config diz agora
explicitamente que é da recolha e aponta a diferença; ESTADO.md
actualizado. Sem teste próprio: é rename mecânico, coberto pelos testes
de paginação existentes.

---

## E. Decisões que são do Afonso — preparadas, não executadas

### E1 — Tudo num PC, dentro do OneDrive, sem remoto git (R2/R3)

O que está em risco, por ordem de gravidade: a **triagem** (interessa/
descartado, fases, responsáveis, histórico — declaradamente
irrecuperável), o **código com os 68 commits**, e por fim corpus e
documentos (refazem-se). As `copias/` diárias estão no mesmo disco e
dentro da mesma conta OneDrive que a base — o OneDrive dá uma cópia
fora da máquina, mas é **sincronização, não backup**: uma corrupção ou
um apagão de conta propaga-se, e é a mesma conta que já bloqueia o
`radar.db` a meio de escritas.

**Para o código (remoto git):**

| Opção | Passos | Exposição |
|---|---|---|
| **1. GitHub/GitLab privado** | criar repo privado; `git remote add origin …; git push -u origin master` — 5 min | o código e os `.md` (incluindo ESTADO/CONCORRENTES, que têm análise competitiva) ficam nos servidores do fornecedor, privados por omissão; sem segredos — o `.gitignore` exclui capturas, chaves e bases (confirmado nesta sessão) |
| **2. Remoto `--bare` num disco externo/NAS** | `git init --bare` no disco; `git remote add`; push manual ou agendado | zero terceiros, mas o disco vive tipicamente na mesma casa — protege de disco morto, não de incêndio/roubo |
| **3. As duas** | 1 + 2 | melhor dos dois; custo: dois pushes |

**Para a triagem (cópia externa do `radar.db`):**

| Opção | Passos | Exposição |
|---|---|---|
| **a. Tarefa Windows que espelha `copias/` para um disco USB** | `robocopy` agendado depois das 09h; um disco de 32 GB chega para anos | nenhuma; exige o disco ligado |
| **b. rclone/restic cifrado para um bucket (Backblaze B2, ~0 €/mês a esta escala)** | instalar rclone, configurar remoto cifrado, tarefa semanal | dados cifrados no cliente; o fornecedor vê blobs |
| **c. Aceitar o OneDrive como está** | nada | continua um único ponto: a conta Microsoft |

A combinação mais barata que fecha o R2: **opção 1 + a** (código na
nuvem privada, triagem num disco físico separado). A decisão — e a
conta GitHub/disco a usar — é tua.

### E2 — Canal de aviso morto: o que falta fornecer, passo a passo

O mecanismo está construído e testado; nunca entregou porque falta a
última milha. Para o ligar:

1. **Decidir a conta que envia** (pode ser o teu Gmail). No
   `config.json`, preencher `email.de` (o endereço que envia);
   `servidor`/`porta` já vêm para Gmail (`smtp.gmail.com`, 587).
2. **Criar uma palavra-passe de aplicação** na conta Google (exige
   verificação em 2 passos): myaccount.google.com → Segurança →
   Palavras-passe de aplicação. Gravar **só a senha** num ficheiro
   `email_senha.txt` na pasta do radar (está no `.gitignore`).
3. **No painel, em /alertas:** preencher o destino («para» — pode ser o
   mesmo endereço) e a hora do resumo. O ecrã mostra a verde/amarelo o
   que está posto.
4. **Ligar alertas aos filtros que interessam.** Hoje há um («CPV IT»).
   Ao ligar, o acervo é marcado — o primeiro resumo não traz tudo.

Para confirmar que **um resumo com conteúdo saiu mesmo**:

1. Carregar em «Enviar resumo já» (em /alertas) → deve chegar um
   e-mail; se falhar, a página diz porquê (autenticação recusada =
   senha de aplicação errada).
2. Confirmar na base as marcas: `ultimo_resumo` com a data de hoje e
   `ultimo_resumo_estado` sem «por enviar»; o `AVISOS.txt` escrito na
   pasta.
3. Prova com conteúdo real: depois da verificação das 17h de um dia
   útil com anúncios novos que caiam no alerta, o e-mail deve listá-los
   e `alertas_vistos.enviado_em` ficar preenchido para esses refs.

**Fragilidade a saber** (da auditoria, secção 1.9): o resumo sai na
verificação que corre **à hora do resumo ou depois**; com verificações
às 09:00/17:00 e `hora_resumo` 17:00, depende de a tarefa das 17h
correr uns minutos depois das 17:00 — hoje corre (17:01–17:09). Se
mudares as horas, mantém `hora_resumo` ≤ hora da última verificação.

### E3 — Links do resumo apontam para `localhost:8765`

O e-mail chega ao telemóvel; os links não abrem lá nada. Opções, com o
custo de cada uma — **sem decisão tomada**:

1. **Aceitar como está**: o e-mail é gatilho («há 3 novos»), abre-se o
   painel no PC. Custo zero; os links continuam úteis no próprio PC.
2. **Tailscale (VPN pessoal)**: instalar no PC e no telemóvel; o PC
   ganha um nome estável e os links passam a funcionar no telemóvel,
   sem expor nada à internet. Implica um campo novo no config (o
   endereço-base dos links do resumo) — alteração pequena, a fazer só
   se escolheres isto. Contras: mais um serviço instalado, e o painel
   continua sem autenticação — dentro da tailnet só entras tu, mas é
   bom sabê-lo.
3. **Tirar os links do e-mail** (só refs e títulos): não promete o que
   não cumpre. Perde-se o clique no PC.
4. **Expor o painel à internet: não** — sem autenticação nem CSRF, está
   identificado no ESTADO como pré-requisito de partilha por cumprir.

### E4 — A frequência de expiração do token não está registada

A forma mais simples de a passar a registar, sem ecrã novo: quando a
recolha detecta «sem JSON, token pode ter expirado», gravar **uma linha
no `historico`** (`accao='token expirou'`) na primeira detecção de cada
episódio (guardado por uma marca `token_expirado_desde`, limpa quando
uma verificação volta a correr bem — que grava então
`accao='token recuperado'`). Com meia dúzia de ciclos, a pergunta
«quanto dura um token?» responde-se por SQL sobre o histórico, e o
`mtime` dos `curl_*.txt` dá a data de cada recaptura de graça. Esforço
1, sem rede, sem interface. Fica por implementar até dizeres que sim.

---

## Fora de âmbito, anotado e não executado

- Retenção de histórico de erros (C3) → BACKLOG.
- Fallback morto na detecção de plataforma → BACKLOG (medir com
  `--reler` sobre cópia antes de decidir).
- Tudo o que é reestruturação/visual/refactor de fundo ficou intocado,
  como pedido — nada de novo a acrescentar ao BACKLOG nessas
  categorias além do que já lá estava.
